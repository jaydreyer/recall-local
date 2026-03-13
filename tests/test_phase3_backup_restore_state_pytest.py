#!/usr/bin/env python3
"""Pytest coverage for Phase 3 backup/restore helpers."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.phase3 import backup_restore_state


class _FakeDistance:
    COSINE = "COSINE"
    DOT = "DOT"
    EUCLID = "EUCLID"
    MANHATTAN = "MANHATTAN"


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (None, None),
        ("Distance.COSINE", "cosine"),
        ("DOT", "dot"),
    ],
)
def test_distance_to_str_normalizes_supported_values(raw_value: object, expected: str | None) -> None:
    assert backup_restore_state._distance_to_str(raw_value) == expected


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("cosine", _FakeDistance.COSINE),
        ("dot", _FakeDistance.DOT),
        ("euclid", _FakeDistance.EUCLID),
        ("manhattan", _FakeDistance.MANHATTAN),
    ],
)
def test_distance_to_enum_maps_known_metrics(raw_value: str, expected: str) -> None:
    fake_models = SimpleNamespace(Distance=_FakeDistance)
    assert backup_restore_state._distance_to_enum(fake_models, raw_value) == expected


def test_distance_to_enum_rejects_unknown_metric() -> None:
    fake_models = SimpleNamespace(Distance=_FakeDistance)
    with pytest.raises(ValueError, match="Unsupported Qdrant distance metric"):
        backup_restore_state._distance_to_enum(fake_models, "weird-metric")


def test_infer_vector_size_from_jsonl_handles_plain_and_named_vectors(tmp_path: Path) -> None:
    points_file = tmp_path / "points.jsonl"
    points_file.write_text(
        "\n".join(
            [
                json.dumps({"id": "job-1", "vector": [0.1, 0.2, 0.3]}),
                json.dumps({"id": "job-2", "vector": {"default": [0.9, 0.8]}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert backup_restore_state._infer_vector_size_from_jsonl(points_file) == 3


def test_prepare_backup_paths_creates_expected_structure(tmp_path: Path) -> None:
    paths = backup_restore_state._prepare_backup_paths(output_dir=tmp_path, backup_name="manual-smoke")

    assert paths.root == tmp_path / "manual-smoke"
    assert paths.sqlite_copy == tmp_path / "manual-smoke" / "sqlite" / "recall.db"
    assert paths.qdrant_points == tmp_path / "manual-smoke" / "qdrant" / "points.jsonl"
    assert paths.sqlite_copy.parent.exists()
    assert paths.qdrant_points.parent.exists()
