from __future__ import annotations

import logging
from abc import abstractmethod
from datetime import datetime
from typing import Iterable, Sequence, Set, TypedDict

import pandas as pd
import streamlit as st

from veschov.io.SessionInfo import SessionInfo, ShipSpecifier
from veschov.transforms.columns import ATTACKER_COLUMN_CANDIDATES, TARGET_COLUMN_CANDIDATES, resolve_column
from veschov.ui.chirality import Lens, resolve_lens
from veschov.ui.components.number_format import get_number_format
from veschov.ui.object_reports.AbstractReport import AbstractReport
from veschov.ui.object_reports.rosters.AttackerTargetStateManager import serialize_spec, AttackerTargetStateManager

SerializedShipSpec = tuple[str, str, str]


class AttackerTargetStateMeta(TypedDict):
    """Metadata stored alongside attacker/target selection state."""
    version: int
    origin: str
    last_source: str
    selection_hash: str
    selection_version: int


class AttackerTargetStateSection(TypedDict):
    """Selected or roster entries for attacker/target state."""
    attacker: list[dict[str, str]]
    target: list[dict[str, str]]


class AttackerTargetStatePayload(TypedDict):
    """Full attacker/target selection state payload."""
    selected: AttackerTargetStateSection
    roster: AttackerTargetStateSection
    meta: AttackerTargetStateMeta


AttackerTargetState = AttackerTargetStatePayload
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
        logger.debug(
            "Actor/target selections resolved: attackers=%d targets=%d lens_key=%s.",
            len(selected_attackers),
            len(selected_targets),
            lens_key,
        )
        if st.session_state.get("debug_attacker_target_state"):
            st.sidebar.expander("Debug: Attacker/Target State", expanded=False).json(
                st.session_state.get(AttackerTargetStateManager.STATE_KEY),
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
            spec for spec in combatant_specs if spec.normalized_alliance()
        ]
        npc_specs = [
            spec for spec in combatant_specs if not spec.normalized_alliance()
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
            logger.warning("Making empty set for specs.")
            specs = set()

        return sorted(specs, key=lambda spec: str(spec))

    def _resolve_player_alliance(self, row: pd.Series) -> str:
        """Extract a normalized alliance string from a player metadata row."""
        for column in ("Alliance", "Player Alliance"):
            if column in row.index:
                alliance = ShipSpecifier.normalize_text(row.get(column))
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
        name = ShipSpecifier.normalize_text(row.get("Player Name"))
        alliance = self._resolve_player_alliance(row)
        ship = ShipSpecifier.normalize_text(row.get("Ship Name"))
        if not any([name, alliance, ship]):
            logger.warning("Unable to infer enemy spec: missing name/alliance/ship values.")
            return None

        for spec in options:
            if spec.matches_normalized(name, alliance, ship):
                return spec
        return None

    def _default_target_from_players(
            self,
            players_df: pd.DataFrame | None,
            options: Sequence[ShipSpecifier],
    ) -> tuple[list[ShipSpecifier], str]:
        """Determine a default target selection from player metadata."""
        # FIX12: players_df should not be empty
        if not isinstance(players_df, pd.DataFrame) or players_df.empty:
            logger.warning("Player metadata missing; unable to infer default target selection.")
            return [], "missing player metadata"
        matched = self._match_enemy_spec(players_df, options)
        if matched is not None:
            return [matched], "player metadata match"
        if options:
            return [options[-1]], "fallback to last option"
        logger.warning("Unable to determine default target; no ship options provided.")
        return [], "no ship options"

    def _build_default_attacker_target_defaults(
            self,
            players_df: pd.DataFrame | None,
            options: Sequence[ShipSpecifier],
    ) -> tuple[list[SerializedShipSpec], list[SerializedShipSpec]]:
        """Build default attacker/target selections for state initialization."""
        # FIX12 players_df should not be empty
        target_fallback, target_reason = self._default_target_from_players(players_df, options)
        if not target_fallback:
            target_fallback = list(options[-1:])
            target_reason = target_reason if target_fallback else "no options for fallback"
        attacker_fallback = [spec for spec in options if spec not in target_fallback]
        if not attacker_fallback:
            attacker_fallback = list(options[:1])
            if not target_fallback:
                target_fallback = list(options[-1:])
            target_reason = target_reason if target_reason else "forced fallback to first option"
        default_attacker_specs = [serialize_spec(spec) for spec in attacker_fallback]
        default_target_specs = [serialize_spec(spec) for spec in target_fallback]
        logger.debug(
            "Default attacker specs=%s; target specs=%s (reason=%s).",
            default_attacker_specs,
            default_target_specs,
            target_reason,
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
        missing_in_lookup = [spec for spec in available_specs if spec not in spec_lookup]
        if missing_in_lookup:
            logger.warning(
                "Available specs missing from lookup during selector render: %s",
                missing_in_lookup,
            )
        # FIX12 players_df should not be empty
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
            strict_mode=bool(st.session_state.get("attacker_target_strict_mode")),
        )
        roster_state = manager.resolve_state(origin="defaults")

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
        manager.clear_refresh()
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
        players_df = session_info.players_df if isinstance(session_info, SessionInfo) else None
        spec_lookup = {serialize_spec(spec): spec for spec in options}
        available_specs = [serialize_spec(spec) for spec in options]
        # FIX12 players_df should not be empty
        # Missing player metadata can reset selections; guard against it.
        default_attacker_specs, default_target_specs = self._build_default_attacker_target_defaults(
            players_df,
            options,
        )
        manager = AttackerTargetStateManager(
            spec_lookup=spec_lookup,
            available_specs=available_specs,
            default_attacker_specs=default_attacker_specs,
            default_target_specs=default_target_specs,
            strict_mode=bool(st.session_state.get("attacker_target_strict_mode")),
        )
        if players_df is None or players_df.empty:
            stored_state = manager.peek_state()
            logger.warning(
                "Player metadata missing for selection resolution (players_df=%s).",
                "none" if players_df is None else "empty",
            )
            if stored_state is not None:
                logger.warning(
                    "Player metadata missing; using stored attacker/target selections without defaults.",
                )
                return (
                    manager.resolve_ship_specs(stored_state.selected_attackers),
                    manager.resolve_ship_specs(stored_state.selected_targets),
                )
            logger.warning(
                "Player metadata missing and no stored state found; preserving empty selections.",
            )
            return [], []
        resolved_state = manager.resolve_state(origin="defaults")
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
    def _format_combatant_label(
            self,
            row: pd.Series,
            name_lookup: dict[str, str],
            ship_lookup: dict[tuple[str, str], str],
    ) -> str:
        """Build a display label for a combatant row."""
        name = ShipSpecifier.normalize_text(row.get("Player Name"))
        ship = ShipSpecifier.normalize_text(row.get("Ship Name"))
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
        return spec.format_label_with_outcome_lookup(outcome_lookup)
