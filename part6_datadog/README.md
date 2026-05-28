# AI Silent Failure Detector - Part 6: Datadog + LLM Reasoning

> Part 6 of 7 - LinkedIn Series by Amruta Lohabare
> The part that reasons across 3 signals simultaneously.

---

## What Part 6 Does Differently

Parts 1-5 analysed one signal at a time — log files.
Part 6 analyses metrics, traces, and logs together.

A silent failure often shows up across all 3 signals at once
but no single signal crosses a threshold. The correlation engine
finds these multi-signal patterns that no dashboard catches.

---

## The Real Incident in This Demo

Metrics showed p99 latency rising from 210ms to 4300ms.
Traces showed payment-gateway consuming 94% of trace duration.
Logs showed silent HTTP 200 returns after timeout and idempotency collisions.

No single signal crossed an alert threshold.
All three together revealed a CRITICAL payment gateway degradation
with 312 customers double-charged.

---

## Architecture

```
observability_snapshot.json
  (metrics + traces + logs)
          |
          v
+------------------+    +------------------+    +------------------+
| MetricsCollector |    |  TraceAnalyzer   |    |  LogCorrelator   |
| p99 latency      |    | span bottleneck  |    | silent 200s      |
| error rate trend |    | service duration |    | idempotency      |
| throughput drop  |    | % of trace       |    | retry escalation |
+--------+---------+    +--------+---------+    +--------+---------+
         |                       |                       |
         +───────────────────────+───────────────────────+
                                 |
                    +------------+------------+
                    |   CorrelationEngine     |
                    | Reasons across all 3    |
                    | Detects cross-signal    |
                    | patterns                |
                    | LLM explains WHY        |
                    +------------+------------+
                                 |
                            +----+----+
                            |   RAG   |
                            | INC-023 |
                            | INC-026 |
                            +----+----+
                                 |
                    reports\observability_report.md
```

---

## Correlated Patterns Detected

| Pattern | Severity | Signals |
|---|---|---|
| PAYMENT_GATEWAY_SILENT_DEGRADATION | CRITICAL | metrics + traces + logs |
| DUPLICATE_CHARGE_RISK | CRITICAL | logs |
| SILENT_ABANDONMENT | HIGH | metrics |

---

## 4 New Incident Types (INC-023 to INC-026)

| ID | Type | What it teaches the correlator |
|---|---|---|
| INC-023 | CROSS_SIGNAL_LATENCY_SPIKE | Stripe degradation visible only across all 3 signals |
| INC-024 | METRIC_LOG_DIVERGENCE | Metrics green, logs show empty responses |
| INC-025 | THROUGHPUT_DROP_SILENT | Users abandoning — no errors, just dropping throughput |
| INC-026 | TRACE_SPAN_ANOMALY | Single span consuming 94% of trace |

---

## Datadog API Swap Point

Runs fully offline with local JSON snapshot.
To connect to real Datadog in production, swap one line in each collector:

```python
# In collectors\observability_collectors.py

# OFFLINE (current):
# Loads from observability_snapshot.json

# PRODUCTION SWAP:
# from datadog_api_client import ApiClient, Configuration
# from datadog_api_client.v1.api.metrics_api import MetricsApi
```

---

## Project Structure

```
part6_datadog\
    collectors\
        __init__.py
        observability_collectors.py  <- MetricsCollector, TraceAnalyzer, LogCorrelator
    analyzer\
        __init__.py
        correlation_engine.py        <- cross-signal correlation + LLM reasoning
    rag\
        __init__.py
        rag_context.py               <- TF-IDF retriever, offline
    knowledge_base\
        incidents.json               <- INC-023 to INC-026
    data\
        observability_snapshot.json  <- mock metrics + traces + logs
    tests\
        __init__.py
        test_observability.py        <- 37 tests, fully offline
    reports\                         <- observability_report.md written here
    main.py
    requirements.txt
    .env.example
    README.md
```

---

## Windows Setup

```
cd C:\Tools\Personal\ai-silent-failure-detector
mkdir part6_datadog
mkdir part6_datadog\collectors
mkdir part6_datadog\analyzer
mkdir part6_datadog\rag
mkdir part6_datadog\knowledge_base
mkdir part6_datadog\data
mkdir part6_datadog\tests
mkdir part6_datadog\reports
type nul > part6_datadog\collectors\__init__.py
type nul > part6_datadog\analyzer\__init__.py
type nul > part6_datadog\rag\__init__.py
type nul > part6_datadog\tests\__init__.py

cd part6_datadog
python -m pytest tests\test_observability.py -v
python main.py
```

Expected: 37 passed

---

## Sample Output

```
[Step 1/4] MetricsCollector...   3 metric finding(s)
[Step 2/4] TraceAnalyzer...      2 trace finding(s)
[Step 3/4] LogCorrelator...      3 log finding(s)
[Step 4/4] CorrelationEngine...
  Signals firing: ['metrics', 'traces', 'logs']
  Correlated patterns: 3
[RAG] 2 past incident(s) retrieved

Findings : 8
Correlated: 3
Completed in 0.1s
```

---

## Series Comparison

| Metric | Part 1 | Part 2 | Part 3 | Part 4 | Part 5 | Part 6 |
|---|---|---|---|---|---|---|
| Tool | LangChain | CrewAI | Playwright | Semantic Kernel | AutoGen | Datadog+LLM |
| Input | Logs | Logs | Screenshots | Logs | Logs | Metrics+Traces+Logs |
| Signals | 1 | 1 | Visual | 1 | 1 | 3 simultaneously |
| Cross-signal | No | No | No | No | No | Yes |
| Tests | 31 | 26 | 30 | 29 | 31 | 37 |

---

## Series Roadmap

| Part | Tool | Status |
|---|---|---|
| Part 1 | LangChain + RAG | Done |
| Part 2 | CrewAI 3-agent debate | Done |
| Part 3 | Playwright + AI Vision | Done |
| Part 4 | Semantic Kernel + Azure | Done |
| Part 5 | AutoGen self-healing | Done |
| Part 6 | Datadog + LLM reasoning | This folder |
| Part 7 | Comparison and verdict | Coming soon |

---

## Connect

LinkedIn: https://www.linkedin.com/in/amruta-lohabare-82017046
Follow: #AISilentFailureDetector

Star this repo if it helped you think differently about QA.