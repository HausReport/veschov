from __future__ import annotations

import json
import logging
from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable, Sequence, Set

import pandas as pd
import streamlit as st

from veschov.io.SessionInfo import SessionInfo, ShipSpecifier
from veschov.transforms.columns import ATTACKER_COLUMN_CANDIDATES, TARGET_COLUMN_CANDIDATES, resolve_column
from veschov.ui.chirality import Lens, resolve_lens
from veschov.ui.components.number_format import get_number_format
from veschov.ui.object_reports.AbstractReport import AbstractReport

SerializedShipSpec = tuple[str, str, str]
AttackerTargetState = dict[str, dict[str, list[dict[str, str]]]]
logger = logging.getLogger(__name__)


def serialize_spec(spec: ShipSpecifier) -> SerializedShipSpec:
    """Serialize a ShipSpecifier into a stable tuple for session storage."""
    return (spec.name or "", spec.alliance or "", spec.ship or "")


def serialize_spec_dict(spec: ShipSpecifier) -> dict[str, str]:
    """Serialize a ShipSpecifier into a JSON-friendly mapping."""
    return {
        "name": spec.name or "",
        "alliance": spec.alliance or "",
        "ship": spec.ship or "",
    }


def deserialize_spec_dict(spec: dict[str, str]) -> SerializedShipSpec:
    """Deserialize a JSON-friendly mapping into a spec key."""
    return SessionInfo.normalize_spec_key(
        spec.get("name"),
        spec.get("alliance"),
        spec.get("ship"),
    )


def serialize_spec_key_dict(spec: SerializedShipSpec) -> dict[str, str]:
    """Serialize a spec key tuple into a JSON-friendly mapping."""
    return {"name": spec[0], "alliance": spec[1], "ship": spec[2]}


@dataclass
class AttackerTargetSelection:
    """Container for attacker/target roster and selection state."""
    attacker_roster: list[SerializedShipSpec]
    target_roster: list[SerializedShipSpec]
    selected_attackers: list[SerializedShipSpec]
    selected_targets: list[SerializedShipSpec]


class AttackerTargetStateManager:
    """Encapsulate attacker/target state stored in Streamlit session_state."""
    STATE_KEY = "attacker_target_state"

    def __init__(
            self,
            *,
            spec_lookup: dict[SerializedShipSpec, ShipSpecifier],
            available_specs: Sequence[SerializedShipSpec],
            default_attacker_specs: Sequence[SerializedShipSpec],
            default_target_specs: Sequence[SerializedShipSpec],
            label_builder: Callable[[ShipSpecifier, dict[SerializedShipSpec, object] | None], str] | None = None,
            outcome_lookup: dict[SerializedShipSpec, object] | None = None,
    ) -> None:
        self._spec_lookup = spec_lookup
        self._available_specs = list(available_specs)
        self._default_attacker_specs = list(default_attacker_specs)
        self._default_target_specs = list(default_target_specs)
        self._label_builder = label_builder
        self._outcome_lookup = outcome_lookup or {}

    def resolve_state(self) -> AttackerTargetSelection:
        """Resolve and persist the current attacker/target state."""
        logger.debug(
            "Resolving attacker/target state (options=%d, defaults=attacker:%d target:%d).",
            len(self._available_specs),
            len(self._default_attacker_specs),
            len(self._default_target_specs),
        )
        stored_state = self._load_state()
        attacker_roster, target_roster = self._resolve_rosters(stored_state)
        selected_attackers = self._resolve_selected_specs(
            stored_state.selected_attackers if stored_state else None,
            attacker_roster,
            role="attacker",
        )
        selected_targets = self._resolve_selected_specs(
            stored_state.selected_targets if stored_state else None,
            target_roster,
            role="target",
        )
        resolved_state = AttackerTargetSelection(
            attacker_roster=attacker_roster,
            target_roster=target_roster,
            selected_attackers=selected_attackers,
            selected_targets=selected_targets,
        )
        self._persist_state(resolved_state)
        return resolved_state

    def render_role_panel(
            self,
            *,
            title: str,
            roster_specs: Sequence[SerializedShipSpec],
            selected_specs: Sequence[SerializedShipSpec],
            role: str,
            key_prefix: str,
    ) -> list[SerializedShipSpec]:
        """Render a checkbox list for a role roster and return selected specs."""
        if self._label_builder is None:
            raise ValueError("Label builder is required to render role panels.")
        st.markdown(f"**{title}**")
        if not roster_specs:
            logger.warning("No roster specs available for %s selection.", title)
            st.caption("None listed in the current log.")
            return []
        resolved: list[SerializedShipSpec] = []
        selected_set = set(selected_specs)
        for spec_key in roster_specs:
            spec = self._spec_lookup.get(spec_key)
            if spec is None:
                logger.warning(
                    "Roster spec %s missing from lookup during %s selection.",
                    spec_key,
                    title,
                )
                continue
            label = self._label_builder(spec, self._outcome_lookup)
            checkbox_key = f"{key_prefix}_{spec_key}"
            st.session_state[checkbox_key] = spec_key in selected_set
            checked = st.checkbox(label, key=checkbox_key)
            if checked:
                resolved.append(spec_key)
        logger.debug(
            "Rendered %s panel with %d roster specs; selected=%d.",
            role,
            len(roster_specs),
            len(resolved),
        )
        return resolved

    def update_from_render(
            self,
            *,
            roster_state: AttackerTargetSelection,
            selected_attackers: Sequence[SerializedShipSpec],
            selected_targets: Sequence[SerializedShipSpec],
    ) -> AttackerTargetSelection:
        """Persist the latest selections after rendering widgets."""
        updated_state = AttackerTargetSelection(
            attacker_roster=list(roster_state.attacker_roster),
            target_roster=list(roster_state.target_roster),
            selected_attackers=list(selected_attackers),
            selected_targets=list(selected_targets),
        )
        self._persist_state(updated_state)
        return updated_state

    def swap(self) -> None:
        """Swap attacker/target roster and selection state."""
        current_state = self.resolve_state()
        swapped_state = AttackerTargetSelection(
            attacker_roster=list(current_state.target_roster),
            target_roster=list(current_state.attacker_roster),
            selected_attackers=list(current_state.selected_targets),
            selected_targets=list(current_state.selected_attackers),
        )
        logger.warning(
            "Swapping attacker/target state (attackers=%d targets=%d).",
            len(swapped_state.selected_attackers),
            len(swapped_state.selected_targets),
        )
        self._persist_state(swapped_state)

    def resolve_ship_specs(
            self,
            selected_specs: Sequence[SerializedShipSpec],
    ) -> list[ShipSpecifier]:
        """Resolve selected spec keys into ShipSpecifiers."""
        return [self._spec_lookup[item] for item in selected_specs if item in self._spec_lookup]

    def _load_state(self) -> AttackerTargetSelection | None:
        """Load attacker/target state from session storage, if present."""
        state = st.session_state.get(self.STATE_KEY)
        if state is None:
            logger.debug("No attacker/target state found in session storage.")
            return None
        if not isinstance(state, dict):
            logger.warning("Attacker/target state has unexpected type: %s", type(state).__name__)
            return None
        selected = state.get("selected")
        roster = state.get("roster")
        if not isinstance(selected, dict) or not isinstance(roster, dict):
            logger.warning("Attacker/target state missing roster/selected sections.")
            return None

        def normalize_specs(section: dict[str, object], role: str) -> list[SerializedShipSpec] | None:
            entries = section.get(role)
            if not isinstance(entries, list):
                logger.warning("Attacker/target state %s list missing for role=%s.", section, role)
                return None
            normalized: list[SerializedShipSpec] = []
            for entry in entries:
                if not isinstance(entry, dict):
                    logger.warning("Ignoring non-dict %s entry: %s", role, entry)
                    continue
                normalized.append(deserialize_spec_dict(entry))
            return normalized

        selected_attackers = normalize_specs(selected, "attacker")
        selected_targets = normalize_specs(selected, "target")
        roster_attackers = normalize_specs(roster, "attacker")
        roster_targets = normalize_specs(roster, "target")
        if None in (selected_attackers, selected_targets, roster_attackers, roster_targets):
            logger.warning("Attacker/target state is incomplete; ignoring stored state.")
            return None
        return AttackerTargetSelection(
            attacker_roster=roster_attackers,
            target_roster=roster_targets,
            selected_attackers=selected_attackers,
            selected_targets=selected_targets,
        )

    def _persist_state(self, state: AttackerTargetSelection) -> None:
        """Persist attacker/target state as a JSON-friendly session object."""
        def serialize_specs(specs: Sequence[SerializedShipSpec]) -> list[dict[str, str]]:
            serialized: list[dict[str, str]] = []
            for spec_key in specs:
                spec = self._spec_lookup.get(spec_key)
                if spec is not None:
                    serialized.append(serialize_spec_dict(spec))
                else:
                    serialized.append(serialize_spec_key_dict(spec_key))
            return serialized

        attacker_target_state: AttackerTargetState = {
            "selected": {
                "attacker": serialize_specs(state.selected_attackers),
                "target": serialize_specs(state.selected_targets),
            },
            "roster": {
                "attacker": serialize_specs(state.attacker_roster),
                "target": serialize_specs(state.target_roster),
            },
        }

        previous_state = st.session_state.get(self.STATE_KEY)
        if previous_state != attacker_target_state:
            st.session_state[self.STATE_KEY] = attacker_target_state
            logger.debug(
                "Attacker/target state updated: %s",
                json.dumps(attacker_target_state, sort_keys=True),
            )

    def _resolve_rosters(
            self,
            stored_state: AttackerTargetSelection | None,
    ) -> tuple[list[SerializedShipSpec], list[SerializedShipSpec]]:
        """Resolve roster state using stored values or defaults."""
        if stored_state is None:
            logger.warning("No stored roster state; using defaults.")
            return self._default_rosters()
        attacker_roster = self._filter_roster(stored_state.attacker_roster, role="attacker")
        target_roster = self._filter_roster(stored_state.target_roster, role="target")
        if not attacker_roster and not target_roster:
            logger.warning("Stored rosters empty after filtering; using defaults.")
            return self._default_rosters()
        return self._normalize_rosters(attacker_roster, target_roster)

    def _default_rosters(self) -> tuple[list[SerializedShipSpec], list[SerializedShipSpec]]:
        """Return default rosters based on provided defaults."""
        if not self._default_attacker_specs and not self._default_target_specs:
            logger.warning("No default roster specs provided; using available specs.")
            default_target = list(self._available_specs[-1:])
            default_attacker = [spec for spec in self._available_specs if spec not in default_target]
            return list(default_attacker), list(default_target)
        return list(self._default_attacker_specs), list(self._default_target_specs)

    def _normalize_rosters(
            self,
            attacker_roster: list[SerializedShipSpec],
            target_roster: list[SerializedShipSpec],
    ) -> tuple[list[SerializedShipSpec], list[SerializedShipSpec]]:
        """Ensure rosters are disjoint and cover all available specs."""
        attacker_roster = self._dedupe_specs(attacker_roster)
        target_roster = [spec for spec in self._dedupe_specs(target_roster) if spec not in attacker_roster]
        missing_specs = [
            spec for spec in self._available_specs
            if spec not in attacker_roster and spec not in target_roster
        ]
        for spec in missing_specs:
            if spec in self._default_target_specs:
                target_roster.append(spec)
            else:
                attacker_roster.append(spec)
        if not target_roster:
            logger.warning("Target roster empty after normalization; using default target roster.")
            target_roster = list(self._default_target_specs or self._available_specs[-1:])
            attacker_roster = [spec for spec in self._available_specs if spec not in target_roster]
        if not attacker_roster:
            logger.warning("Attacker roster empty after normalization; using default attacker roster.")
            attacker_roster = list(self._default_attacker_specs or self._available_specs[:1])
            target_roster = [spec for spec in self._available_specs if spec not in attacker_roster]
        return attacker_roster, target_roster

    def _resolve_selected_specs(
            self,
            stored_specs: Sequence[SerializedShipSpec] | None,
            roster_specs: Sequence[SerializedShipSpec],
            *,
            role: str,
    ) -> list[SerializedShipSpec]:
        """Resolve stored selections against the current roster."""
        roster_list = list(roster_specs)
        if stored_specs is None:
            logger.warning("No stored %s selections; defaulting to roster.", role)
            return list(roster_list)
        if not stored_specs:
            logger.warning("Stored %s selections empty; defaulting to roster.", role)
            return list(roster_list)
        filtered = [spec for spec in self._dedupe_specs(stored_specs) if spec in self._spec_lookup]
        if len(filtered) < len(list(stored_specs)):
            logger.warning(
                "Dropping %s selections missing from current options: %s",
                role,
                [spec for spec in stored_specs if spec not in self._spec_lookup],
            )
        in_roster = [spec for spec in filtered if spec in roster_list]
        missing_in_roster = [spec for spec in filtered if spec not in roster_list]
        if missing_in_roster:
            logger.warning(
                "Dropping %s selections not in roster: %s",
                role,
                missing_in_roster,
            )
        if not in_roster:
            logger.warning("No %s selections remained; defaulting to roster.", role)
            return list(roster_list)
        return in_roster

    def _dedupe_specs(self, specs: Iterable[SerializedShipSpec]) -> list[SerializedShipSpec]:
        """Remove duplicate serialized specs while preserving order."""
        seen: set[SerializedShipSpec] = set()
        deduped: list[SerializedShipSpec] = []
        for spec in specs:
            if spec in seen:
                continue
            seen.add(spec)
            deduped.append(spec)
        return deduped

    def _filter_roster(
            self,
            roster: Iterable[SerializedShipSpec] | None,
            *,
            role: str,
    ) -> list[SerializedShipSpec]:
        """Filter a serialized roster to specs that still exist in the lookup."""
        if not roster:
            if self._spec_lookup:
                logger.warning("Roster filter received no %s specs while options exist; returning empty list.", role)
            return []
        deduped = self._dedupe_specs(roster)
        filtered = [spec for spec in deduped if spec in self._spec_lookup]
        if len(filtered) < len(deduped):
            dropped = [spec for spec in deduped if spec not in self._spec_lookup]
            logger.warning(
                "Dropped %d %s roster spec(s) missing from current ship options: %s",
                len(dropped),
                role,
                dropped,
            )
        return filtered


class AttackerAndTargetReport(AbstractReport):
    """Base report that adds attacker/target selection and lens filtering.

    This report adds a consistent header experience for combat logs:
    - Actor/target selectors with swap support.
    - Lens resolution based on current selections.
    - System/time/round metadata banner.
    - Helpers for filtering combat data to match the selections.

    Subclasses typically supply a lens key and then build charts/tables
    from data filtered via :meth:`apply_combat_lens`.
    """
    number_format: str | None = None

    def render_combat_log_header(
            self,
            players_df: pd.DataFrame | None,
            fleets_df: pd.DataFrame | None,
            battle_df: pd.DataFrame | None,
            *,
            lens_key: str,
            session_info: SessionInfo | Set[ShipSpecifier] | None = None,
    ) -> tuple[str, Lens | None]:
        """Render the standard header controls for combat-log reports.

        This resolves the number format, session info, and lens, then renders
        the actor/target selector and metadata header. Returns the chosen
        number format and lens for downstream chart/table logic.
        """
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
                # st.caption(f"Lens: {lens.label} ({attacker_name} → {target_name})")
            else:
                attacker_label = "Attacker ships" if len(selected_attackers) != 1 else "Attacker ship"
                target_label = "Target ships" if len(selected_targets) != 1 else "Target ship"
                # st.caption(f"Lens: {attacker_label} → {target_label}")

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

    def _render_system_time_and_rounds(
            self,
            players_df: pd.DataFrame,
            battle_df: pd.DataFrame | None,
    ) -> None:
        """Render the system/time/rounds banner for the report header."""
        context_lines = self._get_system_time_and_rounds(players_df, battle_df)
        if context_lines:
            context_text = " • ".join(context_lines)
            # FIXME: This, and about 10 lines down, is where system name, date, and time are written.
            st.markdown(
                "<div style='text-align:center; font-size:1.05rem; font-weight:600;'>"
                f"{context_text}</div>",
                unsafe_allow_html=True,
            )

    def _get_system_time_and_rounds(self, players_df: pd.DataFrame, battle_df: pd.DataFrame | None) -> list[str]:
        """Collect system name, timestamp, and round count from dataframes."""
        def resolve_metadata_value(
                df: pd.DataFrame,
                candidates: Sequence[str],
        ) -> tuple[str | None, object | None]:
            if df.empty:
                return None, None
            def first_non_empty(column: object) -> tuple[str, object | None]:
                series = df[column]
                non_null = series[series.notna()]
                if not non_null.empty:
                    trimmed = non_null.astype("string").str.strip()
                    non_null = non_null[trimmed != ""]
                if non_null.empty:
                    return str(column), pd.NA
                unique_values = non_null.drop_duplicates()
                if len(unique_values) > 1:
                    logger.warning(
                        "Multiple values found for %s in players df; using first non-empty entry.",
                        column,
                    )
                return str(column), unique_values.iloc[0]

            normalized_columns = {
                str(column).strip().lower(): column for column in df.columns
            }
            for candidate in candidates:
                column = normalized_columns.get(candidate.lower())
                if column is not None:
                    return first_non_empty(column)
            for column in df.columns:
                column_key = str(column).strip().lower()
                if any(candidate.lower() in column_key for candidate in candidates):
                    return first_non_empty(column)
            return None, None

        location_column, location = resolve_metadata_value(
            players_df,
            ("location", "system", "system name"),
        )
        timestamp_column, timestamp = resolve_metadata_value(
            players_df,
            ("timestamp", "date", "time", "date/time"),
        )
        if location_column is None:
            logger.warning("Players df missing location/system column for header context.")
        if timestamp_column is None:
            logger.warning("Players df missing timestamp/date column for header context.")
        if location_column and pd.isna(location):
            logger.warning("Players df location value missing for %s.", location_column)
        if timestamp_column and pd.isna(timestamp):
            logger.warning("Players df timestamp value missing for %s.", timestamp_column)
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
                    date_part = f"{date_part} {parsed_dt:%Y}"
                time_part = f"{parsed_dt:%H:%M}"
                context_parts.append(f"on {date_part} at {time_part}")
            else:
                context_parts.append(str(timestamp))
        if context_parts:
            lines.append(" ".join(context_parts))

        if isinstance(battle_df, pd.DataFrame) and not battle_df.empty and "round" in battle_df.columns:
            rounds = pd.to_numeric(battle_df["round"], errors="coerce")
            valid_rounds = rounds.dropna()
            if not valid_rounds.empty:
                min_round = valid_rounds.min()
                max_round = valid_rounds.max()
                if pd.notna(min_round) and pd.notna(max_round):
                    round_count = int(max_round)
                    if min_round == 0:
                        round_count = int(max_round) + 1
                        logger.warning(
                            "Round data appears zero-indexed; displaying %s rounds based on max round %s.",
                            round_count,
                            max_round,
                        )
                    lines.append(f"Battle Rounds: {round_count}")
        return lines

    def render_combatants(
            self,
            session_info: SessionInfo | Set[ShipSpecifier] | None,
            battle_df: pd.DataFrame | None,
    ) -> None:
        """Render a two-column list of player and NPC combatants."""
        if not isinstance(session_info, SessionInfo) and isinstance(battle_df, pd.DataFrame):
            session_info = SessionInfo(battle_df)

        combatant_specs = self._normalize_specs(session_info)
        if not combatant_specs:
            logger.warning("No combatant specs available to render combatants list.")
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
            outcome_lookup = session_info.build_outcome_lookup()

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
        """Render a bullet list of combatants with optional outcome emojis."""
        st.markdown(f"**{title}**")
        if not specs:
            logger.warning("No combatant specs available for %s list.", title)
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
        """Filter combat data using the selected attacker specs and targets.

        The filter uses SessionInfo indices when available, otherwise falls back
        to matching attacker/target names against resolved columns.
        """
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
        """Return the lens key used to resolve lens metadata for this report."""
        pass

    def render_header(self, df: pd.DataFrame) -> Lens | None:
        """Render the combat-log header and persist the number format."""
        players_df = df.attrs.get("players_df")
        fleets_df = df.attrs.get("fleets_df")
        number_format, lens = self.render_combat_log_header(
            players_df,
            fleets_df,
            df,
            lens_key=self.get_lens_key(),
        )
        self.number_format = number_format
        return lens


    @staticmethod
    def _normalize_specs(session_info: SessionInfo | Set[ShipSpecifier] | None) -> Sequence[ShipSpecifier]:
        """Return a sorted list of ship specs from session info or a set."""
        if isinstance(session_info, SessionInfo):
            specs = session_info.get_every_ship()
        elif isinstance(session_info, set):
            specs = session_info
        else:
            specs = set()

        return sorted(specs, key=lambda spec: str(spec))

    def _resolve_player_alliance(self, row: pd.Series) -> str:
        """Extract a normalized alliance string from a player metadata row."""
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
        """Match the local player spec from players_df to a ship option."""
        if not isinstance(players_df, pd.DataFrame) or players_df.empty:
            logger.warning("Unable to infer enemy spec: players_df missing or empty.")
            return None
        row = players_df.iloc[-1]
        name = self._normalize_text(row.get("Player Name"))
        alliance = self._resolve_player_alliance(row)
        ship = self._normalize_text(row.get("Ship Name"))
        if not any([name, alliance, ship]):
            logger.warning("Unable to infer enemy spec: missing name/alliance/ship values.")
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
    ) -> list[ShipSpecifier]:
        """Determine a default target selection from player metadata."""
        matched = self._match_enemy_spec(players_df, options)
        if matched is not None:
            return [matched]
        if options:
            return [options[-1]]
        logger.warning("Unable to determine default target; no ship options provided.")
        return []

    def _build_default_attacker_target_defaults(
            self,
            players_df: pd.DataFrame | None,
            options: Sequence[ShipSpecifier],
    ) -> tuple[list[SerializedShipSpec], list[SerializedShipSpec]]:
        """Build default attacker/target selections for state initialization."""
        target_fallback = self._default_target_from_players(players_df, options)
        if not target_fallback:
            target_fallback = list(options[-1:])
        attacker_fallback = [spec for spec in options if spec not in target_fallback]
        if not attacker_fallback:
            attacker_fallback = list(options[:1])
        default_attacker_specs = [serialize_spec(spec) for spec in attacker_fallback]
        default_target_specs = [serialize_spec(spec) for spec in target_fallback]
        logger.debug(
            "Default attacker specs=%s; target specs=%s.",
            default_attacker_specs,
            default_target_specs,
        )
        return default_attacker_specs, default_target_specs


    def render_actor_target_selector(
            self,
            session_info: SessionInfo | Set[ShipSpecifier] | None,
            players_df: pd.DataFrame | None,
    ) -> tuple[Sequence[ShipSpecifier], Sequence[ShipSpecifier]]:
        """Render the attacker/target selection widgets and return selections."""
        options = self._normalize_specs(session_info)
        if not options:
            logger.warning(
                "Actor/target selector has no ship options; session_info=%s.",
                type(session_info).__name__,
            )
            st.warning("No ship data available to select attacker/target.")
            return (), ()

        spec_lookup = {serialize_spec(spec): spec for spec in options}
        available_specs = [serialize_spec(spec) for spec in options]
        default_attacker_specs, default_target_specs = self._build_default_attacker_target_defaults(
            players_df,
            options,
        )
        outcome_lookup = (
            session_info.build_outcome_lookup()
            if isinstance(session_info, SessionInfo)
            else {}
        )
        manager = AttackerTargetStateManager(
            spec_lookup=spec_lookup,
            available_specs=available_specs,
            default_attacker_specs=default_attacker_specs,
            default_target_specs=default_target_specs,
            label_builder=self._format_ship_spec_label,
            outcome_lookup=outcome_lookup,
        )
        roster_state = manager.resolve_state()

        st.markdown(
            """
<style>
  /* scope to just this wrapper */
  .attacker-target-swap {
    width: 110px !important;
    height: 100% !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
  }

  /* Streamlit button wrapper(s) */
  .attacker-target-swap .stButton,
  .attacker-target-swap .stButton > div {
    width: 105px !important;
    height: 105px !important;
    flex: 0 0 105px !important;
  }

  /* the actual clickable button */
  .attacker-target-swap .stButton > button {
    width: 100px !important;
    height: 100px !important;
    min-width: 100px !important;
    max-width: 100px !important;
    min-height: 100px !important;
    max-height: 100px !important;

    padding: 0 !important;
    line-height: 1 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
  }

  /* make the emoji/text scale nicely (optional) */
  .attacker-target-swap .stButton > button p {
    margin: 0 !important;
    font-size: 64px !important; /* adjust */
  }
</style>
            """,
            unsafe_allow_html=True,
        )
        selector_left, selector_swap, selector_right = st.columns([7, 3, 7])
        with selector_left:
            selected_attacker_specs = manager.render_role_panel(
                title="Attackers",
                roster_specs=roster_state.attacker_roster,
                selected_specs=roster_state.selected_attackers,
                role="attacker",
                key_prefix="attacker_include",
            )
        with selector_swap:
            st.markdown("<div class='attacker-target-swap'>", unsafe_allow_html=True)
            st.button(
                "🔄\nSwap",
                help="Swap attacker/target selections.",
                key="swap_attacker_target_specs",
                on_click=manager.swap,
                # width=125,
            )
            st.markdown("</div>", unsafe_allow_html=True)
        with selector_right:
            selected_target_specs = manager.render_role_panel(
                title="Targets",
                roster_specs=roster_state.target_roster,
                selected_specs=roster_state.selected_targets,
                role="target",
                key_prefix="target_include",
            )
        updated_state = manager.update_from_render(
            roster_state=roster_state,
            selected_attackers=selected_attacker_specs,
            selected_targets=selected_target_specs,
        )
        selected_attackers = manager.resolve_ship_specs(updated_state.selected_attackers)
        selected_targets = manager.resolve_ship_specs(updated_state.selected_targets)
        return selected_attackers, selected_targets

    def _resolve_selected_specs_from_state(
            self,
            session_info: SessionInfo | Set[ShipSpecifier] | None,
    ) -> tuple[list[ShipSpecifier], list[ShipSpecifier]]:
        """Resolve selected specs from session state into ShipSpecifier lists."""
        options = self._normalize_specs(session_info)
        if not options:
            return [], []
        spec_lookup = {serialize_spec(spec): spec for spec in options}
        available_specs = [serialize_spec(spec) for spec in options]
        default_attacker_specs, default_target_specs = self._build_default_attacker_target_defaults(
            None,
            options,
        )
        manager = AttackerTargetStateManager(
            spec_lookup=spec_lookup,
            available_specs=available_specs,
            default_attacker_specs=default_attacker_specs,
            default_target_specs=default_target_specs,
        )
        resolved_state = manager.resolve_state()
        return (
            manager.resolve_ship_specs(resolved_state.selected_attackers),
            manager.resolve_ship_specs(resolved_state.selected_targets),
        )

    def _build_outcome_lookup(
            self,
            session_info: SessionInfo | None,
            battle_df: pd.DataFrame | None,
    ) -> dict[SerializedShipSpec, object]:
        """Build a lookup of ship outcome status for labeling."""
        if isinstance(session_info, SessionInfo):
            return session_info.build_outcome_lookup()
        if isinstance(battle_df, pd.DataFrame):
            return SessionInfo(battle_df).build_outcome_lookup()
        logger.warning("Outcome lookup unavailable: missing session info and battle df.")
        return {}

    @staticmethod
    def _outcome_emoji(outcome: object) -> str:
        """Convert an outcome value into a display emoji."""
        return SessionInfo.outcome_emoji(outcome)

    @staticmethod
    def _normalize_text(value: object) -> str:
        """Normalize arbitrary values into trimmed strings for comparison."""
        if pd.isna(value) or value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _normalize_spec_key(name: object, alliance: object, ship: object) -> SerializedShipSpec:
        """Normalize and serialize key fields into a ShipSpecifier key."""
        return SessionInfo.normalize_spec_key(name, alliance, ship)

    def _format_combatant_label(
            self,
            row: pd.Series,
            name_lookup: dict[str, str],
            ship_lookup: dict[tuple[str, str], str],
    ) -> str:
        """Build a display label for a combatant row."""
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
        """Build a display label for a ship spec, including outcome emoji."""
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
