"""Streamlit UI for Apex Barrier per shot POC."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from typing import Iterable

import humanize
import pandas as pd
import plotly.express as px
import streamlit as st

from veschov.io.parser_stub import parse_battle_log
from veschov.ui.chirality import Lens
from veschov.ui.components.combat_log_header import (
    apply_combat_lens,
    render_combat_log_header,
    render_sidebar_combat_log_upload,
)

OPTIONAL_PREVIEW_COLUMNS: Iterable[str] = (
    "round",
    "battle_event",
    "is_crit",
    "Ship",
    "Weapon",
)

PLAYER_FIELD_LABELS = (
    ("Player Name", "Player Name"),
    ("Ship Name", "Ship Name"),
    ("Ship Level", "Ship Level"),
    ("Ship Strength", "Ship Strength"),
    ("Officer One", "Officer One"),
    ("Officer Two", "Officer Two"),
    ("Officer Three", "Officer Three"),
    ("Hull Health Remaining", "Hull Health Remaining"),
    ("Hull Health", "Hull Health"),
    ("Shield Health Remaining", "Shield Health Remaining"),
    ("Shield Health", "Shield Health"),
)

FLEET_STAT_COLUMNS = (
    "Fleet Type",
    "Attack",
    "Defense",
    "Health",
    "Critical Chance",
    "Critical Damage",
    "Armour",
    "Armor",
    "Shield Deflection",
    "Dodge",
    "Ship Ability",
    "Captain Maneuver",
    "Officer Ability 1",
    "Officer Ability 2",
    "Officer Ability 3",
)

FORMAT_NUMBER_FIELDS = {
    "Ship Strength",
    "Hull Health Remaining",
    "Hull Health",
    "Shield Health Remaining",
    "Shield Health",
}

FLEET_NUMBER_FIELDS = {
    "Attack",
    "Defense",
    "Health",
    "Armour",
    "Armor",
    "Shield Deflection",
    "Dodge",
}

PERCENT_FIELDS = {"Critical Chance", "Critical Damage"}

OUTCOME_DISPLAY = {
    "VICTORY": ("Victory", "🏆"),
    "PARTIAL": ("Partial Victory", "⚖️"),
    "DEFEAT": ("Defeat", "💀"),
}

ATTACKER_COLUMN_CANDIDATES = ("attacker_name", "Attacker")
TARGET_COLUMN_CANDIDATES = ("target_name", "Target", "Defender Name")


def _format_large_number(value: object, number_format: str) -> str:
    if pd.isna(value):
        return "—"
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return str(value)
    if abs(numeric) >= 1_000_000:
        if number_format == "Human":
            return humanize.intword(numeric)
        return f"{numeric:,.0f}"
    if float(numeric).is_integer():
        return f"{int(numeric)}"
    return str(value)


def _format_percent(value: object) -> str:
    if pd.isna(value):
        return "—"
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return str(value)
    if numeric <= 1:
        numeric *= 100
    return f"{numeric:.2f}%"


def _total_apex_barrier_mitigation(
    df: pd.DataFrame,
    *,
    lens: Lens | None,
) -> float | None:
    if "mitigated_apex" not in df.columns:
        return None
    mitigation_df = apply_combat_lens(
        df,
        lens,
        attacker_column_candidates=ATTACKER_COLUMN_CANDIDATES,
        target_column_candidates=TARGET_COLUMN_CANDIDATES,
    )
    total = pd.to_numeric(mitigation_df["mitigated_apex"], errors="coerce").sum(min_count=1)
    if pd.isna(total):
        return None
    return float(total)


def _format_health_pair(row: pd.Series, remaining: str, total: str, number_format: str) -> str:
    remaining_value = row.get(remaining)
    total_value = row.get(total)
    if pd.isna(remaining_value) and pd.isna(total_value):
        return "—"
    if pd.isna(remaining_value):
        return f"— / {_format_large_number(total_value, number_format)}"
    if pd.isna(total_value):
        return f"{_format_large_number(remaining_value, number_format)} / —"
    return f"{_format_large_number(remaining_value, number_format)} / {_format_large_number(total_value, number_format)}"


def _format_player_name(row: pd.Series) -> str:
    name = row.get("Player Name", "—")
    if pd.isna(name):
        name = "—"
    outcome = row.get("Outcome")
    if isinstance(outcome, str):
        outcome_key = outcome.strip().upper()
        label_emoji = OUTCOME_DISPLAY.get(outcome_key)
        if label_emoji:
            label, emoji = label_emoji
            return f"{name} {label}: {emoji}"
    return str(name)


def _player_summary_table(row: pd.Series, number_format: str) -> pd.DataFrame:
    data = []
    for label, column in PLAYER_FIELD_LABELS:
        if column in {"Hull Health Remaining", "Hull Health"}:
            continue
        if column in {"Shield Health Remaining", "Shield Health"}:
            continue
        if column == "Player Name":
            value = _format_player_name(row)
        else:
            value = row.get(column, "—")
        if pd.isna(value):
            value = "—"
        if column in FORMAT_NUMBER_FIELDS:
            value = _format_large_number(value, number_format)
        data.append((label, value))

    data.append(
        (
            "Hull Health Remaining / Hull Health",
            _format_health_pair(row, "Hull Health Remaining", "Hull Health", number_format),
        )
    )
    data.append(
        (
            "Shield Health Remaining / Shield Health",
            _format_health_pair(row, "Shield Health Remaining", "Shield Health", number_format),
        )
    )
    return pd.DataFrame(data, columns=["Field", "Value"])


def _format_battle_context(players_df: pd.DataFrame) -> list[str]:
    location = players_df["Location"].iloc[0] if "Location" in players_df.columns else None
    timestamp = players_df["Timestamp"].iloc[0] if "Timestamp" in players_df.columns else None
    lines = []
    if pd.notna(location):
        lines.append(f"**Location:** {location}")
    if pd.notna(timestamp):
        lines.append(f"**Timestamp:** {timestamp}")
    return lines


def render_metadata_header(df: pd.DataFrame, number_format: str) -> None:
    """Render player and fleet metadata tables for a battle log."""
    players_df = df.attrs.get("players_df")
    fleets_df = df.attrs.get("fleets_df")

    has_players = isinstance(players_df, pd.DataFrame) and not players_df.empty
    has_fleets = isinstance(fleets_df, pd.DataFrame) and not fleets_df.empty

    if not has_players and not has_fleets:
        st.info("No player/fleet metadata found in this file.")
        return

    st.subheader("Battle Metadata")

    if has_players:
        context_lines = _format_battle_context(players_df)
        if context_lines:
            st.markdown("  \n".join(context_lines))
        player_row = players_df.iloc[0]
        enemy_row = players_df.iloc[1] if len(players_df) > 1 else None
        left, right = st.columns(2)

        with left:
            st.markdown("#### Player")
            st.table(_player_summary_table(player_row, number_format))

        with right:
            st.markdown("#### Enemy")
            if enemy_row is not None:
                st.table(_player_summary_table(enemy_row, number_format))
            else:
                st.caption("Enemy row missing in player metadata.")

        if len(players_df) > 1:
            st.caption("Assuming first row is Player Fleet.")

    if has_fleets:
        st.markdown("#### Fleet Stats")
        visible_columns = [col for col in FLEET_STAT_COLUMNS if col in fleets_df.columns]
        if visible_columns:
            formatted_fleets = fleets_df.loc[:, visible_columns].copy()
            for column in visible_columns:
                if column in FLEET_NUMBER_FIELDS:
                    formatted_fleets[column] = formatted_fleets[column].apply(
                        lambda value: _format_large_number(value, number_format)
                    )
                if column in PERCENT_FIELDS:
                    formatted_fleets[column] = formatted_fleets[column].apply(_format_percent)
            st.dataframe(formatted_fleets, use_container_width=True)
        else:
            st.caption("Fleet stats are present but no expected columns were found.")


def render_apex_barrier_poc() -> None:
    """Render the Apex Barrier per-shot proof-of-concept report."""
    df = render_sidebar_combat_log_upload(
        "Apex Barrier Analysis",
        "Upload a battle log to estimate Apex Barrier per hit.",
        parser=parse_battle_log,
    )
    if df is None:
        st.info("No battle data loaded yet.")
        return

    battle_filename = st.session_state.get("battle_filename") or "Session battle data"

    players_df = df.attrs.get("players_df")
    fleets_df = df.attrs.get("fleets_df")
    number_format, lens = render_combat_log_header(
        players_df,
        fleets_df,
        df,
        lens_key="apex_barrier",
    )

    display_df = df.copy()
    display_df.attrs = {}

    include_missing = st.checkbox("Include rows without Apex Barrier hit", value=False)
    plot_df = (
        display_df if include_missing else display_df[display_df["apex_barrier_hit"].notna()]
    )
    plot_df = apply_combat_lens(
        plot_df,
        lens,
        attacker_column_candidates=ATTACKER_COLUMN_CANDIDATES,
        target_column_candidates=TARGET_COLUMN_CANDIDATES,
    )

    st.caption("Per-shot Apex Barrier values come from combat log mitigation fields.")
    title = f"Apex Barrier per Shot — {battle_filename}"
    fig = px.line(plot_df, x="shot_index", y="apex_barrier_hit", markers=True, title=title)
    st.plotly_chart(fig, use_container_width=True)

    total_mitigation = _total_apex_barrier_mitigation(
        display_df,
        lens=lens,
    )
    formatted_total = (
        _format_large_number(total_mitigation, number_format) if total_mitigation is not None else "—"
    )
    st.markdown(f"**Total Apex Barrier Damage Mitigation:** {formatted_total}")

    preview_cols = ["shot_index", "apex_barrier_hit"]
    preview_cols.extend(col for col in OPTIONAL_PREVIEW_COLUMNS if col in display_df.columns)
    preview_df = display_df.loc[:, preview_cols]
    st.caption("Preview of shot-level Apex values and optional combat log metadata.")
    st.dataframe(preview_df.head(200), use_container_width=True)
