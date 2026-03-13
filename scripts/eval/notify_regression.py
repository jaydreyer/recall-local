#!/usr/bin/env python3
"""Send a regression alert for scheduled eval runs."""

from __future__ import annotations

import argparse
import json
import logging
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)
WEBHOOK_TIMEOUT_SECONDS = 10
STATUS_PASS = "pass"
LEVEL_REGRESSION = "REGRESSION"
LEVEL_OK = "OK"
EMOJI_ALERT = "ALERT"
EMOJI_INFO = "INFO"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for regression alert delivery."""
    parser = argparse.ArgumentParser(description="Send a regression alert for eval results.")
    parser.add_argument("--result-json", required=True, help="Path to JSON output from run_eval.py.")
    parser.add_argument("--command-exit", type=int, required=True, help="Exit code from run_eval.py.")
    parser.add_argument("--webhook-url", default="", help="Optional Slack/Teams compatible webhook URL.")
    parser.add_argument("--stderr-log", default="", help="Optional stderr log path from run_eval.py.")
    return parser.parse_args()


def _load_result(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Eval result is not a JSON object.")
    return payload


def _build_message(result: dict[str, Any], *, command_exit: int, stderr_path: str) -> tuple[str, bool]:
    """Build the alert text and whether it should be treated as a regression."""
    status = str(result.get("status", "unknown"))
    run_id = str(result.get("run_id", "unknown"))
    passed = result.get("passed", "?")
    total = result.get("total", "?")
    unanswerable_passed = result.get("unanswerable_passed", "?")
    unanswerable_total = result.get("unanswerable_total", "?")
    artifact_path = str(result.get("artifact_path", ""))
    webhook_url = str(result.get("webhook_url", ""))

    regression = command_exit != 0 or status != STATUS_PASS
    if regression:
        level = LEVEL_REGRESSION
        emoji = EMOJI_ALERT
    else:
        level = LEVEL_OK
        emoji = EMOJI_INFO

    lines = [
        f"[{emoji}] Recall.local scheduled eval {level}",
        f"run_id={run_id}",
        f"status={status} passed={passed}/{total}",
        f"unanswerable={unanswerable_passed}/{unanswerable_total}",
        f"command_exit={command_exit}",
    ]
    if webhook_url:
        lines.append(f"webhook={webhook_url}")
    if artifact_path:
        lines.append(f"artifact={artifact_path}")
    if regression and stderr_path:
        lines.append(f"stderr={stderr_path}")
    return "\n".join(lines), regression


def _post_webhook(*, webhook_url: str, message: str) -> None:
    """Send an alert payload to a Slack- or Teams-compatible webhook."""
    body = json.dumps({"text": message}).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=WEBHOOK_TIMEOUT_SECONDS) as response:
        if response.status >= 300:
            raise RuntimeError(f"Alert webhook returned HTTP {response.status}.")


def main() -> int:
    """Load an eval result, print the alert text, and optionally notify a webhook."""
    args = parse_args()
    result_path = Path(args.result_json)

    try:
        result = _load_result(result_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        message = (
            "[ALERT] Recall.local scheduled eval REGRESSION\n"
            f"reason=Failed to parse eval JSON: {exc}\n"
            f"result_json={result_path}\n"
            f"command_exit={args.command_exit}"
        )
        print(message)
        if args.webhook_url:
            try:
                _post_webhook(webhook_url=args.webhook_url, message=message)
            except (RuntimeError, urllib.error.URLError) as webhook_exc:
                LOGGER.warning("Webhook alert failed for %s: %s", args.webhook_url, webhook_exc)
                print(f"Webhook alert failed: {webhook_exc}")
        return 0

    message, regression = _build_message(result, command_exit=args.command_exit, stderr_path=args.stderr_log)
    print(message)

    if regression and args.webhook_url:
        try:
            _post_webhook(webhook_url=args.webhook_url, message=message)
        except urllib.error.URLError as exc:
            LOGGER.warning("Webhook alert failed for %s: %s", args.webhook_url, exc)
            print(f"Webhook alert failed: {exc}")
        except RuntimeError as exc:
            LOGGER.warning("Webhook alert failed for %s: %s", args.webhook_url, exc)
            print(f"Webhook alert failed: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
