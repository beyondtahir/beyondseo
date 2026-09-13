# Entity SEO Knowledge Graph System

Entity SEO means Google, Bing, and AI systems should know exactly who or what the entity is.

---

## 1. What Entity SEO Means

For a person, company, academy, product, or local business, answer:

```text
Who is this?
What do they do?
Where are they based?
Who founded it?
What are they known for?
Which profiles are official?
What proof exists?
```

---

## 2. Required Entity Pages

Create or improve:

```text
/about/
/founder-name/
/company-profile/
/team/
/services/ or /courses/
/reviews/
/case-studies/
/certifications/
/media/
/contact/
/social-profiles/
/faq/
```

---

## 3. Person Entity Data

```text
Full name
Public name / alias
Job title
Company
Location
Bio
Expertise
Certifications
Awards
Books / research / projects
Media mentions
Social profiles
Official website
Profile image
Contact / schedule page
```

---

## 4. Organization Entity Data

```text
Brand name
Legal/public name
Logo
Website
Address/service area
Phone/email
Founder
Founded year
Services/courses/products
Certifications
Reviews
Media mentions
Social profiles
External authoritative profiles
```

---

## 5. Schema

Use:

```text
Organization
Person
ProfilePage
LocalBusiness
Course
Service
Article
BreadcrumbList
sameAs
Review/AggregateRating only when valid
```

---

## 6. SameAs Strategy

Connect official profiles:

```text
LinkedIn
YouTube
Instagram
Facebook
X/Twitter
Trustpilot
Google Business Profile
Crunchbase
ORCID
GitHub
Medium
Substack
Press profiles
Industry association profiles
```

Only use real official profiles.

---

## 7. Review Compilation Page

If reviews exist, create:

```text
/reviews/
/student-reviews/
/client-results/
/why-clients-trust-us/
```

Page should include:

```text
Review summary
Review themes
Real quotes where permitted
Links to external review platforms
Service/course grouping
Proof links
CTA
```

---

## 8. Evidence Workflow

Use local crawl JSON-LD, organization/person pages and outbound profile links to map entity declarations. Inspect known public proof URLs in their own scoped crawl. Maps performance, broad mention discovery and private profile data are not supplied by this crawler.

## 9. Entity SEO Report Template

```text
Entity:
Known names:
Official website:
Official profiles:
Missing profiles:
Missing pages:
Schema needed:
Review/proof assets:
Inconsistency issues:
Priority actions:
```


For current guidance and measurement limits, read `references/measurement-boundaries.md` from the skill root.
