# Flow and Execution Models

## Purpose

This document defines the main flow and execution-model concepts referenced by the master plan:

- VPIN
- Kyle's lambda
- Almgren-Chriss execution
- temporary vs permanent impact
- optimal execution tradeoffs

The document also distinguishes what can be measured directly only with richer data from what this repository can approximate with bar-level proxies.

## Kyle's Lambda

### Concept

Kyle's lambda is an impact coefficient linking signed order flow to price change.

Stylized form:

```text
r_t = lambda * q_t + epsilon_t
```

Where:

- `r_t` is price return or signed price change
- `q_t` is signed order flow
- `lambda` is impact sensitivity

Interpretation:

- larger lambda means the market moves more per unit of signed flow
- smaller lambda suggests deeper or more resilient liquidity

### What would be needed for a stronger estimate

- trade-signed order flow
- possibly dollar-normalized or volatility-normalized flow
- finer time resolution than basic OHLCV bars

### What this repo can do now

On bar data, the repo can only estimate a proxy:

- sign volume by bar direction or return sign
- regress signed returns on signed volume proxy

This is useful as a regime descriptor, not as a true structural estimate.

## VPIN

### Concept

VPIN, or volume-synchronized probability of informed trading, is intended to measure order-flow toxicity by comparing buy and sell volume imbalance across volume buckets.

Stylized intuition:

- bucket volume into equal-sized chunks
- estimate buy and sell volume imbalance inside each bucket
- large persistent imbalance suggests toxic flow conditions

### What a stronger implementation needs

- trade-by-trade or event-level volume
- buy/sell classification at trade level
- volume bucket construction not tied to clock-time bars

### What this repo can do now

The repo can build a VPIN-style proxy from bar data:

- classify bar volume by bar sign
- compute rolling imbalance over a small bucket window
- normalize by rolling total volume

This is a bar proxy, not canonical VPIN.

## Temporary and Permanent Impact

### Temporary impact

Temporary impact is the immediate execution-cost component that tends to decay after trading pressure subsides.

Intuition:

- crossing the spread
- sweeping depth
- short-lived execution pressure

### Permanent impact

Permanent impact is the part of price change that persists after execution, often interpreted as information or lasting supply-demand imbalance.

Intuition:

- market updates its valuation because of the trade
- other participants infer information from the order

### Current repo mapping

`src/tca.py` already uses:

- a temporary impact proxy
- a permanent impact proxy

These are synthetic modeling choices, not empirically calibrated venue models.

## Almgren-Chriss

### Concept

Almgren-Chriss is a classical optimal execution framework that trades off:

- expected execution cost
- execution-risk variance

Core intuition:

- trade faster to reduce timing risk
- trade slower to reduce market impact
- choose a path based on risk aversion

### Why it matters here

The repository already studies implementation shortfall and adaptive execution, so Almgren-Chriss is a natural conceptual bridge to:

- implementation shortfall schedules
- risk-aversion-aware front-loading
- formalized execution tradeoff policies

### What the repo should implement later

At minimum:

- a schedule generator influenced by risk aversion
- a clean separation between benchmark, impact model, and urgency

The first implementation does not need a full matrix-analytic treatment if the interfaces are clean and the behavior is explicit.

## Optimal Execution Theory

### General objective

Optimal execution theory asks how to trade a large parent order while balancing:

- spread cost
- market impact
- adverse selection
- timing risk
- completion risk

### Why the current repo is relevant

The current bar path already contains:

- participation caps
- adaptive urgency
- TCA decomposition
- fill-rate and opportunity-cost logic

What is missing is a more explicit mapping from theory to strategy classes and simulator assumptions.

## Implementation Shortfall as a Strategy Objective

Implementation shortfall measures performance relative to arrival price.

As a strategy objective, it encourages:

- faster trading when delay risk is high
- slower trading when impact dominates and alpha is favorable

That is why the master plan includes:

- explicit implementation-shortfall strategy modules
- model-driven adaptive execution
- RL comparison against classical policies

## Mapping To Planned Repo Modules

### Proxy metrics

Planned modules:

- `src/microstructure_metrics.py`
- `src/microstructure_proxies.py`

Use:

- regime description on bar data
- candidate alpha features
- execution-condition diagnostics

### Strategy modules

Planned modules:

- `src/strategies_is.py`
- `src/strategies_adaptive_participation.py`
- `src/strategies_model_adaptive.py`

Use:

- execution policies tied more directly to theory

### LOB modules

Planned modules:

- `src/matching_engine.py`
- `src/lob_simulator.py`
- `src/lob_tca.py`

Use:

- richer measurement of realized spread, queue delay, and fill uncertainty

## Honest Measurement Policy

This repository should follow a simple rule:

- if a concept is implemented from bar-level approximations, name it as a proxy
- if a concept is implemented inside a synthetic simulator, name it as synthetic
- if future work adds direct event-level measurements from real data, only then call it real

This prevents theory language from outrunning the evidence in code.
