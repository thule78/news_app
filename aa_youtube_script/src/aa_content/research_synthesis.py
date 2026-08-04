from __future__ import annotations

from datetime import date, timedelta

from aa_content.models import EvidenceStatus, ResearchCategory
from aa_content.research_providers import ResearchDocument

_OFFICIAL_HINTS = ("gov", "embassy", "tourism board", "official")

_RECHECK_DAYS: dict[ResearchCategory, int | None] = {
    ResearchCategory.ACCESS: 30,
    ResearchCategory.OFFICIAL_ADVISORY: 30,
    ResearchCategory.SEASONALITY: 90,
    ResearchCategory.CROWDS: 90,
    ResearchCategory.INDEPENDENT_TRANSPORT: 180,
    ResearchCategory.ROUTE_RULES: 180,
    ResearchCategory.SOLO_TRAVELLER: None,
    ResearchCategory.PRACTICAL_DEMANDS: None,
}

_ELEVATED_AUTHORITY_CATEGORIES = {
    ResearchCategory.ACCESS,
    ResearchCategory.OFFICIAL_ADVISORY,
}

_CATEGORY_LABELS = {
    ResearchCategory.ACCESS: "Access",
    ResearchCategory.ROUTE_RULES: "Route rules",
    ResearchCategory.SEASONALITY: "Seasonality",
    ResearchCategory.CROWDS: "Crowd levels",
    ResearchCategory.INDEPENDENT_TRANSPORT: "Independent transport",
    ResearchCategory.SOLO_TRAVELLER: "Solo-traveller conditions",
    ResearchCategory.OFFICIAL_ADVISORY: "Official advisory",
    ResearchCategory.PRACTICAL_DEMANDS: "Practical demands",
    ResearchCategory.ANGLE_SUPPORT: "Angle support",
}


def evidence_status_for(
    category: ResearchCategory, publishers: list[str]
) -> EvidenceStatus:
    """Authority is judged per Claim category, never by a single global rank."""
    if not publishers:
        return EvidenceStatus.UNKNOWN
    if category in _ELEVATED_AUTHORITY_CATEGORIES and any(
        _looks_official(publisher) for publisher in publishers
    ):
        return EvidenceStatus.VERIFIED
    if len(set(publishers)) >= 2:
        return EvidenceStatus.CORROBORATED
    return EvidenceStatus.INDICATIVE


def recheck_date_for(
    category: ResearchCategory, *, today: date | None = None
) -> str | None:
    days = _RECHECK_DAYS.get(category)
    if days is None:
        return None
    base = today or date.today()
    return (base + timedelta(days=days)).isoformat()


def claim_statement(
    category: ResearchCategory, topic: str, status: EvidenceStatus, source_count: int
) -> str:
    label = _CATEGORY_LABELS[category]
    if status is EvidenceStatus.UNKNOWN:
        return f"No current {label.lower()} information could be found for {topic}."
    source_word = "source" if source_count == 1 else "sources"
    return f"{label} for {topic} is supported by {source_count} {source_word}."


def paraphrase_evidence(
    category: ResearchCategory, document: ResearchDocument
) -> str:
    """A short, non-verbatim summary — never a copied paragraph from the page."""
    label = _CATEGORY_LABELS[category]
    return f"{document.publisher} discusses {label.lower()} relevant to the trip."


def category_label(category: ResearchCategory) -> str:
    return _CATEGORY_LABELS[category]


def _looks_official(publisher: str) -> bool:
    lowered = publisher.lower()
    return any(hint in lowered for hint in _OFFICIAL_HINTS)
