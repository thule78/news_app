from __future__ import annotations

from datetime import date, timedelta
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from aa_content.baseline_research import run_baseline_research  # noqa: E402
from aa_content.models import ResearchCategory  # noqa: E402
from aa_content.persistence import WorkspaceRepository  # noqa: E402
from aa_content.route_segments import (  # noqa: E402
    confirm_route_segment,
    list_route_segments,
    propose_shared_route_segments,
)
from aa_content.research_providers import FakeResearchSourceProvider  # noqa: E402


def run_cli(
    workspace: Path,
    *arguments: str,
    stdin: str | None = None,
    extra_environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    if extra_environment:
        environment.update(extra_environment)
    return subprocess.run(
        [str(PROJECT_ROOT / "aa-content"), "--workspace", str(workspace), *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


SHARED_LEG = "Day 2: Walk from Magome to Tsumago, about 4 hours. Overnight stay in a guesthouse in Tsumago.\n"
DIFFERENT_LEG = "Day 2: Walk from Tsumago to Nojiri, about 3 hours. Overnight stay in a lodge in Nojiri.\n"


def _create_and_process_trip(workspace: Path, name: str, day2: str) -> str:
    itinerary = f"Day 1: Arrive by train.\n{day2}"
    created = run_cli(workspace, "trip", "create", "--name", name, stdin=itinerary)
    assert created.returncode == 0, created.stderr
    trip_id = next(
        line.removeprefix("Trip ID: ")
        for line in created.stdout.splitlines()
        if line.startswith("Trip ID: ")
    )
    processed = run_cli(
        workspace,
        "trip",
        "process",
        "--trip-id",
        trip_id,
        extra_environment={"AA_CONTENT_FAKE_PROVIDERS": "1"},
    )
    assert processed.returncode == 0, processed.stderr
    return trip_id


class RouteSegmentReuseTests(unittest.TestCase):
    def test_ai_proposal_does_not_become_canonical_without_confirmation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_a = _create_and_process_trip(workspace, "Trip A", SHARED_LEG)
            trip_b = _create_and_process_trip(workspace, "Trip B", SHARED_LEG)

            segments = propose_shared_route_segments(workspace, trip_a, trip_b)

            self.assertEqual(len(segments), 1)
            self.assertEqual(segments[0].status, "PROPOSED")
            self.assertIsNone(segments[0].confirmed_at)

            # Unconfirmed: researching both Trips must NOT share evidence.
            run_baseline_research(
                workspace, trip_a, provider=FakeResearchSourceProvider()
            )
            run_baseline_research(
                workspace, trip_b, provider=FakeResearchSourceProvider()
            )
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                route_rules_sources = connection.execute(
                    "SELECT COUNT(*) FROM source_records WHERE category = "
                    "'ROUTE_RULES'"
                ).fetchone()[0]
            self.assertEqual(route_rules_sources, 4)

    def test_confirmed_segment_gets_stable_identity_across_confirm_call(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_a = _create_and_process_trip(workspace, "Trip A", SHARED_LEG)
            trip_b = _create_and_process_trip(workspace, "Trip B", SHARED_LEG)
            proposed = propose_shared_route_segments(workspace, trip_a, trip_b)
            segment_id = proposed[0].route_segment_id

            confirmed = confirm_route_segment(workspace, segment_id)

            self.assertEqual(confirmed.route_segment_id, segment_id)
            self.assertEqual(confirmed.status, "CONFIRMED")
            self.assertIsNotNone(confirmed.confirmed_at)

    def test_second_trip_reuses_first_trips_evidence_without_copying_sources(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_a = _create_and_process_trip(workspace, "Trip A", SHARED_LEG)
            trip_b = _create_and_process_trip(workspace, "Trip B", SHARED_LEG)
            segment = propose_shared_route_segments(workspace, trip_a, trip_b)[0]
            confirm_route_segment(workspace, segment.route_segment_id)

            provider = FakeResearchSourceProvider()
            result_a = run_baseline_research(workspace, trip_a, provider=provider)
            result_b = run_baseline_research(workspace, trip_b, provider=provider)

            claims_a = {claim.category: claim for claim in result_a.claims}
            claims_b = {claim.category: claim for claim in result_b.claims}
            for category in (
                ResearchCategory.ROUTE_RULES,
                ResearchCategory.INDEPENDENT_TRANSPORT,
            ):
                sources_a = {s.source_record_id for s in claims_a[category].sources}
                sources_b = {s.source_record_id for s in claims_b[category].sources}
                self.assertEqual(sources_a, sources_b)
                self.assertTrue(sources_a)

            with sqlite3.connect(workspace / "aa_content.db") as connection:
                shared_source_count = connection.execute(
                    "SELECT COUNT(*) FROM source_records WHERE category IN "
                    "('ROUTE_RULES', 'INDEPENDENT_TRANSPORT')"
                ).fetchone()[0]
                trip_specific_source_count = connection.execute(
                    "SELECT COUNT(*) FROM source_records WHERE category = 'ACCESS'"
                ).fetchone()[0]
            # 2 categories x 2 sources, fetched once and referenced by both Trips.
            self.assertEqual(shared_source_count, 4)
            # ACCESS is never route-segment-scoped: each Trip researches fresh.
            self.assertEqual(trip_specific_source_count, 4)

    def test_distinct_route_leg_does_not_share_the_confirmed_segment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_a = _create_and_process_trip(workspace, "Trip A", SHARED_LEG)
            trip_b = _create_and_process_trip(workspace, "Trip B", SHARED_LEG)
            trip_c = _create_and_process_trip(workspace, "Trip C", DIFFERENT_LEG)
            segment = propose_shared_route_segments(workspace, trip_a, trip_b)[0]
            confirm_route_segment(workspace, segment.route_segment_id)

            provider = FakeResearchSourceProvider()
            run_baseline_research(workspace, trip_a, provider=provider)
            run_baseline_research(workspace, trip_b, provider=provider)
            result_c = run_baseline_research(workspace, trip_c, provider=provider)

            route_rules_c = next(
                claim
                for claim in result_c.claims
                if claim.category == ResearchCategory.ROUTE_RULES
            )
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                segment_count = connection.execute(
                    "SELECT COUNT(*) FROM route_segments"
                ).fetchone()[0]
                a_and_b_sources = {
                    row[0]
                    for row in connection.execute(
                        """
                        SELECT source.source_record_id
                        FROM research_claim_sources AS link
                        JOIN source_records AS source
                          ON source.source_record_id = link.source_record_id
                        JOIN research_claims AS claim
                          ON claim.claim_id = link.claim_id
                        WHERE claim.trip_id IN (?, ?)
                          AND claim.category = 'ROUTE_RULES'
                        """,
                        (trip_a, trip_b),
                    ).fetchall()
                }
            # Trip C's leg was never proposed, so only the A/B segment exists.
            self.assertEqual(segment_count, 1)
            c_sources = {source.source_record_id for source in route_rules_c.sources}
            self.assertTrue(c_sources.isdisjoint(a_and_b_sources))

    def test_passed_recheck_date_triggers_refresh_creating_new_evidence_history(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_a = _create_and_process_trip(workspace, "Trip A", SHARED_LEG)
            trip_b = _create_and_process_trip(workspace, "Trip B", SHARED_LEG)
            segment = propose_shared_route_segments(workspace, trip_a, trip_b)[0]
            confirm_route_segment(workspace, segment.route_segment_id)
            provider = FakeResearchSourceProvider()
            run_baseline_research(workspace, trip_a, provider=provider)

            stale_date = (date.today() - timedelta(days=1)).isoformat()
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                connection.execute(
                    "UPDATE research_claims SET recheck_date = ? WHERE category = "
                    "'ROUTE_RULES'",
                    (stale_date,),
                )
                old_source_ids = {
                    row[0]
                    for row in connection.execute(
                        "SELECT source_record_id FROM source_records WHERE "
                        "category = 'ROUTE_RULES'"
                    ).fetchall()
                }

            result_b = run_baseline_research(workspace, trip_b, provider=provider)

            route_rules_b = next(
                claim
                for claim in result_b.claims
                if claim.category == ResearchCategory.ROUTE_RULES
            )
            self.assertFalse(route_rules_b.stale)
            new_source_ids = {
                source.source_record_id for source in route_rules_b.sources
            }
            self.assertTrue(new_source_ids.isdisjoint(old_source_ids))
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                surviving_old = connection.execute(
                    "SELECT COUNT(*) FROM source_records WHERE source_record_id "
                    f"IN ({','.join('?' for _ in old_source_ids)})",
                    tuple(old_source_ids),
                ).fetchone()[0]
            # Refresh does not destroy the old Evidence history.
            self.assertEqual(surviving_old, len(old_source_ids))

    def test_failed_refresh_produces_stale_claim_that_remains_reviewable(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_a = _create_and_process_trip(workspace, "Trip A", SHARED_LEG)
            trip_b = _create_and_process_trip(workspace, "Trip B", SHARED_LEG)
            segment = propose_shared_route_segments(workspace, trip_a, trip_b)[0]
            confirm_route_segment(workspace, segment.route_segment_id)
            run_baseline_research(
                workspace, trip_a, provider=FakeResearchSourceProvider()
            )

            stale_date = (date.today() - timedelta(days=1)).isoformat()
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                connection.execute(
                    "UPDATE research_claims SET recheck_date = ? WHERE category = "
                    "'ROUTE_RULES'",
                    (stale_date,),
                )

            class FailsOnlyRouteRulesRefresh:
                def find_sources(self, query: str, *, max_results: int = 2):
                    if "trail route rules" in query:
                        raise RuntimeError("simulated retrieval outage")
                    return FakeResearchSourceProvider().find_sources(
                        query, max_results=max_results
                    )

            result_b = run_baseline_research(
                workspace, trip_b, provider=FailsOnlyRouteRulesRefresh()
            )

            route_rules_b = next(
                claim
                for claim in result_b.claims
                if claim.category == ResearchCategory.ROUTE_RULES
            )
            self.assertTrue(route_rules_b.stale)
            self.assertTrue(route_rules_b.sources)

            report = run_cli(
                workspace,
                "trip",
                "research",
                "--trip-id",
                trip_b,
                extra_environment={"AA_CONTENT_FAKE_PROVIDERS": "1"},
            )
            self.assertIn("STALE", report.stdout)

    def test_route_segment_list_reflects_trip_membership(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_a = _create_and_process_trip(workspace, "Trip A", SHARED_LEG)
            trip_b = _create_and_process_trip(workspace, "Trip B", SHARED_LEG)
            segment = propose_shared_route_segments(workspace, trip_a, trip_b)[0]
            confirm_route_segment(workspace, segment.route_segment_id)

            segments_for_a = list_route_segments(workspace, trip_a)

            self.assertEqual(len(segments_for_a), 1)
            self.assertEqual(segments_for_a[0].route_segment_id, segment.route_segment_id)


if __name__ == "__main__":
    unittest.main()
