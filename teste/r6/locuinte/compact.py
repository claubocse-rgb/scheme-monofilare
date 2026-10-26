import json, sys, re
d = json.load(open(sys.argv[1]))
ids = sys.argv[2].split(",") if len(sys.argv) > 2 else None
for x in d:
    if ids and x["id"] not in ids: continue
    I = x["intrare"]; M = x.get("motor") or {}
    print(f"== {x['id']} | {x['text']}")
    print(f"   EXP {x['asteptat']}")
    al = I.get("alimentare")
    rest = {k: v for k, v in I.items() if k not in ("circuite", "tip_schema", "alimentare")}
    print(f"   -> {x['actiune']} tip={x['tip']} alim={al} {rest}")
    if I.get("circuite"):
        print("   rec:", "; ".join(f"{c['nume']}{'' if c.get('P_kW') is None else ' '+str(c['P_kW'])}{' '+c['faza'] if c.get('faza') else ''}{' L'+str(c['L_m']) if c.get('L_m') else ''}" for c in I["circuite"]))
    if x["intrebari"]: print("   ?:", [q[:150] for q in x["intrebari"]])
    if x.get("avert_interp"): print("   AVi:", [q[:150] for q in x["avert_interp"]])
    if x["refuz"][0]: print("   REFUZ:", x["refuz"])
    if M:
        q = M.get("Q") or {}
        qs = f"{q.get('tip')} {q.get('curba','')}{q.get('In_A')} {q.get('IdN_mA','')}" if q else None
        rc = M.get("RCCB") or {}
        print(f"   M: bloc={M.get('bloc')} Q={qs}{' (presupus)' if M.get('Q_presupus') else ''} RCCB={rc.get('In_A')}/{rc.get('IdN_mA')}{rc.get('tip')} col={M.get('coloana')} QG={(M.get('Q_general') or {}).get('tip')} {(M.get('Q_general') or {}).get('In_A')} SP={M.get('schema_pamant')} bil={M.get('bilant')}")
        if M.get("INV"): print(f"   INV={M['INV']} sume={M.get('sume')} PIext={M.get('PI_externa')} BESS={M.get('BESS')} racord={M.get('racord')}")
        for c in M.get("circuite", []): print("      ", c)
        if M.get("circuite_blocate"): print("   CIRC_BLOC:", M["circuite_blocate"])
    if x.get("blocant"): print("   BLOC:", [b[:200] for b in x["blocant"]])
    av = [a[:170] for a in x.get("avert") or [] if not a.startswith("V33")]
    if av: print("   AV:", av)
    if x.get("eroare_motor"): print("   ERR:", x["eroare_motor"])
