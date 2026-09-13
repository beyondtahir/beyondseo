"""Local setup checks; this command does not contact websites."""

import importlib.metadata
import json
import platform


def check_environment():
    result = {"python": platform.python_version(), "packages": {}, "chromium": "not installed"}
    for package in ("beautifulsoup4", "colorama", "playwright"):
        try:
            result["packages"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result["packages"][package] = None
    if result["packages"]["playwright"]:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                browser.close()
            result["chromium"] = "ready"
        except Exception:
            result["chromium"] = "unavailable; run python -m playwright install chromium"
    result["http_ready"] = bool(result["packages"]["beautifulsoup4"])
    result["browser_ready"] = result["chromium"] == "ready"
    print(json.dumps(result, indent=2))
    return 0 if result["http_ready"] and result["browser_ready"] else 1
