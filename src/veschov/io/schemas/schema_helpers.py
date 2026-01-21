"""Schema-driven normalization helpers for battle log dataframes."""


import pandas as pd
from pandera.api.pandas.model import DataFrameModel

from veschov.io.columns import add_alias_columns
from veschov.io.schemas.SchemaValidation import reorder_columns

import importlib
import pandas as pd
from pandera.api.dataframe.model import DataFrameModel

def _get_schema_metadata(schema: type[DataFrameModel]) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """
    Look for module-level constants next to the schema class:
      <PREFIX>_COLUMN_RENAMES
      <PREFIX>_COLUMN_ALIASES
      <PREFIX>_COLUMN_ORDER
    Where PREFIX is the schema class name uppercased (e.g., CombatSchema -> COMBAT).
    Falls back to empty values.
    """
    mod = importlib.import_module(schema.__module__)
    prefix = schema.__name__.removesuffix("Schema").upper()  # CombatSchema -> COMBAT
    renames = getattr(mod, f"{prefix}_COLUMN_RENAMES", {}) or {}
    aliases = getattr(mod, f"{prefix}_COLUMN_ALIASES", {}) or {}
    order = getattr(mod, f"{prefix}_COLUMN_ORDER", []) or []
    return dict(renames), dict(aliases), list(order)

def normalize_dataframe_for_schema(df: pd.DataFrame, schema: type[DataFrameModel]) -> pd.DataFrame:
    """Apply schema column renames, aliases, and ordering."""
    updated = df.copy()
    updated.attrs = df.attrs.copy()

    column_renames, column_aliases, column_order = _get_schema_metadata(schema)

    if column_renames:
        updated = updated.rename(columns=column_renames, inplace=False)

    updated = add_alias_columns(updated, aliases=column_aliases or None)

    if column_order:
        updated = reorder_columns(updated, column_order)

    return updated
