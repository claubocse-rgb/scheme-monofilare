"""r12 — motorul și desenul după verificarea pe proiecte reale (teste/reale/raport.md, „Top 15” 5–15).
Valorile sunt ANONIMIZATE / sintetice (nu provin din proiectele reale): cascade CEF cu tablouri intermediare, tipurile
protecțiilor CEF (gG / MPR, MCB, MCCB; QG electronic / motorizat cu reglaje), tabelul PI, monitorizarea (smart meter,
SmartLogger, RS485, contor de producție), PT / PC conform OD, C0 din tronsoane, cablul MT declarat, pachetul de planșe A3,
cartușul cu „Aprobat”, bugul `cablu_inv.S_fortat` la prosumator."""
import io
import os
import sys
import zipfile

import pytest

RAD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAD)

from engine import constructor, layout, planse  # noqa: E402
from engine.calc import calculeaza  # noqa: E402
from engine.canvas import Text  # noqa: E402
from engine.topologie import coliziuni, verifica_topologie  # noqa: E402

INV30 = {"producator": "Fronius", "model": "Tauro 30-3-D", "Pn_kW": 30, "Iac_max_A": 45.0}
INV60 = {"producator": "Sungrow", "model": "SG60CX", "Pn_kW": 60, "Iac_max_A": 90.0}
AL = {"material": "Al", "izolatie": "XLPE", "metoda": "E"}


def _bl(r, cod=None):
    return [v for v in r["verificari"] if v["nivel"] == "BLOCANT" and (cod is None or v["cod"] == cod)]


def _cod(r, cod, nivel=None):
    return [v for v in r["verificari"] if v["cod"] == cod and (nivel is None or v["nivel"] == nivel)]


def _toate(m):
    out = []

    def br(b):
        for a in b.get("aparate") or []:
            out.append(a)
            out.extend(a.get("laterale") or [])
        for a in b.get("aparate_tablou") or []:
            out.append(a)
            out.extend(a.get("laterale") or [])
        for c in b.get("copii") or []:
            br(c)
    for b in constructor.ramuri_model(m):
        br(b)
    return out


def _txt(c):
    return " ".join(it.s for it in c.items if isinstance(it, Text))


def _gen(inp, fara_coliziuni=True):
    m, r = constructor.genereaza(inp)
    c = layout.build(m)
    if fara_coliziuni:
        assert coliziuni(c) == []
    return m, r, c


CASCADA = {
    "tip_schema": "cef", "retea": "tri", "schema_pamant": "TN-S", "kWp": 260,
    "tablouri_intermediare": [
        {"nume": "TE-Nord", "L_m": 25, "cablu": dict(AL, S_fortat=50), "prot_tip": "gG", "In_A": 100,
         "invertoare": [dict(INV30, n=2, L_m=8, prot_tip="MCB", protectie={"In_A": 63})]},
        {"nume": "TE-Sud", "L_m": 40, "cablu": dict(AL, S_fortat=70),
         "invertoare": [dict(INV30, n=2, L_m=12)]},
        {"nume": "TE-Est", "L_m": 30, "cablu": dict(AL, S_fortat=95), "prot_tip": "MCCB", "In_A": 200,
         "invertoare": [dict(INV60, n=2, L_m=10, prot_tip="MPR", protectie={"In_A": 100})]},
    ],
    "racord": "pt", "pt_Sn_kVA": 630, "pt_existent": True, "L_racord_m": 20,
    "cablu_C0": dict(AL, S_fortat=185, n_fortat=2),
    "QG": {"tip": "MCCB", "In_A": 400, "electronic": True, "motorizat": True, "Icu_kA": 36},
}


# ---------------------------------------------------------------- 5. cascade CEF
def test_cascada_trei_tablouri_calcul():
    r = calculeaza(CASCADA)
    z = r["rezultat"]
    te = z["tablouri_intermediare"]
    assert [t["nume"] for t in te] == ["TE-Nord", "TE-Sud", "TE-Est"]
    assert [t["unitati"] for t in te] == [["INV-1", "INV-2"], ["INV-3", "INV-4"], ["INV-5", "INV-6"]]
    assert all(t.get("C") and t.get("Q") for t in te)
    # protecțiile declarate ale plecărilor și ale invertoarelor
    assert te[0]["Q"]["tip"] == "gG" and te[0]["Q"]["In_A"] == 100
    assert te[2]["Q"]["tip"] == "MCCB" and te[2]["Q"]["In_A"] == 200
    inv = {x["obiect"]: x for x in z["invertoare"]}
    assert inv["INV-1"]["protectie"]["tip"] == "MCB" and inv["INV-1"]["protectie"]["In_A"] == 63
    assert inv["INV-5"]["protectie"]["tip"] == "gG" and inv["INV-5"]["protectie"]["In_A"] == 100
    assert inv["INV-1"]["tablou"] == 1 and inv["INV-6"]["tablou"] == 3
    # ΔU cumulat: C0 → C-TEk → cablul invertorului
    assert z["C0"]["dU_cumulat_pct"] < te[1]["C"]["dU_cumulat_pct"] < inv["INV-3"]["dU_cumulat_pct"]
    # QG la TEG: Ip ≥ Σ Iac al tuturor tablourilor; selectivitatea QG vs plecări și plecare vs invertoare
    assert z["QG"]["Ir_A"] >= z["sume"]["Iac_total_A"] and z["QG"]["decl"] == "EL" and z["QG"]["motorizat"]
    assert any(v["obiect"].startswith("QG vs QF") for v in r["verificari"] if v["cod"] in ("V41", "V42"))
    assert any(v["obiect"].startswith("QS1 vs INV-1") for v in r["verificari"] if v["cod"] in ("V41", "V42"))
    assert not _cod(r, "V96", "BLOCANT")


def test_cascada_desen_teg_si_tablouri():
    m, r, c = _gen(CASCADA)
    sec = m["bara"]["sectiuni"]
    assert [s["titlu"] for s in sec] == ["TE-Nord", "TE-Sud", "TE-Est"] and [s["n_in"] for s in sec] == [2, 2, 2]
    jn = m["jonctiune"]
    assert jn["carcasa"]["titlu"].startswith("TEG")
    refs = {a.get("ref") for a in _toate(m)}
    assert {"QS1", "QS2", "QS3", "QF1", "QF2", "QF3", "QG", "QPT"} <= refs
    # QFk desenat la capătul din TEG (aparat „jos” al coloanei de joncțiune)
    assert all(a.get("jos") for pl in m["plecari"] for a in pl["aparate"] if str(a.get("ref", "")).startswith("QF"))
    nume = {k["nume"] for k in c.meta["carcase"]}
    assert {"TE-Nord", "TE-Sud", "TE-Est"} <= nume and any(n.startswith("TEG") for n in nume)
    t = _txt(c)
    assert "C-TE1" in t and "C-TE3" in t and "C0" in t
    # cablurile plecărilor și C0 ajung în lista de materiale
    mats = " ".join(x["ref"] for x in m["materiale"])
    assert "C-TE" in mats and "C0" in mats
    assert not [v for v in verifica_topologie(m, c) if v["nivel"] == "BLOCANT"]


def test_n_tgd_cf_peste_doi_e_alias_pentru_tablouri_intermediare():
    inv = [dict(INV30, n=2, tgd=k) for k in (1, 2, 3, 4)]
    r = calculeaza({"tip_schema": "cef", "retea": "tri", "n_tgd_cf": 4, "invertoare": inv, "L_racord_m": 15})
    assert len(r["rezultat"]["tablouri_intermediare"]) == 4
    assert not _cod(r, "V96", "BLOCANT")


def test_cascada_tablou_inexistent_si_tablou_gol():
    r = calculeaza(dict(CASCADA, tablouri_intermediare=[{"nume": "A"}], invertoare=[dict(INV30, n=1, tablou=3)]))
    assert _bl(r, "V12")
    r = calculeaza({"tip_schema": "cef", "retea": "tri", "tablouri_intermediare": [{}, {}],
                    "invertoare": [dict(INV30, n=1, tablou=1)]})
    assert _bl(r, "V07")


def test_cascada_invertor_direct_pe_teg():
    inp = dict(CASCADA, invertoare=[dict(INV30, n=1, tablou=0, L_m=5)])
    m, r, c = _gen(inp)
    # invertorul din lista globală e INV-1 (direct pe TEG); cele din tablouri urmează
    assert [t["unitati"] for t in r["rezultat"]["tablouri_intermediare"]][0] == ["INV-2", "INV-3"]
    assert r["rezultat"]["invertoare"][0]["obiect"] == "INV-1" and "tablou" not in r["rezultat"]["invertoare"][0]
    assert any(s["titlu"].startswith("TEG — plecări directe") for s in m["bara"]["sectiuni"])


def test_cascada_cu_pt_nou_doua_trafo_refuzata():
    r = calculeaza(dict(CASCADA, pt_existent=False, n_trafo=2, pt_Sn_kVA=400))
    assert any(v["cod"] == "V96" for v in _bl(r))


# ---------------------------------------------------------------- 6. tipurile protecțiilor CEF
BAZA_V30 = {"tip_schema": "cef", "retea": "tri", "schema_pamant": "TN-C-S", "kWp": 140,
            "invertoare": [dict(INV60, n=2, L_m=10)], "racord": "pt", "pt_Sn_kVA": 1000, "pt_existent": True,
            "L_racord_m": 140, "cablu_C0": dict(AL, S_fortat=70, n_fortat=2), "In_QG_A": 200,
            "racord_In_Q_A": 250, "racord_Q_tip": "gG"}


def test_qg_electronic_isd_dupa_ik1min_scoate_v30_fals():
    r_tm = calculeaza(BAZA_V30)
    assert [v for v in _bl(r_tm, "V30") if v["obiect"] == "C0"]          # TM: Im = 10·In > Ik1min la capătul C0
    r_el = calculeaza(dict(BAZA_V30, QG={"electronic": True, "motorizat": True}))
    z = r_el["rezultat"]
    assert not [v for v in _bl(r_el, "V30") if v["obiect"] == "C0"]
    assert z["QG"]["decl"] == "EL" and z["QG"]["motorizat"]
    assert 1.2 * z["QG"]["Isd_A"] <= z["C0"]["Ik1min_capat_A"] + 1e-6
    m, _ = constructor.genereaza(dict(BAZA_V30, QG={"electronic": True, "motorizat": True}))
    qg = next(a for a in _toate(m) if a.get("ref") == "QG")
    assert "motorizat" in " ".join(qg["lista"]) and qg["lista"][0].startswith("Întreruptor de interfață")


def test_qg_reglaje_impuse_ir_isd_icu():
    r = calculeaza(dict(BAZA_V30, QG={"In_A": 250, "Ir_reglat": 0.8, "Isd_reglat": 4, "Icu_kA": 50}))
    q = r["rezultat"]["QG"]
    assert q["Ir_A"] == pytest.approx(200) and q["Ir_fortat"]
    assert q["Isd_A"] == pytest.approx(800) and q["Isd_fortat"] and q["Icu_kA"] == 50
    r = calculeaza(dict(BAZA_V30, QG={"In_A": 250, "Ir_reglat": 0.2}))
    assert any(v["cod"] == "V12" and v["obiect"] == "QG" for v in _bl(r))
    r = calculeaza(dict(BAZA_V30, QG={"In_A": 250, "Icu_kA": 10}))
    assert _bl(r, "V33")


def test_protectie_invertor_mpr_mcb_mccb():
    for tip, asteptat, ap in (("MPR", "gG", "sep_fuzibil"), ("MCB", "MCB", "mcb"), ("MCCB", "MCCB", "mccb")):
        inp = dict(BAZA_V30, invertoare=[dict(INV60, n=2, L_m=10, prot_tip=tip, protectie={"In_A": 100})],
                   QG={"electronic": True})
        m, r = constructor.genereaza(inp)
        p = r["rezultat"]["invertoare"][0]["protectie"]
        assert p["tip"] == asteptat and p["In_A"] == 100
        assert next(a for a in _toate(m) if a.get("ref") == "Q1")["tip"] == ap


def test_ir_reglat_pe_invertor_si_pe_racord():
    inp = dict(BAZA_V30, invertoare=[dict(INV60, n=2, L_m=10, prot_tip="MCCB", protectie={"In_A": 125, "Ir_reglat": 0.8})],
               racord_Q_tip="MCCB", racord_In_Q_A=400, racord_Ir_A=0.6, racord_Icu_kA=36, QG={"electronic": True})
    z = calculeaza(inp)["rezultat"]
    assert z["invertoare"][0]["protectie"]["Ir_A"] == pytest.approx(100)
    assert z["Q_PT"]["Ir_A"] == pytest.approx(240)


def test_v20_cumulat_spune_amonte_si_cablu():
    inp = dict(BAZA_V30, invertoare=[dict(INV60, n=2, L_m=90, cablu=dict(AL, S_fortat=25))], QG={"electronic": True})
    r = calculeaza(inp)
    v = [x for x in _cod(r, "V20", "BLOCANT") if x["obiect"].startswith("INV")]
    assert v and "amonte" in v[0]["mesaj"] and "cumulat" in v[0]["mesaj"]


# ---------------------------------------------------------------- 7. tabelul PI
def test_tabel_pi_implicit_si_suprascris():
    m, _ = constructor.genereaza(BAZA_V30)
    tp = m["tabel_pi"]
    assert len(tp["randuri"]) >= 9 and "208/2018" in tp["sursa"]
    assert ["Tensiune maximă U> (59)", "1,15·Un", "0,5 s"] in tp["randuri"]
    m, _ = constructor.genereaza(dict(BAZA_V30, protectie_interfata={"ordin": "228/2018", "reglaje": {"U_max": ["1,10·Un", "0,2 s"]}}))
    assert "228/2018" in m["tabel_pi"]["sursa"] and ["Tensiune maximă U> (59)", "1,10·Un", "0,2 s"] in m["tabel_pi"]["randuri"]
    m, _ = constructor.genereaza(dict(BAZA_V30, protectie_interfata=False))
    assert not m.get("tabel_pi")
    c = layout.build(constructor.genereaza(BAZA_V30)[0])
    assert "PARAMETRI ȘI PROTECȚII INVERTOARE" in _txt(c)


# ---------------------------------------------------------------- 8. monitorizare și măsură
def test_smart_meter_smartlogger_rs485():
    inp = dict(BAZA_V30, QG={"electronic": True}, protectie_interfata={"releu": "Releu-X", "ups_VA": 1500},
               monitorizare={"smart_meter": {"model": "SM-1"}, "smartlogger": {"model": "LOG-1"}})
    m, r, c = _gen(inp)
    ap = _toate(m)
    tcs = next(a for a in ap if a.get("ref") == "TCS")
    assert 1443 <= tcs["param"]["primar_A"] <= 1600          # In trafo 1000 kVA = 1443 A → primul TC din serie
    lat = {l.get("ref"): l for l in tcs["laterale"]}
    assert lat["SL"]["legatura"] == "comunicatie" and lat["SM"]["legatura"] == "masura"
    assert sum(1 for a in ap if a.get("eticheta") == "RS485") == 2
    assert any(a.get("ref") == "UPS" for a in ap) and any(a.get("eticheta") == "PI" and "Releu-X" in a["spec"][0] for a in ap)
    t = _txt(c)
    assert "comunicație RS485" in t and "SM" in t
    assert any(it.layer == "RS485" for it in c.items if hasattr(it, "layer"))


def test_tc_smart_meter_declarat():
    m, _ = constructor.genereaza(dict(BAZA_V30, monitorizare={"smart_meter": {"TC_primar_A": 2000}}))
    assert next(a for a in _toate(m) if a.get("ref") == "TCS")["param"]["primar_A"] == 2000


PROS = {"tip_schema": "prosumator", "retea": "mono", "schema_pamant": "TN-C-S", "kWp": 5.2,
        "invertor": {"producator": "GoodWe", "model": "GW5000-NS", "Pn_kW": 5, "Iac_max_A": 22.8},
        "Pn_inv_kW": 5, "In_Q_bransament_A": 32, "L_inv_m": 4, "L_coloana_m": 30, "cablu_inv": {"material": "Cu", "S_fortat": 6}}


def test_prosumator_cablu_inv_s_fortat_respectat():
    r = calculeaza(PROS)
    inv = (r["rezultat"].get("invertoare") or [r["rezultat"].get("INV")])[0]
    assert inv["S_faza_mm2"] == 6
    m, _ = constructor.genereaza(PROS)
    assert "3×6" in m["intrari"][0]["cablu_ca"]["text"]


def test_prosumator_contor_productie_si_smart_meter():
    m, r, c = _gen(dict(PROS, contor_productie=True, monitorizare={"smart_meter": {"model": "SM-M"}, "rs485": True}))
    ap = m["intrari"][0]["aparate"]
    i_inv = next(i for i, a in enumerate(ap) if a["tip"] == "invertor")
    i_pp = next(i for i, a in enumerate(ap) if a.get("ref") == "PP")
    i_q = next(i for i, a in enumerate(ap) if a.get("ref") == "QI")
    assert i_inv < i_pp < i_q and ap[i_pp]["in_carcasa"] is False
    assert "PRODUSĂ" in ap[i_pp]["lista"][0]
    assert any(l.get("ref") == "SM" for a in _toate(m) for l in a.get("laterale") or [])
    assert "228/2018" in m["tabel_pi"]["sursa"]


# ---------------------------------------------------------------- 9. PT / PC conform OD
def test_pt_dg_intreruptor_si_compartimente():
    inp = {"tip_schema": "pt", "Sn_kVA": 400, "dg_intreruptor": True, "masura": "MT",
           "plecari": [{"nume": "TD-1", "In_A": 250}]}
    m, r = constructor.genereaza(inp)
    assert r["rezultat"]["celula_trafo"] == "intreruptor" and r["rezultat"]["dg"]
    ap = m["intrari"][0]["aparate"]
    refs = [a.get("ref") for a in ap]
    assert refs.index("Q1") < refs.index("QM") < refs.index("QR") < refs.index("Q2")
    assert {a.get("compartiment") for a in ap if a.get("ref") in ("Q1", "QM")} == {constructor.COMP_OD}
    assert {a.get("compartiment") for a in ap if a.get("ref") in ("QR", "Q2")} == {constructor.COMP_UT}
    q2 = next(a for a in ap if a.get("ref") == "Q2")
    assert "tor homopolar" in " ".join(q2["laterale"][0]["spec"])
    assert any(l.get("eticheta") == "RGDAT" for l in ap[0]["laterale"])
    c = layout.build(m)
    assert {k["nume"] for k in c.meta["carcase"] if k.get("compartiment")} == {constructor.COMP_OD, constructor.COMP_UT}
    assert coliziuni(c) == []


def test_od_e_distributie_implica_dg():
    r = calculeaza({"tip_schema": "pt", "Sn_kVA": 250, "OD": "E-Distribuție", "plecari": [{"nume": "TD", "In_A": 160}]})
    assert r["rezultat"]["celula_trafo"] == "intreruptor"


CEF_PT_NOU = {"tip_schema": "cef", "retea": "tri", "kWp": 700, "invertoare": [dict(INV60, n=8, L_m=40)],
              "racord": "pt", "pt_Sn_kVA": 800, "pt_existent": False, "L_racord_m": 15, "masura": "MT",
              "cablu_MT": {"tip": "NA2XS(F)2Y", "S_mm2": 95, "material": "Al", "L": 210}}


def test_cablu_mt_declarat_fara_sectiune_inventata():
    m, _ = constructor.genereaza(CEF_PT_NOU)
    t = str(m)
    assert "NA2XS(F)2Y" in t and "3 × 1 × 95 mm² Al" in t and "3 × 1 × 150 mm² Al" not in t
    m, _ = constructor.genereaza({k: v for k, v in CEF_PT_NOU.items() if k != "cablu_MT"})
    assert "3 × 1 × 150 mm² Al" not in str(m)
    cond, txt = constructor.text_cablu_mt({"tronsoane": [{"tip": "A", "S_mm2": 185, "L": 270}, {"tip": "B", "S_mm2": 95, "L": 35}]})
    assert "270 m" in txt and "35 m" in txt


def test_punct_de_conexiune_doua_linii_aar_utilizator_pi():
    inp = dict(CEF_PT_NOU, punct_conexiune={"celule_linie": 2, "aar": True, "servicii_proprii_kVA": 5},
               dg_intreruptor=True)
    m, r, c = _gen(inp)
    ap = _toate(m)
    refs = {a.get("ref") for a in ap}
    assert {"QU", "QL1", "QL2", "QM", "QSP", "TSP", "AAR", "QR"} <= refs
    qu = next(a for a in ap if a.get("ref") == "QU")
    assert any(l.get("eticheta") == "PI" for l in qu["laterale"])
    assert any(k["nume"] == "PUNCT DE CONEXIUNE (PC)" for k in c.meta["carcase"])
    assert not [v for v in verifica_topologie(m, c) if v["nivel"] == "BLOCANT"]


# ---------------------------------------------------------------- 11. C0 din tronsoane
def test_c0_din_doua_tronsoane():
    inp = dict(BAZA_V30, QG={"electronic": True}, L_racord_m=None)
    inp.pop("L_racord_m")
    inp["cablu_C0"] = {"tronsoane": [dict(AL, S_fortat=120, n_fortat=2, L=100),
                                     {"material": "Cu", "S_fortat": 95, "n_fortat": 2, "izolatie": "XLPE", "metoda": "E", "L": 12}]}
    r = calculeaza(inp)
    c0 = r["rezultat"]["C0"]
    assert [t["tronson"] for t in c0["tronsoane"]] == [1, 2]
    assert c0["L_m"] == pytest.approx(112)
    assert c0["dU_ramura_pct"] == pytest.approx(sum(t["dU_ramura_pct"] for t in c0["tronsoane"]))
    assert c0["tronsoane"][0]["material"] == "Al" and c0["tronsoane"][1]["material"] == "Cu"
    assert c0["Ik1min_capat_A"] < c0["tronsoane"][1]["Ik1min_capat_A"]       # capătul tabloului e mai departe
    assert "+" in c0["cablu"] and "(100 m)" in c0["cablu"]


# ---------------------------------------------------------------- 10. pachetul de planșe A3
def test_pachet_planse_a3():
    inp = dict(CASCADA, monitorizare=True, protectie_interfata={"ups_VA": 1000})
    m, _ = constructor.genereaza(inp)
    assert planse.cere_planse(inp) and not planse.cere_planse(dict(inp, planse=False))
    lst = planse.planse_din_model(m)
    coduri = [c for c, _ in lst]
    assert coduri[:3] == ["IE 07.1/FV", "IE 07.2/FV", "IE 07.3/FV"]
    assert {"IE 08/FV", "IE 09/FV", "IE 09.1/FV", "IE 11/FV"} <= set(coduri)
    for cod, mp in lst:
        c = layout.build(mp)
        assert c.w == 420.0 and mp["cartus"]["plansa"] == cod
    ca = dict(lst)["IE 09/FV"]
    assert not any(a.get("tip") == "string_pv" for b in ca["intrari"] for a in b["aparate"])
    assert ca["intrari"][0]["sursa"]["titlu"].startswith("Către INV-")
    cc = dict(lst)["IE 07.1/FV"]
    assert {t["titlu"] for t in cc["tabele"]} == {"MODEL PANOU SOLAR", "MODEL INVERTOR"} or cc["tabele"][0]["titlu"] == "MODEL INVERTOR"
    assert dict(lst)["IE 09.1/FV"].get("tabel_pi")
    z = zipfile.ZipFile(io.BytesIO(planse.pachet_planse_zip(lst, "test")))
    nume = z.namelist()
    assert "IE07_1-FV.svg" in nume and "IE09-FV.dxf" in nume and "CUPRINS.txt" in nume
    assert "<div class=\"p\">" in planse.html_multipagina([("<svg></svg>", 420, 297)])


# ---------------------------------------------------------------- 14. cartuș
def test_cartus_are_aprobat():
    m, _ = constructor.genereaza(dict(BAZA_V30, protectie_interfata=False))
    m["cartus"]["aprobat"] = "Ing. Aprobator"
    t = _txt(layout.build(m))
    assert "Aprobat" in t and "Ing. Aprobator" in t


def test_chei_noi_acceptate():
    inp = dict(CASCADA, monitorizare=True, protectie_interfata={"ordin": "228/2018"}, planse=True, OD="delgaz")
    r = calculeaza(inp)
    assert not [v for v in _bl(r, "V96") if "nu le folosește" in v["mesaj"]]


# ---------------------------------------------------------------- 12. PT — rezervă echipată
def test_pt_rezerva_echipata_fara_cablu_si_fara_sarcina():
    inp = {"tip_schema": "pt", "Sn_kVA": 250, "plecari": [{"nume": "Plecare CEF", "In_A": 250}] +
           [{"nume": f"R{k}", "In_A": 100, "rezerva": True} for k in (1, 2, 3)]}
    m, r = constructor.genereaza(inp)
    assert not _cod(r, "V62")
    assert r["rezultat"]["bilant"]["Pi_kW"] < 200
    rez = [pl for pl in m["plecari"] if (pl.get("sarcina") or {}).get("titlu") == "REZERVĂ"]
    assert len(rez) == 3 and all(not pl["cablu"]["text"] for pl in rez)
