from __future__ import annotations

import logging
from datetime import datetime
from typing import Iterable, Set
from typing import Sequence

import pandas as pd
import streamlit as st

from veschov.io.SessionInfo import SessionInfo, ShipSpecifier
from veschov.transforms.columns import ATTACKER_COLUMN_CANDIDATES, TARGET_COLUMN_CANDIDATES, resolve_column
from veschov.ui.chirality import Lens, resolve_lens
from veschov.ui.components.combat_log_header import get_number_format
from veschov.ui.object_reports.AbstractReport import AbstractReport

SerializedShipSpec = tuple[str, str, str]
logger = logging.getLogger(__name__)

OUTCOME_ICONS = {
    "VICTORY": ("Victory", "🏆"),
    "DEFEAT": ("Defeat", "💀"),
    "PARTIAL VICTORY": ("Partial Victory", "⚖️"),
    "PARTIAL": ("Partial Victory", "⚖️"),
}


class AttackerAndTargetReport(AbstractReport):

    def render_combat_log_header(
            self,
            players_df: pd.DataFrame | None,
            fleets_df: pd.DataFrame | None,
            battle_df: pd.DataFrame | None,
            *,
            lens_key: str,
            session_info: SessionInfo | Set[ShipSpecifier] | None = None,
    ) -> tuple[str, Lens | None]:
        """Render the standard header controls for combat-log reports."""
        number_format = get_number_format()

        resolved_session_info = session_info or st.session_state.get("session_info")
        if resolved_session_info is None and battle_df is not None:
            resolved_session_info = SessionInfo(battle_df)
        if resolved_session_info is not None:
            st.session_state["session_info"] = resolved_session_info

        selected_attackers, selected_targets = self.render_actor_target_selector(
            st.session_state.get("session_info")
        )
        lens = None
        if selected_attackers and selected_targets:
            lens = resolve_lens(lens_key, selected_attackers, selected_targets)
            if len(selected_attackers) == 1 and len(selected_targets) == 1:
                attacker_name = lens.actor_name or "Attacker"
                target_name = lens.target_name or "Target"
                st.caption(f"Lens: {lens.label} ({attacker_name} → {target_name})")
            else:
                attacker_label = "Attacker ships" if len(selected_attackers) != 1 else "Attacker ship"
                target_label = "Target ships" if len(selected_targets) != 1 else "Target ship"
                st.caption(f"Lens: {attacker_label} → {target_label}")

        render_combat_summary(players_df, fleets_df, battle_df=battle_df, number_format=number_format)
        st.divider()
        return number_format, lens

    def apply_combat_lens(
            self,
            df: pd.DataFrame,
            lens: Lens | None,
            *,
            attacker_column_candidates: Iterable[str] = ATTACKER_COLUMN_CANDIDATES,
            target_column_candidates: Iterable[str] = TARGET_COLUMN_CANDIDATES,
            include_nan_attackers: bool = False,
            include_nan_targets: bool = False,
    ) -> pd.DataFrame:
        """Filter combat data using the selected attacker specs and column-based targets."""
        if lens is None:
            return df

        session_info = st.session_state.get("session_info")
        filtered = df

        attacker_column = resolve_column(filtered, attacker_column_candidates)
        target_column = resolve_column(filtered, target_column_candidates)

        attacker_mask = pd.Series(True, index=filtered.index)
        attacker_specs = lens.attacker_specs
        if isinstance(session_info, SessionInfo) and attacker_specs:
            attacker_df = session_info.get_combat_df_filtered_by_attackers(attacker_specs)
            attacker_mask = filtered.index.isin(attacker_df.index)
        elif attacker_column:
            attacker_names = lens.attacker_names()
            if attacker_names:
                attacker_mask = filtered[attacker_column].isin(attacker_names)

        if include_nan_attackers and attacker_column:
            attacker_mask |= filtered[attacker_column].isna()

        filtered = filtered.loc[attacker_mask]

        if target_column:
            target_names = lens.target_names()
            if target_names:
                target_series = filtered[target_column]
                target_mask = target_series.isin(target_names)
                if include_nan_targets:
                    target_mask |= target_series.isna()
                filtered = filtered.loc[target_mask]

        return filtered

    @staticmethod
    def _serialize_spec(spec: ShipSpecifier) -> SerializedShipSpec:
        return (spec.name or "", spec.alliance or "", spec.ship or "")

    @staticmethod
    def _swap_selected_specs() -> None:
        attackers = st.session_state.get("selected_attacker_specs", [])
        targets = st.session_state.get("selected_target_specs", [])
        st.session_state["selected_attacker_specs"] = targets
        st.session_state["selected_target_specs"] = attackers

    @staticmethod
    def _normalize_specs(session_info: SessionInfo | Set[ShipSpecifier] | None) -> Sequence[ShipSpecifier]:
        if isinstance(session_info, SessionInfo):
            specs = session_info.get_every_ship()
        elif isinstance(session_info, set):
            specs = session_info
        else:
            specs = set()

        return sorted(specs, key=lambda spec: str(spec))

    @staticmethod
    def _resolve_defaults(
            serialized: Iterable[SerializedShipSpec] | None,
            spec_lookup: dict[SerializedShipSpec, ShipSpecifier],
            fallback: Sequence[ShipSpecifier],
    ) -> list[ShipSpecifier]:
        if serialized:
            resolved = [spec_lookup[item] for item in serialized if item in spec_lookup]
            if resolved:
                return resolved
        return list(fallback)

    def render_actor_target_selector(
            self,
            session_info: SessionInfo | Set[ShipSpecifier] | None,
    ) -> tuple[Sequence[ShipSpecifier], Sequence[ShipSpecifier]]:
        options = self._normalize_specs(session_info)
        if not options:
            st.warning("No ship data available to select attacker/target.")
            return (), ()

        spec_lookup = {self._serialize_spec(spec): spec for spec in options}
        default_attacker = self._resolve_defaults(
            st.session_state.get("selected_attacker_specs"),
            spec_lookup,
            options[:1],
        )
        default_target = self._resolve_defaults(
            st.session_state.get("selected_target_specs"),
            spec_lookup,
            options[-1:],
        )

        selector_left, selector_swap, selector_right = st.columns([8, 1, 8])
        with selector_left:
            selected_attackers = st.multiselect(
                "Attacker",
                options,
                default=default_attacker,
                format_func=str,
            )
        with selector_swap:
            st.button(
                "🔄",
                help="Swap attacker and target selections.",
                key="swap_attacker_target_specs",
                on_click=self._swap_selected_specs,
                width="stretch",
            )
        with selector_right:
            selected_targets = st.multiselect(
                "Target",
                options,
                default=default_target,
                format_func=str,
            )

        st.session_state["selected_attacker_specs"] = [self._serialize_spec(spec) for spec in selected_attackers]
        st.session_state["selected_target_specs"] = [self._serialize_spec(spec) for spec in selected_targets]

        return selected_attackers, selected_targets


def render_combat_summary(
        self,
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

    context_lines = self._format_context(players_df, battle_df)
    if context_lines:
        context_text = " • ".join(context_lines)
        st.markdown(
            "<div style='text-align:center; font-size:1.05rem; font-weight:600;'>"
            f"{context_text}</div>",
            unsafe_allow_html=True,
        )

    session_info = st.session_state.get("session_info")
    name_lookup, ship_lookup = self._alliance_lookup(session_info)

    players_rows = players_df.iloc[:-1] if len(players_df) > 1 else players_df.iloc[0:0]
    npc_row = players_df.iloc[-1:]

    list_cols = st.columns(2)
    with list_cols[0]:
        self._render_combatant_list("Players", players_rows, name_lookup, ship_lookup)
    with list_cols[1]:
        self._render_combatant_list("NPC", npc_row, name_lookup, ship_lookup)


def _format_context(self, players_df: pd.DataFrame, battle_df: pd.DataFrame | None) -> list[str]:
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


def _alliance_lookup(
        self,
        session_info: SessionInfo | None,
) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    name_lookup: dict[str, str] = {}
    ship_lookup: dict[tuple[str, str], str] = {}
    if not isinstance(session_info, SessionInfo):
        return name_lookup, ship_lookup

    for spec in session_info.get_every_ship():
        if not isinstance(spec, ShipSpecifier):
            continue
        name = self._normalize_text(spec.name)
        ship = self._normalize_text(spec.ship)
        alliance = self._normalize_text(spec.alliance)
        if name and alliance and name not in name_lookup:
            name_lookup[name] = alliance
        if name and ship and alliance:
            ship_lookup[(name, ship)] = alliance
    return name_lookup, ship_lookup


def _render_combatant_list(
        self,
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
        emoji = self._outcome_emoji(row.get("Outcome"))
        label = self._format_combatant_label(row, name_lookup, ship_lookup)
        lines.append(f"- {emoji} {label}")
    st.markdown("\n".join(lines))


def _outcome_emoji(self, outcome: object) -> str:
    if isinstance(outcome, str):
        normalized = outcome.strip().upper().replace("_", " ")
        label_emoji = OUTCOME_ICONS.get(normalized)
        if label_emoji:
            return label_emoji[1]
    return "❔"


def _normalize_text(self, value: object) -> str:
    if pd.isna(value) or value is None:
        return ""
    return str(value).strip()


def _format_combatant_label(
        self,
        row: pd.Series,
        name_lookup: dict[str, str],
        ship_lookup: dict[tuple[str, str], str],
) -> str:
    name = self._normalize_text(row.get("Player Name"))
    ship = self._normalize_text(row.get("Ship Name"))
    alliance = ship_lookup.get((name, ship)) or name_lookup.get(name, "")
    label = name or "Unknown"
    if alliance:
        label = f"{label} [{alliance}]"
    if ship and ship != name:
        label = f"{label} — {ship}"
    return label
