from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

import streamlit as st

from veschov.ui.raw_damage_report import render_raw_damage_report


st.set_page_config(page_title="STFC Reports", layout="wide")
# st.title("Raw Damage by Type")

render_raw_damage_report()
