"""Helpers for validating battle log dataframes against pandera schemas."""


import inspect
import logging
from typing import Iterable, Type

import pandas as pd
import pandera as pa
from pandera.api.pandas.model import DataFrameModel
# import veschov.io.schemas.CombatSchema as cs  # adjust import to your actual module

logger = logging.getLogger(__name__)

import inspect
import importlib

# # Import the *package* module, not the CombatSchema class
# schemas_pkg = importlib.import_module("veschov.io.schemas")
#
# print("schemas package file:", getattr(schemas_pkg, "__file__", None))
# print("schemas package contents has CombatSchema:", hasattr(schemas_pkg, "CombatSchema"))
#
# CombatSchema = getattr(schemas_pkg, "CombatSchema")
# print("CombatSchema object:", CombatSchema)
# print("CombatSchema defined in module:", CombatSchema.__module__)
#
# # Now import the module that *actually defines* the class
# combat_mod = importlib.import_module(CombatSchema.__module__)
# print("CombatSchema defining module file:", getattr(combat_mod, "__file__", None))
#
# ann = getattr(CombatSchema, "__annotations__", {})
# print("COLUMN_RENAMES annotated:", "COLUMN_RENAMES" in ann)
# print("COLUMN_RENAMES annotation:", ann.get("COLUMN_RENAMES"))
# print("COLUMN_RENAMES type:", type(getattr(CombatSchema, "COLUMN_RENAMES", None)))
# print("COLUMN_RENAMES sample:", repr(getattr(CombatSchema, "COLUMN_RENAMES", None))[:200])
# ann = CombatSchema.__annotations__["COLUMN_RENAMES"]
# print("annotation python type:", type(ann), repr(ann)[:80])

def reorder_columns(df: pd.DataFrame, column_order: Iterable[str]) -> pd.DataFrame:
    """Return a dataframe with columns ordered to match the provided list."""
    ordered = [column for column in column_order if column in df.columns]
    extras = [column for column in df.columns if column not in ordered]
    return df.loc[:, ordered + extras]


def _add_missing_schema_columns(
    df: pd.DataFrame,
    schema: Type[DataFrameModel],
    *,
    context: str,
) -> pd.DataFrame:
    schema_obj = schema.to_schema()
    updated = df.copy()
    missing_required = [
        name
        for name, column in schema_obj.columns.items()
        if column.required and name not in updated.columns
    ]
    if missing_required:
        logger.warning(
            "Schema %s missing required columns %s; filling with NA values.",
            context,
            ", ".join(missing_required),
        )
    for column in missing_required:
        updated[column] = pd.NA
    return updated


def _coerce_to_schema(df: pd.DataFrame, schema: Type[DataFrameModel]) -> pd.DataFrame:
    schema_obj = schema.to_schema()
    try:
        return schema_obj.coerce_dtype(df)
    except Exception:  # pragma: no cover - defensive guard
        logger.exception("Schema coercion failed; returning uncoerced dataframe.")
        return df


def validate_dataframe(
    df: pd.DataFrame,
    schema: Type[DataFrameModel],
    *,
    soft: bool,
    context: str,
) -> pd.DataFrame:
    """Validate a dataframe and optionally soften errors with warnings/coercion."""
    from veschov.io.schemas.schema_helpers import normalize_dataframe_for_schema

    updated = _add_missing_schema_columns(df, schema, context=context)
    try:
        validated = schema.validate(updated, lazy=True)
    except pa.errors.SchemaErrors as exc:
        if not soft:
            logger.error("Schema validation failed for %s.", context, exc_info=exc)
            raise
        logger.warning(
            "Schema validation issues for %s; coercing in soft mode. Errors=%s",
            context,
            exc.failure_cases.to_string(index=False),
        )
        validated = _coerce_to_schema(updated, schema)
    return normalize_dataframe_for_schema(validated, schema)
