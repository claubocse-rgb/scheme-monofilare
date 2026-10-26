import sys, json, subprocess, traceback
from pathlib import Path
D = Path(__file__).parent; sys.path.insert(0, str(D.parents[2])); sys.path.insert(0, str(D))
from engine import interpretor, constructor, layout, render_svg, validare
from fraze_src import F

def rez_model(m):
    o = []
    def ap(a): return " ".join(f"{x.get('tip')}[{'/'.join(x.get('spec') or [])}]" for x in a or [])
    def walk(n, pre=""):
        if isinstance(n, dict):
            if "sursa" in n and isinstance(n["sursa"], dict): o.append(pre+"SURSA "+str(n["sursa"].get("titlu"))+" | "+str(n["sursa"].get("sub")))
            if "sarcina" in n and isinstance(n["sarcina"], dict):
                o.append(pre+"- "+str(n["sarcina"].get("titlu"))+" | "+str(n["sarcina"].get("sub"))+" || "+ap(n.get("aparate"))+" || "+str((n.get("cablu") or {}).get("text")))
            elif "aparate" in n and "sursa" in n:
                o.append(pre+"  intrare: "+ap(n.get("aparate"))+" || "+str((n.get("cablu") or {}).get("text")))
            if "eticheta" in n and isinstance(n.get("eticheta"), str): o.append(pre+"BARA "+n["eticheta"])
            for k, v in n.items():
                if k in ("calc","cartus","materiale","calc_rezumat","note","legenda","lista"): continue
                if isinstance(v,(dict,list)): walk(v, pre+("  " if k in ("plecari","copii","tablou","subtablou") else ""))
        elif isinstance(n, list):
            for x in n: walk(x, pre)
    walk(m); return o

out = {}; txt = []
sel = sys.argv[1:] or [f[0] for f in F]
for fid, stil, t, exp in F:
    if fid not in sel: continue
    rec = {"id": fid, "stil": stil, "text": t, "asteptat": exp}
    try:
        r = interpretor.interpreteaza(t, foloseste_llm=False)
        rec.update({k: r.get(k) for k in ("actiune","tip_schema","intrebari","avertismente","refuz_motiv","presupus")})
        rec["intrare_fizica"] = r.get("intrare_fizica")
        if r.get("actiune") != "refuza" and r.get("intrare_fizica"):
            c = r.get("cartus") or {}; cart = {}
            if c.get("beneficiar"): cart["beneficiar"] = c["beneficiar"]
            adr = c.get("adresa")
            if isinstance(adr, dict) and adr.get("localitate"):
                cart["adresa"] = adr["localitate"] + (f", jud. {adr['judet']}" if adr.get("judet") else "")
            for kk in ("plansa", "faza"):
                if c.get(kk): cart[kk] = c[kk]
            m, rz = constructor.genereaza(r["intrare_fizica"], cartus=cart)   # ca în app.py /api/chat
            v = validare.valideaza(m)
            rec["model_rez"] = rez_model(m)
            rec["note"] = m.get("note"); rec["validare"] = [f"{x['nivel']} {x['cod']} {x.get('obiect')}: {x['mesaj']}" for x in v["verificari"]]
            rec["blocheaza"] = v["blocheaza"]
            svg = render_svg.render(layout.build(m), fid)
            svg = svg[0] if isinstance(svg, tuple) else svg
            (D/f"{fid}.svg").write_text(svg)
    except Exception as e:
        rec["EXC"] = traceback.format_exc()[-800:]
    out[fid] = rec
    txt.append("="*100+f"\n{fid} [{stil}] {t}\nEXP: {exp}\nACT: {rec.get('actiune')} tip={rec.get('tip_schema')} bloc={rec.get('blocheaza')}")
    for k in ("intrebari","avertismente","presupus","model_rez","validare"):
        for x in rec.get(k) or []: txt.append(f"  {k[:4]}: {x}")
    if rec.get("refuz_motiv"): txt.append("  REFUZ: "+str(rec["refuz_motiv"]))
    if rec.get("EXC"): txt.append("  EXC: "+rec["EXC"])
prev = json.loads((D/"fraze.json").read_text()) if (D/"fraze.json").exists() and sys.argv[1:] else {}
prev.update(out)
(D/"fraze.json").write_text(json.dumps(prev, ensure_ascii=False, indent=1, default=str))
print("\n".join(txt))
