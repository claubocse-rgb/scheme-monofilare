"""Runda 4c (teste/r4/proiectant_c.md, teste/r4/verificator_c.md, teste/r4/ux_c.md) — SPEC §C.8 v1.7: Q în afara
seriei (M-c1), câmpuri globale invalide ignorate (m-c4), Zb rurală presupusă, nu „din ATR” (N11), VE sub DDR tip AC
(M-c3), fără chei interne (m-c5 / C3), nota ks fără „după 0 receptoare”, plafonul circuitelor la ΔU (m-c6), prizele pe
niveluri (N16), VE dimensionat normal (N17), cosφ cu eticheta receptorului (N13)."""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.calc import calculeaza, norme  # noqa: E402
from engine.calc.locuinta import ETICHETE_RECEPTOR, eticheta_receptor  # noqa: E402
from engine import memoriu  # noqa: E402

L = lambda n, r, **k: dict(nume=n, receptor=r, **k)  # noqa: E731
C2 = [L("Il", "iluminat"), L("Pr", "prize")]


def _loc(retea="mono", circuite=C2, **al):
    return {"tip_schema": "locuinta", "retea": retea, "alimentare": al, "circuite": list(circuite)}


def _v(r, cod, nivel=None):
    return [v for v in r["verificari"] + r["info"] if v["cod"] == cod and (nivel is None or v["nivel"] == nivel)]


def _circuite(z):
    return {c["nume"]: c for g in z["grupe_DDR"] for c in g["circuite"]}


def _texte(r):
    return [v["mesaj"] for v in r["verificari"] + r["info"]] + [v.get("remediere") or "" for v in r["verificari"]] \
        + r["presupus"] + r["ipoteze"]


# ------------------------------------------------------------------------------------- 1. M-c1 — Q în afara seriei
@pytest.mark.parametrize("retea,q,q_pres", [("mono", 33, 40), ("mono", 63, 40), ("tri", 33, 40), ("tri", 110, 125)])
def test_Mc1_Q_in_afara_seriei_rezultat_partial(retea, q, q_pres):
    # 33 A → treapta superioară 40 A; 63 A la mono → limita BMPM 40 A; 110 A tri → 125 A (BMPTi-250)
    r = calculeaza(_loc(retea, In_Q_bransament_A=q, P_aprobata_kW=7))
    v05 = _v(r, "V05", "BLOCANT")
    assert len(v05) == 1 and v05[0]["camp"] == "alimentare.In_Q_bransament_A" and f"{q} A" in v05[0]["mesaj"]
    z = r["rezultat"]
    assert z["alimentare"]["Q"]["In_A"] == q_pres and z["alimentare"]["Q_presupus"] is True
    assert len(_circuite(z)) == 2 and z["coloana"]["S_faza_mm2"] > 0
    assert r["blocheaza_export"]
    assert any(f"Q branșament {q} A nu există" in p and f"Q presupus {q_pres} A" in p for p in r["presupus"])
    # V05 acoperă Q-ul invalid: nu se mai spune „Q nedeclarat” (V46 q_pres)
    assert not any("nedeclarat" in v["mesaj"] for v in _v(r, "V46"))


def test_Mc1_Q_in_serie_neschimbat():
    r = calculeaza(_loc("mono", In_Q_bransament_A=32, P_aprobata_kW=7))
    assert not _v(r, "V05") and "Q_presupus" not in r["rezultat"]["alimentare"]


# ------------------------------------------------------------------- 2. m-c4 — Zb / RA / Ik3 invalide → ignorate
@pytest.mark.parametrize("camp,val,eticheta", [("Zb_OD_ohm", -0.2, "impedanța buclei OD = −0,2 Ω"),
                                                 ("Zb_OD_ohm", [0, 0], "impedanța buclei OD"),
                                                 ("Ik3_OD_kA", 0, "Ik3 OD = 0 kA"),
                                                 ("Ik3_OD_kA", "25", "Ik3 OD = „25”"),
                                                 ("RA_ohm", "30", "rezistența prizei de pământ RA = „30”")])
def test_mc4_campuri_globale_invalide_ignorate(camp, val, eticheta):
    d = dict(_loc("mono", In_Q_bransament_A=32, P_aprobata_kW=7), schema_pamant="TT", RA_ohm=30)
    d[camp] = val
    r = calculeaza(d)
    v07 = [v for v in _v(r, "V07", "BLOCANT") if v.get("camp") == camp]
    assert len(v07) == 1 and eticheta in v07[0]["mesaj"] and "se ignoră" in v07[0]["mesaj"]
    assert camp not in v07[0]["mesaj"] and "0.2" not in v07[0]["mesaj"]
    # calculul continuă cu valoarea implicită (presupusă), exportul rămâne refuzat
    z = r["rezultat"]
    assert len(_circuite(z)) == 2 and z["coloana"] and r["blocheaza_export"]
    if camp == "Zb_OD_ohm":
        assert any("impedanța buclei OD = 0,201 Ω (valoare implicită" in x for x in r["ipoteze"])
    if camp == "Ik3_OD_kA":
        assert any("Ik3max la punctul de delimitare = 25 kA (valoare implicită" in x for x in r["ipoteze"])
    if camp == "RA_ohm":
        assert _v(r, "V34", "AVERTISMENT")          # RA 4 Ω presupus


# ---------------------------------------------------------------------- 3. N11 — Zb rurală presupusă, nu „din ATR”
def test_N11_zb_rurala_presupusa_nu_din_ATR():
    r = calculeaza(dict(_loc("tri", In_Q_bransament_A=25, P_aprobata_kW=10, zona="rural"), schema_pamant="TT", RA_ohm=30))
    ip = [x for x in r["ipoteze"] if x.startswith("impedanța buclei OD")]
    assert ip == ["impedanța buclei OD = 0,45 Ω presupus (zonă rurală, [NEVERIFICAT]) — se confirmă cu OD / ATR"]
    assert not any("(din ATR)" in t for t in _texte(r))
    assert any("0,45 Ω (zonă rurală) — presupus" in p and "OD / ATR" in p for p in r["presupus"])
    h = memoriu.genereaza_html({"calc": {}}, r)
    assert "(din ATR)" not in h and "presupus (zonă rurală, [NEVERIFICAT])" in h


def test_N11_valorile_declarate_si_implicite():
    r = calculeaza(dict(_loc("mono", In_Q_bransament_A=32, P_aprobata_kW=7), Zb_OD_ohm=0.3, Ik3_OD_kA=10))
    assert "impedanța buclei OD = 0,3 Ω (declarat)" in r["ipoteze"]
    assert "Ik3max la punctul de delimitare = 10 kA (declarat)" in r["ipoteze"]
    r = calculeaza(_loc("mono", In_Q_bransament_A=32, P_aprobata_kW=7))
    assert any(x.startswith("impedanța buclei OD = 0,201 Ω (valoare implicită, presupusă — se confirmă cu OD / ATR")
               for x in r["ipoteze"])


# ------------------------------------------------------------------------- 4. M-c3 — VE sub DDR tip AC al branșamentului
VE = [L("Il", "iluminat"), L("VE", "vehicul_electric", P_kW=7.4)]


def test_Mc3_VE_sub_RCBO_BMPM_tip_AC_avertisment():
    r = calculeaza(_loc("mono", VE, In_Q_bransament_A=40, P_aprobata_kW=9))
    v = [x for x in _v(r, "V43") if "c.c." in x["mesaj"]]
    assert len(v) == 1 and v[0]["nivel"] == "AVERTISMENT" and v[0]["obiect"].endswith("vs RCBO BMPM")
    assert "tip AC" in v[0]["mesaj"] and "531.3.2" in v[0]["mesaj"] and "722.531.3.101" in v[0]["mesaj"]
    assert "tip B" in v[0]["remediere"] and v[0]["camp"] == "alimentare.DDR_bransament_tip"
    assert r["rezultat"]["alimentare"]["DDR_bransament_tip"] == "AC"
    assert any("tip AC" in p and "DDR-ul din branșament" in p for p in r["presupus"])


def test_Mc3_TT_blocant_si_remedieri():
    tt = dict(schema_pamant="TT", RA_ohm=30)
    r = calculeaza(dict(_loc("tri", VE, In_Q_bransament_A=32, P_aprobata_kW=15), **tt))
    v = [x for x in _v(r, "V43") if "c.c." in x["mesaj"]]
    assert len(v) == 1 and v[0]["nivel"] == "BLOCANT" and "RCCB BMPT" in v[0]["obiect"] and "TT" in v[0]["mesaj"]
    # DDR-ul din branșament declarat tip B → nimic
    r = calculeaza(dict(_loc("tri", VE, In_Q_bransament_A=32, P_aprobata_kW=15, DDR_bransament_tip="b"), **tt))
    assert not [x for x in _v(r, "V43") if "c.c." in x["mesaj"]] and r["rezultat"]["alimentare"]["DDR_bransament_tip"] == "B"
    # amonte tip A + VE tip A (stație cu RDC-DD 6 mA): c.c. limitat la 6 mA → în regulă (rămâne V49 „ve_tip” AV)
    ve_a = [L("Il", "iluminat"), L("VE", "vehicul_electric", P_kW=11, DDR={"IdN_mA": 30, "tip": "A"})]
    r = calculeaza(dict(_loc("tri", ve_a, In_Q_bransament_A=32, P_aprobata_kW=15, DDR_bransament_tip="A"), **tt))
    assert not [x for x in _v(r, "V43") if "c.c." in x["mesaj"]] and _v(r, "V49", "AVERTISMENT")
    # amonte A + VE tip B (fără limitarea c.c.) → tot BLOCANT în TT
    r = calculeaza(dict(_loc("tri", VE, In_Q_bransament_A=32, P_aprobata_kW=15, DDR_bransament_tip="A"), **tt))
    assert [x["nivel"] for x in _v(r, "V43") if "c.c." in x["mesaj"]] == ["BLOCANT"]
    # tip necunoscut → V12 BLOCANT cu `camp`, câmpul ignorat (AC implicit)
    r = calculeaza(_loc("mono", VE, In_Q_bransament_A=40, P_aprobata_kW=9, DDR_bransament_tip="X"))
    v12 = [x for x in _v(r, "V12", "BLOCANT") if x.get("camp") == "alimentare.DDR_bransament_tip"]
    assert v12 and "DDR_bransament_tip" not in v12[0]["mesaj"]


def test_Mc3_fara_VE_fara_verificare():
    r = calculeaza(_loc("mono", In_Q_bransament_A=32, P_aprobata_kW=7))
    assert not [x for x in _v(r, "V43") if "c.c." in x["mesaj"]]
    assert not any("DDR-ul din branșament" in p for p in r["presupus"])


# --------------------------------------------------------------------------------- 5. m-c5 / C3 — fără chei interne
def test_mc5_fara_chei_interne_in_mesaje_si_presupuneri():
    circ = [L("Bucătărie", "prize_bucatarie"), L("Plită", "plita"), L("Baie", "prize_baie", DDR=False),
            L("VE", "vehicul_electric", DDR={"IdN_mA": 30, "tip": "AC"}), L("Hidrofor", "pompa_apa"), L("X", None)]
    r = calculeaza(dict(_loc("mono", circ, In_Q_bransament_A=40), schema_pamant="TT", RA_ohm=400))
    rx = re.compile(r"\b(" + "|".join(k for k in ETICHETE_RECEPTOR if "_" in k) + r"|IdN_amonte_mA|RA_ohm|Zb_OD_ohm)\b")
    gasite = [t for t in _texte(r) if rx.search(t) or "„plita”" in t]
    assert not gasite, gasite
    t = " | ".join(r["presupus"])
    assert "Prize bucătărie: P = 2,5 kW" in t and "Plită: lungime circuit 15 m" in t and "„Alt circuit”" in t
    v49 = [v["mesaj"] for v in _v(r, "V49")]
    assert _v(r, "V29", "BLOCANT")             # prize baie fără DDR
    assert any("„Încărcător vehicul electric”" in m or "„Pompă apă / hidrofor”" in m for m in v49)
    # V34 TT: remedierea nu mai cere câmpul inexistent „IdN_amonte_mA”
    assert all("IΔn al DDR-ului din amonte" not in v["remediere"] and "RA" in v["remediere"] for v in _v(r, "V34"))
    # memoriu: denumirea receptorului, nu cheia
    h = memoriu.genereaza_html({"calc": {}}, r)
    assert "Prize bucătărie" in h and "prize_bucatarie" not in h
    assert _circuite(r["rezultat"])["Bucătărie"]["receptor_eticheta"] == "Prize bucătărie"
    assert eticheta_receptor("vehicul_electric") == "Încărcător vehicul electric"


def test_mc5_retea_si_zona_mesaje():
    r = calculeaza(_loc(3, In_Q_bransament_A=32))
    v = _v(r, "V12", "BLOCANT")[0]
    assert "sursă de putere" not in v["remediere"] and "mono" in v["remediere"] and v["camp"] == "retea"
    r = calculeaza(_loc("mono", In_Q_bransament_A=32, zona="munte"))
    m = [v["mesaj"] for v in _v(r, "V12") if v.get("camp") == "alimentare.zona"][0]
    assert m.count("(urban / rural)") == 1
    r = calculeaza(_loc("mono", In_Q_bransament_A=32, P_aprobata_kW="7"))
    v = [v for v in _v(r, "V07") if v.get("camp") == "alimentare.P_aprobata_kW"][0]
    assert "nenumerică" in v["mesaj"] and not any(x.get("camp") == "alimentare.P_aprobata_kW" for x in _v(r, "V46"))
    r = calculeaza(_loc("mono", In_Q_bransament_A=32, L_coloana_m=0))
    assert [v.get("camp") for v in _v(r, "V09", "BLOCANT")] == ["alimentare.L_coloana_m"]


# ----------------------------------------------------------------------------------------- 6. nota ks fără 0 receptoare
def test_ks_numai_sarcini_continue():
    r = calculeaza(_loc("tri", [L("VE", "vehicul_electric"), L("PC", "pompa_caldura")], In_Q_bransament_A=32,
                        P_aprobata_kW=20))
    assert not any("după 0" in p or "0 receptoare" in p for p in r["presupus"])
    assert any("numai sarcini continue" in p and "ks = 1" in p for p in r["presupus"])
    b = r["rezultat"]["bilant"]
    assert b["ks"] == 1 and b["Pc_kW"] == pytest.approx(b["Pi_kW"])
    r = calculeaza(_loc("mono", [L("Il", "iluminat")], In_Q_bransament_A=32, P_aprobata_kW=7))
    assert any("ks după 1 receptor general" in p for p in r["presupus"])


# ------------------------------------------------------------------------- 7. m-c6 — plafonul circuitelor finale la ΔU
def test_mc6_coloana_impusa_circuitele_plafonate():
    # verificator „buget_S_fortat_col”: coloana 6 mm² impusă, 60 m → ΔU la bară 5,89 % (V20 bară); circuitele de 50 m
    # nu mai urcă la 4 × 240 mm², ci rămân la plafonul de 16 mm², cu V20 BLOCANT „mărește coloana”
    r = calculeaza(_loc("mono", [L("Il", "iluminat", L_m=50), L("Pr", "prize", L_m=50)], In_Q_bransament_A=32,
                        P_aprobata_kW=7, L_coloana_m=60, cablu={"S_fortat": 6}))
    c = _circuite(r["rezultat"])
    for n in ("Il", "Pr"):
        assert c[n]["S_faza_mm2"] <= norme.LOCUINTA_S_MAX_CIRCUIT_DU_MM2 and (c[n].get("n_paralel") or 1) == 1
        assert c[n]["dU_plafonat_mm2"] == norme.LOCUINTA_S_MAX_CIRCUIT_DU_MM2
    v20 = [v for v in _v(r, "V20", "BLOCANT") if v["obiect"] in ("C1·Il", "C2·Pr")]
    assert len(v20) == 2 and all("mărește coloana" in v["remediere"] and "plafonată" in v["mesaj"] for v in v20)
    assert r["blocheaza_export"]


def test_mc6_circuit_lung_fara_plafon_atins():
    # circuitul de 60 m crește normal (2,5 mm²), fără marcaj de plafon
    r = calculeaza(_loc("mono", [L("Il", "iluminat", L_m=60), L("Pr", "prize", L_m=55)], In_Q_bransament_A=32,
                        P_aprobata_kW=7, L_coloana_m=25))
    c = _circuite(r["rezultat"])
    assert c["Il"]["S_faza_mm2"] == 2.5 and "dU_plafonat_mm2" not in c["Il"] and not r["blocheaza_export"]


# ------------------------------------------------------------------------------------- 8. N16 — prizele pe niveluri
def test_N16_prize_pe_niveluri_separate():
    circ = [L("Prize living parter", "prize"), L("Prize hol parter", "prize"), L("Prize dormitor 1 etaj", "prize"),
            L("Prize dormitor 2 etaj", "prize"), L("Prize dormitor 3 etaj", "prize"), L("Prize birou", "prize")]
    r = calculeaza(_loc("tri", circ, In_Q_bransament_A=32, P_aprobata_kW=15))
    gr = [[c["nume"] for c in g["circuite"]] for g in r["rezultat"]["grupe_DDR"] if g["grupa"] == "general"]
    for g in gr:
        niv = {("parter" if "parter" in n else "etaj") for n in g if "parter" in n or "etaj" in n}
        assert len(niv) <= 1, g
    # circuitul fără nivel completează lotul cel mai mic (parter: 2 circuite)
    assert ["Prize living parter", "Prize hol parter", "Prize birou"] in gr


def test_N16_fara_niveluri_neschimbat():
    circ = [L(f"Prize {i}", "prize") for i in range(1, 7)]
    r = calculeaza(_loc("mono", circ, In_Q_bransament_A=32, P_aprobata_kW=7))
    gr = [len(g["circuite"]) for g in r["rezultat"]["grupe_DDR"] if g["grupa"] == "general"]
    assert gr == [3, 3]                     # ⌈6/5⌉ = 2 grupe cât mai egale, ca în v1.6


# ------------------------------------------------------------------------------------- 9. N17 — VE dimensionat normal
def test_N17_VE_dimensionat_normal():
    # 11 kW 3F: Ib 15,9 A → C20; minimul VE 4 mm² (nu 6 fix); 7,4 kW mono: C40 → Iz cere 10 mm² B2
    r = calculeaza(_loc("tri", [L("VE", "vehicul_electric", P_kW=11)], In_Q_bransament_A=32, P_aprobata_kW=15))
    ve = _circuite(r["rezultat"])["VE"]
    assert ve["protectie"]["In_A"] == 20 and ve["S_faza_mm2"] == 4
    assert any("minimum 4 mm²" in p and "rezervă" in p for p in r["presupus"])
    r = calculeaza(_loc("mono", [L("VE", "vehicul_electric")], In_Q_bransament_A=40, P_aprobata_kW=9))
    ve = _circuite(r["rezultat"])["VE"]
    assert ve["protectie"]["In_A"] == 40 and ve["S_faza_mm2"] == 10
    # VE lung: crește pentru ΔU ca orice circuit
    r = calculeaza(_loc("tri", [L("VE", "vehicul_electric", P_kW=11, L_m=120)], In_Q_bransament_A=32, P_aprobata_kW=15))
    ve = _circuite(r["rezultat"])["VE"]
    assert ve["S_faza_mm2"] > 4 and ve["dU_cumulat_pct"] <= 5


# ------------------------------------------------------------------------------- 10. N13 — cosφ cu eticheta receptorului
def test_N13_cosfi_in_ipoteze_cu_receptor_si_presupus():
    circ = [L("Il", "iluminat"), L("Pr", "prize"), L("Plită", "plita"), L("Hidrofor", "pompa_apa", cosfi=0.8)]
    r = calculeaza(_loc("mono", circ, In_Q_bransament_A=40, P_aprobata_kW=9))
    cos = [x for x in r["ipoteze"] if x.startswith("cosφ")]
    assert len(cos) == 1
    assert "0,9 (Iluminat, Prize) (presupus)" in cos[0] and "1 (Plită) (presupus)" in cos[0]
    assert "0,8 (Pompă apă / hidrofor) (declarat)" in cos[0]
    assert "0,95 (coloana C2, cosφ mediu al locuinței) (presupus)" in cos[0]
    h = memoriu.genereaza_html({"calc": {}}, r)
    assert "0,9 (Iluminat, Prize) (presupus)" in h and "0,95 (declarat)" not in h
