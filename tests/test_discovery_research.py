"""Offline regression fixtures: no search provider or client domain is contacted."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from beyondseo.backlinks import source_rows
from beyondseo.diagnostics import failure_detail
from beyondseo.discovery import RequestBudget, consolidate, discover, host_attempts, parse_search
from beyondseo.evidence import capture_quality
from beyondseo.extract import extract, page_findings
from beyondseo.findings import audit_report
from beyondseo.research import FIELDS, profile, research_queries, select_competitors
from beyondseo.review import readiness

DATE = "2026-01-01T00:00:00+00:00"
DDG = '<div class="result"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fagency.test%2F">Agency</a><a class="result__snippet">A mention is only a lead.</a></div>'


def attempt(provider="fallback", results=True):
    return {
        "provider": provider,
        "captured_at": DATE,
        "status": "results" if results else "empty_results",
        "results": [{"url": "https://agency.test/", "snippet": "Client has 10000 backlinks"}]
        if results
        else [],
    }


def page(url="https://client.test/", html=None):
    html = (
        html
        or '<html lang="en"><title>AI agency</title><main><h1>AI automation</h1>We implement workflow automation for businesses in Pakistan. Request a consultation.</main></html>'
    )
    return {
        "url": url,
        "final_url": url,
        "fetched_at": DATE,
        "status": 200,
        "error": "",
        "headers": {},
        "data": extract(html, url),
    }


def snapshot(folder, record):
    folder.mkdir()
    (folder / "pages.jsonl").write_text(json.dumps(record) + "\n")
    (folder / "summary.json").write_text(
        json.dumps({"seed": record["url"], "coverage_limited": True})
    )
    (folder / "issues.json").write_text(json.dumps(page_findings(record)))


def review(url, market="pakistan", model="agency", service="workflow_automation"):
    quote = "We implement workflow automation for businesses in Pakistan."

    def claim(value, key):
        return {"value": value, "key": key, "evidence": [{"url": url, "quote": quote}]}

    fields = {k: [] for k in FIELDS}
    fields.update(
        business_model=[claim(model, model)],
        core_services=[claim("workflow automation", service)],
        customer_types=[claim("businesses", "business")],
        markets=[claim(market, market)],
        website_languages=[
            {
                "value": "English",
                "key": "en",
                "evidence": [{"url": url, "field": "language", "value": "en"}],
            }
        ],
        commercial_intent=[claim("implementation", "services")],
    )
    return {"target": url, "reviewed_by": "Fixture reviewer", "reviewed_at": DATE, "fields": fields}


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_blocked_primary_falls_back_and_retains_failure(self):
        primary = Mock(
            return_value={
                "provider": "primary",
                "captured_at": DATE,
                "status": "http_access_denied",
                "failure": {"code": "http_access_denied", "evidence": "HTTP 403"},
                "results": [],
            }
        )
        fallback = Mock(return_value=attempt())
        found = discover(
            [{"query": "automation", "market": "Pakistan", "language": "English"}],
            self.root,
            adapters={"primary": primary, "fallback": fallback},
        )
        self.assertEqual(found["candidate_count"], 1)
        self.assertEqual(found["attempts"][1]["fallback_from"]["status"], "http_access_denied")
        self.assertEqual(found["candidates"][0]["provenance"][0]["requested_market"], "Pakistan")
        self.assertEqual(found["candidates"][0]["verification"], "unverified_lead")
        self.assertNotIn("verified_backlinks", found)

    def test_all_unavailable_audit_still_reports_crawl_evidence(self):
        found = discover([{"query": "automation"}], self.root / "search", offline=True)
        snapshot(self.root / "site", page())
        result = audit_report(self.root / "site", self.root / "report", discovery=found)
        self.assertEqual(result["discovery_status"], "no_leads")
        self.assertTrue(result["findings"])
        self.assertFalse(found["search_available"])
        self.assertTrue(found["coverage_limited"])

    def test_execution_permission_is_not_provider_denial(self):
        self.assertEqual(
            failure_detail("PermissionError: Permission denied", context="execution")["code"],
            "execution_denied",
        )
        self.assertEqual(failure_detail(status=403)["code"], "http_access_denied")
        self.assertEqual(failure_detail(status=403)["cause"], "unknown")
        self.assertEqual(failure_detail("something failed")["code"], "unknown")

    def test_transport_failure_types(self):
        for text, code in [
            ("gaierror: no address", "dns_failure"),
            ("SSLError: TLS failed", "tls_failure"),
            ("ConnectionRefusedError: refused", "connection_failure"),
            ("network access is disabled", "environment_network_restricted"),
            ("ModuleNotFoundError: no module named bs4", "missing_dependency"),
            ("Executable doesn't exist", "browser_runtime_missing"),
        ]:
            self.assertEqual(failure_detail(text)["code"], code)

    def test_empty_is_different_from_parse_failure_and_challenge(self):
        self.assertEqual(
            parse_search('<div class="no-results">No results found</div>', "duckduckgo-html")[0],
            "empty_results",
        )
        self.assertEqual(
            parse_search("<html>Unexpected layout</html>", "duckduckgo-html")[0], "parse_failed"
        )
        self.assertEqual(
            parse_search('<form id="challenge-form"></form>', "duckduckgo-html")[0],
            "provider_challenge",
        )
        self.assertEqual(parse_search(DDG, "duckduckgo-html")[1][0]["url"], "https://agency.test/")
        self.assertEqual(parse_search("<rss><channel/></rss>", "bing-rss")[0], "empty_results")
        self.assertEqual(parse_search("<rss>", "bing-rss")[0], "parse_failed")

    def test_duplicate_provenance_survives_csv_and_verification_input(self):
        found = discover(
            [{"query": "one"}, {"query": "two"}],
            self.root,
            adapters={"fallback": lambda _: attempt()},
        )
        self.assertEqual(found["candidate_count"], 1)
        self.assertEqual(len(found["candidates"][0]["provenance"]), 2)
        rows = source_rows(self.root / "sources.csv")
        self.assertEqual(len(rows[0]["provenance"]), 2)
        self.assertEqual(len(consolidate(found["candidates"] * 2)[0]["provenance"]), 2)

    def test_empty_primary_tries_next_provider(self):
        found = discover(
            [{"query": "one"}],
            self.root,
            adapters={"empty": lambda _: attempt("empty", False), "fallback": lambda _: attempt()},
        )
        self.assertEqual(found["candidate_count"], 1)
        self.assertEqual(found["attempts"][0]["status"], "empty_results")

    def test_unreviewed_query_seed_skips_network_but_keeps_other_work(self):
        adapter = Mock(return_value=attempt())
        found = discover(
            [{"query": "technical seed", "query_review_status": "needs_review"}],
            self.root / "search",
            candidates=["https://supplied.test"],
            adapters={"native": adapter},
        )
        adapter.assert_not_called()
        self.assertEqual(found["queries_needing_review"], 1)
        self.assertEqual(found["attempts"][0]["status"], "query_review_required")
        self.assertIsNone(found["attempts"][0]["failure"])
        self.assertEqual(found["candidate_count"], 1)
        snapshot(self.root / "site", page())
        self.assertTrue(
            audit_report(self.root / "site", self.root / "audit", discovery=found)["findings"]
        )

    def test_saved_html_and_supplied_urls_work_offline(self):
        html = self.root / "saved.html"
        html.write_text(DDG)
        found = discover(
            [],
            self.root / "report",
            offline=True,
            candidates=["https://supplied.test"],
            saved=[
                {"path": html, "provider": "duckduckgo-html", "query": "q", "captured_at": DATE}
            ],
        )
        self.assertEqual(found["candidate_count"], 2)
        self.assertEqual(found["native_requests"], 0)

    def test_own_site_only_is_no_relevant_results(self):
        found = discover(
            [{"query": "q"}],
            self.root,
            target="https://agency.test",
            adapters={"x": lambda _: attempt()},
        )
        self.assertEqual(found["attempts"][0]["status"], "no_relevant_results")
        self.assertTrue(found["search_available"])

    def test_budget_is_hard_bounded(self):
        budget = RequestBudget(1)
        budget.take()
        with self.assertRaisesRegex(ValueError, "budget_exhausted"):
            budget.take()

    def test_cache_preserves_capture_date_and_skips_fetch(self):
        from beyondseo.network import utcnow

        live = {**attempt(), "captured_at": utcnow()}
        adapter = Mock(return_value=live)
        for i in range(2):
            found = discover(
                [{"query": "q"}],
                self.root / str(i),
                cache=self.root / "cache",
                adapters={"fallback": adapter},
            )
        self.assertEqual(adapter.call_count, 1)
        self.assertTrue(found["attempts"][0]["cache_hit"])
        self.assertEqual(found["attempts"][0]["captured_at"], live["captured_at"])

    def test_host_tool_failure_evidence_retained_before_fallback(self):
        path = self.root / "host.json"
        path.write_text(
            json.dumps(
                {
                    "attempts": [
                        {
                            "query": "q",
                            "provider": "host-search",
                            "captured_at": DATE,
                            "status": "failed",
                            "stage": "execution",
                            "evidence": "Permission denied",
                        }
                    ]
                }
            )
        )
        records = host_attempts(path)
        found = discover(
            [{"query": "q"}],
            self.root / "out",
            host_records=records,
            adapters={"fallback": lambda _: attempt()},
        )
        self.assertEqual(found["attempts"][0]["status"], "execution_denied")
        self.assertEqual(found["attempts"][1]["fallback_from"]["provider"], "host-search")

    def test_disabled_host_search_is_unavailable_with_unknown_cause_and_fallback(self):
        evidence = "web_search is disabled or no provider is available."
        path = self.root / "host.json"
        path.write_text(
            json.dumps(
                {
                    "attempts": [
                        {
                            "query": "q",
                            "provider": "host-search",
                            "captured_at": DATE,
                            "status": "failed",
                            "stage": "execution",
                            "evidence": evidence,
                        }
                    ]
                }
            )
        )
        found = discover(
            [{"query": "q"}],
            self.root / "out",
            host_records=host_attempts(path),
            adapters={"fallback": lambda _: attempt()},
        )
        failed = found["attempts"][0]
        self.assertEqual(failed["status"], "tool_unavailable")
        self.assertEqual(failed["failure"]["cause"], "unknown")
        self.assertEqual(failed["failure"]["evidence"], evidence)
        self.assertIsNone(failed["failure"]["http_status"])
        self.assertEqual(found["candidate_count"], 1)
        self.assertEqual(found["attempts"][1]["fallback_from"]["status"], "tool_unavailable")

    def test_snippet_is_not_link_evidence_in_source_checker(self):
        from beyondseo.backlinks import check_sources
        from beyondseo.reputation import assess

        discover(
            [{"query": "one"}], self.root / "search", adapters={"fallback": lambda _: attempt()}
        )
        verified = {
            "source_url": "https://agency.test/",
            "verification": "no_link_in_captured_content",
            "target_links": [],
            "brand_mentions": [],
            "coverage_limited": False,
            "evidence_folder": str(self.root / "links" / "sources" / "fixture"),
            "representation": "http",
            "error": "",
        }
        with patch("beyondseo.backlinks.verify_source", return_value=verified):
            result = check_sources(
                self.root / "search/sources.csv",
                "https://client.test",
                self.root / "links",
                brand="Client",
            )
        self.assertEqual(result["observed_link_pages"], 0)
        rating = assess(result)
        self.assertIsNone(rating["estimated_total_backlinks"])
        self.assertEqual(rating["observed_link_pages"], 0)

    def test_doctor_preserves_execution_error(self):
        from beyondseo.doctor import environment_report

        with (
            patch("importlib.metadata.version", return_value="1.0"),
            patch(
                "playwright.sync_api.sync_playwright",
                side_effect=PermissionError("Permission denied: chromium"),
            ),
        ):
            result = environment_report()
        self.assertEqual(result["checks"]["browser_runtime"]["status"], "execution_denied")
        self.assertIn(
            "Permission denied", result["checks"]["browser_runtime"]["failure"]["evidence"]
        )
        self.assertEqual(result["checks"]["search_discovery"]["status"], "not_tested")

    def test_unrecognized_saved_page_never_claims_zero_search_results(self):
        from beyondseo.reputation import import_search_html

        saved = self.root / "unknown.html"
        saved.write_text("<html>A consent screen with no result structure.</html>")
        result = import_search_html(
            [saved], "https://client.test", "brand", DATE, self.root / "import"
        )
        self.assertEqual(result["attempts"][0]["status"], "parse_failed")


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.client = self.make_profile("client")

    def tearDown(self):
        self.tmp.cleanup()

    def make_profile(self, name, **kwargs):
        url = "https://" + name + ".test/"
        snapshot(self.root / name, page(url))
        return profile(
            self.root / name, self.root / (name + "-profile"), review=review(url, **kwargs)
        )

    def buyer_queries(self):
        return [
            {
                "query": wording,
                "intent": intent,
                "market": "Pakistan",
                "language": "English",
                "basis": [{"field": "core_services", "key": "workflow_automation"}],
            }
            for wording, intent in [
                ("automation agency in Pakistan", "category"),
                ("Which agency in Pakistan can automate my business?", "question"),
            ]
        ]

    def test_reviewed_buyer_phrases_and_questions_preserve_wording_without_demand_claims(self):
        reviewed = review("https://client.test/")
        reviewed["search_queries"] = self.buyer_queries()
        result = profile(self.root / "client", self.root / "wording", review=reviewed)
        self.assertEqual(
            [q["query"] for q in result["queries"]],
            [q["query"] for q in reviewed["search_queries"]],
        )
        self.assertEqual({q["query_review_status"] for q in result["queries"]}, {"reviewed"})
        self.assertEqual({q["demand"] for q in result["queries"]}, {"unmeasured"})
        self.assertTrue(
            all(q["purpose"] == "competitor_discovery_hypothesis" for q in result["queries"])
        )
        adapter = Mock(return_value=attempt())
        found = discover(result["queries"], self.root / "search", adapters={"native": adapter})
        self.assertEqual(adapter.call_count, 2)
        self.assertEqual(found["queries_needing_review"], 0)

    def test_legacy_profile_yields_seeds_for_agent_review_without_stacked_jargon(self):
        queries = self.client["queries"]
        self.assertEqual(queries[0]["query"], "workflow automation in pakistan")
        self.assertEqual(queries[0]["query_review_status"], "needs_review")
        self.assertNotIn("implementation agency for", queries[0]["query"])
        self.client["fields"]["markets"] = []
        self.assertIsNone(research_queries(self.client)[0]["market"])

    def test_query_basis_and_market_must_belong_to_profile_or_explicit_brief(self):
        self.client["search_queries"] = self.buyer_queries()
        self.client["search_queries"][0]["basis"][0]["key"] = "unobserved_service"
        with self.assertRaisesRegex(ValueError, "basis is absent"):
            research_queries(self.client)
        self.client["search_queries"] = self.buyer_queries()
        self.client["search_queries"][0]["market"] = "Canada"
        with self.assertRaisesRegex(ValueError, "market is not supported"):
            research_queries(self.client)

    def test_native_language_question_is_not_rewritten_in_english_and_duplicates_collapse(self):
        self.client["brief"] = {"fields": {"search_languages": [{"value": "Urdu", "key": "ur"}]}}
        query = self.buyer_queries()[0]
        query.update(
            query="پاکستان میں آٹومیشن ایجنسی کون سی ہے؟", intent="question", language="Urdu"
        )
        self.client["search_queries"] = [query, query.copy()]
        planned = research_queries(self.client)
        self.assertEqual(len(planned), 1)
        self.assertEqual(planned[0]["query"], query["query"])
        self.assertEqual(planned[0]["language"], "Urdu")

    def test_english_pakistan_agency_is_direct_not_excluded_by_language(self):
        candidate = self.make_profile("agency")
        result = select_competitors(self.client, [candidate], self.root / "selection")
        self.assertEqual(len(result["direct_competitors"]), 1)
        self.assertIn("pakistan", result["direct_competitors"][0]["why_comparable"]["markets"])

    def test_unrelated_keywords_and_nonagency_models_rejected(self):
        candidates = [
            self.make_profile("design", service="graphic_design"),
            self.make_profile("publisher", model="publisher"),
            self.make_profile("training", model="training"),
            self.make_profile("software", model="software_product"),
        ]
        result = select_competitors(self.client, candidates, self.root / "selection")
        self.assertEqual(len(result["rejected"]), 4)
        self.assertFalse(result["direct_competitors"])
        self.assertIn(
            "No evidence-backed core service overlap", result["rejected"][0]["reasons"][0]
        )

    def test_international_benchmark_not_direct(self):
        candidate = self.make_profile("global", market="united_states")
        result = select_competitors(self.client, [candidate], self.root / "selection")
        self.assertFalse(result["direct_competitors"])
        self.assertEqual(len(result["aspirational_benchmarks"]), 1)

    def test_missing_customer_overlap_is_rejected_before_scoring(self):
        candidate = self.make_profile("different")
        candidate["fields"]["customer_types"][0]["key"] = "consumers"
        result = select_competitors(self.client, [candidate], self.root / "selection")
        self.assertTrue(result["rejected"])
        self.assertFalse(result["direct_competitors"])

    def test_generic_international_overlap_cannot_make_direct_competitor(self):
        candidate = self.make_profile("worldwide", market="international")
        self.client["brief"] = {
            "fields": {
                "markets": [
                    {"value": "Pakistan", "key": "pakistan"},
                    {"value": "International", "key": "international"},
                ]
            }
        }
        result = select_competitors(self.client, [candidate], self.root / "selection")
        self.assertFalse(result["direct_competitors"])
        benchmark = result["aspirational_benchmarks"][0]
        self.assertEqual(benchmark["score_components"]["markets"], 0)
        self.assertTrue(
            any("specific market evidence" in gap for gap in benchmark["evidence_gaps"])
        )
        candidate["fields"]["markets"].append({"value": "Pakistan", "key": "pakistan"})
        result = select_competitors(self.client, [candidate], self.root / "specific")
        self.assertEqual(len(result["direct_competitors"]), 1)
        self.assertEqual(result["direct_competitors"][0]["score_components"]["markets"], 15)

    def test_profile_requires_native_quote_and_does_not_infer_market(self):
        unreviewed = profile(self.root / "client", self.root / "unreviewed")
        self.assertEqual(unreviewed["fields"]["markets"], [])
        self.assertFalse(unreviewed["queries"])
        bad = review("https://client.test/")
        bad["fields"]["core_services"][0]["evidence"][0]["quote"] = (
            "A fabricated search snippet about AI."
        )
        with self.assertRaisesRegex(ValueError, "must match"):
            profile(self.root / "client", self.root / "bad", review=bad)

    def test_user_context_preserved_and_conflicts_flagged(self):
        brief = {
            "owner_context": "Serve only France for this comparison.",
            "fields": {"markets": [{"value": "France", "key": "france"}]},
        }
        result = profile(
            self.root / "client", self.root / "france", brief, review("https://client.test/")
        )
        self.assertEqual(result["brief"], brief)
        self.assertTrue(result["contradictions"])
        self.assertEqual(result["queries"][0]["market"], "France")

    def test_failed_or_partial_capture_cannot_claim_missing_content(self):
        for alteration in (
            {"error": "Permission denied"},
            {"rendered": {"error": "TimeoutError"}},
            {"rendered": {"readiness": {"deadline_reached": True}}},
            {"rendered": {"javascript_errors": ["app failed"]}},
        ):
            record = page(html="<html><main></main></html>")
            record.update(alteration)
            codes = {r["code"] for r in page_findings(record)}
            self.assertFalse(codes & {"missing_title", "missing_h1", "missing_description"})
            report = readiness([record], {}, {}, {})
            codes = {r["code"] for r in report["pages"][0]["observations"]}
            self.assertFalse(
                codes & {"title_missing", "h1_missing", "schema_review", "main_content_empty"}
            )

    def test_readiness_failure_reports_cause_and_retains_positive_evidence(self):
        record = page(html="<title>Service</title><main>Observed service text</main>")
        record["rendered"] = {
            "data": record["data"],
            "readiness": {"deadline_reached": True, "selector_error": "Timeout waiting for main"},
        }
        quality = capture_quality(record)
        self.assertTrue(quality["usable"])
        self.assertFalse(quality["absence_supported"])
        self.assertEqual(quality["representation"], "rendered")
        self.assertTrue(any("deadline_reached=true" in item for item in quality["limits"]))
        self.assertTrue(any("Timeout waiting for main" in item for item in quality["limits"]))
        finding = next(r for r in page_findings(record) if r["code"] == "capture_incomplete")
        self.assertIn("deadline_reached=true", finding["evidence"])

    def test_blocked_optional_assets_do_not_invent_readiness_failure(self):
        record = page(html="<title>Service</title><main>Observed service text</main>")
        record["rendered"] = {
            "data": record["data"],
            "readiness": {"deadline_reached": False, "text_stable_observed": True},
            "blocked_requests": [{"reason": "resource_type_disabled"}],
        }
        self.assertFalse(capture_quality(record)["limits"])
        self.assertNotIn("capture_incomplete", {r["code"] for r in page_findings(record)})

    def test_svg_labels_are_not_document_titles(self):
        record = page(
            html="<title>Real title</title><svg><title>Graphic label</title></svg><main>Content</main>"
        )
        self.assertEqual(record["data"]["titles"], ["Real title"])
        self.assertNotIn("multiple_titles", {r["code"] for r in page_findings(record)})

    def test_material_findings_have_dates_actions_and_no_invented_metrics(self):
        result = audit_report(self.root / "client", self.root / "report", self.client)
        self.assertTrue(result["findings"])
        for row in result["findings"]:
            for key in [
                "affected_urls",
                "captured_at",
                "claim_type",
                "evidence_refs",
                "why_it_matters",
                "recommended_action",
                "priority",
                "priority_rationale",
                "acceptance_check",
                "uncertainty",
            ]:
                self.assertTrue(row[key], key)
        for metric in [
            "traffic",
            "domain_authority",
            "total_backlinks",
            "keyword_volume",
            "rankings",
        ]:
            self.assertNotIn(metric, result)

    def test_absence_review_cannot_use_failed_page(self):
        record = page()
        record["rendered"] = {"error": "TimeoutError"}
        snapshot(self.root / "partial", record)
        item = {
            "affected_urls": [record["url"]],
            "observation": "No answer",
            "claim_type": "inference",
            "why_it_matters": "Customer question",
            "recommended_action": "Write answer",
            "priority": "P2",
            "priority_rationale": "Sales question",
            "acceptance_check": "Read page",
            "uncertainty": ["partial"],
            "evidence_refs": [
                {
                    "url": record["url"],
                    "quote": "We implement workflow automation for businesses in Pakistan.",
                }
            ],
            "absence_claim": True,
        }
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            audit_report(self.root / "partial", self.root / "report", reviewed_findings=[item])

    def test_native_http_crawl_survives_missing_browser(self):
        from beyondseo.engine import Crawler
        from beyondseo.network import Config

        record = page(html='<title>Shell</title><script src="app.js"></script>')
        with (
            patch.object(Crawler, "fetch_page", return_value=record),
            patch(
                "beyondseo.render.render_page",
                side_effect=ModuleNotFoundError("No module named playwright"),
            ),
        ):
            crawler = Crawler(
                Config(record["url"], max_pages=1, sitemaps=False, render_mode="auto"),
                self.root / "no-browser",
            )
            try:
                crawler.log = lambda _: None
                result = crawler.run()
            finally:
                crawler.close()
        self.assertEqual(result["attempted_urls"], 1)
        self.assertEqual(result["render_errors"], 1)
        issues = json.loads((self.root / "no-browser/issues.json").read_text())
        self.assertNotIn("missing_h1", {r["code"] for r in issues})


class PartialLinkTests(unittest.TestCase):
    def test_unfinished_render_does_not_establish_link_absence(self):
        from beyondseo.backlinks import verify_source

        record = page()
        record["rendered"] = {"readiness": {"deadline_reached": True}}
        with tempfile.TemporaryDirectory() as folder:
            with (
                patch("beyondseo.backlinks.Crawler") as crawler,
                patch("beyondseo.backlinks.read_pages", return_value=[record]),
            ):
                crawler.return_value.run.return_value = {"coverage_limited": True}
                result = verify_source(
                    "https://client.test/", "other.test", Path(folder), mode="http"
                )
        self.assertEqual(result["verification"], "unverified_access")


class BrowserSetupTests(unittest.TestCase):
    def test_ready_browser_is_reused_without_installation(self):
        from beyondseo.doctor import prepare_browser

        with (
            patch("beyondseo.doctor.environment_report", return_value={"browser_ready": True}),
            patch("beyondseo.doctor.subprocess.run") as install,
        ):
            result = prepare_browser()
        self.assertEqual(result["status"], "already_ready")
        install.assert_not_called()

    def test_missing_components_installed_then_launch_checked(self):
        from beyondseo.doctor import prepare_browser

        missing = {
            "browser_ready": False,
            "packages": {"playwright": None},
            "checks": {"browser_runtime": {"failure": {"code": "missing_dependency"}}},
        }
        with (
            patch(
                "beyondseo.doctor.environment_report",
                side_effect=[missing, {"browser_ready": True}],
            ),
            patch("beyondseo.doctor.sys.prefix", "/approved/runtime"),
            patch("beyondseo.doctor.sys.base_prefix", "/system"),
            patch("beyondseo.doctor.subprocess.run") as install,
        ):
            install.return_value.returncode = 0
            result = prepare_browser()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(install.call_count, 2)
        self.assertIn("playwright>=1.48,<2", install.call_args_list[0].args[0])
        self.assertEqual(
            install.call_args_list[1].args[0][-3:], ["playwright", "install", "chromium"]
        )

    def test_browser_denial_does_not_trigger_reinstallation(self):
        from beyondseo.doctor import prepare_browser

        denied = {
            "browser_ready": False,
            "checks": {
                "browser_runtime": {
                    "failure": {"code": "execution_denied", "evidence": "Permission denied"}
                }
            },
        }
        with (
            patch("beyondseo.doctor.environment_report", return_value=denied),
            patch("beyondseo.doctor.subprocess.run") as install,
        ):
            result = prepare_browser()
        self.assertEqual(result["status"], "blocked")
        install.assert_not_called()

    def test_blocking_business_conflict_prevents_direct_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            snapshot(root / "site", page())
            client = profile(root / "site", root / "profile", review=review("https://client.test/"))
            candidate = dict(
                client,
                target="https://conflicting.test/",
                contradictions=[
                    {"blocking": True, "observation": "Agency and publisher identity conflict."}
                ],
            )
            result = select_competitors(client, [candidate], root / "selection")
        self.assertFalse(result["direct_competitors"])
        self.assertIn("Unresolved comparison conflict", result["rejected"][0]["reasons"][0])
