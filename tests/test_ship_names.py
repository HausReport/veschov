from helpers import get_session_info


def test_ship_names():
    fname = "1.csv"
    session = get_session_info(fname)
    ships = session.get_ships("XanOfHanoi")
    assert "BORG CUBE" in ships, f"Missing ships: {ships}"
    assert len(ships) == 1, "Too many ships"