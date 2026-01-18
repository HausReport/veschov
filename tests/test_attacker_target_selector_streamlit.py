"""Streamlit tests for the attacker/target selector widget."""

from __future__ import annotations

from typing import Optional, Sequence

import pandas as pd

from streamlit.testing.v1 import AppTest

from tests import helpers
from veschov.io.SessionInfo import SessionInfo
from veschov.io.ShipSpecifier import ShipSpecifier
from veschov.ui.chirality import Lens
from veschov.ui.object_reports.AttackerAndTargetReport import (
    AttackerAndTargetReport,
    SerializedShipSpec,
)
from veschov.ui.object_reports.rosters.AttackerTargetStateManager import (
    AttackerTargetStateManager,
    deserialize_spec_dict,
)


class _StreamlitTestReport(AttackerAndTargetReport):
    """Minimal report for exercising the attacker/target selector."""

    def render(self, session_info: SessionInfo, players_df: pd.DataFrame) -> None:
        """Render only the attacker/target selector for testing."""
        self.render_actor_target_selector(session_info, players_df)

    def get_under_title_text(self) -> Optional[str]:
        """Return optional under-title text for the report."""
        return None

    def get_log_title(self) -> str:
        """Return the sidebar log title for this report."""
        return "Test Log"

    def get_log_description(self) -> str:
        """Return the sidebar log description for this report."""
        return "Test-only report for attacker/target selection."

    def get_derived_dataframes(
        self,
        df: pd.DataFrame,
        lens: Lens | None,
    ) -> Optional[list[pd.DataFrame]]:
        """Return derived dataframes for the report lifecycle."""
        _ = lens
        return [df]

    def display_plots(self, dfs: list[pd.DataFrame]) -> None:
        """No-op plot rendering for tests."""
        _ = dfs

    def display_tables(self, dfs: list[pd.DataFrame]) -> None:
        """No-op table rendering for tests."""
        _ = dfs

    def render_debug_info(self, dfs: list[pd.DataFrame]) -> None:
        """No-op debug output for tests."""
        _ = dfs

    def get_x_axis_text(self) -> Optional[str]:
        """Return optional x-axis text for charts."""
        return None

    def get_y_axis_text(self) -> Optional[str]:
        """Return optional y-axis text for charts."""
        return None

    def get_title_text(self) -> Optional[str]:
        """Return the report title text."""
        return None

    def get_under_chart_text(self) -> Optional[str]:
        """Return optional under-chart text."""
        return None

    def get_lens_key(self) -> str:
        return "test"


def _resolve_default_specs(
    report: AttackerAndTargetReport,
    options: Sequence[ShipSpecifier],
    players_df: pd.DataFrame,
) -> tuple[list[SerializedShipSpec], list[SerializedShipSpec]]:
    """Return serialized default attacker/target specs for the selector."""
    target_fallback = report._default_target_from_players(players_df, options)
    if not target_fallback:
        target_fallback = list(options[-1:])
    attacker_fallback = [spec for spec in options if spec not in target_fallback]
    if not attacker_fallback:
        attacker_fallback = list(options[:1])
    default_attacker_specs = [report._serialize_spec(spec) for spec in attacker_fallback]
    default_target_specs = [report._serialize_spec(spec) for spec in target_fallback]
    return default_attacker_specs, default_target_specs


def _get_checkbox(app: AppTest, key: str) -> object:
    """Return the checkbox widget matching the requested key."""
    matches = [checkbox for checkbox in app.checkbox if checkbox.key == key]
    assert len(matches) == 1
    return matches[0]


def _get_button(app: AppTest, key: str) -> object:
    """Return the button widget matching the requested key."""
    matches = [button for button in app.button if button.key == key]
    assert len(matches) == 1
    return matches[0]


def _get_selected_specs_from_state(app: AppTest) -> tuple[list[SerializedShipSpec], list[SerializedShipSpec]]:
    """Return selected attacker/target specs from stored attacker/target state."""
    state = app.session_state[AttackerTargetStateManager.STATE_KEY]
    selected = state["selected"]
    attackers = [deserialize_spec_dict(entry) for entry in selected["attacker"]]
    targets = [deserialize_spec_dict(entry) for entry in selected["target"]]
    return attackers, targets


def test_attacker_target_selector_toggle_updates_state() -> None:
    """Toggle attacker/target selections and verify session state updates."""
    combat_df = helpers.get_battle_log("1.csv")
    players_df = combat_df.attrs["players_df"]
    session_info = SessionInfo(combat_df)
    report = _StreamlitTestReport()
    options = report._normalize_specs(session_info)
    expected_attackers, expected_targets = _resolve_default_specs(report, options, players_df)

    def render() -> None:
        report.render(session_info, players_df)

    app = AppTest.from_function(render)
    app.run()

    selected_attackers, selected_targets = _get_selected_specs_from_state(app)
    assert set(selected_attackers) == set(expected_attackers)
    assert set(selected_targets) == set(expected_targets)

    attacker_key, _ = AttackerTargetStateManager.build_checkbox_keys(
        key_prefix="attacker_include",
        spec_key=expected_attackers[0],
    )
    target_key, _ = AttackerTargetStateManager.build_checkbox_keys(
        key_prefix="target_include",
        spec_key=expected_targets[0],
    )

    attacker_checkbox = _get_checkbox(app, attacker_key)
    attacker_checkbox.set_value(False)
    app.run()
    expected_attackers_after_uncheck = [
        spec for spec in expected_attackers if spec != expected_attackers[0]
    ]
    selected_attackers, _ = _get_selected_specs_from_state(app)
    assert set(selected_attackers) == set(expected_attackers_after_uncheck)

    attacker_checkbox = _get_checkbox(app, attacker_key)
    attacker_checkbox.set_value(True)
    app.run()
    selected_attackers, _ = _get_selected_specs_from_state(app)
    assert set(selected_attackers) == set(expected_attackers)

    target_checkbox = _get_checkbox(app, target_key)
    target_checkbox.set_value(False)
    app.run()
    expected_targets_after_uncheck = [
        spec for spec in expected_targets if spec != expected_targets[0]
    ]
    _, selected_targets = _get_selected_specs_from_state(app)
    assert set(selected_targets) == set(expected_targets_after_uncheck)


def test_attacker_target_swap_updates_checkboxes() -> None:
    """Swap attacker/target selections and verify checkbox state."""
    combat_df = helpers.get_battle_log("1.csv")
    players_df = combat_df.attrs["players_df"]
    session_info = SessionInfo(combat_df)
    report = _StreamlitTestReport()
    options = report._normalize_specs(session_info)
    expected_attackers, expected_targets = _resolve_default_specs(report, options, players_df)

    def render() -> None:
        report = _StreamlitTestReport()
        report.render(session_info, players_df)

    app = AppTest.from_function(render)
    app.run()

    swap_button = _get_button(app, "swap_attacker_target_specs")
    swap_button.click()
    app.run()

    selected_attackers, selected_targets = _get_selected_specs_from_state(app)
    assert set(selected_attackers) == set(expected_targets)
    assert set(selected_targets) == set(expected_attackers)

    swapped_attacker_key, _ = AttackerTargetStateManager.build_checkbox_keys(
        key_prefix="attacker_include",
        spec_key=expected_targets[0],
    )
    swapped_target_key, _ = AttackerTargetStateManager.build_checkbox_keys(
        key_prefix="target_include",
        spec_key=expected_attackers[0],
    )
    swapped_attacker_checkbox = _get_checkbox(app, swapped_attacker_key)
    swapped_target_checkbox = _get_checkbox(app, swapped_target_key)

    assert swapped_attacker_checkbox.value is True
    assert swapped_target_checkbox.value is True
