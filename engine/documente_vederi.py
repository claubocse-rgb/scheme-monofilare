"""documente_vederi — tab-ul „Documente” al interfeței (E2): previzualizarea și exportul fiecărui document, pe chei.

    previzualizare(cheie, corp, m, r) → (content_type, corp)      POST /api/documente/<cheie>
    export(cheie, corp, m, r, pdf)    → (content_type, bytes, sufix_fișier)   POST /api/export/<cheie>

Chei: cabluri, reglaje, curbe, pierderi, spd, carcasa, productie (previzualizare + export) și etichete, racordare,
caiet (doar export). Previzualizarea e JSON {titlu, coloane, randuri, note} / {titlu, tabele[]} (tabele), SVG (curbe)
sau HTML (SPD). `pdf` = convertorul HTML → PDF al aplicației (Chrome); fără el exportul „PDF” iese HTML.
"""
import json
import math

from . import documente_tabele as dt, documente_protectii as dp, documente_racordare as dr, documente_caiet as dc, pvgis
from .documente_doc import Document, Camp, camp

CHEI_PREVIZUALIZARE = ("cabluri", "reglaje", "curbe", "pierderi", "spd", "carcasa", "productie")
CHEI_EXPORT = CHEI_PREVIZUALIZARE + ("etichete", "racordare", "caiet")
JSON = "application/json; charset=utf-8"
HTML = "text/html; charset=utf-8"
SVG = "image/svg+xml; charset=utf-8"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class Indisponibil(ValueError):
    """documentul nu se aplică schemei (→ 400 cu mesaj)"""


def _vizibil(t):
    """tabel intern {coloane: [(cheie, eticheta)], randuri: [dict]} → {coloane: [etichete], randuri: [[valori]]}"""
    col = t["coloane"]
    rows = [[_val(r.get(k)) for k, _ in col] for r in t["randuri"]]
    return {"titlu": t["titlu"], "coloane": [e for _, e in col], "randuri": rows, "note": t.get("note") or []}


def _val(v):
    if isinstance(v, float):
        return round(v, 3)
    if isinstance(v, bool):
        return "da" if v else ""
    return v


def _productie(corp, m):
    inp = m.get("calc") or {}
    p = inp.get("productie") if isinstance(inp.get("productie"), dict) else (corp.get("pvgis") if isinstance(corp.get("pvgis"), dict) else {})
    kwp = inp.get("kWp") or sum(float(g.get("n", 1) or 1) * float(g.get("Pn_kW") or 0) for g in inp.get("invertoare") or []
                                if isinstance(g, dict)) or inp.get("Pn_inv_kW")
    return p, (float(kwp) if kwp else None)


def productie_kwh_kwp(m, corp=None):
    p, _ = _productie(corp or {}, m)
    y = p.get("kWh_kWp_an") or (m.get("calc") or {}).get("productie_specifica_kWh_kWp")
    try:
        return float(y) if y else None
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------------------------------------ tabele
def _t_cabluri(m, r):
    return _vizibil(dt.tabel_cabluri(m, r))


def _t_reglaje(m, r):
    f = dt.fisa_reglaje(m, r)
    tab = [_vizibil(dict(f, coloane=[c for c in f["coloane"] if c[0] != "verificat"]))]
    if f["ik_noduri"]:
        tab.append(_vizibil({"titlu": "Curenți de scurtcircuit pe noduri", "randuri": f["ik_noduri"],
                             "coloane": [("de_la", "De la"), ("nod", "Nod"), ("Ik3max_origine_kA", "Ik3max origine [kA]"),
                                         ("Ik3max_capat_kA", "Ik3max capăt [kA]"), ("Ik1min_capat_A", "Ik1min capăt [A]"),
                                         ("Ia_A", "Ia [A]"), ("t_deconectare_s", "t [s]")]}))
    pi = f.get("protectie_interfata")
    if pi and pi.get("randuri"):
        tab.append({"titlu": pi.get("titlu") or "Protecția de interfață", "coloane": ["Funcția", "Prag", "Temporizare"],
                    "randuri": [list(x[:3]) for x in pi["randuri"]], "note": [pi.get("sursa") or ""]})
    return {"titlu": f["titlu"], "tabele": tab, "note": f["note"]}


def _t_pierderi(m, r, corp):
    p = dt.pierderi_cabluri(m, r, m.get("calc"), productie_kwh_kwp(m, corp))
    if not p.get("aplicabil"):
        raise Indisponibil(p.get("motiv") or "nu se aplică")
    rows = [["c.c. (stringuri)", f"{p['cc']['n_stringuri']} × H1Z2Z2-K {dt._f(p['cc']['S_mm2'])} mm²", p["cc"]["L_m"],
             round(p["cc"]["I_string_A"], 2), round(p["cc"]["R_ohm"], 4), round(p["cc"]["P_pierderi_kW"], 3),
             round(p["cc"]["pct"], 2) if p["cc"]["pct"] is not None else None]]
    for x in p["ca"]["ramuri"]:
        rows.append([x["obiect"], x["cablu"], x["L_m"], round(x["I_A"], 2), round(x["R_ohm"], 4), round(x["P_pierderi_kW"], 3), None])
    rows.append(["TOTAL c.a.", "", None, None, None, round(p["ca"]["P_pierderi_kW"], 3),
                 round(p["ca"]["pct"], 2) if p["ca"]["pct"] is not None else None])
    e = p["energie_pierduta_kWh"]
    note = [f"Producție {dt._f(p['productie_kWh_kWp'], 0)} kWh/kWp/an → {dt._f(p['energie_an_kWh'], 0)} kWh/an; energie pierdută "
            f"estimată: c.c. {dt._f(e['cc'], 0)} kWh, c.a. {dt._f(e['ca'], 0)} kWh, total {dt._f(e['total'], 0)} kWh/an "
            f"({dt._f(p['energie_pierduta_pct'], 2)} %).", p["metoda"]] + p["avertismente"] + \
           ([f"Presupus: {'; '.join(p['presupus'])}"] if p["presupus"] else [])
    return {"titlu": "PIERDERI DE PUTERE ÎN CABLURI", "coloane": ["Ramură", "Cablu", "L [m]", "I [A]", "R [Ω]", "P pierderi [kW]",
                                                                  "Pierderi [%]"], "randuri": rows, "note": note, "date": p}


def _t_carcasa(m, corp):
    c = dt.dimensionare_carcasa(m, corp.get("rezerva_pct", 25))
    rows = [[a["ref"], a["tip"].upper(), a["module"], a["unde"]] for a in c["aparate"]]
    rows += [[a["ref"], a["tip"].upper(), "nemodular", a["unde"]] for a in c["nemodulare"]]
    note = [f"Aparate: {c['module_aparate']} module; cu rezervă {dt._f(c['rezerva_pct'], 0)} %: {c['module_cu_rezerva']} module → "
            f"{c['randuri']} × {c['module_pe_rand']} = {c['capacitate']} module ({c['module_libere']} libere).",
            "Carcasa propusă: " + c["carcasa_propusa"]] + c["note"]
    return {"titlu": "DIMENSIONAREA CARCASEI TABLOULUI (module DIN)", "coloane": ["Ref.", "Aparat", "Module", "Circuit"],
            "randuri": rows, "note": note, "date": c}


def _t_productie(m, corp):
    if (m.get("calc") or {}).get("tip_schema") not in ("cef", "prosumator", "bess"):
        raise Indisponibil("producția estimată se calculează pentru CEF și prosumator")
    p, kwp = _productie(corp, m)
    y = productie_kwh_kwp(m, corp)
    if not y:
        return {"titlu": "PRODUCȚIE ESTIMATĂ", "coloane": [], "randuri": [],
                "note": ["Lipsește producția specifică: calculează cu PVGIS sau introdu manual kWh/kWp/an."], "necesita_valoare": True}
    lun = p.get("lunar") if isinstance(p.get("lunar"), list) else []
    rows = []
    if len(lun) == 12:
        for i, v in enumerate(lun):
            v = v.get("kWh") if isinstance(v, dict) else v
            rows.append([pvgis.LUNI[i], round(float(v or 0), 1), round(float(v or 0) * (kwp or 0), 0) if kwp else None])
    rows.append(["AN", round(y, 0), round(y * kwp, 0) if kwp else None])
    rez = pvgis.din_valoare(y, kwp) if kwp else None
    if rez:
        rez["sursa"] = p.get("sursa") or rez["sursa"]
        rez["parametri"] = {"unghi": p.get("unghi"), "azimut": p.get("azimut")} if p.get("unghi") is not None else {}
        rez["pierderi_pct"] = None
    note = [pvgis.paragraf_memoriu(rez) if rez else "kWp nedeclarat — producția totală nu se poate calcula."]
    if p.get("lat") is not None:
        note.append(f"Amplasament: {p.get('lat')}, {p.get('lon')}; pierderi sistem {p.get('pierderi_pct', 14)} %"
                    + (f"; date din {p['data']}" if p.get("data") else ""))
    return {"titlu": "PRODUCȚIE ESTIMATĂ", "coloane": ["Luna", "kWh/kWp", f"kWh ({dt._f(kwp or 0)} kWp)"], "randuri": rows,
            "note": note}


def _spd_html(m):
    inp = m.get("calc") or {}
    e = dp.evaluare_spd(inp, m)
    d = Document("EVALUAREA NECESITĂȚII SPD", "SR HD 60364-4-443 · SR HD 60364-7-712", (m.get("cartus") or {}).get("denumire2", ""))
    d.p(e["temei"] + ".")
    ca = e["ca"]
    d.campuri([("Decizie c.a.", Camp(ca["decizie"])), ("Tip / poli", Camp(f"{ca['tip']} · {ca['poli']}")),
               ("Up / In", Camp(f"≤ {dt._f(ca['Up_kV'])} kV · In {dt._f(ca['In_kA'], 0)} kA" + (f" · Iimp {dt._f(ca['Iimp_kA'])} kA" if ca["Iimp_kA"] else ""))),
               ("Conexiune", Camp(ca["conexiune"])), ("Protecție amonte", Camp(ca["protectie_amonte"])),
               ("CRL / LP / Ng / fenv", camp(f"{dt._f(e['CRL'], 0) if e['CRL'] is not None else '∞'} / {dt._f(e['LP_km'], 2)} km / "
                                             f"{dt._f(e['Ng'])} / {dt._f(e['fenv'], 0)}"))])
    if e["cc"]:
        d.campuri([("SPD c.c.", Camp("necesar" if e["cc"]["necesar"] else "necerut")), ("Temei c.c.", Camp(e["cc"]["temei"])),
                   ("Tip c.c.", Camp(e["cc"]["tip"])), ("Ucpv", Camp(e["cc"]["Ucpv_V"]))])
    if e["motive"] or e["neconcordante"]:
        d.lista(e["motive"] + ["NECONCORDANȚĂ: " + x for x in e["neconcordante"]])
    if e["presupus"]:
        d.p("Presupus: " + "; ".join(e["presupus"]))
    return d.html(), e


# ------------------------------------------------------------------------------------------------ curbe (SVG)
def svg_curbe(c, latime=760, inaltime=520):
    """graficul log-log al benzilor timp-curent (previzualizare; desenul planșei are propriul randament)"""
    ap = c["aparate"]
    if not ap:
        return ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 60'><text x='10' y='35' font-size='14'>"
                "Nicio protecție cu curbă în schemă.</text></svg>")
    imin = min(min(a["curba"]["I_A"]) for a in ap)
    imax = max(max(a["curba"]["I_A"]) for a in ap)
    for a in ap:
        for k in ("Ik3max_A", "Ik1min_A"):
            if a.get(k):
                imax = max(imax, a[k])
    x0, x1 = 10 ** math.floor(math.log10(imin)), 10 ** math.ceil(math.log10(imax))
    t0, t1 = dp.T_MIN_S, dp.T_MAX_S
    ml, mr, mt, mb = 60, 160, 20, 40
    W, H = latime - ml - mr, inaltime - mt - mb

    def X(i):
        return ml + W * (math.log10(i) - math.log10(x0)) / (math.log10(x1) - math.log10(x0))

    def Y(t):
        return mt + H * (math.log10(t1) - math.log10(t)) / (math.log10(t1) - math.log10(t0))
    o = [f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {latime} {inaltime}' font-family='Arial' font-size='10'>",
         f"<rect x='{ml}' y='{mt}' width='{W}' height='{H}' fill='#fff' stroke='#333'/>"]
    d = int(math.log10(x0))
    while 10 ** d <= x1:
        x = X(10 ** d)
        o.append(f"<line x1='{x:.1f}' y1='{mt}' x2='{x:.1f}' y2='{mt + H}' stroke='#ccc'/><text x='{x:.1f}' y='{mt + H + 14}' "
                 f"text-anchor='middle'>{10 ** d:g}</text>")
        d += 1
    for e in range(-3, 5):
        y = Y(10 ** e)
        if mt - 1 <= y <= mt + H + 1:
            o.append(f"<line x1='{ml}' y1='{y:.1f}' x2='{ml + W}' y2='{y:.1f}' stroke='#ccc'/><text x='{ml - 6}' y='{y + 3:.1f}' "
                     f"text-anchor='end'>{10 ** e:g}</text>")
    o.append(f"<text x='{ml + W / 2}' y='{inaltime - 6}' text-anchor='middle'>I [A]</text>"
             f"<text x='14' y='{mt + H / 2}' transform='rotate(-90 14 {mt + H / 2})' text-anchor='middle'>t [s]</text>")
    culori = ["#1f6feb", "#d1242f", "#1a7f37", "#9a6700", "#8250df", "#bf3989", "#0a7f87", "#6e7781"]
    for k, a in enumerate(ap[:12]):
        cu = culori[k % len(culori)]
        cv = a["curba"]
        sus = [(X(i), Y(t)) for i, t in zip(cv["I_A"], cv["t_max_s"]) if x0 <= i <= x1]
        jos = [(X(i), Y(t)) for i, t in zip(cv["I_A"], cv["t_min_s"]) if x0 <= i <= x1]
        if not sus:
            continue
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in sus + jos[::-1])
        o.append(f"<polygon points='{pts}' fill='{cu}' fill-opacity='0.15' stroke='{cu}' stroke-width='1'/>")
        ly = mt + 12 + 14 * k
        o.append(f"<rect x='{ml + W + 10}' y='{ly - 8}' width='10' height='10' fill='{cu}' fill-opacity='0.5'/>"
                 f"<text x='{ml + W + 24}' y='{ly}'>{_esc(a['ref'])} {_esc(a['eticheta'])[:22]}</text>")
        for kk, sym in (("Ik3max_A", "▲"), ("Ik1min_A", "▼")):
            if a.get(kk) and x0 <= a[kk] <= x1:
                o.append(f"<text x='{X(a[kk]):.1f}' y='{mt + H - 2}' fill='{cu}' text-anchor='middle'>{sym}</text>")
    o.append(f"<text x='{ml + W + 10}' y='{mt + H - 4}' font-size='9'>▲ Ik3max · ▼ Ik1min</text></svg>")
    return "".join(o)


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ------------------------------------------------------------------------------------------------ etichete
def etichete_html(m):
    """etichete de tablou A4: o bandă de 18 mm pe aparat, lățimea = module × 17,5 mm; plus etichetele obligatorii"""
    inp = m.get("calc") or {}
    k = m.get("cartus") or {}
    et = []
    for n in dt.noduri(m):
        if n["rol"] == "intrare_cc" and n["nod"].get("cablu_ca"):
            continue
        for a in n["nod"].get("aparate") or []:
            if a.get("tip") in dt.TIPURI_PROTECTIE or a.get("tip") in ("spd",):
                mod = dt._module_aparat(a) or 2
                et.append((a.get("ref") or "", n["la"] if n["rol"] == "plecare" else "general", " · ".join(a.get("spec") or []), mod))
    for a in (m.get("bara") or {}).get("laterale") or []:
        if isinstance(a, dict) and a.get("tip") == "spd":
            et.append((a.get("ref") or "", "SPD", " · ".join(a.get("spec") or []), dt._module_aparat(a) or 2))
    oblig = []
    if inp.get("tip_schema") in ("cef", "prosumator", "ge_ats"):
        oblig.append("ATENȚIE! Instalație alimentată din două surse (rețea + " +
                     ("generator" if inp.get("tip_schema") == "ge_ats" else "sistem fotovoltaic") + "). Separați ambele surse "
                     "înainte de intervenție.")
    if inp.get("tip_schema") in ("cef", "prosumator"):
        oblig.append("ATENȚIE! Conductoarele de c.c. rămân sub tensiune la lumina zilei.")
    css = ("@page{size:A4;margin:10mm}body{font:8pt Arial,sans-serif}h1{font-size:11pt}.r{display:flex;flex-wrap:wrap;gap:0}"
           ".e{height:18mm;border:.3mm solid #000;box-sizing:border-box;padding:.8mm;overflow:hidden}"
           ".e b{display:block;font-size:9pt}.o{border:.6mm solid #c00;color:#c00;font-weight:bold;padding:3mm;margin:3mm 0;"
           "font-size:11pt;width:120mm}")
    h = [f"<!doctype html><html lang='ro'><head><meta charset='utf-8'><style>{css}</style></head><body>"
         f"<h1>Etichete tablou — {_esc(k.get('denumire2', ''))}</h1><div class='r'>"]
    for ref, c, spec, mod in et:
        h.append(f"<div class='e' style='width:{max(1, mod) * 17.5:.1f}mm'><b>{_esc(ref)}</b>{_esc(c)}<br>{_esc(spec)}</div>")
    h.append("</div>")
    h += [f"<div class='o'>{_esc(x)}</div>" for x in oblig]
    h.append("<p>Lățimea benzilor = numărul de module × 17,5 mm (verificați pe aparatele montate); tipăriți la scara 100 %.</p></body></html>")
    return "".join(h), len(et)


# ------------------------------------------------------------------------------------------------ API
def previzualizare(cheie, corp, m, r):
    if cheie == "cabluri":
        return JSON, json.dumps(_t_cabluri(m, r), ensure_ascii=False, default=str)
    if cheie == "reglaje":
        return JSON, json.dumps(_t_reglaje(m, r), ensure_ascii=False, default=str)
    if cheie == "curbe":
        return SVG, svg_curbe(dp.curbe_timp_curent(m, r))
    if cheie == "pierderi":
        t = _t_pierderi(m, r, corp)
        t.pop("date", None)
        return JSON, json.dumps(t, ensure_ascii=False, default=str)
    if cheie == "spd":
        return HTML, _spd_html(m)[0]
    if cheie == "carcasa":
        t = _t_carcasa(m, corp)
        t.pop("date", None)
        return JSON, json.dumps(t, ensure_ascii=False, default=str)
    if cheie == "productie":
        return JSON, json.dumps(_t_productie(m, corp), ensure_ascii=False, default=str)
    raise KeyError(cheie)


def _tabel_html(t, cartus):
    """tabel vizibil {coloane: [etichete], randuri: [[…]]} sau {tabele: […]} → HTML A4 peisaj"""
    tab = t.get("tabele") or [t]
    intern = [{"titlu": x.get("titlu") or t.get("titlu", ""), "coloane": [(str(i), c) for i, c in enumerate(x.get("coloane") or [])],
               "randuri": [{str(i): v for i, v in enumerate(rw)} for rw in x.get("randuri") or []],
               "note": (x.get("note") or []) + ((t.get("note") or []) if x is tab[-1] and t.get("tabele") else [])} for x in tab]
    return dt.tabel_html(intern, cartus)


def _tabel_xlsx(t, cartus):
    tab = t.get("tabele") or [t]
    intern = [{"titlu": x.get("titlu") or t.get("titlu", ""), "coloane": [(str(i), c) for i, c in enumerate(x.get("coloane") or [])],
               "randuri": [{str(i): v for i, v in enumerate(rw)} for rw in x.get("randuri") or []], "note": x.get("note") or []}
              for x in tab]
    return dt.tabel_xlsx(intern, cartus)


def _ca_pdf(html, pdf):
    if pdf:
        try:
            return "application/pdf", pdf(html), ".pdf"
        except Exception:
            pass
    return HTML, html, ".html"


def export(cheie, corp, m, r, pdf=None, plansa_pdf=None):
    """(content_type, corp, sufix) — sufixul include extensia"""
    k = m.get("cartus") or {}
    tip = (m.get("calc") or {}).get("tip_schema")
    if cheie == "cabluri":
        return XLSX, dt.tabel_xlsx(dt.tabel_cabluri(m, r), k), "_cabluri.xlsx"
    if cheie == "reglaje":
        ct, b, ext = _ca_pdf(_tabel_html(_t_reglaje(m, r), k), pdf)
        return ct, b, "_reglaje" + ext
    if cheie == "curbe":
        c = dp.curbe_timp_curent(m, r)
        h = (f"<!doctype html><html lang='ro'><head><meta charset='utf-8'><style>@page{{size:A4 landscape;margin:10mm}}"
             f"body{{font:9pt Arial}}svg{{width:100%;height:auto}}</style></head><body><h3>Curbe timp-curent — "
             f"{_esc(k.get('denumire2', ''))}</h3>{svg_curbe(c)}<p>{_esc(c['nota'])}</p></body></html>")
        ct, b, ext = _ca_pdf(h, pdf)
        return ct, b, "_curbe" + ext
    if cheie == "pierderi":
        return XLSX, _tabel_xlsx(_t_pierderi(m, r, corp), k), "_pierderi.xlsx"
    if cheie == "spd":
        ct, b, ext = _ca_pdf(_spd_html(m)[0], pdf)
        return ct, b, "_SPD" + ext
    if cheie == "carcasa":
        ct, b, ext = _ca_pdf(_tabel_html(_t_carcasa(m, corp), k), pdf)
        return ct, b, "_carcasa" + ext
    if cheie == "productie":
        t = _t_productie(m, corp)
        if t.get("necesita_valoare"):
            raise Indisponibil(t["note"][0])
        ct, b, ext = _ca_pdf(_tabel_html(t, k), pdf)
        return ct, b, "_productie" + ext
    if cheie == "etichete":
        ct, b, ext = _ca_pdf(etichete_html(m)[0], pdf)
        return ct, b, "_etichete" + ext
    if cheie == "caiet":
        doc = dc.caiet_sarcini(corp, m, r)
        try:
            return DOCX, doc.docx(), "_caiet_sarcini.docx"
        except ImportError:
            return HTML, doc.html(), "_caiet_sarcini.html"
    if cheie == "racordare":
        if tip in ("cef", "prosumator"):
            return "application/zip", dr.dosar_zip(corp, m, r, pdf=pdf, plansa_pdf=plansa_pdf), "_racordare.zip"
        doc = dr.cerere_consum(dr.date_proiect(corp, m, r))
        try:
            return DOCX, doc.docx(), "_racordare.docx"
        except ImportError:
            return HTML, doc.html(), "_racordare.html"
    raise KeyError(cheie)
