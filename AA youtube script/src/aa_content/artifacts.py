from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

from aa_content.models import TripRecord


def publish_trip_artifacts(
    workspace: Path, trip: TripRecord, itinerary: str
) -> None:
    outputs_directory = workspace / "outputs"
    outputs_directory.mkdir(exist_ok=True)
    destination = outputs_directory / trip.directory_name
    if destination.is_symlink():
        raise OSError("Trip artifact directory cannot be a symbolic link.")

    staging = outputs_directory / f".staging-{trip.trip_id}"
    backup = outputs_directory / f".backup-{trip.trip_id}"
    if staging.is_symlink() or backup.is_symlink():
        raise OSError("Trip artifact recovery paths cannot be symbolic links.")
    _recover_interrupted_swap(destination, staging, backup)

    try:
        if destination.exists():
            shutil.copytree(destination, staging, symlinks=True)
        else:
            staging.mkdir()
        _render_trip_directory(staging, trip, itinerary)

        if destination.exists():
            os.replace(destination, backup)
        os.replace(staging, destination)
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if not destination.exists() and backup.exists():
            os.replace(backup, destination)
        if staging.exists():
            shutil.rmtree(staging)
        raise


def _recover_interrupted_swap(
    destination: Path, staging: Path, backup: Path
) -> None:
    if not destination.exists() and backup.exists():
        os.replace(backup, destination)
    elif destination.exists() and backup.exists():
        shutil.rmtree(backup)
    if staging.exists():
        shutil.rmtree(staging)


def _render_trip_directory(
    trip_directory: Path, trip: TripRecord, itinerary: str
) -> None:
    source_root = trip_directory / "source"
    source_directory = source_root / f"r{trip.revision_number}"
    working_directory = trip_directory / "working"
    for directory in (source_root, source_directory, working_directory):
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise OSError(f"Managed artifact path is not a directory: {directory}")
        directory.mkdir(parents=True, exist_ok=True)

    current_package_version = trip.current_editorial_package_version
    metadata = {
        "trip_id": trip.trip_id,
        "name": trip.name,
        "slug": trip.slug,
        "created_at": trip.created_at,
        "current_itinerary_revision": f"r{trip.revision_number}",
        "current_editorial_package_version": current_package_version,
    }
    revision_metadata = {
        "itinerary_revision_id": trip.itinerary_revision_id,
        "trip_id": trip.trip_id,
        "revision": f"r{trip.revision_number}",
        "source_kind": "PASTED_TEXT",
    }
    _write_managed_file(
        source_directory / "original-itinerary.txt",
        itinerary,
    )
    _write_managed_file(
        source_directory / "revision.json",
        json.dumps(revision_metadata, indent=2, sort_keys=True) + "\n",
    )
    _write_managed_file(
        trip_directory / "trip.json",
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
    )
    _write_managed_file(
        trip_directory / "trip.md",
        (
            f"# {trip.name}\n\n"
            f"- Trip ID: `{trip.trip_id}`\n"
            f"- Slug: `{trip.slug}`\n"
            f"- Current Itinerary Revision: `r{trip.revision_number}`\n"
            f"- Current Editorial Package Version: "
            f"`{current_package_version or 'NOT_AVAILABLE'}`\n"
        ),
    )
    _write_managed_file(
        trip_directory / "current-version.json",
        json.dumps(
            {"current_version": current_package_version},
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )


def _write_managed_file(path: Path, content: str) -> None:
    if path.is_symlink():
        path.unlink()
    path.write_text(content, encoding="utf-8")
