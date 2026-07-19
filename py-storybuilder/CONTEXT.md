# Context / Design Log

Living record of decisions for py-storybuilder. Update as decisions change — don't
leave this stale.

## Vision — the "fish-pool"

User sets the initial conditions (the pool): title, style, synopsis/arc, world facts,
seed characters/locations, constraints. From there:

- The AI **drives the plot itself** — writes the next paragraph each step, no
  beat-by-beat puppeting required.
- The AI **notices new facts** as it writes (character traits/goals/history, location
  details) and **proposes** writing them back into the story data.
- **Human-in-the-loop on facts**: every proposed new fact is shown to the user for
  approve/reject before it's saved. Plot generation is autonomous; the persistent
  world model is not auto-mutated without a human okay. (Corrected 2026-07-19 — an
  earlier "max autonomy / full auto-apply" version of this decision was walked back.)

The fish move on their own; the user still decides what's true.

## Process note

Full dev life cycle walked deliberately, phase by phase, **before writing code**.
User is writing the implementation themselves — this repo's assistant-authored
content is design/planning docs (this file, README), not application code, unless
explicitly asked otherwise.

## Requirements — locked (2026-07-19)

| Decision | Choice |
|---|---|
| Interface | CLI |
| AI provider | Claude (Anthropic SDK) |
| Run style | Step-by-step (one paragraph per invocation), not batch scenes |
| Who codes v1 | User codes it; assistant designs/guides |

## Design decisions

- **No knowledge graph in v1.** It's a scale/consistency tool, not a creativity tool.
  Can be added later since it'd derive from the same JSON data — no lock-in from
  skipping it now.
- **Storage**: JSON-per-story on disk (folder per story), not a database. Matches the
  underlying memory model below and needs no schema migrations for a single-user CLI.
- **Memory model**: the LLM is stateless. Durable memory = disk (the story's JSON).
  Working memory = whatever prompt slice gets reassembled and sent on each call.
- **Dropped for v1**: knowledge graph, manuscript import, local ONNX embeddings,
  multi-provider abstraction, agentic mutation tools. All present in AISB; none
  needed for a first working loop.

## What's borrowed from AIStoryBuilders (AISB)

Source read 2026-07-19: `Models/*.cs`, `AI/PromptTemplateService.cs`,
`Services/TimelineSummaryGenerator.cs`, `Services/MasterStoryBuilder.cs`,
`AI/OrchestratorMethods.DetectCharacterAttributes.cs` in the AISB repo
(`../AIStoryBuilders`, C#/.NET MAUI, Windows-only — can't run locally on macOS, source
reading only).

### Data model shape

- `Timeline` is its own entity — a named era with optional start/stop date and
  description (e.g. "Act 1"), **not** a per-fact beat counter. Flat list on Story.
- Fact-tagging lives on the fact itself, not the paragraph:
  - `CharacterBackground { type: Appearance|Goals|History|Aliases|Facts, description, timeline_ref }`
  - `LocationDescription { description, timeline_ref }`
- `Paragraph` refs: chapter, one location, one timeline, list of characters present.
- `Story` holds flat lists: chapters, characters, locations, timelines, plus
  title/style/theme/synopsis/world_facts.
- AISB persists this via a SQL DB (EF Core, nav properties). We take the schema
  shape only — storage stays JSON-per-story on disk (see Design decisions above).

### Growth loop

Three-call sequence per step:

1. **WriteParagraph** — strict JSON, single field (`paragraph_content`). Grounded
   prompt: only use given info, match style, dialogue line-break rule, word cap,
   don't contradict the timeline summary, don't leak other timelines.
2. **DetectCharacters** — which known characters appear in the new paragraph.
3. **DetectCharacterAttributes** — feed paragraph text + a simplified existing-facts
   list (name + current facts only, no ids) → strict JSON → returns **only new**
   facts, categorized into the 5 fixed types. Explicitly constrained to characters
   already in the list and to genuinely new descriptions.

AISB gates step 3's output behind a human-approval selector UI before write-back.
**We keep that gate** (see Vision above) — a CLI-equivalent approve/reject prompt,
not silent auto-apply.

### Prompt assembly

- `WriteParagraph` prompt slice: story_title, story_style, story_synopsis,
  system_directions, world_facts, timeline_summary, current_chapter,
  previous_paragraphs, current_location, characters (with attrs), instructions,
  constraints.
- `TimelineSummaryGenerator`: a **deterministic, non-LLM** prose summary of a
  timeline — active characters + attrs, locations, chronological events. Word-capped
  (800 in AISB), drops oldest events first when over budget. Cheap and worth stealing
  as-is — no reason to spend a model call summarizing state we already hold
  structured.
- `MasterStoryBuilder.TrimToFit`: token-budget trimming across previous + "related"
  paragraphs, ranked by relevance score, dropping lowest-scoring first.
  - We have no embeddings/relevance signal in v1 (dropped, see above) — **simplify to
    a recency + word-budget cap** on `previous_paragraphs` only. No
    `related_paragraphs` section at all in v1.

## AI agentic layer

Decisions locked 2026-07-19 for the orchestration layer sitting on top of the raw
prompt calls:

- **Detect mode is kept, not merged.** Growth loop stays a 3-call sequence per step —
  WriteParagraph → DetectCharacters → DetectCharacterAttributes — mirroring AISB, not
  collapsed into one call. Keeps each step's JSON schema small/reliable and each
  concern independently retryable.
- **New characters can appear mid-story**, not just the seeded cast. AISB's
  "New Character" detection mode is in scope for v1: the detect step can propose an
  entity not present at story creation. Same human-approval gate applies as for facts
  (see Growth loop) — a new character is proposed, not silently added.
- **AI suggests when the story should end.** No fixed chapter-count cutoff decided
  upfront. As part of the step loop, the AI evaluates pacing/arc progress and can
  flag "this looks like a natural ending" — surfaced to the user rather than
  auto-stopping, so growth doesn't drag the story out past its arc. Still needs a
  concrete signal shape (e.g. an `ending_suggested: bool` + reason field somewhere in
  the step output) — left for the schema pass.
- **API keys via `.env`** (not a config file, not hardcoded) — `ANTHROPIC_API_KEY`
  loaded from environment at startup.

## Still open

Next step is drafting the concrete v1 JSON schema (Story/Chapter/Paragraph/
Character/Location/Timeline as actual JSON shapes, plus the new-character-proposal
and ending-suggestion output shapes above) and file layout
(`stories/<id>/story.json` + `stories/<id>/chapters/<n>.json`, as previously
discussed), then module layout for the CLI itself. Update this section as new
questions come up.
