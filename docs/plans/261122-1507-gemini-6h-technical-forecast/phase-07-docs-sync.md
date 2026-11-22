# Phase 07 — Đồng bộ tài liệu

**Worker:** command-code flash · **Phụ thuộc:** 05 · **Trạng thái:** pending

## File sở hữu
- `docs/backend/README.md`: lệnh `forecast-batch`, route scoreboard, biến môi trường cần.
- `docs/external-model-forecast-design.md`: thêm mục "Cập nhật 2026-11-22: horizon 6h, 1 call, bỏ grounding" + nguồn kiểm chứng (copy từ brainstorm report: cutoff 01/2025, Xiong ICLR 2024, Tang & Zhu, Tan NeurIPS 2024 kèm caveat phạm vi, Liu & Tsyvinski).

- `docs/systemmd/**` (user yêu cầu 2026-11-22): đối chiếu với src thật sau phase 06, sửa cho khớp. File đang nhắc Gemini/external_analysis/research/ABSTAIN/30m: `backend/01-layers-and-dependencies.md`, `backend/02-modules-and-flows.md` (luồng mới feed → analyst → verify → report, package `application/forecast/`, bỏ grounding), `backend/03-persistence.md` (envelope `forecast-6h-v1` trong `evidence_envelope_json`, không đổi schema), `frontend/02-data-fetching-and-charts.md` (scoreboard, bỏ mục nguồn search). Kiểm thêm `README.md`, `governance.md`, `backend/04-api-conventions.md` (route scoreboard), `frontend/01-architecture-and-folders.md`. Chỉ ghi điều có trong code; grep tên file/hàm trước khi ghi.

## Nghiệm thu
- Mọi đường dẫn/tên hàm nhắc trong `docs/systemmd` tồn tại (Lead grep lại).
- Lệnh trong docs chạy đúng như ghi (Lead thử `--help`).
- Không hứa độ chính xác; nêu rõ chưa kiểm chứng.
