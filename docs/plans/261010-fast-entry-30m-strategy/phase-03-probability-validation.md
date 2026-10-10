# Phase 03 — Xác suất barrier và kiểm định

## Context
[Plan](plan.md), [risk/barriers](phase-01-entry-barriers-risk.md), [events/lifecycle](phase-02-watcher-lifecycle.md). P1; Pending. Không xem directional model sẵn là đáng tin cho mục tiêu khác. Không giả lập win rate hoặc confidence LLM.

## Files
Root: `D:/AShiroru/ProgramCode/Project/Team/ShootingStar/`.
- Create `backend/shootingstar/application/barrier_evaluation.py`: first-touch labeler và competing-outcome estimator/report; pure core, adapter persistence qua repository đã có ở Phase 02.
- Modify `application/entry_strategy.py` và `application/trade_watch.py`: production consume approved artifact tại cutoff; RESEARCH_ONLY được dùng frozen unapproved artifact và shadow occupancy riêng, không fit trên request/trade hiện tại.
- Modify `backend/shootingstar/cli/main.py`: register `research-entry-strategy` / `evaluate-entry-strategy` / `approve-entry-artifact` (local admin approval ghi provenance, không bypass failed gates).
- Reuse `application/training/splits.py` conventions; sửa/generalize metrics trong `application/evaluation.py` chỉ sau LSP refs, không làm binary consumer đổi nhãn.
- Modify repository/models chỉ theo ownership Phase 02 integration owner cho artifact metadata nếu cần.
- Add `backend/tests/test_barrier_evaluation.py`: observable label, leakage, probability gating; không snapshot wording hoặc mocks echo.

## Chọn estimator ban đầu
**Empirical multinomial baseline có smoothing**; dễ kiểm được từng mẫu, không cần tuyên bố model phức tạp thắng. So sánh global-frequency baseline cùng rule/execution và existing directional model chỉ như nhánh nghiên cứu riêng, không map p_up sang p_tp.

Với 3 outcome `j ∈ {TP_FIRST, SL_FIRST, TIMEOUT}`:
`p_j = (n_j + alpha_j) / (N + sum(alpha))`.
- `n_j` từ các episode cùng setup version, barrier distance bins/regime/entry policy chốt trên train/validation; không tùy chọn historical analog sau khi thấy outcome.
- Prior `alpha_j > 0`/cường độ smoothing chốt trước, fit training-only nếu dùng base-rate; smoothing không tạo thêm observed samples hoặc tự làm calibrated.
- Xác suất tại thời điểm **entry** conditional trên actual entry/barriers đã chấp nhận, horizon còn đủ 30m. Estimate trước entry phải ghi reference-entry/entry-zone rõ và chỉ preview; actual entry khác bin/policy → recompute estimate bằng artifact đã khóa hoặc từ chối, không dùng confidence proposal cũ.
- Khoảng bất định cho vector multinomial: Dirichlet posterior marginals Beta quantiles, ghi rõ credible interval/prior assumptions; temporal block bootstrap để sensitivity phụ thuộc thời gian. Không dùng Wilson interval như interval của posterior smoothed mà không nêu nghĩa.
- Không dữ liệu/không calibration artifact/regime unsupported → p null, reason. Missing class hoặc N ít không lấy raw model confidence để lấp.

## Nhãn và tập dữ liệu
- **Market-touch** label theo source-order entry boundary `(event_time_ms, source_id/cursor)` đến deadline inclusive. Events cùng millisecond nhưng chứng minh sau entry vẫn xét; nếu manual time không có comparable cursor và chạm barrier ở boundary không xác định trước/sau → AMBIGUOUS. Equality TP/SL tính chạm, event đúng deadline ưu tiên trước TIMEOUT.
- Entry observation lưu occurrence/receipt/source và entry cursor khi có; partial entry candle không dùng full high/low. Paper executable outcome riêng, không nâng public hit thành fill. Delayed manual report reconcile elapsed path, không dùng receipt time làm bắt đầu 30m hoặc claim notification quá khứ.
- Một episode một entry; selector/confirmation/barriers hoàn toàn causal. Giữ toàn bộ candidate timeline, expired/no-entry khác timeout position. Không chỉ lấy người đã chọn mua vì thắng; nghiên cứu shadow episodes theo frozen policy để tránh selection bias.
- Đồng nến TP/SL không thứ tự → AMBIGUOUS; missing path/deadline → UNSCORABLE/CENSORED. Đếm riêng, không thắng/thua/timeout giả.
- Không drop ambiguous/censored rồi báo probability cho mọi lượt. Báo full candidate/trigger denominator, coverage theo regime và unresolved fraction. Ưu tiên trade-level complete cohort; giữ unknown assignment bounds (best/worst case) và sensitivity. Nếu unresolved có thể thay đổi calibration/edge verdict → artifact không APPROVED; prediction p null. Không gọi worst-case SL-first là nhãn thật.
- Backfill historical receipt không chứng minh availability quá khứ: feature t dùng giả định latency công khai; outcome path dùng event occurrence sau entry, không đưa labels vào selection.

## Chia tập và gates
1. Chọn params/finite setup grid bằng TRAIN/VALIDATION; calibration cohort độc lập; final test chỉ một lần với version frozen. Tái dùng walk-forward nhưng purge theo **interval thực tế** candidate/wait/holding/feature horizon: không chỉ hardcode 30 bar nếu waiting episodes dài hoặc nhãn overlap.
2. Probability bin/regime/entry distance cố định trước test. Đơn vị mẫu hiệu dụng là episode/dependence block, không số nến/tick. Bootstrap theo thời gian, không iid random split.
3. Báo multiclass Brier `mean(sum_j((p_j-y_j)^2))`, log loss với numerical epsilon versioned, per-class reliability, sample/coverage/uncertainty, regime breakdown; baseline cùng population. Không tái dùng binary fixed bins/argmax UP như multiclass evaluator.
4. Ngưỡng minimum independent samples, interval width, calibration error, uncertainty-adjusted net edge chốt từ validation và mục tiêu risk trước final test; không default tùy ý “50 mẫu/10% ECE/70% thắng”. Đạt sample count không tự đạt edge.
5. Prospective shadow: freeze/persist predictions trước outcome, measure report/calibration/triggers, prior/test cutoffs bảo đảm không model artifact tương lai. Manual approval chỉ sau gates pass; invalid artifact/regime stale về WATCH_ONLY.

### Bootstrap approval không vòng phụ thuộc
- `RESEARCH_ONLY` shadow mode thu toàn bộ triggers của policy frozen, tạo hypothetical entry tại executable quote theo size và recording occupancy **một episode tại một thời điểm**, không chờ production BUY approval. Missing quote/depth → missing outcome/coverage, không mock fill.
- Persist unapproved prediction vector/status trước outcome; analyst dashboard ghi “Nghiên cứu — không khuyến nghị mua”. Không route shadow record qua manual position hoặc eligible production entry.
- Approval command đọc artifact + frozen params/config hash + historical OOS/calibration report + prospective shadow report + cost/receipt coverage + risk protocol; kiểm mọi gate bằng machine-readable verdict và lý do. Approve không sửa test hoặc ngưỡng sau outcome; failed → reject và giữ WATCH_ONLY.

## Costs và expectancy
- Đăng ký account fee assumptions có nguồn/version, gồm tax/special/BNB khi áp dụng; không truy account bằng key thật trong scope public watcher. Operator cung cấp effective fees hoặc baseline đã đăng ký với caveat.
- Capture quote/depth và receipt tại paper entry/exit. Estimate spread + depth walk cho declared size, latency và quantity effects; không double-count spread/slippage. Market order assumptions chốt trước, dùng conservative executable prices thay vì threshold fill.
- Data thiếu historical order book → market-touch probabilities vẫn là nghiên cứu nếu label coverage đủ, **net profitability và BUY vẫn gated**. Prospective quote/depth receipts là cách hoàn thành cost methodology cho size/bối cảnh đã quan sát; không suy ra mọi liquidity/regime.
- Fee mua bằng BTC làm giảm quantity có thể bán; ghi charge asset/quantity net. Timeout payoff theo bid/size/execution model khi deadline, không 0. Stop gap/slippage tail có sensitivity; planned loss không chắc là realized maximum.
- Net expectancy ở Phase 01 chỉ enabled khi cả outcome-conditioned payoff distributions và uncertainty có evidence tương thích với estimator population. Không lấy price-hit p ghép payoffs tưởng tượng.

## Checklist/verification
- [ ] Giá chạm TP trước SL, SL trước TP, equal deadline, no-touch full coverage, same-bar ambiguous, gaps/censoring cho label đúng.
- [ ] Long-only `SL < entry < TP`; không dùng công thức short của ShootingStar cho người chưa mua.
- [ ] Future suffix change không đổi plan/probability artifact được chọn tại cutoff; artifact train/calibration cutoff vượt decision bị reject.
- [ ] One-class/sparse/unsupported regime/non-finite values/normalization đúng gate null, không manufactured certainty.
- [ ] Ambiguous bounds, timeout net cost và size/fees audit có report thật.
- [ ] CLI research chạy dataset thật, artifact/report reload tái lập; không số output bịa.
- [ ] Prospective shadow report có predictions persist trước outcomes. Không đủ evidence thì trạng thái gate còn mở, không claim complete profitability.

## Tiếp theo
Phase 04 hiển thị probability + interval + N + status đúng nghĩa; chưa đạt vẫn xem được chờ/vùng/evidence, nhưng không trình bày như khuyến nghị mua đã kiểm chứng.
