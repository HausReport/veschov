from __future__ import annotations

import logging

import pandas as pd

from veschov.io.AbstractSectionParser import AbstractSectionParser
from veschov.io.StartsWhen import SECTION_HEADERS, section_to_dataframe

logger = logging.getLogger(__name__)

FLEET_COLUMN_RENAMES = {
    "Buff applied": "buff_applied",
    "Debuff applied": "debuff_applied",
}

FLEET_BOOLEAN_COLUMNS = ("buff_applied", "debuff_applied")


class FleetSectionParser(AbstractSectionParser):
    """Parse and normalize the fleets section of a battle log."""

    section_key = "fleets"
    header_prefix = SECTION_HEADERS["fleets"]

    def parse_section(self, text: str, sections: dict[str, str]) -> pd.DataFrame:
        """Parse the fleets section and normalize it."""
        section_text = sections.get(self.section_key)
        df = section_to_dataframe(section_text, self.header_prefix)
        df = self._normalize_dataframe(df)
        df = df.rename(columns=FLEET_COLUMN_RENAMES, inplace=False)
        return self._coerce_yes_no_columns(df, FLEET_BOOLEAN_COLUMNS)
