from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
from collections import defaultdict
from typing import Optional

import streamlit as st
import html


# ----------------------------
# Data model
# ----------------------------

class StatCol(IntEnum):
    C1 = 1
    C2 = 2
    C3 = 3
    C4 = 4


class StatHint(Enum):
    GOOD = "GOOD"
    WARN = "WARN"
    BAD = "BAD"
    MAX = "MAX"
    MIN = "MIN"
    INFO = "INFO"


_HINT_EMOJI: dict[StatHint, str] = {
    StatHint.GOOD: "✅",
    StatHint.WARN: "⚠️",
    StatHint.BAD: "🛑",
    StatHint.MAX: "🔥",
    StatHint.MIN: "🧊",
    StatHint.INFO: "ℹ️",
}


@dataclass(frozen=True)
class Statistic:
    label: str
    value: str
    col: Optional[StatCol] = None      # None => auto-place
    priority: int = 100               # lower => earlier
    hint: Optional[StatHint] = None
    help: Optional[str] = None        # shown in popover

    # Future-friendly fields (optional, unused in row renderer unless you want them)
    delta: Optional[str] = None
    delta_mode: str = "normal"        # "normal" | "inverse" | "off"


# ----------------------------
# Layout helpers
# ----------------------------

def _choose_num_cols(n_stats: int, *, max_cols: int = 4) -> int:
    """Heuristic: pick 0..max_cols based on how many stats we have."""
    if n_stats <= 0:
        return 0
    if n_stats <= 4:
        return min(2, max_cols)
    if n_stats <= 10:
        return min(3, max_cols)
    return min(4, max_cols)


def _layout_stats(stats: list[Statistic], *, max_cols: int = 4) -> dict[int, list[Statistic]]:
    """Return a mapping {1..ncols: [stats...]} with pinned + auto placement."""
    if not stats:
        return {}

    # Stable ordering: priority, then label (you can add tie-breakers if desired)
    stats_sorted = sorted(stats, key=lambda s: (s.priority, s.label))

    ncols = _choose_num_cols(len(stats_sorted), max_cols=max_cols)
    if ncols == 0:
        return {}

    # Separate pinned vs floating
    pinned: dict[int, list[Statistic]] = defaultdict(list)
    floating: list[Statistic] = []
    for s in stats_sorted:
        if s.col is None:
            floating.append(s)
        else:
            pinned[int(s.col)].append(s)

    # Initialize columns
    cols_map: dict[int, list[Statistic]] = {i: [] for i in range(1, ncols + 1)}

    # Place pinned (ignore out-of-range pins quietly)
    for c, items in pinned.items():
        if 1 <= c <= ncols:
            cols_map[c].extend(items)

    # Greedy fill: always put next floating stat in the shortest column
    for s in floating:
        target = min(cols_map.keys(), key=lambda c: len(cols_map[c]))
        cols_map[target].append(s)

    return cols_map

# ----------------------------
# Rendering
# ----------------------------
def render_stat_row_linktip(s: Statistic) -> None:
    prefix = f"{_HINT_EMOJI.get(s.hint, '')} " if s.hint else ""
    if s.help:
        # style="color:#1f77b4; text-decoration:underline; cursor:help;">
        label_html = f"""{prefix}<span title="{html.escape(s.help, quote=True)}"
                           style="cursor:help;">
                           {html.escape(s.label)}
                         </span>"""
        st.markdown(f"{label_html}: {html.escape(s.value)}", unsafe_allow_html=True)
    else:
        st.markdown(f"{prefix}**{s.label}:** {s.value}")

# def _render_stat_row(
#     s: Statistic,
#     key: str,
#     *,
#     label_w: float = 0.55,
#     value_w: float = 0.37,
#     spacer_w: float = 0.03,
#     icon_w: float = 0.05,
# ) -> None:
#     content_w = label_w + value_w + spacer_w
#     left, right = st.columns([content_w, icon_w], vertical_alignment="center")
#
#     with st.container(horizontal=True):
#     # with left:
#         prefix = f"{_HINT_EMOJI.get(s.hint, '')} " if s.hint else ""
#         # label + value inline -> no “spread”
#         st.markdown(f"{prefix}**{s.label}:** {s.value}")
#
#         # with right:
#         if s.help:
#             # tiny tooltip icon; disabled keeps it from looking too “clickable”
#             st.button(
#                 "ℹ️",
#                 key = key,
#                 help=s.help,
#                 disabled=True,
#                 use_container_width=False,
#             )
#         else:
#             st.write("")

def info_tooltip(help_text: str, key: str) -> None:
    st.button("ℹ️", key=key, help=help_text, disabled=True)

def render_stats(
    stats: list[Statistic],
    *,
    max_cols: int = 4,
    gap: str = "small",
    label_w: float = 0.58,
    value_w: float = 0.32,
    icon_w: float = 0.10,
    show_header: bool = False,
) -> None:
    """
    Public entrypoint:
      - auto layout into 0..max_cols columns
      - per-column render of aligned stat rows with popovers
    """
    cols_map = _layout_stats(stats, max_cols=max_cols)
    if not cols_map:
        return

    cols = st.columns(len(cols_map), gap=gap)

    for i, col_idx in enumerate(sorted(cols_map.keys())):
        with cols[i]:
            if show_header:
                st.caption(f"Stats {col_idx}")
            for s in cols_map[col_idx]:
                key = f"stat_{i}_{col_idx}_{s}"
                render_stat_row_linktip(s) #, label_w=label_w, value_w=value_w, icon_w=icon_w)


# ----------------------------
# Example usage
# ----------------------------
if __name__ == "__main__":
    demo = [
        Statistic("Shield Mitigation", "84%", hint=StatHint.GOOD, help="Observed shield mitigation (baseline is 84%).", priority=1),
        Statistic("Total Normal", "150,895,001,600", help="Sum of normal-lane damage before mitigation.", priority=5),
        Statistic("Total Iso", "1,625,138,528,256", hint=StatHint.MAX, help="Sum of isolytic-lane damage before mitigation.", priority=2),
        Statistic("Shots", "36", priority=10),
        Statistic("Target Ship", "Explorer", col=StatCol.C2, priority=3, help="Pinned to column 2 as an example."),
    ]

    st.title("Demo")
    render_stats(demo, show_header=False)
