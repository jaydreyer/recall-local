#!/usr/bin/env python3
"""Bake off local/cloud job-fit evaluator candidates on golden and real jobs."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.eval import run_job_fit_golden  # noqa: E402
from scripts.phase6 import job_evaluator  # noqa: E402

DEFAULT_ARTIFACT_DIR = ROOT / "data" / "artifacts" / "evals" / "job-fit-bakeoff"


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / "docker" / ".env")
    load_dotenv(ROOT / "docker" / ".env.example")


def _settings_for_candidate(candidate: str) -> dict[str, Any]:
    if candidate.startswith("local:"):
        return job_evaluator._load_runtime_settings(  # noqa: SLF001
            {"evaluation_model": "local", "local_model": candidate.removeprefix("local:")}
        )
    if ":" not in candidate:
        raise ValueError("Candidates must use provider:model, for example openai:gpt-4.1-mini")
    provider, model = candidate.split(":", 1)
    return job_evaluator._load_runtime_settings(  # noqa: SLF001
        {
            "evaluation_model": "cloud",
            "cloud_provider": provider,
            "cloud_model": model,
            "max_jobs_per_run": 10,
            "max_cloud_cost_usd": 1.0,
        }
    )


def _evaluate_real_job(job_id: str, *, settings: dict[str, Any]) -> dict[str, Any]:
    job = job_evaluator._load_job_payload(job_id)  # noqa: SLF001
    if job is None:
        return {"job_id": job_id, "status": "error", "error": f"Job not found: {job_id}"}
    resume_text = job_evaluator._load_resume_text()  # noqa: SLF001
    prompt = job_evaluator._build_evaluation_prompt(job=job, resume_text=resume_text)  # noqa: SLF001
    started = time.perf_counter()
    try:
        raw = (
            job_evaluator._call_cloud(prompt=prompt, settings=settings)  # noqa: SLF001
            if settings.get("evaluation_model") == "cloud"
            else job_evaluator._call_ollama(prompt=prompt, settings=settings)  # noqa: SLF001
        )
        parsed = job_evaluator.parse_evaluation(raw)
        parsed = job_evaluator._ground_evaluation_to_context(job=job, resume_text=resume_text, evaluation=parsed)  # noqa: SLF001
    except Exception as exc:  # noqa: BLE001
        return {
            "job_id": job_id,
            "status": "error",
            "error": str(exc),
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }
    return {
        "job_id": job_id,
        "status": "completed",
        "title": str(job.get("title") or ""),
        "company": str(job.get("company") or ""),
        "fit_score": parsed.get("fit_score"),
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "matching_skills": [item.get("skill") for item in parsed.get("matching_skills", [])],
        "gaps": [item.get("gap") for item in parsed.get("gaps", [])],
        "evaluation": parsed,
    }


def run_candidate(
    candidate: str, *, cases_file: Path, max_cases: int | None, real_job_ids: list[str]
) -> dict[str, Any]:
    settings = _settings_for_candidate(candidate)
    cases = run_job_fit_golden.load_cases(cases_file)
    if max_cases:
        cases = cases[: max(max_cases, 0)]

    golden_results = [run_job_fit_golden.evaluate_case(case, settings=settings) for case in cases]
    real_job_results = [_evaluate_real_job(job_id, settings=settings) for job_id in real_job_ids]
    golden_passed = sum(1 for result in golden_results if result["passed"])
    real_completed = sum(1 for result in real_job_results if result["status"] == "completed")
    latencies = [
        int(result["latency_ms"])
        for result in [*golden_results, *real_job_results]
        if isinstance(result.get("latency_ms"), int)
    ]
    return {
        "candidate": candidate,
        "settings": {
            "evaluation_model": settings.get("evaluation_model"),
            "local_model": settings.get("local_model"),
            "cloud_provider": settings.get("cloud_provider"),
            "cloud_model": settings.get("cloud_model"),
        },
        "golden": {
            "total": len(golden_results),
            "passed": golden_passed,
            "pass_rate": round(golden_passed / len(golden_results), 3) if golden_results else 0.0,
            "results": golden_results,
        },
        "real_jobs": {
            "total": len(real_job_results),
            "completed": real_completed,
            "valid_json_rate": round(real_completed / len(real_job_results), 3) if real_job_results else None,
            "results": real_job_results,
        },
        "latency_ms": {
            "min": min(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
            "avg": round(sum(latencies) / len(latencies), 1) if latencies else None,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 6 job-fit evaluator bakeoff.")
    parser.add_argument("--candidate", action="append", required=True, help="provider:model or local:model candidate.")
    parser.add_argument("--cases-file", default=str(run_job_fit_golden.DEFAULT_CASES_FILE), help="Golden cases JSON.")
    parser.add_argument("--max-cases", type=int, default=None, help="Limit synthetic golden cases.")
    parser.add_argument("--real-job-id", action="append", default=[], help="Real Qdrant job id/doc id to calibrate.")
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR), help="Directory for JSON artifacts.")
    parser.add_argument("--dry-run", action="store_true", help="Print summary only; do not write an artifact.")
    return parser.parse_args()


def main() -> int:
    _load_dotenv_if_available()
    args = parse_args()
    started = time.perf_counter()
    results = [
        run_candidate(
            candidate,
            cases_file=Path(args.cases_file),
            max_cases=args.max_cases,
            real_job_ids=args.real_job_id,
        )
        for candidate in args.candidate
    ]
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cases_file": str(Path(args.cases_file).resolve()),
        "real_job_ids": args.real_job_id,
        "latency_ms": int((time.perf_counter() - started) * 1000),
        "results": results,
    }
    if not args.dry_run:
        artifact_dir = Path(args.artifact_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_job_fit_bakeoff.json"
        artifact_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        summary["artifact_path"] = str(artifact_path)
    print(json.dumps(summary, indent=2))
    failed_candidates = [result for result in results if result["golden"]["passed"] < result["golden"]["total"]]
    return 2 if failed_candidates else 0


if __name__ == "__main__":
    raise SystemExit(main())
