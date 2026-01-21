from __future__ import annotations

import logging

import pandas as pd

from veschov.io.AbstractSectionParser import AbstractSectionParser
from veschov.io.StartsWhen import SECTION_HEADERS, section_to_dataframe

logger = logging.getLogger(__name__)

LOOT_NUMERIC_COLUMNS = ("Count",)


class LootSectionParser(AbstractSectionParser):
    """Parse the rewards (loot) section of a battle log."""

    section_key = "rewards"
    header_prefix = SECTION_HEADERS["rewards"]

    def parse_section(self, text: str, sections: dict[str, str]) -> pd.DataFrame:
        """Parse the rewards section and normalize it."""
        section_text = sections.get(self.section_key)
        df = section_to_dataframe(section_text, self.header_prefix)
        df = self._normalize_dataframe(df)
        return self._coerce_numeric_columns(df, LOOT_NUMERIC_COLUMNS)
