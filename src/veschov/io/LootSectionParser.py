from __future__ import annotations

import logging

import pandas as pd

from veschov.io.StartsWhen import NA_TOKENS, SECTION_HEADERS, section_to_dataframe

logger = logging.getLogger(__name__)


class LootSectionParser:
    """Parse the rewards section of a combat log into a normalized dataframe."""

    def __init__(self, section_text: str | None) -> None:
        self.section_text = section_text

    def parse(self) -> pd.DataFrame:
        """Return a normalized dataframe for rewards/loot entries."""
        if not self.section_text:
            logger.debug("Rewards section missing or empty; returning empty loot dataframe.")
        loot_df = section_to_dataframe(self.section_text, SECTION_HEADERS["rewards"])
        return self._normalize_dataframe(loot_df)

    @staticmethod
    def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        cleaned = df.copy()
        for column in cleaned.columns:
            if pd.api.types.is_object_dtype(cleaned[column]) or pd.api.types.is_string_dtype(
                cleaned[column]
            ):
                cleaned[column] = cleaned[column].astype("string").str.strip()
        cleaned = cleaned.replace(list(NA_TOKENS), pd.NA)
        return cleaned
