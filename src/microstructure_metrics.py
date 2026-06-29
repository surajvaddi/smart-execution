"""Bar-data microstructure metric proxies.

These metrics are explicitly proxies. They are designed to create reusable,
named research outputs from OHLCV-style data without implying true order-book
observability.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_kyle_lambda_proxy(
    data: pd.DataFrame,
    return_col: str = "returns",
    volume_col: str = "volume",
) -> pd.DataFrame:
    """Estimate a Kyle-style impact slope from signed returns and signed volume."""
    _require_columns(data, [return_col, volume_col])
    signed_volume = _signed_volume_proxy(data, volume_col=volume_col)
    valid = pd.DataFrame(
        {
            "signed_return": data[return_col],
            "signed_volume_proxy": signed_volume,
        }
    ).replace([np.inf, -np.inf], np.nan).dropna()
    if len(valid) < 2 or valid["signed_volume_proxy"].abs().sum() == 0:
        lambda_value = np.nan
    else:
        slope, _ = np.polyfit(valid["signed_volume_proxy"], valid["signed_return"], 1)
        lambda_value = float(slope)

    return pd.DataFrame(
        [
            {
                "metric": "kyle_lambda_proxy",
                "value": lambda_value,
                "n_obs": int(len(valid)),
                "data_basis": "proxy",
            }
        ]
    )


def compute_vpin_proxy(
    data: pd.DataFrame,
    volume_col: str = "volume",
    bucket_window: int = 5,
) -> pd.DataFrame:
    """Estimate a VPIN-style imbalance proxy from rolling signed volume."""
    _require_columns(data, [volume_col])
    if bucket_window <= 0:
        raise ValueError("bucket_window must be positive.")

    signed_volume = _signed_volume_proxy(data, volume_col=volume_col)
    rolling_abs_imbalance = signed_volume.rolling(bucket_window, min_periods=bucket_window).sum().abs()
    rolling_volume = data[volume_col].rolling(bucket_window, min_periods=bucket_window).sum()
    values = rolling_abs_imbalance / rolling_volume

    return pd.DataFrame(
        {
            "vpin_proxy": values,
            "bucket_window": bucket_window,
            "data_basis": "proxy",
        },
        index=data.index,
    )


def compute_order_flow_autocorrelation_proxy(
    data: pd.DataFrame,
    volume_col: str = "volume",
    lag: int = 1,
) -> pd.DataFrame:
    """Estimate autocorrelation in signed-volume proxy flow."""
    _require_columns(data, [volume_col])
    if lag <= 0:
        raise ValueError("lag must be positive.")

    signed_volume = _signed_volume_proxy(data, volume_col=volume_col)
    autocorr = signed_volume.autocorr(lag=lag)
    return pd.DataFrame(
        [
            {
                "metric": "order_flow_autocorrelation_proxy",
                "value": autocorr,
                "lag": lag,
                "n_obs": int(signed_volume.notna().sum()),
                "data_basis": "proxy",
            }
        ]
    )


def compute_signed_return_impact_proxy(
    data: pd.DataFrame,
    return_col: str = "returns",
    volume_col: str = "volume",
) -> pd.DataFrame:
    """Return row-level interaction between signed flow proxy and realized return."""
    _require_columns(data, [return_col, volume_col])
    signed_volume = _signed_volume_proxy(data, volume_col=volume_col)
    out = pd.DataFrame(index=data.index)
    out["signed_volume_proxy"] = signed_volume
    out["signed_return_impact_proxy"] = signed_volume * data[return_col]
    out["data_basis"] = "proxy"
    return out


def _signed_volume_proxy(data: pd.DataFrame, volume_col: str = "volume") -> pd.Series:
    """Return signed volume using returns when possible, otherwise bar direction."""
    if "returns" in data.columns:
        sign_source = data["returns"]
    elif {"close", "open"}.issubset(data.columns):
        sign_source = data["close"] - data["open"]
    else:
        raise ValueError("Signed-volume proxy requires either returns or open/close columns.")
    return np.sign(sign_source).fillna(0.0) * data[volume_col]


def _require_columns(data: pd.DataFrame, columns: list[str]) -> None:
    """Validate that required columns are present."""
    missing = [column for column in columns if column not in data.columns]
    if missing:
        raise ValueError(f"Missing required microstructure metric columns: {missing}")
