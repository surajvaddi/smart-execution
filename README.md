# Smart Execution Backtester

A Python research backtester for smart order execution and transaction cost analysis using intraday Yahoo Finance OHLCV data.

The project compares TWAP, VWAP, POV, and adaptive signal-aware execution strategies across simulated parent orders. It builds microstructure-inspired features from bar data, evaluates short-horizon alpha signals, simulates child-order execution, estimates synthetic transaction costs, and summarizes execution quality with implementation shortfall and related TCA metrics.

## What This Project Does

The system follows a full execution research pipeline:

```text
Yahoo Finance OHLCV data
-> cleaned intraday bars
-> microstructure proxy features
-> short-horizon signal research
-> simulated parent orders
-> TWAP / VWAP / POV / Adaptive child orders
-> synthetic fills with spread and impact costs
-> parent-order TCA metrics
-> strategy comparison tables
```

The main research question is:

```text
Can adaptive execution reduce implementation shortfall by reacting to OHLCV-based
signals for volume, volatility, liquidity, spread, imbalance, and short-term alpha?
```

## Important Data Limitation

Yahoo Finance does not provide full limit order book data. It does not include bid, ask, depth, queue position, cancellations, or true order flow.

This project therefore uses OHLCV-derived proxies:

- `spread_proxy` approximates trading cost and uncertainty using high-low range.
- `signed_volume` approximates buyer/seller pressure from bar direction.
- `ofi_proxy` approximates order-flow imbalance from rolling signed volume.
- `liquidity_score` combines high volume, low spread proxy, and low volatility.
- synthetic bid/ask prices are modeled from close price and spread proxy.

These are research approximations, not production execution models or real market microstructure measurements.

## Current Capabilities

Implemented phases:

```text
Phase 0: Project scaffold
Phase 1: Yahoo Finance intraday data loading
Phase 2: Microstructure proxy features
Phase 3: Alpha signal research
Phase 4: Parent order simulation
Phase 5: Execution strategies
Phase 6: Transaction cost model
Phase 7: TCA metrics
Phase 8: Backtest loop
```

Implemented execution strategies:

- TWAP: evenly splits quantity across time.
- VWAP: follows the historical intraday volume curve while respecting participation caps.
- POV: trades as a capped percentage of realized market volume.
- Adaptive: adjusts execution speed using alpha signal, liquidity, spread, volatility, urgency, and participation cap.

Implemented TCA metrics:

- average fill price
- arrival price
- market VWAP
- implementation shortfall bps
- VWAP slippage bps
- spread cost bps
- impact cost bps
- timing cost bps
- opportunity cost bps
- fill rate
- execution duration

## Repository Layout

```text
.
├── main.py
├── requirements.txt
├── CODEX_LOG.md
├── data/
│   ├── raw/
│   └── processed/
├── reports/
│   └── figures/
└── src/
    ├── data_loader.py
    ├── features.py
    ├── signals.py
    ├── execution.py
    ├── strategies.py
    ├── tca.py
    ├── backtester.py
    └── plots.py
```

## Installation

```bash
python3 -m pip install -r requirements.txt
```

The project has been developed against Python 3.8 in this local environment. `requirements.txt` includes a Python 3.8-compatible `multitasking` pin required by `yfinance`.

## Quick Start

From the repository root:

```bash
python3 main.py
```

This prints the available smoke-test commands.

### Download Sample Data

```bash
python3 main.py --download-sample --ticker SPY --period 5d --interval 5m
```

Outputs:

```text
data/raw/SPY_5d_5m.csv
data/processed/SPY_5d_5m.csv
```

The data loader converts Yahoo timestamps to `America/New_York` before deriving `date`, `time`, and `bar_index`.

### Build Features

```bash
python3 main.py --feature-sample --input-csv data/processed/SPY_5d_5m.csv
```

Adds:

```text
spread_proxy
signed_volume
ofi_proxy
rolling_vol
volume_zscore
momentum_3
reversal_3
liquidity_score
alpha_signal
```

### Evaluate Signals

```bash
python3 main.py --signal-sample --input-csv data/processed/SPY_5d_5m.csv
```

Outputs:

```text
reports/signal_evaluation_SPY_5d_5m.csv
reports/signal_decay_SPY_5d_5m.csv
reports/signal_summary_SPY_5d_5m.csv
reports/signal_notes_SPY_5d_5m.md
```

Signal metrics:

- information coefficient
- hit rate
- decile spread
- signal decay by horizon

Default horizons:

```text
1 bar  = 5 minutes
3 bars = 15 minutes
6 bars = 30 minutes
12 bars = 60 minutes
```

### Generate Parent Orders

```bash
python3 main.py --orders-sample --input-csv data/processed/SPY_5d_5m.csv
```

Outputs:

```text
reports/parent_orders_SPY_5d_5m.csv
```

Parent orders are generated across:

- buy and sell sides
- 1%, 5%, and 10% of average daily volume
- `10:00-15:30`, `10:00-12:00`, and `13:00-15:30` execution windows
- 10% participation cap

### Generate Strategy Schedules

```bash
python3 main.py --twap-sample --input-csv data/processed/SPY_5d_5m.csv
python3 main.py --vwap-sample --input-csv data/processed/SPY_5d_5m.csv
python3 main.py --pov-sample --input-csv data/processed/SPY_5d_5m.csv
python3 main.py --adaptive-sample --input-csv data/processed/SPY_5d_5m.csv
```

Outputs:

```text
reports/twap_child_orders_SPY_5d_5m.csv
reports/vwap_child_orders_SPY_5d_5m.csv
reports/pov_child_orders_SPY_5d_5m.csv
reports/adaptive_child_orders_SPY_5d_5m.csv
```

Compare schedules:

```bash
python3 main.py --strategy-compare-sample --input-csv data/processed/SPY_5d_5m.csv
```

Output:

```text
reports/strategy_schedule_comparison_SPY_5d_5m.csv
```

### Apply Transaction Cost Model

```bash
python3 main.py --tca-sample --input-csv data/processed/SPY_5d_5m.csv
```

Output:

```text
reports/tca_fills_SPY_5d_5m.csv
```

The cost model adds:

```text
mid_price
synthetic_bid
synthetic_ask
half_spread
temporary_impact
permanent_impact
impact_cost
spread_cost
fill_price
```

Synthetic quotes:

```python
mid_price = close
half_spread = 0.5 * spread_proxy * mid_price
synthetic_bid = mid_price - half_spread
synthetic_ask = mid_price + half_spread
```

Impact model:

```python
temporary_impact = eta * mid_price * (child_quantity / volume) ** beta
permanent_impact = gamma * mid_price * (child_quantity / volume)
```

Default parameters:

```text
eta = 0.10
beta = 0.5
gamma = 0.02
```

These defaults come from the initial research specification and may require calibration for realistic use.

### Compute TCA Metrics

```bash
python3 main.py --tca-metrics-sample --input-csv data/processed/SPY_5d_5m.csv
```

Output:

```text
reports/tca_metrics_SPY_5d_5m.csv
```

### Run Backtest Sample

```bash
python3 main.py --backtest-sample --input-csv data/processed/SPY_5d_5m.csv
```

Outputs:

```text
reports/backtest_results_SPY_5d_5m.csv
reports/backtest_summary_SPY_5d_5m.csv
```

The sample backtest runs one generated parent order across all registered strategies:

```text
TWAP
VWAP
POV
Adaptive
```

### Narrow The Date Or Time Range

Most commands that read `--input-csv` also accept optional inclusive filters:

```bash
--start-date YYYY-MM-DD
--end-date YYYY-MM-DD
--start-time HH:MM
--end-time HH:MM
```

Date filters must be provided as a pair. Time filters must also be provided as a pair. For example, this is valid:

```bash
python3 main.py \
  --backtest-sample \
  --input-csv data/processed/SPY_5d_5m.csv \
  --start-date 2026-04-29 \
  --end-date 2026-05-01 \
  --start-time 10:00 \
  --end-time 14:00
```

This is rejected because the end date is missing:

```bash
python3 main.py --backtest-sample --start-date 2026-04-29
```

### Multi-Ticker Commands

Download multiple tickers into separate raw and processed CSVs:

```bash
python3 main.py \
  --download-tickers SPY QQQ AAPL MSFT NVDA \
  --period 5d \
  --interval 5m
```

Create a timestamp alignment report across multiple processed CSVs:

```bash
python3 main.py \
  --alignment-report \
  --input-csvs data/processed/SPY_5d_5m.csv data/processed/QQQ_5d_5m.csv
```

Output:

```text
reports/alignment_report_multi.csv
```

Run an independent multi-ticker backtest:

```bash
python3 main.py \
  --backtest-multi \
  --input-csvs data/processed/SPY_5d_5m.csv data/processed/QQQ_5d_5m.csv \
  --max-orders-per-ticker 1
```

Outputs:

```text
reports/backtest_results_multi.csv
reports/backtest_summary_by_strategy_multi.csv
reports/backtest_summary_by_ticker_multi.csv
reports/backtest_summary_by_ticker_strategy_multi.csv
```

This is an independent multi-ticker backtest. It runs each ticker through the execution and TCA pipeline separately, then combines the result rows. It does not yet coordinate child orders on a shared portfolio execution clock.

Create a multi-ticker execution tape and timestamp-level activity summary:

```bash
python3 main.py \
  --execution-tape \
  --input-csvs data/processed/SPY_5d_5m.csv data/processed/QQQ_5d_5m.csv \
  --max-orders-per-ticker 1
```

Outputs:

```text
reports/execution_tape_multi.csv
reports/execution_summary_by_timestamp_multi.csv
```

The execution tape is a long-form table of generated child orders across tickers and strategies. The timestamp summary aggregates that tape by timestamp and strategy:

```text
timestamp
strategy
active_tickers
child_orders
total_quantity
total_notional
```

This helps identify when execution is concentrated across multiple assets. It still does not model cross-asset market impact or portfolio risk.

## Reading The Outputs

Best starting points:

```text
CODEX_LOG.md
reports/signal_notes_SPY_5d_5m.md
reports/strategy_schedule_comparison_SPY_5d_5m.csv
reports/tca_fills_SPY_5d_5m.csv
reports/backtest_summary_SPY_5d_5m.csv
```

`CODEX_LOG.md` is a development log that explains what was added phase by phase.

`reports/backtest_summary_SPY_5d_5m.csv` is the highest-level output. It compares strategies by average TCA metrics.

## Architecture Notes

### Data Layer

`src/data_loader.py`

- downloads Yahoo Finance intraday data
- cleans OHLCV columns
- adds returns, dollar volume, date, time, bar index, and ticker
- saves raw and processed CSVs

### Feature Layer

`src/features.py`

- builds OHLCV-derived microstructure proxy features
- estimates historical intraday volume curve
- creates a first-pass composite `alpha_signal`

### Signal Research

`src/signals.py`

- adds forward returns
- computes information coefficient, hit rate, and decile spread
- creates signal decay and signal quality summary tables

### Parent Orders

`src/execution.py`

- defines `ParentOrder`
- computes average daily volume
- generates parent order grids by side, size, window, and participation cap

### Strategies

`src/strategies.py`

- defines child-order schema
- implements TWAP, VWAP, POV, and Adaptive schedules
- enforces participation caps

### TCA

`src/tca.py`

- creates synthetic bid/ask prices
- estimates temporary and permanent impact
- computes fill prices
- computes parent-order TCA metrics

### Backtester

`src/backtester.py`

- registers default strategies
- prepares local processed data
- runs order-strategy simulations
- saves detailed results and strategy summaries

## Current Limitations

- Uses OHLCV bars, not full order book data.
- Synthetic bid/ask prices are deterministic and proxy-based.
- Impact parameters are not calibrated to real market impact data.
- Current CLI sample backtest runs a limited local SPY sample by default.
- Plotting functions and final report generation are not yet implemented.
- No interactive frontend exists yet.

## Roadmap

Planned next phases:

```text
Phase 9: Required plots
Phase 10: Experiments and robustness tests
Phase 11: Final report
Optional: Streamlit dashboard frontend
```

Useful future extensions:

- multi-ticker batch backtests
- configurable impact parameters
- noisy spread robustness experiments
- adaptive strategy ablations
- high-volatility and low-liquidity regime analysis
- Streamlit dashboard for strategy comparison
- true limit order book data integration

## Resume Summary

Built a Python smart execution and transaction cost analysis backtester using intraday Yahoo Finance data, comparing TWAP, VWAP, POV, and adaptive signal-aware execution strategies across simulated parent orders.

Engineered OHLCV-based market microstructure proxies including spread, signed volume, order flow imbalance, rolling volatility, liquidity score, volume curve, momentum, and reversal features.

Decomposed implementation shortfall into spread cost, market impact, timing cost, and opportunity cost to evaluate whether adaptive execution reduced transaction costs relative to baseline algorithms.

Tested short-horizon alpha signal decay across multiple prediction horizons using information coefficient, hit rate, and decile spread analysis.
