"""Pandera schema for fleet metadata dataframes."""


from typing import ClassVar

import pandas as pd
import pandera as pa
from pandera.typing import Series

COLUMN_ORDER: ClassVar[list[str]] = [
    "Fleet Type",
    "Attack",
    "Defense",
    "Health",
    "buff_applied",
    "debuff_applied",
]

class FleetsSchema(pa.DataFrameModel):
    """Schema definition for fleet metadata rows."""

    fleet_type: Series[str] = pa.Field(alias="Fleet Type", nullable=True)
    attack: Series[float] = pa.Field(alias="Attack", nullable=True)
    defense: Series[float] = pa.Field(alias="Defense", nullable=True)
    health: Series[float] = pa.Field(alias="Health", nullable=True)

    buff_applied: Series[pd.BooleanDtype] = pa.Field(nullable=True)
    debuff_applied: Series[pd.BooleanDtype] = pa.Field(nullable=True)

    class Config:
        """Enable dtype coercion while allowing extra columns."""

        coerce = True
        strict = False
