---
status: completed
branch: feat/playwright-e2e-and-cleanup
blockedBy: []
blocks: []
source: docs/plans/261122-1507-gemini-6h-technical-forecast/reports/brainstorm-261122-1419-gemini-6h-technical-forecast.md
---

# 261122-1507 — Gemini dự đoán xu hướng 6h, chấm điểm vs baseline

## Goal
Tại t, Gemini 2.5 Flash đoán giá t+6h UP/DOWN (bỏ ABSTAIN) kèm confidence LOW/MED/HIGH, dựa trên digest kỹ thuật Python tính (đa khung). 1 call Gemini/job. Chấm điểm vs 2 baseline ("luôn TĂNG", "theo đà 6h") để biết Gemini có giỏi thật không. Tách pipeline thành stage nhỏ (<200 dòng/file).

## Quyết định đã chốt (user)
- Horizon 6h (360 phút, tham số). FLAT nếu |close(t+6h) − P| / P < 0.5% → không chấm. (Đo thật 2.581 mốc 6h 02/2025–11/2026: trung vị |Δ| 0.49%; 1% loại 75.9%, 0.5% loại 50.7%; user chốt 0.5% ngày 2026-11-22.)
- Snapshot dài: `9847f2ab35…` (1m, 2025-02-01 → 2026-11-22, 949.380 nến, thiếu 1).
- Input: nến 1m gộp → 1h × N ngày (N tham số, mặc định 14, thử 7/14/30) + 15m × 24h. Không gửi 1m.
- Chỉ báo tự tính bằng numpy (không thêm pandas/TA-Lib). Không kho kiến thức, không Google grounding.
- Confidence: rubric trong prompt + `agreement_score` (Python) + bảng đối chiếu. Không %, không LLM verifier.
- Cờ `possible_memorization` khi t < 2025-02-01 (cutoff gemini-2.5-flash 01/2025).
- Dữ liệu: tải thêm nến 1m từ 2025-02-01 tới nay bằng `fetch-history`.
- Batch CLI: `--limit` (mặc định 50), `--dry-run` (chỉ baseline, không gọi API), resume, dừng khi 429/hết quota.
- Không đổi schema DB: confidence/agreement/baselines/flag lưu trong `evidence_envelope_json`.
- Branch hiện tại `feat/playwright-e2e-and-cleanup`. Không commit/push khi user chưa xác nhận.

## Invariants
- Chỉ nến có `close_time_ms <= t` vào digest (không lookahead). Test bắt buộc.
- Job cũ (30m, ABSTAIN, hypothesis/research) vẫn đọc được (legacy), không xoá dữ liệu.
- Không in key Gemini/admin ra log/brief.
- Không mock trong production flow; mock chỉ trong `tests/`.

## Phases
| # | File | Worker | Phụ thuộc | Trạng thái |
|---|---|---|---|---|
| 00 | [phase-00-data-prep-and-flat-ratio.md](phase-00-data-prep-and-flat-ratio.md) | Lead | — | done |
| 01 | [phase-01-readme-baseline-rules.md](phase-01-readme-baseline-rules.md) | command-code flash | — | done |
| 02 | [phase-02-forecast-core-pure-python.md](phase-02-forecast-core-pure-python.md) | omp terra | — | done (amend A1-A3 cùng phase 03) |
| 03 | [phase-03-gemini-pipeline-refactor.md](phase-03-gemini-pipeline-refactor.md) | omp terra | 02 | done |
| 04 | [phase-04-backend-tests.md](phase-04-backend-tests.md) | command-code flash | 02 (pure tests), 03 (pipeline tests) | done |
| 05 | [phase-05-scoreboard-and-batch-cli.md](phase-05-scoreboard-and-batch-cli.md) | omp terra | 03 | done |
| 06 | [phase-06-frontend-and-e2e.md](phase-06-frontend-and-e2e.md) | command-code flash | 05 (Playwright plan đã xong, user xác nhận) | done |
| 07 | [phase-07-docs-sync.md](phase-07-docs-sync.md) | command-code flash | 05 | done |

Thứ tự chạy song song an toàn: (00 ∥ 01 ∥ 02) → (03) → (04 ∥ 05) → (06, 07).
Cap: 1 omp + 1 command-code session, tái sử dụng handle.

## File ownership (tách rời)
- omp: `backend/shootingstar/application/external_analysis/**`, `backend/shootingstar/application/forecast/**` (mới), `backend/shootingstar/adapters/model_api/**`, `backend/shootingstar/api/external_routes.py`, `backend/shootingstar/api/schemas.py`, `backend/shootingstar/cli/main.py`.
- command-code: `README.md`, `backend/tests/test_forecast_*.py`, `backend/tests/test_external_analysis.py`, `frontend/src/features/{replay,report}/**`, `frontend/src/shared/format.ts`, `frontend/e2e/gemini.spec.ts`, `docs/backend/README.md`, `docs/external-model-forecast-design.md`.

## Gate nghiệm thu (Lead tự chạy lại)
- `cd backend && .venv/Scripts/python -m pytest` xanh (exit 0).
- `cd frontend && npm run typecheck` + `npx playwright test` xanh.
- `shootingstar forecast-batch --dry-run --limit 20` chạy thật trên snapshot dài, in bảng baseline.
- 1 job Gemini thật 6h: 1 call, envelope có `confidence`, `agreement_score`, `baselines`, reasons trỏ feature_id hợp lệ.
- Không file mới/sửa nào trong pipeline > 200 dòng (`wc -l`).

## Câu hỏi mở
- DB test `shootingstar_test_db` chưa tồn tại → 26 errors + 1 failed có sẵn trước plan. Cần user cho phép tạo DB test để gate pytest xanh.

## Việc sau (user chốt 2026-11-22, làm khi mọi thứ ổn định)
- UI chạy batch: nút "Chạy thêm N mốc" trên giao diện, chạy nền, thanh tiến độ, nút dừng, trần quota. Hiện batch chỉ chạy bằng CLI `shootingstar forecast-batch`.
- Gọi Gemini song song trong batch (nhanh 3-4 lần, cẩn thận quota).
