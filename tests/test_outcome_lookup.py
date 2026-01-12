"""Tests for outcome inference in session info."""

from __future__ import annotations

import pytest

from tests import helpers
from veschov.io.SessionInfo import SessionInfo


def _outcome_for_name(
    session_info: SessionInfo,
    outcome_lookup: dict[tuple[str, str, str], object],
    name: str,
) -> str:
    players_df = session_info.players_df
    rows = players_df.loc[players_df["Player Name"] == name]
    assert not rows.empty
    row = rows.iloc[0]
    ship = session_info.normalize_text(row.get("Ship Name"))
    alliance = session_info._resolve_player_alliance(row)
    key = session_info.normalize_spec_key(name, alliance, ship)
    assert key in outcome_lookup
    return session_info.normalize_outcome(outcome_lookup.get(key))


@pytest.mark.parametrize(
    ("log_name", "expected"),
    [
        (
            "1.csv",
            {
                "XanOfHanoi": "DEFEAT",
                "V'ger Silent Enemy ▶": "VICTORY",
            },
        ),
        (
            "2-outpost-retal.csv",
            {
                "XanOfHanoi": "VICTORY",
                "Assimilated Galor-Class": "DEFEAT",
            },
        ),
        (
            "3-armada.csv",
            {
                "Popperbottom": "VICTORY",
                "Borg Polygon 1.2": "DEFEAT",
            },
        ),
        (
            "4-partial.csv",
            {
                "XanOfHanoi": "PARTIAL",
                "Assimilated Prohibitor-class": "PARTIAL",
            },
        ),
    ],
)
def test_outcome_lookup_infers_results(
    log_name: str,
    expected: dict[str, str],
) -> None:
    session_info = helpers.get_session_info(log_name)
    outcome_lookup = session_info.build_outcome_lookup()
    for name, expected_outcome in expected.items():
        assert (
            _outcome_for_name(session_info, outcome_lookup, name) == expected_outcome
        )
