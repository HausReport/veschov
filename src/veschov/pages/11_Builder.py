from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable, Iterable, TypedDict, cast

import streamlit as st

from veschov.builder.Constants import EVEN_SLOTS, BRIDGE_SLOTS
from veschov.builder.CopyUrlButtons import _get_state_query_param, restore_state_from_query, copy_url_buttons
from veschov.builder.Serialization import init_state
from veschov.io.SessionInfo import SessionInfo
from veschov.io.ShipSpecifier import ShipSpecifier

logger = logging.getLogger(__name__)

class OfficerNameRecord(TypedDict):
    id: int
    key: str
    text: str

ASSETS_DIR = Path(__file__).resolve().parents[3] / "assets"


def load_officer_names(path: Path) -> list[str]:
    """Load officer names from the JSON asset and return sorted text values."""
    records = cast(list[OfficerNameRecord], json.loads(path.read_text(encoding="utf-8")))
    names = [record["text"] for record in records]
    return sorted(names)


OFFICER_NAMES = load_officer_names(ASSETS_DIR / "officer_names.json")

def pick(value: str) -> None:
    """Store the selected officer in the holding slot."""
    st.session_state.holding = value


def all_placed_values() -> set[str]:
    """Return a set of all officers currently placed in slots."""
    placed: set[str] = set()
    for value in st.session_state.bridge_slots + st.session_state.even_slots:
        if value is not None:
            placed.add(value)
    return placed


def remove_value_everywhere(value: str) -> None:
    """Remove a value from all slot lists."""
    for key in ("bridge_slots", "even_slots"):
        slots = [v if v != value else None for v in st.session_state[key]]
        st.session_state[key] = slots


def add_suggestion(value: str) -> None:
    """Append a value to suggestions if it is not already present."""
    if value not in st.session_state.suggestions:
        st.session_state.suggestions = st.session_state.suggestions + [value]


def remove_suggestion(value: str) -> None:
    """Remove a value from suggestions if it exists."""
    if value in st.session_state.suggestions:
        st.session_state.suggestions = [
            suggestion for suggestion in st.session_state.suggestions if suggestion != value
        ]


def slot_click(row_key: str, idx: int) -> None:
    """Handle clicking a slot, placing or removing officers."""
    holding = st.session_state.holding
    row = list(st.session_state[row_key])

    if holding is None:
        if row[idx] is not None:
            removed = row[idx]
            row[idx] = None
            st.session_state[row_key] = row
            add_suggestion(removed)
        return

    # Dedupe, place, then drop.
    remove_value_everywhere(holding)
    row[idx] = holding
    st.session_state[row_key] = row
    st.session_state.holding = None
    st.session_state.manual_pick = "—"
    remove_suggestion(holding)


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
    """Move the manual pick value into holding when changed."""
    val = st.session_state.manual_pick
    if val != "—":
        pick(val)


def _normalize_names(values: Iterable[str]) -> list[str]:
    """Return sorted, deduplicated officer names from a raw iterable."""
    normalized = {value.strip() for value in values if value and value.strip()}
    return sorted(normalized)


def _pick_single_name(values: Iterable[str], label: str) -> str | None:
    """Return a deterministic officer name from a set, logging if multiple."""
    names = _normalize_names(values)
    if not names:
        return None
    if len(names) > 1:
        logger.warning("Multiple %s names found (%s); using %s.", label, names, names[0])
    return names[0]


def _player_specs(session_info: SessionInfo) -> list[ShipSpecifier]:
    """Return sorted player ship specs inferred from session info."""
    specs = [
        spec
        for spec in session_info.get_every_ship()
        if SessionInfo.normalize_text(spec.alliance)
    ]
    return sorted(specs, key=lambda spec: (spec.name or "", spec.ship or "", spec.alliance or ""))


def _set_suggestions(values: Iterable[str]) -> None:
    """Set suggestions to the provided officer names."""
    st.session_state.suggestions = _normalize_names(values)


def _auto_seed_from_session() -> None:
    """Seed bridge/below-deck slots from session info when no state URL exists."""
    if st.session_state.auto_seeded:
        return

    if _get_state_query_param():
        return

    session_info = st.session_state.get("session_info")
    if not isinstance(session_info, SessionInfo):
        return

    player_specs = _player_specs(session_info)
    if len(player_specs) == 1:
        spec = player_specs[0]
        if not spec.name or not spec.ship:
            logger.warning("Player ship spec missing name or ship; cannot auto-seed builder.")
            st.session_state.auto_seeded = True
            return

        bridge_slots = list(st.session_state.bridge_slots)
        bridge_updated = False

        captain = _pick_single_name(
            session_info.get_captain_name(spec.name, spec.ship),
            "captain",
        )
        if captain:
            bridge_slots[1] = captain
            bridge_updated = True

        first_officer = _pick_single_name(
            session_info.get_1st_officer_name(spec.name, spec.ship),
            "first officer",
        )
        if first_officer:
            bridge_slots[0] = first_officer
            bridge_updated = True

        second_officer = _pick_single_name(
            session_info.get_2nd_officer_name(spec.name, spec.ship),
            "second officer",
        )
        if second_officer:
            bridge_slots[2] = second_officer
            bridge_updated = True

        if bridge_updated:
            st.session_state.bridge_slots = bridge_slots
            below_deck = _normalize_names(
                session_info.get_below_deck_officers(spec.name, spec.ship)
            )
            even_slots = list(st.session_state.even_slots)
            for index, officer in enumerate(below_deck):
                if index >= len(even_slots):
                    break
                even_slots[index] = officer
            st.session_state.even_slots = even_slots
        else:
            _set_suggestions(session_info.all_officer_names(spec.name, spec.ship))
    elif len(player_specs) > 1:
        combined_officers: set[str] = set()
        for spec in player_specs:
            if not spec.name or not spec.ship:
                logger.warning("Player spec missing name or ship; skipping %s.", spec)
                continue
            combined_officers.update(session_info.all_officer_names(spec.name, spec.ship))
        _set_suggestions(combined_officers)

    st.session_state.auto_seeded = True


init_state()
restore_state_from_query()
_auto_seed_from_session()

st.title("Builder")

# --- Holding text ---
holding = st.session_state.holding
if holding is None:
    st.markdown("**Click an officer to crew.**")
else:
    st.markdown(f"**Click a position for `{holding}`, or click another officer.**")


# Above columns
# st.divider()
copy_url_buttons()

crew_col, notes_col = st.columns([3, 2])

with crew_col:
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
        col.button(
            label,
            key=f"bridge_{i}",
            on_click=slot_click,
            args=("bridge_slots", i),
        )

    centered_row(BRIDGE_SLOTS, render_bridge_label)
    centered_row(BRIDGE_SLOTS, render_bridge_slot)

    # st.divider()

    # --- EVENS (10 slots) ---
    st.subheader("Below-Deck", text_alignment="center")

    def render_below_decks_slot(col: st.delta_generator.DeltaGenerator, i: int) -> None:
        val = st.session_state.even_slots[i]
        label = val if val is not None else "—"
        col.button(
            label,
            key=f"even_{i}",
            on_click=slot_click,
            args=("even_slots", i),
        )

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
        filtered = [
            (value, value)
            for value in st.session_state.suggestions
            if value not in placed
        ]

        st.caption("Click a suggestion to hold it; it disappears once placed.")
        render_wrapped_chips(filtered, per_row=4, key_prefix="sugg")

with notes_col:
    st.text_input("Build Name", key="build_name")
    st.text_input("Ship Name", key="ship_name")
    st.subheader("Notes")
    st.text_area(
        "Notes",
        key="notes",
        height=260,
        help="Freeform notes for this crew layout.",
    )

st.caption("Tip: click a filled slot with nothing held to clear it (suggestions will reappear).")
