# streamlit_app.py
import streamlit as st

BRIDGE_SLOTS = 3
EVEN_SLOTS = 10

# Suggested chips: label -> value placed when clicked
SUGGESTED = [
    ("2 is even",  "2"),
    ("5 is prime", "5"),
    ("7 is prime", "7"),
]

# Manual pick: long-ish names to prove search/select feels natural
OFFICERS = [
    "Alexander F. Johnson",
    "Beatrice L. Nakamura",
    "Catherine M. O'Neill",
    "Dmitri P. Volkov",
    "Evelyn R. Chen",
    "Fernando A. Morales",
    "Greta S. Lindström",
    "Hassan K. Al-Farouq",
    "Isabelle T. DuPont",
    "Jamal N. Washington",
]


def init_state():
    st.session_state.setdefault("holding", None)
    st.session_state.setdefault("bridge_slots", [None] * BRIDGE_SLOTS)
    st.session_state.setdefault("even_slots", [None] * EVEN_SLOTS)
    st.session_state.setdefault("manual_pick", "—")


def pick(value: str):
    st.session_state.holding = value


def all_placed_values() -> set[str]:
    return set(st.session_state.bridge_slots) | set(st.session_state.even_slots)


def remove_value_everywhere(value: str):
    for key in ("bridge_slots", "even_slots"):
        slots = st.session_state[key]
        for i, v in enumerate(slots):
            if v == value:
                slots[i] = None


def slot_click(row_key: str, idx: int):
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


def centered_row(num_slots: int, render_slot_button):
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


def render_wrapped_chips(pairs: list[tuple[str, str]], *, per_row: int = 6, key_prefix: str = "chip"):
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


def on_manual_pick_change():
    val = st.session_state.manual_pick
    if val != "—":
        pick(val)


init_state()

st.title("POC: Click chip/dropdown → click slot")

# --- Holding text ---
holding = st.session_state.holding
if holding is None:
    st.markdown("**Click an officer to crew.**")
else:
    st.markdown(f"**Click a position for `{holding}`, or click another officer.**")

st.divider()

# --- BRIDGE with labels above slots ---
st.subheader("Bridge", text_alignment="center")

def render_bridge_label(col, i):
    labels = ["#1", "Capt.", "#2"]
    col.markdown(
        f"<div style='text-align:center; font-size:0.85rem; opacity:0.8;'>{labels[i]}</div>",
        unsafe_allow_html=True,
    )

def render_bridge_slot(col, i):
    val = st.session_state.bridge_slots[i]
    label = val if val is not None else "—"
    col.button(label, key=f"bridge_{i}", on_click=slot_click, args=("bridge_slots", i))

centered_row(BRIDGE_SLOTS, render_bridge_label)
centered_row(BRIDGE_SLOTS, render_bridge_slot)

st.divider()

# --- EVENS (10 slots) ---
st.subheader("Below-Deck Officers", text_alignment="center")

def render_below_decks_slot(col, i):
    val = st.session_state.even_slots[i]
    label = val if val is not None else "—"
    col.button(label, key=f"even_{i}", on_click=slot_click, args=("even_slots", i))

centered_row(EVEN_SLOTS, render_below_decks_slot)

st.divider()

# --- Bottom: 50/50 Manual Pick + Suggestions ---
left, right = st.columns(2)

with left:
    st.subheader("Choose Officers (type to search)")
    st.selectbox(
        "Pick an officer name",
        options=["—"] + OFFICERS,
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

st.caption("Tip: click a filled slot with nothing held to clear it (suggestions will reappear).")
