#!/usr/bin/env python3
"""Unit tests for Phase 6 job repository helpers."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts.phase6 import job_repository


class JobRepositoryTests(unittest.TestCase):
    def test_normalize_workflow_includes_cover_letter_artifact_defaults(self) -> None:
        normalized = job_repository._normalize_workflow(
            {
                "packet": {"coverLetterDraft": True},
                "nextAction": {
                    "action": "tailor_resume",
                    "rationale": "The role is a strong fit and packet work should start now.",
                    "confidence": "high",
                    "dueAt": "2026-03-20T16:00:00Z",
                },
                "artifacts": {
                    "coverLetterDraft": {
                        "draftId": "cover_letter_job-1",
                        "generatedAt": "2026-03-18T04:10:00Z",
                        "provider": "ollama",
                        "model": "qwen2.5:7b-instruct",
                        "wordCount": 132,
                        "savedToVault": True,
                        "vaultPath": "/tmp/example.md",
                    },
                    "resumeBullets": {
                        "status": "ready",
                        "updatedAt": "2026-03-18T09:15:00Z",
                        "source": "manual",
                        "vaultPath": "career/packets/job-1/resume-bullets.md",
                        "notes": "Stored in the packet folder.",
                    },
                },
            }
        )

        self.assertTrue(normalized["packet"]["coverLetterDraft"])
        self.assertEqual(normalized["nextAction"]["action"], "tailor_resume")
        self.assertEqual(normalized["nextAction"]["confidence"], "high")
        self.assertEqual(normalized["artifacts"]["coverLetterDraft"]["draftId"], "cover_letter_job-1")
        self.assertEqual(normalized["artifacts"]["coverLetterDraft"]["wordCount"], 132)
        self.assertTrue(normalized["artifacts"]["coverLetterDraft"]["savedToVault"])
        self.assertEqual(normalized["artifacts"]["resumeBullets"]["status"], "ready")
        self.assertEqual(normalized["artifacts"]["resumeBullets"]["source"], "manual")

    def test_workflow_packet_readiness_requires_checked_and_linked_core_artifacts(self) -> None:
        readiness = job_repository._workflow_packet_readiness(
            {
                "packet": {
                    "tailoredSummary": True,
                    "resumeBullets": True,
                    "coverLetterDraft": False,
                },
                "artifacts": {
                    "tailoredSummary": {
                        "status": "ready",
                        "updatedAt": "2026-03-18T12:00:00Z",
                        "source": "manual",
                    },
                    "resumeBullets": {
                        "status": "ready",
                        "updatedAt": "2026-03-18T12:05:00Z",
                        "source": "manual",
                    },
                    "coverLetterDraft": {
                        "draftId": "cover_letter_job-1",
                        "generatedAt": "2026-03-18T12:10:00Z",
                        "provider": "ollama",
                        "model": "qwen2.5:7b-instruct",
                    },
                },
            }
        )

        self.assertEqual(readiness["counts"]["checked"], 2)
        self.assertEqual(readiness["counts"]["linked"], 3)
        self.assertEqual(readiness["counts"]["verified"], 2)
        self.assertEqual(readiness["artifactWithoutChecklist"], ["coverLetterDraft"])
        self.assertFalse(readiness["readyForApproval"])

    def test_list_jobs_search_matches_company_gap_and_notes_fields(self) -> None:
        jobs = [
            {
                "jobId": "job-1",
                "title": "Solutions Engineer",
                "company": "OpenAI",
                "company_normalized": "openai",
                "company_tier": 2,
                "location": "Remote",
                "source": "career_page",
                "status": "evaluated",
                "fit_score": 88,
                "matching_skills": [{"skill": "API strategy", "evidence": "Owned API launches"}],
                "gaps": [{"gap": "Pre-sales demos", "severity": "moderate"}],
                "application_tips": "Lead with customer-facing API wins.",
                "cover_letter_angle": "Show operator empathy and AI rollout experience.",
                "notes": "Warm intro possible through former partner contact.",
                "observation": {"escalation_reasons": ["gaps_below_threshold"]},
                "discovered_at": "2026-03-12T10:00:00+00:00",
            },
            {
                "jobId": "job-2",
                "title": "Backend Engineer",
                "company": "OtherCo",
                "company_normalized": "otherco",
                "company_tier": 3,
                "location": "Minneapolis, MN",
                "source": "jobspy",
                "status": "evaluated",
                "fit_score": 41,
                "matching_skills": [],
                "gaps": [],
                "application_tips": "",
                "cover_letter_angle": "",
                "notes": "",
                "observation": {},
                "discovered_at": "2026-03-11T10:00:00+00:00",
            },
        ]

        with patch("scripts.phase6.job_repository._scroll_jobs", return_value=jobs):
            by_company = job_repository.list_jobs(status="evaluated", search="openai")
            by_gap = job_repository.list_jobs(status="evaluated", search="pre-sales demos")
            by_notes = job_repository.list_jobs(status="evaluated", search="warm intro")

        self.assertEqual(by_company["total"], 1)
        self.assertEqual(by_company["items"][0]["jobId"], "job-1")
        self.assertEqual(by_gap["total"], 1)
        self.assertEqual(by_gap["items"][0]["jobId"], "job-1")
        self.assertEqual(by_notes["total"], 1)
        self.assertEqual(by_notes["items"][0]["jobId"], "job-1")

    def test_list_jobs_falls_back_to_title_query_when_search_not_provided(self) -> None:
        jobs = [
            {
                "jobId": "job-1",
                "title": "Forward Deployed Engineer",
                "company": "OpenAI",
                "company_normalized": "openai",
                "company_tier": 2,
                "location": "Remote",
                "source": "career_page",
                "status": "evaluated",
                "fit_score": 84,
                "matching_skills": [],
                "gaps": [],
                "application_tips": "",
                "cover_letter_angle": "",
                "notes": "",
                "observation": {},
                "discovered_at": "2026-03-12T10:00:00+00:00",
            }
        ]

        with patch("scripts.phase6.job_repository._scroll_jobs", return_value=jobs):
            payload = job_repository.list_jobs(status="evaluated", title_query="forward deployed")

        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["jobId"], "job-1")

    def test_normalize_workflow_timeline_infers_event_metadata_for_legacy_entries(self) -> None:
        normalized = job_repository._normalize_workflow_timeline(
            [
                {
                    "type": "packet_approved",
                    "label": "Packet approved",
                    "detail": None,
                    "at": "2026-03-18T20:00:00Z",
                },
                {
                    "type": "follow_up_scheduled",
                    "label": "Follow-up scheduled",
                    "detail": "Due Mar 24, 2026 at 4:00 PM UTC",
                    "at": "2026-03-18T20:05:00Z",
                    "category": "follow_up",
                    "origin": "persisted",
                    "tone": "pending",
                },
            ]
        )

        self.assertEqual(normalized[0]["category"], "approval")
        self.assertEqual(normalized[0]["origin"], "persisted")
        self.assertEqual(normalized[0]["tone"], "complete")
        self.assertEqual(normalized[1]["category"], "follow_up")
        self.assertEqual(normalized[1]["tone"], "pending")

    def test_update_job_records_richer_workflow_timeline_events(self) -> None:
        current = {
            "jobId": "job-123",
            "status": "evaluated",
            "applied": False,
            "dismissed": False,
            "applied_at": None,
            "fit_score": 88,
            "notes": "",
            "workflow": {
                "stage": "review",
                "nextActionApproval": "pending",
                "packetApproval": "pending",
                "packet": {
                    "tailoredSummary": False,
                    "resumeBullets": False,
                    "coverLetterDraft": False,
                    "outreachNote": False,
                    "interviewBrief": False,
                    "talkingPoints": False,
                },
                "nextAction": {
                    "action": "review_role",
                    "rationale": "Review before deeper work.",
                    "confidence": "medium",
                    "dueAt": None,
                },
                "artifacts": {},
                "followUp": {
                    "status": "not_scheduled",
                    "dueAt": None,
                    "lastCompletedAt": None,
                },
                "updatedAt": "2026-03-17T20:00:00Z",
            },
            "workflowTimeline": [],
            "_payload": {},
            "_vector": [0.1, 0.2],
            "_qdrant_id": "point-123",
        }

        with patch("scripts.phase6.job_repository.get_job_raw", return_value=current), patch(
            "scripts.phase6.job_repository.get_job",
            side_effect=lambda _job_id: job_repository._sanitize_job(dict(current)),
        ), patch("scripts.phase6.job_repository.qdrant_client_from_env") as qdrant_client_mock, patch.dict(
            "sys.modules",
            {"qdrant_client": SimpleNamespace(models=SimpleNamespace(PointStruct=lambda **kwargs: kwargs))},
        ):
            qdrant_client_mock.return_value.upsert.return_value = None
            updated = job_repository.update_job(
                job_id="job-123",
                status=None,
                applied=None,
                dismissed=None,
                notes=None,
                workflow={
                    "stage": "follow_up",
                    "nextActionApproval": "approved",
                    "nextAction": {
                        "action": "send_follow_up",
                        "rationale": "The role is already applied and due for outreach.",
                        "confidence": "high",
                        "dueAt": "2026-03-24T16:00:00Z",
                    },
                    "packetApproval": "approved",
                    "packet": {
                        "tailoredSummary": True,
                    },
                    "artifacts": {
                        "resumeBullets": {
                            "status": "ready",
                            "updatedAt": "2026-03-18T20:10:00Z",
                            "source": "manual",
                            "vaultPath": "career/packets/job-123/resume-bullets.md",
                            "notes": "Tailored bullet set linked in Ops.",
                        }
                    },
                    "followUp": {
                        "status": "scheduled",
                        "dueAt": "2026-03-24T16:00:00Z",
                    },
                },
            )

        self.assertIsNotNone(updated)
        event_labels = [event["label"] for event in current["workflowTimeline"]]
        self.assertIn("Next action approved", event_labels)
        self.assertIn("Packet approved", event_labels)
        self.assertIn("Moved to Follow-up lane", event_labels)
        self.assertIn("Tailored summary completed", event_labels)
        self.assertIn("Resume bullets artifact linked", event_labels)
        self.assertIn("Follow-up scheduled", event_labels)
        categories_by_label = {event["label"]: event["category"] for event in current["workflowTimeline"]}
        self.assertEqual(categories_by_label["Next action approved"], "approval")
        self.assertEqual(categories_by_label["Moved to Follow-up lane"], "workflow")
        self.assertEqual(categories_by_label["Tailored summary completed"], "packet")
        self.assertEqual(categories_by_label["Follow-up scheduled"], "follow_up")
        tones_by_label = {event["label"]: event["tone"] for event in current["workflowTimeline"]}
        self.assertEqual(tones_by_label["Packet approved"], "complete")
        self.assertEqual(tones_by_label["Resume bullets artifact linked"], "pending")

    def test_update_job_marks_follow_up_complete_and_clears_due_date(self) -> None:
        current = {
            "jobId": "job-234",
            "status": "applied",
            "applied": True,
            "dismissed": False,
            "applied_at": "2026-03-17T18:00:00Z",
            "fit_score": 83,
            "notes": "",
            "workflow": {
                "stage": "follow_up",
                "nextActionApproval": "approved",
                "packetApproval": "approved",
                "packet": {
                    "tailoredSummary": True,
                    "resumeBullets": True,
                    "coverLetterDraft": True,
                    "outreachNote": False,
                    "interviewBrief": False,
                    "talkingPoints": False,
                },
                "nextAction": {
                    "action": "send_follow_up",
                    "rationale": "Follow-up is due.",
                    "confidence": "high",
                    "dueAt": "2026-03-20T16:00:00Z",
                },
                "artifacts": {},
                "followUp": {
                    "status": "scheduled",
                    "dueAt": "2026-03-20T16:00:00Z",
                    "lastCompletedAt": None,
                },
                "updatedAt": "2026-03-18T18:00:00Z",
            },
            "workflowTimeline": [],
            "_payload": {},
            "_vector": [0.3, 0.4],
            "_qdrant_id": "point-234",
        }

        with patch("scripts.phase6.job_repository.get_job_raw", return_value=current), patch(
            "scripts.phase6.job_repository.get_job",
            side_effect=lambda _job_id: job_repository._sanitize_job(dict(current)),
        ), patch("scripts.phase6.job_repository.qdrant_client_from_env") as qdrant_client_mock, patch.dict(
            "sys.modules",
            {"qdrant_client": SimpleNamespace(models=SimpleNamespace(PointStruct=lambda **kwargs: kwargs))},
        ):
            qdrant_client_mock.return_value.upsert.return_value = None
            updated = job_repository.update_job(
                job_id="job-234",
                status=None,
                applied=None,
                dismissed=None,
                notes=None,
                workflow={
                    "followUp": {
                        "status": "completed",
                    }
                },
            )

        self.assertIsNotNone(updated)
        self.assertEqual(current["workflow"]["followUp"]["status"], "completed")
        self.assertIsNone(current["workflow"]["followUp"]["dueAt"])
        self.assertIsNotNone(current["workflow"]["followUp"]["lastCompletedAt"])
        self.assertEqual(current["workflowTimeline"][-1]["label"], "Follow-up completed")
        self.assertEqual(current["workflowTimeline"][-1]["category"], "follow_up")
        self.assertEqual(current["workflowTimeline"][-1]["tone"], "complete")


if __name__ == "__main__":
    unittest.main()
