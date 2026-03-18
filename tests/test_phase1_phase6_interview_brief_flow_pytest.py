#!/usr/bin/env python3
"""Integration-style pytest coverage for the Phase 1 -> Phase 6 interview-brief flow."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator
from unittest.mock import patch

from fastapi.testclient import TestClient

from scripts.phase1 import ingest_bridge_api
from scripts.phase6 import interview_brief_drafter


@contextmanager
def _build_client(env_updates: dict[str, str]) -> Iterator[TestClient]:
    merged_env = {
        "RECALL_PRELOAD_OLLAMA_MODELS": "false",
        "RECALL_DASHBOARD_CACHE_WARMER": "false",
    }
    merged_env.update(env_updates)
    with patch.dict(os.environ, merged_env, clear=False):
        app = ingest_bridge_api.create_app()
        with TestClient(app) as client:
            yield client


def test_interview_brief_endpoint_uses_phase6_drafter_dependencies(monkeypatch) -> None:
    monkeypatch.setattr(
        interview_brief_drafter,
        "get_job",
        lambda job_id: {
            "jobId": job_id,
            "title": "Solutions Engineer",
            "company": "OpenAI",
            "location": "Remote",
            "description": "Help customers adopt AI products.",
            "matching_skills": [{"skill": "API design"}],
            "gaps": [{"gap": "Deep security domain depth"}],
            "score_rationale": "Strong applied fit.",
            "application_tips": "Lead with technical customer empathy.",
        },
    )
    monkeypatch.setattr(interview_brief_drafter, "_load_resume_text", lambda: "Resume context here.")
    monkeypatch.setattr(
        interview_brief_drafter,
        "_load_runtime_settings",
        lambda settings=None: {"evaluation_model": "local", "local_model": "qwen2.5:7b-instruct"},
    )
    monkeypatch.setattr(
        interview_brief_drafter,
        "_call_ollama",
        lambda prompt, settings: (
            "## Role Snapshot\n"
            "- Customer-facing AI role.\n"
            "- Strong fit around platform adoption.\n\n"
            "## Why You Match\n"
            "- Resume shows API delivery work.\n"
            "- Stakeholder translation is well supported.\n\n"
            "## Stories To Prepare\n"
            "- Tell a rollout story.\n"
            "- Tell a stakeholder alignment story.\n\n"
            "## Risks To Address\n"
            "- Acknowledge missing domain depth carefully.\n"
            "- Do not overstate unsupported tools.\n\n"
            "## Questions To Ask\n"
            "- Ask about first-quarter success.\n"
            "- Ask where customer adoption gets stuck."
        ),
    )

    env = {
        "RECALL_API_KEY": "",
        "RECALL_API_RATE_LIMIT_WINDOW_SECONDS": "60",
        "RECALL_API_RATE_LIMIT_MAX_REQUESTS": "20",
    }
    with _build_client(env) as client:
        response = client.post(
            "/v1/interview-briefs",
            json={"job_id": "job-1", "save_to_vault": False, "settings": {"evaluation_model": "local"}},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["workflow"] == "workflow_06a_interview_brief"
    assert body["job_id"] == "job-1"
    assert body["provider"] == "ollama"
    assert body["model"] == "qwen2.5:7b-instruct"
    assert "## Role Snapshot" in body["brief"]
