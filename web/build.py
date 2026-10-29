"""Construiește versiunea web (o pagină + worker Pyodide) din aceleași surse ca aplicația locală.
Utilizare: python3 web/build.py DEST [VENDOR] [--pagina] [--sursa]
  DEST primește index.html, config.js, worker.js, app_src.zip.wasm, termeni.html, confidentialitate.html, beta.html,
  robots.txt, _headers, fonts/, pyodide/, whl/. Fișierele Pyodide și roțile Python se iau din web/vendor/ (vezi web/README.md).
E2 (găzduire Cloudflare, acces restricționat): codul nu se mai vede ca text în pagină — JS/CSS minificate, fără comentarii
și fără sourcemaps; motorul Python vine compilat (.pyc pentru Python 3.12 = Pyodide 0.26, dacă există python3.12 pe
mașina de build; altfel sursa fără comentarii / docstring-uri), într-o arhivă zip; pagina are `robots: noindex, nofollow`,
fără titlu / descriere indexabile, iar robots.txt blochează tot. E doar o îngreunare: protecția reală e Cloudflare Access.
--sursa = fără minificare (depanare)."""
import base64, io, json, pathlib, re, shutil, subprocess, sys, zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import minif  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
PAGINA = "--pagina" in sys.argv          # pagină de sine stătătoare (GitHub Pages / Cloudflare): păstrează scheletul HTML
SURSA = "--sursa" in sys.argv            # fără minificare (depanare)
ROBOTS = '<meta name="robots" content="noindex, nofollow, noarchive">'
PY_WEB = (3, 12)                          # Python-ul din Pyodide 0.26
VENDOR = pathlib.Path(ARGS[1]) if len(ARGS) > 1 else WEB / "vendor"
DEST = pathlib.Path(ARGS[0])


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    # 1. sursele Python ale aplicației (aceleași fișiere ca local)
    src = {"app.py": (ROOT / "app.py").read_text(encoding="utf-8"), "web/web_api.py": (WEB / "web_api.py").read_text(encoding="utf-8")}
    for f in sorted((ROOT / "engine").rglob("*.py")):
        src[str(f.relative_to(ROOT))] = f.read_text(encoding="utf-8")
    (DEST / "app_src.json").unlink(missing_ok=True)
    zipb, fel = arhiva_python(src)
    (DEST / "app_src.zip.wasm").write_bytes(zipb)
    print("motorul:", fel)
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
    # fără titlu / descriere indexabile; noindex (în <head> la pagina de sine stătătoare, altfel la începutul fragmentului)
    s = re.sub(r"<title>.*?</title>\s*", "", s, flags=re.S)
    s = re.sub(r'<meta name="description"[^>]*>\s*', "", s)
    s = s.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n' + ROBOTS, 1) if PAGINA else ROBOTS + "\n" + s
    if not SURSA:
        s = minif.html(s)
    (DEST / "index.html").write_text(s.strip() + "\n", encoding="utf-8")
    w = (WEB / "worker.js").read_text(encoding="utf-8")
    (DEST / "worker.js").write_text(w if SURSA else minif.js(w), encoding="utf-8")
    # Termenii, Politica de confidențialitate, Condițiile de testare (legături relative din pagină) + fonturile lor (url(fonts/…))
    for f in ("termeni.html", "confidentialitate.html", "beta.html"):
        if (ROOT / "static" / f).exists():
            t = (ROOT / "static" / f).read_text(encoding="utf-8")
            if "noindex" not in t:
                t = re.sub(r"(<meta charset=[^>]*>)", lambda m: m.group(1) + "\n" + ROBOTS, t, count=1, flags=re.I)
            (DEST / f).write_text(t, encoding="utf-8")
    shutil.copytree(ROOT / "static" / "fonts", DEST / "fonts", dirs_exist_ok=True)
    (DEST / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    # Cloudflare Pages: antetele pentru toate fișierele (noindex și pentru PDF / JSON / wasm)
    (DEST / "_headers").write_text("/*\n  X-Robots-Tag: noindex, nofollow, noarchive\n  Referrer-Policy: no-referrer\n"
                                   "  X-Content-Type-Options: nosniff\n", encoding="utf-8")
    # 3. Pyodide + roți (publicate cu sufixul .wasm pentru arhive); fără sourcemaps
    for sub in ("pyodide", "whl"):
        (DEST / sub).mkdir(exist_ok=True)
        for f in (VENDOR / sub).iterdir():
            if f.suffix == ".map":
                continue
            nume = f.name + (".wasm" if f.suffix in (".whl", ".zip") else "")
            if f.suffix in (".js", ".mjs"):
                t = f.read_text(encoding="utf-8")
                (DEST / sub / nume).write_text(re.sub(r"\n?//# sourceMappingURL=\S+\s*$", "\n", t), encoding="utf-8")
            else:
                shutil.copy(f, DEST / sub / nume)
    print("gata:", DEST)


_COMPILEAZA = r"""
import ast, importlib._bootstrap_external as be, io, json, sys, zipfile
src = json.load(sys.stdin)
def fara_docstring(t):
    for n in ast.walk(t):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.body \
                and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant) \
                and isinstance(n.body[0].value.value, str):
            n.body = n.body[1:] or [ast.Pass()]
    return ast.fix_missing_locations(t)
pyc = "--pyc" in sys.argv
bio = io.BytesIO()
with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
    for cale, txt in sorted(src.items()):
        t = fara_docstring(ast.parse(txt, cale))
        if pyc:
            cod = compile(t, cale, "exec", dont_inherit=True, optimize=0)
            z.writestr(cale[:-3] + ".pyc", bytes(be._code_to_timestamp_pyc(cod, 0, 0)))
        else:
            z.writestr(cale, ast.unparse(t) + "\n")
sys.stdout.buffer.write(bio.getvalue())
"""


def _python_web():
    """un interpretor Python 3.12 (același bytecode ca Pyodide 0.26), dacă există pe mașina de build"""
    if sys.version_info[:2] == PY_WEB:
        return sys.executable
    for n in ("python3.12", "python312"):
        p = shutil.which(n)
        if p:
            return p
    return None


def arhiva_python(src):
    """{cale: text} → (zip, descriere). Cu Python 3.12: doar .pyc (fără text); altfel sursa fără comentarii / docstring-uri."""
    py = _python_web()
    if py:
        r = subprocess.run([py, "-I", "-c", _COMPILEAZA, "--pyc"], input=json.dumps(src).encode(), capture_output=True)
        if r.returncode == 0:
            return r.stdout, f"bytecode .pyc (Python {PY_WEB[0]}.{PY_WEB[1]}), {len(src)} module"
        print("atenție: compilarea .pyc a eșuat, rămâne sursa fără comentarii:", r.stderr.decode()[-300:], file=sys.stderr)
    r = subprocess.run([sys.executable, "-I", "-c", _COMPILEAZA], input=json.dumps(src).encode(), capture_output=True, check=True)
    return r.stdout, f"sursă fără comentarii (fără .pyc), {len(src)} module"


if __name__ == "__main__":
    main()
