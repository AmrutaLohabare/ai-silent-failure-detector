"""
Tests for the AI Silent Failure Detector tools.
Run: pytest tests/ -v
"""

import json
import os
import tempfile

import pytest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.silent_failure_detector import (
    AnomalyDetectorTool,
    LogIngestionTool,
    SilentFailureReporterTool,
)


# ─── Fixtures ──────────────────────────────────────────────────────────────

SAMPLE_LOG_LINES = [
    "2024-01-15T10:00:01 INFO 200 GET /api/products response_size=1423 duration_ms=45",
    "2024-01-15T10:00:02 INFO 200 POST /api/auth/refresh response_size=0 duration_ms=88",
    "2024-01-15T10:00:03 INFO 200 GET /api/recommendations response_size=0 duration_ms=120",
    "2024-01-15T10:00:04 INFO 404 GET /api/cart/items response_size=42 duration_ms=12 error=\"resource not found\"",
    "2024-01-15T10:00:05 INFO 200 GET /api/products response_size=1423 duration_ms=45",
    "2024-01-15T10:00:06 INFO 404 GET /api/cart/items response_size=42 duration_ms=11 error=\"resource not found\"",
    "2024-01-15T10:00:07 INFO 200 GET /api/products response_size=1423 duration_ms=44",
    "2024-01-15T10:00:08 INFO 404 GET /api/cart/items response_size=42 duration_ms=13 error=\"not found\"",
    "2024-01-15T10:00:09 INFO 200 GET /api/products response_size=1423 duration_ms=46",
    "2024-01-15T10:00:10 INFO 200 POST /api/checkout response_size=892 duration_ms=210",
    "2024-01-15T10:00:11 INFO 200 GET /api/products response_size=1423 duration_ms=2100",
    "2024-01-15T10:00:12 INFO 200 GET /api/products response_size=1423 duration_ms=1950",
    "2024-01-15T10:00:13 INFO 200 GET /api/products response_size=1423 duration_ms=2300",
]


@pytest.fixture
def sample_log_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write("\n".join(SAMPLE_LOG_LINES))
        return f.name


@pytest.fixture
def ingestion_tool():
    return LogIngestionTool()


@pytest.fixture
def anomaly_tool():
    return AnomalyDetectorTool()


@pytest.fixture
def reporter_tool():
    return SilentFailureReporterTool()


# ─── LogIngestionTool Tests ────────────────────────────────────────────────

class TestLogIngestionTool:

    def test_ingests_valid_log_file(self, ingestion_tool, sample_log_file):
        result = json.loads(ingestion_tool._run(source=sample_log_file))
        assert "entries" in result
        assert result["total_entries"] > 0

    def test_returns_error_for_missing_file(self, ingestion_tool):
        result = json.loads(ingestion_tool._run(source="/nonexistent/path.log"))
        assert "error" in result

    def test_parses_status_code_correctly(self, ingestion_tool, sample_log_file):
        result = json.loads(ingestion_tool._run(source=sample_log_file))
        statuses = {e["status"] for e in result["entries"]}
        assert 200 in statuses
        assert 404 in statuses

    def test_parses_response_size(self, ingestion_tool, sample_log_file):
        result = json.loads(ingestion_tool._run(source=sample_log_file))
        sizes = [e["response_size"] for e in result["entries"]]
        assert 0 in sizes       # empty responses exist
        assert 1423 in sizes    # normal responses exist

    def test_ignores_blank_lines(self, ingestion_tool):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("\n\n" + SAMPLE_LOG_LINES[0] + "\n\n")
            path = f.name
        result = json.loads(ingestion_tool._run(source=path))
        assert result["total_entries"] == 1


# ─── AnomalyDetectorTool Tests ─────────────────────────────────────────────

class TestAnomalyDetectorTool:

    def _make_log_json(self, entries):
        return json.dumps({"entries": entries, "total_entries": len(entries)})

    def test_detects_empty_200_responses(self, anomaly_tool):
        entries = [
            {"status": 200, "path": "/api/auth/refresh", "response_size": 0,
             "duration_ms": 88, "method": "POST", "level": "INFO", "error": ""},
        ] * 5
        result = json.loads(anomaly_tool._run(log_data=self._make_log_json(entries)))
        types = [a["type"] for a in result["anomalies"]]
        assert "EMPTY_SUCCESS_RESPONSE" in types

    def test_detects_sub_threshold_error_rate(self, anomaly_tool):
        # 15 requests to /api/cart — 2 errors = 13.3% — but threshold is 15%
        entries = (
            [{"status": 200, "path": "/api/cart", "response_size": 100,
              "duration_ms": 50, "method": "GET", "level": "INFO", "error": ""}] * 13
            +
            [{"status": 404, "path": "/api/cart", "response_size": 42,
              "duration_ms": 12, "method": "GET", "level": "INFO", "error": "not found"}] * 2
        )
        result = json.loads(anomaly_tool._run(
            log_data=self._make_log_json(entries),
            error_threshold=0.15,
        ))
        types = [a["type"] for a in result["anomalies"]]
        assert "SUB_THRESHOLD_ERROR_RATE" in types

    def test_detects_latency_spike(self, anomaly_tool):
        # Normal requests ~50ms, then 6 spikes at 1000ms+ (> 3x average)
        entries = (
            [{"status": 200, "path": "/api/checkout", "response_size": 892,
              "duration_ms": 50, "method": "POST", "level": "INFO", "error": ""}] * 20
            +
            [{"status": 200, "path": "/api/checkout", "response_size": 892,
              "duration_ms": 2000, "method": "POST", "level": "INFO", "error": ""}] * 6
        )
        result = json.loads(anomaly_tool._run(log_data=self._make_log_json(entries)))
        types = [a["type"] for a in result["anomalies"]]
        assert "LATENCY_SPIKE_ON_SUCCESS" in types

    def test_returns_zero_anomalies_for_clean_logs(self, anomaly_tool):
        entries = [
            {"status": 200, "path": "/api/products", "response_size": 1423,
             "duration_ms": 45, "method": "GET", "level": "INFO", "error": ""}
        ] * 50
        result = json.loads(anomaly_tool._run(log_data=self._make_log_json(entries)))
        assert result["anomaly_count"] == 0

    def test_handles_empty_entries(self, anomaly_tool):
        result = json.loads(anomaly_tool._run(log_data=self._make_log_json([])))
        assert result["anomaly_count"] == 0

    def test_severity_is_high_for_empty_200(self, anomaly_tool):
        entries = [
            {"status": 200, "path": "/api/auth/refresh", "response_size": 0,
             "duration_ms": 88, "method": "POST", "level": "INFO", "error": ""},
        ] * 5
        result = json.loads(anomaly_tool._run(log_data=self._make_log_json(entries)))
        empty_anomaly = next(
            (a for a in result["anomalies"] if a["type"] == "EMPTY_SUCCESS_RESPONSE"), None
        )
        assert empty_anomaly is not None
        assert empty_anomaly["severity"] == "HIGH"


# ─── SilentFailureReporterTool Tests ──────────────────────────────────────

class TestSilentFailureReporterTool:

    SAMPLE_ANOMALY_DATA = json.dumps({
        "anomaly_count": 1,
        "entries_analysed": 100,
        "anomalies": [{
            "type": "EMPTY_SUCCESS_RESPONSE",
            "severity": "HIGH",
            "count": 12,
            "affected_paths": ["/api/auth/refresh"],
            "description": "12 requests returned HTTP 200 with zero-byte body.",
        }],
    })

    def test_creates_report_file(self, reporter_tool):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            result = reporter_tool._run(anomaly_data=self.SAMPLE_ANOMALY_DATA, output_path=out)
            assert os.path.exists(out)
            assert "1 silent failure(s) found" in result

    def test_report_contains_anomaly_type(self, reporter_tool):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            reporter_tool._run(anomaly_data=self.SAMPLE_ANOMALY_DATA, output_path=out)
            content = open(out).read()
            assert "Empty Success Response" in content

    def test_report_contains_high_severity_marker(self, reporter_tool):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            reporter_tool._run(anomaly_data=self.SAMPLE_ANOMALY_DATA, output_path=out)
            content = open(out).read()
            assert "HIGH" in content

    def test_clean_report_when_no_anomalies(self, reporter_tool):
        clean = json.dumps({"anomaly_count": 0, "entries_analysed": 50, "anomalies": []})
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            reporter_tool._run(anomaly_data=clean, output_path=out)
            content = open(out).read()
            assert "No silent failures detected" in content
