#!/usr/bin/env python3
"""Compatibility entry point for the environment check."""

from crawl import main

if __name__ == "__main__":
    raise SystemExit(main(["doctor"]))
