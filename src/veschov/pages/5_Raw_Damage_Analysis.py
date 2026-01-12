from __future__ import annotations

import streamlit as st
from veschov.ui.object_reports.RawDamageReport import RawDamageReport

st.set_page_config(page_title="bat’lethlIj HoS Sov, jagh may’be’ yoD Qop-pa’.  Know the blade's power before the strike", layout="wide")
# st.title("Raw Damage by Type")

report = RawDamageReport()
report.render()
