"""Capturi ale panoului de confirmare după chat (desktop + mobil 390 px).
Rulare: python3 teste/r10/ui_confirmare/capturi.py   (pornește singur serverul local pe un port liber)"""
import os, pathlib, socket, subprocess, sys, tempfile, time, urllib.request
from playwright.sync_api import sync_playwright

D = pathlib.Path(__file__).resolve().parent
ROOT = D.parents[2]
s = socket.socket(); s.bind(("127.0.0.1", 0)); PORT = s.getsockname()[1]; s.close()
U = f"http://127.0.0.1:{PORT}/"
srv = subprocess.Popen([sys.executable, "app.py", str(PORT)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       env=dict(os.environ, ANTHROPIC_API_KEY="", XDG_CONFIG_HOME=tempfile.mkdtemp()))
for _ in range(100):
    try:
        urllib.request.urlopen(U + "api/info", timeout=1); break
    except Exception:
        time.sleep(0.1)


def panou(b, w, h, text, fis, dupa=None):
    pg = b.new_page(viewport={"width": w, "height": h})
    pg.goto(U); pg.wait_for_function("() => typeof INFO !== 'undefined' && Object.keys(SABLOANE).length > 0 && MODEL"); pg.wait_for_timeout(800)
    pg.evaluate("() => { INFO.claude = false; WIZ_START = null; render(); $('#assist').open = true; }")
    pg.fill("#chat-text", text); pg.press("#chat-text", "Control+Enter"); pg.wait_for_selector("#conf")
    pg.evaluate("() => { $('#assist').open = false; }")
    if dupa:
        dupa(pg)
    pg.wait_for_timeout(300); pg.screenshot(path=str(D / fis)); pg.close()


try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        panou(b, 1440, 900, "casă P+1, trifazat 15 kW, plită, pompă de căldură, încărcător mașină 11 kW, coloană 25 m", "01_desktop_casa.png",
              lambda pg: pg.evaluate("() => { document.querySelector('.cf-presl').open = true; $('#pane').scrollTop = 0; }"))
        panou(b, 1440, 900, "tablou general cu plecări: hală 16 A, birouri 10 A", "02_desktop_tg_retea_lipsa.png",
              lambda pg: pg.evaluate("() => { $('#cf-pl-h').scrollIntoView({ block: 'center' }); }"))
        panou(b, 390, 844, "CEF 300 kWp cu 3 invertoare de 100 kW și BESS 200 kWh", "03_mobil_390_cef.png",
              lambda pg: pg.evaluate("() => { $('#cf-inv-h').scrollIntoView({ block: 'center' }); }"))
        b.close()
finally:
    srv.terminate()
print("capturi în", D)
