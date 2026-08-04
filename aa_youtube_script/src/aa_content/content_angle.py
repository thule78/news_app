from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import uuid

from aa_content.errors import StageExecutionError, UserFacingError
from aa_content.models import (
    AngleResearchOutcome,
    AngleResearchResult,
    ContentAngleApprovalResult,
    ContentAngleOption,
    ContentAnglePropositionResult,
    ContentAngleSource,
    ContentAngleStatus,
    EvidenceStatus,
    EvidenceSupportLevel,
    ResearchCategory,
    ResearchClaim,
    SourceRecord,
    StageStatus,
)
from aa_content.persistence import WorkspaceRepository
from aa_content.research_providers import (
    FakeResearchSourceProvider,
    ResearchDocument,
    ResearchSourceProvider,
    WebResearchSourceProvider,
)
from aa_content.research_synthesis import evidence_status_for, paraphrase_evidence

FAKE_PROVIDER_ENVIRONMENT_VARIABLE = "AA_CONTENT_FAKE_PROVIDERS"

# An angle is proposed only when at least one of its supporting categories is
# already well-evidenced — never invented just to reach three options.
_ANGLE_TEMPLATES: tuple[dict[str, object], ...] = (
    {
        "key": "seasonality_crowds",
        "categories": (ResearchCategory.SEASONALITY, ResearchCategory.CROWDS),
        "viewer_question": (
            "When is the best time to do {topic} while avoiding the biggest "
            "crowds?"
        ),
        "commercial_relevance": (
            "Answers a top pre-booking timing question, supporting "
            "date-driven conversions."
        ),
        "risks": (
            "Seasonal and crowd conditions can shift year to year; Claims "
            "must stay within their Recheck Date."
        ),
    },
    {
        "key": "practical_demands",
        "categories": (ResearchCategory.PRACTICAL_DEMANDS,),
        "viewer_question": (
            "How physically demanding is {topic} and who should prepare "
            "for it?"
        ),
        "commercial_relevance": (
            "Sets accurate fitness expectations, reducing mismatched "
            "bookings and refund risk."
        ),
        "risks": (
            "Overstating or understating difficulty creates safety and "
            "expectation-setting risk."
        ),
    },
    {
        "key": "solo_traveller",
        "categories": (ResearchCategory.SOLO_TRAVELLER,),
        "viewer_question": "Is {topic} a good fit for a solo traveller?",
        "commercial_relevance": (
            "Directly targets the solo-traveller segment's main hesitation "
            "before booking."
        ),
        "risks": "Safety framing must stay condition-based, never a guarantee.",
    },
)

_STOPWORDS = frozenset(
    {
        "the", "a", "an", "is", "are", "for", "to", "of", "in", "on", "and",
        "or", "with", "does", "do", "what", "how", "best", "good", "fit",
        "while", "avoiding", "should", "this", "that", "who",
    }
)


def propose_content_angles(
    workspace: Path, trip_id: str
) -> ContentAnglePropositionResult:
    repository = WorkspaceRepository(workspace)
    if not repository.database_path.is_file():
        raise UserFacingError(
            f"Workspace is not initialized: run init for {workspace.resolve()}"
        )
    trip = repository.load_current_trip(trip_id)
    if trip is None:
        raise UserFacingError(f"Trip not found: {trip_id}")

    claims = [
        claim
        for claim in repository.load_research_claims(trip.itinerary_revision_id)
        if claim.category != ResearchCategory.ANGLE_SUPPORT
    ]
    if not claims:
        raise UserFacingError(
            "Baseline Research has not been run: run `trip research` first."
        )
    by_category = {claim.category: claim for claim in claims}
    missing = tuple(
        sorted(
            str(claim.category)
            for claim in claims
            if claim.evidence_status is EvidenceStatus.UNKNOWN
        )
    )

    options: list[ContentAngleOption] = []
    for template in _ANGLE_TEMPLATES:
        categories = template["categories"]
        supporting = [by_category[c] for c in categories if c in by_category]
        well_supported = [
            claim
            for claim in supporting
            if claim.evidence_status
            in (EvidenceStatus.VERIFIED, EvidenceStatus.CORROBORATED)
        ]
        if not well_supported:
            continue
        evidence_refs = tuple(
            f"{claim.category}: {claim.evidence_status}"
            for claim in supporting
            if claim.evidence_status is not EvidenceStatus.UNKNOWN
        )
        options.append(
            ContentAngleOption(
                angle_id=f"cga_{uuid.uuid4().hex}",
                viewer_question=str(template["viewer_question"]).format(
                    topic=trip.name
                ),
                available_evidence=evidence_refs,
                commercial_relevance=str(template["commercial_relevance"]),
                risks=str(template["risks"]),
                missing_information=missing,
                source=ContentAngleSource.GENERATED,
                status=ContentAngleStatus.PROPOSED,
                evidence_support=EvidenceSupportLevel.SUPPORTED,
            )
        )
        if len(options) == 3:
            break

    repository.replace_proposed_angles(
        trip.trip_id, trip.itinerary_revision_id, options
    )
    return ContentAnglePropositionResult(trip=trip, options=tuple(options))


def approve_generated_angle(
    workspace: Path, trip_id: str, angle_id: str
) -> ContentAngleApprovalResult:
    repository = WorkspaceRepository(workspace)
    if not repository.database_path.is_file():
        raise UserFacingError(
            f"Workspace is not initialized: run init for {workspace.resolve()}"
        )
    trip = repository.load_current_trip(trip_id)
    if trip is None:
        raise UserFacingError(f"Trip not found: {trip_id}")

    stored_revision = repository.load_content_angle_revision(angle_id)
    if stored_revision is None:
        raise UserFacingError(f"Content Angle not found: {angle_id}")
    if stored_revision != trip.itinerary_revision_id:
        raise UserFacingError(
            "Itinerary Revision changed since this Content Angle was "
            "proposed; run `trip angle propose` again."
        )
    angle = repository.approve_content_angle(trip.trip_id, angle_id)
    return ContentAngleApprovalResult(trip=trip, angle=angle)


def approve_custom_angle(
    workspace: Path,
    trip_id: str,
    viewer_question: str,
    *,
    acknowledge_unsupported: bool = False,
) -> ContentAngleApprovalResult:
    normalized_question = viewer_question.strip()
    if not normalized_question:
        raise UserFacingError("Custom Content Angle cannot be empty.")

    repository = WorkspaceRepository(workspace)
    if not repository.database_path.is_file():
        raise UserFacingError(
            f"Workspace is not initialized: run init for {workspace.resolve()}"
        )
    trip = repository.load_current_trip(trip_id)
    if trip is None:
        raise UserFacingError(f"Trip not found: {trip_id}")

    claims = repository.load_research_claims(trip.itinerary_revision_id)
    if not claims:
        raise UserFacingError(
            "Baseline Research has not been run: run `trip research` first."
        )
    support, matched = _evidence_support_for_custom(normalized_question, claims)
    if support is EvidenceSupportLevel.UNSUPPORTED and not acknowledge_unsupported:
        raise UserFacingError(
            "Custom Content Angle has no matching Baseline Research Evidence; "
            "pass --acknowledge-unsupported to approve it anyway."
        )

    missing = tuple(
        sorted(
            str(claim.category)
            for claim in claims
            if claim.category != ResearchCategory.ANGLE_SUPPORT
            and claim.evidence_status is EvidenceStatus.UNKNOWN
        )
    )
    option = ContentAngleOption(
        angle_id=f"cga_{uuid.uuid4().hex}",
        viewer_question=normalized_question,
        available_evidence=matched,
        commercial_relevance=(
            "Operator-supplied custom angle; commercial fit is an "
            "Editorial Judgment call."
        ),
        risks=(
            "Custom framing is not generator-validated beyond the Evidence "
            "support check."
        ),
        missing_information=missing,
        source=ContentAngleSource.CUSTOM,
        status=ContentAngleStatus.APPROVED,
        evidence_support=support,
    )
    repository.insert_custom_angle(trip.trip_id, trip.itinerary_revision_id, option)
    return ContentAngleApprovalResult(trip=trip, angle=option)


def _evidence_support_for_custom(
    viewer_question: str, claims: tuple[ResearchClaim, ...]
) -> tuple[EvidenceSupportLevel, tuple[str, ...]]:
    question_words = _significant_words(viewer_question)
    matched: list[str] = []
    for claim in claims:
        if claim.category == ResearchCategory.ANGLE_SUPPORT:
            continue
        if claim.evidence_status is EvidenceStatus.UNKNOWN:
            continue
        claim_words = _significant_words(claim.statement) | _significant_words(
            str(claim.category)
        )
        if question_words & claim_words:
            matched.append(f"{claim.category}: {claim.evidence_status}")
    if len(matched) >= 2:
        return EvidenceSupportLevel.SUPPORTED, tuple(matched)
    if len(matched) == 1:
        return EvidenceSupportLevel.WEAK, tuple(matched)
    return EvidenceSupportLevel.UNSUPPORTED, ()


def _significant_words(text: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z]+", text.lower())
        if len(word) > 3 and word not in _STOPWORDS
    }


def run_angle_research(
    workspace: Path,
    trip_id: str,
    *,
    force: bool = False,
    provider: ResearchSourceProvider | None = None,
) -> AngleResearchResult:
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

    input_hash = trip.itinerary_revision_id
    stage = repository.find_angle_research(angle.angle_id, input_hash)

    if stage is not None and stage.status is StageStatus.COMPLETED and not force:
        outcome = AngleResearchOutcome.REUSED
    else:
        if stage is None:
            stage, attempt = repository.start_angle_research(
                trip, angle.angle_id, input_hash
            )
            outcome = AngleResearchOutcome.RESEARCHED
        else:
            attempt = repository.start_retry(stage)
            outcome = (
                AngleResearchOutcome.REGENERATED
                if force
                else AngleResearchOutcome.RESUMED
            )

        active_provider = provider or _default_provider()
        try:
            documents = active_provider.find_sources(
                angle.viewer_question, max_results=2
            )
            sources = [
                _build_angle_source_record(angle.angle_id, document)
                for document in documents
            ]
            claim = _build_angle_claim(angle, sources)
            repository.persist_angle_research(
                trip.trip_id, trip.itinerary_revision_id, angle.angle_id,
                sources, claim,
            )
        except Exception as error:
            try:
                repository.fail_attempt(stage, attempt, "ANGLE_RESEARCH_FAILED")
            except Exception as persistence_error:
                raise StageExecutionError(
                    "Angle Research failed while saving recovery state; "
                    "retry the same command."
                ) from persistence_error
            raise StageExecutionError(
                "Angle Research did not complete; retry the same command."
            ) from error

        try:
            repository.complete_angle_research(stage, attempt)
        except Exception as error:
            raise StageExecutionError(
                "Angle Research results were saved but completion was "
                "interrupted; retry the same command."
            ) from error

    claim = repository.load_angle_research_claim(
        trip.itinerary_revision_id, angle.angle_id
    )
    return AngleResearchResult(trip=trip, angle=angle, outcome=outcome, claim=claim)


def _default_provider() -> ResearchSourceProvider:
    if os.environ.get(FAKE_PROVIDER_ENVIRONMENT_VARIABLE):
        return FakeResearchSourceProvider()
    return WebResearchSourceProvider()


def _build_angle_source_record(
    angle_id: str, document: ResearchDocument
) -> SourceRecord:
    return SourceRecord(
        source_record_id=f"src_{uuid.uuid4().hex}",
        category=ResearchCategory.ANGLE_SUPPORT,
        url=document.url,
        title=document.title,
        publisher=document.publisher,
        retrieved_at=_utc_now(),
        content_hash=_content_hash(document.extracted_text),
        locator=f"angle:{angle_id}",
        evidence_summary=paraphrase_evidence(
            ResearchCategory.ANGLE_SUPPORT, document
        ),
        published_at=document.published_at,
    )


def _build_angle_claim(
    angle: ContentAngleOption, sources: list[SourceRecord]
) -> ResearchClaim:
    publishers = [source.publisher for source in sources]
    status = evidence_status_for(ResearchCategory.ANGLE_SUPPORT, publishers)
    source_word = "source" if len(sources) == 1 else "sources"
    if not sources:
        statement = (
            f'No current Evidence could be found supporting the angle '
            f'"{angle.viewer_question}".'
        )
    else:
        statement = (
            f'Support for the angle "{angle.viewer_question}" is backed '
            f"by {len(sources)} {source_word}."
        )
    return ResearchClaim(
        claim_id=f"rcl_{uuid.uuid4().hex}",
        category=ResearchCategory.ANGLE_SUPPORT,
        statement=statement,
        evidence_status=status,
        recheck_date=None,
        sources=tuple(sources),
    )


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
