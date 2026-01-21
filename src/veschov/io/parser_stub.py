"""Battle log parser stub."""

from __future__ import annotations

import logging

import pandas as pd

from veschov.io.BattleSectionParser import BattleSectionParser
from veschov.io.FleetSectionParser import FleetSectionParser
from veschov.io.LootSectionParser import LootSectionParser
from veschov.io.PlayerSectionParser import PlayerSectionParser
from veschov.io.StartsWhen import extract_sections

logger = logging.getLogger(__name__)


def parse_battle_log(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """
    Should return a pandas DataFrame with at least:
      - 'mitigated_apex'
      - 'total_normal'
    """
    del filename
    text = BattleSectionParser(file_bytes)._read_text(file_bytes)
    sections = extract_sections(text)
    df, raw_df = BattleSectionParser(text).parse()
    players_df = PlayerSectionParser(sections.get("players"), df).parse()
    fleets_df = FleetSectionParser(sections.get("fleets")).parse()
    loot_df = LootSectionParser(sections.get("rewards")).parse()
    df.attrs["players_df"] = players_df
    df.attrs["fleets_df"] = fleets_df
    df.attrs["loot_df"] = loot_df
    df.attrs["raw_combat_df"] = raw_df
    return df
