#!/usr/bin/env python3
"""Set up a local BeyondSEO environment from this source checkout."""

import argparse
import json
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--http-only", action="store_true", help="Skip the optional browser.")
    parser.add_argument("--dev", action="store_true", help="Install development tools too.")
    parser.add_argument(
        "--venv",
        type=Path,
        help="Host-approved writable/executable runtime folder; default: .venv inside the skill.",
    )
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        print("BeyondSEO needs Python 3.10 or newer. Python 3.12 is recommended.", file=sys.stderr)
        return 2
    root = Path(__file__).resolve().parents[1]
    env = args.venv.expanduser().absolute() if args.venv else root / ".venv"
    if env.is_symlink() or (env.exists() and not (env / "pyvenv.cfg").is_file()):
        print(
            "Choose a new virtualenv folder or an existing Python virtualenv, not an unrelated directory.",
            file=sys.stderr,
        )
        return 2
    if env == root or env in root.parents:
        print(
            "The runtime must be a dedicated folder, not the skill or its parent.", file=sys.stderr
        )
        return 2
    if args.venv and env.resolve().is_relative_to(root.resolve()):
        print(
            "Use --venv for a folder outside the skill; omit it for the default .venv.",
            file=sys.stderr,
        )
        return 2
    print("Preparing", env, flush=True)
    venv.EnvBuilder(with_pip=True).create(env)
    bindir = env / ("Scripts" if sys.platform == "win32" else "bin")
    python = bindir / ("python.exe" if sys.platform == "win32" else "python")
    extras = ([] if args.http_only else ["browser"]) + (["dev"] if args.dev else [])
    suffix = "[" + ",".join(extras) + "]" if extras else ""
    # Hosted skill folders may be read-only. Build the wheel from a clean temporary
    # source copy in the chosen runtime; never write build files into a mounted skill.
    if args.venv:
        from install_skill import install

        with tempfile.TemporaryDirectory(prefix="beyondseo-build-", dir=env) as scratch:
            copy = Path(scratch) / "beyondseo"
            install(root, copy)
            subprocess.run([str(python), "-m", "pip", "install", str(copy) + suffix], check=True)
    else:
        subprocess.run([str(python), "-m", "pip", "install", "-e", str(root) + suffix], check=True)
    if not args.http_only:
        subprocess.run([str(python), "-m", "playwright", "install", "chromium"], check=True)
    # Use the entry point through Python: executable-bit restrictions on scripts
    # are distinct from restrictions on the selected Python runtime itself.
    checked = subprocess.run(
        [str(python), str(root / "scripts/run.py"), "--runtime", str(env), "doctor"],
        capture_output=True,
        text=True,
    )
    print(checked.stdout, end="")
    if checked.stderr:
        print(checked.stderr, file=sys.stderr, end="")
    try:
        readiness = json.loads(checked.stdout)
    except ValueError:
        print("Runtime check did not return valid diagnostics.", file=sys.stderr)
        return 1
    if not readiness.get("http_ready") or (
        not args.http_only and not readiness.get("browser_ready")
    ):
        print(
            "Dependencies were installed, but the requested runtime is not ready. See docs/setup.md.",
            file=sys.stderr,
        )
        return 1
    from install_skill import shell_command

    command = [sys.executable, str(root / "scripts/run.py")]
    if args.venv:
        command.extend(["--runtime", str(env)])
    print("\nCrawler ready for " + ("HTTP mode." if args.http_only else "HTTP and browser mode."))
    print("Check again: " + shell_command([*command, "doctor"]))
    print("Skill registration is separate; confirm BeyondSEO in your assistant's skill list.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        print(
            "Setup stopped at a failed command. Resolve the error above and run setup again.",
            file=sys.stderr,
        )
        raise SystemExit(error.returncode)
    except OSError as error:
        print(f"Runtime setup could not proceed: {error}", file=sys.stderr)
        print(
            "For a permission error, choose a host-approved execution folder with --venv. Do not change the host's security policy.",
            file=sys.stderr,
        )
        raise SystemExit(2)
