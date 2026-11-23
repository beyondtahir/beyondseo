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
    parser.add_argument(
        "--require-browser",
        action="store_true",
        help="Return a failure if the optional browser cannot be prepared.",
    )
    parser.add_argument("--dev", action="store_true", help="Install development tools too.")
    parser.add_argument(
        "--venv",
        type=Path,
        help="Host-approved writable/executable runtime folder; default: .venv inside the skill.",
    )
    args = parser.parse_args()
    if args.http_only and args.require_browser:
        parser.error("--http-only and --require-browser cannot be used together")
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
    # Test execution before downloading packages. A writable mount may still be
    # non-executable; do not try to work around the host's execution policy.
    subprocess.run([str(python), "-c", "import sys; print(sys.executable)"], check=True, timeout=15)
    optional_errors = {}

    def install_project(project, editable=False):
        command = [str(python), "-m", "pip", "install"] + (["-e"] if editable else [])
        suffix = "[dev]" if args.dev else ""
        subprocess.run([*command, str(project) + suffix], check=True, timeout=300)
        # Optional downloads must not discard a usable base engine. Read extras
        # from this same local project so dependency constraints have one owner.
        for extra in ["reports"] + ([] if args.http_only else ["browser"]):
            try:
                subprocess.run([*command, f"{project}[{extra}]"], check=True, timeout=300)
                if extra == "browser":
                    subprocess.run(
                        [str(python), "-m", "playwright", "install", "chromium"],
                        check=True,
                        timeout=300,
                    )
            except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                optional_errors[extra] = type(error).__name__ + ": " + str(error)
                print(f"Optional {extra} setup failed: {optional_errors[extra]}", file=sys.stderr)
                print(
                    "Checking the HTTP engine separately; no security settings were changed.",
                    file=sys.stderr,
                )

    # Hosted skill folders may be read-only. Build the wheel from a clean temporary
    # source copy in the chosen runtime; never write build files into a mounted skill.
    if args.venv:
        from install_skill import install

        with tempfile.TemporaryDirectory(prefix="beyondseo-build-", dir=env) as scratch:
            copy = Path(scratch) / "beyondseo"
            install(root, copy)
            install_project(copy)
    else:
        install_project(root, editable=True)
    # Use the entry point through Python: executable-bit restrictions on scripts
    # are distinct from restrictions on the selected Python runtime itself.
    doctor_command = [str(python), str(root / "scripts/run.py"), "--runtime", str(env), "doctor"]
    if args.http_only or "browser" in optional_errors:
        doctor_command.append("--no-browser")
    try:
        checked = subprocess.run(doctor_command, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        optional_errors["browser"] = (
            "Browser diagnostic timed out after 60 seconds; rendering remains unverified."
        )
        print(
            "Browser diagnostic timed out; checking HTTP readiness without launching it.",
            file=sys.stderr,
        )
        checked = subprocess.run(
            [*doctor_command, "--no-browser"], capture_output=True, text=True, timeout=20
        )
    print(checked.stdout, end="")
    if checked.stderr:
        print(checked.stderr, file=sys.stderr, end="")
    try:
        readiness = json.loads(checked.stdout)
    except ValueError:
        print("Runtime check did not return valid diagnostics.", file=sys.stderr)
        return 1
    if (
        checked.returncode not in (0, 1)
        or readiness.get("status") == "BLOCKED"
        or not readiness.get("http_ready")
    ):
        print(
            "Dependencies were installed, but the requested runtime is not ready. See docs/setup.md.",
            file=sys.stderr,
        )
        return 1
    browser_ready = bool(readiness.get("browser_ready"))
    if not args.http_only and not browser_ready:
        failure = readiness.get("checks", {}).get("browser_runtime", {}).get("failure")
        print(
            "HTTP engine ready; browser rendering not verified. "
            + str(failure or optional_errors.get("browser") or "See doctor diagnostics.")
            + " Use HTTP evidence or a permitted host browser; do not claim JavaScript coverage.",
            file=sys.stderr,
        )
        if args.require_browser:
            return 1
    from install_skill import shell_command

    command = [sys.executable, str(root / "scripts/run.py")]
    if args.venv:
        command.extend(["--runtime", str(env)])
    print("\nCrawler ready for " + ("HTTP and browser mode." if browser_ready else "HTTP mode."))
    print("Target website and search access have not been tested by setup.")
    if not readiness.get("pdf_ready"):
        print(
            "PDF export not ready; HTML reports remain available. See doctor for the report dependency."
        )
    print(
        "Check again: "
        + shell_command([*command, "doctor", *([] if browser_ready else ["--no-browser"])])
    )
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
    except subprocess.TimeoutExpired as error:
        print(
            f"Setup command timed out after {error.timeout} seconds. "
            "Keep the recorded command error; check the host's permitted network/runtime before retrying.",
            file=sys.stderr,
        )
        raise SystemExit(2)
