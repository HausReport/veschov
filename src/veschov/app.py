# src/tests/app.py
from __future__ import annotations

import streamlit as st
from st_pages import add_page_title, get_nav_from_toml

st.set_page_config(page_title="veSchov: Illuminate the Battle.", layout="wide")

# Routing must happen after common frame setup
nav = get_nav_from_toml()  # reads .streamlit/pages.toml
pg = st.navigation(nav)
add_page_title(pg)
pg.run()

# Common sidebar UI that should appear on EVERY page
# st.sidebar.header("Filters")
# date_range = st.sidebar.date_input(
#   "Date range",
#    value=(),
#    help="Leave empty for all time",
#    key="x_sidebar_date_range",
# )
# st.session_state["date_range"] = date_range

# Prevent accidental fallthrough
st.stop()
