"""FastAPI application providing read-only contracts and the evidence-first Research UI.

STRICT INVARIANT:
Cost-adjusted metrics remain explicitly gated as 'Unavailable (pending slippage method)'.
No fabricated profits, slippages, or fake claims.
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from shootingstar.api.read_routes import router as read_router
from shootingstar.api.ingestion_routes import router as ingestion_router
from shootingstar.api.replay_routes import router as replay_router

app = FastAPI(
    title="ShootingStar Research Platform",
    description="Local-first, evidence-first research platform for BTCUSDT 30-minute predictive modeling.",
    version="0.1.0",
)

app.include_router(read_router)
app.include_router(ingestion_router)
app.include_router(replay_router)
@app.get("/", response_class=HTMLResponse)
def get_research_ui():
    """Renders the evidence-first ShootingStar Research Platform Dashboard."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ShootingStar Research Platform | Evidence-First BTCUSDT</title>
    <style>
        :root {
            --bg: #0d1117;
            --surface: #161b22;
            --surface-border: #30363d;
            --text-main: #c9d1d9;
            --text-bright: #f0f6fc;
            --text-muted: #8b949e;
            --accent: #58a6ff;
            --badge-warn-bg: #382403;
            --badge-warn-border: #bb8009;
            --badge-warn-text: #e3b341;
            --badge-success-bg: #04260f;
            --badge-success-text: #3fb950;
            --code-bg: #090d13;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text-main);
            margin: 0;
            padding: 24px;
            line-height: 1.5;
        }
        .container {
            max-width: 1100px;
            margin: 0 auto;
        }
        header {
            border-bottom: 1px solid var(--surface-border);
            padding-bottom: 16px;
            margin-bottom: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        h1 {
            color: var(--text-bright);
            font-size: 24px;
            margin: 0;
        }
        .tagline {
            color: var(--text-muted);
            font-size: 14px;
            margin-top: 4px;
        }
        .card {
            background-color: var(--surface);
            border: 1px solid var(--surface-border);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 24px;
        }
        .card-title {
            color: var(--text-bright);
            font-size: 16px;
            font-weight: 600;
            margin-top: 0;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .badge {
            display: inline-block;
            padding: 3px 8px;
            font-size: 12px;
            font-weight: 500;
            border-radius: 12px;
        }
        .badge-warning {
            background-color: var(--badge-warn-bg);
            color: var(--badge-warn-text);
            border: 1px solid var(--badge-warn-border);
        }
        .badge-success {
            background-color: var(--badge-success-bg);
            color: var(--badge-success-text);
        }
        .grid-2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }
        .stat-box {
            background-color: var(--code-bg);
            border: 1px solid var(--surface-border);
            border-radius: 6px;
            padding: 14px;
        }
        .stat-value {
            font-size: 24px;
            font-weight: 700;
            color: var(--text-bright);
            margin-top: 4px;
        }
        .stat-label {
            font-size: 12px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            margin-top: 10px;
        }
        th, td {
            text-align: left;
            padding: 10px 12px;
            border-bottom: 1px solid var(--surface-border);
        }
        th {
            color: var(--text-muted);
            font-weight: 500;
            background-color: var(--code-bg);
        }
        tr:hover {
            background-color: rgba(255, 255, 255, 0.02);
        }
        .code-hash {
            font-family: monospace;
            font-size: 12px;
            color: var(--accent);
        }
        .manifesto-box {
            border-left: 3px solid var(--badge-warn-border);
            background-color: var(--badge-warn-bg);
            padding: 12px 16px;
            border-radius: 0 6px 6px 0;
            font-size: 13px;
            color: var(--badge-warn-text);
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>ShootingStar Research Platform</h1>
                <div class="tagline">Local-first, evidence-first research on BTCUSDT 30-minute predictive modeling</div>
            </div>
            <div>
                <span class="badge badge-success">● System Healthy</span>
            </div>
        </header>

        <div class="manifesto-box">
            <strong>Evidence-First Invariant:</strong> Cost-adjusted 3-class performance and action net expectancy remain strictly <strong>GATED</strong> until an empirical slippage model is approved. No fake win rates, no zero-slippage assumptions.
        </div>

        <div class="card">
            <div class="card-title">
                <span>Model Out-Of-Sample Benchmark (Walk-Forward Horizon)</span>
                <span class="badge badge-warning">COST: UNAVAILABLE_PENDING_SLIPPAGE_METHOD</span>
            </div>
            <div class="grid-2">
                <div class="stat-box">
                    <div class="stat-label">Model Directional Accuracy</div>
                    <div class="stat-value">Chưa kiểm chứng</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Majority Baseline Accuracy</div>
                    <div class="stat-value">Chưa kiểm chứng</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Brier Score Calibration</div>
                    <div class="stat-value">GATED</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Probability Calibration</div>
                    <div class="stat-value">Platt (1D Sigmoid)</div>
                </div>
            </div>
            <div style="font-size: 12px; color: var(--text-muted); margin-top: 12px;">
                * Kết quả kiểm định out-of-sample chính thức chưa được phê duyệt. Vui lòng tham khảo báo cáo thực nghiệm chi tiết qua API <code>/experiments</code>.
            </div>
        </div>

        <div class="card">
            <div class="card-title">
                <span>Rule-Based Pattern Lab (Hypothesis Testing)</span>
                <span class="badge" style="background: #21262d; color: #8b949e;">Declarative Rules</span>
            </div>
            <p style="font-size: 13px; color: var(--text-muted); margin-bottom: 16px;">
                Các mẫu hình được theo dõi tự động qua quy tắc hình học nến rõ ràng. Chưa có kết quả kiểm chứng độc lập nào chứng minh ưu thế vượt trội (edge) có thể khai thác.
            </p>
            <table>
                <thead>
                    <tr>
                        <th>Pattern Name</th>
                        <th>Target Direction</th>
                        <th>Trạng Thái Kiểm Chứng</th>
                        <th>P&L / Expectancy</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Shooting Star</strong></td>
                        <td>DOWN</td>
                        <td>Chưa có kết quả kiểm chứng</td>
                        <td><span class="badge badge-warning">GATED</span></td>
                    </tr>
                    <tr>
                        <td><strong>Hammer</strong></td>
                        <td>UP</td>
                        <td>Chưa có kết quả kiểm chứng</td>
                        <td><span class="badge badge-warning">GATED</span></td>
                    </tr>
                    <tr>
                        <td><strong>Bearish Engulfing</strong></td>
                        <td>DOWN</td>
                        <td>Chưa có kết quả kiểm chứng</td>
                        <td><span class="badge badge-warning">GATED</span></td>
                    </tr>
                    <tr>
                        <td><strong>Bullish Engulfing</strong></td>
                        <td>UP</td>
                        <td>Chưa có kết quả kiểm chứng</td>
                        <td><span class="badge badge-warning">GATED</span></td>
                    </tr>
                </tbody>
            </table>
        </div>

        <div class="card">
            <div class="card-title">
                <span>Data Integrity & Immutable Snapshots</span>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>File / Snapshot</th>
                        <th>Timeframe</th>
                        <th>Candles</th>
                        <th>SHA-256 Hash</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>BINANCE_BTCUSDT_5m_pilot</td>
                        <td>5m</td>
                        <td>8,640</td>
                        <td><span class="code-hash">97f6323ad230cb233157b85e05030fec...</span></td>
                    </tr>
                    <tr>
                        <td>BINANCE_BTCUSDT_1m_pilot</td>
                        <td>1m</td>
                        <td>43,200</td>
                        <td><span class="code-hash">f06ca2a5089e70198031e428407fc366...</span></td>
                    </tr>
                </tbody>
            </table>
        </div>

        <div style="text-align: center; color: var(--text-muted); font-size: 12px; margin-top: 32px;">
            ShootingStar Research Platform &bull; REST API available at <a href="/docs" style="color: var(--accent);">/docs</a> &bull; Append-Only Signals at <a href="/signals" style="color: var(--accent);">/signals</a>
        </div>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html_content)
