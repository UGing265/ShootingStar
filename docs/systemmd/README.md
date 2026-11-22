# ShootingStar System Design Reference

Chuẩn thiết kế hệ thống cho ShootingStar. Cấu trúc tài liệu mô phỏng `docs/systemmd/` của RecipeHub, nhưng nội dung viết theo code thật của repo này (Python/FastAPI + Next.js), không sao chép quy chuẩn .NET của RecipeHub.

Nguồn đọc khi viết: `AGENTS.md`, cây thư mục `backend/shootingstar/`, `frontend/src/`, `backend/alembic/versions/`. Mục nào chưa kiểm chứng bằng chạy thật được ghi rõ `[CHƯA KIỂM CHỨNG]`.

## 1. Cấu trúc tài liệu

```text
docs/systemmd/
├── README.md                          # Tổng quan + mục lục (file này)
├── governance.md                      # Quy tắc bắt buộc, checklist tính năng mới
├── backend/
│   ├── 01-layers-and-dependencies.md  # cli/api -> application -> domain/adapters
│   ├── 02-modules-and-flows.md        # ingestion, replay, external analysis, trade plan
│   ├── 03-persistence.md              # DB, Alembic, snapshot Parquet
│   └── 04-api-conventions.md          # REST, job 202, lỗi, bảo mật payload
└── frontend/
    ├── 01-architecture-and-folders.md # Next.js App Router, features, server-only API client
    └── 02-data-fetching-and-charts.md # Proxy route, tương tác chart, UTC+7
```

## 2. Kim chỉ nam

1. Bằng chứng trước, tốc độ sau. Không bịa metric, không P&L thiếu phí và slippage.
2. Không rò rỉ tương lai: dự báo tại thời điểm `t` chỉ dùng nến đã đóng có `available_at <= t`.
3. Python/FastAPI là nơi tính toán duy nhất. Frontend chỉ hiển thị; không tính lại công thức ở client.
4. Frontend gọi FastAPI chỉ từ server qua `SHOOTINGSTAR_API_URL`. Trình duyệt không đọc DB/Parquet.
5. Local-first: chạy được trên Windows/Linux trước khi đóng container.
6. Thiếu dữ liệu thì hiển thị `Chưa có dữ liệu` hoặc `Gated`, không dùng dữ liệu giả.

## 3. Điều hướng

- Quy tắc bắt buộc: [governance.md](governance.md)
- Backend: [layers](backend/01-layers-and-dependencies.md), [modules](backend/02-modules-and-flows.md), [persistence](backend/03-persistence.md), [API](backend/04-api-conventions.md)
- Frontend: [kiến trúc](frontend/01-architecture-and-folders.md), [dữ liệu và chart](frontend/02-data-fetching-and-charts.md)
- Chạy local: [../local-run.md](../local-run.md). Giao diện: [../DESIGN.md](../DESIGN.md). Schema DB: [../database-schema.dbml](../database-schema.dbml).

## 4. Phạm vi bộ tài liệu

Chỉ ghi chuẩn và cấu trúc hiện có. Không đưa kế hoạch, nhật ký, kết quả test, trạng thái dở dang hay bản sao schema/API vào đây (quy tắc lấy từ `docs/systemmd/governance.md` của RecipeHub). Tiến độ và công việc đang làm theo dõi ở `docs/plans/`. Chỗ nào chưa kiểm chứng được đánh dấu `[CHƯA KIỂM CHỨNG]` ngay tại nội dung.
