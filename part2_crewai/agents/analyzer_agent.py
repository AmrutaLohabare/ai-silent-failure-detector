"""
Analyzer Agent — Part 2: CrewAI
=================================
Role    : Sceptical challenger. Reviews every Detector finding using RAG.
Persona : "Show me the evidence before I escalate anything."
RAG use : PRIMARY — retrieves past incidents to support or challenge each finding.
          Can overrule the Detector if evidence supports a false positive.
          Requires 2+ corroborating incidents to override a payment-path finding.
"""

import json
import sys
import os
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from rag.rag_context import retrieve


# ─── Verdict constants ─────────────────────────────────────────────────────
CONFIRMED       = "CONFIRMED"          # Analyzer agrees with Detector
OVERRULED       = "OVERRULED"          # Analyzer overrules — false positive
UNCERTAIN       = "UNCERTAIN"          # Conflicting evidence — escalate to human
NEEDS_REVIEW    = "NEEDS_REVIEW"       # Only 1 corroborating incident — not enough to overrule payment path

# Payment-critical paths that require stronger evidence to overrule
PAYMENT_PATHS = ["/api/checkout", "/api/payments", "/api/orders", "/api/billing"]


class AnalyzerAgent:
    """
    Reviews each Detector finding by:
    1. Querying the RAG knowledge base for similar past incidents
    2. Checking if the finding matches a known FALSE_POSITIVE pattern
    3. Checking if the finding matches a known TRUE_POSITIVE pattern
    4. Issuing a verdict: CONFIRMED, OVERRULED, UNCERTAIN, or NEEDS_REVIEW
    5. Posting reasoning back to the shared channel
    """

    def __init__(self, kb_path: Optional[str] = None):
        self.kb_path = kb_path
        self.name = "Analyzer"
        self.role = "Finding validator and false positive reducer"
        self.goal = (
            "Review each Detector finding against the historical knowledge base. "
            "Confirm genuine silent failures. Overrule false positives with evidence. "
            "Never overrule a payment-path finding with fewer than 2 corroborating incidents."
        )
        self.backstory = (
            "You are a senior QA engineer who has seen too many false pages at 2am. "
            "You once got paged for a 'silent failure' that turned out to be expected "
            "cache warm-up behaviour. Now you check the evidence before every escalation. "
            "But you also remember INC-010 — when you overruled a real failure and "
            "89 customers got double-charged. You are sceptical, not dismissive."
        )

    def analyse_finding(self, finding: dict) -> dict:
        """
        Analyse a single Detector finding.
        Returns a verdict dict with reasoning and RAG evidence.
        """
        finding_type = finding.get("type", "")
        affected_paths = finding.get("affected_paths", [finding.get("path", "")])
        if isinstance(affected_paths, str):
            affected_paths = [affected_paths]
        description = finding.get("description", "")

        # Build rich query for RAG
        query = (
            f"{finding_type} on {' '.join(affected_paths)} "
            f"{description} "
            f"false positive maintenance warm-up expected behaviour"
        )

        print(f"  [{self.name}] Querying knowledge base for: {finding_type} on {affected_paths}")
        rag_result = json.loads(retrieve(query, kb_path=self.kb_path, k=3))
        context = rag_result.get("context", [])

        # Separate false positive vs true positive evidence
        fp_evidence = [c for c in context if "FALSE_POSITIVE" in c.get("agent_verdict", "")]
        tp_evidence = [c for c in context if c.get("agent_verdict", "") in (
            "TRUE_POSITIVE", "TRUE_POSITIVE_AFTER_DEBATE"
        )]

        # Is this a payment-critical path?
        is_payment_path = any(
            any(pp in path for pp in PAYMENT_PATHS)
            for path in affected_paths
        )

        # ─── Verdict logic ────────────────────────────────────────────────

        verdict = CONFIRMED
        reasoning = ""
        runbook = ""

        if fp_evidence and not tp_evidence:
            # Strong false positive signal — check if payment path needs more evidence
            if is_payment_path and len(fp_evidence) < 2:
                verdict = NEEDS_REVIEW
                reasoning = (
                    f"Found 1 false positive pattern (INC-{fp_evidence[0]['incident_id']}) "
                    f"but path '{affected_paths}' is payment-critical. "
                    f"Require 2+ corroborating incidents to overrule. Escalating to human review."
                )
            else:
                verdict = OVERRULED
                reasoning = (
                    f"Finding matches known false positive pattern: "
                    f"{fp_evidence[0]['incident_id']} — {fp_evidence[0]['title']}. "
                    f"Analyzer reasoning: {fp_evidence[0].get('analyzer_reasoning', 'Pattern match.')} "
                    f"Overruling Detector finding."
                )
                runbook = fp_evidence[0].get("runbook", "")

        elif fp_evidence and tp_evidence:
            # Conflicting evidence — uncertain
            verdict = UNCERTAIN
            reasoning = (
                f"Conflicting evidence. "
                f"False positive pattern found: {fp_evidence[0]['incident_id']}. "
                f"But true positive pattern also matches: {tp_evidence[0]['incident_id']}. "
                f"Cannot determine verdict with confidence. Escalating to human review."
            )
            runbook = tp_evidence[0].get("runbook", "")

        elif tp_evidence:
            # Clear true positive match
            verdict = CONFIRMED
            reasoning = (
                f"Finding matches confirmed true positive: "
                f"{tp_evidence[0]['incident_id']} — {tp_evidence[0]['title']}. "
                f"Root cause likely: {tp_evidence[0]['root_cause']}"
            )
            runbook = tp_evidence[0].get("runbook", "")

        else:
            # No matching incidents — confirm with uncertainty note
            verdict = CONFIRMED
            reasoning = (
                "No similar past incidents found in knowledge base. "
                "Cannot confirm or deny — treating as genuine finding. "
                "Recommend adding this incident to the knowledge base after investigation."
            )

        return {
            "finding_type": finding_type,
            "affected_paths": affected_paths,
            "original_finding": finding,
            "verdict": verdict,
            "reasoning": reasoning,
            "runbook": runbook,
            "rag_evidence": {
                "false_positive_matches": [c["incident_id"] for c in fp_evidence],
                "true_positive_matches": [c["incident_id"] for c in tp_evidence],
                "retrieved_incidents": context,
            },
            "is_payment_path": is_payment_path,
        }

    def run(self, detector_output: dict, max_debate_rounds: int = 2) -> dict:
        """
        Run the Analyzer over all Detector findings.
        Supports debate rounds — Detector can respond to challenges.
        Returns all verdicts and a summary for the Reporter.
        """
        anomalies = detector_output.get("anomalies", [])

        if not anomalies:
            return {
                "agent": self.name,
                "verdicts": [],
                "confirmed_count": 0,
                "overruled_count": 0,
                "uncertain_count": 0,
                "summary": "No anomalies to analyse.",
            }

        print(f"\n[{self.name}] Reviewing {len(anomalies)} Detector finding(s)...")

        verdicts = []
        for i, finding in enumerate(anomalies, 1):
            print(f"  [{self.name}] [{i}/{len(anomalies)}] Analysing: {finding.get('type')}")
            verdict = self.analyse_finding(finding)
            verdicts.append(verdict)
            print(f"  [{self.name}] Verdict: {verdict['verdict']} — {verdict['reasoning'][:80]}...")

        confirmed = [v for v in verdicts if v["verdict"] == CONFIRMED]
        overruled = [v for v in verdicts if v["verdict"] == OVERRULED]
        uncertain = [v for v in verdicts if v["verdict"] in (UNCERTAIN, NEEDS_REVIEW)]

        print(f"\n[{self.name}] Review complete:")
        print(f"  Confirmed : {len(confirmed)}")
        print(f"  Overruled : {len(overruled)} (false positives removed)")
        print(f"  Uncertain : {len(uncertain)} (escalate to human)")

        return {
            "agent": self.name,
            "verdicts": verdicts,
            "confirmed_count": len(confirmed),
            "overruled_count": len(overruled),
            "uncertain_count": len(uncertain),
            "confirmed_findings": confirmed,
            "overruled_findings": overruled,
            "uncertain_findings": uncertain,
        }
