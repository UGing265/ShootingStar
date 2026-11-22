Use ck:cook to implement this task.

Repo: ShootingStar, branch `dev` (shared; do NOT create a worktree). Read `AGENTS.md` first, then `docs/plans/261121-remove-self-learning/plan.md` (phases P1, P2, P3). Caveman/terse reporting, Vietnamese.

## You own (only these)
`backend/**` and `docs/database-schema.dbml`. Another worker owns `frontend/**`, `README.md`, and `docs/**` except `docs/plans/**` and `docs/database-schema.dbml`. Do not touch those.

## Decisions already made by the user
- Keep in the Gemini report: `ResearchAgent.conduct_job_research` + `research_contract_to_dict` (Google Search grounding), `evaluate_pattern_diagnostics`, `url_validator.py`, trade plan/watch, replay strategy engine.
- Move forward. Do NOT git checkout/stash/restore deleted files. Many files are already deleted on purpose.
- Do not commit. Do not push.
- NEVER run alembic against any DB. PostgreSQL is stopped; do not start it.

## P1: detach lessons from the report pipeline (current state: `import shootingstar.api.app` fails with ModuleNotFoundError ...external_analysis.lessons)
- `application/external_analysis/research_agent.py`: remove `LessonService`/`LessonWorkflowError` import, `lesson_service`, `catalogue_dir`, `_resolve_catalogue_dir`, `count_catalogue_documents`, `search_catalogue`, `orchestrate_research`, `DocumentMatch`. Keep `ResearchAgent(model_adapter=...)` with `conduct_job_research`, and `research_contract_to_dict`. Fix the module docstring.
- `service.py`: drop `approved_lessons`, drop `lesson_service=None` in `ResearchAgent(...)`, drop every `lesson_ids_json` write/read and the `lesson_ids` argument.
- `verifier.py`: drop `approved_lesson_ids` and the lesson-id sanitising block. `contracts.py`: drop `lesson_ids` from `ModelPredictionOutput`.
- `adapters/model_api/gemini_adapter.py`: drop the `approved_lessons` parameters and prompt section, `lesson_ids` in the requested JSON schema and mocks, `extract_lessons_from_text`, `_generate_mock_extracted_lessons`. Keep `grounded_research`.
- Fix `url_validator.py` docstring (no longer "lesson sources").
- `api/app.py`: replace the stale "Pattern Lab" text in the HTML served at `/`, and fix the test that asserts it.
- `cli/main.py` and `README`-visible CLI: nothing else to remove, `scan-patterns`/`research-pattern` already gone.
- Acceptance: `python -c "import shootingstar.api.app, shootingstar.cli.main"` ok; `shootingstar --help` ok; `grep -rniE "lesson" backend/shootingstar` returns nothing (alembic/versions excluded).

## P2: tests
- `backend/tests/test_api_and_ui.py` (imports ~L65-71), `test_persistence.py` (imports L19-29 and the pattern rule/hit test ~L150-180), `test_external_analysis.py` (~L117-135 lesson_ids check, ~L651 `ResearchAgent(lesson_service=None...)`): fix or delete what tests removed behavior. `test_research_agent.py`: delete the catalogue/lesson tests; keep only tests of `conduct_job_research` if any exist.
- Do not add new tests unless report-flow coverage is lost.
- Acceptance: `pytest backend/tests` green; report exact counts.

## P3: migration + DBML (WRITE ONLY, never run)
- New Alembic revision after head `6a7b8c9d0e1f`: drop tables in order `lesson_review_events`, `lesson_revisions`, `lessons`, `pattern_hits`, `pattern_rules`; drop column `external_analysis_jobs.lesson_ids_json`. Faithful `downgrade` recreating them exactly as in the earlier revisions. Check `alembic heads` shows one head using `alembic heads` only (no DB needed); if it needs a DB URL, skip and say so.
- Update `docs/database-schema.dbml` to remove those 5 tables and the column.

## Read-only investigation to report (do NOT change)
`application/barrier_evaluation.py` mixes `FirstTouchLabeler` (used by `replay.py:407`, keep) with `BarrierModelArtifact`, `BarrierArtifactManager`, `verify_approval_gates` (training sample size, Brier score) used by CLI commands in `cli/main.py` (~L370, ~L515, ~L651) and `--train-ratio` (L74). Report which CLI commands call what, which tests cover them (`test_barrier_evaluation.py`), and whether the trained-artifact path is reachable from the API or the report. Do not delete it; the user decides.

## Rules
YAGNI/KISS/DRY, no mocks or stubs, no TODO, follow existing patterns. No UI copy changes. Do not edit `docs/plans/**` except nothing; report only.

End with exactly one line: `Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT` then 1-2 lines of summary, the pytest result, and the barrier_evaluation findings.
