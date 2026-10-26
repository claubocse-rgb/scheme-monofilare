"""Regresie R5 „fotovoltaic” (teste/r5/fotovoltaic.md + prosumator din locuinte.md): CEF / prosumator / BESS,
intrare fizică directă (fără interpretor)."""
import os
import sys

import pytest

RAD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAD)

from engine import constructor, layout  # noqa: E402
from engine.calc import calculeaza  # noqa: E402
from engine.topologie import coliziuni  # noqa: E402


def _toate(m):
    out = []

    def br(b):
        for a in b.get("aparate") or []:
            out.append(a)
            out.extend(a.get("laterale") or [])
        for c in b.get("copii") or []:        # r6: PT nou al CEF = tablou secundar al plecării C0
            br(c)
    for b in (m.get("intrari") or []) + (m.get("plecari") or []):
        br(b)
    return out


def _coduri(r, nivel=None):
    return {(v["cod"], v["obiect"]) for v in r["verificari"] + r["info"] if nivel is None or v["nivel"] == nivel}


def _av(r, cod):
    return [v for v in r["verificari"] if v["cod"] == cod and v["nivel"] == "AVERTISMENT"]


def _gen(inp):
    m, r = constructor.genereaza(inp)
    assert coliziuni(layout.build(m)) == []
    return m, r


# ---------------------------------------------------------------- 1. prosumator cu mai multe invertoare + BESS
def test_f28_prosumator_2_invertoare_si_bess_ca():
    inp = {"tip_schema": "prosumator", "retea": "tri", "invertoare": [{"n": 2, "Pn_kW": 125}],
           "bess": {"P_kW": 100, "kWh": 200}, "limitare_injectie_kW": 150}
    m, r = _gen(inp)
    z = r["rezultat"]
    assert [i["obiect"] for i in z["invertoare"]] == ["INV-1", "INV-2"] and z["PCS"]["Pn_kW"] == 100
    assert z["BESS"]["cuplaj"] == "ca"
    refs = {a.get("ref") for a in _toate(m)}
    assert {"INV-1", "INV-2", "PCS", "BAT", "SB-B", "FB.2", "Q1", "Q2", "QB"} <= refs
    assert [b["sursa"]["titlu"] for b in m["intrari"]] == ["CÂMP PV 1", "CÂMP PV 2", "BESS"]
    # DDR 30 mA nu se pune pe invertoarele de 125 kW (P0-6)
    assert not any(i.get("DDR") for i in z["invertoare"]) and not any(a["tip"] == "rccb" for a in _toate(m))


def test_f22_prosumator_invertoare_diferite_alias_pn_inv():
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 30,
                    "invertoare": [{"n": 1, "Pn_kW": 20, "producator": "Fronius", "model": "Symo 20.0-3-M"},
                                   {"n": 1, "Pn_kW": 10, "producator": "Fronius", "model": "Symo 10.0-3-M"}]})
    z = r["rezultat"]
    assert [i["Pn_kW"] for i in z["invertoare"]] == [20, 10] and not _av(r, "V91")
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 40, "invertoare": [{"n": 2, "Pn_kW": 10}]})
    assert _av(r, "V91")


def test_pn_inv_kw_ramane_alias_pentru_un_invertor():
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 10, "In_Q_bransament_A": 25})
    z = r["rezultat"]
    assert z["INV"]["obiect"] == "INV" and z["INV"]["DDR"]["IdN_mA"] == 30 and len(z["invertoare"]) == 1


# ---------------------------------------------------------------- 2. baterie pe portul invertorului hibrid
def test_l27_baterie_pe_port_separat_nu_in_serie():
    inp = {"tip_schema": "prosumator", "retea": "tri", "In_Q_bransament_A": 32,
           "invertoare": [{"n": 1, "Pn_kW": 10, "producator": "Huawei", "model": "SUN2000-10KTL-M1", "hibrid": True}],
           "bess": {"producator": "Huawei", "model": "LUNA2000-10", "kWh": 10, "U_nom_V": 450}}
    m, r = _gen(inp)
    z = r["rezultat"]
    assert z["BESS"]["cuplaj"] == "cc" and z["BESS"]["la"] == "INV" and z["BESS"]["protectie_cc"]["In_A"] == 32
    lant = [a["tip"] for a in m["intrari"][0]["aparate"]]
    assert "baterie" not in lant                                # nu în serie pe linia c.c. PV → invertor
    inv = next(a for a in m["intrari"][0]["aparate"] if a["tip"] == "invertor")
    lat = {l["ref"]: l for l in inv["laterale"]}
    assert lat["FB"]["legatura"] == "forta" and lat["BAT"]["legatura"] == "forta"
    assert "LUNA2000-10" in lat["BAT"]["lista"][0] and "hibrid" in inv["lista"][0]
    assert not any(b["sursa"]["titlu"] == "BESS" for b in m["intrari"])


def test_bess_cef_are_spd_cc_si_separator_intre_baterie_si_pcs():
    m, r = _gen({"tip_schema": "cef", "kWp": 300, "invertoare": [{"n": 3, "Pn_kW": 100}],
                 "bess": {"producator": "Huawei", "model": "LUNA2000-215", "P_kW": 100, "kWh": 215}})
    b = next(x for x in m["intrari"] if x["sursa"]["titlu"] == "BESS")
    tipuri = [a["tip"] for a in b["aparate"]]
    assert tipuri.index("baterie") < tipuri.index("separator_cc") < tipuri.index("convertor_bess")
    sep = b["aparate"][tipuri.index("separator_cc")]
    assert any(l["tip"] == "spd_cc" for l in sep["laterale"])
    assert "LUNA2000-215" in b["aparate"][0]["lista"][0]


# ---------------------------------------------------------------- 3. TG existent / PT existent
@pytest.mark.parametrize("inp", [
    {"tip_schema": "cef", "kWp": 300, "invertoare": [{"n": 3, "Pn_kW": 100}], "bess": {"P_kW": 100, "kWh": 200},
     "racord": "tg_existent", "L_racord_m": 80, "pt_Sn_kVA": 630},                                      # f31
    {"tip_schema": "cef", "kWp": 600, "invertoare": [{"n": 5, "Pn_kW": 110}], "pt_Sn_kVA": 1000,
     "racord": "tg_existent"},                                                                          # f45
    {"tip_schema": "cef", "kWp": 400, "invertoare": [{"n": 4, "Pn_kW": 100}], "pt_Sn_kVA": 1000, "pt_existent": True},
], ids=["f31", "f45", "pt_existent"])
def test_fara_trafo_in_serie_la_pt_existent(inp):
    m, r = _gen(inp)
    assert r["rezultat"]["trafo"]["existent"] is True
    assert not any(a["tip"] == "trafo" for a in _toate(m))
    assert "EXISTENT" in m["plecari"][0]["sarcina"]["titlu"]


def test_pt_propriu_nou_ramane_desenat():
    m, r = _gen({"tip_schema": "cef", "kWp": 400, "invertoare": [{"n": 4, "Pn_kW": 100}], "pt_Sn_kVA": 630})
    assert any(a["tip"] == "trafo" for a in _toate(m))


def test_q_tg_electronic_nu_mai_da_eroare_interna():
    r = calculeaza({"tip_schema": "cef", "kWp": 600, "invertoare": [{"n": 5, "Pn_kW": 110}], "racord": "tg_existent",
                    "pt_Sn_kVA": 1000, "L_racord_m": 40, "racord_In_Q_A": 1000, "Ik3_TG_kA": 20})
    assert not any(v["cod"] == "V07" for v in r["verificari"]) and r["rezultat"]["Q_TG"]["In_A"] == 1000


# ---------------------------------------------------------------- 4. DDR
def test_ddr_doar_unde_e_cerut():
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 100})
    assert "DDR" not in r["rezultat"]["INV"] and not any(v["cod"] == "V73" for v in r["verificari"])
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "invertoare": [{"n": 1, "Pn_kW": 100,
                    "ddr": {"IdN_mA": 300, "tip": "B"}}]})
    assert r["rezultat"]["INV"]["DDR"]["IdN_mA"] == 300 and r["rezultat"]["INV"]["DDR"]["tip"] == "B"
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "invertoare": [{"n": 1, "Pn_kW": 8, "IdN_min_mA": 100}]})
    assert r["rezultat"]["INV"]["DDR"]["IdN_mA"] == 100
    # TT: invertor mare → 100 mA (nu 30 mA)
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 50, "schema_pamant": "TT", "RA_ohm": 10})
    assert r["rezultat"]["INV"]["DDR"]["IdN_mA"] == 100
    # CEF în TN: fără DDR; declarat pe grup → desenat
    m, r = _gen({"tip_schema": "cef", "kWp": 120, "invertoare": [{"n": 1, "Pn_kW": 100, "ddr": {"IdN_mA": 300}}]})
    assert r["rezultat"]["invertoare"][0]["DDR"]["IdN_mA"] == 300 and any(a.get("ref") == "DDR1" for a in _toate(m))
    r = calculeaza({"tip_schema": "cef", "kWp": 120, "invertoare": [{"n": 1, "Pn_kW": 100, "ddr": {"IdN_mA": 30}}]})
    assert any(v["cod"] == "V73" and v["obiect"] == "INV-1" for v in r["verificari"])


# ---------------------------------------------------------------- 5. monofazat / rețea nepresupusă în tăcere
def test_f35_cef_monofazat_respectat():
    r = calculeaza({"tip_schema": "cef", "kWp": 100, "retea": "mono", "invertoare": [{"n": 2, "Pn_kW": 50}]})
    assert r["rezultat"]["retea"] == "mono" and ("V53", "schema") in _coduri(r, "BLOCANT")
    r = calculeaza({"tip_schema": "cef", "kWp": 100, "invertoare": [{"n": 2, "Pn_kW": 50}]})
    assert any("rețea trifazată" in p for p in r["presupus"])


# ---------------------------------------------------------------- 6. SPD c.a. la invertor, limitarea injecției
def test_spd_ca_la_invertor_peste_10_m():
    m, r = _gen({"tip_schema": "cef", "kWp": 120, "invertoare": [{"n": 1, "Pn_kW": 100, "L_m": 40},
                                                                 {"n": 1, "Pn_kW": 20, "L_m": 8}]})
    inv = r["rezultat"]["invertoare"]
    assert inv[0]["SPD_ca_invertor"]["tip"] == "T2" and "SPD_ca_invertor" not in inv[1]
    refs = {a.get("ref") for a in _toate(m)}
    assert "F1.3" in refs and "F2.3" not in refs


@pytest.mark.parametrize("inp", [
    {"tip_schema": "cef", "kWp": 100, "invertoare": [{"n": 2, "Pn_kW": 50}], "bess": {"P_kW": 50, "kWh": 100},
     "L_racord_m": 50, "limitare_injectie_kW": 0},                                                        # f46
    {"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 100, "limitare_injectie_kW": 30},          # f27
    {"tip_schema": "prosumator", "retea": "tri", "invertoare": [{"n": 4, "Pn_kW": 100}], "limitare_injectie_kW": 0},  # f23
], ids=["f46", "f27", "f23"])
def test_limitare_injectie_analizor_ems_si_comanda(inp):
    m, r = _gen(inp)
    li = r["rezultat"]["limitare_injectie"]
    assert li["P_kW"] == inp["limitare_injectie_kW"] and ("V92", "schema") in _coduri(r)
    toate = _toate(m)
    assert any(a.get("ref") == "TCA" for a in toate) and any(a.get("ref") == "AR" for a in toate)
    assert any(a.get("ref") == "EMS" for a in toate)
    n_cmd = sum(1 for a in toate if a.get("eticheta") == "EMS" and a.get("legatura") == "comanda")
    assert n_cmd == li["n_comandate"]


# ---------------------------------------------------------------- 7. prosumator comercial
def test_f21_prosumator_comercial_nu_e_tablou_de_casa():
    m, r = _gen({"tip_schema": "prosumator", "retea": "tri", "kWp": 120, "racord": "tg_existent",
                 "invertoare": [{"n": 2, "Pn_kW": 50, "producator": "Huawei", "model": "SUN2000-50KTL-M3"}],
                 "limitare_injectie_kW": 50})
    z = r["rezultat"]
    assert z["comercial"] and z["PI_externa"] and z["QG"]["In_A"] >= z["Iac_max_A"]   # > 27 kW: releu anti-insularizare (cerință OD)
    titluri = [p["sarcina"]["titlu"] for p in m["plecari"]]
    assert not {"Iluminat", "Prize"} & set(titluri) and titluri == ["TG EXISTENT"]
    assert m["carcasa"]["titlu"] == "TD-PV"


def test_prosumator_mare_pi_externa():
    m, r = _gen({"tip_schema": "prosumator", "retea": "tri", "invertoare": [{"n": 2, "Pn_kW": 125}]})
    assert r["rezultat"]["PI_externa"] and "externă" in r["rezultat"]["PI"]
    qg = next(a for a in m["plecari"][0]["aparate"] if a.get("ref") == "QG")
    assert any(l.get("eticheta") == "PI" and l.get("legatura") == "comanda" for l in qg["laterale"])
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 150, "PI_externa": False})
    assert not r["rezultat"]["PI_externa"]


def test_prosumator_casa_ramane_te():
    m, r = _gen({"tip_schema": "prosumator", "retea": "mono", "Pn_inv_kW": 5, "In_Q_bransament_A": 32})
    assert m["carcasa"]["titlu"] == "TE" and any(p["sarcina"]["titlu"] == "Prize" for p in m["plecari"])


# ---------------------------------------------------------------- 8. BESS de sine stătător
@pytest.mark.parametrize("tip", ["bess", "cef"])
def test_f33_bess_singur_acceptat(tip):
    m, r = _gen({"tip_schema": tip, "racord": "tg_existent", "pt_Sn_kVA": 1000, "L_racord_m": 40,
                 "bess": {"producator": "Sungrow", "model": "PowerStack 255CS", "P_kW": 500, "kWh": 1000}})
    assert r["rezultat"]["bess_singur"] and not r["blocheaza_export"]
    assert m["cartus"]["denumire2"].startswith("BESS 500 kW")
    assert [b["sursa"]["titlu"] for b in m["intrari"]] == ["BESS"]


# ---------------------------------------------------------------- 9. date declarate respectate
def test_f37_q_ik_tg_si_cablu_cu():
    r = calculeaza({"tip_schema": "cef", "kWp": 250, "invertoare": [{"n": 2, "Pn_kW": 100}], "racord": "tg_existent",
                    "L_racord_m": 30, "racord_In_Q_A": 250, "Ik3_TG_kA": 15, "cablu": {"material": "Cu"}})
    z = r["rezultat"]
    assert z["Q_TG"]["In_A"] == 250 and z["C0"]["Ik3max_origine_kA"] == pytest.approx(15, rel=0.03)
    assert z["C0"]["material"] == "Cu" and all(i["material"] == "Cu" for i in z["invertoare"])


def test_f19_cablu_c0_impus():
    r = calculeaza({"tip_schema": "cef", "kWp": 160, "invertoare": [{"n": 1, "Pn_kW": 125}], "racord": "tg_existent",
                    "L_racord_m": 60, "cablu_C0": {"material": "Al", "S_fortat": 150, "n_fortat": 3}})
    c0 = r["rezultat"]["C0"]
    assert c0["S_faza_mm2"] == 150 and c0["n_paralel"] == 3 and c0["material"] == "Al"


@pytest.mark.parametrize("spl,ra", [("TN-C-S", None), ("TT", 4)])
def test_f05_f42_schema_pamant_cef(spl, ra):
    inp = {"tip_schema": "cef", "kWp": 200, "invertoare": [{"n": 2, "Pn_kW": 100}], "schema_pamant": spl}
    if ra:
        inp.update(RA_ohm=ra, IdN_amonte_mA=300)        # racord direct din PT OD: DDR-ul din amonte se declară
    m, r = _gen(inp)
    assert r["rezultat"]["schema_pamant"] == spl and not r["blocheaza_export"]
    nota = " ".join(m["note"])
    assert ("TT" in nota and "RA" in nota) if spl == "TT" else "separarea PEN" in nota
    if spl == "TT":
        assert r["rezultat"]["invertoare"][0]["DDR"]["IdN_mA"] >= 100


def test_f06_f43_stringuri_si_gpv_declarate_pe_plansa():
    m, r = _gen({"tip_schema": "cef", "kWp": 52, "invertoare": [{"n": 1, "Pn_kW": 50}],
                 "string": {"n_module": 18, "n_stringuri_paralel": 5, "gpv_In_A": 15}})
    assert not r["blocheaza_export"] and r["rezultat"]["gPV_In_A"] == 15
    a = {x.get("ref"): x for x in _toate(m)}
    assert a["F1.1"]["param"]["In_A"] == 15 and "5 str. × 18 mod." in m["intrari"][0]["sursa"]["sub"]
    # cu Isc din fișă, calibrul declarat se verifică
    r = calculeaza({"tip_schema": "cef", "kWp": 52, "invertoare": [{"n": 1, "Pn_kW": 50}],
                    "string": {"n_module": 18, "Uoc_V": 49.5, "n_stringuri_paralel": 3, "Isc_A": 13.9, "gpv_In_A": 15}})
    assert ("V69", "schema") in _coduri(r, "BLOCANT")


# ---------------------------------------------------------------- 10. contradicții de putere
def test_f36_contradictie_putere_v91():
    r = calculeaza({"tip_schema": "cef", "kWp": 120, "invertoare": [{"n": 3, "Pn_kW": 50}], "Pn_total_kW": 100})
    assert _av(r, "V91") and "150" in _av(r, "V91")[0]["mesaj"]
    r = calculeaza({"tip_schema": "cef", "kWp": 120, "invertoare": [{"n": 2, "Pn_kW": 50}], "Pn_total_kW": 100})
    assert not _av(r, "V91")


@pytest.mark.parametrize("pn,ext", [(27, False), (27.5, True), (30, True), (10, False)])
def test_prag_27kw_tablou_cu_releu_antiinsularizare(pn, ext):
    """OD: prosumatorii > 27 kW cer tablou (TD-PV) cu releu anti-insularizare (PI externă pe QG)"""
    m, r = _gen({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": pn})
    z = r["rezultat"]
    assert bool(z["PI_externa"]) is ext and bool(z["comercial"]) is ext
    if ext:
        assert m["carcasa"]["titlu"] == "TD-PV" and "externă" in m["carcasa"]["sub"]
        assert any(l.get("eticheta") == "PI" for p in m["plecari"] for a in p["aparate"] for l in a.get("laterale") or [])
