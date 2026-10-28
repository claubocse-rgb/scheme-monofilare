"""Selectivitatea DDR în serie (SPEC §B.18.1, v1.3 R5): IΔn amonte ≥ 3·IΔn aval și temporizarea amontelui cu
≥ 0,15 s peste a avalului (instantaneu 0, S 0,15 s echivalent, reglabil Δt) — SR HD 60364-5-53 art. 535.3. V43 INFO când e îndeplinită, AVERTISMENT altfel (variante „egal”, „TT”, generală); DDR-urile alese de
motor sunt selective (fără V43 AVERTISMENT)."""
import os
import random
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.calc import calculeaza, ddr  # noqa: E402
from engine.calc.comun import Jurnal  # noqa: E402


def _v43(r, nivel="AVERTISMENT"):
    src = r["verificari"] if nivel != "INFO" else r["info"]
    return {v["obiect"]: v for v in src if v["cod"] == "V43" and v["nivel"] == nivel}


def _tablou(**kw):
    return dict({"tip_schema": "tablou", "L_alimentare_m": 30}, **kw)


# ---------------------------------------------------------------------------------------------------------------
# regula de bază (modulul ddr)
# ---------------------------------------------------------------------------------------------------------------
def _d(idn, temp, den):
    """temp: "i" instantaneu, "S", sau număr = Δt reglabil."""
    return ddr.descriere(idn, temp == "S", den, temp if isinstance(temp, float) else None)


@pytest.mark.parametrize("am,av,ok", [
    ((300, "S"), (30, "i"), True),        # 300 ≥ 90, S (0,15 s) → instantaneu (0): Δt 0,15 ≥ 0,15
    ((100, "S"), (30, "i"), True),        # 100 ≥ 90
    ((300, "i"), (30, "i"), False),       # raport bun, amonte instantaneu
    ((300, "S"), (100, "i"), True),       # 300 ≥ 300 (limita exactă)
    ((300, "S"), (100, "S"), False),      # M5-4: S → S nu e selectiv, deși 300 ≥ 3·100
    ((300, "S"), (300, "S"), False),
    ((30, "i"), (30, "i"), False),        # același IΔn, aceeași temporizare
    ((1000, 0.3), (300, "S"), True),      # reglabil Δt 0,3 s → S (0,15 s): Δt 0,15 s, 1000 ≥ 900
    ((1000, 0.15), (300, "S"), False),    # reglabil 0,15 s = S → nu
    ((300, 0.15), (100, "i"), True),      # reglabil 0,15 s → instantaneu
    ((300, 0.06), (100, "i"), False),     # Δt 0,06 s < 0,15 s
])
def test_regula(am, av, ok):
    j = Jurnal()
    rez = ddr.verifica(j, _d(*am, "A"), _d(*av, "B"), "X")
    assert rez is ok
    niv = {v["nivel"] for v in j.verificari + j.info if v["cod"] == "V43"}
    assert niv == ({"INFO"} if ok else {"AVERTISMENT"})


def test_variante_mesaj_si_remediere():
    # același IΔn 30 mA, instantanee → „egal”, remediere: amonte 100 mA temporizat (prima treaptă ≥ 90) sau aval 10 mA
    j = Jurnal()
    ddr.verifica(j, _d(30, "i", "DDR Q1"), _d(30, "i", "DDR P1"), "P1")
    v = j.verificari[0]
    assert "același IΔn = 30 mA și aceeași temporizare (instantaneu)" in v["mesaj"]
    assert "100 mA temporizat" in v["remediere"] and "10 mA" in v["remediere"]
    # amonte instantaneu, raport bun → motivul „nu e de tip S”
    j = Jurnal()
    ddr.verifica(j, _d(300, "i", "RCBO BMPM"), _d(30, "i", "DDR INV"), "INV")
    assert "nu e de tip S" in j.verificari[0]["mesaj"] and j.verificari[0]["obiect"] == "INV vs RCBO BMPM"
    # S → S (M5-4): motivul „două DDR S în serie”, remediere: aval instantaneu sau releu reglabil Δt ≥ 0,30 s
    j = Jurnal()
    ddr.verifica(j, _d(300, "S", "RCCB BMPT"), _d(100, "S", "DDR Q1"), "Q1")
    v = j.verificari[0]
    assert "două DDR S în serie" in v["mesaj"] and "aval instantaneu" in v["remediere"] and "Δt ≥ 0,3 s" in v["remediere"]
    # TT: aval 100 mA → amonte necesar 300 mA; RA = 500 Ω · 0,3 A = 150 V > 50 V → varianta TT, remediere
    # RA ≤ 50/0,3 = 166,7 Ω
    j = Jurnal()
    ddr.verifica(j, _d(100, "S", "DDR amonte"), _d(100, "i", "DDR P1"), "P1", RA_ohm=500)
    v = j.verificari[0]
    assert "RA = 500 Ω" in v["mesaj"] and "≤ 100 mA" in v["mesaj"] and "RA ≤ 166,7 Ω" in v["remediere"]


@pytest.mark.parametrize("lim,am,intrare,circ", [
    (300, (300, "S"), None, 100),        # RCCB BMPT 300 S, RA ≤ 166 Ω → Q1 fără DDR, circuite 100 mA instantaneu
    (100, (300, "S"), None, 100),        # RA ≤ 500 Ω
    (100, (100, "S"), None, 30),         # amonte declarat 100 S → circuite 30
    (300, (300, "i"), (300, 0.15), 100),  # amonte instantaneu → bloc diferențial reglabil 300 mA Δt 0,15 s pe Q1
    (100, (100, "i"), (100, 0.15), 30),
    (30, (300, "S"), None, 30),          # RA mare: doar 30 mA (amonte 300 S → V34 la schemă)
    (30, (30, "S"), None, 30),           # seria epuizată: circuite 30 sub amonte 30 → V43 la verificare
])
def test_alege_tt(lim, am, intrare, circ):
    al = ddr.alege_tt(lim, _d(*am, "A"))
    assert al["idn_circuite"] == circ
    assert (al["intrare"] and (al["intrare"]["IdN_mA"], al["intrare"]["dt_s"])) == (intrare or None) or \
        (al["intrare"] is None and intrare is None)


# ---------------------------------------------------------------------------------------------------------------
# DDR-uri alese de motor: selective (TN și TT)
# ---------------------------------------------------------------------------------------------------------------
def test_tn_prize_sub_rccb_bmpt_selectiv():
    # RCCB BMPT 300 mA S → DDR 30 mA pe prize: 300 ≥ 90 și S → V43 INFO
    r = calculeaza(_tablou(plecari=[{"nume": "Prize", "In_A": 16}, {"nume": "Hala", "In_A": 63}]))
    assert "P1·Prize vs RCCB BMPT" in _v43(r, "INFO") and not _v43(r)


@pytest.mark.parametrize("ra", [4, 50, 100, 150, 166])
def test_tt_lant_selectiv(ra):
    # M5-4: RA ≤ 166,7 Ω: RCCB BMPT 300 mA S protejează Q1 (fără DDR propriu); plecări 100 mA instantaneu,
    # prize 30 mA instantaneu; fără V43 AVERTISMENT (S → instantaneu, IΔn ≥ 3×)
    r = calculeaza(_tablou(schema_pamant="TT", RA_ohm=ra, plecari=[{"nume": "Hala", "In_A": 63},
                                                                    {"nume": "Prize", "In_A": 16}]))
    z = r["rezultat"]
    assert "DDR" not in z["Q1_C1"]
    assert [p["DDR"]["IdN_mA"] for p in z["plecari"]] == [100, 30] and not any(p["DDR"].get("selectiv") for p in z["plecari"])
    assert not _v43(r) and set(_v43(r, "INFO")) == {"P1·Hala vs RCCB BMPT", "P2·Prize vs RCCB BMPT"}
    # nota 3 (M5-4): DDR-urile reale, nu „IΔn 300 mA pe fiecare circuit”
    nota = z["nota_schema_pamant"].replace("\u00a0", " ")
    assert "Q1 fără DDR propriu" in nota and "circuite IΔn 100 mA / 30 mA" in nota and "pe fiecare circuit" not in nota


def test_tt_ra_intre_166_si_500():
    # RA 400 Ω cu amonte declarat 100 mA S: 0,1·400 = 40 V; circuite ≤ 100/3 → 30 mA instantaneu; Q1 fără DDR
    r = calculeaza(_tablou(schema_pamant="TT", RA_ohm=400, IdN_amonte_mA=100, plecari=[{"nume": "Hala", "In_A": 63}]))
    assert "DDR" not in r["rezultat"]["Q1_C1"] and r["rezultat"]["plecari"][0]["DDR"]["IdN_mA"] == 30 and not _v43(r)


def test_tt_amonte_instantaneu_bloc_reglabil_pe_q1():
    # amonte declarat 300 mA instantaneu, RA 100: Q1 = bloc diferențial reglabil 300 mA, Δt 0,15 s (explicit în
    # rezultat); plecări 100 mA instantaneu. Perechea amonte instantaneu → Q1 rămâne neselectivă (V43 AV), Q1 → plecări
    # selectivă (V43 INFO)
    r = calculeaza(_tablou(schema_pamant="TT", RA_ohm=100, DDR_amonte_selectiv=False,
                           plecari=[{"nume": "Hala", "In_A": 63}]))
    d = r["rezultat"]["Q1_C1"]["DDR"]
    assert d["IdN_mA"] == 300 and d["dt_s"] == 0.15 and d["reglabil"] and d["aparat"] == "bloc_diferential"
    assert "impus" not in d and r["rezultat"]["plecari"][0]["DDR"]["IdN_mA"] == 100
    assert set(_v43(r)) == {"Q1/C1 vs RCCB BMPT"} and "P1·Hala vs DDR Q1/C1" in _v43(r, "INFO")
    assert "bloc diferențial reglabil 300 mA, Δt 0,15 s" in r["rezultat"]["nota_schema_pamant"].replace("\u00a0", " ")


def test_tt_cascada_fara_ddr_pe_alimentarea_td():
    # TT, RA 4 Ω: Q1 și alimentarea TD-1 fără DDR propriu (protejate de RCCB BMPT 300 S); circuitele lui TD-1: prize
    # 30 mA, iluminat 100 mA, instantanee — selective direct cu RCCB BMPT
    r = calculeaza(_tablou(schema_pamant="TT", RA_ohm=4, plecari=[{"nume": "TD-1", "copii": [
        {"nume": "Prize", "In_A": 16}, {"nume": "Iluminat", "In_A": 10}]}]))
    pl = r["rezultat"]["plecari"]
    assert "DDR" not in pl[0] and [p["DDR"]["IdN_mA"] for p in pl[1:]] == [30, 100]
    assert not _v43(r) and "P1·TD-1.1·Prize vs RCCB BMPT" in _v43(r, "INFO")
    assert any("fără DDR propriu" in s for s in r["pasi"])


def test_tt_ra_nu_permite_selectivitatea():
    # RA = 1000 Ω (doar 30 mA: 1000·0,03 = 30 V), amonte declarat 30 mA S: circuite 30 mA sub amonte 30 mA → ar trebui
    # amonte ≥ 100 mA, dar 1000·0,1 = 100 V > 50 V → V43 AVERTISMENT „TT”, remediere RA ≤ 500 Ω
    r = calculeaza(_tablou(schema_pamant="TT", RA_ohm=1000, IdN_amonte_mA=30, plecari=[{"nume": "Hala", "In_A": 63}]))
    av = _v43(r)
    assert set(av) == {"P1·Hala vs DDR amonte (declarat)"}
    assert "RA = 1000 Ω" in av["P1·Hala vs DDR amonte (declarat)"]["mesaj"]
    assert "RA ≤ 500 Ω" in av["P1·Hala vs DDR amonte (declarat)"]["remediere"] and not r["blocheaza_export"]


def test_cef_tt():
    # CEF prin BMPT, RA 100 Ω: RCCB BMPT 300 S protejează QG (fără DDR propriu) → invertoare 100 mA instantaneu
    r = calculeaza({"tip_schema": "cef", "kWp": 60, "invertoare": [{"n": 2, "Pn_kW": 25}], "schema_pamant": "TT",
                    "RA_ohm": 100})
    z = r["rezultat"]
    assert "DDR" not in z["QG"] and [i["DDR"]["IdN_mA"] for i in z["invertoare"]] == [100, 100]
    assert not _v43(r) and {"INV-1 vs RCCB BMPT", "INV-2 vs RCCB BMPT"} <= set(_v43(r, "INFO"))
    # amonte declarat 100 mA instantaneu, RA 400: QG bloc reglabil 100 mA Δt 0,15 s → invertoare 30 mA
    r = calculeaza({"tip_schema": "cef", "kWp": 60, "invertoare": [{"n": 1, "Pn_kW": 50}], "schema_pamant": "TT",
                    "RA_ohm": 400, "IdN_amonte_mA": 100, "DDR_amonte_selectiv": False})
    q = r["rezultat"]["QG"]["DDR"]
    assert (q["IdN_mA"], q["dt_s"], q["reglabil"]) == (100, 0.15, True)
    assert r["rezultat"]["invertoare"][0]["DDR"]["IdN_mA"] == 30
    assert set(_v43(r)) == {"QG vs DDR amonte (declarat)"} and "INV-1 vs DDR QG" in _v43(r, "INFO")


def test_prosumator():
    # Î6 (proiectant 28.10.2026): fără DDR pe invertor implicit → nicio pereche DDR
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 10})
    assert not _v43(r, "INFO") and not _v43(r)
    # DDR cerut — trifazat: RCCB BMPT 300 S → DDR invertor 30 mA → INFO
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 10, "ddr": True})
    assert "INV vs RCCB BMPT" in _v43(r, "INFO") and not _v43(r)
    # monofazat: RCBO BMPM 300 mA instantaneu → AVERTISMENT (amonte nu e S) — golden R02 (istoric v1.3)
    r = calculeaza({"tip_schema": "prosumator", "retea": "mono", "Pn_inv_kW": 3, "ddr": True})
    assert "nu e de tip S" in _v43(r)["INV vs RCBO BMPM"]["mesaj"]
    # dacă proiectantul declară RCBO-ul din amonte de tip S → INFO
    r = calculeaza({"tip_schema": "prosumator", "retea": "mono", "Pn_inv_kW": 3, "DDR_amonte_selectiv": True, "ddr": True})
    assert not _v43(r)


# ---------------------------------------------------------------------------------------------------------------
# DDR-uri impuse de utilizator
# ---------------------------------------------------------------------------------------------------------------
def test_ddr_general_si_circuite_finale_acelasi_idn():
    # DDR general 30 mA instantaneu pe Q1 → circuit final de prize 30 mA: același IΔn, niciunul S → V43 „egal”
    r = calculeaza(_tablou(circuite_finale=True, Q1_DDR={"IdN_mA": 30},
                           plecari=[{"nume": "Prize", "In_A": 16}, {"nume": "Iluminat", "In_A": 10, "receptor": "iluminat"}]))
    av = _v43(r)
    assert set(av) == {"P1·Prize vs DDR Q1/C1"}
    assert "același IΔn = 30 mA" in av["P1·Prize vs DDR Q1/C1"]["mesaj"]
    assert "100 mA temporizat" in av["P1·Prize vs DDR Q1/C1"]["remediere"]
    assert r["rezultat"]["Q1_C1"]["DDR"]["IdN_mA"] == 30 and r["rezultat"]["Q1_C1"]["DDR"]["impus"]
    assert "Q1/C1 vs RCCB BMPT" in _v43(r, "INFO")      # 300 S → 30: selectiv


def test_ddr_impus_s_sub_s_neselectiv():
    # M5-4: Q1 impus 100 mA S sub RCCB BMPT 300 mA S → neselectiv (S → S); prize 30 mA sub Q1 100 S → selectiv
    r = calculeaza(_tablou(Q1_DDR={"IdN_mA": 100, "selectiv": True}, plecari=[{"nume": "Prize", "In_A": 16}]))
    assert "două DDR S în serie" in _v43(r)["Q1/C1 vs RCCB BMPT"]["mesaj"] and "P1·Prize vs DDR Q1/C1" in _v43(r, "INFO")
    # releu reglabil Δt 0,3 s pe Q1: vs RCCB BMPT S (0,15 s) amontele are temporizare MAI MICĂ → neselectiv
    r = calculeaza(_tablou(Q1_DDR={"IdN_mA": 100, "dt_s": 0.3}, plecari=[{"nume": "Prize", "In_A": 16}]))
    assert r["rezultat"]["Q1_C1"]["DDR"]["dt_s"] == 0.3 and "Q1/C1 vs RCCB BMPT" in _v43(r)


def test_ddr_impus_amonte_instantaneu():
    # Q1 100 mA instantaneu → prize 30 mA: raport 100 ≥ 90, dar amonte nu e S → AVERTISMENT (motiv: tip S)
    r = calculeaza(_tablou(Q1_DDR={"IdN_mA": 100, "selectiv": False}, plecari=[{"nume": "Prize", "In_A": 16}]))
    v = _v43(r)["P1·Prize vs DDR Q1/C1"]
    assert "nu e de tip S" in v["mesaj"] and "amonte tip S" in v["remediere"]
    # Q1 100 mA S → prize INFO (dar Q1 S sub RCCB BMPT S → AV, vezi testul S → S)
    r = calculeaza(_tablou(Q1_DDR={"IdN_mA": 100, "selectiv": True}, plecari=[{"nume": "Prize", "In_A": 16}]))
    assert "P1·Prize vs DDR Q1/C1" in _v43(r, "INFO")


def test_ddr_impus_raport_insuficient_si_rccb_bmpt():
    # Q1 300 mA S sub RCCB BMPT 300 mA S: S → S și 300 < 900 → AVERTISMENT; plecare DDR 300 mA instantaneu sub Q1 300 S
    # → AVERTISMENT (300 < 900), remediere „IΔn amonte ≥ 1000 mA sau IΔn aval ≤ 100 mA”
    r = calculeaza(_tablou(Q1_DDR={"IdN_mA": 300, "selectiv": True},
                           plecari=[{"nume": "Hala", "In_A": 63, "DDR": {"IdN_mA": 300}}]))
    av = _v43(r)
    assert set(av) == {"Q1/C1 vs RCCB BMPT", "P1·Hala vs DDR Q1/C1"}
    assert "300 mA < 3·300 = 900 mA" in av["P1·Hala vs DDR Q1/C1"]["mesaj"]
    assert "≥ 1000 mA" in av["P1·Hala vs DDR Q1/C1"]["remediere"] and "≤ 100 mA" in av["P1·Hala vs DDR Q1/C1"]["remediere"]


def test_amonte_declarat_instantaneu():
    r = calculeaza(_tablou(DDR_amonte_selectiv=False, plecari=[{"nume": "Prize", "In_A": 16}]))
    assert "nu e de tip S" in _v43(r)["P1·Prize vs RCCB BMPT"]["mesaj"]


def test_cascada_tn_ddr_pe_td():
    # TN: TD-1 cu DDR impus 300 mA S (sub RCCB BMPT 300 S → AV: S → S și 300 < 900), prize 30 mA sub TD-1 300 S → INFO
    r = calculeaza(_tablou(plecari=[{"nume": "TD-1", "DDR": {"IdN_mA": 300, "selectiv": True},
                                     "copii": [{"nume": "Prize", "In_A": 16}]}]))
    assert set(_v43(r)) == {"P1·TD-1 vs RCCB BMPT"} and "P1·TD-1.1·Prize vs DDR P1·TD-1" in _v43(r, "INFO")


@pytest.mark.parametrize("intr,cod,obiect", [
    (_tablou(plecari=[{"nume": "A", "In_A": 16, "DDR": {"IdN_mA": 50}}]), "V12", "P1·A"),
    (_tablou(plecari=[{"nume": "A", "In_A": 16, "DDR": {"IdN_mA": 30, "selectiv": "da"}}]), "V12", "P1·A"),
    (_tablou(plecari=[{"nume": "A", "In_A": 16, "DDR": {"IdN_mA": 30, "tip": "Z"}}]), "V12", "P1·A"),
    (_tablou(Q1_DDR={"IdN_mA": 0}, plecari=[{"nume": "A", "In_A": 16}]), "V12", "Q1/C1"),
    (_tablou(Q1_DDR={"IdN_mA": 100, "dt_s": 2}, plecari=[{"nume": "A", "In_A": 16}]), "V12", "Q1/C1"),
    (_tablou(Q1_DDR=30, plecari=[{"nume": "A", "In_A": 16}]), "V07", "schema"),
    (_tablou(DDR_amonte_selectiv="S", plecari=[{"nume": "A", "In_A": 16}]), "V12", "schema"),
    (_tablou(IdN_amonte_mA=200, plecari=[{"nume": "A", "In_A": 16}]), "V12", "schema"),
    # prize ≤ 32 A cu DDR impus 100 mA → V29 (SR HD 60364-4-41 art. 411.3.3 cere 30 mA)
    (_tablou(plecari=[{"nume": "Prize", "In_A": 16, "DDR": {"IdN_mA": 100}}]), "V29", "P1·Prize"),
    # TT, RA 500 Ω: DDR impus 300 mA pe plecare → 150 V > 50 V
    (_tablou(schema_pamant="TT", RA_ohm=500, IdN_amonte_mA=100,
             plecari=[{"nume": "Hala", "In_A": 63, "DDR": {"IdN_mA": 300}}]), "V34", "P1·Hala"),
])
def test_ddr_invalid_blocant(intr, cod, obiect):
    r = calculeaza(intr)
    assert (cod, obiect) in {(v["cod"], v["obiect"]) for v in r["verificari"] if v["nivel"] == "BLOCANT"}


def test_proprietate_ddr_alese_de_motor_selective():
    """Pentru tablouri TN/TT aleatoare (prize, cascade, circuite finale) fără DDR impus și cu RA ≤ 500 Ω (amonte
    declarat 100 mA S peste 166 Ω): niciun V43 AVERTISMENT — DDR-urile alese automat sunt selective (în IΔn și timp)."""
    rnd = random.Random(1303)
    for _ in range(150):
        def pl(nivel):
            p = {"nume": rnd.choice(["Prize", "Iluminat", "Hala", "Pompa", "Birou"]), "In_A": rnd.choice([10, 16, 25, 32])}
            if nivel == 0 and rnd.random() < 0.3:
                p = {"nume": "TD", "copii": [pl(1) for _ in range(rnd.randint(1, 3))]}
            return p
        intr = _tablou(plecari=[pl(0) for _ in range(rnd.randint(1, 4))],
                       circuite_finale=rnd.random() < 0.2)
        if rnd.random() < 0.5:
            ra = rnd.choice([1, 4, 10, 50, 100, 150, 166, 300, 500])
            intr.update(schema_pamant="TT", RA_ohm=ra)
            if ra > 166:
                intr["IdN_amonte_mA"] = 100
        r = calculeaza(intr)
        assert not _v43(r), (intr, _v43(r))
