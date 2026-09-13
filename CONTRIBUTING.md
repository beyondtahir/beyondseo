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
