"""Reverificarea rundei 8 (teste/r8/{locuinte,fotovoltaic,industrial}/fraze.json) + rundele 5–7 după reparațiile r8 ale
INTERPRETORULUI LOCAL (regulile, fără Claude).

Pentru fiecare frază r8 se aplică o listă de verificări scrisă din „așteptat” + observația testerului (nu din ce face
codul). Cele 60 de fraze din teste/r8/eval_llm.py își păstrează verificările de acolo (aceleași pentru reguli și pentru
Claude); restul sunt scrise aici, în același stil.
  * „tester” — verdictul testerului r8 (fraze.json);
  * „înainte” — verificările pe codul de dinainte de reparațiile r8 (teste/r8/reverificare_inainte.json, salvat cu
    `--salveaza-inainte` înainte de modificări);
  * „după”    — `interpreteaza_local(text)` cu codul curent.
O frază e „corectă” dacă trec toate verificările, „parțială” dacă trece cel puțin jumătate, altfel „greșită”.
Plasa de siguranță (r6): o frază cu rest neconsumat nu iese „genereaza” fără mențiune.
Rundele 5, 6, 7 se reiau cu teste/r7/reverificare.py (regresii).

Rulare: cd /home/claude/sm && python3 teste/r8/reverificare.py [-v] [--fara-vechi]
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

RAD = Path(__file__).resolve().parents[2]
R8 = RAD / "teste" / "r8"
sys.path.insert(0, str(RAD))
sys.path.insert(0, str(R8))
from engine import interpretor, constructor, validare  # noqa: E402
from engine.interpretor import interpreteaza_local  # noqa: E402
import eval_llm  # noqa: E402

_DIA = str.maketrans("șşțţăâîȘŞȚŢĂÂÎ", "ssttaaiSSTTAAI")
F_INAINTE = R8 / "reverificare_inainte.json"


def _f(s):
    return str(s or "").translate(_DIA).lower()


# ------------------------------------------------------------------------------------------------ context de verificare
class C(dict):
    """{"r": rezultatul interpretorului, "v": validarea motorului (leneș, doar dacă o verificare o cere)}"""

    def __getitem__(self, k):
        if k == "v" and not dict.__contains__(self, "v"):
            v = None
            r = dict.__getitem__(self, "r")
            if r["actiune"] != "refuza" and r.get("intrare_fizica"):
                try:
                    m, _ = constructor.genereaza(r["intrare_fizica"])
                    v = validare.valideaza(m)
                except Exception as e:  # noqa: BLE001
                    dict.__setitem__(self, "exc", repr(e))
            dict.__setitem__(self, "v", v)
        return dict.__getitem__(self, k)

    def get(self, k, d=None):
        try:
            return self[k]
        except KeyError:
            return d


def rezultat(text):
    return C(r=interpreteaza_local(text))


Q, I, gen, coduri, inv, pl, gaseste, circ, rec, pa, apx, n_sum = (
    eval_llm.Q, eval_llm.I, eval_llm.gen, eval_llm.coduri, eval_llm.inv, eval_llm.pl, eval_llm.gaseste, eval_llm.circ,
    eval_llm.rec, eval_llm.pa, eval_llm.apx, eval_llm.n_sum)


def tip(t):
    return (f"tip {t}", lambda c: c["r"]["tip_schema"] == t)


def eq(cheie, val):
    def f(c):
        d = I(c)
        for k in cheie.split("."):
            d = d.get(k) if isinstance(d, dict) else None
        return d == val
    return (f"{cheie} = {val}", f)


def PA(v):
    return (f"P aprobată {v}", lambda c: pa(c) == v)


def RET(v):
    return (f"rețea {v}", lambda c: I(c).get("retea") == v)


def SP(v):
    return (f"schema {v}", lambda c: I(c).get("schema_pamant") == v)


def INV(*g):
    return ("invertoare " + " + ".join(f"{n}×{p}" for n, p in g), lambda c: inv(c) == sorted((n, float(p)) for n, p in g))


def PN(v):
    return (f"Σ invertoare {v} kW", lambda c: abs(sum(n * p for n, p in inv(c)) - v) < 0.01)


def REC(r, n=1, P=None, faza=None):
    return (f"{n} × {r}" + (f" {P} kW" if P is not None else "") + (f" {faza}" if faza else ""),
            lambda c: len([x for x in rec(c, r) if (P is None or x.get("P_kW") == P) and (faza is None or x.get("faza") == faza)]) >= n)


def NREC(r, n):
    return (f"exact {n} × {r}", lambda c: len(rec(c, r)) == n)


def KWH(v):
    return (f"baterie {v} kWh", lambda c: apx((I(c).get("bess") or {}).get("kWh") or I(c).get("baterie_kWh")
                                              or (I(c).get("baterie") or {}).get("kWh"), v, 0.01))


def INTREABA(*cuv):
    """o întrebare (sau refuz cu întrebare) care conține toate cuvintele"""
    return ("întrebare „" + " + ".join(cuv) + "”",
            lambda c: c["r"]["actiune"] != "genereaza" and all(_f(w) in _f(Q(c)) for w in cuv))


def FARA_Q(*cuv):
    return ("fără întrebarea „" + " + ".join(cuv) + "”",
            lambda c: not any(all(_f(w) in _f(q) for w in cuv) for q in c["r"]["intrebari"]))


GENEREAZA = ("generează fără întrebări", lambda c: c["r"]["actiune"] == "genereaza")
NU_REFUZ = ("nu refuză", gen)
INTREABA_ORI_REFUZ = ("întreabă / refuză", lambda c: c["r"]["actiune"] != "genereaza")
FARA_NEC = ("tot textul folosit", lambda c: not c["r"]["neconsumat"])
FARA_BESS = ("fără baterie", lambda c: not I(c).get("bess") and not I(c).get("baterie_kWh") and not I(c).get("baterie"))


def NP(n):
    return (f"{n} plecări (desfăcute)", lambda c: n_sum(pl(c)) == n)


def PLEC(desc, f):
    return (desc, lambda c: any(f(p) for p in pl(c)))


L, T, PR, CEF, PT, GE = tip("locuinta"), tip("tablou"), tip("prosumator"), tip("cef"), tip("pt"), tip("ge_ats")
TD_SEC = lambda desc, f: (desc, lambda c: any(f(t) for t in I(c).get("tablouri_secundare") or []))  # noqa: E731
SIG = lambda cuv: (f"„{cuv}” = siguranță", lambda c: any(  # noqa: E731
    p.get("siguranta") or I(c).get("siguranta_tablou") for p in gaseste(pl(c) + (I(c).get("consumatori") or []), cuv)))

EV = eval_llm.V
LOC = {
    1: [L, RET("tri"), PA(18), SP("TN-C-S"), REC("plita"), REC("cuptor"), NREC("aer_conditionat", 2), REC("boiler"),
        REC("pompa_caldura", P=9, faza="3F"), GENEREAZA],
    2: [L, RET("mono"), PA(6), REC("plita"), REC("cuptor"), REC("boiler"),
        ("schema de pământ întrebată / TN-C-S declarat", lambda c: "tn" in _f(Q(c)) or any("TN-C-S" in x for x in c["r"]["presupus"]))],
    3: [PR, INV((1, 8.2)), RET("tri"), ("P aprobată 12", lambda c: I(c).get("P_aprobata_kW") == 12), GENEREAZA],
    4: [L] + EV["locuinte"][4] + [("Q 3×40 A = branșament (nu plecări)", lambda c: (I(c).get("alimentare") or {}).get("In_Q_bransament_A") == 40)],
    5: [L] + EV["locuinte"][5],
    6: [L] + EV["locuinte"][6],
    7: [L] + EV["locuinte"][7],
    8: [L, RET("mono"), PA(5), SP("TN-C-S"), eq("tip_schema", "locuinta"), GENEREAZA],
    9: [L] + EV["locuinte"][9],
    10: [PR, RET("mono"), INV((1, 5)), ("P aprobată 6", lambda c: I(c).get("P_aprobata_kW") == 6)],
    11: [L, RET("tri"), PA(30), REC("sauna", P=6)],
    12: [L] + EV["locuinte"][12] + [FARA_Q("Contradic")],
    13: [L, ("mono 8 kW sau confirmare", lambda c: (I(c).get("retea") == "mono" and pa(c) == 8) or "monofaz" in _f(Q(c)))],
    14: [L, INTREABA("monofaz"), PA(10)],
    15: [L, INTREABA_ORI_REFUZ, REC("pompa_caldura", P=14)],
    16: [L, RET("mono"), PA(7), NREC("aer_conditionat", 3)],
    17: [L] + EV["locuinte"][17],
    18: [L] + EV["locuinte"][18],
    19: [L] + EV["locuinte"][19],
    20: [L, INTREABA_ORI_REFUZ, ("încălzire 12 kW > Pa semnalat", lambda c: "12" in Q(c))],
    21: [L] + EV["locuinte"][21],
    22: EV["locuinte"][22],
    23: [("branșament / locuință", lambda c: c["r"]["tip_schema"] in ("bransament", "locuinta")), RET("mono"), SP("TT")],
    24: [PR] + EV["locuinte"][24],
    25: [("branșament / locuință", lambda c: c["r"]["tip_schema"] in ("bransament", "locuinta")), RET("mono"),
         ("P 9,2", lambda c: 9.2 in (pa(c), I(c).get("P_kW")))],
    26: [L, RET("tri"), PA(35), ("TD atelier 45 m (desenat sau întrebat)", lambda c: any(t.get("L_m") == 45 for t in I(c).get(
        "tablouri_secundare") or []) or ("atelier" in _f(Q(c)) and "45" in Q(c))), FARA_Q("Confirmați puterea")],
    27: [L] + EV["locuinte"][27],
    28: [L, RET("tri"), PA(12), REC("boiler"), REC("plita")],
    29: [L, RET("mono"), ("6 kW (din „6kv”) sau întrebare", lambda c: pa(c) == 6 or "6" in Q(c))],
    30: [L] + EV["locuinte"][30],
    31: [PR, RET("tri"), INV((1, 10)), ("P aprobată 15", lambda c: I(c).get("P_aprobata_kW") == 15)],
    32: [L, RET("tri"), PA(11), SP("TT"), FARA_Q("TN-C-S", "TT")],
    33: [L, RET("mono"), PA(7)],
    34: [L, RET("mono"), PA(7), SP("TT")] + EV["locuinte"][34],
    35: [tip("bransament"), RET("tri"), eq("P_kW", 20), ("coloana 50 m", lambda c: I(c).get("L_coloana_m") == 50)],
    36: [RET("mono"), ("7 kW", lambda c: 7 in (pa(c), I(c).get("P_kW")))],
    37: [("organizare de șantier (nu locuință)", lambda c: c["r"]["tip_schema"] not in ("locuinta", None)), RET("tri"),
         ("15 kW", lambda c: 15 in (pa(c), I(c).get("P_kW"))), ("tabloul de șantier întrebat / semnalat", lambda c: "santier" in _f(Q(c)))],
    38: [INTREABA("trifaz")],
    39: [L] + EV["locuinte"][39],
    40: [L, RET("mono"), PA(9), SP("TT"), REC("pompa_caldura", P=3)],
    41: [L] + EV["locuinte"][41],
    42: [L, RET("mono"), PA(5), REC("vehicul_electric", P=3.7),
         ("set de apartament (fără exterior)", lambda c: not any("exterior" in _f(x.get("nume")) for x in circ(c)))],
    43: [L, RET("tri"), PA(25), SP("TT"), ("pompă 1,5 kW", lambda c: any(x.get("P_kW") == 1.5 for x in circ(c))),
         ("contracurent 3 kW", lambda c: any(x.get("P_kW") == 3 for x in circ(c))),
         ("iluminat LED 12 V (SELV)", lambda c: any(x.get("receptor") == "iluminat" and "12" in _f(x.get("nume")) for x in circ(c)))],
    44: [L, RET("tri"), PA(24), REC("sauna", P=10.5)],
    45: [L] + EV["locuinte"][45],
    46: [L] + EV["locuinte"][46],
    47: [L, RET("tri"), PA(30), SP("TT"), ("TD etaj + TD garaj (desenate sau întrebate)", lambda c: (
        len(I(c).get("tablouri_secundare") or []) >= 2) or ("etaj" in _f(Q(c)) and "garaj" in _f(Q(c))))],
    48: [L, RET("mono"), PA(8), ("GE 6 kVA, comutator manual", lambda c: (I(c).get("ge_rezerva") or {}).get("Sn_kVA") == 6
                                  and (I(c).get("ge_rezerva") or {}).get("comutare") == "manual"),
         ("GE ≠ circuit", lambda c: not any("generator" in _f(x.get("nume")) for x in circ(c)))],
    49: [L, PA(20), ("GE 15 kVA cu ATS", lambda c: (I(c).get("ge_rezerva") or {}).get("Sn_kVA") == 15
                     and (I(c).get("ge_rezerva") or {}).get("comutare") == "ATS")],
    50: [PR, INV((1, 8)), KWH(10), ("P aprobată 15", lambda c: I(c).get("P_aprobata_kW") == 15), FARA_Q("total"),
         ("backup: frigider + centrală + iluminat", lambda c: len((I(c).get("backup") or {}).get("circuite") or []) == 3)],
    51: [PR, RET("mono"), INV((1, 6)), KWH(5)],
    52: [PR, INV((1, 26)), ("P aprobată 30", lambda c: I(c).get("P_aprobata_kW") == 30)],
    53: [PR, INV((2, 15)), ("P aprobată 35", lambda c: I(c).get("P_aprobata_kW") == 35), FARA_Q("total")],
    54: [PR, PN(30), ("P aprobată 40", lambda c: I(c).get("P_aprobata_kW") == 40)],
    55: [PR, INV((1, 27)), ("P aprobată 27", lambda c: I(c).get("P_aprobata_kW") == 27)],
    56: [PR, INV((1, 36)), ("P aprobată 40", lambda c: I(c).get("P_aprobata_kW") == 40), eq("kWp", 40)],
    57: [PR, RET("mono"), INV((1, 5)), ("P aprobată 7", lambda c: I(c).get("P_aprobata_kW") == 7)],
    58: [INTREABA_ORI_REFUZ],
    59: [PR, RET("tri"), INV((1, 10)), KWH(10.2), SP("TT"), eq("RA_ohm", 8)],
    60: [L, RET("tri"), ("10 sau 12 kW întrebat / 12 declarat", lambda c: ("10" in Q(c) and "12" in Q(c)) or pa(c) == 12)],
    61: [INTREABA_ORI_REFUZ],
    62: [("tri 7 kW cu plită monofazată, sau întrebare", lambda c: (I(c).get("retea") == "tri" and pa(c) == 7 and all(
        x.get("faza") != "3F" for x in rec(c, "plita"))) or c["r"]["actiune"] != "genereaza")],
    63: [INTREABA_ORI_REFUZ],
    64: [PR, INV((1, 8)), ("P aprobată 5", lambda c: I(c).get("P_aprobata_kW") == 5)],
    65: [INTREABA_ORI_REFUZ],
    66: [RET("tri"), ("Q 3×25 A", lambda c: 25 in ((I(c).get("alimentare") or {}).get("In_Q_bransament_A"), I(c).get("Q_In_A")))],
    67: [INTREABA_ORI_REFUZ],
    68: [L, RET("tri"), PA(15), NU_REFUZ],
    69: [L, RET("tri"), PA(15), ("prizele negate (fără circuit) sau întrebare", lambda c: not rec(c, "prize") or "priz" in _f(Q(c)))],
    70: [INTREABA_ORI_REFUZ],
    71: [INTREABA_ORI_REFUZ],
}

EF = EV["fotovoltaic"]
PV = {
    1: EF[1], 2: [CEF, INV((1, 50)), eq("racord", "tg_existent"), SP("TN-C-S"), ("kWp ≈ 55,2", lambda c: apx(I(c).get("kWp"), 55.2, 0.01)),
                  ("cablul solar c.c. ≠ C0", lambda c: (I(c).get("cablu_C0") or {}).get("S_fortat") != 6)],
    3: [CEF, INV((4, 110)), ("PT existent / TG existent (fără trafo nou)", lambda c: I(c).get("pt_existent") is True
                             or I(c).get("racord") == "tg_existent"), INTREABA("bateri"), FARA_BESS],
    4: [PR, INV((1, 15)), FARA_BESS],
    5: [PR, INV((3, 10)), SP("TT"), eq("RA_ohm", 8)],
    6: [INTREABA_ORI_REFUZ],
    7: EF[7], 8: [INTREABA_ORI_REFUZ, ("800 V semnalat", lambda c: "800" in Q(c))],
    9: EF[9],
    10: [CEF, INV((5, 100)), eq("pt_Sn_kVA", 630), ("PT nou", lambda c: I(c).get("pt_existent") is not True)],
    11: [PR, INV((1, 10)), KWH(10)],
    12: [CEF, INV((2, 50)), eq("bess.kWh", 430), eq("bess.cuplaj", "ca")],
    13: EF[13], 14: [PR, INV((2, 20)), eq("limitare_injectie_kW", 0)], 15: EF[15], 16: EF[16],
    17: [CEF, INV((1, 30)), FARA_Q("module")],
    18: [CEF, INV((1, 50)), eq("string.n_module", 24)],
    19: [CEF, INV((1, 110)), eq("cablu_C0.S_fortat", 95)],
    20: [CEF, INV((1, 36)), eq("cablu_C0.S_fortat", 25)],
    21: [PR, INV((1, 10)), KWH(9.6)],
    22: [PR, INV((2, 15))],
    23: [PR, INV((1, 25)), SP("TT")],
    24: EF[24], 25: EF[25], 26: EF[26],
    27: [CEF, eq("kWp", 120), INV((1, 100)), eq("racord", "tg_existent"), NU_REFUZ],
    28: EF[28], 29: EF[29],
    30: [CEF, INV((1, 60)), eq("racord", "tg_existent")],
    31: [PR, RET("mono"), INV((1, 5))],
    32: [INTREABA_ORI_REFUZ],
    33: EF[33], 34: EF[34], 35: EF[35],
    36: [CEF, INV((3, 110)), ("fără „Nu am folosit … invertoare”", lambda c: not any("invert" in _f(x) for x in c["r"]["neconsumat"]))],
    37: EF[37],
    38: [CEF, INV((1, 50)), FARA_BESS, ("fără limitare", lambda c: I(c).get("limitare_injectie_kW") is None)],
    39: [CEF, INV((1, 100)), INTREABA_ORI_REFUZ],
    40: [eq("bess.kWh", 500)],
    41: [PR, INV((1, 10)), KWH(9.6)],
    42: [PR, INV((1, 10)), ("PCS 10 kW / 20 kWh", lambda c: (I(c).get("bess") or {}).get("kWh") == 20)],
    43: [INTREABA_ORI_REFUZ],
    44: [CEF, INV((1, 115)), eq("Ik3_TG_kA", 12)],
    45: EF[45],
    46: [INTREABA_ORI_REFUZ],
    47: [INTREABA_ORI_REFUZ],
    48: [PR, INV((1, 30)), KWH(20.48), RET("tri")],
    49: [PR, PN(30), SP("TT")],
    50: [CEF, INV((1, 40)), ("kWp ≈ 40", lambda c: apx(I(c).get("kWp"), 40, 0.01))],
    51: EF[51],
    52: [CEF, INV((1, 50)), eq("racord", "tg_existent")],
    53: EF[53],
    54: [PR, INV((1, 8)), KWH(10)],
    55: [CEF, INV((3, 50))],
    56: [CEF, INV((1, 125)), eq("limitare_injectie_kW", 0), eq("racord", "bmpt"), NU_REFUZ],
    57: [CEF, INV((2, 110)), eq("pt_Sn_kVA", 400)],
    58: EF[58], 59: [INTREABA_ORI_REFUZ],
    60: [INTREABA_ORI_REFUZ, ("110 kV semnalat", lambda c: "110" in Q(c))],
    61: EF[61], 62: [CEF, INV((1, 40))], 63: [CEF, INV((2, 33))],
    64: [PR, INV((4, 25)), eq("limitare_injectie_kW", 50)],
    65: [CEF, INV((2, 125)), eq("cablu_C0.S_fortat", 240)],
    66: [CEF, INV((1, 300)), ("800 V", lambda c: 800 in (I(c).get("U_ca_V"), I(c).get("U_inv_ca_V")))],
    67: [CEF, INV((2, 200)), eq("masura", "MT"), FARA_BESS, eq("pt_Sn_kVA", 630)],
    68: [CEF, INV((1, 100)), eq("bess.kWh", 200), eq("bess.P_kW", 100), eq("limitare_injectie_kW", 0)],
}

EI = EV["industrial"]
IND = {
    1: [T] + EI[1], 2: [T] + EI[2],
    3: [T, eq("pt_Sn_kVA", 400), NP(4), ("Pi / Pc nu sunt plecări", lambda c: all(p.get("P_kW") not in (320, 224) for p in pl(c)))],
    4: [T] + EI[4], 5: [T] + EI[5],
    6: [T, eq("pt_Sn_kVA", 630), PLEC("2 chillere 110 kW", lambda p: p.get("P_kW") == 110),
        ("4 AHU VFD 15 kW", lambda c: n_sum([p for p in pl(c) if p.get("P_kW") == 15 and p.get("pornire") == "convertizor"]) == 4),
        ("12 circuite prize (desenate sau întrebate)", lambda c: any((p.get("n_circuite") or 1) == 12 for p in pl(c)) or "socket" in _f(Q(c))
         or "priz" in _f(Q(c)))],
    7: [T] + EI[7],
    8: [INTREABA_ORI_REFUZ], 9: [INTREABA("monofaz")], 10: [INTREABA_ORI_REFUZ],
    11: [GE, eq("Sn_GE_kVA", 160), ("pompele de incendiu = siguranță, 1+1", lambda c: any(
        x.get("siguranta") and (x.get("n") in ("1+1", 2) or x.get("rezerva")) for x in I(c).get("consumatori") or [])
        or sum(1 for x in I(c).get("consumatori") or [] if x.get("siguranta") and x.get("P_kW") == 37) == 2),
        ("jockey = siguranță", lambda c: any(x.get("siguranta") and "jockey" in _f(x.get("nume")) for x in I(c).get("consumatori") or [])),
        ("fără nume-gunoi („De”)", lambda c: all(len(x.get("nume") or "") > 3 for x in I(c).get("consumatori") or []))],
    12: EI[12], 13: [INTREABA_ORI_REFUZ], 14: EI[14] + [("fără DDR / FE180 (siguranță pe tot TE)", lambda c: I(c).get("siguranta_tablou") is True)],
    15: [T, EI[15][0], EI[15][1], ("TD-B cu compresor (prizele fără calibru: desenate sau întrebate)", lambda c: any(
        any(k.get("P_kW") == 45 for k in p.get("copii") or []) for p in gaseste(pl(c, False), "td-b"))
        and ("priz" in _f(Q(c)) or any(len(p.get("copii") or []) >= 2 for p in gaseste(pl(c, False), "td-b"))))],
    16: [T] + EI[16], 17: EI[17], 18: EI[18],
    19: [PT, eq("Sn_kVA", 800), eq("SkQ_MVA", 250)],
    20: [PT, eq("Sn_kVA", 630), NP(4)],
    21: [PT, eq("Sn_kVA", 250), eq("pt_aerian", True), NP(3)],
    22: EI[22],
    23: [INTREABA("400", "630")],
    24: [T, ("contradicție 100 A semnalată", lambda c: "100" in Q(c) or "V04" in coduri(c, "BLOCANT")), FARA_Q("kVA")],
    25: [T] + EI[25], 26: [T] + EI[26], 27: EI[27], 28: EI[28], 29: [T] + EI[29], 30: [T] + EI[30], 31: [T, NP(5), eq("In_Q1_A", 63)],
    32: [T] + EI[32],
    33: [T, eq("pt_Sn_kVA", 400), ("3 aparate de sudură 20 kVA", lambda c: n_sum([p for p in pl(c) if p.get("S_kVA") == 20
                                                                                or p.get("P_kW") == 18]) == 3),
         PLEC("polizor 2,2 kW", lambda p: p.get("P_kW") == 2.2), ("fără plecare fantomă „TG”", lambda c: not gaseste(pl(c), "tg"))],
    34: [T, eq("pt_Sn_kVA", 400), PLEC("cuptor 250 kW", lambda p: p.get("P_kW") == 250), eq("cablu.S_fortat", 240)],
    35: [T, ("nu locuință", lambda c: c["r"]["tip_schema"] != "locuinta"), PLEC("motor lift 15 kW", lambda p: p.get("P_kW") == 15)],
    36: [T, RET("mono"), NP(10), ("fără BMPM / locuință", lambda c: c["r"]["tip_schema"] == "tablou")],
    37: [T, RET("tri"), ("3 circuite mono 1,2 kW", lambda c: n_sum([p for p in pl(c) if apx(p.get("P_kW"), 1.2, 0.01)]) == 3
                          and all(p.get("retea") == "mono" for p in pl(c) if apx(p.get("P_kW"), 1.2, 0.01)))],
    38: [T, NP(44), ("circuitele finale monofazate", lambda c: all(p.get("retea") == "mono" for p in pl(c)))],
    39: [T, NP(10), FARA_Q("DDR")],
    40: [INTREABA("690")], 41: [INTREABA_ORI_REFUZ], 42: [INTREABA_ORI_REFUZ], 43: [INTREABA_ORI_REFUZ],
    44: [T, ("2 motoare 11 kW", lambda c: n_sum([p for p in pl(c) if p.get("P_kW") == 11]) == 2), RET("tri"), SP("TN-S")],
    45: [T, eq("origine", "tg_existent"), PLEC("chiller 90 kW", lambda p: p.get("P_kW") == 90),
         PLEC("CTA 18,5 kW", lambda p: p.get("P_kW") == 18.5), NP(2)],
    46: [("PT/TG normal + TG vital cu GE", lambda c: c["r"]["tip_schema"] in ("ge_ats", "tablou", "pt")),
         ("TG-normal nu e pe GE", lambda c: not (c["r"]["tip_schema"] == "ge_ats" and (I(c).get("P_sarcina_kW") or 0) >= 300)),
         ("pompe incendiu = siguranță (1+1)", lambda c: any(x.get("siguranta") for x in (I(c).get("consumatori") or []) + pl(c)
                                                            if "incendiu" in _f(x.get("nume")))),
         ("fără refuz V86 cu GE ≥ 400", lambda c: "400 kva" not in _f(Q(c)))],
    47: [INTREABA_ORI_REFUZ],
    48: [GE, eq("comutare", "manual"), eq("Sn_GE_kVA", 40), ("3 consumatori", lambda c: len(I(c).get("consumatori") or []) == 3
                                                             or n_sum(pl(c)) == 3)],
    49: [T, ("2 intrări + cuplă (sau întrebare)", lambda c: "cupl" in _f(Q(c)) or "intrar" in _f(Q(c))), NP(2)],
    50: [INTREABA_ORI_REFUZ],
    51: [T, eq("pt_Sn_kVA", 630), ("3 motoare 22 kW", lambda c: n_sum([p for p in pl(c) if p.get("P_kW") == 22]) == 3),
         PLEC("compresor 37 kW VFD", lambda p: p.get("P_kW") == 37 and p.get("pornire") == "convertizor"),
         PLEC("iluminat 8 kW", lambda p: p.get("P_kW") == 8)],
    52: [T, NP(3)],
    53: [T, NU_REFUZ, ("6 prize mono", lambda c: n_sum([p for p in gaseste(pl(c), "priz") if p.get("retea") == "mono"]) == 6),
         ("2 CEE 32 A", lambda c: n_sum([p for p in pl(c) if p.get("In_A") == 32]) == 2),
         PLEC("elevator 3 kW", lambda p: p.get("P_kW") == 3), PLEC("compresor 5,5", lambda p: p.get("P_kW") == 5.5)],
    54: [INTREABA_ORI_REFUZ, ("în afara scopului (preț)", lambda c: "pret" in _f(Q(c)) or "scop" in _f(Q(c)) or "domeniu" in _f(Q(c)))],
    55: [INTREABA_ORI_REFUZ, ("sursa întrebată (nu BMPT presupus)", lambda c: I(c).get("origine") != "bmpt" or "surs" in _f(Q(c)))],
    56: [INTREABA("15", "10")],
    57: [T, eq("cablu.S_fortat", 16), eq("L_alimentare_m", 150), NP(2)],
    58: [T, RET("tri"), ("3 VRV × 28 kW", lambda c: n_sum([p for p in pl(c) if p.get("P_kW") == 28]) == 3),
         PLEC("unități interioare mono", lambda p: p.get("retea") == "mono")],
    59: [PT, eq("Sn_kVA", 630), NP(8), ("fără refuz", gen)],
    60: [PT, eq("Sn_kVA", 1600)],
    61: [PT, eq("n_trafo", 2), eq("Sn_kVA", 1000), NP(3)],
    62: [T, eq("pt_Sn_kVA", 630), ("TE-Server sub TE-E2", lambda c: any(p.get("copii") for p in gaseste(pl(c, False), "te-e2"))),
         FARA_Q("kVA")],
    63: [T, PLEC("2 compresoare 55 VFD", lambda p: p.get("P_kW") == 55 and p.get("pornire") == "convertizor"),
         PLEC("uscător 3 kW", lambda p: p.get("P_kW") == 3), eq("L_alimentare_m", 70)],
    64: [T] + EI[64],
    65: [T, NP(5), ("Q1 80", lambda c: 80 in (I(c).get("In_Q1_A"), I(c).get("In_Q_amonte_A"), I(c).get("_In_Q_amonte_A"))),
         ("friteuze 2 × 9 kW", lambda c: n_sum([p for p in pl(c) if p.get("P_kW") == 9]) == 2)],
    66: [T, SP("TT"), eq("RA_ohm", 30)],
    67: [INTREABA_ORI_REFUZ],
    68: [T, eq("pt_Sn_kVA", 1000), ("≥ 12 plecări", lambda c: n_sum(pl(c, False)) >= 12)],
}


# ------------------------------------------------------------------------------------------------- încărcare / rulare
def _v(v):
    v = _f(v)
    return "corect" if v.startswith("c") else "partial" if v.startswith("p") else "gresit"


def incarca():
    """[(domeniu, id, text, verdict tester, prioritate, verificări)]"""
    out = []
    for dom, V, kp in (("locuinte", LOC, "severitate"), ("fotovoltaic", PV, "prioritate"), ("industrial", IND, "severitate")):
        for x in json.loads((R8 / dom / "fraze.json").read_text(encoding="utf-8")):
            p = x.get(kp) or "-"
            out.append((dom, f"{dom[0].upper()}{x['id']:02d}", x["text"], _v(x["verdict"]), p if p in ("P0", "P1", "P2") else "-",
                        V[x["id"]]))
    return out


def evalueaza(verif, c):
    ok, lipsa = 0, []
    for desc, f in verif:
        try:
            r = bool(f(c))
        except Exception:  # noqa: BLE001
            r = False
        ok += r
        if not r:
            lipsa.append(desc)
    n = len(verif)
    return ("corect" if ok == n else "partial" if ok * 2 >= n else "gresit"), lipsa


def plasa_ok(d):
    return not d["neconsumat"] or (d["actiune"] != "genereaza" and "Nu am înțeles" in d["intelegere"])


def ruleaza():
    rez = {}
    for dom, fid, text, vt, prio, verif in incarca():
        c = rezultat(text)
        v, lipsa = evalueaza(verif, c)
        rez[fid] = {"dom": dom, "tester": vt, "prio": prio, "dupa": v, "lipsa": lipsa, "plasa": plasa_ok(c["r"]),
                    "text": text, "nec": c["r"]["neconsumat"]}
    return rez


def main(verbose=False, fara_vechi=False, salveaza_inainte=False):
    rang = {"gresit": 0, "partial": 1, "corect": 2}
    rez = ruleaza()
    if salveaza_inainte:
        F_INAINTE.write_text(json.dumps({k: v["dupa"] for k, v in rez.items()}, ensure_ascii=False, indent=0), encoding="utf-8")
    ina = json.loads(F_INAINTE.read_text(encoding="utf-8")) if F_INAINTE.exists() else {}
    stat = {}
    for fid, x in rez.items():
        s = stat.setdefault(x["dom"], {"n": 0, "t": dict.fromkeys(rang, 0), "i": dict.fromkeys(rang, 0), "d": dict.fromkeys(rang, 0),
                                       "p01": [0, 0], "reg": 0, "plasa": 0})
        s["n"] += 1
        s["t"][x["tester"]] += 1
        s["d"][x["dupa"]] += 1
        if fid in ina:
            s["i"][ina[fid]] += 1
            s["reg"] += rang[x["dupa"]] < rang[ina[fid]]
        if x["prio"] in ("P0", "P1"):
            s["p01"][0] += 1
            s["p01"][1] += x["dupa"] == "corect"
        s["plasa"] += not x["plasa"]
    print("Runda 8 — interpretorul local (C/P/G):")
    print(f"  {'domeniu':12s} {'n':>3s} | {'tester r8':12s} | {'înainte (verif.)':16s} | {'după (verif.)':14s} | P0/P1 corecte | regresii | plasă ruptă")
    tot = {"n": 0, "t": dict.fromkeys(rang, 0), "i": dict.fromkeys(rang, 0), "d": dict.fromkeys(rang, 0), "p01": [0, 0], "reg": 0, "plasa": 0}
    for dom, s in stat.items():
        for k in ("t", "i", "d"):
            for r in rang:
                tot[k][r] += s[k][r]
        for k in ("n", "reg", "plasa"):
            tot[k] += s[k]
        tot["p01"][0] += s["p01"][0]
        tot["p01"][1] += s["p01"][1]
    for dom, s in list(stat.items()) + [("TOTAL", tot)]:
        cpg = lambda d: f"{d['corect']}/{d['partial']}/{d['gresit']}"  # noqa: E731
        print(f"  {dom:12s} {s['n']:3d} | {cpg(s['t']):12s} | {cpg(s['i']) if ina else '—':16s} | {cpg(s['d']):14s} | "
              f"{s['p01'][1]:3d}/{s['p01'][0]:<9d} | {s['reg']:8d} | {s['plasa']}")
    for fid, x in rez.items():
        if x["dupa"] != "corect" or verbose or not x["plasa"]:
            print(f"    {fid} ({x['prio']}): tester {x['tester']}, înainte {ina.get(fid, '—')} → {x['dupa']}"
                  + (f"  lipsă: {'; '.join(x['lipsa'])}" if x["lipsa"] else "") + ("" if x["plasa"] else "  [PLASĂ]")
                  + (f"  | {x['text'][:110]!r}" if verbose or x["dupa"] != "corect" else ""))
    if not fara_vechi:
        print("\nRundele 5 + 6 + 7 (regresii):")
        _spec = importlib.util.spec_from_file_location("reverificare_r7", RAD / "teste" / "r7" / "reverificare.py")
        r7 = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(r7)
        r7.main(verbose=False)
    return rez


if __name__ == "__main__":
    main(verbose="-v" in sys.argv, fara_vechi="--fara-vechi" in sys.argv, salveaza_inainte="--salveaza-inainte" in sys.argv)
