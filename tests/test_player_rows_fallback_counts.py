"""Tests for inferred player rows from combat metadata."""

from __future__ import annotations

import pytest

from tests import helpers

CASES = [
    ("1.csv", 1),
    ("2-outpost-retal.csv", 1),
    ("3-armada.csv", 5),
]


@pytest.mark.parametrize("fname, players", CASES)
def test_player_rows_have_one_entry_per_player(fname: str, players: int) -> None:
    session = helpers.get_session_info(fname)
    df = session.combat_df
    players_df = df.attrs.get("players_df")
    players_rows = players_df.iloc[:-1] if len(players_df) > 1 else players_df.iloc[0:0]
    npc_row = players_df.iloc[-1:]

    assert not players_rows.empty and len(players_rows) == players
    assert (not npc_row.empty and len(npc_row) == 1)
