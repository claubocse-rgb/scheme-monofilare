"""r10: rescrierile pe CLASE de formulări din runda 10 (teste/r10), înainte de regulile interpretorului.
Lungimea NU se păstrează — fiecare rescriere lasă o notă („Am presupus”).

`rescrie_inainte` rulează înaintea autocorecturilor r9 (interp_rescriere.rescrie_autocorectura):
  * autocorecturi formulate altfel: „(400 kW, nu 300)”, „nu 400, ci 630 kVA”, „Corectez: …” la început, „rectific”,
    „mai exact”, „scuze, sunt 3 x SG30CX, deci 90 kW” (suma de control după corectură se aplică totalului);
  * „N invertoare (Huawei 100 kW și Sungrow 110 kW)” — lista din paranteză are prioritate (1 + 1, nu N × P1 + P2);
  * suma de control în paranteză: „2 invertoare Symo 20.0-3-M (40 kW existenți)” — nu e Pn per invertor;
  * ATR: „ATR permite doar 800 kW evacuare” = puterea aprobată de evacuare;
  * engleză: „existing LV switchboard / board / MDB” = TG existent;
  * cantități vs puteri: „8 circ prize 6 ilum”, „5 prize 3 lumini” = N circuite (nu „prize 6 kW”);
    „2 pompe 11 kW (1+1 rezervă)”, „1 pompă 7,5 kW + 1 de rezervă” = activ + rezervă; „interblocaj 2 din 3” (text);
  * cuvinte care nu sunt ce par: „pt uscat 630” = PT; „18/30 kV” = izolația cablului MT (nu tensiunea rețelei);
    „TG cu Q 3x32A” = Q-ul branșamentului (nu plecări); „PTA … pe stâlp”.
"""
from __future__ import annotations

import re

NUM = r"\d+(?:[.,]\d+)?"
_DIA = str.maketrans("șşțţăâîȘŞȚŢĂÂÎ", "ssttaaiSSTTAAI")
_NUMERAL = {"un": 1, "o": 1, "una": 1, "doua": 2, "doi": 2, "trei": 3, "patru": 4, "cinci": 5}


def _n(t: str) -> str:
    return t.translate(_DIA).lower()


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _f(x: float) -> str:
    return (f"{x:.3f}".rstrip("0").rstrip(".")).replace(".", ",")


def _sub(text: str, rx, rep, note: list, nota=None):
    """re.sub pe textul fără diacritice (pozițiile coincid: traducerea diacriticelor păstrează lungimea)"""
    out, last = [], 0
    for m in rx.finditer(_n(text)):
        r = rep(m, text) if callable(rep) else rep
        if r is None:
            continue
        out.append(text[last:m.start()])
        out.append(r)
        last = m.end()
        if nota:
            note.append(nota.format(text[m.start():m.end()].strip()))
    if not out:
        return text
    out.append(text[last:])
    return "".join(out)


# ------------------------------------------------------------------------------------------------- autocorecturi
_U = r"(?:kwp|kwh|kva|kvar|kw|mw|mva|a|m|kv)"
RE_PAR_NU = re.compile(rf"\(\s*(?P<x>{NUM}\s*{_U}?)\s*,\s*(?:si\s+)?nu\s+(?:de\s+)?{NUM}\s*{_U}?\s*\)")
RE_NU_CI = re.compile(rf"\bnu\s+(?:e\s+|este\s+|sunt\s+)?(?:de\s+)?(?P<a>{NUM})\s*(?P<ua>{_U})?\s*,?\s*(?:ci|ba|ci\s+de|ci\s+e)\s+"
                      rf"(?P<b>{NUM})\s*(?P<ub>{_U})\b")
RE_CORECTEZ_INCEPUT = re.compile(r"^\s*(?:corectez|corectie|rectific\w*|erata|revin)\s*[:,]?\s*")
RE_MARCATORI_NOI = re.compile(r"(?:(?<=[\s,.;:!])|^)(?:rectific(?:a|am|are)?|mai\s+exact|ma\s+corectez|am\s+gresit\s+(?:mai\s+sus|cifra|valoarea)"
                              r"|greseala\s+mea|de\s+fapt\s+sunt|scuze\s*,?\s+sunt|pardon\s*,?\s+sunt)\b\s*[,:]?")
RE_DECI_TOTAL = re.compile(rf"(?P<cap>\b(?:cef|centrala|centrala\s+fotovoltaica|prosumator|parc)\s+)(?P<v>{NUM})\s*kw\b"
                           rf"(?P<mid>[^;]{{0,90}}?)[,;.]?\s*(?:deci|adica|in\s+total)\s+(?P<t>{NUM})\s*kw\b")


RE_NU_E = re.compile(rf"(?:[.;,]\s*)?(?:(?:corecti\w*|corectez|rectific\w*|scuze|pardon)\s*[:,]?\s*)?(?P<rec>[a-z]{{2,}})\s+nu\s+(?:e|este|are)\s+"
                     rf"(?:de\s+)?(?P<a>{NUM})\s*(?P<u>kw|kva|a)\b\s*,\s*(?:ci\s+)?(?:(?:e|este|are)\s+)?(?:de\s+)?(?P<b>{NUM})\s*(?P=u)\b"
                     rf"(?P<tail>(?:\s+(?:mono|tri)\w*)?)(?:\s*[;,.]?\s*(?:restul|in\s+rest)\s+(?:ramane|e\s+la\s+fel|neschimbat)\w*)?")
RE_INTREB_NU = re.compile(rf"(?P<old>{NUM})\s*kw(?:\s+[a-z]+)?\s*\?+\s*nu\s*[,:]\s*")


def _nu_e(text, note):
    """„VE 11 kW … corecție: VE nu e 11 kW, e 7,4 kW monofazat; restul rămâne” → „VE 7,4 kW monofazat” (o singură dată);
    „pompa 16 kW electric? nu, 16 kW termic, 4,5 kW electric” → valoarea dinaintea întrebării dispare."""
    t = text
    for _ in range(3):
        n = _n(t)
        m = RE_NU_E.search(n)
        if not m:
            break
        rec, a, u = m.group("rec"), m.group("a"), m.group("u")
        nou = f"{m.group('b')} {t[m.start('u'):m.end('u')]}{t[m.start('tail'):m.end('tail')]}"
        vechi = list(re.finditer(rf"\b{re.escape(rec)}\w*(?:\s+[a-z]+){{0,2}}?\s+(?:de\s+)?{re.escape(a)}\s*{u}\b", n[:m.start()]))
        if not vechi:
            break
        v = vechi[-1]
        rep = t[v.start():v.start() + n[v.start():v.end()].rfind(a)] + nou
        note.append(f"autocorectură „{t[m.start():m.end()].strip(' ,;.')}” → „{rep.strip()}” (ultima valoare câștigă)")
        t = t[:v.start()] + rep + t[v.end():m.start()] + t[m.end():]
    t2 = _sub(t, RE_INTREB_NU, lambda m, t0: "", note,
              "autocorectură „{}” → valoarea dinaintea întrebării se ignoră")
    return t2


def _autocorecturi(text, note):
    text = _nu_e(text, note)
    t = _sub(text, RE_PAR_NU, lambda m, t0: "(" + t0[m.start("x"):m.end("x")] + ")", note,
             "autocorectură în paranteză: „{}” → doar prima valoare (cea corectată) rămâne")

    def nu_ci(m, t0):
        ua, ub = (m.group("ua") or m.group("ub")), m.group("ub")
        if ua != ub:
            return None
        # valoarea veche („nu 400”) dispare și din restul propoziției; rămâne cea nouă
        return t0[m.start("b"):m.end("ub")]
    t2 = _sub(t, RE_NU_CI, nu_ci, note, "autocorectură „{}” → rămâne valoarea de după „ci”")
    t = t2
    m = RE_CORECTEZ_INCEPUT.match(_n(t))
    if m and m.end() < len(t):
        note.append(f"„{t[:m.end()].strip()}” la începutul mesajului — marcator de corectură fără valoare veche (ignorat)")
        t = t[m.end():]
    # „rectific: 3 x …”, „mai exact 25 kW”, „scuze, sunt 3 x SG30CX” → marcatorul r9 („corectez:”), pe care
    # rescrie_autocorectura îl aplică ultimei entități de același fel din propoziție
    t = _sub(t, RE_MARCATORI_NOI, lambda m, t0: " corectez: ", note)
    return t


RE_KVA_INCEPUT = re.compile(rf"^\s*(?P<v>{NUM})\s*kva\s*[.;,]\s*")


def _kva_inceput(text, note):
    """„Corectez: nu 400 kVA, ci 630 kVA. TG din PT propriu …” → valoarea corectată ține de PT-ul fără kVA"""
    n = _n(text)
    m = RE_KVA_INCEPUT.match(n)
    if not m:
        return text
    mp = re.search(r"\b(?:pt|post\w*(?:\s+de\s+transformare)?|trafo\w*|transformator\w*)(?:\s+(?:propriu|existent|nou|uscat|ulei))*\b"
                   r"(?!\s*\d)", n[m.end():])
    if not mp:
        return text
    poz = m.end() + mp.end()
    note.append(f"„{text[:m.end()].strip()}” (valoarea corectată) = Sn al PT-ului ({m.group('v')} kVA)")
    return text[m.end():poz] + f" {m.group('v')} kVA" + text[poz:]


def _deci(text, note):
    n = _n(text)
    m = RE_DECI_TOTAL.search(n)
    if not m:
        return text
    note.append(f"„{text[m.start():m.end()].strip()}”: suma de control ({m.group('t')} kW) înlocuiește totalul scris înainte "
                f"({m.group('v')} kW)")
    return text[:m.start("v")] + m.group("t") + text[m.end("v"):m.end("mid")] + text[m.end():]


# ------------------------------------------------------------------------------------------------- invertoare
_MARCI = r"huawei|sungrow|sma|fronius|deye|growatt|solis|goodwe|solaredge|kostal|abb|fimer|victron|ingeteam|kaco|delta|sofar|foxess"
RE_INV_PARANTEZA = re.compile(rf"(?<![\w.,])(?P<n>\d+|doua|doi|trei|patru|cinci)\s+(?P<w>invertoare|invertori|inv\.?)\s*"
                              rf"\(\s*(?P<lista>[^()]*?\d[^()]*?)\)")


def _inv_paranteza(text, note):
    def f(m, t0):
        n = _NUMERAL.get(m.group("n")) or int(m.group("n"))
        lista = t0[m.start("lista"):m.end("lista")]
        itemi = [x.strip() for x in re.split(r"(?<!\d),|,(?!\d)|\s+(?:si|și|plus)\s+|\s*\+\s*|;", lista) if x.strip()]
        if len(itemi) < 2 or not all(re.search(rf"{NUM}\s*(?:kw|kva)\b|[a-z]{{2,}}\d|\d+ktl", _n(x)) for x in itemi):
            return None
        if len(itemi) != n:
            return None                                   # numărul nu se potrivește → regula I05 (întrebare)
        out = []
        for x in itemi:
            mx = re.match(rf"(?P<k>\d+)\s*[x×]\s*", _n(x))
            out.append(x if mx else f"1 x invertor {x}")
        note.append(f"„{t0[m.start():m.end()].strip()}” = {n} invertoare: " + " + ".join(itemi)
                    + " (lista din paranteză are prioritate)")
        return ", ".join(out)
    return _sub(text, RE_INV_PARANTEZA, f, note)


# „2 invertoare Fronius Symo 20.0-3-M (40 kW existenți)” / „4 x SUN2000-100KTL-M2 (400 kW)” — suma de control
RE_SUMA_PAR = re.compile(rf"(?P<cap>(?<![\w.,])(?P<n>\d+|doua|doi|trei|patru)\s*(?:[x×]\s*|invertoare\s+|invertori\s+)"
                         rf"(?:(?:{_MARCI})\s+)?(?P<model>[a-z][\w.\- ]{{1,30}}?\d[\w.\-]*))\s*\(\s*(?P<v>{NUM})\s*kw\s*"
                         rf"(?P<ex>existent\w*|in\s+total|total|instalat\w*)?\s*\)")


def _suma_paranteza(text, note):
    try:
        from .calc.catalog_invertoare import cauta as _cauta  # type: ignore
    except Exception:  # noqa: BLE001
        _cauta = None

    def p_model(model):
        mm = re.search(r"(\d+(?:[.,]\d+)?)\s*-?\s*(?:ktl|k\b|kw|cx|hx|-3|\.0)", model)
        return _num(mm.group(1)) if mm else None

    def f(m, t0):
        n = _NUMERAL.get(m.group("n")) or int(m.group("n"))
        v = _num(m.group("v"))
        p = p_model(m.group("model"))
        if not p or abs(n * p - v) > 0.01 * max(1, v) or n == 1:
            return None
        ex = m.group("ex") or ""
        note.append(f"„{t0[m.start():m.end()].strip()}”: {m.group('v')} kW = {n} × {_f(p)} kW — suma de control (nu Pn per "
                    "invertor)" + (", grup EXISTENT" if ex.startswith("existent") else ""))
        return t0[m.start("cap"):m.end("cap")] + (" existente" if ex.startswith("existent") else "")
    return _sub(text, RE_SUMA_PAR, f, note)


# „Avem deja 20 kW (Fronius Symo 20.0-3-M) cu PI in tablou.” → „Avem deja 1 x Fronius Symo 20.0-3-M existent …”
RE_DEJA_KW_MODEL = re.compile(rf"\b(?P<cap>(?:avem|are|exista|sunt)\s+deja|deja\s+(?:avem|exista|sunt|am))\s+(?P<v>{NUM})\s*kw\s*"
                              rf"\(\s*(?P<model>[^()]{{3,40}}?)\s*\)")


def _deja_model(text, note):
    def f(m, t0):
        model = t0[m.start("model"):m.end("model")].strip()
        note.append(f"„{t0[m.start():m.end()].strip()}” = invertorul EXISTENT {model} ({m.group('v')} kW)")
        return f"{t0[m.start('cap'):m.end('cap')]} 1 x {model} existent"
    return _sub(text, RE_DEJA_KW_MODEL, f, note)


# ------------------------------------------------------------------------------------------------- ATR / limitări
RE_ATR_PERMITE = re.compile(rf"\b(?:atr(?:-ul)?|avizul(?:\s+tehnic)?|aviz(?:ul)?\s+de\s+racordare|os[dt]|distribuitorul)\s+"
                            rf"(?:ne\s+)?(?:permite|aproba|accepta|da|acorda)\s+(?:doar|numai|maxim|max\.?)?\s*(?P<v>{NUM})\s*"
                            rf"(?P<u>kw|mw)\s*(?:la\s+|de\s+|pentru\s+)?(?:evacuare|injectie|injectare|export|livrare)\b")
RE_PROCENT_LIM = re.compile(rf"\b(?:injecti\w*\s+(?:limitat\w*|maxim\w*)|limitare\w*(?:\s+a)?(?:\s+injecti\w*)?|limitat\w*)\s+"
                            rf"(?:la\s+)?(?P<v>{NUM})\s*%(?:\s+din\s+(?:putere\w*|pn|pi|puterea\s+instalata))?")


RE_ATR_SCURT = re.compile(rf"\b(?:atr|aviz\w*)\s+(?:de\s+|cu\s+|pentru\s+)?(?P<w>evacuare|injectie|export)\s*(?:de\s+|=\s*|:\s*)?"
                          rf"(?P<v>{NUM})\s*(?P<u>kw|mw)\b")
RE_N_BAT = re.compile(rf"(?<![\w.,×x])(?P<n>[2-9]|1[0-9])\s+(?P<cuv>baterii|acumulatoare|module\s+(?:de\s+)?baterie)\s+(?:de\s+)?"
                      rf"(?P<v>{NUM})\s*kwh\b(?!\s*(?:fiecare|total|in\s+total))")


def _atr(text, note):
    t = _sub(text, RE_ATR_PERMITE, lambda m, t0: f"putere aprobata la evacuare {m.group('v')} {m.group('u')}", note,
             "„{}” = puterea aprobată de evacuare din ATR (limitarea injecției, dacă e sub puterea invertoarelor)")
    t = _sub(t, RE_ATR_SCURT, lambda m, t0: f"putere aprobata la evacuare {m.group('v')} {m.group('u')}", note,
             "„{}” = puterea aprobată de evacuare din ATR")
    # „2 baterii 5 kwh” = 2 × 5 kWh (capacitatea unei baterii; totalul se scrie „în total”)
    t = _sub(t, RE_N_BAT, lambda m, t0: f"{m.group('n')} x {m.group('cuv')} {m.group('v')} kWh", note,
             "„{}” = N baterii × capacitatea uneia (PRESUPUS — dacă e capacitatea totală, scrieți „în total”)")
    return t


# ------------------------------------------------------------------------------------------------- engleză r10
EN_R10 = [
    (re.compile(r"\b(?:connection|connected|tie[\s-]*in)\s+(?:to|in|into)\s+(?:the\s+)?existing\s+(?:main\s+)?(?:lv\s+)?"
                r"(?:switchboard|board|panel|mdb|msb)\b", re.I), "racord in TG existent"),
    (re.compile(r"\b(?:source\s*:\s*|fed\s+from\s+|from\s+)?(?:the\s+)?existing\s+(?:main\s+)?(?:lv\s+)?(?:switchboard|board|panel|mdb|msb)\b",
                re.I), "din TG existent"),
    (re.compile(r"\butility\s+(?:transformer|substation)\b|\b(?:dso|dno)(?:'s)?\s+(?:transformer|substation)\b", re.I),
     "PT al OD"),
    (re.compile(rf"\b(new|existing)\s+({NUM})\s*kva\s+(?:substation|transformer|transformer\s+station|post)\b", re.I),
     lambda m: f"PT {'nou' if m.group(1).lower() == 'new' else 'existent'} {m.group(2)} kVA"),
    (re.compile(r"\bcar\s+wash\b", re.I), "spalatorie auto"),
    (re.compile(r"\bsupply\s+(\d+)\s*x\s*(\d+)\s*a\s+from\s+(?:the\s+)?(?:dso|dno|utility|grid)\b", re.I), r"din BMPT \1x\2A"),
    (re.compile(r"\b(?:dryer\s+blower|blower)\b", re.I), "ventilator uscare"),
    (re.compile(r"\bhigh[\s-]*pressure\s+pumps?\b", re.I), "pompe inalta presiune"),
    (re.compile(r"\bvacuums?\b", re.I), "aspiratoare"),
    (re.compile(r"\bforklift\s+chargers?\b", re.I), "incarcatoare stivuitoare"),
    (re.compile(r"\bdock\s+levelers?\b", re.I), "rampe"),
]


def _en(text, note):
    t = text
    for rx, rep in EN_R10:
        t2 = rx.sub(rep, t)
        if t2 != t:
            note.append("termen englezesc → " + (f"„{rep}”".replace("\\1", "").replace("\\2", "") if isinstance(rep, str)
                                                 else "PT"))
            t = t2
    return t


# ------------------------------------------------------------------------------------------------- cantități
_REC_C = r"(?:prize|priza|lumini|ilum\.?|iluminat|iluminare)"
RE_PERECHE_REC = re.compile(rf"(?<![\w.,×x])(?P<n1>\d{{1,2}})[ \t]+(?:circ(?:uite|uit)?\.?[ \t]+(?:de[ \t]+)?)?(?P<r1>{_REC_C})"
                            rf"[ \t]+(?P<n2>\d{{1,2}})[ \t]+(?:circ(?:uite|uit)?\.?[ \t]+(?:de[ \t]+)?)?(?P<r2>{_REC_C})"
                            rf"(?![\w])(?!\s*{NUM}\s*(?:kw|a|w)\b)")
RE_CIRC_ABREV = re.compile(r"(?<![\w.,])(?P<n>\d{1,2})[ \t]+circ\.?[ \t]+(?=[a-z])")


def _rec(x):
    return "prize" if x.startswith("priz") else "iluminat"


def _cantitati(text, note):
    """„8 circ prize 6 ilum” → „8 circuite prize, 6 circuite iluminat”; „5 prize 3 lumini” → idem (nu „prize 6 kW” /
    „prize 3 kW”): o cifră lipită de receptor, urmată de alt receptor, e numărul de circuite al celui de-al doilea."""
    def f(m, t0):
        note.append(f"„{t0[m.start():m.end()]}” = {m.group('n1')} circuite de {_rec(m.group('r1'))} + {m.group('n2')} "
                    f"circuite de {_rec(m.group('r2'))} (număr de circuite, nu putere)")
        return f"{m.group('n1')} circuite {_rec(m.group('r1'))}, {m.group('n2')} circuite {_rec(m.group('r2'))}"
    t = _sub(text, RE_PERECHE_REC, f, note)
    t = _sub(t, RE_CIRC_ABREV, lambda m, t0: f"{m.group('n')} circuite ", note)
    return t


RE_1P1 = re.compile(rf"(?<![\w.,])(?P<n>2|doua|doi)\s+(?P<nume>[a-z]+(?:\s+(?:de\s+)?[a-z]+)?)\s+(?P<p>{NUM})\s*(?P<u>kw|kva)\s*"
                    r"\(\s*1\s*a?\s*\+\s*1\s*r?(?:\s*(?:de\s+)?rezerv\w*)?\s*\)")
RE_1P1_B = re.compile(rf"\b(?P<nume>[a-z]+(?:\s+[a-z]+)?)\s+(?P<n>2)\s*[x×]\s*(?P<p>{NUM})\s*(?P<u>kw|kva)\s*"
                      r"\(\s*1\s*a?\s*\+\s*1\s*r?(?:\s*(?:de\s+)?rezerv\w*)?\s*\)")
RE_PLUS_REZ = re.compile(rf"(?<![\w.,])(?:1|o|un)\s+(?P<nume>pomp\w*|motor\w*|ventilator\w*|compresor\w*|electropomp\w*)\s+"
                         rf"(?P<p>{NUM})\s*(?P<u>kw|kva)\s*(?:\+|si|plus)\s*(?:1|o|una|un)\s+(?:de\s+)?rezerv\w*")


def _sing(nume):
    return re.sub(r"pompe\b", "pompa", re.sub(r"motoare\b", "motor", re.sub(r"ventilatoare\b", "ventilator", nume)))


def _rezerva(text, note):
    if re.search(r"\bge\b|grup\w*\s+electrogen|generator|\bats\b|\baar\b", _n(text)):
        return text                                 # la GE + ATS „(1+1)” e citit de extrage_ge (consumatori[].n)
    def f(m, t0):
        nume = _sing(t0[m.start("nume"):m.end("nume")])
        p, u = m.group("p"), t0[m.start("u"):m.end("u")]
        note.append(f"„{t0[m.start():m.end()].strip()}” = 1 activ + 1 rezervă ({nume} {p} {u}): rezerva desenată, nu se adună")
        return f"{nume} {p} {u}, {nume} rezerva {p} {u}"
    t = _sub(text, RE_1P1, f, note)
    t = _sub(t, RE_1P1_B, f, note)
    t = _sub(t, RE_PLUS_REZ, f, note)
    return t


RE_DIN_N = re.compile(r"\binterblocaj\w*\s*(?:de\s+tip\s+)?(?:\(\s*)?(?P<a>\d)\s+din\s+(?P<b>\d)\b(?:\s*\))?")


def _din(text, note):
    return _sub(text, RE_DIN_N, lambda m, t0: f"interblocaj {m.group('a')}-din-{m.group('b')}".replace("2-din-3", "doi-din-trei")
                .replace("1-din-2", "unu-din-doi"), note, "„{}” = tipul interblocajului (nu valori)")


# ------------------------------------------------------------------------------------------------- cuvinte capcană
RE_PT_MIC = re.compile(rf"(?<![\w-])pt\s+(?P<iz>uscat|ulei|in\s+ulei|zidit|anvelopa|aerian|pe\s+stalp|nou|existent|propriu)\b"
                       rf"(?:\s+(?P<v>{NUM})(?!\s*(?:kw|a|m|v)\b)(?:\s*kva)?)?")
RE_PT_KVA = re.compile(rf"(?<![\w-])pt\s+(?P<v>{NUM})\s*kva\b")


def _pt_mic(text, note):
    def f(m, t0):
        if t0[m.start():m.start() + 2] != "pt":
            return None                                   # „PT” scris cu majuscule e deja post de transformare
        iz = {"in ulei": "ulei", "pe stalp": "aerian"}.get(m.group("iz"), m.group("iz"))
        v = m.group("v")
        note.append(f"„{t0[m.start():m.end()].strip()}” = post de transformare (PT), nu „pentru”"
                    + (f"; {v} = Sn {v} kVA" if v else ""))
        return f"PT {iz}" + (f" {v} kVA" if v else "")
    t = _sub(text, RE_PT_MIC, f, note)
    t = _sub(t, RE_PT_KVA, lambda m, t0: f"PT {m.group('v')} kVA" if t0[m.start():m.start() + 2] == "pt" else None, note)
    return t


RE_IZOLATIE_MT = re.compile(r"(?<![\d.,])(?P<a>3[.,]6|6|8[.,]7|12|18)\s*/\s*(?P<b>6|10|15|20|30|35)\s*(?:\(\s*\d+[.,]?\d*\s*\)\s*)?kv\b")


def _izolatie_mt(text, note):
    return _sub(text, RE_IZOLATIE_MT, lambda m, t0: f"izolatie U0/U {m.group('a')}-{m.group('b')}", note,
                "„{}” = tensiunea de izolație a cablului MT (U0/U), nu tensiunea rețelei")


RE_PTA = re.compile(r"\bpta\b")


def _pta(text, note):
    if not RE_PTA.search(_n(text)):
        return text
    note.append("„PTA” = post de transformare aerian (pe stâlp), nu branșament")
    return _sub(text, RE_PTA, lambda m, t0: "PT aerian", [])


# „TG la intrare cu Q 3x32A” (locuință) / „TG cu Q 3x32A” — Q-ul branșamentului, nu plecări „Q 1/2/3”
RE_Q_BRANS = re.compile(rf"\b(?:tg|tablou\w*\s+general)(?:\s+(?:la|de\s+la)\s+intrare)?\s+cu\s+q\s*(?P<n>[13])\s*[x×]\s*(?P<v>{NUM})\s*a\b"
                        rf"|\bbransament\w*(?:\s+(?:trifaz\w*|tri|existent|nou|unic|comun))*\s+(?P<n2>3)\s*[x×]\s*(?P<v2>\d{{2,3}})(?!\s*(?:a|kw|mm|m)\b)(?![\d.,])")


def _q_brans(text, note):
    def f(m, t0):
        n, v = m.group("n") or m.group("n2"), m.group("v") or m.group("v2")
        return (("TG, " if m.group("n") else "") + f"bransament {'trifazat' if n == '3' else 'monofazat'} {n}x{v}A")
    return _sub(text, RE_Q_BRANS, f, note, "„{}” = Q-ul branșamentului (nu plecări)")


RE_LA_V = re.compile(rf"(?P<p>{NUM}\s*(?:kw|kva|cp|hp))\s+la\s+(?P<u>230|380|400)\s*v\b")


def _la_v(text, note):
    """„cuptor electric 72 kW la 400V” → „… 72 kW 400V” (tensiunea receptorului, nu altă valoare)"""
    return _sub(text, RE_LA_V, lambda m, t0: f"{t0[m.start('p'):m.end('p')]} {m.group('u')}V", note)


RE_VFD = re.compile(r"\b(?:convertizor|convertor|variator)\w*\s+(?:static\s+)?de\s+frecvent\w*|\bconvertizor\w*\s+frecvent\w*")
RE_PLUS_ITEM = re.compile(r"(?<=[a-z\d])\s+\+\s+(?=[a-z])")
RE_ETICHETA_NX = re.compile(rf"\b(?P<et>motoare|pompe|ventilatoare|compresoare|consumatori\s+forta)\s*:\s*"
                            rf"(?P<lista>\d+\s*[x×]\s*{NUM}\s*kw(?:\s*(?:,|si|și|\+)\s*\d+\s*[x×]\s*{NUM}\s*kw)+)")
_VOCAB = ["compresor", "ventilator", "iluminat", "propriu", "trifazat", "monofazat", "pompa", "pompe", "motor", "motoare",
          "prize", "boiler", "cuptor", "plita", "existent", "transformator", "tablou", "plecari", "circuite", "alimentat",
          "ventilatie", "incalzire", "climatizare", "frigider", "uscator", "invertor", "invertoare", "bransament",
          "contor", "generator", "separator", "intreruptor", "siguranta", "hidrofor", "aspirator"]


def _vfd(text, note):
    return _sub(text, RE_VFD, lambda m, t0: "VFD", note, "„{}” = convertizor de frecvență (pornire VFD)")


def _plus(text, note):
    n = _n(text)
    if re.search(r"invertor|\bpv\b|fotovolt|\bcef\b|baterie|hibrid|\bkwh\b|\bcas(?:a|ei)\b|apartament", n) \
            or len(re.findall(r"\d\s*kw\b", n)) < 2:
        return text
    return _sub(text, RE_PLUS_ITEM, lambda m, t0: ", ", [])


def _eticheta_nx(text, note):
    def f(m, t0):
        et = _n(m.group("et"))
        sing = {"motoare": "motor", "pompe": "pompa", "ventilatoare": "ventilator", "compresoare": "compresor"}.get(et, "motor")
        itemi = re.findall(rf"(\d+)\s*[x×]\s*({NUM})\s*kw", t0[m.start("lista"):m.end("lista")], re.I)
        note.append(f"„{t0[m.start():m.end()].strip()}” = " + " + ".join(f"{a} × {sing} {b} kW" for a, b in itemi))
        return "plecari: " + ", ".join(f"{a} x {sing} {b} kW" for a, b in itemi)
    return _sub(text, RE_ETICHETA_NX, f, note)


def _typo(text, note):
    """greșeli de tastare pe cuvintele tehnice uzuale („compresr”, „venitlator”, „ilumnat”, „proprui”)"""
    import difflib
    out, gas = [], []
    parti = re.split(r"(\W+)", text)
    for i, tok in enumerate(parti):
        tn = _n(tok)
        urm = "".join(parti[i + 1:i + 3])
        prec = _n("".join(parti[max(0, i - 2):i]))
        # doar numele unui receptor urmat de valoare („compresr 18,5kw”) sau „pt proprui”
        if not (re.match(r"\s*\d", urm) or re.search(r"\bpt\s*$", prec)):
            out.append(tok)
            continue
        if len(tn) >= 6 and tn.isalpha() and tn not in _VOCAB:
            cand = difflib.get_close_matches(tn, _VOCAB, n=1, cutoff=0.84)
            if cand and abs(len(cand[0]) - len(tn)) <= 1 and tn[:2] == cand[0][:2] \
                    and not any(tn.startswith(v) or v.startswith(tn) for v in _VOCAB):
                gas.append(f"{tok} → {cand[0]}")
                out.append(cand[0] if tok.islower() else cand[0].capitalize())
                continue
        out.append(tok)
    if gas:
        note.append("greșeli de tastare corectate: " + ", ".join(gas))
    return "".join(out)


RE_VE_NX = re.compile(rf"(?<![\w.,])(?P<n>\d+)\s+(?P<st>stati\w*\s+(?:de\s+)?incarcare(?:\s+(?:ev|ve|auto))?)\s+"
                      rf"(?P<k>\d)\s*[x×]\s*(?P<p>{NUM})\s*kw\b")
RE_SURSA_DUBLA = re.compile(rf"(?:\b(?:tg|tablou\w*(?:\s+general)?)\s+cu\s+)?\bsurs\w*\s+dubl\w*\s*:?\s*pt\s*1\s+(?P<a>{NUM})\s*kva\s+(?:si|și|,)\s*pt\s*2\s+(?P<b>{NUM})\s*kva")


def _ve_nx(text, note):
    def f(m, t0):
        n, k, p = int(m.group("n")), int(m.group("k")), _num(m.group("p"))
        note.append(f"„{t0[m.start():m.end()]}” = {n} stații × {k} puncte × {m.group('p')} kW = {n} plecări de "
                    f"{_f(k * p)} kW (DLM declarat — puterea limitată se scrie explicit)")
        return f"plecari: {n} x Statie incarcare VE {_f(k * p)} kW"
    t = _sub(text, RE_VE_NX, f, note)
    # „cu DLM” (gestionarea dinamică a sarcinii) — notă, nu parte din plecare
    t = _sub(t, re.compile(r"\s+cu\s+dlm\b|,\s*dlm\b"), lambda m, t0: "", note,
             "„{}” = gestionare dinamică a sarcinii (DLM) la stațiile VE — puterea limitată se declară explicit")
    return t


RE_POMPA_DIESEL = re.compile(rf"(?:\brezerv\w*\s+1\s*\+\s*1\s+(?:pentru\s+)?(?P<ctx>pomp\w*\s+(?:de\s+)?incendiu)\s*:\s*)?"
                             rf"\b(?P<el>(?:electro)?pomp\w*(?:\s+electric\w*)?)\s+(?P<p>{NUM})\s*kw\s*(?:\+|si|și|plus)\s*"
                             rf"(?:o\s+|1\s+)?(?:moto)?pomp\w*\s+(?:cu\s+motor\s+)?diesel")


def _pompa_diesel(text, note):
    """„Rezervă 1+1 pentru pompele de incendiu: pompă electrică 45 kW + pompă diesel” → plecarea pompei electrice de
    incendiu; motopompa diesel (rezerva 1+1, cu motor propriu) nu se alimentează electric — doar notă."""
    def f(m, t0):
        note.append(f"„{t0[m.start():m.end()].strip()}”: pompa diesel (rezervă 1+1) are motor termic propriu — nu are "
                    "plecare electrică (notă); se desenează doar pompa electrică")
        ctx = "pompa incendiu electrica" if m.group("ctx") or re.search(r"incendiu|psi|hidrant|sprinkler", _n(t0)) \
            else "pompa electrica"
        return f"plecari: {ctx} {m.group('p')} kW"
    return _sub(text, RE_POMPA_DIESEL, f, note)


def _sursa_dubla(text, note):
    def f(m, t0):
        if m.group("a") != m.group("b"):
            return None
        note.append(f"„{t0[m.start():m.end()]}” = PT cu 2 transformatoare de {m.group('a')} kVA (câte unul pe semibară)")
        return f"PT cu 2 transformatoare {m.group('a')} kVA, TG"
    t = _sub(text, RE_SURSA_DUBLA, f, note)
    t = _sub(t, RE_SEMIBARE_N, lambda m, t0: f"fiecare semibara cu {m.group('n')} plecari de {m.group('v')} {m.group('u')}",
             note, "„{}” = plecările fiecărei semibare")
    return t


RE_SEMIBARE_N = re.compile(rf"\b(?:2|doua)\s+(?:semibare|sectii)(?:\s+de\s+bare)?\s+cu\s+(?:cate\s+)?(?P<n>\d+)\s+plecari\s+"
                           rf"(?:de\s+)?(?P<v>{NUM})\s*(?P<u>kw|a)\b")


RE_UNA_SI_UNA = re.compile(rf"(?P<n>\d|doua|doi)\s+(?P<rec>[a-z][a-z ]{{1,30}}?)\s*:\s*(?:una|unul|un|o)\s+(?:de\s+)?(?P<a>{NUM})\s*kw\s*"
                           rf"(?:,|si|și)\s*(?:una|unul|alta|alt|celalalt|cealalta|o)\s+(?:de\s+)?(?P<b>{NUM})\s*kw")
RE_ILUM_ABREV = re.compile(r"(?<![\w.,])(?P<n>\d{1,2})\s+(?:circ\w*\.?\s+)?ilum\b\.?")
RE_CLADIRE_LOC = re.compile(r"\bcladire\w*\s+(?P<p>p\s*\+\s*[1-3m])\s+cu\s+(?:\d|doua)\s+tablouri\s*:?")


def _sing_rec(r):
    r = r.strip()
    for a, b in (("statii", "statie"), ("stații", "stație"), ("pompe", "pompa"), ("motoare", "motor"), ("aparate", "aparat"),
                 ("prize", "priza"), ("boilere", "boiler")):
        r = re.sub(rf"\b{a}\b", b, r)
    return r


def _una_si_una(text, note):
    """„2 stații VE: una 11 kW și una 7,4 kW” → „stație VE 11 kW, stație VE 7,4 kW” (fiecare cu puterea ei)"""
    def f(m, t0):
        n = _NUMERAL.get(m.group("n")) or int(m.group("n"))
        if n != 2:
            return None
        rec = _sing_rec(t0[m.start("rec"):m.end("rec")])
        note.append(f"„{t0[m.start():m.end()]}” = {rec} {m.group('a')} kW + {rec} {m.group('b')} kW")
        return f"{rec} {m.group('a')} kW, {rec} {m.group('b')} kW"
    return _sub(text, RE_UNA_SI_UNA, f, note)


def _ilum(text, note):
    t = _sub(text, RE_ILUM_ABREV, lambda m, t0: f"{m.group('n')} circuite iluminat", note)
    return t


def _cladire_loc(text, note):
    """„Clădire P+1 cu 2 tablouri: TE parter (bucătărie, living) și TE etaj (dormitoare, băi …)” = casă cu TE pe niveluri"""
    n = _n(text)
    if not re.search(r"\bbucatari\w*|\bliving\b|\bdormitor\w*|\bbai\b|\bbaie\b", n) or re.search(
            r"\bbirou\w*|\bmagazin\w*|\bhal[aei]\b|\bscoal\w*|\bpensiun\w*", n):
        return text
    return _sub(text, RE_CLADIRE_LOC, lambda m, t0: f"casa {m.group('p').upper().replace(' ', '')} cu tablouri:", note,
                "„{}” cu bucătărie / dormitoare / băi = casă (locuință) cu tablouri pe niveluri")


RE_CABLU_MM = re.compile(r"(?<![\w.,])(?P<c>[2-5])\s*[x×]\s*(?P<s>\d+(?:[.,]\d+)?)\s*mm\b(?!\s*[²2])")


def _cablu_mm(text, note):
    """„cablu 3x6mm de 45 m” → „cablu 3x6 mm2 …” (secțiunea, nu „6 mm” lungime)"""
    return _sub(text, RE_CABLU_MM, lambda m, t0: f"{m.group('c')}x{m.group('s')} mm2", [])


RE_IN_LOC = re.compile(r"\b(?:in|pentru)\s+(?:anexa|atelier|garaj|mansarda|foisor|sopron)\s*:")
RE_N_PRIZE_A = re.compile(rf"(?:\bbanc\w*\s+de\s+lucru\s+)?(?<![\w.,])(?P<n>\d)\s+prize\s+(?P<a>\d{{2}})\s*a\b")
RE_SCULE = re.compile(r"\s*,\s*(?:flex|bormasin\w*|fierastrau\w*|slefuitor\w*|surubelni\w*)(?=\s*,|\s*$)")
RE_SUDURA = re.compile(rf"(?<!aparat\s)\bsudur\w*\s+(?P<v>{NUM})\s*(?P<u>kva|kw)\b")


def _td_anexa(text, note):
    """TD-ul anexei / atelierului: „în anexă: banc de lucru 2 prize 16A tri, flex, bormașină, sudură 5 kVA” → plecările lui
    (2 prize 16 A tri, aparat de sudură 5 kVA); sculele portabile (flex, bormașină) se alimentează din prize"""
    n = _n(text)
    if not re.match(r"\s*(?:td|te|tablou\w*\s+secundar\w*)\b", n):
        return text
    t = _sub(text, RE_IN_LOC, lambda m, t0: "plecari:", note)
    t = _sub(t, RE_N_PRIZE_A, lambda m, t0: f"{m.group('n')} x priza {m.group('a')}A", note,
             "„{}” = prize separate (câte un circuit)")
    t = _sub(t, RE_SCULE, lambda m, t0: "", note, "„{}” = sculă portabilă alimentată din prize (nu circuit separat)")
    t = _sub(t, RE_SUDURA, lambda m, t0: f"aparat sudura {m.group('v')} {t0[m.start('u'):m.end('u')]}", note)
    return t


def rescrie_inainte(text: str) -> tuple[str, list[str]]:
    note: list[str] = []
    t = text
    t = _en(t, note)
    t = _autocorecturi(t, note)
    return (t, note) if t != text else (text, [])


def rescrie_dupa(text: str) -> tuple[str, list[str]]:
    """după autocorecturile r9 (înaintea cifrelor / termenilor)"""
    note: list[str] = []
    t = text
    for f in (_td_anexa, _cablu_mm, _typo, _vfd, _una_si_una, _ilum, _cladire_loc, _ve_nx, _pompa_diesel, _sursa_dubla, _plus, _eticheta_nx, _la_v, _kva_inceput, _deci, _inv_paranteza, _suma_paranteza, _deja_model, _atr, _cantitati, _rezerva, _din, _pt_mic,
              _izolatie_mt, _pta, _q_brans):
        t = f(t, note)
    return (t, note) if t != text else (text, [])
