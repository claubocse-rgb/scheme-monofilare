"""E2 (interfața): filigranul și asumarea la export, Condițiile de testare (beta) la prima intrare, revizii, soluția GE,
limitarea în PCC, tab-ul Documente (+ PVGIS cu rezervă manuală), galeria de circuite, importul Excel / CSV, restanțe D4,
build-ul web care ascunde codul. Playwright + Chromium pe `python3 app.py PORT` cu date curate. Capturi: teste/e2/ui/."""
import io, json, os, pathlib, re, shutil, socket, subprocess, sys, tempfile, time, urllib.request, zipfile
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CAPT = ROOT / "teste" / "e2" / "ui"
HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
sys.path.insert(0, str(ROOT / "web"))


# --------------------------------------------------------------------------- fără browser
def test_config_filigran_implicit():
    cfg = (ROOT / "static" / "config.js").read_text(encoding="utf-8")
    assert "FILIGRAN: true" in cfg
    assert "kromotec · versiune gratuită" in HTML and "c.FILIGRAN !== false" in HTML


def _build(tmp_path, *extra):
    vendor = tmp_path / "vendor"; (vendor / "pyodide").mkdir(parents=True); (vendor / "whl").mkdir()
    (vendor / "pyodide" / "pyodide.js").write_text("var a = 1; // comentariu\n//# sourceMappingURL=pyodide.js.map\n")
    (vendor / "pyodide" / "pyodide.js.map").write_text("{}")
    dest = tmp_path / "out"
    r = subprocess.run([sys.executable, str(ROOT / "web" / "build.py"), str(dest), str(vendor), "--pagina", *extra], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return dest


def test_build_ascunde_codul(tmp_path):
    dest = _build(tmp_path)
    assert not (dest / "app_src.json").exists() and (dest / "app_src.zip.wasm").exists()
    with zipfile.ZipFile(dest / "app_src.zip.wasm") as z:
        nume = z.namelist()
        assert "web/web_api.py" in nume or "web/web_api.pyc" in nume
        if any(n.endswith(".pyc") for n in nume):                # python3.12 pe mașina de build → doar bytecode
            assert not [n for n in nume if n.endswith(".py")]
        else:                                                      # rezervă: sursa fără comentarii / docstring-uri
            t = z.read("engine/layout.py").decode()
            assert not re.search(r"^\s*#", t, re.M) and '"""' not in t
    idx = (dest / "index.html").read_text(encoding="utf-8")
    assert '<meta name="robots" content="noindex, nofollow' in idx and "<title>" not in idx
    assert "/* ===" not in idx and "\n  " not in idx                # fără comentarii, fără indentare
    assert "// E2:" not in idx and "// echipa" not in idx
    w = (dest / "worker.js").read_text(encoding="utf-8")
    assert "//" not in w.replace("://", "") and "app_src.zip" in w
    assert (dest / "robots.txt").read_text() == "User-agent: *\nDisallow: /\n"
    assert "X-Robots-Tag: noindex" in (dest / "_headers").read_text()
    assert not (dest / "pyodide" / "pyodide.js.map").exists()
    assert "sourceMappingURL" not in (dest / "pyodide" / "pyodide.js").read_text()
    for f in ("termeni.html", "confidentialitate.html", "beta.html"):
        if (ROOT / "static" / f).exists():
            assert "noindex" in (dest / f).read_text(encoding="utf-8"), f
    # --sursa: fără minificare (depanare)
    d2 = _build(tmp_path / "s", "--sursa")
    assert "const LEGAL = window.SM_WEB ? '' : '/static/';" in (d2 / "index.html").read_text(encoding="utf-8")


@pytest.mark.skipif(not shutil.which("node"), reason="node lipsește")
def test_minificarea_js_pastreaza_comportamentul():
    import minif
    cod = r"""
const a = [1, 2, 3]; let i = 0
i++
const re = /[/"'`]+\//g, s = 'x // nu e comentariu', t = "/* nici asta */"
const tpl = `n=${a.map(x => `<${x}>`).join('')} ${ { k: 1 }.k } \` ${'}'}`
function f(x) {
  return x
    / 2
}
const g = x => x - -1, h = i + +'2', o = { a: 1 }?.a
/* bloc
   comentariu */
let u = 1
;[u] = [u + 1]
const r2 = 'a/b'.split(/\//).length, d = 10 / 2 / 5, e = typeof /x/
console.log(JSON.stringify([re.source, s, t, tpl, f(8), g(1), h, o, u, r2, d, e, 1.5e-3, .5]))
"""
    def rul(c):
        return subprocess.run(["node", "-e", c], capture_output=True, text=True, timeout=30)
    a, b = rul(cod), rul(minif.js(cod))
    assert a.returncode == 0, a.stderr
    assert b.returncode == 0, (b.stderr, minif.js(cod))
    assert a.stdout == b.stdout
    assert len(minif.js(cod)) < len(cod)


# --------------------------------------------------------------------------- browser
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
    env = dict(os.environ, ANTHROPIC_API_KEY="", XDG_CONFIG_HOME=tempfile.mkdtemp(), SM_DATE=tempfile.mkdtemp())
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


ACORD = ("try { localStorage.setItem('sm.acord', JSON.stringify({termeni:'0.1', confidentialitate:'0.1', reacceptare:'0.1'}));"
         " localStorage.setItem('sm.cartus.cerut', 'true'); } catch {}")


def _pagina(browser, url, w=1440, h=900, beta=True, cfg=None):
    nou = browser.new_context if beta else (lambda **k: type(browser)._sm_new_context_orig(browser, **k))
    c = nou(viewport={"width": w, "height": h}, accept_downloads=True)
    pg = c.new_page()
    pg.erori = []
    pg.on("pageerror", lambda e: pg.erori.append(str(e)))
    pg.add_init_script(ACORD)
    if cfg is not None:
        pg.route("**/static/config.js", lambda r: r.fulfill(body=cfg, content_type="application/javascript"))
    pg.goto(url)
    pg.wait_for_function("() => typeof INFO !== 'undefined' && Object.keys(SABLOANE).length > 0 && MODEL", timeout=60000)
    pg.wait_for_timeout(400)
    pg.evaluate("() => { INFO.claude = false; }")
    return pg


def _sablon(pg, k):
    pg.evaluate(f"() => newFromSablon('{k}')")
    pg.wait_for_function(f"() => MODEL.calc && MODEL.calc.tip_schema === {json.dumps({'bmptd': 'bransament', 'ge': 'ge_ats', 'tg': 'tablou'}.get(k, k))}", timeout=30000)
    pg.evaluate("() => { acasaInchide(); }")
    pg.wait_for_function("() => $('#paper svg') && VALID", timeout=30000)
    pg.wait_for_timeout(500)


def _capt(pg, nume):
    CAPT.mkdir(parents=True, exist_ok=True)
    pg.screenshot(path=str(CAPT / f"{nume}.png"))


def test_beta_la_prima_intrare(srv, browser):
    pg = _pagina(browser, srv, beta=False)
    pg.wait_for_selector("dialog.dlg[open] #beta-cb", timeout=10000)
    _capt(pg, "01-beta-prima-intrare-1440")
    assert pg.is_disabled("#beta-ok") and not pg.is_checked("#beta-cb")          # nimic precompletat
    href = pg.get_attribute("#beta-link", "href")
    assert href.endswith("beta.html")
    if (ROOT / "static" / "beta.html").exists():
        t = urllib.request.urlopen(srv + "static/beta.html", timeout=5).read().decode()
        assert "testare" in t.lower()
    assert pg.locator("dialog.dlg[open] .dlg-h button").count() == 0             # fără ✕
    pg.keyboard.press("Escape")
    assert pg.query_selector("dialog.dlg[open] #beta-cb")                          # Esc nu-l închide
    pg.check("#beta-cb"); pg.click("#beta-ok")
    assert not pg.query_selector("dialog.dlg[open]")
    v = json.loads(pg.evaluate("() => localStorage.getItem('sm.acord_beta')"))
    assert v["versiune"] == "0.1" and v["la"]
    pg.reload(); pg.wait_for_function("() => typeof INFO !== 'undefined' && MODEL", timeout=60000); pg.wait_for_timeout(600)
    assert not pg.query_selector("dialog.dlg[open]")                              # o singură dată
    # legătura din meniu (pagina de start) și din meniul de export
    assert pg.locator("#h-leg a[href$='beta.html']").count() == 1 and pg.locator("#exp-leg a[href$='beta.html']").count() == 1
    assert not pg.erori


def test_beta_fara_stocare_tine_cat_sesiunea(srv, browser):
    c = type(browser)._sm_new_context_orig(browser, viewport={"width": 1280, "height": 720})
    pg = c.new_page(); erori = []
    pg.on("pageerror", lambda e: erori.append(str(e)))
    pg.add_init_script("Object.defineProperty(window, 'localStorage', { get() { throw new Error('blocat'); } });")
    pg.goto(srv)
    pg.wait_for_selector("dialog.dlg[open] #beta-cb", timeout=60000)
    pg.check("#beta-cb"); pg.click("#beta-ok")
    assert pg.evaluate("() => acordBetaValid()") and not erori


def test_filigran_si_asumare_la_export(srv, browser):
    pg = _pagina(browser, srv)
    _sablon(pg, "bmptd")
    corpuri = []
    pg.on("request", lambda r: corpuri.append(r.post_data) if "/api/export/" in r.url else None)
    pg.click("#exp-more"); pg.click("#exp-menu [data-exp=svg]")
    pg.wait_for_selector("dialog.dlg[open] #as-cb")
    assert "kromotec · versiune gratuită" in pg.inner_text("#as-fil")
    assert "Am verificat planșa și îmi asum conținutul ca proiectant" in pg.inner_text("dialog.dlg[open]")
    assert pg.is_disabled("#as-ok")
    _capt(pg, "02-asumare-export-1440")
    pg.check("#as-cb")
    with pg.expect_download() as dl:
        pg.click("#as-ok")
    svg = pathlib.Path(dl.value.path()).read_text(encoding="utf-8")
    assert "kromotec · versiune gratuită" in svg                                    # în fișier (motorul sau rezerva interfeței)
    assert json.loads(corpuri[-1])["filigran"] == "kromotec · versiune gratuită"
    with pg.expect_download():                                                      # aceeași stare: nu se mai cere
        pg.evaluate("() => exportAs('svg')")
    assert not pg.query_selector("dialog.dlg[open]")
    with pg.expect_download() as dj:                                                # proiectul (.json): fără bifă, fără filigran
        pg.evaluate("() => exportAs('json')")
    assert "filigran" not in json.loads(pathlib.Path(dj.value.path()).read_text(encoding="utf-8"))
    pg.evaluate("() => { mutate(() => { MODEL.cartus.beneficiar = 'SC Alt Beneficiar SRL'; }); }")   # proiectul s-a schimbat → din nou
    pg.evaluate("() => { exportAs('svg'); }"); pg.wait_for_selector("dialog.dlg[open] #as-cb")
    pg.click("#as-nu")
    assert not pg.query_selector("dialog.dlg[open]") and not pg.erori


def test_fara_filigran_cand_config_il_opreste(srv, browser):
    cfg = "window.SM_CONFIG = { SUPABASE_URL: '', SUPABASE_ANON_KEY: '', FILIGRAN: false };"
    pg = _pagina(browser, srv, cfg=cfg)
    _sablon(pg, "bmptd")
    corpuri = []
    pg.on("request", lambda r: corpuri.append(r.post_data) if "/api/export/" in r.url else None)
    pg.evaluate("() => { exportAs('svg'); }"); pg.wait_for_selector("dialog.dlg[open] #as-cb")
    assert not pg.query_selector("#as-fil")
    pg.check("#as-cb")
    with pg.expect_download() as dl:
        pg.click("#as-ok")
    assert "kromotec" not in pathlib.Path(dl.value.path()).read_text(encoding="utf-8")
    assert "filigran" not in json.loads(corpuri[-1]) and not pg.erori


def test_revizii_in_tabul_proiect(srv, browser):
    pg = _pagina(browser, srv)
    _sablon(pg, "bmptd")
    pg.evaluate("() => setTab('proiect')")
    pg.click("#rev-add")
    assert pg.evaluate("() => MODEL.revizii.length") == 1 and pg.evaluate("() => MODEL.revizii[0].descriere") == "Emisă pentru autorizare"
    pg.click("#rev-add")
    assert pg.evaluate("() => document.activeElement.id") == "rev1-descriere"
    pg.keyboard.type("Modificat traseul coloanei")
    pg.fill("#rev1-rev", "1")
    assert pg.evaluate("() => MODEL.cartus.rev") == "1"                             # ultima revizie → câmpul „Revizia”
    pg.evaluate("() => setTab('calc')"); pg.fill("#c-l", "35")                     # recalcul: reviziile rămân
    pg.wait_for_function("() => MODEL.calc.L_coloana_m === 35", timeout=10000); pg.wait_for_timeout(1500)
    assert pg.evaluate("() => MODEL.revizii.map(r => r.descriere)") == ["Emisă pentru autorizare", "Modificat traseul coloanei"]
    assert pg.evaluate("() => payload(false).revizii.length") == 2
    pg.evaluate("() => setTab('proiect')")
    _capt(pg, "03-revizii-proiect-1440")
    pg.click("#rev-t button[aria-label='Șterge revizia 1']")
    assert pg.evaluate("() => MODEL.revizii.length") == 1 and not pg.erori


def test_ge_solutia_de_protectie(srv, browser):
    pg = _pagina(browser, srv)
    _sablon(pg, "ge")
    opt = pg.evaluate("() => [...$('#c-gep').options].map(o => o.value)")
    assert opt == ["", "excitatie", "echipotential"]                              # valorile motorului (GE_PROTECTIE_OPTIUNI)
    assert "scurtcircuit" in pg.inner_text("#c-gep-h")
    pg.select_option("#c-gep", "excitatie")
    pg.wait_for_function("() => MODEL.calc.ge_protectie === 'excitatie'")
    pg.wait_for_function("() => /PMG|AREP/.test($('#c-gep-h').textContent) && /Implică/.test($('#c-gep-h').textContent)", timeout=10000)
    pg.select_option("#c-gep", "echipotential")
    pg.wait_for_function(r"() => /echipotențializare/.test($('#c-gep-h').textContent) && /415\.2/.test($('#c-gep-h').textContent)", timeout=10000)
    _capt(pg, "04-ge-protectie-1440")
    pg.select_option("#c-gep", "")
    pg.wait_for_function("() => !('ge_protectie' in MODEL.calc)")
    assert not pg.erori


def test_cef_limitare_pcc(srv, browser):
    pg = _pagina(browser, srv)
    _sablon(pg, "cef")
    pg.fill("#c-lpcc", "250")
    pg.wait_for_function("() => MODEL.calc.limitare_PCC_kW === 250")
    pg.fill("#c-lpcc", "60,5")
    pg.wait_for_function("() => MODEL.calc.limitare_PCC_kW === 60.5")
    pg.fill("#c-lpcc", "")
    pg.wait_for_function("() => !('limitare_PCC_kW' in MODEL.calc)")
    assert not pg.erori


PVGIS_OK = {"outputs": {"totals": {"fixed": {"E_y": 1287.4}}, "monthly": {"fixed": [{"month": m, "E_m": 50 + m} for m in range(1, 13)]}}}


def test_documente_si_pvgis(srv, browser):
    pg = _pagina(browser, srv)
    _sablon(pg, "cef")
    pg.click("#t-doc")
    for k in ("cabluri", "reglaje", "curbe", "pierderi", "spd", "productie"):
        assert pg.query_selector(f"#doc-{k}"), k
    assert not pg.query_selector("#doc-carcasa")                                   # carcasa DIN: nu la CEF
    for k in ("etichete", "racordare", "caiet"):
        assert pg.query_selector(f"#doc-{k}-exp"), k
    pg.click("#doc-cabluri > summary")
    pg.wait_for_function("() => $('#doc-cabluri-b').textContent.trim() && !$('#doc-cabluri-b [aria-busy]')", timeout=20000)
    assert pg.inner_text("#doc-cabluri-b").strip()                                 # conținut sau „nu e încă disponibil”
    # meniul de export are documentele
    pg.click("#exp-more")
    ks = pg.evaluate("() => [...document.querySelectorAll('#exp-docs [data-exp]')].map(b => b.dataset.exp)")
    assert {"cabluri", "reglaje", "curbe", "productie", "etichete", "racordare", "caiet"} <= set(ks)
    pg.keyboard.press("Escape")
    # PVGIS: răspuns simulat → producția specifică și cea lunară
    pg.route("https://re.jrc.ec.europa.eu/**", lambda r: r.fulfill(json=PVGIS_OK, headers={"Access-Control-Allow-Origin": "*"}))
    pg.click("#doc-productie > summary")
    pg.fill("#pv-lat", "47,05"); pg.fill("#pv-lon", "21,93")
    pg.click("#pv-go")
    pg.wait_for_function("() => MODEL.calc.productie && MODEL.calc.productie.kWh_kWp_an === 1287", timeout=15000)
    p = pg.evaluate("() => MODEL.calc.productie")
    assert p["lat"] == 47.05 and len(p["lunar"]) == 12 and "PVGIS" in p["sursa"]
    pg.wait_for_selector("#pv-tot")
    assert "MWh/an" in pg.inner_text("#pv-tot")
    _capt(pg, "05-documente-pvgis-1440")
    # PVGIS indisponibil → mesaj + câmpul manual
    pg.unroute("https://re.jrc.ec.europa.eu/**")
    pg.route("https://re.jrc.ec.europa.eu/**", lambda r: r.abort())
    pg.click("#pv-go")
    pg.wait_for_selector("#pv-err", timeout=15000)
    assert "manual" in pg.inner_text("#pv-err") and pg.evaluate("() => document.activeElement.id") == "pv-man"
    pg.fill("#pv-man", "1150"); pg.dispatch_event("#pv-man", "change")
    pg.wait_for_function("() => MODEL.calc.productie.kWh_kWp_an === 1150 && MODEL.calc.productie.sursa === 'introdusă manual'", timeout=10000)
    assert not pg.erori


def test_documente_fara_calcul_si_carcasa_la_tablou(srv, browser):
    pg = _pagina(browser, srv)
    _sablon(pg, "tg")
    pg.click("#t-doc")
    assert pg.query_selector("#doc-carcasa") and not pg.query_selector("#doc-productie")
    pg.evaluate("() => newFromPreset(Object.keys(PRESETS)[0])"); pg.wait_for_timeout(800)
    pg.evaluate("() => setTab('documente')")
    assert "desenată manual" in pg.inner_text("#pane")
    assert pg.evaluate("() => document.querySelector('#exp-menu .exp-doc').hidden")
    assert not pg.erori


def test_galerie_circuite_intre_proiecte(srv, browser):
    pg = _pagina(browser, srv)
    pg.evaluate("() => localStorage.removeItem('sm.galerie')")
    _sablon(pg, "tg")
    pg.click("#gal-btn")
    pg.wait_for_selector("dialog.dlg[open] #gal-l")
    assert "goală" in pg.inner_text("#gal-l")
    pg.check("#gal-c2"); pg.click("#gal-sc")                                      # plecarea „Pompe” (30 kW)
    pg.fill("#gal-nume", "TG hală tip"); pg.click("#gal-st")                       # tot tabloul
    gal = pg.evaluate("() => JSON.parse(localStorage.getItem('sm.galerie'))")
    assert gal["versiune"] == 1; g = gal["elemente"]                               # formatul engine/galerie.py
    assert [x["tip"] for x in g] == ["tablou", "plecare"] and g[0]["nume"] == "TG hală tip" and g[1]["date"]["P_kW"] == 30
    assert g[0]["tip_schema"] == "tablou" and len(g[0]["date"]["plecari"]) == 3 and g[0]["id"].startswith("g-")
    assert not any('"_k"' in json.dumps(x) for x in g)                               # fără chei interne
    _capt(pg, "06-galerie-1440")
    pg.keyboard.press("Escape")
    # alt proiect (locuință): circuitul se convertește, tabloul devine tablou secundar
    pg.evaluate("() => newFromSablon('locuinta')"); pg.wait_for_function("() => MODEL.calc.tip_schema === 'locuinta'", timeout=30000)
    pg.evaluate("() => { acasaInchide(); setTab('calc'); }"); pg.wait_for_timeout(500)
    n0 = pg.evaluate("() => MODEL.calc.circuite.length")
    pg.click("#gal-btn"); pg.wait_for_selector("dialog.dlg[open] #gal-l li button")
    pg.locator("#gal-l li", has_text="Pompe").get_by_role("button", name="Inserează").click()
    assert pg.evaluate("() => MODEL.calc.circuite.length") == n0 + 1
    c = pg.evaluate("() => MODEL.calc.circuite.at(-1)")
    assert c["nume"] == "Pompe" and c["P_kW"] == 30 and c["receptor"] in [r[0] for r in pg.evaluate("() => RECEPTOR_LOC")]
    pg.click("#gal-btn"); pg.wait_for_selector("dialog.dlg[open] #gal-l li button")
    pg.locator("#gal-l li", has_text="TG hală tip").get_by_role("button", name="Inserează").click()
    ts = pg.evaluate("() => MODEL.calc.tablouri_secundare")
    assert ts[-1]["nume"] == "TG hală tip" and len(ts[-1]["circuite"]) >= 3
    pg.evaluate("() => undo()")                                                    # se poate anula
    assert not pg.evaluate("() => (MODEL.calc.tablouri_secundare || []).some(t => t.nume === 'TG hală tip')")
    assert not pg.erori


CSV = "﻿Nume;Receptor;P [kW];In [A];L [m];Faza;Tablou\nHală prize;prize;;32;60;;\nCompresor;motor;7,5;;40;;\nIluminat birou;iluminat;1,2;;25;;TD-Birou\nPrize birou;prize;2;;20;;TD-Birou\n"


def test_import_circuite_csv_si_xlsx(srv, browser, tmp_path):
    pg = _pagina(browser, srv)
    _sablon(pg, "tg")
    n0 = pg.evaluate("() => MODEL.calc.plecari.length")
    pg.click("#imp-btn"); pg.wait_for_selector("dialog.dlg[open] #imp-f")
    with pg.expect_download() as dl:                                               # modelul descărcabil
        pg.click("#imp-model")
    model = pathlib.Path(dl.value.path()).read_text(encoding="utf-8-sig")
    assert model.startswith("Nume;Receptor;P [kW];In [A];L [m];Faza;Tablou")
    f = tmp_path / "circuite.csv"; f.write_text(CSV, encoding="utf-8")
    pg.set_input_files("#imp-f", str(f))
    pg.wait_for_selector("#imp-prev")
    assert pg.input_value("#imp-m-nume") == "0" and pg.input_value("#imp-m-P_kW") == "2" and pg.input_value("#imp-m-tablou") == "6"
    assert pg.locator("#imp-prev tbody tr").count() == 4
    _capt(pg, "07-import-csv-1440")
    pg.click("#imp-ok")
    pl = pg.evaluate("() => MODEL.calc.plecari")
    assert len(pl) == n0 + 3                                                       # 2 plecări + TD-Birou cu 2 circuite
    assert pl[n0]["nume"] == "Hală prize" and pl[n0]["In_A"] == 32 and pl[n0]["L_m"] == 60 and pl[n0]["receptor"] == "prize"
    assert pl[n0 + 1]["P_kW"] == 7.5 and pl[n0 + 1]["receptor"] == "motor"
    assert pl[n0 + 2]["nume"] == "TD-Birou" and [x["nume"] for x in pl[n0 + 2]["copii"]] == ["Iluminat birou", "Prize birou"]
    # .xlsx (locuință, înlocuiește circuitele)
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook(); ws = wb.active
    for r in (["Circuit", "Receptor", "Putere kW", "Lungime m", "Faza"], ["Plită", "Plită", 7.2, 12, "3F"], ["Boiler", "boiler", 2, 8, "L2"]):
        ws.append(r)
    fx = tmp_path / "casa.xlsx"; wb.save(fx)
    pg.evaluate("() => newFromSablon('locuinta')"); pg.wait_for_function("() => MODEL.calc.tip_schema === 'locuinta'", timeout=30000)
    pg.evaluate("() => { acasaInchide(); setTab('calc'); }"); pg.wait_for_timeout(500)
    pg.click("#imp-btn"); pg.set_input_files("#imp-f", str(fx)); pg.wait_for_selector("#imp-prev")
    pg.select_option("#imp-mod", "inlocuieste"); pg.click("#imp-ok")
    ci = pg.evaluate("() => MODEL.calc.circuite")
    assert [(c["nume"], c["receptor"], c.get("P_kW"), c.get("L_m"), c.get("faza")) for c in ci] == [("Plită", "plita", 7.2, 12, "3F"), ("Boiler", "boiler", 2, 8, "L2")]
    assert not pg.erori


def test_import_csv_windows_1250_si_document_indisponibil(srv, browser, tmp_path):
    pg = _pagina(browser, srv)
    _sablon(pg, "tg")
    pg.click("#imp-btn")
    f = tmp_path / "w.csv"; f.write_bytes("Nume;In [A]\nPompă hală;40\n".encode("cp1250"))
    pg.set_input_files("#imp-f", str(f)); pg.wait_for_selector("#imp-prev")
    assert "Pompă hală" in pg.inner_text("#imp-prev")
    pg.click("#imp-ok")
    assert pg.evaluate("() => [MODEL.calc.plecari.at(-1).nume, MODEL.calc.plecari.at(-1).In_A]") == ["Pompă hală", 40]
    # documentul pe care motorul nu-l are încă: mesaj clar, nu „eroare”
    pg.wait_for_timeout(1500)
    if pg.evaluate("() => VALID && !VALID.blocheaza"):
        pg.evaluate("() => { exportAs('caiet'); }"); pg.wait_for_selector("dialog.dlg[open] #as-cb")
        pg.check("#as-cb"); pg.click("#as-ok")
        pg.wait_for_function("() => [...document.querySelectorAll('.toast')].some(t => /Caiet de sarcini|Descărcat/.test(t.innerText))", timeout=15000)
        assert not [t for t in pg.evaluate("() => [...document.querySelectorAll('.toast')].map(t => t.innerText)") if "nu a reușit" in t]
    assert not pg.erori


def test_import_fisier_invalid(srv, browser, tmp_path):
    pg = _pagina(browser, srv)
    _sablon(pg, "tg")
    pg.click("#imp-btn")
    f = tmp_path / "rau.xlsx"; f.write_bytes(b"nu e zip")
    pg.set_input_files("#imp-f", str(f))
    pg.wait_for_selector("dialog.dlg[open] .msg.err")
    assert pg.is_disabled("#imp-ok") and not pg.erori


# restanțe D4 --------------------------------------------------------------------------------------
def test_d4_select_tip_schema_netaiat_la_1280(srv, browser):
    pg = _pagina(browser, srv, 1280, 720)
    _sablon(pg, "bmptd")
    pg.evaluate("() => setTab('calc')")
    r = pg.evaluate("""() => { const s = $('#c-tip'), cs = getComputedStyle(s), sp = document.createElement('span');
        sp.style.font = cs.font; sp.style.position = 'absolute'; sp.textContent = s.selectedOptions[0].text; document.body.append(sp);
        const w = sp.getBoundingClientRect().width; sp.remove();
        return [w, s.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) - 16, s.selectedOptions[0].text]; }""")
    assert r[2] == "Branșament BMPT/BMPM" and r[0] <= r[1], r
    _capt(pg, "08-d4-select-1280")
    assert not pg.erori


def test_d4_cef_pe_telefon_incadrat_lizibil(srv, browser):
    pg = _pagina(browser, srv, 390, 844)
    _sablon(pg, "cef")
    pg.evaluate("() => setMView('plan')"); pg.wait_for_timeout(900)
    z, zf = pg.evaluate("() => [VIEW.z, fitZ()]")
    assert z > zf * 1.4                                                             # schema, nu foaia întreagă (~14 %)
    # etichetele aparatelor rămân în ecran pe orizontală
    afara = pg.evaluate("""() => { const st = $('#stage').getBoundingClientRect(); let n = 0;
        document.querySelectorAll('#paper .sym').forEach(g => { const r = g.getBoundingClientRect(); if (r.width && (r.left < st.left - 1 || r.right > st.right + 1)) n++; }); return n; }""")
    assert afara == 0
    _capt(pg, "09-d4-cef-telefon-390")
    assert not pg.erori
