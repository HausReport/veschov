import base64
from pathlib import Path
import streamlit as st

def img_to_data_uri(path: str) -> str:
    data = Path(path).read_bytes()
    b64 = base64.b64encode(data).decode("utf-8")
    return f"data:image/png;base64,{b64}"

# --- path to your png with alpha (transparent background recommended) ---
img_uri = img_to_data_uri("assets/warrior.png")

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

<img class="klingon-wrap" src="{img_uri}" alt="Battle Mentor"/>

<div>
<h1 style="margin-top:0;">Home</h1>
<p style="opacity:0.9; font-size: 1.05rem;">
Welcome to STFC Reports. Use the left navigation to explore sessions and combat logs.
</p>

<p style="opacity:0.85;">
<strong>nuH ghaj Sov.</strong> &nbsp; <em>Knowledge is a weapon.</em>
</p>

<p style="opacity:0.85;">
Add your longer explanatory text here — it will naturally wrap around him as it flows down the page.
Keep writing and you’ll see the wrap behavior.
</p>
</div>
""",
    unsafe_allow_html=True,
)


    # st.subheader("Status")
# ROOT = Path(__file__).resolve().parent
# img_path = (ROOT / "assets" / "warrior.png" )
# st.image(img_path)