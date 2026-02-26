#!/usr/bin/env python3
"""Phase 1 Workflow 01 ingestion pipeline for Recall.local."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import shutil
import sqlite3
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*_args, **_kwargs):  # type: ignore[no-redef]
        return False

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase1.group_model import DEFAULT_GROUP, normalize_group

HEADING_RE = re.compile(r"^(#{1,6}\s+.+|[A-Z][A-Z0-9 _:/-]{4,})$")
TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "utm_campaign",
    "utm_content",
    "utm_id",
    "utm_medium",
    "utm_source",
    "utm_term",
}

DEFAULT_URL_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class Settings:
    qdrant_host: str
    qdrant_collection: str
    db_path: Path
    incoming_dir: Path
    processed_dir: Path
    chunk_tokens: int
    chunk_overlap: int


@dataclass
class IngestRequest:
    source_type: str
    content: Any
    source_channel: str = "manual"
    title: str | None = None
    group: str = DEFAULT_GROUP
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    replace_existing: bool = False
    source_key: str | None = None


@dataclass
class IngestResult:
    run_id: str
    ingest_id: str
    doc_id: str
    source_type: str
    source_ref: str
    title: str
    source_identity: str
    chunks_created: int
    moved_to: str | None
    replace_existing: bool
    replaced_points: int
    replacement_status: str
    latency_ms: int
    status: str


def load_settings() -> Settings:
    load_dotenv(ROOT / "docker" / ".env")
    load_dotenv(ROOT / "docker" / ".env.example")

    chunk_tokens = int(os.getenv("RECALL_CHUNK_TOKENS", "400"))
    chunk_overlap = int(os.getenv("RECALL_CHUNK_OVERLAP", "60"))
    if chunk_overlap >= chunk_tokens:
        raise ValueError("RECALL_CHUNK_OVERLAP must be smaller than RECALL_CHUNK_TOKENS")

    return Settings(
        qdrant_host=os.getenv("QDRANT_HOST", "http://localhost:6333"),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "recall_docs"),
        db_path=Path(os.getenv("RECALL_DB_PATH", str(ROOT / "data" / "recall.db"))),
        incoming_dir=Path(os.getenv("DATA_INCOMING", str(ROOT / "data" / "incoming"))),
        processed_dir=Path(os.getenv("DATA_PROCESSED", str(ROOT / "data" / "processed"))),
        chunk_tokens=chunk_tokens,
        chunk_overlap=chunk_overlap,
    )


def ingest_request(request: IngestRequest, *, dry_run: bool = False) -> IngestResult:
    settings = load_settings()
    if not dry_run:
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        settings.processed_dir.mkdir(parents=True, exist_ok=True)

    started_at = _now_iso()
    started_perf = time.perf_counter()
    run_id = uuid.uuid4().hex
    ingest_id = uuid.uuid4().hex
    doc_id = uuid.uuid4().hex

    conn: sqlite3.Connection | None = None
    if not dry_run:
        conn = sqlite3.connect(settings.db_path)
        _ensure_ingestion_log_columns(conn)
        _insert_run_started(conn, run_id, request, started_at)
        _insert_ingestion_started(conn, ingest_id, request, started_at)

    try:
        extracted_text, source_ref, fallback_title = extract_text(
            request.source_type,
            request.content,
        )
        title = request.title or fallback_title or "Untitled source"
        source_identity = resolve_source_identity(
            request=request,
            source_ref=source_ref,
        )
        chunks = chunk_text(
            extracted_text,
            max_tokens=settings.chunk_tokens,
            overlap_tokens=settings.chunk_overlap,
        )
        if not chunks:
            raise RuntimeError("No chunks produced from source content")

        moved_to: str | None = None
        replaced_points = 0
        replacement_status = "skipped"
        if not dry_run:
            qdrant = qdrant_client_from_env(settings.qdrant_host)
            if request.replace_existing:
                replaced_points = _replace_existing_source_points(
                    qdrant=qdrant,
                    collection_name=settings.qdrant_collection,
                    source_identity=source_identity,
                )
                replacement_status = "applied"
            points = _build_qdrant_points(
                chunks=chunks,
                doc_id=doc_id,
                title=title,
                source_ref=source_ref,
                source_identity=source_identity,
                request=request,
                replaced_points=replaced_points,
            )
            qdrant.upsert(collection_name=settings.qdrant_collection, points=points)
            moved_to = maybe_move_to_processed(
                settings=settings,
                request=request,
                doc_id=doc_id,
            )
        elif request.replace_existing:
            replacement_status = "dry_run"

        ended_at = _now_iso()
        latency_ms = int((time.perf_counter() - started_perf) * 1000)
        status = "dry_run" if dry_run else "completed"

        if conn is not None:
            _mark_run_completed(
                conn=conn,
                run_id=run_id,
                ended_at=ended_at,
                latency_ms=latency_ms,
                output_path=moved_to,
            )
            _mark_ingestion_completed(
                conn=conn,
                ingest_id=ingest_id,
                ended_at=ended_at,
                source_ref=source_ref,
                doc_id=doc_id,
                chunks_created=len(chunks),
            )

        return IngestResult(
            run_id=run_id,
            ingest_id=ingest_id,
            doc_id=doc_id,
            source_type=request.source_type,
            source_ref=source_ref,
            title=title,
            source_identity=source_identity,
            chunks_created=len(chunks),
            moved_to=moved_to,
            replace_existing=request.replace_existing,
            replaced_points=replaced_points,
            replacement_status=replacement_status,
            latency_ms=latency_ms,
            status=status,
        )
    except Exception:
        ended_at = _now_iso()
        latency_ms = int((time.perf_counter() - started_perf) * 1000)
        if conn is not None:
            _mark_run_failed(conn=conn, run_id=run_id, ended_at=ended_at, latency_ms=latency_ms)
            _mark_ingestion_failed(conn=conn, ingest_id=ingest_id, ended_at=ended_at)
        raise
    finally:
        if conn is not None:
            conn.close()


def extract_text(source_type: str, content: Any) -> tuple[str, str, str]:
    normalized = source_type.strip().lower()
    if normalized == "file":
        file_path = Path(str(content)).expanduser()
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        text = extract_text_from_file(file_path)
        return text, str(file_path.resolve()), file_path.name

    if normalized == "url":
        url = str(content).strip()
        text = extract_text_from_url(url)
        host = urlparse(url).netloc or "web source"
        return text, url, host

    if normalized == "gdoc":
        return _extract_text_from_gdoc_content(content)

    if normalized == "text":
        text = str(content).strip()
        if not text:
            raise ValueError("Text content is empty")
        return text, "inline:text", "Inline text"

    if normalized == "email":
        text = str(content).strip()
        if not text:
            raise ValueError("Email body is empty")
        return text, "email:body", "Email body"

    raise ValueError(f"Unsupported source_type: {source_type}")


def extract_text_from_file(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return _extract_text_from_pdf(file_path)
    if suffix == ".docx":
        return _extract_text_from_docx(file_path)

    raw = file_path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    cleaned = text.strip()
    if not cleaned:
        raise ValueError(f"No readable text extracted from {file_path}")
    return cleaned


def extract_text_from_url(url: str) -> str:
    httpx = _require_module("httpx", "pip install -r requirements.txt")
    trafilatura = _require_module("trafilatura", "pip install -r requirements.txt")

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Unsupported URL scheme for ingestion: {url}")

    verify_tls = _bool_env("RECALL_URL_VERIFY_TLS", default=True)
    allow_insecure_fallback = _bool_env("RECALL_URL_ALLOW_INSECURE_FALLBACK", default=False)
    allow_reader_proxy = _bool_env("RECALL_URL_ALLOW_READER_PROXY", default=True)

    try:
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=30,
            verify=verify_tls,
            headers=DEFAULT_URL_FETCH_HEADERS,
        )
        response.raise_for_status()
        downloaded = response.text
    except Exception as exc:  # noqa: BLE001
        if verify_tls and allow_insecure_fallback and _is_tls_verify_error(exc):
            response = httpx.get(
                url,
                follow_redirects=True,
                timeout=30,
                verify=False,
                headers=DEFAULT_URL_FETCH_HEADERS,
            )
            response.raise_for_status()
            downloaded = response.text
        elif allow_reader_proxy and _is_http_status_error(exc, status_code=403):
            proxy_url = _reader_proxy_url(url)
            response = httpx.get(
                proxy_url,
                follow_redirects=True,
                timeout=45,
                verify=verify_tls,
                headers=DEFAULT_URL_FETCH_HEADERS,
            )
            response.raise_for_status()
            downloaded = response.text
        else:
            raise

    extracted = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
    )
    if not extracted:
        extracted = re.sub(r"<[^>]+>", " ", downloaded)

    cleaned = re.sub(r"\n{3,}", "\n\n", extracted).strip()
    if not cleaned:
        raise ValueError(f"No readable content extracted from URL: {url}")
    return cleaned


def _extract_text_from_gdoc_content(content: Any) -> tuple[str, str, str]:
    gdoc_url: str | None = None
    gdoc_id: str | None = None
    gdoc_title: str | None = None

    if isinstance(content, dict):
        gdoc_text = _first_non_empty(
            content.get("text"),
            content.get("document_text"),
            content.get("body"),
            content.get("content"),
        )
        gdoc_url = _first_non_empty(
            content.get("url"),
            content.get("document_url"),
            content.get("source_url"),
        )
        gdoc_id = _first_non_empty(
            content.get("doc_id"),
            content.get("document_id"),
            content.get("id"),
        )
        gdoc_title = _first_non_empty(content.get("title"), content.get("name"))
        if gdoc_text:
            source_ref = gdoc_url or _gdoc_url_from_id(gdoc_id) or f"gdoc:{gdoc_id or 'inline'}"
            title = gdoc_title or (f"Google Doc {gdoc_id}" if gdoc_id else "Google Doc")
            return gdoc_text, source_ref, title
    else:
        content_str = str(content).strip()
        if not content_str:
            raise ValueError("Google Doc content is empty")
        if _looks_like_url(content_str):
            gdoc_url = content_str
        else:
            gdoc_id = content_str

    candidate_url = gdoc_url or _gdoc_export_url_from_id(gdoc_id)
    if not candidate_url:
        raise ValueError(
            "Google Doc payload must include URL, doc id, or extracted text. "
            "Preferred payload: {type:'gdoc', content:{url|doc_id|text}}."
        )

    text = extract_text_from_url(candidate_url)
    source_ref = gdoc_url or _gdoc_url_from_id(gdoc_id) or candidate_url
    title = gdoc_title or (f"Google Doc {gdoc_id}" if gdoc_id else "Google Doc")
    return text, source_ref, title


def _gdoc_export_url_from_id(doc_id: str | None) -> str | None:
    normalized = (doc_id or "").strip()
    if not normalized:
        return None
    return f"https://docs.google.com/document/d/{normalized}/export?format=txt"


def _gdoc_url_from_id(doc_id: str | None) -> str | None:
    normalized = (doc_id or "").strip()
    if not normalized:
        return None
    return f"https://docs.google.com/document/d/{normalized}/edit"


def _extract_text_from_pdf(file_path: Path) -> str:
    pdfplumber = _require_module("pdfplumber", "pip install -r requirements.txt")
    pages: list[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = (page.extract_text() or "").strip()
            if page_text:
                pages.append(page_text)
    text = "\n\n".join(pages).strip()
    if not text:
        raise ValueError(f"No readable text extracted from PDF: {file_path}")
    return text


def _extract_text_from_docx(file_path: Path) -> str:
    docx_module = _require_module("docx", "pip install -r requirements.txt")
    document = docx_module.Document(str(file_path))

    blocks: list[str] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            blocks.append(text)

    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                blocks.append(" | ".join(cells))

    text = "\n\n".join(blocks).strip()
    if not text:
        raise ValueError(f"No readable text extracted from DOCX: {file_path}")
    return text


def chunk_text(text: str, *, max_tokens: int, overlap_tokens: int) -> list[str]:
    sections = _split_into_sections(text)
    chunks: list[str] = []
    for section in sections:
        chunks.extend(_token_windows(section, max_tokens=max_tokens, overlap_tokens=overlap_tokens))
    return [chunk for chunk in chunks if chunk.strip()]


def _split_into_sections(text: str) -> list[str]:
    sections: list[str] = []
    current_heading: str | None = None
    current_body: list[str] = []

    def flush() -> None:
        if not current_body:
            return
        body = "\n".join(current_body).strip()
        if not body:
            return
        if current_heading:
            sections.append(f"{current_heading}\n{body}")
        else:
            sections.append(body)

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if current_body and current_body[-1] != "":
                current_body.append("")
            continue

        if HEADING_RE.match(line):
            flush()
            current_body = []
            current_heading = line
            continue

        current_body.append(line)

    flush()
    return sections or [text.strip()]


def _token_windows(text: str, *, max_tokens: int, overlap_tokens: int) -> list[str]:
    encoder = _load_encoder()
    if encoder is None:
        return _character_windows(text, max_chars=max_tokens * 4, overlap_chars=overlap_tokens * 4)

    token_ids = _encode_tokens(encoder, text)
    if not token_ids:
        return []

    step = max_tokens - overlap_tokens
    if step <= 0:
        step = max_tokens

    windows: list[str] = []
    for start in range(0, len(token_ids), step):
        window = token_ids[start : start + max_tokens]
        if not window:
            break
        windows.append(encoder.decode(window).strip())
        if start + max_tokens >= len(token_ids):
            break
    return windows


def _encode_tokens(encoder: Any, text: str) -> list[int]:
    encode_ordinary = getattr(encoder, "encode_ordinary", None)
    if callable(encode_ordinary):
        return encode_ordinary(text)
    try:
        return encoder.encode(text, disallowed_special=())
    except TypeError:
        return encoder.encode(text)


def _character_windows(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    if max_chars <= 0:
        return []
    step = max_chars - overlap_chars
    if step <= 0:
        step = max_chars

    windows: list[str] = []
    for start in range(0, len(text), step):
        window = text[start : start + max_chars].strip()
        if window:
            windows.append(window)
        if start + max_chars >= len(text):
            break
    return windows


def _load_encoder():
    try:
        tiktoken = _require_module("tiktoken", "pip install -r requirements.txt")
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


def qdrant_client_from_env(host_url: str):
    qdrant_module = _require_module("qdrant_client", "pip install -r requirements.txt")
    QdrantClient = qdrant_module.QdrantClient
    parsed = urlparse(host_url)
    if parsed.scheme:
        return QdrantClient(url=host_url)
    return QdrantClient(host=host_url, port=6333)


def _build_qdrant_points(
    *,
    chunks: Iterable[str],
    doc_id: str,
    title: str,
    source_ref: str,
    source_identity: str,
    request: IngestRequest,
    replaced_points: int,
) -> list[Any]:
    llm_client = _require_module("scripts.llm_client", "pip install -r requirements.txt")
    models_module = _require_module("qdrant_client.models", "pip install -r requirements.txt")
    PointStruct = models_module.PointStruct

    points: list[Any] = []
    created_at = _now_iso()

    for index, chunk in enumerate(chunks):
        chunk_id = f"{doc_id}:{index:04d}"
        embedding = llm_client.embed(chunk)
        metadata = dict(request.metadata)
        group_candidate = request.group
        metadata_group = metadata.get("group")
        if (
            isinstance(metadata_group, str)
            and metadata_group.strip()
            and (not group_candidate or normalize_group(group_candidate) == DEFAULT_GROUP)
        ):
            group_candidate = metadata_group
        group = normalize_group(group_candidate)
        tags = [str(tag).strip() for tag in request.tags if str(tag).strip()]
        metadata["source_identity"] = source_identity
        metadata["group"] = group
        metadata["tags"] = tags
        metadata["ingestion_channel"] = request.source_channel
        metadata["replacement"] = {
            "requested": request.replace_existing,
            "deleted_points": replaced_points,
        }
        payload = {
            "source": source_ref,
            "source_identity": source_identity,
            "source_type": request.source_type,
            "doc_id": doc_id,
            "chunk_id": chunk_id,
            "title": title,
            "created_at": created_at,
            "group": group,
            "tags": tags,
            "ingestion_channel": request.source_channel,
            "text": chunk,
            "metadata": metadata,
        }
        points.append(PointStruct(id=str(uuid.uuid4()), vector=embedding, payload=payload))

    return points


def _require_module(module_name: str, install_hint: str):
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"Missing dependency '{module_name}'. Install with: {install_hint}") from exc


def resolve_source_identity(*, request: IngestRequest, source_ref: str) -> str:
    explicit_source_key = _first_non_empty(
        request.source_key,
        request.metadata.get("source_key") if isinstance(request.metadata, dict) else None,
        request.metadata.get("canonical_source_key") if isinstance(request.metadata, dict) else None,
        request.metadata.get("source_identity") if isinstance(request.metadata, dict) else None,
    )
    if explicit_source_key:
        return explicit_source_key

    normalized_source_type = request.source_type.strip().lower()
    if normalized_source_type in {"url", "gdoc"}:
        return _canonicalize_url(source_ref)

    if normalized_source_type == "file":
        source_path = Path(source_ref).expanduser()
        if source_path.exists():
            return str(source_path.resolve())
        return source_ref

    if request.replace_existing and normalized_source_type in {"text", "email"}:
        raise ValueError(
            "replace_existing=true for text/email requires source_key (or metadata.source_key) "
            "to avoid replacing unrelated records."
        )

    return source_ref


def _canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return url.strip()

    filtered_pairs: list[tuple[str, str]] = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in TRACKING_QUERY_KEYS:
            continue
        filtered_pairs.append((key, value))
    filtered_pairs.sort(key=lambda item: (item[0], item[1]))

    normalized_path = re.sub(r"/+$", "", parsed.path) or "/"
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=normalized_path,
        params="",
        query=urlencode(filtered_pairs, doseq=True),
        fragment="",
    )
    return urlunparse(normalized)


def _replace_existing_source_points(*, qdrant: Any, collection_name: str, source_identity: str) -> int:
    models_module = _require_module("qdrant_client.models", "pip install -r requirements.txt")
    source_filter = _build_source_identity_filter(models_module=models_module, source_identity=source_identity)

    before_count = _count_points(qdrant=qdrant, collection_name=collection_name, source_filter=source_filter)
    if before_count == 0:
        return 0

    filter_selector_cls = getattr(models_module, "FilterSelector", None)
    points_selector = (
        filter_selector_cls(filter=source_filter)
        if filter_selector_cls is not None
        else source_filter
    )

    try:
        qdrant.delete(collection_name=collection_name, points_selector=points_selector, wait=True)
    except TypeError:
        qdrant.delete(collection_name=collection_name, points_selector=points_selector)

    after_count = _count_points(qdrant=qdrant, collection_name=collection_name, source_filter=source_filter)
    if before_count < 0 or after_count < 0:
        return max(before_count, 0)
    return max(before_count - after_count, 0)


def _count_points(*, qdrant: Any, collection_name: str, source_filter: Any) -> int:
    try:
        response = qdrant.count(collection_name=collection_name, count_filter=source_filter, exact=True)
    except TypeError:
        try:
            response = qdrant.count(collection_name=collection_name, filter=source_filter, exact=True)
        except TypeError:
            response = qdrant.count(collection_name=collection_name, count_filter=source_filter)
    except Exception:
        return -1

    if hasattr(response, "count"):
        try:
            return int(response.count)
        except (TypeError, ValueError):
            return -1
    if isinstance(response, dict):
        try:
            return int(response.get("count", -1))
        except (TypeError, ValueError):
            return -1
    return -1


def _build_source_identity_filter(*, models_module: Any, source_identity: str):
    return models_module.Filter(
        must=[
            models_module.FieldCondition(
                key="source_identity",
                match=models_module.MatchValue(value=source_identity),
            )
        ]
    )


def maybe_move_to_processed(*, settings: Settings, request: IngestRequest, doc_id: str) -> str | None:
    if not _bool_env("RECALL_MOVE_INCOMING_TO_PROCESSED", default=True):
        return None

    if request.source_type != "file":
        return None

    source_file = Path(str(request.content)).expanduser()
    if not source_file.exists():
        return None

    source_resolved = source_file.resolve()
    incoming_resolved = settings.incoming_dir.resolve()
    if not _is_relative_to(source_resolved, incoming_resolved):
        return None

    destination = settings.processed_dir / f"{doc_id}_{source_file.name}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_file), str(destination))
    return str(destination.resolve())


def _is_relative_to(path: Path, possible_parent: Path) -> bool:
    try:
        path.relative_to(possible_parent)
        return True
    except ValueError:
        return False


def _insert_run_started(conn: sqlite3.Connection, run_id: str, request: IngestRequest, started_at: str) -> None:
    input_hash = hashlib.sha256(
        f"{request.source_type}|{json.dumps(request.content, sort_keys=True, default=str)}".encode("utf-8")
    ).hexdigest()
    conn.execute(
        """
        INSERT INTO runs (run_id, workflow, status, started_at, input_hash)
        VALUES (?, ?, 'started', ?, ?)
        """,
        (run_id, "workflow_01_ingestion", started_at, input_hash),
    )
    conn.commit()


def _ensure_ingestion_log_columns(conn: sqlite3.Connection) -> None:
    columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(ingestion_log)").fetchall()}
    if not columns:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ingestion_log (
                ingest_id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_ref TEXT,
                channel TEXT NOT NULL,
                doc_id TEXT,
                chunks_created INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                timestamp TEXT NOT NULL,
                group_name TEXT,
                tags_json TEXT
            )
            """
        )
        conn.commit()
        return
    if "group_name" not in columns:
        conn.execute("ALTER TABLE ingestion_log ADD COLUMN group_name TEXT")
    if "tags_json" not in columns:
        conn.execute("ALTER TABLE ingestion_log ADD COLUMN tags_json TEXT")
    conn.commit()


def _insert_ingestion_started(
    conn: sqlite3.Connection,
    ingest_id: str,
    request: IngestRequest,
    started_at: str,
) -> None:
    normalized_group = normalize_group(request.group)
    normalized_tags = [str(tag).strip() for tag in request.tags if str(tag).strip()]
    conn.execute(
        """
        INSERT INTO ingestion_log
            (ingest_id, source_type, source_ref, channel, status, timestamp, group_name, tags_json)
        VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)
        """,
        (
            ingest_id,
            request.source_type,
            None,
            request.source_channel,
            started_at,
            normalized_group,
            json.dumps(normalized_tags),
        ),
    )
    conn.commit()


def _mark_run_completed(
    *,
    conn: sqlite3.Connection,
    run_id: str,
    ended_at: str,
    latency_ms: int,
    output_path: str | None,
) -> None:
    conn.execute(
        """
        UPDATE runs
        SET status='completed', ended_at=?, latency_ms=?, output_path=?
        WHERE run_id=?
        """,
        (ended_at, latency_ms, output_path, run_id),
    )
    conn.commit()


def _mark_ingestion_completed(
    *,
    conn: sqlite3.Connection,
    ingest_id: str,
    ended_at: str,
    source_ref: str,
    doc_id: str,
    chunks_created: int,
) -> None:
    conn.execute(
        """
        UPDATE ingestion_log
        SET source_ref=?, doc_id=?, chunks_created=?, status='completed', timestamp=?
        WHERE ingest_id=?
        """,
        (source_ref, doc_id, chunks_created, ended_at, ingest_id),
    )
    conn.commit()


def _mark_run_failed(*, conn: sqlite3.Connection, run_id: str, ended_at: str, latency_ms: int) -> None:
    conn.execute(
        """
        UPDATE runs
        SET status='failed', ended_at=?, latency_ms=?
        WHERE run_id=?
        """,
        (ended_at, latency_ms, run_id),
    )
    conn.commit()


def _mark_ingestion_failed(*, conn: sqlite3.Connection, ingest_id: str, ended_at: str) -> None:
    conn.execute(
        """
        UPDATE ingestion_log
        SET status='failed', timestamp=?
        WHERE ingest_id=?
        """,
        (ended_at, ingest_id),
    )
    conn.commit()


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _looks_like_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _bool_env(name: str, *, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def _is_tls_verify_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "certificate verify failed" in message or "self signed certificate" in message


def _is_http_status_error(exc: Exception, *, status_code: int) -> bool:
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None) == status_code


def _reader_proxy_url(url: str) -> str:
    return f"https://r.jina.ai/{url}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a single Recall.local ingestion job.")
    parser.add_argument(
        "--type",
        required=True,
        choices=["file", "url", "text", "email", "gdoc"],
        help="Source type for ingestion.",
    )
    parser.add_argument("--content", required=True, help="File path, URL, or raw text.")
    parser.add_argument("--source", default="manual", help="Ingestion channel label.")
    parser.add_argument("--title", default=None, help="Optional source title override.")
    parser.add_argument(
        "--group",
        default=DEFAULT_GROUP,
        help="Canonical group (`job-search|learning|project|reference|meeting`).",
    )
    parser.add_argument("--tags", default="", help="Comma-separated tags.")
    parser.add_argument("--metadata-json", default="{}", help="JSON object for extra metadata.")
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Delete existing chunks for the same source_identity before upsert.",
    )
    parser.add_argument(
        "--source-key",
        default=None,
        help="Optional stable source identity key for replacement behavior.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Skip DB/Qdrant writes.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        metadata = json.loads(args.metadata_json)
    except json.JSONDecodeError as exc:
        print(f"Invalid --metadata-json payload: {exc}", file=sys.stderr)
        return 2

    request = IngestRequest(
        source_type=args.type,
        content=args.content,
        source_channel=args.source,
        title=args.title,
        group=normalize_group(args.group),
        tags=[part.strip() for part in args.tags.split(",") if part.strip()],
        metadata=metadata if isinstance(metadata, dict) else {},
        replace_existing=args.replace_existing,
        source_key=args.source_key,
    )

    try:
        result = ingest_request(request, dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
