from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import re
from urllib import error as urllib_error
from urllib import request as urllib_request


class UrlRetrievalError(Exception):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class UrlRetrievalResult:
    requested_url: str
    final_url: str
    http_status: int
    content_type: str
    raw_html: str
    extracted_text: str


def retrieve_itinerary_source(
    url: str, *, timeout: float = 30.0
) -> UrlRetrievalResult:
    """Fetch a page and extract its main itinerary content, excluding chrome."""
    if not url.strip().lower().startswith(("http://", "https://")):
        raise UrlRetrievalError("INVALID_URL", f"Not an http(s) URL: {url}")

    request = urllib_request.Request(url, headers={"User-Agent": "aa-content/1.0"})
    try:
        with urllib_request.urlopen(request, timeout=timeout) as response:
            final_url = response.geturl()
            http_status = response.status
            content_type = response.headers.get("Content-Type", "")
            raw_bytes = response.read()
    except urllib_error.HTTPError as error:
        raise UrlRetrievalError(
            "HTTP_ERROR", f"Server returned HTTP {error.code} for {url}"
        ) from error
    except urllib_error.URLError as error:
        raise UrlRetrievalError(
            "CONNECTION_ERROR", f"Could not reach {url}: {error.reason}"
        ) from error
    except TimeoutError as error:
        raise UrlRetrievalError("TIMEOUT", f"Timed out retrieving {url}") from error

    if "html" not in content_type.lower() and not raw_bytes.lstrip().startswith(
        b"<"
    ):
        raise UrlRetrievalError(
            "UNSUPPORTED_CONTENT_TYPE",
            "Unsupported content type for itinerary extraction: "
            f"{content_type or 'unknown'}",
        )

    html = raw_bytes.decode(_detect_encoding(content_type), errors="replace")
    extracted = extract_main_content(html)
    if not extracted.strip():
        raise UrlRetrievalError(
            "NO_CONTENT_EXTRACTED",
            f"No itinerary content could be extracted from {url}",
        )
    return UrlRetrievalResult(
        requested_url=url,
        final_url=final_url,
        http_status=http_status,
        content_type=content_type,
        raw_html=html,
        extracted_text=extracted,
    )


def extract_main_content(html: str) -> str:
    """Strip navigation/footer/marketing chrome, keeping the page's main content."""
    parser = _MainContentParser()
    parser.feed(html)
    main_text = parser.main_text
    return main_text if main_text.strip() else parser.body_text


def _detect_encoding(content_type: str) -> str:
    match = re.search(r"charset=([\w-]+)", content_type, re.IGNORECASE)
    return match.group(1) if match else "utf-8"


_SKIP_TAGS = {"script", "style", "nav", "header", "footer", "aside", "noscript", "form"}
_BLOCK_TAGS = {
    "p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr",
    "section", "article",
}
_SKIP_HINTS = (
    "nav", "menu", "footer", "header", "cookie", "newsletter", "advert",
    "banner", "social", "breadcrumb", "sidebar",
)


class _MainContentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._main_depth = 0
        self._main_lines: list[str] = []
        self._body_lines: list[str] = []
        self._main_buffer: list[str] = []
        self._body_buffer: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        hint_text = " ".join(
            filter(None, [attributes.get("class"), attributes.get("id")])
        ).lower()
        if tag in _SKIP_TAGS or any(hint in hint_text for hint in _SKIP_HINTS):
            self._skip_depth += 1
            return
        if tag in ("main", "article"):
            self._main_depth += 1
        if tag in _BLOCK_TAGS:
            self._flush_line()

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag in _BLOCK_TAGS:
            self._flush_line()

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag in _BLOCK_TAGS:
            self._flush_line()
        if tag in ("main", "article") and self._main_depth > 0:
            self._main_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        text = " ".join(data.split())
        if not text:
            return
        self._body_buffer.append(text)
        if self._main_depth > 0:
            self._main_buffer.append(text)

    def _flush_line(self) -> None:
        if self._body_buffer:
            self._body_lines.append(" ".join(self._body_buffer))
            self._body_buffer = []
        if self._main_buffer:
            self._main_lines.append(" ".join(self._main_buffer))
            self._main_buffer = []

    @property
    def main_text(self) -> str:
        self._flush_line()
        return "\n".join(line for line in self._main_lines if line)

    @property
    def body_text(self) -> str:
        self._flush_line()
        return "\n".join(line for line in self._body_lines if line)
