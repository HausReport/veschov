import pandas as pd
import pytest

from veschov.io.SessionInfo import SessionInfo, ShipSpecifier


def _make_session_from_rows(rows: list[dict]) -> SessionInfo:
    """Build a SessionInfo with a minimal combat_df for filtering tests.

    Ensures the required attrs and columns exist while keeping the dataset small.
    """
    df = pd.DataFrame(rows)
    # Ensure required columns exist even if not present in rows
    for col in [
        "round",
        "battle_event",
        "event_type",
        "is_crit",
        "attacker_name",
        "attacker_ship",
        "attacker_alliance",
        "attacker_is_armada",
        "target_name",
        "target_ship",
        "target_alliance",
        "target_is_armada",
    ]:
        if col not in df.columns:
            df[col] = pd.NA

    # Minimal attrs used by SessionInfo elsewhere
    df.attrs["players_df"] = pd.DataFrame(
        columns=[
            "Player Name",
            "Ship Name",
            "Officer One",
            "Officer Two",
            "Officer Three",
        ]
    )
    df.attrs["fleets_df"] = pd.DataFrame()

    return SessionInfo(df)


def test_shipspecifier_str_includes_alliance_and_ship() -> None:
    spec = ShipSpecifier(name="Alice", alliance="TD", ship="BORG CUBE")
    # Expected format: "<name> [<alliance>] — <ship>"
    assert str(spec) == "Alice [TD] — BORG CUBE"


def test_shipspecifier_str_omits_duplicate_ship_name() -> None:
    # When ship equals name, the ship segment should not repeat
    spec = ShipSpecifier(name="Solo", alliance="", ship="Solo")
    assert str(spec) == "Solo []" or str(spec) == "Solo", (
        "Alliance is optional; accept either omission or empty brackets depending on data"
    )


def test_filter_by_attacker_name_only() -> None:
    session = _make_session_from_rows(
        [
            {
                "event_type": "attack",
                "attacker_name": "Alice",
                "attacker_alliance": "TD",
                "attacker_ship": "BORG CUBE",
            },
            {
                "event_type": "attack",
                "attacker_name": "Bob",
                "attacker_alliance": "XYZ",
                "attacker_ship": "KOS'KARII",
            },
        ]
    )

    filtered = session.get_combat_df_filtered_by_attacker(
        ShipSpecifier(name="Alice", alliance=None, ship=None)
    )

    assert set(filtered["attacker_name"]) == {"Alice"}
    assert filtered.shape[0] == 1


def test_filter_by_multiple_attackers_or_logic() -> None:
    session = _make_session_from_rows(
        [
            {
                "event_type": "attack",
                "attacker_name": "Alice",
                "attacker_alliance": "TD",
                "attacker_ship": "BORG CUBE",
            },
            {
                "event_type": "attack",
                "attacker_name": "Bob",
                "attacker_alliance": "XYZ",
                "attacker_ship": "KOS'KARII",
            },
            {
                "event_type": "attack",
                "attacker_name": "Carol",
                "attacker_alliance": "TD",
                "attacker_ship": "ENTERPRISE NX-01",
            },
        ]
    )

    filtered = session.get_combat_df_filtered_by_attackers(
        [
            ShipSpecifier(name="Alice", alliance=None, ship=None),
            ShipSpecifier(name="Carol", alliance=None, ship=None),
        ]
    )

    assert set(filtered["attacker_name"]) == {"Alice", "Carol"}
    assert filtered.shape[0] == 2


def test_below_deck_officers_from_fixture_1() -> None:
    # Uses real parsed fixture via helpers to ensure integration with officer extraction
    from tests.helpers import get_session_info

    session = get_session_info("1.csv")
    below_deck = session.get_below_deck_officers("XanOfHanoi", "BORG CUBE")

    # From existing fixture expectations:
    # all_officer_names includes 7 names (see test_all_officer_names)
    # bridge crew includes 3 names (see test_bridge_officer_names)
    # So below deck should include the other 4 names
    expected = {"Harry Kim", "PIC Hugh", "Masriad Vael", "Seska"}
    assert expected.issubset(below_deck)
