from __future__ import annotations

import json
import re
from typing import Protocol
from urllib import request as urllib_request


NORMALIZATION_SYSTEM_PROMPT = (
    "You convert a sanitized travel itinerary into structured JSON facts. "
    "Never invent details that are not present in the text. Leave a field "
    "out rather than guess. Respond with JSON only."
)

NORMALIZED_ITINERARY_JSON_SCHEMA = {
    "name": "normalized_itinerary",
    "schema": {
        "type": "object",
        "required": ["days", "missing_information", "fact_conflicts"],
        "properties": {
            "days": {"type": "array"},
            "missing_information": {"type": "array"},
            "fact_conflicts": {"type": "array"},
        },
    },
}


class NormalizationProvider(Protocol):
    """Hides how normalized itinerary facts are produced from the domain."""

    def normalize(self, sanitized_text: str) -> dict[str, object]: ...


class OpenAIItineraryProvider:
    """Calls OpenAI directly over stdlib HTTP; no third-party SDK dependency."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gpt-4o-mini",
        endpoint: str = "https://api.openai.com/v1/chat/completions",
        timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._endpoint = endpoint
        self._timeout = timeout

    def normalize(self, sanitized_text: str) -> dict[str, object]:
        payload = json.dumps(
            {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": NORMALIZATION_SYSTEM_PROMPT},
                    {"role": "user", "content": sanitized_text},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": NORMALIZED_ITINERARY_JSON_SCHEMA,
                },
            }
        ).encode("utf-8")
        request = urllib_request.Request(
            self._endpoint,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib_request.urlopen(request, timeout=self._timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise ValueError("OpenAI normalization response was not a JSON object.")
        return parsed


class FakeItineraryProvider:
    """Deterministic, offline stand-in used by the default test suite."""

    def normalize(self, sanitized_text: str) -> dict[str, object]:
        return heuristic_normalize(sanitized_text)


_DAY_HEADER_RE = re.compile(r"^\s*Day\s+(\d+)\s*:?\s*(.*)$", re.IGNORECASE)
_PLACE_WORD = r"[A-Z][\w'-]*"
_ROUTE_LEG_RE = re.compile(
    rf"\bfrom\s+({_PLACE_WORD}(?:\s+{_PLACE_WORD})*)"
    rf"\s+to\s+({_PLACE_WORD}(?:\s+{_PLACE_WORD})*)"
)
_DURATION_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:[-–to]{1,4}\s*(\d+(?:\.\d+)?))?\s*"
    r"(hours?|hrs?|minutes?|mins?)",
    re.IGNORECASE,
)
_ACCOMMODATION_RE = re.compile(
    r"\b(hotel|ryokan|inn|lodge|guest\s*house|homestay|campsite)\b", re.IGNORECASE
)
_MEAL_RE = re.compile(r"\b(breakfast|lunch|dinner|meals?)\b", re.IGNORECASE)
_TRANSPORT_RE = re.compile(
    r"\b(train|bus|taxi|transfer|ferry|flight|shuttle)\b", re.IGNORECASE
)
_OVERNIGHT_RE = re.compile(
    r"\b(overnight|stay(?:ing)? (?:in|at))\b", re.IGNORECASE
)
_ACTIVITY_RE = re.compile(
    r"\b(walk|hike|trek|tour|visit|explore|climb|cycle)\b", re.IGNORECASE
)
_PRACTICAL_RE = re.compile(
    r"\b(cash only|no atm|no phone signal|steep|closed on|reservation "
    r"required|limited|advisory|no toilets|remote|no wifi)\b",
    re.IGNORECASE,
)


def heuristic_normalize(sanitized_text: str) -> dict[str, object]:
    day_blocks = _split_into_days(sanitized_text)

    days: list[dict[str, object]] = []
    route_leg_durations: dict[tuple[str, str], list[tuple[str, dict[str, object]]]] = {}
    saw_meal = False
    saw_transport = False

    for day_number, block in day_blocks:
        locator = f"day {day_number}"
        sentences = _split_sentences(block)

        route_legs: list[dict[str, object]] = []
        overnight_stops: list[dict[str, object]] = []
        activities: list[dict[str, object]] = []
        accommodation: list[dict[str, object]] = []
        meals: list[dict[str, object]] = []
        transport: list[dict[str, object]] = []
        practical_constraints: list[dict[str, object]] = []

        for sentence in sentences:
            duration = _extract_duration(sentence)
            route_match = _ROUTE_LEG_RE.search(sentence)
            if route_match:
                origin = route_match.group(1).strip()
                destination = route_match.group(2).strip()
                key = (origin.casefold(), destination.casefold())
                route_leg_durations.setdefault(key, []).append(
                    (
                        sentence.strip(),
                        {
                            "from": origin,
                            "to": destination,
                            "source_locator": locator,
                            "duration_text": duration["text"] if duration else None,
                            "duration": duration,
                        },
                    )
                )
                route_legs.append(route_leg_durations[key][-1][1])
                continue
            if _ACTIVITY_RE.search(sentence):
                activities.append(
                    {
                        "description": sentence.strip(),
                        "duration": duration,
                        "source_locator": locator,
                    }
                )
            if _OVERNIGHT_RE.search(sentence):
                overnight_stops.append(
                    {"description": sentence.strip(), "source_locator": locator}
                )
            if _ACCOMMODATION_RE.search(sentence):
                accommodation.append(
                    {"description": sentence.strip(), "source_locator": locator}
                )
            if _MEAL_RE.search(sentence):
                meals.append(
                    {"description": sentence.strip(), "source_locator": locator}
                )
                saw_meal = True
            if _TRANSPORT_RE.search(sentence):
                transport.append(
                    {"description": sentence.strip(), "source_locator": locator}
                )
                saw_transport = True
            if _PRACTICAL_RE.search(sentence):
                practical_constraints.append(
                    {"description": sentence.strip(), "source_locator": locator}
                )

        days.append(
            {
                "day_number": day_number,
                "source_locator": locator,
                "route_legs": route_legs,
                "overnight_stops": overnight_stops,
                "activities": activities,
                "accommodation": accommodation,
                "meals": meals,
                "transport": transport,
                "practical_constraints": practical_constraints,
            }
        )

    fact_conflicts = _resolve_route_leg_durations(days, route_leg_durations)
    missing_information = _find_missing_information(
        days, saw_meal=saw_meal, saw_transport=saw_transport
    )

    return {
        "days": days,
        "missing_information": missing_information,
        "fact_conflicts": fact_conflicts,
    }


def _split_into_days(text: str) -> list[tuple[int, str]]:
    lines = text.splitlines()
    headers: list[tuple[int, int, str]] = []
    for line_index, line in enumerate(lines):
        match = _DAY_HEADER_RE.match(line)
        if match:
            headers.append((line_index, int(match.group(1)), match.group(2)))

    if not headers:
        return [(1, text)] if text.strip() else []

    blocks: list[tuple[int, str]] = []
    for position, (line_index, day_number, remainder) in enumerate(headers):
        end_index = (
            headers[position + 1][0] if position + 1 < len(headers) else len(lines)
        )
        body_lines = [remainder] + lines[line_index + 1 : end_index]
        blocks.append((day_number, "\n".join(body_lines)))
    return blocks


def _split_sentences(block: str) -> list[str]:
    pieces = re.split(r"(?<=[.!?])\s+|\n+", block)
    return [piece.strip() for piece in pieces if piece.strip()]


def _extract_duration(sentence: str) -> dict[str, object] | None:
    match = _DURATION_RE.search(sentence)
    if not match:
        return None
    low = float(match.group(1))
    high = float(match.group(2)) if match.group(2) else None
    unit = match.group(3).lower()
    hours_low = low / 60 if unit.startswith("min") else low
    hours_high = (
        (high / 60 if unit.startswith("min") else high) if high is not None else None
    )
    if hours_high is not None:
        return {
            "kind": "ESTIMATED",
            "min_hours": hours_low,
            "max_hours": hours_high,
            "text": match.group(0),
        }
    return {"kind": "EXACT", "value_hours": hours_low, "text": match.group(0)}


def _duration_bounds(duration: dict[str, object]) -> tuple[float, float]:
    if duration["kind"] == "ESTIMATED":
        return float(duration["min_hours"]), float(duration["max_hours"])
    return float(duration["value_hours"]), float(duration["value_hours"])


def _resolve_route_leg_durations(
    days: list[dict[str, object]],
    route_leg_durations: dict[tuple[str, str], list[tuple[str, dict[str, object]]]],
) -> list[dict[str, object]]:
    fact_conflicts: list[dict[str, object]] = []
    for (origin_key, destination_key), occurrences in route_leg_durations.items():
        durations = [
            entry["duration"] for _, entry in occurrences if entry["duration"]
        ]
        if len(durations) < 2:
            continue
        bounds = [_duration_bounds(duration) for duration in durations]
        low = max(bound[0] for bound in bounds)
        high = min(bound[1] for bound in bounds)
        if low <= high:
            merged = {
                "kind": "ESTIMATED",
                "min_hours": min(bound[0] for bound in bounds),
                "max_hours": max(bound[1] for bound in bounds),
                "text": " / ".join(
                    str(duration["text"]) for duration in durations
                ),
            }
            for _, entry in occurrences:
                if entry["duration"]:
                    entry["duration"] = merged
                    entry["duration_text"] = merged["text"]
        else:
            display_origin, display_destination = occurrences[0][1]["from"], (
                occurrences[0][1]["to"]
            )
            fact_conflicts.append(
                {
                    "subject": (
                        f"Route leg {display_origin} to {display_destination} "
                        "duration"
                    ),
                    "reason": "Conflicting duration statements: "
                    + ", ".join(str(duration["text"]) for duration in durations),
                    "details": {
                        "from": display_origin,
                        "to": display_destination,
                        "statements": [duration["text"] for duration in durations],
                    },
                }
            )
            for _, entry in occurrences:
                if entry["duration"]:
                    entry["duration"] = {
                        "kind": "CONFLICTED",
                        "text": entry["duration"]["text"],
                    }
                    entry["duration_text"] = entry["duration"]["text"]
    return fact_conflicts


def _find_missing_information(
    days: list[dict[str, object]], *, saw_meal: bool, saw_transport: bool
) -> list[dict[str, object]]:
    missing: list[dict[str, object]] = []
    for day in days:
        locator = f"day {day['day_number']}"
        has_overnight = bool(day["overnight_stops"])
        has_accommodation = bool(day["accommodation"])
        if has_overnight and not has_accommodation:
            missing.append(
                {
                    "scope": locator,
                    "field": "accommodation",
                    "status": "MISSING_INFORMATION",
                }
            )
        for activity in day["activities"]:
            if activity["duration"] is None:
                missing.append(
                    {
                        "scope": locator,
                        "field": "duration",
                        "status": "MISSING_INFORMATION",
                    }
                )
        for route_leg in day["route_legs"]:
            if route_leg["duration"] is None:
                missing.append(
                    {
                        "scope": locator,
                        "field": "duration",
                        "status": "MISSING_INFORMATION",
                    }
                )
    if not saw_meal:
        missing.append(
            {"scope": "Trip", "field": "meals", "status": "MISSING_INFORMATION"}
        )
    if not saw_transport:
        missing.append(
            {"scope": "Trip", "field": "transport", "status": "MISSING_INFORMATION"}
        )
    return missing
