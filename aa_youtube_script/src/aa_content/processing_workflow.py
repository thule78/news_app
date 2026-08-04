from __future__ import annotations

import os
from pathlib import Path

from aa_content.artifacts import publish_itinerary_processing_artifacts
from aa_content.config import load_openai_config
from aa_content.errors import StageExecutionError, UserFacingError
from aa_content.models import (
    ItineraryProcessingOutcome,
    ItineraryProcessingResult,
    StageStatus,
)
from aa_content.persistence import WorkspaceRepository
from aa_content.providers import (
    FakeItineraryProvider,
    NormalizationProvider,
    OpenAIItineraryProvider,
)
from aa_content.sanitization import sanitize_itinerary

FAKE_PROVIDER_ENVIRONMENT_VARIABLE = "AA_CONTENT_FAKE_PROVIDERS"


def process_itinerary(
    workspace: Path,
    trip_id: str,
    *,
    force: bool = False,
    provider: NormalizationProvider | None = None,
) -> ItineraryProcessingResult:
    repository = WorkspaceRepository(workspace)
    if not repository.database_path.is_file():
        raise UserFacingError(
            f"Workspace is not initialized: run init for {workspace.resolve()}"
        )

    trip = repository.load_current_trip(trip_id)
    if trip is None:
        raise UserFacingError(f"Trip not found: {trip_id}")

    current_text = repository.load_original_itinerary(trip.itinerary_revision_id)
    input_hash = _content_hash(current_text)
    stage = repository.find_itinerary_processing(
        trip.itinerary_revision_id, input_hash
    )

    if stage is not None and stage.status is StageStatus.COMPLETED and not force:
        outcome = ItineraryProcessingOutcome.REUSED
    else:
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

        original_text = repository.load_original_itinerary(
            stage.trip.itinerary_revision_id
        )
        active_provider = provider or _default_provider(workspace)
        sanitization = sanitize_itinerary(original_text)
        normalized = active_provider.normalize(sanitization.sanitized_text)

        try:
            repository.persist_itinerary_processing(
                stage.trip.itinerary_revision_id, sanitization, normalized
            )
            export_blocked = bool(sanitization.findings)
            publish_itinerary_processing_artifacts(
                workspace,
                stage.trip,
                sanitization,
                normalized,
                export_blocked=export_blocked,
            )
        except Exception as error:
            try:
                repository.fail_attempt(stage, attempt, "PROCESSING_FAILED")
            except Exception as persistence_error:
                raise StageExecutionError(
                    "Itinerary processing failed while saving recovery state; "
                    "retry the same command."
                ) from persistence_error
            raise StageExecutionError(
                "Itinerary processing did not complete; fix the workspace and "
                "retry the same command."
            ) from error

        try:
            repository.complete_itinerary_processing(stage, attempt)
        except Exception as error:
            raise StageExecutionError(
                "Itinerary processing results were saved but completion was "
                "interrupted; retry the same command."
            ) from error

    (
        sanitization_status,
        finding_count,
        missing_information_count,
        fact_conflict_count,
        export_blocked,
    ) = repository.load_itinerary_processing_summary(stage.trip.itinerary_revision_id)

    return ItineraryProcessingResult(
        trip=stage.trip,
        outcome=outcome,
        sanitization_status=sanitization_status,
        finding_count=finding_count,
        missing_information_count=missing_information_count,
        fact_conflict_count=fact_conflict_count,
        export_blocked=export_blocked,
    )


def _default_provider(workspace: Path) -> NormalizationProvider:
    if os.environ.get(FAKE_PROVIDER_ENVIRONMENT_VARIABLE):
        return FakeItineraryProvider()
    config = load_openai_config(workspace)
    return OpenAIItineraryProvider(config.api_key)


def _content_hash(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()
