Lead verification of phase 05: ACCEPTED. Lead re-ran: full pytest 136 passed (main DB row counts unchanged); dry-run over 2,580 points created 0 rows: always_up 49.88% (n=1273), momentum_6h 46.50%; scoreboard route 200 with key, 403 without; verify_stage now valid on real job 1dfa822c and still flags a fabricated "72.5".

C1 (fix first): resume in cli/forecast_batch_command.py `_done_times` skips ALL statuses including FAILED, so points that failed on 429/quota are lost forever. Change: skip READY, ABSTAIN (legacy) and INSUFFICIENT_HISTORY; re-run FAILED points (reuse or replace the failed job row; never create duplicate READY jobs for the same key). Add/adjust a test in backend/tests/test_forecast_batch_resume.py (you own this new file only; tests run on main DB: create own ids, delete exactly them in finally).

Then: Use ck:cook to implement this task.
Task: Phase 07 (backend half) of docs/plans/261122-1507-gemini-6h-technical-forecast/plan.md — docs sync. Read docs/plans/261122-1507-gemini-6h-technical-forecast/phase-07-docs-sync.md and AGENTS.md (rule 8: plans/reports only in docs/plans).
Files you own: docs/backend/README.md, docs/external-model-forecast-design.md, docs/systemmd/README.md, docs/systemmd/governance.md, docs/systemmd/backend/*.md. (The other worker owns docs/systemmd/frontend/*.)
Content:
- forecast-batch usage (flags, dry-run, limit, resume, stop on quota), scoreboard route, env vars needed (names only, never values).
- Pipeline: feed (Python digest 1h x N days + 15m x 24h, agreement score, baselines, memorization flag) -> 1 Gemini call -> verify -> envelope forecast-6h-v1 in evidence_envelope_json (no schema change); grounding/research/pattern diagnostics removed; production mock disabled; tests run on main DB.
- Real baseline numbers above with date 2026-11-22 and snapshot range 2025-02-01 to 2026-11-22; state clearly Gemini accuracy NOT yet measured.
- Sources from docs/plans/261122-1507-gemini-6h-technical-forecast/reports/brainstorm-261122-1419-gemini-6h-technical-forecast.md (cutoff 01/2025, Xiong ICLR 2024, Tang & Zhu, Tan NeurIPS 2024 with scope caveat, Liu & Tsyvinski).
- Only write what exists in code: grep every file path / function / route / CLI flag you mention. Remove statements about deleted modules (patterns, research, lessons, ABSTAIN for new jobs).
Acceptance: `shootingstar forecast-batch --help` matches docs; `cd backend && .venv/Scripts/python -m pytest -q` green. No commit/push.
End with: Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT + 1-2 line summary.
