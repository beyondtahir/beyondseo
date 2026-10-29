"""Private publishing preparation and receipts. The permitted host browser submits posts."""

from __future__ import annotations

import hashlib
import json
import os
import re
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .network import normalize_url, utcnow
from .projects import write_private

STATES = {
    "planned",
    "awaiting_signup",
    "account_ready",
    "draft_ready",
    "approved",
    "submitted",
    "published",
    "verified",
    "blocked",
    "cancelled",
}


def read(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > 2_000_000:
        raise ValueError("Use a regular publishing JSON file smaller than 2 MB.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Publishing input must be a JSON object.")
    return data


def url(value):
    result = normalize_url(value)
    if not result or urlsplit(result).query or urlsplit(result).fragment:
        raise ValueError("Use a clean HTTP(S) URL without login data, query or fragment.")
    return result


def wording(value, label, maximum=5000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{label} needs nonempty text, at most {maximum} characters.")
    return value.strip()


def private_folder(folder):
    folder = Path(folder).expanduser().absolute()
    if folder.is_symlink() or folder.resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError("Keep campaigns in a regular private folder outside the skill/source.")
    return folder


def save(folder, data):
    write_private(folder / "campaign.json", json.dumps(data, ensure_ascii=False, indent=2) + "\n")


@contextmanager
def locked(folder):
    folder = private_folder(folder)
    lock = folder / "publishing.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError(
            "Campaign is in use. Check the recorded process before removing a stale publishing.lock."
        ) from None
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(str(os.getpid()))
        yield folder, read(folder / "campaign.json")
    finally:
        lock.unlink(missing_ok=True)


def initialise(plan, out, weekly_target=5, start=None):
    plan = read(plan)
    folder = private_folder(out)
    if folder.exists():
        raise ValueError("Choose a new private campaign folder.")
    if type(weekly_target) is not int or not 1 <= weekly_target <= 7:
        raise ValueError(
            "Choose a proposed target of 1–7 articles/week; default five, subject to approval and site rules."
        )
    start = date.fromisoformat(start) if start else datetime.now(timezone.utc).date()
    tasks = plan.get("tasks")
    if not isinstance(tasks, list) or not tasks or len(tasks) > 100:
        raise ValueError("Use a posting plan with 1–100 reviewed candidate tasks.")
    entries, excluded = [], []
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise ValueError("Posting-plan tasks must be objects.")
        if task.get("format") not in {
            "article",
            "editorial_article",
            "article_directory",
            "newsletter",
        }:
            excluded.append(
                {
                    "site_id": task.get("site_id"),
                    "format": task.get("format"),
                    "reason": "Not an established full-article format; keep answers, communities and curation in their own plan.",
                }
            )
            continue
        entries.append(
            {
                "id": f"post-{index + 1:03d}",
                "site_id": wording(task.get("site_id"), "site_id", 200),
                "posting_url": url(task.get("posting_url")),
                "target_page": url(task.get("target_page")),
                "format": task.get("format", "article"),
                "brief": task,
                "proposed_date": (
                    start + timedelta(days=len(entries) * 7 // weekly_target)
                ).isoformat(),
                "status": "planned",
                "rules": None,
                "account_ready": False,
                "draft": None,
                "approved_digest": None,
                "public_url": None,
                "verification": None,
            }
        )
    if not entries:
        raise ValueError(
            "No full-article destinations in this plan. Research suitable article publishers instead of posting articles into answers or community threads."
        )
    result = {
        "schema_version": 1,
        "created_at": utcnow(),
        "website": url(plan.get("website")),
        "weekly_target": weekly_target,
        "schedule_status": "proposed; user approval and real host scheduler required",
        "scheduler": None,
        "authorization": None,
        "paused": False,
        "tasks": entries,
        "excluded_non_article_tasks": excluded,
        "events": [],
        "limits": [
            "The 206-entry catalog is a prospect library, not a list of universally writable article sites.",
            "Five/week is a proposed campaign target across approved sites, not a promise against bans or a quota overriding platform rules.",
            "The assistant writes distinct complete articles with truthful authorship and sources; this CLI never generates model prose or submits to external accounts.",
            "Submission, moderation acceptance, public publication, verified links, indexing and authority are separate outcomes.",
        ],
    }
    folder.mkdir(parents=True, mode=0o700)
    save(folder, result)
    return result


def item(data, ident):
    task = next((t for t in data["tasks"] if t["id"] == ident), None)
    if task is None:
        raise ValueError("Unknown campaign post ID.")
    return task


def digest(draft):
    return hashlib.sha256(
        json.dumps(draft, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def shingles(body):
    words = re.findall(r"\w+", body.casefold())
    return {tuple(words[i : i + 5]) for i in range(max(0, len(words) - 4))}


def set_draft(folder, ident, source):
    draft = read(source)
    allowed = {
        "title",
        "body",
        "reader",
        "author_voice",
        "unique_angle",
        "opening_answer",
        "source_urls",
        "resource_box",
    }
    if draft.keys() - allowed:
        raise ValueError(
            "Draft includes unsupported fields; never store credentials or browser-session data."
        )
    for key in ("title", "reader", "author_voice", "unique_angle", "opening_answer"):
        draft[key] = wording(draft.get(key), key, 500)
    draft["body"] = wording(draft.get("body"), "Complete article body", 100000)
    if len(re.findall(r"\w+", draft["body"])) < 150:
        raise ValueError(
            "Supply a complete article of at least 150 words; short answers use the planning workflow."
        )
    sources = draft.get("source_urls")
    if not isinstance(sources, list) or not sources or len(sources) > 30:
        raise ValueError(
            "Draft needs 1–30 supporting public source URLs; the agent must actually check the claims."
        )
    draft["source_urls"] = [url(s) for s in sources]
    if "resource_box" in draft and not isinstance(draft["resource_box"], str):
        raise ValueError("resource_box must be text.")
    with locked(folder) as (folder, data):
        task = item(data, ident)
        if task["status"] in {"submitted", "published", "verified", "cancelled"}:
            raise ValueError(
                "Do not replace a submitted or closed article; create a separately reviewed revision."
            )
        current = shingles(draft["body"])
        for other in data["tasks"]:
            old = other.get("draft")
            if other["id"] == ident or not old:
                continue
            previous = shingles(old["body"])
            overlap = len(current & previous) / max(1, min(len(current), len(previous)))
            if (
                draft["title"].casefold() == old["title"].casefold()
                or draft["unique_angle"].casefold() == old["unique_angle"].casefold()
                or overlap >= 0.65
            ):
                raise ValueError(
                    "This draft repeats another campaign article's title, angle or substantial wording. Write a distinct useful article."
                )
        task.update(draft=draft, approved_digest=None, status="draft_ready")
        data["events"].append(
            {"at": utcnow(), "id": ident, "event": "draft_saved", "digest": digest(draft)}
        )
        save(folder, data)
        return {
            "status": "draft_ready",
            "id": ident,
            "digest": digest(draft),
            "quality_review": "Required: verify facts, SEO/AEO usefulness, truthful author voice, distinct angle, platform rules and permitted links. Similarity screening does not prove originality.",
        }


def fresh_rules(task):
    rules = task.get("rules")
    if not rules:
        raise ValueError("Inspect and record current site rules first.")
    observed = datetime.fromisoformat(rules["checked_at"].replace("Z", "+00:00"))
    if (
        observed.tzinfo is None
        or not 0 <= (datetime.now(timezone.utc) - observed).total_seconds() <= 7 * 86400
    ):
        raise ValueError(
            "Refresh the site's rules; the recorded check must be within the last seven days."
        )
    if (
        rules["ai_policy"] not in {"allowed", "disclosure_required"}
        or not rules["submission_permitted"]
    ):
        raise ValueError(
            "Assistant-written submissions are not established as permitted on this site."
        )
    return rules


def check_submission(data, task):
    if (
        data["paused"]
        or task["status"] != "approved"
        or not data["authorization"]
        or task.get("approved_authorization_revision") != data["authorization"].get("revision", 0)
        or task["approved_digest"] != digest(task["draft"])
    ):
        raise ValueError(
            "Submit only the exact approved draft within an active authorised campaign."
        )
    rules = fresh_rules(task)
    if rules["ai_policy"] == "disclosure_required" and not task.get("disclosure_confirmed"):
        raise ValueError("Confirm the site's required AI disclosure before submission.")
    now = datetime.now(timezone.utc)
    recent = [
        e
        for e in data["events"]
        if e["event"] == "submitted"
        and (now - datetime.fromisoformat(e["at"])).total_seconds() < 7 * 86400
    ]
    if len(recent) >= data["weekly_target"]:
        raise ValueError("The approved rolling seven-day campaign target has been reached.")
    site_host = urlsplit(task["posting_url"]).hostname.removeprefix("www.")
    known_limits = [
        r["rules"]["weekly_site_limit"]
        for r in data["tasks"]
        if urlsplit(r["posting_url"]).hostname.removeprefix("www.") == site_host
        and r.get("rules")
        and r["rules"].get("weekly_site_limit")
    ]
    saved_limit = data.get("site_rate_limits", {}).get(site_host)
    if saved_limit:
        known_limits.append(saved_limit)
    limit = min(known_limits) if known_limits else None
    if (
        limit
        and sum(
            urlsplit(item(data, e["id"])["posting_url"]).hostname.removeprefix("www.") == site_host
            for e in recent
        )
        >= limit
    ):
        raise ValueError("The site's recorded posting limit has been reached.")


def preflight(folder, ident):
    with locked(folder) as (_, data):
        task = item(data, ident)
        check_submission(data, task)
        return {
            "status": "ready_for_host_submission",
            "id": ident,
            "digest": task["approved_digest"],
            "posting_url": task["posting_url"],
            "note": "This validates recorded campaign state only. Inspect the live composer and exact article before the actual host-browser submission. No post was submitted by this command.",
        }


def record(folder, ident, source):
    evidence = read(source)
    event = evidence.get("event")
    with locked(folder) as (folder, data):
        task = item(data, ident)
        if event == "authorize":
            scope = evidence.get("scope")
            if scope not in {"review_each_article", "standing_campaign"}:
                raise ValueError(
                    "Choose review_each_article or explicitly granted standing_campaign scope."
                )
            instruction = wording(
                evidence.get("user_instruction"), "User's actual publishing instruction"
            )
            previous = data.get("authorization") or {}
            changed = (
                previous.get("scope") != scope or previous.get("user_instruction") != instruction
            )
            revision = previous.get("revision", 0) + (1 if changed else 0)
            data["authorization"] = {
                "scope": scope,
                "user_instruction": instruction,
                "revision": revision,
                "at": utcnow(),
            }
            if changed:
                for pending in data["tasks"]:
                    if pending["status"] == "approved":
                        pending.update(
                            status="draft_ready",
                            approved_digest=None,
                            approved_authorization_revision=None,
                        )
        elif event == "rules":
            policy = evidence.get("ai_policy")
            if (
                policy not in {"allowed", "disclosure_required", "prohibited", "unknown"}
                or type(evidence.get("submission_permitted")) is not bool
            ):
                raise ValueError(
                    "Record the observed AI policy and whether this submission method is permitted."
                )
            timestamp = wording(evidence.get("checked_at"), "Rules capture date", 60)
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            rules = {
                "source_url": url(evidence.get("source_url")),
                "checked_at": timestamp,
                "ai_policy": policy,
                "submission_permitted": evidence["submission_permitted"],
                "notes": wording(evidence.get("notes"), "Rules and link/affiliation requirements"),
                "weekly_site_limit": evidence.get("weekly_site_limit"),
            }
            if rules["weekly_site_limit"] is not None and (
                type(rules["weekly_site_limit"]) is not int or rules["weekly_site_limit"] < 1
            ):
                raise ValueError(
                    "Observed weekly site limit must be a positive integer or null when unknown."
                )
            task["rules"] = rules
            if rules.get("weekly_site_limit"):
                site_host = urlsplit(task["posting_url"]).hostname.removeprefix("www.")
                limits = data.setdefault("site_rate_limits", {})
                limits[site_host] = min(
                    limits.get(site_host, rules["weekly_site_limit"]), rules["weekly_site_limit"]
                )
            task["approved_digest"] = None
            if task["status"] == "approved":
                task["status"] = "draft_ready"
        elif event in {"awaiting_signup", "account_ready"}:
            if task["status"] in {"submitted", "published", "verified", "cancelled"}:
                raise ValueError("Do not reset a submitted or closed article.")
            task["account_ready"] = event == "account_ready"
            task["status"] = "draft_ready" if task["draft"] else event
        elif event == "approve":
            if (
                task["status"] not in {"draft_ready", "approved"}
                or data["paused"]
                or not data["authorization"]
                or not task["draft"]
                or not task["account_ready"]
            ):
                raise ValueError(
                    "Approval needs an active authorised campaign, an account and a complete draft."
                )
            rules = fresh_rules(task)
            if (
                rules["ai_policy"] == "disclosure_required"
                and evidence.get("disclosure_confirmed") is not True
            ):
                raise ValueError(
                    "Confirm the site's required AI disclosure as part of draft approval."
                )
            if evidence.get("digest") != digest(task["draft"]):
                raise ValueError("Review the exact current draft digest before approval.")
            if data["authorization"]["scope"] == "review_each_article":
                wording(evidence.get("user_approval"), "User approval for this exact article")
            task.update(
                approved_digest=digest(task["draft"]),
                approved_authorization_revision=data["authorization"].get("revision", 0),
                status="approved",
                disclosure_confirmed=evidence.get("disclosure_confirmed") is True,
            )
        elif event == "submitted":
            check_submission(data, task)
            receipt = wording(evidence.get("receipt"), "Observed submission receipt")
            task.update(status="submitted", submission_receipt=receipt)
        elif event == "published":
            if task["status"] != "submitted":
                raise ValueError("Record the actual submission before publication.")
            public = url(evidence.get("public_url"))
            if urlsplit(public).hostname != urlsplit(task["posting_url"]).hostname:
                raise ValueError(
                    "Publication host differs from the approved posting route; review the destination before recording it."
                )
            task.update(status="published", public_url=public)
        elif event in {"blocked", "pause", "cancelled"}:
            reason = wording(evidence.get("reason"), "Observed reason")
            if event == "pause":
                data["paused"] = True
            else:
                task["status"] = event
            # A moderation/account warning stops this campaign instead of changing identities.
            if evidence.get("account_warning") is True:
                data["paused"] = True
            task["last_issue"] = reason
        elif event == "scheduler":
            if not data["authorization"]:
                raise ValueError(
                    "Approve the campaign schedule before registering a real host scheduler."
                )
            data["scheduler"] = {
                "host": wording(evidence.get("host"), "Scheduler host", 100),
                "job_id": wording(evidence.get("job_id"), "Actual scheduler ID", 300),
                "cadence": wording(evidence.get("cadence"), "Actual cadence and timezone", 300),
                "recorded_at": utcnow(),
            }
            data["schedule_status"] = (
                "host scheduler recorded; consult host for actual runtime state"
            )
        else:
            raise ValueError(
                "Unknown publishing event; verified status is available only through publish verify."
            )
        data["events"].append({"at": utcnow(), "id": ident, "event": event})
        save(folder, data)
        return {
            "status": task["status"],
            "id": ident,
            "event": event,
            "paused": data["paused"],
            "note": "Host/user observations recorded; this CLI did not click submit or verify a browser action.",
        }


def verify(folder, ident, out, mode="auto", allow_private=False):
    from .backlinks import verify_source

    with locked(folder) as (folder, data):
        task = item(data, ident)
        if task["status"] not in {"published", "verified"} or not task["public_url"]:
            raise ValueError("Only an observed public publication can be link-verified.")
        public, target = task["public_url"], task["target_page"]
    out = private_folder(out)
    if out.exists():
        raise ValueError("Choose a fresh private verification folder.")
    evidence = verify_source(
        public,
        urlsplit(target).hostname.removeprefix("www."),
        out,
        mode=mode,
        allow_private=allow_private,
    )
    exact = [
        link
        for link in evidence.get("target_links", [])
        if normalize_url(link.get("url", "")) == target
    ]
    with locked(folder) as (folder, data):
        task = item(data, ident)
        if task["public_url"] != public or task["target_page"] != target:
            raise ValueError("Campaign destination changed during verification; inspect it again.")
        task["verification"] = evidence
        if evidence.get("verification") == "link_observed" and exact:
            task["status"] = "verified"
        elif task["status"] == "verified":
            task["status"] = "published"
        data["events"].append(
            {
                "at": utcnow(),
                "id": ident,
                "event": "link_check",
                "exact_target_observed": bool(exact),
            }
        )
        save(folder, data)
        return {
            "status": task["status"],
            "id": ident,
            "exact_target_observed": bool(exact),
            "capture": evidence,
            "limits": "A captured link is not proof of indexing, authority transfer, endorsement or ranking improvement.",
        }


def register(sub):
    group = sub.add_parser(
        "publish", help="Prepare original articles and track authorised host-browser publishing."
    )
    actions = group.add_subparsers(dest="publish_action", required=True)
    p = actions.add_parser("init")
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--weekly-target", type=int, default=5)
    p.add_argument("--start")
    for name in ("status", "draft", "record", "preflight", "verify"):
        p = actions.add_parser(name)
        p.add_argument("--campaign", type=Path, required=True)
        if name != "status":
            p.add_argument("--id", required=True)
        if name in {"draft", "record"}:
            p.add_argument("--input", type=Path, required=True)
        if name == "verify":
            p.add_argument("--out", type=Path, required=True)
            p.add_argument("--mode", choices=["http", "auto", "browser"], default="auto")
            p.add_argument(
                "--allow-private",
                action="store_true",
                help="Explicit local/staging verification only; retain robots and capture checks.",
            )


def execute(args):
    if args.publish_action == "init":
        return initialise(args.plan, args.out, args.weekly_target, args.start)
    if args.publish_action == "status":
        return read(private_folder(args.campaign) / "campaign.json")
    if args.publish_action == "draft":
        return set_draft(args.campaign, args.id, args.input)
    if args.publish_action == "record":
        return record(args.campaign, args.id, args.input)
    if args.publish_action == "preflight":
        return preflight(args.campaign, args.id)
    return verify(args.campaign, args.id, args.out, args.mode, args.allow_private)
