"""Reverificarea rundei 7 (teste/r7/{locuinte,fotovoltaic,industrial}) + rundele 5 și 6 după reparațiile r7 ale
interpretorului (normalizare / segmentare, legarea valorilor de entitate, contradicții numerice, plasa de siguranță).

Pentru fiecare frază r7 se aplică o listă de verificări scrisă din „așteptat” + comentariul testerului (nu din ce face
codul):
  * „înainte” — verdictul testerului din runda 7 (fraze.json / tabelul din industrial.md);
  * „după”    — `interpreteaza_local(text)` cu codul curent, evaluat cu aceleași verificări.
O frază e „corectă” dacă trec toate verificările ei, „parțială” dacă trece cel puțin jumătate, altfel „greșită”.
Verificarea comună tuturor frazelor (r6, cerința 1): o frază cu rest neconsumat nu iese „genereaza” fără mențiune.
Rundele 5 și 6 se reiau cu teste/r6/reverificare.py (regresii).

Rulare: cd /home/claude/sm && python3 teste/r7/reverificare.py [-v]
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

RAD = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAD))
from engine.interpretor import interpreteaza_local  # noqa: E402

R7 = RAD / "teste" / "r7"
_spec = importlib.util.spec_from_file_location("reverificare_r6", RAD / "teste" / "r6" / "reverificare.py")
r6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r6)
r5 = r6.r5
g, inv, plec, evalueaza = r5.g, r5.inv, r5.plec, r5.evalueaza
_inv, _eq, _tip, _act, _np, _pl = r5._inv, r5._eq, r5._tip, r5._act, r5._np, r5._pl
NU_REFUZ, INTREABA = r5.NU_REFUZ, r5.INTREABA
INTREABA_SAU_REFUZ = r6.INTREABA_SAU_REFUZ
REFUZ = r6.REFUZ
GENEREAZA = ("generează fără întrebări", lambda r: r["act"] == "genereaza")
_DIA = str.maketrans("șşțţăâîȘŞȚŢĂÂÎ", "ssttaaiSSTTAAI")


def _f(s):
    return str(s).translate(_DIA).lower()


def _ne(cheie, val):
    return (f"{cheie} ≠ {val}", lambda r: g(r["in"], cheie) != val)


def Q(*cuv, desc=None):
    """o întrebare care conține toate cuvintele (fără diacritice, litere mici)"""
    return (desc or ("întrebare „" + " + ".join(cuv) + "”"),
            lambda r: r["act"] in ("genereaza_cu_intrebare", "refuza")
            and any(all(_f(c) in _f(q) for c in cuv) for q in r["intrebari"]))


def FARA_Q(*cuv):
    return ("fără întrebarea „" + " + ".join(cuv) + "”",
            lambda r: not any(all(_f(c) in _f(q) for c in cuv) for q in r["intrebari"]))


def NEC_FARA(*sub):
    return ("neconsumat fără „" + "/".join(sub) + "”",
            lambda r: not any(_f(s) in _f(x) for x in r["nec"] for s in sub))


FARA_NEC = ("tot textul folosit (neconsumat gol)", lambda r: not r["nec"])


def REC(rec, n=1, P=None):
    return (f"{n} × circuit {rec}" + (f" {P} kW" if P is not None else ""),
            lambda r: sum(1 for c in r["in"].get("circuite") or [] if c["receptor"] == rec
                          and (P is None or c.get("P_kW") == P)) >= n)


def CIRC_NUME(sub):
    return (f"circuit „{sub}”", lambda r: any(_f(sub) in _f(c["nume"]) for c in r["in"].get("circuite") or []))


def PA(v):
    return (f"P aprobată {v}", lambda r: v in (g(r["in"], "alimentare.P_aprobata_kW"), r["in"].get("P_aprobata_kW")))


def PN(v):
    return (f"Σ invertoare {v} kW", lambda r: abs(r5.pn_total(r["in"]) - v) < 0.01)


def TD_SEC(desc, f):
    return (desc, lambda r: any(f(t) for t in r["in"].get("tablouri_secundare") or []))


def PLEC_ANY(desc, f):
    return (desc, lambda r: any(f(p) for p in r5.plec(r["in"])))


def COPII(i, n):
    return (f"plecarea {i + 1} are {n} sub-plecări",
            lambda r: len((r["in"].get("plecari") or [{}] * (i + 1))[i].get("copii") or []) == n)


FARA_HIBRID = ("fără baterie / hibrid nedeclarat", lambda r: not r["in"].get("baterie_kWh") and not r["in"].get("bess")
               and not r["in"].get("hibrid") and not any(x.get("hibrid") for x in r["in"].get("invertoare") or [])
               and not g(r["in"], "invertor.hibrid"))
KWH = lambda v: (f"baterie {v} kWh", lambda r: v in (r["in"].get("baterie_kWh"), g(r["in"], "bess.kWh")))  # noqa: E731
L = _tip("locuinta")
T = _tip("tablou")
PR = _tip("prosumator")
CEF = _tip("cef")

# ------------------------------------------------------------------------------------------- locuințe (r7)
LOC = {
    1: [L, _eq("retea", "mono"), PA(6), _eq("schema_pamant", "TN-C-S"), REC("plita"), REC("boiler", P=2), GENEREAZA],
    2: [L, _eq("retea", "mono"), PA(7), _eq("schema_pamant", "TN-C-S")],
    3: [L, _eq("retea", "mono"), PA(5), _ne("alimentare.cablu.metoda", "D1"), Q("PE")],
    4: [L, INTREABA, Q("monofaz")],
    5: [L, INTREABA, REC("aer_conditionat", 3), REC("plita")],
    6: [L, _eq("retea", "tri"), PA(20), _eq("schema_pamant", "TT"), _eq("RA_ohm", 4), REC("pompa_caldura", P=12),
        CIRC_NUME("exterior"), _eq("schema_pamant", "TT")],
    7: [L, _eq("retea", "mono"), PA(9), REC("centrala_termica"), REC("uscator")],
    8: [L, _eq("retea", "tri"), PA(22), Q("etaj")],
    9: [_eq("retea", "tri"), ("P 15", lambda r: 15 in (r["in"].get("P_kW"), g(r["in"], "alimentare.P_aprobata_kW")))],
    10: [_tip("bransament"), _eq("retea", "tri"), _eq("P_kW", 30), _eq("L_coloana_m", 25)],
    11: [INTREABA_SAU_REFUZ, Q("trifazat")],
    12: [_eq("retea", "tri"), ("P 22", lambda r: 22 in (r["in"].get("P_kW"), g(r["in"], "alimentare.P_aprobata_kW"))),
         ("coloana 40 m", lambda r: 40 in (r["in"].get("L_coloana_m"), g(r["in"], "alimentare.L_coloana_m"))),
         ("coloana Al 35 impusă", lambda r: 35 in (g(r["in"], "cablu.S_fortat"), g(r["in"], "alimentare.cablu.S_fortat"))),
         FARA_Q("tip de schem")],
    13: [REFUZ],
    14: [REFUZ],
    15: [L, INTREABA, Q("monofaz")],
    16: [L, _eq("retea", "tri"), PA(16), _eq("schema_pamant", "TT"), REC("pompa_apa", P=1.1), CIRC_NUME("piscin"),
         ("iluminat piscină 12 V (SELV)", lambda r: any("piscin" in _f(c["nume"]) and c["receptor"] == "iluminat"
                                                        for c in r["in"].get("circuite") or []))],
    17: [L, _eq("retea", "tri"), PA(20), REC("sauna", P=9)],
    18: [L, _eq("retea", "tri"), PA(25), REC("vehicul_electric", P=11)],
    19: [INTREABA_SAU_REFUZ, Q("22"), _eq("retea", "mono")],
    20: [L, _eq("retea", "mono"), _eq("schema_pamant", "TT"), INTREABA_SAU_REFUZ, Q("trifazat")],
    21: [L, _eq("retea", "tri"), PA(20), TD_SEC("TD garaj/atelier la 30 m", lambda t: t.get("L_m") == 30),
         TD_SEC("compresor 2,2 kW pe TD", lambda t: any(c.get("P_kW") == 2.2 for c in t.get("circuite") or []))],
    22: [T, _eq("origine", "tg_existent"), _eq("cablu.S_fortat", 6), _eq("L_alimentare_m", 40), _eq("retea", "tri"),
         _eq("schema_pamant", "TT"), Q("plec")],
    23: [L, _eq("retea", "mono"), PA(11), INTREABA_SAU_REFUZ, Q("trifazat")],
    24: [PR, _eq("retea", "mono"), PN(5), PA(7), _eq("schema_pamant", "TN-C-S")],
    25: [PR, _inv((1, 8)), PA(15), _eq("kWp", 10), _eq("retea", "tri"), FARA_Q("total")],
    26: [PR, _inv((1, 6)), _eq("retea", "mono"), _eq("schema_pamant", "TT"), NEC_FARA("pv")],
    27: [PR, _inv((1, 10)), KWH(10), PA(20), FARA_Q("total")],
    28: [PR, _inv((1, 8)), _eq("bess.P_kW", 5), _eq("bess.kWh", 10), _eq("bess.cuplaj", "ca"), PA(15), FARA_Q("total")],
    29: [PR, PN(27), PA(30)],
    30: [PR, PN(27.5), PA(30)],
    31: [PR, _inv((2, 15)), PA(40), _eq("kWp", 30), FARA_Q("total")],
    32: [INTREABA_SAU_REFUZ],
    33: [PR, INTREABA_SAU_REFUZ, Q("monofaz")],
    34: [PR, _inv((1, 10)), PA(16), _eq("modul.Pmax_W", 455), _eq("retea", "tri"), FARA_Q("total")],
    35: [PR, _inv((1, 6)), PA(9), _eq("limitare_injectie_kW", 0), _eq("retea", "mono"), FARA_Q("total")],
    36: [PR, _inv((1, 12)), PA(7), _eq("retea", "mono"), INTREABA_SAU_REFUZ],
    37: [PR, PN(20), PA(25)],
    38: [PR, _inv((3, 10)), PA(35), NEC_FARA("pa")],
    39: [PR, _inv((2, 13.5)), PA(30), FARA_Q("total"), FARA_NEC],
    40: [PR, _inv((1, 25)), _eq("bess.P_kW", 10), _eq("bess.cuplaj", "ca"), PA(40), FARA_Q("total")],
    41: [INTREABA_SAU_REFUZ, Q("PEN")],
    42: [INTREABA_SAU_REFUZ],
    43: [INTREABA_SAU_REFUZ],
    44: [INTREABA_SAU_REFUZ],
    45: [INTREABA_SAU_REFUZ],
    46: [L, _eq("retea", "tri"), PA(10)],
    47: [L, _eq("retea", "mono"), PA(9)],
    48: [L, _eq("retea", "tri"), _eq("alimentare.In_Q_bransament_A", 25), FARA_NEC],
    49: [L, _eq("retea", "mono"), _eq("alimentare.In_Q_bransament_A", 40), FARA_Q("monofaz")],
    50: [L, _eq("retea", "tri"), PA(15), REC("plita", P=7.2), REC("iluminat", 6), REC("masina_spalat_vase"),
         REC("masina_spalat_rufe"), REC("uscator"), CIRC_NUME("frigider")],
    51: [L, _eq("retea", "tri"), PA(12)],
    52: [_eq("retea", "mono"), _eq("schema_pamant", "TT")],
    53: [L, _eq("retea", "tri"), PA(15), _eq("schema_pamant", "TT")],
    54: [L, _eq("retea", "tri"), PA(11), ("GE = sursă (nu circuit)", lambda r: not any(
        "generator" in _f(c["nume"]) for c in r["in"].get("circuite") or [])),
         ("GE 5 kW cu comutator manual (ge_rezerva)", lambda r: g(r["in"], "ge_rezerva.P_kW") == 5
          and g(r["in"], "ge_rezerva.comutare") == "manual"), FARA_Q("puterea GE"), FARA_Q("kVA")],
    55: [L, _eq("retea", "tri"), PA(20), _eq("schema_pamant", "TT"), REC("pompa_caldura", P=16),
         ("rezistența 9 kW", lambda r: any(c.get("P_kW") == 9 for c in r["in"].get("circuite") or []))],
    56: [L, _eq("retea", "mono"), PA(7), REC("aer_conditionat", 3)],
    57: [L, _eq("retea", "mono"), PA(9), _ne("alimentare.cablu.S_fortat", 10),
         Q("TD Corp 2", "60 m", desc="întrebare: circuitele TD-ului din corpul 2 (60 m, cablu 4x10 Al)"), Q("4 conductoare")],
    58: [L, _eq("retea", "tri"), PA(22), ("jacuzzi 5 kW", lambda r: any(c.get("P_kW") == 5 for c in r["in"].get("circuite") or [])),
         REC("pompa_caldura", P=7)],
    59: [PR, PN(15), KWH(15), FARA_Q("cuplat"), ("backup (EPS) frigider + centrală", lambda r: len(
        g(r["in"], "backup.circuite") or []) == 2)],
    60: [PR, _inv((1, 9)), _eq("retea", "mono")],
    61: [PR, _inv((1, 10)), PA(15), _eq("retea", "tri"), Q("pomp"), NEC_FARA("15 kw", "tn-c-s")],
    62: [T, _eq("origine", "tg_existent"), _eq("In_Q1_A", 16), _eq("retea", "tri"), Q("plec")],
    63: [L, _eq("retea", "mono"), _eq("alimentare.In_Q_bransament_A", 32), REC("plita", P=7), FARA_Q("tip de schem")],
    64: [_ne("retea", "tri"), ("cablu 3x2,5 impus", lambda r: 2.5 in (g(r["in"], "cablu.S_fortat"),)),
         _eq("L_alimentare_m", 25), _eq("origine", "tg_existent"), Q("monofaz"),
         ("prizele / iluminatul păstrate", lambda r: sum(int(p.get("n_circuite") or 1) for p in r["in"].get("plecari") or [])
          >= 7)],
    65: [PR, PN(100), Q("semidirect")],
    66: [PR, _inv((1, 10)), Q("monofaz")],
    67: [L, _eq("retea", "tri"), PA(18)],
    68: [L, _eq("retea", "tri")],
}

# ---------------------------------------------------------------------------------------- fotovoltaic (r7)
PV = {
    1: [CEF, _inv((1, 20)), _eq("racord", "tg_existent"), _eq("schema_pamant", "TN-S"), _eq("kWp", 20)],
    2: [CEF, _inv((10, 110)), _eq("pt_Sn_kVA", 1250), _eq("pt_existent", False)],
    3: [CEF, _inv((20, 100)), _eq("n_trafo", 2), _eq("pt_Sn_kVA", 1250), NEC_FARA("transformatoare")],
    4: [CEF, _inv((5, 110), (2, 50)), _eq("pt_Sn_kVA", 1000), _eq("pt_existent", True)],
    5: [CEF, _inv((3, 100), (1, 50)), _eq("racord", "bmpt"), _eq("schema_pamant", "TN-C-S")],
    6: [CEF, _inv((3, 50)), _eq("string.n_module", 18), _eq("string.Uoc_V", 51.6),
        ("racord nedeclarat → presupus declarat", lambda r: any("BMPT" in x for x in r["d"]["presupus"]))],
    7: [CEF, _inv((4, 100)), _eq("string.n_module", 28), _eq("pt_existent", True)],
    8: [CEF, _inv((1, 125)), _eq("string.n_module", 22), _eq("string.n_MPPT", 8), _eq("racord", "tg_existent")],
    9: [CEF, _inv((1, 50)), _eq("gpv_In_A", 15), _eq("racord", "tg_existent")],
    10: [CEF, _inv((2, 50)), ("fără BESS", lambda r: not r["in"].get("bess")), _eq("racord", "tg_existent")],
    11: [PR, _inv((1, 10)), KWH(15), FARA_Q("kwh")],
    12: [CEF, PN(100), _eq("bess.kWh", 215), _eq("bess.cuplaj", "ca"),
          ("model BESS fără „cuplat”", lambda r: "cuplat" not in _f(g(r["in"], "bess.model") or ""))],
    13: [CEF, _eq("bess.kWh", 1000), _eq("bess.P_kW", 500), _eq("pt_Sn_kVA", 630)],
    14: [PR, PN(6), _eq("retea", "mono"), KWH(7.7), _eq("schema_pamant", "TN-C-S")],
    15: [PR, _inv((1, 12)), KWH(19.2), _eq("schema_pamant", "TT"), _eq("retea", "tri")],
    16: [PR, PN(8), INTREABA_SAU_REFUZ, Q("Sunny Island")],
    17: [PR, _inv((1, 30)), _eq("limitare_injectie_kW", 0)],
    18: [CEF, _inv((2, 110)), _eq("limitare_injectie_kW", 150)],
    19: [PR, _inv((1, 8)), _eq("limitare_injectie_kW", 0), _eq("retea", "tri")],
    20: [PR, _inv((1, 15)), INTREABA_SAU_REFUZ, Q("inject"), _eq("P_evacuata_kW", 15)],
    21: [CEF, _inv((16, 100)), _eq("n_trafo", 2), _eq("pt_Sn_kVA", 1000), FARA_Q("Măriți")],
    22: [PR, PN(25), _eq("In_Q_bransament_A", 200), _eq("racord", "bmpt"), FARA_NEC],
    23: [CEF, _inv((1, 60)), _eq("racord", "tg_existent")],
    24: [PR, _eq("retea", "mono"), PN(5), _eq("schema_pamant", "TT"), FARA_HIBRID],
    25: [PR, _eq("retea", "mono"), PN(6), _eq("schema_pamant", "TT")],
    26: [INTREABA_SAU_REFUZ],
    27: [INTREABA_SAU_REFUZ],
    28: [_inv((1, 33)), ("cablu 5x16 impus", lambda r: 16 in (g(r["in"], "cablu_C0.S_fortat"), g(r["in"], "cablu.S_fortat"),
                                                           g(r["in"], "cablu_inv.S_fortat")))],
    29: [CEF, _inv((2, 50)), _eq("cablu_C0.S_fortat", 50), _eq("L_racord_m", 120)],
    30: [_inv((1, 50)), ("cablu 5x6 impus", lambda r: 6 in (g(r["in"], "cablu_C0.S_fortat"), g(r["in"], "cablu.S_fortat"),
                                                          g(r["in"], "cablu_inv.S_fortat")))],
    31: [INTREABA_SAU_REFUZ],
    32: [PR, _inv((2, 20))],
    33: [PR, _inv((3, 10)), FARA_HIBRID],
    34: [PR, _inv((1, 25))],
    35: [PR, _inv((1, 50)), _eq("limitare_injectie_kW", 27)],
    36: [INTREABA_SAU_REFUZ, Q("monofaz")],
    37: [PR, _inv((1, 8)), Q("monofaz"), FARA_Q("puterea invertorului")],
    38: [INTREABA_SAU_REFUZ],
    39: [INTREABA_SAU_REFUZ],
    40: [INTREABA_SAU_REFUZ],
    41: [CEF, _inv((10, 100)), Q("500"), ("model fără „dar”", lambda r: all(
        "dar" not in _f(x.get("model") or "") for x in r["in"].get("invertoare") or []))],
    42: [INTREABA_SAU_REFUZ],
    43: [CEF, _inv((3, 110)), INTREABA_SAU_REFUZ, Q("racord")],
    44: [INTREABA_SAU_REFUZ],
    45: [_inv((3, 300)), INTREABA_SAU_REFUZ, Q("800")],
    46: [CEF, _inv((4, 250)), _eq("pt_Sn_kVA", 1250), _eq("U_JT_V", 800), _eq("U_inv_ca_V", 800), _eq("U_ca_V", 800)],
    47: [PR, PN(40)],
    48: [CEF, _inv((2, 110)), _eq("pt_Sn_kVA", 630), _eq("pt_existent", True), FARA_NEC],
    49: [_inv((1, 20)), _eq("racord", "tg_existent"), _eq("schema_pamant", "TN-C-S")],
    50: [CEF, _inv((1, 100)), _eq("kWp", 120)],
    51: [INTREABA_SAU_REFUZ],
    52: [CEF, _inv((1, 50))],
    53: [CEF, _inv((1, 100))],
    54: [CEF, _inv((1, 60)), _eq("gpv_In_A", 10)],
    55: [PR, _eq("retea", "mono"), PN(6), KWH(10), _eq("limitare_injectie_kW", 0), _eq("schema_pamant", "TT")],
    56: [CEF, _inv((50, 100)), _eq("n_trafo", 4), _eq("pt_Sn_kVA", 1600), FARA_Q("Împărțiți")],
    57: [CEF, _inv((9, 100)), _eq("pt_Sn_kVA", 1000), FARA_Q("total")],
    58: [INTREABA_SAU_REFUZ],
    59: [PR, _inv((1, 10)), KWH(10.65), _eq("schema_pamant", "TN-C-S")],
    60: [CEF, _eq("bess.kWh", 2000), _eq("bess.P_kW", 1000), _eq("bess.cuplaj", "ca"), _eq("n_trafo", 2),
          _eq("pt_Sn_kVA", 630)],
    61: [CEF, _inv((1, 10)), _eq("retea", "tri"), _eq("racord", "tg_existent"), _eq("schema_pamant", "TN-C-S")],
    62: [PR, _inv((1, 30), (1, 5)), FARA_HIBRID],
    63: [INTREABA_SAU_REFUZ],
    64: [CEF, _inv((3, 50)), _eq("racord", "pt"), _eq("pt_existent", True), Q("kVA"), NEC_FARA("racord")],
    65: [CEF, _inv((8, 100)), _eq("pt_Sn_kVA", 1000), _eq("masura", "MT")],
    66: [INTREABA_SAU_REFUZ, Q("off-grid")],
    67: [PR, _inv((1, 10)), _eq("bess.kWh", 10.2), _eq("bess.P_kW", 6), _eq("bess.cuplaj", "ca"), Q("monofaz")],
    68: [CEF, _inv((3, 110), (2, 50), (1, 33))],
    69: [INTREABA_SAU_REFUZ],
    70: [CEF, _inv((4, 25)), _eq("cablu_C0.material", "Al")],
}

# ----------------------------------------------------------------------------------------- industrial (r7)
PT = _tip("pt")
GE = _tip("ge_ats")
IND = {
    1: [T, _eq("origine", "pt_propriu"), _eq("pt_Sn_kVA", 630), _eq("schema_pamant", "TN-S"), _np(7), Q("prize")],
    2: [T, _eq("origine", "tg_existent"), _eq("cablu.S_fortat", 95), _eq("schema_pamant", "TN-C-S"), _np(5)],
    3: [T, _eq("origine", "bmpt"), _eq("schema_pamant", "TN-S"), _np(12), _ne("P_kW", 9), _ne("In_Q1_A", 16),
        PLEC_ANY("uși 1,1 kW", lambda p: p.get("P_kW") == 1.1)],
    4: [T, _eq("origine", "pt_propriu"), _eq("pt_Sn_kVA", 400), _np(6)],
    5: [T, _eq("pt_Sn_kVA", 1000), _np(11)],
    6: [T, _np(3), _pl(0, "pornire", "stea_triunghi"), _pl(1, "pornire", "convertizor"), _pl(2, "pornire", "soft")],
    7: [T, _eq("cablu.S_fortat", 240), _eq("cablu.n_fortat", 2), _eq("cablu.n_paralel", 2), _eq("cablu.material", "Al"), _np(5),
        _eq("schema_pamant", "TN-S")],
    8: [T, _eq("origine", "bmpt"), _eq("P_kW", 70), _np(5), _eq("retea", "tri"),
        ("fără plecare fantomă TD", lambda r: not any(p["nume"].startswith("TD") for p in r5.plec(r["in"])))],
    9: [("nu e PT (trafo de separare)", lambda r: r["tip"] != "pt"), INTREABA_SAU_REFUZ, Q("IT")],
    10: [T, _eq("schema_pamant", "IT"), INTREABA_SAU_REFUZ],
    11: [T, _eq("schema_pamant", "TT"), _eq("origine", "bmpt"), _np(4)],
    12: [T, _eq("retea", "mono"), _eq("origine", "bmpt"), _np(4),
         ("fără plecare fantomă TD", lambda r: not any(p["nume"].startswith("TD") for p in r5.plec(r["in"])))],
    13: [REFUZ],
    14: [REFUZ],
    15: [T, _np(4), ("rețeaua (trifazat) dedusă și declarată", lambda r: any("trifazat" in x for x in r["d"]["presupus"])
                                                                         or r["act"] == "genereaza_cu_intrebare")],
    16: [T, _eq("origine", "pt_propriu"), _eq("pt_Sn_kVA", 630), _np(3), COPII(2, 1)],
    17: [T, _eq("origine", "pt_propriu"), _eq("pt_Sn_kVA", 400), _np(1), COPII(0, 1),
         ("TD hala 150 kW", lambda r: (r["in"].get("plecari") or [{}])[0].get("P_kW") == 150)],
    18: [T, _eq("origine", "tg_existent"), _np(1), _pl(0, "L_m", 120), _pl(0, "cablu.S_fortat", 6), _ne("L_alimentare_m", 120)],
    19: [T, _eq("cablu.S_fortat", 25), _eq("L_alimentare_m", 40), _eq("P_kW", 32), Q("plec")],
    20: [T, _np(1), _pl(0, "pornire", "directa"), ("motor 55 kW", lambda r: abs((r5.plec(r["in"]) or [{}])[0].get("P_kW", 0) - 55.16)
                                                  < 0.1)],
    21: [T, _eq("origine", "pt_propriu"), _eq("pt_Sn_kVA", 400), _np(2), Q("pornire")],
    22: [PT, _eq("Sn_kVA", 630), _eq("masura", "MT"), _np(8)],
    23: [PT, _eq("Sn_kVA", 1600), _eq("U_MT_kV", 6), _eq("compensare_kvar", 400)],
    24: [PT, _eq("n_trafo", 2), _eq("Sn_kVA", 1000), _np(8), _eq("plecari_pe_sectie", True),
         _pl(7, "sectie", 2), Q("cupla")],
    25: [PT, _eq("Sn_kVA", 400), _eq("U_MT_kV", 10), _eq("masura", "JT")],
    26: [INTREABA_SAU_REFUZ],
    27: [PT, _eq("Sn_kVA", 250), _eq("masura", "JT"), _np(3)],
    28: [PT, _eq("Sn_kVA", 160), Q("300")],
    29: [GE, _eq("Sn_GE_kVA", 60), _eq("sursa_retea", "bmpt"), _eq("P_sarcina_kW", 50)],
    30: [GE, _eq("Sn_GE_kVA", 100)],
    31: [GE, _eq("Sn_GE_kVA", 150), _eq("P_sarcina_kW", 47.2), _eq("siguranta_tablou", True),
         ("toți consumatorii de siguranță", lambda r: len(r["in"].get("consumatori") or []) == 3
          and all(c.get("siguranta") for c in r["in"]["consumatori"])),
         ("pompa de rezervă marcată", lambda r: sum(1 for c in r["in"].get("consumatori") or [] if c.get("rezerva")) == 1),
         NEC_FARA("incendiu")],
    32: [INTREABA_SAU_REFUZ],
    33: [GE, _eq("Sn_GE_kVA", 200), _eq("sursa_retea", "tgd")],
    34: [T, _eq("compensare_kvar", 150), _eq("cosfi", 0.75), _eq("P_kW", 300)],
    35: [INTREABA_SAU_REFUZ],
    36: [T, _eq("origine", "pt_propriu"), _eq("pt_Sn_kVA", 1000), _np(4)],
    37: [INTREABA_SAU_REFUZ, Q("BMPT")],
    38: [T, _np(7), _eq("origine", "tg_existent"), PLEC_ANY("15 CP = 11 kW", lambda p: abs(p.get("P_kW", 0) - 11.03) < 0.05),
         PLEC_ANY("2000 W = 2 kW", lambda p: p.get("P_kW") == 2)],
    39: [T, _np(9)],
    40: [T, _np(12), _pl(0, "P_kW", 1.2)],
    41: [T, _np(9), PLEC_ANY("CEE 32 A", lambda p: p.get("In_A") == 32), PLEC_ANY("CEE 16 A", lambda p: p.get("In_A") == 16)],
    42: [T, _eq("origine", "pt_propriu"), _eq("pt_Sn_kVA", 800), _np(3), _eq("schema_pamant", "TN-S")],
    43: [INTREABA_SAU_REFUZ],
    44: [INTREABA_SAU_REFUZ],
    45: [T, _np(3)],
    46: [INTREABA_SAU_REFUZ],
    47: [T, _eq("origine", "bmpt"), _eq("P_kW", 30), _np(3), _eq("schema_pamant", "TN-C-S")],
    48: [INTREABA_SAU_REFUZ],
    49: [T, _np(8), PLEC_ANY("iluminat 230 V monofazat", lambda p: p.get("retea") == "mono")],
    50: [T, INTREABA_SAU_REFUZ],
    51: [INTREABA_SAU_REFUZ],
    52: [T, _np(40)],
    53: [INTREABA_SAU_REFUZ, Q("690"), _eq("U_V", 690)],
    54: [INTREABA_SAU_REFUZ, Q("16")],
    55: [T, _np(1), _pl(0, "cablu.S_fortat", 2.5)],
    56: [INTREABA_SAU_REFUZ, Q("160"), _eq("In_Q_amonte_A", 160)],
    57: [INTREABA_SAU_REFUZ],
    58: [INTREABA_SAU_REFUZ, Q("15"), Q("20")],
    59: [T, _np(5), _eq("origine", "pt_propriu"), _eq("pt_Sn_kVA", 400)],
    60: [T, _np(5)],
    61: [INTREABA_SAU_REFUZ],
    62: [T, _np(3), _pl(0, "pornire", "stea_triunghi"), _pl(1, "pornire", "stea_triunghi"), _pl(2, "pornire", "directa")],
    63: [GE, _eq("Sn_GE_kVA", 30), _eq("comutare", "manual")],
    64: [PT, _eq("Sn_kVA", 1000), INTREABA_SAU_REFUZ],
    65: [PT, _eq("Sn_kVA", 1000), _eq("U_MT_kV", 6), _np(4), PLEC_ANY("compresoare = motor", lambda p: p.get("receptor") == "motor")],
    66: [INTREABA_SAU_REFUZ],
    67: [T, _np(1), _pl(0, "pornire", "soft")],
    68: [T, _eq("origine", "pt_propriu"), _eq("pt_Sn_kVA", 250), _np(3)],
    69: [T, _eq("origine", "pt_propriu"), _eq("pt_Sn_kVA", 800), _np(5), _pl(2, "pornire", "convertizor")],
    70: [T, _eq("origine", "pt_propriu"), _eq("pt_Sn_kVA", 630), _np(15)],
}


# ------------------------------------------------------------------------------------------------- rulare
def _verdict_tester(v):
    v = _f(v)
    return "corect" if v.startswith(("c", "corect")) else "partial" if v.startswith("p") else "gresit"


def _ind_tabel():
    out = {}
    for lin in (R7 / "industrial.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*(\d+)\s*\|.*\|\s*([CPG])\s*\|\s*(P\d|—|-)\s*\|\s*$", lin)
        if m:
            out[int(m.group(1))] = ({"C": "corect", "P": "partial", "G": "gresit"}[m.group(2)], m.group(3))
    return out


def incarca():
    """(rol, id, text, verdict „înainte”, prioritate, verificări)"""
    out = []
    for x in json.loads((R7 / "locuinte" / "fraze.json").read_text(encoding="utf-8")):
        out.append(("locuinte", f"L{x['id']:02d}", x["text"], _verdict_tester(x["verdict"]), x["severitate"], LOC[x["id"]]))
    for x in json.loads((R7 / "fotovoltaic" / "fraze.json").read_text(encoding="utf-8")):
        out.append(("fotovoltaic", f"F{x['id']:02d}", x["t"], _verdict_tester(x["verdict"]), x["prioritate"], PV[x["id"]]))
    tab = _ind_tabel()
    for x in json.loads((R7 / "industrial" / "fraze.json").read_text(encoding="utf-8")):
        v, p = tab.get(x["id"], ("gresit", "P1"))
        out.append(("industrial", f"I{x['id']:02d}", x["text"], v, p, IND[x["id"]]))
    return out


def rezultat(text):
    d = interpreteaza_local(text)
    return {"tip": d["tip_schema"], "act": d["actiune"], "in": d["intrare_fizica"], "intrebari": d["intrebari"],
            "nec": d["neconsumat"], "d": d}


def main(verbose=False):
    rang = {"gresit": 0, "partial": 1, "corect": 2}
    stat, rand, plasa_rupta = {}, [], []
    for rol, fid, text, vi, prio, verif in incarca():
        r = rezultat(text)
        vd, lipsa = evalueaza(verif, r)
        if not r6.plasa_ok(r["d"]):
            plasa_rupta.append((fid, text))
        s = stat.setdefault(rol, {"n": 0, "inainte": dict.fromkeys(rang, 0), "dupa": dict.fromkeys(rang, 0),
                                  "imb": 0, "reg": 0, "p01": [0, 0]})
        s["n"] += 1
        s["inainte"][vi] += 1
        s["dupa"][vd] += 1
        s["imb"] += rang[vd] > rang[vi]
        s["reg"] += rang[vd] < rang[vi]
        if prio in ("P0", "P1") and vi != "corect":
            s["p01"][0] += 1
            s["p01"][1] += vd == "corect"
        rand.append((rol, fid, vi, vd, prio, lipsa, text, r["nec"]))
    print("Runda 7 (fraze noi, verdictul testerului → după reparațiile r7):")
    for rol, s in stat.items():
        print(f"  {rol:12s} {s['n']:3d} fraze | înainte C/P/G {s['inainte']['corect']}/{s['inainte']['partial']}/"
              f"{s['inainte']['gresit']} | după C/P/G {s['dupa']['corect']}/{s['dupa']['partial']}/{s['dupa']['gresit']}"
              f" | P0/P1 rezolvate {s['p01'][1]}/{s['p01'][0]} | îmbunătățite {s['imb']}, regresii {s['reg']}")
    print(f"  plasa de siguranță: {len(plasa_rupta)} fraze cu rest neconsumat generate fără mențiune")
    for rol, fid, vi, vd, prio, lipsa, text, nec in rand:
        if vd != "corect" or verbose:
            print(f"    [{rol}] {fid} ({prio}): {vi} → {vd}" + (f"  lipsă: {'; '.join(lipsa)}" if lipsa else "")
                  + f"  | {text!r}" + (f"  | neconsumat: {nec}" if nec else ""))
    print("\nRundele 5 + 6 (regresii):")
    tot, rupte = r6.main(verbose=False)
    return stat, plasa_rupta, tot, rupte


if __name__ == "__main__":
    main(verbose="-v" in sys.argv)
