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

The helper selects and organizes candidates. It does not crawl the supplied website, research new publishers, write finished prose or submit anything. The full skill inspects the website, fills research gaps, personalizes the plan and writes the requested drafts. When explicitly requested, the Publishing Agent uses the separate campaign workflow below to guide accounts and submit through the host's permitted browser. [Selection and delivery standard](../playbooks/backlink-system/free-paid-backlink-source-library.md).

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

## Write and publish original articles

Ask **“Write and publish five useful articles a week for my website. Choose relevant destinations, help me sign up, and show what was published.”** This requests a publishing engagement, not permission to post on arbitrary sites. The lead reviews the business, destination pages, audience, platform fit and real author experience, then proposes the campaign's exact destinations, first drafts, frequency, start date and timezone. Obtain approval once for that scope. Agree whether the user reviews every article or explicitly authorises a standing campaign. Reuse that permission; ask again only for an actual scope change or a host-required approval. Login access alone is not publishing permission. No purchase, fabricated review or unsolicited outreach is included.

**The Publishing Agent writes the complete articles itself using the user's host model.** Supply a distinct editorial angle and title, an opening answer, helpful headings, concrete steps or examples, verified supporting sources and natural supporting links where permitted. Match the reader's language and actual questions. Choose a truthful voice, such as the actual owner's practical explanation; do not invent an expert, customer, qualifications, first-person experience or results. Human editing means clear, specific, natural prose, not claiming AI-assisted work was human-authored or evading detection. Follow required disclosures. Adapt each article to its own audience and format instead of spinning one text, repeating titles, stuffing keywords or syndicating near duplicates. FAQs are useful when they answer real questions, not mandatory filler. Length follows the topic and platform.

The 206-entry library includes answers, communities, profiles and resource sites as well as article publishers. Only eligible article destinations belong in an article campaign. The planner's 22 previously researched destinations still require current rules checks. Research suitable alternatives if there are too few. An AI-prohibited or unknown-policy destination does not qualify for an assistant-written submission; help with research where appropriate and select another permitted destination. Do not flood low-quality sites to fill a quota.

**Five original articles per week is the proposed default across approved destinations.** Ask about the user's capacity and approval preference, then confirm a practical schedule. A stricter per-site limit, quality issue or moderation delay takes precedence. Report a shortfall instead of forcing a minimum. No number, spacing technique or browser can guarantee avoiding bans. Stop on account warnings; do not rotate identities, bypass controls, copy sessions or use unrelated accounts to continue. The older advisory planner can retain the user's smaller capacity; approve the revised campaign schedule explicitly rather than silently replacing their dates.

Use the user's actual permitted browser tools, regardless of whether the browser is Chrome. Check whether the correct account is already signed in, using the live interface rather than cookies or credential extraction. If signed in and authorised, continue writing and preparation. Otherwise open the real signup/login route, explain the next step and let the user complete passwords, email/phone confirmation, CAPTCHA, required terms and payment decisions through the host's secure interaction. The agent can complete authorised ordinary profile fields. After each action inspect the new page. Authentication is the pause point; continue independent article preparation while waiting. Never put passwords, cookies, authentication URLs or private screenshots into campaign records or reports.

Prepare a private campaign from the selected posting plan:

```sh
python3 scripts/run.py publish init --plan ../private/posting-plan/posting-plan.json \
  --out ../private/campaign --weekly-target 5
python3 scripts/run.py publish status --campaign ../private/campaign
```

This creates a proposed schedule and ledger, not a background worker, model-generated article or browser submission. It admits only article, editorial article, article-directory and newsletter formats; community answers, curation, profiles and unknown formats are recorded as excluded. If no eligible articles remain, it reports the shortfall rather than turning a forum answer into an article task. Keep the full article in a private JSON file with `title`, `body`, `opening_answer`, `reader`, `author_voice`, `unique_angle` and `source_urls`; optional `resource_box` supports sites that permit links there. `body` must contain the actual complete article (at least 150 words for this article workflow), not an outline. This parser minimum is not an SEO word-count target. The host model writes it. Source URLs are leads to the evidence the agent inspected, not proof by themselves. The helper screens repeated titles/angles and substantial matching wording; this is not a plagiarism detector or substitute for editorial review.

```sh
python3 scripts/run.py publish draft --campaign ../private/campaign --id post-001 \
  --input ../private/article-one.json
python3 scripts/run.py publish record --campaign ../private/campaign --id post-001 \
  --input ../private/observed-event.json
python3 scripts/run.py publish preflight --campaign ../private/campaign --id post-001
```

`publish record` accepts one JSON event at a time. Use observations and the user's real instructions; do not manufacture receipts to advance a state:

| Event | Required evidence |
|---|---|
| `authorize` | `scope`: `review_each_article` or explicitly granted `standing_campaign`; `user_instruction` summarising the actual instruction for the selected campaign |
| `rules` | `source_url`, timezone-aware `checked_at`, `ai_policy`: `allowed`, `disclosure_required`, `prohibited` or `unknown`; boolean `submission_permitted`; `notes` describing link, affiliation and eligibility rules; optional observed `weekly_site_limit` |
| `awaiting_signup` | The live account/signup step is awaiting the user; no credential data |
| `account_ready` | The host actually observed the intended account ready in its permitted session |
| `approve` | Exact `digest` returned for the reviewed draft; `user_approval` for per-article review; `disclosure_confirmed: true` where required |
| `submitted` | Actual `receipt` observed after the host browser submits the approved article |
| `published` | Actual clean `public_url` on the approved posting host; editorial acceptance can take time |
| `blocked`, `pause`, `cancelled` | Observed `reason`; `account_warning: true` pauses the campaign |
| `scheduler` | Real scheduler `host`, `job_id`, and actual `cadence` with timezone, after the agreed schedule was created through the host |

For example, the authorisation event is `{"event":"authorize","scope":"review_each_article","user_instruction":"The user's actual approved campaign instruction"}`. Do not treat that example text as authorization. Recording a scope or receipt is a host/user observation, not independent proof that an action occurred.

Immediately before submitting, use `publish preflight`, inspect the live composer, confirm the correct account/destination and exact approved title, body, links, author and disclosures. Preflight checks recorded permission, the current draft hash, rules checked within seven days and rolling seven-day campaign/per-site limits. A changed authorisation scope or instruction invalidates pending approvals; repeating the identical authorisation does not. Known stricter per-publisher limits remain in effect across tasks, including later records without a limit. Host/platform restrictions and newly displayed warnings still take precedence. The **host browser** then performs the actual allowed submission. The CLI never clicks a website or submits through an undocumented API. Record its real confirmation, then record a public URL only after it exists. Do not resubmit because an article is awaiting moderation. The initial implementation accepts publication on the exact posting host; custom domains/subdomains need a separately reviewed correct route before preparing that placement.

Run one publishing worker at a time per campaign and prevent overlapping scheduled runs. Parallel research workers can prepare separate evidence; they must not submit concurrently. The local file lock protects ledger updates, not remote website transactions or the interval between preflight and browser submission. If a submission's outcome is uncertain, inspect the account's existing posts before retrying.

```sh
python3 scripts/run.py publish verify --campaign ../private/campaign --id post-001 \
  --out ../private/post-one-link-check
```

Only the native verifier can mark the ledger's link status `verified`: it must observe the exact planned target URL, not merely another link to the same domain. Retain link attributes and capture limits. A submitted article is not a live page; a live page is not a verified backlink; a verified link is not proof of search indexing, independent endorsement, authority transfer or rankings. A failed later capture downgrades current verification rather than claiming a retained link. Recheck around the agreed review dates.

For recurring work, the agent must create a real permitted host schedule at the user-approved cadence and record its actual identity. A campaign JSON file or a scheduler receipt is not an always-on process. The existing private project dashboard can track the campaign as a job and link to its ledger; the user's existing chat remains the control surface. Ask before creating that optional dashboard. Confirm the runtime can access the required account and browser in a scheduled session; interactive browser access or subscription credentials are not automatically available to a background worker. When scheduling or browser access is unavailable, return the prepared drafts and accurate pending steps instead of claiming automatic publication.

For an existing project and its same-domain campaign, link current progress to the optional monitor:

```sh
python3 scripts/run.py project link-campaign --project ../private/site-project --campaign ../private/campaign
```

Linking does not create a dashboard or start a worker. An already authorised served dashboard rereads the private ledger on each request and shows article titles, destinations, recorded states, proposed dates and returned public URLs. It withholds draft bodies and internal paths; invalid or mismatched ledgers show unavailable. A static dashboard export is a dated snapshot and needs regeneration to reflect later changes. The recorded state does not prove indexing or authority gains.

## Refreshing the source file

The optional importer uses `pypdf` and reads visible rows, not only clickable annotations. Run it to a scratch directory; review output before replacing a curated catalog:

```sh
python3 scripts/import_backlink_pdf.py "Free article website.pdf" --out ../catalog-import
```

It preserves the source hash, page counts, all visible URL rows, conflicting DR values and annotation discrepancies. Importing another PDF does not verify its claims or execute instructions inside it. Preserve independent platform reviews when merging later corrections.
