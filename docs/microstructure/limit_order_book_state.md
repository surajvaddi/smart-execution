# Limit Order Book State

## Purpose

This document defines the core market microstructure concepts that the future synthetic limit order book stack in `smart-execution` is expected to represent.

It is not a claim that the current repository already models all of these concepts. It is the conceptual contract for future implementation.

## Core Objects

### Bid

The highest currently resting buy price in the book.

### Ask

The lowest currently resting sell price in the book.

### Spread

The difference between best ask and best bid.

Interpretation:

- narrow spread: generally lower immediate execution cost
- wide spread: generally higher uncertainty and transaction cost

### Midpoint

The arithmetic midpoint between best bid and best ask.

Uses:

- reference price for TCA
- benchmark for midpoint tactics
- normalization anchor for spread and impact costs

### Depth

Visible resting liquidity at one or more price levels.

Important distinctions:

- top-of-book depth
- total visible depth over several levels
- hidden or reserve depth not visible in displayed book state

## Book Shape

The book is not just best bid and best ask. It is an ordered set of levels on each side.

### Bid side

- sorted descending by price
- higher bid price has higher priority than lower bid price

### Ask side

- sorted ascending by price
- lower ask price has higher priority than higher ask price

## Price-Time Priority

Price-time priority is the default matching rule assumed by the planned synthetic LOB stack.

Rule order:

1. Better price executes first.
2. Among equal prices, older resting orders execute first.

Implications:

- passive execution quality depends on queue arrival time
- cancel-replace loses queue position unless venue-specific exceptions are modeled
- queue position matters for fill probability and fill timing

## Queue Position

Queue position is the ordering of a specific resting order among other orders at the same price level.

Why it matters:

- a passive order can be touched by price but still not fill
- fills depend on how much earlier liquidity is ahead of the order
- latency directly changes effective queue rank

Minimum implementation expectation for the planned simulator:

- every resting order has a deterministic queue order at its level
- cancellations remove earlier queue mass
- modifications that worsen price lose priority
- quantity increases should be treated as cancel-replace unless explicitly modeled otherwise

## Hidden and Iceberg Liquidity

### Hidden liquidity

Liquidity that does not appear in displayed size but can still trade.

### Iceberg liquidity

An order with:

- visible displayed quantity
- hidden reserve quantity

When the visible portion is depleted, a new displayed peak may refresh.

Why it matters:

- displayed depth understates true executable liquidity
- queue behavior can change after refresh events
- passive strategies may misestimate available liquidity if they only use displayed size

MVP guidance for the simulator:

- iceberg orders are in scope
- fully hidden midpoint or dark behavior is not required in the first engine version

## Trade-Through and Sweeps

### Sweep

A marketable order large enough to execute across multiple price levels.

Expected simulator behavior:

- partial consumption of best level
- continuation into deeper levels if quantity remains
- multiple trade prints or execution reports

### Trade-through intuition

In the synthetic single-venue MVP, sweep logic is enough. True multi-venue trade-through handling is out of scope.

## Cancellations and Modifications

Resting liquidity is not static.

Important consequences:

- the queue ahead of an order can shrink because of cancellations
- the queue can also grow because of new earlier arrivals at better prices
- passive fill risk depends on both matching and queue churn

The simulator therefore needs:

- explicit cancellation events
- explicit modification events
- deterministic state transitions

## Book State Needed By The Planned Simulator

The future `matching_engine.py` and related `lob_*` modules should be able to represent:

- instrument id
- side
- price level
- visible quantity
- reserve quantity
- submit time
- effective time
- owner type
- queue order within level

## Implementation Mapping To This Repo

Current repo status:

- current fill logic in `src/fill_simulator.py` is bar-based and does not store book state
- current queue logic is proxy logic, not real level-by-level queue state

Target repo status:

- `src/lob_types.py` will define explicit resting orders, levels, snapshots, and prints
- `src/matching_engine.py` will enforce price-time priority
- `src/lob_execution.py` will allow execution tactics to interact with queue state

## What This Document Prevents

This document exists to prevent two common failures:

1. Calling a bar-touch fill model a real order book model.
2. Building a matching engine without a clear contract for queue semantics.
