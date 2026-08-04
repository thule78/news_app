from __future__ import annotations

from pathlib import Path

from aa_content.errors import UserFacingError
from aa_content.models import RouteSegment
from aa_content.persistence import WorkspaceRepository


def propose_shared_route_segments(
    workspace: Path, trip_a_id: str, trip_b_id: str
) -> tuple[RouteSegment, ...]:
    """AI-side proposal only: matches identical route legs across two Trips.

    Nothing here is canonical or reusable until an Operator runs
    `confirm_route_segment` on the resulting id.
    """
    repository = WorkspaceRepository(workspace)
    if not repository.database_path.is_file():
        raise UserFacingError(
            f"Workspace is not initialized: run init for {workspace.resolve()}"
        )

    trip_a = repository.load_current_trip(trip_a_id)
    trip_b = repository.load_current_trip(trip_b_id)
    if trip_a is None:
        raise UserFacingError(f"Trip not found: {trip_a_id}")
    if trip_b is None:
        raise UserFacingError(f"Trip not found: {trip_b_id}")

    normalized_a = repository.load_normalized_itinerary(trip_a.itinerary_revision_id)
    normalized_b = repository.load_normalized_itinerary(trip_b.itinerary_revision_id)
    if normalized_a is None or normalized_b is None:
        raise UserFacingError(
            "Both Trips must be processed (`trip process`) before proposing "
            "shared Route Segments."
        )

    legs_b_by_key = {}
    for origin, destination, locator in _route_legs(normalized_b):
        legs_b_by_key.setdefault((origin.casefold(), destination.casefold()), []).append(
            (origin, destination, locator)
        )

    proposed: list[RouteSegment] = []
    seen_keys: set[tuple[str, str]] = set()
    for origin_a, destination_a, locator_a in _route_legs(normalized_a):
        key = (origin_a.casefold(), destination_a.casefold())
        if key in seen_keys or key not in legs_b_by_key:
            continue
        seen_keys.add(key)
        origin_b, destination_b, locator_b = legs_b_by_key[key][0]
        segment = repository.propose_route_segment(
            origin_a,
            destination_a,
            [
                (trip_a.trip_id, trip_a.itinerary_revision_id, locator_a),
                (trip_b.trip_id, trip_b.itinerary_revision_id, locator_b),
            ],
        )
        proposed.append(segment)
    return tuple(proposed)


def confirm_route_segment(workspace: Path, route_segment_id: str) -> RouteSegment:
    repository = WorkspaceRepository(workspace)
    if not repository.database_path.is_file():
        raise UserFacingError(
            f"Workspace is not initialized: run init for {workspace.resolve()}"
        )
    return repository.confirm_route_segment(route_segment_id)


def list_route_segments(workspace: Path, trip_id: str) -> tuple[RouteSegment, ...]:
    repository = WorkspaceRepository(workspace)
    if not repository.database_path.is_file():
        raise UserFacingError(
            f"Workspace is not initialized: run init for {workspace.resolve()}"
        )
    trip = repository.load_current_trip(trip_id)
    if trip is None:
        raise UserFacingError(f"Trip not found: {trip_id}")
    return repository.list_route_segments_for_trip(trip_id)


def _route_legs(normalized: dict[str, object]) -> list[tuple[str, str, str]]:
    legs: list[tuple[str, str, str]] = []
    days = normalized.get("days", [])
    if not isinstance(days, list):
        return legs
    for day in days:
        if not isinstance(day, dict):
            continue
        locator = str(day.get("source_locator", ""))
        route_legs = day.get("route_legs", [])
        if not isinstance(route_legs, list):
            continue
        for leg in route_legs:
            if isinstance(leg, dict) and "from" in leg and "to" in leg:
                legs.append((str(leg["from"]), str(leg["to"]), locator))
    return legs
