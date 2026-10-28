"""Regresie R6 „fotovoltaic” (teste/r6/fotovoltaic.md + prosumator din teste/r6/locuinte.md): CEF cu PT nou / existent,
TT, BESS cuplat în c.c., baterie la prosumator, gPV pe stringuri, Iac vs Q existent, modele din catalog.
Intrare fizică directă (fără interpretor)."""
import os
import re
import sys

import pytest

RAD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAD)

from engine import constructor, layout, render_svg  # noqa: E402
from engine.calc import calculeaza  # noqa: E402
from engine.calc import catalog_invertoare as cat  # noqa: E402
from engine.topologie import coliziuni  # noqa: E402


def _toate(m, cu_copii=True):
    out = []

    def br(b):
        for a in b.get("aparate") or []:
            out.append(a)
            out.extend(a.get("laterale") or [])
        if cu_copii:
            for c in b.get("copii") or []:
                br(c)
    for b in (m.get("intrari") or []) + (m.get("plecari") or []):
        br(b)
    return out


def _gen(inp):
    m, r = constructor.genereaza(inp)
    assert coliziuni(layout.build(m)) == []
    return m, r


def _cod(r, cod, nivel=None):
    return [v for v in r["verificari"] + r.get("info", []) if v["cod"] == cod and (nivel is None or v["nivel"] == nivel)]


def _txt(m):
    s = render_svg.render(layout.build(m), "t")
    return " | ".join(t.strip() for t in re.findall(r">([^<>]+)<", s) if t.strip())


# ---------------------------------------------------------------- P0-2: CEF cu PT propriu nou (toate cazurile din raport)
PT_NOU = {
    "f04": {"pt_Sn_kVA": 400, "kWp": 330, "invertoare": [{"n": 3, "Pn_kW": 100, "producator": "Huawei", "model": "SUN2000-100KTL-M2"}], "L_racord_m": 120},
    "f07": {"pt_Sn_kVA": 1000, "kWp": 800, "invertoare": [{"n": 6, "Pn_kW": 125, "producator": "Sungrow", "model": "SG125CX-P2"}]},
    "f08": {"pt_Sn_kVA": 1250, "pt_existent": False, "kWp": 1100, "invertoare": [{"n": 8, "Pn_kW": 125}], "L_racord_m": 250},
    "f09": {"pt_Sn_kVA": 1600, "kWp": 1300, "invertoare": [{"n": 10, "Pn_kW": 115}]},
    "f22": {"pt_Sn_kVA": 800, "kWp": 500, "invertoare": [{"n": 4, "Pn_kW": 110}], "bess": {"kWh": 257, "P_kW": 125, "producator": "Sungrow", "model": "PowerStack 255CS"}},
    "f24": {"pt_Sn_kVA": 2000, "kWp": 1000, "invertoare": [{"n": 8, "Pn_kW": 125}], "bess": {"kWh": 1000, "P_kW": 500}, "limitare_injectie_kW": 600},
    "f27": {"pt_Sn_kVA": 1250, "bess": {"kWh": 2000, "P_kW": 1000, "producator": "Sungrow", "model": "PowerStack"}},
    "f48": {"pt_Sn_kVA": 250, "kWp": 300, "invertoare": [{"n": 3, "Pn_kW": 100}]},
    "r5_04": {"pt_Sn_kVA": 400, "kWp": 400, "invertoare": [{"n": 4, "Pn_kW": 100}]},
    "r5_09": {"pt_Sn_kVA": 2000, "kWp": 2500, "invertoare": [{"n": 20, "Pn_kW": 100}]},
    "r5_16": {"pt_Sn_kVA": 630, "kWp": 350, "invertoare": [{"n": 3, "Pn_kW": 100}, {"n": 1, "Pn_kW": 50}], "bess": {"kWh": 430, "P_kW": 200, "producator": "Sungrow", "model": "PowerStack"}},
    "r5_32": {"pt_Sn_kVA": 1000, "kWp": 400, "invertoare": [{"n": 4, "Pn_kW": 100}], "bess": {"kWh": 1000, "P_kW": 500}},
    "r5_39": {"racord": "pt", "pt_Sn_kVA": 1250, "kWp": 1200, "invertoare": [{"n": 10, "Pn_kW": 100}], "L_racord_m": 150},
    "r5_40": {"racord": "pt", "pt_Sn_kVA": 630, "kWp": 500, "invertoare": [{"n": 5, "Pn_kW": 100}], "L_racord_m": 100},
}


@pytest.mark.parametrize("cid", sorted(PT_NOU))
def test_pt_nou_topologie(cid):
    m, r = _gen(dict(PT_NOU[cid], tip_schema="cef", retea="tri"))
    z = r["rezultat"]
    # T1 nu mai e în TGD-CF (aparatele plecării din carcasa principală)
    assert not any(a["tip"] == "trafo" for a in _toate(m, cu_copii=False))
    if r["blocheaza_export"]:          # f48: PT 250 kVA < S CEF → V67 (întrebare), fără desen de PT
        assert _cod(r, "V67", "BLOCANT")
        return
    assert "nou" in z["racord"]["tip"] and z["PT"]["Q_JT"]["In_A"] >= z["PT"]["In_T_A"] * 0.95
    pl = m["plecari"][0]
    assert pl["sarcina"]["titlu"].startswith("PT ") and pl.get("pt")
    pt = pl["copii"][0]
    # echipa1 P1-9: PT propriu nou = racord MT — celula de măsură QM și întreruptorul de interfață QI (PI 59N) pe MT
    assert {"QM", "QI"} <= {a.get("ref") for a in pt["aparate"]} and z["masura"]["loc"] == "MT"
    tipuri = [a["tip"] for a in pt["aparate"] if a.get("ref") not in ("QM", "QI")]
    # Q JT → T1 → celula trafo → celula de linie, apoi cablu MT → PCC MT 20 kV
    assert tipuri[-3:-2] == ["trafo"] and tipuri[-2] in ("sigurante_mt", "intreruptor_mt") and tipuri[-1] == "sep_mt"
    assert tipuri[0] in ("mccb", "acb")
    assert "MT 20 kV" in pt["sarcina"]["titlu"]
    sn = z["PT"]["Sn_kVA"]
    assert (tipuri[-2] == "intreruptor_mt") == (sn > 630)        # Î10 (proiectant 28.10.2026): siguranțe MT ≤ 630 kVA
    # anvelopa PT în listă, nu „carcasă tablou PT”
    den = [x["lista"][0] for x in m.get("materiale") or []]
    assert any("Anvelopă post" in d for d in den) and not any(d.startswith("Carcasă tablou PT") for d in den)


def test_pt_nou_c0_legatura_jt():
    m, r = _gen(dict(PT_NOU["f04"], tip_schema="cef", retea="tri"))
    assert r["rezultat"]["C0"]["descriere"].endswith("bara JT a PT (T1)")
    assert m["plecari"][0]["cablu"]["ref"] == "C0"


# ---------------------------------------------------------------- P1-6: PT existent = doar sursă
@pytest.mark.parametrize("inp", [
    {"racord": "pt", "pt_Sn_kVA": 1000, "pt_existent": True, "kWp": 600,
     "invertoare": [{"n": 5, "Pn_kW": 115}], "L_racord_m": 180},
    {"pt_Sn_kVA": 1000, "pt_existent": True, "kWp": 700, "invertoare": [{"n": 6, "Pn_kW": 110}]},
    {"racord": "tg_existent", "pt_Sn_kVA": 1000, "kWp": 300, "invertoare": [{"n": 3, "Pn_kW": 100}],
     "bess": {"kWh": 100, "P_kW": 50, "producator": "BYD", "model": "Battery-Box Premium HVM"}},
])
def test_pt_existent_fara_trafo(inp):
    m, r = _gen(dict(inp, tip_schema="cef", retea="tri"))
    assert not r["blocheaza_export"]
    assert not any(a["tip"] in ("trafo", "sigurante_mt", "intreruptor_mt", "sep_mt") for a in _toate(m))
    assert "PT" not in r["rezultat"] and r["rezultat"]["trafo"]["existent"]
    t = _txt(m)
    assert "20/0,4" not in t and "Anvelopă" not in t


# ---------------------------------------------------------------- P0-4: CEF în TT cu 2 × 100 kW
def test_cef_tt_2x100_planse_completa():
    inp = {"tip_schema": "cef", "schema_pamant": "TT", "RA_ohm": 4, "kWp": 200, "retea": "tri",
           "invertoare": [{"n": 2, "Pn_kW": 100, "producator": "Huawei", "model": "SUN2000-100KTL-M2"}]}
    m, r = _gen(inp)
    z = r["rezultat"]
    assert not r["blocheaza_export"]
    assert _cod(r, "V34", "AVERTISMENT")
    assert z["QG"]["DDR"]["IdN_mA"] == 300 and z["QG"]["DDR"]["dt_s"] > 0
    assert [i["DDR"]["IdN_mA"] for i in z["invertoare"]] == [100, 100]
    assert z["schema_pamant"] == "TT" and "TT" in z["nota_schema_pamant"] and "TN-S" not in z["nota_schema_pamant"]
    assert any("TT" in n for n in m["note"]) and not any("TN-S" in n for n in m["note"])
    refs = {a.get("ref") for a in _toate(m)}
    assert {"INV-1", "INV-2", "QG", "DDR-G", "DDR1", "DDR2"} <= refs


def test_cef_tt_cu_bmpt_neschimbat():
    r = calculeaza({"tip_schema": "cef", "schema_pamant": "TT", "RA_ohm": 10, "kWp": 90, "retea": "tri",
                    "invertoare": [{"n": 1, "Pn_kW": 90}], "racord": "bmpt"})
    assert r["rezultat"]["IdN_amonte_mA"] == 300 and not _cod(r, "V34", "AVERTISMENT")


# ---------------------------------------------------------------- P0-5: BESS cuplat în c.c. la invertor hibrid
def test_cef_hibrid_sungrow_sbh_fara_pcs():
    inp = {"tip_schema": "cef", "racord": "tg_existent", "kWp": 100, "retea": "tri",
           "invertoare": [{"n": 2, "Pn_kW": 50, "producator": "Sungrow", "model": "SH50T"}],
           "bess": {"kWh": 40, "producator": "Sungrow", "model": "SBH", "per_invertor": True, "U_nom_V": 600}}
    m, r = _gen(inp)
    z = r["rezultat"]
    assert "PCS" not in z and z["BESS"]["cuplaj"] == "cc" and z["BESS"]["la"] == ["INV-1", "INV-2"]
    assert z["sume"]["Pn_total_kW"] == 100
    refs = {a.get("ref") for a in _toate(m)}
    assert {"BAT1", "BAT2", "FB1", "FB2"} <= refs and "PCS" not in refs and "QB" not in refs
    assert not any(a["tip"] == "convertor_bess" for a in _toate(m))
    assert z["BESS"]["protectie_cc"]["INV-1"]["In_A"] >= 1.25 * 50000 / 600
    assert [b["sursa"]["titlu"] for b in m["intrari"]] == ["CÂMP PV 1", "CÂMP PV 2"]


def test_cef_cuplaj_cc_explicit_si_ca_explicit():
    base = {"tip_schema": "cef", "kWp": 60, "retea": "tri", "invertoare": [{"n": 1, "Pn_kW": 50}]}
    r = calculeaza(dict(base, bess={"kWh": 50, "P_kW": 25, "cuplaj": "cc"}))
    assert "PCS" not in r["rezultat"] and r["rezultat"]["BESS"]["la"] == ["INV-1"]
    r = calculeaza(dict(base, bess={"kWh": 50, "P_kW": 25, "cuplaj": "ca"}))
    assert r["rezultat"]["PCS"]
    # PowerStack (sistem cu PCS propriu) rămâne c.a. chiar lângă invertoare hibride
    r = calculeaza(dict(base, invertoare=[{"n": 1, "Pn_kW": 50, "model": "SH50T"}], bess={"kWh": 257, "P_kW": 125, "model": "PowerStack 255CS"}))
    assert r["rezultat"]["PCS"]


def test_prosumator_huawei_m1_luna_fara_pcs():
    inp = {"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 10,
           "invertor": {"Pn_kW": 10, "producator": "Huawei", "model": "SUN2000-10KTL-M1"},
           "bess": {"kWh": 10, "P_kW": 5, "producator": "Huawei", "model": "LUNA2000"}, "baterie_kWh": 10}
    m, r = _gen(inp)
    z = r["rezultat"]
    assert z["BESS"]["cuplaj"] == "cc" and "PCS" not in z
    refs = {a.get("ref") for a in _toate(m)}
    assert "BAT" in refs and "PCS" not in refs and "DDR-B" not in refs


# ---------------------------------------------------------------- locuințe P0-9: baterie la prosumator
def test_prosumator_20kw_baterie_implicit_cc():
    # N18: „prosumator 20 kW, invertor 20 kW, baterie 20 kWh, aprobat 20 kW”
    inp = {"tip_schema": "prosumator", "retea": "tri", "P_aprobata_kW": 20, "Pn_inv_kW": 20,
           "bess": {"kWh": 20, "P_kW": 10}, "baterie_kWh": 20}
    m, r = _gen(inp)
    z = r["rezultat"]
    assert z["BESS"]["cuplaj"] == "cc" and "PCS" not in z and not z["PI_externa"]
    assert z["sume"]["P_injectabila_kW"] == 20 and not _cod(r, "V76", "AVERTISMENT")


def test_prosumator_mono_6kw_baterie_nu_mai_blocheaza():
    # N44: 6 kW mono + 5 kWh — PCS-ul presupus dădea V53 BLOCANT
    r = calculeaza({"tip_schema": "prosumator", "retea": "mono", "P_aprobata_kW": 7, "Pn_inv_kW": 6,
                    "bess": {"kWh": 5, "P_kW": 2.5}, "baterie_kWh": 5, "L_inv_m": 10})
    assert not r["blocheaza_export"] and r["rezultat"]["BESS"]["cuplaj"] == "cc"


def test_prosumator_baterie_ca_prag_27_si_pa():
    inp = {"tip_schema": "prosumator", "retea": "tri", "P_aprobata_kW": 20, "Pn_inv_kW": 20,
           "bess": {"kWh": 20, "P_kW": 10, "cuplaj": "ca"}}
    m, r = _gen(inp)
    z = r["rezultat"]
    # 20 + 10 = 30 kW injectabil > 27 kW → PI externă; > Pa 20 kW → V76 (limitare EMS / ATR nou)
    assert z["PCS"] and z["PI_externa"] and z["sume"]["P_injectabila_kW"] == 30
    assert _cod(r, "V76", "AVERTISMENT")
    # cu limitarea injecției la Pa → doar INFO
    r = calculeaza(dict(inp, limitare_injectie_kW=20))
    assert not _cod(r, "V76", "AVERTISMENT") and _cod(r, "V76", "INFO")


def test_prosumator_mare_bess_ramane_ca():
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "invertoare": [{"n": 2, "Pn_kW": 125}],
                    "bess": {"P_kW": 100, "kWh": 200}, "limitare_injectie_kW": 150})
    assert r["rezultat"]["BESS"]["cuplaj"] == "ca"


# ---------------------------------------------------------------- P1-7: gPV pe stringuri
def _cef_str(st, **k):
    return dict({"tip_schema": "cef", "kWp": 110, "retea": "tri", "racord": "bmpt", "L_racord_m": 70,
                 "invertoare": [{"n": 1, "Pn_kW": 110, "producator": "Sungrow", "model": "SG110CX"}], "string": st}, **k)


def test_gpv_declarat_desenat():
    m, r = _gen(_cef_str({"n_stringuri_paralel": 10, "gpv": True}, gpv_In_A=20, kWp=60,
                         invertoare=[{"n": 1, "Pn_kW": 50}]))
    assert not r["blocheaza_export"]
    g = [a for a in _toate(m) if a["tip"] == "gpv"]
    assert g and g[0]["param"]["In_A"] == 20 and g[0]["param"]["n"] == 20
    assert "gPV 20" in _txt(m)


def test_gpv_calculat_din_isc():
    # Voc(−25 °C) = 18·49,6·1,135 = 1013 V: Umax 1100 V declarat (implicitul e acum 1000 V, raport #78)
    m, r = _gen(_cef_str({"n_module": 18, "n_stringuri_paralel": 12, "Uoc_V": 49.6, "Isc_A": 13.9, "Umax_inv_V": 1100}, kWp=120))
    assert r["rezultat"]["gPV_In_A"] and not r["blocheaza_export"]
    assert any(a["tip"] == "gpv" for a in _toate(m))


def test_gpv_fara_isc_avertisment_generic():
    m, r = _gen(_cef_str({"n_stringuri_paralel": 12}))
    assert not r["blocheaza_export"] and _cod(r, "V69", "AVERTISMENT")
    g = [a for a in _toate(m) if a["tip"] == "gpv"]
    assert g and g[0]["param"].get("generic")
    assert "conform proiect DC" in _txt(m)


def test_gpv_necesar_din_irev_la_2_stringuri():
    r = calculeaza(_cef_str({"n_module": 18, "n_stringuri_paralel": 2, "Uoc_V": 49.6, "Isc_A": 13.9, "I_rev_A": 10}))
    assert _cod(r, "V69") or r["rezultat"].get("gPV_In_A")
    r = calculeaza(_cef_str({"n_module": 18, "n_stringuri_paralel": 2, "Uoc_V": 49.6, "Isc_A": 13.9, "I_rev_A": 25}))
    assert "gPV_In_A" not in r["rezultat"]


def test_string_nedescris_nu_blocheaza():
    m, r = _gen(_cef_str({"beta": -0.29}))
    assert not r["blocheaza_export"] and _cod(r, "V07", "AVERTISMENT")
    assert any("conform proiect DC" in b["sursa"]["sub"] for b in m["intrari"])


# ---------------------------------------------------------------- P1-10: Iac vs Q BMPT / branșament existent
def test_cef_iac_peste_bmpt_63():
    r = calculeaza({"tip_schema": "cef", "racord": "bmpt", "In_Q_bransament_A": 63, "kWp": 45, "retea": "tri",
                    "invertoare": [{"n": 1, "Pn_kW": 40, "producator": "Solis", "model": "S5-GC40K"}], "L_racord_m": 25})
    assert _cod(r, "V72", "AVERTISMENT")
    r = calculeaza({"tip_schema": "cef", "racord": "bmpt", "In_Q_bransament_A": 80, "kWp": 45, "retea": "tri",
                    "invertoare": [{"n": 1, "Pn_kW": 40}], "L_racord_m": 25})
    assert not _cod(r, "V72", "AVERTISMENT") and _cod(r, "V72", "INFO")


def test_prosumator_iac_peste_q():
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 40, "In_Q_bransament_A": 63})
    assert _cod(r, "V72", "AVERTISMENT")


# ---------------------------------------------------------------- P1-9: modele din catalog
@pytest.mark.parametrize("prod,model,pn,hib", [
    ("Fronius", "Tauro ECO 50-3-D", 50, False), ("Fronius", "Tauro 50-3-D", 50, False),
    ("SMA", "STP 110-60", 110, False), ("SMA", "STP 50-41", 50, False),
    ("Sungrow", "SH50T", 50, True), ("Sungrow", "SH10RT", 10, True), ("Huawei", "SUN2000-10KTL-M1", 10, True),
    ("Huawei", "SUN2000-100KTL-M2", 100, False), ("Solis", "S6-EH3P10K-H", 10, True),
])
def test_catalog_modele(prod, model, pn, hib):
    d = cat.cauta(prod, model)
    assert d["Pn_kW"] == pn and d["hibrid"] == hib


def test_cef_model_fara_pn_din_catalog():
    r = calculeaza({"tip_schema": "cef", "kWp": 160, "retea": "tri", "racord": "tg_existent", "L_racord_m": 40,
                    "invertoare": [{"n": 2, "producator": "Fronius", "model": "Tauro ECO 50-3-D"},
                                   {"n": 1, "producator": "Fronius", "model": "Tauro 50-3-D"}]})
    assert not r["blocheaza_export"] and r["rezultat"]["sume"]["Pn_total_kW"] == 150
