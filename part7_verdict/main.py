"""
AI Silent Failure Detector - Part 7: The Honest Verdict
========================================================
Runs all 6 detectors on the same input and produces
a side-by-side comparison and honest verdict.

Usage (Windows Command Prompt):
    python main.py
    python main.py --log ..\part1_langchain\logs\sample_prod.log
    python main.py --output reports\my_verdict.md
"""

import argparse
import os
import sys
import time

from dotenv import load_dotenv
load_dotenv()


def parse_args():
    parser = argparse.ArgumentParser(
        description="AI Silent Failure Detector - Part 7: The Verdict"
    )
    parser.add_argument(
        "--log",
        default=os.path.join("..", "part1_langchain", "logs", "sample_prod.log"),
        help="Path to log file (used by Parts 1,2,4,5)"
    )
    parser.add_argument(
        "--output",
        default=os.path.join("reports", "verdict_report.md"),
        help="Path to write the verdict report"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("")
    print("  AI Silent Failure Detector")
    print("  Part 7: The Honest Verdict")
    print("  " + "-" * 44)
    print("")
    print("  Log    : " + args.log)
    print("  Output : " + args.output)
    print("")

    from comparison.comparison_engine import ComparisonEngine

    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    engine = ComparisonEngine(base_dir=base_dir)

    result = engine.run_comparison(
        log_source=args.log,
        output_path=args.output,
    )

    print("")
    print("  " + result["verdict"])
    print("")
    print("  All 6 parts compared.")
    print("  Report : " + args.output)
    print("")


def run_comparison(
    log_source=None,
    output_path="reports/verdict_report.md",
    base_dir=None,
):
    """Importable wrapper for tests."""
    from comparison.comparison_engine import ComparisonEngine
    if base_dir is None:
        base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    if log_source is None:
        log_source = os.path.join(base_dir, "part1_langchain", "logs", "sample_prod.log")
    engine = ComparisonEngine(base_dir=base_dir)
    return engine.run_comparison(log_source=log_source, output_path=output_path)


if __name__ == "__main__":
    start = time.time()
    main()
    print("  Completed in " + str(round(time.time() - start, 1)) + "s")
