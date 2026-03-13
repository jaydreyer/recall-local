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

mkdir -p "$ARTIFACT_DIR"

python3 - "$BRIDGE_BASE_URL" "$DASHBOARD_URL" "$CHAT_UI_URL" "$ARTIFACT_DIR" "$API_KEY" "$ALERT_WEBHOOK_URL" "$ALERT_TELEGRAM_TOKEN" "$ALERT_TELEGRAM_CHAT_ID" "$NOTIFY_ON_SUCCESS" <<'PY'
import json
import pathlib
import sys
import urllib.request
from datetime import datetime, timezone


bridge_base = sys.argv[1].rstrip("/")
dashboard_url = sys.argv[2].rstrip("/")
chat_ui_url = sys.argv[3].rstrip("/")
artifact_dir = pathlib.Path(sys.argv[4])
api_key = sys.argv[5].strip()
alert_webhook_url = sys.argv[6].strip()
alert_telegram_token = sys.argv[7].strip()
alert_telegram_chat_id = sys.argv[8].strip()
notify_on_success = sys.argv[9].strip().lower() in {"1", "true", "yes", "on"}

timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
artifact_path = artifact_dir / f"{timestamp}_ops_observability_check.json"


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
    attempts = (
        {"include_gaps": True, "timeout": 60, "label": "full"},
        {"include_gaps": False, "timeout": 30, "label": "core"},
    )
    failures: list[str] = []

    for index, attempt in enumerate(attempts):
        include_gaps = attempt["include_gaps"]
        url = build_url(endpoint, include_gaps=include_gaps)
        try:
            payload = fetch_json(url, timeout=attempt["timeout"])
            body = payload["body"]
            if str(body.get("status") or "").lower() != "ok":
                raise RuntimeError(f"dashboard-checks status={body.get('status')!r}")
            if int((body.get("jobs") or {}).get("count") or 0) <= 0:
                raise RuntimeError("dashboard-checks reported no jobs")
            if int((body.get("companies") or {}).get("count") or 0) <= 0:
                raise RuntimeError("dashboard-checks reported no companies")
            gaps = body.get("gaps") or {}
            if include_gaps and gaps and str(gaps.get("status") or "").lower() != "ok":
                raise RuntimeError(f"dashboard-checks gaps status={gaps.get('status')!r}")
            result = {"endpoint": url, **payload, "include_gaps": include_gaps}
            if index > 0:
                result["fallback_used"] = True
                result["fallback_reason"] = failures[-1] if failures else "dashboard-checks retry"
            return result
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{attempt['label']} attempt failed: {exc}")

    raise RuntimeError("; ".join(failures))


checks.append(run_check("dashboard_checks", dashboard_check))


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


alert_message = build_alert_message()
should_notify = overall_status != "ok" or notify_on_success
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
