"""r11: dicționarul CENTRAL de sinonime pe concepte de domeniu (SPEC §F.15).

Concluzia rundei 11: reparațiile anterioare au acoperit exact cuvântul testat („uk”, „fără rețea”, „BMPT”), nu sinonimele
lui („Ucc”, „izolat”, „contor”). De aceea fiecare CONCEPT are aici toate variantele uzuale (română cu / fără diacritice,
engleză, prescurtări) și regulile le folosesc prin acest modul, nu prin cuvinte fixe:

* `RX[concept]` — expresia regulată (pe textul normalizat: litere mici, fără diacritice) a tuturor variantelor;
* `are(concept, t)` / `cauta(concept, t)` — căutare în textul normalizat;
* `canonizeaza(text)` — rescrierea variantelor în FORMA CANONICĂ pe care o citesc regulile vechi („Ucc 4,5 %” →
  „uk 4,5 %”, „contor 3x63A” → „BMPT 3x63A”, „AAR” → „ATS”, „genset” → „GE”, „post de transformare” → „PT”,
  „8 lumini” → „8 circuite iluminat”, „wallbox” → „stație de încărcare VE” …); fiecare rescriere lasă o notă.

Rescrierea e CONTEXTUALĂ acolo unde cuvântul are și alt sens: „contor” fără calibru („contor în firida de palier”,
„RCD tip B și contor”) rămâne; „izolat” = fără rețea doar lângă un grup electrogen (nu „neutru izolat”, „cablu izolat”);
„stand-alone” lângă o baterie = BESS fără PV (nu „fără rețea”); „AAR” între transformatoare = ATS între trafo (nu GE).
"""
from __future__ import annotations

import re

NUM = r"\d+(?:[.,]\d+)?"
_DIA = str.maketrans("șşțţăâîȘŞȚŢĂÂÎ", "ssttaaiSSTTAAI")


def norm(t: str) -> str:
    return t.translate(_DIA).lower()


# --------------------------------------------------------------------------------------------- dicționarul
# concept → variantele (regex pe textul normalizat). Ordinea în listă nu contează (se compun cu „|”, lungi întâi).
SINONIME: dict[str, list[str]] = {
    # tensiunea de scurtcircuit a transformatorului
    "uk": [r"u\s*k", r"u_k", r"ucc", r"u\s*cc", r"u_cc", r"usc", r"u\s*sc", r"u_sc", r"ukr", r"z\s*k", r"z\s*cc",
           r"tensiune(?:a)?\s+(?:de\s+)?scurt[\s-]*circuit(?:\s+(?:nominal\w*|a\s+trafo\w*))?",
           r"impedant\w*\s+(?:de\s+)?scurt[\s-]*circuit", r"short[\s-]*circuit\s+(?:voltage|impedance)",
           r"impedance\s+voltage", r"(?:transformer\s+)?impedance"],
    # GE singura sursă (fără rețea publică)
    "fara_retea": [r"fara\s+retea\w*(?:\s+(?:publica|electrica|de\s+distributie))?", r"izolat\w*\s+de\s+retea\w*",
                   r"site\s+izolat\w*", r"(?:in\s+)?regim\w*\s+insular\w*", r"insular\w*", r"off[\s-]*grid", r"izolat[aei]?\b",
                   r"autonom[aei]?\b", r"stand[\s-]*alone", r"nu\s+(?:exista|avem|are)\s+retea\w*",
                   r"fara\s+(?:racord|bransament)\w*(?:\s+la\s+retea\w*)?", r"fara\s+alimentare\w*\s+din\s+retea\w*",
                   r"(?:singura|unica)\s+sursa", r"doar\s+din\s+ge\b", r"island(?:ed)?(?:\s+mode)?", r"isolated",
                   r"no\s+grid(?:\s+connection)?", r"without\s+grid"],
    # branșamentul: BMPT / BMPM / contor / firidă / cutie de branșament
    "bmpt": [r"bmpt\w*", r"bmpm\w*", r"bmp\b", r"contor\w*", r"grup\w*\s+de\s+masur\w*", r"firid\w*(?:\s+de\s+(?:bransament|racord))?",
             r"cutie\w*\s+(?:de\s+)?(?:bransament|racord|masura)\w*", r"(?:dno\s+|service\s+)?cut[\s-]*out", r"meter(?:ing)?\s+box",
             r"punct\w*\s+de\s+masur\w*", r"bloc\w*\s+de\s+masur\w*(?:\s+si\s+protecti\w*)?"],
    # comutarea automată a surselor
    "ats": [r"ats\b", r"aar\b", r"a\.a\.r\.?", r"anclansare\w*\s+automat\w*(?:\s+a\s+rezerve\w*)?", r"comutator\w*\s+automat\w*(?:\s+de\s+(?:surs\w*|transfer|retea))?",
            r"inversor\w*\s+automat\w*(?:\s+de\s+surs\w*)?", r"automatic\s+transfer\s+switch\w*", r"transfer\s+automat\w*",
            r"comutare\w*\s+automat\w*(?:\s+a\s+surselor)?", r"rezerv\w*\s+automat\w*"],
    # grupul electrogen
    "ge": [r"ge\b", r"grup\w*\s+electrogen\w*", r"generator\w*(?:\s+(?:diesel|de\s+rezerva|electric))?", r"genset\w*",
           r"diesel\s+generator\w*", r"\bdg\b", r"d\.g\.", r"motogenerator\w*", r"grup\w*\s+diesel"],
    # postul de transformare
    "pt": [r"pt\b", r"pta\b", r"ptab\b", r"ptcz\b", r"ptz\b", r"post\w*\s+(?:de\s+)?(?:transformare|trafo)", r"post\w*\s+trafo",
           r"substation", r"transformer\s+station", r"cabina\s+(?:de\s+)?transformare"],
    # grupa de conexiuni a trafo-ului
    "grupa_conexiuni": [r"[dyz]\s*[/-]?\s*[yzd]n?\s*[-\s]?(?:0|1|5|6|7|11)\b", r"[dyz]yn?\s*-?\s*\d{1,2}\b", r"[δ∆]\s*/?\s*yn?\s*-?\s*\d{1,2}\b",
                        r"grup\w*\s+de\s+conexiuni\s+\w+", r"triunghi[\s-]+stea\s+(?:cu\s+neutru\s+)?\d{1,2}"],
    # iluminat
    "iluminat": [r"iluminat\w*", r"ilum\b\.?", r"lumin[ia]\b", r"lumini\b", r"lumina\b", r"lights?\b", r"lighting",
                 r"corpuri\s+de\s+iluminat", r"spot(?:uri)?\b", r"aplice\b", r"lustr[ae]\b", r"\bl\b"],
    # tablouri
    "tablou": [r"tablou\w*", r"sub[\s-]*tablou\w*", r"panou\w*\s+(?:electric|de\s+distributie)\w*", r"subpanel\w*",
               r"sub[\s-]*panel\w*", r"db\b", r"\btg\b", r"\btd\b", r"\bte\b", r"\btgd\b", r"\btgjt\b", r"distribution\s+board"],
    # stațiile de încărcare a vehiculelor electrice
    "ve": [r"ve\b", r"ev\b", r"wallbox\w*", r"wall\s+box\w*", r"stati\w*\s+(?:de\s+)?incarcare(?:\s+(?:ve|ev|auto|masini\w*))?",
           r"stati\w*\s+(?:ve|ev)\b", r"incarcator\w*(?:\s+(?:auto|ve|ev|masin\w*))?", r"charger\w*", r"charging\s+station\w*",
           r"borne?\s+de\s+incarcare", r"punct\w*\s+de\s+incarcare"],
    # sursa neîntreruptibilă
    "ups": [r"ups\b", r"u\.p\.s\.?", r"sursa\w*\s+(?:de\s+alimentare\s+)?neintrerupt\w*", r"uninterruptible\s+power\s+suppl\w*"],
    # lipsa unei componente
    "fara_ge": [r"fara\s+(?:grup\w*\s+electrogen\w*|generator\w*|ge\b|genset\w*|diesel)", r"no\s+(?:generator|genset|ge\b)",
                r"without\s+(?:a\s+)?(?:generator|genset|ge\b)"],
    "fara_pv": [r"fara\s+(?:panouri(?:\s+(?:solare|fotovoltaice|pv))?|pv\b|fotovoltaic\w*|module\s+(?:pv|fotovoltaice))",
                r"no\s+(?:pv|solar|panels)", r"without\s+(?:pv|solar|panels)", r"doar\s+(?:o\s+)?baterie\w*"],
    # limitarea injecției
    "limitare_injectie": [r"export\s+(?:cap|limit\w*|limited\s+to)", r"limitare\w*\s+(?:a\s+)?injecti\w*", r"injecti\w*\s+limitat\w*",
                          r"limitat\w*\s+la\s+(?:o\s+)?(?:injecti\w*|evacuare)", r"plafon\w*\s+(?:de\s+)?injecti\w*",
                          r"putere\w*\s+maxim\w*\s+injectat\w*", r"export\s+(?:max\w*|maximum)"],
    # coeficienții de bilanț
    "ks": [r"ks\b", r"k\s*s\b", r"k_s\b", r"coeficient\w*\s+de\s+simultaneitate", r"factor\w*\s+de\s+simultaneitate",
           r"simultaneity\s+factor", r"diversity\s+factor"],
    "ku": [r"ku\b", r"k\s*u\b", r"k_u\b", r"coeficient\w*\s+de\s+utilizare", r"factor\w*\s+de\s+utilizare", r"utili[sz]ation\s+factor",
           r"factor\w*\s+de\s+cerere", r"demand\s+factor"],
}

# forma canonică (cuvântul pe care îl citesc regulile vechi)
CANONIC = {"uk": "uk", "fara_retea": "fara retea", "bmpt": "BMPT", "ats": "ATS", "ge": "GE", "pt": "PT", "iluminat": "iluminat",
           "tablou": "tablou", "ve": "statie de incarcare VE", "ups": "UPS", "ks": "ks", "ku": "ku"}


def _rx(variante: list[str]) -> str:
    return "|".join(sorted(variante, key=len, reverse=True))


RX = {k: re.compile(r"(?<![\w-])(?:" + _rx(v) + r")") for k, v in SINONIME.items()}


# „izolat” / „autonom” / „stand-alone” au și alte sensuri: neutru izolat (IT), cablu / conductor izolat, BESS stand-alone
RE_NU_FARA_RETEA = re.compile(r"\b(?:neutru\w*|cablu\w*|conductor\w*|conductoare|bar[ae]\w*|izolatie\w*|trafo\w*|transformator\w*"
                              r"|bateri\w*|bess|stocare|sistem\w*\s+de\s+stocare|autonomie)\s+(?:\w+\s+){0,2}$")


def fara_retea(t: str, ge: bool = True):
    """GE = SINGURA sursă: „fără rețea”, „izolat”, „insular”, „off-grid”, „autonom” … (doar lângă un GE pentru „izolat” /
    „autonom” / „stand-alone”; nu „neutru izolat”, „cablu izolat”, „BESS stand-alone”). Întoarce match-ul sau None."""
    for m in RX["fara_retea"].finditer(t):
        w = m.group(0)
        slab = re.match(r"izolat|autonom|stand|insular", w)
        if slab and (not ge or RE_NU_FARA_RETEA.search(t[max(0, m.start() - 40):m.start()])):
            continue
        return m
    return None


def are(concept: str, t: str) -> bool:
    return bool(RX[concept].search(t))


def cauta(concept: str, t: str):
    return RX[concept].search(t)


def alternanta(concept: str) -> str:
    """alternanța (fără grup de captură) — pentru a compune regulile din interpretor"""
    return r"(?:" + _rx(SINONIME[concept]) + r")"


# --------------------------------------------------------------------------------------------- grupa de conexiuni
RE_GRUPA = re.compile(r"(?<![\w/])(?P<p>[dyz])\s*[/-]?\s*(?P<s>[yzd])(?P<n>n)?\s*[-\s]?(?P<h>0|1|5|6|7|11)\b(?![.,]\d|\s*(?:kv|kva|a|m|%))", re.I)


def grupa_conexiuni(text_orig: str):
    """„Dyn11”, „Dyn 11”, „DYn-11”, „D/yn-11”, „Δyn11”, „Yzn5”, „Yyn0” → („Dyn11”, start, end) sau None."""
    t = text_orig.replace("Δ", "D").replace("∆", "D")
    for m in RE_GRUPA.finditer(t):
        p, s, n, h = m.group("p").upper(), m.group("s").lower(), (m.group("n") or "").lower(), m.group("h")
        if p == s.upper() and not n:
            continue
        if not n and p != "D" and s != "d":
            continue                              # „Y 11” / „z 5” fără n — prea ambiguu
        return f"{p}{s}{n}{h}", m.start(), m.end()
    return None


# --------------------------------------------------------------------------------------------- rescrierea canonică
def _sub(text: str, rx, rep, note: list, nota=None):
    """re.sub pe textul normalizat (pozițiile coincid: diacriticele se traduc 1:1)"""
    out, last, n = [], 0, norm(text)
    for m in rx.finditer(n):
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


# „Ucc 4,5 %”, „tensiunea de scurtcircuit de 6 %”, „u_k = 6%” → „uk 4,5 %” (doar urmat de procent)
RE_UK = re.compile(r"(?<![\w-])(?P<w>" + _rx([v for v in SINONIME["uk"] if v not in (r"u\s*k",)]) + r")\s*(?:%|\(%\))?\s*"
                   rf"(?:=|:|de|of|is)?\s*(?=(?P<v>{NUM})\s*%)")
# „contor 3x63A”, „firidă trifazată 3 x 40 A”, „cutie de branșament 63 A trifazată” → „BMPT 3x63A”
_BMPT_VAR = _rx([v for v in SINONIME["bmpt"] if not v.startswith("bmp")])
RE_BMPT_SIN = re.compile(r"(?<![\w-])(?P<w>" + _BMPT_VAR + r")(?P<mij>(?:\s+(?:trifazat\w*|trifazic\w*|monofazat\w*|monofazic\w*|tri|mono|"
                         r"existent\w*|nou|general\w*|de|cu|al|electric\w*|delgaz|electrica|enel|e-?distributie|retea\w*))*)\s*[:,]?\s*"
                         rf"(?P<q>(?:(?P<k>[13])\s*[x×]\s*)?(?P<a>{NUM})\s*a)\b")
# „AAR”, „anclanșare automată a rezervei”, „comutator automat de sursă” → „ATS”
RE_ATS_SIN = re.compile(r"(?<![\w-])(?:" + _rx([v for v in SINONIME["ats"] if v != r"ats\b"]) + r")(?:\s*\(?\s*ats\b\s*\)?|\s+ats\b)?")
# „genset”, „grup diesel”, „DG”, „motogenerator” → „GE”
RE_GE_SIN = re.compile(r"(?<![\w-])(?:genset\w*|diesel\s+generator\w*|motogenerator\w*|grup\w*\s+diesel|(?<=\s)dg\b|d\.g\.)")
# „post de transformare”, „cabina de transformare”, „substation” (fără „customer/own” — tratate de engleză) → „PT”
RE_PT_SIN = re.compile(r"(?<![\w-])(?:post\w*\s+(?:de\s+)?transformare|cabina\s+(?:de\s+)?transformare|transformer\s+station)\b")
# „U.P.S.”, „sursă neîntreruptibilă” → UPS
RE_UPS_SIN = re.compile(r"(?<![\w-])(?:u\.p\.s\.?|surs[ae]\s+(?:de\s+alimentare\s+)?neintrerupt\w*|uninterruptible\s+power\s+suppl\w*)")
# „wallbox”, „charger”, „borne de încărcare”, „stații EV” → „stație de încărcare VE”
RE_VE_SIN = re.compile(r"(?<![\w-])(?:wall\s*box\w*|ev\s+chargers?|chargers?|charging\s+stations?|borne?\s+de\s+incarcare|punct\w*\s+de\s+incarcare"
                       r"|stati(?:e|i|a|ile)\s+(?:ev|e\.v\.)(?![\w-]))")
# corpuri de iluminat / spoturi / lights → iluminat
RE_ILUM_SIN = re.compile(r"(?<![\w-])(?:lights|lighting(?:\s+circuits?)?|aplice)(?![\w-])")
# „N lumini / N lumină / N spoturi / N corpuri de iluminat / N l” = N circuite de iluminat (plural cu cifră)
RE_N_LUMINI = re.compile(r"(?<![\w.,×-])(?P<n>\d{1,2}|doua|doi|trei|patru|cinci|sase|un|o)\s*(?P<w>lumini\b|lumina\b|circuite\s+de\s+lumina\b|circuite\s+lumina\b"
                         r"|circuit\s+(?:de\s+)?lumina\b|spoturi\b|corpuri\s+de\s+iluminat\b|iluminat(?=\s*(?:,|;|\.|$|\s+si\b|\s+plus\b|\s+\d))|ilumin\b)")
# „8p 6l” (mesaj scurt) = 8 circuite de prize, 6 circuite de iluminat
RE_P_L = re.compile(r"(?<![\w.,])(?P<p>\d{1,2})\s*p\s*(?:,|si|\+)?\s*(?P<l>\d{1,2})\s*l\b")
_NUMERAL = {"un": 1, "o": 1, "doua": 2, "doi": 2, "trei": 3, "patru": 4, "cinci": 5, "sase": 6}
# subpanou / sub-tablou / subpanel / panou electric → tablou secundar
RE_TABLOU_SIN = re.compile(r"(?<![\w-])(?:sub[\s-]*tablou\w*|sub[\s-]*panel\w*|subpanou\w*|panou\w*\s+electric\w*(?:\s+secundar\w*)?)")


def _uk(text, note):
    return _sub(text, RE_UK, lambda m, t0: None if m.group("w").replace(" ", "") in ("uk",) else "uk ", note,
                "„{}” = tensiunea de scurtcircuit uk (sinonim: Ucc / usc / u_k / tensiunea de scurtcircuit)")


def _bmpt(text, note):
    def f(m, t0):
        w = m.group("w")
        if w.startswith(("contor", "firid", "cutie", "grup", "punct", "bloc")) or "cut" in w or "meter" in w:
            mij = m.group("mij") or ""
            k = m.group("k")
            mono = k == "1" or re.search(r"monofaz|\bmono\b", mij)
            tri = k == "3" or re.search(r"trifaz|\btri\b", mij)
            if not (mono or tri):
                # calibrul fără faze: rețeaua se scrie în altă parte (sau se întreabă) — doar sinonimul
                return f"BMPT {m.group('a')}A" if not re.search(r"monofaz|\bmono\b|\bbmpm|1\s*[x×]", norm(t0)) else f"BMPM {m.group('a')}A"
            ex = " existent" if "existent" in mij else ""
            return (f"BMPM 1x{m.group('a')}A{ex}" if mono and not tri else f"BMPT 3x{m.group('a')}A{ex}")
        return None
    return _sub(text, RE_BMPT_SIN, f, note,
                "„{}” = branșamentul (BMPT / BMPM: contor, firidă, cutie de branșament = sursa, nu o plecare)")


def _ats(text, note):
    return _sub(text, RE_ATS_SIN, "ATS", note, "„{}” = ATS (comutare automată a surselor)")


def _ge(text, note):
    return _sub(text, RE_GE_SIN, "GE", note, "„{}” = grup electrogen (GE)")


def _pt(text, note):
    return _sub(text, RE_PT_SIN, "PT", note)


def _ups(text, note):
    return _sub(text, RE_UPS_SIN, "UPS", note, "„{}” = UPS (sursă neîntreruptibilă)")


def _ve(text, note):
    def f(m, t0):
        w = m.group(0)
        plural = re.match(r"stati(?:i|ile)\b|borne\b|puncte\b", w) or re.search(r"(?:chargers|stations|boxes|box\w+)$", w)
        return "statii de incarcare VE" if plural else "statie de incarcare VE"
    return _sub(text, RE_VE_SIN, f, note, "„{}” = stație de încărcare VE")


def _ilum(text, note):
    t = _sub(text, RE_ILUM_SIN, "iluminat", note)

    t = _sub(t, RE_P_L, lambda m, t0: f"{m.group('p')} prize, {m.group('l')} iluminat", note,
             "„{}” = N circuite de prize și M circuite de iluminat (abrevieri „p” / „l”)")

    def f(m, t0):
        x = m.group("n")
        n = int(x) if x.isdigit() else _NUMERAL[x]
        w = m.group("w")
        if w.startswith("iluminat"):
            return None
        if w.startswith("circuit"):
            return t0[m.start():m.start("w")] + re.sub(r"lumina\b", "iluminat", w)
        return f"{n} iluminat"
    return _sub(t, RE_N_LUMINI, f, note, "„{}” = N circuite de iluminat (lumini / spoturi / corpuri = circuite)")


def _tablou(text, note):
    return _sub(text, RE_TABLOU_SIN, "tablou secundar", note)


def canonizeaza(text: str) -> tuple[str, list[str]]:
    """Rescrierea sinonimelor în forma canonică (vezi docstring). Întoarce (text, note)."""
    note: list[str] = []
    t = text
    for f in (_uk, _bmpt, _ats, _ge, _pt, _ups, _ve, _ilum, _tablou):
        t = f(t, note)
    return (t, note) if t != text else (text, [])
