from __future__ import annotations

from veschov.ui.object_reports.AppliedDamageHeatmapsByAttackerReport import (
    AppliedDamageHeatmapsByAttackerReport,
)
import streamlit as st

st.set_page_config(page_title="STFC Reports", layout="wide")

report = AppliedDamageHeatmapsByAttackerReport()
report.render()
