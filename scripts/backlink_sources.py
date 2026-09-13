#!/usr/bin/env python3
"""Display the saved BeyondSEO backlink/source catalog; no network requests."""

import argparse
import csv
import json
from pathlib import Path


def load_sources(platform="", category=""):
    path = (
        Path(__file__).resolve().parents[1]
        / "playbooks/backlink-system/backlink-source-database.csv"
    )
    with path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    return [
        row
        for row in rows
        if (not platform or platform.casefold() == row["Platform"].casefold())
        and (not category or category.casefold() in row["Category"].casefold())
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", default="", help="Exact platform name, case-insensitive.")
    parser.add_argument("--category", default="", help="Case-insensitive category substring.")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()
    rows = load_sources(args.platform, args.category)
    if args.format == "json":
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        print("# BeyondSEO saved backlink/source catalog\n")
        print(
            f"{len(rows)} matching entries. These are saved source URLs; current availability, ownership and target backlinks have not been checked by this command.\n"
        )
        print("| Platform | Category | Saved source URL | Intended use |")
        print("|---|---|---|---|")
        for row in rows:
            cells = [
                row[key].replace("|", r"\|").replace("\n", " ")
                for key in ("Platform", "Category", "URL", "Best Use")
            ]
            cells[2] = f"[Open saved source]({cells[2]})"
            print("| " + " | ".join(cells) + " |")
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
