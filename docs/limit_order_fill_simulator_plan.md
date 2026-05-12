# Limit Order Placement Grid and Fill Simulator Plan

## Summary

This extension adds a limit-order execution layer between the existing schedule
algorithms and TCA.

The system separates three concepts:

- Execution schedule: TWAP, VWAP, POV, and Adaptive decide when and how much to trade.
- Placement style: market, passive, aggressive, midpoint, pegged, and adaptive limit logic decide where the child order is posted.
- Fill simulator: determines whether the placed order fills, how much fills, and at what price.

## Implementation Shape

The current strategy classes continue to emit child-order intent with timestamp,
ticker, side, strategy, quantity, and reference price.

A new fill simulator layer enriches those child orders with placement details:

- `placement_style`
- `resolved_placement_style`
- `order_type`
- `limit_price`
- `synthetic_bid`
- `synthetic_ask`
- `mid_price`
- `half_spread`

The simulator then emits fill details:

- `submitted_quantity`
- `filled_quantity`
- `unfilled_quantity`
- `fill_status`
- `fill_model`
- `fill_price`
- `spread_cost`
- `impact_cost`
- `temporary_impact`
- `permanent_impact`

## Placement Styles

V1 supports:

- `market`: immediate full fill using the existing synthetic ask/bid cost model.
- `marketable_limit`: buy at synthetic ask, sell at synthetic bid.
- `aggressive_limit`: buy inside the upper spread, sell inside the lower spread.
- `midpoint_limit`: post at synthetic midpoint.
- `passive_limit`: buy at synthetic bid, sell at synthetic ask.
- `primary_peg`: same price as passive in the current bar-based model.
- `midpoint_peg`: same price as midpoint in the current bar-based model.
- `adaptive_limit`: resolves to aggressive, midpoint, or passive based on alpha, spread, liquidity, and bar participation pressure.

## Fill Simulation

The V1 fill model is deterministic and OHLCV-based:

- Market orders always fill the submitted quantity.
- Marketable limits fill the submitted quantity.
- Buy limits are eligible when the bar low touches or crosses the limit.
- Sell limits are eligible when the bar high touches or crosses the limit.
- Passive and pegged fills are volume capped more tightly than aggressive fills.
- Missed orders remain in the simulation output with zero filled quantity.

This is not a queue-position model. It is a first fill simulator that creates
realistic differences between marketable and passive placement while still using
the project's existing OHLCV data contract.

## Refactoring

TCA currently assumes every child order fully fills. The refactor is:

1. Keep `apply_transaction_cost_model()` for the legacy full-fill path.
2. Add simulator output that already contains fill prices and costs.
3. Let `compute_tca_metrics()` handle zero-filled rows by returning `NaN` for price slippage metrics, `0` for realized spread/impact/timing costs, and a valid opportunity cost.
4. Add execution-grid helpers to the backtester so schedules and placements can be compared together.

## CLI Outputs

The execution-grid CLI writes:

- `reports/execution_grid_fills.csv`
- `reports/execution_grid_results.csv`
- `reports/execution_grid_summary_by_strategy.csv`
- `reports/execution_grid_summary_by_placement.csv`
- `reports/execution_grid_summary_by_strategy_placement.csv`

## Test Scenarios

The implementation should verify:

- Existing backtest commands still run.
- Market placement behaves like the current full-fill path.
- Passive buy orders only fill when the bar low touches the limit.
- Passive sell orders only fill when the bar high touches the limit.
- Partial fills reduce fill rate and create opportunity cost.
- Execution-grid results include one row per parent order, strategy, and placement style.
