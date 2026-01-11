"""Render a compact combat summary header."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

import re
from datetime import datetime

import humanize
import pandas as pd
import streamlit as st

from veschov.io.SessionInfo import SessionInfo, ShipSpecifier

from veschov.transforms.columns import (
    ATTACKER_COLUMN_CANDIDATES,
    TARGET_COLUMN_CANDIDATES,
    resolve_column,
)

OUTCOME_ICONS = {
    "VICTORY": ("Victory", "🏆"),
    "DEFEAT": ("Defeat", "💀"),
    "PARTIAL VICTORY": ("Partial Victory", "⚖️"),
    "PARTIAL": ("Partial Victory", "⚖️"),
}

BAR_COLORS = {
    "fill": "#7ea2c7",
    "remainder": "#d9a0a0",
    "border": "#d0d0d0",
    "text": "#1f1f1f",
}

POWER_COLUMNS = ("Ship Strength", "Ship Power")
COMBATANT_STAT_FIELDS = (
    ("Attack", "Attack"),
    ("Defense", "Defense"),
    ("Health", "Health"),
    ("Armour Pierce", "Armour Pierce"),
    ("Shield Pierce", "Shield Pierce"),
    ("Accuracy", "Accuracy"),
    ("Armour", "Armour"),
    ("Armour", "Armor"),
    ("Shield Deflection", "Shield Deflection"),
    ("Dodge", "Dodge"),
)


def _display_value(value: object, number_format: str = "Human") -> str:
    if pd.isna(value):
        return "—"
    numeric_value = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric_value = float(value)
    else:
        text = str(value).strip()
        if text:
            numeric = pd.to_numeric(text.replace(",", ""), errors="coerce")
            if pd.notna(numeric):
                numeric_value = float(numeric)
        else:
            return "—"
    if numeric_value is not None:
        if abs(numeric_value) >= 1_000_000 and number_format == "Human":
            return humanize.intword(numeric_value, format="%.1f")
        if numeric_value.is_integer():
            return f"{int(numeric_value):,}"
        return f"{numeric_value:,}"
    text = str(value).strip()
    return text or "—"


def _parse_numeric_value(value: object) -> float | None:
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    text = str(value).strip().lower()
    if not text or text == "—":
        return None
    multipliers = {
        "trillion": 1_000_000_000_000,
        "billion": 1_000_000_000,
        "million": 1_000_000,
        "thousand": 1_000,
    }
    multiplier = 1.0
    for suffix, factor in multipliers.items():
        if suffix in text:
            multiplier = factor
            break
    match = re.search(r"[-+]?\d*\.?\d+", text.replace(",", ""))
    if match:
        return float(match.group()) * multiplier
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return None
    return float(numeric)


def _format_outcome_title(row: pd.Series, number_format: str) -> str:
    name = _display_value(row.get("Player Name"), number_format)
    outcome = row.get("Outcome")
    if isinstance(outcome, str):
        normalized = outcome.strip().upper()
        normalized = normalized.replace("_", " ")
        label_emoji = OUTCOME_ICONS.get(normalized)
        if label_emoji:
            label, emoji = label_emoji
            return f"{name} {label}: {emoji}"
    return f"{name} Outcome: ❔"


def _outcome_emoji(outcome: object) -> str:
    if isinstance(outcome, str):
        normalized = outcome.strip().upper().replace("_", " ")
        label_emoji = OUTCOME_ICONS.get(normalized)
        if label_emoji:
            return label_emoji[1]
    return "❔"


def _ship_power_text(row: pd.Series, number_format: str) -> str:
    column = next((col for col in POWER_COLUMNS if col in row.index), None)
    if not column:
        return "—"
    value = _display_value(row.get(column), number_format)
    if value == "—":
        return value
    label = "power" if column == "Ship Power" else "strength"
    if label in value.lower():
        return value
    return f"{value} {label}"


def _officer_columns(row: pd.Series, number_format: str) -> list[tuple[str, str]]:
    return [
        ("#2", _display_value(row.get("Officer Two"), number_format)),
        ("Captain", _display_value(row.get("Officer One"), number_format)),
        ("#3", _display_value(row.get("Officer Three"), number_format)),
    ]


def _render_officer_column(label: str, name: str) -> None:
    st.markdown(
        f"""
        <div style="text-align:center; font-size:0.85rem; color:#6b6b6b;">{label}</div>
        <div style="text-align:center; font-weight:600;">{name}</div>
        """,
        unsafe_allow_html=True,
    )


def render_ratio_bar(
        label: str,
        remaining: object,
        total: object,
        *,
        height_px: int = 22,
        number_format: str = "Human",
) -> None:
    remaining_value = _parse_numeric_value(remaining)
    total_value = _parse_numeric_value(total)
    if remaining_value is None or total_value in (None, 0):
        ratio = 0.0
        display_text = "N/A"
    else:
        ratio = max(0.0, min(remaining_value / total_value, 1.0))
        display_text = (
            f"{_display_value(remaining, number_format)} / {_display_value(total, number_format)}"
        )

    bar_html = f"""
    <div style="width:100%;">
      <div style="border:1px solid {BAR_COLORS['border']}; background:{BAR_COLORS['remainder']};
                  height:{height_px}px; position:relative; border-radius:4px; overflow:hidden;">
        <div style="height:100%; width:{ratio * 100:.1f}%; background:{BAR_COLORS['fill']};"></div>
        <div style="position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
                    font-size:0.85rem; color:{BAR_COLORS['text']};">
          {display_text}
        </div>
      </div>
    </div>
    """
    if label:
        st.markdown(f"**{label}:**", unsafe_allow_html=True)
    st.markdown(bar_html, unsafe_allow_html=True)


def _format_context(players_df: pd.DataFrame, battle_df: pd.DataFrame | None) -> list[str]:
    location = players_df["Location"].iloc[0] if "Location" in players_df.columns else None
    timestamp = players_df["Timestamp"].iloc[0] if "Timestamp" in players_df.columns else None
    lines: list[str] = []

    context_parts: list[str] = []
    if pd.notna(location):
        location_text = str(location).strip()
        if location_text and "system" not in location_text.lower():
            location_text = f"{location_text} System"
        context_parts.append(location_text)
    if pd.notna(timestamp):
        parsed = pd.to_datetime(timestamp, errors="coerce")
        if pd.notna(parsed):
            parsed_dt = parsed.to_pydatetime()
            today_year = datetime.now().year
            date_part = f"{parsed_dt:%a} {parsed_dt.day} {parsed_dt:%b}"
            if parsed_dt.year != today_year:
                date_part = f"{date_part} [{parsed_dt:%Y}]"
            time_part = f"{parsed_dt:%H:%M}"
            context_parts.append(f"on {date_part} at {time_part}")
        else:
            context_parts.append(str(timestamp))
    if context_parts:
        lines.append(" ".join(context_parts))

    if isinstance(battle_df, pd.DataFrame) and not battle_df.empty and "round" in battle_df.columns:
        rounds = pd.to_numeric(battle_df["round"], errors="coerce")
        max_round = rounds.max()
        if pd.notna(max_round):
            lines.append(f"Battle Rounds: {int(max_round)}")
    return lines


def total_shots_by_attacker(battle_df: pd.DataFrame) -> dict[str, int]:
    attacker_column = resolve_column(battle_df, ATTACKER_COLUMN_CANDIDATES)
    target_column = resolve_column(battle_df, TARGET_COLUMN_CANDIDATES)
    if not attacker_column:
        return {}
    if "total_normal" in battle_df.columns:
        total_damage = pd.to_numeric(battle_df["total_normal"], errors="coerce")
    else:
        total_damage = pd.Series(pd.NA, index=battle_df.index)
    mask = total_damage > 0
    if target_column:
        mask = mask & (battle_df[attacker_column] != battle_df[target_column])
    counts = battle_df.loc[mask].groupby(attacker_column).size()
    return counts.to_dict()


def _combatant_stats_table(
        *,
        fleet_row: pd.Series | None,
        total_shots: int | None,
        number_format: str,
) -> pd.DataFrame:
    rows: list[tuple[str, str]] = []
    seen_labels: set[str] = set()
    if isinstance(fleet_row, pd.Series):
        for label, column in COMBATANT_STAT_FIELDS:
            if column not in fleet_row.index:
                continue
            if label in seen_labels:
                continue
            value = _display_value(fleet_row.get(column), number_format)
            rows.append((label, value))
            seen_labels.add(label)
    if total_shots is not None:
        rows.append(("Total Shots", _display_value(total_shots, number_format)))
    return pd.DataFrame(rows, columns=["Field", "Value"])


def render_player_card(
        row: pd.Series,
        number_format: str,
        *,
        fleet_row: pd.Series | None,
        total_shots: int | None,
) -> None:
    """Render a single player/NPC card for the summary header."""
    st.markdown(
        f"<h2 style='text-align:center; margin-bottom:0.4rem;'>"
        f"{_format_outcome_title(row, number_format)}</h2>",
        unsafe_allow_html=True,
    )

    ship_left, ship_mid, ship_right = st.columns(3)
    with ship_left:
        st.markdown(
            f"<div style='text-align:center; font-size:1.05rem; font-weight:600;'>"
            f"{_display_value(row.get('Ship Name'), number_format)}</div>",
            unsafe_allow_html=True,
        )
    with ship_mid:
        level = _display_value(row.get("Ship Level"), number_format)
        st.markdown(
            f"<div style='text-align:center;'>Level {level}</div>",
            unsafe_allow_html=True,
        )
    with ship_right:
        st.markdown(
            f"<div style='text-align:center;'>{_ship_power_text(row, number_format)}</div>",
            unsafe_allow_html=True,
        )

    officers = _officer_columns(row, number_format)
    officer_cols = st.columns(3)
    for col, (label, name) in zip(officer_cols, officers):
        with col:
            _render_officer_column(label, name)

    hull_row = st.columns([1, 6])
    with hull_row[0]:
        st.markdown("**Hull:**")
    with hull_row[1]:
        render_ratio_bar(
            "",
            row.get("Hull Health Remaining"),
            row.get("Hull Health"),
            number_format=number_format,
        )

    shield_row = st.columns([1, 6])
    with shield_row[0]:
        st.markdown("**Shield:**")
    with shield_row[1]:
        render_ratio_bar(
            "",
            row.get("Shield Health Remaining"),
            row.get("Shield Health"),
            number_format=number_format,
        )

    combatant_table = _combatant_stats_table(
        fleet_row=fleet_row,
        total_shots=total_shots,
        number_format=number_format,
    )
    if not combatant_table.empty:
        st.table(combatant_table)


def _normalize_text(value: object) -> str:
    if pd.isna(value) or value is None:
        return ""
    return str(value).strip()


def _alliance_lookup(
        session_info: SessionInfo | None,
) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    name_lookup: dict[str, str] = {}
    ship_lookup: dict[tuple[str, str], str] = {}
    if not isinstance(session_info, SessionInfo):
        return name_lookup, ship_lookup

    for spec in session_info.get_every_ship():
        if not isinstance(spec, ShipSpecifier):
            continue
        name = _normalize_text(spec.name)
        ship = _normalize_text(spec.ship)
        alliance = _normalize_text(spec.alliance)
        if name and alliance and name not in name_lookup:
            name_lookup[name] = alliance
        if name and ship and alliance:
            ship_lookup[(name, ship)] = alliance
    return name_lookup, ship_lookup


def _format_combatant_label(
        row: pd.Series,
        name_lookup: dict[str, str],
        ship_lookup: dict[tuple[str, str], str],
) -> str:
    name = _normalize_text(row.get("Player Name"))
    ship = _normalize_text(row.get("Ship Name"))
    alliance = ship_lookup.get((name, ship)) or name_lookup.get(name, "")
    label = name or "Unknown"
    if alliance:
        label = f"{label} [{alliance}]"
    if ship and ship != name:
        label = f"{label} — {ship}"
    return label


def _render_combatant_list(
        title: str,
        rows: pd.DataFrame,
        name_lookup: dict[str, str],
        ship_lookup: dict[tuple[str, str], str],
) -> None:
    st.markdown(f"**{title}**")
    if rows.empty:
        st.caption("None listed in the current log.")
        return
    lines = []
    for _, row in rows.iterrows():
        emoji = _outcome_emoji(row.get("Outcome"))
        label = _format_combatant_label(row, name_lookup, ship_lookup)
        lines.append(f"- {emoji} {label}")
    st.markdown("\n".join(lines))


def render_combat_summary(
        players_df: pd.DataFrame | None,
        fleets_df: pd.DataFrame | None = None,
        battle_df: pd.DataFrame | None = None,
        *,
        number_format: str = "Human",
) -> None:
    """Render a compact summary header for the uploaded combat log."""
    if not isinstance(players_df, pd.DataFrame) or players_df.empty:
        st.info("No player metadata found in this file.")
        return

    context_lines = _format_context(players_df, battle_df)
    if context_lines:
        context_text = " • ".join(context_lines)
        st.markdown(
            "<div style='text-align:center; font-size:1.05rem; font-weight:600;'>"
            f"{context_text}</div>",
            unsafe_allow_html=True,
        )

    session_info = st.session_state.get("session_info")
    name_lookup, ship_lookup = _alliance_lookup(session_info)

    players_rows = players_df.iloc[:-1] if len(players_df) > 1 else players_df.iloc[0:0]
    npc_row = players_df.iloc[-1:]

    list_cols = st.columns(2)
    with list_cols[0]:
        _render_combatant_list("Players", players_rows, name_lookup, ship_lookup)
    with list_cols[1]:
        _render_combatant_list("NPC", npc_row, name_lookup, ship_lookup)
