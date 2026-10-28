"""Testul API-ului pentru panoul „Dimensionează”: `dimensioneaza_ramura_simpla(p)` (lanțul SPEC §B.21 pentru o
ramură izolată, cu contextul implicit §B.0 — bara unui TG alimentat din rețeaua publică)."""
import json
import os
import re
import sys

RADACINA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RADACINA)

from engine.calc import dimensioneaza_ramura_simpla, calculeaza_ramura  # noqa: E402
from engine.calc import scurtcircuit as sc  # noqa: E402
from engine.calc.comun import Jurnal  # noqa: E402

with open(os.path.join(RADACINA, "tests", "date", "cazuri_golden.json"), encoding="utf-8") as f:
    CHEI_PLECARE = set(next(c for c in json.load(f)["cazuri"] if c["id"] == "T01")["asteptat"]["plecari"][0]) - {"nume", "nivel"}


def s(t):
    return re.sub(r"[  ]", " ", t)


def test_chei_si_texte():
    r = dimensioneaza_ramura_simpla({"P_kW": 25, "L_m": 50, "receptor": "tablou"})
    assert not r["blocheaza"]
    assert CHEI_PLECARE <= set(r["rezultat"])
    rr = r["rezultat"]
    # aceeași soluție ca P1·Grajd din T02 (25 kW, Al PVC D1, 50 m): gG 50 A pe Al 25 mm² (fără mărire, bara la ΔU 0)
    assert rr["protectie"]["tip"] == "gG" and rr["protectie"]["In_A"] == 50
    assert (rr["material"], rr["S_faza_mm2"], rr["S_PE_mm2"]) == ("Al", 25.0, 10.0)
    assert s(r["text_cablu"]) == "ACYAbY 4×25 mm² + FY 1×10 mm² (PE)"
    assert s(r["text_lista"][0]) == "Separator 3P cu siguranțe fuzibile NH 000, 50 A gG"
    assert s(" · ".join(r["text_desen"])) == "3 × 50 A gG"
    assert s(r["text_desen_cablu"][0]).startswith("ACYAbY 4×25 mm²")
    assert any("25 kA" in x for x in r["presupus"]) and r["pasi"]
    assert {i["cod"] for i in r["info"]} >= {"V30", "V33", "V35"}


def test_identic_cu_lantul_B21():
    """Aceeași intrare prin API și direct prin calculeaza_ramura cu contextul implicit dau același rezultat."""
    p = {"P_kW": 40, "L_m": 80, "receptor": "motor", "rol": "plecare"}
    r = dimensioneaza_ramura_simpla(p)
    j = Jurnal()
    ctx = sc.context_od(None, None, ddr_amonte=True)
    d = calculeaza_ramura({"rol": "plecare", "receptor": "motor", "retea": "tri", "P_kW": 40,
                           "cablu": {"L": 80.0, "metoda": "D1", "material": "Al", "material_implicit": True}},
                          ctx, j, "ramura")
    for k in ("Ib_A", "S_faza_mm2", "n_paralel", "material", "Ik1min_capat_A", "dU_cumulat_pct", "cablu"):
        assert r["rezultat"][k] == d["rezultat"][k]
    assert [(v["cod"], v["nivel"]) for v in r["verificari"]] == [(v["cod"], v["nivel"]) for v in j.verificari]


def test_circuit_final_prize_mono_ddr():
    r = dimensioneaza_ramura_simpla({"In_A": 16, "rol": "final", "receptor": "prize", "retea": "mono"})
    rr = r["rezultat"]
    assert rr["protectie"]["tip"] == "MCB" and rr["protectie"]["curba"] == "B"
    # v1.2: DDR primește și calibrul (≥ In, seria RCCB) și polii (2P la monofazat), pentru desen
    assert rr["DDR"] == {"IdN_mA": 30, "tip": "A", "In_A": 16, "poli": "2P"} and rr["t_deconectare_s"] == 0.4
    assert s(r["text_cablu"]) == "CYY-F 3×2,5 mm²" and s(r["text_desen"][0]).startswith("1P+N · B16")


def test_origine_pt_propriu_si_ik3_dat():
    r = dimensioneaza_ramura_simpla({"P_kW": 30, "rol": "final", "receptor": "forta", "origine": "pt_propriu",
                                     "Ik3_origine_kA": 10, "dU_origine_pct": 1.5, "material": "Cu", "metoda": "C"})
    rr = r["rezultat"]
    assert rr["dU_limita_pct"] == 8.0 and abs(rr["Ik3max_origine_kA"] - 10) < 1e-9
    assert abs(rr["dU_cumulat_pct"] - 1.5 - rr["dU_ramura_pct"]) < 1e-9
    assert not any(v["cod"] == "V31" for v in r["verificari"])          # fără DDR în amonte


def test_date_contradictorii_si_absurde():
    r = dimensioneaza_ramura_simpla({"P_kW": 10, "In_A": 16})
    assert r["blocheaza"] and r["verificari"][0]["cod"] == "V12" and r["rezultat"] is None
    r = dimensioneaza_ramura_simpla({"P_kW": 10, "cosfi": 1.4})
    assert r["blocheaza"] and r["verificari"][0]["cod"] == "V08"
    r = dimensioneaza_ramura_simpla({"In_A": 72})
    assert r["blocheaza"] and r["verificari"][0]["cod"] == "V05"
