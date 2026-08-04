# Make workflow stages resumable and idempotent

Each completed workflow stage is saved atomically and reused after later failures. Retries resume only failed work, require an explicit force option to replace successful results, and must not duplicate Claims, Evidence, or versions; this controls API cost and preserves reproducibility.
