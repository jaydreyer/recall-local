#!/usr/bin/env python3
"""Regression tests for meeting action items CLI helpers."""

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

from scripts.phase2.meeting_action_items import _load_transcript


class MeetingActionItemsCliTests(unittest.TestCase):
    def test_load_transcript_prefers_inline_transcript(self) -> None:
        args = argparse.Namespace(transcript="hello world", transcript_file=None)

        self.assertEqual(_load_transcript(args), "hello world")

    def test_load_transcript_reads_file_when_provided(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "transcript.txt"
            path.write_text("hello file\n", encoding="utf-8")
            args = argparse.Namespace(transcript=None, transcript_file=str(path))

            self.assertEqual(_load_transcript(args), "hello file")

    def test_load_transcript_raises_value_error_when_missing(self) -> None:
        args = argparse.Namespace(transcript=None, transcript_file=None)

        with self.assertRaisesRegex(ValueError, "Either transcript or transcript_file is required."):
            _load_transcript(args)


if __name__ == "__main__":
    unittest.main()
