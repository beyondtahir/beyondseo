# Keyword-to-Page Map

Every valuable keyword must map to a page, action, or ignore decision.

This is where SEO becomes execution.

## Purpose

Answer:

```text
Which page should rank for which keyword?
Which existing page needs improvement?
Which new page must be created?
Which keywords support money pages?
Which keywords are GBP/backlink/AEO actions?
Which keywords should be ignored?
```

## Required Columns

```text
Keyword
Cluster
Intent
Volume
Current Rank
Current URL
Best Competitor URL
Required Page Type
Recommended URL
Existing/New
Business Value
Priority
Main Action
Supporting Content Needed
Internal Links Needed
Schema Needed
CTA
Confidence
Notes
```

If rank/volume is unavailable:

```text
Not verified
```

Use natural buyer wording and distinguish unmeasured research hypotheses from keywords supported by actual customer/search evidence. Map each useful intent to a suitable existing page before proposing a new one. Do not create pages, force repeated exact-match wording or expand copy to a word-count target just to fill this table. Preserve the user's design, paragraph size and authorised scope.

## Page Type Options

```text
Homepage
Service page
Sub-service page
Product page
Course page
Category page
Location page
Comparison page
Cost/pricing page
FAQ/support article
Blog article
Author/expert page
Case study
GBP/service action
Backlink/authority action
No action
```

## Mapping Logic

### Existing Page Improvement

Use when:

```text
Relevant page exists.
It has ranking momentum.
It can satisfy intent after improvement.
```

Actions:

```text
Expand content
Fix title/H1/meta
Add FAQs
Add schema
Add internal links
Add trust proof
Improve CTA
Build links if authority gap exists
```

### New Page Creation

Use when:

```text
No suitable page exists.
SERP rewards dedicated pages.
Intent is distinct.
Business value is high.
```

Actions:

```text
Create URL
Write page brief
Add internal links
Add schema
Add CTA
Add support content
```

### Support Article

Use when:

```text
Intent is informational.
Question supports a money page.
SERP shows guides/articles/PAA.
```

Actions:

```text
Write answer-focused article
Link to money page
Add expert proof
Add FAQ where useful
```

### GBP Action

Use when:

```text
Near-me/map/local pack intent is strong.
```

Actions:

```text
Optimize GBP categories, services, posts, photos, reviews, Q&A, UTM links.
```

### Backlink Action

Use when:

```text
Page is good but competitors are stronger in authority.
```

Actions:

```text
Build niche/local/PR links to page or cluster.
```

## Existing Winner Handling

```text
Top 1-3: defend + conversion + CTR.
Top 4-10: review relevance, snippet and page evidence; an improvement does not guarantee top-three placement.
Top 11-20: investigate the opportunity and effort; position alone does not prove a fast win.
```

## Missing Money Page Handling

For high-intent missing pages:

```text
Create dedicated page.
Map support articles.
Add homepage/service hub links.
Add schema.
Add page-specific CTA.
Add local proof if relevant.
```

## Examples

### Local Dental

```text
Cluster: Family Dentist Arlington Heights
Intent: Local service
Recommended URL: /family-dentist-arlington-heights/
Action: Create local service page
Schema: Dentist, Service, LocalBusiness, FAQPage
CTA: Book family appointment
```

### Academy

```text
Cluster: AI Automation Course
Intent: Course/enrollment
Recommended URL: /ai-automation-course/
Action: Improve a suitable existing course page, or propose a dedicated page if evidence supports distinct intent; answer the buyer's questions without a fixed word count
Schema: Course, Organization, Person, FAQPage
CTA: Join AI Automation Class
```

## Internal Link Mapping

Each money page should have:

```text
Homepage link
Navigation/service/category hub link
Relevant supporting article links where they help the reader
Related page links
Breadcrumbs
```

Use natural anchors.

Good:

```text
AI automation course
dental implants in Arlington Heights
emergency dental care
```

Bad:

```text
best dentist arlington heights best dentist arlington heights
```

## Schema Mapping

The types below are candidates, not a requirement to apply every type. Use only appropriate factual markup that matches the visible content. FAQPage applies only to genuine suitable FAQ content; schema validity and search-feature eligibility are separate checks. Do not invent courses, credentials, ratings or local offices to populate schema.

```text
Service page → Service + Organization/LocalBusiness + FAQPage + Breadcrumb
Local service page → LocalBusiness/Dentist/Service + FAQPage + Breadcrumb
Course page → Course + Organization + Person + FAQPage + Breadcrumb
Article → Article + Person + Organization + Breadcrumb
Product → Product + Breadcrumb
```

## Output Template

```text
## Keyword-to-Page Map

| Keyword | Cluster | Intent | Current Rank | Current URL | Recommended URL | Existing/New | Priority | Main Action |

### New Pages Required
| Page | Keywords | Why | Priority |

### Existing Pages to Improve
| Page | Keywords | Fix | Priority |

### Support Articles Required
| Article | Supports | Intent | Priority |

### GBP Actions
| Keyword | GBP Action | Priority |

### Backlink/Authority Actions
| Page/Cluster | Link Need | Priority |
```

## CSV Template

```csv
Keyword,Cluster,Intent,Volume,Current Rank,Current URL,Best Competitor URL,Required Page Type,Recommended URL,Existing/New,Business Value,Priority,Main Action,Supporting Content Needed,Internal Links Needed,Schema Needed,CTA,Confidence,Notes
```

## Final Gate

The map is complete when every valuable keyword has:

```text
Intent
Target page
Action
Priority
CTA
Internal link plan
Schema plan
Measurement plan
```
