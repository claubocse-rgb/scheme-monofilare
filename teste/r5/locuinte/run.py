import sys, json, traceback, re
sys.path.insert(0, "/home/claude/sm"); sys.path.insert(0, "/home/claude/sm/teste/r5/locuinte")
from engine.interpretor import interpreteaza_local
from engine import constructor
from fraze_in import F

def g(d, *ks):
    for k in ks:
        if not isinstance(d, dict): return None
        d = d.get(k)
    return d

out = []
for fid, text, exp in F:
    r = interpreteaza_local(text)
    I = r.get("intrare_fizica") or {}
    rec = {"id": fid, "text": text, "asteptat": exp, "actiune": r["actiune"], "tip": r.get("tip_schema"),
           "retea": I.get("retea"), "intelegere": r.get("intelegere"), "presupus": r.get("presupus"),
           "intrebari": r.get("intrebari"), "refuz": [r.get("refuz_cod"), r.get("refuz_motiv")], "intrare": I}
    if r["actiune"] != "refuza":
        try:
            m, rez = constructor.genereaza(I)
            R = rez["rezultat"]
            rec["blocant"] = [v["cod"]+": "+v.get("mesaj","")[:160] for v in rez["verificari"] if v.get("nivel")=="BLOCANT"]
            rec["avert"] = [v["cod"]+": "+v.get("mesaj","")[:120] for v in rez["verificari"] if v.get("nivel")=="AVERTISMENT"]
            s = {}
            if "bloc" in R: s["bloc"]=R.get("bloc"); s["Q"]=R.get("Q"); s["Ib_alim"]=R.get("Ib_A"); s["RCCB"]=R.get("RCCB")
            if isinstance(R.get("C2"), dict): s["coloana"]=(R["C2"].get("cablu"), R["C2"].get("L_m"), R["C2"].get("protectie",{}).get("In_A"), round(R["C2"].get("dU_cumulat_pct") or 0,2))
            if isinstance(R.get("INV"), dict): s["INV"]=(R["INV"].get("cablu"), R["INV"].get("L_m"), R["INV"].get("protectie"), R["INV"].get("DDR"), round(R["INV"].get("dU_cumulat_pct") or 0,2)); s["Iac"]=R.get("Iac_max_A")
            if "alimentare" in R and isinstance(R["alimentare"], dict):
                A = R["alimentare"]; s["bloc"] = A.get("bloc"); s["Q"] = A.get("Q"); s["Ib_alim"] = A.get("Ib_A")
            if isinstance(R.get("coloana"), dict):
                s["coloana"] = (R["coloana"].get("cablu"), R["coloana"].get("L_m"), R["coloana"].get("protectie",{}).get("In_A"), round(R["coloana"].get("dU_cumulat_pct") or 0,2))
            if R.get("bilant"): s["bilant"] = {k: R["bilant"].get(k) for k in ("Pi_kW","Pc_kW","ks","Ib_A","P_aprobata_kW")}
            if R.get("schema_pamant"): s["schema_pamant"] = R.get("schema_pamant")
            cir = []
            for gr in R.get("grupe_DDR") or []:
                for c in gr.get("circuite", []):
                    p = c.get("protectie", {})
                    cir.append(f"{c.get('nume')}[{c.get('faza')}] {c.get('P_kW')}kW {p.get('tip')} {p.get('curba')}{p.get('In_A')} {c.get('cablu')} L{c.get('L_m')} dU{round(c.get('dU_cumulat_pct') or 0,1)} DDR{gr['DDR'].get('IdN_mA')}{gr['DDR'].get('tip')}")
            for c in R.get("circuite_fara_ddr") or []:
                cir.append("FARA DDR: "+str(c.get("nume")))
            s["circuite"] = cir
            s["chei"] = list(R.keys())
            rec["motor"] = s
        except Exception as e:
            rec["eroare_motor"] = repr(e)[:300]
    out.append(rec)
json.dump(out, open("/home/claude/sm/teste/r5/locuinte/fraze_raw.json","w"), ensure_ascii=False, indent=1, default=str)
for x in out:
    print("=====", x["id"], x["text"])
    print(" act:", x["actiune"], "| tip:", x["tip"], "| retea:", x["retea"], "| refuz:", x["refuz"])
    I = x["intrare"]
    print(" alim:", I.get("alimentare"), "| SP:", I.get("schema_pamant"), I.get("RA_ohm"), "| ks", I.get("ks"))
    for k in ("invertoare","bess","P_aprobata_kW","Ib_A","S_kVA","L_coloana_m","bmpt_fortat","masura_ceruta","lungimi_m","P_kW"):
        if k in I: print("  ", k, I[k])
    if I.get("circuite"): print(" circ:", [(c["nume"], c.get("P_kW"), c.get("L_m"), c.get("faza")) for c in I["circuite"]])
    print(" Q?:", x["intrebari"])
    print(" pres:", [p[:70] for p in x["presupus"] or [] if not re.search("Ik3max OD|beneficiar și|DDR 30 mA pe|ks după|puterile și lung|virgul",p)])
    if x.get("motor"):
        M = x["motor"]; print(" M:", {k:v for k,v in M.items() if k not in ("circuite","chei")})
        for c in M["circuite"]: print("    ", c)
    print(" BLOC:", x.get("blocant"), x.get("eroare_motor",""))
    print(" AV:", [a[:90] for a in x.get("avert") or [] if not a.startswith("V33")])
