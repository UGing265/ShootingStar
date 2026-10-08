# ShootingStar — Business Requirements & SRS Scope

## I. Business Overview

ShootingStar là hệ thống nghiên cứu và hỗ trợ quyết định cho BTC/USDT. Tại thời điểm `t`, hệ thống chỉ dùng dữ liệu đã khả dụng trước `t` để đánh giá khả năng giá trong 30 phút tiếp theo là `UP`, `DOWN` hoặc `NO_TRADE` sau fee và slippage.

Hệ thống phục vụ research, backtest, report, signal và paper trading; không tự đặt lệnh thật.

## II. Project Scope

### In-Scope

- Market data OHLCV BTCUSDT từ Binance Spot API.
- Raw response, Parquet snapshot và checksum.
- Kiểm tra timestamp, missing candle, duplicate và candle chưa đóng.
- X/news data từ allowlist account thông qua provider được chấp thuận, có thể thử Apify.
- Lưu tweet/news ID, author, text, URL, `created_at`, `ingested_at`, raw payload và content hash.
- Loại dữ liệu đến muộn, thiếu timestamp hoặc không hợp lệ.
- Label `UP`, `DOWN`, `NO_TRADE` theo threshold có fee/slippage.
- Technical features từ dữ liệu không mới hơn prediction time.
- Baseline always-up, always-down, majority-class và technical baseline.
- Classifier ML nhỏ, probability calibration và model versioning.
- Time-ordered split, gap theo horizon, walk-forward và out-of-sample evaluation.
- Metrics: precision/recall, confusion matrix, calibration, coverage, expectancy, trade count, win rate, loss streak, drawdown, time/regime breakdown.
- Research report có snapshot checksum, configuration hash và evidence.
- Signal generation và signal review.
- Paper order/trade mô phỏng, fee, slippage và net result.
- PostgreSQL, Alembic, repositories và audit records.
- FastAPI read APIs.
- Next.js research dashboard.
- Docker Compose cho `web`, `api`, `worker`, `postgres`.
- Unit, application, adapter và end-to-end smoke tests.

### Out-of-Scope

- Live order placement và exchange trading credential ở Stage 0/1.
- Multi-asset, order-book modeling và dynamic position sizing.
- Autonomous trading agent.
- LLM, multi-agent debate và deep learning.
- Separate vector database, Redis, Celery và Kubernetes.
- Microservice split.
- Go/Rust rewrite trước khi có profiling.
- Realtime dashboard trước khi baseline chứng minh giá trị.
- Tự động chuyển sang live trading.

## III. Actors List

### Researcher

Cấu hình experiment, chạy backtest, xem report, signal và metrics.

### Reviewer

Kiểm tra evidence, signal, paper trade và ghi manual review/override.

### Operations Administrator

Quản lý provider, allowlist, configuration, deployment, database và backup.

### Market Data Provider

Cung cấp market data, ban đầu là Binance Spot API.

### News Provider

Cung cấp X/news data, ban đầu có thể thử Apify hoặc provider được chấp thuận.

### Scheduler

Kích hoạt ingestion, evaluation và paper-trading job.

## IV. Business Workflow

```text
Researcher cấu hình experiment
    ↓
Market Data Provider + News Provider
    ↓
Validate data, timestamp và leakage
    ↓
Snapshot + checksum
    ↓
Labels + technical features
    ↓
Baseline + model + calibration
    ↓
Walk-forward evaluation
    ↓
Metrics + research report
    ↓
Review signal/evidence
    ↓
Paper trading + audit
```

Business rules chính:

- Feature chỉ dùng dữ liệu `<= prediction_time`.
- News chỉ hợp lệ khi `created_at/published_at <= t` và `ingested_at <= t`.
- Giá tương lai chỉ dùng để tạo label và evaluate.
- Baseline phải chạy trước model phức tạp.
- Calibration không được dùng held-out test.
- Fee và slippage phải nằm trong threshold và evaluation.
- Manual override không được trộn vào model evaluation.
- Paper trading không gọi live order endpoint.

## V. Functional Requirements

### Module: Researcher

- **FR-RES-01: Configure Experiment**

    **Research Configuration**

    - Cấu hình symbol, venue, timeframe, horizon, fee, slippage và threshold.
    - Lưu snapshot reference, feature-set version và configuration hash.
    - Không thay đổi threshold hoặc split sau khi đã xem kết quả.

- **FR-RES-02: Build Labels and Features**

    **Label Construction**

    - Return vượt `+threshold` → `UP`.
    - Return thấp hơn `-threshold` → `DOWN`.
    - Còn lại → `NO_TRADE`.

    **Feature Generation**

    - Tạo lagged return, volume, volatility, moving average, momentum và candle structure.
    - Không dùng dữ liệu tương lai.
    - Loại hoặc ghi reason cho sample thiếu warm-up data.

- **FR-RES-03: Train and Calibrate Model**

    **Baseline**

    - Chạy always-up, always-down, majority-class và technical baseline.

    **Classifier and Calibration**

    - Train classifier nhỏ, bắt đầu bằng Logistic Regression.
    - Calibration dùng window độc lập với training và test.
    - Lưu model version, artifact reference, training/calibration window và config hash.

- **FR-RES-04: Evaluate and Report**

    **Walk-forward Evaluation**

    - Dùng train → calibration/validation → held-out test theo thứ tự thời gian.
    - Gap được tính từ horizon và timeframe.
    - Loại label overlap.

    **Research Metrics**

    - Báo cáo precision/recall cho `UP` và `DOWN`, confusion/class distribution, calibration, coverage, expectancy sau chi phí, trade count, win rate, loss streak, maximum drawdown, time/regime breakdown và out-of-sample status.

- **FR-RES-05: Generate and Review Signal**

    **Signal**

    - Lưu decision, probability, timestamp, horizon, threshold, model version, feature window và reason.
    - Lưu news được dùng và bị loại.

    **Manual Review**

    - Reviewer có thể ghi note hoặc manual override.
    - Override phải lưu riêng và không thay đổi kết quả model.

### Module: Market Data Provider

- **FR-MKT-01: Ingest Market Data**

    **OHLCV Retrieval**

    - Gọi Binance Spot API với symbol, interval, start time và end time.
    - Có timeout, retry giới hạn, backoff, rate-limit handling và error logging.

    **Data Quality**

    - Kiểm tra missing, duplicate, timestamp order, OHLCV validity và candle đã đóng.
    - Lưu raw response, request range, provider status, snapshot path và checksum.

### Module: News Provider

- **FR-NEWS-01: Collect News/X Data**

    **Allowlist Collection**

    - Lấy dữ liệu công khai từ account được allowlist.
    - Lưu tweet/news ID, author, text, URL, metrics, `created_at` và `ingested_at`.
    - Lưu provider, actor/run ID, raw payload và content hash.

    **Timestamp and Deduplication**

    - Reject item thiếu timestamp hoặc ID.
    - Reject item đến sau prediction time.
    - Deduplicate theo provider và item ID.
    - Ghi reason cho mọi item bị loại.
    - Không bypass login, CAPTCHA, private data hoặc rate-limit.

### Module: Reviewer

- **FR-REV-01: Review Evidence**

    **Signal Review**

    - Xem signal, model, feature window, news used/rejected và research report.

    **Audit**

    - Ghi actor, action, timestamp, reason và before/after value khi có override.

### Module: Researcher

- **FR-PAP-01: Run Paper Trade**

    **Paper Execution**

    - Mô phỏng entry, exit, holding period, fee, slippage và net result.
    - Liên kết paper trade với signal, experiment và model version.
    - Không gửi lệnh thật.

### Module: Read API and Dashboard

- **FR-API-01: Expose Research Data**

    **Read APIs**

    - Trả latest signals, evidence, experiments, metrics, reports, paper trades và audit history.
    - Frontend không tự tính label, feature, probability, fee/slippage hoặc expectancy.

    **Research Dashboard**

    - Hiển thị signals, probabilities, evidence, experiments, calibration, time/regime metrics, paper trades và audit.

## VI. Non-functional Requirements

- **NFR-01: Data Integrity** — Timestamp UTC, unique candle/tweet, raw data có reference/checksum.
- **NFR-02: Leakage Prevention** — Không dùng feature/news/future price sai thời điểm.
- **NFR-03: Reproducibility** — Cùng snapshot và config phải tạo cùng labels, splits và metrics.
- **NFR-04: Auditability** — Ingestion, reject, model, signal, paper trade và override phải truy vết được.
- **NFR-05: Security** — Secret server-side, parameterized SQL, least privilege, không trading credential ở Stage 0/1.
- **NFR-06: Reliability** — Timeout, retry giới hạn, rate-limit handling và lỗi provider rõ ràng.
- **NFR-07: Maintainability** — Clean Architecture; domain không phụ thuộc framework hoặc provider.
- **NFR-08: Performance** — Phù hợp một user, một pair và workload research ban đầu.

## VII. Recommend Tech Stack

- **Frontend:** Next.js, TypeScript, App Router.
- **Backend:** Python 3.12, FastAPI, Pydantic v2.
- **Database:** PostgreSQL, SQLAlchemy 2, psycopg, Alembic.
- **Data:** pandas, NumPy, PyArrow, Parquet.
- **ML:** scikit-learn, Logistic Regression, calibration, time-series evaluation.
- **Market API:** Binance Spot REST, `httpx`.
- **News:** Apify hoặc provider được phê duyệt; provider adapter tách khỏi domain.
- **Deployment:** Docker Compose với `web`, `api`, `worker`, `postgres`.

## VIII. Known Constraints & Assumptions

- Research đầu tiên dùng BTCUSDT, một venue và horizon 30 phút.
- Binance Spot là venue dự kiến; timeframe 1m hoặc 5m phải được chốt theo chất lượng dữ liệu.
- Fee, slippage, safety margin và threshold là configuration bắt buộc.
- Technical-only phải chạy trước news-augmented.
- Apify chỉ là provider thử nghiệm cho đến khi kiểm tra output, chi phí, độ ổn định và quyền sử dụng dữ liệu.
- Nếu không chứng minh được timestamp lịch sử của news, phải chạy technical-only.
- Giai đoạn đầu là offline research và historical backtest; paper trading là stage sau.
- Live trading không thuộc scope.
- PostgreSQL lưu canonical records; Parquet lưu snapshot bất biến.
- Chưa chốt retention, budget, coverage, evaluation period và deployment target.

## IX. Clarifying Questions

1. Venue là Binance Spot hay nguồn khác?
2. Timeframe là 1m hay 5m?
3. Fee, slippage, safety margin và threshold cụ thể là bao nhiêu?
4. X/news dùng historical, realtime hay cả hai?
5. Apify actor và allowlist account cụ thể là gì?
6. Có lấy reply, quote và repost không?
7. Retention và quyền sử dụng raw news thế nào?
8. Evaluation period, market regimes và coverage tối thiểu là gì?
9. Khi nào chuyển từ backtest sang paper trading?
10. Chạy local hay deploy VPS/cloud?
