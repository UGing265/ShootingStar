# ShootingStar

ShootingStar is an evidence-first research platform for BTCUSDT 30-minute directional price movement analysis, based on historical Binance Spot market data, with Gemini-based replay reports.

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

# 3. Launch Web UI & REST API
shootingstar serve --host 127.0.0.1 --port 8000
```

### Web Platform & API Endpoints
When `shootingstar serve` is running:
- **Web Dashboard:** `http://127.0.0.1:8000/`
- **Interactive Swagger API Docs:** `http://127.0.0.1:8000/docs`
- **Landing Page Narrative:** `http://127.0.0.1:8000/narrative` (or see [`docs/landing-page-narrative.md`](docs/landing-page-narrative.md))
- **Binance Spot Fee & Slippage Gating:** [`docs/binance-spot-fees.md`](docs/binance-spot-fees.md)

### Running Full Test Suite
```bash
pytest -v
```

---

## Chấm điểm dự đoán: so với luật đơn giản

Tại mỗi mốc thời gian `t`, ba bên cùng đoán giá tại `t+6h` cao hơn hay thấp hơn giá mua `P` (giá đóng tại mốc `t`):

- **Luật luôn TĂNG:** không nhìn dữ liệu, luôn đoán TĂNG.
- **Luật theo đà 6h:** nếu `close(t) > close(t-6h)` thì đoán TĂNG, ngược lại đoán GIẢM.
- **Gemini:** phân tích kỹ thuật từ digest do Python tính.

Hai luật chạy độc lập, không nhìn câu trả lời của Gemini, do Python tính và không tốn chi phí API.

Cách chấm: nếu `|Δ| < 0.5%` so với `P` thì coi là đi ngang (FLAT) và không chấm. Gemini chỉ có giá trị khi thắng rõ ràng cả hai luật trên nhiều trăm mốc.

Đo thật trên 2.581 mốc 6h (02/2025 đến 11/2026): biến động 6h trung vị 0.49%, ngưỡng 0.5% loại khoảng 51% số mốc.

Ví dụ 3 lượt:

| Lượt | close(t-6h) | Giá mua P | Thực tế t+6h | Luôn TĂNG | Theo đà 6h | Gemini |
|---|---|---|---|---|---|---|
| 1 | 60.000 | 61.000 | 62.000 | Đúng | Đúng | Sai |
| 2 | 62.000 | 61.000 | 60.000 | Sai | Đúng | Đúng |
| 3 | 60.000 | 60.500 | 61.500 | Đúng | Đúng | Đúng |
| **Tổng** | | | | **2/3** | **3/3** | **2/3** |

Ghi chú: các mốc trước `2025-02-01` có thể đã bị Gemini nhớ sẵn giá (knowledge cutoff `01/2025`), nên được thống kê tách riêng.

Nguồn: Hewamalage et al., [Forecast Evaluation for Data Scientists: Common Pitfalls and Best Practices](https://arxiv.org/pdf/2203.10716); Hyndman & Koehler 2006, [Another look at measures of forecast accuracy](https://www.doi.org/10.1016/J.IJFORECAST.2006.03.001).

Các hướng đi khác (luật Python, máy học, đổi sang dự đoán biến động...) và số liệu baseline thật: [docs/forecast-strategy-options.md](docs/forecast-strategy-options.md).
