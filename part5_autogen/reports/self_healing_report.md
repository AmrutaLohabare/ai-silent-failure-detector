# AI Silent Failure Detector - Part 5: Self-Healing Report

**Generated:** 2026-05-17 02:39 UTC
**Entries analysed:** 62
**Anomalies detected:** 2
**Tests auto-generated:** 2
**Healing failures:** 0

---

## Auto-Generated Healed Tests

### Empty Success Response

**Fix pattern:** INC-019 - Add response body assertion to catch empty 200 responses
**Test function:** `test_healed_empty_200_r1`
**Saved to:** `healed_tests\healed_empty_200.py`
**Rounds needed:** 1
**Verification:** CATCHES_FAILURE

---

### Latency Spike On Success

**Fix pattern:** INC-021 - Add AbortController timeout to all fetch calls on checkout path
**Test function:** `test_healed_latency_spike_r1`
**Saved to:** `healed_tests\healed_latency_spike.py`
**Rounds needed:** 1
**Verification:** STRUCTURE_VALID

---

## Series Comparison

| Metric | Part 1 | Part 2 | Part 3 | Part 4 | Part 5 |
|---|---|---|---|---|---|
| Tool | LangChain | CrewAI | Playwright | Semantic Kernel | AutoGen |
| Agent action | Detect | Detect + debate | Visual detect | Detect (SK) | Detect + fix + verify |
| Output | Report | Report | Visual report | Report | Report + healed tests |
| Human needed | Review | Review | Review | Review | Optional |
| Tests | 31 | 26 | 30 | 29 | TBD |