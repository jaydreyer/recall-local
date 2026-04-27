#!/usr/bin/env python3
"""Ingest resume content into Phase 6 `recall_resume` collection."""

from __future__ import annotations

import argparse
import os
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from scripts.llm_client import embed
from scripts.phase1.ingestion_pipeline import chunk_text, extract_text, load_settings, qdrant_client_from_env
from scripts.phase6 import setup_collections, storage
from scripts.shared_time import now_iso

ROOT = Path(__file__).resolve().parents[2]
RESUME_COLLECTION = setup_collections.COLLECTION_RESUME


def _derive_section(chunk: str) -> str:
    for line in chunk.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            return stripped.lstrip("# ").strip().lower() or "general"
        if stripped.isupper() and len(stripped) <= 80:
            return stripped.lower()
        return "general"
    return "general"


def _extract_text_from_source(*, file_path: Path | None, markdown_text: str | None) -> tuple[str, str, str]:
    if markdown_text is not None:
        text = markdown_text.strip()
        if not text:
            raise ValueError("Resume markdown is empty.")
        return text, "inline:resume-markdown", "resume.md"

    if file_path is None:
        raise ValueError("Either file_path or markdown_text is required.")

    extracted_text, source_ref, fallback_title = extract_text("file", str(file_path.expanduser()))
    title = fallback_title or file_path.name
    return extracted_text, source_ref, title


def _recreate_resume_collection(client) -> None:
    existing = {item.name for item in client.get_collections().collections}
    if RESUME_COLLECTION in existing:
        client.delete_collection(collection_name=RESUME_COLLECTION)
    setup_collections.ensure_collection(
        client=client,
        collection_name=RESUME_COLLECTION,
        vector_size=int(os.getenv("EMBEDDING_DIMENSION", "768")),
        payload_schema=setup_collections.RESUME_PAYLOAD_SCHEMA,
    )


def ingest_resume(
    *,
    file_path: Path | None = None,
    markdown_text: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    settings = load_settings()
    text, source_ref, source_name = _extract_text_from_source(file_path=file_path, markdown_text=markdown_text)
    chunks = chunk_text(
        text,
        max_tokens=settings.chunk_tokens,
        overlap_tokens=settings.chunk_overlap,
    )
    if not chunks:
        raise RuntimeError("No chunks generated from resume source.")

    conn = storage.connect_db()
    try:
        version = storage.next_resume_version(conn)
        ingested_at = now_iso()

        if not dry_run:
            client = qdrant_client_from_env(os.getenv("QDRANT_HOST", "http://localhost:6333"))
            _recreate_resume_collection(client)

            from qdrant_client import models

            points: list[Any] = []
            for index, chunk in enumerate(chunks):
                points.append(
                    models.PointStruct(
                        id=str(uuid.uuid4()),
                        vector=embed(chunk),
                        payload={
                            "chunk_text": chunk,
                            "section": _derive_section(chunk),
                            "version": version,
                            "ingested_at": ingested_at,
                            "chunk_index": index,
                            "source_name": source_name,
                            "source_ref": source_ref,
                        },
                    )
                )
            client.upsert(collection_name=RESUME_COLLECTION, points=points)
            storage.record_resume_version(
                conn,
                version=version,
                source_type="markdown" if markdown_text is not None else "file",
                source_path=source_ref,
                chunk_count=len(chunks),
                ingested_at=ingested_at,
            )

        return {
            "version": version,
            "chunks": len(chunks),
            "ingested_at": ingested_at,
            "source": source_ref,
            "dry_run": dry_run,
        }
    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest a resume into recall_resume collection.")
    parser.add_argument("--file", default=None, help="Path to resume source file (.md, .pdf, .docx, .txt).")
    parser.add_argument("--markdown", default=None, help="Inline markdown resume text.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and chunk without writing to Qdrant/SQLite.")
    return parser.parse_args()


def main() -> int:
    load_dotenv(ROOT / "docker" / ".env")
    load_dotenv(ROOT / "docker" / ".env.example")

    args = parse_args()
    file_path = Path(args.file).expanduser() if args.file else None
    result = ingest_resume(file_path=file_path, markdown_text=args.markdown, dry_run=args.dry_run)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
