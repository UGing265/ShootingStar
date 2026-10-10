# Phase 01 — Kế hoạch giá, contract và rủi ro

## Context
[Plan](plan.md). P1; Pending. Long-only, chưa có vị thế. Trả kế hoạch có cơ sở thay vì chỉ dự đoán hướng. Scope không order-placement.

## Thiết kế tối thiểu
Một engine Python thuần, deterministic chọn vùng/điều kiện từ nến đã đóng/khả dụng. LLM chỉ diễn giải candidate/evidence và phản biện; không quyết giá/quantity, không tạo confidence. Pattern diagnosis là một nguồn, không là điều kiện duy nhất.

Khởi đầu với **một setup bounce/reclaim hỗ trợ** để tránh nhiều chiến thuật không thể kiểm chứng: support/resistance từ extrema của lookback trước nến confirmation, không dùng pivot cần nến tương lai. Confirmation = vùng low chạm vùng support đã khóa và nến đóng reclaim trên mốc confirmation đã khóa. Dải chạm/tolerance, các lookback, điểm confirmation được thử trên train/validation, ghi rule version; chưa chốt không kích hoạt BUY. Có thể không có resistance đủ xa → không target, bỏ lượt; không ép tạo TP.

## Files và ownership
Root tuyệt đối cho mọi path: `D:/AShiroru/ProgramCode/Project/Team/ShootingStar/`.
- Create `backend/shootingstar/domain/trade_plan.py`: dataclasses/enums/config bất biến, không adapters.
- Create `backend/shootingstar/application/entry_strategy.py`: candidate selection, barriers, cost/risk gates, estimator hooks (Phase 03 thực hiện cụ thể, không stub nghiệm thu).
- Modify `backend/shootingstar/application/external_analysis/service.py` chỉ nếu tái dùng feed/pipeline để giải thích candidate: không thay kết luận/direction contract job cũ.
- Reuse `application/external_analysis/context.py`, `application/patterns.py`, domain Candle/Timeframe; chỉ thay khi cần shared extractor thật và sau refs/LSP.
- Add behavioral tests theo conventions trong `backend/tests/test_entry_strategy.py` cho boundary/causality/units.

## Contract khóa trước theo dõi
`candidate_id, strategy_version, rule_config_hash, snapshot/feed_hash hoặc live_receipt_refs, decision_time_ms, available_cutoff_ms, evidence_candle_ids, entry_zone, confirmation, invalidation, wait_expires_at_ms, stop_price, target_price, horizon_ms=1_800_000, risk_config, cost_model_version, probability_estimate_ref, reasons/contradictions`.

- Observation decision: `WAIT_CONFIRMATION | SKIP | WATCH_ONLY | BUY_ELIGIBLE`; reason codes cụ thể (`CONFIG_REQUIRED`, `INSUFFICIENT_HISTORY`, `COST_UNVERIFIED`, `PROBABILITY_UNVERIFIED`, `STALE`, `NO_TARGET`, `RISK_EXCEEDED`). Tách khỏi lifecycle.
- Trạng thái vị thế `FLAT | OPEN | EXIT_REQUIRED | CLOSED`; outcome data status `PENDING | OBSERVED | AMBIGUOUS | UNSCORABLE`. Không equate observed price touch với filled order.
- `probability={tp_first, sl_first, timeout, calibration_status, sample_count, period, interval, artifact_version}`; khi chưa valid cả vector null, không biến score thành probability. Không thêm p_up/down proxy.
- Risk config bắt buộc: `max_notional_usdt, max_planned_loss_usdt`, phí thật/assumption được ghi rõ, hạn chờ, max accepted entry deviation, freshness, max event lag. Không secret/DB paths trong DTO.

## Công thức và quy tắc
- Trước entry: `SL < proposed_entry < TP`, tick size từ exchangeInfo; Decimal, lượng từ notional/risk, không float rounding tiền tùy ý.
- Mức support là vùng setup, không đồng nghĩa invalidation: invalidation trước entry = nến đóng tại/below buffered SL đã khóa; confirmation chỉ xét nếu không invalidated và còn hạn. Nếu low cùng confirmation candle xuyên SL, candidate INVALIDATED dù close reclaim (không biết thứ tự intrabar); invalidation/expiry ưu tiên hơn confirmation. OPEN dùng ordered trade touches theo Phase 02/03. TP ở resistance phía trên entry, không “tìm đỉnh tương lai”; tick collapse → SKIP.
- Tại proposed/paper entry: kiểm deviation, SL/TP ordering, costs/risk; khác xa candidate → reject strategy entry. **Manual đã mua ngoài sàn:** vẫn ghi observation thành `OFF_PLAN/RISK_BREACH` và giữ reservation/clock theo actual entry; không gọi strategy-approved. Barriers giữ nguyên; nếu actual entry làm ordering sai hoặc deadline quá hạn → EXIT_REQUIRED, không tự dời SL/TP.
- Planned loss phải gồm phí và slippage bound có chứng cứ. SL là trigger, không bảo đảm max realized loss do gap/fill; hiển thị cảnh báo rõ. Thiếu notional/approved bound không đưa BUY.
- Reward/risk net sử dụng cost model theo entry/exit, không lấy ratio giá thô làm expected return. `E[net] = p_tp * E[net|tp] + p_sl * E[net|sl] + p_timeout * E[net|timeout]`; từng payoff là fill-aware estimate có evidence, không mặc định timeout=0 hoặc stop fill đúng threshold.
- `BUY_ELIGIBLE` chỉ khi confirmation đã xảy ra, fresh, config đầy đủ, valid estimator artifact, approved cost/slippage model, risk admissible và net-edge criterion chốt trước đạt. Nếu chỉ giá/shape hợp → WATCH_ONLY. Không dự báo “mua chắc thắng”.

## Bước thực hiện
1. Đối chiếu refs/services để không nhân bản availability extractor hoặc fee handling.
2. Chốt schema version, reason codes và một setup; viết config validator và pure engine.
3. Lock vùng và điều kiện vào trước waiting; mỗi thay đổi ở FLAT tạo candidate/version mới, giữ history.
4. Compile feature/evidence từ source canonical; không fetch source hoặc gọi model trong engine.
5. Ràng buộc entry/exit separation và risk gate, expose đủ evidence để Phase 02 persistence.

## Gate
- [ ] Thay tất cả nến sau cutoff không đổi candidate/barriers; late available_at cũng không được dùng.
- [ ] Chưa confirmation → không BUY; nến sau t không là confirmation trước t.
- [ ] Không resistance đủ xa/đơn vị sai/null/tick collapse/cost missing/risk missing → reason rõ.
- [ ] Proposed entry vượt tolerance bị reject; manual fill đã xảy ra vẫn được ghi off-plan, reconcile path và không để hệ thống FLAT giả.
- [ ] Decimal fee/risk formulas kiểm hành vi; không claim max loss guaranteed.

## Rủi ro và kiểm chứng
Rule không bảo đảm edge. Nhiều setup/tune/lookback gây data snooping; chỉ một setup/version và validation trước test. Test deterministic cases riêng DB/network; smoke engine trên feed snapshot thật để xem candidate hoặc SKIP thật. Không số giả trong production.
