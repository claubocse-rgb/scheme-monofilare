"""Integrare cap-coadă: intrare fizică → motor → schemă desenată → validare → export.

Invariante verificate pe toate cazurile golden (în afară de verificare_model):
* schema se generează, se desenează (SVG + DXF) și trece `audit()` DXF;
* `validare.valideaza` blochează EXACT când motorul blochează (desenul nu adaugă / nu ascunde BLOCANT);
* fiecare aparat generat are textele de pe desen și din listă egale cu șabloanele E.3 regenerate din parametri (V80 imposibil);
* ierarhia cascadelor din rezultat se regăsește în desen;
* exportul unei scheme blocate e refuzat (HTTP 409), iar al uneia valide reușește.
"""
import json, pathlib, sys, io, threading, urllib.request, urllib.error
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import constructor, layout, render_svg, render_dxf, validare  # noqa: E402
from engine.calc import text_lista, text_desen  # noqa: E402

DATE = json.loads((ROOT / "tests" / "date" / "cazuri_golden.json").read_text(encoding="utf-8"))
CAZURI = [c for c in DATE["cazuri"] if c["intrare"].get("tip_schema") != "verificare_model"]


def _aparate(m):
    def br(b):
        for a in b.get("aparate") or []:
            yield a
            yield from (a.get("laterale") or [])
        for c in b.get("copii") or []:
            yield from br(c)
    for b in (m.get("intrari") or []) + (m.get("plecari") or []):
        yield from br(b)
    yield from ((m.get("bara") or {}).get("laterale") or [])


@pytest.mark.parametrize("caz", CAZURI, ids=[c["id"] for c in CAZURI])
def test_cap_coada(caz, tmp_path):
    m, r = constructor.genereaza(caz["intrare"])
    v = validare.valideaza(m)
    assert v["blocheaza"] == caz["blocheaza_export"], [x for x in v["verificari"] if x["nivel"] == "BLOCANT"]
    # niciun BLOCANT în plus din desen
    coduri_motor = {(x["cod"], x["obiect"]) for x in r["verificari"] if x["nivel"] == "BLOCANT"}
    coduri_val = {(x["cod"], x["obiect"]) for x in v["verificari"] if x["nivel"] == "BLOCANT"}
    assert coduri_val == coduri_motor
    cv = layout.build(m)
    assert render_svg.render(cv, "t").startswith("<svg")
    f = tmp_path / "s.dxf"
    render_dxf.render(cv, str(f))
    import ezdxf
    doc = ezdxf.readfile(str(f))
    aud = doc.audit()
    assert not aud.has_errors
    # textele aparatelor = șabloanele E.3 din parametri
    for a in _aparate(m):
        par = a.get("param")
        if not par or not par.get("sablon"):
            continue
        p = {k: x for k, x in par.items() if k != "sablon"}
        den, car = text_lista(par["sablon"], p)
        assert a["lista"][0] == den
        if par["sablon"] not in ("contor", "dpst"):
            assert a["spec"] == text_desen(par["sablon"], p)
    # cascada: numărul de circuite din fiecare tablou secundar
    for i, pl in enumerate(caz["intrare"].get("plecari") or []):
        if pl.get("copii") and not r["blocheaza_export"]:
            assert len(m["plecari"][i].get("copii") or []) == len(pl["copii"])


def test_model_manual_e_marcat_neverificat():
    from engine import presets
    m = presets.get("tg")
    v = validare.valideaza(m)
    assert v["calculat"] is False and any(x["cod"] == "V00" for x in v["verificari"])
    me, r = validare.pregateste(m, pentru_export=True)
    assert r is None and me["note"][0] == validare.NOTA_MANUAL


def test_desenul_se_regenereaza_din_calcul():
    """o modificare manuală a unui aparat într-un model calculat nu ajunge pe planșă: desenul se reconstruiește din calcul"""
    m, _ = constructor.genereaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 150, "L_coloana_m": 50})
    q = next(a for a in m["intrari"][0]["aparate"] if a.get("ref") == "Q")
    q["spec"] = ["4P · 500 A"]; q["lista"] = ["Întreruptor 500 A"]; q["param"]["In_A"] = 500
    m2, _ = validare.pregateste(m, pentru_export=True)
    q2 = next(a for a in m2["intrari"][0]["aparate"] if a.get("ref") == "Q")
    assert "250" in q2["spec"][0] and "500" not in " ".join(q2["spec"])


@pytest.fixture(scope="module")
def server():
    import app
    from http.server import ThreadingHTTPServer
    srv = ThreadingHTTPServer(("127.0.0.1", 0), app.H)
    t = threading.Thread(target=srv.serve_forever, daemon=True); t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_export_blocat_si_permis(server):
    st, body = _post(server + "/api/genereaza", {"calc": {"tip_schema": "bransament", "retea": "tri", "P_kW": 300, "L_coloana_m": 80}})
    m = json.loads(body)["model"]
    st, body = _post(server + "/api/export/dxf", m)
    assert st == 409 and json.loads(body)["verificari"][0]["cod"] == "V50"
    st, body = _post(server + "/api/genereaza", {"calc": {"tip_schema": "bransament", "retea": "tri", "P_kW": 150, "L_coloana_m": 80}})
    m = json.loads(body)["model"]
    for fmt in ("dxf", "svg", "xlsx"):
        st, body = _post(server + f"/api/export/{fmt}", m)
        assert st == 200 and len(body) > 1000, fmt


def test_chat_genereaza_si_refuza(server):
    st, body = _post(server + "/api/chat", {"text": "post trafo 630 kVA cu plecări de 250, 160 și 100 A"})
    d = json.loads(body)
    assert d["model"]["calc"]["tip_schema"] == "pt" and len(d["model"]["plecari"]) == 4   # 3 + servicii proprii
    st, body = _post(server + "/api/chat", {"text": "tablou cu 3 plecări"})
    d = json.loads(body)
    assert d["interpretare"]["actiune"] == "refuza" and "model" not in d


@pytest.mark.parametrize("caz", CAZURI, ids=[c["id"] for c in CAZURI])
def test_fara_suprapuneri(caz):
    from engine.topologie import coliziuni
    m, _ = constructor.genereaza(caz["intrare"])
    assert coliziuni(layout.build(m)) == []


def test_model_manual_desen_diferit_de_lista_e_blocat():
    """M6: un model fără `calc` nu se poate exporta dacă desenul contrazice lista / parametrii"""
    m, _ = constructor.genereaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 60, "L_coloana_m": 30})
    m.pop("calc")
    assert not validare.valideaza(m)["blocheaza"]
    q = next(a for a in m["intrari"][0]["aparate"] if a.get("ref") == "Q")
    q["spec"] = ["4P · C160"]
    assert any(x["cod"] == "V80" for x in validare.valideaza(m)["verificari"] if x["nivel"] == "BLOCANT")
    m, _ = constructor.genereaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 60, "L_coloana_m": 30}); m.pop("calc")
    m["plecari"][0]["cablu"]["text"] = "ACYABY 4×16 mm² · L ≈ 30 m"
    assert validare.valideaza(m)["blocheaza"]


def test_ge_ats_doua_intrari_interblocate():
    """C1: rețeaua și GE intră separat în ATS (poziția I / II), cu interblocaj — niciodată pe aceeași bară înainte de ATS"""
    m, r = constructor.genereaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 100, "P_sarcina_kW": 60})
    assert not r["blocheaza_export"]
    i1, i2 = m["intrari"]
    assert i1["aparate"][-1]["interblocaj"] == i2["aparate"][-1]["interblocaj"] == "ATS"
    assert i1["cablu_ca"]["param"]["S_faza_mm2"] and i2["cablu_ca"]["param"]["S_faza_mm2"] and m["plecari"][0]["cablu"]["param"]["S_faza_mm2"]
    assert any(a.get("neutru_pamant") for a in i2["aparate"])
    cv = layout.build(m)
    assert any(getattr(it, "layer", "") == "MECANIC" for it in cv.items)


def test_pt_are_masura_si_servicii_proprii():
    """C5"""
    m, r = constructor.genereaza({"tip_schema": "pt", "Sn_kVA": 630, "plecari": [{"nume": "TD-1", "In_A": 250}]})
    tipuri = [a["tip"] for a in m["intrari"][0]["aparate"]]
    assert "tc" in tipuri and any(l["tip"] == "contor" for a in m["intrari"][0]["aparate"] for l in a.get("laterale") or [])
    assert m["plecari"][-1]["sarcina"]["titlu"] == "Servicii proprii PT"


def test_prosumator_are_cc_si_spd():
    """M5"""
    m, r = constructor.genereaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 10, "In_Q_bransament_A": 25})
    tipuri = [a["tip"] for a in m["intrari"][0]["aparate"]]
    assert "separator_cc" in tipuri
    assert any(l["tip"] == "spd_cc" for a in m["intrari"][0]["aparate"] for l in a.get("laterale") or [])
    assert m["bara"]["laterale"][0]["tip"] == "spd"


def test_cef_monofazat_desenat_monofazat():
    """C3"""
    m, r = constructor.genereaza({"tip_schema": "cef", "retea": "mono", "kWp": 6, "invertoare": [{"n": 1, "Pn_kW": 5}]})
    assert "L + N + PE" in m["bara"]["eticheta"]
    assert any(a["tip"] == "contor_direct" for a in m["plecari"][0]["aparate"])
    assert not any(a["tip"] == "tc" for a in m["plecari"][0]["aparate"])


CAZURI_NOI = [
    {"tip_schema": "ge_ats", "Sn_GE_kVA": 100, "P_sarcina_kW": 60},
    {"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 10, "In_Q_bransament_A": 25},
    {"tip_schema": "prosumator", "retea": "mono", "Pn_inv_kW": 5, "In_Q_bransament_A": 32, "hibrid": True},
    {"tip_schema": "cef", "retea": "mono", "kWp": 6, "invertoare": [{"n": 1, "Pn_kW": 5}]},
    {"tip_schema": "pt", "Sn_kVA": 630, "masura_pt": "MT", "plecari": [{"nume": "TD-1", "In_A": 250}]},
    {"tip_schema": "tablou", "L_alimentare_m": 30, "plecari": [{"nume": "Prize birouri", "In_A": 16}, {"nume": "Iluminat", "In_A": 10}]},
    # v1.2 R3 (N3-M1): 2405 A nu se pot lua din rețeaua publică (V50) — rețeaua normală e un PT propriu de 2000 kVA
    {"tip_schema": "ge_ats", "Sn_GE_kVA": 2000, "P_sarcina_kW": 1500, "origine": "pt_propriu", "pt_Sn_kVA": 2000},
    {"tip_schema": "tablou", "schema_pamant": "TT", "RA_ohm": 500, "IdN_amonte_mA": 100, "L_alimentare_m": 30, "plecari": [{"nume": "Hala", "In_A": 63}]},
    {"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 400, "schema_pamant": "TN-C", "P_kW": 60, "L_alimentare_m": 30,
     "plecari": [{"nume": "Hala", "In_A": 63}]},
    {"tip_schema": "pt", "Sn_kVA": 1600, "plecari": [{"nume": "TD-1", "In_A": 630}]},
]


@pytest.mark.parametrize("intrare", CAZURI_NOI, ids=[f"{c['tip_schema']}-{i}" for i, c in enumerate(CAZURI_NOI)])
def test_cazuri_noi_fara_suprapuneri(intrare):
    from engine.topologie import coliziuni
    m, r = constructor.genereaza(intrare)
    assert not r["blocheaza_export"], [v for v in r["verificari"] if v["nivel"] == "BLOCANT"]
    assert coliziuni(layout.build(m)) == []


def test_model_manual_protectie_peste_cablu_blocata():
    """N-M1: în modelul manual, protecția mărită peste capacitatea cablului e blocată (recalcul Iz' din secțiune)"""
    m, _ = constructor.genereaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 60, "L_coloana_m": 30}); m.pop("calc")
    q = next(a for a in m["intrari"][0]["aparate"] if a.get("ref") == "Q")
    q["param"]["In_A"] = 125
    constructor.regenereaza_texte(m)
    assert any(x["cod"] in ("V02", "V03") and x["nivel"] == "BLOCANT" for x in validare.valideaza(m)["verificari"])
    m, _ = constructor.genereaza({"tip_schema": "tablou", "L_alimentare_m": 30, "plecari": [{"nume": "A", "In_A": 40}]}); m.pop("calc")
    pl = m["plecari"][0]
    pl["cablu"]["param"]["Iz_corectat_A"] = 500          # Iz' falsificat: se recalculează din secțiune
    pl["aparate"][0]["param"]["In_A"] = 250
    constructor.regenereaza_texte(m)
    assert validare.valideaza(m)["blocheaza"]


def test_ge_are_ddr_in_regim_ge():
    m, r = constructor.genereaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 100, "P_sarcina_kW": 60})
    assert any(a.get("ref") == "DDR-G" for a in m["intrari"][1]["aparate"])


def test_tt_tablou_ddr_desenat():
    m, r = constructor.genereaza({"tip_schema": "tablou", "schema_pamant": "TT", "RA_ohm": 500, "IdN_amonte_mA": 100, "L_alimentare_m": 30,
                                  "plecari": [{"nume": "Hala", "In_A": 63}]})
    # v1.3 R5 (M5-4): amontele (100 mA declarat, S) protejează Q1 — Q1 fără DDR propriu (două DDR S în serie nu sunt
    # selective); plecarea are DDR 30 mA instantaneu, desenat
    assert "DDR" not in r["rezultat"]["Q1_C1"]
    assert any(a["tip"] == "rccb" for a in m["plecari"][0]["aparate"])


def test_model_manual_cablu_text_liber_verificat():
    """N3-M3: cablu scris de mână fără parametri → secțiunea se citește din text și se verifică față de protecție"""
    m, _ = constructor.genereaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 60, "L_coloana_m": 50}); m.pop("calc")
    c = m["plecari"][0]["cablu"]; c.pop("param"); c["text"] = "ACYABY 4×16 mm²"
    assert validare.valideaza(m)["blocheaza"]


def test_preseturi_manuale_trec_verificarea():
    from engine import presets
    for k in presets.PRESETS:
        v = validare.valideaza(presets.get(k))
        assert not v["blocheaza"], (k, [x for x in v["verificari"] if x["nivel"] == "BLOCANT"])
