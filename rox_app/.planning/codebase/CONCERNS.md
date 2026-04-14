# Codebase Concerns

**Analysis Date:** 2026-04-14

---

## Known Limitations

### Intentional Scope Boundaries

**Local-only MVP without backend:**
- No Supabase integration exists (by design per `SPEC.md`)
- No account/authentication system
- Event logs are local-only with no sync capability
- No device migration if storage is cleared

**Hardcoded single reset flow:**
- Only one reset mode exists (`ResetFlowConfig.disruptSwipeCount = 3`)
- No user preference for gesture sensitivity
- Fixed 20-second direct-resume threshold (`RecoveryPolicy.directResumeThreshold`)

**Limited trial tracking:**
- `TrialPolicy.computeTrialDay()` is simple days-since-start
- No trial expiration logic
- `trial_start_at` persists forever once created

### Integration Test Status

**Integration test not executed:**
- File: `integration_test/app_flow_test.dart`
- Both tests (happy path and interruption recovery) exist
- Tests require connected device/simulator which was unavailable
- Unit and widget tests all pass (12/12)

---

## Technical Risks

### IdGenerator Collision Risk

**File:** `lib/core/utils/id_generator.dart`

```dart
class IdGenerator {
  String nextId() => DateTime.now().microsecondsSinceEpoch.toString();
}
```

- Uses microsecond timestamp as ID
- Multiple calls within same microsecond could produce duplicates
- Low risk for local-only use, but problematic for any future distributed systems
- Impact: Session IDs could theoretically collide

### Event Log Growth (Unbounded)

**File:** `lib/features/acute_reset/data/repositories/local_event_repository_impl.dart`

- `addEvent()` appends events without limit
- `readEvents()` loads entire log into memory
- No cleanup or archival strategy
- Impact: As app usage grows, storage and memory usage increases unbounded
- Affects: `lib/features/acute_reset/domain/repositories/local_event_repository.dart`

### Silent Event Failure

**File:** `lib/features/acute_reset/data/repositories/local_event_repository_impl.dart` (line 22-24)

```dart
} catch (_) {
  // Event logging must never block user flow.
}
```

- All exceptions silently swallowed
- No retry mechanism
- No error reporting
- Impact: Analytics data loss is undetectable

### Gesture Magic Numbers

**Files:** 
- `lib/features/acute_reset/presentation/widgets/compress_gesture_zone.dart` (line 22)
- `lib/features/acute_reset/presentation/widgets/clear_gesture_layer.dart` (line 22)

```dart
final next = (_distance / 240).clamp(0.0, 1.0);
```

- Hardcoded `240` pixels for gesture completion
- No configuration option
- Impact: Cannot tune feel without code changes

### SharedPreferences Initialization Race

**File:** `lib/services/storage/local_storage_service.dart`

```dart
SharedPreferences? _prefs;

Future<void> init() async {
  _prefs ??= await SharedPreferences.getInstance();
}
```

- `_prefs` is nullable; getter throws `StateError` if not initialized
- If `init()` is not called before use, app crashes
- Impact: Bootstrap pattern mitigates this, but fragile if patterns change

---

## Code Quality Issues

### Missing Test Coverage

**Untested code paths:**
1. **Direct resume path** - Unit test only covers recovery prompt case, not `shouldDirectResume == true`
2. **Progress calculation** - `_progressFor()` in `ActiveResetScreen` has no dedicated test
3. **Reduced-motion behavior** - No widget test for animation behavior
4. **Event repository corruption** - `LocalEventRepositoryImpl` has no unit tests
5. **Bootstrap flow** - No test for `AppBootstrap.initialize()`

### State Observation in Build

**File:** `lib/features/acute_reset/presentation/screens/reset_entry_screen.dart` (lines 31, 43)

```dart
Widget build(BuildContext context) {
  final controller = context.read<ResetSessionController>();
  // ...
  Text('Day ${controller.trialDay}', textAlign: TextAlign.center),
```

- `trialDay` is read in `build()` but not wrapped in `Selector`
- Any `trialDay` change would rebuild entire screen
- Low impact since `trialDay` is stable, but violates rebuild-scoping principle

### Incomplete Stage Handling

**File:** `lib/features/acute_reset/presentation/screens/active_reset_screen.dart` (lines 143-146)

```dart
case ResetStage.recoveryPrompt:
  return 0;
```

- `recoveryPrompt` stage returns progress 0
- This case shouldn't occur on ActiveResetScreen (recovery handled separately)
- However, no defensive check prevents navigation to this screen with that stage

### Unused Feedback After Completion

**File:** `lib/features/acute_reset/presentation/screens/completion_screen.dart`

- `submitFeedback()` is called but event logging is fire-and-forget
- If app crashes after `completeReset()` but before `submitFeedback()`, feedback is lost
- Impact: User feedback may be silently dropped

### RecoverySnapshot Null Safety Gap

**File:** `lib/features/acute_reset/domain/controllers/reset_session_controller.dart` (lines 195-204)

```dart
Future<void> resumeFromRecovery() async {
  final snapshot = _pendingRecoverySnapshot;
  if (snapshot == null) {
    return;  // Silent no-op if snapshot already cleared
  }
  _session = _fromSnapshot(snapshot);
```

- If called when `_pendingRecoverySnapshot` is null, does nothing silently
- No error thrown, no navigation triggered
- Impact: UI could become unresponsive if this path is hit unexpectedly

---

## Future Extensibility Seams

### ✅ Seams Already in Place

**Event Logging Seam:**
- `LocalEventRepository` interface in `lib/features/acute_reset/domain/repositories/local_event_repository.dart`
- `addEvent()` / `readEvents()` pattern ready for backend sync
- Constants defined in `ResetConstants`: `eventResetStarted`, `eventResetCompleted`, `eventResetAbandoned`, `eventFeedbackSubmitted`, `eventUpgradeViewed`
- Local implementation: `lib/features/acute_reset/data/repositories/local_event_repository_impl.dart`

**Recovery Policy Seam:**
- `RecoveryPolicy` class in `lib/features/acute_reset/domain/policies/recovery_policy.dart`
- Injectable into `ResetSessionController`
- Threshold configurable via constructor
- Ready for different policies per user segment

**Trial Policy Seam:**
- `TrialPolicy` class in `lib/features/acute_reset/domain/policies/trial_policy.dart`
- Injectable into controller
- Simple day calculation ready for extended logic

**Repository Pattern:**
- `ResetRepository` interface in `lib/features/acute_reset/domain/repositories/reset_repository.dart`
- Concrete implementation in `lib/features/acute_reset/data/repositories/reset_repository_impl.dart`
- Swap-in ready for Supabase backend

### 🔜 Ready to Extend

**Config-driven reset flow:**
- `ResetFlowConfig` in `lib/features/acute_reset/config/reset_flow_config.dart`
- Currently hardcoded but isolated
- Could accept runtime configuration

**Navigation abstraction:**
- `RouteNames` in `lib/router/route_names.dart`
- Route strings centralized
- Could swap `Navigator.pushReplacementNamed` for GoRouter or auto_route

**Animation configuration:**
- `AppConstants` in `lib/core/constants/app_constants.dart`
- `reducedMotionAnimation` and `gestureAnimation` durations centralized
- Ready for user preference toggle

---

## Recommended Improvements

### High Priority

1. **Add event log size limit and cleanup**
   - Add `maxEvents` parameter to `LocalEventRepositoryImpl`
   - Implement cleanup: remove oldest events when limit reached
   - File: `lib/features/acute_reset/data/repositories/local_event_repository_impl.dart`

2. **Add direct resume unit test**
   - Test `shouldDirectResume == true` path in `ResetSessionController`
   - Verify session state restored correctly
   - File: `test/unit/reset_session_controller_test.dart`

3. **Add event repository tests**
   - Test corruption handling (non-map JSON, missing fields)
   - Test cleanup behavior
   - File: `test/unit/local_event_repository_impl_test.dart` (new)

### Medium Priority

4. **Fix IdGenerator for uniqueness**
   - Add UUID generation or combine timestamp with random component
   - File: `lib/core/utils/id_generator.dart`

5. **Extract gesture sensitivity to config**
   - Move `240` pixel threshold to `ResetFlowConfig`
   - File: `lib/features/acute_reset/config/reset_flow_config.dart`

6. **Add progress calculation widget test**
   - Test `_progressFor()` for all stages
   - File: `test/widget/active_reset_screen_test.dart` (new)

### Low Priority

7. **Wrap `trialDay` in Selector on entry screen**
   - File: `lib/features/acute_reset/presentation/screens/reset_entry_screen.dart`

8. **Add explicit error handling in event logging**
   - Log errors to debug console (non-blocking)
   - File: `lib/features/acute_reset/data/repositories/local_event_repository_impl.dart`

9. **Add widget test for reduced-motion**
   - Verify animations use correct duration
   - File: `test/widget/reset_visual_core_test.dart` (new)

10. **Add defensive navigation check in resumeFromRecovery**
    - Throw or navigate to safe screen if snapshot null
    - File: `lib/features/acute_reset/domain/controllers/reset_session_controller.dart`

---

## Summary

**Overall Assessment:** Solid MVP foundation with clean architecture and good test coverage for critical paths.

**Strengths:**
- Clear separation of concerns (controller owns state, repository owns persistence)
- Corruption self-heals correctly
- Recovery behavior is explicit and testable
- Event seam ready for backend integration

**Critical Gaps:**
- Event log unbounded growth
- Integration tests not executed on real device
- Some edge cases lack test coverage

**Technical Debt:**
- IdGenerator collision risk (low for v1)
- Gesture magic numbers
- Missing direct resume test

**Extensibility:** Well-prepared. All future seams are in place without over-engineering.

---

*Concerns audit: 2026-04-14*
