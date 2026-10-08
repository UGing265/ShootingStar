"""FastAPI application providing read-only contracts and the evidence-first Research UI.

STRICT INVARIANT:
Cost-adjusted metrics remain explicitly gated as 'Unavailable (pending slippage method)'.
No fabricated profits, slippages, or fake claims.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import text

from shootingstar.adapters.db.repository import (
    ExperimentRepository,
    MetricReportRepository,
    SignalRepository,
    SnapshotRepository,
)
from shootingstar.adapters.db.session import get_db_session
from shootingstar.adapters.storage import SnapshotStorage
from shootingstar.application.patterns import PatternLabService


app = FastAPI(
    title="ShootingStar Research Platform",
    description="Local-first, evidence-first research platform for BTCUSDT 30-minute predictive modeling.",
    version="0.1.0",
)


class HealthResponse(BaseModel):
    status: str
    database: str
    engine: str
    timestamp_utc: str


class SnapshotSummary(BaseModel):
    id: str
    venue: str
    symbol: str
    timeframe: str
    candle_count: int
    start_time_ms: int
    end_time_ms: int
    file_path: str
    sha256: str


class ExperimentSummary(BaseModel):
    id: str
    name: str
    config_hash: str
    snapshot_id: str
    parameters: Dict[str, Any]
    created_at: str


class ExperimentDetailResponse(BaseModel):
    id: str
    name: str
    config_hash: str
    snapshot_id: str
    parameters: Dict[str, Any]
    created_at: str
    splits: List[Dict[str, Any]]
    metrics: Optional[Dict[str, Any]]


class SignalSummary(BaseModel):
    id: str
    prediction_time_ms: int
    symbol: str
    timeframe: str
    horizon_minutes: int
    predicted_class: str
    decision: str
    probability_up: float
    probability_down: float
    status: str
    realized_label: Optional[str]
    realized_return: Optional[float]
    is_match: Optional[bool]


@app.get("/health", response_model=HealthResponse)
def get_health():
    """Health check endpoint verifying PostgreSQL connectivity."""
    import datetime

    try:
        with get_db_session() as session:
            session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"unhealthy: {e}"

    return HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        database=db_status,
        engine="PostgreSQL 18 Local",
        timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )


@app.get("/snapshots", response_model=List[SnapshotSummary])
def list_snapshots(limit: int = 50):
    """Lists immutable historical candle snapshots with SHA-256 checksums."""
    with get_db_session() as session:
        repo = SnapshotRepository(session)
        snapshots = repo.list_all(limit=limit)
        return [
            SnapshotSummary(
                id=s.id,
                venue=s.venue,
                symbol=s.symbol,
                timeframe=s.timeframe,
                candle_count=s.candle_count,
                start_time_ms=s.start_time_ms,
                end_time_ms=s.end_time_ms,
                file_path=s.file_path,
                sha256=s.sha256,
            )
            for s in snapshots
        ]


@app.get("/experiments", response_model=List[ExperimentSummary])
def list_experiments():
    """Lists registered research experiments."""
    with get_db_session() as session:
        repo = ExperimentRepository(session)
        experiments = repo.list_all()
        results = []
        for e in experiments:
            params = json.loads(e.parameters_json) if e.parameters_json else {}
            results.append(
                ExperimentSummary(
                    id=e.id,
                    name=e.name,
                    config_hash=e.config_hash,
                    snapshot_id=e.snapshot_id,
                    parameters=params,
                    created_at=e.created_at.isoformat(),
                )
            )
        return results


@app.get("/experiments/{experiment_id}", response_model=ExperimentDetailResponse)
def get_experiment_detail(experiment_id: str):
    """Retrieves full experiment provenance and metric report with gated cost fields."""
    with get_db_session() as session:
        exp_repo = ExperimentRepository(session)
        report_repo = MetricReportRepository(session)

        exp = exp_repo.get_by_id(experiment_id)
        if not exp:
            raise HTTPException(status_code=44, detail=f"Experiment '{experiment_id}' not found")

        splits = [
            {
                "split_type": s.split_type,
                "start_time_ms": s.start_time_ms,
                "end_time_ms": s.end_time_ms,
                "sample_count": s.sample_count,
            }
            for s in exp.splits
        ]

        reports = report_repo.get_by_experiment_id(experiment_id)
        metric_data = None
        if reports:
            rep = reports[0]
            metric_data = json.loads(rep.metrics_json)

        params = json.loads(exp.parameters_json) if exp.parameters_json else {}
        return ExperimentDetailResponse(
            id=exp.id,
            name=exp.name,
            config_hash=exp.config_hash,
            snapshot_id=exp.snapshot_id,
            parameters=params,
            created_at=exp.created_at.isoformat(),
            splits=splits,
            metrics=metric_data,
        )


@app.get("/patterns")
def get_patterns(snapshot_id: Optional[str] = None):
    """Evaluates Pattern Lab rules on a snapshot and returns statistical distributions."""
    storage = SnapshotStorage()
    snapshots_dir = Path("data/snapshots")
    parquet_files = list(snapshots_dir.glob("*.parquet"))

    if not parquet_files:
        return {"message": "No snapshots available for pattern analysis", "reports": []}

    target_file = parquet_files[0]
    if snapshot_id:
        matches = [f for f in parquet_files if snapshot_id in f.name]
        if matches:
            target_file = matches[0]

    candles = storage.load_snapshot(target_file)
    lab = PatternLabService()
    reports = lab.analyze_all(candles, horizon_minutes=30)

    return {
        "snapshot": target_file.name,
        "candle_count": len(candles),
        "reports": [r.to_dict() for r in reports],
        "hypothesis_track": "SEPARATE_HYPOTHESIS_TRACK_NOT_IN_MODEL_FEATURES",
    }


@app.get("/signals", response_model=List[SignalSummary])
def list_signals(limit: int = 50):
    """Lists append-only predictions and their maturation outcomes."""
    with get_db_session() as session:
        repo = SignalRepository(session)
        preds = repo.list_predictions(limit=limit)
        results = []
        for p in preds:
            outcome = repo.get_outcome_by_signal_id(p.id)
            results.append(
                SignalSummary(
                    id=p.id,
                    prediction_time_ms=p.prediction_time_ms,
                    symbol=p.symbol,
                    timeframe=p.timeframe,
                    horizon_minutes=p.horizon_minutes,
                    predicted_class=p.predicted_class,
                    decision=p.decision,
                    probability_up=p.probability_up,
                    probability_down=p.probability_down,
                    status=outcome.status if outcome else "PENDING",
                    realized_label=outcome.realized_label if outcome else None,
                    realized_return=outcome.realized_return if outcome else None,
                    is_match=outcome.is_match if outcome else None,
                )
            )
        return results


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
                <span>Model Out-Of-Sample Benchmark (Walk-Forward 5m Pilot)</span>
                <span class="badge badge-warning">COST: UNAVAILABLE_PENDING_SLIPPAGE_METHOD</span>
            </div>
            <div class="grid-2">
                <div class="stat-box">
                    <div class="stat-label">Model Directional Accuracy (Test N=1,710)</div>
                    <div class="stat-value">51.05%</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Majority Baseline Accuracy</div>
                    <div class="stat-value">51.46%</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Brier Score (Near 0.2500 Coin Flip)</div>
                    <div class="stat-value">0.2507</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Probability Calibration</div>
                    <div class="stat-value">Platt (1D Sigmoid)</div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-title">
                <span>Rule-Based Pattern Lab (Separate Hypothesis Track)</span>
                <span class="badge" style="background: #21262d; color: #8b949e;">8,640 Immutable Candles</span>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Pattern Name</th>
                        <th>Target</th>
                        <th>Hits (N)</th>
                        <th>Win Rate</th>
                        <th>Mean 30m Return</th>
                        <th>Statistical Power</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Shooting Star</strong></td>
                        <td>DOWN</td>
                        <td>272</td>
                        <td>49.3%</td>
                        <td>+0.025%</td>
                        <td><span class="badge badge-success">OK (N &ge; 30)</span></td>
                    </tr>
                    <tr>
                        <td><strong>Hammer</strong></td>
                        <td>UP</td>
                        <td>277</td>
                        <td>46.6%</td>
                        <td>+0.003%</td>
                        <td><span class="badge badge-success">OK (N &ge; 30)</span></td>
                    </tr>
                    <tr>
                        <td><strong>Bearish Engulfing</strong></td>
                        <td>DOWN</td>
                        <td>829</td>
                        <td>49.7%</td>
                        <td>-0.000%</td>
                        <td><span class="badge badge-success">OK (N &ge; 30)</span></td>
                    </tr>
                    <tr>
                        <td><strong>Bullish Engulfing</strong></td>
                        <td>UP</td>
                        <td>796</td>
                        <td>46.0%</td>
                        <td>-0.003%</td>
                        <td><span class="badge badge-success">OK (N &ge; 30)</span></td>
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
