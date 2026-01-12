from __future__ import annotations

import logging

from veschov.ui.object_reports.DamageFlowByRoundReport import DamageFlowByRoundReport
import streamlit as st

st.set_page_config(page_title="bIQ’a’ rur QIH.  Destruction flows like a river.", layout="wide")
# st.title("🖖 Damage Flow by Round")

# render_actual_damage_report()
rep = DamageFlowByRoundReport()
rep.render()
