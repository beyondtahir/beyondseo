# Keyword Clustering

Keyword clustering groups search terms by intent so the agent builds the right pages instead of creating duplicate, cannibalized, or useless content.

## Purpose

Answer:

```text
Which keywords belong together?
Which keywords need separate pages?
Which keywords are support topics?
Which questions should become AEO blocks?
Which should be ignored?
```

## Inputs

```text
Keyword list
SERP top results
GSC queries
Competitor pages
Existing sitemap
Page inventory
People Also Ask
Related searches
Business services/products/courses
```

## Cluster Types

### Money Page Cluster

High-intent searches that deserve a commercial landing page.

Example:

```text
dental implants arlington heights
implant dentist arlington heights
dental implant dentist near me
```

Target:

```text
/dental-implants-arlington-heights/
```

### Service Subpage Cluster

Specific treatment/service needs its own page.

```text
all on 4 dental implants arlington heights
full arch dental implants arlington heights
```

Target:

```text
/all-on-4-dental-implants-arlington-heights/
```

### Support Article Cluster

Informational phrases that support a money page.

```text
dental implant cost
dental implants vs dentures
how long do dental implants last
```

Target:

```text
/dental-implant-cost/
```

Link to:

```text
/dental-implants/
```

### Course Cluster

```text
AI automation course
AI automation course Pakistan
no-code automation course
```

Target:

```text
/ai-automation-course/
```

### AEO Question Cluster

```text
what are AI agents
how do dental implants work
how to learn prompt engineering
```

Target:

```text
FAQ section, answer block, or support article
```

## SERP Similarity Rule

If keywords show the same ranking URLs and same page type, they usually belong on one page.

If SERPs show different page types or different intent, create separate pages.

Example:

```text
"dental implants arlington heights" and "implant dentist arlington heights" can usually share one page.
"all on 4 dental implants arlington heights" likely needs a dedicated subpage.
"how much do dental implants cost" usually needs a cost/support page.
```

## One Page vs Multiple Pages

Use one page when:

```text
Intent is the same.
SERP overlap is high.
One page can answer the topic naturally.
```

Use separate pages when:

```text
Intent is different.
Service/product/course is different.
SERP page types differ.
Topic needs deep standalone treatment.
Location/service combination is important.
```

Use support articles when:

```text
Question is informational.
SERP shows guides/PAA.
Topic supports a money page.
```

## Hierarchy

```text
Homepage / main category
↓
Hub money pages
↓
Sub-service pages
↓
Support articles
↓
FAQ/answer blocks
```

Dental example:

```text
/dentist-arlington-heights/
↓
/family-dentist-arlington-heights/
/emergency-dentist-arlington-heights/
/dental-implants/
↓
/dental-implant-cost/
/all-on-4-vs-dentures/
```

Academy example:

```text
/ai-course-pakistan/
↓
/ai-automation-course/
/ai-agents-course/
/prompt-engineering-course-pakistan/
↓
/what-is-ai-automation/
/ai-agents-explained-urdu-hindi/
```

## Cluster Fields

```text
Cluster name
Primary intent
Primary keyword
Secondary keywords
AEO questions
Target page type
Recommended URL
Existing page?
Current rank if available
Competitor page example
Business value
Priority
Internal link targets
Required support articles
```

## Output Template

```text
## Keyword Clusters

| Cluster | Intent | Primary Keyword | Target URL | Existing/New | Priority |

### Cluster Details
Cluster:
Target URL:
Intent:
Primary keyword:
Secondary keywords:
Questions:
Required sections:
Supporting articles:
Internal links:
Competitor example:
Priority:
```

## Mistakes to Avoid

```text
One page per keyword variation
Merging different intents
Using blogs for commercial intent
Creating thin local doorway pages
Ignoring existing pages
Ignoring SERP similarity
Ignoring internal linking
```

## Final Gate

A cluster is ready when:

```text
Intent is clear.
Target page is clear.
Support content is mapped.
Internal links are planned.
Cannibalization risk is reduced.
Priority is assigned.
```
