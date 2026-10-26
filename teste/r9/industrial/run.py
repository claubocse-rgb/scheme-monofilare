# Rulare r9 industrial: python3 teste/r9/industrial/run.py [id ...]
import sys, json, pathlib, traceback
D = pathlib.Path(__file__).parent
sys.path.insert(0, str(D.parents[2]))
from engine import interpretor, constructor, layout, render_svg, validare
import cairosvg


def apar(a):
    return f"{a.get('ref','')}:{a.get('tip')}[{'; '.join(a.get('spec') or [])}]"


def walk(pl, ind=0):
    lines = []
    for p in pl or []:
        s = p.get("sarcina") or {}
        c = p.get("cablu") or {}
        lines.append("  " * ind + f"- {s.get('titlu')} | {s.get('sub')} | " + " ".join(apar(a) for a in p.get("aparate") or [])
                     + f" | {c.get('text','')}" + (" FOC" if (c.get('param') or {}).get('rezistent_foc') else ""))
        lines += walk(p.get("copii"), ind + 1)
    return lines


def run(f):
    o = {"id": f["id"]}
    r = interpretor.interpreteaza_local(f["text"])
    o.update({k: r.get(k) for k in ("actiune", "tip_schema", "intrebari", "avertismente", "refuz_cod", "refuz_motiv", "neconsumat")})
    o["presupus"] = r.get("presupus")
    o["intrare"] = r.get("intrare_fizica")
    if r.get("actiune") != "refuza" and r.get("intrare_fizica"):
        try:
            m, rez = constructor.genereaza(r["intrare_fizica"])
            v = validare.valideaza(m)
            o["blocheaza"] = v["blocheaza"]
            o["verif"] = [f"{x['cod']} {x['nivel']} {x.get('obiect','')}: {x['mesaj']}" for x in v["verificari"]
                          if x["nivel"] != "INFO" and x["cod"] not in ("V41", "V42")]
            o["intrari_m"] = [f"{(i.get('sursa') or {}).get('titlu')} / {(i.get('sursa') or {}).get('sub')} | "
                              + " ".join(apar(a) for a in i.get("aparate") or []) + f" | {(i.get('cablu') or {}).get('text','')}"
                              for i in m.get("intrari") or []]
            o["plecari_m"] = walk(m.get("plecari"))
            o["titlu"] = (m.get("cartus") or {}).get("denumire2")
            o["note"] = m.get("note")
            svg = render_svg.render(layout.build(m), "t")
            (D / f"p{f['id']:02d}.svg").write_text(svg)
            cairosvg.svg2png(bytestring=svg.encode(), write_to=str(D / f"p{f['id']:02d}.png"), output_width=2400)
            o["png"] = f"p{f['id']:02d}.png"
        except Exception as e:
            o["eroare"] = traceback.format_exc()[-800:]
    return o


if __name__ == "__main__":
    F = json.loads((D / "fraze.json").read_text())
    ids = {int(x) for x in sys.argv[1:]}
    res = [run(f) for f in F if not ids or f["id"] in ids]
    old = {}
    if ids and (D / "res.json").exists():
        old = {x["id"]: x for x in json.loads((D / "res.json").read_text())}
    for x in res: old[x["id"]] = x
    allr = [old[k] for k in sorted(old)] if old else res
    (D / "res.json").write_text(json.dumps(allr, ensure_ascii=False, indent=1, default=str))
    with open(D / "rezultate_brute.txt", "w") as fh:
        for f, o in zip([g for g in F if g["id"] in {x["id"] for x in allr}], allr):
            fh.write(f"\n===== #{o['id']} [{f['stil']}] {f['text']}\nAȘTEPTAT: {f['asteptat']}\n")
            fh.write(f"acțiune={o['actiune']} tip={o['tip_schema']} refuz={o.get('refuz_cod')} {o.get('refuz_motiv') or ''}\n")
            for k in ("intrebari", "avertismente", "neconsumat"):
                if o.get(k): fh.write(f"{k}: {json.dumps(o[k], ensure_ascii=False)}\n")
            fh.write("intrare: " + json.dumps(o.get("intrare"), ensure_ascii=False) + "\n")
            fh.write("presupus:\n  " + "\n  ".join(o.get("presupus") or []) + "\n")
            if "intrari_m" in o:
                fh.write(f"titlu={o.get('titlu')} BLOCHEAZĂ={o['blocheaza']}\nINTRĂRI:\n  " + "\n  ".join(o["intrari_m"]) +
                         "\nPLECĂRI:\n  " + "\n  ".join(o["plecari_m"]) + "\nVERIF:\n  " + "\n  ".join(o["verif"]) + "\n")
            if o.get("eroare"): fh.write("EROARE: " + o["eroare"] + "\n")
    print("ok", len(res))
