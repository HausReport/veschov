from __future__ import annotations

import base64
import json
import logging
import lzma
import zlib
from pathlib import Path
from typing import Callable, Iterable, TypedDict, cast

import streamlit as st

from veschov.io.SessionInfo import SessionInfo, ShipSpecifier

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
    build_name: str
    ship_name: str
    notes: str
    suggestions: list[str]

BRIDGE_SLOTS = 3
EVEN_SLOTS = 10
STATE_VERSION = 3
LZMA_PREFIX = "x:"

ASSETS_DIR = Path(__file__).resolve().parents[3] / "assets"


def load_officer_names(path: Path) -> list[str]:
    """Load officer names from the JSON asset and return sorted text values."""
    records = cast(list[OfficerNameRecord], json.loads(path.read_text(encoding="utf-8")))
    names = [record["text"] for record in records]
    return sorted(names)


OFFICER_NAMES = load_officer_names(ASSETS_DIR / "officer_names.json")
DEFAULT_SUGGESTIONS = [] # OFFICER_NAMES[:8]


def init_state() -> None:
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


def deserialize_state(encoded: str) -> BuilderState | None:
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
    st.session_state.build_name = restored["build_name"]
    st.session_state.ship_name = restored["ship_name"]
    st.session_state.notes = restored["notes"]
    st.session_state.suggestions = restored["suggestions"]
    st.session_state.state_restored = True


def pick(value: str) -> None:
    st.session_state.holding = value


def all_placed_values() -> set[str]:
    placed: set[str] = set()
    for value in st.session_state.bridge_slots + st.session_state.even_slots:
        if value is not None:
            placed.add(value)
    return placed


def remove_value_everywhere(value: str) -> None:
    for key in ("bridge_slots", "even_slots"):
        slots = [v if v != value else None for v in st.session_state[key]]
        st.session_state[key] = slots


def add_suggestion(value: str) -> None:
    if value not in st.session_state.suggestions:
        st.session_state.suggestions = st.session_state.suggestions + [value]


def remove_suggestion(value: str) -> None:
    if value in st.session_state.suggestions:
        st.session_state.suggestions = [
            suggestion for suggestion in st.session_state.suggestions if suggestion != value
        ]


def slot_click(row_key: str, idx: int) -> None:
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

st.title("Share or Save Your Build")

# --- Holding text ---
holding = st.session_state.holding
if holding is None:
    st.markdown("**Click an officer to crew.**")
else:
    st.markdown(f"**Click a position for `{holding}`, or click another officer.**")

st.divider()

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

    st.divider()

    # --- EVENS (10 slots) ---
    st.subheader("Below-Deck Officers", text_alignment="center")

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

submitted = False
with st.form("state-share"):
    st.caption("Save the current layout into the URL for sharing.")
    submitted = st.form_submit_button("Save state to URL")

if submitted:
    st.query_params["state"] = serialize_state()

st.caption("Tip: click a filled slot with nothing held to clear it (suggestions will reappear).")
