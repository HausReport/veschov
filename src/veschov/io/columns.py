"""Canonical column naming policy and normalization helpers."""

from __future__ import annotations

import pandas as pd

CANONICAL_COLUMN_STYLE = "snake_case"

def resolve_event_type(
    df: pd.DataFrame,
    *,
    event_type_column: str = "event_type",
    ability_type_column: str = "ability_type",
) -> pd.Series | None:
    """
    Resolve the authoritative event_type column.

    If ability_type is present, it overrides event_type when non-null.
    """
    if event_type_column not in df.columns and ability_type_column not in df.columns:
        return None
    base = (
        df[event_type_column]
        if event_type_column in df.columns
        else pd.Series(pd.NA, index=df.index)
    )
    if ability_type_column in df.columns:
        return base.where(df[ability_type_column].isna(), df[ability_type_column])
    return base


def add_alias_columns(
    df: pd.DataFrame,
    *,
    aliases: dict[str, str] | None,
) -> pd.DataFrame:
    """Add alias columns for canonical sources (does not drop originals)."""
    updated = df.copy()
    updated.attrs = df.attrs.copy()
    alias_map = aliases or {}
    for alias, source in alias_map.items():
        if alias in updated.columns:
            continue
        if source in updated.columns:
            updated[alias] = updated[source]
    return updated


# def canonicalize_columns(df: pd.DataFrame, *, columns: Iterable[str]) -> pd.DataFrame:
#     """Lowercase column names in-place for a provided list."""
#     updated = df.copy()
#     updated.attrs = df.attrs.copy()
#     mapping = {column: column.lower() for column in columns if column in updated.columns}
#     if mapping:
#         updated = updated.rename(columns=mapping, inplace=False)
#     return updated
