# Set up BeyondSEO

This guide takes you from a source checkout to your first saved crawl. You need Python 3.10 or newer and an internet connection for installation. Python 3.12 is the recommended starting point. Browser mode downloads a local copy of Chromium; no account is needed.

For installation in Claude, Cowork, Claude Code, Codex, ChatGPT Work, Hermes or OpenClaw, see [use with your assistant](agent-installation.md). The same native engine supports each documented local workflow; the host still needs file, shell and network capabilities.

## 1. Open the project

Get the source, then open a terminal in the folder containing `pyproject.toml`, `README.md` and `scripts/`:

```sh
git clone https://github.com/beyondtahir/beyondseo.git
cd beyondseo
```

Confirm your Python version:

```sh
python3 --version
```

On Windows, use `py -3 --version`. If the command is missing or reports a version older than 3.10, install a current Python version from [python.org](https://www.python.org/downloads/).

## 2. Run setup

macOS or Linux:

```sh
python3 scripts/setup.py
python3 scripts/run.py doctor
```

Windows PowerShell:

```powershell
py -3 scripts/setup.py
py -3 scripts/run.py doctor
```

Setup creates `.venv`, installs the local project, PDF renderer and browser library, downloads Chromium, and checks that it can launch. It does not change your system Python or send a crawl to a hosted service.

The launcher works without activation or changes to PowerShell execution policy:

```powershell
py -3 scripts/run.py doctor
py -3 scripts/run.py crawl https://example.com --out ../client-runs/example
```

On Linux, a minimal installation may also need Chromium's system libraries. Run the browser project's dependency installer using this environment:

```sh
.venv/bin/python -m playwright install-deps chromium
```

That command may request administrator access for system packages. The main BeyondSEO setup script does not install operating-system packages silently.

## 3. Check the installation

For an assistant or a terminal where activation does not persist, use `python3 scripts/run.py doctor` (Windows: `py -3 scripts/run.py doctor`). This launcher selects this folder's `.venv` and forwards CLI arguments and exit codes. Use an absolute script path when running from another directory. It also supports `--version` and every other CLI command.

```sh
python3 scripts/run.py --version
python3 scripts/run.py doctor
```

`doctor` executes a private filesystem write/readback and launches Chromium with a local JavaScript DOM probe. With `--target https://example.com --out ../doctor-run`, it separately checks DNS/address policy, robots, bounded sitemap discovery, one HTTP page and automatic rendering where needed. Results use PASS, WARN, FAIL, BLOCKED and NOT_TESTED, with commands and recorded evidence. Missing dependencies or a blocked target affect the exit status. A successful local runtime does not prove website/network access. The legacy `http_ready` flag means parser dependency availability only; use `runtime_checks` and `checks.target_reachable` for executed checks. An HTTP-only audit can still use `--mode http` without Chromium. PDF package availability is not a rendered PDF test.

## 4. Run a small crawl

```sh
python3 scripts/run.py crawl https://example.com --out ../client-runs/example --max-pages 10
```

Open `../client-runs/example/report.md` for the crawl report, `documents.jsonl` for readable page data and `content/` for Markdown/text files. Check `summary.json` before interpreting the results: a page limit, a failed request or an incomplete browser observation can restrict coverage even if the command exits successfully.

If your site redirects between the bare domain and `www`, include the other host:

```sh
beyondseo crawl https://example.com --allow-host www.example.com \
  --out runs/example-www --max-pages 25
```

An additional website host is not automatically inferred. Public browser asset/API dependencies are allowed separately and do not join the page queue.

## Hosted or read-only skill folder

Keep the uploaded skill where the host manages it. Prepare the crawler in a separate folder that the host permits for execution:

```sh
python3 /path/to/beyondseo/scripts/setup.py --venv /approved/runtime/beyondseo
python3 /path/to/beyondseo/scripts/run.py --runtime /approved/runtime/beyondseo doctor
```

Replace both paths with real paths in that execution environment. Setup uses a temporary source copy when building the package, so it does not write build files into the mounted skill. A denied path still needs a host-supported location; the option does not change permissions. Use the same `--runtime` for every crawler command. See [Work save and execution errors](agent-installation.md#when-work-cannot-save-or-run-it).

## Manual installation

Use these commands if you prefer to run the individual steps yourself:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[browser,reports]"
python -m playwright install chromium
beyondseo doctor
```

On Windows replace the first command with `py -3 -m venv .venv` and activate with `.venv\Scripts\Activate.ps1`.

## HTTP-only installation

For websites whose content arrives in the initial response:

```sh
python3 scripts/setup.py --http-only
source .venv/bin/activate
beyondseo crawl https://example.com --out runs/http --mode http
```

Add browser support later from the repository root:

```sh
python -m pip install -e ".[browser,reports]"
python -m playwright install chromium
```

## Update a local checkout

After updating the source files, activate the environment and run the same installation command again. Reinstall Chromium when the Playwright package changes:

```sh
python -m pip install -e ".[browser,reports]"
python -m playwright install chromium
```

Version 2.1 adds crawl settings and output fields. Start a fresh output folder for older 2.0 snapshots; resume requires compatible settings. Retain an older checkout if you need to regenerate an older report with its original code.

## Common setup problems

| Message or symptom | What to do |
|---|---|
| `beyondseo: command not found` | Activate `.venv`, or use `.venv/bin/beyondseo` / `.venv\Scripts\beyondseo.exe` directly |
| Optional rendering dependency missing | Install `.[browser,reports]` inside the active environment |
| Chromium executable missing | Run `python -m playwright install chromium` with that environment's Python |
| Chromium download times out or returns a gateway error | Keep the download error separate from skill registration. Check the host's permitted network access to the browser download URL; do not repeat downloads indefinitely. Use `--http-only` setup and `--mode http` for reachable pages while browser setup is unavailable. This does not verify JavaScript content. |
| Browser launch fails on Linux | Install Chromium system libraries using the command above |
| Target DNS lookup fails | Record the failed hostname and error; check the hostname and the execution environment's DNS/network access. If `robots.txt` cannot be fetched, do not bypass the robots check or describe the page's content as inspected. |
| TLS certificate error | Check the system certificate store and network configuration; certificate verification stays enabled |
| Output already contains a crawl | Use `--resume` with matching settings, or choose a fresh output folder |
| `crawl.lock exists` | Check its recorded process ID; stop an active crawl before removing a stale lock |
| Empty raw text | Try automatic or browser mode and inspect rendered content |
| Empty rendered text | Inspect `javascript_errors`, request restrictions and readiness fields; try a visible selector and a longer timeout |
| Page limit reached | Raise `--max-pages` on a resumed run |
| Server denial or challenge | Inspect the saved response and the site's access requirements; repeated retries do not guarantee access |

## Remove the local environment

Close processes using the environment, deactivate it and delete the project's `.venv` directory. The repository and your saved crawl folders remain separate. Removing the browser cache is optional and can affect other local projects that use the same browser installation.

For a designed client deliverable, follow [branded reports](branded-reports.md). `present` exports PDF and HTML locally; it needs no browser or online account. Both normal and HTTP-only setup include the free PDF renderer.

Next: [browser options](browser.md), [command reference](../references/crawler.md), or [local examples](../examples/README.md).

## Ongoing reviews and hosting access

After the first crawl, read `readiness.md` for plain-language next steps. The [operations guide](operations.md) covers snapshot comparisons, bounded review loops, checking supplied backlinks, and staged website edits over local files, SFTP or FTPS. SFTP needs the optional `sftp` package extra; FTPS uses Python’s standard library.
