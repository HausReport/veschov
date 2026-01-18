"""Streamlit tests for combatant info selection persistence."""

from __future__ import annotations

import streamlit as st
from streamlit.testing.v1 import AppTest

from tests import helpers
from veschov.io.SessionInfo import SessionInfo
from veschov.ui.object_reports.ApexBarrierReport import ApexBarrierReport
from veschov.ui.object_reports.CombatantInfoReport import CombatantInfoReport


def _render_report_page() -> None:
    """Render a report page based on session state to test selection persistence."""
    combat_df = helpers.get_battle_log("3-armada.csv")
    st.session_state.setdefault("battle_df", combat_df)
    st.session_state.setdefault("players_df", combat_df.attrs.get("players_df"))
    st.session_state.setdefault("fleets_df", combat_df.attrs.get("fleets_df"))
    st.session_state.setdefault("session_info", SessionInfo(combat_df))

    page = st.session_state.get("page", "apex")
    if page == "apex":
        report = ApexBarrierReport()
        report.render_header(combat_df)
        return

    report = CombatantInfoReport()
    lens = report.render_header(combat_df)
    dfs = report.get_derived_dataframes(combat_df, lens)
    if dfs is None:
        st.session_state["selected_specs_count"] = 0
        st.session_state["selected_cards_count"] = 0
        return
    st.session_state["selected_specs_count"] = len(report._selected_specs)
    st.session_state["selected_cards_count"] = len(report._selected_cards)


def test_combatant_info_uses_persisted_selection() -> None:
    """Ensure combatant info keeps selections when switching pages."""
    app = AppTest.from_function(_render_report_page)

    app.session_state["page"] = "apex"
    app.run()
    assert "attacker_target_state" in app.session_state

    app.session_state["page"] = "combatant"
    app.run()

    selected_specs = app.session_state.get("selected_specs_count", 0)
    selected_cards = app.session_state.get("selected_cards_count", 0)
    assert selected_specs > 0
    assert selected_cards == selected_specs
