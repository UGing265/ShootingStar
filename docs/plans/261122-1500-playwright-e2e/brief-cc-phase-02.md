Use ck:cook to implement this task (plan, implement, run, verify; no stubs, no mocks, no TODO).

Repo: D:/AShiroru/ProgramCode/Project/Team/ShootingStar, branch dev (shared tree; changes you did not make belong to others, do not touch or revert them).

Read first, in order: AGENTS.md, frontend/AGENTS.md, docs/plans/261122-1500-playwright-e2e/plan.md, docs/plans/261122-1500-playwright-e2e/phase-02-tests-and-testids.md, frontend/playwright.config.ts, frontend/e2e/preflight.ts, docs/frontend/README.md section 6.

Task: implement ONLY phase 02: Playwright specs plus data-testid attributes. Phase 01 (config, preflight) is DONE and verified. Do not edit it.

Files you may edit/create:
- frontend/e2e/*.spec.ts (new)
- data-testid attributes ONLY (no logic, no style, no text changes) in frontend/src/features/replay/*.tsx and in other frontend/src/features/**/*.tsx or frontend/src/app/**/page.tsx files that belong to a page you test.
Forbidden: backend/**, frontend/playwright.config.ts, frontend/e2e/preflight.ts, frontend/package.json, frontend/next.config.mjs, frontend/tsconfig.json, frontend/next-env.d.ts, .env*, docs/plans/**, any logic change in frontend/src/**.

Steps:
1. List pages: find frontend/src/app -name page.tsx. Write one smoke spec per page that exists: opens the page, has a visible heading, no console errors, no text "fetch failed".
2. Replay spec (/replay), snapshot chosen by process.env.E2E_SNAPSHOT_ID (never "first snapshot"):
   a. dropdown label contains a date range and "#" plus 8 characters of the snapshot id.
   b. default state: status line says candles loaded end at the snapshot end.
   c. enter 2026-10-30T12:00 in the datetime-local input: price field changes, status line shows a range around that time.
   d. enter 2026-12-01T12:00: alert text "Ngoài phạm vi snapshot" appears, price field unchanged.
   e. enter a time inside the last 30 minutes of the snapshot: blocked the same way.
   Use data-testid on the input, price field, status line, error alert. Fill datetime-local with page.fill (value format YYYY-MM-DDTHH:mm).
3. Strategy flow in dry-run mode only (see how the UI exposes dryRun; do not call real Gemini): pick a time, click the "Xem vùng vào lệnh" button, assert a result or a clear state appears. Append created job ids to frontend/e2e/.created-jobs.json (file is git-ignored).
4. Gemini flow with dry-run only. One extra test tagged @real-gemini (title contains "@real-gemini") that calls real Gemini once; short comment that it costs quota. NEVER run it.
5. Chart is a canvas: assert text/state only, no pixel comparison.

Hard rules:
- Never print or write SHOOTINGSTAR_ADMIN_KEY or any .env value.
- Main database is used on purpose. No migration, no deleting data, no test DB.
- Use ports 8100/3100 only (via the existing config). Never start or stop anything on 3000 or 8000.
- Run tests with: cd frontend; set E2E_SNAPSHOT_ID=61da7964edb30fbff8de9add491e090a2c7738b41ecc1b048570b5dd578eb8e8 on the command line only (PowerShell: $env:E2E_SNAPSHOT_ID=...). Unset SHOOTINGSTAR_ADMIN_KEY in the shell first.
- Do not skip, loosen, or delete a failing test to make it pass. If the app is wrong, report it.
- Do not commit or push. Do not change plan status.
- After every run check: git diff -- frontend/next-env.d.ts frontend/tsconfig.json must be empty (git restore only those two generated files if not).

Acceptance (paste raw output of each):
- npx playwright test --list   (lists your tests, none tagged @real-gemini)
- npx playwright test   (exit 0)
- npm run typecheck   (exit 0)
- git diff -- frontend/src   (only data-testid attribute additions)
- git diff -- frontend/next-env.d.ts frontend/tsconfig.json   (empty)
- netstat shows nothing listening on 8100/3100 afterwards

Finish with: Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT + 1-2 lines, files changed, raw outputs, what you could not run.
