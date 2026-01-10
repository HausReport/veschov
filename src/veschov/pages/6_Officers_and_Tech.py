from __future__ import annotations

import logging

from veschov.ui.officers_and_tech_report import render_officers_and_tech_report

logger = logging.getLogger(__name__)

import streamlit as st

st.set_page_config(page_title="STFC Reports", layout="wide")
# st.title("🖖 Officers & Tech Procs")

render_officers_and_tech_report()
