"""Reusable attacker/target selector for report pages."""

from __future__ import annotations

import logging

from veschov.io.SessionInfo import ShipSpecifier, SessionInfo

logger = logging.getLogger(__name__)

from typing import Iterable, Sequence, Set

import streamlit as st

SerializedShipSpec = tuple[str, str, str]


def _serialize_spec(spec: ShipSpecifier) -> SerializedShipSpec:
    return (spec.name or "", spec.alliance or "", spec.ship or "")


def _swap_roster_and_selected_specs() -> None:
    attacker_roster = st.session_state.get("attacker_roster_specs", [])
    target_roster = st.session_state.get("target_roster_specs", [])
    st.session_state["attacker_roster_specs"] = target_roster
    st.session_state["target_roster_specs"] = attacker_roster

    attackers = st.session_state.get("selected_attacker_specs", [])
    targets = st.session_state.get("selected_target_specs", [])
    st.session_state["selected_attacker_specs"] = targets
    st.session_state["selected_target_specs"] = attackers


def _normalize_specs(session_info: SessionInfo | Set[ShipSpecifier] | None) -> Sequence[ShipSpecifier]:
    if isinstance(session_info, SessionInfo):
        specs = session_info.get_every_ship()
    elif isinstance(session_info, set):
        specs = session_info
    else:
        specs = set()

    return sorted(specs, key=lambda spec: str(spec))


def _resolve_defaults(
        serialized: Iterable[SerializedShipSpec] | None,
        spec_lookup: dict[SerializedShipSpec, ShipSpecifier],
        fallback: Sequence[ShipSpecifier],
) -> list[ShipSpecifier]:
    if serialized:
        resolved = [spec_lookup[item] for item in serialized if item in spec_lookup]
        if not resolved:
            logger.warning(
                "No matching ship specs found for stored defaults; falling back to %s.",
                [str(spec) for spec in fallback],
            )
        if resolved:
            return resolved
    return list(fallback)


def _resolve_roster_specs(
        serialized: Iterable[SerializedShipSpec] | None,
        spec_lookup: dict[SerializedShipSpec, ShipSpecifier],
        fallback: Sequence[ShipSpecifier],
) -> list[ShipSpecifier]:
    roster_specs = [spec_lookup[item] for item in (serialized or []) if item in spec_lookup]
    if roster_specs:
        return roster_specs
    if serialized:
        logger.warning(
            "Roster specs were present but none matched current ship options; "
            "falling back to %s.",
            [str(spec) for spec in fallback],
        )
    return list(fallback)


def render_actor_target_selector(
        session_info: SessionInfo | Set[ShipSpecifier] | None,
) -> tuple[Sequence[ShipSpecifier], Sequence[ShipSpecifier]]:
    options = _normalize_specs(session_info)
    if not options:
        logger.warning(
            "Actor/target selector has no ship options; session_info=%s.",
            type(session_info).__name__,
        )
        st.warning("No ship data available to select attacker/target.")
        return (), ()

    spec_lookup = {_serialize_spec(spec): spec for spec in options}
    if "attacker_roster_specs" not in st.session_state:
        st.session_state["attacker_roster_specs"] = [_serialize_spec(spec) for spec in options]
    if "target_roster_specs" not in st.session_state:
        st.session_state["target_roster_specs"] = [_serialize_spec(spec) for spec in options]
    if "selected_attacker_specs" not in st.session_state:
        st.session_state["selected_attacker_specs"] = list(
            st.session_state.get("attacker_roster_specs", [])
        )
    if "selected_target_specs" not in st.session_state:
        st.session_state["selected_target_specs"] = list(
            st.session_state.get("target_roster_specs", [])
        )

    attacker_roster = _resolve_roster_specs(
        st.session_state.get("attacker_roster_specs"),
        spec_lookup,
        options,
    )
    target_roster = _resolve_roster_specs(
        st.session_state.get("target_roster_specs"),
        spec_lookup,
        options,
    )
    default_attacker = _resolve_defaults(
        st.session_state.get("selected_attacker_specs"),
        spec_lookup,
        attacker_roster[:1],
    )
    default_target = _resolve_defaults(
        st.session_state.get("selected_target_specs"),
        spec_lookup,
        target_roster[:1],
    )

    selector_left, selector_swap, selector_right = st.columns([8, 1, 8])
    with selector_left:
        st.markdown("**Attacker**")
        selected_attackers: list[ShipSpecifier] = []
        selected_attacker_serialized = {_serialize_spec(spec) for spec in default_attacker}
        for spec in attacker_roster:
            serialized = _serialize_spec(spec)
            is_checked = serialized in selected_attacker_serialized
            if st.checkbox(str(spec), value=is_checked, key=f"attacker_spec_{serialized}"):
                selected_attackers.append(spec)
    with selector_swap:
        st.button(
            "🔄",
            help="Swap attacker and target selections.",
            key="swap_attacker_target_specs",
            on_click=_swap_roster_and_selected_specs,
            width="stretch",
        )
    with selector_right:
        st.markdown("**Target**")
        selected_targets: list[ShipSpecifier] = []
        selected_target_serialized = {_serialize_spec(spec) for spec in default_target}
        for spec in target_roster:
            serialized = _serialize_spec(spec)
            is_checked = serialized in selected_target_serialized
            if st.checkbox(str(spec), value=is_checked, key=f"target_spec_{serialized}"):
                selected_targets.append(spec)

    st.session_state["selected_attacker_specs"] = [_serialize_spec(spec) for spec in selected_attackers]
    st.session_state["selected_target_specs"] = [_serialize_spec(spec) for spec in selected_targets]

    return selected_attackers, selected_targets
