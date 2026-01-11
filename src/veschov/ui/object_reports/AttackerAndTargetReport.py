from __future__ import annotations

import logging
from abc import abstractmethod
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
        #
        # This section just sets up variables
        #
        number_format = get_number_format()

        resolved_session_info = session_info or st.session_state.get("session_info")
        if resolved_session_info is None and battle_df is not None:
            resolved_session_info = SessionInfo(battle_df)
        if resolved_session_info is not None:
            st.session_state["session_info"] = resolved_session_info

        #
        # Adds the actor/target selector
        #
        selected_attackers, selected_targets = self.render_actor_target_selector(
            resolved_session_info,
            players_df,
        )

        #
        # Adds the lens indicator
        #
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

        #
        # Adds the system/time/and rounds line
        #
        #
        # Adds the combatants lines
        #
        if isinstance(players_df, pd.DataFrame) and not players_df.empty:
            self._render_system_time_and_rounds(players_df, battle_df)
            # self.render_combatants(resolved_session_info, battle_df)
        else:
            st.info("No player metadata found in this file.")

        return number_format, lens

    def _render_system_time_and_rounds(self, players_df, battle_df):
        context_lines = self._get_system_time_and_rounds(players_df, battle_df)
        if context_lines:
            context_text = " • ".join(context_lines)
            st.markdown(
                "<div style='text-align:center; font-size:1.05rem; font-weight:600;'>"
                f"{context_text}</div>",
                unsafe_allow_html=True,
            )

    def _get_system_time_and_rounds(self, players_df: pd.DataFrame, battle_df: pd.DataFrame | None) -> list[str]:
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

    def render_combatants(
            self,
            session_info: SessionInfo | Set[ShipSpecifier] | None,
            battle_df: pd.DataFrame | None,
    ) -> None:
        if not isinstance(session_info, SessionInfo) and isinstance(battle_df, pd.DataFrame):
            session_info = SessionInfo(battle_df)

        combatant_specs = self._normalize_specs(session_info)
        if not combatant_specs:
            st.info("No combatant data found in this file.")
            return

        players_specs = [
            spec for spec in combatant_specs if self._normalize_text(spec.alliance)
        ]
        npc_specs = [
            spec for spec in combatant_specs if not self._normalize_text(spec.alliance)
        ]

        outcome_lookup = {}
        if isinstance(session_info, SessionInfo):
            outcome_lookup = self._build_outcome_lookup(session_info.players_df)

        list_cols = st.columns(2)
        with list_cols[0]:
            self._render_combatant_list("Players", players_specs, outcome_lookup)
        with list_cols[1]:
            self._render_combatant_list("NPC", npc_specs, outcome_lookup)

    def _render_combatant_list(
            self,
            title: str,
            specs: Sequence[ShipSpecifier],
            outcome_lookup: dict[SerializedShipSpec, object],
    ) -> None:
        st.markdown(f"**{title}**")
        if not specs:
            st.caption("None listed in the current log.")
            return
        lines = []
        for spec in specs:
            label = self._format_ship_spec_label(spec, outcome_lookup)
            lines.append(f"- {label}")
        st.markdown("\n".join(lines))

        # ########################################################################################################
        # ########################################################################################################
        # ########################################################################################################

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

    @abstractmethod
    def get_lens_key(self) -> str:
        pass

    def render_header(self, df: pd.DataFrame):
        players_df = df.attrs.get("players_df")
        fleets_df = df.attrs.get("fleets_df")
        _, lens = self.render_combat_log_header(
            players_df,
            fleets_df,
            df,
            lens_key=self.get_lens_key(),
        )
        return lens

    @staticmethod
    def _serialize_spec(spec: ShipSpecifier) -> SerializedShipSpec:
        return (spec.name or "", spec.alliance or "", spec.ship or "")

    @staticmethod
    def _swap_selected_specs() -> None:
        attackers = st.session_state.get("selected_attacker_specs", [])
        targets = st.session_state.get("selected_target_specs", [])
        attacker_roster = st.session_state.get("attacker_roster_specs", [])
        target_roster = st.session_state.get("target_roster_specs", [])
        st.session_state["selected_attacker_specs"] = targets
        st.session_state["selected_target_specs"] = attackers
        st.session_state["attacker_roster_specs"] = target_roster
        st.session_state["target_roster_specs"] = attacker_roster

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
    def _gather_specs(
            session_info: SessionInfo | Set[ShipSpecifier] | None,
    ) -> tuple[Sequence[ShipSpecifier], Sequence[ShipSpecifier]]:
        if isinstance(session_info, SessionInfo):
            specs = session_info.get_every_ship()
        elif isinstance(session_info, set):
            specs = session_info
        else:
            specs = set()

        options = sorted(specs, key=lambda spec: str(spec))
        raw_specs = list(specs)
        return options, raw_specs

    def _resolve_player_alliance(self, row: pd.Series) -> str:
        for column in ("Alliance", "Player Alliance"):
            if column in row.index:
                alliance = self._normalize_text(row.get(column))
                if alliance:
                    return alliance
        return ""

    def _match_enemy_spec(
            self,
            players_df: pd.DataFrame | None,
            options: Sequence[ShipSpecifier],
    ) -> ShipSpecifier | None:
        if not isinstance(players_df, pd.DataFrame) or players_df.empty:
            return None
        row = players_df.iloc[-1]
        name = self._normalize_text(row.get("Player Name"))
        alliance = self._resolve_player_alliance(row)
        ship = self._normalize_text(row.get("Ship Name"))
        if not any([name, alliance, ship]):
            return None

        for spec in options:
            if (
                    self._normalize_text(spec.name) == name
                    and self._normalize_text(spec.alliance) == alliance
                    and self._normalize_text(spec.ship) == ship
            ):
                return spec
        return None

    def _default_target_from_players(
            self,
            players_df: pd.DataFrame | None,
            options: Sequence[ShipSpecifier],
            raw_specs: Sequence[ShipSpecifier],
    ) -> list[ShipSpecifier]:
        matched = self._match_enemy_spec(players_df, options)
        if matched is not None:
            return [matched]
        if raw_specs:
            return [raw_specs[-1]]
        return []

    @staticmethod
    def _dedupe_specs(specs: Iterable[SerializedShipSpec]) -> list[SerializedShipSpec]:
        """Remove duplicate serialized specs while preserving order."""
        seen: set[SerializedShipSpec] = set()
        deduped: list[SerializedShipSpec] = []
        for spec in specs:
            if spec in seen:
                continue
            seen.add(spec)
            deduped.append(spec)
        return deduped

    @classmethod
    def _filter_roster(
            cls,
            roster: Iterable[SerializedShipSpec] | None,
            spec_lookup: dict[SerializedShipSpec, ShipSpecifier],
    ) -> list[SerializedShipSpec]:
        """Filter a serialized roster to specs that still exist in the lookup."""
        if not roster:
            return []
        deduped = cls._dedupe_specs(roster)
        filtered = [spec for spec in deduped if spec in spec_lookup]
        if len(filtered) < len(deduped):
            dropped = [spec for spec in deduped if spec not in spec_lookup]
            logger.warning(
                "Dropped %d roster spec(s) missing from current ship options: %s",
                len(dropped),
                dropped,
            )
        return filtered

    def _render_role_panel(
            self,
            title: str,
            roster_specs: Sequence[SerializedShipSpec],
            selected_specs: set[SerializedShipSpec],
            spec_lookup: dict[SerializedShipSpec, ShipSpecifier],
            key_prefix: str,
            outcome_lookup: dict[SerializedShipSpec, object],
    ) -> list[SerializedShipSpec]:
        """Render a checkbox list for a role roster and return selected specs."""
        st.markdown(f"**{title}**")
        if not roster_specs:
            logger.warning("No roster specs available for %s selection.", title)
            st.caption("None listed in the current log.")
            return []
        resolved: list[SerializedShipSpec] = []
        for spec_key in roster_specs:
            spec = spec_lookup.get(spec_key)
            if spec is None:
                logger.warning(
                    "Roster spec %s missing from lookup during %s selection.",
                    spec_key,
                    title,
                )
                continue
            label = self._format_ship_spec_label(spec, outcome_lookup)
            checkbox_key = f"{key_prefix}_{spec_key[0]}_{spec_key[1]}_{spec_key[2]}"
            desired_value = spec_key in selected_specs
            if st.session_state.get(checkbox_key) != desired_value:
                st.session_state[checkbox_key] = desired_value
            checked = st.checkbox(label, key=checkbox_key)
            if checked:
                resolved.append(spec_key)
        return resolved

    def render_actor_target_selector(
            self,
            session_info: SessionInfo | Set[ShipSpecifier] | None,
            players_df: pd.DataFrame | None,
    ) -> tuple[Sequence[ShipSpecifier], Sequence[ShipSpecifier]]:
        options, raw_specs = self._gather_specs(session_info)
        if not options:
            logger.warning(
                "Actor/target selector has no ship options; session_info=%s.",
                type(session_info).__name__,
            )
            st.warning("No ship data available to select attacker/target.")
            return (), ()

        spec_lookup = {self._serialize_spec(spec): spec for spec in options}
        available_specs = [self._serialize_spec(spec) for spec in options]
        target_fallback = self._default_target_from_players(players_df, options, raw_specs)
        if not target_fallback:
            target_fallback = list(options[-1:])
        attacker_fallback = [spec for spec in options if spec not in target_fallback]
        if not attacker_fallback:
            attacker_fallback = list(options[:1])
        default_target_specs = [self._serialize_spec(spec) for spec in target_fallback]
        default_attacker_specs = [self._serialize_spec(spec) for spec in attacker_fallback]

        attacker_roster_specs = self._filter_roster(
            st.session_state.get("attacker_roster_specs"),
            spec_lookup,
        )
        target_roster_specs = self._filter_roster(
            st.session_state.get("target_roster_specs"),
            spec_lookup,
        )
        if not attacker_roster_specs and not target_roster_specs:
            attacker_roster_specs = list(default_attacker_specs)
            target_roster_specs = list(default_target_specs)
        else:
            target_roster_specs = [spec for spec in target_roster_specs if spec not in attacker_roster_specs]
            missing_specs = [
                spec for spec in available_specs
                if spec not in attacker_roster_specs and spec not in target_roster_specs
            ]
            for spec in missing_specs:
                if spec in default_target_specs:
                    target_roster_specs.append(spec)
                else:
                    attacker_roster_specs.append(spec)
            if not target_roster_specs:
                target_roster_specs = list(default_target_specs)
                attacker_roster_specs = [spec for spec in available_specs if spec not in target_roster_specs]
            if not attacker_roster_specs:
                attacker_roster_specs = list(default_attacker_specs)
                target_roster_specs = [spec for spec in available_specs if spec not in attacker_roster_specs]

        st.session_state["attacker_roster_specs"] = attacker_roster_specs
        st.session_state["target_roster_specs"] = target_roster_specs

        selected_attacker_specs = self._filter_roster(
            st.session_state.get("selected_attacker_specs"),
            spec_lookup,
        )
        selected_target_specs = self._filter_roster(
            st.session_state.get("selected_target_specs"),
            spec_lookup,
        )
        if not selected_attacker_specs:
            logger.warning("No selected attacker specs remained after filtering; using roster defaults.")
            selected_attacker_specs = list(attacker_roster_specs)
        else:
            selected_attacker_specs = [
                spec for spec in selected_attacker_specs if spec in attacker_roster_specs
            ]
        if not selected_target_specs:
            logger.warning("No selected target specs remained after filtering; using roster defaults.")
            selected_target_specs = list(target_roster_specs)
        else:
            selected_target_specs = [
                spec for spec in selected_target_specs if spec in target_roster_specs
            ]

        selector_left, selector_swap, selector_right = st.columns([8, 1, 8])
        outcome_lookup = self._build_outcome_lookup(players_df)
        with selector_left:
            selected_attacker_specs = self._render_role_panel(
                "Attackers",
                attacker_roster_specs,
                set(selected_attacker_specs),
                spec_lookup,
                "attacker_include",
                outcome_lookup,
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
            selected_target_specs = self._render_role_panel(
                "Targets",
                target_roster_specs,
                set(selected_target_specs),
                spec_lookup,
                "target_include",
                outcome_lookup,
            )

        st.session_state["selected_attacker_specs"] = list(selected_attacker_specs)
        st.session_state["selected_target_specs"] = list(selected_target_specs)

        selected_attackers = [spec_lookup[item] for item in selected_attacker_specs if item in spec_lookup]
        selected_targets = [spec_lookup[item] for item in selected_target_specs if item in spec_lookup]
        return selected_attackers, selected_targets

    def _outcome_emoji(self, outcome: object) -> str:
        if isinstance(outcome, str):
            normalized = outcome.strip().upper().replace("_", " ")
            label_emoji = OUTCOME_ICONS.get(normalized)
            if label_emoji:
                return label_emoji[1]
        return "❔"

    def _build_outcome_lookup(self, players_df: pd.DataFrame | None) -> dict[SerializedShipSpec, object]:
        if not isinstance(players_df, pd.DataFrame) or players_df.empty:
            return {}
        if "Outcome" not in players_df.columns:
            return {}
        outcome_lookup: dict[SerializedShipSpec, object] = {}
        for _, row in players_df.iterrows():
            name = self._normalize_text(row.get("Player Name"))
            ship = self._normalize_text(row.get("Ship Name"))
            alliance = self._resolve_player_alliance(row)
            if not any([name, ship, alliance]):
                continue
            key = self._normalize_spec_key(name, alliance, ship)
            if key in outcome_lookup:
                continue
            outcome_lookup[key] = row.get("Outcome")
        return outcome_lookup

    def _normalize_text(self, value: object) -> str:
        if pd.isna(value) or value is None:
            return ""
        return str(value).strip()

    def _normalize_spec_key(self, name: object, alliance: object, ship: object) -> SerializedShipSpec:
        return (
            self._normalize_text(name),
            self._normalize_text(alliance),
            self._normalize_text(ship),
        )

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

    def _format_ship_spec_label(
            self,
            spec: ShipSpecifier,
            outcome_lookup: dict[SerializedShipSpec, object] | None = None,
    ) -> str:
        name = self._normalize_text(spec.name)
        ship = self._normalize_text(spec.ship)
        alliance = self._normalize_text(spec.alliance)
        outcome = None
        if outcome_lookup is not None:
            outcome = outcome_lookup.get(self._normalize_spec_key(name, alliance, ship))
        emoji = self._outcome_emoji(outcome)
        label = name or "Unknown"
        if alliance:
            label = f"{label} [{alliance}]"
        if ship and ship != name:
            label = f"{label} — {ship}"
        return f"{emoji} {label}"
