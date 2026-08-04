from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid

from aa_content.errors import UserFacingError
from aa_content.models import (
    AngleResearchStage,
    BaselineResearchStage,
    ContentAngleOption,
    ContentAngleSource,
    ContentAngleStatus,
    DayIntensity,
    EditorialPackageVersion,
    VersionComponent,
    EvidenceStatus,
    EvidenceSupportLevel,
    ItineraryProcessingStage,
    ItinerarySource,
    NarrationSection,
    NarrationStage,
    ResearchCategory,
    ResearchClaim,
    RouteSegment,
    RouteSegmentStatus,
    SanitizationResult,
    SanitizationStatus,
    SourceFetchOutcome,
    SourceFetchRecord,
    SourceRecord,
    StageAttempt,
    StageStatus,
    SupplierDataFinding,
    TripCreationStage,
    TripInspectionResult,
    TripRecord,
    TripUpdateStage,
    ValidationAcknowledgment,
    ValidationFinding,
    VersionApproval,
    WorkingReviewState,
    WorkingReviewStatus,
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
    current_editorial_package_version TEXT,
    current_content_angle_id TEXT
);

CREATE TABLE IF NOT EXISTS itinerary_revisions (
    itinerary_revision_id TEXT PRIMARY KEY,
    trip_id TEXT NOT NULL REFERENCES trips(trip_id),
    revision_number INTEGER NOT NULL CHECK (revision_number > 0),
    source_kind TEXT NOT NULL CHECK (source_kind IN ('PASTED_TEXT', 'URL')),
    source_url TEXT,
    original_text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (trip_id, revision_number)
);

CREATE TABLE IF NOT EXISTS source_fetches (
    source_fetch_id TEXT PRIMARY KEY,
    trip_id TEXT REFERENCES trips(trip_id),
    itinerary_revision_id TEXT
        REFERENCES itinerary_revisions(itinerary_revision_id),
    requested_url TEXT NOT NULL,
    final_url TEXT,
    accessed_at TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('SUCCESS', 'FAILED')),
    http_status INTEGER,
    content_type TEXT,
    response_content_hash TEXT,
    extracted_content_hash TEXT,
    error_code TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS working_review_state (
    trip_id TEXT PRIMARY KEY REFERENCES trips(trip_id),
    status TEXT NOT NULL CHECK (status IN ('CURRENT', 'REVIEW_REQUIRED')),
    based_on_revision_id TEXT NOT NULL
        REFERENCES itinerary_revisions(itinerary_revision_id),
    previous_revision_id TEXT
        REFERENCES itinerary_revisions(itinerary_revision_id),
    reason TEXT,
    updated_at TEXT NOT NULL
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

CREATE TABLE IF NOT EXISTS export_blocks (
    export_block_id TEXT PRIMARY KEY,
    itinerary_revision_id TEXT NOT NULL
        REFERENCES itinerary_revisions(itinerary_revision_id),
    code TEXT NOT NULL CHECK (code = 'UNSANITIZED_SUPPLIER_DATA'),
    message TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'RESOLVED'))
);

CREATE TABLE IF NOT EXISTS source_records (
    source_record_id TEXT PRIMARY KEY,
    trip_id TEXT NOT NULL REFERENCES trips(trip_id),
    itinerary_revision_id TEXT NOT NULL
        REFERENCES itinerary_revisions(itinerary_revision_id),
    category TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    publisher TEXT NOT NULL,
    published_at TEXT,
    retrieved_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    locator TEXT NOT NULL,
    evidence_summary TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS research_claims (
    claim_id TEXT PRIMARY KEY,
    trip_id TEXT NOT NULL REFERENCES trips(trip_id),
    itinerary_revision_id TEXT NOT NULL
        REFERENCES itinerary_revisions(itinerary_revision_id),
    category TEXT NOT NULL,
    statement TEXT NOT NULL,
    evidence_status TEXT NOT NULL CHECK (
        evidence_status IN (
            'VERIFIED', 'CORROBORATED', 'INDICATIVE', 'UNVERIFIED', 'UNKNOWN'
        )
    ),
    recheck_date TEXT,
    stale INTEGER NOT NULL DEFAULT 0,
    angle_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE (itinerary_revision_id, category, angle_id)
);

CREATE TABLE IF NOT EXISTS research_claim_sources (
    claim_id TEXT NOT NULL REFERENCES research_claims(claim_id),
    source_record_id TEXT NOT NULL REFERENCES source_records(source_record_id),
    PRIMARY KEY (claim_id, source_record_id)
);

CREATE TABLE IF NOT EXISTS route_segments (
    route_segment_id TEXT PRIMARY KEY,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    match_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('PROPOSED', 'CONFIRMED')),
    created_at TEXT NOT NULL,
    confirmed_at TEXT
);

CREATE TABLE IF NOT EXISTS route_segment_trips (
    route_segment_id TEXT NOT NULL REFERENCES route_segments(route_segment_id),
    trip_id TEXT NOT NULL REFERENCES trips(trip_id),
    itinerary_revision_id TEXT NOT NULL
        REFERENCES itinerary_revisions(itinerary_revision_id),
    matched_locator TEXT NOT NULL,
    PRIMARY KEY (route_segment_id, trip_id)
);

CREATE TABLE IF NOT EXISTS route_segment_research (
    route_segment_id TEXT NOT NULL REFERENCES route_segments(route_segment_id),
    category TEXT NOT NULL,
    claim_id TEXT NOT NULL REFERENCES research_claims(claim_id),
    PRIMARY KEY (route_segment_id, category)
);

CREATE TABLE IF NOT EXISTS content_angles (
    angle_id TEXT PRIMARY KEY,
    trip_id TEXT NOT NULL REFERENCES trips(trip_id),
    itinerary_revision_id TEXT NOT NULL
        REFERENCES itinerary_revisions(itinerary_revision_id),
    viewer_question TEXT NOT NULL,
    available_evidence TEXT NOT NULL,
    commercial_relevance TEXT NOT NULL,
    risks TEXT NOT NULL,
    missing_information TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('GENERATED', 'CUSTOM')),
    status TEXT NOT NULL CHECK (status IN ('PROPOSED', 'APPROVED')),
    evidence_support TEXT NOT NULL
        CHECK (evidence_support IN ('SUPPORTED', 'WEAK', 'UNSUPPORTED')),
    created_at TEXT NOT NULL,
    approved_at TEXT
);

CREATE TABLE IF NOT EXISTS narrations (
    narration_id TEXT PRIMARY KEY,
    trip_id TEXT NOT NULL REFERENCES trips(trip_id),
    itinerary_revision_id TEXT NOT NULL
        REFERENCES itinerary_revisions(itinerary_revision_id),
    angle_id TEXT NOT NULL REFERENCES content_angles(angle_id),
    sections_json TEXT NOT NULL,
    editorial_notes TEXT,
    word_count INTEGER NOT NULL,
    estimated_minutes REAL NOT NULL,
    overall_intensity INTEGER,
    day_intensities_json TEXT NOT NULL,
    warnings_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (itinerary_revision_id, angle_id)
);

CREATE TABLE IF NOT EXISTS validation_reports (
    draft_signature TEXT PRIMARY KEY,
    trip_id TEXT NOT NULL REFERENCES trips(trip_id),
    itinerary_revision_id TEXT NOT NULL
        REFERENCES itinerary_revisions(itinerary_revision_id),
    angle_id TEXT NOT NULL,
    quality_score INTEGER NOT NULL,
    export_blocked INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS validation_findings (
    draft_signature TEXT NOT NULL REFERENCES validation_reports(draft_signature),
    finding_id TEXT NOT NULL,
    code TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('WARNING', 'BLOCKING')),
    message TEXT NOT NULL,
    locator TEXT NOT NULL,
    PRIMARY KEY (draft_signature, finding_id)
);

CREATE TABLE IF NOT EXISTS validation_acknowledgments (
    draft_signature TEXT NOT NULL,
    finding_id TEXT NOT NULL,
    approver TEXT NOT NULL,
    acknowledged_at TEXT NOT NULL,
    PRIMARY KEY (draft_signature, finding_id)
);

CREATE TABLE IF NOT EXISTS editorial_package_versions (
    trip_id TEXT NOT NULL REFERENCES trips(trip_id),
    version_number INTEGER NOT NULL CHECK (version_number > 0),
    itinerary_revision_id TEXT NOT NULL
        REFERENCES itinerary_revisions(itinerary_revision_id),
    angle_id TEXT NOT NULL REFERENCES content_angles(angle_id),
    narration_signature TEXT NOT NULL,
    youtube_packaging_signature TEXT,
    production_brief_signature TEXT,
    quality_score INTEGER NOT NULL,
    export_blocked INTEGER NOT NULL,
    findings_json TEXT NOT NULL,
    acknowledgments_json TEXT NOT NULL,
    claims_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    PRIMARY KEY (trip_id, version_number)
);

CREATE TABLE IF NOT EXISTS youtube_packaging (
    itinerary_revision_id TEXT NOT NULL
        REFERENCES itinerary_revisions(itinerary_revision_id),
    angle_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    content_signature TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (itinerary_revision_id, angle_id)
);

CREATE TABLE IF NOT EXISTS version_approvals (
    trip_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    component TEXT NOT NULL CHECK (component IN ('NARRATION', 'FINAL')),
    approver TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    content_integrity_reference TEXT NOT NULL,
    PRIMARY KEY (trip_id, version_number, component),
    FOREIGN KEY (trip_id, version_number)
        REFERENCES editorial_package_versions(trip_id, version_number)
);

CREATE TABLE IF NOT EXISTS production_briefs (
    itinerary_revision_id TEXT NOT NULL
        REFERENCES itinerary_revisions(itinerary_revision_id),
    angle_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    content_signature TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (itinerary_revision_id, angle_id)
);

PRAGMA user_version = 11;
"""


class WorkspaceRepository:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.database_path = workspace / "aa_content.db"

    def initialize_database(self) -> bool:
        """Create the schema. Returns True if it was already initialized."""
        with sqlite3.connect(self.database_path) as connection:
            connection.executescript(SCHEMA)

        with self._connect() as connection:
            completed = connection.execute(
                """
                SELECT 1 FROM workflow_stages
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
                    workflow_stage_id, trip_id, scope_key, stage_name,
                    input_hash, status, result_json, completed_at
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
                    stage_attempt_id, workflow_stage_id, attempt_number,
                    status, started_at, completed_at
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
                    trip.trip_id, trip.name, trip.slug,
                    revision.itinerary_revision_id, revision.revision_number,
                    trip.created_at, trip.current_editorial_package_version,
                    stage.workflow_stage_id, stage.status
                FROM workflow_stages AS stage
                JOIN trips AS trip ON trip.trip_id = stage.trip_id
                JOIN itinerary_revisions AS revision
                  ON revision.itinerary_revision_id = stage.itinerary_revision_id
                WHERE stage.scope_key = 'trip'
                  AND stage.stage_name = 'trip_create'
                  AND stage.input_hash = ?
                """,
                (input_hash,),
            ).fetchone()
        return _trip_creation_stage_from_row(row) if row is not None else None

    def load_original_itinerary(self, itinerary_revision_id: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT original_text FROM itinerary_revisions
                WHERE itinerary_revision_id = ?
                """,
                (itinerary_revision_id,),
            ).fetchone()
        if row is None:
            raise RuntimeError(
                f"Itinerary Revision not found: {itinerary_revision_id}"
            )
        return str(row[0])

    def start_trip_creation(
        self,
        name: str,
        slug: str,
        source: ItinerarySource,
        input_hash: str,
        *,
        source_fetch: SourceFetchRecord | None = None,
    ) -> tuple[TripCreationStage, StageAttempt]:
        now = _utc_now()
        trip_id = f"trp_{uuid.uuid4().hex}"
        itinerary_revision_id = f"irv_{uuid.uuid4().hex}"
        workflow_stage_id = f"wfs_{uuid.uuid4().hex}"

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO trips (trip_id, name, slug, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (trip_id, name, slug, now),
            )
            connection.execute(
                """
                INSERT INTO itinerary_revisions (
                    itinerary_revision_id, trip_id, revision_number,
                    source_kind, source_url, original_text, content_hash,
                    created_at
                ) VALUES (?, ?, 1, ?, ?, ?, ?, ?)
                """,
                (
                    itinerary_revision_id,
                    trip_id,
                    source.kind,
                    source.requested_url,
                    source.text,
                    _content_hash(source.text),
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE trips SET current_itinerary_revision_id = ?
                WHERE trip_id = ?
                """,
                (itinerary_revision_id, trip_id),
            )
            connection.execute(
                """
                INSERT INTO working_review_state (
                    trip_id, status, based_on_revision_id, previous_revision_id,
                    reason, updated_at
                ) VALUES (?, 'CURRENT', ?, NULL, NULL, ?)
                """,
                (trip_id, itinerary_revision_id, now),
            )
            if source_fetch is not None:
                self._insert_source_fetch(
                    connection,
                    source_fetch,
                    trip_id=trip_id,
                    itinerary_revision_id=itinerary_revision_id,
                )
            connection.execute(
                """
                INSERT INTO workflow_stages (
                    workflow_stage_id, trip_id, itinerary_revision_id,
                    scope_key, stage_name, input_hash, status, result_json,
                    completed_at
                ) VALUES (?, ?, ?, 'trip', 'trip_create', ?, ?, '{}', NULL)
                """,
                (
                    workflow_stage_id,
                    trip_id,
                    itinerary_revision_id,
                    input_hash,
                    StageStatus.IN_PROGRESS,
                ),
            )
            attempt = StageAttempt(
                workflow_stage_id=workflow_stage_id,
                stage_attempt_id=f"sta_{uuid.uuid4().hex}",
                attempt_number=1,
            )
            self._insert_attempt(connection, attempt, now)

        trip = TripRecord(
            trip_id=trip_id,
            name=name,
            slug=slug,
            itinerary_revision_id=itinerary_revision_id,
            revision_number=1,
            created_at=now,
            current_editorial_package_version=None,
        )
        stage = TripCreationStage(trip, workflow_stage_id, StageStatus.IN_PROGRESS)
        return stage, attempt

    @staticmethod
    def _insert_source_fetch(
        connection: sqlite3.Connection,
        fetch: SourceFetchRecord,
        *,
        trip_id: str | None,
        itinerary_revision_id: str | None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO source_fetches (
                source_fetch_id, trip_id, itinerary_revision_id, requested_url,
                final_url, accessed_at, outcome, http_status, content_type,
                response_content_hash, extracted_content_hash, error_code,
                error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fetch.source_fetch_id,
                trip_id,
                itinerary_revision_id,
                fetch.requested_url,
                fetch.final_url,
                fetch.accessed_at,
                fetch.outcome,
                fetch.http_status,
                fetch.content_type,
                fetch.response_content_hash,
                fetch.extracted_content_hash,
                fetch.error_code,
                fetch.error_message,
            ),
        )

    def record_source_fetch(
        self,
        fetch: SourceFetchRecord,
        *,
        trip_id: str | None = None,
        itinerary_revision_id: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._insert_source_fetch(
                connection,
                fetch,
                trip_id=trip_id,
                itinerary_revision_id=itinerary_revision_id,
            )

    def find_pending_trip_update(self, trip_id: str) -> TripUpdateStage | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    trip.trip_id, trip.name, trip.slug,
                    revision.itinerary_revision_id, revision.revision_number,
                    trip.created_at, trip.current_editorial_package_version,
                    stage.workflow_stage_id, stage.status, stage.input_hash,
                    stage.result_json
                FROM workflow_stages AS stage
                JOIN trips AS trip ON trip.trip_id = stage.trip_id
                JOIN itinerary_revisions AS revision
                  ON revision.itinerary_revision_id = stage.itinerary_revision_id
                WHERE stage.trip_id = ?
                  AND stage.stage_name = 'trip_update'
                  AND stage.status IN ('FAILED', 'IN_PROGRESS')
                ORDER BY stage.rowid DESC
                LIMIT 1
                """,
                (trip_id,),
            ).fetchone()
        return _trip_update_stage_from_row(row) if row is not None else None

    def find_completed_trip_update(
        self, trip_id: str, previous_revision_id: str, input_hash: str
    ) -> TripUpdateStage | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    trip.trip_id, trip.name, trip.slug,
                    revision.itinerary_revision_id, revision.revision_number,
                    trip.created_at, trip.current_editorial_package_version,
                    stage.workflow_stage_id, stage.status, stage.input_hash,
                    stage.result_json
                FROM workflow_stages AS stage
                JOIN trips AS trip ON trip.trip_id = stage.trip_id
                JOIN itinerary_revisions AS revision
                  ON revision.itinerary_revision_id = stage.itinerary_revision_id
                WHERE stage.scope_key = ?
                  AND stage.stage_name = 'trip_update'
                  AND stage.input_hash = ?
                  AND stage.status = 'COMPLETED'
                """,
                (_trip_update_scope_key(trip_id, previous_revision_id), input_hash),
            ).fetchone()
        return _trip_update_stage_from_row(row) if row is not None else None

    def start_trip_update(
        self,
        current: TripRecord,
        source: ItinerarySource,
        input_hash: str,
        *,
        source_fetch: SourceFetchRecord | None = None,
    ) -> tuple[TripUpdateStage, StageAttempt]:
        now = _utc_now()
        revision_number = current.revision_number + 1
        revision_id = f"irv_{uuid.uuid4().hex}"
        workflow_stage_id = f"wfs_{uuid.uuid4().hex}"
        previous_revision_id = current.itinerary_revision_id

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO itinerary_revisions (
                    itinerary_revision_id, trip_id, revision_number,
                    source_kind, source_url, original_text, content_hash,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    revision_id,
                    current.trip_id,
                    revision_number,
                    source.kind,
                    source.requested_url,
                    source.text,
                    _content_hash(source.text),
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE trips SET current_itinerary_revision_id = ?
                WHERE trip_id = ?
                """,
                (revision_id, current.trip_id),
            )
            connection.execute(
                """
                UPDATE working_review_state
                SET status = 'REVIEW_REQUIRED', based_on_revision_id = ?,
                    previous_revision_id = ?, reason = 'ITINERARY_REVISION_CHANGED',
                    updated_at = ?
                WHERE trip_id = ?
                """,
                (revision_id, previous_revision_id, now, current.trip_id),
            )
            if source_fetch is not None:
                self._insert_source_fetch(
                    connection,
                    source_fetch,
                    trip_id=current.trip_id,
                    itinerary_revision_id=revision_id,
                )
            connection.execute(
                """
                INSERT INTO workflow_stages (
                    workflow_stage_id, trip_id, itinerary_revision_id,
                    scope_key, stage_name, input_hash, status, result_json,
                    completed_at
                ) VALUES (?, ?, ?, ?, 'trip_update', ?, ?, ?, NULL)
                """,
                (
                    workflow_stage_id,
                    current.trip_id,
                    revision_id,
                    _trip_update_scope_key(current.trip_id, previous_revision_id),
                    input_hash,
                    StageStatus.IN_PROGRESS,
                    json.dumps(
                        {"previous_revision_id": previous_revision_id},
                        sort_keys=True,
                    ),
                ),
            )
            attempt = StageAttempt(
                workflow_stage_id=workflow_stage_id,
                stage_attempt_id=f"sta_{uuid.uuid4().hex}",
                attempt_number=1,
            )
            self._insert_attempt(connection, attempt, now)

        updated_trip = TripRecord(
            trip_id=current.trip_id,
            name=current.name,
            slug=current.slug,
            itinerary_revision_id=revision_id,
            revision_number=revision_number,
            created_at=current.created_at,
            current_editorial_package_version=(
                current.current_editorial_package_version
            ),
        )
        stage = TripUpdateStage(
            trip=updated_trip,
            previous_revision_id=previous_revision_id,
            workflow_stage_id=workflow_stage_id,
            status=StageStatus.IN_PROGRESS,
            input_hash=input_hash,
        )
        return stage, attempt

    def complete_trip_update(
        self, stage: TripUpdateStage, attempt: StageAttempt
    ) -> None:
        now = _utc_now()
        result_json = json.dumps(
            {
                "trip_id": stage.trip.trip_id,
                "itinerary_revision_id": stage.trip.itinerary_revision_id,
                "revision_number": stage.trip.revision_number,
                "previous_revision_id": stage.previous_revision_id,
            },
            sort_keys=True,
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            attempt_update = connection.execute(
                """
                UPDATE stage_attempts
                SET status = ?, completed_at = ?, error_code = NULL
                WHERE stage_attempt_id = ? AND workflow_stage_id = ? AND status = ?
                """,
                (
                    StageStatus.COMPLETED,
                    now,
                    attempt.stage_attempt_id,
                    stage.workflow_stage_id,
                    StageStatus.IN_PROGRESS,
                ),
            )
            if attempt_update.rowcount != 1:
                raise RuntimeError("Trip update attempt is stale.")
            stage_update = connection.execute(
                """
                UPDATE workflow_stages
                SET status = ?, result_json = ?, completed_at = ?
                WHERE workflow_stage_id = ? AND status = ?
                """,
                (
                    StageStatus.COMPLETED,
                    result_json,
                    now,
                    stage.workflow_stage_id,
                    StageStatus.IN_PROGRESS,
                ),
            )
            if stage_update.rowcount != 1:
                raise RuntimeError("Trip update stage is no longer live.")

    def load_working_review_state(self, trip_id: str) -> WorkingReviewState | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT state.status, based.revision_number,
                       previous.revision_number, state.reason
                FROM working_review_state AS state
                JOIN itinerary_revisions AS based
                  ON based.itinerary_revision_id = state.based_on_revision_id
                LEFT JOIN itinerary_revisions AS previous
                  ON previous.itinerary_revision_id = state.previous_revision_id
                WHERE state.trip_id = ?
                """,
                (trip_id,),
            ).fetchone()
        if row is None:
            return None
        return WorkingReviewState(
            status=WorkingReviewStatus(str(row[0])),
            based_on_revision_number=int(row[1]),
            previous_revision_number=int(row[2]) if row[2] is not None else None,
            reason=str(row[3]) if row[3] is not None else None,
        )

    def start_retry(
        self,
        stage: (
            TripCreationStage
            | ItineraryProcessingStage
            | TripUpdateStage
            | BaselineResearchStage
            | AngleResearchStage
            | NarrationStage
        ),
    ) -> StageAttempt:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            stage_row = connection.execute(
                "SELECT status FROM workflow_stages WHERE workflow_stage_id = ?",
                (stage.workflow_stage_id,),
            ).fetchone()
            if stage_row is None or str(stage_row[0]) not in {
                str(StageStatus.FAILED),
                str(StageStatus.IN_PROGRESS),
                str(StageStatus.COMPLETED),
            }:
                raise RuntimeError("Workflow stage cannot be retried.")

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
                FROM stage_attempts WHERE workflow_stage_id = ?
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
                UPDATE workflow_stages SET status = ?, completed_at = NULL
                WHERE workflow_stage_id = ?
                """,
                (StageStatus.IN_PROGRESS, stage.workflow_stage_id),
            )
            self._insert_attempt(connection, attempt, now)
        return attempt

    def fail_attempt(
        self,
        stage: (
            TripCreationStage
            | ItineraryProcessingStage
            | TripUpdateStage
            | BaselineResearchStage
            | AngleResearchStage
            | NarrationStage
        ),
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
                WHERE stage_attempt_id = ? AND workflow_stage_id = ?
                """,
                (
                    StageStatus.FAILED,
                    now,
                    error_code,
                    attempt.stage_attempt_id,
                    stage.workflow_stage_id,
                ),
            )
            connection.execute(
                """
                UPDATE workflow_stages SET status = ?
                WHERE workflow_stage_id = ?
                """,
                (StageStatus.FAILED, stage.workflow_stage_id),
            )

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
            attempt_update = connection.execute(
                """
                UPDATE stage_attempts
                SET status = ?, completed_at = ?, error_code = NULL
                WHERE stage_attempt_id = ? AND workflow_stage_id = ? AND status = ?
                """,
                (
                    StageStatus.COMPLETED,
                    now,
                    attempt.stage_attempt_id,
                    stage.workflow_stage_id,
                    StageStatus.IN_PROGRESS,
                ),
            )
            if attempt_update.rowcount != 1:
                raise RuntimeError("Trip creation attempt is stale.")
            stage_update = connection.execute(
                """
                UPDATE workflow_stages
                SET status = ?, result_json = ?, completed_at = ?
                WHERE workflow_stage_id = ? AND status = ?
                """,
                (
                    StageStatus.COMPLETED,
                    result_json,
                    now,
                    stage.workflow_stage_id,
                    StageStatus.IN_PROGRESS,
                ),
            )
            if stage_update.rowcount != 1:
                raise RuntimeError("Trip creation stage is no longer live.")

    def load_current_trip(self, trip_id: str) -> TripRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    trip.trip_id, trip.name, trip.slug,
                    revision.itinerary_revision_id, revision.revision_number,
                    trip.created_at, trip.current_editorial_package_version
                FROM trips AS trip
                JOIN itinerary_revisions AS revision
                  ON revision.itinerary_revision_id =
                     trip.current_itinerary_revision_id
                WHERE trip.trip_id = ?
                """,
                (trip_id,),
            ).fetchone()
        if row is None:
            return None
        return TripRecord(
            trip_id=str(row[0]),
            name=str(row[1]),
            slug=str(row[2]),
            itinerary_revision_id=str(row[3]),
            revision_number=int(row[4]),
            created_at=str(row[5]),
            current_editorial_package_version=(
                str(row[6]) if row[6] is not None else None
            ),
        )

    def find_itinerary_processing(
        self, itinerary_revision_id: str, input_hash: str
    ) -> ItineraryProcessingStage | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    trip.trip_id, trip.name, trip.slug,
                    revision.itinerary_revision_id, revision.revision_number,
                    trip.created_at, trip.current_editorial_package_version,
                    stage.workflow_stage_id, stage.status, stage.input_hash
                FROM workflow_stages AS stage
                JOIN trips AS trip ON trip.trip_id = stage.trip_id
                JOIN itinerary_revisions AS revision
                  ON revision.itinerary_revision_id = stage.itinerary_revision_id
                WHERE stage.scope_key = ?
                  AND stage.stage_name = 'itinerary_process'
                  AND stage.input_hash = ?
                """,
                (itinerary_revision_id, input_hash),
            ).fetchone()
        return _itinerary_processing_stage_from_row(row) if row is not None else None

    def start_itinerary_processing(
        self, trip: TripRecord, input_hash: str
    ) -> tuple[ItineraryProcessingStage, StageAttempt]:
        now = _utc_now()
        workflow_stage_id = f"wfs_{uuid.uuid4().hex}"
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO workflow_stages (
                    workflow_stage_id, trip_id, itinerary_revision_id,
                    scope_key, stage_name, input_hash, status, result_json,
                    completed_at
                ) VALUES (?, ?, ?, ?, 'itinerary_process', ?, ?, '{}', NULL)
                """,
                (
                    workflow_stage_id,
                    trip.trip_id,
                    trip.itinerary_revision_id,
                    trip.itinerary_revision_id,
                    input_hash,
                    StageStatus.IN_PROGRESS,
                ),
            )
            attempt = StageAttempt(
                workflow_stage_id=workflow_stage_id,
                stage_attempt_id=f"sta_{uuid.uuid4().hex}",
                attempt_number=1,
            )
            self._insert_attempt(connection, attempt, now)
        stage = ItineraryProcessingStage(
            trip=trip,
            workflow_stage_id=workflow_stage_id,
            status=StageStatus.IN_PROGRESS,
            input_hash=input_hash,
        )
        return stage, attempt

    def persist_itinerary_processing(
        self,
        itinerary_revision_id: str,
        sanitization: SanitizationResult,
        normalized: dict[str, object],
    ) -> None:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM sanitized_itineraries WHERE itinerary_revision_id = ?",
                (itinerary_revision_id,),
            )
            connection.execute(
                "DELETE FROM supplier_data_findings WHERE itinerary_revision_id = ?",
                (itinerary_revision_id,),
            )
            connection.execute(
                "DELETE FROM normalized_itineraries WHERE itinerary_revision_id = ?",
                (itinerary_revision_id,),
            )
            connection.execute(
                "DELETE FROM export_blocks WHERE itinerary_revision_id = ?",
                (itinerary_revision_id,),
            )
            connection.execute(
                """
                INSERT INTO sanitized_itineraries (
                    itinerary_revision_id, sanitized_text, content_hash,
                    status, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    itinerary_revision_id,
                    sanitization.sanitized_text,
                    _content_hash(sanitization.sanitized_text),
                    sanitization.status,
                    now,
                ),
            )
            for finding in sanitization.findings:
                connection.execute(
                    """
                    INSERT INTO supplier_data_findings (
                        finding_id, itinerary_revision_id, category,
                        source_line, matched_text_hash, review_status
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        finding.finding_id,
                        itinerary_revision_id,
                        finding.category,
                        finding.source_line,
                        finding.matched_text_hash,
                        finding.review_status,
                    ),
                )
            connection.execute(
                """
                INSERT INTO normalized_itineraries (
                    itinerary_revision_id, normalized_json, created_at
                ) VALUES (?, ?, ?)
                """,
                (
                    itinerary_revision_id,
                    json.dumps(normalized, sort_keys=True),
                    now,
                ),
            )
            if sanitization.status is SanitizationStatus.REVIEW_REQUIRED:
                connection.execute(
                    """
                    INSERT INTO export_blocks (
                        export_block_id, itinerary_revision_id, code,
                        message, status
                    ) VALUES (?, ?, 'UNSANITIZED_SUPPLIER_DATA', ?, 'ACTIVE')
                    """,
                    (
                        f"xbk_{uuid.uuid4().hex}",
                        itinerary_revision_id,
                        "Possible Supplier Data removals require human "
                        "review before export.",
                    ),
                )

    def complete_itinerary_processing(
        self, stage: ItineraryProcessingStage, attempt: StageAttempt
    ) -> None:
        now = _utc_now()
        result_json = json.dumps(
            {
                "trip_id": stage.trip.trip_id,
                "itinerary_revision_id": stage.trip.itinerary_revision_id,
            },
            sort_keys=True,
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            attempt_update = connection.execute(
                """
                UPDATE stage_attempts
                SET status = ?, completed_at = ?, error_code = NULL
                WHERE stage_attempt_id = ? AND workflow_stage_id = ? AND status = ?
                """,
                (
                    StageStatus.COMPLETED,
                    now,
                    attempt.stage_attempt_id,
                    stage.workflow_stage_id,
                    StageStatus.IN_PROGRESS,
                ),
            )
            if attempt_update.rowcount != 1:
                raise RuntimeError("Itinerary processing attempt is stale.")
            stage_update = connection.execute(
                """
                UPDATE workflow_stages
                SET status = ?, result_json = ?, completed_at = ?
                WHERE workflow_stage_id = ? AND status = ?
                """,
                (
                    StageStatus.COMPLETED,
                    result_json,
                    now,
                    stage.workflow_stage_id,
                    StageStatus.IN_PROGRESS,
                ),
            )
            if stage_update.rowcount != 1:
                raise RuntimeError("Itinerary processing stage is no longer live.")

    def load_normalized_itinerary(
        self, itinerary_revision_id: str
    ) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT normalized_json FROM normalized_itineraries
                WHERE itinerary_revision_id = ?
                """,
                (itinerary_revision_id,),
            ).fetchone()
        return json.loads(str(row[0])) if row is not None else None

    def load_itinerary_processing_summary(
        self, itinerary_revision_id: str
    ) -> tuple[SanitizationStatus, int, int, int, bool]:
        with self._connect() as connection:
            sanitization_row = connection.execute(
                """
                SELECT status FROM sanitized_itineraries
                WHERE itinerary_revision_id = ?
                """,
                (itinerary_revision_id,),
            ).fetchone()
            finding_count = connection.execute(
                """
                SELECT COUNT(*) FROM supplier_data_findings
                WHERE itinerary_revision_id = ?
                """,
                (itinerary_revision_id,),
            ).fetchone()[0]
            normalized_row = connection.execute(
                """
                SELECT normalized_json FROM normalized_itineraries
                WHERE itinerary_revision_id = ?
                """,
                (itinerary_revision_id,),
            ).fetchone()
            export_blocked = (
                connection.execute(
                    """
                    SELECT 1 FROM export_blocks
                    WHERE itinerary_revision_id = ? AND status = 'ACTIVE'
                    """,
                    (itinerary_revision_id,),
                ).fetchone()
                is not None
            )
        if sanitization_row is None or normalized_row is None:
            raise RuntimeError(
                f"Itinerary processing summary not found: {itinerary_revision_id}"
            )
        normalized = json.loads(str(normalized_row[0]))
        return (
            SanitizationStatus(str(sanitization_row[0])),
            int(finding_count),
            len(normalized.get("missing_information", [])),
            len(normalized.get("fact_conflicts", [])),
            export_blocked,
        )

    def find_baseline_research(
        self, itinerary_revision_id: str, input_hash: str
    ) -> BaselineResearchStage | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    trip.trip_id, trip.name, trip.slug,
                    revision.itinerary_revision_id, revision.revision_number,
                    trip.created_at, trip.current_editorial_package_version,
                    stage.workflow_stage_id, stage.status, stage.input_hash,
                    stage.result_json
                FROM workflow_stages AS stage
                JOIN trips AS trip ON trip.trip_id = stage.trip_id
                JOIN itinerary_revisions AS revision
                  ON revision.itinerary_revision_id = stage.itinerary_revision_id
                WHERE stage.scope_key = ?
                  AND stage.stage_name = 'baseline_research'
                  AND stage.input_hash = ?
                """,
                (itinerary_revision_id, input_hash),
            ).fetchone()
        return _baseline_research_stage_from_row(row) if row is not None else None

    def start_baseline_research(
        self, trip: TripRecord, input_hash: str
    ) -> tuple[BaselineResearchStage, StageAttempt]:
        now = _utc_now()
        workflow_stage_id = f"wfs_{uuid.uuid4().hex}"
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO workflow_stages (
                    workflow_stage_id, trip_id, itinerary_revision_id,
                    scope_key, stage_name, input_hash, status, result_json,
                    completed_at
                ) VALUES (?, ?, ?, ?, 'baseline_research', ?, ?, ?, NULL)
                """,
                (
                    workflow_stage_id,
                    trip.trip_id,
                    trip.itinerary_revision_id,
                    trip.itinerary_revision_id,
                    input_hash,
                    StageStatus.IN_PROGRESS,
                    json.dumps({"completed_categories": []}),
                ),
            )
            attempt = StageAttempt(
                workflow_stage_id=workflow_stage_id,
                stage_attempt_id=f"sta_{uuid.uuid4().hex}",
                attempt_number=1,
            )
            self._insert_attempt(connection, attempt, now)
        stage = BaselineResearchStage(
            trip=trip,
            workflow_stage_id=workflow_stage_id,
            status=StageStatus.IN_PROGRESS,
            input_hash=input_hash,
            completed_categories=(),
        )
        return stage, attempt

    def checkpoint_research_category(
        self, workflow_stage_id: str, category: ResearchCategory
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT result_json FROM workflow_stages WHERE workflow_stage_id = ?",
                (workflow_stage_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError("Baseline research stage not found.")
            progress = json.loads(str(row[0]))
            completed = set(progress.get("completed_categories", []))
            completed.add(str(category))
            progress["completed_categories"] = sorted(completed)
            connection.execute(
                "UPDATE workflow_stages SET result_json = ? WHERE workflow_stage_id = ?",
                (json.dumps(progress), workflow_stage_id),
            )

    def persist_research_category(
        self,
        trip_id: str,
        itinerary_revision_id: str,
        category: ResearchCategory,
        sources: list[SourceRecord],
        claim: ResearchClaim,
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing_claim = connection.execute(
                """
                SELECT claim_id FROM research_claims
                WHERE itinerary_revision_id = ? AND category = ?
                """,
                (itinerary_revision_id, category),
            ).fetchone()
            if existing_claim is not None:
                connection.execute(
                    "DELETE FROM research_claim_sources WHERE claim_id = ?",
                    (existing_claim[0],),
                )
                connection.execute(
                    "DELETE FROM research_claims WHERE claim_id = ?",
                    (existing_claim[0],),
                )
            connection.execute(
                """
                DELETE FROM source_records
                WHERE itinerary_revision_id = ? AND category = ?
                """,
                (itinerary_revision_id, category),
            )
            for source in sources:
                connection.execute(
                    """
                    INSERT INTO source_records (
                        source_record_id, trip_id, itinerary_revision_id,
                        category, url, title, publisher, published_at,
                        retrieved_at, content_hash, locator, evidence_summary
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source.source_record_id,
                        trip_id,
                        itinerary_revision_id,
                        source.category,
                        source.url,
                        source.title,
                        source.publisher,
                        source.published_at,
                        source.retrieved_at,
                        source.content_hash,
                        source.locator,
                        source.evidence_summary,
                    ),
                )
            connection.execute(
                """
                INSERT INTO research_claims (
                    claim_id, trip_id, itinerary_revision_id, category,
                    statement, evidence_status, recheck_date, stale, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim.claim_id,
                    trip_id,
                    itinerary_revision_id,
                    claim.category,
                    claim.statement,
                    claim.evidence_status,
                    claim.recheck_date,
                    int(claim.stale),
                    _utc_now(),
                ),
            )
            for source in sources:
                connection.execute(
                    """
                    INSERT INTO research_claim_sources (claim_id, source_record_id)
                    VALUES (?, ?)
                    """,
                    (claim.claim_id, source.source_record_id),
                )

    def persist_reused_research_category(
        self,
        trip_id: str,
        itinerary_revision_id: str,
        category: ResearchCategory,
        claim: ResearchClaim,
        source_record_ids: list[str],
    ) -> None:
        """Link a Trip's Claim to already-fetched Evidence without copying it."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing_claim = connection.execute(
                """
                SELECT claim_id FROM research_claims
                WHERE itinerary_revision_id = ? AND category = ?
                """,
                (itinerary_revision_id, category),
            ).fetchone()
            if existing_claim is not None:
                connection.execute(
                    "DELETE FROM research_claim_sources WHERE claim_id = ?",
                    (existing_claim[0],),
                )
                connection.execute(
                    "DELETE FROM research_claims WHERE claim_id = ?",
                    (existing_claim[0],),
                )
            connection.execute(
                """
                INSERT INTO research_claims (
                    claim_id, trip_id, itinerary_revision_id, category,
                    statement, evidence_status, recheck_date, stale, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim.claim_id,
                    trip_id,
                    itinerary_revision_id,
                    claim.category,
                    claim.statement,
                    claim.evidence_status,
                    claim.recheck_date,
                    int(claim.stale),
                    _utc_now(),
                ),
            )
            for source_record_id in source_record_ids:
                connection.execute(
                    """
                    INSERT INTO research_claim_sources (claim_id, source_record_id)
                    VALUES (?, ?)
                    """,
                    (claim.claim_id, source_record_id),
                )

    def complete_baseline_research(
        self, stage: BaselineResearchStage, attempt: StageAttempt
    ) -> None:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            attempt_update = connection.execute(
                """
                UPDATE stage_attempts
                SET status = ?, completed_at = ?, error_code = NULL
                WHERE stage_attempt_id = ? AND workflow_stage_id = ? AND status = ?
                """,
                (
                    StageStatus.COMPLETED,
                    now,
                    attempt.stage_attempt_id,
                    stage.workflow_stage_id,
                    StageStatus.IN_PROGRESS,
                ),
            )
            if attempt_update.rowcount != 1:
                raise RuntimeError("Baseline research attempt is stale.")
            stage_update = connection.execute(
                """
                UPDATE workflow_stages
                SET status = ?, completed_at = ?
                WHERE workflow_stage_id = ? AND status = ?
                """,
                (
                    StageStatus.COMPLETED,
                    now,
                    stage.workflow_stage_id,
                    StageStatus.IN_PROGRESS,
                ),
            )
            if stage_update.rowcount != 1:
                raise RuntimeError("Baseline research stage is no longer live.")

    def load_research_claims(
        self, itinerary_revision_id: str
    ) -> tuple[ResearchClaim, ...]:
        with self._connect() as connection:
            claim_rows = connection.execute(
                """
                SELECT claim_id, category, statement, evidence_status,
                       recheck_date, stale
                FROM research_claims
                WHERE itinerary_revision_id = ?
                ORDER BY category
                """,
                (itinerary_revision_id,),
            ).fetchall()
            claims: list[ResearchClaim] = []
            for (
                claim_id,
                category,
                statement,
                evidence_status,
                recheck_date,
                stale,
            ) in claim_rows:
                source_rows = connection.execute(
                    """
                    SELECT source.source_record_id, source.category, source.url,
                           source.title, source.publisher, source.retrieved_at,
                           source.content_hash, source.locator,
                           source.evidence_summary, source.published_at
                    FROM research_claim_sources AS link
                    JOIN source_records AS source
                      ON source.source_record_id = link.source_record_id
                    WHERE link.claim_id = ?
                    ORDER BY source.source_record_id
                    """,
                    (claim_id,),
                ).fetchall()
                sources = tuple(
                    SourceRecord(
                        source_record_id=str(row[0]),
                        category=ResearchCategory(str(row[1])),
                        url=str(row[2]),
                        title=str(row[3]),
                        publisher=str(row[4]),
                        retrieved_at=str(row[5]),
                        content_hash=str(row[6]),
                        locator=str(row[7]),
                        evidence_summary=str(row[8]),
                        published_at=str(row[9]) if row[9] is not None else None,
                    )
                    for row in source_rows
                )
                claims.append(
                    ResearchClaim(
                        claim_id=str(claim_id),
                        category=ResearchCategory(str(category)),
                        statement=str(statement),
                        evidence_status=EvidenceStatus(str(evidence_status)),
                        recheck_date=(
                            str(recheck_date) if recheck_date is not None else None
                        ),
                        sources=sources,
                        stale=bool(stale),
                    )
                )
        return tuple(claims)

    def load_research_claim_by_id(self, claim_id: str) -> ResearchClaim | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT itinerary_revision_id, category, statement,
                       evidence_status, recheck_date, stale
                FROM research_claims
                WHERE claim_id = ?
                """,
                (claim_id,),
            ).fetchone()
            if row is None:
                return None
            source_rows = connection.execute(
                """
                SELECT source.source_record_id, source.category, source.url,
                       source.title, source.publisher, source.retrieved_at,
                       source.content_hash, source.locator,
                       source.evidence_summary, source.published_at
                FROM research_claim_sources AS link
                JOIN source_records AS source
                  ON source.source_record_id = link.source_record_id
                WHERE link.claim_id = ?
                ORDER BY source.source_record_id
                """,
                (claim_id,),
            ).fetchall()
        sources = tuple(
            SourceRecord(
                source_record_id=str(source_row[0]),
                category=ResearchCategory(str(source_row[1])),
                url=str(source_row[2]),
                title=str(source_row[3]),
                publisher=str(source_row[4]),
                retrieved_at=str(source_row[5]),
                content_hash=str(source_row[6]),
                locator=str(source_row[7]),
                evidence_summary=str(source_row[8]),
                published_at=str(source_row[9]) if source_row[9] is not None else None,
            )
            for source_row in source_rows
        )
        return ResearchClaim(
            claim_id=claim_id,
            category=ResearchCategory(str(row[1])),
            statement=str(row[2]),
            evidence_status=EvidenceStatus(str(row[3])),
            recheck_date=str(row[4]) if row[4] is not None else None,
            sources=sources,
            stale=bool(row[5]),
        )

    def find_confirmed_route_segment(
        self, origin: str, destination: str
    ) -> RouteSegment | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT route_segment_id, origin, destination, status,
                       created_at, confirmed_at
                FROM route_segments
                WHERE match_key = ? AND status = 'CONFIRMED'
                """,
                (_route_segment_match_key(origin, destination),),
            ).fetchone()
        return _route_segment_from_row(row) if row is not None else None

    def load_route_segment(self, route_segment_id: str) -> RouteSegment | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT route_segment_id, origin, destination, status,
                       created_at, confirmed_at
                FROM route_segments
                WHERE route_segment_id = ?
                """,
                (route_segment_id,),
            ).fetchone()
        return _route_segment_from_row(row) if row is not None else None

    def propose_route_segment(
        self,
        origin: str,
        destination: str,
        trips: list[tuple[str, str, str]],
    ) -> RouteSegment:
        """AI-proposed shared segment; `trips` is (trip_id, revision_id, locator)."""
        match_key = _route_segment_match_key(origin, destination)
        now = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT route_segment_id, origin, destination, status,
                       created_at, confirmed_at
                FROM route_segments WHERE match_key = ?
                """,
                (match_key,),
            ).fetchone()
            if existing is not None:
                route_segment_id = str(existing[0])
            else:
                route_segment_id = f"rsg_{uuid.uuid4().hex}"
                connection.execute(
                    """
                    INSERT INTO route_segments (
                        route_segment_id, origin, destination, match_key,
                        status, created_at, confirmed_at
                    ) VALUES (?, ?, ?, ?, 'PROPOSED', ?, NULL)
                    """,
                    (route_segment_id, origin, destination, match_key, now),
                )
            for trip_id, revision_id, locator in trips:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO route_segment_trips (
                        route_segment_id, trip_id, itinerary_revision_id,
                        matched_locator
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (route_segment_id, trip_id, revision_id, locator),
                )
            row = connection.execute(
                """
                SELECT route_segment_id, origin, destination, status,
                       created_at, confirmed_at
                FROM route_segments WHERE route_segment_id = ?
                """,
                (route_segment_id,),
            ).fetchone()
        return _route_segment_from_row(row)

    def link_trip_to_route_segment(
        self,
        route_segment_id: str,
        trip_id: str,
        itinerary_revision_id: str,
        matched_locator: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT OR IGNORE INTO route_segment_trips (
                    route_segment_id, trip_id, itinerary_revision_id,
                    matched_locator
                ) VALUES (?, ?, ?, ?)
                """,
                (route_segment_id, trip_id, itinerary_revision_id, matched_locator),
            )

    def confirm_route_segment(self, route_segment_id: str) -> RouteSegment:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            updated = connection.execute(
                """
                UPDATE route_segments SET status = 'CONFIRMED', confirmed_at = ?
                WHERE route_segment_id = ? AND status = 'PROPOSED'
                """,
                (now, route_segment_id),
            )
            if updated.rowcount != 1:
                existing = connection.execute(
                    "SELECT status FROM route_segments WHERE route_segment_id = ?",
                    (route_segment_id,),
                ).fetchone()
                if existing is None:
                    raise UserFacingError(
                        f"Route Segment not found: {route_segment_id}"
                    )
                raise UserFacingError(
                    f"Route Segment is already {existing[0]}: {route_segment_id}"
                )
            row = connection.execute(
                """
                SELECT route_segment_id, origin, destination, status,
                       created_at, confirmed_at
                FROM route_segments WHERE route_segment_id = ?
                """,
                (route_segment_id,),
            ).fetchone()
        return _route_segment_from_row(row)

    def list_route_segments_for_trip(self, trip_id: str) -> tuple[RouteSegment, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT segment.route_segment_id, segment.origin,
                       segment.destination, segment.status, segment.created_at,
                       segment.confirmed_at
                FROM route_segment_trips AS link
                JOIN route_segments AS segment
                  ON segment.route_segment_id = link.route_segment_id
                WHERE link.trip_id = ?
                ORDER BY segment.created_at
                """,
                (trip_id,),
            ).fetchall()
        return tuple(_route_segment_from_row(row) for row in rows)

    def load_canonical_research(
        self, route_segment_id: str, category: ResearchCategory
    ) -> ResearchClaim | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT claim_id FROM route_segment_research
                WHERE route_segment_id = ? AND category = ?
                """,
                (route_segment_id, category),
            ).fetchone()
        if row is None:
            return None
        return self.load_research_claim_by_id(str(row[0]))

    def register_canonical_research(
        self, route_segment_id: str, category: ResearchCategory, claim_id: str
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO route_segment_research (
                    route_segment_id, category, claim_id
                ) VALUES (?, ?, ?)
                ON CONFLICT (route_segment_id, category)
                DO UPDATE SET claim_id = excluded.claim_id
                """,
                (route_segment_id, category, claim_id),
            )
        return None

    def replace_proposed_angles(
        self,
        trip_id: str,
        itinerary_revision_id: str,
        options: list[ContentAngleOption],
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                DELETE FROM content_angles
                WHERE itinerary_revision_id = ? AND status = 'PROPOSED'
                """,
                (itinerary_revision_id,),
            )
            for option in options:
                self._insert_content_angle(
                    connection, trip_id, itinerary_revision_id, option
                )

    def insert_custom_angle(
        self,
        trip_id: str,
        itinerary_revision_id: str,
        option: ContentAngleOption,
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._insert_content_angle(
                connection, trip_id, itinerary_revision_id, option
            )
            connection.execute(
                "UPDATE trips SET current_content_angle_id = ? WHERE trip_id = ?",
                (option.angle_id, trip_id),
            )

    @staticmethod
    def _insert_content_angle(
        connection: sqlite3.Connection,
        trip_id: str,
        itinerary_revision_id: str,
        option: ContentAngleOption,
    ) -> None:
        now = _utc_now()
        connection.execute(
            """
            INSERT INTO content_angles (
                angle_id, trip_id, itinerary_revision_id, viewer_question,
                available_evidence, commercial_relevance, risks,
                missing_information, source, status, evidence_support,
                created_at, approved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                option.angle_id,
                trip_id,
                itinerary_revision_id,
                option.viewer_question,
                json.dumps(list(option.available_evidence)),
                option.commercial_relevance,
                option.risks,
                json.dumps(list(option.missing_information)),
                option.source,
                option.status,
                option.evidence_support,
                now,
                now if option.status is ContentAngleStatus.APPROVED else None,
            ),
        )

    def load_content_angle(self, angle_id: str) -> ContentAngleOption | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT angle_id, viewer_question, available_evidence,
                       commercial_relevance, risks, missing_information,
                       source, status, evidence_support
                FROM content_angles WHERE angle_id = ?
                """,
                (angle_id,),
            ).fetchone()
        return _content_angle_from_row(row) if row is not None else None

    def load_content_angle_revision(self, angle_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT itinerary_revision_id FROM content_angles WHERE angle_id = ?",
                (angle_id,),
            ).fetchone()
        return str(row[0]) if row is not None else None

    def approve_content_angle(self, trip_id: str, angle_id: str) -> ContentAngleOption:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            updated = connection.execute(
                """
                UPDATE content_angles SET status = 'APPROVED', approved_at = ?
                WHERE angle_id = ? AND trip_id = ? AND status = 'PROPOSED'
                """,
                (now, angle_id, trip_id),
            )
            if updated.rowcount != 1:
                raise UserFacingError(
                    f"Content Angle cannot be approved: {angle_id}"
                )
            connection.execute(
                "UPDATE trips SET current_content_angle_id = ? WHERE trip_id = ?",
                (angle_id, trip_id),
            )
            row = connection.execute(
                """
                SELECT angle_id, viewer_question, available_evidence,
                       commercial_relevance, risks, missing_information,
                       source, status, evidence_support
                FROM content_angles WHERE angle_id = ?
                """,
                (angle_id,),
            ).fetchone()
        return _content_angle_from_row(row)

    def load_current_angle(self, trip_id: str) -> ContentAngleOption | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT angle.angle_id, angle.viewer_question,
                       angle.available_evidence, angle.commercial_relevance,
                       angle.risks, angle.missing_information, angle.source,
                       angle.status, angle.evidence_support
                FROM trips AS trip
                JOIN content_angles AS angle
                  ON angle.angle_id = trip.current_content_angle_id
                WHERE trip.trip_id = ?
                """,
                (trip_id,),
            ).fetchone()
        return _content_angle_from_row(row) if row is not None else None

    def find_angle_research(
        self, angle_id: str, input_hash: str
    ) -> AngleResearchStage | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    trip.trip_id, trip.name, trip.slug,
                    revision.itinerary_revision_id, revision.revision_number,
                    trip.created_at, trip.current_editorial_package_version,
                    stage.workflow_stage_id, stage.status, stage.input_hash
                FROM workflow_stages AS stage
                JOIN trips AS trip ON trip.trip_id = stage.trip_id
                JOIN itinerary_revisions AS revision
                  ON revision.itinerary_revision_id = stage.itinerary_revision_id
                WHERE stage.scope_key = ?
                  AND stage.stage_name = 'angle_research'
                  AND stage.input_hash = ?
                """,
                (angle_id, input_hash),
            ).fetchone()
        return _angle_research_stage_from_row(row, angle_id) if row is not None else None

    def start_angle_research(
        self, trip: TripRecord, angle_id: str, input_hash: str
    ) -> tuple[AngleResearchStage, StageAttempt]:
        now = _utc_now()
        workflow_stage_id = f"wfs_{uuid.uuid4().hex}"
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO workflow_stages (
                    workflow_stage_id, trip_id, itinerary_revision_id,
                    scope_key, stage_name, input_hash, status, result_json,
                    completed_at
                ) VALUES (?, ?, ?, ?, 'angle_research', ?, ?, '{}', NULL)
                """,
                (
                    workflow_stage_id,
                    trip.trip_id,
                    trip.itinerary_revision_id,
                    angle_id,
                    input_hash,
                    StageStatus.IN_PROGRESS,
                ),
            )
            attempt = StageAttempt(
                workflow_stage_id=workflow_stage_id,
                stage_attempt_id=f"sta_{uuid.uuid4().hex}",
                attempt_number=1,
            )
            self._insert_attempt(connection, attempt, now)
        stage = AngleResearchStage(
            trip=trip,
            angle_id=angle_id,
            workflow_stage_id=workflow_stage_id,
            status=StageStatus.IN_PROGRESS,
            input_hash=input_hash,
        )
        return stage, attempt

    def persist_angle_research(
        self,
        trip_id: str,
        itinerary_revision_id: str,
        angle_id: str,
        sources: list[SourceRecord],
        claim: ResearchClaim,
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing_claim = connection.execute(
                """
                SELECT claim_id FROM research_claims
                WHERE itinerary_revision_id = ? AND category = 'ANGLE_SUPPORT'
                  AND angle_id = ?
                """,
                (itinerary_revision_id, angle_id),
            ).fetchone()
            if existing_claim is not None:
                connection.execute(
                    "DELETE FROM research_claim_sources WHERE claim_id = ?",
                    (existing_claim[0],),
                )
                connection.execute(
                    "DELETE FROM research_claims WHERE claim_id = ?",
                    (existing_claim[0],),
                )
            connection.execute(
                """
                DELETE FROM source_records
                WHERE itinerary_revision_id = ? AND category = 'ANGLE_SUPPORT'
                  AND locator = ?
                """,
                (itinerary_revision_id, f"angle:{angle_id}"),
            )
            for source in sources:
                connection.execute(
                    """
                    INSERT INTO source_records (
                        source_record_id, trip_id, itinerary_revision_id,
                        category, url, title, publisher, published_at,
                        retrieved_at, content_hash, locator, evidence_summary
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source.source_record_id,
                        trip_id,
                        itinerary_revision_id,
                        source.category,
                        source.url,
                        source.title,
                        source.publisher,
                        source.published_at,
                        source.retrieved_at,
                        source.content_hash,
                        source.locator,
                        source.evidence_summary,
                    ),
                )
            connection.execute(
                """
                INSERT INTO research_claims (
                    claim_id, trip_id, itinerary_revision_id, category,
                    statement, evidence_status, recheck_date, stale,
                    angle_id, created_at
                ) VALUES (?, ?, ?, 'ANGLE_SUPPORT', ?, ?, ?, ?, ?, ?)
                """,
                (
                    claim.claim_id,
                    trip_id,
                    itinerary_revision_id,
                    claim.statement,
                    claim.evidence_status,
                    claim.recheck_date,
                    int(claim.stale),
                    angle_id,
                    _utc_now(),
                ),
            )
            for source in sources:
                connection.execute(
                    """
                    INSERT INTO research_claim_sources (claim_id, source_record_id)
                    VALUES (?, ?)
                    """,
                    (claim.claim_id, source.source_record_id),
                )

    def complete_angle_research(
        self, stage: AngleResearchStage, attempt: StageAttempt
    ) -> None:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            attempt_update = connection.execute(
                """
                UPDATE stage_attempts
                SET status = ?, completed_at = ?, error_code = NULL
                WHERE stage_attempt_id = ? AND workflow_stage_id = ? AND status = ?
                """,
                (
                    StageStatus.COMPLETED,
                    now,
                    attempt.stage_attempt_id,
                    stage.workflow_stage_id,
                    StageStatus.IN_PROGRESS,
                ),
            )
            if attempt_update.rowcount != 1:
                raise RuntimeError("Angle research attempt is stale.")
            stage_update = connection.execute(
                """
                UPDATE workflow_stages
                SET status = ?, completed_at = ?
                WHERE workflow_stage_id = ? AND status = ?
                """,
                (
                    StageStatus.COMPLETED,
                    now,
                    stage.workflow_stage_id,
                    StageStatus.IN_PROGRESS,
                ),
            )
            if stage_update.rowcount != 1:
                raise RuntimeError("Angle research stage is no longer live.")

    def load_angle_research_claim(
        self, itinerary_revision_id: str, angle_id: str
    ) -> ResearchClaim | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT claim_id, statement, evidence_status, recheck_date, stale
                FROM research_claims
                WHERE itinerary_revision_id = ? AND category = 'ANGLE_SUPPORT'
                  AND angle_id = ?
                """,
                (itinerary_revision_id, angle_id),
            ).fetchone()
        if row is None:
            return None
        return self.load_research_claim_by_id(str(row[0]))

    def find_narration_stage(
        self, angle_id: str, input_hash: str
    ) -> NarrationStage | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    trip.trip_id, trip.name, trip.slug,
                    revision.itinerary_revision_id, revision.revision_number,
                    trip.created_at, trip.current_editorial_package_version,
                    stage.workflow_stage_id, stage.status, stage.input_hash
                FROM workflow_stages AS stage
                JOIN trips AS trip ON trip.trip_id = stage.trip_id
                JOIN itinerary_revisions AS revision
                  ON revision.itinerary_revision_id = stage.itinerary_revision_id
                WHERE stage.scope_key = ?
                  AND stage.stage_name = 'narration'
                  AND stage.input_hash = ?
                """,
                (angle_id, input_hash),
            ).fetchone()
        if row is None:
            return None
        trip = TripRecord(
            trip_id=str(row[0]),
            name=str(row[1]),
            slug=str(row[2]),
            itinerary_revision_id=str(row[3]),
            revision_number=int(row[4]),
            created_at=str(row[5]),
            current_editorial_package_version=(
                str(row[6]) if row[6] is not None else None
            ),
        )
        return NarrationStage(
            trip=trip,
            angle_id=angle_id,
            workflow_stage_id=str(row[7]),
            status=StageStatus(str(row[8])),
            input_hash=str(row[9]),
        )

    def start_narration(
        self, trip: TripRecord, angle_id: str, input_hash: str
    ) -> tuple[NarrationStage, StageAttempt]:
        now = _utc_now()
        workflow_stage_id = f"wfs_{uuid.uuid4().hex}"
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO workflow_stages (
                    workflow_stage_id, trip_id, itinerary_revision_id,
                    scope_key, stage_name, input_hash, status, result_json,
                    completed_at
                ) VALUES (?, ?, ?, ?, 'narration', ?, ?, '{}', NULL)
                """,
                (
                    workflow_stage_id,
                    trip.trip_id,
                    trip.itinerary_revision_id,
                    angle_id,
                    input_hash,
                    StageStatus.IN_PROGRESS,
                ),
            )
            attempt = StageAttempt(
                workflow_stage_id=workflow_stage_id,
                stage_attempt_id=f"sta_{uuid.uuid4().hex}",
                attempt_number=1,
            )
            self._insert_attempt(connection, attempt, now)
        stage = NarrationStage(
            trip=trip,
            angle_id=angle_id,
            workflow_stage_id=workflow_stage_id,
            status=StageStatus.IN_PROGRESS,
            input_hash=input_hash,
        )
        return stage, attempt

    def persist_narration(
        self,
        trip_id: str,
        itinerary_revision_id: str,
        angle_id: str,
        sections: tuple[NarrationSection, ...],
        editorial_notes: str | None,
        word_count: int,
        estimated_minutes: float,
        overall_intensity: int | None,
        day_intensities: tuple[DayIntensity, ...],
        warnings: tuple[str, ...],
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                DELETE FROM narrations
                WHERE itinerary_revision_id = ? AND angle_id = ?
                """,
                (itinerary_revision_id, angle_id),
            )
            connection.execute(
                """
                INSERT INTO narrations (
                    narration_id, trip_id, itinerary_revision_id, angle_id,
                    sections_json, editorial_notes, word_count,
                    estimated_minutes, overall_intensity,
                    day_intensities_json, warnings_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"nar_{uuid.uuid4().hex}",
                    trip_id,
                    itinerary_revision_id,
                    angle_id,
                    json.dumps(
                        [
                            {"key": s.key, "title": s.title, "body": s.body}
                            for s in sections
                        ]
                    ),
                    editorial_notes,
                    word_count,
                    estimated_minutes,
                    overall_intensity,
                    json.dumps(
                        [
                            {"day_number": d.day_number, "rating": d.rating}
                            for d in day_intensities
                        ]
                    ),
                    json.dumps(list(warnings)),
                    _utc_now(),
                ),
            )

    def complete_narration(self, stage: NarrationStage, attempt: StageAttempt) -> None:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            attempt_update = connection.execute(
                """
                UPDATE stage_attempts
                SET status = ?, completed_at = ?, error_code = NULL
                WHERE stage_attempt_id = ? AND workflow_stage_id = ? AND status = ?
                """,
                (
                    StageStatus.COMPLETED,
                    now,
                    attempt.stage_attempt_id,
                    stage.workflow_stage_id,
                    StageStatus.IN_PROGRESS,
                ),
            )
            if attempt_update.rowcount != 1:
                raise RuntimeError("Narration attempt is stale.")
            stage_update = connection.execute(
                """
                UPDATE workflow_stages
                SET status = ?, completed_at = ?
                WHERE workflow_stage_id = ? AND status = ?
                """,
                (
                    StageStatus.COMPLETED,
                    now,
                    stage.workflow_stage_id,
                    StageStatus.IN_PROGRESS,
                ),
            )
            if stage_update.rowcount != 1:
                raise RuntimeError("Narration stage is no longer live.")

    def load_narration(
        self, itinerary_revision_id: str, angle_id: str
    ) -> tuple[
        tuple[NarrationSection, ...],
        int,
        float,
        int | None,
        tuple[DayIntensity, ...],
        tuple[str, ...],
    ] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT sections_json, word_count, estimated_minutes,
                       overall_intensity, day_intensities_json, warnings_json
                FROM narrations
                WHERE itinerary_revision_id = ? AND angle_id = ?
                """,
                (itinerary_revision_id, angle_id),
            ).fetchone()
        if row is None:
            return None
        sections = tuple(
            NarrationSection(key=s["key"], title=s["title"], body=s["body"])
            for s in json.loads(str(row[0]))
        )
        day_intensities = tuple(
            DayIntensity(day_number=int(d["day_number"]), rating=d["rating"])
            for d in json.loads(str(row[4]))
        )
        warnings = tuple(json.loads(str(row[5])))
        return (
            sections,
            int(row[1]),
            float(row[2]),
            int(row[3]) if row[3] is not None else None,
            day_intensities,
            warnings,
        )

    def persist_validation_report(
        self,
        trip_id: str,
        itinerary_revision_id: str,
        angle_id: str,
        draft_signature: str,
        findings: list[ValidationFinding],
        quality_score: int,
        export_blocked: bool,
    ) -> None:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO validation_reports (
                    draft_signature, trip_id, itinerary_revision_id, angle_id,
                    quality_score, export_blocked, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (draft_signature) DO UPDATE SET
                    quality_score = excluded.quality_score,
                    export_blocked = excluded.export_blocked,
                    created_at = excluded.created_at
                """,
                (
                    draft_signature,
                    trip_id,
                    itinerary_revision_id,
                    angle_id,
                    quality_score,
                    int(export_blocked),
                    now,
                ),
            )
            connection.execute(
                "DELETE FROM validation_findings WHERE draft_signature = ?",
                (draft_signature,),
            )
            for finding in findings:
                connection.execute(
                    """
                    INSERT INTO validation_findings (
                        draft_signature, finding_id, code, severity, message,
                        locator
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        draft_signature,
                        finding.finding_id,
                        finding.code,
                        finding.severity,
                        finding.message,
                        finding.locator,
                    ),
                )

    def load_acknowledgments(
        self, draft_signature: str
    ) -> tuple[ValidationAcknowledgment, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT finding_id, approver, acknowledged_at, draft_signature
                FROM validation_acknowledgments
                WHERE draft_signature = ?
                """,
                (draft_signature,),
            ).fetchall()
        return tuple(
            ValidationAcknowledgment(
                finding_id=str(row[0]),
                approver=str(row[1]),
                acknowledged_at=str(row[2]),
                draft_signature=str(row[3]),
            )
            for row in rows
        )

    def persist_acknowledgment(
        self, draft_signature: str, finding_id: str, approver: str
    ) -> ValidationAcknowledgment:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO validation_acknowledgments (
                    draft_signature, finding_id, approver, acknowledged_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT (draft_signature, finding_id) DO UPDATE SET
                    approver = excluded.approver,
                    acknowledged_at = excluded.acknowledged_at
                """,
                (draft_signature, finding_id, approver, now),
            )
        return ValidationAcknowledgment(
            finding_id=finding_id,
            approver=approver,
            acknowledged_at=now,
            draft_signature=draft_signature,
        )

    def insert_version(
        self,
        trip_id: str,
        itinerary_revision_id: str,
        angle_id: str,
        narration_signature: str,
        quality_score: int,
        export_blocked: bool,
        findings_json: str,
        acknowledgments_json: str,
        claims_json: str,
        content_hash: str,
        *,
        youtube_packaging_signature: str | None = None,
        production_brief_signature: str | None = None,
    ) -> EditorialPackageVersion:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            version_number = int(
                connection.execute(
                    """
                    SELECT COALESCE(MAX(version_number), 0) + 1
                    FROM editorial_package_versions WHERE trip_id = ?
                    """,
                    (trip_id,),
                ).fetchone()[0]
            )
            connection.execute(
                """
                INSERT INTO editorial_package_versions (
                    trip_id, version_number, itinerary_revision_id, angle_id,
                    narration_signature, youtube_packaging_signature,
                    production_brief_signature, quality_score, export_blocked,
                    findings_json, acknowledgments_json, claims_json,
                    content_hash, submitted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trip_id,
                    version_number,
                    itinerary_revision_id,
                    angle_id,
                    narration_signature,
                    youtube_packaging_signature,
                    production_brief_signature,
                    quality_score,
                    int(export_blocked),
                    findings_json,
                    acknowledgments_json,
                    claims_json,
                    content_hash,
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE trips SET current_editorial_package_version = ?
                WHERE trip_id = ?
                """,
                (f"v{version_number}", trip_id),
            )
        return EditorialPackageVersion(
            trip_id=trip_id,
            version_number=version_number,
            itinerary_revision_id=itinerary_revision_id,
            angle_id=angle_id,
            narration_signature=narration_signature,
            quality_score=quality_score,
            export_blocked=export_blocked,
            content_hash=content_hash,
            submitted_at=now,
            youtube_packaging_signature=youtube_packaging_signature,
            production_brief_signature=production_brief_signature,
        )

    def load_version(
        self, trip_id: str, version_number: int
    ) -> EditorialPackageVersion | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT trip_id, version_number, itinerary_revision_id, angle_id,
                       narration_signature, quality_score, export_blocked,
                       content_hash, submitted_at, youtube_packaging_signature,
                       production_brief_signature
                FROM editorial_package_versions
                WHERE trip_id = ? AND version_number = ?
                """,
                (trip_id, version_number),
            ).fetchone()
        return _version_from_row(row) if row is not None else None

    def load_latest_version(self, trip_id: str) -> EditorialPackageVersion | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT trip_id, version_number, itinerary_revision_id, angle_id,
                       narration_signature, quality_score, export_blocked,
                       content_hash, submitted_at, youtube_packaging_signature,
                       production_brief_signature
                FROM editorial_package_versions
                WHERE trip_id = ?
                ORDER BY version_number DESC
                LIMIT 1
                """,
                (trip_id,),
            ).fetchone()
        return _version_from_row(row) if row is not None else None

    def persist_production_brief(
        self,
        itinerary_revision_id: str,
        angle_id: str,
        payload_json: str,
        content_signature: str,
    ) -> None:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO production_briefs (
                    itinerary_revision_id, angle_id, payload_json,
                    content_signature, created_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (itinerary_revision_id, angle_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    content_signature = excluded.content_signature,
                    created_at = excluded.created_at
                """,
                (itinerary_revision_id, angle_id, payload_json, content_signature, now),
            )

    def load_production_brief_signature(
        self, itinerary_revision_id: str, angle_id: str
    ) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT content_signature FROM production_briefs
                WHERE itinerary_revision_id = ? AND angle_id = ?
                """,
                (itinerary_revision_id, angle_id),
            ).fetchone()
        return str(row[0]) if row is not None else None

    def persist_youtube_packaging(
        self,
        itinerary_revision_id: str,
        angle_id: str,
        payload_json: str,
        content_signature: str,
    ) -> None:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO youtube_packaging (
                    itinerary_revision_id, angle_id, payload_json,
                    content_signature, created_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (itinerary_revision_id, angle_id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    content_signature = excluded.content_signature,
                    created_at = excluded.created_at
                """,
                (itinerary_revision_id, angle_id, payload_json, content_signature, now),
            )

    def load_youtube_packaging(
        self, itinerary_revision_id: str, angle_id: str
    ) -> tuple[str, str] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT payload_json, content_signature FROM youtube_packaging
                WHERE itinerary_revision_id = ? AND angle_id = ?
                """,
                (itinerary_revision_id, angle_id),
            ).fetchone()
        return (str(row[0]), str(row[1])) if row is not None else None

    def load_youtube_packaging_signature(
        self, itinerary_revision_id: str, angle_id: str
    ) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT content_signature FROM youtube_packaging
                WHERE itinerary_revision_id = ? AND angle_id = ?
                """,
                (itinerary_revision_id, angle_id),
            ).fetchone()
        return str(row[0]) if row is not None else None

    def record_approval(
        self,
        trip_id: str,
        version_number: int,
        component: VersionComponent,
        approver: str,
        content_integrity_reference: str,
    ) -> VersionApproval:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO version_approvals (
                    trip_id, version_number, component, approver, approved_at,
                    content_integrity_reference
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (trip_id, version_number, component) DO UPDATE SET
                    approver = excluded.approver,
                    approved_at = excluded.approved_at,
                    content_integrity_reference = excluded.content_integrity_reference
                """,
                (
                    trip_id,
                    version_number,
                    component,
                    approver,
                    now,
                    content_integrity_reference,
                ),
            )
        return VersionApproval(
            trip_id=trip_id,
            version_number=version_number,
            component=component,
            approver=approver,
            approved_at=now,
            content_integrity_reference=content_integrity_reference,
        )

    def load_approval(
        self, trip_id: str, version_number: int, component: VersionComponent
    ) -> VersionApproval | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT trip_id, version_number, component, approver,
                       approved_at, content_integrity_reference
                FROM version_approvals
                WHERE trip_id = ? AND version_number = ? AND component = ?
                """,
                (trip_id, version_number, component),
            ).fetchone()
        return _approval_from_row(row) if row is not None else None

    def inspect_trip(self, trip_id: str) -> TripInspectionResult | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    trip.trip_id, trip.name, trip.slug, revision.revision_number,
                    stage.status
                FROM trips AS trip
                JOIN itinerary_revisions AS revision
                  ON revision.itinerary_revision_id =
                     trip.current_itinerary_revision_id
                LEFT JOIN workflow_stages AS stage
                  ON stage.trip_id = trip.trip_id
                 AND stage.stage_name = 'trip_create'
                WHERE trip.trip_id = ?
                """,
                (trip_id,),
            ).fetchone()
        if row is None:
            return None
        trip_id_value, name, slug, revision_number, creation_status = row
        source_path = (
            self.workspace
            / "outputs"
            / f"{slug}--{trip_id_value}"
            / "source"
            / f"r{revision_number}"
            / "original-itinerary.txt"
        )
        working_review_state = self.load_working_review_state(str(trip_id_value))
        return TripInspectionResult(
            trip_id=str(trip_id_value),
            name=str(name),
            slug=str(slug),
            revision_number=int(revision_number),
            creation_status=StageStatus(str(creation_status)),
            source_path=source_path,
            working_review_status=(
                working_review_state.status
                if working_review_state is not None
                else None
            ),
        )

    @staticmethod
    def _insert_attempt(
        connection: sqlite3.Connection, attempt: StageAttempt, started_at: str
    ) -> None:
        connection.execute(
            """
            INSERT INTO stage_attempts (
                stage_attempt_id, workflow_stage_id, attempt_number,
                status, started_at, completed_at
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
            with connection:
                yield connection
        finally:
            connection.close()


def _trip_creation_stage_from_row(row: tuple[object, ...]) -> TripCreationStage:
    trip = TripRecord(
        trip_id=str(row[0]),
        name=str(row[1]),
        slug=str(row[2]),
        itinerary_revision_id=str(row[3]),
        revision_number=int(row[4]),
        created_at=str(row[5]),
        current_editorial_package_version=(
            str(row[6]) if row[6] is not None else None
        ),
    )
    return TripCreationStage(
        trip=trip,
        workflow_stage_id=str(row[7]),
        status=StageStatus(str(row[8])),
    )


def _itinerary_processing_stage_from_row(
    row: tuple[object, ...],
) -> ItineraryProcessingStage:
    trip = TripRecord(
        trip_id=str(row[0]),
        name=str(row[1]),
        slug=str(row[2]),
        itinerary_revision_id=str(row[3]),
        revision_number=int(row[4]),
        created_at=str(row[5]),
        current_editorial_package_version=(
            str(row[6]) if row[6] is not None else None
        ),
    )
    return ItineraryProcessingStage(
        trip=trip,
        workflow_stage_id=str(row[7]),
        status=StageStatus(str(row[8])),
        input_hash=str(row[9]),
    )


def _trip_update_stage_from_row(row: tuple[object, ...]) -> TripUpdateStage:
    trip = TripRecord(
        trip_id=str(row[0]),
        name=str(row[1]),
        slug=str(row[2]),
        itinerary_revision_id=str(row[3]),
        revision_number=int(row[4]),
        created_at=str(row[5]),
        current_editorial_package_version=(
            str(row[6]) if row[6] is not None else None
        ),
    )
    result_data = json.loads(str(row[10]))
    previous_revision_id = str(result_data.get("previous_revision_id", ""))
    return TripUpdateStage(
        trip=trip,
        previous_revision_id=previous_revision_id,
        workflow_stage_id=str(row[7]),
        status=StageStatus(str(row[8])),
        input_hash=str(row[9]),
    )


def _baseline_research_stage_from_row(
    row: tuple[object, ...],
) -> BaselineResearchStage:
    trip = TripRecord(
        trip_id=str(row[0]),
        name=str(row[1]),
        slug=str(row[2]),
        itinerary_revision_id=str(row[3]),
        revision_number=int(row[4]),
        created_at=str(row[5]),
        current_editorial_package_version=(
            str(row[6]) if row[6] is not None else None
        ),
    )
    progress = json.loads(str(row[10]))
    completed_categories = tuple(
        ResearchCategory(value) for value in progress.get("completed_categories", [])
    )
    return BaselineResearchStage(
        trip=trip,
        workflow_stage_id=str(row[7]),
        status=StageStatus(str(row[8])),
        input_hash=str(row[9]),
        completed_categories=completed_categories,
    )


def _version_from_row(row: tuple[object, ...]) -> EditorialPackageVersion:
    return EditorialPackageVersion(
        trip_id=str(row[0]),
        version_number=int(row[1]),
        itinerary_revision_id=str(row[2]),
        angle_id=str(row[3]),
        narration_signature=str(row[4]),
        quality_score=int(row[5]),
        export_blocked=bool(row[6]),
        content_hash=str(row[7]),
        submitted_at=str(row[8]),
        youtube_packaging_signature=(
            str(row[9]) if len(row) > 9 and row[9] is not None else None
        ),
        production_brief_signature=(
            str(row[10]) if len(row) > 10 and row[10] is not None else None
        ),
    )


def _approval_from_row(row: tuple[object, ...]) -> VersionApproval:
    return VersionApproval(
        trip_id=str(row[0]),
        version_number=int(row[1]),
        component=VersionComponent(str(row[2])),
        approver=str(row[3]),
        approved_at=str(row[4]),
        content_integrity_reference=str(row[5]),
    )


def _content_angle_from_row(row: tuple[object, ...]) -> ContentAngleOption:
    return ContentAngleOption(
        angle_id=str(row[0]),
        viewer_question=str(row[1]),
        available_evidence=tuple(json.loads(str(row[2]))),
        commercial_relevance=str(row[3]),
        risks=str(row[4]),
        missing_information=tuple(json.loads(str(row[5]))),
        source=ContentAngleSource(str(row[6])),
        status=ContentAngleStatus(str(row[7])),
        evidence_support=EvidenceSupportLevel(str(row[8])),
    )


def _angle_research_stage_from_row(
    row: tuple[object, ...], angle_id: str
) -> AngleResearchStage:
    trip = TripRecord(
        trip_id=str(row[0]),
        name=str(row[1]),
        slug=str(row[2]),
        itinerary_revision_id=str(row[3]),
        revision_number=int(row[4]),
        created_at=str(row[5]),
        current_editorial_package_version=(
            str(row[6]) if row[6] is not None else None
        ),
    )
    return AngleResearchStage(
        trip=trip,
        angle_id=angle_id,
        workflow_stage_id=str(row[7]),
        status=StageStatus(str(row[8])),
        input_hash=str(row[9]),
    )


def _route_segment_from_row(row: tuple[object, ...]) -> RouteSegment:
    return RouteSegment(
        route_segment_id=str(row[0]),
        origin=str(row[1]),
        destination=str(row[2]),
        status=RouteSegmentStatus(str(row[3])),
        created_at=str(row[4]),
        confirmed_at=str(row[5]) if row[5] is not None else None,
    )


def _route_segment_match_key(origin: str, destination: str) -> str:
    return f"{origin.strip().casefold()}|{destination.strip().casefold()}"


def _trip_update_scope_key(trip_id: str, previous_revision_id: str) -> str:
    return f"{trip_id}:{previous_revision_id}"


def _content_hash(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
