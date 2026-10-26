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
    pg.evaluate("() => { WIZ_START = null; render(); $('#assist').open = true; }")
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
    pg.wait_for_function("() => !$('#conf') && MODEL.calc && MODEL._wiz === 1", timeout=30000)
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
