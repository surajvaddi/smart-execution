# Execution Risks

## Purpose

This document captures the main execution-risk concepts that motivate the future synthetic LOB stack and help interpret the current bar-based proxy stack.

The goal is not to pretend that the current system fully models these risks. The goal is to define them clearly and map what the repository does and does not yet capture.

## Maker and Taker Economics

### Taker

A taker crosses the spread and removes resting liquidity.

Typical consequences:

- higher immediate execution certainty
- immediate spread payment
- possible taker fees

### Maker

A maker posts resting liquidity and waits to be executed.

Typical consequences:

- potential spread capture or price improvement
- queue risk
- adverse selection risk
- possible maker rebates

## Adverse Selection

Adverse selection happens when a passive order fills and the subsequent price move is unfavorable.

Examples:

- passive buy fills, then price falls
- passive sell fills, then price rises

Why it matters:

- passive fills are not always cheaper in economic terms
- spread savings can be offset by post-fill adverse movement

Current repo mapping:

- `src/fill_simulator.py` already includes a simple next-bar adverse-selection proxy for bar-based research

Future LOB mapping:

- adverse selection should be measured from post-fill trade path or post-fill mid evolution

## Latency Risk

Latency means the market may change between decision time and effective submission time.

Sources:

- strategy computation delay
- gateway delay
- exchange handling delay
- market data delay

Consequences:

- worse queue position
- missed passive fills
- unintended marketability
- stale execution logic

Minimum simulator implication:

- event time and effective time must be distinct
- queue rank should depend on effective submission order, not just decision order

## Latency Arbitrage

Latency arbitrage is the exploitation of stale quotes or slower participants.

In full real markets this can involve:

- racing to lift stale offers
- hitting quotes before slower participants can cancel
- exploiting information arriving unevenly across venues

In this repository’s planned synthetic setting, the relevant lesson is simpler:

- latency changes execution outcomes
- deterministic action ordering without latency is too optimistic for passive tactics

## Queue Decay Risk

Passive execution depends not only on whether price touches a level, but on whether enough opposing flow arrives before the order is canceled or repriced.

Queue-decay drivers:

- front-of-queue volume ahead of the order
- cancellations ahead of the order
- new better-priced orders displacing the tactic
- changing market regime that makes the limit stale

Current repo mapping:

- current queue-weighted touch and stochastic queue-touch models are proxies for some of this risk

Future repo mapping:

- actual queue position should evolve in the synthetic book state

## Opportunity Cost

Opportunity cost is the cost of not filling the intended quantity.

Examples:

- passive order rests and misses a move
- participation cap prevents completion
- unfilled inventory must be forced later at worse prices

Current repo mapping:

- current TCA path already tracks opportunity cost for unfilled quantity

Future repo mapping:

- LOB execution runner should preserve unfilled inventory state across the episode

## Spread Capture vs Fill Risk Tradeoff

Execution tactics trade off:

- certainty of fill
- price improvement
- information leakage
- adverse selection

Common pattern:

- marketable orders: higher certainty, higher immediate cost
- passive orders: lower immediate cost, lower certainty, higher queue/adverse-selection risk

This tradeoff is one of the main reasons to keep both the bar path and the LOB path in the repo.

## Fee Modeling Guidance For This Repo

The first synthetic LOB implementation does not need a venue-accurate fee schedule, but it should make room for one.

Recommended fields:

- `maker_flag`
- `taker_flag`
- `fee_bps`
- `rebate_bps`

MVP policy:

- keep fee modeling simple and explicit
- never hide fee effects inside other impact terms

## What The Current Repo Models vs Does Not Model

Current bar path models approximately:

- spread-like cost
- temporary and permanent impact proxies
- simple adverse-selection proxy
- opportunity cost

Current bar path does not model directly:

- real maker/taker venue fees
- true queue position
- latency-adjusted submission ranking
- true hidden liquidity behavior

## Why These Risks Matter For Future Phases

These concepts justify:

- latency-aware event schemas
- queue-aware passive execution state
- richer execution reports
- LOB-specific TCA

Without them, the future simulator would only be a more complicated version of the existing bar-touch path instead of a genuinely more realistic research environment.
