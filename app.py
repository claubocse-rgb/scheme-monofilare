"""Server local pentru generatorul de scheme monofilare.
Pornire:  python3 app.py   →  http://localhost:8765
Fără dependențe externe în afară de ezdxf (DXF) și Google Chrome (PDF)."""
import json, re, sys, pathlib, subprocess, tempfile, urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(ROOT))
from engine import presets, layout, render_svg, render_dxf, symbols, bom, interpretor, constructor, validare, memoriu, deviz, echipamente, cheie_api
from engine import documente_tabele, documente_protectii, documente_racordare, documente_caiet, pvgis, import_circuite, galerie, documente_vederi
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
        from engine import planse as _pl
        if _pl.cere_planse(m.get("calc") or {}):
            # r12: convenția proiectantului — pachetul de planșe A3 (IE 07.x … IE 11) alături de planșa unică
            lst = _pl.planse_din_model(m)
            if lst:
                add(name + "_planse_A3.zip", _pl.pachet_planse_zip(lst, name, pdf=lambda svgs: html_to_pdf(_pl.html_multipagina(svgs))),
                    f"pachetul de {len(lst)} planșe A3 (SVG + DXF pe planșă, PDF multi-pagină): " + ", ".join(c for c, _ in lst))
        # E2: tabelul de cabluri + fișa de reglaje (Excel), caietul de sarcini, dosarul de racordare (PV)
        try:
            add(name + "_tabel_cabluri_si_reglaje.xlsx", documente_tabele.tabel_xlsx(_tabele_predare(m, r), m.get("cartus")),
                "tabelul de cabluri, fișa de reglaje a protecțiilor și curenții de scurtcircuit pe noduri (recepție / PIF)")
            cs = documente_caiet.caiet_sarcini(model_original, m, r)
            try:
                add(name + "_caiet_de_sarcini.docx", cs.docx(), "caietul de sarcini (de completat câmpurile marcate cu galben)")
            except ImportError:
                add(name + "_caiet_de_sarcini.html", cs.html(), "caietul de sarcini (HTML)")
            if (m.get("calc") or {}).get("tip_schema") in ("cef", "prosumator"):
                add(name + "_dosar_racordare.zip", documente_racordare.dosar_zip(model_original, m, r, name,
                                                                                  pdf=html_to_pdf if CHROME else None),
                    "dosarul de racordare: cerere, fișa tehnică, lista echipamentelor cu certificate, declarația instalatorului")
        except Exception as e:                       # documentele derivate nu blochează pachetul
            fis.append(("(documente E2 lipsă)", type(e).__name__))
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


def _cartus_chat(c):
    """cartușul citit din descriere (beneficiar, adresă, planșă, fază) → câmpurile cartușului planșei"""
    cart = {}
    if c.get("beneficiar"): cart["beneficiar"] = c["beneficiar"]
    adr = c.get("adresa")
    if isinstance(adr, dict) and adr.get("localitate"):
        cart["adresa"] = f"{adr['localitate']}" + (f", jud. {adr['judet']}" if adr.get("judet") else "")
    elif isinstance(adr, str) and adr: cart["adresa"] = adr
    for kk in ("plansa", "faza"):
        if c.get(kk): cart[kk] = c[kk]
    return {k: ("" if v is None else v if isinstance(v, str) else str(v)) for k, v in cart.items()}


def _genereaza_chat(intrare, cart, pastreaza):
    """aceeași generare după chat și după confirmarea intrării: intrare fizică + cartușul din text + setările modelului curent"""
    m, r = constructor.genereaza(intrare, cartus=cart, pastreaza=pastreaza if isinstance(pastreaza, dict) else None)
    return {"model": m, "validare": validare.valideaza(m)}


def _verifica_declarate(intrare):
    """r11 (panoul de confirmare): generare de probă, fără desen — ce valori declarate ar schimba motorul.
    Deocamdată: Q-ul branșamentului la locuință (alimentare.In_Q_bransament_A față de Q-ul ales)."""
    import copy
    from engine.confirmare import campuri_lipsa
    from engine.confirmare import intrebari_confirmare
    out = {"schimbari": [], "lipsa": campuri_lipsa(intrare), "intrebari": intrebari_confirmare(intrare)}
    try:
        _, r = constructor.genereaza(copy.deepcopy(intrare))
    except Exception as e:                                   # previzualizarea nu trebuie să blocheze panoul
        out["eroare"] = type(e).__name__
        return out
    rz = (r or {}).get("rezultat") or {}
    out["blocante"] = sum(1 for v in (r or {}).get("verificari") or [] if v.get("nivel") == "BLOCANT")
    # echipa 1: implicitele motorului (valorile presupuse) — panoul le marchează pe câmpurile lor, cu galben
    out["presupus"] = [str(x) for x in ((r or {}).get("presupus") or [])]
    out["avertismente"] = [v.get("mesaj", "") for v in (r or {}).get("verificari") or [] if v.get("nivel") == "AVERTISMENT"]
    if intrare.get("tip_schema") == "locuinta":
        q_d = (intrare.get("alimentare") or {}).get("In_Q_bransament_A")
        q_c = (((rz.get("alimentare") or {}).get("Q")) or {}).get("In_A")
        if q_d is not None and q_c is not None and abs(float(q_c) - float(q_d)) > 1e-6:
            ib = (rz.get("alimentare") or {}).get("Ib_A")
            out["schimbari"].append({"camp": "alimentare.In_Q_bransament_A", "declarat": q_d, "calculat": q_c,
                                     "motiv": f"Ib de calcul {ib:.1f} A".replace(".", ",") if isinstance(ib, (int, float)) else ""})
        # r11: motorul păstrează Q-ul declarat și BLOCHEAZĂ (V46) dacă e prea mic — propunerea lui (cel mai mare calibru
        # propus) se arată ca schimbare sugerată, nu aplicată
        prop = [v for v in (r or {}).get("verificari") or [] if v.get("nivel") == "BLOCANT"
                and (v.get("propunere") or {}).get("camp") == "alimentare.In_Q_bransament_A"]
        if q_d is not None and prop and not out["schimbari"]:
            v = max(prop, key=lambda x: x["propunere"]["valoare"])
            out["schimbari"].append({"camp": "alimentare.In_Q_bransament_A", "declarat": q_d,
                                     "calculat": v["propunere"]["valoare"], "motiv": v.get("mesaj", "")})
    return out


def nume_fisier(text, implicit="Schema_monofilara"):
    """numele fișierului de export: fără diacritice, liniuțe lungi sau caractere problematice pe Windows / email / WhatsApp
    („E01 · BMPTd-40 — BLOC DE MĂSURĂ” → „E01_BMPTd-40_BLOC_DE_MASURA”)"""
    import unicodedata
    t = str(text or "").translate(str.maketrans({"ș": "s", "ş": "s", "Ș": "S", "Ş": "S", "ț": "t", "ţ": "t", "Ț": "T", "Ţ": "T",
                                                  "—": "-", "–": "-", "·": "_", "×": "x", "²": "2", "³": "3"}))
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"[^A-Za-z0-9._+-]+", "_", t)
    t = re.sub(r"_*-_*", "-", t)
    t = re.sub(r"_{2,}", "_", t)
    t = re.sub(r"[_-]+\.", ".", t).strip("._-")
    m = re.search(r"\.[A-Za-z0-9]{2,5}$", t)                       # extensia rămâne întreagă la trunchiere
    ext = m.group(0) if m else ""
    stem = t[:len(t) - len(ext)][:80 - len(ext)].rstrip("._-")
    return (stem or implicit) + ext


def _fara_uid(o):
    """scoate cheile interne ale interfeței (_uid etc.) înainte de export"""
    if isinstance(o, dict): return {k: _fara_uid(v) for k, v in o.items() if not k.startswith("_")}
    if isinstance(o, list): return [_fara_uid(v) for v in o]
    return o


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def documente_json(corp, m, r, parti=None):
    """E2: vederile derivate din planșă + calcul, într-un singur răspuns (interfața afișează ce îi trebuie)"""
    inp = m.get("calc") or {}
    tip = inp.get("tip_schema")
    toate = ("tabel_cabluri", "fisa_reglaje", "carcasa", "pierderi", "spd", "grupuri_tipice", "dosar_racordare", "protectie_regim_GE",
             "limitare_PCC")
    parti = [x for x in (parti or toate) if x in toate + ("curbe",)]
    out = {}
    rz = (r or {}).get("rezultat") or {}
    y = (corp.get("pvgis") or {}).get("kWh_kWp_an") if isinstance(corp.get("pvgis"), dict) else None
    for x in parti:
        if x == "tabel_cabluri":
            out[x] = documente_tabele.tabel_cabluri(m, r)
        elif x == "fisa_reglaje":
            out[x] = documente_tabele.fisa_reglaje(m, r)
        elif x == "carcasa":
            out[x] = documente_tabele.dimensionare_carcasa(m, corp.get("rezerva_pct", 25))
        elif x == "pierderi" and tip in ("cef", "prosumator"):
            out[x] = documente_tabele.pierderi_cabluri(m, r, inp, y)
        elif x == "spd":
            out[x] = documente_protectii.evaluare_spd(dict(inp, evaluare_spd=corp.get("evaluare_spd") or inp.get("evaluare_spd")), m)
        elif x == "curbe":
            out[x] = documente_protectii.curbe_timp_curent(m, r)
        elif x == "grupuri_tipice" and tip in ("cef", "prosumator"):
            out[x] = documente_tabele.grupuri_tipice(m)
        elif x == "dosar_racordare" and tip in ("cef", "prosumator"):
            out[x] = documente_racordare.rezumat(corp, m, r)
        elif x in ("protectie_regim_GE", "limitare_PCC") and rz.get(x):
            out[x] = rz[x]
    return out


def _tabele_predare(m, r):
    t = [documente_tabele.tabel_cabluri(m, r)]
    f = documente_tabele.fisa_reglaje(m, r)
    t.append(f)
    if f.get("ik_noduri"):
        t.append({"titlu": "CURENTI DE SCURTCIRCUIT PE NODURI", "randuri": f["ik_noduri"],
                  "coloane": [("de_la", "De la"), ("nod", "Nod"), ("Ik3max_origine_kA", "Ik3max origine [kA]"),
                              ("Ik3max_capat_kA", "Ik3max capăt [kA]"), ("Ik1min_capat_A", "Ik1min capăt [A]"),
                              ("Ia_A", "Ia [A]"), ("t_deconectare_s", "t deconectare [s]")], "note": []})
    return t


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8", fname=None, extra=None):
        if isinstance(body, str): body = body.encode("utf-8")
        self.send_response(code)
        for k, v in (extra or {}).items(): self.send_header(k, str(v))
        self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        if fname: self.send_header("Content-Disposition", f"attachment; filename=\"{nume_fisier(fname)}\"; filename*=UTF-8''{urllib.parse.quote(fname)}")
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
        if p == "/api/info":       # F.9: citirea avansată (Claude) e disponibilă când există o cheie API
            return self._send(200, json.dumps({"claude": bool(cheie_api.citeste()), "claude_sursa": cheie_api.sursa(),
                                               "pdf": bool(CHROME)}))
        if p == "/api/preturi":
            return self._send(200, json.dumps(deviz.citeste_catalog(), ensure_ascii=False))
        if p == "/api/profile":
            return self._send(200, json.dumps(citeste_profile(), ensure_ascii=False))
        if p == "/api/echipamente":
            return self._send(200, json.dumps(dict(echipamente.citeste_catalog(), claude=echipamente.claude_disponibil()), ensure_ascii=False))
        if p == "/api/import/model_circuite":        # E2: modelul Excel de import al circuitelor
            return self._send(200, import_circuite.model_xlsx(), XLSX, "Model_import_circuite.xlsx")
        if p == "/api/galerie":                      # E2: galeria personală de circuite / tablouri
            return self._send(200, json.dumps(galerie.citeste(), ensure_ascii=False))
        if p == "/api/symbols":
            return self._send(200, json.dumps([{"cheie": k, "nume": v[1], "categorie": v[2]} for k, v in symbols.SYMBOLS.items()], ensure_ascii=False))
        if p.startswith("/static/"):
            f = ROOT / p.lstrip("/")
            if f.exists() and f.resolve().is_relative_to((ROOT / "static").resolve()):
                ct = {".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "application/javascript", ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2"}.get(f.suffix, "application/octet-stream")
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
        if p == "/api/import/circuite":      # E2: corp = fișierul .xlsx / .csv (binar); ?destinatie=locuinta|tablou
            try:
                n = int(self.headers.get("Content-Length", 0))
                q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                rez = import_circuite.importa(self.rfile.read(n), (q.get("destinatie") or [None])[0])
                return self._send(200, json.dumps(rez, ensure_ascii=False))
            except ValueError as e:
                return self._send(400, json.dumps({"eroare": str(e)[:1].upper() + str(e)[1:] + "."}, ensure_ascii=False))
            except Exception as e:
                return self._send(400, json.dumps({"eroare": "Fișierul nu a putut fi citit (" + type(e).__name__ + "). Folosiți "
                                                   "modelul .xlsx sau un CSV cu „;”."}, ensure_ascii=False))
        if p == "/api/echipamente/import":   # corp = fișa tehnică PDF (binar) sau textul fișei
            try:
                n = int(self.headers.get("Content-Length", 0))
                data = self.rfile.read(n)
                if not data:
                    raise ValueError("fișierul e gol")
                return self._send(200, json.dumps(echipamente.importa_fisa(data), ensure_ascii=False))
            except ValueError as e:
                return self._send(400, json.dumps({"eroare": str(e)[:1].upper() + str(e)[1:] + "."}, ensure_ascii=False))
            except Exception as e:
                import traceback; traceback.print_exc()
                return self._send(400, json.dumps({"eroare": "Fișa nu a putut fi citită (" + type(e).__name__ + "). "
                                                   "Lipește textul fișei sau completează valorile manual."}, ensure_ascii=False))
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
            name = nume_fisier(((model.get("cartus") or {}).get("plansa") or "E01") + "_" + ((model.get("cartus") or {}).get("denumire2") or "Schema monofilara"))[:60].rstrip("._-")
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
            if p == "/api/echipamente":          # {echipament: {...}} → salvează în catalog; {sterge: id} → șterge
                try:
                    return self._send(200, json.dumps(echipamente.scrie(model), ensure_ascii=False))
                except ValueError as e:
                    return self._send(400, json.dumps({"eroare": str(e)[:1].upper() + str(e)[1:] + "."}, ensure_ascii=False))
            if p == "/api/echipamente/rafineaza":     # opțional: structurarea textului fișei cu Claude
                try:
                    r = echipamente.rafineaza_claude(str(model.get("text") or ""), model.get("tip"))
                    return self._send(200, json.dumps(r, ensure_ascii=False))
                except ValueError as e:
                    return self._send(400, json.dumps({"eroare": str(e)[:1].upper() + str(e)[1:] + "."}, ensure_ascii=False))
                except Exception as e:
                    return self._send(502, json.dumps({"eroare": "Claude nu a răspuns (" + type(e).__name__ + ") — folosește propunerea locală."}, ensure_ascii=False))
            if p == "/api/deviz":            # previzualizarea devizului (și pentru schemele blocate, marcat)
                m, r = validare.pregateste(model)
                try:
                    out = _deviz(model, m)
                except ValueError as e:
                    return self._send(400, json.dumps({"eroare": str(e)}, ensure_ascii=False))
                out["blocat"] = validare.valideaza(model)["blocheaza"]
                return self._send(200, json.dumps(out, ensure_ascii=False, default=str))
            if p == "/api/documente":        # E2: tabel cabluri, reglaje + Ik, carcasă, pierderi, SPD, tipic, dosar (rezumat)
                m, r = validare.pregateste(model)
                out = documente_json(model, m, r, model.get("parti"))
                out["blocat"] = validare.valideaza(model)["blocheaza"]
                return self._send(200, json.dumps(out, ensure_ascii=False, default=str))
            if p.startswith("/api/documente/"):      # E2: previzualizarea unui document din tab-ul „Documente”
                cheie = p.rsplit("/", 1)[1]
                if cheie not in documente_vederi.CHEI_PREVIZUALIZARE:
                    return self._send(404, "not found", "text/plain")
                m, r = validare.pregateste(model)
                try:
                    ct, corp = documente_vederi.previzualizare(cheie, model, m, r)
                except documente_vederi.Indisponibil as e:
                    return self._send(400, json.dumps({"eroare": str(e)[:1].upper() + str(e)[1:] + "."}, ensure_ascii=False))
                return self._send(200, corp, ct)
            if p == "/api/curbe":            # E2: curbele timp-curent generice (date pentru desen)
                m, r = validare.pregateste(model)
                return self._send(200, json.dumps(documente_protectii.curbe_timp_curent(m, r), ensure_ascii=False, default=str))
            if p == "/api/spd":              # E2: evaluarea necesității SPD (corp: model + evaluare_spd)
                m, _ = validare.pregateste(model)
                inp = dict(m.get("calc") or model.get("calc") or {})
                if isinstance(model.get("evaluare_spd"), dict):
                    inp["evaluare_spd"] = model["evaluare_spd"]
                return self._send(200, json.dumps(documente_protectii.evaluare_spd(inp, m), ensure_ascii=False, default=str))
            if p == "/api/pvgis":            # E2: {lat, lon, kWp, unghi, azimut, pierderi, montaj, offline} → producția (cache)
                r_ = pvgis.estimeaza(model.get("lat"), model.get("lon"), model.get("kWp"), model.get("unghi", 30),
                                     model.get("azimut", 0), model.get("pierderi"), model.get("montaj", "free"),
                                     offline=bool(model.get("offline")))
                return self._send(200, json.dumps(r_, ensure_ascii=False))
            if p == "/api/pvgis/url":        # E2 (browser): adresa cererii PVcalc pe care o face JavaScript
                try:
                    return self._send(200, json.dumps({"url": pvgis.cerere_url(model.get("lat"), model.get("lon"), model.get("kWp"),
                                                                              model.get("unghi", 30), model.get("azimut", 0),
                                                                              model.get("pierderi"), model.get("montaj", "free"))}))
                except ValueError as e:
                    return self._send(400, json.dumps({"eroare": str(e)}, ensure_ascii=False))
            if p == "/api/pvgis/raspuns":    # E2: {raspuns: JSON PVGIS, kWp} sau {kWh_kWp_an, kWp} (mod offline)
                try:
                    if model.get("raspuns") is not None:
                        r_ = pvgis.din_raspuns(model["raspuns"], model.get("kWp"))
                    else:
                        r_ = pvgis.din_valoare(model.get("kWh_kWp_an"), model.get("kWp"))
                    r_["paragraf_memoriu"] = pvgis.paragraf_memoriu(r_)
                    return self._send(200, json.dumps(r_, ensure_ascii=False))
                except (ValueError, KeyError, TypeError) as e:
                    return self._send(400, json.dumps({"eroare": f"Răspuns PVGIS / valoare nevalidă: {e}"}, ensure_ascii=False))
            if p == "/api/galerie":          # E2: {element} adaugă / înlocuiește; {sterge: id}; {aplica: element, intrare}
                try:
                    if model.get("sterge"):
                        return self._send(200, json.dumps(galerie.sterge(str(model["sterge"])), ensure_ascii=False))
                    if model.get("aplica") is not None:
                        return self._send(200, json.dumps({"intrare": galerie.aplica(model["aplica"], model.get("intrare"))},
                                                          ensure_ascii=False))
                    return self._send(200, json.dumps(galerie.adauga(model.get("element")), ensure_ascii=False))
                except ValueError as e:
                    return self._send(400, json.dumps({"eroare": str(e)[:1].upper() + str(e)[1:] + "."}, ensure_ascii=False))
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
                if p == "/api/export/planse":
                    # r12: pachetul de planșe A3 (IE 07.x c.c. pe invertor, IE 08, IE 09 c.a., IE 09.1 releu, IE 11 smart meter)
                    from engine import planse as _pl
                    lst = _pl.planse_din_model(m)
                    if not lst:
                        return self._send(400, json.dumps({"eroare": "Pachetul de planșe se generează pentru CEF calculate."}, ensure_ascii=False))
                    zipb = _pl.pachet_planse_zip(lst, name, pdf=lambda svgs: html_to_pdf(_pl.html_multipagina(svgs)))
                    return self._send(200, zipb, "application/zip", name + "_planse_A3.zip")
                fmt = (urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("format") or [""])[0].lower()
                if p in ("/api/export/tabel_cabluri", "/api/export/fisa_reglaje", "/api/export/tabele"):
                    # E2: tabelul de cabluri / fișa de reglaje + Ik pe noduri — .xlsx (implicit) sau ?format=pdf
                    t = {"/api/export/tabel_cabluri": [documente_tabele.tabel_cabluri(m, r)],
                         "/api/export/fisa_reglaje": _tabele_predare(m, r)[1:],
                         "/api/export/tabele": _tabele_predare(m, r)}[p]
                    suf = p.rsplit("/", 1)[1]
                    if fmt == "pdf":
                        h = documente_tabele.tabel_html(t, m.get("cartus"))
                        try:
                            return self._send(200, html_to_pdf(h), "application/pdf", f"{name}_{suf}.pdf")
                        except RuntimeError:
                            return self._send(200, h, "text/html; charset=utf-8", f"{name}_{suf}.html")
                    return self._send(200, documente_tabele.tabel_xlsx(t, m.get("cartus")), XLSX, f"{name}_{suf}.xlsx")
                if p == "/api/export/caiet_sarcini":      # E2: .docx (implicit) sau ?format=pdf
                    doc = documente_caiet.caiet_sarcini(model, m, r)
                    if fmt == "pdf":
                        try:
                            return self._send(200, html_to_pdf(doc.html()), "application/pdf", f"{name}_caiet_de_sarcini.pdf")
                        except RuntimeError:
                            return self._send(200, doc.html(), "text/html; charset=utf-8", f"{name}_caiet_de_sarcini.html")
                    try:
                        return self._send(200, doc.docx(), DOCX, f"{name}_caiet_de_sarcini.docx")
                    except ImportError:
                        return self._send(200, doc.html(), "text/html; charset=utf-8", f"{name}_caiet_de_sarcini.html")
                if p == "/api/export/dosar_racordare":    # E2: .zip cu .docx + .pdf + planșa
                    if (m.get("calc") or {}).get("tip_schema") not in ("cef", "prosumator"):
                        return self._send(400, json.dumps({"eroare": "Dosarul de racordare se generează pentru prosumator și CEF."},
                                                          ensure_ascii=False))
                    try:
                        pl = to_pdf(m)
                    except RuntimeError:
                        pl = None
                    z = documente_racordare.dosar_zip(model, m, r, name, pdf=html_to_pdf if CHROME else None, plansa_pdf=pl)
                    return self._send(200, z, "application/zip", f"{name}_dosar_racordare.zip")
                cheie = p.rsplit("/", 1)[1]
                if cheie in documente_vederi.CHEI_EXPORT:  # E2: exportul documentelor din tab-ul „Documente”
                    pl = None
                    if cheie == "racordare":
                        try:
                            pl = to_pdf(m)
                        except RuntimeError:
                            pl = None
                    try:
                        ct, corp, suf = documente_vederi.export(cheie, model, m, r, pdf=html_to_pdf if CHROME else None, plansa_pdf=pl)
                    except documente_vederi.Indisponibil as e:
                        return self._send(400, json.dumps({"eroare": str(e)[:1].upper() + str(e)[1:] + "."}, ensure_ascii=False))
                    return self._send(200, corp, ct, name + suf)
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
            if p == "/api/setari/cheie":     # F.9: cheia API — doar în memoria procesului (+ ~/.config dacă „ține minte”)
                try:
                    sursa = cheie_api.seteaza(model.get("cheie"), pastreaza=bool(model.get("pastreaza")))
                except ValueError as e:
                    return self._send(400, json.dumps({"eroare": str(e)[:1].upper() + str(e)[1:] + "."}, ensure_ascii=False))
                return self._send(200, json.dumps({"claude": bool(cheie_api.citeste()), "claude_sursa": sursa}))
            if p == "/api/chat/cerere":      # versiunea web: corpul cererii către Claude (apelul îl face browserul)
                return self._send(200, json.dumps({"url": interpretor.URL_API, "beta": interpretor.BETA_LLM,
                                                   "versiune": interpretor.VERSIUNE_API,
                                                   "corp": interpretor.cerere_llm(str(model.get("text", "")))}, ensure_ascii=False))
            if p == "/api/chat":
                # F.9: Claude e interpretorul principal când există cheie (sau când browserul aduce deja răspunsul lui);
                # regulile locale rulează mereu ca verificare încrucișată / rezervă
                text = str(model.get("text", ""))
                if model.get("raspuns_llm") is not None:
                    it = interpretor.interpreteaza(text, raspuns_llm=model["raspuns_llm"])
                else:
                    it = interpretor.interpreteaza(text, foloseste_llm=model.get("claude", True) is not False and bool(cheie_api.citeste()))
                avansat = it.get("motor") == "llm"
                motiv = model.get("eroare_llm") or next((x for x in it.get("presupus") or [] if x.startswith("(LLM indisponibil")
                                                         or x.startswith("(citirea Claude")), None)
                from engine.calc.umanizare import umanizeaza as _um
                def _um_t(x):            # echipa1 (ux 5): textele pentru om fără chei interne
                    if isinstance(x, str): return _um(x)
                    if isinstance(x, list): return [_um_t(y) for y in x]
                    if isinstance(x, dict): return {k: (_um_t(v) if k in ("mesaj", "text", "intrebare", "motiv") else v) for k, v in x.items()}
                    return x
                for k_ in ("presupus", "intrebari", "refuz_motiv", "intelegere", "avertismente"):
                    if it.get(k_) is not None:
                        it[k_] = _um_t(it[k_])
                out = {"interpretare": {k: it.get(k) for k in ("actiune", "tip_schema", "presupus", "intrebari", "refuz_cod", "refuz_motiv",
                                                               "intelegere", "avertismente", "motor", "intrare_fizica", "cartus",
                                                               "verificare_incrucisata", "neconsumat")},
                       "citire": {"avansata": avansat,
                                  "mesaj": "citire avansată (Claude), verificată cu regulile locale" if avansat else
                                  ("citire avansată indisponibilă — " + (str(motiv).strip("()") if motiv else "fără cheie API")
                                   + "; s-au folosit regulile locale")}}
                if it.get("intrare_fizica"):
                    # echipa1 P0-5: datele obligatorii ale panoului de confirmare — regula motorului (BESS fără PV trece)
                    from engine.confirmare import campuri_lipsa, intrebari_confirmare
                    out["interpretare"]["lipsa"] = campuri_lipsa(it["intrare_fizica"])
                    # Î5 (28.10.2026): întrebările neblocante (prosumator: protecții pe c.c. și pe c.a.)
                    iq = intrebari_confirmare(it["intrare_fizica"])
                    if iq:
                        out["interpretare"]["intrebari"] = list(out["interpretare"].get("intrebari") or []) + \
                            [x["intrebare"] for x in iq]
                if it.get("actiune") != "refuza" and it.get("intrare_fizica"):
                    cart = _cartus_chat(it.get("cartus") or {})
                    out["cartus_chat"] = cart
                    if not model.get("fara_model"):     # interfața: întâi panoul de confirmare, desenul după /api/chat/confirma
                        out.update(_genereaza_chat(it["intrare_fizica"], cart, model.get("model")))
                return self._send(200, json.dumps(out, ensure_ascii=False, default=str))
            if p == "/api/chat/confirma":    # intrarea confirmată / corectată de proiectant în panoul de după chat
                intr = model.get("intrare")
                if not isinstance(intr, dict) or not intr.get("tip_schema"):
                    return self._send(400, json.dumps({"eroare": "Lipsește intrarea confirmată (tip_schema)."}, ensure_ascii=False))
                cart = model.get("cartus_chat") if isinstance(model.get("cartus_chat"), dict) else {}
                return self._send(200, json.dumps(_genereaza_chat(intr, cart, model.get("model")), ensure_ascii=False, default=str))
            if p == "/api/chat/verifica":    # r11: previzualizarea valorilor declarate pe care motorul le-ar schimba (fără desen)
                intr = model.get("intrare")
                if not isinstance(intr, dict) or not intr.get("tip_schema"):
                    return self._send(400, json.dumps({"eroare": "Lipsește intrarea (tip_schema)."}, ensure_ascii=False))
                return self._send(200, json.dumps(_verifica_declarate(intr), ensure_ascii=False, default=str))
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
