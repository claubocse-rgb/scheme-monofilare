"""Echipamente din fișe tehnice: modele pe planșă și în listă, catalog local, import din PDF (v1.8).

Fișele de test sunt sintetice (tests/fise_sintetice.py): structura uzuală JA Solar / Huawei / Fronius / BYD / DEHN,
transformată în PDF cu biblioteca standard (Helvetica, FlateDecode) și, dacă există, cu reportlab (TrueType + ToUnicode).
"""
import json
import os
import re
import sys

import pytest

RAD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAD)
sys.path.insert(0, os.path.join(RAD, "tests"))

import fise_sintetice as F  # noqa: E402
from engine import constructor, echipamente as E, layout, memoriu, pdftext  # noqa: E402
from engine.calc import calculeaza  # noqa: E402
from engine.topologie import coliziuni  # noqa: E402


def _v(r, k=None):
    """valorile variantei k (implicit cea propusă)"""
    v = r["variante"][r["implicit"] if k is None else k]
    return {c: x["valoare"] for c, x in v["campuri"].items()}


def _inc(r, camp, k=None):
    return r["variante"][r["implicit"] if k is None else k]["campuri"][camp]["incredere"]


# ------------------------------------------------------------------------------------------------ extragerea din text
def test_ja_solar_cinci_variante_pe_coloane():
    r = E.extrage(F.text(F.JA_SOLAR))
    assert r["tip"] == "modul_pv" and r["producator"] == "JA Solar"
    assert len(r["variante"]) == 5
    assert [v["model"] for v in r["variante"]] == [f"JAM72S30-{p}/MR" for p in (540, 545, 550, 555, 560)]
    v = _v(r, 2)
    assert v["Pmax_W"] == 550 and v["Voc_V"] == 49.9 and v["Isc_A"] == 14 and v["Vmpp_V"] == 41.96 and v["Impp_A"] == 13.11
    assert v["beta_Voc_pct_K"] == -0.275 and v["gamma_Pmax_pct_K"] == -0.35 and v["alpha_Isc_pct_K"] == 0.045
    assert v["Umax_sistem_V"] == 1500 and v["I_rev_A"] == 25
    assert _v(r, 0)["Voc_V"] == 49.6 and _v(r, 4)["Pmax_W"] == 560     # STC, nu NOCT
    assert _inc(r, "Voc_V", 2) == "ridicată"
    assert any("5 variante" in a for a in r["avertismente"])


def test_huawei_invertor():
    v = _v(E.extrage(F.text(F.HUAWEI)))
    assert v["Pn_kW"] == 100 and v["Smax_kVA"] == 110 and v["Iac_max_A"] == 160.4      # „Max.” are prioritate față de „Rated”
    assert v["Umax_dc_V"] == 1100 and (v["MPPT_min_V"], v["MPPT_max_V"]) == (200, 1000)
    assert v["Idc_max_A"] == 30 and v["Isc_max_A"] == 40 and v["nr_MPPT"] == 10 and v["retea"] == "tri"


def test_fronius_trei_variante_cu_intervale_pe_coloane():
    r = E.extrage(F.text(F.FRONIUS))
    assert r["tip"] == "invertor" and len(r["variante"]) == 3
    assert [v["model"] for v in r["variante"]] == ["Symo GEN24 6.0 Plus", "Symo GEN24 8.0 Plus", "Symo GEN24 10.0 Plus"]
    v = _v(r, 2)
    assert v["Pn_kW"] == 10 and v["MPPT_min_V"] == 265 and v["MPPT_max_V"] == 800 and v["Umax_dc_V"] == 1000
    assert v["Idc_max_A"] == 25 and v["Isc_max_A"] == 37.5 and v["Iac_max_A"] == 15.2 and v["nr_MPPT"] == 2
    assert v["hibrid"] is True and _inc(r, "hibrid", 2) == "scăzută"


def test_byd_baterie_variante():
    r = E.extrage(F.text(F.BYD))
    assert r["tip"] == "bess" and r["producator"] == "BYD" and len(r["variante"]) == 4
    v = _v(r, 2)
    assert r["variante"][2]["model"] == "HVS 10.2"
    assert v["kWh_util"] == 10.24 and v["kWh"] == 10.24 and v["U_nom_V"] == 409 and v["chimie"] == "LiFePO₄"
    assert "Iac_max_A" not in v           # curentul de c.c. al bateriei nu e Iac,max al unui PCS
    assert _inc(r, "kWh", 2) == "medie"   # dedus din capacitatea utilă


def test_dehn_spd():
    r = E.extrage(F.text(F.DEHN))
    v = _v(r)
    assert r["tip"] == "spd_cc" and r["variante"][0]["model"] == "DEHNguard M YPV 1000 FM"
    assert v == {"Ucpv_V": 1000, "In_kA": 12.5, "Imax_kA": 25, "Up_kV": 4}


def test_text_romanesc_si_virgula_zecimala():
    t = """Modul fotovoltaic LONGi LR5-72HTH-580M
Puterea maximă Pmax: 580 Wp
Tensiunea în gol Voc: 52,20 V
Curentul de scurtcircuit Isc: 14,13 A
Tensiunea la puterea maximă Vmpp: 43,92 V
Curentul la puterea maximă Impp: 13,21 A
Coeficient de temperatură Voc: -0,230 %/°C
Tensiunea maximă a sistemului: 1500 V DC
Siguranța maximă în serie: 30 A"""
    r = E.extrage(t)
    v = _v(r)
    assert r["producator"] == "LONGi" and r["variante"][0]["model"] == "LR5-72HTH-580M"
    assert v == {"Pmax_W": 580, "Voc_V": 52.2, "Isc_A": 14.13, "Vmpp_V": 43.92, "Impp_A": 13.21, "beta_Voc_pct_K": -0.23,
                 "Umax_sistem_V": 1500, "I_rev_A": 30}


def test_mai_multe_marimi_pe_acelasi_rand_si_valoare_pe_randul_urmator():
    t = ("Canadian Solar CS6W-550MS ELECTRICAL DATA | STC Nominal Max. Power (Pmax) 550 W Opt. Operating Voltage (Vmp) 41.7 V "
         "Opt. Operating Current (Imp) 13.20 A Open Circuit Voltage (Voc) 49.6 V Short Circuit Current (Isc) 14.00 A "
         "Module Efficiency 21.3% Max. System Voltage 1500V (IEC/UL) Max. Series Fuse Rating 25 A\n"
         "Temperature Coefficient (Voc) -0.26 % / °C\nMax. input voltage\n1100 V")
    v = _v(E.extrage(t, "modul_pv"))
    assert (v["Pmax_W"], v["Vmpp_V"], v["Impp_A"], v["Voc_V"], v["Isc_A"]) == (550, 41.7, 13.2, 49.6, 14)
    assert v["beta_Voc_pct_K"] == -0.26 and v["Umax_sistem_V"] == 1500 and v["I_rev_A"] == 25
    v2 = _v(E.extrage("Huawei inverter MPPT\nMax. input voltage\n1100 V\nNumber of MPP trackers 6"))
    assert v2["Umax_dc_V"] == 1100 and v2["nr_MPPT"] == 6


def test_beta_in_mV_pe_K_si_incoerente():
    r = E.extrage("Open circuit voltage Voc 50 V\nShort circuit current Isc 14 A\nTemperature coefficient of Voc -137 mV/K\n"
                  "MPP voltage Vmpp 52 V")
    v = _v(r)
    assert v["beta_Voc_pct_K"] == pytest.approx(-0.274)
    assert any("Vmpp ≥ Voc" in a for a in r["avertismente"])
    assert _inc(r, "Vmpp_V") == "scăzută"


# ------------------------------------------------------------------------------------------------ PDF
@pytest.mark.parametrize("nume", list(F.FISE))
def test_pdf_extractor_stdlib(nume):
    rr = F.FISE[nume]
    r = E.importa_fisa(F.pdf_simplu(rr), motor="stdlib")
    assert r["motor"] == "stdlib" and r["caractere"] > 100
    ref = E.extrage(F.text(rr))
    assert len(r["variante"]) == len(ref["variante"])
    for k in range(len(ref["variante"])):
        a, b = _v(r, k), _v(ref, k)
        assert {c: b[c] for c in b if c in ("Pmax_W", "Voc_V", "Isc_A", "Pn_kW", "Iac_max_A", "MPPT_min_V", "kWh", "Ucpv_V")} == \
               {c: a[c] for c in a if c in ("Pmax_W", "Voc_V", "Isc_A", "Pn_kW", "Iac_max_A", "MPPT_min_V", "kWh", "Ucpv_V")}


def test_pdf_stdlib_coloane_pastrate():
    t = pdftext.text_stdlib(F.pdf_simplu(F.JA_SOLAR))
    assert re.search(r"Open Circuit Voltage\(Voc\) \[V\]\s{3,}49\.60\s{3,}49\.75", t)


def test_pdf_reportlab_truetype_tounicode():
    b = F.pdf_reportlab(F.JA_SOLAR)
    if b is None:
        pytest.skip("reportlab sau fontul TrueType lipsesc")
    t = pdftext.text_stdlib(b)
    assert "β_Voc" in t and "%/℃" in t           # glife din /ToUnicode (font TrueType încorporat, subset)
    v = _v(E.importa_fisa(b, motor="stdlib"), 2)
    assert v["Voc_V"] == 49.9 and v["beta_Voc_pct_K"] == -0.275


def test_pdf_pypdf_daca_exista():
    pytest.importorskip("pypdf")
    r = E.importa_fisa(F.pdf_simplu(F.HUAWEI))
    assert r["motor"] == "pypdf" and _v(r)["Iac_max_A"] == 160.4


def test_pdf_fara_text_si_fisier_invalid():
    gol = F.pdf_simplu([])
    r = E.importa_fisa(gol, motor="stdlib")
    assert r["caractere"] == 0 and any("scanată" in a for a in r["avertismente"])
    with pytest.raises(ValueError):
        E.importa_fisa(b"\x89PNG\r\n\x1a\n\x00\x00\xff\xfe")
    # textul lipit (fără PDF) merge pe aceeași cale
    assert E.importa_fisa(F.text(F.HUAWEI).encode())["motor"] == "text"


# ------------------------------------------------------------------------------------------------ catalog
@pytest.fixture
def date_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("SM_DATE", str(tmp_path))
    return tmp_path


def test_catalog_salvare_inlocuire_stergere(date_tmp):
    assert E.citeste_catalog()["echipamente"] == []
    d = E.scrie({"echipament": {"tip": "modul_pv", "producator": "JA Solar", "model": "JAM72S30-550/MR", "Voc_V": "49,9",
                                "Isc_A": 14, "Pmax_W": 550}})
    assert d["salvat"] == "modul-pv-ja-solar-jam72s30-550-mr" and d["echipamente"][0]["Voc_V"] == 49.9
    d = E.scrie({"echipament": {"tip": "modul_pv", "producator": "JA Solar", "model": "JAM72S30-550/MR", "Voc_V": 50}})
    assert len(d["echipamente"]) == 1 and d["echipamente"][0]["Voc_V"] == 50 and "Isc_A" not in d["echipamente"][0]
    E.scrie({"echipament": {"tip": "pcs", "producator": "BYD", "model": "HVS 10.2", "kWh": 10.24}})
    assert {e["tip"] for e in E.citeste_catalog()["echipamente"]} == {"modul_pv", "bess"}
    assert json.loads((date_tmp / "echipamente.json").read_text())["echipamente"]
    E.scrie({"sterge": d["salvat"]})
    assert [e["tip"] for e in E.citeste_catalog()["echipamente"]] == ["bess"]


@pytest.mark.parametrize("e, mesaj", [
    ({"tip": "modul_pv", "model": ""}, "lipsește modelul"),
    ({"tip": "frigider", "model": "X"}, "tip de echipament necunoscut"),
    ({"tip": "modul_pv", "model": "X", "Voc_V": "abc"}, "nu este un număr"),
    ({"tip": "modul_pv", "model": "X", "Voc_V": 900}, "domeniului plauzibil"),
    ({"tip": "modul_pv", "model": "X", "Voc_V": 40, "Vmpp_V": 45}, "Vmpp < Voc"),
    ({"tip": "invertor", "model": "X", "MPPT_min_V": 800, "MPPT_max_V": 200}, "MPPT min"),
])
def test_catalog_validare(date_tmp, e, mesaj):
    with pytest.raises(ValueError, match=mesaj):
        E.scrie({"echipament": e})


# ------------------------------------------------------------------------------------------------ calcul cu fișe
MODUL = {"producator": "JA Solar", "model": "JAM72S30-550/MR", "Pmax_W": 550, "Voc_V": 49.9, "Isc_A": 14.0, "Vmpp_V": 41.96,
         "Impp_A": 13.11, "beta_Voc_pct_K": -0.275, "Umax_sistem_V": 1500, "I_rev_A": 25}
HUAWEI = {"producator": "Huawei", "model": "SUN2000-100KTL-M2", "Pn_kW": 100, "Iac_max_A": 160.4, "Umax_dc_V": 1100,
          "MPPT_min_V": 200, "MPPT_max_V": 1000, "nr_MPPT": 10, "Idc_max_A": 30, "Isc_max_A": 40}


def test_cef_datele_de_fisa_inlocuiesc_presupunerile():
    r = calculeaza({"tip_schema": "cef", "kWp": 120, "invertoare": [dict(HUAWEI, n=1)], "modul": MODUL,
                    "string": {"n_module": 18, "n_stringuri_paralel": 2}})
    rz = r["rezultat"]
    assert rz["Uoc_Tmin_V"] == rz["Voc_Tmin_V"] == pytest.approx(18 * 49.9 * (1 + 0.00275 * 50))
    assert rz["Umax_inv_V"] == 1100 and rz["invertoare"][0]["Ib_A"] == 160.4
    assert not any("β" in p or "Umax invertor" in p for p in r["presupus"])
    assert any("din fișa modulului JA Solar JAM72S30-550/MR" in p for p in r["pasi"])
    assert any("din fișa invertorului Huawei SUN2000-100KTL-M2" in p for p in r["pasi"])
    v68 = [v for v in r["info"] if v["cod"] == "V68"][0]
    assert v68["mesaj"].startswith("Voc la Tmin") and "Uoc" not in v68["mesaj"]
    assert any(v["cod"] == "V89" for v in r["info"])                       # Vmpp în fereastra MPPT


def test_aliasuri_vechi_si_noi_ale_stringului():
    vechi = calculeaza({"tip_schema": "cef", "kWp": 50, "invertoare": [{"n": 1, "Pn_kW": 50}],
                        "string": {"n_module": 20, "Uoc_V": 49.5, "beta": -0.27, "Umax_inv_V": 1100}})
    nou = calculeaza({"tip_schema": "cef", "kWp": 50, "invertoare": [{"n": 1, "Pn_kW": 50}],
                      "string": {"n_module": 20, "Voc_V": 49.5, "beta_Voc_pct_K": -0.27, "Umax_inv_V": 1100}})
    assert vechi["rezultat"]["Uoc_Tmin_V"] == nou["rezultat"]["Uoc_Tmin_V"] == pytest.approx(1123.65)
    for r in (vechi, nou):
        v = [x for x in r["verificari"] if x["cod"] == "V68"][0]
        assert v["nivel"] == "BLOCANT" and "Voc la Tmin" in v["mesaj"]


def test_v89_mppt_si_curent():
    inv = dict(HUAWEI, MPPT_min_V=600, Isc_max_A=20)
    r = calculeaza({"tip_schema": "cef", "kWp": 120, "invertoare": [dict(inv, n=1)], "modul": MODUL,
                    "string": {"n_module": 12, "n_stringuri_paralel": 2}})
    v = [x for x in r["verificari"] if x["cod"] == "V89"]
    assert {x["nivel"] for x in v} == {"AVERTISMENT"}
    assert any("MPPT min 600 V" in x["mesaj"] for x in v) and any("Isc max invertor 20 A" in x["mesaj"] for x in v)


def test_v89_kwp_din_stringuri_diferit_de_declarat():
    r = calculeaza({"tip_schema": "cef", "kWp": 120, "invertoare": [dict(HUAWEI, n=1)], "modul": MODUL,
                    "string": {"n_module": 18, "n_stringuri_paralel": 3}})
    assert r["rezultat"]["kWp_stringuri"] == pytest.approx(297)
    assert any(x["cod"] == "V89" and "297 kWp" in x["mesaj"] for x in r["verificari"])


def test_beta_neplauzibil_din_fisa_blocheaza():
    r = calculeaza({"tip_schema": "cef", "kWp": 50, "invertoare": [{"n": 1, "Pn_kW": 50}], "modul": dict(MODUL, beta_Voc_pct_K=0.3),
                    "string": {"n_module": 18}})
    assert any(v["cod"] == "V68" and "β(Voc)" in v["mesaj"] for v in r["verificari"])


# ------------------------------------------------------------------------------------------------ planșa și lista
def _toate(m):
    out = []
    for b in m["intrari"]:
        for a in b["aparate"]:
            out.append(a)
            out += a.get("laterale") or []
    return out


def test_cef_doua_invertoare_diferite_fiecare_cu_modelul_lui():
    inp = {"tip_schema": "cef", "kWp": 200, "modul": MODUL, "string": {"n_module": 18, "n_stringuri_paralel": 3},
           "invertoare": [dict(HUAWEI, n=1), {"n": 1, "Pn_kW": 50, "producator": "Huawei", "model": "SUN2000-50KTL-M3",
                                                "nr_MPPT": 4, "separator_cc_integrat": True}],
           "spd_cc": {"producator": "DEHN", "model": "DEHNguard M YPV 1000 FM", "tip": "T1+T2"}}
    m, r = constructor.genereaza(inp)
    inv = {a["ref"]: a for a in _toate(m) if a["tip"] == "invertor"}
    assert set(inv) == {"INV-1", "INV-2"}
    assert inv["INV-1"]["spec"][-1] == "Huawei SUN2000-100KTL-M2" and inv["INV-2"]["spec"][-1] == "Huawei SUN2000-50KTL-M3"
    assert inv["INV-1"]["lista"][0].endswith("— Huawei SUN2000-100KTL-M2") and "MPPT 200…1000" in inv["INV-1"]["lista"][1]
    refs = [a.get("ref") for a in _toate(m)]
    for k in (1, 2):                          # partea de c.c. completă pe fiecare invertor
        for r_ in (f"PV{k}", f"F{k}.1", f"S{k}", f"F{k}.2", f"SB{k}", f"PE{k}", f"Q{k}"):
            assert r_ in refs, r_
    gpv = [a for a in _toate(m) if a["tip"] == "gpv"]
    assert gpv[0]["lista"][1].startswith("SR EN 60269-6 — 60 buc.")          # 10 MPPT × 3 stringuri × (+, −)
    sep2 = [a for a in _toate(m) if a.get("ref") == "S2"][0]
    assert "integrat" in sep2["lista"][0]
    spd = [a for a in _toate(m) if a.get("ref") == "F1.2"][0]
    assert "tip 1+2" in spd["lista"][0] and "DEHNguard M YPV 1000 FM" in spd["lista"][0]
    pv1 = [a for a in _toate(m) if a.get("ref") == "PV1"][0]
    assert "JA Solar JAM72S30-550/MR" in pv1["lista"][0] and "Voc 49,9" in pv1["lista"][1]
    assert not any("…" in (x or "") for x in refs)
    assert coliziuni(layout.build(m)) == []
    _, poz = layout.build_cu_pozitii(m)
    lista = " ".join(" ".join(p[2]) for p in poz)
    assert "SUN2000-100KTL-M2" in lista and "SUN2000-50KTL-M3" in lista and "string box" in lista


def test_cef_cinci_invertoare_fara_puncte_puncte():
    mod = [("Huawei", "SUN2000-100KTL-M2", 100), ("Huawei", "SUN2000-50KTL-M3", 50), ("Sungrow", "SG110CX", 110),
           ("SMA", "STP 25000TL-30", 25), ("Fronius", "Tauro ECO 50-3-D", 50)]
    inp = {"tip_schema": "cef", "kWp": 335, "atr_jt": True, "modul": MODUL, "string": {"n_module": 18, "n_stringuri_paralel": 3},
           "invertoare": [{"n": 1, "Pn_kW": p, "producator": pr, "model": mo} for pr, mo, p in mod],
           "bess": {"P_kW": 50, "kWh": 100, "producator": "BYD", "model": "Battery-Box Commercial"}}
    m, r = constructor.genereaza(inp)
    assert len(m["intrari"]) == 6
    for k, (pr, mo, p) in enumerate(mod, 1):
        a = [x for x in _toate(m) if x.get("ref") == f"INV-{k}"][0]
        assert mo in " ".join(a["spec"]) and a["lista"][0].endswith(f"— {pr} {mo}")
        assert any(x.get("ref") == f"F{k}.1" and x["tip"] == "gpv" for x in _toate(m))
    assert m["intrari"][-1]["sursa"]["titlu"] == "BESS"
    assert all("…" not in b["sursa"]["titlu"] and "× " not in (b.get("cablu_ca") or {}).get("text", "") for b in m["intrari"])
    assert coliziuni(layout.build(m)) == []


def test_cef_doua_invertoare_identice_desenate_separat():
    m, _ = constructor.genereaza({"tip_schema": "cef", "kWp": 200, "invertoare": [dict(HUAWEI, n=2)]})
    assert [b["sursa"]["titlu"] for b in m["intrari"]] == ["CÂMP PV 1", "CÂMP PV 2"]


def test_prosumator_cu_fise():
    inp = {"tip_schema": "prosumator", "retea": "tri", "In_Q_bransament_A": 32,
           "invertor": {"producator": "Fronius", "model": "Symo GEN24 10.0 Plus", "Pn_kW": 10, "Iac_max_A": 15.2,
                        "Umax_dc_V": 1000, "MPPT_min_V": 265, "MPPT_max_V": 800, "hibrid": True, "separator_cc_integrat": True},
           "baterie": {"producator": "BYD", "model": "Battery-Box Premium HVS 10.2", "kWh": 10.24, "U_nom_V": 409},
           "modul": MODUL, "string": {"n_module": 16, "n_stringuri_paralel": 3}}
    m, r = constructor.genereaza(inp)
    rz = r["rezultat"]
    assert rz["Iac_max_A"] == 15.2 and rz["Umax_inv_V"] == 1000 and rz["SPD_cc_Ucpv_V"] == 1000 and rz["gPV_In_A"]
    a = {x.get("ref"): x for x in _toate(m)}
    assert [x.replace("\u00a0", " ") for x in a["INV"]["spec"]] == ["10 kW · 3 × 400 V", "Fronius Symo GEN24 10.0 Plus"]
    assert "hibrid" in a["INV"]["lista"][0] and "Ord. ANRE 228/2018" in a["INV"]["lista"][1]
    assert a["BAT"]["lista"][0].endswith("— BYD Battery-Box Premium HVS 10.2")
    assert a["F2"]["param"]["Ucpv_V"] == 1000 and "integrat" in a["S"]["lista"][0]
    assert {"PE", "SB", "F1.1"} <= set(a)
    assert m["cartus"]["denumire2"] == "PROSUMATOR 10 kW TRIFAZAT"
    assert coliziuni(layout.build(m)) == []


def test_fara_fise_textele_raman_cele_vechi():
    m, _ = constructor.genereaza({"tip_schema": "cef", "kWp": 60, "invertoare": [{"n": 1, "Pn_kW": 50}]})
    pv = [a for a in _toate(m) if a["tip"] == "string_pv"][0]
    inv = [a for a in _toate(m) if a["tip"] == "invertor"][0]
    nb = lambda L: [x.replace("\u00a0", " ") for x in L]
    assert nb(pv["lista"]) == ["Câmp fotovoltaic 60 kWp (module și stringuri conform plan PV)"]
    assert nb(inv["spec"]) == ["50 kW · 3 × 400 V"] and "—" not in inv["lista"][0]


def test_memoriul_arata_modelele():
    m, r = constructor.genereaza({"tip_schema": "cef", "kWp": 120, "invertoare": [dict(HUAWEI, n=1)], "modul": MODUL,
                                  "string": {"n_module": 18, "n_stringuri_paralel": 2}})
    h = memoriu.genereaza_html(m, r)
    assert "Huawei SUN2000-100KTL-M2" in h and "Modul PV (fișa tehnică)" in h and "Voc" in h
    assert "Uoc" not in re.sub(r"<[^>]+>", "", h)


# ------------------------------------------------------------------------------------------------ API (local și web)
def _cerere(metoda, cale, corp=b""):
    import app
    sys.path.insert(0, os.path.join(RAD, "web"))
    from web_api import WebH                     # aceeași punte ca versiunea Pyodide (fără socket)
    h = WebH(metoda, cale, corp if isinstance(corp, bytes) else json.dumps(corp).encode())
    (h.do_GET if metoda == "GET" else h.do_POST)()
    st, hd, body = h.raspuns
    return st, json.loads(body)


def test_api_catalog_si_import(date_tmp):
    st, d = _cerere("GET", "/api/echipamente")
    assert st == 200 and d["echipamente"] == [] and "modul_pv" in d["campuri"] and d["claude"] in (True, False)
    st, d = _cerere("POST", "/api/echipamente/import", F.pdf_simplu(F.JA_SOLAR))
    assert st == 200 and d["tip"] == "modul_pv" and len(d["variante"]) == 5 and d["text"]
    ales = dict({c: x["valoare"] for c, x in d["variante"][2]["campuri"].items()}, tip="modul_pv",
                producator=d["producator"], model=d["variante"][2]["model"])
    st, d = _cerere("POST", "/api/echipamente", {"echipament": ales})
    assert st == 200 and d["salvat"] and d["echipamente"][0]["Voc_V"] == 49.9
    st, d = _cerere("POST", "/api/echipamente", {"echipament": {"tip": "modul_pv", "model": "X", "Voc_V": -3}})
    assert st == 400 and "Voc" in d["eroare"]
    st, d = _cerere("POST", "/api/echipamente/import", b"")
    assert st == 400
    st, d = _cerere("POST", "/api/echipamente/import", b"%PDF-1.4 stricat")
    assert st == 200 and d["caractere"] == 0


def test_api_rafinare_fara_claude(monkeypatch):
    monkeypatch.setattr(E, "claude_disponibil", lambda: False)
    st, d = _cerere("POST", "/api/echipamente/rafineaza", {"text": F.text(F.HUAWEI)})
    assert st == 400 and "Claude" in d["eroare"]


def test_web_salveaza_catalogul_in_browser():
    sys.path.insert(0, os.path.join(RAD, "web"))
    src = open(os.path.join(RAD, "web", "web_api.py"), encoding="utf-8").read()
    assert '"echipamente.json"' in src
    assert "'/api/echipamente'" in open(os.path.join(RAD, "web", "worker.js"), encoding="utf-8").read()


def test_interfata_scrie_voc_nu_uoc():
    s = open(os.path.join(RAD, "static", "index.html"), encoding="utf-8").read()
    vizibil = re.findall(r"'([^'\n]*Uoc[^'\n]*)'", s)
    assert vizibil == ["Uoc_V"]                     # doar cheia internă (alias compatibil), nu etichete
    assert "Voc modul [V]" in s and "β(Voc)" in s and "/api/echipamente/import" in s
