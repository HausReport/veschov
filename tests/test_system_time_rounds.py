"""Tests for system/time/rounds metadata extraction."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from tests import helpers
from veschov.ui.chirality import Lens
from veschov.ui.object_reports.AttackerAndTargetReport import AttackerAndTargetReport


class _HeaderReport(AttackerAndTargetReport):
    """Concrete report stub for testing header helpers."""

    def get_under_title_text(self) -> str | None:
        return None

    def get_under_chart_text(self) -> str | None:
        return None

    def get_log_title(self) -> str:
        return ""

    def get_log_description(self) -> str:
        return ""

    def get_derived_dataframes(
        self,
        df: pd.DataFrame,
        lens: Lens | None,
    ) -> list[pd.DataFrame] | None:
        return None

    def display_plots(self, dfs: list[pd.DataFrame]) -> None:
        return None

    def display_tables(self, dfs: list[pd.DataFrame]) -> None:
        return None

    def render_debug_info(self, dfs: list[pd.DataFrame]) -> None:
        return None

    def get_x_axis_text(self) -> str | None:
        return None

    def get_y_axis_text(self) -> str | None:
        return None

    def get_title_text(self) -> str | None:
        return None

    def get_lens_key(self) -> str:
        return ""


def _expected_context_line(location: str, timestamp: str) -> str:
    parsed = pd.to_datetime(timestamp, errors="coerce")
    if pd.isna(parsed):
        raise AssertionError("Expected timestamp should parse during tests.")
    parsed_dt = parsed.to_pydatetime()
    today_year = datetime.now().year
    date_part = f"{parsed_dt:%a} {parsed_dt.day} {parsed_dt:%b}"
    if parsed_dt.year != today_year:
        date_part = f"{date_part} [{parsed_dt:%Y}]"
    time_part = f"{parsed_dt:%H:%M}"
    location_text = location.strip()
    if location_text and "system" not in location_text.lower():
        location_text = f"{location_text} System"
    return f"{location_text} on {date_part} at {time_part}"


@pytest.mark.parametrize(
    ("filename", "expected_lines"),
    [
        (
            "4-partial.csv",
            [
                _expected_context_line("Corialsis", "1/12/2026 1:18:58 PM"),
                "Battle Rounds: 1",
            ],
        ),
        (
            "5-kren.csv",
            [
                _expected_context_line("Kren", "2/1/2026 5:12:34 PM"),
                "Battle Rounds: 6",
            ],
        ),
        (
            "2-outpost-retal.csv",
            [
                "Battle Rounds: 11",
            ],
        ),
    ],
)
def test_get_system_time_and_rounds(
    filename: str,
    expected_lines: list[str],
) -> None:
    combat_df = helpers.get_battle_log(filename)
    players_df = combat_df.attrs["players_df"]

    report = _HeaderReport()
    lines = report._get_system_time_and_rounds(players_df, combat_df)

    assert lines == expected_lines
