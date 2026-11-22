Lead verification of phase 03: ACCEPTED with amendments. Lead ran a real Gemini job (job 1dfa822c, snapshot 9847f2ab, t=2026-06-19 00:00 UTC): READY, 1 call, 983+469 tokens, DOWN/MEDIUM, all quoted decimals matched digest. pytest (excluding tests/test_external_analysis.py) 117 passed.

Do these AMENDMENTS FIRST, then phase 05.

B1. verify_stage false positives: on that real job it flagged "1", "4" (from "1 giờ", "4 giờ"), "14" (from "RSI 14"), "24", "7" (from "24 giờ", "7 ngày"). Every job would be invalid, so the flag is useless. Fix: do not check numbers that are part of a timeframe/period expression (number followed by optional space and giờ|h|ngày|d|phút|m|tuần|nến, or number attached to/after indicator names like RSI, EMA, MACD, ATR, SMA) and numbers inside feature_id-like tokens. Still flag: unknown feature_ids, and value-like numbers (decimals or any other number) that match no cited feature value. Keep it simple, document the rule in the docstring. Rerun verify on the stored answer of job 1dfa822c (read evidence_envelope_json from DB) and show valid == true.
B2. Delete dead code (Lead authorizes, including files outside your earlier ownership): backend/shootingstar/application/patterns.py, application/external_analysis/verifier.py, url_validator.py, report_presentation.py, context.py. Move InsufficientHistoryError to backend/shootingstar/application/forecast/errors.py and update imports. Trim contracts.py to what is still used (job DTO, enums, request, legacy fields needed to read old jobs). grep every symbol before deleting; production must import cleanly. Tests that import deleted modules are being rewritten by the other worker (phase 04B); do not edit tests.
B3. Do NOT reintroduce production mock mode.

Then: Use ck:cook to implement this task.
Task: Phase 05 of docs/plans/261122-1507-gemini-6h-technical-forecast/plan.md — scoreboard + forecast-batch CLI.
Read first: AGENTS.md; docs/plans/261122-1507-gemini-6h-technical-forecast/phase-05-scoreboard-and-batch-cli.md (full spec).
Extra requirements:
- Scoreboard reports accuracy at flat thresholds 0.5 (default) and also returns n per threshold for 0.3 and 1.0 as secondary info (scoring only, no extra Gemini calls).
- Scoreboard reads only protocol_version forecast-6h-v1 jobs; scores with forecast/outcome.py using the bounded candle window (never scan all 950k candles per job; load the snapshot once per batch/scoreboard call).
- forecast-batch --dry-run must not create DB rows; it prints baseline accuracy (always_up, momentum_6h) for the selected range. Non dry-run creates jobs via ExternalAnalysisService and respects --limit, resume, stop on 429/quota/3 consecutive errors.
- Files you own: backend/shootingstar/application/forecast/**, backend/shootingstar/application/external_analysis/**, backend/shootingstar/api/external_routes.py, backend/shootingstar/api/schemas.py, backend/shootingstar/cli/** (new cli/forecast_batch_command.py), plus the deletions in B2.
Acceptance (Lead will re-run): `shootingstar forecast-batch --snapshot 9847f2ab355365128b687f175162b5b730cdb62499ef414082865b058b70a2a0 --dry-run --limit 200` prints baseline table, creates 0 rows; scoreboard route returns JSON for the snapshot; all files < 200 lines; `cd backend && .venv/Scripts/python -m pytest -q --ignore=tests/test_external_analysis.py` shows no new failures. Do NOT run a non-dry-run batch with real Gemini (Lead asks user first).
Constraints: YAGNI/KISS/DRY, AGENTS.md (tests run on main DB now; never bulk delete). No DB schema change. No commit/push. Never print keys.
End with: Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT + 1-2 line summary.
