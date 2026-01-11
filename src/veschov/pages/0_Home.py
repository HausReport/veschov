from __future__ import annotations

import streamlit as st

from veschov.ui.flat_pages.home_report import render_home_report

st.set_page_config(page_title="STFC Reports", layout="wide")
# st.title("🏠 Home")

render_home_report()
