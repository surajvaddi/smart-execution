# Target Research Stack

## Purpose

This document defines the intended architecture for `smart-execution` as it grows from a bar-based execution research backtester into a broader execution research platform.

It exists to answer four practical questions:

1. What is the current system?
2. What future subsystems are planned?
3. Where do module boundaries sit?
4. How should new work connect to the existing codebase without creating drift?

This is a design contract, not a marketing document. If code and this document disagree, the discrepancy should be resolved explicitly instead of ignored.

## Current State

Today the repository is primarily a bar-based research system built around processed Yahoo Finance intraday OHLCV data.

Current implemented layers:

- data ingestion and cleaning
- OHLCV-based proxy feature engineering
- signal evaluation on forward returns
- parent-order generation
- schedule generation with TWAP, VWAP, POV, and adaptive heuristics
- bar-based placement and fill simulation
- TCA metrics and strategy summaries
- a lightweight RL environment reusing the bar-based simulator
- API and frontend inspection surfaces

Current architectural truth:

- the project is a valid execution-research backtester on proxy data
- the project is not yet a true order-book simulator
- the project does not yet have a futures-first or FX-first instrument layer
- the project does not yet have a mature predictive alpha modeling stack

## Target End State

The target system has two main research trunks that share common contracts.

### Trunk A: Bar and Proxy Research

Use cases:

- fast execution backtests on saved processed CSVs
- microstructure-inspired feature studies on OHLCV bars
- signal-aware execution benchmarking
- model-driven adaptive execution research on bar data

Primary qualities:

- fast iteration
- reproducible baseline results
- honest proxy labeling

### Trunk B: Event-Level Synthetic Microstructure Research

Use cases:

- event-driven order-book simulation
- queue-aware execution tactics
- latency-sensitive execution experiments
- order-arrival and cancellation regime analysis
- richer execution RL experiments

Primary qualities:

- explicit exchange state
- price-time priority
- event-level auditability
- reproducible stochastic simulation

## High-Level Architecture

```text
                    +----------------------+
                    |   Instrument Specs   |
                    |  equities/futures/FX |
                    +----------+-----------+
                               |
                 +-------------+-------------+
                 |                           |
                 v                           v
       +-------------------+       +----------------------+
       |  Bar/Proxy Data   |       |  Event/LOB Simulator |
       | Yahoo OHLCV CSVs  |       | state + event flow   |
       +---------+---------+       +----------+-----------+
                 |                            |
                 v                            v
       +-------------------+       +----------------------+
       | Proxy Features    |       | Matching Engine      |
       | Signals / Alpha   |       | Queue / Latency      |
       +---------+---------+       +----------+-----------+
                 |                            |
                 v                            v
       +-------------------+       +----------------------+
       | Schedule Policies |<----->| Execution Tactics    |
       | TWAP/VWAP/etc.    |       | market/passive/etc.  |
       +---------+---------+       +----------+-----------+
                 |                            |
                 +-------------+--------------+
                               |
                               v
                     +----------------------+
                     | Execution Reports    |
                     | Fills / TCA / Audit  |
                     +----------+-----------+
                                |
                                v
                     +----------------------+
                     | Services / API / UI  |
                     +----------------------+
```

## Source-of-Truth Layers

The codebase should eventually organize around the following source-of-truth layers.

### Layer 1: Instrument semantics

What belongs here:

- instrument identity
- tick size
- contract multiplier
- session metadata
- expiry and roll metadata

Modules:

- `src/instruments.py`
- `src/futures_math.py`
- `src/futures_sessions.py`
- `src/futures_roll.py`

### Layer 2: Data semantics

What belongs here:

- loader contracts
- dataset metadata
- source provenance
- frequency and timezone labeling

Modules:

- `src/data_loader.py`
- `src/dataset_metadata.py`

### Layer 3: Research features and targets

What belongs here:

- proxy microstructure features
- forward return targets
- alpha feature matrices
- signal-quality summaries

Modules:

- `src/features.py`
- `src/signals.py`
- `src/microstructure_metrics.py`
- `src/microstructure_proxies.py`
- `src/alpha_dataset.py`
- `src/alpha_split.py`

### Layer 4: Execution demand and policy

What belongs here:

- parent orders
- schedule policies
- execution policy configuration
- model-driven or RL-driven control layers

Modules:

- `src/execution.py`
- `src/strategies.py`
- `src/strategies_*`
- `src/strategy_config.py`
- `src/rl_env.py`
- `src/rl_policy.py`

### Layer 5: Market interaction

Bar path:

- `src/fill_simulator.py`

LOB path:

- `src/lob_types.py`
- `src/lob_events.py`
- `src/matching_engine.py`
- `src/lob_generators.py`
- `src/lob_latency.py`
- `src/lob_simulator.py`
- `src/lob_execution.py`

### Layer 6: Cost normalization and evaluation

What belongs here:

- synthetic quote construction
- fill cost decomposition
- parent-level TCA
- LOB-specific execution statistics
- futures normalization

Modules:

- `src/tca.py`
- `src/lob_tca.py`
- `src/futures_tca.py`
- `src/strategy_benchmarks.py`
- `src/alpha_evaluation.py`
- `src/rl_reports.py`

### Layer 7: Orchestration and presentation

What belongs here:

- multi-step workflows
- report assembly
- API transport
- frontend-specific shaping

Modules:

- `src/services.py`
- `src/api.py`
- `src/plots.py`
- `frontend/`

## Bar Path vs LOB Path

This separation is non-negotiable.

### Bar Path

Inputs:

- processed OHLCV data

Mechanics:

- spread and liquidity proxies
- schedule-driven child orders
- synthetic bid/ask
- bar-touch fill logic

Outputs:

- proxy fills
- proxy TCA
- baseline strategy comparisons

Claims allowed:

- bar-based execution research
- proxy microstructure features
- signal-aware scheduling experiments

Claims not allowed:

- real queue position simulation
- real exchange matching
- real hidden liquidity measurement

### LOB Path

Inputs:

- synthetic event flow and synthetic book state
- eventually real LOB/event data if integrated later

Mechanics:

- explicit book levels
- price-time priority
- queue ordering
- cancellations and modifies
- partial fills across levels
- latency-adjusted event ordering

Outputs:

- event logs
- trade prints
- execution reports
- queue-aware TCA

Claims allowed:

- synthetic order-book simulation
- queue-aware execution benchmarking
- latency-sensitive execution experiments

Claims not allowed:

- statements implying venue realism beyond implemented assumptions

## Canonical Data Flow

### Bar research flow

```text
raw CSV / processed CSV
-> cleaned market frame
-> dataset metadata
-> feature engineering
-> signal evaluation / alpha scoring
-> parent order generation
-> schedule policy
-> bar-based placement and fills
-> TCA
-> reports / API / frontend
```

### LOB research flow

```text
instrument spec + simulator config
-> initial synthetic book
-> event generation
-> matching engine state transitions
-> execution child orders enter book
-> fills / queue state / prints
-> execution reports
-> LOB TCA
-> reports / API / frontend
```

## Required Shared Contracts

The following contracts must remain shared across future work.

- dataset metadata contract
- parent-order contract
- child-order intent contract
- execution report contract
- instrument specification contract
- report provenance contract

If any subsystem needs a different shape, the change should be introduced through versioned adapters, not silent schema drift.

## Module Boundary Rules

### Allowed dependencies

- strategies may depend on execution objects and feature columns
- TCA may depend on fill outputs and instrument semantics
- services may depend on all lower layers
- API may depend on services only

### Disallowed dependencies

- matching engine importing API or plotting code
- alpha model code importing frontend or API code
- loader code importing strategy or RL code
- strategy code writing reports directly to disk

## Migration Strategy

The repo should grow in the following order:

1. stabilize and document the current baseline
2. formalize metadata and shared contracts
3. add microstructure knowledge and proxy metrics
4. add LOB domain objects
5. add matching engine
6. add simulator flow and latency
7. connect execution tactics to the LOB path
8. expand strategy coverage
9. add predictive alpha stack
10. add futures and FX instrument depth
11. expose mature workflows through API and UI

## Success Criteria For This Architecture

The architecture is working when:

- new modules can be added without rewriting unrelated layers
- the bar path still runs cleanly as a baseline
- the LOB path can evolve without contaminating proxy claims
- futures support uses instrument semantics instead of ticker heuristics
- alpha models plug into execution through shared contracts
- services can assemble workflows without needing to know internal implementation details of every subsystem

## Immediate Next Artifacts

The next artifacts that should exist after this document are:

- characterization tests for the current bar-based baseline
- dataset metadata helper module
- report provenance helper module
- microstructure docs and proxy metric modules

These create the minimum discipline needed before implementing the matching engine path.
