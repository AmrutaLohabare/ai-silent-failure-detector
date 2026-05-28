"""
Observability Collectors for Part 6 - Datadog + LLM Reasoning
==============================================================
Three collectors that analyse different observability signals:

  MetricsCollector  - p99 latency, error rate, throughput trends
  TraceAnalyzer     - span duration analysis, bottleneck detection
  LogCorrelator     - error pattern extraction, signal correlation

In production these would query the Datadog API.
Here they work on a local JSON snapshot for offline use.

Datadog API swap points are clearly marked in each collector.
"""

import json
import os
import statistics
from typing import Optional


# ─── Metrics Collector ────────────────────────────────────────────────────

class MetricsCollector:
    """
    Analyses time-series metrics for anomaly patterns.

    Production swap: replace _load_snapshot() with:
        from datadog_api_client import ApiClient, Configuration
        from datadog_api_client.v1.api.metrics_api import MetricsApi
    """

    def __init__(self, snapshot_path: Optional[str] = None):
        self._snapshot = self._load_snapshot(snapshot_path)

    def _load_snapshot(self, path: Optional[str]) -> dict:
        if path is None:
            path = os.path.join(
                os.path.dirname(__file__), "..", "data", "observability_snapshot.json"
            )
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def analyse(self) -> dict:
        """Detect anomalies in metrics time-series data."""
        metrics = self._snapshot.get("metrics", {})
        findings = []

        # Analyse p99 latency
        latency_series = metrics.get("http_request_duration_p99_ms", [])
        if latency_series:
            values = [p["value"] for p in latency_series]
            baseline = statistics.mean(values[:3])  # first 3 points as baseline
            peak = max(values)
            recent_avg = statistics.mean(values[-6:])

            if recent_avg > baseline * 2:
                findings.append({
                    "type": "LATENCY_TREND",
                    "severity": "HIGH",
                    "signal": "metrics",
                    "metric": "http_request_duration_p99_ms",
                    "baseline_ms": round(baseline),
                    "peak_ms": round(peak),
                    "recent_avg_ms": round(recent_avg),
                    "increase_factor": round(recent_avg / baseline, 1),
                    "description": (
                        "p99 latency increased " + str(round(recent_avg / baseline, 1)) +
                        "x over baseline (" + str(round(baseline)) + "ms -> " +
                        str(round(recent_avg)) + "ms avg)"
                    ),
                })

        # Analyse error rate trend
        error_series = metrics.get("http_error_rate_pct", [])
        if error_series:
            values = [p["value"] for p in error_series]
            baseline = statistics.mean(values[:3])
            recent_avg = statistics.mean(values[-6:])

            if recent_avg > 1.0 and recent_avg < 2.0:
                findings.append({
                    "type": "SUB_THRESHOLD_ERROR_TREND",
                    "severity": "MEDIUM",
                    "signal": "metrics",
                    "metric": "http_error_rate_pct",
                    "baseline_pct": round(baseline, 2),
                    "recent_avg_pct": round(recent_avg, 2),
                    "alert_threshold_pct": 2.0,
                    "description": (
                        "Error rate " + str(round(recent_avg, 2)) +
                        "% - below 2% alert threshold but trending up from " +
                        str(round(baseline, 2)) + "% baseline"
                    ),
                })

        # Analyse throughput drop
        throughput_series = metrics.get("http_requests_per_second", [])
        if throughput_series:
            values = [p["value"] for p in throughput_series]
            baseline = values[0]
            recent = values[-1]
            drop_pct = round((baseline - recent) / baseline * 100, 1)

            if drop_pct > 30:
                findings.append({
                    "type": "THROUGHPUT_DROP",
                    "severity": "HIGH",
                    "signal": "metrics",
                    "metric": "http_requests_per_second",
                    "baseline_rps": baseline,
                    "current_rps": recent,
                    "drop_pct": drop_pct,
                    "description": (
                        "Throughput dropped " + str(drop_pct) +
                        "% (" + str(baseline) + " -> " + str(recent) + " RPS) " +
                        "with no corresponding error rate increase"
                    ),
                })

        return {
            "collector": "MetricsCollector",
            "findings_count": len(findings),
            "findings": findings,
        }


# ─── Trace Analyzer ───────────────────────────────────────────────────────

class TraceAnalyzer:
    """
    Analyses distributed traces for bottleneck patterns.

    Production swap: replace _load_snapshot() with:
        from datadog_api_client.v2.api.spans_api import SpansApi
    """

    def __init__(self, snapshot_path: Optional[str] = None):
        self._snapshot = self._load_snapshot(snapshot_path)

    def _load_snapshot(self, path: Optional[str]) -> dict:
        if path is None:
            path = os.path.join(
                os.path.dirname(__file__), "..", "data", "observability_snapshot.json"
            )
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def analyse(self) -> dict:
        """Detect bottleneck spans and trace anomalies."""
        traces = self._snapshot.get("traces", [])
        findings = []

        # Find slow traces
        slow_traces = [t for t in traces if t["duration_ms"] > 1000]

        if slow_traces:
            # Analyse span distribution in slow traces
            bottleneck_services = {}
            for trace in slow_traces:
                total = trace["duration_ms"]
                for span in trace.get("spans", []):
                    pct = span["duration_ms"] / total * 100
                    if pct > 80:
                        svc = span["service"]
                        if svc not in bottleneck_services:
                            bottleneck_services[svc] = []
                        bottleneck_services[svc].append({
                            "trace_id": trace["trace_id"],
                            "pct_of_trace": round(pct, 1),
                            "duration_ms": span["duration_ms"],
                            "operation": span["operation"],
                        })

            for service, occurrences in bottleneck_services.items():
                avg_pct = statistics.mean(o["pct_of_trace"] for o in occurrences)
                avg_duration = statistics.mean(o["duration_ms"] for o in occurrences)
                findings.append({
                    "type": "TRACE_SPAN_BOTTLENECK",
                    "severity": "HIGH",
                    "signal": "traces",
                    "service": service,
                    "occurrences": len(occurrences),
                    "avg_pct_of_trace": round(avg_pct, 1),
                    "avg_duration_ms": round(avg_duration),
                    "operations": list({o["operation"] for o in occurrences}),
                    "description": (
                        service + " consuming avg " + str(round(avg_pct, 1)) +
                        "% of trace duration (" + str(round(avg_duration)) +
                        "ms) across " + str(len(occurrences)) + " slow trace(s)"
                    ),
                })

        return {
            "collector": "TraceAnalyzer",
            "traces_analysed": len(traces),
            "slow_traces": len(slow_traces),
            "findings_count": len(findings),
            "findings": findings,
        }


# ─── Log Correlator ───────────────────────────────────────────────────────

class LogCorrelator:
    """
    Extracts error patterns from logs and correlates with other signals.

    Production swap: replace _load_snapshot() with:
        from datadog_api_client.v2.api.logs_api import LogsApi
    """

    def __init__(self, snapshot_path: Optional[str] = None):
        self._snapshot = self._load_snapshot(snapshot_path)

    def _load_snapshot(self, path: Optional[str]) -> dict:
        if path is None:
            path = os.path.join(
                os.path.dirname(__file__), "..", "data", "observability_snapshot.json"
            )
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def analyse(self) -> dict:
        """Extract error patterns and silent failure signals from logs."""
        logs = self._snapshot.get("logs", [])
        findings = []

        # Count by level and service
        error_logs = [l for l in logs if l["level"] == "ERROR"]
        warn_logs  = [l for l in logs if l["level"] == "WARN"]

        # Pattern: returning HTTP 200 after failure
        silent_200s = [
            l for l in error_logs
            if "returning HTTP 200" in l["message"]
        ]
        if silent_200s:
            services = list({l["service"] for l in silent_200s})
            findings.append({
                "type": "SILENT_200_ON_FAILURE",
                "severity": "HIGH",
                "signal": "logs",
                "count": len(silent_200s),
                "services": services,
                "description": (
                    str(len(silent_200s)) + " log entries show HTTP 200 returned after failure. " +
                    "Services: " + ", ".join(services)
                ),
                "sample_messages": [l["message"] for l in silent_200s[:2]],
            })

        # Pattern: idempotency key collisions
        idempotency_errors = [
            l for l in error_logs
            if "idempotency" in l["message"].lower()
        ]
        if idempotency_errors:
            findings.append({
                "type": "IDEMPOTENCY_COLLISION",
                "severity": "HIGH",
                "signal": "logs",
                "count": len(idempotency_errors),
                "description": (
                    str(len(idempotency_errors)) +
                    " idempotency key collisions detected - possible duplicate charges"
                ),
                "sample_messages": [l["message"] for l in idempotency_errors[:2]],
            })

        # Pattern: retry escalation
        retry_logs = [
            l for l in warn_logs
            if "retry" in l["message"].lower() or "retrying" in l["message"].lower()
        ]
        if len(retry_logs) >= 2:
            findings.append({
                "type": "RETRY_ESCALATION",
                "severity": "MEDIUM",
                "signal": "logs",
                "count": len(retry_logs),
                "description": (
                    str(len(retry_logs)) + " retry warning(s) detected. " +
                    "Escalating retry pattern indicates upstream dependency degradation."
                ),
            })

        return {
            "collector": "LogCorrelator",
            "logs_analysed": len(logs),
            "error_count": len(error_logs),
            "warn_count": len(warn_logs),
            "findings_count": len(findings),
            "findings": findings,
        }
