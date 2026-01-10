"""Resolve canonical combat log columns (attacker_name/target_name) and aliases."""

from __future__ import annotations

from typing import Iterable

import pandas as pd

ATTACKER_COLUMN_CANDIDATES = ("attacker_name", "Attacker")
TARGET_COLUMN_CANDIDATES = ("target_name", "Target", "Defender Name")


def resolve_column(df: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    """Return the first matching column name from the ordered candidates."""
    return next((candidate for candidate in candidates if candidate in df.columns), None)


def get_series(df: pd.DataFrame, column: str) -> pd.Series:
    """Return a column series or an NA-filled placeholder for missing columns."""
    if column in df.columns:
        return df[column]
    return pd.Series(pd.NA, index=df.index)
