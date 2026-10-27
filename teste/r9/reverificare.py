"""Reverificarea rundei 9 (teste/r9/{locuinte,fotovoltaic,industrial}/fraze.json) + rundele 5–8 după reparațiile r9 ale
INTERPRETORULUI LOCAL (regulile, fără Claude).

Pentru fiecare frază r9 P0 / P1 se aplică o listă de verificări scrisă din „așteptat” + observația testerului (nu din
ce face codul). Frazele P2 / fără observații pe care testerul le-a găsit CORECTE sunt păzite de regresii cu o amprentă
(tip, acțiune, rețea, schema de pământ, P aprobată, invertoare, nr. plecări / circuite, baterie) luată înainte de
reparații (teste/r9/reverificare_inainte.json, `--salveaza-inainte`); o diferență de amprentă = de analizat.
  * „tester” — verdictul testerului r9 (fraze.json);
  * „înainte” — verificările pe codul de dinainte de reparațiile r9;
  * „după”    — `interpreteaza_local(text)` cu codul curent.
O frază e „corectă” dacă trec toate verificările, „parțială” dacă trece cel puțin jumătate, altfel „greșită”.
Plasa de siguranță (r6): o frază cu rest neconsumat nu iese „genereaza” fără mențiune.
Rundele 5–8 se reiau cu teste/r8/reverificare.py (regresii).

Rulare: cd /home/claude/sm && python3 teste/r9/reverificare.py [-v] [--fara-vechi]
"""
import importlib.util
import json
import sys
from pathlib import Path

RAD = Path(__file__).resolve().parents[2]
R9 = RAD / "teste" / "r9"
sys.path.insert(0, str(RAD))
from engine import constructor, validare  # noqa: E402
from engine.interpretor import interpreteaza_local  # noqa: E402

_spec = importlib.util.spec_from_file_location("reverificare_r8", RAD / "teste" / "r8" / "reverificare.py")
r8 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r8)

_f, C, evalueaza, plasa_ok = r8._f, r8.C, r8.evalueaza, r8.plasa_ok
Q, I, gen, coduri, inv, pl, gaseste, circ, rec, pa, apx, n_sum = (r8.Q, r8.I, r8.gen, r8.coduri, r8.inv, r8.pl, r8.gaseste,
                                                                  r8.circ, r8.rec, r8.pa, r8.apx, r8.n_sum)
tip, eq, PA, RET, SP, INV, PN, REC, NREC, KWH, INTREABA, FARA_Q, NP, PLEC = (
    r8.tip, r8.eq, r8.PA, r8.RET, r8.SP, r8.INV, r8.PN, r8.REC, r8.NREC, r8.KWH, r8.INTREABA, r8.FARA_Q, r8.NP, r8.PLEC)
GENEREAZA, NU_REFUZ, INTREABA_ORI_REFUZ, FARA_NEC, FARA_BESS = (r8.GENEREAZA, r8.NU_REFUZ, r8.INTREABA_ORI_REFUZ,
                                                                r8.FARA_NEC, r8.FARA_BESS)
L, T, PR, CEF, PT, GE = r8.L, r8.T, r8.PR, r8.CEF, r8.PT, r8.GE
F_INAINTE = R9 / "reverificare_inainte.json"


def rezultat(text):
    return C(r=interpreteaza_local(text))


def TD(nume, L_m=None, S=None, **rec_n):
    """tablou secundar de locuință: nume (fragment), lungime, secțiune, receptori (cel puțin n)"""
    def f(c):
        for t in I(c).get("tablouri_secundare") or []:
            if nume not in _f(t.get("nume")):
                continue
            if L_m is not None and t.get("L_m") != L_m:
                continue
            if S is not None and (t.get("cablu") or {}).get("S_fortat") != S:
                continue
            cc = t.get("circuite") or []
            if all(sum(1 for x in cc if x.get("receptor") == r) >= n for r, n in rec_n.items()):
                return True
        return False
    return (f"TD „{nume}”" + (f" {L_m} m" if L_m else "") + (f" S {S}" if S else "")
            + "".join(f" {n}×{r}" for r, n in rec_n.items()), f)


def NREC_TG(r, n):
    return (f"TG: exact {n} × {r}", lambda c: len(rec(c, r)) == n)


APART = ("set de apartament (fără exterior / centrală)", lambda c: not any(
    "exterior" in _f(x.get("nume")) or x.get("receptor") == "centrala_termica" for x in circ(c)))
NU_CONTRAD = ("fără contradicție falsă", lambda c: "contradic" not in _f(Q(c)))


def CIRC_L(r, L_m, P=None):
    return (f"{r} la {L_m} m" + (f" {P} kW" if P else ""), lambda c: any(
        x.get("L_m") == L_m and (P is None or x.get("P_kW") == P) for x in rec(c, r)))


def COL_NU(L_m):
    return (f"coloana ≠ {L_m} m", lambda c: (I(c).get("alimentare") or {}).get("L_coloana_m") != L_m)


def SIG_NUME(cuv, da=True):
    return (f"„{cuv}” {'=' if da else '≠'} siguranță", lambda c: bool(gaseste(pl(c) + (I(c).get("consumatori") or []), cuv))
            and all((p.get("siguranta") is True) if da else (p.get("siguranta") is False)
                    for p in gaseste(pl(c) + (I(c).get("consumatori") or []), cuv)))


def NPL_P(P, n, **k):
    return (f"{n} plecări de {P}" + "".join(f" {a}={b}" for a, b in k.items()), lambda c: n_sum(
        [p for p in pl(c) if apx(p.get("P_kW"), P, 0.01) and all(p.get(a) == b for a, b in k.items())]) == n)


def MOTOR_FARA(*cod):
    """verificare end-to-end: motorul nu emite codurile BLOCANT date"""
    return ("motor fără BLOCANT " + "/".join(cod), lambda c: c.get("v") is not None and not (set(cod) & coduri(c, "BLOCANT")))


def MOTOR_NPAR(n):
    """end-to-end: motorul dimensionează C1 cu n cabluri în paralel (cablul impus păstrat până în calcul)"""
    def f(c):
        m, calc = constructor.genereaza(I(c))
        return (((calc or {}).get("rezultat") or {}).get("Q1_C1") or {}).get("n_paralel") == n
    return (f"motor: C1 cu {n} cabluri în paralel", f)


NO_PLEC_P = lambda *P: (f"fără plecări fantomă {P}", lambda c: not any(p.get("P_kW") in P or p.get("In_A") in P for p in pl(c)))  # noqa: E731

LOC = {
    2: [L, RET("mono"), PA(6), APART, REC("uscator"), REC("plita", P=3.5), REC("boiler"), REC("aer_conditionat"),
        ("schema de pământ întrebată / TN-C-S declarat", lambda c: "tn-s" in _f(Q(c)) or any("TN-C-S" in x for x in c["r"]["presupus"]))],
    3: [L, RET("tri"), PA(22), TD("etaj", 18, 6, prize=4, iluminat=2, aer_conditionat=2), NREC_TG("prize", 6),
        NREC_TG("iluminat", 3), NREC_TG("aer_conditionat", 0), COL_NU(18), FARA_NEC],
    4: [L, RET("tri"), PA(15), REC("pompa_caldura", P=9, faza="3F"), REC("cuptor", P=2.5), NU_REFUZ, NU_CONTRAD,
        FARA_Q("monofazat (230 V) sau trifazat")],
    8: [L, RET("tri"), PA(25), SP("TT"), eq("RA_ohm", 12), NREC("sauna", 1), CIRC_L("sauna", 25, 9), REC("pompa_apa", P=1.1),
        ("jacuzzi 3 kW", lambda c: any(x.get("P_kW") == 3 for x in circ(c))), FARA_NEC],
    14: [L, RET("tri"), PA(11), SP("TT"), REC("vehicul_electric", P=22),
         ("VE 22 > Pa 11 semnalat", lambda c: "22" in Q(c) and "11" in Q(c))],
    17: [L, RET("mono"), PA(8), TD("garaj", 20, 4, prize=1, iluminat=1, poarta_automata=1)],
    21: [PR, RET("tri"), PA(25), PN(24), ("2 × 12 kW", lambda c: inv(c) in ([(2, 12.0)], [(1, 12.0), (1, 12.0)])),
         FARA_Q("6 kW")],
    23: [L, RET("tri"), PA(20), ("GE 10 kVA cu ATS", lambda c: (I(c).get("ge_rezerva") or {}).get("Sn_kVA") == 10
                                  and (I(c).get("ge_rezerva") or {}).get("comutare") == "ATS"),
         ("circuitele de bază pe GE (centrală, frigider, iluminat)", lambda c: len((I(c).get("ge_rezerva") or {}).get("circuite") or []) == 3)],
    32: [("branșament / locuință", lambda c: c["r"]["tip_schema"] in ("bransament", "locuinta")), RET("tri"),
         ("P de calcul = Pa 14 (nu Pi 18)", lambda c: 14 in (pa(c), I(c).get("P_kW")) and I(c).get("P_kW") != 18),
         ("Q 3×25 A", lambda c: 25 in (I(c).get("Q_In_A"), (I(c).get("alimentare") or {}).get("In_Q_bransament_A"))),
         ("coloana Cu 10 mm² 35 m", lambda c: (I(c).get("cablu") or (I(c).get("alimentare") or {}).get("cablu") or {}).get("S_fortat") == 10
          and 35 in (I(c).get("L_coloana_m"), (I(c).get("alimentare") or {}).get("L_coloana_m"))), FARA_NEC],
    35: [L, RET("tri"), PA(24), TD("mansard", 15, 4, prize=3, iluminat=2, aer_conditionat=1),
         TD("anex", 40, 6), ("TD atelier: priză 400 V 16 A + flex 2,2 kW", lambda c: any(
             len(t.get("circuite") or []) >= 2 and any(x.get("P_kW") == 2.2 for x in t.get("circuite") or [])
             for t in I(c).get("tablouri_secundare") or [] if "atelier" in _f(t.get("nume")) or "anex" in _f(t.get("nume")))),
         FARA_NEC],
    36: [RET("mono"), ("tablou foișor: 3 × 2,5 Cu 25 m", lambda c: (
        (I(c).get("cablu") or {}).get("S_fortat") == 2.5 and (I(c).get("cablu") or {}).get("material") != "Al"
        and I(c).get("L_alimentare_m") == 25) or any(t.get("L_m") == 25 and (t.get("cablu") or {}).get("S_fortat") == 2.5
                                                    for t in I(c).get("tablouri_secundare") or [])),
         ("P ≠ Pa casei (7)", lambda c: I(c).get("P_kW") != 7), ("3 plecări (priză grătar, iluminat, priză ext.)", lambda c: n_sum(pl(c)) >= 3
                                                                   or any(len(t.get("circuite") or []) >= 3 for t in I(c).get("tablouri_secundare") or [])),
         FARA_NEC],
    38: [L, RET("tri"), PA(15), SP("TT"), REC("pompa_caldura", P=5, faza="3F"), NU_REFUZ],
    42: [L, RET("tri"), PA(16), REC("vehicul_electric", P=7.4), CIRC_L("vehicul_electric", 30), COL_NU(30)],
    44: [L, RET("mono"), PA(7), APART, REC("vehicul_electric", P=3.7), CIRC_L("vehicul_electric", 60), COL_NU(60), FARA_NEC],
    50: [L, RET("mono"), PA(6), ("GE 5 kW manual = sursă de rezervă", lambda c: (I(c).get("ge_rezerva") or {}).get("comutare") == "manual"
                                  and (I(c).get("ge_rezerva") or {}).get("Sn_kVA")),
         ("GE ≠ circuit / consumator", lambda c: not any("generator" in _f(x.get("nume")) for x in circ(c) + (I(c).get("consumatori") or [])))],
    51: [PR, RET("tri"), INV((1, 12)), KWH(15), ("P aprobată 16", lambda c: I(c).get("P_aprobata_kW") == 16), FARA_Q("total"),
         ("backup: centrală + frigider + pompă", lambda c: len((I(c).get("backup") or {}).get("circuite") or []) == 3), NU_REFUZ],
    52: [PR, RET("tri"), ("P aprobată 15", lambda c: I(c).get("P_aprobata_kW") == 15), eq("bess.kWh", 10), eq("bess.P_kW", 5),
         eq("bess.cuplaj", "ca"), ("invertorul de 8 kW marcat existent", lambda c: any(
             g.get("Pn_kW") == 8 and g.get("existent") for g in I(c).get("invertoare") or []))],
    53: [L, RET("mono"), PA(7), NU_REFUZ, ("fără PV", lambda c: not I(c).get("invertoare") and not I(c).get("Pn_inv_kW"))],
    60: [INTREABA("15", "25")],
    61: [L, RET("tri"), PA(15), ("Q 100 A > Pa 15 kW semnalat", lambda c: "100" in Q(c))],
    69: [L, RET("mono"), PA(6), APART, NREC("aer_conditionat", 2), REC("plita", P=3.5), REC("vehicul_electric", P=3.7)],
}

PV = {
    14: [CEF, INV((5, 30)), eq("racord", "tg_existent")],
    17: [CEF, INV((5, 300)), eq("masura", "MT"), eq("U_ca_V", 800), eq("pt_Sn_kVA", 1600)],
    22: [PR, RET("tri"), INV((1, 12)), KWH(19.2), ("model Deye SUN-12K-SG04LP3 (nescris „12 kW”)", lambda c: any(
        "12K" in (g.get("model") or "") for g in I(c).get("invertoare") or [])), NU_REFUZ],
    25: [CEF, INV((1, 30)), eq("racord", "tg_existent"), ("cablul invertorului NYY 5×25 (nu C0)", lambda c: (
        I(c).get("cablu_inv") or {}).get("S_fortat") == 25 and (I(c).get("cablu_C0") or {}).get("S_fortat") != 25)],
    35: [CEF, INV((1, 125), (1, 25)), eq("racord", "tg_existent"), NU_REFUZ, FARA_Q("150")],
    41: [CEF, INV((8, 100)), eq("pt_existent", True), eq("masura", "JT")],
    42: [CEF, INV((6, 110)), eq("pt_existent", True), eq("n_trafo", 2), INTREABA("T2")],
    49: [CEF, INV((10, 100)), eq("pt_Sn_kVA", 1250), eq("pt_existent", False), eq("masura", "MT"), FARA_NEC],
    55: [PR, RET("tri"), INV((1, 10), (1, 5)), ("monofazatul pe L1", lambda c: any(
        g.get("faza") == "L1" and g.get("Pn_kW") == 5 for g in I(c).get("invertoare") or [])), NU_REFUZ],
    59: [CEF, INV((4, 20)), ("racordul semnalat (întrebare peste 100 kW, avertisment „Am presupus” sub)", lambda c: "racord" in _f(Q(c)))],
    60: [INTREABA_ORI_REFUZ, ("PCS / racord întrebat", lambda c: "pcs" in _f(Q(c)) or "racord" in _f(Q(c)))],
    61: [CEF, INV((1, 125), (1, 25)), eq("racord", "bmpt"), SP("TN-C-S"), FARA_Q("476")],
    68: [CEF, INV((4, 110)), ("fără limitare TOTALĂ 100 kW", lambda c: I(c).get("limitare_injectie_kW") != 100), eq("kWp", 500),
         eq("pt_Sn_kVA", 630), ("400 kWac (4 × 100) reținut", lambda c: "100" in " ".join(c["r"]["presupus"]) or "100" in Q(c))],
}

IND = {
    2: [T, eq("origine", "tg_existent"), SP("TN-S"), NP(8), NPL_P(7.5, 2, pornire="directa"), NPL_P(18.5, 1, pornire="stea_triunghi"),
        NPL_P(55, 1, pornire="soft"), NPL_P(3, 4, pornire="convertizor"), ("P tablou ≠ 55", lambda c: I(c).get("P_kW") != 55)],
    3: [T, eq("pt_Sn_kVA", 630), NP(3), NO_PLEC_P(540, 380), PLEC("TD-Producție 250", lambda p: p.get("P_kW") == 250), FARA_NEC],
    5: [T, SP("TN-S"), RET("tri"), NPL_P(5.5, 4, pornire="stea_triunghi")],
    6: [T, eq("pt_Sn_kVA", 400), SP("TN-S"), NPL_P(15, 3), NO_PLEC_P(11), ("P tablou ≠ 15", lambda c: I(c).get("P_kW") != 15)],
    7: [T, SP("TN-S"), NP(2)],
    8: [T, ("sursa întrebată (nu BMPT tăcut)", lambda c: "surs" in _f(Q(c)))],
    11: [T, SP("TT"), ("nu locuință", lambda c: c["r"]["tip_schema"] != "locuinta"), NPL_P(1.5, 4),
         ("prize 6 circuite", lambda c: n_sum(gaseste(pl(c), "priz")) == 6), PLEC("ventilație 2,2 kW", lambda p: p.get("P_kW") == 2.2)],
    12: [INTREABA_ORI_REFUZ, ("IT medical semnalat", lambda c: "medical" in _f(Q(c)) or " it " in _f(Q(c)))],
    14: [T, eq("pt_Sn_kVA", 800), SP("TN-S"), ("TG → TD1 → TE1", lambda c: any(
        "td1" in _f(p.get("nume")) and any("te1" in _f(k.get("nume")) for k in p.get("copii") or []) for p in pl(c, False))),
         ("TD1: 3 motoare 11 kW", lambda c: any(n_sum([k for k in p.get("copii") or [] if k.get("P_kW") == 11]) == 3
                                                for p in pl(c, False) if "td1" in _f(p.get("nume")))),
         ("doar TD1 la TG", lambda c: n_sum(pl(c, False)) == 1), FARA_NEC],
    15: [T, eq("pt_Sn_kVA", 630), NU_REFUZ, NU_CONTRAD, NP(5) if False else ("TD-Etaje → TE-E1..3", lambda c: any(
        len(p.get("copii") or []) == 3 for p in pl(c, False) if "etaje" in _f(p.get("nume")))),
         ("2 plecări la TG", lambda c: n_sum(pl(c, False)) == 2),
         ("nume curate", lambda c: not any("pleaca" in _f(p.get("nume")) or "randul" in _f(p.get("nume")) for p in pl(c)))],
    16: [T, eq("pt_Sn_kVA", 400), ("TD-A (pompă, ventilator) + TD-B (iluminat)", lambda c: any(
        "td-a" in _f(p.get("nume")) and len(p.get("copii") or []) == 2 for p in pl(c, False)) and any(
        "td-b" in _f(p.get("nume")) and len(p.get("copii") or []) == 1 for p in pl(c, False))), FARA_NEC],
    20: [PT, eq("celula_trafo", "intreruptor"), eq("Q_general_tip", "ACB"), eq("In_Q_JT_A", 1600), eq("U_MT_kV", 6), NP(2)],
    21: [PT, ("fără schema TT din „TT și TC”", lambda c: I(c).get("schema_pamant") != "TT"), eq("masura", "MT"), eq("U_MT_kV", 10),
         NPL_P(None, 0) if False else ("3 plecări 200 A", lambda c: n_sum([p for p in pl(c) if p.get("In_A") == 200]) == 3)],
    24: [GE, eq("Sn_GE_kVA", 200), SIG_NUME("lift pompieri"), SIG_NUME("iluminat siguranta"),
         ("normalii (HVAC, prize) nu sunt pe GE (vital: false)", lambda c: all(
             x.get("vital") is False for x in gaseste(I(c).get("consumatori") or [], "hvac") + gaseste(I(c).get("consumatori") or [], "priz"))
          and (I(c).get("P_sarcina_kW") or 0) < 100),
         NU_REFUZ],
    25: [T, SIG_NUME("sprinkler"), SIG_NUME("jockey"), SIG_NUME("rampe", False), SIG_NUME("iluminat", False),
         ("TG mixt (nu tot de siguranță)", lambda c: not I(c).get("siguranta_tablou"))],
    26: [T, SIG_NUME("desfumare"), SIG_NUME("presurizare"), SIG_NUME("cta", False),
         ("TD mixt", lambda c: not I(c).get("siguranta_tablou"))],
    27: [GE, eq("Sn_GE_kVA", 100), ("electropompe 30 kW siguranță, 1A+1R", lambda c: any(
        x.get("siguranta") and x.get("P_kW") == 30 and (x.get("n") in ("1+1", 2) or x.get("rezerva"))
        for x in I(c).get("consumatori") or [])), SIG_NUME("pilot"), FARA_NEC],
    32: [PT, eq("Sn_kVA", 800), eq("compensare_kvar", 150), ("3 plecări 250 A", lambda c: n_sum([p for p in pl(c) if p.get("In_A") == 250]) == 3)],
    33: [PT, eq("Sn_kVA", 630), NU_REFUZ, ("compensare 120 kvar automată (+ 20 fixă)", lambda c: I(c).get("compensare_kvar") in (120, 140)),
         ("4 plecări 250 A", lambda c: n_sum([p for p in pl(c) if p.get("In_A") == 250]) == 4)],
    34: [T, SP("TN-C-S"), eq("cablu.n_paralel", 2), eq("cablu.S_fortat", 185), eq("L_alimentare_m", 60), NP(2),
         MOTOR_NPAR(2), eq("cablu.tip_cablu", "CYABY")],
    35: [T, SP("TN-S"), SIG_NUME("incendiu"), SIG_NUME("iluminat", False),
         ("pompa: cablu impus 4×10 FE180 70 m", lambda c: any(
             (p.get("cablu") or {}).get("S_fortat") == 10 and p.get("L_m") == 70 for p in gaseste(pl(c), "incendiu"))),
         ("70 m nu e pe alimentare", lambda c: I(c).get("L_alimentare_m") != 70), FARA_NEC],
    37: [T, ("Q1 40 A < Ib semnalat", lambda c: "40" in Q(c) and c["r"]["actiune"] != "genereaza")],
    43: [T, NPL_P(1, 6, retea="mono"), ("8 prize mono", lambda c: n_sum([p for p in pl(c) if p.get("In_A") == 16 and p.get("retea") == "mono"]) == 8),
         ("4 CEE 32 A tri", lambda c: n_sum([p for p in pl(c) if p.get("In_A") == 32]) == 4)],
    44: [T, RET("tri"), NPL_P(0.6, 12, retea="mono")],
    49: [T, NU_REFUZ, NPL_P(90, 2, pornire="soft"), ("rezerva marcată", lambda c: any(p.get("rezerva") or "rezerv" in _f(p.get("nume")) for p in pl(c))),
         NPL_P(45, 1, pornire="convertizor"), NP(3)],
    50: [T, NPL_P(22, 4), NPL_P(50, 1), FARA_NEC],
    52: [T, NP(4), ("BMPT 160 A cu TC (origine)", lambda c: I(c).get("origine") == "bmpt" or "160" in str(I(c).get("In_Q_amonte_A") or I(c).get("_In_Q_amonte_A")))],
    53: [T, eq("pt_Sn_kVA", 630), SP("TN-S"), NPL_P(30, 2, pornire="stea_triunghi"), NPL_P(4, 4, pornire="directa"),
         NPL_P(10, 1), ("6 circuite prize", lambda c: n_sum(gaseste(pl(c), "priz")) == 6)],
    54: [T, RET("tri"), NP(3), ("P tablou ≠ 1,5", lambda c: I(c).get("P_kW") != 1.5)],
    63: [T, ("lift pompieri = siguranță", lambda c: I(c).get("siguranta_tablou") or any(p.get("siguranta") for p in pl(c))),
         ("18 kW folosit", lambda c: any(p.get("P_kW") == 18 for p in pl(c)))],
    66: [T, RET("tri"), SP("TN-C-S"), eq("origine", "bmpt"), NO_PLEC_P(100), NPL_P(7.5, 5, pornire="directa")],
    67: [GE, eq("Sn_GE_kVA", 400), ("3 extrudere 90 kW (Σ 270)", lambda c: (I(c).get("P_sarcina_kW") or 0) == 270), FARA_NEC],
    68: [T, ("pod rulant consumat", lambda c: not any("pod" in _f(x) for x in c["r"]["neconsumat"])),
         ("motoarele podului cu demaror (sau plecare pod rulant)", lambda c: any("pod" in _f(p.get("nume")) for p in pl(c, False))
          or all(p.get("pornire") for p in pl(c)))],
    70: [INTREABA_ORI_REFUZ, ("BMPM vs trifazat întrebat", lambda c: "bmpm" in _f(Q(c)))],
    71: [T, eq("origine", "tg_existent"), PLEC("chiller 120 kW", lambda p: p.get("P_kW") == 120 and "chiller" in _f(p.get("nume")))],
}


# ------------------------------------------------------------------------------------------------- amprentă (regresii)
def amprenta(r):
    i = r.get("intrare_fizica") or {}
    return {"tip": r.get("tip_schema"), "act": "genereaza" if r["actiune"] != "refuza" else "refuza",
            "retea": i.get("retea"), "sp": i.get("schema_pamant"),
            "pa": i.get("P_aprobata_kW", (i.get("alimentare") or {}).get("P_aprobata_kW")),
            "inv": sorted([g.get("n", 1), g.get("Pn_kW")] for g in i.get("invertoare") or []),
            "npl": n_sum(pl({"r": r})), "nc": len(i.get("circuite") or []),
            "kwh": (i.get("bess") or {}).get("kWh") or i.get("baterie_kWh")}


def AMPR(a):
    return [(f"amprentă {k}={v}", (lambda k, v: lambda c: amprenta(c["r"])[k] == v)(k, v)) for k, v in a.items()]


# ------------------------------------------------------------------------------------------------- încărcare / rulare
def _v(v):
    v = _f(v)
    return "corect" if v.startswith("c") else "partial" if v.startswith("p") else "gresit"


DOM = (("locuinte", LOC, "text", "sev"), ("fotovoltaic", PV, "fraza", "prioritate"), ("industrial", IND, "text", "severitate"))


def incarca(ampr=None):
    """[(domeniu, id, text, verdict tester, prioritate, verificări)] — P0/P1 cu verificări explicite, restul corecte
    cu amprenta de dinainte (dacă există)."""
    if ampr is None:
        ampr = json.loads(F_INAINTE.read_text(encoding="utf-8")).get("amprente", {}) if F_INAINTE.exists() else {}
    out = []
    for dom, V, kt, kp in DOM:
        for x in json.loads((R9 / dom / "fraze.json").read_text(encoding="utf-8")):
            p = x.get(kp) or "-"
            p = p if p in ("P0", "P1", "P2") else "-"
            fid = f"{dom[0].upper()}{x['id']:02d}"
            if x["id"] in V:
                verif = V[x["id"]]
            elif _v(x["verdict"]) == "corect" and fid in ampr:
                verif = AMPR(ampr[fid])
            else:
                verif = []
            out.append((dom, fid, x[kt], _v(x["verdict"]), p, verif))
    return out


def ruleaza():
    rez = {}
    for dom, fid, text, vt, prio, verif in incarca():
        c = rezultat(text)
        v, lipsa = evalueaza(verif, c) if verif else ("corect", [])
        rez[fid] = {"dom": dom, "tester": vt, "prio": prio, "dupa": v, "lipsa": lipsa, "plasa": plasa_ok(c["r"]),
                    "text": text, "nec": c["r"]["neconsumat"], "ampr": amprenta(c["r"]), "explicit": prio in ("P0", "P1")}
    return rez


def main(verbose=False, fara_vechi=False, salveaza_inainte=False):
    rang = {"gresit": 0, "partial": 1, "corect": 2}
    rez = ruleaza()
    if salveaza_inainte:
        F_INAINTE.write_text(json.dumps({"verdicte": {k: v["dupa"] for k, v in rez.items()},
                                         "amprente": {k: v["ampr"] for k, v in rez.items()}}, ensure_ascii=False, indent=0),
                             encoding="utf-8")
    ina = json.loads(F_INAINTE.read_text(encoding="utf-8")).get("verdicte", {}) if F_INAINTE.exists() else {}
    stat, tot = {}, None
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
    print("Runda 9 — interpretorul local (C/P/G; P0/P1 cu verificări explicite, restul corecte păzite de amprentă):")
    print(f"  {'domeniu':12s} {'n':>3s} | {'tester r9':12s} | {'înainte (verif.)':16s} | {'după (verif.)':14s} | P0/P1 corecte | regresii | plasă ruptă")
    tot = {"n": 0, "t": dict.fromkeys(rang, 0), "i": dict.fromkeys(rang, 0), "d": dict.fromkeys(rang, 0), "p01": [0, 0], "reg": 0, "plasa": 0}
    for s in stat.values():
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
        print("\nRundele 5 + 6 + 7 + 8 (regresii):")
        r8.main(verbose=False)
    return rez


if __name__ == "__main__":
    main(verbose="-v" in sys.argv, fara_vechi="--fara-vechi" in sys.argv, salveaza_inainte="--salveaza-inainte" in sys.argv)
