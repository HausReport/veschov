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