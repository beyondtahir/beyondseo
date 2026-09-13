# Try BeyondSEO locally

The practice website has two pages: product cards in HTML and a detail page populated by JavaScript. It contains no external dependencies.

With BeyondSEO's environment active, start a server from the repository root:

```sh
python -m http.server 8765 --bind 127.0.0.1 --directory examples/site
```

In a second terminal, activate the same environment and crawl it:

```sh
beyondseo crawl http://127.0.0.1:8765 --allow-private \
  --out runs/practice --max-pages 5 --no-sitemaps --selectors examples/selectors.json
```

The local-address override is required because public crawling excludes loopback addresses. The first page is readable through HTTP; automatic mode renders the dynamic detail page. Inspect `documents.jsonl`, the custom fields in `pages.jsonl`, and the Markdown files in `content/`.

Capture one page visually:

```sh
beyondseo scrape http://127.0.0.1:8765/dynamic.html --allow-private \
  --out runs/practice-visual --screenshot --wait-for-selector h1
```

Press Ctrl+C in the server terminal when finished. The server is only a fixture for testing your installation.

## Use the Python interface

See the complete example in [architecture](../docs/architecture.md#python-usage). `Config` and `Crawler` are importable from `beyondseo`. Close the crawler after a run and avoid multiple writers to the same output directory.
