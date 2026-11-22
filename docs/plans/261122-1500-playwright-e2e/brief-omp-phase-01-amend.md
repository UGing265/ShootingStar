AMENDMENT to brief-omp-phase-01.md. Lead verified your BLOCKED report: both causes are plan gaps, not your fault. Apply this, same hard rules as before.

1. Root cause of startup failure: the user's own `next dev` (port 3000, PID 22416) holds frontend/.next/dev/lock. A second `next dev` in the same directory collides. Do NOT touch, stop, or restart anything on 3000 and do not delete frontend/.next.

2. Fix (additional file now allowed: frontend/next.config.mjs, ONLY this change):
   - add `distDir: process.env.NEXT_DIST_DIR || ".next"` to nextConfig. Behavior is unchanged when the variable is unset.
   - in playwright.config.ts frontend webServer env set `NEXT_DIST_DIR: ".next-e2e"` (keep SHOOTINGSTAR_API_URL).
   - add `.next-e2e/` to frontend/.gitignore.
   - After a run, check `git diff -- frontend/tsconfig.json`. If Next modified tsconfig.json, revert only that auto-edit (git checkout -- frontend/tsconfig.json is NOT allowed if it had user changes: first run `git diff --stat -- frontend/tsconfig.json` BEFORE your first run and compare). Report what happened either way.

3. Restore diagnostics: set `stderr: "pipe"` (not "ignore") on both webServers. Secrets must not be printed by your own code; do not suppress process output to hide them.

4. Acceptance change: phase 01 has no spec files, so plain `--list` exits 1. Use:
   - `cd frontend && npx playwright test --list --pass-with-no-tests`  (exit 0)
   - `cd frontend && npx playwright test --pass-with-no-tests`  (starts both servers on 8100/3100 via webServer, runs nothing; must exit 0 and print no secret; paste raw output)
   - after that run, nothing listening on 8100 or 3100; 3000 untouched.
   - the other acceptance items (typecheck, wrong-key preflight, occupied 8100 preflight) stay as written. Use E2E_SNAPSHOT_ID on the command line only.

Finish with Status line + files changed + raw outputs + what you could not run.
