"""Regresii runda 8 (teste/r8/{locuinte,fotovoltaic,industrial}.md) — INTERPRETORUL LOCAL (regulile, fără Claude).

1. Fiecare frază r8 (P0/P1 separat de rest) cu verificările din teste/r8/reverificare.py — scrise din „așteptat” și din
   observația testerului (cele 60 din teste/r8/eval_llm.py sunt aceleași), nu din ce face codul.
2. Plasa de siguranță pe toate frazele r8: rest neconsumat ⇒ niciodată „genereaza” fără mențiune.
3. Clasele de greșeli pe formulări NOI (nu cele din rapoarte): tabele copiate (tab / „;” / „,” / „|”, cu și fără antet,
   cantitatea coloanei), legarea valorilor (ATR evacuare / absorbție, Ik ≠ calibru, Zs ≠ RA, „N invertoare” = total,
   „Nk” = kW, autocorecturi, „N x … kWh”), contextul tabloului (siguranță la incendiu, compensare ≠ CEF, cascade, sursa
   ≠ plecare, ACB = general), PV fără cuvânt-cheie, engleză, plasa (nicio dată pierdută).

Rulare: cd /home/claude/sm && python3 -m pytest -q tests/test_interpretor_r8.py
"""
import importlib.util
import sys
from pathlib import Path

import pytest

RAD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAD))

from engine.interpretor import interpreteaza_local  # noqa: E402

_spec = importlib.util.spec_from_file_location("reverificare_r8", RAD / "teste" / "r8" / "reverificare.py")
rv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rv)

CAZURI = rv.incarca()
# verificări care țin de MOTOR (nu de interpretor) — raportate separat, nu ascunse
MOTOR = {"I25": "2 × NA2XY 4x240 în paralel e citit corect (S 240, n 2, Al); V02/V03 BLOCANT vine din dimensionarea "
                "motorului (Iz' 370 A < Ip 598 A) — de verificat în engine/calc, nu în interpretor"}
P01 = [c for c in CAZURI if c[4] in ("P0", "P1")]
REST = [c for c in CAZURI if c[4] not in ("P0", "P1")]


def _verif(fid, text, verif):
    c = rv.rezultat(text)
    verdict, lipsa = rv.evalueaza(verif, c)
    if fid in MOTOR:
        lipsa = [x for x in lipsa if "V02" not in x]
        verdict = "corect" if not lipsa else verdict
    r = c["r"]
    assert verdict == "corect", (lipsa, r["intrare_fizica"], r["intrebari"], r["neconsumat"])


def _id(c):
    return f"{c[1]}-{c[4]}"


@pytest.mark.parametrize("dom,fid,text,vt,prio,verif", P01, ids=[_id(c) for c in P01])
def test_fraza_p0_p1(dom, fid, text, vt, prio, verif):
    _verif(fid, text, verif)


@pytest.mark.parametrize("dom,fid,text,vt,prio,verif", REST, ids=[_id(c) for c in REST])
def test_fraza_restul(dom, fid, text, vt, prio, verif):
    _verif(fid, text, verif)


@pytest.mark.parametrize("text", sorted({c[2] for c in CAZURI}))
def test_plasa_pe_toate_frazele_r8(text):
    d = interpreteaza_local(text)
    assert rv.plasa_ok(d), d["neconsumat"]


# ------------------------------------------------------------------------------- clasele, pe formulări noi
def R(text):
    return interpreteaza_local(text)


def I(text):
    return R(text)["intrare_fizica"]


def inv(i):
    return sorted((x["n"], x["Pn_kW"]) for x in i.get("invertoare") or [])


def npl(i):
    return sum(int(p.get("n_circuite") or 1) for p in i.get("plecari") or [])


def rec(i, r):
    return [x for x in i.get("circuite") or [] if x["receptor"] == r]


def Q(d):
    return " ".join(d["intrebari"] + [d.get("refuz_motiv") or ""] + d["avertismente"]).lower()


# 1. tabele copiate
def test_tabel_tab_cu_antet_cantitate():
    i = I("Denumire\tCantitate\tPutere [kW]\nPompa apa uzata\t2\t4\nVentilator hota\t1\t2,2\nIluminat sala\t1\t3\n"
          "Alimentare din TG existent, TN-S")
    assert i["tip_schema"] == "tablou" and i["origine"] == "tg_existent"
    assert sorted(p["P_kW"] for p in i["plecari"]) == [2.2, 3, 4, 4]


def test_tabel_csv_punct_virgula_faze_la_locuinta():
    i = I("Receptor;Buc;P (kW);Faze\nCuptor;1;3,5;1\nPlita;1;7,2;3\nBoiler;1;2;1\ncasa trifazata 16 kW TN-C-S")
    assert i["alimentare"]["P_aprobata_kW"] == 16 and i["retea"] == "tri"
    assert rec(i, "plita")[0]["P_kW"] == 7.2 and rec(i, "plita")[0]["faza"] == "3F"
    assert rec(i, "cuptor")[0]["P_kW"] == 3.5 and rec(i, "cuptor")[0]["faza"] in ("L1", "L2", "L3")


def test_tabel_virgula_cantitate_si_puncte_zecimale():
    i = I("nume,cant,p_kw\nAC dormitor,2,1.5\nboiler,1,2.4\napartament monofazat 6 kW TN-C-S")
    assert i["alimentare"]["P_aprobata_kW"] == 6
    assert [x.get("P_kW") for x in rec(i, "aer_conditionat")] == [1.5, 1.5]
    assert rec(i, "boiler")[0]["P_kW"] == 2.4


def test_tabel_bara_englezesc_cu_bess():
    i = I("Echipament | Qty | Model\nInverter | 4 | Sungrow SG125CX\nBattery | 1 | PowerStack 200CS 200 kW / 430 kWh\n"
          "Racord in TG existent, TN-S")
    assert inv(i) == [(4, 125)] and i["bess"]["kWh"] == 430 and i["bess"]["P_kW"] == 200


def test_lista_numerotata_cu_zecimale_nu_e_tabel_csv():
    i = I("1. Strung 7,5 kW\n2. Freza 5,5 kW\n3. Compresor 11 kW\nTD atelier din TG existent, TN-S")
    assert [(p["nume"], p["P_kW"]) for p in i["plecari"]] == [("Strung", 7.5), ("Freza", 5.5), ("Compresor", 11)]


def test_tabel_corpuri_iluminat_un_circuit_cu_puterea_totala():
    i = I("Cant;Denumire;P[W]\n10;Corp iluminat LED;50\n4;Ventilator;750\nTD hala din TG existent, TN-S, trifazat")
    il = [p for p in i["plecari"] if "ilumin" in p["nume"].lower()]
    assert len(il) == 1 and il[0]["P_kW"] == 0.5 and npl(i) == 5


def test_tabel_bom_cu_module_kwp_din_cantitate():
    i = I("Poz\tDenumire\tUM\tCant\n1\tModul LONGi 450 Wp\tbuc\t40\n2\tInvertor Huawei SUN2000-17KTL-M2\tbuc\t1\n"
          "3\tStructura aluminiu\tset\t1\nprosumator casa tri pa 20 kW TN-C-S")
    assert i["tip_schema"] == "prosumator" and i["kWp"] == 18 and i["P_aprobata_kW"] == 20


# 2. legarea valorilor de entitate
def test_atr_evacuare_si_absorbtie_nu_sunt_puterea_centralei():
    d = R("putere maxima evacuata 0 kW, putere maxima absorbita 60 kW, CEF 45 kWp cu 1 x SUN2000-40KTL-M3, TG existent")
    i = d["intrare_fizica"]
    assert d["actiune"] != "refuza" and inv(i) == [(1, 40)]
    assert i["limitare_injectie_kW"] == 0 and i["P_evacuata_kW"] == 0 and i["P_aprobata_kW"] == 60


def test_atr_engleza_export_import():
    i = I("Grid connection: approved export 50 kW, approved import 80 kW. PV 70 kWp, 1 x SG60CX, existing LV board, TN-S")
    assert i["limitare_injectie_kW"] == 50 and i["P_aprobata_kW"] == 80 and inv(i) == [(1, 60)]


def test_ik_si_zs_din_atr_nu_sunt_calibru_si_ra():
    i = I("casa trifazata 20 kw tt ra 12 ohm, zs 0,6 ohm, Ik3 = 5 kA")
    assert i["RA_ohm"] == 12 and i["Zb_OD_ohm"] == 0.6 and i["Ik3_OD_kA"] == 5
    assert "In_Q_bransament_A" not in i["alimentare"]


def test_ik_30_ka_nu_devine_0():
    i = I("CEF 50 kW, 1 x SG50CX, racord in TG existent, Ik 30 kA la bara")
    assert i["Ik3_TG_kA"] == 30


def test_cef_total_cu_n_invertoare_fara_model_intreaba():
    d = R("CEF 60 kW cu doua invertoare, TG existent TN-S")
    assert inv(d["intrare_fizica"]) == [(2, 30)] and "30 kw fiecare" in Q(d)


def test_antet_n_invertoare_contradictie_cu_lista():
    d = R("CEF 400 kW cu 3 invertoare: 2 x SG110CX si 2 x SG100CX")
    assert d["actiune"] != "genereaza" and sum(n for n, _ in inv(d["intrare_fizica"])) == 4
    assert all(p != 400 for _, p in inv(d["intrare_fizica"]))


def test_fiecare_cu_cate_un_invertor():
    i = I("CEF 3 x 40 kWp pe 3 hale, fiecare cu cate un SUN2000-40KTL-M3, TG existent TN-S")
    assert inv(i) == [(3, 40)] and i["kWp"] == 120


def test_k_inseamna_kw_si_autocorectura():
    assert I("casa 3F 12k TN-C-S cu PC 8kW")["alimentare"]["P_aprobata_kW"] == 12
    assert I("casa tri 22 kw tncs, scuze, de fapt 25 kw")["alimentare"]["P_aprobata_kW"] == 25
    assert rec(I("apartament 1f 7 kw, plita 7 kw, scuze, de fapt plita 5 kw"), "plita")[0]["P_kW"] == 5
    assert inv(I("CEF 100 kWp, 1 x SG125CX, corectez: SG110CX, TG existent TN-S")) == [(1, 110)]


def test_baterie_n_module_x_kwh():
    assert I("baterie 6 x 2,4 kWh Pylontech, invertor hibrid Deye 12 kW trifazat, casa pa 15 kw tncs")["baterie_kWh"] == 14.4
    b = I("Prosumator 20 kW: 1 x Deye SUN-20K-SG01HP3-EU + 3 x baterii BOS-G 5,12 kWh, tri TN-S")
    assert abs(b["baterie_kWh"] - 15.36) < 0.01


def test_n_pcs():
    b = I("BESS 500 kW / 1 MWh cu 2 x PCS 250 kW, PT nou 630 kVA")["bess"]
    assert b["n_pcs"] == 2 and b["P_kW"] == 500 and b["kWh"] == 1000


def test_kw_si_a_pe_acelasi_receptor():
    d = R("TD din TG, TN-S: compresor 22 kW, 10 A")
    assert d["actiune"] != "genereaza" and "22" in Q(d) and "10" in Q(d)
    d = R("TD atelier din TG, TN-S, trifazat: polizor 3 kW, 16 A, flex 2 kW")
    assert npl(d["intrare_fizica"]) == 2 and "Circuit" not in str(d["intrare_fizica"])


def test_receptoare_monofazate_nu_fac_reteaua_necunoscuta():
    i = I("casa trif 12 kw tncs, boiler monofazat, cuptor monofazat 3 kW")
    assert i["retea"] == "tri" and i["alimentare"]["P_aprobata_kW"] == 12


def test_pompa_de_caldura_termic_vs_electric():
    i = I("casa tri 15kw tncs: pompa caldura 6 kw (termic 18 kw), boiler")
    assert rec(i, "pompa_caldura")[0]["P_kW"] == 6
    i = I("pompa de caldura 15 kW termic, consum electric 4 kW, casa mono 9 kw tncs")
    assert rec(i, "pompa_caldura")[0]["P_kW"] == 4


def test_interval_de_putere_se_intreaba():
    d = R("apartament mono 5-6 kw tncs")
    assert d["actiune"] != "genereaza" and "5" in Q(d) and "6" in Q(d)


# 3. contextul tabloului
def test_siguranta_din_titlu_si_din_nume():
    i = I("TE presurizare scari: 2 ventilatoare 5,5 kW, din TG, TN-S")
    assert i["siguranta_tablou"] is True
    i = I("TG hala din PT 1000: compresor 90 kW, pompa hidranti 37 kW, iluminat 15 kW, TN-S")
    sig = {p["nume"]: p.get("siguranta") for p in i["plecari"]}
    assert sig["Pompa hidranti"] is True and not sig["Compresor"]
    i = I("tablou iluminat siguranta si evacuare: 6 circuite 0,5 kW, din TG, TN-S")
    assert i["siguranta_tablou"] is True


def test_cablu_rezistent_la_foc_pe_plecare():
    i = I("TG din PT 630 kVA: pompa sprinkler 45 kW stea-triunghi cu cablu rezistent la foc, iluminat 10 kW, TN-S")
    p = i["plecari"][0]
    assert p["siguranta"] is True and p["pornire"] == "stea_triunghi" and npl(i) == 2


def test_pompe_incendiu_1_plus_1_pe_ge():
    i = I("statie de pompare incendiu: 2 pompe 55 kW (1+1), pompa jockey 4 kW, din PT 630 kVA si GE 200 kVA prin ATS")
    assert i["tip_schema"] == "ge_ats" and i["P_sarcina_kW"] == 59
    assert all(x["siguranta"] for x in i["consumatori"]) and i["consumatori"][0]["n"] == "1+1"


def test_compensare_nu_e_cef():
    i = I("TG din PT 800 kVA, TN-S, compensare automata 200 kvar, plecari TD1 400A")
    assert i["tip_schema"] == "tablou" and i["compensare_kvar"] == 200
    i = I("baterie automata 150 kvar in 6 trepte, TG din PT 630 kVA, TN-S, plecari TD1 250A, TD2 160A")
    assert i["tip_schema"] == "tablou" and i["compensare_kvar"] == 150 and npl(i) == 2
    d = R("cos fi actual 0,8, dorit 0,95, P = 200 kW, ce baterie trebuie in TG din PT 400?")
    assert d["tip_schema"] == "tablou" and 80 <= d["intrare_fizica"]["compensare_kvar"] <= 90


def test_cascade_in_propozitii_si_paranteze_imbricate():
    i = I("TG din PT 630 kVA, TN-S, alimenteaza TD-1 160A si TD-2 100A. Din TD-1 pleaca TE-A 40A (iluminat 5 kW) si "
          "TE-B 32A (2 motoare 4 kW). TD-2 are pompa 11 kW si compresor 7,5 kW.")
    td1, td2 = i["plecari"]
    assert [k["nume"] for k in td1["copii"]] == ["TE-A", "TE-B"] and len(td1["copii"][1]["copii"]) == 2
    assert len(td2["copii"]) == 2


def test_sursa_si_aparatul_general_nu_sunt_plecari():
    i = I("TG cu ACB 2500A din PT 1600 kVA, TN-S, plecari: TD1 800A, TD2 630A")
    assert i["In_Q1_A"] == 2500 and npl(i) == 2
    i = I("alimentare PT propriu 1000 kVA (ulei, 20/0,4 kV); TG: chiller 200 kW, pompe 2 x 15 kW, TN-S")
    assert i["tip_schema"] == "tablou" and i["pt_Sn_kVA"] == 1000 and npl(i) == 3
    i = I("PT 630 kVA 20/0,4 kV, JT: intrerupator general 1000 A, 4 plecari 250A")
    assert i["In_Q_JT_A"] == 1000 and npl(i) == 4


def test_tablou_cladire_cu_lift_nu_e_locuinta():
    d = R("TG bloc de locuinte cu lift 7,5 kW si iluminat scari 2 kW, din BMPT 63A, TN-C-S")
    assert d["tip_schema"] == "tablou" and npl(d["intrare_fizica"]) == 2


def test_separatori_slash_prescurtari_x_n():
    i = I("tg pt atelier: comp 15kw, vent 4kw x2, ilum 2kw, din tgd, tns")
    assert npl(i) == 4 and i["plecari"][0]["nume"] == "Compresor"
    i = I("TD hala: masini 5 x 4 kW / iluminat 3 kW / prize 3 circ, din TG existent, TN-S")
    assert npl(i) == 9


def test_circuite_finale_mici_monofazate_in_tablou_trifazat():
    i = I("TD cu 6 circuite de prize 16A si 4 circuite iluminat 10A, din TG existent, trifazat, TN-S")
    assert all(p["retea"] == "mono" for p in i["plecari"]) and i["retea"] == "tri"


def test_pt_sursa_suprasolicitat_intreaba():
    d = R("TG din PT 250 kVA, TN-S, plecari: TD1 80 kW, TD2 90 kW, TD3 110 kW")
    assert "250" in Q(d)


def test_pta_si_comutator_manual():
    assert I("PTA pe stalp 160 kVA 20/0,4 kV, plecari 2 x 100A")["pt_aerian"] is True
    assert I("GE 60 kVA cu comutator manual pentru ferma, din BMPT 63A, consumatori: muls 5,5 kW, racire 7,5 kW")[
        "comutare"] == "manual"


# 4. PV fără cuvânt-cheie, prosumator
def test_pv_fara_cuvant_cheie_si_casa_pa():
    i = I("panouri 10 kw pe casa de 15 kw tri, tn-c-s")
    assert i["tip_schema"] == "prosumator" and i["P_aprobata_kW"] == 15 and i["Pn_inv_kW"] == 10
    i = I("SUN2000-10KTL-M1 cu LUNA2000-10-S0, casa tri pa 12")
    assert i["P_aprobata_kW"] == 12 and i["baterie_kWh"] == 10


def test_invertoare_monofazate_repartizate_pe_faze():
    i = I("2 x Fronius Primo 5.0-1 pe casa trifazata 15 kW, cate unul pe faza")
    assert sorted(x["faza"] for x in i["invertoare"]) == ["L1", "L2"]
    i = I("prosumator 3 x SUN2000-5KTL-L1 pe trifazat, pa 15 kw")
    assert sorted(x["faza"] for x in i["invertoare"]) == ["L1", "L2", "L3"]


def test_sunny_boy_cu_storage_si_byd():
    i = I("Sunny Boy 5.0 + Sunny Boy Storage 3.7 cu BYD HVS 7.7, casa mono pa 7 kw TN-C-S")
    assert inv(i) == [(1, 5)] and i["bess"]["cuplaj"] == "ca" and i["bess"]["kWh"] == 7.7


def test_luna_c_and_i_si_zero_export():
    i = I("CEF 200 kWp, 2 x SUN2000-100KTL-M2, BESS LUNA2000-200KWH-2H1, zero export, TG existent, TN-S")
    assert i["bess"]["kWh"] == 200 and i["bess"]["P_kW"] == 100 and i["limitare_injectie_kW"] == 0


def test_iac_peste_bmpt_intreaba():
    d = R("prosumator 40 kW, 1 x SUN2000-40KTL-M3, BMPT 3x32 A existent, TN-C-S")
    assert "32" in " ".join(d["intrebari"])


# 5. engleză
def test_engleza_casa():
    i = I("Three-phase house, 25 kW approved, TT earthing, heat pump 10 kW, EV charger 11 kW, induction hob, "
          "2 air conditioners")
    assert i["tip_schema"] == "locuinta" and i["retea"] == "tri" and i["alimentare"]["P_aprobata_kW"] == 25
    assert i["schema_pamant"] == "TT" and len(rec(i, "aer_conditionat")) == 2 and rec(i, "vehicul_electric")


def test_engleza_tablou_industrial_si_cef():
    i = I("Main switchboard fed from own substation 1000 kVA, TN-S, feeders: chiller 150 kW, 3 x pumps 15 kW, "
          "lighting 20 kW")
    assert i["tip_schema"] == "tablou" and i["pt_Sn_kVA"] == 1000 and npl(i) == 5
    i = I("PV plant 1 MWp, 10 x SG100CX, new 1250 kVA transformer, MV metering")
    assert i["masura"] == "MT" and i["pt_Sn_kVA"] == 1250 and i["pt_existent"] is False
    i = I("house 3-phase 20 kW approved, TN-C-S, with 15 kVA generator and ATS")
    assert i["tip_schema"] == "locuinta" and i["ge_rezerva"] == {"Sn_kVA": 15, "comutare": "ATS"}


# 6. plasa: nicio dată pierdută
def test_plasa_locuinta_aircon_led_frigider():
    d = R("casa tri 20 kw tncs, aircon x3, led 24V gradina, frigider separat")
    i = d["intrare_fizica"]
    assert len(rec(i, "aer_conditionat")) == 3 and any("SELV" in x["nume"] for x in rec(i, "iluminat"))
    assert not d["neconsumat"]


def test_plasa_prize_auto_te_garaj():
    i = I("casa mono 9 kw tncs, doua prize auto 3,7 kw in garaj")
    assert [x["P_kW"] for x in rec(i, "vehicul_electric")] == [3.7, 3.7]
    i = I("TE garaj alimentat din TG casa cu CYY-F 5x4 25m: prize 2 circ, iluminat, statie VE 11 kW; casa tri 20 kw tncs")
    td = i["tablouri_secundare"][0]
    assert td["L_m"] == 25 and td["cablu"]["S_fortat"] == 4 and len(td["circuite"]) == 4
    assert [x.get("receptor") for x in td["circuite"][:3]] == ["prize", "prize", "iluminat"]
    assert not any("In_A" in x for x in td["circuite"])


def test_fara_intrebari_inutile_cand_datele_sunt_clare():
    for t in ("casa tri 18 kw tncs, saună 9 kW, boiler 2 kW, VE 11 kW",
              "CEF 150 kW, 3 invertoare de 50 kW, TG existent TN-S",
              "TG din PT 400 kVA, plecari: TD-A 160A (TE-1 32A, TE-2 40A), TD-B 100A, TN-S"):
        assert R(t)["actiune"] == "genereaza", t
