from helpers import get_session_info


def test_combatant_names():
    fname = "1.csv"
    session = get_session_info(fname)
    combatants = session.combatant_names()
    assert "XanOfHanoi" in combatants, f"Missing combatants: {combatants}"
    assert "V'ger Silent Enemy ▶" in combatants, f"Missing combatants: {combatants}"
    assert len(combatants) == 2, "Too many combatants"