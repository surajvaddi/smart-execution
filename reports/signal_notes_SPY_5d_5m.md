# Phase 3 Signal Research Notes

Input data: `data/processed/SPY_5d_5m.csv`
Signal-horizon tests: 32

## Top Signals By Mean Absolute IC

- volume_zscore: mean absolute IC 0.071264, best horizon 12 bars, best-horizon IC 0.126991, mean hit rate 0.501014.
- liquidity_score: mean absolute IC 0.063510, best horizon 6 bars, best-horizon IC -0.102529, mean hit rate 0.448145.
- spread_proxy: mean absolute IC 0.050929, best horizon 12 bars, best-horizon IC 0.075417, mean hit rate 0.549526.

## Alpha Signal

alpha_signal mean absolute IC was 0.024460; its strongest horizon was 6 bars with IC -0.046322.

## Interpretation

- These results are preliminary because the current sample is only the saved local sample, not the full multi-ticker 60-day research set.
- IC values are small, which is normal for short-horizon intraday signals and means the adaptive strategy should treat alpha as one input, not a standalone trading rule.
- Signals based on spread, volume, volatility, and imbalance are OHLCV proxies, not true order book measurements.
- Phase 4 onward should evaluate whether any weak signal value survives spread, impact, timing, and opportunity costs.
