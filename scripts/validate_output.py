#!/usr/bin/env python3
"""Output validation utilities for Recall.local workflow responses."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from typing import Any

JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]
    parsed_response: dict[str, Any] | None


def validate_rag_output(
    raw_text: str,
    *,
    valid_citation_pairs: set[tuple[str, str]],
    require_confidence: bool = True,
    require_assumptions: bool = True,
) -> ValidationResult:
    errors: list[str] = []

    try:
        parsed = parse_json_response(raw_text)
    except ValueError as exc:
        return ValidationResult(valid=False, errors=[str(exc)], parsed_response=None)

    answer = parsed.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        errors.append("Field 'answer' must be a non-empty string.")

    citations_raw = parsed.get("citations")
    if not isinstance(citations_raw, list) or not citations_raw:
        errors.append("Field 'citations' must be a non-empty array.")
        citations_raw = []

    normalized_citations: list[dict[str, str]] = []
    for index, citation in enumerate(citations_raw):
        if not isinstance(citation, dict):
            errors.append(f"citations[{index}] must be an object.")
            continue

        doc_id = str(citation.get("doc_id", "")).strip()
        chunk_id = str(citation.get("chunk_id", "")).strip()
        if not doc_id or not chunk_id:
            errors.append(f"citations[{index}] must include non-empty 'doc_id' and 'chunk_id'.")
            continue

        if valid_citation_pairs and (doc_id, chunk_id) not in valid_citation_pairs:
            errors.append(
                f"citations[{index}] references unknown pair ({doc_id}, {chunk_id}) outside retrieved context."
            )
            continue

        normalized_citations.append({"doc_id": doc_id, "chunk_id": chunk_id})

    if require_confidence:
        confidence_level = parsed.get("confidence_level")
        if not isinstance(confidence_level, str) or not confidence_level.strip():
            errors.append("Field 'confidence_level' must be a non-empty string.")

    if require_assumptions:
        assumptions = parsed.get("assumptions")
        if not isinstance(assumptions, list):
            errors.append("Field 'assumptions' must be an array of strings.")
        elif any(not isinstance(item, str) for item in assumptions):
            errors.append("Field 'assumptions' must contain only strings.")

    parsed["citations"] = _dedupe_citations(normalized_citations)
    return ValidationResult(valid=not errors, errors=errors, parsed_response=parsed)


def parse_json_response(raw_text: str) -> dict[str, Any]:
    candidate = raw_text.strip()
    if not candidate:
        raise ValueError("Model response was empty.")

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        parsed = _parse_relaxed_json(candidate)

    if not isinstance(parsed, dict):
        raise ValueError("Model response JSON must be an object.")
    return parsed


def _dedupe_citations(citations: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for citation in citations:
        key = (citation["doc_id"], citation["chunk_id"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(citation)
    return deduped


def _parse_relaxed_json(candidate: str) -> Any:
    fence_match = JSON_BLOCK_RE.search(candidate)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    first_brace = candidate.find("{")
    last_brace = candidate.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(candidate[first_brace : last_brace + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(f"Model response is not valid JSON: {exc}") from exc

    raise ValueError("Model response is not valid JSON.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a RAG response JSON payload from stdin or argument.")
    parser.add_argument("--response", default=None, help="Raw response string. If omitted, stdin is used.")
    parser.add_argument(
        "--allowed-citations-json",
        default="[]",
        help="JSON array of [doc_id, chunk_id] pairs allowed in citations.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw = args.response if args.response is not None else sys.stdin.read()

    try:
        allowed_raw = json.loads(args.allowed_citations_json)
    except json.JSONDecodeError as exc:
        print(f"Invalid --allowed-citations-json: {exc}", file=sys.stderr)
        return 2

    pairs: set[tuple[str, str]] = set()
    if isinstance(allowed_raw, list):
        for item in allowed_raw:
            if isinstance(item, list) and len(item) == 2:
                pairs.add((str(item[0]), str(item[1])))

    result = validate_rag_output(raw, valid_citation_pairs=pairs)
    print(json.dumps(asdict(result), indent=2))
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
