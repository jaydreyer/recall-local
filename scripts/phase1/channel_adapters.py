#!/usr/bin/env python3
"""Normalize channel-specific payloads into the unified ingestion schema."""

from __future__ import annotations

import re
from typing import Any

URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def normalize_payload(raw_payload: dict[str, Any], channel: str) -> dict[str, Any]:
    normalized_channel = channel.strip().lower()
    if normalized_channel == "webhook":
        return _normalize_webhook(raw_payload)
    if normalized_channel == "ios-share":
        return _normalize_ios_share(raw_payload)
    if normalized_channel == "gmail-forward":
        return _normalize_gmail_forward(raw_payload)
    raise ValueError(f"Unsupported channel: {channel}")


def _normalize_webhook(raw_payload: dict[str, Any]) -> dict[str, Any]:
    if _is_unified_payload(raw_payload):
        payload = dict(raw_payload)
        payload["source"] = str(payload.get("source", "webhook")).strip() or "webhook"
        return payload

    # Fallback inference for webhook callers that post raw content without type.
    content = raw_payload.get("content")
    if content is None:
        raise ValueError("Webhook payload requires either unified shape or a 'content' field.")

    source_type = "text"
    if isinstance(content, str) and URL_RE.match(content.strip()):
        source_type = "url"

    return {
        "type": source_type,
        "content": content,
        "source": str(raw_payload.get("source", "webhook")).strip() or "webhook",
        "metadata": _ensure_metadata(raw_payload.get("metadata")),
    }


def _normalize_ios_share(raw_payload: dict[str, Any]) -> dict[str, Any]:
    if _is_unified_payload(raw_payload):
        payload = dict(raw_payload)
        payload["source"] = str(payload.get("source", "ios-shortcut")).strip() or "ios-shortcut"
        return payload

    shared_url = _first_non_empty(
        raw_payload.get("shared_url"),
        raw_payload.get("sharedUrl"),
        raw_payload.get("url"),
    )
    shared_text = _first_non_empty(
        raw_payload.get("shared_text"),
        raw_payload.get("sharedText"),
        raw_payload.get("text"),
    )

    content: str | None = None
    source_type = "text"
    if shared_url and URL_RE.match(shared_url):
        content = shared_url
        source_type = "url"
    elif shared_text:
        content = shared_text
        source_type = "url" if URL_RE.match(shared_text) else "text"

    if not content:
        raise ValueError("iOS share payload requires shared_url/url or shared_text/text.")

    metadata = _ensure_metadata(raw_payload.get("metadata"))
    title = _first_non_empty(raw_payload.get("title"), raw_payload.get("page_title"))
    if title and "title" not in metadata:
        metadata["title"] = title

    tags = raw_payload.get("tags")
    if tags and "tags" not in metadata:
        metadata["tags"] = tags

    return {
        "type": source_type,
        "content": content,
        "source": "ios-shortcut",
        "metadata": metadata,
    }


def _normalize_gmail_forward(raw_payload: dict[str, Any]) -> dict[str, Any]:
    if _is_unified_payload(raw_payload):
        payload = dict(raw_payload)
        payload["source"] = str(payload.get("source", "gmail-forward")).strip() or "gmail-forward"
        return payload

    metadata = _ensure_metadata(raw_payload.get("metadata"))
    subject = _first_non_empty(raw_payload.get("subject"), raw_payload.get("emailSubject"))
    sender = _first_non_empty(raw_payload.get("from"), raw_payload.get("sender"))
    message_id = _first_non_empty(raw_payload.get("messageId"), raw_payload.get("message_id"))
    body = _first_non_empty(
        raw_payload.get("text"),
        raw_payload.get("plainText"),
        raw_payload.get("body"),
        raw_payload.get("message"),
    )
    if not body:
        html = _first_non_empty(raw_payload.get("html"))
        if html:
            body = re.sub(r"<[^>]+>", " ", html)
            body = re.sub(r"\s+", " ", body).strip()

    attachment_paths = _collect_attachment_paths(raw_payload)
    if not body and not attachment_paths:
        raise ValueError("Gmail payload has no body text and no attachment paths.")

    if subject and "title" not in metadata:
        metadata["title"] = subject
    if sender:
        metadata["email_from"] = sender
    if message_id:
        metadata["email_message_id"] = message_id

    content: dict[str, Any] = {
        "subject": subject or "",
        "body": body or "",
        "attachment_paths": attachment_paths,
    }

    return {
        "type": "email",
        "content": content,
        "source": "gmail-forward",
        "metadata": metadata,
    }


def _collect_attachment_paths(raw_payload: dict[str, Any]) -> list[str]:
    paths: list[str] = []

    direct_paths = raw_payload.get("attachment_paths")
    if isinstance(direct_paths, list):
        for item in direct_paths:
            if isinstance(item, str) and item.strip():
                paths.append(item.strip())

    attachments = raw_payload.get("attachments")
    if isinstance(attachments, list):
        for item in attachments:
            if not isinstance(item, dict):
                continue
            for key in ("path", "filePath", "filepath"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    paths.append(value.strip())
                    break

    unique_paths: list[str] = []
    seen: set[str] = set()
    for path in paths:
        if path not in seen:
            unique_paths.append(path)
            seen.add(path)
    return unique_paths


def _is_unified_payload(payload: dict[str, Any]) -> bool:
    return isinstance(payload.get("type"), str) and "content" in payload


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _ensure_metadata(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}
