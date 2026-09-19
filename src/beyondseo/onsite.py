"""Conservative static-HTML drafts and sitemap drafts; never deploy automatically.

Framework source, templates and CMS content must be edited through the host's
native project tools. Static checks do not establish visual equivalence.
"""

from __future__ import annotations

import json
import tempfile
from contextlib import closing
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

from .network import normalize_url
from .publishing import LIMIT, open_store, stage, text_bytes


def single(soup, selector):
    try:
        nodes = soup.select(selector)
    except Exception as exc:
        raise ValueError("Invalid copy selector; use a valid CSS selector.") from exc
    if len(nodes) != 1:
        raise ValueError(
            f"Expected exactly one {selector}; inspect duplicates/missing markup first."
        )
    return nodes[0]


def metadata(soup, selector, tag, attrs, value=None):
    nodes = soup.select(selector)
    if len(nodes) > 1:
        raise ValueError(f"Duplicate {selector}; resolve deliberately before drafting.")
    node = nodes[0] if nodes else soup.new_tag(tag)
    node.attrs.update(attrs)
    if value is not None:
        node.string = value
    if not nodes:
        single(soup, "head").append(node)


def short_text(value, label, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{label} needs nonempty text up to {maximum} characters.")
    return value.strip()


def draft_html(raw, changes):
    before = text_bytes(raw).decode()
    if any(marker in before for marker in ("<?", "{{", "{%", "<%")):
        raise ValueError(
            "Template source needs its native framework editor, not the static HTML helper."
        )
    if (
        not isinstance(changes, dict)
        or not changes
        or changes.keys()
        - {
            "title",
            "description",
            "canonical",
            "language",
            "copy",
            "schema",
        }
    ):
        raise ValueError(
            "Supported changes: title, description, canonical, language, copy and schema."
        )
    soup = BeautifulSoup(before, "html.parser")
    single(soup, "html")
    single(soup, "head")
    single(soup, "body")
    if "title" in changes:
        metadata(soup, "head title", "title", {}, short_text(changes["title"], "Title", 200))
    if "description" in changes:
        metadata(
            soup,
            'head meta[name="description"]',
            "meta",
            {
                "name": "description",
                "content": short_text(changes["description"], "Description", 500),
            },
        )
    if "canonical" in changes:
        value = changes["canonical"]
        url = normalize_url(value)
        if not url or urlsplit(value).fragment:
            raise ValueError(
                "Canonical must be an absolute HTTP(S) URL without credentials or fragment."
            )
        metadata(soup, 'head link[rel="canonical"]', "link", {"rel": "canonical", "href": url})
    if "language" in changes:
        import re

        if not re.fullmatch(r"[a-zA-Z]{2,8}(?:-[a-zA-Z0-9]{1,8})*", str(changes["language"])):
            raise ValueError("Use a valid language tag supported by the observed content.")
        soup.html["lang"] = changes["language"]
    copied = []
    edits = changes.get("copy", [])
    if not isinstance(edits, list) or len(edits) > 30:
        raise ValueError("Supply up to 30 short, individually reviewed copy edits per page.")
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {"selector", "text"}:
            raise ValueError("Each copy edit needs selector and text.")
        node = single(soup, edit["selector"])
        if node.name not in {"p", "h1", "h2", "h3", "h4", "h5", "h6"} or node.find(True):
            raise ValueError(
                "Only plain-text paragraphs/headings can be replaced; preserve links and nested markup through the native editor."
            )
        old = node.get_text().strip()
        new = short_text(edit["text"], "Copy", 5000)
        if not old or not 0.80 <= len(new) / len(old) <= 1.15:
            raise ValueError(
                "Copy exceeds the 80–115% character-length guard. Review the layout in the native editor instead."
            )
        if edit["selector"] in copied:
            raise ValueError("Duplicate copy selector.")
        copied.append(edit["selector"])
        node.string = new
    if "schema" in changes:
        schema = changes["schema"]
        if not isinstance(schema, (dict, list)) or not schema:
            raise ValueError("Supply reviewed JSON-LD data grounded in visible content.")
        scripts = soup.select('script[type="application/ld+json"]')
        if scripts:
            raise ValueError(
                "Existing JSON-LD needs a deliberate merge through the native editor; refusing a duplicate schema block."
            )
        node = soup.new_tag("script", type="application/ld+json")
        node.string = (
            json.dumps(schema, ensure_ascii=False)
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026")
        )
        soup.head.append(node)
    after = str(soup).encode()
    text_bytes(after)
    return after, {
        "status": "drafted",
        "copy_selectors": copied,
        "static_scope": "No body elements, layout attributes, styles or navigation intentionally changed.",
        "visual_verification": "required; character counts cannot guarantee matching line wraps",
        "schema_semantics": "not verified; agent must compare claims with visible content",
        "next_checks": [
            "Review diff",
            "Check rendered desktop/mobile layouts",
            "Validate links and schema",
            "Apply reviewed hash only within authorised scope",
            "Inspect deployed response and render",
        ],
    }


def plan_html(site, connection, filename, changes_path, out):
    if Path(filename).suffix.lower() not in {".html", ".htm"}:
        raise ValueError(
            "Use the static helper only for HTML files, not framework source or CMS data."
        )
    changes_path = Path(changes_path)
    if changes_path.stat().st_size > LIMIT:
        raise ValueError("Change input exceeds 5 MB.")
    changes = json.loads(changes_path.read_text(encoding="utf-8"))
    with closing(open_store(site, connection)) as store:
        after, checks = draft_html(store.read(filename), changes)
        with tempfile.TemporaryDirectory(prefix="beyondseo-draft-") as temporary:
            replacement = Path(temporary) / "draft.html"
            replacement.write_bytes(after)
            result = stage(store, filename, replacement, out)
    from .projects import write_private

    write_private(Path(out) / "checks.json", json.dumps(checks, indent=2))
    return {**result, **checks, "status": "staged", "website_changed": False}


def sitemap_draft(rows, site):
    """Only explicitly verified, indexable, canonical 200 URLs enter the draft."""
    root_url = normalize_url(site)
    if not root_url or not isinstance(rows, list) or not rows:
        raise ValueError("Provide the website URL and a nonempty reviewed URL list.")
    root = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    seen = set()
    for row in rows:
        url = normalize_url(row.get("url", ""))
        if (
            not url
            or urlsplit(url).netloc != urlsplit(root_url).netloc
            or urlsplit(row["url"]).fragment
        ):
            raise ValueError(
                "Sitemap entries must be absolute URLs on the selected canonical host."
            )
        if (
            row.get("status") != 200
            or row.get("indexable") is not True
            or normalize_url(row.get("canonical", "")) != url
            or not row.get("captured_at")
        ):
            raise ValueError(
                "Each URL needs a captured 200 response, confirmed indexability, self-canonical and capture date."
            )
        if url in seen:
            continue
        seen.add(url)
        item = ET.SubElement(root, "url")
        ET.SubElement(item, "loc").text = url
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def register(sub):
    p = sub.add_parser(
        "onsite", help="Draft guarded static HTML or a reviewed sitemap; does not deploy."
    )
    actions = p.add_subparsers(dest="onsite_action", required=True)
    plan = actions.add_parser("plan")
    target = plan.add_mutually_exclusive_group(required=True)
    target.add_argument("--site", type=Path)
    target.add_argument("--connection", type=Path)
    plan.add_argument("--file", required=True)
    plan.add_argument("--changes", type=Path, required=True)
    plan.add_argument("--out", type=Path, required=True)
    sitemap = actions.add_parser("sitemap")
    sitemap.add_argument("--url", required=True)
    sitemap.add_argument("--input", type=Path, required=True)
    sitemap.add_argument("--out", type=Path, required=True)


def execute(args):
    if args.onsite_action == "plan":
        return plan_html(args.site, args.connection, args.file, args.changes, args.out)
    from .projects import read_json

    data = sitemap_draft(read_json(args.input), args.url)
    with args.out.open("xb") as f:
        f.write(data)
    return {
        "status": "drafted",
        "path": str(args.out),
        "website_changed": False,
        "next_step": "Integrate with the site's existing sitemap mechanism; do not overwrite it blindly.",
    }
