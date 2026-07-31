from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class StageStatus(StrEnum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TripCreationOutcome(StrEnum):
    CREATED = "created"
    REUSED = "reused"
    RESUMED = "resumed"
    REGENERATED = "regenerated"


class ItineraryProcessingOutcome(StrEnum):
    PROCESSED = "processed"
    REUSED = "reused"
    RESUMED = "resumed"
    REGENERATED = "regenerated"


class SanitizationStatus(StrEnum):
    CLEAR = "CLEAR"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(frozen=True)
class TripRecord:
    trip_id: str
    name: str
    slug: str
    itinerary_revision_id: str
    revision_number: int
    created_at: str
    current_editorial_package_version: str | None

    @property
    def directory_name(self) -> str:
        return f"{self.slug}--{self.trip_id}"


@dataclass(frozen=True)
class TripCreationStage:
    trip: TripRecord
    workflow_stage_id: str
    status: StageStatus


@dataclass(frozen=True)
class StageAttempt:
    workflow_stage_id: str
    stage_attempt_id: str
    attempt_number: int


@dataclass(frozen=True)
class TripCreationResult:
    trip: TripRecord
    outcome: TripCreationOutcome

    @property
    def trip_id(self) -> str:
        return self.trip.trip_id

    @property
    def name(self) -> str:
        return self.trip.name

    @property
    def revision_number(self) -> int:
        return self.trip.revision_number


@dataclass(frozen=True)
class TripInspectionResult:
    trip_id: str
    name: str
    slug: str
    revision_number: int
    creation_status: StageStatus
    source_path: Path


@dataclass(frozen=True)
class SupplierDataFinding:
    finding_id: str
    category: str
    source_line: int
    matched_text_hash: str
    review_status: str = "PENDING"

    @property
    def source_locator(self) -> str:
        return f"line {self.source_line}"


@dataclass(frozen=True)
class SanitizationResult:
    sanitized_text: str
    status: SanitizationStatus
    findings: tuple[SupplierDataFinding, ...]


@dataclass(frozen=True)
class ItineraryProcessingStage:
    trip: TripRecord
    workflow_stage_id: str
    status: StageStatus
    input_hash: str


@dataclass(frozen=True)
class ItineraryProcessingResult:
    trip: TripRecord
    outcome: ItineraryProcessingOutcome
    sanitization_status: SanitizationStatus
    finding_count: int
    missing_information_count: int
    fact_conflict_count: int
    export_blocked: bool

    @property
    def trip_id(self) -> str:
        return self.trip.trip_id

    @property
    def name(self) -> str:
        return self.trip.name

    @property
    def revision_number(self) -> int:
        return self.trip.revision_number
