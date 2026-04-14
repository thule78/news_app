# External Integrations

**Analysis Date:** 2026-04-14

## APIs & External Services

**Status:** NONE - Local-only MVP

The app has no external API integrations. Per AGENTS.md constraints, Supabase and account systems are explicitly forbidden for v1.

## Data Storage

### Local Persistence

**Mechanism:** `shared_preferences` (key-value storage)
- Client: `SharedPreferences` from Flutter SDK
- Wrapper: `LocalStorageService` at `lib/services/storage/local_storage_service.dart`

**Storage Keys** (from `lib/core/constants/storage_keys.dart`):
- `device_id` - Anonymous device identifier (UUID)
- `trial_start_at` - UTC timestamp for trial tracking
- `recovery_snapshot` - JSON-encoded session recovery state
- `local_event_log` - JSON-encoded list of events

**Data Integrity:**
- Corrupted JSON entries are cleared automatically
- `RecoverySnapshot.tryParse()` validates data on read
- `LocalEvent.tryParse()` validates events on read

### No Cloud Storage
- No Supabase
- No Firebase
- No other cloud backend

## Authentication & Identity

**Auth Provider:** NONE
- Anonymous device-based identity only
- `IdGenerator` generates UUIDs for `device_id`
- No user accounts
- No login flows

## Monitoring & Observability

**Error Tracking:** NONE
- No crash reporting (e.g., Sentry, Firebase Crashlytics)
- No analytics

**Event Logging:** Local-only
- `LocalEventRepository` stores events locally
- Events: reset_started, reset_completed, reset_abandoned, feedback_submitted
- Never blocks user flow on failure

## Platform Channels

**Status:** NONE

No native platform channels implemented:
- Android: `MainActivity.kt` is standard FlutterActivity (no custom Kotlin code)
- iOS: Directory not present (scaffold only)

All functionality is pure Dart/Flutter.

## CI/CD & Deployment

**Hosting:** Unknown (Flutter project supports iOS/Android deployment targets)

**CI Pipeline:** Not detected in repository

## Required Environment Configuration

**None required** - No env vars for external services.

## Widgets & Plugins

**Flutter Plugins Used:**
- `shared_preferences` - Local storage
- `cupertino_icons` - Icons only

**No other plugins** - App avoids plugin dependencies for v1 simplicity.

## Future Integration Seams

Per AGENTS.md, these seams exist but are NOT implemented:
- Supabase integration (for future cloud sync)
- Account system (for future authentication)
- Analytics/tracking (for future insights)
- Push notifications (for future reminders)

---

*Integration audit: 2026-04-14*
