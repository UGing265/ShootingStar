Lead: verify_stage still has false positives. Real batch (50 jobs, snapshot 9847f2ab, Feb 2025): 20/51 jobs flagged invalid, but Lead inspected every issue and found NO real fabrication. Patterns:
1. Truncation: feature -0.1595586, Gemini wrote -0.159 (truncated, not rounded). Accept a number if it equals the value rounded OR truncated to the written decimals (tolerance = 1 unit of the last written decimal).
2. Sign dropped after a direction word: "mức giảm 0.6073%" for -0.60730865. Accept abs(number) == abs(value) within tolerance.
3. Reference levels: "RSI14 dưới 50" (50 = RSI midpoint). Ignore common reference levels when the reason cites an RSI feature: 30, 50, 70; and 0 for any feature ("âm"/"dương" comparisons). Also ignore a number right after an indicator name with a space, e.g. "EMA 20", "EMA 50", "RSI 14" (check "20" was flagged 3 times, likely this).
Keep flagging: unknown feature_id, numbers matching no cited value under these rules.
Then add a small CLI or one-off function? NO, YAGNI: do not rewrite stored envelopes. Just show: re-run verify() on all stored forecast-6h-v1 answers (read-only query) and print how many become valid and list remaining issues with context. Add 3 tests for the 3 patterns in backend/tests/test_verify_stage_tolerance.py (new file you own).
Files you own: backend/shootingstar/application/external_analysis/stages/verify_stage.py, that new test file. pytest must stay green. No commit/push.
End with: Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT + remaining-issue list.
