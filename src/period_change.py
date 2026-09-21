"""Changes over the contest's fixed January–June observation window."""

from __future__ import annotations

from math import isfinite

import pandas as pd


START_MONTH = pd.Timestamp("2026-01-01")
END_MONTH = pd.Timestamp("2026-06-01")


def jan_jun_change(series: pd.Series) -> float | None:
    """Return None when either endpoint is unobserved or the base is unusable."""
    if START_MONTH not in series.index or END_MONTH not in series.index:
        return None
    start = pd.to_numeric(series.loc[START_MONTH], errors="coerce")
    end = pd.to_numeric(series.loc[END_MONTH], errors="coerce")
    if pd.isna(start) or pd.isna(end) or not isfinite(float(start)) or not isfinite(float(end)) or start <= 0:
        return None
    return float(end / start - 1)


def format_change(value: float | None) -> str:
    return "산출 불가" if value is None else f"{value:+.1%}"
