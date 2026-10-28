"""E2 (28.10.2026) — motorul și documentele generate: deciziile proprietarului (GE în regim GE, limitarea la PCC),
funcționalitățile preluate de la concurență (tabel de cabluri, fișa de reglaje + Ik, carcasa DIN, pierderi, SPD, curbe,
PVGIS, „tipic pentru N”, import Excel / CSV, galerie), modelele de documente (dosar de racordare, caiet de sarcini) și
restanțele D4 (CEF 50 kW, PTA lista_pe, notația CYAbY / ACYAbY)."""
import io
import json
import os
import zipfile

import pytest

from engine import constructor, validare, memoriu
from engine import documente_tabele as dt, documente_protectii as dp, documente_racordare as dr, documente_caiet as dc
from engine import pvgis, import_circuite as ic, galerie
from engine.calc import calculeaza, norme
from engine.documente_doc import Document, Camp, docx_disponibil

GE_SIG = {"tip_schema": "ge_ats", "Sn_GE_kVA": 100, "P_sarcina_kW": 60, "consumatori": [{"nume": "Pompa incendiu", "P_kW": 15}]}
CEF_MARE = {"tip_schema": "cef", "kWp": 1200, "invertoare": [{"n": 11, "Pn_kW": 100}], "pt_Sn_kVA": 1000}
PROS = {"tip_schema": "prosumator", "retea": "tri", "kWp": 12, "In_Q_bransament_A": 25,
        "invertoare": [{"n": 1, "Pn_kW": 10, "producator": "Huawei", "model": "SUN2000-10KTL-M1"}],
        "string": {"n_module": 22, "modul": {"producator": "JA Solar", "model": "JAM54S30-410", "Pmax_W": 410,
                                             "Voc_V": 37.2, "Isc_A": 13.9, "Vmpp_V": 31.2, "Impp_A": 13.1}}}
TG = {"tip_schema": "tablou", "P_kW": 120, "L_alimentare_m": 40,
      "plecari": [{"nume": "TD-1", "copii": [{"nume": "Hală", "In_A": 32}, {"nume": "Birouri", "In_A": 16}]},
                  {"nume": "TD-2", "In_A": 63}, {"nume": "Pompe", "P_kW": 30}]}


def _v(r, cod, nivel=None):
    return [v for v in r["verificari"] + r.get("info", []) if v["cod"] == cod and (nivel is None or v["nivel"] == nivel)]


# ------------------------------------------------------------------------------------------- 1. GE: protecția în regim GE
def test_ge_fara_alegere_blocant_cu_doua_optiuni_explicate():
    r = calculeaza(GE_SIG)
    b = [v for v in r["verificari"] if v["nivel"] == "BLOCANT" and v["cod"] in ("V85", "V97")]
    assert b and r["blocheaza_export"]
    for v in b:
        assert [o["valoare"] for o in v["optiuni"]] == ["excitatie", "echipotential"]
        assert v["camp"] == "ge_protectie"
        assert "3·In" in v["remediere"] and "2 s" in v["remediere"] and "415.2" in v["remediere"]
        for o in v["optiuni"]:
            assert o["cand"] and o["implica"] and o["desen"]      # când, ce implică, ce se desenează
    assert r["rezultat"]["protectie_regim_GE"]["solutie"] is None


@pytest.mark.parametrize("sol", ["excitatie", "echipotential"])
def test_ge_cu_alegere_exportabil(sol):
    r = calculeaza(dict(GE_SIG, ge_protectie=sol))
    assert not r["blocheaza_export"], [v["mesaj"] for v in r["verificari"] if v["nivel"] == "BLOCANT"]
    p = r["rezultat"]["protectie_regim_GE"]
    assert p["solutie"] == sol and p["desen"]
    if sol == "excitatie":
        assert p["Ik_sustinut_A"] == pytest.approx(3 * r["rezultat"]["In_G_A"]) and p["t_sustinut_s"] == 2.0
        assert r["rezultat"]["Ik1_regim_GE_A"] == pytest.approx(3 * r["rezultat"]["In_G_A"])


def test_ge_campurile_vechi_raman_compatibile():
    assert not calculeaza(dict(GE_SIG, legaturi_echipotentiale=True))["blocheaza_export"]
    assert calculeaza(dict(GE_SIG, legaturi_echipotentiale=True))["rezultat"]["protectie_regim_GE"]["solutie"] == "echipotential"


def test_ge_alegerea_apare_in_note_si_memoriu():
    m, r = constructor.genereaza(dict(GE_SIG, ge_protectie="echipotential"))
    assert any("415.2" in n for n in m["note"])
    h = memoriu.genereaza_html(m, r)
    assert "Protecția la contact indirect în regim GE" in h and "Legături echipotențiale" in h
    assert not validare.valideaza(m)["blocheaza"]


# ------------------------------------------------------------------------------------------- 2. CEF peste trafo: PCC
def test_cef_peste_trafo_fara_limitare_blocant_cu_propunere():
    r = calculeaza(CEF_MARE)
    v = _v(r, "V67", "BLOCANT")[0]
    prop = 1000 * norme.PCC_COSFI * norme.PCC_FACTOR
    assert v["propunere"] == {"camp": "limitare_PCC_kW", "valoare": float(int(prop // 5) * 5)}
    assert "limitare_PCC_kW" in v["remediere"]


def test_cef_limitare_pcc_avertisment_nu_blocant():
    r = calculeaza(dict(CEF_MARE, limitare_PCC_kW=800))
    assert not r["blocheaza_export"]
    v = _v(r, "V67", "AVERTISMENT")[0]
    assert "PCC" in v["mesaj"] and "800" in v["mesaj"] and "EMS" in v["mesaj"]
    lp = r["rezultat"]["limitare_PCC"]
    assert lp["aplicata"] and lp["P_kW"] == 800 and lp["propunere_kW"] == 855
    assert r["rezultat"]["limitare_injectie"]["P_kW"] == 800          # lanțul EMS + analizor la PCC se desenează


def test_cef_limitare_pcc_insuficienta_ramane_blocant():
    r = calculeaza(dict(CEF_MARE, limitare_PCC_kW=1000))
    v = _v(r, "V67", "BLOCANT")[0]
    assert "depășește" in v["mesaj"] and v["propunere"]["valoare"] == 855


def test_cef_pcc_nota_pe_plansa():
    m, r = constructor.genereaza(dict(CEF_MARE, limitare_PCC_kW=800))
    assert any("PCC" in n and "800" in n for n in m["note"])
    assert not validare.valideaza(m)["blocheaza"]


# ------------------------------------------------------------------------------------------- 3. tabele, carcasă, pierderi
def test_tabel_cabluri_ref_unic_si_valori_din_calcul():
    m, r = constructor.genereaza(TG)
    t = dt.tabel_cabluri(m, r)
    refs = [x["ref"] for x in t["randuri"]]
    assert len(refs) == len(set(refs)) and "C1" in refs and "W2.1" in refs
    w = next(x for x in t["randuri"] if x["ref"] == "W2.1")
    assert w["de_la"] == "TD-1" and w["la"] == "Hală" and w["Ib_A"] == 32 and w["Iz_A"] >= w["Ib_A"]
    assert w["protectie"].startswith("Q2.1") and w["tip"] == "CYY-F" and w["L_m"] == 25
    assert all(x["din_calcul"] for x in t["randuri"])
    x = dt.tabel_xlsx(t, m["cartus"])
    assert x[:2] == b"PK"
    assert "<table>" in dt.tabel_html(t, m["cartus"])


def test_fisa_reglaje_si_ik_pe_noduri():
    m, r = constructor.genereaza(TG)
    f = dt.fisa_reglaje(m, r)
    q1 = next(x for x in f["randuri"] if x["ref"] == "Q1")
    assert q1["Ir_A"] == 200 and q1["Ii_A"] == 2000 and q1["Ik3max_kA"] > 0 and q1["Ik1min_A"] > 0
    q21 = next(x for x in f["randuri"] if x["ref"] == "Q2.1")
    assert q21["curba"] == "C" and q21["Ii_A"] == 320          # C32 → 10·In
    assert len(f["ik_noduri"]) >= 5 and all(n["Ik3max_origine_kA"] for n in f["ik_noduri"])
    assert len({x["ref"] for x in f["randuri"]}) == len(f["randuri"])


def test_fisa_reglaje_cef_cu_protectia_de_interfata():
    m, r = constructor.genereaza({"tip_schema": "cef", "kWp": 240, "invertoare": [{"n": 4, "Pn_kW": 50}]})
    f = dt.fisa_reglaje(m, r)
    assert f["protectie_interfata"] and f["protectie_interfata"]["randuri"]
    qg = next(x for x in f["randuri"] if x["ref"] == "QG")
    assert qg["Isd_A"] and qg["curba"].startswith("electronic")


def test_carcasa_module_din_si_rezerva():
    d = {"tip_schema": "locuinta", "retea": "mono", "alimentare": {"tip": "bransament_existent"},
         "circuite": [{"nume": f"Prize {i}", "receptor": "prize"} for i in range(6)] + [{"nume": "Iluminat", "receptor": "iluminat"}]}
    m, _ = constructor.genereaza(d)
    c = dt.dimensionare_carcasa(m, 25)
    assert c["module_aparate"] > 0 and c["module_cu_rezerva"] >= c["module_aparate"] * 1.25 - 1e-9
    assert c["capacitate"] >= c["module_cu_rezerva"] and c["randuri"] >= 1 and "IP" in c["carcasa_propusa"]
    assert dt.dimensionare_carcasa(m, 50)["rezerva_pct"] == 30 and dt.dimensionare_carcasa(m, 5)["rezerva_pct"] == 20
    mt, _ = constructor.genereaza(TG)                    # MCCB / NH → dulap metalic cu placă de montaj
    assert "metalic" in dt.dimensionare_carcasa(mt)["carcasa_propusa"]


def test_pierderi_cabluri_cc_ca_si_energie():
    m, r = constructor.genereaza(dict(PROS, productie_specifica_kWh_kWp=1250, cablu_cc={"S_fortat": 6, "L_m": 20}))
    p = dt.pierderi_cabluri(m, r)
    assert p["aplicabil"] and p["productie_kWh_kWp"] == 1250 and p["energie_an_kWh"] == pytest.approx(12 * 1250)
    assert p["cc"]["S_mm2"] == 6 and p["cc"]["L_m"] == 20
    # I²R c.c.: n_stringuri × Impp² × ρ70·2L/S
    n = p["cc"]["n_stringuri"]
    assert p["cc"]["P_pierderi_kW"] == pytest.approx(n * 13.1 ** 2 * norme.RHO_70["Cu"] * 40 / 6 / 1000)
    assert 0 < p["ca"]["pct"] < 2 and 0 < p["energie_pierduta_pct"] < 2
    assert dt.pierderi_cabluri(*constructor.genereaza(TG))["aplicabil"] is False


def test_grupuri_tipice_invertoare_identice():
    m, _ = constructor.genereaza({"tip_schema": "cef", "kWp": 600, "invertoare": [{"n": 5, "Pn_kW": 100}]})
    g = m["grupuri_tipice"]
    assert g[0]["n"] == 5 and g[0]["tipic"] == "INV-1" and g[0]["reprezinta"][-1] == "INV-5" and "TIPIC" in g[0]["eticheta"]
    m2, _ = constructor.genereaza({"tip_schema": "cef", "kWp": 600, "invertoare": [{"n": 5, "Pn_kW": 100}],
                                   "grupare_invertoare": False})
    assert "grupuri_tipice" not in m2


# ------------------------------------------------------------------------------------------- SPD și curbe
def test_spd_evaluare_443_si_712():
    e = dp.evaluare_spd({"tip_schema": "tablou", "evaluare_spd": {"mediu": "urban", "Ng": 1, "L_PCL_km": 0.5}})
    assert e["CRL"] == pytest.approx(850 / 0.5) and e["ca"]["decizie"] != "NECESAR"
    e = dp.evaluare_spd({"tip_schema": "tablou", "evaluare_spd": {"consecinte": "viata", "mediu": "urban", "Ng": 1,
                                                                   "L_PCL_km": 0.1}})
    assert e["ca"]["necesar"] and "443.4" in e["temei"]
    e = dp.evaluare_spd({"tip_schema": "prosumator", "evaluare_spd": {"LPS": True, "Ng": 4, "L_cc_m": 25}})
    assert e["ca"]["tip"] == "T1+T2" and e["cc"]["Lcrit_m"] == pytest.approx(115 / 4) and not e["cc"]["L_m"] >= e["cc"]["Lcrit_m"]
    assert e["cc"]["necesar"]                                      # LPS → SPD c.c. oricum
    e = dp.evaluare_spd({"tip_schema": "cef", "evaluare_spd": {"Ng": 2, "L_cc_m": 120}})
    assert e["cc"]["Lcrit_m"] == 100 and e["cc"]["necesar"]
    e = dp.evaluare_spd({"tip_schema": "cef", "evaluare_spd": {"Ng": 2, "L_cc_m": 50}})
    assert not e["cc"]["necesar"]


def test_spd_neconcordanta_cu_plansa():
    m, _ = constructor.genereaza(TG)
    assert dp.evaluare_spd(dict(TG, evaluare_spd={"LPS": True}), m)["neconcordante"] == []      # TG are T1+T2
    m["bara"]["laterale"] = []
    assert dp.evaluare_spd(dict(TG), m)["neconcordante"]


def test_curbe_benzi_monotone_si_conforme():
    c = dp.curba_mcb(16, "C")
    assert all(a <= b + 1e-12 for a, b in zip(c["t_min_s"], c["t_max_s"]))
    i = c["I_A"]
    k = min(range(len(i)), key=lambda x: abs(i[x] - 2.55 * 16))    # 2,55·In: 1 … 60 s
    assert 0.5 < c["t_min_s"][k] <= 2 and 30 < c["t_max_s"][k] <= 70
    assert all(t <= 0.1 for x, t in zip(i, c["t_max_s"]) if x >= 10 * 16 * 1.0001)   # C: ≤ 0,1 s peste 10·In
    g = dp.curba_gg(63)
    assert all(a >= b for a, b in zip(g["t_max_s"], g["t_max_s"][1:]))
    e = dp.curba_electronic(400, 400, 10, 2000, 0.2, 4800)
    assert min(t for x, t in zip(e["I_A"], e["t_max_s"]) if 2300 < x < 4300) <= 0.25 + 1e-9
    m, r = constructor.genereaza(TG)
    cc = dp.curbe_timp_curent(m, r)
    assert {"amonte": "Q2", "aval": "Q2.1"} in cc["perechi"] and len(cc["aparate"]) >= 5


# ------------------------------------------------------------------------------------------- PVGIS
RASPUNS_PVGIS = {"inputs": {"location": {"latitude": 47.05, "longitude": 21.93}, "pv_module": {"peak_power": 10, "system_loss": 14},
                            "mounting_system": {"fixed": {"slope": {"value": 30}, "azimuth": {"value": 0}}}},
                 "outputs": {"monthly": {"fixed": [{"month": i, "E_m": 1000.0} for i in range(1, 13)]},
                             "totals": {"fixed": {"E_y": 12345.6, "H(i)_y": 1600, "l_total": -20.1}}},
                 "meta": {"version": "5.3"}}


def test_pvgis_raspuns_offline_si_url(tmp_path, monkeypatch):
    r = pvgis.din_raspuns(json.dumps(RASPUNS_PVGIS), 10)
    assert r["kWh_an"] == 12345.6 and r["kWh_kWp_an"] == pytest.approx(1234.56) and len(r["lunar"]) == 12
    assert "kWh/an" in pvgis.paragraf_memoriu(r)
    assert pvgis.din_valoare(1250, 8)["kWh_an"] == 10000
    with pytest.raises(ValueError):
        pvgis.din_valoare(5000, 8)
    assert "aspect=0" in pvgis.cerere_url(47, 21, 10).replace("aspect=0.0", "aspect=0")
    monkeypatch.setattr(pvgis, "CACHE", tmp_path / "c.json")
    monkeypatch.setattr(pvgis, "DATE", tmp_path)
    o = pvgis.estimeaza(47.05, 21.93, 10, offline=True)
    assert o["necesita_valoare"] and o["url"].startswith(pvgis.URL_API)

    class F:
        def __init__(self, b):
            self.b = b

        def read(self):
            return self.b

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    rasp1 = json.loads(json.dumps(RASPUNS_PVGIS))
    rasp1["outputs"]["totals"]["fixed"]["E_y"] = 1234.56
    monkeypatch.setattr(pvgis.urllib.request, "urlopen", lambda *a, **k: F(json.dumps(rasp1).encode()))
    a = pvgis.estimeaza(47.05, 21.93, 10)
    assert a["kWh_an"] == pytest.approx(12345.6)
    monkeypatch.setattr(pvgis.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("fără rețea")))
    b = pvgis.estimeaza(47.05, 21.93, 20)                       # din cache, scalat
    assert "cache" in b["sursa"] and b["kWh_an"] == pytest.approx(2 * 12345.6)
    assert pvgis.estimeaza(45.0, 25.0, 10)["necesita_valoare"]


# ------------------------------------------------------------------------------------------- import Excel / CSV, galerie
def test_import_model_xlsx_si_csv():
    x = ic.model_xlsx()
    r = ic.importa(x)
    assert r["n"] == 3 and r["circuite"][0]["receptor"] == "iluminat" and r["circuite"][2]["faza"] == "3F"
    csv = ("Nr;Denumire;Tip;P[kW];L (m);Faza;Pozare;In\n1;Lumini;iluminat;0,6;20;L1;B2;\n"
           "2;Wallbox;Statie incarcare;7,4 kW;30;3F;D1;32 A\n3;Boiler;;2000 W;10;;;\n4;X;necunoscut;1;;Q;Z;\nTotal;;;11;;;;\n")
    r = ic.importa(csv.encode("cp1250"), "locuinta")
    c = r["circuite"]
    assert [x["receptor"] for x in c] == ["iluminat", "vehicul_electric", "boiler", "alt_circuit"]
    assert c[1]["In_A"] == 32 and c[2]["P_kW"] == 2 and c[1]["cablu"] == {"metoda": "D1"}
    assert len(r["avertismente"]) == 3 and r["ignorate"] and "plecari" not in r
    res = calculeaza({"tip_schema": "locuinta", "retea": "tri", "alimentare": {"tip": "bransament_existent", "In_Q_bransament_A": 40},
                      "circuite": c})
    assert not any(v["cod"] == "V12" and v["nivel"] == "BLOCANT" for v in res["verificari"])
    with pytest.raises(ValueError):
        ic.importa(b"a;b;c\n1;2;3\n")


def test_galerie_adauga_aplica_sterge(tmp_path, monkeypatch):
    monkeypatch.setattr(galerie, "FISIER", tmp_path / "galerie.json")
    e = galerie.adauga({"nume": "Bucătărie", "tip": "tablou", "date": {"circuite": [{"nume": "Plită", "receptor": "plita"}],
                                                                       "_uid": 3}})["element"]
    assert e["tip_schema"] == "locuinta" and "_uid" not in e["date"]
    assert len(galerie.citeste()["elemente"]) == 1
    i = galerie.aplica(e, {"tip_schema": "locuinta", "circuite": [{"nume": "Iluminat"}]})
    assert [c["nume"] for c in i["circuite"]] == ["Iluminat", "Plită"]
    with pytest.raises(ValueError):
        galerie.adauga({"nume": "", "tip": "circuit", "date": {"a": 1}})
    galerie.sterge(e["id"])
    assert galerie.citeste()["elemente"] == []


# ------------------------------------------------------------------------------------------- 4. documente
def test_document_marcheaza_campurile():
    d = Document("T").legenda().campuri([("a", Camp("x")), ("b", Camp(None))])
    assert d.numar_campuri() == {"completate": 1, "de_completat": 1}
    h = d.html()
    assert "class='d'" in h and "class='m'" in h and "(de completat)" in h


def test_dosar_racordare_prosumator():
    m, r = constructor.genereaza(PROS, cartus={"beneficiar": "Ion Popescu", "adresa": "Sântandrei, jud. Bihor"})
    docs, d = dr.dosar({"dosar": {"solicitant": {"telefon": "0740000000"}}}, m, r)
    assert [n for n, _ in docs][0] == "01_Cerere_de_racordare" and len(docs) == 4
    h = docs[0][1].html()
    assert "Ord. ANRE nr. 19/2022" in h and "Ion Popescu" in h and "SUN2000-10KTL-M1" in h and "0740000000" in h
    assert "(de completat)" in h                                   # CNP / CUI etc.
    f = docs[1][1].html()
    assert "12 kWp" in f and "10 kW" in f
    assert "SR EN IEC 61215" in docs[2][1].html() and "SR EN 50549-1" in docs[2][1].html()
    assert "art. 326" in docs[3][1].html()
    rez = dr.rezumat({}, m, r)
    assert all(x["completate"] > 0 for x in rez["documente"])
    z = zipfile.ZipFile(io.BytesIO(dr.dosar_zip({}, m, r, plansa_pdf=b"%PDF-1.4")))
    ext = ".docx" if docx_disponibil() else ".html"
    assert "01_Cerere_de_racordare" + ext in z.namelist() and "05_Schema_monofilara.pdf" in z.namelist()


def test_caiet_de_sarcini_structura_si_neutru_de_marca():
    m, r = constructor.genereaza(PROS)
    doc = dc.caiet_sarcini({}, m, r)
    h = doc.html()
    for cap in ("1. Generalități", "2. Standarde", "3. Materiale și echipamente", "4. Execuția", "5. Verificări și probe",
                "6. Recepția", "7. Punerea în funcțiune", "8. Documentația as-built"):
        assert cap in h
    assert "SR HD 60364-7-712" in h and "SR EN 60898-1" in h
    i3, i4 = h.index("3. Materiale"), h.index("4. Execuția")
    assert "SUN2000" not in h[i3:i4] and "JA Solar" not in h[i3:i4]       # neutru de marcă
    if docx_disponibil():
        assert doc.docx()[:2] == b"PK"


# ------------------------------------------------------------------------------------------- 5. restanțe D4
def test_cef_kw_fara_invertoare_presupune_implicit():
    r = calculeaza({"tip_schema": "cef", "Pn_total_kW": 50})
    assert not r["blocheaza_export"]
    assert r["rezultat"]["sume"]["Pn_total_kW"] == 50 and len(r["rezultat"]["invertoare"]) == 1
    assert any("fără invertoare declarate" in x and "50" in x for x in r["presupus"])
    r = calculeaza({"tip_schema": "cef", "Pn_total_kW": 250})
    assert len(r["rezultat"]["invertoare"]) == 3 and r["rezultat"]["sume"]["Pn_total_kW"] == pytest.approx(250, abs=0.01)


def test_cef_50kw_interpretorul_nu_mai_intreaba_blocant():
    from engine import interpretor
    it = interpretor.interpreteaza("CEF 50 kW", foloseste_llm=False)
    assert it["actiune"] != "refuza" and it["intrare_fizica"]["Pn_total_kW"] == 50
    assert not any("Câte invertoare" in q for q in it.get("intrebari") or [])
    assert any("PRESUPUS" in x for x in it["presupus"])


def test_pta_lista_pe_nu_mai_e_suprascrisa():
    m, _ = constructor.genereaza({"tip_schema": "pt", "Sn_kVA": 100, "pt_aerian": True, "plecari": [{"nume": "TD-1", "In_A": 63}]})
    assert "PTA" in m["lista_pe"][0] and "4 Ω" in m["lista_pe"][0]
    m, _ = constructor.genereaza({"tip_schema": "pt", "Sn_kVA": 630, "plecari": [{"nume": "TD-1", "In_A": 250}]})
    assert "1 Ω" in m["lista_pe"][0]


def test_notatia_cablurilor_cyaby_dupa_standard():
    assert norme.TIP_CABLU[("Cu", "PVC", True)] == "CYAbY" and norme.TIP_CABLU[("Al", "PVC", True)] == "ACYAbY"
    m, r = constructor.genereaza(TG)
    s = json.dumps(m, ensure_ascii=False) + json.dumps(r, ensure_ascii=False, default=str)
    assert "ACYAbY" in s and "ACYABY" not in s and "CYABY" not in s
    assert norme.material_izolatie_din_denumire("ACYAbY 4x25") == ("Al", "PVC")
    assert norme.material_izolatie_din_denumire("cyaby") == ("Cu", "PVC")
    from engine.validare import _cablu_din_text
    assert _cablu_din_text("2 × (ACYAbY 4×120 mm² + FY 1×35 mm² (PE))")["material"] == "Al"
    from engine.constructor import fe180
    assert fe180("CYAbY 5×6 mm² + FY 1×6 mm² (PE)").startswith("NHXH FE180/E90 5×6")


def test_documente_endpoint_si_exporturi(tmp_path):
    import app
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", 0), app.H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        m, _ = constructor.genereaza(PROS)

        def post(p, body):
            req = urllib.request.Request(f"http://127.0.0.1:{port}{p}", data=json.dumps(body).encode(), method="POST")
            with urllib.request.urlopen(req, timeout=120) as f:
                return f.status, f.headers.get("Content-Type"), f.read()
        st, _, b = post("/api/documente", m)
        j = json.loads(b)
        assert st == 200 and {"tabel_cabluri", "fisa_reglaje", "carcasa", "pierderi", "spd", "dosar_racordare"} <= set(j)
        st, ct, b = post("/api/export/tabele", m)
        assert st == 200 and b[:2] == b"PK"
        st, ct, b = post("/api/export/caiet_sarcini", m)
        assert st == 200 and (b[:2] == b"PK" or b"<html" in b[:200])
        st, _, b = post("/api/pvgis/raspuns", {"kWh_kWp_an": 1200, "kWp": 10})
        assert json.loads(b)["kWh_an"] == 12000
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/import/model_circuite") as f:
            assert f.read()[:2] == b"PK"
    finally:
        srv.shutdown()


# ------------------------------------------------------------------------------------------- tab-ul „Documente” (chei)
@pytest.mark.parametrize("schema", ["tg", "prosumator", "locuinta"])
def test_documente_pe_chei_previzualizare_si_export(schema):
    from engine import documente_vederi as V
    d = {"tg": TG, "prosumator": dict(PROS, productie={"kWh_kWp_an": 1250, "lunar": [80] * 12, "sursa": "PVGIS 5.2 (JRC)"}),
         "locuinta": {"tip_schema": "locuinta", "retea": "mono", "alimentare": {"tip": "bransament_existent"},
                      "circuite": [{"nume": "Iluminat", "receptor": "iluminat"}, {"nume": "Prize", "receptor": "prize"}]}}[schema]
    m, r = constructor.genereaza(d)
    pv = schema == "prosumator"
    for k in V.CHEI_PREVIZUALIZARE:
        if k in ("pierderi", "productie") and not pv:
            with pytest.raises(V.Indisponibil):
                V.previzualizare(k, {}, m, r)
            continue
        ct, b = V.previzualizare(k, {}, m, r)
        if "json" in ct:
            j = json.loads(b)
            assert j["titlu"] and (j.get("randuri") or j.get("tabele"))
            if j.get("coloane"):
                assert all(len(rw) == len(j["coloane"]) for rw in j["randuri"])
        else:
            assert ("<svg" in b) if "svg" in ct else ("<html" in b)
    for k in V.CHEI_EXPORT:
        if k in ("pierderi", "productie") and not pv:
            continue
        ct, b, suf = V.export(k, {}, m, r)
        assert b and suf.startswith("_")
    if pv:
        j = json.loads(V.previzualizare("productie", {}, m, r)[1])
        assert j["randuri"][-1] == ["AN", 1250, 15000]                 # 12 kWp × 1250
        assert "Producția estimată" in memoriu.genereaza_html(m, r)
        assert dt.pierderi_cabluri(m, r)["productie_kWh_kWp"] == 1250  # calc.productie folosit la pierderi


def test_etichete_si_cerere_consum():
    from engine import documente_vederi as V
    m, r = constructor.genereaza(PROS)
    h, n = V.etichete_html(m)
    assert n >= 2 and "două surse" in h and "17,5" not in h.split("<body>")[0]
    m2, r2 = constructor.genereaza(TG)
    doc = dr.cerere_consum(dr.date_proiect({}, m2, r2))
    assert "LOC DE CONSUM" in doc.html() and doc.numar_campuri()["completate"] > 0


def test_cai_noi_si_in_varianta_web(tmp_path, monkeypatch):
    """web/web_api.py rulează același handler: căile /api/documente/<cheie> și /api/export/<cheie>?format= merg și în Pyodide"""
    import importlib
    import sys as _s
    monkeypatch.setenv("SM_DATE", str(tmp_path))
    _s.path.insert(0, str(os.path.join(os.path.dirname(__file__), "..", "web")))
    wa = importlib.import_module("web_api")
    m, _ = constructor.genereaza(TG)
    st, hd, b = wa.cerere("POST", "/api/documente/cabluri", json.dumps(m).encode())
    assert st == 200 and json.loads(b)["randuri"]
    st, hd, b = wa.cerere("POST", "/api/export/cabluri", json.dumps(m).encode())
    assert st == 200 and b[:2] == b"PK"
    st, hd, b = wa.cerere("POST", "/api/export/tabel_cabluri?format=xlsx", json.dumps(m).encode())
    assert st == 200 and b[:2] == b"PK"
    st, hd, b = wa.cerere("POST", "/api/documente/necunoscut", json.dumps(m).encode())
    assert st == 404
