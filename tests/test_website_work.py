import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from beyondseo import projects
from beyondseo.cli import main
from beyondseo.network import utcnow
from beyondseo.onsite import draft_html, plan_html, sitemap_draft
from beyondseo.publishing import LocalStore, apply_change

HTML = b"""<!doctype html><html lang="en"><head><title>Service</title><style>p { max-width: 30em; }</style></head><body><nav><a href="/">Home</a></nav><main><h1>Useful AI services</h1><p id="intro" class="short">We build practical AI tools for small teams and their daily work.</p><p id="linked">Read <a href="/services">our services</a>.</p></main></body></html>"""


class WebsiteWorkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "private-project"
        projects.init_project(
            self.project, "https://example.com", "Improve the website without redesigning it"
        )

    def job(self, **values):
        row = {
            "id": "service-copy",
            "title": "Clarify the service",
            "kind": "onsite",
            "url": "https://example.com/services",
            "action": "Answer the service question in the existing paragraph",
            "acceptance": "Desktop/mobile layout preserved and content correct",
            "evidence": "Observed source paragraph in the saved baseline",
            "estimate_minutes": [10, 30],
        }
        row.update(values)
        return row

    def test_init_does_not_create_dashboard_or_replace_project(self):
        self.assertFalse((self.project / "dashboard.html").exists())
        self.assertIsNone(projects.snapshot(self.project)["schedule"])
        with self.assertRaisesRegex(ValueError, "never replaced"):
            projects.init_project(self.project, "https://example.com", "different")

    def test_same_job_import_is_idempotent_and_changed_id_conflicts(self):
        projects.add_jobs(self.project, [self.job()])
        projects.add_jobs(self.project, [self.job()])
        self.assertEqual(len(projects.snapshot(self.project)["jobs"]), 1)
        with self.assertRaisesRegex(ValueError, "different content"):
            projects.add_jobs(self.project, [self.job(title="Different work")])

    def test_invalid_second_job_rolls_back_whole_plan(self):
        with self.assertRaises(ValueError):
            projects.add_jobs(
                self.project,
                [self.job(), self.job(id="second", url="https://unrelated.example/services")],
            )
        self.assertEqual(projects.snapshot(self.project)["jobs"], [])

    def test_unsupported_job_fields_and_credentials_urls_rejected(self):
        for row in (
            self.job(password="secret"),
            self.job(url="https://user:password@example.com/"),
            self.job(destination="https://example.org/?token=secret"),
        ):
            with self.assertRaises(ValueError):
                projects.add_jobs(self.project, [row])

    def test_new_page_needs_existing_authorisation_record(self):
        projects.add_jobs(self.project, [self.job(kind="new_page")])
        with self.assertRaisesRegex(ValueError, "authorisation"):
            projects.transition(self.project, "service-copy", "running", "Start")
        projects.transition(
            self.project,
            "service-copy",
            "running",
            "Start",
            approval="User approved this page in the current task",
        )
        self.assertEqual(projects.snapshot(self.project)["jobs"][0]["status"], "running")

    def test_applied_does_not_mean_verified_and_failed_checks_cannot_pass(self):
        projects.add_jobs(self.project, [self.job()])
        projects.transition(self.project, "service-copy", "running", "Start")
        with self.assertRaisesRegex(ValueError, "applied"):
            projects.transition(self.project, "service-copy", "verified", "Looks done")
        projects.transition(self.project, "service-copy", "applied", "Preview changed")
        with self.assertRaisesRegex(ValueError, "saved acceptance"):
            projects.transition(self.project, "service-copy", "verified", "Done")
        artifact = self.root / "capture.html"
        artifact.write_bytes(HTML)
        evidence = self.root / "verification.json"
        data = {
            "url": "https://example.com/services",
            "captured_at": utcnow(),
            "checks": [{"name": "Mobile", "result": "fail", "observation": "Overflow"}],
            "coverage": "Preview only",
            "artifacts": ["capture.html"],
        }
        evidence.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "passing"):
            projects.transition(self.project, "service-copy", "verified", "Done", evidence)
        data["checks"][0].update(result="pass", observation="No horizontal overflow at 390px")
        evidence.write_text(json.dumps(data))
        projects.transition(self.project, "service-copy", "verified", "Checks complete", evidence)
        verification = projects.snapshot(self.project)["jobs"][0]["verification"]
        self.assertEqual(len(verification["artifacts"][0]["sha256"]), 64)
        self.assertEqual(verification["coverage"], "Preview only")

    def test_pause_blocks_work_until_resumed(self):
        projects.add_jobs(self.project, [self.job()])
        projects.configure(self.project, pause=True)
        with self.assertRaisesRegex(ValueError, "paused"):
            projects.transition(self.project, "service-copy", "running", "Start")
        projects.configure(self.project, pause=False)
        projects.transition(self.project, "service-copy", "running", "Start")

    def test_dashboard_requires_consent_is_escaped_and_updates(self):
        with self.assertRaisesRegex(ValueError, "consent"):
            projects.configure(self.project, dashboard=True)
        projects.add_jobs(self.project, [self.job(title='<script>alert("x")</script>')])
        projects.configure(self.project, dashboard=True, consent=True)
        output = (self.project / "dashboard.html").read_text()
        self.assertIn("&lt;script&gt;", output)
        self.assertNotIn("<script>alert", output)
        self.assertIn("data:image/png;base64,", output)
        projects.transition(self.project, "service-copy", "running", "Baseline retained")
        self.assertIn("Baseline retained", (self.project / "dashboard.html").read_text())

    def test_readonly_monitor_has_no_file_listing_or_cross_host_access(self):
        projects.configure(self.project, dashboard=True, consent=True)
        server, url = projects.make_server(self.project)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(url, timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertIn("no-store", response.headers["Cache-Control"])
                self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
            for request in (
                url.rsplit("/", 1)[0] + "/project.sqlite3",
                Request(url, headers={"Host": "attacker.example"}),
            ):
                with self.assertRaises(HTTPError) as error:
                    urlopen(request, timeout=5)
                self.assertEqual(error.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(5)

    def test_schedule_is_not_a_scheduler_and_runner_is_bounded(self):
        projects.configure(self.project, interval=3600, max_pages=3)
        self.assertIn("external scheduler", projects.snapshot(self.project)["worker_status"])
        calls = []

        def runner(url, out, pages):
            calls.append((url, out, pages))
            return {"html_documents": 2, "coverage_limited": True}

        first = projects.run_due(self.project, runner)
        second = projects.run_due(self.project, runner)
        self.assertEqual(first["status"], "completed")
        self.assertTrue(first["coverage_limited"])
        self.assertEqual(second["status"], "not_due")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][2], 3)

    def test_concurrent_invocations_do_not_double_execute(self):
        projects.configure(self.project, interval=3600)
        entered, finish = threading.Event(), threading.Event()

        def runner(*args):
            entered.set()
            self.assertTrue(finish.wait(5))
            return {"html_documents": 1}

        with ThreadPoolExecutor(2) as pool:
            first = pool.submit(projects.run_due, self.project, runner)
            self.assertTrue(entered.wait(5))
            second = projects.run_due(self.project, runner)
            self.assertEqual(second["status"], "needs_inspection")
            finish.set()
            self.assertEqual(first.result()["status"], "completed")
        self.assertEqual(len(projects.snapshot(self.project)["runs"]), 1)

    def test_empty_capture_is_blocked_not_verified_or_missing_content(self):
        projects.configure(self.project, interval=3600)
        result = projects.run_due(
            self.project, lambda *args: {"html_documents": 0, "coverage_limited": True}
        )
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(projects.snapshot(self.project)["jobs"], [])

    def test_worker_error_is_recorded_without_sensitive_exception_text(self):
        projects.configure(self.project, interval=3600)

        def fail(*args):
            raise PermissionError("secret-password")

        result = projects.run_due(self.project, fail)
        self.assertEqual(result["failure_type"], "PermissionError")
        self.assertEqual(result["status"], "failed")
        self.assertNotIn("secret-password", json.dumps(projects.snapshot(self.project)))

    def test_interrupted_runner_requires_explicit_recovery(self):
        projects.configure(self.project, interval=3600)
        with projects.connection(self.project) as db:
            db.execute(
                "INSERT INTO runs VALUES (?,?,?,?,?)", ("old", "running", utcnow(), None, "{}")
            )
        self.assertEqual(projects.run_due(self.project)["status"], "needs_inspection")
        projects.recover(self.project, "old", "Old process confirmed stopped; evidence retained")
        self.assertEqual(
            projects.run_due(self.project, lambda *args: {"html_documents": 1})["status"],
            "completed",
        )

    def test_static_draft_preserves_body_structure_styles_links_and_classes(self):
        after, checks = draft_html(
            HTML,
            {
                "title": "AI implementation for small teams",
                "description": "Practical AI services",
                "copy": [
                    {
                        "selector": "#intro",
                        "text": "We create useful AI tools for small teams and their everyday work.",
                    }
                ],
            },
        )
        before_soup, after_soup = (
            BeautifulSoup(HTML, "html.parser"),
            BeautifulSoup(after, "html.parser"),
        )
        self.assertEqual(
            [(n.name, n.attrs) for n in before_soup.body.find_all(True)],
            [(n.name, n.attrs) for n in after_soup.body.find_all(True)],
        )
        self.assertEqual(str(before_soup.style), str(after_soup.style))
        self.assertEqual(str(before_soup.nav), str(after_soup.nav))
        self.assertIn("required", checks["visual_verification"])

    def test_empty_draft_and_invalid_selector_are_actionable_errors(self):
        for change in ({}, {"copy": [{"selector": "[", "text": "Invalid"}]}):
            with self.assertRaises(ValueError):
                draft_html(HTML, change)

    def test_copy_expansion_nested_markup_and_ambiguous_selector_refused(self):
        for change in (
            {"selector": "#intro", "text": "Long " * 100},
            {"selector": "#linked", "text": "Read our services."},
            {"selector": "p", "text": "Text"},
        ):
            with self.assertRaises(ValueError):
                draft_html(HTML, {"copy": [change]})

    def test_template_and_duplicate_metadata_refused(self):
        for raw in (
            HTML.replace(b"Service</title>", b"{{ service }}</title>"),
            HTML.replace(b"</head>", b"<title>Duplicate</title></head>"),
        ):
            with self.assertRaises(ValueError):
                draft_html(raw, {"title": "Reviewed title"})

    def test_schema_does_not_duplicate_existing_or_allow_script_escape(self):
        schema = {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "</script><script>alert(1)</script>",
        }
        after, _ = draft_html(HTML, {"schema": schema})
        soup = BeautifulSoup(after, "html.parser")
        self.assertEqual(len(soup.find_all("script")), 1)
        self.assertEqual(json.loads(soup.script.string), schema)
        with self.assertRaisesRegex(ValueError, "Existing JSON-LD"):
            draft_html(after, {"schema": schema})

    def test_stage_apply_and_rollback_keep_original_and_require_exact_hash(self):
        site = self.root / "site"
        site.mkdir()
        (site / "services.html").write_bytes(HTML)
        changes = self.root / "changes.json"
        changes.write_text(json.dumps({"title": "Clear service title"}))
        folder = self.root / "plan"
        result = plan_html(site, None, "services.html", changes, folder)
        self.assertEqual((site / "services.html").read_bytes(), HTML)
        with closing(LocalStore(site)) as store:
            with self.assertRaisesRegex(ValueError, "reviewed hash"):
                apply_change(store, folder, "wrong")
            self.assertEqual(
                apply_change(store, folder, result["plan_sha256"])["status"], "applied"
            )
            self.assertIn(b"Clear service title", (site / "services.html").read_bytes())
            apply_change(store, folder, result["plan_sha256"], rollback=True)
        self.assertEqual((site / "services.html").read_bytes(), HTML)

    def test_sitemap_requires_verified_canonical_indexable_urls_and_deduplicates(self):
        row = {
            "url": "https://example.com/services",
            "canonical": "https://example.com/services",
            "status": 200,
            "indexable": True,
            "captured_at": utcnow(),
        }
        output = sitemap_draft([row, row], "https://example.com")
        self.assertEqual(output.count(b"<loc>"), 1)
        for update in (
            {"status": 404},
            {"indexable": False},
            {"canonical": "https://example.com/other"},
            {"url": "https://other.example/"},
        ):
            with self.assertRaises(ValueError):
                sitemap_draft([{**row, **update}], "https://example.com")

    def test_project_and_onsite_cli_are_registered(self):
        self.assertEqual(main(["project", "status", "--project", str(self.project)]), 0)
        self.assertEqual(main(["project", "dashboard", "--project", str(self.project)]), 2)

    def test_recording_blocked_job_does_not_abort_following_monitor_command(self):
        projects.add_jobs(self.project, [self.job()])
        code = main(
            [
                "project",
                "update",
                "--project",
                str(self.project),
                "--job",
                "service-copy",
                "--state",
                "blocked",
                "--note",
                "Waiting for repository access",
            ]
        )
        self.assertEqual(code, 0)
        self.assertEqual(projects.snapshot(self.project)["jobs"][0]["status"], "blocked")
        if code == 0:
            code = main(["project", "dashboard", "--project", str(self.project), "--consent"])
        self.assertEqual(code, 0)
        self.assertIn(
            "Waiting for repository access", (self.project / "dashboard.html").read_text()
        )
        self.assertEqual(
            main(
                [
                    "project",
                    "update",
                    "--project",
                    str(self.project),
                    "--job",
                    "unknown-job",
                    "--state",
                    "blocked",
                    "--note",
                    "Invalid target",
                ]
            ),
            2,
        )

    def test_actual_blocked_review_run_still_returns_failure(self):
        with patch.object(projects, "run_due", return_value={"status": "blocked"}):
            self.assertEqual(main(["project", "run", "--project", str(self.project)]), 1)
