---
title: ShootingStar — Next Session Handoff
status: active
---

# Current State

ShootingStar is a greenfield research and decision-support system for BTC/USDT short-horizon prediction. It is not an autonomous live-trading bot.

Initial research target:

- Symbol: BTC/USDT.
- Horizon: 30 minutes.
- Classes: `UP`, `DOWN`, `NO_TRADE`.
- Features must contain no values newer than prediction timestamp `t`.
- News must satisfy `published_at <= t` and `ingested_at <= t`.
- Evaluation must be time-ordered/walk-forward.
- Fees and slippage are part of threshold and evaluation.
- Initial execution mode is backtest and paper trading only.

# Documents

1. Approved research direction: `local://shootingstar-trading-direction-plan.md`
2. Research report: `docs/shootingstar-research-report.md`
3. Reader-friendly explanation: `docs/shootingstar-detailed-explanation.md`
4. Technical design spec: `docs/superpowers/specs/2026-08-19-shootingstar-technology-design.md`

# Technology Decisions

- Frontend: Next.js + TypeScript.
- Backend/research: Python.
- API: FastAPI + Pydantic.
- Database: PostgreSQL.
- PostgreSQL access: SQLAlchemy + psycopg.
- Migrations: Alembic.
- Data processing: pandas + NumPy.
- Raw/frozen snapshots: PyArrow/Parquet.
- Initial ML: scikit-learn with calibration and time-series evaluation.
- Later benchmark: LightGBM/XGBoost only after the baseline.
- Data ingestion: httpx with timeout, retry, backoff, deduplication, and timestamp logging.
- Architecture: Clean Architecture modular monolith.
- Deployment: Docker Compose.
- Deferred: Go, Rust, separate Vector DB, Redis, Celery, Kubernetes, PyTorch, LLM orchestration, live order placement.

# Clean Architecture

```text
Frameworks & Drivers
  FastAPI, PostgreSQL, Binance/news clients, sklearn, files
        ↓
Interface Adapters
  HTTP, CLI, worker, repositories, provider adapters
        ↓
Application
  use cases, DTOs, inbound ports, outbound ports
        ↓
Domain
  labels, thresholds, signals, timestamp rules, paper-trade rules
```

Domain does not import FastAPI, SQLAlchemy, Pydantic, pandas, exchange SDKs, or network clients.

Ports are interfaces/contracts. Adapters are concrete implementations:

- `MarketDataProvider` → `BinanceMarketDataAdapter`;
- `SignalRepository` → `PostgresSignalRepository`;
- `ModelArtifactStore` → scikit-learn adapter;
- `MarketDataProvider` → fixture/parquet adapter for deterministic tests.

# Current Gate

Research and technical design are written. Implementation code has not started.

The technical design spec was expanded with plain-language explanations of:

- why Python instead of Go/Rust;
- why FastAPI instead of Django/Flask;
- why SQLAlchemy/Alembic;
- why pandas/NumPy instead of Polars initially;
- why scikit-learn before LightGBM/XGBoost/PyTorch/LLM;
- why PostgreSQL instead of a Vector DB;
- why Parquet is used alongside PostgreSQL;
- why Clean Architecture is used;
- how Clean Architecture relates to DDD and Layered Architecture;
- why Redis/Celery/Kubernetes/microservices are deferred.

# Next Action

After reviewing `docs/superpowers/specs/2026-08-19-shootingstar-technology-design.md`, create the implementation plan. The implementation plan should cover:

1. Scaffold Python, Next.js, and Docker Compose.
2. Create PostgreSQL schema and Alembic migrations.
3. Implement domain rules and Clean Architecture ports/use cases.
4. Implement fixture data and timestamp/leakage checks.
5. Implement market-data ingestion adapter.
6. Implement labels, features, and technical baseline.
7. Implement walk-forward evaluation and reports.
8. Implement FastAPI read APIs.
9. Implement Next.js research dashboard.
10. Implement paper-trade simulator and end-to-end smoke path.

Do not add live order placement to the first implementation plan.
