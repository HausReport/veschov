from typing import cast

import streamlit as st

from veschov.builder.CopyUrlButtons import BRIDGE_SLOTS, EVEN_SLOTS, DEFAULT_SUGGESTIONS


def _validate_slots(values: object, expected_len: int) -> list[str | None] | None:
    """Validate a list of slots with optional string values."""
    if not isinstance(values, list):
        return None
    if len(values) != expected_len:
        return None
    for value in values:
        if value is None:
            continue
        if not isinstance(value, str):
            return None
    return [cast(str | None, value) for value in values]

def init_state() -> None:
    """Initialize Streamlit session state with builder defaults."""
    st.session_state.setdefault("holding", None)
    st.session_state.setdefault("bridge_slots", [None] * BRIDGE_SLOTS)
    st.session_state.setdefault("even_slots", [None] * EVEN_SLOTS)
    st.session_state.setdefault("manual_pick", "—")
    st.session_state.setdefault("build_name", "")
    st.session_state.setdefault("ship_name", "")
    st.session_state.setdefault("notes", "")
    st.session_state.setdefault("suggestions", DEFAULT_SUGGESTIONS.copy())
    st.session_state.setdefault("state_restored", False)
    st.session_state.setdefault("auto_seeded", False)