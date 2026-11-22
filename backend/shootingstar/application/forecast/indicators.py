"""Technical indicators with explicit warm-up; missing values are NaN."""

import numpy as np


def ema(values, period: int):
    """EMA seeded by the first period's SMA, then alpha=2/(period+1)."""
    values = np.asarray(values, dtype=float)
    if period < 1:
        raise ValueError("period must be positive")
    result = np.full(values.shape, np.nan)
    if len(values) < period:
        return result
    result[period - 1] = np.mean(values[:period])
    alpha = 2 / (period + 1)
    for i in range(period, len(values)):
        result[i] = alpha * values[i] + (1 - alpha) * result[i - 1]
    return result


def rsi(values, period: int = 14):
    """Wilder RSI: 100 - 100/(1 + smoothed gains/smoothed losses)."""
    values = np.asarray(values, dtype=float)
    if period < 1:
        raise ValueError("period must be positive")
    result = np.full(values.shape, np.nan)
    if len(values) <= period:
        return result
    delta = np.diff(values)
    gains, losses = np.maximum(delta, 0), np.maximum(-delta, 0)
    gain, loss = np.mean(gains[:period]), np.mean(losses[:period])
    for i in range(period, len(values)):
        if i > period:
            gain = (gain * (period - 1) + gains[i - 1]) / period
            loss = (loss * (period - 1) + losses[i - 1]) / period
        result[i] = 50.0 if gain == loss == 0 else 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)
    return result


def macd(values, fast: int = 12, slow: int = 26, signal: int = 9):
    """Return MACD line, EMA signal and histogram; histogram = line - signal."""
    line = ema(values, fast) - ema(values, slow)
    signal_line = np.full(line.shape, np.nan)
    valid = np.flatnonzero(np.isfinite(line))
    if len(valid):
        signal_line[valid[0]:] = ema(line[valid[0]:], signal)
    return line, signal_line, line - signal_line


def atr(high, low, close, period: int = 14):
    """Wilder ATR: SMA of true ranges, then (previous ATR*(n-1)+TR)/n."""
    high, low, close = (np.asarray(x, dtype=float) for x in (high, low, close))
    if period < 1 or not (len(high) == len(low) == len(close)):
        raise ValueError("invalid period or unequal input lengths")
    result = np.full(close.shape, np.nan)
    if len(close) < period:
        return result
    tr = high - low
    tr[1:] = np.maximum.reduce((tr[1:], abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])))
    result[period - 1] = np.mean(tr[:period])
    for i in range(period, len(close)):
        result[i] = (result[i - 1] * (period - 1) + tr[i]) / period
    return result


def volume_ratio(volumes, period: int = 20):
    """Last volume divided by the mean of the last period, including itself."""
    values = np.asarray(volumes, dtype=float)
    if period < 1:
        raise ValueError("period must be positive")
    if len(values) < period or np.mean(values[-period:]) == 0:
        return None
    return float(values[-1] / np.mean(values[-period:]))
