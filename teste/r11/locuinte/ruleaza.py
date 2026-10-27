"""Runda 11 locuințe — rulează frazele prin calea aplicației (fără cheie API) și scrie rezumate + planșe PNG."""
import sys, json, traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from engine import interpretor, constructor, layout, render_svg, validare
import cairosvg

D = Path(__file__).parent
fraze = json.loads((D / "fraze.json").read_text())
sel = set(int(x) for x in sys.argv[1:]) if len(sys.argv) > 1 else None


def apar(a):
    s = a.get("tip", "")
    if a.get("ref"): s += f"[{a['ref']}]"
    if a.get("spec"): s += " " + " / ".join(map(str, a["spec"]))
    if a.get("laterale"):
        s += " {lat: " + "; ".join(apar(x) for x in a["laterale"]) + "}"
    if a.get("rezerva"):
        s += " {rez: " + apar(a["rezerva"]) + "}"
    return s


def plec(p, ind=1):
    out = []
    pre = "  " * ind
    ap = " | ".join(apar(a) for a in p.get("aparate", []))
    cab = (p.get("cablu") or {}).get("text", "")
    sar = p.get("sarcina") or {}
    tit = sar.get("titlu", "") + (" (" + sar.get("sub", "") + ")" if sar.get("sub") else "")
    out.append(f"{pre}- {tit or p.get('eticheta_grup','')} :: {ap} :: {cab}")
    for c in p.get("copii", []) or []:
        out += plec(c, ind + 1)
    if p.get("tablou"):
        out.append(pre + "  [tablou] " + json.dumps({k: v for k, v in p["tablou"].items() if k not in ("plecari",)}, ensure_ascii=False, default=str)[:300])
        for c in p["tablou"].get("plecari", []):
            out += plec(c, ind + 2)
    return out


def ruleaza(f):
    o = {"id": f["id"], "text": f["text"]}
    try:
        r = interpretor.interpreteaza(f["text"])
    except Exception as e:
        o["eroare"] = "interpretor: " + traceback.format_exc()[-800:]
        return o, None
    for k in ("actiune", "tip_schema", "intelegere", "intrebari", "avertismente", "neconsumat", "refuz_cod", "refuz_motiv"):
        o[k] = r.get(k)
    o["intrare"] = r.get("intrare_fizica")
    if r.get("actiune") == "refuza" or not r.get("intrare_fizica"):
        return o, None
    try:
        m, rez = constructor.genereaza(r["intrare_fizica"])
        v = validare.valideaza(m)
        o["blocheaza"] = v.get("blocheaza")
        o["verif"] = [f"{x['nivel']} {x['cod']} {x.get('obiect','')}: {x['mesaj']}" for x in v.get("verificari", [])]
        txt = [f"titlu: {m['cartus'].get('denumire2')}"]
        for i in m.get("intrari", []):
            txt.append("INTRARE " + json.dumps(i.get("sursa"), ensure_ascii=False))
            for kk in ("cablu", "cablu_ca"):
                if i.get(kk): txt.append(f"  {kk}: {i[kk].get('text')}")
            for a in i.get("aparate", []): txt.append("  ap: " + apar(a))
            for kk in i:
                if kk not in ("sursa", "cablu", "cablu_ca", "aparate"): txt.append(f"  {kk}: " + json.dumps(i[kk], ensure_ascii=False, default=str)[:400])
        b = m.get("bara") or {}
        txt.append("BARA " + str(b.get("eticheta")))
        for a in b.get("laterale", []) or []: txt.append("  lat: " + apar(a))
        for p in m.get("plecari", []): txt += plec(p)
        txt.append("NOTE: " + " || ".join(m.get("note", [])))
        o["model"] = txt
        cv = layout.build(m)
        svg = render_svg.render(cv, f"p{f['id']:02d}")
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(D / f"p{f['id']:02d}.png"), output_width=3300)
        o["png"] = f"p{f['id']:02d}.png"
    except Exception:
        o["eroare"] = "constructor/render: " + traceback.format_exc()[-1200:]
    return o, None


rez = []
for f in fraze:
    if sel and f["id"] not in sel: continue
    o, _ = ruleaza(f)
    rez.append(o)
out = D / ("rezultate.json" if not sel else "rezultate_sel.json")
out.write_text(json.dumps(rez, ensure_ascii=False, indent=1, default=str))
print("ok", len(rez))
