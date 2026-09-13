"""Bounded, restartable reviews with a fresh evidence folder for every cycle."""

from __future__ import annotations

import time
from pathlib import Path

from .engine import Crawler, write_json
from .network import utcnow
from .review import compare


def watch(config, out, cycles=3, interval=3600, quiet=False, sleep=time.sleep, selectors=None):
    if not 1 <= cycles <= 10000 or interval < 60:
        raise ValueError("Use 1–10000 cycles and at least 60 seconds between completed runs.")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / "watch.json"
    if state_path.exists() or any(out.glob("run-*")):
        raise ValueError(
            "Choose a new watch output folder; previous evidence will not be overwritten."
        )
    state = {
        "started_at": utcnow(),
        "seed": config.url,
        "requested_cycles": cycles,
        "interval_seconds": interval,
        "runs": [],
        "status": "running",
    }
    write_json(state_path, state)
    previous = None
    failures = 0
    try:
        for n in range(1, cycles + 1):
            run = out / f"run-{n:04d}"
            crawler = Crawler(config, run, selectors=selectors)
            try:
                if quiet:
                    crawler.log = lambda _: None
                summary = crawler.run()
            finally:
                crawler.close()
            row = {
                "cycle": n,
                "folder": run.name,
                "finished_at": utcnow(),
                "html_documents": summary["html_documents"],
                "coverage_limited": summary["coverage_limited"],
            }
            if previous:
                diff = compare(previous, run, run)
                row["changed_pages"] = len(diff["changed_pages"])
                row["new_findings"] = len(diff["new_findings"])
            state["runs"].append(row)
            failures = failures + 1 if not summary["html_documents"] else 0
            write_json(state_path, state)
            if failures >= 2:
                state["status"] = "stopped_after_two_empty_runs"
                break
            previous = run
            if n < cycles:
                sleep(interval)
        else:
            state["status"] = "completed"
    except KeyboardInterrupt:
        state["status"] = "interrupted"
    except Exception:
        state["status"] = "failed"
        raise
    finally:
        state["finished_at"] = utcnow()
        write_json(state_path, state)
    return state
