#!/usr/bin/env python3
"""Copy a clean BeyondSEO skill folder to an explicit destination. No network or archives."""

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

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
ROOT_DIRS = {"src", "scripts", "references", "playbooks", "docs", "assets", "examples"}
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
            names[:] = sorted(
                n
                for n in names
                if n not in SKIP and not n.startswith(".") and not n.endswith(".egg-info")
            )
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


def host_destination(host, workspace=None, profile_home=None):
    """Resolve documented local roots without changing any host configuration."""
    if profile_home and host != "hermes":
        raise ValueError("--profile-home is for Hermes. Use --dest for a custom folder.")
    if workspace:
        roots = {
            "claude-code": ".claude/skills",
            "codex": ".agents/skills",
            "cursor": ".cursor/skills",
            "openclaw": "skills",
        }
        if host not in roots:
            raise ValueError("Use --profile-home for a Hermes profile, not --workspace.")
        return Path(workspace).expanduser().absolute() / roots[host] / "beyondseo"
    home = Path.home()
    if host == "claude-code":
        return home / ".claude/skills/beyondseo"
    if host == "codex":
        return home / ".agents/skills/beyondseo"
    if host == "cursor":
        return home / ".cursor/skills/beyondseo"
    if host == "openclaw":
        return (
            Path(os.getenv("OPENCLAW_STATE_DIR") or home / ".openclaw").expanduser()
            / "skills/beyondseo"
        )
    if host == "hermes":
        explicit = profile_home or os.getenv("HERMES_HOME")
        if explicit:
            return Path(explicit).expanduser().absolute() / "skills/beyondseo"
        base = (
            Path(os.getenv("LOCALAPPDATA") or home / "AppData/Local") / "hermes"
            if sys.platform == "win32"
            else home / ".hermes"
        )
        active = base / "active_profile"
        if active.is_file():
            profile = active.read_text(encoding="utf-8").strip()
            if profile and profile != "default":
                raise ValueError(
                    "Hermes has a named active profile. Supply --profile-home with that profile's "
                    "directory, or run this command from its terminal with HERMES_HOME set."
                )
        return base / "skills/beyondseo"
    raise ValueError("Choose claude-code, codex, cursor, hermes or openclaw, or use --dest.")


def shell_command(arguments):
    values = [str(a) for a in arguments]
    if os.name == "nt":
        # PowerShell needs the call operator for a quoted executable path.
        # Literal quotes also preserve spaces and dollar signs in user paths.
        return "& " + " ".join("'" + value.replace("'", "''") + "'" for value in values)
    return shlex.join(values)


def install(source, destination, dry_run=False, update=False):
    source = source.resolve()
    destination = destination.expanduser().absolute()
    # Check before resolving so even a dangling destination symlink is rejected.
    if destination.is_symlink():
        raise ValueError("Destination already exists as a symlink. Choose a regular skill folder.")
    resolved = destination.resolve()
    if resolved == source or source in resolved.parents:
        raise ValueError("Choose a destination outside the source folder.")
    files = bundle_files(source)
    manifest = {
        p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files
    }
    result = {"destination": str(destination), "files": len(files), "dry_run": dry_run}
    backup = None
    if destination.exists():
        receipt = destination / "beyondseo-install.json"
        if not receipt.is_file():
            raise ValueError(
                "Destination already exists without an installation receipt. Preserve it and choose a new folder."
            )
        receipt_data = json.loads(receipt.read_text(encoding="utf-8"))
        old = receipt_data.get("files_sha256", {}) if isinstance(receipt_data, dict) else {}
        if not old or not isinstance(old, dict):
            raise ValueError(
                "Existing installation receipt is invalid. Preserve the folder before reinstalling."
            )
        if not all(isinstance(name, str) for name in old):
            raise ValueError("Existing installation receipt has invalid paths.")
        if os.name == "nt":
            old = {name.replace("\\", "/"): digest for name, digest in old.items()}
        for name, digest in old.items():
            path = destination / name
            if (
                Path(name).is_absolute()
                or ".." in Path(name).parts
                or "\\" in name
                or not path.resolve().is_relative_to(destination.resolve())
                or path.is_symlink()
                or not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != digest
            ):
                raise ValueError(
                    "Existing installation has changed files. Preserve your edits before updating."
                )
        if old == manifest:
            result["status"] = "already installed"
            return result
        if not update:
            raise ValueError(
                "Destination already exists with a different version. Use --update to keep a backup and replace it."
            )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
        backup = destination.parent.parent / "beyondseo-backups" / stamp / destination.name
        result["backup"] = str(backup)
    if dry_run:
        return result
    if backup:
        backup.parent.mkdir(parents=True, exist_ok=False)
        destination.rename(backup)
    created = False
    try:
        destination.mkdir(parents=True, exist_ok=False)
        created = True
        for path in files:
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            if (
                hashlib.sha256(target.read_bytes()).hexdigest()
                != manifest[path.relative_to(source).as_posix()]
            ):
                raise ValueError(
                    "Source changed during installation. Retry from a stable checkout."
                )
        (destination / "beyondseo-install.json").write_text(
            json.dumps({"files_sha256": manifest}, indent=2) + "\n", encoding="utf-8"
        )
        # Keep a local runtime at the same absolute path so its launchers remain
        # valid. Copy it from the backup; do not consume the rollback copy or
        # follow a runtime-directory symlink into an external environment.
        previous_runtime = backup / ".venv" if backup else None
        if previous_runtime and previous_runtime.is_dir() and not previous_runtime.is_symlink():
            shutil.copytree(previous_runtime, destination / ".venv", symlinks=True)
            result["runtime_preserved"] = True
    except Exception:
        # Only this invocation's newly created directory can reach this cleanup.
        if created:
            shutil.rmtree(destination)
        if backup and not destination.exists():
            backup.rename(destination)
        raise
    result["status"] = "updated" if backup else "installed"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--dest", type=Path, help="Exact skill folder to create.")
    target.add_argument("--host", choices=["claude-code", "codex", "cursor", "hermes", "openclaw"])
    parser.add_argument("--workspace", type=Path, help="Project/workspace root for a local host.")
    parser.add_argument("--profile-home", type=Path, help="Exact Hermes profile directory.")
    parser.add_argument(
        "--update",
        action="store_true",
        help="Back up an unmodified prior installation before replacing it.",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Also install Python dependencies and optional Chromium.",
    )
    parser.add_argument("--http-only", action="store_true", help="With --setup, skip Chromium.")
    parser.add_argument(
        "--runtime", type=Path, help="With --setup, use a host-approved external virtualenv folder."
    )
    parser.add_argument("--dry-run", action="store_true", help="Check and describe; write nothing.")
    args = parser.parse_args()
    if args.setup and sys.version_info < (3, 10):
        parser.exit(
            2,
            "Crawler setup needs Python 3.10+. Run this command with Python 3.12 (py -3.12 on Windows).\n",
        )
    try:
        from validate_skill import validate

        if args.dest and (args.workspace or args.profile_home):
            raise ValueError("Use --workspace / --profile-home with --host, or use --dest alone.")
        if (args.http_only or args.runtime) and not args.setup:
            raise ValueError("--http-only and --runtime require --setup.")
        source = Path(__file__).resolve().parents[1]
        validate(source)
        destination = args.dest or host_destination(args.host, args.workspace, args.profile_home)
        if destination.name != "beyondseo":
            raise ValueError("Name the destination folder beyondseo so it matches SKILL.md.")
        result = install(source, destination, args.dry_run, args.update)
    except (OSError, ValueError) as error:
        parser.exit(2, f"Installation stopped: {error}\n")
    print(json.dumps(result, indent=2))
    if not args.dry_run:
        destination = Path(result["destination"])
        command = [sys.executable, str(destination / "scripts/setup.py")]
        if args.http_only:
            command.append("--http-only")
        if args.runtime:
            command.extend(["--venv", str(args.runtime.expanduser().absolute())])
        if args.setup:
            try:
                completed = subprocess.run(command, check=False)
            except OSError as error:
                print(
                    f"Skill files are installed; runtime setup could not start: {error}",
                    file=sys.stderr,
                )
                return 1
            if completed.returncode:
                print(
                    "Skill files are installed. Runtime setup needs attention; see the error above.",
                    file=sys.stderr,
                )
                return completed.returncode
        else:
            if result.get("runtime_preserved"):
                print("Existing local runtime preserved. Run scripts/run.py doctor to check it.")
            print("Prepare or refresh crawler dependencies when needed:\n" + shell_command(command))
        print("Open a new assistant session and check that BeyondSEO appears in its skill list.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
