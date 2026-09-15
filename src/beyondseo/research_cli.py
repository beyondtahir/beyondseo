"""Command wiring for discovery and evidence-based research."""

from pathlib import Path


def add_commands(sub):
    p = sub.add_parser("discover", help="Collect unverified search leads with bounded fallbacks.")
    p.add_argument("--query", action="append", default=[])
    p.add_argument(
        "--queries", type=Path, help="JSON query specifications from profile or a reviewed plan."
    )
    p.add_argument("--market")
    p.add_argument("--language")
    p.add_argument("--target", default="")
    p.add_argument("--provider", action="append", choices=["duckduckgo-html", "bing-rss"])
    p.add_argument("--host-results", type=Path)
    p.add_argument(
        "--saved-search",
        type=Path,
        help="JSON list of saved HTML path/provider/query/captured_at records.",
    )
    p.add_argument("--candidate", action="append", default=[])
    p.add_argument("--sources-csv", type=Path)
    p.add_argument("--offline", action="store_true")
    p.add_argument("--max-requests", type=int, default=16)
    p.add_argument("--max-queries", type=int, default=8)
    p.add_argument("--max-candidates", type=int, default=100)
    p.add_argument("--timeout", type=float, default=12)
    p.add_argument("--seconds", type=float, default=90)
    p.add_argument("--cache", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("profile", help="Prepare evidence or validate a reviewed business profile.")
    p.add_argument("--crawl", type=Path, required=True)
    p.add_argument("--brief", type=Path)
    p.add_argument("--review", type=Path)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("competitors", help="Select comparable businesses from verified profiles.")
    p.add_argument("--profile", type=Path, required=True)
    p.add_argument("--candidate-profile", type=Path, action="append", required=True)
    p.add_argument("--discovery", type=Path)
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser(
        "audit", help="Create actionable findings from a crawl; search failure is nonfatal."
    )
    p.add_argument("--crawl", type=Path, required=True)
    p.add_argument("--profile", type=Path)
    p.add_argument("--discovery", type=Path)
    p.add_argument("--discover-queries", type=Path)
    p.add_argument("--offline", action="store_true")
    p.add_argument("--reviewed-findings", type=Path)
    p.add_argument("--out", type=Path, required=True)


def execute(args):
    from .backlinks import source_rows
    from .discovery import PROVIDERS, discover, host_attempts
    from .findings import audit_report
    from .research import profile, select_competitors
    from .review import read_json

    if args.command == "discover":
        queries = read_json(args.queries) if args.queries else []
        queries += [
            {"query": q, "market": args.market, "language": args.language} for q in args.query
        ]
        candidates = args.candidate + (source_rows(args.sources_csv) if args.sources_csv else [])
        return discover(
            queries,
            args.out,
            args.target,
            args.provider or PROVIDERS,
            host_attempts(args.host_results) if args.host_results else [],
            candidates,
            read_json(args.saved_search) if args.saved_search else [],
            args.offline,
            args.max_requests,
            args.max_queries,
            args.max_candidates,
            args.timeout,
            args.seconds,
            args.cache,
        )
    if args.command == "profile":
        return profile(
            args.crawl,
            args.out,
            read_json(args.brief) if args.brief else None,
            read_json(args.review) if args.review else None,
        )
    if args.command == "competitors":
        return select_competitors(
            read_json(args.profile),
            [read_json(p) for p in args.candidate_profile],
            args.out,
            args.limit,
            read_json(args.discovery) if args.discovery else None,
        )
    found = read_json(args.discovery) if args.discovery else None
    if args.discover_queries:
        found = discover(
            read_json(args.discover_queries), args.out / "discovery", offline=args.offline
        )
    return audit_report(
        args.crawl,
        args.out,
        read_json(args.profile) if args.profile else None,
        found,
        read_json(args.reviewed_findings) if args.reviewed_findings else [],
    )
