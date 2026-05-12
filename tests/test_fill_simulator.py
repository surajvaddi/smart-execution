"""Tests for limit placement and deterministic fill simulation."""

from __future__ import annotations

import math
import unittest
from datetime import time

import pandas as pd

from src.execution import ParentOrder
from src.fill_simulator import FillModelConfig, add_order_placement, place_and_simulate_fills
from src.tca import apply_transaction_cost_model, compute_tca_metrics


class FillSimulatorTest(unittest.TestCase):
    """Focused regression tests for the placement/fill layer."""

    def setUp(self) -> None:
        self.timestamp = pd.Timestamp("2026-01-02 10:00:00", tz="America/New_York")
        self.market_data = pd.DataFrame(
            {
                "ticker": ["XYZ"],
                "date": [self.timestamp.date()],
                "time": [self.timestamp.time()],
                "open": [100.0],
                "high": [101.5],
                "low": [98.5],
                "close": [100.0],
                "volume": [10_000.0],
                "spread_proxy": [0.02],
                "alpha_signal": [0.0],
                "liquidity_score": [1.0],
                "bar_index": [0],
            },
            index=pd.Index([self.timestamp], name="timestamp"),
        )
        self.parent_order = ParentOrder(
            ticker="XYZ",
            side="buy",
            quantity=1_000.0,
            start_time=time(10, 0),
            end_time=time(10, 5),
            participation_cap=0.10,
            date=self.timestamp.date(),
            order_id="XYZ_test_buy",
        )

    def child_orders(self, side: str = "buy", quantity: float = 1_000.0) -> pd.DataFrame:
        """Return one child order matching the synthetic market row."""
        return pd.DataFrame(
            {
                "timestamp": [self.timestamp],
                "ticker": ["XYZ"],
                "side": [side],
                "strategy": ["TWAP"],
                "quantity": [quantity],
                "reference_price": [100.0],
            }
        )

    def test_limit_prices_are_side_aware(self) -> None:
        """Placement styles should map to deterministic synthetic prices."""
        buy_child = self.child_orders("buy")
        sell_child = self.child_orders("sell")

        buy_passive = add_order_placement(buy_child, self.market_data, "passive_limit")
        sell_passive = add_order_placement(sell_child, self.market_data, "passive_limit")
        buy_aggressive = add_order_placement(buy_child, self.market_data, "aggressive_limit")
        sell_aggressive = add_order_placement(sell_child, self.market_data, "aggressive_limit")
        midpoint = add_order_placement(buy_child, self.market_data, "midpoint_limit")
        market = add_order_placement(buy_child, self.market_data, "market")

        self.assertAlmostEqual(buy_passive.loc[0, "limit_price"], 99.0)
        self.assertAlmostEqual(sell_passive.loc[0, "limit_price"], 101.0)
        self.assertAlmostEqual(buy_aggressive.loc[0, "limit_price"], 100.75)
        self.assertAlmostEqual(sell_aggressive.loc[0, "limit_price"], 99.25)
        self.assertAlmostEqual(midpoint.loc[0, "limit_price"], 100.0)
        self.assertEqual(market.loc[0, "order_type"], "market")
        self.assertTrue(math.isnan(market.loc[0, "limit_price"]))

    def test_passive_buy_fills_when_low_touches_limit(self) -> None:
        """A passive buy at synthetic bid fills when the bar low crosses bid."""
        fills = place_and_simulate_fills(
            child_orders=self.child_orders("buy"),
            market_data=self.market_data,
            placement_style="passive_limit",
            parent_order=self.parent_order,
        )

        self.assertEqual(fills.loc[0, "fill_status"], "partial")
        self.assertAlmostEqual(fills.loc[0, "submitted_quantity"], 1_000.0)
        self.assertAlmostEqual(fills.loc[0, "filled_quantity"], 250.0)
        self.assertAlmostEqual(fills.loc[0, "unfilled_quantity"], 750.0)
        self.assertAlmostEqual(fills.loc[0, "quantity"], 250.0)

    def test_passive_buy_misses_when_low_does_not_touch_limit(self) -> None:
        """A passive buy remains unfilled when the bar never trades to bid."""
        market_data = self.market_data.copy()
        market_data["low"] = 99.5

        fills = place_and_simulate_fills(
            child_orders=self.child_orders("buy"),
            market_data=market_data,
            placement_style="passive_limit",
            parent_order=self.parent_order,
        )

        self.assertEqual(fills.loc[0, "fill_status"], "unfilled")
        self.assertAlmostEqual(fills.loc[0, "filled_quantity"], 0.0)
        self.assertAlmostEqual(fills.loc[0, "unfilled_quantity"], 1_000.0)
        self.assertTrue(math.isnan(fills.loc[0, "fill_price"]))

    def test_passive_sell_fills_when_high_touches_limit(self) -> None:
        """A passive sell at synthetic ask fills when the bar high crosses ask."""
        sell_order = ParentOrder(
            ticker="XYZ",
            side="sell",
            quantity=1_000.0,
            start_time=time(10, 0),
            end_time=time(10, 5),
            participation_cap=0.10,
            date=self.timestamp.date(),
            order_id="XYZ_test_sell",
        )

        fills = place_and_simulate_fills(
            child_orders=self.child_orders("sell"),
            market_data=self.market_data,
            placement_style="passive_limit",
            parent_order=sell_order,
        )

        self.assertEqual(fills.loc[0, "fill_status"], "partial")
        self.assertAlmostEqual(fills.loc[0, "filled_quantity"], 250.0)
        self.assertAlmostEqual(fills.loc[0, "limit_price"], 101.0)

    def test_market_placement_matches_legacy_transaction_cost_model(self) -> None:
        """Market placement should preserve the existing full-fill cost path."""
        child_orders = self.child_orders("buy")
        legacy = apply_transaction_cost_model(child_orders, self.market_data)
        simulated = place_and_simulate_fills(
            child_orders=child_orders,
            market_data=self.market_data,
            placement_style="market",
            parent_order=self.parent_order,
        )

        self.assertAlmostEqual(simulated.loc[0, "quantity"], legacy.loc[0, "quantity"])
        self.assertAlmostEqual(simulated.loc[0, "fill_price"], legacy.loc[0, "fill_price"])
        self.assertAlmostEqual(simulated.loc[0, "spread_cost"], legacy.loc[0, "spread_cost"])
        self.assertAlmostEqual(simulated.loc[0, "impact_cost"], legacy.loc[0, "impact_cost"])
        self.assertEqual(simulated.loc[0, "fill_status"], "filled")

    def test_queue_weighted_touch_is_more_conservative_for_passive_orders(self) -> None:
        """Queue-weighted fills scale touched limit capacity by depth and priority."""
        base_fills = place_and_simulate_fills(
            child_orders=self.child_orders("buy"),
            market_data=self.market_data,
            placement_style="passive_limit",
            parent_order=self.parent_order,
        )
        queue_fills = place_and_simulate_fills(
            child_orders=self.child_orders("buy"),
            market_data=self.market_data,
            placement_style="passive_limit",
            parent_order=self.parent_order,
            fill_model="queue_weighted_touch",
        )

        self.assertEqual(queue_fills.loc[0, "fill_model"], "queue_weighted_touch")
        self.assertAlmostEqual(queue_fills.loc[0, "touch_depth"], 1.0 / 6.0)
        self.assertAlmostEqual(queue_fills.loc[0, "queue_priority"], 0.30)
        self.assertAlmostEqual(queue_fills.loc[0, "fill_probability"], 0.05)
        self.assertAlmostEqual(queue_fills.loc[0, "filled_quantity"], 12.5)
        self.assertLess(
            queue_fills.loc[0, "filled_quantity"],
            base_fills.loc[0, "filled_quantity"],
        )

    def test_queue_weighted_touch_keeps_market_orders_full_fill(self) -> None:
        """Queue assumptions should not reduce market-order fills."""
        fills = place_and_simulate_fills(
            child_orders=self.child_orders("buy"),
            market_data=self.market_data,
            placement_style="market",
            parent_order=self.parent_order,
            fill_model="queue_weighted_touch",
        )

        self.assertEqual(fills.loc[0, "fill_status"], "filled")
        self.assertAlmostEqual(fills.loc[0, "filled_quantity"], 1_000.0)
        self.assertAlmostEqual(fills.loc[0, "fill_probability"], 1.0)

    def test_fill_model_config_controls_deterministic_capacity(self) -> None:
        """Capacity multipliers should be explicit configurable assumptions."""
        config = FillModelConfig(
            capacity_multipliers={"passive_limit": 0.10},
            queue_priorities={"passive_limit": 0.30},
            default_capacity_multiplier=0.25,
            default_queue_priority=0.30,
        )

        fills = place_and_simulate_fills(
            child_orders=self.child_orders("buy"),
            market_data=self.market_data,
            placement_style="passive_limit",
            parent_order=self.parent_order,
            fill_config=config,
        )

        self.assertAlmostEqual(fills.loc[0, "filled_quantity"], 100.0)

    def test_stochastic_queue_touch_is_seed_reproducible(self) -> None:
        """Stochastic fills should be reproducible with a fixed seed."""
        first = place_and_simulate_fills(
            child_orders=self.child_orders("buy"),
            market_data=self.market_data,
            placement_style="passive_limit",
            parent_order=self.parent_order,
            fill_model="stochastic_queue_touch",
            random_seed=31,
        )
        second = place_and_simulate_fills(
            child_orders=self.child_orders("buy"),
            market_data=self.market_data,
            placement_style="passive_limit",
            parent_order=self.parent_order,
            fill_model="stochastic_queue_touch",
            random_seed=31,
        )

        self.assertAlmostEqual(first.loc[0, "random_draw"], second.loc[0, "random_draw"])
        self.assertAlmostEqual(first.loc[0, "filled_quantity"], second.loc[0, "filled_quantity"])
        self.assertAlmostEqual(first.loc[0, "random_draw"], 0.01227824739797545)
        self.assertAlmostEqual(first.loc[0, "fill_probability"], 0.05)
        self.assertAlmostEqual(first.loc[0, "filled_quantity"], 250.0)

    def test_stochastic_queue_touch_can_miss_touched_limits(self) -> None:
        """A touched limit can still miss when the random draw exceeds probability."""
        fills = place_and_simulate_fills(
            child_orders=self.child_orders("buy"),
            market_data=self.market_data,
            placement_style="passive_limit",
            parent_order=self.parent_order,
            fill_model="stochastic_queue_touch",
            random_seed=1,
        )

        self.assertAlmostEqual(fills.loc[0, "random_draw"], 0.13436424411240122)
        self.assertAlmostEqual(fills.loc[0, "fill_probability"], 0.05)
        self.assertEqual(fills.loc[0, "fill_status"], "unfilled")
        self.assertAlmostEqual(fills.loc[0, "filled_quantity"], 0.0)

    def test_tca_metrics_support_zero_fills(self) -> None:
        """A fully missed limit placement should still produce a TCA result row."""
        second_timestamp = pd.Timestamp("2026-01-02 10:05:00", tz="America/New_York")
        market_data = pd.concat(
            [
                self.market_data.assign(low=99.5),
                pd.DataFrame(
                    {
                        "ticker": ["XYZ"],
                        "date": [second_timestamp.date()],
                        "time": [second_timestamp.time()],
                        "open": [102.0],
                        "high": [102.5],
                        "low": [101.5],
                        "close": [102.0],
                        "volume": [10_000.0],
                        "spread_proxy": [0.02],
                        "alpha_signal": [0.0],
                        "liquidity_score": [1.0],
                        "bar_index": [1],
                    },
                    index=pd.Index([second_timestamp], name="timestamp"),
                ),
            ]
        )
        fills = place_and_simulate_fills(
            child_orders=self.child_orders("buy"),
            market_data=market_data,
            placement_style="passive_limit",
            parent_order=self.parent_order,
        )

        metrics = compute_tca_metrics(self.parent_order, fills, market_data)

        self.assertEqual(metrics["fill_rate"], 0.0)
        self.assertTrue(math.isnan(metrics["avg_fill_price"]))
        self.assertTrue(math.isnan(metrics["implementation_shortfall_bps"]))
        self.assertGreater(metrics["opportunity_cost_bps"], 0.0)
        self.assertEqual(metrics["execution_duration"], pd.Timedelta(0))


if __name__ == "__main__":
    unittest.main()
