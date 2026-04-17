# AI + SVG Visual Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add animated SVG companion, particle effects, screen shake, and AI-generated target art to Stress Smash

**Architecture:** Three independent feature modules (companion, effects, targets) integrated into PlayScreen. Companion uses AnimatedBuilder, effects use CustomPainter, targets use flutter_svg for SVG rendering.

**Tech Stack:** Flutter 3.41, flutter_svg ^2.0.9, vibration ^3.1.8

---

## File Structure

```
stress_smash/lib/
├── features/
│   ├── companion/
│   │   ├── ai_companion.dart           # Main companion widget
│   │   ├── companion_face.dart          # SVG face expressions
│   │   └── companion_phrases.dart       # Sarcastic dialogue pool
│   ├── effects/
│   │   ├── particle_system.dart         # Particle burst effects
│   │   ├── screen_shake.dart           # Shake controller
│   │   └── destruction_stages.dart      # Target damage states
│   └── targets/
│       └── target_svg_assets.dart      # AI-generated SVG targets
├── widgets/
│   ├── animated_companion.dart          # Reusable companion widget
│   ├── particle_overlay.dart            # Particle canvas overlay
│   └── target_destruction.dart          # Target with damage states
├── screens/
│   └── play_screen.dart                # MODIFIED: Add all effects
```

---

## Phase 1: Animated AI Companion

### Task 1: Companion Phrases Pool

**Files:**
- Create: `lib/features/companion/companion_phrases.dart`

- [ ] **Step 1: Create sarcastic phrases pool**

```dart
class CompanionPhrases {
  static const Map<String, List<String>> byTarget = {
    'inbox': [
      "Classic. You always save emails for Friday at 4pm.",
      "That inbox is living rent-free in your head.",
      "Twenty more and it might actually hit zero.",
      "Spam folder called. It misses you.",
    ],
    'deadline': [
      "Deadlines are just suggestions with anxiety attached.",
      "Time is a construct. So is this deadline.",
      "Six more and you can tell time who's boss.",
      "The clock is ticking. PUNCH IT.",
    ],
    'spreadsheet': [
      "Ah yes, #REF! The universal spreadsheet scream.",
      "Someone definitely broke a SUM function.",
      "Those cells aren't going to highlight themselves.",
      "VLOOKUP wishes it could help you now.",
    ],
    'meeting': [
      "Meetings: because coffee breaks weren't painful enough.",
      "This meeting could have been an email.",
      "Twelve more and you'll have your afternoon back.",
      "Is it over yet? Just kidding, it never is.",
    ],
    'boss': [
      "Corporate synergy. The enemy of productivity.",
      "They're probably in a meeting about meetings.",
      "This one's for every 1:1 you didn't ask for.",
      "Performance review? More like performance destruction.",
    ],
    'monday': [
      "Monday morning blues. The struggle is real.",
      "Who decided Tuesdays weren't bad enough?",
      "It's giving... Monday. And it's giving up.",
      "Coffee count: probably not enough.",
    ],
  };

  static const List<String> openings = [
    "Oh, you too huh? Which one are we destroying today?",
    "Bad day? Same. Let's punch something.",
    "I see you've found the coping corner.",
    "Welcome to your five minutes of rage.",
  ];

  static const List<String> milestones = [
    "Halfway! HR would be proud of your coping mechanisms.",
    "Look at you go! That's some healthy aggression.",
    "You're basically a rage therapist now.",
    "The target is trembling. I can feel it.",
  ];

  static const List<String> completions = [
    "Look at you go. You're basically a meditation master now.",
    "Zen achieved. Anger released. Mission accomplished.",
    "That felt good, didn't it? No judgment.",
    "You're welcome. Come back anytime.",
  ];
}
```

- [ ] **Step 2: Run flutter analyze**

Run: `cd stress_smash && flutter analyze`

- [ ] **Step 3: Commit**

```bash
git add lib/features/companion/companion_phrases.dart
git commit -m "feat: add sarcastic companion phrases pool"
```

---

### Task 2: Companion Face SVG

**Files:**
- Create: `lib/features/companion/companion_face.dart`

- [ ] **Step 1: Create SVG face widget**

```dart
import 'package:flutter/material.dart';
import 'dart:math' as math;

enum CompanionMood { smirk, cheering, impressed, proud }

class CompanionFace extends StatelessWidget {
  final CompanionMood mood;
  final double size;

  const CompanionFace({
    super.key,
    required this.mood,
    this.size = 60,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(
        painter: _FacePainter(mood),
      ),
    );
  }
}

class _FacePainter extends CustomPainter {
  final CompanionMood mood;

  _FacePainter(this.mood);

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 - 2;

    // Face circle
    final facePaint = Paint()
      ..color = const Color(0xFFFFE0BD)
      ..style = PaintingStyle.fill;
    canvas.drawCircle(center, radius, facePaint);

    // Outline
    final outlinePaint = Paint()
      ..color = const Color(0xFF333333)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;
    canvas.drawCircle(center, radius, outlinePaint);

    // Draw eyes based on mood
    _drawEyes(canvas, size, mood);

    // Draw mouth based on mood
    _drawMouth(canvas, size, mood);
  }

  void _drawEyes(Canvas canvas, Size size, CompanionMood mood) {
    final eyePaint = Paint()
      ..color = const Color(0xFF333333)
      ..style = PaintingStyle.fill;

    final leftEyeCenter = Offset(size.width * 0.35, size.height * 0.38);
    final rightEyeCenter = Offset(size.width * 0.65, size.height * 0.38);

    switch (mood) {
      case CompanionMood.smirk:
        // Slightly raised eyebrows, neutral eyes
        canvas.drawCircle(leftEyeCenter, 4, eyePaint);
        canvas.drawCircle(rightEyeCenter, 4, eyePaint);
        break;
      case CompanionMood.cheering:
        // Star eyes
        _drawStar(canvas, leftEyeCenter, 6, eyePaint);
        _drawStar(canvas, rightEyeCenter, 6, eyePaint);
        break;
      case CompanionMood.impressed:
        // Wide eyes (O shape)
        canvas.drawCircle(leftEyeCenter, 5, eyePaint);
        canvas.drawCircle(rightEyeCenter, 5, eyePaint);
        break;
      case CompanionMood.proud:
        // Happy closed eyes (arcs)
        final arcPaint = Paint()
          ..color = const Color(0xFF333333)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2;
        canvas.drawArc(
          Rect.fromCenter(center: leftEyeCenter, width: 10, height: 6),
          0, math.pi, false, arcPaint,
        );
        canvas.drawArc(
          Rect.fromCenter(center: rightEyeCenter, width: 10, height: 6),
          0, math.pi, false, arcPaint,
        );
        break;
    }
  }

  void _drawMouth(Canvas canvas, Size size, CompanionMood mood) {
    final mouthPaint = Paint()
      ..color = const Color(0xFF333333)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2
      ..strokeCap = StrokeCap.round;

    final mouthCenter = Offset(size.width / 2, size.height * 0.62);

    switch (mood) {
      case CompanionMood.smirk:
        // Slight smirk
        final path = Path()
          ..moveTo(size.width * 0.35, mouthCenter.dy)
          ..quadraticBezierTo(
            size.width * 0.5, mouthCenter.dy + 8,
            size.width * 0.7, mouthCenter.dy - 4,
          );
        canvas.drawPath(path, mouthPaint);
        break;
      case CompanionMood.cheering:
        // Big grin
        final path = Path()
          ..moveTo(size.width * 0.3, mouthCenter.dy)
          ..quadraticBezierTo(
            size.width * 0.5, mouthCenter.dy + 15,
            size.width * 0.7, mouthCenter.dy,
          );
        canvas.drawPath(path, mouthPaint);
        break;
      case CompanionMood.impressed:
        // O mouth
        canvas.drawCircle(mouthCenter, 5, mouthPaint..style = PaintingStyle.fill);
        break;
      case CompanionMood.proud:
        // Satisfied smile
        final path = Path()
          ..moveTo(size.width * 0.35, mouthCenter.dy)
          ..quadraticBezierTo(
            size.width * 0.5, mouthCenter.dy + 10,
            size.width * 0.65, mouthCenter.dy,
          );
        canvas.drawPath(path, mouthPaint);
        break;
    }
  }

  void _drawStar(Canvas canvas, Offset center, double radius, Paint paint) {
    final path = Path();
    for (int i = 0; i < 5; i++) {
      final angle = (i * 144 - 90) * math.pi / 180;
      final point = Offset(
        center.dx + radius * math.cos(angle),
        center.dy + radius * math.sin(angle),
      );
      if (i == 0) path.moveTo(point.dx, point.dy);
      else path.lineTo(point.dx, point.dy);
    }
    path.close();
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant _FacePainter oldDelegate) {
    return oldDelegate.mood != mood;
  }
}
```

- [ ] **Step 2: Run flutter analyze**

Run: `cd stress_smash && flutter analyze`

- [ ] **Step 3: Commit**

```bash
git add lib/features/companion/companion_face.dart
git commit -m "feat: add companion face with mood expressions"
```

---

### Task 3: AI Companion Widget

**Files:**
- Create: `lib/features/companion/ai_companion.dart`

- [ ] **Step 1: Create main companion widget**

```dart
import 'dart:math';
import 'package:flutter/material.dart';
import 'companion_face.dart';
import 'companion_phrases.dart';

class AiCompanion extends StatefulWidget {
  final String targetId;
  final int tapCount;
  final int totalTaps;

  const AiCompanion({
    super.key,
    required this.targetId,
    required this.tapCount,
    required this.totalTaps,
  });

  @override
  State<AiCompanion> createState() => _AiCompanionState();
}

class _AiCompanionState extends State<AiCompanion>
    with SingleTickerProviderStateMixin {
  late AnimationController _floatController;
  late Animation<double> _floatAnimation;
  String _currentPhrase = '';
  bool _showPhrase = false;
  final Random _random = Random();
  int _lastPhraseIndex = -1;

  @override
  void initState() {
    super.initState();
    _floatController = AnimationController(
      duration: const Duration(seconds: 2),
      vsync: this,
    )..repeat(reverse: true);

    _floatAnimation = Tween<double>(begin: 0, end: 8).animate(
      CurvedAnimation(parent: _floatController, curve: Curves.easeInOut),
    );

    _showOpeningPhrase();
  }

  void _showOpeningPhrase() {
    final phrases = CompanionPhrases.openings;
    setState(() {
      _currentPhrase = phrases[_random.nextInt(phrases.length)];
      _showPhrase = true;
    });

    Future.delayed(const Duration(seconds: 3), () {
      if (mounted) setState(() => _showPhrase = false);
    });
  }

  void _maybeShowPhrase() {
    if (widget.tapCount == 0) return;

    // Show phrase every 10 taps
    if (widget.tapCount % 10 == 0 && widget.tapCount > 0) {
      _showRandomTapPhrase();
    }

    // Show milestone at 50%
    if (widget.tapCount == widget.totalTaps ~/ 2) {
      _showMilestonePhrase();
    }

    // Show completion
    if (widget.tapCount >= widget.totalTaps) {
      _showCompletionPhrase();
    }
  }

  void _showRandomTapPhrase() {
    final phrases = CompanionPhrases.byTarget[widget.targetId] ?? [];
    if (phrases.isEmpty) return;

    int index;
    do {
      index = _random.nextInt(phrases.length);
    } while (index == _lastPhraseIndex && phrases.length > 1);

    _lastPhraseIndex = index;

    setState(() {
      _currentPhrase = phrases[index];
      _showPhrase = true;
    });

    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) setState(() => _showPhrase = false);
    });
  }

  void _showMilestonePhrase() {
    final phrases = CompanionPhrases.milestones;
    setState(() {
      _currentPhrase = phrases[_random.nextInt(phrases.length)];
      _showPhrase = true;
    });

    Future.delayed(const Duration(seconds: 3), () {
      if (mounted) setState(() => _showPhrase = false);
    });
  }

  void _showCompletionPhrase() {
    final phrases = CompanionPhrases.completions;
    setState(() {
      _currentPhrase = phrases[_random.nextInt(phrases.length)];
      _showPhrase = true;
    });
  }

  @override
  void didUpdateWidget(AiCompanion oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.tapCount != widget.tapCount) {
      _maybeShowPhrase();
    }
  }

  @override
  void dispose() {
    _floatController.dispose();
    super.dispose();
  }

  CompanionMood get _mood {
    final progress = widget.tapCount / widget.totalTaps;
    if (progress >= 1.0) return CompanionMood.proud;
    if (progress >= 0.5) return CompanionMood.impressed;
    if (widget.tapCount % 5 == 0) return CompanionMood.cheering;
    return CompanionMood.smirk;
  }

  @override
  Widget build(BuildContext context) {
    return Positioned(
      bottom: 200,
      right: 20,
      child: AnimatedBuilder(
        animation: _floatAnimation,
        builder: (context, child) {
          return Transform.translate(
            offset: Offset(0, -_floatAnimation.value),
            child: child,
          );
        },
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            // Speech bubble
            AnimatedOpacity(
              opacity: _showPhrase ? 1.0 : 0.0,
              duration: const Duration(milliseconds: 200),
              child: Container(
                constraints: BoxConstraints(
                  maxWidth: MediaQuery.of(context).size.width * 0.5,
                ),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.1),
                      blurRadius: 8,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
                child: Text(
                  _currentPhrase,
                  style: const TextStyle(
                    color: Colors.black87,
                    fontSize: 14,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 8),
            // Companion face
            CompanionFace(mood: _mood, size: 70),
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 2: Run flutter analyze**

Run: `cd stress_smash && flutter analyze`

- [ ] **Step 3: Commit**

```bash
git add lib/features/companion/ai_companion.dart
git commit -m "feat: add AI companion widget with phrases"
```

---

## Phase 2: Dynamic Effects

### Task 4: Particle System

**Files:**
- Create: `lib/features/effects/particle_system.dart`

- [ ] **Step 1: Create particle system**

```dart
import 'dart:math';
import 'package:flutter/material.dart';

class Particle {
  Offset position;
  Offset velocity;
  double size;
  Color color;
  double opacity;
  double rotation;
  double rotationSpeed;

  Particle({
    required this.position,
    required this.velocity,
    required this.size,
    required this.color,
    this.opacity = 1.0,
    this.rotation = 0.0,
    this.rotationSpeed = 0.0,
  });

  void update(double dt) {
    position += velocity * dt;
    velocity = Offset(velocity.dx * 0.98, velocity.dy + 200 * dt); // gravity
    opacity -= dt * 1.5;
    size *= 0.97;
    rotation += rotationSpeed * dt;
  }

  bool get isDead => opacity <= 0 || size <= 0.5;
}

class ParticleSystem extends StatefulWidget {
  final Offset emitPosition;
  final Color color;
  final int count;
  final bool emit;

  const ParticleSystem({
    super.key,
    required this.emitPosition,
    required this.color,
    this.count = 8,
    this.emit = false,
  });

  @override
  State<ParticleSystem> createState() => ParticleSystemState();
}

class ParticleSystemState extends State<ParticleSystem>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  final List<Particle> _particles = [];
  final Random _random = Random();
  bool _shouldEmit = false;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 10),
    )..addListener(_update);
    _controller.repeat();
  }

  void emit() {
    setState(() => _shouldEmit = true);
  }

  void _update() {
    if (_shouldEmit) {
      _spawnParticles();
      _shouldEmit = false;
    }

    setState(() {
      for (final particle in _particles) {
        particle.update(0.016);
      }
      _particles.removeWhere((p) => p.isDead);
    });
  }

  void _spawnParticles() {
    for (int i = 0; i < widget.count; i++) {
      final angle = _random.nextDouble() * 2 * pi;
      final speed = _random.nextDouble() * 150 + 100;
      _particles.add(Particle(
        position: widget.emitPosition,
        velocity: Offset(cos(angle) * speed, sin(angle) * speed - 100),
        size: _random.nextDouble() * 8 + 4,
        color: widget.color,
        rotationSpeed: (_random.nextDouble() - 0.5) * 10,
      ));
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      painter: _ParticlePainter(_particles),
      size: Size.infinite,
    );
  }
}

class _ParticlePainter extends CustomPainter {
  final List<Particle> particles;

  _ParticlePainter(this.particles);

  @override
  void paint(Canvas canvas, Size size) {
    for (final particle in particles) {
      final paint = Paint()
        ..color = particle.color.withOpacity(particle.opacity.clamp(0, 1))
        ..style = PaintingStyle.fill;

      canvas.save();
      canvas.translate(particle.position.dx, particle.position.dy);
      canvas.rotate(particle.rotation);

      // Draw as small rectangle for more variety
      canvas.drawRect(
        Rect.fromCenter(
          center: Offset.zero,
          width: particle.size,
          height: particle.size * 0.6,
        ),
        paint,
      );

      canvas.restore();
    }
  }

  @override
  bool shouldRepaint(covariant _ParticlePainter oldDelegate) => true;
}
```

- [ ] **Step 2: Run flutter analyze**

Run: `cd stress_smash && flutter analyze`

- [ ] **Step 3: Commit**

```bash
git add lib/features/effects/particle_system.dart
git commit -m "feat: add particle system for tap effects"
```

---

### Task 5: Screen Shake

**Files:**
- Create: `lib/features/effects/screen_shake.dart`

- [ ] **Step 1: Create screen shake widget**

```dart
import 'dart:math';
import 'package:flutter/material.dart';

class ScreenShake extends StatefulWidget {
  final Widget child;
  final bool shake;
  final double intensity;

  const ScreenShake({
    super.key,
    required this.child,
    required this.shake,
    this.intensity = 5.0,
  });

  @override
  State<ScreenShake> createState() => ScreenShakeState();
}

class ScreenShakeState extends State<ScreenShake>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  final Random _random = Random();
  double _offsetX = 0;
  double _offsetY = 0;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 100),
    )..addListener(_update);
  }

  void _update() {
    if (_controller.isAnimating) {
      setState(() {
        _offsetX = (_random.nextDouble() - 0.5) * widget.intensity * 2;
        _offsetY = (_random.nextDouble() - 0.5) * widget.intensity;
      });
    }
  }

  void trigger() {
    _controller.forward(from: 0);
  }

  @override
  void didUpdateWidget(ScreenShake oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.shake && !oldWidget.shake) {
      trigger();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Transform.translate(
      offset: Offset(_offsetX, _offsetY),
      child: widget.child,
    );
  }
}
```

- [ ] **Step 2: Run flutter analyze**

Run: `cd stress_smash && flutter analyze`

- [ ] **Step 3: Commit**

```bash
git add lib/features/effects/screen_shake.dart
git commit -m "feat: add screen shake effect"
```

---

### Task 6: Target Destruction Stages

**Files:**
- Create: `lib/features/effects/destruction_stages.dart`

- [ ] **Step 1: Create destruction state widget**

```dart
import 'dart:math';
import 'package:flutter/material.dart';
import '../../theme/app_theme.dart';

enum DestructionLevel { intact, cracked, damaged, critical, destroyed }

class DestructionTarget extends StatefulWidget {
  final String emoji;
  final String name;
  final int tapCount;
  final int totalTaps;
  final Color accentColor;

  const DestructionTarget({
    super.key,
    required this.emoji,
    required this.name,
    required this.tapCount,
    required this.totalTaps,
    this.accentColor = AppTheme.primary,
  });

  @override
  State<DestructionTarget> createState() => _DestructionTargetState();
}

class _DestructionTargetState extends State<DestructionTarget>
    with SingleTickerProviderStateMixin {
  late AnimationController _shakeController;
  final Random _random = Random();

  DestructionLevel get _level {
    final progress = widget.tapCount / widget.totalTaps;
    if (progress >= 1.0) return DestructionLevel.destroyed;
    if (progress >= 0.8) return DestructionLevel.critical;
    if (progress >= 0.5) return DestructionLevel.damaged;
    if (progress >= 0.2) return DestructionLevel.cracked;
    return DestructionLevel.intact;
  }

  double get _scale {
    final progress = widget.tapCount / widget.totalTaps;
    return 1.0 - (progress * 0.3);
  }

  double get _opacity {
    final progress = widget.tapCount / widget.totalTaps;
    return 1.0 - (progress * 0.6);
  }

  double get _shake {
    final progress = widget.tapCount / widget.totalTaps;
    if (progress < 0.2) return 0;
    if (progress < 0.5) return 2;
    if (progress < 0.8) return 4;
    return 8;
  }

  @override
  void initState() {
    super.initState();
    _shakeController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 100),
    )..repeat();
  }

  @override
  void dispose() {
    _shakeController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _shakeController,
      builder: (context, child) {
        double offsetX = 0;
        double offsetY = 0;
        if (_shake > 0) {
          offsetX = (_random.nextDouble() - 0.5) * _shake;
          offsetY = (_random.nextDouble() - 0.5) * _shake;
        }

        return Transform.translate(
          offset: Offset(offsetX, offsetY),
          child: Transform.scale(
            scale: _scale,
            child: AnimatedOpacity(
              opacity: _opacity.clamp(0.0, 1.0),
              duration: const Duration(milliseconds: 100),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Stack(
                    alignment: Alignment.center,
                    children: [
                      // Cracks overlay based on level
                      if (_level.index >= DestructionLevel.cracked.index)
                        _CracksOverlay(level: _level),
                      // Main emoji
                      Text(
                        widget.emoji,
                        style: const TextStyle(fontSize: 120),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Text(
                    widget.name,
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

class _CracksOverlay extends StatelessWidget {
  final DestructionLevel level;

  const _CracksOverlay({required this.level});

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      size: const Size(140, 140),
      painter: _CracksPainter(level),
    );
  }
}

class _CracksPainter extends CustomPainter {
  final DestructionLevel level;

  _CracksPainter(this.level);

  @override
  void paint(Canvas canvas, Size size) {
    if (level.index < DestructionLevel.cracked.index) return;

    final paint = Paint()
      ..color = Colors.white.withOpacity(0.7)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;

    final center = Offset(size.width / 2, size.height / 2);

    // Draw cracks based on level
    if (level.index >= DestructionLevel.cracked.index) {
      _drawCrack(canvas, center, paint, -30, 50);
      _drawCrack(canvas, center, paint, 45, 40);
    }

    if (level.index >= DestructionLevel.damaged.index) {
      _drawCrack(canvas, center, paint, 10, 55);
      _drawCrack(canvas, center, paint, -60, 35);
    }

    if (level.index >= DestructionLevel.critical.index) {
      _drawCrack(canvas, center, paint, 80, 45);
      _drawCrack(canvas, center, paint, -45, 60);
    }
  }

  void _drawCrack(Canvas canvas, Offset center, Paint paint, double angle, double length) {
    final startX = center.dx;
    final startY = center.dy;
    final endX = center.dx + cos(angle * pi / 180) * length;
    final endY = center.dy + sin(angle * pi / 180) * length;

    final path = Path()
      ..moveTo(startX, startY)
      ..lineTo(endX, endY)
      ..lineTo(endX + 10, endY + 5)
      ..moveTo(endX, endY)
      ..lineTo(endX - 5, endY + 8);

    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant _CracksPainter oldDelegate) => false;
}
```

- [ ] **Step 2: Run flutter analyze**

Run: `cd stress_smash && flutter analyze`

- [ ] **Step 3: Commit**

```bash
git add lib/features/effects/destruction_stages.dart
git commit -m "feat: add target destruction stages with cracks"
```

---

## Phase 3: AI-Generated Targets

### Task 7: Target SVG Assets

**Files:**
- Create: `lib/features/targets/target_svg_assets.dart`

- [ ] **Step 1: Create SVG asset provider**

```dart
import 'package:flutter/material.dart';

class TargetAsset {
  final String id;
  final String name;
  final String emoji;
  final Color accentColor;

  const TargetAsset({
    required this.id,
    required this.name,
    required this.emoji,
    required this.accentColor,
  });
}

class TargetSvgAssets {
  static const Map<String, TargetAsset> targets = {
    'inbox': TargetAsset(
      id: 'inbox',
      name: 'Inbox Zero',
      emoji: '📧',
      accentColor: Color(0xFFFF6B6B),
    ),
    'deadline': TargetAsset(
      id: 'deadline',
      name: 'Deadline',
      emoji: '⏰',
      accentColor: Color(0xFFFFE66D),
    ),
    'spreadsheet': TargetAsset(
      id: 'spreadsheet',
      name: 'Spreadsheet',
      emoji: '📊',
      accentColor: Color(0xFF4ECDC4),
    ),
    'meeting': TargetAsset(
      id: 'meeting',
      name: 'Meeting',
      emoji: '📅',
      accentColor: Color(0xFF95E1D3),
    ),
    'boss': TargetAsset(
      id: 'boss',
      name: 'The Boss',
      emoji: '👔',
      accentColor: Color(0xFFDDA0DD),
    ),
    'monday': TargetAsset(
      id: 'monday',
      name: 'Monday',
      emoji: '😩',
      accentColor: Color(0xFFA8D8EA),
    ),
  };

  static TargetAsset? getById(String id) => targets[id];
}
```

- [ ] **Step 2: Run flutter analyze**

Run: `cd stress_smash && flutter analyze`

- [ ] **Step 3: Commit**

```bash
git add lib/features/targets/target_svg_assets.dart
git commit -m "feat: add target SVG assets provider"
```

---

### Task 8: Integrate All Effects into PlayScreen

**Files:**
- Modify: `lib/screens/play_screen.dart`

- [ ] **Step 1: Update PlayScreen with all effects**

```dart
import 'package:flutter/material.dart';
import '../models/stress_target.dart';
import '../services/haptic_service.dart';
import '../theme/app_theme.dart';
import '../features/companion/ai_companion.dart';
import '../features/effects/particle_system.dart';
import '../features/effects/screen_shake.dart';
import '../features/effects/destruction_stages.dart';
import '../features/targets/target_svg_assets.dart';
import 'complete_screen.dart';

class PlayScreen extends StatefulWidget {
  final StressTarget target;

  const PlayScreen({super.key, required this.target});

  @override
  State<PlayScreen> createState() => _PlayScreenState();
}

class _PlayScreenState extends State<PlayScreen> {
  int _tapCount = 0;
  static const int _targetTaps = 50;
  final GlobalKey<ParticleSystemState> _particleKey = GlobalKey();
  final GlobalKey<ScreenShakeState> _shakeKey = GlobalKey();

  void _handleTap(TapDownDetails details) {
    HapticService.impact();
    
    // Trigger particle effect
    _particleKey.currentState?.emit();
    
    // Trigger screen shake every 5 taps
    if (_tapCount > 0 && _tapCount % 5 == 0) {
      _shakeKey.currentState?.trigger();
    }
    
    setState(() {
      _tapCount++;
    });

    if (_tapCount >= _targetTaps) {
      Future.delayed(const Duration(milliseconds: 300), () {
        if (mounted) {
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(builder: (_) => const CompleteScreen()),
          );
        }
      });
    }
  }

  double get _progress => _tapCount / _targetTaps;
  
  Color get _accentColor => 
      TargetSvgAssets.getById(widget.target.id)?.accentColor ?? AppTheme.primary;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: _handleTap,
      child: Scaffold(
        body: Stack(
          children: [
            Container(color: AppTheme.background),
            
            // Screen shake wrapper
            ScreenShake(
              key: _shakeKey,
              shake: _tapCount > 0,
              child: Center(
                child: DestructionTarget(
                  emoji: widget.target.emoji,
                  name: widget.target.name,
                  tapCount: _tapCount,
                  totalTaps: _targetTaps,
                  accentColor: _accentColor,
                ),
              ),
            ),
            
            // Particle overlay
            Positioned.fill(
              child: IgnorePointer(
                child: ParticleSystem(
                  key: _particleKey,
                  emitPosition: Offset(
                    MediaQuery.of(context).size.width / 2,
                    MediaQuery.of(context).size.height / 2 - 50,
                  ),
                  color: _accentColor,
                  count: 6,
                ),
              ),
            ),
            
            // AI Companion
            AiCompanion(
              targetId: widget.target.id,
              tapCount: _tapCount,
              totalTaps: _targetTaps,
            ),
            
            // Progress bar
            Positioned(
              bottom: 80,
              left: 40,
              right: 40,
              child: Column(
                children: [
                  LinearProgressIndicator(
                    value: _progress,
                    backgroundColor: AppTheme.surface,
                    valueColor: AlwaysStoppedAnimation(_accentColor),
                    minHeight: 8,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    "$_tapCount / $_targetTaps",
                    style: Theme.of(context).textTheme.bodyLarge,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    "TAP!",
                    style: TextStyle(
                      color: _accentColor,
                      fontSize: 24,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 2: Run flutter analyze**

Run: `cd stress_smash && flutter analyze`

- [ ] **Step 3: Build for verification**

Run: `cd stress_smash && flutter build macos`

- [ ] **Step 4: Commit**

```bash
git add lib/screens/play_screen.dart
git commit -m "feat: integrate all visual effects into play screen"
```

---

## Verification Checklist

- [ ] Companion appears with opening phrase
- [ ] Companion reacts with sarcastic comments every 10 taps
- [ ] Companion shows milestone at 50% progress
- [ ] Companion face changes expression based on progress
- [ ] Particles emit on every tap
- [ ] Screen shakes every 5 taps
- [ ] Target shows cracks at 20%+ progress
- [ ] Target shakes more intensely as progress increases
- [ ] Target fades as progress increases
- [ ] Navigation to complete screen works
- [ ] macOS build succeeds