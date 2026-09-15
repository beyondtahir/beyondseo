import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("skill_install", ROOT / "scripts/install_skill.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class PortabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="beyondseo portable ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source checkout"
        self.source.mkdir()
        for name in ("SKILL.md", "pyproject.toml", "LICENSE"):
            (self.source / name).write_text("fixture", encoding="utf-8")
        (self.source / "src").mkdir()
        (self.source / "src" / "module.py").write_text("# fixture", encoding="utf-8")
        self.dest = self.root / "installed skill"

    def test_clean_copy_preserves_source_and_skips_runtime_and_client_runs(self):
        for directory in (
            ".venv",
            "runs",
            "tests",
            "src/__pycache__",
            "src/example.egg-info",
            "docs/.private",
        ):
            target = self.source / directory
            target.mkdir(parents=True)
            (target / "private.txt").write_text("must not copy", encoding="utf-8")
        (self.source / ".env").write_text("local only", encoding="utf-8")
        result = installer.install(self.source, self.dest)
        self.assertEqual(result["files"], 4)
        self.assertEqual((self.dest / "src/module.py").read_bytes(), b"# fixture")
        self.assertTrue((self.source / "runs/private.txt").exists())
        self.assertFalse((self.dest / "runs").exists())
        manifest = json.loads((self.dest / "beyondseo-install.json").read_text())
        self.assertEqual(len(manifest["files_sha256"]), 4)
        self.assertFalse((self.dest / ".env").exists())
        self.assertFalse((self.dest / "tests").exists())
        self.assertFalse((self.dest / "docs/.private").exists())

    def test_dry_run_does_not_create_parent_directories(self):
        target = self.root / "absent parent" / "new skill"
        self.assertTrue(installer.install(self.source, target, True)["dry_run"])
        self.assertFalse(target.parent.exists())

    def test_existing_installation_is_preserved(self):
        self.dest.mkdir()
        (self.dest / "notes.txt").write_text("keep me", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "already exists"):
            installer.install(self.source, self.dest)
        self.assertEqual((self.dest / "notes.txt").read_text(), "keep me")

    def test_nested_destination_is_refused(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            installer.install(self.source, self.source / "nested")
        self.assertFalse((self.source / "nested").exists())

    def test_symlinked_source_cannot_copy_external_files(self):
        external = self.root / "private.txt"
        external.write_text("private", encoding="utf-8")
        try:
            (self.source / "src/link.txt").symlink_to(external)
        except OSError:
            self.skipTest("Symlink creation unavailable on this host")
        with self.assertRaisesRegex(ValueError, "regular file"):
            installer.install(self.source, self.dest)
        self.assertFalse(self.dest.exists())

    def test_required_source_files_are_checked_before_copy(self):
        (self.source / "LICENSE").unlink()
        with self.assertRaisesRegex(ValueError, "required"):
            installer.install(self.source, self.dest)
        self.assertFalse(self.dest.exists())

    def test_repeat_install_and_update_preserve_previous_folder(self):
        installer.install(self.source, self.dest)
        self.assertEqual(installer.install(self.source, self.dest)["status"], "already installed")
        (self.dest / "personal-notes.txt").write_text("keep", encoding="utf-8")
        (self.source / "src/module.py").write_text("# new version", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "--update"):
            installer.install(self.source, self.dest)
        result = installer.install(self.source, self.dest, update=True)
        backup = Path(result["backup"])
        self.assertEqual((backup / "personal-notes.txt").read_text(), "keep")
        self.assertEqual((backup / "src/module.py").read_text(), "# fixture")
        self.assertEqual((self.dest / "src/module.py").read_text(), "# new version")
        self.assertFalse(backup.is_relative_to(self.dest.parent))

    def test_changed_managed_file_is_not_overwritten(self):
        installer.install(self.source, self.dest)
        (self.dest / "src/module.py").write_text("# customized", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed files"):
            installer.install(self.source, self.dest, update=True)
        self.assertEqual((self.dest / "src/module.py").read_text(), "# customized")

    def test_failed_update_restores_previous_installation(self):
        installer.install(self.source, self.dest)
        (self.source / "src/module.py").write_text("# changed", encoding="utf-8")
        with patch.object(installer.shutil, "copy2", side_effect=OSError("copy failed")):
            with self.assertRaisesRegex(OSError, "copy failed"):
                installer.install(self.source, self.dest, update=True)
        self.assertEqual((self.dest / "src/module.py").read_text(), "# fixture")

    def test_host_roots_and_explicit_profiles(self):
        settings = {
            "HERMES_HOME": str(self.root / "profile"),
            "OPENCLAW_STATE_DIR": str(self.root / "state"),
        }
        with patch.object(installer.os, "getenv", side_effect=lambda key: settings.get(key)):
            self.assertEqual(
                installer.host_destination("hermes"), self.root / "profile/skills/beyondseo"
            )
            self.assertEqual(
                installer.host_destination("openclaw"), self.root / "state/skills/beyondseo"
            )
        self.assertEqual(
            installer.host_destination("claude-code", workspace=self.root),
            self.root / ".claude/skills/beyondseo",
        )
        self.assertEqual(
            installer.host_destination("codex", workspace=self.root),
            self.root / ".agents/skills/beyondseo",
        )
        self.assertEqual(
            installer.host_destination("openclaw", workspace=self.root),
            self.root / "skills/beyondseo",
        )
        with (
            patch.object(installer.Path, "home", return_value=self.root),
            patch.object(installer.os, "getenv", return_value=None),
            patch.object(installer.sys, "platform", "linux"),
        ):
            profile = self.root / ".hermes"
            profile.mkdir()
            (profile / "active_profile").write_text("research", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "named active profile"):
                installer.host_destination("hermes")

    def test_windows_hermes_home(self):
        with (
            patch.object(
                installer.os,
                "getenv",
                side_effect=lambda key: str(self.root) if key == "LOCALAPPDATA" else None,
            ),
            patch.object(installer.sys, "platform", "win32"),
        ):
            self.assertEqual(
                installer.host_destination("hermes"), self.root / "hermes/skills/beyondseo"
            )

    def test_upload_archive_contains_complete_named_bundle_and_no_dev_fixtures(self):
        with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
            from build_skill import build

            archive = self.root / "upload.zip"
            result = build(ROOT, archive)
            self.assertEqual(result["format_check"], "passed")
            self.assertEqual(result["host_safety_scan"], "not run")
            with zipfile.ZipFile(archive) as bundle:
                self.assertEqual({n.split("/")[0] for n in bundle.namelist()}, {"beyondseo"})
                self.assertIn("beyondseo/src/beyondseo/cli.py", bundle.namelist())
                self.assertIn(
                    "beyondseo/playbooks/backlink-system/posting-sites.json", bundle.namelist()
                )
                self.assertFalse(any(n.startswith("beyondseo/tests/") for n in bundle.namelist()))
                bundle.extractall(self.root / "unpacked")
            from validate_skill import validate

            self.assertEqual(validate(self.root / "unpacked/beyondseo")["format_check"], "passed")
            self.assertTrue(archive.with_suffix(".zip.sha256").is_file())
            with self.assertRaisesRegex(ValueError, "already exists"):
                build(ROOT, archive)

    def test_explicit_missing_runtime_does_not_fall_back_silently(self):
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/run.py"),
                "--runtime",
                str(self.root / "missing"),
                "doctor",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("No Python runtime", result.stderr)

    def test_builder_accepts_relative_output_outside_checkout(self):
        archive = self.root / "relative-upload.zip"
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/build_skill.py"),
                "--out",
                os.path.relpath(archive, ROOT),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(zipfile.is_zipfile(archive))

    def test_launcher_works_from_unrelated_working_directory(self):
        from beyondseo import __version__

        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/run.py"), "--version"],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "BeyondSEO " + __version__)

    @unittest.skipUnless(os.name == "nt", "PowerShell command acceptance runs on Windows")
    def test_powershell_follow_up_command_preserves_literal_arguments(self):
        shell = shutil.which("pwsh") or shutil.which("powershell")
        if not shell:
            self.skipTest("PowerShell unavailable")
        expected = "a space, a dollar $sign and an apostrophe '"
        command = installer.shell_command(
            [sys.executable, "-c", "import sys; print(sys.argv[1])", expected]
        )
        result = subprocess.run(
            [shell, "-NoProfile", "-Command", command], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), expected)

    def test_launcher_preserves_cli_error_exit_code(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/run.py"), "unknown-command"],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid choice", result.stderr)


if __name__ == "__main__":
    unittest.main()
