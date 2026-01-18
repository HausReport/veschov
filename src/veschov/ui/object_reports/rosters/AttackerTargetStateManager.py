from __future__ import annotations

import hashlib
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

logger = logging.getLogger(__name__)

def serialize_spec(spec: ShipSpecifier) -> SerializedShipSpec:
    """Serialize a ShipSpecifier into a stable tuple for session storage."""
    return SessionInfo.normalize_spec_key(
        (spec.name or "").strip(),
        (spec.alliance or "").strip(),
        (spec.ship or "").strip(),
    )


def serialize_spec_dict(spec: ShipSpecifier) -> dict[str, str]:
    """Serialize a ShipSpecifier into a JSON-friendly mapping."""
    return {
        "name": (spec.name or "").strip(),
        "alliance": (spec.alliance or "").strip(),
        "ship": (spec.ship or "").strip(),
    }


def deserialize_spec_dict(spec: dict[str, str]) -> SerializedShipSpec:
    """Deserialize a JSON-friendly mapping into a spec key."""
    missing_keys = [key for key in ("name", "alliance", "ship") if key not in spec]
    if missing_keys:
        logger.warning("Spec dict missing keys %s; using empty strings.", missing_keys)
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
    STATE_VERSION = 1

    def __init__(
            self,
            *,
            spec_lookup: dict[SerializedShipSpec, ShipSpecifier],
            available_specs: Sequence[SerializedShipSpec],
            default_attacker_specs: Sequence[SerializedShipSpec],
            default_target_specs: Sequence[SerializedShipSpec],
            label_builder: Callable[[ShipSpecifier, dict[SerializedShipSpec, object] | None], str] | None = None,
            outcome_lookup: dict[SerializedShipSpec, object] | None = None,
            strict_mode: bool = False,
    ) -> None:
        self._spec_lookup = spec_lookup
        self._available_specs = list(available_specs)
        self._default_attacker_specs = list(default_attacker_specs)
        self._default_target_specs = list(default_target_specs)
        self._label_builder = label_builder
        self._outcome_lookup = outcome_lookup or {}
        self._strict_mode = strict_mode

    def resolve_state(self, *, origin: str = "defaults") -> AttackerTargetSelection:
        """Resolve and persist the current attacker/target state."""
        logger.debug(
            "Resolving attacker/target state (options=%d, defaults=attacker:%d target:%d).",
            len(self._available_specs),
            len(self._default_attacker_specs),
            len(self._default_target_specs),
        )
        if not self._available_specs:
            logger.warning("No available specs provided; returning empty attacker/target state.")
            resolved_state = AttackerTargetSelection(
                attacker_roster=[],
                target_roster=[],
                selected_attackers=[],
                selected_targets=[],
            )
            self._persist_state(resolved_state, origin=origin)
            return resolved_state
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
        self._persist_state(resolved_state, origin=origin)
        logger.debug(
            "Resolved attacker/target state: roster(attacker=%d target=%d) selections(attacker=%d target=%d).",
            len(resolved_state.attacker_roster),
            len(resolved_state.target_roster),
            len(resolved_state.selected_attackers),
            len(resolved_state.selected_targets),
        )
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
        if self._strict_mode and self._spec_lookup:
            missing_attackers = [spec for spec in selected_attackers if spec not in self._spec_lookup]
            missing_targets = [spec for spec in selected_targets if spec not in self._spec_lookup]
            if missing_attackers or missing_targets:
                logger.error(
                    "Strict mode: missing selected specs attackers=%s targets=%s.",
                    missing_attackers,
                    missing_targets,
                )
                raise ValueError("Selected specs missing from lookup in strict mode.")
        updated_state = AttackerTargetSelection(
            attacker_roster=list(roster_state.attacker_roster),
            target_roster=list(roster_state.target_roster),
            selected_attackers=list(selected_attackers),
            selected_targets=list(selected_targets),
        )
        self._persist_state(updated_state, origin="user", update_roster=False, update_selected=True)
        return updated_state

    def swap(self) -> None:
        """Swap attacker/target roster and selection state."""
        current_state = self.resolve_state(origin="swap")
        logger.debug(
            "Pre-swap state: roster(attacker=%d target=%d) selections(attacker=%d target=%d).",
            len(current_state.attacker_roster),
            len(current_state.target_roster),
            len(current_state.selected_attackers),
            len(current_state.selected_targets),
        )
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
        self._persist_state(swapped_state, origin="swap")
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
        missing_specs = [item for item in selected_specs if item not in self._spec_lookup]
        if missing_specs:
            logger.warning("Selected specs missing from lookup: %s", missing_specs)
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
        meta = state.get("meta")
        if meta is not None:
            if not isinstance(meta, dict):
                logger.warning("Attacker/target state metadata has unexpected type: %s", type(meta).__name__)
            else:
                version = meta.get("version")
                origin = meta.get("origin")
                logger.debug(
                    "Loaded attacker/target state metadata version=%s origin=%s.",
                    version,
                    origin,
                )
                if version != self.STATE_VERSION:
                    logger.warning(
                        "Attacker/target state version mismatch: expected=%s found=%s.",
                        self.STATE_VERSION,
                        version,
                    )
                    return None
        else:
            logger.warning("Attacker/target state missing metadata; ignoring stored state.")
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

    def _persist_state(
            self,
            state: AttackerTargetSelection,
            *,
            origin: str,
            update_roster: bool = True,
            update_selected: bool = True,
    ) -> None:
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

        previous_state = st.session_state.get(self.STATE_KEY)
        previous_selected = None
        previous_roster = None
        previous_meta = None
        if isinstance(previous_state, dict):
            previous_selected = previous_state.get("selected")
            previous_roster = previous_state.get("roster")
            previous_meta = previous_state.get("meta")

        selected_payload = {
            "attacker": serialize_specs(state.selected_attackers),
            "target": serialize_specs(state.selected_targets),
        }
        roster_payload = {
            "attacker": serialize_specs(state.attacker_roster),
            "target": serialize_specs(state.target_roster),
        }

        if not update_selected and isinstance(previous_selected, dict):
            selected_payload = previous_selected
        if not update_roster and isinstance(previous_roster, dict):
            roster_payload = previous_roster

        selection_hash = self._selection_hash(selected_payload)
        attacker_target_state: AttackerTargetState = {
            "selected": selected_payload,
            "roster": roster_payload,
            "meta": {
                "version": self.STATE_VERSION,
                "origin": origin,
                "selection_hash": selection_hash,
            },
        }

        if previous_state != attacker_target_state:
            st.session_state[self.STATE_KEY] = attacker_target_state
            if isinstance(previous_meta, dict):
                previous_hash = previous_meta.get("selection_hash")
                if previous_hash and previous_hash != selection_hash and origin not in ("user", "swap"):
                    logger.warning(
                        "Selection hash changed without user action (origin=%s, prior=%s, current=%s).",
                        origin,
                        previous_hash,
                        selection_hash,
                    )
            logger.debug(
                "Attacker/target state updated: %s",
                json.dumps(attacker_target_state, sort_keys=True),
            )
        else:
            logger.debug("Attacker/target state unchanged; skipping session update.")

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
            if self._strict_mode and self._spec_lookup:
                logger.error("Strict mode: rosters empty after filtering stored state.")
                raise ValueError("Roster resolution failed in strict mode.")
            return self._default_rosters()
        logger.debug(
            "Resolved rosters attacker=%d target=%d after filtering.",
            len(attacker_roster),
            len(target_roster),
        )
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
        deduped_target = self._dedupe_specs(target_roster)
        overlap = [spec for spec in deduped_target if spec in attacker_roster]
        if overlap:
            logger.warning(
                "Roster overlap detected; removing from target roster: %s",
                overlap,
            )
        target_roster = [spec for spec in deduped_target if spec not in attacker_roster]
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
            available_specs = list(self._spec_lookup.keys())
            available_labels = self._describe_available_specs()
            logger.warning(
                "Dropping %s selections missing from current options: %s",
                role,
                [spec for spec in stored_specs if spec not in self._spec_lookup],
            )
            logger.warning(
                "Available %s spec keys: %s",
                role,
                available_specs,
            )
            logger.warning(
                "Available %s spec labels: %s",
                role,
                available_labels,
            )
            if self._strict_mode:
                raise ValueError(f"Stored {role} selections missing from lookup in strict mode.")
        in_roster = [spec for spec in filtered if spec in roster_list]
        missing_in_roster = [spec for spec in filtered if spec not in roster_list]
        if missing_in_roster:
            logger.warning(
                "Dropping %s selections not in roster: %s",
                role,
                missing_in_roster,
            )
            logger.warning(
                "Roster %s spec keys: %s",
                role,
                roster_list,
            )
            if self._strict_mode:
                raise ValueError(f"Stored {role} selections missing from roster in strict mode.")
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
            available_labels = self._describe_available_specs()
            logger.warning(
                "Dropped %d %s roster spec(s) missing from current ship options: %s",
                len(dropped),
                role,
                dropped,
            )
            logger.warning(
                "Available %s spec keys: %s",
                role,
                list(self._spec_lookup.keys()),
            )
            logger.warning(
                "Available %s spec labels: %s",
                role,
                available_labels,
            )
            if self._strict_mode:
                logger.error("Strict mode: roster specs missing from lookup for %s.", role)
                raise ValueError("Roster specs missing from lookup in strict mode.")
        return filtered

    def _describe_available_specs(self) -> list[str]:
        """Return readable labels for the current spec lookup."""
        labels: list[str] = []
        for spec in self._spec_lookup.values():
            name = (spec.name or "").strip() or "Unknown"
            alliance = (spec.alliance or "").strip()
            ship = (spec.ship or "").strip()
            label = name
            if alliance:
                label = f"{label} [{alliance}]"
            if ship and ship != name:
                label = f"{label} — {ship}"
            labels.append(label)
        return labels

    @staticmethod
    def _selection_hash(selected_payload: dict[str, list[dict[str, str]]]) -> str:
        """Compute a stable hash for selected specs."""
        payload = json.dumps(selected_payload, sort_keys=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
