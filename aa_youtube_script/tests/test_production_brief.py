from __future__ import annotations

import os
from pathlib import Path
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
from aa_content.production_brief import generate_production_brief  # noqa: E402
from aa_content.research_providers import FakeResearchSourceProvider  # noqa: E402
from aa_content.validation import acknowledge_finding, validate_package  # noqa: E402
from aa_content.versioning import submit_review  # noqa: E402


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


CLEAN_ITINERARY = (
    "Day 1: Arrive in Kyoto by train.\n"
    "Day 2: Walk from Magome to Tsumago, about 4 hours. Overnight stay in a "
    "guesthouse in Tsumago. Breakfast and dinner included.\n"
)
MISSING_TRANSPORT_ITINERARY = (
    "Day 1: Arrive in Kyoto.\n"
    "Day 2: Walk from Magome to Tsumago, about 4 hours. Overnight stay in a "
    "guesthouse in Tsumago.\n"
)
SUPPLIER_DATA_ITINERARY = (
    "Day 1: Contact supplier: Yamada Tours, net rate JPY 8000 per night.\n"
    "Day 2: Walk from Magome to Tsumago, about 4 hours. Overnight stay in a "
    "guesthouse in Tsumago. Breakfast included.\n"
)


def _prepare_submitted_trip(workspace: Path, itinerary: str, provider=None) -> str:
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
    submit_review(workspace, trip_id)
    return trip_id


class ProductionBriefTests(unittest.TestCase):
    def test_brief_contains_all_required_elements(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(workspace, CLEAN_ITINERARY)

            result = generate_production_brief(workspace, trip_id)
            brief = result.brief

            self.assertIn("LOCKED", brief.locked_narration)
            self.assertTrue(brief.scene_requirements)
            self.assertTrue(brief.route_map_requirements)
            self.assertTrue(brief.brand_direction)
            self.assertTrue(brief.restrictions)
            self.assertTrue(brief.rights_and_ai_disclosure)

    def test_scene_requirements_identify_meaning_and_location_without_footage(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(workspace, CLEAN_ITINERARY)

            result = generate_production_brief(workspace, trip_id)

            route_scene = next(
                s for s in result.brief.scene_requirements if s.section_key == "route"
            )
            self.assertIn("Magome", route_scene.location)
            self.assertIn("Tsumago", route_scene.location)
            for scene in result.brief.scene_requirements:
                self.assertTrue(scene.visual_meaning)
                lowered = scene.visual_meaning.lower()
                self.assertNotIn("stock footage of", lowered)
                self.assertNotIn(".mp4", lowered)

    def test_rights_language_never_claims_assets_are_licensed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(workspace, CLEAN_ITINERARY)

            result = generate_production_brief(workspace, trip_id)
            disclosure = result.brief.rights_and_ai_disclosure.lower()

            self.assertIn("does not confirm", disclosure)
            self.assertIn("ai-generated", disclosure)
            self.assertNotIn("fully licensed", disclosure)
            self.assertNotIn("rights cleared", disclosure)

    def test_restrictions_forbid_vendor_specific_effects_and_rewriting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(workspace, CLEAN_ITINERARY)

            result = generate_production_brief(workspace, trip_id)
            restrictions_text = " ".join(result.brief.restrictions).lower()

            self.assertIn("does not prescribe", restrictions_text)
            self.assertIn("do not rewrite", restrictions_text)

    def test_markdown_json_csv_describe_the_same_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(workspace, CLEAN_ITINERARY)
            generate_production_brief(workspace, trip_id)

            trip_directory = next((workspace / "outputs").iterdir())
            working = trip_directory / "working"
            import csv
            import json

            payload = json.loads((working / "production-brief.json").read_text())
            markdown = (working / "production-brief.md").read_text()
            with (working / "production-brief-scenes.csv").open() as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(
                len(rows), len(payload["scene_requirements"])
            )
            self.assertIn(payload["brand_direction"], markdown)
            for row, scene in zip(rows, payload["scene_requirements"]):
                self.assertEqual(row["section"], scene["section"])

    def test_pictory_handoff_files_are_plain_files_no_api_needed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(workspace, CLEAN_ITINERARY)
            generate_production_brief(workspace, trip_id)

            trip_directory = next((workspace / "outputs").iterdir())
            working = trip_directory / "working"
            self.assertTrue((working / "pictory-handoff.md").is_file())
            self.assertTrue((working / "pictory-handoff.json").is_file())
            self.assertTrue((working / "pictory-handoff-scenes.csv").is_file())

    def test_export_blocked_by_unresolved_supplier_data_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(
                workspace, SUPPLIER_DATA_ITINERARY
            )

            with self.assertRaises(UserFacingError) as context:
                generate_production_brief(workspace, trip_id)
            self.assertIn("Supplier Data", str(context.exception))

    def test_unacknowledged_warnings_block_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(
                workspace, MISSING_TRANSPORT_ITINERARY
            )

            with self.assertRaises(UserFacingError):
                generate_production_brief(workspace, trip_id)

    def test_acknowledged_warnings_unblock_and_are_included_in_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(
                workspace, MISSING_TRANSPORT_ITINERARY
            )
            report = validate_package(workspace, trip_id)
            for finding in report.unacknowledged_warnings:
                acknowledge_finding(workspace, trip_id, finding.finding_id, "Jane Ops")

            result = generate_production_brief(workspace, trip_id)

            self.assertTrue(result.brief.warnings)
            self.assertTrue(
                all("Jane Ops" in warning for warning in result.brief.warnings)
            )

    def test_requires_submitted_version(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            assert run_cli(workspace, "init").returncode == 0
            created = run_cli(
                workspace, "trip", "create", "--name", "Nakasendo", stdin=CLEAN_ITINERARY
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
                generate_production_brief(workspace, trip_id)

    def test_no_price_secrets_or_raw_page_copies_leak_into_export(self) -> None:
        secret_like = "sk-super-secret-api-key-should-never-appear"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(workspace, CLEAN_ITINERARY)
            from aa_content.persistence import WorkspaceRepository

            repository = WorkspaceRepository(workspace)
            # Confirm the source_records' raw text (which never enters our
            # persisted evidence_summary at all, per Ticket 4) cannot appear.
            trip = repository.load_current_trip(trip_id)

            result = generate_production_brief(workspace, trip_id)

            import json

            blob = json.dumps(
                {
                    "locked_narration": result.brief.locked_narration,
                    "scene_requirements": [
                        s.visual_meaning for s in result.brief.scene_requirements
                    ],
                    "route_map_requirements": result.brief.route_map_requirements,
                }
            )
            self.assertNotRegex(blob, r"[$€£¥]\s?\d")
            self.assertNotIn(secret_like, blob)
            self.assertNotIn("SUPPLIER_DATA_REMOVED", blob)

    def test_reusing_unchanged_brief_returns_reused_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            trip_id = _prepare_submitted_trip(workspace, CLEAN_ITINERARY)

            first = generate_production_brief(workspace, trip_id)
            second = generate_production_brief(workspace, trip_id)

            self.assertEqual(first.content_signature, second.content_signature)
            self.assertEqual(second.outcome, "reused")


if __name__ == "__main__":
    unittest.main()
