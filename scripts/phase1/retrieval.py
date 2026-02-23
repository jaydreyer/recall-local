#!/usr/bin/env python3
"""Workflow 02 retrieval helpers for Recall.local cited RAG."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase1.ingestion_pipeline import qdrant_client_from_env  # noqa: E402


@dataclass
class RetrievalSettings:
    qdrant_host: str
    qdrant_collection: str
    top_k: int
    min_score: float


@dataclass
class RetrievedChunk:
    doc_id: str
    chunk_id: str
    title: str
    source: str
    text: str
    score: float
    source_type: str
    ingestion_channel: str
    tags: list[str]


def load_settings() -> RetrievalSettings:
    load_dotenv(ROOT / "docker" / ".env")
    load_dotenv(ROOT / "docker" / ".env.example")

    top_k = int(os.getenv("RECALL_RAG_TOP_K", "5"))
    min_score = float(os.getenv("RECALL_RAG_MIN_SCORE", "0.2"))
    if top_k <= 0:
        raise ValueError("RECALL_RAG_TOP_K must be greater than 0")

    return RetrievalSettings(
        qdrant_host=os.getenv("QDRANT_HOST", "http://localhost:6333"),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "recall_docs"),
        top_k=top_k,
        min_score=min_score,
    )


def retrieve_chunks(
    query: str,
    *,
    top_k: int | None = None,
    min_score: float | None = None,
    filter_tags: list[str] | None = None,
) -> list[RetrievedChunk]:
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("Query must be non-empty")

    settings = load_settings()
    limit = settings.top_k if top_k is None else top_k
    threshold = settings.min_score if min_score is None else min_score
    normalized_tags = _normalize_filter_tags(filter_tags)
    if limit <= 0:
        raise ValueError("top_k must be greater than 0")

    llm_client = _import_llm_client()
    qdrant = qdrant_client_from_env(settings.qdrant_host)

    try:
        query_embedding = llm_client.embed(
            normalized_query,
            trace_metadata={
                "workflow": "workflow_02_rag_query",
                "operation": "query_embedding",
                "filter_tags": normalized_tags,
            },
        )
    except TypeError:
        query_embedding = llm_client.embed(normalized_query)
    points = _search_points(
        qdrant=qdrant,
        collection=settings.qdrant_collection,
        query_embedding=query_embedding,
        top_k=limit,
        min_score=threshold,
        filter_tags=normalized_tags,
    )

    chunks: list[RetrievedChunk] = []
    for point in points:
        payload = getattr(point, "payload", {}) or {}
        doc_id = str(payload.get("doc_id", "")).strip()
        chunk_id = str(payload.get("chunk_id", "")).strip()
        text = str(payload.get("text", "")).strip()
        if not doc_id or not chunk_id or not text:
            continue

        score = float(getattr(point, "score", 0.0) or 0.0)
        if score < threshold:
            continue

        chunks.append(
            RetrievedChunk(
                doc_id=doc_id,
                chunk_id=chunk_id,
                title=str(payload.get("title", "Untitled source")).strip() or "Untitled source",
                source=str(payload.get("source", "unknown")).strip() or "unknown",
                text=text,
                score=score,
                source_type=str(payload.get("source_type", "unknown")).strip() or "unknown",
                ingestion_channel=str(payload.get("ingestion_channel", "unknown")).strip() or "unknown",
                tags=_normalize_payload_tags(payload.get("tags")),
            )
        )

    return chunks


def _search_points(
    *,
    qdrant: Any,
    collection: str,
    query_embedding: list[float],
    top_k: int,
    min_score: float,
    filter_tags: list[str],
) -> list[Any]:
    query_filter = _build_tag_filter(filter_tags)

    if hasattr(qdrant, "search"):
        kwargs = {
            "collection_name": collection,
            "query_vector": query_embedding,
            "limit": top_k,
            "with_payload": True,
        }
        if query_filter is not None:
            kwargs["query_filter"] = query_filter
        try:
            return qdrant.search(score_threshold=min_score, **kwargs)
        except TypeError:
            if "query_filter" in kwargs:
                kwargs["filter"] = kwargs.pop("query_filter")
            return qdrant.search(**kwargs)

    if hasattr(qdrant, "query_points"):
        kwargs: dict[str, Any] = {
            "collection_name": collection,
            "query": query_embedding,
            "limit": top_k,
            "with_payload": True,
            "score_threshold": min_score,
        }
        if query_filter is not None:
            kwargs["query_filter"] = query_filter
        try:
            response = qdrant.query_points(**kwargs)
        except TypeError:
            if "query_filter" in kwargs:
                kwargs["filter"] = kwargs.pop("query_filter")
            response = qdrant.query_points(**kwargs)
        points = getattr(response, "points", None)
        if isinstance(points, list):
            return points
        return []

    raise RuntimeError("Unsupported qdrant-client version: no search/query_points method available.")


def _import_llm_client():
    try:
        from scripts import llm_client  # noqa: PLC0415
    except ModuleNotFoundError as exc:
        raise RuntimeError("Missing scripts.llm_client module. Ensure repository root is on PYTHONPATH.") from exc
    return llm_client


def _normalize_filter_tags(filter_tags: list[str] | None) -> list[str]:
    if not filter_tags:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in filter_tags:
        tag = str(raw).strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        normalized.append(tag)
    return normalized


def _normalize_payload_tags(value: Any) -> list[str]:
    if isinstance(value, list):
        tags: list[str] = []
        for item in value:
            tag = str(item).strip()
            if tag:
                tags.append(tag)
        return tags
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return []


def _build_tag_filter(filter_tags: list[str]):
    if not filter_tags:
        return None
    models = _import_qdrant_models()
    return models.Filter(
        must=[
            models.FieldCondition(
                key="tags",
                match=models.MatchAny(any=filter_tags),
            )
        ]
    )


def _import_qdrant_models():
    try:
        from qdrant_client import models  # noqa: PLC0415
    except ModuleNotFoundError as exc:
        raise RuntimeError("Missing qdrant-client models import. Install with: pip install -r requirements.txt") from exc
    return models


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retrieve top-k chunks from Qdrant for a query.")
    parser.add_argument("--query", required=True, help="User query to embed and retrieve against.")
    parser.add_argument("--top-k", type=int, default=None, help="Override retrieval top-k.")
    parser.add_argument("--min-score", type=float, default=None, help="Override minimum score threshold.")
    parser.add_argument(
        "--filter-tags",
        default="",
        help="Comma-separated tags for retrieval filtering (optional).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        chunks = retrieve_chunks(
            args.query,
            top_k=args.top_k,
            min_score=args.min_score,
            filter_tags=[part.strip() for part in args.filter_tags.split(",") if part.strip()],
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Retrieval failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps([asdict(chunk) for chunk in chunks], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
