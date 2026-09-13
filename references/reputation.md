# BeyondSEO Reputation Score

Our 0–100 headline measures **how much reputation evidence the observed sample supports**. Model 1.1 uses conservative supported points and an explicit evidence adjustment. Show its provisional/assessed status, sensitivity range, confidence and coverage together. It is not a complete backlink index or a prediction of rankings.

Read [scoring explained](../docs/scoring-explained.md) for the plain-language introduction, worked example and boundaries when comparing this number with proprietary authority metrics. Sharing some public link-quality principles does not reproduce another provider's trained model. Version 2.4 retains model 1.1 and its low-confidence ceiling.

## Discover, verify, assess

Start with a five-page budget for `"Brand" -site:example.com`. Use available browser/search access and follow actual results. Record engine, query, date, pages inspected and candidate URLs. Search position and snippets supply discovery context only.

The native crawler requests each source, follows a bounded chain of observed redirect hosts, checks robots and renders scripted content where needed. A link must point to the target host or www alias. A brand mention must appear in captured text. Unreadable pages remain unverified. Review ambiguous names before attributing them to the company.

Review topical relevance, publisher relationship and placement context. Leave unreviewed dimensions unknown. A company-controlled profile is different from an independent editorial endorsement. Generate the estimate, strongest observed backlink list, mention list, evidence gaps and practical next actions.

No paid metric, crawling account or crawling service is required. Search discovery uses available access or supplied files; the CLI does not contain an unattended live Google collector. Pagination may stop early. Five requested pages do not become five completed pages. Stop at access challenges and report the missing coverage.

## Commands

```sh
beyondseo search-plan --target https://example.com --brand "Example" --pages 5 --out runs/discovery

# Import saved result HTML in actual page order.
beyondseo search-import --html page1.html page2.html --target https://example.com \
  --query '"Example" -site:example.com' --captured-at 2026-09-14T09:00:00Z --out runs/import

# Verify a source CSV and calculate the estimate.
beyondseo reputation --sources runs/import/sources.csv --target https://example.com \
  --brand "Example" --alias "Example Company" --related-host related-company.com \
  --max-sources 50 --search-pages 5 --out runs/reputation

# Reassess dated evidence without another network request.
beyondseo reputation --evidence runs/reputation/verification/backlinks.json \
  --target https://example.com --brand "Example" --out runs/reassessment
```

The importer reads result-heading links and ordinary Google redirect wrappers, excludes the target site and deduplicates URLs. Query, capture time and engine are operator-supplied provenance, not independently authenticated history. For browser DOM extracts or other source lists, supply a CSV directly and retain the discovery evidence alongside it.

CSV requires `URL`. Discovery fields: `engine`, `query`, `search_page`, `result_order`, `observed_at`, `source_snapshot`. Search-plan creates a blank template. `--alias` accepts real brand variants; it does not perform fuzzy entity matching.

| Optional review field | Accepted values |
|---|---|
| `relevance` | `high`, `medium`, `low`, or blank |
| `relationship` | `independent`, `third_party_profile`, `affiliated`, `owned`, or blank |
| `context` | `editorial`, `directory`, `user_generated`, `owned`, or blank |
| `reviewed_by`, `reviewed_at`, `review_evidence` | All three required for judgments to affect the score; identify the source and explain the assessment |
| `paid` | `true` or `yes` for a known paid placement |

These are attributable judgments, not facts inferred from a domain name or position. To review after crawling, retain the original `backlinks.json`, annotate each relevant result's `discovery` fields in a reviewed copy, and reassess with `--evidence`. Preserve original capture dates. Reused evidence must match the target and brand.

## Source quality rubric

| Dimension | Points |
|---|---|
| Captured evidence | Direct backlink: 40; mention without backlink: 25; neither: ineligible |
| Topic relevance | High: 25; medium: 15; low: 5; unknown: 0–25 |
| Relationship | Independent: 20; third-party profile: 10; affiliated: 5; owned or sponsored: 0; unknown: 0–20 |
| Context | Editorial: 15; directory: 10; user-generated: 5; owned: 0; unknown: 0–15 |

Known points form the supported lower bound; unknown dimensions earn no supported points. Their possible maxima form the upper bound. An observed link without review therefore has **40 supported source-quality points, possible range 40–100, assessed weight 40%**. A diagnostic midpoint of 70 remains in the data for explaining the old estimate; it is not the headline or a strong-quality verdict.

The target and its subdomains are excluded from external counts and scoring. Supplied related hosts are treated as owned and never establish independent editorial proof. Link attributes are retained. `nofollow` alone does not deduct points; known sponsorship receives no independence points. Attributes do not establish how an engine values a link.

## Supported score and confidence

Group by final hostname, ignoring www, and pool common publishing platform families. Use the highest diagnostic source quality per group to retain the existing source-selection method. Repeated identical source rows are ignored. This grouping is conservative, not a complete publisher-ownership database.

Calculate supported sample points using known lower-bound source quality:

```text
0.60 × mean supported quality of the strongest five observed publisher groups
+ 25 × min(observed publisher groups / 5, 1)
+ 15 × min(reviewed independent editorial groups / 3, 1)
```

With fewer than five groups, the quality mean uses those present. Unknown independence earns no supported editorial points. Preserve the diagnostic sample midpoint/range separately; they are not the headline score.

Then calculate evidence factors:

| Factor | Calculation |
|---|---|
| Verification coverage | Conclusive link checks / all known source candidates, including those not yet checked |
| Source review | Mean assessed rubric weight across selected sources / 100 |
| Publisher breadth | min(evidence publisher groups / 5, 1) |
| Recorded discovery | min(recorded search pages / requested budget, 1), or unknown when none were recorded |

A source limit does not erase remaining candidates. Keep supplied/remaining counts in verification coverage, so checking only a favorable subset cannot imply complete evidence. Search provenance remains operator-supplied; omitted or undiscovered candidates cannot be independently reconstructed.

Use the **weakest measured factor**, then apply the confidence ceiling:

```text
headline = supported sample points × weakest measured evidence factor
low-confidence headline ceiling = 49 / 100
```

Confidence is “moderate within this sample” only when there are at least five evidence groups, 80% conclusive link checks, 80% assessed source weight and the full requested search-page budget is recorded. Otherwise confidence is low, and neither the headline nor its adjusted range can reach 50. Unknown discovery coverage is not invented as complete; it keeps confidence low even if other factors are strong.

If no link checks were conclusive, withhold the headline while retaining any positive mentions from partial captures. If checked sources establish no external evidence, report zero supported evidence within the sample, not a whole-web reputation verdict.

For example, supported sample points of 72.4 with 12 conclusive checks out of 46, 92% source review and full breadth/discovery give a factor of 0.26087 and a **provisional headline of 18.9/100, low confidence**. The diagnostic midpoint of 74.8 must not replace it. A model revision can change the headline even when the website and all captured links are unchanged.

The adjusted range varies unknown rubric dimensions at the same evidence factor and ceiling. It is a sensitivity range, **not a statistical confidence interval**, and cannot describe unseen web evidence. The weights and 49-point ceiling are transparent conservative design choices, not calibrated ranking thresholds. A low-confidence result never receives a strong-authority badge, positive overall grade or an implied ranking prediction.

## Consistent treatment of every website

Apply identical scoring, review criteria, page budgets, confidence rules and unknown-data treatment to client, owner and competitor sites. Do not raise scores because the user owns the brand, because a site is familiar, or to make a report reassuring. Do not declare a numerical winner when coverage or confidence is materially uneven.

This makes the method consistent and evidence-led; it does not make a ranked search sample or human judgments statistically unbiased. Limited access reduces what we can support, not the intrinsic quality of an unread source. Improving the headline should mean better verified proof or better evidence coverage, not manipulating the sample or adding duplicate rows. Score changes across model versions must be labeled as methodology changes.

Never extrapolate whole-web backlink totals from five ranked pages. An unverified URL remains a candidate to check, never a backlink “probably done.”

## Reports and next actions

Outputs: `reputation.md`, `reputation.json`, `reputation-sources.csv` and underlying crawl evidence. Separate strongest observed backlinks, mentions without links, owned/affiliated sources and unreadable candidates. Link and mention counts may overlap. Positive mentions can survive a partial capture even when the link check is incomplete; the report distinguishes these counts. Show actual imported search-page and source coverage.

Use friendly language: “We found three pages linking to you in the sources we could read. This is a starting point, not your total. Two are useful profiles; we still need independent work examples and editorial coverage.” Give exact URLs, target pages, proposed contributions and verification steps. Compare competitors with similar queries, budgets, geography and dates; disclose capture imbalance.

The score does not measure sentiment, satisfaction, traffic, conversions, indexing or AI citations. Improving it is not a substitute for useful content, credible business proof and measured customer outcomes.

References: [Google link attributes](https://developers.google.com/search/docs/crawling-indexing/qualify-outbound-links), [crawlable links](https://developers.google.com/search/docs/crawling-indexing/links-crawlable), [spam policies](https://developers.google.com/search/docs/essentials/spam-policies).
