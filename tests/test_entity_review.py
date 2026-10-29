"""Saved entity review is an evidence inventory, not a semantic or authority score."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from beyondseo.cli import main
from beyondseo.review import entity_review


class EntityReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.crawl = self.root / "crawl"
        self.crawl.mkdir()

    def page(self, path, schema):
        return {
            "url": "https://example.com/" + path,
            "final_url": "https://example.com/" + path,
            "status": 200,
            "error": "",
            "fetched_at": "2026-10-29T20:00:00+00:00",
            "data": {
                "title": "Example page",
                "word_count": 200,
                "script_count": 0,
                "jsonld": schema,
                "jsonld_errors": [],
            },
        }

    def review(self, pages, name="review"):
        (self.crawl / "pages.jsonl").write_text(
            "\n".join(json.dumps(p) for p in pages), encoding="utf-8"
        )
        with patch("socket.create_connection", side_effect=AssertionError("offline review")):
            return entity_review(self.crawl, self.root / name)

    def test_same_stable_id_conflicting_names_and_urls_are_review_candidates(self):
        result = self.review(
            [
                self.page(
                    "about",
                    [
                        {
                            "@type": "Person",
                            "@id": "https://example.com/#person",
                            "name": "Alice Jones",
                            "url": "https://alice.example/",
                            "sameAs": ["https://profiles.example/alice"],
                        }
                    ],
                ),
                self.page(
                    "contact",
                    [
                        {
                            "@type": "Person",
                            "@id": "https://example.com/#person",
                            "name": "Robert Brown",
                            "url": "https://robert.example/",
                        }
                    ],
                ),
            ]
        )
        self.assertEqual({c["property"] for c in result["review_candidates"]}, {"name", "url"})
        self.assertTrue(
            all(c["classification"] == "review_candidate" for c in result["review_candidates"])
        )
        for candidate in result["review_candidates"]:
            self.assertIn("not a schema defect", candidate["limits"])
            self.assertTrue(
                all(
                    e["captured_at"] == "2026-10-29T20:00:00+00:00"
                    for e in candidate["observed_declarations"]
                )
            )
            self.assertEqual(
                {e["url"] for e in candidate["observed_declarations"]},
                {"https://example.com/about", "https://example.com/contact"},
            )
        person = next(r for r in result["entities"] if r["name"] == ["Alice Jones"])
        self.assertEqual(person["same_as"], ["https://profiles.example/alice"])

    def test_distinct_people_and_organisations_are_not_treated_as_defects(self):
        result = self.review(
            [
                self.page(
                    "team",
                    [
                        {
                            "@graph": [
                                {
                                    "@id": "https://example.com/#alice",
                                    "@type": "Person",
                                    "name": "Alice Jones",
                                },
                                {
                                    "@id": "https://example.com/#company",
                                    "@type": "Organization",
                                    "name": "Example Company",
                                    "founder": {"@id": "https://example.com/#alice"},
                                },
                            ]
                        }
                    ],
                ),
                self.page(
                    "author",
                    [
                        {
                            "@id": "https://example.com/#robert",
                            "@type": "Person",
                            "name": "Robert Brown",
                            "worksFor": {"@id": "https://example.com/#company"},
                        }
                    ],
                ),
            ]
        )
        self.assertEqual(len(result["entities"]), 3)
        self.assertEqual(result["review_candidates"], [])
        self.assertEqual(result["coverage"]["stable_uri_ids_observed"], 3)

    def test_fragments_are_preserved_and_alternative_ids_are_not_automatic_defects(self):
        result = self.review(
            [
                self.page(
                    "about",
                    [
                        {
                            "@id": "https://example.com/#person",
                            "@type": "Person",
                            "name": "Alice Jones",
                        }
                    ],
                ),
                self.page(
                    "contact",
                    [
                        {
                            "@id": "https://example.com/#person-mta",
                            "@type": "Person",
                            "name": "Alice Jones",
                        }
                    ],
                ),
            ]
        )
        self.assertEqual(
            {r["entity_id"] for r in result["entities"]},
            {"https://example.com/#person", "https://example.com/#person-mta"},
        )
        self.assertEqual(result["coverage"]["stable_uri_ids_observed"], 2)
        self.assertEqual(result["review_candidates"], [])

    def test_relative_ids_resolve_to_their_document_and_blank_ids_are_scoped(self):
        result = self.review(
            [
                self.page(
                    "about",
                    [
                        {"@id": "#person", "@type": "Person", "name": "Alice Jones"},
                        {"@id": "_:person", "@type": "Person", "name": "Alice Jones"},
                    ],
                ),
                self.page(
                    "contact",
                    [
                        {"@id": "#person", "@type": "Person", "name": "Robert Brown"},
                        {"@id": "_:person", "@type": "Person", "name": "Robert Brown"},
                    ],
                ),
            ]
        )
        self.assertEqual(result["coverage"]["stable_uri_ids_observed"], 2)
        self.assertTrue(
            {"https://example.com/about#person", "https://example.com/contact#person"}.issubset(
                {r["entity_id"] for r in result["entities"]}
            )
        )
        self.assertEqual(result["review_candidates"], [])
        self.assertEqual(
            sum(r["identifier_scope"] == "document_blank_node" for r in result["entities"]), 2
        )

    def test_partial_positive_observations_survive_but_failed_capture_is_not_missing_schema(self):
        partial = self.page("partial", [])
        partial["rendered"] = {
            "fetched_at": "2026-10-29T20:01:00+00:00",
            "readiness": {"deadline_reached": True},
            "data": {
                **partial["data"],
                "jsonld": [
                    {"@type": "Person", "@id": "https://example.com/#alice", "name": "Alice Jones"}
                ],
            },
        }
        failed = self.page(
            "failed", [{"@type": "Person", "name": "Stale content must not be counted"}]
        )
        failed.update(status=403, error="access_denied")
        result = self.review([partial, failed])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["coverage"]["partial_captures"], 1)
        self.assertEqual(result["coverage"]["unusable_captures"], 1)
        self.assertEqual(len(result["entities"]), 1)
        self.assertTrue(result["entities"][0]["capture_limited"])
        self.assertEqual(result["entities"][0]["captured_at"], "2026-10-29T20:01:00+00:00")
        self.assertEqual(result["review_candidates"], [])
        self.assertFalse(result["pages"][1]["capture_usable"])
        self.assertEqual(result["pages"][1]["observed_definitions"], 0)
        self.assertNotIn("missing_schema", json.dumps(result))

    def test_malformed_schema_is_retained_as_parse_evidence_not_an_absence_claim(self):
        page = self.page("parse", [])
        page["data"]["jsonld_errors"] = ["Block 1: invalid JSON"]
        result = self.review([page])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["pages"][0]["jsonld_parse_errors"], ["Block 1: invalid JSON"])
        self.assertEqual(result["review_candidates"], [])
        self.assertEqual(result["entities"], [])
        self.assertNotIn("schema_missing", json.dumps(result))

    def test_absent_properties_known_aliases_and_case_variations_are_not_conflicts(self):
        result = self.review(
            [
                self.page(
                    "a",
                    [
                        {
                            "@id": "https://example.com/#person",
                            "@type": "Person",
                            "name": "Alice Jones",
                            "alternateName": "AJ",
                            "url": "https://example.com",
                            "sameAs": ["https://profile.example/alice"],
                        }
                    ],
                ),
                self.page(
                    "b",
                    [
                        {
                            "@id": "https://example.com/#person",
                            "@type": "Person",
                            "name": "AJ",
                            "url": "https://EXAMPLE.COM/",
                        }
                    ],
                ),
                self.page("c", [{"@id": "https://example.com/#person", "@type": "Person"}]),
            ]
        )
        self.assertEqual(result["review_candidates"], [])

    def test_relationship_variation_is_observed_without_claiming_invalid_semantics(self):
        result = self.review(
            [
                self.page(
                    "home",
                    [
                        {
                            "@id": "https://example.com/#website",
                            "@type": "WebSite",
                            "name": "Example",
                            "publisher": {"@id": "https://example.com/#alice"},
                        }
                    ],
                ),
                self.page(
                    "about",
                    [
                        {
                            "@id": "https://example.com/#website",
                            "@type": "WebSite",
                            "name": "Example",
                            "publisher": {"@id": "https://example.com/#company"},
                        }
                    ],
                ),
            ]
        )
        self.assertEqual(len(result["review_candidates"]), 1)
        candidate = result["review_candidates"][0]
        self.assertEqual(candidate["property"], "publisher")
        self.assertIn("legitimate", candidate["why_review"])
        self.assertEqual(candidate["classification"], "review_candidate")

    def test_equivalent_relationship_reference_formats_do_not_create_a_candidate(self):
        result = self.review(
            [
                self.page(
                    "home",
                    [
                        {
                            "@id": "https://example.com/#website",
                            "@type": "WebSite",
                            "publisher": "https://example.com/#alice",
                        }
                    ],
                ),
                self.page(
                    "about",
                    [
                        {
                            "@id": "https://example.com/#website",
                            "@type": "WebSite",
                            "publisher": {"@id": "https://example.com/#alice"},
                        }
                    ],
                ),
            ]
        )
        self.assertEqual(result["review_candidates"], [])

    def test_inspection_depth_is_bounded_and_marked_partial(self):
        node = {"@type": "Person", "name": "Deep node"}
        for _ in range(70):
            node = {"nested": node}
        result = self.review([self.page("deep", [node])])
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["pages"][0]["inspection_limits"])
        self.assertEqual(result["review_candidates"], [])

    def test_cli_preserves_existing_output_and_makes_no_unsupported_metric_claim(self):
        result = self.review([self.page("empty", [])])
        self.assertEqual(result["status"], "no_observations")
        for key in ("score", "authority_score", "ai_score", "rank", "complete_schema_validity"):
            self.assertNotIn(key, result)
        original = (self.root / "review/entity-review.json").read_bytes()
        with contextlib.redirect_stderr(io.StringIO()) as error:
            code = main(
                ["entity-review", "--crawl", str(self.crawl), "--out", str(self.root / "review")]
            )
        self.assertEqual(code, 2)
        self.assertIn("already exists", error.getvalue())
        self.assertEqual((self.root / "review/entity-review.json").read_bytes(), original)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = main(
                [
                    "entity-review",
                    "--crawl",
                    str(self.crawl),
                    "--out",
                    str(self.root / "cli-review"),
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "no_observations")

    def test_report_escapes_untrusted_entity_markup_and_json_keeps_observed_value(self):
        name = '<img src="https://untrusted.example/image" onerror="alert(1)">'
        result = self.review([self.page("markup", [{"@type": "Person", "name": name}])])
        self.assertEqual(result["entities"][0]["name"], [name])
        markdown = (self.root / "review/entity-review.md").read_text()
        self.assertNotIn("<img", markdown)
        self.assertIn("&lt;img", markdown)


if __name__ == "__main__":
    unittest.main()
