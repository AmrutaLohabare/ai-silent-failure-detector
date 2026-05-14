"""
AI Silent Failure Detector - Part 4: Semantic Kernel
=====================================================
Builds a Semantic Kernel instance, registers 4 skills,
then runs them in a planned pipeline to detect silent failures.

Usage (Windows Command Prompt):
    python main.py
    python main.py --log logs/sample_prod.log
    python main.py --log logs/sample_prod.log --output reports/my_report.md

No Azure subscription needed - runs fully offline with local TF-IDF mock.
Optional: set OPENAI_API_KEY in .env to enable LLM-powered SK planner.
"""

import argparse
import json
import os
import sys
import time

from dotenv import load_dotenv
load_dotenv()


def parse_args():
    parser = argparse.ArgumentParser(
        description="AI Silent Failure Detector - Part 4: Semantic Kernel"
    )
    parser.add_argument(
        "--log",
        default=os.path.join("logs", "sample_prod.log"),
        help="Path to the log file to analyse"
    )
    parser.add_argument(
        "--output",
        default=os.path.join("reports", "silent_failure_report.md"),
        help="Path to write the report"
    )
    parser.add_argument(
        "--kb",
        default=os.path.join("knowledge_base", "incidents.json"),
        help="Path to knowledge base JSON"
    )
    return parser.parse_args()


def build_kernel(api_key=None):
    """
    Build and return a Semantic Kernel instance.
    Adds OpenAI chat service if API key is available.
    Skills work without a chat service (offline mode).
    """
    from semantic_kernel import Kernel

    kernel = Kernel()

    key = api_key or os.getenv("OPENAI_API_KEY", "")
    if key and key != "sk-your-key-here":
        from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
        kernel.add_service(
            OpenAIChatCompletion(
                service_id="openai",
                ai_model_id="gpt-4o",
                api_key=key,
            )
        )
        print("  Kernel: OpenAI GPT-4o connected")
    else:
        print("  Kernel: offline mode (no API key)")

    return kernel


def main():
    args = parse_args()

    print("")
    print("  AI Silent Failure Detector")
    print("  Part 4: Semantic Kernel + Azure AI Search")
    print("  " + "-" * 46)
    print("")
    print("  Log    : " + args.log)
    print("  Report : " + args.output)
    print("  KB     : " + args.kb)
    print("")

    if not os.path.exists(args.log):
        print("ERROR: Log file not found: " + args.log)
        sys.exit(1)

    os.makedirs(
        os.path.dirname(args.output) if os.path.dirname(args.output) else ".",
        exist_ok=True
    )

    # Import skills
    from skills.detection_skills import (
        LogIngestionSkill,
        AnomalyDetectionSkill,
        AzureRAGSkill,
        ReporterSkill,
    )

    # Build kernel and register skills
    print("[Kernel] Building Semantic Kernel...")
    kernel = build_kernel()

    # Register all 4 skills as kernel plugins
    kernel.add_plugin(LogIngestionSkill(),      plugin_name="LogIngestion")
    kernel.add_plugin(AnomalyDetectionSkill(),  plugin_name="AnomalyDetection")
    kernel.add_plugin(AzureRAGSkill(kb_path=args.kb), plugin_name="AzureRAG")
    kernel.add_plugin(ReporterSkill(),          plugin_name="Reporter")
    print("[Kernel] 4 skills registered: LogIngestion, AnomalyDetection, AzureRAG, Reporter")
    print("")

    # ─── Step 1: Log Ingestion ────────────────────────────────────────
    print("[Skill 1/4] LogIngestionSkill.ingest_logs...")
    import asyncio

    async def run_pipeline():
        log_result = await kernel.invoke(
            plugin_name="LogIngestion",
            function_name="ingest_logs",
            source=args.log,
            window_minutes=60,
        )
        log_data = str(log_result)
        log_parsed = json.loads(log_data)
        if "error" in log_parsed:
            print("ERROR: " + log_parsed["error"])
            sys.exit(1)
        print("  " + str(log_parsed["total_entries"]) + " entries parsed")

        # ─── Step 2: Anomaly Detection ────────────────────────────────
        print("[Skill 2/4] AnomalyDetectionSkill.detect_anomalies...")
        anomaly_result = await kernel.invoke(
            plugin_name="AnomalyDetection",
            function_name="detect_anomalies",
            log_data=log_data,
            error_threshold=0.02,
        )
        anomaly_data = str(anomaly_result)
        anomaly_parsed = json.loads(anomaly_data)
        count = anomaly_parsed.get("anomaly_count", 0)
        print("  " + str(count) + " silent failure(s) detected")

        # ─── Step 3: Azure RAG Context ────────────────────────────────
        print("[Skill 3/4] AzureRAGSkill.retrieve_context...")
        anomaly_summary = " ".join([
            a["type"] + " " + a.get("description", "")
            for a in anomaly_parsed.get("anomalies", [])
        ])
        rag_result = await kernel.invoke(
            plugin_name="AzureRAG",
            function_name="retrieve_context",
            anomaly_summary=anomaly_summary or "silent failure log anomaly",
            k=2,
        )
        rag_data = str(rag_result)
        rag_parsed = json.loads(rag_data)
        print("  " + str(rag_parsed.get("retrieved_count", 0)) + " past incident(s) retrieved")

        # ─── Step 4: Report Generation ────────────────────────────────
        print("[Skill 4/4] ReporterSkill.generate_report...")
        report_result = await kernel.invoke(
            plugin_name="Reporter",
            function_name="generate_report",
            anomaly_data=anomaly_data,
            rag_context=rag_data,
            output_path=args.output,
        )
        print("  " + str(report_result))

        return {
            "status": "complete",
            "total_findings": count,
            "anomaly_data": anomaly_data,
            "rag_data": rag_data,
            "report_path": args.output,
        }

    result = asyncio.run(run_pipeline())

    print("")
    print("  Done")
    print("  Findings : " + str(result["total_findings"]) + " silent failure(s)")
    print("  Report   : " + args.output)
    print("")


def run_detection(
    log_source,
    kb_path=None,
    output_path="reports/silent_failure_report.md",
):
    """Importable wrapper for tests."""
    import asyncio
    from skills.detection_skills import (
        LogIngestionSkill,
        AnomalyDetectionSkill,
        AzureRAGSkill,
        ReporterSkill,
    )
    from semantic_kernel import Kernel

    kernel = Kernel()
    kernel.add_plugin(LogIngestionSkill(),      plugin_name="LogIngestion")
    kernel.add_plugin(AnomalyDetectionSkill(),  plugin_name="AnomalyDetection")
    kernel.add_plugin(AzureRAGSkill(kb_path=kb_path), plugin_name="AzureRAG")
    kernel.add_plugin(ReporterSkill(),          plugin_name="Reporter")

    async def _run():
        log_result = await kernel.invoke(
            plugin_name="LogIngestion",
            function_name="ingest_logs",
            source=log_source,
        )
        log_data = str(log_result)

        anomaly_result = await kernel.invoke(
            plugin_name="AnomalyDetection",
            function_name="detect_anomalies",
            log_data=log_data,
        )
        anomaly_data = str(anomaly_result)
        anomaly_parsed = json.loads(anomaly_data)

        anomaly_summary = " ".join([
            a["type"] + " " + a.get("description", "")
            for a in anomaly_parsed.get("anomalies", [])
        ])
        rag_result = await kernel.invoke(
            plugin_name="AzureRAG",
            function_name="retrieve_context",
            anomaly_summary=anomaly_summary or "silent failure",
        )
        rag_data = str(rag_result)

        await kernel.invoke(
            plugin_name="Reporter",
            function_name="generate_report",
            anomaly_data=anomaly_data,
            rag_context=rag_data,
            output_path=output_path,
        )

        return {
            "status": "complete",
            "total_findings": anomaly_parsed.get("anomaly_count", 0),
            "anomaly_data": anomaly_data,
            "rag_data": rag_data,
            "report_path": output_path,
        }

    return asyncio.run(_run())


if __name__ == "__main__":
    start = time.time()
    main()
    print("  Completed in " + str(round(time.time() - start, 1)) + "s")
