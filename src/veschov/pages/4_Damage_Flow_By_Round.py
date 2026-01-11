from __future__ import annotations

import logging

from veschov.ui.object_reports.DamageFlowByRoundReport import DamageFlowByRoundReport

logger = logging.getLogger(__name__)

import streamlit as st

st.set_page_config(page_title="STFC Reports", layout="wide")
# st.title("🖖 Damage Flow by Round")

# render_actual_damage_report()
rep = DamageFlowByRoundReport()
rep.render()
