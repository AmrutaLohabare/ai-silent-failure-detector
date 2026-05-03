"""
Visual Failure Detector — Part 3: Playwright + AI Vision
==========================================================
Captures screenshots of UI checkpoints using Playwright,
then detects silent visual failures using:
  Primary   : GPT-4o Vision (if OPENAI_API_KEY set)
  Fallback  : Pixel diffing with Pillow (fully offline)

Silent visual failures caught that logs never see:
  - Invisible buttons (white text on white background)
  - Empty content sections (API 200 but no content rendered)
  - Stuck loading spinners (fetch started, never resolved)
  - Confirmation modals off-screen (positioned outside viewport)
"""

import base64
import json
import os
import sys
from pathlib import Path
from typing import Optional

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "..", "screenshots")
BASELINE_DIR    = os.path.join(SCREENSHOTS_DIR, "baseline")
CURRENT_DIR     = os.path.join(SCREENSHOTS_DIR, "current")
DIFF_DIR        = os.path.join(SCREENSHOTS_DIR, "diff")


# ─── Playwright Screenshot Capture ────────────────────────────────────────

def capture_screenshots(page_path: str, output_dir: str) -> list[dict]:
    """
    Use Playwright to open a page and capture screenshots
    at key UI checkpoints.
    Returns list of {name, path, width, height} dicts.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[Visual] Playwright not installed — using pre-captured screenshots.")
        return _list_existing_screenshots(output_dir)

    os.makedirs(output_dir, exist_ok=True)
    screenshots = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # Build file:// URL for local HTML
        abs_path = os.path.abspath(page_path)
        url = f"file:///{abs_path}".replace("\\", "/")

        print(f"  [Playwright] Opening: {url}")
        page.goto(url, wait_until="networkidle")

        checkpoints = [
            ("full_page",    None,                    None),
            ("pay_button",   "#pay-btn",              20),
            ("order_summary",".card:last-child",      10),
            ("recommendations", ".recommendations",   10),
        ]

        folder_name = os.path.basename(output_dir)
        for name, selector, padding in checkpoints:
            path = os.path.join(output_dir, f"{name}_{folder_name}.png")
            if selector:
                try:
                    el = page.locator(selector).first
                    el.screenshot(path=path)
                    print(f"  [Playwright] ✓ {name} ({selector})")
                except Exception as e:
                    print(f"  [Playwright] ✗ {name}: {e}")
                    page.screenshot(path=path, full_page=False)
            else:
                page.screenshot(path=path, full_page=True)
                print(f"  [Playwright] ✓ {name} (full page)")

            screenshots.append({"name": name, "path": path})

        browser.close()

    return screenshots


def _list_existing_screenshots(directory: str) -> list[dict]:
    """Return list of existing screenshots in a directory."""
    result = []
    if os.path.exists(directory):
        for f in sorted(os.listdir(directory)):
            if f.endswith(".png"):
                result.append({
                    "name": f.replace(".png", ""),
                    "path": os.path.join(directory, f),
                })
    return result


# ─── Pixel Diff Engine (offline fallback) ─────────────────────────────────

def pixel_diff(
    baseline_path: str,
    current_path: str,
    diff_path: str,
    threshold: float = 0.02,
) -> dict:
    """
    Compare two screenshots pixel-by-pixel using Pillow.
    Returns a diff result dict with change_pct and verdict.
    threshold: fraction of pixels that can change before flagging (default 2%)
    """
    try:
        from PIL import Image, ImageChops, ImageEnhance
        import struct
    except ImportError:
        return {
            "error": "Pillow not installed. Run: pip install Pillow",
            "change_pct": 0,
            "verdict": "UNKNOWN",
        }

    if not os.path.exists(baseline_path):
        return {
            "error": f"Baseline screenshot not found: {baseline_path}",
            "change_pct": 0,
            "verdict": "NO_BASELINE",
        }
    if not os.path.exists(current_path):
        return {
            "error": f"Current screenshot not found: {current_path}",
            "change_pct": 0,
            "verdict": "NO_CURRENT",
        }

    baseline = Image.open(baseline_path).convert("RGB")
    current  = Image.open(current_path).convert("RGB")

    # Resize current to match baseline if dimensions differ
    if baseline.size != current.size:
        current = current.resize(baseline.size, Image.LANCZOS)

    diff = ImageChops.difference(baseline, current)

    # Count significantly different pixels (channel delta > 30)
    pixels = list(diff.getdata())
    total = len(pixels)
    changed = sum(
        1 for r, g, b in pixels
        if max(r, g, b) > 30
    )
    change_pct = changed / total if total > 0 else 0

    # Save amplified diff image
    os.makedirs(os.path.dirname(diff_path), exist_ok=True)
    enhanced = ImageEnhance.Brightness(diff).enhance(5.0)
    enhanced.save(diff_path)

    verdict = "CHANGED" if change_pct > threshold else "UNCHANGED"

    return {
        "baseline": baseline_path,
        "current": current_path,
        "diff": diff_path,
        "total_pixels": total,
        "changed_pixels": changed,
        "change_pct": round(change_pct * 100, 2),
        "threshold_pct": round(threshold * 100, 2),
        "verdict": verdict,
    }


# ─── GPT-4o Vision Analysis (primary when API key available) ──────────────

def vision_analyse(
    screenshot_path: str,
    checkpoint_name: str,
    api_key: Optional[str] = None,
) -> dict:
    """
    Send a screenshot to GPT-4o Vision for silent failure analysis.
    Returns structured findings dict.
    Falls back gracefully if no API key.
    """
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key or key == "sk-your-key-here":
        return {
            "method": "vision_skipped",
            "reason": "No OPENAI_API_KEY set — using pixel diff only",
            "findings": [],
        }

    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)

        with open(screenshot_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        prompt = f"""You are a QA engineer specialised in detecting silent UI failures.
Analyse this screenshot of the '{checkpoint_name}' UI checkpoint.

Look specifically for these silent failure patterns:
1. INVISIBLE_ELEMENT — buttons, text, or content that exists in DOM but is not visible
   (white text on white background, zero opacity, off-screen positioning)
2. EMPTY_CONTENT_SECTION — a section that should show content but is blank or loading
   (empty recommendations, empty cart, blank dashboard widgets)
3. STUCK_SPINNER — a loading spinner that has been spinning too long
   (payment processing, data loading that never completes)
4. MISSING_CONFIRMATION — an action was performed but no success/confirmation is shown
   (form submitted, no thank you message; payment processed, no receipt)
5. BROKEN_LAYOUT — content rendered outside its container or overlapping incorrectly

For each finding, respond ONLY with valid JSON in this exact format:
{{
  "findings": [
    {{
      "type": "INVISIBLE_ELEMENT",
      "severity": "HIGH",
      "element": "Pay button",
      "description": "Button exists in DOM but text is white on white background — invisible to user",
      "evidence": "Button visible in screenshot at bottom of payment form but text not readable"
    }}
  ],
  "overall_verdict": "SILENT_FAILURES_DETECTED",
  "confidence": "HIGH"
}}

If no silent failures found, return:
{{"findings": [], "overall_verdict": "HEALTHY", "confidence": "HIGH"}}

Respond ONLY with the JSON object. No other text."""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/png;base64,{image_data}",
                        "detail": "high",
                    }},
                ],
            }],
            max_tokens=800,
            temperature=0,
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        result["method"] = "gpt4o_vision"
        result["checkpoint"] = checkpoint_name
        return result

    except json.JSONDecodeError as e:
        return {
            "method": "vision_parse_error",
            "error": str(e),
            "raw_response": raw if "raw" in locals() else "",
            "findings": [],
        }
    except Exception as e:
        return {
            "method": "vision_error",
            "error": str(e),
            "findings": [],
        }


# ─── DOM State Checks (rule-based, no vision needed) ──────────────────────

def check_dom_state(page_path: str) -> list[dict]:
    """
    Parse the HTML file for known silent failure DOM patterns.
    Works without Playwright or vision — pure text analysis.
    """
    issues = []
    try:
        with open(page_path, "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        return [{"type": "FILE_NOT_FOUND", "severity": "HIGH",
                 "description": f"Page file not found: {page_path}"}]

    # Check 1: Invisible button patterns
    if "color: #ffffff" in html and "background: #ffffff" in html:
        issues.append({
            "type": "INVISIBLE_ELEMENT",
            "severity": "HIGH",
            "element": "Button",
            "description": "White text on white background detected — button invisible to user",
            "detection_method": "DOM_ANALYSIS",
        })

    # Check 2: Stuck spinner
    if "spinner" in html and ("loading live" in html.lower() or "calculating" in html.lower()):
        issues.append({
            "type": "STUCK_SPINNER",
            "severity": "MEDIUM",
            "element": "Order summary pricing",
            "description": "Loading spinners detected in pricing section — may never resolve",
            "detection_method": "DOM_ANALYSIS",
        })

    # Check 3: Off-screen modal
    if "top: -9999px" in html or "top:-9999px" in html:
        issues.append({
            "type": "MISSING_CONFIRMATION",
            "severity": "HIGH",
            "element": "Order confirmation modal",
            "description": "Confirmation modal positioned at top:-9999px — off-screen, never visible to user",
            "detection_method": "DOM_ANALYSIS",
        })

    # Check 4: Empty content sections
    if "display: none" in html and "rec-item" in html:
        issues.append({
            "type": "EMPTY_CONTENT_SECTION",
            "severity": "MEDIUM",
            "element": "Recommendations section",
            "description": "Recommendation items hidden via CSS — section shows heading only",
            "detection_method": "DOM_ANALYSIS",
        })

    return issues
