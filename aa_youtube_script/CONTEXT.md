# Adventure Asia YouTube Content Generator

This context defines the language used to turn one Adventure Asia trip into one approved package for a 7–10 minute YouTube video and its supporting content.

## Language

**Trip**:
A specific Adventure Asia journey represented by its itinerary and verified product facts. Each Trip has one current Editorial Package.
_Avoid_: Tour, content item

**Editorial Package**:
The complete approved content derived from one Trip, including research, narration, scene plan, YouTube packaging, supporting formats, and quality records. Revisions create new versions of the same Editorial Package.
_Avoid_: Content, content run, output

**Estimated Duration**:
A supported time range for an activity whose duration naturally varies by traveller pace or conditions. Compatible estimates may be expressed as a range, such as “about 3–5 hours,” rather than treated as contradictory facts.
_Avoid_: Exact duration, guaranteed time

**Fact Conflict**:
Materially inconsistent information that cannot be honestly combined because it describes different routes, segments, conditions, or meanings. A Fact Conflict must be resolved before the affected statement can be approved.
_Avoid_: Variation, estimated range

**Claim**:
A factual statement proposed for use in an Editorial Package. Every Claim must be traceable to supporting Evidence, including Claims derived from the Trip itinerary.
_Avoid_: Fact, copy

**Evidence**:
A traceable source supporting a Claim, including an itinerary location, external source, or verified supplier record.
_Avoid_: Reference, link

**Editorial Judgment**:
Adventure Asia’s clearly identified interpretation or recommendation based on experience and Evidence, rather than an independently verifiable fact.
_Avoid_: Fact, guarantee

**Recheck Date**:
The date after which a time-sensitive Claim can no longer support publication without renewed verification. An overdue critical Claim places its Editorial Package in `RECHECK_REQUIRED`.
_Avoid_: Expiry date

**Supplier Data**:
Private supplier identities, contacts, net rates, commercial terms, operational notes, or other non-public partner information. Supplier Data is forbidden input and must never be used in AI prompts or Editorial Packages.
_Avoid_: Itinerary facts, public accommodation information

**Sanitized Itinerary**:
The AI-safe copy of a Trip itinerary after suspected Supplier Data has been removed. Processing may continue from this copy, but final approval remains blocked until a human reviews the flagged removal.
_Avoid_: Original itinerary, normalized itinerary

**Operator**:
The person who imports, researches, generates, and edits an Editorial Package.
_Avoid_: Approver

**Approver**:
The person accountable for accepting a controlled part or version of an Editorial Package. One person may act as both Operator and Approver in the MVP, but the roles remain distinct.
_Avoid_: Operator, reviewer

**Content Angle**:
The single primary viewer question or promise that determines how a Trip is framed in its Editorial Package. Changes to hooks or wording that preserve the same central promise are not Content Angle changes.
_Avoid_: Title, topic, hook

**Approval**:
Acceptance of an exact version of a controlled Editorial Package component. Approval controls release to video production or publication; it never hides or deletes drafts, and a changed component remains visible as `REVIEW_REQUIRED`.
_Avoid_: Review, draft visibility

**Quality Score**:
An advisory assessment of an Editorial Package against the quality benchmark. Any score remains reviewable and exportable after explicit Approver acknowledgment; failed areas must be shown as actionable notes.
_Avoid_: Release permission, approval

**Export Block**:
A non-overridable condition preventing content from leaving the generator. In the MVP, only detected Supplier Data remaining in AI-bound or exported content creates an Export Block; other validation failures require explicit Approver acknowledgment.
_Avoid_: Warning, low Quality Score

**Editorial Package Version**:
An immutable snapshot of everything related to a Trip’s Editorial Package when the Operator submits mutable work for review. Versions are stored inside the Trip workspace as `v1`, `v2`, `v3`, and one version is identified as current.
_Avoid_: File revision, content run

**Research Library**:
The shared collection of reusable Claims and Evidence that may support multiple Trips. Reuse is allowed only when geographic scope, Route Segment, conditions, and freshness still match.
_Avoid_: Trip research folder, copied sources

**Route Segment**:
A specifically bounded and Operator-confirmed part of a journey used to determine whether practical or destination research applies across multiple Trips. AI may propose matches but cannot silently create or merge reusable Route Segments.
_Avoid_: Trip, destination

**Itinerary Revision**:
An immutable version of a Trip’s source itinerary and normalized product facts. Every Editorial Package Version references the exact Itinerary Revision from which it was produced.
_Avoid_: Editorial Package Version, current itinerary

**Stale Claim**:
A Claim whose Recheck Date has passed without successful renewed verification. The generator attempts refresh first; if refresh fails, the Claim may remain in a draft or export only with a prominent warning and Approver acknowledgment.
_Avoid_: False claim, Fact Conflict

**Trip Transport**:
Transport included and arranged as part of a Trip. Its current Itinerary Revision is authoritative for the planned arrangement.
_Avoid_: Independent transport, public schedule

**Independent Transport**:
Transport a traveller must arrange before, after, or outside the Trip. Official transport operators are authoritative for its current schedules and rules.
_Avoid_: Trip Transport, included transfer

**Traveller Fit**:
The match between a Trip’s verified demands, conditions, and compromises and a traveller’s own capabilities and preferences. It is expressed as condition-based self-assessment, never as age-based eligibility or medical diagnosis.
_Avoid_: Medical clearance, age suitability

**Intensity Rating**:
Adventure Asia’s 1–5 assessment of verified physical demands and conditions. Each active day has a rating, while the overall Trip rating reflects the highest sustained demand across terrain, duration, elevation, climate, remoteness, and consecutive active days rather than a simple average.
_Avoid_: Fitness test, difficulty average

**Missing Information**:
A Trip detail or current condition that remains unknown after appropriate source checking. It must stay visibly unknown and may never be filled by unsupported AI inference.
_Avoid_: Estimate, assumption, likely fact

**Evidence Status**:
The support state of a Claim: `VERIFIED` by a directly authoritative source, `CORROBORATED` by multiple credible sources, `INDICATIVE` as a qualified anecdotal pattern, `UNVERIFIED` as unusable factual narration, or `UNKNOWN` when no usable Evidence exists.
_Avoid_: High confidence, medium confidence, low confidence

**Baseline Research**:
The standard current-information checks run for every Trip before Content Angle selection, covering access, season and crowds, relevant Independent Transport, solo-traveller conditions, government advisories, and major practical demands.
_Avoid_: Full research, Angle Research

**Angle Research**:
Focused research performed after Content Angle selection to support that angle’s particular viewer question and Claims.
_Avoid_: Baseline Research, generic destination research

**Editorial Notes**:
Optional, public-safe input from an Adventure Asia manager explaining route-design judgment, customization, support, compromises, and approved differentiation. Editorial Notes must contain no Supplier Data and cannot justify promises they do not explicitly support.
_Avoid_: Supplier notes, itinerary, generated copy

**Product Promise**:
A public statement committing Adventure Asia to an inclusion, availability, access arrangement, customization, or service condition. It requires explicit scope and Approver acceptance; vague Editorial Notes cannot support it.
_Avoid_: Editorial Judgment, aspiration

**Price Information**:
Any statement of Trip price, price range, discount, or seasonal rate. Price Information is forbidden throughout the Editorial Package; content may link to the Trip page for current pricing.
_Avoid_: Price category, “from” price

**Production Brief**:
The vendor-neutral, approved handoff containing locked narration, semantic scene requirements, route-map requirements, brand direction, on-screen text, and restrictions. It does not select footage, decide licenses, or prescribe tool-specific effects; video-tool exporters may reformat it but never rewrite its substance.
_Avoid_: Pictory input, Fliki script, video

**Repurposed Asset**:
A Short, article, email, social post, or other supporting item derived from approved long-form narration and Claims. It may reframe approved material but cannot introduce a new factual Claim without returning through research and review.
_Avoid_: New content package, independent research

**Source Record**:
The metadata identifying external Evidence, including URL, title, publisher, dates, category, content hash, locator, and Adventure Asia’s paraphrased evidence summary. It does not contain a full copyrighted page or copied paragraphs.
_Avoid_: Webpage archive, article copy
