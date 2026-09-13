import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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
        for directory in (".venv", "runs", "src/__pycache__", "src/example.egg-info"):
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
