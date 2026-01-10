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


def _swap_selected_specs() -> None:
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
        if resolved:
            return resolved
    return list(fallback)


def render_actor_target_selector(
    session_info: SessionInfo | Set[ShipSpecifier] | None,
) -> tuple[Sequence[ShipSpecifier], Sequence[ShipSpecifier]]:
    options = _normalize_specs(session_info)
    if not options:
        st.warning("No ship data available to select attacker/target.")
        return (), ()

    spec_lookup = {_serialize_spec(spec): spec for spec in options}
    default_attacker = _resolve_defaults(
        st.session_state.get("selected_attacker_specs"),
        spec_lookup,
        options[:1],
    )
    default_target = _resolve_defaults(
        st.session_state.get("selected_target_specs"),
        spec_lookup,
        options[-1:],
    )

    selector_left, selector_swap, selector_right = st.columns([5, 1, 5])
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
            on_click=_swap_selected_specs,
            use_container_width=True,
        )
    with selector_right:
        selected_targets = st.multiselect(
            "Target",
            options,
            default=default_target,
            format_func=str,
        )

    st.session_state["selected_attacker_specs"] = [_serialize_spec(spec) for spec in selected_attackers]
    st.session_state["selected_target_specs"] = [_serialize_spec(spec) for spec in selected_targets]

    return selected_attackers, selected_targets
