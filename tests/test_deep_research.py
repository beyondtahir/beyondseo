import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from beyondseo.deep_research import compare_reputation, research_plan
from beyondseo.reputation import assess

DATE = "2026-09-16T00:00:00+00:00"
NOW = datetime.fromisoformat(DATE)


def profile():
    return {
        "target": "https://client.test",
        "status": "reviewed",
        "fields": {
            "core_services": [{"value": "Workflow automation", "key": "automation"}],
            "customer_types": [{"value": "Businesses", "key": "business"}],
            "business_model": [{"value": "Agency", "key": "agency"}],
            "markets": [{"value": "Pakistan", "key": "pakistan"}],
            "search_languages": [{"value": "English", "key": "en"}],
        },
    }


def cohort_entry(item, relationship="independent"):
    rows, attempts, candidates = [], [], []
    for index, spec in enumerate(item["queries"]):
        url = f"https://publisher{index}.test/{item['role']}"
        observation = {
            "provider": "fixture-search",
            "query": spec["query"],
            "captured_at": DATE,
            "status": "results",
            "search_page": 1,
            "requested_market": spec["market"],
            "requested_language": spec["language"],
        }
        attempts.append({**observation, "results": [{"url": url}]})
        candidates.append({"url": url, "provenance": [observation]})
        rows.append(
            {
                "source_url": url,
                "final_url": url,
                "checked_at": DATE,
                "verification": "link_observed",
                "target_links": [{"url": item["target"], "rel": []}],
                "brand_mentions": [],
                "representation": "http",
                "discovery": {
                    "relevance": "high",
                    "relationship": relationship,
                    "context": "editorial",
                    "reviewed_by": "Fixture reviewer",
                    "reviewed_at": DATE,
                    "review_evidence": "Reviewed the captured source context.",
                    "provenance": [observation],
                },
            }
        )
    return {
        "verification": {
            "target": item["target"],
            "brand": item["brand"],
            "checked_at": DATE,
            "results": rows,
            "sources_supplied": 5,
        },
        "discovery": {"target": item["target"], "attempts": attempts, "candidates": candidates},
    }


class DeepResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plan = research_plan(
            profile(),
            self.root / "plan",
            "Example",
            {
                "client": "https://client.test",
                "direct_competitors": [{"website": "https://agency.test"}],
                "aspirational_benchmarks": [{"website": "https://benchmark.test"}],
            },
        )
        self.entries = [
            cohort_entry(self.plan["cohort"][0]),
            cohort_entry(self.plan["cohort"][1], "third_party_profile"),
        ]

    def compare(self):
        return compare_reputation(self.plan, self.entries, self.root / "out", now=NOW)

    def test_plan_has_browser_first_routes_equal_queries_and_no_benchmark_in_cohort(self):
        self.assertEqual(self.plan["route_order"][0], "host_browser_google")
        self.assertEqual(len(self.plan["cohort"]), 2)
        self.assertEqual(self.plan["status"], "planned_not_executed")
        self.assertEqual(
            [q["family"] for q in self.plan["cohort"][0]["queries"]],
            [q["family"] for q in self.plan["cohort"][1]["queries"]],
        )
        self.assertIn("Pakistan", self.plan["competitor_queries"][0]["query"])
        self.assertEqual(self.plan["language"], "English")

    def test_unreviewed_business_cannot_start_and_unknown_market_stays_unknown(self):
        p = profile()
        p["status"] = "needs_review"
        with self.assertRaisesRegex(ValueError, "Review"):
            research_plan(p, self.root / "bad")
        p["status"] = "reviewed"
        p["fields"]["markets"] = []
        self.assertIsNone(research_plan(p, self.root / "unknown")["market"])

    def test_matched_reviewed_samples_can_rank_within_cohort(self):
        result = self.compare()
        self.assertEqual(result["status"], "ranked_within_sample")
        self.assertEqual([s["rank"] for s in result["sites"]], [1, 2])
        self.assertNotIn(
            "backlinks",
            (self.root / "out/reputation-comparison.md").read_text().split("##")[0].lower(),
        )
        self.assertNotIn("publisher0", (self.root / "out/reputation-comparison.md").read_text())

    def test_low_coverage_and_unchecked_candidates_withhold_ranking(self):
        self.entries[0]["discovery"]["candidates"] += [
            {"url": f"https://unread{i}.test"} for i in range(20)
        ]
        result = self.compare()
        self.assertEqual(result["status"], "comparison_only")
        self.assertTrue(all(s["rank"] is None for s in result["sites"]))
        self.assertEqual(result["sites"][0]["coverage"]["known_source_candidates"], 25)
        self.assertLess(result["sites"][0]["score"], 50)

    def test_unequal_providers_withhold_even_if_scores_are_high(self):
        self.entries[1]["discovery"]["attempts"][0]["provider"] = "another-provider"
        result = self.compare()
        self.assertEqual(result["status"], "comparison_only")
        self.assertTrue(any("providers" in r for r in result["ranking_withheld_reasons"]))

    def test_truncated_candidate_pool_withholds_ranking(self):
        self.entries[0]["discovery"]["candidate_budget_reached"] = True
        self.assertEqual(self.compare()["status"], "comparison_only")

    def test_benchmarks_cannot_be_ranked_as_direct_competitors(self):
        self.plan["cohort"][1]["role"] = "aspirational_benchmark"
        with self.assertRaisesRegex(ValueError, "benchmarks separate"):
            self.compare()

    def test_missing_queries_or_unequal_pagination_withhold(self):
        for mode in ("missing", "extra"):
            with self.subTest(mode=mode):
                self.entries = [cohort_entry(i) for i in self.plan["cohort"]]
                attempts = self.entries[1]["discovery"]["attempts"]
                if mode == "missing":
                    attempts.pop()
                else:
                    attempts.append({**attempts[0], "search_page": 2})
                self.assertEqual(self.compare()["status"], "comparison_only")

    def test_stale_or_unknown_capture_dates_do_not_rank(self):
        for value in ("2020-01-01T00:00:00+00:00", "", "2026-09-16"):
            self.entries[0]["verification"]["results"][0]["checked_at"] = value
            self.assertEqual(self.compare()["status"], "comparison_only")

    def test_wrong_target_or_duplicate_site_is_rejected(self):
        self.entries[0]["discovery"]["target"] = "https://unrelated.test"
        with self.assertRaisesRegex(ValueError, "targets differ"):
            self.compare()
        self.entries[0]["discovery"]["target"] = self.plan["client"]
        self.entries.append(self.entries[0])
        with self.assertRaisesRegex(ValueError, "duplicated"):
            self.compare()

    def test_all_provenance_counts_without_inventing_unknown_search_pages(self):
        verification = self.entries[0]["verification"]
        first = verification["results"][0]["discovery"]
        first["provenance"] += copy.deepcopy(first["provenance"])
        result = assess(verification)
        self.assertEqual(len(result["coverage"]["recorded_search_pages"]), 5)
        self.assertEqual(result["confidence"], "moderate within this sample")
        for source in verification["results"]:
            for observation in source["discovery"]["provenance"]:
                observation.pop("search_page", None)
        result = assess(verification)
        self.assertEqual(result["coverage"]["recorded_search_pages"], [])
        self.assertEqual(result["confidence"], "low")

    def test_no_complete_backlink_or_visibility_metrics_generated(self):
        result = json.dumps(self.compare())
        for field in ('"total_backlinks"', '"domain_authority"', '"google_rank"', '"ai_citations"'):
            self.assertNotIn(field, result)
