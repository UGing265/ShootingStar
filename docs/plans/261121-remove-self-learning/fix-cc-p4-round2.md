Use ck:cook. Role: Implementer, round 2 fix, same ownership as before (frontend/**, README.md, docs/** except docs/plans/**, docs/systemmd/**, docs/database-schema.dbml). Do not touch backend/**. Do not commit or push.

Reviewer (omp) found two concrete defects. Fix exactly these, nothing else.

1. frontend/src/features/replay/use-replay-session.ts lines 235-236 and 273-274: the reveal calls use requestJson without a body, so the helper at line 17 (method: body === undefined ? 'GET' : 'POST') sends GET. Both API routes (frontend/src/app/api/replay/jobs/[id]/reveal/route.ts and frontend/src/app/api/external-analysis/jobs/[id]/reveal/route.ts) export only POST. Make the reveal calls POST (pass an explicit body such as {} or add an explicit method option to requestJson, whichever matches how vote is called at ~lines 255-265). Do not change the engine default at line 76. Do not change any other behavior.
2. frontend/src/app/(work)/about/page.tsx lines 10, 15, 20, 25 (tag strings 'Cảnh N — ...') contain an em dash. UI copy must not use em or en dashes. Replace with a colon or plain hyphen. Check the rest of that file and any text you added in P4 for em/en dashes.

Acceptance: `npm run typecheck` in frontend/ exits 0. `npm run build` may still exit 1 with the known Next 16.4.0 SecurityFatalError; quote the line and do not try to fix it. Show the final lines changed (file:line, before and after). Do not claim the flow works in a browser unless you ran it.

End with exactly: Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT + 1-2 line summary.
