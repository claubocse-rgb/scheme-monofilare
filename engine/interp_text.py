"""r7: normalizarea formatului textului liber ÎNAINTE de orice regex al interpretorului (SPEC §F.2.5).

Toate transformările păstrează LUNGIMEA textului (pozițiile din copia de lucru indică același loc în textul original —
de acolo se iau numele plecărilor, beneficiarul, localitatea). Ce face:

* separatori de listă: rând nou / tab / liniuță-bullet la început de rând / „1)” „2.” „a)” (enumerări) → „;”;
* „a câte” / „a cate” / „câte” (distributiv) → spații: „15 plecări a câte 25 kW” = „15 plecări 25 kW”;
  „N de circuite / plecări / bucăți / motoare …” → „N circuite …” („30 de circuite prize de 2 kW”);
* „3P+N+PE”, „1P+N” — „+” nu e separator de listă aici (polii unei prize / plecări);
* „din care” (sub-plecări) → „(”; lanțul „TG -> TD … -> TE …” → a doua săgeată deschide sub-plecările (cascadă);
* greșeli de tastare și termeni englezești uzuali, înlocuiți cu un cuvânt de aceeași lungime („huawey” → „huawei”,
  „exsitent” → „existent”, „substation” → „post trafo”, „existing” → „existent”);
* zecimale: „5x2,5”, „13,5kw”, „1.1kw” rămân neatinse (virgula între cifre NU e separator — vezi RE_SEP).
"""
from __future__ import annotations

import re

_DIA = str.maketrans("șşțţăâîȘŞȚŢĂÂÎ", "ssttaaiSSTTAAI")

# rând nou (+ bullet / liniuță / enumerare la început de rând), tab
RE_RAND_NOU = re.compile(r"[ \t]*(?:\r?\n)+[ \t]*(?:[-*•·–—]\s+|\d{1,2}[.)]\s+|[a-h]\)\s+)?")
RE_TAB = re.compile(r"\t+")
# enumerări în linie: „plecari: 1) linie … 2) cuptor …”, „a) … b) …” — doar dacă există cel puțin două numere consecutive
RE_ENUM = re.compile(r"(?:(?<=^)|(?<=[\s:;,(]))(?P<n>\d{1,2}|[a-h])\)\s+(?=[a-z])")
RE_A_CATE = re.compile(r"\b(?:a\s+cate|cate|fiecare\s+de|fiecare\s+cu|in\s+valoare\s+de)\b(?=\s*\d)")
RE_N_DE = re.compile(r"(?<![\w.,])(?P<n>\d+)\s+(?P<de>de)\s+(?=(?:circuit\w*|plecar\w*|bucat\w*|buc\b|motoar\w*|pomp\w*|priz\w*"
                     r"|ventilat\w*|compresoar\w*|invertoar\w*|module|panouri|incarcatoar\w*|tablouri|iluminat\w*)\b)")
RE_POLI = re.compile(r"\b(?P<p>[1-4]\s*p)\s*\+\s*n(?:\s*\+\s*pe)?\b")
RE_DIN_CARE = re.compile(r"\bdin\s+care\b")
RE_BUC_X = re.compile(r"(?<![\w.,])(\d+)(\s*(?:buc\w*\.?|bucati|pcs|unitati|unit\.?|aparate|bucăți)\s*)[x×](?=\s*\d)")
RE_SAGEATA = re.compile(r"->|→|=>")
TYPO = [  # (regex, înlocuire de aceeași lungime)
    (r"\bhuawey\b", "huawei"), (r"\bhuwaei\b", "huawei"), (r"\bexsitent\b", "existent"), (r"\bexistnet\b", "existent"),
    (r"\binvertr\b", "invert "), (r"\bsubstation\b", "post trafo"), (r"\bexisting\b", "existent"),
    (r"\bgrid\s+connection\b", "racord"), (r"\bplant\b", ""), (r"\baparatament\b", "apartament"),
    (r"\bapartamnet\b", "apartament"), (r"\bon[\s-]+grid\b", ""),
]
TYPO = [(re.compile(rx), rep) for rx, rep in TYPO]


def _subst(lst, s, e, rep):
    rep = rep[:e - s].ljust(e - s)
    lst[s:e] = list(rep)


def normalizeaza_format(t: str) -> tuple[str, list[str]]:
    """Textul (deja litere mici, fără diacritice) → (text de aceeași lungime, note). Vezi docstring-ul modulului."""
    note = []
    lst = list(t)
    for m in RE_RAND_NOU.finditer(t):
        if m.start() == 0 or m.end() >= len(t):
            _subst(lst, m.start(), m.end(), "")
            continue
        _subst(lst, m.start(), m.end(), ";")
    t2 = "".join(lst)
    # r8 (industrial #30): bullet-ul de la începutul textului („• chiller 180 kW …”)
    mb = re.match(r"\s*(?:[-*•·–—]|\d{1,2}[.)])\s+(?=[a-z])", t2)
    if mb:
        t2 = " " * mb.end() + t2[mb.end():]
    # r8 (industrial #32): „pompa 5,5kW / vent 3kW / iluminat 2kW” — „ / ” între itemi = separator de listă
    t2 = re.sub(r"(?<=[a-z0-9.)])(\s+)/(\s+)(?=[a-z])", lambda m: m.group(1) + ";" + m.group(2), t2)
    # r8 (industrial #1): „4 buc x 1,1 kW” = 4 × 1,1 kW
    t2 = RE_BUC_X.sub(lambda m: m.group(1) + " " * len(m.group(2)) + "×", t2)
    if "\n" in t or "\t" in t:
        note.append("rândurile / tab-urile / liniuțele din text = separatori de listă")
    t2 = RE_TAB.sub(lambda m: ";" + " " * (len(m.group(0)) - 1), t2)
    # enumerări „1) … 2) …” (cel puțin două, în ordine)
    en = list(RE_ENUM.finditer(t2))
    if len(en) >= 2:
        lst = list(t2)
        for m in en:
            _subst(lst, m.start(), m.end("n") + 1, ";")
        t2 = "".join(lst)
        note.append("enumerarea „1) 2) …” = separatori de listă (numerele de ordine nu sunt valori)")
    t2 = RE_A_CATE.sub(lambda m: " " * len(m.group(0)), t2)
    t2 = RE_N_DE.sub(lambda m: m.group(0)[:m.start("de") - m.start()] + "  " + m.group(0)[m.end("de") - m.start():], t2)
    t2 = RE_POLI.sub(lambda m: m.group(0).replace("+", " "), t2)
    # „din care” = sub-plecările itemului dinainte
    t2 = RE_DIN_CARE.sub(lambda m: "(" + " " * (len(m.group(0)) - 1), t2)
    # „TG -> TD … -> TE …”: săgețile după prima (lanț) deschid sub-plecări
    sag = list(RE_SAGEATA.finditer(t2))
    if len(sag) >= 2 and re.match(r"\s*(?:tg\w*|tablou\w*|tgd)\s*$", t2[max(0, sag[0].start() - 12):sag[0].start()]):
        lst = list(t2)
        for m in sag[1:]:
            _subst(lst, m.start(), m.end(), "(")
        t2 = "".join(lst)
        note.append("lanțul „TG → TD → TE” = cascadă (fiecare tablou alimentat din cel dinainte)")
    for rx, rep in TYPO:
        t2 = rx.sub(lambda m, r=rep: (r + " " * len(m.group(0)))[:len(m.group(0))], t2)
    assert len(t2) == len(t)
    return t2, note


# --------------------------------------------------------------------------------------------------------------
# r7: completări la catalogul motorului (engine/calc/catalog_invertoare.py nu se modifică de aici) — modele din
# rapoartele r7: Pn, hibrid, rețea, tensiunea c.a. (800 V fără N), invertor de baterie (cuplaj c.a.), kWh baterie
# --------------------------------------------------------------------------------------------------------------
# (regex pe „producător model” majuscul, producător, Pn(m), hibrid, rețea, U_ca_V)
MODELE_SUPL = [
    (r"\bSUN\s*-?\s*(\d+(?:[.,]\d+)?)\s*K\s*-?\s*SG\d+\s*LP3\b", "Deye", lambda m: m.group(1), True, "tri", 400),
    (r"\bSUN\s*-?\s*(\d+(?:[.,]\d+)?)\s*K\s*-?\s*SG\d+\s*LP1\b", "Deye", lambda m: m.group(1), True, "mono", 230),
    (r"\bSUN\s*-?\s*(\d+(?:[.,]\d+)?)\s*K\s*-?\s*SG\d+\s*HP3\b", "Deye", lambda m: m.group(1), True, "tri", 400),
    (r"\bSUN\s*2000\s*-?\s*(\d+)\s*KTL\s*-?\s*H[0-3]\b", "Huawei", lambda m: m.group(1), False, "tri", 800),
    (r"\bSG\s*(\d+)\s*HX\b", "Sungrow", lambda m: m.group(1), False, "tri", 800),
    (r"\bMIN\s*(\d{4,5})\s*TL", "Growatt", lambda m: float(m.group(1)) / 1000, False, "mono", 230),
    # r8 (locuințe #57): Growatt „5000TL-X” = 5 kW monofazat; „…TL3-X” = trifazat
    (r"\bGROWATT\s+(\d{4,5})\s*TL\s*-?\s*X", "Growatt", lambda m: float(m.group(1)) / 1000, False, "mono", 230),
    (r"\bGROWATT\s+(\d{4,5})\s*TL3\s*-?\s*X", "Growatt", lambda m: float(m.group(1)) / 1000, False, "tri", 400),
    (r"\bMIC\s*(\d{4,5})\s*TL", "Growatt", lambda m: float(m.group(1)) / 1000, False, "mono", 230),
    (r"\bGW\s*(\d+(?:[.,]\d+)?)\s*K\s*-?\s*(?:N\s*-?\s*)?MT\b", "GoodWe", lambda m: m.group(1), False, "tri", 400),
    (r"\bGW\s*(\d+(?:[.,]\d+)?)\s*K\s*-?\s*ET\b", "GoodWe", lambda m: m.group(1), True, "tri", 400),
    (r"\bPRIMO\s*GEN24\s*(\d+(?:[.,]\d+)?)", "Fronius", lambda m: m.group(1), True, "mono", 230),
    # r8: SMA Sunny Boy X.Y = invertor monofazat (Sunny Boy Storage = PCS, tratat la INV_BATERIE)
    (r"\bSUNNY\s+BOY\s*(\d+(?:[.,]\d+)?)\b", "SMA", lambda m: m.group(1), False, "mono", 230),
    (r"\bSTP\s*(\d+(?:[.,]\d)?)\s*(?:SE)?\s*$", "SMA", lambda m: m.group(1), None, "tri", 400),
    (r"\b(?:SUNNY\s+)?HIGHPOWER\s+PEAK3\s*(\d{2,3})\b", "SMA", lambda m: m.group(1), False, "tri", 400),
    (r"\bSHP\s*(\d{2,3})\s*-\s*\d{2}\b", "SMA", lambda m: m.group(1), False, "tri", 400),
    (r"\bMOD\s*(\d+(?:[.,]\d+)?)\s*KTL3?\s*-?\s*XH\b", "Growatt", lambda m: m.group(1), True, "tri", 400),
]
MODELE_SUPL = [(re.compile(rx), p, f, h, r, u) for rx, p, f, h, r, u in MODELE_SUPL]
# invertoare de baterie (PCS, cuplaj c.a.) — (regex, producător, P_kW(m), rețea)
INV_BATERIE = [
    (re.compile(r"\bSUNNY\s+ISLAND\s*(\d+(?:[.,]\d+)?)"), "SMA", "mono"),
    (re.compile(r"\bSUNNY\s+BOY\s+STORAGE\s*(\d+(?:[.,]\d+)?)"), "SMA", "mono"),
    (re.compile(r"\bSBS\s*(\d+(?:[.,]\d+)?)"), "SMA", "mono"),
]
# capacitatea bateriei din codul modelului (kWh per modul / pachet)
KWH_MODEL = [
    (re.compile(r"\bLUNA\s*2000\s*-?\s*(5|7|10|15|20|30)\s*-?\s*[SE]\d"), lambda m: float(m.group(1))),
    # r8: Huawei LUNA2000-200KWH-2H1 (BESS C&I) — kWh în cod
    (re.compile(r"\bLUNA\s*2000\s*-?\s*(\d+)\s*KWH\b"), lambda m: float(m.group(1))),
    # r8: BYD Battery-Box Premium HVS/HVM, BOS-G (BYD / Deye) — kWh pe modul / pachet
    (re.compile(r"\bBOS\s*-?\s*G\b(?:\s*(\d+(?:[.,]\d+)?))?"), lambda m: float((m.group(1) or "5.12").replace(",", "."))),
    (re.compile(r"\bHV[SM]\s*(\d+(?:[.,]\d+)?)"), lambda m: float(m.group(1).replace(",", "."))),
    (re.compile(r"\bUS\s*5000"), lambda m: 4.8), (re.compile(r"\bUS\s*3000\w*"), lambda m: 3.55),
    (re.compile(r"\bUS\s*2000\w*"), lambda m: 2.4),
]


def _up(producator, model):
    return re.sub(r"\s+", " ", f"{producator or ''} {model or ''}".upper().translate(_DIA)).strip()


def cauta_supl(producator=None, model=None):
    """{producator, Pn_kW, hibrid, retea, U_ca_V} pentru modelele din MODELE_SUPL, altfel None."""
    t = _up(producator, model)
    if not t:
        return None
    for rx, prod, pn, hib, retea, u in MODELE_SUPL:
        m = rx.search(t)
        if m:
            try:
                p = float(str(pn(m)).replace(",", "."))
            except (TypeError, ValueError):
                continue
            return {"producator": prod, "Pn_kW": round(p, 2), "hibrid": hib, "retea": retea, "U_ca_V": u}
    return None


def invertor_baterie(producator=None, model=None):
    """SMA Sunny Island / Sunny Boy Storage = invertor de baterie (PCS, cuplaj c.a.) → {P_kW, retea} sau None."""
    t = _up(producator, model)
    for rx, prod, retea in INV_BATERIE:
        m = rx.search(t)
        if m:
            return {"producator": prod, "P_kW": float(m.group(1).replace(",", ".")), "retea": retea}
    return None


def p_bess_din_model(producator=None, model=None):
    """r8: puterea unui BESS din codul modelului — „…-2H1” = 2 ore (P = kWh / 2), „…-1H1” = 1 oră."""
    t = _up(producator, model)
    k = kwh_din_model(producator, model)
    m = re.search(r"-\s*(\d)\s*H\d?\b", t)
    if k and m and int(m.group(1)) > 0:
        return round(k / int(m.group(1)), 2)
    return None


def kwh_din_model(producator=None, model=None):
    t = _up(producator, model)
    for rx, f in KWH_MODEL:
        m = rx.search(t)
        if m:
            return f(m)
    return None
