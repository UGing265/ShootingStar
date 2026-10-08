# ShootingStar

ShootingStar is an evidence-first research platform for BTCUSDT 30-minute directional price movement analysis, based on historical Binance Spot market data, probability calibration, and rule-based pattern research.

---

## Architecture & Principles
- **Accuracy before speed:** No invented metrics, no fake 90% claims, no simulated P&L without defensible execution assumptions.
- **Strict time boundaries:** Predictions at time `t` strictly consume candles whose `available_at <= t`. No lookahead leakage.
- **Local-first:** Fully runnable locally without Docker Compose initially.

---

## External Integrations Register
All external market data and API integrations are registered and documented in:
- [External APIs Integration Register](docs/external-apis.md) (Endpoints, rate weights, headers, pagination, error handling).

---

## Local Development & Setup

### Prerequisites
- Python 3.11+
- Virtual environment recommended (`.venv`)

### Installation
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install package in editable mode
pip install -e ".[dev]"
```

### Running the CLI
```bash
# Check CLI help and available subcommands
shootingstar --help

# 1. Pilot Ingestion (Binance Spot REST API)
shootingstar fetch-pilot --symbol BTCUSDT --timeframe 5m --days 30

# 2. Snapshot Catalog
shootingstar list-snapshots
shootingstar show-snapshot --id <SHA256_OR_PATH>

# 3. Run Walk-Forward Research Experiment
shootingstar run-experiment --snapshot <SHA256_OR_PATH> --id exp_pilot_5m_lr

# 4. Rule-Based Pattern Lab (Separate Hypothesis Track)
shootingstar scan-patterns --snapshot <SHA256_OR_PATH>

# 5. Append-Only Signals & Maturation
shootingstar list-signals --limit 20
shootingstar mature-signals --snapshot <SHA256_OR_PATH>

# 6. Launch Research Web UI & REST API
shootingstar serve --host 127.0.0.1 --port 8000
```

### Web Platform & API Endpoints
When `shootingstar serve` is running:
- **Research Dashboard:** `http://127.0.0.1:8000/`
- **Interactive Swagger API Docs:** `http://127.0.0.1:8000/docs`
- **Landing Page Narrative:** `http://127.0.0.1:8000/narrative` (or see [`docs/landing-page-narrative.md`](docs/landing-page-narrative.md))
- **Binance Spot Fee & Slippage Gating:** [`docs/binance-spot-fees.md`](docs/binance-spot-fees.md)

### Running Full Test Suite
```bash
pytest -v
```
