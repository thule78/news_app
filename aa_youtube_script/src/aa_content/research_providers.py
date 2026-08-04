from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import re
from typing import Protocol
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from aa_content.retrieval import UrlRetrievalError, retrieve_itinerary_source


@dataclass(frozen=True)
class ResearchDocument:
    """A single retrieved page's paraphrase-ready content, never the raw copy."""

    url: str
    title: str
    publisher: str
    extracted_text: str
    published_at: str | None = None


class ResearchSourceProvider(Protocol):
    """Hides how candidate sources are found and fetched from the domain."""

    def find_sources(
        self, query: str, *, max_results: int = 2
    ) -> list[ResearchDocument]: ...


class WebResearchSourceProvider:
    """Searches the open web (DuckDuckGo HTML) and fetches each result via the
    same controlled extraction path used for URL ingestion. This is the only
    place Baseline Research is allowed to reach the open web from."""

    def __init__(self, *, timeout: float = 20.0) -> None:
        self._timeout = timeout

    def find_sources(
        self, query: str, *, max_results: int = 2
    ) -> list[ResearchDocument]:
        documents: list[ResearchDocument] = []
        for result in _duckduckgo_search(query, timeout=self._timeout):
            if len(documents) >= max_results:
                break
            try:
                page = retrieve_itinerary_source(result.url, timeout=self._timeout)
            except UrlRetrievalError:
                continue
            documents.append(
                ResearchDocument(
                    url=result.url,
                    title=result.title or _publisher_of(result.url),
                    publisher=_publisher_of(result.url),
                    extracted_text=page.extracted_text,
                )
            )
        return documents


class FakeResearchSourceProvider:
    """Deterministic, offline stand-in used by the default test suite.

    `overrides` maps a substring of the query to the exact documents to
    return (including an empty list, to exercise the UNKNOWN-status path).
    Any query not matched by an override falls back to two synthetic,
    distinct-publisher documents so corroboration logic has something to
    corroborate.
    """

    def __init__(
        self, overrides: dict[str, list[ResearchDocument]] | None = None
    ) -> None:
        self._overrides = overrides or {}

    def find_sources(
        self, query: str, *, max_results: int = 2
    ) -> list[ResearchDocument]:
        for key, documents in self._overrides.items():
            if key in query:
                return documents[:max_results]
        return [
            ResearchDocument(
                url=f"https://example-guide-{index}.test/{urllib_parse.quote(query)}",
                title=f"{query} — traveller notes",
                publisher=f"example-guide-{index}.test",
                extracted_text=(
                    f"Practical notes relevant to: {query}. Conditions are "
                    "generally stable for the current season."
                ),
            )
            for index in range(min(max_results, 2))
        ]


@dataclass(frozen=True)
class _SearchHit:
    url: str
    title: str


def _duckduckgo_search(query: str, *, timeout: float) -> list[_SearchHit]:
    url = "https://duckduckgo.com/html/?" + urllib_parse.urlencode({"q": query})
    request = urllib_request.Request(url, headers={"User-Agent": "aa-content/1.0"})
    with urllib_request.urlopen(request, timeout=timeout) as response:
        html = response.read().decode("utf-8", errors="replace")
    return _parse_duckduckgo_results(html)


def _parse_duckduckgo_results(html: str) -> list[_SearchHit]:
    parser = _DuckDuckGoResultParser()
    parser.feed(html)
    return parser.hits


class _DuckDuckGoResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hits: list[_SearchHit] = []
        self._in_result_link = False
        self._current_href: str | None = None
        self._current_title: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag != "a":
            return
        attributes = dict(attrs)
        classes = (attributes.get("class") or "").split()
        if "result__a" in classes:
            self._in_result_link = True
            self._current_href = _resolve_duckduckgo_href(attributes.get("href"))
            self._current_title = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_result_link:
            if self._current_href:
                self.hits.append(
                    _SearchHit(
                        url=self._current_href,
                        title=" ".join(self._current_title).strip(),
                    )
                )
            self._in_result_link = False
            self._current_href = None
            self._current_title = []

    def handle_data(self, data: str) -> None:
        if self._in_result_link:
            self._current_title.append(data.strip())


def _resolve_duckduckgo_href(href: str | None) -> str | None:
    if not href:
        return None
    if href.startswith("//duckduckgo.com/l/"):
        href = "https:" + href
    parsed = urllib_parse.urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        query = urllib_parse.parse_qs(parsed.query)
        target = query.get("uddg")
        if target:
            return urllib_parse.unquote(target[0])
        return None
    if href.startswith("http://") or href.startswith("https://"):
        return href
    return None


def _publisher_of(url: str) -> str:
    host = urllib_parse.urlparse(url).netloc
    return re.sub(r"^www\.", "", host) or url
