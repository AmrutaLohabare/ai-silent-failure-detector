"""
AI Silent Failure Detector — Part 1: Agentic AI + RAG
Author: Your Name
LinkedIn: linkedin.com/in/yourprofile
GitHub: github.com/yourusername/ai-silent-failure-detector

Detects silent failures in production logs that traditional monitors miss:
  - HTTP 200s with empty response bodies
  - Error rates hovering just below alert thresholds
  - Successful status codes masking downstream failures
"""

import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field


# ─── Tool 1: Log Ingestion ─────────────────────────────────────────────────

def log_ingestion(source: str, window_minutes: int = 60) -> str:
    """Parse raw log lines into structured JSON."""
    try:
        with open(source, "r") as f:
            raw_lines = f.readlines()
    except FileNotFoundError:
        return json.dumps({"error": f"Log file not found: {source}"})

    entries = []
    pattern = (
        r'(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})'
        r'\s+(?P<level>\w+)'
        r'\s+(?P<status>\d{3})'
        r'\s+(?P<method>\w+)'
        r'\s+(?P<path>\S+)'
        r'\s+response_size=(?P<response_size>\d+)'
        r'\s+duration_ms=(?P<duration_ms>\d+)'
        r'(?:\s+error="(?P<e>[^"]*)")?'
    )
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        match = re.match(pattern, line)
        if match:
            d = match.groupdict()
            entries.append({
                "timestamp": d["timestamp"],
                "level": d["level"],
                "status": int(d["status"]),
                "method": d["method"],
                "path": d["path"],
                "response_size": int(d["response_size"]),
                "duration_ms": int(d["duration_ms"]),
                "error": d.get("e") or "",
            })

    return json.dumps({
        "total_entries": len(entries),
        "window_minutes": window_minutes,
        "entries": entries[:500],
    })


# ─── Tool 2: Anomaly Detection ─────────────────────────────────────────────

def anomaly_detector(log_data: str, error_threshold: float = 0.02) -> str:
    """Detect silent failure patterns in parsed log data."""
    try:
        data = json.loads(log_data)
        entries = data.get("entries", [])
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid log_data JSON"})

    if not entries:
        return json.dumps({"anomaly_count": 0, "anomalies": [], "entries_analysed": 0})

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
                f"{len(empty_200s)} requests returned HTTP 200 with zero-byte response body. "
                "Classic silent failure — server reports success but delivers no data."
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
                    f"Path '{path}' has a {round(rate * 100, 2)}% error rate — "
                    f"below the {error_threshold * 100}% alert threshold but significant."
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
                    f"{len(slow)} successful requests took more than 3x the average "
                    f"({round(avg)}ms). May indicate silent timeouts or retries."
                ),
            })

    return json.dumps({
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
        "entries_analysed": len(entries),
    })


# ─── Tool 3: RAG Context ───────────────────────────────────────────────────

def rag_context(anomaly_summary: str, kb_path: Optional[str] = None) -> str:
    """Retrieve similar past incidents from the knowledge base."""
    if kb_path is None:
        kb_path = os.path.join(
            os.path.dirname(__file__), "..", "knowledge_base", "incidents.json"
        )
    try:
        with open(kb_path) as f:
            incidents = json.load(f)
    except FileNotFoundError:
        return json.dumps({"context": [], "message": "Knowledge base not found."})

    # TF-IDF style keyword scoring
    query_terms = set(re.findall(r'\w+', anomaly_summary.lower()))
    scored = []
    for inc in incidents:
        text = (
            f"{inc.get('type','')} {inc.get('title','')} "
            f"{inc.get('root_cause','')} {' '.join(inc.get('tags',[]))}"
        ).lower()
        inc_terms = set(re.findall(r'\w+', text))
        score = len(query_terms & inc_terms)
        scored.append((score, inc))
    scored.sort(key=lambda x: x[0], reverse=True)

    context_items = []
    for _, inc in scored[:2]:
        context_items.append({
            "incident_id": inc.get("id", ""),
            "title": inc.get("title", ""),
            "failure_type": inc.get("type", ""),
            "root_cause": inc.get("root_cause", ""),
            "business_impact": inc.get("business_impact", ""),
            "detection_lag_hours": inc.get("detection_lag_hours", ""),
            "runbook": inc.get("runbook", "No runbook available."),
            "tags": ", ".join(inc.get("tags", [])),
        })

    return json.dumps({"retrieved_count": len(context_items), "context": context_items})


# ─── Tool 4: Report Generator ──────────────────────────────────────────────

def silent_failure_reporter(
    anomaly_data: str,
    rag_context_data: str = "{}",
    output_path: str = "reports/silent_failure_report.md"
) -> str:
    """Generate a Markdown report from anomaly data and RAG context."""
    try:
        data = json.loads(anomaly_data)
    except json.JSONDecodeError:
        return "Error: Invalid anomaly_data JSON"

    anomalies = data.get("anomalies", [])
    count = data.get("anomaly_count", 0)
    entries = data.get("entries_analysed", 0)
    severity_icon = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}

    lines = [
        "# AI Silent Failure Detector — Report",
        f"\n**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Entries analysed:** {entries}",
        f"**Silent failures detected:** {count}",
        "\n---\n",
    ]

    if not anomalies:
        lines.append("✅ No silent failures detected in this window.")
    else:
        for i, a in enumerate(anomalies, 1):
            icon = severity_icon.get(a.get("severity", "LOW"), "⚪")
            lines.append(f"## {icon} Finding {i}: {a['type'].replace('_', ' ').title()}")
            lines.append(f"\n**Severity:** {a.get('severity')}")
            lines.append(f"\n**Description:** {a['description']}\n")
            if "affected_paths" in a:
                lines.append("**Affected paths:**")
                for p in a["affected_paths"]:
                    lines.append(f"- `{p}`")
            if "path" in a:
                lines.append(f"**Path:** `{a['path']}`")
            if "error_rate_pct" in a:
                lines.append(f"**Error rate:** {a['error_rate_pct']}%")

            # RAG context
            try:
                ctx_data = json.loads(rag_context_data)
                ctx_items = ctx_data.get("context", [])
                if ctx_items:
                    lines.append("\n### 🔍 Similar past incidents")
                    for ctx in ctx_items[:2]:
                        lines.append(f"\n**{ctx.get('incident_id')} — {ctx.get('title')}**")
                        lines.append(f"\n**Root cause:** {ctx.get('root_cause')}")
                        lines.append(f"\n**Business impact:** {ctx.get('business_impact')}")
                        lines.append(f"\n**Detection lag:** {ctx.get('detection_lag_hours')} hours")
                        lines.append(f"\n**Runbook:**")
                        for step in ctx.get("runbook", "").split(". "):
                            if step.strip():
                                lines.append(f"  - {step.strip()}")
            except Exception:
                pass

            lines.append("\n---\n")

    report = "\n".join(lines)
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    return f"Report written to {output_path}. {count} silent failure(s) found across {entries} log entries."


# ─── Agentic Orchestrator (no LangChain agent layer needed) ───────────────

def run_detection(
    log_source: str,
    window_minutes: int = 60,
    kb_path: Optional[str] = None,
    output_path: str = "reports/silent_failure_report.md",
) -> str:
    """
    Main entry point. Runs the 4-tool detection pipeline:
      1. log_ingestion       — parse raw logs
      2. anomaly_detector    — detect silent failure patterns
      3. rag_context         — retrieve similar past incidents
      4. silent_failure_reporter — generate enriched report

    Uses ChatOpenAI for the final summary only.
    The tool pipeline runs deterministically — no agent loop needed.
    """
    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    print("\n[Step 1/4] Ingesting logs...")
    log_data = log_ingestion(log_source, window_minutes)
    log_parsed = json.loads(log_data)
    if "error" in log_parsed:
        return f"Log ingestion failed: {log_parsed['error']}"
    print(f"           ✓ {log_parsed['total_entries']} entries parsed")

    print("[Step 2/4] Detecting anomalies...")
    anomaly_data = anomaly_detector(log_data)
    anomaly_parsed = json.loads(anomaly_data)
    count = anomaly_parsed.get("anomaly_count", 0)
    print(f"           ✓ {count} silent failure pattern(s) found")

    print("[Step 3/4] Retrieving RAG context...")
    anomaly_summary = " ".join([
        f"{a['type']} on {a.get('affected_paths', [a.get('path','')])} {a['description']}"
        for a in anomaly_parsed.get("anomalies", [])
    ])
    rag_data = rag_context(anomaly_summary, kb_path)
    rag_parsed = json.loads(rag_data)
    print(f"           ✓ {rag_parsed.get('retrieved_count', 0)} past incident(s) retrieved")

    print("[Step 4/4] Generating report...")
    report_result = silent_failure_reporter(anomaly_data, rag_data, output_path)
    print(f"           ✓ {report_result}")

    # Use LLM to generate a human-readable executive summary
    print("\n[LLM] Generating executive summary...")
    messages = [
        SystemMessage(content=(
            "You are a senior QA engineer. Given the anomaly data and past incident context, "
            "write a concise 3-5 sentence executive summary of what silent failures were found, "
            "their likely root causes based on past incidents, and the most critical next action."
        )),
        HumanMessage(content=(
            f"Anomalies detected:\n{anomaly_data}\n\n"
            f"Past incident context:\n{rag_data}"
        )),
    ]
    summary = llm.invoke(messages)
    return summary.content


if __name__ == "__main__":
    import sys
    log_path = sys.argv[1] if len(sys.argv) > 1 else "logs/sample_prod.log"
    print(run_detection(log_path))
