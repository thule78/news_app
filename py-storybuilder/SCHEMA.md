# v1 Schema & File Layout

Concrete JSON shapes implementing the decisions in [CONTEXT.md](CONTEXT.md). Two
assumptions are called out inline where the design log didn't pin an exact shape —
flagged for confirm, everything else follows locked decisions directly.

## File layout

```
stories/
  <story-slug>/
    story.json              # pool + registries (characters, locations, timelines, ending state)
    chapters/
      01.json
      02.json
      ...
```

One folder per story, one file per chapter. `story.json` holds everything that isn't
paragraph text; chapter files hold the actual prose plus per-paragraph refs. No DB,
no manuscript import, no embeddings (per Design decisions).

## `story.json`

```jsonc
{
  "id": "the-lighthouse-keeper",
  "title": "The Lighthouse Keeper",
  "style": "literary, sparse dialogue",
  "synopsis": "...",
  "world_facts": "free-text blob, same as AISB's single-string WorldFacts field",
  "constraints": ["never break first-person POV", "no time travel"],
  "chapter_count_target": null,          // optional hint only, never a hard cap — AI suggests the actual ending, see `ending` below
  "chapters": [
    { "id": "01", "title": "...", "synopsis": "...", "sequence": 1 }
  ],
  "timelines": [
    { "id": "tl_001", "name": "Act 1", "description": "...", "start_date": null, "stop_date": null }
  ],
  "characters": [
    {
      "id": "char_001",
      "name": "Mara",
      "status": "active",              // "active" | "proposed" — proposed = new character detected mid-story, awaiting approval
      "introduced_in_pool": true,       // false if the AI proposed this character mid-story rather than the user seeding it
      "background": [
        {
          "type": "Appearance",         // Appearance | Goals | History | Aliases | Facts — AISB's fixed 5 types
          "description": "...",
          "timeline_ref": "tl_001",
          "chapter_ref": "01",
          "approved_at": "2026-07-19T00:00:00Z"
        }
      ]
    }
  ],
  "locations": [
    {
      "id": "loc_001",
      "name": "The Lighthouse",
      "status": "active",
      "introduced_in_pool": true,
      "descriptions": [
        { "description": "...", "timeline_ref": "tl_001", "chapter_ref": "01", "approved_at": "..." }
      ]
    }
  ],
  "ending": {
    "suggested": false,
    "reason": null,
    "suggested_at_chapter": null,
    "suggested_at_paragraph": null
  }
}
```

Only **approved** facts/characters/locations ever land here — nothing is written by
the growth loop without the human-approval step (per CONTEXT.md AI agentic layer).
Rejected proposals are simply discarded at the end of the CLI step, not persisted.

## `chapters/<n>.json`

```jsonc
{
  "id": "01",
  "title": "...",
  "sequence": 1,
  "paragraphs": [
    {
      "sequence": 1,
      "content": "...",
      "location_ref": "loc_001",
      "timeline_ref": "tl_001",
      "character_refs": ["char_001"]
    }
  ]
}
```

Matches AISB's Paragraph refs (one chapter, one location, one timeline, many
characters) — just plain dict/JSON instead of EF nav properties.

## Per-step call sequence (the growth loop, concretely)

Given `storybuilder step <story-id>` runs one paragraph and exits (step-by-step run
style):

1. **WriteParagraph** → strict JSON:
   ```jsonc
   { "paragraph_content": "...", "ending_suggested": false, "ending_reason": null }
   ```
   *Assumption:* folding the ending-suggestion signal into this same call (extra
   fields on the existing WriteParagraph schema) rather than a separate 4th LLM call
   — it's a cheap addition to a call already reading full story state, and avoids
   growing the call count. Flag if you'd rather have it as its own detect step.

2. **DetectCharacters** → strict JSON, over the new paragraph text:
   ```jsonc
   { "characters": [ { "name": "Mara", "is_new": false }, { "name": "Sel", "is_new": true } ] }
   ```
   `is_new: true` = name not found in `story.json` characters registry — this is the
   mid-story new-character path from CONTEXT.md's AI agentic layer.

3. **DetectCharacterAttributes** → strict JSON, scoped to whatever DetectCharacters
   returned (existing names get facts checked against their current background;
   `is_new` names get a full proposed profile instead of a diff):
   ```jsonc
   {
     "characters": [
       {
         "name": "Sel",
         "is_new": true,
         "descriptions": [
           { "description_type": "Appearance", "description": "..." }
         ]
       }
     ]
   }
   ```

4. **DetectLocations** → strict JSON, same shape as DetectCharacters, over the new
   paragraph text:
   ```jsonc
   { "locations": [ { "name": "The Lighthouse", "is_new": false } ] }
   ```
   `is_new: true` = name not found in `story.json` locations registry. No precedent
   in AISB (their location extraction only ran once, at manuscript-import time) —
   this and step 5 are our addition, built symmetric to the character path by
   deliberate choice (2026-07-19), not ported from AISB source.

5. **DetectLocationAttributes** → strict JSON, scoped to whatever DetectLocations
   returned:
   ```jsonc
   {
     "locations": [
       {
         "name": "The Lighthouse",
         "is_new": false,
         "descriptions": [ "..." ]
       }
     ]
   }
   ```
   No `description_type` field here — AISB's `LocationDescription` model has no
   sub-type equivalent to the character background's 5 types, just a plain
   description string per timeline. Keep that asymmetry; don't invent categories
   AISB doesn't have.

6. **CLI approval gate** (no LLM call — local): show every proposed fact / proposed
   new character / proposed new location / ending suggestion from steps 1–5, one at a
   time, approve/reject. Approved items get merged into `story.json` (new
   characters/locations get `status: "active"` once approved, and so on); rejected
   items are dropped. Then the paragraph itself is appended to the current chapter
   file — paragraph write-back is not gated the same way as facts (only the *derived
   facts* need approval, not the prose itself, per CONTEXT.md).

## Module layout

```
storybuilder/
  __init__.py
  cli.py              # entrypoint, subcommands: new / step / export / show
  config.py           # .env loading, ANTHROPIC_API_KEY
  models.py           # dataclasses: Story, Chapter, Paragraph, Character, Location, Timeline
  storage.py           # load/save story.json + chapters/<n>.json, path helpers
  prompts.py           # WriteParagraph / DetectCharacters / DetectCharacterAttributes / DetectLocations / DetectLocationAttributes templates
  llm.py               # Anthropic client wrapper, strict-JSON call + retry (AISB's CallLlmWithRetry equivalent)
  timeline_summary.py  # deterministic non-LLM summary (ported from AISB, word-capped)
  growth.py            # orchestrates the 6-step per-paragraph sequence, merges approved items into story.json
  approval.py          # interactive CLI approve/reject prompts
  export.py            # story.json + ALL chapters -> one combined book document
```

## CLI commands

- `storybuilder new` — interactive pool setup → writes `story.json`.
- `storybuilder step <id>` — runs one paragraph (the growth loop).
- `storybuilder show <id>` — dump current registries/state, no LLM call.
- `storybuilder export <id>` — reads **every** chapter file in sequence order and
  concatenates them into **one combined book** (chapter headings + prose, no JSON
  refs) — not per-chapter output. Prints to **stdout** only; user copies it manually
  (e.g. into a blog) — no file write, no auto-publish integration.

## Resolved

- Ending-signal placement (folded into WriteParagraph) and new-character handling
  (`is_new` flag) — confirmed as designed above.
- Location facts grow with **full symmetry** to characters (decided 2026-07-19):
  DetectLocations + DetectLocationAttributes added as steps 4–5 of the growth loop,
  same approval gate, same new-location (`is_new`) path as new characters. This has
  no AISB precedent (their location extraction is import-time only) — it's a
  deliberate departure, not a port.
- Module layout and CLI commands — drafted above.

## Open before coding starts

Nothing outstanding. Design is considered complete for v1; next step is
implementation (user codes it, per CONTEXT.md).
