from __future__ import annotations
from veschov.ui.object_reports.DamageFlowByBattleReport import DamageFlowByBattleReport
import streamlit as st

st.set_page_config(page_title="SuvtaHghach bIQ’a’ rur.  Violence flows like a river.", layout="wide")
# st.title("🖖 Damage Flow by Battle")
report = DamageFlowByBattleReport()
report.render()
