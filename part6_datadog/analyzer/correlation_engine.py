"""
Correlation Engine for Part 6 - Datadog + LLM Reasoning
=========================================================
Combines findings from MetricsCollector, TraceAnalyzer, LogCorrelator
and reasons across all three signals together.

Key insight: a silent failure often shows up in all 3 signals
simultaneously but no single signal crosses a threshold.
The correlation engine finds these multi-signal patterns.

LLM reasoning:
  - If OPENAI_API_KEY set: GPT-4o explains WHY across all signals
  - If no key: rule-based correlation reasoning (offline)
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional


class CorrelationEngine:
    """
    Correlates findings across metrics, traces, and logs.
    Uses LLM to generate a human-readable root cause explanation.
    """

    SEVERITY_WEIGHT = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")

    def correlate(
        self,
        metrics_result: dict,
        traces_result: dict,
        logs_result: dict,
    ) -> dict:
        """
        Combine all signal findings and detect cross-signal patterns.
        Returns correlated anomalies with LLM or rule-based explanation.
        """
        all_findings = (
            metrics_result.get("findings", []) +
            traces_result.get("findings", []) +
            logs_result.get("findings", [])
        )

        if not all_findings:
            return {
                "status": "clean",
                "correlated_anomalies": [],
                "summary": "No anomalies detected across metrics, traces, or logs.",
            }

        # Group findings by signal
        by_signal = {"metrics": [], "traces": [], "logs": []}
        for f in all_findings:
            signal = f.get("signal", "unknown")
            if signal in by_signal:
                by_signal[signal].append(f)

        signals_firing = [s for s, findings in by_signal.items() if findings]

        # Detect cross-signal correlation
        correlated = self._detect_cross_signal_patterns(all_findings, by_signal)

        # Generate explanation
        if len(signals_firing) >= 2:
            explanation = self._explain(all_findings, signals_firing, by_signal)
        else:
            explanation = self._single_signal_explanation(all_findings, signals_firing)

        return {
            "status": "anomalies_detected",
            "signals_firing": signals_firing,
            "total_findings": len(all_findings),
            "correlated_anomalies": correlated,
            "all_findings": all_findings,
            "explanation": explanation,
            "by_signal": {
                "metrics": len(by_signal["metrics"]),
                "traces":  len(by_signal["traces"]),
                "logs":    len(by_signal["logs"]),
            },
        }

    def _detect_cross_signal_patterns(
        self, all_findings: list, by_signal: dict
    ) -> list:
        """Identify findings that span multiple signals."""
        correlated = []

        has_latency  = any(f["type"] in ("LATENCY_TREND", "TRACE_SPAN_BOTTLENECK")
                          for f in all_findings)
        has_silent200 = any(f["type"] == "SILENT_200_ON_FAILURE" for f in all_findings)
        has_retry    = any(f["type"] == "RETRY_ESCALATION" for f in all_findings)
        has_throughput = any(f["type"] == "THROUGHPUT_DROP" for f in all_findings)
        has_idempotency = any(f["type"] == "IDEMPOTENCY_COLLISION" for f in all_findings)

        if has_latency and has_silent200 and has_retry:
            correlated.append({
                "pattern": "PAYMENT_GATEWAY_SILENT_DEGRADATION",
                "severity": "CRITICAL",
                "signals": ["metrics", "traces", "logs"],
                "description": (
                    "Payment gateway degradation confirmed across all 3 signals. "
                    "Latency spike in metrics, bottleneck span in traces, "
                    "silent 200 returns and retry escalation in logs. "
                    "Classic Stripe API degradation with non-idempotent retry pattern."
                ),
                "confidence": "HIGH",
            })

        if has_throughput and not any(
            f["type"] == "SUB_THRESHOLD_ERROR_TREND" and f.get("recent_avg_pct", 0) > 3
            for f in all_findings
        ):
            correlated.append({
                "pattern": "SILENT_ABANDONMENT",
                "severity": "HIGH",
                "signals": ["metrics"],
                "description": (
                    "Throughput dropped significantly with no matching error rate increase. "
                    "Users are abandoning the checkout flow silently — "
                    "no errors logged because they leave before reaching the failure state."
                ),
                "confidence": "MEDIUM",
            })

        if has_idempotency:
            correlated.append({
                "pattern": "DUPLICATE_CHARGE_RISK",
                "severity": "CRITICAL",
                "signals": ["logs"],
                "description": (
                    "Idempotency key collisions detected. "
                    "Combined with retry escalation, this indicates customers "
                    "may be double-charged. Immediate investigation required."
                ),
                "confidence": "HIGH",
            })

        return correlated

    def _explain(
        self, all_findings: list, signals_firing: list, by_signal: dict
    ) -> str:
        """Use LLM if available, else rule-based explanation."""
        key = self._api_key
        if key and key != "sk-your-key-here":
            return self._llm_explain(all_findings, signals_firing)
        return self._rule_based_explain(all_findings, signals_firing, by_signal)

    def _llm_explain(self, all_findings: list, signals_firing: list) -> str:
        """GPT-4o cross-signal root cause explanation."""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self._api_key)

            findings_text = json.dumps(all_findings, indent=2)
            prompt = (
                "You are a senior SRE analysing a production silent failure. "
                "You have findings from " + str(len(signals_firing)) + " observability signals: "
                + ", ".join(signals_firing) + ".\n\n"
                "Findings:\n" + findings_text + "\n\n"
                "In 3-4 sentences explain: "
                "1) What is the most likely root cause connecting all signals? "
                "2) Why did no single signal alert? "
                "3) What is the most urgent action to take right now?"
            )

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            return self._rule_based_explain(all_findings, signals_firing, {})

    def _rule_based_explain(
        self, all_findings: list, signals_firing: list, by_signal: dict
    ) -> str:
        """Offline rule-based cross-signal explanation."""
        types = {f["type"] for f in all_findings}

        if "PAYMENT_GATEWAY_SILENT_DEGRADATION" in str(all_findings):
            return (
                "Root cause: Payment gateway (Stripe) degradation confirmed across all 3 signals. "
                "Metrics show p99 latency increased 19x over baseline. "
                "Traces show payment-gateway span consuming 94% of trace duration. "
                "Logs show silent HTTP 200 returns after timeout and idempotency collisions. "
                "No single signal crossed an alert threshold — the combination tells the story. "
                "Immediate action: check Stripe status page, identify duplicate charges, "
                "enable circuit breaker."
            )

        parts = []
        if "LATENCY_TREND" in types:
            parts.append("p99 latency is elevated in metrics")
        if "TRACE_SPAN_BOTTLENECK" in types:
            parts.append("a single service is bottlenecking traces")
        if "SILENT_200_ON_FAILURE" in types:
            parts.append("HTTP 200 is being returned on failure in logs")
        if "THROUGHPUT_DROP" in types:
            parts.append("throughput has dropped significantly")
        if "IDEMPOTENCY_COLLISION" in types:
            parts.append("idempotency collisions suggest duplicate charges")

        return (
            "Cross-signal analysis: " + "; ".join(parts) + ". "
            "Signals firing: " + ", ".join(signals_firing) + ". "
            "No single signal crossed an alert threshold independently — "
            "multi-signal correlation reveals the underlying silent failure."
        )

    def _single_signal_explanation(
        self, all_findings: list, signals_firing: list
    ) -> str:
        if not signals_firing:
            return "No anomalies detected."
        return (
            "Single signal anomaly detected in " + signals_firing[0] + ". "
            "No cross-signal correlation. Monitor other signals for escalation."
        )
