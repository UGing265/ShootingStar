AMENDMENT 2 to brief-omp-phase-01.md. Lead independently ran your checks. Passed: --list --pass-with-no-tests exit 0, typecheck exit 0, wrong-key preflight (prints booleans only), stderr "pipe" present, tsconfig diff empty. Two problems remain. Same hard rules as before.

1. next-env.d.ts side effect (you did not report it). After your run, `git diff -- frontend/next-env.d.ts` showed Next rewrote both imports from `./.next/types/...` to `./.next-e2e/dev/types/...`. Lead already restored it with `git restore`; baseline was clean. If `.next-e2e` is deleted the user's typecheck breaks. Required fix (frontend/next-env.d.ts is now in your allowed files, for restoring only):
   - snapshot the file content before webServers start and write it back after the run, including when the run fails or is interrupted. Use globalTeardown (and keep preflight as globalSetup). If Playwright starts webServers before globalSetup, take the snapshot at config-module load time instead; read the file once and restore in globalTeardown.
   - do not edit the file's imports permanently; do not touch frontend/.next or frontend/tsconfig.json.
   - verify: run `npx playwright test --pass-with-no-tests`, then `git diff -- frontend/next-env.d.ts frontend/tsconfig.json` must be empty. Run it twice. Also verify after an interrupted/failed run (e.g. port 8100 occupied).

2. Occupied-port check must not hang. Verify with a real HTTP server on 127.0.0.1:8100 that answers 200 (for example `node -e "require('http').createServer((q,r)=>r.end('x')).listen(8100,'127.0.0.1')"` in the background), then run `npx playwright test --pass-with-no-tests`. It must stop quickly, name 8100 in the message, exit non-zero, and leave nothing listening on 3100. Kill your blocker server after. Report raw output. If Playwright starts webServers before globalSetup, say so and say which component produces the message.

Do not touch ports 3000 or the user's frontend/.next. Do not commit.

Finish with Status line + files changed + raw outputs of: both git diff checks, the occupied-port run, listeners on 8100/3100 afterwards.
