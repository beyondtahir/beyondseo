import copy
import csv
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def script_module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


posting = script_module("backlink_sources")
importer = script_module("import_backlink_pdf")
TODAY = date(2026, 9, 15)


class PostingCatalogTests(unittest.TestCase):
    def setUp(self):
        self.sites = posting.load_sources()
        self.profile = json.loads((ROOT / "examples/posting-profile.json").read_text())
        self.profile["start_date"] = TODAY.isoformat()

    def plan(self, **kwargs):
        return posting.build_plan(self.profile, self.sites, as_of=TODAY, **kwargs)

    def test_visible_rows_preserve_unlinked_entries_and_duplicates(self):
        rows = importer.parse_pages(
            [
                "Free article websites\nhttps://medium.com 94 index\nhttps://plain.example/write 20 index",
                "Free POSTING website\nhttps://medium.com 30 no follow\nhttps://plain.example/write 20 index",
            ]
        )
        self.assertEqual(len(rows), 4)
        self.assertEqual([r["source_page"] for r in rows], [1, 1, 2, 2])
        self.assertEqual(rows[-1]["source_section"], "posting")
        sites = importer.group_rows(rows)
        self.assertEqual(len(sites), 2)
        self.assertEqual(sites[0]["sheet_dr_values"], [94, 30])
        self.assertTrue(sites[0]["sheet_dr_conflict"])
        self.assertEqual(sites[1]["source_rows"], ["pdf-002", "pdf-004"])
        self.assertIsNone(sites[0]["observed_link_rel"])
        self.assertEqual(sites[0]["indexing_status"], "not_checked")

    def test_bad_visible_rows_fail_instead_of_silently_disappearing(self):
        for text in ("https://example.com nonsense", "https://example.com 101 index", "No URLs"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                importer.parse_pages([text])
        for url in ("https://:password@example.com", "https://@example.com", "file:///etc/hosts"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                importer.site_key(url)

    def test_routes_group_by_site_but_separate_community_hosts(self):
        self.assertEqual(importer.site_key("https://WWW.Example.com/profile/a"), "example.com")
        self.assertEqual(importer.site_key("https://business.quora.com/"), "quora.com")
        self.assertNotEqual(
            importer.site_key("https://a.mn.co"), importer.site_key("https://b.mn.co")
        )

    def test_every_original_record_is_mapped_exactly_once(self):
        with (ROOT / "playbooks/backlink-system/backlink-source-database.csv").open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 241)
        self.assertEqual(len({r["source_url"] for r in rows}), 237)
        self.assertEqual(len(self.sites), 206)
        by_id = {r["id"]: r for r in rows}
        counts = Counter(r for s in self.sites for r in s["source_rows"])
        self.assertEqual(set(counts), set(by_id))
        self.assertEqual(set(counts.values()), {1})
        for site in self.sites:
            sources = [by_id[r] for r in site["source_rows"]]
            self.assertEqual(set(site["source_urls"]), {r["source_url"] for r in sources})
            self.assertEqual(set(site["sheet_dr_values"]), {int(r["sheet_dr"]) for r in sources})
            self.assertIsNone(site["current_da"])
            self.assertIsNone(site["current_dr"])
        self.assertEqual(sum(s["sheet_dr_conflict"] for s in self.sites), 28)

    def test_browsing_filters_case_insensitively(self):
        self.assertEqual([r["id"] for r in posting.load_sources("mEdIuM")], ["medium.com"])
        rows = posting.load_sources(category="TRAVEL", status="guidance_reviewed")
        self.assertTrue(rows)
        self.assertTrue(all("travel" in r["topics"] for r in rows))
        self.assertNotIn("dev.to", {r["id"] for r in rows})

    def test_technology_plan_has_15_distinct_usable_briefs(self):
        plan = self.plan()
        self.assertEqual(plan["selected_sources"], 15)
        self.assertEqual(len({t["site_id"] for t in plan["tasks"]}), 15)
        self.assertEqual(plan["shortfall"], 0)
        targets = {p["url"] for p in self.profile["pages"]}
        for task in plan["tasks"]:
            self.assertIn(task["target_page"], targets)
            self.assertEqual(task["target_page_status"], "planned")
            self.assertTrue(task["outline"])
            self.assertTrue(task["how_to_post"])
            self.assertTrue(task["guidance_sources"])
            self.assertIsNone(task["current_da"])

    def test_20_source_plan_requires_real_resources_and_excludes_missing_eligibility(self):
        self.profile["assets"] = ["public_code", "public_demo", "public_resource"]
        plan = self.plan(limit=20)
        self.assertEqual(plan["selected_sources"], 20)
        selected = {t["site_id"] for t in plan["tasks"]}
        self.assertTrue(
            {"github.com", "news.ycombinator.com", "sites.google.com"}.issubset(selected)
        )
        self.assertNotIn("vocal.media", selected)
        self.profile["assets"] = []
        limited = self.plan(limit=20)
        self.assertGreater(limited["shortfall"], 0)
        self.assertFalse(
            {"github.com", "news.ycombinator.com", "vocal.media"}
            & {t["site_id"] for t in limited["tasks"]}
        )

    def test_unrelated_industry_does_not_get_technology_sources_or_padded_quota(self):
        self.profile["topics"] = ["travel"]
        self.profile["audience"] = "families planning a holiday"
        self.profile["pages"][0]["topic"] = "choosing a family itinerary"
        plan = self.plan(limit=20)
        self.assertGreater(plan["shortfall"], 0)
        selected = {t["site_id"] for t in plan["tasks"]}
        self.assertFalse(
            {"dev.to", "github.com", "hashnode.com", "hackernoon.com", "joinentre.com"} & selected
        )
        self.assertEqual(plan["selected_sources"] + plan["shortfall"], 20)

    def test_sheet_dr_cannot_change_selection_or_inflate_measured_metrics(self):
        before = [t["site_id"] for t in self.plan()["tasks"]]
        for site in self.sites:
            site["sheet_dr_values"] = [100] if site["readiness"] == "research_first" else [1]
        after = self.plan()
        self.assertEqual(before, [t["site_id"] for t in after["tasks"]])
        self.assertTrue(
            all(t["current_da"] is None and t["current_dr"] is None for t in after["tasks"])
        )

    def test_closed_unreviewed_unknown_cost_and_stale_routes_are_excluded(self):
        base = next(s for s in self.sites if s["id"] == "medium.com")
        variants = [
            {"review_status": "closed"},
            {"review_status": "unreviewed"},
            {"cost_status": "unknown"},
            {"posting_url": ""},
            {"reviewed_at": (TODAY - timedelta(days=91)).isoformat()},
            {"reviewed_at": (TODAY + timedelta(days=1)).isoformat()},
            {"requirements": ["missing_asset"]},
            {"regions": ["Australia"]},
            {"review_sources": []},
            {"how_to_post": []},
        ]
        self.sites = [
            dict(copy.deepcopy(base), id=f"case{i}", **changes)
            for i, changes in enumerate(variants)
        ]
        plan = self.plan()
        self.assertEqual(plan["selected_sources"], 0)
        self.assertEqual(plan["shortfall"], 15)
        self.assertEqual(len(plan["excluded"]), len(variants))

    def test_duplicate_entries_cannot_fill_shortlist(self):
        self.sites = [self.sites[0], copy.deepcopy(self.sites[0])]
        self.assertEqual(self.plan()["selected_sources"], 1)
        self.assertEqual(self.plan()["catalog_sites_considered"], 1)

    def test_schedule_respects_week_one_preparation_and_capacity(self):
        self.profile["posts_per_week"] = 3
        tasks = self.plan()["tasks"]
        self.assertTrue(
            all(date.fromisoformat(t["suggested_date"]) >= TODAY + timedelta(days=7) for t in tasks)
        )
        self.assertLessEqual(max(Counter(t["suggested_week"] for t in tasks).values()), 3)
        self.assertEqual(len({t["suggested_date"] for t in tasks}), len(tasks))

    def test_different_formats_receive_different_writing_briefs(self):
        tasks = {t["site_id"]: t for t in self.plan()["tasks"]}
        self.assertNotEqual(tasks["quora.com"]["outline"], tasks["medium.com"]["outline"])
        self.assertNotEqual(tasks["flipboard.com"]["outline"], tasks["reddit.com"]["outline"])
        self.assertNotEqual(tasks["tumblr.com"]["outline"], tasks["medium.com"]["outline"])

    def test_invalid_profiles_and_limits_are_rejected(self):
        for value in (
            None,
            [],
            {},
            dict(self.profile, topics=[]),
            dict(self.profile, posts_per_week=True),
            dict(self.profile, posts_per_week=8),
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                posting.build_plan(value, self.sites)
        for url in (
            "ftp://example.com",
            "https://:secret@example.com",
            "https://example .com",
            "https://example.com:abc",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                posting.validate_url(url)
        for limit in (0, -1, 21, True):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.plan(limit=limit)

    def test_cli_rejects_zero_limit_with_and_without_profile(self):
        for args in ([], ["--profile", str(ROOT / "examples/posting-profile.json")]):
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts/backlink_sources.py"), "--limit", "0", *args],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)

    def test_cli_exports_consistent_json_markdown_csv_and_neutralizes_formulas(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            # Exercise the real CLI with a fresh local catalog, independent of release age.
            cli = tmp / "bundle/scripts/backlink_sources.py"
            cli.parent.mkdir(parents=True)
            cli.write_bytes((ROOT / "scripts/backlink_sources.py").read_bytes())
            catalog = tmp / "bundle/playbooks/backlink-system/posting-sites.json"
            catalog.parent.mkdir(parents=True)
            fixture = copy.deepcopy(self.sites)
            for site in fixture:
                if site["review_status"] == "guidance_reviewed":
                    site["reviewed_at"] = date.today().isoformat()
            catalog.write_text(json.dumps(fixture), encoding="utf-8")
            self.profile["business"] = "=UNTRUSTED()"
            for page in self.profile["pages"]:
                page["topic"] = "=UNTRUSTED()"
            profile_path = tmp / "business.json"
            profile_path.write_text(json.dumps(self.profile))
            result = subprocess.run(
                [
                    sys.executable,
                    str(cli),
                    "--profile",
                    str(profile_path),
                    "--limit",
                    "15",
                    "--out",
                    str(tmp / "plan"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads((tmp / "plan/posting-plan.json").read_text())
            with (tmp / "plan/posting-plan.csv").open(encoding="utf-8-sig") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), data["selected_sources"])
            for row, task in zip(rows, data["tasks"]):
                self.assertEqual(row["how_to_post"], "\n".join(task["how_to_post"]))
                self.assertEqual(row["current_da"], "not measured")
                self.assertEqual(row["link_guidance"], task["link_guidance"])
            markdown = (tmp / "plan/posting-plan.md").read_text()
            for task in data["tasks"]:
                self.assertIn(task["posting_url"], markdown)
            self.assertTrue(
                all(
                    not str(v).lstrip().startswith(("=", "+", "-", "@"))
                    for row in rows
                    for v in row.values()
                )
            )
            self.assertTrue(any(row["suggested_title_or_action"].startswith("'=") for row in rows))


if __name__ == "__main__":
    unittest.main()
