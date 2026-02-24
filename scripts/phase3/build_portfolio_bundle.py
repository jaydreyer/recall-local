#!/usr/bin/env python3
"""Build a Phase 3C portfolio evidence bundle from local artifacts."""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class EvalRun:
    path: Path
    run_id: str
    status: str
    passed: int
    total: int
    latency_ms: int | None
    webhook_url: str | None


@dataclass
class BundleSelection:
    architecture_doc: Path
    phase3c_runbook: Path
    latest_rehearsal_log: Path | None
    latest_phase3b_comparison: Path | None
    latest_restore_report: Path | None
    latest_eval_pass: EvalRun | None
    latest_eval_fail: EvalRun | None
    trend_runs: list[EvalRun]


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _collect_eval_runs(eval_root: Path) -> list[EvalRun]:
    runs: list[EvalRun] = []
    for path in sorted(eval_root.rglob("*.json")):
        payload = _load_json(path)
        if payload is None:
            continue
        if "passed" not in payload or "total" not in payload:
            continue
        if "results" not in payload:
            continue

        try:
            passed = int(payload.get("passed", 0))
            total = int(payload.get("total", 0))
        except Exception:  # noqa: BLE001
            continue

        run_id = str(payload.get("run_id", ""))
        status = str(payload.get("status") or ("pass" if total > 0 and passed == total else "fail"))
        latency_raw = payload.get("latency_ms")
        latency_ms = int(latency_raw) if isinstance(latency_raw, (int, float)) else None
        webhook_url = payload.get("webhook_url")
        webhook = str(webhook_url) if isinstance(webhook_url, str) else None
        runs.append(
            EvalRun(
                path=path,
                run_id=run_id,
                status=status,
                passed=passed,
                total=total,
                latency_ms=latency_ms,
                webhook_url=webhook,
            )
        )

    runs.sort(key=lambda item: item.path.stat().st_mtime, reverse=True)
    return runs


def _latest_file(glob_pattern: str) -> Path | None:
    matches = sorted(ROOT.glob(glob_pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def _choose(runs: list[EvalRun], max_trend: int) -> BundleSelection:
    latest_pass = next((run for run in runs if run.status.lower() == "pass"), None)
    latest_fail = next((run for run in runs if run.status.lower() != "pass"), None)

    return BundleSelection(
        architecture_doc=ROOT / "docs" / "Recall_local_Architecture_Diagram.md",
        phase3c_runbook=ROOT / "docs" / "Recall_local_Phase3C_Operations_Runbook.md",
        latest_rehearsal_log=_latest_file("data/artifacts/rehearsals/*.log"),
        latest_phase3b_comparison=_latest_file("data/artifacts/evals/phase3b/*_comparison.md"),
        latest_restore_report=_latest_file("data/artifacts/backups/phase3c/**/restore_report_*.json"),
        latest_eval_pass=latest_pass,
        latest_eval_fail=latest_fail,
        trend_runs=runs[:max_trend],
    )


def _copy_if_present(src: Path | None, dest_dir: Path) -> Path | None:
    if src is None or not src.exists():
        return None
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    shutil.copy2(src, dest)
    return dest


def _format_eval_row(run: EvalRun) -> str:
    ratio = f"{run.passed}/{run.total}"
    latency = str(run.latency_ms) if run.latency_ms is not None else "n/a"
    return f"| `{run.path.name}` | `{run.status}` | `{ratio}` | `{latency}` |"


def _write_bundle_markdown(*, output_path: Path, selection: BundleSelection, copied: dict[str, Path | None]) -> None:
    lines: list[str] = []
    lines.append("# Recall.local Phase 3C Portfolio Bundle")
    lines.append("")
    lines.append(f"Generated at (UTC): `{_utc_stamp()}`")
    lines.append("")
    lines.append("## Included Evidence")
    lines.append("")

    def item(label: str, path: Path | None) -> None:
        if path is None:
            lines.append(f"- [MISSING] {label}")
        else:
            lines.append(f"- [OK] {label}: `{path}`")

    item("Architecture diagram", copied.get("architecture_doc"))
    item("Phase 3C operations runbook", copied.get("phase3c_runbook"))
    item("Latest rehearsal log", copied.get("latest_rehearsal_log"))
    item("Latest Phase 3B comparison", copied.get("latest_phase3b_comparison"))
    item("Latest restore report", copied.get("latest_restore_report"))
    item("Latest passing eval JSON", copied.get("latest_eval_pass"))
    item("Latest failing eval JSON", copied.get("latest_eval_fail"))

    lines.append("")
    lines.append("## Eval Trend Snapshot")
    lines.append("")
    if selection.trend_runs:
        lines.append("| Run file | Status | Pass/Total | Latency ms |")
        lines.append("|---|---:|---:|---:|")
        for run in selection.trend_runs:
            lines.append(_format_eval_row(run))
    else:
        lines.append("No eval run JSON files were discovered.")

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- This bundle is assembled from local checked-in artifact paths only.")
    lines.append("- Missing items indicate evidence not yet produced in this workspace or not synced from ai-lab.")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_bundle(*, output_root: Path, max_trend: int) -> Path:
    output_dir = output_root / _utc_stamp()
    evidence_dir = output_dir / "evidence"
    output_dir.mkdir(parents=True, exist_ok=True)

    eval_runs = _collect_eval_runs(ROOT / "data" / "artifacts" / "evals")
    selection = _choose(eval_runs, max_trend=max_trend)

    copied: dict[str, Path | None] = {}
    copied["architecture_doc"] = _copy_if_present(selection.architecture_doc, evidence_dir / "docs")
    copied["phase3c_runbook"] = _copy_if_present(selection.phase3c_runbook, evidence_dir / "docs")
    copied["latest_rehearsal_log"] = _copy_if_present(selection.latest_rehearsal_log, evidence_dir / "logs")
    copied["latest_phase3b_comparison"] = _copy_if_present(selection.latest_phase3b_comparison, evidence_dir / "evals")
    copied["latest_restore_report"] = _copy_if_present(selection.latest_restore_report, evidence_dir / "recovery")
    copied["latest_eval_pass"] = _copy_if_present(selection.latest_eval_pass.path if selection.latest_eval_pass else None, evidence_dir / "evals")
    copied["latest_eval_fail"] = _copy_if_present(selection.latest_eval_fail.path if selection.latest_eval_fail else None, evidence_dir / "evals")

    bundle_md = output_dir / "portfolio_bundle.md"
    _write_bundle_markdown(output_path=bundle_md, selection=selection, copied=copied)

    summary = {
        "generated_at_utc": _utc_stamp(),
        "bundle_dir": str(output_dir),
        "missing_items": [key for key, path in copied.items() if path is None],
        "trend_run_count": len(selection.trend_runs),
    }
    (output_dir / "bundle_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    return output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Phase 3C portfolio evidence bundle.")
    parser.add_argument(
        "--output-root",
        default=str(ROOT / "data" / "artifacts" / "portfolio" / "phase3c"),
        help="Root directory for generated bundle folders.",
    )
    parser.add_argument(
        "--max-trend-runs",
        type=int,
        default=12,
        help="Maximum number of eval runs to include in trend table.",
    )
    args = parser.parse_args()

    output_root = Path(args.output_root).expanduser().resolve()
    bundle_dir = build_bundle(output_root=output_root, max_trend=max(1, args.max_trend_runs))
    print(f"[OK] Portfolio bundle generated: {bundle_dir}")
    print(f"[OK] Bundle summary: {bundle_dir / 'bundle_summary.json'}")
    print(f"[OK] Bundle markdown: {bundle_dir / 'portfolio_bundle.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
