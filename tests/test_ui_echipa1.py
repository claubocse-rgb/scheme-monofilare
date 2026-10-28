"""Echipa 1 de testare (teste/echipa1/ux.md, ui.md, product_owner.md): fluxul unificat, valorile presupuse vizibile,
atenționările, devizul la prima folosire, cartușul la primul export, defectele UI, telefonul, numele fișierelor,
Termenii / Confidențialitatea. Playwright + Chromium pe serverul local `python3 app.py PORT`, cu date curate (SM_DATE gol)."""
import json, os, pathlib, re, socket, subprocess, sys, tempfile, time, unicodedata, urllib.request
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
sys.path.insert(0, str(ROOT))


# --------------------------------------------------------------------------- fără browser
def test_nume_fisier_ascii_cu_extensie():
    import app
    n = app.nume_fisier("E01_BMPTd-40 — BLOC DE MĂSURĂ ȘI PROTECȚIE TRIFAZAT_pachet.zip")
    assert n == "E01_BMPTd-40-BLOC_DE_MASURA_SI_PROTECTIE_TRIFAZAT_pachet.zip"
    assert app.nume_fisier("A" * 120 + ".json").endswith(".json") and len(app.nume_fisier("A" * 120 + ".json")) <= 80
    assert app.nume_fisier("x/y:z*?<>|.pdf") == "x_y_z.pdf" and app.nume_fisier("") == "Schema_monofilara"


def test_structura_flux_si_terminologie():
    assert "const PASI = ['Ce proiectezi', 'Date de intrare'];" in HTML
    assert "function wizVerif(" not in HTML and "Sari la planșă" not in HTML
    i = HTML.index("async function confConfirma("); corp = HTML[i:HTML.index("\n}\n", i)]
    assert "plansaGata(" in corp and "_wiz = 1" not in corp
    # D7: „Planșă nouă” peste tot; titlurile secțiunilor ca pe pagina Exemple
    vizibil = re.findall(r"'([^']*)'", HTML)
    assert not [t for t in vizibil if "Schemă nouă" in t]
    assert "'Șabloane calculate și verificate'" in HTML and "'Desene de exemplu (fără calcul)'" in HTML
    assert "Schemă calculată și verificată" not in HTML and "Desen manual — fără verificare" not in HTML
    # D2: bifa are clasa ei (nu .conf, care e panoul de confirmare)
    assert "class: 'vconf'" in HTML and "class: 'check conf'" not in HTML
    # D20: separatorul din meniul de start nu mai are rol „presentation” în listă
    assert "class: 'sep', role: 'presentation'" not in HTML
    # copy: fără jargon „cheie API” în starea citirii, fără IE 11 promis
    assert "indisponibilă (fără cheie API)" not in HTML and "IE 11 smart meter" not in HTML


def test_build_web_copiaza_paginile_legale(tmp_path):
    vendor = tmp_path / "vendor"; (vendor / "pyodide").mkdir(parents=True); (vendor / "whl").mkdir()
    dest = tmp_path / "out"
    r = subprocess.run([sys.executable, str(ROOT / "web" / "build.py"), str(dest), str(vendor), "--pagina"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    for f in ("termeni.html", "confidentialitate.html", "index.html"):
        assert (dest / f).exists(), f
    t = (dest / "termeni.html").read_text(encoding="utf-8")
    for u in re.findall(r"url\((fonts/[\w.-]+)\)", t):
        assert (dest / u).exists(), u                                  # fonturile paginilor legale, relative
    assert 'href="confidentialitate.html"' in t
    idx = (dest / "index.html").read_text(encoding="utf-8")
    assert "const LEGAL=window.SM_WEB?'':'/static/';" in idx and "SM_WEB=true" in idx          # E2: pagina e minificată


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
    env = dict(os.environ, ANTHROPIC_API_KEY="", XDG_CONFIG_HOME=tempfile.mkdtemp(), SM_DATE=tempfile.mkdtemp())   # catalog / profile goale
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


def _pagina(browser, url, w=1440, h=900, acord=True):
    c = browser.new_context(viewport={"width": w, "height": h}, accept_downloads=True)
    pg = c.new_page()
    pg.erori = []
    pg.on("pageerror", lambda e: pg.erori.append(str(e)))
    if acord:          # Termenii acceptați deja (dialogul are testul lui)
        pg.add_init_script("try { localStorage.setItem('sm.acord', JSON.stringify({termeni:'0.1', confidentialitate:'0.1', reacceptare:'0.1'})); } catch {}")
    pg.goto(url)
    pg.wait_for_function("() => typeof INFO !== 'undefined' && Object.keys(SABLOANE).length > 0 && MODEL", timeout=60000)
    pg.wait_for_timeout(500)
    pg.evaluate("() => { INFO.claude = false; }")
    return pg


def _descrie(pg, text):
    pg.evaluate("() => acasaArata('nou')")
    pg.fill("#h-text", text); pg.click("#h-go")
    pg.wait_for_selector("#conf", timeout=30000)


def _confirma(pg):
    pg.click("#cf-ok")
    pg.wait_for_function("() => !$('#conf') && MODEL.calc && TAB === 'calc'", timeout=30000)
    pg.wait_for_function("() => $('#paper svg') && !$('#vstat').classList.contains('busy') && VALID", timeout=30000)
    pg.wait_for_timeout(600)


# 1. fluxul unificat ------------------------------------------------------------------------------
def test_confirma_si_deseneaza_deseneaza(srv, browser):
    pg = _pagina(browser, srv)
    _descrie(pg, "branșament trifazat 20 kW, coloană 30 m")
    assert "verifică descrierea" in pg.inner_text("#proj-name")              # D27: antetul spune unde ești
    assert "Pa 20 kW" in pg.inner_text("#cf-intel") and "30 m" in pg.inner_text("#cf-intel")
    pg.fill("#cf-L_coloana_m", "12")                                          # „Am înțeles” se recalculează din câmpuri
    assert "coloana C2 12 m" in pg.inner_text("#cf-intel")
    _confirma(pg)
    assert not pg.evaluate("() => wizActiv()") and pg.is_visible("#paper svg") and pg.is_visible(".tabs")
    assert pg.evaluate("() => MODEL.calc.L_coloana_m") == 12
    # aceeași sursă de adevăr: panoul din stânga (Calcul) arată datele confirmate
    assert pg.input_value("#c-l") == "12" and pg.input_value("#c-p") == "20"
    toasts = pg.evaluate("() => [...document.querySelectorAll('.toast')].map(t => t.innerText)")
    assert len(toasts) == 1 and "Planșa e desenată" in toasts[0]                # o singură notificare
    assert pg.evaluate("() => document.activeElement.id") == "t-calc"           # D6: focusul nu e pe <body>
    assert not pg.erori


def test_asistentul_doi_pasi_pana_la_plansa(srv, browser):
    pg = _pagina(browser, srv)
    pg.click("#ht-bmptd")
    pg.wait_for_function("() => MODEL._wiz === 1 && !HOME.on", timeout=30000)
    assert pg.locator("#wizbar li").count() == 2 and pg.is_visible("#wz-gen")
    pg.click("#wz-gen")
    pg.wait_for_function("() => !wizActiv() && TAB === 'calc'", timeout=30000)
    pg.wait_for_function("() => $('#paper svg')", timeout=30000)
    assert not pg.erori


def test_casa_fara_eroare_inainte_de_prima_actiune(srv, browser):
    pg = _pagina(browser, srv)
    pg.click("#ht-locuinta")
    pg.wait_for_function("() => MODEL._wiz === 1 && VALID", timeout=30000); pg.wait_for_timeout(800)
    # quick win 7: rețeaua neleasă e neutră până la prima încercare
    assert pg.get_attribute("#lc-retea", "aria-invalid") is None and "b" not in pg.get_attribute("#vbadge", "class").split()
    assert "rețeaua" in pg.inner_text("#vbadge").lower()
    pg.click("#wz-gen")
    pg.wait_for_function("() => document.querySelector('#lc-retea[aria-invalid=\"true\"]')", timeout=10000)
    assert pg.evaluate("() => wizActiv()") and not pg.erori


# 2. valorile presupuse ---------------------------------------------------------------------------
def test_presupuse_marcate_in_confirmare_si_calcul(srv, browser):
    pg = _pagina(browser, srv)
    _descrie(pg, "branșament trifazat 20 kW, coloană 30 m")
    pg.wait_for_function("() => $('#cf-schema_pamant').closest('.fld').classList.contains('cf-pres')", timeout=10000)
    assert "presupus" in pg.inner_text("label[for=cf-schema_pamant]")
    assert "marcat" in pg.inner_text("#cf-presn")
    _confirma(pg)
    marcate = pg.evaluate("() => [...document.querySelectorAll('#pane .cf-pres')].map(n => (n.querySelector('input,select') || {}).id)")
    for id_ in ("c-ik3", "c-zr", "c-cos", "c-spl", "c-mat", "c-iz"):
        assert id_ in marcate, (id_, marcate)
    assert pg.evaluate("() => $('#c-ik3').closest('.fld').querySelector('.cf-tag').textContent") == "presupus"
    assert "presupus" in pg.inner_text("details.adv > summary")             # secțiunea pliată spune câte are
    # completezi valoarea → nu mai e presupusă
    pg.evaluate("() => $('#c-ik3').closest('details').open = true")
    pg.fill("#c-ik3", "16")
    pg.wait_for_timeout(1500)
    assert not pg.evaluate("() => $('#c-ik3').closest('.fld').classList.contains('cf-pres')")
    # insigna: „Verificat” separat de „N valori presupuse de confirmat”
    assert pg.inner_text("#vbadge .vb-st") == "Verificat" and "presupuse" in pg.inner_text("#vbadge .vb-pr")
    assert pg.evaluate("() => getComputedStyle($('#vbadge .vb-st')).color") != pg.evaluate("() => getComputedStyle($('#vbadge .vb-pr')).backgroundColor")
    assert not pg.erori


# 3. atenționările --------------------------------------------------------------------------------
def test_atentionari_grupate_accept_toate_formula_in_detalii(srv, browser):
    pg = _pagina(browser, srv)
    _descrie(pg, "CEF 200 kW cu 4 invertoare de 50 kW racordată în TG existent, cablu 80 m, beneficiar SC Agro Vest SRL, Ciumeghiu")
    _confirma(pg)
    av = pg.evaluate("() => VALID.verificari.filter(v => v.nivel === 'AVERTISMENT' && !v.confirmat).length")
    assert av >= 4
    assert "Verificat" not in pg.inner_text("#vbadge") and "a" in pg.get_attribute("#vbadge", "class").split()   # nu verde cu atenționări
    randuri = pg.locator("#vres details.vdet[open] .vlist > li").count()
    assert 0 < randuri < av                                                       # grupate (V21 pe INV-1…4 = un rând)
    titluri = pg.evaluate("() => [...document.querySelectorAll('#vres .vlist > li .vt')].map(n => n.textContent)")
    assert len(titluri) == len(set(titluri))                                      # fără dubluri
    assert not [t for t in titluri if re.search(r"[<>≤≥]|·In|ΔU cumulat", t)]     # formulele nu sunt titlu…
    assert pg.locator("#vres .vlist > li details.vdetc").count() >= 1             # …ci în „Detalii de calcul”
    # D2: bifa și eticheta pe același rând, aliniate la stânga
    box = pg.evaluate("() => { const l = document.querySelector('#vres .vconf'); const i = l.querySelector('input').getBoundingClientRect(), t = l.querySelector('span').getBoundingClientRect(), li = l.closest('li').getBoundingClientRect(); return [Math.abs((i.top + i.bottom) / 2 - (t.top + t.bottom) / 2), i.left - li.left]; }")
    assert box[0] < 6 and box[1] < 24
    pg.click("#v-acc-tot")
    assert pg.is_visible("#v-acc-da") and pg.evaluate("() => (MODEL.confirmari || []).length") == 0   # cere confirmare
    pg.click("#v-acc-da")
    pg.wait_for_function("() => VALID.verificari.filter(v => v.nivel === 'AVERTISMENT' && !v.confirmat).length === 0", timeout=30000)
    pg.wait_for_timeout(500)
    assert "Verificat" in pg.inner_text("#vbadge")
    assert not pg.erori


def test_blocant_du_ma_la_camp_si_revino_la_automat(srv, browser):
    pg = _pagina(browser, srv)
    _descrie(pg, "branșament trifazat 20 kW, coloană 30 m")
    _confirma(pg)
    pg.select_option("#c-bloc", "BMPTd-16")
    pg.wait_for_function("() => VALID.verificari.some(v => v.cod === 'V50')", timeout=30000); pg.wait_for_timeout(500)
    li = pg.locator("#vres .vlist > li.b").first
    assert "Blocul impus BMPTd-16" in li.inner_text() and "≈" in li.inner_text()
    li.get_by_text("Du-mă la câmp").click()
    assert pg.evaluate("() => document.activeElement.id") == "c-bloc"
    pg.locator("#vres .vlist > li.b").first.get_by_text("Revino la blocul automat").click()
    pg.wait_for_function("() => !VALID.blocheaza", timeout=30000)
    assert pg.evaluate("() => MODEL.calc.bmpt_fortat") is None and not pg.erori


# 4. devizul la prima folosire ----------------------------------------------------------------------
def test_deviz_catalog_gol_mesaj_cu_actiune(srv, browser):
    pg = _pagina(browser, srv)
    _descrie(pg, "branșament trifazat 20 kW, coloană 30 m")
    _confirma(pg)
    pg.evaluate("() => setTab('deviz')")
    pg.wait_for_selector("#dv-gol", timeout=30000)
    assert "nu are încă prețuri" in pg.inner_text("#dv-gol") and pg.is_visible("#dv-imp")
    rec = pg.inner_text(".dv-rec")
    assert "— fără prețuri" in rec and not re.search(r"Materiale și echipamente\s*0,00", rec)
    assert not pg.erori


# 5. cartușul la primul export + 8. numele fișierului ------------------------------------------------
def test_primul_export_cere_proiectantul_o_data_si_nume_ascii(srv, browser):
    pg = _pagina(browser, srv)
    pg.evaluate("() => { try { localStorage.removeItem('sm.cartus.cerut'); } catch {} }")
    _descrie(pg, "branșament trifazat 20 kW, coloană 30 m")
    _confirma(pg)
    assert re.search(r"[ĂÂÎȘȚ—]", pg.evaluate("() => docName(MODEL)"))           # titlul are diacritice și „—”
    pg.click("#exp-more"); pg.click("#exp-menu [data-exp=svg]")
    pg.wait_for_selector("dialog.dlg[open] #cp-proiectant")
    assert pg.evaluate("() => document.activeElement.id") == "cp-proiectant"
    pg.fill("#cp-proiectant", "SC Proiect Test SRL"); pg.fill("#cp-proiectat", "ing. Ion Pop")
    pg.click("#cp-salv")
    pg.wait_for_selector("dialog.dlg[open] #as-cb")                              # E2: asumarea planșei de către proiectant
    assert pg.is_disabled("#as-ok"); pg.check("#as-cb")
    with pg.expect_download() as dl:
        pg.click("#as-ok")
    nume = dl.value.suggested_filename
    assert nume.endswith(".svg") and nume.isascii() and not re.search(r"[\s—·/\\:*?\"<>|]", nume), nume
    assert unicodedata.normalize("NFKD", nume) == nume
    assert pg.evaluate("() => MODEL.cartus.proiectant") == "SC Proiect Test SRL"
    assert pg.evaluate("() => profilActiv() && profilActiv().proiectat") == "ing. Ion Pop"        # ținut minte în Setări
    with pg.expect_download() as dl2:                                              # a doua oară: fără dialog
        pg.evaluate("() => exportAs('json')")
    assert dl2.value.suggested_filename.endswith(".json") and dl2.value.suggested_filename.isascii()
    assert not pg.query_selector("dialog.dlg[open]") and not pg.erori


# 6. defecte UI --------------------------------------------------------------------------------------
def test_d1_campuri_lizibile_in_panoul_editorului(srv, browser):
    pg = _pagina(browser, srv, 1280, 720)
    _descrie(pg, "casă trifazată")
    w = pg.evaluate("() => document.querySelector('#conf .cf-tab th:nth-child(4)') && [...document.querySelectorAll('#conf .cf-tab select[id$=-faza]')].map(s => s.getBoundingClientRect().width)")
    assert w and min(w) >= 96                                                       # „automat” încape (nu „automa”)
    pg.click("#cf-ok"); pg.wait_for_function("() => !$('#conf')", timeout=30000)
    pg.evaluate("() => acasaArata('nou')"); pg.click("#ht-bmptd")
    pg.wait_for_function("() => MODEL._wiz === 1", timeout=30000); pg.click("#wz-gen"); pg.wait_for_function("() => !wizActiv()")
    pg.wait_for_timeout(800)
    cols = pg.evaluate("() => getComputedStyle(document.querySelector('#pane .g3e')).gridTemplateColumns.split(' ').length")
    assert cols <= 2                                                                # panoul de 440 px: 2 coloane, nu 3
    assert pg.evaluate("() => getComputedStyle(document.querySelector('#pane .fld>label')).whiteSpace") == "normal"   # D18
    assert not pg.erori


def test_d3_mesajul_neinteles_e_vizibil(srv, browser):
    pg = _pagina(browser, srv, 1280, 720)
    pg.fill("#h-text", "asdf qwerty"); pg.click("#h-go")
    pg.wait_for_selector("#h-res .msg.err", timeout=30000); pg.wait_for_timeout(700)
    r = pg.evaluate("() => { const b = $('#h-res .msg.err').getBoundingClientRect(); return [b.top, b.bottom, innerHeight]; }")
    assert r[0] >= 0 and r[1] <= r[2]
    assert not pg.erori


def test_d4_dialog_capcana_focus_esc_revine(srv, browser):
    pg = _pagina(browser, srv)
    pg.evaluate("() => acasaInchide()")
    pg.evaluate("() => { $('#undo').disabled = false; $('#undo').focus(); window._d = dialogNou('Probă', [el('input', { id: 'dlg-a' }), el('input', { id: 'dlg-b' })], [el('button', { type: 'button', id: 'dlg-ok' }, 'OK')]); $('#dlg-a').focus(); }")
    for _ in range(6):
        pg.keyboard.press("Tab")
        assert pg.evaluate("() => !!document.activeElement.closest('dialog')")       # focusul nu iese din dialog
    assert pg.evaluate("() => !!document.querySelector('dialog.dlg').getAttribute('aria-labelledby')")
    pg.keyboard.press("Escape")
    assert not pg.query_selector("dialog.dlg") and pg.evaluate("() => document.activeElement.id") == "undo"
    assert not pg.erori


def test_d5_sertarul_tine_focusul(srv, browser):
    pg = _pagina(browser, srv, 390, 844)
    pg.click("#h-burger"); pg.wait_for_function("() => document.body.classList.contains('h-nav-open')")
    for _ in range(14):
        pg.keyboard.press("Tab")
        assert pg.evaluate("() => !$('#h-body').contains(document.activeElement)")
    pg.keyboard.press("Escape")
    assert not pg.evaluate("() => $('#h-body').inert") and not pg.erori


def test_d7_meniul_plansa_noua(srv, browser):
    pg = _pagina(browser, srv)
    pg.evaluate("() => acasaInchide()")
    pg.click("#new-btn")
    t = pg.inner_text("#new-menu")
    assert "Planșă nouă" in t and "Șabloane calculate și verificate" in t and "Schemă" not in t
    ordine = pg.evaluate("() => [...document.querySelectorAll('#new-menu button')].map(b => b.innerText.split('\\n')[0])")
    sab = pg.evaluate("() => ordineSabloane().map(k => SABLOANE[k].nume)")
    assert [x for x in ordine if x in sab][:len(sab)] == sab                 # (un desen de exemplu poate avea același nume)
    assert pg.inner_text("#ht-locuinta").startswith("Casă") and not pg.erori


# 7. telefon -------------------------------------------------------------------------------------------
def test_telefon_antet_etichete_plansa_lizibila_notificari(srv, browser):
    pg = _pagina(browser, srv, 390, 844)
    _descrie(pg, "branșament trifazat 20 kW, coloană 30 m")
    _confirma(pg)
    assert pg.evaluate("() => document.body.dataset.mview") == "plan"            # după desen, pe telefon se vede planșa
    pg.wait_for_timeout(800)
    assert pg.evaluate("() => VIEW.z") > 0.25                                       # încadrată pe schemă, nu ~10 %
    et = pg.evaluate("() => [...document.querySelectorAll('header .mlbl')].filter(n => n.offsetParent).map(n => n.textContent)")
    assert {"Anulează", "Fișier", "Export"} <= set(et)
    assert pg.evaluate("() => [...document.querySelectorAll('header .btn')].filter(b => b.offsetParent).every(b => b.getBoundingClientRect().height >= 44)")
    hdr = pg.evaluate("() => document.querySelector('header').getBoundingClientRect().bottom")
    t = pg.evaluate("() => { const t = document.querySelector('.toast'); return t ? t.getBoundingClientRect().top : null; }")
    assert t is not None and t >= hdr                                               # sub antet, nu peste cartuș (jos)
    pg.wait_for_function("() => !document.querySelector('.toast')", timeout=8000)    # dispare singură
    assert pg.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth") and not pg.erori


# Termeni / Confidențialitate ------------------------------------------------------------------------
def test_legaturi_termeni_si_confidentialitate(srv, browser):
    pg = _pagina(browser, srv)
    for sel in ("#h-leg a", "#exp-leg a"):
        hrefs = pg.evaluate(f"() => [...document.querySelectorAll('{sel}')].map(a => a.href)")
        assert len(hrefs) == 3 and hrefs[0].endswith("/static/termeni.html") and hrefs[1].endswith("/static/confidentialitate.html")
        assert hrefs[2].endswith("/static/beta.html")                               # E2: Condițiile de testare (pagina: tests/test_ui_e2.py)
        for h in hrefs[:2]:
            assert urllib.request.urlopen(h, timeout=5).status == 200
    pg.evaluate("() => acasaArata('cont')")
    assert pg.locator("#h-main a[href$='termeni.html']").count() == 1
    pg.evaluate("() => acasaArata('setari')")
    a = pg.locator("#h-main a.leg-anth")
    assert a.count() == 1 and a.get_attribute("href").endswith("confidentialitate.html#5-citirea-avansata-cu-cheia-ta-anthropic")
    assert pg.locator("#llm-avert a.leg-anth").count() == 1
    html = urllib.request.urlopen(a.evaluate("n => n.href").split("#")[0], timeout=5).read().decode()
    assert 'id="5-citirea-avansata-cu-cheia-ta-anthropic"' in html
    assert not pg.erori


def test_acord_la_primul_export_inclusiv_json(srv, browser):
    pg = _pagina(browser, srv, acord=False)
    pg.evaluate("() => { try { localStorage.removeItem('sm.acord'); localStorage.setItem('sm.cartus.cerut', 'true'); } catch {} }")
    _descrie(pg, "branșament trifazat 20 kW, coloană 30 m")
    _confirma(pg)
    pg.keyboard.press("Control+s")                                                 # scurtătura Ctrl+S → .json
    pg.wait_for_selector("dialog.dlg[open] #ac-ok")
    cb = pg.evaluate("() => ['ac-1', 'ac-2', 'ac-3'].map(id => $('#' + id).checked)")
    assert cb == [False, False, False] and pg.is_disabled("#ac-ok")                 # nimic precompletat
    assert pg.locator("dialog.dlg[open] a[href$='termeni.html']").count() >= 1
    pg.click("dialog.dlg[open] details.ac-det > summary")
    pg.wait_for_function("() => $('#ac-clauze').dataset.ok === '1'", timeout=10000)
    assert "9.5" in pg.inner_text("#ac-clauze") or "Limitarea" in pg.inner_text("#ac-clauze")
    pg.check("#ac-1"); pg.check("#ac-3")
    assert pg.is_disabled("#ac-ok")                                                 # bifa separată pentru clauze e obligatorie
    pg.click("#ac-nu")                                                              # „Nu acum”: fără export
    assert not pg.query_selector("dialog.dlg[open]") and pg.evaluate("() => localStorage.getItem('sm.acord')") is None
    pg.evaluate("() => { exportAs('json'); }"); pg.wait_for_selector("dialog.dlg[open] #ac-ok")
    for i in (1, 2, 3):
        pg.check(f"#ac-{i}")
    with pg.expect_download() as dl:
        pg.click("#ac-ok")
    assert dl.value.suggested_filename.endswith(".json")
    v = json.loads(pg.evaluate("() => localStorage.getItem('sm.acord')"))
    assert v["termeni"] == "0.1" and v["reacceptare"] == "0.1" and v["context"] == "export"
    with pg.expect_download():                                                      # acceptat: nu mai apare
        pg.evaluate("() => exportAs('json')")
    assert not pg.query_selector("dialog.dlg[open]")
    pg.evaluate("() => { ACORD.reacceptare_de_la = '0.2'; }")                       # versiune nouă cu reacceptare → din nou
    pg.evaluate("() => { exportAs('dxf'); }"); pg.wait_for_selector("dialog.dlg[open] #ac-ok")
    assert not pg.erori
