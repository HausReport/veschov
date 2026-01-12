from __future__ import annotations

from veschov.ui.object_reports.CombatantInfoReport import render_player_info_report
import streamlit as st


st.set_page_config(page_title="STFC Reports", layout="wide")

render_player_info_report()
