
from __future__ import annotations

import base64
import json
import logging
import lzma
import urllib.parse
import zlib
from typing import cast

import streamlit as st
from streamlit_copy_to_clipboard_button import copy_to_clipboard

from veschov.builder.BuilderState import BuilderState
from veschov.builder.Constants import PUBLIC_BASE_URL, STATE_VERSION, EVEN_SLOTS, BRIDGE_SLOTS, \
    DEFAULT_SUGGESTIONS, LZMA_PREFIX
from veschov.builder.Serialization import _validate_slots

logger = logging.getLogger(__name__)



def copy_url_buttons():
    #
    # Save/ share UI
    #
    submitted = False
    share_url = None
    discord_md = None
    reddit_md = None

    with st.form("state-share"):
        c1, c2, c3, c4 = st.columns(4)
        # st.caption("Save the current layout into the URL for sharing.")
        with c1:
            submitted = st.form_submit_button("💾 Save/Share Build")

        if submitted:
            state = serialize_state()
            st.query_params["state"] = state

            qs = urllib.parse.urlencode({"state": state})
            share_url = f"{PUBLIC_BASE_URL}?{qs}"

            discord_md = f"[🔗 Open this build](<{share_url}>)"  # <...> often suppresses preview
            reddit_md = f"[Open this build]({share_url})"

        # st.divider()
        # st.subheader("Share")

        # If the user arrived via an already-shared link, still compute outputs
        state = _get_state_query_param()
        if (share_url is None) and state:
            qs = urllib.parse.urlencode({"state": state})
            share_url = f"{PUBLIC_BASE_URL}?{qs}"
            discord_md = f"[🔗 Open this build](<{share_url}>)"
            reddit_md = f"[Open this build]({share_url})"

        if not share_url:
            st.caption("Click **Save state to URL** to generate share links.")
        else:
            pass
            # st.code(share_url)

        with c2:
            copy_to_clipboard(
                share_url,
                label="Copy long link to clipboard",  # Optional
                # show_text=True,
                label_after_copy="Copied!"  # Optional
            )
        with c3:
            copy_to_clipboard(
                discord_md,
                label="💬 Copy for Discord",
                label_after_copy="Copied!"  # Optional
            )
        with c4:
            copy_to_clipboard(
                reddit_md,
                label="👽 Copy for Reddit markdown",
                label_after_copy="Copied!"  # Optional
            )

        # with st.expander("Show formatted text"):
        # st.code(discord_md, language="markdown")
        # st.code(reddit_md, language="markdown")

def _coerce_state(payload: object) -> BuilderState | None:
    """Validate and normalize a decoded state payload."""
    if not isinstance(payload, dict):
        logger.warning("State payload is not a dict.")
        return None

    raw_version = payload.get("v", STATE_VERSION)
    if not isinstance(raw_version, int):
        logger.warning("State payload version is invalid: %s", raw_version)
        return None

    holding = payload.get("holding")
    if holding is not None and not isinstance(holding, str):
        logger.warning("State payload holding is invalid: %s", holding)
        return None

    bridge_slots = _validate_slots(payload.get("bridge_slots"), BRIDGE_SLOTS)
    if bridge_slots is None:
        logger.warning("State payload bridge slots are invalid.")
        return None

    even_slots = _validate_slots(payload.get("even_slots"), EVEN_SLOTS)
    if even_slots is None:
        logger.warning("State payload even slots are invalid.")
        return None

    manual_pick = payload.get("manual_pick")
    if not isinstance(manual_pick, str):
        logger.warning("State payload manual pick is invalid: %s", manual_pick)
        return None

    build_name = payload.get("build_name", "")
    if not isinstance(build_name, str):
        logger.warning("State payload build name is invalid: %s", build_name)
        return None

    ship_name = payload.get("ship_name", "")
    if not isinstance(ship_name, str):
        logger.warning("State payload ship name is invalid: %s", ship_name)
        return None

    notes = payload.get("notes", "")
    if not isinstance(notes, str):
        logger.warning("State payload notes are invalid: %s", notes)
        return None

    suggestions = payload.get("suggestions", DEFAULT_SUGGESTIONS)
    if not isinstance(suggestions, list) or any(not isinstance(value, str) for value in suggestions):
        logger.warning("State payload suggestions are invalid.")
        return None

    return BuilderState(
        v=raw_version,
        holding=cast(str | None, holding),
        bridge_slots=bridge_slots,
        even_slots=even_slots,
        manual_pick=manual_pick,
        build_name=build_name,
        ship_name=ship_name,
        notes=notes,
        suggestions=list(suggestions),
    )


def serialize_state() -> str:
    """Encode the current builder state into a shareable URL payload."""
    payload: BuilderState = {
        "v": STATE_VERSION,
        "holding": cast(str | None, st.session_state.holding),
        "bridge_slots": cast(list[str | None], st.session_state.bridge_slots),
        "even_slots": cast(list[str | None], st.session_state.even_slots),
        "manual_pick": cast(str, st.session_state.manual_pick),
        "build_name": cast(str, st.session_state.build_name),
        "ship_name": cast(str, st.session_state.ship_name),
        "notes": cast(str, st.session_state.notes),
        "suggestions": cast(list[str], st.session_state.suggestions),
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = lzma.compress(encoded, preset=9)
    return f"{LZMA_PREFIX}{base64.urlsafe_b64encode(compressed).decode('ascii')}"

def _pad_base64(value: str) -> str:
    """Pad base64-encoded strings to valid lengths."""
    return value + ("=" * (-len(value) % 4))

def deserialize_state(encoded: str) -> BuilderState | None:
    """Decode and validate a shareable URL payload."""
    try:
        codec = "zlib"
        raw = encoded
        if encoded.startswith(LZMA_PREFIX):
            codec = "lzma"
            raw = encoded[len(LZMA_PREFIX) :]

        padded = _pad_base64(raw)
        compressed = base64.urlsafe_b64decode(padded.encode("ascii"))
        if codec == "lzma":
            decoded = lzma.decompress(compressed).decode("utf-8")
        else:
            decoded = zlib.decompress(compressed).decode("utf-8")
        payload = json.loads(decoded)
    except (ValueError, zlib.error) as exc:
        logger.warning("Failed to decode state payload: %s", exc)
        return None
    except lzma.LZMAError as exc:
        logger.warning("Failed to LZMA decompress state payload: %s", exc)
        return None
    except OSError as exc:
        logger.warning("Failed to decompress state payload: %s", exc)
        return None

    return _coerce_state(payload)


def _get_state_query_param() -> str | None:
    """Return the state query param, normalizing list vs string values."""
    value = st.query_params.get("state")
    if value is None:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return value


def restore_state_from_query() -> None:
    """Restore session state from the URL, if present."""
    if st.session_state.state_restored:
        return

    raw_state = _get_state_query_param()
    if not raw_state:
        st.session_state.state_restored = True
        return

    restored = deserialize_state(raw_state)
    if restored is None:
        logger.warning("State query parameter could not be restored; using defaults.")
        st.session_state.state_restored = True
        return

    st.session_state.holding = restored["holding"]
    st.session_state.bridge_slots = restored["bridge_slots"]
    st.session_state.even_slots = restored["even_slots"]
    st.session_state.manual_pick = restored["manual_pick"]
    st.session_state.build_name = restored["build_name"]
    st.session_state.ship_name = restored["ship_name"]
    st.session_state.notes = restored["notes"]
    st.session_state.suggestions = restored["suggestions"]
    st.session_state.state_restored = True