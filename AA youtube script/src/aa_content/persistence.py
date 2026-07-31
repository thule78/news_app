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
    ItineraryProcessingOutcome,
    ItineraryProcessingResult,
    ItineraryProcessingStage,
    SanitizationResult,
    SanitizationStatus,
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

CREATE TABLE IF NOT EXISTS workflow_stage_records (
    workflow_stage_id TEXT NOT NULL
        REFERENCES workflow_stages(workflow_stage_id),
    record_type TEXT NOT NULL,
    record_id TEXT NOT NULL,
    PRIMARY KEY (workflow_stage_id, record_type, record_id)
);

CREATE TABLE IF NOT EXISTS sanitized_itineraries (
    itinerary_revision_id TEXT PRIMARY KEY
        REFERENCES itinerary_revisions(itinerary_revision_id),
    sanitized_text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('CLEAR', 'REVIEW_REQUIRED')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS supplier_data_findings (
    finding_id TEXT PRIMARY KEY,
    itinerary_revision_id TEXT NOT NULL
        REFERENCES itinerary_revisions(itinerary_revision_id),
    category TEXT NOT NULL,
    source_line INTEGER NOT NULL CHECK (source_line > 0),
    matched_text_hash TEXT NOT NULL,
    review_status TEXT NOT NULL CHECK (review_status IN ('PENDING', 'APPROVED'))
);

CREATE TABLE IF NOT EXISTS normalized_itineraries (
    itinerary_revision_id TEXT PRIMARY KEY
        REFERENCES itinerary_revisions(itinerary_revision_id),
    normalized_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    trip_id TEXT NOT NULL REFERENCES trips(trip_id),
    itinerary_revision_id TEXT
        REFERENCES itinerary_revisions(itinerary_revision_id),
    claim_kind TEXT NOT NULL,
    statement TEXT NOT NULL,
    value_json TEXT NOT NULL,
    evidence_status TEXT NOT NULL CHECK (
        evidence_status IN (
            'VERIFIED', 'CORROBORATED', 'INDICATIVE', 'UNVERIFIED', 'UNKNOWN'
        )
    ),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id TEXT PRIMARY KEY,
    itinerary_revision_id TEXT
        REFERENCES itinerary_revisions(itinerary_revision_id),
    evidence_kind TEXT NOT NULL,
    source_locator TEXT NOT NULL,
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claim_evidence (
    claim_id TEXT NOT NULL REFERENCES claims(claim_id),
    evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id),
    PRIMARY KEY (claim_id, evidence_id)
);

CREATE TABLE IF NOT EXISTS itinerary_warnings (
    warning_id TEXT PRIMARY KEY,
    itinerary_revision_id TEXT NOT NULL
        REFERENCES itinerary_revisions(itinerary_revision_id),
    code TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('WARNING', 'BLOCKING')),
    message TEXT NOT NULL,
    source_locator TEXT,
    review_status TEXT NOT NULL CHECK (
        review_status IN ('NOT_REQUIRED', 'PENDING', 'ACKNOWLEDGED')
    )
);

CREATE TABLE IF NOT EXISTS fact_conflicts (
    fact_conflict_id TEXT PRIMARY KEY,
    itinerary_revision_id TEXT NOT NULL
        REFERENCES itinerary_revisions(itinerary_revision_id),
    subject TEXT NOT NULL,
    details_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('UNRESOLVED', 'RESOLVED'))
);

CREATE TABLE IF NOT EXISTS export_blocks (
    export_block_id TEXT PRIMARY KEY,
    itinerary_revision_id TEXT NOT NULL
        REFERENCES itinerary_revisions(itinerary_revision_id),
    code TEXT NOT NULL CHECK (code = 'UNSANITIZED_SUPPLIER_DATA'),
    message TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'RESOLVED'))
);

PRAGMA user_version = 3;
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

    def ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            self._backfill_itinerary_stage_ownership(connection)

    @staticmethod
    def _backfill_itinerary_stage_ownership(
        connection: sqlite3.Connection,
    ) -> None:
        stages = connection.execute(
            """
            SELECT stage.workflow_stage_id, stage.itinerary_revision_id
            FROM workflow_stages AS stage
            WHERE stage.stage_name = 'itinerary_process'
              AND stage.completed_at = (
                  SELECT MAX(candidate.completed_at)
                  FROM workflow_stages AS candidate
                  WHERE candidate.stage_name = 'itinerary_process'
                    AND candidate.itinerary_revision_id =
                        stage.itinerary_revision_id
              )
            """
        ).fetchall()
        for workflow_stage_id, itinerary_revision_id in stages:
            ownership_exists = connection.execute(
                """
                SELECT 1
                FROM workflow_stage_records
                WHERE workflow_stage_id = ?
                LIMIT 1
                """,
                (workflow_stage_id,),
            ).fetchone()
            if ownership_exists is not None:
                continue
            for record_type, table, primary_key, extra_filter in (
                (
                    "sanitized_itineraries",
                    "sanitized_itineraries",
                    "itinerary_revision_id",
                    "",
                ),
                (
                    "normalized_itineraries",
                    "normalized_itineraries",
                    "itinerary_revision_id",
                    "",
                ),
                (
                    "supplier_data_findings",
                    "supplier_data_findings",
                    "finding_id",
                    "",
                ),
                (
                    "itinerary_warnings",
                    "itinerary_warnings",
                    "warning_id",
                    (
                        "AND code IN "
                        "('SUPPLIER_DATA_REMOVED', 'MISSING_INFORMATION')"
                    ),
                ),
                (
                    "claims",
                    "claims",
                    "claim_id",
                    (
                        "AND claim_kind IN ("
                        "'ROUTE_LEG', 'ACTIVITY', 'OVERNIGHT_STOP', "
                        "'ACCOMMODATION', 'MEAL', 'TRANSPORT', "
                        "'PRACTICAL_CONSTRAINT')"
                    ),
                ),
                (
                    "evidence",
                    "evidence",
                    "evidence_id",
                    "AND evidence_kind = 'ITINERARY'",
                ),
                (
                    "fact_conflicts",
                    "fact_conflicts",
                    "fact_conflict_id",
                    "",
                ),
                (
                    "export_blocks",
                    "export_blocks",
                    "export_block_id",
                    "AND code = 'UNSANITIZED_SUPPLIER_DATA'",
                ),
            ):
                connection.execute(
                    f"""
                    INSERT OR IGNORE INTO workflow_stage_records (
                        workflow_stage_id, record_type, record_id
                    )
                    SELECT ?, ?, {primary_key}
                    FROM {table}
                    WHERE itinerary_revision_id = ?
                    {extra_filter}
                    """,
                    (
                        str(workflow_stage_id),
                        record_type,
                        str(itinerary_revision_id),
                    ),
                )

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

    def load_current_trip(self, trip_id: str) -> TripRecord | None:
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
                    trip.current_editorial_package_version
                FROM trips AS trip
                JOIN itinerary_revisions AS revision
                  ON revision.itinerary_revision_id =
                     trip.current_itinerary_revision_id
                WHERE trip.trip_id = ?
                """,
                (trip_id,),
            ).fetchone()
        return _trip_record_from_row(row) if row is not None else None

    def find_itinerary_processing(
        self, itinerary_revision_id: str, input_hash: str
    ) -> ItineraryProcessingStage | None:
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
                    stage.status,
                    stage.input_hash
                FROM workflow_stages AS stage
                JOIN trips AS trip ON trip.trip_id = stage.trip_id
                JOIN itinerary_revisions AS revision
                  ON revision.itinerary_revision_id =
                     stage.itinerary_revision_id
                WHERE stage.scope_key = ?
                  AND stage.stage_name = 'itinerary_process'
                  AND stage.input_hash = ?
                """,
                (_itinerary_scope_key(itinerary_revision_id), input_hash),
            ).fetchone()
        if row is None:
            return None
        return _itinerary_processing_stage_from_row(row)

    def start_itinerary_processing(
        self, trip: TripRecord, input_hash: str
    ) -> tuple[ItineraryProcessingStage, StageAttempt]:
        now = _utc_now()
        workflow_stage_id = f"wfs_{uuid.uuid4().hex}"
        stage = ItineraryProcessingStage(
            trip=trip,
            workflow_stage_id=workflow_stage_id,
            status=StageStatus.IN_PROGRESS,
            input_hash=input_hash,
        )
        attempt = StageAttempt(
            workflow_stage_id=workflow_stage_id,
            stage_attempt_id=f"sta_{uuid.uuid4().hex}",
            attempt_number=1,
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
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
                ) VALUES (?, ?, ?, ?, 'itinerary_process', ?, ?, '{}', NULL)
                """,
                (
                    workflow_stage_id,
                    trip.trip_id,
                    trip.itinerary_revision_id,
                    _itinerary_scope_key(trip.itinerary_revision_id),
                    input_hash,
                    StageStatus.IN_PROGRESS,
                ),
            )
            self._insert_attempt(connection, attempt, now)
        return stage, attempt

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

    def start_retry(
        self, stage: TripCreationStage | ItineraryProcessingStage
    ) -> StageAttempt:
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
        self,
        stage: TripCreationStage | ItineraryProcessingStage,
        attempt: StageAttempt,
        error_code: str,
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

    def complete_itinerary_processing(
        self,
        stage: ItineraryProcessingStage,
        attempt: StageAttempt,
        sanitization: SanitizationResult,
        normalized: dict[str, object],
        *,
        export_blocked: bool,
    ) -> ItineraryProcessingResult:
        now = _utc_now()
        missing_information = _list_field(normalized, "missing_information")
        fact_conflicts = _list_field(normalized, "fact_conflicts")
        result_json = json.dumps(
            {
                "trip_id": stage.trip.trip_id,
                "itinerary_revision_id": stage.trip.itinerary_revision_id,
                "sanitization_status": sanitization.status,
                "finding_count": len(sanitization.findings),
                "missing_information_count": len(missing_information),
                "fact_conflict_count": len(fact_conflicts),
                "export_blocked": export_blocked,
            },
            sort_keys=True,
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._delete_itinerary_processing_records(
                connection, stage.trip.itinerary_revision_id
            )
            connection.execute(
                """
                INSERT INTO sanitized_itineraries (
                    itinerary_revision_id,
                    sanitized_text,
                    content_hash,
                    status,
                    created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    stage.trip.itinerary_revision_id,
                    sanitization.sanitized_text,
                    hashlib.sha256(
                        sanitization.sanitized_text.encode("utf-8")
                    ).hexdigest(),
                    sanitization.status,
                    now,
                ),
            )
            self._own_stage_record(
                connection,
                stage.workflow_stage_id,
                "sanitized_itineraries",
                stage.trip.itinerary_revision_id,
            )
            for finding in sanitization.findings:
                connection.execute(
                    """
                    INSERT INTO supplier_data_findings (
                        finding_id,
                        itinerary_revision_id,
                        category,
                        source_line,
                        matched_text_hash,
                        review_status
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        finding.finding_id,
                        stage.trip.itinerary_revision_id,
                        finding.category,
                        finding.source_line,
                        finding.matched_text_hash,
                        finding.review_status,
                    ),
                )
                self._own_stage_record(
                    connection,
                    stage.workflow_stage_id,
                    "supplier_data_findings",
                    finding.finding_id,
                )
                warning_id = f"wrn_{finding.finding_id.removeprefix('sdf_')}"
                connection.execute(
                    """
                    INSERT INTO itinerary_warnings (
                        warning_id,
                        itinerary_revision_id,
                        code,
                        severity,
                        message,
                        source_locator,
                        review_status
                    ) VALUES (?, ?, 'SUPPLIER_DATA_REMOVED', 'WARNING', ?, ?, 'PENDING')
                    """,
                    (
                        warning_id,
                        stage.trip.itinerary_revision_id,
                        "Possible Supplier Data was removed before normalization.",
                        finding.source_locator,
                    ),
                )
                self._own_stage_record(
                    connection,
                    stage.workflow_stage_id,
                    "itinerary_warnings",
                    warning_id,
                )
            for index, item in enumerate(missing_information, start=1):
                warning_id = _stable_database_id(
                    "wrn",
                    stage.trip.itinerary_revision_id,
                    "missing",
                    str(index),
                )
                connection.execute(
                    """
                    INSERT INTO itinerary_warnings (
                        warning_id,
                        itinerary_revision_id,
                        code,
                        severity,
                        message,
                        source_locator,
                        review_status
                    ) VALUES (?, ?, 'MISSING_INFORMATION', 'WARNING', ?, NULL,
                              'NOT_REQUIRED')
                    """,
                    (
                        warning_id,
                        stage.trip.itinerary_revision_id,
                        (
                            f"{item.get('scope', 'Trip')}: "
                            f"{item.get('field', 'unknown field')} is unknown."
                        ),
                    ),
                )
                self._own_stage_record(
                    connection,
                    stage.workflow_stage_id,
                    "itinerary_warnings",
                    warning_id,
                )
            connection.execute(
                """
                INSERT INTO normalized_itineraries (
                    itinerary_revision_id, normalized_json, created_at
                ) VALUES (?, ?, ?)
                """,
                (
                    stage.trip.itinerary_revision_id,
                    json.dumps(normalized, sort_keys=True),
                    now,
                ),
            )
            self._own_stage_record(
                connection,
                stage.workflow_stage_id,
                "normalized_itineraries",
                stage.trip.itinerary_revision_id,
            )
            self._insert_claims_and_evidence(
                connection,
                stage.workflow_stage_id,
                stage.trip,
                normalized,
                now,
            )
            for index, conflict in enumerate(fact_conflicts, start=1):
                fact_conflict_id = str(
                    conflict.get(
                        "fact_conflict_id",
                        _stable_database_id(
                            "fcf",
                            stage.trip.itinerary_revision_id,
                            str(index),
                        ),
                    )
                )
                connection.execute(
                    """
                    INSERT INTO fact_conflicts (
                        fact_conflict_id,
                        itinerary_revision_id,
                        subject,
                        details_json,
                        status
                    ) VALUES (?, ?, ?, ?, 'UNRESOLVED')
                    """,
                    (
                        fact_conflict_id,
                        stage.trip.itinerary_revision_id,
                        str(conflict.get("subject", "Unspecified Trip fact")),
                        json.dumps(conflict, sort_keys=True),
                    ),
                )
                self._own_stage_record(
                    connection,
                    stage.workflow_stage_id,
                    "fact_conflicts",
                    fact_conflict_id,
                )
            if export_blocked:
                export_block_id = _stable_database_id(
                    "exb",
                    stage.trip.itinerary_revision_id,
                    "supplier-data",
                )
                connection.execute(
                    """
                    INSERT INTO export_blocks (
                        export_block_id,
                        itinerary_revision_id,
                        code,
                        message,
                        status
                    ) VALUES (?, ?, 'UNSANITIZED_SUPPLIER_DATA', ?, 'ACTIVE')
                    """,
                    (
                        export_block_id,
                        stage.trip.itinerary_revision_id,
                        "Possible Supplier Data remains in export-bound content.",
                    ),
                )
                self._own_stage_record(
                    connection,
                    stage.workflow_stage_id,
                    "export_blocks",
                    export_block_id,
                )
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
        return ItineraryProcessingResult(
            trip=stage.trip,
            outcome=ItineraryProcessingOutcome.PROCESSED,
            sanitization_status=sanitization.status,
            finding_count=len(sanitization.findings),
            missing_information_count=len(missing_information),
            fact_conflict_count=len(fact_conflicts),
            export_blocked=export_blocked,
        )

    def load_itinerary_processing_result(
        self,
        stage: ItineraryProcessingStage,
        outcome: ItineraryProcessingOutcome,
    ) -> ItineraryProcessingResult:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    sanitized.status,
                    COUNT(DISTINCT finding.finding_id),
                    normalized.normalized_json,
                    COUNT(DISTINCT block.export_block_id)
                FROM sanitized_itineraries AS sanitized
                JOIN normalized_itineraries AS normalized
                  ON normalized.itinerary_revision_id =
                     sanitized.itinerary_revision_id
                LEFT JOIN supplier_data_findings AS finding
                  ON finding.itinerary_revision_id =
                     sanitized.itinerary_revision_id
                LEFT JOIN export_blocks AS block
                  ON block.itinerary_revision_id =
                     sanitized.itinerary_revision_id
                 AND block.status = 'ACTIVE'
                WHERE sanitized.itinerary_revision_id = ?
                GROUP BY sanitized.status, normalized.normalized_json
                """,
                (stage.trip.itinerary_revision_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError("Completed itinerary processing result disappeared.")
        status, finding_count, normalized_json, block_count = row
        normalized = json.loads(str(normalized_json))
        return ItineraryProcessingResult(
            trip=stage.trip,
            outcome=outcome,
            sanitization_status=SanitizationStatus(str(status)),
            finding_count=int(finding_count),
            missing_information_count=len(
                _list_field(normalized, "missing_information")
            ),
            fact_conflict_count=len(_list_field(normalized, "fact_conflicts")),
            export_blocked=int(block_count) > 0,
        )

    @staticmethod
    def _delete_itinerary_processing_records(
        connection: sqlite3.Connection, itinerary_revision_id: str
    ) -> None:
        connection.execute(
            """
            DELETE FROM claim_evidence
            WHERE claim_id IN (
                SELECT owned.record_id
                FROM workflow_stage_records AS owned
                JOIN workflow_stages AS stage
                  ON stage.workflow_stage_id = owned.workflow_stage_id
                WHERE stage.itinerary_revision_id = ?
                  AND stage.stage_name = 'itinerary_process'
                  AND owned.record_type = 'claims'
            )
               OR evidence_id IN (
                SELECT owned.record_id
                FROM workflow_stage_records AS owned
                JOIN workflow_stages AS stage
                  ON stage.workflow_stage_id = owned.workflow_stage_id
                WHERE stage.itinerary_revision_id = ?
                  AND stage.stage_name = 'itinerary_process'
                  AND owned.record_type = 'evidence'
            )
            """,
            (itinerary_revision_id, itinerary_revision_id),
        )
        for record_type, table, primary_key in (
            ("evidence", "evidence", "evidence_id"),
            ("claims", "claims", "claim_id"),
            ("itinerary_warnings", "itinerary_warnings", "warning_id"),
            ("fact_conflicts", "fact_conflicts", "fact_conflict_id"),
            ("export_blocks", "export_blocks", "export_block_id"),
            (
                "supplier_data_findings",
                "supplier_data_findings",
                "finding_id",
            ),
            (
                "normalized_itineraries",
                "normalized_itineraries",
                "itinerary_revision_id",
            ),
            (
                "sanitized_itineraries",
                "sanitized_itineraries",
                "itinerary_revision_id",
            ),
        ):
            connection.execute(
                f"""
                DELETE FROM {table}
                WHERE {primary_key} IN (
                    SELECT owned.record_id
                    FROM workflow_stage_records AS owned
                    JOIN workflow_stages AS stage
                      ON stage.workflow_stage_id = owned.workflow_stage_id
                    WHERE stage.itinerary_revision_id = ?
                      AND stage.stage_name = 'itinerary_process'
                      AND owned.record_type = ?
                )
                """,
                (itinerary_revision_id, record_type),
            )
        connection.execute(
            """
            DELETE FROM workflow_stage_records
            WHERE workflow_stage_id IN (
                SELECT workflow_stage_id
                FROM workflow_stages
                WHERE itinerary_revision_id = ?
                  AND stage_name = 'itinerary_process'
            )
            """,
            (itinerary_revision_id,),
        )

    @staticmethod
    def _insert_claims_and_evidence(
        connection: sqlite3.Connection,
        workflow_stage_id: str,
        trip: TripRecord,
        normalized: dict[str, object],
        created_at: str,
    ) -> None:
        for claim in _list_field(normalized, "claims"):
            evidence = claim.get("evidence")
            value = claim.get("value")
            if not isinstance(evidence, dict) or not isinstance(value, dict):
                raise ValueError("Normalizer returned an invalid Claim.")
            connection.execute(
                """
                INSERT INTO claims (
                    claim_id,
                    trip_id,
                    itinerary_revision_id,
                    claim_kind,
                    statement,
                    value_json,
                    evidence_status,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(claim["claim_id"]),
                    trip.trip_id,
                    trip.itinerary_revision_id,
                    str(claim["claim_kind"]),
                    str(claim["statement"]),
                    json.dumps(value, sort_keys=True),
                    str(claim["evidence_status"]),
                    created_at,
                ),
            )
            WorkspaceRepository._own_stage_record(
                connection,
                workflow_stage_id,
                "claims",
                str(claim["claim_id"]),
            )
            connection.execute(
                """
                INSERT INTO evidence (
                    evidence_id,
                    itinerary_revision_id,
                    evidence_kind,
                    source_locator,
                    summary,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(evidence["evidence_id"]),
                    trip.itinerary_revision_id,
                    str(evidence["kind"]),
                    str(evidence["source_locator"]),
                    str(evidence["summary"]),
                    created_at,
                ),
            )
            WorkspaceRepository._own_stage_record(
                connection,
                workflow_stage_id,
                "evidence",
                str(evidence["evidence_id"]),
            )
            connection.execute(
                """
                INSERT INTO claim_evidence (claim_id, evidence_id)
                VALUES (?, ?)
                """,
                (str(claim["claim_id"]), str(evidence["evidence_id"])),
            )

    @staticmethod
    def _own_stage_record(
        connection: sqlite3.Connection,
        workflow_stage_id: str,
        record_type: str,
        record_id: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO workflow_stage_records (
                workflow_stage_id, record_type, record_id
            ) VALUES (?, ?, ?)
            """,
            (workflow_stage_id, record_type, record_id),
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
    trip = _trip_record_from_row(
        (
            trip_id,
            name,
            slug,
            revision_id,
            revision_number,
            created_at,
            current_package_version,
        )
    )
    return TripCreationStage(trip, str(stage_id), StageStatus(str(status)))


def _itinerary_processing_stage_from_row(
    row: tuple[object, ...]
) -> ItineraryProcessingStage:
    trip = _trip_record_from_row(row[:7])
    return ItineraryProcessingStage(
        trip=trip,
        workflow_stage_id=str(row[7]),
        status=StageStatus(str(row[8])),
        input_hash=str(row[9]),
    )


def _trip_record_from_row(row: tuple[object, ...]) -> TripRecord:
    (
        trip_id,
        name,
        slug,
        revision_id,
        revision_number,
        created_at,
        current_package_version,
    ) = row
    return TripRecord(
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


def _trip_scope_key(input_hash: str) -> str:
    return f"trip-create:{input_hash}"


def _itinerary_scope_key(itinerary_revision_id: str) -> str:
    return f"itinerary:{itinerary_revision_id}"


def _list_field(
    normalized: dict[str, object], field_name: str
) -> list[dict[str, object]]:
    value = normalized.get(field_name, [])
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"Normalizer returned invalid {field_name}.")
    return value


def _stable_database_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:32]}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
