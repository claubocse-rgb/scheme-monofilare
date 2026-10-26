import json, re, sys, traceback
sys.path.insert(0, "/home/claude/sm")
sys.path.insert(0, "/home/claude/sm/teste/r5/fotovoltaic")
from fraze import FRAZE
from engine.interpretor import interpreteaza_local
from engine import constructor, layout, render_svg

OUT = "/home/claude/sm/teste/r5/fotovoltaic"
CHEI = {"gPV": r"gPV", "SPD_cc": r"SPD c\.c\.", "separator_cc": r"c\.c\. sub sarcin|separator", "cutie_jonctiune": r"cutie de jonc",
        "SPD_ca": r"SPD T1|SPD tip T|SPD T2", "PI": r"\bPI\b", "contor": r"kWh|[Cc]ontor", "DDR": r"DDR|IΔn|ΔI", "TG_existent": r"TG EXISTENT",
        "trafo": r"kVA · 20/0,4", "BMPT": r"BMPT", "modele": r"Huawei|Sungrow|SMA|Fronius|Growatt|Solis|LONGi|JA |Trina|Jinko|BYD|LUNA|PowerStack"}
rez_all = []
for i, f in enumerate(FRAZE, 1):
    o = {"nr": i, "fraza": f}
    try:
        r = interpreteaza_local(f)
        o.update(actiune=r["actiune"], tip=r.get("tip_schema"), intrare=r.get("intrare_fizica"), presupus=r.get("presupus"),
                 intrebari=r.get("intrebari"), refuz=r.get("refuz_motiv"), avertismente=r.get("avertismente"),
                 intelegere=r.get("intelegere"))
        if r["actiune"] != "refuza":
            m, rez = constructor.genereaza(r["intrare_fizica"])
            o["blocant"] = rez.get("blocheaza_export")
            o["verificari"] = [f'{v["nivel"][:2]} {v["cod"]} {v.get("obiect","")}: {v["mesaj"]}' for v in rez.get("verificari", [])]
            s = render_svg.render(layout.build(m))
            open(f"{OUT}/f{i:02d}.svg", "w").write(s)
            txt = " | ".join(re.findall(r">([^<>]{1,})<", s))
            o["planse_are"] = {k: bool(re.search(v, txt)) for k, v in CHEI.items()}
            o["n_INV"] = len(set(re.findall(r"\bINV-\d+\b", txt)))
            o["inv_text"] = sorted(set(re.findall(r"INV-\d+ \| ([^|]+)", txt)))
    except Exception as e:
        o["eroare"] = traceback.format_exc()[-600:]
    rez_all.append(o)
json.dump(rez_all, open(f"{OUT}/_brut.json", "w"), ensure_ascii=False, indent=1, default=str)
for o in rez_all:
    print(f'--- {o["nr"]:02d} {o["fraza"]}')
    print("  ", o.get("actiune"), o.get("tip"), json.dumps(o.get("intrare"), ensure_ascii=False, default=str)[:400])
    if o.get("refuz"): print("   REFUZ:", o["refuz"])
    if o.get("intrebari"): print("   Q:", o["intrebari"])
    if o.get("presupus"): print("   P:", "; ".join(o["presupus"])[:700])
    if o.get("verificari"): print("   V:", [v for v in o["verificari"] if not v.startswith("IN")][:6])
    if "planse_are" in o: print("   SVG:", o["n_INV"], o["inv_text"][:4], [k for k, v in o["planse_are"].items() if v], "BLOC" if o["blocant"] else "")
    if o.get("eroare"): print("   ERR", o["eroare"])
