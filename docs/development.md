# Develop BeyondSEO

The repository includes the native engine, source catalog, portable skill and local fixtures. Keep client reports, captured website content, credentials and run outputs outside the source tree.

## Prepare the environment

```sh
python3 scripts/setup.py --dev
```

Activate `.venv` with `source .venv/bin/activate` on macOS/Linux, or `.venv\Scripts\Activate.ps1` in Windows PowerShell. Windows users can replace `python3` with `py -3` for setup.

Install optional local hosting fixtures when working on SFTP/FTPS behavior:

```sh
python -m pip install -e '.[hosting-test]'
```

## Check a change

```sh
ruff check .
ruff format --check .
python scripts/check_docs.py
python -m unittest discover -s tests -v
beyondseo doctor
```

The suite uses local fixtures for HTTP/browser crawling, extraction, robots and sitemap behavior, reputation calculations, catalog import and selection, planning, installation and file changes. Optional hosting fixtures require their corresponding dependencies. A fixture verifies defined behavior; it does not establish another website's availability or a client's search performance.

The [repository workflow](https://github.com/beyondtahir/beyondseo/actions/workflows/tests.yml) runs across Linux, Windows and macOS with Python 3.10 and 3.12. Keep regressions reproducible and independent of external websites remaining unchanged.

## Update the posting library

Use [the posting guide](backlink-posting-guide.md) for the optional PDF importer and catalog structure. Preserve original source rows, unverified metric labels and dated primary-source guidance. Review exact posting routes, eligibility and content rules before qualifying an entry. Keep account-specific or client-specific observations outside the shared catalog.

See [Contributing](../CONTRIBUTING.md) for change descriptions and [Security](../SECURITY.md) for reporting vulnerabilities.
