"""Tests for shared normalization across section parsers."""

from __future__ import annotations

import pandas as pd

from veschov.io.FleetSectionParser import FleetSectionParser
from veschov.io.LootSectionParser import LootSectionParser
from veschov.io.PlayerSectionParser import PlayerSectionParser


def test_section_parsers_trim_and_na_tokens_consistently() -> None:
    """Ensure loot/player/fleet normalization trims and handles NA tokens consistently."""
    combat_df = pd.DataFrame()
    loot_text = "Reward Name\tCount\n  Nanoprobe  \t -- "
    player_text = "Player Name\tPlayer Level\tOutcome\n  Nanoprobe  \t -- \t  Victory  "
    fleet_text = "Fleet Type\tAttack\tDefense\tHealth\n  Nanoprobe  \t -- \t — \t  100  "

    loot_df = LootSectionParser(loot_text).parse()
    players_df = PlayerSectionParser(player_text, combat_df).parse()
    fleets_df = FleetSectionParser(fleet_text).parse()

    assert loot_df.loc[0, "Reward Name"] == "Nanoprobe"
    assert pd.isna(loot_df.loc[0, "Count"])

    assert players_df.loc[0, "Player Name"] == "Nanoprobe"
    assert pd.isna(players_df.loc[0, "Player Level"])
    assert players_df.loc[0, "Outcome"] == "Victory"

    assert fleets_df.loc[0, "Fleet Type"] == "Nanoprobe"
    assert pd.isna(fleets_df.loc[0, "Attack"])
    assert pd.isna(fleets_df.loc[0, "Defense"])
    assert fleets_df.loc[0, "Health"] == "100"
