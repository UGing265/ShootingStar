# Binance Spot Trading Fee Schedule Register

This register records the official Binance Spot fee schedule and conservative execution assumptions for ShootingStar research.

---

## 1. Official Reference
- **Source URL:** [Binance Spot Trading Fees](https://www.binance.com/en/fee/trading)
- **Retrieved Date:** 2026-10-09
- **Venue:** Binance Spot (`BINANCE`)
- **Symbol:** `BTCUSDT`

---

## 2. Fee Tier & Defaults
- **Default Tier:** Regular User (Tier 0 / VIP 0)
- **Maker Fee Rate:** `0.1000%` (0.0010)
- **Taker Fee Rate:** `0.1000%` (0.0010)
- **BNB Fee Deduction Discount:** Not assumed (requires active BNB balance setting; conservative research assumes standard rate of `0.1000%`).
- **KYC Principle:** Individual KYC status verifies identity, but **does NOT grant VIP tier or fee reductions**.

---

## 3. Cost-Adjusted Threshold & Slippage Policy
- **Round-trip Fee:** $0.10\% + 0.10\% = 0.20\%$ (20 bps) assuming taker orders for both entry and exit.
- **Slippage Status:** Historical OHLCV market data does not contain order book depth or executed trade fills for hypothetical orders.
- **Strict Invariant:** ShootingStar does **NOT** invent arbitrary or zero slippage constants to fabricate positive P&L.
- **Gating Rule:** Three-class cost-adjusted labels (`UP/DOWN/NO_TRADE`), net expectancy, and trade profitability metrics remain **UNAVAILABLE / GATED** until a defensible slippage estimation methodology is formally approved.
- **Directional-Only Separation:** Research initially evaluates directional prediction accuracy ($R_{30\text{m}} > 0$ vs $< 0$) and probability calibration independently from post-cost trading returns.
