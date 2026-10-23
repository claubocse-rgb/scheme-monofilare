"""Server local pentru generatorul de scheme monofilare.
Pornire:  python3 app.py   →  http://localhost:8765
Fără dependențe externe în afară de ezdxf (DXF) și Google Chrome (PDF)."""
import json, sys, pathlib, subprocess, tempfile, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))
from engine import presets, layout, render_svg, render_dxf, symbols, bom, interpretor, constructor, validare, memoriu, deviz
from engine.calc import dimensioneaza_ramura_simpla

def _find_chrome():
    """Chrome / Chromium pentru exportul PDF — macOS, Windows, Linux sau variabila CHROME."""
    import os, shutil, glob
    cand = [os.environ.get("CHROME", ""),
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]
    cand += [shutil.which(n) or "" for n in ("google-chrome", "chromium", "chromium-browser", "chrome")]
    cand += sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
    for c in cand:
        if c and os.path.exists(c): return c
    return None

CHROME = _find_chrome()
PORT = 8765


def to_svg(model):
    c = layout.build(model)
    return render_svg.render(c, model.get("cartus", {}).get("denumire2", "Schema")), c


def to_pdf(model) -> bytes:
    svg, c = to_svg(model)
    if not CHROME:
        raise RuntimeError("Exportul PDF are nevoie de Google Chrome / Chromium / Edge instalat (sau variabila CHROME).")
    with tempfile.TemporaryDirectory() as td:
        html = pathlib.Path(td) / "p.html"; pdf = pathlib.Path(td) / "p.pdf"
        html.write_text(f'<!doctype html><html><head><meta charset="utf-8"><style>@page{{size:{c.w}mm {c.h}mm;margin:0}}'
                        f'html,body{{margin:0}}svg{{display:block}}</style></head><body>{svg}</body></html>', encoding="utf-8")
        import os
        args = [CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf}", f"file://{html}"]
        if hasattr(os, "geteuid") and os.geteuid() == 0: args.insert(1, "--no-sandbox")
        r = subprocess.run(args, capture_output=True, timeout=90)
        if not pdf.exists() or pdf.stat().st_size == 0:
            raise RuntimeError("Chrome nu a reușit să genereze PDF-ul. Încearcă din nou sau exportă SVG / DXF.")
        return pdf.read_bytes()


def html_to_pdf(html_text, page_css="") -> bytes:
    if not CHROME:
        raise RuntimeError("Exportul PDF are nevoie de Google Chrome / Chromium / Edge instalat (sau variabila CHROME).")
    import os
    with tempfile.TemporaryDirectory() as td:
        h = pathlib.Path(td) / "m.html"; pdf = pathlib.Path(td) / "m.pdf"
        h.write_text(html_text, encoding="utf-8")
        args = [CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf}", f"file://{h}"]
        if hasattr(os, "geteuid") and os.geteuid() == 0: args.insert(1, "--no-sandbox")
        subprocess.run(args, capture_output=True, timeout=90)
        if not pdf.exists() or pdf.stat().st_size == 0:
            raise RuntimeError("Chrome nu a reușit să genereze PDF-ul.")
        return pdf.read_bytes()


# Șabloane de pornire = intrări fizice (SPEC §B.1); schema se generează și se dimensionează din ele
SABLOANE = {
    "locuinta": ("Casă / apartament — tabloul locuinței", "coloana de la branșament, tabloul casei cu diferențiale și circuitele uzuale",
                 {"tip_schema": "locuinta", "schema_pamant": "TN-C-S",      # rețeaua și datele din ATR le completează proiectantul
                  "alimentare": {"tip": "bransament_existent"},
                  "circuite": [{"nume": n, "receptor": r} for n, r in (
                      ("Iluminat interior", "iluminat"), ("Iluminat exterior", "iluminat"), ("Prize camere", "prize"), ("Prize living", "prize"),
                      ("Prize bucătărie", "prize_bucatarie"), ("Plită", "plita"), ("Cuptor", "cuptor"), ("Prize baie", "prize_baie"),
                      ("Mașină de spălat rufe", "masina_spalat_rufe"), ("Mașină de spălat vase", "masina_spalat_vase"), ("Boiler", "boiler"), ("Centrală termică", "centrala_termica"), ("Prize exterior", "prize_exterior"))]}),
    "bmpt": ("Branșament trifazat BMPTi-250 (150 kW)", "măsură semidirectă cu TC, 100–250 A",
             {"tip_schema": "bransament", "retea": "tri", "P_kW": 150, "L_coloana_m": 50}),
    "bmptd": ("Branșament trifazat BMPTd (50 kW)", "măsură directă, până la 100 A",
              {"tip_schema": "bransament", "retea": "tri", "P_kW": 50, "L_coloana_m": 30}),
    "bmpm": ("Branșament monofazat BMPM (7 kW)", "măsură directă, până la 40 A",
             {"tip_schema": "bransament", "retea": "mono", "P_kW": 7, "L_coloana_m": 20}),
    "tg": ("Tablou general JT cu plecări", "bilanț de puteri, plecări, cascadă",
           {"tip_schema": "tablou", "P_kW": 120, "L_alimentare_m": 40,
            "plecari": [{"nume": "TD-1", "copii": [{"nume": "Hală", "In_A": 32}, {"nume": "Birouri", "In_A": 16}]},
                        {"nume": "TD-2", "In_A": 63}, {"nume": "Pompe", "P_kW": 30}]}),
    "cef": ("CEF fotovoltaic + BESS (racord JT)", "invertoare, BESS, protecție de interfață",
            {"tip_schema": "cef", "kWp": 120, "invertoare": [{"n": 1, "Pn_kW": 100}], "bess": {"P_kW": 50, "kWh": 100}}),
    "pt": ("Post de transformare 20/0,4 kV (630 kVA)", "celule MT, transformator, TGJT, plecări",
           {"tip_schema": "pt", "Sn_kVA": 630, "plecari": [{"nume": "TD-1", "In_A": 250}, {"nume": "TD-2", "In_A": 160}, {"nume": "TD-3", "In_A": 100}]}),
    "prosumator": ("Prosumator trifazat (10 kW)", "invertor pe branșament existent",
                   {"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 10, "In_Q_bransament_A": 25}),
    "ge": ("Grup electrogen + ATS", "sursă de rezervă cu comutare automată",
           {"tip_schema": "ge_ats", "Sn_GE_kVA": 100, "P_sarcina_kW": 60}),
}


def to_dxf(model) -> bytes:
    _, c = to_svg(model)
    with tempfile.TemporaryDirectory() as td:
        f = pathlib.Path(td) / "s.dxf"
        render_dxf.render(c, str(f))
        return f.read_bytes()


PROFILE = deviz.DATE / "profile.json"


def citeste_profile():
    try:
        d = json.loads(PROFILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    return {"profile": d.get("profile") or [], "activ": d.get("activ")}


def scrie_profile(d):
    PROFILE.parent.mkdir(exist_ok=True)
    prof = [x for x in (d.get("profile") or []) if isinstance(x, dict) and x.get("nume")]
    activ = d.get("activ") if any(x["nume"] == d.get("activ") for x in prof) else None
    out = {"profile": prof, "activ": activ}
    PROFILE.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def _deviz(model_original, m):
    _, poz = layout.build_cu_pozitii(m)
    dv = model_original.get("deviz") or {}
    return deviz.calculeaza(poz, setari=dv.get("setari"), suprascrieri=dv.get("suprascrieri"), extra=dv.get("extra"))


def pachet_zip(model_original, m, r, name):
    """pachetul de predare: planșa (DXF, PDF, SVG), memoriul, lista, devizul și proiectul (JSON)"""
    import zipfile, io as _io
    bio = _io.BytesIO(); fis = []
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        def add(fn, data, ce):
            z.writestr(fn, data); fis.append((fn, ce))
        add(name + ".dxf", to_dxf(m), "planșa, AutoCAD (DXF R2018, blocuri cu atribute)")
        svg, _ = to_svg(m); add(name + ".svg", svg, "planșa, vectorial")
        try:
            add(name + ".pdf", to_pdf(m), "planșa, PDF")
        except RuntimeError as e:
            fis.append(("(PDF lipsă)", str(e)))
        if r is not None:
            h = memoriu.genereaza_html(m, r)
            try:
                add(name + "_memoriu_de_calcul.pdf", html_to_pdf(h), "memoriul de calcul")
            except RuntimeError:
                add(name + "_memoriu_de_calcul.html", h, "memoriul de calcul (HTML)")
        _, poz = layout.build_cu_pozitii(m)
        add(name + "_lista_echipamente.xlsx", bom.bom_xlsx(m, poz), "lista de echipamente și materiale")
        dv = _deviz(model_original, m)
        add(name + "_deviz_estimativ.xlsx", deviz.deviz_xlsx(m, dv), "deviz estimativ (prețuri din catalog)")
        add(name + "_proiect.json", json.dumps(validare._fara_interne(model_original), ensure_ascii=False, indent=2),
            "proiectul — se redeschide în aplicație (Deschide)")
        k = m.get("cartus") or {}
        txt = [f"Pachet de predare — {k.get('denumire2', '')}", f"Beneficiar: {k.get('beneficiar', '')}",
               f"Planșa {k.get('plansa', '')} rev. {k.get('rev', '')} · faza {k.get('faza', '')}", ""]
        txt += [f"- {fn}: {ce}" for fn, ce in fis]
        if r is not None:
            ver = r.get("verificari") or []
            av = [v for v in ver if v.get("nivel") == "AVERTISMENT" and not v.get("confirmat")]
            ok = [v for v in ver if v.get("nivel") == "AVERTISMENT" and v.get("confirmat")]
            txt += ["", "STAREA VERIFICĂRILOR", "- erori blocante: 0 (altfel pachetul nu se generează)",
                    f"- atenționări de verificat: {len(av)}" + (": " + "; ".join(f"{v['cod']} {v['obiect']}" for v in av[:12]) if av else ""),
                    f"- atenționări analizate și acceptate de proiectant: {len(ok)}"]
            pres = r.get("presupus") or []
            if pres:
                txt += ["", "VALORI PRESUPUSE — DE CONFIRMAT CU ATR-UL / MĂSURĂTORI"] + [f"- {x}" for x in pres]
        rc = dv["recapitulatie"]
        txt += ["", "DEVIZ", f"- total cu TVA: {rc['total']:,.2f} {dv['setari'].get('moneda', 'lei')}".replace(",", " ").replace(".", ",")]
        if rc["fara_pret"]:
            txt += [f"- ATENȚIE: {rc['fara_pret']} articole nu au preț în catalog — totalul e incomplet."]
        if rc.get("fara_ore"):
            txt += [f"- {rc['fara_ore']} articole nu au ore de manoperă."]
        miss = [n for kk, n in (("proiectant", "firma de proiectare"), ("beneficiar", "beneficiar"), ("nr_pr", "nr. proiect"), ("data", "data")) if not k.get(kk)]
        if miss:
            txt += ["", "CARTUȘ INCOMPLET: " + ", ".join(miss)]
        z.writestr("CITESTE.txt", "\n".join(txt))
    return bio.getvalue()


def _fara_uid(o):
    """scoate cheile interne ale interfeței (_uid etc.) înainte de export"""
    if isinstance(o, dict): return {k: _fara_uid(v) for k, v in o.items() if not k.startswith("_")}
    if isinstance(o, list): return [_fara_uid(v) for v in o]
    return o


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8", fname=None, extra=None):
        if isinstance(body, str): body = body.encode("utf-8")
        self.send_response(code)
        for k, v in (extra or {}).items(): self.send_header(k, str(v))
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        if fname: self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{urllib.parse.quote(fname)}")
        self.end_headers(); self.wfile.write(body)

    def _json(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if p in ("/", "/index.html"):
            return self._send(200, (ROOT / "static" / "index.html").read_bytes(), "text/html; charset=utf-8")
        if p == "/api/presets":       # compatibilitate: modelele vechi desenate manual
            return self._send(200, json.dumps({k: {"nume": v[0], "model": v[1]} for k, v in presets.PRESETS.items()}, ensure_ascii=False))
        if p == "/api/sabloane":
            return self._send(200, json.dumps({k: {"nume": v[0], "descriere": v[1], "calc": v[2]} for k, v in SABLOANE.items()}, ensure_ascii=False))
        if p == "/api/info":
            try:
                import anthropic, os  # noqa
                claude = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.path.exists(os.path.expanduser("~/.config/anthropic")))
            except ImportError:
                claude = False
            return self._send(200, json.dumps({"claude": claude, "pdf": bool(CHROME)}))
        if p == "/api/preturi":
            return self._send(200, json.dumps(deviz.citeste_catalog(), ensure_ascii=False))
        if p == "/api/profile":
            return self._send(200, json.dumps(citeste_profile(), ensure_ascii=False))
        if p == "/api/symbols":
            return self._send(200, json.dumps([{"cheie": k, "nume": v[1], "categorie": v[2]} for k, v in symbols.SYMBOLS.items()], ensure_ascii=False))
        if p.startswith("/static/"):
            f = ROOT / p.lstrip("/")
            if f.exists() and f.resolve().is_relative_to((ROOT / "static").resolve()):
                ct = {".css": "text/css", ".js": "application/javascript", ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2"}.get(f.suffix, "application/octet-stream")
                return self._send(200, f.read_bytes(), ct)
        self._send(404, "not found", "text/plain")

    def _blocat(self, v):
        return self._send(409, json.dumps({"eroare": "Exportul este blocat: schema are verificări neîndeplinite.",
                                           "verificari": [x for x in v["verificari"] if x.get("nivel") == "BLOCANT"]}, ensure_ascii=False))

    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        if p == "/api/preturi/import":       # corp = fișierul Excel (binar)
            try:
                n = int(self.headers.get("Content-Length", 0))
                nou = deviz.importa_xlsx(self.rfile.read(n))
                d = deviz.scrie_catalog(nou)
                return self._send(200, json.dumps({"importate": len(nou["articole"]), "total": len(d["articole"]),
                                                   "sarite": nou.get("sarite", [])}, ensure_ascii=False))
            except ValueError as e:
                return self._send(400, json.dumps({"eroare": str(e)[:1].upper() + str(e)[1:] + "."}, ensure_ascii=False))
            except Exception:
                return self._send(400, json.dumps({"eroare": "Fișierul nu e un Excel .xlsx valid. Salvează lista de prețuri ca .xlsx "
                                                   "(nu .xls / .csv / .pdf) și încearcă din nou."}, ensure_ascii=False))
        try:
            try:
                model = self._json()
            except (ValueError, UnicodeDecodeError):
                return self._send(400, json.dumps({"eroare": "Corpul cererii nu e JSON valid."}, ensure_ascii=False))
            if not isinstance(model, dict):
                return self._send(400, json.dumps({"eroare": "Corpul cererii trebuie să fie un obiect JSON."}, ensure_ascii=False))
            for k in ("calc", "model", "cartus"):
                if model.get(k) is not None and not isinstance(model.get(k), dict):
                    return self._send(400, json.dumps({"eroare": f"„{k}” trebuie să fie un obiect JSON."}, ensure_ascii=False))
            for d in (model, model.get("model") if isinstance(model.get("model"), dict) else None):
                if d and isinstance(d.get("cartus"), dict):        # cartușul e text: numere / null → șiruri
                    d["cartus"] = {k: ("" if v is None else v if isinstance(v, str) else str(v)) for k, v in d["cartus"].items()}
            name = ((model.get("cartus") or {}).get("plansa", "E01") + "_" + ((model.get("cartus") or {}).get("denumire2") or "Schema monofilara"))[:80]
            if p == "/api/preview":
                m, _ = validare.pregateste(model)
                svg, _ = to_svg(m); return self._send(200, svg, "image/svg+xml; charset=utf-8")
            if p == "/api/valideaza":
                v = validare.valideaza(model)
                return self._send(200, json.dumps(v, ensure_ascii=False, default=str))
            if p == "/api/genereaza":
                # body: {calc: intrare fizică, model: modelul curent (pentru cartuș / setări)}
                m, r = constructor.genereaza(model.get("calc") or {}, pastreaza=model.get("model"))
                if (model.get("model") or {}).get("note_manuale"):
                    m["note_manuale"] = model["model"]["note_manuale"]
                v = validare.valideaza(m)
                return self._send(200, json.dumps({"model": m, "validare": v}, ensure_ascii=False, default=str))
            if p == "/api/preturi":
                try:
                    return self._send(200, json.dumps(deviz.scrie_catalog(model), ensure_ascii=False))
                except ValueError as e:
                    return self._send(400, json.dumps({"eroare": str(e)}, ensure_ascii=False))
            if p == "/api/profile":
                return self._send(200, json.dumps(scrie_profile(model), ensure_ascii=False))
            if p == "/api/deviz":            # previzualizarea devizului (și pentru schemele blocate, marcat)
                m, r = validare.pregateste(model)
                try:
                    out = _deviz(model, m)
                except ValueError as e:
                    return self._send(400, json.dumps({"eroare": str(e)}, ensure_ascii=False))
                out["blocat"] = validare.valideaza(model)["blocheaza"]
                return self._send(200, json.dumps(out, ensure_ascii=False, default=str))
            if p == "/api/export/json":
                return self._send(200, json.dumps(validare._fara_interne(model), ensure_ascii=False, indent=2), "application/json; charset=utf-8", name + ".json")
            if p.startswith("/api/export/"):
                v = validare.valideaza(model)
                if v["blocheaza"]:
                    return self._blocat(v)
                m, r = validare.pregateste(model, pentru_export=True)
                if p == "/api/export/svg":
                    svg, _ = to_svg(m); return self._send(200, svg, "image/svg+xml; charset=utf-8", name + ".svg")
                if p == "/api/export/dxf":
                    return self._send(200, to_dxf(m), "application/dxf", name + ".dxf")
                if p == "/api/export/pdf":
                    return self._send(200, to_pdf(m), "application/pdf", name + ".pdf")
                if p == "/api/export/xlsx":
                    _, poz = layout.build_cu_pozitii(m)
                    return self._send(200, bom.bom_xlsx(m, poz), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", name + "_BOM.xlsx")
                if p in ("/api/export/deviz", "/api/export/pachet"):
                    try:
                        dvz = _deviz(model, m)
                        hdr = {"X-Deviz-Fara-Pret": dvz["recapitulatie"]["fara_pret"], "Access-Control-Expose-Headers": "X-Deviz-Fara-Pret"}
                    except ValueError as e:
                        return self._send(400, json.dumps({"eroare": "Devizul are date greșite: " + str(e)}, ensure_ascii=False))
                if p == "/api/export/deviz":
                    return self._send(200, deviz.deviz_xlsx(m, dvz),
                                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", name + "_deviz.xlsx", extra=hdr)
                if p == "/api/export/pachet":
                    return self._send(200, pachet_zip(model, m, r, name), "application/zip", name + "_pachet.zip", extra=hdr)
                if p == "/api/export/memoriu":
                    if r is None:
                        return self._send(400, json.dumps({"eroare": "Memoriul de calcul există doar pentru schemele generate din calcul."}, ensure_ascii=False))
                    h = memoriu.genereaza_html(m, r)
                    try:
                        return self._send(200, html_to_pdf(h), "application/pdf", name + "_memoriu.pdf")
                    except RuntimeError:
                        return self._send(200, h, "text/html; charset=utf-8", name + "_memoriu.html")
            if p == "/api/memoriu":       # memoriul se poate vedea oricând, inclusiv cu verificări blocante
                m, r = validare.pregateste(model)
                if r is None:
                    return self._send(400, json.dumps({"eroare": "Memoriul de calcul există doar pentru schemele generate din calcul."}, ensure_ascii=False))
                return self._send(200, memoriu.genereaza_html(m, r), "text/html; charset=utf-8")
            if p == "/api/dimensionare":
                r = dimensioneaza_ramura_simpla(model)
                return self._send(200, json.dumps(r, ensure_ascii=False, default=str))
            if p == "/api/chat":
                it = interpretor.interpreteaza(model.get("text", ""), foloseste_llm=bool(model.get("claude")))
                out = {"interpretare": {k: it.get(k) for k in ("actiune", "tip_schema", "presupus", "intrebari", "refuz_cod", "refuz_motiv",
                                                               "intelegere", "avertismente", "motor", "intrare_fizica", "cartus")}}
                if it.get("actiune") != "refuza" and it.get("intrare_fizica"):
                    cart = {}
                    c = it.get("cartus") or {}
                    if c.get("beneficiar"): cart["beneficiar"] = c["beneficiar"]
                    adr = c.get("adresa")
                    if isinstance(adr, dict) and adr.get("localitate"):
                        cart["adresa"] = f"{adr['localitate']}" + (f", jud. {adr['judet']}" if adr.get("judet") else "")
                    elif isinstance(adr, str) and adr: cart["adresa"] = adr
                    for kk in ("plansa", "faza"):
                        if c.get(kk): cart[kk] = c[kk]
                    m, r = constructor.genereaza(it["intrare_fizica"], cartus=cart, pastreaza=model.get("model"))
                    v = validare.valideaza(m)
                    out.update({"model": m, "validare": v})
                return self._send(200, json.dumps(out, ensure_ascii=False, default=str))
        except (TypeError, AttributeError, KeyError, ValueError, IndexError) as e:
            import traceback; traceback.print_exc()          # formă neașteptată a datelor primite → 400, fără text Python
            return self._send(400, json.dumps({"eroare": "Datele trimise au un câmp de tip neașteptat (ex. text în loc de obiect / listă). "
                                                         f"Verifică proiectul (.json). [{type(e).__name__}]"}, ensure_ascii=False))
        except Exception as e:
            import traceback; traceback.print_exc()
            return self._send(500, json.dumps({"eroare": "Eroare internă a aplicației — " + type(e).__name__}, ensure_ascii=False))
        self._send(404, "not found", "text/plain")

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.command, self.path))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    print(f"Schema monofilară — http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
