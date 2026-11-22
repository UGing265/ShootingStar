# ShootingStar Platform Documentation

ShootingStar is an evidence-first, local-first quantitative research platform for BTCUSDT 30-minute predictive modeling.

## Documentation Index

- [Backend Guide](./backend/README.md) — FastAPI service, Python venv, PostgreSQL, Alembic migrations, and test suite.
- [Frontend Guide](./frontend/README.md) — Next.js 14 App Router, TypeScript, component architecture, and page routes.
- [Local Development Runbook](./local-run.md) — Two-terminal local launch instructions, verification steps, and troubleshooting.
- [Design Tokens & Guidelines](./DESIGN.md) — Apple-inspired UI design system, color palette, typography, and layout rules.
- [Spot Trading Fees Reference](./binance-spot-fees.md) — Binance maker/taker fee structures and research considerations.
- [External APIs](./external-apis.md) — Binance public market data endpoints and rate limit specifications.
- [Nghiên cứu model API cho Replay](./external-model-forecast-design.md) — so sánh Gemini/OpenAI/Claude, rủi ro dữ liệu tương lai và thiết kế thử nghiệm chưa triển khai.
- [Kế hoạch nghiên cứu model API ngoài](./plans/261010-external-model-api-research/plan.md) — phases so sánh và thử tích hợp, chưa chạy.

---

## Core Invariants

1. **Zero Lookahead:** All features enforce positive latency boundaries (`assumed_latency_ms >= 1`). Entries entering at next candle open must have features available prior to open.
2. **Data Provenance:** Snapshots are verified via immutable SHA-256 parquet checksums. Public APIs never leak local filesystem paths or database secrets.
