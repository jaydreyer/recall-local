#!/usr/bin/env python3
"""Workflow 02 retrieval helpers for Recall.local cited RAG."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase1.group_model import normalize_group
from scripts.phase1.ingestion_pipeline import qdrant_client_from_env  # noqa: E402

QUOTED_PHRASE_PATTERN = re.compile(r'["“”](.+?)["“”]')
MIN_TITLE_HINT_TOKENS = 3
TITLE_LOOKUP_SCROLL_LIMIT = 256
TITLE_LOOKUP_MAX_POINTS = 2500
TITLE_MATCHED_DOCUMENT_MIN_CHUNKS = 20


@dataclass
class RetrievalSettings:
    qdrant_host: str
    qdrant_collection: str
    top_k: int
    min_score: float
    retrieval_mode: str
    hybrid_alpha: float
    hybrid_candidate_multiplier: int
    reranker_enabled: bool
    reranker_weight: float


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
    group: str
    tags: list[str]
    dense_score: float | None = None
    sparse_score: float | None = None
    hybrid_score: float | None = None
    rerank_score: float | None = None
    title_match_score: float | None = None
    chunk_index: int | None = None


def load_settings() -> RetrievalSettings:
    load_dotenv(ROOT / "docker" / ".env")
    load_dotenv(ROOT / "docker" / ".env.example")

    top_k = int(os.getenv("RECALL_RAG_TOP_K", "5"))
    min_score = float(os.getenv("RECALL_RAG_MIN_SCORE", "0.2"))
    retrieval_mode = _normalize_retrieval_mode(os.getenv("RECALL_RAG_RETRIEVAL_MODE", "vector"))
    hybrid_alpha = _clamp_float(
        os.getenv("RECALL_RAG_HYBRID_ALPHA", "0.65"),
        minimum=0.0,
        maximum=1.0,
    )
    hybrid_candidate_multiplier = max(int(os.getenv("RECALL_RAG_HYBRID_CANDIDATE_MULTIPLIER", "4")), 1)
    reranker_enabled = _parse_bool(os.getenv("RECALL_RAG_ENABLE_RERANK", "false"))
    reranker_weight = _clamp_float(
        os.getenv("RECALL_RAG_RERANK_WEIGHT", "0.35"),
        minimum=0.0,
        maximum=1.0,
    )

    if top_k <= 0:
        raise ValueError("RECALL_RAG_TOP_K must be greater than 0")

    return RetrievalSettings(
        qdrant_host=os.getenv("QDRANT_HOST", "http://localhost:6333"),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "recall_docs"),
        top_k=top_k,
        min_score=min_score,
        retrieval_mode=retrieval_mode,
        hybrid_alpha=hybrid_alpha,
        hybrid_candidate_multiplier=hybrid_candidate_multiplier,
        reranker_enabled=reranker_enabled,
        reranker_weight=reranker_weight,
    )


def retrieve_chunks(
    query: str,
    *,
    top_k: int | None = None,
    min_score: float | None = None,
    filter_tags: list[str] | None = None,
    filter_tag_mode: str | None = None,
    filter_group: str | None = None,
    retrieval_mode: str | None = None,
    hybrid_alpha: float | None = None,
    enable_reranker: bool | None = None,
    reranker_weight: float | None = None,
) -> list[RetrievedChunk]:
    normalized_query = query.strip()
    if not normalized_query:
        raise ValueError("Query must be non-empty")

    settings = load_settings()
    limit = settings.top_k if top_k is None else top_k
    threshold = settings.min_score if min_score is None else min_score
    normalized_tags = _normalize_filter_tags(filter_tags)
    normalized_tag_mode = _normalize_filter_tag_mode(filter_tag_mode)
    normalized_group = _normalize_filter_group(filter_group)
    active_retrieval_mode = _normalize_retrieval_mode(retrieval_mode or settings.retrieval_mode)
    active_hybrid_alpha = (
        settings.hybrid_alpha
        if hybrid_alpha is None
        else _clamp_float(str(hybrid_alpha), minimum=0.0, maximum=1.0)
    )
    active_reranker = settings.reranker_enabled if enable_reranker is None else bool(enable_reranker)
    active_reranker_weight = (
        settings.reranker_weight
        if reranker_weight is None
        else _clamp_float(str(reranker_weight), minimum=0.0, maximum=1.0)
    )

    if limit <= 0:
        raise ValueError("top_k must be greater than 0")

    title_hints = _extract_title_hints(normalized_query)
    retrieval_query = _focused_retrieval_query(normalized_query, title_hints=title_hints)
    candidate_limit = limit
    if active_retrieval_mode == "hybrid" or active_reranker:
        candidate_limit = max(limit * settings.hybrid_candidate_multiplier, limit)
    if title_hints:
        candidate_limit = max(candidate_limit, limit * 8, 24)
    search_threshold = threshold if active_retrieval_mode == "vector" else -1.0

    llm_client = _import_llm_client()
    qdrant = qdrant_client_from_env(settings.qdrant_host)

    try:
        query_embedding = llm_client.embed(
            retrieval_query,
            trace_metadata={
                "workflow": "workflow_02_rag_query",
                "operation": "query_embedding",
                "retrieval_query": retrieval_query,
                "filter_tags": normalized_tags,
                "filter_tag_mode": normalized_tag_mode,
                "filter_group": normalized_group,
                "retrieval_mode": active_retrieval_mode,
                "reranker_enabled": active_reranker,
            },
        )
    except TypeError:
        query_embedding = llm_client.embed(retrieval_query)

    points = _search_points(
        qdrant=qdrant,
        collection=settings.qdrant_collection,
        query_embedding=query_embedding,
        top_k=candidate_limit,
        min_score=search_threshold,
        filter_tags=normalized_tags,
        filter_tag_mode=normalized_tag_mode,
        filter_group=normalized_group,
    )

    chunks: list[RetrievedChunk] = []
    for point in points:
        payload = getattr(point, "payload", {}) or {}
        doc_id = str(payload.get("doc_id", "")).strip()
        chunk_id = str(payload.get("chunk_id", "")).strip()
        text = str(payload.get("text", "")).strip()
        if not doc_id or not chunk_id or not text:
            continue

        dense_score = float(getattr(point, "score", 0.0) or 0.0)
        chunks.append(
            RetrievedChunk(
                doc_id=doc_id,
                chunk_id=chunk_id,
                title=str(payload.get("title", "Untitled source")).strip() or "Untitled source",
                source=str(payload.get("source", "unknown")).strip() or "unknown",
                text=text,
                score=dense_score,
                source_type=str(payload.get("source_type", "unknown")).strip() or "unknown",
                ingestion_channel=str(payload.get("ingestion_channel", "unknown")).strip() or "unknown",
                group=normalize_group(payload.get("group")),
                tags=_normalize_payload_tags(payload.get("tags")),
                dense_score=dense_score,
                chunk_index=_coerce_chunk_index(payload.get("chunk_index")),
            )
        )

    if active_retrieval_mode == "hybrid":
        chunks = _apply_hybrid_ranking(chunks, query=retrieval_query, alpha=active_hybrid_alpha)
        chunks = [item for item in chunks if item.score >= threshold]
    else:
        chunks = [item for item in chunks if item.score >= threshold]

    if active_reranker and chunks:
        chunks = _apply_heuristic_reranker(
            chunks,
            query=normalized_query,
            reranker_weight=active_reranker_weight,
            title_hints=title_hints,
        )

    if title_hints:
        if len(title_hints) > 1:
            looked_up = _lookup_documents_by_title_hints(
                qdrant=qdrant,
                collection=settings.qdrant_collection,
                title_hints=title_hints,
                filter_tags=normalized_tags,
                filter_tag_mode=normalized_tag_mode,
                filter_group=normalized_group,
                limit=limit,
            )
            if looked_up:
                chunks = looked_up
        elif chunks and _has_strong_title_match(chunks):
            chunks = _expand_title_matched_document(
                qdrant=qdrant,
                collection=settings.qdrant_collection,
                chunks=chunks,
                filter_tags=normalized_tags,
                filter_tag_mode=normalized_tag_mode,
                filter_group=normalized_group,
                limit=limit,
            )
        else:
            looked_up = _lookup_document_by_title_hints(
                qdrant=qdrant,
                collection=settings.qdrant_collection,
                title_hints=title_hints,
                filter_tags=normalized_tags,
                filter_tag_mode=normalized_tag_mode,
                filter_group=normalized_group,
                limit=limit,
            )
            if looked_up:
                chunks = looked_up

    return chunks[:limit]


def _search_points(
    *,
    qdrant: Any,
    collection: str,
    query_embedding: list[float],
    top_k: int,
    min_score: float,
    filter_tags: list[str],
    filter_tag_mode: str,
    filter_group: str | None,
) -> list[Any]:
    query_filter = _build_query_filter(
        filter_tags=filter_tags,
        filter_tag_mode=filter_tag_mode,
        filter_group=filter_group,
    )

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


def _apply_hybrid_ranking(chunks: list[RetrievedChunk], *, query: str, alpha: float) -> list[RetrievedChunk]:
    if not chunks:
        return []

    dense_values = [float(item.dense_score if item.dense_score is not None else item.score) for item in chunks]
    dense_norms = _minmax_normalize(dense_values)
    query_tokens = set(_tokenize(query))

    for index, item in enumerate(chunks):
        chunk_tokens = _tokenize(f"{item.title} {item.text}")
        sparse_score = _token_overlap_score(query_tokens, chunk_tokens)
        hybrid_score = (alpha * dense_norms[index]) + ((1.0 - alpha) * sparse_score)
        item.sparse_score = sparse_score
        item.hybrid_score = hybrid_score
        item.score = hybrid_score

    return sorted(
        chunks,
        key=lambda item: (
            item.score,
            item.dense_score if item.dense_score is not None else item.score,
        ),
        reverse=True,
    )


def _apply_heuristic_reranker(
    chunks: list[RetrievedChunk],
    *,
    query: str,
    reranker_weight: float,
    title_hints: list[str] | None = None,
) -> list[RetrievedChunk]:
    if not chunks:
        return []

    query_tokens = _tokenize(query)
    query_token_set = set(query_tokens)
    query_bigrams = set(_bigrams(query_tokens))
    normalized_title_hints = title_hints or []

    for item in chunks:
        item_tokens = _tokenize(f"{item.title} {item.text}")
        item_token_set = set(item_tokens)
        item_bigrams = set(_bigrams(item_tokens))

        token_overlap = _jaccard(query_token_set, item_token_set)
        phrase_overlap = _jaccard(query_bigrams, item_bigrams) if query_bigrams else 0.0
        lexical_relevance = (0.7 * token_overlap) + (0.3 * phrase_overlap)
        title_match_score = _title_match_score(item=item, title_hints=normalized_title_hints)
        item.title_match_score = title_match_score
        lexical_with_title = lexical_relevance if title_match_score <= 0 else max(lexical_relevance, title_match_score)
        base_score = item.score
        rerank_score = ((1.0 - reranker_weight) * base_score) + (reranker_weight * lexical_with_title)
        if title_match_score > 0:
            rerank_score += 0.35 * title_match_score
        item.rerank_score = rerank_score
        item.score = rerank_score

    return sorted(
        chunks,
        key=lambda item: (
            item.score,
            item.title_match_score if item.title_match_score is not None else 0.0,
            item.hybrid_score if item.hybrid_score is not None else item.score,
        ),
        reverse=True,
    )


def _extract_title_hints(query: str) -> list[str]:
    hints: list[str] = []
    for match in QUOTED_PHRASE_PATTERN.findall(query):
        cleaned = " ".join(match.strip().split())
        if len(_tokenize(cleaned)) >= MIN_TITLE_HINT_TOKENS:
            hints.append(cleaned)
    return hints


def _focused_retrieval_query(query: str, *, title_hints: list[str]) -> str:
    if title_hints:
        return " ".join(title_hints)
    return query


def _title_match_score(*, item: RetrievedChunk, title_hints: list[str]) -> float:
    if not title_hints:
        return 0.0

    title_normalized = " ".join(item.title.lower().split())
    source_normalized = " ".join(item.source.lower().split())
    best_score = 0.0
    for hint in title_hints:
        normalized_hint = " ".join(hint.lower().split())
        if not normalized_hint:
            continue
        if normalized_hint == title_normalized:
            return 1.0
        if normalized_hint in title_normalized:
            best_score = max(best_score, 0.95)
            continue
        if normalized_hint in source_normalized:
            best_score = max(best_score, 0.85)
            continue

        hint_tokens = set(_tokenize(normalized_hint))
        title_tokens = set(_tokenize(title_normalized))
        if hint_tokens and title_tokens:
            overlap = len(hint_tokens.intersection(title_tokens)) / len(hint_tokens)
            if overlap >= 0.8:
                best_score = max(best_score, 0.75)
            elif overlap >= 0.5:
                best_score = max(best_score, 0.55)
    return best_score


def _expand_title_matched_document(
    *,
    qdrant: Any,
    collection: str,
    chunks: list[RetrievedChunk],
    filter_tags: list[str],
    filter_tag_mode: str,
    filter_group: str | None,
    limit: int,
) -> list[RetrievedChunk]:
    if not chunks:
        return chunks

    best = chunks[0]
    if not _has_strong_title_match(chunks):
        return chunks

    expanded = _load_chunks_for_doc_id(
        qdrant=qdrant,
        collection=collection,
        doc_id=best.doc_id,
        filter_tags=filter_tags,
        filter_tag_mode=filter_tag_mode,
        filter_group=filter_group,
        limit=max(limit, TITLE_MATCHED_DOCUMENT_MIN_CHUNKS),
    )
    if not expanded:
        return chunks

    for item in expanded:
        item.title_match_score = best.title_match_score
        if item.doc_id == best.doc_id:
            item.score += 0.25

    return sorted(
        expanded,
        key=lambda item: (
            item.chunk_index if item.chunk_index is not None else 999999,
            -(item.title_match_score if item.title_match_score is not None else 0.0),
        ),
    )


def _has_strong_title_match(chunks: list[RetrievedChunk]) -> bool:
    if not chunks:
        return False
    return (chunks[0].title_match_score or 0.0) >= 0.75


def _lookup_document_by_title_hints(
    *,
    qdrant: Any,
    collection: str,
    title_hints: list[str],
    filter_tags: list[str],
    filter_tag_mode: str,
    filter_group: str | None,
    limit: int,
) -> list[RetrievedChunk]:
    candidate_doc_id = _find_best_doc_id_by_title_hints(
        qdrant=qdrant,
        collection=collection,
        title_hints=title_hints,
        filter_tags=filter_tags,
        filter_tag_mode=filter_tag_mode,
        filter_group=filter_group,
    )
    if not candidate_doc_id:
        return []

    expanded = _load_chunks_for_doc_id(
        qdrant=qdrant,
        collection=collection,
        doc_id=candidate_doc_id,
        filter_tags=filter_tags,
        filter_tag_mode=filter_tag_mode,
        filter_group=filter_group,
        limit=max(limit, TITLE_MATCHED_DOCUMENT_MIN_CHUNKS),
    )
    if not expanded:
        return []

    for item in expanded:
        item.title_match_score = _title_match_score(item=item, title_hints=title_hints)
        item.score = 1.0 + (item.title_match_score or 0.0)
    return expanded


def _lookup_documents_by_title_hints(
    *,
    qdrant: Any,
    collection: str,
    title_hints: list[str],
    filter_tags: list[str],
    filter_tag_mode: str,
    filter_group: str | None,
    limit: int,
) -> list[RetrievedChunk]:
    if not title_hints:
        return []

    per_doc_limit = max(limit, 8)
    per_doc_chunks: list[list[RetrievedChunk]] = []
    seen_doc_ids: set[str] = set()

    for index, hint in enumerate(title_hints):
        candidate_doc_id = _find_best_doc_id_by_title_hints(
            qdrant=qdrant,
            collection=collection,
            title_hints=[hint],
            filter_tags=filter_tags,
            filter_tag_mode=filter_tag_mode,
            filter_group=filter_group,
        )
        if not candidate_doc_id or candidate_doc_id in seen_doc_ids:
            continue

        seen_doc_ids.add(candidate_doc_id)
        expanded = _load_chunks_for_doc_id(
            qdrant=qdrant,
            collection=collection,
            doc_id=candidate_doc_id,
            filter_tags=filter_tags,
            filter_tag_mode=filter_tag_mode,
            filter_group=filter_group,
            limit=per_doc_limit,
        )
        if not expanded:
            continue

        doc_boost = max(0.0, 0.2 - (index * 0.05))
        for item in expanded:
            item.title_match_score = _title_match_score(item=item, title_hints=[hint])
            item.score = 1.0 + (item.title_match_score or 0.0) + doc_boost
        per_doc_chunks.append(
            sorted(
                expanded,
                key=lambda item: item.chunk_index if item.chunk_index is not None else 999999,
            )
        )

    return _interleave_ranked_chunks(per_doc_chunks)


def _interleave_ranked_chunks(per_doc_chunks: list[list[RetrievedChunk]]) -> list[RetrievedChunk]:
    merged: list[RetrievedChunk] = []
    max_depth = max((len(items) for items in per_doc_chunks), default=0)
    for depth in range(max_depth):
        for items in per_doc_chunks:
            if depth < len(items):
                merged.append(items[depth])
    return merged


def _find_best_doc_id_by_title_hints(
    *,
    qdrant: Any,
    collection: str,
    title_hints: list[str],
    filter_tags: list[str],
    filter_tag_mode: str,
    filter_group: str | None,
) -> str | None:
    if not title_hints:
        return None

    query_filter = _build_query_filter(
        filter_tags=filter_tags,
        filter_tag_mode=filter_tag_mode,
        filter_group=filter_group,
    )
    kwargs: dict[str, Any] = {
        "collection_name": collection,
        "limit": TITLE_LOOKUP_SCROLL_LIMIT,
        "with_payload": True,
        "with_vectors": False,
    }
    offset: Any = None
    scanned = 0
    best_doc_id: str | None = None
    best_score = 0.0
    seen_docs: set[str] = set()

    while scanned < TITLE_LOOKUP_MAX_POINTS:
        request_kwargs = dict(kwargs)
        if offset is not None:
            request_kwargs["offset"] = offset
        if query_filter is not None:
            request_kwargs["query_filter"] = query_filter
        try:
            response = qdrant.scroll(**request_kwargs)
        except Exception as exc:
            if "query_filter" not in str(exc):
                return None
            request_kwargs.pop("query_filter", None)
            if query_filter is not None:
                request_kwargs["scroll_filter"] = query_filter
            response = qdrant.scroll(**request_kwargs)

        if isinstance(response, tuple) and len(response) == 2:
            points, offset = response
        else:
            points = getattr(response, "points", None)
            offset = getattr(response, "next_page_offset", None)

        if not isinstance(points, list) or not points:
            break

        for point in points:
            scanned += 1
            payload = getattr(point, "payload", {}) or {}
            doc_id = str(payload.get("doc_id", "")).strip()
            if not doc_id or doc_id in seen_docs:
                continue
            seen_docs.add(doc_id)
            candidate = RetrievedChunk(
                doc_id=doc_id,
                chunk_id=str(payload.get("chunk_id", "")).strip() or "unknown",
                title=str(payload.get("title", "Untitled source")).strip() or "Untitled source",
                source=str(payload.get("source", "unknown")).strip() or "unknown",
                text=str(payload.get("text", "")).strip(),
                score=0.0,
                source_type=str(payload.get("source_type", "unknown")).strip() or "unknown",
                ingestion_channel=str(payload.get("ingestion_channel", "unknown")).strip() or "unknown",
                group=normalize_group(payload.get("group")),
                tags=_normalize_payload_tags(payload.get("tags")),
                chunk_index=_coerce_chunk_index(payload.get("chunk_index")),
            )
            match_score = _title_match_score(item=candidate, title_hints=title_hints)
            if match_score > best_score:
                best_score = match_score
                best_doc_id = doc_id

        if offset is None:
            break

    if best_score < 0.75:
        return None
    return best_doc_id


def _load_chunks_for_doc_id(
    *,
    qdrant: Any,
    collection: str,
    doc_id: str,
    filter_tags: list[str],
    filter_tag_mode: str,
    filter_group: str | None,
    limit: int,
) -> list[RetrievedChunk]:
    if not doc_id:
        return []

    models = _import_qdrant_models()
    must_conditions = [
        models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id)),
    ]
    extra_filter = _build_query_filter(
        filter_tags=filter_tags,
        filter_tag_mode=filter_tag_mode,
        filter_group=filter_group,
    )
    if extra_filter is not None:
        extra_must = getattr(extra_filter, "must", None)
        if isinstance(extra_must, list):
            must_conditions.extend(extra_must)

    query_filter = models.Filter(must=must_conditions)
    kwargs: dict[str, Any] = {
        "collection_name": collection,
        "limit": max(limit, 1),
        "with_payload": True,
        "with_vectors": False,
    }

    response = None
    try:
        response = qdrant.scroll(query_filter=query_filter, **kwargs)
    except Exception as exc:
        if "query_filter" not in str(exc):
            return []
        response = qdrant.scroll(scroll_filter=query_filter, **kwargs)

    if isinstance(response, tuple) and len(response) == 2:
        points = response[0]
    else:
        points = getattr(response, "points", None)

    if not isinstance(points, list):
        return []

    chunks: list[RetrievedChunk] = []
    for point in points:
        payload = getattr(point, "payload", {}) or {}
        text = str(payload.get("text", "")).strip()
        chunk_id = str(payload.get("chunk_id", "")).strip()
        if not text or not chunk_id:
            continue
        chunks.append(
            RetrievedChunk(
                doc_id=doc_id,
                chunk_id=chunk_id,
                title=str(payload.get("title", "Untitled source")).strip() or "Untitled source",
                source=str(payload.get("source", "unknown")).strip() or "unknown",
                text=text,
                score=1.0,
                source_type=str(payload.get("source_type", "unknown")).strip() or "unknown",
                ingestion_channel=str(payload.get("ingestion_channel", "unknown")).strip() or "unknown",
                group=normalize_group(payload.get("group")),
                tags=_normalize_payload_tags(payload.get("tags")),
                chunk_index=_coerce_chunk_index(payload.get("chunk_index")),
            )
        )
    return sorted(chunks, key=lambda item: item.chunk_index if item.chunk_index is not None else 999999)


def _coerce_chunk_index(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _minmax_normalize(values: list[float]) -> list[float]:
    if not values:
        return []
    lower = min(values)
    upper = max(values)
    if abs(upper - lower) < 1e-9:
        return [1.0] * len(values)
    return [(value - lower) / (upper - lower) for value in values]


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _bigrams(tokens: list[str]) -> list[str]:
    if len(tokens) < 2:
        return []
    return [f"{tokens[index]} {tokens[index + 1]}" for index in range(len(tokens) - 1)]


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    intersection = len(left.intersection(right))
    union = len(left.union(right))
    if union == 0:
        return 0.0
    return intersection / union


def _token_overlap_score(query_tokens: set[str], chunk_tokens: list[str]) -> float:
    if not query_tokens:
        return 0.0
    chunk_set = set(chunk_tokens)
    if not chunk_set:
        return 0.0
    overlap = query_tokens.intersection(chunk_set)
    return len(overlap) / len(query_tokens)


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


def _build_query_filter(*, filter_tags: list[str], filter_tag_mode: str = "any", filter_group: str | None):
    if not filter_tags and not filter_group:
        return None
    normalized_tag_mode = _normalize_filter_tag_mode(filter_tag_mode)
    models = _import_qdrant_models()
    must_conditions = []
    if filter_group:
        must_conditions.append(
            models.FieldCondition(
                key="group",
                match=models.MatchValue(value=filter_group),
            )
        )
    if filter_tags:
        if normalized_tag_mode == "all":
            must_conditions.extend(
                models.FieldCondition(
                    key="tags",
                    match=models.MatchAny(any=[tag]),
                )
                for tag in filter_tags
            )
        else:
            must_conditions.append(
                models.FieldCondition(
                    key="tags",
                    match=models.MatchAny(any=filter_tags),
                )
            )
    return models.Filter(
        must=must_conditions
    )


def _normalize_filter_group(filter_group: str | None) -> str | None:
    if filter_group is None:
        return None
    raw = str(filter_group).strip()
    if not raw:
        return None
    return normalize_group(raw)


def _normalize_filter_tag_mode(filter_tag_mode: str | None) -> str:
    raw = str(filter_tag_mode or "").strip().lower()
    if raw in {"", "any", "or"}:
        return "any"
    if raw in {"all", "and", "must"}:
        return "all"
    raise ValueError(f"Unsupported filter_tag_mode: {filter_tag_mode}")


def _import_qdrant_models():
    try:
        from qdrant_client import models  # noqa: PLC0415
    except ModuleNotFoundError as exc:
        raise RuntimeError("Missing qdrant-client models import. Install with: pip install -r requirements.txt") from exc
    return models


def _normalize_retrieval_mode(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"", "default", "vector", "dense"}:
        return "vector"
    if normalized in {"hybrid", "fusion"}:
        return "hybrid"
    raise ValueError(f"Unsupported retrieval mode: {value}")


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {"1", "true", "yes", "on"}


def _clamp_float(value: str, *, minimum: float, maximum: float) -> float:
    parsed = float(value)
    return max(minimum, min(maximum, parsed))


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
    parser.add_argument(
        "--filter-group",
        default="",
        help="Optional group filter (`job-search|learning|project|reference|meeting`).",
    )
    parser.add_argument(
        "--filter-tag-mode",
        default="any",
        help="Tag filter mode: any|all.",
    )
    parser.add_argument(
        "--retrieval-mode",
        default=None,
        help="Retrieval mode override: vector|hybrid.",
    )
    parser.add_argument(
        "--hybrid-alpha",
        type=float,
        default=None,
        help="Hybrid fusion weight for dense score [0..1].",
    )
    parser.add_argument(
        "--enable-reranker",
        action="store_true",
        help="Enable heuristic reranker stage after retrieval.",
    )
    parser.add_argument(
        "--reranker-weight",
        type=float,
        default=None,
        help="Heuristic reranker blend weight [0..1].",
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
            filter_tag_mode=args.filter_tag_mode,
            filter_group=args.filter_group or None,
            retrieval_mode=args.retrieval_mode,
            hybrid_alpha=args.hybrid_alpha,
            enable_reranker=args.enable_reranker if args.enable_reranker else None,
            reranker_weight=args.reranker_weight,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Retrieval failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps([asdict(chunk) for chunk in chunks], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
