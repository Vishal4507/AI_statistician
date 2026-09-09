"""Bundle the static explorer into one self-contained page.

The site/ directory needs a host that serves several files; this collapses it
into a single HTML document with the data, styles and script inlined, so it can
be published anywhere that accepts one file -- including as an Artifact, which
gives a shareable link without a Netlify account.

    python scripts/build_artifact.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
OUT = ROOT / "site" / "explorer.html"


def main() -> int:
    for required in ("index.html", "style.css", "app.js", "data/meta.json",
                     "data/cases.json", "data/runs.json"):
        if not (SITE / required).exists():
            print(f"missing {required} -- run scripts/export_site.py first",
                  file=sys.stderr)
            return 2

    css = (SITE / "style.css").read_text()
    js = (SITE / "app.js").read_text()
    meta = json.loads((SITE / "data" / "meta.json").read_text())
    cases = json.loads((SITE / "data" / "cases.json").read_text())
    runs = json.loads((SITE / "data" / "runs.json").read_text())

    # Replace the network boot with the embedded payload. Everything else in
    # app.js is unchanged, so the two builds cannot drift apart.
    js = js.replace(
        '''async function boot() {
  try {
    const [meta, cases, runs] = await Promise.all([
      fetch("data/meta.json").then((r) => r.json()),
      fetch("data/cases.json").then((r) => r.json()),
      fetch("data/runs.json").then((r) => r.json()),
    ]);
    Object.assign(state, { meta, cases, runs });
    render();
  } catch (err) {''',
        '''function boot() {
  try {
    const { meta, cases, runs } = window.__AISTAT__;
    Object.assign(state, { meta, cases, runs });
    render();
  } catch (err) {''')

    # The corpus self-check in the Reports view fetches too; make it read the
    # embedded object instead.
    js = js.replace('await fetch("data/runs.json").then((r) => r.json())',
                    'window.__AISTAT__.runs')

    payload = json.dumps({"meta": meta, "cases": cases, "runs": runs},
                         separators=(",", ":"))

    head = (SITE / "index.html").read_text()
    body = head.split("<body>", 1)[1].split("</body>", 1)[0]
    body = body.replace('<link rel="stylesheet" href="style.css">', "")
    body = body.replace('<script src="app.js"></script>', "")

    # The charset declaration must survive: a plain static server sends no
    # charset header, and the browser then guesses latin-1 and mangles every
    # em-dash. Harmlessly redundant where a wrapper already supplies one.
    doc = f"""<meta charset="utf-8">
<title>AI Statistician Explorer</title>
<style>
{css}
</style>
{body}
<script>window.__AISTAT__ = {payload};</script>
<script>
{js}
</script>
"""
    OUT.write_text(doc, encoding="utf-8")
    kb = OUT.stat().st_size / 1024
    print(f"wrote {OUT.relative_to(ROOT)}  ({kb:,.0f} KB, single file)")
    if kb > 15000:
        print("  WARNING: approaching the 16 MB artifact ceiling")
    return 0


if __name__ == "__main__":
    sys.exit(main())
