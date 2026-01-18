from __future__ import annotations

import logging

import streamlit as st

logger = logging.getLogger(__name__)


def load_widget_state(
        *,
        temp_key: str,
        persistent_key: str,
        default: bool,
        force_default: bool = False,
) -> bool:
    """Load a widget value into a temporary key from persistent session storage."""
    if force_default or persistent_key not in st.session_state:
        st.session_state[persistent_key] = default
        logger.debug(
            "Widget persistent key seeded (key=%s, default=%s, force=%s).",
            persistent_key,
            default,
            force_default,
        )
    st.session_state[temp_key] = st.session_state[persistent_key]
    return bool(st.session_state[temp_key])


def store_widget_state(*, temp_key: str, persistent_key: str) -> None:
    """Persist a widget value from its temporary key."""
    if temp_key not in st.session_state:
        logger.debug(
            "Widget temp key missing during persist (temp_key=%s, persistent_key=%s).",
            temp_key,
            persistent_key,
        )
    st.session_state[persistent_key] = bool(st.session_state.get(temp_key, False))
    logger.debug(
        "Widget state stored (temp_key=%s, persistent_key=%s, value=%s).",
        temp_key,
        persistent_key,
        st.session_state[persistent_key],
    )
