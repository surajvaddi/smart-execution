from __future__ import annotations

import pandas as pd

from src.alpha_dataset import build_alpha_feature_matrix
from src.alpha_split import rolling_walk_forward_splits, split_by_date
from src.features import add_microstructure_features
from test_rl_env import sample_market_data


def multi_day_featured_data() -> pd.DataFrame:
    day_one = sample_market_data()
    day_two = sample_market_data().copy()
    day_two.index = day_two.index + pd.Timedelta(days=1)
    day_two["date"] = day_two.index.date
    day_three = sample_market_data().copy()
    day_three.index = day_three.index + pd.Timedelta(days=2)
    day_three["date"] = day_three.index.date
    day_four = sample_market_data().copy()
    day_four.index = day_four.index + pd.Timedelta(days=3)
    day_four["date"] = day_four.index.date
    combined = pd.concat([day_one, day_two, day_three, day_four]).sort_index()
    return add_microstructure_features(combined)


def alpha_dataset() -> pd.DataFrame:
    return build_alpha_feature_matrix(multi_day_featured_data(), horizons=[1])


def test_split_by_date_returns_non_overlapping_windows() -> None:
    splits = split_by_date(
        alpha_dataset(),
        train_end_date="2026-01-02",
        validation_end_date="2026-01-03",
        test_end_date="2026-01-04",
    )

    train_dates = set(pd.to_datetime(splits["train"]["date"]).dt.date)
    validation_dates = set(pd.to_datetime(splits["validation"]["date"]).dt.date)
    test_dates = set(pd.to_datetime(splits["test"]["date"]).dt.date)

    assert train_dates == {pd.Timestamp("2026-01-02").date()}
    assert validation_dates == {pd.Timestamp("2026-01-03").date()}
    assert test_dates == {pd.Timestamp("2026-01-04").date()}
    assert train_dates.isdisjoint(validation_dates)
    assert train_dates.isdisjoint(test_dates)
    assert validation_dates.isdisjoint(test_dates)


def test_rolling_walk_forward_splits_generate_ordered_non_overlapping_windows() -> None:
    splits = rolling_walk_forward_splits(alpha_dataset(), train_days=2, validation_days=1, test_days=1)

    assert len(splits) == 1
    split = splits[0]
    train_dates = set(pd.to_datetime(split["train"]["date"]).dt.date)
    validation_dates = set(pd.to_datetime(split["validation"]["date"]).dt.date)
    test_dates = set(pd.to_datetime(split["test"]["date"]).dt.date)

    assert train_dates == {
        pd.Timestamp("2026-01-02").date(),
        pd.Timestamp("2026-01-03").date(),
    }
    assert validation_dates == {pd.Timestamp("2026-01-04").date()}
    assert test_dates == {pd.Timestamp("2026-01-05").date()}
    assert train_dates.isdisjoint(validation_dates)
    assert train_dates.isdisjoint(test_dates)
    assert validation_dates.isdisjoint(test_dates)
