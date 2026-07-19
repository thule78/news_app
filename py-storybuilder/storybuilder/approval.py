from dataclasses import dataclass
from typing import Any


@dataclass
class Proposal:
    kind: str  # new_character | character_fact | new_location | location_fact | ending
    description: str
    payload: dict[str, Any]


def review(proposals: list[Proposal]) -> list[Proposal]:
    approved = []
    for p in proposals:
        answer = input(f"[{p.kind}] {p.description}\n  Approve? (y/n): ").strip().lower()
        if answer.startswith("y"):
            approved.append(p)
    return approved
