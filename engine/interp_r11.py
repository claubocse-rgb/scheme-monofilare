"""r11: rescrierile pe CLASE de formulări din runda 11 (teste/r11) + completările după reguli (SPEC §F.15).

Sinonimele de domeniu sunt în engine/interp_sinonime.py (dicționarul central); aici sunt formulările-clasă. Lungimea
textului NU se păstrează — fiecare rescriere lasă o notă („Am presupus”).

`rescrie_inainte` (formatul brut): CSV cu virgulă și ghilimele → „;”; liste numerotate „1. … - 12 kW; 2. …”.
`rescrie_dupa` (după autocorecturile r9 / r10):
  * invertoare: „3 x 50KTL” fără marcă = 3 × invertor 50 kW; „două tablouri TGD-CF …, fiecare cu 3 x …” = 6 împărțite
    în 2 TGD-CF; „12 stringuri a câte 20 module”; „2 baterii BOS-G 5,12 kWh” = 2 × 5,12; „export cap 400 kW”;
    „Avem PT propriu” = PT existent; „cablu solar 6 mmp” = cablul de c.c. (nu C0); autocorecturi pe racord
    („TG existent… de fapt nu, prin BMPT nou”) și pe statutul existent („pardon, existente sunt doar 2”); „3 x … noi și
    2 x … existente”;
  * industrial: „N stații EV de 22 kW”; „AAR” între trafo; „fără generator”; „pe bara vitală: …; pe bara normală: …”,
    „ATS pe consumatorii vitali (…). Nevitalii (…) rămân doar pe rețea”; cascade („TG alimentează TD1, TD1 alimentează
    TD1.1”, „TE alimentat din TD-2 care e alimentat din TG, iar TG din PT”); „TGJT cu 6 plecări NH: 3 x 250 A …”;
  * locuință: „pompa … e la 120 m, 1,5 kW”; „prizele pe C25 cu cablu 2,5 mm²”; „priză trifazată CEE 32A”; „generator
    8 kVA pe intrarea GEN”; „mărire de la 6 kW monofazat la 11 kW trifazat”.
`post(c, intr, ex, tip)` — după regulile vechi: UPS (nu PT), GE izolat, AAR, vitali, rețeaua DEDUSĂ (`_deduse`),
contradicțiile mono / tri doar pe alimentare, „fără panouri” = BESS fără PV, ks / ku declarate.
"""
from __future__ import annotations

import re

try:
    from . import interp_sinonime as S
except ImportError:  # rulare ca script
    from engine import interp_sinonime as S  # type: ignore

NUM = r"\d+(?:[.,]\d+)?"
_n = S.norm
_sub = S._sub
_NUMERAL = {"un": 1, "o": 1, "una": 1, "unu": 1, "doua": 2, "doi": 2, "trei": 3, "patru": 4, "cinci": 5, "sase": 6,
            "sapte": 7, "opt": 8, "noua": 9, "zece": 10}
_NUMW = r"\d+|doua|doi|trei|patru|cinci|sase|sapte|opt|noua|zece"


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _int(s: str) -> int:
    s = _n(s)
    return _NUMERAL[s] if s in _NUMERAL else int(s)


def _f(x: float) -> str:
    return (f"{x:.3f}".rstrip("0").rstrip(".")).replace(".", ",")


# ================================================================================================= format brut
def _csv_virgula(text, note):
    """r11 (fotovoltaic #62, r10 #47): CSV cu virgulă și ghilimele („Item,Qty,Power kW” / „"Huawei …",3,50”) → „;”
    (tabelul îl citește interp_tabel). Doar când ≥ 2 rânduri au același număr (≥ 2) de virgule în afara ghilimelelor."""
    linii = text.splitlines()
    if len(linii) < 2:
        return text

    def campuri(l):
        out, cur, q = [], "", False
        for ch in l:
            if ch == '"':
                q = not q
                continue
            if ch == "," and not q:
                out.append(cur.strip())
                cur = ""
                continue
            cur += ch
        out.append(cur.strip())
        return out
    idx = [i for i, l in enumerate(linii) if l.count(",") >= 2 and ";" not in l and "\t" not in l]
    if len(idx) < 2:
        return text
    nr = {len(campuri(linii[i])) for i in idx}
    if len(nr) != 1 or nr.pop() < 3:
        return text
    if not any('"' in linii[i] for i in idx) and not re.search(r"\b(?:qty|cant\w*|buc\w*|item|nr|denumire|pos|poz)\b", _n(linii[idx[0]])):
        return text
    for i in idx:
        linii[i] = ";".join(campuri(linii[i]))
    note.append("tabel CSV cu virgulă (și ghilimele) citit pe coloane")
    return "\n".join(linii)


RE_LISTA_NUM = re.compile(r"(?:(?<=[:;,])|^)\s*(?P<k>\d{1,2})[.]\s+(?=[A-Za-zĂÂÎȘȚăâîșț])", re.M)


def _lista_numerotata(text, note):
    """r11 (industrial #53): „plecari: 1. Iluminat hala - 12 kW; 2. Prize 3P 32A - 4 buc; …” — numărul de ordine nu e
    o valoare; „Nume - 12 kW” = „Nume 12 kW”; „Prize 3P 32A - 4 buc” = 4 × priză 3P 32 A."""
    if len(RE_LISTA_NUM.findall(text)) < 2:
        return text
    k = [int(m.group("k")) for m in RE_LISTA_NUM.finditer(text)]
    if k[:2] != [1, 2] and k[:2] != [0, 1]:
        return text
    t = RE_LISTA_NUM.sub(" ", text)
    t = re.sub(r"\s+[-–]\s+(?=\d+(?:[.,]\d+)?\s*(?:kw|kva|a|buc)\b)", " ", t, flags=re.I)
    t = re.sub(rf"(?P<nume>[A-Za-zĂÂÎȘȚăâîșț][\w ăâîșțĂÂÎȘȚ]*?)\s+(?P<a>\d+)\s*A\s+(?P<n>\d+)\s*buc\w*\.?",
               lambda m: f"{m.group('n')} x {m.group('nume').strip()} {m.group('a')}A", t)
    note.append("listă numerotată („1. … 2. …”): numerele de ordine nu sunt valori; „Nume - 12 kW” = Nume 12 kW")
    return t


_RET = r"(?:trifazat\w*|trifazic\w*|monofazat\w*|monofazic\w*|mono\b|tri\b)"
_SP = r"(?:tn-c-s|tn-s|tn-c|tt)"
RE_AUTO_RETEA = re.compile(rf"(?P<v>\b{_RET}(?:\s+(?:[13]\s*[x×]\s*)?\d+\s*a)?)(?P<mij>[^.;]{{0,10}}?)(?:\.{{2,}}|…|[,;.])?\s*(?:de\s+fapt|scuze|pardon|corectez|gresit)"
                           rf"\s*,?\s*(?:nu\s*,?\s*)?(?:(?:scuze|pardon)\s*,?\s*)?(?:e|este|e\s+de\s+fapt)?\s*(?P<nou>{_RET}(?:\s+(?:[13]\s*[x×]\s*)?\d+\s*a)?)")
RE_AUTO_SP = re.compile(rf"(?P<v>\b{_SP})\b(?P<mij>[^.]{{0,60}}?)[.,;]\s*(?:nu|scuze|pardon|de\s+fapt|corectez)\s*,?\s*(?:(?:nu|scuze|pardon)\s*,?\s*)?"
                        rf"(?:e|este|schema\s+e)\s+(?P<nou>{_SP})\b")


def _autocorectura_retea(text, note):
    """r11 (locuințe #9, industrial #23): „Casă trifazată 3x32A... de fapt nu, e monofazată 40 A” → monofazat 40 A;
    „Tablou TT, BMPT 50A trifazat. Nu, scuze, e TN-C-S” → TN-C-S (ultima valoare câștigă, pe rețea / schema de pământ)"""
    def f(m, t0):
        nou = t0[m.start("nou"):m.end("nou")]
        note.append(f"autocorectură pe rețea: „{t0[m.start('v'):m.end('v')].strip()}” → „{nou}” (ultima valoare scrisă câștigă)")
        return f"{nou}{t0[m.start('mij'):m.end('mij')]}"
    t = _sub(text, RE_AUTO_RETEA, f, note)

    def g(m, t0):
        nou = t0[m.start("nou"):m.end("nou")]
        note.append(f"autocorectură pe schema de pământ: „{t0[m.start('v'):m.end('v')]}” → „{nou}”")
        return f"{nou}{t0[m.start('mij'):m.end('mij')]}."
    return _sub(t, RE_AUTO_SP, g, note)


def rescrie_inainte(text: str) -> tuple[str, list[str]]:
    """înaintea tabelelor / engleză / autocorecturi (formatul brut al mesajului)"""
    note: list[str] = []
    t = text
    for f in (_csv_virgula, _lista_numerotata, _autocorectura_racord, _existent_nou, _autocorectura_retea):
        t = f(t, note)
    return (t, note) if t != text else (text, [])


# ================================================================================================= fotovoltaic
_MARCI_KTL = r"huawei|huawie|solis|sofar|growatt|goodwe"
RE_KTL = re.compile(rf"(?<![\w.,-])(?P<n>\d+)\s*[x×]\s*(?P<b1>(?:{_MARCI_KTL})\s+)?(?P<p>\d+(?:[.,]\d+)?)\s*ktl(?:-?[a-z0-9]+)*\b"
                    rf"(?P<b2>\s+(?:{_MARCI_KTL})\b)?")


def _ktl(text, note):
    """„3 x 50KTL Huawei”, „4 x 100KTL” (fără codul complet) = N × invertor P kW (marca păstrată)"""
    def f(m, t0):
        b = (m.group("b1") or m.group("b2") or "").strip()
        b = {"huawie": "Huawei"}.get(b, b.capitalize() if b else "")
        note.append(f"„{t0[m.start():m.end()].strip()}” = {m.group('n')} × invertor {m.group('p')} kW"
                    + (f" {b}" if b else "") + " (codul „…KTL” = puterea nominală)")
        return f"{m.group('n')} x invertor {m.group('p')} kW" + (f" {b}" if b else "")
    return _sub(text, RE_KTL, f, note)


RE_FIECARE_CU = re.compile(rf"(?<![\w.,])(?P<k>{_NUMW})\s+(?P<ce>tablouri\s+tgd[\w-]*|tablouri\s+(?:de\s+)?invertoare|tgd[\w-]*|tablouri"
                           rf"|acoperisuri|hale|cladiri|corpuri|campuri|zone|sectoare)\b(?P<mij>[^.;]{{0,90}}?)[,;]?\s*\b(?:fiecare|pe\s+fiecare|cate\s+unul)"
                           rf"(?:\s+(?:tablou|acoperis|hala|cladire|corp|camp))?\s+(?:cu|are|avand|contine)\s+(?:cate\s+)?(?P<m>\d+)\s*[x×]\s*"
                           rf"(?P<model>[^,;]+?)(?=\s*(?:[,;]|\.\s|\.$|$))")


def _fiecare_cu(text, note):
    """r11 (P0 fotovoltaic #44): „Două tablouri TGD-CF, câte unul pe fiecare acoperiș, fiecare cu 3 x SUN2000-50KTL-M3”
    = 6 invertoare, împărțite în 2 TGD-CF a câte 3 (nu 3)."""
    def f(m, t0):
        k, mm = _int(m.group("k")), int(m.group("m"))
        if k < 2:
            return None
        model = t0[m.start("model"):m.end("model")].strip()
        tgd = "tgd" in m.group("ce") or "tablou" in m.group("ce")
        note.append(f"„{t0[m.start():m.end()].strip()}” = {k} × {mm} = {k * mm} invertoare {model}"
                    + (f", împărțite în {k} tablouri TGD-CF a câte {mm}" if tgd else f" ({k} {m.group('ce')} a câte {mm})"))
        return f"{k * mm} x {model}" + (f" impartite in {k} tablouri TGD-CF a cate {mm}" if tgd else "")
    return _sub(text, RE_FIECARE_CU, f, note)


RE_STR_CATE = re.compile(rf"(?<![\w.,])(?P<s>\d+)\s+(?P<w>stringuri|siruri)\s+(?:a\s+|de\s+|cu\s+)?cate\s+(?P<m>\d+)\s+(?:module|panouri)\b")


def _stringuri(text, note):
    return _sub(text, RE_STR_CATE, lambda m, t0: f"{m.group('s')} stringuri x {m.group('m')} module", note,
                "„{}” = N stringuri × M module pe string")


RE_BAT_MODEL = re.compile(rf"(?<![\w.,×x])(?P<n>[2-9]|1[0-9]|doua|trei|patru|cinci|sase)\s+(?P<cuv>baterii|acumulatoare|module\s+(?:de\s+)?baterie)\s+"
                          rf"(?P<model>(?!de\b)[a-z][\w.\-]*(?:\s+(?!de\b)[a-z][\w.\-]*){{0,2}})\s+(?:de\s+)?(?P<v>{NUM})\s*kwh\b"
                          rf"(?!\s*(?:fiecare|total|in\s+total))")


def _baterii_model(text, note):
    """r11 (fotovoltaic #11): „2 baterii BOS-G 5,12 kWh” = 2 × 5,12 kWh (capacitatea unei baterii)"""
    def f(m, t0):
        n = _int(m.group("n"))
        v = _num(m.group("v"))
        note.append(f"„{t0[m.start():m.end()].strip()}” = {n} × {m.group('v')} kWh = {_f(n * v)} kWh (capacitatea unei "
                    "baterii × numărul; dacă e totalul, scrieți „în total”)")
        return f"{n} x baterii {t0[m.start('model'):m.end('model')]} {m.group('v')} kWh"
    return _sub(text, RE_BAT_MODEL, f, note)


RE_EXPORT = re.compile(rf"\b(?:{S.alternanta('limitare_injectie')})\s*(?:de\s+|la\s+|:|=|of|to)?\s*(?P<v>{NUM})\s*(?P<u>kw|mw)\b")


def _export(text, note):
    """„export cap 400 kW”, „plafon injecție 200 kW”, „putere maximă injectată 150 kW” = limitarea injecției"""
    return _sub(text, RE_EXPORT, lambda m, t0: f"injectie limitata la {m.group('v')} {t0[m.start('u'):m.end('u')]}", note,
                "„{}” = limitarea injecției (EMS / analizor la punctul de racord)")


RE_AVEM_PT = re.compile(r"\b(?:avem|are|exista|dispunem\s+de|detinem|beneficiarul\s+are|clientul\s+are)\s+(?:deja\s+)?(?:un\s+)?"
                        r"(?P<pt>pt|post\s+(?:de\s+)?(?:transformare|trafo))\b(?P<pr>\s+propri\w*)?(?!\s+nou)")


def _avem_pt(text, note):
    """r11 (fotovoltaic #4): „Avem PT propriu 400 kVA” = PT propriu EXISTENT (nu se desenează / ofertează trafo nou)"""
    def f(m, t0):
        dupa = _n(t0[m.end():m.end() + 60])
        if re.match(r"[^.;]{0,40}\b(?:nou|se\s+construieste|proiectat)", dupa):
            return None
        note.append(f"„{t0[m.start():m.end()].strip()}” = PT propriu EXISTENT (nu se desenează trafo / celule noi)")
        return "PT propriu existent"
    return _sub(text, RE_AVEM_PT, f, note)


RE_CABLU_SOLAR = re.compile(rf"(?:\b\d+\)\s*)?\bcablu\w*\s+(?:solar\w*|fotovoltaic\w*|pv|dc|c\.c\.|h1z2z2-k|pv1-f)\b[^;\n]*?(?P<s>{NUM})\s*(?:mmp|mm2|mm²|mm)\b"
                            rf"(?:\s*[-–:x×]?\s*(?P<l>{NUM})\s*m\b)?")


def _cablu_solar(text, note):
    """r11 (fotovoltaic #2): „Cablu solar 6 mmp – 1500 m” (rând de BOM) = cablul de c.c. al stringurilor — nu cablul de
    c.a. al racordului (C0). Informativ (lungimea totală a stringurilor)."""
    return _sub(text, RE_CABLU_SOLAR, lambda m, t0: f" solarcc{m.group('s')} ", note,
                "„{}” = cablul solar de c.c. al stringurilor (informativ, în lista de materiale c.c.) — NU cablul de c.a. "
                "C0 / al invertorului")


# „racord in TG existent... de fapt nu, prin BMPT nou 3x125A” — autocorectura se aplică RACORDULUI
RE_AUTO_RACORD = re.compile(r"\b(?P<v>(?:racord\w*|conectare|racordare|legat\w*)\s+(?:in|la|prin|din)\s+(?:tg|tablou\w*|pt|post\w*|bmpt|bransament)"
                            r"[^.;]*?)(?:\.{2,}|…|,|;|\s)\s*(?:de\s+fapt|scuze|pardon|corectez|gresit)\s*,?\s*(?:nu\s*,?\s*)?"
                            r"(?P<nou>(?:prin|in|la|din)\s+(?:tg|tablou\w*|pt|post\w*|bmpt|bransament)\w*[^.;,]*)")


def _autocorectura_racord(text, note):
    def f(m, t0):
        nou = t0[m.start("nou"):m.end("nou")].strip()
        note.append(f"autocorectură pe racord: „{t0[m.start('v'):m.end('v')].strip()}” înlocuit cu „{nou}”")
        return f"racord {nou}"
    return _sub(text, RE_AUTO_RACORD, f, note)


RE_GRUP_INV = re.compile(rf"(?<![\w.,])(?P<k>\d+)\s*[x×]\s*(?P<model>[a-z][\w.\-]*(?:\s+[a-z0-9][\w.\-]*){{0,2}}?)"
                         rf"(?P<st>\s+(?:existent\w*|noi|nou[aă]?|deja\s+montat\w*))?(?=\s*(?:[,;.]|\s+si\b|\s+și\b|\s+[-–—]|$))")
RE_PARDON_EXIST = re.compile(rf"\s*[-–—,;.]?\s*(?:pardon|scuze|de\s+fapt|corectez|gresit)\s*,?\s*(?:nu\s*,?\s*)?existent\w*\s+(?:sunt\s+)?(?:doar|numai)?\s*"
                             rf"(?P<e>\d+)\s*(?:,|si)?\s*(?:(?:iar\s+)?cele(?:lalte)?\s+(?P<n>\d+)\s+(?:sunt\s+)?(?:noi|nou\w*))?\s*")


def _existent_nou(text, note):
    """r11 (fotovoltaic #66): „3 x M și 2 x M existente — pardon, existente sunt doar 2, cele 3 sunt noi” → grupul de 2
    existent, grupul de 3 nou; „3 x … noi și 2 x … existente” → propoziții separate (statutul fiecărui grup)."""
    n = _n(text)
    m = RE_PARDON_EXIST.search(n)
    t = text
    if m:
        e = int(m.group("e"))
        inainte = n[:m.start()]
        grupuri = list(RE_GRUP_INV.finditer(inainte))
        if any(int(g.group("k")) == e for g in grupuri):
            out, last = [], 0
            for g in grupuri:
                k = int(g.group("k"))
                out.append(t[last:g.start()])
                st = "existente" if k == e else "noi"
                out.append(f"{t[g.start():g.end('model')]} {st}")
                last = g.end()
            out.append(t[last:m.start()])
            t = "".join(out) + ". " + t[m.end():].lstrip(" ,.;")
            note.append(f"autocorectură pe statutul existent: „{text[m.start():m.end()].strip()}” → {e} existente, restul noi")
            n = _n(t)
    # „3 x M noi și 2 x M existente” → „3 x M noi. 2 x M existente.” (statutul se citește pe propoziție)
    gr = [g for g in RE_GRUP_INV.finditer(n) if g.group("st")]
    if len(gr) >= 2 and len({("exist" in g.group("st")) for g in gr}) == 2:
        out, last = [], 0
        for a, b in zip(gr, gr[1:]):
            mij = n[a.end():b.start()]
            if re.fullmatch(r"\s*(?:,|;|si|și|plus|\+)\s*", mij):
                out.append(t[last:a.end()] + ". ")
                last = b.start()
        if out:
            out.append(t[last:])
            t = "".join(out)
            note.append("grupurile de invertoare „noi” / „existente” din aceeași frază = grupuri separate (fiecare cu statutul lui)")
    return t


RE_MODUL_TABEL = re.compile(rf"(?<![\w.,])(?P<n>\d+)\s*[x×]\s*(?P<m>[^\n;]*?\b\d{{3}}\s*wp?\b[^\n;]*?)\s+(?P<v>0[.,]\d+)\s*kw\b")


def _module_tabel(text, note):
    """rândul de modul dintr-un tabel („330 x JA Solar JAM72S30 545W 0.545 kW”) = 330 module de 545 W (nu un invertor)"""
    return _sub(text, RE_MODUL_TABEL, lambda m, t0: f"{m.group('n')} x module {t0[m.start('m'):m.end('m')]}", note,
                "„{}” = rândul modulelor PV (număr × Pmax), nu un invertor")


_SERIE_TRAFO = {"100", "160", "250", "400", "630", "800", "1000", "1250", "1600", "2000", "2500"}
RE_PT_FARA_KVA = re.compile(r"\b(?P<c>pt|post\w*\s+trafo|trafo\w*|transformator\w*)(?P<a>(?:\s+(?:existent\w*|nou|propriu|uscat|in\s+ulei|ulei))*)\s+"
                            r"(?P<v>\d{3,4})\b(?![.,]\d)(?!\s*(?:kva|kv|kw|a|m|v|mm|mmp|/|x|×))")


def _pt_fara_kva(text, note):
    """„PT existent 630.” (fără unitate) = 630 kVA (valoare din seria trafo)"""
    def f(m, t0):
        if m.group("v") not in _SERIE_TRAFO:
            return None
        note.append(f"„{t0[m.start():m.end()].strip()}”: {m.group('v')} = puterea trafo-ului ({m.group('v')} kVA, din seria standard)")
        return f"{t0[m.start():m.end()]} kVA"
    return _sub(text, RE_PT_FARA_KVA, f, note)


# ================================================================================================= industrial
RE_STATII_N = re.compile(rf"(?:\b(?:parcare\w*|garaj\w*|curte)\s+cu\s+)?(?<![\w.,])(?P<n>{_NUMW})\s+(?P<w>statii\s+de\s+incarcare\s+ve|statii\s+(?:de\s+)?incarcare|incarcatoare|wallbox\w*)"
                         rf"\s+(?:de\s+|a\s+cate\s+|cate\s+)?(?P<p>{NUM})\s*kw\b(?!\s*[x×])")


def _statii_n(text, note):
    """r11 (P0 industrial #46): „6 stații EV 22 kW” / „6 stații EV de 22 kW trifazate” = 6 plecări de câte 22 kW"""
    def f(m, t0):
        n = _int(m.group("n"))
        if n < 2:
            return None
        note.append(f"„{t0[m.start():m.end()].strip()}” = {n} stații de încărcare × {m.group('p')} kW ({n} plecări, nu una)")
        pre = _n(t0[max(0, m.start() - 12):m.start()])
        return ("plecari: " if not re.search(r"plecari\s*:?\s*$", pre) else "") + f"{n} x statie de incarcare VE {m.group('p')} kW"
    return _sub(text, RE_STATII_N, f, note)


RE_FARA_GE = re.compile(r"[,;]?\s*\b(?:" + S.alternanta("fara_ge") + r")\b(?:\s+de\s+rezerva)?")


def _fara_ge(text, note):
    """„ATS între T1 și T2, fără generator” — negația scoate GE-ul (nu e o sursă, nu se întreabă puterea lui)"""
    return _sub(text, RE_FARA_GE, " ", note, "„{}” = fără grup electrogen (declarat — nu se desenează / nu se întreabă GE)")


RE_ATS_T1T2 = re.compile(r"\bats\b(?P<mij>[^.;]{0,30}?)\bintre\s+(?:trafo\w*|transformatoar\w*)?\s*(?:t\s*1|1)\s*(?:si|și|,)\s*(?:t\s*2|2)\b")
RE_AAR_2TRAFO = re.compile(r"\b(?:2|doua|doi)\s*(?:[x×]\s*)?(?:transformatoare|trafo\w*)\b[^.]*?\bats\b")


def _ats_trafo(text, note):
    """r11 (P0 industrial #5, #29): „AAR” / „ATS între T1 și T2” la un PT cu 2 trafo, fără GE = ATS între transformatoare
    (sursa de rezervă = al doilea trafo, cupla normal deschisă) — nu grup electrogen."""
    n = _n(text)
    if re.search(r"\b(?:grup\w*\s+electrogen\w*|generator\w*|genset\w*|diesel)\b|\bge\b", n):
        return text
    t = _sub(text, RE_ATS_T1T2, lambda m, t0: "ATS intre cele 2 transformatoare", note,
             "„{}” = ATS între cele 2 transformatoare (fără grup electrogen)")
    n = _n(t)
    m = RE_AAR_2TRAFO.search(n)
    if m and not re.search(r"\bats\s+intre\s+cele\s+2\s+transformatoare", n):
        a = n.rfind("ats", m.start(), m.end())
        t = t[:a] + "ATS intre cele 2 transformatoare" + t[a + 3:]
        note.append("„AAR / ATS” la PT cu 2 transformatoare (fără GE) = anclanșarea automată a rezervei între trafo: cupla JT "
                    "normal deschisă + AAR (aar)")
    return t


RE_BARA_VIT = re.compile(r"(?:,\s*|\b)pe\s+bar(?:a|e)\s+(?P<c>vital\w*|esential\w*|de\s+siguranta|prioritar\w*|normal\w*|nevital\w*|neprioritar\w*)\s*:")
RE_VIT_PAR = re.compile(r"\bpe\s+consumatorii\s+(?P<c>vitali|prioritari|esentiali)\s*\((?P<l>[^()]*)\)")
RE_NEVIT_PAR = re.compile(r"(?:,\s*)?\b(?:nevitalii|consumatorii\s+nevitali|neprioritarii|ceilalti(?:\s+consumatori)?|restul(?:\s+consumatorilor)?)\s*\((?P<l>[^()]*)\)"
                          r"\s*(?:raman|sunt|merg)?\s*(?:doar|numai)?\s*(?:pe|din)\s+retea\w*")


def _vitali(text, note):
    """r11 (P0 industrial #8, #30): „pe bara vitală: …; pe bara normală: …”, „ATS pe consumatorii vitali (…). Nevitalii
    (…) rămân doar pe rețea” → „Vitali: … . Nevitali: … .” (formatul citit de extrage_ge: vital true / false)"""
    t = _sub(text, RE_BARA_VIT, lambda m, t0: ". Vitali:" if re.match(r"vital|esential|de\s+sig|prioritar", m.group("c"))
             else ". Nevitali:", note, "„{}” = bara vitală (pe GE prin ATS) / bara normală (doar rețea)")
    t = _sub(t, RE_VIT_PAR, lambda m, t0: f". Vitali: {t0[m.start('l'):m.end('l')]}.", note,
             "„{}” = consumatorii vitali (pe GE prin ATS)")
    t = _sub(t, RE_NEVIT_PAR, lambda m, t0: f". Nevitali: {t0[m.start('l'):m.end('l')]}.", note,
             "„{}” = consumatori nevitali — doar pe rețea (nu intră în sarcina GE)")
    if t != text:
        t = re.sub(r"\.\s*\.(?!\.)", ".", t)
    # „Doar 2 circuite pe GE: compresor 2,2 kW și autoclavă 3 kW, restul (AC 7 kW, prize 4 circ, iluminat 2 kW) doar pe rețea”
    t2 = _sub(t, re.compile(r"\b(?:doar|numai)\s+(?:\d+\s+)?(?:circuite|consumatori|plecari)\s+pe\s+ge\s*:"), lambda m, t0: ". Vitali:", note,
              "„{}” = consumatorii de pe GE (vitali)")
    t2 = _sub(t2, re.compile(r",\s*restul\s*\((?P<l>[^()]*)\)\s*(?:doar|numai)\s+pe\s+retea\w*"),
              lambda m, t0: f". Nevitali: {t0[m.start('l'):m.end('l')]}.", note, "„{}” = restul consumatorilor doar pe rețea")
    return t2


RE_ALIM_LANT = re.compile(r"\b(?P<a>tg\w*|td[\w.\-]*|te[\w.\-]*|tablou\w*)\s+alimenteaza\s+(?P<b>(?:td|te)[\w.\-]*(?:\s*(?:,|si)\s*(?:td|te)[\w.\-]*)*)")


def _cascade_sursa(text, note):
    """r11 (industrial #62): „Tablou TE alimentat din TD-2 care e alimentat din TG, iar TG din PT 400 kVA” — lanțul de
    surse e UNA singură (sursa directă = TD-2), nu „două surse”; „TG alimentează TD1, TD1 alimentează TD1.1 și TD1.2”"""
    n = _n(text)
    m = re.search(r"\balimentat\w*\s+din\s+(?P<d>t[dge][\w.\-]*)\s+(?:care\s+(?:e|este)\s+)?alimentat\w*\s+din\s+(?P<u>t[dge][\w.\-]*)"
                  r"(?:\s*,?\s*(?:iar|si)\s+(?P=u)\s+din\s+(?P<s>pt\b[^.;,]*|post\w*[^.;,]*|bmpt[^.;,]*))?", n)
    if m:
        d = text[m.start("d"):m.end("d")]
        lant = text[m.end("d"):m.end()].strip()
        note.append(f"lanț de alimentare „{text[m.start():m.end()].strip()}”: sursa directă a tabloului = {d.upper()} (amonte: "
                    f"{lant}) — o singură sursă, nu două")
        return text[:m.start()] + f"alimentat din {d} existent" + text[m.end():]
    return text


RE_NH_N = re.compile(rf"\b(?P<n>\d+)\s+plecari\s+(?:nh|mccb|acb|cu\s+sigurante\s+nh|cu\s+mccb)?\s*:\s*(?P<l>(?:\d+\s*[x×]\s*{NUM}\s*a\s*(?:,|si|\+)?\s*)+)")


def _plecari_nh(text, note):
    """r11 (industrial #40): „TGJT cu 6 plecări NH: 3 x 250 A, 2 x 160 A, 1 x 400 A” = plecările (Σ = 6)"""
    def f(m, t0):
        gr = re.findall(rf"(\d+)\s*[x×]\s*({NUM})\s*a", m.group("l"))
        if sum(int(a) for a, _ in gr) != int(m.group("n")):
            return None
        note.append(f"„{t0[m.start():m.end()].strip()}” = {m.group('n')} plecări: " + ", ".join(f"{a} × {b} A" for a, b in gr))
        return "plecari " + ", ".join(f"{a} x {b}A" for a, b in gr) + ". "
    return _sub(text, RE_NH_N, f, note)


RE_SAGEATA = re.compile(r"\b(?P<tg>tg\w*|tgd\w*|tablou\w*(?:\s+general)?)\s*\((?P<src>[^()]*)\)\s*(?:->|→|=>|-->)\s*(?P<rest>[^\n]+)$")
RE_SEG_TD = re.compile(rf"^\s*(?P<nume>(?:td|te|tablou)[\w.\-]*(?:\s+[\w.\-]+)?)\s*(?:\(\s*(?:l\s*=\s*)?(?P<l>{NUM})\s*m\s*\))?\s*:\s*(?P<it>.+)$")


def _sageata_td(text, note):
    """r11 (industrial #38): „TG (din PT 1000 kVA, TN-S) -> TD-P1 (L=60 m): iluminat 6 kW, …; TD-P2 (L=85 m): …” =
    TG cu plecările TD-P1, TD-P2 … (fiecare cu lungimea și circuitele lui)"""
    n = _n(text)
    m = RE_SAGEATA.search(n)
    if not m:
        return text
    segs = [x for x in re.split(r";", text[m.start("rest"):m.end("rest")]) if x.strip()]
    out = []
    for sg in segs:
        ms = RE_SEG_TD.match(_n(sg))
        if not ms:
            return text
        nume = sg[ms.start("nume"):ms.end("nume")].strip()
        L = f" {ms.group('l')} m" if ms.group("l") else ""
        out.append(f"{nume}{L} ({sg[ms.start('it'):ms.end('it')].strip().rstrip('.')})")
    note.append(f"cascada „{text[m.start():m.end()][:60].strip()}…” = {text[m.start('tg'):m.end('tg')]} cu plecările "
                + ", ".join(o.split(' (')[0] for o in out))
    return (text[:m.start()] + f"{text[m.start('tg'):m.end('tg')]} {text[m.start('src'):m.end('src')]}. Plecari: "
            + ", ".join(out) + text[m.end():])


_TDN = r"(?:td|te|tg|tablou)[\w\-]*(?:\.\d+)*(?![\w\-]|\.\d)"
RE_ALIM = re.compile(rf"\b(?P<a>{_TDN})\s+alimenteaza\s+(?P<b>{_TDN}(?:\s*(?:,|si)(?!\s*{_TDN}\s+(?:alimenteaza|are)\b)\s*{_TDN})*)")
_IT = r"(?:[^,.;]|(?<=\d)[.,](?=\d))+"
RE_ARE = re.compile(rf"\b(?P<a>{_TDN})\s+are\s+(?P<it>{_IT}(?:,(?!\s*{_TDN}\s+are\b)\s*{_IT})*)")


def _arbore_alimenteaza(text, note):
    """r11 (industrial #39): „TG alimentează TD1, TD1 alimentează TD1.1 și TD1.2. TD1.1 are 5 kW iluminat, TD1.2 are un
    cuptor de 20 kW” → „Plecari: TD1 (TD1.1 (5 kW iluminat), TD1.2 (cuptor 20 kW))” (arborele tablourilor)"""
    n = _n(text)
    muchii = [(m.group("a"), [x for x in re.split(r"\s*(?:,|\bsi\b)\s*", m.group("b")) if x]) for m in RE_ALIM.finditer(n)]
    if not muchii or sum(len(b) for _, b in muchii) < 2:
        return text
    cont = {m.group("a"): text[m.start("it"):m.end("it")].strip() for m in RE_ARE.finditer(n)}
    copii = {}
    for a, bs in muchii:
        copii.setdefault(a, []).extend(bs)
    toti_copii = {b for bs in copii.values() for b in bs}
    radacini = [a for a in copii if a not in toti_copii]
    if len(radacini) != 1:
        return text
    orig = {}
    for m in re.finditer(_TDN, n):
        orig.setdefault(m.group(0), text[m.start():m.end()])

    def nod(x):
        interior = [nod(y) for y in copii.get(x, [])]
        if x in cont:
            interior.append(re.sub(r"^(?:un|o)\s+", "", cont[x]))
        return orig.get(x, x).upper() + (f" ({', '.join(interior)})" if interior else "")
    arbore = ", ".join(nod(y) for y in copii[radacini[0]])
    t = text
    for rx in (RE_ARE, RE_ALIM):
        t = _sub(t, rx, lambda m, t0: " ", [])
    t = re.sub(r"(?:\s*[,.;]\s*){2,}", ". ", t).strip(" ,.;")
    note.append(f"arborele tablourilor din „… alimentează …”: {orig.get(radacini[0], radacini[0]).upper()} → {arbore}")
    return f"{orig.get(radacini[0], radacini[0]).upper()}. Plecari: {arbore}. {t}"


RE_SPRE_TD = re.compile(rf"\b(?P<n>\d|doua)\s+plecari\s+(?:spre|catre|pentru)\s+(?P<l>(?:td|te)[\w.\-]*(?:\s*(?:,|si)\s*(?:td|te)[\w.\-]*)+)\s*,?\s*"
                        rf"fiecare\s+cu\s+(?P<p>{NUM})\s*kw(?:\s+instalat\w*)?\s*(?:si|,)\s*ks\s*(?:=|de)?\s*(?P<ks>{NUM})")


def _spre_td_ks(text, note):
    """r11 (industrial #52): „2 plecări spre TD-Prod1 și TD-Prod2, fiecare cu 250 kW instalat și ks 0,6” = 2 plecări de
    250 × 0,6 = 150 kW (cererea fiecărui TD)"""
    def f(m, t0):
        tds = [t0[x.start() + m.start("l"):x.end() + m.start("l")] for x in re.finditer(r"(?:td|te)[\w.\-]*", m.group("l"))]
        pc = _num(m.group("p")) * _num(m.group("ks"))
        note.append(f"„{t0[m.start():m.end()].strip()}” = {len(tds)} plecări: Pi {m.group('p')} kW × ks {m.group('ks')} = "
                    f"{_f(pc)} kW fiecare")
        return "plecari: " + ", ".join(f"{x} {_f(pc)} kW" for x in tds)
    return _sub(text, RE_SPRE_TD, f, note)


RE_PRIZE_ILUM = re.compile(r"(?<![\w.,])(?P<p>\d{1,2})\s+prize\s+(?P<l>\d{1,2})\s+(?P<w>(?:circuite\s+)?(?:iluminat|lumini))\b")
RE_N_X_CIRC = re.compile(r"(?<![\w.,])(?P<n>\d{1,2})\s+(?P<r>iluminat|prize|lumini)\s+circuite\b")
RE_N_CIRC_NUME_A = re.compile(rf"(?<![\w.,])(?P<n>\d{{1,2}})\s+circuite\s+(?P<nume>(?!de\b|prize\b|iluminat\b|ilum\b|lumini\b)[a-z][a-z ]{{1,25}}?)\s+(?P<a>\d{{1,3}})\s*a\b")


def _n_circuite(text, note):
    """„3 iluminat circuite” (din engleză) = 3 circuite iluminat; „4 circuite servere 16A” = 4 × servere 16 A"""
    text = _sub(text, RE_PRIZE_ILUM, lambda m, t0: f"{m.group('p')} prize, {m.group('l')} iluminat", note)
    t = _sub(text, RE_N_X_CIRC, lambda m, t0: f"{m.group('n')} circuite {m.group('r')}", note)
    t = _sub(t, RE_N_CIRC_NUME_A, lambda m, t0: f"{m.group('n')} x {t0[m.start('nume'):m.end('nume')]} {m.group('a')}A", note,
             "„{}” = N circuite (fiecare cu calibrul lui)")
    return t


RE_N_CIRC_DE_CATE = re.compile(rf"(?<![\w.,])(?P<n>\d{{1,2}})\s+circuite\s+de\s+(?P<r>iluminat|prize|forta|incalzire)\s+(?:de\s+)?cate\s+(?P<v>{NUM})\s*(?P<u>kw|a)\b"
                               r"(?:\s+si\s+(?P<n2>\d{1,2})\s+(?:circuite\s+)?de\s+(?P<r2>prize|iluminat))?")


def _n_circ_de_cate(text, note):
    """r11 (industrial #37): „10 circuite de iluminat de câte 1 kW și 6 de prize” = 10 × iluminat 1 kW + 6 circuite prize"""
    def f(m, t0):
        out = f"{m.group('n')} x {m.group('r')} {m.group('v')} {t0[m.start('u'):m.end('u')]}"
        if m.group("n2"):
            out += f", {m.group('n2')} circuite {m.group('r2')}"
        note.append(f"„{t0[m.start():m.end()].strip()}” = {out}")
        return "plecari: " + out
    return _sub(text, RE_N_CIRC_DE_CATE, f, note)


RE_BMPT_TABLOU = re.compile(r"(?<!din\s)(?<!prin\s)(?<!de la\s)\bBMPT\s+3x(?P<a>\d+)A\b(?P<ex>\s+existent)?")


def _bmpt_tablou(text, note):
    """r11 (P0 industrial #55): într-un tablou (nu casă / PV) „contor 3x63A” → „BMPT 3x63A” = SURSA tabloului (din BMPT
    63 A trifazat), nu 3 plecări de 63 A"""
    n = _n(text)
    if re.search(r"\bcas(?:a|ei|e)\b(?!\s+(?:scar|de\s+marcat|marcat))|\blocuint|\bapartament|\bvil[ae]\b|\bgarsonier|\bprosumator|\binvertor|\bpv\b|\bcef\b"
                 r"|fotovolt|\bpanouri|\bmarire|\bbransament\w*\s+nou", n):
        return text
    if not re.search(r"\btablou\w*|\btg\b|\btd\b|\bplecari|\bdepozit|\bmagazin|\bhal[ae]\b|\batelier|\bkw\b", n):
        return text
    return _sub(text, re.compile(r"(?<![\w-])(?<!din\s)(?<!prin\s)(?<!de la\s)bmpt\s+(?:3x)?(?P<a>\d+)\s*a\b(?:\s+trifazat\w*)?(?P<ex>\s+existent)?"),
                lambda m, t0: f"alimentat din BMPT trifazat {m.group('a')} A" + (" existent" if m.group("ex") else ""), note,
                "„{}” = sursa tabloului (BMPT trifazat), nu plecări")


RE_KVAR_NX = re.compile(rf"(?<![\w.,])(?P<n>[2-9])\s*[x×]\s*(?P<v>{NUM})\s*kvar\b")


def _kvar_nx(text, note):
    """r11 (industrial #6): „compensare 2x300 kvar” = 600 kvar (două baterii / trepte de 300)"""
    def f(m, t0):
        tot = int(m.group("n")) * _num(m.group("v"))
        note.append(f"„{t0[m.start():m.end()]}” = {_f(tot)} kvar în total ({m.group('n')} × {m.group('v')} kvar)")
        return f"{_f(tot)} kvar"
    return _sub(text, RE_KVAR_NX, f, note)


RE_TG_PT = re.compile(r"^(?P<cap>\s*(?:tg|tgd|tablou\w*)\b[^.;]{0,60}?,\s*)(?P<pt>pt\s+\d{3,4}\s*kva)\b")


def _tg_pt_sursa(text, note):
    """r11 (industrial #21): „TG hală TN-S, PT 1000 kVA, compresor …” — PT-ul scris în lista tabloului = sursa lui"""
    return _sub(text, RE_TG_PT, lambda m, t0: f"{t0[m.start('cap'):m.end('cap')]}alimentat din {t0[m.start('pt'):m.end('pt')]}",
                note, "„{}” = sursa tabloului (din PT), nu o plecare")


RE_REC_DIN_TG = re.compile(rf"^\s*(?P<r>(?:motor|pompa|ventilator|compresor|statie|utilaj)[^,;]*?{NUM}\s*kw)\s*,\s*(?:plecare\s+(?:noua\s+)?)?"
                           r"(?:din|in)\s+(?P<tg>tg\w*|tablou\w*(?:\s+general)?)\s+existent\w*\s*,?\s*")


def _rec_din_tg(text, note):
    """r11 (industrial #18): „Motor ventilator 45 kW, plecare din TG existent, cablu impus …” = plecarea nouă din TG
    existent (motorul cu cablul / lungimea / pornirea lui)"""
    return _sub(text, RE_REC_DIN_TG, lambda m, t0: f"Din {t0[m.start('tg'):m.end('tg')]} existent plecare noua: "
                f"{t0[m.start('r'):m.end('r')]}, ", note, "„{}” = plecarea nouă din tabloul existent")


RE_LINIE_COD = re.compile(rf"^\s*(?P<cod>[A-Z]{{1,3}}\d{{1,2}})\s+(?P<vals>(?:{NUM}\s*(?:kW|kVA|A|m)\s+)+)(?P<r>monofazat|trifazat)?\s*(?P<nume>[A-Za-zĂÂÎȘȚăâîșț].*?)\s*$")


def _tabel_coduri(text, note):
    """r11 (industrial #58): tabel cu „Circuit;Destinație;P;Faze;L” (după interp_tabel: „C1 2,4 kW 35 m monofazat Iluminat
    birouri”) → „Plecări: Iluminat birouri 2,4 kW 35 m monofazat, …” (faza e a circuitului, nu a tabloului)"""
    linii = text.splitlines()
    rand = [RE_LINIE_COD.match(l) for l in linii]
    if sum(1 for r in rand if r) < 2:
        return text
    pl = [f"{r.group('nume')} {r.group('vals').strip()}" + (f" {r.group('r')}" if r.group("r") else "") for r in rand if r]
    rest = [l for l, r in zip(linii, rand) if not r and l.strip()]
    note.append("tabelul de circuite (cod, destinație, P, faze, L) = plecările tabloului, fiecare cu faza și lungimea ei")
    return (" ".join(x.rstrip(".") + "." for x in rest) + " Plecari: " + ", ".join(pl)).strip()


RE_N_SCHEMA = re.compile(rf"(?<![\w.,])(?P<n>\d)\s+(?P<r>pompe|ventilatoare|compresoare|motoare)\s+(?:de\s+)?(?P<p>{NUM})\s*kw\s+"
                         rf"(?:in\s+(?:schema|configurati\w*)\s+)?\(?(?P<a>\d)\s*\+\s*(?P<b>\d)(?:\s*(?:rezerv\w*|r))?\)?"
                         r"(?P<porn>\s*,?\s*(?:pornire\s+)?cu\s+convertizor\w*(?:\s+de\s+frecventa)?|\s*,?\s*pornire\s+(?:directa|stea[\s-]*triunghi|soft[\s-]*start\w*))?")


def _n_schema(text, note):
    """r11 (industrial #44): „3 pompe de 11 kW în schema 2+1, pornire cu convertizor” = 2 active + 1 rezervă, fiecare
    plecare cu convertizorul ei (rezerva desenată, nu se adună la bilanț)"""
    if re.search(r"\bge\b|grup\w*\s+electrogen|generator|\bats\b|\baar\b", _n(text)):
        return text                       # la GE + ATS „(1+1)” e citit de extrage_ge (consumatori[].n)

    def f(m, t0):
        n, a, b = int(m.group("n")), int(m.group("a")), int(m.group("b"))
        if a + b != n:
            return None
        sg = {"pompe": "pompa", "ventilatoare": "ventilator", "compresoare": "compresor", "motoare": "motor"}[m.group("r")]
        porn = ""
        if m.group("porn"):
            pm = _n(m.group("porn"))
            porn = (" cu convertizor de frecventa" if "convertizor" in pm else " pornire directa" if "directa" in pm
                    else " pornire stea-triunghi" if "stea" in pm else " cu soft-starter")
        it = [f"{sg} {k + 1} {m.group('p')} kW{porn}" for k in range(a)] + [f"{sg} rezerva {m.group('p')} kW{porn}" for _ in range(b)]
        note.append(f"„{t0[m.start():m.end()].strip()}” = {a} active + {b} rezervă ({sg} {m.group('p')} kW): rezerva desenată, nu se adună")
        return "plecari: " + ", ".join(it)
    return _sub(text, RE_N_SCHEMA, f, note)


# ================================================================================================= locuință
RE_E_LA_M = re.compile(rf"\b(?P<r>pomp\w*(?:\s+(?:de\s+)?(?:apa|submersibil\w*|puț|put|fantana|hidrofor)\w*)*(?:\s+din\s+(?:fantana|put)\w*)?)"
                       rf"\s+(?:e|este|se\s+afla|e\s+situat\w*)\s+la\s+(?P<l>{NUM})\s*m\b(?:\s+de\s+(?:casa|tablou\w*))?\s*,?\s*(?P<p>{NUM})\s*kw\b")


def _receptor_la_m(text, note):
    """r11 (locuințe #66): „pompa de apă din fântână e la 120 m, 1,5 kW” = circuitul pompei (1,5 kW, 120 m), nu coloana"""
    return _sub(text, RE_E_LA_M, lambda m, t0: f"pompa apa {m.group('p')} kW, {m.group('l')} m",
                note, "„{}” = receptorul cu lungimea circuitului lui (nu coloana)")


RE_PRIZE_PE = re.compile(rf"\bprizele\s+(?:sunt\s+)?pe\s+(?P<c>[bcd]\s*\d+)\s+cu\s+(?:cablu\s+)?(?:(?:3\s*[x×]\s*)?(?P<s>{NUM})\s*(?:mm2|mm²|mmp|mm))"
                         rf"(?:\s*,\s*(?P<n>\d+)\s+circuite)?")


def _prize_pe(text, note):
    """r11 (locuințe #52): „prizele pe C25 cu cablu 2,5 mm2, 6 circuite” = 6 circuite de prize C25, 2,5 mm² (nu coloana)"""
    def f(m, t0):
        n = m.group("n") or "1"
        c = m.group("c").replace(" ", "").upper()
        note.append(f"„{t0[m.start():m.end()].strip()}” = {n} circuite de prize {c} cu {m.group('s')} mm² (secțiunea e a "
                    "circuitelor de prize, nu a coloanei)")
        return f"{n} circuite prize {c} cablu 3x{m.group('s')} mm2"
    return _sub(text, RE_PRIZE_PE, f, note)


RE_CEE = re.compile(rf"\b(?P<pre>(?:o\s+|1\s+)?)priz\w*\s+(?P<tri>trifazat\w*|tri|3f|3p|industrial\w*)?\s*(?:cee|industrial\w*)?\s*(?P<a>{NUM})\s*a\b"
                    r"(?P<post>\s+(?:trifazat\w*|tri|3f|3p))?")


def _cee(text, note):
    """r11 (locuințe #41): „priză trifazată CEE 32A în garaj” = circuit trifazat 32 A (priză CEE 3P+N+PE)"""
    if not re.search(r"\bcas(?:a|ei|e)\b|\blocuint|\bapartament|\bvil[ae]\b|\bgaraj", _n(text)):
        return text

    def f(m, t0):
        if not (m.group("tri") or m.group("post")) or "cee" not in _n(t0[m.start():m.end()]) and not re.search(r"trifaz|tri\b|3f|3p", m.group(0)):
            return None
        if not re.search(r"cee|trifaz|\b3p\b|\b3f\b", m.group(0)):
            return None
        note.append(f"„{t0[m.start():m.end()].strip()}” = circuit TRIFAZAT {m.group('a')} A pentru priză CEE 3P+N+PE")
        return f"{m.group('pre')}priza CEE trifazata {m.group('a')}A"
    return _sub(text, RE_CEE, f, note)


RE_MARIRE = re.compile(rf"\bmarire\w*\s+(?:de\s+)?putere\w*\s+(?:de\s+la\s+)?(?P<a>{NUM})\s*kw\s+(?P<ra>monofazat\w*|mono|trifazat\w*|tri)\s+"
                       rf"la\s+(?P<b>{NUM})\s*kw\s+(?P<rb>trifazat\w*|tri|monofazat\w*|mono)\b")


def _marire(text, note):
    """r11 (locuințe #5): „Mărire de putere de la 6 kW monofazat la 11 kW trifazat” = mărire (rețeaua NOUĂ = trifazat;
    cea veche nu e o contradicție)"""
    def f(m, t0):
        rb = "trifazat" if m.group("rb").startswith("tri") else "monofazat"
        note.append(f"„{t0[m.start():m.end()].strip()}” = mărire de putere: rețeaua nouă {rb} {m.group('b')} kW (vechiul "
                    f"branșament {m.group('a')} kW {m.group('ra')} nu e o contradicție)")
        return f"marire de putere, {rb}, Pa {m.group('b')} kW"
    t = _sub(text, RE_MARIRE, f, note)
    if t != text:      # „se înlocuiește BMPM cu BMPT 3x25A” = BMPT-ul nou (BMPM-ul vechi nu e rețeaua proiectului)
        t = _sub(t, re.compile(r"\b(?:se\s+)?inlocuieste\s+(?:bmpm\w*|bmpt\w*)\s+cu\s+(?=bmp[tm])"), "", note,
                 "„{}” = branșamentul vechi se înlocuiește (proiectul = branșamentul nou)")
        t = _sub(t, re.compile(r"\s*,?\s*tabloul\s+(?:casei\s+)?existent\s+ramane(?:\s+neschimbat)?\s*(?=,|;|\.|$)"), "", note,
                 "„{}” = tabloul existent al casei rămâne (informativ)")
    return t


RE_GEN_INTRARE = re.compile(rf"\b(?P<g>generator\w*|ge|grup\w*\s+electrogen\w*)\s+(?:de\s+rezerva\s+)?(?P<v>{NUM})\s*kva\s+pe\s+intrarea\s+gen\w*"
                            r"(?:\s+a\s+invertorului)?")


def _gen_intrare(text, note):
    """r11 (locuințe #58): „generator de rezervă 8 kVA pe intrarea GEN a invertorului” = GE pe portul GEN al hibridului
    (informativ) — nu un invertor de 8 kW"""
    return _sub(text, RE_GEN_INTRARE, lambda m, t0: "intrarea GEN a invertorului hibrid ocupata de GE", note,
                "„{}” = grup electrogen pe portul GEN al invertorului hibrid (informativ pe planșă) — NU un invertor")


RE_TE_NOU_DIN = re.compile(r"\b(?:se\s+adauga\s+)?(?:un\s+)?(?:tablou\s+nou\s+)?(?P<te>(?:te|td)\s+[a-z]\w*)(?:\s+nou)?\s+alimentat\w*\s+(?P<r>monofazat\s+|trifazat\s+)?"
                           r"din\s+(?:tabloul\s+)?(?:existent|tg\s+existent|tabloul\s+existent)(?P<cu>\s+cu\s+(?P<c>[bcd])\s*(?P<a>\d+))?\s*,?\s*(?:cu\s+)?")
RE_EXISTENT_NESCH = re.compile(r"\b(?:tabloul|te|tg)\s+existent\s+(?:cu\s+\d+\s+circuite\s+)?(?:ramane|nu\s+se\s+modifica)\s+(?:neschimbat|asa|la\s+fel)?\s*[;,.]\s*")


def _te_nou(text, note):
    """r11 (locuințe #28, #45): „Tabloul existent cu 8 circuite rămâne neschimbat; se adaugă tablou nou TE mansardă
    alimentat din existent cu C32, cu 4 prize …” = tabloul secundar nou (din TG existent, protejat cu C32) cu circuitele lui"""
    t = _sub(text, RE_EXISTENT_NESCH, lambda m, t0: "", note, "„{}” = tabloul existent rămâne neschimbat (informativ, nu se desenează)")

    def f(m, t0):
        te = t0[m.start("te"):m.end("te")]
        r = (m.group("r") or "").strip()
        prot = f", intreruptor general {m.group('a')} A" if m.group("a") else ""
        note.append(f"„{t0[m.start():m.end()].strip()}” = tabloul secundar {te} alimentat din tabloul existent"
                    + (f" (protecție C{m.group('a')} în tabloul existent)" if prot else ""))
        return f"{te} {r + ' ' if r else ''}alimentat din TG existent{prot}: "
    return _sub(t, RE_TE_NOU_DIN, f, note)


_TYPO_R11 = [(r"\bcas\b(?=\s+(?:mnofaz|monofaz|trifaz|tri|mono)\w*)", "casa"), (r"\bmnofaz", "monofaz"), (r"\btrifzat", "trifazat"),
             (r"\bprz\b", "prize"), (r"\bpriz\b", "prize"), (r"\bboilr\b", "boiler"), (r"\bboilerr\b", "boiler"),
             (r"\bilumn\w*", "iluminat"), (r"\bluimin\w*", "lumini"), (r"\bcuptr\b", "cuptor")]


RE_DOAR_TE_ORD = re.compile(r"^\s*doar\s+tablou\w*(?:\s+\w+)?\s*,\s*(?P<te>(?:te|td)\s+\w+)\s*:\s*(?P<it>.+?)\s*,\s*"
                            r"(?P<al>alimentat\w*\s+(?:monofazat\w*\s+|trifazat\w*\s+)?din\s+(?:te|td|tg)\s*\w*)\s*\.?\s*$")


def _doar_te(text, note):
    """„Doar tabloul băii, TE baie: 2 prize, …, alimentat monofazat din TE apartament” → „TE baie alimentat monofazat din
    TE apartament: 2 prize, …” (tabloul secundar cu circuitele lui)"""
    def f(m, t0):
        it = re.sub(r"(?<![\w.,])(\d{1,2})\s+(prize|iluminat)\b(?!\s+\d)", r"\2 \1 circuite", t0[m.start('it'):m.end('it')])
        return f"{t0[m.start('te'):m.end('te')]} {t0[m.start('al'):m.end('al')]}. Plecari: {it}"
    return _sub(text, RE_DOAR_TE_ORD, f, note, "„{}” = doar tabloul secundar (cu circuitele lui), fără branșament")


def _typo(text, note):
    t = text
    for rx, rep in _TYPO_R11:
        t = re.sub(rx, rep, t, flags=re.I)
    if t != text:
        note.append("greșeli de tastare corectate (cas, mnofazat, prz, boilr …)")
    return t


def rescrie_dupa(text: str) -> tuple[str, list[str]]:
    """după autocorecturile r9 / r10 (înaintea cifrelor / termenilor)"""
    note: list[str] = []
    t = text
    for f in (_typo, _doar_te, _te_nou, _module_tabel, _pt_fara_kva, _ktl, _fiecare_cu, _stringuri, _baterii_model, _export, _avem_pt,
              _cablu_solar, _n_schema, _kvar_nx, _tg_pt_sursa, _rec_din_tg, _tabel_coduri, _statii_n, _fara_ge, _ats_trafo, _vitali, _cascade_sursa, _sageata_td, _arbore_alimenteaza,
              _spre_td_ks, _n_circuite, _n_circ_de_cate, _bmpt_tablou, _plecari_nh, _receptor_la_m,
              _prize_pe, _cee, _marire, _gen_intrare):
        t = f(t, note)
    return (t, note) if t != text else (text, [])


# ================================================================================================= după reguli
RE_UPS_KVA = re.compile(rf"\bups\b(?P<adj>(?:\s+(?:trifazat\w*|monofazat\w*|tri|mono|online|on-line|de|cu\s+dubla\s+conversie|modular))*)\s*"
                        rf"(?P<v>{NUM})\s*(?P<u>kva|kw)\b")
RE_PT_CUV = re.compile(r"\bpost\w*\s+(?:de\s+)?(?:transformare|trafo)|\btransformator\w*|\btrafo\w*|\b20\s*/\s*0[.,]4|\bcelul\w*\s+mt")


RE_DOAR_TE = re.compile(r"^\s*(?:doar\s+tablou\w*(?:\s+\w+)?\s*,?\s*)?(?:te|td|tablou\w*\s+secundar\w*)\s+[a-z]\w*(?:\s+nou)?\s+"
                        r"(?:monofazat\w*\s+|trifazat\w*\s+)?alimentat\w*\s+(?:monofazat\w*\s+|trifazat\w*\s+)?din\s+(?:te|td|tg|tablou)\b"
                        r"|^\s*doar\s+tablou\w*\s+(?:baii|bai|bucatariei|garajului|mansardei|\w+)\b")
RE_BRANS_CUV = re.compile(r"\bbransament\w*|\bbmp[mt]\w*|\bcontor\w*|\bpa\b|\bputere\w*\s+aprobat\w*|\bq\s*\d|\bq\s+(?:3\s*×\s*)?\d")


def corecteaza_tip(c, tip):
    """r11 (locuințe #45): „Doar tabloul băii, TE baie: …, alimentat monofazat din TE apartament” = tablou secundar
    (fără branșament / BMPM inventate)."""
    if tip == "locuinta" and RE_DOAR_TE.search(c.t) and not RE_BRANS_CUV.search(c.t) and not re.search(
            r"\b(?:cas(?:a|ei)|locuint\w*|apartament\w*)\s+(?:e\s+|este\s+)?(?:mono|tri|monofaz|trifaz|\d)", c.t):
        c.nota("doar tabloul secundar (alimentat din tabloul existent) — fără branșament / contor")
        c.consumat, c.citit = [], []          # citirea „locuință” din detecteaza_tip nu se păstrează
        return "tablou"
    return _corecteaza_ups(c, tip)


def _corecteaza_ups(c, tip):
    """r11 (P0 industrial #33): „UPS trifazat 200 kVA 1+1 …, ieșire pe TD-DC cu 10 plecări” = tablou cu UPS — kVA-ul e
    al UPS-ului, nu al unui PT (fără cuvinte de PT în text)"""
    if tip in ("pt", None, "bransament") and RE_UPS_KVA.search(c.t) and not RE_PT_CUV.search(c.t) \
            and not re.search(r"\bPT[A-Z]*\b", c.orig):
        c.nota("„UPS … kVA”: puterea e a UPS-ului (nu a unui post de transformare) → tablou cu plecare UPS")
        c._ups_tip = True
        return "tablou"
    return tip


def _toate_pl(pl):
    for p in pl or []:
        yield p
        yield from _toate_pl(p.get("copii"))


def _ups(c, intr, ex, tip, I):
    m = RE_UPS_KVA.search(c.t)
    if not m or tip != "tablou":
        return
    v = I._nr(I.numar(m.group("v")))
    pl = intr.get("plecari") or []
    u = next((p for p in _toate_pl(pl) if p.get("ups") or p.get("receptor") == "ups"), None)
    bypass = bool(re.search(r"\bby-?pass\w*", c.t))
    if u is None and not getattr(c, "_ups_tip", False):
        return
    if u is None:
        u = {"nume": f"UPS {I.fmt(v)} {'kVA' if m.group('u') == 'kva' else 'kW'}", "ups": True}
        alimenteaza = re.search(r"\b(?:alimenteaza|iesire\w*|dupa\s+ups|din\s+ups|in\s+aval)\b", c.t)
        if pl and alimenteaza:
            u["copii"] = pl
        intr["plecari"] = [u] if u.get("copii") else pl + [u]
    if not u.get("copii"):        # r11 (industrial #15): „alimentează TD IT: 6 rack-uri a câte 5 kW, monofazate”
        mr_ = re.search(rf"\b(?P<n>\d+)\s+(?P<w>rack\w*(?:-uri)?|servere|pdu\w*|circuite\s+[a-z]+)\s+(?:a\s+)?(?:cate\s+|de\s+)?(?P<p>{NUM})\s*kw\b"
                        r"(?P<mono>\s*,?\s*monofazat\w*)?", c.t)
        if mr_:
            n_, p_ = int(mr_.group("n")), I._nr(I.numar(mr_.group("p")))
            w_ = re.sub(r"-uri$|uri$", "", mr_.group("w"))
            u["copii"] = [dict({"nume": f"{w_.capitalize()} {k + 1}", "P_kW": p_},
                               **({"retea": "mono", "faza": ("L1", "L2", "L3")[k % 3]} if mr_.group("mono") else {})) for k in range(n_)]
            c.foloseste(mr_.start(), mr_.end())
            me_ = re.search(r"\bechilibrat\w*\s+pe\s+faze\b", c.t)
            if me_:
                c.foloseste(me_.start(), me_.end())
            if intr.get("P_kW") == p_:
                intr.pop("P_kW")
            c.nota(f"„{c.o(mr_.start(), mr_.end()).strip()}” = {n_} circuite de {I.fmt(p_)} kW pe ieșirea UPS"
                   + (", monofazate repartizate L1 / L2 / L3" if mr_.group("mono") else ""))
    u["receptor"] = "ups"
    u["Sn_kVA"] = v if m.group("u") == "kva" else I._nr(v / 0.9)
    if m.group("u") == "kva":
        u["S_kVA"] = v
    u.pop("P_kW", None)
    if bypass:
        u["bypass"] = True
        mb = re.search(r"\bby-?pass\w*(?:\s+(?:static|de\s+mentenanta|manual\w*))*(?:\s+si\s+by-?pass\w*(?:\s+(?:static|de\s+mentenanta|manual\w*))*)?", c.t)
        if mb:
            c.foloseste(mb.start(), mb.end())
    if re.search(r"\bintrari\s+separate\b", c.t):
        u["intrari_separate"] = True
        mi = re.search(r"\bintrari\s+separate(?:\s+(?:redresor|si|by-?pass))*", c.t)
        c.foloseste(mi.start(), mi.end())
    if re.search(r"\bmonofaz\w*|\bmono\b", m.group("adj") or ""):
        u["retea"] = "mono"
    mr = re.search(r"\b(?:in\s+)?(?:configurati\w*\s+)?(?P<a>\d)\s*\+\s*(?P<b>\d)(?:\s+(?:redundant\w*|paralel\w*|in\s+paralel))*", c.t)
    if mr:
        c.foloseste(mr.start(), mr.end())
        c.intrebari.append(("I14", f"„{c.o(mr.start(), mr.end()).strip()}”: UPS-uri redundante în paralel — desenez un UPS de "
                                   f"{I.fmt(u['Sn_kVA'])} kVA (al doilea identic, în paralel, cu aceeași protecție); confirmați "
                                   "sau descrieți modulele separat?"))
    c.foloseste(m.start(), m.end())
    for mm in re.finditer(r"\bups\b(?:\s+(?:online|on-line))?|\bonline\b|\bintrarea\s+ups\b", c.t):
        c.foloseste(mm.start(), mm.end())
    c.nota(f"„{c.o(m.start(), m.end()).strip()}” = UPS (receptor „ups”, Sn {I.fmt(u['Sn_kVA'])} kVA"
           + (", cu bypass" if bypass else "") + (", cu tabloul din aval" if u.get("copii") else "") + ") — nu post de transformare")
    c.intrebari[:] = [q for q in c.intrebari if not re.match(r"Confirmați \d+ kVA", q[1])]


def _aar(c, intr, ex, tip, I):
    if tip == "pt" and intr.get("n_trafo") == 2 and intr.get("sursa_rezerva") == "trafo" and intr.get("comutare") == "ATS":
        intr["aar"] = ex["aar"] = True
        if intr.get("cupla") != "inchisa":
            intr["cupla"] = ex["cupla"] = "deschisa"
        c.nota("ATS / AAR între cele 2 transformatoare = cupla JT normal deschisă + AAR (aar: true): la pierderea unui trafo, "
               "QC închide automat (interblocaj 2 din 3)")


def _grupa(c, intr, ex, tip, I):
    if tip not in ("pt", "cef", "tablou") or intr.get("grupa_conexiuni"):
        return
    g = S.grupa_conexiuni(c.orig if len(c.orig) == len(c.t) else c.t)
    if g and (tip == "pt" or intr.get("pt_Sn_kVA") or intr.get("Sn_kVA")):
        intr["grupa_conexiuni"] = ex["grupa_conexiuni"] = g[0]
        c.foloseste(g[1], g[2])
        c.nota(f"„{c.o(g[1], g[2]).strip()}” = grupa de conexiuni a transformatorului ({g[0]}) — pe planșă și în listă")


def _ge_post(c, intr, ex, tip, I):
    if tip != "ge_ats":
        return
    cons = intr.get("consumatori") or []
    if any(x.get("vital") is False for x in cons) or re.search(r"\bbar\w*\s+(?:vital\w*|esential\w*|normal\w*)", c.t):
        intr["bara_vitala"] = ex["bara_vitala"] = True     # r11: TG cu bară normală (rețea) + bară vitală (GE prin ATS)
        c.nota("bară normală (doar rețea) + bară vitală (rețea / GE prin ATS): ATS-ul și GE-ul alimentează doar consumatorii vitali")
    sn = intr.get("Sn_GE_kVA")
    for x in intr.get("consumatori") or []:
        if x.get("pornire") == "directa" and sn and (x.get("P_kW") or 0) > 0.25 * sn:
            c.avert.append(f"{x['nume']} {I.fmt(x['P_kW'])} kW cu pornire DIRECTĂ pe GE {I.fmt(sn)} kVA: curentul de pornire "
                           f"(≈ 6–7·In) depășește mult capacitatea GE — cădere de tensiune / oprirea GE la pornire; "
                           "pornire progresivă (soft-starter / convertizor) sau GE mai mare")
            c.intrebari.append(("I08", f"{x['nume']} {I.fmt(x['P_kW'])} kW pornit DIRECT pe GE {I.fmt(sn)} kVA: GE-ul nu poate porni "
                                       "motorul (cădere de tensiune > 20 %). Soft-starter / convertizor, sau GE mai mare?"))
            break
    mc = re.match(r"\s*(?P<h>[^,;:.\d]{6,70}?)\s*(?=,)", c.t)
    if mc and not re.search(r"\d", mc.group("h")):
        c.foloseste(mc.start("h"), mc.end("h"))                  # titlul („Stație pompare apă potabilă izolată”)


RE_2TRAFO_GE = re.compile(r"\b(?:2|two|doua|doi)\s+(?:x\s*)?(?:\d+\s*kva\s+)?(?:transformatoare|transformers|trafo\w*)")


def _pt2_ge(c, intr, ex, tip, I):
    """r11 (P0 industrial #57): PT cu 2 trafo + cuplă + GE pe bara esențială — topologie neacoperită de o singură planșă:
    refuz cinstit cu propunerea de împărțire (nu GE cu puterea trafo-ului)"""
    if tip != "ge_ats" or not RE_2TRAFO_GE.search(c.t):
        return
    c.foloseste(0, len(c.t))
    c.probleme.append(("I12", "PT cu 2 transformatoare (cuplă de bare) + GE pe bara esențială: topologia nu se desenează pe o "
                              "singură planșă de aplicație (I12).",
                       "Desenez separat: (1) PT-ul cu 2 trafo și cupla JT (normal deschisă / AAR) și (2) bara esențială cu GE "
                       "+ ATS (sursa de rețea = secția de bare a PT-ului)?"))


def _pv_post(c, intr, ex, tip, I):
    if tip not in ("cef", "prosumator"):
        return
    for g in intr.get("invertoare") or []:
        if isinstance(g.get("model"), str) and g["model"].endswith("?"):
            g["model"] = g["model"].rstrip("?").strip()
        if isinstance(g.get("model"), str):          # r11 (#16): „SUN2000-5KTL-L1 repartizate L1-L2-L3” — modelul curat
            g["model"] = re.sub(r"\s+(?:repartizat\w*|cate|pe|cu|montat\w*|existent\w*|noi|nou|monofazat\w*|trifazat\w*)\b.*$", "",
                                g["model"], flags=re.I).strip()
    mcc = re.search(rf"\bsolarcc(?P<s>{NUM})", c.t)
    if mcc:
        c.foloseste(mcc.start(), mcc.end())
        if tip == "cef":
            intr["cablu_cc"] = {"S_fortat": I._nr(I.numar(mcc.group("s"))), "material": "Cu", "tip_cablu": "H1Z2Z2-K"}
    # „Ik3 la bara 0,4 kV = 18 kA”, „impedanța buclei 0,05 ohm” = datele rețelei la punctul de racord
    mik = re.search(rf"\bik\s*3?\w*\s+(?:la\s+)?(?:bara|bare|punct\w*\s+de\s+racord\w*)?(?:[^=;,]|(?<=\d),(?=\d)){{0,20}}?(?:=|:|de)\s*(?P<v>{NUM})\s*ka\b", c.t)
    if mik and not intr.get("Ik3_OD_kA"):
        intr["Ik3_OD_kA"] = I._nr(I.numar(mik.group("v")))
        c.foloseste(mik.start(), mik.end())
        c.nota(f"„{c.o(mik.start(), mik.end()).strip()}” = Ik3 la punctul de racord (Ik3_OD_kA)")
    mzb = re.search(rf"\bimpedant\w*\s+(?:a\s+)?buclei\w*(?:\s+de\s+defect)?\s*(?:=|:|de)?\s*(?P<v>{NUM})\s*(?:ohm\w*|ω)", c.t)
    if mzb:
        z = I._nr(I.numar(mzb.group("v")))
        if intr.get("RA_ohm") == z:
            intr.pop("RA_ohm")
        intr["Zb_OD_ohm"] = z
        c.foloseste(mzb.start(), mzb.end())
        c.nota(f"„{c.o(mzb.start(), mzb.end()).strip()}” = impedanța buclei de defect la punctul de racord (Zb_OD_ohm), nu "
               "rezistența prizei de pământ")
    for k in ("invertor",):
        if isinstance(intr.get(k), dict) and str(intr[k].get("model", "")).endswith("?"):
            intr[k]["model"] = intr[k]["model"].rstrip("?").strip()
    # „fără panouri / doar baterie” + invertor hibrid + baterie = BESS fără câmp PV (PCS = invertorul hibrid)
    mfp = S.cauta("fara_pv", c.t)
    inv = intr.get("invertoare") or []
    if mfp and not intr.get("kWp") and not intr.get("modul") and len(inv) == 1 and inv[0].get("n", 1) == 1 \
            and (intr.get("baterie_kWh") or (intr.get("bess") or {}).get("kWh")):
        g = inv[0]
        kwh = intr.pop("baterie_kWh", None) or intr["bess"]["kWh"]
        b = {"kWh": kwh, "P_kW": g.get("Pn_kW"), "cuplaj": "ca"}
        b.update({k: g[k] for k in ("producator", "model") if g.get(k)})
        for k in ("invertoare", "invertor", "Pn_inv_kW", "hibrid", "bess"):
            intr.pop(k, None)
        intr["bess"] = b
        intr["tip_schema"] = "cef"
        c.foloseste(mfp.start(), mfp.end())
        c.nota(f"„{c.o(mfp.start(), mfp.end()).strip()}” = DOAR stocare (fără câmp PV): invertorul hibrid "
               f"{g.get('model') or I.fmt(g.get('Pn_kW')) + ' kW'} lucrează ca PCS al bateriei {I.fmt(kwh)} kWh — nu se desenează "
               "module / stringuri")
    # invertor declarat TRIFAZAT pe branșament declarat MONOFAZAT → contradicție (nu repartizare tăcută pe L1)
    mtri = re.search(r"\binvertor\w*\s+trifazat\w*|\btrifazat\w*\s+(?:invertor\w*|sun2000|\w+-\w+ktl)", c.t)
    mmono = re.search(r"\b(?:bransament\w*|bmp[mt]\w*|retea\w*|cas(?:a|ei))\s+(?:existent\w*\s+)?(?:e\s+|este\s+)?monofazat\w*(?:\s+1\s*×\s*\d+\s*a)?"
                      r"|\b1\s*×\s*\d+\s*a\b", c.t)
    if mtri and mmono and not any("trifazat" in q[1] and "monofazat" in q[1] for q in c.intrebari):
        c.foloseste(mtri.start(), mtri.end())
        c.foloseste(mmono.start(), mmono.end())
        c.intrebari.append(("I08", f"„{c.o(mtri.start(), mtri.end()).strip()}” pe „{c.o(mmono.start(), mmono.end()).strip()}”: un "
                                   "invertor trifazat nu se racordează la un branșament monofazat. Branșamentul e (sau devine) "
                                   "trifazat, sau invertorul e monofazat?"))
        for g in intr.get("invertoare") or []:
            g.pop("faza", None)
    # „Q 3x25A” / „branșament mono 32A” la prosumator = Q-ul branșamentului (verificarea Iac ≤ Q)
    if tip == "prosumator" and not intr.get("In_Q_bransament_A"):
        mq = re.search(rf"\b(?:q|bransament\w*(?:\s+(?:mono\w*|tri\w*))?)\s*(?:de\s+)?(?:[13]\s*×\s*)?(?P<a>{NUM})\s*a\b", c.t)
        if mq:
            intr["In_Q_bransament_A"] = I._nr(I.numar(mq.group("a")))
            c.foloseste(mq.start(), mq.end())
            c.nota(f"„{c.o(mq.start(), mq.end()).strip()}” = Q-ul branșamentului ({mq.group('a')} A) — Iac,max se verifică față de el")
    # racord dublu: „în BMPT și în PT propriu”
    mb = re.search(r"\bracord\w*\s+(?:in|la|prin)\s+bmpt\w*\s+si\s+(?:in|la|prin)\s+(?:pt|post)\w*(?:\s+propriu)?", c.t)
    if mb:
        c.foloseste(mb.start(), mb.end())
        c.probleme.append(("I08", f"Contradicție: „{c.o(mb.start(), mb.end()).strip()}” — două puncte de racord (I08).",
                           "Centrala se racordează prin BMPT (rețeaua OD, JT) sau în PT-ul propriu (bara JT a PT-ului)?"))
    # „injecție zero, dar ATR aprobă evacuare 100 kW”
    if intr.get("limitare_injectie_kW") == 0:
        me = re.search(rf"\b(?:atr\w*|aviz\w*)?\s*(?:aproba\w*|permite)\s+(?:o\s+)?(?:evacuare|injecti\w*)\s+(?:de\s+)?(?P<v>{NUM})\s*kw", c.t) \
            or re.search(rf"\bevacuare\w*\s+(?:aprobat\w*\s+)?(?:de\s+)?(?P<v>{NUM})\s*kw", c.t)
        if me and I.numar(me.group("v")) > 0:
            c.foloseste(me.start(), me.end())
            c.intrebari.append(("I08", f"Injecție zero, dar „{c.o(me.start(), me.end()).strip()}”: limitez injecția la 0 (EMS, "
                                       f"autoconsum) sau la {me.group('v')} kW aprobați prin ATR?"))


RE_ITEM_LOC = re.compile(rf"(?:^|(?<=[,;:]))\s*(?P<nume>(?:aparat\w*\s+de\s+)?[a-z][a-z\-]+(?:\s+(?!de\b)[a-z][a-z\-]+){{0,2}}?)\s+(?:de\s+)?(?P<v>{NUM})\s*(?P<u>kw|kva)"
                         r"(?:\s+(?P<r>trifazat\w*|monofazat\w*|tri|mono))?\s*(?=,|;|$|\.)")
_REC_MOTOR = r"strung|compresor|freza|polizor|banc\w*|circular\w*|rindea|hidrofor|moara|tocator|ventilator|pompa|sudura|aparat\s+de\s+sudura"


def _loc_post(c, intr, ex, tip, I):
    if tip != "locuinta":
        return
    al = intr.get("alimentare") or {}
    for m in re.finditer(rf"\bpompa\s+apa\s+(?P<p>{NUM})\s*kw\s*,\s*(?P<l>{NUM})\s*m\b", c.t):
        L = I._nr(I.numar(m.group("l")))
        for x in intr.get("circuite") or []:
            if x.get("receptor") == "pompa_apa" and not x.get("L_m"):
                x["L_m"] = L
                if al.get("L_coloana_m") == L:
                    al.pop("L_coloana_m")
                c.foloseste(m.start(), m.end())
                c.nota(f"„{c.o(m.start(), m.end()).strip()}” = lungimea circuitului pompei ({I.fmt(L)} m), nu a coloanei")
                break
    _loc_post2(c, intr, ex, tip, I)


def _loc_post2(c, intr, ex, tip, I):
    """CEE trifazată, numele-fantomă („Monofazat cu” = puterea TD-ului), prizele pe C25 cu 2,5 mm², vila cu N apartamente"""
    circ = intr.get("circuite") or []
    # priză CEE trifazată
    for m in re.finditer(r"\bpriza\s+cee\s+trifazata\s+(?P<a>\d+)\s*a\b(?P<loc>\s+(?:in|la|din)\s+\w+)?", c.t):
        a = int(m.group("a"))
        gen = next((x for x in circ if x.get("receptor") == "prize" and re.fullmatch(r"Priz[aă]", x.get("nume") or "")), None)
        if gen:
            circ.remove(gen)
        loc = (m.group("loc") or "").strip()
        circ.append({"nume": f"Priză CEE {a} A trifazată" + (f" ({c.o(m.start('loc'), m.end('loc')).strip()})" if loc else ""),
                     "receptor": "prize", "In_A": a, "faza": "3F", "retea": "tri"})
        c.foloseste(m.start(), m.end())
        c.nota(f"„{c.o(m.start(), m.end()).strip()}” = circuit TRIFAZAT {a} A (priză CEE 3P+N+PE, DDR 30 mA)")
    # nume-fantomă: „Monofazat cu” 3 kW = puterea tabloului secundar
    for td in intr.get("tablouri_secundare") or []:
        for x in list(td.get("circuite") or []):
            if re.fullmatch(r"(?:(?:mono|tri)fazat\w*)?(?:\s*cu)?", I._fara_diacritice(x.get("nume") or "").lower().strip()):
                td["circuite"].remove(x)
                if x.get("P_kW") and not td.get("P_kW"):
                    td["P_kW"] = x["P_kW"]
                if re.match(r"mono", I._fara_diacritice(x.get("nume") or "").lower()):
                    td["retea"] = "mono"
                c.nota(f"{td.get('nume')}: {I.fmt(x.get('P_kW') or 0)} kW = puterea tabloului secundar (nu un circuit)")
        for x in td.get("circuite") or []:
            mm = re.match(r"(?i)(?:trifazat\w*|monofazat\w*)\s+cu\s+(.+)$", x.get("nume") or "")
            if mm:
                x["nume"] = mm.group(1)[:1].upper() + mm.group(1)[1:]
    for x in circ:
        mm = re.match(r"(?i)(?:trifazat\w*|monofazat\w*)\s+cu\s+(.+)$", x.get("nume") or "")
        if mm:
            x["nume"] = mm.group(1)[:1].upper() + mm.group(1)[1:]
    # „6 circuite prize C25 cablu 3x2,5 mm2” — calibrul și secțiunea sunt ale prizelor, nu ale coloanei
    m = re.search(rf"\b(?P<n>\d+)\s+circuite\s+prize\s+(?P<c>[bcd])(?P<a>\d+)\s+cablu\s+3\s*×\s*(?P<s>{NUM})\s*mm2", c.t)
    if m:
        n, a, S_ = int(m.group("n")), int(m.group("a")), I._nr(I.numar(m.group("s")))
        pr = [x for x in circ if x.get("receptor") == "prize"]
        for x in pr:
            circ.remove(x)
        for k in range(n):
            circ.append({"nume": f"Prize {k + 1}", "receptor": "prize", "In_A": a, "curba": m.group("c").upper(),
                         "cablu": {"S_fortat": S_, "material": "Cu"}})
        al = intr.get("alimentare") or {}
        if (al.get("cablu") or {}).get("S_fortat") == S_:
            al.pop("cablu")
        if (intr.get("cablu") or {}).get("S_fortat") == S_:
            intr.pop("cablu")
        c.foloseste(m.start(), m.end())
        c.nota(f"„{c.o(m.start(), m.end()).strip()}” = {n} circuite de prize {m.group('c').upper()}{a} cu {I.fmt(S_)} mm² "
               "(declarat — verificat la Iz; coloana se dimensionează separat)")
    # vilă / clădire cu N apartamente, fiecare cu contorul lui
    mv = re.search(r"\b(?:vil\w*|cas\w*|cladire\w*|imobil\w*)\s+cu\s+(?P<n>2|3|4|doua|trei|patru)\s+apartamente\b[^.;]*", c.t)
    if mv:
        n = _int(mv.group("n"))
        c.foloseste(mv.start(), mv.end())
        c.intrebari.append(("I14", f"„{c.o(mv.start(), mv.end()).strip()}”: {n} apartamente, fiecare cu branșamentul / contorul lui "
                                   f"= {n} scheme de locuință (câte un BMPM și un TE). Desenez schema unui apartament (tip, "
                                   f"identică pentru toate {n}), sau descrieți fiecare apartament?"))
        c.nota(f"{n} apartamente cu contoare separate: planșa arată UN apartament (tip); celelalte {n - 1} sunt identice — "
               "de confirmat")
    t = c.mascat()
    circ = intr.setdefault("circuite", [])
    faze = ["L1", "L2", "L3"]
    k = sum(1 for x in circ if x.get("faza") in faze)
    for m in RE_ITEM_LOC.finditer(t):
        nume = m.group("nume")
        if not re.search(_REC_MOTOR, nume) and not m.group("r"):
            continue
        if re.match(r"(?:casa|pa|q|putere|bransament|retea|trifazat|monofazat|apartament|pompa\s+de\s+caldura)\b", nume):
            continue
        P = I.numar(m.group("v"))
        r = m.group("r") or ""
        d = {"nume": I.nume_normalizat(c.o(m.start("nume"), m.end("nume"))), "receptor": "alt_circuit", "P_kW": I._nr(P)}
        if r.startswith("tri"):
            d["faza"] = "3F"
        elif intr.get("retea") == "tri":
            d["faza"] = faze[k % 3]
            k += 1
        circ.append(d)
        c.consumat.append((m.start("nume"), m.end()))
        c.nota(f"„{c.o(m.start('nume'), m.end()).strip()}” = circuit dedicat {d['nume']} {I.fmt(P)} "
               f"{'kVA (majorant: cosφ 1)' if m.group('u') == 'kva' else 'kW'}"
               + (", trifazat" if d.get("faza") == "3F" else f", monofazat pe {d['faza']}" if d.get("faza") else ""))


RE_EXPLICIT = re.compile(r"trifaz\w*|monofaz\w*|\btri\b|\bmono\b|\b[13]f\b|\b3\s+faze\b|\b(?:o|1)\s+faz[ae]\b|\bfaz[ae]\s+si\s+nul")


def _retea_dedusa(c, intr, ex, tip, I):
    """r11 (cerința 4): rețeaua NU se presupune fără marcaj — dedusă (din BMPT 3x, 400 V, modelul invertorului, PT,
    putere) → mențiune explicită în presupus[] + `_deduse: ["retea"]` (panoul de confirmare o marchează); fără nicio
    indicație (doar „BMPT” / nimic) și cu o putere care încape în monofazat → și întrebare."""
    ret = intr.get("retea") or ex.get("retea")
    if not ret or tip not in ("tablou", "prosumator", "locuinta", "bransament", "cef") or RE_EXPLICIT.search(c.t):
        return
    if tip == "cef" and (intr.get("pt_Sn_kVA") or intr.get("racord") in ("pt",)):
        return
    surse = [(r"\b3\s*×\s*\d+(?:[.,]\d+)?\s*a\b", "„3 × … A” (trifazat)"), (r"\b1\s*×\s*\d+(?:[.,]\d+)?\s*a\b", "„1 × … A” (monofazat)"),
             (r"\b400\s*v\b", "„400 V”"), (r"\b230\s*v\b", "„230 V”"), (r"\bbmpm\w*", "BMPM (monofazat)"),
             (r"\b(?:din|de\s+la)\s+(?:pt|post)\b", "alimentarea din PT"), (r"\bbmpt\w*", "BMPT")]
    din = next((d for rx, d in surse if re.search(rx, c.t)), None)
    if din is None and tip == "tablou" and intr.get("origine") == "pt_propriu":
        return
    fortat = any("nu încape" in n or "nu încap" in n for n in c.note)
    for g in intr.get("invertoare") or []:
        if re.search(r"KTL-M\d|LP3|HP3|-3-|SG\d+CX|STP|TAURO|SYMO|-L\d\b|PRIMO|SUNNY BOY", str(g.get("model") or "").upper()):
            fortat = True
            din = din if din not in (None, "BMPT") else f"modelul invertorului {g.get('model')}"
    sig = sum((g.get("n") if isinstance(g.get("n"), int) else 1) * (g.get("Pn_kW") or 0) for g in intr.get("invertoare") or [])
    al = intr.get("alimentare") or {}
    P = max(sig, intr.get("P_kW") or 0, intr.get("Pn_inv_kW") or 0, intr.get("S_kVA") or 0, al.get("P_aprobata_kW") or 0)
    Ia = max(intr.get("Q_In_A") or 0, intr.get("In_Q_bransament_A") or 0, al.get("In_Q_bransament_A") or 0,
             intr.get("Ib_A") or 0, intr.get("In_Q1_A") or 0)
    if P * 1000 * 1.1 / 230 > 40 or Ia > 40:
        fortat = True
        din = din if din not in (None, "BMPT") else "puterea (nu încape în monofazat, BMPM max. 40 A)"
    if not fortat and tip == "tablou":
        try:
            if I._i_mono_echiv(intr, intr.get("plecari") or []) > 40:
                fortat = True
                din = din if din not in (None, "BMPT") else "suma plecărilor (nu încape în monofazat)"
        except Exception:  # noqa: BLE001
            pass
    intr["_deduse"] = sorted(set(intr.get("_deduse") or []) | {"retea"})
    ex["_deduse"] = intr["_deduse"]
    txt = "trifazat 3 × 400/230 V" if ret == "tri" else "monofazat 230 V"
    c.nota(f"REȚEA DEDUSĂ (nedeclarată explicit): {txt}" + (f" — din {din}" if din else " — fără indicație în text")
           + "; confirmați în panoul de confirmare")
    if tip == "tablou" and not intr.get("origine"):
        intr["_deduse"] = sorted(set(intr["_deduse"]) | {"origine"})
        ex["_deduse"] = intr["_deduse"]
        c.nota("SURSA tabloului nedeclarată — desenată ca BMPT (PRESUPUS, de confirmat în panou: BMPT / tablou existent / PT)")
    if din in (None, "BMPT") and not fortat and not any(
            "Rețeaua nu se presupune" in q[1] or "monofazat (230 V) sau trifazat" in q[1] or "monofazată (230 V) sau trifazată" in q[1]
            for q in c.intrebari):
        c.intrebari.append(("I02", f"Instalația este monofazată (230 V) sau trifazată (3 × 400 V)? Rețeaua nu se presupune "
                                   f"(propus: {txt}" + (", dedus din BMPT" if din else "") + ")."))


def _l_din_nume(c, intr, ex, tip, I):
    """„TD-P1 60 m” (cascadă) — lungimea din numele plecării → L_m"""
    for p in _toate_pl(intr.get("plecari")):
        nm = re.sub(r"^[\s.,;:\-]+", "", p.get("nume") or "")
        if nm != (p.get("nume") or ""):
            p["nume"] = nm[:1].upper() + nm[1:]
        m = re.search(rf"\s+(?:l\s*=\s*)?({NUM})\s*m$", p.get("nume") or "", re.I)
        if m and not p.get("L_m"):
            p["L_m"] = I._nr(_num(m.group(1)))
            p["nume"] = p["nume"][:m.start()].strip()


def _ku(c, intr, ex, tip, I):
    """r11 (industrial #24): „Pi total = 420 kW, ku = 0,65” — P de calcul = Pi × ku (nu Pi)"""
    if tip not in ("tablou", "pt"):
        return
    m = re.search(rf"\b(?:{S.alternanta('ku')})\s*(?:=|:|de)?\s*(?P<v>0[.,]\d+)", c.t)
    mpi = re.search(rf"\bp\s*i\w*\s*(?:total\w*)?\s*(?:=|:|de)?\s*(?P<v>{NUM})\s*kw", c.t)
    if m and mpi:
        for p in list(intr.get("plecari") or []):         # „Pi total = 420 kW” citit ca plecare
            if re.match(r"(?i)p\s*i\b|p\s*inst", I._fara_diacritice(p.get("nume") or "")) and p.get("P_kW") == I.numar(mpi.group("v")):
                intr["plecari"].remove(p)
                intr["P_kW"] = p["P_kW"]
    if m and mpi and intr.get("P_kW") and abs(intr["P_kW"] - I.numar(mpi.group("v"))) < 0.01:
        ku = I.numar(m.group("v"))
        intr["P_kW"] = I._nr(round(I.numar(mpi.group("v")) * ku, 1))
        if intr.get("ks") == ku:
            intr.pop("ks")
        c.foloseste(m.start(), m.end())
        c.nota(f"„{c.o(mpi.start(), mpi.end()).strip()}” × ku {I.fmt(ku)} = P de calcul {I.fmt(intr['P_kW'])} kW (Pi × ku, nu Pi)")


def post(c, intr: dict, ex: dict, tip, I):
    """completările r11 după regulile vechi (înaintea plasei de siguranță); I = modulul interpretor (utilitare)"""
    for f in (_ku, _ups, _aar, _grupa, _ge_post, _pt2_ge, _pv_post, _loc_post, _l_din_nume, _retea_dedusa):
        f(c, intr, ex, tip, I)
