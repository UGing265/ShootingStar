# Phase 02 — Test và data-testid

Worker: command-code (`deepseek/deepseek-v4.1-flash`). Chỉ bắt đầu khi Lead đã tự kiểm chứng phase 01 đạt. Không commit/push.

## Goal
Spec Playwright cho các trang `/`, about, dashboard, data, replay, report; giả lập Gemini là mặc định, một test Gemini thật tách riêng.

## Files được sửa
- `frontend/e2e/**/*.spec.ts` (mới).
- `data-testid`: CHỈ thêm thuộc tính trong `frontend/src/features/replay/replay-setup.tsx`, `frontend/src/features/replay/replay-player.tsx` và các file trang/feature liên quan tới trang được test. Không đổi logic, không đổi style.

## Files cấm sửa
`backend/**`, `frontend/playwright.config.ts`, `frontend/package.json`, mọi logic trong `frontend/src/**`, `.env*`.

## Việc cần làm
1. Smoke mỗi trang: mở được, có tiêu đề, không có thông báo lỗi JS ở console, không có `fetch failed`.
2. Trang Mô phỏng (`/replay`), chọn snapshot theo `E2E_SNAPSHOT_ID`:
   - Nhãn dropdown có khoảng ngày và `#<8 ký tự ID>`.
   - Mặc định mở ở cuối snapshot: dòng trạng thái ghi nến đang tải kết thúc ở cuối snapshot.
   - Nhập ngày giữa cửa sổ (`2026-10-30T12:00`): tải nến, giá đổi, dòng trạng thái ghi khoảng nến quanh mốc đó.
   - Nhập ngày ngoài phạm vi (`2026-12-01T12:00`): hiện lỗi `Ngoài phạm vi snapshot`, ô giữ giá trị cũ.
   - Nhập ngày nằm trong 30 phút cuối: bị chặn như ngoài phạm vi.
3. Luồng chiến thuật ở chế độ `dryRun`: chọn thời điểm, bấm "Xem vùng vào lệnh", thấy kết quả hoặc trạng thái rõ ràng; ghi id job vào `frontend/e2e/.created-jobs.json`.
4. Gemini giả lập: chạy luồng báo cáo với `dryRun`, kiểm tra nhãn giả lập hiển thị, không gọi Gemini thật.
5. Một test gắn tag `@real-gemini`: gọi Gemini thật một lần, chỉ chạy bằng `npm run e2e:gemini`; ghi rõ trong comment ngắn là tốn quota.
6. Chart là canvas: kiểm tra bằng text, ô giá, thông báo, không so pixel.
7. Không dùng selector theo text tiếng Việt dài dễ vỡ; ưu tiên `data-testid`, `role`, `aria`.

## Invariants (`AGENTS.md`)
- Múi giờ hiển thị UTC+7.
- Dữ liệu thiếu thì hiển thị `Chưa có dữ liệu`, test không giả lập dữ liệu để đánh lừa.
- Test không in `SHOOTINGSTAR_ADMIN_KEY`, không xoá dữ liệu DB, không chạy migration.
- Không nới, skip hay sửa test cho pass khi lỗi nằm ở code (Lead sẽ trả lại).

## Acceptance (Lead tự chạy lại)
- `cd frontend && npx playwright test` exit 0 ở cổng 8100/3100, không dính `@real-gemini`.
- `cd frontend && npm run typecheck` exit 0.
- `git diff -- frontend/src` chỉ thêm thuộc tính `data-testid`, không đổi logic.
- Cố tình phá một điều kiện (ví dụ bỏ chặn ngoài phạm vi) thì test replay tương ứng phải fail; Lead kiểm tra bằng cách đọc diff, không cần sửa code thật.

## Kết thúc bằng
`Status: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT` + 1-2 dòng, kèm output lệnh nguyên văn và điều chưa chạy được.
