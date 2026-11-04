# BeyondSEO roadmap

This roadmap shows where the project is heading so contributors and users can see what comes next. It is a direction, not a promise of dates; the [changelog](CHANGELOG.md) records what actually shipped.

## Now — reliability and trust

- Keep installation boring: close every install-blocking report with a verified fix or a clear explanation.
- Release automation: every tag builds the skill ZIP, its SHA-256 checksum and the Python distribution in CI.
- Publish the engine to PyPI so `pip install beyondseo` works alongside the skill bundles.
- Dependency updates through Dependabot, static analysis through CodeQL and visible test coverage.

## Next — community

- `good first issue` labels and small starter tasks for new contributors.
- GitHub Discussions for host-compatibility questions that are not bugs.
- A documented extension contract so the community can contribute new audit checks without waiting on the maintainer.
- Presence in the major skill and agent directories, with the repository as the single source of truth.

## Later — reach and proof

- An MCP server mode so any MCP-capable assistant can call the crawler and findings engine natively.
- A public, reproducible benchmark suite that measures finding accuracy against known sites.
- Signed release provenance (SLSA/Sigstore) for skill bundles.
- A versioned documentation site built from `docs/`.
- A `--self-test` command with bundled fixture sites so anyone can verify their installation against known-good output.

## What stays constant

- Free and MIT-licensed, with no required paid SEO API, scraping subscription or model key for the native engine.
- Evidence before claims: inspected pages, dated captures and honest coverage limits over impressive-sounding numbers.
- Client data and private captures never enter the repository.

Suggestions welcome: [open a feature request](https://github.com/beyondtahir/beyondseo/issues/new?template=feature.yml) or start a discussion.
