"""r9: rescrierea CIFRELOR înainte de reguli (lungimea NU se păstrează — notele spun ce s-a rescris).

Clasa „cifra greșită devine putere / se pierde” (teste/r9):
  * „4 baterii Pylontech US5000 (4,8 kWh fiecare)” → „4 x baterii Pylontech US5000 4,8 kWh” (= 19,2 kWh);
  * „12 si 12 kw” → „12 kW si 12 kW” (fiecare valoare cu unitatea ei; nu 2 × 6);
  * „16 kW termic (consum max 5 kW electric)” → „5 kW electric” (puterea termică = COP × electrică, informativă);
  * „Pi = 18 kW, Pa = 14 kW” → Pi informativ, Pa câștigă (puterea de calcul); „P instalată 540 kW, P absorbită 380 kW”
    într-un bilanț → Pi informativ, P absorbită = puterea cerută a tabloului;
  * „limitate la 100 kW” lângă invertoare = setarea Pmax a FIECĂRUI invertor, nu limitarea injecției la PCC.
"""
from __future__ import annotations

import re

NUM = r"\d+(?:[.,]\d+)?"
_DIA = str.maketrans("șşțţăâîȘŞȚŢĂÂÎ", "ssttaaiSSTTAAI")


def _n(t: str) -> str:
    return t.translate(_DIA).lower()


def _f(x: float) -> str:
    return (f"{x:.2f}".rstrip("0").rstrip(".")).replace(".", ",")


def _num(s: str) -> float:
    return float(s.replace(",", "."))


RE_BAT_FIECARE = re.compile(rf"(?<![\w.,])(?P<n>\d+)\s+(?P<cuv>baterii|acumulatoare|module\s+(?:de\s+)?baterie|module\s+baterii)"
                            rf"(?P<mid>[^(),;]{{0,40}}?)\s*\(\s*(?P<v>{NUM})\s*kwh\s*(?:fiecare|/\s*buc\w*|pe\s+bucata)\s*\)", re.I)
RE_BAT_FIECARE2 = re.compile(rf"(?<![\w.,])(?P<n>\d+)\s+(?P<cuv>baterii|acumulatoare)(?P<mid>[^(),;]{{0,40}}?)\s+(?:de\s+)?"
                             rf"(?P<v>{NUM})\s*kwh\s+fiecare\b", re.I)
RE_SI_KW = re.compile(rf"(?<![\w.,×x])(?P<a>{NUM}(?:\s*,\s+{NUM})*)\s*(?P<sep>\s+si|\s+și)\s+(?P<b>{NUM})\s*(?P<u>kw|kva)\b",
                      re.I)
RE_TERMIC = re.compile(rf"(?P<t>{NUM})\s*kw\s*(?:termic\w*|th\b)\s*(?:\(|,)?\s*(?:consum\w*\s*)?(?:max\w*\s*)?(?:de\s+)?"
                       rf"(?P<e>{NUM})\s*kw\s*(?:electric\w*|el\b\.?)\s*\)?", re.I)
RE_ELECTRIC_TERMIC = re.compile(rf"(?P<e>{NUM})\s*kw\s*(?:electric\w*|el\b\.?)\s*(?:\(|,)\s*(?P<t>{NUM})\s*kw\s*(?:termic\w*|th\b)\s*\)?",
                                re.I)
RE_PI = re.compile(rf"\b(?:pi|p\s*inst\w*|puterea?\s+instalat\w*)\s*(?:=|:)?\s*(?P<v>{NUM})\s*(?P<u>kw|kva|mw)\b\s*[,;.]?\s*", re.I)
RE_PA = re.compile(rf"\b(?:pa|p\s*abs\w*|puterea?\s+(?:maxim\w*\s+)?(?:simultan\s+)?absorbit\w*|puterea?\s+aprobat\w*|p\s*aprobat\w*)"
                   rf"\s*(?:=|:)?\s*{NUM}\s*(?:kw|kva|mw)\b", re.I)


def rescrie_cifre(text: str) -> tuple[str, list[str]]:
    note = []
    t = text

    def bat(m):
        n, v = int(m.group("n")), _num(m.group("v"))
        note.append(f"„{m.group(0).strip()}” = {n} × {m.group('v')} kWh = {_f(n * v)} kWh")
        return f"{n} x {m.group('cuv')}{m.group('mid')} {m.group('v')} kWh"
    t = RE_BAT_FIECARE.sub(bat, t)
    t = RE_BAT_FIECARE2.sub(bat, t)

    def si(m):
        # „între 12 și 15 kW” / „de la 12 și …” nu sunt două valori
        pre = _n(t[max(0, m.start() - 12):m.start()])
        if re.search(r"\b(?:intre|de\s+la)\s*$", pre):
            return m.group(0)
        note.append(f"„{m.group(0).strip()}” = {m.group('a')} {m.group('u')} și {m.group('b')} {m.group('u')} (fiecare valoare cu "
                    "unitatea ei)")
        a = re.split(r"\s*,\s+", m.group("a"))
        return ", ".join(f"{x} {m.group('u')}" for x in a) + f"{m.group('sep')} {m.group('b')} {m.group('u')}"
    t = RE_SI_KW.sub(si, t)

    def termic(m):
        note.append(f"„{m.group(0).strip()}”: puterea ELECTRICĂ absorbită = {m.group('e')} kW (puterea termică "
                    f"{m.group('t')} kW = COP × P electrică, informativă)")
        return f"{m.group('e')} kW electric "
    t = RE_TERMIC.sub(termic, t)
    t = RE_ELECTRIC_TERMIC.sub(termic, t)

    if RE_PA.search(_n(t)):
        mi = RE_PI.search(_n(t))
        if mi:
            note.append(f"„{t[mi.start():mi.end()].strip(' ,;.')}” = puterea instalată (informativă); puterea de calcul = "
                        "puterea aprobată / absorbită")
            t = t[:mi.start()] + t[mi.end():]
    return t, note


# r9 (plecări fantomă): termeni care NU sunt plecări / scheme de pământ
TERMENI = [
    # prescurtări de mesaj scurt (r9 industrial #5, #53, #54)
    (re.compile(r"(?<![\w-])vent(?=\s+\d|\s*$)", re.I), "ventilator", None),
    (re.compile(r"(?<![\w-])vent\b(?=\s+[0-9])", re.I), "ventilator", None),
    (re.compile(r"(?<![\w.,])(\d+)\s*[x×]\s*m\s+(?=\d)", re.I), r"\1 x motor ", "„N x M P kW” = N motoare de P kW"),
    (re.compile(r"(?<![\w-])il(?=\s+\d)", re.I), "iluminat", None),
    (re.compile(r"(?<![\w-])pr\s+(\d+)\s*c\b", re.I), r"prize \1 circuite", "„pr Nc” = prize, N circuite"),
    # r9 (#43): „iluminat 6 circuite 230V a 1 kW” = 6 circuite de 1 kW (monofazate)
    (re.compile(r"\b(\d+)\s+circuite\s+(?:230\s*v|monofazat\w*|mono)\s+a\s+(?=\d)", re.I), r"\1 circuite de ", None),
    (re.compile(r"\b(\d+)\s+circuite\s+a\s+(?=\d)", re.I), r"\1 circuite de ", None),
    (re.compile(r"(?<![\w-])alim\.?\s+(?=pt\b|din\b|tg|bmpt)", re.I), "alimentare din ", None),
    # r9 (#71): „Tabloul general existent 400 A …, se adaugă plecare nouă pentru chiller 120 kW” = plecarea nouă din TG existent
    (re.compile(r"^\s*(?:tabloul|tablou)\s+general\s+existent\b|^\s*tg(?:-ul)?\s+existent\b", re.I), "din TG existent",
     "„{}” = sursa (TG existent); se desenează doar ce se adaugă"),
    (re.compile(r"\bse\s+(?:adauga|adaugă|prevede|monteaza|montează)\s+(?:o\s+)?(?:plecare|plecarea|plecari)\s+(?:noua|nouă|noi)\s+"
                r"(?:pentru|pt\.?|spre)\s+", re.I), "plecari: ", None),
    # r9 (locuințe #36): „din TG casa mono 7kw” — puterea casei (informativă), nu o plecare a tabloului secundar
    (re.compile(rf"\bdin\s+(tg|tablou\w*(?:\s+general)?)\s+(?:al\s+)?(?:casa|casei)\s+(?:(?:mono|tri)\w*\s+)?{NUM}\s*kw\b", re.I),
     r"din \1 casei", "„{}” = sursa (TG-ul casei); puterea casei e informativă, nu o plecare"),
    # „celula de măsură cu TT și TC” — TT = transformator de TENSIUNE (măsură), nu schema TT
    (re.compile(r"\b(?:tt\s*(?:si|și|,|\+|/)\s*tc|tc\s*(?:si|și|,|\+|/)\s*tt)\b", re.I), "transformatoare de masura",
     "„{}” în celula de măsură = transformatoare de măsură (de tensiune și de curent), nu schema TT"),
    (re.compile(r"\bplecari\s+(?:jt|de\s+joasa\s+tensiune)\b", re.I), "plecari", None),
    # „Consumatori principali: TD-Producție 250 kW, …” = lista plecărilor tabloului
    (re.compile(r"\bconsumatori(?:i)?\s+principali\s*:", re.I), "plecari:", "„{}” = lista plecărilor tabloului"),
]


RE_VAL_INAINTE_NUME = re.compile(rf"(?<![\w.,])(?P<n>\d+)\s*[x×]\s*(?P<v>{NUM})\s*(?P<u>kw|kva|a|cp|hp)\s+"
                                 r"(?P<nume>pomp\w*|motoar\w*|motor\w*|ventilat\w*|compresoa\w*|compresor\w*|extruder\w*"
                                 r"|chiller\w*|cta\b|ahu\w*)", re.I)


RE_POD = re.compile(r"\b(?P<nume>pod\w*\s+rulant\w*|macara\w*|electropalan\w*)(?:\s+(?:de\s+)?\d+(?:[.,]\d+)?\s*t(?:one)?\b)?\s*:\s*"
                    r"(?P<lista>[^.;]*?)(?=,\s*(?:alimentat\w*|din\b|cu\s+cablu)|[.;]|$)", re.I)


def _pod(m, note):
    """„pod rulant 10 t: ridicare 7,5 kW, translație 2 x 1,5 kW” = o plecare spre tabloul podului, cu motoarele lui"""
    itemi = [x.strip() for x in re.split(r"(?<!\d),|,(?!\d)|\bsi\b", m.group("lista")) if x.strip()]
    if not itemi or not all(re.search(rf"{NUM}\s*(?:kw|cp|hp)\b", x, re.I) for x in itemi):
        return m.group(0)
    note.append(f"„{m.group(0).strip()}” = plecarea spre {m.group('nume')} (tabloul lui) cu motoarele: " + ", ".join(itemi))
    return "plecari: " + m.group("nume") + " (" + ", ".join(x if re.match(r"motor", x, re.I) else f"motor {x}" for x in itemi) + ")"


RE_REZERVA = re.compile(rf"\b(?P<nume>[a-z]+)\s+(?P<v>{NUM})\s*(?P<u>kw|kva)\s+(?:de\s+)?rezerv\w*"
                        rf"(?:\s*\(\s*\d\s*[ar]?\s*\+\s*\d\s*[ar]?\s*\))?", re.I)
_PORNIRE = r"soft[\s-]*start\w*|soft\b|stea[\s-]*triunghi|y\s*/\s*d\b|vfd\b|convertizor\w*|dol\b|directa\b"


def _rezerva(m, t, note):
    """„pompă 90 kW soft starter și pompă 90 kW rezervă (1+1)” → „pompa rezerva 90 kW soft starter” (aceeași pornire)"""
    nume, v, u = m.group("nume"), m.group("v"), m.group("u")
    mp = re.search(rf"\b{re.escape(nume)}\s+{re.escape(v)}\s*{u}\s+(?P<p>{_PORNIRE})", t[:m.start()], re.I)
    note.append(f"„{m.group(0).strip()}” = unitatea de rezervă (1 activ + 1 rezervă): desenată, nu se adună la putere")
    return f"{nume} rezerva {v} {u}" + (f" {mp.group('p')}" if mp else "")


def rescrie_termeni(text: str) -> tuple[str, list[str]]:
    note = []
    t = text
    t = RE_REZERVA.sub(lambda m: _rezerva(m, text, note), t)
    t = RE_POD.sub(lambda m: _pod(m, note), t)
    # r9 (#11, #52): „BMPT 160 A cu măsură indirectă cu TC 200/5, TG magazin: …” = SURSA tabloului (nu branșament, nu plecare)
    if len(re.findall(r"\d\s*kw\b", _n(t))) >= 2 and re.search(r"\btg\b|\btablou|\bmagazin|\bplecari|\bhal[ae]\b|\batelier",
                                                             _n(t)) and not re.search(r"\bcas(?:a|ei)\b(?!\s+(?:de\s+)?marcat)|\bapartament",
                                                                                      _n(t)):
        def bm(m):
            if m.group("tc"):
                note.append(f"„{m.group('tc').strip(' ,')}” = măsura semidirectă din BMPT (TC), informativ pentru schema tabloului")
            note.append(f"„{m.group('b')}” = sursa tabloului (din BMPT)")
            return f"din {m.group('b')}"
        t = re.sub(r"(?<!din )(?<!prin )(?P<b>\bbmpt\w*\s+(?:3\s*x\s*)?\d+\s*a)\b(?P<tc>\s+cu\s+masur\w*\s+(?:in|semi)?direct\w*"
                   r"(?:\s+cu\s+tc\s+\d+\s*/\s*\d+(?:\s*a)?)?)?", bm, t, flags=re.I)
    if "\n" not in t and t.count("|") <= 3:                 # r9 (#54): „… | sursa TG | TN-S” pe un rând = separator
        t = re.sub(r"\s+\|\s+", "; ", t)
    # r9 (#66): „5 x 7.5 kW pompe DOL” (ordinea engleză) → „pompe 5 x 7.5 kW DOL”
    t2 = RE_VAL_INAINTE_NUME.sub(lambda m: f"{m.group('nume')} {m.group('n')} x {m.group('v')} {m.group('u')}", t)
    if t2 != t:
        note.append("„N x P kW <receptor>” = <receptor> N x P kW")
        t = t2
    for rx, rep, nota in TERMENI:
        m = rx.search(t)
        if m:
            if nota:
                note.append(nota.format(m.group(0).strip()))
            t = rx.sub(rep, t)
    return t, note


# r9 (locuințe #42, #44): lungimea / puterea unui receptor scrise în clauza următoare rămân pe circuitul lui (nu pe coloană)
_REC_L = (r"(?:priz\w*\s+(?:pt|pentru)\s+)?masin\w*\s+electric\w*|wallbox\w*|stati\w*\s+(?:de\s+)?incarcare(?:\s+ve)?"
          r"|stati\w*\s+ve\b|incarcator\w*|\bsauna\b|\bsaun[aă]\b|pomp\w*\s+(?:de\s+)?caldura|jacuzzi")
RE_REC_CLAUZA = re.compile(rf"(?P<rec>{_REC_L})(?P<mid>(?:(?!\d\s*kw)[^,;.]){{0,40}}?)(?<!\d),\s*(?P<p>{NUM}\s*kw)\b"
                           rf"(?P<l>\s*,\s*{NUM}\s*m\b)?(?=\s*(?:[,;.]|$))", re.I)
RE_LA_M_TABLOU = re.compile(rf",?\s*(?:la\s+)?(?:o\s+)?(?:distan\w*\s+(?:de\s+)?)?(?P<l>{NUM})\s*m\s+(?:de|fata\s+de|pana\s+la)\s+"
                            r"(?:tablou\w*|tg\b|te\b|casa|cladire)", re.I)


def rescrie_lungimi(text: str) -> tuple[str, list[str]]:
    n = _n(text)
    if not re.search(r"\bcas(?:a|ei)\b|\bapartament|\bap\b|\blocuint|\bbloc\b", n):
        return text, []
    note, t = [], text

    def f(m):
        note.append(f"„{m.group(0).strip()}” = puterea / lungimea receptorului (circuitul lui, nu coloana)")
        lung = m.group("l").strip(" ,") if m.group("l") else ""
        return f"{m.group('rec')} {m.group('p')}" + (f" {lung}" if lung else "") + m.group("mid")
    t = RE_REC_CLAUZA.sub(f, t)
    # „Distanța până la saună 25 m.” → lungimea circuitului saunei
    md = re.search(rf"[.,;]?\s*distan\w*\s+(?:pana\s+)?(?:la\s+)?(?P<r>{_REC_L})\s+(?:este\s+|e\s+|de\s+)?(?P<l>{NUM})\s*m\b\.?",
                   _n(t), re.I)
    if md:
        stem = md.group("r")[:4]
        recs = [r for r in re.finditer(rf"{re.escape(stem)}\w*[^,;]*?{NUM}\s*kw\b", _n(t[:md.start()]))]
        if len(recs) == 1:
            r = recs[0]
            note.append(f"„{t[md.start():md.end()].strip(' .,')}” = lungimea circuitului ({md.group('r')}), nu un circuit nou")
            t = t[:r.end()] + f" {md.group('l')} m" + t[r.end():md.start()] + "." + t[md.end():]
    ml = RE_LA_M_TABLOU.search(_n(t))
    if ml:
        recs = list(re.finditer(rf"(?:{_REC_L})[^,;]*?{NUM}\s*kw\b", _n(t[:ml.start()]), re.I))
        if len(recs) == 1:
            r = recs[0]
            note.append(f"„{t[ml.start():ml.end()].strip(' ,')}” = lungimea circuitului receptorului, nu a coloanei")
            t = t[:r.end()] + f" {ml.group('l')} m" + t[r.end():ml.start()] + t[ml.end():]
    return (t, note) if t != text else (text, [])


# r9 (locuințe #4): „branșament monofazat 4 kW, vrem să trecem pe trifazat 15 kW” = mărire de putere mono → tri
RE_TRECEM = re.compile(rf"\b(?:vrem|vreau|dorim|doreste|dorește|vor|vrea|ar\s+vrea)\s+(?:sa\s+|să\s+)?(?:trecem|treaca|treacă|trec|facem|marim|mărim)"
                       rf"\s+(?:pe|la)\s+(?P<r>trifaz\w*|monofaz\w*|tri|mono)\s+(?:de\s+)?(?P<p>{NUM})\s*kw\b", re.I)
RE_BRANS_VECHI = re.compile(rf"\b(?:bransament\w*|branșament\w*|bmp[mt]\w*)\s+(?P<r>monofaz\w*|trifaz\w*|mono|tri)\s+(?:de\s+)?"
                            rf"(?P<p>{NUM})\s*kw\b", re.I)


def rescrie_marire(text: str) -> tuple[str, list[str]]:
    m = RE_TRECEM.search(text)
    if not m:
        return text, []
    v = RE_BRANS_VECHI.search(text[:m.start()])
    if not v:
        return text, []
    nou = f"marire de putere de la {v.group('p')} kW {v.group('r')} la {m.group('p')} kW {m.group('r')}"
    t = text[:v.start()] + nou + text[v.end():m.start()] + text[m.end():]
    return t, [f"„{v.group(0)} … {m.group(0)}” = mărire de putere {v.group('p')} kW {v.group('r')} → {m.group('p')} kW "
               f"{m.group('r')} (proiectul = puterea nouă)"]
