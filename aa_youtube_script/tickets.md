# Tickets: Adventure Asia YouTube Content Generator MVP

These tickets build the local evidence-backed Trip-to-Editorial-Package workflow defined in `.scratch/aa-youtube-content-generator/PRD.md`.

Work the **frontier**: any ticket whose blockers are all done. Tickets 10 and 11 may run in parallel after Ticket 9.

## 1. Create a resumable Trip workspace

**What to build:** Allow an Operator to initialize the local CLI, create a Trip from pasted itinerary text, and inspect durable source and workflow state. This slice establishes the application seam used by every later ticket.

**Blocked by:** None — can start immediately.

- [ ] The CLI initializes one shared SQLite-backed workspace without requiring a third-party database dependency.
- [ ] The CLI loads the OpenAI API key only from the local `.env` contract and fails clearly when required configuration is missing.
- [ ] Secret values never appear in logs, database records, Trip artifacts, or error reports.
- [ ] Creating a Trip assigns a stable Trip ID and readable slug.
- [ ] The original pasted itinerary is preserved as the first immutable Itinerary Revision.
- [ ] The Trip workspace and readable metadata exports are created consistently from persisted state.
- [ ] A completed workflow stage is recorded atomically.
- [ ] Repeating the same command reuses the completed result unless the Operator explicitly forces regeneration.
- [ ] Automated tests drive the workflow through the CLI-facing application seam and inspect external state rather than internal calls.

## 2. Sanitize and normalize an Itinerary Revision

**What to build:** Turn a pasted itinerary into an AI-safe Sanitized Itinerary and a reviewable normalized Trip while preserving unknowns, warnings, and source traceability.

**Blocked by:** 1. Create a resumable Trip workspace.

- [ ] Possible Supplier Data is detected before any itinerary content reaches the OpenAI provider.
- [ ] Flagged content is removed from the AI-bound Sanitized Itinerary while the original remains local.
- [ ] Processing continues with a prominent human-check warning.
- [ ] Unsanitized Supplier Data in AI-bound or exported content creates the only non-overridable Export Block.
- [ ] Normalization captures route, overnight stops, activities, accommodation, meals, Trip Transport, durations, and practical constraints when present.
- [ ] Missing values remain explicit Missing Information and are never filled through unsupported inference.
- [ ] Compatible duration estimates become an honest Estimated Duration only when scope, route, segment, and conditions match.
- [ ] Incompatible statements create a visible Fact Conflict.
- [ ] Every normalized Claim traces to the relevant location in the Itinerary Revision.
- [ ] OpenAI-specific request and response details remain behind the provider interface.
- [ ] Any proposed third-party dependency is presented for approval before use.

## 3. Add URL ingestion and itinerary updates

**What to build:** Allow an Operator to ingest a Trip from a webpage URL and later create new immutable Itinerary Revisions without losing historical package reproducibility.

**Blocked by:** 2. Sanitize and normalize an Itinerary Revision.

- [ ] A URL can be ingested through the same sanitization and normalization workflow as pasted text.
- [ ] Navigation, footer, repeated marketing copy, and unrelated page content are excluded from the itinerary source.
- [ ] Source URL and access metadata are retained for audit.
- [ ] A changed itinerary creates the next immutable Itinerary Revision rather than overwriting the current one.
- [ ] Earlier Editorial Package Versions continue to reference their original Itinerary Revision.
- [ ] A new Itinerary Revision moves affected working content to `REVIEW_REQUIRED` without deleting drafts.
- [ ] URL retrieval failures produce actionable errors and can resume without duplicating the Trip.
- [ ] Tests cover first ingestion, unchanged re-ingestion, changed re-ingestion, and retrieval failure.

## 4. Produce Baseline Research with traceable Evidence

**What to build:** Run standard current-information research for a normalized Trip and produce reusable Claims, Evidence, Source Records, freshness data, and a human-readable research brief before angle selection.

**Blocked by:** 2. Sanitize and normalize an Itinerary Revision.

- [ ] Baseline Research covers current access, route rules, seasonality, crowds, relevant Independent Transport, solo-traveller conditions, official advisories, and major practical demands.
- [ ] Retrieval completes and persists Source Records before AI Claim synthesis begins.
- [ ] Script-generation access to unrestricted web retrieval is impossible through the application workflow.
- [ ] Source Records retain URL, title, publisher, dates when available, category, content hash, locator, and Adventure Asia’s paraphrased Evidence summary.
- [ ] Full copyrighted webpages and copied paragraphs are not stored.
- [ ] Every external Claim links to one or more Evidence records.
- [ ] Evidence Status uses only `VERIFIED`, `CORROBORATED`, `INDICATIVE`, `UNVERIFIED`, or `UNKNOWN`.
- [ ] Source authority is evaluated by Claim type rather than a global ranking.
- [ ] Included Trip Transport remains governed by the Itinerary Revision; official operators govern Independent Transport.
- [ ] Time-sensitive Claims receive Recheck Dates.
- [ ] Research output includes human-readable source, Claim, Missing Information, and warning reports.
- [ ] Interrupted or failed research resumes without repeating successful retrieval or creating duplicate Claims.

## 5. Reuse Research Library Evidence across Trips

**What to build:** Allow multiple Trips to reuse relevant, fresh research through Operator-confirmed Route Segments without silently applying evidence to the wrong route or conditions.

**Blocked by:** 4. Produce Baseline Research with traceable Evidence.

- [ ] AI may propose that two Trips share a Route Segment.
- [ ] No reusable Route Segment becomes canonical until an Operator confirms it.
- [ ] Confirmed Route Segments receive stable identities.
- [ ] Claims and Evidence may be referenced by multiple Trips without copying source records.
- [ ] Reuse requires matching geography or Route Segment, Claim scope, conditions, and freshness.
- [ ] Trip-specific accommodation, transfer, inclusion, and Product Promise Claims are not reused as general route research.
- [ ] A passed Recheck Date triggers refresh before reuse.
- [ ] Successful refresh creates new Evidence history without destroying the old record.
- [ ] Failed refresh produces a prominent Stale Claim warning and remains reviewable.
- [ ] Tests use at least two Trips with one shared segment and distinct non-shared segments.

## 6. Approve a Content Angle and run Angle Research

**What to build:** Present evidence-supported editorial options, let the Approver select or supply one Content Angle, then research that angle deeply enough to support script generation.

**Blocked by:** 4. Produce Baseline Research with traceable Evidence.

- [ ] The generator proposes up to three materially different Content Angles.
- [ ] It never invents weak options solely to reach three.
- [ ] Each option states its viewer question, available Evidence, commercial relevance, risks, and Missing Information.
- [ ] The Approver may select one proposed Content Angle.
- [ ] The Approver may enter a custom Content Angle.
- [ ] A custom angle receives an Evidence support check before generation.
- [ ] The system does not silently reshape a custom angle into a different promise.
- [ ] Angle Research starts only after angle approval.
- [ ] Angle Research persists additional Claims, Evidence, Source Records, and warnings through the same research rules.
- [ ] The approved Content Angle binds to the current Trip and Itinerary Revision.
- [ ] Tests cover generated selection, custom selection, unsupported custom framing, and fewer-than-three proposals.

## 7. Generate evidence-traceable neutral narration

**What to build:** Generate one useful, brand-consistent long-form narration draft from the approved Content Angle, supported Claims, Itinerary Revision, and optional Editorial Notes.

**Blocked by:** 6. Approve a Content Angle and run Angle Research.

- [ ] Narration targets 7–10 minutes using configured narration speed and planned pauses.
- [ ] Shorter useful narration is allowed and warned; filler is never added to meet duration.
- [ ] Required sections cover the decision-focused hook, Journey at a Glance, Route, Reality Check, Who It Suits, Who Should Avoid It, Adventure Asia Verdict, and controlled CTA.
- [ ] Conditional sections appear only when relevant and evidenced.
- [ ] Important itinerary days are grouped into meaningful chapters rather than read mechanically.
- [ ] Every factual narration Claim links to stored Evidence.
- [ ] `INDICATIVE` Claims use qualified wording.
- [ ] `UNVERIFIED`, `UNKNOWN`, or unsupported Claims do not appear as factual statements.
- [ ] Missing Information stays visibly unknown.
- [ ] Daily Intensity Ratings and one explained overall Trip rating are included when activity evidence exists.
- [ ] Traveller Fit uses conditions and demands rather than age-only eligibility or medical diagnosis.
- [ ] Editorial Notes may support Editorial Judgment but do not create unsupported Product Promises.
- [ ] Price Information is absent.
- [ ] Narration remains understandable without phrases that depend on selected visuals.

## 8. Validate the Editorial Package

**What to build:** Give the Approver a deterministic and AI-assisted review report covering factual support, brand voice, safety language, Product Promises, privacy, originality, and benchmark quality.

**Blocked by:** 7. Generate evidence-traceable neutral narration.

- [ ] The review checks every narration Claim for Evidence linkage and acceptable Evidence Status.
- [ ] The review identifies Stale Claims, Fact Conflicts, Missing Information, and unsupported Product Promises.
- [ ] The review flags prohibited Price Information throughout the draft package.
- [ ] The review flags Supplier Data and creates an Export Block only when forbidden content remains AI-bound or export-bound.
- [ ] The review flags unsupported safety guarantees, medical conclusions, misleading exclusivity, and restricted brand phrases.
- [ ] The review checks that the narration remains neutral and visually independent.
- [ ] A Quality Score and actionable notes are shown regardless of score.
- [ ] Scores below the benchmark remain reviewable and exportable after explicit Approver acknowledgment.
- [ ] Every acknowledgment identifies the warning, Approver, timestamp, and controlled draft version.
- [ ] Re-running validation without changed inputs is idempotent.
- [ ] Tests prove the distinction between advisory warnings and the single non-overridable Export Block.

## 9. Submit, approve, and revise immutable versions

**What to build:** Let the Operator edit working artifacts, submit immutable whole-package versions, record approvals, and safely create later versions without losing history.

**Blocked by:** 8. Validate the Editorial Package.

- [ ] Mutable artifacts remain separate from submitted Editorial Package Versions.
- [ ] `submit-review` creates the next immutable whole-package version.
- [ ] A submitted version references its exact Itinerary Revision, Content Angle, Claims, Evidence, warnings, Quality Score, and acknowledgments.
- [ ] The Approver can approve controlled components and the complete version.
- [ ] Approval records include Approver identity, timestamp, version identity, and content integrity reference.
- [ ] A Content Angle change invalidates script and downstream approval while preserving visible drafts.
- [ ] A narration change invalidates script and final approval.
- [ ] YouTube packaging or Production Brief changes invalidate only final approval.
- [ ] Formatting-only or internal-note changes preserve unrelated approvals.
- [ ] Manual changes are imported explicitly from mutable working artifacts and validated before updating SQLite.
- [ ] Earlier versions remain immutable and restorable.
- [ ] Repeated submission cannot create duplicate version numbers or partial snapshots.

## 10. Generate YouTube packaging and Shorts

**What to build:** Derive complete YouTube discovery assets and two Shorts from an approved long-form version without introducing unsupported Claims or Price Information.

**Blocked by:** 9. Submit, approve, and revise immutable versions.

- [ ] The package contains two search-led, two curiosity-led, and two hybrid title options.
- [ ] Titles match the approved Content Angle and narration.
- [ ] The description includes value, Trip summary, Traveller Fit, controlled CTA, Trip link, chapters, and required disclosures.
- [ ] Chapters and timestamps align with the approved narration duration.
- [ ] The thumbnail brief contains one clear idea, accurate destination cues, and concise text options.
- [ ] Keyword candidates and search intent are qualitative.
- [ ] Unavailable search volume, competition, or difficulty values display `NOT_AVAILABLE`.
- [ ] Two Shorts are generated only from approved long-form Claims.
- [ ] Shorts may reframe but cannot add new factual Claims.
- [ ] Price Information is absent from every generated asset.
- [ ] Changes create reviewable working output and follow normal approval invalidation rules.

## 11. Generate the Production Brief and Pictory handoff

**What to build:** Produce a vendor-neutral visual-production package and manual Pictory handoff from an approved Editorial Package Version without selecting media or allowing the vendor to rewrite editorial substance.

**Blocked by:** 9. Submit, approve, and revise immutable versions.

- [ ] The Production Brief contains locked narration, semantic scene requirements, route-map requirements, on-screen text, brand direction, and restrictions.
- [ ] Scene requirements identify visual meaning and exact location where relevant without choosing footage.
- [ ] Rights and AI-disclosure requirements are stated without claiming that assets have been licensed.
- [ ] The package does not prescribe Pictory-specific transitions, effects, or automated rewriting.
- [ ] Narration and scene plans remain vendor-neutral.
- [ ] Markdown, JSON, and CSV exports describe the same Editorial Package Version.
- [ ] Manual Pictory handoff files are usable without API integration.
- [ ] Export is prevented only when unresolved Supplier Data remains in export-bound content.
- [ ] Other warnings require recorded Approver acknowledgment and remain included in the handoff record.
- [ ] Export tests verify that no Price Information, secrets, copyrighted page copies, or Supplier Data leak into the package.

## 12. Pass the Nakasendo end-to-end benchmark

**What to build:** Demonstrate the complete MVP on the Nakasendo–Kiso Valley Trip, including alternate ingestion paths, reusable research, approvals, exports, privacy controls, and failure recovery.

**Blocked by:** 3. Add URL ingestion and itinerary updates; 5. Reuse Research Library Evidence across Trips; 10. Generate YouTube packaging and Shorts; 11. Generate the Production Brief and Pictory handoff.

- [ ] The benchmark succeeds from URL or pasted-text ingestion through an immutable approved `v1`.
- [ ] Route, days, walking times, daily and overall intensity, accommodation, Trip Transport, and practical constraints normalize correctly.
- [ ] Baseline Research includes current, traceable crowd and solo-traveller Evidence.
- [ ] Up to three meaningful Content Angles are offered and one is approved.
- [ ] Angle Research supports the selected promise.
- [ ] Narration is original, useful, evidence-traceable, visually independent, and free of generic filler.
- [ ] Reality Check, Traveller Fit, Adventure Asia Verdict, and controlled CTA are present.
- [ ] Missing Information remains explicit instead of inferred.
- [ ] Quality notes, warnings, acknowledgments, approvals, and version references are complete.
- [ ] YouTube packaging, two Shorts, scene plan, route-map brief, Production Brief, and manual Pictory handoff are internally consistent.
- [ ] Supplier Data and Price Information are absent from AI-bound and exported content.
- [ ] The workflow resumes successfully after simulated interruption at every major stage.
- [ ] Forced regeneration replaces only the requested stage and cannot duplicate Claims, Evidence, or versions.
- [ ] A second Trip demonstrates confirmed Route Segment research reuse without leaking Trip-specific Claims.
- [ ] The default automated test suite uses fake external adapters; any live OpenAI smoke test remains opt-in.
