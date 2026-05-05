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
