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
    bindir = root / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    python = bindir / ("python.exe" if os.name == "nt" else "python")
    # Compare prefixes: virtualenv Python can be a symlink to the system executable.
    if python.is_file() and Path(sys.prefix).resolve() != (root / ".venv").resolve():
        return subprocess.call([str(python), "-B", str(Path(__file__).resolve()), *sys.argv[1:]])
    sys.path.insert(0, str(root / "src"))
    try:
        from beyondseo.cli import main as cli_main
    except ModuleNotFoundError as error:
        print(
            f"Missing dependency: {error.name}. Run Python on {root / 'scripts/setup.py'} first.",
            file=sys.stderr,
        )
        return 2
    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
