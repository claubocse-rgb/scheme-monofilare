"""Reverificarea frazelor din rundele 5 și 6 după reparațiile r6 ale interpretorului (plasa de siguranță + clasele de
greșeli din teste/r6/{locuinte,fotovoltaic,industrial}.md).

Pentru fiecare frază se aplică ACEEAȘI listă de verificări (așteptatul din rapoarte) pe:
  * „înainte” — rezultatul înregistrat de testatori în runda 6 (teste/r6/*/fraze.json, reverificare_r5.json);
  * „după”    — `interpreteaza_local(text)` cu codul curent.
O frază e „corectă” dacă trec toate verificările ei, „parțială” dacă trece cel puțin jumătate, altfel „greșită”.
Verificarea comună tuturor frazelor (r6, cerința 1): o frază cu rest neconsumat nu iese „genereaza” fără mențiune.

Rulare: cd /home/claude/sm && python3 teste/r6/reverificare.py [-v]
"""
import importlib.util
import json
import sys
from pathlib import Path

RAD = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAD))
from engine.interpretor import interpreteaza_local  # noqa: E402

R6 = RAD / "teste" / "r6"
_spec = importlib.util.spec_from_file_location("reverificare_r5", RAD / "teste" / "r5" / "reverificare.py")
r5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r5)
g, inv, plec, evalueaza = r5.g, r5.inv, r5.plec, r5.evalueaza
_inv, _eq, _tip, _act, _np, _pl = r5._inv, r5._eq, r5._tip, r5._act, r5._np, r5._pl
NU_REFUZ, INTREABA = r5.NU_REFUZ, r5.INTREABA
INTREABA_SAU_REFUZ = ("întreabă / refuză", lambda r: r["act"] in ("genereaza_cu_intrebare", "refuza"))
REFUZ = _act("refuza")


def _ne(cheie, val):
    return (f"{cheie} ≠ {val}", lambda r: g(r["in"], cheie) != val)


def _pl_any(desc, f):
    return (desc, lambda r: any(f(p) for p in plec(r["in"])))


# ------------------------------------------------------------------------------------------- locuințe (r6)
def asteptari_locuinte_r6(a, fid):
    """Așteptatul structurat din teste/r6/locuinte/fraze.json (tip „a|b” acceptat, „intreaba”)."""
    a = dict(a)
    tipuri = a.pop("tip").split("|")
    v = []
    a["tip"] = tipuri[0]
    baza = r5.asteptari_locuinte(a, fid)
    v.append(("tip " + "|".join(tipuri), lambda r, t=tuple(tipuri): r["tip"] in t))
    for nume, f in baza[1:]:
        if len(tipuri) > 1 and nume in ("P", "P aprobată", "Q"):          # cheia depinde de tip — orice formă
            v.append((nume, lambda r, x=a.get("P") if nume.startswith("P") else a.get("Q"), k=nume: x in (
                r["in"].get("P_kW"), g(r["in"], "alimentare.P_aprobata_kW"), r["in"].get("P_aprobata_kW"))
                if k.startswith("P") else x in (r["in"].get("Q_In_A"), g(r["in"], "alimentare.In_Q_bransament_A"))))
            continue
        v.append((nume, f))
    if a.get("intreaba") and not a.get("contradictie"):
        v.append(INTREABA_SAU_REFUZ)
    rec = lambda r: [c["receptor"] for c in r["in"].get("circuite") or []]  # noqa: E731
    extra = {
        "N04": [("3 AC + PdC 10 kW", lambda r: rec(r).count("aer_conditionat") == 3)],
        "N08": [("atelierul = tablou secundar (strung, compresor, prize; 40 m)", lambda r: [
            (t.get("L_m"), len(t.get("circuite") or [])) for t in r["in"].get("tablouri_secundare") or []] == [(40, 3)])],
        "N14": [("fără întrebare BESS", lambda r: not any("stocare" in q for q in r["intrebari"]))],
        "N18": [("cuplajul bateriei întrebat", lambda r: any("cuplat" in q for q in r["intrebari"]))],
        "N22": [("cuplajul bateriei întrebat", lambda r: any("cuplat" in q for q in r["intrebari"]))],
        "N34": [("pompa piscină păstrată", lambda r: "pompa_apa" in rec(r))],
        "N37": [("coloana Al 2,5 impusă", lambda r: g(r["in"], "alimentare.cablu.S_fortat") == 2.5)],
        "N39": [("3 AC", lambda r: rec(r).count("aer_conditionat") == 3)],
        "N41": [("saună L 30 m", lambda r: any(c["receptor"] == "sauna" and c.get("L_m") == 30
                                              for c in r["in"].get("circuite") or []))],
        "N44": [("cuplajul bateriei întrebat", lambda r: any("cuplat" in q for q in r["intrebari"]))],
        "N50": [("tablou din TG existent", lambda r: r["tip"] == "tablou" and r["in"].get("origine") == "tg_existent"),
                INTREABA],
        "N51": [("coloana 4x10 Cu impusă", lambda r: g(r["in"], "cablu.S_fortat") == 10)],
        "N53": [("încălzire în pardoseală 4 kW", lambda r: any(c["receptor"] == "incalzire_electrica" and c.get("P_kW") == 4
                                                              for c in r["in"].get("circuite") or []))],
    }
    return v + extra.get(fid, [])


# ---------------------------------------------------------------------------------------- fotovoltaic (r6)
PT_NU_EXISTENT = _ne("pt_existent", True)
PV6 = {
    "f01": [_tip("cef"), _inv((1, 50)), _eq("racord", "tg_existent"), _eq("schema_pamant", "TN-C-S"),
            _eq("cablu_C0.material", "Al"), _eq("L_racord_m", 35)],
    "f02": [_inv((1, 110)), _eq("string.n_module", 16), _eq("string.n_stringuri_paralel", 12), _eq("racord", "bmpt"),
            _eq("L_racord_m", 70)],
    "f03": [_inv((2, 110)), _eq("racord", "tg_existent"), _eq("Ik3_TG_kA", 20), _eq("racord_In_Q_A", 400)],
    "f04": [_inv((3, 100)), _eq("pt_Sn_kVA", 400), PT_NU_EXISTENT, _eq("L_racord_m", 120)],
    "f05": [_inv((4, 110)), _eq("pt_Sn_kVA", 630), _eq("schema_pamant", "TN-S"), PT_NU_EXISTENT],
    "f06": [_inv((5, 115)), _eq("pt_Sn_kVA", 1000), _eq("pt_existent", True), _eq("cablu_C0.S_fortat", 240),
            _eq("cablu_C0.material", "Al"), _eq("L_racord_m", 180)],
    "f07": [_inv((6, 125)), _eq("pt_Sn_kVA", 1000), PT_NU_EXISTENT],
    "f08": [_inv((8, 125)), _eq("pt_Sn_kVA", 1250), _ne("racord", "tg_existent"), PT_NU_EXISTENT, _eq("L_racord_m", 250)],
    "f09": [_inv((10, 115)), _eq("pt_Sn_kVA", 1600), PT_NU_EXISTENT],
    "f10": [_inv((2, 50), (1, 50)), _eq("racord", "tg_existent"), _eq("cablu_C0.material", "Cu"), _eq("L_racord_m", 40)],
    "f11": [_inv((1, 100), (1, 50)), _eq("racord", "tg_existent"), _eq("L_racord_m", 60)],
    "f12": [_inv((2, 110), (1, 50)), _eq("racord_In_Q_A", 630)],
    "f13": [_inv((1, 60), (1, 15)), _eq("In_Q_bransament_A", 160)],
    "f14": [_inv((3, 100), (1, 50)), _eq("pt_Sn_kVA", 630), _eq("pt_existent", True), _eq("L_racord_m", 90)],
    "f15": [_inv((1, 110), (2, 50)), _eq("schema_pamant", "TT"), _eq("RA_ohm", 2), _eq("racord", "tg_existent")],
    "f16": [_inv((2, 30), (1, 12)), _eq("racord", "tg_existent")],
    "f17": [_inv((1, 50)), _eq("string.n_module", 11), _eq("string.n_stringuri_paralel", 10),
            ("gPV 20 A", lambda r: 20 in (g(r["in"], "string.gpv_In_A"), r["in"].get("gpv_In_A")))],
    "f18": [_inv((1, 100)), _eq("string.n_MPPT", 10), _eq("string.n_stringuri_paralel", 3),
            ("gPV 15 A", lambda r: 15 in (g(r["in"], "string.gpv_In_A"), r["in"].get("gpv_In_A")))],
    "f19": [_inv((1, 110)), _eq("string.n_module", 18), _eq("string.n_stringuri_paralel", 12), _eq("string.Uoc_V", 49.6),
            _eq("string.Isc_A", 13.9)],
    "f20": [_inv((2, 100)), _eq("bess.kWh", 215), _eq("bess.P_kW", 108), _eq("bess.cuplaj", "ca"),
            _eq("pt_existent", True)],
    "f21": [_inv((2, 50)), ("invertoare hibride", lambda r: all(i.get("hibrid") for i in r["in"].get("invertoare") or [{}])),
            _eq("bess.cuplaj", "cc"), _eq("bess.kWh", 80)],
    "f22": [_inv((4, 110)), _eq("bess.kWh", 257), _eq("bess.P_kW", 125), _eq("bess.cuplaj", "ca"), _eq("pt_Sn_kVA", 800),
            PT_NU_EXISTENT],
    "f23": [_inv((3, 100)), _eq("bess.kWh", 100), _eq("bess.P_kW", 50), _eq("pt_existent", True)],
    "f24": [_inv((8, 125)), _eq("bess.kWh", 1000), _eq("bess.P_kW", 500), _eq("bess.cuplaj", "ca"),
            _eq("limitare_injectie_kW", 600), _eq("pt_Sn_kVA", 2000)],
    "f25": [_eq("bess.kWh", 500), _eq("bess.P_kW", 250), _eq("pt_existent", True), _eq("L_racord_m", 80)],
    "f26": [_eq("bess.kWh", 100), _eq("bess.P_kW", 50), _eq("racord", "tg_existent")],
    "f27": [_eq("bess.kWh", 2000), _eq("bess.P_kW", 1000), _eq("pt_Sn_kVA", 1250)],
    "f28": [_inv((2, 100)), _eq("limitare_injectie_kW", 0), _eq("pt_existent", True)],
    "f29": [_inv((3, 50)), _eq("limitare_injectie_kW", 50), _eq("racord", "bmpt")],
    "f30": [_tip("prosumator"), _inv((2, 40), (1, 10)), _eq("limitare_injectie_kW", 0), _eq("racord", "tg_existent")],
    "f31": [_inv((4, 100)), _eq("racord", "tg_existent"), INTREABA],
    "f32": [_inv((1, 40)), _eq("In_Q_bransament_A", 63), INTREABA],
    "f33": [_inv((6, 110)), _eq("pt_Sn_kVA", 1000), _eq("pt_existent", True)],
    "f34": [_tip("prosumator"), _eq("retea", "mono"), ("Pn 6", lambda r: r5.pn_total(r["in"]) == 6)],
    "f35": [REFUZ],
    "f36": [_inv((1, 100)), _eq("schema_pamant", "TT"), _eq("RA_ohm", 10), _eq("cablu_C0.S_fortat", 70)],
    "f37": [_inv((1, 125)), _eq("cablu_C0.S_fortat", 150), _eq("cablu_C0.N_fortat", 70)],
    "f38": [_tip("prosumator"), _eq("baterie_kWh", 10), ("fără PCS fictiv", lambda r: not r["in"].get("bess"))],
    "f39": [REFUZ],
    "f40": [_tip("prosumator"), ("Pn 30", lambda r: r5.pn_total(r["in"]) == 30), _eq("racord", "tg_existent")],
    "f41": [_tip("prosumator"), ("Pn 50", lambda r: r5.pn_total(r["in"]) == 50), _eq("In_Q_bransament_A", 125)],
    "f42": [_tip("prosumator"), _eq("hibrid", True), _eq("baterie_kWh", 20)],
    "f43": [REFUZ],
    "f44": [INTREABA_SAU_REFUZ, ("conflict model–putere întrebat", lambda r: any("100" in q for q in r["intrebari"]))],
    "f45": [REFUZ],
    "f46": [REFUZ],
    "f47": [REFUZ],
    "f48": [_inv((3, 100)), _eq("pt_Sn_kVA", 250), INTREABA],
}

# ----------------------------------------------------------------------------------------- industrial (r6)
T = _tip("tablou")
IND6 = {
    1: [T, _eq("origine", "pt_propriu"), _eq("pt_Sn_kVA", 400), _eq("schema_pamant", "TN-S"), _np(16)],
    2: [T, _eq("origine", "tg_existent"), _eq("L_alimentare_m", 60), _eq("cablu.S_fortat", 25), _np(7),
        _pl(2, "pornire", "stea_triunghi"), _pl(3, "retea", "mono"), _ne("retea", "mono")],
    3: [T, _eq("origine", "tg_existent"), _eq("schema_pamant", "TN-S"), _np(16), _eq("retea", "tri")],
    4: [T, _eq("retea", "mono"), _eq("origine", "tg_existent"), _eq("L_alimentare_m", 25), _np(12)],
    5: [T, _eq("origine", "pt_propriu"), _eq("pt_Sn_kVA", 250), _eq("L_alimentare_m", 120), _np(4),
        _pl(0, "pornire", "soft"), ("fără plecarea „alimentare din PT”", lambda r: not any(
            "PT" in p["nume"] for p in plec(r["in"])))],
    6: [T, _eq("origine", "bmpt"), _eq("In_Q1_A", 250), _np(14)],
    7: [T, _np(14), INTREABA],
    8: [T, _np(2), _pl(0, "pornire", "directa"), _pl(1, "pornire", "soft")],
    9: [T, _eq("pt_Sn_kVA", 1000), _eq("In_Q1_A", 1600), _np(5)],
    10: [T, _eq("origine", "bmpt"), _eq("schema_pamant", "TT"), _eq("RA_ohm", 10), _np(3)],
    11: [T, _eq("schema_pamant", "TT"), _eq("RA_ohm", 50), _np(5)],
    12: [T, _eq("schema_pamant", "TN-C"), _np(2)],
    13: [_eq("schema_pamant", "IT"), INTREABA_SAU_REFUZ],                  # motorul: V28 BLOCANT
    14: [T, _eq("origine", "pt_propriu"), INTREABA],
    15: [T, _eq("origine", "bmpt"), _eq("In_Q1_A", 63), _np(3)],
    16: [T, INTREABA, ("rețea nepresupusă", lambda r: "retea" not in r["in"])],
    17: [T, _eq("retea", "mono"), _np(4)],
    18: [REFUZ],
    19: [T, _eq("retea", "tri"), _np(4), _pl(0, "retea", "mono"), _pl(3, "retea", "tri")],
    20: [REFUZ],
    21: [T, _np(3), ("copii 3 + 2 (+ 6 prize)", lambda r: [len(p.get("copii") or []) for p in plec(r["in"])][:2] == [3, 7])],
    22: [T, _np(2), INTREABA],
    23: [T, _eq("origine", "tg_existent"), _eq("cablu.S_fortat", 35), _np(4)],
    24: [_tip("pt"), _eq("Sn_kVA", 630), _eq("n_trafo", 2), _np(2)],
    25: [_tip("pt"), _eq("Sn_kVA", 630), _eq("trafo_izolatie", "uscat"), _eq("masura", "MT"), _eq("compensare_kvar", 150),
         _eq("celula_trafo", "intreruptor")],
    26: [_tip("pt"), _eq("Sn_kVA", 160), ("măsura directă (masura_ceruta / metadatele _masura_ceruta — r11: cheia nu e a PT-ului)", lambda r: "directa" in (r["in"].get("masura_ceruta"), r["in"].get("_masura_ceruta")))],
    27: [_tip("pt"), _eq("Sn_kVA", 400), _eq("SkQ_MVA", 350)],
    28: [_tip("pt"), _eq("Sn_kVA", 1250), _eq("celula_trafo", "sigurante")],
    29: [_tip("pt"), _eq("Sn_kVA", 630), _eq("U_MT_kV", 6)],
    30: [_tip("ge_ats"), _eq("Sn_GE_kVA", 150), _eq("P_sarcina_kW", 100), INTREABA],
    31: [_tip("ge_ats"), _eq("Sn_GE_kVA", 150), _eq("In_Q_retea_A", 200), _eq("sursa_retea", "bmpt"),
         _eq("L_GE_ATS_m", 25), _eq("P_sarcina_kW", 90)],
    32: [_tip("ge_ats"), _eq("Sn_GE_kVA", 80), _eq("pt_Sn_kVA", 400), _eq("P_sarcina_kW", 55), _eq("L_GE_ATS_m", 20)],
    33: [_eq("retea", "mono"), INTREABA_SAU_REFUZ],                        # motorul blochează GE mono
    34: [_eq("ge_paralel", True)],
    35: [_tip("ge_ats"), _eq("P_sarcina_kW", 97.5), ("2 consumatori (pompe incendiu Y/D + hidrofor)", lambda r: len(
        r["in"].get("consumatori") or []) == 2), ("pompe incendiu = siguranță", lambda r: bool(
            (r["in"].get("consumatori") or [{}])[0].get("siguranta")))],
    36: [REFUZ],
    37: [_tip("ge_ats"), _eq("Sn_GE_kVA", 100), _eq("sursa_retea", "tgd")],
    38: [T, _eq("cablu.S_fortat", 240), _eq("cablu.n_fortat", 2), _eq("cablu.material", "Al"), _eq("In_Q1_A", 400), _np(2)],
    39: [T, _np(2), _pl(0, "cablu.S_fortat", 10), _pl(1, "cablu.S_fortat", 6), _pl(0, "L_m", 80), _pl(1, "L_m", 30)],
    40: [T, _np(1), _pl(0, "cablu.S_fortat", 16)],
    41: [REFUZ],
    42: [_tip("pt"), _np(1)],
    43: [REFUZ],
    44: [REFUZ],
    45: [T, _eq("origine", "bmpt"), _eq("In_Q1_A", 100), INTREABA],
    46: [REFUZ],
    47: [REFUZ],
    48: [T, _eq("origine", "tg_existent"), _eq("schema_pamant", "TN-S"), _np(3), _pl(0, "L_m", 60), _pl(1, "L_m", 45),
         _pl(2, "L_m", 30)],
    49: [T, _np(5), _pl(0, "nume", "TD-1"), _pl(2, "nume", "TD-3")],
    50: [T, _eq("origine", "tg_existent"), _eq("cablu.S_fortat", 16), _eq("L_alimentare_m", 50), _np(7)],
    51: [T, _eq("retea", "mono"), _eq("origine", "tg_existent"), _eq("L_alimentare_m", 20), _np(8)],
    52: [T, _eq("origine", "pt_propriu"), _eq("pt_Sn_kVA", 630), _np(2), _eq("compensare_kvar", 120)],
    53: [T, _eq("origine", "bmpt"), _eq("In_Q1_A", 125), _np(3)],
    54: [T, _eq("origine", "pt_propriu"), _eq("pt_Sn_kVA", 1600), _eq("schema_pamant", "TN-S"), _np(4),
         _pl(0, "pornire", "soft"), _pl(1, "pornire", "stea_triunghi")],
}


# ------------------------------------------------------------------------------------------------- rulare
def _rez(act, tip, intr, intrebari):
    return {"tip": tip, "act": act, "in": intr or {}, "intrebari": intrebari or []}


def incarca():
    """(set, rol, id, text, „înainte”, verificări)"""
    out = []
    r5_loc = {x["id"]: x for x in json.loads((RAD / "teste/r5/locuinte/fraze.json").read_text(encoding="utf-8"))}
    for x in json.loads((R6 / "locuinte" / "fraze.json").read_text(encoding="utf-8")):
        o = x["obtinut"]
        ina = _rez(o.get("actiune"), o.get("tip"), o.get("intrare_fizica"), o.get("intrebari"))
        if x["runda"] == "R5-reluat":
            a5 = r5_loc.get(x["id"], {}).get("asteptat") or x["asteptat"]
            out.append(("r5", "locuinte", x["id"], x["text"], ina, r5.asteptari_locuinte(a5, x["id"])))
        else:
            out.append(("r6", "locuinte", x["id"], x["text"], ina, asteptari_locuinte_r6(x["asteptat"], x["id"])))
    for x in json.loads((R6 / "fotovoltaic" / "fraze.json").read_text(encoding="utf-8")):
        ina = _rez(x.get("actiune"), x.get("tip"), x.get("intrare"), x.get("intrebari"))
        if x["set"] == "r5":
            out.append(("r5", "fotovoltaic", x["id"], x["fraza"], ina, r5.PV[x["nr"]]))
        else:
            out.append(("r6", "fotovoltaic", x["id"], x["fraza"], ina, PV6[x["id"]]))
    for x in json.loads((R6 / "industrial" / "reverificare_r5.json").read_text(encoding="utf-8")):
        ina = _rez(x.get("actiune"), x.get("tip"), x.get("intrare"), x.get("intrebari"))
        out.append(("r5", "industrial", f"#{x['nr']}", x["fraza"], ina, r5.IND[x["nr"]]))
    for x in json.loads((R6 / "industrial" / "fraze.json").read_text(encoding="utf-8")):
        ina = _rez(x.get("actiune"), x.get("tip"), x.get("intrare"), x.get("intrebari"))
        out.append(("r6", "industrial", f"#{x['nr']}", x["fraza"], ina, IND6[x["nr"]]))
    return out


def plasa_ok(d) -> bool:
    """Cerința 1 r6: rest neconsumat ⇒ nu „genereaza” fără mențiune (întrebare + „Nu am înțeles”)."""
    return not d["neconsumat"] or (d["actiune"] != "genereaza" and "Nu am înțeles" in d["intelegere"])


def main(verbose=False):
    stat, rand, plasa_rupta = {}, [], []
    rang = {"gresit": 0, "partial": 1, "corect": 2}
    for set_, rol, fid, text, ina, verif in incarca():
        d = interpreteaza_local(text)
        dupa = _rez(d["actiune"], d["tip_schema"], d["intrare_fizica"], d["intrebari"])
        vi, _ = evalueaza(verif, ina)
        vd, lipsa = evalueaza(verif, dupa)
        if not plasa_ok(d):
            plasa_rupta.append((fid, text))
        s = stat.setdefault((set_, rol), {"n": 0, "inainte": dict.fromkeys(rang, 0), "dupa": dict.fromkeys(rang, 0),
                                          "imb": 0, "reg": 0, "plasa": 0})
        s["n"] += 1
        s["inainte"][vi] += 1
        s["dupa"][vd] += 1
        s["imb"] += rang[vd] > rang[vi]
        s["reg"] += rang[vd] < rang[vi]
        s["plasa"] += bool(d["neconsumat"])
        rand.append((set_, rol, fid, vi, vd, lipsa, text, d["neconsumat"]))
    tot = {"n": 0, "inainte": dict.fromkeys(rang, 0), "dupa": dict.fromkeys(rang, 0), "imb": 0, "reg": 0, "plasa": 0}
    for (set_, rol), s in sorted(stat.items()):
        print(f"{set_} {rol:12s} {s['n']:3d} fraze | înainte C/P/G {s['inainte']['corect']}/{s['inainte']['partial']}/"
              f"{s['inainte']['gresit']} | după C/P/G {s['dupa']['corect']}/{s['dupa']['partial']}/{s['dupa']['gresit']}"
              f" | îmbunătățite {s['imb']}, regresii {s['reg']} | cu rest neconsumat (întrebat) {s['plasa']}")
        for k in ("n", "imb", "reg", "plasa"):
            tot[k] += s[k]
        for k in ("inainte", "dupa"):
            for v in rang:
                tot[k][v] += s[k][v]
    print(f"TOTAL           {tot['n']:3d} fraze | înainte C/P/G {tot['inainte']['corect']}/{tot['inainte']['partial']}/"
          f"{tot['inainte']['gresit']} | după C/P/G {tot['dupa']['corect']}/{tot['dupa']['partial']}/"
          f"{tot['dupa']['gresit']} | îmbunătățite {tot['imb']}, regresii {tot['reg']}")
    print(f"plasa de siguranță: {len(plasa_rupta)} fraze cu rest neconsumat generate fără mențiune")
    for set_, rol, fid, vi, vd, lipsa, text, nec in rand:
        if vd != "corect" or verbose:
            print(f"  [{set_} {rol}] {fid}: {vi} → {vd}" + (f"  lipsă: {'; '.join(lipsa)}" if lipsa else "") + f"  | {text}"
                  + (f"  | neconsumat: {nec}" if nec else ""))
    return tot, plasa_rupta


if __name__ == "__main__":
    main(verbose="-v" in sys.argv)
