#!/usr/bin/env python3
"""Create and validate Phase 6 Qdrant collections."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from qdrant_client import QdrantClient

from scripts.shared_qdrant import create_qdrant_client

COLLECTION_JOBS = "recall_jobs"
COLLECTION_RESUME = "recall_resume"
DEFAULT_VECTOR_SIZE = 768

JOBS_PAYLOAD_SCHEMA: dict[str, str] = {
    "title": "keyword",
    "company": "keyword",
    "company_normalized": "keyword",
    "company_tier": "integer",
    "location": "keyword",
    "location_type": "keyword",
    "url": "keyword",
    "source": "keyword",
    "description": "text",
    "salary_min": "integer",
    "salary_max": "integer",
    "date_posted": "datetime",
    "discovered_at": "datetime",
    "evaluated_at": "datetime",
    "search_query": "keyword",
    "status": "keyword",
    "fit_score": "integer",
    "score_rationale": "text",
    "matching_skills": "json",
    "gaps": "json",
    "application_tips": "text",
    "cover_letter_angle": "text",
    "applied": "bool",
    "applied_at": "datetime",
    "notes": "text",
    "dismissed": "bool",
}

RESUME_PAYLOAD_SCHEMA: dict[str, str] = {
    "chunk_text": "text",
    "section": "keyword",
    "version": "integer",
    "ingested_at": "datetime",
}


@dataclass
class CollectionStatus:
    name: str
    created: bool
    indexed_fields: list[str]
    skipped_fields: list[str]


def qdrant_client_from_env():
    return create_qdrant_client(os.getenv("QDRANT_HOST"), client_cls=QdrantClient)


def _existing_collection_names(client) -> set[str]:
    response = client.get_collections()
    collections = getattr(response, "collections", None) or []
    names: set[str] = set()
    for item in collections:
        name = getattr(item, "name", None)
        if isinstance(name, str) and name:
            names.add(name)
    return names


def _schema_to_qdrant_type(schema_type: str):
    from qdrant_client.models import PayloadSchemaType

    normalized = schema_type.strip().lower()
    mapping = {
        "keyword": PayloadSchemaType.KEYWORD,
        "integer": PayloadSchemaType.INTEGER,
        "text": PayloadSchemaType.TEXT,
        "datetime": PayloadSchemaType.DATETIME,
        "bool": PayloadSchemaType.BOOL,
    }
    return mapping.get(normalized)


def _create_payload_indexes(*, client, collection_name: str, payload_schema: dict[str, str]) -> tuple[list[str], list[str]]:
    indexed: list[str] = []
    skipped: list[str] = []
    for field_name, field_type in payload_schema.items():
        qdrant_type = _schema_to_qdrant_type(field_type)
        if qdrant_type is None:
            skipped.append(field_name)
            continue
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=qdrant_type,
            )
            indexed.append(field_name)
        except TypeError:
            client.create_payload_index(collection_name, field_name, qdrant_type)
            indexed.append(field_name)
        except Exception:
            # Indexes are best-effort. Existing index or unsupported runtime versions should not fail setup.
            skipped.append(field_name)
    return indexed, skipped


def ensure_collection(
    *,
    client,
    collection_name: str,
    vector_size: int,
    payload_schema: dict[str, str],
) -> CollectionStatus:
    from qdrant_client.models import Distance, VectorParams

    names = _existing_collection_names(client)
    created = collection_name not in names
    if created:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
    indexed, skipped = _create_payload_indexes(
        client=client,
        collection_name=collection_name,
        payload_schema=payload_schema,
    )
    return CollectionStatus(
        name=collection_name,
        created=created,
        indexed_fields=indexed,
        skipped_fields=skipped,
    )


def ensure_phase6_collections(*, client=None, vector_size: int | None = None) -> list[CollectionStatus]:
    resolved_client = client or qdrant_client_from_env()
    resolved_vector_size = int(vector_size or os.getenv("EMBEDDING_DIMENSION", str(DEFAULT_VECTOR_SIZE)))
    return [
        ensure_collection(
            client=resolved_client,
            collection_name=COLLECTION_JOBS,
            vector_size=resolved_vector_size,
            payload_schema=JOBS_PAYLOAD_SCHEMA,
        ),
        ensure_collection(
            client=resolved_client,
            collection_name=COLLECTION_RESUME,
            vector_size=resolved_vector_size,
            payload_schema=RESUME_PAYLOAD_SCHEMA,
        ),
    ]


def main() -> int:
    load_dotenv("docker/.env")
    load_dotenv("docker/.env.example")

    statuses = ensure_phase6_collections()
    for status in statuses:
        state = "created" if status.created else "already-exists"
        print(f"[{state}] {status.name}")
        print(f"  indexed: {', '.join(status.indexed_fields) if status.indexed_fields else '(none)'}")
        if status.skipped_fields:
            print(f"  skipped: {', '.join(status.skipped_fields)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
