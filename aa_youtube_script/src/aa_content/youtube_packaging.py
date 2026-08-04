from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from aa_content.artifacts import publish_youtube_packaging_artifacts
from aa_content.errors import UserFacingError
from aa_content.models import (
    ChapterMarker,
    EvidenceStatus,
    KeywordCandidate,
    NarrationSection,
    ResearchCategory,
    ShortScript,
    ThumbnailBrief,
    TitleOption,
    TitleStyle,
    YoutubePackaging,
    YoutubePackagingOutcome,
    YoutubePackagingResult,
)
from aa_content.persistence import WorkspaceRepository
from aa_content.research_synthesis import category_label
from aa_content.validation import compute_draft_signature

_PRICE_PATTERN = re.compile(
    r"[$€£¥]\s?\d|\b\d+(?:\.\d+)?\s?(?:usd|eur|gbp|jpy|vnd|dollars?)\b",
    re.IGNORECASE,
)
_COMMERCIAL_INTENT_CATEGORIES = frozenset(
    {ResearchCategory.ACCESS, ResearchCategory.INDEPENDENT_TRANSPORT}
)
_DISCLOSURES = (
    "This video reflects Adventure Asia's independent assessment; "
    "itinerary details and current conditions can change, so always "
    "confirm the latest information on the Trip page before booking."
)


def generate_youtube_packaging(
    workspace: Path, trip_id: str
) -> YoutubePackagingResult:
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

    loaded_narration = repository.load_narration(
        trip.itinerary_revision_id, angle.angle_id
    )
    if loaded_narration is None:
        raise UserFacingError("No narration to package: run `trip narrate` first.")
    sections, _word_count, estimated_minutes, _overall, _days, _warnings = (
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

    claims = [
        claim
        for claim in repository.load_research_claims(trip.itinerary_revision_id)
        if claim.category != ResearchCategory.ANGLE_SUPPORT
    ]
    by_category = {claim.category: claim for claim in claims}

    packaging = _build_packaging(
        trip.name, angle.viewer_question, sections, estimated_minutes, by_category
    )
    payload = _serialize(packaging)
    _guard_no_price_information(payload)
    payload_json = json.dumps(payload, sort_keys=True)
    content_signature = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    existing_signature = repository.load_youtube_packaging_signature(
        trip.itinerary_revision_id, angle.angle_id
    )
    if existing_signature is None:
        outcome = YoutubePackagingOutcome.GENERATED
    elif existing_signature == content_signature:
        outcome = YoutubePackagingOutcome.REUSED
    else:
        outcome = YoutubePackagingOutcome.REGENERATED

    repository.persist_youtube_packaging(
        trip.itinerary_revision_id, angle.angle_id, payload_json, content_signature
    )
    publish_youtube_packaging_artifacts(workspace, trip, packaging)
    return YoutubePackagingResult(
        trip=trip,
        angle=angle,
        outcome=outcome,
        packaging=packaging,
        content_signature=content_signature,
    )


def _build_packaging(
    trip_name: str,
    viewer_question: str,
    sections: tuple[NarrationSection, ...],
    estimated_minutes: float,
    by_category: dict[ResearchCategory, object],
) -> YoutubePackaging:
    keyword_label = _best_evidenced_label(by_category)
    titles = _build_titles(trip_name, viewer_question, keyword_label)
    description = _build_description(trip_name, sections, estimated_minutes)
    chapters = _build_chapters(sections, estimated_minutes)
    thumbnail_brief = _build_thumbnail_brief(trip_name, viewer_question, keyword_label)
    keywords = _build_keywords(trip_name, by_category)
    shorts = _build_shorts(trip_name, sections)
    return YoutubePackaging(
        titles=titles,
        description=description,
        chapters=chapters,
        thumbnail_brief=thumbnail_brief,
        keywords=keywords,
        shorts=shorts,
    )


def _best_evidenced_label(by_category: dict[ResearchCategory, object]) -> str | None:
    for status in (EvidenceStatus.VERIFIED, EvidenceStatus.CORROBORATED):
        for category, claim in by_category.items():
            if claim.evidence_status is status:
                return category_label(category)
    return None


def _build_titles(
    trip_name: str, viewer_question: str, keyword_label: str | None
) -> tuple[TitleOption, ...]:
    topic = keyword_label or "Route and Duration"
    return (
        TitleOption(TitleStyle.SEARCH_LED, f"{trip_name}: Complete Trip Guide"),
        TitleOption(
            TitleStyle.SEARCH_LED, f"{trip_name} Itinerary: {topic} Explained"
        ),
        TitleOption(TitleStyle.CURIOSITY_LED, viewer_question),
        TitleOption(
            TitleStyle.CURIOSITY_LED, f"{viewer_question} (Watch Before You Book)"
        ),
        TitleOption(TitleStyle.HYBRID, f"{trip_name}: {viewer_question}"),
        TitleOption(
            TitleStyle.HYBRID, f"{trip_name} — What the Evidence Says About {topic}"
        ),
    )


def _build_description(
    trip_name: str, sections: tuple[NarrationSection, ...], estimated_minutes: float
) -> str:
    by_key = {section.key: section for section in sections}
    parts = [by_key["hook"].body, by_key["journey_at_a_glance"].body]
    fit_parts = []
    if "who_it_suits" in by_key:
        fit_parts.append(by_key["who_it_suits"].body)
    if "who_should_avoid_it" in by_key:
        fit_parts.append(by_key["who_should_avoid_it"].body)
    if fit_parts:
        parts.append(" ".join(fit_parts))
    parts.append(by_key["cta"].body)
    parts.append(f"{trip_name} Trip page: [link]")

    chapters = _build_chapters(sections, estimated_minutes)
    chapter_lines = "\n".join(
        f"{chapter.timestamp_label} {chapter.title}" for chapter in chapters
    )
    parts.append("Chapters:\n" + chapter_lines)
    parts.append(_DISCLOSURES)
    return "\n\n".join(parts)


def _build_chapters(
    sections: tuple[NarrationSection, ...], estimated_minutes: float
) -> tuple[ChapterMarker, ...]:
    total_words = sum(len(section.body.split()) for section in sections) or 1
    total_seconds = max(1, round(estimated_minutes * 60))
    chapters = []
    elapsed_words = 0
    for section in sections:
        timestamp = round(total_seconds * elapsed_words / total_words)
        chapters.append(ChapterMarker(title=section.title, timestamp_seconds=timestamp))
        elapsed_words += len(section.body.split())
    return tuple(chapters)


def _build_thumbnail_brief(
    trip_name: str, viewer_question: str, keyword_label: str | None
) -> ThumbnailBrief:
    clear_idea = viewer_question if len(viewer_question) <= 60 else trip_name
    cues = [trip_name]
    if keyword_label:
        cues.append(keyword_label)
    text_options = [trip_name.upper()]
    if keyword_label:
        text_options.append(keyword_label.upper())
    text_options.append("WATCH FIRST")
    return ThumbnailBrief(
        clear_idea=clear_idea,
        destination_cues=tuple(cues),
        text_options=tuple(text_options),
    )


def _build_keywords(
    trip_name: str, by_category: dict[ResearchCategory, object]
) -> tuple[KeywordCandidate, ...]:
    keywords = []
    for category, claim in by_category.items():
        if claim.evidence_status not in (
            EvidenceStatus.VERIFIED,
            EvidenceStatus.CORROBORATED,
        ):
            continue
        intent = (
            "commercial-investigation"
            if category in _COMMERCIAL_INTENT_CATEGORIES
            else "informational"
        )
        keywords.append(
            KeywordCandidate(
                keyword=f"{trip_name} {category_label(category).lower()}",
                search_intent=intent,
            )
        )
    return tuple(keywords)


def _build_shorts(
    trip_name: str, sections: tuple[NarrationSection, ...]
) -> tuple[ShortScript, ...]:
    by_key = {section.key: section for section in sections}
    hook_sentences = _sentences(by_key["hook"].body, 2)
    fit_source = by_key.get("who_it_suits") or by_key.get("reality_check")
    fit_sentences = _sentences(fit_source.body, 2) if fit_source is not None else []
    return (
        ShortScript(
            title=f"{trip_name} in 30 Seconds",
            body=" ".join(hook_sentences),
        ),
        ShortScript(
            title=f"Is {trip_name} Right for You?",
            body=" ".join(fit_sentences),
        ),
    )


def _sentences(text: str, count: int) -> list[str]:
    pieces = [piece.strip() for piece in re.split(r"(?<=[.!?])\s+", text) if piece.strip()]
    return pieces[:count]


def _serialize(packaging: YoutubePackaging) -> dict[str, object]:
    return {
        "titles": [
            {"style": str(t.style), "text": t.text} for t in packaging.titles
        ],
        "description": packaging.description,
        "chapters": [
            {"title": c.title, "timestamp_seconds": c.timestamp_seconds}
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


def _guard_no_price_information(payload: dict[str, object]) -> None:
    blob = json.dumps(payload)
    if _PRICE_PATTERN.search(blob):
        raise RuntimeError("Price Information detected in YouTube packaging output.")
