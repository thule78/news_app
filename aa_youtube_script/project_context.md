# Adventure Asia YouTube Content Generator

## Purpose

Build a local Python CLI that turns one Adventure Asia Trip into one evidence-backed Editorial Package for one faceless YouTube travel briefing. The target duration is 7–10 minutes, but useful shorter content is preferable to filler.

The generator stops at a vendor-neutral Production Brief. It does not create, publish, schedule, or analyze videos.

## Product principles

- AI drafts; humans approve.
- Unknown information stays explicitly unknown.
- Every factual narration Claim traces to Evidence, including itinerary-derived Claims.
- Adventure Asia judgment is labeled and comes from approved Editorial Notes.
- No Supplier Data may reach AI or exports.
- No Price Information may appear anywhere in the Editorial Package.
- Quality checks advise the Approver; only unsanitized Supplier Data creates an absolute Export Block.
- Neutral narration must make sense without depending on selected footage.

## Users and roles

- **Operator**: imports, researches, generates, and edits.
- **Approver**: approves controlled versions and acknowledges warnings.
- One person may hold both roles in the MVP, but approvals remain separate records.

## MVP operator flow

```text
ingest URL/text
→ detect and sanitize forbidden Supplier Data
→ normalize Itinerary Revision
→ run Baseline Research
→ propose up to three evidence-supported Content Angles
→ approve one generated or manager-supplied angle
→ run Angle Research
→ generate neutral narration and supporting outputs
→ display evidence, quality, and benchmark notes
→ submit immutable Editorial Package Version
→ approve/export vendor-neutral Production Brief
→ manually hand off to Pictory
```

Drafts always remain visible. Editing a controlled component moves affected output to `REVIEW_REQUIRED`; it never deletes or hides work.

## Core data model

- One Trip has one current Editorial Package.
- A Trip may have multiple immutable Itinerary Revisions.
- Mutable work lives in `working/`.
- `submit-review` creates immutable whole-package versions: `v1`, `v2`, `v3`.
- Each package version references its exact Itinerary Revision, Claims, Evidence, warnings, score, and approvals.
- One shared Research Library holds reusable Claims, Evidence, and human-confirmed Route Segments.
- Shared research may be reused only when geographic scope, route segment, conditions, and freshness match.
- Stale research is refreshed first; failed refresh remains visibly `STALE`.
- AI may propose shared Route Segment matches but cannot silently create or merge canonical segments.

## Evidence rules

Evidence statuses:

- `VERIFIED`: directly supported by an authoritative source.
- `CORROBORATED`: supported by multiple credible sources.
- `INDICATIVE`: anecdotal pattern that must be qualified.
- `UNVERIFIED`: cannot appear as factual narration.
- `UNKNOWN`: no usable Evidence found.

Compatible activity-duration estimates may become an honest range only when route, segment, scope, and conditions match. Different scopes create a Fact Conflict.

Source authority depends on Claim type:

- Current Itinerary Revision for included Trip Transport and product arrangements.
- Official transport operators for Independent Transport.
- Government sources for official advisories.
- Relevant official/local authorities for access, rules, and current conditions.
- Recent traveller reports only for qualified pattern discovery.

External Source Records store metadata, content hash, locator, and Adventure Asia’s own paraphrased Evidence summary. They do not archive full copyrighted webpages or copied paragraphs.

## Research scope

Baseline Research runs for every Trip:

- Current access and route rules.
- Season and crowd conditions.
- Relevant Independent Transport.
- Solo-traveller conditions.
- Government advisories.
- Major physical and practical constraints.

Angle Research runs only after angle approval and goes deeper on the chosen viewer question.

## Editorial rules

Always include:

- Decision-focused hook.
- Journey at a Glance.
- Route.
- Reality Check.
- Who It Suits / Who Should Avoid It.
- Adventure Asia Verdict.
- Controlled CTA.

Include only when useful and evidenced:

- Avoiding Crowds.
- Solo-Traveller Considerations.
- Accommodation.
- Signature Experiences.
- Adventure Asia Difference.

Traveller Fit uses condition-based self-assessment, never age-only eligibility or medical diagnosis. Daily Intensity Ratings and one overall Trip rating must explain duration, terrain, elevation, climate, remoteness, and consecutive active days.

The generator may use manager-supplied, public-safe Editorial Notes. Operational Product Promises require explicit scope and approval; vague notes are insufficient.

## Outputs

- Neutral narration.
- Neutral semantic scene plan.
- Route-map brief.
- On-screen text.
- Rights and AI-disclosure requirements.
- YouTube titles, description, chapters, and thumbnail brief.
- Two Shorts derived only from approved long-form Claims.
- Quality and benchmark notes.
- Claim/Evidence/source reports.
- Vendor-neutral Production Brief.
- Pictory manual-import files.

The generator does not select footage, decide licenses, prescribe tool-specific effects, or rewrite content for Pictory.

## Storage architecture

- Python local CLI.
- One shared workspace `aa_content.db` using Python’s built-in `sqlite3`.
- SQLite is the operational source of truth.
- Markdown, JSON, and CSV are readable review/export formats.
- Trip folder name: `{trip-slug}--{trip_id}`.
- Manual edits occur only under `working/` and enter SQLite through explicit `import-edits`.
- Completed workflow stages save atomically and resume idempotently; retries do not duplicate records.

Suggested workspace shape:

```text
aa_content.db
research-library/
outputs/
  {trip-slug}--{trip_id}/
    source/
      r1/
      r2/
    working/
    v1/
    v2/
    current-version.json
```

## OpenAI boundary

- Use the OpenAI API behind an internal provider interface.
- Retrieval and source capture happen before AI synthesis.
- AI synthesizes Claims only from stored Evidence.
- Script generation receives supported Claims, not unrestricted web access.
- Model and SDK selection must be verified against current official OpenAI documentation during implementation.

## Secrets

- API keys exist only in workspace-root `.env`.
- `.env` is excluded from Git and restricted to the local user.
- `.env.example` contains variable names without values.
- Secrets never enter SQLite, Trip folders, prompts, exports, or logs.
- Use a small built-in loader; no dependency is needed solely for `.env`.

## MVP exclusions

- Word/PDF ingestion.
- Supplier integrations.
- Video creation.
- Pictory API integration.
- Footage and license selection.
- Automatic publishing.
- Price content.
- YouTube planning, scheduling, analytics, and feedback optimization.
- Numeric SEO volume/difficulty metrics; unavailable metrics display `NOT_AVAILABLE`.

## MVP acceptance test

Use the Nakasendo–Kiso Valley Trip.

Success requires:

- URL or pasted-text ingestion.
- Sanitized and correctly normalized route/day structure.
- Current Baseline Research with traceable Sources.
- Up to three meaningful supported angles and manager selection.
- Angle Research for the approved angle.
- Original neutral narration with no generic filler.
- Clear activity time, daily/overall intensity, comfort, constraints, Reality Check, Traveller Fit, and verdict.
- Explicit Missing Information instead of invention.
- Advisory quality notes and Approver acknowledgment.
- Complete YouTube packaging, two Shorts, neutral scene plan, route brief, and Production Brief.
- Immutable `v1` snapshot in readable and structured formats.
- Manual Pictory handoff.

## Implementation order

1. Finalize product workflow and domain schema.
2. Define SQLite tables and version/file contracts.
3. Define OpenAI and retrieval interfaces.
4. Implement ingestion, sanitization, and normalization.
5. Implement research, Claim/Evidence, and freshness workflows.
6. Implement angle approval and script generation.
7. Implement quality notes, approvals, versioning, and exports.
8. Run the Nakasendo benchmark.

