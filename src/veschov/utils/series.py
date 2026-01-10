"""Helpers for working with pandas series."""

from __future__ import annotations

import pandas as pd


def coerce_numeric(series: pd.Series) -> pd.Series:
    """Coerce a series of strings/numbers to numeric values."""
    cleaned = series.astype(str).str.replace(",", "", regex=False).str.strip()
    return pd.to_numeric(cleaned, errors="coerce")
