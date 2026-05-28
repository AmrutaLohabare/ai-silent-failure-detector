"""
AI Silent Failure Detector - Part 6: Datadog + LLM Reasoning
=============================================================
Cross-signal observability analysis:
  MetricsCollector  - p99 latency, error rate, throughput
  TraceAnalyzer     - span bottleneck detection
  LogCorrelator     - silent 200s, retries, idempotency collisions
  CorrelationEngine - reasons across all 3 signals together
  RAG               - retrieves matching past incidents

Usage (Windows Command Prompt):
    python main.py
    python main.py --data data\observability_snapshot.json
    python main.py --output reports\my_report.md
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
        description="AI Silent Failure Detector - Part 6: Datadog + LLM"
    )
    parser.add_argument(
        "--data",
        default=os.path.join("data", "observability_snapshot.json"),
        help="Path to observability snapshot JSON"
    )
    parser.add_argument(
        "--output",
        default=os.path.join("reports", "observability_report.md"),
        help="Path to write the report"
    )
    parser.add_argument(
        "--kb",
        default=os.path.join("knowledge_base", "incidents.json"),
        help="Path to knowledge base JSON"
    )
    return parser.parse_args()


def run_detection(
    data_path=None,
    kb_path=None,
    output_path="reports/observability_report.md",
    api_key=None,
):
    """Main detection pipeline. Importable for tests."""
    from collectors.observability_collectors import (
        LogCorrelator, MetricsCollector, TraceAnalyzer,
    )
    from analyzer.correlation_engine import CorrelationEngine
    from rag.rag_context import retrieve, reset
    reset()

    if data_path is None:
        data_path = os.path.join("data", "observability_snapshot.json")
    if kb_path is None:
        kb_path = os.path.join("knowledge_base", "incidents.json")

    os.makedirs(
        os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
        exist_ok=True
    )

    print("\n[Step 1/4] MetricsCollector...")
    metrics = MetricsCollector(data_path).analyse()
    print("  " + str(metrics["findings_count"]) + " metric finding(s)")

    print("[Step 2/4] TraceAnalyzer...")
    traces = TraceAnalyzer(data_path).analyse()
    print("  " + str(traces["findings_count"]) + " trace finding(s)")

    print("[Step 3/4] LogCorrelator...")
    logs = LogCorrelator(data_path).analyse()
    print("  " + str(logs["findings_count"]) + " log finding(s)")

    print("[Step 4/4] CorrelationEngine...")
    key = api_key or os.getenv("OPENAI_API_KEY", "")
    engine = CorrelationEngine(api_key=key)
    correlation = engine.correlate(metrics, traces, logs)
    signals = correlation.get("signals_firing", [])
    print("  Signals firing: " + str(signals))
    print("  Correlated patterns: " + str(len(correlation.get("correlated_anomalies", []))))

    print("[RAG] Enriching findings...")
    query = " ".join([
        f.get("type", "") + " " + f.get("description", "")
        for f in correlation.get("all_findings", [])
    ])
    rag_data = json.loads(retrieve(query or "silent failure observability", kb_path=kb_path))
    print("  " + str(rag_data.get("retrieved_count", 0)) + " past incident(s) retrieved")

    report = _generate_report(correlation, rag_data, metrics, traces, logs, output_path)
    print("[Report] " + report)

    return {
        "status": "complete",
        "signals_firing": signals,
        "total_findings": correlation.get("total_findings", 0),
        "correlated_patterns": len(correlation.get("correlated_anomalies", [])),
        "rag_retrieved": rag_data.get("retrieved_count", 0),
        "report_path": output_path,
        "correlation": correlation,
    }


def _generate_report(
    correlation, rag_data, metrics, traces, logs, output_path
):
    lines = [
        "# AI Silent Failure Detector - Part 6: Observability Report",
        "",
        "**Generated:** " + datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "**Signals analysed:** metrics, traces, logs",
        "**Signals firing:** " + ", ".join(correlation.get("signals_firing", [])),
        "**Total findings:** " + str(correlation.get("total_findings", 0)),
        "**Correlated patterns:** " + str(len(correlation.get("correlated_anomalies", []))),
        "",
        "---",
        "",
    ]

    lines.append("## Signal Summary")
    lines.append("")
    lines.append("| Signal | Findings |")
    lines.append("|---|---|")
    by_signal = correlation.get("by_signal", {})
    lines.append("| Metrics | " + str(by_signal.get("metrics", 0)) + " |")
    lines.append("| Traces  | " + str(by_signal.get("traces", 0)) + " |")
    lines.append("| Logs    | " + str(by_signal.get("logs", 0)) + " |")
    lines.append("")
    lines.append("---")
    lines.append("")

    explanation = correlation.get("explanation", "")
    if explanation:
        lines.append("## LLM Root Cause Analysis")
        lines.append("")
        lines.append(explanation)
        lines.append("")
        lines.append("---")
        lines.append("")

    correlated = correlation.get("correlated_anomalies", [])
    if correlated:
        lines.append("## Correlated Patterns")
        lines.append("")
        for c in correlated:
            lines.append("### [" + c["severity"] + "] " + c["pattern"].replace("_", " ").title())
            lines.append("")
            lines.append("**Confidence:** " + c["confidence"])
            lines.append("**Signals:** " + ", ".join(c["signals"]))
            lines.append("")
            lines.append(c["description"])
            lines.append("")
            lines.append("---")
            lines.append("")

    ctx = rag_data.get("context", [])
    if ctx:
        lines.append("## RAG Context - Similar Past Incidents")
        lines.append("")
        for inc in ctx:
            lines.append("### " + inc["incident_id"] + " - " + inc["title"])
            lines.append("")
            lines.append("**Root cause:** " + inc["root_cause"])
            lines.append("")
            lines.append("**Business impact:** " + inc["business_impact"])
            lines.append("")
            sc = inc.get("signal_correlation", {})
            if sc:
                lines.append("**Signal correlation:**")
                for signal, note in sc.items():
                    lines.append("  - " + signal + ": " + note)
                lines.append("")
            lines.append("**Runbook:**")
            for step in inc.get("runbook", "").split(". "):
                if step.strip():
                    lines.append("  - " + step.strip())
            lines.append("")
            lines.append("---")
            lines.append("")

    lines.append("## Series Comparison")
    lines.append("")
    lines.append("| Metric | Part 1 | Part 2 | Part 3 | Part 4 | Part 5 | Part 6 |")
    lines.append("|---|---|---|---|---|---|---|")
    lines.append("| Input | Logs | Logs | Screenshots | Logs | Logs | Metrics+Traces+Logs |")
    lines.append("| Signals | 1 | 1 | Visual | 1 | 1 | 3 simultaneously |")
    lines.append("| Cross-signal | No | No | No | No | No | Yes |")
    lines.append("| LLM role | Summary | None | Optional | Optional | None | Root cause reasoning |")

    report = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    return (
        "Report written to " + output_path + ". " +
        str(len(correlated)) + " correlated pattern(s) found."
    )


def main():
    args = parse_args()

    print("")
    print("  AI Silent Failure Detector")
    print("  Part 6: Datadog + LLM Reasoning")
    print("  " + "-" * 44)
    print("")
    print("  Data   : " + args.data)
    print("  Report : " + args.output)
    print("  KB     : " + args.kb)
    print("")

    if not os.path.exists(args.data):
        print("ERROR: Data file not found: " + args.data)
        sys.exit(1)

    result = run_detection(
        data_path=args.data,
        kb_path=args.kb,
        output_path=args.output,
    )

    print("")
    print("  Done")
    print("  Signals firing    : " + str(result["signals_firing"]))
    print("  Findings          : " + str(result["total_findings"]))
    print("  Correlated        : " + str(result["correlated_patterns"]))
    print("  Report            : " + args.output)
    print("")


if __name__ == "__main__":
    start = time.time()
    main()
    print("  Completed in " + str(round(time.time() - start, 1)) + "s")
