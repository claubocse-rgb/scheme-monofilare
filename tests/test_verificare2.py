"""Defectele găsite la verificarea independentă (/home/claude/verif2/RAPORT_VERIFICARE.md, secțiunea 3) — SPEC v1.2.

Fiecare test folosește intrarea exactă din raport (sau una echivalentă) și valorile calculate de mână (în comentarii).
Regula comună: nicio intrare nu are voie să dea o schemă exportabilă (fără BLOCANT) dar greșită tehnic, iar nicio intrare
validă nu are voie să cadă cu excepție Python (mesaj V07 „TypeError …”).
"""
import math
import os
import sys

import pytest

RADACINA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RADACINA)

from engine.calc import calculeaza, text_lista, text_desen  # noqa: E402
from engine.calc import norme  # noqa: E402

U3 = math.sqrt(3) * 400.0      # 692,82 V


def blocante(r):
    return {(v["cod"], v["obiect"]) for v in r["verificari"] if v["nivel"] == "BLOCANT"}


def avert(r):
    return {(v["cod"], v["obiect"]) for v in r["verificari"] if v["nivel"] == "AVERTISMENT"}


def coduri(r):
    return {v["cod"] for v in r["verificari"]} | {v["cod"] for v in r["info"]}


def fara_exceptie(r):
    """Nicio eroare Python ajunsă în mesaje (V07 „intern”)."""
    for v in r["verificari"]:
        assert "Error" not in v["mesaj"] and "date de intrare incomplete" not in v["mesaj"], v


# ------------------------------------------------------------------------------------------------------------ C2
def test_C2_iac_fisa_neplauzibil_cu_pt():
    # Iac,max fizic minim = Pn/(√3·400) = 110 000/692,82 = 158,77 A > 100 A din „fișă” → V64 BLOCANT (× 8 invertoare)
    r = calculeaza({"tip_schema": "cef", "kWp": 1000, "invertoare": [{"n": 8, "Pn_kW": 110, "Iac_max_A": 100}],
                    "pt_Sn_kVA": 630})
    assert r["blocheaza_export"]
    assert {("V64", f"INV-{i}") for i in range(1, 9)} <= blocante(r)
    assert "158,77" in next(v["mesaj"] for v in r["verificari"] if v["cod"] == "V64")


def test_C2_iac_fisa_neplauzibil_jt():
    # 100 kW: minim 144,34 A > 80 A → V64; schema nu mai ajunge la „racord prin BMPT” cu S = 166 kVA
    r = calculeaza({"tip_schema": "cef", "kWp": 300, "invertoare": [{"n": 3, "Pn_kW": 100, "Iac_max_A": 80}]})
    assert {("V64", "INV-1"), ("V64", "INV-2"), ("V64", "INV-3")} <= blocante(r)


def test_C2_s_total_max_iac_pn():
    # Iac din fișă = Pn/U exact (144,3376 A): S = max(√3·400·144,3376/1000 = 100,0 ; Σ Pn = 100) = 100 kVA, fără V64
    iac = 100_000 / U3
    r = calculeaza({"tip_schema": "cef", "kWp": 120, "invertoare": [{"n": 1, "Pn_kW": 100, "Iac_max_A": iac}]})
    assert "V64" not in coduri(r)
    assert r["rezultat"]["sume"]["S_total_kVA"] == pytest.approx(100.0, rel=1e-6)


# ------------------------------------------------------------------------------------------------------------ C3
def test_C3_cef_monofazat_calcul_230V():
    # Iac = 1,1·5000/230 = 23,913 A; Ip,min = 1,25·5000/230 = 27,174 A → MCB C32 (1P+N); cablu cu 3 conductoare;
    # ΔU = 100·2·23,913·0,030·R'(Cu 6, 70 °C)/230, R' = 3,08·(1 + 0,00393·50) = 3,6852 Ω/km → 2,299 %
    r = calculeaza({"tip_schema": "cef", "retea": "mono", "kWp": 6, "invertoare": [{"n": 1, "Pn_kW": 5}]})
    inv = r["rezultat"]["invertoare"][0]
    assert inv["retea"] == "mono"
    assert inv["Ib_A"] == pytest.approx(23.913, rel=1e-4)
    assert inv["Ip_min_A"] == pytest.approx(27.174, rel=1e-4)
    assert inv["protectie"]["tip"] == "MCB" and inv["protectie"]["In_A"] == 32
    assert inv["cablu"].split()[1].startswith("3×")
    assert inv["dU_ramura_pct"] == pytest.approx(100 * 2 * 23.913 * 0.030 * 3.08 * (1 + 0.00393 * 50) / 230, rel=1e-3)
    assert r["rezultat"]["sume"]["Iac_total_A"] == pytest.approx(23.913, rel=1e-4)
    assert r["rezultat"]["QG"]["poli"] == "2P"
    assert "TC" not in r["rezultat"]                       # măsură directă monofazată (BMPM)
    assert not r["blocheaza_export"]


def test_C3_cef_monofazat_peste_40A():
    # 10 kW mono: Iac = 1,1·10 000/230 = 47,83 A > 40 A (BMPM) → V53 BLOCANT
    r = calculeaza({"tip_schema": "cef", "retea": "mono", "kWp": 11, "invertoare": [{"n": 1, "Pn_kW": 10}]})
    assert ("V53", "schema") in blocante(r)


# ------------------------------------------------------------------------------------------------------------ C4
def test_C4_plecare_prize_primeste_ddr():
    # plecare TG „Prize birouri” 16 A (≤ 32 A) → DDR 30 mA tip A (SR HD 60364-4-41 art. 411.3.3) + V29 INFO
    r = calculeaza({"tip_schema": "tablou", "L_alimentare_m": 30,
                    "plecari": [{"nume": "Prize birouri", "In_A": 16}, {"nume": "Iluminat", "In_A": 10}]})
    pl = r["rezultat"]["plecari"]
    assert pl[0]["receptor"] == "prize"
    assert pl[0]["DDR"] == {"IdN_mA": 30, "tip": "A", "In_A": 25, "poli": "4P"}   # RCCB 4P minim 25 A
    assert "DDR" not in pl[1]
    assert "V29" in {i["cod"] for i in r["info"]}


def test_C4_prize_fara_ddr_impus_blocant():
    r = calculeaza({"tip_schema": "tablou", "L_alimentare_m": 30,
                    "plecari": [{"nume": "Prize atelier", "In_A": 32, "DDR": False}]})
    assert ("V29", "P1·Prize atelier") in blocante(r)


def test_C4_prize_peste_32A_fara_ddr():
    r = calculeaza({"tip_schema": "tablou", "L_alimentare_m": 30, "plecari": [{"nume": "Prize hală", "In_A": 40}]})
    assert "DDR" not in r["rezultat"]["plecari"][0]


# ------------------------------------------------------------------------------------------------------------ C6
def test_C6_bransament_coloana_100km_blocant():
    # ΔU 44,28 % la TE (raport) > 5 % chiar la secțiunea maximă → V20 BLOCANT (nu doar V21 AVERTISMENT)
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 15, "L_coloana_m": 100000})
    assert ("V20", "C2") in blocante(r)


def test_C6_bara_td_peste_5_blocant_intre_3_si_5_avertisment():
    r = calculeaza({"tip_schema": "tablou", "L_alimentare_m": 20, "plecari": [{"nume": "TD-1", "P_kW": 100, "L_m": 3000}]})
    assert ("V20", "P1·TD-1") in blocante(r)
    r = calculeaza({"tip_schema": "tablou", "L_alimentare_m": 20, "plecari": [{"nume": "TD-1", "P_kW": 100, "L_m": 1000}]})
    assert ("V21", "P1·TD-1") in avert(r) and not r["blocheaza_export"]


def test_C6_prosumator_marire_automata_la_3_la_suta():
    # 20 kW tri, 200 m: Iac = 1,1·20 000/692,82 = 31,75 A; ΔU = 100·√3·31,75·0,2·R'/400 ≤ 3 % → R' ≤ 1,091 Ω/km
    # Cu 16: R' = 1,15·1,1965 = 1,376 (ΔU 3,78 %) ; Cu 25: R' = 0,727·1,1965 = 0,8699 → ΔU = 2,39 % → Cu 25 mm²
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 20, "In_Q_bransament_A": 40, "L_inv_m": 200})
    inv = r["rezultat"]["INV"]
    assert inv["S_faza_mm2"] == 25.0 and inv["material"] == "Cu"
    assert inv["dU_ramura_pct"] == pytest.approx(100 * math.sqrt(3) * 31.754 * 0.2 * 0.727 * (1 + 0.00393 * 50) / 400,
                                                 rel=1e-3)
    assert ("V21", "INV") in avert(r) and not r["blocheaza_export"]


def test_C6_prosumator_sectiune_impusa_peste_3_blocant():
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 20, "L_inv_m": 200,
                    "cablu": {"S_fortat": 6, "material": "Cu"}})
    assert ("V20", "INV") in blocante(r)


# ------------------------------------------------------------------------------------------------------------ C7
def test_C7_IT_neacoperit():
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 15, "L_coloana_m": 20, "schema_pamant": "IT"})
    assert ("V28", "schema") in blocante(r)
    assert "nu este acoperită" in r["verificari"][0]["mesaj"]


def test_C7_TN_C_in_aval_de_DDR():
    r = calculeaza({"tip_schema": "tablou", "schema_pamant": "TN-C", "P_kW": 50, "L_alimentare_m": 30,
                    "plecari": [{"nume": "A", "In_A": 32}]})
    assert ("V27", "schema") in blocante(r)


def test_C7_TN_C_din_PT_propriu_permis_si_nota_reala():
    r = calculeaza({"tip_schema": "tablou", "schema_pamant": "TN-C", "origine": "pt_propriu", "pt_Sn_kVA": 400,
                    "ddr_amonte": False, "P_kW": 80, "L_alimentare_m": 30, "plecari": [{"nume": "TD-1", "In_A": 63}]})
    assert "V27" not in coduri(r)
    assert r["rezultat"]["schema_pamant"] == "TN-C" and "TN-C" in r["rezultat"]["nota_schema_pamant"]


def test_C7_TT_nota_din_valoarea_reala():
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 15, "L_coloana_m": 20, "schema_pamant": "tt", "RA_ohm": 10})
    assert r["rezultat"]["schema_pamant"] == "TT"
    assert r["rezultat"]["nota_schema_pamant"].startswith("Schemă de legare la pământ: TT")


# ------------------------------------------------------------------------------------------------------------ C8
@pytest.mark.parametrize("retea, bloc", [("trifazat", "BMPTd-40"), ("TRI", "BMPTd-40")])
def test_C8_sinonime_trifazat(retea, bloc):
    # Ib = 15 000/(692,82·0,9) = 24,06 A → BMPTd-40, Q C25
    r = calculeaza({"tip_schema": "bransament", "P_kW": 15, "L_coloana_m": 20, "retea": retea})
    assert r["rezultat"]["Ib_A"] == pytest.approx(24.056, rel=1e-4)
    assert r["rezultat"]["bloc"] == bloc and r["rezultat"]["Q"]["In_A"] == 25


def test_C8_monofazat_normalizat():
    # „monofazat”: Ib = 15 000/(230·0,9) = 72,46 A > 40 A → V53 (nu bloc trifazat cu Ib monofazat)
    r = calculeaza({"tip_schema": "bransament", "P_kW": 15, "L_coloana_m": 20, "retea": "monofazat"})
    assert ("V53", "schema") in blocante(r)
    r = calculeaza({"tip_schema": "bransament", "P_kW": 5, "L_coloana_m": 20, "retea": "Mono"})
    assert r["rezultat"]["bloc"] == "BMPM-25"            # 5000/(230·0,9) = 24,15 A


@pytest.mark.parametrize("retea", ["bi", "3f+N", "", 3])
def test_C8_retea_invalida_V12(retea):
    r = calculeaza({"tip_schema": "bransament", "P_kW": 15, "L_coloana_m": 20, "retea": retea})
    assert ("V12", "schema") in blocante(r)
    r = calculeaza({"tip_schema": "prosumator", "retea": retea, "Pn_inv_kW": 5})
    assert ("V12", "schema") in blocante(r)


# ------------------------------------------------------------------------------------------------------------ C9
def test_C9_beta_pozitiv_blocant():
    # cu β = +0,27 Uoc(−25 °C) ar ieși 942 V (OK fals); corect: 22·49,5·(1 + 0,0027·50) = 1236 V > 1100 V
    r = calculeaza({"tip_schema": "cef", "kWp": 50, "invertoare": [{"n": 1, "Pn_kW": 50}],
                    "string": {"n_module": 22, "Uoc_V": 49.5, "beta": 0.27, "Umax_inv_V": 1100}})
    assert ("V68", "schema") in blocante(r)
    assert "Uoc_Tmin_V" not in r["rezultat"]
    r = calculeaza({"tip_schema": "cef", "kWp": 50, "invertoare": [{"n": 1, "Pn_kW": 50}],
                    "string": {"n_module": 22, "Uoc_V": 49.5, "beta": -0.27, "Umax_inv_V": 1100}})
    assert r["rezultat"]["Uoc_Tmin_V"] == pytest.approx(22 * 49.5 * (1 + 0.0027 * 50), rel=1e-9)   # 1236,0 V
    assert ("V68", "schema") in blocante(r)


# ------------------------------------------------------------------------------------------------------------ C10 / M8
@pytest.mark.parametrize("inp, cod", [
    ({"tip_schema": "ge_ats", "Sn_GE_kVA": 100, "P_sarcina_kW": 0}, "V07"),
    ({"tip_schema": "tablou", "ks": 1.5, "L_alimentare_m": 30, "plecari": [{"nume": "A", "In_A": 32}]}, "V10"),
    ({"tip_schema": "bransament", "retea": "tri", "P_kW": 60, "L_coloana_m": 50, "Ik3_OD_kA": -3}, "V07"),
    ({"tip_schema": "bransament", "retea": "tri", "P_kW": 60, "L_coloana_m": 50, "Ik3_OD_kA": 0}, "V07"),
    ({"tip_schema": "pt", "Sn_kVA": 1000, "SkQ_MVA": -50, "plecari": [{"nume": "TD-1", "In_A": 400}]}, "V07"),
    ({"tip_schema": "ge_ats", "Sn_GE_kVA": 100, "P_sarcina_kW": 60, "xd": 0}, "V07"),
    ({"tip_schema": "cef", "kWp": 50, "invertoare": [{"n": 1, "Pn_kW": 50}],
      "string": {"n_module": 0, "Uoc_V": 49.5}}, "V07"),
    ({"tip_schema": "cef", "kWp": 0, "invertoare": [{"n": 1, "Pn_kW": 50}]}, "V07"),
    ({"tip_schema": "cef", "kWp": 50, "invertoare": [{"n": 0, "Pn_kW": 50}]}, "V07"),
    ({"tip_schema": "bransament", "retea": "tri", "P_kW": 15, "L_coloana_m": -5}, "V09"),
    ({"tip_schema": "bransament", "retea": "tri", "P_kW": "15", "L_coloana_m": 20}, "V07"),
    ({"tip_schema": "bransament", "retea": "tri", "P_kW": float("nan"), "L_coloana_m": 20}, "V07"),
    ({"tip_schema": "bransament", "retea": "tri", "P_kW": 15, "L_coloana_m": 20, "material": "Fe"}, "V10"),
    ({"tip_schema": "ge_ats", "Sn_GE_kVA": 0, "P_sarcina_kW": 60}, "V07"),
    ({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 0}, "V07"),
])
def test_C10_M8_valori_absurde_blocante(inp, cod):
    r = calculeaza(inp)
    assert r["blocheaza_export"]
    assert any(v["cod"] == cod and v["nivel"] == "BLOCANT" for v in r["verificari"]), r["verificari"]
    fara_exceptie(r)


# ------------------------------------------------------------------------------------------------------------ M1
def test_M1_bransament_dict_cablu_respectat():
    # Ib = 60 000/(692,82·0,9) = 96,23 A → BMPTd-100, Q C100 → Iz' ≥ 100 A; Cu XLPE metoda E (3 conductoare
    # încărcate): Iz(16) = 100 A (IEC 60364-5-52 tab. B.52.12) → Cu 16 mm²
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 60, "L_coloana_m": 30,
                    "cablu": {"material": "Cu", "izolatie": "XLPE", "metoda": "E"}})
    c2 = r["rezultat"]["C2"]
    assert (c2["material"], c2["izolatie"], c2["metoda"]) == ("Cu", "XLPE", "E")
    assert c2["S_faza_mm2"] == 16.0 and c2["Iz_tabel_A"] == norme.iz_tabel("Cu", "XLPE", "E", 3, 16.0) == 100


def test_M1_bransament_S_fortat_verificat():
    # Al 25 mm² D1 PVC: Iz' = 64 A < Ip = 100 A → V02; I2 = 1,45·100 = 145 > 1,45·64 = 92,8 → V03
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 60, "L_coloana_m": 30, "cablu": {"S_fortat": 25}})
    assert {("V02", "C2"), ("V03", "C2")} <= blocante(r)
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 10, "L_coloana_m": 30, "cablu": {"S_fortat": 10, "material": "Al"}})
    assert ("V13", "C2") in blocante(r)


# ------------------------------------------------------------------------------------------------------------ M2
def test_M2_zb_modul_acceptat():
    # |Z| = 2 Ω cu R/X = 2 (ca 0,18 + j0,09): R = 2·0,18/0,20125 = 1,789 Ω, X = 0,894 Ω; Ik1 la origine = 0,95·230/2
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 60, "L_coloana_m": 50, "Zb_OD_ohm": 2.0})
    fara_exceptie(r)
    c2 = r["rezultat"]["C2"]
    assert c2["Ik1min_capat_A"] < 0.95 * 230 / 2.0
    assert any("modul" in p for p in r["presupus"])
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 60, "L_coloana_m": 50, "Zb_OD_ohm": [0.5, 0.2]})
    fara_exceptie(r)
    assert r["rezultat"]["C2"]["Ik1min_capat_A"] < 0.95 * 230 / math.hypot(0.5, 0.2)


@pytest.mark.parametrize("zb", [0, -1, [0, 0], [-0.1, 0.2], "x"])
def test_M2_zb_invalid_mesaj_clar(zb):
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 60, "L_coloana_m": 50, "Zb_OD_ohm": zb})
    assert ("V07", "schema") in blocante(r)
    fara_exceptie(r)


# ------------------------------------------------------------------------------------------------------------ M3
@pytest.mark.parametrize("sn, In, ir", [(1250, 2000, 1800.0), (2000, 3200, 2880.0)])
def test_M3_ge_mare_acb(sn, In, ir):
    # In_G = 1250 000/692,82 = 1804,2 A → ACB 2000 A, Ir = 0,90·2000 = 1800 A ≤ In_G; 2000 kVA: 2886,8 A → ACB 3200, Ir 2880
    r = calculeaza({"tip_schema": "ge_ats", "Sn_GE_kVA": sn, "P_sarcina_kW": sn * 0.8})
    fara_exceptie(r)
    q = r["rezultat"]["Q_G"]
    assert q["tip"] == "ACB" and q["In_A"] == In and q["Ir_A"] == pytest.approx(ir)
    assert q["Ir_A"] <= r["rezultat"]["In_G_A"]
    assert q["Icu_kA"] >= r["rezultat"]["Ik3_GE_kA"]


# ------------------------------------------------------------------------------------------------------------ M4
def test_M4_cef_bmpt_qg_peste_250():
    # Iac = 1,1·157 000/692,82 = 249,27 A (S = 172,7 kVA ≤ 173 → BMPT); Ip,min = 1,25·157 000/692,82 = 283,26 A
    # → QG MCCB 320 A, Ir = 0,90·320 = 288 A > 250 A (Q BMPTi-250) → V66 BLOCANT
    r = calculeaza({"tip_schema": "cef", "kWp": 160, "invertoare": [{"n": 1, "Pn_kW": 157}]})
    assert r["rezultat"]["QG"]["Ir_A"] == pytest.approx(288.0)
    assert ("V66", "schema") in blocante(r)
    assert r["rezultat"]["racord"]["tip"] == "JT prin BMPT"


# ------------------------------------------------------------------------------------------------------------ M9
def test_M9_ik1_nu_depaseste_ik3():
    # Ik3 OD 0,5 kA: Z_Q = 1,1·400/(√3·500) = 0,5081 Ω → Zb implicit ridicat la (0,18 ; 2·0,5056 = 1,0111) Ω
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 60, "L_coloana_m": 50, "Ik3_OD_kA": 0.5})
    c2 = r["rezultat"]["C2"]
    assert c2["Ik1min_capat_A"] <= c2["Ik3max_capat_kA"] * 1000
    assert c2["Ik1min_capat_A"] < 0.95 * 230 / math.hypot(0.18, 1.0111) + 1e-6
    assert "V15" not in coduri(r)
    # date incoerente introduse de utilizator → V15 BLOCANT
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 60, "L_coloana_m": 5, "Ik3_OD_kA": 0.5, "Zb_OD_ohm": 0.05})
    assert ("V15", "C2") in blocante(r)


# ------------------------------------------------------------------------------------------------------------ M10
def test_M10_motor_pornire_directa():
    # Ib = 45 000/(692,82·0,85) = 76,41 A; Ip pornire = 6·76,41 = 458,5 A. gG 80 (Imin 10 s = 215 A) s-ar topi →
    # MCCB TM 80 A, Ir = 1,00·80 = 80 A, prag 0,8·Im = 640 A ≥ 458,5 A (V23 INFO); ΔU la pornire calculat (V22)
    r = calculeaza({"tip_schema": "tablou", "L_alimentare_m": 30,
                    "plecari": [{"nume": "Compresor", "P_kW": 45, "receptor": "motor", "L_m": 120, "randament": 1.0, "cosfi": 0.85}]})
    p = r["rezultat"]["plecari"][0]
    assert p["Ib_A"] == pytest.approx(76.414, rel=1e-4)
    assert p["protectie"]["tip"] == "MCCB" and p["protectie"]["In_A"] == 80 and p["protectie"]["Ir_A"] == 80.0
    assert p["Ip_pornire_A"] == pytest.approx(6 * 76.414, rel=1e-4)
    assert p["dU_pornire_pct"] > p["dU_cumulat_pct"]
    assert "V23" in {i["cod"] for i in r["info"]}
    assert ("V22", "P1·Compresor") in avert(r)            # 12,6 % > 12 % (SPEC §B.12)


def test_M10_motor_gG_impus_marit():
    # gG impus: Imin(10 s) ≥ 458,5 A → gG 125 (355 A) nu; gG 160 (465 A) da → In = 160 A
    r = calculeaza({"tip_schema": "tablou", "L_alimentare_m": 30,
                    "plecari": [{"nume": "Compresor", "P_kW": 45, "receptor": "motor", "L_m": 120, "prot_tip": "gG",
                                  "randament": 1.0, "cosfi": 0.85}]})
    p = r["rezultat"]["plecari"][0]
    assert p["protectie"]["tip"] == "gG" and p["protectie"]["In_A"] == 160


def test_M10_motor_mcb_c_marit():
    # circuit final motor 5,5 kW: Ib = 5500/(692,82·0,85) = 9,34 A; Ip = 56,0 A; MCB C: 5·In ≥ 56 → In = 13 A
    r = calculeaza({"tip_schema": "tablou", "circuite_finale": True, "L_alimentare_m": 20,
                    "plecari": [{"nume": "Pompă", "P_kW": 5.5, "receptor": "motor", "randament": 1.0, "cosfi": 0.85}]})
    p = r["rezultat"]["plecari"][0]
    assert p["protectie"]["tip"] == "MCB" and p["protectie"]["curba"] == "C" and p["protectie"]["In_A"] == 13


# ------------------------------------------------------------------------------------------------------------ M11
def test_M11_bloc_diferential_peste_125A_si_selectiv():
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 150, "L_coloana_m": 80})
    rc = r["rezultat"]["RCCB"]
    assert rc["aparat"] == "bloc_diferential" and rc["In_A"] == 250 and rc["selectiv"] is True
    den, _ = text_lista("rccb", {"In_A": 250, "poli": "4P", "IdN_mA": 300, "tip_ddr": "AC", "selectiv": True})
    assert den.startswith("Bloc diferențial asociat întreruptorului Q (MCCB 4P") and den.endswith("tip AC, S")
    assert "RCCB" not in den and "Întreruptor diferențial" not in den
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 60, "L_coloana_m": 30})
    assert r["rezultat"]["RCCB"]["aparat"] == "RCCB" and r["rezultat"]["RCCB"]["selectiv"] is True
    assert text_desen("rccb", {"In_A": 100, "IdN_mA": 300, "tip_ddr": "AC", "selectiv": True})[-1].endswith("AC S")


# ------------------------------------------------------------------------------------------------------------ M12
def test_M12_icu_q_bmpti_calcul_egal_desen():
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 150, "L_coloana_m": 80})
    assert r["rezultat"]["Q"]["Icu_kA"] == 25 and r["rezultat"]["C2"]["protectie"]["Icu_kA"] == 25


# ------------------------------------------------------------------------------------------------------------ minore
def test_minor_ge_qg_ir_sub_in_g_si_cabluri_c1_c3():
    # In_G = 100 000/692,82 = 144,34 A → MCCB 160, Ir = 0,90·160 = 144 A ≤ 144,34 A; Ib = 96,23 A
    r = calculeaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 100, "P_sarcina_kW": 60, "L_m": 80})
    z = r["rezultat"]
    assert z["Q_G"]["Ir_A"] == 144.0 and z["Q_G"]["Icu_kA"] >= z["Ik3_GE_kA"]
    assert z["Q_retea"]["Icu_kA"] >= 25.0                       # Ik3 rețea implicit 25 kA
    assert z["C1"]["cablu"].startswith("ACYABY 4×70") and z["C1"]["L_m"] == 80.0   # Ib 96,23 → Al 70 D1
    assert z["C2"]["Ib_A"] == 144.0 and z["C2"]["Ik3max_origine_kA"] == pytest.approx(1.1 * 144.34 / 0.12 / 1000, rel=1e-3)
    # v1.2 R2: C3 în regim rețea e protejat de QR (Ir 100 A), în regim GE (C3.regim_GE) de Q_G (Ir 144 A)
    assert z["C3"]["protectie"]["Ir_A"] == 100.0 and z["C3"]["regim_GE"]["protectie"]["Ir_A"] == 144.0
    assert z["ATS"]["intrari"]["II"].startswith("GE")
    assert not r["blocheaza_export"]


def test_minor_ge_sarcina_peste_ir():
    r = calculeaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 66.67, "P_sarcina_kW": 60})
    assert ("V86", "schema") in blocante(r)


def test_minor_v51_mesaj_bloc_real():
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 15, "L_coloana_m": 20, "masura_ceruta": "semidirecta"})
    v = next(v for v in r["verificari"] if v["cod"] == "V51")
    assert v["mesaj"].endswith("BMPTd-40") and r["rezultat"]["bloc"] == "BMPTd-40"


def test_minor_q_in_si_bmpt_fortat_insuficient():
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 60, "L_coloana_m": 50, "Q_In_A": 63})
    assert ("V04", "Q") in blocante(r)
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 60, "L_coloana_m": 50, "bmpt_fortat": "BMPTd-40"})
    assert ("V50", "schema") in blocante(r)
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 20, "L_coloana_m": 50, "Q_In_A": 100})
    assert r["rezultat"]["bloc"] == "BMPTd-100" and r["rezultat"]["Q"]["In_A"] == 100


@pytest.mark.parametrize("tip", ["altceva", None, 5])
def test_minor_tip_schema_necunoscut(tip):
    inp = {"P_kW": 10} if tip is None else {"tip_schema": tip, "P_kW": 10}
    r = calculeaza(inp)
    assert r["blocheaza_export"] and "tip de schemă necunoscut" in r["verificari"][0]["mesaj"]


def test_minor_tablou_pt_fara_plecari():
    assert ("V07", "schema") in blocante(calculeaza({"tip_schema": "tablou", "P_kW": 50, "plecari": []}))
    assert ("V07", "schema") in blocante(calculeaza({"tip_schema": "pt", "Sn_kVA": 400, "plecari": []}))


def test_minor_gG_icu_120():
    r = calculeaza({"tip_schema": "pt", "Sn_kVA": 2500, "plecari": [{"nume": "TD-1", "In_A": 400}]})
    p = r["rezultat"]["plecari"][0]
    assert p["protectie"]["tip"] == "gG" and p["protectie"]["Icu_kA"] == 120.0
    assert ("V33", "P1·TD-1") not in blocante(r)                # Ik3 bara 2500 kVA ≈ 60 kA < 120 kA


def test_minor_q_jt_electronic_isd_tsd_ii():
    # PT 630: Q MCCB 1000 EL, Ir 950 A; Ik1min bara 21 025 A → m max cu 1,2·m·950 ≤ 21 025 → m = 10 (≤ 18,4)
    q = calculeaza({"tip_schema": "pt", "Sn_kVA": 630, "plecari": [{"nume": "TD-1", "In_A": 250}]})["rezultat"]["Q_JT"]
    assert q["decl"] == "EL" and q["Isd_A"] == 9500.0 and q["tsd_s"] == 0.1 and q["Ii_A"] == 12000.0


def test_minor_h3_peste_33_protectie_neutru():
    r = calculeaza({"tip_schema": "tablou", "P_kW": 100, "L_alimentare_m": 30, "h3": 50,
                    "plecari": [{"nume": "LED", "In_A": 100, "h3": 50}]})
    assert ("V24", "P1·LED") in avert(r) and r["rezultat"]["plecari"][0]["protectie_neutru"] is True


def test_minor_text_termic_pe_ik3():
    # memoriul (pașii): pentru MCCB se scriu ambele cerințe — la Ik1min și la Ik3max — nu „t = 0,3 s la Ik1min”
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 150, "L_coloana_m": 80})
    pas = next(p for p in r["pasi"] if p.startswith("C2: N =") and "termic PE" in p)
    assert "la Ik1min" in pas and "la Ik3max" in pas


def test_minor_niciun_crash_pe_intrari_reale():
    """Toate intrările din scripturile verificatorului (t1…t7) — fără excepții Python."""
    cazuri = [
        {"tip_schema": "bransament", "retea": "tri", "P_kW": 60, "L_coloana_m": 30, "cablu": {"theta": 70}},
        {"tip_schema": "tablou", "P_kW": 50, "L_alimentare_m": 30, "plecari": [{"nume": "A", "In_A": 32, "cablu": {"n_alte": 25}}]},
        {"tip_schema": "cef", "kWp": 0, "invertoare": [], "bess": {"P_kW": 100, "kWh": 200}},
        {"tip_schema": "ge_ats", "Sn_GE_kVA": 3000, "P_sarcina_kW": 2500},
        {"tip_schema": "pt", "Sn_kVA": 630, "plecari": [{"nume": "TD-1", "In_A": 1250, "prot_tip": "MCCB", "L_m": 10,
                                                         "cablu": {"material": "Cu", "izolatie": "XLPE", "metoda": "E"}}]},
        {"tip_schema": "tablou", "plecari": [{"nume": "A", "In_A": 32, "prot_tip": "aM"}]},
        {"tip_schema": "tablou", "plecari": "x"},
        {"tip_schema": "cef", "invertoare": [{"n": 1}]},
        {"tip_schema": "ge_ats"},
        {"tip_schema": "prosumator"},
    ]
    for inp in cazuri:
        r = calculeaza(inp)
        fara_exceptie(r)


# ============================================================================================================
# Runda 2 (/home/claude/verif2/RAPORT_VERIFICARE_R2.md §3)
# ============================================================================================================
from engine.calc import verifica_cablu  # noqa: E402


def test_R2_NC1_ge_bloc_diferential_pe_qg():
    # regim GE: Ik1 ≈ In_G = 144,3 A ≪ Ia(Q_G MCCB 160) = 1,2·10·160 = 1920 A → bloc diferențial 300 mA A S pe Q_G;
    # Zs·IΔn ≤ U0 ⇔ Ik1 ≥ IΔn: 143 A ≫ 0,3 A → deconectare asigurată (V85 INFO)
    r = calculeaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 100, "P_sarcina_kW": 60})
    z = r["rezultat"]
    assert z["Q_G"]["DDR"] == {"aparat": "bloc_diferential", "asociat": "Q_G", "tip_q": "MCCB", "IdN_mA": 300,
                               "tip": "A", "selectiv": True, "In_A": 160, "poli": "4P"}
    assert not r["blocheaza_export"]
    assert ("V85", "schema") in {(i["cod"], i["obiect"]) for i in r["info"]}
    assert ("V31", "C3 (regim GE)") not in avert(r)          # nu mai pretinde un „DDR din amonte” inexistent
    g = z["C3"]["regim_GE"]
    assert g["obiect"] == "C3 (regim GE)" and g["protectie"]["Ir_A"] == 144.0
    assert g["Ik1min_capat_A"] < g["Ia_A"]                    # regimul GE e cel defavorabil, verificat separat
    assert z["C3"]["protectie"]["Ir_A"] == 100.0             # regimul rețea: QR, cu Ik-ul rețelei
    assert z["C3"]["Ik1min_capat_A"] > g["Ik1min_capat_A"]


def test_R2_NC1_ge_fara_ddr_blocant():
    r = calculeaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 100, "P_sarcina_kW": 60, "DDR_GE": False})
    assert ("V85", "schema") in blocante(r) and ("V85", "C3 (regim GE)") in blocante(r)


def test_R2_NC2_tablou_TT_ddr_pe_fiecare_circuit():
    # RA = 500 Ω: IΔn ≤ 50/500 = 0,1 A; amonte declarat 100 mA S (R3: RCCB-ul BMPT de 300 mA ar da 150 V → V34).
    # v1.3 R5 (M5-4): Q1 fără DDR propriu (protejat de amonte, un al doilea DDR S nu ar fi selectiv); plecări 30 mA
    # instantaneu (≤ 100/3); nota 3 descrie DDR-urile reale
    r = calculeaza({"tip_schema": "tablou", "schema_pamant": "TT", "RA_ohm": 500, "IdN_amonte_mA": 100,
                    "L_alimentare_m": 30, "plecari": [{"nume": "Hala", "In_A": 63}]})
    z = r["rezultat"]
    assert z["plecari"][0]["DDR"]["IdN_mA"] == 30 and "DDR" not in z["Q1_C1"]
    nota = z["nota_schema_pamant"].replace(" ", " ")
    assert "IΔn 100" in nota and "= 50 V ≤ 50 V" in nota and "Q1 fără DDR propriu" in nota and "circuite IΔn 30 mA" in nota
    assert not any(v["cod"] == "V30" for v in r["verificari"])          # deconectarea prin DDR, Ia doar informativ
    # RA = 2000 Ω: chiar 30 mA → 60 V > 50 V → V34 BLOCANT
    r = calculeaza({"tip_schema": "tablou", "schema_pamant": "TT", "RA_ohm": 2000, "L_alimentare_m": 30,
                    "plecari": [{"nume": "Hala", "In_A": 63}]})
    assert ("V34", "schema") in blocante(r)
    # DDR refuzat explicit în TT → V34 BLOCANT
    r = calculeaza({"tip_schema": "tablou", "schema_pamant": "TT", "L_alimentare_m": 30,
                    "plecari": [{"nume": "Hala", "In_A": 63, "DDR": False}]})
    assert ("V34", "P1·Hala") in blocante(r)


@pytest.mark.parametrize("cheie", ["retea", "schema_pamant", "origine", "masura_ceruta"])
def test_R2_NC3_enumerari_null_ca_absente(cheie):
    # null = absent: trifazat, Ib = 15 000/(692,82·0,9) = 24,06 A → BMPTd-40, C25 (nu formula /230)
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 15, "L_coloana_m": 20, cheie: None})
    if cheie == "retea":
        # v1.5: rețeaua null / lipsă la branșament nu se mai presupune trifazată → V07 BLOCANT pe „retea”
        assert ("V07", "retea") in blocante(r)
        return
    assert r["rezultat"]["Ib_A"] == pytest.approx(24.056, rel=1e-4) and r["rezultat"]["bloc"] == "BMPTd-40"
    assert not r["blocheaza_export"]


def test_R2_NC3_retea_non_string_V12():
    for v in (3, True, ["tri"]):
        r = calculeaza({"tip_schema": "bransament", "P_kW": 15, "L_coloana_m": 20, "retea": v})
        assert ("V12", "schema") in blocante(r)


def test_R2_NM2_tn_c_pen_in_cablu():
    r = calculeaza({"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 400, "schema_pamant": "TN-C",
                    "P_kW": 60, "L_alimentare_m": 30, "plecari": [{"nume": "Hala", "In_A": 63}]})
    c1 = r["rezultat"]["Q1_C1"]
    assert c1["PE"] == "PEN" and c1["S_PE_mm2"] == c1["S_N_mm2"]
    assert c1["cablu"].replace(" ", " ") == "ACYABY 4×70 mm² (PEN)" and "FY" not in c1["cablu"]


@pytest.mark.parametrize("pl, cod", [
    ({"nume": "Compresor", "P_kW": 45, "receptor": "motor", "pornire": "abc"}, "V12"),
    ({"nume": "A", "P_kW": 10, "receptor": "xyz"}, "V12"),
    ({"nume": "A", "In_A": 32, "prot_tip": "aM"}, "V12"),
    ({"nume": "A", "In_A": 32, "curba": "K"}, "V12"),
    ({"nume": "A", "In_A": 32, "cablu": {"metoda": "Z"}}, "V10"),
    ({"nume": "A", "In_A": 32, "cablu": {"izolatie": "EPR"}}, "V10"),
    ({"nume": "A", "In_A": 32, "cablu": {"material": "Fe"}}, "V10"),
])
def test_R2_NM3_enumerari_invalide(pl, cod):
    r = calculeaza({"tip_schema": "tablou", "L_alimentare_m": 30, "plecari": [pl]})
    assert any(v["cod"] == cod and v["nivel"] == "BLOCANT" for v in r["verificari"]), r["verificari"]
    fara_exceptie(r)


def test_R2_NM3_enumerari_sinonime():
    r = calculeaza({"tip_schema": "tablou", "L_alimentare_m": 30,
                    "plecari": [{"nume": "Compresor", "P_kW": 45, "receptor": "Motor", "pornire": "Directă"}]})
    assert r["rezultat"]["plecari"][0]["pornire"] == "directa"


def test_R2_NM4_servicii_proprii_gG_cablu_mic():
    # PT 1600 kVA: Ik3 bară 39,66 kA > 25 kA (Icn max MCB) → gG 16 A, Icu 120 kA; PE termic cu I²t limitat:
    # 2·1000 A²s → S ≥ √2000/115 = 0,39 mm² → cablu Cu PVC C 5×4 mm² (min. 4 mm² coloană), PE în cablu
    s = calculeaza({"tip_schema": "pt", "Sn_kVA": 1600, "plecari": [{"nume": "TD-1", "In_A": 630}]})["rezultat"]["servicii_proprii"]
    assert s["protectie"]["tip"] == "gG" and s["protectie"]["In_A"] == 16 and s["protectie"]["Icu_kA"] == 120.0
    assert s["S_faza_mm2"] <= 6 and s["PE"] == "cablu" and s["cablu"].startswith("CYY-F 5×")
    # PT 630 kVA: MCB 16 A (23,7 kA ≤ 25 kA), PE rămâne în cablu (5×S, Cu ≤ 35 mm²), nu „4×6 + FY 1×6”
    s = calculeaza({"tip_schema": "pt", "Sn_kVA": 630, "plecari": [{"nume": "TD-1", "In_A": 250}]})["rezultat"]["servicii_proprii"]
    assert s["protectie"]["tip"] == "MCB" and s["PE"] == "cablu" and "FY" not in s["cablu"]


@pytest.mark.parametrize("sn, n, S", [(800, 2, 240.0), (2000, 5, 300.0)])
def test_R2_NM5_ge_mare_cabluri_monopolare(sn, n, S):
    # 800 kVA: Q_G MCCB 1250, Ir = 0,90·1250 = 1125 A; F treflă Cu XLPE 240: 2·607·0,97 = 1177,6 A (B.52.21, raport #17) ≥ 1125 A
    # 2000 kVA: ACB 3200, Ir = 2880 A; 300 mm²: 5·703·0,92 = 3233,8 A ≥ 2880 A (4·703·0,93 = 2615 A < 2880 A)
    # R3 (N3-M1): rețeaua normală de > 250 A trebuie să fie un PT (aici PT propriu 1000 / 2000 kVA)
    r = calculeaza({"tip_schema": "ge_ats", "Sn_GE_kVA": sn, "P_sarcina_kW": sn * 0.75, "origine": "pt_propriu",
                    "pt_Sn_kVA": {800: 1000, 2000: 2000}[sn]})
    assert not r["blocheaza_export"], blocante(r)
    c2 = r["rezultat"]["C2"]
    assert c2["metoda"] == "F_trefla" and c2["n_paralel"] == n and c2["S_faza_mm2"] == S
    k = {2: 0.97, 5: 0.92}[n]
    iz = {240.0: 607, 300.0: 703}[S]
    assert c2["Iz_corectat_A"] == pytest.approx(n * iz * k)
    assert ("V45", "QG/C2") in avert(r)
    assert any("monopolare" in p for p in r["presupus"])


def test_R2_verifica_cablu():
    # CYABY 5×10 Cu PVC D1: Iz = 50 A (din tabel, nu 500 A din parametri); gG 50: I2 = 1,6·50 = 80 > 1,45·50 = 72,5 → V03
    v = verifica_cablu({"material": "Cu", "izolatie": "PVC", "metoda": "D1", "S_faza_mm2": 10, "n_paralel": 1,
                        "Iz_corectat_A": 500}, {"tip": "gG", "In_A": 50})
    assert [x["cod"] for x in v if x["nivel"] == "BLOCANT"] == ["V03"]
    info = [x for x in v if x["nivel"] == "INFO"][0]
    assert info["Iz_corectat_A"] == 50.0 and info["Iz_declarat_A"] == 500
    # ACYABY 4×70 D1: Iz' 112 A < MCB C125 → V02 + V03
    v = verifica_cablu({"material": "Al", "metoda": "D1", "S_faza_mm2": 70}, {"tip": "MCB", "In_A": 125, "curba": "C"})
    assert {x["cod"] for x in v if x["nivel"] == "BLOCANT"} == {"V02", "V03"}
    # Al 10 mm² nu există → V13; material necunoscut → V10
    assert verifica_cablu({"material": "Al", "metoda": "D1", "S_faza_mm2": 10}, {"tip": "MCB", "In_A": 16})[0]["cod"] == "V13"
    assert verifica_cablu({"material": "Fe", "metoda": "D1", "S_faza_mm2": 10}, {"tip": "MCB", "In_A": 16})[0]["cod"] == "V10"
    # cablu corect: fără BLOCANT
    v = verifica_cablu({"material": "Al", "metoda": "D1", "S_faza_mm2": 70}, {"tip": "MCB", "In_A": 100})
    assert not [x for x in v if x["nivel"] == "BLOCANT"]


def test_R2_minore():
    # Iac,max = Pn/U rotunjit la 2 zecimale (158,77 A la 110 kW) → fără V64 (toleranță 0,1 %)
    r = calculeaza({"tip_schema": "cef", "kWp": 120, "invertoare": [{"n": 1, "Pn_kW": 110, "Iac_max_A": 158.77}]})
    assert "V64" not in coduri(r)
    # „Sockets” = circuit de prize → DDR 30 mA
    r = calculeaza({"tip_schema": "tablou", "L_alimentare_m": 30, "plecari": [{"nume": "Sockets office", "In_A": 16}]})
    assert r["rezultat"]["plecari"][0]["DDR"]["IdN_mA"] == 30
    # ks la branșament: declarat (nu ignorat tacit)
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 15, "L_coloana_m": 20, "ks": 0.8})
    assert any("ks" in p for p in r["presupus"])
    # ΔU la pornire fără dubla numărare: Compresor 45 kW → ≈ 12,0 % (înainte 12,62 %)
    r = calculeaza({"tip_schema": "tablou", "L_alimentare_m": 30,
                    "plecari": [{"nume": "Compresor", "P_kW": 45, "receptor": "motor", "L_m": 120, "randament": 1.0, "cosfi": 0.85}]})
    assert 11.5 < r["rezultat"]["plecari"][0]["dU_pornire_pct"] < 12.3


# ============================================================================================================
# Runda 3 (/home/claude/verif2/RAPORT_VERIFICARE_R3.md §3)
# ============================================================================================================
def test_R3_NC1_metoda_explicita_in_pamant_pastrata():
    # D1 cerut: monopolare Cu XLPE în treflă în tub, Iz(D1, 300) = 365 A pe sistem, grupare B.52.19 6 circuite 0,60:
    # 6·365·0,60 = 1314 A ≥ 1250 A → metoda rămâne D1 (nu F în aer)
    r = calculeaza({"tip_schema": "pt", "Sn_kVA": 1600,
                    "plecari": [{"nume": "TD-1", "In_A": 1250, "L_m": 80, "cablu": {"metoda": "D1"}}]})
    p = r["rezultat"]["plecari"][0]
    assert p["metoda"] == "D1" and p["monopolar"] is True and p["n_paralel"] == 6 and p["S_faza_mm2"] == 300.0
    assert p["Iz_corectat_A"] == pytest.approx(6 * 365 * 0.60)
    assert not any("pat de cabluri în aer" in x for x in r["ipoteze"])
    # D1 cerut și nici 6 sisteme nu ajung → V01 BLOCANT (fără trecere tacită în aer)
    r = calculeaza({"tip_schema": "pt", "Sn_kVA": 2500,
                    "plecari": [{"nume": "TD-1", "In_A": 1600, "prot_tip": "MCCB", "L_m": 80, "cablu": {"metoda": "D1"}}]})
    assert ("V01", "P1·TD-1") in blocante(r)


def test_R3_NC1_metoda_implicita_ipoteza_pe_plansa():
    r = calculeaza({"tip_schema": "pt", "Sn_kVA": 1600, "plecari": [{"nume": "TD-1", "In_A": 1250, "L_m": 80}]})
    p = r["rezultat"]["plecari"][0]
    assert p["metoda"] == "F_trefla"
    assert any(x.startswith("pozare pe pat de cabluri în aer, monopolare în treflă") for x in r["ipoteze"])
    assert any("pozare pe pat de cabluri în aer, monopolare în treflă" in x for x in r["presupus"])


def test_R3_metoda_F_fara_varianta_respinsa():
    r = calculeaza({"tip_schema": "tablou", "L_alimentare_m": 30,
                    "plecari": [{"nume": "A", "In_A": 32, "cablu": {"metoda": "F"}}]})
    assert any(v["cod"] == "V10" and v["nivel"] == "BLOCANT" for v in r["verificari"])


def test_R3_NC2_prosumator_cef_TT():
    # prosumator: DDR 30 mA tip A pe invertor; RA 500 → 15 V ≤ 50 V; RA 2000 → 60 V > 50 V → V34
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 10, "In_Q_bransament_A": 25,
                    "schema_pamant": "TT", "RA_ohm": 500})
    assert r["rezultat"]["INV"]["DDR"]["IdN_mA"] == 30 and not r["blocheaza_export"]
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 10, "schema_pamant": "TT", "RA_ohm": 2000})
    assert ("V34", "schema") in blocante(r)
    # CEF 50 kW prin BMPT: RA 500 → RCCB-ul BMPT de 300 mA dă 150 V → V34; RA 100 → v1.3 R5 (§C.2 pct. 13, M5-4):
    # QG fără DDR propriu (protejat de RCCB BMPT 300 mA S), invertor 100 mA instantaneu (≤ 300/3, 10 V)
    r = calculeaza({"tip_schema": "cef", "kWp": 60, "invertoare": [{"n": 1, "Pn_kW": 50}], "schema_pamant": "TT",
                    "RA_ohm": 500})
    assert ("V34", "C1 (amonte)") in blocante(r)
    r = calculeaza({"tip_schema": "cef", "kWp": 60, "invertoare": [{"n": 1, "Pn_kW": 50}], "schema_pamant": "TT",
                    "RA_ohm": 100})
    z = r["rezultat"]
    assert "DDR" not in z["QG"] and z["invertoare"][0]["DDR"]["IdN_mA"] == 100
    assert not z["invertoare"][0]["DDR"]["selectiv"] and not any(v["cod"] == "V43" for v in r["verificari"])


def _schema_tt(tip, ra):
    baza = {"bransament": {"retea": "tri", "P_kW": 15, "L_coloana_m": 20},
            "tablou": {"L_alimentare_m": 30, "plecari": [{"nume": "Hala", "In_A": 63}, {"nume": "Prize", "In_A": 16}]},
            "prosumator": {"retea": "tri", "Pn_inv_kW": 10, "In_Q_bransament_A": 25},
            "cef": {"kWp": 60, "invertoare": [{"n": 1, "Pn_kW": 50}]},
            "pt": {"Sn_kVA": 400, "plecari": [{"nume": "TD-1", "In_A": 100}]},
            "ge_ats": {"Sn_GE_kVA": 100, "P_sarcina_kW": 60}}[tip]
    return dict(baza, tip_schema=tip, schema_pamant="TT", RA_ohm=ra)


def _idn_din_rezultat(x, acc):
    if isinstance(x, dict):
        for k, v in x.items():
            if k in ("DDR", "RCCB") and isinstance(v, dict) and v.get("IdN_mA") is not None:
                acc.append(v["IdN_mA"])
            elif k == "IdN_amonte_mA":
                acc.append(v)
            else:
                _idn_din_rezultat(v, acc)
    elif isinstance(x, list):
        for v in x:
            _idn_din_rezultat(v, acc)
    return acc


@pytest.mark.parametrize("tip", ["bransament", "tablou", "prosumator", "cef", "pt", "ge_ats"])
@pytest.mark.parametrize("ra", [4, 100, 500, 2000])
def test_R3_proprietate_TT(tip, ra):
    """Pentru orice schemă în TT: fie e BLOCANT V34 (sau V28 — TT neacoperit la PT / GE), fie nu e blocată și TOATE
    DDR-urile (inclusiv cel din amonte) au RA·IΔn ≤ 50 V, iar nota nu afirmă „> 50 V”."""
    r = calculeaza(_schema_tt(tip, ra))
    b = {v["cod"] for v in r["verificari"] if v["nivel"] == "BLOCANT"}
    if r["blocheaza_export"]:
        assert b & {"V34", "V28"}, b
        return
    idn = _idn_din_rezultat(r["rezultat"], [])
    assert idn, "TT fără niciun DDR în rezultat"
    assert all(ra * x / 1000.0 <= 50 + 1e-9 for x in idn), idn
    assert "> 50" not in (r["rezultat"].get("nota_schema_pamant") or "")


def test_R3_NM1_ge_retea_peste_bmpt_v50_si_pt_propriu():
    # GE 2000 kVA / 1500 kW: Ib = 1 500 000/(692,82·0,9) = 2405,6 A > 250 A → V50 (racord din PT)
    r = calculeaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 2000, "P_sarcina_kW": 1500})
    assert ("V50", "schema") in blocante(r)
    # din PT propriu 1000 kVA: Ik3 bară 25,31 kA (ca P04/M09) la originea C1; sarcina 666,7 kVA ≤ 1000 kVA
    r = calculeaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 800, "P_sarcina_kW": 600, "origine": "pt_propriu",
                    "pt_Sn_kVA": 1000})
    assert r["rezultat"]["C1"]["Ik3max_origine_kA"] == pytest.approx(25.31, rel=1e-3) and not r["blocheaza_export"]
    # PT 400 kVA < 666,7 kVA → V62 BLOCANT
    r = calculeaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 800, "P_sarcina_kW": 600, "origine": "pt_propriu",
                    "pt_Sn_kVA": 400})
    assert ("V62", "schema") in blocante(r)


def test_R3_NM2_tablou_TT_ddr_amonte():
    # RA 500 Ω, fără IdN_amonte_mA: RCCB BMPT 300 mA → 150 V > 50 V → V34 BLOCANT pe C1 (amonte)
    r = calculeaza({"tip_schema": "tablou", "schema_pamant": "TT", "RA_ohm": 500, "L_alimentare_m": 30,
                    "plecari": [{"nume": "Hala", "In_A": 63}]})
    assert ("V34", "C1 (amonte)") in blocante(r)
    assert "DDR 100/30 mA în amonte" in next(v["remediere"] for v in r["verificari"] if v["cod"] == "V34")
    # RA 100 Ω: 300 mA → 30 V; v1.3 R5 (M5-4): Q1 fără DDR propriu (protejat de RCCB BMPT 300 mA S), plecări 100 mA
    # instantaneu (≤ 300/3) — lanț selectiv în timp și IΔn: 300 S → 100 instantaneu
    r = calculeaza({"tip_schema": "tablou", "schema_pamant": "TT", "RA_ohm": 100, "L_alimentare_m": 30,
                    "plecari": [{"nume": "Hala", "In_A": 63}]})
    z = r["rezultat"]
    assert not r["blocheaza_export"] and z["IdN_amonte_mA"] == 300
    assert "DDR" not in z["Q1_C1"] and z["plecari"][0]["DDR"]["IdN_mA"] == 100
    assert not any(v["cod"] == "V43" for v in r["verificari"])
    # din PT propriu fără DDR în amonte declarat → V34 (lipsă DDR pe C1)
    r = calculeaza({"tip_schema": "tablou", "schema_pamant": "TT", "RA_ohm": 100, "origine": "pt_propriu",
                    "L_alimentare_m": 30, "plecari": [{"nume": "Hala", "In_A": 63}]})
    assert ("V34", "C1 (amonte)") in blocante(r)
