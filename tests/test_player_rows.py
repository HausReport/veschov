"""Tests for inferred player rows in battle log metadata."""

from __future__ import annotations

import pandas as pd

from tests import helpers


def _player_names(players_df: pd.DataFrame) -> set[str]:
    return set(players_df["Player Name"].dropna().astype(str))


def test_infers_player_rows_from_combat_targets() -> None:
    combat_df = helpers.get_battle_log("2-outpost-retal.csv")
    players_df = combat_df.attrs["players_df"]

    assert len(players_df) > 1
    assert "XanOfHanoi" in _player_names(players_df)
    assert players_df.iloc[-1]["Player Name"] == "Assimilated Galor-Class"


def test_infers_player_rows_for_armada_logs() -> None:
    combat_df = helpers.get_battle_log("3-armada.csv")
    players_df = combat_df.attrs["players_df"]

    assert len(players_df) > 1
    assert "AmigoSniped" in _player_names(players_df)
    assert players_df.iloc[-1]["Player Name"] == "Borg Polygon 1.2"


def test_preserves_multi_row_player_metadata() -> None:
    combat_df = helpers.get_battle_log("1.csv")
    players_df = combat_df.attrs["players_df"]

    assert players_df.shape[0] == 2
    assert _player_names(players_df) == {"XanOfHanoi", "V'ger Silent Enemy ▶"}
