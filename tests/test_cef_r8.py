"""Regresie R8 „fotovoltaic” (teste/r8/fotovoltaic.md) — partea de motor / desen: invertoare monofazate pe rețea trifazată
(230 V, 2P, repartiție pe faze, dezechilibru), catalogul (Pn Huawei -H1/-H3, LUNA2000-200KWH, n PCS, n module × kWh),
CEF cu 2 trafo (secții de bare, QG pe secție, cuplă normal deschisă, celule MT comune), selectivitatea QG → Q JT,
mixul 800 V + 400 V, Ik declarat la bară și regula generală „planșă goală ⇒ BLOCANT explicit”. Intrare fizică directă."""
import itertools
import os
import re
import sys

import pytest

RAD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAD)

from engine import constructor, layout, render_svg  # noqa: E402
from engine.calc import calculeaza, norme  # noqa: E402
from engine.calc import catalog_invertoare as cat  # noqa: E402
from engine.topologie import coliziuni  # noqa: E402


def _toate(m):
    out = []

    def br(b):
        for a in b.get("aparate") or []:
            out.append(a)
            out.extend(a.get("laterale") or [])
        for c in b.get("copii") or []:
            br(c)
    for b in (m.get("intrari") or []) + (m.get("plecari") or []):
        br(b)
    return out


def _gen(inp):
    m, r = constructor.genereaza(inp)
    c = layout.build(m)
    assert coliziuni(c) == []
    return m, r, c


def _cod(r, cod, nivel=None):
    return [v for v in r["verificari"] + r.get("info", []) if v["cod"] == cod and (nivel is None or v["nivel"] == nivel)]


def _txt(c):
    s = render_svg.render(c, "t")
    return " | ".join(t.strip() for t in re.findall(r">([^<>]+)<", s) if t.strip())


# ---------------------------------------------------------------- 1. catalog
@pytest.mark.parametrize("model, pn, retea", [
    ("Primo 8.2-1", 8.2, "mono"), ("Fronius Primo 3.0-1", 3.0, "mono"), ("SB 5.0-1AV-41", 5.0, "mono"),
    ("Sunny Boy 6.0", 6.0, "mono"), ("SUN2000-6KTL-L1", 6.0, "mono"), ("MIN 6000TL-X", 6.0, "mono"),
    ("SH6.0RS", 6.0, "mono"), ("SUN2000-10KTL-M1", 10.0, "tri"), ("Symo 10.0-3-M", 10.0, "tri"),
    ("SUN2000-330KTL-H1", 300.0, "tri"), ("SUN2000-215KTL-H3", 200.0, "tri"), ("SUN2000-185KTL-H1", 175.0, "tri"),
    ("SUN2000-150K-MG0", 150.0, "tri"), ("SUN2000-100KTL-M2", 100.0, "tri")])
def test_catalog_pn_si_retea(model, pn, retea):
    d = cat.cauta(None, model)
    assert d["Pn_kW"] == pn and d["retea"] == retea


def test_catalog_sunny_boy_storage_nu_e_invertor_pv():
    assert cat.cauta(None, "Sunny Boy Storage 6.0") is None and cat.bess_ca(None, "Sunny Boy Storage 6.0")


def test_catalog_luna_200kwh_bess_cu_pcs():
    assert cat.bess_ca("Huawei", "LUNA2000-200KWH-2H1")
    assert cat.bess_din_cod("Huawei", "LUNA2000-200KWH-2H1") == {"kWh": 200.0, "P_kW": 100.0}
    assert cat.kwh_modul("Deye", "BOS-G") == 5.12


# ---------------------------------------------------------------- 2. invertoare monofazate pe rețea trifazată
PRIMO3 = {"tip_schema": "prosumator", "retea": "tri", "schema_pamant": "TN-S",
          "invertoare": [{"n": 3, "producator": "Fronius", "model": "Primo 8.2-1"}]}


def test_primo_3_pe_trei_faze_230v_2p():
    m, r, c = _gen(PRIMO3)
    z = r["rezultat"]
    assert not r["blocheaza_export"]
    assert [i["faza"] for i in z["invertoare"]] == ["L1", "L2", "L3"]
    for i in z["invertoare"]:
        assert i["retea"] == "mono" and abs(i["Ib_A"] - 1.1 * 8200 / 230) < 0.1     # ≈ 39 A, nu 13 A
        assert i["protectie"]["In_A"] >= 40
    assert abs(z["Iac_max_A"] - 39.22) < 0.1 and z["faze"]["L1"] == z["faze"]["L3"]
    assert not _cod(r, "V71", "AVERTISMENT") and _cod(r, "V71", "INFO")
    qs = [a for b in m["intrari"] for a in b["aparate"] if re.fullmatch(r"Q[123]", str(a.get("ref")))]
    assert len(qs) == 3 and all(a["param"]["poli"] == "2P" for a in qs)
    assert all("3×" in (i.get("cablu") or "") for i in z["invertoare"])            # L + N + PE
    t = _txt(c)
    assert "L1 + N" in t and "L3 + N" in t and "3 × 400" not in t


def test_dezechilibru_peste_3_68_kva_avertisment():
    r = calculeaza(dict(PRIMO3, invertoare=[{"n": 2, "producator": "Fronius", "model": "Primo 8.2-1"}]))
    v = _cod(r, "V71", "AVERTISMENT")
    assert v and "dezechilibru" in v[0]["mesaj"] and norme.DEZECHILIBRU_FAZE_MAX_KVA == 3.68      # 16 A, Ord. ANRE 228/2018 art. 12(3)


def test_faza_declarata_respectata():
    r = calculeaza(dict(PRIMO3, invertoare=[{"n": 3, "Pn_kW": 3, "producator": "Fronius", "model": "Primo 3.0-1",
                                              "faza": ["L2", "L2", "L2"]}]))
    z = r["rezultat"]
    assert [i["faza"] for i in z["invertoare"]] == ["L2"] * 3 and _cod(r, "V71", "AVERTISMENT")


def test_cef_tri_cu_mono_curent_pe_faza():
    r = calculeaza({"tip_schema": "cef", "retea": "tri", "kWp": 60,
                    "invertoare": [{"n": 1, "Pn_kW": 30, "model": "STP 30-50"},
                                   {"n": 3, "producator": "SMA", "model": "SB 5.0-1AV-41"}]})
    z = r["rezultat"]
    assert not r["blocheaza_export"]
    i_tri = 1.1 * 30000 / (3 ** 0.5 * 400)
    assert abs(z["sume"]["Iac_total_A"] - (i_tri + 1.1 * 5000 / 230)) < 0.1
    assert sorted(i.get("faza") for i in z["invertoare"] if i.get("faza")) == ["L1", "L2", "L3"]


# ---------------------------------------------------------------- 3. CEF cu 2 trafo peste ~2,2 MW
CEF3 = {"tip_schema": "cef", "retea": "tri", "n_trafo": 2, "pt_Sn_kVA": 2000, "pt_existent": False, "masura": "MT",
        "kWp": 3600, "invertoare": [{"n": 30, "Pn_kW": 100, "producator": "Sungrow", "model": "SG100CX"}]}


def test_cef_3mw_doua_sectii_fara_qg_unic():
    m, r, c = _gen(CEF3)
    z = r["rezultat"]
    assert not r["blocheaza_export"] and not _cod(r, "V06")
    assert len(z["sectii"]) == 2 and [len(s["unitati"]) for s in z["sectii"]] == [15, 15]
    assert z.get("QG") is None and all(s["QG"]["Ir_A"] <= z["PT"]["Q_JT"]["Ir_A"] for s in z["sectii"])
    assert [p["sarcina"]["titlu"] for p in m["plecari"]] == ["PT — T1", "PT — T2"]
    assert m["bara"]["cupla"]["n1_in"] == 2 and len(m["intrari"]) == 3      # T1: INV-1 + INV-2…15 │ T2: INV-16…30
    # celulele MT comune (măsură + linie) o singură dată, în amonte de ambele celule trafo
    # echipa1 P1-9: întreruptorul de interfață MT (QI, PI cu 59N) între bara MT a centralei și celula de măsură
    assert [a["ref"] for a in m["jonctiune"]["aparate"]] == ["QI", "QM", "QL"]
    refs = [a.get("ref") for a in _toate(m)]
    assert "QM" not in refs and "QL" not in refs
    t = _txt(c)
    for x in ("QG1", "QG2", "QC", "QJT1", "QJT2", "T1", "T2", "QM", "QL", "INV-1", "INV-2…15", "INV-16…30", "Q16…30"):
        assert x in t
    assert c.meta["scara"] >= 0.6          # r8: coloanele „idem” consecutive comprimate (> 24 invertoare)


def test_cef_2_trafo_repartitie_declarata():
    inp = dict(CEF3, invertoare=[{"n": 10, "Pn_kW": 100, "sectie": 2}, {"n": 10, "Pn_kW": 100, "sectie": 1}], kWp=2400)
    z = calculeaza(inp)["rezultat"]
    assert z["sectii"][0]["unitati"][0] == "INV-11" and z["sectii"][1]["unitati"][0] == "INV-1"


def test_cef_mare_un_trafo_v06_cu_remediere_2_trafo():
    r = calculeaza(dict(CEF3, n_trafo=1, pt_Sn_kVA=3150) if 3150 in norme.TRAFO else dict(CEF3, n_trafo=1, pt_Sn_kVA=2500))
    v = _cod(r, "V06", "BLOCANT")
    assert v and "n_trafo 2" in v[0]["remediere"]


# ---------------------------------------------------------------- 4. selectivitate QG → Q JT
@pytest.mark.parametrize("inp", [
    {"tip_schema": "cef", "retea": "tri", "pt_Sn_kVA": 400, "pt_existent": False, "kWp": 400, "L_racord_m": 20,
     "invertoare": [{"n": 1, "producator": "Huawei", "model": "SUN2000-330KTL-H1"}]},
    {"tip_schema": "cef", "pt_Sn_kVA": 1250, "pt_existent": False, "masura": "MT", "bess": {"kWh": 2000, "P_kW": 1000}},
    {"tip_schema": "cef", "pt_Sn_kVA": 630, "pt_existent": False, "bess": {"kWh": 1000, "P_kW": 500}},
])
def test_reglajele_cresc_spre_amonte(inp):
    r = calculeaza(inp)
    z = r["rezultat"]
    assert z["QG"]["Ir_A"] <= z["PT"]["Q_JT"]["Ir_A"] <= norme.Q_JT_IR_MAX_IN_T * z["PT"]["In_T_A"] + 1e-6
    assert not _cod(r, "V41", "AVERTISMENT")


def test_selectivitate_inversata_imposibila_avertisment():
    # PCS 560 kW pe 630 kVA: Ip PCS = 1,25·Pn/U ≈ 1010 A > 1,1·In_T = 1000 A → Q JT nu poate urca peste QG:
    # V41 AVERTISMENT cu remediere, nu planșă curată
    r = calculeaza({"tip_schema": "cef", "pt_Sn_kVA": 630, "pt_existent": False,
                    "bess": {"kWh": 1120, "P_kW": 560}})
    v = _cod(r, "V41", "AVERTISMENT")
    assert v and "inversat" in v[0]["mesaj"] and "amonte" in v[0]["remediere"]


# ---------------------------------------------------------------- 5. 800 V + 400 V, Ik la bară, Pn Huawei
def test_mix_800_400_mesaj_clar():
    r = calculeaza({"tip_schema": "cef", "pt_Sn_kVA": 1600, "pt_existent": False, "kWp": 1500, "retea": "tri",
                    "U_ca_V": 800, "invertoare": [{"n": 4, "producator": "Sungrow", "model": "SG250HX"},
                                                  {"n": 2, "producator": "Sungrow", "model": "SG110CX"}]})
    v = _cod(r, "V12", "BLOCANT")
    assert v and "800 V și de 400 V" in v[0]["mesaj"] and "SG250HX" in v[0]["mesaj"]
    assert "două înfășurări JT" in v[0]["remediere"] and "trafo separate" in v[0]["remediere"]


@pytest.mark.parametrize("camp", ["Ik3_TG_kA", "Ik3_sursa_kA"])
def test_ik_la_bara_folosit(camp):
    inp = {"tip_schema": "cef", "retea": "tri", "racord": "tg_existent", "kWp": 120, camp: 30,
           "invertoare": [{"n": 1, "producator": "Huawei", "model": "SUN2000-100KTL-M2"}]}
    r = calculeaza(inp)
    assert not r["blocheaza_export"] and r["rezultat"]["QG"]["Icu_kA"] >= 30


def test_ik_zero_blocant_explicit():
    r = calculeaza({"tip_schema": "cef", "retea": "tri", "racord": "tg_existent", "Ik3_TG_kA": 0,
                    "invertoare": [{"n": 1, "Pn_kW": 100}]})
    v = _cod(r, "V07", "BLOCANT")
    assert v and "Ik3_TG_kA" in v[0]["mesaj"]


def test_huawei_h1_pn_300():
    z = calculeaza({"tip_schema": "cef", "pt_Sn_kVA": 400, "pt_existent": False, "kWp": 400,
                    "invertoare": [{"n": 1, "producator": "Huawei", "model": "SUN2000-330KTL-H1"}]})["rezultat"]
    assert z["sume"]["Pn_total_kW"] == 300 and abs(z["sume"]["S_total_kVA"] - 330) < 0.1


# ---------------------------------------------------------------- 6. BESS
def test_luna2000_200kwh_desenat():
    m, r, c = _gen({"tip_schema": "cef", "retea": "tri", "kWp": 120, "limitare_injectie_kW": 0, "racord": "tg_existent",
                    "invertoare": [{"n": 1, "producator": "Huawei", "model": "SUN2000-100KTL-M2"}],
                    "bess": {"producator": "Huawei", "model": "LUNA2000-200KWH-2H1"}})
    z = r["rezultat"]
    assert not r["blocheaza_export"] and z["PCS"]["Pn_kW"] == 100
    t = _txt(c)
    assert "PCS" in t and "200" in t and "BAT" in t


def test_n_pcs_si_n_module():
    r = calculeaza({"tip_schema": "cef", "pt_Sn_kVA": 1250, "pt_existent": False,
                    "bess": {"n_pcs": 4, "pcs": {"Pn_kW": 250}, "n_module": 10, "kWh_modul": 200}})
    z = r["rezultat"]
    assert len(z["PCS_lista"]) == 4 and all(p["Pn_kW"] == 250 for p in z["PCS_lista"])
    assert z["sume"]["Pn_total_kW"] == 1000
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "schema_pamant": "TN-C-S", "Pn_inv_kW": 30,
                    "bess": {"cuplaj": "cc", "n_module": 4, "producator": "Deye", "model": "BOS-G"}})
    assert abs(r["rezultat"]["BESS"]["kWh"] - 20.48) < 0.01


def test_n_pcs_desen_fiecare_cu_qb():
    m, r, c = _gen({"tip_schema": "cef", "pt_Sn_kVA": 1250, "pt_existent": False, "bess": {"n_pcs": 4, "P_kW": 1000, "kWh": 2000}})
    t = _txt(c)
    for k in range(1, 5):
        assert f"PCS-{k}" in t and f"QB{k}" in t


# ---------------------------------------------------------------- 7. regula generală: planșă goală ⇒ BLOCANT explicit
_INV = [[{"n": 1, "Pn_kW": 50}], [{"n": 30, "Pn_kW": 100, "model": "SG100CX"}], [{"n": 4, "model": "SG250HX"}],
        [{"n": 3, "model": "Primo 8.2-1"}], [{"n": 4, "model": "SG250HX"}, {"n": 2, "model": "SG110CX"}],
        [{"n": 1, "model": "SUN2000-330KTL-H1"}], [{"n": 12, "Pn_kW": 250}], [{"n": 2, "Pn_kW": 0.5}], []]
_RAC = [{}, {"racord": "tg_existent", "Ik3_TG_kA": 30}, {"pt_Sn_kVA": 1600, "pt_existent": False},
        {"pt_Sn_kVA": 2000, "pt_existent": False, "n_trafo": 2, "masura": "MT"}, {"pt_Sn_kVA": 1000, "pt_existent": True},
        {"retea": "mono"}, {"pt_Sn_kVA": 1600, "pt_existent": False, "n_trafo": 3}]
_BESS = [None, {"model": "LUNA2000-200KWH-2H1"}, {"n_pcs": 2, "P_kW": 500, "kWh": 1000}]


@pytest.mark.parametrize("inv, rac, bess", list(itertools.product(range(len(_INV)), range(len(_RAC)), range(len(_BESS)))))
def test_plansa_goala_numai_cu_blocant(inv, rac, bess):
    inp = dict({"tip_schema": "cef", "kWp": 500}, **_RAC[rac])
    inp["invertoare"] = [dict(g) for g in _INV[inv]]
    if _BESS[bess]:
        inp["bess"] = dict(_BESS[bess])
    m, r = constructor.genereaza(inp)
    goala = not m.get("plecari") or not m.get("intrari")
    if goala:
        bl = [v for v in r["verificari"] if v["nivel"] == "BLOCANT"]
        assert bl and all(v.get("mesaj") for v in bl), inp
    else:
        layout.build(m)
