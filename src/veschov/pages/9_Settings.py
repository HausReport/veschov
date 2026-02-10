from __future__ import annotations

import streamlit as st

from veschov.ui.flat_pages.settings_page import render_settings_report

st.set_page_config(page_title="mu’mey. janmey.  Settings.", layout="wide")
render_settings_report()
