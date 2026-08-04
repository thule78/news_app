from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import threading
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ITINERARY_PAGE = """
<html><body>
<nav><a href="/">Home</a><a href="/deals">Deals</a></nav>
<header class="site-header">Adventure Asia — Book your trip today!</header>
<main>
<h1>Nakasendo Trail</h1>
<p>Day 1: Arrive in Kyoto by train from the airport.</p>
<p>Day 2: Walk from Magome to Tsumago, about 4 hours. Overnight stay in a
guesthouse in Tsumago.</p>
</main>
<div class="newsletter-signup">Subscribe for 10% off your next trip!</div>
<footer>Copyright 2026 Adventure Asia. All rights reserved.</footer>
</body></html>
"""

CHANGED_ITINERARY_PAGE = ITINERARY_PAGE.replace(
    "about 4 hours", "about 5 hours, a longer route this season"
)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib method name
        if self.path == "/not-found":
            self.send_response(404)
            self.end_headers()
            return
        page = CHANGED_ITINERARY_PAGE if self.path == "/changed" else ITINERARY_PAGE
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


class _TestServer:
    def __enter__(self) -> "_TestServer":
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def url(self, path: str) -> str:
        port = self.server.server_address[1]
        return f"http://127.0.0.1:{port}{path}"


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


class UrlIngestionCliTests(unittest.TestCase):
    def test_url_ingestion_excludes_navigation_footer_and_marketing_copy(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory, _TestServer() as server:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)

            result = run_cli(
                workspace,
                "trip",
                "create",
                "--name",
                "Nakasendo",
                "--url",
                server.url("/itinerary"),
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Trip created", result.stdout)

            trip_directory = next((workspace / "outputs").iterdir())
            original = (
                trip_directory / "source" / "r1" / "original-itinerary.txt"
            ).read_text()
            self.assertIn("Day 1", original)
            self.assertIn("Day 2", original)
            self.assertNotIn("Home", original)
            self.assertNotIn("Book your trip", original)
            self.assertNotIn("newsletter", original.lower())
            self.assertNotIn("Copyright", original)

            with sqlite3.connect(workspace / "aa_content.db") as connection:
                revision = connection.execute(
                    "SELECT source_kind, source_url FROM itinerary_revisions"
                ).fetchone()
                fetch = connection.execute(
                    "SELECT requested_url, outcome, http_status FROM source_fetches"
                ).fetchone()
            self.assertEqual(revision[0], "URL")
            self.assertEqual(revision[1], server.url("/itinerary"))
            self.assertEqual(fetch[0], server.url("/itinerary"))
            self.assertEqual(fetch[1], "SUCCESS")
            self.assertEqual(fetch[2], 200)

    def test_same_workflow_processes_url_ingested_itinerary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory, _TestServer() as server:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            created = run_cli(
                workspace,
                "trip",
                "create",
                "--name",
                "Nakasendo",
                "--url",
                server.url("/itinerary"),
            )
            self.assertEqual(created.returncode, 0, created.stderr)
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

            self.assertEqual(processed.returncode, 0, processed.stderr)
            self.assertIn("Itinerary processed", processed.stdout)

    def test_retrieval_failure_is_actionable_and_creates_no_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory, _TestServer() as server:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)

            result = run_cli(
                workspace,
                "trip",
                "create",
                "--name",
                "Nakasendo",
                "--url",
                server.url("/not-found"),
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("Could not retrieve itinerary", result.stderr)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                trip_count = connection.execute(
                    "SELECT COUNT(*) FROM trips"
                ).fetchone()[0]
                fetch = connection.execute(
                    "SELECT outcome, error_code FROM source_fetches"
                ).fetchone()
            self.assertEqual(trip_count, 0)
            self.assertEqual(fetch, ("FAILED", "HTTP_ERROR"))

            retried = run_cli(
                workspace,
                "trip",
                "create",
                "--name",
                "Nakasendo",
                "--url",
                server.url("/itinerary"),
            )
            self.assertEqual(retried.returncode, 0, retried.stderr)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                trip_count = connection.execute(
                    "SELECT COUNT(*) FROM trips"
                ).fetchone()[0]
            self.assertEqual(trip_count, 1)

    def test_unchanged_reingestion_does_not_create_new_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory, _TestServer() as server:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            created = run_cli(
                workspace,
                "trip",
                "create",
                "--name",
                "Nakasendo",
                "--url",
                server.url("/itinerary"),
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            trip_id = next(
                line.removeprefix("Trip ID: ")
                for line in created.stdout.splitlines()
                if line.startswith("Trip ID: ")
            )

            updated = run_cli(
                workspace,
                "trip",
                "update",
                "--trip-id",
                trip_id,
                "--url",
                server.url("/itinerary"),
            )

            self.assertEqual(updated.returncode, 0, updated.stderr)
            self.assertIn("Itinerary unchanged", updated.stdout)
            self.assertIn("Itinerary Revision: r1", updated.stdout)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                revision_count = connection.execute(
                    "SELECT COUNT(*) FROM itinerary_revisions"
                ).fetchone()[0]
                fetch_count = connection.execute(
                    "SELECT COUNT(*) FROM source_fetches"
                ).fetchone()[0]
            self.assertEqual(revision_count, 1)
            self.assertEqual(fetch_count, 2)

    def test_changed_reingestion_creates_new_revision_and_flags_review(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory, _TestServer() as server:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            created = run_cli(
                workspace,
                "trip",
                "create",
                "--name",
                "Nakasendo",
                "--url",
                server.url("/itinerary"),
            )
            self.assertEqual(created.returncode, 0, created.stderr)
            trip_id = next(
                line.removeprefix("Trip ID: ")
                for line in created.stdout.splitlines()
                if line.startswith("Trip ID: ")
            )
            trip_directory = next((workspace / "outputs").iterdir())

            updated = run_cli(
                workspace,
                "trip",
                "update",
                "--trip-id",
                trip_id,
                "--url",
                server.url("/changed"),
            )

            self.assertEqual(updated.returncode, 0, updated.stderr)
            self.assertIn("Itinerary updated", updated.stdout)
            self.assertIn("Itinerary Revision: r2", updated.stdout)
            self.assertIn("Previous Itinerary Revision: r1", updated.stdout)

            self.assertTrue(
                (trip_directory / "source" / "r1" / "original-itinerary.txt")
                .is_file()
            )
            r2_text = (
                trip_directory / "source" / "r2" / "original-itinerary.txt"
            ).read_text()
            self.assertIn("5 hours", r2_text)

            shown = run_cli(workspace, "trip", "show", "--trip-id", trip_id)
            self.assertIn("Working Review: REVIEW_REQUIRED", shown.stdout)

            with sqlite3.connect(workspace / "aa_content.db") as connection:
                revision_count = connection.execute(
                    "SELECT COUNT(*) FROM itinerary_revisions"
                ).fetchone()[0]
                review_state = connection.execute(
                    """
                    SELECT status, based.revision_number, previous.revision_number
                    FROM working_review_state AS state
                    JOIN itinerary_revisions AS based
                      ON based.itinerary_revision_id = state.based_on_revision_id
                    JOIN itinerary_revisions AS previous
                      ON previous.itinerary_revision_id = state.previous_revision_id
                    """
                ).fetchone()
            self.assertEqual(revision_count, 2)
            self.assertEqual(review_state, ("REVIEW_REQUIRED", 2, 1))

    def test_repeating_same_update_command_does_not_duplicate_revisions(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory, _TestServer() as server:
            workspace = Path(temporary_directory)
            self.assertEqual(run_cli(workspace, "init").returncode, 0)
            created = run_cli(
                workspace,
                "trip",
                "create",
                "--name",
                "Nakasendo",
                "--url",
                server.url("/itinerary"),
            )
            trip_id = next(
                line.removeprefix("Trip ID: ")
                for line in created.stdout.splitlines()
                if line.startswith("Trip ID: ")
            )

            first = run_cli(
                workspace,
                "trip",
                "update",
                "--trip-id",
                trip_id,
                "--url",
                server.url("/changed"),
            )
            second = run_cli(
                workspace,
                "trip",
                "update",
                "--trip-id",
                trip_id,
                "--url",
                server.url("/changed"),
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            with sqlite3.connect(workspace / "aa_content.db") as connection:
                revision_count = connection.execute(
                    "SELECT COUNT(*) FROM itinerary_revisions"
                ).fetchone()[0]
            self.assertEqual(revision_count, 2)


if __name__ == "__main__":
    unittest.main()
