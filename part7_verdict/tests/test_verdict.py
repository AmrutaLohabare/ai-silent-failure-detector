"""
Tests for Part 7: The Honest Verdict
Run: pytest tests\test_verdict.py -v
Fully offline - tests static metadata and report generation.
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from comparison.comparison_engine import PART_METADATA, ComparisonEngine

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
LOG_PATH = os.path.join(BASE_DIR, "part1_langchain", "logs", "sample_prod.log")


# ─── Metadata Tests ───────────────────────────────────────────────────────

class TestPartMetadata:

    def test_has_6_parts(self):
        assert len(PART_METADATA) == 6

    def test_all_parts_present(self):
        keys = list(PART_METADATA.keys())
        assert "part1_langchain"       in keys
        assert "part2_crewai"          in keys
        assert "part3_playwright"      in keys
        assert "part4_semantic_kernel" in keys
        assert "part5_autogen"         in keys
        assert "part6_datadog"         in keys

    def test_all_have_required_fields(self):
        required = [
            "name", "part", "tests", "best_for",
            "avoid_when", "key_innovation", "complexity",
        ]
        for key, meta in PART_METADATA.items():
            for field in required:
                assert field in meta, key + " missing: " + field

    def test_total_tests_is_184(self):
        total = sum(m["tests"] for m in PART_METADATA.values())
        assert total == 184

    def test_only_part1_requires_api_key(self):
        for key, meta in PART_METADATA.items():
            if key == "part1_langchain":
                assert meta["api_key_required"] is True
            else:
                assert meta["api_key_required"] is False

    def test_part_numbers_are_1_to_6(self):
        parts = sorted(m["part"] for m in PART_METADATA.values())
        assert parts == [1, 2, 3, 4, 5, 6]

    def test_multi_agent_only_parts_2_and_5(self):
        multi = [k for k, m in PART_METADATA.items() if m["multi_agent"]]
        assert "part2_crewai"   in multi
        assert "part5_autogen"  in multi
        assert len(multi) == 2

    def test_part6_has_most_tests(self):
        tests = {k: m["tests"] for k, m in PART_METADATA.items()}
        assert tests["part6_datadog"] == max(tests.values())


# ─── Comparison Engine Tests ──────────────────────────────────────────────

class TestComparisonEngine:

    def test_initialises_with_base_dir(self):
        engine = ComparisonEngine(base_dir=BASE_DIR)
        assert engine._base == BASE_DIR

    def test_report_created(self):
        engine = ComparisonEngine(base_dir=BASE_DIR)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            result = engine.run_comparison(log_source=LOG_PATH, output_path=out)
            assert os.path.exists(out)

    def test_report_contains_all_6_parts(self):
        engine = ComparisonEngine(base_dir=BASE_DIR)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            engine.run_comparison(log_source=LOG_PATH, output_path=out)
            content = open(out, encoding="utf-8").read()
            for name in ["LangChain", "CrewAI", "Playwright",
                         "Semantic Kernel", "AutoGen", "Datadog"]:
                assert name in content

    def test_report_contains_honest_verdict_section(self):
        engine = ComparisonEngine(base_dir=BASE_DIR)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            engine.run_comparison(log_source=LOG_PATH, output_path=out)
            content = open(out, encoding="utf-8").read()
            assert "Honest Verdict" in content

    def test_report_contains_biggest_lesson(self):
        engine = ComparisonEngine(base_dir=BASE_DIR)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            engine.run_comparison(log_source=LOG_PATH, output_path=out)
            content = open(out, encoding="utf-8").read()
            assert "Biggest Lesson" in content

    def test_report_contains_knowledge_base_journey(self):
        engine = ComparisonEngine(base_dir=BASE_DIR)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            engine.run_comparison(log_source=LOG_PATH, output_path=out)
            content = open(out, encoding="utf-8").read()
            assert "Knowledge Base Journey" in content
            assert "26 incidents" in content

    def test_report_contains_github_link(self):
        engine = ComparisonEngine(base_dir=BASE_DIR)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            engine.run_comparison(log_source=LOG_PATH, output_path=out)
            content = open(out, encoding="utf-8").read()
            assert "AmrutaLohabare" in content

    def test_result_has_status_complete(self):
        engine = ComparisonEngine(base_dir=BASE_DIR)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            result = engine.run_comparison(log_source=LOG_PATH, output_path=out)
            assert result["status"] == "complete"

    def test_result_has_all_6_results(self):
        engine = ComparisonEngine(base_dir=BASE_DIR)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            result = engine.run_comparison(log_source=LOG_PATH, output_path=out)
            assert len(result["results"]) == 6

    def test_timings_recorded_for_all_parts(self):
        engine = ComparisonEngine(base_dir=BASE_DIR)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            result = engine.run_comparison(log_source=LOG_PATH, output_path=out)
            for i in range(1, 7):
                assert "part" + str(i) in result["timings"]

    def test_report_utf8_encoded(self):
        engine = ComparisonEngine(base_dir=BASE_DIR)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            engine.run_comparison(log_source=LOG_PATH, output_path=out)
            content = open(out, encoding="utf-8").read()
            assert len(content) > 500


# ─── Integration via main.py ──────────────────────────────────────────────

class TestMain:

    def test_run_comparison_importable(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "part7_main",
            os.path.join(os.path.dirname(__file__), "..", "main.py")
        )
        mod = importlib.util.load_from_spec = spec
        part7_main = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(part7_main)
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            result = part7_main.run_comparison(
                log_source=LOG_PATH,
                output_path=out,
                base_dir=BASE_DIR,
            )
            assert result["status"] == "complete"
            assert os.path.exists(out)
