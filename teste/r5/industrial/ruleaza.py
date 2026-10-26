import sys, json, traceback
sys.path.insert(0, "/home/claude/sm"); sys.path.insert(0, "/home/claude/sm/teste/r5/industrial")
from engine.interpretor import interpreteaza_local
from engine import constructor, validare, layout, render_svg
from fraze_in import F
out = []
for i, (t, exp) in enumerate(F, 1):
    rec = {"nr": i, "fraza": t, "asteptat": exp}
    try:
        r = interpreteaza_local(t)
        rec.update(actiune=r["actiune"], tip=r["tip_schema"], refuz=r.get("refuz_cod"), refuz_motiv=r.get("refuz_motiv"),
                   intrare=r["intrare_fizica"], intrebari=r["intrebari"], presupus=r["presupus"], intelegere=r["intelegere"],
                   avert=r.get("avertismente"))
        if r["actiune"] != "refuza":
            m, rez = constructor.genereaza(r["intrare_fizica"], cartus=r.get("cartus"))
            ver = rez.get("verificari") or []
            rec["blocant"] = [f'{v["cod"]} {v.get("obiect","")}: {v["mesaj"]}' for v in ver if v.get("nivel") == "BLOCANT"]
            rec["avertisment"] = [f'{v["cod"]} {v.get("obiect","")}: {v["mesaj"]}' for v in ver if v.get("nivel") == "AVERTISMENT"]
            rec["blocheaza_export"] = rez.get("blocheaza_export")
            # summary of drawn plecari
            def pl(p, d=0):
                s = []
                for x in p.get("plecari", []) or []:
                    ap = [ (a.get("tip"), a.get("text") or a.get("eticheta") or a.get("calibru")) for a in (x.get("aparate") or [])]
                    s.append({"nume": x.get("nume") or x.get("eticheta"), "cablu": x.get("cablu"), "aparate": ap})
                return s
            rec["model_intrari"] = [ {k: v for k, v in x.items() if k in ("nume","eticheta","tip","cablu")} for x in m.get("intrari", [])]
            rec["model_plecari"] = pl(m)
            try:
                svg = render_svg.render(layout.build(m))
                open(f"/home/claude/sm/teste/r5/industrial/svg/f{i:02d}.svg", "w").write(svg)
            except Exception as e:
                rec["render_err"] = repr(e)
    except Exception as e:
        rec["exceptie"] = traceback.format_exc()[-600:]
    out.append(rec)
json.dump(out, open("/home/claude/sm/teste/r5/industrial/brut.json", "w"), ensure_ascii=False, indent=1, default=str)
for r in out:
    print(f'#{r["nr"]:02d} {r.get("actiune")} tip={r.get("tip")} ref={r.get("refuz")} BLK={len(r.get("blocant") or [])} AV={len(r.get("avertisment") or [])} {"EXC" if "exceptie" in r else ""}')
