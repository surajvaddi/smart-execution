# Target Research Stack

## Purpose

This document defines the intended long-term architecture for `smart-execution`.

It exists to remove ambiguity between:

- what the repository already supports today
- what is planned but not yet implemented
- which modules belong to which research path
- how future subsystems should connect without drifting into incompatible prototypes

This is an architecture target, not a claim that every component already exists.

## Current State

Today the repository is primarily a bar-based smart execution backtester built on Yahoo Finance intraday OHLCV data.

Current strengths:

- deterministic data-cleaning pipeline
- proxy microstructure feature generation
- descriptive short-horizon signal research
- parent-order simulation
- schedule generation for TWAP, VWAP, POV, and adaptive execution
- synthetic bid/ask and bar-based fill simulation
- parent-order TCA metrics
- execution grid and Monte Carlo comparisons
- a lightweight RL execution layer
- API and frontend inspection tools

Current limitations:

- no true order-book state
- no explicit price-time priority engine
- no event-level order arrivals or cancellations
- no queue-position state
- no futures-specific instrument layer
- no out-of-sample predictive alpha lab

## Two Research Paths

The repository should evolve into two connected but clearly separated paths.

### Path A: Bar-Based Execution Research

Purpose:

- perform execution research on widely available intraday OHLCV data
- estimate execution quality using microstructure-inspired proxies
- compare scheduling and placement decisions under a synthetic cost model

Core truth:

- this path is proxy-based, not exchange-state-based

Primary modules:

- `src/data_loader.py`
- `src/features.py`
- `src/signals.py`
- `src/execution.py`
- `src/strategies.py`
- `src/fill_simulator.py`
- `src/tca.py`
- `src/backtester.py`
- `src/monte_carlo.py`
- `src/rl_env.py`
- `src/rl_policy.py`
- `src/rl_train.py`
- `src/rl_backtester.py`

Expected claims:

- smart scheduling research on bar data
- proxy liquidity and order-flow features
- synthetic fill modeling
- execution benchmarking and TCA

Claims this path must not make:

- true queue modeling
- real exchange matching behavior
- real maker/taker fill economics

### Path B: Event-Level Synthetic Microstructure Research

Purpose:

- simulate an exchange-like market with explicit order-book state
- study queue-aware execution decisions
- compare strategies under a matching engine with latency, cancellations, and partial fills

Core truth:

- this path is synthetic but structurally closer to real market microstructure than the bar path

Target modules:

- `src/lob_types.py`
- `src/lob_events.py`
- `src/lob_replay.py`
- `src/matching_engine.py`
- `src/lob_simulator_config.py`
- `src/lob_generators.py`
- `src/lob_latency.py`
- `src/lob_simulator.py`
- `src/lob_execution.py`
- `src/lob_execution_runner.py`
- `src/lob_tca.py`

Expected claims:

- price-time priority simulation
- queue-aware passive execution
- event-level trade and fill logs
- latency-sensitive synthetic market interaction

Claims this path must not make unless real data is added:

- historical exchange replay
- real venue microstructure reconstruction

## Cross-Cutting Research Layers

These layers should work across one or both paths.

### Instrument Layer

Purpose:

- standardize instrument metadata across equities, futures, and FX

Target modules:

- `src/instruments.py`
- `src/futures_math.py`
- `src/futures_roll.py`
- `src/calendar_spreads.py`
- `src/futures_tca.py`

### Predictive Alpha Layer

Purpose:

- move from descriptive signal research to out-of-sample predictive modeling

Target modules:

- `src/alpha_dataset.py`
- `src/alpha_split.py`
- `src/alpha_models_linear.py`
- `src/alpha_models_tree.py`
- `src/alpha_evaluation.py`
- `src/strategies_model_adaptive.py`

### Orchestration Layer

Purpose:

- expose consistent workflows to the CLI, API, and frontend without embedding research logic there

Primary modules:

- `src/services.py`
- `src/api.py`
- `main.py`

## Architecture Diagram

### Current bar-based stack

```text
processed OHLCV CSV
-> load/clean
-> proxy feature engineering
-> parent-order generation
-> schedule generation
-> synthetic placement/fill simulation
-> TCA summary
-> API / frontend / reports
```

### Target synthetic LOB stack

```text
instrument spec + simulator config
-> initial book state
-> exogenous event generation
-> latency application
-> matching engine state transitions
-> execution child order interaction
-> execution reports and trade prints
-> LOB-aware TCA
-> strategy comparison and reports
```

### Target predictive alpha stack

```text
prepared market data
-> leakage-safe feature matrix
-> train/validation/test split
-> predictive model training
-> score generation
-> model evaluation
-> execution policy integration
-> out-of-sample strategy comparison
```

## Module Boundary Rules

These boundary rules are mandatory if the codebase is going to stay coherent.

### Data and feature modules

- must be deterministic
- must not depend on API or frontend modules
- must not write user-facing reports directly

### Strategy modules

- emit execution intent
- should not calculate final TCA summaries
- should not assume a specific transport layer

### Simulation modules

- bar simulation and LOB simulation must remain distinct
- neither should contain frontend formatting logic
- stochastic behavior must be parameterized and seedable

### TCA modules

- should consume normalized fills or execution reports
- should not own schedule generation or market simulation

### Services layer

- can orchestrate workflows
- can attach metadata and provenance
- can assemble API-ready responses
- should avoid embedding nontrivial market logic inline

### API layer

- should translate requests to service calls
- should validate inputs and shape outputs
- should not become a second orchestration layer

## Migration Strategy

The codebase should move in the following pattern:

1. Preserve the current bar-based baseline.
2. Add shared metadata and provenance contracts.
3. Add missing theory and research specs in `docs/`.
4. Add new LOB and alpha modules beside existing code.
5. Integrate them through adapters and service-layer mode switches.
6. Only then expose broader CLI/API/frontend entry points.

This prevents unstable internal experiments from becoming accidental public interfaces.

## What Success Looks Like

The target architecture is achieved when:

- the bar-based path remains a strong baseline
- the synthetic LOB path is a real event-level simulator
- futures and FX semantics are first-class in shared instrument metadata
- predictive alpha research is out-of-sample and execution-integrated
- API, CLI, and reports expose these paths through stable service boundaries

## Related Documents

- `docs/research_execution_master_plan.md`
- `docs/limit_order_fill_simulator_plan.md`
