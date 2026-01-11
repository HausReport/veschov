from __future__ import annotations
import streamlit as st

from veschov.ui.object_reports.CritHitReport import CritHitReport

st.set_page_config(page_title="STFC Reports", layout="wide")
# st.title("Hits per Round")

report = CritHitReport()
report.render()
