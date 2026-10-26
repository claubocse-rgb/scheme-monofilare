"""Runda 9 fotovoltaic — harness: interpreteaza_local → constructor → validare → layout → SVG/PNG.
Rulare: cd /home/claude/sm && python3 teste/r9/fotovoltaic/ruleaza.py [id ...]"""
import json, sys, traceback
from pathlib import Path
RAD = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAD)); sys.path.insert(0, str(Path(__file__).parent))
from engine import interpretor, constructor, layout, render_svg, validare
from fraze_r9 import F
OUT = Path(__file__).parent

def walk(o, acc):
    if isinstance(o, dict):
        if "tip" in o and isinstance(o.get("tip"), str):
            spec = o.get("spec") or []
            p = o.get("param") or {}
            acc.append(f"{o['tip']}:{o.get('ref','')}" + (f"[{' | '.join(map(str,spec))}]" if spec else "")
                       + (f"{{{p.get('model','')}}}" if p.get("model") else ""))
        for k in ("sursa", "sarcina"):
            if isinstance(o.get(k), dict):
                acc.append(f"<{k}:{o[k].get('titlu','')} / {o[k].get('sub','')}>")
        if isinstance(o.get("cablu"), dict) and o["cablu"].get("text"):
            acc.append(f"~cablu {o['cablu'].get('ref','')}: {o['cablu']['text']}")
        if isinstance(o.get("cablu_ca"), dict) and o["cablu_ca"].get("text"):
            acc.append(f"~cablu_ca: {o['cablu_ca']['text']}")
        for k, v in o.items():
            if k in ("lista", "spec", "param", "calc", "cartus", "materiale", "calc_rezumat", "note"): continue
            walk(v, acc)
    elif isinstance(o, list):
        for x in o: walk(x, acc)

def ruleaza(ids=None):
    rez = []
    for fid, text, astept in F:
        if ids and fid not in ids: continue
        d = {"id": fid, "text": text, "asteptat": astept}
        try:
            r = interpretor.interpreteaza_local(text)
            d.update({k: r.get(k) for k in ("actiune", "tip_schema", "intrare_fizica", "presupus", "intrebari",
                                             "avertismente", "refuz_cod", "refuz_motiv", "neconsumat")})
            if r.get("actiune") != "refuza" and r.get("intrare_fizica"):
                m, _ = constructor.genereaza(r["intrare_fizica"])
                v = validare.valideaza(m)
                d["blocheaza"] = v.get("blocheaza")
                d["verificari"] = [f"{x['nivel'][:2]} {x['cod']} {x['obiect']}: {x['mesaj']}" for x in v.get("verificari", [])]
                acc = []; walk({"intrari": m.get("intrari"), "bara": m.get("bara"), "plecari": m.get("plecari")}, acc)
                for k in m:
                    if k not in ("intrari", "bara", "plecari", "format", "cartus", "auto_format", "lista_auto", "legenda",
                                 "calc", "note", "materiale", "calc_rezumat", "carcasa"):
                        walk(m[k], acc)
                d["plansa"] = acc
                d["carcasa"] = m.get("carcasa"); d["note"] = m.get("note"); d["format"] = m.get("format")
                d["titlu"] = (m.get("cartus") or {}).get("denumire2")
                cv = layout.build(m)
                svg = render_svg.render(cv, f"r9-{fid:02d}")
                (OUT / f"f{fid:02d}.svg").write_text(svg, encoding="utf-8")
        except Exception as e:
            d["exceptie"] = f"{type(e).__name__}: {e}"; d["tb"] = traceback.format_exc()[-1500:]
        rez.append(d)
    return rez

if __name__ == "__main__":
    ids = [int(x) for x in sys.argv[1:]] or None
    rez = ruleaza(ids)
    (OUT / "brut.json").write_text(json.dumps(rez, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    for d in rez:
        print(f"\n===== #{d['id']} [{d.get('actiune')}/{d.get('tip_schema')}] {d['text'][:150]!r}")
        print("  ASTEPT:", d["asteptat"])
        if d.get("exceptie"): print("  EXC:", d["exceptie"]); print(d["tb"]); continue
        print("  IN:", json.dumps(d.get("intrare_fizica"), ensure_ascii=False, default=str))
        for q in d.get("intrebari") or []: print("  Q:", q)
        if d.get("refuz_cod"): print("  REFUZ:", d["refuz_cod"], d.get("refuz_motiv"))
        for a in d.get("avertismente") or []: print("  AV:", a)
        if d.get("neconsumat"): print("  NEC:", d["neconsumat"])
        print("  PRES:", " || ".join(d.get("presupus") or []))
        if "plansa" in d:
            print("  TITLU:", d.get("titlu"), "| FORMAT:", d.get("format"), "| BLOCHEAZA:", d.get("blocheaza"))
            print("  PL:", " ; ".join(d["plansa"]))
            print("  VER:", " ## ".join(x for x in d["verificari"] if not x.startswith("AV V32")))
