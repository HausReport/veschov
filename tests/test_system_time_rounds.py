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
            ['Corialsis System', 'Mon 12 Jan at 13:18', 'Battle Rounds: 1']
        ),
        (
            "5-kren.csv",
            ['Kyana System', 'Tue 25 Nov 2025 at 19:20', 'Battle Rounds: 5']
        ),
        (
            "2-outpost-retal.csv",
            ['Draxyl System', 'Wed 31 Dec 2025 at 20:02', 'Battle Rounds: 11']
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

    print(f"Expected: {expected_lines}")
    print(f"Got: {lines}")
    assert lines == expected_lines
