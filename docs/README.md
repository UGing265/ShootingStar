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
- [Thiết kế tự train lưu tham khảo](./self-trained-model-design.md) — hướng cũ, chưa triển khai cho giá mua tùy ý.
- [Kế hoạch nghiên cứu model API ngoài](./plans/261010-external-model-api-research/plan.md) — phases so sánh và thử tích hợp, chưa chạy.

---

## Core Invariants

1. **Zero Lookahead:** All features enforce positive latency boundaries (`assumed_latency_ms >= 1`). Entries entering at next candle open must have features available prior to open.
2. **Causal Purging:** Walk-forward splits enforce a strict 30-minute purge gap (6 bars for 5m, 30 bars for 1m) preventing target overlap leakage.
3. **Conservative Spot Accounting:** Directional DOWN predictions stand aside in cash (realizing 0.0% return), eliminating unproven short-selling assumptions.
4. **Data Provenance:** Snapshots are verified via immutable SHA-256 parquet checksums. Public APIs never leak local filesystem paths or database secrets.
