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

    def test_update_preserves_local_runtime_at_original_path_and_in_backup(self):
        installer.install(self.source, self.dest)
        runtime = self.dest / ".venv"
        runtime.mkdir()
        (runtime / "pyvenv.cfg").write_text("existing runtime", encoding="utf-8")
        (self.source / "src/module.py").write_text("# changed", encoding="utf-8")
        result = installer.install(self.source, self.dest, update=True)
        self.assertTrue(result["runtime_preserved"])
        self.assertEqual((runtime / "pyvenv.cfg").read_text(), "existing runtime")
        backup = Path(result["backup"])
        self.assertEqual((backup / ".venv/pyvenv.cfg").read_text(), "existing runtime")

    def test_failed_runtime_preservation_rolls_back_entire_update(self):
        installer.install(self.source, self.dest)
        (self.dest / ".venv").mkdir()
        (self.dest / ".venv/pyvenv.cfg").write_text("keep", encoding="utf-8")
        (self.source / "src/module.py").write_text("# changed", encoding="utf-8")
        with patch.object(installer.shutil, "copytree", side_effect=OSError("runtime copy failed")):
            with self.assertRaisesRegex(OSError, "runtime copy failed"):
                installer.install(self.source, self.dest, update=True)
        self.assertEqual((self.dest / "src/module.py").read_text(), "# fixture")
        self.assertEqual((self.dest / ".venv/pyvenv.cfg").read_text(), "keep")

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
                self.assertEqual(len(bundle.namelist()), result["archive_files"])
                self.assertLessEqual(len(bundle.namelist()), result["max_upload_files"])
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

    def test_upload_limit_includes_receipt_and_fails_before_writing(self):
        with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
            from build_skill import build
            from validate_skill import validate

            source = self.root / "complete source"
            installer.install(ROOT, source)
            count = len(installer.bundle_files(source))
            for index in range(199 - count):
                (source / "docs" / f"extra-{index}.md").write_text("Resource", encoding="utf-8")
            self.assertEqual(validate(source)["archive_files"], 200)
            (source / "docs/one-too-many.md").write_text("Resource", encoding="utf-8")
            output = self.root / "oversized.zip"
            with self.assertRaisesRegex(ValueError, "201 files.*maximum 200"):
                build(source, output)
            self.assertFalse(output.exists())
            self.assertFalse(output.with_suffix(".zip.sha256").exists())

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

    def test_launcher_uses_installed_runtime_before_rejecting_old_system_python(self):
        spec = importlib.util.spec_from_file_location("skill_run", ROOT / "scripts/run.py")
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        runtime = self.root / "runtime"
        executable = runtime / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        executable.parent.mkdir(parents=True)
        executable.touch()
        with (
            patch.object(launcher.sys, "version_info", (3, 9, 6)),
            patch.object(launcher.sys, "argv", ["run.py", "--runtime", str(runtime), "doctor"]),
            patch.object(launcher.subprocess, "call", return_value=0) as run,
        ):
            self.assertEqual(launcher.main(), 0)
        self.assertEqual(run.call_args.args[0][0], str(executable))

    def test_old_runtime_still_cannot_run_native_engine(self):
        spec = importlib.util.spec_from_file_location("skill_run", ROOT / "scripts/run.py")
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        with (
            patch.object(launcher.sys, "version_info", (3, 9, 6)),
            patch.object(launcher.sys, "argv", ["run.py", "doctor"]),
            patch.object(launcher.Path, "is_file", return_value=False),
            patch.object(launcher.subprocess, "call") as run,
        ):
            self.assertEqual(launcher.main(), 2)
        run.assert_not_called()

    def test_builder_accepts_relative_output_outside_checkout(self):
        # A sibling stays on the source volume when Windows temp uses another drive.
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            archive = Path(directory) / "relative-upload.zip"
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
