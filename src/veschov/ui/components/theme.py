"""Theme utilities for Streamlit UI."""

from __future__ import annotations

import logging

import streamlit as st

logger = logging.getLogger(__name__)

THEME_SESSION_KEY = "ui_theme"
THEME_OPTIONS = ("Dark", "Light")
THEME_DEFAULT = "Dark"
THEME_HELP = "Choose the color theme used across all pages."


def get_theme_selection() -> str:
    """Return the current theme selection, defaulting when needed."""
    stored_value = st.session_state.get(THEME_SESSION_KEY, THEME_DEFAULT)
    if stored_value not in THEME_OPTIONS:
        logger.warning("Unknown theme selection '%s'; resetting to default.", stored_value)
        stored_value = THEME_DEFAULT
    st.session_state[THEME_SESSION_KEY] = stored_value
    return stored_value


def apply_theme() -> None:
    """Apply the selected theme styles to the Streamlit app."""
    selected_theme = get_theme_selection()
    if selected_theme == "Light":
        palette = {
            "bg": "#f4f6f9",
            "text": "#1d1f23",
            "card": "#ffffff",
            "border": "#c7cbd1",
            "link": "#1b5ea8",
        }
    else:
        palette = {
            "bg": "#0f1116",
            "text": "#e6e7ea",
            "card": "#1c1f26",
            "border": "#2b2f38",
            "link": "#8bb4ff",
        }

    st.markdown(
        f"""
<style>
:root {{
  --veschov-bg: {palette['bg']};
  --veschov-text: {palette['text']};
  --veschov-card: {palette['card']};
  --veschov-border: {palette['border']};
  --veschov-link: {palette['link']};
}}

.stApp {{
  background-color: var(--veschov-bg);
  color: var(--veschov-text);
}}

.stApp a {{
  color: var(--veschov-link);
}}

.stApp [data-testid="stHeader"],
.stApp [data-testid="stToolbar"],
.stApp [data-testid="stSidebar"] {{
  background-color: var(--veschov-bg);
}}

.stApp .stMarkdown,
.stApp .stText,
.stApp label,
.stApp span {{
  color: var(--veschov-text);
}}

.stApp input,
.stApp textarea,
.stApp select,
.stApp [data-testid="stSelectbox"] div {{
  background-color: var(--veschov-card);
  color: var(--veschov-text);
  border-color: var(--veschov-border);
}}

.stApp [data-testid="stMarkdownContainer"] code {{
  background-color: var(--veschov-card);
  color: var(--veschov-text);
}}
</style>
""",
        unsafe_allow_html=True,
    )
