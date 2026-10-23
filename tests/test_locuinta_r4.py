"""Runda 4 de testare (teste/r4/proiectant.md, teste/r4/verificator.md) — reproducerile exacte și regulile v1.5 din
SPEC §C.8: V46 pe faza cea mai încărcată, P aprobată, Q presupus, TT (protecția la defect = DDR), DDR ≤ 30 mA, V40,
grupele DDR (5 circuite, iluminat separat, 2P pe fază, RCBO), valori implicite, saună, coloana, minore, rețeaua.
Valorile de referință sunt calculate de mână în comentarii."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.calc import calculeaza, norme  # noqa: E402
from engine import memoriu  # noqa: E402

L = lambda n, r, **k: dict(nume=n, receptor=r, **k)  # noqa: E731


def _v(r, cod, nivel=None):
    return [v for v in r["verificari"] + r["info"] if v["cod"] == cod and (nivel is None or v["nivel"] == nivel)]


def _b(r):
    return {(v["cod"], v["obiect"]) for v in r["verificari"] if v["nivel"] == "BLOCANT"}


def _circuite(z):
    return {c["nume"]: c for g in z["grupe_DDR"] for c in g["circuite"]}


def _loc(retea="mono", circuite=(), **al):
    return {"tip_schema": "locuinta", "retea": retea, "alimentare": al, "circuite": list(circuite)}


# ---------------------------------------------------------------------------------------------------- C1 / V46 pe fază
K11 = {"tip_schema": "locuinta", "retea": "tri", "Ik3_OD_kA": 6, "Zb_OD_ohm": 0.45,
       "alimentare": {"tip": "bransament_existent", "In_Q_bransament_A": 25, "P_aprobata_kW": 14, "L_coloana_m": 50},
       "circuite": [{"nume": "Il", "receptor": "iluminat", "L_m": 40}, {"nume": "Pr", "receptor": "prize", "L_m": 45},
                    {"nume": "Plită", "receptor": "plita"}, {"nume": "VE mono", "receptor": "vehicul_electric", "faza": "L2"}]}


def test_C1_ve_mono_pe_L2_blocheaza_q_25():
    # L2: VE 7400/230 = 32,17 A (continuu, ks 1) + plită 3F 7500/692,82 = 10,83 A·0,8 = 40,83 A > 1,13·25 = 28,25 A
    r = calculeaza(K11)
    f = r["rezultat"]["faze"]
    assert f["faza_max"] == "L2" and f["L2_calc_A"] == pytest.approx(40.83, rel=1e-3)
    assert f["L2_continuu_A"] == pytest.approx(32.17, rel=1e-3) and f["L2_A"] == pytest.approx(43.0, rel=1e-3)
    b = [v for v in _v(r, "V46", "BLOCANT") if v["obiect"] == "Q"]
    assert b and "L2" in b[0]["mesaj"] and r["blocheaza_export"]
    # M2: VE C40 sub Q 3 × C25 → V40 BLOCANT
    assert ("V40", "C4·VE mono") in _b(r)


def test_C1_trei_incalziri_pe_L1_q16():
    r = calculeaza(_loc("tri", [L(f"Inc{i}", "incalzire_electrica", faza="L1") for i in (1, 2, 3)],
                        tip="bransament_existent", In_Q_bransament_A=16, P_aprobata_kW=10))
    # I_L1 = 3·3000/230 = 39,13 A (continue) > 1,13·16 = 18,08 A → BLOCANT; grupa pe L1 → RCCB 2P
    assert r["rezultat"]["faze"]["L1_calc_A"] == pytest.approx(39.13, rel=1e-3)
    assert ("V46", "Q") in _b(r)
    g = r["rezultat"]["grupe_DDR"][0]
    assert g["faza"] == "L1" and g["DDR"]["poli"] == "2P" and g["DDR"]["In_A"] == 25


def test_C1_sarcina_continua_peste_in_blocheaza_sub_113():
    # 7b proiectant: mono Q 40 + saună 6 kW: L1 = 0,8·(2,42 + 2·9,66) + 26,09 = 43,48 A ∈ (40; 45,2] — continuu → BLOCANT
    r = calculeaza(_loc("mono", [L("Il", "iluminat"), L("Pr", "prize"), L("Saună", "sauna"), L("Pr2", "prize")],
                        In_Q_bransament_A=40, P_aprobata_kW=9))
    assert r["rezultat"]["faze"]["L1_calc_A"] == pytest.approx(43.48, rel=1e-3)
    b = [v for v in _v(r, "V46", "BLOCANT") if v["obiect"] == "Q"]
    assert b and "sarcini continue" in b[0]["mesaj"]


# ---------------------------------------------------------------------------------------------------- P0-1 / P0-2
APT_UI = {"tip_schema": "locuinta", "retea": "mono", "schema_pamant": "TN-C-S",
          "alimentare": {"In_Q_bransament_A": 32, "P_aprobata_kW": 7, "L_coloana_m": 25},
          "circuite": [L("Iluminat", "iluminat"), L("Prize camere", "prize"), L("Prize bucătărie", "prize_bucatarie"),
                       L("Prize baie", "prize_baie"), L("Mașină de spălat rufe", "masina_spalat_rufe"),
                       L("Aer condiționat", "aer_conditionat"), L("Cuptor", "cuptor"), L("Boiler", "boiler"),
                       L("Prize living", "prize")]}


def test_P0_1_apartamentul_standard_nu_e_blocat():
    # Σ Pi 19,2 kW, 9 receptoare → ks 0,4 → Pc 7,68 kW (informativ, V46 AV > 7 kW); Ib general = 7000/218,5 = 32,04 A
    r = calculeaza(APT_UI)
    z = r["rezultat"]
    assert not r["blocheaza_export"], _b(r)
    assert z["bilant"]["ks"] == 0.4 and z["bilant"]["Pc_kW"] == pytest.approx(7.68)
    assert z["bilant"]["Ib_A"] == pytest.approx(32.037, rel=1e-3) and z["Q_general"]["In_A"] == 32
    assert {v["obiect"] for v in _v(r, "V46")} <= {"schema", "Q"} and not _v(r, "V46", "BLOCANT")


def test_P0_2_q_nedeclarat_presupus_si_aceeasi_regula():
    c = [L("Il", "iluminat"), L("Pr", "prize"), L("Plită", "plita"), L("PC", "pompa_caldura"),
         L("VE", "vehicul_electric", P_kW=11)]
    fara = calculeaza(_loc("tri", c, P_aprobata_kW=15, L_coloana_m=25))
    cu = calculeaza(_loc("tri", c, P_aprobata_kW=15, L_coloana_m=25, In_Q_bransament_A=25))
    # Q presupus = calibrul standard ≥ Ib din Pa (22,79 A) = 25 A, declarat; aceeași verificare V46 ca la Q declarat
    assert fara["rezultat"]["alimentare"]["Q"]["In_A"] == 25 and fara["rezultat"]["alimentare"]["Q_presupus"]
    assert any("Q presupus 25 A" in p for p in fara["presupus"])
    assert ("V46", "Q") in _b(fara) and ("V46", "Q") in _b(cu)
    # Q general nu depășește Q-ul dedus (IS 4P ≥ In Q, cea mai mică treaptă 32 A)
    assert fara["rezultat"]["Q_general"]["In_A"] == 32


def test_P0_2_fara_pa_si_fara_q_peste_limita_blocului():
    # mono fără Pa și fără Q: Ib(Pc) = (0,8·Σ general + VE + saună) > 40 A → nu există BMPM → V46 BLOCANT (bloc)
    r = calculeaza(_loc("mono", [L("Pr", "prize"), L("VE", "vehicul_electric"), L("Saună", "sauna")]))
    b = [v for v in _v(r, "V46", "BLOCANT") if v["obiect"] == "Q"]
    assert b and "BMPM" in b[0]["mesaj"] and "trifazat" in b[0]["remediere"]
    # fără Pa, sarcină mică: Q presupus ≥ max(Ib(Pc), faza cea mai încărcată)
    r = calculeaza(_loc("mono", [L("Il", "iluminat"), L("Pr", "prize")]))
    assert r["rezultat"]["alimentare"]["Q"]["In_A"] == 16 and not r["blocheaza_export"]


def test_P0_1_pa_incoerent_cu_q():
    # Pa 10 kW mono → 45,8 A > 1,13·25 = 28,25 A → ATR incoerent, V46 BLOCANT „pa”
    r = calculeaza(_loc("mono", [L("Il", "iluminat")], In_Q_bransament_A=25, P_aprobata_kW=10))
    assert any("incoerente" in v["mesaj"] for v in _v(r, "V46", "BLOCANT"))


# ---------------------------------------------------------------------------------------------------- P0-3 TT
def test_P0_3_tt_protectia_la_defect_prin_ddr():
    inp = dict(APT_UI, schema_pamant="TT", RA_ohm=30)
    r = calculeaza(inp)
    z = r["rezultat"]
    # nicio „demonstrație” de deconectare prin MCB cu bucla TN, nici la circuite, nici la coloană
    assert not [v for v in _v(r, "V30") if "deconectare automată îndeplinită" in v["mesaj"]]
    tt = [v for v in _v(r, "V30") if v["mesaj"].startswith("TT")]
    assert {v["obiect"] for v in tt} >= {"C2"} | {c["obiect"] for c in _circuite(z).values()}
    assert all("RA·IΔn = 0,9 V" in v["mesaj"] for v in tt if v["obiect"] != "C2")       # 30 Ω · 0,03 A
    assert all(c["protectie_defect"].startswith("DDR 30 mA") for c in _circuite(z).values())
    h = memoriu.genereaza_html({"calc": inp}, r)
    assert "Schema TT: protecția la defect" in h and "Protecția la defect (contact indirect)" in h
    assert "CT2" in z["SPD"]["configuratie"]


# ---------------------------------------------------------------------------------------------------- M1 / M2 / M4
@pytest.mark.parametrize("rec", ["iluminat", "masina_spalat_rufe", "uscator", "boiler", "centrala_termica"])
def test_M1_ddr_impus_peste_30mA_blocant(rec):
    r = calculeaza(_loc("mono", [{"nume": "X", "receptor": rec, "DDR": {"IdN_mA": 300}}], In_Q_bransament_A=32,
                        P_aprobata_kW=7))
    assert ("V49", "DDR1") in _b(r)


def test_M1_toate_circuitele_au_ddr_obligatoriu():
    assert all(v[12] == "obligatoriu" for v in norme.LOCUINTA_RECEPTORI.values())
    r = calculeaza(_loc("mono", [{"nume": "Boiler", "receptor": "boiler", "DDR": False}], In_Q_bransament_A=32))
    assert ("V49", "C1·Boiler") in _b(r)


def test_M2_mcb_peste_q_bransament():
    r = calculeaza(_loc("mono", [L("Plită", "plita")], In_Q_bransament_A=25, P_aprobata_kW=6))
    assert ("V40", "C1·Plită") in _b(r)
    # Q general MCB nu poate depăși Q branșament: e ales ≤ In Q; IS ≥ In Q nu e V40 (e protejat de Q)
    r = calculeaza(_loc("mono", [L("Il", "iluminat")], In_Q_bransament_A=25))
    assert not _v(r, "V40")


@pytest.mark.parametrize("x", [[1, 2], "casa", 7, None])
def test_M4_intrare_non_obiect(x):
    r = calculeaza(x)
    assert r["blocheaza_export"] and ("V07", "schema") in _b(r)


# ---------------------------------------------------------------------------------------------------- grupele DDR (P1)
def test_grupe_max_5_iluminat_separat_rcbo():
    c = [L(f"Il{i}", "iluminat") for i in range(3)] + [L(f"Pr{i}", "prize") for i in range(7)]
    r = calculeaza(_loc("mono", c))
    gr = r["rezultat"]["grupe_DDR"]
    assert all(len(g["circuite"]) <= 5 for g in gr)
    il = [g for g in gr if g["grupa"] == "iluminat"]
    assert len(il) == 2 and all(c["receptor"] == "iluminat" for g in il for c in g["circuite"])
    assert not any(c["receptor"] == "iluminat" for g in gr if g["grupa"] != "iluminat" for c in g["circuite"])
    single = [g for g in gr if len(g["circuite"]) == 1]
    assert all(g["DDR"]["aparat"] == "RCBO" and g["circuite"][0]["protectie"]["tip"] == "RCBO" for g in single)
    multi = [g for g in gr if len(g["circuite"]) > 1]
    assert all(g["DDR"]["aparat"] == "RCCB" and g["DDR"]["In_A"] >= 25 for g in multi)


def test_grupe_tri_2p_pe_faza_4p_doar_cu_3f():
    c = [L("Il1", "iluminat"), L("Il2", "iluminat")] + [L(f"Pr{i}", "prize") for i in range(6)] + \
        [L("Plită", "plita"), L("PB", "prize_bucatarie"), L("Baie", "prize_baie")]
    r = calculeaza(_loc("tri", c, tip="bransament_nou"))
    for g in r["rezultat"]["grupe_DDR"]:
        fz = {x["faza"] for x in g["circuite"]}
        if "3F" in fz:
            assert g["DDR"]["poli"] == "4P" and g["faza"] == "3F"
        else:
            assert len(fz) == 1 and g["DDR"]["poli"] == "2P" and g["faza"] == fz.pop()
    rc = [g for g in r["rezultat"]["grupe_DDR"] if g["DDR"]["aparat"] == "RCBO"]
    assert rc and all(g["circuite"][0]["protectie"]["poli"] == "1P+N" for g in rc)


def test_sauna_grupa_proprie_cablu_termorezistent():
    r = calculeaza(_loc("tri", [L("Il", "iluminat"), L("Pr", "prize"), L("Saună", "sauna")], tip="bransament_nou"))
    g = [g for g in r["rezultat"]["grupe_DDR"] if g["grupa"] == "saună"]
    assert len(g) == 1 and [c["nume"] for c in g[0]["circuite"]] == ["Saună"]
    assert "SiHF" in g[0]["circuite"][0]["cablu_nota"] and "7-703" in g[0]["circuite"][0]["cablu_nota"]


# ---------------------------------------------------------------------------------------------------- valori implicite
def test_valori_implicite_r4():
    R = norme.LOCUINTA_RECEPTORI
    assert R["pompa_caldura"][:2] == (3.5, 6.0) and R["cuptor"][4] == 16
    assert norme.LOCUINTA_KS_GENERAL == [(3, 0.8), (5, 0.6), (9, 0.4), (15, 0.35), (10 ** 6, 0.3)]
    assert norme.LOCUINTA_CIRCUITE_PE_DDR == 5
    r = calculeaza(_loc("mono", [L("Centrală", "centrala_termica"), L("Poartă", "poarta_automata"), L("Cuptor", "cuptor"),
                                 L("PC", "pompa_caldura")], tip="bransament_nou"))
    c = _circuite(r["rezultat"])
    assert c["Centrală"]["S_faza_mm2"] == 1.5 and c["Poartă"]["S_faza_mm2"] == 1.5
    assert c["Cuptor"]["protectie"]["In_A"] == 16
    # PC mono 3,5 kW electric: Ib = 3500/(230·0,95) = 16,0 A → C20, 2,5 mm²
    assert c["PC"]["P_kW"] == 3.5 and c["PC"]["protectie"]["In_A"] == 20 and c["PC"]["S_faza_mm2"] == 2.5


@pytest.mark.parametrize("n,ks", [(3, 0.8), (5, 0.6), (9, 0.4), (15, 0.35), (16, 0.3)])
def test_ks_dupa_numarul_receptoarelor(n, ks):
    r = calculeaza(_loc("tri", [L(f"P{i}", "prize") for i in range(n)], tip="bransament_nou"))
    assert r["rezultat"]["bilant"]["ks"] == ks


def test_ks_fara_iec_61439():
    r = calculeaza(dict(APT_UI))
    txt = " ".join(r["ipoteze"] + r["presupus"] + [v["mesaj"] for v in r["verificari"] + r["info"]])
    assert "61439" not in txt and "DECIZIE proiectant" in txt
    r = calculeaza(dict(APT_UI, ks=1.5))
    assert "61439" not in " ".join(v["mesaj"] for v in r["verificari"]) and ("V10", "schema") in _b(r)


# ---------------------------------------------------------------------------------------------------- coloana (P1-9)
def test_coloana_pozare_in_cladire():
    r = calculeaza(dict(APT_UI, alimentare=dict(APT_UI["alimentare"], pozare_coloana="în clădire")))
    col = r["rezultat"]["coloana"]
    assert col["metoda"] == "B2" and col["cablu"].startswith("CYY-F")
    r = calculeaza(dict(APT_UI, alimentare=dict(APT_UI["alimentare"], cablu={"metoda": "c"})))
    assert r["rezultat"]["coloana"]["metoda"] == "C"
    r = calculeaza(APT_UI)
    assert r["rezultat"]["coloana"]["metoda"] == "D1" and any("pozarea coloanei „în clădire”" in p for p in r["presupus"])
    r = calculeaza(dict(APT_UI, alimentare=dict(APT_UI["alimentare"], pozare_coloana="aerian")))
    assert ("V12", "C2") in _b(r)


# ---------------------------------------------------------------------------------------------------- minore (verificator)
def test_ve_ddr_false_nu_e_dublat_si_ddr_impus_semnalat():
    r = calculeaza(_loc("mono", [{"nume": "VE", "receptor": "vehicul_electric", "DDR": False}], In_Q_bransament_A=40,
                        P_aprobata_kW=9))
    assert [c["nume"] for g in r["rezultat"]["grupe_DDR"] for c in g["circuite"]] == ["VE"]
    assert ("V49", "C1·VE") in _b(r)
    r = calculeaza(_loc("mono", [{"nume": "VE", "receptor": "vehicul_electric", "DDR": {"IdN_mA": 30, "tip": "A"}}],
                        In_Q_bransament_A=40, P_aprobata_kW=9))
    g = r["rezultat"]["grupe_DDR"][0]
    assert g["DDR"]["tip"] == "A" and g["DDR"]["aparat"] == "RCCB" and _v(r, "V49", "AVERTISMENT")


def test_ddr_imposibil_si_tip_ac():
    r = calculeaza(_loc("mono", [{"nume": "X", "receptor": "prize", "DDR": {"IdN_mA": 30, "selectiv": True}}]))
    assert ("V12", "C1·X") in _b(r)
    r = calculeaza(_loc("mono", [{"nume": "B", "receptor": "prize_baie", "DDR": {"IdN_mA": 30, "tip": "AC"}}]))
    assert _v(r, "V49", "AVERTISMENT") and not r["blocheaza_export"]


def test_normalizari_nume_chei_sectiune():
    r = calculeaza(_loc("Trifazat", [{"nume": 7, "receptor": "prize", "cablu": {"material": "cu", "metoda": "b2"},
                                      "putere": 5}], In_Q_bransament_A=25, P_aprobata_kW=10))
    z = r["rezultat"]
    assert z["retea"] == "tri" and z["Q_general"]["poli"] == "4P" and not r["blocheaza_export"]
    c = z["grupe_DDR"][0]["circuite"][0]
    assert c["nume"] == "7" and c["material"] == "Cu" and c["metoda"] == "B2"
    assert any("putere" in v["mesaj"] for v in _v(r, "V12", "AVERTISMENT"))
    r = calculeaza(_loc("mono", [{"nume": "P", "receptor": "prize", "cablu": {"S_fortat": 1.5}}]))
    assert ("V13", "C1·P") in _b(r)
    # iluminat declarat 3F: P implicit = 3 × 0,5 kW (valorile monofazate pe fază, cum spune mesajul)
    r = calculeaza(_loc("tri", [{"nume": "Il", "receptor": "iluminat", "faza": "3F"}], tip="bransament_nou"))
    assert _circuite(r["rezultat"])["Il"]["P_kW"] == 1.5


def test_capacitate_conditionata_ddr_si_is():
    inp = {"tip_schema": "locuinta", "retea": "tri", "Ik3_OD_kA": 25,
           "alimentare": {"In_Q_bransament_A": 63, "P_aprobata_kW": 30, "L_coloana_m": 3, "cablu": {"S_fortat": 25}},
           "circuite": [L(f"P{i}", "prize") for i in range(3)]}
    r = calculeaza(inp)
    z = r["rezultat"]
    g = [g for g in z["grupe_DDR"] if g["DDR"]["aparat"] == "RCCB"][0]
    assert g["DDR"]["Inc_kA"] == 10 and z["Q_general"]["Icc_kA"] == 10
    av = {v["obiect"] for v in _v(r, "V33", "AVERTISMENT")}
    assert "Q general" in av and g["obiect"] in av


# ---------------------------------------------------------------------------------------------------- rețeaua
@pytest.mark.parametrize("val,exp", [("trifazat", "tri"), ("Tri", "tri"), ("TRI", "tri"), ("monofazat", "mono"),
                                     ("Mono", "mono"), ("trifazată", "tri")])
def test_retea_normalizata_in_rezultat(val, exp):
    r = calculeaza(_loc(val, [L("Pr", "prize")], tip="bransament_nou"))
    assert r["rezultat"]["retea"] == exp


@pytest.mark.parametrize("tip,extra", [("locuinta", {"circuite": [L("Pr", "prize")]}),
                                       ("bransament", {"P_kW": 15, "L_coloana_m": 20}),
                                       ("prosumator", {"Pn_inv_kW": 5, "In_Q_bransament_A": 32})])
@pytest.mark.parametrize("retea", ["lipsă", None])
def test_retea_obligatorie(tip, extra, retea):
    inp = dict(extra, tip_schema=tip)
    if retea != "lipsă":
        inp["retea"] = retea
    r = calculeaza(inp)
    b = [(v["cod"], v["obiect"]) for v in r["verificari"] if v["nivel"] == "BLOCANT"]
    assert b == [("V07", "retea")]
    v = [v for v in r["verificari"] if v["cod"] == "V07"][0]
    assert "BMPM" in v["remediere"] and "BMPT" in v["remediere"]
    assert not any("trifazată" in p for p in r["presupus"])
