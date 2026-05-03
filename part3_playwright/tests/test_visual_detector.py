"""
Tests for Part 3: Playwright + AI Vision
Run: pytest tests/ -v
Fully offline — no Playwright, no OpenAI key needed for core tests.
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from detector.visual_detector import check_dom_state, pixel_diff, vision_analyse
import rag.rag_context as rag_module
from rag.rag_context import _TFIDFRetriever, retrieve, get_retriever

KB_PATH     = os.path.join(os.path.dirname(__file__), "..", "knowledge_base", "incidents.json")
PAGES_DIR   = os.path.join(os.path.dirname(__file__), "..", "pages")
HEALTHY     = os.path.join(PAGES_DIR, "checkout_healthy.html")
BROKEN      = os.path.join(PAGES_DIR, "checkout_broken.html")


@pytest.fixture(autouse=True)
def reset_rag():
    rag_module._retriever_cache = None
    yield
    rag_module._retriever_cache = None


# ─── DOM Analysis Tests ───────────────────────────────────────────────────

class TestDOMAnalysis:

    def test_detects_invisible_button_in_broken_page(self):
        issues = check_dom_state(BROKEN)
        types = [i["type"] for i in issues]
        assert "INVISIBLE_ELEMENT" in types

    def test_detects_stuck_spinner_in_broken_page(self):
        issues = check_dom_state(BROKEN)
        types = [i["type"] for i in issues]
        assert "STUCK_SPINNER" in types

    def test_detects_offscreen_modal_in_broken_page(self):
        issues = check_dom_state(BROKEN)
        types = [i["type"] for i in issues]
        assert "MISSING_CONFIRMATION" in types

    def test_detects_empty_section_in_broken_page(self):
        issues = check_dom_state(BROKEN)
        types = [i["type"] for i in issues]
        assert "EMPTY_CONTENT_SECTION" in types

    def test_finds_4_issues_in_broken_page(self):
        issues = check_dom_state(BROKEN)
        assert len(issues) == 4

    def test_no_issues_in_healthy_page(self):
        issues = check_dom_state(HEALTHY)
        assert len(issues) == 0

    def test_all_issues_have_severity(self):
        issues = check_dom_state(BROKEN)
        for issue in issues:
            assert "severity" in issue
            assert issue["severity"] in ("HIGH", "MEDIUM", "LOW")

    def test_all_issues_have_description(self):
        issues = check_dom_state(BROKEN)
        for issue in issues:
            assert "description" in issue
            assert len(issue["description"]) > 10

    def test_returns_error_for_missing_file(self):
        issues = check_dom_state("/nonexistent/page.html")
        assert len(issues) == 1
        assert issues[0]["type"] == "FILE_NOT_FOUND"

    def test_detection_method_is_set(self):
        issues = check_dom_state(BROKEN)
        for issue in issues:
            assert issue.get("detection_method") == "DOM_ANALYSIS"


# ─── Pixel Diff Tests ─────────────────────────────────────────────────────

class TestPixelDiff:

    def _make_png(self, path: str, color: tuple, size: tuple = (100, 100)):
        """Create a simple solid-color PNG using raw bytes."""
        try:
            from PIL import Image
            img = Image.new("RGB", size, color)
            img.save(path)
            return True
        except ImportError:
            return False

    def test_identical_images_return_unchanged(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            b = os.path.join(tmpdir, "baseline.png")
            c = os.path.join(tmpdir, "current.png")
            d = os.path.join(tmpdir, "diff.png")
            if not self._make_png(b, (255, 255, 255)):
                pytest.skip("Pillow not installed")
            self._make_png(c, (255, 255, 255))
            result = pixel_diff(b, c, d)
            assert result["verdict"] == "UNCHANGED"
            assert result["change_pct"] == 0.0

    def test_different_images_return_changed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            b = os.path.join(tmpdir, "baseline.png")
            c = os.path.join(tmpdir, "current.png")
            d = os.path.join(tmpdir, "diff.png")
            if not self._make_png(b, (255, 255, 255)):
                pytest.skip("Pillow not installed")
            self._make_png(c, (0, 0, 0))
            result = pixel_diff(b, c, d)
            assert result["verdict"] == "CHANGED"
            assert result["change_pct"] > 90

    def test_missing_baseline_returns_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            c = os.path.join(tmpdir, "current.png")
            d = os.path.join(tmpdir, "diff.png")
            result = pixel_diff("/nonexistent/baseline.png", c, d)
            assert "error" in result
            assert result["verdict"] == "NO_BASELINE"

    def test_diff_image_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            b = os.path.join(tmpdir, "baseline.png")
            c = os.path.join(tmpdir, "current.png")
            d = os.path.join(tmpdir, "diff.png")
            if not self._make_png(b, (200, 200, 200)):
                pytest.skip("Pillow not installed")
            self._make_png(c, (100, 100, 100))
            pixel_diff(b, c, d)
            assert os.path.exists(d)

    def test_change_pct_is_numeric(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            b = os.path.join(tmpdir, "baseline.png")
            c = os.path.join(tmpdir, "current.png")
            d = os.path.join(tmpdir, "diff.png")
            if not self._make_png(b, (255, 0, 0)):
                pytest.skip("Pillow not installed")
            self._make_png(c, (0, 0, 255))
            result = pixel_diff(b, c, d)
            assert isinstance(result["change_pct"], float)


# ─── Vision Analysis Tests ────────────────────────────────────────────────

class TestVisionAnalysis:

    def test_skips_gracefully_without_api_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal PNG
            png_path = os.path.join(tmpdir, "screenshot.png")
            try:
                from PIL import Image
                Image.new("RGB", (100, 100), (255, 255, 255)).save(png_path)
            except ImportError:
                with open(png_path, "wb") as f:
                    f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
            result = vision_analyse(png_path, "test_checkpoint", api_key=None)
            assert result["method"] == "vision_skipped"
            assert "findings" in result

    def test_skips_with_placeholder_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            png_path = os.path.join(tmpdir, "screenshot.png")
            try:
                from PIL import Image
                Image.new("RGB", (100, 100), (255,255,255)).save(png_path)
            except ImportError:
                with open(png_path, "wb") as f:
                    f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
            result = vision_analyse(png_path, "test", api_key="sk-your-key-here")
            assert result["method"] == "vision_skipped"


# ─── RAG Tests ────────────────────────────────────────────────────────────

class TestVisualRAG:

    def test_loads_4_visual_incidents(self):
        from rag.rag_context import _load_incidents
        incidents = _load_incidents(KB_PATH)
        assert len(incidents) == 4

    def test_all_incidents_have_visual_tags(self):
        from rag.rag_context import _load_incidents
        incidents = _load_incidents(KB_PATH)
        for inc in incidents:
            assert "visual" in inc.get("tags", [])

    def test_incident_ids_are_inc_011_to_014(self):
        from rag.rag_context import _load_incidents
        incidents = _load_incidents(KB_PATH)
        ids = [i["id"] for i in incidents]
        assert "INC-011" in ids
        assert "INC-014" in ids

    def test_retrieves_invisible_button_for_checkout_query(self):
        result = json.loads(retrieve(
            "INVISIBLE_ELEMENT pay button white on white checkout",
            kb_path=KB_PATH
        ))
        assert result["retrieved_count"] > 0
        types = [c["type"] for c in result["context"]]
        assert "INVISIBLE_ELEMENT" in types

    def test_retrieves_spinner_for_loading_query(self):
        result = json.loads(retrieve(
            "STUCK_SPINNER loading pricing fetch timeout",
            kb_path=KB_PATH
        ))
        assert result["retrieved_count"] > 0
        types = [c["type"] for c in result["context"]]
        assert "STUCK_SPINNER" in types

    def test_retrieves_modal_for_confirmation_query(self):
        result = json.loads(retrieve(
            "MISSING_CONFIRMATION modal off-screen order placed",
            kb_path=KB_PATH
        ))
        assert result["retrieved_count"] > 0
        types = [c["type"] for c in result["context"]]
        assert "MISSING_CONFIRMATION" in types

    def test_all_context_items_have_runbook(self):
        result = json.loads(retrieve(
            "visual failure checkout button empty",
            kb_path=KB_PATH
        ))
        for ctx in result["context"]:
            assert "runbook" in ctx
            assert len(ctx["runbook"]) > 10

    def test_all_context_items_have_business_impact(self):
        result = json.loads(retrieve(
            "visual failure spinner modal",
            kb_path=KB_PATH
        ))
        for ctx in result["context"]:
            assert "business_impact" in ctx


# ─── Integration Tests ────────────────────────────────────────────────────

class TestIntegration:

    def test_full_pipeline_on_broken_page(self):
        """End-to-end: broken page → DOM analysis → RAG → report"""
        from main import run_visual_detection
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            result = run_visual_detection(
                page_path=BROKEN,
                kb_path=KB_PATH,
                output_path=out,
            )
            assert result["status"] == "complete"
            assert result["total_findings"] >= 4
            assert os.path.exists(out)

    def test_full_pipeline_on_healthy_page(self):
        """Healthy page should have no DOM issues"""
        from main import run_visual_detection
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            result = run_visual_detection(
                page_path=HEALTHY,
                kb_path=KB_PATH,
                output_path=out,
            )
            assert result["status"] == "complete"
            # DOM analysis should find zero issues on the healthy page
            dom_findings = [f for f in result["findings"] if f.get("source") == "DOM_ANALYSIS"]
            assert len(dom_findings) == 0

    def test_report_contains_comparison_table(self):
        """Report should include Part 1 vs 2 vs 3 comparison"""
        from main import run_visual_detection
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            run_visual_detection(
                page_path=BROKEN,
                kb_path=KB_PATH,
                output_path=out,
            )
            content = open(out, encoding="utf-8").read()
            assert "Part 1" in content
            assert "Part 3" in content

    def test_report_contains_rag_runbooks(self):
        """Enriched report should include runbook steps from RAG"""
        from main import run_visual_detection
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            run_visual_detection(
                page_path=BROKEN,
                kb_path=KB_PATH,
                output_path=out,
            )
            content = open(out, encoding="utf-8").read()
            assert "Runbook" in content

    def test_summary_mentions_findings(self):
        from main import run_visual_detection
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "report.md")
            result = run_visual_detection(
                page_path=BROKEN,
                kb_path=KB_PATH,
                output_path=out,
            )
            assert "visual silent failure" in result["summary"].lower()
