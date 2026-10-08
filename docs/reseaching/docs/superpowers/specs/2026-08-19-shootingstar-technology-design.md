---
title: ShootingStar Technology and Architecture Design
description: Python-first research platform with Next.js frontend and PostgreSQL persistence for reproducible crypto signal evaluation.
status: pending-review
---

# ShootingStar — Technology and Architecture Design

## 1. Purpose

ShootingStar is a research and decision-support system for one initial question:

> At timestamp `t`, using only market data and news available by `t`, is BTC/USDT likely to move enough during the next 30 minutes to classify as `UP`, `DOWN`, or `NO_TRADE` after fees and slippage?

The first release is not an autonomous trading bot. It provides reproducible research, historical evaluation, signals, paper trades, and audit evidence.

## 2. Decisions

| Area | Decision | Reason |
|---|---|---|
| Frontend | Next.js App Router + TypeScript | User requirement; strong UI and server-rendering option. |
| Backend | Python + FastAPI | Keeps API, research, model, and paper-trading logic in one ecosystem. |
| Database | PostgreSQL | Durable source of truth for canonical data, experiments, signals, paper trades, and audit records. |
| Raw snapshots | Parquet files with checksums | Immutable, portable snapshots for reproducible experiments. Not a second database service. |
| Vector search | None initially; `pgvector` only if later justified | Semantic search does not automatically improve price prediction and adds leakage/operations risk. |
| ML baseline | pandas, NumPy, scikit-learn | Small, explainable, deterministic baseline with time-series evaluation and calibration support. |
| Advanced models | LightGBM/XGBoost only as later benchmarks | Compare incremental value after the baseline; never assume complexity improves accuracy. |
| Data access | SQLAlchemy + psycopg; Alembic migrations | Explicit PostgreSQL access and versioned schema changes. |
| External data | `httpx` plus provider adapters | Retries, timeouts, rate-limit handling, and provider replacement without changing domain rules. |
| Architecture | Clean Architecture modular monolith | Strict dependency direction; domain and use cases stay independent from FastAPI, PostgreSQL, Binance, and ML frameworks. |
| Deployment | Docker Compose | One-user local/VPS deployment without Kubernetes, Redis, or Celery. |
| Runtime | Python 3.12, Node.js LTS | Conservative compatibility for ML and Next.js dependencies. |

## 3. Why Python is the core language

The accuracy-critical work is not HTTP routing. It is:

- timestamp-safe data preparation;
- label construction;
- feature generation;
- time-ordered validation;
- calibration;
- backtesting;
- paper-trade accounting;
- metrics and reports.

Python has the broadest practical ecosystem for this work. NumPy, pandas, scikit-learn, LightGBM, XGBoost, PyArrow, and PostgreSQL clients are mature and interoperable. Many numerical operations execute in native code beneath the Python API, so Python is sufficient for one user, one pair, and the initial research workload.

Go or Rust are not excluded forever. They become candidates only after profiling demonstrates a real ingestion or concurrency bottleneck. They would then replace one edge worker, not the model and research core.

## 4. Why PostgreSQL is the primary database

PostgreSQL provides one durable source of truth for data that must be queried, related, audited, and updated transactionally.

### 4.1. Data stored in PostgreSQL

#### Market data

`market_candles` stores normalized candles:

- venue;
- symbol;
- timeframe;
- open/close timestamp;
- open, high, low, close;
- volume;
- ingestion run;
- source snapshot reference.

Use a unique constraint on `(venue, symbol, timeframe, open_time)` to prevent duplicate candles. Use `timestamptz` for timestamps and numeric types for prices/volumes where exactness is needed.

#### News

`news_items` stores:

- provider and source identifier;
- canonical URL or immutable reference;
- headline;
- raw snapshot reference or permitted text;
- `published_at`;
- `ingested_at`;
- content hash;
- processing status;
- rejection reason.

`news_features` stores extracted sentiment/event fields with the model version that produced them. The raw source remains auditable.

#### Ingestion and dataset snapshots

`ingestion_runs` and `dataset_snapshots` store:

- provider;
- request range and parameters;
- execution timestamps;
- response status;
- retry/error details;
- raw snapshot path;
- checksum;
- schema version.

#### Experiments and labels

`experiments`, `experiment_splits`, and `labels` store:

- experiment configuration;
- data snapshot;
- prediction timestamp;
- horizon;
- fee/slippage assumptions;
- threshold;
- future return used only for label/evaluation;
- `UP`, `DOWN`, or `NO_TRADE` label.

#### Models and metrics

`model_versions`, `model_runs`, and `evaluation_metrics` store:

- model family;
- feature-set version;
- training/calibration windows;
- configuration hash;
- artifact reference;
- fold/regime metrics;
- calibration metrics;
- creation timestamp.

#### Signals and paper trades

`signals`, `paper_orders`, and `paper_trades` store:

- signal timestamp and symbol;
- probabilities and decision;
- threshold;
- model version;
- feature window;
- news IDs used and rejected;
- simulated entry/exit;
- fee/slippage;
- net result;
- linked experiment.

#### Audit

`audit_events` and `manual_overrides` store:

- actor/process;
- action;
- timestamp;
- before/after values;
- reason;
- linked signal or paper trade.

Manual overrides remain separate from model predictions so evaluation is not contaminated.

### 4.2. Why raw snapshots are also files

PostgreSQL stores canonical records and metadata. Raw API responses and frozen experiment datasets are also written to Parquet files with checksums.

This is intentional duplication:

- PostgreSQL supports operational queries and relationships;
- Parquet preserves the exact data snapshot used by an experiment;
- a future API change does not silently rewrite historical research;
- a report can identify exactly which snapshot produced it.

No separate DuckDB server is required. Python can read Parquet directly. DuckDB remains an optional local analytical library if query ergonomics later justify it.

## 5. Why no Vector DB initially

A vector database is useful for semantic news retrieval, similar-article search, clustering, and LLM context retrieval. It is not required for the first technical baseline and does not itself improve price-prediction accuracy.

If semantic news work becomes justified, use PostgreSQL `pgvector` first. Store embedding metadata with:

- source news ID;
- embedding model version;
- creation time;
- source `published_at` and `ingested_at`.

Every retrieval used for a signal must filter `ingested_at <= prediction_time`. A semantic index must not become a path for future news leakage.

A separate Qdrant/Weaviate/Pinecone deployment is out of scope until data volume or profiling demonstrates that PostgreSQL cannot meet the requirement.

## 6. Architecture style

### 6.1. Choice

Use **Clean Architecture as a modular monolith**.

Clean Architecture is an organization and dependency rule, not a requirement to split the system into microservices. The application remains one Python codebase and one deployable backend, but its core rules do not depend on FastAPI, PostgreSQL, Binance, pandas, or scikit-learn.

The design also uses light domain modeling: explicit concepts such as `Label`, `Signal`, `PredictionWindow`, and `PaperTrade` live in the domain layer. Full tactical DDD—multiple bounded contexts, aggregates, domain events, and event sourcing—is not required for the first pair and strategy.

### 6.2. Dependency rule

Dependencies point inward:

```text
Frameworks & Drivers  →  Interface Adapters  →  Application  →  Domain
```

The domain imports nothing from the outer layers. The application layer depends only on domain types and port interfaces. Infrastructure implements those ports. The composition root wires concrete implementations together.

### 6.3. Clean Architecture layers

```text
┌──────────────────────────────────────────────────────────────┐
│ Frameworks & Drivers                                         │
│ FastAPI, PostgreSQL, Binance, news providers, sklearn, files │
├──────────────────────────────────────────────────────────────┤
│ Interface Adapters                                           │
│ HTTP controllers, CLI, worker, repositories, provider maps   │
├──────────────────────────────────────────────────────────────┤
│ Application                                                  │
│ use cases, input/output DTOs, inbound/outbound ports         │
├──────────────────────────────────────────────────────────────┤
│ Domain                                                       │
│ labels, thresholds, signals, availability, paper-trade rules │
└──────────────────────────────────────────────────────────────┘
```

#### Domain layer

Contains framework-independent rules and value objects:

- `Candle`;
- `NewsItem`;
- `PredictionWindow`;
- `TradingThreshold`;
- `Label`;
- `Signal`;
- `PaperTrade`;
- fee/slippage calculation;
- timestamp availability rules.

Domain code must not import FastAPI, SQLAlchemy, Pydantic, pandas, or exchange SDKs. A domain test should run without PostgreSQL, network access, or a model file.

#### Application layer

Contains use cases and contracts. Use cases coordinate work but do not know HTTP, SQL syntax, or Binance response shapes:

- `IngestMarketData`;
- `IngestNews`;
- `ValidateAvailability`;
- `BuildLabels`;
- `GenerateFeatures`;
- `TrainBaseline`;
- `CalibrateModel`;
- `EvaluateWalkForward`;
- `GenerateSignal`;
- `RunPaperTrade`;
- `BuildResearchReport`.

Each use case has explicit input and output DTOs. The same use case can be called by an HTTP controller, CLI command, or worker.

#### Inbound ports

Inbound ports describe application capabilities exposed to the outside:

```text
RunBacktest
GenerateSignal
ListSignals
RunPaperTrade
GetExperimentReport
```

FastAPI routes and CLI commands call inbound ports. They do not contain business rules.

#### Outbound ports

Outbound ports describe dependencies required by use cases:

```text
MarketDataProvider
NewsProvider
CandleRepository
NewsRepository
SignalRepository
ExperimentRepository
ModelArtifactStore
Clock
```

The interfaces belong to the application boundary. Concrete adapters implement them.

#### Interface adapters

Translate external representations into application DTOs and domain objects:

- FastAPI controllers map HTTP requests to use-case input;
- CLI adapters map command-line arguments;
- Binance adapters map exchange payloads to `Candle`;
- PostgreSQL repositories map rows to domain/application records;
- scikit-learn adapters map model artifacts to a prediction port;
- Parquet adapters map snapshots to a deterministic dataset reader.

#### Frameworks and drivers

The outermost layer contains replaceable tools:

- FastAPI;
- Pydantic;
- SQLAlchemy and psycopg;
- Alembic;
- Binance/news HTTP clients;
- pandas, NumPy, scikit-learn;
- PostgreSQL;
- Parquet files;
- Docker runtime.

### 6.4. Composition root

All concrete dependencies are wired in one place:

```text
composition/
  container.py
```

The composition root creates the PostgreSQL repositories, provider adapters, model adapter, use cases, FastAPI controllers, CLI commands, and worker entry points. Domain and application code never instantiate infrastructure clients directly.

### 6.5. Why Clean Architecture is useful here

The primary benefit is not speed. It protects research correctness and makes the same rules reusable:

- backtest, API prediction, and paper trading call the same use cases;
- label logic cannot accidentally depend on a database query or HTTP request;
- timestamp rules can be tested with deterministic fakes;
- Binance can be replaced without rewriting the domain;
- PostgreSQL queries stay in adapters;
- the Next.js frontend cannot create a second implementation of fee, label, or expectancy logic.

The architecture is still a monolith. Clean Architecture supplies boundaries, not distributed deployment.

### 6.6. Why not only classic controller/service/repository layers

A classic three-layer design is faster to start, but its service layer often imports ORM models, HTTP clients, and framework types directly. That creates two risks for this project:

1. Backtest and paper trading can implement slightly different rules.
2. Research code becomes difficult to run without live infrastructure.

Clean Architecture prevents those specific failures by keeping domain/application rules inward and external systems behind ports.

### 6.7. Why not full tactical DDD

Clean Architecture and DDD are not alternatives. Clean Architecture controls dependency direction; DDD supplies domain modeling techniques.

Use light DDD now by naming and testing the domain concepts explicitly. Do not add aggregates, bounded contexts, domain events, or event sourcing until multiple strategies, assets, execution policies, or user workflows create a demonstrated need.

### 6.8. Proposed module layout

```text
src/shootingstar/
├── domain/
│   ├── market.py
│   ├── news.py
│   ├── labels.py
│   ├── signals.py
│   └── paper_trading.py
│
├── application/
│   ├── ports/
│   │   ├── inbound.py
│   │   └── outbound.py
│   ├── dto/
│   └── use_cases/
│       ├── ingest_market_data.py
│       ├── ingest_news.py
│       ├── build_labels.py
│       ├── train_baseline.py
│       ├── evaluate_walk_forward.py
│       ├── generate_signal.py
│       └── run_paper_trade.py
│
├── adapters/
│   ├── inbound/
│   │   ├── http/
│   │   ├── cli/
│   │   └── worker/
│   └── outbound/
│       ├── binance/
│       ├── news/
│       ├── postgres/
│       ├── parquet/
│       └── sklearn/
│
├── configuration/
└── composition/
    └── container.py
```

`apps/api`, `apps/worker`, and `apps/cli` are thin entry points. They assemble dependencies and call application ports.

### 6.9. Clean Architecture tests

Test per boundary:

- domain tests: threshold, label, timestamp, fee/slippage, paper-trade rules;
- application tests: use cases with fake outbound ports;
- adapter integration tests: PostgreSQL, fixture HTTP responses, migrations, serialization;
- end-to-end test: fixture data → label → feature → baseline → signal → paper trade → PostgreSQL audit.

This makes the critical claim testable without requiring live exchange access.

## 7. Python package technologies

| Technology | Use | Initial status |
|---|---|---|
| Python 3.12 | Runtime | Required |
| FastAPI | HTTP API | Required |
| Pydantic v2 | API/config/data validation | Required |
| SQLAlchemy 2 + psycopg | PostgreSQL access | Required |
| Alembic | Database migrations | Required |
| httpx | HTTP data providers | Required |
| pandas + NumPy | Feature and experiment preparation | Required |
| PyArrow | Parquet snapshots | Required |
| scikit-learn | Baselines, calibration, metrics, time split | Required |
| LightGBM/XGBoost | Later model comparisons | Deferred |
| pytest | Behavioral tests | Required |
| Ruff | Formatting/linting | Required |
| uv | Locked Python dependency workflow | Recommended |
| Celery/Redis | Distributed background jobs | Deferred |
| PyTorch | Deep learning | Deferred |
| LLM SDK | News/analysis experiments | Deferred |

## 8. Frontend boundary

Next.js + TypeScript consumes the FastAPI contract. The frontend may display:

- latest signals;
- signal evidence;
- experiment runs;
- metrics and regime breakdowns;
- paper trades;
- audit history.

The frontend must not independently calculate:

- labels;
- features;
- fees/slippage;
- model probabilities;
- expectancy.

Those values come from the Python service and stored experiment records. This avoids two implementations disagreeing.

## 9. Deployment

Initial Docker Compose services:

```text
web       Next.js production container
api       FastAPI container
worker    Python CLI/worker container
postgres  PostgreSQL container
```

Raw snapshots and model artifacts use mounted volumes with backup rules. A reverse proxy is added when exposed outside localhost. Redis, Celery, Kubernetes, and separate vector infrastructure are not required for the first one-user deployment.

The worker can run as a manual command or scheduled process. A queue is introduced only when a measured job-scheduling requirement appears.

## 10. Security and reliability boundaries

- No exchange trading credentials in Stage 0 or Stage 1.
- No withdrawal permission in any future paper/shadow configuration.
- Public market-data calls use rate-limit-aware retries and backoff.
- Secrets remain server-side; never expose them through `NEXT_PUBLIC_*` variables.
- PostgreSQL uses migrations, least-privilege credentials, backups, and parameterized queries.
- Every external record has source timestamps and ingestion metadata.
- Every model artifact references its configuration and dataset snapshot.
- Every paper-trade action is auditable.
- Live trading is a separate safety-critical design, not an accidental extension of this architecture.

## 11. Testing strategy

### Domain tests

Test pure rules:

- threshold classification;
- `UP/DOWN/NO_TRADE` boundaries;
- fee/slippage arithmetic;
- timestamp availability;
- paper-trade accounting.

### Application tests

Use fake ports to test:

- late news exclusion;
- duplicate candle handling;
- label generation;
- signal creation;
- manual override separation;
- reproducibility from the same snapshot.

### Adapter integration tests

Use PostgreSQL and fixture HTTP responses to test:

- schema serialization;
- unique candle constraints;
- migrations;
- retries and timeout translation;
- repository queries;
- raw snapshot metadata.

### End-to-end smoke path

The first end-to-end command must:

1. load a fixed fixture dataset;
2. validate timestamps;
3. create labels;
4. generate technical features;
5. train/evaluate the baseline;
6. create a signal;
7. run a paper trade;
8. write metrics and audit records to PostgreSQL.

## 12. Non-goals

- Go or Rust ingestion rewrite before profiling;
- a separate vector database;
- full DDD modeling;
- a full microservice split;
- autonomous live trading;
- multi-asset support;
- order-book modeling;
- dynamic position sizing;
- LLM debate orchestration;
- realtime dashboard before the research claim survives evaluation.

## 13. Acceptance criteria for the technology design

The architecture is considered correctly implemented when:

1. Next.js can display API-backed signals without recalculating research logic.
2. Python can run the same label/feature/signal logic from CLI and API entry points.
3. PostgreSQL stores canonical data, experiment metadata, signals, paper trades, and audit records.
4. A fixed Parquet snapshot can reproduce an experiment result.
5. Provider and repository ports can be replaced with deterministic test fakes.
6. Late news is excluded by timestamp and the exclusion is recorded.
7. Docker Compose starts web, API, worker, and PostgreSQL without requiring Redis or a vector service.

## 14. Follow-up implementation plan

The implementation plan should begin with the smallest vertical slice:

1. project scaffolding and locked dependencies;
2. PostgreSQL schema and migrations for snapshots, candles, experiments, signals, paper trades, and audit;
3. fixed-fixture ingestion and timestamp validation;
4. label/feature generation and technical baseline;
5. walk-forward evaluation and report persistence;
6. FastAPI read APIs;
7. Next.js research dashboard;
8. paper-trade simulator and end-to-end smoke command.

No live order endpoint is part of this plan.

## 15. Giải thích lựa chọn công nghệ cho người đọc

Phần này trả lời câu hỏi “vì sao dùng công nghệ này mà không dùng công nghệ kia?” bằng ngôn ngữ dễ đọc. Đây là quyết định cho một người dùng, một cặp BTC/USDT và giai đoạn research/paper trading; không phải kiến trúc cho một sàn giao dịch lớn.

### 15.1. Tóm tắt một câu

```text
Next.js làm giao diện.
Python làm data, research, model và paper trading.
PostgreSQL lưu dữ liệu chính.
Docker Compose đóng gói toàn bộ hệ thống.
```

### 15.2. Vì sao Python?

Phần quyết định chất lượng ShootingStar là:

- tạo label đúng;
- không dùng dữ liệu tương lai;
- tạo feature;
- train model;
- calibration;
- backtest;
- tính phí/slippage;
- viết report.

Python có ecosystem phù hợp nhất cho nhóm công việc này. `pandas`, `NumPy`, `scikit-learn`, `PyArrow`, `LightGBM` và `XGBoost` có thể dùng cùng một pipeline.

Python không có nghĩa mọi phép tính đều chạy chậm bằng Python thuần. Nhiều phép tính của NumPy, pandas, scikit-learn, LightGBM và XGBoost chạy ở native layer bên dưới.

Với một người dùng và một pair, tốc độ Python đủ dùng. Tốc độ API còn bị giới hạn bởi network và rate limit của Binance/news provider. Viết downloader bằng Rust không làm Binance cho phép request nhanh hơn.

### 15.3. Vì sao không Go hoặc Rust ngay từ đầu?

Go và Rust mạnh ở:

- nhiều kết nối đồng thời;
- nhiều WebSocket;
- worker chạy lâu với ít RAM;
- ingestion tốc độ cao;
- binary deploy gọn.

Nhưng chúng không làm model chính xác hơn. Chúng cũng không giải quyết các lỗi quan trọng nhất của giai đoạn đầu:

- label sai;
- timestamp leakage;
- phí/slippage bị bỏ qua;
- test split sai;
- news đến muộn;
- overfitting.

Go hoặc Rust chỉ được thêm sau khi profiling chứng minh Python là bottleneck. Khi đó chúng có thể thay riêng data-ingestion worker; domain, model và backtest vẫn ở Python.

### 15.4. Vì sao dùng FastAPI?

FastAPI là lớp giao tiếp giữa Next.js và Python.

Ví dụ:

```text
Next.js gọi GET /signals
FastAPI nhận request
FastAPI gọi GenerateSignal use case
Use case đọc model/repository
FastAPI trả signal đã lưu
```

FastAPI được chọn vì nhẹ, có validation qua Pydantic và sinh OpenAPI. Nó không làm model và không được chứa toàn bộ business logic.

Có thể thay bằng:

- Django REST Framework: tốt khi cần admin, user, permission và workflow lớn;
- Flask: đơn giản hơn nhưng phải tự lắp nhiều thứ;
- Litestar: khả năng tương tự nhưng ecosystem nhỏ hơn.

Django không bị loại vì kém. Nó chỉ nhiều hơn nhu cầu hiện tại. FastAPI hợp với API data/ML nhỏ và một worker research.

### 15.5. Vì sao dùng SQLAlchemy và Alembic?

SQLAlchemy là lớp Python làm việc với PostgreSQL. Alembic quản lý migration.

```text
Python use case
    ↓
Repository adapter
    ↓
SQLAlchemy/psycopg
    ↓
PostgreSQL
```

Không để FastAPI route tự viết SQL và không để domain import SQLAlchemy.

Có thể thay bằng:

- Django ORM: phù hợp nếu chọn Django;
- SQLModel: dễ đọc hơn, nhưng vẫn gắn với hệ sinh thái SQLAlchemy/Pydantic;
- psycopg trực tiếp: ít abstraction hơn, nhưng nhiều SQL và mapping thủ công hơn.

SQLAlchemy + Alembic là lựa chọn cân bằng giữa kiểm soát SQL, migration rõ ràng và khả năng test.

### 15.6. Vì sao dùng pandas và NumPy?

Dùng để:

- đọc candle;
- tính return;
- tính volatility;
- xử lý volume;
- tạo feature;
- chuẩn bị dữ liệu cho scikit-learn.

Có thể dùng Polars. Polars có thể nhanh và tiết kiệm memory hơn trong dữ liệu lớn, nhưng speed chưa phải bottleneck của một người dùng một pair. pandas có compatibility rộng hơn với các thư viện research nên được chọn trước.

Nếu sau này dữ liệu lớn hoặc profiling cho thấy pandas chậm, chỉ thay adapter feature/data. Không cần thay toàn bộ kiến trúc.

### 15.7. Vì sao dùng scikit-learn trước?

Model đầu tiên phải là control để trả lời: “AI hoặc feature mới có tốt hơn cách đơn giản không?”

Scikit-learn cung cấp:

- baseline classifier;
- `TimeSeriesSplit`;
- calibration;
- metrics;
- pipeline;
- preprocessing.

Thứ tự model:

```text
majority class
→ Logistic Regression
→ calibrated tree-based baseline
→ LightGBM/XGBoost benchmark
→ chỉ sau đó mới cân nhắc deep learning/LLM
```

LightGBM/XGBoost có thể mạnh hơn trên feature dạng bảng, nhưng không được giả định là tốt trước khi chạy cùng split, cùng threshold, cùng phí và cùng data snapshot.

PyTorch được hoãn vì deep learning không tự giải quyết vấn đề timestamp và data quality. LLM được hoãn vì news model phải chứng minh incremental value so với technical-only trước.

### 15.8. Vì sao dùng httpx?

`httpx` dùng để gọi Binance/news provider.

Downloader cần có:

- timeout;
- retry;
- exponential backoff;
- xử lý HTTP 429;
- deduplicate;
- raw response archive;
- `published_at` và `ingested_at`;
- checksum.

`requests` cũng dùng được. `aiohttp` phù hợp nếu cần async throughput cao. Với một người dùng, `httpx` đủ rõ và đủ khả năng.

### 15.9. PostgreSQL hay Vector DB?

PostgreSQL là database chính vì ShootingStar chủ yếu lưu dữ liệu có cấu trúc và cần audit:

```text
candles
news_items
labels
experiments
model_versions
signals
paper_trades
audit_events
```

Vector DB chỉ giải quyết semantic search. Nó không tự làm dự đoán giá chính xác hơn.

Nếu sau này cần tìm news tương tự hoặc cấp context cho LLM, dùng `pgvector` trong PostgreSQL trước. Mọi truy vấn semantic vẫn phải lọc:

```text
ingested_at <= prediction_time
```

Không thêm Qdrant, Weaviate hoặc Pinecone khi chưa có hàng triệu document hoặc bottleneck được đo bằng profiling.

### 15.10. Vì sao PostgreSQL vẫn đi cùng Parquet?

Hai loại lưu trữ có vai trò khác nhau:

```text
PostgreSQL:
  dữ liệu canonical, quan hệ, signal, audit, experiment

Parquet:
  raw response và snapshot bất biến để chạy lại experiment
```

Parquet không phải một database server. Nó là file snapshot có checksum. Đây là cách giữ bằng chứng chính xác về dataset đã dùng.

Không cần chạy DuckDB server. Nếu sau này cần query Parquet dễ hơn, có thể thêm DuckDB như thư viện trong Python mà không thêm service deployment.

### 15.11. Vì sao chọn Clean Architecture?

Clean Architecture được dùng để bảo vệ phần logic nghiên cứu khỏi framework và hạ tầng.

```text
FastAPI, PostgreSQL, Binance, sklearn
              ↓
       Interface adapters
              ↓
          Use cases
              ↓
        Domain rules
```

Ví dụ quy tắc “news đến sau timestamp dự đoán thì loại” nằm trong domain/application, không nằm trong controller Binance hay câu SQL PostgreSQL.

Kết quả:

- backtest và paper trading dùng cùng rule;
- test không cần gọi Binance thật;
- đổi provider không cần viết lại label;
- frontend không tự tính lại expectancy;
- PostgreSQL chỉ là adapter lưu trữ, không quyết định domain rule.

Clean Architecture không phải framework Python và không bắt buộc microservices. Ứng dụng vẫn là một Python modular monolith.

### 15.12. Clean Architecture, DDD và Layered Architecture quan hệ thế nào?

Đây không phải ba công nghệ loại trừ nhau:

- **Layered Architecture**: chia code theo tầng;
- **Clean Architecture**: quy định dependency phải hướng vào domain;
- **DDD**: cung cấp cách đặt tên và mô hình hóa domain.

ShootingStar dùng:

```text
Clean Architecture
  + light DDD cho các khái niệm Signal, Label, Threshold, PaperTrade
  + một Python modular monolith
```

Không dùng full tactical DDD vì hiện tại chỉ có một chiến lược, một pair và một horizon. Không thêm aggregate, event sourcing hoặc bounded context nếu chưa có complexity thực tế.

### 15.13. Vì sao không dùng microservices, Redis hoặc Kubernetes?

Một người dùng không cần:

```text
Kafka
Redis
Celery
Kubernetes
service mesh
vector database riêng
```

Các công cụ này giải quyết scale và vận hành lớn. Chúng không làm model chính xác hơn và tạo thêm failure modes.

Docker Compose đủ để chạy:

```text
web       Next.js
api       FastAPI
worker    Python research/paper worker
postgres  PostgreSQL
```

Nếu worker cần lịch, chạy command bằng cron hoặc container scheduler đơn giản. Chỉ thêm queue khi có job concurrency thực tế.

### 15.14. Stack cuối cùng

```text
Frontend:
  Next.js + TypeScript

Backend/API:
  Python + FastAPI + Pydantic

Database:
  PostgreSQL

Database access:
  SQLAlchemy + psycopg + Alembic

Data:
  pandas + NumPy + PyArrow/Parquet

ML baseline:
  scikit-learn

HTTP ingestion:
  httpx

Architecture:
  Clean Architecture modular monolith

Deployment:
  Docker Compose

Deferred:
  Go, Rust, Vector DB, Redis, Celery, Kubernetes, PyTorch, LLM
```

### 15.15. Nguyên tắc không đổi

Dù thay thư viện hay provider nào, các nguyên tắc sau không đổi:

1. Feature không dùng dữ liệu mới hơn `t`.
2. News phải có thời điểm khả dụng.
3. Label dùng giá tương lai chỉ ở bước evaluate.
4. Technical baseline luôn được giữ làm control.
5. Mọi kết quả phải tính phí và slippage.
6. Signal, paper trade và manual override phải audit được.
7. Không thêm công nghệ vì “có thể sẽ cần”; thêm sau khi có yêu cầu hoặc bottleneck được đo.
