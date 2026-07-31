from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

from aa_content.models import (
    StageAttempt,
    StageStatus,
    TripCreationStage,
    TripInspectionResult,
    TripRecord,
)


WORKSPACE_INIT_STAGE_ID = "workspace_init_v1"
WORKSPACE_INIT_INPUT_HASH = "workspace-schema-v1"


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS trips (
    trip_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    created_at TEXT NOT NULL,
    current_itinerary_revision_id TEXT
        REFERENCES itinerary_revisions(itinerary_revision_id),
    current_editorial_package_version TEXT
);

CREATE TABLE IF NOT EXISTS itinerary_revisions (
    itinerary_revision_id TEXT PRIMARY KEY,
    trip_id TEXT NOT NULL REFERENCES trips(trip_id),
    revision_number INTEGER NOT NULL CHECK (revision_number > 0),
    source_kind TEXT NOT NULL CHECK (source_kind IN ('PASTED_TEXT')),
    original_text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (trip_id, revision_number)
);

CREATE TABLE IF NOT EXISTS workflow_stages (
    workflow_stage_id TEXT PRIMARY KEY,
    trip_id TEXT REFERENCES trips(trip_id),
    itinerary_revision_id TEXT
        REFERENCES itinerary_revisions(itinerary_revision_id),
    scope_key TEXT NOT NULL,
    stage_name TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN ('IN_PROGRESS', 'COMPLETED', 'FAILED')),
    result_json TEXT NOT NULL,
    completed_at TEXT,
    UNIQUE (scope_key, stage_name, input_hash)
);

CREATE TABLE IF NOT EXISTS stage_attempts (
    stage_attempt_id TEXT PRIMARY KEY,
    workflow_stage_id TEXT NOT NULL REFERENCES workflow_stages(workflow_stage_id),
    attempt_number INTEGER NOT NULL CHECK (attempt_number > 0),
    status TEXT NOT NULL
        CHECK (status IN ('IN_PROGRESS', 'COMPLETED', 'FAILED')),
    started_at TEXT NOT NULL,
    completed_at TEXT,
    error_code TEXT,
    UNIQUE (workflow_stage_id, attempt_number)
);

PRAGMA user_version = 1;
"""


class WorkspaceRepository:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.database_path = workspace / "aa_content.db"

    def initialize_database(self) -> bool:
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            completed = connection.execute(
                """
                SELECT 1
                FROM workflow_stages
                WHERE workflow_stage_id = ? AND status = ?
                """,
                (WORKSPACE_INIT_STAGE_ID, StageStatus.COMPLETED),
            ).fetchone()
            if completed is not None:
                return True

            now = _utc_now()
            connection.execute(
                """
                INSERT INTO workflow_stages (
                    workflow_stage_id,
                    trip_id,
                    scope_key,
                    stage_name,
                    input_hash,
                    status,
                    result_json,
                    completed_at
                ) VALUES (?, NULL, 'workspace', 'workspace_init', ?, ?, '{}', ?)
                """,
                (
                    WORKSPACE_INIT_STAGE_ID,
                    WORKSPACE_INIT_INPUT_HASH,
                    StageStatus.COMPLETED,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO stage_attempts (
                    stage_attempt_id,
                    workflow_stage_id,
                    attempt_number,
                    status,
                    started_at,
                    completed_at
                ) VALUES (?, ?, 1, ?, ?, ?)
                """,
                (
                    f"{WORKSPACE_INIT_STAGE_ID}_attempt_1",
                    WORKSPACE_INIT_STAGE_ID,
                    StageStatus.COMPLETED,
                    now,
                    now,
                ),
            )
        return False

    def find_trip_creation(self, input_hash: str) -> TripCreationStage | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    trip.trip_id,
                    trip.name,
                    trip.slug,
                    revision.itinerary_revision_id,
                    revision.revision_number,
                    trip.created_at,
                    trip.current_editorial_package_version,
                    stage.workflow_stage_id,
                    stage.status
                FROM workflow_stages AS stage
                JOIN trips AS trip ON trip.trip_id = stage.trip_id
                JOIN itinerary_revisions AS revision
                  ON revision.itinerary_revision_id =
                     stage.itinerary_revision_id
                WHERE stage.scope_key = ?
                  AND stage.stage_name = 'trip_create'
                  AND stage.input_hash = ?
                """,
                (_trip_scope_key(input_hash), input_hash),
            ).fetchone()
        if row is None:
            return None
        return _trip_creation_stage_from_row(row)

    def start_trip_creation(
        self, name: str, slug: str, itinerary: str, input_hash: str
    ) -> tuple[TripCreationStage, StageAttempt]:
        now = _utc_now()
        trip = TripRecord(
            trip_id=f"trp_{uuid.uuid4().hex}",
            name=name,
            slug=slug,
            itinerary_revision_id=f"irv_{uuid.uuid4().hex}",
            revision_number=1,
            created_at=now,
            current_editorial_package_version=None,
        )
        workflow_stage_id = f"wfs_{uuid.uuid4().hex}"
        attempt = StageAttempt(
            workflow_stage_id=workflow_stage_id,
            stage_attempt_id=f"sta_{uuid.uuid4().hex}",
            attempt_number=1,
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO trips (
                    trip_id, name, slug, created_at, current_itinerary_revision_id
                ) VALUES (?, ?, ?, ?, NULL)
                """,
                (trip.trip_id, trip.name, trip.slug, trip.created_at),
            )
            connection.execute(
                """
                INSERT INTO itinerary_revisions (
                    itinerary_revision_id,
                    trip_id,
                    revision_number,
                    source_kind,
                    original_text,
                    content_hash,
                    created_at
                ) VALUES (?, ?, 1, 'PASTED_TEXT', ?, ?, ?)
                """,
                (
                    trip.itinerary_revision_id,
                    trip.trip_id,
                    itinerary,
                    hashlib.sha256(itinerary.encode("utf-8")).hexdigest(),
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE trips
                SET current_itinerary_revision_id = ?
                WHERE trip_id = ?
                """,
                (trip.itinerary_revision_id, trip.trip_id),
            )
            connection.execute(
                """
                INSERT INTO workflow_stages (
                    workflow_stage_id,
                    trip_id,
                    itinerary_revision_id,
                    scope_key,
                    stage_name,
                    input_hash,
                    status,
                    result_json,
                    completed_at
                ) VALUES (?, ?, ?, ?, 'trip_create', ?, ?, '{}', NULL)
                """,
                (
                    workflow_stage_id,
                    trip.trip_id,
                    trip.itinerary_revision_id,
                    _trip_scope_key(input_hash),
                    input_hash,
                    StageStatus.IN_PROGRESS,
                ),
            )
            self._insert_attempt(connection, attempt, now)
        return (
            TripCreationStage(trip, workflow_stage_id, StageStatus.IN_PROGRESS),
            attempt,
        )

    def start_retry(self, stage: TripCreationStage) -> StageAttempt:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE stage_attempts
                SET status = ?, completed_at = ?, error_code = 'INTERRUPTED'
                WHERE workflow_stage_id = ? AND status = ?
                """,
                (
                    StageStatus.FAILED,
                    now,
                    stage.workflow_stage_id,
                    StageStatus.IN_PROGRESS,
                ),
            )
            attempt_number = connection.execute(
                """
                SELECT COALESCE(MAX(attempt_number), 0) + 1
                FROM stage_attempts
                WHERE workflow_stage_id = ?
                """,
                (stage.workflow_stage_id,),
            ).fetchone()[0]
            attempt = StageAttempt(
                workflow_stage_id=stage.workflow_stage_id,
                stage_attempt_id=f"sta_{uuid.uuid4().hex}",
                attempt_number=attempt_number,
            )
            connection.execute(
                """
                UPDATE workflow_stages
                SET status = ?, completed_at = NULL
                WHERE workflow_stage_id = ?
                """,
                (StageStatus.IN_PROGRESS, stage.workflow_stage_id),
            )
            self._insert_attempt(connection, attempt, now)
        return attempt

    def complete_attempt(
        self, stage: TripCreationStage, attempt: StageAttempt
    ) -> None:
        now = _utc_now()
        result_json = json.dumps(
            {
                "trip_id": stage.trip.trip_id,
                "itinerary_revision_id": stage.trip.itinerary_revision_id,
                "revision_number": stage.trip.revision_number,
            },
            sort_keys=True,
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE stage_attempts
                SET status = ?, completed_at = ?, error_code = NULL
                WHERE stage_attempt_id = ?
                """,
                (StageStatus.COMPLETED, now, attempt.stage_attempt_id),
            )
            connection.execute(
                """
                UPDATE workflow_stages
                SET status = ?, result_json = ?, completed_at = ?
                WHERE workflow_stage_id = ?
                """,
                (
                    StageStatus.COMPLETED,
                    result_json,
                    now,
                    stage.workflow_stage_id,
                ),
            )

    def fail_attempt(
        self, stage: TripCreationStage, attempt: StageAttempt, error_code: str
    ) -> None:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE stage_attempts
                SET status = ?, completed_at = ?, error_code = ?
                WHERE stage_attempt_id = ?
                """,
                (
                    StageStatus.FAILED,
                    now,
                    error_code,
                    attempt.stage_attempt_id,
                ),
            )
            connection.execute(
                """
                UPDATE workflow_stages
                SET status = ?, completed_at = ?
                WHERE workflow_stage_id = ?
                """,
                (StageStatus.FAILED, now, stage.workflow_stage_id),
            )

    def load_original_itinerary(self, itinerary_revision_id: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT original_text
                FROM itinerary_revisions
                WHERE itinerary_revision_id = ?
                """,
                (itinerary_revision_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError("Persisted Itinerary Revision disappeared.")
        return row[0]

    def inspect_trip(self, trip_id: str) -> TripInspectionResult | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    trip.trip_id,
                    trip.name,
                    trip.slug,
                    revision.revision_number,
                    stage.status
                FROM trips AS trip
                JOIN itinerary_revisions AS revision
                  ON revision.itinerary_revision_id =
                     trip.current_itinerary_revision_id
                JOIN workflow_stages AS stage
                  ON stage.trip_id = trip.trip_id
                 AND stage.stage_name = 'trip_create'
                WHERE trip.trip_id = ?
                ORDER BY stage.completed_at DESC
                LIMIT 1
                """,
                (trip_id,),
            ).fetchone()
        if row is None:
            return None
        persisted_trip_id, name, slug, revision_number, status = row
        source_path = (
            Path("outputs")
            / f"{slug}--{persisted_trip_id}"
            / "source"
            / f"r{revision_number}"
            / "original-itinerary.txt"
        )
        return TripInspectionResult(
            trip_id=persisted_trip_id,
            name=name,
            slug=slug,
            revision_number=revision_number,
            creation_status=StageStatus(status),
            source_path=source_path,
        )

    @staticmethod
    def _insert_attempt(
        connection: sqlite3.Connection, attempt: StageAttempt, started_at: str
    ) -> None:
        connection.execute(
            """
            INSERT INTO stage_attempts (
                stage_attempt_id,
                workflow_stage_id,
                attempt_number,
                status,
                started_at,
                completed_at
            ) VALUES (?, ?, ?, ?, ?, NULL)
            """,
            (
                attempt.stage_attempt_id,
                attempt.workflow_stage_id,
                attempt.attempt_number,
                StageStatus.IN_PROGRESS,
                started_at,
            ),
        )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


def _trip_creation_stage_from_row(row: tuple[object, ...]) -> TripCreationStage:
    (
        trip_id,
        name,
        slug,
        revision_id,
        revision_number,
        created_at,
        current_package_version,
        stage_id,
        status,
    ) = row
    trip = TripRecord(
        trip_id=str(trip_id),
        name=str(name),
        slug=str(slug),
        itinerary_revision_id=str(revision_id),
        revision_number=int(revision_number),
        created_at=str(created_at),
        current_editorial_package_version=(
            str(current_package_version)
            if current_package_version is not None
            else None
        ),
    )
    return TripCreationStage(trip, str(stage_id), StageStatus(str(status)))


def _trip_scope_key(input_hash: str) -> str:
    return f"trip-create:{input_hash}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
