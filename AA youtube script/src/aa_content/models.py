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
