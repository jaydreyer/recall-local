#!/usr/bin/env python3
"""Phase 5F regression tests for cloud-provider retry parity in llm_client."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import httpx

from scripts import llm_client


def _http_status_error(status_code: int, url: str) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", url)
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(f"status={status_code}", request=request, response=response)


class Phase5FLlmRetryParityTests(unittest.TestCase):
    def test_anthropic_retries_on_timeout(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "RECALL_GENERATE_RETRIES": "2",
                    "RECALL_GENERATE_BACKOFF_SECONDS": "0",
                    "ANTHROPIC_MODEL": "test-model",
                },
                clear=False,
            ),
            patch("scripts.llm_client._require_env", return_value="test-key"),
            patch("scripts.llm_client.time.sleep") as sleep_mock,
            patch(
                "scripts.llm_client.httpx.post",
                side_effect=[
                    httpx.ReadTimeout("timeout", request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")),
                    httpx.Response(
                        200,
                        request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
                        json={"content": [{"text": "ok"}]},
                    ),
                ],
            ) as post_mock,
        ):
            response = llm_client._anthropic_generate("prompt", "", 0.1, 128)  # noqa: SLF001

        self.assertEqual(response, "ok")
        self.assertEqual(post_mock.call_count, 2)
        sleep_mock.assert_called_once_with(0.0)

    def test_openai_retries_on_http_429(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "RECALL_GENERATE_RETRIES": "2",
                    "RECALL_GENERATE_BACKOFF_SECONDS": "0",
                    "OPENAI_MODEL": "test-model",
                },
                clear=False,
            ),
            patch("scripts.llm_client._require_env", return_value="test-key"),
            patch("scripts.llm_client.time.sleep") as sleep_mock,
            patch(
                "scripts.llm_client.httpx.post",
                side_effect=[
                    _http_status_error(429, "https://api.openai.com/v1/chat/completions"),
                    httpx.Response(
                        200,
                        request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions"),
                        json={"choices": [{"message": {"content": "ok"}}]},
                    ),
                ],
            ) as post_mock,
        ):
            response = llm_client._openai_generate("prompt", "system", 0.2, 256)  # noqa: SLF001

        self.assertEqual(response, "ok")
        self.assertEqual(post_mock.call_count, 2)
        sleep_mock.assert_called_once_with(0.0)

    def test_gemini_does_not_retry_on_http_401(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "RECALL_GENERATE_RETRIES": "3",
                    "RECALL_GENERATE_BACKOFF_SECONDS": "0",
                    "GEMINI_MODEL": "gemini-test",
                },
                clear=False,
            ),
            patch("scripts.llm_client._require_env", return_value="test-key"),
            patch("scripts.llm_client.time.sleep") as sleep_mock,
            patch(
                "scripts.llm_client.httpx.post",
                side_effect=[_http_status_error(401, "https://generativelanguage.googleapis.com/v1beta/models/gemini-test:generateContent")],
            ) as post_mock,
        ):
            with self.assertRaises(httpx.HTTPStatusError):
                llm_client._gemini_generate("prompt", "", 0.1, 128)  # noqa: SLF001

        self.assertEqual(post_mock.call_count, 1)
        sleep_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
