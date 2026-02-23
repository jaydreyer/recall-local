#!/usr/bin/env python3
"""HTTP bridge for Recall workflows when n8n Execute Command is unavailable."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase1.channel_adapters import normalize_payload  # noqa: E402
from scripts.phase1.ingest_from_payload import payload_to_requests  # noqa: E402
from scripts.phase1.ingestion_pipeline import ingest_request  # noqa: E402
from scripts.phase1.rag_query import run_rag_query  # noqa: E402


class IngestBridgeHandler(BaseHTTPRequestHandler):
    server_version = "RecallIngestBridge/1.0"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/healthz", "/health"}:
            self._send_json(200, {"status": "ok"})
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path.startswith("/ingest/"):
            self._handle_ingest_request(parsed)
            return

        if parsed.path in {"/query/rag", "/rag/query"}:
            self._handle_rag_query_request(parsed)
            return

        self._send_json(404, {"error": "Unknown path"})

    def _handle_ingest_request(self, parsed) -> None:
        prefix = "/ingest/"
        channel = parsed.path[len(prefix):].strip().lower()
        if channel not in {"webhook", "ios-share", "gmail-forward"}:
            self._send_json(400, {"error": f"Unsupported ingest channel: {channel}"})
            return

        try:
            payload = self._read_json_body()
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
            return

        query = parse_qs(parsed.query)
        dry_run = _query_bool(query.get("dry_run"))

        try:
            unified = normalize_payload(payload, channel=channel)
            requests = payload_to_requests(unified)
        except Exception as exc:  # noqa: BLE001
            self._send_json(400, {"error": f"Invalid payload: {exc}"})
            return

        results = []
        errors = []
        for index, request in enumerate(requests):
            try:
                result = ingest_request(request, dry_run=dry_run)
                results.append(asdict(result))
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    {
                        "request_index": index,
                        "source_type": request.source_type,
                        "error": str(exc),
                    }
                )

        response = {
            "workflow": "workflow_01_ingestion",
            "channel": channel,
            "normalized_payload": unified,
            "ingested": results,
            "errors": errors,
            "dry_run": dry_run,
        }
        self._send_json(200 if not errors else 207, response)

    def _handle_rag_query_request(self, parsed) -> None:
        try:
            payload = self._read_json_body()
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
            return

        query = str(payload.get("query", "")).strip()
        if not query:
            self._send_json(400, {"error": "Missing required field: query"})
            return

        query_args = parse_qs(parsed.query)
        dry_run = _query_bool(query_args.get("dry_run"))

        top_k = payload.get("top_k")
        min_score = payload.get("min_score")
        max_retries = payload.get("max_retries")
        try:
            top_k_value = int(top_k) if top_k is not None else None
            min_score_value = float(min_score) if min_score is not None else None
            max_retries_value = int(max_retries) if max_retries is not None else None
        except (TypeError, ValueError) as exc:
            self._send_json(400, {"error": f"Invalid RAG options: {exc}"})
            return

        try:
            result = run_rag_query(
                query,
                top_k=top_k_value,
                min_score=min_score_value,
                max_retries=max_retries_value,
                dry_run=dry_run,
            )
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"error": f"Workflow 02 failed: {exc}"})
            return

        self._send_json(
            200,
            {
                "workflow": "workflow_02_rag_query",
                "dry_run": dry_run,
                "result": result,
            },
        )

    def _read_json_body(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0").strip()
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("Invalid Content-Length header.") from exc

        body = self.rfile.read(length) if length > 0 else b""
        if not body:
            return {}

        try:
            parsed = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Request body is not valid JSON: {exc}") from exc

        if not isinstance(parsed, dict):
            raise ValueError("JSON body must be an object.")
        return parsed

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _query_bool(values: list[str] | None) -> bool:
    if not values:
        return False
    value = values[0].strip().lower()
    return value in {"1", "true", "yes", "on"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Recall ingestion HTTP bridge.")
    parser.add_argument("--host", default="0.0.0.0", help="Host/interface to bind.")
    parser.add_argument("--port", type=int, default=8090, help="Port to bind.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), IngestBridgeHandler)
    print(f"Recall ingestion bridge listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
