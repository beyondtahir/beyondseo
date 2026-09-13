#!/usr/bin/env python3
"""Set up a local BeyondSEO environment from this source checkout."""

import argparse
import subprocess
import sys
import venv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--http-only", action="store_true", help="Skip the optional browser.")
    parser.add_argument("--dev", action="store_true", help="Install development tools too.")
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        print("BeyondSEO needs Python 3.10 or newer. Python 3.12 is recommended.", file=sys.stderr)
        return 2
    root = Path(__file__).resolve().parents[1]
    env = root / ".venv"
    print("Preparing", env, flush=True)
    venv.EnvBuilder(with_pip=True).create(env)
    bindir = env / ("Scripts" if sys.platform == "win32" else "bin")
    python = bindir / ("python.exe" if sys.platform == "win32" else "python")
    executable = bindir / ("beyondseo.exe" if sys.platform == "win32" else "beyondseo")
    extras = ([] if args.http_only else ["browser"]) + (["dev"] if args.dev else [])
    target = str(root) + ("[" + ",".join(extras) + "]" if extras else "")
    subprocess.run([str(python), "-m", "pip", "install", "-e", target], check=True)
    if not args.http_only:
        subprocess.run([str(python), "-m", "playwright", "install", "chromium"], check=True)
        subprocess.run([str(executable), "doctor"], check=True)
    print("\nBeyondSEO is ready.\n")
    print(
        "Activate: .venv\\Scripts\\Activate.ps1"
        if sys.platform == "win32"
        else "Activate: source .venv/bin/activate"
    )
    print(
        "Try: beyondseo crawl https://example.com --out runs/example --max-pages 10"
        + (" --mode http" if args.http_only else "")
    )
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
