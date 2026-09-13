#!/usr/bin/env python3
"""Compatibility entrypoint: regenerate evidence reports from a local crawl."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from crawl import main

if __name__ == "__main__":
    sys.exit(main(["report"] + sys.argv[1:]))
