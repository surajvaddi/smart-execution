from __future__ import annotations

from src.features import EXTENDED_PROXY_COLUMNS, add_microstructure_features
from src.services import prepare_features
from test_rl_env import sample_market_data


def test_add_microstructure_features_can_include_extended_proxies() -> None:
    featured = add_microstructure_features(sample_market_data(), include_extended_proxies=True)

    for column in EXTENDED_PROXY_COLUMNS:
        assert column in featured.columns


def test_prepare_features_keeps_default_output_stable() -> None:
    featured = prepare_features(sample_market_data())

    for column in EXTENDED_PROXY_COLUMNS:
        assert column not in featured.columns


def test_prepare_features_can_opt_into_extended_proxies() -> None:
    featured = prepare_features(sample_market_data(), include_extended_proxies=True)

    for column in EXTENDED_PROXY_COLUMNS:
        assert column in featured.columns
