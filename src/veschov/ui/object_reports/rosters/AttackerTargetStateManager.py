from __future__ import annotations

import json
import logging
from typing import Iterable, Sequence, Callable

import streamlit as st
from typing import TYPE_CHECKING
from veschov.ui.object_reports.rosters.AttackerTargetSelection import AttackerTargetSelection
from veschov.io.SessionInfo import SessionInfo

if TYPE_CHECKING:
    from veschov.io.SessionInfo import ShipSpecifier
    from veschov.ui.object_reports.AttackerAndTargetReport import SerializedShipSpec, AttackerTargetState
    from veschov.ui.object_reports.AttackerAndTargetReport import SerializedShipSpec

logger = logging.getLogger(__name__)

def serialize_spec(spec: ShipSpecifier) -> SerializedShipSpec:
    """Serialize a ShipSpecifier into a stable tuple for session storage."""
    return SessionInfo.normalize_spec_key(spec.name, spec.alliance, spec.ship)


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

class AttackerTargetStateManager:
    """Encapsulate attacker/target state stored in Streamlit session_state."""
    STATE_KEY = "attacker_target_state"
    REFRESH_KEY = "attacker_target_state_refresh"

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

    def peek_state(self) -> AttackerTargetSelection | None:
        """Return stored attacker/target state without applying defaults."""
        logger.debug("Peeking attacker/target state without resolving defaults.")
        return self._load_state()

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
            logger.warning(f"No roster specs available for {title} selection, key = {key_prefix}.")
            st.caption("None listed in the current log.")
            return []
        resolved: list[SerializedShipSpec] = []
        selected_set = set(selected_specs)
        refresh_requested = st.session_state.get(self.REFRESH_KEY, False)
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
            if refresh_requested or checkbox_key not in st.session_state:
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
        self.request_refresh()

    def request_refresh(self) -> None:
        """Request a checkbox refresh from stored selections."""
        st.session_state[self.REFRESH_KEY] = True
        logger.debug(f"Attacker/target checkbox refresh requested. Key = {self.REFRESH_KEY}")

    def clear_refresh(self) -> None:
        """Clear any pending checkbox refresh request."""
        if st.session_state.pop(self.REFRESH_KEY, None) is not None:
            logger.debug(f"Attacker/target checkbox refresh cleared. Key = {self.REFRESH_KEY}")

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
