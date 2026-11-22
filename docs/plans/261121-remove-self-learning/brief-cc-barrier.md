Use ck:cook. Role: Implementer. Owns backend/shootingstar/application/barrier_evaluation.py, backend/shootingstar/cli/main.py, backend/tests/test_barrier_evaluation.py, docs/**, README.md. Do not commit/push. Do not run alembic or touch the DB.

User order: delete the self-trained barrier model leftovers.

Remove from backend/shootingstar/application/barrier_evaluation.py: EmpiricalMultinomialEstimator, MultinomialProbabilityEstimate (if unused elsewhere), BarrierModelArtifact, BarrierArtifactManager (all methods). KEEP FirstTouchOutcome, BarrierSimulationResult, FirstTouchLabeler (used at application/replay.py:407).
Remove from backend/shootingstar/cli/main.py: subcommands research-entry-strategy, evaluate-entry-strategy, approve-entry-artifact, their handlers (~lines 366-700) and the --train-ratio argument, plus now-unused imports.
Tests: in backend/tests/test_barrier_evaluation.py delete tests of the removed classes and the 3 CLI commands; keep FirstTouchLabeler tests. Delete the file's unused imports.
Docs: grep docs/ and README.md for the 3 command names, EmpiricalMultinomialEstimator, BarrierModelArtifact, BarrierArtifactManager, --train-ratio and remove or fix those mentions (leave docs/plans/** untouched).
First, grep that nothing else (api/, application/, adapters/) imports the removed names; if something does, stop and report.

Acceptance (run and quote):
- `.venv\Scripts\python.exe -c "import shootingstar.api.app, shootingstar.cli.main"` exit 0
- `rg -n "EmpiricalMultinomialEstimator|BarrierModelArtifact|BarrierArtifactManager|research-entry-strategy|evaluate-entry-strategy|approve-entry-artifact|train.ratio" backend README.md docs --glob '!docs/plans/**'` empty
- tests: run from a temp dir that has its own .env with SHOOTINGSTAR_TEST_DATABASE_URL=sqlite:///<tmp>/t.db and SHOOTINGSTAR_DATABASE_URL same value (do NOT edit repo .env): `pytest <repo>/backend/tests/test_barrier_evaluation.py <repo>/backend/tests/test_external_analysis.py -q --rootdir=<repo>`.
End with the line `Status: DONE|DONE_WITH_CONCERNS|BLOCKED` then on its own last line the token CC-BARRIER-END.
