# Schema and Structured Data Audit

This file defines BeyondSEO's schema audit process.

Schema is not magic ranking dust. It helps search engines and answer engines understand entities, page types, relationships, products, courses, services, local businesses, breadcrumbs, FAQs, and trust signals.

---

## 1. Purpose

Schema audit answers:

```text
Is the site using accurate structured data that matches visible content and supports search understanding?
```

---

## 2. Core Rules

Schema must be:

```text
Accurate
Visible-content backed
Relevant to page type
Valid JSON-LD or supported format
Not spammy
Not misleading
Not duplicated/conflicting
```

Never recommend:

```text
Fake review schema
Hidden FAQ schema
Fake ratings
Misleading medical/course claims
Schema that does not match visible content
```

---

## 3. Inputs

Use:

```text
Page HTML/source
Crawl output
Schema validator output
Rich Results Test output
BeyondSEO local crawl output
CMS templates
Existing JSON-LD
Visible page content
```

---

## 4. Schema Types to Check

Common types:

```text
Organization
LocalBusiness
MedicalBusiness
Dentist
Physician
Service
Course
Product
Article
FAQPage
BreadcrumbList
Person
Review / AggregateRating
VideoObject
Event
WebSite
SearchAction
```

Use only where relevant.

---

## 5. Sitewide Schema

### Organization

Use for the main brand/business entity.

Fields:

```text
name
url
logo
sameAs social/profile links
contactPoint if useful
founder/person if relevant
address if physical business
```

### WebSite

Useful for:

```text
site name
url
potential SearchAction if site search exists
```

### BreadcrumbList

Useful for:

```text
service pages
course pages
blog articles
category pages
location pages
```

---

## 6. Local Business Schema

For local businesses, consider:

```text
LocalBusiness
Dentist
MedicalBusiness
Physician
ProfessionalService
LegalService
RealEstateAgent
Store
Restaurant
```

Fields:

```text
name
url
image/logo
telephone
address
geo
openingHours
priceRange if appropriate
sameAs
areaServed
services if useful
```

Rules:

```text
NAP must match visible page and GBP/citations.
Use the most specific subtype when accurate.
Do not add fake ratings.
```

---

## 7. Service Schema

Use for service pages when the service is clearly described.

Fields:

```text
name
description
provider
areaServed
serviceType
url
offers if pricing is visible and accurate
```

Examples:

```text
Dental Implants in Arlington Heights
Emergency Dentist in Arlington Heights
AI Automation Consulting
Website SEO Audit
```

Service schema supports strong page content. It does not replace content.

---

## 8. Course Schema

Use for course/academy pages.

Fields:

```text
name
description
provider
instructor if applicable
courseMode
educationalLevel if useful
teaches
offers if pricing/enrollment visible
url
hasCourseInstance if applicable
```

Rules:

```text
Only add Course schema to real course pages.
Course details must be visible.
Do not fake certification claims.
```

Course pages should often include:

```text
Organization schema
Person/instructor schema
Breadcrumb schema
FAQPage if visible FAQs exist
```

---

## 9. Article Schema

Use for blog/support articles.

Fields:

```text
headline
description
author
publisher
datePublished
dateModified
image
mainEntityOfPage
```

For YMYL articles:

```text
author credentials
reviewer if applicable
dateModified
sources/citations where needed
```

---

## 10. FAQPage Schema

FAQPage schema should only be used when:

```text
FAQ questions and answers are visible on the page.
Questions are genuinely useful.
Answers are not spammy.
FAQ content matches page topic.
```

Do not promise rich results. Search result display can change.

Use FAQ schema primarily for:

```text
clarity
AEO/GEO extraction support
structured understanding
```

not as a guaranteed CTR boost.

---

## 11. Review and Rating Schema

Use carefully.

Allowed only when:

```text
Reviews/ratings are visible.
Reviews are about the same entity/page topic.
The business is allowed to mark them up.
Ratings are authentic.
```

Avoid:

```text
Fake reviews
Self-serving misleading review markup
Hidden reviews
Sitewide duplicate aggregate ratings
Ratings copied from third-party platforms without proper context
```

If unsure, avoid review schema and use visible testimonials without markup.

---

## 12. Person Schema

Use for:

```text
Founder
Doctor
Dentist
Instructor
Author
Consultant
Expert reviewer
Speaker
```

Fields:

```text
name
url
image
jobTitle
worksFor
sameAs
knowsAbout
alumniOf if relevant and visible
award if visible/verifiable
```

Person schema supports E-E-A-T and entity clarity.

---

## 13. Medical/Dental Schema

For medical/dental sites, consider:

```text
Dentist
MedicalBusiness
Physician
MedicalClinic
Service
Person
FAQPage
BreadcrumbList
Article
```

Rules:

```text
Do not add medical claims not visible on page.
Do not exaggerate outcomes.
Include disclaimers where appropriate.
Make doctor credentials visible.
```

---

## 14. Product/Ecommerce Schema

Use for product pages.

Fields:

```text
name
image
description
brand
sku if available
offers
price
availability
review/aggregateRating if valid
```

Product schema should match visible product information.

---

## 15. VideoObject Schema

Use if video is embedded and important.

Fields:

```text
name
description
thumbnailUrl
uploadDate
duration
contentUrl or embedUrl
transcript if available
```

Useful for:

```text
course previews
doctor explanations
AI tutorials
product demos
```

---

## 16. Schema Validation Checks

Check:

```text
Syntax errors
Invalid fields
Missing required fields
Duplicate schema
Conflicting entities
Wrong page type schema
Schema not matching visible content
Old/stale organization info
Broken logo/image URLs
Wrong canonical/mainEntityOfPage
```

---

## 17. Schema Mapping by Page Type

```text
Homepage:
Organization, WebSite, LocalBusiness if local

Service page:
Service, BreadcrumbList, FAQPage if visible

Local service page:
LocalBusiness/Dentist/MedicalBusiness + Service + BreadcrumbList + FAQPage if visible

Course page:
Course, Organization, Person, BreadcrumbList, FAQPage if visible

Blog article:
Article, Person, Organization, BreadcrumbList, FAQPage if visible

Author/expert page:
Person, Organization relationship

Product page:
Product, BreadcrumbList

Video page:
VideoObject, Article if article-style
```

---

## 18. Schema Audit Output Template

```text
## Schema Audit

### Current Schema Found
| Page/Template | Schema Type | Status | Issue |

### Missing Schema Opportunities
| Page/Template | Recommended Schema | Why | Priority |

### Errors / Risks
| Issue | Affected Pages | Fix | Priority |

### Implementation Notes
- Use JSON-LD.
- Match visible content.
- Validate before deployment.
- Test key templates after deployment.
```

---

## 19. JSON-LD Implementation Rules

Prefer JSON-LD.

Implementation must:

```text
Inject per page/template
Use canonical URL
Use correct entity IDs where possible
Avoid duplicate Organization objects with conflicting data
Use stable @id references
Validate before publishing
```

Example entity ID pattern:

```text
https://example.com/#organization
https://example.com/#website
https://example.com/about/#person-founder
https://example.com/service-page/#service
```

---

## 20. Developer Acceptance Criteria

When giving schema tasks to developers:

```text
Schema is server-rendered or present in final HTML.
Each page template gets correct schema type.
Fields match visible content.
No fake ratings/reviews.
No syntax errors.
Google Rich Results Test passes where applicable.
Schema validator shows no critical errors.
Canonical URLs match schema URLs.
```

---

## 21. Common Mistakes

Do not:

```text
Add schema to fix weak content.
Use FAQ schema with hidden FAQs.
Use fake review ratings.
Use wrong local business subtype.
Use Course schema for a generic blog post.
Duplicate Organization schema with different names.
Forget breadcrumbs.
Forget Person schema for experts/instructors.
Promise rich results.
```

---

## 22. Final Schema Gate

Schema is ready when:

```text
It matches visible content.
It is technically valid.
It supports the page/entity.
It does not mislead.
It helps search and answer engines understand the site.
```
