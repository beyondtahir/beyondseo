"""Specialist assignments remain scoped plans until a host actually delegates."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from beyondseo.cli import main
from beyondseo.research_cli import setup_agents, swarm_plan


class SwarmPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_team_has_named_specialists_and_never_claims_execution(self):
        with patch("socket.create_connection", side_effect=AssertionError("no network in plan")):
            result = swarm_plan("https://example.com", self.root / "plan")
        ids = {entry["id"] for entry in result["specialists"]}
        self.assertTrue(
            {
                "seo-aeo",
                "seo-geo",
                "seo-entity",
                "seo-authority",
                "seo-reputation",
                "seo-backlinks",
            }.issubset(ids)
        )
        self.assertEqual(result["agents_launched"], 0)
        self.assertEqual(result["status"], "planned")
        root = Path(__file__).resolve().parents[1]
        for entry in result["specialists"]:
            self.assertTrue((root / entry["reference"]).is_file(), entry["reference"])
        self.assertTrue(all(entry["status"] == "planned" for entry in result["specialists"]))
        self.assertIn("sequentially", result["execution_note"])
        self.assertTrue(
            any("shared" in item and "budget" in item for item in result["shared_setup"])
        )
        self.assertEqual(
            json.loads((self.root / "plan/swarm-plan.json").read_text())["agents_launched"], 0
        )

    def test_user_focus_and_concurrency_are_preserved(self):
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            status = main(
                [
                    "swarm-plan",
                    "--url",
                    "https://example.com",
                    "--specialist",
                    "seo-aeo",
                    "--specialist",
                    "seo-geo",
                    "--max-parallel",
                    "2",
                    "--out",
                    str(self.root / "focused"),
                ]
            )
        self.assertEqual(status, 0)
        result = json.loads(stream.getvalue())
        self.assertEqual([row["id"] for row in result["specialists"]], ["seo-aeo", "seo-geo"])
        self.assertEqual(result["max_parallel_requested"], 2)
        self.assertEqual(result["agents_launched"], 0)

    def test_invalid_input_fails_before_output_and_existing_plan_is_preserved(self):
        out = self.root / "plan"
        for url, roles, maximum in [
            ("https://user:password@example.com", [], 4),
            ("https://example.com", ["unknown"], 4),
            ("https://example.com", [], 9),
        ]:
            with self.subTest(url=url, roles=roles, maximum=maximum):
                with self.assertRaises(ValueError):
                    swarm_plan(url, out, roles, maximum)
                self.assertFalse(out.exists())
        swarm_plan("https://example.com", out)
        original = (out / "swarm-plan.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "already exists"):
            swarm_plan("https://example.org", out)
        self.assertEqual((out / "swarm-plan.json").read_bytes(), original)

    def test_publisher_is_opt_in_and_contains_publishing_authorization_scope(self):
        routine = swarm_plan("https://example.com", self.root / "routine")
        self.assertNotIn("seo-publisher", {r["id"] for r in routine["specialists"]})
        campaign = swarm_plan("https://example.com", self.root / "campaign", ["seo-publisher"])
        self.assertEqual(
            campaign["specialists"][0]["authorization_scope"], "explicit publishing campaign"
        )
        self.assertEqual(campaign["agents_launched"], 0)

    def test_host_definitions_are_real_scoped_files_and_settings_are_preserved(self):
        for host, hidden, extension in [
            ("codex", ".codex", ".toml"),
            ("claude-code", ".claude", ".md"),
        ]:
            with self.subTest(host=host):
                project = self.root / host
                (project / hidden).mkdir(parents=True)
                settings = project / hidden / "config.toml"
                settings.write_text("existing_setting = true\n")
                plan = setup_agents(host, project, True)
                self.assertEqual(plan["status"], "planned")
                self.assertFalse((project / hidden / "agents").exists())
                result = setup_agents(host, project)
                self.assertEqual(len(result["files"]), 11)
                self.assertEqual(result["agents_launched"], 0)
                self.assertIn("not_tested", result["host_registration"])
                self.assertEqual(settings.read_text(), "existing_setting = true\n")
                for filename in result["files"]:
                    path = Path(filename)
                    self.assertEqual(path.suffix, extension)
                    content = path.read_text()
                    self.assertIn("BeyondSEO", content)
                    self.assertNotIn("model =", content)
                    if host == "codex":
                        try:
                            import tomllib
                        except ImportError:
                            pass  # Python 3.10 keeps the same generated basic-string format.
                        else:
                            parsed = tomllib.loads(content)
                            self.assertTrue(parsed["name"].startswith("beyondseo_"))
                            self.assertIn("shared evidence", parsed["developer_instructions"])
                first = Path(result["files"][0])
                first.write_text("User's custom role")
                with self.assertRaisesRegex(ValueError, "already exists"):
                    setup_agents(host, project)
                self.assertEqual(first.read_text(), "User's custom role")


if __name__ == "__main__":
    unittest.main()
