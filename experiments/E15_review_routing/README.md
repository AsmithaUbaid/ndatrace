# E15 — Human Review Routing / Selective Prediction (STAGE A)
Zero model calls, no TEST. Offline evaluation of deterministic routing policies R0–R3 on stored E13 FULL (GPT-5-mini + GPT-P0) DEV outputs, plus a fresh-DEV validation plan and cost forecast.
Route.ACCEPT = AUTO-HANDLE, Route.REVIEW = HUMAN_REVIEW; NDATrace remains a reviewer aid (no approve/reject action).
Script: `scripts/e15_routing_stage_a.py` -> `results/`. Guard tests: `tests/test_e15_routing.py`. Findings: summary.md. Stage A stops for approval before any GPT call.
