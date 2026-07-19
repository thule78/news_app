# Manual Test Plan (v1)

Nothing here has been run against the live Anthropic API yet — everything below is
untested on the real model. Work through in order; each step assumes the previous
ones passed. Note actual vs expected for anything that diverges.

## 0. Setup

- [ ] `cd py-storybuilder && pip install -r requirements.txt`
- [ ] `cp .env.example .env`, fill in a real `ANTHROPIC_API_KEY`
- [ ] `python3 -m storybuilder.cli list` → should print nothing (no error), stories dir is empty/absent

## 1. `new` — create a story

- [ ] Run `python3 -m storybuilder.cli new`, fill in: title, style, synopsis, world facts,
      one constraint, 2 seed characters (one with facts, one without), 2 seed
      locations (one with a description, one without), first chapter title + synopsis
- [ ] Confirm it prints `Created story '<slug>'.`
- [ ] Inspect `stories/<slug>/story.json` — title/style/synopsis/world_facts/constraints
      match what you typed; both characters present with correct `background`; both
      locations present; one `timelines` entry named "Act 1"; one `chapters` entry
- [ ] Inspect `stories/<slug>/chapters/01.json` — exists, `paragraphs: []`
- [ ] Run `python3 -m storybuilder.cli new` again with the **same title** → should
      print `Story '<slug>' already exists.` and not overwrite the file

## 2. `step` — first paragraph (the real test)

- [ ] Run `python3 -m storybuilder.cli step <slug>`
- [ ] Does it print a paragraph under `--- New paragraph ---`? Does the prose respect
      the style/synopsis/world_facts/constraint you set (spot check, not exact)?
- [ ] Does it then prompt `[kind] description ... Approve? (y/n):` for zero or more
      proposals? For each proposal shown:
  - [ ] Is the `kind` one of `character_fact` / `new_character` / `location_fact` /
        `new_location` / `ending` — nothing else?
  - [ ] Does the description text read as a real, sensible fact (not garbled JSON,
        not an empty string)?
  - [ ] Reject one proposal (`n`) if you get the chance — confirm it does NOT appear
        in `story.json` afterward
  - [ ] Approve at least one character fact and one location fact if offered
- [ ] After answering all prompts, does it exit cleanly (no traceback)?
- [ ] Check `story.json`: approved facts appended to the right character/location's
      background/descriptions, each with `timeline_ref`, `chapter_ref`, `approved_at`
      filled in (not null)
- [ ] Check `chapters/01.json`: one new paragraph, `sequence: 1`, `content` matches
      what was printed, `location_ref`/`timeline_ref` non-null, `character_refs`
      contains the right character ids

## 3. `step` again — continuity

- [ ] Run `step <slug>` a second time
- [ ] Does the new paragraph read as a continuation (references prior events/characters
      sensibly), not a reset to the beginning?
- [ ] Confirm `chapters/01.json` now has 2 paragraphs, `sequence: 2` on the new one

## 4. New character mid-story

- [ ] Keep running `step <slug>` until the model introduces a name not in your seed
      cast (or nudge it by seeding a synopsis that implies more characters are coming)
- [ ] When a `new_character` proposal appears: does rejecting it correctly leave the
      name out of `story.json` entirely? Does approving it add a new entry under
      `characters` with `introduced_in_pool: false`, `status: "active"`?
- [ ] On the *next* `step`, does the now-approved character get picked up as a
      "known" character (i.e. `DetectCharacters` treats them as existing, not new
      again)?

## 5. New location mid-story

- [ ] Same as above but for `new_location` / a place not in your seed locations —
      confirm `introduced_in_pool: false` and it doesn't get proposed as "new" again
      on the following step

## 6. Ending suggestion

- [ ] Run enough steps to plausibly approach the arc's natural end (or write a short
      synopsis on purpose to hit this sooner)
- [ ] When an `ending` proposal appears, approve it — confirm `story.json`'s `ending`
      block gets `suggested: true`, a `reason`, and the right `suggested_at_chapter`/
      `suggested_at_paragraph`
- [ ] Confirm `step` still runs fine afterward (an ending suggestion doesn't block
      further steps — there's no auto-stop, that's intentional)

## 7. `show`

- [ ] Run `python3 -m storybuilder.cli show <slug>` → prints the full story.json as
      formatted JSON, matches what's on disk

## 8. `export`

- [ ] Run `python3 -m storybuilder.cli export <slug>`
- [ ] Confirm output is a single Markdown doc: `# <title>`, then `## <chapter title>`,
      then every paragraph's prose in order, no JSON/refs leaking into the text
- [ ] Confirm it includes ALL chapters if you have more than one (create a second
      chapter manually in `story.json`/`chapters/02.json` to check this if you haven't
      reached one naturally)

## 9. Error paths

- [ ] Run `step` on a story id that doesn't exist → should error clearly, not a
      confusing traceback about missing files (currently just raises `FileNotFoundError`
      from `story_path` — note if this is too unfriendly)
- [ ] Temporarily blank `ANTHROPIC_API_KEY` in `.env` and run `step` → confirm it
      fails with an auth error rather than hanging or silently returning garbage
- [ ] If you can trigger it: does a malformed-JSON response from the model actually
      get retried (see `llm.call_json`'s retry loop)? Hard to force deliberately —
      just note if a step ever fails with "LLM did not return valid JSON after 3
      attempts" and what the raw output looked like

## Known gaps (not bugs, just not built yet)

- No `new-chapter` command — the loop always appends to the last chapter in
  `story.chapters`. Starting chapter 2 currently means hand-editing `story.json` /
  adding `chapters/02.json`.
- No undo/regenerate for a bad paragraph or a wrongly-approved fact.
- Name matching for detect-characters/detect-locations is exact-string, case-sensitive
  — a model typo or casing drift (e.g. "the Lighthouse" vs "The Lighthouse") would
  register as a brand-new entity instead of matching the existing one. Worth watching
  for in step 4/5.
