from __future__ import annotations

import streamlit as st

from veschov.ui.object_reports.AbstractReport import AbstractReport
from veschov.ui.object_reports.AttackerAndTargetReport import AttackerAndTargetReport
from veschov.ui.view_by import VIEW_BY_OPTIONS, select_view_by


class RoundOrShotsReport(AttackerAndTargetReport):
    """Report base that adds a round/shots view selector to the chart header.

    Subclasses use ``self.view_by`` to decide whether the x-axis represents
    combat rounds or number of shots.
    """
    VIEW_BY_DEFAULT = "Round"
    VIEW_BY_KEY = "actual_damage_view_by"
    lens_key = f"round_shot_rept_{AbstractReport.key_suffix}"

    def __init__(self) -> None:
        """Initialize the report with the current view-by selection."""
        self.view_by = self._resolve_view_by()

    def _resolve_view_by(self) -> str:
        """Resolve the view-by choice from session state or defaults."""
        view_by = st.session_state.get(self.VIEW_BY_KEY)
        if view_by not in VIEW_BY_OPTIONS:
            view_by = self.VIEW_BY_DEFAULT
        return view_by

    def display_under_chart(self) -> None:
        """Render the view selector alongside the standard under-chart text."""
        utt = self.under_chart_text
        self._resolve_view_by()
        default_index = VIEW_BY_OPTIONS.index(self.VIEW_BY_DEFAULT)
        text_column, selector_column = st.columns([4, 1])
        with selector_column:
            select_view_by(self.VIEW_BY_KEY, default_index=default_index)
        if utt is not None:
            with text_column:
                st.markdown(utt, unsafe_allow_html=True)
