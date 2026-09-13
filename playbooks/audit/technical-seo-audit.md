# Technical SEO Audit

This file defines BeyondSEO's technical SEO audit process.

Technical SEO answers one question:

```text
Can search engines discover, crawl, index, render, understand, and rank the right pages?
```

If the answer is no, content and backlinks will underperform.

---

## 1. When to Use

Use this file for:

```text
Technical SEO audit
Crawlability audit
Indexability audit
Sitemap/robots review
JavaScript rendering review
Redirect/canonical audit
Page speed/Core Web Vitals review
Technical implementation brief
```

---

## 2. Inputs

Use any available:

```text
Website URL
Sitemap XML
Robots.txt
BeyondSEO local crawl output
Native crawler
Screaming Frog export
Sitebulb export
GSC coverage/indexing export
PageSpeed/Core Web Vitals data
Server logs if available
CMS/platform access if available
HTML/source inspection
Schema validator output
```

---

## 3. Technical Audit Categories

Audit these categories:

```text
Crawlability
Indexability
URL architecture
Sitemap
Robots.txt
Status codes
Redirects
Canonicals
Duplicate URLs
JavaScript rendering
Mobile usability
Core Web Vitals / speed
Internal link accessibility
Schema validity
International/language setup if relevant
Security/HTTPS
Tracking/measurement basics
```

---

## 4. Crawlability Checks

Check:

```text
Important pages linked from navigation/homepage
Important pages included in sitemap
Important pages reachable within 3 clicks where possible
No critical pages blocked by robots.txt
No critical pages hidden behind forms/login
No crawl traps from filters/search parameters
No infinite calendar/tag/page combinations
No broken internal links to money pages
```

Issue examples:

```text
Service pages exist but are not linked from homepage or main service hub.
Important course pages are only accessible after JavaScript interaction.
Location pages are missing from sitemap.
```

Impact language:

```text
If Google cannot discover or crawl these pages reliably, rankings will not scale.
```

---

## 5. Indexability Checks

Check:

```text
robots meta index/noindex
X-Robots-Tag
Canonical target
HTTP status
Sitemap inclusion
Duplicate/canonicalized versions
GSC indexing status if available
```

Critical issues:

```text
Money page has noindex
Canonical points to wrong page
Page returns 404/500
Page redirects unexpectedly
Page blocked by robots
Sitemap includes non-indexable URLs
Indexed pages are thin/duplicate
```

Output:

```text
URL
Indexability issue
Business impact
Fix
Priority
```

---

## 6. Sitemap Audit

Check:

```text
Sitemap exists
Sitemap is referenced in robots.txt
Sitemap includes important pages
Sitemap excludes noindex/canonicalized/404 URLs
Sitemap is not bloated with tags/search/utility pages
Lastmod is accurate where used
Multiple sitemap files are logical
```

Common fixes:

```text
Regenerate sitemap
Remove non-indexable URLs
Add missing money pages
Submit sitemap in GSC
Split large sitemap if needed
```

---

## 7. Robots.txt Audit

Check:

```text
Robots.txt exists
Sitemap reference exists
Important sections are not blocked
Admin/private sections are blocked where appropriate
Staging/dev paths are blocked or not indexable
No accidental Disallow: /
```

Important rule:

```text
Robots blocking is not the same as noindex. A blocked URL may still appear in search if discovered elsewhere.
```

---

## 8. Status Code Audit

Check:

```text
200 OK for indexable pages
301 for permanent redirects
302/307 only when temporary
404 for removed pages
410 if intentionally gone
5xx server errors
Soft 404s
Redirect chains
Redirect loops
Mixed HTTP/HTTPS
www/non-www inconsistency
```

Priority:

```text
Critical: 5xx on money pages, broken homepage, redirect loops.
High: broken service/product/course pages.
Medium: broken blog/support pages with links.
Low: old irrelevant URLs.
```

---

## 9. Redirect Audit

Check:

```text
HTTP to HTTPS
www vs non-www
Trailing slash consistency
Old URLs to new relevant pages
Redirect chains longer than 1 hop
Redirect loops
302 used where 301 should be used
```

Good redirect:

```text
/old-service/ → /new-service/
```

Weak redirect:

```text
/old-service/ → homepage
```

unless no relevant replacement exists.

---

## 10. Canonical Audit

Check:

```text
Self-referencing canonical on indexable pages
Canonical target is 200/indexable
No canonical to unrelated page
No canonical to HTTP version
No canonical conflicts with sitemap
No duplicate canonical across distinct pages
```

Common high-risk issue:

```text
All dynamic course pages canonicalize to homepage.
```

Impact:

```text
Search engines may consolidate or ignore pages, preventing them from ranking independently.
```

---

## 11. URL Architecture

Check:

```text
Readable URLs
Keyword/service relevance
No unnecessary parameters
No duplicate case variants
No confusing dynamic IDs for indexable pages
Logical folder structure
Location/service URLs where local SEO matters
```

Good:

```text
/ai-automation-course/
/family-dentist-arlington-heights/
/dental-implants/
```

Weak:

```text
/page?id=123
/service1
/category/uncategorized/post-92
```

---

## 12. JavaScript Rendering Audit

This is critical for React, SPA, Lovable, and app-style websites.

Check:

```text
Does raw HTML contain title/meta?
Does raw HTML contain H1/H2/body content?
Does content appear only after JavaScript?
Are course/service pages crawlable?
Are dynamic routes pre-rendered?
Is schema injected into HTML?
Do meta tags change per route?
```

Red flags:

```text
No crawlable H1/H2
Very little body content in source
Same title/meta on all routes
Client-side-only course pages
Content visible to users but weak for crawlers
```

Recommended fixes:

```text
SSR
Static pre-rendering
Dynamic metadata per route
Server-rendered landing pages
Static JSON-LD injection
Sitemap generation for dynamic routes
```

Severity:

```text
Critical if public money pages are not crawlable.
High if important content is visible only after JS.
Medium if support pages are affected.
```

---

## 13. Mobile and Speed Audit

Check if data/tools exist:

```text
Core Web Vitals
LCP
INP
CLS
TTFB
Image weight
JavaScript bundle size
Render-blocking resources
Font loading
Lazy loading
Mobile layout issues
CTA visibility on mobile
```

Do not rely only on lab score. Use field data if available.

SEO impact:

```text
Speed rarely fixes weak strategy by itself, but slow pages reduce crawl efficiency, UX, and conversions.
```

---

## 14. Image and Media Audit

Check:

```text
Oversized images
Missing alt text
Generic file names
Uncompressed images
No lazy loading
Hero image hurting LCP
Video embeds slowing page
No image dimensions
```

Alt text should describe the image naturally. Do not keyword-stuff alt text.

---

## 15. Internal Link Accessibility

Check:

```text
Navigation links are crawlable <a href>
Important links are not only JavaScript click handlers
Footer links work
Breadcrumbs exist where useful
Money pages receive internal links
Support articles link back to money pages
Broken internal links are fixed
```

---

## 16. Security and HTTPS

Check:

```text
HTTPS active
No mixed content
One canonical protocol
Valid certificate
No indexable staging/dev URLs
No insecure forms
```

---

## 17. Tracking Basics

Technical SEO should check measurement foundation:

```text
GA4 installed
GSC verified
Sitemap submitted
Conversion events configured
GBP links UTM-tagged
Form submissions trackable
Phone/WhatsApp clicks trackable
Thank-you pages not indexed if thin/duplicative
```

If lead goals exist and tracking is missing, mark as high priority.

---

## 18. Severity Rules

Use:

```text
Critical: blocks crawling, indexing, rendering, tracking, or money-page access.
High: strongly reduces ranking or conversion potential.
Medium: improves performance or clarity but not blocking.
Low: cleanup or polish.
```

Examples:

```text
Critical: /services/ noindexed.
High: 28 service pages have duplicate H1/title patterns.
Medium: multiple images missing alt text.
Low: meta description slightly long.
```

---

## 19. Technical Audit Output Template

```text
## Technical SEO Audit

### Summary
[2-4 lines]

### Critical Issues
| Issue | Evidence | Impact | Fix | Priority |

### High Issues
| Issue | Evidence | Impact | Fix | Priority |

### Medium / Low Issues
| Issue | Evidence | Fix |

### Technical Roadmap
Week 1:
Week 2:
Month 1:
Month 2:

### Data Missing
[What still needs GSC/crawl/PageSpeed/server logs]
```

---

## 20. Common Mistakes

Do not:

```text
Over-prioritize tiny meta length issues.
Ignore JavaScript rendering.
Ignore indexability.
Ignore canonical conflicts.
Ignore conversion tracking.
Call a site technically healthy without crawl evidence.
Recommend full rebuild when template fixes can solve it.
```

---

## 21. Final Technical Audit Gate

Before finalizing:

```text
Can important pages be discovered?
Can they be crawled?
Can they be indexed?
Can their content be rendered?
Can Google understand their topic?
Can users convert?
Can performance be measured?
```

If any answer is no, explain the fix.
