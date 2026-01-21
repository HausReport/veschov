"""Schema-driven normalization helpers for battle log dataframes."""

from __future__ import annotations

import pandas as pd
from pandera.api.pandas.model import DataFrameModel

from veschov.io.columns import add_alias_columns
from veschov.io.schemas.SchemaValidation import reorder_columns


def normalize_dataframe_for_schema(
    df: pd.DataFrame,
    schema: type[DataFrameModel],
) -> pd.DataFrame:
    """Apply schema column renames, aliases, and ordering."""
    updated = df.copy()
    updated.attrs = df.attrs.copy()
    column_renames = getattr(schema, "COLUMN_RENAMES", {})
    if column_renames:
        updated = updated.rename(columns=column_renames, inplace=False)
    column_aliases = getattr(schema, "COLUMN_ALIASES", None)
    updated = add_alias_columns(updated, aliases=column_aliases)
    column_order = getattr(schema, "COLUMN_ORDER", [])
    if column_order:
        updated = reorder_columns(updated, column_order)
    return updated
