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
    approve_custom_angle,
    approve_generated_angle,
    propose_content_angles,
    run_angle_research,
)
from aa_content.errors import UserFacingError  # noqa: E402
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


ITINERARY = (
    "Day 1: Arrive in Kyoto by train.\n"
    "Day 2: Walk from Magome to Tsumago, about 4 hours. Overnight stay in a "
    "guesthouse in Tsumago.\n"
)


def _prepare_researched_trip(workspace: Path, provider=None) -> str:
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
    run_baseline_research(
        workspace, trip_id, provider=provider or FakeResearchSourceProvider()
    )
    return trip_id


class ContentAngleTests(unittest.TestCase):
    def test_generated_proposal_covers_all_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_researched_trip(workspace)

            result = propose_content_angles(workspace, trip_id)

            self.assertLessEqual(len(result.options), 3)
            self.assertGreater(len(result.options), 0)
            for option in result.options:
                self.assertTrue(option.viewer_question)
                self.assertTrue(option.available_evidence)
                self.assertTrue(option.commercial_relevance)
                self.assertTrue(option.risks)
                self.assertEqual(option.status, "PROPOSED")
                self.assertEqual(option.source, "GENERATED")

    def test_never_proposes_more_than_available_well_supported_categories(
        self,
    ) -> None:
        # Only SEASONALITY/CROWDS end up well-supported (single, non-official
        # source -> INDICATIVE); PRACTICAL_DEMANDS and SOLO_TRAVELLER get
        # zero sources -> UNKNOWN. Only one angle should qualify.
        weak_doc = [
            ResearchDocument(
                url="https://example.test/notes",
                title="Notes",
                publisher="example.test",
                extracted_text="Some travel notes.",
            )
        ]
        provider = FakeResearchSourceProvider(
            overrides={
                "best season weather": weak_doc,
                "crowd levels": weak_doc,
                "practical requirements": [],
                "solo traveller safety": [],
            }
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_researched_trip(workspace, provider=provider)

            result = propose_content_angles(workspace, trip_id)

            self.assertEqual(result.options, ())

    def test_fewer_than_three_when_only_some_categories_are_well_supported(
        self,
    ) -> None:
        strong_docs = [
            ResearchDocument(
                url="https://a.test/x", title="A", publisher="a.test",
                extracted_text="text",
            ),
            ResearchDocument(
                url="https://b.test/x", title="B", publisher="b.test",
                extracted_text="text",
            ),
        ]
        provider = FakeResearchSourceProvider(
            overrides={
                "practical requirements": [],
                "solo traveller safety": [],
                "best season weather": strong_docs,
                "crowd levels": strong_docs,
            }
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_researched_trip(workspace, provider=provider)

            result = propose_content_angles(workspace, trip_id)

            self.assertEqual(len(result.options), 1)
            self.assertIn("crowds", result.options[0].viewer_question.lower())

    def test_approving_generated_angle_binds_to_trip_and_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_researched_trip(workspace)
            proposed = propose_content_angles(workspace, trip_id)
            angle_id = proposed.options[0].angle_id

            approval = approve_generated_angle(workspace, trip_id, angle_id)

            self.assertEqual(approval.angle.status, "APPROVED")
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                current_angle, angle_trip, angle_revision = connection.execute(
                    """
                    SELECT trip.current_content_angle_id, angle.trip_id,
                           angle.itinerary_revision_id
                    FROM trips AS trip
                    JOIN content_angles AS angle
                      ON angle.angle_id = trip.current_content_angle_id
                    WHERE trip.trip_id = ?
                    """,
                    (trip_id,),
                ).fetchone()
            self.assertEqual(current_angle, angle_id)
            self.assertEqual(angle_trip, trip_id)

    def test_custom_angle_with_matching_evidence_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_researched_trip(workspace)

            approval = approve_custom_angle(
                workspace, trip_id, "What about crowds and seasonality here?"
            )

            self.assertEqual(approval.angle.evidence_support, "SUPPORTED")
            self.assertEqual(approval.angle.status, "APPROVED")
            self.assertEqual(
                approval.angle.viewer_question,
                "What about crowds and seasonality here?",
            )

    def test_unsupported_custom_angle_is_blocked_without_acknowledgement(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_researched_trip(workspace)

            with self.assertRaises(UserFacingError):
                approve_custom_angle(
                    workspace, trip_id, "Zzyzx quibble frobnicate?"
                )

            with sqlite3.connect(workspace / "aa_content.db") as connection:
                angle_count = connection.execute(
                    "SELECT COUNT(*) FROM content_angles WHERE source = 'CUSTOM'"
                ).fetchone()[0]
            self.assertEqual(angle_count, 0)

    def test_unsupported_custom_angle_preserves_exact_text_when_acknowledged(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_researched_trip(workspace)
            original_text = "Zzyzx quibble frobnicate?"

            approval = approve_custom_angle(
                workspace,
                trip_id,
                original_text,
                acknowledge_unsupported=True,
            )

            self.assertEqual(approval.angle.evidence_support, "UNSUPPORTED")
            # The system never silently reshapes the custom promise.
            self.assertEqual(approval.angle.viewer_question, original_text)

    def test_angle_research_requires_prior_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_researched_trip(workspace)

            with self.assertRaises(UserFacingError):
                run_angle_research(
                    workspace, trip_id, provider=FakeResearchSourceProvider()
                )

    def test_angle_research_persists_claim_and_sources_after_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_researched_trip(workspace)
            proposed = propose_content_angles(workspace, trip_id)
            angle_id = proposed.options[0].angle_id
            approve_generated_angle(workspace, trip_id, angle_id)

            result = run_angle_research(
                workspace, trip_id, provider=FakeResearchSourceProvider()
            )

            self.assertEqual(result.outcome, "researched")
            self.assertIsNotNone(result.claim)
            self.assertGreaterEqual(len(result.claim.sources), 1)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                claim_row = connection.execute(
                    """
                    SELECT category, angle_id FROM research_claims
                    WHERE angle_id = ?
                    """,
                    (angle_id,),
                ).fetchone()
                source_count = connection.execute(
                    "SELECT COUNT(*) FROM source_records WHERE category = "
                    "'ANGLE_SUPPORT'"
                ).fetchone()[0]
            self.assertEqual(claim_row, ("ANGLE_SUPPORT", angle_id))
            self.assertGreater(source_count, 0)

    def test_reusing_completed_angle_research_does_not_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_researched_trip(workspace)
            proposed = propose_content_angles(workspace, trip_id)
            angle_id = proposed.options[0].angle_id
            approve_generated_angle(workspace, trip_id, angle_id)
            provider = FakeResearchSourceProvider()

            run_angle_research(workspace, trip_id, provider=provider)
            second = run_angle_research(workspace, trip_id, provider=provider)

            self.assertEqual(second.outcome, "reused")
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                claim_count = connection.execute(
                    "SELECT COUNT(*) FROM research_claims WHERE angle_id = ?",
                    (angle_id,),
                ).fetchone()[0]
            self.assertEqual(claim_count, 1)

    def test_baseline_categories_still_have_exactly_one_row_after_angle_research(
        self,
    ) -> None:
        # Guards the shared research_claims table's uniqueness: angle-scoped
        # rows must never collide with the per-category baseline rows.
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_researched_trip(workspace)
            proposed = propose_content_angles(workspace, trip_id)
            approve_generated_angle(workspace, trip_id, proposed.options[0].angle_id)
            run_angle_research(
                workspace, trip_id, provider=FakeResearchSourceProvider()
            )

            with sqlite3.connect(workspace / "aa_content.db") as connection:
                counts = connection.execute(
                    """
                    SELECT category, COUNT(*) FROM research_claims
                    WHERE angle_id = ''
                    GROUP BY category
                    """
                ).fetchall()
            self.assertTrue(all(count == 1 for _, count in counts))
            self.assertEqual(len(counts), 8)


if __name__ == "__main__":
    unittest.main()
