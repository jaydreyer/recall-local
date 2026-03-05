#!/usr/bin/env python3
"""Extract job metadata from ingested job-page content."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any
from urllib.parse import urlparse

import httpx

JOB_URL_PATTERNS = [
    re.compile(r"linkedin\.com/jobs", re.IGNORECASE),
    re.compile(r"indeed\.com/viewjob", re.IGNORECASE),
    re.compile(r"lever\.co", re.IGNORECASE),
    re.compile(r"greenhouse\.io", re.IGNORECASE),
    re.compile(r"boards\.greenhouse\.io", re.IGNORECASE),
    re.compile(r"jobs\.ashbyhq\.com", re.IGNORECASE),
    re.compile(r"wellfound\.com/jobs", re.IGNORECASE),
    re.compile(r"workday\.com", re.IGNORECASE),
    re.compile(r"/careers?/", re.IGNORECASE),
    re.compile(r"/jobs?/", re.IGNORECASE),
]

_SEVERITY_DEFAULT = "moderate"
ALLOWED_LOCATION_TYPES = {"remote", "hybrid", "onsite"}
ALLOWED_JOB_SOURCES = {
    "linkedin",
    "indeed",
    "greenhouse",
    "lever",
    "ashby",
    "wellfound",
    "workday",
    "career_page",
    "chrome_extension",
    "jobspy",
    "adzuna",
    "serpapi",
    "unknown",
}


def looks_like_job_url(url: str) -> bool:
    text = str(url or "").strip()
    if not text:
        return False
    return any(pattern.search(text) for pattern in JOB_URL_PATTERNS)


def infer_source_from_url(url: str) -> str:
    host = urlparse(str(url or "").strip()).netloc.lower()
    if "linkedin.com" in host:
        return "linkedin"
    if "indeed.com" in host:
        return "indeed"
    if "greenhouse.io" in host:
        return "greenhouse"
    if "lever.co" in host:
        return "lever"
    if "ashbyhq.com" in host:
        return "ashby"
    if "wellfound.com" in host:
        return "wellfound"
    if "workday" in host:
        return "workday"
    return "career_page"


def extract_job_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    url = str(payload.get("url") or "").strip()
    source = _normalize_source(str(payload.get("source") or ""), url=url)
    input_title = str(payload.get("title") or "").strip()
    input_company = str(payload.get("company") or "").strip()
    input_location = str(payload.get("location") or "").strip()

    content = _coerce_content(payload)
    llm_data: dict[str, Any] = {}
    if content and len(content) >= 120:
        try:
            llm_data = _extract_with_llm(url=url, content=content)
        except Exception:
            llm_data = {}

    title = _best_text(llm_data.get("title"), input_title)
    company = _best_text(llm_data.get("company"), input_company)
    location = _best_text(llm_data.get("location"), input_location)
    if not title and input_title:
        title = input_title

    if not company and title:
        company = _infer_company_from_title(title)
    if not location:
        location = "Remote" if "remote" in content.lower() else "Unknown"

    description = _best_text(llm_data.get("description"), content)
    if len(description) > 12000:
        description = description[:12000]

    location_type = _normalize_location_type(
        llm_data.get("location_type"),
        location=location,
        description=description,
    )
    salary_min = _coerce_salary(llm_data.get("salary_min"))
    salary_max = _coerce_salary(llm_data.get("salary_max"))

    return {
        "is_job_url": looks_like_job_url(url),
        "source": source or "unknown",
        "url": url or None,
        "title": title or None,
        "company": company or None,
        "location": location or None,
        "location_type": location_type or None,
        "description": description,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "_quality": {
            "used_llm": bool(llm_data),
            "content_chars": len(content),
            "default_severity": _SEVERITY_DEFAULT,
        },
    }


def _normalize_source(raw_source: str, *, url: str) -> str:
    source = str(raw_source or "").strip().lower()
    if source in ALLOWED_JOB_SOURCES:
        return source
    inferred = infer_source_from_url(url)
    if inferred in ALLOWED_JOB_SOURCES:
        return inferred
    return "career_page"


def _normalize_location_type(raw_location_type: Any, *, location: str, description: str) -> str:
    candidate = str(raw_location_type or "").strip().lower()
    if candidate in ALLOWED_LOCATION_TYPES:
        return candidate
    inferred = _infer_location_type(location, description)
    if inferred in ALLOWED_LOCATION_TYPES:
        return inferred
    return "onsite"


def _coerce_content(payload: dict[str, Any]) -> str:
    for key in ("content", "text", "description", "body"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    chunks = payload.get("chunks")
    if isinstance(chunks, list):
        parts: list[str] = []
        for item in chunks:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
            elif isinstance(item, dict):
                text = str(item.get("text") or item.get("chunk_text") or "").strip()
                if text:
                    parts.append(text)
        joined = "\n".join(parts).strip()
        if joined:
            return joined
    return ""


def _extract_with_llm(*, url: str, content: str) -> dict[str, Any]:
    prompt = _build_extraction_prompt(url=url, content=content)
    raw = _call_ollama(prompt)
    parsed = _parse_json_object(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Metadata extraction returned non-object JSON.")
    return parsed


def _build_extraction_prompt(*, url: str, content: str) -> str:
    trimmed = content.strip()
    if len(trimmed) > 14000:
        trimmed = trimmed[:14000]

    return (
        "Extract job posting metadata from this content. "
        "Return ONLY valid JSON, with no markdown and no extra keys.\n\n"
        "JSON schema:\n"
        "{\n"
        '  "title": "<job title>",\n'
        '  "company": "<company name>",\n'
        '  "location": "<location or Remote>",\n'
        '  "location_type": "remote|hybrid|onsite",\n'
        '  "description": "<concise but complete role description>",\n'
        '  "salary_min": <number or null>,\n'
        '  "salary_max": <number or null>\n'
        "}\n\n"
        f"Source URL: {url or 'unknown'}\n\n"
        "Job content:\n"
        f"{trimmed}"
    )


def _call_ollama(prompt: str) -> str:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434").strip() or "http://localhost:11434"
    model = os.getenv("RECALL_PHASE6_METADATA_MODEL", "llama3.2:3b").strip() or "llama3.2:3b"
    retries = _int_env("RECALL_GENERATE_RETRIES", default=3, minimum=1)
    backoff_seconds = _float_env("RECALL_GENERATE_BACKOFF_SECONDS", default=1.5, minimum=0.0)

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 1200,
        },
    }

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = httpx.post(
                f"{host}/api/generate",
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            body = response.json()
            text = str(body.get("response") or "").strip()
            if not text:
                raise ValueError("Ollama response was empty.")
            return text
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(backoff_seconds * attempt)

    if last_error is not None:
        raise last_error
    raise RuntimeError("Ollama call failed without an error.")


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    candidate = _extract_first_json_object(text)
    if candidate is None:
        raise ValueError("Could not parse JSON object from LLM response.")
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise ValueError("Parsed JSON is not an object.")
    return parsed


def _extract_first_json_object(text: str) -> str | None:
    depth = 0
    start = -1
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
            continue
        if char == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start >= 0:
                return text[start : index + 1]

    return None


def _best_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text and text.lower() not in {"none", "null", "n/a", "unknown"}:
            return text
    return ""


def _coerce_salary(value: Any) -> int | None:
    if value in {None, "", "null"}:
        return None
    if isinstance(value, (int, float)):
        numeric = int(value)
        return numeric if numeric > 0 else None
    text = str(value).strip().replace(",", "")
    match = re.search(r"\d{2,7}", text)
    if not match:
        return None
    numeric = int(match.group(0))
    return numeric if numeric > 0 else None


def _infer_company_from_title(title: str) -> str:
    text = title.strip()
    separators = [" at ", " @ ", " - ", " | "]
    lowered = text.lower()
    for separator in separators:
        index = lowered.find(separator)
        if index > 0:
            maybe_company = text[index + len(separator) :].strip()
            if maybe_company and len(maybe_company) <= 120:
                return maybe_company
    return ""


def _infer_location_type(location: str, description: str) -> str:
    lowered = f"{location} {description}".lower()
    if "remote" in lowered:
        return "remote"
    if "hybrid" in lowered:
        return "hybrid"
    if "onsite" in lowered or "on-site" in lowered or "on site" in lowered:
        return "onsite"
    return "onsite"


def _int_env(name: str, *, default: int, minimum: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return parsed if parsed >= minimum else minimum


def _float_env(name: str, *, default: float, minimum: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        parsed = float(raw)
    except ValueError:
        return default
    return parsed if parsed >= minimum else minimum
