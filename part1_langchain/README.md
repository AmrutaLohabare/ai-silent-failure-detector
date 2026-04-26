# 🔇 AI Silent Failure Detector — Part 1: LangChain + RAG

> **LinkedIn Series:** [AI Silent Failure Detector — 7 Tools, 1 Problem](#)
>
> Part 1 of a 7-part series where I solve the same QA problem with different agentic AI tools.
> Each part lives in its own folder. This is the LangChain + RAG edition.

---

## The Problem

Your CI pipeline says ✅ green. Production is quietly failing.

Silent failures are the hardest bugs to catch — and the most expensive:

| Pattern | Why it hides | Real-world example |
|---|---|---|
| HTTP 200 with empty body | Server reports success; delivers nothing | Auth token refresh returning 200 but not writing to Redis |
| Sub-threshold error rate | Stays just below your pager threshold | 1.8% checkout failures when alert fires at 2% |
| Latency spike on success | Retries succeed eventually; spike goes unnoticed | Payment gateway 503 → silent retry → double charge |

Traditional monitors only fire when you cross a threshold **you already defined**.
This agent finds failures **you didn't know to look for** — and tells you what probably caused them.

---

## What RAG Adds

Without RAG, the agent tells you **what** is failing.
With RAG, it also tells you **why it's probably failing** and **what to do about it** — by retrieving
from a knowledge base of past incidents and runbooks.

```
Without RAG:   "14 HTTP 200s with zero-byte body on /api/auth/refresh [HIGH]"

With RAG:      "14 HTTP 200s with zero-byte body on /api/auth/refresh [HIGH]
                ↳ Similar to INC-001: Redis session store OOM
                  Root cause: Redis maxmemory exhausted — writes silently failing
                  Business impact: 8,000 silent logouts, 300% support spike
                  Runbook:
                    1. redis-cli INFO memory
                    2. Check eviction events: redis-cli INFO stats | grep evicted_keys
                    3. Increase maxmemory and set LRU eviction policy
                    4. Restart auth service"
```

---

## Architecture

```
Production Logs
      │
      ▼
┌─────────────────────┐
│  Tool 1             │
│  LogIngestionTool   │  Parse raw lines → structured JSON
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Tool 2             │
│  AnomalyDetector    │  Detect 3 silent failure patterns
│  Tool               │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐         ┌──────────────────────┐
│  Tool 3  ✦ RAG      │◄───────►│  FAISS Vector Store  │
│  RAGContextTool     │         │  (incidents.json)    │
└──────────┬──────────┘         └──────────────────────┘
           │
           ▼
┌─────────────────────┐
│  Tool 4             │
│  SilentFailure      │  Anomaly + RAG context → enriched report
│  ReporterTool       │
└──────────┬──────────┘
           │
           ▼
  reports/silent_failure_report.md
  (What failed · Why · What to do)
```

The **LangChain ZERO_SHOT_REACT agent** orchestrates all four tools autonomously.
The **RAG layer** uses FAISS + sentence-transformers for semantic search, with an automatic
TF-IDF fallback so tests and CI run fully offline without any API keys.

---

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/yourusername/ai-silent-failure-detector.git
cd ai-silent-failure-detector
pip install -r requirements.txt
```

### 2. Set your OpenAI API key

```bash
export OPENAI_API_KEY="sk-..."
```

Or create a `.env` file:
```
OPENAI_API_KEY=sk-...
```

### 3. Run on the sample log

```bash
python agent/silent_failure_detector.py logs/sample_prod.log
```

### 4. Run tests (no API key needed)

```bash
pytest tests/ -v
```

All 31 tests run fully offline — no OpenAI calls, no model downloads needed.

---

## Project Structure

```
ai-silent-failure-detector/
├── agent/
│   ├── silent_failure_detector.py   # Main agent + 3 detection tools
│   └── rag_context.py               # RAGContextTool (FAISS + TF-IDF fallback)
├── knowledge_base/
│   └── incidents.json               # Past incidents + runbooks (grow this over time)
├── logs/
│   └── sample_prod.log              # Sample log with silent failures baked in
├── reports/                         # Generated reports land here
├── tests/
│   ├── test_detector.py             # 15 tests for detection tools
│   └── test_rag_context.py          # 16 tests for RAG pipeline
└── requirements.txt
```

---

## Detected Patterns

| Pattern | Severity | Description |
|---|---|---|
| `EMPTY_SUCCESS_RESPONSE` | 🔴 HIGH | HTTP 200 with zero-byte response body |
| `SUB_THRESHOLD_ERROR_RATE` | 🟡 MEDIUM | Error rate between 1% and your alert threshold |
| `LATENCY_SPIKE_ON_SUCCESS` | 🟡 MEDIUM | Successful requests taking 3× average time |

---

## Extending the Knowledge Base

The RAG layer gets smarter every time you add an incident. After any postmortem, add an entry to
`knowledge_base/incidents.json` in this format:

```json
{
  "id": "INC-007",
  "type": "EMPTY_SUCCESS_RESPONSE",
  "path_pattern": "/api/your-endpoint",
  "title": "Short description of what happened",
  "root_cause": "The actual technical root cause.",
  "detection_lag_hours": 3,
  "business_impact": "What broke for users and the business.",
  "resolution": "What was done to fix it.",
  "runbook": "1. First step. 2. Second step. 3. Third step.",
  "tags": ["relevant", "tags"]
}
```

The vector store rebuilds automatically on the next run.

---

## Sample Report Output

```markdown
# AI Silent Failure Detector — Report

**Generated:** 2024-01-15 10:05 UTC
**Entries analysed:** 62
**Silent failures detected:** 3

---

## 🔴 Finding 1: Empty Success Response

**Severity:** HIGH
**Description:** 14 requests returned HTTP 200 with zero-byte body on /api/auth/refresh

**Affected paths:**
- `/api/auth/refresh`

### 🔍 Similar past incidents

**INC-001 — Auth token refresh returning empty body**

**Root cause:** Redis session store ran out of memory. Writes silently failed.
**Business impact:** 8,000 users silently logged out. Support tickets up 300%.
**Detection lag:** 4 hours

**Runbook:**
  - Check Redis memory: redis-cli INFO memory
  - Check eviction events: redis-cli INFO stats | grep evicted_keys
  - Increase maxmemory, set LRU eviction policy
  - Restart auth service

---
```

---

## Series Roadmap

| Part | Tool | Status |
|---|---|---|
| **Part 1** | LangChain + RAG | ✅ This repo |
| Part 2 | CrewAI multi-agent | 🔜 Coming soon |
| Part 3 | Playwright + AI Vision | 🔜 Coming soon |
| Part 4 | Semantic Kernel (Azure) | 🔜 Coming soon |
| Part 5 | AutoGen self-healing | 🔜 Coming soon |
| Part 6 | Datadog + LLM reasoning | 🔜 Coming soon |
| Part 7 | Comparison & verdict | 🔜 Coming soon |

---

## Connect

- LinkedIn: [https://www.linkedin.com/in/amruta-lohabare-82017046/](#) — follow the series with `#AISilentFailureDetector`
- Found a bug or want to contribute a runbook? Open a PR.

⭐ Star this repo if it helped you think differently about QA.
