from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
from typing import Callable

from aa_content.models import SanitizationResult, TripRecord


def publish_trip_artifacts(
    workspace: Path, trip: TripRecord, itinerary: str
) -> None:
    _publish_trip_directory(
        workspace,
        trip,
        lambda trip_directory: _render_trip_directory(
            trip_directory, trip, itinerary
        ),
    )


def publish_itinerary_processing_artifacts(
    workspace: Path,
    trip: TripRecord,
    sanitization: SanitizationResult,
    normalized: dict[str, object],
    *,
    export_blocked: bool,
) -> None:
    _publish_trip_directory(
        workspace,
        trip,
        lambda trip_directory: _render_itinerary_processing(
            trip_directory,
            trip,
            sanitization,
            normalized,
            export_blocked=export_blocked,
        ),
    )


def _publish_trip_directory(
    workspace: Path,
    trip: TripRecord,
    render: Callable[[Path], None],
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
        render(staging)

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


def _render_itinerary_processing(
    trip_directory: Path,
    trip: TripRecord,
    sanitization: SanitizationResult,
    normalized: dict[str, object],
    *,
    export_blocked: bool,
) -> None:
    revision_directory = (
        trip_directory / "source" / f"r{trip.revision_number}"
    )
    if revision_directory.is_symlink() or not revision_directory.is_dir():
        raise OSError(
            f"Managed revision path is not a directory: {revision_directory}"
        )
    findings = [
        {
            "category": finding.category,
            "source_locator": finding.source_locator,
            "review_status": finding.review_status,
        }
        for finding in sanitization.findings
    ]
    report = {
        "itinerary_revision_id": trip.itinerary_revision_id,
        "status": sanitization.status,
        "findings": findings,
        "export_blocked": export_blocked,
    }
    _write_managed_file(
        revision_directory / "sanitized-itinerary.txt",
        sanitization.sanitized_text,
    )
    _write_managed_file(
        revision_directory / "sanitization-report.json",
        json.dumps(report, indent=2, sort_keys=True) + "\n",
    )
    _write_managed_file(
        revision_directory / "sanitization-report.md",
        _sanitization_markdown(report),
    )
    _write_managed_file(
        revision_directory / "normalized-itinerary.json",
        json.dumps(normalized, indent=2, sort_keys=True) + "\n",
    )
    _write_managed_file(
        revision_directory / "normalized-itinerary.md",
        _normalized_itinerary_markdown(normalized),
    )


def _sanitization_markdown(report: dict[str, object]) -> str:
    lines = [
        "# Sanitization Report",
        "",
        f"- Status: `{report['status']}`",
        f"- Export Blocked: `{'YES' if report['export_blocked'] else 'NO'}`",
        "",
        "## Findings",
        "",
    ]
    findings = report["findings"]
    if not isinstance(findings, list) or not findings:
        lines.append("No possible Supplier Data detected.")
    else:
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            lines.append(
                f"- `{finding['source_locator']}` — `{finding['category']}` "
                f"— review `{finding['review_status']}`"
            )
    return "\n".join(lines) + "\n"


def _normalized_itinerary_markdown(normalized: dict[str, object]) -> str:
    lines = ["# Normalized Itinerary", ""]
    days = normalized.get("days", [])
    if isinstance(days, list):
        for day in days:
            if not isinstance(day, dict):
                continue
            lines.extend(
                [
                    f"## Day {day['day_number']}",
                    "",
                    f"- Source: `{day['source_locator']}`",
                    f"- Route Legs: {len(_artifact_list(day, 'route_legs'))}",
                    f"- Overnight Stops: {len(_artifact_list(day, 'overnight_stops'))}",
                    f"- Activities: {len(_artifact_list(day, 'activities'))}",
                    f"- Accommodation: {len(_artifact_list(day, 'accommodation'))}",
                    f"- Meals: {len(_artifact_list(day, 'meals'))}",
                    f"- Transport: {len(_artifact_list(day, 'transport'))}",
                    (
                        "- Practical Constraints: "
                        f"{len(_artifact_list(day, 'practical_constraints'))}"
                    ),
                    "",
                ]
            )
    missing = normalized.get("missing_information", [])
    conflicts = normalized.get("fact_conflicts", [])
    lines.extend(
        [
            "## Review",
            "",
            (
                "- Missing Information: "
                f"{len(missing) if isinstance(missing, list) else 0}"
            ),
            f"- Fact Conflicts: {len(conflicts) if isinstance(conflicts, list) else 0}",
            "",
            "### Missing Information",
            "",
        ]
    )
    if isinstance(missing, list) and missing:
        for item in missing:
            if isinstance(item, dict):
                lines.append(
                    f"- {item.get('scope', 'Trip')}: "
                    f"`{item.get('field', 'unknown')}` — "
                    f"`{item.get('status', 'MISSING_INFORMATION')}`"
                )
    else:
        lines.append("No Missing Information recorded.")
    lines.extend(["", "### Fact Conflicts", ""])
    if isinstance(conflicts, list) and conflicts:
        for conflict in conflicts:
            if isinstance(conflict, dict):
                lines.append(
                    f"- {conflict.get('subject', 'Unspecified Trip fact')}: "
                    f"{conflict.get('reason', 'requires review')}"
                )
    else:
        lines.append("No Fact Conflicts recorded.")
    return "\n".join(lines) + "\n"


def _artifact_list(container: dict[str, object], key: str) -> list[object]:
    value = container.get(key, [])
    return value if isinstance(value, list) else []


def _write_managed_file(path: Path, content: str) -> None:
    if path.is_symlink():
        path.unlink()
    path.write_text(content, encoding="utf-8")
