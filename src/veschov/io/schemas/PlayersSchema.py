"""Pandera schema for player metadata dataframes."""

from __future__ import annotations

from typing import ClassVar

import pandera as pa
from pandera.typing import Series


class PlayersSchema(pa.DataFrameModel):
    """Schema definition for player metadata rows."""

    player_name: Series[str] = pa.Field(alias="Player Name", nullable=True)
    player_level: Series[float] = pa.Field(alias="Player Level", nullable=True)
    outcome: Series[str] = pa.Field(alias="Outcome", nullable=True)

    ship_name: Series[str] = pa.Field(alias="Ship Name", nullable=True, required=False)
    location: Series[str] = pa.Field(alias="Location", nullable=True, required=False)
    timestamp: Series[str] = pa.Field(alias="Timestamp", nullable=True, required=False)
    alliance: Series[str] = pa.Field(alias="Alliance", nullable=True, required=False)

    COLUMN_ORDER: ClassVar[list[str]] = [
        "Player Name",
        "Player Level",
        "Outcome",
        "Ship Name",
        "Alliance",
        "Location",
        "Timestamp",
    ]

    class Config:
        """Enable dtype coercion while allowing extra columns."""

        coerce = True
        strict = False
