from __future__ import annotations

from veschov.ui.flat_pages.player_info_report import render_player_info_report
import streamlit as st


st.set_page_config(page_title="STFC Reports", layout="wide")

render_player_info_report()
