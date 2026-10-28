"""r10: panoul de confirmare după chat — textul → interpretare → tabel editabil → „Confirmă și desenează” → planșa.

* structura din static/index.html (funcțiile, butoanele, legătura cu render / chat / asistent);
* API: /api/chat cu `fara_model` nu desenează; /api/chat/confirma desenează intrarea corectată;
* cap-coadă în Chromium (Playwright) pe serverul local `python3 app.py PORT`: casă, CEF, TG fără rețea (prin asistent);
* opțional, versiunea web (Pyodide): SM_WEB_VENDOR=<vendor> → build + un scenariu în pagina statică.
"""
import json, os, pathlib, re, shutil, socket, subprocess, sys, tempfile, time, urllib.request
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
sys.path.insert(0, str(ROOT))


# --------------------------------------------------------------------------- structura interfeței
@pytest.mark.parametrize("fn", ["confDeschide", "confRender", "confCampuri", "confFld", "confTabel", "confTabele",
                                "confBlocaj", "confStare", "confInapoi", "confExport", "confConfirma"])
def test_functii_noi(fn):
    assert re.search(r"(async\s+)?function " + fn + r"\(", HTML), fn


def test_butoane_si_flux():
    assert "'Confirmă și desenează'" in HTML and "'← Înapoi la text'" in HTML
    assert "id: 'cf-ok'" in HTML and "id: 'cf-back'" in HTML and "id: 'cf-block'" in HTML
    # chatul și asistentul nu mai desenează direct: cer doar interpretarea, apoi deschid panoul
    for fn in ("chatGo", "wizChat"):
        i = HTML.index(f"async function {fn}("); j = HTML.index("\n}\n", i)
        corp = HTML[i:j]
        assert "fara_model: true" in corp and "confDeschide(" in corp and "replaceModel" not in corp, fn
    # Ctrl+Enter din text → chatGo (→ confirmare); în panou Ctrl+Enter confirmă, Escape revine la text
    assert re.search(r"#chat-text'\)\.addEventListener\('keydown'.*chatGo\(\)", HTML)
    i = HTML.index("function confRender("); corp = HTML[i:HTML.index("\n}\n", i)]
    assert "Escape" in corp and "confInapoi()" in corp and "confConfirma()" in corp
    # panoul ține locul tab-urilor în render(); confirmarea trece prin /api/chat/confirma
    assert "if (CONF) confRender(frag);" in HTML and "$('.tabs').hidden = !!CONF" in HTML
    assert "/api/chat/confirma" in HTML


def test_accesibilitate_si_aspect():
    # etichete legate de câmpuri, tabel în container derulabil propriu, contur „presupus” cu variabilele temei
    assert "el('label', { for: id }" in HTML
    assert ".cf-scroll{overflow-x:auto" in HTML and "role: 'region'" in HTML
    assert re.search(r"\.cf-pres input,.*var\(--sig-line\)", HTML)
    assert "aria-disabled" in HTML and "'aria-describedby': 'cf-block'" in HTML
    css = HTML[HTML.index("confirmarea intrării după chat */"):HTML.index("mobil / îngust */")]
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", css), "culori fixe în CSS-ul panoului — folosește variabilele"


# --------------------------------------------------------------------------- API
def _H(metoda, cale, corp):
    import app, io

    class H(app.H):
        def __init__(self):
            b = json.dumps(corp).encode()
            self.command, self.path, self.headers, self.rfile = metoda, cale, {"Content-Length": str(len(b))}, io.BytesIO(b)
            self.out = None

        def _send(self, code, body, ctype="", fname=None, extra=None):
            self.out = (code, body)
    h = H(); h.do_POST()
    return h.out[0], json.loads(h.out[1])


def test_api_chat_fara_model_si_confirma():
    st, d = _H("POST", "/api/chat", {"text": "casă P+1, trifazat 15 kW, plită, cuptor, coloană 25 m, beneficiar Ion Pop",
                                     "claude": False, "fara_model": True})
    assert st == 200 and "model" not in d and d["interpretare"]["intrare_fizica"]["tip_schema"] == "locuinta"
    assert d["cartus_chat"].get("beneficiar") == "Ion Pop" and "neconsumat" in d["interpretare"]
    intr = d["interpretare"]["intrare_fizica"]
    intr["alimentare"]["P_aprobata_kW"] = 20
    intr["circuite"] = [c for c in intr["circuite"] if c["nume"] != "Plită"]
    st, g = _H("POST", "/api/chat/confirma", {"intrare": intr, "cartus_chat": d["cartus_chat"], "model": {"cartus": {"proiectant": "X"}}})
    assert st == 200 and g["model"]["calc"]["alimentare"]["P_aprobata_kW"] == 20
    assert g["model"]["cartus"]["beneficiar"] == "Ion Pop" and g["model"]["cartus"]["proiectant"] == "X"
    assert not any(c["nume"] == "Plită" for c in g["model"]["calc"]["circuite"]) and "validare" in g
    st, e = _H("POST", "/api/chat/confirma", {"intrare": {}})
    assert st == 400 and "eroare" in e


def test_api_chat_vechi_neschimbat():
    st, d = _H("POST", "/api/chat", {"text": "post trafo 630 kVA cu plecări de 250 și 160 A", "claude": False})
    assert st == 200 and d["model"]["calc"]["Sn_kVA"] == 630 and "validare" in d


# --------------------------------------------------------------------------- cap-coadă în browser
def _pw():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except Exception:
        return False


def _port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


@pytest.fixture(scope="module")
def srv():
    port = _port()
    env = dict(os.environ, ANTHROPIC_API_KEY="", XDG_CONFIG_HOME=tempfile.mkdtemp())
    pr = subprocess.Popen([sys.executable, "app.py", str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    if not _pw():
        pytest.skip("playwright (Python) nu e instalat")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:
            pytest.skip(f"Chromium indisponibil: {e}")
        yield b
        b.close()


def _pagina(browser, url, w=1440, h=900):
    pg = browser.new_page(viewport={"width": w, "height": h})
    pg.erori = []
    pg.on("pageerror", lambda e: pg.erori.append(str(e)))
    pg.goto(url); pg.wait_for_function("() => typeof INFO !== 'undefined' && Object.keys(SABLOANE).length > 0 && MODEL", timeout=60000)
    pg.wait_for_timeout(800)                         # pornirea își termină pașii (asistentul / panoul „Descrie” deschis sau nu)
    pg.evaluate("() => { INFO.claude = false; }")
    return pg


def _chat(pg, text):
    pg.evaluate("() => { acasaInchide(); WIZ_START = null; render(); $('#assist').open = true; }")   # de pe pagina de start în editor
    pg.fill("#chat-text", text)
    pg.press("#chat-text", "Control+Enter")          # Ctrl+Enter din text → panoul de confirmare
    pg.wait_for_selector("#conf", timeout=30000)


def _planse(pg):
    pg.wait_for_function("() => !$('#conf') && MODEL.calc", timeout=30000)
    pg.wait_for_timeout(800)
    pg.wait_for_function("() => $('#paper svg') && !$('#vstat').classList.contains('busy')", timeout=30000)
    return pg.evaluate("() => $('#paper').innerHTML")


def test_e2e_casa(srv, browser):
    pg = _pagina(browser, srv)
    _chat(pg, "casă P+1, trifazat 15 kW, plită, pompă de căldură, încărcător mașină 11 kW, coloană 25 m")
    assert pg.evaluate("() => $('.tabs').hidden") and pg.get_attribute("#cf-ok", "aria-disabled") == "false"
    # desenul NU s-a schimbat încă
    assert pg.evaluate("() => !(MODEL.calc && MODEL.calc.tip_schema === 'locuinta' && MODEL.calc.alimentare && MODEL.calc.alimentare.L_coloana_m === 25)")
    pg.fill("#cf-alimentare-P_aprobata_kW", "20")
    nume = pg.evaluate("() => [...document.querySelectorAll('#conf input[id$=\"-nume\"]')].map(i => i.value)")
    i = nume.index("Plită")
    pg.click(f"#cf-ci-{i}-del")
    assert "Plită" not in pg.evaluate("() => [...document.querySelectorAll('#conf input[id$=\"-nume\"]')].map(i => i.value)")
    pg.click("#cf-ok")
    svg = _planse(pg)
    c = pg.evaluate("() => MODEL.calc")
    assert c["alimentare"]["P_aprobata_kW"] == 20 and c["alimentare"]["L_coloana_m"] == 25
    assert [x["nume"] for x in c["circuite"]] == [n for n in nume if n != "Plită"]
    assert "Pompă de căldură" in svg and "Plită" not in svg
    assert pg.evaluate("() => !$('.tabs').hidden && TAB === 'calc'") and not pg.erori


def test_e2e_cef(srv, browser):
    pg = _pagina(browser, srv)
    _chat(pg, "CEF 300 kWp cu 3 invertoare de 100 kW și BESS 200 kWh")
    assert pg.input_value("#cf-inv-0-n") == "3"
    assert pg.evaluate("() => $('#cf-bat-P_kW').closest('.fld').classList.contains('cf-pres')")   # PCS presupus, marcat
    pg.fill("#cf-inv-0-n", "4")
    pg.click("#cf-ok")
    svg = _planse(pg)
    assert pg.evaluate("() => MODEL.calc.invertoare[0].n") == 4 and pg.evaluate("() => MODEL.calc.bess.kWh") == 200
    assert {"INV-1", "INV-2", "INV-3", "INV-4"} <= set(re.findall(r"INV-\d+", svg)) and "INV-5" not in svg
    assert not pg.erori


def test_e2e_tg_fara_retea_prin_asistent(srv, browser):
    pg = _pagina(browser, srv)
    pg.evaluate("() => startWizard()")
    pg.fill("#wz-text", "tablou general cu plecări: hală 16 A, birouri 10 A")
    pg.press("#wz-text", "Control+Enter")
    pg.wait_for_selector("#conf", timeout=30000)
    assert pg.get_attribute("#cf-ok", "aria-disabled") == "true"
    assert "rețeaua" in pg.inner_text("#cf-block")
    assert pg.evaluate("() => $('#wizbar').hidden && $('#wizfoot').hidden")
    inainte = pg.evaluate("() => JSON.stringify(MODEL.calc)")
    pg.click("#cf-ok", force=True); pg.wait_for_timeout(800)     # aria-disabled: clicul nu desenează, arată ce lipsește
    assert pg.query_selector("#conf") and pg.evaluate("() => JSON.stringify(MODEL.calc)") == inainte
    assert pg.evaluate("() => document.activeElement.id").startswith("cf-retea")
    # câmpul de lângă întrebare și cel din „Instalația” sunt același câmp
    pg.select_option("#cf-retea-q", "tri")
    assert pg.input_value("#cf-retea") == "tri" and pg.get_attribute("#cf-ok", "aria-disabled") == "false"
    pg.click("#cf-ok")
    pg.wait_for_function("() => !$('#conf') && MODEL.calc && !wizActiv() && TAB === 'calc'", timeout=30000)   # echipa 1: direct la planșă
    c = pg.evaluate("() => MODEL.calc")
    assert c["retea"] == "tri" and [p["nume"] for p in c["plecari"]] == ["Hală", "Birouri"]
    assert not pg.erori


def test_e2e_inapoi_la_text_si_mobil(srv, browser):
    pg = _pagina(browser, srv, 390, 844)
    _chat(pg, "prosumator 10 kW cu baterie 10 kWh")
    assert pg.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    assert pg.evaluate("() => { const s = document.querySelector('#conf .cf-scroll'); return getComputedStyle(s).overflowX; }") == "auto"
    pg.keyboard.press("Escape")
    pg.wait_for_selector("#conf", state="detached")
    assert pg.evaluate("() => document.activeElement.id") == "chat-text" and not pg.evaluate("() => $('.tabs').hidden")
    assert not pg.erori


# --------------------------------------------------------------------------- r11: ce nu se putea corecta în panou (teste/r11/*.md)
CAPTURI = ROOT / "teste" / "r11" / "ui_confirmare"
VIEWPORTS = [pytest.param((1440, 900), id="desktop"), pytest.param((390, 844), id="mobil")]


@pytest.mark.parametrize("fn", ["confDeduse", "confPtMod", "confInGE", "confQWarn", "confStringuri", "confCabluri",
                                "confWarnUpd", "confPrevLater"])
def test_r11_functii(fn):
    assert re.search(r"(async\s+)?function " + fn + r"\(", HTML), fn


def test_r11_campuri_si_etichete():
    i = HTML.index("function confCampuri("); corp = HTML[i:HTML.index("\nfunction confFld(", i)]
    # CEF: post de transformare existent / nou / nu e cazul, racordul cu PT existent / nou, TGD-CF
    for t in ("'Post de transformare'", "'existent (sursă, fără trafo nou)'", "'nou (se proiectează)'", "'nu e cazul (racord JT)'",
              "'Racord'", "'TG existent'", "'BMPT'", "'PT existent'", "'PT nou'", "'Tablouri TGD-CF'", "'Măsura de decontare'",
              # tablou / PT / GE: n trafo + cuplă + AAR + uk + grupa; sursa (inclusiv GE izolat)
              "'Cupla longitudinală JT'", "'AAR pe cuplă", "'uk trafo [%]'", "'Grupa de conexiuni'", "'grup electrogen izolat (fără rețea)'",
              "'fără rețea — GE izolat (sursă unică)'", "'Comutarea sursei'",
              # locuință: branșament nou / existent, Q cu atenționare, generator, EPS
              "'nou (se proiectează)'", "warnId: 'cf-qwarn'", "'Generator de rezervă'", "'Sn generator [kVA]'", "'Tablou EPS (rezervat)'"):
        assert t in corp, t
    i = HTML.index("const cabG = "); corp = HTML[i:HTML.index("\nfunction confBlocaj(", i)]
    for t in ("label: 'Vital'", "label: 'UPS'", "label: 'Siguranță'", "label: 'Cablu impus'", "label: 'S [mm²]'", "label: 'n ∥'", "label: 'Nr. circ.'",
              "label: 'Buc.'", "label: 'TGD'", "'Tablouri secundare'", "`Circuitele ${", "'Tablou EPS — circuite'", "'Cabluri impuse'", "'Stringuri (c.c.)'",
              "'Module pe string'", "'Stringuri în paralel / MPPT'", "'Pmax modul [W]'", "'cablu_C0'", "'cablu_inv'", "'cablu_cc'"):
        assert t in corp, t
    # bifele au etichetă legată, atenționarea e anunțată (role status) și legată de câmp
    i = HTML.index("function confFld("); corp = HTML[i:HTML.index("\nfunction confTabel(", i)]
    assert "el('label', { for: id }, inp," in corp and "role: 'status'" in corp and "aria-describedby" in corp
    assert ".cf-chk.cf-pres>label" in HTML and ".cf-warn{" in HTML
    assert "/api/chat/verifica" in HTML


def test_r11_retea_dedusa_regex_si_deduse(browser, srv):
    pg = _pagina(browser, srv)
    r = pg.evaluate("""() => [
      'rețea nedeclarată, dar tabloul e alimentat din PT → trifazat 3 × 400/230 V',
      'rețea mixtă: invertor trifazat + invertor monofazat → instalație trifazată 3 × 400 V',
      'rețea nedeclarată → trifazat 3 × 400 V din modelul invertorului (fișa tehnică)',
      'S"kQ = 500 MVA (rețea MT 20 kV, valoare implicită)',
      'sursa: rețea publică prin BMPT (declarată), RCCB 300 mA în BMPT conform ST 4-JT'].map(t => CONF_PRES[0][0].test(t))""")
    assert r == [True, True, True, False, False]
    assert pg.evaluate("() => [confDeduse(['retea']), confDeduse({retea: 'din 3x25A'}), confDeduse('retea'), confDeduse([{camp: 'retea', motiv: 'BMPT'}]), confDeduse(null)]") \
        == ([[["retea", ""]], [["retea", "din 3x25A"]], [["retea", ""]], [["retea", "BMPT"]], []])
    assert not pg.erori


def test_r11_api_verifica_q_declarat():
    intr = {"tip_schema": "locuinta", "retea": "tri", "alimentare": {"tip": "bransament_nou", "In_Q_bransament_A": 16, "P_aprobata_kW": 15},
            "circuite": [{"nume": "Plită", "receptor": "plita"}]}
    st, d = _H("POST", "/api/chat/verifica", {"intrare": intr})
    assert st == 200 and d["schimbari"] and d["schimbari"][0]["camp"] == "alimentare.In_Q_bransament_A" and d["schimbari"][0]["declarat"] == 16
    intr["alimentare"]["In_Q_bransament_A"] = d["schimbari"][0]["calculat"]
    st, d2 = _H("POST", "/api/chat/verifica", {"intrare": intr})
    assert st == 200 and d2["schimbari"] == []
    st, e = _H("POST", "/api/chat/verifica", {"intrare": {}})
    assert st == 400 and "eroare" in e


def _captura(pg, nume, vp):
    CAPTURI.mkdir(parents=True, exist_ok=True)
    pg.wait_for_timeout(250)
    pg.screenshot(path=str(CAPTURI / f"{nume}_{'mobil' if vp[0] < 600 else 'desktop'}.png"))


def _fara_scroll_pagina(pg):
    return pg.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth")


@pytest.mark.parametrize("vp", VIEWPORTS)
def test_e2e_r11_cef_pt_existent(srv, browser, vp):
    """CEF cu PT existent selectat în panou → planșa fără transformator nou; cablul C0 impus ajunge în motor."""
    pg = _pagina(browser, srv, *vp)
    _chat(pg, "CEF 400 kWp cu 4 invertoare SUN2000-100KTL de 100 kW, PT propriu 630 kVA, racord în PT")
    assert pg.is_visible("#cf-_pt") and pg.is_visible("#cf-cab-0-tip") and pg.is_visible("#cf-string-n_module")
    pg.select_option("#cf-_pt", "existent")
    assert pg.input_value("#cf-pt_Sn_kVA") == "630" and pg.input_value("#cf-racord") in ("", "pt_ex")
    pg.select_option("#cf-racord", "pt_ex")
    pg.select_option("#cf-masura", "MT")
    pg.fill("#cf-cab-0-tip", "na2xy"); pg.fill("#cf-cab-0-S", "240"); pg.fill("#cf-cab-0-L", "80")
    pg.fill("#cf-string-n_module", "20"); pg.fill("#cf-string-n_stringuri_paralel", "2"); pg.fill("#cf-modul-Pmax_W", "550")
    pg.fill("#cf-n_tgd_cf", "2"); pg.press("#cf-n_tgd_cf", "Tab")
    pg.select_option("#cf-inv-0-tgd", "1")
    assert _fara_scroll_pagina(pg)
    pg.evaluate("() => $('#cf-cab-h').scrollIntoView()"); _captura(pg, "cef_pt_existent", vp)
    ex = pg.evaluate("() => confExport()")
    assert ex["pt_existent"] is True and ex["racord"] == "pt" and ex["pt_Sn_kVA"] == 630 and ex["masura"] == "MT"
    assert ex["cablu_C0"] == {"tip_cablu": "NA2XY", "S_fortat": 240} and ex["L_racord_m"] == 80
    assert ex["string"]["n_module"] == 20 and ex["modul"]["Pmax_W"] == 550 and ex["n_tgd_cf"] == 2 and ex["invertoare"][0]["tgd"] == 1
    pg.click("#cf-ok")
    svg = _planse(pg)
    m = pg.evaluate("() => JSON.stringify(MODEL)")
    assert pg.evaluate("() => MODEL.calc.pt_existent") is True
    assert '"tip":"trafo"' not in m.replace(" ", ""), "trafo nou desenat deși PT-ul e existent"
    assert "EXISTENT" in svg.upper() and not pg.erori


@pytest.mark.parametrize("vp", VIEWPORTS)
def test_e2e_r11_tg_doua_trafo_cupla_deschisa(srv, browser, vp):
    """TG din PT propriu cu 2 trafo + cupla deschisă + AAR, coloanele noi ale plecărilor → planșa cu 2 secții de bare."""
    pg = _pagina(browser, srv, *vp)
    _chat(pg, "tablou general alimentat din PT propriu, plecări: hală 250 A, birouri 100 A, pompă incendiu 30 kW")
    # rețeaua nedeclarată (dedusă din PT) e marcată galben
    assert pg.evaluate("() => $('#cf-retea').closest('.fld').classList.contains('cf-pres')")
    pg.select_option("#cf-pt_Sn_kVA", "630"); pg.select_option("#cf-n_trafo", "2")
    assert pg.is_visible("#cf-cupla") and pg.evaluate("() => $('#cf-grupa_conexiuni').closest('.fld').classList.contains('cf-pres')")
    pg.select_option("#cf-cupla", "deschisa"); pg.check("#cf-aar"); pg.fill("#cf-uk_pct", "6"); pg.select_option("#cf-grupa_conexiuni", "Dyn11")
    nume = pg.evaluate("() => CONF.ed.plecari.map(p => p.nume)")
    i = nume.index("Birouri")
    pg.check(f"#cf-pl-{i}-vital"); pg.check(f"#cf-pl-{i}-ups"); pg.fill(f"#cf-pl-{i}-n_circuite", "2")
    pg.fill(f"#cf-pl-{i}-cab_tip", "CYABY"); pg.fill(f"#cf-pl-{i}-cab_S", "50"); pg.fill(f"#cf-pl-{i}-cab_n", "2")
    assert _fara_scroll_pagina(pg)
    pg.evaluate("() => $('#cf-n_trafo').scrollIntoView()"); _captura(pg, "tg_2trafo_cupla", vp)
    ex = pg.evaluate("() => confExport()")
    assert ex["n_trafo"] == 2 and ex["cupla"] == "deschisa" and ex["aar"] is True and ex["uk_pct"] == 6 and ex["grupa_conexiuni"] == "Dyn11"
    b = ex["plecari"][i]
    assert b["vital"] is True and b["ups"] is True and b["n_circuite"] == 2 and b["cablu"] == {"tip_cablu": "CYABY", "S_fortat": 50, "n_paralel": 2}
    pg.click("#cf-ok")
    _planse(pg)
    c = pg.evaluate("() => MODEL.calc")
    assert c["n_trafo"] == 2 and c["cupla"] == "deschisa" and not pg.erori
    doua = pg.evaluate("() => !!(MODEL.bara && MODEL.bara.cupla) || JSON.stringify(MODEL).split('\"tip\": \"trafo\"').length - 1 >= 2 || JSON.stringify(MODEL).split('\"tip\":\"trafo\"').length - 1 >= 2")
    assert doua          # r11: motorul desenează TG-ul din PT cu 2 trafo + cuplă deschisă ca 2 secții de bare


@pytest.mark.parametrize("vp", VIEWPORTS)
def test_e2e_r11_locuinta_retea_dedusa(srv, browser, vp):
    """Locuință cu rețea dedusă (`_deduse`) → câmpul Rețea marcat galben; Q declarat cu atenționare; TD-uri, GE, EPS editabile."""
    pg = _pagina(browser, srv, *vp)

    def ruta(route):                        # contractul `_deduse` al interpretorului, impus aici ca să nu depindă de reguli
        r = route.fetch(); d = r.json()
        i = (d.get("interpretare") or {}).get("intrare_fizica")
        if i and i.get("tip_schema") == "locuinta":
            i.setdefault("retea", "tri"); i.setdefault("_deduse", ["retea"])
        route.fulfill(response=r, json=d)
    pg.route("**/api/chat", ruta)
    _chat(pg, "casă cu branșament nou, Pa 15 kW, Q 16 A, plită, cuptor, boiler, coloană 20 m, tablou secundar la garaj cu prize la 30 m")
    assert pg.input_value("#cf-retea") == "tri"
    assert pg.evaluate("() => $('#cf-retea').closest('.fld').classList.contains('cf-pres')")
    assert "dedus" in (pg.get_attribute("#cf-retea", "title") or "")
    assert "dedus" in pg.text_content(".cf-presl")
    assert pg.input_value("#cf-alimentare-tip") == "bransament_nou"
    # Q declarat 16 A sub Ib din Pa 15 kW → atenționare vizibilă (locală, apoi și cea a motorului)
    pg.wait_for_function("() => !$('#cf-qwarn').hidden && /16/.test($('#cf-qwarn').textContent)", timeout=10000)
    pg.wait_for_function("() => /Motorul ar folosi Q/.test($('#cf-qwarn').textContent)", timeout=15000)
    assert "cf-qwarn" in (pg.get_attribute("#cf-alimentare-In_Q_bransament_A", "aria-describedby") or "")
    # tablou secundar: sub-tabel editabil; generator; EPS
    if not pg.evaluate("() => CONF.ed.tablouri_secundare.length"):
        pg.click("#cf-td-add")
    pg.fill("#cf-td-0-nume", "TD Garaj"); pg.fill("#cf-td-0-L_m", "35"); pg.fill("#cf-td-0-cab_tip", "CYABY"); pg.fill("#cf-td-0-cab_S", "6")
    pg.click("#cf-td0c-add")
    pg.select_option("#cf-_ge", "ATS"); pg.fill("#cf-ge_rezerva-Sn_kVA", "10")
    pg.select_option("#cf-_eps", "circ")
    assert pg.is_visible("#cf-eps-h") and pg.is_visible("#cf-_eps-w")
    assert _fara_scroll_pagina(pg)
    pg.evaluate("() => $('#cf-retea').scrollIntoView()"); _captura(pg, "locuinta_retea_dedusa", vp)
    pg.evaluate("() => $('#cf-td-h').scrollIntoView()"); _captura(pg, "locuinta_td_ge_eps", vp)
    ex = pg.evaluate("() => confExport()")
    td = ex["tablouri_secundare"][0]
    assert td["nume"] == "TD Garaj" and td["L_m"] == 35 and td["cablu"] == {"tip_cablu": "CYABY", "S_fortat": 6} and len(td["circuite"]) >= 2
    assert ex["ge_rezerva"] == {"comutare": "ATS", "Sn_kVA": 10} and len(ex["backup"]["circuite"]) == 3 and ex["_deduse"] == ["retea"]
    # rețeaua aleasă de proiectant nu mai e „dedusă”: marcajul dispare și cheia nu mai pleacă la motor
    pg.select_option("#cf-retea", "tri")
    assert not pg.evaluate("() => $('#cf-retea').closest('.fld').classList.contains('cf-pres')")
    assert "_deduse" not in pg.evaluate("() => confExport()")
    assert not pg.erori


# --------------------------------------------------------------------------- versiunea web (Pyodide), opțional
@pytest.mark.skipif(not os.environ.get("SM_WEB_VENDOR"), reason="SM_WEB_VENDOR nu e setat (Pyodide + roți)")
def test_web_static_confirmare(browser, tmp_path):
    dest = tmp_path / "web"
    r = subprocess.run([sys.executable, str(ROOT / "web" / "build.py"), str(dest), os.environ["SM_WEB_VENDOR"], "--pagina"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    port = _port()
    pr = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=dest, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(0.5)
        pg = browser.new_page(viewport={"width": 1440, "height": 900}); erori = []
        pg.on("pageerror", lambda e: erori.append(str(e)))
        pg.goto(f"http://127.0.0.1:{port}/index.html")
        pg.wait_for_selector("#sm-boot", state="hidden", timeout=180000)
        pg.wait_for_function("() => typeof INFO !== 'undefined' && Object.keys(SABLOANE).length > 0", timeout=60000)
        pg.evaluate("() => { INFO.claude = false; }")
        _chat(pg, "CEF 300 kWp cu 3 invertoare de 100 kW și BESS 200 kWh")
        pg.fill("#cf-inv-0-n", "2"); pg.click("#cf-ok")
        pg.wait_for_function("() => !$('#conf') && MODEL.calc && MODEL.calc.invertoare[0].n === 2", timeout=60000)
        assert not erori
    finally:
        pr.terminate()
