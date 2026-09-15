#!/usr/bin/env python3
"""Run the bundled CLI from any working directory, without shell activation."""

import os
import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    if sys.version_info < (3, 10):
        print("BeyondSEO needs Python 3.10 or newer.", file=sys.stderr)
        return 2
    arguments = sys.argv[1:]
    runtime = root / ".venv"
    explicit_runtime = arguments[:1] == ["--runtime"]
    if explicit_runtime:
        if len(arguments) < 3:
            print("Use: run.py --runtime /approved/virtualenv <command>", file=sys.stderr)
            return 2
        runtime = Path(arguments[1]).expanduser().absolute()
        arguments = arguments[2:]
    bindir = runtime / ("Scripts" if os.name == "nt" else "bin")
    python = bindir / ("python.exe" if os.name == "nt" else "python")
    if explicit_runtime and not python.is_file():
        print(
            f"No Python runtime at {runtime}. Run setup.py --venv with this folder first.",
            file=sys.stderr,
        )
        return 2
    # Compare prefixes: virtualenv Python can be a symlink to the system executable.
    if python.is_file() and Path(sys.prefix).resolve() != runtime.resolve():
        try:
            return subprocess.call(
                [str(python), "-B", str(Path(__file__).resolve()), *sys.argv[1:]]
            )
        except OSError as error:
            print(f"Cannot launch the Python runtime at {runtime}: {error}", file=sys.stderr)
            print(
                "Use setup.py --venv and run.py --runtime with a host-approved execution folder. See docs/agent-installation.md.",
                file=sys.stderr,
            )
            return 2
    sys.path.insert(0, str(root / "src"))
    try:
        from beyondseo.cli import main as cli_main
    except ModuleNotFoundError as error:
        print(
            f"Missing dependency: {error.name}. Run Python on {root / 'scripts/setup.py'} first.",
            file=sys.stderr,
        )
        return 2
    return cli_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
