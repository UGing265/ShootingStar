Use ck:cook to implement this task (if you lack the cook skill: plan, implement, run tests, no mocks of the code under test).

Task: Phase 04 PART A of plan docs/plans/261122-1507-gemini-6h-technical-forecast/plan.md — unit tests for the pure-Python forecast core (backend/shootingstar/application/forecast/). Part B (pipeline/API tests) comes later, not now.
Read first: AGENTS.md; docs/plans/261122-1507-gemini-6h-technical-forecast/phase-04-backend-tests.md; all files in backend/shootingstar/application/forecast/; backend/shootingstar/domain/models.py (Candle, Timeframe).

IMPORTANT: another worker (omp) is editing backend/shootingstar/application/forecast/ right now. Changes coming: default flat_threshold_pct becomes 0.5; new digest features 1h range_position_{N}d and return_{N}d (N = lookback_days); new helper candle_window.py (time slice with bisect). Do NOT edit any file under backend/shootingstar/. Write tests against the public functions; pass flat_threshold_pct explicitly where it matters. If a test fails because of production code, report it, do not change production code.

Files you own (create only): backend/tests/test_forecast_indicators.py, backend/tests/test_forecast_digest.py, backend/tests/test_forecast_baselines_outcome.py. Build candles with a small local helper in the test files (synthetic 1m candles), no network, no DB.

Must cover:
- ema / rsi / macd / atr / volume_ratio on tiny hand-computed series (put the hand calculation in a comment), warm-up NaN behaviour.
- resample 1m -> 15m / 1h OHLCV correct; bucket not closed at t excluded; incomplete bucket (missing minute) excluded.
- Lookahead: adding candles after t does not change build_technical_digest output or digest_hash.
- Short history raises InsufficientHistoryError.
- agreement_score counts per its documented rules.
- always_up == "UP"; momentum_6h UP / DOWN / None (gap or tie).
- evaluate_direction_outcome with flat_threshold_pct=0.5: +1.5% UP, -1.2% DOWN, +0.3% FLAT, missing target candle UNSCORABLE.
- possible_memorization: t in 2024-12 True, t in 2025-03 False, unknown model False.

Run: `cd backend && .venv/Scripts/python -m pytest -q tests/test_forecast_indicators.py tests/test_forecast_digest.py tests/test_forecast_baselines_outcome.py`. Paste the summary line. If something fails only because omp has not finished A1-A3 yet, say which.
Constraints: YAGNI/KISS, no commit/push, keep each test file < 300 lines.
End your reply with: Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT + 1-2 line summary.
