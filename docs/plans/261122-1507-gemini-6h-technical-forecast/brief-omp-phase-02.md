Use ck:cook to implement this task (if you lack the cook skill: plan, implement, compile, test, no mocks).

Task: Phase 02 of plan docs/plans/261122-1507-gemini-6h-technical-forecast/plan.md — pure-Python forecast core (no Gemini calls).
Read first (mandatory): AGENTS.md; docs/plans/261122-1507-gemini-6h-technical-forecast/plan.md; docs/plans/261122-1507-gemini-6h-technical-forecast/phase-02-forecast-core-pure-python.md (full spec); docs/plans/261122-1507-gemini-6h-technical-forecast/reports/brainstorm-261122-1419-gemini-6h-technical-forecast.md (design rationale).
Read for context: backend/shootingstar/application/external_analysis/context.py (InsufficientHistoryError, causal window), backend/shootingstar/domain/ (Candle), backend/shootingstar/application/patterns.py (reuse candle pattern logic if fitting), backend/shootingstar/application/external_analysis/service.py reveal_outcome (interval containment rule).

Files you own (create): backend/shootingstar/application/forecast/{__init__,resample,indicators,technical_digest,agreement_score,baselines,outcome}.py (+ memorization flag inside outcome.py or own small module). Do not modify other files in this phase.

Acceptance criteria:
- Resample closed 1m/5m candles to 15m/1h (drop buckets not fully closed at t).
- numpy-only indicators: ema, rsi(14), macd(12,26,9), atr(14), volume ratio. No new dependencies.
- build_technical_digest(candles, t_ms, lookback_days=14) -> features with feature_id/timeframe/name/value/unit + digest_hash; uses only candles with close_time_ms <= t; raises InsufficientHistoryError when history short. Features per phase file (EMA slope 1h/4h, RSI 1h/15m, MACD hist 1h, ATR% 1h, volume ratio, range position 24h/7d, swing high/low, return 6h/24h).
- agreement_score: fixed documented rules, returns up/down/total counts.
- baselines: always_up, momentum_6h (None if t-6h missing).
- outcome: evaluate_direction_outcome(..., flat_threshold_pct=1.0) -> UP/DOWN/FLAT/UNSCORABLE + target_price + move_pct.
- possible_memorization(t_ms, model_id): gemini-2.5-flash cutoff = 2025-02-01T00:00:00Z.
- Each file < 200 lines. `cd backend && .venv/Scripts/python -c "import shootingstar.application.forecast"` OK and existing `.venv/Scripts/python -m pytest` not broken.
- Quick self-check: digest for one real t on an existing snapshot (use `.venv/Scripts/shootingstar list-snapshots`) has < ~8000 chars JSON. Report the char count.

Constraints: YAGNI/KISS/DRY, follow AGENTS.md. No DB schema change. No network calls. Do NOT commit or push. Full tests are phase 04 (another worker) — a tiny lookahead sanity check is enough here.
End your reply with: Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT + 1-2 line summary.
