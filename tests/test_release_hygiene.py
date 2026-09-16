import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_check", ROOT / "scripts/check_release.py")
release_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_check)


class ReleaseHygieneTests(unittest.TestCase):
    def test_live_browser_artifacts_fail_even_when_renamed_or_nested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = [
                "docs/host-validation-fixture/notes.txt",
                "examples/Captures/site.txt",
                "assets/network.HAR",
                "browser-discovery.json",
                "debug.trace.zip",
            ]
            for name in names:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fictional test content")
            report = release_check.check_files(root, names)
            self.assertEqual(report["status"], "failed")
            self.assertEqual(len(report["findings"]), len(names))

    def test_clean_tree_does_not_hide_private_identifier_in_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def git(*args):
                subprocess.run(["git", "-C", tmp, *args], check=True, capture_output=True)

            git("init")
            path = root / "guide.md"
            path.write_text("Old private client: customer-only.test")
            git("add", "guide.md")
            git(
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.com",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-m",
                "fixture",
            )
            path.write_text("Use example.com")
            self.assertEqual(
                release_check.check_files(root, ["guide.md"], ["customer-only.test"])["status"],
                "passed",
            )
            history = release_check.check_history(root, ["customer-only.test"])
            self.assertEqual(history["status"], "failed")
            self.assertEqual(history["commits_checked"], 1)
            self.assertNotIn("customer-only.test", str(history))
            self.assertTrue(history["matching_files"][0].endswith(":guide.md"))

    def test_client_identifiers_and_capture_files_fail_without_echoing_sensitive_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.md").write_text("Private customer: hidden-customer.test")
            (root / "pages.jsonl").write_text("{}")
            result = release_check.check_files(
                root, ["notes.md", "pages.jsonl"], ["hidden-customer.test"]
            )
            self.assertEqual(result["status"], "failed")
            self.assertEqual(len(result["findings"]), 2)
            self.assertNotIn("hidden-customer.test", str(result))

    def test_generic_documentation_and_fictional_fixture_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "guide.md").write_text("Use https://example.com and /path/to/runtime.")
            self.assertEqual(release_check.check_files(root, ["guide.md"])["status"], "passed")
