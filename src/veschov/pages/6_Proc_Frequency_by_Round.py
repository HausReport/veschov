from __future__ import annotations

import streamlit as st

from veschov.ui.object_reports.ProcFrequencyByRoundReport import ProcFrequencyByRoundReport

st.set_page_config(page_title="Proc Frequency by Round", layout="wide")

report = ProcFrequencyByRoundReport()
report.render()
