"""Build a single-page scoring app from a blinded packet.

    python scripts/build_scorer.py

Reading 49 reports in a markdown file and typing scores into a spreadsheet is
where scoring errors come from: lost place, mis-keyed row, drift in what a "1"
means. This presents one report at a time with the rubric always on screen,
keeps progress in the browser so the session survives a closed tab, and exports
exactly the CSV that ``score_blinded.py --ingest`` expects.

It embeds only the blinded items. The key stays on disk, sealed.
"""
from __future__ import annotations

import csv
import html
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aistat.env import load_dotenv
load_dotenv()          # credentials are project-local, not in a shell profile
warnings.filterwarnings("ignore")

from aistat.evaluation.blinded import (JUDGED_SECTIONS, RUBRIC, SCOPE,
                                       Session, blind)

BLIND = ROOT / "reports" / "blinded"
OUT = BLIND / "score.html"

TITLES = {"problem_statement": "Problem statement", "data_audit": "Data audit",
          "method_decision": "Method decision", "results": "Results",
          "interpretation": "Interpretation", "limitations": "Limitations"}


def load_calibration() -> list[dict]:
    p = BLIND / "calibration.json"
    return json.loads(p.read_text()) if p.exists() else []


def load_items() -> list[dict]:
    """Rebuild the presented items from the packet's own order."""
    sheet = BLIND / "scores_blank.csv"
    if not sheet.exists():
        raise FileNotFoundError(
            f"{sheet} not found -- run `make blind RUN=<run_name>` first")
    order = [r["item_id"] for r in csv.DictReader(sheet.open())]

    packet = (BLIND / "packet.md").read_text()
    blocks = packet.split("REPORT ")[1:]
    by_id: dict[str, dict] = {}
    for b in blocks:
        item_id = b.split("\n", 1)[0].strip()
        body = b.split("\n", 1)[1].split("-" * 72)[0]
        sections = {}
        for part in body.split("## ")[1:]:
            head, _, text = part.partition("\n")
            key = next((k for k, v in TITLES.items() if v == head.strip()), None)
            if key:
                sections[key] = text.strip()
        by_id[item_id] = {"id": item_id, "sections": sections}
    return [by_id[i] for i in order if i in by_id]


def main() -> int:
    try:
        items = load_items()
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 2

    cal = load_calibration()
    for c in cal:
        c["sections"] = {k: blind(v) for k, v in c["sections"].items()
                         if k in JUDGED_SECTIONS}
    payload = json.dumps(items, separators=(",", ":"))
    cal_payload = json.dumps(cal, separators=(",", ":"))
    rubric_rows = "".join(
        f"<tr><td class='k'>{k}</td><td>{html.escape(v)}</td></tr>"
        for k, v in RUBRIC.items())
    scope_html = html.escape(SCOPE).replace("\n\n", "</p><p>").replace("\n", " ")
    n_cal = len(cal)
    titles = json.dumps(TITLES)

    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Blinded interpretation scoring</title>
<style>
:root {{
  --paper:#f4f6f8; --surface:#fff; --surface-2:#eceff3;
  --ink:#171b21; --ink-2:#4d5763; --ink-3:#79838f;
  --rule:#dde2e8; --accent:#2c5578; --ok:#326b58; --risk:#9c4630;
}}
@media (prefers-color-scheme:dark){{:root{{
  --paper:#111419; --surface:#181c23; --surface-2:#1f242c;
  --ink:#e7eaef; --ink-2:#9aa5b2; --ink-3:#6f7a87;
  --rule:#282e37; --accent:#7fadd8; --ok:#6fb79c; --risk:#d98d74;}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);
  font:15px/1.62 ui-sans-serif,system-ui,-apple-system,sans-serif}}
.bar{{position:sticky;top:0;z-index:5;background:var(--surface);
  border-bottom:1px solid var(--rule);padding:.75rem 1.5rem;
  display:flex;gap:1.25rem;align-items:center;flex-wrap:wrap}}
.bar b{{font-variant-numeric:tabular-nums}}
.prog{{flex:1;min-width:8rem;height:6px;background:var(--surface-2);
  border-radius:3px;overflow:hidden}}
.prog i{{display:block;height:100%;background:var(--ok);width:0}}
main{{max-width:52rem;margin:0 auto;padding:1.75rem 1.5rem 8rem}}
h1{{font-size:1.5rem;margin:.4rem 0 1rem}}
.rid{{font-family:ui-monospace,monospace;font-size:.8rem;color:var(--ink-3);
  letter-spacing:.08em}}
h2{{font-size:.78rem;letter-spacing:.09em;text-transform:uppercase;
  color:var(--ink-3);margin:1.5rem 0 .3rem;font-weight:500}}
p.sec{{margin:0;max-width:70ch}}
.scope{{border:1px solid var(--rule);background:var(--surface);
  border-left:3px solid var(--accent);padding:1rem 1.2rem;margin:1rem 0}}
.scope p{{margin:0 0 .8rem;max-width:70ch}} .scope p:last-child{{margin:0}}
.judge{{border:1px solid var(--rule);background:var(--surface);
  border-left:3px solid var(--accent);padding:1rem 1.2rem;margin:1.5rem 0 0}}
.judge h3{{margin:0 0 .5rem;font-size:.95rem}}
table.rub{{border-collapse:collapse;font-size:.85rem;margin:.5rem 0 1rem}}
table.rub td{{padding:.3rem .6rem .3rem 0;vertical-align:top;color:var(--ink-2)}}
table.rub td.k{{font-family:ui-monospace,monospace;color:var(--ink);font-weight:600}}
.btns{{display:flex;gap:.6rem;flex-wrap:wrap}}
button{{font:inherit;cursor:pointer;border:1px solid var(--rule);
  background:var(--surface-2);color:var(--ink);padding:.55rem 1.1rem;
  border-radius:4px}}
button:hover{{border-color:var(--accent)}}
button.sel{{background:var(--accent);color:#fff;border-color:var(--accent)}}
button:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}
.nav{{display:flex;gap:.6rem;margin-top:1rem;align-items:center}}
.nav .sp{{flex:1}}
textarea{{width:100%;font:inherit;font-size:.9rem;padding:.5rem;
  border:1px solid var(--rule);border-radius:4px;background:var(--paper);
  color:var(--ink);margin-top:.75rem;min-height:3rem}}
.feedback{{border:1px solid var(--rule);padding:1rem 1.2rem;margin-top:1rem;
  background:var(--surface);border-left:3px solid var(--ok)}}
.feedback.miss{{border-left-color:var(--risk)}}
.feedback h4{{margin:0 0 .5rem;font-size:.95rem}}
.feedback p{{margin:0;max-width:70ch;color:var(--ink-2)}}
.done{{background:var(--surface);border:1px solid var(--rule);
  border-left:3px solid var(--ok);padding:1.25rem 1.4rem;margin-top:1.5rem}}
kbd{{font-family:ui-monospace,monospace;font-size:.78rem;
  background:var(--surface-2);border:1px solid var(--rule);
  border-radius:3px;padding:.05em .35em}}
.hint{{font-size:.82rem;color:var(--ink-3);margin-top:.6rem;max-width:70ch}}
</style></head><body>

<div class="bar">
  <b id="pos">Before you start</b>
  <div class="prog"><i id="prog"></i></div>
  <span class="rid" id="rid"></span>
  <button id="export">Export CSV</button>
</div>

<main>
  <div id="intro">
    <h1>Before you start</h1>
    <div class="scope"><p>{scope_html}</p></div>
    <table class="rub">{rubric_rows}</table>
    <p class="hint">You will score {n_cal} worked examples first and see the
      intended answer after each. It takes about five minutes, and it is what
      makes two people's scores comparable — the first round ran without it and
      returned no usable agreement.</p>
    <div class="btns"><button id="begin">Start calibration</button></div>
  </div>

  <div id="report" hidden></div>

  <div class="judge" id="judge" hidden>
    <h3 id="ask">Does the Interpretation follow from the Results above?</h3>
    <table class="rub">{rubric_rows}</table>
    <div class="btns">
      <button data-s="0">0 · Not supported</button>
      <button data-s="1">1 · Partly supported</button>
      <button data-s="2">2 · Fully supported</button>
    </div>
    <textarea id="note" placeholder="Optional note — why, in a few words"></textarea>
    <div class="nav">
      <button id="prev">← Previous</button><span class="sp"></span>
      <button id="next">Skip →</button>
    </div>
    <p class="hint">Keys: <kbd>0</kbd> <kbd>1</kbd> <kbd>2</kbd> to score,
      <kbd>←</kbd> <kbd>→</kbd> to move. Progress saves in this browser, so you
      can close the tab and come back. Take a break every fifteen or so —
      this measures consistency, not speed.</p>
    <div class="feedback" id="feedback" hidden></div>
  </div>

  <div class="done" id="done" hidden></div>
</main>

<script>
const ITEMS = {payload};
const CAL = {cal_payload};
const TITLES = {titles};
const KEY = "aistat-blind-scores";
let phase = "intro";
let ci = 0, i = 0;
let scores = {{}};
try {{ scores = JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{}}

const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c =>
  ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]));

const save = () => {{
  try {{ localStorage.setItem(KEY, JSON.stringify(scores)); }} catch (e) {{}}
}};

function showSections(sections) {{
  $("#report").innerHTML = Object.entries(TITLES)
    .filter(([k]) => sections[k])
    .map(([k, t]) => `<h2>${{t}}</h2><p class="sec">${{esc(sections[k])}}</p>`)
    .join("");
}}

function renderCalibration() {{
  const c = CAL[ci];
  $("#intro").hidden = true;
  $("#report").hidden = false;
  $("#judge").hidden = false;
  $("#note").hidden = true;
  $("#pos").textContent = `calibration ${{ci + 1}} / ${{CAL.length}}`;
  $("#rid").textContent = "worked example";
  $("#prog").style.width = (100 * ci / CAL.length) + "%";
  $("#ask").textContent = "Score this, then check your answer.";
  showSections(c.sections);
  document.querySelectorAll("[data-s]").forEach(b => b.classList.remove("sel"));
  $("#feedback").hidden = true;
  window.scrollTo({{ top: 0 }});
}}

function judgeCalibration(v) {{
  const c = CAL[ci];
  const hit = v === c.score;
  const fb = $("#feedback");
  fb.hidden = false;
  fb.className = "feedback" + (hit ? "" : " miss");
  const last = ci >= CAL.length - 1;
  fb.innerHTML = `<h4>${{hit ? "Agreed" : "Not the intended score"}} — this is a
    ${{c.score}}</h4><p>${{esc(c.why)}}</p>
    <div class="btns" style="margin-top:.9rem"><button id="calnext">${{
      last ? "Begin scoring" : "Next example"}}</button></div>`;
  $("#calnext").addEventListener("click", () => {{
    if (!last) {{ ci++; renderCalibration(); }}
    else {{ phase = "scoring"; $("#note").hidden = false; render(); }}
  }});
}}

function render() {{
  if (phase !== "scoring") return;
  const it = ITEMS[i];
  $("#intro").hidden = true;
  $("#report").hidden = false;
  $("#judge").hidden = false;
  $("#pos").textContent = `${{i + 1}} / ${{ITEMS.length}}`;
  $("#rid").textContent = it.id;
  const n = Object.keys(scores).length;
  $("#prog").style.width = (100 * n / ITEMS.length) + "%";
  $("#ask").textContent = "Does the Interpretation follow from the Results above?";
  $("#feedback").hidden = true;
  showSections(it.sections);
  const rec = scores[it.id] || {{}};
  document.querySelectorAll("[data-s]").forEach(b =>
    b.classList.toggle("sel", String(rec.score) === b.dataset.s));
  $("#note").value = rec.notes || "";
  $("#done").hidden = n < ITEMS.length;
  if (n >= ITEMS.length) {{
    $("#done").innerHTML = `<strong>All ${{ITEMS.length}} scored.</strong>
      Export the CSV, save it over <code>reports/blinded/scores_blank.csv</code>,
      then run <code>make blind-ingest</code>.`;
  }}
  window.scrollTo({{ top: 0 }});
}}

function score(v) {{
  if (phase === "calibration") {{ judgeCalibration(v); return; }}
  if (phase !== "scoring") return;
  scores[ITEMS[i].id] = {{ score: v, notes: $("#note").value.trim() }};
  save();
  if (i < ITEMS.length - 1) i++;
  render();
}}

$("#begin").addEventListener("click", () => {{
  if (CAL.length) {{ phase = "calibration"; renderCalibration(); }}
  else {{ phase = "scoring"; render(); }}
}});
document.querySelectorAll("[data-s]").forEach(b =>
  b.addEventListener("click", () => score(Number(b.dataset.s))));
$("#prev").addEventListener("click", () => {{ if (i > 0) i--; render(); }});
$("#next").addEventListener("click", () => {{
  if (i < ITEMS.length - 1) i++; render(); }});
$("#note").addEventListener("input", () => {{
  const rec = scores[ITEMS[i]?.id];
  if (rec) {{ rec.notes = $("#note").value.trim(); save(); }}
}});
document.addEventListener("keydown", e => {{
  if (e.target.tagName === "TEXTAREA" || phase === "intro") return;
  if (["0","1","2"].includes(e.key)) score(Number(e.key));
  else if (e.key === "ArrowLeft" && i > 0) {{ i--; render(); }}
  else if (e.key === "ArrowRight" && i < ITEMS.length - 1) {{ i++; render(); }}
}});
$("#export").addEventListener("click", () => {{
  const rows = ["item_id,score,notes"];
  for (const it of ITEMS) {{
    const r = scores[it.id];
    const note = (r?.notes || "").replace(/"/g, '""');
    rows.push(`${{it.id}},${{r ? r.score : ""}},"${{note}}"`);
  }}
  const blob = new Blob([rows.join("\\n") + "\\n"], {{ type: "text/csv" }});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "scores_blank.csv";
  a.click();
  URL.revokeObjectURL(a.href);
}});
</script>
</body></html>
"""
    OUT.write_text(doc, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size/1024:,.0f} KB, "
          f"{len(cal)} calibration + {len(items)} scored)")
    print(f"\n  open it:  open {OUT.relative_to(ROOT)}")
    print("  calibrate, score, export the CSV over "
          "reports/blinded/scores_blank.csv,\n  then: make blind-ingest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
