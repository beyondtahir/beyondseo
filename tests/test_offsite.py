"""Publishing checkpoints preserve authority, originality and actual evidence states."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from beyondseo import offsite
from beyondseo.network import utcnow


class OffsiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = self.root / "plan.json"
        self.plan.write_text(
            json.dumps(
                {
                    "website": "https://example.com",
                    "tasks": [
                        {
                            "site_id": "publisher.example",
                            "posting_url": "https://publisher.example/write",
                            "target_page": "https://example.com/service",
                            "format": "article",
                        }
                        for _ in range(7)
                    ],
                }
            )
        )
        self.folder = self.root / "campaign"
        offsite.initialise(self.plan, self.folder)

    def event(self, event, ident="post-001", **values):
        path = self.root / "event.json"
        path.write_text(json.dumps({"event": event, **values}))
        return offsite.record(self.folder, ident, path)

    def draft(self, ident="post-001", seed="a"):
        path = self.root / "draft.json"
        path.write_text(
            json.dumps(
                {
                    "title": "A useful decision " + seed,
                    "body": " ".join(f"{seed}word{i}" for i in range(190)),
                    "opening_answer": "A direct answer " + seed,
                    "unique_angle": "A distinct useful angle " + seed,
                    "reader": "Local business owners",
                    "author_voice": "Clear practitioner voice using verified experience",
                    "source_urls": ["https://example.com/service"],
                }
            )
        )
        return offsite.set_draft(self.folder, ident, path)

    def prepare(self, ident="post-001", seed="a", policy="allowed", weekly=None):
        self.event(
            "authorize",
            ident,
            scope="standing_campaign",
            user_instruction="Publish the reviewed campaign on these selected sites at five articles per week.",
        )
        self.event(
            "rules",
            ident,
            source_url="https://publisher.example/rules",
            checked_at=utcnow(),
            ai_policy=policy,
            submission_permitted=True,
            notes="Original educational articles; disclose affiliation; one supporting resource permitted.",
            weekly_site_limit=weekly,
        )
        self.event("account_ready", ident)
        draft = self.draft(ident, seed)
        self.event("approve", ident, digest=draft["digest"], disclosure_confirmed=True)
        return draft

    def test_initialisation_is_proposal_not_scheduler_or_permission(self):
        data = offsite.read(self.folder / "campaign.json")
        self.assertEqual(data["weekly_target"], 5)
        self.assertIsNone(data["authorization"])
        self.assertIsNone(data["scheduler"])
        self.assertEqual({t["status"] for t in data["tasks"]}, {"planned"})
        self.assertTrue(all(t["public_url"] is None for t in data["tasks"]))

    def test_article_campaign_excludes_community_answer_and_unknown_formats(self):
        data = json.loads(self.plan.read_text())
        data["tasks"][0]["format"] = "community"
        data["tasks"][1]["format"] = "answer"
        data["tasks"][2].pop("format")
        self.plan.write_text(json.dumps(data))
        result = offsite.initialise(self.plan, self.root / "articles-only")
        self.assertEqual(len(result["tasks"]), 4)
        self.assertEqual(len(result["excluded_non_article_tasks"]), 3)
        self.assertEqual(result["tasks"][0]["proposed_date"], result["created_at"][:10])

    def test_complete_article_is_written_before_signup_without_implying_access(self):
        self.event("awaiting_signup")
        draft = self.draft()
        self.assertEqual(draft["status"], "draft_ready")
        self.assertFalse(offsite.read(self.folder / "campaign.json")["tasks"][0]["account_ready"])
        with self.assertRaises(ValueError):
            offsite.preflight(self.folder, "post-001")

    def test_submission_requires_permission_rules_account_and_exact_draft(self):
        self.draft()
        with self.assertRaises(ValueError):
            self.event("submitted", receipt="not actually permitted")
        draft = self.prepare()
        self.assertEqual(offsite.preflight(self.folder, "post-001")["digest"], draft["digest"])
        self.draft(seed="replacement")
        with self.assertRaises(ValueError):
            offsite.preflight(self.folder, "post-001")

    def test_per_article_permission_is_preserved(self):
        self.prepare()
        self.event(
            "authorize",
            scope="review_each_article",
            user_instruction="Ask me to approve every final article.",
        )
        self.draft(seed="newdraft")
        data = offsite.read(self.folder / "campaign.json")
        with self.assertRaisesRegex(ValueError, "approval"):
            self.event("approve", digest=offsite.digest(data["tasks"][0]["draft"]))

    def test_stricter_campaign_permission_invalidates_existing_standing_approval(self):
        staged = self.prepare()
        self.assertEqual(
            offsite.preflight(self.folder, "post-001")["status"], "ready_for_host_submission"
        )
        self.event(
            "authorize",
            scope="review_each_article",
            user_instruction="I now want to approve each individual article.",
        )
        with self.assertRaises(ValueError):
            offsite.preflight(self.folder, "post-001")
        with self.assertRaises(ValueError):
            self.event("approve", digest=staged["digest"])
        self.event(
            "approve", digest=staged["digest"], user_approval="Approved this exact current draft."
        )
        self.assertEqual(
            offsite.preflight(self.folder, "post-001")["status"], "ready_for_host_submission"
        )

    def test_known_site_limit_survives_an_unknown_limit_on_another_article(self):
        self.prepare(weekly=1)
        self.event("submitted", receipt="Observed browser receipt")
        self.prepare("post-002", "other-article", weekly=None)
        with self.assertRaisesRegex(ValueError, "site's"):
            offsite.preflight(self.folder, "post-002")
        # Revising the first task's rule observation to unknown cannot erase a
        # previously established restriction on the publisher.
        self.event(
            "rules",
            source_url="https://publisher.example/rules",
            checked_at=utcnow(),
            ai_policy="allowed",
            submission_permitted=True,
            notes="The quota is not visible in this capture.",
            weekly_site_limit=None,
        )
        with self.assertRaisesRegex(ValueError, "site's"):
            offsite.preflight(self.folder, "post-002")

    def test_private_monitor_reads_campaign_progress_without_exposing_drafts(self):
        from beyondseo import projects

        project = self.root / "project"
        projects.init_project(project, "https://example.com", "Improve search visibility")
        projects.link_campaign(project, self.folder)
        self.assertIsNone(projects.snapshot(project)["publishing"]["tasks"][0]["public_url"])
        self.prepare()
        state = projects.snapshot(project)
        self.assertEqual(state["publishing"]["tasks"][0]["status"], "approved")
        self.assertNotIn("body", json.dumps(state["publishing"]))
        self.assertNotIn(str(self.folder), json.dumps(state))
        page = projects.dashboard_html(state)
        self.assertIn("Article publishing", page)
        self.assertIn("approved", page)
        # Linking does not enable the optional dashboard or create a schedule.
        self.assertFalse(state["dashboard"])
        self.assertIsNone(state["schedule"])
        self.plan.write_text(
            json.dumps(
                {
                    "website": "https://other.example",
                    "tasks": [
                        {
                            "site_id": "publisher.example",
                            "posting_url": "https://publisher.example/write",
                            "target_page": "https://other.example/page",
                            "format": "article",
                        }
                    ],
                }
            )
        )
        other = self.root / "other-campaign"
        offsite.initialise(self.plan, other)
        with self.assertRaisesRegex(ValueError, "no longer matches"):
            projects.link_campaign(project, other)

    def test_ai_prohibition_and_unknown_policy_do_not_allow_submission(self):
        for policy in ("prohibited", "unknown"):
            with self.subTest(policy=policy):
                with self.assertRaisesRegex(ValueError, "not established"):
                    self.prepare(policy=policy)

    def test_required_disclosure_is_checked(self):
        self.prepare(policy="disclosure_required")
        data = offsite.read(self.folder / "campaign.json")
        with self.assertRaisesRegex(ValueError, "disclosure"):
            self.event("approve", digest=offsite.digest(data["tasks"][0]["draft"]))

    def test_reused_article_with_new_title_and_angle_is_rejected(self):
        self.draft()
        path = self.root / "draft.json"
        draft = json.loads(path.read_text())
        draft.update(title="Different heading", unique_angle="Different label")
        path.write_text(json.dumps(draft))
        with self.assertRaisesRegex(ValueError, "substantial wording"):
            offsite.set_draft(self.folder, "post-002", path)
        self.draft("post-002", "genuinelydifferent")

    def test_weekly_campaign_and_platform_limits_are_checked_before_click(self):
        for i in range(1, 6):
            ident = f"post-{i:03d}"
            self.prepare(ident, "unique" + str(i))
            offsite.preflight(self.folder, ident)
            self.event("submitted", ident, receipt="Browser receipt observed")
        self.prepare("post-006", "sixth")
        with self.assertRaisesRegex(ValueError, "seven-day"):
            offsite.preflight(self.folder, "post-006")
        # A separate campaign may have a stricter per-site rate.
        other = self.root / "other"
        offsite.initialise(self.plan, other)
        self.folder = other
        self.prepare(weekly=1)
        self.event("submitted", receipt="Actual observed receipt")
        self.prepare("post-002", "second", weekly=1)
        with self.assertRaisesRegex(ValueError, "site's"):
            offsite.preflight(self.folder, "post-002")

    def test_warning_pauses_campaign_and_does_not_rotate_accounts(self):
        self.prepare()
        self.event("blocked", reason="Platform moderation warning", account_warning=True)
        self.assertTrue(offsite.read(self.folder / "campaign.json")["paused"])
        with self.assertRaises(ValueError):
            offsite.preflight(self.folder, "post-001")

    def test_submission_publication_and_exact_link_are_separate(self):
        self.prepare()
        self.event("submitted", receipt="Waiting for editorial review")
        with self.assertRaises(ValueError):
            offsite.verify(self.folder, "post-001", self.root / "unpublished")
        with self.assertRaisesRegex(ValueError, "host differs"):
            self.event("published", public_url="https://other.example/post")
        self.event("published", public_url="https://publisher.example/article")
        for links, state in [
            ([{"url": "https://example.com/another-page"}], "published"),
            ([{"url": "https://example.com/service", "rel": ["nofollow"]}], "verified"),
            ([], "published"),
        ]:
            evidence = {
                "verification": "link_observed" if links else "unverified_access",
                "target_links": links,
                "checked_at": utcnow(),
            }
            with patch("beyondseo.backlinks.verify_source", return_value=evidence):
                result = offsite.verify(
                    self.folder, "post-001", self.root / ("check-" + str(len(links)))
                )
            self.assertEqual(result["status"], state)
        # No indexing or authority claim accompanies the verified link.
        self.assertIn("not proof", result["limits"])

    def test_submitted_article_cannot_be_approved_again_and_duplicate_submission_is_blocked(self):
        self.prepare()
        self.event("submitted", receipt="Observed")
        with self.assertRaises(ValueError):
            self.event("submitted", receipt="Duplicate")
        data = offsite.read(self.folder / "campaign.json")
        with self.assertRaises(ValueError):
            self.event("approve", digest=offsite.digest(data["tasks"][0]["draft"]))

    def test_locks_and_existing_campaigns_are_preserved(self):
        original = (self.folder / "campaign.json").read_bytes()
        with self.assertRaises(ValueError):
            offsite.initialise(self.plan, self.folder)
        with offsite.locked(self.folder):
            with self.assertRaisesRegex(ValueError, "in use"):
                self.event("account_ready")
        self.assertEqual((self.folder / "campaign.json").read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
