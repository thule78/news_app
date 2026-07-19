from .models import Chapter, Story

MAX_WORDS = 800


def _word_count(text: str) -> int:
    return len(text.split())


def generate_summary(story: Story, chapters: list[Chapter], timeline_id: str, max_words: int = MAX_WORDS) -> str:
    timeline = next((t for t in story.timelines if t.id == timeline_id), None)
    if timeline is None:
        return ""

    lines: list[str] = []

    date_range = ""
    if timeline.start_date or timeline.stop_date:
        date_range = f" ({timeline.start_date or '?'} to {timeline.stop_date or '?'})"
    lines.append(f"Timeline: {timeline.name}{date_range}")
    if timeline.description:
        lines.append(timeline.description)
    lines.append("")

    characters = [c for c in story.active_characters() if any(b.timeline_ref == timeline_id for b in c.background)]
    if characters:
        lines.append("Characters active in this timeline:")
        for c in characters:
            attrs = "; ".join(b.description for b in c.background if b.timeline_ref == timeline_id)
            lines.append(f"- {c.name}: {attrs}" if attrs else f"- {c.name}")
        lines.append("")

    locations = [l for l in story.active_locations() if any(d.timeline_ref == timeline_id for d in l.descriptions)]
    if locations:
        lines.append("Locations in this timeline:")
        for loc in locations:
            desc = "; ".join(d.description for d in loc.descriptions if d.timeline_ref == timeline_id)
            lines.append(f"- {loc.name}: {desc}" if desc else f"- {loc.name}")
        lines.append("")

    event_lines: list[str] = []
    for chapter in sorted(chapters, key=lambda c: c.sequence):
        for paragraph in sorted(chapter.paragraphs, key=lambda p: p.sequence):
            if paragraph.timeline_ref != timeline_id:
                continue
            char_names = [story.find_character_by_id(ref) for ref in paragraph.character_refs]
            chars = ", ".join(filter(None, char_names))
            location = story.find_location_by_id(paragraph.location_ref)
            loc_part = f" at {location}" if location else ""
            event_lines.append(f"- {chapter.title}, P{paragraph.sequence}: {chars}{loc_part}")

    if event_lines:
        lines.append("Events (chronological):")
        current_words = sum(_word_count(l) for l in lines)
        kept: list[str] = []
        for line in reversed(event_lines):
            if current_words + _word_count(line) > max_words and kept:
                omitted = len(event_lines) - len(kept)
                kept.insert(0, f"- ... and {omitted} earlier events")
                break
            kept.insert(0, line)
            current_words += _word_count(line)
        lines.extend(kept)

    return "\n".join(lines).rstrip()
