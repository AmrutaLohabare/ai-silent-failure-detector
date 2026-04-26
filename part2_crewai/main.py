"""
AI Silent Failure Detector — Part 2: CrewAI
============================================
3-Agent Collaborative Debate Edition

Usage:
    python main.py
    python main.py --log logs/sample_prod.log
    python main.py --log logs/your_prod.log --window 180
"""

import argparse
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()


def parse_args():
    parser = argparse.ArgumentParser(
        description="AI Silent Failure Detector — Part 2: CrewAI"
    )
    parser.add_argument("--log", default="logs/sample_prod.log")
    parser.add_argument("--window", type=int, default=60)
    parser.add_argument("--output", default="reports/silent_failure_report.md")
    parser.add_argument("--kb", default="knowledge_base/incidents.json")
    return parser.parse_args()


def main():
    args = parse_args()

    if not os.path.exists(args.log):
        print(f"\n❌  Log file not found: {args.log}\n")
        sys.exit(1)

    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)

    from crew.silent_failure_crew import SilentFailureCrew

    crew = SilentFailureCrew(
        kb_path=args.kb,
        output_path=args.output,
    )

    start = time.time()
    result = crew.run(log_source=args.log, window_minutes=args.window)
    elapsed = round(time.time() - start, 1)

    print(f"\n✅  Done in {elapsed}s")
    print(f"📄  Report: {args.output}")
    print(f"\n🔍  Summary:\n{result.get('summary', '')}")


if __name__ == "__main__":
    main()
