# Contributing to BeyondSEO

Good contributions make a real page easier to crawl, explain a failure more clearly, or make the project easier to use.

Create a local environment and install development tools:

```sh
python scripts/setup.py --dev
source .venv/bin/activate
ruff check .
ruff format --check .
python -m unittest discover -s tests -v
```

On Windows, activate with `.venv\Scripts\Activate.ps1`.

Keep fixes focused. Explain the input that failed, the expected result and the behavior after the change. Add a small local fixture for crawler behavior; the test suite should not depend on an external website remaining unchanged. Do not commit crawl databases, downloaded website content, credentials, environment files or personal paths.

Preserve the distinction between raw responses and rendered pages. Record restrictions and errors rather than silently presenting partial content as complete. When changing an output field or crawl setting, update the CLI reference and the corresponding tests.

Before a pull request, run formatting, checks and the relevant tests. The [repository workflow](https://github.com/beyondtahir/beyondseo/actions/workflows/tests.yml) runs the suite on Linux, Windows and macOS. Run relevant local checks before submitting a change. Contributions are provided under the project's MIT license.

## Release hygiene

Keep all live-client research and host-validation output outside the repository. Automated tests use fictional fixtures. Public testing notes describe the checks, result and limitations only: no client names/domains, crawl findings, scores, screenshots, recordings, browser/search transcripts, contact details, machine paths or raw diagnostic output. The project's approved creator credits and official source-library links are separate from private test subjects. Apply this rule to commits, pull requests, issues, CI logs, screenshots and release attachments as well as the current files.

Use invented names and reserved example domains in reproduction fixtures. Redacting a name from an actual client report does not make the remaining report public material. Before staging or publishing, run:

```sh
python scripts/check_release.py
# Add private client/domain identifiers for this local check only:
python scripts/check_release.py --deny-text "private-client-name"
git diff --check
git diff --cached
```

The check scans tracked and nonignored untracked files without staging or publishing anything. It flags known capture/runtime paths, environment/key files, machine-specific home paths and supplied private text; it reports filenames rather than echoing matching private content. It is a heuristic, not a comprehensive secret scanner. Review the exact staged files, outgoing commits and release assets as well. Do not put actual client identifiers in public test fixtures or CI arguments. Do not push or publish without the repository owner's authorization.

Also check retained history with `python scripts/check_release.py --history --deny-text "private-client-name"`. This is read-only and covers locally available refs. A clean current tree does not erase older commits, tags, release assets or external caches. Report historical findings separately; rewriting published history and replacing old assets needs the owner's explicit approval and a reviewed recovery plan.
