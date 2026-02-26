#!/usr/bin/env python3
"""Phase 5B regression tests for group/tag metadata propagation and filtering."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from scripts.phase1.ingest_from_payload import payload_to_requests
from scripts.phase1.ingestion_pipeline import IngestRequest, _build_qdrant_points
from scripts.phase1 import retrieval


class _FakePointStruct:
    def __init__(self, *, id: str, vector: list[float], payload: dict[str, object]):
        self.id = id
        self.vector = vector
        self.payload = payload


class _FakeFieldCondition:
    def __init__(self, *, key: str, match: object):
        self.key = key
        self.match = match


class _FakeMatchAny:
    def __init__(self, *, any: list[str]):  # noqa: A002
        self.any = any


class _FakeMatchValue:
    def __init__(self, *, value: str):
        self.value = value


class _FakeFilter:
    def __init__(self, *, must: list[object]):
        self.must = must


class _FakeModels:
    PointStruct = _FakePointStruct
    FieldCondition = _FakeFieldCondition
    MatchAny = _FakeMatchAny
    MatchValue = _FakeMatchValue
    Filter = _FakeFilter


class _FakeLlmClient:
    @staticmethod
    def embed(_text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class _FakeLlmModule:
    embed = _FakeLlmClient.embed


class Phase5BMetadataModelTests(unittest.TestCase):
    def test_payload_to_requests_defaults_invalid_group_to_reference(self) -> None:
        requests = payload_to_requests(
            {
                "type": "text",
                "content": "hello world",
                "source": "webhook",
                "group": "unknown-group",
                "tags": ["phase5b", "test"],
            }
        )

        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].group, "reference")
        self.assertEqual(requests[0].tags, ["phase5b", "test"])

    def test_qdrant_payload_includes_group_tags_and_ingestion_channel(self) -> None:
        request = IngestRequest(
            source_type="text",
            content="hello world",
            source_channel="bookmarklet",
            group="job-search",
            tags=["alpha", "beta"],
            metadata={"title": "Example"},
        )

        def fake_require(module_name: str, _install_hint: str):
            if module_name == "scripts.llm_client":
                return _FakeLlmModule
            if module_name == "qdrant_client.models":
                return _FakeModels
            raise AssertionError(f"Unexpected module request: {module_name}")

        with patch("scripts.phase1.ingestion_pipeline._require_module", side_effect=fake_require):
            points = _build_qdrant_points(
                chunks=["chunk one"],
                doc_id="doc-001",
                title="Example",
                source_ref="inline:text",
                source_identity="inline:text",
                request=request,
                replaced_points=0,
            )

        self.assertEqual(len(points), 1)
        payload = points[0].payload
        self.assertEqual(payload["group"], "job-search")
        self.assertEqual(payload["tags"], ["alpha", "beta"])
        self.assertEqual(payload["ingestion_channel"], "bookmarklet")
        self.assertEqual(payload["metadata"]["group"], "job-search")
        self.assertEqual(payload["metadata"]["tags"], ["alpha", "beta"])
        self.assertEqual(payload["metadata"]["ingestion_channel"], "bookmarklet")

    def test_retrieval_filter_combines_group_and_tags(self) -> None:
        with patch("scripts.phase1.retrieval._import_qdrant_models", return_value=_FakeModels):
            query_filter = retrieval._build_query_filter(  # noqa: SLF001
                filter_group="job-search",
                filter_tags=["anthropic", "interview-prep"],
                filter_tag_mode="any",
            )

        self.assertIsNotNone(query_filter)
        self.assertEqual(len(query_filter.must), 2)
        first = query_filter.must[0]
        second = query_filter.must[1]
        self.assertEqual(first.key, "group")
        self.assertEqual(first.match.value, "job-search")
        self.assertEqual(second.key, "tags")
        self.assertEqual(second.match.any, ["anthropic", "interview-prep"])

    def test_retrieval_filter_all_mode_requires_each_tag(self) -> None:
        with patch("scripts.phase1.retrieval._import_qdrant_models", return_value=_FakeModels):
            query_filter = retrieval._build_query_filter(  # noqa: SLF001
                filter_group=None,
                filter_tags=["mistral", "job-posting"],
                filter_tag_mode="all",
            )

        self.assertIsNotNone(query_filter)
        self.assertEqual(len(query_filter.must), 2)
        self.assertEqual(query_filter.must[0].key, "tags")
        self.assertEqual(query_filter.must[0].match.any, ["mistral"])
        self.assertEqual(query_filter.must[1].key, "tags")
        self.assertEqual(query_filter.must[1].match.any, ["job-posting"])


if __name__ == "__main__":
    unittest.main()
