"""Acquire and freeze the four UCI datasets (blueprint section 3.1, step 3).

Raw files are written once and never overwritten.  Row counts, SHA-256 hashes,
IDs, DOIs and licence are recorded so the benchmark is reproducible from a
fresh clone.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

SOURCES = {
    "bank_marketing":      {"id": 222, "doi": "10.24432/C5K306"},
    "online_shoppers":     {"id": 468, "doi": "10.24432/C5F88Q"},
    "student_performance": {"id": 320, "doi": "10.24432/C5TG7T"},
    "seoul_bike":          {"id": 560, "doi": "10.24432/C5F62R"},
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    from ucimlrepo import fetch_ucirepo

    RAW.mkdir(parents=True, exist_ok=True)
    manifest = {}

    for name, meta in SOURCES.items():
        out = RAW / f"{name}.csv"
        if out.exists():
            print(f"  {name:22s} already present, not overwriting")
        else:
            print(f"  {name:22s} fetching UCI id={meta['id']} ...", flush=True)
            repo = fetch_ucirepo(id=meta["id"])
            X, y = repo.data.features, repo.data.targets
            df = X.join(y) if y is not None else X
            df.to_csv(out, index=False)

        import pandas as pd
        df = pd.read_csv(out, low_memory=False)
        manifest[name] = {
            "uci_id": meta["id"], "doi": meta["doi"],
            "license": "CC BY 4.0",
            "url": f"https://archive.ics.uci.edu/dataset/{meta['id']}",
            "file": str(out.relative_to(ROOT)),
            "n_rows": int(len(df)), "n_columns": int(df.shape[1]),
            "columns": [str(c) for c in df.columns],
            "sha256": sha256(out),
        }
        print(f"  {name:22s} {len(df):>7,} rows x {df.shape[1]:>2} cols  "
              f"sha256={manifest[name]['sha256'][:12]}")

    (RAW / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nwrote {RAW / 'MANIFEST.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
