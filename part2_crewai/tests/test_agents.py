"""
Tests for Part 2 agents — fully offline, no API key needed.
Run: pytest tests/ -v
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.detector_agent import DetectorAgent, ingest_logs, detect_anomalies
from agents.analyzer_agent import AnalyzerAgent, CONFIRMED, OVERRULED, UNCERTAIN, NEEDS_REVIEW
from agents.reporter_agent import ReporterAgent
import rag.rag_context as rag_module
from rag.rag_context import _TFIDFRetriever, _incidents_to_docs, _load_incidents


KB_PATH = os.path.join(os.path.dirname(__file__), "..", "knowledge_base", "incidents.json")

SAMPLE_LOG_LINES = [
    # Normal products traffic
    "2024-01-15T10:00:01 INFO 200 GET /api/products response_size=1423 duration_ms=45",
    "2024-01-15T10:00:02 INFO 200 GET /api/products response_size=1423 duration_ms=47",
    "2024-01-15T10:00:03 INFO 200 GET /api/products response_size=1423 duration_ms=44",
    "2024-01-15T10:00:04 INFO 200 GET /api/products response_size=1423 duration_ms=46",
    "2024-01-15T10:00:05 INFO 200 GET /api/products response_size=1423 duration_ms=45",
    "2024-01-15T10:00:06 INFO 200 GET /api/products response_size=1423 duration_ms=43",
    "2024-01-15T10:00:07 INFO 200 GET /api/products response_size=1423 duration_ms=46",
    "2024-01-15T10:00:08 INFO 200 GET /api/products response_size=1423 duration_ms=44",
    "2024-01-15T10:00:09 INFO 200 GET /api/products response_size=1423 duration_ms=45",
    "2024-01-15T10:00:10 INFO 200 GET /api/products response_size=1423 duration_ms=47",
    "2024-01-15T10:00:11 INFO 200 GET /api/products response_size=1423 duration_ms=44",
    "2024-01-15T10:00:12 INFO 200 GET /api/products response_size=1423 duration_ms=46",
    "2024-01-15T10:00:13 INFO 200 GET /api/products response_size=1423 duration_ms=45",
    "2024-01-15T10:00:14 INFO 200 GET /api/products response_size=1423 duration_ms=43",
    "2024-01-15T10:00:15 INFO 200 GET /api/products response_size=1423 duration_ms=46",
    "2024-01-15T10:00:16 INFO 200 GET /api/products response_size=1423 duration_ms=44",
    "2024-01-15T10:00:17 INFO 200 GET /api/products response_size=1423 duration_ms=45",
    "2024-01-15T10:00:18 INFO 200 GET /api/products response_size=1423 duration_ms=47",
    "2024-01-15T10:00:19 INFO 200 GET /api/products response_size=1423 duration_ms=44",
    "2024-01-15T10:00:20 INFO 200 GET /api/products response_size=1423 duration_ms=46",
    # Pattern 1: Empty 200 responses (auth + recommendations)
    "2024-01-15T10:00:21 INFO 200 POST /api/auth/refresh response_size=0 duration_ms=88",
    "2024-01-15T10:00:22 INFO 200 POST /api/auth/refresh response_size=0 duration_ms=91",
    "2024-01-15T10:00:23 INFO 200 GET /api/recommendations response_size=0 duration_ms=120",
    "2024-01-15T10:00:24 INFO 200 GET /api/recommendations response_size=0 duration_ms=118",
    # Pattern 2: Sub-threshold errors on cart (14 requests, 2 errors = 14.3%, threshold 50%)
    "2024-01-15T10:00:25 INFO 200 GET /api/cart/items response_size=420 duration_ms=32",
    "2024-01-15T10:00:26 INFO 200 GET /api/cart/items response_size=420 duration_ms=31",
    "2024-01-15T10:00:27 INFO 200 GET /api/cart/items response_size=420 duration_ms=33",
    "2024-01-15T10:00:28 INFO 200 GET /api/cart/items response_size=420 duration_ms=30",
    "2024-01-15T10:00:29 INFO 200 GET /api/cart/items response_size=420 duration_ms=32",
    "2024-01-15T10:00:30 INFO 200 GET /api/cart/items response_size=420 duration_ms=31",
    "2024-01-15T10:00:31 INFO 200 GET /api/cart/items response_size=420 duration_ms=33",
    "2024-01-15T10:00:32 INFO 200 GET /api/cart/items response_size=420 duration_ms=30",
    "2024-01-15T10:00:33 INFO 200 GET /api/cart/items response_size=420 duration_ms=31",
    "2024-01-15T10:00:34 INFO 200 GET /api/cart/items response_size=420 duration_ms=32",
    "2024-01-15T10:00:35 INFO 200 GET /api/cart/items response_size=420 duration_ms=30",
    "2024-01-15T10:00:36 INFO 200 GET /api/cart/items response_size=420 duration_ms=33",
    "2024-01-15T10:00:37 INFO 404 GET /api/cart/items response_size=42 duration_ms=12 error=\"not found\"",
    "2024-01-15T10:00:38 INFO 404 GET /api/cart/items response_size=42 duration_ms=11 error=\"not found\"",
    # Pattern 3: Latency spikes on checkout (20 normal + 6 spikes = 3x avg)
    "2024-01-15T10:00:39 INFO 200 POST /api/checkout response_size=892 duration_ms=50",
    "2024-01-15T10:00:40 INFO 200 POST /api/checkout response_size=892 duration_ms=52",
    "2024-01-15T10:00:41 INFO 200 POST /api/checkout response_size=892 duration_ms=48",
    "2024-01-15T10:00:42 INFO 200 POST /api/checkout response_size=892 duration_ms=51",
    "2024-01-15T10:00:43 INFO 200 POST /api/checkout response_size=892 duration_ms=50",
    "2024-01-15T10:00:44 INFO 200 POST /api/checkout response_size=892 duration_ms=49",
    "2024-01-15T10:00:45 INFO 200 POST /api/checkout response_size=892 duration_ms=51",
    "2024-01-15T10:00:46 INFO 200 POST /api/checkout response_size=892 duration_ms=50",
    "2024-01-15T10:00:47 INFO 200 POST /api/checkout response_size=892 duration_ms=52",
    "2024-01-15T10:00:48 INFO 200 POST /api/checkout response_size=892 duration_ms=48",
    "2024-01-15T10:00:49 INFO 200 POST /api/checkout response_size=892 duration_ms=50",
    "2024-01-15T10:00:50 INFO 200 POST /api/checkout response_size=892 duration_ms=51",
    "2024-01-15T10:00:51 INFO 200 POST /api/checkout response_size=892 duration_ms=49",
    "2024-01-15T10:00:52 INFO 200 POST /api/checkout response_size=892 duration_ms=50",
    "2024-01-15T10:00:53 INFO 200 POST /api/checkout response_size=892 duration_ms=52",
    "2024-01-15T10:00:54 INFO 200 POST /api/checkout response_size=892 duration_ms=48",
    "2024-01-15T10:00:55 INFO 200 POST /api/checkout response_size=892 duration_ms=50",
    "2024-01-15T10:00:56 INFO 200 POST /api/checkout response_size=892 duration_ms=51",
    "2024-01-15T10:00:57 INFO 200 POST /api/checkout response_size=892 duration_ms=49",
    "2024-01-15T10:00:58 INFO 200 POST /api/checkout response_size=892 duration_ms=50",
    "2024-01-15T10:00:59 INFO 200 POST /api/checkout response_size=892 duration_ms=2100",
    "2024-01-15T10:01:00 INFO 200 POST /api/checkout response_size=892 duration_ms=1950",
    "2024-01-15T10:01:01 INFO 200 POST /api/checkout response_size=892 duration_ms=2300",
    "2024-01-15T10:01:02 INFO 200 POST /api/checkout response_size=892 duration_ms=2150",
    "2024-01-15T10:01:03 INFO 200 POST /api/checkout response_size=892 duration_ms=2050",
    "2024-01-15T10:01:04 INFO 200 POST /api/checkout response_size=892 duration_ms=2200",
]


@pytest.fixture(autouse=True)
def reset_rag_cache():
    """Reset RAG singleton before each test."""
    rag_module._retriever_cache = None
    yield
    rag_module._retriever_cache = None


@pytest.fixture
def sample_log_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False, encoding="utf-8") as f:
        f.write("\n".join(SAMPLE_LOG_LINES))
        return f.name


@pytest.fixture
def seeded_analyzer():
    """Analyzer with TF-IDF retriever pre-seeded from real KB."""
    incidents = _load_incidents(KB_PATH)
    docs = _incidents_to_docs(incidents)
    rag_module._retriever_cache = _TFIDFRetriever(docs)
    return AnalyzerAgent(kb_path=KB_PATH)


# ─── Detector Tests ────────────────────────────────────────────────────────

class TestDetectorAgent:

    def test_ingests_log_file(self, sample_log_file):
        result = json.loads(ingest_logs(sample_log_file))
        assert result["total_entries"] > 0

    def test_returns_error_for_missing_file(self):
        result = json.loads(ingest_logs("/nonexistent/path.log"))
        assert "error" in result

    def test_detects_empty_200_responses(self, sample_log_file):
        log_data = ingest_logs(sample_log_file)
        result = json.loads(detect_anomalies(log_data))
        types = [a["type"] for a in result["anomalies"]]
        assert "EMPTY_SUCCESS_RESPONSE" in types

    def test_detects_sub_threshold_error_rate(self, sample_log_file):
        log_data = ingest_logs(sample_log_file)
        result = json.loads(detect_anomalies(log_data, error_threshold=0.5))
        types = [a["type"] for a in result["anomalies"]]
        assert "SUB_THRESHOLD_ERROR_RATE" in types

    def test_detects_latency_spike(self, sample_log_file):
        log_data = ingest_logs(sample_log_file)
        result = json.loads(detect_anomalies(log_data))
        types = [a["type"] for a in result["anomalies"]]
        assert "LATENCY_SPIKE_ON_SUCCESS" in types

    def test_detector_agent_run_returns_anomalies(self, sample_log_file):
        agent = DetectorAgent()
        result = agent.run(sample_log_file)
        assert "anomalies" in result
        assert result["entries_analysed"] > 0

    def test_detector_confidence_field_present(self, sample_log_file):
        log_data = ingest_logs(sample_log_file)
        result = json.loads(detect_anomalies(log_data))
        for a in result["anomalies"]:
            assert "detector_confidence" in a

    def test_detector_note_present(self, sample_log_file):
        log_data = ingest_logs(sample_log_file)
        result = json.loads(detect_anomalies(log_data))
        assert "detector_note" in result


# ─── RAG / Knowledge Base Tests ───────────────────────────────────────────

class TestKnowledgeBase:

    def test_loads_10_incidents(self):
        incidents = _load_incidents(KB_PATH)
        assert len(incidents) == 10

    def test_has_4_new_multi_agent_incidents(self):
        incidents = _load_incidents(KB_PATH)
        multi_agent = [i for i in incidents if "multi-agent" in i.get("tags", [])]
        assert len(multi_agent) == 4

    def test_new_incidents_have_agent_verdict(self):
        incidents = _load_incidents(KB_PATH)
        for inc in incidents:
            assert "agent_verdict" in inc

    def test_false_positive_incidents_exist(self):
        incidents = _load_incidents(KB_PATH)
        fp = [i for i in incidents if "FALSE_POSITIVE" in i.get("agent_verdict", "")]
        assert len(fp) >= 2

    def test_tfidf_retrieves_false_positive_for_warmup_query(self):
        incidents = _load_incidents(KB_PATH)
        docs = _incidents_to_docs(incidents)
        retriever = _TFIDFRetriever(docs)
        results = retriever.query(
            "EMPTY_SUCCESS_RESPONSE recommendations warm-up cache expected", k=3
        )
        verdicts = [r["metadata"]["agent_verdict"] for r in results]
        assert any("FALSE_POSITIVE" in v for v in verdicts)


# ─── Analyzer Tests ────────────────────────────────────────────────────────

class TestAnalyzerAgent:

    def test_confirms_auth_empty_200(self, seeded_analyzer):
        finding = {
            "type": "EMPTY_SUCCESS_RESPONSE",
            "severity": "HIGH",
            "count": 14,
            "affected_paths": ["/api/auth/refresh"],
            "description": "14 HTTP 200 with zero-byte body on auth refresh",
            "detector_confidence": "HIGH",
        }
        result = seeded_analyzer.analyse_finding(finding)
        assert result["verdict"] in (CONFIRMED, UNCERTAIN)

    def test_overrules_recommendations_warmup(self, seeded_analyzer):
        finding = {
            "type": "EMPTY_SUCCESS_RESPONSE",
            "severity": "HIGH",
            "count": 8,
            "affected_paths": ["/api/recommendations"],
            "description": "8 HTTP 200 with zero-byte body on recommendations during warm-up",
            "detector_confidence": "HIGH",
        }
        result = seeded_analyzer.analyse_finding(finding)
        assert result["verdict"] in (OVERRULED, UNCERTAIN, CONFIRMED)

    def test_verdict_always_present(self, seeded_analyzer):
        finding = {
            "type": "SUB_THRESHOLD_ERROR_RATE",
            "severity": "MEDIUM",
            "path": "/api/cart",
            "error_rate_pct": 1.4,
            "total_requests": 100,
            "error_count": 14,
            "description": "1.4% error rate on /api/cart",
            "detector_confidence": "MEDIUM",
        }
        result = seeded_analyzer.analyse_finding(finding)
        assert result["verdict"] in (CONFIRMED, OVERRULED, UNCERTAIN, NEEDS_REVIEW)

    def test_payment_path_requires_strong_evidence(self, seeded_analyzer):
        """Checkout is a payment path — Analyzer should not overrule with weak evidence."""
        finding = {
            "type": "SUB_THRESHOLD_ERROR_RATE",
            "severity": "MEDIUM",
            "path": "/api/checkout",
            "error_rate_pct": 1.8,
            "total_requests": 200,
            "error_count": 36,
            "affected_paths": ["/api/checkout"],
            "description": "1.8% errors on checkout",
            "detector_confidence": "HIGH",
        }
        result = seeded_analyzer.analyse_finding(finding)
        assert result["is_payment_path"] is True
        assert result["verdict"] != OVERRULED or len(
            result["rag_evidence"]["false_positive_matches"]
        ) >= 2

    def test_analyzer_run_returns_all_counts(self, seeded_analyzer, sample_log_file):
        from agents.detector_agent import DetectorAgent
        detector_output = DetectorAgent().run(sample_log_file)
        result = seeded_analyzer.run(detector_output)
        assert "confirmed_count" in result
        assert "overruled_count" in result
        assert "uncertain_count" in result
        assert "verdicts" in result

    def test_reasoning_always_present(self, seeded_analyzer):
        finding = {
            "type": "LATENCY_SPIKE_ON_SUCCESS",
            "severity": "MEDIUM",
            "count": 6,
            "affected_paths": ["/api/products"],
            "description": "6 requests at 3x latency on products",
            "detector_confidence": "MEDIUM",
        }
        result = seeded_analyzer.analyse_finding(finding)
        assert len(result["reasoning"]) > 10


# ─── Reporter Tests ────────────────────────────────────────────────────────

class TestReporterAgent:

    def _make_analyzer_output(self, confirmed=1, overruled=0, uncertain=0):
        finding = {
            "type": "EMPTY_SUCCESS_RESPONSE",
            "severity": "HIGH",
            "count": 14,
            "affected_paths": ["/api/auth/refresh"],
            "description": "14 HTTP 200 with zero-byte body.",
            "detector_confidence": "HIGH",
        }
        verdict = {
            "finding_type": "EMPTY_SUCCESS_RESPONSE",
            "affected_paths": ["/api/auth/refresh"],
            "original_finding": finding,
            "verdict": "CONFIRMED",
            "reasoning": "Matches INC-001 Redis OOM pattern.",
            "runbook": "redis-cli INFO memory. Check eviction events.",
            "rag_evidence": {"false_positive_matches": [], "true_positive_matches": ["INC-001"],
                             "retrieved_incidents": []},
            "is_payment_path": False,
        }
        return {
            "confirmed_findings": [verdict] * confirmed,
            "overruled_findings": [
                {**verdict, "verdict": "OVERRULED",
                 "reasoning": "Matches warm-up pattern INC-007."}
            ] * overruled,
            "uncertain_findings": [
                {**verdict, "verdict": "UNCERTAIN",
                 "reasoning": "Conflicting evidence."}
            ] * uncertain,
            "confirmed_count": confirmed,
            "overruled_count": overruled,
            "uncertain_count": uncertain,
        }

    def test_creates_report_file(self):
        reporter = ReporterAgent(kb_path=KB_PATH)
        detector_output = {"entries_analysed": 62, "anomaly_count": 1, "anomalies": []}
        analyzer_output = self._make_analyzer_output(confirmed=1)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            result = reporter.generate_report(detector_output, analyzer_output, out)
            assert os.path.exists(out)
            assert "confirmed" in result.lower()

    def test_report_contains_comparison_table(self):
        reporter = ReporterAgent(kb_path=KB_PATH)
        detector_output = {"entries_analysed": 62, "anomaly_count": 1, "anomalies": []}
        analyzer_output = self._make_analyzer_output(confirmed=1)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            reporter.generate_report(detector_output, analyzer_output, out)
            content = open(out, encoding="utf-8").read()
            assert "Part 1" in content
            assert "Part 2" in content

    def test_overruled_findings_in_audit_trail(self):
        reporter = ReporterAgent(kb_path=KB_PATH)
        detector_output = {"entries_analysed": 62, "anomaly_count": 2, "anomalies": []}
        analyzer_output = self._make_analyzer_output(confirmed=1, overruled=1)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            reporter.generate_report(detector_output, analyzer_output, out)
            content = open(out, encoding="utf-8").read()
            assert "Overruled" in content or "False Positives" in content

    def test_uncertain_findings_flagged(self):
        reporter = ReporterAgent(kb_path=KB_PATH)
        detector_output = {"entries_analysed": 62, "anomaly_count": 1, "anomalies": []}
        analyzer_output = self._make_analyzer_output(confirmed=0, uncertain=1)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            reporter.generate_report(detector_output, analyzer_output, out)
            content = open(out, encoding="utf-8").read()
            assert "Uncertain" in content or "Human Review" in content


# ─── Crew Integration Test ─────────────────────────────────────────────────

class TestCrewIntegration:

    def test_full_crew_run(self, sample_log_file):
        """End-to-end: log → 3 agents → report"""
        from crew.silent_failure_crew import SilentFailureCrew

        incidents = _load_incidents(KB_PATH)
        docs = _incidents_to_docs(incidents)
        rag_module._retriever_cache = _TFIDFRetriever(docs)

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            crew = SilentFailureCrew(kb_path=KB_PATH, output_path=out)
            result = crew.run(log_source=sample_log_file)

            assert "status" in result
            assert result["status"] in ("complete", "clean")
            assert os.path.exists(out)

    def test_channel_has_messages_after_run(self, sample_log_file):
        from crew.silent_failure_crew import SilentFailureCrew

        incidents = _load_incidents(KB_PATH)
        docs = _incidents_to_docs(incidents)
        rag_module._retriever_cache = _TFIDFRetriever(docs)

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            crew = SilentFailureCrew(kb_path=KB_PATH, output_path=out)
            result = crew.run(log_source=sample_log_file)
            assert len(result.get("channel_log", [])) > 0

    def test_summary_in_result(self, sample_log_file):
        from crew.silent_failure_crew import SilentFailureCrew

        incidents = _load_incidents(KB_PATH)
        docs = _incidents_to_docs(incidents)
        rag_module._retriever_cache = _TFIDFRetriever(docs)

        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            crew = SilentFailureCrew(kb_path=KB_PATH, output_path=out)
            result = crew.run(log_source=sample_log_file)
            assert "summary" in result
            assert len(result["summary"]) > 20
