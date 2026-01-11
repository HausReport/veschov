from __future__ import annotations
from veschov.ui.flat_pages.settings_report import render_settings_report
import streamlit as st

st.set_page_config(page_title="STFC Reports", layout="wide")
render_settings_report()
