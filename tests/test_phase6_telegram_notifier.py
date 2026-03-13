#!/usr/bin/env python3
"""Unit tests for Phase 6 Telegram notification summaries."""

from __future__ import annotations

import unittest

from scripts.phase6.telegram_notifier import build_notification_text


class TelegramNotifierTests(unittest.TestCase):
    def test_build_notification_text_includes_match_gap_and_angle(self) -> None:
        payload = {
            "title": "Solutions Engineer",
            "company": "Anthropic",
            "fit_score": 82,
            "location": "Remote",
            "url": "https://example.com/jobs/1",
            "matching_skills": [
                {
                    "skill": "API governance",
                    "evidence": "Led API launches and developer rollout motions across product lines. Additional detail.",
                }
            ],
            "gaps": [{"gap": "Pre-sales demo experience", "severity": "moderate"}],
            "cover_letter_angle": "Lead with customer-facing API enablement and operator empathy. Then connect that to applied AI rollout wins.",
        }

        text = build_notification_text(payload)

        self.assertIn("Solutions Engineer @ Anthropic", text)
        self.assertIn("Fit: 82 | Remote", text)
        self.assertIn("Top match: API governance from Led API launches and developer rollout motions across product lines.", text)
        self.assertIn("Top gap: Pre-sales demo experience (moderate)", text)
        self.assertIn("Angle: Lead with customer-facing API enablement and operator empathy.", text)
        self.assertTrue(text.endswith("https://example.com/jobs/1"))

    def test_build_notification_text_uses_fallback_copy_when_signals_missing(self) -> None:
        text = build_notification_text({"title": "Unknown", "company": "Fallback Co"})

        self.assertIn("Top match: No evidence-backed match captured yet.", text)
        self.assertIn("Top gap: No priority gap captured.", text)
        self.assertIn("Angle: Open the dossier for the full evaluation context.", text)

    def test_build_notification_text_truncates_on_word_boundary(self) -> None:
        payload = {
            "title": "AI Deployment Engineer",
            "company": "OpenAI",
            "fit_score": 93,
            "location": "Remote - US",
            "url": "https://example.com/jobs/2",
            "matching_skills": [
                {
                    "skill": "AI Strategy & Implementation",
                    "evidence": "Built a custom GPT that replaces a fifty-thousand-dollar yearly workflow and improved enterprise operator adoption.",
                }
            ],
        }

        text = build_notification_text(payload)

        self.assertIn("Top match: AI Strategy & Implementation from Built a custom GPT", text)
        self.assertIn("fifty-thousand-dollar...", text)
        self.assertNotIn("fifty-thousand-d...", text)


if __name__ == "__main__":
    unittest.main()
