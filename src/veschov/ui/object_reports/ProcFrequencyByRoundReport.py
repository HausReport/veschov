"""Streamlit UI for proc frequency by round."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from veschov.ui.object_reports.AbstractReport import AbstractReport
from veschov.ui.object_reports.ProcReportBase import ProcReportBase, build_proc_matrix, style_heatmap


class ProcFrequencyByRoundReport(ProcReportBase):
    """Render the proc frequency by round report."""
    lens_key = f"proc_freq_round_{AbstractReport.key_suffix}"

    def display_tables(self, dfs: list[pd.DataFrame]) -> None:
        display_df = dfs[0]
        selection = self._get_proc_selection(display_df)
        if selection is None:
            return
        _, owner_filter = selection

        matrix_df = build_proc_matrix(
            display_df,
            self.include_forbidden_tech,
            show_totals=True,
            show_distinct=False,
            owner_filter=owner_filter,
        )
        if matrix_df.empty:
            st.info("No officer/tech proc rows found for this battle.")
            return

        st.subheader("Proc Frequency by Round")
        st.caption("Heatmap counts how often each officer/tech ability fired per round.")
        st.dataframe(style_heatmap(matrix_df, heat_cap=5), width="stretch")
