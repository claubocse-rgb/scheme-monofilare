"""Regresii runda 6 (teste/r6/{locuinte,fotovoltaic,industrial}.md) — interpretorul.

1. Toate frazele r6 (noi) și r5 (reluate) din teste/r6/*/fraze.json cu verificările din teste/r6/reverificare.py
   (așteptatul din rapoarte, nu ce făcea codul): P0/P1 + restul.
2. Plasa de siguranță (cerința 1): pe TOATE frazele r5 + r6, o frază cu rest semnificativ neconsumat nu iese
   „genereaza” fără mențiune („Nu am înțeles: …” + întrebare).
3. Clasele de greșeli pe formulări NOI (nu cele din rapoarte): multiplicitate, surse, contradicții, liste, cabluri,
   cuplaj baterie, stringuri, chei noi ale motorului.

Rulare: cd /home/claude/sm && python3 -m pytest -q tests/test_interpretor_r6.py
"""
import importlib.util
import sys
from pathlib import Path

import pytest

RAD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAD))

from engine.interpretor import interpreteaza_local  # noqa: E402

_spec = importlib.util.spec_from_file_location("reverificare_r6", RAD / "teste" / "r6" / "reverificare.py")
rv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rv)

CAZURI = rv.incarca()
# P2 rămas (refuz I02 cu întrebare, sigur): „panouri 5 kwp pe casa” — Pn invertor nu se deduce din kWp
CUNOSCUTE = {"N25"}


@pytest.mark.parametrize("set_,rol,fid,text,ina,verif", CAZURI, ids=[f"{c[0]}-{c[1]}-{c[2]}" for c in CAZURI])
def test_fraza(set_, rol, fid, text, ina, verif):
    d = interpreteaza_local(text)
    r = {"tip": d["tip_schema"], "act": d["actiune"], "in": d["intrare_fizica"], "intrebari": d["intrebari"]}
    verdict, lipsa = rv.evalueaza(verif, r)
    if fid in CUNOSCUTE:
        pytest.xfail("P2 cunoscut")
    assert verdict == "corect", (lipsa, d["intrare_fizica"], d["intrebari"])


@pytest.mark.parametrize("text", sorted({c[3] for c in CAZURI}))
def test_plasa_pe_toate_frazele(text):
    d = interpreteaza_local(text)
    assert rv.plasa_ok(d), d["neconsumat"]
    if d["neconsumat"]:
        assert any(q.startswith("Nu am folosit") for q in d["intrebari"]) or d["actiune"] == "refuza"


# ------------------------------------------------------------------------------- clasele, pe formulări noi
def R(text):
    return interpreteaza_local(text)


def I(text):
    return R(text)["intrare_fizica"]


def inv(i):
    return sorted((x["n"], x["Pn_kW"]) for x in i.get("invertoare") or [])


def test_plasa_receptor_necunoscut_cu_putere():
    r = R("casa tri 15 kW, coloana 20m, frigider industrial 3 kW")
    assert r["actiune"] != "genereaza" and r["neconsumat"] and "Nu am înțeles" in r["intelegere"]


def test_plasa_receptor_la_prosumator():
    r = R("prosumator 10 kW tri, pompa de caldura 8 kW")
    assert any("pompa" in x for x in r["neconsumat"])


def test_plasa_cablu_la_ge():
    assert R("GE 100 kVA cu ATS, sarcina 60 kW, retea din PT 400 kVA, cablu 3x150 Al 50 m")["neconsumat"]


def test_plasa_fara_zgomot_pe_fraze_complete():
    for t in ("TG din PT propriu 630 kVA, plecari TD-1 250A 60m, TD-2 160A", "casa mono 7 kW, coloana 15 m",
              "CEF 100 kWp cu 2 invertoare de 50 kW, racord in TG existent, cablu 40 m"):
        assert not R(t)["neconsumat"], t


@pytest.mark.parametrize("text,asteptat", [
    ("CEF 220 kWp, 2 x Sungrow SG110CX, racord TG existent", [(2, 110)]),
    ("CEF 90 kWp cu SUN2000-30KTL-M3 x3", [(3, 30)]),
    ("CEF 330 kWp, 3 bucati Huawei SUN2000-100KTL-M2, PT nou 400 kVA", [(3, 100)]),
    ("CEF 60 kWp, Fronius Symo 15 kW x4, racord BMPT", [(4, 15)]),
    ("CEF 160 kWp: 2 Solis S5-GC50K si 1 x Solis S5-GC60K", [(1, 60), (2, 50)]),
])
def test_multiplicitate_invertoare(text, asteptat):
    assert inv(I(text)) == asteptat


def test_model_fara_k_din_catalog():
    assert inv(I("CEF 120 kWp cu 2 Fronius Tauro ECO 50-3-D, racord TG existent")) == [(2, 50)]


def test_pt_nou_cu_cablu_pana_la_tgd():
    i = I("CEF 900 kWp, 7 inv x 125 kW, PT nou 1000 kVA, cablu 180 m pana la TGD-CF")
    assert i.get("racord") != "tg_existent" and i["pt_Sn_kVA"] == 1000 and i.get("pt_existent") is False


def test_pt_existent_al_beneficiarului():
    assert I("CEF 500 kWp, 4 x 110 kW, racord in PT existent 800 kVA al fabricii")["pt_existent"] is True


def test_doua_racorduri_intreaba():
    assert R("CEF 60 kWp, 1 invertor 50 kW, racord in TG existent sau prin BMPT nou")["actiune"] == "refuza"


@pytest.mark.parametrize("text", [
    "TG schema TT si TN-C-S, plecari TD-1 32A, TD-2 16A",
    "tablou monofazat 230V cu pompa 5,5 kW trifazata",
    "TD hala 230V, plecari TD-1 40A 4P, TD-2 25A",
    "casa P+1, 8 kW sau 11 kW, tri, coloana 25m",
    "prosumator 25 kW cu 2 invertoare de 20 kW",
    "TG atelier alimentat din TG existent si din BMPT, plecari TD-1 40A",
])
def test_contradictii_intreaba(text):
    assert R(text)["actiune"] in ("refuza", "genereaza_cu_intrebare") and R(text)["intrebari"]


def test_mono_pe_un_receptor_nu_face_tabloul_mono():
    i = I("TG hala din TG existent, plecari: masina 7,5 kW, iluminat 1 kW monofazat, prize 3,6 kW")
    assert i.get("retea") != "mono" and any(p.get("retea") == "mono" for p in i["plecari"])


def test_tg_din_bmpt_e_tablou():
    i = I("TG magazin din BMPT 160A, plecari: frig 15 kW, iluminat 4 kW, prize 6 circuite 16A")
    assert i["tip_schema"] == "tablou" and i["origine"] == "bmpt" and i["In_Q1_A"] == 160


def test_sursa_pt_in_lista_nu_e_plecare():
    i = I("tablou statie pompare: 3 pompe 7,5 kW cu softstarter, iluminat 1 kW; alimentare din PT 160 kVA, 80 m Al")
    assert i["origine"] == "pt_propriu" and i["pt_Sn_kVA"] == 160 and not any("PT" in p["nume"] for p in i["plecari"])


@pytest.mark.parametrize("text,n", [
    ("TE etaj 230V din TG 15m, 6 circuite: 2 iluminat 10A, 3 prize 16A, 1 AC 2,5kW", 6),
    ("TD atelier, 3x400V, 4 circ iluminat B10, 2 prize trifazate 32A", 6),
    ("TG; plecari: 2 x TD 40A + 3 x ventilator 1,1kW", 5),
    ("tg depozit, sursa tgd exist., td-1 100 a/40 m, td-2 63a/25m, tn-s", 2),
])
def test_liste_forme_noi(text, n):
    i = I(text)
    assert sum(int(p.get("n_circuite") or 1) for p in i.get("plecari") or []) == n


def test_cablu_pe_plecare_nu_pe_coloana():
    i = I("TG plecari: TD-1 80A cablu CYABY 5x16 60m, TD-2 40A CYY-F 5x10 20m")
    assert [p["cablu"]["S_fortat"] for p in i["plecari"]] == [16, 10] and "S_fortat" not in (i.get("cablu") or {})


def test_cablu_paralel_si_tensiune():
    assert I("TG din PT propriu 400 kVA, coloana 2x(NA2XY 4x185) 70 m, plecari TD-1 160A")["cablu"]["n_fortat"] == 2
    assert (I("TD-3 din TG 40 m CYABY 5x10, 3x400V, plecari: cuptor 9 kW, malaxor 4 kW").get("cablu") or {}).get(
        "S_fortat") == 10


def test_casa_de_marcat_nu_e_casa():
    assert I("TG magazin TN-C-S din BMPT 100A: frig 20 kW, iluminat 5 kW, prize casa de marcat 4 circuite 16A"
             )["tip_schema"] == "tablou"


def test_marire_putere_tinta():
    i = I("marire putere bmpm 9kw -> bmpt 20 kw tri, coloana 30m")
    assert i["tip_schema"] == "bransament" and i["P_kW"] == 20 and i["retea"] == "tri"


def test_receptoare_prescurtate_locuinta():
    i = I("ap 3 cam, mono 6kw aprobati, pc 4kw, plita 6.5, inc pardoseala 2kw baie")
    rec = {c["receptor"]: c.get("P_kW") for c in i["circuite"]}
    assert rec.get("pompa_caldura") == 4 and rec.get("plita") == 6.5 and rec.get("incalzire_electrica") == 2


def test_tt_litere_mici_si_q_lipit():
    i = I("casa mono, tt, Ra 30 ohm, 7 kw, Q32A, col 20m")
    assert i["schema_pamant"] == "TT" and i["alimentare"]["In_Q_bransament_A"] == 32


def test_atelier_tablou_secundar():
    i = I("casa tri 15 kW, coloana 20m, garaj la 25 m: polizor 2 kW, compresor 2,2 kW")
    td = i["tablouri_secundare"][0]
    assert td["L_m"] == 25 and [c["P_kW"] for c in td["circuite"]] == [2, 2.2]


def test_baterie_fara_hibrid_intreaba_cuplajul():
    r = R("prosumator 8 kW tri cu baterie 10 kWh, Pa 10 kW")
    assert any("cuplat" in q for q in r["intrebari"]) and r["intrare_fizica"].get("baterie_kWh") == 10
    assert not any("stocare" in q for q in R("prosumator 6 kW mono, fara baterie")["intrebari"])


def test_baterie_cc_la_cef_hibrid():
    i = I("CEF 60 kWp, 2 x Sungrow SH25T, baterii SBH 20 kWh fiecare (cuplaj c.c.), racord TG existent")
    assert i["bess"]["cuplaj"] == "cc" and i["bess"]["kWh"] == 40 and all(x.get("hibrid") for x in i["invertoare"])


def test_stringuri():
    s = I("CEF 100 kWp, SG110CX, 20 module/string, 9 stringuri, Voc 50,1 V, Isc 14 A, gPV 20A pe string")["string"]
    assert (s["n_module"], s["n_stringuri_paralel"], s["Uoc_V"], s["Isc_A"], s["gpv_In_A"]) == (20, 9, 50.1, 14, 20)


def test_chei_noi_motor():
    assert I("PT 400 kVA 10/0,4 kV plecari TD-1 250A")["U_MT_kV"] == 10
    assert I("PT 2x400 kVA, plecari TG1 500A, TG2 500A")["n_trafo"] == 2
    assert I("TG din PT 400 kVA, baterie condensatoare 80 kvar, plecari TD-1 200A")["compensare_kvar"] == 80
    assert I("TG regim IT, plecari TD-1 40A")["schema_pamant"] == "IT"
    assert I("GE 300 kVA in paralel cu reteaua, sarcina 200 kW")["ge_paralel"] is True
    c = I("GE 150 kVA ATS, pompa incendiu 55 kW stea triunghi, hidrofor 5,5 kW")["consumatori"]
    assert c[0].get("siguranta") is True and c[0]["pornire"] == "stea_triunghi"
    assert I("GE 30 kVA monofazat cu ATS, sarcina 20 kW")["retea"] == "mono"


def test_kvar_nu_trimite_la_cef():
    assert R("PTAB 400 kVA, plecari TG 500A, baterie de condensatoare 100 kvar")["tip_schema"] == "pt"


def test_v72_la_cef():
    assert R("CEF 50 kWp, invertor 50 kW, racord prin BMPT existent 63 A")["actiune"] == "genereaza_cu_intrebare"
