#!/usr/bin/env python3
"""Unit tests for optional OpenTelemetry/Honeycomb config resolution."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from scripts.phase1 import observability


class ObservabilityTests(unittest.TestCase):
    def test_resolve_exporter_config_uses_explicit_otlp_env(self) -> None:
        env = {
            "OTEL_SERVICE_NAME": "recall-bridge-test",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "https://api.honeycomb.io",
            "OTEL_EXPORTER_OTLP_HEADERS": "x-honeycomb-team=test-key",
        }
        with patch.dict(os.environ, env, clear=False):
            config = observability._resolve_exporter_config_from_env()

        self.assertIsNotNone(config)
        assert config is not None
        self.assertEqual(config.service_name, "recall-bridge-test")
        self.assertEqual(config.endpoint, "https://api.honeycomb.io/v1/traces")
        self.assertEqual(config.headers["x-honeycomb-team"], "test-key")

    def test_resolve_exporter_config_falls_back_to_honeycomb_env(self) -> None:
        env = {
            "HONEYCOMB_API_KEY": "abc123",
            "HONEYCOMB_API_ENDPOINT": "https://api.honeycomb.io",
            "HONEYCOMB_DATASET": "recall-classic",
        }
        with patch.dict(os.environ, env, clear=False):
            config = observability._resolve_exporter_config_from_env()

        self.assertIsNotNone(config)
        assert config is not None
        self.assertEqual(config.endpoint, "https://api.honeycomb.io/v1/traces")
        self.assertEqual(config.headers["x-honeycomb-team"], "abc123")
        self.assertEqual(config.headers["x-honeycomb-dataset"], "recall-classic")

    def test_resolve_exporter_config_requires_endpoint_and_headers(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = observability._resolve_exporter_config_from_env()

        self.assertIsNone(config)
