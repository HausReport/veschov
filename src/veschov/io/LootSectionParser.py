from __future__ import annotations

import logging

import pandas as pd

from veschov.io.AbstractSectionParser import AbstractSectionParser
from veschov.io.StartsWhen import SECTION_HEADERS, section_to_dataframe
from veschov.io.schemas import LootSchema, validate_dataframe

logger = logging.getLogger(__name__)


class LootSectionParser(AbstractSectionParser):
    """Parse the rewards section of a combat log into a normalized dataframe."""

    def __init__(self, section_text: str | None) -> None:
        self.section_text = section_text

    def parse(self, *, soft: bool = False) -> pd.DataFrame:
        """Return a normalized dataframe for rewards/loot entries."""
        if not self.section_text:
            logger.debug("Rewards section missing or empty; returning empty loot dataframe.")
        loot_df = section_to_dataframe(self.section_text, SECTION_HEADERS["rewards"])
        loot_df = self._normalize_dataframe(loot_df)
        return validate_dataframe(
            loot_df,
            LootSchema,
            soft=soft,
            context="loot section",
        )
