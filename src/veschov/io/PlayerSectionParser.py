"""Parse the player metadata section of a battle log."""

from __future__ import annotations

import logging

import pandas as pd

from veschov.io.AbstractSectionParser import AbstractSectionParser
from veschov.io.StartsWhen import SECTION_HEADERS, section_to_dataframe
from veschov.io.schemas import PlayersSchema, validate_dataframe

logger = logging.getLogger(__name__)


class PlayerSectionParser(AbstractSectionParser):
    """Parse and normalize the player metadata section of a battle log."""

    def __init__(self, section_text: str | None, combat_df: pd.DataFrame) -> None:
        self.section_text = section_text
        self.combat_df = combat_df

    def parse(self, *, soft: bool = False) -> pd.DataFrame:
        """Return a normalized players dataframe, with inferred entries as needed."""
        players_df = section_to_dataframe(self.section_text, SECTION_HEADERS["players"])
        players_df = self._normalize_dataframe(players_df)
        players_df = self._augment_players_df(players_df, self.combat_df)
        return validate_dataframe(
            players_df,
            PlayersSchema,
            soft=soft,
            context="player section",
        )
