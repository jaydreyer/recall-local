#!/usr/bin/env python3
"""Phase 5C Obsidian vault sync with hash dedupe and optional watch mode."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase1.group_model import DEFAULT_GROUP, normalize_group  # noqa: E402
from scripts.phase1.ingestion_pipeline import IngestRequest, ingest_request  # noqa: E402
from scripts.shared_time import now_iso  # noqa: E402

DEFAULT_VAULT_PATH = "~/obsidian-vault"
DEFAULT_EXCLUDE_DIRS = ".obsidian,.trash,_attachments,recall-artifacts"
DEFAULT_DEBOUNCE_SECONDS = 5
DEFAULT_STATE_DB_PATH = ROOT / "data" / "vault_sync_state.db"
DEFAULT_AUTO_TAG_RULES_PATH = ROOT / "config" / "auto_tag_rules.json"

WIKI_LINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")
HASHTAG_RE = re.compile(r"(?<![\w/])#([A-Za-z0-9][A-Za-z0-9_\-/]*)")
HEADING_RE = re.compile(r"^\s*#\s+(.+)$", re.MULTILINE)


@dataclass
class SyncSettings:
    vault_path: Path
    state_db_path: Path
    auto_tag_rules_path: Path
    exclude_dirs: set[str]
    debounce_seconds: int
    write_back: bool


@dataclass
class VaultNote:
    absolute_path: Path
    relative_path: str
    content_hash: str
    modified_at_iso: str
    markdown: str


def load_settings(*, vault_path: str | Path | None = None) -> SyncSettings:
    configured_vault = str(vault_path) if vault_path else os.getenv("RECALL_VAULT_PATH", DEFAULT_VAULT_PATH)
    configured_state_db = os.getenv("RECALL_VAULT_STATE_DB", str(DEFAULT_STATE_DB_PATH))
    configured_auto_tag_rules = os.getenv("RECALL_AUTO_TAG_RULES_PATH", str(DEFAULT_AUTO_TAG_RULES_PATH))
    configured_debounce = _read_positive_int_env("RECALL_VAULT_DEBOUNCE_SEC", DEFAULT_DEBOUNCE_SECONDS)

    return SyncSettings(
        vault_path=Path(configured_vault).expanduser().resolve(),
        state_db_path=Path(configured_state_db).expanduser().resolve(),
        auto_tag_rules_path=Path(configured_auto_tag_rules).expanduser().resolve(),
        exclude_dirs=_parse_exclude_dirs(os.getenv("RECALL_VAULT_EXCLUDE_DIRS", DEFAULT_EXCLUDE_DIRS)),
        debounce_seconds=configured_debounce,
        write_back=_read_bool_env("RECALL_VAULT_WRITE_BACK", default=False),
    )


def run_vault_sync_once(
    *,
    vault_path: str | Path | None = None,
    dry_run: bool = False,
    max_files: int | None = None,
) -> dict[str, Any]:
    settings = load_settings(vault_path=vault_path)
    _ensure_vault_exists(settings.vault_path)
    auto_tag_rules = _read_auto_tag_rules(settings.auto_tag_rules_path)

    settings.state_db_path.parent.mkdir(parents=True, exist_ok=True)
    state = _load_state(settings.state_db_path)
    notes = _scan_vault_notes(settings.vault_path, exclude_dirs=settings.exclude_dirs)
    if max_files is not None and max_files > 0:
        notes = notes[:max_files]

    current_paths = {note.relative_path for note in notes}
    changed_notes = [note for note in notes if state.get(note.relative_path) != note.content_hash]
    removed_paths = sorted(set(state) - current_paths)

    ingested: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    synced_at = now_iso()

    for note in changed_notes:
        try:
            parsed = _parse_note(markdown=note.markdown)
            group = _derive_group(
                relative_path=note.relative_path,
                frontmatter=parsed["frontmatter"],
                auto_tag_rules=auto_tag_rules,
            )
            tags = _derive_tags(parsed["hashtags"], parsed["frontmatter"])
            source_ref = f"obsidian://{note.relative_path}"
            request = IngestRequest(
                source_type="text",
                content=parsed["body"] or note.markdown,
                source_channel="vault-sync",
                title=_derive_title(note.relative_path, parsed["body"], parsed["frontmatter"]),
                group=group,
                tags=tags,
                metadata={
                    "source": source_ref,
                    "source_ref": source_ref,
                    "source_type": "obsidian-note",
                    "vault_path": note.relative_path,
                    "wiki_links": parsed["wiki_links"],
                    "frontmatter": parsed["frontmatter"],
                    "ingestion_channel": "vault-sync",
                },
                replace_existing=True,
                source_key=f"vault:{note.relative_path}",
            )
            result = ingest_request(request, dry_run=dry_run)
            if not dry_run:
                _upsert_state(settings.state_db_path, relative_path=note.relative_path, content_hash=note.content_hash)
            ingested.append(
                {
                    "vault_path": note.relative_path,
                    "group": group,
                    "tags": tags,
                    "wiki_links": parsed["wiki_links"],
                    "status": result.status,
                    "run_id": result.run_id,
                    "doc_id": result.doc_id,
                }
            )
        except Exception as exc:  # noqa: BLE001
            errors.append({"vault_path": note.relative_path, "error": str(exc)})

    removed_count = 0
    if not dry_run and removed_paths:
        removed_count = _delete_removed_paths(settings.state_db_path, removed_paths)

    summary: dict[str, Any] = {
        "workflow": "workflow_05c_vault_sync",
        "mode": "once",
        "dry_run": dry_run,
        "vault_path": str(settings.vault_path),
        "state_db_path": str(settings.state_db_path),
        "scanned_files": len(notes),
        "changed_files": len(changed_notes),
        "skipped_unchanged_files": len(notes) - len(changed_notes),
        "removed_files": removed_count if not dry_run else len(removed_paths),
        "ingested_files": len(ingested),
        "errors": errors,
        "ingested": ingested,
        "synced_at": synced_at,
    }
    write_back_path = _write_sync_report_if_enabled(settings=settings, summary=summary)
    if write_back_path is not None:
        summary["write_back_report"] = write_back_path
    return summary


def list_vault_tree(*, vault_path: str | Path | None = None) -> dict[str, Any]:
    settings = load_settings(vault_path=vault_path)
    _ensure_vault_exists(settings.vault_path)
    auto_tag_rules = _read_auto_tag_rules(settings.auto_tag_rules_path)
    notes = _scan_vault_notes(settings.vault_path, exclude_dirs=settings.exclude_dirs)

    files: list[dict[str, Any]] = []
    for note in notes:
        parsed = _parse_note(markdown=note.markdown)
        files.append(
            {
                "path": note.relative_path,
                "title": _derive_title(note.relative_path, parsed["body"], parsed["frontmatter"]),
                "group": _derive_group(
                    relative_path=note.relative_path,
                    frontmatter=parsed["frontmatter"],
                    auto_tag_rules=auto_tag_rules,
                ),
                "modified_at": note.modified_at_iso,
            }
        )

    return {
        "workflow": "workflow_05c_vault_tree",
        "vault_path": str(settings.vault_path),
        "generated_at": now_iso(),
        "file_count": len(files),
        "tree": _build_tree([item["path"] for item in files]),
        "files": files,
    }


def run_vault_sync_watch(
    *,
    vault_path: str | Path | None = None,
    dry_run: bool = False,
    max_files: int | None = None,
) -> int:
    settings = load_settings(vault_path=vault_path)
    _ensure_vault_exists(settings.vault_path)
    print(
        json.dumps(run_vault_sync_once(vault_path=settings.vault_path, dry_run=dry_run, max_files=max_files), indent=2)
    )

    try:
        from watchdog.events import FileSystemEvent, FileSystemEventHandler
        from watchdog.observers import Observer
    except ModuleNotFoundError as exc:  # pragma: no cover - runtime dependency path
        raise RuntimeError("watch mode requires watchdog (pip install watchdog).") from exc

    sync_lock = threading.Lock()

    def trigger_sync(trigger: str) -> None:
        with sync_lock:
            summary = run_vault_sync_once(vault_path=settings.vault_path, dry_run=dry_run, max_files=max_files)
        summary["trigger"] = trigger
        print(json.dumps(summary, indent=2))

    class DebouncedHandler(FileSystemEventHandler):
        def __init__(self, debounce_seconds: int):
            super().__init__()
            self._debounce_seconds = debounce_seconds
            self._timer: threading.Timer | None = None
            self._lock = threading.Lock()
            self._last_trigger = "change"

        def _schedule(self, trigger: str) -> None:
            with self._lock:
                self._last_trigger = trigger
                if self._timer is not None:
                    self._timer.cancel()
                self._timer = threading.Timer(self._debounce_seconds, self._flush)
                self._timer.daemon = True
                self._timer.start()

        def _flush(self) -> None:
            with self._lock:
                trigger = self._last_trigger
                self._timer = None
            trigger_sync(trigger)

        def on_created(self, event: FileSystemEvent) -> None:
            if not event.is_directory:
                self._schedule("created")

        def on_modified(self, event: FileSystemEvent) -> None:
            if not event.is_directory:
                self._schedule("modified")

        def on_deleted(self, event: FileSystemEvent) -> None:
            if not event.is_directory:
                self._schedule("deleted")

        def on_moved(self, event: FileSystemEvent) -> None:
            if not event.is_directory:
                # Syncthing temp-to-final writes typically arrive as move events.
                self._schedule("moved")

    handler = DebouncedHandler(settings.debounce_seconds)
    observer = Observer()
    observer.schedule(handler, str(settings.vault_path), recursive=True)
    observer.start()
    print(
        "Watching vault for changes: "
        f"path={settings.vault_path} debounce={settings.debounce_seconds}s dry_run={dry_run}"
    )

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    return 0


def _parse_note(*, markdown: str) -> dict[str, Any]:
    frontmatter, body = _extract_frontmatter(markdown)
    wiki_links = []
    for match in WIKI_LINK_RE.findall(body):
        clean = str(match).split("|", 1)[0].split("#", 1)[0].strip()
        if clean:
            wiki_links.append(clean)
    hashtags = [tag.lower() for tag in HASHTAG_RE.findall(body)]
    return {
        "frontmatter": frontmatter,
        "body": body.strip(),
        "wiki_links": _dedupe_preserving_order(wiki_links),
        "hashtags": _dedupe_preserving_order(hashtags),
    }


def _derive_group(*, relative_path: str, frontmatter: dict[str, Any], auto_tag_rules: dict[str, Any]) -> str:
    frontmatter_group = frontmatter.get("group")
    if isinstance(frontmatter_group, str) and frontmatter_group.strip():
        return normalize_group(frontmatter_group)

    vault_folders = auto_tag_rules.get("vault_folders", {})
    folder_map: dict[str, str] = {}
    if isinstance(vault_folders, dict):
        for folder, group in vault_folders.items():
            folder_map[str(folder).strip().lower()] = normalize_group(group)

    parts = [part.lower() for part in Path(relative_path).parts[:-1]]
    for part in parts:
        mapped = folder_map.get(part)
        if mapped:
            return normalize_group(mapped)
    return DEFAULT_GROUP


def _derive_tags(hashtags: list[str], frontmatter: dict[str, Any]) -> list[str]:
    values: list[str] = []
    frontmatter_tags = frontmatter.get("tags")
    if isinstance(frontmatter_tags, list):
        values.extend(str(item).strip().lower() for item in frontmatter_tags)
    elif isinstance(frontmatter_tags, str):
        values.extend(part.strip().lower() for part in frontmatter_tags.split(","))
    values.extend(hashtags)
    return [tag for tag in _dedupe_preserving_order(values) if tag]


def _derive_title(relative_path: str, body: str, frontmatter: dict[str, Any]) -> str:
    frontmatter_title = frontmatter.get("title")
    if isinstance(frontmatter_title, str) and frontmatter_title.strip():
        return frontmatter_title.strip()
    heading_match = HEADING_RE.search(body)
    if heading_match:
        return heading_match.group(1).strip()
    return Path(relative_path).stem


def _extract_frontmatter(markdown: str) -> tuple[dict[str, Any], str]:
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, markdown

    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        return {}, markdown

    parsed = _parse_frontmatter_lines(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1 :])
    return parsed, body


def _parse_frontmatter_lines(lines: list[str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    idx = 0
    while idx < len(lines):
        raw_line = lines[idx]
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            idx += 1
            continue

        if ":" not in raw_line:
            idx += 1
            continue

        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            idx += 1
            continue

        if not value:
            list_values: list[str] = []
            lookahead = idx + 1
            while lookahead < len(lines):
                item_line = lines[lookahead].strip()
                if item_line.startswith("- "):
                    list_values.append(item_line[2:].strip())
                    lookahead += 1
                    continue
                break
            if list_values:
                parsed[key] = list_values
                idx = lookahead
                continue
            parsed[key] = ""
            idx += 1
            continue

        parsed[key] = _parse_scalar(value)
        idx += 1
    return parsed


def _parse_scalar(value: str) -> Any:
    trimmed = value.strip()
    if trimmed.startswith("[") and trimmed.endswith("]"):
        inner = trimmed[1:-1].strip()
        if not inner:
            return []
        return [part.strip().strip("'\"") for part in inner.split(",") if part.strip()]
    lowered = trimmed.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if (trimmed.startswith("'") and trimmed.endswith("'")) or (trimmed.startswith('"') and trimmed.endswith('"')):
        return trimmed[1:-1]
    try:
        return int(trimmed)
    except ValueError:
        pass
    try:
        return float(trimmed)
    except ValueError:
        return trimmed


def _scan_vault_notes(vault_path: Path, *, exclude_dirs: set[str]) -> list[VaultNote]:
    notes: list[VaultNote] = []
    for file_path in sorted(vault_path.rglob("*")):
        if not file_path.is_file():
            continue
        relative_path = file_path.relative_to(vault_path).as_posix()
        if _is_excluded_file(relative_path, exclude_dirs=exclude_dirs):
            continue
        if file_path.suffix.lower() != ".md":
            continue
        try:
            markdown = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            markdown = file_path.read_text(encoding="utf-8", errors="replace")
        file_hash = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
        notes.append(
            VaultNote(
                absolute_path=file_path,
                relative_path=relative_path,
                content_hash=file_hash,
                modified_at_iso=datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc).isoformat(
                    timespec="seconds"
                ),
                markdown=markdown,
            )
        )
    return notes


def _is_excluded_file(relative_path: str, *, exclude_dirs: set[str]) -> bool:
    normalized = relative_path.replace("\\", "/")
    name = Path(normalized).name.lower()
    if name.startswith(".syncthing.") or name.endswith(".tmp"):
        return True

    parts = [part.lower() for part in Path(normalized).parts]
    for part in parts[:-1]:
        if part in exclude_dirs:
            return True
    return False


def _load_state(state_db_path: Path) -> dict[str, str]:
    with sqlite3.connect(state_db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vault_sync_state (
                relative_path TEXT PRIMARY KEY,
                content_hash TEXT NOT NULL,
                synced_at TEXT NOT NULL
            )
            """
        )
        rows = conn.execute("SELECT relative_path, content_hash FROM vault_sync_state").fetchall()
    return {str(path): str(content_hash) for path, content_hash in rows}


def _upsert_state(state_db_path: Path, *, relative_path: str, content_hash: str) -> None:
    with sqlite3.connect(state_db_path) as conn:
        conn.execute(
            """
            INSERT INTO vault_sync_state (relative_path, content_hash, synced_at)
            VALUES (?, ?, ?)
            ON CONFLICT(relative_path) DO UPDATE SET
                content_hash=excluded.content_hash,
                synced_at=excluded.synced_at
            """,
            (relative_path, content_hash, now_iso()),
        )
        conn.commit()


def _delete_removed_paths(state_db_path: Path, removed_paths: list[str]) -> int:
    if not removed_paths:
        return 0
    with sqlite3.connect(state_db_path) as conn:
        conn.executemany(
            "DELETE FROM vault_sync_state WHERE relative_path=?",
            [(path,) for path in removed_paths],
        )
        conn.commit()
    return len(removed_paths)


def _write_sync_report_if_enabled(*, settings: SyncSettings, summary: dict[str, Any]) -> str | None:
    if not settings.write_back:
        return None
    if summary.get("dry_run"):
        return None

    report_root = settings.vault_path / "recall-artifacts" / "sync-reports"
    report_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = report_root / f"{timestamp}_vault_sync_report.json"
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return str(report_path)


def _read_auto_tag_rules(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def _build_tree(paths: list[str]) -> dict[str, Any]:
    root: dict[str, Any] = {"name": ".", "type": "directory", "children": []}
    index: dict[str, dict[str, Any]] = {"": root}

    for path in paths:
        normalized = path.replace("\\", "/").strip("/")
        if not normalized:
            continue
        parts = normalized.split("/")
        parent_key = ""
        for idx, part in enumerate(parts):
            key = "/".join(parts[: idx + 1])
            node = index.get(key)
            is_file = idx == len(parts) - 1
            if node is None:
                node = {
                    "name": part,
                    "type": "file" if is_file else "directory",
                }
                if is_file:
                    node["path"] = key
                else:
                    node["children"] = []
                index[key] = node
                parent = index[parent_key]
                parent["children"].append(node)
            parent_key = key
    _sort_tree(root)
    return root


def _sort_tree(node: dict[str, Any]) -> None:
    children = node.get("children")
    if not isinstance(children, list):
        return
    children.sort(key=lambda item: (item.get("type") != "directory", item.get("name", "")))
    for child in children:
        _sort_tree(child)


def _read_bool_env(name: str, *, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_exclude_dirs(raw_value: str) -> set[str]:
    values = set()
    for part in raw_value.split(","):
        cleaned = part.strip().strip("/")
        if cleaned:
            values.add(cleaned.lower())
    return values


def _read_positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    if parsed <= 0:
        return default
    return parsed


def _ensure_vault_exists(vault_path: Path) -> None:
    if not vault_path.exists():
        raise FileNotFoundError(f"Vault path does not exist: {vault_path}")
    if not vault_path.is_dir():
        raise NotADirectoryError(f"Vault path is not a directory: {vault_path}")


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        clean = str(value).strip()
        if not clean:
            continue
        if clean in seen:
            continue
        seen.add(clean)
        deduped.append(clean)
    return deduped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Obsidian vault notes into Recall.local.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Run one-shot sync and exit.")
    mode.add_argument("--watch", action="store_true", help="Run watch mode with debounce sync.")
    parser.add_argument("--vault-path", default=None, help="Override RECALL_VAULT_PATH.")
    parser.add_argument("--dry-run", action="store_true", help="Skip durable ingestion/state writes.")
    parser.add_argument("--max-files", type=int, default=None, help="Optional cap for files processed in one run.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.once:
        summary = run_vault_sync_once(vault_path=args.vault_path, dry_run=args.dry_run, max_files=args.max_files)
        print(json.dumps(summary, indent=2))
        return 0
    return run_vault_sync_watch(vault_path=args.vault_path, dry_run=args.dry_run, max_files=args.max_files)


if __name__ == "__main__":
    raise SystemExit(main())
