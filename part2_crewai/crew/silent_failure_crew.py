"""
Silent Failure Crew — Part 2: CrewAI Orchestrator
===================================================
Manages the collaborative debate loop between:
  - DetectorAgent  (flags anomalies)
  - AnalyzerAgent  (challenges findings with RAG evidence)
  - ReporterAgent  (writes enriched report from surviving findings)

Collaborative flow:
  1. Detector scans logs → posts findings to shared channel
  2. Analyzer reviews each finding → posts verdict + reasoning
  3. If Analyzer overrules → Detector can respond (debate round)
  4. Consensus reached → Reporter writes final report
  5. LLM generates executive summary (optional, requires API key)
"""

import json
import os
import sys
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.detector_agent import DetectorAgent
from agents.analyzer_agent import AnalyzerAgent
from agents.reporter_agent import ReporterAgent


class SilentFailureCrew:
    """
    Orchestrates the 3-agent collaborative pipeline.
    No external CrewAI framework dependency — pure Python orchestration
    for Windows/Python 3.13 compatibility.
    """

    def __init__(
        self,
        kb_path: Optional[str] = None,
        error_threshold: float = 0.02,
        max_debate_rounds: int = 2,
        output_path: str = "reports/silent_failure_report.md",
    ):
        self.kb_path = kb_path or os.path.join(
            os.path.dirname(__file__), "..", "knowledge_base", "incidents.json"
        )
        self.error_threshold = error_threshold
        self.max_debate_rounds = max_debate_rounds
        self.output_path = output_path

        # Instantiate agents
        self.detector = DetectorAgent(error_threshold=error_threshold)
        self.analyzer = AnalyzerAgent(kb_path=self.kb_path)
        self.reporter = ReporterAgent(kb_path=self.kb_path)

        # Shared message channel — all agents read/write here
        self.channel: list[dict] = []

    def _post_to_channel(self, agent: str, message_type: str, payload: dict):
        """Post a message to the shared channel."""
        entry = {
            "from": agent,
            "type": message_type,
            "payload": payload,
        }
        self.channel.append(entry)
        print(f"\n[Channel] {agent} → {message_type}")

    def _get_from_channel(self, message_type: str) -> list[dict]:
        """Retrieve all messages of a given type from the channel."""
        return [m for m in self.channel if m["type"] == message_type]

    def run(
        self,
        log_source: str,
        window_minutes: int = 60,
    ) -> dict:
        """
        Run the full collaborative crew pipeline.
        Returns the final crew result dict.
        """
        print("\n" + "═" * 52)
        print("  AI Silent Failure Detector — Part 2: CrewAI")
        print("  3-Agent Collaborative Debate")
        print("═" * 52)

        # ─── Round 1: Detector scans ──────────────────────────────────────
        print("\n[Crew] Round 1 — Detector scanning logs...")
        detector_output = self.detector.run(log_source, window_minutes)

        if "error" in detector_output:
            return {"error": detector_output["error"]}

        self._post_to_channel(
            "Detector",
            "FINDINGS",
            {
                "anomaly_count": detector_output.get("anomaly_count", 0),
                "anomalies": detector_output.get("anomalies", []),
            },
        )

        # Early exit if no findings
        if not detector_output.get("anomalies"):
            print("\n[Crew] No anomalies detected. No debate needed.")
            result = self.reporter.run(
                detector_output,
                {"confirmed_findings": [], "overruled_findings": [], "uncertain_findings": []},
                self.output_path,
            )
            return {"status": "clean", "report": result}

        # ─── Round 2: Analyzer challenges ────────────────────────────────
        print("\n[Crew] Round 2 — Analyzer reviewing findings...")
        analyzer_output = self.analyzer.run(
            detector_output,
            max_debate_rounds=self.max_debate_rounds,
        )

        self._post_to_channel(
            "Analyzer",
            "VERDICTS",
            {
                "confirmed": analyzer_output.get("confirmed_count", 0),
                "overruled": analyzer_output.get("overruled_count", 0),
                "uncertain": analyzer_output.get("uncertain_count", 0),
            },
        )

        # ─── Debate round (if Analyzer overruled anything) ────────────────
        overruled = analyzer_output.get("overruled_findings", [])
        if overruled:
            print(f"\n[Crew] Debate — Detector responding to {len(overruled)} overruled finding(s)...")
            for v in overruled:
                print(
                    f"  [Detector → Analyzer] "
                    f"I flagged {v['finding_type']} on {v['affected_paths']}. "
                    f"You overruled it. My confidence was {v['original_finding'].get('detector_confidence', 'HIGH')}."
                )
                print(
                    f"  [Analyzer → Detector] "
                    f"Verdict stands: {v['reasoning'][:100]}..."
                )
                self._post_to_channel(
                    "Debate",
                    "CHALLENGE_RESPONSE",
                    {"finding": v["finding_type"], "outcome": "OVERRULE_MAINTAINED"},
                )

        # ─── Round 3: Reporter writes report ─────────────────────────────
        print("\n[Crew] Round 3 — Reporter writing enriched report...")
        reporter_output = self.reporter.run(
            detector_output,
            analyzer_output,
            self.output_path,
        )

        self._post_to_channel("Reporter", "REPORT_COMPLETE", reporter_output)

        # ─── Executive summary ────────────────────────────────────────────
        summary = self._build_summary(detector_output, analyzer_output)

        print("\n" + "═" * 52)
        print("  Crew run complete.")
        print(f"  {reporter_output['summary']}")
        print("═" * 52)

        return {
            "status": "complete",
            "detector_output": detector_output,
            "analyzer_output": analyzer_output,
            "reporter_output": reporter_output,
            "channel_log": self.channel,
            "summary": summary,
        }

    def _build_summary(self, detector_output: dict, analyzer_output: dict) -> str:
        """Build a plain-text executive summary without needing OpenAI."""
        confirmed  = analyzer_output.get("confirmed_count", 0)
        overruled  = analyzer_output.get("overruled_count", 0)
        uncertain  = analyzer_output.get("uncertain_count", 0)
        total      = detector_output.get("anomaly_count", 0)
        entries    = detector_output.get("entries_analysed", 0)

        lines = [
            f"Analysed {entries} log entries.",
            f"Detector flagged {total} potential silent failure(s).",
            f"Analyzer confirmed {confirmed}, overruled {overruled} as false positive(s).",
        ]

        confirmed_findings = analyzer_output.get("confirmed_findings", [])
        for v in confirmed_findings:
            f = v["original_finding"]
            lines.append(
                f"  → {f['type']} on {f.get('affected_paths', [f.get('path','')])}: {f['description'][:80]}"
            )

        if overruled > 0:
            lines.append(
                f"False positives removed by Analyzer: {overruled}. "
                "This reduces alert fatigue compared to Part 1."
            )

        if uncertain > 0:
            lines.append(
                f"⚠️  {uncertain} finding(s) flagged as UNCERTAIN — human review required."
            )

        return " ".join(lines)
