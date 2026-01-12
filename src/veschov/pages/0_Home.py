
"""Streamlit UI for the home page."""

from __future__ import annotations

from pathlib import Path

import streamlit as st


def render_home_report() -> None:
    """Render the home page report content."""
    st.set_page_config(page_title="STFC Reports", layout="wide")
    st.caption("Welcome to STFC Reports. Use the left navigation to explore sessions and combat logs.")

    st.image("assets/warrior.png")

    # st.subheader("Status")
ROOT = Path(__file__).resolve().parent
img_path = (ROOT / "assets" / "warrior.png" )
st.image(img_path)
#/ "avatars" / "klingonish.png")
#st.image(str(img_path))