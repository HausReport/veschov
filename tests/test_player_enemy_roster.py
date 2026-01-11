"""Tests for attacker/target roster defaults derived from player metadata."""

from __future__ import annotations

from typing import Optional

import pandas as pd
import pytest

from tests import helpers
from veschov.io.SessionInfo import SessionInfo, ShipSpecifier
from veschov.ui.object_reports.AttackerAndTargetReport import AttackerAndTargetReport


class _TestReport(AttackerAndTargetReport):
    def get_under_title_text(self) -> Optional[str]:
        pass

    def get_log_title(self) -> str:
        pass

    def get_log_description(self) -> str:
        pass

    def get_derived_dataframes(self, df: pd.DataFrame, lens) -> Optional[list[pd.DataFrame]]:
        pass

    def display_plots(self, dfs: list[pd.DataFrame]) -> None:
        pass

    def display_tables(self, dfs: list[pd.DataFrame]) -> None:
        pass

    def get_debug_info(self, df: pd.DataFrame) -> None:
        pass

    def get_x_axis_text(self) -> Optional[str]:
        pass

    def get_y_axis_text(self) -> Optional[str]:
        pass

    def get_title_text(self) -> Optional[str]:
        pass

    def get_under_chart_text(self) -> Optional[str]:
        pass

    def get_lens_key(self) -> str:
        return "test"


CASES = [
    (
        "1.csv",
        [
            ShipSpecifier("XanOfHanoi", "ThunderDome", "BORG CUBE"),
            ShipSpecifier("V'ger Silent Enemy ▶", "", "V'ger Silent Enemy"),
        ],
    ),
    (
        "2-outpost-retal.csv",
        [
            ShipSpecifier("XanOfHanoi", "ThunderDome", "BORG CUBE"),
            ShipSpecifier("XanOfHanoi", "ThunderDome", "KOS'KARII"),
            ShipSpecifier("Assimilated Galor-Class", "", "Assimilated Galor-Class"),
        ],
    ),
    (
        "3-armada.csv",
        [
            ShipSpecifier("Popperbottom", "ThunderDome", "ENTERPRISE NX-01"),
            ShipSpecifier("NWMaverick", "ThunderDome", "SS REVENANT"),
            ShipSpecifier("chahkoh", "ThunderDome", "SS REVENANT"),
            ShipSpecifier("AmigoSniped", "ThunderDome", "SS REVENANT"),
            ShipSpecifier("XanOfHanoi", "ThunderDome", "SS REVENANT"),
            ShipSpecifier("Borg Polygon 1.2", "", "Borg Polygon 1.2"),
        ],
    ),
]


@pytest.mark.parametrize("fname, expected", CASES)
def test_player_enemy_defaults(fname: str, expected: list[ShipSpecifier]) -> None:
    combat_df = helpers.get_battle_log(fname)
    players_df = combat_df.attrs["players_df"]
    session_info = SessionInfo(combat_df)

    report = _TestReport()
    options, raw_specs = report._gather_specs(session_info)
    targets = report._default_target_from_players(players_df, options, raw_specs)

    assert targets == [expected[-1]]

    players = [spec for spec in options if spec not in targets]
    for spec in expected[:-1]:
        assert spec in players
