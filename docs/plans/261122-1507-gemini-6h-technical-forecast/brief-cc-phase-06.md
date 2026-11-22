Use ck:cook to implement this task (plan, implement, typecheck, build, e2e; no mock data in production UI).

Task: Phase 06 of docs/plans/261122-1507-gemini-6h-technical-forecast/plan.md — frontend for forecast-6h-v1 + update Playwright e2e + sync docs/systemmd/frontend.
Read first (mandatory): AGENTS.md (rules 6, 7, 9: UTC+7 display, no raw UUID/hash/IDs in UI, chart rules); docs/DESIGN.md; docs/plans/261122-1507-gemini-6h-technical-forecast/phase-06-frontend-and-e2e.md (full spec incl. the "E2E Gemini" decision).
Backend contract (read the code, do not guess): backend/shootingstar/api/schemas.py, backend/shootingstar/api/external_routes.py (job GET, reveal, new GET /external-analysis/scoreboard), backend/shootingstar/application/external_analysis/job_dto.py, stages/report_stage.py (envelope forecast-6h-v1: digest.features[{feature_id,timeframe,name,value,unit}], answer{direction,confidence,reasons[{feature_ids,text}],risks}, verification{valid,issues}, agreement_score{up,down,total}, baselines{always_up,momentum_6h}, possible_memorization, horizon_minutes, lookback_days, flat_threshold_pct, token_usage).
Real data for checks: forecast job id prefix 1dfa822c (READY, DOWN/MEDIUM) on snapshot 9847f2ab…; legacy jobs (30m, ABSTAIN, evidence-pipeline-v1) also exist in the main DB.

Files you own: frontend/src/features/replay/**, frontend/src/features/report/**, frontend/src/shared/format.ts, frontend/src/shared/api-client.ts (only to add the scoreboard call), frontend/e2e/gemini.spec.ts (+ small helpers in frontend/e2e/ if needed), docs/systemmd/frontend/01-architecture-and-folders.md, docs/systemmd/frontend/02-data-fetching-and-charts.md.
Do not touch backend/ or other docs.

Key acceptance:
- New jobs: show direction (TĂNG/GIẢM), confidence with note "model tự đánh giá, chưa kiểm chứng", agreement "x/y chỉ số cùng chiều", reasons with readable feature name + value (no raw feature_id strings shown as the only label), risks, verification warning when invalid, memorization banner when possible_memorization. No research/sources section for new jobs.
- Replay result: Gemini vs Luôn TĂNG vs Theo đà 6h vs outcome; FLAT shows "đi ngang (<0.5%), không chấm".
- Scoreboard card (server-side fetch via api-client; browser never recomputes metrics): accuracy + n + Wilson 95% for Gemini / always_up / momentum_6h, breakdown by confidence; empty state "Chưa có dữ liệu".
- Legacy jobs still render (ABSTAIN shows "Không dự báo").
- e2e default: open saved real job (E2E_FORECAST_JOB_ID default = full id of 1dfa822c job, look it up via API/DB read once) and a legacy job (E2E_LEGACY_JOB_ID); no Gemini call, no mock. Creating a new job only in @real-gemini.
- docs/systemmd/frontend: update to match real code (grep every path/name you write).
- Commands green: `cd frontend && npm run typecheck && npm run build && npx playwright test` (Playwright uses its own ports 8100/3100). Paste summaries.
Constraints: YAGNI/KISS, files < 200 lines where practical (split components), no em/en dash in UI copy, no commit/push.
End with: Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT + 1-2 line summary.
