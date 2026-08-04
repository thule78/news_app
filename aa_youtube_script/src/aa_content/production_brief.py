from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from aa_content.artifacts import publish_production_brief_artifacts
from aa_content.errors import UserFacingError
from aa_content.models import (
    NarrationSection,
    ProductionBrief,
    ProductionBriefOutcome,
    ProductionBriefResult,
    SceneRequirement,
)
from aa_content.persistence import WorkspaceRepository
from aa_content.validation import compute_draft_signature, validate_package

_PRICE_PATTERN = re.compile(
    r"[$€£¥]\s?\d|\b\d+(?:\.\d+)?\s?(?:usd|eur|gbp|jpy|vnd|dollars?)\b",
    re.IGNORECASE,
)

_VISUAL_MEANING_BY_SECTION: dict[str, str] = {
    "hook": (
        "Establish the central viewer question visually, grounded in the "
        "actual location rather than generic stock imagery."
    ),
    "journey_at_a_glance": (
        "A wide or overview visual conveying the Trip's scale and geography."
    ),
    "route": (
        "Sequential visuals following the described route in order; convey "
        "the terrain and pace implied by the stated durations."
    ),
    "reality_check": (
        "Supporting visuals for the stated practical facts (access, "
        "transport, conditions); do not dramatize beyond stated Evidence."
    ),
    "who_it_suits": (
        "Traveller-perspective visuals matching the stated conditions; do "
        "not depict specific individuals as a guarantee of experience."
    ),
    "who_should_avoid_it": (
        "Visuals illustrating the stated limiting conditions honestly; "
        "avoid alarmist framing."
    ),
    "intensity": (
        "Visual pacing matching the stated Intensity Rating; do not "
        "exaggerate difficulty beyond the Evidence."
    ),
    "adventure_asia_verdict": (
        "Reflective, summary visual tone, clearly distinct from the factual "
        "b-roll used elsewhere — this section is Editorial Judgment, not a "
        "fact statement."
    ),
    "cta": (
        "Clear on-screen direction toward the Trip page; no urgency "
        "graphics beyond the controlled CTA text."
    ),
}

_BRAND_DIRECTION = (
    "Neutral, evidence-based tone throughout. Avoid unsupported safety "
    "guarantees, medical conclusions, misleading exclusivity claims, and "
    "restricted superlative brand phrases (e.g. \"the best in the world\"). "
    "Narration and on-screen text are locked; do not rewrite them."
)

_RESTRICTIONS = (
    "No Price Information in any on-screen text, caption, or overlay.",
    "This brief does not prescribe vendor-specific transitions, effects, "
    "or automated rewriting; the vendor selects execution within these "
    "requirements.",
    "Do not rewrite or paraphrase the locked narration text.",
    "Do not select or license specific footage on Adventure Asia's behalf.",
)

_RIGHTS_AND_AI_DISCLOSURE = (
    "This package does not confirm or grant footage, image, or music "
    "licensing. The production vendor is responsible for confirming rights "
    "for any asset used. Any AI-generated or AI-assisted visual element "
    "must be disclosed per the publishing platform's current policy."
)


def generate_production_brief(
    workspace: Path, trip_id: str
) -> ProductionBriefResult:
    repository = WorkspaceRepository(workspace)
    if not repository.database_path.is_file():
        raise UserFacingError(
            f"Workspace is not initialized: run init for {workspace.resolve()}"
        )
    trip = repository.load_current_trip(trip_id)
    if trip is None:
        raise UserFacingError(f"Trip not found: {trip_id}")

    angle = repository.load_current_angle(trip.trip_id)
    if angle is None:
        raise UserFacingError(
            "No approved Content Angle: run `trip angle approve` first."
        )
    stored_revision = repository.load_content_angle_revision(angle.angle_id)
    if stored_revision != trip.itinerary_revision_id:
        raise UserFacingError(
            "Itinerary Revision changed since the Content Angle was "
            "approved; approve a Content Angle for the current revision "
            "first."
        )

    version = repository.load_latest_version(trip.trip_id)
    if version is None:
        raise UserFacingError(
            "No submitted version: run `trip submit-review` first."
        )
    if (
        version.itinerary_revision_id != trip.itinerary_revision_id
        or version.angle_id != angle.angle_id
    ):
        raise UserFacingError(
            "The latest submitted version no longer matches the current "
            "Trip state; run `trip submit-review` again first."
        )

    # The only non-overridable Export Block: unresolved Supplier Data.
    if version.export_blocked:
        raise UserFacingError(
            "Export is blocked: unresolved Supplier Data remains in the "
            "current Itinerary Revision. Resolve it before generating the "
            "Production Brief."
        )

    loaded_narration = repository.load_narration(
        trip.itinerary_revision_id, angle.angle_id
    )
    if loaded_narration is None:
        raise UserFacingError("No narration to brief: run `trip narrate` first.")
    sections, _word_count, _estimated_minutes, _overall, _days, _warnings = (
        loaded_narration
    )
    live_signature = compute_draft_signature(
        trip.itinerary_revision_id, angle.angle_id, sections
    )
    if live_signature != version.narration_signature:
        raise UserFacingError(
            f"Narration has changed since v{version.version_number} was "
            "submitted; run `trip submit-review` again first."
        )

    report = validate_package(workspace, trip_id)
    if report.unacknowledged_warnings:
        pending = ", ".join(f.finding_id for f in report.unacknowledged_warnings)
        raise UserFacingError(
            "Unacknowledged validation warnings must be acknowledged before "
            f"the Production Brief can be generated: {pending}"
        )
    acknowledgment_by_finding = {a.finding_id: a for a in report.acknowledgments}
    warning_lines = tuple(
        f"{finding.message} (acknowledged by "
        f"{acknowledgment_by_finding[finding.finding_id].approver})"
        for finding in report.findings
        if finding.severity == "WARNING"
    )

    normalized = repository.load_normalized_itinerary(trip.itinerary_revision_id) or {}
    brief = _build_brief(trip.name, sections, normalized, warning_lines)
    payload = _serialize(brief)
    _guard_no_price_information(payload)
    payload_json = json.dumps(payload, sort_keys=True)
    content_signature = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    existing_signature = repository.load_production_brief_signature(
        trip.itinerary_revision_id, angle.angle_id
    )
    if existing_signature is None:
        outcome = ProductionBriefOutcome.GENERATED
    elif existing_signature == content_signature:
        outcome = ProductionBriefOutcome.REUSED
    else:
        outcome = ProductionBriefOutcome.REGENERATED

    repository.persist_production_brief(
        trip.itinerary_revision_id, angle.angle_id, payload_json, content_signature
    )
    publish_production_brief_artifacts(workspace, trip, brief)
    return ProductionBriefResult(
        trip=trip, outcome=outcome, brief=brief, content_signature=content_signature
    )


def _build_brief(
    trip_name: str,
    sections: tuple[NarrationSection, ...],
    normalized: dict[str, object],
    warning_lines: tuple[str, ...],
) -> ProductionBrief:
    locked_narration = "LOCKED — do not rewrite:\n\n" + "\n\n".join(
        f"[{section.title}]\n{section.body}" for section in sections
    )
    legs = _route_legs(normalized)
    scene_requirements = tuple(
        SceneRequirement(
            section_key=section.key,
            visual_meaning=_VISUAL_MEANING_BY_SECTION.get(
                section.key, "Supporting visual conveying this section's content."
            ),
            location=_location_for_section(section.key, legs),
            on_screen_text=_on_screen_text_for_section(section),
        )
        for section in sections
    )
    if legs:
        stops = " -> ".join([legs[0][0]] + [leg[1] for leg in legs])
        route_map_requirements = (
            f"Highlight the route for {trip_name}: {stops}. Mark overnight "
            "stops where the itinerary specifies them. Do not select a "
            "specific mapping product or style here."
        )
    else:
        route_map_requirements = (
            f"No specific route legs are recorded for {trip_name}; a route "
            "map is not required."
        )
    return ProductionBrief(
        locked_narration=locked_narration,
        scene_requirements=scene_requirements,
        route_map_requirements=route_map_requirements,
        brand_direction=_BRAND_DIRECTION,
        restrictions=_RESTRICTIONS,
        rights_and_ai_disclosure=_RIGHTS_AND_AI_DISCLOSURE,
        warnings=warning_lines,
    )


def _location_for_section(
    section_key: str, legs: list[tuple[str, str]]
) -> str | None:
    if section_key not in ("route", "journey_at_a_glance") or not legs:
        return None
    return f"{legs[0][0]} to {legs[-1][1]}"


def _on_screen_text_for_section(section: NarrationSection) -> str | None:
    if section.key == "cta":
        return "See the Trip page"
    if section.key == "adventure_asia_verdict":
        return "Adventure Asia's take"
    return None


def _route_legs(normalized: dict[str, object]) -> list[tuple[str, str]]:
    legs: list[tuple[str, str]] = []
    days = normalized.get("days", [])
    if not isinstance(days, list):
        return legs
    for day in days:
        if not isinstance(day, dict):
            continue
        route_legs = day.get("route_legs", [])
        if not isinstance(route_legs, list):
            continue
        for leg in route_legs:
            if isinstance(leg, dict) and "from" in leg and "to" in leg:
                legs.append((str(leg["from"]), str(leg["to"])))
    return legs


def _serialize(brief: ProductionBrief) -> dict[str, object]:
    return {
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


def _guard_no_price_information(payload: dict[str, object]) -> None:
    blob = json.dumps(payload)
    if _PRICE_PATTERN.search(blob):
        raise RuntimeError("Price Information detected in Production Brief output.")
