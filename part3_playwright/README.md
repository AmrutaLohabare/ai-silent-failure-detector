# AI Silent Failure Detector - Part 3: Playwright + AI Vision

> Part 3 of 7 - LinkedIn Series by Amruta Lohabare
> Same problem. Different tool. This time we catch what logs never see.

---

## What Part 3 Solves

Parts 1 and 2 analysed log files.
Part 3 looks at the actual UI - because some failures never appear in logs at all.

The button is there. The API returned 200. Logs show nothing wrong.
But the button is white text on a white background. Users cannot see it.

These are visual silent failures. The only way to catch them is to look.

---

## The 4 Silent Failures in This Demo

All four return HTTP 200. None appear in logs.

| # | Type | What happens | Why logs miss it |
|---|---|---|---|
| 1 | INVISIBLE_ELEMENT | Pay button has white text on white background | DOM has button, HTTP 200, no JS error |
| 2 | STUCK_SPINNER | Live pricing fetch has no timeout, spins forever | fetch() never errors, just hangs |
| 3 | EMPTY_CONTENT_SECTION | Recommendations heading shows, items hidden by CSS | API returns 200 with empty array |
| 4 | MISSING_CONFIRMATION | Order confirmation modal at top:-9999px | submitOrder() runs fine, HTTP 200 |

---

## Detection Pipeline

```
checkout_broken.html
        |
        v
[Step 1] DOM Analysis
         Parse HTML for known silent failure patterns
         Rule-based, always runs, no dependencies
        |
        v
[Step 2] Screenshot Capture
         Playwright opens the page and captures 4 checkpoints
         Falls back to existing screenshots if Playwright not installed
        |
        v
[Step 3] Pixel Diff
         Compare current screenshots against healthy baseline
         Uses Pillow - fully offline, no API key needed
        |
        v
[Step 4] GPT-4o Vision  (optional - only if OPENAI_API_KEY set)
         Send screenshots to GPT-4o for semantic analysis
         Automatically skipped if no key - pixel diff covers it
        |
        v
[RAG]  Retrieve similar past incidents and runbooks
        |
        v
[Report] reports\visual_failure_report.md
         What failed, why, business impact, fix steps
```

---

## Project Structure

```
part3_playwright\
    pages\
        checkout_healthy.html      <- known-good baseline page
        checkout_broken.html       <- page with 4 silent failures injected
    detector\
        __init__.py
        visual_detector.py         <- DOM analysis, pixel diff, Vision
    rag\
        __init__.py
        rag_context.py             <- TF-IDF retriever, offline
    knowledge_base\
        incidents.json             <- INC-011 to INC-014 (visual types)
    screenshots\
        baseline\                  <- captured from healthy page
        current\                   <- captured from page under test
        diff\                      <- amplified diff images
    tests\
        __init__.py
        test_visual_detector.py    <- 30 tests, fully offline
    reports\                       <- generated reports land here
    main.py                        <- entry point
    requirements.txt
    .env.example
    README.md
```

---

## Windows Setup - Step by Step

### Step 1 - Create folders

Run each line one at a time in Command Prompt:

```
cd C:\Tools\Personal\ai-silent-failure-detector
mkdir part3_playwright
mkdir part3_playwright\detector
mkdir part3_playwright\rag
mkdir part3_playwright\knowledge_base
mkdir part3_playwright\pages
mkdir part3_playwright\tests
mkdir part3_playwright\reports
mkdir part3_playwright\screenshots
mkdir part3_playwright\screenshots\baseline
mkdir part3_playwright\screenshots\current
mkdir part3_playwright\screenshots\diff
```

### Step 2 - Create empty init files

```
type nul > part3_playwright\detector\__init__.py
type nul > part3_playwright\rag\__init__.py
type nul > part3_playwright\tests\__init__.py
```

### Step 3 - Download and place files

Download each file from the outputs and place it at the path shown:

| Download | Place at |
|---|---|
| visual_detector.py | part3_playwright\detector\visual_detector.py |
| rag_context.py | part3_playwright\rag\rag_context.py |
| incidents.json | part3_playwright\knowledge_base\incidents.json |
| checkout_healthy.html | part3_playwright\pages\checkout_healthy.html |
| checkout_broken.html | part3_playwright\pages\checkout_broken.html |
| test_visual_detector.py | part3_playwright\tests\test_visual_detector.py |
| main.py | part3_playwright\main.py |
| requirements.txt | part3_playwright\requirements.txt |
| .env.example | part3_playwright\.env.example |

### Step 4 - Install dependencies

```
cd part3_playwright
pip install -r requirements.txt
```

To also enable Playwright browser automation:

```
playwright install chromium
```

This is optional. The detector runs without it using DOM analysis + pixel diff.

### Step 5 - Run tests (no API key needed)

```
cd C:\Tools\Personal\ai-silent-failure-detector\part3_playwright
python -m pytest tests\ -v
```

Expected: 30 passed

### Step 6 - Run the detector

```
python main.py
```

To test the broken page explicitly:

```
python main.py --page pages\checkout_broken.html --baseline pages\checkout_healthy.html
```

To enable GPT-4o Vision, copy .env.example to .env and add your key:

```
copy .env.example .env
notepad .env
```

---

## What the Report Looks Like

```
# AI Silent Failure Detector - Part 3: Visual Report

Generated: 2024-01-15 10:05 UTC
Page tested: checkout_broken.html
Detection methods: DOM analysis, pixel diff
Visual failures detected: 4

---

## Finding 1: Invisible Element
Severity: HIGH
Element: Pay button
Detection method: DOM_ANALYSIS
Description: White text on white background - button invisible to user

### Similar past incidents
INC-011 - Pay button invisible after CSS deploy
Root cause: CSS variable override set button text to #ffffff globally...
Business impact: Checkout conversion dropped 94%. Revenue loss Rs 2.1M.
Runbook:
  - Check CSS variable overrides: grep -r btn-primary-text src/styles/
  - Audit dark mode stylesheets for color variable conflicts
  - Add contrast check to CI: axe-core audit on all CTA buttons
```
## Screenshots
Screenshots are generated locally on each run.
Run `python main.py` to generate them in `screenshots\`.
---

## Series Roadmap

| Part | Tool | Status |
|---|---|---|
| Part 1 | LangChain + RAG | Done |
| Part 2 | CrewAI 3-agent debate | Done |
| Part 3 | Playwright + AI Vision | This folder |
| Part 4 | Semantic Kernel (Azure) | Coming soon |
| Part 5 | AutoGen self-healing | Coming soon |
| Part 6 | Datadog + LLM reasoning | Coming soon |
| Part 7 | Comparison and verdict | Coming soon |

---

## Connect

LinkedIn: https://www.linkedin.com/in/amruta-lohabare/
Follow the series: #AISilentFailureDetector

Star this repo if it helped you think differently about QA.
