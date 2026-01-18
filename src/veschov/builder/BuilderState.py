from typing import TypedDict


class BuilderState(TypedDict):
    v: int
    holding: str | None
    bridge_slots: list[str | None]
    even_slots: list[str | None]
    manual_pick: str
    build_name: str
    ship_name: str
    notes: str
    suggestions: list[str]