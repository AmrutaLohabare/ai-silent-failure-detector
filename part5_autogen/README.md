# AI Silent Failure Detector - Part 5: AutoGen Self-Healing

> Part 5 of 7 - LinkedIn Series by Amruta Lohabare
> The agent that does not just detect the failure. It fixes it.

---

## What Part 5 Does Differently

Every other part produces a report.
Part 5 produces working test files.

The 3-agent loop runs fully automatically:
- DetectorAgent finds the silent failure
- HealerAgent writes a pytest fix
- VerifierAgent runs the fix and confirms it catches the failure
- If the fix fails, it loops back to HealerAgent (max 3 rounds)
- If the fix passes, it saves to healed_tests\ and moves on

No human writes a test. The agent writes it, runs it, saves it.

---

## The Self-Healing Loop

```
DetectorAgent scans logs
      |
      | anomaly found
      v
HealerAgent queries RAG for fix pattern
HealerAgent writes pytest test
      |
      v
VerifierAgent runs pytest on the fix
      |
      |-- CATCHES_FAILURE --> save to healed_tests\ (done)
      |-- STRUCTURE_VALID --> save to healed_tests\ (done)
      |-- NEEDS_REWORK    --> back to HealerAgent (max 3 rounds)
      |
      v
Reporter writes enriched report
```

---

## The 3 Agents

### DetectorAgent
Scans production logs for 3 silent failure patterns.
Same detection logic as Parts 1-4 for consistency across the series.

### HealerAgent
Queries the RAG knowledge base for matching fix patterns.
Writes a complete pytest function targeting the detected failure.
Each fix is designed to:
- FAIL on broken code (proves it catches the failure)
- PASS on fixed code (proves the fix works)

### VerifierAgent
Runs pytest on the generated test file.
Interprets the result:
- Exit code 1 + AssertionError = fix correctly catches the failure
- Exit code 0 = fix structure is valid
- Exit code 4 = collection error, needs rework

---

## The 4 Fix Patterns in the Knowledge Base

Part 5 adds INC-019 to INC-022 - fix patterns, not failure patterns:

| ID | Type | What the Healer learns |
|---|---|---|
| INC-019 | FIX_EMPTY_RESPONSE_ASSERTION | Add body length assertion after every HTTP 200 |
| INC-020 | FIX_THRESHOLD_ALERT | Lower error rate threshold to 0.5% on payment paths |
| INC-021 | FIX_LATENCY_TIMEOUT | Add 8-second timeout assertion on all checkout fetches |
| INC-022 | FIX_MODAL_VISIBILITY | Add getBoundingClientRect assertion after order submit |

---

## Project Structure

```
part5_autogen\
    agents\
        __init__.py
        autogen_agents.py      <- DetectorAgent, HealerAgent, VerifierAgent
    knowledge_base\
        incidents.json         <- INC-019 to INC-022 (fix patterns)
    logs\
        sample_prod.log        <- sample log with silent failures
    tests\
        __init__.py
        test_self_healing.py   <- 31 tests, fully offline
    reports\                   <- self_healing_report.md written here
    healed_tests\              <- auto-generated test files saved here
    main.py                    <- entry point, runs self-healing loop
    requirements.txt
    .env.example
    README.md
```

---

## Windows Setup - Step by Step

### Step 1 - Create folders

```
cd C:\Tools\Personal\ai-silent-failure-detector
mkdir part5_autogen
mkdir part5_autogen\agents
mkdir part5_autogen\knowledge_base
mkdir part5_autogen\logs
mkdir part5_autogen\tests
mkdir part5_autogen\reports
mkdir part5_autogen\healed_tests
```

### Step 2 - Create empty init files

```
type nul > part5_autogen\agents\__init__.py
type nul > part5_autogen\tests\__init__.py
```

### Step 3 - Place downloaded files

| Download | Place at |
|---|---|
| autogen_agents.py | part5_autogen\agents\autogen_agents.py |
| incidents.json | part5_autogen\knowledge_base\incidents.json |
| sample_prod.log | part5_autogen\logs\sample_prod.log |
| test_self_healing.py | part5_autogen\tests\test_self_healing.py |
| main.py | part5_autogen\main.py |
| requirements.txt | part5_autogen\requirements.txt |
| .env.example | part5_autogen\.env.example |

### Step 4 - Install and run

```
cd part5_autogen
pip install pyautogen==0.2.35
python -m pytest tests\test_self_healing.py -v
python main.py
```

Expected: 31 passed

---

## Sample Output

```
  AI Silent Failure Detector
  Part 5: AutoGen Self-Healing

[Crew] Step 1 - DetectorAgent scanning logs...
[DetectorAgent] 2 anomaly(s) detected

[Crew] Processing anomaly 1/2: EMPTY_SUCCESS_RESPONSE
[Crew] Round 1/3
[HealerAgent] Round 1 - Writing fix for: EMPTY_SUCCESS_RESPONSE
[VerifierAgent] Verifying fix: test_healed_empty_200_r1
[VerifierAgent] Fix CATCHES FAILURE - assertion fires as expected
[VerifierAgent] Healed test saved: healed_tests\healed_empty_200.py

[Crew] Processing anomaly 2/2: LATENCY_SPIKE_ON_SUCCESS
[Crew] Round 1/3
[HealerAgent] Round 1 - Writing fix for: LATENCY_SPIKE_ON_SUCCESS
[VerifierAgent] Fix VERIFIED - test passes (structure valid)
[VerifierAgent] Healed test saved: healed_tests\healed_latency_spike.py

Self-healing complete
Scanned 62 log entries. Found 2 anomaly(s). Healed 2 with auto-generated tests.

Completed in 13.2s
```

After running, check healed_tests\ for the auto-generated test files.

---

## Series Comparison

| Metric | Part 1 | Part 2 | Part 3 | Part 4 | Part 5 |
|---|---|---|---|---|---|
| Tool | LangChain | CrewAI | Playwright | Semantic Kernel | AutoGen |
| Agents | 1 | 3 | 1 | 4 skills | 3 |
| Output | Report | Report | Visual report | Report | Report + healed tests |
| Writes code | No | No | No | No | Yes |
| Human needed | Review | Review | Review | Review | Optional |
| Tests | 31 | 26 | 30 | 29 | 31 |

---

## Series Roadmap

| Part | Tool | Status |
|---|---|---|
| Part 1 | LangChain + RAG | Done |
| Part 2 | CrewAI 3-agent debate | Done |
| Part 3 | Playwright + AI Vision | Done |
| Part 4 | Semantic Kernel + Azure | Done |
| Part 5 | AutoGen self-healing | This folder |
| Part 6 | Datadog + LLM reasoning | Coming soon |
| Part 7 | Comparison and verdict | Coming soon |

---

## Connect

LinkedIn: https://www.linkedin.com/in/amruta-lohabare-82017046/
Follow the series: #AISilentFailureDetector

Star this repo if it helped you think differently about QA.
