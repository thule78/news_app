from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_cli(
    workspace: Path,
    *arguments: str,
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(PROJECT_ROOT / "aa-content"),
            "--workspace",
            str(workspace),
            *arguments,
        ],
        cwd=PROJECT_ROOT,
        env=os.environ.copy(),
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


def create_trip(workspace: Path, itinerary: str) -> tuple[str, Path]:
    result = run_cli(
        workspace,
        "trip",
        "create",
        "--name",
        "Nakasendo & Kiso Valley",
        stdin=itinerary,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    trip_id = next(
        line.removeprefix("Trip ID: ")
        for line in result.stdout.splitlines()
        if line.startswith("Trip ID: ")
    )
    return trip_id, next((workspace / "outputs").iterdir())


class ItineraryProcessingCliTests(unittest.TestCase):
    def test_operator_sanitizes_then_normalizes_an_itinerary_revision(self) -> None:
        sensitive_line = (
            "Supplier contact: Kiso Partner, guide@example.com, +81 90 1234 5678."
        )
        itinerary = (
            "Day 1: Included train from Kyoto to Magome.\n"
            f"{sensitive_line}\n"
            "Day 2: Walk from Magome to Tsumago for 3-5 hours on a steep trail.\n"
            "Stay overnight at Kiso Ryokan. Dinner included.\n"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_id, trip_directory = create_trip(workspace, itinerary)

            result = run_cli(
                workspace,
                "trip",
                "process",
                "--trip-id",
                trip_id,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Itinerary processed: Nakasendo & Kiso Valley", result.stdout)
            self.assertIn("Supplier Data: REVIEW_REQUIRED (1 removal)", result.stdout)
            self.assertIn("Export: READY", result.stdout)

            revision_directory = trip_directory / "source" / "r1"
            original = (revision_directory / "original-itinerary.txt").read_text()
            sanitized = (revision_directory / "sanitized-itinerary.txt").read_text()
            report = json.loads(
                (revision_directory / "sanitization-report.json").read_text()
            )
            normalized = json.loads(
                (revision_directory / "normalized-itinerary.json").read_text()
            )

            self.assertIn(sensitive_line, original)
            self.assertNotIn("guide@example.com", sanitized)
            self.assertNotIn("+81 90 1234 5678", sanitized)
            self.assertIn("[SUPPLIER DATA REMOVED: CONTACT_DETAILS]", sanitized)
            self.assertEqual(report["status"], "REVIEW_REQUIRED")
            self.assertEqual(
                report["findings"],
                [
                    {
                        "category": "CONTACT_DETAILS",
                        "source_locator": "line 2",
                        "review_status": "PENDING",
                    }
                ],
            )

            self.assertEqual(
                normalized["days"][0]["route_legs"][0]["from"],
                "Kyoto",
            )
            self.assertEqual(
                normalized["days"][0]["route_legs"][0]["to"],
                "Magome",
            )
            walking_activity = normalized["days"][1]["activities"][0]
            self.assertEqual(walking_activity["kind"], "WALK")
            self.assertEqual(
                walking_activity["estimated_duration"],
                {"minimum_minutes": 180, "maximum_minutes": 300},
            )
            self.assertEqual(
                normalized["days"][1]["overnight_stops"][0]["name"],
                "Kiso Ryokan",
            )
            self.assertEqual(
                normalized["days"][1]["accommodation"][0]["kind"],
                "RYOKAN",
            )
            self.assertEqual(
                normalized["days"][1]["meals"][0]["name"],
                "DINNER",
            )
            self.assertEqual(
                normalized["days"][1]["meals"][0]["arrangement"],
                "INCLUDED",
            )
            self.assertTrue(normalized["days"][1]["practical_constraints"])
            self.assertEqual(
                normalized["days"][0]["transport"][0]["arrangement"],
                "TRIP_TRANSPORT",
            )

            with sqlite3.connect(workspace / "aa_content.db") as connection:
                warning = connection.execute(
                    """
                    SELECT code, severity, review_status, source_locator
                    FROM itinerary_warnings
                    WHERE code = 'SUPPLIER_DATA_REMOVED'
                    """
                ).fetchone()
                export_block_count = connection.execute(
                    "SELECT COUNT(*) FROM export_blocks"
                ).fetchone()[0]
                revision_id = connection.execute(
                    """
                    SELECT current_itinerary_revision_id
                    FROM trips
                    WHERE trip_id = ?
                    """,
                    (trip_id,),
                ).fetchone()[0]

                self.assertEqual(
                    warning,
                    ("SUPPLIER_DATA_REMOVED", "WARNING", "PENDING", "line 2"),
                )
                self.assertEqual(export_block_count, 0)
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """
                        INSERT INTO export_blocks (
                            export_block_id,
                            itinerary_revision_id,
                            code,
                            message,
                            status
                        ) VALUES (
                            'exb_invalid',
                            ?,
                            'LOW_QUALITY',
                            'Advisory issue must not hard-block export.',
                            'ACTIVE'
                        )
                        """,
                        (revision_id,),
                    )

            for persisted_path in workspace.rglob("*"):
                if not persisted_path.is_file():
                    continue
                if persisted_path in {
                    workspace / "aa_content.db",
                    revision_directory / "original-itinerary.txt",
                }:
                    continue
                self.assertNotIn(
                    sensitive_line.encode(),
                    persisted_path.read_bytes(),
                    str(persisted_path),
                )

    def test_sanitization_covers_private_identities_and_preserves_safe_line_facts(
        self,
    ) -> None:
        itinerary = (
            "Day 1: Walk from Magome to Tsumago for 3 hours; "
            "Supplier Kiso Travel manages luggage.\n"
            "Guide Hiro Tanaka handles the group.\n"
            "Operational note: call the lodge if the trail closes.\n"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_id, trip_directory = create_trip(workspace, itinerary)

            result = run_cli(
                workspace, "trip", "process", "--trip-id", trip_id
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("REVIEW_REQUIRED (3 removals)", result.stdout)
            revision_directory = trip_directory / "source" / "r1"
            sanitized = (
                revision_directory / "sanitized-itinerary.txt"
            ).read_text()
            normalized = json.loads(
                (revision_directory / "normalized-itinerary.json").read_text()
            )
            self.assertIn("Walk from Magome to Tsumago for 3 hours", sanitized)
            self.assertNotIn("Kiso Travel", sanitized)
            self.assertNotIn("Hiro Tanaka", sanitized)
            self.assertNotIn("call the lodge", sanitized)
            self.assertEqual(
                normalized["days"][0]["route_legs"][0]["from"],
                "Magome",
            )
            self.assertEqual(
                normalized["days"][0]["route_legs"][0]["to"],
                "Tsumago",
            )
            self.assertEqual(
                normalized["days"][0]["activities"][0]["estimated_duration"],
                {"minimum_minutes": 180, "maximum_minutes": 180},
            )

    def test_multiline_supplier_sections_block_without_removing_public_guide_activity(
        self,
    ) -> None:
        itinerary = (
            "Day 1: Your guide will walk from Magome to Tsumago.\n"
            "Supplier:\n"
            "Kiso Trail Partners Ltd\n"
            "Hiro Tanaka\n"
            "Visit the old post town.\n"
            "Operational note:\n"
            "Call Yamada if the trail closes.\n"
            "Booking ref ABC123.\n"
            "The trip is operated by Kiso Travel.\n"
            "Day 2: Continue from Tsumago to Nagiso.\n"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_id, trip_directory = create_trip(workspace, itinerary)

            result = run_cli(
                workspace, "trip", "process", "--trip-id", trip_id
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("REVIEW_REQUIRED (7 removals)", result.stdout)
            self.assertIn("Export: READY", result.stdout)
            revision_directory = trip_directory / "source" / "r1"
            sanitized = (
                revision_directory / "sanitized-itinerary.txt"
            ).read_text()
            self.assertIn(
                "Your guide will walk from Magome to Tsumago",
                sanitized,
            )
            self.assertNotIn("Kiso Trail Partners", sanitized)
            self.assertNotIn("Hiro Tanaka", sanitized)
            self.assertNotIn("Call Yamada", sanitized)
            self.assertNotIn("ABC123", sanitized)
            self.assertNotIn("Kiso Travel", sanitized)
            normalized = json.loads(
                (revision_directory / "normalized-itinerary.json").read_text()
            )
            self.assertEqual(
                {
                    activity["kind"]
                    for activity in normalized["days"][0]["activities"]
                },
                {"WALK", "VISIT"},
            )

    def test_normalized_claims_trace_to_itinerary_evidence_and_unknowns_stay_missing(
        self,
    ) -> None:
        itinerary = "Day 1: Walk from Magome to Tsumago.\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_id, trip_directory = create_trip(workspace, itinerary)

            result = run_cli(
                workspace,
                "trip",
                "process",
                "--trip-id",
                trip_id,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            normalized = json.loads(
                (
                    trip_directory
                    / "source"
                    / "r1"
                    / "normalized-itinerary.json"
                ).read_text()
            )
            missing_fields = {
                item["field"] for item in normalized["missing_information"]
            }
            self.assertIn("accommodation", missing_fields)
            self.assertIn("meals", missing_fields)
            self.assertIn("transport", missing_fields)
            self.assertNotIn("likely", json.dumps(normalized).casefold())
            normalized_markdown = (
                trip_directory / "source" / "r1" / "normalized-itinerary.md"
            ).read_text()
            self.assertIn(
                "Day 1: `accommodation` — `MISSING_INFORMATION`",
                normalized_markdown,
            )

            artifact_claim_ids = {
                claim["claim_id"] for claim in normalized["claims"]
            }
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                persisted_links = connection.execute(
                    """
                    SELECT claim.claim_id,
                           claim.evidence_status,
                           evidence.evidence_kind,
                           evidence.source_locator
                    FROM claims AS claim
                    JOIN claim_evidence AS link
                      ON link.claim_id = claim.claim_id
                    JOIN evidence
                      ON evidence.evidence_id = link.evidence_id
                    WHERE claim.itinerary_revision_id = (
                        SELECT current_itinerary_revision_id
                        FROM trips
                        WHERE trip_id = ?
                    )
                    """,
                    (trip_id,),
                ).fetchall()
                missing_warning_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM itinerary_warnings
                    WHERE code = 'MISSING_INFORMATION'
                    """
                ).fetchone()[0]

            self.assertEqual(
                {row[0] for row in persisted_links},
                artifact_claim_ids,
            )
            self.assertTrue(persisted_links)
            self.assertTrue(
                all(
                    status == "VERIFIED"
                    and kind == "ITINERARY"
                    and locator.startswith("line ")
                    for _, status, kind, locator in persisted_links
                )
            )
            self.assertEqual(
                missing_warning_count,
                len(normalized["missing_information"]),
            )

    def test_duration_estimates_merge_only_for_matching_scope_and_conditions(
        self,
    ) -> None:
        itinerary = (
            "Day 1: Walk from Magome to Tsumago for 3 hours.\n"
            "Walk from Magome to Tsumago for 5 hours.\n"
            "Day 2: Walk from Yabuhara to Narai for 2 hours in dry weather.\n"
            "Walk from Yabuhara to Narai for 4 hours in snow.\n"
            "Day 3: Walk from Magome to Tsumago for 6 hours.\n"
            "Day 4: Walk from Ochiai to Magome via upper trail for 3 hours.\n"
            "Walk from Ochiai to Magome via lower trail for 5 hours.\n"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_id, trip_directory = create_trip(workspace, itinerary)

            result = run_cli(
                workspace,
                "trip",
                "process",
                "--trip-id",
                trip_id,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            normalized = json.loads(
                (
                    trip_directory
                    / "source"
                    / "r1"
                    / "normalized-itinerary.json"
                ).read_text()
            )
            self.assertEqual(
                normalized["days"][0]["activities"][0]["estimated_duration"],
                {"minimum_minutes": 180, "maximum_minutes": 300},
            )
            self.assertEqual(len(normalized["days"][0]["activities"]), 1)
            self.assertEqual(
                len(normalized["days"][0]["activities"][0]["claim_ids"]),
                2,
            )

            self.assertEqual(len(normalized["days"][1]["activities"]), 2)
            self.assertEqual(len(normalized["fact_conflicts"]), 3)
            conflict = next(
                item
                for item in normalized["fact_conflicts"]
                if item["subject"] == "WALK: Yabuhara to Narai"
            )
            self.assertEqual(
                set(conflict["conditions"]),
                {"DRY", "SNOW"},
            )
            scope_conflict = next(
                item
                for item in normalized["fact_conflicts"]
                if item["subject"] == "WALK: Magome to Tsumago"
            )
            self.assertEqual(
                set(scope_conflict["scopes"]),
                {"Day 1", "Day 3"},
            )
            segment_conflict = next(
                item
                for item in normalized["fact_conflicts"]
                if item["subject"] == "WALK: Ochiai to Magome"
            )
            self.assertEqual(
                set(segment_conflict["route_segments"]),
                {"upper trail", "lower trail"},
            )
            self.assertEqual(len(normalized["days"][3]["activities"]), 2)
            self.assertIn("Fact Conflicts: 3", result.stdout)

    def test_transport_inclusion_and_duration_bind_to_transport_clause(self) -> None:
        itinerary = (
            "Day 1: Take the public bus from Kyoto to Magome for 2 hours "
            "and dinner included.\n"
            "Day 2: Included train from Magome to Nagoya for 90 minutes.\n"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_id, trip_directory = create_trip(workspace, itinerary)

            result = run_cli(
                workspace, "trip", "process", "--trip-id", trip_id
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            normalized = json.loads(
                (
                    trip_directory
                    / "source"
                    / "r1"
                    / "normalized-itinerary.json"
                ).read_text()
            )
            first_transport = normalized["days"][0]["transport"][0]
            self.assertEqual(first_transport["arrangement"], "UNKNOWN")
            self.assertEqual(
                first_transport["estimated_duration"],
                {"minimum_minutes": 120, "maximum_minutes": 120},
            )
            self.assertEqual(
                normalized["days"][0]["meals"][0]["arrangement"],
                "INCLUDED",
            )
            second_transport = normalized["days"][1]["transport"][0]
            self.assertEqual(
                second_transport["arrangement"],
                "TRIP_TRANSPORT",
            )
            self.assertEqual(
                second_transport["estimated_duration"],
                {"minimum_minutes": 90, "maximum_minutes": 90},
            )

    def test_nakasendo_route_variants_normalize_without_inventing_missing_fields(
        self,
    ) -> None:
        itinerary = (
            "Day 1: Kyoto to Magome by train. Overnight in Magome.\n"
            "Day 2: Walk Magome to Tsumago (8 km, 3–4 hours). "
            "Overnight in Tsumago.\n"
            "Day 3: Tsumago → Kiso-Fukushima by bus.\n"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_id, trip_directory = create_trip(workspace, itinerary)

            result = run_cli(
                workspace, "trip", "process", "--trip-id", trip_id
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            normalized = json.loads(
                (
                    trip_directory
                    / "source"
                    / "r1"
                    / "normalized-itinerary.json"
                ).read_text()
            )
            routes = [
                (day["route_legs"][0]["from"], day["route_legs"][0]["to"])
                for day in normalized["days"]
            ]
            self.assertEqual(
                routes,
                [
                    ("Kyoto", "Magome"),
                    ("Magome", "Tsumago"),
                    ("Tsumago", "Kiso-Fukushima"),
                ],
            )
            self.assertEqual(
                normalized["days"][1]["activities"][0]["estimated_duration"],
                {"minimum_minutes": 180, "maximum_minutes": 240},
            )
            day_two_missing = {
                item["field"]
                for item in normalized["missing_information"]
                if item["scope"] == "Day 2"
            }
            self.assertNotIn("route_legs", day_two_missing)
            self.assertNotIn("overnight_stops", day_two_missing)
            self.assertNotIn("activities", day_two_missing)
            self.assertEqual(
                normalized["days"][0]["transport"][0]["arrangement"],
                "UNKNOWN",
            )
            day_one_missing = {
                item["field"]
                for item in normalized["missing_information"]
                if item["scope"] == "Day 1"
            }
            self.assertIn("transport.arrangement", day_one_missing)

    def test_repeated_processing_reuses_results_and_force_replaces_without_duplicates(
        self,
    ) -> None:
        itinerary = (
            "Day 1: Walk from Magome to Tsumago for 3 hours.\n"
            "Supplier contact: guide@example.com.\n"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_id, trip_directory = create_trip(workspace, itinerary)
            first = run_cli(
                workspace, "trip", "process", "--trip-id", trip_id
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            normalized_path = (
                trip_directory / "source" / "r1" / "normalized-itinerary.json"
            )
            normalized_path.write_text("damaged", encoding="utf-8")

            reused = run_cli(
                workspace, "trip", "process", "--trip-id", trip_id
            )
            self.assertEqual(reused.returncode, 0, reused.stderr)
            self.assertIn("Itinerary reused", reused.stdout)
            self.assertEqual(normalized_path.read_text(), "damaged")

            forced = run_cli(
                workspace,
                "trip",
                "process",
                "--trip-id",
                trip_id,
                "--force",
            )

            self.assertEqual(forced.returncode, 0, forced.stderr)
            self.assertIn("Itinerary regenerated", forced.stdout)
            json.loads(normalized_path.read_text())

            with sqlite3.connect(workspace / "aa_content.db") as connection:
                counts = {
                    table: connection.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0]
                    for table in (
                        "sanitized_itineraries",
                        "supplier_data_findings",
                        "normalized_itineraries",
                    )
                }
                stage_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM workflow_stages
                    WHERE stage_name = 'itinerary_process'
                    """
                ).fetchone()[0]
                attempt_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM stage_attempts AS attempt
                    JOIN workflow_stages AS stage
                      ON stage.workflow_stage_id = attempt.workflow_stage_id
                    WHERE stage.stage_name = 'itinerary_process'
                    """
                ).fetchone()[0]

            self.assertEqual(
                counts,
                {
                    "sanitized_itineraries": 1,
                    "supplier_data_findings": 1,
                    "normalized_itineraries": 1,
                },
            )
            self.assertEqual((stage_count, attempt_count), (1, 2))

    def test_force_replaces_only_records_owned_by_itinerary_processing(self) -> None:
        itinerary = "Day 1: Walk from Magome to Tsumago.\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_id, _ = create_trip(workspace, itinerary)
            first = run_cli(
                workspace, "trip", "process", "--trip-id", trip_id
            )
            self.assertEqual(first.returncode, 0, first.stderr)

            with sqlite3.connect(workspace / "aa_content.db") as connection:
                revision_id = connection.execute(
                    """
                    SELECT current_itinerary_revision_id
                    FROM trips
                    WHERE trip_id = ?
                    """,
                    (trip_id,),
                ).fetchone()[0]
                connection.execute(
                    """
                    INSERT INTO claims (
                        claim_id,
                        trip_id,
                        itinerary_revision_id,
                        claim_kind,
                        statement,
                        value_json,
                        evidence_status,
                        created_at
                    ) VALUES (
                        'clm_later_research',
                        ?,
                        ?,
                        'RESEARCH',
                        'Later research Claim.',
                        '{}',
                        'VERIFIED',
                        '2026-07-31T00:00:00+00:00'
                    )
                    """,
                    (trip_id, revision_id),
                )
                connection.execute(
                    """
                    INSERT INTO evidence (
                        evidence_id,
                        itinerary_revision_id,
                        evidence_kind,
                        source_locator,
                        summary,
                        created_at
                    ) VALUES (
                        'evd_later_research',
                        ?,
                        'EXTERNAL_SOURCE',
                        'https://example.com',
                        'Later research Evidence.',
                        '2026-07-31T00:00:00+00:00'
                    )
                    """,
                    (revision_id,),
                )
                connection.execute(
                    """
                    INSERT INTO claim_evidence (claim_id, evidence_id)
                    VALUES ('clm_later_research', 'evd_later_research')
                    """
                )
                connection.execute(
                    """
                    INSERT INTO itinerary_warnings (
                        warning_id,
                        itinerary_revision_id,
                        code,
                        severity,
                        message,
                        source_locator,
                        review_status
                    ) VALUES (
                        'wrn_later_review',
                        ?,
                        'LATER_REVIEW',
                        'WARNING',
                        'Later-stage warning.',
                        NULL,
                        'ACKNOWLEDGED'
                    )
                    """,
                    (revision_id,),
                )

            forced = run_cli(
                workspace,
                "trip",
                "process",
                "--trip-id",
                trip_id,
                "--force",
            )

            self.assertEqual(forced.returncode, 0, forced.stderr)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                later_claim = connection.execute(
                    "SELECT statement FROM claims WHERE claim_id = 'clm_later_research'"
                ).fetchone()
                later_evidence = connection.execute(
                    """
                    SELECT summary
                    FROM evidence
                    WHERE evidence_id = 'evd_later_research'
                    """
                ).fetchone()
                later_warning = connection.execute(
                    """
                    SELECT review_status
                    FROM itinerary_warnings
                    WHERE warning_id = 'wrn_later_review'
                    """
                ).fetchone()

            self.assertEqual(later_claim, ("Later research Claim.",))
            self.assertEqual(later_evidence, ("Later research Evidence.",))
            self.assertEqual(later_warning, ("ACKNOWLEDGED",))

    def test_failed_processing_resumes_without_duplicate_domain_records(self) -> None:
        itinerary = "Day 1: Walk from Magome to Tsumago.\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            trip_id, trip_directory = create_trip(workspace, itinerary)
            blocked_path = (
                trip_directory / "source" / "r1" / "sanitized-itinerary.txt"
            )
            blocked_path.mkdir()

            failed = run_cli(
                workspace, "trip", "process", "--trip-id", trip_id
            )

            self.assertEqual(failed.returncode, 1)
            self.assertIn("fix the workspace and retry", failed.stderr)
            self.assertNotIn(itinerary.strip(), failed.stderr)
            shutil.rmtree(blocked_path)

            resumed = run_cli(
                workspace, "trip", "process", "--trip-id", trip_id
            )

            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertIn("Itinerary resumed", resumed.stdout)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                stage_status = connection.execute(
                    """
                    SELECT status
                    FROM workflow_stages
                    WHERE stage_name = 'itinerary_process'
                    """
                ).fetchone()[0]
                attempt_statuses = connection.execute(
                    """
                    SELECT attempt.status
                    FROM stage_attempts AS attempt
                    JOIN workflow_stages AS stage
                      ON stage.workflow_stage_id = attempt.workflow_stage_id
                    WHERE stage.stage_name = 'itinerary_process'
                    ORDER BY attempt.attempt_number
                    """
                ).fetchall()
                normalized_count = connection.execute(
                    "SELECT COUNT(*) FROM normalized_itineraries"
                ).fetchone()[0]

            self.assertEqual(stage_status, "COMPLETED")
            self.assertEqual(attempt_statuses, [("FAILED",), ("COMPLETED",)])
            self.assertEqual(normalized_count, 1)


if __name__ == "__main__":
    unittest.main()
