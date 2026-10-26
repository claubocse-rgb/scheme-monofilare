"""Regresii runda 5 (teste/r5/{locuinte,fotovoltaic,industrial}.md): fiecare frază P0/P1 din rapoarte, cu
așteptatul din raport (nu ce făcea codul). Verificările sunt pe ieșirea interpretorului (`intrare_fizica`,
acțiune, întrebări) — cheile noi le integrează motorul (SPEC §F.5, tabelul „chei r5”).

Rulare: cd /home/claude/sm && python3 -m pytest -q tests/test_interpretor_r5.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import interpretor as m  # noqa: E402
from engine.interpretor import interpreteaza_local  # noqa: E402


def g(d, cale):
    for k in cale.split("."):
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def inv(i):
    if i.get("invertoare"):
        return sorted((x["n"], x["Pn_kW"]) for x in i["invertoare"])
    return [(1, i["Pn_inv_kW"])] if i.get("Pn_inv_kW") else []


def plec(i):
    out = []
    for p in i.get("plecari") or []:
        out += [p] * int(p.get("n_circuite") or 1)
    return out


def rec(i):
    return [c["receptor"] for c in i.get("circuite") or []]


# (id, text, tip, acțiune | None, {cale: valoare}, [(descriere, funcție(rezultat) -> bool)])
GEN = ("genereaza", "genereaza_cu_intrebare")
CAZURI = [
    # ------------------------------------------------------------------ locuințe — P0
    ("L26", "prosumator casa 5 kW invertor monofazat, bransament mono 7 kW, L=15m", "prosumator", GEN,
     {"retea": "mono", "Pn_inv_kW": 5, "P_aprobata_kW": 7, "L_inv_m": 15}, []),
    ("L28", "prosumator pe casa, 8 kW, cablu 25 m pana la BMPT", "prosumator", GEN,
     {"retea": "tri", "Pn_inv_kW": 8, "L_coloana_m": 25, "racord": "bmpt"}, []),
    ("L30", "panouri pe casa 3 kWp, invertor 3 kW mono", "prosumator", GEN, {"retea": "mono", "Pn_inv_kW": 3, "kWp": 3}, []),
    ("L31", "casa P+1 tri 15 kW + fotovoltaic 10 kW pe acoperis", "prosumator", GEN,
     {"retea": "tri", "Pn_inv_kW": 10, "P_aprobata_kW": 15}, []),
    ("L37", "Casa P+1 trifazat 22 kVA, coloana 30m", "locuinta", GEN, {"retea": "tri", "alimentare.L_coloana_m": 30},
     [("fără P din kVA", lambda r: g(r["intrare_fizica"], "alimentare.P_aprobata_kW") is None)]),
    ("L08", "Casa P+M trifazata 3x400V, Paprobat 20kW, sauna 9 kW, pompa caldura 8 kW, VE 11kW, coloana cca 30 m Al",
     "locuinta", GEN, {"alimentare.P_aprobata_kW": 20},
     [("PdC 8 kW", lambda r: any(c["receptor"] == "pompa_caldura" and c.get("P_kW") == 8
                                 for c in r["intrare_fizica"]["circuite"]))]),
    ("L47", "casa parter tri 10kw, pompa caldura 3 kW monofazata, coloana 25 m", "locuinta", GEN,
     {"retea": "tri", "alimentare.P_aprobata_kW": 10},
     [("PdC monofazată", lambda r: any(c["receptor"] == "pompa_caldura" and c.get("faza") in ("L1", "L2", "L3")
                                       for c in r["intrare_fizica"]["circuite"]))]),
    ("E01", "casa parter mono, pompa caldura 6 kw, 7 kw aprobat", "locuinta", GEN, {"alimentare.P_aprobata_kW": 7},
     [("PdC 6 kW", lambda r: "pompa_caldura" in rec(r["intrare_fizica"]))]),
    ("E02", "casa tri 15 kw, PC aer-apa 9kW, coloana 20m", "locuinta", GEN, {"alimentare.P_aprobata_kW": 15},
     [("PdC 9 kW", lambda r: any(c["receptor"] == "pompa_caldura" and c.get("P_kW") == 9
                                 for c in r["intrare_fizica"]["circuite"]))]),
    ("L15", "casa monofazata cu pompa de caldura trifazata 10 kW", "locuinta", ("refuza",), {},
     [("I08", lambda r: r["refuz_cod"] == "I08" and r["intrebari"])]),
    ("L46", "locuinta individuala P+1, mono, Pi 18 kW, Pa 8 kW, coloana 20m", "locuinta", GEN,
     {"alimentare.P_aprobata_kW": 8, "alimentare.L_coloana_m": 20}, []),
    # ------------------------------------------------------------------ locuințe — P1
    ("L27", "prosumator 10 kWp, invertor hibrid 10 kW trifazat, baterie 10 kWh, P aprobata 15 kW, coloana 20m",
     "prosumator", GEN, {"Pn_inv_kW": 10, "baterie_kWh": 10, "P_aprobata_kW": 15, "L_coloana_m": 20, "hibrid": True}, []),
    ("L29", "prosumator 6kw hibrid cu acumulator 5 kWh, 230 V, aprobat 6 kw", "prosumator", GEN,
     {"retea": "mono", "Pn_inv_kW": 6, "baterie_kWh": 5, "P_aprobata_kW": 6}, []),
    ("L32", "prosumator 15 kW trifazic hibrid, baterie 15kWh/7,5kW, Paprobat 15kW, coloana 35 m", "prosumator", GEN,
     {"Pn_inv_kW": 15, "P_aprobata_kW": 15, "L_coloana_m": 35}, []),
    ("L33", "prosumator 2 invertoare de 5 kW, tri, P evacuata 10 kW, coloana 18m", "prosumator", GEN,
     {"Pn_inv_kW": 10, "P_evacuata_kW": 10, "L_coloana_m": 18}, [("2 × 5", lambda r: inv(r["intrare_fizica"]) == [(2, 5)])]),
    ("L01", "casa parter monofazata, P aprobata 7 kW, Q bransament 32A, coloana 15 m", "locuinta", GEN,
     {"alimentare.P_aprobata_kW": 7, "alimentare.In_Q_bransament_A": 32, "alimentare.L_coloana_m": 15}, []),
    ("BQ", "bransament monofazat 7 kW, Q 32 A, coloana 15 m", "bransament", GEN, {"P_kW": 7, "Q_In_A": 32}, []),
    ("E03", "casa mono 6 kW, coloana 15 m, plita gaz", "locuinta", GEN, {},
     [("fără plită electrică", lambda r: "plita" not in rec(r["intrare_fizica"]))]),
    ("E04", "casa mono 6kW, fara plita electrica, fara cuptor", "locuinta", GEN, {},
     [("fără plită/cuptor", lambda r: not {"plita", "cuptor"} & set(rec(r["intrare_fizica"])))]),
    ("L06", "tablou locuinta casa veche, schema TT, priza de pamant proprie RA 30 ohm, mono 230V, 6 kW", "locuinta", GEN,
     {"schema_pamant": "TT", "RA_ohm": 30},
     [("set tipic fără plită/cuptor", lambda r: not {"plita", "cuptor"} & set(rec(r["intrare_fizica"])))]),
    ("L42", "casa tri, 15 kW, statie incarcare VE 7,4 kW monofazata, coloana 25 m", "locuinta", GEN, {"retea": "tri"},
     [("VE monofazat", lambda r: any(c["receptor"] == "vehicul_electric" and c.get("faza") in ("L1", "L2", "L3")
                                     for c in r["intrare_fizica"]["circuite"]))]),
    ("L10", "casa P+1, mono, 2 boilere de 2kW, 3 aparate AC 1,2 kW, plita 6 kW, aprobat 9 kW", "locuinta", GEN, {},
     [("3 AC + 2 boilere", lambda r: rec(r["intrare_fizica"]).count("aer_conditionat") == 3
       and rec(r["intrare_fizica"]).count("boiler") == 2)]),
    ("L35", "casa P+1, TN-C-S, tri 400 V, 12 kw, 20 m coloana, plita 7,5kW, cuptor 3kW, 2 bai cu boiler 2 kW fiecare",
     "locuinta", GEN, {}, [("2 boilere", lambda r: rec(r["intrare_fizica"]).count("boiler") == 2)]),
    ("L40", "casa P+1 tri 20kW, 3 circuite prize de 16A, 2 circuite iluminat, plita 7 kW, cuptor, mas spalat vase, msr, uscator",
     "locuinta", GEN, {},
     [("3 prize, 2 iluminat, MSV", lambda r: rec(r["intrare_fizica"]).count("prize") == 3
       and rec(r["intrare_fizica"]).count("iluminat") == 2 and "masina_spalat_vase" in rec(r["intrare_fizica"]))]),
    ("E05", "casa mono, plita, 6 kW, Q 32 A, 5 circuite prize", "locuinta", GEN, {},
     [("5 prize", lambda r: rec(r["intrare_fizica"]).count("prize") == 5)]),
    ("L43", "casa P+1 15kw trifazat, coloana 25m, sauna 6 kW pe 3F", "locuinta", GEN, {},
     [("fără nota „6 kW > 7,4 kW”", lambda r: not any("6 kW > 7,4" in p for p in r["presupus"]))]),
    # ------------------------------------------------------------------ fotovoltaic — P0
    ("f02", "cef 120kwp, 1 invertor sungrow SG110CX, panouri longi 580W, racord in TG existent la 40m", "cef", GEN,
     {"modul.Pmax_W": 580, "modul.producator": "LONGi", "racord": "tg_existent", "L_racord_m": 40},
     [("1 × 110", lambda r: inv(r["intrare_fizica"]) == [(1, 110)])]),
    ("f07", "CEF 150 kWp, 3 invertoare a 50 kW (Solis S5-GC50K), stringuri 2 pe MPPT, racord JT cf ATR, coloana 120 m al",
     "cef", GEN, {"atr_jt": True, "L_racord_m": 120, "cablu_C0.material": "Al", "invertoare.0.model": None},
     [("3 × 50", lambda r: inv(r["intrare_fizica"]) == [(3, 50)]),
      ("model Solis", lambda r: r["intrare_fizica"]["invertoare"][0]["model"] == "S5-GC50K")]),
    ("f08", "cef 1 MWp, 8 invertoare Huawei SUN2000-115KTL de 115 kW, PT propriu 1000 kVA, cablu 200 m", "cef", GEN,
     {"pt_Sn_kVA": 1000}, [("8 × 115", lambda r: inv(r["intrare_fizica"]) == [(8, 115)]),
                           ("întreabă V67", lambda r: any("V67" in q for q in r["intrebari"]))]),
    ("f18", "CEF 500 kWp, 4 invertoare Sungrow SG125CX 125 kW, racord JT conform ATR", "cef", GEN, {},
     [("4 × 125", lambda r: inv(r["intrare_fizica"]) == [(4, 125)])]),
    ("f15", "fotovoltaic 60 kWp cu 2 invertoare diferite: Huawei 36 kW si Huawei 20 kW, racord in tablou existent", "cef",
     GEN, {"racord": "tg_existent"}, [("36 + 20", lambda r: inv(r["intrare_fizica"]) == [(1, 20), (1, 36)])]),
    ("f03", "Centrala fotovoltaica 250 kWp pe acoperis hala, 2 x Huawei SUN2000-100KTL-M2 (100 kW), JA 545Wp, racord in TG "
            "existent, L=90 m", "cef", GEN, {"modul.Pmax_W": 545, "L_racord_m": 90},
     [("2 × 100", lambda r: inv(r["intrare_fizica"]) == [(2, 100)])]),
    ("f11", "CEF 200 kWp cu 1 invertor Huawei SUN2000-100KTL-M2 de 100 kW si 2 invertoare Sungrow SG50CX de 50 kW, racord "
            "in TG existent, cablu 70 m", "cef", GEN, {"L_racord_m": 70},
     [("1×100 + 2×50", lambda r: inv(r["intrare_fizica"]) == [(1, 100), (2, 50)])]),
    ("f12", "cef 180 kwp: invertor 1 = Fronius Tauro 100 kW, invertor 2 = SMA STP 50 kW, racord jt", "cef", GEN, {},
     [("1×100 + 1×50", lambda r: inv(r["intrare_fizica"]) == [(1, 50), (1, 100)])]),
    ("f40", "CEF 0,5 MWp cu 5 inv x 100kw, aprox 100 m pana la PT", "cef", GEN, {"L_racord_m": 100},
     [("5 × 100", lambda r: inv(r["intrare_fizica"]) == [(5, 100)])]),
    ("f14", "CEF 90 kwp, invertoare growatt MAX 50KTL3 + MAX 30KTL3, total 80 kw, cablu 45 m", "cef", GEN, {},
     [("50 + 30", lambda r: inv(r["intrare_fizica"]) == [(1, 30), (1, 50)])]),
    ("f13", "CEF 300 kWp cu 2×110 kW + 1×60 kW, module LONGi Hi-MO 6 570 Wp, BESS Huawei LUNA2000 215 kWh / 100 kW, racord TG "
            "existent 50 m", "cef", GEN, {"bess.kWh": 215, "bess.P_kW": 100, "bess.model": "LUNA2000", "modul.Pmax_W": 570},
     [("2×110 + 1×60", lambda r: inv(r["intrare_fizica"]) == [(1, 60), (2, 110)]),
      ("fără PT nou", lambda r: not r["intrare_fizica"].get("pt_Sn_kVA"))]),
    ("f16", "CEF 350 kWp, 3 invertoare 100 kW + 1 invertor 50 kW, PT propriu 630 kVA, BESS Sungrow PowerStack 200 kW / 430 kWh",
     "cef", GEN, {"bess.P_kW": 200, "bess.kWh": 430, "bess.producator": "Sungrow", "pt_Sn_kVA": 630}, []),
    ("f17", "CEF 220 kWp cu invertoare: 2 x SUN2000-100KTL (100 kW), racord TG existent; BESS BYD Battery-Box 150 kWh", "cef",
     GEN, {"bess.kWh": 150, "bess.producator": "BYD"}, [("2 × 100", lambda r: inv(r["intrare_fizica"]) == [(2, 100)])]),
    ("f44", "CEF 30 kWp cu invertor 30 kW, BESS Huawei LUNA2000 30 kWh, racord in TG", "cef", GEN, {"bess.kWh": 30}, []),
    ("f31", "CEF 300 kWp cu 3 invertoare de 100 kW si BESS 200 kWh, racord in TG existent, cablu 80 m", "cef",
     ("genereaza_cu_intrebare",), {"racord": "tg_existent"},
     [("fără trafo în serie", lambda r: not r["intrare_fizica"].get("pt_Sn_kVA"))]),
    ("f45", "CEF 600 kWp, 5 invertoare de 110 kW, racord in TG existent al fabricii (PT propriu 1000 kVA existent)", "cef",
     GEN, {"racord": "tg_existent", "pt_Sn_kVA": 1000, "pt_existent": True}, []),
    ("f21", "prosumator comercial 100 kW trifazat, 2 invertoare Huawei SUN2000-50KTL, 120 kWp, racord in TG existent, "
            "limitare injectie 50 kW", "prosumator", GEN,
     {"racord": "tg_existent", "limitare_injectie_kW": 50, "Pn_inv_kW": 100},
     [("2 × 50 separat", lambda r: inv(r["intrare_fizica"]) == [(2, 50)])]),
    ("f22", "prosumator 30 kW trifazat, invertor Fronius Symo 20 kW + Fronius Symo 10 kW, module JA 450 Wp", "prosumator", GEN,
     {"modul.Pmax_W": 450}, [("20 + 10", lambda r: inv(r["intrare_fizica"]) == [(1, 10), (1, 20)])]),
    ("f28", "prosumator 250 kW trifazat cu 2 invertoare de 125 kW si BESS 200 kWh / 100 kW, injectie limitata 150 kW",
     "prosumator", GEN, {"bess.kWh": 200, "bess.P_kW": 100, "limitare_injectie_kW": 150},
     [("2 × 125", lambda r: inv(r["intrare_fizica"]) == [(2, 125)])]),
    ("f35", "CEF 100 kWp cu 2 invertoare de 50 kW, monofazat", "cef", ("refuza",), {},
     [("I08", lambda r: r["refuz_cod"] == "I08")]),
    # ------------------------------------------------------------------ fotovoltaic — P1
    ("f01", "CEF 100 kWp cu 2 invertoare Huawei SUN2000-50KTL-M3, module JA Solar 550 Wp, racord JT prin BMPT, cablu 60 m",
     "cef", GEN, {"racord": "bmpt", "L_racord_m": 60, "invertoare.0.producator": "Huawei",
                  "invertoare.0.model": None}, [("2 × 50", lambda r: inv(r["intrare_fizica"]) == [(2, 50)])]),
    ("f25", "prosumator 150 kW cu 3 invertoare de 50 kW, BMPT existent 200 A, retea trifazata", "prosumator", GEN,
     {"In_Q_bransament_A": 200, "racord": "bmpt"}, []),
    ("f42", "CEF 200 kWp cu 2 invertoare Huawei SUN2000-100KTL-M2, retea TT, priza de pamant 4 ohm", "cef", GEN,
     {"schema_pamant": "TT", "RA_ohm": 4}, [("2 × 100", lambda r: inv(r["intrare_fizica"]) == [(2, 100)])]),
    ("f23", "prosumator 400 kW, 4 invertoare de 100 kW, trifazat, autoconsum cu injectie zero", "prosumator", GEN,
     {"limitare_injectie_kW": 0}, []),
    ("f27", "prosumator comercial, invertor 100 kW SMA, 3f, limitare injectie la 30 kW (ATR), contor bidirectional",
     "prosumator", GEN, {"limitare_injectie_kW": 30, "Pn_inv_kW": 100}, []),
    ("f38", "CEF 300 kwp cu 3 invertoare 100kw, autoconsum fara injectie (injectie zero), racord in TG existent", "cef", GEN,
     {"limitare_injectie_kW": 0}, []),
    ("f46", "cef 100kwp 2 invertoare de 50 kw cablu 50m , BESS 100kwh/50kw, injectie limitata la 0", "cef", GEN,
     {"limitare_injectie_kW": 0, "L_racord_m": 50, "bess.kWh": 100}, []),
    ("f05", "fotovoltaic 80 kwp, 2 invertoare de 40kw fronius tauro, racord in tg, cablu cu 35m, retea TN-C-S", "cef", GEN,
     {"schema_pamant": "TN-C-S", "cablu_C0.material": "Cu", "invertoare.0.producator": "Fronius"}, []),
    ("f06", "CEF 50 kWp cu invertor SMA Sunny Tripower Core2 50 kW, module Jinko Tiger Neo 580 Wp, 18 module pe string, "
            "5 stringuri, cablu Cu 25 m", "cef", GEN,
     {"string.n_module": 18, "string.n_stringuri_paralel": 5, "cablu_C0.material": "Cu", "modul.producator": "Jinko Solar"},
     []),
    ("f19", "CEF 160kWp invertor Solis 125 kW, raport dc/ac 1.28, racord in TG existent, cablu 3x(4x150)Al 60m", "cef", GEN,
     {"cablu_C0.S_fortat": 150, "cablu_C0.n_fortat": 3, "cablu_C0.material": "Al", "L_racord_m": 60}, []),
    ("f37", "CEF 250 kWp, 2 invertoare de 100 kW, racord in TG existent cu Q 250 A, Ik bara TG 15 kA, cablu 30 m Cu", "cef",
     GEN, {"racord_In_Q_A": 250, "Ik3_TG_kA": 15, "cablu_C0.material": "Cu"}, []),
    ("f43", "CEF 150 kWp cu 1 invertor 100 kW si 1 invertor 50 kW, cutie de jonctiune cu siguranta gPV 15 A pe string, "
            "SPD c.c. tip 2", "cef", GEN, {"string.gpv": True, "gpv_In_A": 15}, []),
    ("f36", "CEF 120 kWp, 3 invertoare de 50 kW, total 100 kW", "cef", ("refuza",), {},
     [("I08 cu întrebare", lambda r: r["refuz_cod"] == "I08" and r["intrebari"])]),
    ("f34", "CEF 200 kWp cu 2 invertoare de 100 kVA, racord JT", "cef", GEN, {},
     [("2 × 100", lambda r: inv(r["intrare_fizica"]) == [(2, 100)])]),
    ("f33", "BESS 500 kW / 1000 kWh Sungrow PowerStack langa CEF existenta, racord in TG existent", "cef", GEN,
     {"bess.P_kW": 500, "bess.kWh": 1000}, []),
    ("f41", "cef 99,6 kWp, 2 invertoare de 50kW, 1.000 m cablu?? nu, 100 m", "cef", GEN, {"L_racord_m": 100}, []),
    ("f26", "prosumator 60 kw, 2 invertoare de 30 kw growatt, racord in TG existent", "prosumator", GEN,
     {"racord": "tg_existent"}, [("2 × 30", lambda r: inv(r["intrare_fizica"]) == [(2, 30)])]),
    # ------------------------------------------------------------------ industrial — P0
    ("i42", "TG atelier 3 plecari: TD-1 32A, TD-2 32A, TD-3 32A, retea TT RA 30 ohm", "tablou", GEN,
     {"schema_pamant": "TT", "RA_ohm": 30}, []),
    ("i47", "tablou general, plecari: TD-1 40A, TD-2 25A, schema TT, RA 20 ohm", "tablou", GEN,
     {"schema_pamant": "TT", "RA_ohm": 20}, []),
    ("i53", "tablou general monofazat cu plecari: iluminat 2 kW, prize 3 kW", "tablou", GEN, {"retea": "mono"}, []),
    ("i11", "tablou monofazat 3x63A", "tablou", ("refuza",), {}, [("I08", lambda r: r["refuz_cod"] == "I08")]),
    ("i36", "PT 1000 kVA + TG hala cu plecari TD-1 250A 40m, TD-2 160A 60m, plus GE 200 kVA cu ATS pe tabloul vital 120 kW",
     "ge_ats", ("genereaza_cu_intrebare",), {"Sn_GE_kVA": 200, "P_sarcina_kW": 120, "sursa_retea": "pt", "pt_Sn_kVA": 1000},
     []),
    ("i49", "PT 400 kVA si GE 100 kVA cu ATS, sarcina vitala 70 kW", "ge_ats", ("genereaza_cu_intrebare",),
     {"Sn_GE_kVA": 100, "P_sarcina_kW": 70, "sursa_retea": "pt"}, []),
    ("i38", "hala productie: PT 630kVA, TG, GE 150kVA ATS, CEF 100 kWp", "ge_ats", ("genereaza_cu_intrebare",),
     {"Sn_GE_kVA": 150}, []),
    ("i32", "GE 250kVA + AAR, consumatori vitali: pompe incendiu 2x30kW, iluminat siguranta 3kW, server 10kW", "ge_ats", GEN,
     {"Sn_GE_kVA": 250, "P_sarcina_kW": 73}, []),
    ("i50", "GE 100kVA cu ATS, consumatori vitali 2 pompe x 15 kW si iluminat 5 kW", "ge_ats", GEN, {"P_sarcina_kW": 35}, []),
    ("i19", "tablou general cu plecari TD-1 40A si TD-2 30 kVA", "tablou", GEN, {},
     [("2 plecări, TD-2 27 kW", lambda r: len(plec(r["intrare_fizica"])) == 2 and plec(r["intrare_fizica"])[1]["P_kW"] == 27)]),
    ("i16", "tg plecari td-1 250A 120m, td-2 160 A 0,15 km Al XLPE in tub", "tablou", GEN, {},
     [("160 A, 150 m", lambda r: plec(r["intrare_fizica"])[1]["In_A"] == 160 and plec(r["intrare_fizica"])[1]["L_m"] == 150),
      ("fără 2160 A", lambda r: r["intrare_fizica"].get("In_Q1_A") is None)]),
    ("i44", "TG hala 2 plecari: TD-1 125A 50m pozat aparent pe perete, TD-2 63A 30m in aer pe pat", "tablou", GEN, {},
     [("C / E", lambda r: [g(p, "cablu.metoda") for p in plec(r["intrare_fizica"])] == ["C", "E"])]),
    ("i04", "tg birouri P+2: TE parter 40A, TE etaj1 40A, TE etaj2 40A, server 25A, lift 11kW, HVAC 32 kW", "tablou", GEN, {},
     [("6 plecări", lambda r: len(plec(r["intrare_fizica"])) == 6)]),
    # ------------------------------------------------------------------ industrial — P1
    ("i15", "TG plecari: motor pompa 30 kW pornire stea-triunghi 50 m, motor ventilator 45kW cu convertizor 35m, banda "
            "transportoare 7.5 kW", "tablou", GEN, {},
     [("pornire", lambda r: [p.get("pornire") for p in plec(r["intrare_fizica"])] == ["stea_triunghi", "convertizor", None]),
      ("L", lambda r: [p.get("L_m") for p in plec(r["intrare_fizica"])][:2] == [50, 35])]),
    ("i13", "TG: TD-Hala 200A 90m (TD-H1 63A 30m; TD-H2 63A 45m); TD-Birouri 63A 25m", "tablou", GEN, {},
     [("cascadă", lambda r: len(plec(r["intrare_fizica"])) == 2 and len(plec(r["intrare_fizica"])[0]["copii"]) == 2
       and plec(r["intrare_fizica"])[0]["In_A"] == 200)]),
    ("i12", "TG 400V TN-C-S, plecari: TD-1 cu sub-plecari (iluminat 3 kW, prize 4 kW, pompa 5,5 kW), TD-2 cu sub-plecari "
            "(motor 18,5 kW 40m, ventilator 4 kW)", "tablou", GEN, {"schema_pamant": "TN-C-S"},
     [("nume TD-1 / TD-2", lambda r: [p["nume"] for p in plec(r["intrare_fizica"])] == ["TD-1", "TD-2"])]),
    ("i43", "tablou distributie ferma pasari, ventilatoare 10 x 1,1 kW, incalzire 3 x 9 kW, hranire 2,2kW", "tablou", GEN, {},
     [("14 plecări", lambda r: len(plec(r["intrare_fizica"])) == 14)]),
    ("i48", "TG din retea TN-C-S, plecari: pompa 15 CP, compresor 11kW", "tablou", GEN,
     {"schema_pamant": "TN-C-S", "origine": "bmpt"},
     [("15 CP ≈ 11 kW", lambda r: abs(plec(r["intrare_fizica"])[0]["P_kW"] - 11.03) < 0.01)]),
    ("i51", "tablou general hala 3x400V, plecari: TD-1 In=100A L=60m, TD-2 In=63A L=40m", "tablou", GEN, {"retea": "tri"},
     [("In / L", lambda r: [(p["In_A"], p["L_m"]) for p in plec(r["intrare_fizica"])] == [(100, 60), (63, 40)])]),
    ("i20", "TG cu plecari: cuptor industrial 60 kW cosfi 1, TD-3 100A", "tablou", GEN, {},
     [("cosφ pe plecare", lambda r: plec(r["intrare_fizica"])[0].get("cosfi") == 1
       and plec(r["intrare_fizica"])[0]["P_kW"] == 60 and "cosfi" not in r["intrare_fizica"])]),
    ("i52", "TG plecari: TD-1 100 A, TD-2 63 A, TD-3 40 A; alimentare 3x185+95 Al 70 m din PT", "tablou", GEN,
     {"cablu.S_fortat": 185, "cablu.material": "Al", "L_alimentare_m": 70, "origine": "pt_propriu"},
     [("3 plecări", lambda r: len(plec(r["intrare_fizica"])) == 3)]),
    ("i05", "Tablou general ferma vaci 250 vite: muls 15 kW, racire lapte 22 kW, ventilatie 6x1,5kW, iluminat grajd 4 kW, "
            "pompe apa 2x5,5 kW, coloana 120 m din PT ATR", "tablou", GEN, {"L_alimentare_m": 120},
     [("11 plecări", lambda r: len(plec(r["intrare_fizica"])) == 11)]),
    ("i40", "tablou general pentru SC Agro Ferma Nord SRL, loc. Salonta jud. Bihor, plansa E-03, faza PT, plecari TD-1 80A "
            "50m, TD-2 63A", "tablou", GEN, {}, [("faza PT în cartuș", lambda r: r["cartus"]["faza"] == "PT")]),
    ("i01", "TG hala productie, alimentat din PT propriu 630 kVA, TN-S, plecari: TD-1 125A 60m, TD-2 80A 45m, compresor "
            "37 kW 30m, iluminat 12 kW", "tablou", GEN, {"origine": "pt_propriu", "pt_Sn_kVA": 630, "schema_pamant": "TN-S"},
     []),
    ("i37", "TG hala 250A din retea, plecari TD-1 100A, TD-2 63A, si CEF pe acoperis 50 kWp cu invertor 50 kW", "cef",
     ("genereaza_cu_intrebare",), {"racord": "tg_existent", "racord_In_Q_A": 250},
     [("întrebare TG", lambda r: any("TG" in q for q in r["intrebari"]))]),
    ("i39", "TG cu plecari: TD-1 100A, invertor fotovoltaic 30 kW", "cef", ("genereaza_cu_intrebare",), {"racord": "tg_existent"},
     [("1 × 30", lambda r: inv(r["intrare_fizica"]) == [(1, 30)])]),
    ("i41", "Tablou TG alimentat cu cablu 3x150+70 Cu din TGD existent 45m, In 250A, plecari TD-1 100A, TD-2 100A", "tablou",
     GEN, {"origine": "tg_existent", "cablu.S_fortat": 150, "cablu.N_fortat": 70, "cablu.material": "Cu", "In_Q1_A": 250,
           "L_alimentare_m": 45}, []),
    ("i23", "PTAB 400 kVA cu celula de linie intrare-iesire si celula trafo, masura pe MT, plecari TD-1 200A, TD-2 160A", "pt",
     GEN, {"masura": "MT"}, [("celule de linie", lambda r: "linie_intrare" in r["intrare_fizica"]["celule_mt"])]),
    ("i28", "PT 250kVA trafo uscat, plecari: ferma porci 100A 200m; moara furaje 30kW 80m", "pt", GEN,
     {"trafo_izolatie": "uscat"}, []),
    ("i33", "generator diesel 60 kVA, ATS, sarcina 45 kW, cablu GE-ATS 15m", "ge_ats", GEN, {"L_GE_ATS_m": 15}, []),
    ("i31", "grup electrogen 100 kVA cu ATS pentru consumatori vitali 60 kW, retea 125A", "ge_ats", GEN,
     {"In_Q_retea_A": 125, "P_sarcina_kW": 60}, []),
    ("i34", "grup electrogen 500 kva pentru hala, sarcina vitala 380 kW", "ge_ats", GEN, {"sursa_retea": "pt"}, []),
    ("i03", "TG atelier mecanic 3 plecari: strung 7,5kW, freza 11 kw, compresor 15 kW, alimentare 80m Al in pamant", "tablou",
     GEN, {}, [("motoare", lambda r: [p.get("receptor") for p in plec(r["intrare_fizica"])][:2] == ["motor", "motor"])]),
    ("i14", "tablou general hala, iluminat 5 circuite de 16 A, prize 4 circuite de 25A, forta 2x32A", "tablou", GEN, {},
     [("n_circuite", lambda r: [p.get("n_circuite") for p in r["intrare_fizica"]["plecari"]][:2] == [5, 4]
       and r["intrare_fizica"]["plecari"][0]["nume"] == "Iluminat")]),
    ("i06", "TG hala depozitare cca 150A, plecari TD-1 63A, TD-2 63A, TD-3 40A, incarcare stivuitoare 3x16A", "tablou",
     ("genereaza_cu_intrebare",), {"In_Q1_A": 160}, []),
    ("i30", "PT 630 kVA cu 4 plecari", "pt", ("refuza",), {}, [("I02", lambda r: r["refuz_cod"] == "I02")]),
]


@pytest.mark.parametrize("cid,text,tip,actiuni,campuri,extra", CAZURI, ids=[c[0] for c in CAZURI])
def test_fraza_r5(cid, text, tip, actiuni, campuri, extra):
    r = interpreteaza_local(text)
    assert r["tip_schema"] == tip, (r["tip_schema"], r["intelegere"])
    assert r["actiune"] in actiuni, (r["actiune"], r["refuz_motiv"], r["intrebari"])
    i = r["intrare_fizica"]
    for cale, val in campuri.items():
        if val is None:                                   # doar prezența
            assert g(i, cale.replace(".0.", ".")) is not None or g({"x": (i.get(cale.split(".")[0]) or [{}])[0]},
                                                                   "x." + cale.split(".")[-1]) is not None, cale
            continue
        if ".0." in cale:
            a, b = cale.split(".0.")
            assert (i.get(a) or [{}])[0].get(b) == val, (cale, i.get(a))
        else:
            assert g(i, cale) == val, (cale, g(i, cale), i)
    for descr, f in extra:
        assert f(r), (descr, i, r["intrebari"])


def test_presupuneri_periculoase_declarate():
    """Rețeaua presupusă (când nu încape în mono), schema de pământ și sursa tabloului apar la „Am presupus”."""
    r = interpreteaza_local("CEF 100 kWp cu 2 invertoare de 50 kW")
    assert any("rețea nedeclarată" in p for p in r["presupus"])
    assert any("schema de legare la pământ nedeclarată" in p for p in r["presupus"])
    r = interpreteaza_local("TG cu plecari TD-1 100A, TD-2 63A")
    assert any("sursa tabloului nedeclarată" in p for p in r["presupus"])
    assert any("schema de legare la pământ nedeclarată" in p for p in r["presupus"])
    # tablou mic, fără rețea declarată → întrebare (nu se presupune)
    r = interpreteaza_local("tablou cu plecari: iluminat 1 kW, prize 2 kW")
    assert r["actiune"] == "genereaza_cu_intrebare" and "retea" not in r["intrare_fizica"]


def test_kw_nu_se_imparte_fara_intrebare():
    r = interpreteaza_local("CEF 200 kW, 4 invertoare")
    assert r["intrare_fizica"]["invertoare"] == [{"n": 4, "Pn_kW": 50}] and r["actiune"] == "genereaza_cu_intrebare"


def test_kva_pe_plecare_nu_face_pt_si_tablou_numit_are_prioritate():
    assert interpreteaza_local("tablou general cu plecari TD-1 40A si TD-2 30 kVA")["tip_schema"] == "tablou"
    assert interpreteaza_local("pt 100 kva pt ferma, plecari 2x63A")["tip_schema"] == "pt"


def test_prag_pi_externa_din_norme():
    """PI externă / tablou cu releu anti-insularizare peste norme.PROSUMATOR_PI_EXTERNA_KW (27 kW, cerință OD)."""
    prag = m.norme.PROSUMATOR_PI_EXTERNA_KW
    r = interpreteaza_local(f"prosumator trifazat {prag + 3:g} kW")
    assert any("PI externă" in p for p in r["presupus"])
    r = interpreteaza_local(f"prosumator trifazat {prag - 7:g} kW")
    assert not any("PI externă" in p for p in r["presupus"])


def test_cheile_noi_trec_normalizarea_llm():
    """Calea LLM păstrează cheile r5 (aceeași formă ca ieșirea locală)."""
    for t in ("CEF 220 kWp cu invertoare: 2 x SUN2000-100KTL (100 kW), racord TG existent; BESS BYD Battery-Box 150 kWh",
              "prosumator comercial 100 kW trifazat, 2 invertoare Huawei SUN2000-50KTL, 120 kWp, racord in TG existent, "
              "limitare injectie 50 kW",
              "Tablou TG alimentat cu cablu 3x150+70 Cu din TGD existent 45m, In 250A, plecari TD-1 100A, TD-2 100A",
              "PTAB 400 kVA cu celula de linie intrare-iesire si celula trafo, masura pe MT, plecari TD-1 200A, TD-2 160A",
              "generator diesel 60 kVA, ATS, sarcina 45 kW, cablu GE-ATS 15m",
              "TG plecari: motor pompa 30 kW pornire stea-triunghi 50 m, motor ventilator 45kW cu convertizor 35m"):
        i = interpreteaza_local(t)["intrare_fizica"]
        n = m.normalizeaza_intrare(i)
        for k in i:
            if k not in ("cablu", "plecari"):
                assert n.get(k) == i[k], (t, k, i[k], n.get(k))
        assert not m.valideaza_forma(n), t


def test_iesirea_r5_nu_strica_motorul():
    """Intrarea produsă din frazele r5 trece prin constructor fără excepții."""
    from engine import constructor
    for _, text, *_ in CAZURI:
        r = interpreteaza_local(text)
        if r["actiune"] != "refuza":
            constructor.genereaza(r["intrare_fizica"])
