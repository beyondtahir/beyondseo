"""Offline, branded client reports from explicit, attributable report content.

No websites are fetched and no scores are computed here. The presentation layer
preserves the supplied findings, source notes and uncertainty. HTML needs only
the standard library; the optional ReportLab renderer creates a printable PDF.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import html
import json
import math
import os
import tempfile
from importlib.resources import files
from pathlib import Path
from urllib.parse import urlsplit

INK = "#151515"
RED = "#991B1B"
MUTED = "#595959"
PALE = "#F5F3F1"
RULE = "#DDDAD7"
BLOCKS = {"text", "bullets", "callout", "table", "metrics", "bars", "finding"}


def text(value):
    return str(value if value is not None else "")


def asset(name):
    return files("beyondseo").joinpath("report_assets", name).read_bytes()


def validate_report(data):
    """Check layout contracts, never certify the truth of supplied report claims."""
    if not isinstance(data, dict):
        raise ValueError("Report input must be a JSON object.")
    for field in ("title", "client", "date", "summary"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise ValueError("Report needs nonempty " + field + ".")
    for field, limit in (("title", 140), ("client", 100), ("date", 60), ("summary", 650)):
        if len(data[field]) > limit:
            raise ValueError(
                f"Report {field} exceeds {limit} characters; move detail into a section."
            )
    sections = data.get("sections")
    if not isinstance(sections, list) or not 1 <= len(sections) <= 40:
        raise ValueError("Use 1–40 report sections.")
    for section in sections:
        if (
            not isinstance(section, dict)
            or not section.get("title")
            or len(text(section["title"])) > 140
        ):
            raise ValueError("Every section needs a title of 1–140 characters.")
        blocks = section.get("blocks", [])
        if not isinstance(blocks, list) or not 1 <= len(blocks) <= 100:
            raise ValueError("Every section needs 1–100 content blocks.")
        for block in blocks:
            if not isinstance(block, dict) or block.get("type") not in BLOCKS:
                raise ValueError("Unknown report block; use " + ", ".join(sorted(BLOCKS)))
            kind = block["type"]
            if kind in ("text", "callout") and not block.get("text"):
                raise ValueError(kind + " needs text.")
            if kind == "bullets" and not isinstance(block.get("items"), list):
                raise ValueError("Bullets need an items list.")
            if kind == "table":
                columns, rows = block.get("columns"), block.get("rows")
                if not isinstance(columns, list) or not 1 <= len(columns) <= 6:
                    raise ValueError("Tables support 1–6 columns; split wider tables.")
                if not isinstance(rows, list) or len(rows) > 1000:
                    raise ValueError("Tables support up to 1000 rows.")
                if any(not isinstance(row, list) or len(row) != len(columns) for row in rows):
                    raise ValueError("Every table row must match its column count.")
                weights = block.get("widths", [1] * len(columns))
                if len(weights) != len(columns) or any(
                    not isinstance(w, (int, float)) or not math.isfinite(w) or w <= 0
                    for w in weights
                ):
                    raise ValueError("Table widths must be positive finite column weights.")
            if kind in ("metrics", "bars"):
                if not block.get("source"):
                    raise ValueError(
                        "Metrics and charts need an explicit source and coverage note."
                    )
                items = block.get("items")
                if not isinstance(items, list) or not 1 <= len(items) <= (
                    4 if kind == "metrics" else 12
                ):
                    raise ValueError("Use 1–4 metrics or 1–12 chart items per block.")
                for item in items:
                    if not isinstance(item, dict) or not item.get("label") or "value" not in item:
                        raise ValueError("Metrics/chart items need label and value.")
                    if kind == "bars" and (
                        not isinstance(item["value"], (int, float))
                        or isinstance(item["value"], bool)
                        or not math.isfinite(item["value"])
                        or item["value"] < 0
                    ):
                        raise ValueError("Bar values must be finite nonnegative numbers.")
            if kind == "finding":
                required = (
                    "title",
                    "urls",
                    "observation",
                    "captured_at",
                    "claim_type",
                    "impact",
                    "action",
                    "priority",
                    "rationale",
                    "acceptance",
                    "limits",
                    "source",
                )
                if any(field not in block for field in required):
                    raise ValueError(
                        "Finding needs exact URLs, evidence/date, impact, action, priority/rationale, acceptance and limits."
                    )
                if block["claim_type"] not in ("verified_fact", "inference", "hypothesis"):
                    raise ValueError(
                        "Finding claim type must be verified_fact, inference or hypothesis."
                    )
                if not isinstance(block["urls"], list) or not block["urls"]:
                    raise ValueError("Finding URLs must be a nonempty list.")
    return copy.deepcopy(data)


def from_audit(audit):
    """Turn an existing evidence audit into a report without inventing analysis."""
    blocks = []
    for row in audit.get("findings", []):
        blocks.append(
            {
                "type": "finding",
                "title": row.get("title")
                or row.get("code", "Observed finding").replace("_", " ").capitalize(),
                "urls": row["affected_urls"],
                "observation": row["observation"],
                "captured_at": row.get("captured_at") or "Not recorded",
                "claim_type": row["claim_type"],
                "impact": row["why_it_matters"],
                "action": row["recommended_action"],
                "priority": row["priority"],
                "rationale": row["priority_rationale"],
                "acceptance": row["acceptance_check"],
                "limits": row["uncertainty"],
                "source": "; ".join(ref.get("url", "") for ref in row.get("evidence_refs", []))
                or "Source reference not recorded",
            }
        )
    coverage = audit.get("crawl_coverage", {})
    return {
        "title": "Website audit",
        "client": urlsplit(audit["target"]).hostname or audit["target"],
        "website": audit["target"],
        "date": audit.get("created_at", "Not recorded")[:10],
        "subtitle": "Evidence, priorities and practical next steps",
        "summary": "This report presents the findings in the supplied audit. Read the evidence, proposed action and acceptance check together. Strategic conclusions require a reviewed business profile and comparable research.",
        "sections": [
            {
                "title": "Scope & evidence",
                "lead": "What this report can establish",
                "blocks": [
                    {
                        "type": "text",
                        "text": audit.get("note", "Findings describe the inspected evidence only."),
                    },
                    {
                        "type": "table",
                        "columns": ["Coverage", "Recorded status"],
                        "rows": [
                            ["Target", audit["target"]],
                            ["Search discovery", audit.get("discovery_status", "not_run")],
                            [
                                "Website coverage",
                                "Limited"
                                if coverage.get("coverage_limited", True)
                                else "Within the recorded crawl scope",
                            ],
                            [
                                "Unmeasured",
                                ", ".join(audit.get("unmeasured", []))
                                or "Consult the original audit scope",
                            ],
                        ],
                    },
                ],
            },
            {
                "title": "Findings & actions",
                "lead": "Resolve the evidenced issues, then check the same pages again.",
                "blocks": blocks
                or [
                    {
                        "type": "callout",
                        "title": "No material findings supplied",
                        "text": "This does not establish that the website has no issues. Review the original audit's access and coverage limits.",
                    }
                ],
            },
        ],
    }


def _string(value):
    if isinstance(value, list):
        return "; ".join(_string(v) for v in value)
    return text(value)


def _e(value):
    return html.escape(_string(value), quote=True)


def finding_fields(block):
    return [
        ("Affected pages", block["urls"]),
        ("Observed", block["observation"]),
        ("Evidence", f"{_string(block['captured_at'])} / {block['claim_type'].replace('_', ' ')}"),
        ("Why it matters", block["impact"]),
        ("Recommended action", block["action"]),
        ("Priority rationale", block["rationale"]),
        ("Acceptance check", block["acceptance"]),
        ("Uncertainty & coverage", block["limits"]),
        ("Source", block["source"]),
    ]


def html_report(data):
    logo = base64.b64encode(asset("beyondseo-logo.png")).decode("ascii")
    css = asset("report.css").decode("utf-8")

    def block_html(block):
        kind = block["type"]
        title = f"<h3>{_e(block['title'])}</h3>" if block.get("title") else ""
        source = (
            f'<p class="source">Source & scope: {_e(block["source"])}</p>'
            if block.get("source")
            else ""
        )
        if kind == "text":
            body = '<p dir="auto">' + _e(block["text"]).replace("\n", "<br>") + "</p>"
        elif kind == "bullets":
            body = (
                "<ul>"
                + "".join(f'<li dir="auto">{_e(item)}</li>' for item in block["items"])
                + "</ul>"
            )
        elif kind == "callout":
            return f'<aside class="callout">{title}<p dir="auto">{_e(block["text"])}</p></aside>'
        elif kind == "table":
            body = (
                '<div class="table-wrap"><table><thead><tr>'
                + "".join(f"<th>{_e(c)}</th>" for c in block["columns"])
                + "</tr></thead><tbody>"
            )
            body += (
                "".join(
                    "<tr>" + "".join(f'<td dir="auto">{_e(c)}</td>' for c in row) + "</tr>"
                    for row in block["rows"]
                )
                + "</tbody></table></div>"
            )
        elif kind == "metrics":
            body = (
                '<div class="metrics">'
                + "".join(
                    f"<div><strong>{_e(i['value'])}</strong><span>{_e(i['label'])}</span></div>"
                    for i in block["items"]
                )
                + "</div>"
            )
        elif kind == "bars":
            maximum = max(i["value"] for i in block["items"]) or 1
            body = (
                '<div class="bars-chart">'
                + "".join(
                    f'<div><label>{_e(i["label"])}</label><span class="bar"><i style="width:{i["value"] / maximum * 100:.4f}%"></i></span><b>{_e(i["value"])}</b></div>'
                    for i in block["items"]
                )
                + "</div>"
            )
        else:
            body = (
                f'<p class="eyebrow">{_e(block["priority"])}</p><dl>'
                + "".join(
                    f'<dt>{_e(k)}</dt><dd dir="auto">{_e(v)}</dd>' for k, v in finding_fields(block)
                )
                + "</dl>"
            )
            source = ""
        return f'<div class="block {kind}">{title}{body}{source}</div>'

    toc = "".join(
        f'<a href="#section-{i}"><span>{i:02}</span>{_e(s["title"])}<b>↗</b></a>'
        for i, s in enumerate(data["sections"], 1)
    )
    sections = "".join(
        f'<section class="content" id="section-{i}"><div class="section-number">{i:02}</div><h2 dir="auto">{_e(s["title"])}</h2><p class="lead" dir="auto">{_e(s.get("lead", ""))}</p>{"".join(block_html(b) for b in s["blocks"])}<footer>BeyondSEO · {_e(data["client"])}</footer></section>'
        for i, s in enumerate(data["sections"], 1)
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>{_e(data["title"])} | BeyondSEO</title><style>{css}</style></head><body>
<main><section class="cover"><img class="logo" alt="BeyondSEO" src="data:image/png;base64,{logo}"><div class="edition">SEARCH INTELLIGENCE <span>{_e(data["date"])}</span></div><p class="eyebrow">{_e(data.get("label", "STRATEGY & EVIDENCE"))}</p><h1 dir="auto">{_e(data["title"])}</h1><p class="subtitle" dir="auto">{_e(data.get("subtitle", ""))}</p><div class="client"><small>PREPARED FOR</small><h2 dir="auto">{_e(data["client"])}</h2><p>{_e(data.get("website", ""))}</p></div><div class="cover-note"><small>THE FOCUS</small><p dir="auto">{_e(data["summary"])}</p></div><div class="cover-footer">INSPECT / COMPARE / IMPROVE <span>BEYONDSEO</span></div></section>
<nav class="contents"><p class="eyebrow">THE READING GUIDE</p><h2>Inside this report.</h2><p>Read the conclusions alongside their evidence and coverage limits.</p>{toc}</nav>{sections}</main></body></html>"""


class PDFUnavailable(ValueError):
    """A precise rendering limitation; the HTML report remains available."""


def pdf_report(data, path):
    try:
        import reportlab
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_LEFT
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import (
            BaseDocTemplate,
            Flowable,
            Frame,
            LongTable,
            NextPageTemplate,
            PageBreak,
            PageTemplate,
            Paragraph,
            Spacer,
            TableStyle,
        )
        from reportlab.platypus.tableofcontents import TableOfContents
    except ImportError as exc:
        raise PDFUnavailable(
            "PDF export needs the free report renderer. Run scripts/setup.py in the skill, or install reportlab>=4.2,<5 in the selected runtime. HTML export still works."
        ) from exc
    import io

    fonts = Path(reportlab.__file__).parent / "fonts"
    for name, filename in (("BeyondSans", "Vera.ttf"), ("BeyondSans-Bold", "VeraBd.ttf")):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(fonts / filename)))
    pdfmetrics.registerFontFamily(
        "BeyondSans",
        normal="BeyondSans",
        bold="BeyondSans-Bold",
        italic="BeyondSans",
        boldItalic="BeyondSans-Bold",
    )
    # Refuse silent missing-glyph boxes. Complex-script HTML can use the host's
    # native fonts and print workflow; this PDF renderer does not claim shaping.
    chars = pdfmetrics.getFont("BeyondSans").face.charToGlyph
    body_text = json.dumps(data, ensure_ascii=False)
    unsupported = {c for c in body_text if ord(c) > 31 and ord(c) not in chars}
    if unsupported or any(0x590 <= ord(c) <= 0x109F for c in body_text):
        raise PDFUnavailable(
            "This report contains characters or complex scripts unsupported by the bundled PDF font. Use the complete HTML report and the host's suitable font/print renderer; no content was transliterated or removed."
        )
    W, H, M = 595.276, 841.89, 46
    usable = W - 2 * M
    ink, red, muted, pale, rule = [colors.HexColor(c) for c in (INK, RED, MUTED, PALE, RULE)]
    logo = ImageReader(io.BytesIO(asset("beyondseo-logo.png")))
    styles = {
        "body": ParagraphStyle(
            "body",
            fontName="BeyondSans",
            fontSize=9.3,
            leading=14.6,
            textColor=ink,
            spaceAfter=12,
            splitLongWords=True,
        ),
        "lead": ParagraphStyle(
            "lead", fontName="BeyondSans", fontSize=12, leading=18, textColor=muted, spaceAfter=24
        ),
        "h2": ParagraphStyle(
            "h2",
            fontName="BeyondSans-Bold",
            fontSize=30,
            leading=34,
            textColor=ink,
            spaceAfter=14,
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "h3",
            fontName="BeyondSans-Bold",
            fontSize=13,
            leading=18,
            textColor=ink,
            spaceBefore=12,
            spaceAfter=9,
            keepWithNext=True,
        ),
        "small": ParagraphStyle(
            "small",
            fontName="BeyondSans",
            fontSize=7.3,
            leading=10.8,
            textColor=muted,
            spaceAfter=12,
            splitLongWords=True,
        ),
        "label": ParagraphStyle(
            "label",
            fontName="BeyondSans-Bold",
            fontSize=8,
            leading=11,
            textColor=red,
            spaceAfter=10,
            keepWithNext=True,
        ),
        "cell": ParagraphStyle(
            "cell",
            fontName="BeyondSans",
            fontSize=8,
            leading=12,
            textColor=ink,
            splitLongWords=True,
        ),
        "th": ParagraphStyle(
            "th", fontName="BeyondSans-Bold", fontSize=7.5, leading=11, textColor=colors.white
        ),
    }

    def p(value, style="body"):
        return Paragraph(_e(value).replace("\n", "<br/>"), styles[style])

    def canvas_text(c, value, x, top, width, size, color=ink, bold=False, maxheight=None):
        while True:
            st = ParagraphStyle(
                "cover",
                fontName="BeyondSans-Bold" if bold else "BeyondSans",
                fontSize=size,
                leading=size * 1.2,
                textColor=color,
            )
            para = Paragraph(_e(value), st)
            _, height = para.wrap(width, H)
            if maxheight is None or height <= maxheight or size <= 7:
                break
            size -= 1
        if maxheight is not None and height > maxheight:
            raise ValueError("Cover text is too long; shorten it and move detail into sections.")
        para.drawOn(c, x, top - height)
        return height

    def cover(c, doc):
        c.setFillColor(colors.white)
        c.rect(0, 0, W, H, fill=1, stroke=0)
        c.drawImage(logo, M - 5, H - 115, width=240, height=240 * 729 / 2157, mask="auto")
        c.setFillColor(red)
        c.rect(W - 72, H - 118, 26, 74, fill=1, stroke=0)
        c.setStrokeColor(rule)
        c.line(M, H - 136, W - M, H - 136)
        canvas_text(c, "SEARCH INTELLIGENCE", M, H - 154, 310, 8, bold=True)
        canvas_text(c, data["date"], W - 155, H - 154, 109, 8, muted)
        canvas_text(
            c, data.get("label", "STRATEGY & EVIDENCE"), M, H - 218, usable, 8, red, True, 30
        )
        title_height = canvas_text(
            c, data["title"], M - 2, H - 251, usable - 20, 44, bold=True, maxheight=164
        )
        canvas_text(
            c,
            data.get("subtitle", ""),
            M,
            H - 270 - title_height,
            usable - 50,
            12,
            muted,
            maxheight=50,
        )
        canvas_text(c, "PREPARED FOR", M, 344, usable, 7.5, red, True)
        canvas_text(c, data["client"], M, 322, usable, 20, bold=True, maxheight=49)
        canvas_text(c, data.get("website", ""), M, 268, usable, 8.5, muted, maxheight=25)
        c.setFillColor(ink)
        c.rect(0, 72, W, 155, fill=1, stroke=0)
        c.setFillColor(red)
        c.rect(0, 72, 9, 155, fill=1, stroke=0)
        canvas_text(c, "THE FOCUS", M, 204, usable, 8, colors.white, True)
        canvas_text(c, data["summary"], M, 181, usable, 11, colors.white, maxheight=89)
        canvas_text(c, "INSPECT / COMPARE / IMPROVE", M, 43, 370, 7, muted)
        canvas_text(c, "BEYONDSEO", W - 123, 43, 100, 7, red, True)

    def page(c, doc):
        c.drawImage(logo, M - 3, H - 54, width=110, height=110 * 729 / 2157, mask="auto")
        c.setFillColor(red)
        c.rect(W - M - 36, H - 44, 36, 19, fill=1, stroke=0)
        c.setFont("BeyondSans-Bold", 8)
        c.setFillColor(colors.white)
        c.drawCentredString(W - M - 18, H - 38, f"{doc.page:02}")
        c.setStrokeColor(rule)
        c.line(M, 48, W - M, 48)
        canvas_text(c, data["client"], M, 37, usable - 105, 6.8, muted, maxheight=18)
        canvas_text(c, "BEYONDSEO", W - M - 85, 37, 85, 7, red, True)

    class Doc(BaseDocTemplate):
        def afterFlowable(self, flowable):
            if hasattr(flowable, "toc_entry"):
                title, key = flowable.toc_entry
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(title, key, level=0)
                self.notify("TOCEntry", (0, _e(title), self.page, key))

    doc = Doc(
        str(path),
        pagesize=(W, H),
        leftMargin=M,
        rightMargin=M,
        topMargin=79,
        bottomMargin=67,
        title=data["title"],
        author="BeyondSEO",
        subject="Evidence-based website review",
        allowSplitting=1,
    )
    frame = Frame(
        M, 67, usable, H - 146, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0
    )
    doc.addPageTemplates(
        [
            PageTemplate(id="cover", frames=[frame], onPage=cover),
            PageTemplate(id="body", frames=[frame], onPage=page),
        ]
    )
    story = [
        Spacer(1, 1),
        NextPageTemplate("body"),
        PageBreak(),
        p("THE READING GUIDE", "label"),
        p("Inside this report.", "h2"),
        p("Read the conclusions alongside their evidence and coverage limits.", "lead"),
    ]
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            "toc",
            fontName="BeyondSans-Bold",
            fontSize=12,
            leading=21,
            textColor=ink,
            spaceBefore=14,
            spaceAfter=10,
            leftIndent=0,
            firstLineIndent=0,
            rightIndent=25,
            alignment=TA_LEFT,
        )
    ]
    toc.dotsMinLevel = 0
    story.append(toc)

    def table(rows, widths, header=True, background=True):
        obj = LongTable(
            rows,
            colWidths=widths,
            repeatRows=1 if header else 0,
            hAlign="LEFT",
            splitByRow=1,
            splitInRow=1,
        )
        commands = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 11),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, rule),
        ]
        if header:
            commands.append(("BACKGROUND", (0, 0), (-1, 0), ink))
        if background:
            commands.append(
                ("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, pale])
            )
        obj.setStyle(TableStyle(commands))
        return obj

    class BarRow(Flowable):
        def __init__(self, item, maximum):
            super().__init__()
            self.item = item
            self.maximum = maximum
            self.width = usable
            self.height = 43

        def draw(self):
            c = self.canv
            canvas_text(c, self.item["label"], 0, 39, usable - 65, 8.5, ink, True, maxheight=13)
            c.setFont("BeyondSans-Bold", 9)
            c.setFillColor(ink)
            c.drawRightString(usable, 28, text(self.item["value"]))
            c.setFillColor(pale)
            c.rect(0, 7, usable, 10, fill=1, stroke=0)
            c.setFillColor(red)
            c.rect(0, 7, usable * self.item["value"] / self.maximum, 10, fill=1, stroke=0)

    for number, section in enumerate(data["sections"], 1):
        heading = p(section["title"], "h2")
        heading.toc_entry = (f"{number:02}  {section['title']}", f"section-{number}")
        story.extend([PageBreak(), p(f"{number:02} / THE ANALYSIS", "label"), heading])
        if section.get("lead"):
            story.append(p(section["lead"], "lead"))
        for block in section["blocks"]:
            kind = block["type"]
            if block.get("title") and kind != "callout":
                story.append(p(block["title"], "h3"))
            if kind == "text":
                story.append(p(block["text"]))
            elif kind == "bullets":
                for index, item in enumerate(block["items"], 1):
                    story.append(p(f"{index:02}  {_string(item)}"))
            elif kind == "callout":
                content = ([p(block["title"], "h3")] if block.get("title") else []) + [
                    p(block["text"])
                ]
                box = table([[content]], [usable], header=False)
                box.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, -1), pale),
                            ("LINEBEFORE", (0, 0), (0, -1), 3, red),
                        ]
                    )
                )
                story.extend([box, Spacer(1, 15)])
            elif kind == "table":
                weights = block.get("widths", [1] * len(block["columns"]))
                rows = [[p(c, "th") for c in block["columns"]]] + [
                    [p(c, "cell") for c in row] for row in block["rows"]
                ]
                story.extend(
                    [table(rows, [usable * w / sum(weights) for w in weights]), Spacer(1, 12)]
                )
            elif kind == "metrics":
                cells = []
                for item in block["items"]:
                    style = ParagraphStyle(
                        "metric",
                        fontName="BeyondSans-Bold",
                        fontSize=25 if len(text(item["value"])) < 9 else 14,
                        leading=29,
                        textColor=red,
                        spaceAfter=9,
                    )
                    cells.append([Paragraph(_e(item["value"]), style), p(item["label"], "cell")])
                story.extend(
                    [
                        table([cells], [usable / len(cells)] * len(cells), header=False),
                        Spacer(1, 12),
                    ]
                )
            elif kind == "bars":
                maximum = max(i["value"] for i in block["items"]) or 1
                story.extend(BarRow(i, maximum) for i in block["items"])
            elif kind == "finding":
                story.append(p(block["priority"], "label"))
                for label, value in finding_fields(block):
                    story.append(p(label.upper(), "label"))
                    story.append(
                        p(
                            value,
                            "small"
                            if label in ("Affected pages", "Evidence", "Source")
                            else "body",
                        )
                    )
                story.append(Spacer(1, 14))
            if block.get("source") and kind != "finding":
                story.append(p("Source & scope: " + block["source"], "small"))
        # A trailing spacer must not push an otherwise empty page ahead of the
        # next explicit section break.
        while story and isinstance(story[-1], Spacer):
            story.pop()
    # Multi-pass layout produces actual contents-page numbers, including overflow.
    doc.multiBuild(story)


def export_report(data, out, output_format="both", overwrite=False):
    data = validate_report(data)
    if output_format not in ("both", "html", "pdf"):
        raise ValueError("Report format must be both, html or pdf.")
    out = Path(out)
    names = (
        ["report.manifest.json"]
        + (["report.html"] if output_format != "pdf" else [])
        + (["report.pdf"] if output_format != "html" else [])
    )
    if not overwrite and any((out / name).exists() for name in names):
        raise ValueError("Report output already exists. Choose a new folder or use --overwrite.")
    out.mkdir(parents=True, exist_ok=True)
    result = {
        "status": "complete",
        "renderer": "BeyondSEO editorial v1",
        "files": {},
        "privacy": "Local export only; no upload or external asset requests.",
        "evidence_boundary": "Presentation preserves supplied claims; it does not verify their truth or compute authority metrics.",
    }
    with tempfile.TemporaryDirectory(prefix=".beyondseo-report-", dir=out) as temporary:
        scratch = Path(temporary)
        if output_format != "pdf":
            (scratch / "report.html").write_text(html_report(data), encoding="utf-8")
        if output_format != "html":
            try:
                pdf_report(data, scratch / "report.pdf")
            except PDFUnavailable as exc:
                if output_format == "pdf":
                    raise
                result.update(status="html_only", pdf_limitation=str(exc))
        for name in names:
            file = scratch / name
            if file.exists():
                result["files"][name] = {
                    "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                    "bytes": file.stat().st_size,
                }
        (scratch / "report.manifest.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
        for name in names:
            if (scratch / name).exists():
                os.replace(scratch / name, out / name)
            elif name == "report.pdf" and overwrite and (out / name).exists():
                # Do not leave a previous client's PDF beside the new HTML when
                # this explicitly requested replacement could not render a PDF.
                (out / name).unlink()
    return result
