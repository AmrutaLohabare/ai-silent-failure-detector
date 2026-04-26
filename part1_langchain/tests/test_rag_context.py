"""
Tests for the RAGContextTool — no OpenAI API key needed.
Uses the TF-IDF fallback retriever so tests run fully offline.
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.rag_context import RAGContextTool, _load_knowledge_base, _incidents_to_documents, _TFIDFRetriever


# ─── Fixtures ─────────────────────────────────────────────────────────────

KB_PATH = os.path.join(os.path.dirname(__file__), "..", "knowledge_base", "incidents.json")


@pytest.fixture
def rag_tool_with_real_kb():
    """RAGContextTool backed by the real knowledge base using TF-IDF fallback."""
    tool = RAGContextTool(kb_path=KB_PATH)
    # Pre-seed with TF-IDF retriever to avoid sentence-transformers download in CI
    from agent.rag_context import _incidents_to_documents, _load_knowledge_base, _TFIDFRetriever, get_retriever
    import agent.rag_context as rag_module
    incidents = _load_knowledge_base(KB_PATH)
    docs = _incidents_to_documents(incidents)
    rag_module._retriever_cache = _TFIDFRetriever(docs)
    return tool


# ─── Knowledge Base Loading Tests ─────────────────────────────────────────

class TestKnowledgeBaseLoading:

    def test_loads_real_kb_file(self):
        incidents = _load_knowledge_base(KB_PATH)
        assert len(incidents) > 0

    def test_incidents_have_required_fields(self):
        incidents = _load_knowledge_base(KB_PATH)
        for inc in incidents:
            assert "id" in inc
            assert "type" in inc
            assert "root_cause" in inc
            assert "runbook" in inc

    def test_returns_empty_list_for_missing_file(self):
        result = _load_knowledge_base("/nonexistent/path.json")
        assert result == []

    def test_incidents_to_documents_produces_rich_text(self):
        incidents = _load_knowledge_base(KB_PATH)
        docs = _incidents_to_documents(incidents)
        assert len(docs) == len(incidents)
        for doc in docs:
            assert len(doc["text"]) > 50
            assert "root_cause" in doc["metadata"]
            assert "runbook" in doc["metadata"]


# ─── TF-IDF Retriever Tests ───────────────────────────────────────────────

class TestTFIDFRetriever:

    @pytest.fixture
    def retriever(self):
        incidents = _load_knowledge_base(KB_PATH)
        docs = _incidents_to_documents(incidents)
        return _TFIDFRetriever(docs)

    def test_returns_two_documents(self, retriever):
        results = retriever.get_relevant_documents("EMPTY_SUCCESS_RESPONSE auth/refresh")
        assert len(results) == 2

    def test_auth_query_retrieves_auth_incident(self, retriever):
        results = retriever.get_relevant_documents(
            "EMPTY_SUCCESS_RESPONSE on /api/auth/refresh — zero-byte response body"
        )
        titles = [r.metadata["title"] for r in results]
        assert any("auth" in t.lower() or "token" in t.lower() for t in titles)

    def test_checkout_query_retrieves_checkout_incident(self, retriever):
        results = retriever.get_relevant_documents(
            "SUB_THRESHOLD_ERROR_RATE on /api/checkout — 1.8% error rate"
        )
        types = [r.metadata["type"] for r in results]
        assert "SUB_THRESHOLD_ERROR_RATE" in types

    def test_metadata_contains_runbook(self, retriever):
        results = retriever.get_relevant_documents("latency spike on checkout payment")
        for r in results:
            assert "runbook" in r.metadata
            assert len(r.metadata["runbook"]) > 10

    def test_invoke_alias_works(self, retriever):
        results = retriever.invoke("empty response auth")
        assert len(results) == 2


# ─── RAGContextTool Tests ─────────────────────────────────────────────────

class TestRAGContextTool:

    def test_returns_valid_json(self, rag_tool_with_real_kb):
        result = rag_tool_with_real_kb._run(
            "EMPTY_SUCCESS_RESPONSE on /api/auth/refresh — 14 HTTP 200 with zero-byte body"
        )
        parsed = json.loads(result)
        assert "context" in parsed

    def test_retrieves_at_least_one_incident(self, rag_tool_with_real_kb):
        result = json.loads(rag_tool_with_real_kb._run(
            "EMPTY_SUCCESS_RESPONSE on /api/recommendations — empty payload on successful responses"
        ))
        assert result["retrieved_count"] >= 1

    def test_each_context_item_has_runbook(self, rag_tool_with_real_kb):
        result = json.loads(rag_tool_with_real_kb._run(
            "SUB_THRESHOLD_ERROR_RATE on /api/checkout — 1.8% error rate below 2% threshold"
        ))
        for item in result["context"]:
            assert "runbook" in item
            assert len(item["runbook"]) > 5

    def test_each_context_item_has_root_cause(self, rag_tool_with_real_kb):
        result = json.loads(rag_tool_with_real_kb._run(
            "LATENCY_SPIKE_ON_SUCCESS on /api/products — 6 requests at 3x average latency"
        ))
        for item in result["context"]:
            assert "root_cause" in item
            assert len(item["root_cause"]) > 10

    def test_each_context_item_has_business_impact(self, rag_tool_with_real_kb):
        result = json.loads(rag_tool_with_real_kb._run(
            "EMPTY_SUCCESS_RESPONSE on /api/auth — session writes silently failing"
        ))
        for item in result["context"]:
            assert "business_impact" in item

    def test_graceful_on_unrecognised_anomaly(self, rag_tool_with_real_kb):
        """Should still return results (TF-IDF always returns top-2), not crash."""
        result = json.loads(rag_tool_with_real_kb._run(
            "UNKNOWN_PATTERN on /api/very-obscure-endpoint"
        ))
        assert "context" in result


# ─── Integration: anomaly → RAG → enriched report ─────────────────────────

class TestRAGEnrichedReport:

    def test_reporter_renders_rag_context(self):
        """End-to-end: AnomalyDetectorTool output → RAGContextTool output → ReporterTool"""
        import agent.rag_context as rag_module
        from agent.silent_failure_detector import (
            AnomalyDetectorTool,
            SilentFailureReporterTool,
        )

        # Seed TF-IDF retriever
        incidents = _load_knowledge_base(KB_PATH)
        docs = _incidents_to_documents(incidents)
        rag_module._retriever_cache = _TFIDFRetriever(docs)
        rag_tool = RAGContextTool(kb_path=KB_PATH)

        # Step 1: Detect anomaly
        anomaly_entries = [
            {"status": 200, "path": "/api/auth/refresh", "response_size": 0,
             "duration_ms": 88, "method": "POST", "level": "INFO", "error": ""},
        ] * 8
        anomaly_data = AnomalyDetectorTool()._run(
            log_data=json.dumps({"entries": anomaly_entries, "total_entries": 8})
        )

        # Step 2: RAG retrieval
        rag_result = rag_tool._run(
            "EMPTY_SUCCESS_RESPONSE on /api/auth/refresh — 8 HTTP 200 with zero-byte body"
        )

        # Step 3: Generate report
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "enriched_report.md")
            report_result = SilentFailureReporterTool()._run(
                anomaly_data=anomaly_data,
                rag_context=rag_result,
                output_path=out,
            )
            assert os.path.exists(out)
            content = open(out).read()

            # Report should contain both detection and RAG-enriched context
            assert "EMPTY_SUCCESS_RESPONSE" in content or "Empty Success Response" in content
            assert "Similar past incidents" in content
            assert "Root cause" in content or "root_cause" in content.lower()
            assert "Runbook" in content
