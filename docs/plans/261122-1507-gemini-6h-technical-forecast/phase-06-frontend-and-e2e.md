# Phase 06 — Giao diện + cập nhật e2e

**Worker:** command-code flash · **Phụ thuộc:** 05 (Playwright e2e đã xong, sửa spec thoải mái) · **Trạng thái:** pending

## File sở hữu
- `frontend/src/features/replay/external-types.ts`, `replay-result.tsx`, `replay-analysis.tsx` (nếu cần horizon 6h)
- `frontend/src/features/report/report-view.tsx`, `labels.ts`
- `frontend/src/shared/format.ts`
- `frontend/e2e/gemini.spec.ts` (sửa assertion theo UI mới)
- Có thể tạo `frontend/src/features/report/scoreboard-card.tsx`, `confidence-badge.tsx`

## Việc
- Types: envelope `forecast-6h-v1` (digest, answer, verification, agreement_score, baselines, possible_memorization); giữ type legacy (ABSTAIN, research) optional để job cũ không vỡ.
- Report: hiện hướng + confidence (nhãn "model tự đánh giá, chưa kiểm chứng"), điểm đồng thuận "x/y chỉ số cùng chiều", danh sách lý do kèm feature (tên + giá trị từ digest, không hiện id thô), cờ verification, banner `possible_memorization`. Bỏ mục nguồn search cho job mới.
- Replay result: so Gemini / luôn TĂNG / theo đà với outcome (FLAT = "đi ngang, không chấm").
- Scoreboard card: gọi API server-side qua `api-client.ts` (không tính lại metric ở client), hiện bảng accuracy + n + khoảng tin cậy.
- Giờ hiển thị UTC+7. Theo `docs/DESIGN.md`. Không em/en dash.

## E2E Gemini (user chốt 2026-11-22)
- Production cấm mock. `gemini.spec.ts` mặc định: mở job Gemini thật đã lưu trong DB (job `1dfa822c…`, forecast-6h-v1) + 1 job legacy (30m/ABSTAIN), kiểm render. Không gọi Gemini, không giả lập.
- Tạo job mới chỉ trong test tag `@real-gemini`, chạy tay `npm run e2e:gemini`.
- Id job lấy qua biến `E2E_FORECAST_JOB_ID` / `E2E_LEGACY_JOB_ID` (mặc định là id thật hiện có), không hardcode rải rác.

## Nghiệm thu
- `npm run typecheck` + `npm run build` xanh.
- `npx playwright test` xanh (gồm gemini.spec.ts đã cập nhật).
- Mở 1 job legacy + 1 job mới, cả hai render.
