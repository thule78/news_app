from __future__ import annotations

import hashlib
import json
from pathlib import Path

from aa_content.errors import UserFacingError
from aa_content.models import (
    ComponentStatus,
    ComponentValidity,
    EditorialPackageVersion,
    ResearchCategory,
    VersionApproval,
    VersionComponent,
    VersionStatus,
)
from aa_content.persistence import WorkspaceRepository
from aa_content.validation import compute_draft_signature, validate_package

_COMPONENT_ORDER: tuple[VersionComponent, ...] = (
    VersionComponent.NARRATION,
    VersionComponent.FINAL,
)


def submit_review(workspace: Path, trip_id: str) -> EditorialPackageVersion:
    repository = WorkspaceRepository(workspace)
    if not repository.database_path.is_file():
        raise UserFacingError(
            f"Workspace is not initialized: run init for {workspace.resolve()}"
        )
    trip = repository.load_current_trip(trip_id)
    if trip is None:
        raise UserFacingError(f"Trip not found: {trip_id}")

    report = validate_package(workspace, trip_id)
    angle = repository.load_current_angle(trip.trip_id)
    assert angle is not None  # validate_package already required this

    claims = [
        claim
        for claim in repository.load_research_claims(trip.itinerary_revision_id)
        if claim.category != ResearchCategory.ANGLE_SUPPORT
    ]
    angle_claim = repository.load_angle_research_claim(
        trip.itinerary_revision_id, angle.angle_id
    )
    claims_snapshot = [
        {
            "category": str(claim.category),
            "statement": claim.statement,
            "evidence_status": str(claim.evidence_status),
            "recheck_date": claim.recheck_date,
            "stale": claim.stale,
            "source_ids": [s.source_record_id for s in claim.sources],
        }
        for claim in claims
    ]
    if angle_claim is not None:
        claims_snapshot.append(
            {
                "category": "ANGLE_SUPPORT",
                "statement": angle_claim.statement,
                "evidence_status": str(angle_claim.evidence_status),
                "recheck_date": angle_claim.recheck_date,
                "stale": angle_claim.stale,
                "source_ids": [s.source_record_id for s in angle_claim.sources],
            }
        )

    findings_json = json.dumps(
        [
            {
                "finding_id": f.finding_id,
                "code": f.code,
                "severity": str(f.severity),
                "message": f.message,
                "locator": f.locator,
            }
            for f in report.findings
        ],
        sort_keys=True,
    )
    acknowledgments_json = json.dumps(
        [
            {
                "finding_id": a.finding_id,
                "approver": a.approver,
                "acknowledged_at": a.acknowledged_at,
            }
            for a in report.acknowledgments
        ],
        sort_keys=True,
    )
    claims_json = json.dumps(claims_snapshot, sort_keys=True)

    content_hash = hashlib.sha256(
        "\0".join(
            [
                trip.itinerary_revision_id,
                angle.angle_id,
                report.draft_signature,
                findings_json,
                acknowledgments_json,
                claims_json,
            ]
        ).encode("utf-8")
    ).hexdigest()

    youtube_packaging_signature = repository.load_youtube_packaging_signature(
        trip.itinerary_revision_id, angle.angle_id
    )
    production_brief_signature = repository.load_production_brief_signature(
        trip.itinerary_revision_id, angle.angle_id
    )
    return repository.insert_version(
        trip.trip_id,
        trip.itinerary_revision_id,
        angle.angle_id,
        report.draft_signature,
        report.quality_score,
        report.export_blocked,
        findings_json,
        acknowledgments_json,
        claims_json,
        content_hash,
        youtube_packaging_signature=youtube_packaging_signature,
        production_brief_signature=production_brief_signature,
    )


def approve_component(
    workspace: Path,
    trip_id: str,
    component: VersionComponent,
    approver: str,
) -> VersionApproval:
    approver = approver.strip()
    if not approver:
        raise UserFacingError("Approver identity is required to approve a component.")

    repository = WorkspaceRepository(workspace)
    if not repository.database_path.is_file():
        raise UserFacingError(
            f"Workspace is not initialized: run init for {workspace.resolve()}"
        )
    trip = repository.load_current_trip(trip_id)
    if trip is None:
        raise UserFacingError(f"Trip not found: {trip_id}")

    version = repository.load_latest_version(trip.trip_id)
    if version is None:
        raise UserFacingError(
            "No submitted version: run `trip submit-review` first."
        )

    status = get_version_status(workspace, trip_id)
    component_status = status.status_for(component)
    if component_status.validity is ComponentValidity.INVALIDATED:
        raise UserFacingError(
            f"{component} approval is invalidated by changes since v"
            f"{version.version_number} was submitted; submit a new version "
            "first."
        )

    if component is VersionComponent.FINAL:
        narration_status = status.status_for(VersionComponent.NARRATION)
        if narration_status.validity is not ComponentValidity.VALID or (
            narration_status.approval is None
        ):
            raise UserFacingError(
                "Approve NARRATION before approving the complete version."
            )
        integrity_reference = version.content_hash
    else:
        integrity_reference = version.narration_signature

    return repository.record_approval(
        trip.trip_id, version.version_number, component, approver, integrity_reference
    )


def get_version_status(workspace: Path, trip_id: str) -> VersionStatus:
    repository = WorkspaceRepository(workspace)
    if not repository.database_path.is_file():
        raise UserFacingError(
            f"Workspace is not initialized: run init for {workspace.resolve()}"
        )
    trip = repository.load_current_trip(trip_id)
    if trip is None:
        raise UserFacingError(f"Trip not found: {trip_id}")
    version = repository.load_latest_version(trip.trip_id)
    if version is None:
        raise UserFacingError(
            "No submitted version: run `trip submit-review` first."
        )

    current_angle = repository.load_current_angle(trip.trip_id)
    current_angle_id = current_angle.angle_id if current_angle is not None else None
    narration_current = current_angle_id == version.angle_id
    if narration_current and current_angle is not None:
        loaded = repository.load_narration(
            trip.itinerary_revision_id, current_angle.angle_id
        )
        if loaded is not None:
            sections = loaded[0]
            live_signature = compute_draft_signature(
                trip.itinerary_revision_id, current_angle.angle_id, sections
            )
            narration_current = live_signature == version.narration_signature
        else:
            narration_current = False
    revision_current = trip.itinerary_revision_id == version.itinerary_revision_id

    narration_valid = revision_current and narration_current
    narration_approval = repository.load_approval(
        trip.trip_id, version.version_number, VersionComponent.NARRATION
    )
    final_approval = repository.load_approval(
        trip.trip_id, version.version_number, VersionComponent.FINAL
    )
    current_youtube_signature = (
        repository.load_youtube_packaging_signature(
            trip.itinerary_revision_id, current_angle_id
        )
        if current_angle_id is not None
        else None
    )
    youtube_current = current_youtube_signature == version.youtube_packaging_signature
    current_brief_signature = (
        repository.load_production_brief_signature(
            trip.itinerary_revision_id, current_angle_id
        )
        if current_angle_id is not None
        else None
    )
    brief_current = current_brief_signature == version.production_brief_signature
    # FINAL depends on NARRATION staying current AND on YouTube packaging /
    # Production Brief staying current — either drifting invalidates only
    # FINAL, never NARRATION itself.
    final_valid = narration_valid and youtube_current and brief_current

    components = (
        _component_status(
            VersionComponent.NARRATION, narration_valid, narration_approval
        ),
        _component_status(VersionComponent.FINAL, final_valid, final_approval),
    )
    return VersionStatus(trip=trip, version=version, components=components)


def _component_status(
    component: VersionComponent,
    is_current: bool,
    approval: VersionApproval | None,
) -> ComponentStatus:
    if approval is None:
        validity = ComponentValidity.NOT_APPROVED
    elif is_current:
        validity = ComponentValidity.VALID
    else:
        validity = ComponentValidity.INVALIDATED
    return ComponentStatus(component=component, validity=validity, approval=approval)
