"""Assembles deploy/cloud/dist: the source LingCode Cloud builds and runs as one hosted app.

Usage (from the repository root, after `npm run build` in web/):  python3 deploy/cloud/build.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = REPO / "deploy" / "cloud"
OUT = HERE / "dist"
MAX_FILES = 500  # LingCode Cloud's source limit


def main() -> int:
    web = REPO / "web" / "dist"
    if not (web / "index.html").is_file():
        print("web/dist is missing: run `npm run build` in web/ first")
        return 1
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store")
    shutil.copytree(REPO / "server" / "opa", OUT / "opa", ignore=ignore)
    shutil.copytree(web, OUT / "web-dist", ignore=ignore)
    # The browser lock is the server lock plus Playwright, hash-pinned and exported from server/uv.lock.
    shutil.copy(REPO / "deploy" / "locks" / "browser.txt", OUT / "requirements.txt")
    shutil.copy(HERE / "start.py", OUT / "start.py")
    (OUT / "Procfile").write_text("web: python start.py\n")
    count = sum(1 for p in OUT.rglob("*") if p.is_file())
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"{OUT.relative_to(REPO)}: {count} files, {size / 1e6:.1f} MB")
    if count > MAX_FILES:
        print(f"too many files for LingCode Cloud (limit {MAX_FILES})")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
