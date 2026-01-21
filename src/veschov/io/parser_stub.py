"""Battle log parser stub."""

from __future__ import annotations

import logging
from typing import IO

import pandas as pd

from veschov.io.BattleSectionParser import BattleSectionParser
from veschov.io.FleetSectionParser import FleetSectionParser
from veschov.io.LootSectionParser import LootSectionParser
from veschov.io.PlayerSectionParser import PlayerSectionParser
from veschov.io.StartsWhen import extract_sections

logger = logging.getLogger(__name__)


def _read_text(file_bytes: bytes | str | IO[object]) -> str:
    if isinstance(file_bytes, bytes):
        return file_bytes.decode("utf-8", errors="replace")
    if isinstance(file_bytes, str):
        return file_bytes
    if hasattr(file_bytes, "read"):
        content = file_bytes.read()
        if isinstance(content, bytes):
            return content.decode("utf-8", errors="replace")
        return str(content)
    return str(file_bytes)


def parse_battle_log(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """
    Should return a pandas DataFrame with at least:
      - 'mitigated_apex'
      - 'total_normal'
    """
    text = _read_text(file_bytes)
    sections = extract_sections(text)

    context: dict[str, object] = {"filename": filename}

    battle_parser = BattleSectionParser()
    combat_df = battle_parser.parse_section(text, sections)
    context["combat_df"] = combat_df
    if battle_parser.raw_df is not None:
        context["raw_combat_df"] = battle_parser.raw_df

    players_parser = PlayerSectionParser()
    players_df = players_parser.parse_section(text, sections)
    players_df = players_parser.post_process(players_df, context)

    fleets_parser = FleetSectionParser()
    fleets_df = fleets_parser.parse_section(text, sections)
    fleets_df = fleets_parser.post_process(fleets_df, context)

    loot_parser = LootSectionParser()
    loot_df = loot_parser.parse_section(text, sections)
    loot_df = loot_parser.post_process(loot_df, context)

    combat_df.attrs["players_df"] = players_df
    combat_df.attrs["fleets_df"] = fleets_df
    combat_df.attrs["loot_df"] = loot_df
    combat_df.attrs["raw_combat_df"] = context.get("raw_combat_df")

    return combat_df
