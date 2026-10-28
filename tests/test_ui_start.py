"""Pagina de start, „Pornește din descriere” (bug A), proiectele (local + Supabase simulat), versiunea web.

* structura: static/index.html (pagina de start, meniul, conturile), static/config.js gol, supabase/schema.sql (RLS);
* Chromium (Playwright) pe `python3 app.py PORT`: pagina de start la deschidere; „Planșă nouă → Branșament” deschide
  asistentul; cele 6 fraze ale bugului A; „Proiectele mele” (listare, redenumire, duplicare, ștergere, redeschidere);
* Supabase cu un client simulat (fără rețea): intrare în cont, salvare automată + explicită (cu versiune), listare, import;
* capturi desktop + mobil (390 px) în teste/ui_start/;
* opțional, versiunea web (Pyodide): SM_WEB_VENDOR=<vendor> → build + un scenariu în pagina statică.
"""
import json, os, pathlib, re, shutil, socket, subprocess, sys, tempfile, time, urllib.request
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
CAPTURI = ROOT / "teste" / "ui_start"


def _corp(fn):
    i = HTML.index(fn); return HTML[i:HTML.index("\n}\n", i)]


# --------------------------------------------------------------------------- structura
@pytest.mark.parametrize("fn", ["acasaArata", "acasaInchide", "acasaNav", "acasaRender", "acasaCartus", "secNou", "secProiecte", "secRecente",
                                "secExemple", "secCatalog", "secSetari", "secCont", "acasaSablon", "acasaDescrie", "cloudInit", "cloudSave",
                                "cloudImport", "salveazaExplicit", "confLipsa", "confObligUpd", "lucruStart", "neinteles", "miniFa", "schemaProvizorie"])
def test_functii(fn):
    assert re.search(r"(async\s+)?function " + fn + r"\(", HTML), fn


def test_meniul_si_sectiunile():
    for t in ("'Planșă nouă'", "'Proiectele mele'", "'Recente'", "'Exemple și șabloane'", "'Catalog echipamente'", "'Setări'", "'Cont'"):
        assert t in HTML, t
    for k in ("locuinta", "bmpm", "bmptd", "bmpt", "tg", "cef", "prosumator", "pt", "ge"):      # toate tipurile de lucrare
        assert re.search(r"\['" + k + r"', '", HTML), k
    assert 'id="home-btn"' in HTML and "acasaArata()" in HTML                                 # din editor înapoi la start
    assert 'aria-controls="h-nav"' in HTML and "aria-current" in HTML                          # sertar pe mobil, pagina curentă
    assert "body.home>header,body.home>main{display:none" in HTML


def test_bug_a_structura():
    # orice interpretare care a recunoscut tipul lucrării deschide panoul (și la refuz pentru date lipsă)
    for fn in ("async function wizChat(", "async function chatGo(", "async function acasaDescrie("):
        c = _corp(fn)
        assert "intelesCeva(it)" in c and "confDeschide(" in c and "lucruStart(" in c, fn
        assert "it.actiune === 'refuza' ||" not in c, fn
    assert "const intelesCeva = it => !!(it && it.intrare_fizica && it.intrare_fizica.tip_schema)" in HTML
    c = _corp("function confBlocaj(")
    assert "confLipsa()" in c
    # mesajul de „neînțeles” e vizibil (msg err, role alert), nu text mic gri
    c = _corp("function neinteles(")
    assert "msg err" in c and "role: 'alert'" in c


def test_config_si_schema_sql():
    cfg = (ROOT / "static" / "config.js").read_text(encoding="utf-8")
    assert "SUPABASE_URL: ''" in cfg and "SUPABASE_ANON_KEY: ''" in cfg
    assert not re.search(r"eyJ[\w-]{20,}", cfg + HTML), "o cheie JWT în cod"
    assert '<script src="/static/config.js"></script>' in HTML
    assert "@supabase/supabase-js@2.45.4/dist/umd/supabase.min.js" in HTML                   # versiune fixă
    assert "service_role" not in HTML
    sql = (ROOT / "supabase" / "schema.sql").read_text(encoding="utf-8")
    for t in ("profiles", "projects", "project_versions"):
        assert f"alter table public.{t:<16} enable row level security" in sql or f"alter table public.{t} enable row level security" in sql, t
        assert f"create table if not exists public.{t}" in sql, t
    assert sql.count("auth.uid()") >= 10 and "on_auth_user_created" in sql and "set_updated_at" in sql
    assert "revoke all on public.profiles, public.projects, public.project_versions from anon" in sql
    b = (ROOT / "web" / "build.py").read_text(encoding="utf-8")
    assert "config.js" in b


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


def _pagina(browser, url, w=1440, h=900, ctx=None, init=None, cfg=None):
    c = ctx or browser.new_context(viewport={"width": w, "height": h})
    pg = c.new_page()
    pg.erori = []; pg.cereri = []
    pg.on("pageerror", lambda e: pg.erori.append(str(e)))
    pg.on("request", lambda r: pg.cereri.append(r.url))
    if init:
        pg.add_init_script(init)
    if cfg is not None:
        pg.route("**/static/config.js", lambda r: r.fulfill(body=cfg, content_type="application/javascript"))
    pg.goto(url)
    pg.wait_for_function("() => typeof INFO !== 'undefined' && Object.keys(SABLOANE).length > 0 && MODEL && Object.keys(PRESETS).length > 0", timeout=60000)
    pg.wait_for_timeout(500)
    pg.evaluate("() => { INFO.claude = false; }")
    return pg


def _captura(pg, nume):
    CAPTURI.mkdir(parents=True, exist_ok=True)
    pg.wait_for_timeout(300)
    w = pg.viewport_size["width"]
    pg.screenshot(path=str(CAPTURI / f"{nume}_{'mobil' if w < 600 else 'desktop'}.png"))


def _fara_scroll(pg):
    return pg.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth")


@pytest.mark.parametrize("vp", [pytest.param((1440, 900), id="desktop"), pytest.param((390, 844), id="mobil")])
def test_start_apare_la_deschidere(srv, browser, vp):
    pg = _pagina(browser, srv, *vp)
    assert pg.evaluate("() => document.body.classList.contains('home') && HOME.on && HOME.sec === 'nou'")
    assert pg.is_visible("#home") and not pg.is_visible("header") and not pg.is_visible("#pane")
    assert pg.get_attribute("#hn-nou", "aria-current") == "page"
    assert pg.locator(".h-tile").count() == 9 and pg.is_visible("#h-text")
    assert _fara_scroll(pg)
    _captura(pg, "start")
    if vp[0] < 600:                       # meniul e un sertar: se deschide, se navighează cu tastatura, Escape îl închide
        assert not pg.is_visible("#hn-proiecte")
        pg.click("#h-burger")
        pg.wait_for_function("() => document.body.classList.contains('h-nav-open')")
        assert pg.evaluate("() => document.activeElement.id") == "hn-nou"
        pg.wait_for_timeout(250); _captura(pg, "meniu")
        pg.keyboard.press("Escape")
        assert not pg.evaluate("() => document.body.classList.contains('h-nav-open')")
        assert pg.evaluate("() => document.activeElement.id") == "h-burger"
    for sec in ("setari", "cont", "exemple", "catalog"):
        pg.evaluate(f"() => acasaArata('{sec}')")
        assert pg.get_attribute(f"#hn-{sec}", "aria-current") == "page" and _fara_scroll(pg)
        assert "null" not in pg.inner_text("#h-main").split()
        _captura(pg, sec)
    assert "Conturile nu sunt încă activate" in pg.evaluate("() => (acasaArata('cont'), $('#h-main').innerText)")
    assert not pg.erori


def test_plansa_noua_bransament_deschide_asistentul(srv, browser):
    pg = _pagina(browser, srv)
    pg.click("#ht-bmpm")
    pg.wait_for_function("() => !document.body.classList.contains('home') && MODEL._wiz === 1", timeout=30000)
    assert pg.is_visible("#wizbar") and pg.is_visible("header")
    assert pg.evaluate("() => MODEL.calc.tip_schema") == "bransament" and pg.evaluate("() => MODEL.calc.retea") == "mono"
    # înapoi la start din editor (logo / „Acasă”), apoi din nou în editor fără să pierzi nimic
    pg.click("#home-btn")
    assert pg.evaluate("() => HOME.on") and pg.is_visible("#home")
    pg.evaluate("() => acasaInchide()")
    assert pg.evaluate("() => MODEL._wiz === 1 && !HOME.on") and not pg.erori


# fraza → (tipul așteptat, rețeaua preselectată, câmpul obligatoriu din „De lămurit” sau None, confirmarea blocată?)
FRAZE = [
    ("bransament monofazat", "bransament", "mono", "#cf-P_kW-q", True),
    ("bransament trifazat", "bransament", "tri", "#cf-P_kW-q", True),
    ("casa trifazata", "locuinta", "tri", None, False),
    ("cef 50 kw", "cef", None, "#cf-lipsa-invertoare", True),
    ("tablou", "tablou", None, "#cf-P_kW-q", True),
    ("asdf", None, None, None, None),
]


@pytest.mark.parametrize("text,tip,retea,oblig,blocat", FRAZE, ids=[f[0].replace(" ", "_") for f in FRAZE])
def test_bug_a_descriere_din_start(srv, browser, text, tip, retea, oblig, blocat):
    pg = _pagina(browser, srv)
    pg.fill("#h-text", text)
    pg.click("#h-go")
    if tip is None:                      # nimic recunoscut: rămâne pe loc, cu mesaj vizibil
        pg.wait_for_selector("#h-res .msg.err", timeout=30000)
        assert pg.evaluate("() => HOME.on") and not pg.query_selector("#conf")
        assert pg.is_visible("#h-res .msg.err") and "Nu am recunoscut" in pg.inner_text("#h-res")
        assert pg.evaluate("() => parseFloat(getComputedStyle($('#h-res .msg.err')).fontSize)") >= 12.5
        assert not pg.erori
        return
    pg.wait_for_selector("#conf", timeout=30000)
    assert not pg.evaluate("() => HOME.on") and pg.evaluate("() => CONF.src") == "wiz"
    assert pg.input_value("#cf-tip_schema") == tip
    if retea:
        assert pg.input_value("#cf-retea") == retea
    assert pg.get_attribute("#cf-ok", "aria-disabled") == ("true" if blocat else "false")
    if oblig:
        assert pg.is_visible(oblig) and pg.is_visible(".cf-oblig-li")
        assert "Obligatoriu" in pg.inner_text(".cf-intreb")
        if oblig.startswith("#cf-P_kW"):
            assert pg.get_attribute(oblig, "aria-invalid") == "true" and pg.evaluate(f"() => $('{oblig}').closest('.fld').classList.contains('cf-oblig')")
            assert pg.evaluate("() => document.activeElement.id") == oblig[1:]     # cursorul e deja în câmpul care lipsește
    if text.startswith("bransament"):
        _captura(pg, "confirmare_" + retea)
        pg.fill("#cf-P_kW-q", "7" if retea == "mono" else "20")
        assert pg.get_attribute("#cf-ok", "aria-disabled") == "false" and pg.input_value("#cf-P_kW") == pg.input_value("#cf-P_kW-q")
        assert pg.get_attribute("#cf-P_kW-q", "aria-invalid") is None
        pg.click("#cf-ok")
        # echipa 1 (flux unificat): „Confirmă și desenează” duce direct la planșă, fără pașii asistentului
        pg.wait_for_function("() => !$('#conf') && MODEL.calc && !MODEL._wiz && !wizActiv() && TAB === 'calc'", timeout=30000)
        c = pg.evaluate("() => MODEL.calc")
        assert c["tip_schema"] == "bransament" and c["retea"] == retea and c["P_kW"] in (7, 20)
    if text == "cef 50 kw":
        pg.click("#cf-lipsa-invertoare")
        pg.fill("#cf-inv-0-Pn_kW", "50")
        assert pg.get_attribute("#cf-ok", "aria-disabled") == "false"
    if text == "tablou":
        assert "rețeaua" in pg.inner_text("#cf-block") and "puterea tabloului" in pg.inner_text("#cf-block")
    assert _fara_scroll(pg) and not pg.erori


@pytest.mark.parametrize("text,retea", [("bransament trifazat", "tri"), ("bransament monofazat", "mono")])
def test_bug_a_chat_principal_si_asistent(srv, browser, text, retea):
    """Același comportament din chatul editorului (chatGo) și din asistent (wizChat)."""
    pg = _pagina(browser, srv)
    pg.evaluate("() => { acasaInchide(); WIZ_START = null; render(); $('#assist').open = true; }")
    pg.fill("#chat-text", text); pg.click("#chat-go")
    pg.wait_for_selector("#conf", timeout=30000)
    assert pg.input_value("#cf-retea") == retea and pg.get_attribute("#cf-ok", "aria-disabled") == "true"
    pg.keyboard.press("Escape"); pg.wait_for_selector("#conf", state="detached")
    pg.evaluate("() => startWizard()")
    pg.fill("#wz-text", text); pg.click("#wz-go")
    pg.wait_for_selector("#conf", timeout=30000)
    assert pg.input_value("#cf-retea") == retea and pg.is_visible("#cf-P_kW-q")
    pg.keyboard.press("Escape"); pg.wait_for_selector("#conf", state="detached")
    pg.fill("#wz-text", "asdf"); pg.click("#wz-go")
    pg.wait_for_selector("#wz-res .msg.err", timeout=30000)
    assert not pg.query_selector("#conf") and not pg.erori


def test_indicator_de_lucru(srv, browser):
    """„Interpretez…” cu spinner cât timp interpretarea durează (în browser, prima poate dura câteva secunde)."""
    pg = _pagina(browser, srv)

    pg.evaluate("""() => { const f = window.fetch; window.fetch = async (u, o) => {
      if (String(u) === '/api/chat') await new Promise(r => setTimeout(r, 3200)); return f(u, o); }; }""")
    pg.fill("#h-text", "bransament trifazat")
    pg.click("#h-go")
    pg.wait_for_selector("#h-res .lucru .spin", timeout=5000)
    assert "Interpretez" in pg.inner_text("#h-res") and pg.evaluate("() => $('#h-go').classList.contains('busy') && $('#h-go').disabled")
    pg.wait_for_function("() => /poate dura|Mai durează/.test($('#h-res').innerText)", timeout=5000)     # explică de ce durează
    pg.wait_for_selector("#conf", timeout=30000)
    assert not pg.erori


def test_proiectele_mele_local(srv, browser):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = _pagina(browser, srv, ctx=ctx)
    assert pg.evaluate("() => store.get(DOCS, []).length") == 0          # schema provizorie nu e un proiect
    pg.click("#ht-tg")
    pg.wait_for_function("() => MODEL._wiz === 1", timeout=30000)
    pg.evaluate("() => { mutate(() => { MODEL.cartus.denumire2 = 'TG Hala Nord'; MODEL.cartus.plansa = 'E07'; }); wizFinish(); saveNow(); }")
    pg.wait_for_function("() => $('#paper svg')", timeout=30000)
    pg.wait_for_function("() => MINI.has(MODEL._doc)", timeout=15000)       # miniatura planșei pentru listă
    doc = pg.evaluate("() => MODEL._doc")
    pg.evaluate("() => saveNow()")
    pg.close()
    # redeschiderea aplicației: pagina de start; „Proiectele mele” listează proiectul
    pg = _pagina(browser, srv, ctx=ctx)
    assert pg.evaluate("() => HOME.on")
    pg.click("#hn-proiecte")
    pg.wait_for_selector("#h-lista .h-item")
    assert pg.locator("#h-lista .h-item").count() == 1
    assert "E07 · TG Hala Nord" in pg.inner_text("#h-lista") and "Tablou general" in pg.inner_text("#h-lista")
    assert pg.evaluate("() => /^url\\(\"data:image\\/jpeg/.test($('#h-lista .h-mini').style.backgroundImage)")
    _captura(pg, "proiecte")
    # redenumire, duplicare, ștergere cu confirmare
    pg.click("#h-ren-b-0"); pg.fill("#h-ren-0", "Hala Nord — TG"); pg.press("#h-ren-0", "Enter")
    pg.wait_for_function("() => /Hala Nord — TG/.test($('#h-lista').innerText)")
    pg.click("[aria-label='Duplică Hala Nord — TG']")
    pg.wait_for_function("() => $('#h-lista') && $('#h-lista').querySelectorAll('.h-item').length === 2")
    assert "Hala Nord — TG (copie)" in pg.inner_text("#h-lista")
    i = pg.evaluate("() => [...document.querySelectorAll('#h-lista .h-open')].findIndex(b => /copie/.test(b.textContent))")
    pg.click(f"#h-del-b-{i}")
    assert pg.is_visible(".h-conf") and pg.evaluate("() => document.activeElement.id") == "h-del-no"
    _captura(pg, "proiecte_sterge")
    pg.click("#h-del-ok")
    pg.wait_for_function("() => $('#h-lista') && $('#h-lista').querySelectorAll('.h-item').length === 1")
    # deschide pentru editare
    pg.click("#h-open-0")
    pg.wait_for_function("() => !HOME.on", timeout=30000)
    assert pg.evaluate("() => MODEL._doc") == doc and pg.evaluate("() => MODEL._titlu") == "Hala Nord — TG"
    assert pg.evaluate("() => $('#proj-name').textContent") == "Hala Nord — TG" and pg.is_visible("#paper")
    assert not pg.erori
    ctx.close()


# --------------------------------------------------------------------------- Supabase simulat (fără rețea)
MOCK_SB = r"""
window.__SB = { tables: { projects: [], project_versions: [], profiles: [] }, user: null, calls: [] };
window.supabase = { createClient: (url, key, opts) => {
  const S = window.__SB; S.url = url; S.key = key; S.opts = opts; const subs = [];
  const sess = () => S.user ? { user: S.user, access_token: 't' } : null;
  const emit = ev => subs.forEach(f => f(ev, sess()));
  const cp = o => JSON.parse(JSON.stringify(o));
  const auth = {
    getSession: async () => ({ data: { session: sess() }, error: null }),
    onAuthStateChange: f => { subs.push(f); setTimeout(() => f('INITIAL_SESSION', sess()), 0); return { data: { subscription: { unsubscribe() {} } } }; },
    signInWithPassword: async ({ email, password }) => {
      if (password !== 'parola-buna') return { data: {}, error: { message: 'Invalid login credentials' } };
      S.user = { id: 'u-1', email, created_at: '2026-10-01T10:00:00Z' }; emit('SIGNED_IN'); return { data: { session: sess() }, error: null }; },
    signUp: async ({ email, password, options }) => { S.signup = { email, options }; return { data: { user: { email }, session: null }, error: null }; },
    signOut: async () => { S.user = null; emit('SIGNED_OUT'); return { error: null }; },
    resetPasswordForEmail: async (email, o) => { S.reset = { email, o }; return { data: {}, error: null }; },
    updateUser: async () => ({ data: {}, error: null }),
  };
  function from(t) {
    const st = { op: 'select', filt: [], ord: null, row: null, single: false, maybe: false };
    const q = {
      select() { return q; }, order(k, o) { st.ord = [k, !!(o && o.ascending === false)]; return q; }, eq(k, v) { st.filt.push([k, v]); return q; },
      single() { st.single = true; return q; }, maybeSingle() { st.maybe = true; return q; },
      insert(r) { st.op = 'insert'; st.row = r; return q; }, upsert(r) { st.op = 'upsert'; st.row = r; return q; },
      update(v) { st.op = 'update'; st.row = v; return q; }, delete() { st.op = 'delete'; return q; },
      then(ok, no) { return Promise.resolve().then(run).then(ok, no); },
    };
    function run() {
      S.calls.push(t + ':' + st.op);
      if (!S.user) return { data: null, error: { message: 'JWT expired' } };
      const uid = S.user.id, T = S.tables[t], now = new Date(Date.now() + S.calls.length).toISOString();
      const own = r => (t === 'profiles' ? r.id === uid : r.owner === uid);          // RLS: doar rândurile proprii
      const match = r => own(r) && st.filt.every(([k, v]) => r[k] === v);
      const rls = { data: null, error: { message: 'new row violates row-level security policy for table "' + t + '"', code: '42501' } };
      if (st.op === 'select') {
        let d = T.filter(match).map(cp);
        if (st.ord) d.sort((a, b) => (a[st.ord[0]] < b[st.ord[0]] ? -1 : 1) * (st.ord[1] ? -1 : 1));
        if (st.single || st.maybe) return d.length || st.maybe ? { data: d[0] || null, error: null } : { data: null, error: { message: 'no rows' } };
        return { data: d, error: null };
      }
      if (st.op === 'insert' || st.op === 'upsert') {
        const r = cp(st.row);
        if (t === 'project_versions') {
          if (!S.tables.projects.some(p => p.id === r.project_id && p.owner === uid)) return rls;
          T.push(Object.assign(r, { id: T.length + 1, owner: uid, created_at: now })); return { data: null, error: null };
        }
        const ex = T.find(x => x.id === r.id);
        if (ex) { if (st.op === 'insert') return { data: null, error: { message: 'duplicate key', code: '23505' } }; if (!own(ex)) return rls;
          Object.assign(ex, r, { updated_at: now }); return { data: null, error: null }; }
        if (t === 'profiles' && r.id !== uid) return rls;
        if (t !== 'profiles') r.owner = uid;
        T.push(Object.assign(r, { created_at: now, updated_at: now })); return { data: null, error: null };
      }
      if (st.op === 'update') { T.filter(match).forEach(r => Object.assign(r, cp(st.row), { updated_at: now })); return { data: null, error: null }; }
      if (st.op === 'delete') { S.tables[t] = T.filter(r => !match(r));
        if (t === 'projects') S.tables.project_versions = S.tables.project_versions.filter(v => S.tables.projects.some(p => p.id === v.project_id));
        return { data: null, error: null }; }
    }
    return q;
  }
  return { auth, from };
} };
"""
CFG_PLIN = "window.SM_CONFIG = { SUPABASE_URL: 'https://proiect-test.supabase.co', SUPABASE_ANON_KEY: 'anon-public-test' };"


def test_supabase_simulat_salvare_listare_import(srv, browser):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = _pagina(browser, srv, ctx=ctx, init=MOCK_SB, cfg=CFG_PLIN)
    # un proiect local existent înainte de logare → importul e oferit după intrarea în cont
    pg.click("#ht-bmptd"); pg.wait_for_function("() => MODEL._wiz === 1", timeout=30000)
    pg.evaluate("() => { mutate(() => { MODEL.cartus.plansa = ''; MODEL.cartus.denumire2 = 'Branșament Ferma Vest'; }); saveNow(); }")
    local_doc = pg.evaluate("() => MODEL._doc")
    pg.evaluate("() => acasaArata('cont')")
    pg.wait_for_selector("#ha-e")
    assert pg.evaluate("() => __SB.url") == "https://proiect-test.supabase.co" and pg.evaluate("() => __SB.opts.auth.persistSession") is True
    _captura(pg, "cont_intrare")
    pg.fill("#ha-e", "ion@firma.ro"); pg.fill("#ha-p", "gresita"); pg.click("#ha-go")
    pg.wait_for_selector("#h-cont-msg.msg.err")
    assert "Email sau parolă greșită" in pg.inner_text("#h-cont-msg")
    pg.fill("#ha-e", "ion@firma.ro"); pg.fill("#ha-p", "parola-buna"); pg.click("#ha-go")
    pg.wait_for_function("() => cloudOk() && CLOUD.neimp === 1", timeout=10000)
    assert "ion@firma.ro" in pg.inner_text("#h-main") and pg.is_visible("text=Importă în cont")
    _captura(pg, "cont_conectat")
    pg.click(".h-card-f >> text=Importă în cont")
    pg.wait_for_function("() => __SB.tables.projects.length === 1 && CLOUD.neimp === 0", timeout=10000)
    p0 = pg.evaluate("() => __SB.tables.projects[0]")
    assert p0["owner"] == "u-1" and p0["titlu"] == "Branșament Ferma Vest" and p0["model"]["_doc"] == local_doc and p0["tip_schema"] == "bransament"
    assert pg.evaluate("() => MODEL._cid") == p0["id"]
    # salvarea automată (debounce) după o modificare + „Salvează” explicit cu versiune în istoric
    pg.evaluate("() => acasaInchide()")
    pg.evaluate("() => mutate(() => { MODEL.cartus.beneficiar = 'SC Ferma Vest SRL'; })")
    pg.wait_for_function("() => __SB.tables.projects[0].model.cartus.beneficiar === 'SC Ferma Vest SRL'", timeout=10000)
    assert "salvat în cont" in pg.inner_text("#proj-save")
    nver = pg.evaluate("() => __SB.tables.project_versions.length")
    pg.click("#save-btn")
    pg.wait_for_function(f"() => __SB.tables.project_versions.length === {nver + 1}", timeout=10000)
    assert pg.evaluate("() => __SB.tables.project_versions.at(-1).project_id") == p0["id"]
    # un proiect nou, salvat în cont; lista din „Proiectele mele” vine din cont
    pg.evaluate("() => acasaArata('nou')"); pg.click("#ht-pt")
    pg.wait_for_function("() => !HOME.on && MODEL._wiz === 1 && MODEL.calc.tip_schema === 'pt'", timeout=30000)
    pg.evaluate("() => mutate(() => { MODEL.cartus.plansa = ''; MODEL.cartus.denumire2 = 'PT 630 kVA Hala'; })")
    pg.wait_for_function("() => __SB.tables.projects.length === 2 && __SB.tables.projects.some(p => p.titlu === 'PT 630 kVA Hala')", timeout=10000)
    pg.evaluate("() => acasaArata('proiecte')")
    pg.wait_for_selector("#h-lista .h-item")
    assert pg.locator("#h-lista .h-item").count() == 2 and "În contul ion@firma.ro" in pg.inner_text("#h-main")
    assert pg.inner_text("#h-lista .h-open >> nth=0") == "PT 630 kVA Hala"           # ordonate după ultima modificare
    _captura(pg, "proiecte_cont")
    # redenumire în cont, ștergere din cont (cu istoricul)
    pg.click("#h-ren-b-1"); pg.fill("#h-ren-1", "Ferma Vest — branșament"); pg.press("#h-ren-1", "Enter")
    pg.wait_for_function("() => __SB.tables.projects.some(p => p.titlu === 'Ferma Vest — branșament')")
    pg.wait_for_function("() => $('#h-lista') && /Ferma Vest — branșament/.test($('#h-lista').innerText)")
    i = pg.evaluate("() => [...document.querySelectorAll('#h-lista .h-open')].findIndex(b => /Ferma Vest/.test(b.textContent))")
    pg.click(f"#h-del-b-{i}"); pg.click("#h-del-ok")
    pg.wait_for_function("() => __SB.tables.projects.length === 1 && __SB.tables.project_versions.every(v => v.project_id === __SB.tables.projects[0].id)")
    # redeschiderea din cont
    pg.wait_for_selector("#h-open-0"); pg.evaluate("() => schemaProvizorie()")
    pg.click("#h-open-0"); pg.wait_for_function("() => !HOME.on", timeout=30000)
    assert pg.evaluate("() => MODEL._titlu") == "PT 630 kVA Hala" and pg.evaluate("() => MODEL._cid") == pg.evaluate("() => __SB.tables.projects[0].id")
    # nicio cerere în rețea către Supabase sau CDN (clientul e simulat)
    assert not [u for u in pg.cereri if "supabase" in u or "jsdelivr" in u], pg.cereri
    # ieșirea din cont: proiectele rămân în browser
    pg.evaluate("() => acasaArata('cont')"); pg.click("#h-logout")
    pg.wait_for_function("() => !cloudOk()")
    assert "Intră în cont" in pg.inner_text("#h-main") and not pg.erori
    ctx.close()


def test_supabase_simulat_cont_nou_si_parola(srv, browser):
    pg = _pagina(browser, srv, init=MOCK_SB, cfg=CFG_PLIN)
    pg.evaluate("() => acasaArata('cont')"); pg.wait_for_selector("#hc-nou")
    pg.click("#hc-nou"); pg.fill("#ha-n", "Ion Pop"); pg.fill("#ha-e", "ion@firma.ro"); pg.fill("#ha-p", "parola-noua-1"); pg.click("#ha-go")
    pg.wait_for_function("() => __SB.signup")
    s = pg.evaluate("() => __SB.signup")
    assert s["email"] == "ion@firma.ro" and s["options"]["data"]["nume"] == "Ion Pop" and s["options"]["emailRedirectTo"].startswith("http://127.0.0.1")
    assert "email de confirmare" in pg.inner_text("#h-cont-msg")
    pg.click("#hc-parola"); pg.fill("#ha-e", "ion@firma.ro"); pg.click("#ha-go")
    pg.wait_for_function("() => __SB.reset")
    assert "link de resetare" in pg.inner_text("#h-cont-msg") and not pg.erori


# --------------------------------------------------------------------------- versiunea web (Pyodide), opțional
@pytest.mark.skipif(not os.environ.get("SM_WEB_VENDOR"), reason="SM_WEB_VENDOR nu e setat (Pyodide + roți)")
def test_web_static_start_si_descriere(browser, tmp_path):
    dest = tmp_path / "web"
    r = subprocess.run([sys.executable, str(ROOT / "web" / "build.py"), str(dest), os.environ["SM_WEB_VENDOR"], "--pagina"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert (dest / "config.js").exists() and 'src="config.js"' in (dest / "index.html").read_text(encoding="utf-8")
    port = _port()
    pr = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"], cwd=dest, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(0.5)
        pg = browser.new_page(viewport={"width": 1440, "height": 900}); erori = []
        pg.on("pageerror", lambda e: erori.append(str(e)))
        pg.goto(f"http://127.0.0.1:{port}/index.html")
        assert pg.evaluate("() => HOME.on")                       # pagina de start apare și cât pornește motorul
        pg.wait_for_selector("#sm-boot", state="hidden", timeout=180000)
        pg.wait_for_function("() => typeof INFO !== 'undefined' && Object.keys(SABLOANE).length > 0", timeout=60000)
        pg.evaluate("() => { INFO.claude = false; }")
        pg.fill("#h-text", "bransament trifazat"); pg.click("#h-go")
        pg.wait_for_selector("#conf", timeout=60000)
        assert pg.input_value("#cf-retea") == "tri" and pg.is_visible("#cf-P_kW-q")
        pg.fill("#cf-P_kW-q", "20"); pg.click("#cf-ok")
        pg.wait_for_function("() => !$('#conf') && MODEL.calc && MODEL.calc.P_kW === 20", timeout=60000)
        pg.evaluate("() => acasaArata('proiecte')"); pg.wait_for_selector("#h-lista .h-item", timeout=10000)
        assert "Conturile nu sunt încă activate" in pg.evaluate("() => (acasaArata('cont'), $('#h-main').innerText)")
        assert not erori
    finally:
        pr.terminate()
