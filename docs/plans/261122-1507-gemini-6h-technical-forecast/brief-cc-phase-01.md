Use ck:cook to implement this task (if you lack the cook skill: plan, implement, verify, no mocks).

Task: Phase 01 of plan docs/plans/261122-1507-gemini-6h-technical-forecast/plan.md — add a baseline-rules section to the root README.md.
Read first: AGENTS.md (mandatory rules), docs/plans/261122-1507-gemini-6h-technical-forecast/phase-01-readme-baseline-rules.md (full spec, includes the exact example table numbers and sources).

Files you own (modify ONLY this): README.md (root). Add one new section; do not change other sections.

Acceptance criteria:
- Section in Vietnamese explains: at each time t, three predictors guess whether price at t+6h is higher or lower than purchase price P: rule "luôn TĂNG", rule "theo đà 6h" (close(t) > close(t-6h) => TĂNG else GIẢM), and Gemini.
- States the two rules run independently, do not look at Gemini, computed by Python, no API cost.
- States |move| < 1% vs P = đi ngang, not scored. Gemini only has value if it clearly beats both rules over hundreds of samples.
- Example table with 3 rounds exactly as in the phase file (totals 2/3, 3/3, 2/3).
- Note: samples before 2025-02 may be memorized by Gemini (knowledge cutoff 01/2025), counted separately.
- Two source links from the phase file.
- No em dash or en dash characters in the text. Valid markdown table.

Constraints: YAGNI/KISS. Do NOT commit or push. Do not touch any other file.
End your reply with: Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT + 1-2 line summary.
