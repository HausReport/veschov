from __future__ import annotations

import streamlit as st

from veschov.ui.object_reports.ObservedMitigationReport import ObservedMitigationReport

st.set_page_config(
    page_title="Observed Mitigation (Normal Lane)",
    layout="wide",
)

report = ObservedMitigationReport()
report.render()
