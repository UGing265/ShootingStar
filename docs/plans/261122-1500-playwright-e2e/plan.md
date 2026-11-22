# 261122-1500 — Playwright E2E

## Goal
Bộ test Playwright chạy lặp lại được cho các trang `/`, about, dashboard, data, replay, report, để bắt sớm lỗi môi trường và UI (cổng đụng nhau, key cũ, TLS, chọn ngày replay, lỗi Gemini).

## Quyết định của user
- Phạm vi: tất cả trang, gồm báo cáo Gemini.
- **DB: dùng thẳng DB chính (`SHOOTINGSTAR_DATABASE_URL`). Không tạo DB test riêng, không seed riêng.** Snapshot `61da7964…` (30 ngày, 2026-10-22 13:47 đến 2026-11-22 13:46, UTC+7).
- Gemini: giả lập là mặc định; một test Gemini thật chạy tay, nằm ngoài lần chạy mặc định.
- Thợ (theo skill `orca-orchestrator`, chia theo độ khó): phase 1 giao omp terra (cấu hình, môi trường, preflight); phase 2 giao command-code flash (test, `data-testid`). Lead tự kiểm chứng bằng output thật.

## Rủi ro đã nêu (user đã chọn chấp nhận)
1. Replay và external-analysis tạo job trong DB chính. Guardrail: test chỉ dùng `dryRun`/giả lập; không xoá dữ liệu, không migration; test ghi lại id job tạo ra vào `frontend/e2e/.created-jobs.json` (git-ignore) để dọn tay nếu cần.
2. `snapshots[0]` đổi khi tải dữ liệu mới. Guardrail: test chọn snapshot theo `E2E_SNAPSHOT_ID` (cố định), mốc ngày dùng giữa cửa sổ (2026-10-30 12:00).
3. Gemini thật tốn quota. Guardrail: tag `@real-gemini`, bỏ qua mặc định, chạy bằng `npm run e2e:gemini`.
4. Test không gọi Binance. Snapshot đã lưu.

## Invariants
- Không in hay ghi `SHOOTINGSTAR_ADMIN_KEY` ra log; đọc từ `.env`.
- Backend chạy bằng `backend/.venv` (Python 3.14 python.org), không dùng bản uv 3.12.
- Preflight kiểm tra biến shell `SHOOTINGSTAR_ADMIN_KEY` không lệch `.env` (chỉ in set/match, không in giá trị).
- Cổng riêng cho e2e (backend 8100, frontend 3100) để không đụng bản dev đang chạy. DB vẫn là DB chính.
- Không commit/push khi user chưa xác nhận (`AGENTS.md`).

## Phases (omp terra phase 1, command-code phase 2)
1. `phase-01-env-and-config.md`: cài `@playwright/test`, `playwright.config.ts`, `webServer` bật backend + frontend cổng riêng, script `e2e` và `e2e:gemini`, preflight, `docs/frontend/README.md`.
2. `phase-02-tests-and-testids.md`: `data-testid` (chỉ thêm thuộc tính), spec cho các trang, spec replay (ngày trong và ngoài phạm vi, lỗi hiển thị), spec Gemini giả lập, spec `@real-gemini`.

Tuần tự, không song song (cùng ngành file, phase 2 cần config của phase 1). Chỉ một omp và một command-code.

Sở hữu file:
- Phase 1: `frontend/package.json`, `frontend/package-lock.json`, `frontend/playwright.config.ts`, `frontend/e2e/preflight.ts`, `frontend/.gitignore`, `docs/frontend/README.md`.
- Phase 2: `frontend/e2e/**/*.spec.ts`, `data-testid` trong `frontend/src/features/**` và `frontend/src/app/**`.

## Gate nghiệm thu (Lead tự chạy lại)
- `npx playwright test` xanh, exit code 0, cổng 8100/3100, không đụng 8000/3000.
- `npm run typecheck` xanh trong `frontend/`.
- Replay: ngày ngoài phạm vi hiện đúng lỗi; ngày trong phạm vi tải nến và đổi giá.
- Lead tự chạy lại các lệnh trên và đọc diff; không dựa vào báo cáo của thợ.

## Ngoài phạm vi
CI, container hoá, visual regression của chart canvas (chỉ assert text/trạng thái), DB schema, migration.
