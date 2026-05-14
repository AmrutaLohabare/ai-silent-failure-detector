"""
Semantic Kernel Skills for Part 4 — AI Silent Failure Detector
===============================================================
Four native SK skills using the @kernel_function decorator:

  LogIngestionSkill     - parse raw logs into structured JSON
  AnomalyDetectionSkill - detect 3 silent failure patterns
  AzureRAGSkill         - retrieve past incidents (local TF-IDF mock)
  ReporterSkill         - generate enriched Markdown report

Each skill is a plain Python class with methods decorated with
@kernel_function. The Kernel invokes them by name.

Azure AI Search mock:
  In production this would use azure-search-documents to query
  an Azure AI Search index. Here we use TF-IDF for offline use
  so the project runs on Windows without an Azure subscription.
  The mock is swappable — see AzureRAGSkill._build_retriever().
"""

import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Annotated, Optional

from semantic_kernel.functions import kernel_function


# ─── Skill 1: Log Ingestion ───────────────────────────────────────────────

class LogIngestionSkill:
    """
    SK Skill: Ingest raw production log files.
    Parses common log format into structured JSON entries.
    """

    @kernel_function(
        name="ingest_logs",
        description="Parse a production log file into structured JSON entries",
    )
    def ingest_logs(
        self,
        source: Annotated[str, "Path to the log file"],
        window_minutes: Annotated[int, "Time window in minutes"] = 60,
    ) -> str:
        try:
            with open(source, "r", encoding="utf-8") as f:
                raw_lines = f.readlines()
        except FileNotFoundError:
            return json.dumps({"error": "Log file not found: " + source})

        pattern = (
            r"(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
            r"\s+(?P<level>\w+)"
            r"\s+(?P<status>\d{3})"
            r"\s+(?P<method>\w+)"
            r"\s+(?P<path>\S+)"
            r"\s+response_size=(?P<response_size>\d+)"
            r"\s+duration_ms=(?P<duration_ms>\d+)"
            r'(?:\s+error="(?P<error>[^"]*)")?'
        )

        entries = []
        for line in raw_lines:
            line = line.strip()
            if not line:
                continue
            m = re.match(pattern, line)
            if m:
                d = m.groupdict()
                entries.append({
                    "timestamp": d["timestamp"],
                    "level": d["level"],
                    "status": int(d["status"]),
                    "method": d["method"],
                    "path": d["path"],
                    "response_size": int(d["response_size"]),
                    "duration_ms": int(d["duration_ms"]),
                    "error": d.get("error") or "",
                })

        return json.dumps({
            "total_entries": len(entries),
            "window_minutes": window_minutes,
            "entries": entries[:500],
        })


# ─── Skill 2: Anomaly Detection ───────────────────────────────────────────

class AnomalyDetectionSkill:
    """
    SK Skill: Detect silent failure patterns in parsed log data.
    Detects 3 patterns: empty 200s, sub-threshold errors, latency spikes.
    """

    @kernel_function(
        name="detect_anomalies",
        description="Detect silent failure patterns in parsed log JSON",
    )
    def detect_anomalies(
        self,
        log_data: Annotated[str, "JSON string from LogIngestionSkill"],
        error_threshold: Annotated[float, "Error rate threshold (0.02 = 2%)"] = 0.02,
    ) -> str:
        try:
            data = json.loads(log_data)
            entries = data.get("entries", [])
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid log_data JSON"})

        if not entries:
            return json.dumps({
                "anomaly_count": 0,
                "anomalies": [],
                "entries_analysed": 0,
            })

        anomalies = []

        # Pattern 1: HTTP 200 with empty response body
        empty_200s = [e for e in entries if e["status"] == 200 and e["response_size"] == 0]
        if empty_200s:
            paths = list({e["path"] for e in empty_200s})
            anomalies.append({
                "type": "EMPTY_SUCCESS_RESPONSE",
                "severity": "HIGH",
                "count": len(empty_200s),
                "affected_paths": paths[:10],
                "description": (
                    str(len(empty_200s)) + " HTTP 200 responses with zero-byte body. "
                    "Server reports success but delivers no data."
                ),
            })

        # Pattern 2: Sub-threshold error rate per path
        path_totals: dict = defaultdict(int)
        path_errors: dict = defaultdict(int)
        for e in entries:
            path_totals[e["path"]] += 1
            if e["status"] >= 400 or e.get("error"):
                path_errors[e["path"]] += 1

        for path, total in path_totals.items():
            if total < 10:
                continue
            rate = path_errors[path] / total
            if 0.01 <= rate < error_threshold:
                anomalies.append({
                    "type": "SUB_THRESHOLD_ERROR_RATE",
                    "severity": "MEDIUM",
                    "path": path,
                    "error_rate_pct": round(rate * 100, 2),
                    "total_requests": total,
                    "error_count": path_errors[path],
                    "description": (
                        "Path '" + path + "' has " + str(round(rate * 100, 2)) + "% error rate "
                        "below the " + str(error_threshold * 100) + "% threshold."
                    ),
                })

        # Pattern 3: Latency spike on successful requests
        success_entries = [e for e in entries if e["status"] < 400]
        if success_entries:
            durations = [e["duration_ms"] for e in success_entries]
            avg = sum(durations) / len(durations)
            slow = [e for e in success_entries if e["duration_ms"] > avg * 3]
            if len(slow) > 5:
                slow_paths = list({e["path"] for e in slow})
                anomalies.append({
                    "type": "LATENCY_SPIKE_ON_SUCCESS",
                    "severity": "MEDIUM",
                    "count": len(slow),
                    "avg_duration_ms": round(avg),
                    "spike_threshold_ms": round(avg * 3),
                    "affected_paths": slow_paths[:10],
                    "description": (
                        str(len(slow)) + " successful requests took >3x average "
                        "(" + str(round(avg)) + "ms). Possible silent retries."
                    ),
                })

        return json.dumps({
            "anomaly_count": len(anomalies),
            "anomalies": anomalies,
            "entries_analysed": len(entries),
        })


# ─── Skill 3: Azure RAG (local TF-IDF mock) ──────────────────────────────

class AzureRAGSkill:
    """
    SK Skill: Retrieve similar past incidents from the knowledge base.

    Production use: swap _build_retriever() to use
    azure.search.documents.SearchClient for Azure AI Search.

    Offline/dev: uses TF-IDF keyword overlap — no Azure subscription needed.
    """

    def __init__(self, kb_path: Optional[str] = None):
        self._kb_path = kb_path
        self._retriever = None

    def _build_retriever(self) -> object:
        if self._retriever is not None:
            return self._retriever

        # Production swap point:
        # from azure.search.documents import SearchClient
        # return SearchClient(endpoint, index_name, credential)

        # Offline TF-IDF mock
        kb = self._kb_path or os.path.join(
            os.path.dirname(__file__), "..", "knowledge_base", "incidents.json"
        )
        with open(kb, encoding="utf-8") as f:
            incidents = json.load(f)

        docs = []
        for inc in incidents:
            text = (
                inc["id"] + " " + inc["title"] + " " +
                inc["type"] + " " + inc.get("path_pattern", "") + " " +
                inc["root_cause"] + " " +
                " ".join(inc.get("tags", []))
            ).lower()
            docs.append({"text": text, "metadata": inc})

        self._retriever = docs
        print("[AzureRAGSkill] Loaded " + str(len(docs)) + " incidents (local TF-IDF mock).")
        return docs

    def _query(self, query_text: str, k: int = 2) -> list:
        docs = self._build_retriever()
        query_terms = set(re.findall(r"\w+", query_text.lower()))
        scored = []
        for doc in docs:
            doc_terms = set(re.findall(r"\w+", doc["text"]))
            score = len(query_terms & doc_terms)
            scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:k]]

    @kernel_function(
        name="retrieve_context",
        description=(
            "Query the Azure AI Search index for similar past incidents. "
            "Returns root cause, business impact, and runbook for each match."
        ),
    )
    def retrieve_context(
        self,
        anomaly_summary: Annotated[str, "Description of the detected anomaly"],
        k: Annotated[int, "Number of results to return"] = 2,
    ) -> str:
        results = self._query(anomaly_summary, k=k)
        items = []
        for doc in results:
            m = doc["metadata"]
            items.append({
                "incident_id": m["id"],
                "title": m["title"],
                "type": m["type"],
                "azure_service": m.get("azure_service", ""),
                "root_cause": m["root_cause"],
                "business_impact": m["business_impact"],
                "detection_lag_hours": m.get("detection_lag_hours", "unknown"),
                "runbook": m.get("runbook", "No runbook available."),
                "agent_verdict": m.get("agent_verdict", "UNKNOWN"),
                "tags": ", ".join(m.get("tags", [])),
            })
        return json.dumps({"retrieved_count": len(items), "context": items})


# ─── Skill 4: Reporter ────────────────────────────────────────────────────

class ReporterSkill:
    """
    SK Skill: Generate enriched Markdown report from anomaly + RAG data.
    Includes Azure service attribution and a Part 1-4 comparison table.
    """

    @kernel_function(
        name="generate_report",
        description="Generate enriched Markdown report from anomaly and RAG context data",
    )
    def generate_report(
        self,
        anomaly_data: Annotated[str, "JSON from AnomalyDetectionSkill"],
        rag_context: Annotated[str, "JSON from AzureRAGSkill"] = "{}",
        output_path: Annotated[str, "Path to write report"] = "reports/silent_failure_report.md",
    ) -> str:
        try:
            data = json.loads(anomaly_data)
        except json.JSONDecodeError:
            return "Error: Invalid anomaly_data JSON"

        anomalies = data.get("anomalies", [])
        count = data.get("anomaly_count", 0)
        entries = data.get("entries_analysed", 0)
        severity_icon = {"HIGH": "[HIGH]", "MEDIUM": "[MED]", "LOW": "[LOW]"}

        try:
            ctx_data = json.loads(rag_context)
            ctx_items = ctx_data.get("context", [])
        except json.JSONDecodeError:
            ctx_items = []

        lines = [
            "# AI Silent Failure Detector - Part 4: Semantic Kernel Report",
            "",
            "**Generated:** " + datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "**Entries analysed:** " + str(entries),
            "**Silent failures detected:** " + str(count),
            "**Stack:** Semantic Kernel 1.41.3 + Azure AI Search (local TF-IDF mock)",
            "",
            "---",
            "",
        ]

        if not anomalies:
            lines.append("No silent failures detected.")
        else:
            for i, a in enumerate(anomalies, 1):
                sev = a.get("severity", "MEDIUM")
                icon = severity_icon.get(sev, "[?]")
                lines.append("## " + icon + " Finding " + str(i) + ": " + a["type"].replace("_", " ").title())
                lines.append("")
                lines.append("**Severity:** " + sev)
                lines.append("**Description:** " + a["description"])
                lines.append("")

                if a.get("affected_paths"):
                    lines.append("**Affected paths:**")
                    for p in a["affected_paths"]:
                        lines.append("  - " + p)
                if a.get("path"):
                    lines.append("**Path:** " + a["path"])
                if a.get("error_rate_pct"):
                    lines.append("**Error rate:** " + str(a["error_rate_pct"]) + "%")
                lines.append("")

                if ctx_items:
                    lines.append("### Azure RAG Context - Similar past incidents")
                    lines.append("")
                    for ctx in ctx_items[:2]:
                        azure_svc = ctx.get("azure_service", "")
                        lines.append("**" + ctx["incident_id"] + " - " + ctx["title"] + "**")
                        if azure_svc:
                            lines.append("**Azure service:** " + azure_svc)
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
        lines.append("| Metric | Part 1 | Part 2 | Part 3 | Part 4 |")
        lines.append("|---|---|---|---|---|")
        lines.append("| Orchestration | LangChain | CrewAI | Direct Python | Semantic Kernel |")
        lines.append("| Vector store | FAISS | TF-IDF | TF-IDF | Azure AI Search |")
        lines.append("| Multi-agent | No | Yes (3 agents) | No | No (Planner) |")
        lines.append("| Target stack | Any | Any | UI/visual | Azure enterprise |")
        lines.append("| Tests | 31 | 26 | 30 | TBD |")

        report = "\n".join(lines)
        os.makedirs(
            os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
            exist_ok=True
        )
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)

        return (
            "Report written to " + output_path + ". "
            + str(count) + " silent failure(s) found across " + str(entries) + " log entries."
        )
