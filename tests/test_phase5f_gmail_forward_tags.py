#!/usr/bin/env python3
"""Regression tests for Gmail-forward payload normalization."""

from __future__ import annotations

import unittest

from scripts.phase1.channel_adapters import normalize_payload


class Phase5FGmailForwardTagsTests(unittest.TestCase):
    def test_gmail_forward_preserves_top_level_tags_into_metadata(self) -> None:
        normalized = normalize_payload(
            {
                "subject": "OpenAI Dev Newsletter",
                "from": "newsletter@updates.openai.com",
                "text": "Welcome to the OpenAI developer update.",
                "group": "reference",
                "tags": ["gmail", "email", "openai"],
                "metadata": {"email_from_name": "OpenAI"},
            },
            channel="gmail-forward",
        )

        self.assertEqual(normalized["type"], "email")
        self.assertEqual(normalized["source"], "gmail-forward")
        self.assertEqual(normalized["group"], "reference")
        self.assertEqual(normalized["metadata"]["tags"], ["gmail", "email", "openai"])
        self.assertEqual(normalized["metadata"]["group"], "reference")
        self.assertEqual(normalized["metadata"]["email_from"], "newsletter@updates.openai.com")


if __name__ == "__main__":
    unittest.main()
