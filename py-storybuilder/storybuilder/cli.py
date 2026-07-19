import argparse
import json

from . import export, growth, storage
from .models import Chapter, ChapterMeta, Character, CharacterBackground, Location, LocationDescription, Story, Timeline


def cmd_new(args: argparse.Namespace) -> None:
    title = input("Title: ").strip()
    style = input("Style: ").strip()
    synopsis = input("Synopsis/arc: ").strip()
    world_facts = input("World facts: ").strip()
    constraints_raw = input("Constraints (comma-separated, optional): ").strip()
    constraints = [c.strip() for c in constraints_raw.split(",") if c.strip()]

    story_id = storage.slugify(title)
    if storage.story_exists(story_id):
        print(f"Story '{story_id}' already exists.")
        return

    timeline = Timeline(id=storage.new_id("tl"), name="Act 1")
    story = Story(
        id=story_id, title=title, style=style, synopsis=synopsis,
        world_facts=world_facts, constraints=constraints, timelines=[timeline],
    )

    print("\nSeed characters (blank name to stop):")
    while True:
        name = input("  Character name: ").strip()
        if not name:
            break
        facts_raw = input("  Facts (semicolon-separated, optional): ").strip()
        background = [
            CharacterBackground(type="Facts", description=f.strip(), timeline_ref=timeline.id)
            for f in facts_raw.split(";") if f.strip()
        ]
        story.characters.append(Character(id=storage.new_id("char"), name=name, background=background))

    print("\nSeed locations (blank name to stop):")
    while True:
        name = input("  Location name: ").strip()
        if not name:
            break
        desc = input("  Description (optional): ").strip()
        descriptions = [LocationDescription(description=desc, timeline_ref=timeline.id)] if desc else []
        story.locations.append(Location(id=storage.new_id("loc"), name=name, descriptions=descriptions))

    chapter_title = input("\nFirst chapter title [Chapter 1]: ").strip() or "Chapter 1"
    chapter_synopsis = input("First chapter synopsis (optional): ").strip()
    story.chapters.append(ChapterMeta(id="01", title=chapter_title, synopsis=chapter_synopsis, sequence=1))

    storage.save_story(story)
    storage.save_chapter(story_id, Chapter(id="01", title=chapter_title, sequence=1))

    print(f"\nCreated story '{story_id}'.")


def cmd_step(args: argparse.Namespace) -> None:
    growth.run_step(args.story_id)


def cmd_show(args: argparse.Namespace) -> None:
    story = storage.load_story(args.story_id)
    print(json.dumps(story.to_dict(), indent=2))


def cmd_export(args: argparse.Namespace) -> None:
    print(export.export_book(args.story_id))


def cmd_list(args: argparse.Namespace) -> None:
    for story_id in storage.list_stories():
        print(story_id)


def main() -> None:
    parser = argparse.ArgumentParser(prog="storybuilder")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("new")

    step_parser = sub.add_parser("step")
    step_parser.add_argument("story_id")

    show_parser = sub.add_parser("show")
    show_parser.add_argument("story_id")

    export_parser = sub.add_parser("export")
    export_parser.add_argument("story_id")

    sub.add_parser("list")

    args = parser.parse_args()
    handlers = {
        "new": cmd_new,
        "step": cmd_step,
        "show": cmd_show,
        "export": cmd_export,
        "list": cmd_list,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
