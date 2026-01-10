from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

import streamlit as st

from veschov.ui.damage_flow_sankey_report import render_damage_flow_sankey_report


st.set_page_config(page_title="STFC Reports", layout="wide")
# st.title("🖖 Damage Flow by Battle")
render_damage_flow_sankey_report()
