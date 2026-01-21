"""Pandera schema for loot/rewards dataframes."""


from typing import ClassVar

import pandera as pa
from pandera.typing import Series

COLUMN_ORDER: ClassVar[list[str]] = [
    "Reward Name",
    "Count",
]


class LootSchema(pa.DataFrameModel):
    """Schema definition for rewards entries."""

    reward_name: Series[str] = pa.Field(alias="Reward Name", nullable=True)
    count: Series[float] = pa.Field(alias="Count", nullable=True)


    class Config:
        """Enable dtype coercion while allowing extra columns."""

        coerce = True
        strict = False
