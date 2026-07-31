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
    extra_environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    if extra_environment:
        environment.update(extra_environment)
    return subprocess.run(
        [
            str(PROJECT_ROOT / "aa-content"),
            "--workspace",
            str(workspace),
            *arguments,
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


class WorkspaceCliTests(unittest.TestCase):
    def test_operator_can_initialize_shared_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)

            result = run_cli(workspace, "init")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Workspace initialized", result.stdout)
            self.assertTrue((workspace / "aa_content.db").is_file())
            self.assertTrue((workspace / "research-library").is_dir())
            self.assertTrue((workspace / "outputs").is_dir())

            with sqlite3.connect(workspace / "aa_content.db") as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }

            self.assertTrue(
                {
                    "trips",
                    "itinerary_revisions",
                    "workflow_stages",
                    "stage_attempts",
                }.issubset(tables)
            )

    def test_repeating_workspace_init_reuses_completed_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)

            first_result = run_cli(workspace, "init")
            second_result = run_cli(workspace, "init")

            self.assertEqual(first_result.returncode, 0, first_result.stderr)
            self.assertEqual(second_result.returncode, 0, second_result.stderr)
            self.assertIn("already initialized", second_result.stdout)

            with sqlite3.connect(workspace / "aa_content.db") as connection:
                stages = connection.execute(
                    """
                    SELECT stage_name, status
                    FROM workflow_stages
                    WHERE stage_name = 'workspace_init'
                    """
                ).fetchall()
                attempt_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM stage_attempts AS attempt
                    JOIN workflow_stages AS stage
                      ON stage.workflow_stage_id = attempt.workflow_stage_id
                    WHERE stage.stage_name = 'workspace_init'
                    """
                ).fetchone()[0]

            self.assertEqual(stages, [("workspace_init", "COMPLETED")])
            self.assertEqual(attempt_count, 1)

    def test_operator_can_create_trip_from_pasted_itinerary(self) -> None:
        itinerary = (
            "Day 1: Arrive in Kyoto.\n"
            "Day 2: Walk from Magome to Tsumago and stay overnight.\n"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)

            result = run_cli(
                workspace,
                "trip",
                "create",
                "--name",
                "Nakasendo & Kiso Valley",
                stdin=itinerary,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Trip created", result.stdout)

            trip_directories = list((workspace / "outputs").iterdir())
            self.assertEqual(len(trip_directories), 1)
            trip_directory = trip_directories[0]
            self.assertRegex(
                trip_directory.name,
                r"^nakasendo-kiso-valley--trp_[0-9a-f]{32}$",
            )
            self.assertTrue((trip_directory / "working").is_dir())
            self.assertEqual(
                (trip_directory / "source" / "r1" / "original-itinerary.txt").read_text(),
                itinerary,
            )

            metadata = json.loads((trip_directory / "trip.json").read_text())
            self.assertEqual(metadata["name"], "Nakasendo & Kiso Valley")
            self.assertEqual(metadata["slug"], "nakasendo-kiso-valley")
            self.assertEqual(metadata["current_itinerary_revision"], "r1")
            self.assertIsNone(metadata["current_editorial_package_version"])

            with sqlite3.connect(workspace / "aa_content.db") as connection:
                persisted = connection.execute(
                    """
                    SELECT trip.name, trip.slug, revision.revision_number,
                           revision.original_text
                    FROM trips AS trip
                    JOIN itinerary_revisions AS revision
                      ON revision.itinerary_revision_id =
                         trip.current_itinerary_revision_id
                    """
                ).fetchone()

            self.assertEqual(
                persisted,
                ("Nakasendo & Kiso Valley", "nakasendo-kiso-valley", 1, itinerary),
            )

    def test_repeating_trip_create_reuses_trip_without_duplicates(self) -> None:
        itinerary = "Day 1: Walk from Magome to Tsumago.\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)

            first_result = run_cli(
                workspace,
                "trip",
                "create",
                "--name",
                "Nakasendo",
                stdin=itinerary,
            )
            second_result = run_cli(
                workspace,
                "trip",
                "create",
                "--name",
                "Nakasendo",
                stdin=itinerary,
            )

            self.assertEqual(first_result.returncode, 0, first_result.stderr)
            self.assertEqual(second_result.returncode, 0, second_result.stderr)
            self.assertIn("Trip reused", second_result.stdout)
            self.assertEqual(
                [
                    line
                    for line in first_result.stdout.splitlines()
                    if line.startswith("Trip ID:")
                ],
                [
                    line
                    for line in second_result.stdout.splitlines()
                    if line.startswith("Trip ID:")
                ],
            )
            self.assertEqual(len(list((workspace / "outputs").iterdir())), 1)

            with sqlite3.connect(workspace / "aa_content.db") as connection:
                counts = tuple(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in (
                        "trips",
                        "itinerary_revisions",
                    )
                )
                create_stage_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM workflow_stages
                    WHERE stage_name = 'trip_create'
                    """
                ).fetchone()[0]
                create_attempt_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM stage_attempts AS attempt
                    JOIN workflow_stages AS stage
                      ON stage.workflow_stage_id = attempt.workflow_stage_id
                    WHERE stage.stage_name = 'trip_create'
                    """
                ).fetchone()[0]

            self.assertEqual(counts, (1, 1))
            self.assertEqual(create_stage_count, 1)
            self.assertEqual(create_attempt_count, 1)

    def test_openai_key_is_loaded_only_from_private_workspace_env(self) -> None:
        secret = "sk-ticket-one-secret-value"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)

            missing_result = run_cli(
                workspace,
                "config",
                "check-openai",
                extra_environment={"OPENAI_API_KEY": secret},
            )

            self.assertEqual(missing_result.returncode, 2)
            self.assertIn("OPENAI_API_KEY", missing_result.stderr)
            self.assertIn(str(workspace / ".env"), missing_result.stderr)
            self.assertNotIn(secret, missing_result.stdout + missing_result.stderr)

            env_path = workspace / ".env"
            env_path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            env_path.chmod(0o600)

            ready_result = run_cli(workspace, "config", "check-openai")

            self.assertEqual(ready_result.returncode, 0, ready_result.stderr)
            self.assertEqual(ready_result.stdout, "OpenAI configuration ready.\n")
            self.assertNotIn(secret, ready_result.stdout + ready_result.stderr)
            for persisted_path in workspace.rglob("*"):
                if persisted_path.is_file() and persisted_path != env_path:
                    self.assertNotIn(secret.encode(), persisted_path.read_bytes())

    def test_force_regenerates_trip_exports_without_duplicate_domain_records(self) -> None:
        itinerary = "Day 1: Walk the Nakasendo trail.\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            first_result = run_cli(
                workspace,
                "trip",
                "create",
                "--name",
                "Nakasendo",
                stdin=itinerary,
            )
            self.assertEqual(first_result.returncode, 0, first_result.stderr)
            trip_directory = next((workspace / "outputs").iterdir())
            (trip_directory / "trip.json").write_text("damaged", encoding="utf-8")

            force_result = run_cli(
                workspace,
                "trip",
                "create",
                "--name",
                "Nakasendo",
                "--force",
                stdin=itinerary,
            )

            self.assertEqual(force_result.returncode, 0, force_result.stderr)
            self.assertIn("Trip regenerated", force_result.stdout)
            self.assertEqual(
                json.loads((trip_directory / "trip.json").read_text())["name"],
                "Nakasendo",
            )
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                trip_count = connection.execute(
                    "SELECT COUNT(*) FROM trips"
                ).fetchone()[0]
                revision_count = connection.execute(
                    "SELECT COUNT(*) FROM itinerary_revisions"
                ).fetchone()[0]
                attempt_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM stage_attempts AS attempt
                    JOIN workflow_stages AS stage
                      ON stage.workflow_stage_id = attempt.workflow_stage_id
                    WHERE stage.stage_name = 'trip_create'
                    """
                ).fetchone()[0]

            self.assertEqual((trip_count, revision_count, attempt_count), (1, 1, 2))

    def test_operator_can_inspect_persisted_trip_and_workflow_state(self) -> None:
        itinerary = "Day 1: Walk from Magome to Tsumago.\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            create_result = run_cli(
                workspace,
                "trip",
                "create",
                "--name",
                "Nakasendo",
                stdin=itinerary,
            )
            self.assertEqual(create_result.returncode, 0, create_result.stderr)
            trip_id = next(
                line.removeprefix("Trip ID: ")
                for line in create_result.stdout.splitlines()
                if line.startswith("Trip ID: ")
            )

            show_result = run_cli(
                workspace,
                "trip",
                "show",
                "--trip-id",
                trip_id,
            )

            self.assertEqual(show_result.returncode, 0, show_result.stderr)
            self.assertIn("Trip: Nakasendo", show_result.stdout)
            self.assertIn(f"Trip ID: {trip_id}", show_result.stdout)
            self.assertIn("Current Itinerary Revision: r1", show_result.stdout)
            self.assertIn("Trip Creation: COMPLETED", show_result.stdout)
            self.assertIn(
                f"outputs/nakasendo--{trip_id}/source/r1/original-itinerary.txt",
                show_result.stdout,
            )

    def test_failed_trip_creation_resumes_without_duplicate_records(self) -> None:
        itinerary = "Day 1: Walk from Magome to Tsumago.\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            outputs_path = workspace / "outputs"
            outputs_path.rmdir()
            outputs_path.write_text("blocks directory creation", encoding="utf-8")

            failed_result = run_cli(
                workspace,
                "trip",
                "create",
                "--name",
                "Nakasendo",
                stdin=itinerary,
            )

            self.assertEqual(failed_result.returncode, 1)
            self.assertIn("retry the same command", failed_result.stderr)
            self.assertNotIn(itinerary.strip(), failed_result.stderr)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                failed_counts = tuple(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in ("trips", "itinerary_revisions")
                )
                failed_stage_status = connection.execute(
                    """
                    SELECT status FROM workflow_stages
                    WHERE stage_name = 'trip_create'
                    """
                ).fetchone()[0]
                failed_attempt_status = connection.execute(
                    """
                    SELECT attempt.status FROM stage_attempts AS attempt
                    JOIN workflow_stages AS stage
                      ON stage.workflow_stage_id = attempt.workflow_stage_id
                    WHERE stage.stage_name = 'trip_create'
                    """
                ).fetchone()[0]

            self.assertEqual(failed_counts, (1, 1))
            self.assertEqual(failed_stage_status, "FAILED")
            self.assertEqual(failed_attempt_status, "FAILED")

            outputs_path.unlink()
            outputs_path.mkdir()
            resumed_result = run_cli(
                workspace,
                "trip",
                "create",
                "--name",
                "Nakasendo",
                stdin=itinerary,
            )

            self.assertEqual(resumed_result.returncode, 0, resumed_result.stderr)
            self.assertIn("Trip resumed", resumed_result.stdout)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                resumed_counts = tuple(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in ("trips", "itinerary_revisions")
                )
                stage_status = connection.execute(
                    """
                    SELECT status FROM workflow_stages
                    WHERE stage_name = 'trip_create'
                    """
                ).fetchone()[0]
                attempt_statuses = connection.execute(
                    """
                    SELECT attempt.status
                    FROM stage_attempts AS attempt
                    JOIN workflow_stages AS stage
                      ON stage.workflow_stage_id = attempt.workflow_stage_id
                    WHERE stage.stage_name = 'trip_create'
                    ORDER BY attempt.attempt_number
                    """
                ).fetchall()

            self.assertEqual(resumed_counts, (1, 1))
            self.assertEqual(stage_status, "COMPLETED")
            self.assertEqual(attempt_statuses, [("FAILED",), ("COMPLETED",)])

    def test_unicode_trip_name_produces_readable_slug(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)

            result = run_cli(
                workspace,
                "trip",
                "create",
                "--name",
                "中山道",
                stdin="第一天：馬籠から妻籠まで歩く。\n",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            trip_directory = next((workspace / "outputs").iterdir())
            self.assertRegex(
                trip_directory.name,
                r"^中山道--trp_[0-9a-f]{32}$",
            )

    def test_force_preserves_later_editorial_package_state(self) -> None:
        itinerary = "Day 1: Walk the Nakasendo trail.\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            self.assertEqual(
                run_cli(
                    workspace,
                    "trip",
                    "create",
                    "--name",
                    "Nakasendo",
                    stdin=itinerary,
                ).returncode,
                0,
            )
            trip_directory = next((workspace / "outputs").iterdir())
            metadata = json.loads((trip_directory / "trip.json").read_text())
            metadata["current_editorial_package_version"] = "v1"
            (trip_directory / "trip.json").write_text(
                json.dumps(metadata), encoding="utf-8"
            )
            (trip_directory / "current-version.json").write_text(
                '{"current_version": "v1"}\n', encoding="utf-8"
            )
            (trip_directory / "v1").mkdir()
            (trip_directory / "v1" / "manifest.json").write_text(
                '{"version": "v1"}\n', encoding="utf-8"
            )
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                connection.execute(
                    """
                    UPDATE trips
                    SET current_editorial_package_version = 'v1'
                    """
                )
            (trip_directory / "trip.json").write_text("damaged", encoding="utf-8")

            force_result = run_cli(
                workspace,
                "trip",
                "create",
                "--name",
                "Nakasendo",
                "--force",
                stdin=itinerary,
            )

            self.assertEqual(force_result.returncode, 0, force_result.stderr)
            regenerated_metadata = json.loads(
                (trip_directory / "trip.json").read_text()
            )
            self.assertEqual(
                regenerated_metadata["current_editorial_package_version"], "v1"
            )
            self.assertEqual(
                json.loads((trip_directory / "current-version.json").read_text()),
                {"current_version": "v1"},
            )
            self.assertTrue((trip_directory / "v1" / "manifest.json").is_file())

    def test_interrupted_artifact_swap_recovers_and_resumes_same_trip(self) -> None:
        itinerary = "Day 1: Walk the Nakasendo trail.\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            self.assertEqual(
                run_cli(
                    workspace,
                    "trip",
                    "create",
                    "--name",
                    "Nakasendo",
                    stdin=itinerary,
                ).returncode,
                0,
            )
            trip_directory = next((workspace / "outputs").iterdir())
            trip_id = json.loads((trip_directory / "trip.json").read_text())[
                "trip_id"
            ]
            staging = workspace / "outputs" / f".staging-{trip_id}"
            backup = workspace / "outputs" / f".backup-{trip_id}"
            shutil.copytree(trip_directory, staging)
            os.replace(trip_directory, backup)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                connection.execute(
                    """
                    UPDATE workflow_stages
                    SET status = 'IN_PROGRESS', completed_at = NULL
                    WHERE stage_name = 'trip_create'
                    """
                )
                connection.execute(
                    """
                    UPDATE stage_attempts
                    SET status = 'IN_PROGRESS', completed_at = NULL
                    WHERE workflow_stage_id = (
                        SELECT workflow_stage_id
                        FROM workflow_stages
                        WHERE stage_name = 'trip_create'
                    )
                    """
                )

            resumed_result = run_cli(
                workspace,
                "trip",
                "create",
                "--name",
                "Nakasendo",
                stdin=itinerary,
            )

            self.assertEqual(resumed_result.returncode, 0, resumed_result.stderr)
            self.assertIn("Trip resumed", resumed_result.stdout)
            self.assertTrue(trip_directory.is_dir())
            self.assertFalse(staging.exists())
            self.assertFalse(backup.exists())
            self.assertEqual(
                (trip_directory / "source" / "r1" / "original-itinerary.txt").read_text(),
                itinerary,
            )
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                stage_status = connection.execute(
                    """
                    SELECT status FROM workflow_stages
                    WHERE stage_name = 'trip_create'
                    """
                ).fetchone()[0]
                attempts = connection.execute(
                    """
                    SELECT attempt.status, attempt.error_code
                    FROM stage_attempts AS attempt
                    JOIN workflow_stages AS stage
                      ON stage.workflow_stage_id = attempt.workflow_stage_id
                    WHERE stage.stage_name = 'trip_create'
                    ORDER BY attempt.attempt_number
                    """
                ).fetchall()

            self.assertEqual(stage_status, "COMPLETED")
            self.assertEqual(
                attempts,
                [("FAILED", "INTERRUPTED"), ("COMPLETED", None)],
            )

    def test_completed_stage_remains_bound_to_its_exact_itinerary_revision(self) -> None:
        itinerary = "Day 1: Walk the Nakasendo trail.\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            first_result = run_cli(
                workspace,
                "trip",
                "create",
                "--name",
                "Nakasendo",
                stdin=itinerary,
            )
            self.assertEqual(first_result.returncode, 0, first_result.stderr)
            trip_directory = next((workspace / "outputs").iterdir())
            first_metadata = json.loads((trip_directory / "trip.json").read_text())
            trip_id = first_metadata["trip_id"]
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                connection.execute(
                    """
                    INSERT INTO itinerary_revisions (
                        itinerary_revision_id,
                        trip_id,
                        revision_number,
                        source_kind,
                        original_text,
                        content_hash,
                        created_at
                    )
                    SELECT
                        'irv_simulated_r2',
                        trip_id,
                        2,
                        source_kind,
                        'Day 1: Changed itinerary.',
                        'simulated-r2-hash',
                        created_at
                    FROM itinerary_revisions
                    WHERE revision_number = 1
                    """
                )
                connection.execute(
                    """
                    UPDATE trips
                    SET current_itinerary_revision_id = 'irv_simulated_r2'
                    WHERE trip_id = ?
                    """,
                    (trip_id,),
                )

            repeated_result = run_cli(
                workspace,
                "trip",
                "create",
                "--name",
                "Nakasendo",
                stdin=itinerary,
            )

            self.assertEqual(repeated_result.returncode, 0, repeated_result.stderr)
            self.assertIn("Trip reused", repeated_result.stdout)
            self.assertIn("Itinerary Revision: r1", repeated_result.stdout)


if __name__ == "__main__":
    unittest.main()
