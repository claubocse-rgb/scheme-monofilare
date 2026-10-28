"""r12 (proiecte reale, Top 15 #10): ieșirea pe mai multe planșe A3 — convenția proiectantului de CEF.

Din modelul calculat al unei CEF (constructor.genereaza) se derivă pachetul de planșe, toate A3, numerotate IE-xx/FV:
  * IE 07.k/FV — schema bloc c.c. a invertorului k (câmpul PV cu stringurile pe MPPT, cutia de joncțiune, separatorul,
    SPD c.c., invertorul) + tabelele „Model panou solar” și „Model invertor” cu datele din fișă;
  * IE 08/FV   — schema bloc c.c. + c.a. (planșa completă, scalată pe A3);
  * IE 09/FV   — schema monofilară c.a.: invertoarele cu caseta de date („Către INVERTOR k … U, P, Imax, RS485”),
    tablourile intermediare, TEG / TGD-CF, racordul;
  * IE 09.1/FV — conexiunile releului de interfață (QG, PI, UPS) + tabelul de reglaje PI;
  * IE 11/FV   — smart meter-ul la punctul de racord (TC, SM, SmartLogger, RS485), când există.
Pachetul se exportă ca ZIP (SVG + DXF pe planșă + PDF multi-pagină dacă există Chrome).

Desenul, lista și notele fiecărei planșe vin din același calcul (o singură sursă de date) — planșele nu se pot
contrazice între ele.
"""
import copy

from .calc.texte import fmt_ro

NB = " "
PUNCT = "·"

ETICHETE_MODUL = (("producator", "Producător"), ("model", "Model"), ("Pmax_W", "Pmax [Wp]"), ("Voc_V", "Voc [V]"),
                  ("Isc_A", "Isc [A]"), ("Vmpp_V", "Vmpp [V]"), ("Impp_A", "Impp [A]"),
                  ("beta_Voc_pct_K", "β(Voc) [%/K]"), ("Umax_sistem_V", "Umax sistem [V]"), ("I_rev_A", "Siguranță max. [A]"))
ETICHETE_INVERTOR = (("producator", "Producător"), ("model", "Model"), ("Pn_kW", "Pn c.a. [kW]"),
                     ("Iac_max_A", "Iac max [A]"), ("Umax_dc_V", "Umax c.c. [V]"), ("MPPT_min_V", "MPPT min [V]"),
                     ("MPPT_max_V", "MPPT max [V]"), ("nr_MPPT", "Nr. MPPT"), ("Idc_max_A", "Idc max / MPPT [A]"))


def _f(x, z=1):
    if x is None:
        return "—"
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return fmt_ro(x, z)
    return str(x)


def cere_planse(intrare, rz=None):
    """pachetul de planșe e cerut (`planse: true`) sau implicit (CEF trifazat cu mai mult de un invertor);
    `planse: false` îl oprește"""
    if not isinstance(intrare, dict) or intrare.get("tip_schema") not in ("cef", "bess"):
        return False
    p = intrare.get("planse")
    if isinstance(p, str):
        p = {"true": True, "da": True, "false": False, "nu": False}.get(p.strip().lower())
    if p is not None:
        return bool(p)
    n = sum(int(g.get("n", 1)) for g in intrare.get("invertoare") or [] if isinstance(g, dict))
    n += sum(int(g.get("n", 1)) for t in intrare.get("tablouri_intermediare") or [] if isinstance(t, dict)
             for g in t.get("invertoare") or [] if isinstance(g, dict))
    return n > 1 and intrare.get("retea") != "mono"


def _baza(m, cod, titlu):
    """modelul unei planșe: cartușul și setările planșei-mamă, A3 fix, codul planșei și titlul ei"""
    b = {k: copy.deepcopy(v) for k, v in m.items() if k in ("cartus", "calc", "calc_rezumat", "blocaj", "confirmari")}
    b.update(format="A3", auto_format=False, lista_auto=True, legenda=True, plansa_pachet=True)
    b["cartus"] = dict(b.get("cartus") or {}, plansa=cod, denumire1=titlu)
    b["note"] = []
    return b


def _tabel_fisa(titlu, par, etichete):
    rand = [[e, _f(par.get(k), 2)] for k, e in etichete if par.get(k) not in (None, "")]
    return {"titlu": titlu, "coloane": ["Parametru", "Valoare"], "randuri": rand} if rand else None


def _e_cc(a):
    return a.get("tip") in ("string_pv", "gpv", "separator_cc", "invertor", "nod", "baterie", "convertor_bess")


def plansa_cc(m, b, k, cod):
    """IE 07.k — partea de c.c. a invertorului desenat complet în intrarea `b` (câmp PV → invertor) până la cablul c.a."""
    pl = _baza(m, cod, f"SCHEMĂ BLOC C.C. — {(b.get('sursa') or {}).get('titlu', '')}")
    ap = []
    for a in b.get("aparate") or []:
        if not _e_cc(a):
            break
        ap.append(copy.deepcopy(a))
    inv = next((a for a in ap if a.get("tip") == "invertor"), {})
    pv = next((a for a in ap if a.get("tip") == "string_pv"), {})
    pl["intrari"] = [{"sursa": copy.deepcopy(b.get("sursa") or {}), "cablu": copy.deepcopy(b.get("cablu") or {}),
                      "aparate": ap}]
    pl["plecari"] = [{"aparate": [], "cablu": copy.deepcopy(b.get("cablu_ca") or {}),
                      "sarcina": {"titlu": f"către tabloul c.a. — {inv.get('ref', '')}",
                                  "sub": "protecția c.a. și restul instalației: planșa IE 09/FV"}}]
    pl["bara"] = {"afisare": False}
    pl["carcasa"] = None
    tab = [t for t in (_tabel_fisa("MODEL PANOU SOLAR", pv.get("param") or {}, ETICHETE_MODUL),
                       _tabel_fisa("MODEL INVERTOR", inv.get("param") or {}, ETICHETE_INVERTOR)) if t]
    if tab:
        pl["tabele"] = tab
    pl["note"] = [f"1. Schema bloc c.c. a invertorului {inv.get('ref', '')}: "
                  + (b.get("sursa") or {}).get("sub", "") + "; cablu solar H1Z2Z2-K, conductoarele + / − pozate alăturat.",
                  "2. Ramele modulelor și structura metalică se leagă la priza de pământ (echipotențializare), Rp ≤ 1 Ω.",
                  "3. Se citește împreună cu planșele IE 08/FV și IE 09/FV."]
    return pl


def _caseta_invertor(b):
    """r12 (#13): caseta de date a invertorului pe planșa c.a. — „Către INVERTOR k … U 400 V, P, Imax, RS485”"""
    inv = next((a for a in b.get("aparate") or [] if a.get("tip") == "invertor"), None)
    if inv is None:
        return None
    par = inv.get("param") or {}
    ref = inv.get("ref", "")
    mod = " ".join(str(x) for x in (par.get("producator"), par.get("model")) if x)
    u = "230 V" if par.get("retea") == "mono" else f"{_f(par.get('U_ca_V') or 400, 0)} V"
    sub = f"{mod + ' ' + PUNCT + ' ' if mod else ''}U {u} {PUNCT} P {_f(par.get('Pn_kW'))} kW {PUNCT} " \
          f"Imax {_f(par.get('Iac_max_A'))} A"
    if any(l.get("eticheta") == "RS485" for l in inv.get("laterale") or []):
        sub += f" {PUNCT} RS485"
    if not par and inv.get("spec"):
        sub = " · ".join(inv["spec"])
    return {"titlu": f"Către {ref}", "sub": sub}


def plansa_ca(m, cod):
    """IE 09 — monofilara c.a.: fiecare invertor = caseta de date + simbolul invertorului + protecția lui c.a.;
    partea de c.c. e pe planșele IE 07.x"""
    pl = _baza(m, cod, "SCHEMĂ MONOFILARĂ C.A.")
    for k in ("bara", "plecari", "jonctiune", "carcasa", "materiale", "rp", "ref_pe", "lista_pe", "tabel_pi"):
        if k in m:
            pl[k] = copy.deepcopy(m[k])
    intr = []
    for b in m.get("intrari") or []:
        nb = copy.deepcopy(b)
        ap = nb.get("aparate") or []
        i_inv = next((i for i, a in enumerate(ap) if a.get("tip") in ("invertor", "convertor_bess")), None)
        if i_inv is not None and not b.get("compact"):
            nb["aparate"] = ap[i_inv:]
            cs = _caseta_invertor(nb)
            if cs:
                nb["sursa"] = cs
            nb["cablu"] = {"ref": "", "cond": "c.c.", "text": "vezi IE 07.x"}
        elif b.get("compact"):
            cs = _caseta_invertor(nb)
            if cs:
                nb["sursa"] = dict(cs, sub=(b.get("sursa") or {}).get("sub", ""))
        intr.append(nb)
    pl["intrari"] = intr
    pl["note"] = [n for n in m.get("note") or [] if not n.startswith("0.")]
    # convenția proiectantului: lista de echipamente stă în memoriu / anexă, nu pe planșa c.a. (loc pentru tabelul PI)
    pl["lista_auto"] = False
    pl["note"].append(f"{len(pl['note']) + 1}. Lista de echipamente și materiale: planșa IE 08/FV și anexa .xlsx.")
    return pl


def _gaseste(m, pred):
    def walk(bs):
        for b in bs or []:
            for a in b.get("aparate") or []:
                if pred(a):
                    return a
            r = walk(b.get("copii"))
            if r is not None:
                return r
        return None
    jn = [m["jonctiune"]] if isinstance(m.get("jonctiune"), dict) else []
    return walk((m.get("intrari") or []) + (m.get("plecari") or []) + jn)


def plansa_releu(m, cod):
    """IE 09.1 — conexiunile releului de interfață: bara TEG → siguranțele circuitelor releului → releul PI (măsura
    L1–L3, N; alimentarea A1/A2 din UPS) → bobina de declanșare a întreruptorului de interfață; tabelul de reglaje"""
    qg = _gaseste(m, lambda a: a.get("ref") == "QG")
    if qg is None:
        return None
    pl = _baza(m, cod, "SCHEMĂ CONEXIUNI RELEU DE INTERFAȚĂ")
    pi = next((l for l in qg.get("laterale") or [] if l.get("eticheta") == "PI"), {})
    ups = next((l for l in qg.get("laterale") or [] if l.get("ref") == "UPS"), None)
    f_mas = {"tip": "mcb", "ref": "F-PI", "spec": ["3P · C6 · 6 kA", "măsură U / f releu"],
             "lista": ["Întreruptor automat modular 3P, curba C, In 6 A, 6 kA — circuitul de măsură al releului de interfață",
                       "L1, L2, L3 (+ N) → bornele de măsură ale releului"]}
    rel = {"tip": "cutie", "ref": "", "eticheta": "PI", "spec": list(pi.get("spec") or ["U / f"]),
           "lista": list(pi.get("lista") or ["Releu de protecție de interfață"]), "legatura": "masura"}
    lat = [rel]
    if ups:
        lat.append(dict(ups, legatura="forta"))
    q = copy.deepcopy(qg)
    q["laterale"] = [{"tip": "cutie", "eticheta": "BD", "spec": ["bobina de declanșare", "contact Y → BD"],
                      "legatura": "comanda", "buc": 0, "lista": list(pi.get("lista") or ["comanda PI"])}]
    pl["intrari"] = [{"sursa": {"titlu": "BARA TEG", "sub": "L1, L2, L3, N, PE · 3 × 400/230 V"},
                      "cablu": {"ref": "", "cond": "3 + N", "text": "conductoare 1,5 mm² Cu"},
                      "aparate": [dict(f_mas, laterale=lat)]}]
    pl["plecari"] = [{"aparate": [q], "cablu": {"ref": "", "cond": "", "text": ""},
                      "sarcina": {"titlu": "spre punctul de racord", "sub": "circuitul de forță — planșa IE 09/FV"}}]
    pl["bara"] = {"afisare": False}
    pl["carcasa"] = {"titlu": "TEG — TE INTERFAȚĂ", "sub": "releul de interfață și întreruptorul comandat"}
    if m.get("tabel_pi"):
        pl["tabel_pi"] = copy.deepcopy(m["tabel_pi"])
    pl["note"] = ["1. Releul de interfață măsoară tensiunea și frecvența pe bara TEG (L1, L2, L3, N) prin F-PI; "
                  "alimentarea auxiliară A1 / A2 230 V din UPS (funcționare la lipsa tensiunii rețelei).",
                  "2. Contactul de ieșire al releului comandă bobina de declanșare BD a întreruptorului de interfață "
                  "QG; contactul auxiliar al QG se readuce la intrarea de stare a releului.",
                  "3. Reglajele din tabel se confirmă / se înlocuiesc cu cele din ATR; reconectarea automată numai "
                  "după revenirea U, f în limite (temporizare).",
                  "4. Se citește împreună cu planșa IE 09/FV."]
    return pl


def plansa_smart_meter(m, cod):
    """IE 11 — smart meter-ul la punctul de racord (TC + SM + SmartLogger pe RS485)"""
    tcs = _gaseste(m, lambda a: a.get("ref") == "TCS" or any(l.get("ref") in ("SM", "SL") for l in a.get("laterale") or []))
    if tcs is None:
        return None
    pl = _baza(m, cod, "SCHEMĂ SMART METER ȘI MONITORIZARE")
    pl["intrari"] = [{"sursa": {"titlu": "PUNCTUL DE RACORD", "sub": "sosirea trafo / alimentarea TG existent"},
                      "cablu": {"ref": "", "cond": "3 + N + PE", "text": "existent"},
                      "aparate": [copy.deepcopy(tcs)]}]
    pl["plecari"] = [{"aparate": [], "cablu": {"ref": "", "cond": "", "text": "existent"},
                      "sarcina": {"titlu": "bara de racord", "sub": "planșa IE 09/FV"}}]
    pl["bara"] = {"afisare": False}
    pl["carcasa"] = None
    pl["note"] = ["1. Smart meter-ul măsoară schimbul total cu rețeaua la punctul de racord (TC cu raportul ales după "
                  "curentul nominal al racordului); datele merg pe RS485 la SmartLogger.",
                  "2. Magistrala RS485: cablu ecranat 2 × 2 × AWG24, înlănțuire invertoare → SmartLogger, ecranul legat "
                  "la pământ la un singur capăt, rezistență terminală 120 Ω la capete.",
                  "3. Se citește împreună cu planșa IE 09/FV."]
    return pl


TIPURI_FV = ("cef", "bess", "prosumator")


def are_fv(m):
    """echipa1 P0-4: pachetul „FV” (IE 07–09.1/FV, releu de interfață) există doar la CEF / BESS / prosumator"""
    tip = ((m or {}).get("calc") or {}).get("tip_schema")
    return tip in TIPURI_FV


def plansa_principala(m):
    """[(cod, model)] — pentru lucrările fără producție (casă, branșament, TG, PT, GE) pachetul conține doar planșa
    principală, în formatul ei (fără planșe FV / releu de interfață)"""
    cod = ((m.get("cartus") or {}).get("plansa") or "E01")
    pb = copy.deepcopy(m)
    pb.setdefault("materiale", [])
    return [(cod, pb)]


def planse_din_model(m, prefix="IE", sufix="FV"):
    """lista [(cod, model)] a planșelor A3 derivate din modelul calculat al CEF; pentru celelalte tipuri de lucrări —
    doar planșa principală (echipa1 P0-4)"""
    if not are_fv(m):
        return plansa_principala(m) if m.get("intrari") else []
    out = []
    k = 0
    for b in m.get("intrari") or []:
        if b.get("compact") or not any(a.get("tip") == "string_pv" for a in b.get("aparate") or []):
            continue
        k += 1
        cod = f"{prefix} 07.{k}/{sufix}"
        out.append((cod, plansa_cc(m, b, k, cod)))
    cod = f"{prefix} 08/{sufix}"
    pb = copy.deepcopy(m)
    pb.update(format="A3", auto_format=False, plansa_pachet=True)
    pb["cartus"] = dict(pb.get("cartus") or {}, plansa=cod, denumire1="SCHEMĂ BLOC C.C. ȘI C.A.")
    out.append((cod, pb))
    cod = f"{prefix} 09/{sufix}"
    out.append((cod, plansa_ca(m, cod)))
    for cod, f in ((f"{prefix} 09.1/{sufix}", plansa_releu), (f"{prefix} 11/{sufix}", plansa_smart_meter)):
        p = f(m, cod)
        if p is not None:
            out.append((cod, p))
    for _, p in out:
        p.setdefault("materiale", [])
    return out


def genereaza_planse(intrare, cartus=None):
    """intrarea fizică → [(cod, model)] (calculul o singură dată, planșele derivate)"""
    from . import constructor
    m, _ = constructor.genereaza(intrare, cartus=cartus)
    if not m.get("intrari"):
        return []
    return planse_din_model(m)


def nume_fisier(cod):
    return cod.replace(" ", "").replace("/", "-").replace(".", "_")


def pachet_planse_zip(planse, nume="planse", pdf=None):
    """ZIP cu planșele: SVG + DXF pe planșă, PDF multi-pagină (`pdf(svg_lista)` → bytes, opțional) și CUPRINS.txt"""
    import io, zipfile, tempfile, pathlib
    from . import layout, render_svg, render_dxf
    bio = io.BytesIO()
    svgs = []
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        cup = [f"Pachet de planșe A3 — {nume}", ""]
        for cod, mp in planse:
            c = layout.build(mp)
            svg = render_svg.render(c, cod)
            svgs.append((svg, c.w, c.h))
            fn = nume_fisier(cod)
            z.writestr(f"{fn}.svg", svg)
            with tempfile.TemporaryDirectory() as td:
                f = pathlib.Path(td) / "s.dxf"
                render_dxf.render(c, str(f))
                z.writestr(f"{fn}.dxf", f.read_bytes())
            cup.append(f"- {cod}: {(mp.get('cartus') or {}).get('denumire1', '')}")
        if pdf is not None:
            try:
                z.writestr(f"{nume}_planse.pdf", pdf(svgs))
                cup.append(f"- {nume}_planse.pdf: toate planșele, PDF multi-pagină A3")
            except RuntimeError as e:
                cup.append(f"- (PDF lipsă: {e})")
        z.writestr("CUPRINS.txt", "\n".join(cup))
    return bio.getvalue()


def html_multipagina(svgs):
    """HTML cu câte o pagină A3 pe planșă (pentru PDF-ul multi-pagină tipărit de Chrome)"""
    w, h = (svgs[0][1], svgs[0][2]) if svgs else (420, 297)
    pagini = "".join(f'<div class="p">{s}</div>' for s, _, _ in svgs)
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>@page{{size:{w}mm {h}mm;margin:0}}'
            f'html,body{{margin:0}}.p{{page-break-after:always;width:{w}mm;height:{h}mm;overflow:hidden}}'
            f'.p:last-child{{page-break-after:auto}}svg{{display:block}}</style></head><body>{pagini}</body></html>')
