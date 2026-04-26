"""
Reporter Agent — Part 2: CrewAI
=================================
Role    : Writes the final enriched report.
Persona : "I only report what survived the debate."
RAG use : SECONDARY — pulls runbooks for confirmed findings.
          Never writes about overruled findings.
          Flags UNCERTAIN findings prominently for human review.
"""

import json
import os
import sys
from datetime import datetime
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from rag.rag_context import retrieve


class ReporterAgent:

    def __init__(self, kb_path: Optional[str] = None):
        self.kb_path = kb_path
        self.name = "Reporter"
        self.role = "Report writer and escalation coordinator"
        self.goal = (
            "Write a clear, actionable report from findings that survived Analyzer review. "
            "Prominently flag UNCERTAIN findings for human review. "
            "Never include overruled false positives in the final report."
        )
        self.backstory = (
            "You are the QA lead who presents findings to the engineering team. "
            "You know that a noisy report full of false positives gets ignored. "
            "You only write about findings that have been validated. "
            "But you never bury an UNCERTAIN finding — those get a red flag."
        )

    def _severity_icon(self, severity: str) -> str:
        return {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(severity, "⚪")

    def _verdict_icon(self, verdict: str) -> str:
        return {
            "CONFIRMED": "✅",
            "UNCERTAIN": "⚠️",
            "NEEDS_REVIEW": "🔍",
        }.get(verdict, "✅")

    def generate_report(
        self,
        detector_output: dict,
        analyzer_output: dict,
        output_path: str = "reports/silent_failure_report.md",
    ) -> str:
        """Generate the final enriched Markdown report."""

        confirmed  = analyzer_output.get("confirmed_findings", [])
        overruled  = analyzer_output.get("overruled_findings", [])
        uncertain  = analyzer_output.get("uncertain_findings", [])
        entries    = detector_output.get("entries_analysed", 0)

        total_flagged   = detector_output.get("anomaly_count", len(
            confirmed + overruled + uncertain
        ))
        total_confirmed = len(confirmed) + len(uncertain)

        lines = [
            "# AI Silent Failure Detector — Part 2: CrewAI Report",
            "",
            f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            f"**Log entries analysed:** {entries}",
            f"**Detector flagged:** {total_flagged}",
            f"**Analyzer confirmed:** {len(confirmed)}",
            f"**Analyzer overruled (false positives):** {len(overruled)}",
            f"**Uncertain (human review required):** {len(uncertain)}",
            "",
            "---",
            "",
        ]

        # ─── Confirmed findings ───────────────────────────────────────────
        if confirmed:
            lines.append("## ✅ Confirmed Silent Failures\n")
            for i, v in enumerate(confirmed, 1):
                f = v["original_finding"]
                sev = f.get("severity", "MEDIUM")
                icon = self._severity_icon(sev)
                lines.append(f"### {icon} Finding {i}: {f['type'].replace('_', ' ').title()}")
                lines.append(f"\n**Severity:** {sev}")
                lines.append(f"**Verdict:** {v['verdict']}")
                lines.append(f"\n**Description:** {f['description']}\n")

                if f.get("affected_paths"):
                    lines.append("**Affected paths:**")
                    for p in f["affected_paths"]:
                        lines.append(f"- `{p}`")
                if f.get("path"):
                    lines.append(f"**Path:** `{f['path']}`")
                if f.get("error_rate_pct"):
                    lines.append(f"**Error rate:** {f['error_rate_pct']}%")

                lines.append(f"\n**Analyzer reasoning:** {v['reasoning']}\n")

                # RAG evidence
                rag = v.get("rag_evidence", {})
                tp_matches = rag.get("true_positive_matches", [])
                if tp_matches:
                    lines.append(f"**Matched past incidents:** {', '.join(tp_matches)}")

                # Runbook
                runbook = v.get("runbook", "")
                if not runbook:
                    # Pull fresh from RAG
                    query = f"{f.get('type', '')} {f.get('description', '')}"
                    rag_data = json.loads(retrieve(query, kb_path=self.kb_path))
                    ctx = rag_data.get("context", [])
                    if ctx:
                        runbook = ctx[0].get("runbook", "")

                if runbook:
                    lines.append("\n**Runbook:**")
                    for step in runbook.split(". "):
                        if step.strip():
                            lines.append(f"  - {step.strip()}")

                lines.append("\n---\n")

        # ─── Uncertain findings ───────────────────────────────────────────
        if uncertain:
            lines.append("## ⚠️ Uncertain Findings — Human Review Required\n")
            lines.append(
                "> These findings have conflicting evidence. "
                "The Analyzer could not make a confident determination. "
                "**Do not ignore these.** Assign to a human reviewer.\n"
            )
            for i, v in enumerate(uncertain, 1):
                f = v["original_finding"]
                lines.append(f"### Finding U{i}: {f['type'].replace('_', ' ').title()}")
                lines.append(f"\n**Description:** {f['description']}")
                lines.append(f"\n**Analyzer note:** {v['reasoning']}\n")
                lines.append("---\n")

        # ─── Overruled findings (audit trail) ────────────────────────────
        if overruled:
            lines.append("## 🚫 Overruled Findings (False Positives Removed)\n")
            lines.append(
                "> These were flagged by the Detector but overruled by the Analyzer. "
                "Included for audit trail only.\n"
            )
            for i, v in enumerate(overruled, 1):
                f = v["original_finding"]
                lines.append(f"### Finding O{i}: {f['type'].replace('_', ' ').title()}")
                lines.append(f"\n**Why overruled:** {v['reasoning']}\n")
                lines.append("---\n")

        # ─── Part 1 comparison ───────────────────────────────────────────
        lines.append("## 📊 Part 1 vs Part 2 Comparison\n")
        lines.append("| Metric | Part 1 (LangChain) | Part 2 (CrewAI) |")
        lines.append("|---|---|---|")
        lines.append(f"| Findings flagged | {total_flagged} | {total_flagged} |")
        lines.append(f"| False positives removed | 0 | {len(overruled)} |")
        lines.append(f"| Uncertain escalations | 0 | {len(uncertain)} |")
        lines.append(f"| Agent debate rounds | 0 | 1 collaborative pass |")
        lines.append(f"| RAG used by | Reporter only | Analyzer (challenge) + Reporter (runbook) |")

        report = "\n".join(lines)

        os.makedirs(
            os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
            exist_ok=True
        )
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)

        return (
            f"Report written to {output_path}. "
            f"{len(confirmed)} confirmed, {len(overruled)} overruled, {len(uncertain)} uncertain."
        )

    def run(
        self,
        detector_output: dict,
        analyzer_output: dict,
        output_path: str = "reports/silent_failure_report.md",
    ) -> dict:
        print(f"\n[{self.name}] Generating enriched report...")
        result = self.generate_report(detector_output, analyzer_output, output_path)
        print(f"[{self.name}] {result}")
        return {
            "agent": self.name,
            "report_path": output_path,
            "summary": result,
        }
