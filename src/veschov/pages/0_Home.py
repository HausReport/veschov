from __future__ import annotations

import base64
import hashlib
import logging
import random
from pathlib import Path

import pandas as pd
import streamlit as st

from veschov.io.SessionInfo import SessionInfo
from veschov.io.parser_stub import parse_battle_log
from veschov.ui.chirality import Lens
from veschov.ui.object_reports.AbstractReport import AbstractReport

logger = logging.getLogger(__name__)


class HomeReport(AbstractReport):
    """Render the home page content and preload a sample log."""

    def __init__(self) -> None:
        self._repo_root = Path(__file__).resolve().parents[3]
        self._assets_path = Path(__file__).resolve().parent / "assets" / "warrior.png"

    def render(self) -> None:
        self._maybe_load_sample_log()
        img_uri = self._img_to_data_uri(self._assets_path)
        image_html = ""
        if img_uri:
            image_html = f'<img class="klingon-wrap" src="{img_uri}" alt="Battle Mentor"/>'

        st.markdown(
            f"""
<style>
/* Wrap container placed at top of the page content */
.klingon-wrap {{
  float: right;
  margin: 0.25rem 0 0.75rem 1rem;   /* top, right, bottom, left */
  max-height: 288px;               /* ~3" at 96dpi */
  height: auto;
  width: auto;
  shape-outside: inset(0 round 18px); /* helps wrap around rounded shape */
}}

.klingon-wrap img {{
  display: block;
  max-height: 240px;
  height: auto;
  width: auto;
  border-radius: 18px;
  /* optional: subtle separation from dark background */
  filter: drop-shadow(0 10px 20px rgba(0,0,0,0.55));
}}
</style>

{image_html}

<div>
<h1 style="margin-top:0;">Home</h1>
<p style="opacity:0.9; font-size: 1.05rem;">
<strong>"Greetings, warrior and welcome to veSchov!  That's tlhIngan Hol for 'Illuminate the battle.'
I've loaded up a sample battle from Hanoi Xan so you can tour the facility, but you're welcome to 
<u>upload your own battle log</u> using the control in the lower-left corner and we can look through 
it together."</strong>
</p>

<p style="opacity:0.85;">
<strong>"nuH ghaj Sov.</strong> &nbsp; <em>Knowledge is a weapon."</strong>
</p>

</div>
""",
            unsafe_allow_html=True,
        )
        df = self.add_log_uploader(
            title="Home",
            description="Upload a battle log to explore sample reports.",
        )

    def _img_to_data_uri(self, path: Path) -> str | None:
        """Return a base64-encoded data URI for a local image path."""
        if not path.exists():
            logger.warning("Home page image missing at %s.", path)
            st.warning("Home page image not found.")
            return None
        data = path.read_bytes()
        b64 = base64.b64encode(data).decode("utf-8")
        return f"data:image/png;base64,{b64}"

    def _maybe_load_sample_log(self) -> None:
        """Load a random sample log into session state if none is present."""
        if isinstance(st.session_state.get("battle_df"), pd.DataFrame):
            return
        log_dir = self._repo_root / "tests" / "logs"
        if not log_dir.exists():
            logger.warning("Sample log directory not found at %s.", log_dir)
            return
        candidates = [
            path
            for path in log_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".csv", ".tsv", ".txt"}
        ]
        if not candidates:
            logger.warning("No sample logs found in %s.", log_dir)
            return

        sample = random.choice(candidates)
        try:
            data = sample.read_bytes()
            df = parse_battle_log(data, sample.name)
        except Exception as exc:  # pragma: no cover - UI feedback
            logger.exception("Failed to load sample log %s.", sample)
            st.warning(f"Unable to load sample log: {sample.name}.")
            return

        upload_hash = hashlib.md5(data).hexdigest()
        st.session_state["battle_df"] = df
        st.session_state["battle_filename"] = sample.name
        st.session_state["battle_upload_hash"] = upload_hash
        st.session_state["players_df"] = df.attrs.get("players_df")
        st.session_state["fleets_df"] = df.attrs.get("fleets_df")
        st.session_state["session_info"] = SessionInfo(df)
        st.caption(f"Loaded sample log: {sample.name}")

    def get_under_title_text(self) -> str | None:
        return None

    def get_under_chart_text(self) -> str | None:
        return None

    def get_log_title(self) -> str:
        return "Home"

    def get_log_description(self) -> str:
        return "Welcome to STFC Reports."

    def render_header(self, df: pd.DataFrame) -> Lens | None:
        return None

    def get_derived_dataframes(self, df: pd.DataFrame, lens: Lens | None) -> list[pd.DataFrame] | None:
        return None

    def display_plots(self, dfs: list[pd.DataFrame]) -> None:
        return None

    def display_tables(self, dfs: list[pd.DataFrame]) -> None:
        return None

    def render_debug_info(self, dfs: list[pd.DataFrame]) -> None:
        return None

    def get_x_axis_text(self) -> str | None:
        return None

    def get_y_axis_text(self) -> str | None:
        return None

    def get_title_text(self) -> str | None:
        return None


st.set_page_config(page_title="veSchov: Illuminate the Battle.", layout="wide")
HomeReport().render()


