# ShootingStar: Honest Research Narrative

> **A local-first, evidence-first research platform for BTCUSDT 30-minute predictive modeling.**  
> *Zero hype. Zero fabricated win rates. Zero zero-slippage curves.*

> **Cập nhật 2026-11-21:** phần tự huấn luyện model, Pattern Lab thống kê, lessons và các trang research/signals/patterns đã được gỡ. Các mục nói về chúng dưới đây giữ làm ghi chép lịch sử; sản phẩm hiện chỉ còn ingestion, snapshot, mô phỏng và báo cáo Gemini.

---

## 1. Executive Summary & Core Research Question

Can short-horizon (30-minute) price direction of Bitcoin (`BTCUSDT`) spot on Binance be reliably predicted using causal candlestick morphology and rolling price-volume dynamics?

Commercial trading vendors routinely claim 80–90% win rates on retail indicators. Academic and quantitative reality demonstrates that short-term liquid crypto spot markets operate near the efficient market hypothesis. 

ShootingStar was constructed from the ground up to establish an **honest, reproducible research baseline**:

| Metric | Logistic Regression (Out-Of-Sample) | Baseline 1 (Majority Class) | Baseline 2 (Momentum) | Coin Flip Benchmark |
| :--- | :--- | :--- | :--- | :--- |
| **Directional Accuracy** | **Chưa kiểm chứng** | **Chưa kiểm chứng** | **Chưa kiểm chứng** | 50.00% |
| **Brier Score** | **GATED** | GATED | GATED | 0.2500 |
| **Sample Size ($N$)** | Walk-Forward Out-of-Sample | Walk-Forward Out-of-Sample | Walk-Forward Out-of-Sample | - |
| **Cost-Adjusted Expectancy** | **GATED** | **GATED** | **GATED** | - |

> **Trạng thái:** Chưa có kết quả kiểm chứng out-of-sample chính thức được phê duyệt cho production. Tất cả chỉ số P&L ròng và kỳ vọng giao dịch đều bị khóa (**GATED**) cho đến khi mô hình trượt giá sổ lệnh được thẩm định.

---

## 2. Rejection of Commercial Trading Hype

ShootingStar categorically rejects common retail marketing fallacies:

### Fallacy 1: "90% Win Rate Indicator"
- **Cause:** Lookahead leakage, unpurged cross-validation (training on $t+k$ while predicting $t$), or arbitrary retrospective threshold fitting.
- **ShootingStar Countermeasure:** Enforced causal feature extraction (strictly $i \le t$). Feature perturbations in $t+1 \dots t+k$ have zero effect on feature vectors at $t$ (verified in `tests/test_labels_features_baselines.py`).

### Fallacy 2: "Zero-Slippage Backtests"
- **Cause:** Assuming orders fill at exact interval close prices with zero fee drag.
- **ShootingStar Countermeasure:** Enforced cost gating (`UNAVAILABLE_PENDING_SLIPPAGE_METHOD`). Binance Spot standard fees are 0.1000% maker / 0.1000% taker (0.2000% roundtrip). Assuming zero slippage is strictly prohibited in our protocol (`docs/binance-spot-fees.md`).

### Fallacy 3: "Candlestick Patterns Guarantee Reversals"
- **Cause:** Visual survivorship bias (remembering the hammer that preceded a rally, ignoring the 50 that failed).
- **ShootingStar Countermeasure:** Tiêu chí nến chỉ được dùng làm bằng chứng mô tả trong báo cáo, tính bằng quy tắc cố định trên nến đã đóng tới thời điểm dự báo (`backend/shootingstar/application/patterns.py`). Hệ thống không gán win rate, không coi mẫu nến là edge; thống kê Pattern Lab đã gỡ.
---

## 3. Methodological Rigor & Data Provenance

1. **Wire Byte Preservation:**
   Raw Binance REST HTTP responses are written bit-for-bit to `.raw.json` sidecar files before processing (`src/shootingstar/adapters/storage.py`).
2. **Immutable Parquet Snapshots:**
   Snapshots are stored in Apache Parquet format and sealed with an immutable SHA-256 hash. Rebuilding from raw bytes reproduces the exact bit-for-bit SHA-256 hash (`tests/test_storage_and_ingestion.py`).
3. **Decoupled Data Availability:**
   Interval closure (`close_time_ms`) is strictly separated from data availability (`available_at_ms`). Historical backfills require positive latency assumptions ($\ge 1000\,\text{ms}$) to avoid hindsight bias.
4. **Purged Walk-Forward Splitting (đã gỡ cùng phần tự huấn luyện):**
   Quy tắc embargo 6 nến (30 phút) từng được áp dụng giữa Train, Calibration và Test để loại bỏ rò rỉ chồng lấn; sản phẩm hiện tại không còn luồng train.
5. **Platt Calibration (đã gỡ cùng phần tự huấn luyện):**
   Xác suất model từng được hiệu chỉnh bằng hồi quy logistic 1 chiều trên fold calibration độc lập; không còn trong sản phẩm hiện tại.
6. **Append-Only Replay Reports:**
   Mỗi báo cáo Gemini được lưu trước khi kết quả được reveal và không bị viết lại hồi tố; kết quả thực tế được tính riêng từ nến đã đóng.

---

## 4. Reproducibility & Audit Trail

Every metric reported in this narrative is backed by reproducible artifacts in the repository:

- **Experiment Report:** `data/reports/exp_pilot_5m_lr_report.md`
- **Model Checksum:** `data/artifacts/exp_pilot_5m_lr_model.joblib` (SHA-256: `6c5cf14e7dbdf91b98f2b4c50ee7b374d6cce4d6b63d91cf9feea2d6ecbcfe4e`)
- **Primary Snapshot:** `data/snapshots/BINANCE_BTCUSDT_5m_1788894000000_1791485999999_97f6323ad2.parquet` (SHA-256: `97f6323ad2...`)
- **Automated Test Suite:** 40 passing pytest tests covering domain boundaries, leakage resistance, Alembic migrations, and API contracts.

---

## 5. Next Milestones

- [ ] **Phase 10 Gated Work:**
  - Design empirical orderbook slippage model before un-gating cost-adjusted metrics.
  - Paper trading harness (local execution simulator).
  - External macro/news filter integration.
