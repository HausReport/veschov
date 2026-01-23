import pytest
import streamlit as st

from tests.helpers import get_battle_log
from veschov.io.SessionInfo import SessionInfo
from veschov.io.ShipSpecifier import ShipSpecifier
from veschov.ui.chirality import Lens
from veschov.ui.components.combat_lens import apply_combat_lens


@pytest.mark.parametrize(
    ("ability_owner", "expected_count"),
    [
        ("Masriad Vael", 59),
        ("Annorax", 59),
        ("Kathryn Janeway", 49),
        ("The Doctor", 48),
        ("Seska", 45),
        ("Harry Kim", 15),
    ],
)
def test_proc_target_filter_skip_counts(ability_owner: str, expected_count: int) -> None:
    battle_df = get_battle_log("1.csv")
    session = SessionInfo(battle_df)
    st.session_state["session_info"] = session

    xan_ship = (
        battle_df.loc[battle_df["attacker_name"] == "XanOfHanoi", "attacker_ship"]
        .dropna()
        .iloc[0]
    )
    vger_name = "V'ger Silent Enemy ▶"
    vger_ship = (
        battle_df.loc[battle_df["attacker_name"] == vger_name, "attacker_ship"]
        .dropna()
        .iloc[0]
    )

    attacker = ShipSpecifier(name="XanOfHanoi", alliance="", ship=xan_ship)
    target = ShipSpecifier(name=vger_name, alliance="", ship=vger_ship)
    lens = Lens(
        actor_name=attacker.name,
        target_name=target.name,
        label="Player → NPC",
        attacker_specs=(attacker,),
        target_specs=(target,),
    )

    filtered = apply_combat_lens(
        battle_df,
        lens,
        skip_target_filter_for_procs=True,
    )
    proc_types = {"Officer", "ForbiddenTechAbility"}
    proc_df = filtered[filtered["event_type"].isin(proc_types)]
    counts = proc_df["ability_owner_name"].value_counts()

    assert counts.get(ability_owner, 0) == expected_count
