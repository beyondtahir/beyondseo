"""Check degraded setup, command boundaries and actual readiness reporting."""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_setup():
    spec = importlib.util.spec_from_file_location("beyondseo_setup_test", ROOT / "scripts/setup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SetupRecoveryTests(unittest.TestCase):
    def run_setup(
        self,
        arguments=(),
        browser_error=None,
        doctor_exit=1,
        doctor_timeout=False,
        reports_error=False,
    ):
        setup = load_setup()
        calls = []

        def run(command, **kwargs):
            calls.append((command, kwargs))
            if reports_error and any(str(item).endswith("[reports]") for item in command):
                raise subprocess.TimeoutExpired(command, 300)
            if command[1:5] == ["-m", "playwright", "install", "chromium"] and browser_error:
                raise browser_error
            if "doctor" in command:
                if doctor_timeout and "--no-browser" not in command:
                    raise subprocess.TimeoutExpired(command, 60)
                return subprocess.CompletedProcess(
                    command,
                    doctor_exit,
                    json.dumps(
                        {
                            "status": "WARN",
                            "http_ready": True,
                            "browser_ready": False,
                            "checks": {
                                "browser_runtime": {
                                    "failure": {
                                        "code": "browser_runtime_missing",
                                        "evidence": "fixture",
                                    }
                                }
                            },
                        }
                    ),
                    "",
                )
            return subprocess.CompletedProcess(command, 0, "", "")

        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch.object(setup.sys, "argv", ["setup.py", *arguments]),
            patch.object(setup.venv.EnvBuilder, "create"),
            patch.object(setup.subprocess, "run", side_effect=run),
            patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            code = setup.main()
        return code, stdout.getvalue(), stderr.getvalue(), calls

    def test_browser_download_failure_keeps_http_engine_usable(self):
        error = subprocess.CalledProcessError(1, ["python", "-m", "playwright"])
        code, stdout, stderr, calls = self.run_setup(browser_error=error)
        self.assertEqual(code, 0)
        self.assertIn("HTTP mode", stdout)
        self.assertNotIn("HTTP and browser mode", stdout)
        self.assertIn("Optional browser setup failed", stderr)
        self.assertTrue(any("doctor" in command for command, _ in calls))

    def test_strict_browser_request_fails_without_discarding_http_result(self):
        code, _, stderr, _ = self.run_setup(["--require-browser"])
        self.assertEqual(code, 1)
        self.assertIn("HTTP engine ready", stderr)

    def test_optional_browser_timeout_is_bounded_and_nonfatal_to_http(self):
        code, _, stderr, calls = self.run_setup(
            browser_error=subprocess.TimeoutExpired(["python", "-m", "playwright"], 180)
        )
        self.assertEqual(code, 0)
        self.assertIn("TimeoutExpired", stderr)
        self.assertTrue(all(kwargs.get("timeout") for _, kwargs in calls))

    def test_doctor_nonzero_cannot_become_setup_success(self):
        code, _, _, _ = self.run_setup(["--http-only"], doctor_exit=2)
        self.assertEqual(code, 1)

    def test_slow_optional_pdf_download_does_not_discard_core_engine(self):
        code, _, stderr, _ = self.run_setup(["--http-only"], reports_error=True)
        self.assertEqual(code, 0)
        self.assertIn("Optional reports setup failed", stderr)

    def test_hung_browser_diagnostic_falls_back_to_http_diagnostic(self):
        code, _, stderr, calls = self.run_setup(doctor_timeout=True)
        self.assertEqual(code, 0)
        self.assertIn("Browser diagnostic timed out", stderr)
        probes = [command for command, _ in calls if "doctor" in command]
        self.assertEqual(len(probes), 2)
        self.assertIn("--no-browser", probes[-1])

    def test_real_http_doctor_contract_without_browser(self):
        from beyondseo.doctor import check_environment

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = check_environment(check_browser=False)
        report = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(report["checks"]["browser_runtime"]["status"], "not_tested")
        self.assertEqual(report["runtime_checks"]["javascript_probe"]["status"], "NOT_TESTED")
        self.assertIsNone(report["checks"]["browser_runtime"]["failure"])

    def test_browser_presence_is_not_reported_as_control_permission(self):
        from beyondseo.doctor import installed_browsers

        with (
            patch("beyondseo.doctor.shutil.which", return_value=None),
            patch("beyondseo.doctor.Path.is_file", lambda p: "Brave Browser" in str(p)),
        ):
            report = installed_browsers()
        self.assertIn("brave", report["detected"])
        self.assertEqual(report["host_control"], "not_observed_by_cli")

    def test_execution_denial_is_detected_before_dependency_downloads(self):
        setup = load_setup()
        with (
            patch.object(setup.sys, "argv", ["setup.py"]),
            patch.object(setup.venv.EnvBuilder, "create"),
            patch.object(
                setup.subprocess, "run", side_effect=PermissionError("fixture denied")
            ) as run,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            with self.assertRaises(PermissionError):
                setup.main()
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][1], "-c")


if __name__ == "__main__":
    unittest.main()
