from __future__ import annotations

import os
from pathlib import Path
import re
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
from aa_content.youtube_packaging import generate_youtube_packaging  # noqa: E402


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


def _prepare_submitted_trip(workspace: Path, provider=None) -> str:
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
    submit_review(workspace, trip_id)
    return trip_id


class YoutubePackagingTests(unittest.TestCase):
    def test_titles_have_two_of_each_required_style(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(workspace)

            result = generate_youtube_packaging(workspace, trip_id)

            styles = [title.style for title in result.packaging.titles]
            self.assertEqual(styles.count("SEARCH_LED"), 2)
            self.assertEqual(styles.count("CURIOSITY_LED"), 2)
            self.assertEqual(styles.count("HYBRID"), 2)
            self.assertEqual(len(result.packaging.titles), 6)

    def test_titles_reference_trip_name_or_approved_angle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(workspace)

            result = generate_youtube_packaging(workspace, trip_id)

            for title in result.packaging.titles:
                self.assertTrue(
                    "Nakasendo" in title.text
                    or result.angle.viewer_question in title.text
                )

    def test_description_contains_required_elements(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(workspace)

            result = generate_youtube_packaging(workspace, trip_id)
            description = result.packaging.description

            self.assertIn("Nakasendo", description)
            self.assertIn("Trip page: [link]", description)
            self.assertIn("Chapters:", description)
            self.assertIn("independent assessment", description)

    def test_chapters_align_with_narration_duration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(workspace)

            result = generate_youtube_packaging(workspace, trip_id)

            chapters = result.packaging.chapters
            self.assertGreaterEqual(len(chapters), 8)
            timestamps = [c.timestamp_seconds for c in chapters]
            self.assertEqual(timestamps, sorted(timestamps))
            self.assertEqual(timestamps[0], 0)

            loaded = None
            from aa_content.persistence import WorkspaceRepository

            repository = WorkspaceRepository(workspace)
            trip = repository.load_current_trip(trip_id)
            angle = repository.load_current_angle(trip.trip_id)
            loaded = repository.load_narration(trip.itinerary_revision_id, angle.angle_id)
            estimated_minutes = loaded[2]
            self.assertLess(timestamps[-1], estimated_minutes * 60 + 1)

    def test_thumbnail_brief_has_idea_cues_and_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(workspace)

            result = generate_youtube_packaging(workspace, trip_id)
            brief = result.packaging.thumbnail_brief

            self.assertTrue(brief.clear_idea)
            self.assertTrue(brief.destination_cues)
            self.assertTrue(brief.text_options)

    def test_keyword_metrics_are_not_available(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(workspace)

            result = generate_youtube_packaging(workspace, trip_id)

            self.assertTrue(result.packaging.keywords)
            for keyword in result.packaging.keywords:
                self.assertEqual(keyword.search_volume, "NOT_AVAILABLE")
                self.assertEqual(keyword.competition, "NOT_AVAILABLE")
                self.assertEqual(keyword.difficulty, "NOT_AVAILABLE")
                self.assertTrue(keyword.search_intent)

    def test_exactly_two_shorts_built_only_from_existing_narration_sentences(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(workspace)
            from aa_content.persistence import WorkspaceRepository

            repository = WorkspaceRepository(workspace)
            trip = repository.load_current_trip(trip_id)
            angle = repository.load_current_angle(trip.trip_id)
            sections = repository.load_narration(
                trip.itinerary_revision_id, angle.angle_id
            )[0]
            full_narration_text = " ".join(s.body for s in sections)

            result = generate_youtube_packaging(workspace, trip_id)

            self.assertEqual(len(result.packaging.shorts), 2)
            for short in result.packaging.shorts:
                for sentence in re.split(r"(?<=[.!?])\s+", short.body):
                    sentence = sentence.strip()
                    if sentence:
                        self.assertIn(sentence, full_narration_text)

    def test_no_price_information_anywhere_in_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(workspace)

            result = generate_youtube_packaging(workspace, trip_id)

            import json

            from aa_content.youtube_packaging import _PRICE_PATTERN, _serialize

            blob = json.dumps(_serialize(result.packaging))
            self.assertIsNone(_PRICE_PATTERN.search(blob))

    def test_requires_submitted_version_first(self) -> None:
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
            run_cli(
                workspace,
                "trip",
                "process",
                "--trip-id",
                trip_id,
                extra_environment={"AA_CONTENT_FAKE_PROVIDERS": "1"},
            )
            provider = FakeResearchSourceProvider()
            run_baseline_research(workspace, trip_id, provider=provider)
            proposed = propose_content_angles(workspace, trip_id)
            approve_generated_angle(workspace, trip_id, proposed.options[0].angle_id)
            run_angle_research(workspace, trip_id, provider=provider)
            generate_narration(workspace, trip_id)

            with self.assertRaises(UserFacingError):
                generate_youtube_packaging(workspace, trip_id)

    def test_narration_drift_since_submission_blocks_packaging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(workspace)
            generate_narration(
                workspace, trip_id, editorial_notes="Changed.", force=True
            )

            with self.assertRaises(UserFacingError):
                generate_youtube_packaging(workspace, trip_id)

    def test_regenerating_unchanged_package_is_reused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(workspace)

            first = generate_youtube_packaging(workspace, trip_id)
            second = generate_youtube_packaging(workspace, trip_id)

            self.assertEqual(first.content_signature, second.content_signature)
            self.assertEqual(second.outcome, "reused")

    def test_youtube_packaging_change_invalidates_only_final_not_narration(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(workspace)
            generate_youtube_packaging(workspace, trip_id)
            approve_component(workspace, trip_id, VersionComponent.NARRATION, "Jane Ops")
            approve_component(workspace, trip_id, VersionComponent.FINAL, "Jane Ops")

            # Simulate a subsequent YouTube packaging edit/regeneration that
            # changes its content signature without touching narration.
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                connection.execute(
                    "UPDATE youtube_packaging SET content_signature = "
                    "'simulated-changed-signature'"
                )

            status = get_version_status(workspace, trip_id)

            self.assertEqual(
                status.status_for(VersionComponent.NARRATION).validity, "VALID"
            )
            self.assertEqual(
                status.status_for(VersionComponent.FINAL).validity, "INVALIDATED"
            )


if __name__ == "__main__":
    unittest.main()
