from __future__ import annotations

import streamlit as st

from veschov.ui.object_reports.ObservedShieldMitigationReport import ObservedShieldMitigationReport

st.set_page_config(
    page_title="Observed Shield Mitigation",
    layout="wide",
)

report = ObservedShieldMitigationReport()
report.render()
