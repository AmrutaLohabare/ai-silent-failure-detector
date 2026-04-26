# 🔇 AI Silent Failure Detector — Part 2: CrewAI + RAG

> **LinkedIn Series:** [AI Silent Failure Detector — 7 Tools, 1 Problem](#)
>
> Part 2 of a 7-part series where I solve the same QA problem with different agentic AI tools.
> [← Part 1: LangChain + RAG](../part1_langchain/) | Part 3: Playwright + AI Vision → *(coming soon)*

---

## What's Different from Part 1

| | Part 1 — LangChain | Part 2 — CrewAI |
|---|---|---|
| Agents | 1 sequential pipeline | 3 collaborating agents |
| RAG used by | Reporter (runbooks) | Analyzer (to challenge findings) |
| False positive handling | None | Analyzer overrules with evidence |
| Uncertain findings | Not possible | Escalated to human review |
| Debate rounds | 0 | 1 collaborative pass |
| Verdict types | detected / not detected | CONFIRMED / OVERRULED / UNCERTAIN |

**The core upgrade:** Part 1 detected *what* was failing. Part 2 adds a sceptical Analyzer that asks *"are you sure?"* — backed by RAG evidence from past incidents. False positive rate drops. Alert fatigue drops. Human reviewers only see findings that survived debate.

---

## The 3-Agent Collaborative Design

```
Production Logs
      │
      ▼
┌─────────────────────────────────────────┐
│  Agent 1 — Detector                     │
│  Aggressive scanner. Flags everything.  │
│  "Better to over-flag than miss one."   │
└──────────────────┬──────────────────────┘
                   │  posts findings to shared channel
                   ▼
         ┌─────────────────┐
         │  Shared Message │  ◄── all 3 agents read & write
         │    Channel      │
         └────────┬────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Agent 2 — Analyzer  ✦ RAG-powered      │
│  Challenges each finding with evidence. │
│  Can CONFIRM, OVERRULE, or flag         │
│  UNCERTAIN when evidence conflicts.     │
│  Requires 2+ incidents to overrule      │
│  any payment-path finding.              │
└──────────────────┬──────────────────────┘
                   │  consensus findings only
                   ▼
         ┌─────────────────┐
         │ Consensus Gate  │  only agreed findings pass
         └────────┬────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  Agent 3 — Reporter                     │
│  Writes enriched report. Flags          │
│  UNCERTAIN findings prominently.        │
│  Includes audit trail of overruled FPs. │
└─────────────────────────────────────────┘
```

---

## What RAG Does Differently in Part 2

In Part 1, RAG was used by the Reporter to enrich the report with runbooks.

In Part 2, **RAG is the Analyzer's weapon**. Every time the Analyzer challenges a finding, it retrieves similar past incidents to back its argument:

```
Detector  → "EMPTY_SUCCESS_RESPONSE on /api/auth/refresh — flag it"

Analyzer  → [queries knowledge base]
           → Found INC-007: this pattern is a FALSE_POSITIVE during cache warm-up
           → Found INC-001: this pattern is a TRUE_POSITIVE for Redis OOM
           → Conflicting evidence → verdict: UNCERTAIN → escalate to human

Reporter  → Writes finding with ⚠️ UNCERTAIN flag and both incident references
```

---

## The 4 New Incident Types (Part 2 Knowledge Base)

Part 2 adds 4 multi-agent-specific incidents to the knowledge base (10 total):

| ID | Type | What it teaches the Analyzer |
|---|---|---|
| INC-007 | `FALSE_POSITIVE_CACHE_WARMUP` | Empty 200s on /recommendations are expected during warm-up |
| INC-008 | `FALSE_POSITIVE_MAINTENANCE` | Sub-threshold errors during DynamoDB GSI rebuild are expected |
| INC-009 | `CONFIRMED_SILENT_FAILURE` | Analyzer challenged then confirmed — shows the debate working |
| INC-010 | `AGENT_CONSENSUS_OVERRIDE` | Analyzer overruled wrongly — teaches the "2 incident rule" for payment paths |

---

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/AmrutaLohabare/ai-silent-failure-detector.git
cd ai-silent-failure-detector/part2_crewai
pip install -r requirements.txt
```

### 2. Run (no API key needed)

```bash
python main.py
```

### 3. Run tests (fully offline)

```bash
pytest tests/ -v
```

---

## Project Structure

```
part2_crewai/
├── agents/
│   ├── detector_agent.py    # Flags all anomalies aggressively
│   ├── analyzer_agent.py    # Challenges findings with RAG evidence
│   └── reporter_agent.py    # Writes enriched report from survivors
├── crew/
│   └── silent_failure_crew.py  # Orchestrates the 3-agent debate loop
├── rag/
│   └── rag_context.py       # Shared TF-IDF retriever (no API key)
├── knowledge_base/
│   └── incidents.json       # 10 incidents (6 from Part 1 + 4 new)
├── logs/
│   └── sample_prod.log      # Sample log with silent failures
├── tests/
│   └── test_agents.py       # 26 tests — all 3 agents + crew integration
├── main.py
└── requirements.txt
```

---

## Verdict Types

| Verdict | Meaning | Action |
|---|---|---|
| `CONFIRMED` | Analyzer agrees with Detector | Include in report |
| `OVERRULED` | Analyzer found false positive evidence | Excluded — audit trail only |
| `UNCERTAIN` | Conflicting evidence found | Escalate to human reviewer |
| `NEEDS_REVIEW` | Payment path with weak override evidence | Escalate to human reviewer |

---

## Sample Terminal Output

```
════════════════════════════════════════════════════
  AI Silent Failure Detector — Part 2: CrewAI
  3-Agent Collaborative Debate
════════════════════════════════════════════════════

[Crew] Round 1 — Detector scanning logs...
[Detector] 62 entries parsed. Detecting anomalies...
[Detector] 1 potential silent failure(s) flagged.

[Crew] Round 2 — Analyzer reviewing findings...
[Analyzer] [1/1] Analysing: EMPTY_SUCCESS_RESPONSE
[RAG] Loaded 10 incidents into shared retriever.
[Analyzer] Verdict: UNCERTAIN — Conflicting evidence.
           False positive pattern: INC-007
           True positive pattern:  INC-001

[Analyzer] Review complete:
  Confirmed : 0
  Overruled : 0  (false positives removed)
  Uncertain : 1  (escalate to human)

[Crew] Round 3 — Reporter writing enriched report...
[Reporter] Report written to reports/silent_failure_report.md.

✅  Done in 0.0s
```

---

## Growing the Knowledge Base

The Analyzer gets smarter with every incident you add to `knowledge_base/incidents.json`.
The critical field is `agent_verdict` — it tells the Analyzer how to use each record:

```json
{
  "id": "INC-011",
  "type": "EMPTY_SUCCESS_RESPONSE",
  "path_pattern": "/api/your-endpoint",
  "title": "Short description",
  "root_cause": "What actually caused it.",
  "detection_lag_hours": 2,
  "business_impact": "What broke for users.",
  "resolution": "How it was fixed.",
  "runbook": "1. First step. 2. Second step.",
  "agent_verdict": "TRUE_POSITIVE",
  "analyzer_reasoning": "Optional: reasoning the Analyzer can reference.",
  "tags": ["relevant", "tags"]
}
```

`agent_verdict` options: `TRUE_POSITIVE`, `FALSE_POSITIVE_CACHE_WARMUP`,
`FALSE_POSITIVE_MAINTENANCE`, `TRUE_POSITIVE_AFTER_DEBATE`, `FALSE_NEGATIVE_OVERRIDE`

---

## Series Roadmap

| Part | Tool | Status |
|---|---|---|
| Part 1 | LangChain + RAG | ✅ [Done](../part1_langchain/) |
| **Part 2** | CrewAI 3-agent debate | ✅ This folder |
| Part 3 | Playwright + AI Vision | 🔜 Coming soon |
| Part 4 | Semantic Kernel (Azure) | 🔜 Coming soon |
| Part 5 | AutoGen self-healing | 🔜 Coming soon |
| Part 6 | Datadog + LLM reasoning | 🔜 Coming soon |
| Part 7 | Comparison & verdict | 🔜 Coming soon |

---

## Connect

- LinkedIn: [Amruta Lohabare](https://linkedin.com/in/yourprofile) — follow with `#AISilentFailureDetector`
- Found a bug or want to contribute a runbook? Open a PR.

⭐ Star this repo if it helped you think differently about QA.
