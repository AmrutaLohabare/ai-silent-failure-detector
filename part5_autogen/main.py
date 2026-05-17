"""
AI Silent Failure Detector - Part 5: AutoGen Self-Healing
==========================================================
3-agent self-healing pipeline:

  DetectorAgent  - finds silent failures
  HealerAgent    - writes the fix
  VerifierAgent  - runs and validates the fix
                   loops back to Healer if fix fails (max 3 rounds)

Usage (Windows Command Prompt):
    python main.py
    python main.py --log logs\sample_prod.log
    python main.py --log logs\sample_prod.log --output reports\my_report.md
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()


def parse_args():
    parser = argparse.ArgumentParser(
        description="AI Silent Failure Detector - Part 5: AutoGen Self-Healing"
    )
    parser.add_argument(
        "--log",
        default=os.path.join("logs", "sample_prod.log"),
        help="Path to the log file to analyse"
    )
    parser.add_argument(
        "--output",
        default=os.path.join("reports", "self_healing_report.md"),
        help="Path to write the report"
    )
    parser.add_argument(
        "--kb",
        default=os.path.join("knowledge_base", "incidents.json"),
        help="Path to knowledge base JSON"
    )
    parser.add_argument(
        "--healed-dir",
        default="healed_tests",
        dest="healed_dir",
        help="Directory to save verified healed tests"
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=3,
        dest="max_rounds",
        help="Maximum heal-verify rounds per anomaly"
    )
    return parser.parse_args()


def run_self_healing(
    log_source,
    kb_path=None,
    output_path="reports/self_healing_report.md",
    healed_dir="healed_tests",
    max_rounds=3,
):
    """
    Main self-healing pipeline. Importable for tests.
    Returns result dict with all findings and healed tests.
    """
    from agents.autogen_agents import DetectorAgent, HealerAgent, VerifierAgent

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    os.makedirs(healed_dir, exist_ok=True)

    print("\n" + "=" * 54)
    print("  AI Silent Failure Detector - Part 5: AutoGen")
    print("  Self-Healing Test Generation")
    print("=" * 54 + "\n")

    # Instantiate agents
    detector = DetectorAgent()
    healer   = HealerAgent(kb_path=kb_path)
    verifier = VerifierAgent()

    # ─── Step 1: Detection ───────────────────────────────────────────
    print("[Crew] Step 1 - DetectorAgent scanning logs...")
    detection = detector.run(log_source)

    if "error" in detection:
        print("ERROR: " + detection["error"])
        return {"status": "error", "message": detection["error"]}

    anomalies = detection.get("anomalies", [])
    print("[Crew] " + str(len(anomalies)) + " anomaly(s) found\n")

    if not anomalies:
        return {
            "status": "clean",
            "anomalies": [],
            "healed_tests": [],
            "summary": "No anomalies detected. No healing needed.",
        }

    # ─── Step 2-3: Heal + Verify loop per anomaly ────────────────────
    healed_tests = []
    failed_heals = []

    for i, anomaly in enumerate(anomalies, 1):
        failure_type = anomaly.get("type", "UNKNOWN")
        print("[Crew] Processing anomaly " + str(i) + "/" + str(len(anomalies)) + ": " + failure_type)

        verified = False
        final_fix = None
        final_verification = None

        for round_num in range(1, max_rounds + 1):
            print("[Crew] Round " + str(round_num) + "/" + str(max_rounds))

            # HealerAgent writes the fix
            fix = healer.write_fix(anomaly, round_num=round_num)

            # VerifierAgent runs the fix
            verification = verifier.verify(fix, healed_dir)
            status = verification["status"]

            if status in ("CATCHES_FAILURE", "STRUCTURE_VALID"):
                # Fix is good - save it permanently
                saved_path = verifier.save_healed_test(fix, healed_dir)
                healed_tests.append({
                    "failure_type": failure_type,
                    "incident_id": fix["incident_id"],
                    "fix_title": fix["fix_title"],
                    "test_function": fix["test_function"],
                    "test_path": saved_path,
                    "rounds_needed": round_num,
                    "verification_status": status,
                })
                verified = True
                final_fix = fix
                final_verification = verification
                print("[Crew] Fix verified in " + str(round_num) + " round(s)")
                break
            else:
                print("[Crew] Round " + str(round_num) + " failed - retrying...")

        if not verified:
            print("[Crew] Could not heal " + failure_type + " after " + str(max_rounds) + " rounds")
            failed_heals.append({
                "failure_type": failure_type,
                "rounds_attempted": max_rounds,
                "reason": "Max rounds exceeded without valid fix",
            })

    # ─── Step 4: Generate report ─────────────────────────────────────
    report = _generate_report(
        detection, healed_tests, failed_heals, output_path
    )
    print("\n[Report] " + report)

    summary = (
        "Scanned " + str(detection["entries_analysed"]) + " log entries. "
        "Found " + str(len(anomalies)) + " anomaly(s). "
        "Healed " + str(len(healed_tests)) + " with auto-generated tests. "
        + (str(len(failed_heals)) + " could not be healed." if failed_heals else "")
    )

    print("\n" + "=" * 54)
    print("  Self-healing complete")
    print("  " + summary)
    print("=" * 54)

    return {
        "status": "complete",
        "anomalies": anomalies,
        "healed_tests": healed_tests,
        "failed_heals": failed_heals,
        "report_path": output_path,
        "summary": summary,
    }


def _generate_report(
    detection: dict,
    healed_tests: list,
    failed_heals: list,
    output_path: str,
) -> str:
    anomalies   = detection.get("anomalies", [])
    entries     = detection.get("entries_analysed", 0)

    lines = [
        "# AI Silent Failure Detector - Part 5: Self-Healing Report",
        "",
        "**Generated:** " + datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "**Entries analysed:** " + str(entries),
        "**Anomalies detected:** " + str(len(anomalies)),
        "**Tests auto-generated:** " + str(len(healed_tests)),
        "**Healing failures:** " + str(len(failed_heals)),
        "",
        "---",
        "",
    ]

    if healed_tests:
        lines.append("## Auto-Generated Healed Tests")
        lines.append("")
        for h in healed_tests:
            lines.append("### " + h["failure_type"].replace("_", " ").title())
            lines.append("")
            lines.append("**Fix pattern:** " + h["incident_id"] + " - " + h["fix_title"])
            lines.append("**Test function:** `" + h["test_function"] + "`")
            lines.append("**Saved to:** `" + h["test_path"] + "`")
            lines.append("**Rounds needed:** " + str(h["rounds_needed"]))
            lines.append("**Verification:** " + h["verification_status"])
            lines.append("")
            lines.append("---")
            lines.append("")

    if failed_heals:
        lines.append("## Unhealed Anomalies - Manual Review Required")
        lines.append("")
        for f in failed_heals:
            lines.append("- " + f["failure_type"] + ": " + f["reason"])
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## Series Comparison")
    lines.append("")
    lines.append("| Metric | Part 1 | Part 2 | Part 3 | Part 4 | Part 5 |")
    lines.append("|---|---|---|---|---|---|")
    lines.append("| Tool | LangChain | CrewAI | Playwright | Semantic Kernel | AutoGen |")
    lines.append("| Agent action | Detect | Detect + debate | Visual detect | Detect (SK) | Detect + fix + verify |")
    lines.append("| Output | Report | Report | Visual report | Report | Report + healed tests |")
    lines.append("| Human needed | Review | Review | Review | Review | Optional |")
    lines.append("| Tests | 31 | 26 | 30 | 29 | TBD |")

    report = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    return (
        "Report written to " + output_path + ". "
        + str(len(healed_tests)) + " test(s) auto-generated."
    )


def main():
    args = parse_args()

    print("")
    print("  AI Silent Failure Detector")
    print("  Part 5: AutoGen Self-Healing")
    print("  " + "-" * 44)
    print("")
    print("  Log        : " + args.log)
    print("  Report     : " + args.output)
    print("  KB         : " + args.kb)
    print("  Healed dir : " + args.healed_dir)
    print("  Max rounds : " + str(args.max_rounds))
    print("")

    if not os.path.exists(args.log):
        print("ERROR: Log file not found: " + args.log)
        sys.exit(1)

    result = run_self_healing(
        log_source=args.log,
        kb_path=args.kb,
        output_path=args.output,
        healed_dir=args.healed_dir,
        max_rounds=args.max_rounds,
    )

    return result


if __name__ == "__main__":
    start = time.time()
    main()
    print("\n  Completed in " + str(round(time.time() - start, 1)) + "s")
