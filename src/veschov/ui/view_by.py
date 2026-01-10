"""Shared helpers for selecting shot vs. round views."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from veschov.utils.series import coerce_numeric

VIEW_BY_OPTIONS = ("Shot index", "Round")


def select_view_by(
    key: str,
    *,
    label: str = "View by",
    default_index: int = 0,
) -> str:
    """Render the view-by control and return the selected option."""
    return st.radio(
        label,
        VIEW_BY_OPTIONS,
        index=default_index,
        horizontal=True,
        key=key,
    )


def prepare_round_view(
    df: pd.DataFrame,
    *,
    round_column: str = "round",
) -> pd.DataFrame | None:
    """Coerce and validate round data, returning a filtered frame or None."""
    if round_column not in df.columns:
        st.warning("Round data is unavailable for this battle log.")
        return None
    round_series = coerce_numeric(df[round_column])
    round_df = df.assign(**{round_column: round_series})
    round_df = round_df[round_df[round_column].notna()].copy()
    if round_df.empty:
        st.warning("No round data is available for this selection.")
        return None
    round_df[round_column] = round_df[round_column].astype(int)
    return round_df
