# Architecture

**Analysis Date:** 2026-04-14

## Pattern Overview

**Overall:** Feature-First Clean Architecture with State Machine Controllers

**Key Characteristics:**
- Feature modules organize code by business capability, not technical layer
- Clean Architecture layers within each feature: `domain/`, `data/`, `presentation/`
- Controllers own state machines and orchestrate business logic
- Repositories abstract data persistence behind interfaces
- Dependency injection via manual bootstrap (no external DI framework)

## Layers

### Feature Layer (`lib/features/`)

**Purpose:** Encapsulate all code for a single business capability

**Location:** `lib/features/{feature_name}/`

**Contains:**
- `domain/` - Business logic (interfaces, models, controllers, policies)
- `data/` - Data layer implementations (repository implementations)
- `presentation/` - UI layer (screens, widgets)
- `config/` - Feature-specific configuration

**Example Structure (`lib/features/acute_reset/`):**
```
acute_reset/
├── config/reset_flow_config.dart
├── data/repositories/
│   ├── reset_repository_impl.dart
│   └── local_event_repository_impl.dart
├── domain/
│   ├── controllers/reset_session_controller.dart
│   ├── models/
│   │   ├── reset_session.dart
│   │   ├── reset_stage.dart
│   ├── policies/
│   │   ├── recovery_policy.dart
│   │   └── trial_policy.dart
│   └── repositories/
│       ├── reset_repository.dart
│       └── local_event_repository.dart
└── presentation/
    ├── screens/
    └── widgets/
```

### Domain Layer

**Purpose:** Define business logic, models, and repository interfaces

**Location:** `lib/features/{feature}/domain/`

**Contains:**
- `controllers/` - State machines using `ChangeNotifier`
- `models/` - Immutable data classes (value objects)
- `policies/` - Configuration objects for business rules
- `repositories/` - Abstract interface definitions

**Key Pattern - Controller as State Machine:**
```dart
class ResetSessionController extends ChangeNotifier {
  // Inject dependencies through constructor
  ResetSessionController({
    required ResetRepository resetRepository,
    required LocalEventRepository eventRepository,
  });
  
  // Expose state through getters
  ResetSession get session => _session;
  
  // Actions modify state and persist
  Future<void> startReset() async { ... }
}
```

### Data Layer

**Purpose:** Implement repository interfaces and handle persistence

**Location:** `lib/features/{feature}/data/repositories/`

**Contains:**
- `*_repository_impl.dart` - Concrete implementations of domain interfaces
- Depends on `services/` for storage abstractions

**Pattern - Repository Implementation:**
```dart
class ResetRepositoryImpl implements ResetRepository {
  ResetRepositoryImpl({
    required LocalStorageService storage,
    required IdGenerator idGenerator,
  });
  
  @override
  Future<String> getOrCreateDeviceId() async { ... }
}
```

### Presentation Layer

**Purpose:** Render UI and handle user interactions

**Location:** `lib/features/{feature}/presentation/`

**Contains:**
- `screens/` - Full-page widgets
- `widgets/` - Reusable UI components

**Key Patterns:**
- Screens use `Selector` for targeted rebuilds (not high-level `watch()`)
- Widgets are pure render functions (no business logic)
- Navigation via `Navigator.pushNamed()`

### Core Layer (`lib/core/`)

**Purpose:** Cross-cutting utilities shared across features

**Location:** `lib/core/`

**Contains:**
- `accessibility/` - Accessibility helpers (reduced motion)
- `constants/` - App-wide constants and storage keys
- `errors/` - Exception types
- `theme/` - Colors, typography, theme data
- `utils/` - Reusable utilities (Clock, IdGenerator)

### Services Layer (`lib/services/`)

**Purpose:** Application-wide infrastructure services

**Location:** `lib/services/`

**Contains:**
- `lifecycle/app_lifecycle_service.dart` - App lifecycle observer
- `storage/local_storage_service.dart` - SharedPreferences wrapper

### Router (`lib/router/`)

**Purpose:** Centralized navigation configuration

**Location:** `lib/router/`

**Files:**
- `route_names.dart` - Route name constants
- `app_router.dart` - `onGenerateRoute` handler

**Pattern:**
```dart
class AppRouter {
  static Route<dynamic> onGenerateRoute(RouteSettings settings) {
    switch (settings.name) {
      case RouteNames.activeReset:
        return MaterialPageRoute(builder: (_) => const ActiveResetScreen());
      // ...
    }
  }
}
```

### App Layer (`lib/app/`)

**Purpose:** Application bootstrap and root widget

**Files:**
- `bootstrap.dart` - Dependency initialization and composition
- `app.dart` - Root `RoxApp` widget with Provider setup

**Bootstrap Pattern:**
```dart
class AppBootstrap {
  Future<AppDependencies> initialize() async {
    // 1. Create services
    final storage = LocalStorageService();
    await storage.init();
    
    // 2. Create repositories
    final resetRepository = ResetRepositoryImpl(storage: storage, ...);
    
    // 3. Create controllers
    final controller = ResetSessionController(resetRepository: ...);
    
    // 4. Bind lifecycle
    controller.bindLifecycle(lifecycle);
    
    return AppDependencies(...);
  }
}
```

## Data Flow

### Reset Flow State Machine

```
ResetEntryScreen
    │
    ├── [hasRecoveryPrompt] ──→ RecoveryScreen ──→ [resume/startOver]
    │
    └── [Start Reset] ──→ ActiveResetScreen
                              │
                              ├── compress ──→ updateCompress(progress)
                              ├── disrupt ──→ registerDisruptSwipe()
                              ├── clear ────→ updateClear(progress)
                              ├── landing ──→ completeReset()
                              │
                              └── completed ──→ CompletionScreen
```

### State Persistence Flow

```
User Action
    │
    ▼
Controller Action
    │
    ├──► Update local state
    │
    └──► Repository.saveRecoverySnapshot()
              │
              ▼
         LocalStorageService
              │
              ▼
         SharedPreferences
```

### Interruption Recovery Flow

```
App Lifecycle (paused/inactive)
    │
    ▼
AppLifecycleService (StreamController)
    │
    ▼
ResetSessionController.bindLifecycle()
    │
    ▼
_saveSnapshotIfActive() ──→ RecoverySnapshot saved
```

## Key Abstractions

### Repository Pattern

- **Purpose:** Abstract data persistence behind interface
- **Examples:**
  - `lib/features/acute_reset/domain/repositories/reset_repository.dart` (interface)
  - `lib/features/acute_reset/data/repositories/reset_repository_impl.dart` (impl)

### Controller Pattern

- **Purpose:** Own state machine, coordinate between UI and domain
- **Examples:**
  - `lib/features/acute_reset/domain/controllers/reset_session_controller.dart`

### Policy Pattern

- **Purpose:** Encapsulate configurable business rules
- **Examples:**
  - `lib/features/acute_reset/domain/policies/recovery_policy.dart`
  - `lib/features/acute_reset/domain/policies/trial_policy.dart`

### State Machine Pattern (in Controllers)

- **Purpose:** Manage discrete states with allowed transitions
- **Examples:**
  - `ResetStage` enum defines states
  - `ResetSessionController` enforces valid transitions

## Entry Points

### Application Entry

**Location:** `lib/main.dart`
**Responsibilities:**
- Initialize Flutter binding
- Bootstrap dependencies
- Launch root widget

### Navigation Entry

**Location:** `lib/app/app.dart`
**Responsibilities:**
- Configure MaterialApp with router
- Set up Provider hierarchy
- Manage app lifecycle binding

## Error Handling

**Strategy:** Fail-fast with safe defaults

**Patterns:**
- Controllers throw on invalid state transitions (guarded by `if` checks)
- Repository `tryParse` methods return null on invalid data
- Corrupted storage is cleared and recovered (no thrown exceptions)
- `AppException` exists for domain-specific errors

## Cross-Cutting Concerns

**Logging:** No centralized logging (local event repository for analytics)
**Validation:** Performed in controllers before state updates
**Authentication:** Not applicable (local-only MVP)
**Accessibility:** `reduced_motion_helper.dart` for motion preferences

---

*Architecture analysis: 2026-04-14*
