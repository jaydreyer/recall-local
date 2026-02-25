#!/usr/bin/env python3
"""Phase 5E.1 regression checks for Gmail extension wiring."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT_DIR / "chrome-extension" / "manifest.json"
GMAIL_SCRIPT_PATH = ROOT_DIR / "chrome-extension" / "gmail.js"
POPUP_SCRIPT_PATH = ROOT_DIR / "chrome-extension" / "popup.js"


class Phase5E1GmailExtensionTests(unittest.TestCase):
    def test_manifest_registers_gmail_content_script(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        content_scripts = manifest.get("content_scripts", [])
        gmail_entries = [
            entry
            for entry in content_scripts
            if "https://mail.google.com/*" in entry.get("matches", [])
        ]
        self.assertEqual(len(gmail_entries), 1)
        gmail_entry = gmail_entries[0]
        self.assertIn("gmail.js", gmail_entry.get("js", []))
        self.assertEqual(gmail_entry.get("run_at"), "document_idle")

    def test_gmail_script_has_dom_resilience_and_sender_prefill_logic(self) -> None:
        source = GMAIL_SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn("MutationObserver", source)
        self.assertIn("setInterval(() =>", source)
        self.assertIn('div[role="toolbar"]', source)
        self.assertIn("deriveGroupFromSender", source)
        self.assertIn("email_senders", source)
        self.assertIn("recall_open_popup_from_gmail", source)
        self.assertIn("recall_gmail_prefill", source)

    def test_popup_consumes_gmail_prefill_and_routes_channel(self) -> None:
        source = POPUP_SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn("loadAndConsumeGmailPrefill", source)
        self.assertIn("GMAIL_PREFILL_STORAGE_KEY", source)
        self.assertIn('channel: state.gmailPrefill ? "gmail-forward" : "bookmarklet"', source)
        self.assertIn("Gmail prefill loaded for", source)


if __name__ == "__main__":
    unittest.main()
