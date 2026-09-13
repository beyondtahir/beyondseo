#!/usr/bin/env python3
"""Heuristic URL-label helper; URL tokens do not establish page intent."""

import csv
import sys


def classify(url):
    u = url.lower()
    if "blog" in u or "article" in u:
        return "Blog/Support"
    if "service" in u:
        return "Service"
    if "course" in u or "academy" in u:
        return "Course"
    if "contact" in u or "book" in u:
        return "Conversion"
    if "about" in u or "team" in u:
        return "Trust"
    return "Unknown"


if __name__ == "__main__":
    writer = csv.writer(sys.stdout)
    writer.writerow(["url", "heuristic_page_type"])
    for raw in sys.stdin:
        url = raw.strip()
        if url:
            writer.writerow(
                ["'" + url if url.startswith(("=", "+", "-", "@")) else url, classify(url)]
            )
