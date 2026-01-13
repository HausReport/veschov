from __future__ import annotations

import base64
import json
import logging
import zlib
from pathlib import Path
from typing import Callable, TypedDict, cast

import streamlit as st

logger = logging.getLogger(__name__)


class OfficerNameRecord(TypedDict):
    id: int
    key: str
    text: str

class BuilderState(TypedDict):
    v: int
    holding: str | None
    bridge_slots: list[str | None]
    even_slots: list[str | None]
    manual_pick: str

BRIDGE_SLOTS = 3
EVEN_SLOTS = 10
STATE_VERSION = 1

# Suggested chips: label -> value placed when clicked
SUGGESTED = [
    ("2 is even",  "2"),
    ("5 is prime", "5"),
    ("7 is prime", "7"),
]

ASSETS_DIR = Path(__file__).resolve().parents[3] / "assets"


def load_officer_names(path: Path) -> list[str]:
    """Load officer names from the JSON asset and return sorted text values."""
    records = cast(list[OfficerNameRecord], json.loads(path.read_text(encoding="utf-8")))
    names = [record["text"] for record in records]
    return sorted(names)


OFFICER_NAMES = load_officer_names(ASSETS_DIR / "officer_names.json")


def init_state() -> None:
    st.session_state.setdefault("holding", None)
    st.session_state.setdefault("bridge_slots", [None] * BRIDGE_SLOTS)
    st.session_state.setdefault("even_slots", [None] * EVEN_SLOTS)
    st.session_state.setdefault("manual_pick", "—")
    st.session_state.setdefault("state_restored", False)


def _pad_base64(value: str) -> str:
    return value + ("=" * (-len(value) % 4))


def _validate_slots(values: object, expected_len: int) -> list[str | None] | None:
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


def _coerce_state(payload: object) -> BuilderState | None:
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

    return BuilderState(
        v=raw_version,
        holding=cast(str | None, holding),
        bridge_slots=bridge_slots,
        even_slots=even_slots,
        manual_pick=manual_pick,
    )


def serialize_state() -> str:
    payload: BuilderState = {
        "v": STATE_VERSION,
        "holding": cast(str | None, st.session_state.holding),
        "bridge_slots": cast(list[str | None], st.session_state.bridge_slots),
        "even_slots": cast(list[str | None], st.session_state.even_slots),
        "manual_pick": cast(str, st.session_state.manual_pick),
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(encoded, level=9)
    return base64.urlsafe_b64encode(compressed).decode("ascii")


def deserialize_state(encoded: str) -> BuilderState | None:
    try:
        padded = _pad_base64(encoded)
        compressed = base64.urlsafe_b64decode(padded.encode("ascii"))
        decoded = zlib.decompress(compressed).decode("utf-8")
        payload = json.loads(decoded)
    except (ValueError, zlib.error) as exc:
        logger.warning("Failed to decode state payload: %s", exc)
        return None
    except OSError as exc:
        logger.warning("Failed to decompress state payload: %s", exc)
        return None

    return _coerce_state(payload)


def _get_state_query_param() -> str | None:
    value = st.query_params.get("state")
    if value is None:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return value


def restore_state_from_query() -> None:
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
    st.session_state.state_restored = True


def pick(value: str) -> None:
    st.session_state.holding = value


def all_placed_values() -> set[str]:
    return set(st.session_state.bridge_slots) | set(st.session_state.even_slots)


def remove_value_everywhere(value: str) -> None:
    for key in ("bridge_slots", "even_slots"):
        slots = st.session_state[key]
        for i, v in enumerate(slots):
            if v == value:
                slots[i] = None


def slot_click(row_key: str, idx: int) -> None:
    holding = st.session_state.holding
    row = st.session_state[row_key]

    if holding is None:
        if row[idx] is not None:
            row[idx] = None
        return

    # Dedupe, place, then drop.
    remove_value_everywhere(holding)
    row[idx] = holding
    st.session_state.holding = None


def centered_row(num_slots: int, render_slot_button: Callable[[st.delta_generator.DeltaGenerator, int], None]) -> None:
    """
    Center a row of num_slots using EVEN_SLOTS as the max width reference.
    """
    max_width = EVEN_SLOTS
    left_pad = max((max_width - num_slots) // 2, 0)
    right_pad = max_width - num_slots - left_pad

    cols = st.columns([1] * left_pad + [2] * num_slots + [1] * right_pad)
    start = left_pad
    for i in range(num_slots):
        render_slot_button(cols[start + i], i)


def render_wrapped_chips(
    pairs: list[tuple[str, str]],
    *,
    per_row: int = 6,
    key_prefix: str = "chip",
) -> None:
    """
    Render chips horizontally by chunking into rows.
    pairs: list of (label, value)
    """
    if not pairs:
        st.caption("—")
        return

    for r in range(0, len(pairs), per_row):
        row = pairs[r : r + per_row]
        cols = st.columns(len(row))
        for i, (label, value) in enumerate(row):
            cols[i].button(label, key=f"{key_prefix}_{r+i}", on_click=pick, args=(value,))


def on_manual_pick_change() -> None:
    val = st.session_state.manual_pick
    if val != "—":
        pick(val)


init_state()
restore_state_from_query()

st.title("POC: Click chip/dropdown → click slot")

if "battle_df" in st.session_state:
    pass

# --- Holding text ---
holding = st.session_state.holding
if holding is None:
    st.markdown("**Click an officer to crew.**")
else:
    st.markdown(f"**Click a position for `{holding}`, or click another officer.**")

st.divider()

# --- BRIDGE with labels above slots ---
st.subheader("Bridge", text_alignment="center")

def render_bridge_label(col: st.delta_generator.DeltaGenerator, i: int) -> None:
    labels = ["#1", "Capt.", "#2"]
    container = col.container()
    container.markdown(
        f"<div style='text-align:center; font-size:0.85rem; opacity:0.8;'>{labels[i]}</div>",
        unsafe_allow_html=True,
    )

def render_bridge_slot(col: st.delta_generator.DeltaGenerator, i: int) -> None:
    val = st.session_state.bridge_slots[i]
    label = val if val is not None else "—"
    if col.button(label, key=f"bridge_{i}"):
        slot_click("bridge_slots", i)

centered_row(BRIDGE_SLOTS, render_bridge_label)
centered_row(BRIDGE_SLOTS, render_bridge_slot)

st.divider()

# --- EVENS (10 slots) ---
st.subheader("Below-Deck Officers", text_alignment="center")

def render_below_decks_slot(col: st.delta_generator.DeltaGenerator, i: int) -> None:
    val = st.session_state.even_slots[i]
    label = val if val is not None else "—"
    if col.button(label, key=f"even_{i}"):
        slot_click("even_slots", i)

centered_row(EVEN_SLOTS, render_below_decks_slot)

st.divider()

# --- Bottom: 50/50 Manual Pick + Suggestions ---
left, right = st.columns(2)

with left:
    st.subheader("Choose Officers (type to search)")
    st.selectbox(
        "Pick an officer name",
        options=["—"] + OFFICER_NAMES,
        key="manual_pick",
        on_change=on_manual_pick_change,
        help="Selecting a name puts it in Holding. Then click a slot to place.",
    )

with right:
    st.subheader("Suggestions")

    placed = all_placed_values()
    # filter suggestions: hide any whose value is already placed
    filtered = [(lbl, val) for (lbl, val) in SUGGESTED if val not in placed]

    st.caption("Click a suggestion to hold it; it disappears once placed.")
    render_wrapped_chips(filtered, per_row=4, key_prefix="sugg")

submitted = False
with st.form("state-share"):
    st.caption("Save the current layout into the URL for sharing.")
    submitted = st.form_submit_button("Save state to URL")

if submitted:
    st.query_params["state"] = serialize_state()

st.caption("Tip: click a filled slot with nothing held to clear it (suggestions will reappear).")
