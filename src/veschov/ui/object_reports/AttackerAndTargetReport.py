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
from veschov.ui.components.number_format import get_number_format
from veschov.ui.object_reports.AbstractReport import AbstractReport

SerializedShipSpec = tuple[str, str, str]
logger = logging.getLogger(__name__)


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
            normalized_columns = {
                str(column).strip().lower(): column for column in df.columns
            }
            for candidate in candidates:
                column = normalized_columns.get(candidate.lower())
                if column is not None:
                    return column, df[column].iloc[0]
            for column in df.columns:
                column_key = str(column).strip().lower()
                if any(candidate.lower() in column_key for candidate in candidates):
                    return column, df[column].iloc[0]
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
                    date_part = f"{date_part} [{parsed_dt:%Y}]"
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
    def _serialize_spec(spec: ShipSpecifier) -> SerializedShipSpec:
        """Serialize a ShipSpecifier into a stable tuple for session storage."""
        return (spec.name or "", spec.alliance or "", spec.ship or "")

    @staticmethod
    def _swap_selected_specs() -> None:
        """Swap the attacker and target selection state."""
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
            if spec_lookup:
                logger.warning("Roster filter received no specs while options exist; returning empty list.")
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

    @classmethod
    def _log_filtered_selection(
            cls,
            role: str,
            stored_specs: Iterable[SerializedShipSpec] | None,
            selected_specs: Sequence[SerializedShipSpec],
            *,
            spec_lookup: dict[SerializedShipSpec, ShipSpecifier],
            roster_specs: Sequence[SerializedShipSpec],
            checkbox_prefix: str,
    ) -> None:
        """Log why stored selections were filtered out."""
        checkbox_key_prefix = f"{checkbox_prefix}_"
        checkbox_count = sum(
            1 for key in st.session_state.keys()
            if isinstance(key, str) and key.startswith(checkbox_key_prefix)
        )
        if stored_specs is None:
            if not selected_specs and roster_specs:
                logger.warning(
                    "No stored %s selections in session state; defaulting to roster defaults. "
                    "(options=%d, roster=%d, checkbox_keys=%d)",
                    role,
                    len(spec_lookup),
                    len(roster_specs),
                    checkbox_count,
                )
            return
        if not stored_specs:
            if not selected_specs and roster_specs:
                logger.warning(
                    "Stored %s selections are empty; defaulting to roster defaults. "
                    "(options=%d, roster=%d, checkbox_keys=%d)",
                    role,
                    len(spec_lookup),
                    len(roster_specs),
                    checkbox_count,
                )
            return
        deduped = cls._dedupe_specs(stored_specs)
        missing_in_options = [spec for spec in deduped if spec not in spec_lookup]
        missing_in_roster = [
            spec for spec in deduped
            if spec in spec_lookup and spec not in roster_specs
        ]
        if not missing_in_options and not missing_in_roster and len(deduped) == len(selected_specs):
            return
        if missing_in_options:
            logger.warning(
                "Stored %s selections dropped because they are missing from current ship options: %s "
                "(options=%d, roster=%d, checkbox_keys=%d)",
                role,
                missing_in_options,
                len(spec_lookup),
                len(roster_specs),
                checkbox_count,
            )
        if missing_in_roster:
            logger.warning(
                "Stored %s selections dropped because they are not in the current roster: %s "
                "(options=%d, roster=%d, checkbox_keys=%d)",
                role,
                missing_in_roster,
                len(spec_lookup),
                len(roster_specs),
                checkbox_count,
            )
        if len(deduped) > len(selected_specs) and not missing_in_options and not missing_in_roster:
            logger.warning(
                "Stored %s selections contained duplicates; reduced to %s. "
                "(options=%d, roster=%d, checkbox_keys=%d)",
                role,
                selected_specs,
                len(spec_lookup),
                len(roster_specs),
                checkbox_count,
            )

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
            checkbox_key = f"{key_prefix}_{spec_key}"
            desired_value = spec_key in selected_specs
            if checkbox_key not in st.session_state:
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
        """Render the attacker/target selection widgets and return selections."""
        options = self._normalize_specs(session_info)
        if not options:
            logger.warning(
                "Actor/target selector has no ship options; session_info=%s.",
                type(session_info).__name__,
            )
            st.warning("No ship data available to select attacker/target.")
            return (), ()

        spec_lookup = {self._serialize_spec(spec): spec for spec in options}
        available_specs = [self._serialize_spec(spec) for spec in options]
        target_fallback = self._default_target_from_players(players_df, options)
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

        stored_attacker_specs = st.session_state.get("selected_attacker_specs") or list(attacker_roster_specs)
        stored_target_specs = st.session_state.get("selected_target_specs") or list(target_roster_specs)
        st.session_state["selected_attacker_specs"] = list(stored_attacker_specs)
        st.session_state["selected_target_specs"] = list(stored_target_specs)
        selected_attacker_specs = self._filter_roster(
            stored_attacker_specs,
            spec_lookup,
        )
        selected_target_specs = self._filter_roster(
            stored_target_specs,
            spec_lookup,
        )
        initial_attacker_specs = list(selected_attacker_specs)
        initial_target_specs = list(selected_target_specs)
        self._log_filtered_selection(
            "attacker",
            stored_attacker_specs,
            selected_attacker_specs,
            spec_lookup=spec_lookup,
            roster_specs=attacker_roster_specs,
            checkbox_prefix="attacker_include",
        )
        self._log_filtered_selection(
            "target",
            stored_target_specs,
            selected_target_specs,
            spec_lookup=spec_lookup,
            roster_specs=target_roster_specs,
            checkbox_prefix="target_include",
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
        if (
            initial_attacker_specs != list(selected_attacker_specs)
            or initial_target_specs != list(selected_target_specs)
        ):
            st.session_state["selected_attacker_specs"] = list(selected_attacker_specs)
            st.session_state["selected_target_specs"] = list(selected_target_specs)

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
        outcome_lookup = (
            session_info.build_outcome_lookup()
            if isinstance(session_info, SessionInfo)
            else {}
        )
        selector_left, selector_swap, selector_right = st.columns([7, 3, 7])
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
            st.markdown("<div class='attacker-target-swap'>", unsafe_allow_html=True)
            st.button(
                "🔄\nSwap",
                help="Swap attacker/target selections.",
                key="swap_attacker_target_specs",
                on_click=self._swap_selected_specs,
                # width=125,
            )
            st.markdown("</div>", unsafe_allow_html=True)
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

    def _resolve_selected_specs_from_state(
            self,
            session_info: SessionInfo | Set[ShipSpecifier] | None,
    ) -> tuple[list[ShipSpecifier], list[ShipSpecifier]]:
        """Resolve selected specs from session state into ShipSpecifier lists."""
        options = self._normalize_specs(session_info)
        if not options:
            return [], []
        spec_lookup = {self._serialize_spec(spec): spec for spec in options}
        attacker_specs = st.session_state.get("selected_attacker_specs", [])
        target_specs = st.session_state.get("selected_target_specs", [])
        selected_attackers = [spec_lookup[item] for item in attacker_specs if item in spec_lookup]
        selected_targets = [spec_lookup[item] for item in target_specs if item in spec_lookup]
        return selected_attackers, selected_targets

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

    def _outcome_emoji(self, outcome: object) -> str:
        """Convert an outcome value into a display emoji."""
        return SessionInfo.outcome_emoji(outcome)

    def _normalize_text(self, value: object) -> str:
        """Normalize arbitrary values into trimmed strings for comparison."""
        if pd.isna(value) or value is None:
            return ""
        return str(value).strip()

    def _normalize_spec_key(self, name: object, alliance: object, ship: object) -> SerializedShipSpec:
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
