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
-> market / limit / pegged placement styles
-> deterministic synthetic fill simulation
-> spread, impact, timing, and opportunity costs
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

## Current Vs Target Architecture

The repository currently supports a bar-based execution research stack and does not yet implement a true event-level limit order book simulator.

Current path:

```text
processed OHLCV data
-> proxy features
-> parent orders
-> TWAP / VWAP / POV / Adaptive schedules
-> synthetic placement and fill models
-> TCA and strategy comparison
```

Target path:

```text
instrument metadata
-> synthetic exchange state
-> order arrivals, cancels, and market orders
-> price-time priority matching engine
-> queue-aware execution interaction
-> event-level fills and LOB-aware TCA
```

That target architecture is specified in:

- `docs/architecture/target_research_stack.md`
- `docs/research_execution_master_plan.md`

The current code should be described as:

- a bar-based execution backtester with microstructure-inspired proxy features
- a synthetic fill-simulation research tool
- not yet a true exchange-state limit order book simulator

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
- adverse selection cost bps
- timing cost bps
- opportunity cost bps
- fill rate
- execution duration

Implemented placement and fill simulation:

- market orders
- marketable limits
- aggressive limits
- midpoint limits
- passive limits
- primary pegs
- midpoint pegs
- adaptive limits
- deterministic OHLCV touch-based fill simulation
- queue-weighted touch simulation for more conservative limit fills
- seeded stochastic queue-touch simulation for probabilistic limit fills

Implemented RL research layer:

- bar-by-bar `ExecutionEnv` episodes for parent orders
- discrete ensemble actions across rate and placement choices
- random and heuristic policies
- simple tabular Q-learning trainer
- RL backtest helper that produces comparable TCA rows

## Repository Layout

```text
.
├── main.py
├── pyproject.toml
├── Makefile
├── requirements.txt
├── CODEX_LOG.md
├── frontend/
│   ├── src/
│   └── package.json
├── docs/
│   └── limit_order_fill_simulator_plan.md
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
    ├── fill_simulator.py
    ├── rl_env.py
    ├── rl_policy.py
    ├── rl_train.py
    ├── rl_backtester.py
    ├── tca.py
    ├── backtester.py
    ├── services.py
    ├── api.py
    └── plots.py
```

## Installation

```bash
python3 -m pip install -r requirements.txt
```

The project has been developed against Python 3.8 in this local environment. `requirements.txt` includes a Python 3.8-compatible `multitasking` pin required by `yfinance`.

Common development commands:

```bash
make test
make api
make install-frontend
make frontend
make frontend-build
```

Generated raw data, processed data, report outputs, frontend build output, and model artifacts are ignored for future runs. The committed `reports/` files are retained as sample outputs for reference.

## Web App

The project now includes a FastAPI backend and React/Vite frontend for interactive inspection of saved processed CSVs.

Run the API from the repository root:

```bash
uvicorn src.api:app --reload --host 127.0.0.1 --port 8000
```

In this Python 3.8 environment, use the Makefile command if uvicorn attempts to use uvloop:

```bash
make api
```

Run the frontend in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend is served at:

```text
http://127.0.0.1:5173
```

Current dashboard views:

- dataset selector for `data/processed/*.csv`
- strategy backtest summary
- implementation shortfall and fill-rate charts
- execution-grid heatmap by strategy and placement style
- fill tape preview table

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

### Run The Execution Placement Grid

```bash
python3 main.py \
  --execution-grid-sample \
  --input-csv data/processed/SPY_5d_5m.csv \
  --max-orders-per-ticker 1
```

Outputs:

```text
reports/execution_grid_fills.csv
reports/execution_grid_results.csv
reports/execution_grid_summary_by_strategy.csv
reports/execution_grid_summary_by_placement.csv
reports/execution_grid_summary_by_strategy_placement.csv
```

The execution grid compares:

```text
TWAP / VWAP / POV / Adaptive
```

against:

```text
market
marketable_limit
aggressive_limit
midpoint_limit
passive_limit
primary_peg
midpoint_peg
adaptive_limit
```

You can narrow the placement set:

```bash
python3 main.py \
  --execution-grid-sample \
  --input-csv data/processed/SPY_5d_5m.csv \
  --placement-styles market passive_limit midpoint_limit adaptive_limit
```

The grid keeps schedule logic separate from placement logic. TWAP, VWAP, POV,
and Adaptive decide the child-order rate. Placement styles decide whether that
child order is submitted as marketable, passive, midpoint, pegged, or adaptive
limit liquidity.

The default fill model is:

```text
volume_capped_touch
```

This fills touched limits up to a placement-specific share of available bar
volume. A more conservative model is also available:

```bash
python3 main.py \
  --execution-grid-sample \
  --input-csv data/processed/SPY_5d_5m.csv \
  --fill-model queue_weighted_touch
```

`queue_weighted_touch` still uses OHLCV bars, but it scales touched limit fills
by how deeply the bar traded through the limit and a queue-priority proxy. It is
not a real order-book queue model, but it is more conservative than treating
every touch as equally fillable.

A stochastic model is available for seeded random fill/no-fill outcomes:

```bash
python3 main.py \
  --execution-grid-sample \
  --input-csv data/processed/SPY_5d_5m.csv \
  --fill-model stochastic_queue_touch \
  --random-seed 42
```

`stochastic_queue_touch` uses the same touch-depth and queue-priority proxy to
estimate fill probability, then draws a seeded random number for each touched
limit order. If the draw is above the modeled probability, the order misses even
though the bar touched the limit. Market and marketable-limit placements still
fill immediately.

The fill simulator also records a pessimistic adverse-selection proxy:

- `post_fill_return`: next-bar signed return after the fill, where negative is adverse.
- `adverse_selection_cost`: per-share cost when a non-marketable limit fill is followed by adverse next-bar movement.
- `adverse_selection_cost_bps`: TCA summary metric for that cost.

This models the common backtest problem where passive orders appear cheap
because they fill at favorable prices, but those fills may happen right before
the market moves against the trade.

Fill model assumptions can be tuned from the CLI:

```bash
python3 main.py \
  --execution-grid-sample \
  --input-csv data/processed/SPY_5d_5m.csv \
  --fill-model queue_weighted_touch \
  --fill-capacity-multiplier passive_limit=0.15 \
  --fill-queue-priority passive_limit=0.20
```

Available config flags:

```text
--fill-capacity-multiplier STYLE=VALUE
--fill-queue-priority STYLE=VALUE
--default-fill-capacity-multiplier VALUE
--default-fill-queue-priority VALUE
```

`STYLE` is one of the placement styles, such as `passive_limit`,
`aggressive_limit`, `midpoint_limit`, `primary_peg`, or `midpoint_peg`.
Capacity multipliers control how much bar volume is available after the parent
order participation cap. Queue priorities control the probability proxy used by
`queue_weighted_touch` and `stochastic_queue_touch`. Queue priorities must be
between `0` and `1`; capacity multipliers must be non-negative.

### Monte Carlo Execution Summaries

Use Monte Carlo summaries when you want to understand how sensitive the
execution grid is to stochastic fill outcomes:

```bash
python3 main.py \
  --monte-carlo-execution-grid \
  --input-csv data/processed/SPY_5d_5m.csv \
  --monte-carlo-paths 25 \
  --max-orders-per-ticker 1
```

Outputs:

```text
reports/monte_carlo_results_SPY_5d_5m.csv
reports/monte_carlo_fills_SPY_5d_5m.csv
reports/monte_carlo_summary_SPY_5d_5m.csv
```

The Monte Carlo path reruns the same strategy-by-placement grid across a range
of random seeds. If `--fill-model` is left at its deterministic default, the
CLI uses `stochastic_queue_touch` for this command so the repeated paths have
fill uncertainty. You can still override it explicitly with `--fill-model`.

The summary groups by `strategy` and `placement_style`, then reports:

```text
num_paths
num_simulations
mean / median / p10 / p90 / std for each main TCA metric
```

This is useful for comparing not only average cost, but also downside cases.
For example, `implementation_shortfall_bps_p90` shows a worse-tail simulated
outcome for a strategy-placement pair, while `fill_rate_p10` highlights
placements that often leave inventory behind.

### Report Plots

Generate static PNG plots from saved summary CSVs:

```bash
python3 main.py --plot-reports
```

Default outputs:

```text
reports/figures/strategy_tca_costs.png
reports/figures/strategy_fill_rates.png
reports/figures/execution_grid_shortfall_heatmap.png
reports/figures/execution_grid_fill_rate_heatmap.png
```

If a matching Monte Carlo summary exists, the command also writes:

```text
reports/figures/monte_carlo_shortfall_intervals.png
reports/figures/monte_carlo_fill_rate_intervals.png
```

Useful overrides:

```bash
python3 main.py \
  --plot-reports \
  --plot-backtest-summary-csv reports/backtest_summary_SPY_5d_5m.csv \
  --plot-execution-grid-summary-csv reports/execution_grid_summary_by_strategy_placement.csv \
  --plot-monte-carlo-summary-csv reports/monte_carlo_summary_SPY_5d_5m.csv \
  --plot-output-dir reports/figures
```

### Adaptive Ensemble RL Execution

The RL research layer treats each parent order as a bar-by-bar episode. At each
bar, an agent observes only current and prior information, then chooses one
discrete execution action:

```text
0 = wait
1 = TWAP-sized marketable child order
2 = VWAP-sized marketable child order
3 = POV-sized marketable child order
4 = Adaptive-sized marketable child order
5 = passive limit, small quantity
6 = passive limit, medium quantity
7 = aggressive limit, small quantity
8 = aggressive limit, medium quantity
```

The environment reuses the existing fill simulator and TCA path. This keeps RL
results comparable with TWAP, VWAP, POV, and Adaptive strategy results while
leaving the existing baseline APIs unchanged.

Key modules:

```text
src/rl_env.py         ExecutionEnv and RewardConfig
src/rl_policy.py      RandomPolicy and HeuristicExecutionPolicy
src/rl_train.py       small tabular Q-learning utilities
src/rl_backtester.py  helper for comparable RL TCA result rows
```

This is a research simulator, not production execution logic. It uses OHLCV
proxy features, synthetic bid/ask prices, and modeled fills rather than real
order book queue state.

Run a sample RL backtest:

```bash
python3 main.py \
  --rl-backtest-sample \
  --input-csv data/processed/SPY_5d_5m.csv \
  --rl-policy heuristic \
  --max-orders-per-ticker 1
```

Outputs:

```text
reports/rl_backtest_results_SPY_5d_5m.csv
```

Available RL policies:

```text
heuristic
random
qtable
```

Use `--q-table-path artifacts/models/q_policy.pkl` with `--rl-policy qtable`
after training a Q-table.

Train a small tabular Q policy:

```bash
python3 main.py \
  --rl-train-q \
  --input-csv data/processed/SPY_5d_5m.csv \
  --max-orders-per-ticker 1 \
  --q-episodes 10 \
  --q-table-path artifacts/models/q_policy.pkl
```

Then evaluate it:

```bash
python3 main.py \
  --rl-backtest-sample \
  --input-csv data/processed/SPY_5d_5m.csv \
  --rl-policy qtable \
  --q-table-path artifacts/models/q_policy.pkl
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

Run the execution placement grid independently across multiple ticker CSVs:

```bash
python3 main.py \
  --execution-grid-multi \
  --input-csvs data/processed/SPY_5d_5m.csv data/processed/QQQ_5d_5m.csv \
  --max-orders-per-ticker 1
```

This writes the same execution-grid reports as the single-CSV command, with
`source_csv` included in the detailed result and fill rows.

## Reading The Outputs

Best starting points:

```text
CODEX_LOG.md
reports/signal_notes_SPY_5d_5m.md
reports/strategy_schedule_comparison_SPY_5d_5m.csv
reports/tca_fills_SPY_5d_5m.csv
reports/backtest_summary_SPY_5d_5m.csv
reports/execution_grid_summary_by_strategy_placement.csv
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

### Fill Simulator

`src/fill_simulator.py`

- converts child-order intent into market, limit, pegged, or adaptive placements
- uses synthetic bid/ask prices from the TCA layer
- simulates full, partial, and missed fills using OHLCV touch rules
- optionally applies queue-weighted touch depth for more conservative fills
- optionally applies seeded stochastic fill/no-fill draws for touched limits
- records next-bar adverse-selection cost for non-marketable limit fills
- preserves submitted quantity separately from filled quantity

### TCA

`src/tca.py`

- creates synthetic bid/ask prices
- estimates temporary and permanent impact
- computes fill prices
- computes parent-order TCA metrics
- supports partial and zero-fill rows from the fill simulator

### Backtester

`src/backtester.py`

- registers default strategies
- prepares local processed data
- runs order-strategy simulations
- saves detailed results and strategy summaries
- runs execution grids across strategies and placement styles

### Service And API Layer

`src/services.py`, `src/api.py`

- exposes callable backend functions for the CLI, API, and frontend
- loads and filters processed CSVs
- runs backtests, execution grids, signal research, RL backtests, and Monte Carlo grids
- serializes result tables for the FastAPI dashboard API

### RL Research Layer

`src/rl_env.py`, `src/rl_policy.py`, `src/rl_train.py`, `src/rl_backtester.py`

- turns parent orders into bar-by-bar execution episodes
- exposes a no-lookahead state schema for experimentation
- chooses among wait, rate-based marketable orders, passive limits, and aggressive limits
- provides random, heuristic, and tabular Q-learning policy utilities
- returns RL TCA rows with `strategy = RLAdaptiveEnsemble`

## Current Limitations

- Uses OHLCV bars, not full order book data.
- Synthetic bid/ask prices are deterministic and proxy-based.
- Impact parameters are not calibrated to real market impact data.
- Fill simulation is bar-based; queue and stochastic models are proxies, not true order-book queue position.
- Current CLI sample backtest runs a limited local SPY sample by default.
- Frontend currently targets saved processed CSVs; upload and long-running job management are future work.

## Roadmap

Planned next phases:

```text
Phase 9: Dashboard upload and async job management
Phase 10: Experiments and robustness tests
Phase 11: Final report workflow
```

Useful future extensions:

- multi-ticker batch backtests
- configurable impact parameters
- noisy spread robustness experiments
- multi-path Monte Carlo summaries for stochastic fills
- adaptive strategy ablations
- high-volatility and low-liquidity regime analysis
- richer web dashboard workflows for strategy comparison
- true limit order book data integration

## Resume Summary

Built a Python smart execution and transaction cost analysis backtester using intraday Yahoo Finance data, comparing TWAP, VWAP, POV, and adaptive signal-aware execution strategies across simulated parent orders.

Engineered OHLCV-based market microstructure proxies including spread, signed volume, order flow imbalance, rolling volatility, liquidity score, volume curve, momentum, and reversal features.

Decomposed implementation shortfall into spread cost, market impact, timing cost, and opportunity cost to evaluate whether adaptive execution reduced transaction costs relative to baseline algorithms.

Tested short-horizon alpha signal decay across multiple prediction horizons using information coefficient, hit rate, and decile spread analysis.
