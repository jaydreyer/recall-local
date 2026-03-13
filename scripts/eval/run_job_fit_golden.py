#!/usr/bin/env python3
"""Run versioned golden-set checks for Phase 6 job-fit evaluation quality."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase6 import job_evaluator

DEFAULT_CASES_FILE = ROOT / "scripts" / "eval" / "golden_sets" / "job_fit_golden_v1.json"
DEFAULT_ARTIFACT_DIR = ROOT / "data" / "artifacts" / "evals" / "job-fit-golden"


@dataclass
class GoldenCase:
    case_id: str
    category: str
    title: str
    company: str
    location: str
    url: str
    description: str
    resume_text: str
    expected_score_min: int
    expected_score_max: int
    required_matching_skills: list[str]
    required_gap_terms: list[str]
    forbidden_gap_terms: list[str]
    forbidden_matching_skills: list[str]


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv(ROOT / "docker" / ".env")
    load_dotenv(ROOT / "docker" / ".env.example")


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def load_cases(path: Path) -> list[GoldenCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Golden cases file must be a JSON array.")

    cases: list[GoldenCase] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"Golden case at index {index} must be an object.")
        case_id = str(item.get("case_id") or f"golden-{index + 1:02d}").strip()
        title = str(item.get("title") or "").strip()
        company = str(item.get("company") or "").strip()
        description = str(item.get("description") or "").strip()
        resume_text = str(item.get("resume_text") or "").strip()
        if not title or not company or not description or not resume_text:
            raise ValueError(f"Golden case {case_id} is missing required title/company/description/resume_text.")
        score_min = int(item.get("expected_score_min", 0))
        score_max = int(item.get("expected_score_max", 100))
        if score_min > score_max:
            raise ValueError(f"Golden case {case_id} has invalid score range.")

        cases.append(
            GoldenCase(
                case_id=case_id,
                category=str(item.get("category") or "general").strip() or "general",
                title=title,
                company=company,
                location=str(item.get("location") or "Unknown").strip() or "Unknown",
                url=str(item.get("url") or "").strip(),
                description=description,
                resume_text=resume_text,
                expected_score_min=score_min,
                expected_score_max=score_max,
                required_matching_skills=_normalize_string_list(item.get("required_matching_skills")),
                required_gap_terms=_normalize_string_list(item.get("required_gap_terms")),
                forbidden_gap_terms=_normalize_string_list(item.get("forbidden_gap_terms")),
                forbidden_matching_skills=_normalize_string_list(item.get("forbidden_matching_skills")),
            )
        )
    return cases


def _contains_all_terms(values: list[str], terms: list[str]) -> tuple[bool, list[str]]:
    missing = [
        term
        for term in terms
        if not any(job_evaluator._signals_overlap(value, term) for value in values)  # noqa: SLF001
    ]
    return (len(missing) == 0, missing)


def _contains_any_forbidden(values: list[str], terms: list[str]) -> list[str]:
    return [
        term
        for term in terms
        if any(job_evaluator._signals_overlap(value, term) for value in values)  # noqa: SLF001
    ]


def evaluate_case(case: GoldenCase, *, settings: dict[str, Any]) -> dict[str, Any]:
    prompt = job_evaluator._build_evaluation_prompt(  # noqa: SLF001
        job={
            "title": case.title,
            "company": case.company,
            "location": case.location,
            "url": case.url,
            "description": case.description,
        },
        resume_text=case.resume_text,
    )

    started = time.perf_counter()
    model_mode = str(settings.get("evaluation_model") or "local").strip().lower()
    if model_mode == "cloud":
        raw = job_evaluator._call_cloud(prompt=prompt, settings=settings)  # noqa: SLF001
    else:
        raw = job_evaluator._call_ollama(prompt=prompt, settings=settings)  # noqa: SLF001
    parsed = job_evaluator.parse_evaluation(raw)
    parsed = job_evaluator._ground_evaluation_to_context(  # noqa: SLF001
        job={
            "title": case.title,
            "company": case.company,
            "location": case.location,
            "url": case.url,
            "description": case.description,
        },
        resume_text=case.resume_text,
        evaluation=parsed,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)

    matching_skill_names = [str(item.get("skill") or "") for item in parsed.get("matching_skills") or []]
    gap_names = [str(item.get("gap") or "") for item in parsed.get("gaps") or []]

    score = int(parsed.get("fit_score", -1))
    score_ok = case.expected_score_min <= score <= case.expected_score_max
    required_matches_ok, missing_matches = _contains_all_terms(matching_skill_names, case.required_matching_skills)
    required_gaps_ok, missing_gaps = _contains_all_terms(gap_names, case.required_gap_terms)
    forbidden_gap_hits = _contains_any_forbidden(gap_names, case.forbidden_gap_terms)
    forbidden_match_hits = _contains_any_forbidden(matching_skill_names, case.forbidden_matching_skills)

    passed = score_ok and required_matches_ok and required_gaps_ok and not forbidden_gap_hits and not forbidden_match_hits
    notes: list[str] = []
    if not score_ok:
        notes.append(f"score {score} outside expected range {case.expected_score_min}-{case.expected_score_max}")
    if missing_matches:
        notes.append(f"missing matching skill terms: {', '.join(missing_matches)}")
    if missing_gaps:
        notes.append(f"missing gap terms: {', '.join(missing_gaps)}")
    if forbidden_gap_hits:
        notes.append(f"forbidden gap terms present: {', '.join(forbidden_gap_hits)}")
    if forbidden_match_hits:
        notes.append(f"forbidden matching skill terms present: {', '.join(forbidden_match_hits)}")

    return {
        "case_id": case.case_id,
        "category": case.category,
        "passed": passed,
        "latency_ms": latency_ms,
        "notes": notes,
        "score": score,
        "expected_score_range": [case.expected_score_min, case.expected_score_max],
        "matching_skills": matching_skill_names,
        "gaps": gap_names,
        "evaluation": parsed,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Phase 6 job-fit golden evaluation cases.")
    parser.add_argument("--cases-file", default=str(DEFAULT_CASES_FILE), help="Path to the job-fit golden set JSON file.")
    parser.add_argument("--model", choices=["local", "cloud"], default="local", help="Evaluation backend to use.")
    parser.add_argument("--local-model", default=None, help="Optional Ollama model override.")
    parser.add_argument("--cloud-provider", default=None, help="Optional cloud provider override.")
    parser.add_argument("--cloud-model", default=None, help="Optional cloud model override.")
    parser.add_argument("--max-cases", type=int, default=None, help="Run only the first N cases.")
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR), help="Directory for JSON artifacts.")
    parser.add_argument("--dry-run", action="store_true", help="Skip artifact write.")
    return parser.parse_args()


def main() -> int:
    _load_dotenv_if_available()
    args = parse_args()
    cases = load_cases(Path(args.cases_file))
    if args.max_cases:
        cases = cases[: max(args.max_cases, 0)]
    if not cases:
        print("No golden cases to run.", file=sys.stderr)
        return 1

    settings = job_evaluator._load_runtime_settings(  # noqa: SLF001
        {
            "evaluation_model": args.model,
            "local_model": args.local_model,
            "cloud_provider": args.cloud_provider,
            "cloud_model": args.cloud_model,
        }
    )

    results = [evaluate_case(case, settings=settings) for case in cases]
    passed = sum(1 for result in results if result["passed"])
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "workflow": "workflow_06c_job_fit_golden",
        "cases_file": str(Path(args.cases_file).resolve()),
        "model": settings.get("evaluation_model"),
        "local_model": settings.get("local_model"),
        "cloud_provider": settings.get("cloud_provider"),
        "cloud_model": settings.get("cloud_model"),
        "total_cases": len(results),
        "passed_cases": passed,
        "failed_cases": len(results) - passed,
        "pass_rate": round(passed / len(results), 3),
        "results": results,
    }

    artifact_path: Path | None = None
    if not args.dry_run:
        artifact_dir = Path(args.artifact_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_job_fit_golden.json"
        artifact_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        summary["artifact_path"] = str(artifact_path)

    print(json.dumps(summary, indent=2))
    return 0 if passed == len(results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
