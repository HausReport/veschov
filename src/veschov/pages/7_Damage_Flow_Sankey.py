from __future__ import annotations

import streamlit as st

from veschov.ui.object_reports.DamageFlowByBattleReport import DamageFlowByBattleReport

st.set_page_config(page_title="SuvtaHghach bIQ’a’ rur.  Violence flows like a river.", layout="wide")
# st.title("🖖 Damage Flow by Battle")
report = DamageFlowByBattleReport()
report.render()
