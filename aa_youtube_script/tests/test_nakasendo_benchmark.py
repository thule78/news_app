"""Ticket 12: the Nakasendo-Kiso Valley end-to-end MVP benchmark.

Exercises the full Trip-to-Editorial-Package pipeline built across
Tickets 1-11 against one realistic itinerary, then a second Trip sharing
a Route Segment with it. Every external adapter is the Fake variant
(AA_CONTENT_FAKE_PROVIDERS=1 / explicit FakeResearchSourceProvider) per
the ticket's own rule that the default suite must stay offline; a live
OpenAI smoke test is defined at the bottom but skipped unless explicitly
opted into.
"""

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
from aa_content.models import (  # noqa: E402
    EvidenceStatus,
    ResearchCategory,
    VersionComponent,
)
from aa_content.narration import generate_narration  # noqa: E402
from aa_content.persistence import WorkspaceRepository  # noqa: E402
from aa_content.processing_workflow import process_itinerary  # noqa: E402
from aa_content.production_brief import generate_production_brief  # noqa: E402
from aa_content.research_providers import FakeResearchSourceProvider  # noqa: E402
from aa_content.route_segments import (  # noqa: E402
    confirm_route_segment,
    propose_shared_route_segments,
)
from aa_content.trip_workflow import create_trip  # noqa: E402
from aa_content.validation import acknowledge_finding, validate_package  # noqa: E402
from aa_content.versioning import approve_component, submit_review  # noqa: E402
from aa_content.workspace import initialize_workspace  # noqa: E402
from aa_content.youtube_packaging import generate_youtube_packaging  # noqa: E402

FAKE_PROVIDER_ENVIRONMENT = {"AA_CONTENT_FAKE_PROVIDERS": "1"}
PRICE_PATTERN = re.compile(
    r"[$€£¥]\s?\d|\b\d+(?:\.\d+)?\s?(?:usd|eur|gbp|jpy|vnd|dollars?)\b", re.IGNORECASE
)

NAKASENDO_ITINERARY = (
    "Day 1: Arrive in Nagoya, transfer by train to Nakatsugawa, then bus "
    "to Magome. Overnight stay in a ryokan in Magome. Dinner included.\n"
    "Day 2: Walk from Magome to Tsumago via the historic Nakasendo trail, "
    "about 3-5 hours, with moderate uphill sections. Overnight stay in a "
    "guesthouse in Tsumago. Breakfast and dinner included. Cash only in "
    "most local shops along the trail.\n"
    "Day 3: Walk from Tsumago to Nagiso, about 2 hours, mostly flat. "
    "Transfer by train back to Nagoya. Breakfast included.\n"
)

SECOND_TRIP_ITINERARY = (
    "Day 1: Arrive in Nagoya by shinkansen.\n"
    "Day 2: Walk from Magome to Tsumago, about 4 hours on the same "
    "historic trail. Overnight stay in a different guesthouse in "
    "Tsumago. Breakfast included.\n"
    "Day 3: Free day exploring Tsumago before departure.\n"
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


class NakasendoBenchmarkTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temporary_directory.name)
        self.addCleanup(self._temporary_directory.cleanup)
        initialize_workspace(self.workspace)
        self.provider = FakeResearchSourceProvider()
        # process_itinerary()/etc. are called directly (not via the CLI
        # subprocess), so the fake-provider switch must be set in-process.
        previous = os.environ.get("AA_CONTENT_FAKE_PROVIDERS")
        os.environ["AA_CONTENT_FAKE_PROVIDERS"] = "1"
        self.addCleanup(
            lambda: (
                os.environ.pop("AA_CONTENT_FAKE_PROVIDERS", None)
                if previous is None
                else os.environ.__setitem__("AA_CONTENT_FAKE_PROVIDERS", previous)
            )
        )

    # -- helpers ------------------------------------------------------

    def _create_trip(self, name: str, itinerary: str) -> str:
        result = create_trip(self.workspace, name, itinerary)
        return result.trip_id

    def _run_full_pipeline(self, trip_id: str) -> dict[str, object]:
        process_itinerary(self.workspace, trip_id)
        run_baseline_research(self.workspace, trip_id, provider=self.provider)
        proposed = propose_content_angles(self.workspace, trip_id)
        self.assertTrue(proposed.options)
        self.assertLessEqual(len(proposed.options), 3)
        approve_generated_angle(self.workspace, trip_id, proposed.options[0].angle_id)
        run_angle_research(self.workspace, trip_id, provider=self.provider)
        narration = generate_narration(self.workspace, trip_id)
        report = validate_package(self.workspace, trip_id)
        for finding in report.unacknowledged_warnings:
            acknowledge_finding(
                self.workspace, trip_id, finding.finding_id, "Jane Ops"
            )
        version = submit_review(self.workspace, trip_id)
        approve_component(
            self.workspace, trip_id, VersionComponent.NARRATION, "Jane Ops"
        )
        approve_component(self.workspace, trip_id, VersionComponent.FINAL, "Jane Ops")
        youtube = generate_youtube_packaging(self.workspace, trip_id)
        brief = generate_production_brief(self.workspace, trip_id)
        return {
            "angle": proposed.options[0],
            "narration": narration,
            "version": version,
            "youtube": youtube,
            "brief": brief,
        }

    # -- the benchmark --------------------------------------------------

    def test_end_to_end_reaches_an_immutable_approved_v1(self) -> None:
        trip_id = self._create_trip("Nakasendo Kiso Valley", NAKASENDO_ITINERARY)

        pipeline = self._run_full_pipeline(trip_id)

        self.assertEqual(pipeline["version"].version_number, 1)
        repository = WorkspaceRepository(self.workspace)
        status_component = repository.load_approval(
            trip_id, 1, VersionComponent.FINAL
        )
        self.assertIsNotNone(status_component)
        self.assertEqual(status_component.approver, "Jane Ops")

    def test_normalization_captures_route_days_intensity_and_constraints(
        self,
    ) -> None:
        trip_id = self._create_trip("Nakasendo Kiso Valley", NAKASENDO_ITINERARY)
        process_itinerary(self.workspace, trip_id)
        repository = WorkspaceRepository(self.workspace)
        trip = repository.load_current_trip(trip_id)
        normalized = repository.load_normalized_itinerary(trip.itinerary_revision_id)

        self.assertEqual(len(normalized["days"]), 3)
        day2 = next(d for d in normalized["days"] if d["day_number"] == 2)
        day3 = next(d for d in normalized["days"] if d["day_number"] == 3)
        self.assertTrue(day2["route_legs"])
        self.assertEqual(day2["route_legs"][0]["from"], "Magome")
        self.assertEqual(day2["route_legs"][0]["to"], "Tsumago")
        self.assertEqual(day2["route_legs"][0]["duration"]["kind"], "ESTIMATED")
        self.assertEqual(day3["route_legs"][0]["duration"]["kind"], "EXACT")
        self.assertTrue(day2["accommodation"])
        self.assertTrue(day2["practical_constraints"])
        self.assertTrue(
            any("cash" in c["description"].lower() for c in day2["practical_constraints"])
        )
        day1 = next(d for d in normalized["days"] if d["day_number"] == 1)
        self.assertTrue(day1["transport"])

        run_baseline_research(self.workspace, trip_id, provider=self.provider)
        from aa_content.narration import _compute_intensities

        day_intensities, overall = _compute_intensities(normalized)
        self.assertIsNotNone(overall)
        rated = {d.day_number: d.rating for d in day_intensities if d.rating is not None}
        self.assertIn(2, rated)
        self.assertIn(3, rated)

    def test_baseline_research_has_traceable_crowd_and_solo_evidence(self) -> None:
        trip_id = self._create_trip("Nakasendo Kiso Valley", NAKASENDO_ITINERARY)
        process_itinerary(self.workspace, trip_id)

        result = run_baseline_research(self.workspace, trip_id, provider=self.provider)

        by_category = {c.category: c for c in result.claims}
        for category in (ResearchCategory.CROWDS, ResearchCategory.SOLO_TRAVELLER):
            claim = by_category[category]
            self.assertNotEqual(claim.evidence_status, EvidenceStatus.UNKNOWN)
            self.assertTrue(claim.sources)
            for source in claim.sources:
                self.assertTrue(source.url)
                self.assertTrue(source.publisher)
                self.assertTrue(source.content_hash)
                self.assertTrue(source.evidence_summary)

    def test_angle_research_supports_the_selected_promise(self) -> None:
        trip_id = self._create_trip("Nakasendo Kiso Valley", NAKASENDO_ITINERARY)
        process_itinerary(self.workspace, trip_id)
        run_baseline_research(self.workspace, trip_id, provider=self.provider)
        proposed = propose_content_angles(self.workspace, trip_id)
        approve_generated_angle(self.workspace, trip_id, proposed.options[0].angle_id)

        result = run_angle_research(self.workspace, trip_id, provider=self.provider)

        self.assertIsNotNone(result.claim)
        self.assertIn(proposed.options[0].viewer_question, result.claim.statement)

    def test_narration_is_traceable_complete_and_free_of_visual_dependency(
        self,
    ) -> None:
        trip_id = self._create_trip("Nakasendo Kiso Valley", NAKASENDO_ITINERARY)
        process_itinerary(self.workspace, trip_id)
        run_baseline_research(self.workspace, trip_id, provider=self.provider)
        proposed = propose_content_angles(self.workspace, trip_id)
        approve_generated_angle(self.workspace, trip_id, proposed.options[0].angle_id)
        run_angle_research(self.workspace, trip_id, provider=self.provider)

        narration = generate_narration(self.workspace, trip_id)

        keys = {s.key for s in narration.sections}
        for required in (
            "reality_check",
            "who_it_suits",
            "who_should_avoid_it",
            "adventure_asia_verdict",
            "cta",
        ):
            self.assertIn(required, keys)
        full_text = narration.full_text.lower()
        for phrase in ("as you can see", "pictured here", "shown above"):
            self.assertNotIn(phrase, full_text)
        self.assertNotRegex(full_text, r"[$€£¥]\s?\d")

        # Missing Information stays explicit rather than silently inferred.
        report = validate_package(self.workspace, trip_id)
        missing_codes = {
            f.finding_id for f in report.findings if f.code == "MISSING_INFORMATION"
        }
        repository = WorkspaceRepository(self.workspace)
        trip = repository.load_current_trip(trip_id)
        normalized = repository.load_normalized_itinerary(trip.itinerary_revision_id)
        if normalized.get("missing_information"):
            self.assertTrue(missing_codes)

    def test_quality_warnings_acknowledgments_and_approvals_are_complete(
        self,
    ) -> None:
        trip_id = self._create_trip("Nakasendo Kiso Valley", NAKASENDO_ITINERARY)
        pipeline = self._run_full_pipeline(trip_id)

        report = validate_package(self.workspace, trip_id)
        self.assertEqual(report.unacknowledged_warnings, ())
        self.assertGreaterEqual(report.quality_score, 0)
        self.assertLessEqual(report.quality_score, 100)

        repository = WorkspaceRepository(self.workspace)
        narration_approval = repository.load_approval(
            trip_id, pipeline["version"].version_number, VersionComponent.NARRATION
        )
        final_approval = repository.load_approval(
            trip_id, pipeline["version"].version_number, VersionComponent.FINAL
        )
        self.assertIsNotNone(narration_approval)
        self.assertIsNotNone(final_approval)
        self.assertTrue(narration_approval.approved_at)
        self.assertTrue(final_approval.approved_at)

    def test_youtube_shorts_scene_plan_and_pictory_handoff_are_consistent(
        self,
    ) -> None:
        trip_id = self._create_trip("Nakasendo Kiso Valley", NAKASENDO_ITINERARY)
        pipeline = self._run_full_pipeline(trip_id)

        youtube = pipeline["youtube"]
        brief = pipeline["brief"]
        self.assertEqual(len(youtube.packaging.shorts), 2)
        self.assertTrue(youtube.packaging.chapters)
        self.assertTrue(brief.brief.scene_requirements)
        self.assertTrue(brief.brief.route_map_requirements)

        trip_directory = next((self.workspace / "outputs").iterdir())
        working = trip_directory / "working"
        for filename in (
            "youtube-packaging.json",
            "production-brief.json",
            "pictory-handoff.json",
            "pictory-handoff-scenes.csv",
        ):
            self.assertTrue((working / filename).is_file(), filename)

    def test_no_supplier_data_or_price_information_anywhere_exported(self) -> None:
        trip_id = self._create_trip("Nakasendo Kiso Valley", NAKASENDO_ITINERARY)
        self._run_full_pipeline(trip_id)

        trip_directory = next((self.workspace / "outputs").iterdir())
        for path in trip_directory.rglob("*"):
            if not path.is_file() or path.name == "original-itinerary.txt":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertNotRegex(
                text, r"[$€£¥]\s?\d", f"price-like token in {path}"
            )
            self.assertNotIn("SUPPLIER_DATA_REMOVED", text)

    def test_resumes_after_simulated_interruption_at_process_research_and_narrate(
        self,
    ) -> None:
        trip_id = self._create_trip("Nakasendo Kiso Valley", NAKASENDO_ITINERARY)
        process_itinerary(self.workspace, trip_id)
        run_baseline_research(self.workspace, trip_id, provider=self.provider)
        proposed = propose_content_angles(self.workspace, trip_id)
        approve_generated_angle(self.workspace, trip_id, proposed.options[0].angle_id)
        run_angle_research(self.workspace, trip_id, provider=self.provider)
        generate_narration(self.workspace, trip_id)

        with sqlite3.connect(self.workspace / "aa_content.db") as connection:
            for stage_name in ("itinerary_process", "baseline_research", "narration"):
                connection.execute(
                    "UPDATE workflow_stages SET status = 'FAILED' "
                    "WHERE stage_name = ? AND trip_id = ?",
                    (stage_name, trip_id),
                )

        # Each resumes cleanly without duplicating domain records.
        process_itinerary(self.workspace, trip_id)
        run_baseline_research(self.workspace, trip_id, provider=self.provider)
        generate_narration(self.workspace, trip_id)

        with sqlite3.connect(self.workspace / "aa_content.db") as connection:
            normalized_count = connection.execute(
                "SELECT COUNT(*) FROM normalized_itineraries"
            ).fetchone()[0]
            claim_count = connection.execute(
                "SELECT COUNT(*) FROM research_claims WHERE angle_id = ''"
            ).fetchone()[0]
            narration_count = connection.execute(
                "SELECT COUNT(*) FROM narrations"
            ).fetchone()[0]
        self.assertEqual(normalized_count, 1)
        self.assertEqual(claim_count, 8)
        self.assertEqual(narration_count, 1)

    def test_forced_regeneration_replaces_only_the_requested_stage(self) -> None:
        trip_id = self._create_trip("Nakasendo Kiso Valley", NAKASENDO_ITINERARY)
        process_itinerary(self.workspace, trip_id)
        run_baseline_research(self.workspace, trip_id, provider=self.provider)
        proposed = propose_content_angles(self.workspace, trip_id)
        approve_generated_angle(self.workspace, trip_id, proposed.options[0].angle_id)
        run_angle_research(self.workspace, trip_id, provider=self.provider)
        generate_narration(self.workspace, trip_id)

        with sqlite3.connect(self.workspace / "aa_content.db") as connection:
            before_research_claims = connection.execute(
                "SELECT COUNT(*) FROM research_claims"
            ).fetchone()[0]
            before_narrations = connection.execute(
                "SELECT COUNT(*) FROM narrations"
            ).fetchone()[0]

        process_itinerary(self.workspace, trip_id, force=True)

        with sqlite3.connect(self.workspace / "aa_content.db") as connection:
            after_research_claims = connection.execute(
                "SELECT COUNT(*) FROM research_claims"
            ).fetchone()[0]
            after_narrations = connection.execute(
                "SELECT COUNT(*) FROM narrations"
            ).fetchone()[0]
            normalized_count = connection.execute(
                "SELECT COUNT(*) FROM normalized_itineraries"
            ).fetchone()[0]

        # Forcing itinerary processing again touches only that stage's own
        # table; Baseline Research Claims and the narration draft survive.
        self.assertEqual(normalized_count, 1)
        self.assertEqual(before_research_claims, after_research_claims)
        self.assertEqual(before_narrations, after_narrations)

        pipeline_before_versions = None
        with sqlite3.connect(self.workspace / "aa_content.db") as connection:
            pipeline_before_versions = connection.execute(
                "SELECT COUNT(*) FROM editorial_package_versions"
            ).fetchone()[0]
        self.assertEqual(pipeline_before_versions, 0)

    def test_second_trip_reuses_confirmed_route_segment_without_leaking_claims(
        self,
    ) -> None:
        trip_a = self._create_trip("Nakasendo Kiso Valley", NAKASENDO_ITINERARY)
        process_itinerary(self.workspace, trip_a)

        trip_b = self._create_trip("Nakasendo Return Trip", SECOND_TRIP_ITINERARY)
        process_itinerary(self.workspace, trip_b)

        # Confirm the shared segment before either Trip researches it, so
        # the first Trip to research it becomes the canonical registrant.
        segments = propose_shared_route_segments(self.workspace, trip_a, trip_b)
        self.assertEqual(len(segments), 1)
        confirm_route_segment(self.workspace, segments[0].route_segment_id)

        result_a = run_baseline_research(self.workspace, trip_a, provider=self.provider)
        result_b = run_baseline_research(self.workspace, trip_b, provider=self.provider)

        by_category_a = {c.category: c for c in result_a.claims}
        by_category_b = {c.category: c for c in result_b.claims}

        for category in (
            ResearchCategory.ROUTE_RULES,
            ResearchCategory.INDEPENDENT_TRANSPORT,
        ):
            sources_a = {s.source_record_id for s in by_category_a[category].sources}
            sources_b = {s.source_record_id for s in by_category_b[category].sources}
            self.assertEqual(sources_a, sources_b)

        # Trip-specific categories are never shared between the two Trips.
        with sqlite3.connect(self.workspace / "aa_content.db") as connection:
            access_trip_ids = {
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT trip_id FROM source_records WHERE category = "
                    "'ACCESS'"
                ).fetchall()
            }
        self.assertEqual(access_trip_ids, {trip_a, trip_b})
        with sqlite3.connect(self.workspace / "aa_content.db") as connection:
            shared_route_rules_sources = connection.execute(
                "SELECT COUNT(*) FROM source_records WHERE category = 'ROUTE_RULES'"
            ).fetchone()[0]
        # Fetched once (2 sources), referenced by both Trips, never doubled.
        self.assertEqual(shared_route_rules_sources, 2)

    def test_default_suite_never_uses_real_external_adapters(self) -> None:
        from aa_content.content_angle import (
            FAKE_PROVIDER_ENVIRONMENT_VARIABLE as angle_env,
        )
        from aa_content.baseline_research import (
            FAKE_PROVIDER_ENVIRONMENT_VARIABLE as research_env,
        )
        from aa_content.processing_workflow import (
            FAKE_PROVIDER_ENVIRONMENT_VARIABLE as itinerary_env,
        )

        self.assertEqual(angle_env, "AA_CONTENT_FAKE_PROVIDERS")
        self.assertEqual(research_env, "AA_CONTENT_FAKE_PROVIDERS")
        self.assertEqual(itinerary_env, "AA_CONTENT_FAKE_PROVIDERS")


@unittest.skipUnless(
    os.environ.get("AA_CONTENT_LIVE_OPENAI_SMOKE") == "1"
    and os.environ.get("OPENAI_API_KEY"),
    "Live OpenAI smoke test is opt-in: set AA_CONTENT_LIVE_OPENAI_SMOKE=1 "
    "and OPENAI_API_KEY to run it.",
)
class LiveOpenAiSmokeTest(unittest.TestCase):
    """Not run by the default suite. Opt in explicitly to exercise the real
    OpenAIItineraryProvider against the live API."""

    def test_real_provider_normalizes_a_trivial_itinerary(self) -> None:
        from aa_content.providers import OpenAIItineraryProvider

        provider = OpenAIItineraryProvider(os.environ["OPENAI_API_KEY"])
        result = provider.normalize("Day 1: Walk from Magome to Tsumago.\n")
        self.assertIn("days", result)


if __name__ == "__main__":
    unittest.main()
