from helpers import get_session_info
from veschov.io.ShipSpecifier import ShipSpecifier
import pytest

CASES = [
    (
        "1.csv",
        [
            ShipSpecifier("XanOfHanoi", "ThunderDome", "BORG CUBE"),
            ShipSpecifier("V'ger Silent Enemy ▶", "", "V'ger Silent Enemy"),
            # up to ~8 entries here
        ],
    ),
    (
        "2-outpost-retal.csv",
        [
            ShipSpecifier("XanOfHanoi", "ThunderDome", "BORG CUBE"),
            ShipSpecifier("XanOfHanoi", "ThunderDome", "KOS'KARII"),
            ShipSpecifier("Assimilated Galor-Class", "", "Assimilated Galor-Class"),
        ],
    ),
    (
        "3-armada.csv",
        [
            ShipSpecifier("Popperbottom", "ThunderDome", "ENTERPRISE NX-01"),
            ShipSpecifier("NWMaverick", "ThunderDome", "SS REVENANT"),
            ShipSpecifier("chahkoh", "ThunderDome", "SS REVENANT"),
            ShipSpecifier("AmigoSniped", "ThunderDome", "SS REVENANT"),
            ShipSpecifier("XanOfHanoi", "ThunderDome", "SS REVENANT"),
            ShipSpecifier("Borg Polygon 1.2", "", "Borg Polygon 1.2"),
        ],
    ),
]

@pytest.mark.parametrize("fname, expected", CASES)
def test_get_every_ship(fname, expected):
    session = get_session_info(fname)
    ships = session.get_every_ship()
    for ship in expected:
        assert ship in ships, f"Missing ship: {ship}"