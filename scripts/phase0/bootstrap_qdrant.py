#!/usr/bin/env python3
"""Create recall_docs collection in Qdrant if it does not exist."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from scripts.shared_qdrant import create_qdrant_client


def qdrant_client_from_env() -> QdrantClient:
    return create_qdrant_client(os.getenv("QDRANT_HOST"), client_cls=QdrantClient)


def main() -> None:
    load_dotenv("docker/.env")
    load_dotenv("docker/.env.example")

    collection = os.getenv("QDRANT_COLLECTION", "recall_docs")
    vector_size = int(os.getenv("EMBEDDING_DIMENSION", "768"))

    client = qdrant_client_from_env()
    existing = {item.name for item in client.get_collections().collections}

    if collection in existing:
        info = client.get_collection(collection)
        size = info.config.params.vectors.size
        print(f"Collection already exists: {collection} (dimension={size})")
        return

    client.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )
    print(f"Created collection: {collection} (dimension={vector_size})")


if __name__ == "__main__":
    main()
