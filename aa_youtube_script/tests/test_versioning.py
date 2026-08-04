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
from aa_content.models import VersionComponent  # noqa: E402
from aa_content.narration import generate_narration  # noqa: E402
from aa_content.research_providers import FakeResearchSourceProvider  # noqa: E402
from aa_content.versioning import approve_component, get_version_status, submit_review


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


ITINERARY = (
    "Day 1: Arrive in Kyoto by train.\n"
    "Day 2: Walk from Magome to Tsumago, about 4 hours. Overnight stay in a "
    "guesthouse in Tsumago. Breakfast and dinner included.\n"
)


def _prepare_submittable_trip(workspace: Path, provider=None) -> str:
    provider = provider or FakeResearchSourceProvider()
    assert run_cli(workspace, "init").returncode == 0
    created = run_cli(workspace, "trip", "create", "--name", "Nakasendo", stdin=ITINERARY)
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


class VersioningTests(unittest.TestCase):
    def test_submit_creates_v1_referencing_exact_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submittable_trip(workspace)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                trip_revision, angle_id = connection.execute(
                    """
                    SELECT current_itinerary_revision_id, current_content_angle_id
                    FROM trips WHERE trip_id = ?
                    """,
                    (trip_id,),
                ).fetchone()

            version = submit_review(workspace, trip_id)

            self.assertEqual(version.version_number, 1)
            self.assertEqual(version.itinerary_revision_id, trip_revision)
            self.assertEqual(version.angle_id, angle_id)
            self.assertTrue(version.content_hash)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                findings_json, acks_json, claims_json = connection.execute(
                    """
                    SELECT findings_json, acknowledgments_json, claims_json
                    FROM editorial_package_versions WHERE trip_id = ? AND
                    version_number = 1
                    """,
                    (trip_id,),
                ).fetchone()
                current_version_marker = connection.execute(
                    "SELECT current_editorial_package_version FROM trips "
                    "WHERE trip_id = ?",
                    (trip_id,),
                ).fetchone()[0]
            self.assertIn("[", findings_json)
            self.assertIn("[", acks_json)
            self.assertGreater(len(claims_json), 2)
            self.assertEqual(current_version_marker, "v1")

    def test_repeated_submission_creates_sequential_versions_not_duplicates(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submittable_trip(workspace)

            v1 = submit_review(workspace, trip_id)
            v2 = submit_review(workspace, trip_id)

            self.assertEqual(v1.version_number, 1)
            self.assertEqual(v2.version_number, 2)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                version_numbers = [
                    row[0]
                    for row in connection.execute(
                        "SELECT version_number FROM editorial_package_versions "
                        "WHERE trip_id = ? ORDER BY version_number",
                        (trip_id,),
                    ).fetchall()
                ]
            self.assertEqual(version_numbers, [1, 2])

    def test_approve_narration_then_final(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submittable_trip(workspace)
            submit_review(workspace, trip_id)

            narration_approval = approve_component(
                workspace, trip_id, VersionComponent.NARRATION, "Jane Ops"
            )
            final_approval = approve_component(
                workspace, trip_id, VersionComponent.FINAL, "Jane Ops"
            )

            self.assertEqual(narration_approval.approver, "Jane Ops")
            self.assertEqual(narration_approval.version_number, 1)
            self.assertEqual(final_approval.version_number, 1)
            status = get_version_status(workspace, trip_id)
            self.assertEqual(status.status_for(VersionComponent.NARRATION).validity, "VALID")
            self.assertEqual(status.status_for(VersionComponent.FINAL).validity, "VALID")

    def test_final_requires_narration_approval_first(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submittable_trip(workspace)
            submit_review(workspace, trip_id)

            with self.assertRaises(UserFacingError):
                approve_component(
                    workspace, trip_id, VersionComponent.FINAL, "Jane Ops"
                )

    def test_approval_records_approver_timestamp_version_and_integrity(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submittable_trip(workspace)
            version = submit_review(workspace, trip_id)

            approval = approve_component(
                workspace, trip_id, VersionComponent.NARRATION, "Jane Ops"
            )

            self.assertEqual(approval.approver, "Jane Ops")
            self.assertTrue(approval.approved_at)
            self.assertEqual(approval.version_number, version.version_number)
            self.assertEqual(approval.content_integrity_reference, version.narration_signature)

    def test_narration_change_invalidates_narration_and_final_approval(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submittable_trip(workspace)
            submit_review(workspace, trip_id)
            approve_component(workspace, trip_id, VersionComponent.NARRATION, "Jane Ops")
            approve_component(workspace, trip_id, VersionComponent.FINAL, "Jane Ops")

            generate_narration(
                workspace,
                trip_id,
                editorial_notes="A brand new editorial note.",
                force=True,
            )

            status = get_version_status(workspace, trip_id)
            self.assertEqual(
                status.status_for(VersionComponent.NARRATION).validity, "INVALIDATED"
            )
            self.assertEqual(
                status.status_for(VersionComponent.FINAL).validity, "INVALIDATED"
            )
            # The prior approval record itself is preserved as history.
            self.assertIsNotNone(
                status.status_for(VersionComponent.NARRATION).approval
            )

    def test_invalidated_approval_blocks_reapproval_until_new_version(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submittable_trip(workspace)
            submit_review(workspace, trip_id)
            approve_component(workspace, trip_id, VersionComponent.NARRATION, "Jane Ops")
            generate_narration(
                workspace, trip_id, editorial_notes="Changed.", force=True
            )

            with self.assertRaises(UserFacingError):
                approve_component(
                    workspace, trip_id, VersionComponent.FINAL, "Jane Ops"
                )

            submit_review(workspace, trip_id)
            new_narration_approval = approve_component(
                workspace, trip_id, VersionComponent.NARRATION, "Jane Ops"
            )
            self.assertEqual(new_narration_approval.version_number, 2)

    def test_visible_drafts_preserved_after_invalidation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submittable_trip(workspace)
            submit_review(workspace, trip_id)
            approve_component(workspace, trip_id, VersionComponent.NARRATION, "Jane Ops")
            generate_narration(
                workspace, trip_id, editorial_notes="Changed again.", force=True
            )

            trip_directory = next((workspace / "outputs").iterdir())
            self.assertTrue(
                (trip_directory / "working" / "narration.md").is_file()
            )

    def test_earlier_version_remains_immutable_after_new_version_submitted(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submittable_trip(workspace)
            v1 = submit_review(workspace, trip_id)

            generate_narration(
                workspace, trip_id, editorial_notes="Second draft.", force=True
            )
            v2 = submit_review(workspace, trip_id)

            with sqlite3.connect(workspace / "aa_content.db") as connection:
                v1_row = connection.execute(
                    """
                    SELECT narration_signature, angle_id FROM
                    editorial_package_versions WHERE trip_id = ? AND
                    version_number = 1
                    """,
                    (trip_id,),
                ).fetchone()
            self.assertEqual(v1_row[0], v1.narration_signature)
            self.assertEqual(v1_row[1], v1.angle_id)
            self.assertNotEqual(v1.narration_signature, v2.narration_signature)

    def test_submitting_without_narration_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            assert run_cli(workspace, "init").returncode == 0
            created = run_cli(
                workspace, "trip", "create", "--name", "Nakasendo", stdin=ITINERARY
            )
            trip_id = next(
                line.removeprefix("Trip ID: ")
                for line in created.stdout.splitlines()
                if line.startswith("Trip ID: ")
            )

            with self.assertRaises(UserFacingError):
                submit_review(workspace, trip_id)


if __name__ == "__main__":
    unittest.main()
