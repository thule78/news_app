from __future__ import annotations

import hashlib
from pathlib import Path
import re

from aa_content.artifacts import publish_narration_artifacts
from aa_content.errors import StageExecutionError, UserFacingError
from aa_content.models import (
    DayIntensity,
    EvidenceStatus,
    NarrationOutcome,
    NarrationResult,
    NarrationSection,
    ResearchCategory,
    StageStatus,
)
from aa_content.persistence import WorkspaceRepository
from aa_content.research_synthesis import category_label
from aa_content.sanitization import sanitize_itinerary

NARRATION_WORDS_PER_MINUTE = 130
TARGET_MINUTES_LOW = 7.0
TARGET_MINUTES_HIGH = 10.0

_PROMISE_KEYWORDS = (
    "guarantee", "guaranteed", "we provide", "we will arrange", "included",
    "we include", "we ensure", "promise",
)
_PRICE_PATTERN = re.compile(
    r"[$€£¥]\s?\d|\b\d+(?:\.\d+)?\s?(?:usd|eur|gbp|jpy|vnd|dollars?)\b",
    re.IGNORECASE,
)

_REALITY_CHECK_CATEGORIES: tuple[ResearchCategory, ...] = (
    ResearchCategory.ACCESS,
    ResearchCategory.ROUTE_RULES,
    ResearchCategory.SEASONALITY,
    ResearchCategory.CROWDS,
    ResearchCategory.INDEPENDENT_TRANSPORT,
    ResearchCategory.OFFICIAL_ADVISORY,
)


def validate_editorial_notes(notes: str) -> str:
    """Reject Supplier Data or promise-shaped wording before it enters narration."""
    stripped = notes.strip()
    if not stripped:
        return ""
    sanitized = sanitize_itinerary(stripped)
    if sanitized.findings:
        raise UserFacingError(
            "Editorial Notes contain possible Supplier Data; remove it "
            "before it can support narration."
        )
    lowered = stripped.lower()
    for keyword in _PROMISE_KEYWORDS:
        if keyword in lowered:
            raise UserFacingError(
                "Editorial Notes read as a Product Promise "
                f'("{keyword}"); rephrase as Editorial Judgment instead of '
                "a commitment."
            )
    return stripped


def generate_narration(
    workspace: Path,
    trip_id: str,
    *,
    editorial_notes: str = "",
    force: bool = False,
) -> NarrationResult:
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

    normalized = repository.load_normalized_itinerary(trip.itinerary_revision_id)
    if normalized is None:
        raise UserFacingError(
            "Itinerary Revision has not been processed: run `trip process` "
            "first."
        )

    clean_notes = validate_editorial_notes(editorial_notes)
    input_hash = _content_hash(f"{trip.itinerary_revision_id}\0{clean_notes}")
    stage = repository.find_narration_stage(angle.angle_id, input_hash)

    if stage is not None and stage.status is StageStatus.COMPLETED and not force:
        outcome = NarrationOutcome.REUSED
    else:
        if stage is None:
            stage, attempt = repository.start_narration(
                trip, angle.angle_id, input_hash
            )
            outcome = NarrationOutcome.GENERATED
        else:
            attempt = repository.start_retry(stage)
            outcome = (
                NarrationOutcome.REGENERATED if force else NarrationOutcome.RESUMED
            )

        research_claims = [
            claim
            for claim in repository.load_research_claims(trip.itinerary_revision_id)
            if claim.category != ResearchCategory.ANGLE_SUPPORT
        ]
        angle_claim = repository.load_angle_research_claim(
            trip.itinerary_revision_id, angle.angle_id
        )

        try:
            day_intensities, overall_intensity = _compute_intensities(normalized)
            sections = _build_sections(
                trip.name,
                normalized,
                research_claims,
                angle,
                angle_claim,
                clean_notes,
                overall_intensity,
                day_intensities,
            )
            _guard_no_price_information(sections)
            word_count = sum(len(section.body.split()) for section in sections)
            estimated_minutes = round(word_count / NARRATION_WORDS_PER_MINUTE, 1)
            warnings: list[str] = []
            if estimated_minutes < TARGET_MINUTES_LOW:
                warnings.append(
                    "Narration is shorter than the 7-10 minute target "
                    f"({estimated_minutes} min) because available Evidence "
                    "is limited; filler was not added."
                )
            repository.persist_narration(
                trip.trip_id,
                trip.itinerary_revision_id,
                angle.angle_id,
                sections,
                clean_notes or None,
                word_count,
                estimated_minutes,
                overall_intensity,
                day_intensities,
                tuple(warnings),
            )
            publish_narration_artifacts(
                workspace,
                stage.trip,
                sections,
                word_count=word_count,
                estimated_minutes=estimated_minutes,
                warnings=tuple(warnings),
            )
        except Exception as error:
            try:
                repository.fail_attempt(stage, attempt, "NARRATION_FAILED")
            except Exception as persistence_error:
                raise StageExecutionError(
                    "Narration failed while saving recovery state; retry "
                    "the same command."
                ) from persistence_error
            raise StageExecutionError(
                "Narration did not complete; retry the same command."
            ) from error

        try:
            repository.complete_narration(stage, attempt)
        except Exception as error:
            raise StageExecutionError(
                "Narration was saved but completion was interrupted; retry "
                "the same command."
            ) from error

    loaded = repository.load_narration(trip.itinerary_revision_id, angle.angle_id)
    assert loaded is not None
    sections, word_count, estimated_minutes, overall_intensity, day_intensities, warnings = (
        loaded
    )
    return NarrationResult(
        trip=stage.trip,
        angle=angle,
        outcome=outcome,
        sections=sections,
        word_count=word_count,
        estimated_minutes=estimated_minutes,
        overall_intensity=overall_intensity,
        day_intensities=day_intensities,
        warnings=warnings,
    )


def _compute_intensities(
    normalized: dict[str, object],
) -> tuple[tuple[DayIntensity, ...], int | None]:
    days = normalized.get("days", [])
    intensities: list[DayIntensity] = []
    if isinstance(days, list):
        for day in days:
            if not isinstance(day, dict):
                continue
            hours = _known_hours(day)
            rating = _rating_for_hours(hours) if hours is not None else None
            intensities.append(
                DayIntensity(day_number=int(day["day_number"]), rating=rating)
            )
    known = [d.rating for d in intensities if d.rating is not None]
    overall = max(known) if known else None
    return tuple(intensities), overall


def _known_hours(day: dict[str, object]) -> float | None:
    total = 0.0
    found = False
    for key in ("route_legs", "activities"):
        items = day.get(key, [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            duration = item.get("duration")
            if not isinstance(duration, dict):
                continue
            kind = duration.get("kind")
            if kind == "EXACT" and isinstance(duration.get("value_hours"), (int, float)):
                total += float(duration["value_hours"])
                found = True
            elif kind == "ESTIMATED" and isinstance(
                duration.get("min_hours"), (int, float)
            ) and isinstance(duration.get("max_hours"), (int, float)):
                total += (float(duration["min_hours"]) + float(duration["max_hours"])) / 2
                found = True
    return total if found else None


def _rating_for_hours(hours: float) -> int:
    if hours <= 2:
        return 1
    if hours <= 4:
        return 2
    if hours <= 6:
        return 3
    if hours <= 8:
        return 4
    return 5


def _build_sections(
    trip_name: str,
    normalized: dict[str, object],
    research_claims,
    angle,
    angle_claim,
    editorial_notes: str,
    overall_intensity: int | None,
    day_intensities: tuple[DayIntensity, ...],
) -> tuple[NarrationSection, ...]:
    by_category = {claim.category: claim for claim in research_claims}
    missing = sorted(
        str(claim.category)
        for claim in research_claims
        if claim.evidence_status is EvidenceStatus.UNKNOWN
    )

    sections: list[NarrationSection] = []
    sections.append(_hook_section(trip_name, angle, by_category))
    sections.append(_journey_at_a_glance_section(trip_name, normalized, overall_intensity))
    sections.append(_route_section(normalized))
    sections.append(_reality_check_section(trip_name, by_category, missing))
    who_suits, who_avoids = _traveller_fit_sections(
        by_category, overall_intensity
    )
    sections.append(who_suits)
    sections.append(who_avoids)
    if day_intensities and overall_intensity is not None:
        sections.append(_intensity_section(overall_intensity, day_intensities))
    sections.append(
        _verdict_section(trip_name, angle, angle_claim, by_category, editorial_notes)
    )
    sections.append(_cta_section(trip_name))
    return tuple(sections)


def _hook_section(trip_name: str, angle, by_category) -> NarrationSection:
    teaser = ""
    for category in _REALITY_CHECK_CATEGORIES:
        claim = by_category.get(category)
        if claim is not None and claim.evidence_status in (
            EvidenceStatus.VERIFIED,
            EvidenceStatus.CORROBORATED,
        ):
            teaser = f" {_stated(claim)}"
            break
    body = f"{angle.viewer_question}{teaser}".strip()
    return NarrationSection(key="hook", title="Hook", body=body)


def _journey_at_a_glance_section(
    trip_name: str, normalized: dict[str, object], overall_intensity: int | None
) -> NarrationSection:
    days = normalized.get("days", [])
    day_count = len(days) if isinstance(days, list) else 0
    legs = _all_route_legs(normalized)
    endpoints = ""
    if legs:
        endpoints = f" from {legs[0][0]} to {legs[-1][1]}"
    intensity_text = (
        f" Overall Trip intensity is rated {overall_intensity}/5."
        if overall_intensity is not None
        else ""
    )
    body = (
        f"{trip_name} runs {day_count} day{'s' if day_count != 1 else ''}"
        f"{endpoints}.{intensity_text}"
    )
    return NarrationSection(key="journey_at_a_glance", title="Journey at a Glance", body=body)


def _route_section(normalized: dict[str, object]) -> NarrationSection:
    days = normalized.get("days", [])
    chapters = _group_chapters(days if isinstance(days, list) else [])
    paragraphs = []
    for title, chapter_days in chapters:
        day_numbers = ", ".join(str(d["day_number"]) for d in chapter_days)
        sentences = [f"{title} (Day {day_numbers})."]
        for day in chapter_days:
            sentences.extend(_day_sentences(day))
        paragraphs.append(" ".join(sentences))
    body = "\n\n".join(paragraphs) if paragraphs else "No route detail is recorded yet."
    return NarrationSection(key="route", title="Route", body=body)


def _group_chapters(
    days: list[dict[str, object]],
) -> list[tuple[str, list[dict[str, object]]]]:
    chapters: list[tuple[str, list[dict[str, object]]]] = []
    current_kind: str | None = None
    current_days: list[dict[str, object]] = []
    for day in days:
        if not isinstance(day, dict):
            continue
        kind = "trail" if _artifact_list(day, "route_legs") else "logistics"
        if kind != current_kind and current_days:
            chapters.append((_chapter_title(current_kind, len(chapters), False), current_days))
            current_days = []
        current_kind = kind
        current_days.append(day)
    if current_days:
        chapters.append(
            (_chapter_title(current_kind, len(chapters), True), current_days)
        )
    return chapters


def _chapter_title(kind: str | None, position: int, is_last: bool) -> str:
    if kind == "trail":
        return "On the Trail"
    if position == 0:
        return "Arrival and Logistics"
    if is_last:
        return "Departure and Logistics"
    return "Logistics"


def _day_sentences(day: dict[str, object]) -> list[str]:
    sentences = []
    for leg in _artifact_list(day, "route_legs"):
        if not isinstance(leg, dict):
            continue
        duration = leg.get("duration")
        duration_text = ""
        if isinstance(duration, dict) and duration.get("kind") in ("EXACT", "ESTIMATED"):
            duration_text = f" ({duration.get('text')})"
        sentences.append(f"Walk from {leg.get('from')} to {leg.get('to')}{duration_text}.")
    for accommodation in _artifact_list(day, "accommodation"):
        if isinstance(accommodation, dict):
            sentences.append(str(accommodation.get("description", "")).rstrip(".") + ".")
    for meal in _artifact_list(day, "meals"):
        if isinstance(meal, dict):
            sentences.append(str(meal.get("description", "")).rstrip(".") + ".")
    for constraint in _artifact_list(day, "practical_constraints"):
        if isinstance(constraint, dict):
            sentences.append(str(constraint.get("description", "")).rstrip(".") + ".")
    return sentences


def _reality_check_section(trip_name: str, by_category, missing: list[str]) -> NarrationSection:
    statements = []
    for category in _REALITY_CHECK_CATEGORIES:
        claim = by_category.get(category)
        if claim is None:
            continue
        if claim.evidence_status in (EvidenceStatus.UNVERIFIED, EvidenceStatus.UNKNOWN):
            continue
        statements.append(_stated(claim))
    body = " ".join(statements) if statements else "No well-evidenced practical facts yet."
    if missing:
        body += (
            "\n\nMissing Information: current data was not found for "
            + ", ".join(category_label(ResearchCategory(m)) for m in missing)
            + "."
        )
    return NarrationSection(key="reality_check", title="Reality Check", body=body)


def _stated(claim) -> str:
    if claim.evidence_status is EvidenceStatus.INDICATIVE:
        return f"Some sources suggest: {claim.statement}"
    return claim.statement


def _traveller_fit_sections(
    by_category, overall_intensity: int | None
) -> tuple[NarrationSection, NarrationSection]:
    suits = []
    avoids = []
    if overall_intensity is not None and overall_intensity >= 3:
        suits.append(
            "This suits travellers comfortable with multi-hour daily "
            "walking and self-guided navigation."
        )
        if overall_intensity >= 4:
            avoids.append(
                "It is best avoided by anyone who cannot manage several "
                "consecutive hours of walking with limited rest options."
            )
    elif overall_intensity is not None:
        suits.append(
            "This suits travellers looking for a lighter, low-intensity pace."
        )

    practical = by_category.get(ResearchCategory.PRACTICAL_DEMANDS)
    if practical is not None and practical.evidence_status in (
        EvidenceStatus.VERIFIED,
        EvidenceStatus.CORROBORATED,
    ):
        avoids.append(
            "Travellers who need reliable phone signal or easy access to "
            "cash and services along the way should plan carefully first."
        )

    solo = by_category.get(ResearchCategory.SOLO_TRAVELLER)
    if solo is not None and solo.evidence_status in (
        EvidenceStatus.VERIFIED,
        EvidenceStatus.CORROBORATED,
    ):
        suits.append(_stated(solo))
    elif solo is not None and solo.evidence_status is EvidenceStatus.INDICATIVE:
        suits.append(_stated(solo))

    if not suits:
        suits.append("Traveller Fit for this Trip is not yet well evidenced.")
    if not avoids:
        avoids.append(
            "No specific conditions currently rule this Trip out; review "
            "individual capability against the Reality Check above."
        )

    return (
        NarrationSection(key="who_it_suits", title="Who It Suits", body=" ".join(suits)),
        NarrationSection(
            key="who_should_avoid_it", title="Who Should Avoid It", body=" ".join(avoids)
        ),
    )


def _intensity_section(
    overall_intensity: int, day_intensities: tuple[DayIntensity, ...]
) -> NarrationSection:
    lines = [
        f"Day {d.day_number}: intensity {d.rating}/5"
        if d.rating is not None
        else f"Day {d.day_number}: intensity not yet evidenced"
        for d in day_intensities
    ]
    body = (
        f"Overall Trip intensity is {overall_intensity}/5, reflecting the "
        "highest sustained demand rather than an average across days.\n\n"
        + "\n".join(lines)
    )
    return NarrationSection(key="intensity", title="Daily Intensity Ratings", body=body)


def _verdict_section(
    trip_name: str, angle, angle_claim, by_category, editorial_notes: str
) -> NarrationSection:
    parts = [f"Our take: {angle.viewer_question}"]
    if angle_claim is not None and angle_claim.evidence_status in (
        EvidenceStatus.VERIFIED,
        EvidenceStatus.CORROBORATED,
    ):
        parts.append(_stated(angle_claim))
    elif angle_claim is not None and angle_claim.evidence_status is EvidenceStatus.INDICATIVE:
        parts.append(_stated(angle_claim))
    if editorial_notes:
        parts.append(f"Editorial note: {editorial_notes}")
    return NarrationSection(
        key="adventure_asia_verdict",
        title="Adventure Asia Verdict",
        body=" ".join(parts),
    )


def _cta_section(trip_name: str) -> NarrationSection:
    body = (
        f"See the current {trip_name} Trip page for dates, availability, "
        "and full details before you book."
    )
    return NarrationSection(key="cta", title="What to Do Next", body=body)


def _all_route_legs(normalized: dict[str, object]) -> list[tuple[str, str]]:
    legs = []
    days = normalized.get("days", [])
    if isinstance(days, list):
        for day in days:
            if not isinstance(day, dict):
                continue
            for leg in _artifact_list(day, "route_legs"):
                if isinstance(leg, dict) and "from" in leg and "to" in leg:
                    legs.append((str(leg["from"]), str(leg["to"])))
    return legs


def _artifact_list(container: dict[str, object], key: str) -> list[object]:
    value = container.get(key, [])
    return value if isinstance(value, list) else []


def _guard_no_price_information(sections: tuple[NarrationSection, ...]) -> None:
    for section in sections:
        if _PRICE_PATTERN.search(section.body):
            raise RuntimeError(
                f"Price Information detected in generated section: {section.key}"
            )


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
