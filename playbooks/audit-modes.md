# Audit modes

1. **Local crawl:** default for a website URL; raw HTML, sitemaps, robots, links, metadata and content evidence.
2. **Local rendered comparison:** optional local Chromium produces a second representation for JavaScript-heavy pages. Preserve raw observations.
3. **Local crawl plus files:** add supplied GSC, analytics, review, search-observation or backlink exports. Attribute metrics to their actual source/date.
4. **Files only:** analyze supplied artifacts when live access is unavailable. Do not label historical data as a current crawl.
5. **Advisory:** outline checks when there is no executable runtime and no usable data. Do not claim a completed audit.

No mode implies complete information. Report coverage and unverified measurements with each result.
