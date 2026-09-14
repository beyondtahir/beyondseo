#!/usr/bin/env python3
"""Import visible posting-site rows from a supplied PDF, retaining unverified claims."""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

FIELDS = ["id", "source_page", "source_section", "source_url", "sheet_dr", "sheet_link_label"]
ROW = re.compile(r"^\s*(https?://\S+)\s+(\d{1,3})\s+(index|no follow)\s*$")


def parse_pages(texts):
    rows = []
    section = "article"
    for page, text in enumerate(texts, 1):
        for line in text.splitlines():
            if "POSTING website" in line:
                section = "posting"
            match = ROW.match(line)
            if not match:
                if line.lstrip().startswith(("http://", "https://")):
                    raise ValueError(f"Unparsed URL row on page {page}: {line[:150]}")
                continue
            if int(match[2]) > 100:
                raise ValueError(f"Out-of-range sheet DR on page {page}")
            site_key(match[1])
            rows.append(
                dict(
                    zip(
                        FIELDS,
                        [
                            f"pdf-{len(rows) + 1:03d}",
                            page,
                            section,
                            match[1],
                            int(match[2]),
                            match[3],
                        ],
                    )
                )
            )
    if not rows:
        raise ValueError("No visible URL rows found; inspect the PDF before importing")
    return rows


def site_key(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("Expected an HTTP(S) website URL without credentials")
    host = parsed.hostname.lower().removeprefix("www.")
    # This help subdomain is another route for the same posting platform.
    return {"business.quora.com": "quora.com"}.get(host, host)


def group_rows(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[site_key(row["source_url"])].append(row)
    sites = []
    for host, records in grouped.items():
        urls = list(dict.fromkeys(r["source_url"] for r in records))
        values = list(dict.fromkeys(int(r["sheet_dr"]) for r in records))
        is_community = host.endswith(".mn.co")
        is_example = any("/members/" in u or "/posts/" in u or "onlinequran" in u for u in urls)
        sites.append(
            {
                "id": host,
                "name": host,
                "source_rows": [r["id"] for r in records],
                "source_urls": urls,
                "sheet_dr_values": values,
                "sheet_dr_conflict": len(values) > 1,
                "sheet_link_labels": list(dict.fromkeys(r["sheet_link_label"] for r in records)),
                "website_url": f"{urlsplit(urls[0]).scheme}://{urlsplit(urls[0]).netloc}/",
                "posting_url": "",
                "kind": "community" if is_community else "unclassified",
                "topics": [],
                "regions": [],
                "requirements": [],
                "cost_status": "sheet_claim_only",
                "review_status": "unreviewed",
                "reviewed_at": None,
                "review_sources": [],
                "how_to_post": [],
                "link_guidance": "Link placement and rel attributes have not been checked.",
                "eligibility": "Check current registration, topic rules and free posting terms.",
                "fit_note": "",
                "article_angle": "",
                "readiness": "research_first",
                "example_url_only": is_example,
                "current_da": None,
                "current_dr": None,
                "observed_link_rel": None,
                "indexing_status": "not_checked",
            }
        )
    return sites


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="Directory for raw import files")
    args = parser.parse_args()
    try:
        from pypdf import PdfReader
    except ImportError:
        parser.error("This optional import command needs pypdf; normal catalog use does not.")
    reader = PdfReader(args.pdf)
    rows = parse_pages([p.extract_text(extraction_mode="layout") or "" for p in reader.pages])
    annotations = []
    for page_number, page in enumerate(reader.pages, 1):
        for ref in page.get("/Annots", []):
            action = ref.get_object().get("/A", {})
            if action.get("/URI"):
                annotations.append({"page": page_number, "url": str(action["/URI"])})
    sites = group_rows(rows)
    visible = {r["source_url"] for r in rows}
    provenance = {
        "source_document": args.pdf.name,
        "sha256": hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
        "pages": len(reader.pages),
        "visible_rows": len(rows),
        "unique_exact_urls": len(visible),
        "unique_site_entries": len(sites),
        "hyperlink_annotations": len(annotations),
        "rows_per_page": dict(Counter(r["source_page"] for r in rows)),
        "additional_annotation_destinations": sorted({a["url"] for a in annotations} - visible),
        "metric_label_in_source": "Domain Rating (DR)",
        "metric_provider": "not supplied",
        "metric_measurement_date": None,
        "metric_status": "unverified source claims",
        "sites_with_conflicting_dr_values": [s["id"] for s in sites if s["sheet_dr_conflict"]],
        "interpretation": "Visible rows are the import authority. PDF annotations are incomplete; their count is not the catalog size. The word index in a do-follow column verifies neither indexing nor link attributes.",
    }
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "backlink-source-database.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    for name, data in [
        ("posting-sites.json", sites),
        ("source-catalog-provenance.json", provenance),
    ]:
        (args.out / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(provenance, indent=2))


if __name__ == "__main__":
    main()
