# Deep research that explains where a business stands

For a broad audit or a request to compare reputation, deliver a researched comparison and practical actions. A list of links alone is not the result. Keep source URLs in the evidence appendix, with a few useful examples in the narrative. Follow the user's depth and time limits; explain incomplete coverage without making them choose search providers.

## Understand the brief before searching

If the user supplies a website, inspect the homepage, About, Contact, core services and relevant cases/markets. Review the [business profile](discovery-and-competitors.md): what the company sells, to whom, where its offices are, which markets it serves and in which languages. A country suffix or English copy is not market proof. Preserve user context when the site's messaging conflicts with it.

If the user supplies only a category and country, start with that explicit brief and research the market. Do not invent their company, its backlinks or a personal rank. If they supply a URL later, inspect it and build the client cohort. Unknown facts can stay unknown while useful work continues.

Use the matching service, customer intent and geography to inspect a pool of about 15 candidate businesses before aiming for five direct comparators. The pool goal is an effort target, not permission to fill a quota. Reject directories, publishers, unrelated services and incompatible customer models. Capture relevant service, About/Contact and proof pages, normally up to four per candidate. Use fewer candidates where evidence or the user's budget requires it. Retain concise rejection reasons.

Before searching, the assistant writes reviewed buyer wording: a short category phrase, core service phrases and relevant questions about choosing, pricing or solving a customer problem. Do not turn internal service labels into a chain of technical modifiers. Use the [`search_queries` review format](discovery-and-competitors.md#write-searches-the-customer-would-use), preserving explicit user phrases and the requested language. Rewrite generated `needs_review` seeds autonomously. Competitor discovery phrases and question prompts are research hypotheses; a keyword recommendation needs intent and business-fit reasoning, a target page and a measurement plan. Search volume remains unmeasured unless a source establishes it.

Select by business fit first. Then compare dated search observations and equivalent pages' AI-readiness signals. Do not assume that a business with more attractive copy, more schema types or one higher search result is generally better or more authoritative. International benchmarks belong in a separate group unless specific customer/service/market overlap supports direct comparison.

## Start with the actual browser available to the agent

1. Inspect host tools and browser status. Record host, browser tool, managed/local/remote backend, profile mode, execution location and evidence of navigation. A laptop browser executable is not the same as a browser the host controls. Hermes and OpenClaw can expose their own managed browser surfaces; use the active supported surface.
2. Try ordinary Google search through that permitted browser first. Preserve the query, capture time, observed result URLs/order, requested market/language and actual observable context. An agent-controlled clean Chromium session may behave differently from a signed-in personal browser. Do not copy cookies, enable a real-profile mode or attach to an arbitrary debugging port to improve access.
3. If this route is unavailable, denied or challenged, record it and try an independently permitted host search tool, then native DuckDuckGo HTML/Bing RSS discovery. Stop the individual challenged route; do not bypass it or repeat it endlessly. A host-wide network restriction applies across routes.
4. When live access is unavailable, use supplied candidate URLs, saved result HTML, source CSVs and prior dated evidence. Continue the website audit and posting plan with stated limits.

A missing required local browser can use `browser-setup` when setup is authorized. Check first; a browser already available in the host does not need replacement. Details: [browser choices and setup](browser-search.md). The assistant executes host tools; the Python engine cannot control those tools by itself. No new extension is necessary.

## Plan comparable reputation research

After reviewing the client and selecting comparable businesses:

```sh
beyondseo research-plan --profile runs/client-profile/profile.json --brand "Example Company" \
  --selection runs/competitors/competitors.json --out runs/research-plan
```

The command writes `research-plan.json` and `reputation-queries-0.json`, `reputation-queries-1.json`, etc. These are planned actions, never marked completed. Defaults:

| Work | Bounded research target |
|---|---|
| Candidate pool | About 15 before choosing up to five direct comparators |
| Candidate page inspection | Up to four relevant pages each |
| Reputation discovery per site | Five query families: brand, domain, reviews, project references and partnerships |
| Source verification per site | Up to 30 distinct candidates; adjustable with `--source-limit`, identical across the cohort |
| Native fallback per site | Up to 48 requests including robots/redirects, 180 seconds |
| Comparison capture window | At most two days apart; evidence no older than seven days |

These are transparent defaults, not scientific sufficiency thresholds or a claim to exhaust the web. Honor smaller explicit task limits and label the study accordingly. Confirm brand names/aliases from the inspected sites before executing name-based queries; domain-only fallback is labeled by its query, not a guessed company name. Translate query wording when needed while retaining the same query intent across the cohort. Use a separate coherent cohort for each additional market/language; do not mix different regional studies into one rank.

For each website, execute Google/host observations first and pass them into discovery:

```sh
beyondseo discover --queries runs/research-plan/reputation-queries-0.json \
  --host-results runs/client-host-search.json --target https://example.com \
  --max-requests 48 --seconds 180 --cache runs/search-cache --out runs/client-discovery
beyondseo backlinks --sources runs/client-discovery/sources.csv --target https://example.com \
  --brand "Example Company" --max-sources 30 --out runs/client-links
```

Native first-result responses retain `search_page: 1`; this is one observed result list, not five inspected pages. Imported host/saved pages need their actual page identifier if known. Preserve all query provenance when the same URL appears repeatedly. Consolidate the full candidate pool before choosing source checks; unchecked candidates stay in the coverage denominator. Spread checks across relevant publishers/query families rather than selecting only favorable links. Document any selection judgment.

One query is not one network request: fetching robots policy, redirects and the result page can require several requests. Keep the native request budget separate from the query budget. A timeout during robots retrieval is not evidence of a disallow rule. Capture exact result destinations where available; if a browser exposes only a displayed domain, label it as domain-only and do not invent an article path or a page ranking.

Review captured source relevance, publisher relationship, editorial/profile/owned context and paid placement evidence. Leave unknowns unknown. Keep the original verification file and annotate a reviewed copy using the [reputation fields](../references/reputation.md). Search position, familiar branding and `nofollow` alone do not establish link value. Unreviewed sources cannot outrank reviewed evidence simply because their unknown quality midpoint is high.

## Compare first, rank only when supported

Create a manifest whose file paths are relative to the manifest:

```json
{
  "plan": "research-plan/research-plan.json",
  "sites": [
    {"verification": "client-links/backlinks-reviewed.json", "discovery": "client-discovery/discovery.json"},
    {"verification": "peer-links/backlinks-reviewed.json", "discovery": "peer-discovery/discovery.json"}
  ]
}
```

```sh
beyondseo compare-reputation --manifest runs/comparison-input.json --out runs/comparison
```

Include every planned cohort member. The command recalculates the existing model 1.1 from captured source evidence; it does not accept a manually supplied score. It preserves the discovered-but-unchecked source count. It requires matching completed query families, providers, observable contexts, sample counts, time windows and sufficiently reviewed evidence. Verification/review coverage cannot differ by more than ten percentage points. These are conservative comparison rules, not calibrated market metrics.

When supported, the result shows a **position for reputation evidence within this cohort**. Equal scores share a position. Overlapping sensitivity ranges can prevent a clear ordering. If coverage is weak, mismatched or incomplete, the report still compares observed facts and gaps but withholds the ordinal position and explains why. It does not ask the user to purchase access or restart the whole audit.

Keep three assessments distinct:

- **Reputation evidence:** verified source pages, independent proof, relevance, review coverage and the conservative score.
- **Observed search visibility:** exact buyer queries, provider, date, visible result order and available context. It is not a neutral universal ranking.
- **AI readiness and observed AI visibility:** comparable initial/rendered content, access/index signals, direct customer answers, entity consistency, visible proof and appropriate schema. Actual AI-answer visibility requires a recorded prompt, engine, date and citations; otherwise it remains unmeasured.

Do not collapse these into an invented single “SEO authority” metric. Explain which customer needs competitors address better and what the client should improve, with exact pages and acceptance checks. Derive keyword-to-page proposals from verified services, buyer questions and observed search intent; do not invent volumes or difficulty.

## Finish with an improvement and publishing plan

Lead with where the client stands and the highest-value actions, then the comparison, supporting examples and coverage limits. Link the full source evidence instead of flooding the main report with backlink URLs.

Use the [206-entry posting library](backlink-posting-guide.md) to propose 15 suitable sources, or 20 when requested and qualified. Check current rules and eligibility. Give the actual route, proposed article/title, outline, relevant target page, permitted link placement, posting steps and a realistic schedule. Relevant communities, technical contributions, customer/partner case studies and profiles have different purposes; raw DR values from the original sheet are unverified historical inputs, not current authority claims. Research a shortfall instead of padding the list.

Client research belongs outside the skill/repository. Before any authorized publication, run [release checks](../CONTRIBUTING.md#release-hygiene), inspect the exact diff/outgoing commits and keep private captures, transcripts, credentials and test-client identifiers out of the upload. Publication still requires the owner's authorization.
