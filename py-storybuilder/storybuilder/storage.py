import json
import re
import uuid
from pathlib import Path

from . import config
from .models import Chapter, Story


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "story"


def story_dir(story_id: str) -> Path:
    return config.STORIES_DIR / story_id


def story_path(story_id: str) -> Path:
    return story_dir(story_id) / "story.json"


def chapter_path(story_id: str, chapter_id: str) -> Path:
    return story_dir(story_id) / "chapters" / f"{chapter_id}.json"


def list_stories() -> list[str]:
    if not config.STORIES_DIR.exists():
        return []
    return sorted(p.name for p in config.STORIES_DIR.iterdir() if (p / "story.json").exists())


def story_exists(story_id: str) -> bool:
    return story_path(story_id).exists()


def load_story(story_id: str) -> Story:
    return Story.from_dict(json.loads(story_path(story_id).read_text()))


def save_story(story: Story) -> None:
    path = story_path(story.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(story.to_dict(), indent=2))


def load_chapter(story_id: str, chapter_id: str) -> Chapter:
    return Chapter.from_dict(json.loads(chapter_path(story_id, chapter_id).read_text()))


def save_chapter(story_id: str, chapter: Chapter) -> None:
    path = chapter_path(story_id, chapter.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(chapter.to_dict(), indent=2))


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"
