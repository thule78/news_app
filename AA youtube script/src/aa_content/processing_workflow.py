from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
from typing import NoReturn

from aa_content.artifacts import publish_itinerary_processing_artifacts
from aa_content.errors import StageExecutionError, UserFacingError
from aa_content.models import (
    ItineraryProcessingOutcome,
    ItineraryProcessingResult,
    ItineraryProcessingStage,
    StageAttempt,
    StageStatus,
)
from aa_content.normalization import (
    ItineraryNormalizer,
    NORMALIZER_VERSION,
    RuleBasedItineraryNormalizer,
)
from aa_content.persistence import WorkspaceRepository
from aa_content.sanitization import (
    SANITIZER_VERSION,
    contains_possible_supplier_data,
    sanitize_itinerary,
)


def process_itinerary(
    workspace: Path,
    trip_id: str,
    *,
    force: bool = False,
    normalizer: ItineraryNormalizer | None = None,
) -> ItineraryProcessingResult:
    repository = WorkspaceRepository(workspace)
    if not repository.database_path.is_file():
        raise UserFacingError(
            f"Workspace is not initialized: run init for {workspace.resolve()}"
        )
    repository.ensure_schema()
    trip = repository.load_current_trip(trip_id)
    if trip is None:
        raise UserFacingError(f"Trip not found: {trip_id}")

    original_itinerary = repository.load_original_itinerary(
        trip.itinerary_revision_id
    )
    input_hash = _processing_input_hash(original_itinerary)
    stage = repository.find_itinerary_processing(
        trip.itinerary_revision_id, input_hash
    )
    if stage is not None and stage.status is StageStatus.COMPLETED and not force:
        return repository.load_itinerary_processing_result(
            stage, ItineraryProcessingOutcome.REUSED
        )

    if stage is None:
        stage, attempt = repository.start_itinerary_processing(trip, input_hash)
        outcome = ItineraryProcessingOutcome.PROCESSED
    else:
        attempt = repository.start_retry(stage)
        outcome = (
            ItineraryProcessingOutcome.REGENERATED
            if force
            else ItineraryProcessingOutcome.RESUMED
        )

    try:
        sanitization = sanitize_itinerary(
            trip.itinerary_revision_id, original_itinerary
        )
        selected_normalizer = normalizer or RuleBasedItineraryNormalizer()
        normalized = selected_normalizer.normalize(
            trip.itinerary_revision_id,
            sanitization.sanitized_text,
        )
        serialized_normalized = json.dumps(normalized, sort_keys=True)
        export_blocked = contains_possible_supplier_data(
            sanitization.sanitized_text
        ) or contains_possible_supplier_data(serialized_normalized)
    except Exception as error:
        _record_failure(
            repository,
            stage,
            attempt,
            "ITINERARY_PROCESSING_FAILED",
            "Itinerary processing failed; retry after checking the source.",
            error,
        )

    try:
        publish_itinerary_processing_artifacts(
            workspace,
            trip,
            sanitization,
            normalized,
            export_blocked=export_blocked,
        )
    except Exception as error:
        _record_failure(
            repository,
            stage,
            attempt,
            "ARTIFACT_WRITE_FAILED",
            "Itinerary processing did not complete; fix the workspace and retry.",
            error,
        )

    try:
        result = repository.complete_itinerary_processing(
            stage,
            attempt,
            sanitization,
            normalized,
            export_blocked=export_blocked,
        )
    except Exception as error:
        raise StageExecutionError(
            "Itinerary artifacts were saved but completion was interrupted; retry "
            "the same command."
        ) from error
    return replace(result, outcome=outcome)


def _processing_input_hash(original_itinerary: str) -> str:
    digest = hashlib.sha256()
    for part in (SANITIZER_VERSION, NORMALIZER_VERSION, original_itinerary):
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _record_failure(
    repository: WorkspaceRepository,
    stage: ItineraryProcessingStage,
    attempt: StageAttempt,
    error_code: str,
    safe_message: str,
    cause: Exception,
) -> NoReturn:
    try:
        repository.fail_attempt(stage, attempt, error_code)
    except Exception as persistence_error:
        raise StageExecutionError(
            "Itinerary processing failed while saving recovery state; retry the "
            "same command."
        ) from persistence_error
    raise StageExecutionError(safe_message) from cause
