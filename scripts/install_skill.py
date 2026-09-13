#!/usr/bin/env python3
"""Copy a clean BeyondSEO skill folder to an explicit destination. No network or archives."""

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

ROOT_FILES = {
    "SKILL.md",
    "README.md",
    "pyproject.toml",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CITATION.cff",
    ".gitignore",
}
ROOT_DIRS = {"src", "scripts", "references", "playbooks", "docs", "assets", "examples", "tests"}
SKIP = {".venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".git"}


def bundle_files(source):
    files = []
    for entry in sorted(source.iterdir()):
        if entry.name not in ROOT_FILES | ROOT_DIRS:
            continue
        if entry.is_symlink():
            raise ValueError(f"Refusing a symlink in the bundle: {entry.name}")
        if entry.name in ROOT_FILES:
            if not entry.is_file():
                raise ValueError(f"Expected a file: {entry.name}")
            files.append(entry)
            continue
        for directory, names, filenames in os.walk(entry, followlinks=False):
            names[:] = sorted(n for n in names if n not in SKIP and not n.endswith(".egg-info"))
            for name in names:
                if (Path(directory) / name).is_symlink():
                    raise ValueError(f"Refusing a symlink in the bundle: {name}")
            for name in sorted(filenames):
                if name.startswith(".") or name.endswith((".pyc", ".pyo")):
                    continue
                path = Path(directory) / name
                if path.is_symlink() or not path.is_file():
                    raise ValueError(f"Expected a regular file: {path.relative_to(source)}")
                files.append(path)
    if not all((source / name) in files for name in ("SKILL.md", "pyproject.toml", "LICENSE")):
        raise ValueError("Source is missing required BeyondSEO files.")
    return files


def install(source, destination, dry_run=False):
    source = source.resolve()
    destination = destination.expanduser().absolute()
    # Check before resolving so even a dangling destination symlink is rejected.
    if destination.exists() or destination.is_symlink():
        raise ValueError("Destination already exists. Keep it as a backup and choose a new folder.")
    resolved = destination.resolve()
    if resolved == source or source in resolved.parents:
        raise ValueError("Choose a destination outside the source folder.")
    files = bundle_files(source)
    manifest = {
        str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files
    }
    result = {"destination": str(destination), "files": len(files), "dry_run": dry_run}
    if dry_run:
        return result
    destination.mkdir(parents=True, exist_ok=False)
    try:
        for path in files:
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            if (
                hashlib.sha256(target.read_bytes()).hexdigest()
                != manifest[str(path.relative_to(source))]
            ):
                raise ValueError(
                    "Source changed during installation. Retry from a stable checkout."
                )
        (destination / "beyondseo-install.json").write_text(
            json.dumps({"files_sha256": manifest}, indent=2) + "\n", encoding="utf-8"
        )
    except Exception:
        # Only this invocation's newly created directory can reach this cleanup.
        shutil.rmtree(destination)
        raise
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest", required=True, type=Path, help="Exact new skill folder to create."
    )
    parser.add_argument("--dry-run", action="store_true", help="Check and describe; write nothing.")
    args = parser.parse_args()
    try:
        result = install(Path(__file__).resolve().parents[1], args.dest, args.dry_run)
    except (OSError, ValueError) as error:
        parser.exit(2, f"Installation stopped: {error}\n")
    print(json.dumps(result, indent=2))
    if not args.dry_run:
        print("Next: run scripts/setup.py inside the installed folder, then scripts/run.py doctor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
