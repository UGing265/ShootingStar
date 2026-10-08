# Research Report: exp_pilot_5m_lr

## 1. Setup & Horizon
- **Symbol:** BTCUSDT
- **Timeframe:** 5m
- **Horizon:** 30 minutes forward
- **Snapshot SHA-256:** `97f6323ad2`
- **Test Window:** 1790971200000 to 1791483900000 (1710 samples)
- **Class Distribution:** UP=880 (51.5%), DOWN=830 (48.5%)

## 2. Directional Performance (Out-of-Sample Test)
- **Accuracy:** 51.05%
- **Precision (UP):** 51.97% | **Recall (UP):** 64.32% | **F1 (UP):** 57.49%
- **Precision (DOWN):** 49.44% | **Recall (DOWN):** 36.99% | **F1 (DOWN):** 42.32%
- **Brier Score:** 0.2507 (lower is better, 0.25 is random coin flip)
- **Log Loss:** 0.6946

## 3. Probability Calibration Bins
| Bin | Range | Samples | Mean Pred Prob | Empirical Observed UP |
|---|---|---|---|---|
| 1 | [0.00, 0.40] | 0 | 20.0% | 0.0% |
| 2 | [0.40, 0.48] | 170 | 47.1% | 58.2% |
| 3 | [0.48, 0.52] | 1011 | 50.1% | 48.4% |
| 4 | [0.52, 0.60] | 516 | 53.9% | 56.0% |
| 5 | [0.60, 1.00] | 13 | 65.3% | 23.1% |

## 4. Baseline Comparison
| Model | Accuracy | Precision UP | Recall UP | Spot Return/Signal | Spot Cumulative |
|---|---|---|---|---|---|
| Logistic_Regression (Calibrated) | 51.05% | 51.97% | 64.32% | -0.0104% | -17.70% |
| Always_UP | 51.46% | 51.46% | 100.00% | -0.0119% | -20.41% |
| Always_DOWN | 48.54% | 0.00% | 0.00% | 0.0000% | 0.00% |
| Majority_Class | 51.46% | 51.46% | 100.00% | -0.0119% | -20.41% |
| Simple_Momentum | 47.72% | 49.17% | 47.16% | -0.0089% | -15.21% |

## 5. Cost-Adjusted Status & Policy Gates
> **CRITICAL INVARIANT:** No arbitrary zero slippage was applied.

- **Action Policy (Three-Class UP/DOWN/NO_TRADE):** `UNAVAILABLE_PENDING_SLIPPAGE_METHOD`
- **Net Expectancy After Costs:** `UNAVAILABLE_PENDING_SLIPPAGE_METHOD`
- **Win Rate After Fee & Slippage:** `UNAVAILABLE_PENDING_SLIPPAGE_METHOD`
- **Maximum Drawdown After Costs:** `UNAVAILABLE_PENDING_SLIPPAGE_METHOD`
- **Post-Cost Regime Breakdown:** `UNAVAILABLE_PENDING_SLIPPAGE_METHOD`