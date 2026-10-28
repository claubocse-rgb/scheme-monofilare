"""Construiește versiunea web (o pagină + worker Pyodide) din aceleași surse ca aplicația locală.
Utilizare: python3 web/build.py DEST   — DEST primește index.html, config.js, worker.js, app_src.json, termeni.html, confidentialitate.html, fonts/, pyodide/, whl/.
Fișierele Pyodide și roțile Python se iau din web/vendor/ (vezi web/README.md)."""
import base64, json, pathlib, re, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
PAGINA = "--pagina" in sys.argv          # pagină de sine stătătoare (GitHub Pages): păstrează scheletul HTML
VENDOR = pathlib.Path(ARGS[1]) if len(ARGS) > 1 else WEB / "vendor"
DEST = pathlib.Path(ARGS[0])


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    # 1. sursele Python ale aplicației (aceleași fișiere ca local)
    src = {"app.py": (ROOT / "app.py").read_text(encoding="utf-8"), "web/web_api.py": (WEB / "web_api.py").read_text(encoding="utf-8")}
    for f in sorted((ROOT / "engine").rglob("*.py")):
        src[str(f.relative_to(ROOT))] = f.read_text(encoding="utf-8")
    (DEST / "app_src.json").write_text(json.dumps(src, ensure_ascii=False), encoding="utf-8")
    # 2. pagina: interfața locală, fără scheletul HTML (îl pune gazda), cu fonturile înglobate și puntea spre worker
    s = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    for tag in () if PAGINA else ("<!doctype html>", '<html lang="ro">', "<head>", '<meta charset="utf-8">',
                '<meta name="viewport" content="width=device-width, initial-scale=1">', "</head>", "<body>", "</body>", "</html>"):
        s = s.replace(tag, "", 1)
    def font(m):
        b = (ROOT / "static" / "fonts" / m.group(1)).read_bytes()
        return "url(data:font/woff2;base64," + base64.b64encode(b).decode() + ")"
    s = re.sub(r"url\(/static/fonts/([\w.-]+\.woff2)\)", font, s)
    boot = """
<style>
html,body{overflow:hidden}
#sm-boot{position:fixed;inset:0;z-index:2000;display:flex;align-items:center;justify-content:center;background:var(--bg,#f4f5f2);color:var(--ink,#1d2126)}
#sm-boot .bx{max-width:420px;padding:24px 28px;border-radius:14px;background:var(--surface,#fff);border:1px solid var(--rule,#ddd);box-shadow:0 10px 40px rgba(0,0,0,.12);font:15px/1.45 "Barlow",system-ui,sans-serif}
#sm-boot h2{margin:0 0 6px;font:600 20px/1.2 "Barlow Semi Condensed","Barlow",system-ui,sans-serif}
#sm-boot .bar{height:4px;border-radius:2px;margin:14px 0 8px;background:linear-gradient(90deg,var(--sig-line,#e8b100) 0 35%,transparent 35%) 0 0/300% 100%;animation:smb 1.2s linear infinite;background-color:var(--rule,#ddd)}
#sm-boot.err .bar{animation:none;background:var(--danger,#b00020)}
#sm-boot small{color:var(--ink-2,#555)}
@keyframes smb{to{background-position:-300% 0}}
@media (prefers-reduced-motion:reduce){#sm-boot .bar{animation:none}}
</style>
<div id="sm-boot" role="status" aria-live="polite"><div class="bx"><h2>Scheme monofilare</h2>
<div>Pornesc motorul de calcul direct în browser — prima deschidere durează 10–20 de secunde, apoi merge instant.</div>
<div class="bar"></div><small id="sm-boot-t">Se încarcă…</small></div></div>
"""
    # configurarea conturilor (Supabase) rămâne fișier separat lângă pagină: se completează fără o nouă construire
    s = s.replace('<script src="/static/config.js"></script>', '<script src="config.js"></script>', 1)
    shutil.copy(ROOT / "static" / "config.js", DEST / "config.js")
    shim = "<script>\n" + (WEB / "shim.js").read_text(encoding="utf-8") + "\n</script>\n"
    i = s.index("<script>")
    s = s[:i] + boot + shim + s[i:]
    (DEST / "index.html").write_text(s.strip() + "\n", encoding="utf-8")
    shutil.copy(WEB / "worker.js", DEST / "worker.js")
    # Termenii și Politica de confidențialitate (legături relative din pagină) + fonturile lor (url(fonts/…))
    for f in ("termeni.html", "confidentialitate.html"):
        if (ROOT / "static" / f).exists():
            shutil.copy(ROOT / "static" / f, DEST / f)
    shutil.copytree(ROOT / "static" / "fonts", DEST / "fonts", dirs_exist_ok=True)
    # 3. Pyodide + roți (publicate cu sufixul .wasm pentru arhive)
    for sub in ("pyodide", "whl"):
        (DEST / sub).mkdir(exist_ok=True)
        for f in (VENDOR / sub).iterdir():
            nume = f.name + (".wasm" if f.suffix in (".whl", ".zip") else "")
            shutil.copy(f, DEST / sub / nume)
    print("gata:", DEST)


if __name__ == "__main__":
    main()
