"""Reverificarea rundei 10 (teste/r10/{locuinte,fotovoltaic,industrial}) + rundele 5–9 după reparațiile r10 ale
INTERPRETORULUI LOCAL (regulile, fără Claude).

Pentru fiecare frază r10 P0 / P1 (și câteva P2 din clasele reparate) se aplică o listă de verificări scrisă din
„așteptat” + observația testerului (nu din ce face codul). Restul frazelor sunt păzite doar de plasa de siguranță și de
regula „nimic blocat fără întrebare” (clasa 8).
  * „tester” — verdictul testerului r10 (tabelele din *.md, respectiv fraze.json la fotovoltaic);
  * „înainte” — verificările pe codul de dinainte de reparațiile r10 (teste/r10/reverificare_inainte.json);
  * „după”    — `interpretor.interpreteaza(text)` (calea aplicației fără cheie API: regulile locale + întrebările din
                 verificarea motorului) cu codul curent.
O frază e „corectă” dacă trec toate verificările, „parțială” dacă trece cel puțin jumătate, altfel „greșită”.

Rulare: cd /home/claude/sm && python3 teste/r10/reverificare.py [-v] [--fara-vechi]
"""
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

RAD = Path(__file__).resolve().parents[2]
R10 = RAD / "teste" / "r10"
if os.environ.get("SM_ENGINE_RAD"):                 # „înainte”: o copie a pachetului engine de dinaintea reparațiilor
    sys.path.insert(0, os.environ["SM_ENGINE_RAD"])
sys.path.insert(1 if os.environ.get("SM_ENGINE_RAD") else 0, str(RAD))
from engine import interpretor  # noqa: E402

_spec = importlib.util.spec_from_file_location("reverificare_r9", RAD / "teste" / "r9" / "reverificare.py")
r9 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r9)
r8 = r9.r8

_f, C, evalueaza, plasa_ok = r8._f, r8.C, r8.evalueaza, r8.plasa_ok
Q, I, coduri, inv, pl, gaseste, circ, rec, pa, apx, n_sum = (r8.Q, r8.I, r8.coduri, r8.inv, r8.pl, r8.gaseste, r8.circ,
                                                             r8.rec, r8.pa, r8.apx, r8.n_sum)
tip, eq, PA, RET, SP, INV, PN, REC, NREC, KWH, INTREABA, FARA_Q, NP, PLEC = (
    r8.tip, r8.eq, r8.PA, r8.RET, r8.SP, r8.INV, r8.PN, r8.REC, r8.NREC, r8.KWH, r8.INTREABA, r8.FARA_Q, r8.NP, r8.PLEC)
GENEREAZA, NU_REFUZ, INTREABA_ORI_REFUZ, FARA_NEC = r8.GENEREAZA, r8.NU_REFUZ, r8.INTREABA_ORI_REFUZ, r8.FARA_NEC
L, T, PR, CEF, PT, GE = r8.L, r8.T, r8.PR, r8.CEF, r8.PT, r8.GE
TD, NREC_TG, NPL_P, SIG_NUME, NU_CONTRAD = r9.TD, r9.NREC_TG, r9.NPL_P, r9.SIG_NUME, r9.NU_CONTRAD
F_INAINTE = R10 / "reverificare_inainte.json"


def rezultat(text):
    try:
        r = interpretor.interpreteaza(text)
    except TypeError:
        r = interpretor.interpreteaza_local(text)
    return C(r=r)


# ------------------------------------------------------------------------------------------------- verificări noi
def _g(d, cheie):
    for k in cheie.split("."):
        d = d.get(k) if isinstance(d, dict) else None
    return d


def al(c):
    return I(c).get("alimentare") or {}


def QB(v):
    """Q-ul branșamentului (locuință: alimentare.In_Q_bransament_A; PV / branșament: In_Q_bransament_A)"""
    return (f"Q branșament {v} A", lambda c: v in (al(c).get("In_Q_bransament_A"), I(c).get("In_Q_bransament_A"),
                                                   I(c).get("Q_In_A")))


BLOC_INTREBAT = ("BLOCANT motor → întrebare (nu fundătură)", lambda c: not ((c.get("v") or {}).get("blocheaza"))
                 or (c["r"]["actiune"] != "genereaza" and bool(c["r"]["intrebari"])))


def MOTOR_FARA_BLOCANT():
    return ("motorul nu blochează", lambda c: c.get("v") is not None and not c["v"]["blocheaza"])


def TOATE_REC(c):
    """toți receptorii: circuitele casei, ale tablourilor secundare, plecările tabloului"""
    out = list(circ(c)) + list(pl(c))
    for t in I(c).get("tablouri_secundare") or []:
        out += t.get("circuite") or []
    for k in ("backup", "ge_rezerva"):
        out += (I(c).get(k) or {}).get("circuite") or []
    return out


def CNT(cuv_sau_rec, n, P=None):
    def f(c):
        xs = [x for x in TOATE_REC(c) if x.get("receptor") == cuv_sau_rec
              or (x.get("receptor") in (None, "", "prize", "iluminat", "motor", "aer_conditionat") and cuv_sau_rec in _f(x.get("nume"))
                  and (not x.get("receptor") or x.get("receptor").startswith(cuv_sau_rec[:4])))]
        xs = [x for x in xs if P is None or apx(x.get("P_kW"), P, 0.01)]
        return sum(int(x.get("n_circuite") or (x.get("n") if isinstance(x.get("n"), int) else 1)) for x in xs) == n
    return (f"{n} × „{cuv_sau_rec}”" + (f" {P} kW" if P else ""), f)


def INV_F(*faze):
    return ("invertoare pe faze " + "/".join(faze), lambda c: sorted(
        f for g in I(c).get("invertoare") or [] for f in [g.get("faza")] * int(g.get("n", 1)) if f) == sorted(faze))


def EXIST(Pn, n=None):
    return (f"invertor {Pn} kW marcat existent", lambda c: any(
        g.get("existent") and g.get("Pn_kW") == Pn and (n is None or g.get("n", 1) == n) for g in I(c).get("invertoare") or []))


def NOU(Pn, n=None):
    return (f"invertor {Pn} kW nou (neexistent)", lambda c: any(
        not g.get("existent") and g.get("Pn_kW") == Pn and (n is None or g.get("n", 1) == n) for g in I(c).get("invertoare") or []))


def BACKUP(*cuv):
    return ("backup / EPS: " + ", ".join(cuv), lambda c: all(any(
        w in _f(x.get("nume")) or w == x.get("receptor") for x in (I(c).get("backup") or {}).get("circuite") or []) for w in cuv))


def CU_Q(*cuv):
    """o întrebare (cu generare sau refuz) care conține toate cuvintele (în întrebări / refuz)"""
    return ("întrebare „" + " + ".join(cuv) + "”", lambda c: c["r"]["actiune"] != "genereaza" and all(
        _f(w) in _f(" ".join(c["r"]["intrebari"]) + " " + (c["r"].get("refuz_motiv") or "")) for w in cuv))


def NU_TIP(*t):
    return ("tip ≠ " + "/".join(t), lambda c: c["r"]["tip_schema"] not in t)


def PL_RE(desc, f, n=None):
    return (desc, lambda c: (sum(int(p.get("n_circuite") or 1) for p in pl(c) if f(p)) == n) if n is not None
            else any(f(p) for p in pl(c)))


NU_PLEC_NUME = lambda *cuv: (f"fără plecări „{'/'.join(cuv)}”", lambda c: not any(  # noqa: E731
    any(w in _f(p.get("nume")) for w in cuv) for p in TOATE_REC(c)))
FARA_ATR_INUTIL = FARA_Q("Nu am folosit")
VE = "vehicul_electric"

LOC = {
    1: [L, RET("mono"), PA(5), REC("plita", P=7.2), BLOC_INTREBAT, CU_Q("plit")],
    2: [L, RET("tri"), PA(15), CNT("prize", 8), CNT("iluminat", 6), REC("pompa_caldura", P=9),
        ("fără „prize 6 kW”", lambda c: not any(x.get("receptor") == "prize" and x.get("P_kW") == 6 for x in TOATE_REC(c))),
        FARA_NEC],
    3: [L, RET("tri"), QB(25), REC(VE, P=11), BLOC_INTREBAT, CU_Q("DLM")],
    9: [PR, RET("mono"), PN(5), KWH(5), BACKUP("frigider", "central")],
    10: [L, RET("mono"), QB(32), ("GE 8 kVA manual", lambda c: _g(I(c), "ge_rezerva.Sn_kVA") == 8
                                   and _g(I(c), "ge_rezerva.comutare") == "manual"), BLOC_INTREBAT],
    14: [L, CNT("prize", 5), CNT("iluminat", 3), PA(4),
         ("fără „prize 3 kW”", lambda c: not any(x.get("P_kW") == 3 for x in TOATE_REC(c))), INTREABA("monofaz")],
    16: [("doar TD-ul anexei (fără casă tipică)", lambda c: not any(x.get("receptor") in ("plita", "boiler", "masina_spalat_rufe")
                                                                     for x in TOATE_REC(c))),
         ("cablu 5×6 60 m", lambda c: 6 in (_g(I(c), "cablu.S_fortat"), _g(al(c), "cablu.S_fortat"))
          and 60 in (I(c).get("L_alimentare_m"), al(c).get("L_coloana_m"), I(c).get("L_coloana_m"))),
         ("sudura 5 kVA", lambda c: any("sud" in _f(x.get("nume")) and (x.get("S_kVA") == 5 or x.get("P_kW")) for x in TOATE_REC(c))),
         CNT("priz", 2), FARA_Q("monofazat (230 V) sau trifazat"), RET("tri")],
    17: [L, RET("mono"), PA(3), REC("plita", P=3)],
    22: [PR, RET("tri"), PN(6), INV_F("L2")],
    26: [PR, RET("mono"), EXIST(5), ("baterie c.a. 10 kWh / 5 kW", lambda c: _g(I(c), "bess.kWh") == 10 and _g(I(c), "bess.P_kW") == 5),
         BLOC_INTREBAT],
    27: [PR, RET("tri"), PN(10), ("EPS pe toată casa, ATS", lambda c: _g(I(c), "backup.toata_casa") is True
                                  and _g(I(c), "backup.comutare") == "ATS"), SP("TN-C-S")],
    29: [L, RET("tri"), PA(12), REC("pompa_caldura", P=4.5), NU_REFUZ],
    30: [L, RET("mono"), PA(9), NREC("aer_conditionat", 3), REC("aer_conditionat", P=2.8), REC("aer_conditionat", 2, P=1.2)],
    31: [L, RET("tri"), PA(15), TD("piscin", 25), ("electroliza 0,3 kW", lambda c: any(x.get("P_kW") == 0.3 for x in TOATE_REC(c))),
         ("PC piscină 7 kW în TD piscină", lambda c: any(any(x.get("P_kW") == 7 for x in t.get("circuite") or [])
                                                        for t in I(c).get("tablouri_secundare") or [] if "piscin" in _f(t.get("nume"))))],
    35: [RET("tri"), QB(25), CU_Q("25", "22"), BLOC_INTREBAT],
    36: [L, RET("mono"), QB(32), BLOC_INTREBAT, CU_Q("aprobat")],
    38: [L, RET("tri"), PA(12), SP("TN-C-S"), ("separarea PEN declarată", lambda c: "pen" in _f(" ".join(c["r"]["presupus"]))),
         BLOC_INTREBAT],
    39: [CNT("priz", 4), CNT("ilumin", 3), ("AC 3,5 kW", lambda c: any(apx(x.get("P_kW"), 3.5, 0.01) for x in TOATE_REC(c))),
         RET("mono"), ("titlul nu e „TG general”", lambda c: "general" not in _f(I(c).get("titlu_tablou") or ""))],
    40: [L, RET("tri"), PA(15), ("GE 15 kVA cu ATS", lambda c: _g(I(c), "ge_rezerva.Sn_kVA") == 15
                                         and _g(I(c), "ge_rezerva.comutare") == "ATS")],
    43: [PR, RET("tri"), PN(5), INV_F("L1"), QB(25)],
    48: [L, RET("tri"), QB(25), ("P aprobată ≈ 13,5 kW (din 15 kVA)", lambda c: apx(pa(c), 13.5, 0.01))],
    49: [L, RET("mono"), PA(9), ("coloana 3×6 45 m", lambda c: _g(al(c), "cablu.S_fortat") == 6 and al(c).get("L_coloana_m") == 45)],
    51: [L, RET("tri"), SP("TN-C-S"), eq("RA_ohm", 30), ("RA 30 Ω > 4 Ω semnalat", lambda c: "30" in Q(c) and "4" in Q(c))],
    54: [L, RET("tri"), PA(15), NREC(VE, 1), REC(VE, P=7.4), REC("plita", P=7), NU_CONTRAD, NU_REFUZ],
    55: [L, RET("mono"), PA(6), REC("masina_spalat_rufe", P=2.2), REC("masina_spalat_vase", P=2), REC("plita", P=7.2),
         NREC("aer_conditionat", 2), BLOC_INTREBAT],
    56: [L, RET("tri"), QB(32), PA(18), TD("parter"), TD("etaj"), NU_PLEC_NUME("total", "la intrare"),
         ("încălzitoare prosop 0,5 kW", lambda c: any(x.get("P_kW") == 0.5 for x in TOATE_REC(c)))],
    60: [L, RET("tri"), QB(32), TD("corp", 40), ("corp B 5 kW", lambda c: any(t.get("P_kW") == 5 or any(
        x.get("P_kW") == 5 for x in t.get("circuite") or []) for t in I(c).get("tablouri_secundare") or [])), FARA_NEC],
    66: [PR, RET("tri"), PN(12), KWH(15), BACKUP("frigider", "central", "router", "ilumin"),
         ("fără BESS c.a. independent", lambda c: _g(I(c), "bess.cuplaj") != "ca"), SP("TN-C-S")],
    67: [L, RET("tri"), PA(22), NREC(VE, 2), REC(VE, P=11), REC(VE, P=7.4)],
    # P2 din clasele reparate (date de branșament evidente)
    7: [PR, RET("tri"), QB(32), FARA_ATR_INUTIL],
    8: [PR, QB(63), FARA_ATR_INUTIL],
    25: [PR, QB(100), FARA_ATR_INUTIL],
    57: [PR, QB(32), FARA_ATR_INUTIL],
    58: [PR, PN(34.8), FARA_ATR_INUTIL],
}

PV = {
    3: [INV((2, 30), (1, 20)), QB(160), NU_REFUZ],
    4: [PR, KWH(10)],
    9: [INV((2, 20), (2, 50)), EXIST(20, 2), NOU(50, 2), NU_REFUZ],
    12: [CEF, INV((3, 30)), FARA_NEC],
    15: [CEF, INV((4, 100)), eq("pt_existent", True), eq("n_trafo", 2), eq("bara", "T1"), eq("racord_In_Q_A", 630)],
    20: [CEF, INV((3, 50)), eq("racord", "tg_existent"), eq("limitare_injectie_kW", 100)],
    34: [CEF, INV((10, 50), (10, 50)) if False else PN(1000), eq("masura", "JT"), eq("pt_Sn_kVA", 1250),
         ("2 tablouri TGD-CF a câte 10", lambda c: sorted(g.get("tgd") for g in I(c).get("invertoare") or []
                                                         for _ in range(int(g.get("n", 1)))).count(1) == 10)],
    39: [CU_Q("zero", "40"), FARA_Q("2 × 33")],
    41: [PR, RET("tri"), PN(18), INV_F("L1", "L2", "L3"), FARA_Q("57")],
    42: [PR, RET("tri"), PN(6), INV_F("L1"), QB(25)],
    43: [CEF, PN(50), EXIST(20), NOU(30)],
    46: [CEF, INV((2, 50)), eq("racord", "tg_existent"), ("model curat SG50CX", lambda c: all(
        (g.get("model") or "SG50CX") == "SG50CX" for g in I(c).get("invertoare") or [])),
         ("PT-ul Electrica nu e PT propriu", lambda c: not I(c).get("pt_Sn_kVA") or I(c).get("pt_existent") is not False)],
    47: [CEF, INV((3, 100)), ("BESS LUNA 200 kWh", lambda c: _g(I(c), "bess.kWh") == 200), eq("pt_Sn_kVA", 630)],
    50: [INV((1, 30)), ("cablul 5×16 Cu 120 m pe circuitul invertorului", lambda c: _g(I(c), "cablu_inv.S_fortat") == 16
                         and I(c).get("L_inv_m") == 120)],
    51: [INV((1, 100)), ("cablul impus 5×35 păstrat, cu lungime (verificat de motor)", lambda c: 35 in (
        _g(I(c), "cablu_inv.S_fortat"), _g(I(c), "cablu_C0.S_fortat")) and (I(c).get("L_racord_m") or I(c).get("L_inv_m"))),
         ("lungimea cablului impus întrebată", lambda c: "lungime" in _f(Q(c)))],
    53: [PN(130), QB(200), eq("Ik3_OD_kA", 8.5), ("Iac 206 > 200 întrebat", lambda c: "200" in Q(c))],
    56: [INV((3, 33)), EXIST(33, 3), ("BESS c.a. 100 kW / 200 kWh", lambda c: _g(I(c), "bess.kWh") == 200 and _g(I(c), "bess.P_kW") == 100)],
    57: [CU_Q("hibrid"), ("SG110CX nu e desenat hibrid", lambda c: not any(g.get("hibrid") for g in I(c).get("invertoare") or []))],
    58: [INV((1, 100)), eq("limitare_injectie_kW", 70)],
    61: [PR, PN(75), INV_F(*["L1"] * 5 + ["L2"] * 5 + ["L3"] * 5)],
    62: [CEF, INV((1, 100), (1, 110))],
    63: [CEF, INV((10, 100)), ("limitare / evacuare 800 kW", lambda c: 800 in (I(c).get("limitare_injectie_kW"), I(c).get("P_evacuata_kW"))),
         FARA_NEC],
    64: [CEF, INV((3, 50)), eq("racord_In_Q_A", 250), eq("racord_Q_tip", "gG")],
    65: [CEF, INV((4, 100)), NU_REFUZ],
    66: [CEF, INV((2, 150)), eq("racord", "tg_existent")],
}

IND = {
    3: [T, SP("TT"), ("BMPT 63 A = sursa (origine)", lambda c: I(c).get("origine") == "bmpt"),
        NU_PLEC_NUME("bmpt"), NP(16)],
    4: [T, NU_REFUZ, ("pompe 1+1 (rezervă)", lambda c: any(p.get("rezerva") or p.get("n") == "1+1" for p in pl(c))),
        ("cablu 5×6 80 m", lambda c: 80 in (I(c).get("L_alimentare_m"), *(p.get("L_m") for p in pl(c))))],
    5: [T, SP("TN-C-S"), NP(13)],
    8: [PT, eq("n_trafo", 2), ("cuplă JT (stare declarată sau întrebată)", lambda c: I(c).get("cupla") is not None
                                or "cupla" in _f(Q(c))), eq("masura", "MT")],
    9: [PT, NU_REFUZ, eq("pt_aerian", True), eq("Sn_kVA", 250)],
    12: [GE, NU_REFUZ, eq("Sn_GE_kVA", 250), ("nevitalii vital: false", lambda c: all(
        x.get("vital") is False for x in I(c).get("consumatori") or [] if any(w in _f(x.get("nume")) for w in ("bucat", "spalat", "hvac")))),
         ("vitalii vital: true", lambda c: all(x.get("vital") is True or x.get("siguranta") for x in I(c).get("consumatori") or []
                                               if any(w in _f(x.get("nume")) for w in ("operator", "ati", "lift"))))],
    15: [GE, SP("TT"), eq("Sn_GE_kVA", 60), eq("comutare", "manual"), BLOC_INTREBAT],
    18: [T, ("cablu 4×4 120 m pe plecarea motorului", lambda c: any(
        _g(p, "cablu.S_fortat") == 4 and p.get("L_m") == 120 for p in pl(c))), ("120 m nu e pe alimentare", lambda c: I(c).get("L_alimentare_m") != 120)],
    21: [T, NU_CONTRAD, NU_REFUZ, NP(5), NPL_P(3.6, 1, retea="mono"), NPL_P(3, 1, retea="mono")],
    22: [NU_REFUZ, FARA_Q("fără unitate"), ("ku / cosφ consumate", lambda c: not any("0,7" in x or "0,92" in x for x in c["r"]["neconsumat"]))],
    23: [T, NPL_P(18.5, 1, pornire="directa") if False else ("compresor = motor", lambda c: any(
        "compresor" in _f(p.get("nume")) and p.get("receptor") in (None, "motor") for p in pl(c))),
         ("nume corectate", lambda c: not any(w in _f(p.get("nume")) for p in pl(c) for w in ("compresr", "venitlator", "ilumnat")))],
    25: [T, NPL_P(72, 1), NU_TIP("locuinta")],
    27: [T, SP("TN-C"), ("TN-C cu 2,5 mm² semnalat", lambda c: "pen" in _f(Q(c)) or "10 mm" in _f(Q(c)))],
    31: [PT, eq("masura", "JT")],
    34: [T, NU_REFUZ, NPL_P(95, 2), ("pompe 1+1", lambda c: any(p.get("rezerva") or p.get("n") == "1+1" for p in pl(c))),
         NPL_P(0.2, 4, retea="mono")],
    35: [T, NPL_P(45, 1, pornire="convertizor"), NPL_P(30, 1, pornire="convertizor")],
    36: [T, ("UPS 100 kVA cu bypass", lambda c: any(p.get("ups") and p.get("bypass") and p.get("S_kVA") == 100 for p in pl(c))),
         NPL_P(30, 2)],
    37: [T, SP("TN-C-S"), eq("separare_PEN", "TG"), eq("cablu.S_fortat", 150), eq("L_alimentare_m", 120), BLOC_INTREBAT],
    39: [INTREABA_ORI_REFUZ, ("mono vs BMPT trifazat întrebat", lambda c: "monofaz" in _f(Q(c)) and "trifaz" in _f(Q(c)))],
    46: [T, ("4 stații × 2 × 22 kW", lambda c: n_sum([p for p in pl(c) if p.get("P_kW") == 22]) == 8
              or n_sum([p for p in pl(c) if p.get("P_kW") == 44]) == 4)],
    48: [PT, eq("masura", "MT"), eq("Sn_kVA", 1000)],
    49: [PT, NU_REFUZ, eq("U_MT_kV", 20), NU_CONTRAD],
    53: [("PT 630 uscat (nu „pentru”)", lambda c: 630 in (I(c).get("Sn_kVA"), I(c).get("pt_Sn_kVA"))
          and I(c).get("trafo_izolatie") == "uscat")],
    54: [T, ("pompa de rezervă", lambda c: any(p.get("rezerva") or p.get("n") == "1+1" for p in pl(c)))],
    56: [T, NPL_P(90, 1, pornire="stea_triunghi"), ("70 m pe plecare", lambda c: any(p.get("L_m") == 70 for p in pl(c))),
         ("70 m nu e pe alimentare", lambda c: I(c).get("L_alimentare_m") != 70)],
    57: [T, NU_REFUZ, NP(5), eq("ks", 0.7), eq("cosfi", 0.85), eq("cablu.S_fortat", 25)],
    58: [T, NPL_P(3, 1), NPL_P(90, 1, pornire="soft")],
    60: [T, eq("origine", "tg_existent"), NPL_P(5.5, 3), ("cablu 5×10 60 m", lambda c: 60 in (
        I(c).get("L_alimentare_m"), *(p.get("L_m") for p in pl(c))))],
    62: [NU_REFUZ, NPL_P(50, 6)],
    64: [T, NPL_P(11, 2), NPL_P(2.2, 4)],
    68: [("PT 630 kVA (nu 400)", lambda c: 630 in (I(c).get("pt_Sn_kVA"), I(c).get("Sn_kVA"))), NU_REFUZ,
         FARA_Q("puterea trafo")],
    # P0
    30: [("2 trafo în paralel (cuplă închisă)", lambda c: I(c).get("n_trafo") == 2 and _f(I(c).get("cupla")) in ("inchisa", "ni", "paralel"))],
    41: [T, NU_TIP("locuinta"), SP("TT"), ("BMPT 63 A sursă", lambda c: I(c).get("origine") == "bmpt"), NP(9),
         NU_PLEC_NUME("baie", "bucatarie")],
    43: [GE, eq("fara_retea", True), eq("Sn_GE_kVA", 500)],
    45: [T, ("plecarea VE: DDR tip B", lambda c: any("B" in (_g(p, "ddr.tip"), _g(p, "DDR.tip")) for p in pl(c))),
         ("45 m pe plecare", lambda c: any(p.get("L_m") == 45 for p in pl(c))), NPL_P(22, 1)],
    47: [eq("sursa_rezerva", "trafo"), ("fără GE inventat", lambda c: not I(c).get("Sn_GE_kVA")), eq("n_trafo", 2)],
    61: [SIG_NUME("incendiu"), NPL_P(45, 1)],
    65: [eq("uk_pct", 4)],
    67: [GE, NU_REFUZ, ("cuptoarele vital: false", lambda c: all(x.get("vital") is False for x in gaseste(I(c).get("consumatori") or [], "cupto"))
                        and gaseste(I(c).get("consumatori") or [], "cupto")),
         ("pompele vital: true", lambda c: all(x.get("vital") is True for x in gaseste(I(c).get("consumatori") or [], "pomp"))
          and gaseste(I(c).get("consumatori") or [], "pomp"))],
}


# ------------------------------------------------------------------------------------------------- încărcare / rulare
def _v(v):
    v = _f(v)
    return "corect" if v.startswith("c") else "partial" if v.startswith("p") else "gresit"


def _tabel_md(f: Path, col_v: int, col_p: int) -> dict:
    """verdictele testerului din tabelul complet al raportului (id → (verdict, prioritate))"""
    out = {}
    txt = f.read_text(encoding="utf-8")
    txt = txt[txt.index("## Tabel complet"):]
    for linie in txt.splitlines():
        cel = [x.strip() for x in linie.strip().strip("|").split("|")]
        if len(cel) <= max(col_v, col_p) or not re.match(r"^i?\d+$", cel[0]):
            continue
        p = re.sub(r"[^P0-9]", "", cel[col_p].replace("*", ""))
        out[int(cel[0].lstrip("i"))] = (_v(cel[col_v]), p if p in ("P0", "P1", "P2") else "-")
    return out


def incarca():
    """[(domeniu, id, text, verdict tester, prioritate, verificări)]"""
    out = []
    md = _tabel_md(R10 / "locuinte.md", 3, 4)
    for x in json.loads((R10 / "locuinte" / "fraze.json").read_text(encoding="utf-8")):
        v, p = md.get(x["id"], ("-", "-"))
        out.append(("locuinte", f"L{x['id']:02d}", x["text"], v, p, LOC.get(x["id"], [])))
    for x in json.loads((R10 / "fotovoltaic" / "fraze.json").read_text(encoding="utf-8")):
        p = x.get("prioritate") or "-"
        out.append(("fotovoltaic", f"F{x['id']:02d}", x["fraza"], _v(x["verdict"]), p if p in ("P0", "P1", "P2") else "-",
                    PV.get(x["id"], [])))
    md = _tabel_md(R10 / "industrial.md", 2, 3)
    for k, x in json.loads((R10 / "industrial" / "fraze.json").read_text(encoding="utf-8")).items():
        n = int(k[1:])
        v, p = md.get(n, ("-", "-"))
        out.append(("industrial", f"I{n:02d}", x["text"], v, p, IND.get(n, [])))
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


def main(verbose=False, fara_vechi=False, salveaza_inainte=False):
    rang = {"gresit": 0, "partial": 1, "corect": 2}
    rez = ruleaza()
    if salveaza_inainte:
        F_INAINTE.write_text(json.dumps({"verdicte": {k: v["dupa"] for k, v in rez.items()}}, ensure_ascii=False, indent=0),
                             encoding="utf-8")
    ina = json.loads(F_INAINTE.read_text(encoding="utf-8")).get("verdicte", {}) if F_INAINTE.exists() else {}
    stat = {}
    tot = {"n": 0, "t": dict.fromkeys(rang, 0), "i": dict.fromkeys(rang, 0), "d": dict.fromkeys(rang, 0), "p01": [0, 0],
           "reg": 0, "plasa": 0}
    for fid, x in rez.items():
        s = stat.setdefault(x["dom"], {"n": 0, "t": dict.fromkeys(rang, 0), "i": dict.fromkeys(rang, 0),
                                       "d": dict.fromkeys(rang, 0), "p01": [0, 0], "reg": 0, "plasa": 0})
        for d in (s, tot):
            d["n"] += 1
            if x["tester"] in rang:
                d["t"][x["tester"]] += 1
            d["d"][x["dupa"]] += 1
            if fid in ina:
                d["i"][ina[fid]] += 1
                d["reg"] += rang[x["dupa"]] < rang[ina[fid]]
            if x["prio"] in ("P0", "P1"):
                d["p01"][0] += 1
                d["p01"][1] += x["dupa"] == "corect"
            d["plasa"] += not x["plasa"]
    print("Runda 10 — interpretorul local (C/P/G; P0/P1 cu verificări explicite, restul: plasa + „nimic blocat fără întrebare”):")
    print(f"  {'domeniu':12s} {'n':>3s} | {'tester r10':12s} | {'înainte (verif.)':16s} | {'după (verif.)':14s} | P0/P1 corecte | regresii | plasă ruptă")
    cpg = lambda d: f"{d['corect']}/{d['partial']}/{d['gresit']}"  # noqa: E731
    for dom, s in list(stat.items()) + [("TOTAL", tot)]:
        print(f"  {dom:12s} {s['n']:3d} | {cpg(s['t']):12s} | {cpg(s['i']) if ina else '—':16s} | {cpg(s['d']):14s} | "
              f"{s['p01'][1]:3d}/{s['p01'][0]:<9d} | {s['reg']:8d} | {s['plasa']}")
    for fid, x in rez.items():
        if x["dupa"] != "corect" or verbose or not x["plasa"]:
            print(f"    {fid} ({x['prio']}): tester {x['tester']}, înainte {ina.get(fid, '—')} → {x['dupa']}"
                  + (f"  lipsă: {'; '.join(x['lipsa'])}" if x["lipsa"] else "") + ("" if x["plasa"] else "  [PLASĂ]")
                  + (f"  | {x['text'][:110]!r}" if verbose or x["dupa"] != "corect" else ""))
    if not fara_vechi:
        print("\nRundele 5–9 (regresii):")
        r9.main(verbose=False)
    return rez


if __name__ == "__main__":
    main(verbose="-v" in sys.argv, fara_vechi="--fara-vechi" in sys.argv, salveaza_inainte="--salveaza-inainte" in sys.argv)
