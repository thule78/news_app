from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class CharacterBackground:
    type: str  # Appearance | Goals | History | Aliases | Facts
    description: str
    timeline_ref: Optional[str] = None
    chapter_ref: Optional[str] = None
    approved_at: Optional[str] = None


@dataclass
class Character:
    id: str
    name: str
    status: str = "active"  # active | proposed
    introduced_in_pool: bool = True
    background: list[CharacterBackground] = field(default_factory=list)

    @staticmethod
    def from_dict(d: dict) -> "Character":
        return Character(
            id=d["id"],
            name=d["name"],
            status=d.get("status", "active"),
            introduced_in_pool=d.get("introduced_in_pool", True),
            background=[CharacterBackground(**b) for b in d.get("background", [])],
        )


@dataclass
class LocationDescription:
    description: str
    timeline_ref: Optional[str] = None
    chapter_ref: Optional[str] = None
    approved_at: Optional[str] = None


@dataclass
class Location:
    id: str
    name: str
    status: str = "active"  # active | proposed
    introduced_in_pool: bool = True
    descriptions: list[LocationDescription] = field(default_factory=list)

    @staticmethod
    def from_dict(d: dict) -> "Location":
        return Location(
            id=d["id"],
            name=d["name"],
            status=d.get("status", "active"),
            introduced_in_pool=d.get("introduced_in_pool", True),
            descriptions=[LocationDescription(**x) for x in d.get("descriptions", [])],
        )


@dataclass
class Timeline:
    id: str
    name: str
    description: str = ""
    start_date: Optional[str] = None
    stop_date: Optional[str] = None


@dataclass
class ChapterMeta:
    id: str
    title: str
    synopsis: str = ""
    sequence: int = 1


@dataclass
class EndingState:
    suggested: bool = False
    reason: Optional[str] = None
    suggested_at_chapter: Optional[str] = None
    suggested_at_paragraph: Optional[int] = None


@dataclass
class Story:
    id: str
    title: str
    style: str = ""
    synopsis: str = ""
    world_facts: str = ""
    constraints: list[str] = field(default_factory=list)
    chapter_count_target: Optional[int] = None
    chapters: list[ChapterMeta] = field(default_factory=list)
    timelines: list[Timeline] = field(default_factory=list)
    characters: list[Character] = field(default_factory=list)
    locations: list[Location] = field(default_factory=list)
    ending: EndingState = field(default_factory=EndingState)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Story":
        return Story(
            id=d["id"],
            title=d["title"],
            style=d.get("style", ""),
            synopsis=d.get("synopsis", ""),
            world_facts=d.get("world_facts", ""),
            constraints=d.get("constraints", []),
            chapter_count_target=d.get("chapter_count_target"),
            chapters=[ChapterMeta(**c) for c in d.get("chapters", [])],
            timelines=[Timeline(**t) for t in d.get("timelines", [])],
            characters=[Character.from_dict(c) for c in d.get("characters", [])],
            locations=[Location.from_dict(l) for l in d.get("locations", [])],
            ending=EndingState(**d.get("ending", {})),
        )

    def active_characters(self) -> list[Character]:
        return [c for c in self.characters if c.status == "active"]

    def active_locations(self) -> list[Location]:
        return [l for l in self.locations if l.status == "active"]

    def find_character(self, name: str) -> Optional[Character]:
        return next((c for c in self.characters if c.name == name), None)

    def find_location(self, name: str) -> Optional[Location]:
        return next((l for l in self.locations if l.name == name), None)

    def find_character_by_id(self, character_id: Optional[str]) -> Optional[str]:
        c = next((c for c in self.characters if c.id == character_id), None)
        return c.name if c else None

    def find_location_by_id(self, location_id: Optional[str]) -> Optional[str]:
        l = next((l for l in self.locations if l.id == location_id), None)
        return l.name if l else None


@dataclass
class Paragraph:
    sequence: int
    content: str
    location_ref: Optional[str] = None
    timeline_ref: Optional[str] = None
    character_refs: list[str] = field(default_factory=list)


@dataclass
class Chapter:
    id: str
    title: str
    sequence: int
    paragraphs: list[Paragraph] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Chapter":
        return Chapter(
            id=d["id"],
            title=d["title"],
            sequence=d.get("sequence", 1),
            paragraphs=[Paragraph(**p) for p in d.get("paragraphs", [])],
        )
