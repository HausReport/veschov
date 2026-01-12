from __future__ import annotations
import streamlit as st

from veschov.ui.object_reports.CritHitReport import CritHitReport

st.set_page_config(page_title="wa’ HIv tIn law’ Hoch HIvmey puj puS.  One mighty strike is worth a thousand taps.", layout="wide")
# st.title("Hits per Round")

report = CritHitReport()
report.render()
