# Ticket 3: URL Ingestion and Itinerary Updates

**Date:** 2026-07-31  
**Status:** Approved in conversation; ready for implementation planning

## Goal

Allow an Operator to create or update a Trip from an HTTP/HTTPS itinerary page while preserving the same sanitization and normalization boundary used for pasted text.

Changed source content creates the next immutable Itinerary Revision. Unchanged content does not. Existing drafts and Editorial Package Versions remain intact and traceable to their original revision.

## Scope

### Included

- Create a Trip from a URL.
- Update an existing Trip from a URL or pasted text.
- Retrieve HTML with Python standard-library code.
- Extract itinerary content while excluding page chrome, repeated marketing, and unrelated content.
- Retain URL access metadata and content hashes without archiving the full webpage.
- Detect unchanged and changed extracted content.
- Create and publish immutable revision artifacts.
- Mark existing working content `REVIEW_REQUIRED` when the current revision changes.
- Make failed retrieval and interrupted artifact publication safely retryable.
- Test first ingestion, unchanged re-ingestion, changed re-ingestion, content filtering, and retrieval failure.

### Excluded

- JavaScript-rendered pages and browser automation.
- Authentication, cookies, paywalls, and robots bypasses.
- PDF, Word, image, or other document ingestion.
- General research-source capture; Ticket 4 owns that workflow.
- Automatic sanitization/normalization during `trip create` or `trip update`.
- Editorial Package Version creation or approval.
- Full-page HTML archives.
- New third-party dependencies.

## Product Flow

### Create from URL

```text
Operator runs trip create --name NAME --url URL
→ validate workspace and URL
→ retrieve page
→ extract itinerary-only text
→ save fetch audit metadata
→ create Trip and immutable r1
→ publish r1 source artifacts
→ Operator runs trip process --trip-id ID
→ existing sanitizer and normalizer process r1
```

Retrieval and extraction happen before a new Trip is inserted. A retrieval or extraction failure therefore cannot leave a duplicate or empty Trip.

### Update from URL

```text
Operator runs trip update --trip-id ID --url URL
→ validate Trip and URL
→ retrieve and extract
→ save fetch audit metadata
→ compare extracted-content hash with current revision
   → unchanged: retain current revision
   → changed: reserve next revision, publish it, move current pointer
→ if changed, mark existing working content REVIEW_REQUIRED
→ Operator runs trip process --trip-id ID
```

### Update from pasted text

```text
Operator runs trip update --trip-id ID
→ read pasted text from stdin
→ compare source-content hash
→ unchanged or changed path matches URL update
```

Pasted and URL input differ only in source acquisition. Both produce source text that enters the existing `trip process` sanitization and normalization workflow.

## CLI Contract

```bash
aa-content --workspace . trip create --name "Trip" --url "https://example.com/trip"
aa-content --workspace . trip update --trip-id TRIP_ID --url "https://example.com/trip"
```

Without `--url`, both commands read itinerary text from standard input.

When `--url` is present, the CLI does not read standard input. This prevents blocking and makes the source choice unambiguous.

Successful output includes:

- Trip ID
- current Itinerary Revision number
- result: `CREATED`, `UNCHANGED`, `UPDATED`, `RESUMED`, or `REGENERATED`
- requested URL and final URL for URL input

Failures use the existing CLI error boundary:

- exit `2` for invalid input or an unknown Trip
- exit `1` for retrieval, extraction, persistence, or artifact-stage failure

Error text identifies the cause and safe next action without exposing response bodies.

## Architecture

### Components

```text
CLI
└── Itinerary ingestion workflow
    ├── UrlRetriever interface
    │   └── urllib standard-library adapter
    ├── HtmlItineraryExtractor
    │   └── html.parser standard-library implementation
    ├── WorkspaceRepository
    │   └── SQLite revisions, fetch audit, workflow recovery
    ├── Artifact publisher
    │   └── immutable source/rN + mutable review-status artifact
    └── Existing trip process workflow
        └── sanitizer → normalizer → Claims/Evidence
```

`UrlRetriever` is an internal provider boundary. Network details do not leak into the domain workflow or extraction logic.

Suggested contracts:

```python
class UrlRetriever(Protocol):
    def retrieve(self, url: str) -> RetrievedPage: ...


class HtmlItineraryExtractor:
    def extract(self, page: RetrievedPage) -> ExtractedItinerary: ...
```

`RetrievedPage` carries the requested URL, final URL, access time, status, content type, body bytes, and response metadata. Body bytes exist only in memory.

`ExtractedItinerary` carries normalized plain text plus response and extracted-content hashes.

### Dependency Policy

Use only Python standard-library modules already available to the project:

- `urllib.request`
- `urllib.parse`
- `html.parser`
- existing `sqlite3`, hashing, JSON, and filesystem utilities

No library approval is required because no dependency is added.

## Retrieval Rules

- Accept only `http` and `https`.
- Reject missing hosts, embedded credentials, fragments-only input, and other schemes.
- Apply a finite timeout.
- Apply a maximum response size before decoding.
- Accept HTML and plain-text response content types.
- Record redirect destination as the final URL.
- Decode using the declared charset when valid, otherwise use a deterministic UTF-8 fallback with replacement.
- Convert transport, timeout, HTTP, size, content-type, and decoding/extraction failures into stable application error codes.
- Never log or persist response bodies.

Initial implementation constants should be explicit and testable. Recommended defaults:

- timeout: 20 seconds
- maximum response body: 2 MiB

## HTML Extraction Rules

Extraction is deterministic and conservative.

1. Parse with `HTMLParser`.
2. Remove non-content elements such as `script`, `style`, `noscript`, `nav`, `footer`, `header`, `aside`, `form`, `svg`, and dialogs.
3. Remove elements whose semantic role or class/id tokens identify menus, cookies, newsletters, promotions, related content, social/share controls, or page chrome.
4. Select the first usable `<main>` root. If absent, select the longest usable `<article>`. If neither exists, use filtered `<body>` content.
5. Emit readable blocks from headings, paragraphs, list items, definition lists, and table cells.
6. Preserve source order and list boundaries.
7. Normalize whitespace and blank lines.
8. Remove exact repeated promotional/CTA blocks while preserving repeated itinerary facts such as meals or accommodation.
9. Reject an empty or implausibly short result with `ITINERARY_CONTENT_NOT_FOUND`.

The extractor does not infer facts, summarize prose, or use AI. Its result remains subject to the existing Supplier Data sanitizer.

## Data Model

### `itinerary_revisions`

Extend `source_kind` to:

```text
PASTED_TEXT | URL
```

`original_text` means the exact plain-text source presented to sanitization:

- pasted input for `PASTED_TEXT`
- extracted itinerary text for `URL`

It never contains a full HTML page.

The existing `content_hash` remains the SHA-256 hash of `original_text`. Revision equality is based on this hash plus an exact-text comparison to protect against theoretical hash collisions.

### `source_fetches`

Add an append-only URL access audit table:

```text
source_fetch_id             TEXT PRIMARY KEY
trip_id                     TEXT NULL
itinerary_revision_id       TEXT NULL
requested_url               TEXT NOT NULL
final_url                   TEXT NULL
accessed_at                 TEXT NOT NULL
outcome                     SUCCESS | FAILED
http_status                 INTEGER NULL
content_type                TEXT NULL
response_content_hash       TEXT NULL
extracted_content_hash      TEXT NULL
error_code                  TEXT NULL
error_message               TEXT NULL
```

Rules:

- Successful create/update records become linked to the Trip and resolved revision.
- An unchanged update links to the existing current revision.
- A changed update links to the newly created revision.
- Failed create fetches may have no Trip or revision.
- Failed update fetches link to the existing Trip but not a new revision.
- `error_message` is bounded, actionable application text, never a response body.

### `working_review_state`

Add one mutable state row per Trip:

```text
trip_id                     TEXT PRIMARY KEY
status                      CURRENT | REVIEW_REQUIRED
based_on_revision_id        TEXT NOT NULL
previous_revision_id        TEXT NULL
reason                      TEXT NULL
updated_at                  TEXT NOT NULL
```

When a changed revision is published:

- preserve every existing file under `working/`
- set status to `REVIEW_REQUIRED`
- retain the previous revision ID
- bind the working state to the new current revision
- write matching readable metadata to `working/review-status.json`

The state indicates that drafts must be reviewed; it does not delete, hide, rewrite, or auto-approve them.

First Trip creation initializes the row as `CURRENT`, based on `r1`, with no
previous revision or review reason.

### Schema Migration

The current SQLite constraint permits only `PASTED_TEXT`, so Ticket 3 introduces schema version 4.

Migration sequence:

1. Open the local database exclusively for migration.
2. Disable foreign-key enforcement before the transaction.
3. Rebuild `itinerary_revisions` with the expanded constraint.
4. Copy all rows unchanged.
5. Add `source_fetches` and `working_review_state`.
6. Backfill each existing Trip that has a current revision as `CURRENT`, based
   on that revision, without creating a false review requirement.
7. Set `PRAGMA user_version = 4` and commit.
8. Re-enable foreign keys.
9. Run `PRAGMA foreign_key_check`; fail initialization if any violation exists.

Fresh workspaces receive the version-4 schema directly. Existing version-3 workspaces migrate idempotently. Unsupported future schema versions are rejected instead of modified.

## Revision Semantics

### First ingestion

- Create one Trip.
- Create revision `r1`.
- Set the Trip current pointer to `r1`.
- Publish `source/r1`.

### Unchanged ingestion

- Record the acquisition/fetch attempt.
- Compare against the current revision.
- Do not insert another revision.
- Do not change the current pointer.
- Do not change working review state.
- Return `UNCHANGED`.

### Changed ingestion

- Calculate `next_revision = max(revision_number) + 1`.
- Insert a new immutable revision.
- Publish `source/rN` using the existing staging-and-replace pattern.
- Update the Trip current pointer.
- Set working content to `REVIEW_REQUIRED`.
- Never modify prior revision rows or `source/rN` directories.

The transaction and artifact stage use a stable operation key derived from Trip ID, previous revision ID, source kind, and extracted-content hash.

If publication is interrupted after `rN` is reserved, retry resumes the same workflow stage and repairs `rN`; it must not allocate `rN+1`.

### Editorial Package preservation

The update workflow does not modify:

- existing `v1`, `v2`, or later directories
- `current-version.json`
- any current or future Editorial Package Version row
- any revision reference held by a package version

Ticket 3 tests preserve fixture package artifacts. Later package-version schema must keep an explicit foreign key to `itinerary_revision_id`.

## Artifact Contract

Each URL-backed revision stores:

```text
source/rN/
  original-itinerary.txt
  revision.json
  source-fetch.json
```

`original-itinerary.txt` contains extracted itinerary text, not HTML.

`revision.json` includes:

- Trip ID
- Itinerary Revision ID and number
- source kind
- source-content hash
- creation time

`source-fetch.json` includes:

- requested and final URLs
- access time
- HTTP status
- content type
- response and extracted-content hashes

It excludes response headers that may contain sensitive data, response bodies, and copied page paragraphs beyond the extracted itinerary source.

Pasted-text revisions need no `source-fetch.json`.

## Failure and Recovery

### Retrieval or extraction failure

- Persist a failed `source_fetches` audit row when the workspace database is available.
- Do not create or advance a Trip revision.
- Do not modify working drafts or package versions.
- Return a stable error code and retry guidance.

### Database failure

- Roll back the active transaction.
- Leave the prior current revision authoritative.
- Return a persistence error.

### Artifact publication failure

- Keep the workflow stage recoverable.
- Preserve prior artifact directories.
- Retry the same command using the stable operation key.
- Reuse the reserved Trip/revision rather than duplicating it.

### Safe create retry

URL retrieval occurs before Trip creation. Once source text exists, the current Trip-creation idempotency key of normalized name plus source text prevents duplicate Trips during downstream retries.

## Security and Privacy

- Do not send retrieved content to an AI provider during ingestion.
- Do not persist full HTML.
- Do not include response bodies in errors or logs.
- Do not forward cookies, credentials, or workspace secrets.
- Reject URL user-info credentials.
- Keep `.env` as the only secret file; Ticket 3 does not change secret handling.
- Run extracted content through Supplier Data sanitization before any later AI-bound stage.

## Test Strategy

Use `unittest` and a local in-process HTTP server. Tests do not depend on public internet access.

### CLI acceptance tests

1. **First URL ingestion**
   - Serve a page with main itinerary content plus nav, footer, related content, and repeated CTA copy.
   - Run `trip create --url`.
   - Assert one Trip, one URL revision, one successful fetch record, correct metadata, and filtered source artifact.
   - Run `trip process`.
   - Assert the same sanitizer/normalizer records and artifacts used by pasted text.

2. **Unchanged re-ingestion**
   - Update the Trip from the same extracted content.
   - Assert one revision remains, another fetch record exists, and result is `UNCHANGED`.

3. **Changed re-ingestion**
   - Change the served itinerary.
   - Seed representative `working/` and `v1/` files.
   - Run update.
   - Assert immutable `r1`, new `r2`, current pointer `r2`, preserved drafts/version files, and `REVIEW_REQUIRED`.

4. **Retrieval failure**
   - Serve HTTP failure or an unreachable local endpoint.
   - Assert actionable failure, a failed audit record, unchanged domain state, and no empty/duplicate Trip.
   - Retry after recovery and assert exactly one Trip and one new revision.

5. **Interrupted publication recovery**
   - Force artifact publication failure after revision reservation.
   - Retry.
   - Assert the same revision completes and no extra revision is allocated.

### Unit tests

- URL validation and redirect metadata.
- response size and content-type limits.
- semantic-root selection.
- chrome/marketing removal.
- preservation of legitimate repeated itinerary facts.
- empty extraction.
- schema migration from version 3 with existing related rows.

The implementation plan must pin the minimum usable-content threshold and the
chrome-token and CTA-deduplication vocabularies as named, directly tested
constants rather than leaving them as hidden heuristics.

## Acceptance Criteria Mapping

| Ticket requirement | Design coverage |
|---|---|
| URL uses same sanitization/normalization workflow | Shared `trip process` boundary |
| Exclude navigation/footer/marketing/unrelated content | Deterministic HTML extraction rules |
| Retain source URL/access metadata | `source_fetches` and `source-fetch.json` |
| Changed source creates immutable revision | Revision semantics and stable operation key |
| Earlier package versions retain original revision | Update workflow preservation contract |
| New revision marks working content for review | `working_review_state` and readable artifact |
| Failures actionable and resumable without duplicate Trip | Failure/recovery rules |
| Required tests | CLI acceptance and unit test strategy |

## Implementation Constraints

- Follow strict red-green-refactor TDD.
- Preserve current pasted-text behavior and CLI exit codes.
- Use atomic filesystem publication.
- Do not alter unrelated dirty files in the parent Git worktree.
- Add no third-party dependency.
