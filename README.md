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
# Check version and help
shootingstar --help
shootingstar --version
```

### Running Tests
```bash
pytest
```
