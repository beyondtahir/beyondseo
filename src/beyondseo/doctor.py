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
                try:
                    page = browser.new_page()
                    page.set_content(
                        "<main id='probe'>initial</main><script>document.querySelector('#probe').textContent='rendered'</script>"
                    )
                    if page.locator("#probe").inner_text() != "rendered":
                        raise RuntimeError("Local JavaScript probe did not execute")
                finally:
                    browser.close()
            result["chromium"] = "ready"
            browser_failure = None
        except Exception as exc:
            error = type(exc).__name__ + ": " + str(exc)
            result["chromium"] = "unavailable"
            browser_failure = failure_detail(error, context="execution")
    result["http_ready"] = bool(result["packages"]["beautifulsoup4"])
    result["http_ready_meaning"] = (
        "Legacy dependency-availability flag only; see checks.target_reachable for actual access."
    )
    result["runtime_checks"] = {
        "python": {
            "status": "PASS" if sys.version_info >= (3, 10) else "FAIL",
            "evidence": sys.version,
            "blocks_crawling": sys.version_info < (3, 10),
        },
        "html_parser": {
            "status": "PASS" if result["http_ready"] else "FAIL",
            "evidence": result["packages"]["beautifulsoup4"],
            "blocks_crawling": not result["http_ready"],
        },
        "javascript_probe": {
            "status": "PASS" if result["chromium"] == "ready" else "BLOCKED",
            "evidence": "Local inline-script DOM mutation verified."
            if result["chromium"] == "ready"
            else browser_failure,
            "blocks_crawling": False,
            "blocks": "JavaScript rendering only",
        },
    }
    result["browser_ready"] = result["chromium"] == "ready"
    result["pdf_ready"] = bool(result["packages"]["reportlab"])
    result["installed_browsers"] = installed_browsers()
    result["checks"] = {
        "skill_installed": {
            "status": "unknown",
            "evidence": "Python cannot confirm registration in the host skill list. Ask the host to list its installed skills.",
        },
        "native_engine": {
            "status": "dependencies_present" if result["http_ready"] else "missing_dependency",
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
    """Only explicit target/query probes make network requests; preserve legacy fields."""
    result = environment_report()
    launcher = Path(__file__).resolve().parents[2] / "scripts/run.py"
    command = (
        [sys.executable, str(launcher), "doctor"]
        if launcher.is_file()
        else [sys.executable, "-m", "beyondseo", "doctor"]
    )
    if target:
        command.extend(["--target", target])
    if query:
        command.extend(["--query", query])
    if out:
        command.extend(["--out", str(out)])
    result["command"] = command
    probes = result.setdefault("runtime_checks", {})
    for name in ("dns", "robots", "sitemap", "target_http", "target_render"):
        probes[name] = {
            "status": "NOT_TESTED",
            "blocks_crawling": False,
            "evidence": "Supply --target for a bounded live probe.",
        }
    probes["filesystem"] = {
        "status": "NOT_TESTED",
        "evidence": "Write/readback not yet attempted.",
        "blocks_crawling": False,
    }
    try:
        parent = Path(out) if out else Path(tempfile.gettempdir())
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="beyondseo-doctor-", dir=parent) as temporary:
            folder = Path(temporary)
            probe_file = folder / "write-probe"
            probe_file.write_text("probe", encoding="utf-8")
            if probe_file.read_text(encoding="utf-8") != "probe":
                raise OSError("Filesystem readback mismatch")
            probes["filesystem"] = {
                "status": "PASS",
                "evidence": "Private write/readback succeeded in " + str(parent),
                "blocks_crawling": False,
            }
            if target and result["http_ready"]:
                from .engine import Crawler
                from .evidence import capture_quality
                from .network import Config, addresses
                from .review import read_pages

                config = Config(
                    target,
                    max_pages=1,
                    max_sitemaps=3,
                    workers=1,
                    include_www=True,
                    render_mode="auto",
                    timeout=12,
                    retries=0,
                )
                try:
                    addresses(config.url)
                    probes["dns"] = {
                        "status": "PASS",
                        "evidence": "DNS resolved and public address validation passed.",
                        "blocks_crawling": False,
                    }
                except (OSError, ValueError) as exc:
                    probes["dns"] = {
                        "status": "BLOCKED",
                        "failure": failure_detail(str(exc)),
                        "evidence": str(exc),
                        "blocks_crawling": True,
                        "remediation": "Check this host's DNS/network access; do not alter security controls.",
                    }
                if probes["dns"]["status"] == "PASS":
                    crawler = Crawler(config, folder / "target")
                    try:
                        crawler.log = lambda _: None
                        summary = crawler.run()
                        decision = crawler.robots.decision(config.url)
                    finally:
                        crawler.close()
                    pages = read_pages(folder / "target")
                    page = pages[0] if pages else {}
                    detail = failure_detail(page.get("error"), status=page.get("status", 0))
                    result["checks"]["target_reachable"] = {
                        "status": "response_received" if not detail else detail["code"],
                        "url": config.url,
                        "http_status": page.get("status"),
                        "failure": detail,
                        "robots_decision": page.get("robots_decision"),
                    }
                    probes["target_http"] = {
                        "status": "PASS"
                        if not detail and 200 <= page.get("status", 0) < 300
                        else "BLOCKED",
                        "evidence": result["checks"]["target_reachable"],
                        "blocks_crawling": bool(detail),
                    }
                    robots = json.loads((folder / "target/robots.json").read_text())
                    probes["robots"] = {
                        "status": "PASS" if decision.get("allowed") else "BLOCKED",
                        "evidence": robots,
                        "decision": decision,
                        "blocks_crawling": not decision.get("allowed"),
                    }
                    maps = json.loads((folder / "target/sitemaps.json").read_text())
                    probes["sitemap"] = {
                        "status": "PASS" if any(m.get("kind") for m in maps["fetches"]) else "WARN",
                        "evidence": maps["fetches"],
                        "blocks_crawling": False,
                        "note": "Discovery only; sitemap member responses require the audit page budget.",
                    }
                    quality = capture_quality(page)
                    render = page.get("rendered") or {}
                    probes["target_render"] = {
                        "status": ("PASS" if quality["absence_supported"] else "WARN")
                        if render.get("data")
                        else ("BLOCKED" if render.get("error") else "NOT_TESTED"),
                        "evidence": {
                            "readiness": render.get("readiness"),
                            "error": render.get("error"),
                            "limits": quality["limits"],
                        },
                        "blocks_crawling": False,
                        "note": "Auto mode renders only when needed; HTTP evidence remains available.",
                    }
                    result["target_coverage"] = summary.get("coverage")
                else:
                    result["checks"]["target_reachable"] = {
                        "status": "blocked",
                        "failure": probes["dns"],
                    }
            if query and result["http_ready"]:
                from .discovery import discover

                found = discover([{"query": query}], folder / "search", max_requests=6, seconds=40)
                result["checks"]["search_discovery"] = {
                    "status": "available" if found["search_available"] else "unavailable",
                    "attempts": found["attempts"],
                    "native_requests": found["native_requests"],
                }
    except (OSError, ValueError) as exc:
        if probes["filesystem"]["status"] == "NOT_TESTED":
            probes["filesystem"] = {
                "status": "BLOCKED",
                "evidence": str(exc),
                "blocks_crawling": True,
            }
        probes["execution"] = {
            "status": "BLOCKED",
            "evidence": type(exc).__name__ + ": " + str(exc),
            "failure": failure_detail(str(exc), context="execution"),
            "blocks_crawling": True,
            "remediation": "Use a writable host-approved output folder and inspect the recorded error. Do not disable permission checks.",
        }
    for check in probes.values():
        check["command"] = command
        if check["status"] in ("FAIL", "BLOCKED", "WARN"):
            check.setdefault(
                "remediation",
                "Inspect the recorded evidence and retry only the affected check after resolving its cause; unknown causes remain unknown.",
            )
    failed = any(
        c.get("blocks_crawling") and c["status"] in ("FAIL", "BLOCKED") for c in probes.values()
    )
    result["status"] = (
        "BLOCKED"
        if failed
        else (
            "WARN"
            if any(c["status"] in ("WARN", "BLOCKED", "FAIL") for c in probes.values())
            else "PASS"
        )
    )
    result["scope_note"] = (
        "PASS applies only to executed checks. NOT_TESTED is neither passing nor blocked. No target means no website/network readiness claim."
    )
    if out:
        try:
            (Path(out) / "doctor.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        except OSError as exc:
            result["output_error"] = str(exc)
            result["status"] = "BLOCKED"
    print(json.dumps(result, indent=2))
    return (
        1
        if result["status"] == "BLOCKED" or not result["http_ready"] or not result["browser_ready"]
        else 0
    )
