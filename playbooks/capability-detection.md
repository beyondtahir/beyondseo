# Capability detection

Run `python3 scripts/check_environment.py` from the skill folder, then inspect the task's supplied URL, goal and files. The core engine needs Python and BeautifulSoup; Colorama only affects terminal styling. Local Playwright plus installed Chromium enables the optional renderer.

Check output-directory write access and use a bounded crawl to establish network reachability. Do not turn a missing dependency or blocked response into an SEO finding. Follow `docs/setup.md` for dependencies and `audit-modes.md` for alternative evidence modes.

The executable capability contract and limitations are in `references/crawler.md` and `references/measurement-boundaries.md`. Never infer availability of rankings, analytics, Maps, backlink databases or AI-answer visibility merely because the crawler runs.
