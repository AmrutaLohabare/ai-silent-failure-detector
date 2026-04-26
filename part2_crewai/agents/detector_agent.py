"""
Detector Agent — Part 2: CrewAI
================================
Role    : Aggressive log scanner. Flags every anomaly it finds.
Persona : "Better to over-flag than miss a real failure."
RAG use : None — pure detection logic, no knowledge base access.
          (The Analyzer challenges findings using RAG.)
"""

import json
import re
from collections import defaultdict
from typing import Optional


# ─── Core Detection Logic ─────────────────────────────────────────────────

def ingest_logs(source: str, window_minutes: int = 60) -> str:
    """Parse raw log lines into structured JSON."""
    try:
        with open(source, "r", encoding="utf-8") as f:
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
                "error": d.get("e") or "",
            })

    return json.dumps({
        "total_entries": len(entries),
        "window_minutes": window_minutes,
        "entries": entries[:500],
    })


def detect_anomalies(log_data: str, error_threshold: float = 0.02) -> str:
    """
    Detect all silent failure patterns.
    Detector is intentionally aggressive — it flags
    everything suspicious and lets the Analyzer decide.
    """
    try:
        data = json.loads(log_data)
        entries = data.get("entries", [])
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid log_data"})

    if not entries:
        return json.dumps({
            "anomaly_count": 0,
            "anomalies": [],
            "entries_analysed": 0,
            "detector_note": "No entries to analyse.",
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
                f"{len(empty_200s)} HTTP 200 responses with zero-byte body. "
                "Server reports success but delivers no data."
            ),
            "detector_confidence": "HIGH",
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
                    f"Path '{path}' has {round(rate * 100, 2)}% error rate — "
                    f"below {error_threshold * 100}% threshold but statistically significant."
                ),
                "detector_confidence": "MEDIUM",
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
                    f"{len(slow)} successful requests took >3x average ({round(avg)}ms). "
                    "Possible silent timeouts or retries masking failures."
                ),
                "detector_confidence": "MEDIUM",
            })

    return json.dumps({
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
        "entries_analysed": len(entries),
        "detector_note": (
            "Findings are unvalidated. Analyzer must review each before escalation."
        ),
    })


class DetectorAgent:
    """
    Wraps the detection logic as a CrewAI-compatible agent interface.
    In collaborative mode, findings are posted to the shared message
    channel for the Analyzer to review.
    """

    def __init__(self, error_threshold: float = 0.02):
        self.error_threshold = error_threshold
        self.name = "Detector"
        self.role = "Silent failure scanner"
        self.goal = (
            "Scan production logs and flag every potential silent failure pattern. "
            "Be aggressive — it is better to over-flag than to miss a real failure. "
            "The Analyzer will validate each finding."
        )
        self.backstory = (
            "You are a QA engineer who has been burned by silent failures too many times. "
            "You once missed a payment processing failure that cost the company $42,000 "
            "because the error rate was 1.8% and your alert threshold was 2%. "
            "Now you flag everything suspicious and let the Analyzer decide."
        )

    def run(self, log_source: str, window_minutes: int = 60) -> dict:
        """Run detection pipeline and return structured findings."""
        print(f"\n[{self.name}] Ingesting logs from {log_source}...")
        log_data = ingest_logs(log_source, window_minutes)
        log_parsed = json.loads(log_data)

        if "error" in log_parsed:
            return {"error": log_parsed["error"], "anomalies": []}

        print(f"[{self.name}] {log_parsed['total_entries']} entries parsed. Detecting anomalies...")
        anomaly_data = detect_anomalies(log_data, self.error_threshold)
        anomaly_parsed = json.loads(anomaly_data)

        count = anomaly_parsed.get("anomaly_count", 0)
        print(f"[{self.name}] {count} potential silent failure(s) flagged. Posting to channel...")

        return {
            "agent": self.name,
            "log_data": log_data,
            "anomaly_data": anomaly_data,
            "anomalies": anomaly_parsed.get("anomalies", []),
            "entries_analysed": anomaly_parsed.get("entries_analysed", 0),
        }
