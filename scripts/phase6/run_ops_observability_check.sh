#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BRIDGE_BASE_URL="${1:-http://localhost:8090}"
DASHBOARD_URL="${2:-http://localhost:3001}"
CHAT_UI_URL="${3:-http://localhost:8170}"
API_KEY="${RECALL_API_KEY:-}"
ARTIFACT_DIR="$ROOT_DIR/data/artifacts/observability"
ALERT_WEBHOOK_URL="${RECALL_UPTIME_ALERT_WEBHOOK_URL:-}"
ALERT_TELEGRAM_TOKEN="${RECALL_UPTIME_ALERT_TELEGRAM_BOT_TOKEN:-${RECALL_TELEGRAM_BOT_TOKEN:-}}"
ALERT_TELEGRAM_CHAT_ID="${RECALL_UPTIME_ALERT_TELEGRAM_CHAT_ID:-${RECALL_TELEGRAM_CHAT_ID:-}}"
NOTIFY_ON_SUCCESS="${RECALL_UPTIME_NOTIFY_ON_SUCCESS:-false}"
ALERT_COOLDOWN_MINUTES="${RECALL_UPTIME_ALERT_COOLDOWN_MINUTES:-60}"

mkdir -p "$ARTIFACT_DIR"

python3 - "$ROOT_DIR" "$BRIDGE_BASE_URL" "$DASHBOARD_URL" "$CHAT_UI_URL" "$ARTIFACT_DIR" "$API_KEY" "$ALERT_WEBHOOK_URL" "$ALERT_TELEGRAM_TOKEN" "$ALERT_TELEGRAM_CHAT_ID" "$NOTIFY_ON_SUCCESS" "$ALERT_COOLDOWN_MINUTES" <<'PY'
import json
import pathlib
import sqlite3
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from hashlib import sha256


root_dir = pathlib.Path(sys.argv[1]).resolve()
bridge_base = sys.argv[2].rstrip("/")
dashboard_url = sys.argv[3].rstrip("/")
chat_ui_url = sys.argv[4].rstrip("/")
artifact_dir = pathlib.Path(sys.argv[5])
api_key = sys.argv[6].strip()
alert_webhook_url = sys.argv[7].strip()
alert_telegram_token = sys.argv[8].strip()
alert_telegram_chat_id = sys.argv[9].strip()
notify_on_success = sys.argv[10].strip().lower() in {"1", "true", "yes", "on"}
try:
    alert_cooldown_minutes = max(0, int(sys.argv[11].strip() or "60"))
except ValueError:
    alert_cooldown_minutes = 60

timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
artifact_path = artifact_dir / f"{timestamp}_ops_observability_check.json"
alert_state_path = artifact_dir / "ops_observability_alert_state.json"


def api_headers(extra=None):
    headers = {"Accept": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    if extra:
        headers.update(extra)
    return headers


def fetch_json(url, *, method="GET", payload=None, timeout=60):
    data = None
    headers = api_headers()
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
        parsed = json.loads(body.decode("utf-8")) if body else {}
        return {
            "status_code": response.status,
            "headers": dict(response.headers.items()),
            "body": parsed,
        }


def build_url(base, *, include_gaps=None):
    if include_gaps is None:
        return base
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}include_gaps={'true' if include_gaps else 'false'}"


def build_n8n_webhook_base(bridge_url):
    parsed = urllib.parse.urlparse(bridge_url)
    port = parsed.port
    if port == 8090:
        netloc = parsed.netloc.rsplit(":", 1)[0] + ":5678"
    elif port is None:
        netloc = f"{parsed.netloc}:5678"
    else:
        netloc = parsed.netloc
    return urllib.parse.urlunparse((parsed.scheme or "http", netloc, "", "", "", ""))


def fetch_text(url, *, timeout=30):
    request = urllib.request.Request(url, headers={"Accept": "text/html"}, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(4096).decode("utf-8", errors="replace")
        return {
            "status_code": response.status,
            "headers": dict(response.headers.items()),
            "body_preview": body,
        }


def post_json(url, payload, *, timeout=15):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status >= 300:
            raise RuntimeError(f"POST {url} returned HTTP {response.status}")
        return response.status


def load_alert_state():
    if not alert_state_path.exists():
        return {}
    try:
        return json.loads(alert_state_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def save_alert_state(payload):
    alert_state_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def run_check(name, fn):
    try:
        result = fn()
        return {"name": name, "status": "ok", **result}
    except Exception as exc:  # noqa: BLE001
        return {"name": name, "status": "error", "error": str(exc)}


checks = []

checks.append(
    run_check(
        "bridge_health",
        lambda: {
            "endpoint": f"{bridge_base}/v1/healthz",
            **fetch_json(f"{bridge_base}/v1/healthz", timeout=20),
        },
    )
)


def dashboard_check():
    endpoint = f"{bridge_base}/v1/dashboard-checks"
    core_url = build_url(endpoint, include_gaps=False)
    core_payload = fetch_json(core_url, timeout=30)
    core_body = core_payload["body"]
    if str(core_body.get("status") or "").lower() != "ok":
        raise RuntimeError(f"dashboard-checks core status={core_body.get('status')!r}")
    if int((core_body.get("jobs") or {}).get("count") or 0) <= 0:
        raise RuntimeError("dashboard-checks core reported no jobs")
    if int((core_body.get("companies") or {}).get("count") or 0) <= 0:
        raise RuntimeError("dashboard-checks core reported no companies")

    result = {
        "endpoint": core_url,
        **core_payload,
        "include_gaps": False,
    }

    full_url = build_url(endpoint, include_gaps=True)
    try:
        full_payload = fetch_json(full_url, timeout=60)
        full_body = full_payload["body"]
        gaps = full_body.get("gaps") or {}
        if str(full_body.get("status") or "").lower() != "ok":
            raise RuntimeError(f"dashboard-checks full status={full_body.get('status')!r}")
        if gaps and str(gaps.get("status") or "").lower() != "ok":
            raise RuntimeError(f"dashboard-checks gaps status={gaps.get('status')!r}")
        result = {
            "endpoint": full_url,
            **full_payload,
            "include_gaps": True,
        }
    except Exception as exc:  # noqa: BLE001
        result["full_check_warning"] = f"full attempt failed: {exc}"

    return result


checks.append(run_check("dashboard_checks", dashboard_check))


def job_alert_workflow_check():
    db_path = root_dir / "n8n" / "database.sqlite"
    if not db_path.exists():
        return {
            "database": str(db_path),
            "skipped": True,
            "reason": "n8n database not present on this host",
        }
    if db_path.stat().st_size == 0:
        return {
            "database": str(db_path),
            "skipped": True,
            "reason": "n8n database is empty on this host",
        }

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        tables = {
            row[0]
            for row in cur.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        if "workflow_entity" not in tables:
            return {
                "database": str(db_path),
                "skipped": True,
                "reason": "n8n workflow_entity table not present on this host",
            }

        workflow_row = cur.execute(
            "SELECT active, nodes FROM workflow_entity WHERE id = ?",
            ("9DEQqfD8JA5PCiVP",),
        ).fetchone()
        if workflow_row is None:
            raise RuntimeError("Workflow 3 not found in n8n database")

        active, nodes_json = workflow_row
        if int(active or 0) != 1:
            raise RuntimeError("Workflow 3 is not active")

        nodes = json.loads(nodes_json)

        send_node = next((node for node in nodes if node.get("name") == "Send Telegram Alert"), None)
        if send_node is None:
            raise RuntimeError("Send Telegram Alert node missing")
        if send_node.get("type") != "n8n-nodes-base.telegram":
            raise RuntimeError(f"Send Telegram Alert node type={send_node.get('type')!r}")

        telegram_credential = ((send_node.get("credentials") or {}).get("telegramApi") or {})
        if str(telegram_credential.get("id") or "") != "6aWx4DnLbVi8JlGU":
            raise RuntimeError("Workflow 3 is not bound to the expected Telegram credential")

        aggregator_row = cur.execute(
            "SELECT nodes FROM workflow_entity WHERE id = ?",
            ("cWHLi1plI5siWP8X",),
        ).fetchone()
        if aggregator_row is None:
            raise RuntimeError("Job Board Aggregator workflow missing")

        aggregator_nodes = json.loads(aggregator_row[0])
        trigger_node = next(
            (node for node in aggregator_nodes if node.get("name") in {"Trigger Evaluation Workflow", "Queue Evaluation Run"}),
            None,
        )
        if trigger_node is None:
            raise RuntimeError("Aggregator evaluation handoff node missing")
        trigger_url = str(((trigger_node.get("parameters") or {}).get("url")) or "")
        if "/webhook/recall-job-evaluate" not in trigger_url:
            raise RuntimeError("Aggregator is not handing off to Workflow 3 webhook")
    finally:
        conn.close()

    probe_payload = {"job_ids": ["job_smoke_nonexistent"], "wait": True}
    n8n_base = build_n8n_webhook_base(bridge_base)
    probe_response = fetch_json(
        f"{n8n_base}/webhook/recall-job-evaluate",
        method="POST",
        payload=probe_payload,
        timeout=45,
    )
    body = probe_response["body"]
    if str(body.get("status") or "").lower() != "completed":
        raise RuntimeError(f"job alert webhook status={body.get('status')!r}")
    if int(body.get("notifications_sent") or 0) != 0:
        raise RuntimeError("job alert smoke unexpectedly sent a notification")

    return {
        "database": str(db_path),
        "endpoint": f"{n8n_base}/webhook/recall-job-evaluate",
        "credential": telegram_credential,
        "aggregator_handoff_url": trigger_url,
        "probe": {
            "status_code": probe_response["status_code"],
            "run_id": body.get("run_id"),
            "status": body.get("status"),
            "high_fit_count": body.get("high_fit_count"),
            "notifications_sent": body.get("notifications_sent"),
        },
    }


checks.append(run_check("job_alert_workflow", job_alert_workflow_check))


def rag_probe():
    payload = {
        "query": "What are the benefits of prompt engineering? Give a concise overview with bullet points.",
        "top_k": 8,
        "max_retries": 2,
        "retrieval_mode": "hybrid",
        "enable_reranker": True,
        "reranker_weight": 0.65,
    }
    response = fetch_json(f"{bridge_base}/v1/rag-queries", method="POST", payload=payload, timeout=120)
    body = response["body"]
    result = body.get("result") or {}
    answer = str(result.get("answer") or "").strip()
    citations = result.get("citations") or []
    audit = result.get("audit") or {}
    if len(answer) < 120:
        raise RuntimeError("RAG probe answer was too short")
    if len(citations) < 1:
        raise RuntimeError("RAG probe returned no citations")
    return {
        "endpoint": f"{bridge_base}/v1/rag-queries",
        "status_code": response["status_code"],
        "headers": response["headers"],
        "summary": {
            "strategy": audit.get("query_strategy"),
            "model": audit.get("model"),
            "fallback_used": audit.get("fallback_used"),
            "citation_count": len(citations),
            "answer_preview": answer[:240],
        },
    }


checks.append(run_check("rag_probe", rag_probe))
checks.append(
    run_check(
        "daily_dashboard_ui",
        lambda: {"endpoint": dashboard_url, **fetch_text(dashboard_url, timeout=20)},
    )
)
checks.append(
    run_check(
        "recall_chat_ui",
        lambda: {"endpoint": chat_ui_url, **fetch_text(chat_ui_url, timeout=20)},
    )
)

overall_status = "ok" if all(check["status"] == "ok" for check in checks) else "error"
artifact = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "bridge_base_url": bridge_base,
    "dashboard_url": dashboard_url,
    "chat_ui_url": chat_ui_url,
    "status": overall_status,
    "checks": checks,
}
artifact_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

print(json.dumps({"status": overall_status, "artifact": str(artifact_path)}, indent=2))
for check in checks:
    if check["status"] == "ok":
        print(f"[ok] {check['name']}")
    else:
        print(f"[error] {check['name']}: {check.get('error')}")

def build_alert_message():
    failing = [check for check in checks if check["status"] != "ok"]
    lines = [
        f"Recall.local ops observability {'ALERT' if overall_status != 'ok' else 'OK'}",
        f"bridge={bridge_base}",
        f"dashboard={dashboard_url}",
        f"chat={chat_ui_url}",
        f"artifact={artifact_path}",
    ]
    if failing:
        for check in failing:
            lines.append(f"fail={check['name']}: {check.get('error')}")
    else:
        rag_summary = next((check.get("summary", {}) for check in checks if check["name"] == "rag_probe"), {})
        lines.append(f"rag_strategy={rag_summary.get('strategy')}")
        lines.append(f"rag_model={rag_summary.get('model')}")
    return "\n".join(lines)


def failure_fingerprint():
    failing = [
        {
            "name": check["name"],
            "error": check.get("error"),
        }
        for check in checks
        if check["status"] != "ok"
    ]
    return sha256(
        json.dumps(
            {
                "bridge_base_url": bridge_base,
                "dashboard_url": dashboard_url,
                "chat_ui_url": chat_ui_url,
                "failing": failing,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


alert_message = build_alert_message()
now_ts = datetime.now(timezone.utc).timestamp()
alert_state = load_alert_state()
state_changed = False
should_notify = False
suppression_reason = None

if overall_status != "ok":
    fingerprint = failure_fingerprint()
    last_fingerprint = str(alert_state.get("last_failure_fingerprint") or "")
    last_notified_at = float(alert_state.get("last_failure_notified_at") or 0)
    cooldown_seconds = alert_cooldown_minutes * 60
    fingerprint_changed = fingerprint != last_fingerprint
    cooldown_elapsed = cooldown_seconds <= 0 or (now_ts - last_notified_at) >= cooldown_seconds
    should_notify = fingerprint_changed or cooldown_elapsed
    if should_notify:
        alert_state.update(
            {
                "last_status": "error",
                "last_failure_fingerprint": fingerprint,
                "last_failure_notified_at": now_ts,
                "last_failure_artifact": str(artifact_path),
                "last_failure_generated_at": artifact["generated_at"],
            }
        )
        state_changed = True
    else:
        suppression_reason = (
            f"repeated failure suppressed for {alert_cooldown_minutes}m cooldown"
        )
        alert_state.update(
            {
                "last_status": "error",
                "last_failure_fingerprint": fingerprint,
                "last_failure_artifact": str(artifact_path),
                "last_failure_generated_at": artifact["generated_at"],
            }
        )
        state_changed = True
elif notify_on_success:
    prior_status = str(alert_state.get("last_status") or "")
    should_notify = prior_status == "error"
    alert_state.update(
        {
            "last_status": "ok",
            "last_success_artifact": str(artifact_path),
            "last_success_generated_at": artifact["generated_at"],
        }
    )
    state_changed = True
else:
    alert_state.update(
        {
            "last_status": "ok",
            "last_success_artifact": str(artifact_path),
            "last_success_generated_at": artifact["generated_at"],
        }
    )
    state_changed = True

if state_changed:
    save_alert_state(alert_state)

if suppression_reason:
    print(f"[info] {suppression_reason}")

if should_notify and alert_webhook_url:
    try:
        post_json(alert_webhook_url, {"text": alert_message})
        print("[ok] alert_webhook")
    except Exception as exc:  # noqa: BLE001
        print(f"[error] alert_webhook: {exc}")

if should_notify and alert_telegram_token and alert_telegram_chat_id:
    telegram_url = f"https://api.telegram.org/bot{alert_telegram_token}/sendMessage"
    telegram_payload = {"chat_id": alert_telegram_chat_id, "text": alert_message}
    try:
        post_json(telegram_url, telegram_payload)
        print("[ok] alert_telegram")
    except Exception as exc:  # noqa: BLE001
        print(f"[error] alert_telegram: {exc}")

if overall_status != "ok":
    raise SystemExit(1)
PY
