# Phase 01 — Feed thật và giao giả thuyết cho agent nghiên cứu

## Context / trạng thái

[Plan tổng](plan.md), [Tra nguồn và tiêu chí](phase-02-research-pattern-criteria.md). **Pending; chỉ thiết kế.**

## Điểm tái sử dụng đã đọc từ source

- `context.py:extract_causal_window/build_context_a/build_context_b`: cửa sổ 6h, nến có close + latency <= t, metric được backend tính. Cửa sổ neo vào nến hợp lệ cuối, không cắt máy móc `[t-6h,t]`.
- `patterns.py`: đã có rule Hammer/ShootingStar/Engulfing. `PatternLabService.analyze_pattern` còn dùng nến tương lai để đánh giá forward return: **không gọi đường đánh giá đó làm tool của agent**.
- `GeminiModelAdapter.analyze`/`service.create_analysis_job`: hiện một call và rationale ngắn. Chưa có điều phối nhiều giai đoạn.
- Verifier hiện lọc ID/timestamp/direction; không xác minh nội dung nhận xét, pattern hoặc nguồn web. Đọc source không phải bằng chứng luồng mới đã chạy.

## FeedContract v1

```text
feed_id, feed_version, feed_hash
snapshot_id, snapshot_checksum, symbol, timeframe
prediction_time_t_ms, purchase_price_p, horizon_minutes
context_start_open_time_ms, context_end_close_time_ms, assumed_latency_ms
candles[]: canonical candle_id/open_time_ms/close_time_ms/O/H/L/C/V
coverage: required_span, observed_span, gaps, invalid/duplicate rows, status
features[]: feature_id/value/unit/formula_version/source_candle_ids
```

- Canonical candle ID gắn snapshot + timeframe + open_time_ms; numeric timestamps tiếp tục giữ cho chart hiện có. Hash gồm input/query/recipe version, không phụ thuộc lời AI.
- Mỗi job một snapshot/timeframe đã chọn, không tự tạo multi-timeframe hoặc tổng hợp 1m thành 5m ở frontend. Thiếu 6h/quality gate không đạt: dừng trước provider, trạng thái INSUFFICIENT_HISTORY.
- Feature chỉ từ nến hợp lệ: đặc điểm thân/râu/biên độ, biến động và khối lượng theo công thức có version. Tái dùng metric B hiện có trước khi thêm công thức; không để LLM tự tính hoặc FE tính lại.
- Phân biệt giá cuối quan sát và giá mua nhập P. Tín hiệu tăng từ giá hiện tại chưa chắc có nghĩa giá cuối vượt P.
- Feed không có nến sau t, outcome, vote, nhãn chấm tương lai hoặc metric forward return. Không gửi toàn snapshot để model tự bỏ tương lai.
- Lưu hash/bounds/recipe và snapshot bất biến, feature evidence đủ truy lại nguồn. Không public file_path/artifact_path hoặc secret. Persist artifacts cần thiết tại backend, không dump raw sách/context có bản quyền xuống browser.

## Agent phân tích sơ bộ

Agent này nhận feed, không có web tool, vote/outcome hoặc quyền kết luận cuối. Nhiệm vụ đọc quan sát, nêu giả thuyết có thể kiểm tra và giao nghiên cứu:

```text
hypothesis_id, feed_id/hash
observations[]: claim_id, mô tả, feature_ids, candle_ids
candidates[]: tên mẫu ứng viên, candle_ids, vì sao đáng kiểm, bối cảnh chưa rõ
- Sửa `backend/shootingstar/application/patterns.py`: thêm hàm chuyên biệt `evaluate_pattern_diagnostics(candles: List[Candle], target_index: int)` nhận **danh sách nến đã cắt tại t (không có bất kỳ nến tương lai nào)**; cấm hoàn toàn việc gọi `PatternLabService.analyze_pattern` trong pipeline vì class này chứa logic tính forward return qua tương lai.
```

- Bản A gửi nến/feature source đầy đủ trong window; B gửi metric/tail có provenance và cho research/matcher đọc feed canonical khi cần. Tóm tắt không được thay thế số liệu gốc khi đối chiếu.
- Không bỏ giả thuyết đối lập chỉ vì analyst thích một tên mẫu; research phải tìm cả điều kiện bác bỏ.
- Không bắt agent trình bày suy nghĩ nội bộ. Chỉ cần luận điểm công khai, bằng chứng/giả thuyết để kiểm tra.
- Bản giao nghiên cứu có cấu trúc, không nhét hướng “chắc chắn giảm” để agent sau chỉ tìm nguồn xác nhận.

## File dự kiến

- Sửa `backend/shootingstar/application/external_analysis/context.py`: đóng gói feed/metadata/provenance, reuse extractor và serializer.
- Sửa `contracts.py`: FeedContract/HypothesisContract và schema version; không dùng ModelPredictionOutput cuối làm sơ bộ.
- Sửa `backend/shootingstar/application/patterns.py` khi cần primitive diagnostics không future; giữ đường evaluation Pattern Lab riêng.
- Sửa `backend/shootingstar/adapters/model_api/gemini_adapter.py`: role preliminary JSON contract, giữ key manager; bỏ một prompt làm mọi vai.
- Sửa `service.py`: ghi feed, chạy preliminary, chuyển artifact cho research; phần orchestration/persist ở Phase 03.
- Regression hành vi trong test external/pattern tương ứng; references/exported callers phải được kiểm trước khi đổi symbol.

## Các bước / gate

1. Chốt schema/version/hash và extractor inputs; kết quả cùng snapshot/params phải truy được cùng feed.
2. Tách matcher/feature khỏi đường forward-evaluation trước khi gọi từ agent.
3. Khóa feed; kiểm input t/P/horizon; tạo preliminary artifact với evidence IDs thuộc feed.
4. Backend xác thực mọi value/ID tham chiếu; số không có tool provenance bị loại khỏi claim đã xác thực hoặc gắn UNKNOWN, không bù bằng câu chuyện.
5. Giao artifact cho research, chưa trả kết luận READY cho UI.

- [ ] Nến sau t thay đổi không ảnh hưởng feed/hypothesis input; hash/provenance kiểm được.
- [ ] Candidate có nến/feature cụ thể, thông tin thiếu và vấn đề cần tra; chưa có hướng cuối.
- [ ] Không gọi forward-return tool, không nhìn vote/outcome, không tự thêm timeframe.
- [ ] Thiếu lịch sử dừng trước call và hiển thị lý do thật.

## Rủi ro

“Có feed” không có nghĩa dữ liệu sạch. Gate là eligibility, coverage và provenance, không chỉ số lượng nến. Analyst vẫn có thể đọc sai; matcher và đối chiếu nguồn tiếp theo phải bắt được điều đó.
