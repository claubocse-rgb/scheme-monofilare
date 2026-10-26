"""v1.3 (UX r3, P0-2): CEF racordat în TG existent, cablul C0 dimensionat, cablurile invertoarelor din setările globale
și pe grup, valorile adoptate ale prizei în „presupus”, memoriul cu etichete românești și mesajele curățate."""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.calc import calculeaza  # noqa: E402
from engine import memoriu  # noqa: E402

# CEF 100 kW: Σ Iac = 1,1·100 000/(√3·400) = 158,77 A; Ip,min invertor = 1,25·100 000/692,82 = 180,42 A
# → QG MCCB 200 A, Ir = 0,95·200 = 190 A
CEF = {"tip_schema": "cef", "kWp": 120, "invertoare": [{"n": 1, "Pn_kW": 100}]}


def _v(r, cod, nivel=None):
    return [v for v in r["verificari"] + r["info"] if v["cod"] == cod and (nivel is None or v["nivel"] == nivel)]


def _b(r):
    return {(v["cod"], v["obiect"]) for v in r["verificari"] if v["nivel"] == "BLOCANT"}


# ---------------------------------------------------------------------------------------------------------------
# C0 și racordul în TG existent
# ---------------------------------------------------------------------------------------------------------------
def test_c0_dimensionat_si_fara_tg_existent():
    r = calculeaza(dict(CEF, L_racord_m=60))
    z = r["rezultat"]
    c0 = z["C0"]
    assert c0["Ib_A"] == pytest.approx(158.77, rel=1e-3) and c0["L_m"] == 60
    assert c0["protectie"]["tip"] == "MCCB" and c0["protectie"]["In_A"] == 200 and c0["protectie"]["Ir_A"] == 190
    assert c0["Iz_corectat_A"] >= 190 and c0["cablu"] and c0["descriere"].endswith("punctul de racord")
    # ΔU la invertor = ΔU pe cablul invertorului + ΔU pe C0 (cumulat până la punctul de racord)
    inv = z["invertoare"][0]
    assert inv["dU_cumulat_pct"] == pytest.approx(inv["dU_ramura_pct"] + c0["dU_cumulat_pct"], rel=1e-9)
    # Ik la bara TGD-CF = capătul C0 (mai mic decât la punctul de racord)
    assert z["bara_TGD_CF"]["Ik3max_kA"] < c0["Ik3max_origine_kA"] == pytest.approx(25.0)
    assert "Q_TG" not in z and not z["racord"].get("tg_existent")


def test_fara_lungime_c0_neschimbat():
    r = calculeaza(CEF)
    assert "C0" not in r["rezultat"] and "bara_TGD_CF" not in r["rezultat"]


def test_tg_existent_complet():
    # Q TG MCCB 250 A (Ip 250 ≥ Σ Iac 158,8), Icu 36 kA ≥ Ik3 TG 15 kA; C0 60 m în aer (E, Cu)
    r = calculeaza(dict(CEF, racord="tg_existent", L_racord_m=60, racord_In_Q_A=250, racord_Icu_kA=36, Ik3_TG_kA=15,
                        cablu={"material": "Cu", "metoda": "E"}))
    z = r["rezultat"]
    assert z["racord"]["tg_existent"] and z["racord"]["tip"].startswith("TG existent")
    assert z["Q_TG"] == {"tip": "MCCB", "In_A": 250, "Ir_A": 250.0, "Icu_kA": 36.0}
    assert z["C0"]["Ik3max_origine_kA"] == pytest.approx(15.0, rel=1e-3) and z["C0"]["material"] == "Cu"
    assert z["C0"]["descriere"] == "TGD-CF → TG existent"
    # selectivitatea Q TG (amonte) față de QG (aval): raport 250/190 = 1,32 < 1,6 → V41 AVERTISMENT
    assert any(v["obiect"] == "Q TG vs QG" for v in _v(r, "V41"))
    # Q TG față de C0: 250 A > Iz' C0 → V44 AVERTISMENT (C0 protejat la suprasarcină doar de QG)
    assert any(v["obiect"] == "Q TG / C0" and v["nivel"] == "AVERTISMENT" for v in _v(r, "V44"))
    assert ("V33", "Q TG") not in _b(r)


@pytest.mark.parametrize("extra,cod,obiect,nivel", [
    ({"racord_In_Q_A": 125}, "V44", "Q TG", "BLOCANT"),           # 125 A < Σ Iac 158,8 A: declanșează la injecție
    ({"racord_In_Q_A": 230}, "V05", "Q TG", "BLOCANT"),           # 230 A nu există în seria MCCB
    ({"racord_In_Q_A": 250, "racord_Icu_kA": 10, "Ik3_TG_kA": 15}, "V33", "Q TG", "BLOCANT"),
    ({"racord_In_Q_A": 250}, "V33", "Q TG", "AVERTISMENT"),        # Icu nedeclarat
    ({"racord_In_Q_A": 250, "racord_Q_tip": "gG"}, "V41", "Q TG vs QG", "AVERTISMENT"),
])
def test_tg_existent_verificari(extra, cod, obiect, nivel):
    r = calculeaza(dict(CEF, racord="tg_existent", L_racord_m=40, **extra))
    assert any(v["obiect"] == obiect for v in _v(r, cod, nivel)), [(v["cod"], v["nivel"], v["obiect"]) for v in
                                                                   r["verificari"]]


def test_tg_existent_fara_c0_selectivitate():
    # fără lungime C0: Q TG tot se verifică față de QG
    r = calculeaza(dict(CEF, racord="tg", racord_In_Q_A=400, racord_Icu_kA=50))
    assert "C0" not in r["rezultat"] and r["rezultat"]["Q_TG"]["In_A"] == 400
    assert any(v["obiect"] == "Q TG vs QG" for v in _v(r, "V42") + _v(r, "V41"))
    # protecția din TG nedeclarată → presupunere declarată
    r = calculeaza(dict(CEF, racord="tg_existent", L_racord_m=40))
    assert any("protecția din TG existent" in x for x in r["presupus"]) and "Q_TG" not in r["rezultat"]


def test_tg_existent_punct_de_racord_verificat_dupa_puterea_totala():
    # 3 × 100 kW = 300 kW > 173 kVA → racord JT doar direct din PT OD (V66 AVERTISMENT), ca fără TG existent
    r = calculeaza(dict(CEF, invertoare=[{"n": 3, "Pn_kW": 100}], racord="tg_existent", L_racord_m=30))
    assert any(v["nivel"] == "AVERTISMENT" for v in _v(r, "V66"))
    # cu PT propriu: Sn < S → V67
    r = calculeaza(dict(CEF, invertoare=[{"n": 3, "Pn_kW": 100}], racord="tg_existent", pt_Sn_kVA=250, L_racord_m=30))
    assert ("V67", "schema") in _b(r) and r["rezultat"]["C0"]["Ik3max_origine_kA"] > 5


@pytest.mark.parametrize("intr,cod", [
    (dict(CEF, racord="pt"), "V07"), (dict(CEF, racord="aer"), "V12"), (dict(CEF, L_racord_m=0), "V09"),
    (dict(CEF, racord="tg_existent", racord_In_Q_A=-5), "V07"), (dict(CEF, racord_Q_tip="XYZ"), "V12"),
    (dict(CEF, cablu_C0="x"), "V07"), (dict(CEF, invertoare=[{"n": 1, "Pn_kW": 100, "cablu": {"metoda": "Z"}}]), "V10"),
])
def test_validare(intr, cod):
    assert cod in {c for c, _ in _b(calculeaza(intr))}


# ---------------------------------------------------------------------------------------------------------------
# cablurile invertoarelor: setări globale și pe grup
# ---------------------------------------------------------------------------------------------------------------
def test_cabluri_invertoare_setari_globale_si_pe_grup():
    r = calculeaza(dict(CEF, cablu={"material": "Cu", "metoda": "E"}))
    inv = r["rezultat"]["invertoare"][0]
    assert (inv["material"], inv["metoda"], inv["L_m"]) == ("Cu", "E", 30)
    # cablu_inv are prioritate față de cablul global; grupul are prioritate față de amândouă
    r = calculeaza(dict(CEF, cablu={"material": "Cu", "metoda": "E"}, cablu_inv={"metoda": "C"},
                        invertoare=[{"n": 1, "Pn_kW": 50, "L_m": 12},
                                    {"n": 1, "Pn_kW": 50, "cablu": {"metoda": "D1", "material": "Al", "L": 70}}]))
    a, b = r["rezultat"]["invertoare"]
    assert (a["material"], a["metoda"], a["L_m"]) == ("Cu", "C", 12)
    assert (b["material"], b["metoda"], b["L_m"]) == ("Al", "D1", 70)
    assert not any("lungime cablu invertor CEF 30 m" in x for x in r["presupus"])


# ---------------------------------------------------------------------------------------------------------------
# memoriu și mesaje
# ---------------------------------------------------------------------------------------------------------------
def test_memoriu_date_intrare_cu_etichete():
    calc = {"tip_schema": "bransament", "retea": "tri", "P_kW": 15, "L_coloana_m": 20, "Zb_OD_ohm": [0.12, 0.06], "Ik3_OD_kA": 10,
            "cablu": {"material": "Cu", "metoda": "D1"}, "priza": {"rho_ohm_m": 80, "electrozi": {"n": 3}}}
    h = memoriu.genereaza_html({"calc": calc}, calculeaza(calc))
    cap1 = h[h.index("1. Date de intrare"):h.index("2. Ipoteze")]
    for brut in ("L_coloana_m", "Zb_OD_ohm", "Ik3_OD_kA", "rho_ohm_m", "tip_schema", "{'"):
        assert brut not in cap1, brut
    for et in ("Lungime coloană C2 [m]", "Impedanța buclei OD (ATR) [Ω]", "0,12 + j0,06", "material: Cu",
               "rezistivitatea solului ρ [Ω·m]", "branșament DEER"):
        assert et in cap1, et


SCHEME = [
    dict(CEF, racord="tg_existent", L_racord_m=60, racord_In_Q_A=250),
    {"tip_schema": "tablou", "L_alimentare_m": 30, "plecari": [{"nume": "Prize", "In_A": 16}, {"nume": "Hala", "In_A": 63}],
     "priza": {"electrozi": {"n": 1}, "platbanda": False, "rho_ohm_m": 5}},
    {"tip_schema": "tablou", "plecari": [{"nume": "Hala", "In_A": 63}], "priza": {}},
    {"tip_schema": "pt", "Sn_kVA": 400, "plecari": [{"nume": "TD", "In_A": 100}], "priza": {}},
    {"tip_schema": "bransament", "retea": "tri", "P_kW": 60, "L_coloana_m": 300},
    {"tip_schema": "ge_ats", "Sn_GE_kVA": 50, "P_sarcina_kW": 60},
]


@pytest.mark.parametrize("intr", SCHEME)
def test_mesaje_curate(intr):
    r = calculeaza(intr)
    for v in r["verificari"] + r["info"]:
        if v["cod"] in ("V11", "V90", "V80", "V81"):
            continue
        assert not v["mesaj"].startswith(v["obiect"] + ":"), v           # obiectul nu se repetă
        assert not re.search(r"(?<![\d,.])\b1 (electrozi|plecări|circuite|invertoare)\b", v["mesaj"]), v
        for t in (v["mesaj"], v.get("remediere") or ""):
            assert not re.search(r"\b(introduceți|verificați|confirmați|cereți|măriți|alegeți|declarați|reduceți|"
                                 r"înlocuiți|îmbunătățiți|acceptați|măsurați)\b", t, re.I), t
    assert not any(re.search(r"(?<![\d,.])\b1 plecări\b", x) for x in r["presupus"])


def test_priza_mesaj_fara_obiect_si_singular():
    # n = 1 electrod fără platbandă, ρ = 5 Ω·m, ψ_e 1,6: R_e = 8/(2π·3)·4,8869 = 2,07 Ω ≤ 4 Ω → V37 INFO cu „1 electrod”
    r = calculeaza(SCHEME[1])
    v = _v(r, "V37")[0]
    assert v["obiect"] == "priza de pământ" and v["mesaj"].startswith("Rp = ") and "1 electrod ×" in v["mesaj"]
