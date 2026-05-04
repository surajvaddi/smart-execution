# Smart Execution Backtester Assignment

## Project Title

**Smart Execution Backtester: Transaction Cost Analysis, Microstructure Proxies, and Adaptive Execution Using Yahoo Finance Data**

## Purpose

This assignment is designed to build practical skills in the three areas identified as gaps for smart execution roles:

1. Transaction cost analysis, or TCA
2. Market microstructure research
3. Alpha signal research

The final project should show that you can take intraday market data, create microstructure-inspired features, test short-horizon signals, simulate execution algorithms, and evaluate performance after transaction costs.

## Core Research Question

Can an adaptive execution strategy reduce implementation shortfall by using OHLCV-based microstructure proxies such as volume imbalance, volatility, spread proxy, liquidity score, and short-horizon alpha signals?

## Important Data Limitation

Yahoo Finance does not provide full limit order book data. It does not include bid, ask, depth, queue position, cancellations, or true order flow. This project therefore uses OHLCV-based proxies for spread, liquidity, volatility, order flow, and imbalance.

This limitation should be stated clearly in the README and final report.

---

# Phase 0: Repository Setup

## Goal

Create a clean project structure that looks like a real research engineering project.

## Suggested Repository Structure

```text
smart-execution-backtester/
  README.md
  requirements.txt
  main.py

  data/
    raw/
    processed/

  src/
    __init__.py
    data_loader.py
    features.py
    signals.py
    execution.py
    strategies.py
    tca.py
    backtester.py
    plots.py

  notebooks/
    01_data_exploration.ipynb
    02_signal_research.ipynb
    03_execution_backtest.ipynb

  reports/
    smart_execution_report.md
```

## Required Packages

```text
yfinance
pandas
numpy
matplotlib
scikit-learn
statsmodels
```

Optional:

```text
plotly
jupyter
```

## Deliverables

* [ ] Create repository
* [ ] Create directory structure
* [ ] Create `requirements.txt`
* [ ] Create starter `README.md`
* [ ] Confirm the project runs from `main.py`

---

# Phase 1: Load Intraday Yahoo Finance Data

## Goal

Download and clean intraday OHLCV data.

## Suggested Tickers

```python
tickers = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA"]
```

## Suggested Data Settings

Use 5-minute bars for the main project:

```python
interval = "5m"
period = "60d"
```

Optional short-window high-frequency experiment:

```python
interval = "1m"
period = "7d"
```

## Function to Implement

```python
def load_intraday_data(ticker: str, period: str, interval: str) -> pd.DataFrame:
    """
    Download intraday OHLCV data from Yahoo Finance.
    Return a cleaned DataFrame indexed by timestamp.
    """
```

## Required Columns After Cleaning

```text
open
high
low
close
volume
returns
dollar_volume
date
time
bar_index
ticker
```

## Example Feature Construction

```python
df["returns"] = df["close"].pct_change()
df["dollar_volume"] = df["close"] * df["volume"]
df["date"] = df.index.date
df["time"] = df.index.time
df["bar_index"] = df.groupby("date").cumcount()
```

## Deliverables

* [ ] Download data for at least 5 tickers
* [ ] Clean column names
* [ ] Add returns, dollar volume, date, time, and bar index
* [ ] Save raw and processed data locally
* [ ] Validate that each ticker has usable intraday data

---

# Phase 2: Build Market Microstructure Proxy Features

## Goal

Engineer OHLCV-based proxies for market microstructure variables.

Because Yahoo Finance does not provide order book data, these features are approximations. The point is to learn the research workflow.

---

## Feature 1: Spread Proxy

Use high-low range as a proxy for intrabar spread and volatility.

```python
df["spread_proxy"] = (df["high"] - df["low"]) / df["close"]
```

Interpretation:

* Higher spread proxy means trading may be more expensive.
* It can represent weaker liquidity or higher volatility.
* It is not true bid-ask spread.

---

## Feature 2: Signed Volume

Infer buyer or seller pressure from bar direction.

```python
df["signed_volume"] = np.sign(df["close"] - df["open"]) * df["volume"]
```

Alternative:

```python
df["signed_volume"] = np.sign(df["close"].diff()) * df["volume"]
```

Interpretation:

* Positive signed volume means buyer pressure proxy.
* Negative signed volume means seller pressure proxy.

---

## Feature 3: Order Flow Imbalance Proxy

```python
df["ofi_proxy"] = (
    df["signed_volume"].rolling(5).sum()
    / df["volume"].rolling(5).sum()
)
```

Interpretation:

For a buy order:

* Positive OFI suggests price may move up, so executing faster may help.
* Negative OFI suggests price may soften, so executing slower may help.

---

## Feature 4: Rolling Volatility

```python
df["rolling_vol"] = df["returns"].rolling(12).std()
```

Interpretation:

* High volatility increases timing risk.
* High volatility may also imply higher execution uncertainty.

---

## Feature 5: Volume Curve

Estimate average intraday volume share by bar index.

```python
volume_by_bar = df.groupby("bar_index")["volume"].mean()
volume_curve = volume_by_bar / volume_by_bar.sum()
```

Interpretation:

* This is the historical VWAP schedule.
* High-volume bars are generally easier to trade in.

---

## Feature 6: Volume Z-Score

```python
df["volume_zscore"] = (
    df["volume"] - df["volume"].rolling(20).mean()
) / df["volume"].rolling(20).std()
```

Interpretation:

* Positive volume shock may indicate liquidity or informed activity.
* It can be used as either a liquidity signal or an alpha signal.

---

## Feature 7: Momentum and Reversal

```python
df["momentum_3"] = df["close"].pct_change(3)
df["reversal_3"] = -df["momentum_3"]
```

Interpretation:

* Momentum assumes short-term continuation.
* Reversal assumes short-term mean reversion.

---

## Feature 8: Liquidity Score

```python
df["liquidity_score"] = (
    df["volume"].rank(pct=True)
    - df["spread_proxy"].rank(pct=True)
    - df["rolling_vol"].rank(pct=True)
)
```

Interpretation:

* High liquidity score means better conditions for trading.
* Low liquidity score means more expensive or risky execution conditions.

## Deliverables

* [ ] Implement all feature functions in `features.py`
* [ ] Add feature validation checks
* [ ] Create plots of spread proxy, volume, OFI proxy, and volatility
* [ ] Explain the limitation of each proxy in the README

---

# Phase 3: Alpha Signal Research

## Goal

Test whether your microstructure proxy features predict short-horizon future returns.

This phase directly addresses alpha signal research.

---

## Forward Return Targets

Implement forward returns for multiple horizons.

```python
def add_forward_returns(df: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    for h in horizons:
        df[f"fwd_return_{h}"] = df["close"].shift(-h) / df["close"] - 1
    return df
```

## Suggested Horizons

```python
horizons = [1, 3, 6, 12]
```

For 5-minute bars:

```text
1 bar  = 5 minutes
3 bars = 15 minutes
6 bars = 30 minutes
12 bars = 60 minutes
```

---

## Signals to Test

```text
ofi_proxy
momentum_3
reversal_3
volume_zscore
rolling_vol
spread_proxy
liquidity_score
```

You may also create a combined alpha signal:

```python
df["alpha_signal"] = (
    0.40 * df["ofi_proxy"].rank(pct=True)
    + 0.25 * df["momentum_3"].rank(pct=True)
    + 0.20 * df["volume_zscore"].rank(pct=True)
    + 0.15 * df["liquidity_score"].rank(pct=True)
)
```

Normalize if needed:

```python
df["alpha_signal"] = df["alpha_signal"] - df["alpha_signal"].mean()
```

---

## Signal Evaluation Metrics

### Information Coefficient

```python
def information_coefficient(df, signal_col, target_col):
    return df[[signal_col, target_col]].corr().iloc[0, 1]
```

### Hit Rate

```python
def hit_rate(df, signal_col, target_col):
    valid = df[[signal_col, target_col]].dropna()
    return (np.sign(valid[signal_col]) == np.sign(valid[target_col])).mean()
```

### Decile Spread

```python
def decile_spread(df, signal_col, target_col):
    temp = df[[signal_col, target_col]].dropna().copy()
    temp["decile"] = pd.qcut(temp[signal_col], 10, labels=False, duplicates="drop")
    by_decile = temp.groupby("decile")[target_col].mean()
    return by_decile.iloc[-1] - by_decile.iloc[0]
```

---

## Required Analysis

For each signal and horizon, compute:

* Information coefficient
* Hit rate
* Decile spread
* Signal decay by horizon

## Deliverables

* [ ] Create `signals.py`
* [ ] Implement forward return generation
* [ ] Implement IC, hit rate, and decile spread
* [ ] Build a signal evaluation table
* [ ] Plot signal decay by horizon
* [ ] Write a short interpretation of which signals are useful and which are noisy

---

# Phase 4: Parent Order Simulation

## Goal

Simulate large parent orders that must be executed over a fixed window.

A parent order is split into child orders by different execution strategies.

## Parent Order Example

```python
parent_order = {
    "ticker": "SPY",
    "side": "buy",
    "quantity": 100_000,
    "start_time": "10:00",
    "end_time": "15:30",
    "participation_cap": 0.10
}
```

## Required Parent Order Fields

```text
ticker
side
quantity
start_time
end_time
participation_cap
```

## Order Sizes to Test

Use order size as a fraction of average daily volume.

```text
1% of daily volume
5% of daily volume
10% of daily volume
```

## Execution Windows to Test

```text
10:00 to 15:30
10:00 to 12:00
13:00 to 15:30
```

## Deliverables

* [ ] Create parent order object or class
* [ ] Generate multiple parent orders per ticker
* [ ] Support buy and sell orders
* [ ] Support different time windows
* [ ] Support participation caps

---

# Phase 5: Execution Strategies

## Goal

Implement four execution strategies:

1. TWAP
2. VWAP
3. POV
4. Adaptive smart execution

Each strategy should output child orders.

Each child order should contain:

```text
timestamp
ticker
side
strategy
quantity
reference_price
```

---

## Strategy 1: TWAP

TWAP trades evenly across time.

```python
child_qty = remaining_qty / remaining_bars
```

Strengths:

* Simple
* Reliable completion
* Easy benchmark

Weaknesses:

* Ignores volume
* Ignores volatility
* Ignores liquidity
* Ignores alpha signals

---

## Strategy 2: VWAP

VWAP trades according to the historical volume curve.

```python
child_qty = parent_qty * expected_volume_share[t]
```

Strengths:

* Trades more when liquidity is historically higher
* Common benchmark

Weaknesses:

* Uses expected volume, not actual conditions
* Can be predictable
* Does not react to alpha signals

---

## Strategy 3: POV

POV trades as a fixed percentage of actual market volume.

```python
child_qty = participation_rate * market_volume[t]
```

Strengths:

* Adapts to actual volume
* Controls market footprint

Weaknesses:

* May fail to complete
* May chase volume spikes
* Does not use signal direction

---

## Strategy 4: Adaptive Smart Execution

The adaptive strategy uses signal, liquidity, spread, volatility, and urgency.

For a buy order:

```text
If signal predicts price up, trade faster.
If signal predicts price down, trade slower.
If spread proxy is high, trade slower.
If volatility is high, trade slower unless urgency is high.
If volume is high, trade more.
If behind schedule, increase urgency.
```

For a sell order:

```text
If signal predicts price down, sell faster.
If signal predicts price up, sell slower.
```

## Adaptive Multiplier Example

```python
def adaptive_multiplier(row, side, urgency):
    signal = row["alpha_signal"]
    spread = row["spread_proxy"]
    vol = row["rolling_vol"]
    liquidity = row["liquidity_score"]

    multiplier = 1.0

    if side == "buy":
        if signal > 0:
            multiplier *= 1.4
        elif signal < 0:
            multiplier *= 0.7

    elif side == "sell":
        if signal < 0:
            multiplier *= 1.4
        elif signal > 0:
            multiplier *= 0.7

    if spread > row["spread_proxy_75pct"]:
        multiplier *= 0.75

    if vol > row["rolling_vol_75pct"]:
        multiplier *= 0.85

    if liquidity > row["liquidity_score_75pct"]:
        multiplier *= 1.2

    multiplier *= urgency

    return np.clip(multiplier, 0.25, 2.5)
```

## Child Quantity Rule

```python
child_qty = base_qty * multiplier
child_qty = min(child_qty, remaining_qty)
child_qty = min(child_qty, participation_cap * row["volume"])
```

## Deliverables

* [ ] Implement `TWAPStrategy`
* [ ] Implement `VWAPStrategy`
* [ ] Implement `POVStrategy`
* [ ] Implement `AdaptiveStrategy`
* [ ] Ensure each strategy respects remaining quantity
* [ ] Ensure each strategy respects participation cap
* [ ] Compare child order schedules across strategies

---

# Phase 6: Transaction Cost Model

## Goal

Estimate execution prices and decompose transaction costs.

This phase directly addresses TCA.

Because Yahoo Finance does not provide bid and ask, create synthetic bid and ask prices using close price and spread proxy.

---

## Synthetic Bid and Ask

```python
mid = row["close"]
half_spread = 0.5 * row["spread_proxy"] * mid

synthetic_bid = mid - half_spread
synthetic_ask = mid + half_spread
```

---

## Fill Price for Buy Orders

```python
fill_price = synthetic_ask + temporary_impact
```

## Fill Price for Sell Orders

```python
fill_price = synthetic_bid - temporary_impact
```

---

## Temporary Market Impact

```python
temporary_impact = eta * mid * (child_qty / row["volume"]) ** beta
```

Suggested parameters:

```python
eta = 0.10
beta = 0.5
```

Interpretation:

* Larger child orders create larger impact.
* Impact grows sublinearly when `beta = 0.5`.

---

## Permanent Market Impact Proxy

```python
permanent_impact = gamma * mid * (child_qty / row["volume"])
```

Suggested parameter:

```python
gamma = 0.02
```

You do not need to mutate the historical price path. Track permanent impact as a cost component.

## Deliverables

* [ ] Implement synthetic bid and ask
* [ ] Implement temporary impact
* [ ] Implement permanent impact proxy
* [ ] Compute fill prices for buy and sell child orders
* [ ] Store spread cost, impact cost, and timing cost for every fill

---

# Phase 7: TCA Metrics

## Goal

Evaluate execution quality for each strategy.

---

## Average Fill Price

```python
avg_fill = sum(fill_price * quantity) / sum(quantity)
```

---

## Arrival Price

```python
arrival_price = close price at order start
```

---

## Implementation Shortfall

For a buy:

```python
implementation_shortfall = avg_fill - arrival_price
```

For a sell:

```python
implementation_shortfall = arrival_price - avg_fill
```

In basis points:

```python
shortfall_bps = 10_000 * implementation_shortfall / arrival_price
```

---

## Market VWAP

```python
market_vwap = sum(close * volume) / sum(volume)
```

---

## VWAP Slippage

For a buy:

```python
vwap_slippage = avg_fill - market_vwap
```

For a sell:

```python
vwap_slippage = market_vwap - avg_fill
```

In basis points:

```python
vwap_slippage_bps = 10_000 * vwap_slippage / market_vwap
```

---

## Spread Cost

For a buy:

```python
spread_cost = synthetic_ask - mid
```

For a sell:

```python
spread_cost = mid - synthetic_bid
```

---

## Impact Cost

```python
impact_cost = temporary_impact + permanent_impact
```

---

## Timing Cost

For a buy:

```python
timing_cost = mid_at_execution - arrival_price
```

For a sell:

```python
timing_cost = arrival_price - mid_at_execution
```

---

## Opportunity Cost

If the strategy does not fully complete:

```python
unfilled_qty = parent_qty - filled_qty
opportunity_cost = unfilled_qty * abs(close_at_end - arrival_price)
```

---

## Fill Rate

```python
fill_rate = filled_qty / parent_qty
```

## Required Result Columns

```text
ticker
date
side
quantity
strategy
avg_fill_price
arrival_price
market_vwap
implementation_shortfall_bps
vwap_slippage_bps
spread_cost_bps
impact_cost_bps
timing_cost_bps
opportunity_cost_bps
fill_rate
execution_duration
```

## Deliverables

* [ ] Implement all TCA metrics in `tca.py`
* [ ] Return one result row per parent order per strategy
* [ ] Validate buy and sell calculations separately
* [ ] Create summary table by strategy

---

# Phase 8: Backtest Design

## Goal

Run a multi-ticker, multi-strategy backtest.

## Backtest Grid

Run:

```text
5 tickers
20 parent orders per ticker
Buy and sell orders
3 order sizes
3 execution windows
4 strategies
```

At minimum, produce 100+ parent order simulations.

## Main Backtest Loop

```python
for ticker in tickers:
    data = load_intraday_data(ticker, period, interval)
    data = add_features(data)
    data = add_signals(data)

    parent_orders = generate_parent_orders(data)

    for order in parent_orders:
        for strategy in strategies:
            fills = strategy.generate_child_orders(order, data)
            fills = apply_transaction_cost_model(fills, data)
            result = compute_tca_metrics(order, fills, data)
            results.append(result)
```

## Deliverables

* [ ] Implement `Backtester`
* [ ] Run all strategies on identical market windows
* [ ] Save results as CSV
* [ ] Create aggregate results by strategy
* [ ] Identify which strategy performs best under which market conditions

---

# Phase 9: Required Plots

## Plot 1: Price Path With Fills

Show:

* Close price or synthetic mid price
* Execution points for each strategy
* Buy or sell markers

Purpose:

* See whether the strategy trades before or after price movement.

---

## Plot 2: Cumulative Fill Curve

Show cumulative executed quantity over time for each strategy.

Purpose:

* Compare execution speed.
* Show urgency and completion behavior.

---

## Plot 3: Implementation Shortfall by Strategy

Bar chart of average implementation shortfall in basis points.

Purpose:

* Compare execution quality.

---

## Plot 4: Cost Decomposition

Stacked bar chart with:

```text
Spread cost
Impact cost
Timing cost
Opportunity cost
```

Purpose:

* Show why one strategy wins or loses.

---

## Plot 5: Signal Decay

X-axis:

```text
Prediction horizon
```

Y-axis:

```text
Information coefficient
```

Purpose:

* Show whether alpha signals decay over time.

## Deliverables

* [ ] Implement plotting functions in `plots.py`
* [ ] Save all plots to `reports/figures/`
* [ ] Include plots in final report

---

# Phase 10: Experiments

## Experiment 1: Baseline Execution Comparison

Question:

Does adaptive execution beat TWAP, VWAP, and POV on average?

Required output:

* Summary table by strategy
* Implementation shortfall plot
* Cost decomposition plot

---

## Experiment 2: Signal Value After Costs

Question:

Do alpha signals improve execution quality after spread, impact, and timing costs?

Required output:

* Signal IC table
* Signal decay plot
* Adaptive strategy performance versus baselines

---

## Experiment 3: High Volatility Regime

Question:

How do strategies behave when rolling volatility is high?

Method:

Filter parent orders into high-volatility windows.

Required output:

* TCA table for high-volatility subset
* Cost decomposition by strategy

---

## Experiment 4: Low Liquidity Regime

Question:

How do strategies behave when volume is low and spread proxy is high?

Method:

Filter parent orders into low-liquidity windows.

Required output:

* Fill rate comparison
* Impact cost comparison
* Opportunity cost comparison

---

## Experiment 5: Adaptive Strategy Ablation

Question:

Which adaptive feature matters most?

Run versions of adaptive execution:

```text
Adaptive full
Adaptive without alpha signal
Adaptive without liquidity score
Adaptive without spread control
Adaptive without urgency control
```

Required output:

* TCA comparison across ablations
* Interpretation of what helped or hurt

---

# Phase 11: Final Report

## Goal

Write a clear 4 to 6 page markdown report that explains your methodology, results, and lessons learned.

## Report Structure

```text
reports/smart_execution_report.md
```

## Section 1: Motivation

Explain that the project was motivated by the need to understand:

* Transaction cost analysis
* Market microstructure research
* Alpha signal research
* Smart execution principles

## Section 2: Data and Limitations

Explain:

* Yahoo Finance provides OHLCV data
* It does not provide full limit order book data
* You use OHLCV-derived proxies
* Results should be interpreted as research simulation, not production execution modeling

## Section 3: Feature Engineering

Explain:

* Spread proxy
* Signed volume
* OFI proxy
* Rolling volatility
* Volume curve
* Liquidity score
* Momentum and reversal

## Section 4: Signal Research

Explain:

* Forward return prediction
* Information coefficient
* Hit rate
* Decile spread
* Signal decay

## Section 5: Execution Strategies

Explain:

* TWAP
* VWAP
* POV
* Adaptive smart execution

## Section 6: TCA Methodology

Explain:

* Synthetic bid and ask
* Temporary impact
* Permanent impact proxy
* Implementation shortfall
* VWAP slippage
* Spread, impact, timing, and opportunity cost

## Section 7: Results

Include:

* Strategy comparison table
* Cost decomposition
* Signal decay plot
* Regime analysis
* Ablation analysis

## Section 8: Lessons Learned

Answer:

* When does adaptive execution help?
* When does it overfit noisy signals?
* How do costs erase raw signal value?
* Why does execution research require both signal quality and cost modeling?
* What would improve the project with true limit order book data?

---

# Final Summary Table Template

Use this in the report.

| Strategy | Avg IS bps | VWAP Slippage bps | Spread Cost bps | Impact Cost bps | Timing Cost bps | Opportunity Cost bps | Fill Rate |
| -------- | ---------: | ----------------: | --------------: | --------------: | --------------: | -------------------: | --------: |
| TWAP     |            |                   |                 |                 |                 |                      |           |
| VWAP     |            |                   |                 |                 |                 |                      |           |
| POV      |            |                   |                 |                 |                 |                      |           |
| Adaptive |            |                   |                 |                 |                 |                      |           |

---

# README Framing

Use this language in the README.

```text
This project builds a smart execution and transaction cost analysis backtester using intraday Yahoo Finance OHLCV data. The system compares TWAP, VWAP, POV, and adaptive signal-aware execution strategies across simulated large parent orders. Because Yahoo Finance does not provide full limit order book data, the project uses OHLCV-derived proxies for spread, liquidity, order flow imbalance, volatility, and short-horizon alpha.

The objective is to evaluate whether adaptive execution can reduce implementation shortfall after estimated spread, market impact, timing, and opportunity costs.
```

---

# Resume Bullets After Completion

Use these after the project works.

* Built a Python smart execution and transaction cost analysis backtester using intraday Yahoo Finance data, comparing TWAP, VWAP, POV, and adaptive signal-aware execution strategies across simulated parent orders.

* Engineered OHLCV-based market microstructure proxies including spread, signed volume, order flow imbalance, rolling volatility, liquidity score, volume curve, momentum, and reversal features.

* Decomposed implementation shortfall into spread cost, market impact, timing cost, and opportunity cost to evaluate whether adaptive execution reduced transaction costs relative to baseline algorithms.

* Tested short-horizon alpha signal decay across multiple prediction horizons using information coefficient, hit rate, and decile spread analysis.

---

# Completion Checklist

## Data

* [ ] Download intraday Yahoo Finance data
* [ ] Clean and store OHLCV data
* [ ] Validate data coverage

## Features

* [ ] Spread proxy
* [ ] Signed volume
* [ ] OFI proxy
* [ ] Rolling volatility
* [ ] Volume curve
* [ ] Liquidity score
* [ ] Momentum
* [ ] Reversal

## Alpha Research

* [ ] Forward returns
* [ ] IC analysis
* [ ] Hit rate
* [ ] Decile spread
* [ ] Signal decay plot

## Execution Strategies

* [ ] TWAP
* [ ] VWAP
* [ ] POV
* [ ] Adaptive smart execution

## TCA

* [ ] Synthetic bid and ask
* [ ] Temporary impact
* [ ] Permanent impact proxy
* [ ] Implementation shortfall
* [ ] VWAP slippage
* [ ] Spread cost
* [ ] Impact cost
* [ ] Timing cost
* [ ] Opportunity cost
* [ ] Fill rate

## Backtesting

* [ ] Multi-ticker test
* [ ] Buy and sell orders
* [ ] Multiple order sizes
* [ ] Multiple execution windows
* [ ] Strategy comparison table

## Reporting

* [ ] Price path with fills
* [ ] Cumulative fill curve
* [ ] Implementation shortfall plot
* [ ] Cost decomposition plot
* [ ] Signal decay plot
* [ ] Final markdown report

---

# Stretch Goals

## Stretch Goal 1: Broker Simulation

Simulate multiple broker execution profiles:

```text
Broker A: low spread, higher impact
Broker B: higher spread, lower impact
Broker C: slower fills, lower impact
```

Then test broker routing decisions.

## Stretch Goal 2: Reinforcement Learning Policy

Train a basic policy that chooses whether to trade slowly, normally, or aggressively at each bar.

State variables:

```text
remaining quantity
remaining time
alpha signal
spread proxy
rolling volatility
liquidity score
current fill rate
```

Actions:

```text
slow
normal
aggressive
```

Reward:

```text
negative implementation shortfall
penalty for non-completion
```

## Stretch Goal 3: Real Limit Order Book Data

Replace Yahoo Finance proxies with true order book data from another source.

Potential data sources:

```text
LOBSTER academic data
NASDAQ ITCH samples
crypto exchange order book data
```

This would make the project much closer to real market microstructure research.

---

# Interview Story

After completing the project, describe it like this:

```text
After receiving feedback that I needed deeper exposure to transaction cost analysis, market microstructure research, and alpha signal research, I built a smart execution backtester around those exact areas. The project uses intraday Yahoo Finance data to simulate large parent order execution across TWAP, VWAP, POV, and adaptive signal-aware strategies. I engineered OHLCV-based microstructure proxies, tested short-horizon signal decay, and decomposed implementation shortfall into spread, impact, timing, and opportunity costs. The goal was to understand when adaptive execution improves realized execution quality after costs, not just when a signal predicts returns in isolation.
```

