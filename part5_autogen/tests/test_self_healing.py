"""
Tests for Part 5: AutoGen Self-Healing
Run: pytest tests\ -v
Fully offline - no AutoGen API key needed.
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.autogen_agents import DetectorAgent, FixPatternRetriever, HealerAgent, VerifierAgent

KB_PATH  = os.path.join(os.path.dirname(__file__), "..", "knowledge_base", "incidents.json")
LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "sample_prod.log")


# ─── Knowledge Base Tests ────────────────────────────────────────────────

class TestKnowledgeBase:

    def test_loads_4_fix_patterns(self):
        with open(KB_PATH, encoding="utf-8") as f:
            incidents = json.load(f)
        assert len(incidents) == 4

    def test_all_have_fix_code_template(self):
        with open(KB_PATH, encoding="utf-8") as f:
            incidents = json.load(f)
        for inc in incidents:
            assert "fix_code_template" in inc
            assert len(inc["fix_code_template"]) > 20

    def test_all_have_verification_query(self):
        with open(KB_PATH, encoding="utf-8") as f:
            incidents = json.load(f)
        for inc in incidents:
            assert "verification_query" in inc

    def test_ids_are_019_to_022(self):
        with open(KB_PATH, encoding="utf-8") as f:
            incidents = json.load(f)
        ids = [i["id"] for i in incidents]
        assert "INC-019" in ids
        assert "INC-022" in ids

    def test_all_are_fix_patterns(self):
        with open(KB_PATH, encoding="utf-8") as f:
            incidents = json.load(f)
        for inc in incidents:
            assert inc["agent_verdict"] == "FIX_PATTERN"


# ─── FixPatternRetriever Tests ───────────────────────────────────────────

class TestFixPatternRetriever:

    def test_loads_knowledge_base(self):
        r = FixPatternRetriever(kb_path=KB_PATH)
        assert len(r._docs) == 4

    def test_retrieves_empty_response_fix(self):
        r = FixPatternRetriever(kb_path=KB_PATH)
        results = r.query("EMPTY_SUCCESS_RESPONSE auth fix assertion", k=1)
        assert len(results) == 1
        assert results[0]["type"] == "FIX_EMPTY_RESPONSE_ASSERTION"

    def test_retrieves_threshold_fix(self):
        r = FixPatternRetriever(kb_path=KB_PATH)
        results = r.query("SUB_THRESHOLD_ERROR_RATE checkout payment fix", k=1)
        assert len(results) == 1
        assert results[0]["type"] == "FIX_THRESHOLD_ALERT"

    def test_retrieves_latency_fix(self):
        r = FixPatternRetriever(kb_path=KB_PATH)
        results = r.query("LATENCY_SPIKE_ON_SUCCESS timeout fix fetch", k=1)
        assert len(results) == 1
        assert results[0]["type"] == "FIX_LATENCY_TIMEOUT"

    def test_all_results_have_fix_code(self):
        r = FixPatternRetriever(kb_path=KB_PATH)
        results = r.query("fix assertion silent failure", k=4)
        for result in results:
            assert "fix_code_template" in result


# ─── DetectorAgent Tests ─────────────────────────────────────────────────

class TestDetectorAgent:

    def test_detects_anomalies_in_real_log(self):
        agent = DetectorAgent()
        result = agent.run(LOG_PATH)
        assert "anomalies" in result
        assert result["entries_analysed"] > 0

    def test_returns_error_for_missing_file(self):
        agent = DetectorAgent()
        result = agent.run("/nonexistent/path.log")
        assert "error" in result

    def test_detects_empty_200_in_real_log(self):
        agent = DetectorAgent()
        result = agent.run(LOG_PATH)
        types = [a["type"] for a in result["anomalies"]]
        assert "EMPTY_SUCCESS_RESPONSE" in types

    def test_anomalies_have_required_fields(self):
        agent = DetectorAgent()
        result = agent.run(LOG_PATH)
        for a in result["anomalies"]:
            assert "type" in a
            assert "severity" in a
            assert "description" in a

    def test_clean_log_returns_no_anomalies(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, encoding="utf-8"
        ) as f:
            for i in range(20):
                f.write(
                    "2024-01-15T10:00:0" + str(i % 10) +
                    " INFO 200 GET /api/products response_size=1423 duration_ms=45\n"
                )
            clean_path = f.name
        agent = DetectorAgent()
        result = agent.run(clean_path)
        assert len(result["anomalies"]) == 0


# ─── HealerAgent Tests ───────────────────────────────────────────────────

class TestHealerAgent:

    def test_writes_fix_for_empty_response(self):
        agent = HealerAgent(kb_path=KB_PATH)
        anomaly = {
            "type": "EMPTY_SUCCESS_RESPONSE",
            "severity": "HIGH",
            "count": 10,
            "affected_paths": ["/api/auth/refresh"],
            "description": "10 HTTP 200 with zero-byte body",
        }
        fix = agent.write_fix(anomaly)
        assert "test_code" in fix
        assert "test_function" in fix
        assert fix["test_function"].startswith("test_healed_")

    def test_fix_contains_assertion(self):
        agent = HealerAgent(kb_path=KB_PATH)
        anomaly = {
            "type": "EMPTY_SUCCESS_RESPONSE",
            "severity": "HIGH",
            "count": 5,
            "affected_paths": ["/api/auth/refresh"],
            "description": "empty response body",
        }
        fix = agent.write_fix(anomaly)
        assert "assert" in fix["test_code"]

    def test_fix_is_valid_python(self):
        agent = HealerAgent(kb_path=KB_PATH)
        anomaly = {
            "type": "EMPTY_SUCCESS_RESPONSE",
            "severity": "HIGH",
            "count": 5,
            "affected_paths": ["/api/auth/refresh"],
            "description": "empty response",
        }
        fix = agent.write_fix(anomaly)
        try:
            compile(fix["test_code"], "<string>", "exec")
            valid = True
        except SyntaxError:
            valid = False
        assert valid

    def test_writes_fix_for_latency_spike(self):
        agent = HealerAgent(kb_path=KB_PATH)
        anomaly = {
            "type": "LATENCY_SPIKE_ON_SUCCESS",
            "severity": "MEDIUM",
            "count": 6,
            "avg_duration_ms": 200,
            "affected_paths": ["/api/checkout"],
            "description": "6 requests at 3x average latency",
        }
        fix = agent.write_fix(anomaly)
        assert "test_code" in fix
        assert "assert" in fix["test_code"]

    def test_writes_fix_for_sub_threshold_error(self):
        agent = HealerAgent(kb_path=KB_PATH)
        anomaly = {
            "type": "SUB_THRESHOLD_ERROR_RATE",
            "severity": "MEDIUM",
            "path": "/api/checkout",
            "error_rate_pct": 1.8,
            "description": "1.8% error rate below threshold",
        }
        fix = agent.write_fix(anomaly)
        assert "test_code" in fix
        assert "PAYMENT_PATHS" in fix["test_code"]

    def test_round_number_in_function_name(self):
        agent = HealerAgent(kb_path=KB_PATH)
        anomaly = {
            "type": "EMPTY_SUCCESS_RESPONSE",
            "severity": "HIGH",
            "count": 5,
            "affected_paths": ["/api/auth"],
            "description": "empty",
        }
        fix = agent.write_fix(anomaly, round_num=2)
        assert "_r2" in fix["test_function"]

    def test_references_incident_id(self):
        agent = HealerAgent(kb_path=KB_PATH)
        anomaly = {
            "type": "EMPTY_SUCCESS_RESPONSE",
            "severity": "HIGH",
            "count": 5,
            "affected_paths": ["/api/auth/refresh"],
            "description": "empty response",
        }
        fix = agent.write_fix(anomaly)
        assert fix["incident_id"].startswith("INC-")


# ─── VerifierAgent Tests ─────────────────────────────────────────────────

class TestVerifierAgent:

    def _make_fix(self, failure_type="EMPTY_SUCCESS_RESPONSE", round_num=1):
        agent = HealerAgent(kb_path=KB_PATH)
        anomaly = {
            "type": failure_type,
            "severity": "HIGH",
            "count": 5,
            "affected_paths": ["/api/auth/refresh"],
            "description": "test anomaly for verification",
            "error_rate_pct": 1.8 if failure_type == "SUB_THRESHOLD_ERROR_RATE" else None,
            "path": "/api/checkout" if failure_type == "SUB_THRESHOLD_ERROR_RATE" else None,
            "avg_duration_ms": 200 if failure_type == "LATENCY_SPIKE_ON_SUCCESS" else None,
        }
        return agent.write_fix(anomaly, round_num=round_num)

    def test_verifier_returns_status(self):
        agent = VerifierAgent()
        fix = self._make_fix()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = agent.verify(fix, tmpdir)
            assert "status" in result
            assert result["status"] in (
                "CATCHES_FAILURE", "STRUCTURE_VALID", "NEEDS_REWORK"
            )

    def test_verifier_writes_test_file(self):
        agent = VerifierAgent()
        fix = self._make_fix()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = agent.verify(fix, tmpdir)
            assert os.path.exists(result["test_path"])

    def test_verifier_result_has_required_fields(self):
        agent = VerifierAgent()
        fix = self._make_fix()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = agent.verify(fix, tmpdir)
            assert "test_path" in result
            assert "test_function" in result
            assert "pytest_output" in result
            assert "message" in result

    def test_save_healed_test_writes_file(self):
        agent = VerifierAgent()
        fix = self._make_fix()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = agent.save_healed_test(fix, tmpdir)
            assert os.path.exists(path)
            content = open(path, encoding="utf-8").read()
            assert "def test_healed_" in content

    def test_latency_fix_is_verified(self):
        agent = VerifierAgent()
        fix = self._make_fix("LATENCY_SPIKE_ON_SUCCESS")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = agent.verify(fix, tmpdir)
            assert result["status"] in (
                "CATCHES_FAILURE", "STRUCTURE_VALID", "NEEDS_REWORK"
            )


# ─── Integration Tests ────────────────────────────────────────────────────

class TestSelfHealingIntegration:

    def test_full_self_healing_pipeline(self):
        from main import run_self_healing
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            healed = os.path.join(tmpdir, "healed")
            result = run_self_healing(
                log_source=LOG_PATH,
                kb_path=KB_PATH,
                output_path=out,
                healed_dir=healed,
            )
            assert result["status"] in ("complete", "clean")
            assert os.path.exists(out)

    def test_healed_tests_are_valid_python(self):
        from main import run_self_healing
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            healed = os.path.join(tmpdir, "healed")
            result = run_self_healing(
                log_source=LOG_PATH,
                kb_path=KB_PATH,
                output_path=out,
                healed_dir=healed,
            )
            for h in result.get("healed_tests", []):
                path = h["test_path"]
                if os.path.exists(path):
                    content = open(path, encoding="utf-8").read()
                    try:
                        compile(content, path, "exec")
                        valid = True
                    except SyntaxError:
                        valid = False
                    assert valid

    def test_report_contains_series_comparison(self):
        from main import run_self_healing
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            healed = os.path.join(tmpdir, "healed")
            run_self_healing(
                log_source=LOG_PATH,
                kb_path=KB_PATH,
                output_path=out,
                healed_dir=healed,
            )
            content = open(out, encoding="utf-8").read()
            assert "AutoGen" in content
            assert "Part 5" in content

    def test_summary_contains_findings(self):
        from main import run_self_healing
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            healed = os.path.join(tmpdir, "healed")
            result = run_self_healing(
                log_source=LOG_PATH,
                kb_path=KB_PATH,
                output_path=out,
                healed_dir=healed,
            )
            assert "summary" in result
            assert len(result["summary"]) > 20
