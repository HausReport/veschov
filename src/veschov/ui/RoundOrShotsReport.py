from veschov.ui.AbstractReport import AbstractReport
import streamlit as st
from veschov.ui.view_by import VIEW_BY_OPTIONS, select_view_by, prepare_round_view


class RoundOrShotsReport(AbstractReport):
    VIEW_BY_DEFAULT = "Round"
    VIEW_BY_KEY = "actual_damage_view_by"

    def __init__(self):
        self.view_by = self._resolve_view_by()

    def _resolve_view_by(self) -> str:
        view_by = st.session_state.get(self.VIEW_BY_KEY)
        if view_by not in VIEW_BY_OPTIONS:
            view_by = self.VIEW_BY_DEFAULT
            st.session_state[self.VIEW_BY_KEY] = view_by
        return view_by

    def display_under_chart(self) -> None:
        utt = self.get_under_chart_text()
        if utt is not None:
            st.markdown(utt, unsafe_allow_html=True)
        self._resolve_view_by()
        default_index = VIEW_BY_OPTIONS.index(self.VIEW_BY_DEFAULT)
        select_view_by(self.VIEW_BY_KEY, default_index=default_index)