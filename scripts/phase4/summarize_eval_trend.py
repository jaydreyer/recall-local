#!/usr/bin/env python3
"""Summarize Phase 4 soak eval artifacts into trend JSON + Markdown."""

from __future__ import annotations

import argparse
import glob
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class RunSummary:
    suite: str
    iteration: int
    command_exit: int
    status: str
    passed: int
    total: int
    case_pass_rate: float
    latency_ms: int | None
    run_id: str | None
    artifact_path: str | None
    result_json: str
    stderr_log: str
    failure_reasons: list[str]
    error: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize soak eval runs into trend artifacts.")
    parser.add_argument(
        "--meta-glob",
        required=True,
        help="Glob for *.meta.json files created by run_eval_soak_now.sh.",
    )
    parser.add_argument("--output-json", required=True, help="Output summary JSON path.")
    parser.add_argument("--output-markdown", required=True, help="Output summary Markdown path.")
    parser.add_argument("--min-pass-rate", type=float, default=1.0, help="Minimum average case pass-rate threshold.")
    parser.add_argument(
        "--max-avg-latency-ms",
        type=int,
        default=15000,
        help="Maximum average run latency threshold in milliseconds.",
    )
    parser.add_argument("--label", default="Phase 4A eval soak", help="Label shown in output artifacts.")
    parser.add_argument(
        "--fail-on-threshold",
        action="store_true",
        help="Exit non-zero when any threshold breach is detected.",
    )
    return parser.parse_args()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_reason(note: str) -> str:
    normalized = note.strip()
    lowered = normalized.lower()
    if lowered.startswith("execution error:"):
        return "execution_error"
    if lowered.startswith("latency "):
        return "latency_threshold_exceeded"
    if lowered.startswith("expected doc_id"):
        return "expected_doc_mismatch"
    if lowered.startswith("answer missing required grounding terms"):
        return "required_terms_missing"
    if lowered.startswith("sources did not satisfy required tags"):
        return "required_source_tags_missing"
    if lowered.startswith("semantic similarity"):
        return "semantic_similarity_below_threshold"
    if lowered.startswith("invalid citation pairs"):
        return "invalid_citation_pairs"
    if lowered.startswith("response missing"):
        return "response_shape_error"
    if lowered.startswith("expected explicit"):
        return "unanswerable_phrase_missing"
    if lowered.startswith("expected confidence_level=low"):
        return "unanswerable_confidence_invalid"
    return normalized if len(normalized) <= 120 else f"{normalized[:117]}..."


def _extract_failure_reasons(results: list[Any]) -> list[str]:
    reasons: list[str] = []
    for row in results:
        if not isinstance(row, dict):
            continue
        if bool(row.get("passed", False)):
            continue
        note_text = str(row.get("notes", "")).strip()
        if not note_text:
            reasons.append("missing_failure_note")
            continue
        split_notes = [piece.strip() for piece in note_text.split(";") if piece.strip()]
        if not split_notes:
            reasons.append("missing_failure_note")
            continue
        reasons.extend(_normalize_reason(piece) for piece in split_notes)
    return reasons


def _load_run_summary(meta_path: Path) -> RunSummary:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    suite = str(meta.get("suite", "unknown")).strip() or "unknown"
    iteration = _safe_int(meta.get("iteration"), 0)
    command_exit = _safe_int(meta.get("command_exit"), 1)
    result_json = str(meta.get("result_json", "")).strip()
    stderr_log = str(meta.get("stderr_log", "")).strip()

    if not result_json:
        return RunSummary(
            suite=suite,
            iteration=iteration,
            command_exit=command_exit,
            status="error",
            passed=0,
            total=0,
            case_pass_rate=0.0,
            latency_ms=None,
            run_id=None,
            artifact_path=None,
            result_json=result_json,
            stderr_log=stderr_log,
            failure_reasons=["missing_result_json_path"],
            error="meta_missing_result_json",
        )

    result_path = Path(result_json)
    if not result_path.exists():
        return RunSummary(
            suite=suite,
            iteration=iteration,
            command_exit=command_exit,
            status="error",
            passed=0,
            total=0,
            case_pass_rate=0.0,
            latency_ms=None,
            run_id=None,
            artifact_path=None,
            result_json=result_json,
            stderr_log=stderr_log,
            failure_reasons=["missing_result_json_file"],
            error="result_json_missing",
        )

    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return RunSummary(
            suite=suite,
            iteration=iteration,
            command_exit=command_exit,
            status="error",
            passed=0,
            total=0,
            case_pass_rate=0.0,
            latency_ms=None,
            run_id=None,
            artifact_path=None,
            result_json=result_json,
            stderr_log=stderr_log,
            failure_reasons=["invalid_result_json"],
            error=f"result_json_invalid: {exc}",
        )

    passed = _safe_int(payload.get("passed"), 0)
    total = _safe_int(payload.get("total"), 0)
    case_pass_rate = (passed / total) if total > 0 else 0.0
    status = str(payload.get("status", "")).strip().lower() or "error"
    if status not in {"pass", "fail"}:
        status = "error"
    latency_ms_raw = payload.get("latency_ms")
    latency_ms = _safe_int(latency_ms_raw) if latency_ms_raw is not None else None
    failure_reasons = _extract_failure_reasons(payload.get("results", []))
    if status != "pass" and not failure_reasons:
        failure_reasons = ["run_failed_without_case_detail"]

    return RunSummary(
        suite=suite,
        iteration=iteration,
        command_exit=command_exit,
        status=status,
        passed=passed,
        total=total,
        case_pass_rate=case_pass_rate,
        latency_ms=latency_ms,
        run_id=str(payload.get("run_id")) if payload.get("run_id") else None,
        artifact_path=str(payload.get("artifact_path")) if payload.get("artifact_path") else None,
        result_json=result_json,
        stderr_log=stderr_log,
        failure_reasons=failure_reasons,
        error=None,
    )


def _suite_threshold_breaches(
    *,
    suite: str,
    avg_case_pass_rate: float | None,
    avg_latency_ms: float | None,
    error_run_count: int,
    min_pass_rate: float,
    max_avg_latency_ms: int,
) -> list[str]:
    breaches: list[str] = []
    if avg_case_pass_rate is None:
        breaches.append(f"{suite}:missing_case_pass_rate")
    elif avg_case_pass_rate < min_pass_rate:
        breaches.append(
            f"{suite}:avg_case_pass_rate_below_threshold:{avg_case_pass_rate:.3f}<{min_pass_rate:.3f}"
        )
    if avg_latency_ms is None:
        breaches.append(f"{suite}:missing_latency")
    elif avg_latency_ms > max_avg_latency_ms:
        breaches.append(
            f"{suite}:avg_latency_above_threshold:{avg_latency_ms:.1f}>{max_avg_latency_ms}"
        )
    if error_run_count > 0:
        breaches.append(f"{suite}:error_runs_present:{error_run_count}")
    return breaches


def _render_markdown(
    *,
    label: str,
    generated_at: str,
    min_pass_rate: float,
    max_avg_latency_ms: int,
    overall_status: str,
    threshold_breaches: list[str],
    by_suite: dict[str, Any],
) -> str:
    lines: list[str] = []
    lines.append(f"# {label}")
    lines.append("")
    lines.append(f"- Generated at (UTC): `{generated_at}`")
    lines.append(f"- Thresholds: min pass-rate `{min_pass_rate:.3f}`, max avg latency `{max_avg_latency_ms}ms`")
    lines.append(f"- Overall status: `{overall_status}`")
    lines.append("")
    lines.append("## Suite Summary")
    lines.append("")
    lines.append("| Suite | Runs | Pass runs | Fail runs | Error runs | Avg case pass-rate | Avg latency (ms) |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")

    for suite_name, suite_payload in sorted(by_suite.items()):
        avg_case_pass_rate = suite_payload.get("avg_case_pass_rate")
        avg_latency_ms = suite_payload.get("avg_latency_ms")
        lines.append(
            "| {suite} | {runs} | {pass_runs} | {fail_runs} | {error_runs} | {pass_rate} | {latency} |".format(
                suite=suite_name,
                runs=suite_payload.get("run_count", 0),
                pass_runs=suite_payload.get("pass_run_count", 0),
                fail_runs=suite_payload.get("fail_run_count", 0),
                error_runs=suite_payload.get("error_run_count", 0),
                pass_rate=(
                    f"{avg_case_pass_rate:.3f}"
                    if isinstance(avg_case_pass_rate, (int, float))
                    else "n/a"
                ),
                latency=(
                    f"{avg_latency_ms:.1f}"
                    if isinstance(avg_latency_ms, (int, float))
                    else "n/a"
                ),
            )
        )

    lines.append("")
    lines.append("## Threshold Breaches")
    lines.append("")
    if threshold_breaches:
        for breach in threshold_breaches:
            lines.append(f"- {breach}")
    else:
        lines.append("- none")

    lines.append("")
    lines.append("## Failure Histogram")
    lines.append("")
    for suite_name, suite_payload in sorted(by_suite.items()):
        lines.append(f"### {suite_name}")
        histogram = suite_payload.get("failure_reason_histogram", {})
        if not histogram:
            lines.append("- none")
        else:
            for reason, count in sorted(histogram.items(), key=lambda item: (-item[1], item[0])):
                lines.append(f"- {reason}: {count}")
        lines.append("")

    lines.append("## Run Detail")
    lines.append("")
    lines.append(
        "| Suite | Iteration | Status | Command exit | Passed | Total | Case pass-rate | Latency (ms) | Result JSON | Stderr log |"
    )
    lines.append("|---|---:|---|---:|---:|---:|---:|---:|---|---|")
    for suite_name, suite_payload in sorted(by_suite.items()):
        for run in suite_payload.get("runs", []):
            lines.append(
                "| {suite} | {iteration} | {status} | {command_exit} | {passed} | {total} | {case_pass_rate:.3f} | {latency} | {result_json} | {stderr_log} |".format(
                    suite=suite_name,
                    iteration=run["iteration"],
                    status=run["status"],
                    command_exit=run["command_exit"],
                    passed=run["passed"],
                    total=run["total"],
                    case_pass_rate=run["case_pass_rate"],
                    latency=(str(run["latency_ms"]) if run["latency_ms"] is not None else "n/a"),
                    result_json=run["result_json"],
                    stderr_log=run["stderr_log"],
                )
            )

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    if args.min_pass_rate < 0 or args.min_pass_rate > 1:
        raise SystemExit("--min-pass-rate must be within [0, 1].")
    if args.max_avg_latency_ms < 0:
        raise SystemExit("--max-avg-latency-ms must be non-negative.")

    meta_paths = sorted(Path(path_str) for path_str in glob.glob(args.meta_glob))
    if not meta_paths:
        raise SystemExit(f"No meta files matched --meta-glob: {args.meta_glob}")

    run_summaries = [_load_run_summary(path) for path in meta_paths]
    run_summaries.sort(key=lambda item: (item.suite, item.iteration, item.result_json))

    by_suite_runs: dict[str, list[RunSummary]] = defaultdict(list)
    for run in run_summaries:
        by_suite_runs[run.suite].append(run)

    by_suite: dict[str, Any] = {}
    all_breaches: list[str] = []

    for suite_name, suite_runs in sorted(by_suite_runs.items()):
        suite_failures = Counter()
        pass_runs = 0
        fail_runs = 0
        error_runs = 0
        latency_values: list[int] = []
        pass_rate_values: list[float] = []

        serialized_runs: list[dict[str, Any]] = []
        for run in suite_runs:
            if run.status == "pass":
                pass_runs += 1
            elif run.status == "fail":
                fail_runs += 1
            else:
                error_runs += 1

            if run.latency_ms is not None:
                latency_values.append(run.latency_ms)
            if run.total > 0:
                pass_rate_values.append(run.case_pass_rate)

            suite_failures.update(run.failure_reasons)
            serialized_runs.append(
                {
                    "suite": run.suite,
                    "iteration": run.iteration,
                    "command_exit": run.command_exit,
                    "status": run.status,
                    "passed": run.passed,
                    "total": run.total,
                    "case_pass_rate": round(run.case_pass_rate, 6),
                    "latency_ms": run.latency_ms,
                    "run_id": run.run_id,
                    "artifact_path": run.artifact_path,
                    "result_json": run.result_json,
                    "stderr_log": run.stderr_log,
                    "failure_reasons": run.failure_reasons,
                    "error": run.error,
                }
            )

        avg_case_pass_rate = (
            round(sum(pass_rate_values) / len(pass_rate_values), 6) if pass_rate_values else None
        )
        avg_latency_ms = round(sum(latency_values) / len(latency_values), 2) if latency_values else None
        suite_breaches = _suite_threshold_breaches(
            suite=suite_name,
            avg_case_pass_rate=avg_case_pass_rate,
            avg_latency_ms=avg_latency_ms,
            error_run_count=error_runs,
            min_pass_rate=args.min_pass_rate,
            max_avg_latency_ms=args.max_avg_latency_ms,
        )
        all_breaches.extend(suite_breaches)

        by_suite[suite_name] = {
            "run_count": len(suite_runs),
            "pass_run_count": pass_runs,
            "fail_run_count": fail_runs,
            "error_run_count": error_runs,
            "avg_case_pass_rate": avg_case_pass_rate,
            "avg_latency_ms": avg_latency_ms,
            "failure_reason_histogram": dict(sorted(suite_failures.items())),
            "threshold_breaches": suite_breaches,
            "runs": serialized_runs,
        }

    generated_at = _now_iso()
    overall_status = "pass" if not all_breaches else "fail"
    output_payload = {
        "label": args.label,
        "generated_at": generated_at,
        "thresholds": {
            "min_pass_rate": _safe_float(args.min_pass_rate),
            "max_avg_latency_ms": _safe_int(args.max_avg_latency_ms),
        },
        "status": overall_status,
        "threshold_breaches": all_breaches,
        "by_suite": by_suite,
        "meta_files": [str(path) for path in meta_paths],
    }

    output_json_path = Path(args.output_json)
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(json.dumps(output_payload, indent=2) + "\n", encoding="utf-8")

    output_markdown_path = Path(args.output_markdown)
    output_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    output_markdown_path.write_text(
        _render_markdown(
            label=args.label,
            generated_at=generated_at,
            min_pass_rate=args.min_pass_rate,
            max_avg_latency_ms=args.max_avg_latency_ms,
            overall_status=overall_status,
            threshold_breaches=all_breaches,
            by_suite=by_suite,
        ),
        encoding="utf-8",
    )

    print(f"Wrote summary JSON: {output_json_path}")
    print(f"Wrote summary Markdown: {output_markdown_path}")
    print(f"Status: {overall_status}")

    if args.fail_on_threshold and overall_status != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
