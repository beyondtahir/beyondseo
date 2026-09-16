# Search discovery that keeps its evidence

BeyondSEO can collect public search leads without an SEO subscription. It uses permitted native search responses, recorded host search results, saved result HTML or supplied URLs. Its crawler then checks the actual pages. A search snippet alone never proves a backlink, a company's services, authority or ranking.

The host assistant and native engine are separate. An assistant's search tool can work while shell networking is blocked; the reverse is also possible. Python cannot call a tool merely because the assistant sees it. The assistant executes its available search tools and passes their recorded responses through the shared import contract below. BeyondSEO does not install a search plugin or require a paid API.

## Start with the business

1. Crawl the homepage, then inspect About, Contact, main services and relevant case studies, industry and service-area pages. Use browser capture for JavaScript content. Include explicit customer, market and business context supplied by the owner.
2. Generate the evidence packet. Read the captured text and `uninspected_relevant_pages`; capture missing relevant pages before a broad comparison.
3. Review the profile using exact native-capture quotes. Keep office location, served markets, website language and requested search language separate. An English-language business in Pakistan is not automatically targeting only English-speaking countries. A domain suffix never establishes its market.
4. Write natural buyer queries in the profile review: simple category/service phrases first, then useful customer questions. Discover a broader pool, capture candidate pages, and review their profiles using the same matching keys. Reject unrelated business models before selecting competitors.

```sh
beyondseo crawl https://example.com --out runs/site --max-pages 25
beyondseo profile --crawl runs/site --out runs/business
# The assistant reads the packet and writes review.json, following the format below.
beyondseo profile --crawl runs/site --brief brief.json --review review.json --out runs/business-reviewed
beyondseo discover --queries runs/business-reviewed/queries.json --target https://example.com \
  --cache runs/search-cache --out runs/discovery
```

The native profiler prepares evidence and validates references and query context. **The assistant or human reviewer interprets the business and writes buyer language.** It does not silently turn keyword matches into business facts. Without a reviewed core offer and business model, the profile remains `needs_review` and generates no competitor queries.

A brief retains the owner's words and optional matching categories:

```json
{
  "owner_context": "We build workflow automation for local businesses and want a Pakistan-market comparison.",
  "fields": {
    "markets": [{"value": "Pakistan", "key": "pakistan"}],
    "search_languages": [{"value": "English", "key": "en"}]
  }
}
```

A review includes `target`, `reviewed_by`, `reviewed_at` (ISO date/time), `confidence`, `unknowns`, `contradictions` and `fields`. Fields are lists of claims in this shape:

```json
{
  "value": "Workflow automation",
  "key": "workflow_automation",
  "confidence": "medium",
  "evidence": [{"url": "https://example.com/services", "quote": "Exact sentence copied from the captured page."}]
}
```

The fields are `business_category`, `business_model`, `core_services`, `secondary_services`, `customer_types`, `industries`, `offices`, `markets`, `website_languages`, `search_languages`, `positioning`, `differentiators` and `commercial_intent`. Use an empty list for unknowns. Language evidence can use `{"url":"https://example.com/","field":"language","value":"en"}` when that exactly matches the captured HTML language. Quotes must match native page text. A site's self-description is evidence of its positioning, not independent verification of its promotional claims.

Use the same meaningful keys across candidate reviews. For business models, distinguish `agency`, `directory`, `marketplace`, `publisher`, `training` and `software_product`; a mixed business may have several supported models. Do not label every business an agency to pass the filter. Service and customer keys need comparable specificity: shared words such as “AI” or “business” alone are poor review judgments. Record conflicts instead of rewriting the owner's brief to fit the website.

## Write searches the customer would use

Add `search_queries` to the review object. For the example service claim and country/language brief above:

```json
{
  "search_queries": [
    {
      "query": "automation agency in Pakistan",
      "intent": "category",
      "market": "Pakistan",
      "language": "English",
      "basis": [{"field": "core_services", "key": "workflow_automation"}]
    },
    {
      "query": "Which agency in Pakistan can automate my business?",
      "intent": "question",
      "market": "Pakistan",
      "language": "English",
      "basis": [{"field": "core_services", "key": "workflow_automation"}]
    }
  ]
}
```

Write the actual requested language; a language label does not translate text. Supported intents are `category`, `service`, `question` and `comparison`. Each basis must reference an existing profile or explicit-brief field/key; market/language must match that context. This validates the context, not the semantic quality of the wording: the assistant must still review it. Keep category, service and question searches separate instead of joining every technical label, audience and agency modifier into one phrase.

These are **discovery hypotheses with unmeasured demand**, not automatically recommended keywords. Inspect result intent, business fit and available customer/search evidence before proposing a primary page target. Technical phrases can be useful for a specific buyer/use case; neither their popularity nor zero demand can be inferred from wording alone. Add question-and-answer content where it answers a relevant customer need, with a useful answer and a suitable existing page.

Legacy reviews without `search_queries` receive seeds marked `query_review_status: needs_review`. The assistant rewrites them, adds `search_queries` to the review and reruns `profile` before browser/native discovery. This is routine agent work, not another user approval step. Native `discover` skips unreviewed seeds with `query_review_required`, preserves imports and other work, and does not label this a search-provider failure. Explicit `--query` input remains available. Query lists are bounded to 20; discovery's normal per-run limit is eight.

## Browser-assisted Google search

An available host browser can perform ordinary Google navigation and pass its observed results into this workflow. Check the host browser first; use `browser-setup` for missing free local Chromium support when needed. Follow [browser search and setup](browser-search.md). A successful browser session is a separate capability from the host search tool or shell network.

## Actual search methods and fallbacks

```sh
beyondseo discover --query 'automation agency in Pakistan' \
  --market Pakistan --language English --target https://example.com --out runs/search
```

Native adapters support DuckDuckGo HTML results and Bing RSS. They retrieve robots policy first, respect restrictions, validate public destinations and TLS, and parse recognized result structures. Bing may disallow its search route: that produces a recorded robots restriction and the next permitted source is tried. No adapter promises access to its provider. The default tries DuckDuckGo first; `--provider bing-rss --provider duckduckgo-html` changes order. These are public response formats, not a service-level guarantee.

Each failed, empty or irrelevant source advances to the next configured source. There are no automatic same-provider retries. Default limits: 8 queries, 16 total native HTTP requests including robots/redirects, 12 seconds per request, 90 seconds total request budget, 100 candidates, 2 MB native responses. A required crawl delay can extend elapsed time; requests stop when the budget is exhausted. No CAPTCHA solving, proxy rotation, alternate identities or security changes are performed. Cache entries expire after 24 hours and preserve their original capture date; cache reuse is labeled. Cache files contain queries and results: keep them outside the public repository.

Search queries include requested geography and customer intent. `market` and `language` are requested context, **not a claim that the provider localized the results**. Native actual market/language remain unknown. Record actual host localization only when the host supplies it. One returned result list is not five pages, and result order is not a measured rank.

## Use the assistant's available search tool

Inspect the host's actual tool inventory and permissions. If an authorized search tool exists, run the profile-derived queries within the agreed budget. Keep its tool output/reference and exact error. Do not infer Google access from a generic browser error. Save a normalized JSON file:

```json
{"attempts":[{
  "provider":"host-search-tool-name",
  "query":"automation agency in Pakistan",
  "requested_market":"Pakistan",
  "requested_language":"English",
  "actual_market":null,
  "actual_language":null,
  "captured_at":"2026-09-16T09:00:00Z",
  "status":"results",
  "evidence":"Tool response reference or local saved response path",
  "coverage":"One returned list; pagination and localization not supplied",
  "results":[{"url":"https://candidate.example/","title":"Candidate","snippet":"Discovery lead only"}]
}]}
```

For failures use `status: "failed"`, `results: []`, exact `evidence`, and `stage: "execution"` only if command execution was actually denied; include `http_status` when observable. Use `empty_results` only when the tool successfully reported no results. Imports are operator-recorded history, not cryptographically authenticated searches. Unknown causes remain unknown.

```sh
beyondseo discover --queries runs/business-reviewed/queries.json --host-results host-search.json \
  --target https://example.com --out runs/discovery
```

Matching host results are consumed first. If they fail or have no relevant URLs, permitted native methods are attempted. An explicit broad network prohibition must be respected: use `--offline` rather than trying another route around that prohibition. A provider-specific denial does not imply that another independently permitted provider is prohibited.

## Work when live search is unavailable

```sh
# Supplied candidates or an existing source CSV:
beyondseo discover --offline --candidate https://candidate.example/services \
  --sources-csv sources.csv --out runs/supplied

# Saved Google, Bing HTML, DuckDuckGo HTML or Bing RSS responses:
beyondseo search-import --html saved.html --engine DuckDuckGo --target https://example.com \
  --query 'automation agency in Pakistan' --captured-at 2026-09-16T09:00:00Z --out runs/import
```

For multiple providers/dates, pass `--saved-search snapshots.json` to `discover`. The JSON is a list with `path`, `provider` (`google`, `bing`, `duckduckgo-html`, `bing-rss`), `query`, `captured_at`, and optional `market`/`language`. At most 20 files, 5 MB each. Empty recognized results differ from an unrecognized response or parser failure. Duplicate URLs retain every distinct query/provider/capture observation in `provenance`.

`discovery.json` contains attempts, failure evidence, fallback history and coverage; `sources.csv` remains compatible with `backlinks` and `reputation`. Continue technical, content, schema and business work when there are no leads. Describe backlink/competitor coverage as unavailable or partial. Do not translate this into “paid tools required.”

## Verify candidates and select competitors

For backlinks, run the existing source checker; only captured links count:

```sh
beyondseo backlinks --sources runs/discovery/sources.csv --target https://example.com \
  --brand Example --max-sources 20 --out runs/links
```

For competitors, crawl the exact candidate and relevant service/about/contact pages, prepare and review its profile, then:

```sh
beyondseo competitors --profile runs/business-reviewed/profile.json \
  --candidate-profile runs/candidate-a/profile.json \
  --candidate-profile runs/candidate-b/profile.json \
  --discovery runs/discovery/discovery.json --out runs/comparison
```

Selection requires core service, customer and business-model overlap plus demonstrated service sales intent. Direct competitors also need supported market overlap. Comparable agencies without that overlap become aspirational benchmarks. Directories/publishers may be query-specific search competitors after page verification; they do not become direct agencies. Discovery observations remain separately labeled search leads until that comparison is established.

Use evidenced country, region or city keys for geographic comparison. Generic `international`, `global`, `worldwide`, `remote`, `online` or `all` keys remain in the profile but cannot establish direct geographic overlap or earn geographic relevance points. Two companies saying they serve international customers does not establish that they pursue the same market.

Use this structured selection in the final report. Preserve any known conflicting About, Contact or legal-page evidence across retries and sessions; a newly readable sales page does not resolve it. If a small capture supports service overlap but leaves company identity or market coverage uncertain, retain that limit or defer the candidate. A suggested content brief for an uninspected client page is conditional, not evidence that the page lacks those answers.

Weights: service overlap 40, customer overlap 25, market overlap 15, business model 10, language 5, evidence completeness 5. These are transparent review assumptions, not an objective market score, authority score or measured rank. The output keeps supporting pages, exact evidence, differences, confidence, gaps and rejection reasons. It never fills a quota with mismatches. A competitor's feature matters only if it answers a relevant customer need for the client.

## Deliver checkable findings

Every crawl now writes `findings.json`, alongside existing `issues.json`. Enrich those observations with the reviewed business context:

```sh
beyondseo audit --crawl runs/site --profile runs/business-reviewed/profile.json \
  --discovery runs/discovery/discovery.json --out runs/audit
```

`audit --discover-queries queries.json` optionally runs discovery and still exports the audit if live methods fail; `--offline` preserves other work without live discovery. Outputs include affected URLs, observation, capture date, fact/inference/hypothesis, business relevance, action, priority rationale, acceptance check and uncertainty.

For content questions, supply `--reviewed-findings findings.json`, a JSON list with those fields and `evidence_refs` in the quote format above. Mark `absence_claim: true` when claiming a missing answer or markup. References are checked against native captures, and missing-content claims from failed/partial pages are rejected. Quote verification establishes the source text, not the correctness of a reviewer's inference. Explain the actual unanswered customer question and provide a draft improvement; never generate generic filler to satisfy a checklist.
