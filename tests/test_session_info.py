from helpers import get_session_info











def test_officer_names():
    fname = "1.csv"
    session = get_session_info(fname)
    officers = session.all_officer_names("XanOfHanoi", "BORG CUBE")
    for officer in {'Kathryn Janeway', 'Harry Kim', 'The Doctor', 'Annorax', 'PIC Hugh', 'Masriad Vael', 'Seska'}:
        assert officer in officers, f"Missing officers: {officers}"
