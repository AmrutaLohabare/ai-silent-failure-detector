# AI Silent Failure Detector - 7 Tools, 1 Problem

> LinkedIn Series by Amruta Lohabare
> https://www.linkedin.com/in/amruta-lohabare-82017046
> GitHub: https://github.com/AmrutaLohabare/ai-silent-failure-detector
> Follow: #AISilentFailureDetector

---

## The Problem

Your CI pipeline says green. Production is silently failing.

- HTTP 200s with empty response bodies
- Error rates hovering just below alert thresholds
- Latency spikes on successful requests
- Visual failures that never appear in logs
- Azure service failures with no error in the chain
- Multi-signal failures invisible to every individual dashboard

This series builds agents that find the failures you did not know to look for.

---

## The Series - Complete

| Part | Tool | Key Concept | Tests | Status |
|---|---|---|---|---|
| Part 1 | LangChain + RAG | 4-tool pipeline. RAG gives institutional memory. | 31 | Done |
| Part 2 | CrewAI | 3-agent debate. Reduces false positives with evidence. | 26 | Done |
| Part 3 | Playwright + AI Vision | Visual detection. Catches failures logs never see. | 30 | Done |
| Part 4 | Semantic Kernel | Azure enterprise. SK skills + Azure AI Search. | 29 | Done |
| Part 5 | AutoGen | Self-healing. Agent writes and verifies the fix. | 31 | Done |
| Part 6 | Datadog + LLM | 3-signal correlation. Metrics + Traces + Logs. | 37 | Done |
| Part 7 | Verdict | Honest comparison. Live run results. | 20 | Done |

**Total: 204 tests - all passing on Windows + Python 3.13**

---

## The Honest Verdict (Short Version)

| Use this | If... |
|---|---|
| LangChain | You want the fastest setup on any cloud |
| CrewAI | You have too many false positive alerts |
| Playwright | Your users report UI bugs that logs never show |
| Semantic Kernel | Your team runs on Azure |
| AutoGen | You want autonomous fixing of known failures |
| Datadog + LLM | You run microservices with cross-signal failures |

The tool matters less than the pattern.
The RAG knowledge base is the constant across all 6.
Build it religiously. It gets smarter with every incident.

---

## Repo Structure

```
ai-silent-failure-detector\
    part1_langchain\
    part2_crewai\
    part3_playwright\
    part4_semantic_kernel\
    part5_autogen\
    part6_datadog\
    part7_verdict\
    .gitignore
    README.md
```

---

## Knowledge Base - 26 Incidents

| Part | Incidents | Type |
|---|---|---|
| Part 1 | INC-001 to INC-006 | Core silent failure patterns |
| Part 2 | INC-007 to INC-010 | Multi-agent debate patterns |
| Part 3 | INC-011 to INC-014 | Visual failure patterns |
| Part 4 | INC-015 to INC-018 | Azure enterprise patterns |
| Part 5 | INC-019 to INC-022 | Fix patterns for self-healing |
| Part 6 | INC-023 to INC-026 | Cross-signal observability patterns |

---

## Quickstart

```
git clone https://github.com/AmrutaLohabare/ai-silent-failure-detector.git

cd part1_langchain          && pip install -r requirements.txt && python main.py
cd ..\part2_crewai          && pip install -r requirements.txt && python main.py
cd ..\part3_playwright      && pip install -r requirements.txt && python main.py
cd ..\part4_semantic_kernel && pip install -r requirements.txt && python main.py
cd ..\part5_autogen         && pip install -r requirements.txt && python main.py
cd ..\part6_datadog         && pip install -r requirements.txt && python main.py
cd ..\part7_verdict         && pip install -r requirements.txt && python main.py
```

All parts tested on Windows + Python 3.13.5.
Parts 2-7 require no API key.

---

## Connect

LinkedIn: https://www.linkedin.com/in/amruta-lohabare-82017046
GitHub: https://github.com/AmrutaLohabare/ai-silent-failure-detector
Follow: #AISilentFailureDetector

Star this repo if it helped you think differently about QA.
