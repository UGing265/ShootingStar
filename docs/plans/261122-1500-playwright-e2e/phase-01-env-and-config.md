# Phase 01 — Môi trường và cấu hình Playwright

Worker: omp terra (`--model gpt-6.1-terra --effort high`). Không commit/push.

## Goal
`npx playwright test` tự bật backend và frontend ở cổng riêng, chạy được một spec rỗng-hợp-lệ, và fail rõ ràng khi môi trường sai.

## Files được sửa
- `frontend/package.json`, `frontend/package-lock.json` (thêm devDependency `@playwright/test`, script `e2e`, `e2e:gemini`).
- `frontend/playwright.config.ts` (mới).
- `frontend/e2e/preflight.ts` (mới).
- `frontend/.gitignore` (thêm `test-results/`, `playwright-report/`, `e2e/.created-jobs.json`).
- `docs/frontend/README.md` (thêm mục chạy E2E).
- `frontend/next.config.mjs`: chỉ thêm `distDir: process.env.NEXT_DIST_DIR || ".next"`; e2e dùng `NEXT_DIST_DIR=.next-e2e` để không đụng `.next` và lock của `next dev` ở cổng 3000. Thêm `.next-e2e/` vào `frontend/.gitignore`.

## Files cấm sửa
Mọi file khác, kể cả `backend/**`, `.env`, `frontend/.env.local`, `frontend/src/**`.

## Việc cần làm
1. Cài `@playwright/test` làm devDependency; chạy `npx playwright install chromium`.
2. `playwright.config.ts`:
   - `baseURL` `http://127.0.0.1:3100`.
   - `webServer` thứ nhất: backend, lệnh `backend/.venv/Scripts/python.exe -m uvicorn shootingstar.api.app:app --host 127.0.0.1 --port 8100` từ thư mục gốc repo, chờ `http://127.0.0.1:8100/health` trả 200, `reuseExistingServer: false`.
   - `webServer` thứ hai: frontend `next dev -p 3100` với `SHOOTINGSTAR_API_URL=http://127.0.0.1:8100`, chờ cổng 3100.
   - `grepInvert: /@real-gemini/` mặc định; project hoặc script `e2e:gemini` chỉ chạy `@real-gemini`.
   - Chromium một worker (`workers: 1`) vì ghi vào cùng DB.
3. `e2e/preflight.ts` (globalSetup): kiểm tra, KHÔNG in giá trị bí mật:
   - `process.env.SHOOTINGSTAR_ADMIN_KEY` nếu đã set thì phải bằng giá trị trong `.env`, nếu lệch: dừng, in `set: true, match: false` kèm hướng dẫn bỏ biến.
   - Cổng 8100 và 3100 đang trống, nếu không: dừng, nói rõ cổng nào.
   - `E2E_SNAPSHOT_ID` có mặt (mặc định đọc từ biến môi trường), nếu thiếu: dừng với thông báo.
4. Backend phải dùng `backend/.venv`, không dùng bản uv 3.12 (chết TLS khi gọi HTTPS).
5. Ghi vào `docs/frontend/README.md`: cách chạy `npm run e2e`, `npm run e2e:gemini`, biến `E2E_SNAPSHOT_ID`, cảnh báo test ghi job vào DB chính.

## Invariants (`AGENTS.md`)
- Không lộ `SHOOTINGSTAR_ADMIN_KEY`, chuỗi kết nối DB, đường dẫn nội bộ trong log hay thông báo lỗi.
- Không mock dữ liệu trong production flow.
- `frontend/.env.local` vẫn git-ignore.

## Acceptance (Lead tự chạy lại)
- `cd frontend && npx playwright test --list --pass-with-no-tests` exit 0 (phase này chưa có spec; `--list` trần exit 1 `No tests found`).
- `cd frontend && npx playwright test --pass-with-no-tests` bật cả hai server ở 8100/3100, không chạy test, exit 0, không in bí mật; cổng 3000 và `frontend/.next` không bị đụng.
- `webServer` dùng `stderr: "pipe"` (không `"ignore"`) để thấy lỗi khởi động.
- `git diff -- frontend/tsconfig.json` rỗng sau mỗi lần chạy (kể cả fail). Next có thể tự thêm include cho `.next-e2e`; `frontend/tsconfig.json` nằm trong phạm vi được sửa CHỈ để khôi phục, cùng quy tắc có điều kiện như `next-env.d.ts` (chỉ khôi phục khi file còn chứa `.next-e2e`).
- `git diff -- frontend/next-env.d.ts` rỗng sau mỗi lần chạy `npx playwright test` (kể cả khi lần chạy fail). Next tự ghi file này trỏ sang `.next-e2e`. `globalTeardown` chỉ khôi phục khi file hiện tại vẫn chứa `.next-e2e` (do e2e ghi); nếu nội dung đã khác (dev server 3000 ghi đè), KHÔNG ghi đè. Giới hạn đã biết: trong lúc e2e chạy, file này tạm trỏ sang `.next-e2e`, nên không chạy `tsc`/mở editor cho `frontend/` song song; ghi chú này vào `docs/frontend/README.md`.
- Ca cổng 8100 bị chiếm kiểm bằng một HTTP server thật trả 200 ở 8100 (không dùng socket câm, vì probe `/health` sẽ treo). Kết quả mong đợi: Playwright hoặc preflight dừng nhanh, thông báo nêu 8100, exit khác 0, không treo.
- `cd frontend && npm run typecheck` exit 0.
- Chạy preflight với biến shell `SHOOTINGSTAR_ADMIN_KEY` cố tình lệch: dừng, không in giá trị.
- Chạy với cổng 8100 đang bị chiếm: dừng, nêu cổng 8100.
- Khi `npx playwright test` chạy xong thì không còn tiến trình uvicorn/next nào giữ 8100/3100.

## Kết thúc bằng
`Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT` + 1-2 dòng, kèm output lệnh nguyên văn và điều chưa chạy được.
