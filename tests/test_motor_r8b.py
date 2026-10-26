"""Regresie r8b — motor: (1) cabluri în paralel impuse (industrial #25: „2 × NA2XY 4x240 în paralel”): Iz' = n·Iz·kgrup(n)
(SR HD 60364-5-52 tab. B.52.17–B.52.19), protecția verificată față de Σ Iz, denumirea impusă dă materialul și izolația;
(2) circuitele unui tablou secundar al locuinței: `n_circuite` multiplică circuitul în bilanț, iar un circuit casnic dat
doar prin calibru intră cu puterea implicită a receptorului (DECIZIE), nu cu U·In. Intrare fizică directă."""
import os
import sys

import pytest

RAD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAD)

from engine import constructor  # noqa: E402
from engine.calc import calculeaza, norme  # noqa: E402
from engine.calc import cabluri as cb  # noqa: E402


def _b(r):
    return [v for v in r["verificari"] if v["nivel"] == "BLOCANT"]


# ------------------------------------------------------------------------------------------ 1. cabluri în paralel
def _tg(cab, In=400, L=80, plecari=None):
    return {"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 630, "schema_pamant": "TN-S",
            "L_alimentare_m": L, "In_A": In, "cablu": cab, "retea": "tri",
            "plecari": plecari or [{"nume": "TD1", "In_A": 250}, {"nume": "TD2", "In_A": 160}]}


def _q1(cab, **kw):
    m, r = constructor.genereaza(_tg(cab, **kw))
    return r, r["rezultat"]["Q1_C1"]


@pytest.mark.parametrize("cab", [
    {"S_fortat": 240, "n_paralel": 2, "tip_cablu": "NA2XY"},
    {"S_fortat": 240, "n_fortat": 2, "tip_cablu": "NA2XY"},
    {"S_fortat": 240, "n": 2, "material": "Al", "izolatie": "XLPE"},
])
def test_tg_din_pt_400A_2xNA2XY_4x240_80m(cab):
    r, q = _q1(cab)
    assert not [v for v in _b(r) if v["cod"] in ("V02", "V03")]
    assert q["n_paralel"] == 2 and q["S_faza_mm2"] == 240 and q["material"] == "Al" and q["izolatie"] == "XLPE"
    assert q["protectie"]["In_A"] == 400
    # Iz' = n · Iz(tabel) · kgrup(n circuite) — 2 · 253 · 0,85 = 430,1 A ≥ Ir 380 A
    kg = norme.k_grupare(q["metoda"], 2, "atingere", None)
    assert q["Iz_corectat_A"] == pytest.approx(2 * q["Iz_tabel_A"] * kg * norme.k_temperatura("XLPE", q["metoda"], 20.0)
                                               * norme.k_rezistivitate_sol(q["metoda"], 2.5))
    assert q["Iz_corectat_A"] == pytest.approx(430.1, abs=0.1)
    assert q["Iz_corectat_A"] >= q["protectie"]["Ir_A"] and q["I2_A"] <= 1.45 * q["Iz_corectat_A"]


def test_denumirea_impusa_ramane_pe_cablu():
    _, q = _q1({"S_fortat": 240, "n_paralel": 2, "tip_cablu": "NA2XY"})
    assert q["cablu"].startswith("2 × (NA2XY 4×240") and q.get("tip_cablu") == "NA2XY"


def test_iz_paralel_e_suma_cu_grupare_in_aer():
    # metoda E (pe pat de cabluri): 2 cabluri = 2 circuite la grupare
    _, q = _q1({"S_fortat": 240, "n_paralel": 2, "tip_cablu": "NA2XY", "metoda": "E"})
    c = {"material": "Al", "izolatie": "XLPE", "metoda": "E", "retea": "tri", "theta": 30.0, "rho_sol": 2.5,
         "n_alte": 0, "distanta": "atingere", "aranjament": None}
    iz1, _, izp1 = cb.iz_corectat(c, 1, 240)
    iz2, k2, izp2 = cb.iz_corectat(c, 2, 240)
    assert izp2 == pytest.approx(2 * iz1 * k2) and k2 < 1.0 and izp2 < 2 * izp1
    assert q["Iz_corectat_A"] == pytest.approx(izp2)


def test_fara_izolatie_pvc_conservator_cu_indicatie_xlpe():
    r, q = _q1({"S_fortat": 240, "n_paralel": 2, "material": "Al"})
    assert q["izolatie"] == "PVC" and q["Iz_corectat_A"] == pytest.approx(370.6, abs=0.1)   # 2 · 218 · 0,85
    assert [v for v in _b(r) if v["cod"] == "V02"]
    assert any("XLPE" in p and "430,1" in p for p in r["presupus"])


def test_630A_pe_2x240_al_ingropat_ramane_v02():
    # #25: TD1 400 A + TD2 250 A → Q1 630 A (Ir 598 A) — 2 × NA2XY 4x240 în pământ (430 A) chiar nu ajung
    r, q = _q1({"S_fortat": 240, "n_paralel": 2, "tip_cablu": "NA2XY"}, In=None,
               plecari=[{"nume": "TD1", "In_A": 400}, {"nume": "TD2", "In_A": 250}])
    assert q["n_paralel"] == 2 and q["izolatie"] == "XLPE"
    assert [v for v in _b(r) if v["cod"] == "V02"]


def test_n_paralel_fara_sectiune_fixeaza_numarul():
    _, q = _q1({"n_paralel": 2, "material": "Cu", "izolatie": "XLPE"})
    assert q["n_paralel"] == 2
    assert q["Iz_corectat_A"] >= q["Iz_min_A"]
    c = {"material": "Cu", "izolatie": "XLPE", "metoda": q["metoda"], "retea": "tri", "theta": 20.0, "rho_sol": 2.5,
         "n_alte": 0, "distanta": "atingere", "aranjament": None}
    sect = cb.sectiuni(c)
    S_ant = sect[sect.index(q["S_faza_mm2"]) - 1]
    assert cb.iz_corectat(c, 2, S_ant)[2] < q["Iz_min_A"]          # cea mai mică secțiune la n = 2


def test_denumire_contra_campuri_explicite():
    _, q = _q1({"S_fortat": 240, "n_paralel": 2, "tip_cablu": "NA2XY", "material": "Cu"})
    assert q["material"] == "Cu" and "NA2XY" not in q["cablu"]


@pytest.mark.parametrize("den, mi", [("NA2XY", ("Al", "XLPE")), ("N2XY", ("Cu", "XLPE")), ("NAYY", ("Al", "PVC")),
                                     ("NYY", ("Cu", "PVC")), ("CYY-F", ("Cu", "PVC")), ("ACYABY", ("Al", "PVC")),
                                     ("AC2XABY", ("Al", "XLPE")), ("cyaby", ("Cu", "PVC")), ("XYZ", None)])
def test_material_izolatie_din_denumire(den, mi):
    assert norme.material_izolatie_din_denumire(den) == mi


# ------------------------------------------------------------------------------- 2. tablou secundar la locuință
def _loc(circ_td, Pa=10, retea="tri", circ=None):
    return {"tip_schema": "locuinta", "retea": retea, "schema_pamant": "TN-C-S", "alimentare": {"P_aprobata_kW": Pa},
            "circuite": circ or [{"nume": "Iluminat parter", "receptor": "iluminat"},
                                 {"nume": "Prize parter", "receptor": "prize"}],
            "tablouri_secundare": [{"nume": "TD Etaj", "L_m": 15, "circuite": circ_td}]}


def _td(r, nume="TD Etaj"):
    return next(c for g in r["rezultat"]["grupe_DDR"] for c in g["circuite"] if c["nume"] == nume)


ETAJ = [{"nume": "Prize", "receptor": "prize", "In_A": 16, "n_circuite": 4},
        {"nume": "Aer condiționat", "receptor": "aer_conditionat", "n_circuite": 2},
        {"nume": "Iluminat", "receptor": "iluminat"}]


def test_td_etaj_n_circuite_si_calibru():
    r = calculeaza(_loc(ETAJ))
    td = _td(r)
    assert [p["nume"] for p in td["tablou_secundar"]["plecari"]] == [
        "Prize 1", "Prize 2", "Prize 3", "Prize 4", "Aer condiționat 1", "Aer condiționat 2", "Iluminat"]
    # Σ Pi = 4·2 + 2·2,5 + 0,5 = 13,5 kW (7 circuite); receptoare casnice → ks locuință 0,4 (6–9 receptoare)
    assert any("7 circuite, Σ Pi = 13,5 kW, ks = 0,4" in p for p in r["pasi"])
    assert td["P_kW"] == pytest.approx(5.4)
    assert td["P_kW"] <= 10 and not [v for v in r["verificari"] if v["cod"] == "V46" and "TD Etaj" in v["obiect"]]
    assert not _b(r)
    assert any("calibru 16 A → 2 kW" in p and "DECIZIE" in p for p in r["presupus"])
    # circuitul de prize își păstrează calibrul C16
    pr1 = next(p for p in td["tablou_secundar"]["plecari"] if p["nume"] == "Prize 1")
    assert pr1["protectie"]["In_A"] == 16


def test_n_circuite_multiplica_bilantul():
    unu = _td(calculeaza(_loc([{"nume": "Prize", "receptor": "prize", "P_kW": 2.0}])))
    patru = _td(calculeaza(_loc([{"nume": "Prize", "receptor": "prize", "P_kW": 2.0, "n_circuite": 4}])))
    assert unu["P_kW"] == pytest.approx(0.8 * 2.0) and patru["P_kW"] == pytest.approx(0.6 * 8.0)


def test_prize_c16_nu_sunt_incarcate_la_in_trifazat():
    # înainte: In 16 A pe TD trifazat = √3·400·16·0,9 = 9,98 kW pentru un circuit de prize
    r = calculeaza(_loc([{"nume": "Prize", "receptor": "prize", "In_A": 16}]))
    assert _td(r)["P_kW"] == pytest.approx(0.8 * 2.0)


def test_td_atelier_forta_dat_prin_calibru_ramane_la_in():
    r = calculeaza(_loc([{"nume": "Strung", "In_A": 20, "retea": "tri"}, {"nume": "Prize atelier", "In_A": 16}], Pa=20))
    p_strung = 3 ** 0.5 * 400 * 20 * norme.COSFI_IMPLICIT["motor"] / 1000.0     # strung = motor, cosφ 0,85
    assert _td(r)["P_kW"] == pytest.approx(norme.ks_implicit(2) * (p_strung + 2.0), abs=0.01)
