# Adventure Asia YouTube Content Generator MVP

Status: ready-for-agent

## Problem Statement

Adventure Asia has valuable Trip itineraries but lacks a repeatable way to turn them into trustworthy, original, brand-consistent YouTube content. Manual research and writing take too long, quality varies between staff and contractors, and generic AI generation creates serious risks: invented facts, stale travel information, unsafe claims, hidden Supplier Data, unsupported Product Promises, repetitive scripts, and visuals that misrepresent real destinations.

Adventure Asia needs a local editorial system that transforms one Trip into one reviewable Editorial Package for one faceless travel briefing. The system must combine verified itinerary facts, current external Evidence, and Adventure Asia’s Editorial Judgment without pretending uncertain information is known. Humans must retain approval authority. The output must remain independent of any video-production vendor and must not publish automatically.

## Solution

Build a local Python CLI that ingests an Adventure Asia itinerary from a URL or pasted text, removes suspected Supplier Data from the AI-bound copy, normalizes the Trip into an immutable Itinerary Revision, performs reusable evidence-backed research, proposes supported Content Angles, and generates one neutral Editorial Package.

The workflow separates Baseline Research from Angle Research. It stores Claims, Evidence, Source Records, Route Segments, approvals, warnings, and immutable Editorial Package Versions in a shared SQLite-backed workspace. Human-readable Markdown, JSON, and CSV artifacts support review and manual editing.

The generator produces neutral narration, YouTube packaging, two Shorts, a semantic scene plan, a route-map brief, quality notes, and a vendor-neutral Production Brief for manual Pictory handoff. Unknown information remains explicitly unknown. Quality warnings are advisory and require Approver acknowledgment. Detected Supplier Data remaining in AI-bound or exported content is the only non-overridable Export Block.

## User Stories

1. As an Operator, I want to create a Trip from an itinerary URL, so that I can begin from an existing Adventure Asia webpage.
2. As an Operator, I want to create a Trip from pasted itinerary text, so that I can process content without a public webpage.
3. As an Operator, I want every Trip to receive a stable identifier and readable slug, so that similarly named Trips never collide.
4. As an Operator, I want the original Adventure Asia itinerary preserved locally, so that every generated result remains auditable.
5. As an Operator, I want itinerary changes stored as new immutable Itinerary Revisions, so that previous Editorial Package Versions remain reproducible.
6. As an Operator, I want the system to detect possible Supplier Data before any AI call, so that private partner information is protected.
7. As an Operator, I want suspected Supplier Data removed from the AI-bound copy while processing continues, so that one warning does not destroy useful work.
8. As an Approver, I want every Supplier Data removal shown for human review, so that legitimate itinerary details are not silently lost.
9. As an Approver, I want export blocked when Supplier Data remains in AI-bound or exported content, so that forbidden information cannot leave the generator.
10. As an Operator, I want the itinerary normalized into structured Trip facts, so that later stages do not repeatedly process the complete source.
11. As an Operator, I want route legs, overnight stops, activities, accommodation, meals, transfers, activity times, and practical constraints normalized when available, so that the content accurately reflects the Trip.
12. As an Operator, I want Missing Information reported explicitly, so that I know which source details require follow-up.
13. As an Approver, I want unknown information to remain unknown, so that AI inference cannot become a false Trip fact.
14. As an Operator, I want compatible activity-time estimates expressed as honest ranges, so that different traveller speeds are represented realistically.
15. As an Approver, I want incompatible estimates marked as a Fact Conflict, so that route or condition differences are not hidden inside a misleading range.
16. As an Operator, I want Baseline Research run for every Trip, so that essential current conditions are checked before choosing a Content Angle.
17. As an Operator, I want Baseline Research to cover access rules, route conditions, seasonality, crowds, relevant Independent Transport, solo-traveller conditions, official advisories, and major practical demands, so that every package has a reliable foundation.
18. As an Operator, I want external retrieval completed before AI synthesis, so that the model writes from stored Evidence rather than invented citations.
19. As an Approver, I want every factual Claim traced to Evidence, including itinerary-derived Claims, so that fact-checking is complete.
20. As an Approver, I want Evidence Status shown as `VERIFIED`, `CORROBORATED`, `INDICATIVE`, `UNVERIFIED`, or `UNKNOWN`, so that support quality is explicit.
21. As an Approver, I want `INDICATIVE` patterns qualified in narration, so that anecdotes are not presented as universal facts.
22. As an Approver, I want `UNVERIFIED` Claims excluded from factual narration, so that unsupported statements do not become authoritative copy.
23. As an Operator, I want source authority evaluated by Claim type, so that the most relevant authority supports each statement.
24. As an Operator, I want the current Itinerary Revision treated as authoritative for included Trip Transport, so that public schedules do not contradict arranged transfers.
25. As an Operator, I want official operators used for Independent Transport, so that current public schedules and rules come from the correct source.
26. As an Operator, I want Source Records to preserve metadata, dates, hashes, locators, and Adventure Asia paraphrases, so that Evidence remains auditable without copying copyrighted pages.
27. As an Operator, I want shared Claims and Evidence stored in a Research Library, so that multiple Trips using the same route do not repeat research unnecessarily.
28. As an Operator, I want AI to propose Route Segment matches, so that reusable research can be discovered efficiently.
29. As an Operator, I want to confirm reusable Route Segments manually, so that AI cannot silently merge different places or routes.
30. As an Operator, I want shared research reused only when geography, Route Segment, conditions, and freshness match, so that reuse does not create false relevance.
31. As an Operator, I want expired Claims refreshed automatically when possible, so that current research stays useful.
32. As an Approver, I want failed refreshes shown as Stale Claims, so that outdated Evidence is never hidden.
33. As an Approver, I want every time-sensitive Claim to carry a Recheck Date, so that freshness is evaluated at Claim level.
34. As an Operator, I want up to three evidence-supported Content Angles proposed, so that I can compare meaningful editorial options.
35. As an Operator, I want fewer than three angles when the Evidence cannot support more, so that the generator never pads the choice set with weak ideas.
36. As an Approver, I want each proposed Content Angle to explain its viewer question, Evidence, commercial relevance, and Missing Information, so that selection is informed.
37. As an Approver, I want to select exactly one Content Angle for the Editorial Package, so that the video has one clear promise.
38. As an Approver, I want to enter a custom Content Angle, so that Adventure Asia retains editorial control.
39. As an Approver, I want custom angles checked against Evidence before generation, so that manager direction does not bypass factual discipline.
40. As an Operator, I want Angle Research to run only after angle approval, so that research cost focuses on the chosen viewer question.
41. As an Operator, I want optional public-safe Editorial Notes accepted as input, so that Adventure Asia’s real judgment can shape the content.
42. As an Approver, I want vague Editorial Notes prevented from becoming Product Promises, so that operational commitments remain precise.
43. As an Approver, I want Price Information prohibited throughout the Editorial Package, so that seasonal price changes cannot make durable media misleading.
44. As a viewer, I want a decision-focused opening, so that I immediately understand the practical question the video will answer.
45. As a viewer, I want a clear Journey at a Glance and Route explanation, so that I can orient myself quickly.
46. As a viewer, I want itinerary days grouped into meaningful chapters, so that the video explains the journey instead of mechanically reading each day.
47. As a viewer, I want a Reality Check, so that compromises receive equal attention with benefits.
48. As a viewer, I want Who It Suits and Who Should Avoid It sections, so that I can assess Traveller Fit honestly.
49. As a viewer, I want Traveller Fit described through conditions and demands rather than age or diagnosis, so that the guidance is useful without becoming medical advice.
50. As a viewer, I want daily Intensity Ratings and one explained overall Trip rating, so that a difficult day is not hidden by an average.
51. As a viewer, I want Estimated Durations expressed as ranges when pace naturally varies, so that timing is realistic.
52. As a viewer, I want solo-traveller conditions described specifically without safety guarantees, so that I can assess logistics and precautions myself.
53. As a viewer, I want optional sections omitted when they add no useful Evidence, so that the video avoids repetitive filler.
54. As a viewer, I want a shorter video when the Trip cannot support seven useful minutes, so that duration targets do not reduce quality.
55. As a viewer, I want Adventure Asia’s value demonstrated through supported arrangements and Editorial Judgment, so that the video remains useful rather than promotional.
56. As a viewer, I want a controlled CTA linking to the Trip page without price claims or artificial urgency, so that I can continue when the journey fits me.
57. As an Operator, I want neutral narration that makes sense without selected footage, so that later visual changes do not break the script.
58. As an Operator, I want a semantic scene plan describing visual meaning, so that a video editor can choose accurate media independently.
59. As an Operator, I want a route-map brief and on-screen text plan, so that essential orientation and practical information can be visualized consistently.
60. As an Operator, I want the generator to state rights and AI-disclosure requirements without selecting assets, so that media responsibility remains with video production.
61. As an Operator, I want a vendor-neutral Production Brief, so that the editorial core does not depend on Pictory.
62. As an Operator, I want manual Pictory handoff files, so that the MVP can produce a rough video without building an API integration.
63. As an Operator, I want two Shorts derived from approved long-form Claims, so that supporting content cannot introduce unsupported facts.
64. As an Operator, I want YouTube titles, description, chapters, and a thumbnail brief, so that each Editorial Package is ready for channel packaging.
65. As an Approver, I want unavailable SEO metrics labeled `NOT_AVAILABLE`, so that the system never invents search volume or competition.
66. As an Operator, I want mutable work separated from submitted versions, so that editing remains easy while review snapshots stay stable.
67. As an Operator, I want `submit-review` to create immutable whole-package versions, so that `v1`, `v2`, and later versions remain auditable.
68. As an Approver, I want approvals bound to exact component and package versions, so that later edits cannot inherit stale approval.
69. As an Approver, I want affected work moved to `REVIEW_REQUIRED` after controlled changes, so that previous output stays visible while release status remains honest.
70. As an Operator, I want formatting-only or internal-note changes to preserve unrelated approvals, so that review work is not repeated unnecessarily.
71. As an Approver, I want any Quality Score visible with actionable benchmark notes, so that low-scoring work can still be reviewed and improved.
72. As an Approver, I want non-critical validation failures exportable after explicit acknowledgment, so that final editorial accountability remains human.
73. As an Operator, I want manual file changes imported explicitly, so that filesystem edits cannot silently corrupt structured state.
74. As an Operator, I want completed workflow stages saved atomically, so that interruption does not lose successful work.
75. As an Operator, I want failed stages resumed without repeating completed calls, so that API cost and output drift are controlled.
76. As an Operator, I want forced regeneration to require an explicit command, so that successful outputs are not replaced accidentally.
77. As an Operator, I want one shared SQLite database for all Trips, so that Research Library reuse and cross-Trip freshness checks are reliable.
78. As an Operator, I want human-readable Markdown, JSON, and CSV exports, so that I can inspect, edit, and hand off content without database tools.
79. As an Operator, I want the OpenAI API isolated behind a provider interface, so that domain workflow is not coupled to vendor-specific types.
80. As an Operator, I want the OpenAI API key loaded only from a local `.env`, so that credentials do not enter source control or content artifacts.
81. As an Operator, I want logs to exclude secrets and forbidden content, so that diagnostics do not create a new exposure path.
82. As an Approver, I want the final Editorial Package to identify every warning and acknowledgment, so that release decisions are auditable.
83. As a product owner, I want the Nakasendo–Kiso Valley Trip used as the end-to-end benchmark, so that MVP quality is evaluated against one realistic journey.
84. As a product owner, I want YouTube planning and analytics kept in a separate future system, so that this MVP stays focused on trustworthy editorial production.

## Implementation Decisions

- The product is a local Python CLI. No graphical interface, hosted service, authentication system, or automatic publisher is required for the MVP.
- The primary application seam is a workflow service invoked by the CLI. It accepts an Operator command and workspace context, advances one explicit stage, persists the result atomically, and returns a user-readable stage report.
- The CLI remains thin. Domain logic lives behind deep modules with narrow interfaces:
  - ingestion and Supplier Data sanitization;
  - Trip normalization and Itinerary Revision management;
  - retrieval, Source Records, Claims, Evidence, and the Research Library;
  - Content Angle proposal and approval;
  - editorial planning, narration, YouTube packaging, and Repurposed Assets;
  - deterministic validation, Quality Scores, warnings, and approvals;
  - versioned workspace persistence and export;
  - vendor-neutral Production Brief generation;
  - OpenAI and retrieval provider adapters.
- One Trip has one current Editorial Package. Revisions create immutable Editorial Package Versions rather than separate content runs.
- One shared workspace SQLite database is the operational source of truth. Python’s built-in `sqlite3` is sufficient; no database dependency is required.
- The structured model must represent at least Trips, Itinerary Revisions, Editorial Packages, Editorial Package Versions, Route Segments, Source Records, Claims, Evidence, Claim-to-Evidence links, Recheck Dates, warnings, validation results, approvals, workflow stages, and stage attempts.
- Trip workspaces use a readable slug plus stable Trip ID. They contain source revisions, mutable working artifacts, immutable submitted versions, and a pointer to the current version.
- SQLite owns mutable operational state. Markdown, JSON, and CSV are review and handoff formats. Direct file changes affect the system only through an explicit import operation.
- The original Adventure Asia itinerary is retained locally. Suspected Supplier Data is removed from a Sanitized Itinerary before AI processing. The original is never included in prompts or exports when flagged content remains.
- Sanitization warnings require human review. Processing may continue from the Sanitized Itinerary. Unsanitized Supplier Data in AI-bound or exported content is the only non-overridable Export Block.
- URL and pasted-text ingestion are included. Word and PDF ingestion are deferred.
- Normalization happens once per Itinerary Revision. Downstream model calls receive only fields required for their stage.
- Missing values remain Missing Information. The system must not convert unsupported AI inference into Trip facts.
- Compatible duration estimates may be combined only when route, segment, scope, and conditions match. Otherwise the system records a Fact Conflict.
- Retrieval and AI synthesis are separate. Retrieval creates Source Records and Evidence before any Claim synthesis.
- Source Records retain identifying metadata, access/publication dates when available, source category, content hash, locator, and Adventure Asia’s paraphrased evidence summary. They do not store full copyrighted webpages or copied paragraphs.
- Every factual Claim must link to Evidence, including Claims derived from an Itinerary Revision.
- Evidence uses the canonical statuses `VERIFIED`, `CORROBORATED`, `INDICATIVE`, `UNVERIFIED`, and `UNKNOWN`.
- `INDICATIVE` Claims require qualified language. `UNVERIFIED` and `UNKNOWN` Claims cannot appear as unqualified facts.
- Source authority is Claim-type-specific. The Itinerary Revision governs included Trip arrangements; official operators govern Independent Transport; official authorities govern advisories, access, and rules; traveller reports support only qualified patterns.
- Baseline Research runs before Content Angle selection. Angle Research runs only after an Approver selects a generated or custom Content Angle.
- The generator proposes up to three supported Content Angles. It must not invent weak angles to reach a quota.
- AI may propose reusable Route Segment matches. An Operator must confirm a Route Segment before Claims and Evidence are reused across Trips.
- Shared Evidence reuse requires matching scope, geography or Route Segment, conditions, and freshness.
- Time-sensitive Claims carry Recheck Dates. The system attempts refresh before reuse. Failed refreshes remain available as Stale Claims with prominent warnings.
- Editorial Notes are optional, manager-provided, public-safe input. They may support Editorial Judgment but cannot silently create Product Promises.
- Price Information is prohibited in narration, on-screen text, YouTube metadata, Shorts, articles, social copy, email copy, and all other Editorial Package artifacts.
- The default long-form target is 7–10 minutes. Duration is estimated from narrator speed and planned pauses. Shorter useful narration is allowed; padding and generic filler are prohibited.
- Required editorial components are the decision-focused hook, Journey at a Glance, Route, Reality Check, Who It Suits, Who Should Avoid It, Adventure Asia Verdict, and controlled CTA.
- Crowd guidance, solo-traveller guidance, accommodation, signature experiences, and Adventure Asia Difference are conditional sections included only when useful and evidenced.
- Traveller Fit is condition-based and cannot assert medical suitability or use age alone as an eligibility rule.
- Intensity Rating exists at daily and whole-Trip levels. The overall value reflects the highest sustained demand, not a simple average.
- Narration must remain understandable without visual dependencies such as “as you can see.”
- The Production Brief is vendor-neutral. It contains locked narration, semantic scene requirements, route-map requirements, brand direction, on-screen text, and restrictions.
- The generator does not select footage, determine licenses, prescribe vendor effects, rewrite content for Pictory, create videos, or publish.
- Pictory support in the MVP is a manual file handoff. No Pictory API integration is included.
- Repurposed Assets are generated only after long-form approval and may not add new Claims.
- SEO output is qualitative. Numeric search volume, competition, or difficulty displays `NOT_AVAILABLE` until a real data integration exists.
- Quality Scores and validation results are advisory. Any score remains reviewable. Export after non-critical failures requires explicit Approver acknowledgment.
- Approvals bind to exact versions. Changes invalidate only dependent approvals and move affected work to `REVIEW_REQUIRED`; drafts remain visible.
- `submit-review` freezes the mutable working state into the next immutable whole-package version.
- Workflow stages are resumable and idempotent. Completed stages are reused after failure; replacement requires an explicit force operation; retries cannot duplicate domain records.
- The OpenAI API is accessed through an internal provider interface. Exact model, SDK, structured-output mechanism, and request settings must be verified against current official OpenAI documentation during implementation.
- API secrets are loaded only from a workspace-root `.env`, excluded from Git, restricted to the local user, omitted from logs and exports, and represented by empty names in `.env.example`.
- Use built-in Python capabilities before proposing dependencies. Any new third-party library requires explicit user approval under the project’s dependency policy.

## Testing Decisions

- The primary test seam is the complete workflow service as observed through the CLI contract. Tests run a command against a temporary workspace, use deterministic fake retrieval and OpenAI adapters, then inspect user-visible artifacts, SQLite state, warnings, approvals, and stage status.
- Tests assert external behavior rather than internal helper calls, prompt wording, SQL statement shape, or private class structure.
- A Nakasendo–Kiso Valley fixture provides the main end-to-end acceptance test from ingestion through immutable `v1` Production Brief export.
- The acceptance fixture must prove correct route/day normalization, Supplier Data sanitization behavior, Baseline Research records, supported angle proposals, approved Angle Research, traceable narration Claims, Missing Information handling, Intensity Ratings, Reality Check, Traveller Fit, YouTube packaging, two Shorts, and manual Pictory handoff artifacts.
- Workflow tests cover successful first runs, interruption after each stage, resume from failure, forced regeneration, and duplicate prevention.
- Versioning tests cover mutable work, review submission, immutable snapshots, current-version selection, approval binding, dependent approval invalidation, and restoration of prior versions.
- Evidence tests cover Claim-to-Evidence traceability, Evidence Status rules, Claim-type authority, Stale Claims, Recheck Dates, compatible Estimated Duration ranges, Fact Conflicts, and cross-Trip Route Segment reuse.
- Privacy tests cover Supplier Data detection, pre-AI sanitization, human-review warnings, export blocking when forbidden data remains, log redaction, and exclusion of `.env` content from persisted artifacts.
- Editorial policy tests cover prohibited Price Information, banned or restricted brand language, visual-independent narration, required/conditional sections, unsupported Product Promises, and prohibition of unqualified `UNVERIFIED` Claims.
- Export contract tests validate that Markdown, JSON, and CSV describe the same Editorial Package Version and that the Production Brief contains no Pictory-specific rewriting.
- Repository integration tests use a real temporary SQLite database and filesystem. They verify transactional updates and artifact regeneration without relying on a production workspace.
- OpenAI and retrieval adapters receive contract tests at their boundary. Routine tests do not call live external services.
- A small opt-in live smoke test may be added after model and SDK approval to verify authentication and structured response compatibility. It must never be part of the default test suite.
- No implementation prior art exists in the current workspace; the codebase currently contains only the domain glossary, project context, and ADRs. Tests therefore establish the initial behavioral conventions.

## Out of Scope

- Word and PDF itinerary ingestion.
- Supplier portal, supplier API, accommodation API, or private partner-system integration.
- Any use of Supplier Data in prompts or Editorial Packages.
- Price Information anywhere in generated content.
- Graphical or web-based operator interface.
- Multi-user authentication and role enforcement.
- Hosted deployment or remote database.
- Automatic video creation.
- Pictory API integration.
- Fliki or Digital Maker AI integrations.
- Footage selection, media purchasing, license verification, or final AI-visual disclosure review.
- Automated map rendering.
- Automatic YouTube publishing.
- YouTube planning, channel scheduling, analytics ingestion, and performance optimization.
- Numeric SEO volume, competition, or keyword-difficulty metrics.
- Multilingual generation.
- Partner brand profiles and white-label output.
- B2B partner workflows.
- Automated article, email, or social-channel publishing.

## Further Notes

- The canonical domain language is defined in `CONTEXT.md`; implementation and tests must use those terms.
- The accepted architectural boundaries are recorded in ADRs 0001–0013 and must not be silently contradicted.
- The MVP exists to validate editorial trust and workflow efficiency, not to maximize automation.
- One person may act as both Operator and Approver in the MVP, but the roles and approval records remain distinct.
- The separate YouTube planner system will own scheduling, publishing coordination, analytics, and feedback optimization.
- The first production-tool target is Pictory through manual handoff only.
- The original product/editorial specification remains useful background, but this spec and the accepted ADRs contain the sharpened MVP decisions.
