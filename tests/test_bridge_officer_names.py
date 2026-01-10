from helpers import get_session_info


def test_session_info():
    fname = "1.csv"
    session = get_session_info(fname)
    officers = session.get_bridge_crew("XanOfHanoi", "BORG CUBE")
    for officer in ['The Doctor', 'Kathryn Janeway', 'Annorax']:
        assert officer in officers, f"Missing officers: {officers}"