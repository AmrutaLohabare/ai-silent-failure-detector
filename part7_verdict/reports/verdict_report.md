# AI Silent Failure Detector - Part 7: The Honest Verdict

**Generated:** 2026-05-31 13:33 UTC
**Series:** 7 tools, 1 problem, 184 tests
**Repo:** https://github.com/AmrutaLohabare/ai-silent-failure-detector

---

## Side-by-Side Comparison

| | Part 1 | Part 2 | Part 3 | Part 4 | Part 5 | Part 6 |
|---|---|---|---|---|---|---|
| **Tool** | LangChain | CrewAI | Playwright | Semantic Kernel | AutoGen | Datadog+LLM |
| **Input** | Logs | Logs | Screenshots | Logs | Logs | Metrics+Traces+Logs |
| **Multi-agent** | No | Yes (3) | No | No (Planner) | Yes (3) | No |
| **API key** | Required | No | Optional | Optional | No | Optional |
| **RAG role** | Enrich report | Challenge findings | Visual patterns | Azure Search | Fix patterns | Signal correlation |
| **Output** | Report | Validated report | Visual report | Report | Report + tests | Correlated report |
| **Writes code** | No | No | No | No | Yes | No |
| **Tests** | 31 | 26 | 30 | 29 | 31 | 37 |
| **Complexity** | Low | Medium | Medium | Medium | High | High |

**Live run results (same log file):**

| Part | Findings | Time | Status |
|---|---|---|---|
| Part 1 - LangChain + RAG | 1 | 10.16s | ran |
| Part 2 - CrewAI 3-Agent Debate | 1 | 0.0s | ran |
| Part 3 - Playwright + AI Vision | 4 | 0.0s | ran |
| Part 4 - Semantic Kernel + Azure | 1 | 1.28s | ran |
| Part 5 - AutoGen Self-Healing | N/A | 0.0s | skipped |
| Part 6 - Datadog + LLM Reasoning | 8 | 0.01s | ran |

---

## The Honest Verdict

### Use LangChain if...

You want the fastest path from zero to a working agentic QA tool. OpenAI key + 5 minutes. Works on any cloud. Best for: teams new to agentic AI, proof of concepts, demos.

### Use CrewAI if...

Your team gets paged too often for false positives. The Analyzer-Detector debate reduces noise significantly. Best for: mature teams with high alert fatigue, production monitoring.

### Use Playwright + AI Vision if...

Your application has a significant UI layer and your users report bugs that never appear in logs. Best for: e-commerce, consumer apps, checkout-critical flows.

### Use Semantic Kernel if...

Your team runs on Azure. Full stop. The one-line swap to Azure AI Search makes it production-ready in an Azure environment faster than any other tool in this series. Best for: enterprise Azure shops, .NET teams.

### Use AutoGen if...

You have well-documented failure patterns and want the system to fix known issues autonomously. Not recommended for unknown failure types in production without human review. Best for: well-understood systems with mature runbooks.

### Use Datadog + LLM if...

You run a distributed system where failures manifest across multiple services simultaneously. Single-signal monitoring is not enough. Best for: microservices, payment platforms, multi-dependency critical paths.

---

## The Biggest Lesson

The tool matters less than the pattern. Every part in this series — regardless of the framework — shares three things: a detector, a knowledge base that grows with every incident, and a reporter that explains what it found. The RAG layer is the constant. It is what turns a detector into a system that gets smarter over time. Pick the tool that fits your stack. Build the knowledge base religiously. The tool you choose is temporary. The institutional memory you build is permanent.

---

## Knowledge Base Journey

| Part | Incidents | What was learned |
|---|---|---|
| Part 1 | INC-001 to INC-006 | Core silent failure patterns |
| Part 2 | INC-007 to INC-010 | False positive patterns, debate outcomes |
| Part 3 | INC-011 to INC-014 | Visual failure patterns |
| Part 4 | INC-015 to INC-018 | Azure enterprise failure patterns |
| Part 5 | INC-019 to INC-022 | Fix patterns for self-healing |
| Part 6 | INC-023 to INC-026 | Cross-signal observability patterns |
| **Total** | **26 incidents** | **A complete institutional memory** |