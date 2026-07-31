from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

from aa_content.config import load_openai_config
from aa_content.errors import StageExecutionError, UserFacingError
from aa_content.trip_workflow import create_trip, inspect_trip
from aa_content.workspace import initialize_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aa-content")
    parser.add_argument(
        "--workspace",
        required=True,
        type=Path,
        help="Workspace containing aa_content.db and Trip artifacts.",
    )

    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Initialize a shared Adventure Asia workspace.")

    trip_parser = commands.add_parser("trip", help="Manage Trips.")
    trip_commands = trip_parser.add_subparsers(dest="trip_command", required=True)
    create_parser = trip_commands.add_parser(
        "create", help="Create a Trip from itinerary text pasted through stdin."
    )
    create_parser.add_argument("--name", required=True, help="Readable Trip name.")
    create_parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate readable Trip artifacts from persisted state.",
    )
    show_parser = trip_commands.add_parser(
        "show", help="Inspect persisted Trip and workflow state."
    )
    show_parser.add_argument("--trip-id", required=True, help="Stable Trip ID.")

    config_parser = commands.add_parser("config", help="Validate local configuration.")
    config_commands = config_parser.add_subparsers(
        dest="config_command", required=True
    )
    config_commands.add_parser(
        "check-openai",
        help="Verify that OPENAI_API_KEY is available from the workspace .env.",
    )
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    options = build_parser().parse_args(arguments)

    try:
        if options.command == "init":
            reused = initialize_workspace(options.workspace)
            state = "already initialized" if reused else "initialized"
            print(f"Workspace {state}: {options.workspace.resolve()}")
            return 0

        if options.command == "trip" and options.trip_command == "create":
            result = create_trip(
                options.workspace,
                options.name,
                sys.stdin.read(),
                force=options.force,
            )
            print(f"Trip {result.outcome}: {result.name}")
            print(f"Trip ID: {result.trip_id}")
            print(f"Itinerary Revision: r{result.revision_number}")
            return 0

        if options.command == "trip" and options.trip_command == "show":
            result = inspect_trip(options.workspace, options.trip_id)
            print(f"Trip: {result.name}")
            print(f"Trip ID: {result.trip_id}")
            print(f"Slug: {result.slug}")
            print(f"Current Itinerary Revision: r{result.revision_number}")
            print(f"Trip Creation: {result.creation_status}")
            print(f"Source: {result.source_path.as_posix()}")
            return 0

        if options.command == "config" and options.config_command == "check-openai":
            load_openai_config(options.workspace)
            print("OpenAI configuration ready.")
            return 0
    except StageExecutionError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except UserFacingError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    return 2
