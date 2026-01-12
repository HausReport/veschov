# veSchov

veSchov is a **technical analysis and visualization tool** for combat log data, built with
**Python, pandas, Plotly, and Streamlit**.

It focuses on **truthful, low-abstraction representations of combat behavior**, prioritizing
correctness, explicit state, and analytical clarity over convenience or visual sugar.

This is not a generic dashboard framework. It is a domain-driven tool built to answer specific
questions about combat dynamics.

---

## What this project is

- A **Streamlit-based analytical UI** for exploring combat logs
- Strongly typed, correctness-first Python
- Designed around **explicit entities** (ships, players, NPCs)
- Built for **small-N, high-fidelity analysis** (≈ 1–8 combatants)
- Uses Plotly for precise, inspectable visualizations

Key features include:
- Damage flow analysis by round
- Shot-level cadence visualizations (e.g. per-round firing patterns)
- Entity-driven filtering (“what they did” vs “what was done to them”)
- Post-mitigation damage analysis (normal / isolytic / apex, etc.)

---

## What this project is not

- Not a polished consumer app
- Not a generic data-viz library
- Not optimized for very large datasets
- Not designed to hide or smooth inconvenient truths in the data

If a visualization flattens because one entity dominates, that is considered **correct behavior**.

---

## Design principles

Some explicit design choices you’ll see throughout the code:

- **Strong typing is mandatory**
  - All functions declare parameter and return types
  - `from __future__ import annotations` is preferred
- **Explicit state over clever abstractions**
  - Streamlit session state is managed deliberately
- **Small-N UI design**
  - Readability beats compactness
  - Entity names must always be readable
- **Truth over aesthetics**
  - Visualizations reflect reality, even when that reality is uneven
- **Docstrings are contracts**
  - They explain intent, invariants, and assumptions

Additional guidance for contributors and tools can be found in `AGENTS.md`.

---

## Project structure (high level)

## Status

This is an **actively evolving personal/research tool**.

APIs, UI structure, and internal models may change without notice.

---

## License

MIT License. See `LICENSE` for details.