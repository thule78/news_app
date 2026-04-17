# Stress Smash AI + SVG Visual Enhancement
**Date:** 2026-04-16
**Feature:** Full visual upgrade with SVG animation + AI
**Parent:** Stress Smash Core App

---

## Overview

Three visual enhancements that transform the app from "tapping on emojis" to an engaging, dynamic experience:

1. **Animated AI Companion** — SVG character with reactive facial expressions
2. **Dynamic Destruction FX** — Particles, screen shake, impact effects
3. **AI-Generated Targets** — Custom angry art for stress targets

---

## 1. Animated AI Companion

### Concept
An SVG-based office worker character that reacts to your taps with facial expressions and body language.

### Visual Design
- **Style:** Flat illustration, minimal, expressive
- **Size:** ~100x150px floating in corner
- **Expressions:** 4 states based on tap intensity

| Tap Intensity | Expression | Visual |
|---------------|------------|--------|
| Normal tap | Smirk | 👉 😏 |
| Hard/fast tap | Cheering | 👉 🤩 |
| 50% milestone | Impressed | 👉 😲 |
| Completion | Proud | 👉 😊 |

### SVG Implementation
```svg
<!-- Base character structure -->
<svg viewBox="0 0 100 150">
  <!-- Head with swappable face elements -->
  <circle cx="50" cy="40" r="30" fill="#FFE0BD"/>
  <!-- Face elements as separate paths, shown/hidden based on state -->
  <g id="face-smirk">...</g>
  <g id="face-cheering">...</g>
  <!-- Body -->
  <rect x="30" y="75" width="40" height="60" fill="#4A90D9"/>
  <!-- Arms that animate based on tap -->
  <g id="arms-normal">...</g>
  <g id="arms-cheering">...</g>
</svg>
```

### Animation
- **Idle:** Subtle float/bob animation (2s loop)
- **On tap:** Quick bounce + expression flash
- **Milestone:** Arms raise + celebration bounce
- **Transition:** 200ms crossfade between expressions

---

## 2. Dynamic Destruction FX

### Concept
Visual feedback that makes every tap feel impactful — particles, screen effects, and satisfying destruction animation on the target.

### Effects

#### Screen Shake
- **Trigger:** Every 5th tap
- **Intensity:** Subtle (2-3px) to moderate (5-7px)
- **Duration:** 100ms
- **Direction:** Random horizontal + slight vertical

#### Particle Burst
- **Trigger:** Every tap
- **Type:** Small colored circles/shapes matching target color
- **Count:** 5-8 particles per tap
- **Animation:** Explode outward, fade + shrink over 400ms
- **Physics:** Slight gravity, random velocity

#### Target Destruction Stages
Target visually degrades as taps accumulate:

| Progress | Visual State |
|----------|--------------|
| 0-20% | Intact emoji |
| 20-50% | Cracks appear, slight tilt |
| 50-80% | Broken, shaking, cracks |
| 80-99% | Near destruction, heavy shake |
| 100% | Explodes into particles, gone |

#### Impact Flash
- **Trigger:** Every tap
- **Effect:** Brief white/colored flash at impact point
- **Duration:** 50ms
- **Color:** Matches target theme

### SVG Particle System
```dart
class Particle {
  Offset position;
  Offset velocity;
  double size;
  Color color;
  double opacity;
  double rotation;
}

class ParticleSystem {
  List<Particle> particles = [];

  void emit(Offset origin, int count, Color color) {
    for (int i = 0; i < count; i++) {
      particles.add(Particle(
        position: origin,
        velocity: Offset.random() * 200,
        size: Random().nextDouble() * 10 + 5,
        color: color,
      ));
    }
  }

  void update(double dt) {
    // Apply physics, remove dead particles
  }

  void render(Canvas canvas) {
    // Draw all particles
  }
}
```

---

## 3. AI-Generated Targets

### Concept
Instead of static emojis, generate custom "angry" versions of stress targets using AI image generation.

### Targets to Generate

| Target | Base Concept | Angry Version |
|--------|--------------|--------------|
| Inbox | Email icon | Angry red envelope, flames, spam |
| Deadline | Clock | Clock with X eyes, cracks |
| Spreadsheet | Excel grid | Grid on fire, #ERROR everywhere |
| Meeting | Calendar | Calendar with sweat drops, crying |
| Boss | Suit icon | Angry suit with steam from ears |
| Monday | Sad face | Chaos Monday face, tornado hair |

### AI Generation Strategy

**Option A: Pre-generate (Recommended for MVP)**
- Generate all 6 targets once using DALL-E/Midjourney
- Store as SVG or PNG assets
- No runtime AI calls, instant loading

**Option B: Runtime Generation**
- Generate on first play of each target
- Cache locally for subsequent plays
- Show loading spinner on first generation

**Option C: Hybrid**
- Use simple SVG/CSS for base version
- Offer "AI Upgrade" in settings for angry versions

### Recommended: Option A for launch, Option B as feature

### Generation Prompts
```
"Inbox": "Angry email inbox icon, red and steaming, annoyed expression, flat design, simple vector, colorful background"
"Deadline": "Clock with angry face, X for eyes, cracks and stress lines, flat design, simple vector"
"Spreadsheet": "Spreadsheet on fire, red grid cells, ERROR messages, flat design, simple vector"
"Meeting": "Calendar with sad worried face, sweat drops, tears, flat design, simple vector"
"Boss": "Business suit with angry expression, steam from ears, flat design, simple vector"
"Monday": "Chaotic monday face, messy hair like tornado, stressed expression, flat design, simple vector"
```

---

## Technical Architecture

### File Structure
```
lib/
├── features/
│   ├── companion/
│   │   ├── ai_companion.dart
│   │   ├── companion_face.dart
│   │   └── companion_phrases.dart
│   ├── effects/
│   │   ├── particle_system.dart
│   │   ├── screen_shake.dart
│   │   └── impact_flash.dart
│   └── targets/
│       ├── ai_target_generator.dart
│       └── target_assets.dart
├── widgets/
│   ├── animated_companion.dart
│   ├── particle_overlay.dart
│   └── target_destruction.dart
```

### Dependencies
```yaml
dependencies:
  flutter:
    sdk: flutter
  flutter_svg: ^2.0.9  # SVG rendering
  # For AI image generation (if runtime):
  # volcengine_imagex: ^1.0.0  # Alternative to OpenAI DALL-E
```

### State Management
- Companion state: `ValueNotifier<CompanionState>`
- Particle system: Independent update loop
- Screen shake: `AnimatedBuilder` with random offset
- Target destruction: `AnimationController` tied to tap progress

---

## Performance Considerations

1. **Particle limit:** Max 50 active particles at once
2. **SVG complexity:** Keep paths under 500 points per element
3. **AI caching:** Store generated images locally, never regenerate
4. **Animation frame rate:** Target 60fps, reduce to 30fps if needed
5. **Memory:** Dispose particles immediately when off-screen

---

## Success Metrics

- Session duration increases (users enjoy watching effects)
- Tap count increases (satisfying feedback loop)
- User recordings/sharing (dynamic effects are screenshot-worthy)
- "This feels real" qualitative feedback

---

## Implementation Order

1. **Phase 1:** SVG companion with expressions (lowest risk, highest impact)
2. **Phase 2:** Particle system + screen shake (technical showcase)
3. **Phase 3:** AI-generated target art (wow factor, API integration)