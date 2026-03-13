#!/usr/bin/env python3
"""Shared Qdrant client helpers."""

from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlparse

DEFAULT_QDRANT_URL = "http://localhost:6333"


def create_qdrant_client(
    host_url: str | None = None,
    *,
    client_cls: type[Any] | Callable[..., Any],
    default_port: int = 6333,
) -> Any:
    """Build a Qdrant client from either a URL or bare host."""
    normalized = str(host_url or DEFAULT_QDRANT_URL).strip() or DEFAULT_QDRANT_URL
    parsed = urlparse(normalized)
    if parsed.scheme:
        return client_cls(url=normalized)
    return client_cls(host=normalized, port=default_port)
