from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import unicodedata
import uuid

from aa_content.artifacts import publish_trip_artifacts
from aa_content.errors import StageExecutionError, UserFacingError
from aa_content.models import (
    ItinerarySource,
    ItinerarySourceKind,
    SourceFetchOutcome,
    SourceFetchRecord,
    StageAttempt,
    StageStatus,
    TripCreationOutcome,
    TripCreationResult,
    TripInspectionResult,
    TripRecord,
    TripUpdateOutcome,
    TripUpdateResult,
    TripUpdateStage,
)
from aa_content.persistence import WorkspaceRepository
from aa_content.retrieval import UrlRetrievalError, retrieve_itinerary_source


def create_trip(
    workspace: Path,
    name: str,
    itinerary: str,
    *,
    force: bool = False,
    source_kind: ItinerarySourceKind = ItinerarySourceKind.PASTED_TEXT,
    source_url: str | None = None,
    source_fetch: SourceFetchRecord | None = None,
) -> TripCreationResult:
    normalized_name = name.strip()
    if not normalized_name:
        raise UserFacingError("Trip name cannot be empty.")
    if not itinerary.strip():
        raise UserFacingError("Paste itinerary text through standard input.")

    repository = WorkspaceRepository(workspace)
    if not repository.database_path.is_file():
        raise UserFacingError(
            f"Workspace is not initialized: run init for {workspace.resolve()}"
        )

    input_hash = _trip_input_hash(normalized_name, itinerary)
    stage = repository.find_trip_creation(input_hash)

    if stage is not None and stage.status is StageStatus.COMPLETED and not force:
        return TripCreationResult(stage.trip, TripCreationOutcome.REUSED)

    if stage is None:
        source = ItinerarySource(
            kind=source_kind, text=itinerary, requested_url=source_url
        )
        stage, attempt = repository.start_trip_creation(
            normalized_name,
            _slugify(normalized_name),
            source,
            input_hash,
            source_fetch=source_fetch,
        )
        outcome = TripCreationOutcome.CREATED
        persisted_itinerary = itinerary
    else:
        attempt = repository.start_retry(stage)
        persisted_itinerary = repository.load_original_itinerary(
            stage.trip.itinerary_revision_id
        )
        outcome = (
            TripCreationOutcome.REGENERATED if force else TripCreationOutcome.RESUMED
        )

    try:
        publish_trip_artifacts(workspace, stage.trip, persisted_itinerary)
    except Exception as error:
        try:
            repository.fail_attempt(stage, attempt, "ARTIFACT_WRITE_FAILED")
        except Exception as persistence_error:
            raise StageExecutionError(
                "Trip creation failed while saving recovery state; retry the "
                "same command."
            ) from persistence_error
        raise StageExecutionError(
            "Trip creation did not complete; fix the workspace and retry the "
            "same command."
        ) from error

    try:
        repository.complete_attempt(stage, attempt)
    except Exception as error:
        raise StageExecutionError(
            "Trip artifacts were saved but completion was interrupted; retry "
            "the same command."
        ) from error

    return TripCreationResult(stage.trip, outcome)


def update_trip(
    workspace: Path,
    trip_id: str,
    itinerary: str,
    *,
    force: bool = False,
    source_kind: ItinerarySourceKind = ItinerarySourceKind.PASTED_TEXT,
    source_url: str | None = None,
    source_fetch: SourceFetchRecord | None = None,
) -> TripUpdateResult:
    if not itinerary.strip():
        raise UserFacingError("Paste itinerary text through standard input.")

    repository = WorkspaceRepository(workspace)
    if not repository.database_path.is_file():
        raise UserFacingError(
            f"Workspace is not initialized: run init for {workspace.resolve()}"
        )

    current = repository.load_current_trip(trip_id)
    if current is None:
        raise UserFacingError(f"Trip not found: {trip_id}")

    pending = repository.find_pending_trip_update(trip_id)
    if pending is not None:
        return TripUpdateResult(
            _resume_trip_update(repository, workspace, pending),
            TripUpdateOutcome.RESUMED,
            previous_revision_number=current.revision_number,
        )

    current_text = repository.load_original_itinerary(current.itinerary_revision_id)
    if itinerary == current_text and not force:
        if source_fetch is not None:
            repository.record_source_fetch(
                source_fetch,
                trip_id=current.trip_id,
                itinerary_revision_id=current.itinerary_revision_id,
            )
        return TripUpdateResult(current, TripUpdateOutcome.UNCHANGED)

    input_hash = _trip_input_hash(current.itinerary_revision_id, itinerary)
    completed = repository.find_completed_trip_update(
        trip_id, current.itinerary_revision_id, input_hash
    )
    if completed is not None and not force:
        return TripUpdateResult(
            completed.trip,
            TripUpdateOutcome.RESUMED,
            previous_revision_number=current.revision_number,
        )

    source = ItinerarySource(
        kind=source_kind, text=itinerary, requested_url=source_url
    )
    stage, attempt = repository.start_trip_update(
        current, source, input_hash, source_fetch=source_fetch
    )
    _publish_trip_update(repository, workspace, stage, attempt)
    return TripUpdateResult(
        stage.trip,
        TripUpdateOutcome.UPDATED,
        previous_revision_number=current.revision_number,
    )


def resolve_url_source(
    workspace: Path, url: str, *, trip_id: str | None = None
) -> tuple[ItinerarySource, SourceFetchRecord]:
    """Retrieve and extract itinerary content from a URL, recording the fetch."""
    repository = WorkspaceRepository(workspace)
    accessed_at = datetime.now(timezone.utc).isoformat()

    try:
        result = retrieve_itinerary_source(url)
    except UrlRetrievalError as error:
        repository.record_source_fetch(
            SourceFetchRecord(
                source_fetch_id=f"srf_{uuid.uuid4().hex}",
                requested_url=url,
                accessed_at=accessed_at,
                outcome=SourceFetchOutcome.FAILED,
                error_code=error.error_code,
                error_message=str(error),
            ),
            trip_id=trip_id,
        )
        raise UserFacingError(
            f"Could not retrieve itinerary from {url}: {error}"
        ) from error

    fetch = SourceFetchRecord(
        source_fetch_id=f"srf_{uuid.uuid4().hex}",
        requested_url=result.requested_url,
        accessed_at=accessed_at,
        outcome=SourceFetchOutcome.SUCCESS,
        final_url=result.final_url,
        http_status=result.http_status,
        content_type=result.content_type,
        response_content_hash=_content_digest(result.raw_html),
        extracted_content_hash=_content_digest(result.extracted_text),
    )
    source = ItinerarySource(
        kind=ItinerarySourceKind.URL,
        text=result.extracted_text,
        requested_url=url,
    )
    return source, fetch


def inspect_trip(workspace: Path, trip_id: str) -> TripInspectionResult:
    repository = WorkspaceRepository(workspace)
    if not repository.database_path.is_file():
        raise UserFacingError(
            f"Workspace is not initialized: run init for {workspace.resolve()}"
        )
    result = repository.inspect_trip(trip_id)
    if result is None:
        raise UserFacingError(f"Trip not found: {trip_id}")
    return result


def _resume_trip_update(
    repository: WorkspaceRepository, workspace: Path, pending: TripUpdateStage
) -> TripRecord:
    attempt = repository.start_retry(pending)
    _publish_trip_update(repository, workspace, pending, attempt)
    return pending.trip


def _publish_trip_update(
    repository: WorkspaceRepository,
    workspace: Path,
    stage: TripUpdateStage,
    attempt: StageAttempt,
) -> None:
    persisted_itinerary = repository.load_original_itinerary(
        stage.trip.itinerary_revision_id
    )
    try:
        publish_trip_artifacts(workspace, stage.trip, persisted_itinerary)
    except Exception as error:
        try:
            repository.fail_attempt(stage, attempt, "ARTIFACT_WRITE_FAILED")
        except Exception as persistence_error:
            raise StageExecutionError(
                "Itinerary update failed while saving recovery state; retry "
                "the same command."
            ) from persistence_error
        raise StageExecutionError(
            "Itinerary update did not complete; fix the workspace and retry "
            "the same command."
        ) from error

    try:
        repository.complete_trip_update(stage, attempt)
    except Exception as error:
        raise StageExecutionError(
            "Itinerary update was saved but completion was interrupted; "
            "retry the same command."
        ) from error


def _trip_input_hash(name: str, itinerary: str) -> str:
    digest = hashlib.sha256()
    digest.update(name.encode("utf-8"))
    digest.update(b"\0")
    digest.update(itinerary.encode("utf-8"))
    return digest.hexdigest()


def _content_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    slug = re.sub(r"[_\W]+", "-", normalized, flags=re.UNICODE).strip("-")
    return slug or "trip"
