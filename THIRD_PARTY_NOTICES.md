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

Dependencies retain their respective licenses and notices. They are installed through their own packages, not copied into this source tree. Development uses setuptools and Ruff. No hosted crawling provider is required.
