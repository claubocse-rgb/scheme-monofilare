"""Verificarea normelor din 28.10.2026: răspunsurile proiectantului (teste/verificare_norme/raspunsuri_proiectant.md,
15 decizii) și corecturile verificatorului (teste/verificare_norme/raport.md) care nu le contrazic, plus restanțele
de interfață (BESS fără PV în panoul de confirmare, limitarea stației VE, „nu intră în deviz”, titlul TD).

Valorile calculate de mână sunt în comentarii.
"""
import json, os, pathlib, re, socket, subprocess, sys, tempfile, time, urllib.request
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import constructor, layout  # noqa: E402
from engine.calc import norme, catalog_invertoare as cat_inv  # noqa: E402
from engine.calc.scheme import calculeaza  # noqa: E402
from engine.confirmare import campuri_lipsa, intrebari_confirmare  # noqa: E402
from engine import deviz  # noqa: E402

HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")


def _v(r, cod, nivel=None):
    return [v for v in r["verificari"] + r.get("info", []) if v["cod"] == cod and (nivel is None or v["nivel"] == nivel)]


# ------------------------------------------------------------------------------------ 1. valorile din norme.py
def test_decizii_proiectant_valori():
    assert abs((norme.OD_ZBUCLA_IMPLICIT_OHM[0] ** 2 + norme.OD_ZBUCLA_IMPLICIT_OHM[1] ** 2) ** 0.5 - 0.30) < 1e-3   # Î2
    assert norme.OD_ZBUCLA_IMPLICIT_OHM[0] / norme.OD_ZBUCLA_IMPLICIT_OHM[1] == pytest.approx(2.0, rel=1e-3)
    assert norme.LOCUINTA_ZB_OD_RURAL_OHM == 0.8                                                               # Î2
    assert norme.PROSUMATOR_PI_EXTERNA_KW == 27.0                                                              # Î3
    assert norme.DEZECHILIBRU_FAZE_MAX_KVA == pytest.approx(16 * 230 / 1000, abs=1e-6)                         # Î4
    assert norme.PROSUMATOR_TD_PV_INTOTDEAUNA and norme.DDR_INVERTOR_DOAR_LA_CERERE                           # Î5, Î6
    assert norme.OD_IK3MAX_IMPLICIT_KA == 25.0 and norme.TRAFO_GRUPA_CONEXIUNI == "Dyn5"                      # Î7, Î9
    assert norme.PRIZA_R_LIMITA_OHM["bransament"] == 4.0 and norme.PRIZA_R_LIMITA_OHM["pt"] == norme.PRIZA_PT_ANRE["R_ohm"]
    assert norme.TRAFO_SN_MAX_SIGURANTE_MT_KVA == 630                                                          # Î10
    assert norme.LOCUINTA_KS_GENERAL == [(3, 0.8), (5, 0.6), (9, 0.4), (15, 0.35), (10 ** 6, 0.3)]           # Î11
    assert norme.PRAG_RACORD_JT_MAX_KVA == 400.0                                                               # Î13
    assert "5(" not in norme.CONTOR_DIRECT_TRIFAZAT and "furnizat" in norme.CONTOR_DIRECT_MONOFAZAT           # Î15
    assert norme.LOCUINTA_DDR_BRANSAMENT_IMPLICIT == {"tip": "AC", "selectiv": False} and not norme.BMPM_RCBO_SELECTIV
    assert norme.BMPT_RCCB["tip"] == "AC"
    assert len(norme.DECIZII_PROIECTANT_28_10_2026) == 15


def test_corecturi_verificator():
    # #12 CLC/TR 50480: fază 1,20 / 1,28; PE 1,38 / 1,60
    assert norme.FACTOR_R_IK1MIN == {"PVC": 1.20, "XLPE": 1.28} and norme.FACTOR_R_IK1MIN_PE == {"PVC": 1.38, "XLPE": 1.60}
    # #29 Im MCCB TM = max(10·In; 500 A) la In ≤ 50 A
    assert norme.im_tm(16) == 500 and norme.im_tm(50) == 500 and norme.im_tm(63) == 630 and norme.im_tm(100) == 1000
    # #43 I²t clasa 3 pe curbă, fără rândul de 25 kA: C ≤ 16 A la 6 kA = 42 000 A²s; B 16…32 A la 10 kA = 90 000
    assert norme.mcb_i2t(16, 5000, "C") == 42000 and norme.mcb_i2t(16, 5000, "B") == 35000
    assert norme.mcb_i2t(25, 10000, "B") == 90000 and norme.mcb_i2t(25, 10000, "C") == 110000
    assert norme.mcb_i2t(16, 12000, "C") is None and norme.mcb_i2t(16, 3000, "D") is None and norme.mcb_i2t(40, 3000) is None
    assert norme.PV_UMAX_INVERTOR_IMPLICIT_V == 1000.0                                                         # #78
    assert norme.PRIZA_ELECTROD_D_IMPLICIT_M == 0.060                                                          # #109
    assert norme.TC_CONSUM_CONTOR_VA == 1.0 and norme.K_GRUP_F_DISTANTAT[2] == 0.97                           # #71, #17
    # nicio poziție decisă / verificată nu mai e listată ca NEVERIFICAT
    for k in ("FACTOR_R_IK1MIN", "X_CABLU_OHM_KM", "RFG_PRAG_TIP_C/D", "DEZECHILIBRU_FAZE_MAX_KVA", "LOCUINTA_KS_GENERAL",
              "BMPM_RCBO_SELECTIV", "CONTOR_DIRECT_*", "LOCUINTA_ZB_OD_RURAL_OHM", "PRIZA_ETA_ELECTROZI"):
        assert k not in norme.NEVERIFICAT, k
    assert norme._autoverificare()


def test_marcajele_din_norme():
    src = (ROOT / "engine" / "calc" / "norme.py").read_text(encoding="utf-8")
    assert src.count("[DECIZIE proiectant 28.10.2026") >= 14 and src.count("[VERIFICAT:") >= 30
    # corectura de citare: pragurile RfG în Ord. ANRE 79/2016
    assert "Ord. ANRE 79/2016" in src


def test_huawei_m1_hibrid_doar_3_10_kw():
    assert cat_inv.cauta("Huawei", "SUN2000-10KTL-M1")["hibrid"] and cat_inv.cauta("Huawei", "SUN2000-3KTL-M1")["hibrid"]
    assert cat_inv.cauta("Huawei", "SUN2000-100KTL-M1")["hibrid"] is False
    assert cat_inv.cauta("Huawei", "SUN2000-100KTL-M1")["Pn_kW"] == 100.0


# ------------------------------------------------------------------------------------ 2. efectele pe calcul
def test_locuinta_ddr_bransament_ac_instantaneu_cu_remediere():
    r = calculeaza({"tip_schema": "locuinta", "retea": "mono", "alimentare": {"In_Q_bransament_A": 32, "P_aprobata_kW": 7},
                    "circuite": [{"nume": "Il", "receptor": "iluminat"}, {"nume": "Pr", "receptor": "prize"}]})
    v = _v(r, "V43", "AVERTISMENT")
    assert v and "instantaneu" in v[0]["mesaj"] and "blocul real" in v[0]["remediere"]
    assert r["rezultat"]["alimentare"]["DDR_bransament_tip"] == "AC"


def test_zb_rural_0_8_si_ik1_mai_mic():
    base = {"tip_schema": "locuinta", "retea": "mono", "alimentare": {"In_Q_bransament_A": 32, "P_aprobata_kW": 7},
            "circuite": [{"nume": "Pr", "receptor": "prize", "L_m": 30}]}
    ur = calculeaza(base)
    ru = calculeaza(dict(base, alimentare=dict(base["alimentare"], zona="rural")))
    ik = lambda r: r["rezultat"]["grupe_DDR"][0]["circuite"][0]["Ik1min_capat_A"]
    assert ik(ru) < ik(ur)
    assert any("0,8 Ω (zonă rurală)" in p for p in ru["presupus"])


def test_dezechilibru_16a_si_v71_pe_kva():
    # 3,5 kW mono: Smax = 1,1·3,5 = 3,85 kVA > 3,68 kVA (16 A) → V71 AV (comparația pe kVA, Ord. 228/2018 art. 12(3))
    r = calculeaza({"tip_schema": "prosumator", "retea": "mono", "Pn_inv_kW": 3.5})
    v = _v(r, "V71", "AVERTISMENT")
    assert v and "3,68 kVA" in v[0]["mesaj"] and "228/2018" in v[0]["mesaj"]
    # 3,3 kW: 3,63 kVA ≤ 3,68 → fără V71
    assert not _v(calculeaza({"tip_schema": "prosumator", "retea": "mono", "Pn_inv_kW": 3.3}), "V71", "AVERTISMENT")


def test_prosumator_td_pv_la_orice_putere_si_protectii_cc_ca():
    m, r = constructor.genereaza({"tip_schema": "prosumator", "retea": "mono", "Pn_inv_kW": 3, "In_Q_bransament_A": 32})
    assert m["carcasa"]["titlu"] == "TD-PV" and r["rezultat"]["QG"] and r["rezultat"]["td_pv"]
    tip = [a["tip"] for b in m["intrari"] for a in b["aparate"]]
    lat = [l["tip"] for b in m["intrari"] for a in b["aparate"] for l in a.get("laterale") or []]
    assert "separator_cc" in tip and "spd_cc" in lat and m["bara"]["laterale"]
    assert any("protecții pe partea de c.c." in p for p in r["presupus"])
    # „nu” pe c.c. și pe c.a.: fără cutie c.c. / SPD c.c., fără SPD c.a. (nici pe bara TD-PV, nici la invertor)
    m, r = constructor.genereaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 10, "L_inv_m": 30,
                                  "protectii_cc": False, "protectii_ca": "false"})
    lat = [l["tip"] for b in m["intrari"] for a in b["aparate"] for l in a.get("laterale") or []]
    assert "spd_cc" not in lat and "spd" not in lat and not m["bara"]["laterale"]
    assert not r["rezultat"]["INV"].get("SPD_ca_invertor")
    assert intrebari_confirmare({"tip_schema": "prosumator", "Pn_inv_kW": 3}) and \
        not intrebari_confirmare({"tip_schema": "prosumator", "protectii_cc": True, "protectii_ca": False})


def test_ddr_invertor_doar_la_cerere_tt_ramane():
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 8})
    assert "DDR" not in r["rezultat"]["INV"]
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 8, "schema_pamant": "TT", "RA_ohm": 10})
    assert r["rezultat"]["INV"]["DDR"]["IdN_mA"] == 30
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "invertoare": [{"n": 1, "Pn_kW": 8, "producator": "Huawei",
                                                                               "model": "SUN2000-8KTL-M1", "ddr": True}]})
    assert r["rezultat"]["INV"]["DDR"]["IdN_mA"] == 100            # Huawei ≥ 100 mA (manualul 3…10KTL-M1)


def test_celula_trafo_630_si_contor_fara_curent():
    r = calculeaza({"tip_schema": "pt", "Sn_kVA": 800, "plecari": [{"nume": "TD-1", "In_A": 250}]})
    assert r["rezultat"]["celula_trafo"] == "intreruptor"
    r = calculeaza({"tip_schema": "pt", "Sn_kVA": 630, "plecari": [{"nume": "TD-1", "In_A": 250}]})
    assert r["rezultat"]["celula_trafo"].startswith("separator de sarcină + siguranțe MT 40")
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 15})
    assert "furnizat și montat de OD" in r["rezultat"]["contor"] and "5(100)" not in r["rezultat"]["contor"]


def test_priza_pt_conform_anre_cu_nota():
    r = calculeaza({"tip_schema": "pt", "Sn_kVA": 400, "plecari": [{"nume": "TD-1", "In_A": 100}], "priza": {}})
    p = r["rezultat"]["priza"]
    assert p["R_limita_ohm"] == 1.0 and "conform ANRE" in json.dumps(r, ensure_ascii=False)


# ------------------------------------------------------------------------------------ 3. restanțele de interfață
def test_confirmare_bess_fara_pv_nu_e_blocat():
    assert campuri_lipsa({"tip_schema": "cef", "bess": {"P_kW": 250, "kWh": 500}}) == []
    # panoul folosește regula serverului (interpretare.lipsa / /api/chat/verifica), nu doar copia locală
    i = HTML.index("function confLipsa()"); corp = HTML[i:HTML.index("\n}\n", i)]
    assert "lipsaSrv" in corp and "it.lipsa" in corp
    assert "C.lipsaSrv = { tip: intrare.tip_schema, L: r.lipsa }" in HTML
    rg = HTML[HTML.index("function confLipsaRegula("):HTML.index("function confLipsa()")]
    assert "!inv && !bess" in rg


def test_ve_limitare_propunere_v46():
    r = calculeaza({"tip_schema": "locuinta", "retea": "mono", "alimentare": {"In_Q_bransament_A": 32, "P_aprobata_kW": 7},
                    "circuite": [{"nume": "Il", "receptor": "iluminat"}, {"nume": "Stație VE", "receptor": "vehicul_electric",
                                                                          "P_kW": 7.4}]})
    pv = [v["propunere_ve"] for v in _v(r, "V46") if v.get("propunere_ve")]
    assert pv and pv[0]["obiect"].startswith("C2·") and 1.3 < pv[0]["limitare_kW"] <= 7.4
    assert "Limitează stația la" in HTML and "propunere_ve" in HTML and "'limitare_kW'" in HTML and "id + 'lim'" in HTML


def test_deviz_generice_existente_nu_intra():
    m, _ = constructor.genereaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 15})
    _, poz = layout.build_cu_pozitii(m)
    d = deviz.calculeaza(poz, catalog={"articole": {}, "setari": {}})
    contor = [a for a in d["articole"] if a["ref"] == "P"]
    assert contor and contor[0]["exclus"] and contor[0]["exclus_auto"] == "furnizat de OD"
    assert d["recapitulatie"]["nr_in_deviz"] == d["recapitulatie"]["nr_articole"] - 1
    # inclus explicit de proiectant
    d = deviz.calculeaza(poz, catalog={"articole": {}, "setari": {}}, suprascrieri={contor[0]["cheie"]: {"exclus": False}})
    assert not [a for a in d["articole"] if a["ref"] == "P"][0]["exclus"]
    assert "nu intră în deviz · ${a.exclus_auto}" in HTML


def test_titlu_td_la_tablou_din_tg():
    m, _ = constructor.genereaza({"tip_schema": "tablou", "origine": "tg_existent", "plecari": [{"nume": "Prize", "P_kW": 3}]})
    assert m["carcasa"]["titlu"] == "TD" and "TABLOU DE DISTRIBUȚIE JT (TD)" in m["cartus"]["denumire2"]
    m, _ = constructor.genereaza({"tip_schema": "tablou", "origine": "bmpt", "plecari": [{"nume": "Prize", "P_kW": 3}]})
    assert m["carcasa"]["titlu"] == "TG"


# ------------------------------------------------------------------------------------ 4. cap-coadă în Chromium
def _port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


@pytest.fixture(scope="module")
def srv():
    port = _port()
    env = dict(os.environ, ANTHROPIC_API_KEY="", XDG_CONFIG_HOME=tempfile.mkdtemp())
    pr = subprocess.Popen([sys.executable, "app.py", str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL)
    u = f"http://127.0.0.1:{port}/"
    for _ in range(100):
        try:
            urllib.request.urlopen(u + "api/info", timeout=1); break
        except Exception:
            time.sleep(0.1)
    yield u
    pr.terminate(); pr.wait(5)


@pytest.fixture(scope="module")
def browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright (Python) nu e instalat")
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"Chromium indisponibil: {e}")
        yield b
        b.close()


def _pagina(browser, url):
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    pg.erori = []
    pg.on("pageerror", lambda e: pg.erori.append(str(e)))
    pg.goto(url); pg.wait_for_function("() => typeof INFO !== 'undefined' && Object.keys(SABLOANE).length > 0 && MODEL", timeout=60000)
    pg.wait_for_timeout(800)
    pg.evaluate("() => { INFO.claude = false; }")
    return pg


def _chat(pg, text):
    pg.evaluate("() => { acasaInchide(); WIZ_START = null; render(); $('#assist').open = true; }")
    pg.fill("#chat-text", text)
    pg.press("#chat-text", "Control+Enter")
    pg.wait_for_selector("#conf", timeout=30000)


def test_e2e_bess_fara_pv_se_poate_confirma(srv, browser):
    pg = _pagina(browser, srv)
    _chat(pg, "Sistem de stocare BESS 250 kW / 500 kWh racordat în JT la tabloul general al unei fabrici, cablu 40 m")
    pg.wait_for_timeout(1200)                                  # previzualizarea pe server (regula „lipsă”)
    assert pg.get_attribute("#cf-ok", "aria-disabled") == "false", pg.inner_text("#cf-block")
    assert not pg.erori


def test_e2e_prosumator_intreaba_protectiile(srv, browser):
    pg = _pagina(browser, srv)
    _chat(pg, "prosumator trifazat 6 kW pe acoperișul casei")
    txt = pg.inner_text("#conf")
    assert "protecții pe partea de c.c." in txt and "protecții pe partea de c.a." in txt
    assert pg.query_selector("#cf-protectii_cc") or pg.query_selector("#cf-protectii_cc-q")
    assert not pg.erori
