# Validation

BeyondSEO **2.4.0** was validated locally on September 14, 2026 (Pakistan time).

## Automated and installation checks

- **110 behavioral tests passed** with Python 3.12.14 on macOS and local Chromium.
- Ruff checks, formatting, skill frontmatter and local documentation/asset links passed.
- The clean-folder installer was exercised with a fresh destination containing spaces. `scripts/setup.py` installed version 2.4.0 and launched Chromium.
- Invoking the new launcher from an unrelated directory with Python outside the installed environment selected the installed runtime, captured three local practice documents including one JavaScript-rendered document, and reproduced the model 1.1 reputation result from saved evidence: 18.9/100, low confidence.
- All 27 supplied source records remain byte-for-byte unchanged. The prior PDF comparison established 27 exact URL matches.

Tests exercise crawl scope, robots rules/availability/scope limits, redirects, sitemap/gzip handling, retry history, response limits, challenges, resume, offline exports, selected content, raw noindex preservation, browser rendering and restrictions. The new regression cases cover HTTP-200 missing-content screens, rendered metadata/duplicates, cross-host source follow-ups, late links on text-rich pages and incomplete JavaScript checks.

Reputation tests cover source-review attribution, ranges, grouping, owned/sponsored sources, mentions versus links, incomplete captures, import provenance and saved-evidence reuse. Additional tests ensure low-confidence headlines remain below 50, unsupported headlines are withheld, source limits retain unchecked candidates, duplicate rows cannot inflate coverage, unrelated target links cannot count, and owner/competitor evidence receives identical treatment. Source review notes are assessments; tests establish model behavior, not calibration to rankings.

The suite also includes readiness, snapshot comparisons, review loops and guarded content updates. Local SFTP and FTPS fixtures verify staging, upload, receipt and rollback behavior. An untrusted FTPS certificate is rejected; a trusted fixture uses encrypted channels. These checks do not certify every hosting provider.

## Assistant portability checks

- Codex CLI **0.153.4**: its actual app-server `skills/list` discovered the installed project skill. This was a read-only discovery request, not a model run.
- Hermes Agent **v0.21.1**: its actual `skills_list` and `skill_view` loaded BeyondSEO and `references/reputation.md` from an isolated profile. No model request or personal-profile installation was made.
- Claude Code **2.1.91** was available. Its official skill format and installation path were checked; an assistant-driven acceptance run was not performed.
- OpenClaw's official file format, local installation paths and runtime boundaries were checked. OpenClaw was unavailable locally and was not executed.
- ChatGPT Work guidance distinguishes local files from cloud/workspace installation. Cloud import, networking and Chromium execution have not been validated.

Eight added tests cover installer exclusions, checksum receipts, dry runs without writes, existing-install protection, nested destinations, symlinks, missing source files, launcher path independence and CLI error codes. Runtime checks validate Python/Chromium behavior; skill discovery validates loading. Neither alone certifies the quality of every host's model-generated audit. Use [the host acceptance steps](agent-installation.md) before a new client deployment.

## Practical trial

The updated report engine replayed a saved PureDesigners crawl with **134 URL records and 86 unique final URLs**. It detected all **13** missing-content destinations from the independent manual review and the **14** referring link observations. Initial-shell false positives decreased: missing-H1 findings fell from 134 to 1 and duplicate-title findings from 86 to 14. Remaining observations need page review. This was an offline reanalysis of captured evidence, not a fresh whole-site crawl or a live website repair.

A separate live reputation trial inspected five Google result pages and recorded 47 entries, yielding 46 unique candidate URLs. The native verifier observed direct target links on nine source pages and name mentions on 17 pages, including one ambiguous project-search card requiring an entity check. Twelve link checks were conclusive; 34 remained incomplete/unverified. Positive mentions were retained from six partial captures. All observed counts describe this sample only.

Re-scoring the same saved evidence with model **1.1** gives **18.9/100**, adjusted range **18.9–20.1**, provisional and **low confidence**. Supported sample points of 72.4 are reduced by the verification factor 12/46. The old 74.8 midpoint is retained only as diagnostic/historical context. This is a methodology change, not evidence that the website lost links. The range does not cover unseen web evidence or statistical confidence. No independent editorial publisher group was established. Client captures and the original assessment remain outside the publication directory.

Earlier versions also captured PureDesigners and BeyondTahir homepages with 931 and 570 selected main-text words and successful JavaScript rendering. Those dated smoke tests are not current whole-site indexing or answer-engine visibility measurements.

## Remaining release limits

The GitHub workflow targets Python 3.10/3.12 on Linux, Windows and macOS. [Current hosted results](https://github.com/beyondtahir/beyondseo/actions/workflows/tests.yml) are the live record for that matrix; local test figures above describe the recorded macOS run. This is a beta, not production-scale or every-agent certification. Dependency ranges do not certify future releases.

The runtime has no web-wide backlink graph, native unattended Google collector, actual ranking/AI-citation history, full schema-semantic validator or universal authenticated site editor. Search discovery uses supplied files or available access; the native engine performs verification and scoring. Access challenges and incomplete content remain visible.

## Release metadata

The initial public release uses the MIT license and a single package version for the CLI and crawl exports. The discovery regression test checks the in-memory and saved summary version, preventing older hard-coded export labels.

## Repeat the checks

```sh
python scripts/setup.py --dev
python -m pip install -e '.[hosting-test]'
ruff check .
ruff format --check .
python scripts/check_docs.py
python -m unittest discover -s tests -v
beyondseo doctor
```

Tests use local fixtures. Live trials run separately. Hosting tests skip when their optional fixture dependencies are absent; normal crawling needs no hosting test servers.
