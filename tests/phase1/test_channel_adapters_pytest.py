#!/usr/bin/env python3
"""Regression coverage for channel adapter normalization paths."""

from __future__ import annotations

import pytest

from scripts.phase1.channel_adapters import normalize_payload


def test_normalize_webhook_infers_text_payload_and_metadata() -> None:
    payload = normalize_payload(
        {
            "text": "Hello from webhook",
            "group": "job-search",
            "tags": ["phase6"],
            "source_key": "source-123",
        },
        "webhook",
    )

    assert payload["type"] == "text"
    assert payload["content"] == "Hello from webhook"
    assert payload["group"] == "job-search"
    assert payload["source_key"] == "source-123"
    assert payload["metadata"]["tags"] == ["phase6"]


def test_normalize_bookmarklet_sets_source() -> None:
    payload = normalize_payload({"url": "https://example.com/post"}, "bookmarklet")

    assert payload["type"] == "url"
    assert payload["source"] == "bookmarklet"


def test_normalize_ios_share_prefers_shared_url() -> None:
    payload = normalize_payload({"shared_url": "https://example.com", "title": "Example"}, "ios-share")

    assert payload["type"] == "url"
    assert payload["content"] == "https://example.com"
    assert payload["metadata"]["title"] == "Example"


def test_normalize_gmail_forward_collects_body_and_attachments() -> None:
    payload = normalize_payload(
        {
            "subject": "Job lead",
            "from": "person@example.com",
            "html": "<p>Hello <b>world</b></p>",
            "attachments": [{"path": "/tmp/resume.pdf"}],
        },
        "gmail-forward",
    )

    assert payload["type"] == "email"
    assert payload["content"]["body"] == "Hello world"
    assert payload["content"]["attachment_paths"] == ["/tmp/resume.pdf"]
    assert payload["metadata"]["email_from"] == "person@example.com"


def test_normalize_gmail_forward_requires_body_or_attachments() -> None:
    with pytest.raises(ValueError, match="no body text and no attachment paths"):
        normalize_payload({"subject": "Empty"}, "gmail-forward")
