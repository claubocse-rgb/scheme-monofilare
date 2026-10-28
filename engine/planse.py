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
    b = {k: copy.deepcopy(v) for k, v in m.items() if k in ("cartus", "calc", "calc_rezumat", "blocaj", "confirmari",
                                                             "revizii", "culori_faze", "orientare", "filigran")}
    b.update(format="A3", auto_format=False, lista_auto=True, legenda=True, plansa_pachet=True)
    b["cartus"] = dict(b.get("cartus") or {}, plansa=cod, denumire1=titlu)
    b["note"] = []
    return b


def _tabel_fisa(titlu, par, etichete):
    rand = [[e, _f(par.get(k), 2)] for k, e in etichete if par.get(k) not in (None, "")]
    return {"titlu": titlu, "coloane": ["Parametru", "Valoare"], "randuri": rand} if rand else None


def _e_cc(a):
    return a.get("tip") in ("string_pv", "gpv", "separator_cc", "invertor", "nod", "baterie", "convertor_bess")


def plansa_cc(m, b, k, cod, tipic=None):
    """IE 07.k — partea de c.c. a invertorului desenat complet în intrarea `b` (câmp PV → invertor) până la cablul c.a.
    E2: cu stringurile descrise (module / string, stringuri / MPPT) planșa se desenează direct — fiecare „SIR k”,
    gPV pe string, separatorul pe MPPT, intrările MPPT pe conturul invertorului; `tipic` = {titlu, mentiune, refs}
    pentru invertoarele identice desenate o singură dată."""
    tit = (b.get('sursa') or {}).get('titlu', '')
    if tipic:
        tit = f"TIPIC {tipic['titlu']}"
    pl = _baza(m, cod, f"SCHEMĂ BLOC C.C. — {tit}")
    pl["orientare"] = "clasic"          # blocul c.c. generic: câmpul PV sus (desenul direct curge stânga → dreapta)
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
    if tipic:
        pl["note"].append(f"4. Schemă tipică pentru {tipic['titlu']} ({len(tipic['refs'])} invertoare identice: câmp PV, "
                          "stringuri, protecții c.c.); fiecare invertor apare cu eticheta lui pe planșa IE 09/FV.")
    from . import desen_e2
    ds = desen_e2.date_stringuri(b, tipic)
    if ds:
        pl["desen_special"] = {"tip": "stringuri", "date": ds}
        pl["lista_auto"] = False           # convenția proiectantului: fișele pe planșă, lista în memoriu / anexă
        pl["note"].append(f"{len(pl['note']) + 1}. Lista de echipamente și materiale: planșa IE 08/FV și anexa .xlsx.")
    return pl


def _cheie_identic(b):
    """amprenta ramurii unui invertor fără notații (ref) — invertoarele cu aceeași amprentă sunt identice"""
    import json

    def curat(o):
        if isinstance(o, dict):
            return {k: curat(v) for k, v in o.items() if k not in ("ref", "_uid", "titlu")}
        if isinstance(o, list):
            return [curat(v) for v in o]
        return o
    ap = []
    for a in b.get("aparate") or []:
        if not _e_cc(a):
            break
        ap.append(curat(a))
    return json.dumps([ap, curat(b.get("cablu") or {}), (b.get("sursa") or {}).get("sub", "")], sort_keys=True,
                      ensure_ascii=False, default=str)


def _ref_inv(b):
    return next((a.get("ref", "") for a in b.get("aparate") or [] if a.get("tip") == "invertor"), "")


def prag_tipic(m):
    """E2 (#7): de la câte invertoare identice IE 07 se desenează o singură dată („tipic pentru INV-1 … INV-N”);
    `tipic_invertoare`: true / false / număr (implicit 6), în model sau în intrarea de calcul"""
    v = m.get("tipic_invertoare", (m.get("calc") or {}).get("tipic_invertoare"))
    if v is False or v == 0:
        return None
    if v is True:
        return 2
    if isinstance(v, (int, float)) and v >= 2:
        return int(v)
    return 6


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
    # E2 (#1): la CEF, TE de interfață (TE-CEF / TEG) se desenează multifilar — conductoarele L1 / L2 / L3 / N / PE
    # colorate, QG motorizat cu bobina, releul PI cu bornele lui, UPS-ul, TC-urile; plecările și fiecare invertor
    from . import desen_e2
    if ((m.get("calc") or {}).get("tip_schema") == "cef" and m.get("multifilar_te", True) is not False):
        dt = desen_e2.date_te(m)
        if dt and dt.get("pi") and not dt.get("mono"):
            pl["desen_special"] = {"tip": "te_multifilar", "date": dt, "culori_faze": m.get("culori_faze")}
            pl["note"].append(f"{len(pl['note']) + 1}. TE de interfață desenat multifilar: conductoarele L1 / L2 / "
                              "L3 maro / negru / gri, N albastru, PE verde-galben (SR EN 60445); comanda releului "
                              "în roșu, comunicația RS485 în cyan.")
    return pl


def plansa_curbe(m, cod):
    """E2 (#6): IE 10 — curbele timp-curent ale protecțiilor înseriate (selectivitate vizuală)"""
    from . import desen_e2
    dc = desen_e2.date_curbe(m)
    if not dc or len(dc.get("curbe") or []) < 2:
        return None
    pl = _baza(m, cod, "CURBE TIMP-CURENT — SELECTIVITATE")
    pl.update(lista_auto=False, legenda=False, desen_special={"tip": "curbe", "date": dc}, intrari=[], plecari=[],
              bara={"afisare": False}, carcasa=None, orientare="clasic")
    pl["note"] = ["1. Caracteristicile de declanșare ale protecțiilor înseriate pe calea cea mai încărcată (de la "
                  "invertor / plecare spre punctul de racord); selectivitatea e asigurată acolo unde curbele nu se "
                  "intersectează până la curentul de scurtcircuit maxim.",
                  "2. Curbe orientative; reglajele finale se verifică pe curbele producătorului aparatelor alese "
                  "și se trec în fișa de reglaje la PIF.",
                  "3. Se citește împreună cu planșa IE 09/FV și cu memoriul de calcul (V41 / V42)."]
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
    pl["orientare"] = "clasic"          # intrarea e chiar punctul de racord (sus)
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
    ramuri = [b for b in m.get("intrari") or []
              if not b.get("compact") and any(a.get("tip") == "string_pv" for a in b.get("aparate") or [])]
    prag = prag_tipic(m)
    grupe = {}
    for b in ramuri:
        grupe.setdefault(_cheie_identic(b), []).append(b)
    facut = set()

    def idem(ref):
        """invertoarele desenate compact („idem INV-k”) de constructor — identice cu INV-k"""
        out_ = []
        for x in m.get("intrari") or []:
            if not x.get("compact"):
                continue
            txt = " ".join(" ".join(a.get("spec") or []) for a in x.get("aparate") or []) + " " + \
                (x.get("cablu_ca") or {}).get("text", "") + " " + (x.get("sursa") or {}).get("sub", "")
            if f"idem {ref}" in txt.split(" · ") or txt.rstrip().endswith(f"idem {ref}") or f"idem {ref} " in txt + " ":
                r_ = _ref_inv(x)
                if r_:
                    out_.append(r_)
        return out_
    for b in ramuri:
        g = grupe[_cheie_identic(b)]
        tipic = None
        refs = [_ref_inv(x) for x in g]
        refs += [r_ for x in g for r_ in idem(_ref_inv(x)) if r_ not in refs]
        if prag and len(refs) >= prag:
            if id(g[0]) in facut:
                continue
            facut.add(id(g[0]))
            tit = f"{refs[0]} … {refs[-1]}" if len(refs) > 2 else ", ".join(refs)
            tipic = {"titlu": tit, "refs": refs, "mentiune": f"TIPIC PENTRU {tit} ({len(refs)} invertoare identice)"}
        k += 1
        cod = f"{prefix} 07.{k}/{sufix}"
        out.append((cod, plansa_cc(m, b, k, cod, tipic)))
    cod = f"{prefix} 08/{sufix}"
    pb = copy.deepcopy(m)
    pb.update(format="A3", auto_format=False, plansa_pachet=True)
    pb["cartus"] = dict(pb.get("cartus") or {}, plansa=cod, denumire1="SCHEMĂ BLOC C.C. ȘI C.A.")
    if pb.get("tabel_pi"):
        # convenția proiectantului (#11): tabelul PI stă pe planșa c.a. (IE 09) și pe cea a releului (IE 09.1)
        pb["tabel_pi"] = None
        pb["note"] = list(pb.get("note") or []) + [
            f"{len(pb.get('note') or []) + 1}. Parametrii și protecțiile invertoarelor / PI: planșele {prefix} 09/{sufix} "
            f"și {prefix} 09.1/{sufix}."]
    out.append((cod, pb))
    cod = f"{prefix} 09/{sufix}"
    out.append((cod, plansa_ca(m, cod)))
    for cod, f in ((f"{prefix} 09.1/{sufix}", plansa_releu), (f"{prefix} 10/{sufix}", plansa_curbe),
                   (f"{prefix} 11/{sufix}", plansa_smart_meter)):
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


def pachet_planse_zip(planse, nume="planse", pdf=None, model=None, etichete=True):
    """ZIP cu planșele: SVG + DXF pe planșă, PDF multi-pagină (`pdf(svg_lista)` → bytes, opțional) și CUPRINS.txt;
    E2: + etichetele tablourilor (A4, SVG + PDF) și schema de ușă a fiecărui tablou (A4, SVG)"""
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
        if etichete and planse:
            mm = model or next((mp for cod, mp in planse if "08/" in cod), planse[0][1])
            try:
                et = etichete_tablou(mm)
                for i, (svg, _, _) in enumerate(et):
                    z.writestr(f"ETICHETE_tablou_{i + 1}.svg", svg)
                if et:
                    cup.append(f"- ETICHETE_tablou_*.svg: {len(et)} pagini A4 cu etichetele circuitelor (bandă DIN 18 mm)")
                    if pdf is not None:
                        try:
                            z.writestr(f"{nume}_etichete.pdf", pdf(et))
                            cup.append(f"- {nume}_etichete.pdf: etichetele, A4")
                        except RuntimeError:
                            pass
                for nt, mu in scheme_usa(mm):
                    c = layout.build(mu)
                    z.writestr(f"USA_{nume_fisier(nt)}.svg", render_svg.render(c, f"Schemă tablou {nt}"))
                    cup.append(f"- USA_{nume_fisier(nt)}.svg: schema compactă a tabloului {nt} (A4, pentru ușă)")
            except Exception as e:      # noqa: BLE001 — anexele nu opresc pachetul de planșe
                cup.append(f"- (etichete / schemă de ușă: {e})")
        z.writestr("CUPRINS.txt", "\n".join(cup))
    return bio.getvalue()


def html_multipagina(svgs):
    """HTML cu câte o pagină A3 pe planșă (pentru PDF-ul multi-pagină tipărit de Chrome)"""
    w, h = (svgs[0][1], svgs[0][2]) if svgs else (420, 297)
    pagini = "".join(f'<div class="p">{s}</div>' for s, _, _ in svgs)
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>@page{{size:{w}mm {h}mm;margin:0}}'
            f'html,body{{margin:0}}.p{{page-break-after:always;width:{w}mm;height:{h}mm;overflow:hidden}}'
            f'.p:last-child{{page-break-after:auto}}svg{{display:block}}</style></head><body>{pagini}</body></html>')


# ================================================================ E2 (#4): etichete de tablou și schema de pe ușa tabloului
DIN_TIP = ("mcb", "rcbo", "rccb", "mccb_dif", "sep_fuzibil", "fuzibil", "separator", "mccb", "contact")


def _den_plecare(b):
    s = (b.get("sarcina") or {}).get("titlu") or ""
    return s


def tablouri_model(m):
    """tablourile modelului cu aparatele lor (pentru etichete și schema de ușă):
    [{nume, etichete: [...], model: submodelul tabloului pentru schema de ușă}]"""
    from . import layout, desen_e2
    out = []
    car = m.get("carcasa") or {}
    nume_p = car.get("titlu") or ((m.get("cartus") or {}).get("denumire2") or "TG")
    et = []
    intr_usa = []
    for b in m.get("intrari") or []:
        afara, inauntru = layout._split_intrare(b, bool(car))
        sursa = (b.get("sursa") or {}).get("titlu") or "sosire"
        inv = next((a.get("ref") for a in afara if a.get("tip") in ("invertor", "convertor_bess", "generator")), None)
        den = inv or sursa
        for a in inauntru:
            if a.get("tip") in DIN_TIP:
                et.append(desen_e2.eticheta_circuit(a, den if len(m.get("intrari") or []) > 1 else "GENERAL / " + den))
        if inauntru:
            intr_usa.append({"sursa": {"titlu": den, "sub": (b.get("cablu_ca") or b.get("cablu") or {}).get("text", "")},
                             "cablu": {}, "aparate": copy.deepcopy(inauntru)})
    for l in (m.get("bara") or {}).get("laterale") or []:
        if l.get("tip") == "spd":
            et.append(desen_e2.eticheta_circuit(l, "SPD bare"))
    pl_usa, secundare = [], []

    def plecare(b, et_, lst, parinte):
        den = _den_plecare(b) or (", ".join(_den_plecare(ch) for ch in b.get("copii") or [] if _den_plecare(ch))
                                  if b.get("grup") else "") or "plecare"
        aps = [a for a in b.get("aparate") or [] if not a.get("jos")]
        for a in aps:
            if a.get("tip") in DIN_TIP:
                et_.append(desen_e2.eticheta_circuit(a, den))
        nb = {k: copy.deepcopy(v) for k, v in b.items() if k not in ("copii", "aparate")}
        nb["aparate"] = copy.deepcopy(aps)
        if b.get("copii") and b.get("grup"):
            nb["copii"] = []
            for ch in b["copii"]:
                plecare(ch, et_, nb["copii"], parinte)
        elif b.get("copii"):
            secundare.append((b, parinte))
        lst.append(nb)
    for b in m.get("plecari") or []:
        plecare(b, et, pl_usa, nume_p)
    sub = {k: copy.deepcopy(v) for k, v in m.items() if k in ("cartus", "calc", "revizii", "bara", "carcasa", "filigran")}
    if isinstance(sub.get("bara"), dict):
        sub["bara"].pop("sectiuni", None)
    sub.update(intrari=intr_usa, plecari=pl_usa)
    out.append({"nume": nume_p, "etichete": et, "model": sub})
    for b, parinte in secundare:
        nume = (b.get("sarcina") or {}).get("titlu") or "TD"
        et2, pl2 = [], []
        for a in b.get("aparate_tablou") or []:
            if a.get("tip") in DIN_TIP:
                et2.append(desen_e2.eticheta_circuit(a, "GENERAL"))
        for ch in b.get("copii") or []:
            plecare(ch, et2, pl2, nume)
        sm = {k: copy.deepcopy(v) for k, v in m.items() if k in ("cartus", "calc", "revizii", "filigran")}
        sm.update(carcasa={"titlu": nume, "sub": (b.get("sarcina") or {}).get("sub", "")},
                  intrari=[{"sursa": {"titlu": f"din {parinte}", "sub": (b.get("cablu") or {}).get("text", "")},
                            "cablu": {}, "aparate": copy.deepcopy(b.get("aparate_tablou") or [])}],
                  bara={"afisare": True, "forteaza": True}, plecari=pl2)
        out.append({"nume": nume, "etichete": et2, "model": sm})
    jn = m.get("jonctiune") if isinstance(m.get("jonctiune"), dict) else None
    if jn:
        nume = (jn.get("carcasa") or {}).get("titlu") or "TEG"
        et3 = [desen_e2.eticheta_circuit(a, "GENERAL / racord") for a in jn.get("aparate") or [] if a.get("tip") in DIN_TIP]
        sect = (m.get("bara") or {}).get("sectiuni") or []
        for k_, b in enumerate(m.get("plecari") or []):
            dest = (sect[k_].get("titlu") if k_ < len(sect) and isinstance(sect[k_], dict) else "") or "plecare"
            for a in b.get("aparate") or []:
                if a.get("jos") and a.get("tip") in DIN_TIP:
                    et3.append(desen_e2.eticheta_circuit(a, f"spre {dest}"))
        out.append({"nume": nume, "etichete": et3, "model": None})
    return out


def _antet(m):
    k = m.get("cartus") or {}
    from .layout import rev_curenta
    return " · ".join(x for x in (k.get("titlu") or k.get("denumire2") or "", (f"nr. {k['nr_pr']}" if k.get("nr_pr") else ""),
                                   f"rev. {rev_curenta(m)}") if x)


def etichete_tablou(m):
    """E2 (#4): paginile A4 cu etichetele circuitelor (cod, denumire, calibru, IΔn) — [(svg, w, h)]"""
    from . import desen_e2, render_svg
    tab = [t for t in tablouri_model(m) if t["etichete"]]
    out = []
    for i, cv in enumerate(desen_e2.pagini_etichete(tab, _antet(m), m.get("filigran"))):
        out.append((render_svg.render(cv, f"Etichete tablou {i + 1}"), cv.w, cv.h))
    return out


def model_usa_tablou(m, sub, nume):
    """modelul paginii „schemă de tablou” (A4, compactă, pentru ușa tabloului): monofilara tabloului fără listă,
    legendă și note, cu un antet mic în locul cartușului"""
    mm = copy.deepcopy(sub)
    mm.update(format="A4", auto_format=False, lista_auto=False, legenda=False, note=[], cartus_mini=True,
              orientare="clasic", tabel_pi=None)
    mm["cartus"] = dict(mm.get("cartus") or {}, denumire1=f"SCHEMĂ TABLOU {nume}")
    for b in mm.get("plecari") or []:
        b.pop("jonctiune", None)
    return mm


def scheme_usa(m):
    """[(nume, model)] — câte o pagină A4 „schemă de tablou” pentru fiecare tablou cu aparate"""
    out = []
    for t in tablouri_model(m):
        if t.get("model") and (t["model"].get("plecari") or t["model"].get("intrari")):
            out.append((t["nume"], model_usa_tablou(m, t["model"], t["nume"])))
    return out
