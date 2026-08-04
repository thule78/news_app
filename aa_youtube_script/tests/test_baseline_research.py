from __future__ import annotations

import json
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
from aa_content.errors import StageExecutionError  # noqa: E402
from aa_content.models import EvidenceStatus, ResearchCategory  # noqa: E402
from aa_content.research_providers import (  # noqa: E402
    FakeResearchSourceProvider,
    ResearchDocument,
)


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


FAKE_PROVIDER_ENVIRONMENT = {"AA_CONTENT_FAKE_PROVIDERS": "1"}
ITINERARY = (
    "Day 1: Arrive in Kyoto by train from the airport.\n"
    "Day 2: Walk from Magome to Tsumago, about 4 hours. Overnight stay in a "
    "guesthouse in Tsumago. Breakfast and dinner included.\n"
)


def _prepare_processed_trip(workspace: Path, name: str = "Nakasendo") -> str:
    assert run_cli(workspace, "init").returncode == 0
    created = run_cli(workspace, "trip", "create", "--name", name, stdin=ITINERARY)
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
        extra_environment=FAKE_PROVIDER_ENVIRONMENT,
    )
    assert processed.returncode == 0, processed.stderr
    return trip_id


class BaselineResearchCliTests(unittest.TestCase):
    def test_research_requires_processed_itinerary_first(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            created = run_cli(
                workspace, "trip", "create", "--name", "Nakasendo", stdin=ITINERARY
            )
            trip_id = next(
                line.removeprefix("Trip ID: ")
                for line in created.stdout.splitlines()
                if line.startswith("Trip ID: ")
            )

            result = run_cli(
                workspace,
                "trip",
                "research",
                "--trip-id",
                trip_id,
                extra_environment=FAKE_PROVIDER_ENVIRONMENT,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("run `trip process`", result.stderr)

    def test_baseline_research_covers_all_required_categories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_processed_trip(workspace)

            result = run_cli(
                workspace,
                "trip",
                "research",
                "--trip-id",
                trip_id,
                extra_environment=FAKE_PROVIDER_ENVIRONMENT,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Baseline Research researched", result.stdout)
            for category in (
                "ACCESS",
                "ROUTE_RULES",
                "SEASONALITY",
                "CROWDS",
                "INDEPENDENT_TRANSPORT",
                "SOLO_TRAVELLER",
                "OFFICIAL_ADVISORY",
                "PRACTICAL_DEMANDS",
            ):
                self.assertIn(category, result.stdout)

            with sqlite3.connect(workspace / "aa_content.db") as connection:
                claim_count = connection.execute(
                    "SELECT COUNT(*) FROM research_claims"
                ).fetchone()[0]
                distinct_categories = connection.execute(
                    "SELECT COUNT(DISTINCT category) FROM research_claims"
                ).fetchone()[0]
            self.assertEqual(claim_count, 8)
            self.assertEqual(distinct_categories, 8)

    def test_independent_transport_query_uses_itinerary_route_leg(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_processed_trip(workspace)
            self.assertEqual(
                run_cli(
                    workspace,
                    "trip",
                    "research",
                    "--trip-id",
                    trip_id,
                    extra_environment=FAKE_PROVIDER_ENVIRONMENT,
                ).returncode,
                0,
            )
            trip_directory = next((workspace / "outputs").iterdir())
            report = json.loads(
                (trip_directory / "source" / "r1" / "baseline-research.json")
                .read_text()
            )
            transport_claim = next(
                claim
                for claim in report["claims"]
                if claim["category"] == "INDEPENDENT_TRANSPORT"
            )
            self.assertTrue(
                any(
                    "Magome" in source["title"] and "Tsumago" in source["title"]
                    for source in transport_claim["sources"]
                )
            )

    def test_no_full_page_text_is_persisted_anywhere(self) -> None:
        verbatim_sentence = (
            "This exact sentence must never be copied into storage verbatim "
            "because it is the full copyrighted page body."
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_processed_trip(workspace)
            provider = FakeResearchSourceProvider(
                overrides={
                    "entry access": [
                        ResearchDocument(
                            url="https://example.test/access",
                            title="Access guide",
                            publisher="example.test",
                            extracted_text=verbatim_sentence,
                        )
                    ]
                }
            )

            run_baseline_research(workspace, trip_id, provider=provider)

            db_bytes = (workspace / "aa_content.db").read_bytes()
            self.assertNotIn(verbatim_sentence.encode(), db_bytes)
            trip_directory = next((workspace / "outputs").iterdir())
            for path in trip_directory.rglob("*"):
                if path.is_file():
                    self.assertNotIn(
                        verbatim_sentence.encode(), path.read_bytes()
                    )

    def test_official_source_verifies_access_but_not_crowds(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_processed_trip(workspace)
            official = ResearchDocument(
                url="https://travel.state.gov/notice",
                title="Official entry notice",
                publisher="travel.state.gov",
                extracted_text="Official access notice content.",
            )
            provider = FakeResearchSourceProvider(
                overrides={
                    "entry access": [official],
                    "government travel advisory": [official],
                    "crowd levels": [official],
                }
            )

            result = run_baseline_research(workspace, trip_id, provider=provider)

            by_category = {claim.category: claim for claim in result.claims}
            self.assertEqual(
                by_category[ResearchCategory.ACCESS].evidence_status,
                EvidenceStatus.VERIFIED,
            )
            self.assertEqual(
                by_category[ResearchCategory.OFFICIAL_ADVISORY].evidence_status,
                EvidenceStatus.VERIFIED,
            )
            self.assertEqual(
                by_category[ResearchCategory.CROWDS].evidence_status,
                EvidenceStatus.INDICATIVE,
            )

    def test_zero_sources_produce_unknown_claim_with_no_evidence_links(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_processed_trip(workspace)
            provider = FakeResearchSourceProvider(
                overrides={"entry access": []}
            )

            result = run_baseline_research(workspace, trip_id, provider=provider)

            by_category = {claim.category: claim for claim in result.claims}
            access_claim = by_category[ResearchCategory.ACCESS]
            self.assertEqual(access_claim.evidence_status, EvidenceStatus.UNKNOWN)
            self.assertEqual(access_claim.sources, ())
            self.assertIn(ResearchCategory.ACCESS, result.missing_categories)

            for claim in result.claims:
                if claim.evidence_status is not EvidenceStatus.UNKNOWN:
                    self.assertGreaterEqual(len(claim.sources), 1)

    def test_time_sensitive_categories_receive_recheck_dates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_processed_trip(workspace)

            result = run_baseline_research(
                workspace, trip_id, provider=FakeResearchSourceProvider()
            )

            by_category = {claim.category: claim for claim in result.claims}
            for category in (
                ResearchCategory.ACCESS,
                ResearchCategory.OFFICIAL_ADVISORY,
                ResearchCategory.SEASONALITY,
                ResearchCategory.CROWDS,
                ResearchCategory.INDEPENDENT_TRANSPORT,
                ResearchCategory.ROUTE_RULES,
            ):
                self.assertIsNotNone(by_category[category].recheck_date)
            for category in (
                ResearchCategory.SOLO_TRAVELLER,
                ResearchCategory.PRACTICAL_DEMANDS,
            ):
                self.assertIsNone(by_category[category].recheck_date)

    def test_reusing_completed_research_does_not_duplicate_claims(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_processed_trip(workspace)
            provider = FakeResearchSourceProvider()

            run_baseline_research(workspace, trip_id, provider=provider)
            second = run_baseline_research(workspace, trip_id, provider=provider)

            self.assertEqual(second.outcome, "reused")
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                claim_count = connection.execute(
                    "SELECT COUNT(*) FROM research_claims"
                ).fetchone()[0]
                attempt_count = connection.execute(
                    """
                    SELECT COUNT(*) FROM stage_attempts AS attempt
                    JOIN workflow_stages AS stage
                      ON stage.workflow_stage_id = attempt.workflow_stage_id
                    WHERE stage.stage_name = 'baseline_research'
                    """
                ).fetchone()[0]
            self.assertEqual(claim_count, 8)
            self.assertEqual(attempt_count, 1)

    def test_interrupted_research_resumes_without_repeating_completed_categories(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_processed_trip(workspace)

            call_log: list[str] = []

            class FailingAfterTwoProvider:
                def find_sources(self, query: str, *, max_results: int = 2):
                    call_log.append(query)
                    if len(call_log) > 2:
                        raise RuntimeError("simulated network failure")
                    return FakeResearchSourceProvider().find_sources(
                        query, max_results=max_results
                    )

            with self.assertRaises(StageExecutionError):
                run_baseline_research(
                    workspace, trip_id, provider=FailingAfterTwoProvider()
                )

            with sqlite3.connect(workspace / "aa_content.db") as connection:
                stage_status = connection.execute(
                    "SELECT status FROM workflow_stages WHERE stage_name = "
                    "'baseline_research'"
                ).fetchone()[0]
                claims_after_failure = connection.execute(
                    "SELECT COUNT(*) FROM research_claims"
                ).fetchone()[0]
                surviving_source_ids = set(
                    row[0]
                    for row in connection.execute(
                        "SELECT source_record_id FROM source_records"
                    ).fetchall()
                )
            self.assertEqual(stage_status, "FAILED")
            self.assertEqual(claims_after_failure, 2)
            # Only ACCESS and ROUTE_RULES completed before the simulated failure.
            self.assertEqual(len(surviving_source_ids), 4)

            result = run_baseline_research(
                workspace, trip_id, provider=FakeResearchSourceProvider()
            )

            self.assertEqual(result.outcome, "resumed")
            self.assertEqual(len(result.claims), 8)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                attempt_count = connection.execute(
                    """
                    SELECT COUNT(*) FROM stage_attempts AS attempt
                    JOIN workflow_stages AS stage
                      ON stage.workflow_stage_id = attempt.workflow_stage_id
                    WHERE stage.stage_name = 'baseline_research'
                    """
                ).fetchone()[0]
                claim_count = connection.execute(
                    "SELECT COUNT(*) FROM research_claims"
                ).fetchone()[0]
                resumed_source_ids = set(
                    row[0]
                    for row in connection.execute(
                        "SELECT source_record_id FROM source_records"
                    ).fetchall()
                )
            self.assertEqual(attempt_count, 2)
            self.assertEqual(claim_count, 8)
            # The categories completed before the crash were never re-fetched:
            # their source_record rows are the exact same ones, untouched.
            self.assertTrue(surviving_source_ids.issubset(resumed_source_ids))
            self.assertEqual(len(resumed_source_ids), 16)

    def test_normalized_itinerary_is_untouched_by_research(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_processed_trip(workspace)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                before = connection.execute(
                    "SELECT normalized_json FROM normalized_itineraries"
                ).fetchone()[0]

            run_baseline_research(
                workspace, trip_id, provider=FakeResearchSourceProvider()
            )

            with sqlite3.connect(workspace / "aa_content.db") as connection:
                after = connection.execute(
                    "SELECT normalized_json FROM normalized_itineraries"
                ).fetchone()[0]
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
