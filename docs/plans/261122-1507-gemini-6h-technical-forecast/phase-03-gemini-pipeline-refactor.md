# Phase 03 — Pipeline Gemini 1 call + tách stage

**Worker:** omp terra · **Phụ thuộc:** phase 02 · **Trạng thái:** pending

## Hiện trạng
- `service.py:139` `run_pipeline` ~210 dòng, 5 stage (feed → analyze_preliminary → grounded_research → pattern match → synthesize) = 3 call Gemini.
- `adapters/model_api/gemini_adapter.py` 831 dòng: HTTP + key rotation + retry 503 + prompt + mock.
- `research_agent.py:28` query hardcode `"{pattern} definition criteria rules Steve Nison"`.

## Thiết kế mới
```
run_forecast_pipeline(job):
  digest   = feed_stage(job)                 # phase 02 build_technical_digest + agreement + baselines + flag
  answer   = analyst_stage(digest, job)      # 1 call Gemini, JSON schema
  checked  = verify_stage(answer, digest)    # feature_id tồn tại, giá trị trích dẫn khớp → cờ
  envelope = report_stage(job, digest, checked)  # dict lưu evidence_envelope_json
```
- Output schema Gemini: `{direction: "UP"|"DOWN", confidence: "LOW"|"MEDIUM"|"HIGH", reasons: [{feature_ids: [..], text}], risks: [text]}`. `response_mime_type=application/json` + responseSchema.
- Prompt (file riêng `prompts/forecast_6h_prompt.py`, có `PROMPT_VERSION`): vai trò, chỉ dùng số trong digest, cấm bịa số/sự kiện, bắt buộc chọn UP hoặc DOWN, rubric:
  - HIGH: xu hướng 1h và 4h cùng chiều VÀ có xác nhận volume/động lượng, không tín hiệu ngược mạnh.
  - MEDIUM: đa số tín hiệu cùng chiều nhưng có 1–2 tín hiệu ngược.
  - LOW: tín hiệu trái chiều/không rõ; vẫn phải chọn hướng nghiêng hơn.
  - Không đưa ngày tháng tuyệt đối vào prompt nếu không cần (giảm recall); giá giữ nguyên.
- Envelope `protocol_version: "forecast-6h-v1"`: `digest`, `answer`, `verification`, `agreement_score`, `baselines {always_up, momentum_6h}`, `possible_memorization`, `horizon_minutes`, `flat_threshold_pct`, `prompt_version`, token usage.
- `job.direction` chỉ UP/DOWN cho job mới; ABSTAIN legacy vẫn đọc được.
- Gemini lỗi schema/timeout → status lỗi rõ ràng (không dự báo dự phòng giả).
- `reveal_outcome` dùng `forecast/outcome.py` (ngưỡng 1%, horizon từ job).
- `horizon_minutes` mặc định 360 cho job mới (request vẫn truyền được).

## File
- Tạo: `external_analysis/stages/{feed_stage,analyst_stage,verify_stage,report_stage}.py`, `external_analysis/forecast_pipeline.py` (orchestrator mỏng), `adapters/model_api/gemini_transport.py` (HTTP + key rotation + retry 503, tách từ adapter), `adapters/model_api/prompts/forecast_6h_prompt.py`.
- Sửa: `service.py` (gọi pipeline mới, bỏ code stage cũ), `contracts.py` (DTO mới, giữ field legacy optional), `gemini_adapter.py` (còn mỏng hoặc thay bằng `gemini_forecast_client.py`), `api/external_routes.py`, `api/schemas.py`.
- Xoá: `research_agent.py`, các hàm `analyze_preliminary`, `grounded_research`, `synthesize_evidence_report`, `_generate_mock_*` khỏi production; mock chuyển `backend/tests/fakes/` (phase 04 dùng). `context.py` phần build_context_a/b/feed_contract nếu không còn caller (grep trước khi xoá).
- `report_presentation.py`: cập nhật cho envelope mới, giữ render legacy nếu FE/API còn đọc job cũ.

## Ràng buộc
- Mỗi file pipeline < 200 dòng. Không đổi DB schema. Không đổi admin gate trong routes.
- Grep mọi caller trước khi xoá (`replay.py`, `replay_routes.py`, CLI).

## Nghiệm thu
- 1 job retrospective thật (admin, `SHOOTINGSTAR_EXTERNAL_API_ENABLED=true`) trên snapshot dài: đúng 1 request Gemini, envelope đủ field.
- `pytest backend/tests/test_api_and_ui.py` xanh (sửa test vỡ do contract → báo Lead, phase 04 làm phần test).
- `grep -rn "grounded_research\|research_agent\|Steve Nison" backend/shootingstar` rỗng.
