from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

import streamlit as st

from veschov.ui.crit_hit_report import render_crit_hit_report


st.set_page_config(page_title="STFC Reports", layout="wide")
# st.title("Hits per Round")

render_crit_hit_report()
