"""Unit tests for attacker/target state persistence."""

from __future__ import annotations

import streamlit as st
from streamlit.testing.v1 import AppTest

from veschov.io.ShipSpecifier import ShipSpecifier
from veschov.ui.object_reports.rosters.AttackerTargetSelection import AttackerTargetSelection
from veschov.ui.object_reports.rosters.AttackerTargetStateManager import (
    AttackerTargetStateManager,
    serialize_spec,
)


def _build_specs() -> list[ShipSpecifier]:
    """Return a small roster of ShipSpecifier instances for tests."""
    return [
        ShipSpecifier(name="Alpha", alliance="A", ship="Alpha"),
        ShipSpecifier(name="Bravo", alliance="B", ship="Bravo"),
        ShipSpecifier(name="Charlie", alliance="C", ship="Charlie"),
    ]


def _build_manager(specs: list[ShipSpecifier]) -> AttackerTargetStateManager:
    """Create a state manager for the provided specs."""
    spec_lookup = {serialize_spec(spec): spec for spec in specs}
    available_specs = [serialize_spec(spec) for spec in specs]
    default_attacker_specs = available_specs[:1]
    default_target_specs = available_specs[1:2]
    return AttackerTargetStateManager(
        spec_lookup=spec_lookup,
        available_specs=available_specs,
        default_attacker_specs=default_attacker_specs,
        default_target_specs=default_target_specs,
    )


def test_persist_and_load_state_without_widget_keys() -> None:
    """Selections persist even when widget keys are missing."""
    specs = _build_specs()
    serialized_specs = [serialize_spec(spec) for spec in specs]

    def render() -> None:
        manager = _build_manager(specs)
        phase = st.session_state.get("phase", "persist")
        if phase == "persist":
            state = AttackerTargetSelection(
                attacker_roster=serialized_specs[:2],
                target_roster=serialized_specs[1:],
                selected_attackers=serialized_specs[:1],
                selected_targets=serialized_specs[1:2],
            )
            manager._persist_state(state, origin="test")
            st.session_state["phase"] = "load"
            return
        for key in list(st.session_state.keys()):
            if key.startswith(manager.CHECKBOX_TEMP_PREFIX) or key.startswith(manager.CHECKBOX_PERSIST_PREFIX):
                st.session_state.pop(key, None)
        loaded = manager._load_state()
        st.session_state["loaded_attackers"] = (
            list(loaded.selected_attackers) if loaded is not None else []
        )
        st.session_state["loaded_targets"] = (
            list(loaded.selected_targets) if loaded is not None else []
        )

    app = AppTest.from_function(render)
    app.run()
    app.run()

    assert set(app.session_state["loaded_attackers"]) == {serialized_specs[0]}
    assert set(app.session_state["loaded_targets"]) == {serialized_specs[1]}


def test_resolve_state_filters_missing_roster_specs() -> None:
    """Roster changes drop missing selections and fall back to defaults."""
    specs = _build_specs()
    serialized_specs = [serialize_spec(spec) for spec in specs]

    def render() -> None:
        phase = st.session_state.get("phase", "persist")
        if phase == "persist":
            manager = _build_manager(specs)
            state = AttackerTargetSelection(
                attacker_roster=serialized_specs[:2],
                target_roster=serialized_specs[2:],
                selected_attackers=serialized_specs[:2],
                selected_targets=serialized_specs[2:],
            )
            manager._persist_state(state, origin="test")
            st.session_state["phase"] = "resolve"
            return
        updated_specs = specs[:2]
        manager = _build_manager(updated_specs)
        resolved = manager.resolve_state(origin="test")
        st.session_state["resolved_attackers"] = list(resolved.selected_attackers)
        st.session_state["resolved_targets"] = list(resolved.selected_targets)

    app = AppTest.from_function(render)
    app.run()
    app.run()

    assert set(app.session_state["resolved_attackers"]) <= set(serialized_specs[:2])
    assert set(app.session_state["resolved_targets"]) <= set(serialized_specs[:2])
