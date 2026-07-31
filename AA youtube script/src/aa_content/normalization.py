from __future__ import annotations

from collections.abc import Sequence
import hashlib
import json
import re
from typing import Protocol

from aa_content.sanitization import remove_supplier_placeholders


NORMALIZER_VERSION = "rule-based-normalizer-v2"


class ItineraryNormalizer(Protocol):
    def normalize(
        self, itinerary_revision_id: str, sanitized_itinerary: str
    ) -> dict[str, object]:
        """Return provider-neutral structured Trip data."""


class RuleBasedItineraryNormalizer:
    def normalize(
        self, itinerary_revision_id: str, sanitized_itinerary: str
    ) -> dict[str, object]:
        days: list[dict[str, object]] = []
        claims: list[dict[str, object]] = []
        current_day: dict[str, object] | None = None

        for line_number, raw_line in enumerate(
            sanitized_itinerary.splitlines(), start=1
        ):
            line = remove_supplier_placeholders(raw_line).strip(" \t,;")
            if not line:
                continue
            day_match = re.match(r"Day\s+(\d+)\s*:\s*(.*)", line, re.IGNORECASE)
            if day_match:
                current_day = _new_day(int(day_match.group(1)), line_number)
                days.append(current_day)
                line = day_match.group(2).strip()
                if not line:
                    continue
            if current_day is None:
                current_day = _new_day(1, line_number)
                days.append(current_day)
            _extract_line(
                itinerary_revision_id,
                current_day,
                claims,
                line,
                line_number,
            )

        fact_conflicts = _reconcile_duration_estimates(
            itinerary_revision_id, days
        )
        missing_information = _missing_information(days)
        return {
            "schema_version": 1,
            "itinerary_revision_id": itinerary_revision_id,
            "days": days,
            "claims": claims,
            "missing_information": missing_information,
            "fact_conflicts": fact_conflicts,
        }


def _new_day(day_number: int, source_line: int) -> dict[str, object]:
    return {
        "day_number": day_number,
        "source_locator": f"line {source_line}",
        "route_legs": [],
        "overnight_stops": [],
        "activities": [],
        "accommodation": [],
        "meals": [],
        "transport": [],
        "practical_constraints": [],
    }


def _extract_line(
    itinerary_revision_id: str,
    day: dict[str, object],
    claims: list[dict[str, object]],
    line: str,
    line_number: int,
) -> None:
    route_points = _extract_route(line)
    route: dict[str, object] | None = None
    if route_points is not None:
        origin, destination = route_points
        route = {
            "from": origin,
            "to": destination,
        }
        claim_id = _append_claim(
            itinerary_revision_id,
            claims,
            "ROUTE_LEG",
            route,
            line,
            line_number,
        )
        route["claim_id"] = claim_id
        _items(day, "route_legs").append(route)

    activity_kind = _activity_kind(line)
    if activity_kind is not None:
        activity_route = (
            {"from": route["from"], "to": route["to"]}
            if route is not None
            else None
        )
        activity_clause = _clause_containing_activity(line, activity_kind)
        conditions = _duration_conditions(activity_clause)
        route_segment = _route_segment(activity_clause)
        activity_value: dict[str, object] = {
            "kind": activity_kind,
            "description": activity_clause,
            "estimated_duration": _extract_duration(activity_clause),
            "route": activity_route,
            "route_segment": route_segment,
            "conditions": conditions,
        }
        activity = dict(activity_value)
        claim_id = _append_claim(
            itinerary_revision_id,
            claims,
            "ACTIVITY",
            activity_value,
            line,
            line_number,
        )
        activity["claim_id"] = claim_id
        activity["claim_ids"] = [claim_id]
        _items(day, "activities").append(activity)

    overnight_match = re.search(
        r"\b(?:stay(?:ing)?(?:\s+overnight)?|overnight)\s+(?:in|at)\s+(.+?)(?=[.;]|$)",
        line,
        re.IGNORECASE,
    )
    if overnight_match:
        overnight = {"name": _clean_name(overnight_match.group(1))}
        overnight["claim_id"] = _append_claim(
            itinerary_revision_id,
            claims,
            "OVERNIGHT_STOP",
            overnight,
            line,
            line_number,
        )
        _items(day, "overnight_stops").append(overnight)

    accommodation_kind = _accommodation_kind(line)
    if accommodation_kind is not None:
        accommodation = {"kind": accommodation_kind, "description": line}
        accommodation["claim_id"] = _append_claim(
            itinerary_revision_id,
            claims,
            "ACCOMMODATION",
            accommodation,
            line,
            line_number,
        )
        _items(day, "accommodation").append(accommodation)

    meals = [
        meal
        for meal in ("BREAKFAST", "LUNCH", "DINNER")
        if re.search(rf"\b{meal}\b", line, re.IGNORECASE)
    ]
    for meal in meals:
        arrangement = _inclusion_arrangement(line, meal)
        meal_record: dict[str, object] = {
            "name": meal,
            "arrangement": arrangement,
        }
        claim_id = _append_claim(
            itinerary_revision_id,
            claims,
            "MEAL",
            meal_record,
            line,
            line_number,
        )
        meal_record["claim_id"] = claim_id
        _items(day, "meals").append(meal_record)

    transport_kind = _transport_kind(line)
    if transport_kind is not None:
        transport_clause = _clause_containing_transport(line, transport_kind)
        transport = {
            "kind": transport_kind,
            "arrangement": _transport_arrangement(transport_clause),
            "description": transport_clause,
            "estimated_duration": _extract_duration(transport_clause),
        }
        transport["claim_id"] = _append_claim(
            itinerary_revision_id,
            claims,
            "TRANSPORT",
            transport,
            line,
            line_number,
        )
        _items(day, "transport").append(transport)

    if re.search(
        r"\b(?:steep|uneven|elevation|altitude|stairs?|rain|snow|"
        r"remote|limited|luggage|fitness|strenuous)\b",
        line,
        re.IGNORECASE,
    ):
        constraint = {"description": line}
        constraint["claim_id"] = _append_claim(
            itinerary_revision_id,
            claims,
            "PRACTICAL_CONSTRAINT",
            constraint,
            line,
            line_number,
        )
        _items(day, "practical_constraints").append(constraint)


def _extract_duration(line: str) -> dict[str, int] | None:
    range_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(\d+(?:\.\d+)?)\s*"
        r"(hours?|hrs?|minutes?|mins?)\b",
        line,
        re.IGNORECASE,
    )
    if range_match:
        return {
            "minimum_minutes": _to_minutes(
                float(range_match.group(1)), range_match.group(3)
            ),
            "maximum_minutes": _to_minutes(
                float(range_match.group(2)), range_match.group(3)
            ),
        }
    single_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|minutes?|mins?)\b",
        line,
        re.IGNORECASE,
    )
    if single_match:
        minutes = _to_minutes(float(single_match.group(1)), single_match.group(2))
        return {"minimum_minutes": minutes, "maximum_minutes": minutes}
    return None


def _extract_route(line: str) -> tuple[str, str] | None:
    endpoint = (
        r"(?=,|[.;]|\s*\(|\s+(?:for|on|and|with|by|in|via|along|using)\b|$)"
    )
    patterns = (
        rf"\bfrom\s+(.+?)\s+to\s+(.+?){endpoint}",
        (
            rf"\b(?:walk|hike|travel|transfer|ride)\s+(?:from\s+)?"
            rf"(.+?)\s+to\s+(.+?){endpoint}"
        ),
        rf"^(.+?)\s+to\s+(.+?){endpoint}",
        rf"^(.+?)\s*(?:→|–|—)\s*(.+?){endpoint}",
    )
    for pattern in patterns:
        match = re.search(pattern, line, re.IGNORECASE)
        if match is None:
            continue
        origin = _clean_name(match.group(1))
        destination = _clean_name(match.group(2))
        if re.search(r"[^\W\d_]", origin, re.UNICODE) and re.search(
            r"[^\W\d_]", destination, re.UNICODE
        ):
            return origin, destination
    return None


def _duration_conditions(line: str) -> str:
    conditions: list[str] = []
    for pattern, condition in (
        (r"\bdry\b", "DRY"),
        (r"\b(?:wet|rain|rainy)\b", "WET"),
        (r"\bsnow(?:y)?\b", "SNOW"),
        (r"\bwinter\b", "WINTER"),
        (r"\bsummer\b", "SUMMER"),
        (r"\bwith\s+luggage\b", "WITH_LUGGAGE"),
        (r"\bwithout\s+luggage\b", "WITHOUT_LUGGAGE"),
    ):
        if re.search(pattern, line, re.IGNORECASE):
            conditions.append(condition)
    return "+".join(conditions) if conditions else "UNSPECIFIED"


def _route_segment(line: str) -> str:
    match = re.search(
        r"\b(?:via|along|using|on(?:\s+the)?)\s+"
        r"(.+?)(?=,|[.;]|\s+(?:for|in|with|under|during)\b|$)",
        line,
        re.IGNORECASE,
    )
    return _clean_name(match.group(1)).casefold() if match else "UNSPECIFIED"


def _reconcile_duration_estimates(
    itinerary_revision_id: str,
    days: list[dict[str, object]],
) -> list[dict[str, object]]:
    conflicts: list[dict[str, object]] = []
    for day in days:
        activities = _items(day, "activities")
        groups: dict[tuple[str, str, str], list[dict[str, object]]] = {}
        unscoped: list[dict[str, object]] = []
        for item in activities:
            if not isinstance(item, dict):
                continue
            route = item.get("route")
            if not isinstance(route, dict):
                unscoped.append(item)
                continue
            key = (
                str(item.get("kind", "")),
                str(route.get("from", "")),
                str(route.get("to", "")),
            )
            groups.setdefault(key, []).append(item)

        reconciled: list[object] = list(unscoped)
        for (kind, origin, destination), scoped_activities in groups.items():
            by_compatibility: dict[
                tuple[str, str],
                list[dict[str, object]],
            ] = {}
            for activity in scoped_activities:
                compatibility_key = (
                    str(activity.get("conditions", "UNSPECIFIED")),
                    str(activity.get("route_segment", "UNSPECIFIED")),
                )
                by_compatibility.setdefault(compatibility_key, []).append(
                    activity
                )

            condition_activities: list[dict[str, object]] = []
            for matching_activities in by_compatibility.values():
                condition_activities.append(
                    _merge_matching_duration_estimates(matching_activities)
                )
            reconciled.extend(condition_activities)

            durations = [
                activity.get("estimated_duration")
                for activity in condition_activities
                if isinstance(activity.get("estimated_duration"), dict)
            ]
            if len(by_compatibility) > 1 and len(
                {
                    json.dumps(duration, sort_keys=True)
                    for duration in durations
                }
            ) > 1:
                claim_ids = [
                    str(claim_id)
                    for activity in condition_activities
                    for claim_id in _object_list(activity, "claim_ids")
                ]
                subject = f"{kind}: {origin} to {destination}"
                conflicts.append(
                    {
                        "fact_conflict_id": _stable_id(
                            "fcf",
                            itinerary_revision_id,
                            str(day["day_number"]),
                            subject,
                        ),
                        "subject": subject,
                        "conditions": sorted(
                            {
                                condition
                                for condition, _ in by_compatibility
                            }
                        ),
                        "route_segments": sorted(
                            {
                                segment
                                for _, segment in by_compatibility
                            }
                        ),
                        "claim_ids": claim_ids,
                        "reason": (
                            "Duration estimates use incompatible conditions or "
                            "Route Segments and must not be combined."
                        ),
                    }
                )
        day["activities"] = reconciled
    conflicts.extend(
        _cross_scope_duration_conflicts(itinerary_revision_id, days)
    )
    return conflicts


def _cross_scope_duration_conflicts(
    itinerary_revision_id: str,
    days: list[dict[str, object]],
) -> list[dict[str, object]]:
    groups: dict[
        tuple[str, str, str],
        list[tuple[int, dict[str, object]]],
    ] = {}
    for day in days:
        day_number = int(day["day_number"])
        for item in _items(day, "activities"):
            if not isinstance(item, dict):
                continue
            route = item.get("route")
            duration = item.get("estimated_duration")
            if not isinstance(route, dict) or not isinstance(duration, dict):
                continue
            key = (
                str(item.get("kind", "")),
                str(route.get("from", "")),
                str(route.get("to", "")),
            )
            groups.setdefault(key, []).append((day_number, item))

    conflicts: list[dict[str, object]] = []
    for (kind, origin, destination), observations in groups.items():
        scopes = {day_number for day_number, _ in observations}
        durations = {
            json.dumps(activity["estimated_duration"], sort_keys=True)
            for _, activity in observations
        }
        if len(scopes) < 2 or len(durations) < 2:
            continue
        subject = f"{kind}: {origin} to {destination}"
        conflicts.append(
            {
                "fact_conflict_id": _stable_id(
                    "fcf",
                    itinerary_revision_id,
                    "cross-scope",
                    subject,
                ),
                "subject": subject,
                "scopes": [f"Day {scope}" for scope in sorted(scopes)],
                "claim_ids": [
                    str(claim_id)
                    for _, activity in observations
                    for claim_id in _object_list(activity, "claim_ids")
                ],
                "reason": (
                    "Duration estimates use different day scopes and must not "
                    "be combined."
                ),
            }
        )
    return conflicts


def _merge_matching_duration_estimates(
    activities: list[dict[str, object]],
) -> dict[str, object]:
    first = dict(activities[0])
    claim_ids = [
        str(claim_id)
        for activity in activities
        for claim_id in _object_list(activity, "claim_ids")
    ]
    first["claim_ids"] = claim_ids
    durations = [
        duration
        for activity in activities
        if isinstance((duration := activity.get("estimated_duration")), dict)
    ]
    if durations:
        first["estimated_duration"] = {
            "minimum_minutes": min(
                int(duration["minimum_minutes"]) for duration in durations
            ),
            "maximum_minutes": max(
                int(duration["maximum_minutes"]) for duration in durations
            ),
        }
    return first


def _to_minutes(value: float, unit: str) -> int:
    multiplier = 60 if unit.casefold().startswith(("hour", "hr")) else 1
    return round(value * multiplier)


def _activity_kind(line: str) -> str | None:
    for pattern, kind in (
        (r"\bwalk(?:ing)?\b", "WALK"),
        (r"\bhik(?:e|ing)\b", "HIKE"),
        (r"\btrek(?:king)?\b", "TREK"),
        (r"\bcycl(?:e|ing)\b", "CYCLE"),
        (r"\bkayak(?:ing)?\b", "KAYAK"),
        (r"\braft(?:ing)?\b", "RAFT"),
        (r"\bvisit(?:ing)?\b", "VISIT"),
    ):
        if re.search(pattern, line, re.IGNORECASE):
            return kind
    return None


def _clause_containing_activity(line: str, activity_kind: str) -> str:
    pattern = {
        "WALK": r"\bwalk(?:ing)?\b",
        "HIKE": r"\bhik(?:e|ing)\b",
        "TREK": r"\btrek(?:king)?\b",
        "CYCLE": r"\bcycl(?:e|ing)\b",
        "KAYAK": r"\bkayak(?:ing)?\b",
        "RAFT": r"\braft(?:ing)?\b",
        "VISIT": r"\bvisit(?:ing)?\b",
    }[activity_kind]
    return _clause_containing(line, pattern)


def _accommodation_kind(line: str) -> str | None:
    for word, kind in (
        ("ryokan", "RYOKAN"),
        ("hotel", "HOTEL"),
        ("guesthouse", "GUESTHOUSE"),
        ("hostel", "HOSTEL"),
        ("lodge", "LODGE"),
        ("inn", "INN"),
    ):
        if re.search(rf"\b{word}\b", line, re.IGNORECASE):
            return kind
    return None


def _transport_kind(line: str) -> str | None:
    for phrase, kind in (
        ("cable car", "CABLE_CAR"),
        ("train", "TRAIN"),
        ("bus", "BUS"),
        ("transfer", "TRANSFER"),
        ("taxi", "TAXI"),
        ("ferry", "FERRY"),
        ("flight", "FLIGHT"),
    ):
        if re.search(rf"\b{phrase}\b", line, re.IGNORECASE):
            return kind
    return None


def _clause_containing_transport(line: str, transport_kind: str) -> str:
    phrase = {
        "CABLE_CAR": "cable car",
        "TRAIN": "train",
        "BUS": "bus",
        "TRANSFER": "transfer",
        "TAXI": "taxi",
        "FERRY": "ferry",
        "FLIGHT": "flight",
    }[transport_kind]
    return _clause_containing(line, rf"\b{phrase}\b")


def _clause_containing(line: str, pattern: str) -> str:
    for clause in re.split(r"[.;]", line):
        cleaned = clause.strip()
        if re.search(pattern, cleaned, re.IGNORECASE):
            return cleaned
    return line.strip()


def _transport_arrangement(transport_clause: str) -> str:
    transport = r"(?:cable\s+car|train|bus|transfer|taxi|ferry|flight)"
    if re.search(
        rf"(?:\b(?:not included|self-arranged|independent)\s+{transport}\b|"
        rf"\b{transport}\b\s+(?:is\s+)?not included\b|"
        rf"^\s*(?:the\s+)?{transport}\b[^,]*\bown arrangement\b)",
        transport_clause,
        re.IGNORECASE,
    ):
        return "INDEPENDENT_TRANSPORT"
    if re.search(
        rf"(?:\b(?:included|arranged)\s+"
        rf"(?:(?:private|shared|local)\s+)?{transport}\b|"
        rf"^\s*(?:the\s+)?{transport}\b\s+(?:is\s+)?"
        rf"(?:included|arranged)\b|"
        rf"\bprivate\s+transfer\b)",
        transport_clause,
        re.IGNORECASE,
    ):
        return "TRIP_TRANSPORT"
    return "UNKNOWN"


def _inclusion_arrangement(line: str, meal: str) -> str:
    meal_clause = _clause_containing(line, rf"\b{meal}\b")
    if re.search(
        rf"(?:\b{meal}\b[^.;]*\b(?:not included|excluded)\b|"
        rf"\b(?:not included|excluded)\b[^.;]*\b{meal}\b)",
        meal_clause,
        re.IGNORECASE,
    ):
        return "EXCLUDED"
    if re.search(
        rf"(?:\b{meal}\b[^.;]*\b(?:included|provided)\b|"
        rf"\b(?:included|provided)\b[^.;]*\b{meal}\b)",
        meal_clause,
        re.IGNORECASE,
    ):
        return "INCLUDED"
    return "UNKNOWN"


def _append_claim(
    itinerary_revision_id: str,
    claims: list[dict[str, object]],
    claim_kind: str,
    value: dict[str, object],
    statement: str,
    source_line: int,
) -> str:
    canonical_value = json.dumps(value, sort_keys=True, separators=(",", ":"))
    persisted_value = json.loads(canonical_value)
    claim_id = _stable_id(
        "clm",
        itinerary_revision_id,
        claim_kind,
        str(source_line),
        canonical_value,
    )
    evidence_id = _stable_id("evd", itinerary_revision_id, str(source_line), claim_id)
    claims.append(
        {
            "claim_id": claim_id,
            "claim_kind": claim_kind,
            "statement": statement,
            "value": persisted_value,
            "evidence_status": "VERIFIED",
            "evidence": {
                "evidence_id": evidence_id,
                "kind": "ITINERARY",
                "source_locator": f"line {source_line}",
                "summary": statement,
            },
        }
    )
    return claim_id


def _missing_information(days: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    missing: list[dict[str, object]] = []
    fields = (
        "route_legs",
        "overnight_stops",
        "activities",
        "accommodation",
        "meals",
        "transport",
        "practical_constraints",
    )
    for day in days:
        for field in fields:
            if not day.get(field):
                missing.append(
                    {
                        "scope": f"Day {day['day_number']}",
                        "field": field,
                        "status": "MISSING_INFORMATION",
                    }
                )
        for field in ("meals", "transport"):
            records = day.get(field)
            if isinstance(records, list) and any(
                isinstance(record, dict)
                and record.get("arrangement") == "UNKNOWN"
                for record in records
            ):
                missing.append(
                    {
                        "scope": f"Day {day['day_number']}",
                        "field": f"{field}.arrangement",
                        "status": "MISSING_INFORMATION",
                    }
                )
        for field in ("activities", "transport"):
            records = day.get(field)
            if isinstance(records, list) and any(
                isinstance(record, dict)
                and record.get("estimated_duration") is None
                for record in records
            ):
                missing.append(
                    {
                        "scope": f"Day {day['day_number']}",
                        "field": f"{field}.estimated_duration",
                        "status": "MISSING_INFORMATION",
                    }
                )
    return missing


def _items(container: dict[str, object], key: str) -> list[object]:
    value = container.setdefault(key, [])
    if not isinstance(value, list):
        raise TypeError(f"Normalized field is not a list: {key}")
    return value


def _object_list(container: dict[str, object], key: str) -> list[object]:
    value = container.get(key, [])
    return value if isinstance(value, list) else []


def _clean_name(value: str) -> str:
    return value.strip(" \t,.;:")


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:32]}"
