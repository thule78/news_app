# URL Ingestion and Itinerary Updates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add audited HTTP/HTTPS itinerary ingestion and immutable Trip updates without changing the existing sanitization and normalization boundary.

**Architecture:** Standard-library retrieval and deterministic HTML extraction produce an `ItinerarySource`. The existing Trip workflow persists that source as an immutable revision, while SQLite workflow stages and atomic artifact publication make changed updates resumable. URL and pasted sources then use the existing explicit `trip process` command.

**Tech Stack:** Python 3.11 standard library (`urllib`, `html.parser`, `sqlite3`, `unittest`, `http.server`), SQLite, JSON/text artifacts.

---

## Implementation Baseline

Before Task 1, record the fixed point:

```bash
git rev-parse HEAD
```

Expected: the commit containing this implementation plan. Use that commit as the fixed point for final `$code-review`.

Do not stage or modify unrelated parent-worktree files, the existing `.env.example` deletion, `.DS_Store`, `.scratch/`, or other untracked project documents.

## File Structure

### Create

- `src/aa_content/url_retrieval.py` — URL validation, bounded HTTP retrieval, response decoding, and stable retrieval errors.
- `src/aa_content/html_extraction.py` — deterministic semantic HTML-to-itinerary extraction.
- `tests/http_fixture.py` — reusable local HTTP server for subprocess acceptance tests.
- `tests/test_schema_migration.py` — version-3 to version-4 migration coverage.
- `tests/test_url_retrieval.py` — retrieval validation, redirect, response limit, and content-type tests.
- `tests/test_html_extraction.py` — semantic-root and filtering tests.
- `tests/test_cli_url_ingestion.py` — URL create/update, failure, audit, preservation, and recovery acceptance tests.

### Modify

- `src/aa_content/models.py` — source, fetch, update-stage, and update-result domain records.
- `src/aa_content/persistence.py` — schema version 4, migration, fetch audit, and immutable update transactions.
- `src/aa_content/artifacts.py` — source-aware revision metadata, source-fetch provenance, and working review status.
- `src/aa_content/trip_workflow.py` — source acquisition, idempotent URL creation, and update orchestration.
- `src/aa_content/cli.py` — `--url` create option and new `trip update` command.
- `tests/test_cli_workspace.py` — fresh schema assertions and pasted-source regression coverage.
- `tests/test_cli_itinerary_processing.py` — confirm URL-backed revisions use the unchanged processing path.

## Domain Contracts

Add these types to `models.py`; keep network-only response types inside `url_retrieval.py`.

```python
class ItinerarySourceKind(StrEnum):
    PASTED_TEXT = "PASTED_TEXT"
    URL = "URL"


class SourceFetchOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class TripUpdateOutcome(StrEnum):
    UNCHANGED = "unchanged"
    UPDATED = "updated"
    RESUMED = "resumed"
    REGENERATED = "regenerated"


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
class ItinerarySource:
    kind: ItinerarySourceKind
    text: str
    source_fetch: SourceFetchRecord | None = None


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
    source_fetch: SourceFetchRecord | None = None
```

Use exact source text equality after matching hashes. Hashes alone must not decide revision equality.

### Task 1: Add Schema Version 4 and Safe Migration

**Files:**
- Modify: `src/aa_content/persistence.py:26-245`
- Modify: `tests/test_cli_workspace.py:42-69`
- Create: `tests/test_schema_migration.py`

- [ ] **Step 1: Write the failing fresh-schema assertions**

Extend `test_operator_can_initialize_shared_workspace`:

```python
with sqlite3.connect(workspace / "aa_content.db") as connection:
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }

self.assertEqual(version, 4)
self.assertTrue(
    {"source_fetches", "working_review_state"}.issubset(tables)
)
```

- [ ] **Step 2: Write the failing version-3 migration test**

In `tests/test_schema_migration.py`, create a temporary SQLite database containing minimal legacy `trips`, `itinerary_revisions`, and `claims` tables, one linked Trip/revision/Claim, and `PRAGMA user_version = 3`. Then call:

```python
WorkspaceRepository(workspace).ensure_schema()
```

Assert:

```python
self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 4)
self.assertEqual(
    connection.execute(
        "SELECT original_text FROM itinerary_revisions"
    ).fetchone()[0],
    "Day 1: Walk from Magome to Tsumago.",
)
self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
self.assertEqual(
    connection.execute(
        """
        SELECT status, based_on_revision_id, previous_revision_id
        FROM working_review_state
        """
    ).fetchone(),
    ("CURRENT", "irv_existing", None),
)
connection.execute(
    """
    INSERT INTO itinerary_revisions (
        itinerary_revision_id, trip_id, revision_number, source_kind,
        original_text, content_hash, created_at
    ) VALUES ('irv_url', 'trp_existing', 2, 'URL', 'Changed', 'hash2', 'now')
    """
)
```

- [ ] **Step 3: Run the focused tests to verify RED**

Run:

```bash
python3 -m unittest tests.test_schema_migration tests.test_cli_workspace.WorkspaceCliTests.test_operator_can_initialize_shared_workspace -v
```

Expected: FAIL because schema version is `3` and the two new tables do not exist.

- [ ] **Step 4: Implement the version-4 schema**

In `persistence.py`:

```python
SCHEMA_VERSION = 4
```

Change the revision constraint to:

```sql
source_kind TEXT NOT NULL
    CHECK (source_kind IN ('PASTED_TEXT', 'URL'))
```

Add:

```sql
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

PRAGMA user_version = 4;
```

- [ ] **Step 5: Implement explicit schema preparation**

Replace blind `executescript(SCHEMA)` calls with `_prepare_schema()`.

```python
def _prepare_schema(self) -> None:
    connection = sqlite3.connect(self.database_path)
    try:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version == 0:
            connection.executescript(SCHEMA)
        elif version == 3:
            self._migrate_v3_to_v4(connection)
        elif version == SCHEMA_VERSION:
            connection.executescript(SCHEMA)
        else:
            raise RuntimeError(
                f"Unsupported workspace schema version: {version}"
            )
    finally:
        connection.close()
```

`initialize_database()` and `ensure_schema()` call `_prepare_schema()` before opening their normal foreign-key-enabled connection.

- [ ] **Step 6: Implement the migration transaction**

With foreign keys disabled before `BEGIN EXCLUSIVE`:

```sql
CREATE TABLE itinerary_revisions_v4 (... expanded source_kind check ...);
INSERT INTO itinerary_revisions_v4 (...) SELECT ... FROM itinerary_revisions;
DROP TABLE itinerary_revisions;
ALTER TABLE itinerary_revisions_v4 RENAME TO itinerary_revisions;
```

Then create the two new tables, backfill:

```sql
INSERT INTO working_review_state (
    trip_id, status, based_on_revision_id,
    previous_revision_id, reason, updated_at
)
SELECT
    trip_id, 'CURRENT', current_itinerary_revision_id,
    NULL, NULL, created_at
FROM trips
WHERE current_itinerary_revision_id IS NOT NULL;
```

Set version 4 and commit. Re-enable foreign keys and run `PRAGMA foreign_key_check`; raise and leave an actionable error if violations exist.

- [ ] **Step 7: Run focused tests to verify GREEN**

Run the Step 3 command.

Expected: PASS.

- [ ] **Step 8: Run existing workspace tests**

Run:

```bash
python3 -m unittest tests.test_cli_workspace -v
```

Expected: all current workspace tests PASS.

- [ ] **Step 9: Commit**

```bash
git add src/aa_content/persistence.py tests/test_schema_migration.py tests/test_cli_workspace.py
git commit -m "Add URL ingestion schema migration"
```

### Task 2: Add Bounded URL Retrieval

**Files:**
- Create: `src/aa_content/url_retrieval.py`
- Create: `tests/http_fixture.py`
- Create: `tests/test_url_retrieval.py`

- [ ] **Step 1: Create the local HTTP fixture**

Implement `serve_routes(routes)` as a context manager. Bind `ThreadingHTTPServer` to `127.0.0.1` and port `0`, run it in a daemon thread, and always call `shutdown()`, `server_close()`, and `thread.join()` in `finally`.

Each route fixture supplies:

```python
{
    "/trip": (200, {"Content-Type": "text/html; charset=utf-8"}, b"..."),
    "/failure": (503, {"Content-Type": "text/plain"}, b"unavailable"),
}
```

Suppress handler request logging so tests remain clean.

- [ ] **Step 2: Write failing retrieval tests**

Cover:

```python
retriever = UrllibUrlRetriever(timeout_seconds=1, maximum_bytes=128)
page = retriever.retrieve(f"{server_url}/trip")
self.assertEqual(page.http_status, 200)
self.assertEqual(page.content_type, "text/html")
self.assertEqual(page.body_text, "<main>...</main>")
```

Also assert stable `UrlRetrievalError.code` values:

- `INVALID_URL` for `file:///tmp/input` and embedded credentials.
- `UNSAFE_REDIRECT` when an accessed HTTP(S) URL redirects outside the allowed
  HTTP(S), host, and no-credentials boundary.
- `HTTP_ERROR` for status `503`.
- `UNSUPPORTED_CONTENT_TYPE` for `application/pdf`.
- `RESPONSE_TOO_LARGE` when the body exceeds the configured limit.
- Redirect test retains requested URL and records final URL.
- Redirect tests reject a target that changes to a non-HTTP(S) scheme or
  contains URL user-info credentials as `UNSAFE_REDIRECT`.

- [ ] **Step 3: Run tests to verify RED**

Run:

```bash
python3 -m unittest tests.test_url_retrieval -v
```

Expected: import failure because `aa_content.url_retrieval` does not exist.

- [ ] **Step 4: Implement retrieval contracts**

Use:

```python
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_MAXIMUM_BYTES = 2 * 1024 * 1024
SUPPORTED_CONTENT_TYPES = frozenset({"text/html", "text/plain"})


@dataclass(frozen=True)
class RetrievedPage:
    requested_url: str
    final_url: str
    accessed_at: str
    http_status: int
    content_type: str
    body_text: str
    response_content_hash: str


class UrlRetrievalError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        requested_url: str,
        final_url: str | None = None,
        http_status: int | None = None,
        content_type: str | None = None,
    ) -> None:
        ...


class UrlRetriever(Protocol):
    def retrieve(self, url: str) -> RetrievedPage: ...
```

- [ ] **Step 5: Implement URL validation and adapter**

Validation:

```python
parts = urllib.parse.urlsplit(url.strip())
if parts.scheme not in {"http", "https"} or not parts.hostname:
    raise UrlRetrievalError("INVALID_URL", ...)
if parts.username is not None or parts.password is not None:
    raise UrlRetrievalError("INVALID_URL", ...)
requested_url = urllib.parse.urlunsplit(parts._replace(fragment=""))
```

Retrieval:

```python
request = urllib.request.Request(
    requested_url,
    headers={"User-Agent": "AdventureAsiaContent/1.0"},
)
with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
    body = response.read(self.maximum_bytes + 1)
```

Use a small `urllib.request.HTTPRedirectHandler` subclass that validates every
redirect destination with the same scheme, host, and credential rules before
following it. Revalidate `response.geturl()` after `urlopen()` as defense in
depth. Allow `UrlRetrievalError` raised by redirect validation to pass through
unchanged. A rejected redirect uses `UNSAFE_REDIRECT`, because network access
already occurred; only invalid requested input uses `INVALID_URL`.

Check size before decoding. Use `response.headers.get_content_type()` and `get_content_charset()`. Decode with a valid declared charset; otherwise decode UTF-8 with replacement. Convert `HTTPError`, `URLError`, and `TimeoutError` to safe stable errors without reading or including response bodies.

- [ ] **Step 6: Run focused tests to verify GREEN**

Run:

```bash
python3 -m unittest tests.test_url_retrieval -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/aa_content/url_retrieval.py tests/http_fixture.py tests/test_url_retrieval.py
git commit -m "Add bounded itinerary URL retrieval"
```

### Task 3: Add Deterministic HTML Extraction

**Files:**
- Create: `src/aa_content/html_extraction.py`
- Create: `tests/test_html_extraction.py`

- [ ] **Step 1: Write failing semantic extraction tests**

Use a fixture containing:

```html
<header>Book Adventure Asia today</header>
<nav>Home Trips About</nav>
<main>
  <h1>Nakasendo Trail</h1>
  <p>Day 1: Walk from Magome to Tsumago.</p>
  <ul><li>Walking time: 3–4 hours.</li><li>Breakfast included.</li></ul>
  <div class="newsletter"><p>Subscribe now</p></div>
  <p>Breakfast included.</p>
</main>
<aside>Related tours</aside>
<footer>Contact and legal links</footer>
```

Assert main itinerary blocks remain and header/nav/newsletter/aside/footer do not.

Add tests for:

- first usable `<main>` wins
- longest usable `<article>` is selected when no main exists
- filtered body fallback
- exact repeated CTA removal
- repeated itinerary facts remain
- empty/short result raises `ITINERARY_CONTENT_NOT_FOUND`
- `text/plain` normalization

- [ ] **Step 2: Run tests to verify RED**

Run:

```bash
python3 -m unittest tests.test_html_extraction -v
```

Expected: import failure because `aa_content.html_extraction` does not exist.

- [ ] **Step 3: Implement named extraction constants**

```python
MINIMUM_USABLE_CHARACTERS = 40
CONTENT_TAGS = frozenset(
    {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "dt", "dd", "th", "td"}
)
SKIP_TAGS = frozenset(
    {"script", "style", "noscript", "nav", "footer", "header",
     "aside", "form", "svg", "dialog"}
)
CHROME_TOKENS = frozenset(
    {"nav", "navigation", "menu", "breadcrumb", "cookie", "newsletter",
     "promo", "promotion", "related", "social", "share", "sidebar",
     "modal", "advert", "ads"}
)
CTA_PHRASES = frozenset(
    {"book now", "enquire now", "contact us", "sign up",
     "subscribe", "view all trips"}
)
```

Tests must reference behavior, not duplicate implementation logic.

- [ ] **Step 4: Implement parser and selection**

Create an internal `HTMLParser` subclass that:

- maintains skip depth
- tracks main/article/body candidate identity
- buffers content blocks
- ignores candidates inside semantic or class/id/role chrome
- decodes character/entity references through `HTMLParser`

Selection:

```python
main = next((item for item in mains if _is_usable(item)), None)
if main is not None:
    blocks = main
elif any(_is_usable(item) for item in articles):
    blocks = max(
        (item for item in articles if _is_usable(item)),
        key=_content_length,
    )
else:
    blocks = body_blocks
```

Normalize each block with `" ".join(text.split())`. Remove repeated blocks only when the normalized casefolded block contains a CTA phrase. Preserve all other duplicate blocks.

- [ ] **Step 5: Implement public extractor**

```python
@dataclass(frozen=True)
class ExtractedItinerary:
    text: str
    content_hash: str


class HtmlItineraryExtractor:
    def extract(self, page: RetrievedPage) -> ExtractedItinerary:
        if page.content_type == "text/plain":
            text = _normalize_plain_text(page.body_text)
        else:
            text = _extract_html(page.body_text)
        if len(text) < MINIMUM_USABLE_CHARACTERS:
            raise ItineraryExtractionError(
                "ITINERARY_CONTENT_NOT_FOUND",
                "No usable itinerary content was found at the URL.",
            )
        return ExtractedItinerary(
            text=text,
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )
```

- [ ] **Step 6: Run focused tests to verify GREEN**

Run:

```bash
python3 -m unittest tests.test_html_extraction -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/aa_content/html_extraction.py tests/test_html_extraction.py
git commit -m "Extract itinerary content from HTML"
```

### Task 4: Make Trip Creation Source-Aware

**Files:**
- Modify: `src/aa_content/models.py:1-80`
- Modify: `src/aa_content/persistence.py:353-675`
- Modify: `src/aa_content/artifacts.py:1-152`
- Modify: `src/aa_content/trip_workflow.py:1-83`
- Modify: `tests/test_cli_workspace.py:103-228`
- Create: `tests/test_cli_url_ingestion.py`

- [ ] **Step 1: Write failing pasted-source state assertions**

In the existing pasted-create test, assert:

```python
self.assertEqual(
    connection.execute(
        """
        SELECT status, based_on_revision_id, previous_revision_id
        FROM working_review_state
        """
    ).fetchone(),
    ("CURRENT", revision_id, None),
)
self.assertEqual(revision_metadata["source_kind"], "PASTED_TEXT")
self.assertFalse((revision_directory / "source-fetch.json").exists())
```

- [ ] **Step 2: Write failing URL-backed creation workflow test**

Use a fake `UrlRetriever` returning a fixed `RetrievedPage`; call the new workflow entry point directly:

```python
result = create_trip_from_url(
    workspace,
    "Nakasendo",
    "https://example.test/nakasendo",
    retriever=fake_retriever,
)
```

Assert one `URL` revision, one successful linked `source_fetches` row, extracted text in `original-itinerary.txt`, response metadata in `source-fetch.json`, and no raw HTML anywhere in the workspace.

- [ ] **Step 2a: Write failing repeated-access audit tests**

Cover every URL create branch that performs a real fetch:

- exact completed match → second successful fetch linked to the existing
  revision
- exact match with `--force` → second successful fetch linked to the existing
  revision
- different URL with the same normalized name and extracted text → reused Trip
  plus fetch linked to the existing revision
- same name/requested URL with changed extracted text → actionable conflict,
  successful fetch linked to the existing Trip with a null revision, and no
  duplicate Trip

- [ ] **Step 3: Run focused tests to verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_cli_workspace.WorkspaceCliTests.test_operator_can_create_trip_from_pasted_itinerary \
  tests.test_cli_url_ingestion.UrlIngestionCliTests.test_workflow_creates_url_backed_trip \
  -v
```

Expected: FAIL because source-aware models/workflow and review state initialization do not exist.

- [ ] **Step 4: Add the domain contracts**

Add `ItinerarySourceKind`, `SourceFetchOutcome`, `SourceFetchRecord`, and `ItinerarySource` from the Domain Contracts section to `models.py`.

Use a factory in `trip_workflow.py` for pasted input:

```python
source = ItinerarySource(
    kind=ItinerarySourceKind.PASTED_TEXT,
    text=itinerary,
)
```

- [ ] **Step 5: Extend creation persistence**

Change:

```python
start_trip_creation(name, slug, source, input_hash)
```

The transaction inserts:

- revision `source_kind = source.kind`
- `working_review_state = CURRENT`
- successful `source_fetches` when present
- the existing `trip_create` stage and attempt

Add:

```python
def record_failed_source_fetch(
    self,
    fetch: SourceFetchRecord,
    *,
    trip_id: str | None = None,
) -> None:
    ...

def record_successful_source_fetch(
    self,
    fetch: SourceFetchRecord,
    *,
    trip_id: str,
    itinerary_revision_id: str | None,
) -> None:
    ...
```

Bound `error_message` before insertion, for example `fetch.error_message[:500]`.
Every completed network access is appended exactly once, including reuse,
force, and rejected changed-content create branches.

- [ ] **Step 6: Make artifact publication source-aware**

Change:

```python
publish_trip_artifacts(workspace, trip, source)
```

Write revision metadata:

```python
revision_metadata = {
    "content_hash": sha256(source.text.encode("utf-8")).hexdigest(),
    "itinerary_revision_id": trip.itinerary_revision_id,
    "revision": f"r{trip.revision_number}",
    "source_kind": source.kind,
    "trip_id": trip.trip_id,
}
```

For URL sources, write `source-fetch.json` from a safe allowlist. Always initialize `working/review-status.json`:

```json
{
  "based_on_revision": "r1",
  "previous_revision": null,
  "reason": null,
  "status": "CURRENT"
}
```

- [ ] **Step 7: Implement idempotent URL creation**

Keep the existing creation identity: normalized name plus extracted source text.
Two different URLs yielding the same name/text must reuse the same Trip.

Before network retrieval, look only for a failed/in-progress URL creation with
the same normalized name and requested URL. If found, load its persisted
revision source and resume artifact publication; this protects downstream
failure recovery if the webpage changes before retry.

Otherwise retrieve and extract, then derive the normal name-plus-text creation
hash:

- exact completed match → record the new fetch linked to that revision, then
  return `REUSED`
- failed/in-progress exact match → resume persisted source
- `--force` exact match → record the new fetch linked to that revision, then
  regenerate from persisted source
- different URL with exact name/text → record the fetch linked to the reused
  revision

If the same normalized name and requested URL already belong to a completed
Trip but now yield different text, return an actionable exit-`2` error naming
the Trip ID and instructing the Operator to use `trip update`. Record the
successful access linked to that Trip with a null revision because the fetched
text did not become an Itinerary Revision. Do not create a second Trip. On
retrieval/extraction failure, persist a failed fetch audit and create no Trip.

- [ ] **Step 8: Run focused and existing creation tests**

Run:

```bash
python3 -m unittest tests.test_cli_workspace tests.test_cli_url_ingestion -v
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/aa_content/models.py src/aa_content/persistence.py src/aa_content/artifacts.py src/aa_content/trip_workflow.py tests/test_cli_workspace.py tests/test_cli_url_ingestion.py
git commit -m "Create Trips from audited URL sources"
```

### Task 5: Add Immutable Itinerary Updates

**Files:**
- Modify: `src/aa_content/models.py`
- Modify: `src/aa_content/persistence.py`
- Modify: `src/aa_content/artifacts.py`
- Modify: `src/aa_content/trip_workflow.py`
- Modify: `src/aa_content/cli.py:15-119`
- Modify: `tests/test_cli_url_ingestion.py`

- [ ] **Step 1: Write the failing unchanged pasted-update test**

Create a Trip, then:

```python
result = run_cli(
    workspace,
    "trip",
    "update",
    "--trip-id",
    trip_id,
    stdin=original_itinerary,
)
```

Assert output contains `Itinerary unchanged`, revision count remains one, the current pointer remains `r1`, and working state remains `CURRENT`.

- [ ] **Step 2: Write the failing empty pasted-update test**

Run `trip update --trip-id ID` with empty/whitespace standard input. Assert exit
`2`, an instruction to paste itinerary text, and no new revision, stage, or
working-state change.

- [ ] **Step 3: Write the failing changed-update preservation test**

Before update, create:

```text
working/draft.md
v1/manifest.json
current-version.json -> v1
```

Run pasted update with changed text. Assert:

- `r1` row and files unchanged
- exactly one `r2` row and directory
- Trip current pointer is `r2`
- draft, `v1`, and `current-version.json` unchanged
- working state and `working/review-status.json` are `REVIEW_REQUIRED`
- reason is `ITINERARY_REVISION_CHANGED`
- `previous_revision_id` is `r1`

- [ ] **Step 4: Run update tests to verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_cli_url_ingestion.UrlIngestionCliTests.test_unchanged_pasted_update_reuses_revision \
  tests.test_cli_url_ingestion.UrlIngestionCliTests.test_empty_pasted_update_is_rejected \
  tests.test_cli_url_ingestion.UrlIngestionCliTests.test_changed_pasted_update_preserves_drafts_and_versions \
  -v
```

Expected: parser failure because `trip update` does not exist.

- [ ] **Step 5: Add update models and repository queries**

Add `TripUpdateOutcome`, `TripUpdateStage`, and `TripUpdateResult` from Domain Contracts.

Repository methods:

```python
def find_recoverable_trip_update(self, trip_id: str) -> TripUpdateStage | None: ...
def find_trip_update(
    self, trip_id: str, previous_revision_id: str, input_hash: str
) -> TripUpdateStage | None: ...
def start_trip_update(
    self, current: TripRecord, source: ItinerarySource, input_hash: str
) -> tuple[TripUpdateStage, StageAttempt]: ...
def complete_trip_update(
    self, stage: TripUpdateStage, attempt: StageAttempt
) -> None: ...
```

`start_trip_update`:

- lock with `BEGIN IMMEDIATE`
- re-read the current revision inside the transaction
- allocate `MAX(revision_number) + 1`
- insert new revision, optional fetch record, stage, and attempt
- do **not** move the Trip current pointer yet

`complete_trip_update` atomically:

- move the Trip pointer to the reserved revision
- set `working_review_state = REVIEW_REQUIRED`
- complete attempt and stage

- [ ] **Step 6: Implement update orchestration**

```python
def update_trip(
    workspace: Path,
    trip_id: str,
    source: ItinerarySource,
) -> TripUpdateResult:
    ...
```

Order:

1. validate initialized workspace and Trip
2. reject pasted source text when `not source.text.strip()` with
   `UserFacingError("Paste itinerary text through standard input.")`
3. resume any recoverable stage from persisted revision text before allocating
4. compare source hash and exact text with current revision
5. unchanged → record successful fetch if present and return
6. changed → start/reuse stage
7. publish the reserved revision using atomic artifacts
8. complete the database pointer/review-state transaction

On artifact failure, mark the attempt failed with `ARTIFACT_WRITE_FAILED` and tell the Operator to retry the same command.

- [ ] **Step 7: Extend retry helpers to update stages**

Generalize `start_retry`, `fail_attempt`, and completion result serialization to accept `TripUpdateStage`. Load the reserved revision source and original successful source-fetch provenance during recovery; do not retrieve the URL again.

- [ ] **Step 8: Add `trip update` CLI**

Parser:

```python
update_parser = trip_commands.add_parser(
    "update",
    help="Create a new Itinerary Revision when source content changed.",
)
update_parser.add_argument("--trip-id", required=True)
update_parser.add_argument("--url")
```

For this task, wire pasted text:

```python
source = ItinerarySource(
    kind=ItinerarySourceKind.PASTED_TEXT,
    text=sys.stdin.read(),
)
result = update_trip(options.workspace, options.trip_id, source)
```

Print result, Trip ID, and revision number.

- [ ] **Step 9: Run focused tests to verify GREEN**

Run the Step 4 command.

Expected: PASS.

- [ ] **Step 10: Run processing regression**

Run:

```bash
python3 -m unittest tests.test_cli_itinerary_processing -v
```

Expected: all Ticket 2 tests PASS.

- [ ] **Step 11: Commit**

```bash
git add src/aa_content/models.py src/aa_content/persistence.py src/aa_content/artifacts.py src/aa_content/trip_workflow.py src/aa_content/cli.py tests/test_cli_url_ingestion.py
git commit -m "Add immutable itinerary updates"
```

### Task 6: Wire URL CLI, Auditing, and Actionable Failures

**Files:**
- Modify: `src/aa_content/cli.py`
- Modify: `src/aa_content/trip_workflow.py`
- Modify: `src/aa_content/persistence.py`
- Modify: `tests/test_cli_url_ingestion.py`
- Modify: `tests/test_cli_itinerary_processing.py`

- [ ] **Step 1: Write the failing first-ingestion acceptance test**

Use `serve_routes()` with a real subprocess CLI call:

```python
result = run_cli(
    workspace,
    "trip",
    "create",
    "--name",
    "Nakasendo",
    "--url",
    f"{server_url}/trip",
)
```

Assert:

- output reports URL and `r1`
- nav/footer/marketing are absent from `original-itinerary.txt`
- requested/final URL and hashes exist in DB/artifacts
- full HTML is absent from all persisted files
- subsequent `trip process --trip-id` succeeds and produces the same normalized tables/artifacts as pasted input

- [ ] **Step 2: Write failing unchanged and changed URL update tests**

Unchanged re-ingestion must add a fetch audit but not a revision.

Changed re-ingestion must create only `r2`, preserve `r1`, working drafts, and version fixtures, and set `REVIEW_REQUIRED`.

- [ ] **Step 3: Write failing retrieval-failure and retry test**

Serve `503`, run URL create, and assert:

- exit `1`
- stderr contains `HTTP_ERROR`, status, and retry guidance
- stderr contains no response body
- failed fetch audit exists
- no Trip or revision exists

Change the route to `200`, retry, and assert exactly one Trip and one revision.

Also fail an update and assert its current revision and working files remain unchanged.

- [ ] **Step 4: Write failing invalid-URL and redirect-output tests**

Run URL create with `file:///tmp/itinerary` and a URL containing user-info.
Assert exit `2`, `INVALID_URL`, no fetch audit, and no Trip. Invalid input is
rejected before an access attempt, so it is not recorded as a failed fetch.

Serve an HTTP redirect to a valid HTTP itinerary. Assert exit `0` and that both
the requested URL and final URL appear in CLI output. Add a redirect-to-invalid
target case and assert exit `1`, `UNSAFE_REDIRECT`, one failed fetch audit, and
no Trip. Network access occurred before the redirect was rejected.

- [ ] **Step 5: Run acceptance tests to verify RED**

Run:

```bash
python3 -m unittest tests.test_cli_url_ingestion -v
```

Expected: URL CLI cases FAIL because `--url` is not wired.

- [ ] **Step 6: Wire source acquisition**

Add:

```python
def acquire_url_source(
    url: str,
    *,
    retriever: UrlRetriever | None = None,
    extractor: HtmlItineraryExtractor | None = None,
) -> ItinerarySource:
    ...
```

Construct one `SourceFetchRecord` per actual access. On success, include response and extracted hashes. On retrieval/extraction failure, construct a failed record and raise a workflow error carrying that safe record for persistence.

- [ ] **Step 7: Wire create/update URL options**

Create:

```python
create_parser.add_argument("--url")
```

When `--url` exists, never call `sys.stdin.read()`.

Route to:

```python
create_trip_from_url(...)
update_trip_from_url(...)
```

Without `--url`, preserve current pasted behavior.

- [ ] **Step 8: Map input and execution errors to exact CLI exits**

Convert requested-input `INVALID_URL` into `UserFacingError`, which the current
CLI boundary maps to exit `2`. Convert failures from an attempted access,
including `UNSAFE_REDIRECT`, or extraction into `StageExecutionError`, which
maps to exit `1` after its fetch audit is saved.

Keep this mapping explicit:

```python
if error.code == "INVALID_URL":
    raise UserFacingError(f"{error.code}: {error}") from error
raise StageExecutionError(f"{error.code}: {error}") from error
```

- [ ] **Step 9: Make errors actionable and safe**

Format examples:

```text
Error: HTTP_ERROR: URL returned HTTP 503. Retry when the page is available.
Error: RESPONSE_TOO_LARGE: URL exceeded the 2097152-byte limit.
Error: ITINERARY_CONTENT_NOT_FOUND: No usable itinerary content was found.
```

Do not include body text, headers, cookies, credentials, or `.env` values.

- [ ] **Step 10: Run URL acceptance tests to verify GREEN**

Run:

```bash
python3 -m unittest tests.test_cli_url_ingestion -v
```

Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add src/aa_content/cli.py src/aa_content/trip_workflow.py src/aa_content/persistence.py tests/test_cli_url_ingestion.py tests/test_cli_itinerary_processing.py
git commit -m "Expose URL itinerary ingestion in the CLI"
```

### Task 7: Prove Interrupted Update Recovery and Full Regression

**Files:**
- Modify: `tests/test_cli_url_ingestion.py`
- Modify production files only if the new recovery test exposes a defect

- [ ] **Step 1: Write the failing interrupted-publication recovery test**

Create `r1`, then force the same artifact failure pattern used by the existing Trip creation recovery test during a changed update. After the first failure, assert:

- reserved revision is `r2`
- current Trip pointer is still `r1`
- update stage/attempt is `FAILED`
- no `r3`

Repair the artifact path and retry the same command. Assert:

- output reports `resumed`
- current pointer becomes `r2`
- stage completes
- attempts are `[FAILED, COMPLETED]`
- revision numbers are exactly `[1, 2]`
- no additional network access occurs during URL-stage recovery

- [ ] **Step 2: Run recovery test to verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_cli_url_ingestion.UrlIngestionCliTests.test_interrupted_update_resumes_reserved_revision \
  -v
```

Expected: FAIL until recoverable update lookup runs before new acquisition/allocation.

- [ ] **Step 3: Implement the minimal recovery correction**

If needed, change update entry points to:

```python
recoverable = repository.find_recoverable_trip_update(trip_id)
if recoverable is not None:
    return _resume_trip_update(
        workspace,
        repository,
        recoverable,
    )
```

The resume path loads persisted revision text and its original source-fetch metadata, republishes artifacts, then completes the pointer transaction.

- [ ] **Step 4: Run focused recovery test to verify GREEN**

Run the Step 2 command.

Expected: PASS.

- [ ] **Step 5: Compile and run the complete suite**

Run:

```bash
python3 -m compileall -q src tests
python3 -m unittest discover -s tests -v
git diff --check
```

Expected: compile succeeds, every test passes, and `git diff --check` prints nothing.

- [ ] **Step 6: Run `$code-review` against the fixed point**

Use:

- fixed point: implementation-plan commit captured before Task 1
- specification: `tickets.md` Ticket 3 and `docs/superpowers/specs/2026-07-31-url-ingestion-itinerary-updates-design.md`
- standards: `project_context.md`, `CONTEXT.md`, ADRs 0001, 0002, 0007, 0008, 0010, 0011, and 0012

Dispatch the Standards and Spec reviewers in parallel as required by the skill. Fix every hard finding with a failing regression test first, then rerun the full suite.

- [ ] **Step 7: Commit review fixes, if any**

```bash
git add <only Ticket 3 files>
git commit -m "Resolve URL ingestion review findings"
```

If review produces no changes, do not create an empty commit.

- [ ] **Step 8: Final verification**

Run fresh:

```bash
python3 -m compileall -q src tests
python3 -m unittest discover -s tests -v
git diff --check
git status --short
```

Expected: all tests pass; only known unrelated dirty parent-worktree state remains.

## Completion Evidence

Before claiming Ticket 3 complete, report:

- exact commit range
- exact full-suite pass count
- migration test result
- first/unchanged/changed/failure/recovery acceptance results
- code-review aggregate
- confirmation that no dependency was added
- confirmation that `.env` handling was unchanged and `.env.example` was not restored
