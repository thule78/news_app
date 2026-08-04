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


class ItinerarySourceKind(StrEnum):
    PASTED_TEXT = "PASTED_TEXT"
    URL = "URL"


class SourceFetchOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class TripUpdateOutcome(StrEnum):
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    RESUMED = "resumed"
    REGENERATED = "regenerated"


class WorkingReviewStatus(StrEnum):
    CURRENT = "CURRENT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ResearchCategory(StrEnum):
    ACCESS = "ACCESS"
    ROUTE_RULES = "ROUTE_RULES"
    SEASONALITY = "SEASONALITY"
    CROWDS = "CROWDS"
    INDEPENDENT_TRANSPORT = "INDEPENDENT_TRANSPORT"
    SOLO_TRAVELLER = "SOLO_TRAVELLER"
    OFFICIAL_ADVISORY = "OFFICIAL_ADVISORY"
    PRACTICAL_DEMANDS = "PRACTICAL_DEMANDS"
    ANGLE_SUPPORT = "ANGLE_SUPPORT"


class EvidenceStatus(StrEnum):
    VERIFIED = "VERIFIED"
    CORROBORATED = "CORROBORATED"
    INDICATIVE = "INDICATIVE"
    UNVERIFIED = "UNVERIFIED"
    UNKNOWN = "UNKNOWN"


class BaselineResearchOutcome(StrEnum):
    RESEARCHED = "researched"
    REUSED = "reused"
    RESUMED = "resumed"
    REGENERATED = "regenerated"


class RouteSegmentStatus(StrEnum):
    PROPOSED = "PROPOSED"
    CONFIRMED = "CONFIRMED"


class ContentAngleStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"


class ContentAngleSource(StrEnum):
    GENERATED = "GENERATED"
    CUSTOM = "CUSTOM"


class EvidenceSupportLevel(StrEnum):
    SUPPORTED = "SUPPORTED"
    WEAK = "WEAK"
    UNSUPPORTED = "UNSUPPORTED"


class AngleResearchOutcome(StrEnum):
    RESEARCHED = "researched"
    REUSED = "reused"
    RESUMED = "resumed"
    REGENERATED = "regenerated"


class NarrationOutcome(StrEnum):
    GENERATED = "generated"
    REUSED = "reused"
    RESUMED = "resumed"
    REGENERATED = "regenerated"


class FindingSeverity(StrEnum):
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"


class VersionComponent(StrEnum):
    NARRATION = "NARRATION"
    FINAL = "FINAL"


class ComponentValidity(StrEnum):
    VALID = "VALID"
    INVALIDATED = "INVALIDATED"
    NOT_APPROVED = "NOT_APPROVED"


class TitleStyle(StrEnum):
    SEARCH_LED = "SEARCH_LED"
    CURIOSITY_LED = "CURIOSITY_LED"
    HYBRID = "HYBRID"


class YoutubePackagingOutcome(StrEnum):
    GENERATED = "generated"
    REUSED = "reused"
    REGENERATED = "regenerated"


class ProductionBriefOutcome(StrEnum):
    GENERATED = "generated"
    REUSED = "reused"
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
class StageAttempt:
    workflow_stage_id: str
    stage_attempt_id: str
    attempt_number: int


@dataclass(frozen=True)
class TripCreationStage:
    trip: TripRecord
    workflow_stage_id: str
    status: StageStatus


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
    working_review_status: WorkingReviewStatus | None = None


@dataclass(frozen=True)
class ItinerarySource:
    kind: ItinerarySourceKind
    text: str
    requested_url: str | None = None


@dataclass(frozen=True)
class SourceFetchRecord:
    source_fetch_id: str
    requested_url: str
    accessed_at: str
    outcome: SourceFetchOutcome
    final_url: str | None = None
    http_status: int | None = None
    content_type: str | None = None
    response_content_hash: str | None = None
    extracted_content_hash: str | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class TripUpdateStage:
    trip: TripRecord
    previous_revision_id: str
    workflow_stage_id: str
    status: StageStatus
    input_hash: str


@dataclass(frozen=True)
class TripUpdateResult:
    trip: TripRecord
    outcome: TripUpdateOutcome
    previous_revision_number: int | None = None

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
class WorkingReviewState:
    status: WorkingReviewStatus
    based_on_revision_number: int
    previous_revision_number: int | None
    reason: str | None


@dataclass(frozen=True)
class SourceRecord:
    source_record_id: str
    category: ResearchCategory
    url: str
    title: str
    publisher: str
    retrieved_at: str
    content_hash: str
    locator: str
    evidence_summary: str
    published_at: str | None = None

    @property
    def source_locator(self) -> str:
        return f"{self.publisher}: {self.locator}"


@dataclass(frozen=True)
class ResearchClaim:
    claim_id: str
    category: ResearchCategory
    statement: str
    evidence_status: EvidenceStatus
    recheck_date: str | None
    sources: tuple[SourceRecord, ...]
    stale: bool = False


@dataclass(frozen=True)
class RouteSegment:
    route_segment_id: str
    origin: str
    destination: str
    status: RouteSegmentStatus
    created_at: str
    confirmed_at: str | None = None


@dataclass(frozen=True)
class ContentAngleOption:
    angle_id: str
    viewer_question: str
    available_evidence: tuple[str, ...]
    commercial_relevance: str
    risks: str
    missing_information: tuple[str, ...]
    source: ContentAngleSource
    status: ContentAngleStatus
    evidence_support: EvidenceSupportLevel


@dataclass(frozen=True)
class ContentAnglePropositionResult:
    trip: TripRecord
    options: tuple[ContentAngleOption, ...]


@dataclass(frozen=True)
class ContentAngleApprovalResult:
    trip: TripRecord
    angle: ContentAngleOption


@dataclass(frozen=True)
class AngleResearchStage:
    trip: TripRecord
    angle_id: str
    workflow_stage_id: str
    status: StageStatus
    input_hash: str


@dataclass(frozen=True)
class NarrationStage:
    trip: TripRecord
    angle_id: str
    workflow_stage_id: str
    status: StageStatus
    input_hash: str


@dataclass(frozen=True)
class AngleResearchResult:
    trip: TripRecord
    angle: ContentAngleOption
    outcome: AngleResearchOutcome
    claim: ResearchClaim | None

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
class BaselineResearchStage:
    trip: TripRecord
    workflow_stage_id: str
    status: StageStatus
    input_hash: str
    completed_categories: tuple[ResearchCategory, ...]


@dataclass(frozen=True)
class BaselineResearchResult:
    trip: TripRecord
    outcome: BaselineResearchOutcome
    claims: tuple[ResearchClaim, ...]

    @property
    def trip_id(self) -> str:
        return self.trip.trip_id

    @property
    def name(self) -> str:
        return self.trip.name

    @property
    def revision_number(self) -> int:
        return self.trip.revision_number

    @property
    def missing_categories(self) -> tuple[ResearchCategory, ...]:
        return tuple(
            claim.category
            for claim in self.claims
            if claim.evidence_status is EvidenceStatus.UNKNOWN
        )


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


@dataclass(frozen=True)
class DayIntensity:
    day_number: int
    rating: int | None


@dataclass(frozen=True)
class NarrationSection:
    key: str
    title: str
    body: str


@dataclass(frozen=True)
class NarrationResult:
    trip: TripRecord
    angle: ContentAngleOption
    outcome: NarrationOutcome
    sections: tuple[NarrationSection, ...]
    word_count: int
    estimated_minutes: float
    overall_intensity: int | None
    day_intensities: tuple[DayIntensity, ...]
    warnings: tuple[str, ...]

    @property
    def trip_id(self) -> str:
        return self.trip.trip_id

    @property
    def name(self) -> str:
        return self.trip.name

    @property
    def revision_number(self) -> int:
        return self.trip.revision_number

    @property
    def full_text(self) -> str:
        return "\n\n".join(
            f"## {section.title}\n\n{section.body}" for section in self.sections
        )


@dataclass(frozen=True)
class ValidationFinding:
    finding_id: str
    code: str
    severity: FindingSeverity
    message: str
    locator: str


@dataclass(frozen=True)
class ValidationAcknowledgment:
    finding_id: str
    approver: str
    acknowledged_at: str
    draft_signature: str


@dataclass(frozen=True)
class ValidationReport:
    trip: TripRecord
    draft_signature: str
    findings: tuple[ValidationFinding, ...]
    acknowledgments: tuple[ValidationAcknowledgment, ...]
    quality_score: int
    export_blocked: bool

    @property
    def trip_id(self) -> str:
        return self.trip.trip_id

    @property
    def name(self) -> str:
        return self.trip.name

    @property
    def acknowledged_ids(self) -> frozenset[str]:
        return frozenset(a.finding_id for a in self.acknowledgments)

    @property
    def blocking_findings(self) -> tuple[ValidationFinding, ...]:
        return tuple(f for f in self.findings if f.severity is FindingSeverity.BLOCKING)

    @property
    def unacknowledged_warnings(self) -> tuple[ValidationFinding, ...]:
        acknowledged = self.acknowledged_ids
        return tuple(
            f
            for f in self.findings
            if f.severity is FindingSeverity.WARNING
            and f.finding_id not in acknowledged
        )


@dataclass(frozen=True)
class EditorialPackageVersion:
    trip_id: str
    version_number: int
    itinerary_revision_id: str
    angle_id: str
    narration_signature: str
    quality_score: int
    export_blocked: bool
    content_hash: str
    submitted_at: str
    youtube_packaging_signature: str | None = None
    production_brief_signature: str | None = None

    @property
    def version_label(self) -> str:
        return f"v{self.version_number}"


@dataclass(frozen=True)
class VersionApproval:
    trip_id: str
    version_number: int
    component: VersionComponent
    approver: str
    approved_at: str
    content_integrity_reference: str


@dataclass(frozen=True)
class ComponentStatus:
    component: VersionComponent
    validity: ComponentValidity
    approval: VersionApproval | None


@dataclass(frozen=True)
class VersionStatus:
    trip: TripRecord
    version: EditorialPackageVersion
    components: tuple[ComponentStatus, ...]

    def status_for(self, component: VersionComponent) -> ComponentStatus:
        return next(c for c in self.components if c.component == component)


@dataclass(frozen=True)
class TitleOption:
    style: TitleStyle
    text: str


@dataclass(frozen=True)
class ChapterMarker:
    title: str
    timestamp_seconds: int

    @property
    def timestamp_label(self) -> str:
        minutes, seconds = divmod(self.timestamp_seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"


@dataclass(frozen=True)
class ThumbnailBrief:
    clear_idea: str
    destination_cues: tuple[str, ...]
    text_options: tuple[str, ...]


@dataclass(frozen=True)
class KeywordCandidate:
    keyword: str
    search_intent: str
    search_volume: str = "NOT_AVAILABLE"
    competition: str = "NOT_AVAILABLE"
    difficulty: str = "NOT_AVAILABLE"


@dataclass(frozen=True)
class ShortScript:
    title: str
    body: str


@dataclass(frozen=True)
class YoutubePackaging:
    titles: tuple[TitleOption, ...]
    description: str
    chapters: tuple[ChapterMarker, ...]
    thumbnail_brief: ThumbnailBrief
    keywords: tuple[KeywordCandidate, ...]
    shorts: tuple[ShortScript, ...]


@dataclass(frozen=True)
class YoutubePackagingResult:
    trip: TripRecord
    angle: ContentAngleOption
    outcome: YoutubePackagingOutcome
    packaging: YoutubePackaging
    content_signature: str

    @property
    def trip_id(self) -> str:
        return self.trip.trip_id

    @property
    def name(self) -> str:
        return self.trip.name


@dataclass(frozen=True)
class SceneRequirement:
    section_key: str
    visual_meaning: str
    location: str | None
    on_screen_text: str | None


@dataclass(frozen=True)
class ProductionBrief:
    locked_narration: str
    scene_requirements: tuple[SceneRequirement, ...]
    route_map_requirements: str
    brand_direction: str
    restrictions: tuple[str, ...]
    rights_and_ai_disclosure: str
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ProductionBriefResult:
    trip: TripRecord
    outcome: ProductionBriefOutcome
    brief: ProductionBrief
    content_signature: str

    @property
    def trip_id(self) -> str:
        return self.trip.trip_id

    @property
    def name(self) -> str:
        return self.trip.name
