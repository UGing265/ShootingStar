# ShootingStar: Honest Research Narrative

> **A local-first, evidence-first research platform for BTCUSDT 30-minute predictive modeling.**  
> *Zero hype. Zero fabricated win rates. Zero zero-slippage curves.*

---

## 1. Executive Summary & Core Research Question

Can short-horizon (30-minute) price direction of Bitcoin (`BTCUSDT`) spot on Binance be reliably predicted using causal candlestick morphology and rolling price-volume dynamics?

Commercial trading vendors routinely claim 80–90% win rates on retail indicators. Academic and quantitative reality demonstrates that short-term liquid crypto spot markets operate near the efficient market hypothesis. 

ShootingStar was constructed from the ground up to establish an **honest, reproducible research baseline**:

| Metric | Logistic Regression (Held-Out Test) | Baseline 1 (Majority Class) | Baseline 2 (Momentum) | Coin Flip Benchmark |
| :--- | :--- | :--- | :--- | :--- |
| **Directional Accuracy** | **51.05%** | **51.46%** | **49.42%** | **50.00%** |
| **Brier Score** | **0.2507** | 0.2502 | 0.5058 | 0.2500 |
| **Sample Size ($N$)** | 1,710 | 1,710 | 1,710 | - |
| **Cost-Adjusted Expectancy** | **GATED** | **GATED** | **GATED** | - |

**Empirical Conclusion:** On pure 5-minute causal features over a 30-day window (8,640 candles), linear classification achieves **51.05%** out-of-sample directional accuracy, indistinguishable from random noise and slightly trailing the majority baseline. Standalone candlestick patterns show win rates between **46.0% and 49.7%**.

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
- **ShootingStar Countermeasure:** Declarative, mathematical Rule-Based Pattern Lab (`src/shootingstar/application/patterns.py`). In a 30-day pilot of 8,640 candles:
  - **Shooting Star ($N=272$):** 49.3% win rate, mean 30m return +0.025%.
  - **Hammer ($N=277$):** 46.6% win rate, mean 30m return +0.003%.
  - **Bearish Engulfing ($N=829$):** 49.7% win rate, mean 30m return -0.000%.
  - **Bullish Engulfing ($N=796$):** 46.0% win rate, mean 30m return -0.003%.
  *None demonstrate an exploitable standalone directional edge.*

---

## 3. Methodological Rigor & Data Provenance

1. **Wire Byte Preservation:**
   Raw Binance REST HTTP responses are written bit-for-bit to `.raw.json` sidecar files before processing (`src/shootingstar/adapters/storage.py`).
2. **Immutable Parquet Snapshots:**
   Snapshots are stored in Apache Parquet format and sealed with an immutable SHA-256 hash. Rebuilding from raw bytes reproduces the exact bit-for-bit SHA-256 hash (`tests/test_storage_and_ingestion.py`).
3. **Decoupled Data Availability:**
   Interval closure (`close_time_ms`) is strictly separated from data availability (`available_at_ms`). Historical backfills require positive latency assumptions ($\ge 1000\,\text{ms}$) to avoid hindsight bias.
4. **Purged Walk-Forward Splitting:**
   A mandatory 6-candle (30-minute) embargo gap is enforced between Train, Calibration, and Test splits to eliminate overlap leakage (`src/shootingstar/application/splits.py`).
5. **Platt Calibration:**
   Model probabilities are calibrated using 1D logistic regression over an independent calibration fold.
6. **Append-Only Signal Predictions:**
   Model predictions are stored in an append-only database table (`signal_predictions`). Maturation outcomes are recorded in a separate table (`signal_outcomes`) with a 1-to-1 foreign key, preventing retroactive rewrites.

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
