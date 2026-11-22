Use ck:cook to implement this task (plan, implement, run tests; fakes only inside tests/).

Task: Phase 04 PART B of docs/plans/261122-1507-gemini-6h-technical-forecast/plan.md — rewrite backend tests for the new 1-call Gemini forecast pipeline.
Read first: AGENTS.md (NOTE: tests now run directly on the MAIN DB; create rows with your own ids and delete exactly those rows in finally; never bulk delete/truncate/drop); docs/plans/261122-1507-gemini-6h-technical-forecast/phase-04-backend-tests.md; backend/shootingstar/application/external_analysis/{service.py,forecast_pipeline.py,job_dto.py,stages/*.py}; backend/shootingstar/adapters/model_api/{gemini_adapter.py,gemini_transport.py,prompts/forecast_6h_prompt.py}; backend/shootingstar/api/external_routes.py; backend/tests/fakes/; backend/tests/conftest.py.

Context: the other worker (omp) is right now (a) deleting dead modules patterns.py, external_analysis/verifier.py, url_validator.py, report_presentation.py, context.py (InsufficientHistoryError moves to shootingstar/application/forecast/errors.py), (b) fixing verify_stage so numbers inside timeframe/period words ("1 giờ", "4 giờ", "RSI 14", "7 ngày") are NOT flagged, (c) adding a scoreboard + batch CLI. Do not edit anything under backend/shootingstar/.

Files you own: backend/tests/test_external_analysis.py (rewrite; split into test_external_analysis_pipeline.py / test_external_analysis_api.py if > 300 lines), backend/tests/test_gemini_json_parsing.py (fix or delete if obsolete), backend/tests/fakes/** (may extend).
Remove tests for deleted behaviour (hypothesis/research/grounding/pattern diagnostics/old verifier/url validator/report_presentation/ABSTAIN for new jobs/mock_mode production path).

Must cover (fake Gemini at the adapter/transport boundary, no network):
- New job: exactly 1 model call; envelope protocol_version forecast-6h-v1 with digest, answer, verification, agreement_score, baselines, possible_memorization, horizon_minutes 360, lookback_days, flat_threshold_pct 0.5, token usage.
- Invalid answer (ABSTAIN, missing reasons, bad confidence) => job FAILED with message, no fabricated forecast.
- verify_stage: unknown feature_id flagged; fabricated decimal flagged; timeframe words like "1 giờ", "RSI 14", "7 ngày" NOT flagged (this one may fail until omp finishes B1; report it).
- Insufficient history => INSUFFICIENT_HISTORY.
- mock_mode request => rejected/FAILED (production mock disabled).
- API: create job (admin gate on), get job, reveal uses 0.5% flat threshold; admin gate still blocks without key.
- Legacy job row (old 30m ABSTAIN envelope) still serializes via the API.

Run: `cd backend && .venv/Scripts/python -m pytest -q` (whole suite). Paste the summary. Report failures caused by omp's in-progress work separately.
Constraints: YAGNI/KISS, no commit/push.
End with: Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT + 1-2 line summary.
