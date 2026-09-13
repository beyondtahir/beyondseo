#!/usr/bin/env python3
"""Classify a supplied CSV's user-assessed relevance/risk; does not measure backlinks."""

import csv
import sys


def verdict(relevance, risk):
    if relevance not in ("low", "medium", "high") or risk not in ("low", "medium", "high"):
        return "Need valid relevance/risk assessment"
    if risk == "high":
        return "Avoid"
    if relevance == "high" and risk in ("low", "medium"):
        return "Good prospect"
    if relevance == "medium" and risk == "low":
        return "Review manually"
    return "Low priority"


if __name__ == "__main__":
    reader = csv.DictReader(sys.stdin)
    if not reader.fieldnames or not {"url", "relevance", "risk"}.issubset(reader.fieldnames):
        sys.exit("CSV requires url,relevance,risk columns.")
    fields = list(reader.fieldnames) + ([] if "verdict" in reader.fieldnames else ["verdict"])
    writer = csv.DictWriter(sys.stdout, fieldnames=fields)
    writer.writeheader()
    for row in reader:
        row["verdict"] = verdict(row["relevance"].lower(), row["risk"].lower())
        writer.writerow(
            {
                k: (
                    "'" + v
                    if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@"))
                    else v
                )
                for k, v in row.items()
            }
        )
