# Coding Conventions

**Analysis Date:** 2026-04-14

## Naming Conventions

**Files:**
- Use `snake_case.dart` for all Dart files
- Examples: `reset_session_controller.dart`, `local_event_repository.dart`, `app_colors.dart`

**Classes:**
- Use `PascalCase` for class names
- Examples: `ResetSessionController`, `LocalEventRepository`, `AppException`
- Test doubles prefixed with `_`: `_FakeClock`, `_InMemoryResetRepository`
- Extension classes use `X` suffix: `ResetStageX`

**Variables and Functions:**
- Use `camelCase` for variables and methods
- Examples: `sessionId`, `currentStage`, `getOrCreateDeviceId()`
- Private members prefixed with `_`: `_resetRepository`, `_session`
- Constants may use `SCREAMING_SNAKE_CASE` for truly global constants

**Directories:**
- Use `snake_case` for directory names
- Examples: `domain/controllers/`, `data/repositories/`, `presentation/screens/`

**Types/Interfaces:**
- Repository interfaces named with `_repository.dart` suffix pattern
- Policy classes use `*_policy.dart` naming
- Enum files use singular noun: `reset_stage.dart`

## Code Style

**Formatting:**
- Tool: `dart format` (via flutter_lints)
- Config: `analysis_options.yaml` includes `package:flutter_lints/flutter.yaml`

**Imports:**
- Relative imports for same package: `../../domain/models/...`
- Package imports for external: `package:flutter/material.dart`
- No explicit ordering rules observed; follows Dart defaults

**Widget Construction:**
- Stateless widgets preferred when possible
- `const` constructor used where applicable
- Widget tests use helper functions (`_app()`, `_buildController()`) to construct test widgets

## Error Handling

**Pattern:** Self-healing with defensive defaults

**Key Pattern in `lib/features/acute_reset/data/repositories/reset_repository_impl.dart`:**
```dart
// Try-parse pattern with self-healing
try {
  final decoded = jsonDecode(raw);
  if (decoded is! Map) {
    await clearRecoverySnapshot();  // Self-heal
    return null;
  }
  // ...
} catch (_) {                        // Catch-all with discard
  await clearRecoverySnapshot();     // Self-heal
  return null;
}
```

**Exception Class:**
- Minimal `AppException` at `lib/core/errors/app_exception.dart`
- Only stores a `message` string
- Used sparingly in codebase

**Null Safety:**
- Nullable types with `?` suffix
- Null checks before operations: `if (existing != null && existing.isNotEmpty)`
- Safe navigation via `?.` not heavily used

## Async Patterns

**Await Usage:**
- All async operations use `await` explicitly (no `.then()` chains)
- Async functions marked with `async` keyword
- Repository methods return `Future<T>` signatures

**Examples from `lib/features/acute_reset/domain/controllers/reset_session_controller.dart`:**
```dart
Future<void> initialize() async {
  _deviceId = await _resetRepository.getOrCreateDeviceId();
  _trialStartAt = await _resetRepository.getOrCreateTrialStartAt();
  // ...
  _initialized = true;
  notifyListeners();
}
```

**Stream Usage:**
- Lifecycle events via `StreamSubscription<AppLifecycleState>`
- Proper cleanup in `dispose()`:
```dart
@override
void dispose() {
  _lifecycleSub?.cancel();
  super.dispose();
}
```

**Guard Clauses:**
- Early returns for invalid state:
```dart
Future<void> updateCompress(double value) async {
  if (_session.currentStage != ResetStage.compress) {
    return;
  }
  // ...
}
```

## Import Organization

**Order (Dart default):**
1. `dart:` imports
2. `package:` imports
3. Relative imports

**Example:**
```dart
import 'dart:async';

import 'package:flutter/widgets.dart';

import '../../../../core/constants/reset_constants.dart';
import '../models/reset_session.dart';
```

## State Management

**Framework:** Provider

**Usage Pattern:**
- `context.read<T>()` for triggering actions (no rebuild)
- `Consumer<T>` or `Selector<T>` for scoped rebuilds
- Controller extends `ChangeNotifier` for reactive state

**State Access Example:**
```dart
// Action - no rebuild
onPressed: () async {
  await context.read<ResetSessionController>().startReset();
  // ...
},

// Conditional rebuild using Consumer or Selector
Consumer<ResetSessionController>(
  builder: (context, controller, _) => Text('Day ${controller.trialDay}'),
)
```

## Comment Patterns

**Minimal comments observed:**
- No JSDoc/TSDoc style comments in source
- Code is self-documenting through clear naming
- Inline comments rare; used only for non-obvious logic

## Architecture Conventions

**Feature-First Structure:**
```
lib/features/acute_reset/
├── config/          # Flow configuration
├── data/            # Repository implementations
│   └── repositories/
├── domain/          # Business logic
│   ├── controllers/  # State machines
│   ├── models/       # Data classes
│   ├── policies/    # Business rules
│   └── repositories/ # Interfaces
└── presentation/    # UI layer
    ├── screens/
    └── widgets/
```

**Layer Rules:**
- Widgets render state; they do not own domain logic
- No timers inside screen widgets
- No direct storage calls from presentation widgets
- Controller owns reset flow state machine
- Repository owns persistence

---

*Convention analysis: 2026-04-14*
