"""Validarea modelului înainte de previzualizare / export (SPEC §D: BLOCANT = exportul este refuzat).

Două moduri:
* model CALCULAT (`model["calc"]` = intrarea fizică): desenul, textele, lista de echipamente și notele generate se reconstruiesc
  ÎNTOTDEAUNA din calcul (`pregateste`), deci nu pot contrazice dimensionarea. Se păstrează doar cartușul, formatul planșei
  și notele suplimentare scrise de utilizator (`note_manuale`).
* model MANUAL (fără `calc`): se desenează așa cum e, dar dimensionarea nu e verificată → AVERTISMENT V00 și o notă pe
  planșă („schemă nevalidată”). Topologia (V57/V82/V83) se verifică în ambele moduri.
"""
import copy, re

from . import constructor, layout, topologie
from .calc import calculeaza

NOTA_MANUAL = ("ATENȚIE: schemă desenată manual — dimensionarea cablurilor, reglajele protecțiilor, scurtcircuitul și "
               "selectivitatea NU au fost verificate de aplicație.")
CHEI_PLANSA = ("format", "auto_format", "lista_auto", "legenda", "titlu_lista", "abrevieri", "note_manuale", "deviz", "confirmari", "_doc")


def _fara_interne(o):
    if isinstance(o, dict):
        return {k: _fara_interne(v) for k, v in o.items() if not k.startswith("_")}
    if isinstance(o, list):
        return [_fara_interne(v) for v in o]
    return o


def _copiaza_uid(src, dst):
    """modelul regenerat din calcul are aceeași structură ca cel din interfață → se preiau cheile _uid/_k pe poziție
    (legătura planșă ↔ formular din interfață)"""
    if isinstance(src, dict) and isinstance(dst, dict):
        for k in ("_uid", "_k"):
            if k in src and k not in dst:
                dst[k] = src[k]
        for k, v in dst.items():
            if k in src and not k.startswith("_"):
                _copiaza_uid(src[k], v)
    elif isinstance(src, list) and isinstance(dst, list):
        for a, b in zip(src, dst):
            _copiaza_uid(a, b)


def pregateste(model, pentru_export=False):
    """modelul gata de desenat + rezultatul calculului (sau None pentru modelele manuale)"""
    if model.get("calc"):
        m, r = constructor.genereaza(model["calc"], pastreaza=model)
        for k in CHEI_PLANSA:
            if k in model:
                m[k] = copy.deepcopy(model[k])
        if not pentru_export:
            _copiaza_uid(model, m)
        if model.get("note_manuale"):
            n0 = len(m.get("note") or [])
            m["note"] = (m.get("note") or []) + [f"{n0 + i + 1}. {t}" for i, t in enumerate(model["note_manuale"])]
        return (_fara_interne(m) if pentru_export else m), r
    m = copy.deepcopy(model)
    if pentru_export:
        m = _fara_interne(m)
        note = list(m.get("note") or [])
        if NOTA_MANUAL not in note:
            m["note"] = [NOTA_MANUAL] + note
    return m, None


_NR_A = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:\u00a0)?A\b")


def _numere_A(texte):
    return {float(x.replace(",", ".")) for t in texte for x in _NR_A.findall(t or "")}


_PROT_SABLON = {"mcb": "MCB", "mccb": "MCCB", "acb": "ACB", "sep_sig": "gG", "sf": "gG", "rcbo": "MCB"}


_TIP_PROT = {"mcb": "mcb", "mccb": "mccb", "acb": "acb", "sep_fuzibil": "sep_sig", "fuzibil": "sep_sig", "rcbo": "rcbo", "mccb_dif": "mccb"}


def _n(t):
    return " ".join(str(t or "").replace("\u00a0", " ").replace("\u202f", " ").split())


def _cablu_din_text(t):
    """„ACYABY 4×16 mm²”, „2 × (CYABY 5×95 mm² …)”, „4 x 16 mmp Al”, „N2XY 4×1×16” → parametri pentru verifica_cablu
    (None dacă secțiunea nu se poate citi). Izolația și pozarea se deduc din denumire: 2X / XLPE → XLPE, altfel PVC;
    cablu armat (…ABY / …A2Y) → îngropat (D1), altfel pe perete (C). Aluminiu: denumirea începe cu A sau textul spune „Al”."""
    t = _n(t).replace("mmp", "mm²").replace(" x ", "×").replace("x", "×")
    n = 1
    mp = re.match(r"^\s*(\d+)\s*×\s*\(", t)
    if mp:
        n = int(mp.group(1))
    tip = (re.search(r"\b([A-Z][A-Z0-9-]{2,})\b", t) or [None, ""])[1] if re.search(r"\b([A-Z][A-Z0-9-]{2,})\b", t) else ""
    ms = re.search(r"(\d)\s*×\s*(?:1\s*×\s*)?(\d+(?:[.,]\d+)?)", t) or re.search(r"(\d+(?:[.,]\d+)?)\s*mm²", t)
    if not ms:
        return None
    S = float((ms.group(2) if ms.lastindex == 2 else ms.group(1)).replace(",", "."))
    al = (tip.startswith("A") and not tip.startswith("AF")) or bool(re.search(r"\bAl\b", t))
    xlpe = "2X" in tip or "XLPE" in t.upper()
    armat = tip.endswith("ABY") or tip.endswith("A2Y") or "ABY" in tip
    nc = int(ms.group(1)) if ms.lastindex == 2 else 4
    return {"material": "Al" if al else "Cu", "izolatie": "XLPE" if xlpe else "PVC", "metoda": "D1" if armat else "C",
            "S_faza_mm2": S, "n_paralel": n, "retea": "mono" if nc in (2, 3) and S < 16 else "tri"}


def _consistenta_manual(m):
    """model desenat manual: ce scrie pe desen trebuie să coincidă cu lista de echipamente (V80) și, unde există
    parametri fizici, cu textele generate din ei; protecția nu poate depăși Iz' al cablului cu parametri (V02)"""
    from .calc import text_lista, text_desen
    from .calc import verifica_cablu
    out = []
    prot_curenta = [None]
    def r_(cod, ob, mesaj, rem):
        out.append({"cod": cod, "nivel": "BLOCANT", "obiect": ob, "mesaj": mesaj, "remediere": rem})
    def br(b, cale):
        cab = (b.get("cablu") or {}).get("param") or {}
        for key in ("cablu", "cablu_ca"):
            cb = b.get(key) or {}
            cp = cb.get("param") or {}
            if cp.get("S_faza_mm2"):
                from .calc.texte import text_cablu
                t = text_cablu(cp.get("material"), cp.get("izolatie"), cp.get("metoda"), cp.get("n_paralel") or 1, cp.get("S_faza_mm2"),
                               cp.get("S_N_mm2"), cp.get("S_PE_mm2"), cp.get("PE") or "cablu", cp.get("retea", "tri"))
                if _n(t) not in _n(cb.get("text") or ""):
                    r_("V80", cb.get("ref") or cale, f"{cb.get('ref') or 'cablu'}: textul de pe desen „{cb.get('text')}” ≠ cablul dimensionat „{t}”",
                       "corectați cablul din tab-ul Calcul")
        for a in b.get("aparate") or []:
            ref = a.get("ref") or a.get("tip", "")
            par = a.get("param") or {}
            if par.get("sablon"):
                p = {k: v for k, v in par.items() if k != "sablon"}
                try:
                    den, _ = text_lista(par["sablon"], p)
                    if _n((a.get("lista") or [""])[0]) != _n(den):
                        r_("V80", ref, f"{ref}: lista „{(a.get('lista') or [''])[0]}” ≠ parametri „{den}”", "regenerați lista din parametri")
                    if par["sablon"] not in ("contor", "dpst") and [_n(x) for x in a.get("spec") or []] != [_n(x) for x in text_desen(par["sablon"], p)]:
                        r_("V80", ref, f"{ref}: desenul „{' · '.join(a.get('spec') or [])}” ≠ parametri „{' · '.join(text_desen(par['sablon'], p))}”",
                           "corectați aparatul din tab-ul Calcul")
                except Exception as e:
                    r_("V80", ref, f"{ref}: parametri incompleți ({e})", "completați parametrii")
                if par["sablon"] in _PROT_SABLON:
                    prot_curenta[0] = (ref, par)
            else:
                tp = _TIP_PROT.get(a.get("tip"))
                if tp:      # protecție scrisă de mână: calibrul = primul curent de pe desen
                    nums = [float(x.replace(",", ".")) for x in _NR_A.findall(" ".join(a.get("spec") or []))]
                    if nums:
                        cb = re.search(r"\b([BCD])\s?(\d+)", " ".join(a.get("spec") or []))
                        prot_curenta[0] = (ref, {"sablon": tp, "In_A": nums[0], "curba": cb.group(1) if cb else "C"})
                ns, nl = _numere_A(a.get("spec") or []), _numere_A(a.get("lista") or [])
                if ns and nl and not (ns & nl):
                    r_("V80", ref, f"{ref}: valorile de pe desen ({', '.join(a.get('spec') or [])}) nu apar în lista de echipamente",
                       "aduceți desenul și lista la aceleași valori")
        # cablul ramurii e protejat de ultima protecție dinaintea lui (din ramură sau din amonte)
        for key in ("cablu_ca", "cablu"):
            cp = (b.get(key) or {}).get("param") or {}
            if cp.get("S_faza_mm2") and prot_curenta[0]:
                pref, pp = prot_curenta[0]
                prot = {"tip": _PROT_SABLON[pp["sablon"]], "In_A": pp.get("In_A"), "Ir_A": pp.get("Ir_A"), "curba": pp.get("curba")}
                for v in verifica_cablu(cp, prot, f"{(b.get(key) or {}).get('ref') or 'cablu'} ({pref})"):
                    if v.get("nivel") == "BLOCANT":
                        out.append(v)
            cb = b.get(key) or {}
            if not cp.get("S_faza_mm2") and cb.get("text") and prot_curenta[0]:
                # cablu scris de mână (fără parametri): se citește secțiunea din text și se verifică în ipoteza cea mai
                # probabilă din denumirea cablului (material, izolație, armare → pozare); se blochează dacă nu rezistă
                cp2 = _cablu_din_text(cb["text"])
                if cp2:
                    pref, pp = prot_curenta[0]
                    prot = {"tip": _PROT_SABLON[pp["sablon"]], "In_A": pp.get("In_A"), "Ir_A": pp.get("Ir_A"), "curba": pp.get("curba")}
                    for v in verifica_cablu(cp2, prot, f"{cb.get('ref') or 'cablu'} ({pref}, citit din text)"):
                        if v.get("nivel") == "BLOCANT" and v.get("cod") in ("V02", "V03"):
                            out.append(v)
        amonte = prot_curenta[0]
        for i, c in enumerate(b.get("copii") or []):
            prot_curenta[0] = amonte
            br(c, f"{cale}.{i + 1}")
        prot_curenta[0] = amonte
    intrari = m.get("intrari") or []
    for i, b in enumerate(intrari):
        prot_curenta[0] = None
        br(b, f"i{i}")
    prot_in = prot_curenta[0] if len(intrari) == 1 else None    # protecția de intrare protejează plecările fără protecție proprie
    for i, b in enumerate(m.get("plecari") or []):
        prot_curenta[0] = prot_in
        br(b, f"p{i}")
    return out


def valideaza(model):
    """{blocheaza, verificari, info, presupus, ipoteze, calculat} — verificările BLOCANT + AVERTISMENT ale calculului
    și ale topologiei desenului"""
    m, r = pregateste(model)
    ver, info, presupus, ipoteze = [], [], [], []
    if r is not None:
        ver += r.get("verificari") or []
        info += r.get("info") or []
        presupus = r.get("presupus") or []
        ipoteze = r.get("ipoteze") or []
    else:
        ver.append({"cod": "V00", "nivel": "AVERTISMENT", "obiect": "schema",
                    "mesaj": "Schemă desenată manual: dimensionarea nu este verificată de aplicație.",
                    "remediere": "Generează schema din tab-ul Calcul (sau din „Schemă nouă”) ca să fie dimensionată și verificată."})
        ver += _consistenta_manual(m)
    try:
        cv = layout.build(m)
        ver += topologie.verifica_topologie(m, cv)
        sc = (cv.meta or {}).get("scara") or 1
        if sc < 0.6 and (m.get("plecari") or []):
            # textul de bază (2,1–2,8 mm) ajunge sub ~1,3 mm la mărimea reală a formatului
            fmt_ = "A1" if cv.w > 800 else "A2" if cv.w > 500 else "A3"
            ver.append({"cod": "V95", "nivel": "AVERTISMENT", "obiect": "planșa",
                        "mesaj": f"planșa e greu lizibilă: schema e redusă la {round(sc * 100)} % pe {fmt_} (text ≈ {sc * 2.1:.1f} mm)",
                        "remediere": "împarte tabloul (ex. un tablou secundar pe etaj, pe planșă separată) sau grupează circuitele"})
    except Exception as e:
        ver.append({"cod": "V00", "nivel": "BLOCANT", "obiect": "schema", "mesaj": f"desenul nu poate fi generat: {e}",
                    "remediere": "corectați datele"})
    blocheaza = any(v.get("nivel") == "BLOCANT" for v in ver)
    from .calc.verificari import completeaza_remedieri
    completeaza_remedieri(ver)            # r10: orice BLOCANT are remediere textuală
    return {"blocheaza": blocheaza, "verificari": ver, "info": info, "presupus": presupus, "ipoteze": ipoteze,
            "calculat": r is not None, "rezultat": (r or {}).get("rezultat")}
