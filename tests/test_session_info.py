from pathlib import Path

import pandas as pd

from veschov.io.SessionInfo import SessionInfo
from veschov.io.parser_stub import parse_battle_log

def get_battle_log(fname) -> pd.DataFrame:
    path = Path(__file__).resolve().parent / "logs" / fname
    assert path.exists(), f"Missing test fixture file: {path.resolve()}"
    file_bytes = path.read_bytes()
    combat_df = parse_battle_log(file_bytes, fname)
    return combat_df

def get_session_info(fname) -> SessionInfo:
    combat_df = get_battle_log(fname)
    return SessionInfo(combat_df)

def test_combatant_names():
    fname = "1.csv"
    session = get_session_info(fname)
    combatants = session.combatant_names()
    assert "XanOfHanoi" in combatants, f"Missing combatants: {combatants}"
    assert "V'ger Silent Enemy ▶" in combatants, f"Missing combatants: {combatants}"
    assert len(combatants) == 2, "Too many combatants"

def test_alliance_names():
    fname = "1.csv"
    session = get_session_info(fname)
    alliances = session.alliance_names()
    assert "ThunderDome" in alliances, f"Missing alliances: {alliances}"
    # assert "--" in alliances, f"Missing alliances: {alliances}"
    assert len(alliances) == 1, "Too many alliances"

def test_ship_names():
    fname = "1.csv"
    session = get_session_info(fname)
    ships = session.get_ships("XanOfHanoi")
    assert "BORG CUBE" in ships, f"Missing ships: {ships}"
    assert len(ships) == 1, "Too many ships"


def test_bridge_officer_names():
    fname = "1.csv"
    session = get_session_info(fname)
    officers = session.get_bridge_crew("XanOfHanoi", "BORG CUBE")
    for officer in ['The Doctor', 'Kathryn Janeway', 'Annorax']:
        assert officer in officers, f"Missing officers: {officers}"

def test_officer_names():
    fname = "1.csv"
    session = get_session_info(fname)
    officers = session.all_officer_names("XanOfHanoi", "BORG CUBE")
    for officer in {'Kathryn Janeway', 'Harry Kim', 'The Doctor', 'Annorax', 'PIC Hugh', 'Masriad Vael', 'Seska'}:
        assert officer in officers, f"Missing officers: {officers}"
