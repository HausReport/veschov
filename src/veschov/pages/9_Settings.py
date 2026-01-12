from __future__ import annotations
from veschov.ui.flat_pages.settings_page import render_settings_report
import streamlit as st

st.set_page_config(page_title="mu’mey. janmey.  Settings.", layout="wide")
render_settings_report()
