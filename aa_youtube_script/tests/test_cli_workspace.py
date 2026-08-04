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
        [str(PROJECT_ROOT / "aa-content"), "--workspace", str(workspace), *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )


class WorkspaceCliTests(unittest.TestCase):
    def test_init_creates_sqlite_backed_workspace_without_third_party_dependency(
        self,
    ) -> None:
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
                {"trips", "itinerary_revisions", "workflow_stages", "stage_attempts"}
                .issubset(tables)
            )

    def test_repeated_init_reuses_completed_stage_without_duplicate_attempts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)

            first = run_cli(workspace, "init")
            second = run_cli(workspace, "init")

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("already initialized", second.stdout)

            with sqlite3.connect(workspace / "aa_content.db") as connection:
                stages = connection.execute(
                    "SELECT status FROM workflow_stages WHERE stage_name = "
                    "'workspace_init'"
                ).fetchall()
                attempt_count = connection.execute(
                    """
                    SELECT COUNT(*) FROM stage_attempts AS attempt
                    JOIN workflow_stages AS stage
                      ON stage.workflow_stage_id = attempt.workflow_stage_id
                    WHERE stage.stage_name = 'workspace_init'
                    """
                ).fetchone()[0]
            self.assertEqual(stages, [("COMPLETED",)])
            self.assertEqual(attempt_count, 1)

    def test_create_trip_assigns_stable_id_and_preserves_original_itinerary(
        self,
    ) -> None:
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
                trip_directory.name, r"^nakasendo-kiso-valley--trp_[0-9a-f]{32}$"
            )
            self.assertTrue((trip_directory / "working").is_dir())
            self.assertEqual(
                (trip_directory / "source" / "r1" / "original-itinerary.txt")
                .read_text(),
                itinerary,
            )

            metadata = json.loads((trip_directory / "trip.json").read_text())
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

    def test_repeating_create_reuses_trip_without_duplicating_domain_records(
        self,
    ) -> None:
        itinerary = "Day 1: Walk from Magome to Tsumago.\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)

            first = run_cli(
                workspace, "trip", "create", "--name", "Nakasendo", stdin=itinerary
            )
            second = run_cli(
                workspace, "trip", "create", "--name", "Nakasendo", stdin=itinerary
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("Trip reused", second.stdout)
            self.assertEqual(len(list((workspace / "outputs").iterdir())), 1)

            with sqlite3.connect(workspace / "aa_content.db") as connection:
                counts = tuple(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in ("trips", "itinerary_revisions")
                )
                attempt_count = connection.execute(
                    """
                    SELECT COUNT(*) FROM stage_attempts AS attempt
                    JOIN workflow_stages AS stage
                      ON stage.workflow_stage_id = attempt.workflow_stage_id
                    WHERE stage.stage_name = 'trip_create'
                    """
                ).fetchone()[0]
            self.assertEqual(counts, (1, 1))
            self.assertEqual(attempt_count, 1)

    def test_openai_key_loads_only_from_private_workspace_env_without_leaking(
        self,
    ) -> None:
        secret = "sk-ticket-one-secret-value"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)

            missing = run_cli(
                workspace,
                "config",
                "check-openai",
                extra_environment={"OPENAI_API_KEY": secret},
            )
            self.assertEqual(missing.returncode, 2)
            self.assertIn("OPENAI_API_KEY", missing.stderr)
            self.assertIn(str(workspace / ".env"), missing.stderr)
            self.assertNotIn(secret, missing.stdout + missing.stderr)

            env_path = workspace / ".env"
            env_path.write_text(f"OPENAI_API_KEY={secret}\n", encoding="utf-8")
            env_path.chmod(0o600)

            ready = run_cli(workspace, "config", "check-openai")
            self.assertEqual(ready.returncode, 0, ready.stderr)
            self.assertEqual(ready.stdout, "OpenAI configuration ready.\n")
            self.assertNotIn(secret, ready.stdout + ready.stderr)
            for path in workspace.rglob("*"):
                if path.is_file() and path != env_path:
                    self.assertNotIn(secret.encode(), path.read_bytes())

    def test_force_regenerates_exports_without_duplicating_domain_records(
        self,
    ) -> None:
        itinerary = "Day 1: Walk the Nakasendo trail.\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            self.assertEqual(
                run_cli(
                    workspace, "trip", "create", "--name", "Nakasendo", stdin=itinerary
                ).returncode,
                0,
            )
            trip_directory = next((workspace / "outputs").iterdir())
            (trip_directory / "trip.json").write_text("damaged", encoding="utf-8")

            forced = run_cli(
                workspace,
                "trip",
                "create",
                "--name",
                "Nakasendo",
                "--force",
                stdin=itinerary,
            )

            self.assertEqual(forced.returncode, 0, forced.stderr)
            self.assertIn("Trip regenerated", forced.stdout)
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
                    SELECT COUNT(*) FROM stage_attempts AS attempt
                    JOIN workflow_stages AS stage
                      ON stage.workflow_stage_id = attempt.workflow_stage_id
                    WHERE stage.stage_name = 'trip_create'
                    """
                ).fetchone()[0]
            self.assertEqual((trip_count, revision_count, attempt_count), (1, 1, 2))

    def test_inspect_shows_persisted_trip_and_workflow_state(self) -> None:
        itinerary = "Day 1: Walk from Magome to Tsumago.\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            created = run_cli(
                workspace, "trip", "create", "--name", "Nakasendo", stdin=itinerary
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            trip_id = next(
                line.removeprefix("Trip ID: ")
                for line in created.stdout.splitlines()
                if line.startswith("Trip ID: ")
            )

            shown = run_cli(workspace, "trip", "show", "--trip-id", trip_id)

            self.assertEqual(shown.returncode, 0, shown.stderr)
            self.assertIn("Trip: Nakasendo", shown.stdout)
            self.assertIn(f"Trip ID: {trip_id}", shown.stdout)
            self.assertIn("Current Itinerary Revision: r1", shown.stdout)
            self.assertIn("Trip Creation: COMPLETED", shown.stdout)
            self.assertIn(
                f"outputs/nakasendo--{trip_id}/source/r1/original-itinerary.txt",
                shown.stdout,
            )

    def test_failed_creation_resumes_without_duplicate_records(self) -> None:
        itinerary = "Day 1: Walk from Magome to Tsumago.\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            outputs_path = workspace / "outputs"
            outputs_path.rmdir()
            outputs_path.write_text("blocks directory creation", encoding="utf-8")

            failed = run_cli(
                workspace, "trip", "create", "--name", "Nakasendo", stdin=itinerary
            )

            self.assertEqual(failed.returncode, 1)
            self.assertIn("retry the same command", failed.stderr)
            self.assertNotIn(itinerary.strip(), failed.stderr)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                counts = tuple(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in ("trips", "itinerary_revisions")
                )
                stage_status = connection.execute(
                    "SELECT status FROM workflow_stages WHERE stage_name = "
                    "'trip_create'"
                ).fetchone()[0]
            self.assertEqual(counts, (1, 1))
            self.assertEqual(stage_status, "FAILED")

            outputs_path.unlink()
            outputs_path.mkdir()
            resumed = run_cli(
                workspace, "trip", "create", "--name", "Nakasendo", stdin=itinerary
            )

            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertIn("Trip resumed", resumed.stdout)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                resumed_counts = tuple(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                    for table in ("trips", "itinerary_revisions")
                )
                stage_status = connection.execute(
                    "SELECT status FROM workflow_stages WHERE stage_name = "
                    "'trip_create'"
                ).fetchone()[0]
                attempt_statuses = connection.execute(
                    """
                    SELECT attempt.status FROM stage_attempts AS attempt
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
                stdin="第一天:馬籠から妻籠まで歩く。\n",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            trip_directory = next((workspace / "outputs").iterdir())
            self.assertRegex(trip_directory.name, r"^中山道--trp_[0-9a-f]{32}$")

    def test_interrupted_artifact_swap_recovers_and_resumes_same_trip(self) -> None:
        itinerary = "Day 1: Walk the Nakasendo trail.\n"
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            self.assertEqual(
                run_cli(
                    workspace, "trip", "create", "--name", "Nakasendo", stdin=itinerary
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
                    "UPDATE workflow_stages SET status = 'IN_PROGRESS', "
                    "completed_at = NULL WHERE stage_name = 'trip_create'"
                )
                connection.execute(
                    """
                    UPDATE stage_attempts
                    SET status = 'IN_PROGRESS', completed_at = NULL
                    WHERE workflow_stage_id = (
                        SELECT workflow_stage_id FROM workflow_stages
                        WHERE stage_name = 'trip_create'
                    )
                    """
                )

            resumed = run_cli(
                workspace, "trip", "create", "--name", "Nakasendo", stdin=itinerary
            )

            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertIn("Trip resumed", resumed.stdout)
            self.assertTrue(trip_directory.is_dir())
            self.assertFalse(staging.exists())
            self.assertFalse(backup.exists())
            self.assertEqual(
                (trip_directory / "source" / "r1" / "original-itinerary.txt")
                .read_text(),
                itinerary,
            )
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                stage_status = connection.execute(
                    "SELECT status FROM workflow_stages WHERE stage_name = "
                    "'trip_create'"
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
                attempts, [("FAILED", "INTERRUPTED"), ("COMPLETED", None)]
            )


if __name__ == "__main__":
    unittest.main()
