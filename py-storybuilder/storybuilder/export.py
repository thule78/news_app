from . import storage


def export_book(story_id: str) -> str:
    story = storage.load_story(story_id)
    lines = [f"# {story.title}", ""]

    for chapter_meta in sorted(story.chapters, key=lambda c: c.sequence):
        chapter = storage.load_chapter(story_id, chapter_meta.id)
        lines.append(f"## {chapter.title}")
        lines.append("")
        for paragraph in sorted(chapter.paragraphs, key=lambda p: p.sequence):
            lines.append(paragraph.content)
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
