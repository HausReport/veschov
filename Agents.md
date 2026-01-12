1. Project uses Streamlit 1.0.1.  Note carefully, major differences to earlier versions.
2. We try to stay as close to PEP as possible, but are not fanatics if it would cause problems.
2.1 A PEP exception - I prefer CamelCase for classes.
2.2 Other than tiny helper classes, I prefer one per file.  I prefer the filename and class name to match.
3. We believe deeply in typing, return types, and docstrings.
4. Page navigation is in [root]/.streamlit/pages.toml.
5. Pytests are in [root]/tests.  Some normal and abnormal logs are in [root]/tests/logs.
6. Docstrings should be widely used and clear.
7. We like logging.  Loggers should be defined at the module level and used freely.  Streamlit error notification to the user is fine, but not a substitute for logging. 
7.1 Silent returns that interrupt execution and silent exception handling lead to difficult-to-debug problems.  When you see cases like this, please add an appropriate logger.warning.
7.2 Err on the side of too many logger messages rather than too few.
7. Typing is mandatory, not aspirational.
   - All functions must declare parameter and return types.
   - Prefer modern typing (`list[T]`, `dict[str, T]`, `X | None`).
   - Use `from __future__ import annotations` by default.
   - If imports would cause cycles or heavy runtime cost, use:
     `from typing import TYPE_CHECKING` and guard imports under `if TYPE_CHECKING:`.
   - Avoid `Any`. If unavoidable, document why.
8. Streamlit UI philosophy:
   - This is an analytical tool for power users, not a marketing dashboard.
   - Favor explicit controls over clever or compact ones.
   - Entity names must always be readable; avoid truncation-heavy widgets.
   - Assume small-N lists (≈8 entities); optimize for clarity, not scalability.
   - State should be explicit and deterministic (prefer `st.session_state` with clear keys).
9. Testing philosophy:
    - Prefer parameterized tests over repetitive assertions.
    - When order is irrelevant, compare sets, not lists.
    - Golden data files are acceptable and encouraged where appropriate.
    - Tests should validate behavior, not incidental implementation details.
10. Observations (for Codex):
    - Use this section to record patterns, invariants, or assumptions discovered
      while working in the codebase.
    - Do not repeat existing rules; add only genuinely new insights.