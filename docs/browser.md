# Read pages that use JavaScript

BeyondSEO uses a local Chromium browser to execute page scripts, load public dependencies, wait for content and scroll through a bounded part of the page. The raw HTTP response is always retained as a separate representation.

## Three modes

| Mode | Behavior | Useful when |
|---|---|---|
| `auto` | Render responses with scripts and little main text or no H1 | Starting an audit without knowing how the site is built |
| `http` | Read the initial response only | Fast discovery, server-rendered sites or no browser installation |
| `browser` | Render every successfully extracted HTML page | Dynamic content matters even on pages with substantial initial text |

The command line defaults to `auto`; the Python `Config` defaults to `http` so a library call does not silently require Chromium. The older `--render` flag remains an alias for browser mode. Screenshots also select browser mode.

## Wait for something meaningful

```sh
beyondseo scrape https://example.com/articles --out runs/articles \
  --mode browser --wait-for-selector "article h2" \
  --render-wait-ms 2000 --render-settle-ms 3000 --timeout 60
```

The renderer waits for DOMContentLoaded, then an optional visible CSS selector, then the configured minimum observation time. It samples body text and link count until they are stable or the settling window ends. It then performs the configured number of scrolls. The selector uses CSS syntax; custom extraction uses the same portable CSS approach.

A stability observation is a signal, not proof that all asynchronous work is complete. A selector timeout, request budget or deadline stays visible in the result.

## Scroll and capture

```sh
beyondseo scrape https://example.com --out runs/visual \
  --mode browser --scroll-steps 5 --screenshot --timeout 60
```

Scrolling moves by part of a viewport and waits briefly between steps. Use 0 to disable it; at most 20 steps are allowed. This can expose lazy-loaded text and links, but it is not an unlimited infinite-scroll harvester.

Screenshots capture a 1440 × 1000 viewport after returning to the top. Images and fonts are fetched for screenshot runs. Ordinary text runs skip images/fonts and media to save requests. Use `--headed` to see the browser window locally.

## Website dependencies

The default `--browser-assets public` permits public HTTP(S) asset/API hosts observed in page requests. Each request still passes through BeyondSEO's transport, address checks, pacing, robots policy and body-size limit. These dependencies do not become crawl-page targets. Cross-site frames are not loaded as page documents.

For a tighter run:

```sh
beyondseo scrape https://example.com --out runs/restricted \
  --mode browser --browser-assets allowlist \
  --render-allow-host cdn.example.com --render-allow-host api.example.com
```

Allowed GET and CORS OPTIONS requests preserve selected origin-bound browser headers needed by public website APIs. Cookies are not imported or forwarded. POST requests, media, WebSockets, service workers and resource redirects are restricted. Some websites rely on those behaviors and need a future adapter. These restrictions differ from a normal interactive browser and can change the page.

## Robots policy

`--robots respect` is the default. The crawler applies matching robots rules and crawl delay. An unavailable robots file is distinct from a denied resource: most 4xx responses on the robots URL permit attempts to public pages, while network/server failures and 429 defer requests. See [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html#section-2.3.1.3).

`--robots ignore` is an explicit choice for authorized crawling. It records the override, ignores robots allow/disallow and crawl-delay decisions, and retains the configured request spacing. The robots response is still collected as evidence. Authentication, TLS validation, address checks and server response handling remain active.

## Understand a failed capture

Read the page's `rendered` object in `pages.jsonl`:

- `error`: browser/transport exception, if any.
- `javascript_errors`: captured page errors, capped at 20.
- `readiness`: selector result, text stability and deadline observations.
- `blocked_request_log`: the first 100 blocked requests with their reasons.
- `http_events`: recorded attempt status and failure details.
- `content_warning`: empty main-text extraction.
- `scroll_steps_completed`: actual scroll steps performed.

A 403, 429 or recognized challenge is recorded separately from local restrictions. A successful HTTP response with an empty DOM may be an application failure. BeyondSEO does not solve CAPTCHAs, rotate identities or claim universal access. The aim is inspectable content and a clear account of what was actually read.
