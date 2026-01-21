"""Battle log parser stub."""

from __future__ import annotations

import logging

import pandas as pd

from veschov.io.BattleSectionParser import BattleSectionParser
from veschov.io.FleetSectionParser import FleetSectionParser
from veschov.io.LootSectionParser import LootSectionParser
from veschov.io.PlayerSectionParser import PlayerSectionParser

logger = logging.getLogger(__name__)


def parse_battle_log(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """
    Should return a pandas DataFrame with at least:
      - 'mitigated_apex'
      - 'total_normal'
    """
    del filename
    df, raw_df, sections = BattleSectionParser(file_bytes).parse_with_sections()
    validated_players_df = PlayerSectionParser(sections.get("players"), df).parse()
    validated_fleets_df = FleetSectionParser(sections.get("fleets")).parse()
    validated_loot_df = LootSectionParser(sections.get("rewards")).parse()
    df.attrs.update(
        {
            "players_df": validated_players_df,
            "fleets_df": validated_fleets_df,
            "loot_df": validated_loot_df,
            "raw_combat_df": raw_df,
        }
    )
    return df
