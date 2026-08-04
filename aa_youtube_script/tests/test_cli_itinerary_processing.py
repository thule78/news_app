from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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


def create_trip(workspace: Path, name: str, itinerary: str) -> str:
    result = run_cli(workspace, "trip", "create", "--name", name, stdin=itinerary)
    assert result.returncode == 0, result.stderr
    return next(
        line.removeprefix("Trip ID: ")
        for line in result.stdout.splitlines()
        if line.startswith("Trip ID: ")
    )


FAKE_PROVIDER_ENVIRONMENT = {"AA_CONTENT_FAKE_PROVIDERS": "1"}


class ItineraryProcessingCliTests(unittest.TestCase):
    def test_supplier_data_is_removed_before_normalization_and_blocks_export(
        self,
    ) -> None:
        itinerary = (
            "Day 1: Arrive in Kyoto. Contact supplier: Yamada Tours, net rate "
            "JPY 8000 per night. Email agent@example.com.\n"
            "Day 2: Walk from Magome to Tsumago, about 3-4 hours. Overnight "
            "stay in a ryokan in Tsumago. Breakfast included.\n"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_id = create_trip(workspace, "Nakasendo", itinerary)

            result = run_cli(
                workspace,
                "trip",
                "process",
                "--trip-id",
                trip_id,
                extra_environment=FAKE_PROVIDER_ENVIRONMENT,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Supplier Data: REVIEW_REQUIRED", result.stdout)
            self.assertIn("Export: BLOCKED", result.stdout)

            trip_directory = next((workspace / "outputs").iterdir())
            sanitized = (
                trip_directory / "source" / "r1" / "sanitized-itinerary.txt"
            ).read_text()
            self.assertNotIn("Yamada Tours", sanitized)
            self.assertNotIn("8000", sanitized)
            self.assertNotIn("agent@example.com", sanitized)
            self.assertIn("Walk from Magome to Tsumago", sanitized)

            original = (
                trip_directory / "source" / "r1" / "original-itinerary.txt"
            ).read_text()
            self.assertIn("Yamada Tours", original)

            with sqlite3.connect(workspace / "aa_content.db") as connection:
                findings = connection.execute(
                    "SELECT category FROM supplier_data_findings"
                ).fetchall()
                export_block = connection.execute(
                    "SELECT status FROM export_blocks"
                ).fetchone()
            self.assertGreaterEqual(len(findings), 2)
            self.assertEqual(export_block, ("ACTIVE",))

    def test_clean_itinerary_normalizes_without_export_block(self) -> None:
        itinerary = (
            "Day 1: Arrive in Kyoto by train from the airport.\n"
            "Day 2: Walk from Magome to Tsumago, about 4 hours. Overnight "
            "stay in a guesthouse in Tsumago. Breakfast and dinner "
            "included.\n"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_id = create_trip(workspace, "Nakasendo", itinerary)

            result = run_cli(
                workspace,
                "trip",
                "process",
                "--trip-id",
                trip_id,
                extra_environment=FAKE_PROVIDER_ENVIRONMENT,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Itinerary processed", result.stdout)
            self.assertIn("Supplier Data: CLEAR (0 removals)", result.stdout)
            self.assertIn("Missing Information: 0", result.stdout)
            self.assertIn("Fact Conflicts: 0", result.stdout)
            self.assertIn("Export: READY", result.stdout)

    def test_conflicting_duration_statements_produce_fact_conflict(self) -> None:
        itinerary = (
            "Day 1: Walk from Magome to Tsumago, about 3 hours in the "
            "morning.\n"
            "Day 2: Some say the walk from Magome to Tsumago takes about 6 "
            "hours instead.\n"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_id = create_trip(workspace, "Nakasendo", itinerary)

            result = run_cli(
                workspace,
                "trip",
                "process",
                "--trip-id",
                trip_id,
                extra_environment=FAKE_PROVIDER_ENVIRONMENT,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Fact Conflicts: 1", result.stdout)
            trip_directory = next((workspace / "outputs").iterdir())
            normalized_markdown = (
                trip_directory / "source" / "r1" / "normalized-itinerary.md"
            ).read_text()
            self.assertIn("Magome to Tsumago", normalized_markdown)
            self.assertIn("Conflicting duration statements", normalized_markdown)

    def test_compatible_duration_ranges_merge_into_estimated_duration(self) -> None:
        itinerary = (
            "Day 1: Walk from Magome to Tsumago, about 3-4 hours.\n"
            "Day 2: The walk from Magome to Tsumago usually takes 4-5 hours "
            "in summer.\n"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_id = create_trip(workspace, "Nakasendo", itinerary)

            result = run_cli(
                workspace,
                "trip",
                "process",
                "--trip-id",
                trip_id,
                extra_environment=FAKE_PROVIDER_ENVIRONMENT,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Fact Conflicts: 0", result.stdout)

    def test_repeating_process_reuses_result_without_duplicate_attempts(
        self,
    ) -> None:
        itinerary = "Day 1: Walk from Magome to Tsumago, about 4 hours.\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_id = create_trip(workspace, "Nakasendo", itinerary)

            first = run_cli(
                workspace,
                "trip",
                "process",
                "--trip-id",
                trip_id,
                extra_environment=FAKE_PROVIDER_ENVIRONMENT,
            )
            second = run_cli(
                workspace,
                "trip",
                "process",
                "--trip-id",
                trip_id,
                extra_environment=FAKE_PROVIDER_ENVIRONMENT,
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("Itinerary reused", second.stdout)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                attempt_count = connection.execute(
                    """
                    SELECT COUNT(*) FROM stage_attempts AS attempt
                    JOIN workflow_stages AS stage
                      ON stage.workflow_stage_id = attempt.workflow_stage_id
                    WHERE stage.stage_name = 'itinerary_process'
                    """
                ).fetchone()[0]
                normalized_count = connection.execute(
                    "SELECT COUNT(*) FROM normalized_itineraries"
                ).fetchone()[0]
            self.assertEqual(attempt_count, 1)
            self.assertEqual(normalized_count, 1)

    def test_force_reprocesses_without_duplicating_revision_records(self) -> None:
        itinerary = "Day 1: Walk from Magome to Tsumago, about 4 hours.\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_id = create_trip(workspace, "Nakasendo", itinerary)
            self.assertEqual(
                run_cli(
                    workspace,
                    "trip",
                    "process",
                    "--trip-id",
                    trip_id,
                    extra_environment=FAKE_PROVIDER_ENVIRONMENT,
                ).returncode,
                0,
            )

            forced = run_cli(
                workspace,
                "trip",
                "process",
                "--trip-id",
                trip_id,
                "--force",
                extra_environment=FAKE_PROVIDER_ENVIRONMENT,
            )

            self.assertEqual(forced.returncode, 0, forced.stderr)
            self.assertIn("Itinerary regenerated", forced.stdout)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                revision_count = connection.execute(
                    "SELECT COUNT(*) FROM itinerary_revisions"
                ).fetchone()[0]
                normalized_count = connection.execute(
                    "SELECT COUNT(*) FROM normalized_itineraries"
                ).fetchone()[0]
                attempt_count = connection.execute(
                    """
                    SELECT COUNT(*) FROM stage_attempts AS attempt
                    JOIN workflow_stages AS stage
                      ON stage.workflow_stage_id = attempt.workflow_stage_id
                    WHERE stage.stage_name = 'itinerary_process'
                    """
                ).fetchone()[0]
            self.assertEqual(revision_count, 1)
            self.assertEqual(normalized_count, 1)
            self.assertEqual(attempt_count, 2)

    def test_processing_without_configured_provider_fails_clearly(self) -> None:
        itinerary = "Day 1: Walk from Magome to Tsumago, about 4 hours.\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_id = create_trip(workspace, "Nakasendo", itinerary)

            result = run_cli(workspace, "trip", "process", "--trip-id", trip_id)

            self.assertEqual(result.returncode, 2)
            self.assertIn("OPENAI_API_KEY", result.stderr)


if __name__ == "__main__":
    unittest.main()
