"""Report installation, runtime and optional network probes separately."""

import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .diagnostics import failure_detail


def installed_browsers():
    """Filesystem/PATH detection only; presence does not grant host UI control."""
    found = {}
    paths = {
        "chrome": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
        "edge": ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"],
        "firefox": ["/Applications/Firefox.app/Contents/MacOS/firefox"],
    }
    for browser, relative in [
        ("chrome", "Google/Chrome/Application/chrome.exe"),
        ("edge", "Microsoft/Edge/Application/msedge.exe"),
    ]:
        for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            if os.getenv(variable):
                paths[browser].append(str(Path(os.environ[variable]) / relative))
    for browser, commands in {
        "chrome": ["google-chrome", "google-chrome-stable"],
        "edge": ["microsoft-edge"],
        "chromium": ["chromium", "chromium-browser"],
        "firefox": ["firefox"],
    }.items():
        options = paths.get(browser, []) + [shutil.which(command) for command in commands]
        match = next((path for path in options if path and Path(path).is_file()), None)
        if match:
            found[browser] = match
    return {
        "detected": found,
        "host_control": "not_observed_by_cli",
        "note": "Ask the host to inspect its browser tools and test an allowed navigation. An installed browser is not proof of automation access.",
    }


def prepare_browser():
    """Explicit, idempotent setup in the selected virtual environment."""
    before = environment_report()
    if before["browser_ready"]:
        return {"status": "already_ready", "changed": False, "checks": before}
    failure = before["checks"]["browser_runtime"]["failure"]
    if failure["code"] not in ("missing_dependency", "browser_runtime_missing"):
        return {
            "status": "blocked",
            "changed": False,
            "failure": failure,
            "note": "Setup cannot repair an execution or policy denial.",
        }
    if sys.prefix == sys.base_prefix:
        return {
            "status": "runtime_required",
            "changed": False,
            "remediation": "Use scripts/setup.py --venv <approved-runtime>, then scripts/run.py --runtime <approved-runtime> browser-setup.",
        }
    commands = []
    if not before["packages"]["playwright"]:
        commands.append([sys.executable, "-m", "pip", "install", "playwright>=1.48,<2"])
    commands.append([sys.executable, "-m", "playwright", "install", "chromium"])
    for command in commands:
        try:
            run = subprocess.run(command, capture_output=True, text=True, timeout=180)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {
                "status": "setup_failed",
                "command": command,
                "failure": failure_detail(
                    type(exc).__name__ + ": " + str(exc), context="execution"
                ),
            }
        if run.returncode:
            return {
                "status": "setup_failed",
                "command": command,
                "exit_code": run.returncode,
                "failure": failure_detail((run.stderr or run.stdout)[-4000:], context="execution"),
            }
    after = environment_report()
    return {
        "status": "ready" if after["browser_ready"] else "setup_incomplete",
        "changed": True,
        "checks": after,
    }


def environment_report():
    result = {"python": platform.python_version(), "packages": {}, "chromium": "not installed"}
    for package in ("beautifulsoup4", "colorama", "playwright", "reportlab"):
        try:
            result["packages"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result["packages"][package] = None
    browser_failure = {
        "code": "missing_dependency",
        "evidence": "Playwright package not installed.",
    }
    if result["packages"]["playwright"]:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                browser.close()
            result["chromium"] = "ready"
            browser_failure = None
        except Exception as exc:
            error = type(exc).__name__ + ": " + str(exc)
            result["chromium"] = "unavailable"
            browser_failure = failure_detail(error, context="execution")
    result["http_ready"] = bool(result["packages"]["beautifulsoup4"])
    result["browser_ready"] = result["chromium"] == "ready"
    result["pdf_ready"] = bool(result["packages"]["reportlab"])
    result["installed_browsers"] = installed_browsers()
    result["checks"] = {
        "skill_installed": {
            "status": "unknown",
            "evidence": "Python cannot confirm registration in the host skill list. Ask the host to list its installed skills.",
        },
        "native_engine": {
            "status": "ready" if result["http_ready"] else "missing_dependency",
            "evidence": "Python executed; beautifulsoup4 package availability checked.",
        },
        "browser_runtime": {
            "status": "ready" if result["browser_ready"] else browser_failure["code"],
            "failure": browser_failure,
        },
        "target_reachable": {"status": "not_tested"},
        "report_export": {
            "html": "ready",
            "pdf": "dependency_present" if result["pdf_ready"] else "missing_dependency",
            "evidence": "Package availability only; run present on a fictional input to verify actual rendering.",
            "remediation": None
            if result["pdf_ready"]
            else "Run scripts/setup.py or install reportlab>=4.2,<5 in the selected runtime. HTML export remains available.",
        },
        "search_discovery": {
            "status": "not_tested",
            "host_tools": "Host search availability is separate from Python/network access.",
        },
        "source_page_verification": {
            "status": "runtime_ready" if result["http_ready"] else "unavailable",
            "evidence": "Each source's access must be checked; target reachability does not establish source reachability.",
        },
    }
    remediation = {
        "missing_dependency": "In this runtime: python -m pip install -e '.[browser]' (from the BeyondSEO repository).",
        "browser_runtime_missing": "In this runtime: python -m playwright install chromium",
        "execution_denied": "Ask the host to authorize this specific Python/browser executable in an approved execution directory. Installing Chromium will not fix an execution denial.",
        "unknown": "Inspect the recorded browser exception; no cause-specific fix is established.",
    }
    if browser_failure:
        result["checks"]["browser_runtime"]["remediation"] = remediation.get(
            browser_failure["code"],
            "Resolve the exact recorded failure; do not disable security controls.",
        )
    return result


def check_environment(target=None, query=None, out=None):
    result = environment_report()
    if result["http_ready"] and (target or query):
        from .discovery import discover
        from .engine import Crawler
        from .network import Config
        from .review import read_pages

        with tempfile.TemporaryDirectory(prefix="beyondseo-doctor-") as temporary:
            folder = Path(out or temporary)
            if target:
                crawler = Crawler(
                    Config(
                        target,
                        max_pages=1,
                        workers=1,
                        sitemaps=False,
                        render_mode="http",
                        timeout=12,
                        retries=0,
                    ),
                    folder / "target",
                )
                try:
                    crawler.log = lambda _: None
                    crawler.run()
                finally:
                    crawler.close()
                page = read_pages(folder / "target")[0]
                detail = failure_detail(page.get("error"), status=page["status"])
                result["checks"]["target_reachable"] = {
                    "status": "response_received" if not detail else detail["code"],
                    "url": page["url"],
                    "http_status": page["status"],
                    "failure": detail,
                    "access": page.get("access"),
                    "robots_decision": page.get("robots_decision"),
                }
            if query:
                found = discover([{"query": query}], folder / "search", max_requests=6, seconds=40)
                result["checks"]["search_discovery"] = {
                    "status": "available" if found["search_available"] else "unavailable",
                    "attempts": found["attempts"],
                    "native_requests": found["native_requests"],
                }
    if out:
        Path(out).mkdir(parents=True, exist_ok=True)
        (Path(out) / "doctor.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["http_ready"] and result["browser_ready"] else 1
