# Reports that look like BeyondSEO

Use the built-in editorial layout for PDFs, downloadable audits, proposals, strategy reports and recurring reviews. Lead with a clear cover, a short reading guide, useful conclusions, comparable evidence and actions the reader can verify.

The existing BeyondSEO logo is included unchanged. Reports use white, near-black and dark red, generous margins, numbered sections, neutral comparison tables, source notes and page numbers. PDF contents link to the actual section pages. Charts are vector graphics; the logo and fonts are embedded. PDF export requires no paid API, browser session, remote fonts or online template account.

## Generate a report

The normal installer includes the free PDF renderer. Copy the [fictional content example](../examples/report-content.json) outside the repository and replace it with reviewed client evidence:

```sh
python3 scripts/run.py present --input /path/to/client/report-content.json \
  --out /path/to/client/deliverable
```

Windows uses `py -3` in place of `python3`. Outputs are `report.pdf`, self-contained `report.html`, and `report.manifest.json` with export status and checksums. Files stay local. Choose a fresh folder; `--overwrite` deliberately replaces an earlier export.

For a direct presentation of native audit findings:

```sh
python3 scripts/run.py present --audit /path/to/client/audit.json \
  --out /path/to/client/audit-deliverable
```

This preserves findings, URLs, dates, claim types, priority rationale, actions, acceptance checks and uncertainty. It does not invent an executive judgment, competitor research or missing measurements. For a complete strategy report, the assistant prepares reviewed content JSON from the audit and other captured research first.

`--format html` needs no PDF library. `--format pdf` requests only PDF. The default `both` retains usable HTML if the PDF renderer is unavailable and returns a partial status with the reason. An explicitly overwritten, outdated PDF is removed in that case so it cannot be mistaken for the new report. The existing `report --out` command still regenerates raw crawl exports; `present` is the client-facing design step.

## Write the content first

Keep sections proportional to the request. A short technical review does not need a long strategy deck. A complete audit normally covers:

1. Executive perspective and priorities.
2. Business profile, scope and evidence limits.
3. Buyer language, keyword hypotheses and page intent.
4. Verified competitor comparisons and meaningful differences.
5. Backlink/reputation evidence and comparable research coverage.
6. Technical/content findings with acceptance checks.
7. AEO/GEO, entity consistency, useful answers and visibility limits.
8. Tailored publishing recommendations and 30/60/90-day actions.
9. Sources, capture dates, unmeasured items and follow-up checks.

Lead with conclusions; place the detailed source list in an appendix. Preserve verified facts, inferences, hypotheses and unknowns. Show only measured metrics or explicitly labeled planning assumptions. Never invent a score, ranking, volume or traffic figure to fill a chart.

## Content format

Required top-level fields: `title`, `client`, `date`, `summary`, `sections`. Optional fields: `website`, `subtitle`, `label`. A section has a `title`, optional `lead` and `blocks`.

| Block type | Content | Design |
|---|---|---|
| `text` | `text`, optional `title` | Readable body copy |
| `bullets` | `items` | Parallel actions or observations |
| `callout` | `text`, optional `title` | Pale panel with a red rule |
| `table` | `columns`, `rows`, optional relative `widths` | Wrapped rows and repeated PDF headings |
| `metrics` | 1–4 `items` with `label`/`value`, plus `source` | Strong figures with source and coverage notes |
| `bars` | 1–12 `items` with `label`/nonnegative numeric `value`, plus `source` | Horizontal bars scaled to the largest supplied value; identify units in the title/source |
| `finding` | `title`, `urls`, `observation`, `captured_at`, `claim_type`, `impact`, `action`, `priority`, `rationale`, `acceptance`, `limits`, `source` | Complete evidence and action record |

Text is treated as text, not executable HTML or instructions. Tables support up to six columns; split wider comparisons instead of shrinking type. Long tables and body content flow across pages. Input validation checks the format, not the truth of the claims.

## Check the delivery

Inspect the rendered cover, contents, every section, long tables, sources and final page. Check clipping, overlap, empty overflow pages, page numbers and unsupported glyphs. Confirm the logo is intact on a light background and no fictional content remains in a real report. Keep the reviewed JSON with the private evidence for reproducible updates.

PDF uses embedded Bitstream Vera fonts distributed with ReportLab. Unsupported characters/complex scripts produce a precise limitation and retain complete HTML instead of missing-glyph boxes or transliterated text. Use a host renderer with suitable fonts for those PDF outputs. HTML is responsive, uses local system fonts and provides a reading alternative to the PDF; the PDF is not tagged/PDF-UA certified.

If ReportLab is missing, run `python3 scripts/setup.py` or install `reportlab>=4.2,<5` in the selected runtime. It is a free local dependency. `doctor` reports dependency presence separately; a `present` run verifies actual rendering. Export needs no network or browser permission.

Generated client reports, preview renders and private evidence stay outside the public repository. The example is fictional input, not a client report or proof of search results.
