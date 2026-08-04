from __future__ import annotations

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
from aa_content.content_angle import (  # noqa: E402
    approve_generated_angle,
    propose_content_angles,
    run_angle_research,
)
from aa_content.errors import UserFacingError  # noqa: E402
from aa_content.narration import generate_narration  # noqa: E402
from aa_content.research_providers import FakeResearchSourceProvider  # noqa: E402
from aa_content.validation import (  # noqa: E402
    QUALITY_BENCHMARK,
    acknowledge_finding,
    validate_package,
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


def _prepare_validated_trip(
    workspace: Path, itinerary: str, provider=None
) -> str:
    provider = provider or FakeResearchSourceProvider()
    assert run_cli(workspace, "init").returncode == 0
    created = run_cli(workspace, "trip", "create", "--name", "Nakasendo", stdin=itinerary)
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
    run_baseline_research(workspace, trip_id, provider=provider)
    proposed = propose_content_angles(workspace, trip_id)
    approve_generated_angle(workspace, trip_id, proposed.options[0].angle_id)
    run_angle_research(workspace, trip_id, provider=provider)
    generate_narration(workspace, trip_id)
    return trip_id


CLEAN_ITINERARY = (
    "Day 1: Arrive in Kyoto by train.\n"
    "Day 2: Walk from Magome to Tsumago, about 4 hours. Overnight stay in a "
    "guesthouse in Tsumago. Breakfast and dinner included.\n"
)
SUPPLIER_DATA_ITINERARY = (
    "Day 1: Contact supplier: Yamada Tours, net rate JPY 8000 per night.\n"
    "Day 2: Walk from Magome to Tsumago, about 4 hours. Overnight stay in a "
    "guesthouse in Tsumago. Breakfast included.\n"
)
MISSING_TRANSPORT_ITINERARY = (
    "Day 1: Arrive in Kyoto.\n"
    "Day 2: Walk from Magome to Tsumago, about 4 hours. Overnight stay in a "
    "guesthouse in Tsumago.\n"
)


class ValidationTests(unittest.TestCase):
    def test_clean_package_scores_full_marks_with_no_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_validated_trip(workspace, CLEAN_ITINERARY)

            report = validate_package(workspace, trip_id)

            self.assertEqual(report.quality_score, 100)
            self.assertEqual(report.findings, ())
            self.assertFalse(report.export_blocked)

    def test_missing_information_is_flagged_as_advisory_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_validated_trip(
                workspace, MISSING_TRANSPORT_ITINERARY
            )

            report = validate_package(workspace, trip_id)

            missing_findings = [
                f for f in report.findings if f.code == "MISSING_INFORMATION"
            ]
            self.assertTrue(missing_findings)
            self.assertTrue(all(f.severity == "WARNING" for f in missing_findings))
            self.assertFalse(report.export_blocked)

    def test_supplier_data_creates_the_only_blocking_finding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_validated_trip(
                workspace, SUPPLIER_DATA_ITINERARY
            )

            report = validate_package(workspace, trip_id)

            self.assertTrue(report.export_blocked)
            self.assertEqual(len(report.blocking_findings), 1)
            self.assertEqual(report.blocking_findings[0].code, "SUPPLIER_DATA")
            for finding in report.findings:
                if finding.code != "SUPPLIER_DATA":
                    self.assertEqual(finding.severity, "WARNING")

    def test_advisory_warnings_are_distinct_from_the_export_block(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_validated_trip(
                workspace, MISSING_TRANSPORT_ITINERARY
            )

            report = validate_package(workspace, trip_id)

            # Advisory-only package: reviewable/exportable, not blocked.
            self.assertFalse(report.export_blocked)
            self.assertEqual(report.blocking_findings, ())
            self.assertTrue(report.unacknowledged_warnings)

    def test_stale_claim_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_validated_trip(workspace, CLEAN_ITINERARY)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                connection.execute(
                    "UPDATE research_claims SET stale = 1 WHERE category = "
                    "'ROUTE_RULES'"
                )

            report = validate_package(workspace, trip_id)

            stale_findings = [f for f in report.findings if f.code == "STALE_CLAIM"]
            self.assertEqual(len(stale_findings), 1)
            self.assertLess(report.quality_score, 100)

    def test_fact_conflict_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_validated_trip(workspace, CLEAN_ITINERARY)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                normalized_json = connection.execute(
                    "SELECT normalized_json FROM normalized_itineraries"
                ).fetchone()[0]
                import json as _json

                normalized = _json.loads(normalized_json)
                normalized["fact_conflicts"] = [
                    {"subject": "Test leg duration", "reason": "conflicting"}
                ]
                connection.execute(
                    "UPDATE normalized_itineraries SET normalized_json = ?",
                    (_json.dumps(normalized),),
                )

            report = validate_package(workspace, trip_id)

            conflict_findings = [
                f for f in report.findings if f.code == "FACT_CONFLICT"
            ]
            self.assertEqual(len(conflict_findings), 1)

    def test_price_information_and_promise_language_are_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_validated_trip(workspace, CLEAN_ITINERARY)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                sections_json = connection.execute(
                    "SELECT sections_json FROM narrations"
                ).fetchone()[0]
                import json as _json

                sections = _json.loads(sections_json)
                sections[0]["body"] += (
                    " This trip costs $199 and we guarantee good weather."
                )
                connection.execute(
                    "UPDATE narrations SET sections_json = ?",
                    (_json.dumps(sections),),
                )

            report = validate_package(workspace, trip_id)

            codes = {f.code for f in report.findings}
            self.assertIn("PRICE_INFORMATION", codes)
            self.assertIn("UNSUPPORTED_PRODUCT_PROMISE", codes)

    def test_quality_score_shown_regardless_of_score(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_validated_trip(
                workspace, SUPPLIER_DATA_ITINERARY
            )

            result = run_cli(workspace, "trip", "validate", "--trip-id", trip_id)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Quality Score:", result.stdout)
            report = validate_package(workspace, trip_id)
            if report.quality_score < QUALITY_BENCHMARK:
                self.assertIn("Below benchmark", result.stdout)

    def test_below_benchmark_package_remains_reviewable_and_exportable_after_ack(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_validated_trip(
                workspace, MISSING_TRANSPORT_ITINERARY
            )
            report = validate_package(workspace, trip_id)
            self.assertTrue(report.unacknowledged_warnings)
            finding_id = report.unacknowledged_warnings[0].finding_id

            acknowledgment = acknowledge_finding(
                workspace, trip_id, finding_id, "Jane Ops"
            )

            self.assertEqual(acknowledgment.approver, "Jane Ops")
            self.assertEqual(acknowledgment.finding_id, finding_id)
            self.assertTrue(acknowledgment.acknowledged_at)
            self.assertEqual(acknowledgment.draft_signature, report.draft_signature)

            report_after = validate_package(workspace, trip_id)
            self.assertIn(finding_id, report_after.acknowledged_ids)
            self.assertFalse(report_after.export_blocked)

    def test_blocking_finding_cannot_be_acknowledged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_validated_trip(
                workspace, SUPPLIER_DATA_ITINERARY
            )
            report = validate_package(workspace, trip_id)
            blocking_id = report.blocking_findings[0].finding_id

            with self.assertRaises(UserFacingError):
                acknowledge_finding(workspace, trip_id, blocking_id, "Jane Ops")

    def test_acknowledgment_records_approver_timestamp_and_draft_version(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_validated_trip(
                workspace, MISSING_TRANSPORT_ITINERARY
            )
            report = validate_package(workspace, trip_id)
            finding_id = report.unacknowledged_warnings[0].finding_id

            acknowledgment = acknowledge_finding(
                workspace, trip_id, finding_id, "Jane Ops"
            )

            with sqlite3.connect(workspace / "aa_content.db") as connection:
                row = connection.execute(
                    """
                    SELECT finding_id, approver, acknowledged_at, draft_signature
                    FROM validation_acknowledgments
                    WHERE finding_id = ?
                    """,
                    (finding_id,),
                ).fetchone()
            self.assertEqual(row[0], finding_id)
            self.assertEqual(row[1], "Jane Ops")
            self.assertTrue(row[2])
            self.assertEqual(row[3], acknowledgment.draft_signature)

    def test_revalidating_unchanged_package_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_validated_trip(workspace, CLEAN_ITINERARY)

            first = validate_package(workspace, trip_id)
            second = validate_package(workspace, trip_id)

            self.assertEqual(first.draft_signature, second.draft_signature)
            self.assertEqual(first.quality_score, second.quality_score)
            self.assertEqual(
                {f.finding_id for f in first.findings},
                {f.finding_id for f in second.findings},
            )
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                report_count = connection.execute(
                    "SELECT COUNT(*) FROM validation_reports"
                ).fetchone()[0]
            self.assertEqual(report_count, 1)

    def test_acknowledgment_survives_idempotent_revalidation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_validated_trip(
                workspace, MISSING_TRANSPORT_ITINERARY
            )
            report = validate_package(workspace, trip_id)
            finding_id = report.unacknowledged_warnings[0].finding_id
            acknowledge_finding(workspace, trip_id, finding_id, "Jane Ops")

            report_again = validate_package(workspace, trip_id)

            self.assertIn(finding_id, report_again.acknowledged_ids)


if __name__ == "__main__":
    unittest.main()
