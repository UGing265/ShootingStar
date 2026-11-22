# Phase 01 — Backend cleanup

Owner: BackendCleanup. Scope: `backend/`, mentions trong README/docs.

## Bước
1. Map hai contract báo cáo: `/replay/jobs` và `/external-analysis/jobs`; giữ mọi module chúng cần.
2. Xoá training, baselines, evaluation, signals, patterns, lessons, research_agent, routes/CLI/ORM/test liên quan.
3. Replay không dùng `CalibratedLogisticRegressionModel`.
4. Không drop bảng DB, không chạy migration.

## Nghiệm thu (cần output thật)
- `pytest backend/tests` xanh
- `shootingstar --help` chạy được
- `import shootingstar.api.app` OK
- Báo danh sách route còn lại + module đã xoá

Trạng thái: đang thực hiện.
