from __future__ import annotations

import hashlib
import re
import uuid

from aa_content.models import SanitizationResult, SanitizationStatus, SupplierDataFinding


_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\+?\d{1,4}(?:[\s.-]\d{2,4}){2,4}")
_NET_RATE_RE = re.compile(
    r"\b(?:net\s*rate|nett\s*rate|cost\s*price|commission|mark[\s-]?up)\b"
    r"[^.\n]*",
    re.IGNORECASE,
)
_SUPPLIER_CONTACT_RE = re.compile(
    r"\b(?:supplier|agent\s*code|internal\s*use\s*only|confidential|"
    r"do\s*not\s*share)\b[^.\n]*",
    re.IGNORECASE,
)

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("EMAIL", _EMAIL_RE),
    ("PHONE", _PHONE_RE),
    ("NET_RATE", _NET_RATE_RE),
    ("SUPPLIER_CONTACT", _SUPPLIER_CONTACT_RE),
)


def sanitize_itinerary(original_text: str) -> SanitizationResult:
    """Strip suspected Supplier Data before any content reaches the AI provider."""
    lines = original_text.splitlines(keepends=True)
    sanitized_lines: list[str] = []
    findings: list[SupplierDataFinding] = []

    for line_number, line in enumerate(lines, start=1):
        sanitized_line = line
        for category, pattern in _PATTERNS:
            sanitized_line, line_findings = _redact(
                sanitized_line, category, line_number
            )
            findings.extend(line_findings)
        sanitized_lines.append(sanitized_line)

    sanitized_text = "".join(sanitized_lines)
    status = (
        SanitizationStatus.REVIEW_REQUIRED
        if findings
        else SanitizationStatus.CLEAR
    )
    return SanitizationResult(
        sanitized_text=sanitized_text, status=status, findings=tuple(findings)
    )


def _redact(
    line: str, category: str, line_number: int
) -> tuple[str, list[SupplierDataFinding]]:
    findings: list[SupplierDataFinding] = []
    pattern = dict(_PATTERNS)[category]

    def replace(match: re.Match[str]) -> str:
        matched_text = match.group(0)
        findings.append(
            SupplierDataFinding(
                finding_id=f"sdf_{uuid.uuid4().hex}",
                category=category,
                source_line=line_number,
                matched_text_hash=hashlib.sha256(
                    matched_text.encode("utf-8")
                ).hexdigest(),
            )
        )
        return f"[SUPPLIER_DATA_REMOVED:{category}]"

    return pattern.sub(replace, line), findings
