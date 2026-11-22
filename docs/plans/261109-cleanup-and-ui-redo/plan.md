# 261109 — Dọn model dư thừa + làm lại UI

## Goal
Bỏ toàn bộ phần "model" phức tạp; chỉ giữ dữ liệu giá, mô phỏng replay, trade plan và báo cáo replay. Làm lại toàn bộ UI.

## Giữ
- Ingestion + snapshots (Lịch sử giá).
- Replay simulation (`application/replay.py` SimulationJobManager: create/vote/reveal).
- Trade plan: `domain/trade_plan.py`, `entry_strategy`, `trade_watch`, `barrier_evaluation`, `binance_market_events`, `trade_plan_routes`.
- Báo cáo replay: cả hai contract — `/replay/jobs` (vote/reveal) và `/external-analysis/jobs` (Gemini report); Backend worker phải map trước khi xoá.
- `docs/plans/` giữ nguyên.

## Xoá (code + route + CLI + test + UI)
Self-trained model (training, baselines, evaluation, signals, patterns, experiments), lessons, research agent, các trang patterns/signals/research/lessons.
Bảng DB hiện có giữ nguyên, không drop, không chạy migration.

## UI
Trang giữ: Tổng quan, Lịch sử giá, Mô phỏng (Replay), Báo cáo, Giới thiệu. Thiết kế lại; cập nhật `docs/DESIGN.md` nếu đổi design system. Chart giữ zoom/pan/click-vs-drag, UTC+7.

## Phases
1. Backend cleanup — gate: `pytest backend/tests` xanh, `shootingstar --help`, app import OK.
2. Frontend delete + redo — gate: `npm run typecheck && npm run build`, trang render.
3. Docs sync + review.

## Trạng thái
Chưa hoàn tất: chờ kết quả chạy thật của phase 1–2.

## Invariants
- Không dữ liệu giả; thiếu dữ liệu hiển thị `Chưa có dữ liệu`.
- Không lookahead: replay chỉ dùng nến `available_at <= t`.
- Frontend không tính lại metric; chỉ gọi FastAPI từ server.
- Chart: wheel zoom, drag pan, click≠drag, hiển thị UTC+7.
- Không commit/push khi chưa có xác nhận user.

## Ownership
- Phase 1: BackendCleanup (chỉ `backend/`, README/docs mention).
- Phase 2: FrontendRedo (chỉ `frontend/`; bám `docs/DESIGN.md` hiện có, chỉ bổ sung nhỏ nếu cần ghi pattern mới). Chi tiết: `phase-02-frontend-redo.md`.
- Phase 3: Lead (docs sync, review kết quả).
