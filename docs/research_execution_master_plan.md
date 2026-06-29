# Research Execution Master Plan

## Purpose

This document turns the high-level project goals into a concrete implementation specification for the current `smart-execution` repository.

It is designed to do four things:

1. Clarify what the project already is.
2. Clarify what it is not yet.
3. Define a staged, low-ambiguity path to get there.
4. Keep new work connected to the current codebase instead of creating parallel, drifting prototypes.

The plan is intentionally more detailed than a normal roadmap. It specifies:

- commit-level sequencing
- file-level targets
- function-level expectations
- tests and acceptance criteria
- decisions that must be made before implementation
- cross-module contracts needed to avoid architecture drift

## Current Project Reality

The current repository is an intraday smart-execution research backtester built on Yahoo Finance OHLCV bars. It already provides:

- processed OHLCV ingestion
- bar-derived proxy feature engineering
- short-horizon signal evaluation
- parent order generation
- TWAP, VWAP, POV, and adaptive heuristic scheduling
- synthetic bid/ask generation
- bar-based placement and fill simulation
- TCA metrics
- a lightweight RL execution environment
- an API and frontend for inspecting results

This means the repo is already credible as a bar-based execution research tool.

It is not yet credible as:

- a true market microstructure simulator
- a limit order book simulator with exchange state
- a futures and FX execution research platform
- a robust predictive alpha lab
- a serious event-level RL execution environment

## Non-Negotiable Architecture Principles

These principles apply across all phases.

### 1. Preserve the current bar-based path

The existing code is a valid baseline and should remain runnable through the migration.

Requirements:

- existing CLI flows must continue to work
- current tests must keep passing
- new work must be added as an extension, not by overwriting the current bar model

### 2. Separate proxy research from event-level simulation

The repo currently blends feature engineering, proxy execution modeling, and TCA. That is acceptable for the current scope, but the next phases require a clean distinction.

Required distinction:

- `bar/proxy path`: Yahoo OHLCV-based approximations
- `event/LOB path`: explicit order-book state and matching

Nothing in the codebase should imply that a proxy metric is equivalent to a real market microstructure metric.

### 3. Every model and metric must declare its basis

Every new feature, signal, metric, fill model, and report must be explicitly labeled as one of:

- `real`
- `synthetic`
- `proxy`

This avoids accidental overclaiming in docs, charts, and future portfolio use.

### 4. Shared schemas must be centralized

If a concept is used across more than one module, it needs a shared contract.

Examples:

- child order schema
- parent order schema
- event schema
- execution report schema
- alpha dataset schema
- instrument specification schema

### 5. Stochastic behavior must always be reproducible

Every stochastic component must accept:

- `random_seed`
- explicit config

No hidden randomness inside helpers.

### 6. Favor additive modules before refactors

If the current code works, new subsystems should first be added beside it, then integrated through narrow adapters.

This reduces regression risk and makes testing easier.

## Repository-Level Decisions That Must Be Fixed Early

These decisions eliminate ambiguity across later phases.

### Decision A: What are the top-level execution modes?

This must be formalized before adding the LOB stack.

Recommended decision:

- `bar_backtest`
- `lob_backtest`
- `alpha_research`
- `futures_research`
- `rl_execution`

Specification:

- services layer must expose these modes explicitly
- CLI and API should eventually use the same names
- reports should include a `research_mode` column

### Decision B: What is the canonical time model?

Current code uses intraday bar timestamps in `America/New_York`. Event-driven simulation will require more precision.

Recommended decision:

- keep bar timestamps timezone-aware at minute granularity for bar research
- use nanosecond or microsecond-aware pandas timestamps for event simulation
- include both `event_time` and `effective_time` for LOB events

Specification:

- all event modules use timezone-aware timestamps
- latency is modeled as deltas added to `event_time`
- reports preserve the original timezone

### Decision C: What is the canonical quantity model?

Current bar system uses shares and ADV fractions. Futures will require contracts.

Recommended decision:

- keep execution quantity in `native units`
- equities: shares
- futures: contracts
- FX spot: base currency units

Specification:

- parent and child order objects keep `quantity`
- instrument metadata determines interpretation
- TCA normalizers translate to notional, ticks, and dollars

### Decision D: What is the canonical instrument identity?

Current code is ticker-centric. Futures work needs richer identity.

Recommended decision:

- add `instrument_id`
- keep `ticker` as a display and import field
- map `ticker -> instrument_id` for simple equities

Specification:

- instrument-aware modules should not assume plain equities
- existing bar path can continue using `ticker`
- futures layers should require `instrument_id` and `InstrumentSpec`

### Decision E: How much realism is required for the LOB simulator?

This defines scope and prevents overbuilding too early.

Recommended minimum viable realism:

- price-time priority
- multiple price levels
- market orders
- passive and aggressive limit orders
- partial fills
- cancellations
- modifications
- queue position tracking
- optional iceberg behavior
- configurable latency

Explicitly deferred from MVP:

- fragmented venues
- smart order routing
- implied matching
- auction opens/closes
- exchange-specific fee schedules beyond a simple model

### Decision F: What is the alpha evaluation standard?

Current alpha evaluation is descriptive. Future alpha work must be out-of-sample.

Recommended decision:

- all models evaluated with date-based train/validation/test splits
- optional walk-forward validation
- metrics reported by horizon and by split

Required metrics:

- IC
- rank IC
- hit rate
- decile spread
- turnover proxy
- stability across dates

## Cross-Codebase Shared Specifications

These specifications are needed before the deeper phases to keep modules connected.

## Shared Spec 1: Dataset metadata

Create a central metadata helper for any loaded or transformed dataset.

Target module:

- `src/dataset_metadata.py`

Required fields:

- `dataset_name`
- `source_name`
- `frequency`
- `timezone`
- `instrument_type`
- `data_basis`
- `contains_quotes`
- `contains_depth`
- `contains_order_events`
- `contains_trade_events`

Rules:

- bar data from Yahoo must set `data_basis = proxy`
- synthetic quote columns do not change dataset basis to `real`
- event-replay or simulator outputs must declare whether they are `synthetic` or `real`

## Shared Spec 2: Research result provenance

Every saved report should carry provenance fields.

Required columns:

- `research_mode`
- `data_basis`
- `source_dataset`
- `model_name`
- `simulation_model`
- `random_seed`
- `config_id`

This must be enforced in services/report-writing code.

## Shared Spec 3: Execution report schema

Needed for both bar fills and LOB fills.

Required fields:

- `timestamp`
- `parent_order_id`
- `child_order_id`
- `instrument_id`
- `ticker`
- `side`
- `submitted_quantity`
- `filled_quantity`
- `remaining_quantity`
- `fill_price`
- `fill_status`
- `execution_venue`
- `simulation_model`
- `data_basis`

Optional fields for LOB mode:

- `queue_position_at_submit`
- `queue_position_at_fill`
- `latency_us`
- `book_level`
- `maker_flag`
- `taker_flag`

## Shared Spec 4: Instrument specification

Needed before futures work.

Target module:

- `src/instruments.py`

Required fields:

- `instrument_id`
- `ticker`
- `instrument_type`
- `quote_currency`
- `base_currency`
- `tick_size`
- `contract_multiplier`
- `session_timezone`
- `trading_hours`
- `expiry_date`
- `roll_rule`

Behavior:

- equities may leave expiry and roll fields empty
- futures must define tick size and multiplier
- calendar spread helpers consume two compatible futures specs

## Shared Spec 5: Alpha dataset contract

Target module:

- `src/alpha_dataset.py`

Required sections:

- raw feature columns
- transformed feature columns
- target columns
- split metadata
- leakage-control metadata

Required anti-leakage rules:

- no target horizon can use future data in features
- any rolling feature must only use past and current rows
- train/validation/test split boundaries must be date-based, not row-random

## Shared Spec 6: Canonical object relationships

The project will become much harder to reason about once the repo contains bar data, event data, simulated exchange state, execution state, futures metadata, and alpha model artifacts. The object relationship graph must therefore be explicit.

Canonical relationship chain:

`InstrumentSpec -> DatasetMetadata -> ParentOrder -> ChildOrderIntent -> PlacementDecision -> ExecutionReport -> ParentTCAResult`

Additional LOB-mode relationship chain:

`InstrumentSpec -> BookSnapshot/EventBatch -> RestingOrder/TradePrint -> ExecutionReport -> ParentTCAResult`

Rules:

- `InstrumentSpec` is the root dependency for anything instrument-aware.
- `DatasetMetadata` describes the basis and provenance of any research frame.
- `ParentOrder` is the canonical expression of execution demand.
- `ChildOrderIntent` expresses schedule output before placement.
- `PlacementDecision` expresses where the intent is posted.
- `ExecutionReport` expresses actual realized fills.
- `ParentTCAResult` is the normalized summary row used in comparisons.

Anti-patterns to avoid:

- strategy modules reading raw CSV path assumptions directly
- TCA modules inferring instrument semantics from ticker string parsing
- alpha modules mutating parent-order or fill schemas in place
- LOB execution reports using a one-off schema incompatible with current TCA

## Shared Spec 7: Canonical service boundaries

The current repository already has a `services.py` module. As the codebase grows, service boundaries must be made stricter so research logic does not leak into API handlers or frontend-specific view shaping.

Recommended boundaries:

- `src/data_loader.py`: raw external data ingestion and cleaning
- `src/features.py`: deterministic feature generation on prepared data
- `src/signals.py`: descriptive signal evaluation only
- `src/alpha_*`: predictive model dataset, train, predict, evaluate
- `src/strategies_*`: schedule policies that emit child-order intents
- `src/fill_simulator.py`: bar-based placement and fill simulation only
- `src/lob_*` and `src/matching_engine.py`: event-driven exchange simulation only
- `src/tca.py`, `src/lob_tca.py`, `src/futures_tca.py`: cost and performance normalization only
- `src/services.py`: orchestration of end-to-end user-facing workflows
- `src/api.py`: transport layer only

Prohibited service leakage:

- API handlers should not compute features inline.
- Frontend-oriented formatting should not live in simulation or TCA modules.
- Strategy modules should not write reports to disk.
- Matching engine code should not import plotting or API modules.

## Shared Spec 8: Required output artifact families

The project should eventually emit outputs in a small number of standardized families rather than ad hoc CSV names.

Required artifact families:

- `dataset_profile`
- `feature_frame`
- `signal_evaluation`
- `alpha_scorecard`
- `parent_orders`
- `execution_tape`
- `fill_tape`
- `parent_tca_results`
- `strategy_comparison`
- `lob_event_log`
- `lob_snapshot_series`
- `futures_roll_profile`
- `rl_policy_report`

Required artifact metadata fields:

- `artifact_family`
- `artifact_version`
- `generated_at`
- `research_mode`
- `data_basis`
- `source_dataset`

## Shared Spec 9: Naming and schema stability rules

To prevent churn and accidental incompatibility, schema naming should follow a consistent standard.

Rules:

- quantity fields must explicitly state whether they mean submitted, filled, or remaining quantity
- cost fields must explicitly encode units when not obvious, for example `_bps`, `_ticks`, `_usd`
- any proxy metric must include `_proxy` in its raw internal feature name unless intentionally promoted to a model score or summary artifact
- identifier columns must end in `_id`
- boolean flags should end in `_flag` where ambiguity is possible
- model scores should use `score` rather than `signal` once they come from fitted predictive models

Examples:

- `filled_quantity`
- `adverse_selection_cost_bps`
- `queue_pressure_proxy`
- `parent_order_id`
- `maker_flag`
- `alpha_model_score`

## Shared Spec 10: Backward-compatibility policy

Because the repo already has working tests, API endpoints, and a frontend, the implementation plan needs an explicit policy for breakage.

Rules:

- preserve existing public endpoint names unless there is a strong reason to version them
- preserve current CSV artifact columns where practical and add new columns additively
- prefer new optional parameters to silent behavior changes
- when a breaking change is unavoidable, it must be called out in README and test names

Migration standard:

- add new interface
- adapt callers
- deprecate old interface
- remove old interface only after tests and docs reflect the new path

## Dependency Graph

The phase order is not enough on its own. The repo also needs a dependency graph that explains what cannot start until something else exists.

### Hard dependencies

- Phase 0 is a dependency for every later phase.
- Phase 2 is a dependency for Phases 3, 4, and 5.
- Phase 3 is a dependency for Phase 4 and Phase 5.
- Phase 4 is a dependency for meaningful Phase 5 integration.
- Phase 7 depends on `InstrumentSpec` and quantity normalization policies being fixed.
- Phase 8 depends on feature stability and leakage rules from Shared Spec 5.
- Phase 9 depends on strategy coverage from Phase 6 and stronger state inputs from Phases 1, 5, or 8.
- Phase 10 depends on stable artifact families and service boundaries.

### Soft dependencies

- Phase 1 can proceed in parallel with Phase 0.3 and 0.4 once metadata conventions are clear.
- Phase 6 can begin before Phase 5 completes if it targets only the existing bar path first.
- Phase 8 can begin before Phase 7 if it remains equity/bar focused.
- Phase 7 can begin before the full LOB stack if it starts with metadata and normalization work.

### Parallelization guidance

Good parallel tracks once Phase 0 is complete:

- Track A: microstructure docs and proxy metrics
- Track B: LOB domain types and matching engine
- Track C: strategy refactors and new policies
- Track D: alpha dataset and modeling

Bad parallelization patterns:

- building API and frontend surfaces before core schemas stabilize
- adding futures analytics before `InstrumentSpec` exists
- adding RL state features before feature names and model-score conventions are fixed

## Canonical Interface Sketches

These are not final code signatures, but they are the target shape needed to keep implementations aligned.

### Parent order

Required semantic fields:

- `parent_order_id`
- `instrument_id`
- `ticker`
- `side`
- `quantity`
- `start_time`
- `end_time`
- `participation_cap`
- `benchmark_price_type`
- `research_mode`

### Child order intent

Required semantic fields:

- `child_order_id`
- `parent_order_id`
- `timestamp`
- `instrument_id`
- `ticker`
- `side`
- `strategy`
- `quantity`
- `reference_price`
- `schedule_reason`

### Placement decision

Required semantic fields:

- `child_order_id`
- `placement_style`
- `resolved_placement_style`
- `order_type`
- `limit_price`
- `venue`
- `time_in_force`
- `maker_taker_intent`

### Parent TCA result

Required semantic fields:

- `parent_order_id`
- `strategy`
- `simulation_model`
- `data_basis`
- `arrival_price`
- `avg_fill_price`
- `implementation_shortfall_bps`
- `fill_rate`
- `opportunity_cost_bps`
- `execution_duration`

### Alpha model artifact

Required semantic fields:

- `model_name`
- `feature_set_name`
- `train_start`
- `train_end`
- `validation_start`
- `validation_end`
- `test_start`
- `test_end`
- `target_horizon`
- `data_basis`

## Milestone Gates

Each major subsystem should have a gate that blocks the next layer from claiming readiness too early.

### Gate G0: Baseline preservation

Must be true before Phase 2 is considered active:

- characterization tests exist for current scheduling and fill logic
- README and docs explicitly distinguish proxy vs future true LOB work
- dataset metadata and provenance policy exist

### Gate G1: LOB domain readiness

Must be true before matching engine work is considered stable:

- order, event, and snapshot schemas are defined
- replayability from event logs is possible
- latency-aware timestamps exist in the event schema

### Gate G2: Matching engine readiness

Must be true before LOB simulator work claims usefulness:

- price-time priority is implemented
- market orders, crossing limits, cancels, and modify semantics exist
- queue ordering tests pass

### Gate G3: Exchange simulation readiness

Must be true before execution-on-LOB claims are made:

- exogenous arrivals, cancels, and market orders exist
- latency affects effective ordering
- full episode runner produces event logs, prints, and snapshots

### Gate G4: Execution research readiness

Must be true before saying the project supports queue-aware execution:

- parent orders can trade against the LOB simulator
- passive and aggressive tactics are supported
- queue position affects fill timing or likelihood
- LOB TCA metrics exist

### Gate G5: Alpha research readiness

Must be true before claiming predictive alpha modeling:

- leakage-safe dataset builder exists
- at least two model families exist
- out-of-sample evaluation exists
- model scores are integrated into execution comparisons

### Gate G6: Futures readiness

Must be true before claiming futures specialization:

- instrument specs support futures
- tick-value and contract arithmetic exist
- roll methodology is implemented and explicit
- TCA outputs can be normalized in futures-relevant units

## Per-Phase Definition of Done Checklists

The earlier commit lists are detailed, but each phase also needs a concise end-state checklist.

### Phase 0 done when

- baseline behavior is pinned by tests
- shared metadata and provenance helpers exist
- architecture docs explain the target stack

### Phase 1 done when

- microstructure docs cover the named concepts at a usable level
- proxy metrics exist in code
- extended proxy features can be integrated without breaking defaults

### Phase 2 done when

- LOB objects and event types are explicit
- event replay is deterministic
- object relationships are documented

### Phase 3 done when

- matching engine supports insert, match, cancel, modify, and iceberg basics
- queue ordering is test-covered

### Phase 4 done when

- exchange flow generators exist
- latency model exists
- simulator can run a full episode with reproducible outputs

### Phase 5 done when

- execution child orders interact with the simulated book
- queue-aware fills and cancels are possible
- LOB execution results map into normalized TCA

### Phase 6 done when

- strategy logic is modular
- IS and adaptive participation are implemented
- benchmark utilities compare strategy families statistically

### Phase 7 done when

- instrument metadata supports futures and FX semantics
- roll and spread helpers exist
- TCA normalization covers ticks and dollars

### Phase 8 done when

- leakage-safe alpha datasets exist
- baseline linear and nonlinear models exist
- out-of-sample scorecards exist
- model scores influence execution policy comparisons

### Phase 9 done when

- RL has train/eval splits
- state can optionally include richer features
- RL reports include regret and policy behavior summaries

### Phase 10 done when

- services expose the main research modes coherently
- CLI and API paths are explicit and non-ambiguous
- docs cover end-to-end usage flows

## Implementation Risks and Failure Modes

This project is large enough that the plan should name the most likely ways it can go wrong.

### Risk 1: Proxy and real concepts get blended

Failure mode:

- the repo starts presenting bar-derived features as if they were real order-book measurements

Mitigation:

- enforce `data_basis`
- keep `_proxy` naming
- separate bar and LOB service paths

### Risk 2: Matching engine and simulator drift apart

Failure mode:

- simulator generators emit events the engine cannot handle cleanly

Mitigation:

- formal event schema
- replay tests
- G1 and G2 milestone gates

### Risk 3: Strategy outputs become incompatible across paths

Failure mode:

- bar strategies and LOB strategies return incompatible child-order or fill schemas

Mitigation:

- centralize child-order intent and execution report contracts
- add adapter layers rather than special-case fields everywhere

### Risk 4: Alpha research becomes leaky or overfit

Failure mode:

- model performance looks strong because of row-random splitting or future leakage

Mitigation:

- date-based split utilities
- explicit leakage checks
- out-of-sample-only scorecards

### Risk 5: Futures support becomes cosmetic only

Failure mode:

- futures are mentioned in docs, but the code still assumes equities everywhere

Mitigation:

- instrument-rooted arithmetic
- futures-specific normalization tests
- roll/spread helpers as first-class modules

### Risk 6: API and frontend cement unstable schemas too early

Failure mode:

- UI code starts depending on fields that are still changing across core modules

Mitigation:

- delay broad productization until core schemas stabilize
- treat services as the only frontend-facing shaping layer

## Recommended First 15 Build Commits

This is the narrowest high-value path that turns the document into action while keeping momentum.

1. `docs: define target architecture for proxy execution, lob simulation, futures, and alpha research`
2. `test: add characterization tests for existing scheduling fill and tca behavior`
3. `feat: add dataset metadata and provenance helpers`
4. `feat: add shared research result provenance columns`
5. `docs: add limit order book mechanics specification`
6. `docs: add maker taker fees latency arbitrage and adverse selection notes`
7. `docs: add vpin kyle lambda and almgren chriss implementation notes`
8. `feat: add microstructure metric proxy module`
9. `feat: add queue pressure and hidden liquidity proxy features`
10. `feat: add order book core data types`
11. `feat: add exchange event schema with latency aware timestamps`
12. `feat: add book replay and serialization helpers`
13. `feat: implement empty book and price level management`
14. `feat: implement limit order insertion with price time priority`
15. `feat: implement market order execution across book levels`

Reason for this ordering:

- the first 9 commits remove conceptual ambiguity and establish metadata discipline
- commits 10 to 15 produce the first durable LOB foundation without requiring premature UI or service integration

## Review Protocol For Every Future PR

The plan should also specify how work gets checked, not just what gets built.

Every PR that implements part of this plan should answer:

1. Which phase and commit item does this PR satisfy?
2. Which shared spec does it rely on or modify?
3. Does it add `real`, `synthetic`, or `proxy` outputs?
4. What schema did it add or change?
5. Which tests prove the new behavior?
6. Does it preserve the current bar-based baseline?
7. Does it introduce any new randomness, and if so, where is the seed?

If a PR cannot answer those questions cleanly, it is likely crossing boundaries or introducing ambiguity too early.

## Implementation Plan

The phases below are ordered to preserve repo integrity and reduce risk.

---

# Phase 0: Guardrails, contracts, and characterization

## Goal

Freeze current behavior, introduce shared contracts, and document the target architecture before major subsystem work starts.

## Why this phase exists

Without characterization, later refactors will silently alter current execution behavior. Without shared contracts, the codebase will fragment into unrelated modules.

## Commits

### Commit 0.1

`docs: define target architecture for proxy execution, lob simulation, futures, and alpha research`

Files:

- `docs/architecture/target_research_stack.md`
- `README.md`

Implementation details:

- add a diagram showing current modules and future modules
- define where bar path stops and LOB path begins
- define which modules remain baseline vs which are new

Acceptance criteria:

- a new contributor can understand the long-term repo shape in one read
- the README no longer implies that the current simulator is a true order book simulator

Decisions required:

- whether to keep all docs in `docs/architecture/` and `docs/microstructure/`

### Commit 0.2

`test: add characterization tests for existing scheduling fill and tca behavior`

Files:

- `tests/test_backtester_characterization.py`
- `tests/test_strategy_characterization.py`
- `tests/test_fill_simulator_characterization.py`

Implementation details:

- pin TWAP quantity splitting
- pin VWAP cap behavior
- pin POV incomplete-fill behavior
- pin adaptive heuristic scaling on obvious signal cases
- pin fill simulator behavior for current placement styles

Acceptance criteria:

- later refactors can prove whether they changed baseline behavior

Decisions required:

- whether to use exact numerical expectations or tolerances

Recommended:

- exact for discrete logic
- tolerance-based for floating-point aggregates

### Commit 0.3

`feat: add dataset metadata and provenance helpers`

Files:

- `src/dataset_metadata.py`
- small integrations in `src/services.py`

Functions:

- `build_dataset_metadata`
- `attach_dataset_metadata`
- `validate_dataset_metadata`

Tests:

- `tests/test_dataset_metadata.py`

Acceptance criteria:

- any DataFrame passed into services can be tagged with source and basis metadata

### Commit 0.4

`feat: add shared research result provenance columns`

Files:

- `src/report_provenance.py`
- integrate into `src/services.py`, `src/backtester.py`, and report writers

Functions:

- `build_provenance_record`
- `attach_provenance_columns`

Tests:

- `tests/test_report_provenance.py`

Acceptance criteria:

- all new reports have uniform provenance columns

---

# Phase 1: Microstructure knowledge and proxy research expansion

## Goal

Close the conceptual gap in market microstructure while keeping a sharp distinction between true measurements and bar-data proxies.

## Why this phase exists

The current repo uses microstructure-like language, but the theoretical layer is not encoded in either docs or reusable metrics. This phase makes the project intellectually coherent before building the simulator.

## Commits

### Commit 1.1

`docs: add limit order book mechanics specification`

Files:

- `docs/microstructure/limit_order_book_state.md`

Required sections:

- top of book
- level 2 depth
- price-time priority
- queue position
- hidden and iceberg liquidity
- spread and depth dynamics
- trade-through and sweep examples

Acceptance criteria:

- defines exactly what the future matching engine must implement

### Commit 1.2

`docs: add maker taker fees latency arbitrage and adverse selection notes`

Files:

- `docs/microstructure/execution_risks.md`

Required sections:

- maker rebate vs taker fee mechanics
- adverse selection after passive fills
- latency arbitrage intuition
- cancellation risk
- queue decay risk

Acceptance criteria:

- explains which of these will be simulated in MVP and which will only be approximated

### Commit 1.3

`docs: add vpin kyle lambda and almgren chriss implementation notes`

Files:

- `docs/microstructure/flow_and_execution_models.md`

Required sections:

- VPIN definition
- Kyle's lambda regression setup
- Almgren-Chriss intuition
- temporary vs permanent impact
- optimal execution tradeoff between risk and cost

Acceptance criteria:

- formulas are explicit enough to implement from the document

### Commit 1.4

`feat: add microstructure metric proxy module`

Files:

- `src/microstructure_metrics.py`

Functions:

- `compute_kyle_lambda_proxy`
- `compute_vpin_proxy`
- `compute_order_flow_autocorrelation_proxy`
- `compute_signed_return_impact_proxy`

Tests:

- `tests/test_microstructure_metrics.py`

Implementation notes:

- these functions should consume bar-level data only
- return either scalar summaries or time series consistently
- document assumptions inline

Acceptance criteria:

- outputs are stable on small synthetic test frames
- all functions raise on missing required columns

Decisions required:

- whether these functions return plain Series/DataFrames or richer typed objects

Recommended:

- return DataFrames with explicit metric name columns for easier report wiring

### Commit 1.5

`feat: add queue pressure and hidden liquidity proxy features`

Files:

- `src/microstructure_proxies.py`

Functions:

- `compute_queue_pressure_proxy`
- `compute_hidden_liquidity_proxy`
- `compute_passive_fill_risk_proxy`

Tests:

- `tests/test_microstructure_proxies.py`

Acceptance criteria:

- functions can be joined to the current feature pipeline without mutating existing outputs

### Commit 1.6

`feat: add optional microstructure enrichment to feature engineering`

Files:

- `src/features.py`
- `src/services.py`

Implementation details:

- keep current `add_microstructure_features(df)` behavior stable
- add optional flag-based enrichment path

Possible API:

- `add_microstructure_features(df, include_extended_proxies=False)`

Tests:

- `tests/test_feature_enrichment.py`

Acceptance criteria:

- default output remains backward compatible
- enriched output includes extra proxy metrics only when enabled

### Commit 1.7

`feat: add microstructure regime summary report`

Files:

- `src/microstructure_reports.py`

Functions:

- `summarize_microstructure_regimes`
- `microstructure_metric_scorecard`

Tests:

- `tests/test_microstructure_reports.py`

Acceptance criteria:

- project can generate a coherent report explaining flow, volatility, and liquidity regimes on bar data

---

# Phase 2: Core LOB domain model

## Goal

Define the objects and event contracts for a true book simulator before writing matching logic.

## Why this phase exists

Most simulator failures happen because people skip the domain contract and jump straight into matching code.

## Commits

### Commit 2.1

`feat: add order book core data types`

Files:

- `src/lob_types.py`

Required types:

- `RestingOrder`
- `BookLevel`
- `BookSnapshot`
- `TradePrint`
- `ExecutionReport`

Required fields for `RestingOrder`:

- `order_id`
- `parent_order_id`
- `child_order_id`
- `side`
- `price`
- `visible_quantity`
- `reserve_quantity`
- `submitted_at`
- `effective_at`
- `owner_type`
- `instrument_id`

Tests:

- `tests/test_lob_types.py`

Acceptance criteria:

- types validate invalid quantities and invalid sides
- hidden liquidity fields are explicit even if unused initially

### Commit 2.2

`feat: add exchange event schema with latency aware timestamps`

Files:

- `src/lob_events.py`

Required event types:

- `LimitAddEvent`
- `MarketOrderEvent`
- `CancelEvent`
- `ModifyEvent`
- `EventBatch`

Required event fields:

- `event_id`
- `event_time`
- `effective_time`
- `instrument_id`
- `source`
- `random_seed`

Tests:

- `tests/test_lob_events.py`

Acceptance criteria:

- events can be sorted deterministically
- events can represent both exogenous market flow and our own execution flow

### Commit 2.3

`feat: add book replay and serialization helpers`

Files:

- `src/lob_replay.py`

Functions:

- `snapshot_to_frame`
- `events_to_frame`
- `execution_reports_to_frame`
- `replay_events`

Tests:

- `tests/test_lob_replay.py`

Acceptance criteria:

- book state can be reconstructed from event logs

Decisions required:

- whether to store book state as nested objects or level-indexed dicts internally

Recommended:

- nested objects for correctness, helper conversion to flat frames for reporting

---

# Phase 3: Matching engine

## Goal

Build the first true price-time priority engine for the repo.

## Why this phase exists

This is the point where the project starts becoming a real microstructure simulation platform rather than an execution backtester with proxy fills.

## Commits

### Commit 3.1

`feat: implement empty book and price level management`

Files:

- `src/matching_engine.py`

Functions:

- `create_empty_book`
- `best_bid`
- `best_ask`
- `add_price_level`
- `remove_price_level_if_empty`

Tests:

- `tests/test_matching_engine_levels.py`

Acceptance criteria:

- bid levels sort descending
- ask levels sort ascending
- empty levels are cleaned correctly

### Commit 3.2

`feat: implement limit order insertion with price time priority`

Files:

- `src/matching_engine.py`

Functions:

- `submit_limit_order`
- `append_to_queue`

Tests:

- `tests/test_matching_engine_submission.py`

Acceptance criteria:

- same-price orders keep FIFO
- non-crossing orders rest on the book

### Commit 3.3

`feat: implement market order execution across book levels`

Files:

- `src/matching_engine.py`

Functions:

- `execute_market_order`
- `consume_top_of_book`

Tests:

- `tests/test_matching_engine_market_orders.py`

Acceptance criteria:

- market orders can sweep multiple levels
- partial fill state is returned when liquidity is insufficient

### Commit 3.4

`feat: implement crossing limit order matching`

Files:

- `src/matching_engine.py`

Functions:

- `match_crossing_limit_order`
- `rest_residual_quantity`

Tests:

- `tests/test_matching_engine_crossing_limits.py`

Acceptance criteria:

- crossing quantity matches immediately
- residual quantity rests at the submitted limit price

### Commit 3.5

`feat: implement cancel and modify semantics`

Files:

- `src/matching_engine.py`

Functions:

- `cancel_order`
- `modify_order_quantity`
- `modify_order_price`

Tests:

- `tests/test_matching_engine_order_updates.py`

Acceptance criteria:

- quantity reductions do not lose queue priority
- price changes do lose queue priority

Decision required:

- whether quantity increases retain priority

Recommended:

- no, treat quantity increase as cancel-replace unless modeled otherwise

### Commit 3.6

`feat: add iceberg and hidden liquidity behavior`

Files:

- `src/matching_engine.py`
- `src/lob_types.py`

Functions:

- `refresh_iceberg_peak`
- `is_hidden_order`

Tests:

- `tests/test_matching_engine_iceberg.py`

Acceptance criteria:

- reserve quantity refreshes after visible peak depletion
- queue effects of refreshed liquidity are explicit and documented

---

# Phase 4: Synthetic LOB market simulator

## Goal

Simulate exogenous market flow around the matching engine.

## Why this phase exists

A matching engine alone is not a market simulator. It needs arrivals, cancellations, and latency.

## Commits

### Commit 4.1

`feat: add simulator configuration models for arrivals cancellations and latency`

Files:

- `src/lob_simulator_config.py`

Types:

- `ArrivalProcessConfig`
- `CancellationProcessConfig`
- `LatencyModelConfig`
- `BookInitializationConfig`

Tests:

- `tests/test_lob_simulator_config.py`

Acceptance criteria:

- config objects validate invalid rates, probabilities, and latency values

### Commit 4.2

`feat: implement initial book generation helpers`

Files:

- `src/lob_generators.py`

Functions:

- `build_initial_book_snapshot`
- `seed_symmetric_depth`
- `seed_imbalanced_depth`

Tests:

- `tests/test_lob_initialization.py`

Acceptance criteria:

- simulator can start from a non-empty book with configurable shape

### Commit 4.3

`feat: implement exogenous limit order arrival generator`

Files:

- `src/lob_generators.py`

Functions:

- `generate_limit_add_events`
- `sample_price_offset`
- `sample_limit_size`

Tests:

- `tests/test_lob_generators_limit_adds.py`

Acceptance criteria:

- generator can create near-touch and deep-book arrivals

Decision required:

- distribution family for price offsets

Recommended:

- start with discrete level offsets and configurable probabilities

### Commit 4.4

`feat: implement exogenous cancellation generator`

Files:

- `src/lob_generators.py`

Functions:

- `generate_cancel_events`
- `sample_cancel_candidates`

Tests:

- `tests/test_lob_generators_cancels.py`

Acceptance criteria:

- cancellations only target live orders
- cancellation rate can vary by depth level

### Commit 4.5

`feat: implement market order flow generator`

Files:

- `src/lob_generators.py`

Functions:

- `generate_market_order_events`
- `sample_market_order_side`
- `sample_market_order_size`

Tests:

- `tests/test_lob_generators_market_orders.py`

Acceptance criteria:

- generator can produce balanced and imbalanced order flow regimes

### Commit 4.6

`feat: implement latency application and effective event scheduling`

Files:

- `src/lob_latency.py`

Functions:

- `sample_gateway_latency`
- `sample_exchange_latency`
- `apply_event_latency`
- `sort_events_by_effective_time`

Tests:

- `tests/test_lob_latency.py`

Acceptance criteria:

- effective ordering can differ from event creation ordering
- fixed seed yields deterministic results

### Commit 4.7

`feat: implement one step book advance`

Files:

- `src/lob_simulator.py`

Functions:

- `advance_book_one_step`
- `apply_event_batch`

Tests:

- `tests/test_lob_simulator_step.py`

Acceptance criteria:

- one step applies new exogenous flow and returns updated book plus prints

### Commit 4.8

`feat: implement full lob simulation episode runner`

Files:

- `src/lob_simulator.py`

Functions:

- `run_lob_simulation_episode`
- `collect_episode_summary`

Tests:

- `tests/test_lob_simulator_episode.py`

Acceptance criteria:

- returns event log, snapshots, prints, and summary metrics

---

# Phase 5: Execution on top of the LOB simulator

## Goal

Make the simulator relevant to execution research by letting our child orders interact with the book.

## Why this phase exists

The project goal is not only to simulate a market, but to compare execution algorithms within that market.

## Commits

### Commit 5.1

`feat: add queue aware child order state model`

Files:

- `src/lob_execution.py`

Types/functions:

- `ChildOrderState`
- `create_child_order_state`
- `update_queue_position`

Tests:

- `tests/test_lob_execution_queue.py`

Acceptance criteria:

- child orders retain state across multiple simulation steps

### Commit 5.2

`feat: implement execution child submission on the matching engine`

Files:

- `src/lob_execution.py`

Functions:

- `submit_execution_child_order`
- `submit_market_execution_child`
- `submit_limit_execution_child`

Tests:

- `tests/test_lob_execution_submission.py`

Acceptance criteria:

- execution child orders enter the same book and event stream as exogenous orders

### Commit 5.3

`feat: implement passive aggressive and midpoint tactics on lob`

Files:

- `src/lob_execution.py`

Functions:

- `place_passive_child`
- `place_aggressive_child`
- `place_midpoint_child`

Tests:

- `tests/test_lob_execution_placement.py`

Acceptance criteria:

- tactics map to explicit book prices and queue outcomes

Decision required:

- whether midpoint is simulated as a synthetic hidden venue or as an internalized crossing point

Recommended MVP:

- synthetic midpoint venue, clearly labeled as `synthetic`

### Commit 5.4

`feat: implement cancel replace lifecycle for execution orders`

Files:

- `src/lob_execution.py`

Functions:

- `cancel_replace_child_order`
- `cancel_stale_child_orders`

Tests:

- `tests/test_lob_execution_lifecycle.py`

Acceptance criteria:

- stale passive orders can be canceled and reposted with new queue position

### Commit 5.5

`feat: add parent order execution runner on lob`

Files:

- `src/lob_execution_runner.py`

Functions:

- `execute_parent_order_on_lob`
- `run_schedule_against_lob_episode`

Tests:

- `tests/test_lob_execution_runner.py`

Acceptance criteria:

- parent execution returns fills in a schema comparable with current TCA pipeline

### Commit 5.6

`feat: add lob based execution metrics and queue statistics`

Files:

- `src/lob_tca.py`

Functions:

- `queue_wait_time_stats`
- `realized_spread_bps`
- `realized_impact_from_trade_path`
- `fill_probability_by_queue_position`

Tests:

- `tests/test_lob_tca.py`

Acceptance criteria:

- execution outcomes can be measured in a richer way than bar-touch heuristics

---

# Phase 6: Strategy expansion

## Goal

Add the missing execution algorithms and turn current heuristics into configurable policy families.

## Why this phase exists

The project already has baseline strategies, but it needs cleaner separation and additional policies to look credible as execution research.

## Commits

### Commit 6.1

`refactor: split existing strategy implementations into dedicated modules`

Files:

- `src/strategies_twap.py`
- `src/strategies_vwap.py`
- `src/strategies_pov.py`
- `src/strategies_adaptive.py`
- keep thin compatibility layer in `src/strategies.py`

Tests:

- extend existing strategy tests

Acceptance criteria:

- no output drift for current policies

### Commit 6.2

`feat: add strategy config objects`

Files:

- `src/strategy_config.py`

Types:

- `TWAPConfig`
- `VWAPConfig`
- `POVConfig`
- `AdaptiveConfig`
- `ImplementationShortfallConfig`
- `AdaptiveParticipationConfig`

Tests:

- `tests/test_strategy_config.py`

Acceptance criteria:

- hard-coded constants are replaced with explicit config surfaces

### Commit 6.3

`feat: implement implementation shortfall schedule`

Files:

- `src/strategies_is.py`

Functions:

- `generate_is_schedule`
- `compute_risk_adjusted_urgency`
- `frontload_fraction_from_alpha`

Tests:

- `tests/test_strategies_is.py`

Acceptance criteria:

- buys accelerate under positive alpha and higher risk aversion
- sells accelerate under negative alpha and higher risk aversion

### Commit 6.4

`feat: implement adaptive participation schedule`

Files:

- `src/strategies_adaptive_participation.py`

Functions:

- `generate_adaptive_participation_schedule`
- `target_participation_rate`

Tests:

- `tests/test_strategies_adaptive_participation.py`

Acceptance criteria:

- participation target varies with liquidity, volatility, and signal

### Commit 6.5

`feat: add common strategy benchmarking utilities`

Files:

- `src/strategy_benchmarks.py`

Functions:

- `compare_strategy_results`
- `bootstrap_strategy_difference`
- `strategy_tail_risk_summary`

Tests:

- `tests/test_strategy_benchmarks.py`

Acceptance criteria:

- strategy comparison is statistical, not only descriptive

### Commit 6.6

`feat: add strategy comparison report outputs`

Files:

- `src/services.py`
- optional plot/report additions

Tests:

- `tests/test_services.py`

Acceptance criteria:

- service layer can generate comparison tables for all strategy families

---

# Phase 7: Futures and FX support

## Goal

Make the repo instrument-aware enough to support futures execution research.

## Why this phase exists

The current equity-style share model is not enough for the stated career goals.

## Commits

### Commit 7.1

`feat: add instrument specification model for equities futures and fx`

Files:

- `src/instruments.py`

Types/functions:

- `InstrumentSpec`
- `load_builtin_instrument_specs`
- `lookup_instrument_spec`

Tests:

- `tests/test_instruments.py`

Acceptance criteria:

- can represent equities, futures, and FX spot cleanly

### Commit 7.2

`feat: add futures arithmetic helpers`

Files:

- `src/futures_math.py`

Functions:

- `tick_value`
- `price_move_to_ticks`
- `contracts_to_notional`
- `ticks_to_dollars`

Tests:

- `tests/test_futures_math.py`

Acceptance criteria:

- TCA can be normalized meaningfully for futures

### Commit 7.3

`feat: add futures session and liquidity profile helpers`

Files:

- `src/futures_sessions.py`

Functions:

- `session_mask_for_instrument`
- `session_liquidity_profile`

Tests:

- `tests/test_futures_sessions.py`

Acceptance criteria:

- repo can distinguish session behavior from equity regular-hours assumptions

### Commit 7.4

`feat: add continuous contract roll utilities`

Files:

- `src/futures_roll.py`

Functions:

- `compute_roll_dates`
- `back_adjust_series`
- `ratio_adjust_series`
- `build_continuous_contract`

Tests:

- `tests/test_futures_roll.py`

Acceptance criteria:

- roll methodology is explicit and reproducible

Decision required:

- default roll rule

Recommended:

- volume-based rollover with explicit override support

### Commit 7.5

`feat: add calendar spread pricing helpers`

Files:

- `src/calendar_spreads.py`

Functions:

- `price_calendar_spread`
- `spread_tick_value`
- `spread_notional`

Tests:

- `tests/test_calendar_spreads.py`

Acceptance criteria:

- spreads can be represented as first-class research objects

### Commit 7.6

`feat: add futures aware tca normalization`

Files:

- `src/futures_tca.py`
- minimal adapter changes in `src/tca.py`

Functions:

- `normalize_fill_to_ticks`
- `normalize_fill_to_dollars`
- `normalize_parent_tca_for_futures`

Tests:

- `tests/test_futures_tca.py`

Acceptance criteria:

- results can be reported in bps, ticks, and dollars where appropriate

---

# Phase 8: Predictive alpha modeling

## Goal

Move from descriptive proxy signals to a real intraday alpha research stack.

## Why this phase exists

Current signal work is a good start, but it is not yet a robust predictive modeling framework.

## Commits

### Commit 8.1

`feat: add alpha dataset builder with leakage safe targets`

Files:

- `src/alpha_dataset.py`

Functions:

- `attach_forward_targets`
- `build_alpha_feature_matrix`
- `drop_leaky_columns`
- `validate_alpha_dataset`

Tests:

- `tests/test_alpha_dataset.py`

Acceptance criteria:

- feature matrix and targets are built without leakage

### Commit 8.2

`feat: add date based alpha splitting utilities`

Files:

- `src/alpha_split.py`

Functions:

- `split_by_date`
- `rolling_walk_forward_splits`

Tests:

- `tests/test_alpha_split.py`

Acceptance criteria:

- train, validation, and test windows never overlap

### Commit 8.3

`feat: add baseline linear alpha models`

Files:

- `src/alpha_models_linear.py`

Functions:

- `fit_ridge_alpha_model`
- `fit_lasso_alpha_model`
- `predict_linear_alpha`

Tests:

- `tests/test_alpha_models_linear.py`

Acceptance criteria:

- models train and predict deterministically on fixed data

### Commit 8.4

`feat: add nonlinear tree based alpha models`

Files:

- `src/alpha_models_tree.py`

Functions:

- `fit_random_forest_alpha_model`
- `fit_gradient_boosted_alpha_model`
- `predict_tree_alpha`

Tests:

- `tests/test_alpha_models_tree.py`

Acceptance criteria:

- models can capture interactions among liquidity, volatility, and flow proxies

### Commit 8.5

`feat: add alpha evaluation scorecards`

Files:

- `src/alpha_evaluation.py`

Functions:

- `rank_ic`
- `bucket_return_spread`
- `calibration_table`
- `model_scorecard`

Tests:

- `tests/test_alpha_evaluation.py`

Acceptance criteria:

- evaluation is comparable across models and horizons

### Commit 8.6

`feat: wire model scores into execution feature frames`

Files:

- `src/features.py`
- `src/services.py`

Functions:

- `attach_alpha_model_score`

Tests:

- `tests/test_alpha_integration.py`

Acceptance criteria:

- execution strategies can consume model scores alongside or instead of heuristic `alpha_signal`

### Commit 8.7

`feat: add model based adaptive execution strategy`

Files:

- `src/strategies_model_adaptive.py`

Functions:

- `generate_model_adaptive_schedule`
- `model_score_to_execution_multiplier`

Tests:

- `tests/test_strategies_model_adaptive.py`

Acceptance criteria:

- model-based policy is benchmarked against current adaptive heuristic

---

# Phase 9: RL execution upgrade

## Goal

Turn RL from a lightweight experiment into a structured research layer.

## Why this phase exists

The current RL environment is useful as a prototype, but it is not yet rigorous enough to support strong claims.

## Commits

### Commit 9.1

`feat: add rl train eval dataset utilities`

Files:

- `src/rl_dataset.py`

Functions:

- `build_rl_train_orders`
- `build_rl_eval_orders`
- `split_rl_orders_by_date`

Tests:

- `tests/test_rl_dataset.py`

Acceptance criteria:

- RL training and evaluation are separated cleanly

### Commit 9.2

`feat: enrich rl state with optional alpha and microstructure features`

Files:

- `src/rl_env.py`

Implementation details:

- preserve current state schema as baseline mode
- add extended-state mode

Tests:

- extend `tests/test_rl_env.py`

Acceptance criteria:

- old tests still pass
- extended states are opt-in

### Commit 9.3

`feat: add rl evaluation and regret reports`

Files:

- `src/rl_reports.py`

Functions:

- `policy_regret_table`
- `action_frequency_report`
- `state_slice_performance`

Tests:

- `tests/test_rl_reports.py`

Acceptance criteria:

- RL results are inspectable and comparable to classical baselines

### Commit 9.4

`feat: add out of sample rl benchmarking against all execution strategies`

Files:

- `src/rl_backtester.py`
- `src/services.py`

Tests:

- `tests/test_rl_backtester.py`

Acceptance criteria:

- RL policy performance is measured out of sample against TWAP, VWAP, POV, Adaptive, IS, and adaptive participation

---

# Phase 10: Integration, APIs, and workflows

## Goal

Expose the new subsystems coherently without breaking the current user experience.

## Why this phase exists

The repo already has CLI, API, and frontend surfaces. New capabilities should be attached cleanly rather than via ad hoc entry points.

## Commits

### Commit 10.1

`feat: add backtester mode abstraction for bar and lob research`

Files:

- `src/backtester.py`
- `src/services.py`

Functions:

- `run_bar_backtest`
- `run_lob_backtest`
- adapter helpers for shared result schemas

Tests:

- `tests/test_backtester_modes.py`

Acceptance criteria:

- services can switch execution engines through an explicit mode

### Commit 10.2

`feat: extend cli for lob futures and alpha workflows`

Files:

- `main.py`

Tests:

- extend `tests/test_cli.py`

Acceptance criteria:

- users can run core new workflows from CLI without ambiguity

Required design rule:

- do not overload old flags with new semantics
- prefer new explicit subcommands or grouped flags

### Commit 10.3

`feat: add api endpoints for alpha microstructure and lob summaries`

Files:

- `src/api.py`
- `src/services.py`

Tests:

- extend `tests/test_api.py`

Acceptance criteria:

- API can serve new reports with provenance metadata

### Commit 10.4

`docs: add end to end workflows for each research track`

Files:

- `docs/workflows/bar_execution_research.md`
- `docs/workflows/lob_execution_research.md`
- `docs/workflows/futures_execution_research.md`
- `docs/workflows/alpha_model_research.md`

Acceptance criteria:

- a user can follow each workflow from data to report

---

# Decision Register

The following decisions should be explicitly recorded as they are made.

## DR-1: Internal book representation

Options:

- nested objects
- dict of price -> queue
- DataFrame-backed structure

Recommended:

- object model internally, flat frames only for reporting

Reason:

- clearer semantics for queue operations and hidden liquidity

## DR-2: Latency granularity

Options:

- milliseconds
- microseconds
- nanoseconds

Recommended:

- microseconds

Reason:

- enough realism without overcomplicating event ordering

## DR-3: Iceberg queue semantics

Options:

- refreshed peak goes to back of queue
- refreshed peak retains special priority

Recommended:

- refreshed peak goes to back of queue unless venue-specific behavior is modeled

## DR-4: Midpoint execution semantics

Options:

- synthetic midpoint venue
- hidden midpoint resting inside the same book

Recommended:

- synthetic midpoint venue in MVP

Reason:

- simpler and more honest about synthetic assumptions

## DR-5: Futures roll rule default

Options:

- date-based
- volume-based
- open-interest-based

Recommended:

- volume-based default with explicit override

## DR-6: Alpha target horizons

Options:

- keep current `[1, 3, 6, 12]`
- extend to more horizons

Recommended:

- keep current set first, extend only after baseline evaluation is stable

## DR-7: RL training regime

Options:

- one global policy across all symbols
- one policy per symbol
- one policy per instrument class

Recommended:

- one policy per instrument class first

Reason:

- avoids overfitting to a single symbol while keeping state distribution manageable

---

# Testing Strategy

## Unit tests

Use for:

- metric calculations
- schema validation
- matching engine primitives
- config validation

## Integration tests

Use for:

- full parent-order execution on bar path
- parent-order execution on LOB path
- alpha model fit/evaluate workflow
- futures normalization workflow

## Characterization tests

Use for:

- current strategy behavior
- current fill simulator logic
- current service outputs

## Property-style tests

Useful for:

- queue conservation
- non-negative depth
- sum of fills never exceeds order quantity
- cancellations never remove nonexistent liquidity

## Reproducibility tests

Required anywhere randomness exists:

- same seed gives same events, fills, and reports
- different seeds can change outcomes where intended

---

# Report and Portfolio Alignment

The final architecture should support telling two honest stories:

## Story 1: Bar-based execution research

Claims the repo can support:

- scheduling research on intraday bar data
- proxy microstructure features
- signal-aware execution studies
- bar-based TCA and strategy benchmarking

Claims the repo should not make:

- true queue position modeling
- real exchange matching behavior

## Story 2: Synthetic microstructure research platform

Claims the repo can support after LOB phases:

- event-level order-book simulation
- price-time priority matching
- queue-aware limit execution
- partial fills, cancels, and latency effects
- execution benchmarking in a synthetic market

This split is important because it keeps portfolio claims accurate.

---

# Suggested Near-Term Build Order

If implementation starts immediately, the most defensible order is:

1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 3
5. Phase 4
6. Phase 5
7. Phase 6
8. Phase 8
9. Phase 7
10. Phase 9
11. Phase 10

Why this order:

- phases 0 to 5 create the strongest qualitative jump in project credibility
- phase 6 makes the simulator useful for direct execution comparisons
- phase 8 adds predictive modeling depth
- phase 7 adds domain breadth for futures and FX
- phase 9 becomes much more valuable once the simulator and alpha stack are stronger

---

# Definition of Success

The project should be considered to have met the target goals only when all of the following are true:

1. Market microstructure concepts are documented, implemented where applicable, and correctly labeled as proxy or synthetic.
2. A real event-level LOB simulator exists with matching, queue position, cancellations, latency, and partial fills.
3. Execution algorithms include TWAP, VWAP, POV, adaptive heuristic, implementation shortfall, adaptive participation, and RL, all benchmarked quantitatively.
4. Futures and FX workflows include instrument specs, tick math, roll methodology, and spread-aware analytics.
5. Predictive alpha modeling includes leakage-safe datasets, multiple model families, and out-of-sample evaluation.
6. Services, CLI, and reports expose these capabilities coherently.
7. The current bar-based path still works as a baseline.

---

# Final Implementation Rule

Do not collapse ambiguity into code.

When a design question affects more than one subsystem, record the decision first, then implement it through shared contracts. That is the only reliable way to keep this repository coherent as it grows from a bar backtester into a true execution research platform.
