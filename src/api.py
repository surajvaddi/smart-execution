"""FastAPI interface for the smart execution backend."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.backtester import Backtester
from src.fill_simulator import DEFAULT_FILL_MODEL, DEFAULT_RANDOM_SEED, PLACEMENT_STYLES
from src.services import (
    load_processed_data,
    preview_execution_fills,
    run_backtest,
    run_execution_grid,
    run_signal_research,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"


class DataRequest(BaseModel):
    """Common request payload for CSV-backed analysis endpoints."""

    input_csv: str
    max_orders_per_ticker: Optional[int] = Field(default=1, ge=1)
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    adaptive_weights: Optional[Dict[str, float]] = None


class ExecutionGridRequest(DataRequest):
    """Request payload for execution-grid analysis."""

    placement_styles: Optional[List[str]] = None
    fill_model: str = DEFAULT_FILL_MODEL
    random_seed: Optional[int] = DEFAULT_RANDOM_SEED
    fill_row_limit: int = Field(default=500, ge=0, le=10_000)


class SignalRequest(DataRequest):
    """Request payload for signal analysis."""

    horizons: Optional[List[int]] = None


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(
        title="Smart Execution API",
        version="0.1.0",
        description="JSON API for smart execution backtests and execution-grid analysis.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/datasets")
    def datasets() -> Dict[str, List[Dict[str, Any]]]:
        files = []
        for path in sorted(PROCESSED_DATA_DIR.glob("*.csv")):
            try:
                row_count = sum(1 for _ in path.open("r", encoding="utf-8")) - 1
            except OSError:
                row_count = None
            files.append(
                {
                    "name": path.name,
                    "path": str(path.relative_to(PROJECT_ROOT)),
                    "rows": row_count,
                }
            )
        return {"datasets": files}

    @app.post("/api/backtest")
    def backtest(request: DataRequest) -> Dict[str, Any]:
        data = _load_request_data(request)
        results = run_backtest(
            data,
            adaptive_weights=request.adaptive_weights,
            max_orders_per_ticker=request.max_orders_per_ticker,
        )
        summary = Backtester(
            tickers=sorted(results["ticker"].unique().tolist()),
            max_orders_per_ticker=request.max_orders_per_ticker,
        ).summarize_by_strategy(results)
        return {
            "results": _frame_records(results),
            "summary": _frame_records(summary),
            "meta": _meta(data, results),
        }

    @app.post("/api/execution-grid")
    def execution_grid(request: ExecutionGridRequest) -> Dict[str, Any]:
        _validate_placement_styles(request.placement_styles)
        data = _load_request_data(request)
        grid = run_execution_grid(
            data,
            placement_styles=request.placement_styles,
            adaptive_weights=request.adaptive_weights,
            fill_model=request.fill_model,
            random_seed=request.random_seed,
            max_orders_per_ticker=request.max_orders_per_ticker,
        )
        backtester = Backtester(
            tickers=sorted(grid.results["ticker"].unique().tolist()),
            max_orders_per_ticker=request.max_orders_per_ticker,
        )
        strategy_summary = backtester.summarize_by_strategy(grid.results)
        placement_summary = backtester.summarize_by_placement(grid.results)
        strategy_placement_summary = backtester.summarize_by_strategy_placement(grid.results)
        fills = preview_execution_fills(grid.fills, request.fill_row_limit)
        return {
            "results": _frame_records(grid.results),
            "fills": _frame_records(fills),
            "summary_by_strategy": _frame_records(strategy_summary),
            "summary_by_placement": _frame_records(placement_summary),
            "summary_by_strategy_placement": _frame_records(strategy_placement_summary),
            "meta": {
                **_meta(data, grid.results),
                "fill_rows_returned": len(fills),
                "fill_rows_total": len(grid.fills),
            },
        }

    @app.post("/api/signals")
    def signals(request: SignalRequest) -> Dict[str, Any]:
        data = _load_request_data(request)
        result = run_signal_research(data, horizons=request.horizons)
        return {
            "evaluation": _frame_records(result.evaluation),
            "decay": _frame_records(result.decay),
            "summary": _frame_records(result.summary),
            "meta": {"rows": len(data)},
        }

    return app


def _load_request_data(request: DataRequest) -> pd.DataFrame:
    """Load request data or return a concise HTTP error."""
    try:
        return load_processed_data(
            _resolve_input_csv(request.input_csv),
            start_date=request.start_date,
            end_date=request.end_date,
            start_time=request.start_time,
            end_time=request.end_time,
        )
    except (FileNotFoundError, ValueError, KeyError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _resolve_input_csv(input_csv: str) -> Path:
    """Resolve a dataset path without allowing traversal outside the project."""
    raw_path = Path(input_csv)
    if raw_path.is_absolute():
        path = raw_path.resolve()
    else:
        path = (PROJECT_ROOT / raw_path).resolve()
    if PROJECT_ROOT not in path.parents and path != PROJECT_ROOT:
        raise ValueError("input_csv must be inside the project directory.")
    if not path.exists():
        raise FileNotFoundError(f"Input CSV does not exist: {input_csv}")
    return path


def _validate_placement_styles(placement_styles: Optional[List[str]]) -> None:
    """Validate placement styles before running a grid."""
    if placement_styles is None:
        return
    invalid = sorted(set(placement_styles) - set(PLACEMENT_STYLES))
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid placement styles: {invalid}",
        )


def _frame_records(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    """Return JSON-safe records from a DataFrame."""
    safe = frame.copy()
    for column in safe.columns:
        if pd.api.types.is_timedelta64_dtype(safe[column]):
            safe[column] = safe[column].astype(str)
    safe = safe.astype(object).where(pd.notnull(safe), None)
    records = safe.to_dict(orient="records")
    return [{key: _json_value(value) for key, value in row.items()} for row in records]


def _json_value(value: Any) -> Any:
    """Convert common pandas/numpy values into JSON-serializable values."""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def _meta(data: pd.DataFrame, results: pd.DataFrame) -> Dict[str, Any]:
    """Return compact metadata for UI display."""
    return {
        "market_rows": len(data),
        "result_rows": len(results),
        "tickers": sorted(data["ticker"].dropna().unique().tolist()) if "ticker" in data else [],
    }


app = create_app()
