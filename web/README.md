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

Datele utilizatorului (catalog de prețuri, profile) se păstrează în browserul fiecăruia (localStorage).
