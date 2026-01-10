from __future__ import annotations

import logging

from veschov.ui.player_info_report import render_player_info_report

logger = logging.getLogger(__name__)

import streamlit as st

st.set_page_config(page_title="STFC Reports", layout="wide")

render_player_info_report()
