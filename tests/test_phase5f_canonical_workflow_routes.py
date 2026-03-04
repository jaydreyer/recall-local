#!/usr/bin/env python3
"""Phase 5F regression tests for canonical n8n workflow bridge routes."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = ROOT_DIR / "n8n" / "workflows"


class Phase5FCanonicalWorkflowRoutesTests(unittest.TestCase):
    def _load_http_request_node(self, workflow_path: Path) -> dict[str, object]:
        payload = json.loads(workflow_path.read_text(encoding="utf-8"))
        nodes = payload.get("nodes", [])
        for node in nodes:
            if node.get("type") == "n8n-nodes-base.httpRequest":
                return node
        self.fail(f"No n8n-nodes-base.httpRequest node found in {workflow_path}")

    def test_http_workflows_use_canonical_bridge_routes(self) -> None:
        expected_urls = {
            "phase1b_recall_ingest_webhook_http.workflow.json": "={{ ($env.RECALL_BRIDGE_BASE_URL || 'http://100.116.103.78:8090') + '/v1/ingestions' }}",
            "phase1b_gmail_forward_ingest_http.workflow.json": "={{ ($env.RECALL_BRIDGE_BASE_URL || 'http://100.116.103.78:8090') + '/v1/ingestions' }}",
            "phase1c_recall_rag_query_http.workflow.json": "http://100.116.103.78:8090/v1/rag-queries",
            "phase2a_meeting_action_items_http.workflow.json": "http://100.116.103.78:8090/v1/meeting-action-items",
            "phase3a_bookmarklet_form_http.workflow.json": "={{ ($env.RECALL_BRIDGE_BASE_URL || 'http://100.116.103.78:8090') + '/v1/ingestions' }}",
            "phase3a_meeting_action_form_http.workflow.json": "http://100.116.103.78:8090/v1/meeting-action-items",
        }

        for filename, expected_url in expected_urls.items():
            workflow_path = WORKFLOWS_DIR / filename
            node = self._load_http_request_node(workflow_path)
            parameters = node.get("parameters", {})
            self.assertEqual(parameters.get("url"), expected_url, msg=filename)

    def test_ingestion_workflows_force_expected_channel(self) -> None:
        expected_json_body = {
            "phase1b_recall_ingest_webhook_http.workflow.json": "={{ Object.assign({}, ($json.body || $json), { channel: 'webhook' }) }}",
            "phase1b_gmail_forward_ingest_http.workflow.json": "={{ ({ channel: 'gmail-forward', subject: $json.subject || '', from: (typeof $json.from === 'string' ? $json.from : (($json.from && $json.from.text) ? $json.from.text : '')), messageId: $json.messageId || $json.message_id || '', text: $json.textPlain || $json.text || ($json.subject ? ('Subject: ' + $json.subject) : ''), html: $json.textHtml || $json.html || '', attachment_paths: Array.isArray($json.attachment_paths) ? $json.attachment_paths : [] }) }}",
            "phase3a_bookmarklet_form_http.workflow.json": "={{ Object.assign({}, $json.body ? $json.body : $json, { channel: 'bookmarklet' }) }}",
        }

        for filename, expected_expression in expected_json_body.items():
            workflow_path = WORKFLOWS_DIR / filename
            node = self._load_http_request_node(workflow_path)
            parameters = node.get("parameters", {})
            self.assertEqual(parameters.get("jsonBody"), expected_expression, msg=filename)


if __name__ == "__main__":
    unittest.main()
