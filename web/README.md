# Versiunea web (fără server)

Aceeași aplicație, rulată integral în browser: interfața din `static/index.html` + motorul Python
(`app.py`, `engine/`) executat în **Pyodide** (CPython în WebAssembly), într-un Web Worker.

- `web_api.py` — rulează handler-ul HTTP din `app.py` fără socket (cerere → status, antete, corp).
- `worker.js` — pornește Pyodide, încarcă numpy / ezdxf / openpyxl și sursele aplicației.
- `shim.js` — înlocuiește `fetch('/api/...')` din interfață cu apeluri către worker; descărcările trec prin
  capabilitatea `downloads` a gazdei (DXF vine arhivat .zip; PDF nu e disponibil — nu există Chrome pe server).
- `build.py DEST [VENDOR]` — produce pagina publicabilă. `VENDOR` conține `pyodide/` (din
  pyodide-0.26.4.tar.bz2: pyodide.js, pyodide.asm.js/.wasm, python_stdlib.zip, pyodide-lock.json, roata numpy)
  și `whl/` (ezdxf, openpyxl, et_xmlfile, fonttools, pyparsing, typing_extensions — `pip download`).

Build-ul ascunde codul (îngreunare, nu protecție — accesul real îl restricționează Cloudflare Access):
JS/CSS minificate fără comentarii și fără sourcemaps (`web/minif.py`), motorul Python ca `app_src.zip.wasm` cu bytecode
.pyc (dacă pe mașina de build există `python3.12`, aceeași versiune ca Pyodide 0.26; altfel sursa fără comentarii),
`robots: noindex, nofollow`, `robots.txt` care blochează tot și `_headers` (Cloudflare Pages) cu `X-Robots-Tag`.
`--sursa` construiește fără minificare, pentru depanare.

Datele utilizatorului (catalog de prețuri, profile) se păstrează în browserul fiecăruia (localStorage).
