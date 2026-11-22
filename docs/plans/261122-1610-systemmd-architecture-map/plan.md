# Bản đồ kiến trúc `docs/systemmd/`

**Trạng thái:** đã viết xong, chưa commit. Phase 07 xong; chưa commit.

## Mục tiêu

`docs/systemmd/` trả lời được: backend có kiến trúc gì, luồng nào, code ở đâu, có bao nhiêu API, bảng nào; frontend có cấu trúc thư mục gì, công nghệ gì, trang và proxy nào. Một bản đồ tổng thể cho người mới đọc, không phải runbook hay nhật ký.

## Quyết định đã chốt với user

- Chờ phase 07 xong rồi mới viết (không tiếp quản giữa chừng).
- Phần chạy lệnh, cài đặt, E2E không để trong thư mục `docs/backend/` và `docs/frontend/`. Chuyển thành hai file phẳng `docs/run-backend.md` và `docs/run-frontend.md` (bỏ hai thư mục), sửa mọi link trỏ tới. Chỉ làm sau khi phase 07 xong vì phase 07 đang sở hữu `docs/backend/README.md`. `systemmd` chỉ là bản đồ kiến trúc, trỏ sang hai file này khi cần lệnh.

## Nguồn dữ liệu

Chỉ đọc code thật của trạng thái sau phase 07 (đánh dấu rõ là HEAD hay working tree khi viết). Không ghi phần đang refactor dở thành chuẩn. Mục nào chưa kiểm chứng ghi `[CHƯA KIỂM CHỨNG]`.

## Dàn bài

| File | Nội dung |
|---|---|
| `README.md` | Mục lục, sơ đồ tổng thể (browser, Next.js, FastAPI, DB, Parquet, Binance, Gemini), công nghệ và phiên bản |
| `backend/01-layers-and-dependencies.md` | Tầng, quy tắc phụ thuộc, bảng module theo thư mục (1 dòng mỗi module) |
| `backend/02-modules-and-flows.md` | Luồng ingestion, replay, báo cáo Gemini, trade watch (sequence), job nền |
| `backend/03-persistence.md` | Bảng DB (tên, vai trò, khoá chính), Parquet, raw, simulations, Alembic; link tới `database-schema.dbml` thay vì chép cột |
| `backend/04-api-catalog.md` | **Bảng đầy đủ mọi route**: method, path, router, mô tả, mã trả, gate admin; tổng số route tính lại từ code |
| `backend/05-cli-config-tests.md` | Lệnh CLI, biến môi trường, danh sách file test và phạm vi |
| `frontend/01-architecture-and-folders.md` | Cây thư mục `frontend/src`, công nghệ (Next 16, React 19, CSS thuần, Canvas), quy tắc features |
| `frontend/02-routes-and-data-flow.md` | Trang, proxy `app/api/**`, `api-client`, localStorage, chart, UTC+7 |

## Gate nghiệm thu

- Số route trong `04-api-catalog.md` khớp lệnh đếm decorator `@router.*` trong `backend/shootingstar/api/` (chạy lại, ghi lệnh).
- Mọi đường dẫn file và tên hàm nhắc tới tồn tại (grep từng cái).
- Số proxy và trang frontend khớp `find frontend/src/app`.
- Không chép lại cột bảng hay runbook; link sang `docs/database-schema.dbml` và README.
- Đối chiếu `AGENTS.md` và `governance.md`; sửa dòng nào mâu thuẫn.
- Chưa commit nếu user chưa xác nhận.

## Sở hữu file

Chỉ `docs/systemmd/**`, hai file `docs/run-*.md` mới (chuyển nội dung từ hai README cũ rồi xoá thư mục cũ), và link hiện hành ở `AGENTS.md`, `docs/README.md`, `README.md`. Không sửa hàng loạt lịch sử `docs/plans/**` chỉ vì còn đường dẫn cũ. Không đụng code.
