# 🔇 AI Silent Failure Detector — 7 Tools, 1 Problem

> **LinkedIn Series by [Amruta Lohabare](https://www.linkedin.com/in/amruta-lohabare/)**
> Follow the series: `#AISilentFailureDetector`

---

## The Problem

Your CI pipeline says ✅ green. Production is silently failing.

Silent failures are the hardest bugs to catch — and the most expensive:

- **HTTP 200s with empty response bodies** — success codes, no data delivered
- **Error rates hovering just below alert thresholds** — 1.8% errors when your pager fires at 2%
- **Latency spikes on successful requests** — timeouts swallowed silently, retries masking failures

Traditional monitors only fire when you cross a threshold you already defined.
This series builds an agent that finds the failures **you didn't know to look for.**

---

## The Series

Same problem. 7 different agentic AI tools. One part per LinkedIn post.

| Part | Tool | Key concept | Status |
|---|---|---|---|
| **Part 1** | LangChain + RAG | 4-tool pipeline · RAG gives agent institutional memory | ✅ [Done](./part1_langchain/) |
| **Part 2** | CrewAI | 3-agent collaborative debate · Analyzer challenges Detector with RAG evidence | ✅ [Done](./part2_crewai/) |
| Part 3 | Playwright + AI Vision | Screenshot embeddings · visual silent failure detection | 🔜 Coming soon |
| Part 4 | Semantic Kernel | Azure AI Search · enterprise RAG stack | 🔜 Coming soon |
| Part 5 | AutoGen | Self-healing tests · agent writes and commits the fix | 🔜 Coming soon |
| Part 6 | Datadog + LLM | Operational RAG · time-series context retrieval | 🔜 Coming soon |
| Part 7 | Comparison | Honest verdict across all 6 tools | 🔜 Coming soon |

---

## What's Built So Far

### Part 1 — LangChain + RAG
**4-tool sequential pipeline:**
```
Logs → LogIngestionTool → AnomalyDetectorTool → RAGContextTool → ReporterTool
```
- Detects 3 silent failure patterns: empty 200s, sub-threshold errors, latency spikes
- RAG retrieves similar past incidents and runbooks from knowledge_base/incidents.json
- GPT-4o generates executive summary
- **31 tests · Windows + Python 3.13 compatible**

→ [Part 1 README](./part1_langchain/README.md)

---

### Part 2 — CrewAI 3-Agent Debate
**3 agents collaborating via shared message channel:**
```
Detector → [shared channel] → Analyzer (RAG-powered) → Consensus Gate → Reporter
```
- Detector flags everything aggressively
- Analyzer challenges findings with RAG evidence — can CONFIRM, OVERRULE, or flag UNCERTAIN
- Reporter only writes about findings that survived the debate
- **26 tests · no API key needed · fully offline**

→ [Part 2 README](./part2_crewai/README.md)

---

## Knowledge Base

The RAG layer gets smarter with every incident added to the knowledge base.

| Part | Incidents | New types added |
|---|---|---|
| Part 1 | INC-001 to INC-006 | Core silent failure patterns |
| Part 2 | INC-007 to INC-010 | Multi-agent debate patterns (false positives, overrides) |

After every real postmortem, add an entry — the detector improves automatically.

---

## Quickstart

```bash
git clone https://github.com/AmrutaLohabare/ai-silent-failure-detector.git

# Run Part 1 (needs OpenAI API key)
cd part1_langchain
pip install -r requirements.txt
python main.py

# Run Part 2 (no API key needed)
cd ../part2_crewai
pip install -r requirements.txt
python main.py
```

---

## Connect

- LinkedIn: [Amruta Lohabare](https://www.linkedin.com/in/amruta-lohabare/)
- Follow the series: `#AISilentFailureDetector`
- Found a bug or want to contribute a runbook? Open a PR.

⭐ Star this repo if it helped you think differently about QA.
