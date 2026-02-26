#!/usr/bin/env python3
"""Regression tests for ingestion chunking with special-token-like text."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts.phase1 import ingestion_pipeline


class _EncoderWithOrdinary:
    def __init__(self) -> None:
        self.last_text = ""

    def encode(self, _text: str, **_kwargs: object) -> list[int]:
        raise AssertionError("encode() should not be called when encode_ordinary() is available")

    def encode_ordinary(self, text: str) -> list[int]:
        self.last_text = text
        return [11, 22, 33]

    def decode(self, token_ids: list[int]) -> str:
        return f"tokens:{'-'.join(str(item) for item in token_ids)}"


class _EncoderWithoutOrdinary:
    def __init__(self) -> None:
        self.last_kwargs: dict[str, object] = {}

    def encode(self, _text: str, **kwargs: object) -> list[int]:
        self.last_kwargs = kwargs
        return [1, 2, 3]

    def decode(self, token_ids: list[int]) -> str:
        return f"tokens:{len(token_ids)}"


class Phase5FIngestSpecialTokensTests(unittest.TestCase):
    def test_token_windows_uses_encode_ordinary_when_available(self) -> None:
        encoder = _EncoderWithOrdinary()
        with patch("scripts.phase1.ingestion_pipeline._load_encoder", return_value=encoder):
            windows = ingestion_pipeline._token_windows(  # noqa: SLF001
                "hello <|endofprompt|> world",
                max_tokens=8,
                overlap_tokens=2,
            )

        self.assertEqual(encoder.last_text, "hello <|endofprompt|> world")
        self.assertEqual(windows, ["tokens:11-22-33"])

    def test_token_windows_disables_disallowed_special_for_encode(self) -> None:
        encoder = _EncoderWithoutOrdinary()
        with patch("scripts.phase1.ingestion_pipeline._load_encoder", return_value=encoder):
            windows = ingestion_pipeline._token_windows(  # noqa: SLF001
                "hello <|endofprompt|> world",
                max_tokens=8,
                overlap_tokens=2,
            )

        self.assertEqual(encoder.last_kwargs, {"disallowed_special": ()})
        self.assertEqual(windows, ["tokens:3"])


if __name__ == "__main__":
    unittest.main()
