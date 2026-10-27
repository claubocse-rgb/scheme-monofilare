"""Reverificarea rundei 11 (teste/r11/{locuinte,fotovoltaic,industrial}) + rundele 5–10 după reparațiile r11 ale
INTERPRETORULUI LOCAL (regulile + dicționarul central de sinonime, fără Claude).

Pentru fiecare frază r11 P0 / P1 (și P2 din clasele reparate) se aplică o listă de verificări scrisă din „așteptat” +
observația testerului (nu din ce face codul). Restul frazelor sunt păzite de plasa de siguranță și de regula „nimic
blocat fără întrebare”.
  * „tester” — verdictul testerului r11 (tabelul din locuinte.md, fraze.json la fotovoltaic, lista P0/P1 la industrial);
  * „după”   — `interpretor.interpreteaza(text)` (calea aplicației fără cheie API) cu codul curent.
O frază e „corectă” dacă trec toate verificările, „parțială” dacă trece cel puțin jumătate, altfel „greșită”.

Rulare: cd /home/claude/sm && python3 teste/r11/reverificare.py [-v] [--fara-vechi]
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

RAD = Path(__file__).resolve().parents[2]
R11 = RAD / "teste" / "r11"
sys.path.insert(0, str(RAD))

_spec = importlib.util.spec_from_file_location("reverificare_r10", RAD / "teste" / "r10" / "reverificare.py")
r10 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r10)
r8 = r10.r8

_f, C, evalueaza, plasa_ok = r8._f, r8.C, r8.evalueaza, r8.plasa_ok
I, inv, pl, apx, n_sum = r8.I, r8.inv, r8.pl, r8.apx, r8.n_sum
PA = r8.PA
eq, RET, SP, INV, PN, REC, NREC, KWH, INTREABA, FARA_Q, NU_REFUZ, NP = (
    r8.eq, r8.RET, r8.SP, r8.INV, r8.PN, r8.REC, r8.NREC, r8.KWH, r8.INTREABA, r8.FARA_Q, r8.NU_REFUZ, r8.NP)
INTREABA_ORI_REFUZ, FARA_NEC = r8.INTREABA_ORI_REFUZ, r8.FARA_NEC
L, T, PR, CEF, PT, GE = r8.L, r8.T, r8.PR, r8.CEF, r8.PT, r8.GE
QB, CU_Q, NU_TIP, EXIST, NOU, CNT, TOATE_REC, BLOC_INTREBAT, al = (r10.QB, r10.CU_Q, r10.NU_TIP, r10.EXIST, r10.NOU, r10.CNT,
                                                                   r10.TOATE_REC, r10.BLOC_INTREBAT, r10.al)
NU_CONTRAD = r10.NU_CONTRAD
rezultat = r10.rezultat
_g = r10._g


def DEDUS(k="retea"):
    return (f"„{k}” marcat dedus (_deduse)", lambda c: k in (I(c).get("_deduse") or []) and k in (c["r"].get("_deduse") or []))


def PL_NUME(*cuv):
    return ("plecare „" + "/".join(cuv) + "”", lambda c: any(all(w in _f(p.get("nume")) for w in cuv) for p in pl(c)))


def NU_NUME(*cuv):
    return ("fără elementul-fantomă „" + "/".join(cuv) + "”", lambda c: not any(
        any(w in _f(x.get("nume")) for w in cuv) for x in list(pl(c)) + list(TOATE_REC(c)) + list(I(c).get("consumatori") or [])))


def CONS(nume, **kv):
    return (f"consumator {nume} {kv}", lambda c: any(nume in _f(x.get("nume")) and all(x.get(k) == v for k, v in kv.items())
                                                       for x in I(c).get("consumatori") or []))


def ILUM(n):
    return CNT("iluminat", n)


VE = "vehicul_electric"
REFUZ = ("refuză (cu întrebare)", lambda c: c["r"]["actiune"] == "refuza" and bool(c["r"]["intrebari"]))

LOC = {
    3: [L, RET("tri"), QB(25), ILUM(6), CNT("prize", 8)],
    5: [RET("tri"), NU_REFUZ, NU_CONTRAD, ("Q 25 A", lambda c: 25 in (al(c).get("In_Q_bransament_A"), I(c).get("Q_In_A")))],
    9: [L, RET("mono"), QB(40), NU_REFUZ, ILUM(4), CNT("prize", 6)],
    12: [L, RET("tri"), ILUM(8), CNT("prize", 10)],
    14: [L, RET("tri"), NU_REFUZ, NU_NUME("trifazat cu", "monofazat cu"), ("TE garaj: VE 11 kW", lambda c: any(
        any(x.get("P_kW") == 11 for x in t.get("circuite") or []) for t in I(c).get("tablouri_secundare") or []))],
    19: [L, RET("mono"), ILUM(3), CNT("prize", 4)],
    20: [L, RET("tri"), QB(25), ILUM(4), CNT("prize", 6)],
    21: [L, RET("mono"), ILUM(3), CNT("prize", 4)],
    25: [L, RET("mono"), ILUM(4), CNT("prize", 5)],
    28: [T, NU_REFUZ, PL_NUME("priz"), PL_NUME("ilumin"), PL_NUME("ac"), eq("In_Q1_A", 32), NU_NUME("adauga", "neschimbat")],
    29: [L, RET("mono"), QB(32), PA(7), CNT("prize", 5), ILUM(3), REC("boiler", P=2),
         ("prizele fără „3 kW”", lambda c: not any(x.get("receptor") == "prize" and x.get("P_kW") == 3 for x in TOATE_REC(c)))],
    30: [L, RET("mono"), ILUM(4), CNT("prize", 6)],
    34: [L, RET("tri"), NU_REFUZ, NU_CONTRAD, ("strung 4 kW trifazat", lambda c: any(
        "strung" in _f(x.get("nume")) and x.get("faza") == "3F" for x in TOATE_REC(c))),
         ("sudură 6 kVA monofazată", lambda c: any("sudur" in _f(x.get("nume")) and x.get("faza") in ("L1", "L2", "L3")
                                                  for x in TOATE_REC(c)))],
    35: [L, ILUM(3), CNT("prize", 5)],
    36: [L, SP("TT"), ILUM(4), CNT("prize", 6)],
    40: [L, RET("mono"), NU_NUME("monofazat cu"), ("TD anexă 80 m, 3 kW", lambda c: any(
        t.get("L_m") == 80 for t in I(c).get("tablouri_secundare") or []))],
    41: [L, RET("tri"), ("circuit CEE 32 A trifazat", lambda c: any(x.get("In_A") == 32 and x.get("faza") == "3F"
                                                                  for x in TOATE_REC(c))), ILUM(5), CNT("prize", 7)],
    42: [L, ILUM(4), CNT("prize", 5)],
    45: [T, NU_REFUZ, eq("origine", "tg_existent"), RET("mono"), ("fără branșament / BMPM", lambda c: not I(c).get("alimentare")),
         PL_NUME("priz"), PL_NUME("ilumin"), PL_NUME("boiler")],
    48: [L, RET("tri"), ILUM(4), CNT("prize", 6)],
    49: [L, RET("mono"), ILUM(4), CNT("prize", 6)],
    52: [L, RET("mono"), ("6 prize C25 cu 2,5 mm²", lambda c: len([x for x in TOATE_REC(c) if x.get("receptor") == "prize"
                                                                  and x.get("In_A") == 25 and _g(x, "cablu.S_fortat") == 2.5]) == 6),
         ("2,5 mm² NU e pe coloană", lambda c: _g(al(c), "cablu.S_fortat") != 2.5), ILUM(3)],
    53: [L, ILUM(3), CNT("prize", 4)],
    56: [L, ILUM(6), CNT("prize", 8)],
    58: [PR, PN(10), ("GE 8 kVA nu e invertor", lambda c: not any(g.get("Pn_kW") == 8 for g in I(c).get("invertoare") or [])),
         NU_CONTRAD, QB(25)],
    59: [L, ILUM(3), CNT("prize", 4), REC("aer_conditionat", P=2.5)],
    61: [L, RET("mono"), CU_Q("apartamente")],
    62: [L, ILUM(4), CNT("prize", 4)],
    63: [L, RET("tri"), ILUM(6), CNT("prize", 8), REC(VE, P=7.4)],
    65: [L, ILUM(4), CNT("prize", 6)],
    66: [L, RET("mono"), ("pompa 1,5 kW la 120 m", lambda c: any(x.get("receptor") == "pompa_apa" and x.get("P_kW") == 1.5
                                                                and x.get("L_m") == 120 for x in TOATE_REC(c))),
         ("120 m nu e pe coloană", lambda c: al(c).get("L_coloana_m") != 120), ILUM(3), CNT("prize", 5)],
    7: [PR, QB(25)],
    6: [PR, RET("mono"), QB(32)],
    17: [PR, QB(32)],
    26: [PR, QB(50)],
}

PV = {
    2: [CEF, INV((1, 110)), ("cablul solar = c.c. (nu C0)", lambda c: _g(I(c), "cablu_cc.S_fortat") == 6
                             and not _g(I(c), "cablu_C0.S_fortat") and I(c).get("L_racord_m") != 1500)],
    4: [CEF, INV((2, 110)), eq("pt_existent", True), eq("masura", "MT"), eq("limitare_injectie_kW", 0),
        ("model fără „?”", lambda c: all("?" not in (g.get("model") or "") for g in I(c).get("invertoare") or []))],
    9: [PR, DEDUS()],
    11: [PR, KWH(10.24), SP("TT"), QB(32)],
    15: [CEF, INV((4, 320)), NU_REFUZ],
    16: [PR, ("model curat SUN2000-5KTL-L1", lambda c: all(g.get("model") == "SUN2000-5KTL-L1" for g in I(c).get("invertoare") or []))],
    19: [CEF, INV((3, 25), (1, 110)), EXIST(25, 3), NOU(110, 1), NU_REFUZ, eq("limitare_injectie_kW", 0)],
    20: [CEF, INV((2, 100), (1, 110)), PN(310)],
    24: [CEF, INV((2, 50)), eq("string.n_module", 20), eq("string.n_stringuri_paralel", 12),
         ("kWp = 109,2", lambda c: apx(I(c).get("kWp"), 109.2, 0.001))],
    31: [CU_Q("zero", "100")],
    32: [INTREABA_ORI_REFUZ, ("întrebarea BMPT / PT", lambda c: "bmpt" in _f(r10.Q(c)) and "pt" in _f(r10.Q(c))), INV((3, 50))],
    33: [INTREABA("trifazat", "monofazat")],
    43: [CEF, INV((2, 30)), ("cablu invertor CYY-F 5×16, 25 m", lambda c: _g(I(c), "cablu_inv.S_fortat") == 16 and I(c).get("L_inv_m") == 25),
         ("C0 fără cablul invertorului", lambda c: not _g(I(c), "cablu_C0.S_fortat"))],
    44: [CEF, PN(300), eq("n_tgd_cf", 2), ("câte 3 pe TGD-CF", lambda c: sorted(
        g.get("tgd") for g in I(c).get("invertoare") or [] for _ in range(int(g.get("n", 1)))) == [1, 1, 1, 2, 2, 2])],
    45: [CEF, INV((4, 115)), eq("limitare_injectie_kW", 400), NU_REFUZ, eq("pt_existent", True)],
    46: [NU_REFUZ, ("BMPT 125 A (nu TG)", lambda c: (I(c).get("racord") == "bmpt" or I(c).get("origine") == "bmpt")
                                                  and 125 in (I(c).get("In_Q_bransament_A"), I(c).get("racord_In_Q_A")))],
    48: [PR, RET("mono"), ("fără fază (instalație monofazată)", lambda c: not any(g.get("faza") for g in I(c).get("invertoare") or []))],
    53: [CEF, eq("Ik3_OD_kA", 18), eq("Zb_OD_ohm", 0.05), ("0,05 Ω nu e RA", lambda c: I(c).get("RA_ohm") != 0.05)],
    59: [("BESS fără câmp PV", lambda c: _g(I(c), "bess.kWh") == 30 and not I(c).get("invertoare") and not I(c).get("kWp")),
         ("PCS = hibridul 12 kW", lambda c: _g(I(c), "bess.P_kW") == 12)],
    62: [CEF, INV((3, 50)), ("kWp = 330 × 545 W", lambda c: apx(I(c).get("kWp"), 179.85, 0.001)), eq("pt_existent", True)],
    66: [CEF, INV((3, 100), (2, 100)), EXIST(100, 2), NOU(100, 3), eq("pt_existent", True), eq("pt_Sn_kVA", 630)],
}

IND = {
    5: [PT, eq("n_trafo", 2), eq("aar", True), eq("cupla", "deschisa"), ("fără GE inventat", lambda c: not I(c).get("Sn_GE_kVA")),
        eq("Sn_kVA", 800)],
    6: [PT, eq("compensare_kvar", 600), eq("n_trafo", 2)],
    8: [GE, NU_REFUZ, eq("P_sarcina_kW", 64), CONS("hvac", vital=False), CONS("rafturi", vital=False), CONS("servere", vital=True),
        eq("bara_vitala", True)],
    10: [GE, eq("fara_retea", True), CONS("pompe", n="1+1"), FARA_NEC],
    15: [T, ("UPS 60 kVA cu bypass și 6 rack-uri pe faze", lambda c: any(
        p.get("receptor") == "ups" and p.get("Sn_kVA") == 60 and p.get("bypass") and len(p.get("copii") or []) == 6
        and sorted({x.get("faza") for x in p["copii"]}) == ["L1", "L2", "L3"] for p in pl(c)))],
    18: [T, eq("origine", "tg_existent"), ("motor 45 kW, 110 m, 4×25", lambda c: any(
        p.get("P_kW") == 45 and p.get("L_m") == 110 and _g(p, "cablu.S_fortat") == 25 for p in pl(c)))],
    20: [T, RET("mono"), ("3 iluminat + 4 prize", lambda c: n_sum([p for p in pl(c) if "ilumin" in _f(p.get("nume"))]) == 3
                         and n_sum([p for p in pl(c) if "priz" in _f(p.get("nume"))]) == 4)],
    21: [T, eq("origine", "pt_propriu"), PL_NUME("compresor"), ("compresor 75 kW", lambda c: any(p.get("P_kW") == 75 for p in pl(c))),
         NU_NUME("pt"), NU_REFUZ],
    23: [T, SP("TN-C-S"), NU_REFUZ, eq("origine", "bmpt")],
    24: [T, eq("P_kW", 273), NP(8)],
    25: [T, eq("ks", 0.75)],
    29: [PT, eq("aar", True), ("fără GE / întrebare de GE", lambda c: not I(c).get("Sn_GE_kVA") and "ge" not in _f(r10.Q(c)).split())],
    30: [GE, eq("P_sarcina_kW", 103), CONS("hvac", vital=False), CONS("pompa incendiu", vital=True), eq("bara_vitala", True)],
    33: [T, ("UPS 200 kVA (nu PT)", lambda c: any(p.get("receptor") == "ups" and p.get("Sn_kVA") == 200 for p in pl(c))),
         ("fără PT inventat", lambda c: not I(c).get("Sn_kVA") and not I(c).get("pt_Sn_kVA")), CU_Q("1+1")],
    37: [T, ("10 iluminat × 1 kW", lambda c: n_sum([p for p in pl(c) if "ilumin" in _f(p.get("nume")) and p.get("P_kW") == 1]) == 10),
         NU_NUME("fa-mi"), DEDUS()],
    36: [T, DEDUS(), DEDUS("origine")],
    38: [T, eq("origine", "pt_propriu"), ("TD-P1 60 m / TD-P2 85 m / TD-Tehnic 20 m", lambda c: sorted(
        p.get("L_m") for p in I(c).get("plecari") or []) == [20, 60, 85]), FARA_NEC],
    39: [T, ("TD1 → TD1.1 + TD1.2", lambda c: any(p.get("nume") == "TD1" and sorted(k["nume"] for k in p.get("copii") or [])
                                                   == ["TD1.1", "TD1.2"] for p in I(c).get("plecari") or [])), FARA_NEC],
    40: [PT, NP(6), eq("masura", "JT")],
    41: [PT, eq("uk_pct", 4.5), eq("grupa_conexiuni", "Dyn11")],
    44: [T, NU_REFUZ, eq("origine", "pt_propriu"), ("2 active + 1 rezervă", lambda c: len(pl(c)) == 3
                                                    and sum(1 for p in pl(c) if p.get("rezerva")) == 1)],
    45: [GE, eq("fara_retea", True), ("fără rețea inventată", lambda c: not I(c).get("sursa_retea")), CU_Q("direct")],
    46: [NP(6), ("6 × 22 kW", lambda c: n_sum([p for p in pl(c) if p.get("P_kW") == 22]) == 6)],
    52: [T, ("2 × 150 kW", lambda c: sorted(p.get("P_kW") for p in pl(c)) == [150, 150])],
    53: [T, NP(17), PL_NUME("iluminat hala"), PL_NUME("td laborator")],
    55: [T, eq("origine", "bmpt"), NU_NUME("contor", "bmpt"), SP("TN-C-S"), RET("tri")],
    57: [REFUZ, ("fără GE de 2000 kVA", lambda c: c["r"]["actiune"] == "refuza")],
    58: [T, NU_REFUZ, NP(5), ("faze pe circuite", lambda c: sorted(p.get("retea") for p in pl(c)) == ["mono"] * 4 + ["tri"]),
         ("L pe circuite", lambda c: sorted(p.get("L_m") for p in pl(c)) == [10, 15, 20, 30, 35])],
    62: [T, NU_REFUZ, eq("origine", "tg_existent")],
}

IND_PRIO = {**{k: "P0" for k in (5, 8, 30, 33, 41, 45, 46, 55, 57)},
            **{k: "P1" for k in (38, 39, 44, 62, 52, 53, 58, 40, 32, 37, 20, 10, 15, 18, 16, 6, 61, 64, 3, 17, 26, 28, 51, 49,
                                 9, 25, 24, 21, 29, 56, 36, 1, 60, 23)}}


def _v(v):
    v = _f(v)
    return "corect" if v.startswith("c") else "partial" if v.startswith("p") else "gresit" if v.startswith("g") else "-"


def _tabel_loc():
    out = {}
    txt = (R11 / "locuinte.md").read_text(encoding="utf-8")
    txt = txt[txt.index("## Tabel pe fraze"):]
    for linie in txt.splitlines():
        cel = [x.strip() for x in linie.strip().strip("|").split("|")]
        if len(cel) < 4 or not re.match(r"^\d+$", cel[0]):
            continue
        p = re.sub(r"[^P0-9]", "", cel[3].split("(")[0].replace("*", ""))
        out[int(cel[0])] = (_v(cel[2].replace("*", "")), p if p in ("P0", "P1", "P2") else "-")
    return out


def incarca():
    """[(domeniu, id, text, verdict tester, prioritate, verificări)]"""
    out = []
    md = _tabel_loc()
    for x in json.loads((R11 / "locuinte" / "fraze.json").read_text(encoding="utf-8")):
        v, p = md.get(x["id"], ("-", "-"))
        out.append(("locuinte", f"L{x['id']:02d}", x["text"], v, p, LOC.get(x["id"], [])))
    for x in json.loads((R11 / "fotovoltaic" / "fraze.json").read_text(encoding="utf-8")):
        p = x.get("prioritate") or "-"
        out.append(("fotovoltaic", f"F{x['id']:02d}", x["fraza"], _v(x.get("verdict") or "-"), p if p in ("P0", "P1", "P2") else "-",
                    PV.get(x["id"], [])))
    for k, x in json.loads((R11 / "industrial" / "fraze.json").read_text(encoding="utf-8")).items():
        n = int(k[1:])
        p = IND_PRIO.get(n, "-")
        out.append(("industrial", f"I{n:02d}", x["text"], "gresit" if p == "P0" else "-", p, IND.get(n, [])))
    return out


def ruleaza():
    rez = {}
    for dom, fid, text, vt, prio, verif in incarca():
        c = rezultat(text)
        verif = list(verif) + [BLOC_INTREBAT] if BLOC_INTREBAT not in verif else verif
        v, lipsa = evalueaza(verif, c)
        rez[fid] = {"dom": dom, "tester": vt, "prio": prio, "dupa": v, "lipsa": lipsa, "plasa": plasa_ok(c["r"]),
                    "text": text, "nec": c["r"]["neconsumat"], "explicit": len(verif) > 1}
    return rez


def main(verbose=False, fara_vechi=False):
    rang = {"gresit": 0, "partial": 1, "corect": 2}
    rez = ruleaza()
    stat = {}
    tot = {"n": 0, "t": dict.fromkeys(rang, 0), "d": dict.fromkeys(rang, 0), "p01": [0, 0], "expl": [0, 0], "plasa": 0}
    for fid, x in rez.items():
        s = stat.setdefault(x["dom"], {"n": 0, "t": dict.fromkeys(rang, 0), "d": dict.fromkeys(rang, 0), "p01": [0, 0],
                                       "expl": [0, 0], "plasa": 0})
        for d in (s, tot):
            d["n"] += 1
            if x["tester"] in rang:
                d["t"][x["tester"]] += 1
            d["d"][x["dupa"]] += 1
            if x["prio"] in ("P0", "P1") and x["explicit"]:
                d["p01"][0] += 1
                d["p01"][1] += x["dupa"] == "corect"
            if x["explicit"]:
                d["expl"][0] += 1
                d["expl"][1] += x["dupa"] == "corect"
            d["plasa"] += not x["plasa"]
    print("Runda 11 — interpretorul local (C/P/G; verificări explicite pe P0/P1 + clasele reparate, restul: plasa + "
          "„nimic blocat fără întrebare”):")
    print(f"  {'domeniu':12s} {'n':>3s} | {'tester r11':12s} | {'după (verif.)':14s} | verificate corecte | P0/P1 verificate corecte | plasă ruptă")
    cpg = lambda d: f"{d['corect']}/{d['partial']}/{d['gresit']}"  # noqa: E731
    for dom, s in list(stat.items()) + [("TOTAL", tot)]:
        print(f"  {dom:12s} {s['n']:3d} | {cpg(s['t']):12s} | {cpg(s['d']):14s} | {s['expl'][1]:3d}/{s['expl'][0]:<14d} | "
              f"{s['p01'][1]:3d}/{s['p01'][0]:<21d} | {s['plasa']}")
    for fid, x in rez.items():
        if x["dupa"] != "corect" or verbose or not x["plasa"]:
            print(f"    {fid} ({x['prio']}): tester {x['tester']} → {x['dupa']}"
                  + (f"  lipsă: {'; '.join(x['lipsa'])}" if x["lipsa"] else "") + ("" if x["plasa"] else "  [PLASĂ]")
                  + (f"  | {x['text'][:110]!r}" if verbose or x["dupa"] != "corect" else ""))
    if not fara_vechi:
        print("\nRundele 5–10 (regresii):")
        r10.main(verbose=False)
    return rez


if __name__ == "__main__":
    main(verbose="-v" in sys.argv, fara_vechi="--fara-vechi" in sys.argv)
