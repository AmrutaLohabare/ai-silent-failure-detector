"""
Tests for Part 6: Datadog + LLM Reasoning
Run: pytest tests\test_observability.py -v
Fully offline - no Datadog API, no OpenAI key needed.
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from collectors.observability_collectors import (
    LogCorrelator, MetricsCollector, TraceAnalyzer,
)
from analyzer.correlation_engine import CorrelationEngine
import rag.rag_context as rag_module
from rag.rag_context import retrieve, reset

KB_PATH   = os.path.join(os.path.dirname(__file__), "..", "knowledge_base", "incidents.json")
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "observability_snapshot.json")


@pytest.fixture(autouse=True)
def reset_rag():
    reset()
    yield
    reset()


# ─── MetricsCollector Tests ───────────────────────────────────────────────

class TestMetricsCollector:

    def test_loads_snapshot(self):
        c = MetricsCollector(DATA_PATH)
        assert c._snapshot is not None

    def test_detects_latency_trend(self):
        c = MetricsCollector(DATA_PATH)
        result = c.analyse()
        types = [f["type"] for f in result["findings"]]
        assert "LATENCY_TREND" in types

    def test_detects_sub_threshold_error(self):
        c = MetricsCollector(DATA_PATH)
        result = c.analyse()
        types = [f["type"] for f in result["findings"]]
        assert "SUB_THRESHOLD_ERROR_TREND" in types

    def test_detects_throughput_drop(self):
        c = MetricsCollector(DATA_PATH)
        result = c.analyse()
        types = [f["type"] for f in result["findings"]]
        assert "THROUGHPUT_DROP" in types

    def test_findings_have_signal_field(self):
        c = MetricsCollector(DATA_PATH)
        result = c.analyse()
        for f in result["findings"]:
            assert f.get("signal") == "metrics"

    def test_findings_have_severity(self):
        c = MetricsCollector(DATA_PATH)
        result = c.analyse()
        for f in result["findings"]:
            assert f.get("severity") in ("HIGH", "MEDIUM", "LOW")

    def test_returns_collector_name(self):
        c = MetricsCollector(DATA_PATH)
        result = c.analyse()
        assert result["collector"] == "MetricsCollector"

    def test_latency_finding_has_baseline_and_peak(self):
        c = MetricsCollector(DATA_PATH)
        result = c.analyse()
        latency = next((f for f in result["findings"] if f["type"] == "LATENCY_TREND"), None)
        assert latency is not None
        assert "baseline_ms" in latency
        assert "peak_ms" in latency
        assert latency["peak_ms"] > latency["baseline_ms"]


# ─── TraceAnalyzer Tests ──────────────────────────────────────────────────

class TestTraceAnalyzer:

    def test_loads_snapshot(self):
        a = TraceAnalyzer(DATA_PATH)
        assert a._snapshot is not None

    def test_detects_span_bottleneck(self):
        a = TraceAnalyzer(DATA_PATH)
        result = a.analyse()
        types = [f["type"] for f in result["findings"]]
        assert "TRACE_SPAN_BOTTLENECK" in types

    def test_identifies_payment_gateway_bottleneck(self):
        a = TraceAnalyzer(DATA_PATH)
        result = a.analyse()
        bottlenecks = [f for f in result["findings"] if f["type"] == "TRACE_SPAN_BOTTLENECK"]
        services = [b["service"] for b in bottlenecks]
        assert "payment-gateway" in services

    def test_findings_have_signal_field(self):
        a = TraceAnalyzer(DATA_PATH)
        result = a.analyse()
        for f in result["findings"]:
            assert f.get("signal") == "traces"

    def test_returns_traces_analysed_count(self):
        a = TraceAnalyzer(DATA_PATH)
        result = a.analyse()
        assert "traces_analysed" in result
        assert result["traces_analysed"] > 0

    def test_bottleneck_has_pct_of_trace(self):
        a = TraceAnalyzer(DATA_PATH)
        result = a.analyse()
        bottleneck = next(
            (f for f in result["findings"] if f["type"] == "TRACE_SPAN_BOTTLENECK"), None
        )
        assert bottleneck is not None
        assert bottleneck["avg_pct_of_trace"] > 80


# ─── LogCorrelator Tests ──────────────────────────────────────────────────

class TestLogCorrelator:

    def test_loads_snapshot(self):
        c = LogCorrelator(DATA_PATH)
        assert c._snapshot is not None

    def test_detects_silent_200(self):
        c = LogCorrelator(DATA_PATH)
        result = c.analyse()
        types = [f["type"] for f in result["findings"]]
        assert "SILENT_200_ON_FAILURE" in types

    def test_detects_idempotency_collision(self):
        c = LogCorrelator(DATA_PATH)
        result = c.analyse()
        types = [f["type"] for f in result["findings"]]
        assert "IDEMPOTENCY_COLLISION" in types

    def test_detects_retry_escalation(self):
        c = LogCorrelator(DATA_PATH)
        result = c.analyse()
        types = [f["type"] for f in result["findings"]]
        assert "RETRY_ESCALATION" in types

    def test_findings_have_signal_field(self):
        c = LogCorrelator(DATA_PATH)
        result = c.analyse()
        for f in result["findings"]:
            assert f.get("signal") == "logs"

    def test_returns_logs_analysed_count(self):
        c = LogCorrelator(DATA_PATH)
        result = c.analyse()
        assert "logs_analysed" in result
        assert result["logs_analysed"] > 0

    def test_silent_200_has_sample_messages(self):
        c = LogCorrelator(DATA_PATH)
        result = c.analyse()
        silent = next(
            (f for f in result["findings"] if f["type"] == "SILENT_200_ON_FAILURE"), None
        )
        assert silent is not None
        assert "sample_messages" in silent
        assert len(silent["sample_messages"]) > 0


# ─── CorrelationEngine Tests ──────────────────────────────────────────────

class TestCorrelationEngine:

    def _get_results(self):
        return (
            MetricsCollector(DATA_PATH).analyse(),
            TraceAnalyzer(DATA_PATH).analyse(),
            LogCorrelator(DATA_PATH).analyse(),
        )

    def test_correlates_all_signals(self):
        engine = CorrelationEngine()
        m, t, l = self._get_results()
        result = engine.correlate(m, t, l)
        assert result["status"] == "anomalies_detected"

    def test_detects_payment_gateway_pattern(self):
        engine = CorrelationEngine()
        m, t, l = self._get_results()
        result = engine.correlate(m, t, l)
        patterns = [c["pattern"] for c in result.get("correlated_anomalies", [])]
        assert "PAYMENT_GATEWAY_SILENT_DEGRADATION" in patterns

    def test_detects_duplicate_charge_risk(self):
        engine = CorrelationEngine()
        m, t, l = self._get_results()
        result = engine.correlate(m, t, l)
        patterns = [c["pattern"] for c in result.get("correlated_anomalies", [])]
        assert "DUPLICATE_CHARGE_RISK" in patterns

    def test_signals_firing_contains_all_three(self):
        engine = CorrelationEngine()
        m, t, l = self._get_results()
        result = engine.correlate(m, t, l)
        for signal in ("metrics", "traces", "logs"):
            assert signal in result["signals_firing"]

    def test_explanation_is_not_empty(self):
        engine = CorrelationEngine()
        m, t, l = self._get_results()
        result = engine.correlate(m, t, l)
        assert len(result.get("explanation", "")) > 20

    def test_clean_signals_return_clean_status(self):
        engine = CorrelationEngine()
        empty = {"findings": [], "findings_count": 0}
        result = engine.correlate(empty, empty, empty)
        assert result["status"] == "clean"


# ─── RAG Tests ────────────────────────────────────────────────────────────

class TestObservabilityRAG:

    def test_loads_4_incidents(self):
        with open(KB_PATH, encoding="utf-8") as f:
            incidents = json.load(f)
        assert len(incidents) == 4

    def test_ids_are_023_to_026(self):
        with open(KB_PATH, encoding="utf-8") as f:
            incidents = json.load(f)
        ids = [i["id"] for i in incidents]
        assert "INC-023" in ids
        assert "INC-026" in ids

    def test_all_have_signal_correlation(self):
        with open(KB_PATH, encoding="utf-8") as f:
            incidents = json.load(f)
        for inc in incidents:
            assert "signal_correlation" in inc

    def test_retrieves_payment_incident(self):
        result = json.loads(retrieve(
            "payment gateway latency silent retry stripe", kb_path=KB_PATH
        ))
        assert result["retrieved_count"] > 0
        ids = [c["incident_id"] for c in result["context"]]
        assert "INC-023" in ids

    def test_retrieves_trace_incident(self):
        result = json.loads(retrieve(
            "trace span bottleneck 94 percent payment", kb_path=KB_PATH
        ))
        assert result["retrieved_count"] > 0

    def test_context_has_signal_correlation(self):
        result = json.loads(retrieve("silent failure observability", kb_path=KB_PATH))
        for ctx in result["context"]:
            assert "signal_correlation" in ctx


# ─── Integration Tests ────────────────────────────────────────────────────

class TestIntegration:

    def test_full_pipeline(self):
        from main import run_detection
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            result = run_detection(
                data_path=DATA_PATH,
                kb_path=KB_PATH,
                output_path=out,
            )
            assert result["status"] == "complete"
            assert os.path.exists(out)

    def test_report_contains_series_comparison(self):
        from main import run_detection
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            run_detection(data_path=DATA_PATH, kb_path=KB_PATH, output_path=out)
            content = open(out, encoding="utf-8").read()
            assert "Part 6" in content
            assert "Metrics+Traces+Logs" in content

    def test_report_contains_rag_runbook(self):
        from main import run_detection
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            run_detection(data_path=DATA_PATH, kb_path=KB_PATH, output_path=out)
            content = open(out, encoding="utf-8").read()
            assert "Runbook" in content

    def test_all_3_signals_fire(self):
        from main import run_detection
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            result = run_detection(data_path=DATA_PATH, kb_path=KB_PATH, output_path=out)
            assert len(result["signals_firing"]) == 3
