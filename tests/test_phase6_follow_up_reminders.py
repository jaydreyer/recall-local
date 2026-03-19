#!/usr/bin/env python3
"""Unit tests for Phase 6 follow-up reminder helpers."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts.phase6.follow_up_reminders import build_follow_up_reminder_text, queue_follow_up_reminder_runs


class FollowUpReminderTests(unittest.TestCase):
    def test_build_follow_up_reminder_text_includes_due_prompt_and_url(self) -> None:
        text = build_follow_up_reminder_text(
            {
                "title": "Solutions Engineer",
                "company": "OpenAI",
                "location": "Remote",
                "url": "https://example.com/jobs/123",
                "application_tips": "Send a concise note that reinforces customer-facing API wins. Mention operator empathy too.",
                "workflow": {
                    "followUp": {
                        "dueAt": "2026-03-24T16:00:00Z",
                    }
                },
            }
        )

        self.assertIn("Solutions Engineer @ OpenAI", text)
        self.assertIn("Due: Mar 24 at 4:00 PM UTC", text)
        self.assertIn("Location: Remote", text)
        self.assertIn("Prompt: Send a concise note that reinforces customer-facing API wins.", text)
        self.assertTrue(text.endswith("https://example.com/jobs/123"))

    def test_queue_follow_up_reminder_runs_selects_due_jobs_and_updates_metadata(self) -> None:
        jobs = [
            {
                "jobId": "job-1",
                "title": "Solutions Engineer",
                "company": "OpenAI",
                "location": "Remote",
                "url": "https://example.com/jobs/1",
                "workflow": {
                    "followUp": {
                        "status": "scheduled",
                        "dueAt": "2026-03-01T16:00:00Z",
                        "reminder": {
                            "status": "not_created",
                        },
                    }
                },
            },
            {
                "jobId": "job-2",
                "title": "Platform Engineer",
                "company": "OtherCo",
                "workflow": {
                    "followUp": {
                        "status": "scheduled",
                        "dueAt": "2099-03-01T16:00:00Z",
                        "reminder": {
                            "status": "not_created",
                        },
                    }
                },
            },
        ]

        with patch("scripts.phase6.follow_up_reminders.all_jobs", return_value=jobs), patch(
            "scripts.phase6.follow_up_reminders.update_job",
            side_effect=lambda **kwargs: {
                "jobId": kwargs["job_id"],
                "title": "Solutions Engineer",
                "company": "OpenAI",
                "location": "Remote",
                "url": "https://example.com/jobs/1",
                "workflow": {
                    "followUp": {
                        "status": "scheduled",
                        "dueAt": "2026-03-01T16:00:00Z",
                    }
                },
            },
        ) as update_mock:
            payload = queue_follow_up_reminder_runs(limit=10, due_only=True, dry_run=False, channel="n8n")

        self.assertEqual(payload["queued"], 1)
        self.assertEqual(payload["items"][0]["job_id"], "job-1")
        self.assertEqual(payload["items"][0]["reminder_status"], "queued")
        self.assertEqual(payload["items"][0]["delivery_target"], "telegram")
        self.assertEqual(update_mock.call_count, 1)
        self.assertEqual(update_mock.call_args.kwargs["workflow"]["followUp"]["reminder"]["status"], "queued")


if __name__ == "__main__":
    unittest.main()
