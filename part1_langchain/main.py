"""
AI Silent Failure Detector — Main Entry Point
=============================================
Part 1 of the LinkedIn series: LangChain + RAG

Usage:
    # Basic run on sample log
    python main.py

    # Run on your own log file
    python main.py --log logs/your_prod.log

    # Change the time window
    python main.py --log logs/your_prod.log --window 180

    # Change the output report path
    python main.py --log logs/your_prod.log --output reports/my_report.md

Prerequisites:
    1. pip install -r requirements.txt
    2. Copy .env.example to .env and add your OpenAI API key
"""

import argparse
import os
import sys
import time

from dotenv import load_dotenv

# Load .env file before importing anything that needs the API key
load_dotenv()


def validate_env():
    """Check required environment variables are set before running."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "sk-your-key-here":
        print("\n❌  OPENAI_API_KEY not set.")
        print("    1. Open the .env file in the project root")
        print("    2. Replace 'sk-your-key-here' with your real key")
        print("    3. Get a key at: https://platform.openai.com/api-keys\n")
        sys.exit(1)
    return api_key


def validate_log_file(path: str):
    """Check the log file exists and is readable."""
    if not os.path.exists(path):
        print(f"\n❌  Log file not found: {path}")
        print("    Make sure the path is correct and the file exists.\n")
        sys.exit(1)
    if os.path.getsize(path) == 0:
        print(f"\n⚠️   Log file is empty: {path}")
        print("    Nothing to analyse.\n")
        sys.exit(1)


def parse_args():
    parser = argparse.ArgumentParser(
        description="AI Silent Failure Detector — LangChain + RAG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py
  python main.py --log logs/sample_prod.log
  python main.py --log logs/prod.log --window 180 --output reports/prod_report.md
        """
    )
    parser.add_argument(
        "--log",
        default="logs/sample_prod.log",
        help="Path to the log file to analyse (default: logs/sample_prod.log)"
    )
    parser.add_argument(
        "--window",
        type=int,
        default=int(os.getenv("DETECTION_WINDOW_MINUTES", 60)),
        help="Time window in minutes to scan (default: 60)"
    )
    parser.add_argument(
        "--output",
        default="reports/silent_failure_report.md",
        help="Path to write the report (default: reports/silent_failure_report.md)"
    )
    parser.add_argument(
        "--kb",
        default="knowledge_base/incidents.json",
        help="Path to the knowledge base JSON file (default: knowledge_base/incidents.json)"
    )
    return parser.parse_args()


def main():
    print("\n🔇  AI Silent Failure Detector")
    print("    LangChain + RAG Edition — Part 1 of 7")
    print("─" * 48)

    # Validate environment and inputs
    validate_env()
    args = parse_args()
    validate_log_file(args.log)

    print(f"\n📂  Log file   : {args.log}")
    print(f"⏱️   Time window : {args.window} minutes")
    print(f"📊  Report     : {args.output}")
    print(f"🧠  Knowledge  : {args.kb}")
    print("\n🚀  Starting detection agent...\n")

    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else ".", exist_ok=True)

    # Import here (after load_dotenv) so API key is available
    from agent.silent_failure_detector import run_detection

    start = time.time()
    try:
        result = run_detection(
            log_source=args.log,
            window_minutes=args.window,
            kb_path=args.kb,
        )
        elapsed = round(time.time() - start, 1)

        print("\n" + "─" * 48)
        print(f"✅  Detection complete in {elapsed}s")
        print(f"📄  Report saved to: {args.output}")
        print("\n🔍  Agent summary:")
        print(result)
        print("─" * 48 + "\n")

    except KeyboardInterrupt:
        print("\n\n⚠️   Interrupted by user.\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌  Agent failed: {e}")
        print("    Check your OPENAI_API_KEY and try again.\n")
        raise


if __name__ == "__main__":
    main()
