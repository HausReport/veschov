from __future__ import annotations

import logging

from veschov.ui.apex_barrier_poc import render_apex_barrier_poc

logger = logging.getLogger(__name__)

import streamlit as st

st.set_page_config(page_title="STFC Reports", layout="wide")
# st.title("🖖 Apex Barrier Analysis")

render_apex_barrier_poc()
