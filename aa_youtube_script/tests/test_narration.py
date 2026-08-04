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
    "Day 3: Depart from Tsumago.\n"
)


def _prepare_narratable_trip(workspace: Path, provider=None) -> str:
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
    return trip_id


REQUIRED_SECTION_KEYS = {
    "hook",
    "journey_at_a_glance",
    "route",
    "reality_check",
    "who_it_suits",
    "who_should_avoid_it",
    "adventure_asia_verdict",
    "cta",
}


class NarrationTests(unittest.TestCase):
    def test_all_required_sections_are_present(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_narratable_trip(workspace)

            result = generate_narration(workspace, trip_id)

            section_keys = {section.key for section in result.sections}
            self.assertTrue(REQUIRED_SECTION_KEYS.issubset(section_keys))

    def test_indicative_claims_use_qualified_wording(self) -> None:
        from aa_content.research_providers import ResearchDocument

        single_doc = [
            ResearchDocument(
                url="https://example.test/a", title="A", publisher="example.test",
                extracted_text="text",
            )
        ]
        provider = FakeResearchSourceProvider(
            overrides={"current entry access requirements": single_doc}
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_narratable_trip(workspace, provider=provider)

            result = generate_narration(workspace, trip_id)

            reality_check = next(s for s in result.sections if s.key == "reality_check")
            self.assertIn("Some sources suggest", reality_check.body)

    def test_unknown_claims_never_appear_as_factual_statements(self) -> None:
        provider = FakeResearchSourceProvider(
            overrides={
                "current entry access requirements": [],
                "trail route rules and regulations": [],
            }
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_narratable_trip(workspace, provider=provider)

            result = generate_narration(workspace, trip_id)

            reality_check = next(s for s in result.sections if s.key == "reality_check")
            self.assertNotIn("Access for", reality_check.body)
            self.assertNotIn("Route rules for", reality_check.body)
            self.assertIn("Missing Information", reality_check.body)
            self.assertIn("Access", reality_check.body)  # named as missing, not stated

    def test_daily_intensity_present_when_activity_evidence_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_narratable_trip(workspace)

            result = generate_narration(workspace, trip_id)

            self.assertIsNotNone(result.overall_intensity)
            self.assertTrue(
                any(s.key == "intensity" for s in result.sections)
            )
            rated_days = [d for d in result.day_intensities if d.rating is not None]
            self.assertTrue(rated_days)

    def test_intensity_section_omitted_when_no_duration_evidence(self) -> None:
        itinerary = "Day 1: Arrive in Kyoto.\nDay 2: Explore the old town.\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            created = run_cli(
                workspace, "trip", "create", "--name", "Kyoto", stdin=itinerary
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
            self.assertTrue(proposed.options, "expected at least one proposed angle")
            approve_generated_angle(workspace, trip_id, proposed.options[0].angle_id)
            run_angle_research(workspace, trip_id, provider=provider)

            result = generate_narration(workspace, trip_id)

            self.assertIsNone(result.overall_intensity)
            self.assertFalse(any(s.key == "intensity" for s in result.sections))

    def test_route_section_groups_days_into_chapters_not_mechanical_list(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_narratable_trip(workspace)

            result = generate_narration(workspace, trip_id)

            route = next(s for s in result.sections if s.key == "route")
            self.assertIn("Arrival and Logistics (Day 1)", route.body)
            self.assertIn("On the Trail (Day 2)", route.body)
            self.assertIn("Departure and Logistics (Day 3)", route.body)

    def test_short_narration_is_warned_not_padded_with_filler(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_narratable_trip(workspace)

            result = generate_narration(workspace, trip_id)

            self.assertLess(result.estimated_minutes, 7.0)
            self.assertTrue(
                any("filler was not added" in warning for warning in result.warnings)
            )

    def test_editorial_notes_appear_only_in_verdict_not_reality_check(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_narratable_trip(workspace)

            result = generate_narration(
                workspace,
                trip_id,
                editorial_notes="Our guides know this trail well.",
            )

            verdict = next(s for s in result.sections if s.key == "adventure_asia_verdict")
            reality_check = next(s for s in result.sections if s.key == "reality_check")
            self.assertIn("Our guides know this trail well.", verdict.body)
            self.assertNotIn("Our guides know this trail well.", reality_check.body)

    def test_editorial_notes_with_product_promise_wording_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_narratable_trip(workspace)

            with self.assertRaises(UserFacingError):
                generate_narration(
                    workspace,
                    trip_id,
                    editorial_notes="We guarantee good weather every trip.",
                )

    def test_editorial_notes_with_supplier_data_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_narratable_trip(workspace)

            with self.assertRaises(UserFacingError):
                generate_narration(
                    workspace,
                    trip_id,
                    editorial_notes="Contact supplier: Yamada Tours, net rate JPY 8000.",
                )

    def test_no_price_information_in_any_section(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_narratable_trip(workspace)

            result = generate_narration(workspace, trip_id)

            for section in result.sections:
                self.assertNotRegex(section.body, r"[$€£¥]\s?\d")

    def test_narration_requires_approved_angle(self) -> None:
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
            run_cli(
                workspace,
                "trip",
                "process",
                "--trip-id",
                trip_id,
                extra_environment={"AA_CONTENT_FAKE_PROVIDERS": "1"},
            )

            with self.assertRaises(UserFacingError):
                generate_narration(workspace, trip_id)

    def test_reusing_completed_narration_does_not_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_narratable_trip(workspace)

            generate_narration(workspace, trip_id)
            second = generate_narration(workspace, trip_id)

            self.assertEqual(second.outcome, "reused")
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                narration_count = connection.execute(
                    "SELECT COUNT(*) FROM narrations"
                ).fetchone()[0]
                attempt_count = connection.execute(
                    """
                    SELECT COUNT(*) FROM stage_attempts AS attempt
                    JOIN workflow_stages AS stage
                      ON stage.workflow_stage_id = attempt.workflow_stage_id
                    WHERE stage.stage_name = 'narration'
                    """
                ).fetchone()[0]
            self.assertEqual(narration_count, 1)
            self.assertEqual(attempt_count, 1)

    def test_changed_editorial_notes_regenerate_a_new_narration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_narratable_trip(workspace)

            first = generate_narration(workspace, trip_id, editorial_notes="Notes A.")
            second = generate_narration(workspace, trip_id, editorial_notes="Notes B.")

            self.assertEqual(first.outcome, "generated")
            self.assertEqual(second.outcome, "generated")
            verdict_2 = next(
                s for s in second.sections if s.key == "adventure_asia_verdict"
            )
            self.assertIn("Notes B.", verdict_2.body)


if __name__ == "__main__":
    unittest.main()
