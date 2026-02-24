#!/usr/bin/env python3
"""Phase 5C tests for vault sync hashing, exclusions, and metadata extraction."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.phase1.ingestion_pipeline import IngestResult
from scripts.phase5 import vault_sync


def _fake_ingest_result() -> IngestResult:
    return IngestResult(
        run_id="run-1",
        ingest_id="ingest-1",
        doc_id="doc-1",
        source_type="text",
        source_ref="inline:text",
        title="Example",
        source_identity="inline:text",
        chunks_created=1,
        moved_to=None,
        replace_existing=True,
        replaced_points=0,
        replacement_status="applied",
        latency_ms=1,
        status="completed",
    )


class VaultSyncPhase5CTests(unittest.TestCase):
    def test_sync_detects_only_changed_files_and_extracts_obsidian_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            vault_path = root / "vault"
            vault_path.mkdir(parents=True, exist_ok=True)
            state_db = root / "vault_state.db"
            rules_path = root / "auto_tag_rules.json"
            rules_path.write_text(
                json.dumps({"vault_folders": {"career": "job-search"}}),
                encoding="utf-8",
            )

            note_path = vault_path / "career" / "anthropic-prep.md"
            note_path.parent.mkdir(parents=True, exist_ok=True)
            note_path.write_text(
                "\n".join(
                    [
                        "---",
                        "title: Anthropic Interview Prep",
                        "tags: [anthropic, se-role]",
                        "---",
                        "# Prep",
                        "Review [[Behavioral Questions|Behavioral Questions]] and #Interview.",
                    ]
                ),
                encoding="utf-8",
            )

            env = {
                "RECALL_VAULT_PATH": str(vault_path),
                "RECALL_VAULT_STATE_DB": str(state_db),
                "RECALL_AUTO_TAG_RULES_PATH": str(rules_path),
                "RECALL_VAULT_EXCLUDE_DIRS": ".obsidian,.trash,_attachments,recall-artifacts",
                "RECALL_VAULT_WRITE_BACK": "false",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("scripts.phase5.vault_sync.ingest_request", return_value=_fake_ingest_result()) as mock_ingest:
                    first = vault_sync.run_vault_sync_once(dry_run=False)
                    second = vault_sync.run_vault_sync_once(dry_run=False)
                    note_path.write_text(
                        note_path.read_text(encoding="utf-8") + "\nAdd #followup details.",
                        encoding="utf-8",
                    )
                    third = vault_sync.run_vault_sync_once(dry_run=False)

        self.assertEqual(first["scanned_files"], 1)
        self.assertEqual(first["changed_files"], 1)
        self.assertEqual(first["ingested_files"], 1)
        self.assertEqual(first["errors"], [])

        self.assertEqual(second["changed_files"], 0)
        self.assertEqual(second["ingested_files"], 0)

        self.assertEqual(third["changed_files"], 1)
        self.assertEqual(third["ingested_files"], 1)
        self.assertEqual(mock_ingest.call_count, 2)

        first_request = mock_ingest.call_args_list[0].args[0]
        self.assertEqual(first_request.group, "job-search")
        self.assertEqual(first_request.metadata["vault_path"], "career/anthropic-prep.md")
        self.assertEqual(first_request.metadata["wiki_links"], ["Behavioral Questions"])
        self.assertIn("anthropic", first_request.tags)
        self.assertIn("se-role", first_request.tags)
        self.assertIn("interview", first_request.tags)

    def test_sync_excludes_configured_paths_and_handles_rename_state_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            vault_path = root / "vault"
            vault_path.mkdir(parents=True, exist_ok=True)
            state_db = root / "vault_state.db"
            rules_path = root / "auto_tag_rules.json"
            rules_path.write_text("{}", encoding="utf-8")

            (vault_path / ".obsidian").mkdir(parents=True, exist_ok=True)
            (vault_path / ".trash").mkdir(parents=True, exist_ok=True)
            (vault_path / "_attachments").mkdir(parents=True, exist_ok=True)
            (vault_path / "recall-artifacts").mkdir(parents=True, exist_ok=True)
            (vault_path / "notes").mkdir(parents=True, exist_ok=True)

            (vault_path / ".obsidian" / "skip.md").write_text("# skip", encoding="utf-8")
            (vault_path / ".trash" / "skip.md").write_text("# skip", encoding="utf-8")
            (vault_path / "_attachments" / "skip.md").write_text("# skip", encoding="utf-8")
            (vault_path / "recall-artifacts" / "skip.md").write_text("# skip", encoding="utf-8")
            (vault_path / "notes" / ".syncthing.note.md").write_text("# skip", encoding="utf-8")
            (vault_path / "notes" / "temp.md.tmp").write_text("# skip", encoding="utf-8")
            kept = vault_path / "notes" / "keep.md"
            kept.write_text("# keep", encoding="utf-8")

            env = {
                "RECALL_VAULT_PATH": str(vault_path),
                "RECALL_VAULT_STATE_DB": str(state_db),
                "RECALL_AUTO_TAG_RULES_PATH": str(rules_path),
                "RECALL_VAULT_EXCLUDE_DIRS": ".obsidian,.trash,_attachments,recall-artifacts",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("scripts.phase5.vault_sync.ingest_request", return_value=_fake_ingest_result()):
                    first = vault_sync.run_vault_sync_once(dry_run=False)
                    renamed = vault_path / "notes" / "keep-renamed.md"
                    kept.rename(renamed)
                    second = vault_sync.run_vault_sync_once(dry_run=False)

        self.assertEqual(first["scanned_files"], 1)
        self.assertEqual(first["changed_files"], 1)
        self.assertEqual(first["ingested_files"], 1)

        self.assertEqual(second["scanned_files"], 1)
        self.assertEqual(second["changed_files"], 1)
        self.assertEqual(second["removed_files"], 1)
        self.assertEqual(second["ingested_files"], 1)


if __name__ == "__main__":
    unittest.main()
