#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BRIDGE_BASE_URL="${1:-http://localhost:8090}"
DASHBOARD_URL="${2:-http://localhost:3001}"
CHAT_UI_URL="${3:-http://localhost:8170}"
API_KEY="${RECALL_API_KEY:-}"
ARTIFACT_DIR="$ROOT_DIR/data/artifacts/observability"

mkdir -p "$ARTIFACT_DIR"

python3 - "$BRIDGE_BASE_URL" "$DASHBOARD_URL" "$CHAT_UI_URL" "$ARTIFACT_DIR" "$API_KEY" <<'PY'
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


def fetch_text(url, *, timeout=30):
    request = urllib.request.Request(url, headers={"Accept": "text/html"}, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(4096).decode("utf-8", errors="replace")
        return {
            "status_code": response.status,
            "headers": dict(response.headers.items()),
            "body_preview": body,
        }


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
    payload = fetch_json(f"{bridge_base}/v1/dashboard-checks", timeout=60)
    body = payload["body"]
    if str(body.get("status") or "").lower() != "ok":
        raise RuntimeError(f"dashboard-checks status={body.get('status')!r}")
    if int((body.get("jobs") or {}).get("count") or 0) <= 0:
        raise RuntimeError("dashboard-checks reported no jobs")
    if int((body.get("companies") or {}).get("count") or 0) <= 0:
        raise RuntimeError("dashboard-checks reported no companies")
    gaps = body.get("gaps") or {}
    if gaps and str(gaps.get("status") or "").lower() != "ok":
        raise RuntimeError(f"dashboard-checks gaps status={gaps.get('status')!r}")
    return {"endpoint": f"{bridge_base}/v1/dashboard-checks", **payload}


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

if overall_status != "ok":
    raise SystemExit(1)
PY
