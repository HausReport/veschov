"""Streamlit UI for settings."""

from __future__ import annotations

import streamlit as st

from veschov.ui.components.number_format import (
    NUMBER_FORMAT_DEFAULT,
    NUMBER_FORMAT_HELP,
    NUMBER_FORMAT_OPTIONS,
    NUMBER_FORMAT_SESSION_KEY,
)


def render_settings_report() -> None:
    """Render the settings report."""
    st.title("Settings")

    options = list(NUMBER_FORMAT_OPTIONS)
    current_value = st.session_state.get(NUMBER_FORMAT_SESSION_KEY, NUMBER_FORMAT_DEFAULT)
    if current_value not in options:
        current_value = NUMBER_FORMAT_DEFAULT
    selected_index = options.index(current_value)
    selection = st.selectbox(
        "Large Number Display",
        options,
        index=selected_index,
        help=NUMBER_FORMAT_HELP,
    )
    st.session_state[NUMBER_FORMAT_SESSION_KEY] = selection
