"""Streamlit UI for the home page."""

from __future__ import annotations
import streamlit as st


def render_home_report() -> None:
    """Render the home page report content."""
    st.caption("Welcome to STFC Reports. Use the left navigation to explore sessions and combat logs.")

    st.subheader("Status")
    st.success("✅ App loaded successfully.")
