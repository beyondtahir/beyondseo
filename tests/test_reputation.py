import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from beyondseo.reputation import assess, import_search_html, reputation, search_plan, source_score

TARGET = "https://example.com/"


def source(url="https://publisher.test/article", link=True, mention=True, review=None):
    return {
        "source_url": url,
        "final_url": url,
        "verification": "link_observed" if link else "no_link_in_captured_content",
        "target_links": [{"url": TARGET, "rel": ["nofollow"]}] if link else [],
        "brand_mentions": [{"name": "Example", "excerpt": "Example provides services."}]
        if mention
        else [],
        "mention_status": "observed_in_page" if mention else "not_observed_in_capture",
        "representation": "rendered",
        "discovery": review or {},
    }


REVIEW = {
    "relevance": "high",
    "relationship": "independent",
    "context": "editorial",
    "reviewed_by": "Test reviewer",
    "reviewed_at": "2026-09-14",
    "review_evidence": "Read the article and verified its publisher and editorial context.",
}


def reviewed_sample():
    rows = [
        source(f"https://publisher{i}.test/article", review=copy.deepcopy(REVIEW)) for i in range(5)
    ]
    for i, row in enumerate(rows):
        row["discovery"].update(
            engine="Google", query='"Example"', search_page=i + 1, observed_at="2026-09-14"
        )
    return rows


def inaccessible(url):
    row = source(url, link=False, mention=False)
    row["verification"] = "unverified_access"
    return row


class ReputationTests(unittest.TestCase):
    def assess(self, rows, **kwargs):
        return assess({"target": TARGET, "brand": "Example", "results": rows}, **kwargs)

    def test_unknown_dimensions_widen_range(self):
        result = source_score(source(), TARGET)
        self.assertEqual(result["quality_range"], [40, 100])
        self.assertEqual(result["quality_estimate"], 70)
        self.assertEqual(result["assessed_weight_percent"], 40)
        self.assertEqual(self.assess([source()])["confidence"], "low")

    def test_unattributed_judgment_is_unknown(self):
        row = source(review={"relevance": "high", "relationship": "independent"})
        self.assertEqual(source_score(row, TARGET)["relationship"], "unknown")

    def test_nofollow_is_preserved_without_automatic_quality_penalty(self):
        result = source_score(source(review=REVIEW), TARGET)
        self.assertEqual(result["quality_range"], [100, 100])
        self.assertEqual(result["target_links"][0]["rel"], ["nofollow"])

    def test_sponsored_is_not_independent(self):
        row = source(review=REVIEW)
        row["target_links"][0]["rel"].append("sponsored")
        result = source_score(row, TARGET)
        self.assertFalse(result["independent_editorial_evidence"])
        self.assertEqual(result["relationship"], "sponsored")

    def test_owned_sites_cannot_supply_independent_proof(self):
        row = source("https://related.test/article", review=REVIEW)
        result = self.assess([row], related_hosts=["related.test"])
        self.assertEqual(result["independent_editorial_publisher_groups"], 0)
        self.assertEqual(result["sources"][0]["relationship"], "owned")

    def test_same_site_subdomain_is_excluded_from_external_counts(self):
        result = self.assess([source("https://news.example.com/article", review=REVIEW)])
        self.assertEqual(result["observed_link_pages"], 0)
        self.assertEqual(result["observed_mention_pages"], 0)
        self.assertEqual(result["top_mentions_without_links"], [])
        self.assertEqual(result["score"], 0)

    def test_repeated_publisher_pages_do_not_inflate_score(self):
        one = self.assess([source(review=REVIEW)])
        many = self.assess(
            [source(f"https://publisher.test/{i}", review=REVIEW) for i in range(25)]
        )
        self.assertEqual(one["score"], many["score"])
        self.assertEqual(many["coverage"]["unique_publisher_groups_with_evidence"], 1)

    def test_redirect_aliases_and_platform_subdomains_are_pooled(self):
        one = source("https://old.test/article", review=REVIEW)
        one["final_url"] = "https://one.substack.com/article"
        two = source("https://two.substack.com/article", review=REVIEW)
        self.assertEqual(
            self.assess([one, two])["coverage"]["unique_publisher_groups_with_evidence"], 1
        )

    def test_mentions_are_not_backlinks(self):
        result = self.assess([source(link=False)])
        self.assertEqual(result["observed_link_pages"], 0)
        self.assertEqual(result["observed_mention_pages"], 1)
        self.assertEqual(len(result["top_mentions_without_links"]), 1)

    def test_unreadable_sample_has_no_score_or_invented_total(self):
        row = source(link=False, mention=False)
        row["verification"] = "unverified_access"
        result = self.assess([row])
        self.assertIsNone(result["score"])
        self.assertIsNone(result["estimated_total_backlinks"])

    def test_readable_unrelated_source_scores_zero_within_sample(self):
        row = source(link=False, mention=False)
        row["discovery"] = {"snippet": "Example has many links", "result_order": "1"}
        self.assertEqual(self.assess([row])["score"], 0)

    def test_requested_pages_are_not_reported_as_completed(self):
        with tempfile.TemporaryDirectory() as folder:
            result = search_plan(TARGET, "Example", folder)
        self.assertEqual(result["completed_pages"], 0)
        self.assertEqual(len(result["pages"]), 5)
        self.assertEqual(self.assess([source()])["coverage"]["recorded_search_pages"], [])

    def test_html_import_unwraps_deduplicates_and_excludes_own_site(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            snapshot = root / "page.html"
            snapshot.write_text(
                '<a href="/url?q=https%3A%2F%2Fpublisher.test%2Farticle"><h3>Result</h3></a><a href="https://publisher.test/article"><h3>Duplicate</h3></a><a href="https://news.example.com"><h3>Own</h3></a><p>Example backlink snippet</p>'
            )
            result = import_search_html(
                [snapshot], TARGET, '"Example"', "2026-09-14T00:00:00Z", root / "import"
            )
            rows = list(csv.DictReader((root / "import/sources.csv").open(encoding="utf-8-sig")))
        self.assertEqual(result["candidate_urls"], 1)
        self.assertEqual(rows[0]["URL"], "https://publisher.test/article")
        self.assertEqual(rows[0]["search_page"], "1")

    def test_saved_evidence_reuse_preserves_date_and_never_recrawls(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            payload = {
                "target": TARGET,
                "brand": "Example",
                "checked_at": "2026-09-01T00:00:00Z",
                "results": [source()],
            }
            evidence = root / "evidence.json"
            evidence.write_text(json.dumps(payload))
            with patch(
                "beyondseo.reputation.check_sources", side_effect=AssertionError("Unexpected fetch")
            ):
                result = reputation(None, TARGET, "Example", root / "report", evidence=evidence)
                self.assertTrue(result["reused_evidence"])
                self.assertEqual(result["checked_at"], payload["checked_at"])
                with self.assertRaises(ValueError):
                    reputation(
                        None, "https://other.test", "Example", root / "other", evidence=evidence
                    )
                with self.assertRaises(ValueError):
                    reputation(None, TARGET, "Other", root / "other", evidence=evidence)

    def test_complete_review_has_bounded_repeatable_score(self):
        rows = [
            source(f"https://publisher{i}.test/article", review=copy.deepcopy(REVIEW))
            for i in range(5)
        ]
        for i, row in enumerate(rows):
            row["discovery"].update(
                engine="Google", query='"Example"', search_page=i + 1, observed_at="2026-09-14"
            )
        result = self.assess(rows)
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["score_range"], [100, 100])
        self.assertEqual(result["confidence"], "moderate within this sample")

    def test_known_user_generated_context_cannot_gain_editorial_bonus(self):
        review = {**REVIEW, "relationship": "unknown", "context": "user_generated"}
        result = self.assess([source(review=review)])
        self.assertEqual(result["components"]["independent_proof_points_range"], [0, 0])

    def test_independent_source_with_unknown_context_has_open_editorial_range(self):
        review = {**REVIEW, "context": "unknown"}
        result = self.assess([source(review=review)])
        self.assertEqual(result["components"]["independent_proof_points_range"], [0, 5])

    def test_partial_capture_preserves_positive_mention_without_claiming_complete_check(self):
        row = source(link=False)
        row["verification"] = "unverified_access"
        result = self.assess([row])
        self.assertEqual(result["coverage"]["conclusive_link_checks"], 0)
        self.assertEqual(result["coverage"]["sources_with_positive_evidence"], 1)
        self.assertEqual(result["observed_mention_pages"], 1)
        self.assertIsNone(result["score"])

    def test_missing_discovery_provenance_prevents_high_headline(self):
        rows = reviewed_sample()
        for row in rows:
            row["discovery"].pop("search_page")
        result = self.assess(rows)
        self.assertEqual(result["sample_quality_estimate"], 100)
        self.assertEqual(result["score"], 49)
        self.assertEqual(result["score_status"], "provisional")
        self.assertIsNone(result["evidence_adjustment"]["factors"]["search_page_coverage"])

    def test_partial_search_budget_lowers_headline_and_confidence(self):
        rows = reviewed_sample()
        for row in rows:
            row["discovery"]["search_page"] = 1
        result = self.assess(rows)
        self.assertEqual(result["score"], 20)
        self.assertEqual(result["confidence"], "low")

    def test_inaccessible_sources_reduce_assurance_not_source_quality(self):
        rows = reviewed_sample()
        full = self.assess(rows)
        limited = self.assess(rows + [inaccessible(f"https://blocked{i}.test/") for i in range(15)])
        self.assertEqual(limited["sample_quality_estimate"], full["sample_quality_estimate"])
        self.assertEqual(limited["score"], 25)
        self.assertLess(limited["score"], full["score"])

    def test_unknown_dimensions_do_not_earn_optimistic_headline_points(self):
        rows = reviewed_sample()
        for row in rows:
            for field in ("relevance", "relationship", "context"):
                row["discovery"].pop(field)
        result = self.assess(rows)
        self.assertEqual(result["score"], 19.6)
        self.assertEqual(result["sources"][0]["supported_quality_points"], 40)
        self.assertGreater(result["sample_quality_estimate"], result["score"])

    def test_duplicate_evidence_rows_cannot_improve_verification_fraction(self):
        rows = reviewed_sample() + [inaccessible(f"https://blocked{i}.test/") for i in range(15)]
        once = self.assess(rows)
        repeated = self.assess(rows + [copy.deepcopy(rows[0]) for _ in range(100)])
        self.assertEqual(repeated["score"], once["score"])
        self.assertEqual(repeated["coverage"]["sources_checked"], 20)
        self.assertEqual(repeated["coverage"]["duplicate_source_rows_ignored"], 100)

    def test_same_evidence_gets_same_score_for_owner_and_competitor(self):
        rows = reviewed_sample() + [inaccessible("https://blocked.test/")]
        results = []
        for target, brand in [
            ("https://puredesigners.com", "PureDesigners"),
            ("https://competitor.test", "Competitor"),
        ]:
            same = copy.deepcopy(rows)
            for row in same:
                for link in row["target_links"]:
                    link["url"] = target
            results.append(assess({"target": target, "brand": brand, "results": same}))
        first, second = results
        self.assertEqual(first["score"], second["score"])
        self.assertEqual(first["evidence_adjustment"], second["evidence_adjustment"])

    def test_low_confidence_never_has_high_headline_or_range(self):
        for failures in (1, 2, 5, 20):
            result = self.assess(
                reviewed_sample()
                + [inaccessible(f"https://blocked{i}.test") for i in range(failures)]
            )
            if result["confidence"] == "low":
                self.assertLess(result["score"], 50)
                self.assertLess(result["score_range"][1], 50)

    def test_unknown_verification_state_cannot_establish_conclusive_coverage(self):
        row = source(link=False, mention=False)
        row["verification"] = "pending"
        self.assertIsNone(self.assess([row])["score"])

    def test_invalid_page_budget_is_rejected(self):
        for budget in (0, 21):
            with self.assertRaises(ValueError):
                self.assess(reviewed_sample(), requested_search_pages=budget)

    def test_link_to_another_company_cannot_count_as_target_backlink(self):
        row = source(mention=False)
        row["target_links"][0]["url"] = "https://unrelated.test/"
        result = self.assess([row])
        self.assertEqual(result["observed_link_pages"], 0)
        self.assertEqual(result["top_backlinks"], [])

    def test_source_limit_cannot_hide_unchecked_candidates_from_confidence(self):
        result = assess(
            {
                "target": TARGET,
                "brand": "Example",
                "results": reviewed_sample(),
                "sources_supplied": 50,
                "sources_remaining": 45,
            }
        )
        self.assertEqual(result["score"], 10)
        self.assertEqual(result["confidence"], "low")
        self.assertEqual(result["coverage"]["sources_checked"], 5)
        self.assertEqual(result["coverage"]["known_source_candidates"], 50)
        self.assertEqual(result["coverage"]["sources_unchecked"], 45)
