#!/usr/bin/env python3
"""Check local Markdown links and embedded asset paths without network requests."""

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit


def main():
    root = Path(__file__).resolve().parents[1]
    problems = []
    checked = 0
    for page in root.rglob("*.md"):
        if any(
            part in (".venv", ".git", "build", "dist") or part.endswith(".egg-info")
            for part in page.parts
        ):
            continue
        text = re.sub(r"```.*?```", "", page.read_text(encoding="utf-8"), flags=re.S)
        links = re.findall(r"\]\(([^)]+)\)", text) + re.findall(r'(?:src|href)="([^"]+)"', text)
        for target in links:
            target = target.split(' "', 1)[0].strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or target.startswith("#") or not parsed.path:
                continue
            checked += 1
            path = page.parent / unquote(parsed.path)
            if not path.exists():
                problems.append(f"{page.relative_to(root)}: missing {target}")
    for problem in problems:
        print(problem)
    print(f"Checked {checked} local links/assets; {len(problems)} missing.")
    return bool(problems)


if __name__ == "__main__":
    raise SystemExit(main())
