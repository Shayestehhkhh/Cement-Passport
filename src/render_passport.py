"""Render a DCP batch record as a readable, phone-friendly passport page.

The page shows what a stakeholder would see after scanning the QR code of a cement batch:
the EN 197-1 designation, key figures, composition, safety, EN 15804 indicators per module,
and which role sees which part. Synthetic data only; the record is validated first.

Usage:
    python src/render_passport.py examples/batch-valid.json [output_dir] [--qr-url URL]

--qr-url  optional address encoded in the QR printed on the page (for example the address
          where the page itself is published online). Without it, the QR holds a short text
          summary that any phone shows offline.
"""
import base64
import html
import json
import sys
from pathlib import Path

import qrcode

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_qr import summary_text  # noqa: E402
from passport_report import a1_a3_total  # noqa: E402
from validate_passport import validate_record  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
E = html.escape


def _g(value):
    """Number without trailing zeros, or a dash when the indicator is not declared."""
    return "–" if value is None else f"{value:g}"

STYLE = """
/* Layout: a cement-bag label at the top, then role-marked sections in one column (max 760px). */
:root{
  --bg:#eceeef; --paper:#ffffff; --ink:#1b2126; --muted:#5d6870; --line:#cfd5d9;
  --accent:#c99a12; --accent-ink:#3a2c00; --bar:#5d7584; --bar2:#9db0bc; --bar3:#d5dde2;
  --ok:#2f7d4f; --public:#2f7d4f; --engineer:#2f5f8f; --auditor:#6b4a8f; --warn-bg:#fff6d6; --warn-line:#e2c35c;
  --f-display:"Archivo",system-ui,"Segoe UI",Arial,sans-serif;
  --f-body:"Source Sans 3",system-ui,"Segoe UI",Arial,sans-serif;
  --f-mono:"JetBrains Mono",ui-monospace,Consolas,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#14181b; --paper:#1d2327; --ink:#e7ecef; --muted:#9aa6ad; --line:#323b41;
  --accent:#e0b43a; --accent-ink:#2a2000; --bar:#8fa7b5; --bar2:#5f7684; --bar3:#3b4952;
  --ok:#6cc495; --public:#58b37f; --engineer:#6f9fd1; --auditor:#a789c9; --warn-bg:#2d2812; --warn-line:#7a6625; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#14181b; --paper:#1d2327; --ink:#e7ecef; --muted:#9aa6ad; --line:#323b41;
  --accent:#e0b43a; --accent-ink:#2a2000; --bar:#8fa7b5; --bar2:#5f7684; --bar3:#3b4952;
  --ok:#6cc495; --public:#58b37f; --engineer:#6f9fd1; --auditor:#a789c9; --warn-bg:#2d2812; --warn-line:#7a6625; color-scheme:dark}
body{background:var(--bg);color:var(--ink);font:16px/1.5 var(--f-body);margin:0}
.wrap{max-width:760px;margin:0 auto;padding-block:16px 40px;
  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));
  display:flex;flex-direction:column;gap:18px}
.note{background:var(--warn-bg);border:1px solid var(--warn-line);border-radius:8px;padding:10px 12px;font-size:14px}
.label{background:var(--paper);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.label-top{background:var(--accent);color:var(--accent-ink);padding:10px 16px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;
  font:600 12px/1.3 var(--f-display);letter-spacing:.12em;text-transform:uppercase}
.label-body{padding:16px;display:flex;flex-direction:column;gap:6px}
.desig{font:800 clamp(30px,8vw,44px)/1.05 var(--f-display);letter-spacing:-.01em;margin:0}
.desig small{display:block;font:600 15px/1.4 var(--f-body);color:var(--muted);letter-spacing:0;margin-top:6px}
.mono{font-family:var(--f-mono);font-size:.92em}
.figs{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--line);border-top:1px solid var(--line)}
.fig{background:var(--paper);padding:12px 16px;display:flex;flex-direction:column;gap:2px;min-width:0}
.fig .k{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}
.fig .v{font:700 24px/1.2 var(--f-display);font-variant-numeric:tabular-nums}
.fig .v span{font:500 14px var(--f-body);color:var(--muted)}
.fig .s{font-size:13px;color:var(--ok)}
.meter{height:6px;background:var(--bar3);border-radius:3px;overflow:hidden;margin-top:4px}
.meter i{display:block;height:100%;background:var(--ok)}
section{display:flex;flex-direction:column;gap:10px}
h2{font:700 18px/1.3 var(--f-display);margin:0;display:flex;align-items:center;gap:10px;flex-wrap:wrap;text-wrap:balance}
.chip{font:700 11px/1 var(--f-body);letter-spacing:.08em;text-transform:uppercase;color:#fff;border-radius:999px;padding:5px 9px}
.chip.public{background:var(--public)}.chip.engineer{background:var(--engineer)}.chip.auditor{background:var(--auditor)}
.panel{background:var(--paper);border:1px solid var(--line);border-radius:10px;padding:4px 16px}
dl{margin:0;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.3fr)}
dt,dd{margin:0;padding:10px 0;border-bottom:1px solid var(--line);min-width:0;overflow-wrap:anywhere}
dt{color:var(--muted);padding-right:12px}
dl>:nth-last-child(-n+2){border-bottom:0}
.stack{display:flex;height:28px;border-radius:6px;overflow:hidden;margin:14px 0 8px}
.stack div{display:flex;align-items:center;justify-content:center;font:600 12px var(--f-body);color:#fff;min-width:0;white-space:nowrap;overflow:hidden}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:14px;padding-bottom:12px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
.tablebox{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px;font-variant-numeric:tabular-nums}
th,td{padding:9px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.05em}
td.n,th.n{text-align:right}
tr:last-child td{border-bottom:0}
.bars{display:flex;flex-direction:column;gap:8px;padding:14px 0}
.brow{display:grid;grid-template-columns:52px minmax(0,1fr) 64px;align-items:center;gap:10px;font-size:14px}
.brow .t{position:relative;height:16px;background:var(--bar3);border-radius:3px;overflow:hidden}
.brow .t i{position:absolute;top:0;bottom:0;background:var(--bar)}
.brow .t s{position:absolute;top:0;bottom:0;left:50%;width:1px;background:var(--muted)}
.brow .val{text-align:right;font-variant-numeric:tabular-nums}
.brow b{font-family:var(--f-mono);font-weight:600}
.qrbox{display:flex;gap:16px;align-items:center;flex-wrap:wrap;background:var(--paper);border:1px solid var(--line);border-radius:10px;padding:16px}
.qrbox img{width:150px;height:150px;background:#fff;padding:6px;border-radius:6px;image-rendering:pixelated}
.qrbox p{margin:0;max-width:44ch;min-width:0;font-size:14px;color:var(--muted)}
.foot{font-size:13px;color:var(--muted)}
"""


def _qr_data_uri(content):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(content)
    qr.make(fit=True)
    import io
    buf = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buf)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _dl(pairs):
    return "<dl>" + "".join(f"<dt>{E(k)}</dt><dd>{v}</dd>" for k, v in pairs) + "</dl>"


def page_body(record, qr_url=None):
    """HTML of the page content (title, style and markup, without the document skeleton)."""
    problems = validate_record(record)
    if problems:
        raise ValueError(f"record rejected, no passport page generated: {problems}")
    t, c, s, st = record["traceability"], record["composition"], record["safety"], record["strength"]
    lca = record["lcaIndicators"]
    unit = lca["declaredUnit"]
    entries = lca["indicatorsPerModule"]
    gwp = a1_a3_total(entries)
    gwp_html = (f'<span class="v">{gwp:g}<span> kg CO₂e</span></span><span class="s" style="color:var(--muted)">per {E(unit)}</span>'
                if gwp is not None else
                '<span class="v">–</span><span class="s" style="color:var(--muted)">Not available (A1, A2 and A3 not all declared)</span>')
    early = st.get("earlyStrength")
    cr = s["solubleChromiumVI"]

    colors = {"clinker": "var(--bar)", "mainConstituent": "var(--accent)", "minorAdditionalConstituent": "var(--bar2)",
              "calciumSulfate": "var(--bar2)", "additive": "var(--muted)"}
    stack = "".join(
        f'<div style="width:{x["massPercent"]}%;background:{colors[x["role"]]}">{x["massPercent"]:g}%</div>'
        for x in c["constituents"])
    legend = "".join(f'<span><i style="background:{colors[x["role"]]}"></i>{E(x["name"])}</span>'
                     for x in c["constituents"])
    rows = "".join(
        f'<tr><td>{E(x["name"])}</td><td>{E(x["role"])}</td><td class="mono">{E(x["casNumber"])}</td>'
        f'<td class="n">{x["massPercent"]:g}</td></tr>' for x in c["constituents"])
    vmax = max(abs(e["gwpTotal"]) for e in entries) or 1
    has_negative = any(e["gwpTotal"] < 0 for e in entries)

    def bar(value):
        """Bar from a zero line: at the left edge, or in the middle when any value is negative."""
        if not has_negative:
            return f'<i style="left:0;width:{100 * value / vmax:.1f}%"></i>'
        width = 50 * abs(value) / vmax
        left = 50 - width if value < 0 else 50
        return f'<i style="left:{left:.1f}%;width:{width:.1f}%"></i><s></s>'
    bars = "".join(
        f'<div class="brow"><b>{E(e["module"])}</b><div class="t">{bar(e["gwpTotal"])}</div>'
        f'<span class="val">{e["gwpTotal"]:g}</span></div>' for e in entries)
    mod_rows = "".join(
        f'<tr><td class="mono">{E(e["module"])}</td><td class="n">{e["gwpTotal"]:g}</td>'
        f'<td class="n">{_g(e.get("primaryEnergyRenewableTotal"))}</td>'
        f'<td class="n">{_g(e.get("primaryEnergyNonRenewableTotal"))}</td><td>{E(e.get("dataSource", "–"))}</td></tr>'
        for e in entries)
    q = t.get("quarryLocation")
    qr_content = qr_url or summary_text(record)
    qr_text = ("Scan to open this passport on a phone." if qr_url else
               "Scan with a phone camera: the QR holds a short text summary of this batch and works offline.")

    return f"""<title>Cement Passport {E(record['batchID'])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700;800&family=JetBrains+Mono:wght@500;600&family=Source+Sans+3:wght@400;600;700&display=swap">
<style>{STYLE}</style>
<main class="wrap">
<div class="note"><b>Synthetic example.</b> Produced by the Digital Cement Passport pilot. The batch, plant and every value are invented. This is not a real cement, a conformity assessment or proof of regulatory compliance.</div>

<article class="label" aria-label="Batch label">
  <div class="label-top"><span>Digital Cement Passport</span><span class="mono">{E(record['batchID'])}</span></div>
  <div class="label-body">
    <h1 class="desig">{E(c['cementType'])} {E(c['strengthClass'])}<small>Common cement to EN 197-1 · {E(t['plantLocation'])} · made {E(t['manufacturingDate'])}</small></h1>
  </div>
  <div class="figs">
    <div class="fig"><span class="k">Clinker</span><span class="v">{c['clinkerRatio']:g}<span> %</span></span></div>
    <div class="fig"><span class="k">28-day strength</span><span class="v">{st['standardStrength28Days']:g}<span> MPa</span></span></div>
    <div class="fig"><span class="k">Soluble Cr(VI)</span><span class="v">{cr:g}<span> / 2 mg/kg</span></span>
      <div class="meter" aria-hidden="true"><i style="width:{min(100, 50 * cr):.0f}%"></i></div><span class="s">At or below the REACH limit</span></div>
    <div class="fig"><span class="k">GWP A1–A3</span>{gwp_html}</div>
  </div>
</article>

<section><h2><span class="chip public">Public</span>Identity</h2>
<div class="panel">{_dl([
        ("Batch ID", f'<span class="mono">{E(record["batchID"])}</span>'),
        ("Cement type (EN 197-1)", E(c["cementType"])),
        ("Plant", E(t["plantLocation"])),
        ("Energy source", E(record.get("energySourceType", "–"))),
        ("Passport address", f'<span class="mono">{E(record["passportURI"])}</span>'),
    ])}</div></section>

<section><h2><span class="chip public">Public</span>Where the carbon comes from</h2>
<div class="panel"><div class="bars" role="img" aria-label="GWP-total per EN 15804 module">{bars}</div>
<p class="foot" style="margin:0 0 12px">GWP-total in kg CO₂e per {E(unit)}, by EN 15804 module: A1 raw materials, A2 transport, A3 manufacturing, C1–C4 end of life.</p></div></section>

<section><h2><span class="chip engineer">Engineer</span>Strength and documents</h2>
<div class="panel">{_dl([
        ("Strength class (EN 197-1)", E(c["strengthClass"])),
        ("28-day compressive strength", f'{st["standardStrength28Days"]:g} MPa'),
        ("Early strength", f'{early["value"]:g} MPa at {early["ageDays"]} days' if early else "–"),
        ("Manufacturing date", E(t["manufacturingDate"])),
        ("Safety data sheet", f'<span class="mono">{E(s.get("safetyDataSheet", "–"))}</span>'),
        ("Recyclability status (Stage C)", E(record.get("endOfLife", {}).get("recyclabilityStatus", "–"))),
    ])}</div></section>

<section><h2><span class="chip auditor">Auditor</span>Composition</h2>
<div class="panel"><div class="stack" role="img" aria-label="Constituent shares">{stack}</div><div class="legend">{legend}</div>
<div class="tablebox"><table><thead><tr><th>Constituent</th><th>Role</th><th>CAS No.</th><th class="n">% mass</th></tr></thead><tbody>{rows}</tbody></table></div>
{_dl([("Clinker ratio (EN 197-1)", f'{c["clinkerRatio"]:g} % of main + minor constituents')])}</div></section>

<section><h2><span class="chip auditor">Auditor</span>Safety and origin</h2>
<div class="panel">{_dl([
        ("Water-soluble chromium VI", f'{cr:g} mg/kg (limit 2 mg/kg, REACH Annex XVII, entry 47)'),
        ("Manufacturer ID", f'<span class="mono">{E(t["manufacturerID"])}</span>'),
        ("Product SKU", f'<span class="mono">{E(t["productSKU"])}</span>'),
        ("Quarry location", f'{q["latitude"]:g}, {q["longitude"]:g} (placeholder)' if q else "–"),
    ])}</div></section>

<section><h2><span class="chip auditor">Auditor</span>EN 15804 indicators per {E(unit)}</h2>
<div class="panel"><div class="tablebox"><table><thead><tr><th>Module</th><th class="n">GWP-total kg CO₂e</th><th class="n">PERT MJ</th><th class="n">PENRT MJ</th><th>Source</th></tr></thead><tbody>{mod_rows}</tbody></table></div></div></section>

<div class="qrbox"><img src="{_qr_data_uri(qr_content)}" alt="QR code of this passport"><p>{E(qr_text)} In a deployed system each role would see only its own sections; all are shown here for demonstration.</p></div>
</main>
"""


def render(record, out_dir=ROOT / "output", qr_url=None):
    """Write a standalone HTML page and return its path."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    body = page_body(record, qr_url)
    # title, font links and styles belong in <head>; the visible content starts at <main>
    head_part, main_part = body.split("<main", 1)
    doc = ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
           f'{head_part}</head><body>\n<main{main_part}</body></html>\n')
    target = out_dir / f"passport_{record['batchID']}.html"
    target.write_text(doc, encoding="utf-8")
    return target


if __name__ == "__main__":
    args = sys.argv[1:]
    url = None
    if "--qr-url" in args:
        i = args.index("--qr-url")
        url = args[i + 1]
        del args[i:i + 2]
    if not args:
        print(__doc__)
        sys.exit(2)
    with open(args[0], encoding="utf-8") as f:
        rec = json.load(f)
    path = render(rec, args[1] if len(args) > 1 else ROOT / "output", url)
    print(f"Passport page written to {path} - open it in a web browser.")
