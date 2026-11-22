Use ck:cook to implement this task (plan, implement, run, verify; no stubs, no mocks, no TODO).

Repo: D:/AShiroru/ProgramCode/Project/Team/ShootingStar, branch dev (shared; other changes in the working tree are not yours, do not touch or revert them).

Read first: AGENTS.md, frontend/AGENTS.md, docs/plans/261122-1500-playwright-e2e/plan.md, docs/plans/261122-1500-playwright-e2e/phase-01-env-and-config.md.

Task: implement ONLY phase 01 exactly as written in phase-01-env-and-config.md (Playwright install, frontend/playwright.config.ts with two webServers on ports 8100/3100, frontend/e2e/preflight.ts, scripts e2e and e2e:gemini, frontend/.gitignore entries, docs/frontend/README.md section).

Files you may edit: frontend/package.json, frontend/package-lock.json, frontend/playwright.config.ts, frontend/e2e/preflight.ts, frontend/.gitignore, docs/frontend/README.md. Anything else is forbidden, including backend/**, .env, frontend/.env.local, frontend/src/**, and any docs/plans/** file.

Hard rules:
- Never print, log, or write SHOOTINGSTAR_ADMIN_KEY or any value from .env. Preflight prints only set/match booleans.
- Backend must run with backend/.venv/Scripts/python.exe (Python 3.14 from python.org). Do not use any other Python.
- Test database is the MAIN database. Do not create a test DB, do not run migrations, do not delete data.
- Default config must exclude tests tagged @real-gemini (grepInvert). Never run npm run e2e:gemini.
- Do not run the dev servers on ports 8000 or 3000; the user's own servers may be using them.
- Do not commit or push. Do not change plan status.
- For manual verification set E2E_SNAPSHOT_ID=61da7964edb30fbff8de9add491e090a2c7738b41ecc1b048570b5dd578eb8e8 on the command line only; do not write it into any file.

Acceptance (run them and paste the raw output):
- cd frontend && npx playwright test --list  (exit 0)
- cd frontend && npm run typecheck  (exit 0)
- preflight with a deliberately wrong SHOOTINGSTAR_ADMIN_KEY in the shell: stops, prints no secret value
- preflight with port 8100 occupied: stops and names port 8100
- after a run, nothing is left listening on 8100 or 3100

Finish with: Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT + 1-2 lines, files changed, raw command outputs, and what you could not run.
