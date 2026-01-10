from __future__ import annotations

import streamlit as st

from veschov.ui.settings_report import render_settings_report


st.set_page_config(page_title="STFC Reports", layout="wide")

render_settings_report()
