"""
AI Silent Failure Detector - Part 3: Playwright + AI Vision
============================================================
Detects silent visual failures that logs never catch.

Usage (Windows Command Prompt):
    python main.py
    python main.py --page pages\checkout_broken.html
    python main.py --page pages\checkout_broken.html --baseline pages\checkout_healthy.html
    python main.py --page pages\checkout_broken.html --output reports\my_report.md
"""

import argparse
import os
import sys
import time

from dotenv import load_dotenv
load_dotenv()


def parse_args():
    parser = argparse.ArgumentParser(
        description="AI Silent Failure Detector - Part 3: Playwright + AI Vision"
    )
    parser.add_argument(
        "--page",
        default=os.path.join("pages", "checkout_broken.html"),
        help="Path to the HTML page to test"
    )
    parser.add_argument(
        "--baseline",
        default=os.path.join("pages", "checkout_healthy.html"),
        help="Path to the known-good baseline page"
    )
    parser.add_argument(
        "--output",
        default=os.path.join("reports", "visual_failure_report.md"),
        help="Path to write the report"
    )
    parser.add_argument(
        "--kb",
        default=os.path.join("knowledge_base", "incidents.json"),
        help="Path to knowledge base JSON"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("")
    print("  AI Silent Failure Detector")
    print("  Part 3: Playwright + AI Vision")
    print("  " + "-" * 44)
    print("")
    print("  Page     : " + args.page)
    print("  Baseline : " + args.baseline)
    print("  Report   : " + args.output)
    print("  KB       : " + args.kb)
    print("")

    if not os.path.exists(args.page):
        print("ERROR: Page file not found: " + args.page)
        sys.exit(1)

    os.makedirs(
        os.path.dirname(args.output) if os.path.dirname(args.output) else ".",
        exist_ok=True
    )

    from detector.visual_detector import (
        capture_screenshots,
        check_dom_state,
        pixel_diff,
        vision_analyse,
        BASELINE_DIR,
        CURRENT_DIR,
        DIFF_DIR,
    )
    from rag.rag_context import retrieve
    import json
    from datetime import datetime

    all_findings = []
    methods_used = []

    print("[Step 1/4] DOM analysis...")
    dom_issues = check_dom_state(args.page)
    for issue in dom_issues:
        issue["source"] = "DOM_ANALYSIS"
        all_findings.append(issue)
    print("           " + str(len(dom_issues)) + " DOM issue(s) found")
    if dom_issues:
        methods_used.append("DOM analysis")

    print("[Step 2/4] Capturing screenshots...")
    current_shots = capture_screenshots(args.page, CURRENT_DIR)
    print("           " + str(len(current_shots)) + " screenshot(s) captured")

    if os.path.exists(args.baseline):
        baseline_shots = capture_screenshots(args.baseline, BASELINE_DIR)
        print("           " + str(len(baseline_shots)) + " baseline screenshot(s) captured")
    else:
        baseline_shots = []
        print("           No baseline page found - skipping baseline capture")

    print("[Step 3/4] Pixel diff...")
    diff_count = 0
    for shot in current_shots:
        name = shot["name"]
        b_path = os.path.join(BASELINE_DIR, name.replace("_current", "") + "_baseline.png")
        c_path = shot["path"]
        d_path = os.path.join(DIFF_DIR, name.replace("_current", "") + "_diff.png")

        if not os.path.exists(b_path):
            continue

        result = pixel_diff(b_path, c_path, d_path)
        change = result.get("change_pct", 0)
        verdict = result.get("verdict", "UNKNOWN")
        print("           " + name + ": " + str(change) + "% changed -> " + verdict)

        if verdict == "CHANGED":
            all_findings.append({
                "type": "VISUAL_REGRESSION",
                "severity": "MEDIUM",
                "element": name,
                "description": (
                    "Screenshot '" + name + "' differs from baseline by "
                    + str(change) + "% (" + str(result.get("changed_pixels", 0)) + " pixels)"
                ),
                "diff_path": d_path,
                "change_pct": change,
                "source": "PIXEL_DIFF",
            })
            diff_count += 1
    if diff_count > 0:
        methods_used.append("pixel diff")
    print("           " + str(diff_count) + " visual regression(s) detected")

    print("[Step 4/4] Vision analysis...")
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key and api_key != "sk-your-key-here":
        print("           GPT-4o Vision: enabled")
        vision_count = 0
        for shot in current_shots:
            result = vision_analyse(shot["path"], shot["name"], api_key)
            if result.get("method") == "gpt4o_vision":
                for f in result.get("findings", []):
                    f["source"] = "GPT4O_VISION"
                    f["checkpoint"] = shot["name"]
                    all_findings.append(f)
                    vision_count += 1
        methods_used.append("GPT-4o Vision")
        print("           " + str(vision_count) + " vision finding(s)")
    else:
        print("           GPT-4o Vision: skipped (no API key)")

    print("")
    print("[RAG] Enriching " + str(len(all_findings)) + " finding(s)...")
    enriched = []
    for finding in all_findings:
        query = (
            finding.get("type", "") + " "
            + finding.get("element", "") + " "
            + finding.get("description", "")
            + " visual checkout button spinner modal"
        )
        rag_result = json.loads(retrieve(query, kb_path=args.kb))
        finding["rag_context"] = rag_result.get("context", [])
        enriched.append(finding)

    print("[Report] Writing report...")
    severity_icon = {"HIGH": "[HIGH]", "MEDIUM": "[MED]", "LOW": "[LOW]"}

    lines = [
        "# AI Silent Failure Detector - Part 3: Visual Report",
        "",
        "**Generated:** " + datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "**Page tested:** " + os.path.basename(args.page),
        "**Detection methods:** " + (", ".join(set(methods_used)) if methods_used else "DOM analysis"),
        "**Visual failures detected:** " + str(len(enriched)),
        "",
        "> These failures all return HTTP 200.",
        "> Logs show nothing wrong. Only visual inspection catches them.",
        "",
        "---",
        "",
    ]

    if not enriched:
        lines.append("No visual silent failures detected.")
    else:
        for i, f in enumerate(enriched, 1):
            sev = f.get("severity", "MEDIUM")
            icon = severity_icon.get(sev, "[?]")
            lines.append("## " + icon + " Finding " + str(i) + ": " + f["type"].replace("_", " ").title())
            lines.append("")
            lines.append("**Severity:** " + sev)
            lines.append("**Element:** " + f.get("element", "Unknown"))
            lines.append("**Detection method:** " + f.get("source", "Unknown"))
            lines.append("")
            lines.append("**Description:** " + f.get("description", ""))
            lines.append("")

            rag = f.get("rag_context", [])
            if rag:
                lines.append("### Similar past incidents")
                lines.append("")
                for ctx in rag[:2]:
                    lines.append("**" + ctx["incident_id"] + " - " + ctx["title"] + "**")
                    lines.append("")
                    lines.append("**Root cause:** " + ctx["root_cause"])
                    lines.append("")
                    lines.append("**Business impact:** " + ctx["business_impact"])
                    lines.append("")
                    lines.append("**Detection lag:** " + str(ctx["detection_lag_hours"]) + " hours")
                    lines.append("")
                    lines.append("**Runbook:**")
                    for step in ctx.get("runbook", "").split(". "):
                        if step.strip():
                            lines.append("  - " + step.strip())
                    lines.append("")

            lines.append("---")
            lines.append("")

    lines.append("## Series Comparison")
    lines.append("")
    lines.append("| Metric | Part 1 | Part 2 | Part 3 |")
    lines.append("|---|---|---|---|")
    lines.append("| Input | Log files | Log files | Screenshots |")
    lines.append("| Catches log-invisible failures | No | No | Yes |")
    lines.append("| API key required | Yes | No | Optional |")
    lines.append("| Findings this run | - | - | " + str(len(enriched)) + " |")

    report_text = "\n".join(lines)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report_text)

    print("")
    print("  Done")
    print("  Report  : " + args.output)
    print("  Findings: " + str(len(enriched)) + " visual silent failure(s)")
    print("")



def run_visual_detection(
    page_path,
    baseline_page_path=None,
    kb_path=None,
    output_path="reports/visual_failure_report.md",
    api_key=None,
):
    """Importable wrapper for integration tests."""
    import sys as _sys
    _orig = _sys.argv[:]
    args = ["main.py", "--page", page_path]
    if kb_path:
        args += ["--kb", kb_path]
    if output_path:
        args += ["--output", output_path]
    _sys.argv = args

    from detector.visual_detector import (
        capture_screenshots, check_dom_state, pixel_diff, vision_analyse,
        BASELINE_DIR, CURRENT_DIR, DIFF_DIR,
    )
    from rag.rag_context import retrieve
    import json
    from datetime import datetime

    all_findings = []
    methods_used = []

    dom_issues = check_dom_state(page_path)
    for issue in dom_issues:
        issue["source"] = "DOM_ANALYSIS"
        all_findings.append(issue)
    if dom_issues:
        methods_used.append("DOM analysis")

    current_shots = capture_screenshots(page_path, CURRENT_DIR)
    if baseline_page_path and os.path.exists(baseline_page_path):
        capture_screenshots(baseline_page_path, BASELINE_DIR)

    for shot in current_shots:
        name = shot["name"]
        b_path = os.path.join(BASELINE_DIR, name.replace("_current", "") + "_baseline.png")
        c_path = shot["path"]
        d_path = os.path.join(DIFF_DIR, name.replace("_current", "") + "_diff.png")
        if not os.path.exists(b_path):
            continue
        result = pixel_diff(b_path, c_path, d_path)
        if result.get("verdict") == "CHANGED":
            all_findings.append({
                "type": "VISUAL_REGRESSION",
                "severity": "MEDIUM",
                "element": name,
                "description": "Screenshot changed by " + str(result.get("change_pct", 0)) + "%",
                "source": "PIXEL_DIFF",
            })
            methods_used.append("pixel diff")

    enriched = []
    for finding in all_findings:
        query = finding.get("type", "") + " " + finding.get("description", "")
        rag_result = json.loads(retrieve(query, kb_path=kb_path))
        finding["rag_context"] = rag_result.get("context", [])
        enriched.append(finding)

    lines = [
        "# AI Silent Failure Detector - Part 3: Visual Report",
        "",
        "**Generated:** " + datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "**Page tested:** " + os.path.basename(page_path),
        "**Visual failures detected:** " + str(len(enriched)),
        "",
        "---",
        "",
    ]

    for i, f in enumerate(enriched, 1):
        lines.append("## Finding " + str(i) + ": " + f["type"])
        lines.append("")
        lines.append("**Description:** " + f.get("description", ""))
        lines.append("")
        rag = f.get("rag_context", [])
        if rag:
            lines.append("### Runbook")
            for ctx in rag[:1]:
                for step in ctx.get("runbook", "").split(". "):
                    if step.strip():
                        lines.append("  - " + step.strip())
        lines.append("")

    lines.append("## Part 1 vs Part 2 vs Part 3")
    lines.append("")
    lines.append("| Metric | Part 1 | Part 2 | Part 3 |")
    lines.append("|---|---|---|---|")
    lines.append("| Input | Logs | Logs | Screenshots |")
    lines.append("| Visual failures | No | No | Yes |")

    report_text = "\n".join(lines)
    os.makedirs(
        os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
        exist_ok=True
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    _sys.argv = _orig

    summary = (
        "Tested " + os.path.basename(page_path) + " using " +
        (", ".join(set(methods_used)) if methods_used else "DOM analysis") +
        ". Found " + str(len(enriched)) + " visual silent failure(s) that logs would never catch."
    )

    return {
        "status": "complete",
        "total_findings": len(enriched),
        "findings": enriched,
        "methods_used": methods_used,
        "report_path": output_path,
        "summary": summary,
    }


if __name__ == "__main__":
    start = time.time()
    main()
    print("  Completed in " + str(round(time.time() - start, 1)) + "s")
