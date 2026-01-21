"""Parse the fleet metadata section of a battle log."""

from __future__ import annotations

import logging

import pandas as pd

from veschov.io.AbstractSectionParser import AbstractSectionParser
from veschov.io.StartsWhen import SECTION_HEADERS, section_to_dataframe

logger = logging.getLogger(__name__)


class FleetSectionParser(AbstractSectionParser):
    """Parse and normalize the fleet metadata section of a battle log."""

    FLEET_COLUMN_RENAMES = {
        "Buff applied": "buff_applied",
        "Debuff applied": "debuff_applied",
    }
    FLEET_BOOLEAN_COLUMNS = ("buff_applied", "debuff_applied")

    def __init__(self, section_text: str | None) -> None:
        self.section_text = section_text

    def parse(self) -> pd.DataFrame:
        """Return a normalized fleets dataframe."""
        fleets_df = section_to_dataframe(self.section_text, SECTION_HEADERS["fleets"])
        fleets_df = self._normalize_dataframe(fleets_df)
        fleets_df = fleets_df.rename(columns=self.FLEET_COLUMN_RENAMES, inplace=False)
        return self._coerce_yes_no_columns(fleets_df, self.FLEET_BOOLEAN_COLUMNS)
