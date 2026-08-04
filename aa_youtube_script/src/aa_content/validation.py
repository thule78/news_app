from __future__ import annotations

import hashlib
from pathlib import Path
import re

from aa_content.errors import UserFacingError
from aa_content.models import (
    EvidenceStatus,
    FindingSeverity,
    NarrationSection,
    ResearchCategory,
    ResearchClaim,
    SanitizationStatus,
    ValidationFinding,
    ValidationReport,
)
from aa_content.persistence import WorkspaceRepository

QUALITY_BENCHMARK = 80

_PRICE_PATTERN = re.compile(
    r"[$€£¥]\s?\d|\b\d+(?:\.\d+)?\s?(?:usd|eur|gbp|jpy|vnd|dollars?)\b",
    re.IGNORECASE,
)
_PROMISE_PHRASES = (
    "guarantee", "guaranteed", "we provide", "we will arrange", "we include",
    "we ensure", "promise",
)
_SAFETY_GUARANTEE_PHRASES = (
    "100% safe", "completely safe", "no risk", "guaranteed safe", "totally safe",
)
_MEDICAL_PHRASES = (
    "cures", "treats", "medically approved", "doctor recommended", "diagnosis",
)
_EXCLUSIVITY_PHRASES = (
    "only we offer", "exclusive access", "nowhere else", "only company",
    "only operator",
)
_BRAND_PHRASES = (
    "the best in the world", "#1 rated", "world's best", "guaranteed lowest",
)
_VISUAL_DEPENDENCY_PHRASES = (
    "as you can see", "pictured here", "in this shot", "shown above",
    "as shown", "in the photo", "in the video above",
)


def validate_package(workspace: Path, trip_id: str) -> ValidationReport:
    repository = WorkspaceRepository(workspace)
    if not repository.database_path.is_file():
        raise UserFacingError(
            f"Workspace is not initialized: run init for {workspace.resolve()}"
        )
    trip = repository.load_current_trip(trip_id)
    if trip is None:
        raise UserFacingError(f"Trip not found: {trip_id}")

    angle = repository.load_current_angle(trip.trip_id)
    if angle is None:
        raise UserFacingError(
            "No approved Content Angle: run `trip angle approve` first."
        )
    loaded_narration = repository.load_narration(
        trip.itinerary_revision_id, angle.angle_id
    )
    if loaded_narration is None:
        raise UserFacingError("No narration to validate: run `trip narrate` first.")
    sections = loaded_narration[0]

    normalized = repository.load_normalized_itinerary(trip.itinerary_revision_id) or {}
    claims = repository.load_research_claims(trip.itinerary_revision_id)
    (
        sanitization_status,
        _finding_count,
        _missing_count,
        _conflict_count,
        export_blocked,
    ) = repository.load_itinerary_processing_summary(trip.itinerary_revision_id)

    findings: list[ValidationFinding] = []
    findings.extend(_check_evidence_linkage(claims))
    findings.extend(_check_stale_claims(claims))
    findings.extend(_check_fact_conflicts(normalized))
    findings.extend(_check_missing_information(normalized, claims))
    findings.extend(_check_narration_language(sections))
    findings.extend(_check_supplier_data(sanitization_status, export_blocked))

    quality_score = _compute_quality_score(findings)
    draft_signature = compute_draft_signature(
        trip.itinerary_revision_id, angle.angle_id, sections
    )
    repository.persist_validation_report(
        trip.trip_id,
        trip.itinerary_revision_id,
        angle.angle_id,
        draft_signature,
        findings,
        quality_score,
        export_blocked,
    )
    acknowledgments = repository.load_acknowledgments(draft_signature)
    return ValidationReport(
        trip=trip,
        draft_signature=draft_signature,
        findings=tuple(findings),
        acknowledgments=acknowledgments,
        quality_score=quality_score,
        export_blocked=export_blocked,
    )


def acknowledge_finding(
    workspace: Path, trip_id: str, finding_id: str, approver: str
):
    approver = approver.strip()
    if not approver:
        raise UserFacingError("Approver identity is required to acknowledge a finding.")
    report = validate_package(workspace, trip_id)
    finding = next((f for f in report.findings if f.finding_id == finding_id), None)
    if finding is None:
        raise UserFacingError(f"Finding not found in current validation: {finding_id}")
    if finding.severity is FindingSeverity.BLOCKING:
        raise UserFacingError(
            "The Supplier Data Export Block cannot be acknowledged or "
            "overridden; resolve the flagged content instead."
        )
    repository = WorkspaceRepository(workspace)
    return repository.persist_acknowledgment(
        report.draft_signature, finding_id, approver
    )


def _check_evidence_linkage(
    claims: tuple[ResearchClaim, ...],
) -> list[ValidationFinding]:
    findings = []
    for claim in claims:
        if claim.evidence_status is EvidenceStatus.UNVERIFIED:
            findings.append(
                ValidationFinding(
                    finding_id=f"EVIDENCE_LINKAGE_GAP:{claim.category}",
                    code="EVIDENCE_LINKAGE_GAP",
                    severity=FindingSeverity.WARNING,
                    message=(
                        f"{claim.category} Claim has UNVERIFIED Evidence "
                        "Status and must not be treated as factual."
                    ),
                    locator=str(claim.category),
                )
            )
        elif (
            claim.evidence_status is not EvidenceStatus.UNKNOWN
            and not claim.sources
        ):
            findings.append(
                ValidationFinding(
                    finding_id=f"EVIDENCE_LINKAGE_GAP:{claim.category}",
                    code="EVIDENCE_LINKAGE_GAP",
                    severity=FindingSeverity.WARNING,
                    message=(
                        f"{claim.category} Claim has no linked Evidence "
                        f"despite status {claim.evidence_status}."
                    ),
                    locator=str(claim.category),
                )
            )
    return findings


def _check_stale_claims(claims: tuple[ResearchClaim, ...]) -> list[ValidationFinding]:
    return [
        ValidationFinding(
            finding_id=f"STALE_CLAIM:{claim.category}",
            code="STALE_CLAIM",
            severity=FindingSeverity.WARNING,
            message=(
                f"{claim.category} Claim is Stale: its Recheck Date passed "
                "and refresh failed."
            ),
            locator=str(claim.category),
        )
        for claim in claims
        if claim.stale
    ]


def _check_fact_conflicts(normalized: dict[str, object]) -> list[ValidationFinding]:
    conflicts = normalized.get("fact_conflicts", [])
    if not isinstance(conflicts, list):
        return []
    findings = []
    for index, conflict in enumerate(conflicts):
        if not isinstance(conflict, dict):
            continue
        subject = str(conflict.get("subject", f"conflict-{index}"))
        findings.append(
            ValidationFinding(
                finding_id=f"FACT_CONFLICT:{subject}",
                code="FACT_CONFLICT",
                severity=FindingSeverity.WARNING,
                message=f"Unresolved Fact Conflict: {subject}.",
                locator=subject,
            )
        )
    return findings


def _check_missing_information(
    normalized: dict[str, object], claims: tuple[ResearchClaim, ...]
) -> list[ValidationFinding]:
    findings = []
    missing = normalized.get("missing_information", [])
    if isinstance(missing, list):
        for item in missing:
            if not isinstance(item, dict):
                continue
            scope = str(item.get("scope", "Trip"))
            field = str(item.get("field", "unknown"))
            findings.append(
                ValidationFinding(
                    finding_id=f"MISSING_INFORMATION:itinerary:{scope}:{field}",
                    code="MISSING_INFORMATION",
                    severity=FindingSeverity.WARNING,
                    message=f"Missing Information: {scope} {field} is unknown.",
                    locator=f"{scope}/{field}",
                )
            )
    for claim in claims:
        if claim.evidence_status is EvidenceStatus.UNKNOWN:
            findings.append(
                ValidationFinding(
                    finding_id=f"MISSING_INFORMATION:research:{claim.category}",
                    code="MISSING_INFORMATION",
                    severity=FindingSeverity.WARNING,
                    message=(
                        f"Missing Information: no current Evidence found for "
                        f"{claim.category}."
                    ),
                    locator=str(claim.category),
                )
            )
    return findings


def _check_narration_language(
    sections: tuple[NarrationSection, ...],
) -> list[ValidationFinding]:
    findings = []
    checks: tuple[tuple[str, str, tuple[str, ...]], ...] = (
        ("UNSUPPORTED_PRODUCT_PROMISE", "Unsupported Product Promise language", _PROMISE_PHRASES),
        ("PRICE_INFORMATION", "Price Information is prohibited", ()),
        ("UNSUPPORTED_SAFETY_GUARANTEE", "Unsupported safety guarantee language", _SAFETY_GUARANTEE_PHRASES),
        ("MEDICAL_CONCLUSION", "Medical conclusion language", _MEDICAL_PHRASES),
        ("MISLEADING_EXCLUSIVITY", "Misleading exclusivity language", _EXCLUSIVITY_PHRASES),
        ("RESTRICTED_BRAND_PHRASE", "Restricted brand phrase", _BRAND_PHRASES),
        ("VISUAL_DEPENDENCY", "Narration depends on an unseen visual", _VISUAL_DEPENDENCY_PHRASES),
    )
    for section in sections:
        lowered = section.body.lower()
        for code, label, phrases in checks:
            if code == "PRICE_INFORMATION":
                if _PRICE_PATTERN.search(section.body):
                    findings.append(
                        ValidationFinding(
                            finding_id=f"{code}:{section.key}",
                            code=code,
                            severity=FindingSeverity.WARNING,
                            message=f"{label} in section '{section.title}'.",
                            locator=section.key,
                        )
                    )
                continue
            for phrase in phrases:
                if phrase in lowered:
                    findings.append(
                        ValidationFinding(
                            finding_id=f"{code}:{section.key}",
                            code=code,
                            severity=FindingSeverity.WARNING,
                            message=(
                                f'{label} ("{phrase}") in section '
                                f"'{section.title}'."
                            ),
                            locator=section.key,
                        )
                    )
                    break
    return findings


def _check_supplier_data(
    sanitization_status: SanitizationStatus, export_blocked: bool
) -> list[ValidationFinding]:
    if not export_blocked:
        return []
    return [
        ValidationFinding(
            finding_id="SUPPLIER_DATA:itinerary",
            code="SUPPLIER_DATA",
            severity=FindingSeverity.BLOCKING,
            message=(
                "Possible Supplier Data remains unresolved in the current "
                "Itinerary Revision; export is blocked until it is "
                "reviewed."
            ),
            locator="itinerary",
        )
    ]


def _compute_quality_score(findings: list[ValidationFinding]) -> int:
    penalties = {
        "EVIDENCE_LINKAGE_GAP": 10,
        "STALE_CLAIM": 5,
        "FACT_CONFLICT": 10,
        "MISSING_INFORMATION": 3,
        "UNSUPPORTED_PRODUCT_PROMISE": 15,
        "PRICE_INFORMATION": 20,
        "UNSUPPORTED_SAFETY_GUARANTEE": 15,
        "MEDICAL_CONCLUSION": 15,
        "MISLEADING_EXCLUSIVITY": 15,
        "RESTRICTED_BRAND_PHRASE": 10,
        "VISUAL_DEPENDENCY": 5,
        "SUPPLIER_DATA": 25,
    }
    score = 100
    for finding in findings:
        score -= penalties.get(finding.code, 5)
    return max(0, min(100, score))


def compute_draft_signature(
    itinerary_revision_id: str, angle_id: str, sections: tuple[NarrationSection, ...]
) -> str:
    digest = hashlib.sha256()
    digest.update(itinerary_revision_id.encode("utf-8"))
    digest.update(b"\0")
    digest.update(angle_id.encode("utf-8"))
    for section in sections:
        digest.update(b"\0")
        digest.update(section.body.encode("utf-8"))
    return digest.hexdigest()
