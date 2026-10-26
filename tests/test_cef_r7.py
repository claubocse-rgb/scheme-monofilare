"""Regresie R7 „fotovoltaic” (teste/r7/fotovoltaic.md + prosumator din teste/r7/locuinte.md): PT nou cu n trafo,
invertoare de 800 V c.a., limitarea injecției la punctul de racord, baterie la mai multe hibride, selectivitate QG / Q JT /
invertor, lizibilitate peste 6 invertoare, contradicții, măsura pe MT. Intrare fizică directă (fără interpretor)."""
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
    c = layout.build(m)
    assert coliziuni(c) == []
    return m, r, c


def _cod(r, cod, nivel=None):
    return [v for v in r["verificari"] + r.get("info", []) if v["cod"] == cod and (nivel is None or v["nivel"] == nivel)]


def _txt(c):
    s = render_svg.render(c, "t")
    return " | ".join(t.strip() for t in re.findall(r">([^<>]+)<", s) if t.strip())


HUAWEI_100 = {"producator": "Huawei", "model": "SUN2000-100KTL-M2"}
CEF_16 = {"tip_schema": "cef", "retea": "tri", "pt_Sn_kVA": 1000, "pt_existent": False, "kWp": 1900, "L_racord_m": 40,
          "invertoare": [dict(HUAWEI_100, n=16, Pn_kW=100)]}


# ---------------------------------------------------------------- 1. n_trafo pe ramura CEF / BESS
def test_cef_2_trafo_1000_fara_v67_si_doua_ramuri_pt():
    # r8: PT nou cu 2 trafo = 2 secții de bare (câte un QG și un trafo pe secție), cuplă normal deschisă
    m, r, _ = _gen(dict(CEF_16, n_trafo=2))
    z = r["rezultat"]
    assert not _cod(r, "V67") and not r["blocheaza_export"]
    assert z["n_trafo"] == 2 and z["PT"]["n_trafo"] == 2 and len(z["sectii"]) == 2
    # Ik3 pe secție = un singur trafo (cupla deschisă)
    assert abs(z["trafo"]["Ik3max_bara_kA"] - calculeaza(dict(CEF_16, pt_Sn_kVA=1000, kWp=900, invertoare=[
        dict(HUAWEI_100, n=8, Pn_kW=100)]))["rezultat"]["trafo"]["Ik3max_bara_kA"]) < 0.01
    qjt = z["PT"]["Q_JT"]
    for sz in z["sectii"]:
        assert qjt["Ir_A"] >= sz["QG"]["Ir_A"]                 # reglajele cresc spre amonte
        assert qjt["Ir_A"] >= sz["sume"]["Iac_total_A"]
    assert [len(p["copii"]) for p in m["plecari"]] == [1, 1]
    refs = {a.get("ref") for a in _toate(m)} | {a.get("ref") for a in m["jonctiune"]["aparate"]}
    assert {"QG1", "QG2", "QJT1", "QJT2", "T1", "T2", "QT1", "QT2", "QL"} <= refs
    assert m["bara"]["cupla"]["aparat"]["ref"] == "QC" and "NO" in m["bara"]["cupla"]["aparat"]["spec"][1]


def test_bess_2x630_un_pcs_nu_incape_pe_o_sectie():
    # r8: un PCS de 1000 kW nu se poate împărți pe două trafo cu cupla deschisă → V67 pe secție
    r = calculeaza({"tip_schema": "cef", "pt_Sn_kVA": 630, "n_trafo": 2, "pt_existent": False,
                    "bess": {"kWh": 2000, "P_kW": 1000}})
    v = _cod(r, "V67", "BLOCANT")
    assert v and "secția" in v[0]["mesaj"]
    # cu 2 PCS × 500 kW: câte unul pe trafo, fără V67
    m, r, _ = _gen({"tip_schema": "cef", "pt_Sn_kVA": 630, "n_trafo": 2, "pt_existent": False,
                    "bess": {"kWh": 2000, "P_kW": 1000, "n_pcs": 2}})
    assert not _cod(r, "V67") and len(r["rezultat"]["PCS_lista"]) == 2


def test_n_trafo_suma_sn_insuficienta_si_mesaj():
    r = calculeaza(dict(CEF_16, pt_Sn_kVA=630, n_trafo=2))
    v = _cod(r, "V67", "BLOCANT")
    assert len(v) == 2 and "Sn T1 630 kVA" in v[0]["mesaj"] and "secția" in v[0]["mesaj"]


@pytest.mark.parametrize("n", [0, 5, 1.5, "doi"])
def test_n_trafo_invalid(n):
    r = calculeaza(dict(CEF_16, n_trafo=n))
    assert _cod(r, "V96", "BLOCANT")


# ---------------------------------------------------------------- 2. invertoare de 800 V c.a.
SG = {"tip_schema": "cef", "retea": "tri", "pt_Sn_kVA": 2500, "pt_existent": False, "kWp": 2400, "L_racord_m": 30,
      "invertoare": [{"n": 8, "producator": "Sungrow", "model": "SG250HX"}]}


def test_catalog_800v():
    for mo in ("SG250HX", "SG350HX", "SUN2000-330KTL-H1", "SUN2000-215KTL-H3"):
        assert cat.u_ca(None, mo) == 800 and cat.cauta(None, mo)["Umax_dc_V"] == 1500
    assert cat.u_ca(None, "SUN2000-100KTL-M2") is None and cat.cauta(None, "SG110CX").get("U_ca_V") is None


def test_cef_800v_calcul_si_desen():
    m, r, c = _gen(SG)
    z = r["rezultat"]
    assert z["U_ca_V"] == 800 and not r["blocheaza_export"]
    inv = z["invertoare"][0]
    assert inv["Ib_A"] == pytest.approx(1.1 * 250000 / (3 ** 0.5 * 800), rel=1e-6)
    assert inv["fara_N"] and "4×" not in inv["cablu"].split("+")[0] or "(3 + PE)" in inv["cablu"]
    assert z["PT"]["In_T_A"] == pytest.approx(2500000 / (3 ** 0.5 * 800), rel=1e-6)
    assert z["SPD_cc_Ucpv_V"] == 1500
    assert norme.u_n() == 400.0                               # contextul de 800 V nu iese din calcul
    t = _txt(c)
    assert "20/0,8 kV" in t and "3 × 800 V" in t and "3 + PE" in t and "3 + N + PE" not in t
    assert "1500 V" in t
    assert all((a.get("param") or {}).get("poli") == "3P" for a in _toate(m) if a.get("tip") in ("mccb", "acb"))


def test_800v_in_tg_existent_blocant():
    r = calculeaza({"tip_schema": "cef", "racord": "tg_existent",
                    "invertoare": [{"n": 3, "producator": "Huawei", "model": "SUN2000-330KTL-H1"}]})
    v = _cod(r, "V12", "BLOCANT")
    assert v and "800 V" in v[0]["mesaj"] and "20/0,8" in v[0]["remediere"]


def test_800v_declarat_contra_catalog_si_tensiune_nesuportata():
    assert _cod(calculeaza(dict(CEF_16, U_ca_V=800)), "V12", "BLOCANT")
    assert _cod(calculeaza(dict(SG, U_ca_V=690)), "V96", "BLOCANT")
    r = calculeaza(dict(CEF_16, invertoare=[{"n": 4, "Pn_kW": 100}], U_inv_ca_V=800, pt_Sn_kVA=630))
    assert r["rezultat"].get("U_ca_V") == 800 and not r["blocheaza_export"]


# ---------------------------------------------------------------- 3. injecție zero: TC la punctul de racord
def test_injectie_zero_tg_existent_tc_pe_alimentarea_tg():
    m, r, _ = _gen({"tip_schema": "cef", "racord": "tg_existent", "pt_Sn_kVA": 630, "kWp": 160, "retea": "tri",
                    "invertoare": [{"n": 3, "Pn_kW": 50}], "limitare_injectie_kW": 0, "L_racord_m": 40})
    pl = m["plecari"][0]
    assert not any(a.get("ref") == "TCA" for a in pl["aparate"])          # nu pe plecarea PV
    tg = pl["copii"]
    assert pl.get("tablou_existent") and any(a.get("ref") == "TCA" for a in tg[0]["aparate"])
    assert "PCC" in tg[0]["sarcina"]["titlu"]
    # comanda EMS spre fiecare invertor
    for b in m["intrari"]:
        inv = next(a for a in b["aparate"] if a["tip"] == "invertor")
        assert any(l.get("eticheta") == "EMS" and l.get("legatura") == "comanda" for l in inv.get("laterale") or [])
    # TG existent nu intră în lista de furnizare
    assert not any("TG EXISTENT" in str(x.get("ref")) for x in m["materiale"])


def test_injectie_zero_prosumator_30kw_la_pcc():
    m, r, _ = _gen({"tip_schema": "prosumator", "retea": "tri", "schema_pamant": "TN-C-S", "Pn_inv_kW": 30,
                    "limitare_injectie_kW": 0, "racord": "tg_existent"})
    pl = m["plecari"][0]
    assert pl["aparate"][0]["ref"] == "QG" and not any(a.get("ref") == "TCA" for a in pl["aparate"])
    assert any(a.get("ref") == "TCA" for a in pl["copii"][0]["aparate"])


# ---------------------------------------------------------------- 4. baterie la mai multe hibride / fără baterie
P33 = {"tip_schema": "prosumator", "retea": "tri", "schema_pamant": "TN-C-S",
       "invertoare": [{"n": 3, "Pn_kW": 10, "producator": "Huawei", "model": "SUN2000-10KTL-M1", "hibrid": True}]}


def test_hibrid_fara_baterie_nu_primeste_baterie():
    m, r, _ = _gen(dict(P33, hibrid=True))
    assert "BESS" not in r["rezultat"]
    assert not any(str(a.get("ref", "")).startswith(("BAT", "FB")) for a in _toate(m))


def test_baterie_pe_total_repartizata_pe_toate_hibridele():
    m, r, _ = _gen(dict(P33, bess={"kWh": 15, "producator": "Huawei", "model": "LUNA2000-15-S0"}))
    b = r["rezultat"]["BESS"]
    assert b["la"] == ["INV-1", "INV-2", "INV-3"] and b["kWh_port"] == 5.0
    assert any("împărțită pe 3" in p for p in r["presupus"])
    invs = [a for a in _toate(m) if a.get("tip") == "invertor"]
    assert [sorted(l["ref"] for l in i["laterale"]) for i in invs] == [["BAT1", "FB1"], ["BAT2", "FB2"], ["BAT3", "FB3"]]


def test_baterie_declarata_pe_un_invertor():
    m, r, _ = _gen(dict(P33, bess={"kWh": 10, "la": ["INV-2"]}))
    assert r["rezultat"]["BESS"]["la"] == "INV-2"
    invs = {a["ref"]: a for a in _toate(m) if a.get("tip") == "invertor"}
    assert not invs["INV-1"].get("laterale") and any(l["ref"] == "BAT" for l in invs["INV-2"]["laterale"])


def test_cef_baterie_bess_la():
    r = calculeaza({"tip_schema": "cef", "invertoare": [{"n": 4, "Pn_kW": 50, "hibrid": True}],
                    "bess": {"kWh": 100, "cuplaj": "cc", "la": 2}})
    assert r["rezultat"]["BESS"]["la"] == ["INV-1", "INV-2"] and r["rezultat"]["BESS"]["kWh_port"] == 50


# ---------------------------------------------------------------- 5. selectivitate
def test_un_singur_invertor_fara_v41_avertisment():
    r = calculeaza({"tip_schema": "cef", "kWp": 50, "invertoare": [{"n": 1, "Pn_kW": 50}]})
    assert not _cod(r, "V41", "AVERTISMENT") and _cod(r, "V41", "INFO")
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 30, "schema_pamant": "TN-C-S"})
    assert not _cod(r, "V41", "AVERTISMENT")


def test_bess_pt_nou_qjt_sub_in_trafo_si_temporizare():
    r = calculeaza({"tip_schema": "cef", "racord": "pt", "pt_Sn_kVA": 630, "pt_existent": False,
                    "bess": {"kWh": 1000, "P_kW": 500}})
    z = r["rezultat"]
    # r8: Q JT ridicat ≥ Ir QG (≤ 1,1·In_T, Σ Iac ≤ In_T) — reglajele cresc spre amonte
    assert z["QG"]["Ir_A"] <= z["PT"]["Q_JT"]["Ir_A"] <= 1.1 * z["PT"]["In_T_A"]
    assert not _cod(r, "V60") and not _cod(r, "V41", "AVERTISMENT")
    assert z["PT"]["Q_JT"]["tsd_s"] > z["QG"]["tsd_s"] and _cod(r, "V41", "INFO")


# ---------------------------------------------------------------- 6. lizibilitate peste 6 invertoare
@pytest.mark.parametrize("inp, n", [(dict(CEF_16, pt_Sn_kVA=2000), 16), (dict(CEF_16, n_trafo=2), 16), (SG, 8),
                                    (dict(CEF_16, pt_Sn_kVA=2500, invertoare=[dict(HUAWEI_100, n=20, Pn_kW=100)]), 20)])
def test_multe_invertoare_lizibile_fiecare_cu_protectia_lui(inp, n):
    m, r, c = _gen(inp)
    assert c.meta["scara"] >= 0.6 and c.w in (594.0, 841.0)
    t = _txt(c)
    for k in range(1, n + 1):
        assert f"INV-{k}" in t and f"Q{k}" in t
    assert sum(1 for b in m["intrari"] if b.get("compact")) == n - 1
    # partea de c.c. a reprezentantului: cantitatea × n în listă
    sep = next(a for a in _toate(m) if a.get("tip") == "separator_cc")
    assert sep["buc"] == n


def test_sub_prag_fara_grupare():
    m, r, c = _gen({"tip_schema": "cef", "kWp": 300, "invertoare": [{"n": 3, "Pn_kW": 100}]})
    assert not any(b.get("compact") for b in m["intrari"])


# ---------------------------------------------------------------- 7. contradicții
def test_sunny_island_cuplaj_cc_blocant():
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 8, "schema_pamant": "TN-C-S",
                    "bess": {"cuplaj": "cc", "producator": "SMA", "model": "Sunny Island 6.0H", "kWh": 10}})
    v = _cod(r, "V12", "BLOCANT")
    assert v and "Sunny Island" in v[0]["mesaj"] and "„ca”" in v[0]["remediere"]
    # fără cuplaj declarat: Sunny Island = c.a. (PCS propriu)
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 8, "schema_pamant": "TN-C-S",
                    "bess": {"producator": "SMA", "model": "Sunny Island 6.0H", "kWh": 10, "P_kW": 6}})
    assert r["rezultat"]["BESS"]["cuplaj"] == "ca"


def test_injectie_zero_vs_putere_evacuata():
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 15, "schema_pamant": "TN-C-S",
                    "limitare_injectie_kW": 0, "P_evacuata_kW": 15})
    v = [x for x in _cod(r, "V92", "AVERTISMENT") if "15 kW" in x["mesaj"]]
    assert v and "injecție zero" in v[0]["mesaj"]


def test_dublu_racord_blocant():
    r = calculeaza({"tip_schema": "cef", "racord": "tg_existent", "pt_Sn_kVA": 400, "pt_existent": False,
                    "invertoare": [{"n": 3, "Pn_kW": 100}]})
    assert any("un singur punct de racord" in v["mesaj"] for v in _cod(r, "V12", "BLOCANT"))


# ---------------------------------------------------------------- 8. măsura pe MT
def test_masura_mt_celula_si_fara_tc_jt():
    m, r, c = _gen({"tip_schema": "cef", "pt_Sn_kVA": 1000, "pt_existent": False, "masura": "MT", "kWp": 950,
                    "invertoare": [dict(HUAWEI_100, n=8, Pn_kW=100)], "L_racord_m": 30})
    z = r["rezultat"]
    assert z["masura"]["loc"] == "MT" and z["PT"]["celule_mt"]["masura"] and "TC" not in z
    apq = m["plecari"][0]["aparate"]
    assert not any(a.get("tip") == "tc" for a in apq)
    pt = m["plecari"][0]["copii"][0]["aparate"]
    refs = [a.get("ref") for a in pt]
    assert refs.index("QT") < refs.index("QM") < refs.index("QL")
    qm = pt[refs.index("QM")]
    assert qm["laterale"][0]["tip"] == "contor" and "MT" in qm["laterale"][0]["lista"][0]


def test_masura_mt_din_celule_mt_si_fara_pt_blocant():
    r = calculeaza(dict(CEF_16, pt_Sn_kVA=2000, celule_mt=["linie", "masura", "trafo"]))
    assert r["rezultat"]["masura"]["loc"] == "MT"
    r = calculeaza({"tip_schema": "cef", "kWp": 100, "invertoare": [{"n": 1, "Pn_kW": 100}], "masura": "MT"})
    assert _cod(r, "V12", "BLOCANT")
    assert _cod(calculeaza(dict(CEF_16, pt_Sn_kVA=2000, masura="abc")), "V12", "BLOCANT")
