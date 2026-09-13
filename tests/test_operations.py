import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from test_crawler import CrawlerTests

from beyondseo.backlinks import check_sources
from beyondseo.engine import write_json
from beyondseo.extract import extract
from beyondseo.monitor import watch
from beyondseo.network import RobotsRules
from beyondseo.publishing import LocalStore, RemoteStore, apply_change, digest, stage
from beyondseo.review import compare, readiness


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.url = "https://example.com/"

    def tearDown(self):
        self.tmp.cleanup()

    def page(self, html="<title>Test</title><main>Useful answer</main>"):
        return {
            "url": self.url,
            "final_url": self.url,
            "status": 200,
            "headers": {},
            "error": "",
            "data": extract(html, self.url),
        }

    def snapshot(self, name, pages, issues):
        out = self.root / name
        out.mkdir()
        write_json(
            out / "summary.json", {"seed": self.url, "configuration": {}, "coverage_limited": False}
        )
        write_json(out / "issues.json", issues)
        (out / "pages.jsonl").write_text("\n".join(json.dumps(p) for p in pages))
        return out

    def test_agent_rules_are_evaluated_separately(self):
        text = "User-agent: *\nAllow: /\nUser-agent: Googlebot\nDisallow: /\n"
        self.assertFalse(RobotsRules(text, agent="Googlebot").allowed(self.url))
        self.assertTrue(RobotsRules(text, agent="Bingbot").allowed(self.url))
        result = readiness(
            [self.page()],
            {"seed": self.url},
            {self.url.rstrip("/"): {"text": text, "blocked": False}},
            {"urls": [{"url": self.url}]},
        )
        self.assertTrue(result["pages"][0]["in_observed_sitemap"])
        self.assertFalse(result["pages"][0]["robots_path_permissions"]["Googlebot"])

    def test_unknown_robots_remains_unknown(self):
        result = readiness([self.page()], {}, {}, {})
        self.assertIsNone(result["pages"][0]["robots_path_permissions"]["Googlebot"])

    def test_raw_noindex_survives_rendered_removal(self):
        page = self.page('<meta name="robots" content="noindex"><main>Raw</main>')
        page["rendered"] = {"data": extract("<main>Rendered content</main>", self.url), "error": ""}
        result = readiness([page], {}, {}, {})
        self.assertIn("noindex_observed", [r["code"] for r in result["pages"][0]["observations"]])

    def test_diff_tracks_changed_content_and_missing_urls_without_false_resolution(self):
        old = self.page()
        missing = self.page()
        missing["url"] += "missing"
        a = self.snapshot(
            "before", [old, missing], [{"url": missing["url"], "code": "title_missing"}]
        )
        b = self.snapshot("after", [self.page("<title>New</title><main>Updated answer</main>")], [])
        result = compare(a, b, self.root / "diff")
        self.assertEqual(result["not_reobserved_urls"], [missing["url"]])
        self.assertEqual(result["findings_no_longer_observed_on_comparable_pages"], [])
        self.assertIn("title", result["changed_pages"][0]["fields"])

    def test_failed_capture_is_not_a_resolved_issue(self):
        old = self.page()
        new = {**old, "status": 403, "error": "denied", "data": None}
        a = self.snapshot("before", [old], [{"url": self.url, "code": "title_missing"}])
        b = self.snapshot("after", [new], [])
        self.assertFalse(
            compare(a, b, self.root / "diff")["findings_no_longer_observed_on_comparable_pages"]
        )

    def test_comparison_rejects_different_seeds(self):
        a = self.snapshot("before", [self.page()], [])
        b = self.snapshot("after", [self.page()], [])
        write_json(b / "summary.json", {"seed": "https://competitor.example/"})
        with self.assertRaises(ValueError):
            compare(a, b, self.root / "diff")


class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.site = self.root / "site"
        self.site.mkdir()
        self.file = self.site / "index.html"
        self.file.write_text("<main>Before</main>\n")
        self.draft = self.root / "draft.html"
        self.draft.write_text("<main>Clear answer with evidence</main>\n")
        self.plan = self.root / "change"
        self.store = LocalStore(self.site)

    def tearDown(self):
        self.tmp.cleanup()

    def make_plan(self):
        return stage(self.store, "index.html", self.draft, self.plan)["plan_sha256"]

    def test_stage_changes_nothing_then_apply_and_rollback_exact_bytes(self):
        before = self.file.read_bytes()
        checksum = self.make_plan()
        self.assertEqual(self.file.read_bytes(), before)
        self.assertIn("+<main>Clear", (self.plan / "review.diff").read_text())
        self.assertEqual(apply_change(self.store, self.plan, checksum)["status"], "applied")
        self.assertEqual(self.file.read_bytes(), self.draft.read_bytes())
        self.assertEqual(
            apply_change(self.store, self.plan, checksum, True)["status"], "rolled_back"
        )
        self.assertEqual(self.file.read_bytes(), before)

    def test_concurrent_site_change_prevents_apply(self):
        checksum = self.make_plan()
        self.file.write_text("Someone else's edit")
        with self.assertRaises(ValueError):
            apply_change(self.store, self.plan, checksum)
        self.assertEqual(self.file.read_text(), "Someone else's edit")

    def test_tampered_draft_and_plan_are_rejected(self):
        checksum = self.make_plan()
        (self.plan / "after.txt").write_text("Tampered")
        with self.assertRaises(ValueError):
            apply_change(self.store, self.plan, checksum)
        with self.assertRaises(ValueError):
            apply_change(self.store, self.plan, "0" * 64)

    def test_wrong_target_is_rejected(self):
        checksum = self.make_plan()
        other = self.root / "other"
        other.mkdir()
        (other / "index.html").write_text(self.file.read_text())
        with self.assertRaises(ValueError):
            apply_change(LocalStore(other), self.plan, checksum)

    def test_rollback_will_not_overwrite_later_edit(self):
        checksum = self.make_plan()
        apply_change(self.store, self.plan, checksum)
        self.file.write_text("Later edit")
        with self.assertRaises(ValueError):
            apply_change(self.store, self.plan, checksum, True)
        self.assertEqual(self.file.read_text(), "Later edit")

    def test_traversal_symlinks_and_webroot_backups_are_rejected(self):
        for path in ("../draft.html", "/index.html", ".env", "x/../../index.html", "wp-config.php"):
            with self.assertRaises(ValueError):
                stage(self.store, path, self.draft, self.plan)
        (self.site / "linked.html").symlink_to(self.draft)
        with self.assertRaises(ValueError):
            stage(self.store, "linked.html", self.draft, self.plan)
        with self.assertRaises(ValueError):
            stage(self.store, "index.html", self.draft, self.site / "change")

    def test_failed_atomic_replace_retains_original_and_receipt(self):
        before = self.file.read_bytes()
        checksum = self.make_plan()
        original_replace = os.replace

        def fail_target(source, target):
            if Path(target).resolve() == self.file.resolve():
                raise OSError("write failure")
            return original_replace(source, target)

        with patch("beyondseo.publishing.os.replace", side_effect=fail_target):
            with self.assertRaises(ValueError):
                apply_change(self.store, self.plan, checksum)
        self.assertEqual(self.file.read_bytes(), before)
        self.assertEqual(
            json.loads((self.plan / "receipt.json").read_text())["status"], "needs_inspection"
        )
        self.assertFalse(list(self.site.glob(".beyondseo-*")))

    def test_connection_profile_refuses_plaintext_secrets(self):
        with self.assertRaises(ValueError):
            RemoteStore(
                {"type": "ftps", "host": "example.com", "root": "/www", "password": "do-not-store"}
            )

    def test_remote_symlink_is_rejected(self):
        remote = RemoteStore.__new__(RemoteStore)
        remote.identity = {"root": "/www"}
        remote.sftp = Mock()
        remote.sftp.lstat.return_value.st_mode = 0o120777
        with self.assertRaises(ValueError):
            remote.path("index.html")

    def test_ftps_checks_upload_before_rename(self):
        remote = RemoteStore.__new__(RemoteStore)
        remote.identity = {"root": "/www"}
        remote.sftp = None
        remote.client = Mock()
        remote.client.mlsd.return_value = [("index.html", {"type": "file"})]
        remote.read = Mock(return_value=b"before")
        remote.client.retrbinary.side_effect = lambda command, callback: callback(b"corrupt")
        with self.assertRaises(ValueError):
            remote.replace("index.html", b"after", digest(b"before"))
        remote.client.rename.assert_not_called()
        remote.client.delete.assert_called_once()


class LoopIntegrationTests(CrawlerTests):
    def test_watch_makes_fresh_snapshots_and_comparison(self):
        sleep = Mock()
        state = watch(
            self.config("/a", max_pages=1, sitemaps=False),
            self.out,
            cycles=2,
            interval=60,
            quiet=True,
            sleep=sleep,
            selectors={"heading": "h1"},
        )
        self.assertEqual(state["status"], "completed")
        self.assertEqual(len(state["runs"]), 2)
        page = json.loads((self.out / "run-0002/pages.jsonl").read_text().splitlines()[0])
        self.assertEqual(page["data"]["custom"]["heading"], ["A"])
        sleep.assert_called_once_with(60)
        self.assertTrue((self.out / "run-0002/comparison.json").exists())
        self.assertTrue((self.out / "run-0001/readiness.md").exists())
        with self.assertRaises(ValueError):
            watch(self.config(), self.out, cycles=1)

    def test_watch_stops_after_two_empty_runs(self):
        state = watch(
            self.config("/missing", max_pages=1, sitemaps=False),
            self.out,
            cycles=4,
            interval=60,
            quiet=True,
            sleep=lambda _: None,
        )
        self.assertEqual(state["status"], "stopped_after_two_empty_runs")
        self.assertEqual(len(state["runs"]), 2)

    def test_backlink_source_records_observed_link_and_failed_access(self):
        csv_path = self.out / "sources.csv"
        with csv_path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["URL"])
            w.writerow([self.root + "/"])
            w.writerow([self.root + "/private"])
        result = check_sources(
            csv_path, "http://outside.invalid/", self.out / "checked", allow_private=True
        )
        self.assertEqual(result["observed_link_pages"], 1)
        self.assertEqual(result["unverified_pages"], 1)
        self.assertEqual(result["results"][0]["target_links"][0]["url"], "http://outside.invalid/")


def load_tests(loader, tests, pattern):
    suite = unittest.TestSuite()
    for cls in (ReviewTests, PublishingTests):
        suite.addTests(loader.loadTestsFromTestCase(cls))
    for name in LoopIntegrationTests.__dict__:
        if name.startswith("test_"):
            suite.addTest(LoopIntegrationTests(name))
    return suite
