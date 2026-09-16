#!/usr/bin/env python3
"""Read-only release hygiene check. Does not stage, commit, zip or publish files."""

import argparse
import json
import re
import subprocess
from pathlib import Path

PRIVATE_DIRS = {
    "client-runs",
    "trial-runs",
    "validation-runs",
    "reports",
    "runs",
    "private",
    "work",
    ".venv",
    "acceptance-runs",
    "captures",
    "transcripts",
}
PRIVATE_PREFIXES = ("host-validation", "deep-research-validation", "acceptance-run-")
CAPTURES = {
    "pages.jsonl",
    "documents.jsonl",
    "backlinks.json",
    "discovery.json",
    "capabilities.json",
    "beyondseo-install.json",
    "storage-state.json",
    "browser-discovery.json",
    "discovery-evidence.json",
}


def check_files(root, files, denied=()):
    root = Path(root).resolve()
    findings = []
    for name in files:
        relative = Path(name)
        path = root / relative
        if not path.is_file():
            continue
        reasons = []
        if relative.is_absolute() or ".." in relative.parts or path.is_symlink():
            findings.append(
                {"file": relative.as_posix(), "reasons": ["nonportable or symlinked release path"]}
            )
            continue
        parts = [part.casefold() for part in relative.parts]
        if (
            set(parts) & PRIVATE_DIRS
            or any(part.startswith(PRIVATE_PREFIXES) for part in parts)
            or path.name.casefold() in CAPTURES
            or path.suffix.casefold() in (".sqlite", ".sqlite3", ".pem", ".key", ".har")
            or path.name.casefold().endswith(".trace.zip")
        ):
            reasons.append("runtime, credential or client capture artifact")
        if path.name.startswith(".env") and path.name != ".env.example":
            reasons.append("environment file")
        body = path.read_bytes()
        if b"\x00" not in body:
            text = body.decode("utf-8", "replace")
            if any(term.casefold() in text.casefold() for term in denied if term):
                reasons.append("matches a supplied private identifier")
            if re.search(r"/(?:Users|home)/[A-Za-z0-9_.-]+/", text) or re.search(
                r"[A-Za-z]:\\Users\\[^\\\s]+\\", text
            ):
                reasons.append("machine-specific home path")
        if reasons:
            findings.append({"file": relative.as_posix(), "reasons": reasons})
    return {
        "status": "failed" if findings else "passed",
        "files_checked": len(files),
        "findings": findings,
        "limits": "Heuristic file/content checks, not a guarantee against every secret or private artifact. Review the actual diff and outgoing commits before publishing.",
    }


def check_history(root, denied):
    commits = subprocess.check_output(
        ["git", "-C", str(root), "rev-list", "--all"], text=True
    ).splitlines()
    findings = set()
    for commit in commits:
        if not denied:
            break
        command = ["git", "-C", str(root), "grep", "-il", "-F"]
        for term in denied:
            command += ["-e", term]
        result = subprocess.run([*command, commit, "--"], capture_output=True, text=True)
        if result.returncode not in (0, 1):
            raise ValueError("Cannot inspect Git history: " + result.stderr)
        findings.update(result.stdout.splitlines())
    return {
        "status": "failed" if findings else "passed",
        "commits_checked": len(commits),
        "matching_files": sorted(findings),
        "scope": "Locally available Git refs; remote-only refs/assets/caches are not inspected.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--deny-text",
        action="append",
        default=[],
        help="Private client/domain identifier; kept out of public configuration.",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Also scan local Git history for supplied private identifiers; no history is changed.",
    )
    args = parser.parse_args()
    result = subprocess.run(
        [
            "git",
            "-C",
            str(args.root),
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        capture_output=True,
        check=True,
    )
    files = sorted(set(result.stdout.decode().split("\0")) - {""})
    report = check_files(args.root, files, args.deny_text)
    if args.history:
        if not args.deny_text:
            parser.error("--history requires at least one --deny-text identifier.")
        report["history"] = check_history(args.root, args.deny_text)
        if report["history"]["status"] == "failed":
            report["status"] = "failed"
    print(json.dumps(report, indent=2))
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
