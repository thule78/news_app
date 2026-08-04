# Sanitize forbidden supplier data before AI processing

If ingestion detects possible Supplier Data, the system preserves the original locally, removes flagged content from the AI-bound copy, and continues with a Sanitized Itinerary. Final approval remains blocked until human review; this avoids sending forbidden data to external AI while allowing useful processing to continue.
