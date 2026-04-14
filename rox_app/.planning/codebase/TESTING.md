# Testing Patterns

**Analysis Date:** 2026-04-14

## Test Framework

**Runner:**
- Flutter Test (`flutter_test` SDK)
- Integration Test (`integration_test` SDK)

**Dependencies in `pubspec.yaml`:**
```yaml
dev_dependencies:
  flutter_test:
    sdk: flutter
  integration_test:
    sdk: flutter
```

**Mocking:**
- No external mocking library (mockito, etc.)
- In-memory fake implementations
- `SharedPreferences.setMockInitialValues()` for storage tests

## Test File Organization

**Location Pattern:**
- Unit tests: `test/unit/`
- Widget tests: `test/widget/`
- Integration tests: `integration_test/` (top-level)

**Naming:**
- Test files: `*_test.dart`
- Match source file name: `reset_session_controller_test.dart` tests `reset_session_controller.dart`

**Directory Structure:**
```
test/
├── unit/
│   ├── reset_session_controller_test.dart
│   └── reset_repository_impl_test.dart
└── widget/
    └── reset_entry_screen_test.dart

integration_test/
└── app_flow_test.dart
```

## Test Structure

### Unit Tests

**Pattern:** Arrange-Act-Assert (AAA) with inline fakes

**Structure:**
```dart
class _FakeClock extends AppClock {
  _FakeClock(this.value);
  DateTime value;

  @override
  DateTime now() => value;
}

class _FakeIdGenerator extends IdGenerator {
  _FakeIdGenerator(this.values);
  final List<String> values;
  int _index = 0;

  @override
  String nextId() {
    final next = values[_index];
    _index = (_index + 1).clamp(0, values.length - 1);
    return next;
  }
}

class _InMemoryResetRepository implements ResetRepository {
  // ... implementations
}

void main() {
  test('test description', () async {
    // Arrange
    final resetRepository = _InMemoryResetRepository();
    final eventRepository = _InMemoryEventRepository();
    final controller = ResetSessionController(...);

    // Act
    await controller.initialize();

    // Assert
    expect(controller.session.currentStage, ResetStage.entry);
  });
}
```

**Key Characteristics:**
- Fake implementations prefixed with `_` (e.g., `_FakeClock`)
- Lists as ID generators with index tracking
- In-memory repositories for isolated testing
- DateTime values are mutable (`value` property) to simulate time passing

### Widget Tests

**Pattern:** Controller-first, widget-under-test

**Helper Functions:**
```dart
Future<ResetSessionController> _buildController(
    {RecoverySnapshot? snapshot, DateTime? now}) async {
  final repo = _InMemoryResetRepository()..snapshot = snapshot;
  final controller = ResetSessionController(
    resetRepository: repo,
    eventRepository: _InMemoryEventRepository(),
    clock: _FakeClock(now ?? DateTime.utc(2026, 4, 13, 8, 0, 0)),
    idGenerator: _FakeIdGenerator('s1'),
  );
  await controller.initialize();
  return controller;
}

Widget _app(ResetSessionController controller,
    {String initialRoute = RouteNames.resetEntry}) {
  return ChangeNotifierProvider<ResetSessionController>.value(
    value: controller,
    child: MaterialApp(
      routes: {...},
      initialRoute: initialRoute,
    ),
  );
}
```

**Test Pattern:**
```dart
testWidgets('entry screen shows one strong CTA', (tester) async {
  final controller = await _buildController();

  await tester.pumpWidget(_app(controller));

  expect(find.text('Start reset'), findsOneWidget);
  expect(find.text('Pull it in.'), findsOneWidget);
});
```

### Integration Tests

**Pattern:** Real bootstrap, full app flow

**Setup:**
```dart
IntegrationTestWidgetsFlutterBinding.ensureInitialized();

void main() {
  testWidgets('first launch to completion and skip feedback', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final dependencies = await AppBootstrap().initialize();

    await tester.pumpWidget(RoxApp(dependencies: dependencies));
    await tester.pumpAndSettle();

    // Test flow...
  });
}
```

**Characteristics:**
- Uses `IntegrationTestWidgetsFlutterBinding.ensureInitialized()`
- Real `AppBootstrap()` initialization
- `SharedPreferences.setMockInitialValues()` for state
- Tests complete user flows end-to-end

## Mocking Patterns

### Fake Implementations

**Clock Fake:**
```dart
class _FakeClock extends AppClock {
  _FakeClock(this.value);
  DateTime value;

  @override
  DateTime now() => value;
}
```

**ID Generator Fake:**
```dart
class _FakeIdGenerator extends IdGenerator {
  _FakeIdGenerator(this.values);
  final List<String> values;
  int _index = 0;

  @override
  String nextId() {
    final next = values[_index];
    _index = (_index + 1).clamp(0, values.length - 1);
    return next;
  }
}
```

**In-Memory Repository:**
```dart
class _InMemoryResetRepository implements ResetRepository {
  RecoverySnapshot? snapshot;
  String id = 'device-1';
  DateTime startedAt = DateTime.utc(2026, 4, 13);

  @override
  Future<String> getOrCreateDeviceId() async => id;

  @override
  Future<RecoverySnapshot?> getRecoverySnapshot() async => snapshot;

  // ... etc
}
```

## Test Coverage Areas

**Unit Tests Cover:**
- Stage transitions: `compress` → `disrupt` → `clear` → `landing` → `completed`
- Event recording on `startReset`, `abandonReset`, `submitFeedback`
- Recovery prompt logic (direct resume vs. prompt)
- Repository persistence (device ID, trial start, snapshot)
- Self-healing on corrupted data

**Widget Tests Cover:**
- Entry screen UI: CTA button, copy text
- Stage copy changes during reset
- Completion screen feedback buttons
- Recovery prompt appearance

**Integration Tests Cover:**
- Full happy path: launch → compress → disrupt → clear → completion → feedback
- Interruption/recovery flow with pre-seeded snapshot

## Run Commands

**Unit and Widget Tests:**
```bash
flutter test
```

**Specific Test File:**
```bash
flutter test test/unit/reset_session_controller_test.dart
```

**Specific Test:**
```bash
flutter test --name "stage transitions"
```

**Integration Tests:**
```bash
flutter test integration_test/
```

**With Coverage:**
```bash
flutter test --coverage
```

## Async Testing

**Pattern:** `await` with async test functions

```dart
test('async operation completes', () async {
  await controller.initialize();
  expect(controller.initialized, isTrue);
});
```

**Widget Async:**
```dart
await tester.pumpWidget(_app(controller));
await tester.pumpAndSettle();  // Wait for animations
```

## Assertions

**Common Patterns:**
```dart
expect(actual, expected);
expect(actual, isTrue);
expect(actual, isFalse);
expect(actual, isNull);
expect(actual, isNotNull);
expect(actual, isA<SomeType>());
expect(list.any((e) => e.property == value), isTrue);
```

## Key Test Files

- `test/unit/reset_session_controller_test.dart` - Controller state machine tests
- `test/unit/reset_repository_impl_test.dart` - Persistence tests
- `test/widget/reset_entry_screen_test.dart` - Screen and flow tests
- `integration_test/app_flow_test.dart` - E2E flow tests

---

*Testing analysis: 2026-04-14*
