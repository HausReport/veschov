import io
import logging
from typing import Dict, IO, Optional

import pandas as pd

logger = logging.getLogger(__name__)

NA_TOKENS = ("--", "—", "–", "")

SECTION_HEADERS = {
    "players": "Player Name\tPlayer Level\tOutcome",
    "rewards": "Reward Name\tCount",
    "fleets": "Fleet Type\tAttack\tDefense\tHealth",
    "combat": "Round\tBattle Event\tType",
}


def extract_sections(
    text: str, headers: Dict[str, str] | None = None
) -> Dict[str, str]:
    """Extract labeled sections from a battle log export."""
    headers = headers or SECTION_HEADERS
    found: Dict[str, str] = {}
    current_key: Optional[str] = None
    buffer: list[str] = []

    for line in text.splitlines():
        if line.strip() == "":
            if current_key and buffer:
                found[current_key] = "\n".join(buffer)
            current_key = None
            buffer = []
            continue

        matched_key = next(
            (key for key, prefix in headers.items() if line.startswith(prefix)),
            None,
        )
        if matched_key:
            if current_key and buffer:
                found[current_key] = "\n".join(buffer)
            current_key = matched_key
            buffer = [line]
            continue

        if current_key:
            buffer.append(line)

    if current_key and buffer:
        found[current_key] = "\n".join(buffer)

    return found


def section_to_dataframe(
    section_text: Optional[str], header_prefix: str
) -> pd.DataFrame:
    """Parse a tab-delimited section into a dataframe."""
    columns = header_prefix.split("\t")
    if not section_text:
        return pd.DataFrame(columns=columns)

    try:
        return pd.read_csv(
            io.StringIO(section_text),
            sep="\t",
            dtype=str,
            na_values=NA_TOKENS,
        )
    except Exception:  # pragma: no cover - defensive for messy inputs
        logger.exception("Failed to parse section with header %s", header_prefix)
        return pd.DataFrame(columns=columns)


class StartsWhen(io.TextIOBase):
    """Wrap a text stream so reads begin after a specific prefix line."""

    def __init__(self, f: IO[str], prefix: str) -> None:
        self._f = f
        self._prefix = prefix
        self._started = False

    def readable(self) -> bool:
        return True

    def readline(self, size: int = -1) -> str:
        if not self._started:
            for line in self._f:
                if line.startswith(self._prefix):
                    self._started = True
                    return line
            return ""  # EOF
        return self._f.readline(size)

    def read(self, size: int = -1) -> str:
        if not self._started:
            # consume until we hit the prefix
            first = self.readline()
            if first == "":
                return ""
            if size == -1:
                return first + self._f.read()
            # bounded read: return first plus remaining up to size
            rest = self._f.read(max(0, size - len(first)))
            return first + rest
        return self._f.read(size)
