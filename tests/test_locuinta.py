"""Tipul de schemă „locuinta” (SPEC §C.8, v1.5 — valorile v1.4 actualizate la runda 4): bilanț, branșament + coloană, Q general, SPD, grupe DDR, circuite,
repartizarea pe faze, TT, valori absurde și memoriul. Valorile de referință sunt calculate de mână în comentarii."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.calc import calculeaza, norme  # noqa: E402
from engine import memoriu  # noqa: E402

CASA_MONO = {"tip_schema": "locuinta", "retea": "mono",
             "alimentare": {"tip": "bransament_existent", "In_Q_bransament_A": 32, "P_aprobata_kW": 7, "L_coloana_m": 15},
             "circuite": [{"nume": "Iluminat parter", "receptor": "iluminat"},
                          {"nume": "Iluminat etaj", "receptor": "iluminat"},
                          {"nume": "Prize living", "receptor": "prize"},
                          {"nume": "Prize dormitoare", "receptor": "prize"},
                          {"nume": "Prize bucătărie", "receptor": "prize_bucatarie"},
                          {"nume": "Baie", "receptor": "prize_baie"},
                          {"nume": "Mașină de spălat", "receptor": "masina_spalat_rufe"},
                          {"nume": "Boiler", "receptor": "boiler"}]}

CASA_TRI = {"tip_schema": "locuinta", "retea": "tri",
            "alimentare": {"tip": "bransament_nou", "P_aprobata_kW": 15, "L_coloana_m": 25},
            "circuite": [{"nume": "Iluminat", "receptor": "iluminat"},
                         {"nume": "Prize 1", "receptor": "prize"},
                         {"nume": "Prize 2", "receptor": "prize"},
                         {"nume": "Plită", "receptor": "plita", "faza": "3F"},
                         {"nume": "Pompă de căldură", "receptor": "pompa_caldura"},
                         {"nume": "Încărcare VE", "receptor": "vehicul_electric", "P_kW": 11},
                         {"nume": "Prize bucătărie", "receptor": "prize_bucatarie"},
                         {"nume": "Baie", "receptor": "prize_baie"},
                         {"nume": "Cuptor", "receptor": "cuptor"},
                         {"nume": "Exterior", "receptor": "prize_exterior"}]}

APARTAMENT = {"tip_schema": "locuinta", "retea": "mono",
              "alimentare": {"tip": "bransament_existent", "In_Q_bransament_A": 25, "P_aprobata_kW": 5, "L_coloana_m": 30},
              "circuite": [{"nume": "Iluminat", "receptor": "iluminat", "L_m": 15},
                           {"nume": "Prize camere", "receptor": "prize"},
                           {"nume": "Prize bucătărie", "receptor": "prize_bucatarie"},
                           {"nume": "Baie", "receptor": "prize_baie", "L_m": 8},
                           {"nume": "Aer condiționat", "receptor": "aer_conditionat"},
                           {"nume": "Centrală", "receptor": "centrala_termica"}]}


def _v(r, cod, nivel=None):
    return [v for v in r["verificari"] + r["info"] if v["cod"] == cod and (nivel is None or v["nivel"] == nivel)]


def _circuite(z):
    return {c["nume"]: c for g in z["grupe_DDR"] for c in g["circuite"]}


def test_casa_mono_7kw_8_circuite():
    r = calculeaza(CASA_MONO)
    z = r["rezultat"]
    assert not r["blocheaza_export"], [v for v in r["verificari"] if v["nivel"] == "BLOCANT"]
    # bilanț: Σ Pi = 2·0,5 + 2·2 + 2,5 + 2 + 2,2 + 2 = 13,7 kW; 8 receptoare generale → ks 0,4 (v1.5); Pc = 5,48 kW
    # P aprobată 7 kW → Ib general = 7000/(230·0,95) = 32,04 A (Pc informativ: 5480/218,5 = 25,08 A)
    # Ib de calcul pe L1 = 0,4·Σ Ib instalat = 0,4·64,15 = 25,66 A ≤ 32 A → fără V46
    b = z["bilant"]
    assert b["Pi_kW"] == pytest.approx(13.7) and b["ks"] == 0.4 and b["Pc_kW"] == pytest.approx(5.48)
    assert b["Ib_A"] == pytest.approx(32.037, rel=1e-3) and b["Ib_Pc_A"] == pytest.approx(25.08, rel=1e-3)
    assert b["Ib_baza"] == "P aprobată (ATR)" and not _v(r, "V46")
    assert z["faze"]["L1_calc_A"] == pytest.approx(0.4 * z["faze"]["L1_A"]) and z["faze"]["faza_max"] == "L1"
    # branșament existent BMPM-32, coloana Cu poartă min(In Q, Ib general) = 32 A, ramură completă
    assert z["alimentare"]["bloc"] == "BMPM-32" and z["coloana"]["Ib_A"] == pytest.approx(32.0)
    assert z["coloana"]["material"] == "Cu" and z["coloana"]["protectie"]["In_A"] == 32
    for k in ("Iz_corectat_A", "dU_cumulat_pct", "Ik3max_capat_kA", "Ik1min_capat_A"):
        assert k in z["coloana"]
    # Q general: întreruptor-separator 2P, In ≥ In Q branșament (32 A); SPD T2 1P+N
    assert z["Q_general"]["tip"] == "IS" and z["Q_general"]["In_A"] == 32 and z["Q_general"]["poli"] == "2P"
    assert z["SPD"]["tip"] == "T2" and z["SPD"]["poli"] == "1P+N" and z["SPD"]["Up_kV"] <= 1.5
    # v1.5 grupe: iluminat separat de prize și pe 2 DDR (2 circuite), general (4 ≤ 5 circuite), bucătărie, baie;
    # grupele cu un singur circuit → RCBO; toate 30 mA tip A, 2P
    gr = [(g["obiect"], g["grupa"], len(g["circuite"]), g["DDR"]["aparat"]) for g in z["grupe_DDR"]]
    assert gr == [("DDR1", "iluminat", 1, "RCBO"), ("DDR2", "iluminat", 1, "RCBO"), ("DDR3", "general", 4, "RCCB"),
                  ("DDR4", "bucătărie", 1, "RCBO"), ("DDR5", "baie", 1, "RCBO")]
    assert all(g["DDR"]["IdN_mA"] == 30 and g["DDR"]["tip"] == "A" and g["DDR"]["poli"] == "2P" for g in z["grupe_DDR"])
    # In DDR3 ≥ max(In MCB max 16; min(In Q 32, Σ In 64)) = 32 → RCCB 40 A; RCBO: In = In MCB
    assert z["grupe_DDR"][2]["DDR"]["In_A"] == 40 and z["grupe_DDR"][0]["DDR"]["In_A"] == 10
    c = _circuite(z)
    assert c["Iluminat parter"]["protectie"]["tip"] == "RCBO" and c["Prize living"]["protectie"]["tip"] == "MCB"
    assert c["Iluminat parter"]["protectie"]["curba"] == "B" and c["Iluminat parter"]["protectie"]["In_A"] == 10
    assert c["Iluminat parter"]["S_faza_mm2"] == 1.5 and c["Iluminat parter"]["dU_limita_pct"] == 3.0
    assert c["Prize living"]["protectie"]["In_A"] == 16 and c["Prize living"]["S_faza_mm2"] == 2.5
    assert c["Prize living"]["dU_limita_pct"] == 5.0 and c["Prize living"]["metoda"] == "B2"
    # ΔU cumulat de la punctul de delimitare (include coloana)
    assert c["Prize living"]["dU_cumulat_pct"] > c["Prize living"]["dU_ramura_pct"] > 0
    assert all(x["faza"] == "L1" for x in c.values())
    assert z["faze"]["dezechilibru_pct"] is None and z["faze"]["L1_A"] > 0
    assert z["nota_schema_pamant"].startswith("Schemă de legare la pământ: TN-C-S") and "5 grupe" in z["nota_schema_pamant"]
    assert z["retea"] == "mono"
    # RCBO BMPM instantaneu în amonte → V43 AVERTISMENT, v1.6 (P2-1): o singură atenționare agregată DDR1–DDR5
    assert [v["obiect"] for v in _v(r, "V43", "AVERTISMENT")] == ["DDR1–DDR5 vs RCBO BMPM"]
    assert "DDR1–DDR5" in _v(r, "V43", "AVERTISMENT")[0]["mesaj"]


def test_casa_tri_15kw_plita_pompa_ve():
    r = calculeaza(CASA_TRI)
    z = r["rezultat"]
    # Pi = 0,5 + 2 + 2 + 7,5 + 6 + 11 + 2,5 + 2 + 3,5 + 1,5 = 38,5 kW; continue: pompă 6 (electric, v1.5) + VE 11 = 17 kW;
    # 8 generale → ks 0,4: Pc = 0,4·21,5 + 17 = 25,6 kW > 15 kW aprobați → V46 AVERTISMENT (Pc informativ)
    b = z["bilant"]
    assert b["Pi_kW"] == pytest.approx(38.5) and b["P_continuu_kW"] == pytest.approx(17.0)
    assert b["Pc_kW"] == pytest.approx(25.6) and any(v["obiect"] == "schema" for v in _v(r, "V46", "AVERTISMENT"))
    # Ib general din Pa = 15 000/(692,82·0,95) = 22,79 A; Ib(Pc) = 25 600/658,18 = 38,90 A; branșament nou: Q ≥ max(Ib
    # general, Ib(Pc), faza cea mai încărcată) — v1.6 (m-n3): repartizarea pe curentul de CALCUL (3F; apoi monofazatele
    # descrescător, inclusiv cele din grupele 4P): continuu 3F pe fiecare fază = 6000/(692,82·0,95) + 11000/692,82
    # = 9,12 + 15,88 = 24,99 A; generale 3F plită 0,4·10,83 = 4,33 A → 29,32 A pe fază; monofazatele ·0,4: cuptor 6,09,
    # prize bucătărie 4,83, prize 1 / 2 3,86, baie 3,86, exterior 2,90, iluminat 0,97 → L1 29,32 + 6,09 + 2,90 = 38,31 A
    # (în v1.5: 40,24 A) → BMPTd-40, Q C40 (nu C50)
    assert b["Ib_A"] == pytest.approx(22.79, rel=1e-3) and b["Ib_Pc_A"] == pytest.approx(38.895, rel=1e-3)
    assert z["alimentare"]["bloc"] == "BMPTd-40" and z["alimentare"]["Q"]["In_A"] == 40
    assert z["faze"]["I_calc_max_A"] == pytest.approx(38.31, rel=1e-3) and not _v(r, "V46", "BLOCANT")
    assert z["Q_general"]["poli"] == "4P" and z["SPD"]["poli"] == "3P+N"
    c = _circuite(z)
    # plită 3F 7,5 kW: Ib = 7500/692,82 = 10,8 A → C16 3P+N; pompă 6 kW 3F: 9,1 A → C16; VE 11 kW 3F: 15,9 A → C20,
    # v1.7 (N17): 4 mm² (minimul VE; B2 3 conductoare încărcate Iz 2,5 mm² ≈ 20 A, fără rezervă pe sarcină continuă)
    assert c["Plită"]["faza"] == "3F" and c["Plită"]["protectie"]["In_A"] == 16 and c["Plită"]["retea"] == "tri"
    assert c["Pompă de căldură"]["faza"] == "3F" and c["Pompă de căldură"]["protectie"]["In_A"] == 16
    assert c["Încărcare VE"]["faza"] == "3F" and c["Încărcare VE"]["S_faza_mm2"] == 4
    # VE: grupă proprie, DDR tip B (alternativ A-EV + RDC-DD 6 mA c.c.), 4P
    ve = [g for g in z["grupe_DDR"] if g["grupa"] == "vehicul electric"]
    assert len(ve) == 1 and ve[0]["DDR"]["tip"] == "B" and "RDC-DD" in ve[0]["DDR"]["alternativa"]
    assert ve[0]["DDR"]["poli"] == "4P" and [x["nume"] for x in ve[0]["circuite"]] == ["Încărcare VE"]
    # bucătăria are plita 3F → o grupă 4P cu prizele bucătăriei și cuptorul; baia / exteriorul / iluminatul: RCBO 2P pe o fază
    gb = {g["grupa"]: g for g in z["grupe_DDR"]}
    assert gb["bucătărie"]["DDR"]["poli"] == "4P" and len(gb["bucătărie"]["circuite"]) == 3
    assert gb["baie"]["DDR"]["aparat"] == "RCBO" and gb["baie"]["DDR"]["poli"] == "2P" and gb["baie"]["faza"] in ("L1", "L2", "L3")
    # repartizarea pe faze: grupele 2P pe faza cea mai puțin încărcată, monofazatele din grupele 4P individual
    f = z["faze"]
    assert f["dezechilibru_pct"] < 10 and {x["faza"] for x in c.values() if x["retea"] == "mono"} == {"L1", "L2", "L3"}
    assert f["L1_A"] + f["L2_A"] + f["L3_A"] == pytest.approx(sum(
        x["Ib_A"] * (3 if x["faza"] == "3F" else 1) for x in c.values()), rel=1e-6)
    # cu P aprobată 35 kW: fără V46
    r2 = calculeaza(dict(CASA_TRI, alimentare=dict(CASA_TRI["alimentare"], P_aprobata_kW=35)))
    assert not _v(r2, "V46") and not r2["blocheaza_export"]


def test_apartament_mono_6_circuite():
    r = calculeaza(APARTAMENT)
    z = r["rezultat"]
    # Σ Pi = 0,5 + 2 + 2,5 + 2 + 2,5 + 0,2 = 9,7 kW; 6 generale → ks 0,4 → Pc 3,88 kW ≤ 5; Ib din Pa = 5000/218,5 = 22,88 A
    assert z["bilant"]["Pc_kW"] == pytest.approx(3.88) and z["bilant"]["Ib_A"] == pytest.approx(22.883, rel=1e-3)
    assert not r["blocheaza_export"] and not _v(r, "V46")
    assert z["alimentare"]["bloc"] == "BMPM-25" and len(_circuite(z)) == 6
    assert _circuite(z)["Baie"]["L_m"] == 8 and _circuite(z)["Iluminat"]["L_m"] == 15
    assert any(x.startswith("Aer condiționat: P = 2,5 kW") for x in r["presupus"])
    # v1.5: centrala termică (receptor fix ≤ 10 A) pe 1,5 mm² (I7-2011), cum cere SPEC
    assert _circuite(z)["Centrală"]["S_faza_mm2"] == 1.5


def test_depasire_putere():
    # 8 circuite + încălzire electrică 6 kW + saună 6 kW (continue): Pc = 0,4·13,7 + 12 = 17,48 kW
    # Ib de calcul L1 = 0,4·64,15 + 6000/230 + 6000/230 = 25,66 + 52,17 = 77,83 A > 1,13·32 A → V46 BLOCANT pe Q;
    # Pc > 7 kW → V46 AVERTISMENT
    c = CASA_MONO["circuite"] + [{"nume": "Încălzire", "receptor": "incalzire_electrica", "P_kW": 6},
                                 {"nume": "Saună", "receptor": "sauna"}]
    r = calculeaza(dict(CASA_MONO, circuite=c))
    assert r["rezultat"]["bilant"]["Pc_kW"] == pytest.approx(17.48)
    assert r["rezultat"]["faze"]["L1_calc_A"] == pytest.approx(77.83, rel=1e-3)
    b = _v(r, "V46", "BLOCANT")
    assert b and b[0]["obiect"] == "Q" and "trifazat" in b[0]["remediere"] and "ATR" in b[0]["remediere"]
    assert _v(r, "V46", "AVERTISMENT") and r["blocheaza_export"]
    # între In și 1,13·In, fără sarcini continue → doar AVERTISMENT: ks declarat 0,53 → L1 = 0,53·64,15 = 34,0 A
    # (32 < 34,0 ≤ 36,16 A); mesajul nu mai spune că Q declanșează (m7)
    r = calculeaza(dict(CASA_MONO, ks=0.53))
    assert r["rezultat"]["faze"]["L1_calc_A"] == pytest.approx(34.0, rel=1e-3)
    av = [v for v in _v(r, "V46", "AVERTISMENT") if v["obiect"] == "Q"]
    assert av and "nu declanșează convențional" in av[0]["mesaj"] and not _v(r, "V46", "BLOCANT")


def test_bransament_nou_mono_peste_40A_cere_trifazat():
    c = CASA_MONO["circuite"] + [{"nume": "VE", "receptor": "vehicul_electric"}, {"nume": "Plită", "receptor": "plita"}]
    r = calculeaza(dict(CASA_MONO, alimentare={"tip": "bransament_nou", "L_coloana_m": 15}, circuite=c))
    # Pc = 0,5·(13,7 + 7,2) + 7,4 = 17,85 kW → Ib 81,7 A > 40 A → V53 BLOCANT (nu există BMPM, branșament trifazat)
    assert ("V53", "schema") in {(v["cod"], v["obiect"]) for v in r["verificari"] if v["nivel"] == "BLOCANT"}


def test_tt():
    # TT, RA 100 Ω: RCCB BMPT 300 mA → 30 V ≤ 50 V; DDR 30 mA pe grupe → 3 V; nota 3 cu valorile reale (6 grupe v1.5)
    # v1.7 (M-c3): casa are VE — în TT, sub RCCB-ul BMPT tip AC implicit, V43 „ve_dc” BLOCANT; cu DDR-ul din
    # branșament declarat tip B nu mai blochează
    r0 = calculeaza(dict(CASA_TRI, schema_pamant="TT", RA_ohm=100,
                         alimentare=dict(CASA_TRI["alimentare"], P_aprobata_kW=35)))
    assert [v["cod"] for v in r0["verificari"] if v["nivel"] == "BLOCANT"] == ["V43"]
    r = calculeaza(dict(CASA_TRI, schema_pamant="TT", RA_ohm=100,
                        alimentare=dict(CASA_TRI["alimentare"], P_aprobata_kW=35, DDR_bransament_tip="B")))
    z = r["rezultat"]
    assert not r["blocheaza_export"] and z["schema_pamant"] == "TT"
    n = z["nota_schema_pamant"].replace(" ", " ")
    assert "TT" in n and "DDR 30 mA pe 6 grupe" in n and "RA = 100 Ω" in n and "≤ 50 V" in n
    assert all(g["DDR"]["IdN_mA"] == 30 for g in z["grupe_DDR"])
    assert all(c["t_deconectare_s"] == 0.2 for c in _circuite(z).values())    # TT, circuite finale ≤ 63 A
    assert not any(v["cod"] == "V30" and v["nivel"] == "BLOCANT" for v in r["verificari"])
    # v1.5 (P0-3): în TT protecția la defect a circuitelor e DDR-ul, nu „Ik1min ≥ Ia”
    assert all("TT" in c["protectie_defect"] and "DDR 30 mA" in c["protectie_defect"] for c in _circuite(z).values())
    assert not any(v["cod"] == "V30" and "deconectare automată îndeplinită" in v["mesaj"] for v in r["info"])
    # RA 500 Ω: RCCB-ul BMPT de 300 mA → 150 V > 50 V → V34 BLOCANT
    r = calculeaza(dict(CASA_TRI, schema_pamant="TT", RA_ohm=500))
    assert any(v["cod"] == "V34" and v["nivel"] == "BLOCANT" for v in r["verificari"])


def test_faza_impusa_si_dezechilibru():
    c = [{"nume": f"P{i}", "receptor": "prize", "faza": "L1"} for i in range(4)] + [{"nume": "Il", "receptor": "iluminat"}]
    r = calculeaza({"tip_schema": "locuinta", "retea": "tri", "alimentare": {"tip": "bransament_nou"}, "circuite": c})
    z = r["rezultat"]
    assert all(_circuite(z)[f"P{i}"]["faza"] == "L1" for i in range(4)) and _circuite(z)["Il"]["faza"] in ("L2", "L3")
    # grupa celor 4 prize impuse pe L1 → RCCB 2P (nu 4P), etichetată L1
    g = [g for g in z["grupe_DDR"] if g["grupa"] == "general"][0]
    assert g["faza"] == "L1" and g["DDR"]["poli"] == "2P" and g["DDR"]["aparat"] == "RCCB"
    # L1 = 4·2000/(230·0,9) = 38,6 A; L2 = 500/207 = 2,4 A; L3 = 0 → Imed 13,7 → dezechilibru 182 % > 30 % → V47
    assert z["faze"]["dezechilibru_pct"] == pytest.approx(181.9, rel=1e-2)
    assert _v(r, "V47", "AVERTISMENT")


def test_ddr_impus_si_refuzat():
    c = [dict(x) for x in CASA_MONO["circuite"]]
    c[0]["DDR"] = False          # iluminat fără DDR → V49 BLOCANT (SR HD 60364-4-41 art. 411.3.4)
    c[2]["DDR"] = False          # prize fără DDR → V29 BLOCANT
    c[7]["DDR"] = {"IdN_mA": 30, "selectiv": False}    # boiler pe DDR propriu
    r = calculeaza(dict(CASA_MONO, circuite=c))
    b = {(v["cod"], v["obiect"]) for v in r["verificari"] if v["nivel"] == "BLOCANT"}
    assert ("V49", "C1·Iluminat parter") in b and ("V29", "C3·Prize living") in b
    gr = {g["grupa"]: g for g in r["rezultat"]["grupe_DDR"]}
    assert gr["fără DDR"]["DDR"] is None and gr["propriu"]["circuite"][0]["nume"] == "Boiler"


def test_cablu_si_lungime_impuse():
    c = [{"nume": "Prize garaj", "receptor": "prize", "L_m": 60, "cablu": {"metoda": "C", "material": "Cu"}}]
    r = calculeaza({"tip_schema": "locuinta", "retea": "mono", "alimentare": {"tip": "bransament_nou"}, "circuite": c})
    x = _circuite(r["rezultat"])["Prize garaj"]
    assert x["metoda"] == "C" and x["L_m"] == 60 and x["S_faza_mm2"] >= 2.5


@pytest.mark.parametrize("modif,cod", [
    ({"circuite": []}, "V07"),
    ({"circuite": [{"nume": "X", "receptor": "teleport"}]}, "V12"),
    ({"circuite": [{"nume": "X", "receptor": "prize", "P_kW": 0}]}, "V07"),
    ({"circuite": [{"nume": "X", "receptor": "prize", "P_kW": -2}]}, "V07"),
    ({"circuite": [{"nume": "X", "receptor": "prize", "P_kW": 80}]}, "V07"),
    ({"circuite": [{"nume": "X", "receptor": "prize", "L_m": 0}]}, "V09"),
    ({"circuite": [{"nume": "X", "receptor": "prize", "faza": "L2"}]}, "V12"),       # L2 la monofazat
    ({"circuite": [{"nume": "X", "receptor": "prize", "faza": "L4"}]}, "V12"),
    ({"circuite": [{"nume": "X", "receptor": "prize", "DDR": {"IdN_mA": 40}}]}, "V12"),
    ({"circuite": [{"nume": "X", "receptor": "prize", "DDR": {"IdN_mA": 300}}]}, "V29"),
    ({"circuite": [{"nume": "X", "receptor": "prize", "cablu": {"metoda": "Z"}}]}, "V10"),
    ({"alimentare": {"tip": "aerian"}}, "V12"),
    ({"alimentare": {"tip": "bransament_existent", "In_Q_bransament_A": 30}}, "V05"),
    ({"alimentare": {"tip": "bransament_existent", "P_aprobata_kW": -7}}, "V07"),
    ({"alimentare": {"L_coloana_m": 0}}, "V09"),
    ({"alimentare": "BMPM"}, "V07"),
    ({"ks": 1.5}, "V10"),
    ({"RA_ohm": 0, "schema_pamant": "TT"}, "V07"),
    ({"schema_pamant": "IT"}, "V28"),
    ({"retea": "bi"}, "V12"),
    ({"Q_general_tip": "ACB"}, "V12"),
])
def test_valori_absurde(modif, cod):
    r = calculeaza(dict(CASA_MONO, **modif))
    assert r["blocheaza_export"] and cod in {v["cod"] for v in r["verificari"] if v["nivel"] == "BLOCANT"}, \
        [(v["cod"], v["nivel"], v["obiect"]) for v in r["verificari"]]


def test_q_general_mcb_selectiv():
    # Q general MCB: cel mai mare calibru ≤ In Q branșament și ≥ min(Ib, In Q) → C32 sub RCBO C32 (egal) → V41 AVERTISMENT
    r = calculeaza(dict(CASA_MONO, Q_general_tip="MCB"))
    q = r["rezultat"]["Q_general"]
    assert q["tip"] == "MCB" and q["In_A"] == 32 and q["curba"] == "C"
    assert any(v["obiect"] == "Q general vs Q branșament" for v in _v(r, "V41"))


def test_valori_implicite_declarate_si_receptori():
    r = calculeaza(CASA_MONO)
    t = " | ".join(r["presupus"])
    for s in ("Iluminat: P = 0,5 kW", "Prize: lungime circuit 20 m", "ks după 8 receptoare generale"):
        assert s in t, s
    # tabelul receptorilor: toți au valori complete, secțiunile minime cerute
    assert set(norme.LOCUINTA_RECEPTORI) >= {"iluminat", "prize", "prize_bucatarie", "prize_baie", "prize_exterior",
                                             "masina_spalat_rufe", "masina_spalat_vase", "uscator", "boiler", "cuptor",
                                             "plita", "aer_conditionat", "pompa_caldura", "centrala_termica",
                                             "incalzire_electrica", "vehicul_electric", "pompa_apa", "poarta_automata",
                                             "sauna", "alt_circuit"}
    assert norme.LOCUINTA_RECEPTORI["plita"][6] == 6.0 and norme.LOCUINTA_RECEPTORI["vehicul_electric"][6] == 4.0  # v1.7 (N17)
    assert norme.LOCUINTA_RECEPTORI["iluminat"][6] == 1.5


@pytest.mark.parametrize("rec", sorted(norme.LOCUINTA_RECEPTORI))
def test_fiecare_receptor_mono_si_tri(rec):
    for retea in ("mono", "tri"):
        r = calculeaza({"tip_schema": "locuinta", "retea": retea, "alimentare": {"tip": "bransament_nou"},
                        "circuite": [{"nume": rec, "receptor": rec}]})
        assert not [v for v in r["verificari"] if v["nivel"] == "BLOCANT"], (rec, retea, r["verificari"])
        c = _circuite(r["rezultat"])[rec]
        # circuit singur → RCBO (VE: RCCB tip B + MCB)
        assert c["protectie"]["tip"] == ("MCB" if rec == "vehicul_electric" else "RCBO")
        assert c["Iz_corectat_A"] >= c["protectie"]["In_A"]


def test_memoriu_capitol_bilant_faze():
    r = calculeaza(CASA_TRI)
    h = memoriu.genereaza_html({"calc": CASA_TRI}, r)
    assert "4. Bilanț și repartizarea pe faze" in h and "Dezechilibru" in h and "5. Verificări" in h
    assert "Încărcare VE" in h and "P_aprobata_kW" not in h[h.index("1. Date"):h.index("2. Ipoteze")]
