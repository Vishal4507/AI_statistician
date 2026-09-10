"""Project-local credential loading.

Credentials live in a gitignored `.env` beside the project rather than a shell
profile -- this machine's ~/.bash_profile is root-owned, and a project-scoped
secret is cleaner anyway.

The Makefile loads it, but a script invoked directly did not, so the same
credential worked through `make` and appeared missing through `python3
scripts/...`. Loading here means every entry point behaves the same.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path | None = None, override: bool = False) -> list[str]:
    """Load KEY=VALUE lines into the environment. Returns the names set.

    A value already present in the environment wins unless ``override``, so an
    explicit `export` in the caller's shell beats the file.
    """
    p = path or (ROOT / ".env")
    if not p.exists():
        return []
    loaded = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if not key or not value:
            continue
        if override or key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded
