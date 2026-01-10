from helpers import get_session_info


def test_alliance_names():
    fname = "1.csv"
    session = get_session_info(fname)
    alliances = session.alliance_names()
    assert "ThunderDome" in alliances, f"Missing alliances: {alliances}"
    # assert "--" in alliances, f"Missing alliances: {alliances}"
    assert len(alliances) == 1, "Too many alliances"