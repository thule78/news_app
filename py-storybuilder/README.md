# py-storybuilder

A small Python CLI that grows a story on its own.

You set the **pool** — title, style, synopsis/arc, world facts, seed characters and
locations, constraints. The AI writes the story one step at a time, and as it writes,
it notices new facts about characters and places (new traits, goals, history) and
proposes writing them back into the story data. You approve or reject each proposed
fact before it's saved. Over time the cast and world grow past what you seeded,
without you hand-editing every character sheet — the fish move on their own, but you
still decide what's true.

Inspired by [AIStoryBuilders](../AIStoryBuilders) (C#/.NET MAUI) — see
[CONTEXT.md](CONTEXT.md) for the full design log, what's borrowed from AISB, what's
deliberately dropped for v1, and what's still undecided.

## Status

Pre-code. Requirements and design decided; implementation not started. See
CONTEXT.md for current state and next steps.

## Planned shape (v1)

- **Interface**: CLI, step-by-step (one paragraph per invocation, not batch scenes).
- **AI provider**: Claude via the Anthropic SDK.
- **Storage**: one JSON folder per story on disk — no database.
- **Growth loop**: AI drives the plot autonomously; new character/location facts
  require human approval before being written back to the story data.
