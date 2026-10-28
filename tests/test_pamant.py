"""Priza de pământ (SPEC §C.7, v1.3): formule, coeficienți, dimensionare automată, limite, TT, materiale, V37,
valori absurde. Valorile de referință sunt calculate de mână în comentarii."""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.calc import calculeaza, norme, pamant  # noqa: E402
from engine import memoriu  # noqa: E402

EXEMPLU = {"rho_ohm_m": 100, "electrozi": {"n": 2, "L_m": 3, "d_m": 0.0635, "distanta_m": 6},
           "platbanda": {"L_m": 12, "latime_m": 0.04, "adancime_m": 0.8}, "R_limita_ohm": None, "sezon": "k_sezon"}
TABLOU = {"tip_schema": "tablou", "L_alimentare_m": 30, "plecari": [{"nume": "Hala", "In_A": 63}]}


def _v(r, cod):
    return [v for v in r["verificari"] + r["info"] if v["cod"] == cod]


def _par(**kw):
    par, er, _ = pamant.normalizeaza(dict(EXEMPLU, **kw))
    assert par is not None, er
    return par


# ---------------------------------------------------------------------------------------------------------------
# formulele de bază
# ---------------------------------------------------------------------------------------------------------------
def test_electrod_vertical():
    # ρ = 100 Ω·m, L = 3 m, d = 0,0635 m, capul la 0,8 m → t = 0,8 + 1,5 = 2,3 m
    # R_e = 100/(2π·3)·[ln(6/0,0635) + ½·ln((9,2 + 3)/(9,2 − 3))] = 5,3052·[4,5485 + ½·0,6769] = 5,3052·4,8869 = 25,926 Ω
    re, t = pamant.r_electrod(100.0, 3.0, 0.0635, 0.8)
    assert t == pytest.approx(2.3)
    assert re == pytest.approx(25.926, rel=1e-4)


def test_platbanda_orizontala():
    # R_pl = 100/(2π·12)·ln(2·144/(0,04·0,8)) = 1,32629·ln(9000) = 1,32629·9,10498 = 12,0759 Ω
    # (= 0,366·ρ/L·lg(2L²/(b·h)), 1.RE-Ip 30 / STAS 12604/5)
    assert pamant.r_platbanda(100.0, 12.0, 0.04, 0.8) == pytest.approx(12.0759, rel=1e-4)


def test_coeficienti_utilizare():
    # tabelate: n = 2, a/L = 2 → η_e 0,91, η_p 0,94; interpolare n = 4: 0,87 + (0,81 − 0,87)·1/2 = 0,84
    assert norme.priza_eta(norme.PRIZA_ETA_ELECTROZI, 2, 2.0) == 0.91
    assert norme.priza_eta(norme.PRIZA_ETA_PLATBANDA, 2, 2.0) == 0.94
    assert norme.priza_eta(norme.PRIZA_ETA_ELECTROZI, 4, 2.0) == pytest.approx(0.84)
    # a/L intermediar → rândul IMEDIAT INFERIOR (conservator): a/L 2,9 → rândul 2; a/L 7 → rândul 3
    assert norme.priza_eta(norme.PRIZA_ETA_ELECTROZI, 2, 2.9) == 0.91
    assert norme.priza_eta(norme.PRIZA_ETA_ELECTROZI, 2, 7.0) == 0.94
    assert norme.priza_eta(norme.PRIZA_ETA_ELECTROZI, 1, 1.0) == 1.0
    for n, aL in ((31, 2.0), (2, 0.5), (0, 2.0)):
        with pytest.raises(ValueError):
            norme.priza_eta(norme.PRIZA_ETA_ELECTROZI, n, aL)


def test_combinatie_psi_1():
    # ψ_e = ψ_pl = 1: Rp = R_e·R_pl/(R_e·η_p + n·R_pl·η_e) = 25,926·12,076/(25,926·0,94 + 2·12,076·0,91)
    #           = 313,08/(24,370 + 21,978) = 6,755 Ω
    c = pamant.calcul(_par(psi=1.0, psi_platbanda=1.0), 2)
    assert c["R_e"] == pytest.approx(25.926, rel=1e-4) and c["R_pl"] == pytest.approx(12.0759, rel=1e-4)
    assert (c["eta_e"], c["eta_p"]) == (0.91, 0.94)
    assert c["Rp"] == pytest.approx(6.7549, rel=1e-4)


def test_psi_distinct_electrozi_platbanda():
    # v1.3 R5 (M5-1): ψ_e = 1,6 și ψ_pl = 3,5 (zona II, implicit) → ρ_e = 160, ρ_pl = 350 Ω·m
    # R_e = 1,6·25,926 = 41,481 Ω; R_pl(12 m) = 3,5·12,0759 = 42,265 Ω
    # Rp = 41,481·42,265/(41,481·0,94 + 2·42,265·0,91) = 1753,2/(38,992 + 76,922) = 15,125 Ω
    # (cu același ψ = 1,6 și pe platbandă ar fi ieșit 10,81 Ω — subestimat)
    c = pamant.calcul(_par(), 2)
    assert c["rho_c"] == pytest.approx(160.0) and c["rho_pl"] == pytest.approx(350.0)
    assert c["R_pl"] == pytest.approx(42.265, rel=1e-4) and c["Rp"] == pytest.approx(15.125, rel=1e-4)
    # zone: I → 1,8 / 4,5; III → 1,4 / 2,5; ψ numerice directe
    assert (_par(sezon="i")["psi"], _par(sezon="i")["psi_pl"]) == (1.8, 4.5)
    assert (_par(sezon="III")["psi"], _par(sezon="III")["psi_pl"]) == (1.4, 2.5)
    assert _par(psi=1.7, psi_platbanda=3.0)["psi"] == 1.7 and _par(psi_platbanda=3.0)["psi_pl"] == 3.0
    assert _par(sezon=1.5)["psi"] == 1.5
    # Rp crește cu ψ_pl
    assert pamant.calcul(_par(psi_platbanda=4.5), 2)["Rp"] > c["Rp"] > pamant.calcul(_par(psi_platbanda=2.5), 2)["Rp"]


def test_lungime_platbanda_implicita():
    # v1.3 R5 (M5-1): L_p = (n − 1)·a + racord (5 m implicit): n = 2, a = 6 → 11 m; racord dat 2 m → 8 m
    # n = 2, L_p = 11 m: R_pl = 350/(2π·11)·ln(2·121/0,032) = 5,06397·8,93101 = 45,226 Ω
    # electrod ø60 mm (ST 42 DEER, verificare 28.10.2026): R_e = 1,6·100/(2π·3)·[ln(6/0,06) + ½·ln(12,2/6,2)] = 41,963 Ω
    # Rp = 41,963·45,226/(41,963·0,94 + 2·45,226·0,91) = 1897,8/121,757 = 15,587 Ω
    par, _, _ = pamant.normalizeaza({})
    c = pamant.calcul(par, 2)
    assert c["Lp"] == 11.0 and c["R_pl"] == pytest.approx(45.226, rel=1e-4) and c["Rp"] == pytest.approx(15.587, rel=1e-4)
    assert pamant.calcul(par, 5)["Lp"] == 29.0
    par, _, _ = pamant.normalizeaza({"platbanda": {"L_racord_m": 2}})
    assert pamant.calcul(par, 2)["Lp"] == 8.0
    r = calculeaza(dict(TABLOU, priza={}))
    assert r["rezultat"]["priza"]["L_racord_m"] == 5.0 and r["rezultat"]["priza"]["Rp_initial_ohm"] == pytest.approx(15.587, rel=1e-4)


def test_fara_platbanda():
    # 1 electrod, fără platbandă, ψ = 1 → Rp = R_e = 25,926 Ω; 2 electrozi la a/L = 2: 25,926/(2·0,91) = 14,245 Ω
    par = _par(psi=1.0, platbanda=False, electrozi={"n": 1, "L_m": 3, "d_m": 0.0635})
    assert par["psi_pl"] is None
    assert pamant.calcul(par, 1)["Rp"] == pytest.approx(25.926, rel=1e-4)
    assert pamant.calcul(par, 2)["Rp"] == pytest.approx(25.926 / 1.82, rel=1e-4)
    assert pamant.calcul(par, 2)["eta_p"] is None


# ---------------------------------------------------------------------------------------------------------------
# dimensionarea automată și limitele
# ---------------------------------------------------------------------------------------------------------------
def test_exemplu_dimensionare_automata_bransament():
    # Exemplul din temă (platbandă impusă 12 m, ψ_e 1,6, ψ_pl 3,5): n = 2 → 15,125 Ω > 4 Ω. La fiecare electrod
    # adăugat platbanda crește cu a = 6 m.
    # n = 10: L_p = 60 m → 4,059 Ω > 4
    # n = 11: L_p = 66 m, R_pl = 350/(2π·66)·ln(2·4356/0,032) = 0,84402·12,5145 = 10,5625 Ω; η_e = 0,75 − 0,04/5 = 0,742;
    #         η_p = 0,75 − 0,11/5 = 0,728 → Rp = 41,481·10,5625/(41,481·0,728 + 11·10,5625·0,742) = 438,15/116,41 = 3,764 Ω
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 15, "L_coloana_m": 20, "priza": EXEMPLU})
    p = r["rezultat"]["priza"]
    assert p["Rp_initial_ohm"] == pytest.approx(15.125, rel=1e-4) and p["n_initial"] == 2
    assert p["n_necesar"] == 11 and p["n_electrozi"] == 11 and p["L_platbanda_m"] == pytest.approx(66.0)
    assert p["Rp_ohm"] == pytest.approx(3.764, rel=1e-3) and p["ok"] and p["R_limita_ohm"] == 4.0
    assert p["eta_e"] == pytest.approx(0.742) and p["eta_p"] == pytest.approx(0.728)
    assert p["psi"] == 1.6 and p["psi_platbanda"] == 3.5 and p["rho_calcul_platbanda_ohm_m"] == pytest.approx(350.0)
    assert pamant.calcul(_par(), 10)["Rp"] == pytest.approx(4.059, rel=1e-3)
    v = _v(r, "V37")
    assert len(v) == 1 and v[0]["nivel"] == "INFO" and "necesar n = 11" in v[0]["mesaj"]
    assert not r["blocheaza_export"]
    for k in ("Rp_ohm", "R_limita_ohm", "n_electrozi", "L_electrod_m", "L_platbanda_m", "rho_ohm_m", "psi", "eta_e",
              "eta_p", "R_electrod_ohm", "R_platbanda_ohm", "materiale", "ok", "psi_platbanda", "L_racord_m"):
        assert k in p
    assert any("Priză de pământ" in s for s in r["pasi"])


def test_materiale_din_calcul():
    # n = 11, L_p = 66 m: platbandă ⌈66·1,1⌉ = 73 m; îmbinări = 11 electrozi + 1 PS + (⌈66/6⌉ − 1 = 10) = 22
    # → vopsea ⌈22·0,1⌉ = 3 kg (kg întregi); săpătură 66 m; 1 piesă de separație
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 15, "L_coloana_m": 20, "priza": EXEMPLU})
    mat = r["rezultat"]["priza"]["materiale"]
    m = {x["ref"]: (x["cantitate"], x["um"]) for x in mat}
    assert m == {"PP-E": (11, "buc"), "PP-PL": (73, "m"), "PS": (1, "buc"), "PP-SUD": (22, "buc"), "PP-VOP": (3, "kg"),
                 "PP-SAP": (66, "m")}
    # v1.3 R5: ore de manoperă orientative pe unitate; cantități întregi (fără zecimale)
    assert all(set(x) == {"ref", "denumire", "cantitate", "um", "ore_u"} and x["ore_u"] > 0 for x in mat)
    assert all(isinstance(x["cantitate"], int) for x in mat)
    assert {x["ref"]: x["ore_u"] for x in mat}["PP-E"] == norme.PRIZA_ORE_U["electrod"]


def test_limita_dupa_un_electrod_adaugat():
    # ρ = 30 Ω·m: n = 2 → 0,3·15,125 = 4,5375 Ω > 4; n = 3: L_p = 18 m, R_e = 12,444 Ω,
    # R_pl = 105/(2π·18)·ln(648/0,032) = 0,92840·9,91609 = 9,2060 Ω; η_e 0,87, η_p 0,91
    # Rp = 12,444·9,206/(12,444·0,91 + 3·9,206·0,87) = 114,56/35,352 = 3,2406 Ω ≤ 4 → n_necesar = 3
    r = calculeaza(dict(TABLOU, priza=dict(EXEMPLU, rho_ohm_m=30)))
    p = r["rezultat"]["priza"]
    assert p["Rp_initial_ohm"] == pytest.approx(4.5375, rel=1e-3)
    assert p["Rp_ohm"] == pytest.approx(3.2406, rel=1e-3) and p["n_electrozi"] == 3 and p["n_necesar"] == 3
    assert _v(r, "V37")[0]["nivel"] == "INFO" and p["materiale"][0]["cantitate"] == 3
    # ρ = 20 Ω·m: 0,2·15,125 = 3,025 Ω ≤ 4 direct cu n = 2
    r = calculeaza(dict(TABLOU, priza=dict(EXEMPLU, rho_ohm_m=20)))
    assert r["rezultat"]["priza"]["n_electrozi"] == 2 and r["rezultat"]["priza"]["Rp_ohm"] == pytest.approx(3.025, rel=1e-3)


def test_pt_1_ohm_blocant_la_30_electrozi():
    # PT 400 kVA, implicite: limita 1 Ω (priză comună MT/JT). n = 30, L_p = 29·6 + 5 = 179 m:
    # R_pl = 350/(2π·179)·ln(2·32 041/0,032) = 0,31120·14,5099 = 4,5155 Ω; η_e(30) = 0,60, η_p(30) = 0,46
    # Rp = 41,963·4,5155/(41,963·0,46 + 30·4,5155·0,60) = 189,48/100,58 = 1,884 Ω > 1 Ω → V37 BLOCANT (R_e cu ø60 mm)
    r = calculeaza({"tip_schema": "pt", "Sn_kVA": 400, "plecari": [{"nume": "TD-1", "In_A": 100}], "priza": {}})
    p = r["rezultat"]["priza"]
    assert p["R_limita_ohm"] == 1.0 and p["n_electrozi"] == 30 and p["n_necesar"] is None and not p["ok"]
    assert p["Rp_ohm"] == pytest.approx(1.884, rel=2e-3) and p["L_platbanda_m"] == 179.0
    assert ("V37", "BLOCANT", "priza de pământ") in {(v["cod"], v["nivel"], v["obiect"]) for v in r["verificari"]}
    assert r["blocheaza_export"]


def test_limite_pe_tip_de_schema():
    for intr, lim in (({"tip_schema": "bransament", "retea": "tri", "P_kW": 15}, 4.0),
                      ({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 10}, 4.0),
                      ({"tip_schema": "cef", "kWp": 60, "invertoare": [{"n": 1, "Pn_kW": 50}]}, 4.0),
                      ({"tip_schema": "cef", "kWp": 600, "invertoare": [{"n": 1, "Pn_kW": 500}], "pt_Sn_kVA": 630}, 1.0),
                      ({"tip_schema": "ge_ats", "Sn_GE_kVA": 100, "P_sarcina_kW": 60}, 4.0)):
        r = calculeaza(dict(intr, priza={"rho_ohm_m": 10}))
        assert r["rezultat"]["priza"]["R_limita_ohm"] == lim, intr
    # v1.3 R5 (M5-2): limita impusă poate doar COBORÎ limita normată — 3 Ω < 4 Ω se folosește
    r = calculeaza(dict(TABLOU, priza=dict(EXEMPLU, R_limita_ohm=3)))
    p = r["rezultat"]["priza"]
    assert p["R_limita_ohm"] == 3 and p["limita_motiv"].startswith("impusă") and p["Rp_ohm"] <= 3
    assert pamant.calcul(_par(), p["n_electrozi"] - 1)["Rp"] > 3 and not r["blocheaza_export"]


@pytest.mark.parametrize("intr,lim", [
    (TABLOU, 4.0),
    ({"tip_schema": "pt", "Sn_kVA": 400, "plecari": [{"nume": "TD-1", "In_A": 250}]}, 1.0),
    (dict(TABLOU, schema_pamant="TT", RA_ohm=10), 50000.0 / 300),
])
def test_limita_normata_nu_poate_fi_ridicata(intr, lim):
    # caz R5 M5-2: PT cu R_limita 10 Ω > 1 Ω → V12 BLOCANT; calculul continuă cu limita normată
    r = calculeaza(dict(intr, priza={"rho_ohm_m": 300, "R_limita_ohm": 10 if lim < 10 else 500}))
    b = [v for v in r["verificari"] if v["cod"] == "V12" and v["obiect"] == "priza de pământ"]
    assert b and b[0]["nivel"] == "BLOCANT" and "nu poate fi ridicată" in b[0]["mesaj"]
    assert r["rezultat"]["priza"]["R_limita_ohm"] == pytest.approx(lim) and r["blocheaza_export"]


def test_fara_cheia_priza_neschimbat():
    for intr in (TABLOU, {"tip_schema": "bransament", "retea": "tri", "P_kW": 15}, {"tip_schema": "pt", "Sn_kVA": 400,
                                                                  "plecari": [{"nume": "A", "In_A": 100}]}):
        a = calculeaza(intr)
        b = calculeaza(dict(intr, priza=None))
        assert a == b and "priza" not in a["rezultat"] and not _v(a, "V37")


# ---------------------------------------------------------------------------------------------------------------
# TT: RA = Rp calculat
# ---------------------------------------------------------------------------------------------------------------
def test_tt_ra_din_priza():
    # TT fără RA_ohm: RA = Rp (n = 2, implicite, electrod ø60 mm) = 15,587 Ω (declarat), fără V34 „RA nedeclarat”; limita prizei =
    # 50 V / 0,3 A = 166,7 Ω (RCCB BMPT 300 mA = cel mai mare IΔn din schemă) → V37 INFO
    r = calculeaza(dict(TABLOU, schema_pamant="TT", priza={}))
    p = r["rezultat"]["priza"]
    assert p["RA_din_priza"] and p["R_limita_ohm"] == pytest.approx(166.667, rel=1e-4) and p["ok"]
    assert any(x.startswith("RA = Rp calculat = 15,59") for x in r["presupus"])
    assert not any(v["cod"] == "V34" for v in r["verificari"])
    assert "RA = 15,59" in r["rezultat"]["nota_schema_pamant"]
    # RA declarat → nu se înlocuiește
    r = calculeaza(dict(TABLOU, schema_pamant="TT", RA_ohm=50, priza={}))
    assert not r["rezultat"]["priza"]["RA_din_priza"] and "RA = 50" in r["rezultat"]["nota_schema_pamant"]


def test_tt_ra_din_priza_dimensionata():
    # ρ = 3000 Ω·m, ψ 1,6, 1 electrod ø60 mm fără platbandă: R_e = 4800/(6π)·4,9437 = 1258,9 Ω > 166,7 Ω (RCCB BMPT
    # 300 mA); n = 10: η_e 0,75 → 1258,9/7,5 = 167,9 Ω > 166,7; n = 11: η_e = 0,75 − 0,04/5 = 0,742 → 1258,9/8,162 =
    # 154,2 Ω → schema se recalculează cu RA = 154,2 Ω: 0,3 A·154,2 = 46,3 V ≤ 50 V (fără V34); v1.3 R5: Q1 fără DDR propriu
    # (protejat de RCCB BMPT 300 mA S), plecarea 100 mA instantaneu (≤ 300/3; 0,1·165,9 = 16,6 V)
    r = calculeaza(dict(TABLOU, schema_pamant="TT", priza={"rho_ohm_m": 3000, "electrozi": {"n": 1},
                                                            "platbanda": False}))
    p = r["rezultat"]["priza"]
    assert p["Rp_initial_ohm"] == pytest.approx(1258.88, rel=1e-4) and p["n_necesar"] == 11
    assert p["Rp_ohm"] == pytest.approx(154.24, rel=1e-4) and p["L_platbanda_m"] == 0.0
    assert not r["blocheaza_export"] and "DDR" not in r["rezultat"]["Q1_C1"]
    assert r["rezultat"]["plecari"][0]["DDR"]["IdN_mA"] == 100
    assert any("154,24" in x for x in r["presupus"])


# ---------------------------------------------------------------------------------------------------------------
# valori absurde → BLOCANT V07 / V10 / V12; schema se calculează în continuare
# ---------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("priza,cod", [
    ({"rho_ohm_m": 0}, "V07"), ({"rho_ohm_m": -50}, "V07"), ({"rho_ohm_m": "sol"}, "V07"),
    ({"rho_ohm_m": float("nan")}, "V07"), ({"rho_ohm_m": 20000}, "V10"),
    ({"electrozi": {"n": 0}}, "V07"), ({"electrozi": {"n": 2.5}}, "V07"), ({"electrozi": {"n": -1}}, "V07"),
    ({"electrozi": {"n": 31}}, "V10"), ({"electrozi": {"L_m": 0}}, "V07"), ({"electrozi": {"d_m": -0.01}}, "V07"),
    ({"electrozi": {"L_m": 3, "d_m": 3}}, "V10"), ({"electrozi": {"L_m": 50}}, "V10"),
    ({"electrozi": {"n": 3, "distanta_m": 2}}, "V10"), ({"electrozi": {"distanta_m": 0}}, "V07"),
    ({"platbanda": {"L_m": 0}}, "V07"), ({"platbanda": {"latime_m": 0}}, "V07"), ({"platbanda": {"adancime_m": -1}}, "V07"),
    ({"platbanda": {"L_m": 0.1}}, "V10"), ({"platbanda": "da"}, "V07"),
    ({"R_limita_ohm": 0}, "V07"), ({"R_limita_ohm": -4}, "V07"), ({"psi_platbanda": 10}, "V10"),
    ({"psi_platbanda": 0.5}, "V10"), ({"platbanda": {"L_racord_m": -1}}, "V07"),
    ({"sezon": "XYZ"}, "V12"), ({"psi": 0.5}, "V10"), ({"psi": 5}, "V10"), ({"psi": "mult"}, "V07"),
    ("priza", "V07"), ({"electrozi": [2, 3]}, "V07"),
])
def test_valori_absurde(priza, cod):
    r = calculeaza(dict(TABLOU, priza=priza))
    b = [(v["cod"], v["obiect"]) for v in r["verificari"] if v["nivel"] == "BLOCANT"]
    assert (cod, "priza de pământ") in b, b
    assert r["blocheaza_export"] and "priza" not in r["rezultat"]
    assert r["rezultat"].get("Q1_C1")            # schema însăși se calculează în continuare


def test_un_electrod_fara_conditie_a_pe_L():
    # n = 1: distanța nu intervine (η = 1) → a/L < 1 nu e eroare. ρ = 10: R_e = 4,196 Ω (ø60 mm); L_p = racord 5 m,
    # R_pl = 35/(2π·5)·ln(50/0,032) = 1,11408·7,354 = 8,193 Ω → Rp = 4,196·8,193/(4,196 + 8,193) = 2,775 Ω ≤ 4
    r = calculeaza(dict(TABLOU, priza={"rho_ohm_m": 10, "electrozi": {"n": 1, "distanta_m": 1}}))
    assert r["rezultat"]["priza"]["Rp_ohm"] == pytest.approx(2.775, rel=1e-3)
    assert r["rezultat"]["priza"]["eta_e"] == 1.0 and not r["blocheaza_export"]


def test_valori_implicite_declarate():
    r = calculeaza(dict(TABLOU, priza={}))
    t = " | ".join(r["presupus"])
    # v1.3 (P0-2, pct. 3): n și L_p apar cu valorile ADOPTATE după dimensionare (inițialele între paranteze)
    for s in ("ρ sol = 100 Ω·m", "priză: 11 electrozi (mărit automat de la 2", "Ø 60", "a = 2·L = 6 m",
              "platbandă 65 m = (n − 1)·a + racord = 10·6 + 5 m (inițial 11 m)",
              "racord platbandă → piesa de separație 5 m", "40 × 4 mm", "ψ_e = 1,6", "ψ_pl = 3,5"):
        assert s in t, s


def test_memoriu_capitol_priza():
    r = calculeaza(dict(TABLOU, priza=EXEMPLU))
    h = memoriu.genereaza_html({}, r)
    assert "4. Priza de pământ" in h and "5. Verificări" in h and "6. Pașii de calcul" in h and "Platbandă OL-Zn" in h
    h = memoriu.genereaza_html({}, calculeaza(TABLOU))
    assert "Priza de pământ" not in h and "4. Verificări" in h


def test_nota_priza_si_monotonie():
    r = calculeaza(dict(TABLOU, priza=EXEMPLU))
    assert r["rezultat"]["priza"]["nota"].startswith("Priză de pământ: 11 electrozi") and "ψ_pl = 3,5" in r["rezultat"]["priza"]["nota"]
    # Rp scade strict cu n (η scade, dar n·η crește) — pe tot domeniul 1…30, la a/L = 1, 2, 3
    for a in (3, 6, 9):
        par = _par(electrozi={"n": 1, "L_m": 3, "d_m": 0.0635, "distanta_m": a}, platbanda={})
        v = [pamant.calcul(par, n)["Rp"] for n in range(1, 31)]
        assert all(y < x for x, y in zip(v, v[1:])), a
    assert math.isclose(pamant.calcul(_par(psi=1.6, psi_platbanda=1.6), 2)["Rp"],
                        1.6 * pamant.calcul(_par(psi=1.0, psi_platbanda=1.0), 2)["Rp"])
