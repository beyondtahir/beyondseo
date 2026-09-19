"""Private project ledger, read-only monitor and bounded recurring crawl runner.

The agent executes editing tasks. This module never executes arbitrary commands,
installs a scheduler, posts externally or equates an applied edit with verification.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .network import normalize_url, utcnow

STATES = {"planned", "running", "awaiting_review", "applied", "verified", "blocked", "cancelled"}
TRANSITIONS = {
    "planned": {"running", "blocked", "cancelled"},
    "running": {"awaiting_review", "applied", "verified", "blocked", "cancelled"},
    "awaiting_review": {"running", "applied", "blocked", "cancelled"},
    "applied": {"verified", "blocked"},
    "blocked": {"running", "cancelled"},
    "verified": set(),
    "cancelled": set(),
}


def read_json(path):
    path = Path(path)
    if path.stat().st_size > 2_000_000:
        raise ValueError("Project input exceeds 2 MB.")
    return json.loads(path.read_text(encoding="utf-8"))


def write_private(path, data):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Project output must not be a symlink.")
    temp = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
    try:
        fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def text(value, label, limit=3000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{label} needs nonempty text of at most {limit} characters.")
    return value.strip()


def safe_url(value):
    url = normalize_url(value)
    if not url:
        raise ValueError("Use an HTTP(S) URL without credentials.")
    # Tokens in URLs do not belong in a persistent activity ledger.
    if urlsplit(value).query or urlsplit(value).fragment:
        raise ValueError("Use a clean public page URL without query parameters or fragments.")
    return url


def init_project(folder, url, goal):
    folder = Path(folder).expanduser().absolute()
    package = Path(__file__).resolve().parents[2]
    if folder.resolve().is_relative_to(package):
        raise ValueError("Keep client projects outside the skill/source folder.")
    if folder.exists() or folder.is_symlink():
        raise ValueError(
            "Choose a new private project folder; existing projects are never replaced."
        )
    url, goal = safe_url(url), text(goal, "Goal")
    folder.mkdir(parents=True, mode=0o700)
    db = sqlite3.connect(folder / "project.sqlite3")
    try:
        db.executescript("""
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE jobs (id TEXT PRIMARY KEY, data TEXT NOT NULL);
        CREATE TABLE events (seq INTEGER PRIMARY KEY, at TEXT NOT NULL, job TEXT, message TEXT NOT NULL);
        CREATE TABLE runs (id TEXT PRIMARY KEY, status TEXT NOT NULL, started TEXT NOT NULL,
                           finished TEXT, data TEXT NOT NULL);
        """)
        for key, value in {
            "schema_version": 1,
            "url": url,
            "goal": goal,
            "created_at": utcnow(),
            "paused": False,
            "dashboard": False,
            "refresh_seconds": 30,
            "schedule": None,
            "last_worker_check": None,
            "profile": {},
        }.items():
            db.execute("INSERT INTO meta VALUES (?, ?)", (key, json.dumps(value)))
        db.execute(
            "INSERT INTO events(at, message) VALUES (?, ?)",
            (utcnow(), "Project created; no scheduler or website edits started."),
        )
        db.commit()
    finally:
        db.close()
    os.chmod(folder / "project.sqlite3", 0o600)
    return {
        "project": str(folder),
        "status": "created",
        "dashboard": "not requested",
        "scheduler": "not installed",
    }


@contextmanager
def connection(folder):
    folder = Path(folder).resolve()
    path = folder / "project.sqlite3"
    if path.is_symlink() or not path.is_file():
        raise ValueError("No regular project database found. Use project init first.")
    db = sqlite3.connect(path, timeout=10)
    try:
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def meta(db):
    return {key: json.loads(value) for key, value in db.execute("SELECT key,value FROM meta")}


def set_meta(db, key, value):
    db.execute("UPDATE meta SET value=? WHERE key=?", (json.dumps(value), key))


def event(db, job, message):
    db.execute("INSERT INTO events(at,job,message) VALUES (?,?,?)", (utcnow(), job, message))


def snapshot(folder):
    with connection(folder) as db:
        result = meta(db)
        result["jobs"] = [
            json.loads(row[0]) for row in db.execute("SELECT data FROM jobs ORDER BY rowid")
        ]
        result["events"] = [
            dict(zip(("at", "job", "message"), row))
            for row in db.execute("SELECT at,job,message FROM events ORDER BY seq DESC LIMIT 100")
        ]
        result["runs"] = [
            dict(zip(("id", "status", "started", "finished", "data"), row))
            for row in db.execute("SELECT * FROM runs ORDER BY started DESC LIMIT 50")
        ]
    result["worker_status"] = (
        "not configured"
        if not result["schedule"]
        else "external scheduler required; see last worker check"
    )
    return result


def save_profile(folder, profile):
    allowed = {
        "business",
        "services",
        "customers",
        "offices",
        "markets",
        "languages",
        "sources",
        "unknowns",
        "constraints",
        "access_route",
    }
    if not isinstance(profile, dict) or profile.keys() - allowed:
        raise ValueError(
            "Profile accepts business context only; never credentials or connection secrets."
        )
    if len(json.dumps(profile)) > 20000:
        raise ValueError("Keep the profile under 20 KB; retain detailed evidence separately.")
    with connection(folder) as db:
        set_meta(db, "profile", profile)
        event(db, None, "Business profile updated.")
    refresh(folder)
    return {"status": "saved"}


def add_jobs(folder, rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise ValueError("Supply 1–100 concrete jobs.")
    prepared = []
    for row in rows:
        if not isinstance(row, dict) or row.keys() - {
            "id",
            "title",
            "kind",
            "url",
            "action",
            "acceptance",
            "evidence",
            "priority",
            "estimate_minutes",
            "due_at",
            "destination",
            "requires_approval",
        }:
            raise ValueError(
                "Unexpected job field; credentials and execution commands are not accepted."
            )
        job = dict(row)
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", str(job.get("id", ""))):
            raise ValueError("Job id must be 1–64 lowercase letters, digits or hyphens.")
        for field in ("title", "action", "acceptance", "evidence"):
            job[field] = text(job.get(field), field)
        if job.get("kind") not in {"onsite", "new_page", "offsite_plan", "report", "review"}:
            raise ValueError("Choose onsite, new_page, offsite_plan, report or review.")
        job["url"] = safe_url(job["url"])
        if job.get("destination"):
            job["destination"] = safe_url(job["destination"])
        estimate = job.get("estimate_minutes")
        if estimate is not None and (
            not isinstance(estimate, list)
            or len(estimate) != 2
            or any(type(v) is not int for v in estimate)
            or not 1 <= estimate[0] <= estimate[1] <= 10080
        ):
            raise ValueError(
                "Estimate must be [minimum, maximum] implementation minutes, or omitted."
            )
        if job.get("due_at"):
            parsed = datetime.fromisoformat(job["due_at"].replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("due_at must include a timezone.")
        if "requires_approval" in job and type(job["requires_approval"]) is not bool:
            raise ValueError("requires_approval must be boolean.")
        job.update(
            status="planned", created_at=utcnow(), updated_at=utcnow(), note="", verification=None
        )
        prepared.append(job)
    with connection(folder) as db:
        project_host = urlsplit(meta(db)["url"]).netloc
        for job in prepared:
            if urlsplit(job["url"]).netloc != project_host:
                raise ValueError(
                    "The affected URL must belong to this project; use destination for an external posting route."
                )
            old = db.execute("SELECT data FROM jobs WHERE id=?", (job["id"],)).fetchone()
            if old:
                previous = json.loads(old[0])
                for key in ("created_at", "updated_at", "status", "note", "verification"):
                    previous.pop(key, None)
                incoming = {
                    key: value
                    for key, value in job.items()
                    if key not in {"created_at", "updated_at", "status", "note", "verification"}
                }
                if previous != incoming:
                    raise ValueError(
                        "An existing job id has different content; preserve it and use a new id."
                    )
                continue
            db.execute("INSERT INTO jobs VALUES (?,?)", (job["id"], json.dumps(job)))
            event(db, job["id"], "Planned: " + job["title"])
    refresh(folder)
    return {"status": "recorded", "jobs": len(prepared), "execution": "not started"}


def transition(folder, job_id, state, note, evidence=None, approval=None):
    note = text(note, "Activity note")
    with connection(folder) as db:
        settings = meta(db)
        row = db.execute("SELECT data FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise ValueError("Unknown job id.")
        job = json.loads(row[0])
        if state not in TRANSITIONS[job["status"]]:
            raise ValueError(f"Cannot move {job['status']} to {state}.")
        if settings["paused"] and state not in {"blocked", "cancelled"}:
            raise ValueError("Project is paused.")
        if (
            (job["kind"] == "new_page" or job.get("requires_approval"))
            and state in {"running", "applied"}
            and not (approval or job.get("approval"))
        ):
            raise ValueError("Record the existing user authorisation before this action.")
        if approval:
            job["approval"] = text(approval, "Authorisation reference")
        if state == "verified":
            if job["kind"] in {"onsite", "new_page"} and job["status"] != "applied":
                raise ValueError("Website changes must be applied before verification.")
            if not evidence:
                raise ValueError("Verification requires a saved acceptance-check JSON file.")
            checks = read_json(evidence)
            required = {"url", "captured_at", "checks", "coverage", "artifacts"}
            if (
                not isinstance(checks, dict)
                or not required <= checks.keys()
                or checks["url"] != job["url"]
            ):
                raise ValueError(
                    "Verification needs the affected URL, capture date, checks, coverage and artifacts."
                )
            captured = datetime.fromisoformat(checks["captured_at"].replace("Z", "+00:00"))
            if (
                captured.tzinfo is None
                or captured.timestamp() > time.time() + 300
                or captured < datetime.fromisoformat(job["updated_at"])
            ):
                raise ValueError("Verification must be dated after this job and not in the future.")
            items = checks["checks"]
            if (
                not isinstance(items, list)
                or not items
                or any(
                    not isinstance(c, dict)
                    or not c.get("name")
                    or c.get("result") != "pass"
                    or not c.get("observation")
                    for c in items
                )
            ):
                raise ValueError(
                    "Each required acceptance check needs a passing result and observation."
                )
            text(checks["coverage"], "Coverage limits")
            if not isinstance(checks["artifacts"], list) or not checks["artifacts"]:
                raise ValueError("Retain at least one local verification artifact.")
            hashes = []
            for value in checks["artifacts"]:
                artifact = Path(evidence).parent / value
                if (
                    artifact.is_symlink()
                    or not artifact.is_file()
                    or artifact.stat().st_size > 20_000_000
                ):
                    raise ValueError(
                        "Verification artifacts must be regular files of at most 20 MB."
                    )
                hashes.append(
                    {
                        "name": artifact.name,
                        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
                    }
                )
            job["verification"] = {
                "captured_at": checks["captured_at"],
                "checks": items,
                "coverage": checks["coverage"],
                "artifacts": hashes,
                "recorded_by": "agent; acceptance evidence is reviewable, not independently certified",
            }
        job.update(status=state, updated_at=utcnow(), note=note)
        db.execute("UPDATE jobs SET data=? WHERE id=?", (json.dumps(job), job_id))
        event(db, job_id, state + ": " + note)
    refresh(folder)
    return {"job": job_id, "status": state}


def configure(
    folder,
    pause=None,
    dashboard=False,
    consent=False,
    refresh_seconds=30,
    interval=None,
    max_pages=10,
):
    if not 10 <= refresh_seconds <= 3600:
        raise ValueError("Dashboard refresh must be 10–3600 seconds.")
    if dashboard and not consent:
        raise ValueError(
            "Ask once before creating the optional dashboard; record consent with --consent."
        )
    if interval is not None and (interval < 3600 or not 1 <= max_pages <= 100):
        raise ValueError(
            "Recurring review interval must be at least 3600 seconds; use 1–100 pages."
        )
    with connection(folder) as db:
        if pause is not None:
            set_meta(db, "paused", pause)
            event(db, None, "Project paused." if pause else "Project resumed.")
        if dashboard:
            set_meta(db, "dashboard", True)
            set_meta(db, "refresh_seconds", refresh_seconds)
            event(db, None, "Private monitoring dashboard enabled with user consent.")
        if interval is not None:
            set_meta(
                db,
                "schedule",
                {
                    "interval_seconds": interval,
                    "max_pages": max_pages,
                    "next_due": time.time(),
                    "scope": "read-only HTTP crawl; no model, edits, submissions or notifications",
                },
            )
            event(
                db,
                None,
                "Review cadence saved. An external scheduler must invoke project run; none was installed.",
            )
    refresh(folder)
    return snapshot(folder)


def run_due(folder, runner=None):
    """One bounded read-only crawl. Transactional claim prevents concurrent/repeated runs."""
    with connection(folder) as db:
        settings = meta(db)
        set_meta(db, "last_worker_check", utcnow())
        schedule = settings["schedule"]
        if settings["paused"] or not schedule or schedule["next_due"] > time.time():
            return {"status": "paused" if settings["paused"] else "not_due"}
        active = db.execute("SELECT id FROM runs WHERE status='running'").fetchone()
        if active:
            return {
                "status": "needs_inspection",
                "run": active[0],
                "reason": "A prior runner is active or was interrupted; inspect it before project recover.",
            }
        run_id = secrets.token_hex(8)
        db.execute("INSERT INTO runs VALUES (?,?,?,?,?)", (run_id, "running", utcnow(), None, "{}"))
        event(db, None, "Read-only review started: " + run_id)
    refresh(folder)
    out = Path(folder) / "runs" / run_id
    result = {}
    status = "failed"
    try:
        if runner:
            result = runner(settings["url"], out, schedule["max_pages"])
        else:
            from .engine import Crawler
            from .network import Config

            config = Config(
                url=settings["url"],
                max_pages=schedule["max_pages"],
                workers=2,
                timeout=15,
                retries=1,
                max_discovered=500,
                max_sitemaps=5,
                include_www=True,
                render_mode="http",
            )
            crawler = Crawler(config, out)
            try:
                crawler.log = lambda _: None
                result = crawler.run()
            finally:
                crawler.close()
        status = "completed" if result.get("html_documents") else "blocked"
        result = {key: result.get(key) for key in ("html_documents", "coverage_limited")}
        result["evidence_folder"] = "runs/" + run_id
    except Exception as exc:
        # Do not put arbitrary exception text (URLs/credentials) on the dashboard.
        result = {
            "failure_type": type(exc).__name__,
            "coverage": "No successful result recorded; inspect private worker output.",
        }
    finally:
        with connection(folder) as db:
            db.execute(
                "UPDATE runs SET status=?,finished=?,data=? WHERE id=?",
                (status, utcnow(), json.dumps(result), run_id),
            )
            current = meta(db)["schedule"]
            if current:
                current["next_due"] = time.time() + current["interval_seconds"]
                set_meta(db, "schedule", current)
            event(db, None, f"Review {run_id}: {status}. Website was not edited.")
        refresh(folder)
    return {"run": run_id, "status": status, **result}


def recover(folder, run_id, note):
    with connection(folder) as db:
        row = db.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()
        if not row or row[0] != "running":
            raise ValueError("Only an inspected interrupted running review can be recovered.")
        db.execute("UPDATE runs SET status='interrupted',finished=? WHERE id=?", (utcnow(), run_id))
        event(
            db,
            None,
            "Runner recovery after checking the old process stopped: "
            + text(note, "Recovery note"),
        )
    refresh(folder)
    return {"run": run_id, "status": "interrupted"}


def dashboard_html(state):
    def esc(value):
        return html.escape(str(value), quote=True)

    logo = base64.b64encode(
        (Path(__file__).parent / "report_assets/beyondseo-logo.png").read_bytes()
    ).decode()

    def verification_html(job):
        verification = job.get("verification")
        if not verification:
            return "<p>Not yet verified</p>"
        checks = "".join(
            f"<li><strong>{esc(check['name'])}</strong>: {esc(check['observation'])}</li>"
            for check in verification["checks"]
        )
        return f"<p>Checked {esc(verification['captured_at'])}</p><ul>{checks}</ul><p>Coverage: {esc(verification['coverage'])}</p>"

    def estimate(job):
        values = job.get("estimate_minutes")
        return f"{values[0]}–{values[1]} min" if values else "Not estimated"

    rows = "".join(
        f"<tr><td><strong>{esc(j['title'])}</strong><p><a href='{esc(j['url'])}' rel='noreferrer'>{esc(j['url'])}</a></p><small>{esc(j['kind'].replace('_', ' '))}</small></td><td><span class='status'>{esc(j['status'].replace('_', ' '))}</span><p>{esc(j['note'])}</p></td><td>{esc(j['action'])}<details><summary>Acceptance and evidence</summary><p>{esc(j['acceptance'])}</p><p>{esc(j['evidence'])}</p>{verification_html(j)}</details></td><td>{estimate(j)}<p>{esc(j.get('due_at') or 'Not scheduled')}</p></td></tr>"
        for j in state["jobs"]
    )
    events = "".join(
        f"<li><time>{esc(e['at'])}</time><p>{esc(e['message'])}</p></li>" for e in state["events"]
    )
    runs = "".join(
        f"<li><strong>{esc(r['status'])}</strong> · {esc(r['started'])}<p>{esc(r['data'])}</p></li>"
        for r in state["runs"]
    )
    verified = sum(j["status"] == "verified" for j in state["jobs"])
    blocked = sum(j["status"] == "blocked" for j in state["jobs"])
    due = state["schedule"]
    cadence = (
        (
            "Next eligible review: "
            + datetime.fromtimestamp(due["next_due"], timezone.utc).isoformat()
        )
        if due
        else "No recurring review configured"
    )
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><meta http-equiv="refresh" content="{state["refresh_seconds"]}"><title>BeyondSEO · Project monitor</title><style>
    :root{{--red:#991b1b;--ink:#151515;--muted:#666;--paper:#f5f3f1}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.6 system-ui,sans-serif}}main{{max-width:1220px;margin:auto;padding:36px}}header{{display:flex;justify-content:space-between;align-items:center;border-bottom:2px solid var(--ink)}}img{{width:230px;max-width:55vw}}.label{{text-transform:uppercase;letter-spacing:.15em;font-size:11px;color:var(--red)}}h1{{font-size:clamp(28px,4vw,48px);letter-spacing:-.04em;line-height:1.15}}h2{{font-size:23px}}p,h1{{overflow-wrap:anywhere}}a{{color:var(--red)}}.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:28px 0}}.stats article{{background:white;border-top:3px solid var(--red);padding:20px}}.stats b{{display:block;font-size:34px}}section{{background:white;padding:24px;margin:24px 0;border:1px solid #ddd}}table{{border-collapse:collapse;width:100%;min-width:720px}}th,td{{text-align:left;vertical-align:top;padding:16px 10px;border-bottom:1px solid #ddd}}th{{font-size:12px;text-transform:uppercase}}td p{{margin:6px 0;font-size:13px;color:var(--muted)}}.scroll{{overflow:auto}}.status{{font-size:12px;border:1px solid #ddd;border-radius:20px;padding:4px 9px;white-space:nowrap}}ul{{list-style:none;padding:0}}li{{padding:12px 0;border-bottom:1px solid #eee}}time,small{{color:var(--muted);font-size:12px}}summary{{cursor:pointer;color:var(--red)}}.notice{{border-left:4px solid var(--red);padding:12px 20px;background:white}}footer{{font-size:12px;color:var(--muted)}}@media(max-width:600px){{main{{padding:16px}}.stats{{gap:8px}}.stats article{{padding:12px}}}}
    </style></head><body><main><header><img src="data:image/png;base64,{logo}" alt="BeyondSEO"><span class="label">Private project monitor</span></header><p class="label">{"Paused" if state["paused"] else "Project activity"}</p><h1>{esc(state["url"])}</h1><p>{esc(state["goal"])}</p><div class="stats"><article><b>{len(state["jobs"])}</b>Total jobs</article><article><b>{verified}</b>Verified jobs</article><article><b>{blocked}</b>Blocked jobs</article></div><div class="notice">Operate through your existing agent chat. This monitor does not run an AI or a scheduler.<br>{esc(cadence)}<br>Last worker check: {esc(state["last_worker_check"] or "Never")} · {esc(state["worker_status"])}</div><section><h2>Your work plan</h2><div class="scroll"><table><thead><tr><th>Job / page</th><th>Status</th><th>Work and checks</th><th>Estimate (minutes) / due</th></tr></thead><tbody>{rows or '<tr><td colspan="4">No jobs recorded yet.</td></tr>'}</tbody></table></div></section><section><h2>Review runs</h2><ul>{runs or "<li>No reviews executed.</li>"}</ul></section><section><h2>Activity</h2><ul>{events}</ul></section><footer>Updated {esc(utcnow())}. Implementation estimates are not ranking forecasts. Verification reflects the recorded evidence and its limits. Keep this monitor private.</footer></main></body></html>'''


def refresh(folder):
    state = snapshot(folder)
    if state["dashboard"]:
        write_private(Path(folder) / "dashboard.html", dashboard_html(state))


def make_server(folder, port=0):
    state = snapshot(folder)
    if not state["dashboard"]:
        raise ValueError("Enable the dashboard with consent first.")
    token = secrets.token_urlsafe(24)
    route = "/" + token

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if (
                self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}"
                or self.path != route
            ):
                self.send_error(404)
                return
            body = dashboard_html(snapshot(folder)).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass  # Do not log private capability URLs.

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    return server, f"http://127.0.0.1:{server.server_port}{route}"


def register(sub):
    p = sub.add_parser("project", help="Private job ledger and optional read-only monitor.")
    actions = p.add_subparsers(dest="project_action", required=True)
    for name in (
        "init",
        "profile",
        "plan",
        "status",
        "update",
        "dashboard",
        "pause",
        "resume",
        "schedule",
        "run",
        "recover",
    ):
        cmd = actions.add_parser(name)
        cmd.add_argument("--project", type=Path, required=True)
        if name == "init":
            cmd.add_argument("--url", required=True)
            cmd.add_argument("--goal", required=True)
        if name in {"profile", "plan"}:
            cmd.add_argument("--input", type=Path, required=True)
        if name == "update":
            cmd.add_argument("--job", required=True)
            cmd.add_argument("--state", choices=sorted(STATES), required=True)
            cmd.add_argument("--note", required=True)
            cmd.add_argument("--evidence", type=Path)
            cmd.add_argument(
                "--approval",
                help="Reference to existing user authorisation, not an automatic grant.",
            )
        if name == "dashboard":
            cmd.add_argument("--consent", action="store_true")
            cmd.add_argument("--refresh-seconds", type=int, default=30)
            cmd.add_argument(
                "--serve",
                action="store_true",
                help="Run a read-only localhost server until stopped.",
            )
            cmd.add_argument("--port", type=int, default=0)
        if name == "schedule":
            cmd.add_argument("--interval", type=int, required=True)
            cmd.add_argument("--max-pages", type=int, default=10)
        if name == "recover":
            cmd.add_argument("--run", required=True)
            cmd.add_argument("--note", required=True)


def execute(args):
    folder, action = args.project, args.project_action
    if action == "init":
        return init_project(folder, args.url, args.goal)
    if action == "profile":
        return save_profile(folder, read_json(args.input))
    if action == "plan":
        return add_jobs(folder, read_json(args.input))
    if action == "update":
        return transition(folder, args.job, args.state, args.note, args.evidence, args.approval)
    if action in {"pause", "resume"}:
        return configure(folder, pause=action == "pause")
    if action == "schedule":
        return configure(folder, interval=args.interval, max_pages=args.max_pages)
    if action == "run":
        return run_due(folder)
    if action == "recover":
        return recover(folder, args.run, args.note)
    if action == "dashboard":
        configure(
            folder, dashboard=True, consent=args.consent, refresh_seconds=args.refresh_seconds
        )
        if args.serve:
            server, url = make_server(folder, args.port)
            print(
                json.dumps(
                    {
                        "dashboard_url": url,
                        "access": "this computer only",
                        "scheduler": "not installed",
                    }
                ),
                flush=True,
            )
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
        return {"dashboard_file": str(folder.resolve() / "dashboard.html"), "private": True}
    return snapshot(folder)
