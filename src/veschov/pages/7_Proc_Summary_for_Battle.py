from __future__ import annotations

import streamlit as st

from veschov.ui.object_reports.ProcSummaryForBattleReport import ProcSummaryForBattleReport

st.set_page_config(page_title="Proc Summary for Battle", layout="wide")

report = ProcSummaryForBattleReport()
report.render()
