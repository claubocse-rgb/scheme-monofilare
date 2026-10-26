import json, re, sys, traceback, importlib
sys.path.insert(0, "/home/claude/sm")
from engine.interpretor import interpreteaza_local
from engine import constructor, layout, render_svg

OUT = "/home/claude/sm/teste/r6/fotovoltaic"
CHEI = {"gPV": r"gPV", "SPD_cc": r"SPD c\.c\.", "separator_cc": r"c\.c\. sub sarcin|separator|[Ss]ep\. c\.c", "cutie_jonctiune": r"cutie de jonc",
        "SPD_ca": r"SPD T1|SPD tip T|SPD T2|SPD", "PI": r"\bPI\b", "contor": r"kWh|[Cc]ontor", "DDR": r"DDR|IΔn|ΔI", "TG_existent": r"TG EXISTENT|EXISTENT",
        "trafo": r"kVA · 20/0,4|20/0,4", "BMPT": r"BMPT", "BESS": r"BESS|PCS|BAT", "analizor": r"[Aa]nalizor|Smart Dongle|Power Manager|EMS|limitare|injec",
        "modele": r"Huawei|Sungrow|SMA|Fronius|Growatt|Solis|LONGi|JA |Trina|Jinko|BYD|LUNA|PowerStack|SUN2000|SG\d|STP|Tauro|MAX"}
def ruleaza(fraze, prefix, png=()):
    rez_all = []
    for i, f in enumerate(fraze, 1):
        o = {"nr": i, "fraza": f}
        try:
            r = interpreteaza_local(f)
            o.update(actiune=r["actiune"], tip=r.get("tip_schema"), intrare=r.get("intrare_fizica"), presupus=r.get("presupus"),
                     intrebari=r.get("intrebari"), refuz=r.get("refuz_motiv"), avertismente=r.get("avertismente"))
            if r["actiune"] != "refuza" and r.get("intrare_fizica"):
                m, rez = constructor.genereaza(r["intrare_fizica"])
                o["blocant"] = rez.get("blocheaza_export")
                o["verificari"] = [f'{v["nivel"][:2]} {v["cod"]} {v.get("obiect","")}: {v["mesaj"]}' for v in rez.get("verificari", [])]
                s = render_svg.render(layout.build(m), f"{prefix}{i:02d}")
                fn = f"{OUT}/{prefix}{i:02d}.svg"
                open(fn, "w").write(s)
                if i in png:
                    import cairosvg; cairosvg.svg2png(url=fn, write_to=fn[:-4]+".png", output_width=2400, background_color="white")
                txt = " | ".join(t.strip() for t in re.findall(r">([^<>]{1,})<", s) if t.strip())
                o["planse_are"] = {k: bool(re.search(v, txt)) for k, v in CHEI.items()}
                o["n_INV"] = len(set(re.findall(r"\bINV-\d+\b", txt)))
                o["n_gPV"] = len(re.findall(r"gPV", txt))
                o["txt"] = txt[:6000]
        except Exception as e:
            o["eroare"] = traceback.format_exc()[-800:]
        rez_all.append(o)
    json.dump(rez_all, open(f"{OUT}/_brut_{prefix}.json", "w"), ensure_ascii=False, indent=1, default=str)
    for o in rez_all:
        print(f'=== {prefix}{o["nr"]:02d} {o["fraza"]}')
        print("  ", o.get("actiune"), o.get("tip"), json.dumps(o.get("intrare"), ensure_ascii=False, default=str)[:900])
        if o.get("refuz"): print("   REFUZ:", o["refuz"])
        if o.get("intrebari"): print("   Q:", o["intrebari"])
        if o.get("avertismente"): print("   AV:", o["avertismente"])
        if o.get("presupus"): print("   P:", " ;; ".join(o["presupus"])[:900])
        if o.get("verificari"): print("   V:", [v[:110] for v in o["verificari"] if not v.startswith("IN")][:6])
        if "planse_are" in o: print("   SVG: nINV", o["n_INV"], "gPV", o["n_gPV"], [k for k, v in o["planse_are"].items() if v], "BLOC" if o["blocant"] else "")
        if o.get("eroare"): print("   ERR", o["eroare"])
