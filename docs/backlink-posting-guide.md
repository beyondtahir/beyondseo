# Find the right places to publish

BeyondSEO uses your website and the supplied posting library to answer: **where should I publish, what should I write, how do I post it, and when should I do it?**

The catalog source is **Free article website.pdf**: 241 rows, 237 distinct URL strings and 206 website/community entries after grouping duplicate routes. Full articles, community posts, answers, profiles and resource sites are different opportunities. [Browse the catalog](backlink-source-catalog.md).

## Ask for a useful plan

> Review my website and recommend 15 suitable free posting sources. For each, give me a direct route, explain why it fits, suggest a specific article or post, identify the page to link, explain the posting steps and schedule it around two pieces per week. Show any unconfirmed free terms, authority claims or eligibility. Draft the first two articles.

Ask for 20 if your scope needs it. A focused niche may have fewer qualifying sites in the current reviewed subset. BeyondSEO should research the missing relevant opportunities or explain the shortfall; it should not add unrelated sites to satisfy a number.

## How the library works

- The raw CSV preserves every visible row, including duplicate source URLs and the sheet's DR values.
- The site catalog groups account, feed, post and member URLs for the same website. Separate communities remain identifiable.
- Public posting guidance has been reviewed for 22 destinations. Catalog review dates use UTC. This does not certify signup success, editorial acceptance, a free promotional placement, live backlink attributes or indexing.
- Unreviewed entries remain visible for research. Closed, unavailable and ineligible sources are excluded from automatic selection.
- Dated guidance needs refreshing. The helper stops selecting records older than 90 days; an actual posting recommendation still checks current rules at the time of use.

Hacker News requires human-written contributions and disallows generated or AI-edited text. Medium excludes AI-generated and primarily promotional pieces from General Distribution. Help the user understand these limits; do not present an assistant-written draft as suitable for every platform. [Hacker News guidance](https://news.ycombinator.com/newsguidelines.html) · [Medium distribution rules](https://help.medium.com/hc/en-us/articles/360006362473-Medium-s-Distribution-Guidelines-How-curators-review-stories-for-Boost-General-and-Network-Distribution).

## Browse or filter

```sh
python3 scripts/backlink_sources.py
python3 scripts/backlink_sources.py --platform Medium
python3 scripts/backlink_sources.py --category technology --status guidance_reviewed
python3 scripts/backlink_sources.py --kind article --format json
```

Use `py -3` instead of `python3` on Windows. Browsing and planning use Python's standard library and make no model or network calls.

## Draft a plan from website facts

Save a copy of [the example profile](../examples/posting-profile.json) as `../client-runs/business.json`, outside the skill folder. Replace its example business, target URLs, audience and topics with facts observed on the user's actual website. Record the crawl/source date in `evidence_basis`. Do not invent a service URL or mark a planned resource as already live.

```sh
python3 scripts/backlink_sources.py --profile ../client-runs/business.json --limit 15 --out ../client-runs/posting-plan
```

This writes `posting-plan.md`, `posting-plan.csv` and `posting-plan.json`. Each recommendation contains a specific title/action, outline, target page, posting instructions, restrictions, guidance sources, proposed week and verification checklist.

The helper selects and organizes candidates. It does not crawl the supplied website, research new publishers, write finished prose or submit anything. The full skill inspects the website, fills research gaps, personalizes the plan and writes the requested drafts. [Selection and delivery standard](../playbooks/backlink-system/free-paid-backlink-source-library.md).

`topics` are matching tags such as `technology`, `business`, `education`, `creative`, `travel` or `wellness`. Use only genuine capabilities in `assets`: `public_code`, `public_demo`, `public_resource` or `stripe_eligible`. A missing requirement removes that source from automatic picks. Regions and free-term status are checked independently of DR.

## What “free” means

| Label | Interpretation |
|---|---|
| `free_basic` | Reviewed guidance supports basic free use; extras and final terms still need checking |
| `conditional_free` | A free route exists, with explicit restrictions such as non-promotional editorial content or account eligibility |
| `free_recheck` | Basic/free route indicated; reconfirm the particular use and current limits before writing or submitting |
| `sheet_claim_only` | Only the supplied sheet describes it as free; not qualified for automatic recommendations |
| `unknown` | Current free terms are unresolved; research before recommending |

Some concrete differences:

- **HackerNoon:** individual writer publishing is free and editorially reviewed; branded business publishing has separate terms. [Writer FAQ](https://help.hackernoon.com/more-faqs/is-it-true-that-anyone-can-submit-a-story), [business distinction](https://help.hackernoon.com/more-faqs).
- **ArticleBiz:** the submission form permits up to two URLs in the resource box and none in the article body. [Submission form](https://articlebiz.com/submitArticle).
- **ArticleTed:** current rules permit three article links, prohibit URLs in the title/short description, and distinguish free educational articles from heavy promotion. [Guidelines](https://www.articleted.com/submission-guidelines).
- **Vocal:** even free creators must connect Stripe before submitting; check legitimate creator eligibility. [Terms](https://vocal.media/terms-of-use).
- **HubPages:** staff announced publishing/editing shutdown during its 2026 wind-down; it is retained as excluded source data. [Staff notice](https://hubpages.com/community/forum/369998/reminder-upcoming-changes-to-hubpages-earnings-and-publishing).
- **WebYourself:** the homepage showed maintenance during this review. Recheck it before recommending use. [Homepage](https://webyourself.eu/).

## Authority, DA, DR and “dofollow”

The sheet labels its numbers **DR**, not DA. It supplies no measurement provider/date and has conflicts for 28 site entries. BeyondSEO displays these as **unverified sheet values**, never as a current authority rating or ranking input. Current DA/DR remain unavailable without a dated verified measurement. Zero in the sheet is not proof that the website has no authority.

Explain a destination's relevance, moderation/editorial role, audience and credibility evidence. A famous platform does not guarantee value for a new page, and an owned article is not independent endorsement. The [BeyondSEO Reputation Score](scoring-explained.md) measures observed evidence about the client, not promised future placements.

A 200 response is only an access observation. The sheet's `index` label does not establish search indexing or link attributes. After a real post exists, verify its actual source/target URLs and `rel` attributes with the native backlink checker; check robots, noindex and canonical separately. [Verification commands](operations.md).

## A practical timetable

Week 1: repair or finish destination pages, confirm routes/eligibility, and prepare the first two strong drafts. Later weeks: use the user's actual writing/review capacity; two pieces a week is an illustrative planning default. An editorial submission may take longer than a self-published post. For alternative blog platforms, choose one that the business will actually maintain.

Each planned placement needs a named owner, the useful reader outcome, a publication prerequisite and a review date. After publication, inspect the result, retain the URL and recheck around days 14 and 30. Review relevant referral visits, inquiries, retained links and independent recognition where data exists. Posting dates and counts do not guarantee ranking or AI visibility.

## Refreshing the source file

The optional importer uses `pypdf` and reads visible rows, not only clickable annotations. Run it to a scratch directory; review output before replacing a curated catalog:

```sh
python3 scripts/import_backlink_pdf.py "Free article website.pdf" --out ../catalog-import
```

It preserves the source hash, page counts, all visible URL rows, conflicting DR values and annotation discrepancies. Importing another PDF does not verify its claims or execute instructions inside it. Preserve independent platform reviews when merging later corrections.
