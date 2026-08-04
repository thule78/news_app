# Use SQLite with file exports

The local CLI uses one shared workspace database, `aa_content.db`, through Python’s built-in `sqlite3` as the structured source of truth for Trips, revisions, shared research, Claims, Evidence, approvals, and version links. Human-readable Markdown, JSON, and CSV remain the review and handoff formats, while immutable version folders preserve submitted package snapshots.
