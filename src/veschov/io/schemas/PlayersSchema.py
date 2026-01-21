"""Pandera schema for player metadata dataframes."""


from typing import ClassVar

import pandera as pa
from pandera.typing import Series

COLUMN_ORDER: ClassVar[list[str]] = [
    "Player Name",
    "Player Level",
    "Outcome",
    "Ship Name",
    "Alliance",
    "Location",
    "Timestamp",
]

class PlayersSchema(pa.DataFrameModel):
    """Schema definition for player metadata rows."""

    player_name: Series[str] = pa.Field(alias="Player Name", nullable=True)
    player_level: Series[int] = pa.Field(alias="Player Level", nullable=True)
    outcome: Series[str] = pa.Field(alias="Outcome", nullable=True)

    ship_name: Series[str] = pa.Field(alias="Ship Name", nullable=True)
    location: Series[str] = pa.Field(alias="Location", nullable=True)
    timestamp: Series[str] = pa.Field(alias="Timestamp", nullable=True)
    alliance: Series[str] = pa.Field(alias="Alliance", nullable=True)



    class Config:
        """Enable dtype coercion while allowing extra columns."""

        coerce = True
        strict = False
