import json
from datetime import datetime, timezone

from . import llm, prompts, storage
from .approval import Proposal, review
from .models import Character, CharacterBackground, Location, LocationDescription, Paragraph, Story

MAX_PREVIOUS_WORDS = 600
MAX_PARAGRAPH_WORDS = 200


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _character_context(story: Story) -> str:
    lines = []
    for c in story.active_characters():
        facts = "; ".join(f"({b.type}) {b.description}" for b in c.background)
        lines.append(f"{c.name}: {facts}" if facts else c.name)
    return "\n".join(lines) if lines else "(none yet)"


def _location_context(story: Story, location_id: str | None) -> str:
    if location_id is None:
        return "(unspecified)"
    location = next((l for l in story.locations if l.id == location_id), None)
    return location.name if location else "(unspecified)"


def _previous_paragraphs_text(chapter) -> str:
    kept = []
    total_words = 0
    for paragraph in reversed(chapter.paragraphs):
        words = len(paragraph.content.split())
        if kept and total_words + words > MAX_PREVIOUS_WORDS:
            break
        kept.insert(0, paragraph.content)
        total_words += words
    return "\n\n".join(kept) if kept else "(story just started)"


def _character_background_json(character: Character) -> list[dict]:
    return [{"description_type": b.type, "description": b.description} for b in character.background]


def _location_background_json(location: Location) -> list[str]:
    return [d.description for d in location.descriptions]


def run_step(story_id: str) -> None:
    from .timeline_summary import generate_summary

    story = storage.load_story(story_id)
    if not story.chapters:
        raise RuntimeError("Story has no chapters yet — create one before running a step.")
    if not story.timelines:
        raise RuntimeError("Story has no timelines yet — create one before running a step.")

    chapter_meta = story.chapters[-1]
    chapter = storage.load_chapter(story_id, chapter_meta.id)
    all_chapters = [storage.load_chapter(story_id, cm.id) for cm in story.chapters]

    last_paragraph = chapter.paragraphs[-1] if chapter.paragraphs else None
    timeline_id = last_paragraph.timeline_ref if last_paragraph else story.timelines[0].id
    location_id = last_paragraph.location_ref if last_paragraph else (
        story.active_locations()[0].id if story.active_locations() else None
    )

    timeline_summary = generate_summary(story, all_chapters, timeline_id)

    user_prompt = prompts.WRITE_PARAGRAPH_USER.format(
        title=story.title,
        style=story.style,
        synopsis=story.synopsis,
        world_facts=story.world_facts,
        constraints="; ".join(story.constraints) if story.constraints else "(none)",
        timeline_summary=timeline_summary or "(none yet)",
        current_chapter=f"{chapter_meta.title}: {chapter_meta.synopsis}",
        previous_paragraphs=_previous_paragraphs_text(chapter),
        current_location=_location_context(story, location_id),
        characters=_character_context(story),
        max_words=MAX_PARAGRAPH_WORDS,
    )
    written = llm.call_json(prompts.WRITE_PARAGRAPH_SYSTEM, user_prompt)
    paragraph_content = written["paragraph_content"]

    proposals: list[Proposal] = []
    if written.get("ending_suggested"):
        proposals.append(Proposal(
            kind="ending",
            description=f"Story may be nearing its end: {written.get('ending_reason')}",
            payload={"reason": written.get("ending_reason")},
        ))

    known_characters = [c.name for c in story.active_characters()]
    detected_characters = llm.call_json(
        prompts.DETECT_CHARACTERS_SYSTEM,
        prompts.DETECT_CHARACTERS_USER.format(
            known_characters=json.dumps(known_characters),
            paragraph=paragraph_content,
        ),
    )["characters"]

    existing_char_facts = {
        c.name: _character_background_json(c)
        for c in story.characters
        if c.name in {d["name"] for d in detected_characters if not d["is_new"]}
    }
    character_attrs = []
    if detected_characters:
        character_attrs = llm.call_json(
            prompts.DETECT_CHARACTER_ATTRIBUTES_SYSTEM,
            prompts.DETECT_CHARACTER_ATTRIBUTES_USER.format(
                paragraph=paragraph_content,
                candidate_characters=json.dumps(detected_characters),
                existing_facts=json.dumps(existing_char_facts),
            ),
        )["characters"]

    for entry in character_attrs:
        if entry.get("is_new"):
            proposals.append(Proposal(
                kind="new_character",
                description=f"New character '{entry['name']}': " +
                            "; ".join(f"({d['description_type']}) {d['description']}" for d in entry["descriptions"]),
                payload=entry,
            ))
        else:
            for d in entry["descriptions"]:
                proposals.append(Proposal(
                    kind="character_fact",
                    description=f"{entry['name']} - ({d['description_type']}) {d['description']}",
                    payload={"name": entry["name"], **d},
                ))

    known_locations = [l.name for l in story.active_locations()]
    detected_locations = llm.call_json(
        prompts.DETECT_LOCATIONS_SYSTEM,
        prompts.DETECT_LOCATIONS_USER.format(
            known_locations=json.dumps(known_locations),
            paragraph=paragraph_content,
        ),
    )["locations"]

    existing_loc_facts = {
        l.name: _location_background_json(l)
        for l in story.locations
        if l.name in {d["name"] for d in detected_locations if not d["is_new"]}
    }
    location_attrs = []
    if detected_locations:
        location_attrs = llm.call_json(
            prompts.DETECT_LOCATION_ATTRIBUTES_SYSTEM,
            prompts.DETECT_LOCATION_ATTRIBUTES_USER.format(
                paragraph=paragraph_content,
                candidate_locations=json.dumps(detected_locations),
                existing_facts=json.dumps(existing_loc_facts),
            ),
        )["locations"]

    for entry in location_attrs:
        if entry.get("is_new"):
            proposals.append(Proposal(
                kind="new_location",
                description=f"New location '{entry['name']}': " + "; ".join(entry["descriptions"]),
                payload=entry,
            ))
        else:
            for d in entry["descriptions"]:
                proposals.append(Proposal(
                    kind="location_fact",
                    description=f"{entry['name']} - {d}",
                    payload={"name": entry["name"], "description": d},
                ))

    print("\n--- New paragraph ---\n")
    print(paragraph_content)
    print()

    approved = review(proposals) if proposals else []

    for p in approved:
        if p.kind == "ending":
            story.ending.suggested = True
            story.ending.reason = p.payload["reason"]
            story.ending.suggested_at_chapter = chapter_meta.id
            story.ending.suggested_at_paragraph = len(chapter.paragraphs) + 1
        elif p.kind == "new_character":
            story.characters.append(Character(
                id=storage.new_id("char"),
                name=p.payload["name"],
                status="active",
                introduced_in_pool=False,
                background=[
                    CharacterBackground(
                        type=d["description_type"], description=d["description"],
                        timeline_ref=timeline_id, chapter_ref=chapter_meta.id, approved_at=_now(),
                    )
                    for d in p.payload["descriptions"]
                ],
            ))
        elif p.kind == "character_fact":
            character = story.find_character(p.payload["name"])
            if character:
                character.background.append(CharacterBackground(
                    type=p.payload["description_type"], description=p.payload["description"],
                    timeline_ref=timeline_id, chapter_ref=chapter_meta.id, approved_at=_now(),
                ))
        elif p.kind == "new_location":
            story.locations.append(Location(
                id=storage.new_id("loc"),
                name=p.payload["name"],
                status="active",
                introduced_in_pool=False,
                descriptions=[
                    LocationDescription(
                        description=d, timeline_ref=timeline_id, chapter_ref=chapter_meta.id, approved_at=_now(),
                    )
                    for d in p.payload["descriptions"]
                ],
            ))
        elif p.kind == "location_fact":
            location = story.find_location(p.payload["name"])
            if location:
                location.descriptions.append(LocationDescription(
                    description=p.payload["description"],
                    timeline_ref=timeline_id, chapter_ref=chapter_meta.id, approved_at=_now(),
                ))

    character_refs = [
        story.find_character(d["name"]).id
        for d in detected_characters
        if story.find_character(d["name"])
    ]
    detected_location_names = [d["name"] for d in detected_locations]
    new_location_id = location_id
    if detected_location_names:
        matched = story.find_location(detected_location_names[0])
        if matched:
            new_location_id = matched.id

    chapter.paragraphs.append(Paragraph(
        sequence=len(chapter.paragraphs) + 1,
        content=paragraph_content,
        location_ref=new_location_id,
        timeline_ref=timeline_id,
        character_refs=character_refs,
    ))

    storage.save_chapter(story_id, chapter)
    storage.save_story(story)
