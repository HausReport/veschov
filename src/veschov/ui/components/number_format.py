"""Shared header helpers for combat-log-based reports."""

from __future__ import annotations

import logging

import humanize
import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)

# DEFAULT_UPLOAD_TYPES: Iterable[str] = ("tsv", "csv", "txt")

NUMBER_FORMAT_SESSION_KEY = "number_format"
NUMBER_FORMAT_OPTIONS: tuple[str, ...] = ("Human", "Exact")
NUMBER_FORMAT_DEFAULT = "Human"
NUMBER_FORMAT_HELP = "Choose how numbers over 999,999 are formatted."


def get_number_format() -> str:
    """Return the configured large-number formatting preference."""
    stored_value = st.session_state.get(NUMBER_FORMAT_SESSION_KEY, NUMBER_FORMAT_DEFAULT)
    if stored_value not in NUMBER_FORMAT_OPTIONS:
        stored_value = NUMBER_FORMAT_DEFAULT
    st.session_state[NUMBER_FORMAT_SESSION_KEY] = stored_value
    return stored_value


def format_number(
    value: object,
    *,
    number_format: str,
    humanize_format: str = "%.1f",
    null_display: str = "—",
) -> str:
    """Format a value using the configured large-number preference."""
    if pd.isna(value):
        return null_display
    if isinstance(value, bool):
        return str(value)
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.notna(numeric):
        if abs(numeric) >= 1_000_000 and number_format == "Human":
            return humanize.intword(numeric, format=humanize_format)
        if float(numeric).is_integer():
            return f"{int(numeric):,}"
        return f"{numeric:,}"
    text = str(value).strip()
    return text or null_display
