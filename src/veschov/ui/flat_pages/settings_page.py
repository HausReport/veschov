"""Streamlit UI for settings."""

from __future__ import annotations

import streamlit as st

from veschov.ui.components.number_format import (
    NUMBER_FORMAT_DEFAULT,
    NUMBER_FORMAT_HELP,
    NUMBER_FORMAT_OPTIONS,
    NUMBER_FORMAT_SESSION_KEY,
)
from veschov.ui.components.theme import (
    THEME_DEFAULT,
    THEME_HELP,
    THEME_OPTIONS,
    THEME_SESSION_KEY,
)


def render_settings_report() -> None:
    """Render the settings report."""
    st.title("Settings")

    theme_options = list(THEME_OPTIONS)
    current_theme = st.session_state.get(THEME_SESSION_KEY, THEME_DEFAULT)
    if current_theme not in theme_options:
        current_theme = THEME_DEFAULT
    theme_index = theme_options.index(current_theme)
    theme_selection = st.selectbox(
        "Color Theme",
        theme_options,
        index=theme_index,
        help=THEME_HELP,
    )
    st.session_state[THEME_SESSION_KEY] = theme_selection

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
