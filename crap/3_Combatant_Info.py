from __future__ import annotations

import streamlit as st

from crap.CombatantInfoReport import render_player_info_report

st.set_page_config(page_title="jagh yISov. yISov’egh.  Know the enemy.  Know thyself.", layout="wide")

render_player_info_report()
