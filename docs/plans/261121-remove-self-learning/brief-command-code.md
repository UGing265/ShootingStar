Use ck:cook to implement this task.

Repo: ShootingStar, branch `dev` (shared; do NOT create a worktree). Read `AGENTS.md` first, then `docs/plans/261121-remove-self-learning/plan.md` (phase P4). Vietnamese, terse.

## You own (only these)
`frontend/**`, `README.md`, and `docs/**` EXCEPT `docs/plans/**`, `docs/database-schema.dbml`, `docs/systemmd/**`. Another worker owns `backend/**` and `docs/database-schema.dbml`. Do not touch those.

## Context
The self-learning features (lessons, Pattern Lab statistics, research/signals pages, self-trained model) are being removed. Already removed from frontend: pages and features `lessons`, `patterns`, `signals`, `research`, the two sidebar entries, the lessons chip in `report-view.tsx`. KEEP: `/report`, `/replay`, `/data`, `/dashboard`, `/about`, the report's `PatternDiagnostic` (candle criteria), research sources (Google grounding) and the `RESEARCHING` / `RESEARCH_INCOMPLETE` status labels. They are NOT self-learning.

## Tasks
1. `README.md` lines ~48-49: remove the "Rule-Based Pattern Lab" section and the `shootingstar scan-patterns` command (CLI removed). Check the rest of the README for other removed commands/features (`research-pattern`, lessons, self-trained model) and fix them.
2. Scan `docs/**` (except the excluded paths) for references to removed things: lessons, Pattern Lab, `scan-patterns`, `research-pattern`, self-trained model, removed pages (`/lessons`, `/patterns`, `/signals`, `/research`). Fix links and text, or add a one-line "đã gỡ" note where the whole doc is about a removed feature (e.g. `docs/self-trained-model-design.md` is already deleted; check dangling links to it). Do not rewrite history docs (`docs/journals`, `docs/reseaching`, `docs/materials`); leave them.
3. `frontend/src`: re-grep for leftover `lesson|patterns page|signals|research page` links or dead imports. Do not change the report/replay behavior.
4. Unused-import hint: `frontend/src/features/report/report-view.tsx` and `shared/ui/sidebar.tsx` have an unused `React` import hint; remove only if typecheck stays green.

## Rules
No em/en dashes in UI copy, never show raw UUIDs. No behavior change in report/replay. Do not commit or push. Do not touch backend.

## Acceptance
`npm run typecheck` in `frontend/` exits 0; `npm run build` result reported honestly (known: Next 16.4.0 security error may appear at the end; quote the exact line). List every file changed.

End with exactly one line: `Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT` then 1-2 lines of summary.
