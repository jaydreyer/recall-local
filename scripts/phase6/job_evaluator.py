#!/usr/bin/env python3
"""Phase 6C job evaluation pipeline and run orchestration."""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from scripts.phase1.ingestion_pipeline import qdrant_client_from_env
from scripts.phase6 import storage
from scripts.phase6.setup_collections import COLLECTION_JOBS, COLLECTION_RESUME


class MalformedResponseError(RuntimeError):
    """Raised when model output is not valid evaluation JSON."""


JOB_EVAL_RUNS_LOCK = threading.Lock()
JOB_EVAL_RUNS: dict[str, dict[str, Any]] = {}

ALLOWED_CLOUD_PROVIDERS = {"anthropic", "openai", "gemini"}
ALLOWED_RECOMMENDATION_TYPES = {"course", "project", "video", "certification", "article"}
ALLOWED_SEVERITY = {"critical", "moderate", "minor"}
ALLOWED_LOCATION_TYPES = {"remote", "hybrid", "onsite"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def queue_job_evaluations(
    *,
    job_ids: list[str],
    wait: bool = False,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    unique_ids = [item for item in dict.fromkeys(str(job_id).strip() for job_id in job_ids) if item]
    run_id = f"job_eval_{uuid.uuid4().hex[:12]}"
    resolved_settings = _load_runtime_settings(settings)

    if wait:
        started = time.perf_counter()
        result = _evaluate_jobs(job_ids=unique_ids, settings=resolved_settings)
        result.update(
            {
                "run_id": run_id,
                "queued": len(unique_ids),
                "job_ids": unique_ids,
                "status": "completed",
                "wait": True,
                "triggered_at": _now_iso(),
                "latency_ms": int((time.perf_counter() - started) * 1000),
                "settings": resolved_settings,
                "message": f"Evaluated {result.get('evaluated', 0)} jobs.",
            }
        )
        _set_job_eval_run(
            run_id=run_id,
            state={
                "run_id": run_id,
                "status": "completed",
                "queued": len(unique_ids),
                "job_ids": unique_ids,
                "result": result,
                "started_at": result.get("triggered_at"),
                "ended_at": _now_iso(),
            },
        )
        return result

    _set_job_eval_run(
        run_id=run_id,
        state={
            "run_id": run_id,
            "status": "queued",
            "queued": len(unique_ids),
            "job_ids": unique_ids,
            "settings": resolved_settings,
            "triggered_at": _now_iso(),
            "started_at": None,
            "ended_at": None,
            "result": None,
            "error": None,
        },
    )

    thread = threading.Thread(
        target=_run_job_eval_background,
        kwargs={
            "run_id": run_id,
            "job_ids": unique_ids,
            "settings": resolved_settings,
        },
        daemon=True,
    )
    thread.start()

    return {
        "run_id": run_id,
        "queued": len(unique_ids),
        "job_ids": unique_ids,
        "status": "queued",
        "wait": False,
        "triggered_at": _now_iso(),
        "settings": resolved_settings,
        "message": "Job evaluation run queued.",
    }


def _run_job_eval_background(*, run_id: str, job_ids: list[str], settings: dict[str, Any]) -> None:
    _update_job_eval_run(run_id, status="running", started_at=_now_iso())
    try:
        result = _evaluate_jobs(job_ids=job_ids, settings=settings)
    except Exception as exc:  # noqa: BLE001
        _update_job_eval_run(run_id, status="failed", ended_at=_now_iso(), error=str(exc), result=None)
        return

    _update_job_eval_run(run_id, status="completed", ended_at=_now_iso(), result=result, error=None)


def _evaluate_jobs(*, job_ids: list[str], settings: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    evaluated = 0
    failed = 0

    for job_id in job_ids:
        try:
            evaluation = evaluate_job(job_id=job_id, settings=settings)
            rows.append(
                {
                    "job_id": job_id,
                    "status": "completed",
                    "fit_score": evaluation.get("fit_score", -1),
                    "evaluation": evaluation,
                    "observation": evaluation.get("observation") or {},
                }
            )
            evaluated += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            _store_error(job_id=job_id, error_message=str(exc))
            rows.append(
                {
                    "job_id": job_id,
                    "status": "error",
                    "fit_score": -1,
                    "error": str(exc),
                }
            )

    return {
        "evaluated": evaluated,
        "failed": failed,
        "results": rows,
    }


def evaluate_job(*, job_id: str, settings: dict[str, Any]) -> dict[str, Any]:
    job = _load_job_payload(job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")

    resume_text = _load_resume_text()
    if not resume_text:
        raise RuntimeError("No resume found in recall_resume. Ingest a resume before evaluation.")

    prompt = _build_evaluation_prompt(job=job, resume_text=resume_text)
    model_mode = str(settings.get("evaluation_model", "local")).strip().lower()

    first_response = _call_cloud(prompt=prompt, settings=settings) if model_mode == "cloud" else _call_ollama(prompt=prompt, settings=settings)
    evaluation = _parse_with_retry(
        first_response=first_response,
        prompt=prompt,
        settings=settings,
        retry_mode=model_mode,
    )

    escalation_reasons = _escalation_reasons(evaluation=evaluation, settings=settings) if model_mode == "local" else []
    escalated = model_mode == "local" and bool(escalation_reasons)

    if escalated:
        cloud_response = _call_cloud(prompt=prompt, settings=settings)
        cloud_eval = _parse_with_retry(
            first_response=cloud_response,
            prompt=prompt,
            settings=settings,
            retry_mode="cloud",
        )
        evaluation = _merge_evaluations(local_eval=evaluation, cloud_eval=cloud_eval)
        evaluation["evaluation_model"] = "cloud_escalated"
    else:
        evaluation["evaluation_model"] = model_mode

    evaluation["job_id"] = str(job.get("job_id") or job.get("doc_id") or job_id)
    evaluation["title"] = str(job.get("title") or "")
    evaluation["company"] = str(job.get("company") or "")
    evaluation["company_tier"] = _coerce_int(job.get("company_tier"), default=0)
    evaluation["url"] = str(job.get("url") or "")
    evaluation["observation"] = _build_observation(
        job=job,
        settings=settings,
        initial_mode=model_mode,
        escalated=escalated,
        escalation_reasons=escalation_reasons,
    )

    _store_evaluation(job_id=job_id, evaluation=evaluation)
    return evaluation


def _parse_with_retry(
    *,
    first_response: str,
    prompt: str,
    settings: dict[str, Any],
    retry_mode: str,
) -> dict[str, Any]:
    try:
        return parse_evaluation(first_response)
    except MalformedResponseError:
        strict_prompt = (
            "IMPORTANT: Return ONLY a JSON object. No explanation, no markdown, no code fences.\n\n"
            f"{prompt}"
        )
        retry_response = (
            _call_cloud(prompt=strict_prompt, settings=settings)
            if retry_mode == "cloud"
            else _call_ollama(prompt=strict_prompt, settings=settings)
        )
        try:
            return parse_evaluation(retry_response)
        except MalformedResponseError as exc:
            raise RuntimeError(f"LLM returned malformed evaluation JSON after retry: {exc}") from exc


def parse_evaluation(response_text: str) -> dict[str, Any]:
    cleaned = _clean_response_json(response_text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise MalformedResponseError("LLM returned invalid JSON") from exc

    if not isinstance(data, dict):
        raise MalformedResponseError("Evaluation payload must be a JSON object.")

    required_keys = ["fit_score", "score_rationale", "matching_skills", "gaps"]
    for key in required_keys:
        if key not in data:
            raise MalformedResponseError(f"Missing required key: {key}")

    fit_score = _coerce_int(data.get("fit_score"), field="fit_score")
    if fit_score < 0 or fit_score > 100:
        raise MalformedResponseError(f"fit_score {fit_score} out of range")

    score_rationale = str(data.get("score_rationale") or "").strip()
    if not score_rationale:
        raise MalformedResponseError("score_rationale must be non-empty")

    matching_skills = _normalize_matching_skills(data.get("matching_skills"))
    gaps = _normalize_gaps(data.get("gaps"))

    return {
        "fit_score": fit_score,
        "score_rationale": score_rationale,
        "matching_skills": matching_skills,
        "gaps": gaps,
        "application_tips": str(data.get("application_tips") or "").strip(),
        "cover_letter_angle": str(data.get("cover_letter_angle") or "").strip(),
    }


def _should_escalate(*, evaluation: dict[str, Any], settings: dict[str, Any]) -> bool:
    return bool(_escalation_reasons(evaluation=evaluation, settings=settings))


def _escalation_reasons(*, evaluation: dict[str, Any], settings: dict[str, Any]) -> list[str]:
    if not bool(settings.get("auto_escalate", False)):
        return []

    threshold_gaps = int(settings.get("escalate_threshold_gaps", 2) or 0)
    threshold_words = int(settings.get("escalate_threshold_rationale_words", 20) or 0)

    gaps = evaluation.get("gaps") if isinstance(evaluation.get("gaps"), list) else []
    rationale = str(evaluation.get("score_rationale") or "").strip()
    rationale_words = len([word for word in rationale.split() if word])

    reasons: list[str] = []
    if len(gaps) < threshold_gaps:
        reasons.append("gaps_below_threshold")
    if rationale_words < threshold_words:
        reasons.append("rationale_too_short")
    return reasons


def _build_observation(
    *,
    job: dict[str, Any],
    settings: dict[str, Any],
    initial_mode: str,
    escalated: bool,
    escalation_reasons: list[str],
) -> dict[str, Any]:
    location = str(job.get("location") or "").strip()
    location_type = str(job.get("location_type") or "").strip().lower()
    description = str(job.get("description") or "").strip()
    blob = f"{location} {description[:800]}".lower()

    is_remote = location_type == "remote" or "remote" in blob
    is_twin_cities = any(token in blob for token in ("minneapolis", "st paul", "saint paul", "twin cities"))

    inferred_location_type = location_type
    if inferred_location_type not in ALLOWED_LOCATION_TYPES:
        if is_remote:
            inferred_location_type = "remote"
        elif "hybrid" in blob:
            inferred_location_type = "hybrid"
        else:
            inferred_location_type = "onsite"

    if is_remote:
        preference_bucket = "remote"
    elif is_twin_cities:
        preference_bucket = "twin_cities"
    else:
        preference_bucket = "other"

    provider_sequence = "local->cloud" if escalated else initial_mode
    return {
        "provider_sequence": provider_sequence,
        "escalation": {
            "enabled": bool(settings.get("auto_escalate", False)) and initial_mode == "local",
            "triggered": escalated,
            "reasons": list(escalation_reasons),
        },
        "location": {
            "raw": location,
            "location_type": inferred_location_type,
            "is_remote": is_remote,
            "is_twin_cities": is_twin_cities,
            "preference_bucket": preference_bucket,
        },
        "settings_snapshot": {
            "evaluation_model": initial_mode,
            "auto_escalate": bool(settings.get("auto_escalate", False)),
            "escalate_threshold_gaps": int(settings.get("escalate_threshold_gaps", 2) or 0),
            "escalate_threshold_rationale_words": int(settings.get("escalate_threshold_rationale_words", 20) or 0),
        },
    }


def _merge_evaluations(*, local_eval: dict[str, Any], cloud_eval: dict[str, Any]) -> dict[str, Any]:
    merged = dict(local_eval)
    for key in (
        "fit_score",
        "score_rationale",
        "matching_skills",
        "gaps",
        "application_tips",
        "cover_letter_angle",
    ):
        value = cloud_eval.get(key)
        if value is not None and value != "" and value != [] and value != {}:
            merged[key] = value
    return merged


def _build_evaluation_prompt(*, job: dict[str, Any], resume_text: str) -> str:
    description = str(job.get("description") or "").strip()
    if len(description) > 12000:
        description = description[:12000]

    if len(resume_text) > 14000:
        resume_text = resume_text[:14000]

    return (
        "You are a career advisor evaluating job fit. You will receive: "
        "(1) a job listing and (2) a candidate resume.\n"
        "Evaluate how well the candidate fits the role. Be critical and honest. "
        "A score of 70+ means the candidate is a strong fit.\n"
        "Be specific about missing skills and provide practical recommendations.\n\n"
        "Return ONLY valid JSON:\n"
        "{\n"
        '  "fit_score": <0-100>,\n'
        '  "score_rationale": "<2-3 sentence summary>",\n'
        '  "matching_skills": [{"skill": "<skill>", "evidence": "<resume evidence>"}],\n'
        '  "gaps": [\n'
        "    {\n"
        '      "gap": "<missing skill or experience>",\n'
        '      "severity": "critical|moderate|minor",\n'
        '      "recommendations": [\n'
        "        {\n"
        '          "type": "course|project|video|certification|article",\n'
        '          "title": "<specific suggestion>",\n'
        '          "source": "<platform or URL>",\n'
        '          "effort": "<estimated effort>"\n'
        "        }\n"
        "      ]\n"
        "    }\n"
        "  ],\n"
        '  "application_tips": "<1-2 sentences>",\n'
        '  "cover_letter_angle": "<strongest narrative angle>"\n'
        "}\n\n"
        "Job listing:\n"
        f"Title: {job.get('title', 'Unknown')}\n"
        f"Company: {job.get('company', 'Unknown')}\n"
        f"Location: {job.get('location', 'Unknown')}\n"
        f"URL: {job.get('url') or 'n/a'}\n"
        f"Description:\n{description}\n\n"
        "Candidate resume:\n"
        f"{resume_text}"
    )


def _call_ollama(*, prompt: str, settings: dict[str, Any]) -> str:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434").strip() or "http://localhost:11434"
    model = str(settings.get("local_model") or os.getenv("RECALL_PHASE6_EVAL_LOCAL_MODEL") or "llama3.2:3b").strip()
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 2200,
        },
    }
    response = _post_json_with_retries(
        url=f"{host}/api/generate",
        headers={"Content-Type": "application/json"},
        payload=payload,
        timeout_seconds=180.0,
    )
    text = str(response.json().get("response") or "").strip()
    if not text:
        raise RuntimeError("Ollama evaluation response was empty.")
    return text


def _call_cloud(*, prompt: str, settings: dict[str, Any]) -> str:
    provider = str(settings.get("cloud_provider") or "anthropic").strip().lower()
    model = str(settings.get("cloud_model") or "").strip()
    max_tokens = int(settings.get("max_tokens") or 2200)

    if provider == "anthropic":
        api_key = _require_env("ANTHROPIC_API_KEY")
        payload: dict[str, Any] = {
            "model": model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"),
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}],
        }
        response = _post_json_with_retries(
            url="https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            payload=payload,
            timeout_seconds=120.0,
        )
        content = response.json().get("content", [])
        if not content:
            raise RuntimeError("Anthropic response missing content.")
        return str(content[0].get("text") or "").strip()

    if provider == "openai":
        api_key = _require_env("OPENAI_API_KEY")
        payload = {
            "model": model or os.getenv("OPENAI_MODEL", "gpt-4o"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        response = _post_json_with_retries(
            url="https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            payload=payload,
            timeout_seconds=120.0,
        )
        choices = response.json().get("choices") or []
        if not choices:
            raise RuntimeError("OpenAI response missing choices.")
        return str(choices[0].get("message", {}).get("content") or "").strip()

    if provider == "gemini":
        api_key = _require_env("GEMINI_API_KEY")
        model_name = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": max_tokens,
            },
        }
        response = _post_json_with_retries(
            url=f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent",
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            payload=payload,
            timeout_seconds=120.0,
        )
        candidates = response.json().get("candidates") or []
        if not candidates:
            raise RuntimeError("Gemini response missing candidates.")
        parts = candidates[0].get("content", {}).get("parts") or []
        if not parts:
            raise RuntimeError("Gemini response missing parts.")
        return "\n".join(str(part.get("text") or "") for part in parts).strip()

    raise ValueError(f"Unsupported cloud provider: {provider}")


def _post_json_with_retries(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout_seconds: float,
) -> httpx.Response:
    retries = _int_env("RECALL_GENERATE_RETRIES", default=3, minimum=1)
    backoff_seconds = _float_env("RECALL_GENERATE_BACKOFF_SECONDS", default=1.5, minimum=0.0)

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = httpx.post(
                url,
                headers=headers,
                json=payload,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            return response
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt >= retries or not _is_retryable_generation_error(exc):
                break
            time.sleep(backoff_seconds * attempt)

    if last_error is not None:
        raise last_error
    raise RuntimeError("Model call failed without error response.")


def _is_retryable_generation_error(exc: Exception) -> bool:
    if isinstance(exc, httpx.RequestError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        return status_code == 408 or status_code == 429 or status_code >= 500
    return False


def _clean_response_json(raw: str) -> str:
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return json.dumps(parsed)
    except json.JSONDecodeError:
        pass

    candidate = _extract_first_json_object(text)
    if candidate is None:
        raise MalformedResponseError("Could not find a JSON object in model response.")
    return candidate


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
            if depth <= 0:
                continue
            depth -= 1
            if depth == 0 and start >= 0:
                return text[start : index + 1]

    return None


def _normalize_matching_skills(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        raise MalformedResponseError("matching_skills must be a list")

    normalized: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, str):
            skill = item.strip()
            if skill:
                normalized.append({"skill": skill, "evidence": ""})
            continue
        if not isinstance(item, dict):
            continue
        skill = str(item.get("skill") or item.get("name") or "").strip()
        evidence = str(item.get("evidence") or item.get("proof") or "").strip()
        if skill:
            normalized.append({"skill": skill, "evidence": evidence})
    return normalized


def _normalize_gaps(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise MalformedResponseError("gaps must be a list")

    normalized: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            gap = item.strip()
            if gap:
                normalized.append(
                    {
                        "gap": gap,
                        "severity": "moderate",
                        "recommendations": [],
                    }
                )
            continue

        if not isinstance(item, dict):
            continue

        gap = str(item.get("gap") or item.get("skill") or item.get("name") or "").strip()
        if not gap:
            continue

        severity = str(item.get("severity") or "moderate").strip().lower()
        if severity not in ALLOWED_SEVERITY:
            severity = "moderate"

        recommendations_raw = item.get("recommendations") if isinstance(item.get("recommendations"), list) else []
        recommendations: list[dict[str, str]] = []
        for rec in recommendations_raw:
            if isinstance(rec, str):
                text = rec.strip()
                if text:
                    recommendations.append(
                        {
                            "type": "article",
                            "title": text,
                            "source": "",
                            "effort": "",
                        }
                    )
                continue
            if not isinstance(rec, dict):
                continue
            rec_type = str(rec.get("type") or "article").strip().lower()
            if rec_type not in ALLOWED_RECOMMENDATION_TYPES:
                rec_type = "article"
            title = str(rec.get("title") or "").strip()
            if not title:
                continue
            recommendations.append(
                {
                    "type": rec_type,
                    "title": title,
                    "source": str(rec.get("source") or "").strip(),
                    "effort": str(rec.get("effort") or "").strip(),
                }
            )

        normalized.append(
            {
                "gap": gap,
                "severity": severity,
                "recommendations": recommendations,
            }
        )

    return normalized


def _store_evaluation(*, job_id: str, evaluation: dict[str, Any]) -> None:
    record = _load_job_record_for_update(job_id)
    if record is None:
        raise ValueError(f"Job not found for update: {job_id}")

    payload = dict(record.get("payload") or {})
    payload.update(
        {
            "fit_score": int(evaluation.get("fit_score", -1)),
            "score_rationale": str(evaluation.get("score_rationale") or ""),
            "matching_skills": evaluation.get("matching_skills") or [],
            "gaps": evaluation.get("gaps") or [],
            "application_tips": str(evaluation.get("application_tips") or ""),
            "cover_letter_angle": str(evaluation.get("cover_letter_angle") or ""),
            "evaluated_at": _now_iso(),
            "status": "evaluated",
            "evaluation_model": evaluation.get("evaluation_model"),
            "observation": evaluation.get("observation") or {},
            "evaluation_error": None,
        }
    )

    _upsert_job_record(
        point_id=record["id"],
        vector=record.get("vector"),
        payload=payload,
    )


def _store_error(*, job_id: str, error_message: str) -> None:
    record = _load_job_record_for_update(job_id)
    if record is None:
        return

    payload = dict(record.get("payload") or {})
    payload.update(
        {
            "fit_score": -1,
            "score_rationale": f"Evaluation failed: {error_message}",
            "matching_skills": [],
            "gaps": [],
            "application_tips": "",
            "cover_letter_angle": "",
            "evaluated_at": _now_iso(),
            "status": "error",
            "observation": payload.get("observation") or {},
            "evaluation_error": error_message,
        }
    )

    _upsert_job_record(
        point_id=record["id"],
        vector=record.get("vector"),
        payload=payload,
    )


def _load_runtime_settings(overrides: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(storage.DEFAULT_LLM_SETTINGS)

    conn = storage.connect_db()
    try:
        merged.update(storage.get_llm_settings(conn))
    finally:
        conn.close()

    if not overrides:
        return _normalize_runtime_settings(merged)

    for key, value in overrides.items():
        if key in {
            "evaluation_model",
            "cloud_provider",
            "cloud_model",
            "auto_escalate",
            "escalate_threshold_gaps",
            "escalate_threshold_rationale_words",
            "local_model",
            "max_tokens",
        }:
            merged[key] = value

    return _normalize_runtime_settings(merged)


def _normalize_runtime_settings(settings: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(settings)
    normalized["evaluation_model"] = (
        str(normalized.get("evaluation_model") or "local").strip().lower()
    )
    if normalized["evaluation_model"] not in {"local", "cloud"}:
        normalized["evaluation_model"] = "local"

    normalized["cloud_provider"] = str(normalized.get("cloud_provider") or "anthropic").strip().lower()
    if normalized["cloud_provider"] not in ALLOWED_CLOUD_PROVIDERS:
        normalized["cloud_provider"] = "anthropic"

    normalized["cloud_model"] = str(normalized.get("cloud_model") or "").strip() or os.getenv(
        "ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929"
    )
    normalized["auto_escalate"] = _coerce_bool(normalized.get("auto_escalate", True), default=True)
    normalized["escalate_threshold_gaps"] = max(_coerce_int(normalized.get("escalate_threshold_gaps"), default=0), 0)
    normalized["escalate_threshold_rationale_words"] = max(
        _coerce_int(normalized.get("escalate_threshold_rationale_words"), default=0),
        0,
    )
    if "local_model" in normalized and normalized["local_model"] is not None:
        normalized["local_model"] = str(normalized["local_model"]).strip()
    if "max_tokens" in normalized and normalized["max_tokens"] is not None:
        normalized["max_tokens"] = max(_coerce_int(normalized["max_tokens"], default=2200), 256)
    return normalized


def _load_resume_text() -> str:
    host = os.getenv("QDRANT_HOST", "http://localhost:6333").strip() or "http://localhost:6333"
    client = qdrant_client_from_env(host)

    points: list[dict[str, Any]] = []
    offset: Any = None
    while True:
        response = client.scroll(
            collection_name=COLLECTION_RESUME,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        if isinstance(response, tuple) and len(response) == 2:
            records, offset = response
        else:
            records = getattr(response, "points", None)
            offset = getattr(response, "next_page_offset", None)
        if not records:
            break
        for record in records:
            payload = dict(getattr(record, "payload", {}) or {})
            text = str(payload.get("chunk_text") or "").strip()
            if not text:
                continue
            points.append(
                {
                    "text": text,
                    "index": _coerce_int(payload.get("chunk_index"), default=999999),
                }
            )
        if offset is None:
            break

    points.sort(key=lambda item: item["index"])
    return "\n\n".join(item["text"] for item in points)


def _load_job_payload(job_id: str) -> dict[str, Any] | None:
    record = _load_job_record_for_update(job_id)
    if record is None:
        return None
    return dict(record.get("payload") or {})


def _load_job_record_for_update(job_id: str) -> dict[str, Any] | None:
    target = str(job_id).strip()
    if not target:
        return None

    host = os.getenv("QDRANT_HOST", "http://localhost:6333").strip() or "http://localhost:6333"
    client = qdrant_client_from_env(host)
    from qdrant_client import models

    for field in ("job_id", "doc_id"):
        filter_payload = models.Filter(
            must=[
                models.FieldCondition(key=field, match=models.MatchValue(value=target)),
            ]
        )
        try:
            response = client.scroll(
                collection_name=COLLECTION_JOBS,
                limit=4,
                with_payload=True,
                with_vectors=True,
                query_filter=filter_payload,
            )
        except Exception as exc:
            if "query_filter" not in str(exc):
                raise
            response = client.scroll(
                collection_name=COLLECTION_JOBS,
                limit=4,
                with_payload=True,
                with_vectors=True,
                scroll_filter=filter_payload,
            )

        if isinstance(response, tuple) and len(response) == 2:
            records = response[0]
        else:
            records = getattr(response, "points", None)

        if records:
            record = records[0]
            return {
                "id": getattr(record, "id", None),
                "vector": getattr(record, "vector", None),
                "payload": dict(getattr(record, "payload", {}) or {}),
            }

    return None


def _upsert_job_record(*, point_id: Any, vector: Any, payload: dict[str, Any]) -> None:
    host = os.getenv("QDRANT_HOST", "http://localhost:6333").strip() or "http://localhost:6333"
    client = qdrant_client_from_env(host)
    from qdrant_client import models

    client.upsert(
        collection_name=COLLECTION_JOBS,
        points=[
            models.PointStruct(
                id=point_id,
                vector=vector,
                payload=payload,
            )
        ],
    )


def _set_job_eval_run(*, run_id: str, state: dict[str, Any]) -> None:
    with JOB_EVAL_RUNS_LOCK:
        JOB_EVAL_RUNS[run_id] = state


def _update_job_eval_run(run_id: str, **fields: Any) -> None:
    with JOB_EVAL_RUNS_LOCK:
        state = JOB_EVAL_RUNS.get(run_id)
        if state is None:
            return
        state.update(fields)


def _coerce_int(value: Any, *, field: str | None = None, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        if field is None:
            return default
        raise MalformedResponseError(f"{field} must be an integer") from exc


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off", ""}:
            return False
    return default


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


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value
