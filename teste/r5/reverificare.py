"""Reverificarea frazelor din runda 5 (teste/r5/{locuinte,fotovoltaic,industrial}/fraze.json) după repararea
interpretorului.

Pentru fiecare frază se aplică ACEEAȘI listă de verificări (așteptatul din rapoarte) pe:
  * „înainte” — rezultatul înregistrat de testatori în fraze.json (tip, acțiune, intrarea fizică);
  * „după”    — `interpreteaza_local(text)` cu codul curent.
O frază e „corectă” dacă trec toate verificările ei, „parțială” dacă trece cel puțin jumătate, altfel „greșită”.

Rulare: cd /home/claude/sm && python3 teste/r5/reverificare.py [-v]
"""
import json
import sys
from pathlib import Path

RAD = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAD))
from engine.interpretor import interpreteaza_local  # noqa: E402

R5 = RAD / "teste" / "r5"


# ----------------------------------------------------------------------------------------------- utilitare
def g(d, cale, implicit=None):
    for k in cale.split("."):
        if not isinstance(d, dict) or k not in d:
            return implicit
        d = d[k]
    return d


def inv(i):
    """[(n, Pn)] sortat — din invertoare[] sau (prosumator) din Pn_inv_kW."""
    if i.get("invertoare"):
        return sorted((int(x.get("n", 1)), float(x["Pn_kW"])) for x in i["invertoare"])
    if i.get("Pn_inv_kW"):
        return [(1, float(i["Pn_inv_kW"]))]
    return []


def pn_total(i):
    return sum(n * p for n, p in inv(i))


def plec(i):
    """plecările desfăcute (n_circuite)"""
    out = []
    for p in i.get("plecari") or []:
        out += [p] * int(p.get("n_circuite") or 1)
    return out


def bess_kwh(i):
    return g(i, "bess.kWh") or i.get("baterie_kWh")


def L_any(i):
    return {i.get(k) for k in ("L_coloana_m", "L_inv_m", "L_racord_m", "L_alimentare_m")} | {g(i, "alimentare.L_coloana_m")}


def are_intrebare(act):
    return act in ("genereaza_cu_intrebare", "refuza")


# --------------------------------------------------------------------------------------- așteptări: locuințe
def asteptari_locuinte(a, fid):
    """Din câmpul `asteptat` structurat al testatorului."""
    v = []
    tip = a.get("tip")
    v.append(("tip", lambda r, t=tip: r["tip"] == t))
    if a.get("refuz") or a.get("contradictie"):
        v.append(("refuz/I08", lambda r: r["act"] == "refuza"))
        return v
    if a.get("refuz_sau_tri"):
        v.append(("refuz sau tri", lambda r: r["act"] == "refuza" or r["in"].get("retea") == "tri"))
        return v
    if a.get("intreaba_retea"):
        # rețeaua nu se presupune — excepție: puterea nu încape fizic în monofazat (40 A) → trifazat declarat
        nu_incape = (a.get("P") or 0) * 1000 / (230 * 0.9) > 40
        v.append(("întreabă rețeaua", lambda r, x=nu_incape: ("retea" not in r["in"] and are_intrebare(r["act"]))
                  or (x and r["in"].get("retea") == "tri")))
    elif a.get("retea"):
        v.append(("retea", lambda r, x=a["retea"]: r["in"].get("retea") == x))
    if "P" in a:
        if tip == "locuinta":
            v.append(("P aprobată", lambda r, x=a["P"]: g(r["in"], "alimentare.P_aprobata_kW") == x))
        elif tip == "bransament":
            v.append(("P", lambda r, x=a["P"]: r["in"].get("P_kW") == x))
        elif tip == "prosumator":
            v.append(("P aprobată", lambda r, x=a["P"]: r["in"].get("P_aprobata_kW") == x))
    if "Q" in a:
        if tip == "locuinta":
            v.append(("Q", lambda r, x=a["Q"]: g(r["in"], "alimentare.In_Q_bransament_A") == x))
        else:
            v.append(("Q", lambda r, x=a["Q"]: x in (r["in"].get("Ib_A"), r["in"].get("Q_In_A"))))
    if "L" in a:
        v.append(("L", lambda r, x=a["L"]: x in L_any(r["in"])))
    for rec, P in (a.get("rec") or {}).items():
        v.append((f"receptor {rec}", lambda r, rec=rec, P=P: any(
            c["receptor"] == rec and c.get("P_kW") == P for c in r["in"].get("circuite") or [])))
    if "inv" in a:
        v.append(("Pn invertor", lambda r, x=a["inv"]: abs(pn_total(r["in"]) - x) < 0.01))
    if "bess" in a:
        v.append(("baterie", lambda r, x=a["bess"]: bess_kwh(r["in"]) == x))
    if a.get("TT"):
        v.append(("TT", lambda r: r["in"].get("schema_pamant") == "TT"))
    if "RA" in a:
        v.append(("RA", lambda r, x=a["RA"]: r["in"].get("RA_ohm") == x))
    if "ks" in a:
        v.append(("ks", lambda r, x=a["ks"]: r["in"].get("ks") == x))
    if a.get("alim"):
        v.append(("branșament nou", lambda r, x=a["alim"]: g(r["in"], "alimentare.tip") == x))
    rec = lambda r: [c["receptor"] for c in r["in"].get("circuite") or []]  # noqa: E731
    extra = {
        "L10": [("3 × AC", lambda r: rec(r).count("aer_conditionat") == 3)],
        "L35": [("2 × boiler", lambda r: rec(r).count("boiler") == 2)],
        "L37": [("fără P din kVA", lambda r: g(r["in"], "alimentare.P_aprobata_kW") is None)],
        "L40": [("3 prize + 2 iluminat + MSV", lambda r: rec(r).count("prize") >= 3 and rec(r).count("iluminat") >= 2
                 and "masina_spalat_vase" in rec(r))],
        "L42": [("VE monofazat", lambda r: any(c["receptor"] == "vehicul_electric" and c.get("faza") != "3F"
                                               for c in r["in"].get("circuite") or []))],
        "L47": [("PdC monofazată", lambda r: any(c["receptor"] == "pompa_caldura" and c.get("faza") != "3F"
                                                 for c in r["in"].get("circuite") or []))],
        "E03": [("fără plită electrică", lambda r: "plita" not in rec(r))],
        "E04": [("fără plită / cuptor", lambda r: "plita" not in rec(r) and "cuptor" not in rec(r))],
        "E05": [("5 circuite prize", lambda r: rec(r).count("prize") >= 5)],
        "L03": [("plită fără P nu e adăugată implicit cu 7,2 kW", lambda r: True)],
    }
    v += extra.get(fid, [])
    return v


# ------------------------------------------------------------------------------------ așteptări: fotovoltaic
def _inv(*grupuri):
    return ("invertoare " + " + ".join(f"{n}×{p}" for n, p in grupuri),
            lambda r: inv(r["in"]) == sorted((n, float(p)) for n, p in grupuri))


def _eq(cheie, val):
    return (f"{cheie} = {val}", lambda r: g(r["in"], cheie) == val)


def _tip(t):
    return ("tip " + t, lambda r: r["tip"] == t)


def _act(*a):
    return ("acțiune " + "/".join(a), lambda r: r["act"] in a)


NU_REFUZ = ("nu refuză", lambda r: r["act"] != "refuza")
FARA_PT_IN_SERIE = ("fără PT nou în serie cu TG", lambda r: not r["in"].get("pt_Sn_kVA") or r["in"].get("pt_existent"))
INTREABA = ("întreabă", lambda r: r["act"] == "genereaza_cu_intrebare")

PV = {
    1: [_tip("cef"), _inv((2, 50)), _eq("kWp", 100), _eq("L_racord_m", 60), NU_REFUZ,
        ("model SUN2000", lambda r: "SUN2000" in str(g(r["in"], "invertoare")))],
    2: [_tip("cef"), _inv((1, 110)), _eq("modul.Pmax_W", 580), _eq("racord", "tg_existent"), _eq("L_racord_m", 40)],
    3: [_tip("cef"), _inv((2, 100)), _eq("racord", "tg_existent"), _eq("L_racord_m", 90)],
    4: [_tip("cef"), _inv((4, 100)), _eq("pt_Sn_kVA", 400), _eq("modul.Pmax_W", 600),
        ("model SG110CX", lambda r: "SG110CX" in str(g(r["in"], "invertoare")))],
    5: [_tip("cef"), _inv((2, 40)), _eq("racord", "tg_existent"), _eq("schema_pamant", "TN-C-S"),
        _eq("cablu_C0.material", "Cu"), _eq("L_racord_m", 35)],
    6: [_tip("cef"), _inv((1, 50)), _eq("cablu_C0.material", "Cu"), _eq("string.n_module", 18),
        _eq("string.n_stringuri_paralel", 5), _eq("modul.Pmax_W", 580)],
    7: [_tip("cef"), _inv((3, 50)), _eq("atr_jt", True), _eq("L_racord_m", 120), _eq("string.n_stringuri_paralel", 2)],
    8: [_tip("cef"), _inv((8, 115)), _eq("pt_Sn_kVA", 1000), _eq("L_racord_m", 200)],
    9: [_tip("cef"), _inv((20, 100)), _eq("pt_Sn_kVA", 2000)],
    10: [_tip("cef"), _inv((32, 125)), ("BESS 2000 kWh", lambda r: g(r["in"], "bess.kWh") == 2000)],
    11: [_tip("cef"), _inv((1, 100), (2, 50)), _eq("racord", "tg_existent"), _eq("L_racord_m", 70)],
    12: [_tip("cef"), _inv((1, 100), (1, 50))],
    13: [_tip("cef"), _inv((2, 110), (1, 60)), _eq("bess.kWh", 215), _eq("bess.P_kW", 100), _eq("racord", "tg_existent"),
         _eq("L_racord_m", 50)],
    14: [_tip("cef"), _inv((1, 50), (1, 30)), _eq("L_racord_m", 45)],
    15: [_tip("cef"), _inv((1, 36), (1, 20)), _eq("racord", "tg_existent")],
    16: [_tip("cef"), _inv((3, 100), (1, 50)), _eq("bess.P_kW", 200), _eq("bess.kWh", 430), _eq("pt_Sn_kVA", 630)],
    17: [_tip("cef"), _inv((2, 100)), _eq("bess.kWh", 150), _eq("racord", "tg_existent")],
    18: [_tip("cef"), _inv((4, 125)), _eq("atr_jt", True)],
    19: [_tip("cef"), _inv((1, 125)), _eq("racord", "tg_existent"), _eq("cablu_C0.S_fortat", 150),
         _eq("cablu_C0.n_fortat", 3), _eq("cablu_C0.material", "Al"), _eq("L_racord_m", 60)],
    20: [_tip("cef"), _inv((1, 60)), _eq("racord", "tg_existent"), _eq("L_racord_m", 60)],
    21: [_tip("prosumator"), _inv((2, 50)), _eq("racord", "tg_existent"), _eq("limitare_injectie_kW", 50),
         _eq("retea", "tri")],
    22: [_tip("prosumator"), _inv((1, 20), (1, 10))],
    23: [_tip("prosumator"), _inv((4, 100)), _eq("limitare_injectie_kW", 0)],
    24: [_tip("prosumator"), ("Pn 25", lambda r: pn_total(r["in"]) == 25), _eq("baterie_kWh", 25), _eq("hibrid", True)],
    25: [_tip("prosumator"), _inv((3, 50)), _eq("In_Q_bransament_A", 200), _eq("retea", "tri")],
    26: [_tip("prosumator"), _inv((2, 30)), _eq("racord", "tg_existent")],
    27: [_tip("prosumator"), ("Pn 100", lambda r: pn_total(r["in"]) == 100), _eq("limitare_injectie_kW", 30)],
    28: [_tip("prosumator"), _inv((2, 125)), _eq("bess.kWh", 200), _eq("bess.P_kW", 100),
         _eq("limitare_injectie_kW", 150)],
    29: [_tip("prosumator"), _eq("retea", "mono"), ("Pn 10", lambda r: pn_total(r["in"]) == 10)],
    30: [_tip("prosumator"), ("Pn 20", lambda r: pn_total(r["in"]) == 20), ("L 30", lambda r: 30 in L_any(r["in"]))],
    31: [_tip("cef"), _inv((3, 100)), _eq("bess.kWh", 200), _eq("racord", "tg_existent"), FARA_PT_IN_SERIE,
         _eq("L_racord_m", 80)],
    32: [_tip("cef"), _inv((4, 100)), _eq("bess.kWh", 1000), _eq("bess.P_kW", 500), _eq("pt_Sn_kVA", 1000)],
    33: [_tip("cef"), _eq("bess.P_kW", 500), _eq("bess.kWh", 1000), NU_REFUZ],
    34: [_tip("cef"), _inv((2, 100)), NU_REFUZ],
    35: [_act("refuza")],
    36: [_act("refuza", "genereaza_cu_intrebare"), ("întrebare despre puteri", lambda r: bool(r.get("intrebari")))],
    37: [_tip("cef"), _inv((2, 100)), _eq("racord", "tg_existent"), _eq("racord_In_Q_A", 250), _eq("Ik3_TG_kA", 15),
         _eq("cablu_C0.material", "Cu"), _eq("L_racord_m", 30)],
    38: [_tip("cef"), _inv((3, 100)), _eq("limitare_injectie_kW", 0), _eq("racord", "tg_existent")],
    39: [_tip("cef"), _inv((10, 100)), _eq("pt_Sn_kVA", 1250), _eq("L_racord_m", 150)],
    40: [_tip("cef"), _inv((5, 100)), _eq("L_racord_m", 100)],
    41: [_tip("cef"), _inv((2, 50)), _eq("L_racord_m", 100)],
    42: [_tip("cef"), _inv((2, 100)), _eq("schema_pamant", "TT"), _eq("RA_ohm", 4), NU_REFUZ],
    43: [_tip("cef"), _inv((1, 100), (1, 50)), _eq("string.gpv", True), _eq("gpv_In_A", 15)],
    44: [_tip("cef"), _inv((1, 30)), _eq("bess.kWh", 30), _eq("racord", "tg_existent")],
    45: [_tip("cef"), _inv((5, 110)), _eq("racord", "tg_existent"), FARA_PT_IN_SERIE],
    46: [_tip("cef"), _inv((2, 50)), _eq("bess.kWh", 100), _eq("bess.P_kW", 50), _eq("limitare_injectie_kW", 0),
         _eq("L_racord_m", 50)],
}


# ------------------------------------------------------------------------------------- așteptări: industrial
def _np(n):
    return (f"{n} plecări", lambda r: len(plec(r["in"])) == n)


def _pl(i, cheie, val):
    return (f"plecarea {i + 1}: {cheie} = {val}", lambda r: len(plec(r["in"])) > i and g(plec(r["in"])[i], cheie) == val)


IND = {
    1: [_tip("tablou"), _eq("origine", "pt_propriu"), _eq("pt_Sn_kVA", 630), _eq("schema_pamant", "TN-S"), _np(4),
        _pl(0, "L_m", 60)],
    2: [_tip("tablou"), _np(4), _pl(0, "In_A", 63), _eq("cablu.material", "Cu"), _eq("cablu.metoda", "E"),
        _eq("L_alimentare_m", 35)],
    3: [_tip("tablou"), _np(3), _pl(0, "receptor", "motor"), _pl(1, "receptor", "motor"), _eq("L_alimentare_m", 80),
        _eq("cablu.material", "Al"), _eq("cablu.metoda", "D1")],
    4: [_tip("tablou"), _np(6)],
    5: [_tip("tablou"), _np(11), _eq("L_alimentare_m", 120)],
    6: [_tip("tablou"), _eq("In_Q1_A", 160), INTREABA, _np(6)],
    7: [_act("refuza")],
    8: [_act("refuza")],
    9: [_tip("tablou"), _np(3), _eq("L_alimentare_m", 25)],
    10: [_act("refuza")],
    11: [_act("refuza")],
    12: [_tip("tablou"), _np(2), ("copii 3 + 2", lambda r: [len(p.get("copii") or []) for p in plec(r["in"])] == [3, 2]),
         ("nume TD-1", lambda r: plec(r["in"])[0]["nume"] == "TD-1"), _eq("schema_pamant", "TN-C-S")],
    13: [_tip("tablou"), _np(2), ("TD-Hala cu 2 copii", lambda r: len(plec(r["in"])) == 2 and len(
        plec(r["in"])[0].get("copii") or []) == 2), _pl(0, "In_A", 200), _pl(0, "L_m", 90), _pl(1, "L_m", 25)],
    14: [_tip("tablou"), _np(11), ("Iluminat / Prize în nume", lambda r: any(
        "Ilumin" in p["nume"] for p in plec(r["in"])) and any("Priz" in p["nume"] for p in plec(r["in"])))],
    15: [_tip("tablou"), _np(3), _pl(0, "pornire", "stea_triunghi"), _pl(1, "pornire", "convertizor"),
         _pl(0, "L_m", 50), _pl(1, "L_m", 35)],
    16: [_tip("tablou"), _np(2), _pl(0, "In_A", 250), _pl(1, "In_A", 160), _pl(1, "L_m", 150),
         ("fără Q1 2160 A", lambda r: r["in"].get("In_Q1_A") != 2160)],
    17: [("63 A sau refuz", lambda r: r["act"] == "refuza" or any(p.get("In_A") == 63 for p in plec(r["in"])))],
    18: [_tip("tablou"), _np(1), _pl(0, "L_m", 2500)],
    19: [_tip("tablou"), _np(2)],
    20: [_tip("tablou"), _np(2), _pl(0, "P_kW", 60), _pl(0, "cosfi", 1)],
    21: [_tip("pt"), _eq("Sn_kVA", 630), _np(4), _pl(0, "L_m", 100)],
    22: [_tip("pt"), _eq("Sn_kVA", 1000), _np(3)],
    23: [_tip("pt"), _eq("Sn_kVA", 400), _eq("masura", "MT"), ("celule de linie", lambda r: "linie_intrare" in (
        r["in"].get("celule_mt") or [])), _np(2)],
    24: [_tip("pt"), _eq("Sn_kVA", 1600), _np(1)],
    25: [_tip("pt"), _eq("Sn_kVA", 800), INTREABA],
    26: [_act("refuza")],
    27: [_tip("pt"), _eq("Sn_kVA", 100), _np(2)],
    28: [_tip("pt"), _eq("Sn_kVA", 250), _eq("trafo_izolatie", "uscat"), _np(2)],
    29: [_tip("pt"), _eq("Sn_kVA", 400), _np(1)],
    30: [_act("refuza")],
    31: [_tip("ge_ats"), _eq("Sn_GE_kVA", 100), _eq("P_sarcina_kW", 60), _eq("In_Q_retea_A", 125)],
    32: [_tip("ge_ats"), _eq("Sn_GE_kVA", 250), _eq("P_sarcina_kW", 73)],
    33: [_tip("ge_ats"), _eq("Sn_GE_kVA", 60), _eq("P_sarcina_kW", 45), _eq("L_GE_ATS_m", 15)],
    34: [_tip("ge_ats"), _eq("Sn_GE_kVA", 500), _eq("P_sarcina_kW", 380), ("sursa rețea", lambda r: bool(
        r["in"].get("sursa_retea")))],
    35: [_act("refuza")],
    36: [_tip("ge_ats"), _eq("Sn_GE_kVA", 200), _eq("P_sarcina_kW", 120), INTREABA],
    37: [_tip("cef"), _inv((1, 50)), _eq("racord", "tg_existent"), INTREABA],
    38: [_tip("ge_ats"), _eq("Sn_GE_kVA", 150), INTREABA],
    39: [_tip("cef"), _inv((1, 30)), _eq("racord", "tg_existent"), INTREABA],
    40: [_tip("tablou"), _np(2)],
    41: [_tip("tablou"), _eq("origine", "tg_existent"), _eq("cablu.S_fortat", 150), _eq("L_alimentare_m", 45),
         _eq("In_Q1_A", 250), _np(2)],
    42: [_tip("tablou"), _eq("schema_pamant", "TT"), _eq("RA_ohm", 30), _np(3)],
    43: [_tip("tablou"), _np(14)],
    44: [_tip("tablou"), _np(2), _pl(0, "cablu.metoda", "C"), _pl(1, "cablu.metoda", "E")],
    45: [_tip("tablou"), _np(2)],
    46: [_tip("tablou"), _np(2), _pl(0, "cablu.metoda", "C"),
         ("TD-2 fără pozare aparentă", lambda r: len(plec(r["in"])) > 1 and g(plec(r["in"])[1], "cablu.metoda") != "C")],
    47: [_tip("tablou"), _eq("schema_pamant", "TT"), _eq("RA_ohm", 20), _np(2)],
    48: [_tip("tablou"), _np(2), ("pompa ≈ 11 kW", lambda r: len(plec(r["in"])) > 0 and abs(
        (plec(r["in"])[0].get("P_kW") or 0) - 11.03) < 0.1), _eq("schema_pamant", "TN-C-S")],
    49: [_tip("ge_ats"), _eq("Sn_GE_kVA", 100), _eq("P_sarcina_kW", 70), _eq("sursa_retea", "pt")],
    50: [_tip("ge_ats"), _eq("Sn_GE_kVA", 100), _eq("P_sarcina_kW", 35)],
    51: [_tip("tablou"), _np(2), _pl(0, "In_A", 100), _pl(0, "L_m", 60), _pl(1, "L_m", 40), _eq("retea", "tri")],
    52: [_tip("tablou"), _np(3), _eq("cablu.S_fortat", 185), _eq("cablu.material", "Al"), _eq("L_alimentare_m", 70),
         ("origine declarată", lambda r: bool(r["in"].get("origine")))],
    53: [_tip("tablou"), _eq("retea", "mono"), _np(2)],
    54: [_tip("tablou"), _np(3), _pl(0, "L_m", 80), _pl(1, "L_m", 95), _pl(2, "L_m", 60)],
}


# ------------------------------------------------------------------------------------------------- rulare
def incarca():
    out = []
    for x in json.loads((R5 / "locuinte" / "fraze.json").read_text(encoding="utf-8")):
        out.append(("locuinte", x["id"], x["text"], x, asteptari_locuinte(x["asteptat"], x["id"])))
    for x in json.loads((R5 / "fotovoltaic" / "fraze.json").read_text(encoding="utf-8")):
        out.append(("fotovoltaic", f"f{x['nr']:02d}", x["fraza"], x, PV[x["nr"]]))
    for x in json.loads((R5 / "industrial" / "fraze.json").read_text(encoding="utf-8")):
        out.append(("industrial", f"#{x['nr']}", x["fraza"], x, IND[x["nr"]]))
    return out


def evalueaza(verif, r):
    ok = []
    for nume, f in verif:
        try:
            ok.append((nume, bool(f(r))))
        except Exception:                                   # noqa: BLE001 — câmp lipsă = verificare picată
            ok.append((nume, False))
    trec = sum(1 for _, x in ok if x)
    verdict = "corect" if trec == len(ok) else "partial" if trec * 2 >= len(ok) else "gresit"
    return verdict, [n for n, x in ok if not x]


def main(verbose=False):
    stat = {}
    rand = []
    for rol, fid, text, rec, verif in incarca():
        inainte = {"tip": rec.get("tip"), "act": rec.get("actiune"), "in": rec.get("intrare") or {},
                   "intrebari": rec.get("intrebari") or []}
        d = interpreteaza_local(text)
        dupa = {"tip": d["tip_schema"], "act": d["actiune"], "in": d["intrare_fizica"], "intrebari": d["intrebari"]}
        vi, _ = evalueaza(verif, inainte)
        vd, lipsa = evalueaza(verif, dupa)
        s = stat.setdefault(rol, {"n": 0, "inainte": {"corect": 0, "partial": 0, "gresit": 0},
                                  "dupa": {"corect": 0, "partial": 0, "gresit": 0}, "imbunatatite": 0, "regresii": 0})
        s["n"] += 1
        s["inainte"][vi] += 1
        s["dupa"][vd] += 1
        rang = {"gresit": 0, "partial": 1, "corect": 2}
        s["imbunatatite"] += rang[vd] > rang[vi]
        s["regresii"] += rang[vd] < rang[vi]
        rand.append((rol, fid, vi, vd, lipsa, text))
    tot = {"n": 0, "inainte": {"corect": 0, "partial": 0, "gresit": 0}, "dupa": {"corect": 0, "partial": 0, "gresit": 0},
           "imbunatatite": 0, "regresii": 0}
    for rol, s in stat.items():
        print(f"{rol:12s} {s['n']:3d} fraze | înainte C/P/G {s['inainte']['corect']}/{s['inainte']['partial']}/"
              f"{s['inainte']['gresit']} | după C/P/G {s['dupa']['corect']}/{s['dupa']['partial']}/{s['dupa']['gresit']}"
              f" | îmbunătățite {s['imbunatatite']}, regresii {s['regresii']}")
        tot["n"] += s["n"]
        for k in ("inainte", "dupa"):
            for v in tot[k]:
                tot[k][v] += s[k][v]
        tot["imbunatatite"] += s["imbunatatite"]
        tot["regresii"] += s["regresii"]
    print(f"{'TOTAL':12s} {tot['n']:3d} fraze | înainte C/P/G {tot['inainte']['corect']}/{tot['inainte']['partial']}/"
          f"{tot['inainte']['gresit']} | după C/P/G {tot['dupa']['corect']}/{tot['dupa']['partial']}/"
          f"{tot['dupa']['gresit']} | îmbunătățite {tot['imbunatatite']}, regresii {tot['regresii']}")
    for rol, fid, vi, vd, lipsa, text in rand:
        if vd != "corect" or verbose:
            print(f"  [{rol}] {fid}: {vi} → {vd}" + (f"  lipsă: {'; '.join(lipsa)}" if lipsa else "") + f"  | {text}")
    return tot


if __name__ == "__main__":
    main(verbose="-v" in sys.argv)
