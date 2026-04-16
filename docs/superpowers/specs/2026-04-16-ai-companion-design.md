# Stress Smash AI Companion — Design Spec
**Date:** 2026-04-16
**Feature:** Sarcastic Coworker AI Companion
**Parent:** Stress Smash Core App

---

## Concept

A sarcastic coworker companion that appears during play sessions to provide dry, relatable commentary. The companion is a temporary session friend — no persistence, no loyalty system — just shows up when you need a laugh, disappears when you're done.

---

## Personality

**Type:** Sarcastic office humor  
**Voice:** Dry, deadpan, relatable  
**Tone:** "I've been there, let's roast this thing together"

**Sample Lines:**
- Opening: *"Oh, you too huh? Which one are we destroying today?"*
- Tap reactions:
  - *"Classic. You always save emails for Friday at 4pm."*
  - *"That's the spirit. Meetings don't punch back."*
  - *"Thirteen more until that spreadsheet regrets ever being created."*
- 50% progress: *"Halfway! HR would be proud of your coping mechanisms."*
- Completion: *"Look at you go. You're basically a meditation master now."*

---

## Visual Design

**Avatar:** Floating emoji face (🤖 or 🧑‍💻)  
**Speech bubbles:** Standard chat bubble style, positioned above avatar  
**Animation:** Subtle bounce/float animation, speech bubble fades in/out  
**Placement:** Bottom-right corner during play screen

---

## Behavior

### Session Flow

1. **Play screen starts** → Companion fades in with opening line
2. **Every 10 taps** → Random sarcastic comment from pool
3. **25 taps (50%)** → Milestone message
4. **50 taps (complete)** → Victory message, companion fades out
5. **Complete screen** → Companion gone (moment is over)

### Commentary Rules

- Never judge or be preachy
- Keep it under 15 words per message
- Always relate to the selected target (inbox, deadline, etc.)
- Match the burnout energy without being mean

---

## Technical Approach

### Option A: Pre-written Script Pool (Simple)
- Hardcoded arrays of sarcastic lines per target
- Random selection per trigger point
- No API cost, instant response

### Option B: AI-Generated (Dynamic)
- Use OpenAI/Claude API to generate context-aware commentary
- Sends: target type, tap count, session progress
- Returns: sarcastic one-liner
- Pros: Endless variety, more engaging
- Cons: API cost, latency, needs error handling

### Recommended: Option A for MVP, Option B as upgrade

For MVP: Use a curated pool of 10-15 lines per target that rotate randomly. This captures 80% of the value with zero API cost.

---

## Implementation Scope (MVP)

- Single companion widget
- Speech bubble with text
- Tap counter triggers
- 3-5 lines per target type
- Fade in/out animations
- No persistence between sessions

---

## Success Criteria

- User smiles/laughs at least once per session
- Return rate increases (companion creates emotional hook)
- Completes the "5-minute" promise — companion adds personality without extending session