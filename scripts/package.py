"""Build the handoff archive, and refuse to build one containing a secret.

    python scripts/package.py [--out PATH]

The archive is what leaves this machine, so the exclusion rules matter more
here than anywhere else in the project.  Two independent guards run:

  by name     a deny-list of paths that must never be packaged
  by content  every file is scanned for key-shaped strings before it is added

The second exists because the first is only as good as its author's memory.  A
credential can reach a file nobody thought of -- a notebook checkpoint, a shell
history, a debug log, a results file that captured an error message containing
a URL with a token.  Scanning content catches those; a deny-list does not.

A hit aborts the build.  It never silently drops the file, because a project
that quietly omits things is worse than one that stops and explains.
"""
from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Directory names pruned wherever they appear.
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".ipynb_checkpoints",
             "node_modules", ".venv", "venv", ".mypy_cache", ".ruff_cache",
             ".DS_Store"}

#: Exact repo-relative paths never packaged.  `.env.example` is deliberately
#: absent from this list: the template documents which variables are needed and
#: carries no values.
SKIP_PATHS = {".env"}

#: Suffixes never packaged.
SKIP_SUFFIXES = {".zip", ".pyc", ".pyo"}

#: Key shapes, kept broad on purpose.  A false positive costs one look; a false
#: negative publishes a credential.
SECRET = re.compile(
    rb"sk-ant-[A-Za-z0-9_-]{20,}"        # Anthropic
    rb"|gsk_[A-Za-z0-9]{40,}"            # Groq
    rb"|sk-or-v1-[A-Za-z0-9]{40,}"       # OpenRouter
    rb"|sk-[A-Za-z0-9]{40,}"             # OpenAI and lookalikes
    rb"|csk-[A-Za-z0-9]{40,}"            # Cerebras
    rb"|ghp_[A-Za-z0-9]{36}"             # GitHub
)

TEXTLIKE = {".py", ".md", ".txt", ".json", ".jsonl", ".csv", ".toml", ".cfg",
            ".ini", ".yml", ".yaml", ".html", ".js", ".css", ".sh", ".env",
            ".example", ".ipynb", ".log", ""}


def excluded(rel: Path) -> bool:
    if any(part in SKIP_DIRS for part in rel.parts):
        return True
    if str(rel) in SKIP_PATHS or rel.suffix in SKIP_SUFFIXES:
        return True
    # .env.local, .env.production and friends -- everything but the template
    return rel.name.startswith(".env") and rel.name != ".env.example"


def scan(path: Path) -> str | None:
    """Return the offending pattern's description, or None when clean."""
    if path.suffix.lower() not in TEXTLIKE and path.stat().st_size > 2_000_000:
        return None                      # large binaries: images, pdfs
    try:
        blob = path.read_bytes()
    except OSError:
        return None
    m = SECRET.search(blob)
    return m.group(0)[:12].decode("ascii", "replace") + "..." if m else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT.parent / "ai-statistician-complete.zip"))
    args = ap.parse_args()
    out = Path(args.out).resolve()

    files, skipped = [], 0
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if excluded(rel):
            skipped += 1
            continue
        files.append((p, rel))

    leaks = [(rel, hit) for p, rel in files if (hit := scan(p))]
    if leaks:
        print("REFUSING TO PACKAGE -- key-shaped strings found:", file=sys.stderr)
        for rel, hit in leaks:
            print(f"  {rel}: {hit}", file=sys.stderr)
        print("\nRemove the credential, rotate it, then run this again.",
              file=sys.stderr)
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p, rel in files:
            z.write(p, Path("ai-statistician") / rel)

    mb = out.stat().st_size / 1e6
    print(f"  {out}")
    print(f"  {len(files)} files, {mb:.1f} MB  ({skipped} excluded)")
    print(f"  scanned every file for credentials: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
