# What website observations establish

| Evidence | Supported conclusion | Unsupported shortcut |
|---|---|---|
| HTTP status/headers/HTML | The crawler observed that response at that time | Google has indexed or ranked the URL |
| Robots rules | Whether BeyondSEO may crawl under the retrieved policy | Whether every bot may crawl, or whether the URL is absent from search |
| noindex/canonical declaration | The declaration exists and should be reviewed against page intent | Google accepted it, or every noindex/canonical is a defect |
| JSON-LD parsing | JSON syntax and type declarations | Schema.org semantic validity or rich-result eligibility |
| HTML word count | Amount of extracted text by this method | Content usefulness or a required word count |
| Sitemap + sampled link graph | A URL lacks observed inbound anchors in the sample | A confirmed whole-site orphan |
| Fetch elapsed time | Local wait/retry/transfer duration | TTFB, page-load performance, LCP, INP or CLS |
| On-site outbound links | This page links to these destinations | Its complete inbound backlink profile or independent reputation |
| BeyondSEO Reputation Score | A transparent estimate for the observed source sample, with a range and coverage | Whole-web backlink totals, engine authority, sentiment or ranking predictions |
| Named competitor pages | Observed content/structure differences | Competitor ranking, search demand or traffic |
| Answer blocks, entity pages, proof links | Content readiness observations | Visibility or citation by an AI answer system |
| Dated supplied GSC/analytics exports | Metrics as defined and sampled by those exports | Whole-market demand, a ranking guarantee or unobserved conversions |

The local runtime has no search-engine, Maps, Trends, social-platform or analytics connector. Supplied exports and dated observations can support the relevant playbooks without a runtime dependency on those products. Do not request a plugin merely to run the website crawler.

Retained playbook examples are not mechanical minimums. Replace arbitrary word counts with the questions and evidence the page needs. Do not invent authority, health or AI-readiness scores; a score requires a stated rubric, coverage and missing-data treatment. Content plans can improve structure and clarity but do not guarantee rankings or citations. Distinguish GSC search-query impressions/clicks from business inquiries and leads.

Official references checked during this revision:

- [Robots Exclusion Protocol, RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html): agent groups, path matching and access outcomes. The crawler's stricter scope/error choices are documented separately.
- [Sitemaps protocol](https://www.sitemaps.org/protocol.html): XML URL sets, indexes and compressed sitemaps.
- [Google robots meta and X-Robots-Tag documentation](https://developers.google.com/search/docs/crawling-indexing/robots-meta-tag): directive semantics and agent targeting.
- [BeautifulSoup documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/): DOM parsing, selector extraction and parser differences.
- [Playwright network documentation](https://playwright.dev/python/docs/network): local browser routing and resource interception.
- [Colorama package documentation](https://pypi.org/project/colorama/): terminal color portability.

These references document particular mechanisms. They are not evidence for a particular website's rankings or for every recommendation in the specialist playbooks. Recheck current official search-engine guidance when a task depends on eligibility or platform-specific rules.
