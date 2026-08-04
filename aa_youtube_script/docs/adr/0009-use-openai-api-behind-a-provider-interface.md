# Use OpenAI API behind a provider interface

The MVP uses the OpenAI API for extraction, synthesis, planning, writing, and review tasks, while application code depends on an internal provider interface rather than OpenAI-specific types. This keeps the initial implementation focused without coupling the domain workflow to one model vendor.
