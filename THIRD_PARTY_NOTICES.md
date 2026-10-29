# Third-party dependencies

BeyondSEO's crawler, queue, extraction rules, reporting and command-line interface are maintained in this repository. The project uses the following independently distributed libraries:

| Component | Purpose | Upstream |
|---|---|---|
| BeautifulSoup | HTML parsing and CSS selection | https://www.crummy.com/software/BeautifulSoup/ |
| Colorama | Cross-platform terminal colors | https://github.com/tartley/colorama |
| Playwright | Optional local browser control | https://github.com/microsoft/playwright-python |
| Paramiko | Optional encrypted SFTP publishing | https://www.paramiko.org/ |
| Chromium | Optional browser runtime, installed through Playwright | https://www.chromium.org/ |
| ReportLab | Local PDF layout and embedded Bitstream Vera fonts, distributed with its package | https://www.reportlab.com/ |
| Google Auth OAuthlib | Optional read-only Google browser consent | https://github.com/googleapis/google-auth-library-python-oauthlib |
| Requests | Optional Google account HTTP transport | https://requests.readthedocs.io/ |

Dependencies retain their respective licenses and notices. They are installed through their own packages, not copied into this source tree. Development uses setuptools and Ruff. No hosted crawling provider is required.

The editable README animation sources use an optional separately installed GSAP runtime
and HyperFrames renderer. These artwork tools are not required by the SEO engine or
included in the skill upload. Original character artwork and native report output are
identified in [the media notes](https://github.com/beyondtahir/beyondseo/blob/main/media/README.md); the dated Academy performance capture
was supplied with the owner's publication permission.
