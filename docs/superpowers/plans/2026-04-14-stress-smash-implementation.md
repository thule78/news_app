# Stress Smash Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a 5-minute tap-based stress relief game in Flutter for burned-out office workers.

**Architecture:** Screen-based navigation (Open → Target Select → Play → Complete). State managed via StatefulWidgets with a simple GameState object. Haptic feedback on every tap. No backend, local analytics only.

**Tech Stack:** Flutter 3.41, Dart, vibration package for haptics

---

## File Structure

```
stress_smash/lib/
├── main.dart                    # Entry point
├── app.dart                     # MaterialApp config
├── screens/
│   ├── open_screen.dart         # Opening acknowledgment
│   ├── target_select_screen.dart # Stress target grid
│   ├── play_screen.dart         # Tap/smash gameplay
│   └── complete_screen.dart     # Victory screen
├── widgets/
│   └── stress_target_card.dart  # Target selection card
├── models/
│   └── stress_target.dart       # Target data model
├── services/
│   └── haptic_service.dart      # Haptic feedback
├── theme/
│   └── app_theme.dart           # Colors, typography
└── constants/
    └── strings.dart             # All text copy
```

---

## Tasks

### Task 1: Project Setup

**Files:**
- Modify: `stress_smash/pubspec.yaml`

- [ ] **Step 1: Add dependencies to pubspec.yaml**

```yaml
dependencies:
  flutter:
    sdk: flutter
  vibration: ^2.0.1  # For haptic feedback
```

Run: `cd stress_smash && flutter pub add vibration`

---

### Task 2: Theme & Constants

**Files:**
- Create: `stress_smash/lib/theme/app_theme.dart`
- Create: `stress_smash/lib/constants/strings.dart`

- [ ] **Step 1: Create app theme with colors**

```dart
import 'package:flutter/material.dart';

class AppTheme {
  static const Color primary = Color(0xFFFF6B6B);      // Energetic red
  static const Color secondary = Color(0xFF4ECDC4);    // Teal accent
  static const Color background = Color(0xFF1A1A2E);    // Dark purple-black
  static const Color surface = Color(0xFF16213E);       // Card background
  static const Color textPrimary = Color(0xFFFFFFFF);
  static const Color textSecondary = Color(0xFFB8B8D1);
  
  static ThemeData get darkTheme => ThemeData(
    brightness: Brightness.dark,
    scaffoldBackgroundColor: background,
    colorScheme: const ColorScheme.dark(
      primary: primary,
      secondary: secondary,
      surface: surface,
    ),
    textTheme: const TextTheme(
      headlineLarge: TextStyle(
        fontSize: 32,
        fontWeight: FontWeight.bold,
        color: textPrimary,
      ),
      headlineMedium: TextStyle(
        fontSize: 24,
        fontWeight: FontWeight.w600,
        color: textPrimary,
      ),
      bodyLarge: TextStyle(
        fontSize: 18,
        color: textSecondary,
      ),
    ),
  );
}
```

- [ ] **Step 2: Create strings constants**

```dart
class AppStrings {
  // Open screen
  static const String openTitle = "Had a day?";
  static const String openSubtitle = "Let's punch something.";
  static const String openCTA = "Tap to start";
  
  // Target select
  static const String selectTitle = "What's bothering you?";
  
  // Play screen
  static const String tapToSmash = "TAP!";
  
  // Complete screen
  static const String completeTitle = "Better?";
  static const String completeSubtitle = "You still hate your job, but your hands don't have to.";
  static const String completeCTA = "Again?";
  
  // Targets
  static const List<Map<String, String>> targets = [
    {'id': 'inbox', 'name': 'Inbox Zero', 'emoji': '📧'},
    {'id': 'deadline', 'name': 'Deadline', 'emoji': '⏰'},
    {'id': 'spreadsheet', 'name': 'Spreadsheet', 'emoji': '📊'},
    {'id': 'meeting', 'name': 'Meeting', 'emoji': '📅'},
    {'id': 'boss', 'name': 'The Boss', 'emoji': '👔'},
    {'id': 'monday', 'name': 'Monday', 'emoji': '😩'},
  ];
}
```

---

### Task 3: Data Model

**Files:**
- Create: `stress_smash/lib/models/stress_target.dart`

- [ ] **Step 1: Create StressTarget model**

```dart
class StressTarget {
  final String id;
  final String name;
  final String emoji;
  
  const StressTarget({
    required this.id,
    required this.name,
    required this.emoji,
  });
  
  factory StressTarget.fromMap(Map<String, String> map) {
    return StressTarget(
      id: map['id']!,
      name: map['name']!,
      emoji: map['emoji']!,
    );
  }
}
```

---

### Task 4: Services

**Files:**
- Create: `stress_smash/lib/services/haptic_service.dart`

- [ ] **Step 1: Create HapticService**

```dart
import 'package:vibration/vibration.dart';

class HapticService {
  static Future<void> impact() async {
    final hasVibrator = await Vibration.hasVibrator();
    if (hasVibrator == true) {
      Vibration.vibrate(duration: 50, amplitude: 128);
    }
  }
  
  static Future<void> heavyImpact() async {
    final hasVibrator = await Vibration.hasVibrator();
    if (hasVibrator == true) {
      Vibration.vibrate(duration: 100, amplitude: 255);
    }
  }
}
```

---

### Task 5: Screens - Open Screen

**Files:**
- Create: `stress_smash/lib/screens/open_screen.dart`

- [ ] **Step 1: Create OpenScreen**

```dart
import 'package:flutter/material.dart';
import '../constants/strings.dart';
import 'target_select_screen.dart';

class OpenScreen extends StatelessWidget {
  const OpenScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => const TargetSelectScreen()),
      ),
      child: Scaffold(
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                AppStrings.openTitle,
                style: Theme.of(context).textTheme.headlineLarge,
              ),
              const SizedBox(height: 16),
              Text(
                AppStrings.openSubtitle,
                style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                  color: Theme.of(context).colorScheme.primary,
                ),
              ),
              const SizedBox(height: 80),
              Text(
                AppStrings.openCTA,
                style: Theme.of(context).textTheme.bodyLarge,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
```

---

### Task 6: Screens - Target Select

**Files:**
- Create: `stress_smash/lib/screens/target_select_screen.dart`
- Create: `stress_smash/lib/widgets/stress_target_card.dart`

- [ ] **Step 1: Create StressTargetCard widget**

```dart
import 'package:flutter/material.dart';
import '../models/stress_target.dart';
import '../theme/app_theme.dart';

class StressTargetCard extends StatelessWidget {
  final StressTarget target;
  final VoidCallback onTap;

  const StressTargetCard({
    super.key,
    required this.target,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: AppTheme.primary.withOpacity(0.3),
            width: 2,
          ),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              target.emoji,
              style: const TextStyle(fontSize: 48),
            ),
            const SizedBox(height: 8),
            Text(
              target.name,
              style: const TextStyle(
                color: AppTheme.textPrimary,
                fontSize: 16,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 2: Create TargetSelectScreen**

```dart
import 'package:flutter/material.dart';
import '../constants/strings.dart';
import '../models/stress_target.dart';
import '../widgets/stress_target_card.dart';
import 'play_screen.dart';

class TargetSelectScreen extends StatelessWidget {
  const TargetSelectScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final targets = AppStrings.targets
        .map((t) => StressTarget.fromMap(t))
        .toList();

    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                AppStrings.selectTitle,
                style: Theme.of(context).textTheme.headlineLarge,
              ),
              const SizedBox(height: 24),
              Expanded(
                child: GridView.builder(
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 2,
                    crossAxisSpacing: 16,
                    mainAxisSpacing: 16,
                    childAspectRatio: 1.2,
                  ),
                  itemCount: targets.length,
                  itemBuilder: (context, index) {
                    final target = targets[index];
                    return StressTargetCard(
                      target: target,
                      onTap: () => Navigator.push(
                        context,
                        MaterialPageRoute(
                          builder: (_) => PlayScreen(target: target),
                        ),
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
```

---

### Task 7: Screens - Play Screen

**Files:**
- Create: `stress_smash/lib/screens/play_screen.dart`

- [ ] **Step 1: Create PlayScreen**

```dart
import 'package:flutter/material.dart';
import '../models/stress_target.dart';
import '../services/haptic_service.dart';
import '../theme/app_theme.dart';
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

  void _handleTap() {
    HapticService.impact();
    setState(() {
      _tapCount++;
    });
    
    if (_tapCount >= _targetTaps) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const CompleteScreen()),
      );
    }
  }

  double get _progress => _tapCount / _targetTaps;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: _handleTap,
      child: Scaffold(
        body: Stack(
          children: [
            // Background
            Container(color: AppTheme.background),
            
            // Target with damage effect
            Center(
              child: AnimatedScale(
                scale: 1.0 - (_progress * 0.5),
                duration: const Duration(milliseconds: 100),
                child: AnimatedOpacity(
                  opacity: 1.0 - (_progress * 0.7),
                  duration: const Duration(milliseconds: 100),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        widget.target.emoji,
                        style: const TextStyle(fontSize: 120),
                      ),
                      const SizedBox(height: 16),
                      Text(
                        widget.target.name,
                        style: Theme.of(context).textTheme.headlineMedium,
                      ),
                    ],
                  ),
                ),
              ),
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
                    valueColor: const AlwaysStoppedAnimation(AppTheme.primary),
                    minHeight: 8,
                    borderRadius: BorderRadius.circular(4),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    "$_tapCount / $targetTaps",
                    style: Theme.of(context).textTheme.bodyLarge,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    "TAP!",
                    style: TextStyle(
                      color: AppTheme.primary,
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

---

### Task 8: Screens - Complete Screen

**Files:**
- Create: `stress_smash/lib/screens/complete_screen.dart`

- [ ] **Step 1: Create CompleteScreen**

```dart
import 'package:flutter/material.dart';
import '../constants/strings.dart';
import '../theme/app_theme.dart';
import 'target_select_screen.dart';

class CompleteScreen extends StatelessWidget {
  const CompleteScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () => Navigator.pushAndRemoveUntil(
        context,
        MaterialPageRoute(builder: (_) => const TargetSelectScreen()),
        (route) => false,
      ),
      child: Scaffold(
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Text(
                  "💪",
                  style: TextStyle(fontSize: 80),
                ),
                const SizedBox(height: 32),
                Text(
                  AppStrings.completeTitle,
                  style: Theme.of(context).textTheme.headlineLarge,
                ),
                const SizedBox(height: 16),
                Text(
                  AppStrings.completeSubtitle,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: AppTheme.textSecondary,
                  ),
                ),
                const SizedBox(height: 64),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 24,
                    vertical: 12,
                  ),
                  decoration: BoxDecoration(
                    border: Border.all(color: AppTheme.primary, width: 2),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    AppStrings.completeCTA,
                    style: TextStyle(
                      color: AppTheme.primary,
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
```

---

### Task 9: App Configuration

**Files:**
- Create: `stress_smash/lib/app.dart`
- Modify: `stress_smash/lib/main.dart`

- [ ] **Step 1: Create app.dart**

```dart
import 'package:flutter/material.dart';
import 'screens/open_screen.dart';
import 'theme/app_theme.dart';

class StressSmashApp extends StatelessWidget {
  const StressSmashApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Stress Smash',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      home: const OpenScreen(),
    );
  }
}
```

- [ ] **Step 2: Update main.dart**

```dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'app.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
  ]);
  runApp(const StressSmashApp());
}
```

---

### Task 10: Build & Verify

- [ ] **Step 1: Get dependencies**

Run: `cd stress_smash && flutter pub get`

- [ ] **Step 2: Build for iOS simulator**

Run: `cd stress_smash && flutter build ios --simulator --no-codesign`

Expected: Build succeeds with `stress_smash/build/ios/iphonesimulator/Runner.app`

- [ ] **Step 3: Run on simulator**

Run: `cd stress_smash && flutter run -d "iPhone 16"`

---

## Verification Checklist

- [ ] Open screen shows "Had a day?" with tap to continue
- [ ] Target select shows 6 stress targets with emojis
- [ ] Tapping a target navigates to play screen
- [ ] Each tap triggers haptic feedback
- [ ] Progress bar fills as you tap
- [ ] Target shrinks/fades as progress increases
- [ ] After 50 taps, navigates to complete screen
- [ ] Complete screen shows victory message and "Again?" option
- [ ] "Again?" returns to target select (not open screen)
- [ ] iOS simulator build completes without errors
