---
title: "ShootingStar research platform"
description: "Implement a reproducible BTCUSDT research workflow, evidence-first dashboard, rule-based pattern lab and restrained scrollytelling landing page."
status: pending
priority: P2
tags: [backend, database, api, frontend, feature]
blockedBy: []
blocks: []
created: 2026-10-09
---
# ShootingStar Research Platform Implementation Plan

> Planning only. No code, trained model, database, provider integration, or verified result exists yet. Phase gates below must not be described as shipped features.

**Goal:** Research and review BTCUSDT 30-minute `UP/DOWN/NO_TRADE` predictions from data available at prediction time; publish reproducible evidence, not automated trading or profit promises.

**Architecture:** Python 3.12 modular monolith: domain rules → application use cases/ports → provider, persistence, file and ML adapters → local CLI jobs and FastAPI read API. Next.js App Router/TypeScript consumes backend read contracts. PostgreSQL holds canonical records; raw responses and immutable validated Parquet experiment snapshots are separately checksummed files. Initial operation is local/manual. No Docker Compose until deployment discussion.

**Reference:** `docs/reseaching/docs/shootingstar-business-requirements.md`, `docs/reseaching/docs/shootingstar-research-report.md`, `docs/reseaching/docs/superpowers/specs/2026-08-19-shootingstar-technology-design.md`, `docs/DESIGN.md`. Correct references to legacy paths when writing project README. `docs/DESIGN.md` is ShootingStar's primary visual system; adapt Apple-like sparse chrome to data-dense research tables, not retail imagery/CTAs.

## Decisions already agreed

- Binance Spot public BTCUSDT OHLCV via `GET /api/v3/klines`; public market data needs no trading key. Respect IP-wide weights and headers; back off on 429 (`Retry-After` when present); stop on 418. No live order endpoint or trading credentials.
- Pilot: lấy 30 ngày BTCUSDT gần đây để thử phân trang/chất lượng; đây là độ dài tập dữ liệu thử, KHÔNG phải thời gian dự đoán. Timeframe nến là cấu hình per-experiment với lựa chọn đầu tiên `1m` hoặc `5m`; horizon dự đoán cố định 30 phút. Mỗi experiment khóa timeframe trong config hash; không trộn timeframe trong cùng experiment.
- Separate raw provider archive from cleaned frozen dataset snapshot; retain request range, response status, source, timestamps, checksums and reject reasons. Store canonical records/metadata in PostgreSQL.
- Train only on historical data; local Python jobs invoked intentionally, no permanently running trainer. Snapshot itself does not learn. Technical-only baselines before news. Logistic Regression is first classifier, not Gemini/LLM; no auto-agent council.
- Features và pattern chỉ dùng nến đã đóng **và thực sự khả dụng tại prediction time `t`**; kiểm tra `available_at <= t`, không chỉ `close_time <= t`. Binance historical klines không chứng minh được thời điểm publication trong quá khứ: với backtest phải công khai giả định độ trễ bảo thủ; giá entry không sớm hơn thời điểm khả dụng giả định. Future prices chỉ dùng để tạo label/outcome. Train → calibration → held-out test theo thời gian, gap/purge theo horizon.
- Separate predicted class, calibrated probabilities and action policy. `DOWN 60%` is not automatically actionable; `NO_TRADE` may be selected even if `DOWN` is argmax. On Spot, DOWN is not short P&L. Override/review is separate from model prediction and evaluation.
- Rule-based, interpretable candle patterns live in separate Pattern Lab, not silently fed into classifier. Explicit definitions/versions and normalized candle measurements; overlapping windows must not masquerade as independent confirmations.
- Landing page narrates why ShootingStar exists, what it is, and accuracy-before-speed. 90% is unverified ambition, never a result or guarantee. A restrained pinned scroll-driven SVG/illustrative chart story; real research report or explicit 'not yet verified' state, no invented results. Work pages use only basic motion; reduced-motion and mobile non-pinned equivalents.
- Primary visual system: `docs/DESIGN.md` (white/parchment/near-black, blue `#0066cc` as interactive accent, low chrome, strong type). Color must not imply UP/profit. Avoid retail components and huge tiles inside work pages.
- Deployment/Docker Compose, real trading, news integration where provenance is unverified, LLM/Gemini, and automatic retraining deferred. Paper trading is later than validated offline research. Do not claim predictive edge until measured.

## Open gates requiring user/product input before affected phases

1. Pilot 30 ngày gần đây đã chốt cho **kiểm tra ingestion/chất lượng**, không dùng riêng pilot để tuyên bố model hiệu quả. Evaluation period/regime coverage và minimum sample/coverage cho báo cáo model vẫn chưa chốt.
2. Timeframe của nến đã chốt là **cấu hình theo experiment**, bản đầu hỗ trợ `1m` và `5m`; horizon giữ 30 phút. Chọn phương án nghiên cứu bằng train/validation hoặc walk-forward trước, chỉ đánh giá một lần trên final held-out test. Trước khi tạo label, xác định `t`, giả định trễ `available_at` cho nến lịch sử, thời điểm/giá entry-exit và cách xử lý nến thiếu; không giả vờ `close_time` là thời điểm dữ liệu đã nhận được.
3. Tài khoản Binance Spot cá nhân đã KYC; KYC không quyết định fee tier. Tra biểu phí Spot theo ngày và ghi rõ giả định Regular User/maker-taker/discount. **Đã chốt: không mặc định slippage bằng 0 hay một tỷ lệ 'phổ biến', không yêu cầu người dùng tự bịa số.** OHLCV không cho phép đo giá khớp; phase nghiên cứu ban đầu chỉ công bố dự đoán/độ tin cậy. Do SRS định nghĩa threshold/label và net expectancy sau fee+slippage, phần label ba lớp theo ngưỡng chi phí, action policy và performance giao dịch **bị chặn** cho tới khi có phương pháp/giả định slippage được duyệt; không âm thầm hạ chuẩn hoặc tuyên bố hoàn tất FR-RES-02/04. Không thêm order-book modeling vào giai đoạn đầu.
4. Spot-only action semantics: DOWN = warning/stand aside, or later separate product with a legally/technically supported short venue. Plan assumes warning/stand aside.
5. Pattern definitions are candidate hypotheses, not pre-validated signals. Specify initial small set before evaluating held-out data.
6. News provider permissions, account allowlist, raw retention, reliable historical `published_at` and `ingested_at` if/when news phase starts. If unverifiable, remain technical-only.
7. Whether report numbers are public on landing page; until approved and measured, show status without performance claims.

## Contracts and state transitions

- Prediction record: `prediction_time`, horizon, snapshot/feature-window reference, experiment/model version, probability vector summing to 1, predicted class, **separate** decision (`UP`, `DOWN`, `NO_TRADE`), decision-policy version/reason, news used/rejected references where applicable. Append-only prediction payload.
- Outcome: `PENDING` until target horizon and required closed candles available; then `EVALUATED` with realized return, label, match of predicted class, and *separately* decision/paper accounting; or `UNSCORABLE` with reason. Never rewrite old prediction. Late/missing data cannot create hindsight signals.
- Experiment: frozen configuration hash, snapshot checksum, feature-set/model and rule versions; ordered split windows, embargo length, artifact checksum, calibration window, metrics/report references. Any change creates new version/experiment.
- Pattern: immutable rule/version, detection timestamp, fixed lookback, normalized descriptors, outcome once mature, rejection reason if invalid. Pattern card shows count, **effective temporal coverage**, outcomes and uncertainty/time-period breakdown; not 'verified 100000 times' from overlapping windows.

## Phases — kế hoạch, chưa triển khai

| Phase | Kết quả bàn giao | Phụ thuộc | Trạng thái |
|---|---|---|---|
| 1. Nền tảng local | Quy tắc thời gian, CLI, hướng dẫn API | Không | Chưa bắt đầu |
| 2. Dữ liệu | Pilot 30 ngày, kiểm tra nến, raw + snapshot | 1 | Chưa bắt đầu |
| 3. Lưu trữ | PostgreSQL, migration, audit/provenance | 1–2 | Chưa bắt đầu |
| 4. Nghiên cứu cơ bản | Features, baseline; nhãn theo chi phí chờ phương pháp slippage | 2–3 | Chưa bắt đầu |
| 5. Đánh giá model | Walk-forward, calibration, report trung thực | 4 và quy tắc label đã chốt | Chưa bắt đầu |
| 6. Mẫu hình | Rule-based Pattern Lab riêng biệt | 2–4, chốt quy tắc mẫu | Chưa bắt đầu |
| 7. Signals | Dự đoán, chờ đủ 30 phút, đối chiếu/review | 5 | Chưa bắt đầu |
| 8. Web làm việc | FastAPI read APIs, Next.js 5 page | 2–7 theo page | Chưa bắt đầu |
| 9. Landing | Scrollytelling lý do ra đời, report thật/empty state | Thiết kế đã duyệt; report thật cần 5 | Chưa bắt đầu |
| 10. Sau nghiên cứu | Paper trading, news, deployment chỉ khi đủ điều kiện riêng | 5–9 và quyết định sau | Để sau |

### Phase 1. Local foundation and data contracts

- [ ] Create Python package with `domain/`, `application/`, `adapters/`, `cli/`, `api/`; configure lint/type/test tooling and local run instructions. Domain imports no FastAPI/SQLAlchemy/pandas/exchange SDK. Next.js workspace created only when backend read contract exists.
- [ ] Add README integration register linked to `docs/external-apis.md`: Binance base URL/endpoint, params, UTC milliseconds, max 1000 candles/page, rate weights/headers, retries/backoff, no auth, raw/reject retention. Do not put operator integration specification into agent instructions.
- [ ] Define UTC timestamp, candle close availability, unique `(venue,symbol,timeframe,open_time)` and provenance types. Include scenario tests for boundary candle and duplicate/invalid OHLCV.
- **Gate:** local Python CLI prints package version/help; boundary tests run without database/network.

### Phase 2. Binance pilot, raw archive and immutable snapshot

- [ ] Build httpx adapter: bounded requests and retries, status/error logging, cursor pagination with no duplicates, explicit time bounds, IP-weight awareness and 429/418 response handling. Pilot 30 ngày gần đây, tải theo từng trang giới hạn; loại current unclosed candle. Lưu thời gian ingestion thực tế; báo cáo độ phủ cả `1m` và lựa chọn `5m` nếu được chốt, không âm thầm đổi timeframe.
- [ ] Store exact raw JSON responses with checksums and request/response metadata; validate UTC order, missing/duplicate intervals, OHLCV consistency and rejected samples with reasons. Snapshot only validated eligible candles as immutable Parquet with checksum/version; keep raw archive distinct.
- [ ] Local smoke: fetch bounded BTCUSDT pilot from public endpoint, inspect headers and closed-candle status, reproduce snapshot hash from archived data; if network unavailable use recorded fixture and report live limit. Do not quietly fill gaps.
- **Gate:** quality report explicitly shows count, expected intervals, missing/duplicates/rejects and which candle timeframes are supportable; 30 ngày chỉ là pilot dữ liệu, chưa đủ để kết luận model.

### Phase 3. Persistence and experiment provenance

- [ ] Add local PostgreSQL configuration, SQLAlchemy 2 repositories and Alembic migration(s) for ingestion runs, candles, rejected records, snapshots, experiments/config/splits, labels, model versions/artifacts, metrics/reports, signals/outcomes, pattern rules/hits/outcomes, reviews/overrides, audit and later paper trades/news. Define keys, immutable references and UTC constraints; no raw bulk blobs duplicated into canonical tables without retention decision.
- [ ] Adapter tests against temporary PostgreSQL: uniqueness, referential links, audit append-only writes, snapshot/config hash integrity. Run migrations up/down on disposable local database.
- **Gate:** CLI can store/retrieve one real pilot run and its immutable snapshot metadata.

### Phase 4. Labels, features and baseline research

- [ ] Define `t` là lúc đủ nến đã đóng và khả dụng; lịch sử Binance không ghi thời điểm nến được nhận, vì vậy ghi giả định latency bảo thủ và entry không sớm hơn `t`. Từ pilot kiểm tra timestamp/gap rồi khóa convention giá tại `t` và `t+30m`. Tách thử nghiệm directional-only có nhãn hướng giá khỏi nhãn `UP/DOWN/NO_TRADE` theo ngưỡng chi phí của SRS; không gọi cái đầu là nhãn giao dịch ba lớp đã hoàn thành.
- [ ] Lưu biểu phí Binance Spot có URL/ngày truy xuất/tier/maker-taker/discount; KYC cá nhân không đồng nghĩa VIP hoặc giảm phí. Không mặc định slippage và không yêu cầu UI tự nhập để hợp thức hóa P&L. Trước khi xây nhãn ba lớp theo cost threshold, quyết định policy và báo net expectancy, phải có phương pháp chi phí/slippage được duyệt và đóng băng; nếu chưa có, hiện rõ trạng thái chưa đánh giá sau slippage.
- [ ] Generate lagged return, volume, volatility, moving average, momentum and candle-structure features strictly from candles whose `available_at <= t`. Add leakage boundary tests: open vs close vs actual/assumed availability, missing intervals and delayed candles.
- [ ] Implement always-UP, always-DOWN, majority and simple technical baseline; define trade accounting separately from class prediction, with DOWN as non-short on Spot.
- **Gate:** rerunning same snapshot/config yields identical labels/features/splits/baseline results; test future data perturbations do not alter features at earlier `t`.

### Phase 5. Evaluation, calibrated model and report

- [ ] Chronological walk-forward: train → independent calibration/validation → held-out test, horizon-based purge/embargo for overlapping labels, training-only feature transforms and majority class. So `1m` với `5m` trên validation/walk-forward, chọn và đóng băng timeframe/model/policy trước khi mở final held-out test; không lặp lại việc chọn winner dựa trên test.
- [ ] Train Logistic Regression only after suitable frozen label definition and baselines; calibrate on separate window, save immutable versioned model artifact and snapshot/config hashes. For directional-only research report accuracy/precision/recall, confusion/class distribution and calibrated probability bins with counts/uncertainty. Three-class `NO_TRADE`, action coverage, trade count, net expectancy, win rate, loss streak, drawdown and cost-adjusted regime breakdown require approved fee/slippage/threshold/execution convention; without them mark these fields unavailable, not zero or profitable.
- [ ] Compare with baselines using matched windows. Report test dates, actual effective sample size under overlapping horizons, excluded observations, limitations and no-edge outcome if applicable. Never publish invented 90% performance.
- [ ] Smoke an offline end-to-end run from frozen pilot snapshot → report → reload model and reproduce predictions; keep run evidence.
- **Gate:** report can be regenerated bit-for-bit where deterministic artifacts permit; metrics do not confuse DOWN classification with Spot short returns.

### Phase 6. Rule-based Pattern Lab (separate hypothesis track)

- [ ] Agree and freeze initial few declarative pattern rules with lookback, normalized body/wick/return/volume conditions; render representative candle thumbnail from rule, not cherry-picked winner. Rule changes receive new version.
- [ ] Detect historical occurrences using only candles closed at `t`; record all hits, not only wins. Score mature hits with same 30-minute label semantics; account for overlapping windows and periods/regimes; keep independent of classifier feature set initially.
- [ ] Present both hits and failures, count and uncertainty; abstain from statistical claims on sparse/correlated samples.
- **Gate:** rule with future candle dependency fails validation; explicit fixture produces expected hits and misses.

### Phase 7. Signals, maturation and review; paper trading gated later

- [ ] Local explicit signal command loads approved model and new closed candles, computes features/probabilities and applies frozen decision policy; append prediction/evidence with `PENDING` outcome. No live order API.
- [ ] Separate local maturation command checks horizon completion and quality, appends `EVALUATED`/`UNSCORABLE` result; never overwrites prediction. Reviewer notes and overrides stored as audit records, excluded from model evaluation.
- **Gate:** smoke prediction → time maturity → outcome/review; verify no early evaluation and no exchange trading endpoint called.

### Phase 8. FastAPI read contracts and research UI

- [ ] Read APIs: data-quality runs/snapshots, experiments/splits/baselines/report/calibration, pattern rules/hits/outcomes, latest signals/evidence/outcomes/reviews/audit; paper trade data only after Phase 10 paper-trading gate. Pagination and UTC dates; no secret/raw sensitive payloads in browser. Backend alone calculates labels/probabilities/costs/statistics.
- [ ] Next.js pages: Overview (system status and honest empty states), Data (coverage timeline, quality details, snapshots/checksum, small candle drilldown), Research (experiment list, matched baseline comparison, calibration/out-of-sample report and provenance), Pattern Lab (versioned rule cards with candle visuals and outcome drilldowns), Signals (probabilities versus separate decision, pending/evaluated/unscorable and review). Reports open from Research; audit via relevant details. UI initially reads stored results; train/backtest initiated locally, no fake Train button.
- [ ] Apply `docs/DESIGN.md`: light/parchment tables with legible dense numerical columns, neutral evidence semantics, blue interactive affordances, accessible contrast/touch/focus, basic transitions only. Include empty/loading/error states, filters and time-zone labels. No scrollytelling inside work pages.
- **Gate:** browser smoke from real seeded local DB: inspect data gap, report calibration, pattern failure, and a pending then mature signal; screenshot responsive view.

### Phase 9. Landing-page narrative

- [ ] Design short Vietnamese copy and storyboard: ShootingStar name as aspiration, origin in volatile crypto/news, purpose as evidence-first 30-minute research, human review plus tested model, accuracy-before-speed, report evidence/limitations. Never promise 90% accuracy/profit or claim unshipped agents/news functionality exists.
- [ ] Restrained SVG/canvas illustration in `docs/DESIGN.md` palette: short meteor motif, an explicitly illustrative market/news scene, then human hypothesis + model probabilities + NO_TRADE/evidence. One desktop pinned/sticky scroll stage with scene transitions; native scroll, no hijacking. Mobile uses stacked scenes; `prefers-reduced-motion` renders fully readable static frames. Real report only if available/approved; otherwise 'chưa có kết quả kiểm chứng'.
- [ ] Browser smoke desktop scroll, mobile layout and reduced-motion state; check focus/navigation and no fabricated metrics.
- **Gate:** story communicates reason/goal before workflow; work pages remain restrained.

### Phase 10. Later gated work: paper trading, news and deployment
- [ ] Only **after** research evidence reviewed: simulate spot-valid paper actions with explicit entry/exit prices, fees/slippage, net result and signal/model/experiment links. Do not invent profits for DOWN.

- [ ] After source, rights and retention approved: provider adapter for allowlisted public X/news; raw payload/hash, provider item ID, author/text/URL, created/published and ingested timestamps, dedup and rejection reasons. Reject late or missing historical availability; technical-only results remain valid without news. Compare news-augmented model against technical-only on matched out-of-sample windows.
- [ ] Only when deployment requested: decide local/VPS/cloud, backups, secrets, HTTPS, scheduling and Docker Compose if useful. No live trading transition in this plan.

## Validation matrix

| Invariant | Verification |
|---|---|
| No future features/news | controlled time-boundary fixtures; mutate future input without changing earlier prediction |
| Closed candles and complete timeline | pilot ingestion quality report and missing/duplicate/unfinished fixtures |
| Reproducible experiment | same snapshot checksum/config hash gives same labels/splits/metrics |
| Honest probabilities | held-out calibration by bin with counts, uncertainty, and time/regime breakdown |
| No test contamination | fit transform/calibrator/threshold only in allowed windows; horizon gap tests |
| Model prediction ≠ trading action | fixture with DOWN argmax but NO_TRADE decision; report both separately |
| Append-only evidence | prediction immutable, delayed outcome/audit linkage persists |
| UI is not a calculator | API/UI contract inspection and browser smoke with real persisted values |
| Reduced motion | landing page readable at mobile and reduced-motion setting |
| No live order execution | adapter boundary and smoke verify only public market-data endpoint |

## Deferred scope and risks

- News historical availability is a hard blocker for news features, not for technical-only path. Avoid retroactive backfills that make historical signals omniscient.
- 30-minute sliding labels strongly overlap; raw hit count is not independent evidence. Use horizon-aware gaps and show effective coverage/uncertainty.
- Binance Spot DOWN signal means possible avoidance, not short P&L. Paper returns require an explicit executable Spot strategy.
- Fee/slippage assumptions determine three-class cost threshold and actionable policy. With only OHLCV and no defensible slippage assumption, initial research may assess direction/probability, but **cannot claim SRS cost-adjusted labels, net P&L, or complete feature acceptance**. Resolve before those stages; do not add out-of-scope order-book modeling by default.
- 90% is a user aspiration; neither UI nor documentation may state it as achieved absent independently held-out evidence.
- No live trading credentials, multi-asset, LLM/Gemini, autonomous agents, Redis/Celery/Kubernetes or Docker Compose in initial local milestones.
