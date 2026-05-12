# Codex Development Log

## 2026-05-04

### Scaffold

- Created the initial repository layout from the README:
  - `data/raw/`
  - `data/processed/`
  - `notebooks/`
  - `reports/figures/`
  - `src/`
- Added `requirements.txt` with the core project dependencies.
- Added starter Python modules under `src/`.
- Added `main.py` as a runnable scaffold smoke check.
- Verified `python3 main.py` imports the package and prints the scaffold status.

Comments:

- This phase intentionally created a thin but complete project shell before adding behavior.
- The modules mirror the README phases, which makes future development easier to follow and keeps each concept in a focused file.
- `main.py` was kept non-networked at first so the project could be smoke-tested before dependencies, data access, or Yahoo Finance behavior entered the loop.
- The scaffold is not a final architecture; it is a stable starting point that lets later phases replace placeholders with real functionality incrementally.

### Phase 1: Data Loading

- Started implementing intraday Yahoo Finance data loading and cleaning.
- Added `CODEX_LOG.md` to track incremental development updates.
- Implemented `src/data_loader.py` functions to download Yahoo Finance intraday data, clean OHLCV columns, add required fields, and save raw/processed CSV files.
- Updated `main.py` with a `--download-sample` option for manually exercising the loader.
- Made `yfinance` import lazily so default scaffold checks do not pay download-library import cost.
- Added `.gitignore` for Python caches, virtual environments, downloaded CSV data, and generated figures.
- Installed project dependencies to verify the loader.
- Found `multitasking 0.0.13` is incompatible with the current Python 3.8 runtime, so pinned `multitasking<0.0.12` in `requirements.txt`.
- Verified `python3 main.py --download-sample --ticker SPY --period 5d --interval 5m` with network access.
- Saved sample files to `data/raw/SPY_5d_5m.csv` and `data/processed/SPY_5d_5m.csv`.
- Added `numexpr>=2.7.3` to avoid pandas runtime warnings in this environment.

Comments:

- The loader establishes the canonical data contract for the rest of the project: lowercase OHLCV columns plus `returns`, `dollar_volume`, `date`, `time`, `bar_index`, and `ticker`.
- Raw and processed saves are separated so future debugging can distinguish Yahoo Finance output from project cleaning logic.
- `yfinance` is imported lazily because the default CLI path should stay fast and usable even before optional download dependencies are installed.
- The sample download proved the full path works only when network access is available; offline development can continue against the saved processed CSV.
- Yahoo Finance remains a limited OHLCV source, so later market microstructure features must be treated as proxies rather than true order book measurements.

### Phase 2: Microstructure Proxy Features

- Implemented `src/features.py` feature generation for:
  - `spread_proxy`
  - `signed_volume`
  - `ofi_proxy`
  - `rolling_vol`
  - `volume_zscore`
  - `momentum_3`
  - `reversal_3`
  - `liquidity_score`
  - `alpha_signal`
- Added base schema and feature output validation helpers.
- Added `estimate_volume_curve()` for VWAP schedule support.
- Added `main.py --feature-sample` to compute features from a processed CSV and print a validation summary.

Comments:

- Feature engineering is grouped by ticker to prevent rolling windows, ranks, and percent changes from leaking across symbols once multi-ticker data is used.
- Rolling features intentionally produce leading `NaN` values until enough bars are available; this is expected and avoids manufacturing early-window data.
- `spread_proxy`, `ofi_proxy`, `liquidity_score`, and `alpha_signal` are research approximations based on OHLCV bars, not true bid-ask spread, order flow, or depth.
- `alpha_signal` is a simple weighted composite so Phase 3 has a first combined signal to evaluate before using it in adaptive execution.
- `estimate_volume_curve()` was added early because VWAP execution will need a historical intraday volume schedule in a later phase.

### Code Comment Pass

- Added code comments and expanded module docstrings across the Phase 0-2 implementation.
- Clarified the Yahoo Finance OHLCV limitation directly in `src/data_loader.py` and `src/features.py`.
- Documented the cleaned data schema contract, raw versus processed saves, per-ticker feature grouping, rolling-window `NaN` behavior, proxy feature interpretation, and CLI smoke-check purpose.
- Added phase-boundary comments to placeholder modules so future implementation work has clear contracts.

### Phase 3: Alpha Signal Research

- Added safer signal metric utilities in `src/signals.py`:
  - finite signal/target filtering
  - `information_coefficient()`
  - `hit_rate()`
  - `decile_spread()`
- Added default signal columns and forward-return horizons for the README's signal research plan.
- Added `evaluate_signals()` to produce one result row per signal and prediction horizon.
- Added `main.py --signal-sample` to run the offline signal research path from a processed CSV.
- Added CSV output for signal evaluation results under `reports/`.
- Added `signal_decay_table()` to pivot information coefficient by signal and horizon.
- Added signal decay CSV output under `reports/` for future plotting/reporting.
- Added `signal_quality_summary()` to rank signals across horizons by mean absolute IC.
- Added signal summary CSV output and markdown interpretation notes under `reports/`.

### Phase 4: Parent Order Simulation

- Expanded `src/execution.py` with parent order validation, default ADV fractions, default execution windows, and participation cap defaults.
- Added helpers for parsing execution window times, computing average daily volume, converting ADV fractions into order quantities, and filtering market data by execution window.
- Implemented deterministic parent order generation across ticker, date, side, order size, and execution window.
- Added `parent_orders_to_frame()` to save generated parent orders as tabular research inputs.
- Added `main.py --orders-sample` to generate parent orders from a processed CSV and save them under `reports/`.
- Corrected intraday timestamp handling so Yahoo Finance UTC bars are converted to New York market time before deriving `date`, `time`, and `bar_index`.

### Phase 5: Execution Strategies

- Added shared child-order schema and validation in `src/strategies.py`.
- Added common strategy helpers for selecting a parent order's market window and building child-order DataFrames.
- Implemented TWAP child-order generation with equal quantity per bar and exact final quantity adjustment.
- Added `main.py --twap-sample` and saved TWAP sample child orders under `reports/`.
- Implemented VWAP child-order generation using the historical volume curve from Phase 2.
- Added `main.py --vwap-sample` and saved VWAP sample child orders under `reports/`.
- Implemented POV child-order generation using realized market volume and the parent order participation cap.
- Added `main.py --pov-sample` and saved POV sample child orders under `reports/`.
- Implemented Adaptive child-order generation using `alpha_signal`, `spread_proxy`, `rolling_vol`, `liquidity_score`, urgency, and the participation cap.
- Added `main.py --adaptive-sample` and saved Adaptive sample child orders under `reports/`.
- Added `main.py --strategy-compare-sample` to compare TWAP, VWAP, POV, and Adaptive schedules on the same parent order.
- Found and fixed a VWAP participation-cap issue during schedule comparison.

### Phase 6: Transaction Cost Model

- Added deterministic synthetic quote helpers in `src/tca.py`:
  - `synthetic_bid_ask_from_row()`
  - `add_synthetic_bid_ask()`
- Synthetic quotes use `close` as mid price and center an OHLCV `spread_proxy` range around it.
- Added temporary and permanent market impact helper functions using the README parameters:
  - `eta = 0.10`
  - `beta = 0.5`
  - `gamma = 0.02`
- Added buy/sell fill price logic:
  - buys fill at synthetic ask plus temporary impact
  - sells fill at synthetic bid minus temporary impact
- Implemented `apply_transaction_cost_model()` to enrich child orders with synthetic quotes, impact costs, spread cost, and fill price.
- Added `main.py --tca-sample` to run one TWAP schedule through the Phase 6 cost model and save enriched fills under `reports/`.
- Validated quote ordering, buy/sell fill direction, nonnegative spread costs, and nonnegative impact costs on the saved SPY sample.
- Noted that the README default impact parameters produce large estimated impact costs on the current sample; calibration remains a later modeling decision.

### Phase 7: TCA Metrics

- Added parent-order-level TCA helper functions in `src/tca.py`:
  - `average_fill_price()`
  - `arrival_price()`
  - `market_vwap()`
  - `implementation_shortfall_bps()`
  - `vwap_slippage_bps()`
  - `weighted_cost_bps()`
  - `timing_cost_bps()`
  - `fill_rate()`
  - `opportunity_cost_bps()`
- Implemented `compute_tca_metrics()` to return one result row per parent order and strategy.
- Added `main.py --tca-metrics-sample` to compute a TWAP parent-order TCA row from the saved SPY sample.
- Saved sample TCA metrics under `reports/tca_metrics_SPY_5d_5m.csv`.
- Validated required output columns, positive price fields, fill-rate bounds, nonnegative spread/impact/opportunity costs, and execution duration.

### Phase 8: Backtest Design

- Expanded `src/backtester.py` with default strategy registration for TWAP, VWAP, POV, and Adaptive.
- Added backtester configuration fields for strategies and `max_orders_per_ticker`.
- Added `prepare_data_from_csv()` to load local processed data and apply Phase 2 features.
- Added `run_order_strategy()` to run one parent order through one strategy, apply transaction costs, and compute TCA metrics.
- Added `run_single_ticker_csv()` to generate parent orders and run all configured strategies on one processed CSV.
- Added `summarize_by_strategy()` and `save_results()` for detailed result and aggregate summary CSV output.
- Added `main.py --backtest-sample` to run a deterministic one-ticker sample backtest across all strategies.
- Saved sample outputs under `reports/backtest_results_SPY_5d_5m.csv` and `reports/backtest_summary_SPY_5d_5m.csv`.
- Validated result columns, strategy coverage, summary row count, fill-rate bounds, positive price fields, numeric cost fields, and per-strategy simulation counts.
- Added optional inclusive date/time filters for processed CSV commands:
  - `--start-date` and `--end-date`
  - `--start-time` and `--end-time`
- Enforced paired filter bounds so start date/time cannot be provided without matching end date/time.
- Updated the sample backtest path to use filtered in-memory data instead of reloading the full CSV.

### Multi-Ticker Extension

- Added `prepare_data_from_csvs()` to load, feature-enrich, and concatenate multiple processed CSVs.
- Added `alignment_report()` to summarize timestamp coverage and missing bars by ticker.
- Added `run_multiple_csvs()` to run independent per-CSV backtests and concatenate TCA result rows.
- Added summary helpers by ticker and by ticker-strategy.
- Added CLI support for:
  - `--download-tickers`
  - `--alignment-report --input-csvs ...`
  - `--backtest-multi --input-csvs ...`
- Added multi-ticker output files under `reports/` for alignment, detailed results, and strategy/ticker summaries.
- Documented that this is independent multi-ticker backtesting, not yet shared-clock portfolio execution.
- Added execution tape generation for multiple CSVs, saving all child orders with parent-order metadata and notional.
- Added timestamp-level execution summary grouped by timestamp and strategy, including active tickers, child-order count, total quantity, and total notional.
- Added `main.py --execution-tape --input-csvs ...` to write `reports/execution_tape_multi.csv` and `reports/execution_summary_by_timestamp_multi.csv`.

### Limit Placement Grid and Fill Simulator

- Added `docs/limit_order_fill_simulator_plan.md` to capture the placement-grid and fill-simulation design.
- Added `src/fill_simulator.py` for separating child-order scheduling from order placement and fill simulation.
- Implemented placement styles for market, marketable limit, aggressive limit, midpoint limit, passive limit, primary peg, midpoint peg, and adaptive limit orders.
- Implemented a deterministic `volume_capped_touch` fill model using OHLCV high/low touches, synthetic bid/ask prices, and participation-based fill capacity.
- Preserved submitted quantity separately from filled quantity so passive misses and partial fills can be analyzed.
- Updated TCA metrics so partial-fill and zero-fill paths produce valid result rows with opportunity cost instead of failing.
- Added execution-grid orchestration in the backtester across strategy schedules and placement styles.
- Added CLI support for:
  - `--execution-grid-sample`
  - `--execution-grid-multi`
  - `--placement-styles`
  - `--fill-model`
- Added execution-grid report outputs for simulated fills, detailed TCA rows, strategy summary, placement summary, and strategy-placement summary.
- Updated the README with the new fill-simulator architecture, commands, outputs, and current limitations.

Comments:

- Schedule algorithms still answer when and how much to trade; placement styles now answer where the child order is posted.
- The first fill simulator is intentionally deterministic because the project still uses OHLCV data rather than real order book depth or queue position.
- `market` placement remains the backwards-compatible path, while passive and pegged styles can now miss or partially fill and create opportunity cost.

### Fill Simulator Tests

- Added standard-library `unittest` coverage under `tests/test_fill_simulator.py`.
- Covered side-aware placement prices for passive, aggressive, midpoint, and market orders.
- Covered passive buy and sell touch rules using OHLCV high/low bars.
- Covered passive partial fills and missed fills.
- Added a regression check that `market` placement matches the legacy transaction cost model.
- Added a zero-fill TCA check so fully missed limit orders still produce a valid metrics row with opportunity cost.

### Artifact Cleanup

- Removed tracked Python bytecode files from `src/__pycache__/`.
- Confirmed `.gitignore` already ignores `__pycache__/` and `*.py[cod]` so new Python cache files should stay out of future commits.
- Confirmed the execution-grid plan document, CSV reports, and fill-simulator tests are tracked project artifacts rather than ignored local cache files.
