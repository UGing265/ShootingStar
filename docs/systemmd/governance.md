# Governance

Quy tắc bắt buộc cho dev và AI agent. Mâu thuẫn thì `AGENTS.md` thắng.

## Quy tắc

1. Không mock data trong production flow; không giả lập metric.
2. Không lộ `file_path`, `artifact_path`, chuỗi kết nối DB hay khoá API qua endpoint công khai (`/health`, `/snapshots`...).
3. `frontend/.env.local` được git-ignore. `frontend/.env.example` chỉ chứa biến công khai (`SHOOTINGSTAR_API_URL`).
4. Không đổi schema DB ngoài Alembic. Migration phá huỷ (drop bảng/cột) chỉ viết khi user chỉ đạo rõ, kèm `downgrade`, và không chạy lên DB thật khi chưa được duyệt và chưa `pg_dump`.
5. Không commit/push khi chưa có lệnh user. Commit atomic, prefix `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
6. Mọi kế hoạch lớn nằm ở `docs/plans/<yymmdd>-<tên>/plan.md`. Chỉ đánh dấu hoàn tất khi có output chạy thật.
7. Thời gian: backend/DB/Parquet lưu UTC hoặc epoch millisecond; UI hiển thị UTC+7.

## Checklist tính năng mới

- [ ] Logic tính toán nằm ở `application/` hoặc `domain/`, không ở route hay frontend.
- [ ] Dữ liệu chỉ dùng nến có `available_at <= t`.
- [ ] Route mới đăng ký trong `api/app.py`; DTO nằm ở `api/schemas.py` hoặc `application/*/contracts.py`.
- [ ] Trường mới trong DB có Alembic revision và cập nhật `docs/database-schema.dbml`.
- [ ] Có trạng thái thiếu dữ liệu rõ ràng trên UI.
- [ ] Chart mới hỗ trợ zoom (wheel), pan (kéo), click chọn mốc, và phân biệt kéo với click bằng ngưỡng dịch chuyển.
- [ ] Backend: `pytest backend/tests` xanh. Frontend: `npm run typecheck` (hoặc `npm run build`) exit 0.
- [ ] Docs liên quan được cập nhật.

## Điều phối đa agent

Điều phối qua Orca theo skill `orca-orchestrator`: tối đa 1 omp + 1 command-code, file sở hữu tách rời, Lead chỉ báo xong sau khi tự kiểm chứng bằng output thật.
