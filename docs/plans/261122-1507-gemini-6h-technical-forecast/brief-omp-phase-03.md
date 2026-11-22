Lead review of phase 02: good work, accepted with 3 amendments. Do the amendments FIRST, then phase 03.

AMENDMENTS to backend/shootingstar/application/forecast/ (phase 02):
A1. User decision (measured on 2,581 real 6h samples: 1% flat excluded 75.9%): flat threshold is now 0.5%. Change default flat_threshold_pct to 0.5 in outcome.py and everywhere else.
A2. lookback_days currently has almost no effect (features use fixed 24h/7d windows), so A/B 7/14/30 days would be meaningless. Add features over the lookback window: 1h range_position_{N}d and return_{N}d (N = lookback_days). Keep warm-up rules.
A3. Performance: callers will pass ~950k candles. Add a helper (e.g. forecast/candle_window.py) that slices candles by time to [t - (max(lookback_days, 9) + 1) days, t + horizon + 1 bar] using bisect on open_time_ms (candles sorted), and use it in the pipeline/batch so digest/baselines/outcome never scan the full list.

Then: Use ck:cook to implement this task.

Task: Phase 03 of plan docs/plans/261122-1507-gemini-6h-technical-forecast/plan.md — Gemini 1-call pipeline + split stages + remove grounding research.
Read first (mandatory): AGENTS.md; docs/plans/261122-1507-gemini-6h-technical-forecast/phase-03-gemini-pipeline-refactor.md (full spec: output schema, prompt rubric LOW/MEDIUM/HIGH, envelope forecast-6h-v1, files to create/modify/delete).
Read for context: backend/shootingstar/application/external_analysis/service.py (run_pipeline, reveal_outcome), adapters/model_api/gemini_adapter.py + key_manager.py, research_agent.py, context.py, report_presentation.py, api/external_routes.py, api/schemas.py, api/replay_routes.py, application/replay.py, cli/main.py (grep every caller before deleting).

Files you own: backend/shootingstar/application/external_analysis/**, backend/shootingstar/application/forecast/**, backend/shootingstar/adapters/model_api/**, backend/shootingstar/api/external_routes.py, backend/shootingstar/api/schemas.py, backend/shootingstar/api/replay_routes.py and application/replay.py only if they call removed code. Move production mocks to backend/tests/fakes/ (create that dir only). Do NOT edit other test files (phase 04 worker owns them); if existing tests break because of removed contracts, list them in your report.

Key acceptance criteria:
- New job: exactly 1 Gemini request; JSON schema {direction UP|DOWN, confidence LOW|MEDIUM|HIGH, reasons[{feature_ids,text}], risks[]}; no ABSTAIN for new jobs; legacy jobs still readable.
- Envelope protocol_version "forecast-6h-v1" with digest, answer, verification, agreement_score, baselines {always_up, momentum_6h}, possible_memorization, horizon_minutes (default 360), lookback_days, flat_threshold_pct (0.5), prompt_version, token usage.
- verify_stage flags reasons citing unknown feature_ids or numbers not matching the digest.
- reveal_outcome uses forecast/outcome.py with 0.5%.
- Gemini error/schema failure => explicit error status, no fallback fake forecast.
- `grep -rn "grounded_research\|research_agent\|Steve Nison" backend/shootingstar` empty.
- Every pipeline file < 200 lines.
- Self-check: one real retrospective job (mock_mode allowed ONLY for this self-check if no key; say which) on snapshot 9847f2ab355365128b687f175162b5b730cdb62499ef414082865b058b70a2a0 (2025-02 to 2026-11, 1m).
- Note: `pytest` has pre-existing env failures (DB shootingstar_test_db missing: 26 errors + test_fail_closed_api_protection). Baseline before your change: 77 passed. Do not count those as yours; report any NEW failures.

Constraints: YAGNI/KISS/DRY, AGENTS.md. No DB schema change. Do NOT commit or push. Never print API keys.
End your reply with: Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT + 1-2 line summary.
