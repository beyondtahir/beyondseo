"""Small, deterministic HTML-to-Markdown conversion for readable crawl exports."""

import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, NavigableString


def escape(text):
    return re.sub(r"([\\`*_\[\]<>])", r"\\\1", text)


def markdown_from_html(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    for node in soup.find_all(
        ["script", "style", "head", "noscript", "template", "svg", "nav", "footer", "aside"]
    ):
        node.decompose()
    for node in soup.select('[hidden], [aria-hidden="true"]'):
        if node.parent:
            node.decompose()
    body = soup.body or soup
    main = body.find("main") or body.find(attrs={"role": "main"})
    # A hero-only landmark must not discard the rest of the useful page.
    if main and len(main.get_text(" ", strip=True).split()) >= 0.35 * len(
        body.get_text(" ", strip=True).split()
    ):
        body = main

    def walk(node, depth=0):
        if isinstance(node, NavigableString):
            return escape(re.sub(r"\s+", " ", str(node)))
        name = node.name or ""
        if name == "pre":
            raw = node.get_text().strip("\n")
            fence = "`" * max(
                3, max((len(m.group()) + 1 for m in re.finditer(r"`+", raw)), default=3)
            )
            return "\n\n" + fence + "\n" + raw + "\n" + fence + "\n\n"
        if name == "code":
            raw = node.get_text()
            fence = "`" * (max((len(m.group()) for m in re.finditer(r"`+", raw)), default=0) + 1)
            return fence + " " + raw + " " + fence
        if name in ("ul", "ol"):
            lines = []
            for i, li in enumerate(node.find_all("li", recursive=False), 1):
                value = "".join(walk(c, depth + 1) for c in li.children).strip()
                marker = str(i) + ". " if name == "ol" else "- "
                lines.append("  " * depth + marker + value)
            return "\n" + "\n".join(lines) + "\n"
        if name == "table":
            rows = []
            for tr in node.find_all("tr"):
                cells = [
                    escape(c.get_text(" ", strip=True)).replace("|", "\\|")
                    for c in tr.find_all(["th", "td"], recursive=False)
                ]
                if cells:
                    rows.append(cells)
            if not rows:
                return ""
            width = max(map(len, rows))
            rows = [r + [""] * (width - len(r)) for r in rows]
            lines = ["| " + " | ".join(r) + " |" for r in rows]
            lines.insert(1, "| " + " | ".join(["---"] * width) + " |")
            return "\n\n" + "\n".join(lines) + "\n\n"
        text = "".join(walk(c, depth) for c in node.children)
        if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            return "\n\n" + "#" * int(name[1]) + " " + text.strip() + "\n\n"
        if name == "a" and node.get("href"):
            href = urljoin(base_url, node["href"])
            if urlsplit(href).scheme in ("https", "http", "mailto", "tel"):
                return (
                    "[" + text.strip() + "](" + href.replace(" ", "%20").replace(")", "%29") + ")"
                    if text.strip()
                    else ""
                )
        if name in ("strong", "b"):
            return "**" + text.strip() + "**" if text.strip() else ""
        if name in ("em", "i"):
            return "*" + text.strip() + "*" if text.strip() else ""
        if name == "br":
            return "\n"
        if name in ("p", "div", "section", "article", "main", "header", "blockquote"):
            return "\n\n" + text.strip() + "\n\n"
        return text

    return re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", walk(body)).strip() + "\n"
