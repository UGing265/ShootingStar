# Phase 05 — Bảng điểm + chạy hàng loạt

**Worker:** omp terra · **Phụ thuộc:** 03 · **Trạng thái:** pending

## Scoreboard (service + API)
- `application/forecast/scoreboard.py`: đọc job `protocol_version=forecast-6h-v1` (lọc snapshot, horizon, lookback), chấm bằng `outcome.py` (không cần user vote, không ghi đè vote), trả:
  - tổng mốc, số FLAT/UNSCORABLE bị loại;
  - accuracy Gemini, always_up, momentum_6h trên cùng tập mốc chấm được;
  - accuracy theo confidence LOW/MEDIUM/HIGH (n + %);
  - accuracy theo agreement_score bucket;
  - tách 2 nhóm `possible_memorization` true/false.
  - Không tính p-value phức tạp; kèm n và khoảng tin cậy Wilson 95% (công thức đơn giản, ghi docstring).
- Route admin-gated `GET /external-analysis/scoreboard?snapshot_id=&horizon=&lookback_days=` trong `external_routes.py`; schema trong `schemas.py`.

## Batch CLI
- `shootingstar forecast-batch --snapshot <id> --horizon 360 --step-hours 6 --lookback-days 14 --limit 50 [--dry-run] [--start ISO] [--end ISO]`.
- Mốc không chồng: bước 6h; bỏ mốc thiếu lịch sử/thiếu nến t+6h.
- Resume: bỏ qua mốc đã có job cùng (snapshot, t, horizon, lookback, prompt_version).
- `--dry-run`: không gọi Gemini, chỉ tính digest + baselines + outcome, in bảng baseline.
- Dừng sạch khi 429/hết quota/lỗi liên tiếp 3 lần; in số đã xong và lệnh để chạy tiếp.
- In tiến độ + bảng scoreboard cuối.
- Yêu cầu `SHOOTINGSTAR_EXTERNAL_API_ENABLED=true` khi không dry-run.

## Ràng buộc
- File < 200 dòng (CLI tách `cli/forecast_batch_command.py` nếu `main.py` phình). Không đổi DB schema.

## Nghiệm thu
- Lead chạy `--dry-run --limit 20` thật, thấy bảng baseline.
- Lead chạy thật `--limit 5` (user đồng ý quota), scoreboard API trả số khớp CLI.
