# Phase 10: Gated Work Register & Unblocking Criteria

> **Document Status:** Official Technical Specification  
> **Repository:** ShootingStar Research Platform  
> **Last Updated:** 2026-10-09  

---

## Overview

In alignment with our core engineering principles (*evidence-first, no invented metrics, no premature deployment*), the following components are **deliberately gated**. They cannot be implemented or activated without satisfying explicit, measurable prerequisites.

---

## 1. Paper Trading Harness (Local Execution Simulator)

| Property | Details |
| :--- | :--- |
| **Status** | **GATED** |
| **Current Blocker** | Cost-adjusted 3-class labeling and action policies remain unproven and blocked under plan §4. Binance Spot fee schedule (0.1000% maker / 0.1000% taker) requires defensible execution assumptions; assuming zero slippage is strictly prohibited. |
| **Unblocking Criteria** | 1. Formal stakeholder review and approval of an empirical orderbook depth & slippage model (zero slippage prohibited).<br>2. Formally documented and tested action decision policy accounting for positive execution latency.<br>3. Verified out-of-sample positive net expectancy after transaction costs and execution drag on immutable snapshots. |
| **Associated Artifacts** | `docs/binance-spot-fees.md`, `src/shootingstar/application/evaluation.py` |

---

## 2. News / Macro Catalyst Filter Integration

| Property | Details |
| :--- | :--- |
| **Status** | **GATED** |
| **Current Blocker** | Unavailability of low-latency, causal timestamped financial news and macro data feeds with verifiable receipt timestamps (`received_at_ms` strictly separated from retroactive article edits). |
| **Unblocking Criteria** | 1. Formal vendor evaluation and registration in `docs/external-apis.md` (e.g. CryptoPanic API, Bloomberg feed, or Twitter/X firehose).<br>2. Enforced ingestion schema recording both publication timestamp and arrival timestamp to prevent retroactive news lookahead leakage. |
| **Associated Artifacts** | `docs/external-apis.md`, `src/shootingstar/domain/models.py` |

---

## 3. Live WebSocket Ingestion

| Property | Details |
| :--- | :--- |
| **Status** | **GATED** |
| **Current Blocker** | Project roadmap prioritizes local-first batch research, snapshot reproducibility, and walk-forward modeling. Live streaming adds operational overhead without improving offline model evaluation. |
| **Unblocking Criteria** | 1. Model achieves validated out-of-sample edge on historical snapshots.<br>2. Specification and implementation of a WebSocket reconnection, heartbeat monitoring, and gap-detection backfill state machine matching the Binance WebSocket API contract. |
| **Associated Artifacts** | `src/shootingstar/adapters/binance.py`, `src/shootingstar/application/ingestion.py` |

---

## 4. Production Deployment (Docker Compose & Cloud Hosting)

| Property | Details |
| :--- | :--- |
| **Status** | **GATED** |
| **Current Blocker** | Strict project constraint: local-first development environment on PostgreSQL 18 with no unnecessary containerization or remote cloud complexity during the exploratory research phase. |
| **Unblocking Criteria** | 1. Maturation of research platform to multi-user collaborative status.<br>2. Explicit stakeholder authorization to provision remote infrastructure and manage deployment keys. |
| **Associated Artifacts** | `pyproject.toml`, `alembic.ini`, `docker-compose.yml` (deferred) |
