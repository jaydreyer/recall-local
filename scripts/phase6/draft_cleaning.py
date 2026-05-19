#!/usr/bin/env python3
"""Cleanup helpers for generated job-application artifacts."""

from __future__ import annotations

import json
import re
from typing import Any

TEXT_KEYS = (
    "text",
    "content",
    "draft",
    "summary",
    "bullets",
    "note",
    "brief",
    "talking_points",
    "talkingPoints",
)


def unwrap_generated_text(value: Any) -> str:
    """Extract prose when a model returns a JSON-like wrapper despite plain-text instructions."""
    if isinstance(value, list):
        parts = [unwrap_generated_text(item) for item in value]
        return "\n".join(part for part in parts if part.strip()).strip()
    if isinstance(value, dict):
        for key in TEXT_KEYS:
            if key in value:
                unwrapped = unwrap_generated_text(value.get(key))
                if unwrapped.strip():
                    return unwrapped
        parts = [unwrap_generated_text(item) for item in value.values()]
        return "\n".join(part for part in parts if part.strip()).strip()

    text = str(value or "").strip()
    if not text:
        return ""
    text = _strip_code_fence(text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        loose_text = _unwrap_loose_object_text(text)
        return loose_text or text

    unwrapped = unwrap_generated_text(parsed)
    return unwrapped or text


def _strip_code_fence(text: str) -> str:
    match = re.fullmatch(r"```(?:json|markdown|md|text)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else text


def _unwrap_loose_object_text(text: str) -> str:
    stripped = text.strip()
    if not (stripped.startswith("{") or stripped.startswith("[")):
        return ""

    candidates: list[str] = []
    for match in re.finditer(r'"((?:\\.|[^"\\])*)"', stripped, flags=re.DOTALL):
        try:
            candidate = json.loads(f'"{match.group(1)}"')
        except json.JSONDecodeError:
            candidate = match.group(1)
        candidate = str(candidate).strip()
        if "\n-" in candidate or candidate.startswith("- ") or len(candidate.split()) >= 8:
            candidates.append(candidate)
    return "\n".join(candidates).strip()
