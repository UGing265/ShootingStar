# Backend — FastAPI read contracts

## Phạm vi

Chi tiết B1 trong [`plan.md`](plan.md). Nguồn hiện có: `src/shootingstar/api/app.py` và models/repositories tại `src/shootingstar/adapters/db/`. Đây là kế hoạch, chưa thực thi.

## Tiền điều kiện A0 từ agent audit

Trước khi đưa quality/report/pattern/signal ra API, xử lý và xác minh các mục A0 trong [`plan.md`](plan.md): requested-window/duplicate/reject & availability, purge 1m/5m và baseline fit trên train, full checksum + lỗi lưu DB, persisted rule + mọi hit, model-driven signal và maturity chỉ sau nến đóng/có sẵn. Đây là **kế hoạch**, audit tĩnh chưa chạy test. Không coi DTO đọc từ bảng trống là chứng minh producer hoạt động.

## Việc cần làm

- [ ] Đóng băng response schema rồi test: `GET /ingestion-runs`, `/snapshots/{id}/quality`, `/snapshots/{id}/candles`, `/experiments/{id}` với toàn bộ splits/reports/baselines/calibration, `/pattern-rules`, `/pattern-rules/{id}/hits`, `/signals/{id}` với review/audit. Giữ `/health`, `/snapshots`, `/experiments`, `/signals`, `/narrative`; tách bạch aggregate tính on-demand với persisted hits.
- [ ] Pagination giới hạn, thứ tự ổn định + cursor; 404/422/503 rõ ràng. Verify snapshot checksum trước đọc file; giới hạn rows/time cho candle drilldown. Không trả raw payload/path/secrets.
- [ ] Trường thiếu dữ liệu thật trả `unavailable`/empty state có lý do; không phát minh gap timestamps, score calibration hay trading profit. Report luôn gắn `experiment_id`, snapshot hash, split/timeframe và test window.
- [ ] Test migrated PostgreSQL cho multi-report, data gap, calibration bins, pattern failure, 3 signal states và review; chạy API tests + full suite; chứng minh DB unavailable không rò URL.

## Gate bàn giao sang Frontend

JSON contract với dữ liệu seeded lấy được từ migrated DB và frontend có thể phân biệt loading/error/empty/unavailable; không chỉ kiểm tra `/docs` hiển thị. Viết `docs/backend/README.md` khi triển khai, không ngay lúc lập kế hoạch.
