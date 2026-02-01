"""Streamlit UI for proc summary reporting."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from veschov.ui.object_reports.AbstractReport import AbstractReport
from veschov.ui.object_reports.ProcReportBase import ProcReportBase, build_proc_summary


class ProcSummaryForBattleReport(ProcReportBase):
    """Render the proc summary for battle report."""
    lens_key = f"proc_freq_battle_{AbstractReport.key_suffix}"

    def display_tables(self, dfs: list[pd.DataFrame]) -> None:
        display_df = dfs[0]
        selection = self._get_proc_selection(display_df)
        if selection is None:
            return
        _, owner_filter = selection

        summary_df = build_proc_summary(
            display_df,
            self.include_forbidden_tech,
            owner_filter,
        )
        if summary_df.empty:
            st.info("No officer/tech proc rows found for this battle.")
            return

        st.subheader("Proc Summary for Battle")
        st.caption("Summary table aggregates total fires, active rounds, and first activation.")
        st.dataframe(summary_df, width="stretch")
