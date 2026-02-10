from __future__ import annotations

import streamlit as st

from veschov.ui.object_reports.AppliedDamageHeatmapsByAttackerReport import (
    AppliedDamageHeatmapsByAttackerReport,
)

st.set_page_config(page_title="DoS ghaj nuH.  Every weapon has its rhythm.", layout="wide")

report = AppliedDamageHeatmapsByAttackerReport()
report.render()
