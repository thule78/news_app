from __future__ import annotations

import hashlib
import re

from aa_content.models import (
    SanitizationResult,
    SanitizationStatus,
    SupplierDataFinding,
)


SANITIZER_VERSION = "supplier-sanitizer-v2"


_CLAUSE_RULES = (
    (
        "CONTACT_DETAILS",
        re.compile(
            r"\b(?:(?:supplier|partner|guide|operator|vendor|driver|emergency)"
            r"\s+contact|contact)\s*:?\s*"
            r"(?:(?![;|]|\.(?:\s|$)).)+",
            re.IGNORECASE,
        ),
    ),
    (
        "COMMERCIAL_TERMS",
        re.compile(
            r"\b(?:net\s+rate|commission|commercial\s+terms?|contract\s+rate|"
            r"wholesale\s+rate|payment\s+terms?|mark-?up)\b"
            r"(?:(?![;|]|\.(?:\s|$)).)*",
            re.IGNORECASE,
        ),
    ),
    (
        "PRIVATE_REFERENCE",
        re.compile(
            r"\b(?:booking\s+(?:ref|reference)|confirmation\s+(?:code|number)|"
            r"supplier\s+reference|internal\s+reference)\b"
            r"(?:(?![;|]|\.(?:\s|$)).)*",
            re.IGNORECASE,
        ),
    ),
    (
        "OPERATIONAL_NOTE",
        re.compile(
            r"\b(?:(?:internal|operational|supplier|partner)\s+notes?|"
            r"(?:driver|guide|pickup)\s+details|rooming\s+list|"
            r"room\s+allocation)\b\s*:?\s*"
            r"(?:(?![;|]|\.(?:\s|$)).)*",
            re.IGNORECASE,
        ),
    ),
    (
        "SUPPLIER_IDENTITY",
        re.compile(
            r"\b(?:supplier|vendor|local\s+partner|ground\s+operator|operator|"
            r"guide|driver|partner)(?:\s+(?:name|identity))?\s*:\s*"
            r"(?:(?![;|]|\.(?:\s|$)).)+",
            re.IGNORECASE,
        ),
    ),
)
_FRAGMENT_RULES = (
    (
        "CONTACT_DETAILS",
        re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    ),
    (
        "CONTACT_DETAILS",
        re.compile(
            r"(?<!\w)(?:\+\d{1,3}[\s.-]?)?"
            r"(?:\(?\d{2,4}\)?[\s.-]?){2,}\d{3,4}(?!\w)"
        ),
    ),
    (
        "SUPPLIER_IDENTITY",
        re.compile(
            r"\b(?i:supplier|vendor|local\s+partner|ground\s+operator|partner|"
            r"guide|driver|operator)\s+"
            r"(?:[A-Z][\w&'-]*)(?:\s+[A-Z][\w&'-]*){1,4}\b"
        ),
    ),
    (
        "SUPPLIER_IDENTITY",
        re.compile(
            r"\b(?i:operated|supplied|managed|contracted)\s+by\s+"
            r"(?:[A-Z][\w&'-]*)(?:\s+[A-Z][\w&'-]*){1,4}\b"
        ),
    ),
)
_PLACEHOLDER_PATTERN = re.compile(r"\[SUPPLIER DATA REMOVED: [A-Z_]+\]")
_SENSITIVE_HEADINGS = (
    (
        "CONTACT_DETAILS",
        re.compile(
            r"\s*(?:(?:supplier|partner|guide|operator|vendor|driver|"
            r"emergency)\s+contact|contact)\s*:\s*",
            re.IGNORECASE,
        ),
    ),
    (
        "COMMERCIAL_TERMS",
        re.compile(
            r"\s*(?:net\s+rate|commission|commercial\s+terms?|contract\s+rate|"
            r"wholesale\s+rate|payment\s+terms?|mark-?up)\s*:\s*",
            re.IGNORECASE,
        ),
    ),
    (
        "PRIVATE_REFERENCE",
        re.compile(
            r"\s*(?:booking\s+(?:ref|reference)|confirmation\s+(?:code|number)|"
            r"supplier\s+reference|internal\s+reference)\s*:\s*",
            re.IGNORECASE,
        ),
    ),
    (
        "OPERATIONAL_NOTE",
        re.compile(
            r"\s*(?:(?:internal|operational|supplier|partner)\s+notes?|"
            r"(?:driver|guide|pickup)\s+details|rooming\s+list|"
            r"room\s+allocation)\s*:\s*",
            re.IGNORECASE,
        ),
    ),
    (
        "SUPPLIER_IDENTITY",
        re.compile(
            r"\s*(?:supplier|vendor|local\s+partner|ground\s+operator|operator|"
            r"guide|driver|partner)(?:\s+(?:name|identity))?\s*:\s*",
            re.IGNORECASE,
        ),
    ),
)


def sanitize_itinerary(
    itinerary_revision_id: str, original_text: str
) -> SanitizationResult:
    sanitized_lines: list[str] = []
    findings: list[SupplierDataFinding] = []
    pending_heading_category: str | None = None
    for line_number, line in enumerate(
        original_text.splitlines(keepends=True), start=1
    ):
        line_ending = "\n" if line.endswith("\n") else ""
        line_body = line.removesuffix(line_ending)
        stripped_line = line_body.strip()
        heading_category = _sensitive_heading_category(line_body)
        if heading_category is not None:
            sanitized_body = f"[SUPPLIER DATA REMOVED: {heading_category}]"
            removed_fragments = [(heading_category, line_body)]
            pending_heading_category = heading_category
        elif pending_heading_category is not None and not stripped_line:
            pending_heading_category = None
            sanitized_body = line_body
            removed_fragments = []
        elif (
            pending_heading_category is not None
            and not _starts_public_itinerary_content(stripped_line)
        ):
            sanitized_body, removed_fragments = _redact_line(line_body)
            if not removed_fragments:
                sanitized_body = (
                    f"[SUPPLIER DATA REMOVED: {pending_heading_category}]"
                )
                removed_fragments = [(pending_heading_category, line_body)]
        else:
            pending_heading_category = None
            sanitized_body, removed_fragments = _redact_line(line_body)
        for occurrence, (category, removed_text) in enumerate(
            removed_fragments, start=1
        ):
            finding_id = _stable_id(
                "sdf",
                itinerary_revision_id,
                str(line_number),
                str(occurrence),
                category,
                removed_text,
            )
            findings.append(
                SupplierDataFinding(
                    finding_id=finding_id,
                    category=category,
                    source_line=line_number,
                    matched_text_hash=hashlib.sha256(
                        removed_text.encode("utf-8")
                    ).hexdigest(),
                )
            )
        sanitized_lines.append(f"{sanitized_body}{line_ending}")

    status = (
        SanitizationStatus.REVIEW_REQUIRED
        if findings
        else SanitizationStatus.CLEAR
    )
    return SanitizationResult(
        sanitized_text="".join(sanitized_lines),
        status=status,
        findings=tuple(findings),
    )


def contains_possible_supplier_data(text: str) -> bool:
    without_placeholders = _PLACEHOLDER_PATTERN.sub("", text)
    return bool(
        sanitize_itinerary("scan_for_supplier_data", without_placeholders).findings
    )


def remove_supplier_placeholders(text: str) -> str:
    return _PLACEHOLDER_PATTERN.sub("", text)


def _sensitive_heading_category(line: str) -> str | None:
    for category, pattern in _SENSITIVE_HEADINGS:
        if pattern.fullmatch(line):
            return category
    return None


def _starts_public_itinerary_content(line: str) -> bool:
    return bool(
        re.match(
            r"(?:Day\s+\d+\s*:|Walk\b|Hike\b|Trek\b|Cycle\b|Transfer\b|"
            r"Visit\b|Kayak\b|Raft\b|Train\b|Bus\b|Stay\b|Overnight\b|"
            r"Breakfast\b|Lunch\b|Dinner\b|Accommodation\b|Route\b|Activity\b)",
            line,
            re.IGNORECASE,
        )
    )


def _redact_line(line: str) -> tuple[str, list[tuple[str, str]]]:
    redacted = line
    fragments: list[tuple[str, str]] = []
    tokens: dict[str, str] = {}
    for category, pattern in (*_CLAUSE_RULES, *_FRAGMENT_RULES):
        def replace(match: re.Match[str], category: str = category) -> str:
            token = f"__AA_REDACTION_{len(tokens)}__"
            fragments.append((category, match.group(0)))
            tokens[token] = f"[SUPPLIER DATA REMOVED: {category}]"
            return token

        redacted = pattern.sub(replace, redacted)
    for token, placeholder in tokens.items():
        redacted = redacted.replace(token, placeholder)
    return redacted, fragments


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:32]}"
