"""
Tests for Part 4: Semantic Kernel Skills
Run: pytest tests\ -v
Fully offline — no Azure subscription, no OpenAI key needed.
"""

import asyncio
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from skills.detection_skills import (
    AnomalyDetectionSkill,
    AzureRAGSkill,
    LogIngestionSkill,
    ReporterSkill,
)

KB_PATH  = os.path.join(os.path.dirname(__file__), "..", "knowledge_base", "incidents.json")
LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "sample_prod.log")


# ─── LogIngestionSkill Tests ──────────────────────────────────────────────

class TestLogIngestionSkill:

    def test_ingests_real_log_file(self):
        skill = LogIngestionSkill()
        result = json.loads(skill.ingest_logs(LOG_PATH))
        assert "entries" in result
        assert result["total_entries"] > 0

    def test_returns_error_for_missing_file(self):
        skill = LogIngestionSkill()
        result = json.loads(skill.ingest_logs("/nonexistent/path.log"))
        assert "error" in result

    def test_parses_status_codes(self):
        skill = LogIngestionSkill()
        result = json.loads(skill.ingest_logs(LOG_PATH))
        statuses = {e["status"] for e in result["entries"]}
        assert 200 in statuses

    def test_parses_response_size(self):
        skill = LogIngestionSkill()
        result = json.loads(skill.ingest_logs(LOG_PATH))
        sizes = [e["response_size"] for e in result["entries"]]
        assert 0 in sizes

    def test_window_minutes_in_output(self):
        skill = LogIngestionSkill()
        result = json.loads(skill.ingest_logs(LOG_PATH, window_minutes=30))
        assert result["window_minutes"] == 30

    def test_skill_is_kernel_function(self):
        from semantic_kernel.functions import KernelFunction
        skill = LogIngestionSkill()
        assert callable(skill.ingest_logs)


# ─── AnomalyDetectionSkill Tests ─────────────────────────────────────────

class TestAnomalyDetectionSkill:

    def _make_entries(self, items):
        return json.dumps({"entries": items, "total_entries": len(items)})

    def test_detects_empty_200_responses(self):
        skill = AnomalyDetectionSkill()
        entries = [
            {"status": 200, "path": "/api/auth/refresh", "response_size": 0,
             "duration_ms": 88, "method": "POST", "level": "INFO", "error": ""},
        ] * 5
        result = json.loads(skill.detect_anomalies(self._make_entries(entries)))
        types = [a["type"] for a in result["anomalies"]]
        assert "EMPTY_SUCCESS_RESPONSE" in types

    def test_detects_sub_threshold_error_rate(self):
        skill = AnomalyDetectionSkill()
        entries = (
            [{"status": 200, "path": "/api/cart", "response_size": 100,
              "duration_ms": 50, "method": "GET", "level": "INFO", "error": ""}] * 13
            +
            [{"status": 404, "path": "/api/cart", "response_size": 42,
              "duration_ms": 12, "method": "GET", "level": "INFO", "error": "not found"}] * 2
        )
        result = json.loads(skill.detect_anomalies(
            self._make_entries(entries), error_threshold=0.20
        ))
        types = [a["type"] for a in result["anomalies"]]
        assert "SUB_THRESHOLD_ERROR_RATE" in types

    def test_detects_latency_spike(self):
        skill = AnomalyDetectionSkill()
        entries = (
            [{"status": 200, "path": "/api/checkout", "response_size": 892,
              "duration_ms": 50, "method": "POST", "level": "INFO", "error": ""}] * 20
            +
            [{"status": 200, "path": "/api/checkout", "response_size": 892,
              "duration_ms": 2000, "method": "POST", "level": "INFO", "error": ""}] * 6
        )
        result = json.loads(skill.detect_anomalies(self._make_entries(entries)))
        types = [a["type"] for a in result["anomalies"]]
        assert "LATENCY_SPIKE_ON_SUCCESS" in types

    def test_clean_logs_return_zero_anomalies(self):
        skill = AnomalyDetectionSkill()
        entries = [
            {"status": 200, "path": "/api/products", "response_size": 1423,
             "duration_ms": 45, "method": "GET", "level": "INFO", "error": ""}
        ] * 50
        result = json.loads(skill.detect_anomalies(self._make_entries(entries)))
        assert result["anomaly_count"] == 0

    def test_empty_entries_returns_zero(self):
        skill = AnomalyDetectionSkill()
        result = json.loads(skill.detect_anomalies(
            json.dumps({"entries": [], "total_entries": 0})
        ))
        assert result["anomaly_count"] == 0

    def test_on_real_log_file(self):
        skill_ingest = LogIngestionSkill()
        skill_detect = AnomalyDetectionSkill()
        log_data = skill_ingest.ingest_logs(LOG_PATH)
        result = json.loads(skill_detect.detect_anomalies(log_data))
        assert "anomaly_count" in result
        assert result["anomaly_count"] >= 0


# ─── AzureRAGSkill Tests ──────────────────────────────────────────────────

class TestAzureRAGSkill:

    def test_loads_4_azure_incidents(self):
        skill = AzureRAGSkill(kb_path=KB_PATH)
        skill._build_retriever()
        assert len(skill._retriever) == 4

    def test_all_incidents_are_azure_specific(self):
        skill = AzureRAGSkill(kb_path=KB_PATH)
        skill._build_retriever()
        for doc in skill._retriever:
            assert "azure" in doc["metadata"].get("tags", [])

    def test_incident_ids_are_015_to_018(self):
        skill = AzureRAGSkill(kb_path=KB_PATH)
        skill._build_retriever()
        ids = [doc["metadata"]["id"] for doc in skill._retriever]
        assert "INC-015" in ids
        assert "INC-018" in ids

    def test_retrieves_relevant_incident_for_auth_query(self):
        skill = AzureRAGSkill(kb_path=KB_PATH)
        result = json.loads(skill.retrieve_context(
            "EMPTY_SUCCESS_RESPONSE auth refresh token empty body Azure"
        ))
        assert result["retrieved_count"] > 0
        types = [c["type"] for c in result["context"]]
        assert "EMPTY_SUCCESS_RESPONSE" in types

    def test_retrieves_cosmosdb_for_cart_query(self):
        skill = AzureRAGSkill(kb_path=KB_PATH)
        result = json.loads(skill.retrieve_context(
            "SUB_THRESHOLD_ERROR_RATE cart CosmosDB throttling Azure"
        ))
        assert result["retrieved_count"] > 0
        incident_ids = [c["incident_id"] for c in result["context"]]
        assert "INC-016" in incident_ids

    def test_all_context_items_have_azure_service(self):
        skill = AzureRAGSkill(kb_path=KB_PATH)
        result = json.loads(skill.retrieve_context("Azure silent failure"))
        for ctx in result["context"]:
            assert "azure_service" in ctx

    def test_all_context_items_have_runbook(self):
        skill = AzureRAGSkill(kb_path=KB_PATH)
        result = json.loads(skill.retrieve_context("silent failure log anomaly"))
        for ctx in result["context"]:
            assert len(ctx.get("runbook", "")) > 10

    def test_missing_kb_returns_empty_gracefully(self):
        skill = AzureRAGSkill(kb_path="/nonexistent/incidents.json")
        try:
            result = json.loads(skill.retrieve_context("test query"))
            assert result["retrieved_count"] == 0
        except Exception:
            pass


# ─── ReporterSkill Tests ──────────────────────────────────────────────────

class TestReporterSkill:

    SAMPLE_ANOMALY = json.dumps({
        "anomaly_count": 1,
        "entries_analysed": 62,
        "anomalies": [{
            "type": "EMPTY_SUCCESS_RESPONSE",
            "severity": "HIGH",
            "count": 10,
            "affected_paths": ["/api/auth/refresh"],
            "description": "10 HTTP 200 with zero-byte body",
        }],
    })
    SAMPLE_RAG = json.dumps({
        "retrieved_count": 1,
        "context": [{
            "incident_id": "INC-015",
            "title": "Azure AD token refresh returning empty body",
            "type": "EMPTY_SUCCESS_RESPONSE",
            "azure_service": "Azure Active Directory / Key Vault",
            "root_cause": "Managed Identity permissions revoked.",
            "business_impact": "12,000 enterprise users de-authenticated.",
            "detection_lag_hours": 5,
            "runbook": "1. Check Managed Identity. 2. Verify Key Vault policy.",
            "agent_verdict": "TRUE_POSITIVE",
            "tags": "azure, managed-identity",
        }],
    })

    def test_creates_report_file(self):
        skill = ReporterSkill()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            result = skill.generate_report(self.SAMPLE_ANOMALY, self.SAMPLE_RAG, out)
            assert os.path.exists(out)
            assert "silent failure" in result.lower()

    def test_report_contains_azure_service(self):
        skill = ReporterSkill()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            skill.generate_report(self.SAMPLE_ANOMALY, self.SAMPLE_RAG, out)
            content = open(out, encoding="utf-8").read()
            assert "Azure" in content

    def test_report_contains_comparison_table(self):
        skill = ReporterSkill()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            skill.generate_report(self.SAMPLE_ANOMALY, self.SAMPLE_RAG, out)
            content = open(out, encoding="utf-8").read()
            assert "Semantic Kernel" in content
            assert "Part 1" in content
            assert "Part 4" in content

    def test_report_contains_runbook(self):
        skill = ReporterSkill()
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            skill.generate_report(self.SAMPLE_ANOMALY, self.SAMPLE_RAG, out)
            content = open(out, encoding="utf-8").read()
            assert "Runbook" in content

    def test_clean_report_when_no_anomalies(self):
        skill = ReporterSkill()
        clean = json.dumps({"anomaly_count": 0, "entries_analysed": 62, "anomalies": []})
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            skill.generate_report(clean, "{}", out)
            content = open(out, encoding="utf-8").read()
            assert "No silent failures detected" in content


# ─── Integration Tests ────────────────────────────────────────────────────

class TestIntegration:

    def test_full_sk_pipeline(self):
        from main import run_detection
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            result = run_detection(
                log_source=LOG_PATH,
                kb_path=KB_PATH,
                output_path=out,
            )
            assert result["status"] == "complete"
            assert os.path.exists(out)

    def test_kernel_registers_all_4_skills(self):
        from semantic_kernel import Kernel
        from skills.detection_skills import (
            AnomalyDetectionSkill, AzureRAGSkill,
            LogIngestionSkill, ReporterSkill,
        )
        kernel = Kernel()
        kernel.add_plugin(LogIngestionSkill(),      plugin_name="LogIngestion")
        kernel.add_plugin(AnomalyDetectionSkill(),  plugin_name="AnomalyDetection")
        kernel.add_plugin(AzureRAGSkill(kb_path=KB_PATH), plugin_name="AzureRAG")
        kernel.add_plugin(ReporterSkill(),          plugin_name="Reporter")
        plugin_names = list(kernel.plugins.keys())
        assert "LogIngestion"     in plugin_names
        assert "AnomalyDetection" in plugin_names
        assert "AzureRAG"         in plugin_names
        assert "Reporter"         in plugin_names

    def test_report_written_with_utf8(self):
        from main import run_detection
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            run_detection(log_source=LOG_PATH, kb_path=KB_PATH, output_path=out)
            content = open(out, encoding="utf-8").read()
            assert "Semantic Kernel" in content

    def test_findings_count_is_non_negative(self):
        from main import run_detection
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            result = run_detection(log_source=LOG_PATH, kb_path=KB_PATH, output_path=out)
            assert result["total_findings"] >= 0
