from __future__ import annotations

import streamlit as st

from veschov.ui.object_reports.CritMultiplierTrendsReport import CritMultiplierTrendsReport

st.set_page_config(page_title="SuD tlhIngan ghot chaq bejlu’.  The wise watch trends before strikes.", layout="wide")

report = CritMultiplierTrendsReport()
report.render()
