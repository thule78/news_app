from __future__ import annotations

import hashlib
from pathlib import Path
import re
import unicodedata

from aa_content.artifacts import publish_trip_artifacts
from aa_content.errors import StageExecutionError, UserFacingError
from aa_content.models import (
    StageStatus,
    TripCreationOutcome,
    TripCreationResult,
    TripInspectionResult,
)
from aa_content.persistence import WorkspaceRepository


def create_trip(
    workspace: Path, name: str, itinerary: str, *, force: bool = False
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
        stage, attempt = repository.start_trip_creation(
            normalized_name,
            _slugify(normalized_name),
            itinerary,
            input_hash,
        )
        outcome = TripCreationOutcome.CREATED
        persisted_itinerary = itinerary
    else:
        attempt = repository.start_retry(stage)
        persisted_itinerary = repository.load_original_itinerary(
            stage.trip.itinerary_revision_id
        )
        outcome = (
            TripCreationOutcome.REGENERATED
            if force
            else TripCreationOutcome.RESUMED
        )

    try:
        publish_trip_artifacts(workspace, stage.trip, persisted_itinerary)
    except Exception as error:
        try:
            repository.fail_attempt(stage, attempt, "ARTIFACT_WRITE_FAILED")
        except Exception as persistence_error:
            raise StageExecutionError(
                "Trip creation failed while saving recovery state; retry the same "
                "command."
            ) from persistence_error
        raise StageExecutionError(
            "Trip creation did not complete; fix the workspace and retry the same "
            "command."
        ) from error

    try:
        repository.complete_attempt(stage, attempt)
    except Exception as error:
        raise StageExecutionError(
            "Trip artifacts were saved but completion was interrupted; retry the "
            "same command."
        ) from error
    return TripCreationResult(stage.trip, outcome)


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


def _trip_input_hash(name: str, itinerary: str) -> str:
    digest = hashlib.sha256()
    digest.update(name.encode("utf-8"))
    digest.update(b"\0")
    digest.update(itinerary.encode("utf-8"))
    return digest.hexdigest()


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    slug = re.sub(r"[_\W]+", "-", normalized, flags=re.UNICODE).strip("-")
    return slug or "trip"
