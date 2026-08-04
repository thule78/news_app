from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
from typing import Callable

from aa_content.models import (
    NarrationSection,
    ProductionBrief,
    ResearchClaim,
    SanitizationResult,
    TripRecord,
    YoutubePackaging,
)


def publish_trip_artifacts(
    workspace: Path, trip: TripRecord, itinerary: str
) -> None:
    """Write readable Trip exports from persisted state, swapping in atomically."""
    _publish_trip_directory(
        workspace,
        trip,
        lambda trip_directory: _render_trip_directory(trip_directory, trip, itinerary),
    )


def publish_itinerary_processing_artifacts(
    workspace: Path,
    trip: TripRecord,
    sanitization: SanitizationResult,
    normalized: dict[str, object],
    *,
    export_blocked: bool,
) -> None:
    """Write readable sanitization/normalization exports, swapping in atomically."""
    _publish_trip_directory(
        workspace,
        trip,
        lambda trip_directory: _render_itinerary_processing(
            trip_directory, trip, sanitization, normalized, export_blocked=export_blocked
        ),
    )


def publish_baseline_research_artifacts(
    workspace: Path, trip: TripRecord, claims: tuple[ResearchClaim, ...]
) -> None:
    """Write the human-readable Baseline Research brief, swapping in atomically."""
    _publish_trip_directory(
        workspace,
        trip,
        lambda trip_directory: _render_baseline_research(trip_directory, trip, claims),
    )


def publish_narration_artifacts(
    workspace: Path,
    trip: TripRecord,
    sections: tuple[NarrationSection, ...],
    *,
    word_count: int,
    estimated_minutes: float,
    warnings: tuple[str, ...],
) -> None:
    """Write the working narration draft, swapping in atomically."""
    _publish_trip_directory(
        workspace,
        trip,
        lambda trip_directory: _render_narration(
            trip_directory,
            sections,
            word_count=word_count,
            estimated_minutes=estimated_minutes,
            warnings=warnings,
        ),
    )


def publish_youtube_packaging_artifacts(
    workspace: Path, trip: TripRecord, packaging: YoutubePackaging
) -> None:
    """Write the working YouTube packaging draft, swapping in atomically."""
    _publish_trip_directory(
        workspace,
        trip,
        lambda trip_directory: _render_youtube_packaging(trip_directory, packaging),
    )


def publish_production_brief_artifacts(
    workspace: Path, trip: TripRecord, brief: ProductionBrief
) -> None:
    """Write the Markdown/JSON/CSV Production Brief and Pictory handoff files."""
    _publish_trip_directory(
        workspace,
        trip,
        lambda trip_directory: _render_production_brief(trip_directory, brief),
    )


def _publish_trip_directory(
    workspace: Path, trip: TripRecord, render: Callable[[Path], None]
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


def _recover_interrupted_swap(destination: Path, staging: Path, backup: Path) -> None:
    """Reconcile a directory swap left half-done by a prior crash."""
    if not destination.exists() and backup.exists():
        os.replace(backup, destination)
    elif destination.exists() and backup.exists():
        shutil.rmtree(backup)
    if staging.exists():
        shutil.rmtree(staging)


def _render_trip_directory(
    trip_directory: Path, trip: TripRecord, itinerary: str
) -> None:
    source_directory = trip_directory / "source" / f"r{trip.revision_number}"
    working_directory = trip_directory / "working"
    for directory in (source_directory, working_directory):
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise OSError(f"Managed artifact path is not a directory: {directory}")
        directory.mkdir(parents=True, exist_ok=True)

    metadata = {
        "trip_id": trip.trip_id,
        "name": trip.name,
        "slug": trip.slug,
        "created_at": trip.created_at,
        "current_itinerary_revision": f"r{trip.revision_number}",
        "current_editorial_package_version": trip.current_editorial_package_version,
    }
    revision_metadata = {
        "itinerary_revision_id": trip.itinerary_revision_id,
        "trip_id": trip.trip_id,
        "revision": f"r{trip.revision_number}",
    }
    _write_managed_file(source_directory / "original-itinerary.txt", itinerary)
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
            f"`{trip.current_editorial_package_version or 'NOT_AVAILABLE'}`\n"
        ),
    )
    _write_managed_file(
        trip_directory / "current-version.json",
        json.dumps(
            {"current_version": trip.current_editorial_package_version},
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
    revision_directory = trip_directory / "source" / f"r{trip.revision_number}"
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
        revision_directory / "sanitized-itinerary.txt", sanitization.sanitized_text
    )
    _write_managed_file(
        revision_directory / "sanitization-report.json",
        json.dumps(report, indent=2, sort_keys=True) + "\n",
    )
    _write_managed_file(
        revision_directory / "sanitization-report.md", _sanitization_markdown(report)
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


def _render_production_brief(trip_directory: Path, brief: ProductionBrief) -> None:
    working_directory = trip_directory / "working"
    if working_directory.is_symlink() or (
        working_directory.exists() and not working_directory.is_dir()
    ):
        raise OSError(f"Managed working path is not a directory: {working_directory}")
    working_directory.mkdir(parents=True, exist_ok=True)

    payload = {
        "locked_narration": brief.locked_narration,
        "scene_requirements": [
            {
                "section": s.section_key,
                "visual_meaning": s.visual_meaning,
                "location": s.location,
                "on_screen_text": s.on_screen_text,
            }
            for s in brief.scene_requirements
        ],
        "route_map_requirements": brief.route_map_requirements,
        "brand_direction": brief.brand_direction,
        "restrictions": list(brief.restrictions),
        "rights_and_ai_disclosure": brief.rights_and_ai_disclosure,
        "warnings": list(brief.warnings),
    }
    json_text = json.dumps(payload, indent=2, sort_keys=True) + "\n"

    lines = [
        "# Production Brief",
        "",
        "## Locked Narration",
        "",
        brief.locked_narration,
        "",
        "## Scene Requirements",
        "",
    ]
    for scene in brief.scene_requirements:
        lines.append(f"### {scene.section_key}")
        lines.append(f"- Visual meaning: {scene.visual_meaning}")
        lines.append(f"- Location: {scene.location or 'Not location-specific'}")
        lines.append(f"- On-screen text: {scene.on_screen_text or 'None'}")
        lines.append("")
    lines.extend(
        [
            "## Route Map Requirements",
            "",
            brief.route_map_requirements,
            "",
            "## Brand Direction",
            "",
            brief.brand_direction,
            "",
            "## Restrictions",
            "",
        ]
    )
    for restriction in brief.restrictions:
        lines.append(f"- {restriction}")
    lines.extend(["", "## Rights and AI Disclosure", "", brief.rights_and_ai_disclosure, ""])
    lines.extend(["## Acknowledged Warnings", ""])
    if brief.warnings:
        for warning in brief.warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("No warnings recorded.")
    markdown_text = "\n".join(lines) + "\n"

    csv_lines = ["section,visual_meaning,location,on_screen_text"]
    for scene in brief.scene_requirements:
        csv_lines.append(
            ",".join(
                _csv_field(value)
                for value in (
                    scene.section_key,
                    scene.visual_meaning,
                    scene.location or "",
                    scene.on_screen_text or "",
                )
            )
        )
    csv_text = "\n".join(csv_lines) + "\n"

    for base_name in ("production-brief", "pictory-handoff"):
        _write_managed_file(working_directory / f"{base_name}.json", json_text)
        _write_managed_file(working_directory / f"{base_name}.md", markdown_text)
        _write_managed_file(
            working_directory / f"{base_name}-scenes.csv", csv_text
        )


def _csv_field(value: str) -> str:
    escaped = value.replace('"', '""')
    return f'"{escaped}"'


def _render_youtube_packaging(
    trip_directory: Path, packaging: YoutubePackaging
) -> None:
    working_directory = trip_directory / "working"
    if working_directory.is_symlink() or (
        working_directory.exists() and not working_directory.is_dir()
    ):
        raise OSError(f"Managed working path is not a directory: {working_directory}")
    working_directory.mkdir(parents=True, exist_ok=True)

    payload = {
        "titles": [
            {"style": t.style, "text": t.text} for t in packaging.titles
        ],
        "description": packaging.description,
        "chapters": [
            {"title": c.title, "timestamp": c.timestamp_label}
            for c in packaging.chapters
        ],
        "thumbnail_brief": {
            "clear_idea": packaging.thumbnail_brief.clear_idea,
            "destination_cues": list(packaging.thumbnail_brief.destination_cues),
            "text_options": list(packaging.thumbnail_brief.text_options),
        },
        "keywords": [
            {
                "keyword": k.keyword,
                "search_intent": k.search_intent,
                "search_volume": k.search_volume,
                "competition": k.competition,
                "difficulty": k.difficulty,
            }
            for k in packaging.keywords
        ],
        "shorts": [{"title": s.title, "body": s.body} for s in packaging.shorts],
    }
    _write_managed_file(
        working_directory / "youtube-packaging.json",
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
    )

    lines = ["# YouTube Packaging", "", "## Titles", ""]
    for title in packaging.titles:
        lines.append(f"- [{title.style}] {title.text}")
    lines.extend(["", "## Description", "", packaging.description, ""])
    lines.extend(["## Chapters", ""])
    for chapter in packaging.chapters:
        lines.append(f"- {chapter.timestamp_label} {chapter.title}")
    lines.extend(["", "## Thumbnail Brief", ""])
    lines.append(f"- Clear idea: {packaging.thumbnail_brief.clear_idea}")
    lines.append(
        f"- Destination cues: {', '.join(packaging.thumbnail_brief.destination_cues)}"
    )
    lines.append(
        f"- Text options: {', '.join(packaging.thumbnail_brief.text_options)}"
    )
    lines.extend(["", "## Keywords", ""])
    for keyword in packaging.keywords:
        lines.append(
            f"- {keyword.keyword} — intent: {keyword.search_intent}, "
            f"volume: {keyword.search_volume}, competition: "
            f"{keyword.competition}, difficulty: {keyword.difficulty}"
        )
    lines.extend(["", "## Shorts", ""])
    for short in packaging.shorts:
        lines.extend([f"### {short.title}", "", short.body, ""])
    _write_managed_file(
        working_directory / "youtube-packaging.md", "\n".join(lines) + "\n"
    )


def _render_narration(
    trip_directory: Path,
    sections: tuple[NarrationSection, ...],
    *,
    word_count: int,
    estimated_minutes: float,
    warnings: tuple[str, ...],
) -> None:
    working_directory = trip_directory / "working"
    if working_directory.is_symlink() or (
        working_directory.exists() and not working_directory.is_dir()
    ):
        raise OSError(f"Managed working path is not a directory: {working_directory}")
    working_directory.mkdir(parents=True, exist_ok=True)

    payload = {
        "word_count": word_count,
        "estimated_minutes": estimated_minutes,
        "warnings": list(warnings),
        "sections": [
            {"key": s.key, "title": s.title, "body": s.body} for s in sections
        ],
    }
    _write_managed_file(
        working_directory / "narration.json",
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
    )
    lines = [
        "# Narration",
        "",
        f"- Word count: {word_count}",
        f"- Estimated duration: {estimated_minutes} min",
    ]
    if warnings:
        lines.append("")
        for warning in warnings:
            lines.append(f"> WARNING: {warning}")
    lines.append("")
    for section in sections:
        lines.extend([f"## {section.title}", "", section.body, ""])
    _write_managed_file(working_directory / "narration.md", "\n".join(lines) + "\n")


def _render_baseline_research(
    trip_directory: Path, trip: TripRecord, claims: tuple[ResearchClaim, ...]
) -> None:
    revision_directory = trip_directory / "source" / f"r{trip.revision_number}"
    if revision_directory.is_symlink() or not revision_directory.is_dir():
        raise OSError(
            f"Managed revision path is not a directory: {revision_directory}"
        )
    payload = {
        "claims": [
            {
                "category": claim.category,
                "statement": claim.statement,
                "evidence_status": claim.evidence_status,
                "recheck_date": claim.recheck_date,
                "stale": claim.stale,
                "sources": [
                    {
                        "url": source.url,
                        "title": source.title,
                        "publisher": source.publisher,
                        "published_at": source.published_at,
                        "content_hash": source.content_hash,
                        "locator": source.locator,
                        "evidence_summary": source.evidence_summary,
                    }
                    for source in claim.sources
                ],
            }
            for claim in claims
        ]
    }
    _write_managed_file(
        revision_directory / "baseline-research.json",
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
    )
    _write_managed_file(
        revision_directory / "baseline-research.md",
        _baseline_research_markdown(claims),
    )


def _baseline_research_markdown(claims: tuple[ResearchClaim, ...]) -> str:
    lines = ["# Baseline Research", ""]
    missing = [claim for claim in claims if claim.evidence_status == "UNKNOWN"]
    lines.extend(
        [
            f"- Claims: {len(claims)}",
            f"- Missing Information: {len(missing)}",
            "",
            "## Claims",
            "",
        ]
    )
    for claim in claims:
        recheck = f", recheck {claim.recheck_date}" if claim.recheck_date else ""
        lines.append(
            f"### {claim.category} — `{claim.evidence_status}`{recheck}"
        )
        lines.append("")
        if claim.stale:
            lines.append(
                "**STALE — refresh failed; this Claim is past its Recheck "
                "Date and remains reviewable, not authoritative.**"
            )
            lines.append("")
        lines.append(claim.statement)
        lines.append("")
        if claim.sources:
            for source in claim.sources:
                lines.append(
                    f"- [{source.title}]({source.url}) — {source.publisher}: "
                    f"{source.evidence_summary}"
                )
        else:
            lines.append("No current sources found.")
        lines.append("")
    lines.extend(
        [
            "## Missing Information",
            "",
        ]
    )
    if missing:
        for claim in missing:
            lines.append(f"- {claim.category}: no current sources found.")
    else:
        lines.append("No Missing Information recorded.")
    return "\n".join(lines) + "\n"


def _artifact_list(container: dict[str, object], key: str) -> list[object]:
    value = container.get(key, [])
    return value if isinstance(value, list) else []


def _write_managed_file(path: Path, content: str) -> None:
    if path.is_symlink():
        path.unlink()
    path.write_text(content, encoding="utf-8")
