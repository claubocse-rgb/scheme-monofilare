import sys, json, re
sys.path.insert(0, "/home/claude/sm"); sys.path.insert(0, "/home/claude/sm/teste/r5/locuinte"); sys.path.insert(0, "/home/claude/sm/teste/r6/locuinte")
from engine.interpretor import interpreteaza_local
from engine import constructor, validare
from fraze_in import F
from fraze_noi import N
which = sys.argv[1] if len(sys.argv) > 1 else "all"
LIST = (F if which in ("all", "r5") else []) + (N if which in ("all", "noi") else [])

def cart_of(r):
    cart = {}; c = r.get("cartus") or {}
    if c.get("beneficiar"): cart["beneficiar"] = c["beneficiar"]
    adr = c.get("adresa")
    if isinstance(adr, dict) and adr.get("localitate"):
        cart["adresa"] = adr["localitate"] + (f", jud. {adr['judet']}" if adr.get("judet") else "")
    return cart

def circ(R):
    out = []
    for gr in R.get("grupe_DDR") or []:
        for c in gr.get("circuite", []):
            p = c.get("protectie", {})
            out.append(f"{c.get('nume')}[{c.get('faza')}] {c.get('P_kW')}kW {p.get('tip')} {p.get('curba')}{p.get('In_A')} {c.get('cablu')} L{c.get('L_m')} dU{round(c.get('dU_cumulat_pct') or 0,1)} DDR{gr['DDR'].get('IdN_mA')}{gr['DDR'].get('tip')}{gr['DDR'].get('aparat','')}")
    for c in R.get("circuite_fara_ddr") or []:
        out.append("FARA DDR: " + str(c.get("nume")))
    return out

res = []
for fid, text, exp in LIST:
    r = interpreteaza_local(text); I = r.get("intrare_fizica") or {}
    rec = {"id": fid, "text": text, "asteptat": exp, "actiune": r["actiune"], "tip": r.get("tip_schema"),
           "retea": I.get("retea"), "intelegere": r.get("intelegere"), "presupus": r.get("presupus"),
           "intrebari": r.get("intrebari"), "avert_interp": r.get("avertismente"),
           "refuz": [r.get("refuz_cod"), r.get("refuz_motiv")], "intrare": I}
    if r["actiune"] != "refuza" and I:
        try:
            m, rez = constructor.genereaza(I, cartus=cart_of(r)); R = rez["rezultat"]
            v = validare.valideaza(m)
            rec["blocant"] = [x["cod"] + ": " + x.get("mesaj", "")[:200] for x in rez["verificari"] if x.get("nivel") == "BLOCANT"]
            rec["avert"] = [x["cod"] + ": " + x.get("mesaj", "")[:160] for x in rez["verificari"] if x.get("nivel") == "AVERTISMENT"]
            s = {}
            if "bloc" in R: s.update(bloc=R.get("bloc"), Q=R.get("Q"), Ib=R.get("Ib_A"), RCCB=R.get("RCCB"), SF=R.get("SF"))
            A = R.get("alimentare")
            if isinstance(A, dict): s.update(bloc=A.get("bloc"), Q=A.get("Q"), Ib=A.get("Ib_A"), RCCB=A.get("RCCB"), Q_presupus=A.get("Q_presupus"))
            for k in ("C2", "coloana"):
                if isinstance(R.get(k), dict):
                    c = R[k]; s["coloana"] = (c.get("cablu"), c.get("L_m"), (c.get("protectie") or {}).get("In_A"), round(c.get("dU_cumulat_pct") or 0, 2))
            if R.get("Q_general"): s["Q_general"] = R["Q_general"]
            if R.get("SPD"): s["SPD"] = R["SPD"]
            if R.get("invertoare"):
                s["INV"] = [(x.get("Pn_kW"), x.get("cablu"), x.get("L_m"), x.get("protectie"), x.get("DDR"), round(x.get("dU_cumulat_pct") or 0, 2)) for x in R["invertoare"]]
                s["sume"] = R.get("sume"); s["PI_externa"] = R.get("PI_externa"); s["PI"] = R.get("PI"); s["BESS"] = R.get("BESS"); s["racord"] = R.get("racord")
            if R.get("bilant"): s["bilant"] = {k: R["bilant"].get(k) for k in ("Pi_kW", "Pc_kW", "ks", "Ib_A", "Ib_baza", "P_aprobata_kW")}
            s["schema_pamant"] = R.get("schema_pamant"); s["circuite"] = circ(R); s["chei"] = list(R.keys())
            if R.get("circuite_blocate"): s["circuite_blocate"] = R["circuite_blocate"]
            rec["motor"] = s
            rec["validare"] = v if isinstance(v, (dict, list)) else str(v)
            txt = json.dumps(m, ensure_ascii=False, default=str)
            rec["model_contine"] = {k: bool(re.search(p, txt, re.I)) for k, p in
                {"anti_insular": "insular", "releu_PI": r"\bPI\b|interfa", "BAT": r"BAT|baterie|acumulator", "SPD": "SPD", "BPE": "BPE", "contor": "contor|kWh"}.items()}
        except Exception as e:
            import traceback; rec["eroare_motor"] = traceback.format_exc()[-600:]
    res.append(rec)
json.dump(res, open(f"/home/claude/sm/teste/r6/locuinte/raw_{which}.json", "w"), ensure_ascii=False, indent=1, default=str)

for x in res:
    print("=====", x["id"], x["text"]); print("  EXP:", x["asteptat"])
    print("  act:", x["actiune"], "| tip:", x["tip"], "| retea:", x["retea"], "| refuz:", x["refuz"])
    I = {k: v for k, v in x["intrare"].items() if k != "circuite"}; print("  I:", I)
    if x["intrare"].get("circuite"): print("  circ_in:", [(c["nume"], c.get("P_kW"), c.get("L_m"), c.get("faza"), c.get("n")) for c in x["intrare"]["circuite"]])
    print("  Q?:", x["intrebari"]); 
    if x["avert_interp"]: print("  AVi:", x["avert_interp"])
    print("  pres:", [p[:90] for p in x["presupus"] or [] if not re.search("Ik3max OD|beneficiar și|DDR 30 mA pe|ks după|puterile și lung|virgul", p)])
    if x.get("motor"):
        M = x["motor"]; print("  M:", {k: v for k, v in M.items() if k not in ("circuite", "chei")})
        for c in M["circuite"]: print("     ", c)
        print("  has:", x.get("model_contine"))
    print("  BLOC:", x.get("blocant"), x.get("eroare_motor", ""))
    print("  AV:", [a[:140] for a in x.get("avert") or [] if not a.startswith("V33")])
