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
