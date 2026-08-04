from __future__ import annotations

from datetime import date
import hashlib
import os
from pathlib import Path
import uuid

from aa_content.artifacts import publish_baseline_research_artifacts
from aa_content.errors import StageExecutionError, UserFacingError
from aa_content.models import (
    BaselineResearchOutcome,
    BaselineResearchResult,
    ResearchCategory,
    ResearchClaim,
    SourceRecord,
    StageStatus,
    TripRecord,
)
from aa_content.persistence import WorkspaceRepository
from aa_content.research_providers import (
    FakeResearchSourceProvider,
    ResearchDocument,
    ResearchSourceProvider,
    WebResearchSourceProvider,
)
from aa_content.research_synthesis import (
    claim_statement,
    evidence_status_for,
    paraphrase_evidence,
    recheck_date_for,
)

FAKE_PROVIDER_ENVIRONMENT_VARIABLE = "AA_CONTENT_FAKE_PROVIDERS"

# Ordered so a resumed run always finishes categories in a stable sequence.
_CATEGORY_ORDER: tuple[ResearchCategory, ...] = (
    ResearchCategory.ACCESS,
    ResearchCategory.ROUTE_RULES,
    ResearchCategory.SEASONALITY,
    ResearchCategory.CROWDS,
    ResearchCategory.INDEPENDENT_TRANSPORT,
    ResearchCategory.SOLO_TRAVELLER,
    ResearchCategory.OFFICIAL_ADVISORY,
    ResearchCategory.PRACTICAL_DEMANDS,
)

# Only route-leg-scoped categories are eligible for cross-Trip reuse through a
# confirmed Route Segment. Trip-specific categories (access, crowds, solo
# conditions, advisories, practical demands) always research fresh per Trip.
_ROUTE_SEGMENT_CATEGORIES = frozenset(
    {ResearchCategory.ROUTE_RULES, ResearchCategory.INDEPENDENT_TRANSPORT}
)


def run_baseline_research(
    workspace: Path,
    trip_id: str,
    *,
    force: bool = False,
    provider: ResearchSourceProvider | None = None,
) -> BaselineResearchResult:
    repository = WorkspaceRepository(workspace)
    if not repository.database_path.is_file():
        raise UserFacingError(
            f"Workspace is not initialized: run init for {workspace.resolve()}"
        )

    trip = repository.load_current_trip(trip_id)
    if trip is None:
        raise UserFacingError(f"Trip not found: {trip_id}")

    normalized = repository.load_normalized_itinerary(trip.itinerary_revision_id)
    if normalized is None:
        raise UserFacingError(
            "Itinerary Revision has not been processed: run `trip process` "
            f"for {trip_id} first."
        )

    input_hash = trip.itinerary_revision_id
    stage = repository.find_baseline_research(trip.itinerary_revision_id, input_hash)

    if stage is not None and stage.status is StageStatus.COMPLETED and not force:
        outcome = BaselineResearchOutcome.REUSED
    else:
        if stage is None:
            stage, attempt = repository.start_baseline_research(trip, input_hash)
            outcome = BaselineResearchOutcome.RESEARCHED
        else:
            attempt = repository.start_retry(stage)
            outcome = (
                BaselineResearchOutcome.REGENERATED
                if force
                else BaselineResearchOutcome.RESUMED
            )

        active_provider = provider or _default_provider()
        topic = trip.name
        remaining = [
            category
            for category in _CATEGORY_ORDER
            if force or category not in stage.completed_categories
        ]
        leg = _first_route_leg(normalized)
        try:
            for category in remaining:
                _research_category(
                    repository, active_provider, trip, category, topic, leg
                )
                repository.checkpoint_research_category(
                    stage.workflow_stage_id, category
                )
        except Exception as error:
            try:
                repository.fail_attempt(stage, attempt, "RESEARCH_FAILED")
            except Exception as persistence_error:
                raise StageExecutionError(
                    "Baseline research failed while saving recovery state; "
                    "retry the same command."
                ) from persistence_error
            raise StageExecutionError(
                "Baseline research did not complete; retry the same command "
                "to resume from the last completed category."
            ) from error

        claims = repository.load_research_claims(trip.itinerary_revision_id)
        try:
            publish_baseline_research_artifacts(workspace, stage.trip, claims)
            repository.complete_baseline_research(stage, attempt)
        except Exception as error:
            raise StageExecutionError(
                "Baseline research results were saved but completion was "
                "interrupted; retry the same command."
            ) from error

    claims = repository.load_research_claims(stage.trip.itinerary_revision_id)
    return BaselineResearchResult(trip=stage.trip, outcome=outcome, claims=claims)


def _default_provider() -> ResearchSourceProvider:
    if os.environ.get(FAKE_PROVIDER_ENVIRONMENT_VARIABLE):
        return FakeResearchSourceProvider()
    return WebResearchSourceProvider()


def _research_category(
    repository: WorkspaceRepository,
    provider: ResearchSourceProvider,
    trip: TripRecord,
    category: ResearchCategory,
    topic: str,
    leg: tuple[str, str] | None,
) -> None:
    if category in _ROUTE_SEGMENT_CATEGORIES and leg is not None:
        segment = repository.find_confirmed_route_segment(leg[0], leg[1])
        if segment is not None:
            repository.link_trip_to_route_segment(
                segment.route_segment_id,
                trip.trip_id,
                trip.itinerary_revision_id,
                f"{leg[0]} to {leg[1]}",
            )
            canonical = repository.load_canonical_research(
                segment.route_segment_id, category
            )
            if canonical is not None and not _recheck_has_passed(canonical):
                _reuse_canonical_claim(repository, trip, category, canonical)
                return
            if canonical is not None:
                # Recheck Date passed: refresh before reuse.
                try:
                    sources, claim = _fresh_research(
                        provider, category, topic, leg
                    )
                except Exception:
                    stale_claim = ResearchClaim(
                        claim_id=f"rcl_{uuid.uuid4().hex}",
                        category=canonical.category,
                        statement=canonical.statement,
                        evidence_status=canonical.evidence_status,
                        recheck_date=canonical.recheck_date,
                        sources=canonical.sources,
                        stale=True,
                    )
                    repository.persist_reused_research_category(
                        trip.trip_id,
                        trip.itinerary_revision_id,
                        category,
                        stale_claim,
                        [source.source_record_id for source in canonical.sources],
                    )
                    return
                repository.persist_research_category(
                    trip.trip_id, trip.itinerary_revision_id, category, sources, claim
                )
                repository.register_canonical_research(
                    segment.route_segment_id, category, claim.claim_id
                )
                return
            sources, claim = _fresh_research(provider, category, topic, leg)
            repository.persist_research_category(
                trip.trip_id, trip.itinerary_revision_id, category, sources, claim
            )
            repository.register_canonical_research(
                segment.route_segment_id, category, claim.claim_id
            )
            return

    sources, claim = _fresh_research(provider, category, topic, leg)
    repository.persist_research_category(
        trip.trip_id, trip.itinerary_revision_id, category, sources, claim
    )


def _reuse_canonical_claim(
    repository: WorkspaceRepository,
    trip: TripRecord,
    category: ResearchCategory,
    canonical: ResearchClaim,
) -> None:
    reused_claim = ResearchClaim(
        claim_id=f"rcl_{uuid.uuid4().hex}",
        category=category,
        statement=canonical.statement,
        evidence_status=canonical.evidence_status,
        recheck_date=canonical.recheck_date,
        sources=canonical.sources,
        stale=False,
    )
    repository.persist_reused_research_category(
        trip.trip_id,
        trip.itinerary_revision_id,
        category,
        reused_claim,
        [source.source_record_id for source in canonical.sources],
    )


def _recheck_has_passed(claim: ResearchClaim) -> bool:
    if claim.recheck_date is None:
        return False
    return date.fromisoformat(claim.recheck_date) < date.today()


def _fresh_research(
    provider: ResearchSourceProvider,
    category: ResearchCategory,
    topic: str,
    leg: tuple[str, str] | None,
) -> tuple[list[SourceRecord], ResearchClaim]:
    query = _query_for(category, topic, leg)
    documents = provider.find_sources(query, max_results=2)
    sources = [_build_source_record(category, document) for document in documents]
    claim = _build_claim(category, topic, sources)
    return sources, claim


def _query_for(
    category: ResearchCategory, topic: str, leg: tuple[str, str] | None
) -> str:
    if category in _ROUTE_SEGMENT_CATEGORIES and leg is not None:
        if category is ResearchCategory.INDEPENDENT_TRANSPORT:
            return f"{leg[0]} to {leg[1]} public transport schedule"
        return f"{leg[0]} to {leg[1]} trail route rules and regulations"
    templates = {
        ResearchCategory.ACCESS: f"{topic} current entry access requirements",
        ResearchCategory.ROUTE_RULES: f"{topic} trail route rules and regulations",
        ResearchCategory.SEASONALITY: f"{topic} best season weather conditions",
        ResearchCategory.CROWDS: f"{topic} crowd levels peak season",
        ResearchCategory.INDEPENDENT_TRANSPORT: f"{topic} independent transport options",
        ResearchCategory.SOLO_TRAVELLER: f"{topic} solo traveller safety conditions",
        ResearchCategory.OFFICIAL_ADVISORY: f"{topic} government travel advisory",
        ResearchCategory.PRACTICAL_DEMANDS: f"{topic} practical requirements terrain",
    }
    return templates[category]


def _first_route_leg(normalized: dict[str, object]) -> tuple[str, str] | None:
    days = normalized.get("days", [])
    if not isinstance(days, list):
        return None
    for day in days:
        if not isinstance(day, dict):
            continue
        legs = day.get("route_legs", [])
        if isinstance(legs, list) and legs:
            leg = legs[0]
            if isinstance(leg, dict) and "from" in leg and "to" in leg:
                return str(leg["from"]), str(leg["to"])
    return None


def _build_source_record(
    category: ResearchCategory, document: ResearchDocument
) -> SourceRecord:
    return SourceRecord(
        source_record_id=f"src_{uuid.uuid4().hex}",
        category=category,
        url=document.url,
        title=document.title,
        publisher=document.publisher,
        retrieved_at=_utc_now(),
        content_hash=_content_hash(document.extracted_text),
        locator="extracted main content",
        evidence_summary=paraphrase_evidence(category, document),
        published_at=document.published_at,
    )


def _build_claim(
    category: ResearchCategory, topic: str, sources: list[SourceRecord]
) -> ResearchClaim:
    publishers = [source.publisher for source in sources]
    status = evidence_status_for(category, publishers)
    return ResearchClaim(
        claim_id=f"rcl_{uuid.uuid4().hex}",
        category=category,
        statement=claim_statement(category, topic, status, len(sources)),
        evidence_status=status,
        recheck_date=recheck_date_for(category),
        sources=tuple(sources),
    )


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
