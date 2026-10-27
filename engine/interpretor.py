"""Interpretorul de text liber (chat) — SPEC_TEHNIC.md, secțiunea F.

Contract (F.1): primește o frază în română și întoarce
    {actiune, tip_schema, intrare_fizica, extras, cartus, presupus[], intrebari[],
     avertismente[], refuz_cod, refuz_motiv, intelegere, motor}

* `intrare_fizica` are forma câmpului `intrare` din tests/date/cazuri_golden.json și se dă
  motorului de dimensionare (engine.calc). Interpretorul NU dimensionează (F.1): conține doar ce
  a scris utilizatorul (plus ce impune F.7, ex. PT propriu adăugat la I11). Valorile implicite
  din B.0 NU se scriu în intrare — le aplică motorul — dar se DECLARĂ în `presupus` (F.6).
* `extras` e vederea structurală din tests/date/fraze_chat.json → `asteptat`.
* Calculele de aici (Ib, Iac, S) servesc numai la regulile de refuz/întrebare din F.7.

Opțional (`foloseste_llm=True`): modelul Claude întoarce DOAR `intrare_fizica` în JSON; rezultatul trece
prin aceeași normalizare și validare de formă și prin aceleași verificări F.7. Dacă SDK-ul `anthropic`,
cheia sau răspunsul lipsesc/sunt invalide, rămâne rezultatul regulilor locale.
"""
from __future__ import annotations

import copy
import json
import math
import os
import re
import sys

try:  # norme.py e sursa unică pentru seriile standard (trafo, BMPT, ks, factori)
    from .calc import norme
except ImportError:  # rulare ca script izolat
    from engine.calc import norme  # type: ignore
try:  # r7: normalizarea formatului (rânduri, enumerări, „a câte”) + completările de catalog ale interpretorului
    from .interp_text import normalizeaza_format, cauta_supl, invertor_baterie, kwh_din_model, p_bess_din_model
except ImportError:
    from engine.interp_text import normalizeaza_format, cauta_supl, invertor_baterie, kwh_din_model, p_bess_din_model  # type: ignore
try:  # r8: rescrierea textului (tabele copiate, engleză, cascade în propoziții, autocorecturi) înaintea regulilor
    from .interp_rescriere import rescrie
except ImportError:
    from engine.interp_rescriere import rescrie  # type: ignore
try:  # r11: dicționarul central de sinonime + clasele r11 (rescriere înainte / completări după reguli)
    from . import interp_sinonime as SIN
    from . import interp_r11 as R11
    from . import interp_reale as R12
except ImportError:
    from engine import interp_sinonime as SIN  # type: ignore
    from engine import interp_r11 as R11  # type: ignore
    from engine import interp_reale as R12  # type: ignore
try:  # r6: catalogul modelelor de invertoare / baterii (al motorului) — Pn și „hibrid” din cod
    from .calc import catalog_invertoare as _cat_inv
except Exception:  # noqa: BLE001
    try:
        from engine.calc import catalog_invertoare as _cat_inv  # type: ignore
    except Exception:  # noqa: BLE001
        _cat_inv = None

SQRT3 = norme.SQRT3
U_TRI = SQRT3 * norme.U_N_V          # 692,82 V
U_MONO = norme.U_0_V                 # 230 V
COSFI = norme.COSFI_IMPLICIT["forta"]
FACTOR_INV = norme.FACTOR_SMAX_INVERTOR

TIPURI = ("bransament", "tablou", "cef", "pt", "prosumator", "ge_ats", "locuinta")
NUME_TIP = {"bransament": "branșament", "tablou": "tablou", "cef": "CEF",
            "pt": "post de transformare 20/0,4 kV", "prosumator": "prosumator", "ge_ats": "grup electrogen + ATS",
            "locuinta": "locuință"}

# =====================================================================================================
# F.2 Normalizare
# =====================================================================================================
_DIACRITICE = str.maketrans("șşțţăâîȘŞȚŢĂÂÎ", "ssttaaiSSTTAAI")
NUM = r"\d+(?:[.,]\d+)?"


def normalizeaza(text: str) -> str:
    """Copia de lucru (F.2.2): litere mici, fără diacritice, „x”/„*” între numere → „×”, „~” → „≈”.
    Toate înlocuirile păstrează lungimea, deci pozițiile din copia de lucru indică același loc
    în textul original (de unde se iau numele, beneficiarul și localitatea — F.2.1)."""
    t = text.translate(_DIACRITICE).lower()
    if len(t) != len(text):          # caractere exotice care își schimbă lungimea la lower()
        t = "".join(c if len(c.lower()) != 1 else c.lower() for c in text.translate(_DIACRITICE))
    t = re.sub(r"(?<=\d)(\s*)[x*](?=\s*\d)", r"\1×", t)
    return t.replace("~", "≈")


def numar(s: str) -> float:
    """F.2.3: virgula = zecimal; punctul urmat de exact 3 cifre = separator de mii."""
    s = s.strip()
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s):
        return float(s.replace(".", ""))
    return float(s.replace(",", "."))


def _nr(x):
    """Număr „curat” pentru JSON: 15.0 → 15."""
    if x is None:
        return None
    x = round(float(x), 4)
    return int(x) if x == int(x) else x


def fmt(x, dec=1) -> str:
    """Format românesc: virgulă zecimală, fără zecimale inutile."""
    x = round(float(x), dec)
    s = f"{x:.{dec}f}".rstrip("0").rstrip(".") if dec else f"{x:.0f}"
    return s.replace(".", ",")


def _fara_diacritice(s: str) -> str:
    return s.translate(_DIACRITICE).lower()


# =====================================================================================================
# F.3 Unități
# =====================================================================================================
UNITATI = {  # text → (mărime, factor spre unitatea de bază)
    "kwp": ("kWp", 1), "mwp": ("kWp", 1000), "wp": ("Wp", 1),
    "kwh": ("kWh", 1), "mwh": ("kWh", 1000),
    "kva": ("kVA", 1), "mva": ("kVA", 1000),
    "kw": ("kW", 1), "mw": ("kW", 1000), "w": ("kW", 0.001),
    "ka": ("A", 1000), "a": ("A", 1),
    "km": ("m", 1000), "metri": ("m", 1), "ml": ("m", 1), "m": ("m", 1),
    "cp": ("kW", 0.7355),                 # r5: cai-putere (1 CP = 0,7355 kW)
    "hp": ("kW", 0.7457),                 # r8: horsepower (1 HP = 0,7457 kW)
}
KW_PE_CP = 0.7355
UNIT_AFIS = {"hp": "HP", "kwp": "kWp", "mwp": "MWp", "wp": "Wp", "kwh": "kWh", "mwh": "MWh", "kva": "kVA", "mva": "MVA",
             "kw": "kW", "mw": "MW", "w": "W", "ka": "kA", "a": "A", "km": "km", "metri": "m", "ml": "m", "m": "m",
             "cp": "CP"}
# r5 (P0-6): „-” în lookbehind — cifra din codul tabloului („td-2 160 A”) nu se lipește de valoare („2 160 A”)
RE_VAL = re.compile(rf"(?<![\w.,\-])(?P<num>{NUM}|\d{{1,3}}(?: \d{{3}})+)\s*"
                    r"(?P<u>kwp|mwp|wp|kwh|mwh|kva|mva|kw|mw|w|ka|a|km|metri|ml|m|cp|hp)\b")
RE_APROX = re.compile(r"(?:≈|cca\.?|circa|aprox\.?|aproximativ|cam)\s*$")


def valori(t: str) -> list[dict]:
    """Toate perechile număr + unitate din textul (mascat), cu poziții și marcajul „aproximativ”."""
    out = []
    for m in RE_VAL.finditer(t):
        txt = m.group("num")
        if " " in txt and not re.fullmatch(r"\d{1,3}(?: \d{3})+", txt):
            continue
        val = float(txt.replace(" ", "")) if " " in txt else numar(txt)
        marime, factor = UNITATI[m.group("u")]
        ap = RE_APROX.search(t[max(0, m.start() - 14):m.start()])
        out.append({"marime": marime, "val": val * factor, "brut": val, "u": m.group("u"), "txt": txt,
                    "s": m.start(), "e": m.end(),
                    "s_aprox": (max(0, m.start() - 14) + ap.start()) if ap else None})
    return out


# =====================================================================================================
# Context de lucru (textul original + copia normalizată + ce s-a găsit)
# =====================================================================================================
_SEP_CLAUZA = re.compile(r"(?<!\d),|,(?!\d)|;|:")
RE_AUTOCORECTIE = re.compile(r"\?+\s*nu\s*[,:;]\s*")
RE_PREFIX_EGAL = re.compile(r"\b(?:in|l)\s*=\s*(?=\d)")
# r6 (locuințe P0-2/3): „mărire putere bmpm 7kw -> bmpt 15 kw tri”, „de la 7 kw mono la 15 kw tri” — sursa (situația
# existentă) e informativă; ținta e proiectul
_PUTERE_LOC = rf"(?:(?:bmp[mt]\w*|bransament\w*|mono\w*|tri\w*|existent\w*)\s+){{0,3}}{NUM}\s*(?:kw|kva|a)\b" \
              rf"(?:\s+(?:mono\w*|tri\w*|bmp[mt]\w*|existent\w*))?"
RE_MARIRE = re.compile(rf"(?P<src>(?:\bde\s+la\s+){_PUTERE_LOC}|{_PUTERE_LOC}|(?<![\w.,]){NUM}(?=\s*(?:->|→|=>)))\s*"
                       rf"(?P<sag>->|→|=>|\bla\b)\s*"
                       rf"(?=(?:(?:bmp[mt]\w*|bransament\w*)\s+)?{NUM}\s*(?:kw|kva|a)\b)")
RE_CONTEXT_MARIRE = re.compile(r"\bmarire\w*|\bsuplimentare\w*|\bcrestere\w*|\bmajorare\w*|\bmodificare\w*|\bschimbare\w*"
                               r"|\bmari(?:m|ti|t|ta)\b|\bmajor(?:am|ati)\b|\bcrest(?:em|eti)\b|\bsuplimentam\b")

# r6 (industrial #48): „td-1 125 a/60 m” → calibru + lungime
RE_A_PE_M = re.compile(rf"(?<=\d)(\s*a)\s*/\s*(?={NUM}\s*m\b)")
# r6 (industrial #49): „(TD-1..TD-3)” = numele generate, nu o cascadă
RE_INTERVAL_TD = re.compile(r"\(\s*t[dge]-?\s*\d+\s*(?:\.{2,3}|…|-|pana\s+la)\s*(?:t[dge]-?\s*)?\d+\s*\)")
# r6 (industrial #22): „TD-P (parter) 63A” — paranteza fără cifre și fără separatori = descriere, nu cascadă
RE_PARANTEZA_DESCR = re.compile(r"\(\s*[a-z][a-z.\- ]{0,30}\)")
RE_PARANTEZA_CIRC = re.compile(r"\(\s*\d+\s*(?:circuite|circuit|circ\.?|buc\w*\.?|bucati|plecari)\s*\)")
# r6 (locuințe N31): „7 kW sau 10 kW” = valoare ambiguă → întrebare
RE_INTERVAL_VAL = re.compile(rf"(?<![\w.,×/-])(?P<a>{NUM})\s*-\s*(?P<b>{NUM})\s*(?P<u>kw|kva)\b")
RE_BTU = re.compile(r"(?<![\w.,])(?:(?P<n>\d+)\s*[x×]\s*)?(?P<v>\d{4,5})\s*btu\b")
RE_ALTERNATIVA = re.compile(rf"(?P<a>{NUM})\s*(?P<ua>kwp|kwh|kva|kw|a|m)?\s+(?:sau|ori)\s+(?P<b>{NUM})\s*(?P<ub>kwp|kwh|kva|kw|a|m)\b")


def _preproceseaza(t: str):
    """r5: (1) autocorecturile „1.000 m cablu?? nu, 100 m” — clauza dinaintea lui „? nu,” se ignoră;
    (2) „In=100A L=60m” → „    100A   60m” (prefixele „X=” ale valorilor dispar).
    r6: (3) mărirea de putere „X → Y” / „de la X la Y” — X (existent) se ignoră; (4) „125 a/60 m” → „125 a 60 m”;
    (5) „(TD-1..TD-3)” se ignoră; (6) parantezele descriptive „(parter)” nu deschid cascade.
    Lungimea se păstrează. Întoarce (text, autocorecturi, [(s, e, fel)] zone ignorate cu notă)."""
    out, corectii = list(t), []
    for m in RE_AUTOCORECTIE.finditer(t):
        s = max([x.end() for x in _SEP_CLAUZA.finditer(t, 0, m.start())] or [0])
        corectii.append((s, m.end()))
        out[s:m.end()] = " " * (m.end() - s)
    t2 = "".join(out)
    t2 = RE_PREFIX_EGAL.sub(lambda m: " " * len(m.group(0)), t2)
    zone = []
    for m in RE_MARIRE.finditer(t2):
        if m.group("sag") == "la" and not m.group("src").startswith("de"):
            continue
        if m.group("sag") == "la" and not RE_CONTEXT_MARIRE.search(t2):
            continue
        zone.append((m.start(), m.end(), "marire"))
    t2 = RE_A_PE_M.sub(lambda m: m.group(1) + " ", t2)
    for m in RE_INTERVAL_TD.finditer(t2):
        zone.append((m.start(), m.end(), "interval_td"))
    lst = list(t2)
    for s, e, _ in zone:
        lst[s:e] = " " * (e - s)
    t2 = "".join(lst)
    lst = list(t2)
    for m in RE_PARANTEZA_DESCR.finditer(t2):
        lst[m.start()] = lst[m.end() - 1] = " "
    # r8 (industrial #1): „iluminat hală 18 kW (6 circuite)” — paranteza cu numărul de circuite nu deschide o cascadă
    for m in RE_PARANTEZA_CIRC.finditer(t2):
        lst[m.start()] = lst[m.end() - 1] = " "
    return "".join(lst), corectii, zone


class Ctx:
    def __init__(self, text: str):
        self.orig = text or ""
        self.t = normalizeaza(self.orig)
        self.t, note_format = normalizeaza_format(self.t)   # r7: rânduri / tab / enumerări / „a câte” / greșeli
        self.t_brut = self.t                  # copia de lucru ÎNAINTE de preprocesare (plasa de siguranță)
        self.t, self.corectii, self.zone = _preproceseaza(self.t)
        self.note: list[str] = []          # presupuneri care vin din citirea textului (F.2–F.5)
        self.probleme: list[tuple] = []    # (cod, motiv, întrebare) găsite la parsare
        self.intrebari: list[tuple] = []   # (cod, întrebare) — se generează ȘI se întreabă (r5)
        self.avert: list[str] = []         # avertismente din citirea textului (r5)
        self.lista = None                  # rezultatul parsării listei de plecări
        self.consumat: list[tuple] = []    # intervale din t deja interpretate (lista, invertoare, BESS)
        self.citit: list[tuple] = []       # r6: intervale folosite (sau tratate printr-o notă / întrebare), nemascate
        self.fara_valoare: list[str] = []  # r6: itemi de listă fără putere / calibru (→ întrebare)
        for n in note_format:
            self.nota(n)
        for s, e in self.corectii:
            self.nota(f"„{self.o(s, e).strip()}” = autocorectură: valoarea dinainte de „nu,” se ignoră")
        for s, e, fel in self.zone:
            if fel == "marire":
                self.nota(f"„{self.o(s, e).strip()}” = situația existentă (informativ); proiectul = puterea nouă")
            else:
                self.nota(f"„{self.o(s, e).strip()}” = numele plecărilor (generate în ordine)")
        for m in RE_INTERVAL_VAL.finditer(self.t):     # r8 (locuințe #7, #60): „20-25 kW” = interval → întrebare
            u = m.group("u")
            self.citit.append((m.start(), m.end()))
            self.probleme.append(("I08", f"Valoare dată ca interval: „{self.o(m.start(), m.end()).strip()}” (I08).",
                                  f"Ce putere (aprobată / cerută): {m.group('a')} {UNIT_AFIS.get(u, u)} sau {m.group('b')} "
                                  f"{UNIT_AFIS.get(u, u)}? (din ATR / cererea de racordare)"))

        for m in re.finditer(rf"(?<![\w.,])(?P<a>{NUM})\s+(?:sau|ori)\s+(?P<b>{NUM})(?![\w.,]|\s*(?:kwp|kwh|kva|kw|a|m|v)\b)",
                             self.t):
            # r9 (locuințe #60): „casa 15 kw (nu știu dacă e 15 sau 25)” — alternativa fără unitate, la o valoare scrisă
            mu = re.search(rf"(?<![\w.,]){re.escape(m.group('a'))}\s*(kwp|kwh|kva|kw|a)\b", self.t)
            if mu and numar(m.group("a")) != numar(m.group("b")):
                u = mu.group(1)
                self.citit.append((m.start(), m.end()))
                self.probleme.append(("I08", f"Valoare ambiguă: „{self.o(m.start(), m.end()).strip()}” (I08).",
                                      f"Care este valoarea: {m.group('a')} {UNIT_AFIS.get(u, u)} sau {m.group('b')} "
                                      f"{UNIT_AFIS.get(u, u)}?"))
        for m in RE_ALTERNATIVA.finditer(self.t):
            ua, ub = m.group("ua") or m.group("ub"), m.group("ub")
            if ua == ub and numar(m.group("a")) != numar(m.group("b")):
                self.citit.append((m.start(), m.end()))
                self.probleme.append(("I08", f"Valoare ambiguă: „{self.o(m.start(), m.end()).strip()}” (I08).",
                                      f"Care este valoarea: {m.group('a')} {UNIT_AFIS.get(ub, ub)} sau {m.group('b')} "
                                      f"{UNIT_AFIS.get(ub, ub)}?"))

    def foloseste(self, s, e):
        """r6: marchează [s, e) ca folosit (pentru plasa de siguranță), fără să-l mascheze."""
        if e > s:
            self.citit.append((s, e))

    def o(self, s, e):
        """Felia din textul original pentru pozițiile copiei de lucru."""
        return self.orig[s:e] if len(self.orig) == len(self.t) else self.t[s:e]

    def mascat(self) -> str:
        t = list(self.t)
        for s, e in self.consumat:
            t[s:e] = " " * (e - s)
        return "".join(t)

    def nota(self, s: str):
        if s and s not in self.note:
            self.note.append(s)


# =====================================================================================================
# F.5 Tipul schemei (r5: prosumator > CEF/BESS > GE > locuință > branșament > PT > tablou; vezi SPEC F.5)
# =====================================================================================================
RE_PT_PROPRIU = re.compile(r"\bdin\s+(?:pt|postul)\s+propriu\b")
# „PT” ca SURSĂ a altei instalații (nu tipul schemei): „din PT (propriu)”, „până la PT”, „faza PT”, „PT … existent”
_SN_STD = r"(?:100|160|250|400|630|800|1000|1250|1600|2000|2500)"
_ATR_PT = r"(?:\s+(?:propriu|propr\w*|existent\w*|od|atr|al\s+od|cf\.?\s*atr|conform\s+atr|al\s+fabricii|al\s+beneficiar\w*))"
RE_PT_SURSA = re.compile(
    r"\b(?:din|de\s+la|pana\s+la|alimentat\w*\s+din|alim\s+din|alimentare\w*(?:\s+din)?|sursa\s*:?(?:\s+din)?)\s+"
    r"(?:pt|postul|post(?:ul)?\s+(?:de\s+)?(?:transformare|trafo))\b"
    rf"(?P<atr>{_ATR_PT}*)"
    # r8 (industrial #5, #33, #62, #64): „din PT 250”, „TG din PT 400” — un număr din seria trafo = kVA
    rf"(?:\s*(?P<sn>{NUM})\s*kva(?:\s+existent\w*)?|\s+(?P<sn4>{_SN_STD})\b(?!\s*(?:a|kw|m|v|kv|%|w)\b))?"
    rf"(?P<atr2>{_ATR_PT}*)"
    # r8 (industrial #1, #6, #68): „(ulei, 20/0,4 kV)”, „uscat 20/0,4 kV” = atributele PT-ului SURSĂ (nu tipul schemei)
    rf"(?P<tr>(?:\s+(?:uscat\w*|ulei|in\s+ulei))?(?:\s*,?\s*\(?\s*(?:(?:ulei|uscat\w*)\s*,?\s*)?{NUM}\s*/\s*0[.,]4\s*kv\s*\)?)?)"
    rf"|\(\s*(?:pt|post\w*)\s+propriu\s+(?:(?P<sn2>{NUM})\s*kva\s+)?existent\w*\s*\)"
    rf"|\b(?:pt|post\w*)\s+propriu\s+(?:(?P<sn3>{NUM})\s*kva\s+)?existent\w*"
    r"|\bfaza\s+pt\b")
RE_CASA_TARE = re.compile(r"\bcas(?:a|ei|e|uta)\b|\blocuint\w*|\bapartament\w*|\bgarsonier\w*|\bvil(?:a|e|ei)\b|\bduplex\b"
                          r"|\bapt\b\.?|\bap\.?\s+(?=\d|cam|bloc|et|mono|tri|\d)")
# r6 (industrial #6, locuințe N50): „casa de marcat” nu e o casă; „din TG casa” = sursa unui tablou secundar
RE_NU_CASA = re.compile(r"\bcas(?:a|e|ei)\s+(?:de\s+)?marcat\w*|\bcas(?:a|ei)\s+scar\w*|\b(?:din|de\s+la)\s+(?:tg|te|tablou\w*)(?:\s+general\w*)?\s+"
                        r"(?:al\s+|de\s+la\s+)?(?:casa|casei|locuint\w*)")
# r6: tablouri comerciale / industriale — „TG supermarket / magazin / hală / birouri” ≠ locuință
RE_COMERCIAL = re.compile(r"\bsupermarket\w*|\bmagazin\w*|\bhal(?:a|e|ei)\b|\bbirou\w*|\bfabric\w*|\bferm(?:a|e|ei)\b"
                          r"|\bdepozit\w*|\bscoal\w*|\bspital\w*|\bhotel\w*|\brestaurant\w*|\bpensiun\w*|\batelier\w*"
                          r"|\bindustrial\w*|\bstatie\w*(?!\s+(?:de\s+)?(?:incarcare|ve\b|ev\b))|\bmall\b|\bparcare\b"
                          r"|\bspalatori\w*|\bbrutari\w*|\bcomercial\w*"
                          r"|\bfarmaci\w*|\bcabinet\w*|\bclinic\w*|\bsalon\w*|\bcafenea\w*|\bcofetari\w*|\bfrizeri\w*"
                          r"|\bservice\s+auto|\bshowroom\w*|\bchiosc\w*|\bbanc[aă]\b|\bsediu\w*"   # r9 (#11)
                          # r8: TG-ul clădirii (lift, scări, spații comune) ≠ locuință
                          r"|\blift\w*|\bascensor\w*|\bspatii\s+comune|\basociati\w*\s+de\s+proprietari|\bbloc\s+de\s+locuint\w*"
                          r"|\bimobil\w*|\bcladir\w*\s+(?:de\s+)?(?:birouri|locuint\w*|rezidential\w*)"
                          # r8 (industrial #65): bucătărie profesională (restaurant, pizzerie) ≠ locuință
                          r"|\bpizz\w*|\bfriteuz\w*|\bhot[ae]\b|\bprofesional\w*|\bcantin\w*|\bcofetari\w*|\bcafenea\w*"
                          r"|\bbar\b|\bbistro\w*|\bfast[\s-]*food\b|\bservice\b|\bservice\s+auto\b")

# r6 (industrial #25, #52): bateria de condensatoare (compensare) nu e BESS
RE_COMPENSARE = re.compile(r"\bbateri\w*\s+(?:de\s+)?(?:condensato\w*|compensare)|\bcompensare\w*(?:\s+(?:a\s+)?factor\w*"
                           r"(?:\s+de)?\s+putere)?|\bcondensatoare\b(?=[^,;.]{0,30}kvar)"
                           # r8 (industrial #27): „baterie automată 250 kvar cu filtru 7%, 8 trepte” = compensare, nu BESS
                           r"|\bbateri\w*(?:\s+(?!de\b)[a-z]+){0,3}\s+\d+(?:[.,]\d+)?\s*kvar\b(?:\s+cu\s+filtru\w*(?:\s+\d+\s*%)?)?"
                           r"(?:\s*,?\s*\d+\s+trepte)?|\d\s*kvar\b|\bkvar\b")
# r8 (industrial #28): „factor de putere 0,78 → 0,95, ce baterie îmi trebuie” — bateria e de compensare
RE_FACTOR_PUTERE = re.compile(r"\bfactor\w*\s+de\s+putere|\bcos\s*(?:fi|φ|phi)\b|\bcompensare\w*|\bkvar\b|\benergie\s+reactiv\w*")
# r6 (industrial #10, #15, #45, #47, #53): „TG … din BMPT” = sursa tabloului (origine bmpt), nu un branșament
RE_BMPT_SURSA = re.compile(r"\b(?:din|prin|de\s+la|alimentat\w*\s+din|sursa(?:\s+retea\w*)?\s+din|sursa)\s+"
                           r"(?:bmp[tm]\w*|bransament\w*|retea\w*(?:\s+publica)?)")
RE_CASA_SLAB = re.compile(r"(?<![\w+])p\s*\+\s*[1-3m]\b|\bparter\b|\bmansard\w*")
RE_PV = re.compile(r"\bcef\b|fotovoltaic\w*|\bpv\b|\d\s*[km]?wp\b|invertor\w*|invertoare\w*|\binv\b|\bpanou\w*"
                   r"|\bsun2000|\bsg\d+cx|\bsh\d+(?:\.\d+)?(?:t|rt|rs)\b|\bstp\s*\d|\bsunny\s+tripower|\btauro\b|\bsymo\b")
RE_BESS_CUV = re.compile(r"\bbess\b|\bstocare\b|\bbateri\w*|\bacumulator\w*|\bluna2000|\bpowerstack|battery[\s-]*box")
RE_GE_CUV = re.compile(r"\bgrup(?:ul)?\s+electrogen|\bgenerator\w*\b|\bats\b|\baar\b")
RE_TABLOU_CUV = re.compile(r"\btablou\w*|\btg\b|\btgd\b|\btd\b|\bplecari\b|\btgjt\b")


def _masca(t: str, rx) -> str:
    return rx.sub(lambda m: " " * len(m.group(0)), t)


# r7 (industrial #9, #10): transformatorul de separare (IT medical) / 400/230 V pentru iluminat ≠ post de transformare
RE_TRAFO_NU_PT = re.compile(r"\b(?:transformator\w*|trafo)\s+(?:de\s+)?(?:separare|izolare|siguranta|comanda|SELV)\w*"
                            r"(?:\s+(?:de\s+)?\d+(?:[.,]\d+)?\s*kva)?|\b(?:transformator\w*|trafo)\s+400\s*/\s*230(?:\s*v)?"
                            r"|\bprin\s+(?:transformator\w*|trafo)\b(?:\s+400\s*/\s*230(?:\s*v)?)?")


# r10: distribuitorii (OD) — „PT al Electrica”, „Rețele Electrice Banat”, „Delgaz”, „(nu e al nostru)”
_OD_NUME = (r"\belectrica\b|\benel\b|e-?distributie|\bdelgaz\b|retele\s+electrice|distributie\s+(?:oltenia|energie)"
            r"|\bdeer\b|\bnu\s+e(?:ste)?\s+al\s+nostru|\bal\s+(?:distribuitorului|operatorului)")


def _pt_explicit(c: Ctx) -> bool:
    """„PT” majuscul / post de transformare / transformator / 20/0,4 kV — în afara mențiunilor de SURSĂ."""
    t = _masca(_masca(c.t, RE_PT_SURSA), RE_TRAFO_NU_PT)
    o = "".join(ch if t[i] != " " or c.t[i] == " " else " " for i, ch in enumerate(c.orig)) \
        if len(c.orig) == len(c.t) else t
    return bool(re.search(r"\bPT\b|\bPTAB\b|\bPTA\b|\bPTCZ\b", o) or re.search(
        r"\bpost(?:ul)?\s+(?:de\s+)?(?:transformare|trafo)|transformator|\btrafo\b|20/0[.,]4\s*kv|\bptab\b", t))


def _ge(c: Ctx) -> bool:
    return bool(RE_GE_CUV.search(c.t) or re.search(r"\bGE\b", c.orig))


def _pv(c: Ctx) -> bool:
    """r7: fotovoltaic și fără „CEF / prosumator”: „pv N kW”, „solar”, „panouri”, o marcă / un model de invertor sau de
    baterie recunoscut (Fronius Primo GEN24, Growatt MIN 6000TL-X, GoodWe GW10K-ET, Deye SUN-12K …)."""
    t_pv = _masca(c.t, re.compile(r"\bfara\s+(?:panouri|pv|fotovoltaic\w*|invertor\w*|solar\w*)\b"))  # r9 (#53)
    if not re.search(r"\bpanou\w*|\bpv\b|invert|solar|fotovolt|\bcef\b|kwp", t_pv) and re.search(r"\bfara\s+panouri", c.t):
        return False
    if RE_PV.search(t_pv) or RE_PV_R7.search(t_pv):
        return True
    for m in RE_MARCA.finditer(c.t):
        if MARCI[m.group(1)][1] in ("inv", "bess") and m.group(1) != "ja":
            return True
    return bool(RE_COD_MODEL.search(c.t) or cauta_supl(None, c.t))


RE_PV_R7 = re.compile(r"\bsolar\w*|\bfotovolt\w*|\bpanouri\b|\binvert\w*|\bluna\s*2000|\bpylontech\b|\bbyd\s+hv[sm]"
                      r"|\bsunny\s+(?:boy|island|highpower)|\bprimo\b|\bmod\s*\d+\s*ktl|\bmin\s*\d{4}\s*tl")
# r7: „off-grid” = fără racord la rețea → în afara domeniului (nu e schemă de racordare OD)
RE_OFFGRID = re.compile(r"\boff[\s-]*grid\b|\bizolat\w*\s+de\s+retea|\bfara\s+retea\b|\bautonom\w*\b")
# r7: indicii de CEF (centrală / PT / TG / hală / MW) — fără ele un sistem PV mic e prosumator (casă, BMPT)
RE_CEF_CUE = re.compile(r"\bcef\b|\bcentral\w*\s+(?:fotovolt\w*|pv|solar\w*|electric\w*\s+fotovolt)|\bcentralei\b|\bparc\w*\b"
                        r"|\bagrivolt\w*|\bmw\b|\bmwp\b|\bmwh\b|\bbess\b|\bpcs\b|\btg\b|\btgd\b|\btablou\w*|\bhal(?:a|e|ei)\b"
                        r"|\bpost\w*\s+(?:de\s+)?(?:transformare|trafo)|\btrafo\b|transformator\w*|\bfabric\w*|\bdepozit\w*")


def _cef_sau_prosumator(c: Ctx) -> str:
    """r7: PV fără „CEF / prosumator / casă”: CEF dacă textul are indicii de centrală (PT, TG, hală, MW, BESS …) sau o
    putere > 100 kW; altfel prosumator (racord prin BMPT / BMPM, invertor de casă)."""
    if RE_CEF_CUE.search(c.t) or _pt_explicit(c):
        return "cef"
    if any(v["val"] > 100 for v in valori(c.t) if v["marime"] in ("kW", "kWp", "kVA")):
        return "cef"
    return "prosumator"


def _tablou_numit_t(c: Ctx, t: str) -> bool:
    o = "".join(ch if t[i] != " " or c.t[i] == " " else " " for i, ch in enumerate(c.orig)) \
        if len(c.orig) == len(c.t) == len(t) else c.orig
    return bool(RE_TABLOU_CUV.search(_masca(_masca(t, RE_PT_SURSA), RE_NU_CASA)) or re.search(r"\bTE\b", o)
                or re.search(r"\b(?:te|tg|td)-\w", t))


def _tablou_numit(c: Ctx) -> bool:
    return bool(RE_TABLOU_CUV.search(_masca(_masca(c.t, RE_PT_SURSA), RE_NU_CASA)) or re.search(r"\bTE\b", c.orig)
                or re.search(r"\b(?:te|tg|td)-\w", c.t))


RE_ATS_TRAFO = re.compile(r"\b(?:ats|aar|anclansare\w*\s+automat\w*)\b[^.;]{0,40}?\b(?:intre\s+)?(?:cele\s+)?(?:2|doua|doi)\s+"
                          r"(?:transformatoare|trafo\w*|surse\s+trafo)|\b(?:2|doua)\s+(?:transformatoare|trafo\w*)[^.;]{0,40}?"
                          r"\b(?:ats|aar|rezerv\w*\s+(?:100|reciproc\w*))")


def detecteaza_tip(c: Ctx) -> str | None:
    t = c.t
    c.combo = []                       # alte instalații din aceeași frază (se desenează separat → întrebare I14)
    t_fc = _masca(t, RE_COMPENSARE)    # r6: „baterie de condensatoare” ≠ BESS
    if RE_FACTOR_PUTERE.search(t) and not re.search(r"\bkwh\b|\bbess\b|\bstocare\b|\binvertor\w*|\bpv\b|\bcef\b", t):
        t_fc = _masca(t_fc, re.compile(r"\bbateri\w*"))      # r8 (#28): bateria de compensare (cosφ / kvar)
    pv, ge, bess = _pv(c), _ge(c), bool(RE_BESS_CUV.search(t_fc))
    tablou = _tablou_numit(c)
    pt = _pt_explicit(c)
    if "prosumator" in t:
        return "prosumator"
    if re.match(r"\s*(?:td|te|tablou\w*\s+secundar\w*)\s+(?:\w+\s+){0,2}?(?:la\s+\d+\s*m\s+de\s+casa\s*,?\s*)?(?:alimentat\w*\s+)?din\s+tg\b"
                r"|\s*(?:td|te|tablou\w*\s+secundar\w*)\s+\w+(?:\s+la\s+\d+(?:[.,]\d+)?\s*m\s+de\s+casa)?\s*,\s*alimentat\w*\s+din\s+tg\b", t) \
            and not re.search(r"\bbransament\w*|\bbmp[mt]\w*|\baprobat\w*|\bpa\b|\bcas(?:a|ei)\s+(?:\w+\s+){0,2}\d", t) and not pv:
        return "tablou"                # r10 (locuințe #16): doar TD-ul anexei / mansardei (din TG-ul casei), nu casa tipică
    if RE_ATS_TRAFO.search(t) and not re.search(r"\bgrup\w*\s+electrogen|\bgenerator\w*|\bge\b|\bdiesel\b", t) and not pv:
        return "pt"                    # r10 (P0 industrial #47): ATS între 2 transformatoare — fără GE inventat
    if re.search(r"\bpt\s+aerian\w*|\bpt\b[^,;.]{0,30}\bpe\s+stalp", t) and re.search(r"\d\s*kva\b", t) and not pv:
        return "pt"                    # r10 (industrial #9): PTA pe stâlp (cu cutia BMPT de JT) = post, nu branșament
    if re.search(r"\bloc(?:ul)?\s+de\s+consum", t) and re.search(r"\bloc(?:ul)?\s+de\s+producere", t) and not pt \
            and all(v["val"] <= 100 for v in valori(t) if v["marime"] in ("kW", "kWp")):
        return "prosumator"            # r8 (locuințe #22): ATR „loc de consum / loc de producere” ≤ 100 kW = prosumator

    if (pv or re.search(r"\bhibrid\w*", t)) and not pt and re.search(r"\bhibrid\w*", t) and re.search(r"\bbackup\b|\beps\b", t) \
            and all(v["val"] <= 30 for v in valori(t) if v["marime"] in ("kW", "kWp", "kVA")):
        return "prosumator"            # r10 (P0 locuințe #66): hibrid + baterie + tablou de backup (EPS) = prosumator casnic
    if pv and not pt and re.search(r"\bhibrid\w*|\bbackup\b|\beps\b", t) and re.search(r"\bpa\b|aprobat\w*", t) \
            and all(v["val"] <= 30 for v in valori(t) if v["marime"] in ("kW", "kWp", "kVA")):
        return "prosumator"            # r9 (locuințe #51): hibrid + EPS / backup + Pa (fără „casă”) = prosumator casnic
    if pv or (bess and not ge):
        if RE_CASA_TARE.search(_masca(t, RE_NU_CASA)):
            return "prosumator"        # casă + fotovoltaic = prosumator (circuitele casei nu se desenează aici)
        if ge:
            c.combo = [x for x, ok in (("pt", pt), ("tablou", tablou), ("cef", True)) if ok]
            return "ge_ats"
        if tablou and re.search(r"\bplecari\b|\btd-?\s*\d", t):
            c.combo = ["tablou"]
        if pt and re.search(r"\bge\b|grup", t):
            c.combo.append("pt")
        return _cef_sau_prosumator(c)
    tablou_ge = tablou and _tablou_numit_t(c, _masca(t, re.compile(
        r"\b(?:pe\s+)?(?:tot|intreg)\w*\s+tablou\w*|\btablou\w*\s+(?:casei|general\s+al\s+casei)\b")))   # r9 (#50)
    if ge and RE_CASA_TARE.search(_masca(t, RE_NU_CASA)) and not pt and not pv and re.search(r"\btablou\w*\s+general", t) \
            and not re.search(r"\bvital\w*|\bincendiu|\bsiguranta", t) \
            and all(v["val"] <= 40 for v in valori(t) if v["marime"] in ("kVA", "kW")):
        return "locuinta"              # r10 (locuințe #10): „Casa: generator 8 kVA …, tablou general monofazat 32 A”
    if ge and RE_CASA_TARE.search(_masca(t, RE_NU_CASA)) and not pt and not tablou_ge and (
            not re.search(r"\bats\b|\baar\b|\bautomat\w*", t)
            or (not re.search(r"\bvital\w*|\bconsumator\w*|\bincendiu|\bsiguranta", t)
                and all(v["val"] <= 40 for v in valori(t) if v["marime"] in ("kVA", "kW")))):
        return "locuinta"              # r7 (#54) / r8 (#49): casa + GE (manual sau ATS) = GE sursă de rezervă a casei
    if ge:
        c.combo = [x for x, ok in (("pt", pt and _kva_pt(c)), ("tablou", tablou and bool(
            re.search(r"\bplecari\b|\btd-?\s*\d", t)))) if ok]
        return "ge_ats"
    if _e_locuinta(c):
        return "locuinta"
    if (tablou or RE_COMERCIAL.search(t)) and re.search(r"\bbmpt\w*\s+\d+\s*a\b", t) and len(re.findall(r"\d\s*kw\b", t)) >= 2 \
            and not RE_CASA_TARE.search(_masca(t, RE_NU_CASA)):
        return "tablou"                # r9 (industrial #11, #52): „magazin, BMPT 63 A: vitrine …”, „BMPT 160 A …, TG magazin: …”
    if not tablou and RE_BMPT_SURSA.search(t) and len(re.findall(r"\d\s*kw\b", t)) >= 2 and (
            RE_ATOM_REC.search(t) or re.search(RE_MOTOR_NUME, t) or RE_COMERCIAL.search(t)):
        return "tablou"                # r8 (industrial #65): receptoare cu puteri „din BMPT 80A” = tabloul lor, nu branșament
    t_b = _masca(t, RE_BMPT_SURSA) if tablou else t

    if re.search(r"\bbmpm", t_b) or re.search(r"\bbmpt|bransament|\bfirida", t_b):
        return "bransament"
    if not tablou and re.search(r"\b(?:conform\s+)?atr\b|\baviz\w*\s+tehnic", t) and re.search(
            r"\bp\s*aprob\w*|\bputere\w*\s+aprobat\w*|\bpa\b", t) and (RE_TRI_DECLARAT.search(t) or RE_MONO_DECLARAT.search(t)):
        return "bransament"            # r8 (locuințe #25): extras ATR (P aprobată, rețea, Ik, coloană) fără „casă”
    if not tablou and (re.search(r"\bcontor\w*", t) or re.search(r"\bsigurant\w*\s+(?:de\s+)?\d+\s*a\b", t)) and \
            (RE_TRI_DECLARAT.search(t) or RE_MONO_DECLARAT.search(t)) and re.search(r"\d\s*a\b", t) \
            and not RE_COMERCIAL.search(t):
        return "locuinta"              # r8 (locuințe #66): „siguranță de 25A la contor, trifazat” = branșamentul casei
    if not tablou and re.search(r"\b(?:marire|majorare|suplimentare|crestere)\w*\s+(?:de\s+)?putere\w*", t):

        return "bransament"            # r7 (#12): „mărire putere 11->22 kW, trifazic, coloana …” = branșamentul
    t_fara_sursa = _masca(t, RE_PT_SURSA)
    if pt:
        return "pt"
    # „kVA” pe o plecare NU face din tablou un PT (P0-5): tabloul numit explicit are prioritate
    if re.search(r"\d\s*[km]va\b", t_fara_sursa) and not re.search(r"\btablou\w*|\btg\b|\btgd\b|\btgjt\b", t_fara_sursa):
        return "pt"
    if tablou or re.search(r"\bcircuite\b", t) or re.search(r"\bTE\b", c.orig):
        return "tablou"
    # r7 (#21, #59): receptoare cu putere + sursa declarată („din PT 400 kVA alimentăm un motor …”), stație de încărcare
    rec = re.search(RE_MOTOR_NUME, t) or RE_ATOM_REC.search(t) or re.search(r"\bincarcator\w*|\bcuptor\w*", t)
    sursa = RE_PT_SURSA.search(t) or RE_ORIG_TG.search(t) or RE_ORIG_BMPT.search(t)
    if re.search(r"\bstati\w*\s+(?:de\s+)?incarcare\b", t) or (rec and sursa and re.search(r"\d\s*(?:kw|a|cp)\b", t)):
        return "tablou"
    if rec and any(v["val"] > 30 for v in valori(t) if v["marime"] == "kW"):
        return "tablou"                # r10 (industrial #25): un receptor industrial fără sursă = plecarea lui (sursa întrebată)
    return None


def _kva_pt(c: Ctx) -> bool:
    """Există o valoare kVA legată de PT/trafo (nu de GE)?"""
    return any(_proprietar_kva(c, v) == "pt" for v in valori(c.t) if v["marime"] == "kVA")


def _proprietar_kva(c: Ctx, v) -> str | None:
    """r5 (P0-3): kVA-ul aparține cuvântului cel mai apropiat dinaintea lui (PT / trafo vs GE / grup / generator)."""
    fer = c.t[max(0, v["s"] - 40):v["s"]]
    o = c.orig[max(0, v["s"] - 40):v["s"]] if len(c.orig) == len(c.t) else fer
    cand = []
    for m in re.finditer(r"grup\w*(?:\s+electrogen)?|generator\w*|\bge\b", fer):
        cand.append((m.end(), "ge"))
    for m in re.finditer(r"\bpt\b|post\w*|trafo|transformator\w*|ptab", fer):
        if m.group(0) != "pt" or re.match(r"PT", o[m.start():m.end()]):
            cand.append((m.end(), "pt"))
    for m in re.finditer(r"invert\w*|\binv\b", fer):
        cand.append((m.end(), "inv"))
    return max(cand)[1] if cand else None


# r7: „3x25A” / „3x400V” / „3 faze” = trifazat; un CABLU „3x2.5” / „3x150” NU spune rețeaua (L+N+PE sau 3F) — nu se deduce
RE_TRI_DECLARAT = re.compile(r"trifaz\w*|\btri\b|\btrif\b|\b400\s*v\b|\bbmpt|\b3f\b|\b3\s*[×x]\s*\d+(?:[.,]\d+)?\s*a\b"
                             r"|\b3\s*\+\s*n\b|3\s*[×x]\s*(?:230\s*/\s*)?400|\b3\s+faze\b")
# r7: „1x40A”, „1 fază”, „fază și nul” = monofazat
RE_MONO_DECLARAT = re.compile(r"\bbmpm|monofaz\w*|\bmono\b|\b1f\b|\b230\s*v\b|\b1\s*[×x]\s*\d+(?:[.,]\d+)?\s*a\b"
                              r"|\b(?:1|o)\s+faz[ae]\b|\bfaz[ae]\s+si\s+nul\b")
# r6 (N47): „nu știu dacă e mono sau tri” = rețea NEdeclarată (întrebare), nu „mono”; r7: „rețea: nu știu”, „3 faze sau una”
RE_RETEA_NESTIUTA = re.compile(r"\b(?:mono\w*|monofaz\w*)\s+(?:sau|ori)\s+(?:tri\w*)|\b(?:tri\w*)\s+(?:sau|ori)\s+(?:mono\w*)"
                               r"|\b3\s+faze\s+sau\s+(?:una|1|o\s+faza)\b|\bretea\w*\s*:?\s*(?:nu\s+stiu|necunoscut\w*|\?)")


RE_U_RECEPTOR = re.compile(r"\b(?:priz\w*|circuit\w*|consumator\w*)\s+(?:de\s+)?(?:\d+\s*a\s+)?(?:(?:230|400)\s*v\s*(?:si|,|/|sau)?\s*)+")


def retea_declarata(c: Ctx, t: str | None = None):
    """rețeaua spusă explicit în text ("mono" / "tri") sau None — nu se presupune (r5: la toate tipurile)"""
    t = c.t if t is None else t
    if getattr(c, "_tip", None) in ("bransament", "locuinta"):
        t = _masca(t, RE_U_RECEPTOR)       # r8 (#37): „prize 400V și 230V” = tensiunile prizelor, nu rețeaua

    if RE_RETEA_NESTIUTA.search(t):
        t = _masca(t, RE_RETEA_NESTIUTA)
        if not getattr(c, "_retea_nestiuta", False):
            c._retea_nestiuta = True
            m = RE_RETEA_NESTIUTA.search(c.t)
            if m:
                c.foloseste(max(0, m.start() - 20), m.end())
    if RE_MONO_DECLARAT.search(t):
        return "mono"
    return "tri" if RE_TRI_DECLARAT.search(t) else None


def retele_declarate(t: str) -> set:
    """r6: TOATE rețelele scrise în text (pentru contradicții: „tablou monofazat 3x400V”, „TG 230V … 3P”)."""
    t = _masca(t, RE_RETEA_NESTIUTA)
    out = set()
    if RE_MONO_DECLARAT.search(t):
        out.add("mono")
    if RE_TRI_DECLARAT.search(_masca(t, re.compile(r"\bbmpm\w*"))) or re.search(r"\b[34]\s*p\b", t):
        out.add("tri")
    return out


def detecteaza_retea(c: Ctx) -> str:
    """F.5: mono/tri; implicit tri (tablou / PT / CEF / GE — JT industrial)."""
    return retea_declarata(c) or "tri"


# =====================================================================================================
# F.4 Lista de plecări
# =====================================================================================================
RECEPTORI = r"iluminat|prize|priza|forta|motor|motoare|pompa|pompe|compresor|ventilatie"
_TIP_CABLU = r"(?:cyaby|acyaby|cyy-?f|cyy|nyy(?:-j)?|n2xy|na2xy|n2xh(?:-j)?|nhxh(?:-j)?|c2xaby|ac2xaby|cyabyf)"
_ADJ_FAZA = r"(?:\s+(?:monofazat\w*|monofazic\w*|trifazat\w*|trifazic\w*|mono|tri))?"
RE_TRIGGER = re.compile(rf"(?:\b(?P<n>\d+)\s+)?(?<!sub-)(?<!sub)\b(?P<w>plecari|plecare|circuite|plec(?=\s*:)){_ADJ_FAZA}\b")
# r6 (industrial #22): „TG -> TD-P …” = lista plecărilor TG-ului
RE_TRIGGER_SAGEATA = re.compile(r"\b(?:tg\w*|tgd|tablou\w*(?:\s+general)?)\s*(?P<w>->|→)")
# „+” din „P+2” (nivel de clădire) nu e separator de listă (r5 #4); r6: „plus” = separator
RE_SEP = re.compile(r"\s*(?:[;:()]|(?<!\bp)\+|(?<!\d),|,(?!\d)|\bsi\b|\bplus\b|->|→|(?<=[a-z0-9)])\.(?=\s+[a-z]))(?:\s*[;,()])*\s*")   # „(” / „)” = cascadă
RE_ITEM_CAP = re.compile(
    rf"(?:(?P<mult>\d+)\s*(?:×|x\b|(?P<circ>circuite|circuit|circ\.?|plecari|bucati|buc\.?)\s+(?:de\s+)?)\s*)?"
    rf"(?P<curba>[bcd](?=\d))?(?P<val>{NUM})\s*(?P<unit>a|kw|kva|cp|hp|w)?(?![\w²%/])")
RE_NUME_ITEM = re.compile(r"^[^\d\s,;][^,;]*$")
RE_VAL_IN_NUME = re.compile(rf"(?<![\w.,-]){NUM}\s*(?:a|kw|kva|cp|kwh|kvar)\b")
# r6 (industrial #3, #5, #49, #51): numărul ÎNAINTEA numelui — „3 iluminat 10A”, „2 pompe submersibile 11 kW”,
# „8 circuite iluminat B10”, „3 x TD 63A”, „4 bucati …”
RE_PREFIX_N = re.compile(r"^(?P<n>\d+)\s*(?:(?P<x>×|x)\s*|(?P<circ>circuite|circuit|circ\.?|plecari|bucati|buc\.?|pcs)\s+"
                         r"(?:de\s+)?)?(?=[a-z])")
# r6 (industrial #7, #22): item fără putere / calibru — „iluminat grajd 3 circuite”, „prize 4 circ”
RE_FARA_VAL = re.compile(r"^(?P<nume>[a-z][^\d,;]*?)\s+(?P<n>\d+)\s*(?:circuite|circuit|circ\.?|buc\w*\.?|bucati)$"
                         r"|^(?P<n2>\d+)\s*(?:circuite|circuit|circ\.?)\s+(?P<nume2>[a-z][^\d,;]*)$"
                         # r9 (locuințe #36): „iluminat”, „priză exterioară” singure într-o listă cu valori
                         r"|^(?P<nume3>(?:iluminat\w*|priz[ae]\w*)(?:\s+[a-z]+){0,2})$")
RE_RECEPTOR_ITEM = re.compile(r"\b(?:ilumin\w*|priz\w*|motor\w*|motoar\w*|pomp\w*|compresor\w*|ventil\w*|boiler\w*|ac\b|clim\w*"
                              r"|incalz\w*|sudur\w*|polizor\w*|strung\w*|circuit\w*|td\b|te\b"
                              r"|stati\w*\s+(?:de\s+)?incarcare|stati\w*\s+(?:dc|ac|ve|ev)\b|wallbox\w*|incarcator\w*"
                              r"|chiller\w*|extruder\w*|vitrin\w*|lift\w*|ascensor\w*|cta\b|hvac\b|ups\b)")   # r9
# coada unui item (r5 #15, #16, #20, #44, #51): lungime, cosφ, pornire, material, izolație, pozare, receptor
_COADA_ITEM = [
    ("L", re.compile(rf"(?:(?:pe|de|la|lungime|l\s*=)\s+)?(?P<v>\d{{1,3}}(?: \d{{3}})+|{NUM})\s*(?P<u>km|metri|ml|m)\b")),
    # r7 (industrial #3): „prize 16A 5 circuite” — numărul de circuite DUPĂ valoare
    ("ncirc", re.compile(r"(?P<v>\d+)\s*(?:circuite|circuit|circ\.?|bucati|buc\b\.?|plecari)")),
    # r7 (industrial #54): „compresor 22 kW 16 A” — al doilea calibru al aceluiași receptor (contradicție verificată)
    ("In2", re.compile(rf"(?P<v>{NUM})\s*a\b")),
    ("cos", re.compile(rf"cos\s*(?:fi|φ|phi)\s*(?:=|de)?\s*(?P<v>{NUM})")),
    ("pornire", re.compile(r"(?:cu\s+)?(?:pornire\s+)?(?:in\s+)?(?P<v>stea[\s-]*triunghi|y\s*[-/]\s*d\b|convertizor\w*"
                           r"|variator\w*(?:\s+de\s+frecventa)?|\bvfd\b|soft[\s-]*start\w*|soft\b|directa\b|direct\b|dol\b)")),
    # r6 (industrial #39, #40): cablul plecării — „cablu CYABY 5x10”, „CYY-F 5x6”, „cu cablu 4x16 Cu”
    ("cab", re.compile(rf"(?:alimentat\w*\s+)?(?:cu\s+)?(?:cablu\w*\s+(?:tip\s+)?(?P<tip1>{_TIP_CABLU})?|(?P<tip2>{_TIP_CABLU}))\s*"
                       rf"(?P<foc>(?:fe\s*180\s*(?:/\s*)?|e\s*90\s*|ph\s*90\s*)*)"
                       rf"(?:(?P<c>[1-5])\s*×\s*(?P<s>{NUM})(?:\s*\+\s*(?P<n>{NUM}))?(?:\s*(?:mm2?|mm²|mmp)\b)?)?")),
    # r6 (industrial #23): „server 16A cu UPS 10 kVA”
    ("ups", re.compile(rf"cu\s+(?P<v>ups)(?:\s+(?:de\s+)?{NUM}\s*kva\b)?")),

    # r6: „cu DDR 30mA [tip A]”
    ("ddr", re.compile(r"(?:cu\s+)?(?:ddr|rcd|rccb|rcbo|diferential\w*)\s*(?:de\s+)?(?:(?P<v>\d+)\s*ma\b)?"
                       r"(?:\s+tip\s+(?:a|ac|b|f)\b)?")),
    ("poz", re.compile(r"(?:pozat\w*\s+)?(?P<v>direct\s+in\s+pamant|in\s+tub\w*|in\s+pamant|ingropat\w*"
                       r"|in\s+aer(?:\s+pe\s+pat(?:\s+de\s+cabluri)?)?|pe\s+pat(?:\s+de\s+cabluri)?|pat\s+de\s+cabluri"
                       r"|aparent(?:\s+pe\s+perete)?|pe\s+perete|pe\s+zid|in\s+teava|pe\s+jgheab)")),
    ("mat", re.compile(r"(?P<v>al|cupru|aluminiu|cu(?=\s*$|\s+(?:xlpe|pvc|in\s|pe\s|pozat|\d)))\b")),
    ("iz", re.compile(r"(?P<v>xlpe|pvc)\b")),
    ("rec", re.compile(rf"(?P<v>{RECEPTORI})\b")),
    ("fiecare", re.compile(r"(?P<v>fiecare)\b")),
    # r8 (industrial #51): „mot 22kw x3” — multiplicatorul DUPĂ valoare
    ("xn", re.compile(r"[x×]\s*(?P<v>\d{1,2})\b(?!\s*(?:kw|a|m|mm|kva|v)\b)(?![.,]\d)")),
    ("alim", re.compile(r"(?P<v>alimentat\w*|racordat\w*|conectat\w*)\b")),
    # r8: „cu cablu rezistent la foc” / „FE180” pe o plecare = circuit de siguranță (motorul pune NHXH FE180/E90)
    ("foc", re.compile(r"(?:cu\s+)?(?:cablu\w*\s+)?(?P<v>(?:rezistent\w*|ignifug\w*)\s+(?:la\s+)?foc\w*|fe\s*180\w*|nhxh\w*|e\s*90)\b")),
    # r8 (industrial #34): descrierea receptorului după putere („250 kW rezistiv”, „noi”, „de rezervă”) — informativă
    ("desc", re.compile(r"(?P<v>rezistiv\w*|inductiv\w*|electric\w*|nou[aă]?\b|noi\b|existent\w*|activ\w*)")),
    # r9 (industrial #50): locul receptorului („în parcarea magazinului”, „în hală”) — informativ
    ("loc", re.compile(r"(?P<v>(?:in|la|pe)\s+(?:parcar\w*|hal(?:a|ei|e)\b|curte|exterior\w*|subsol\w*|zona\w*|depozit\w*"
                       r"|acoperis\w*|terasa\w*|teren\w*|curtea)(?:\s+(?:magazin\w*|subteran\w*|exterioar\w*|[a-z]+ului|[a-z]+ei))?)\b")),
    ("eta", re.compile(rf"(?:cu\s+)?(?:randament\w*|η|eta)\s*(?:=|de|:)?\s*(?P<v>{NUM})\s*%?")),   # r7: randamentul motorului
    ("sp", re.compile(r"(?P<v>tn-?c-?s|tn-?s|tn-?c|tt)\b(?![\w-])")),       # schema de pământ scrisă după item
    # r6: rețeaua / polii plecării („iluminat 2 kw monofazat”, „TD-1 63A 3P”, „pompa 4 kW trifazata”)
    ("faza", re.compile(r"(?P<v>monofaz\w*|mono\b|trifaz\w*|tri\b|trif\b|[1-4]\s*p(?:\s*[+ ]\s*n)?(?:\s*[+ ]\s*pe)?\b|[13]f\b|230\s*v\b"
                        r"|400\s*v\b|3\s*×\s*400\s*v\b)")),
]
RE_DOAR_TRIGGER = re.compile(rf"^(?:(?P<n>\d+)\s+)?(?:plecari|plecare|circuite|plec){_ADJ_FAZA}"
                             r"(?:\s+(?:noi|nou[aă]?|suplimentar\w*|existent\w*|libere|de\s+rezerva|viitoare))?(?:\s+de)?$"
                             r"|^(?:td-?uri\w*|tablouri\w*|tablourile|sub-?tablouri\w*|consumatori\w*)$")
RE_TRIGGER_REST = re.compile(rf"^(?:(?P<n>\d+)\s+)?(?P<w>plecari|plecare|circuite){_ADJ_FAZA}\s+(?:de\s+)?(?P<rest>.+)$")
RE_CASCADA = re.compile(r"^(?P<nume>.+?)\s+cu\s+(?:sub-?\s*plecari(?:le)?|circuitele)\s*:?\s*(?P<rest>.+)$")
# r6 (industrial #22): „TD-P parter 63A 20m cu iluminat 3 circ, prize 4 circ; …” — „cu” + receptor = sub-plecări
RE_CASCADA_CU = re.compile(r"^(?P<cap>.+?\d\s*(?:a|kw|kva)\b(?:\s+\d+(?:[.,]\d+)?\s*m\b)?)\s+cu\s+(?P<rest>[a-z].+)$")
RE_CU_SUB = re.compile(r"\s+cu\s+(?:sub-?\s*plecari(?:le)?|circuitele|circuite)\s*:?\s*$")
RE_ETICHETA_SECTIE = re.compile(r"^(?:semibar\w*|sectia|sectiunea|sectie|bara|semisectia)\s*(?:nr\.?\s*)?(?P<k>a|b|1|2|i|ii)$")
RE_COD_TD = re.compile(r"^(?:t[dge]-?\s*\d+\w*|t[dge]-[a-z]\w*)\b")
RE_ANTET_TABLOU = re.compile(r"^(?:tablou\w*|tg|tgd|td|te|tgjt|post\w*|pt)\b(?!-)")
POZARE_METODA = [(r"direct\s+in\s+pamant", "D2"), (r"tub|pamant|ingropat|teava", "D1"),
                 (r"pat|aer|jgheab", "E"), (r"aparent|perete|zid", "C")]


def receptor_dupa_nume(nume: str, nivel: int, circuite_finale=False) -> str:
    """C.2: receptorul după nume (fără diacritice, litere mici). r5 #13: mașinile-unelte și utilajele = motor."""
    n = _fara_diacritice(nume or "")
    if "ilumin" in n or re.match(r"il\b|ilum\b", n):
        return "iluminat"
    if "priz" in n:
        return "prize"
    if re.search(RE_MOTOR_NUME, n):
        return "motor"
    return "forta" if (nivel >= 1 or circuite_finale) else "tablou"


RE_MOTOR_NUME = (r"motor|motoar|pomp|compresor|compresoare|\bcomp\b|ventila|moar|concasor|malaxor|strung|frez|banda|transportor|lift|ascensor"
                 r"|hidrofor|polizor|ferastrau|gater|elevator|snec|melc|agitator|tocator|separator\s+lapte|muls")


_PRESCURTARI = [(re.compile(r"^mot\b\.?", re.I), "motor"), (re.compile(r"^il\b\.?", re.I), "iluminat"), (re.compile(r"^ilum\b\.?", re.I), "iluminat"),
                (re.compile(r"^comp\b\.?", re.I), "compresor"), (re.compile(r"^vent\b\.?", re.I), "ventilator"),
                (re.compile(r"^pr\b\.?", re.I), "prize")]


def nume_normalizat(s: str) -> str:
    """F.4 regula 4: numele se păstrează; dacă e scris integral cu litere mici, prima literă devine majusculă.
    Codurile (TD-1, HVAC) rămân neschimbate. NU .capitalize() pe tot șirul (P1-14).
    r7 (#42): prescurtările uzuale la începutul numelui („il”, „comp aer”, „vent.”) se scriu întregi."""
    s = re.sub(r"\s+", " ", s.strip(" ,;:"))
    s = re.sub(r"^(?:[-*•·–—]|\d{1,2}[.)](?=\s))\s*", "", s)       # r8: bullet-ul / numărul rândului nu e parte din nume
    for rx, rep in _PRESCURTARI:
        s = rx.sub(rep, s)
    if s.count("(") > s.count(")"):
        s += ")"                                                  # r6: „TD-P (parter)”
    if re.fullmatch(r"t[dgec]{1,2}-?\s*\d+[a-z]?", s):           # „td-1” = cod de tablou → „TD-1”
        return s.upper()
    if s and s == s.lower():
        return s[0].upper() + s[1:]
    return s


def _bucati(c: Ctx, start: int):
    """Taie textul de la începutul listei în bucăți după separatorii F.4 (păstrând pozițiile)."""
    t = _tl(c)
    poz, out, sep = start, [], ""
    for m in RE_SEP.finditer(t, start):
        if m.start() > poz:
            e_ = m.start()
            while e_ > poz and t[e_ - 1] in ". " and not (e_ - 2 >= poz and t[e_ - 2].isdigit() and t[e_ - 1] == "."):
                e_ -= 1                                 # r8: punctul de la sfârșitul propoziției nu e parte din item
            out.append((poz, e_, sep))

            sep = m.group(0).strip() or ","
        else:                                   # r8: separatori lipiți („) si”, „)) ,”) — se cumulează
            sep = (sep + " " + (m.group(0).strip() or ",")).strip()
        poz = m.end()
    if poz < len(t):
        out.append((poz, len(t.rstrip(" .")), sep))
    return [(s, e, sp) for s, e, sp in out if t[s:e].strip()]


def _coada(text: str):
    """Atributele din coada unui item; (dict, rest neinterpretat)."""
    atr, poz = {}, 0
    while True:
        rest = text[poz:]
        ws = len(rest) - len(rest.lstrip())
        if not rest.strip():
            return atr, ""
        for k, rx in _COADA_ITEM:
            m = rx.match(rest, ws)
            if m and k not in atr:
                atr[k] = m
                poz += m.end()
                break
        else:
            return atr, rest.strip()


def _item(c: Ctx, s: int, text: str, prefix_ok=False, fara_valoare_ok=True):
    """Un item „[N [×|circuite|buc]] [nume] [N×|N circuite de] [B|C|D]valoare [unitate] {coada}” (F.4, r5, r6).
    r6: numărul poate sta înaintea numelui („3 iluminat 10A”, „2 x pompa 7,5kW”); itemul fără valoare
    („iluminat grajd 3 circuite”) se întoarce cu val None (→ întrebare). Întoarce (dict, capăt) sau None."""
    mde = re.match(r"^\s*(?P<n>\d+|unul|una|un|o)\s+de\s+(?=\d)", text)
    if mde:                                     # r7 (#38): „2 de 3 kW”, „unul de 15 CP” — numele se moștenește
        r = _item(c, s + mde.end(), text[mde.end():], prefix_ok, fara_valoare_ok)
        if r and r[0]["nume"] is None:
            it = r[0]
            it["mult"] = int(mde.group("n")) if mde.group("n").isdigit() else 1
            it["_mosteneste"] = True
            it["s"], it["txt"] = s, c.o(s, r[1])
            return it, r[1]
    mp = RE_PREFIX_N.match(text)
    if mp and int(mp.group("n")) >= 1:
        r = _item(c, s + mp.end(), text[mp.end():], prefix_ok, fara_valoare_ok)
        if r and r[0]["nume"] and r[0]["mult"] == 1:
            it = r[0]
            n = int(mp.group("n"))
            it["mult"] = n
            generic = bool(re.match(r"(?:ilumin|priz|circuit)", _fara_diacritice(it["nume"])))
            it["n_circuite"] = bool(n > 1 and (mp.group("circ") and not mp.group("circ").startswith(("buc", "pcs"))
                                               or (generic and not mp.group("x"))))
            if re.fullmatch(r"t[dge]", _fara_diacritice(it["nume"]).strip()):
                it["cod"], it["nume"] = it["nume"].strip().upper(), None
            it["s"], it["txt"] = s, c.o(s, r[1])
            return it, r[1]
    m = atr = None
    capat_rel = None
    for poz in [0] + [x.start() for x in re.finditer(r"(?<=\s)(?:\d|[bcd](?=\d))", text)]:
        if poz and (not RE_NUME_ITEM.match(text[:poz].strip()) or RE_VAL_IN_NUME.search(text[:poz])):
            continue
        mm = RE_ITEM_CAP.match(text, poz)
        if not mm:
            continue
        a, rest = _coada(text[mm.end():])
        if ("In2" in a and mm.group("unit") != "kw") or ("ncirc" in a and not mm.group("unit")):
            continue                                       # „hală 1 100 A”: „1” e din nume, nu valoarea
        if rest:
            if not prefix_ok or not mm.group("unit"):
                continue
            cr = text.index(rest, mm.end())
            while cr > 0 and text[cr - 1] == " ":
                cr -= 1
        else:
            cr = len(text.rstrip())
        m, atr, capat_rel, poz_val = mm, a, cr, poz
        break
    if m is None:
        # r8 (industrial #53): „prize 230V 6 circ” — tensiunea din nume = rețeaua circuitului
        mvf = re.search(r"\s+(?P<v>230|400)\s*v\b", text)
        tf = (text[:mvf.start()] + " " * (mvf.end() - mvf.start()) + text[mvf.end():]) if mvf else text
        mf = RE_FARA_VAL.match(re.sub(r"\s+", " ", tf.strip())) if fara_valoare_ok else None
        if mf:
            nume_t = (mf.group("nume") or mf.group("nume2") or mf.group("nume3")).strip()
            n = int(mf.group("n") or mf.group("n2") or 1)
            ws = len(text) - len(text.lstrip())
            i0 = text.index(nume_t, ws)
            it = {"nume": nume_normalizat(c.o(s + i0, s + i0 + len(nume_t))), "val": None, "unit": None, "mult": n,
                  "copii": None, "rec": None, "L": None, "s": s, "e": s + len(text.rstrip()),
                  "txt": c.o(s, s + len(text.rstrip())), "n_circuite": n > 1, "fara_valoare": True}
            if mvf:
                it["retea"] = "mono" if mvf.group("v") == "230" else "tri"
            if mf.group("nume3"):
                it["_simplu"] = True
            return it, s + len(text.rstrip())
        return None
    nume = None
    if poz_val:
        nume_t = re.sub(r"(?:\s+(?:de|a|cu|la|cate|fiecare|in))+\s*$", "", text[:poz_val].rstrip())
        mvolt = re.search(r"\s+(?P<v>230|400)\s*v\b", nume_t)
        if mvolt:                                          # r7 (#49): „iluminat 230V de 1 kW” = circuit monofazat
            c._retea_nume = (s, "mono" if mvolt.group("v") == "230" else "tri")
            nume_t = nume_t[:mvolt.start()] + nume_t[mvolt.end():]
        mv = re.match(r"\s*(?:alimentam|alimentez|alimentat\w*|avem|am|vreau|un|o|si)\s+(?:(?:un|o)\s+)?", nume_t)
        if mv and nume_t[mv.end():].strip():               # r7 (#21): „alimentăm un motor de 200 kW” → „Motor”
            s, text, poz_val, nume_t = s + mv.end(), text[mv.end():], poz_val - mv.end(), nume_t[mv.end():]
        nume = nume_normalizat(c.o(s, s + len(nume_t))) if nume_t.strip() else None
        if nume and re.fullmatch(r"(?:de|cu|si|la|in)", _fara_diacritice(nume)):
            nume = None
        if nume and re.fullmatch(r"(?:sig(?:urant\w*)?\.?\s+)?(?:nh|mpr|gg|fuzibil\w*)(?:\s+\d{1,2})?", _fara_diacritice(nume).lower()):
            c._prot_item = (s, "GG")                     # r8 (#59): „8 plecări NH 250A” — NH = siguranțe gG, nu un nume
            nume = None
        mal = re.match(r"(?i)^(\S+)\s+alimenteaz\w*\s+(.+)$", nume or "")
        if mal:                                          # r8 (#62): „TE-E2 alimentează TE-Server 32A” → „TE-Server”
            nume = nume_normalizat(mal.group(2))
    unit = {"a": "A", "kw": "kW", "kva": "kVA", "cp": "CP", "hp": "HP", "w": "kW"}.get(m.group("unit"))
    val = numar(m.group("val")) / (1000 if m.group("unit") == "w" else 1)
    if m.group("unit") == "w":
        c.nota(f"„{c.o(s + m.start('val'), s + m.end('unit'))}” = {fmt(val, 3)} kW")
    it = {"nume": nume, "val": val, "unit": unit,
          "mult": int(m.group("mult")) if m.group("mult") else 1, "copii": None,
          "rec": atr["rec"].group("v") if "rec" in atr else None, "L": None, "s": s, "e": s + capat_rel,
          "txt": c.o(s, s + capat_rel), "n_circuite": bool(m.group("circ") and m.group("mult"))}
    rn = getattr(c, "_retea_nume", None)
    if rn and rn[0] == s:
        it["retea"] = rn[1]
    pi_ = getattr(c, "_prot_item", None)
    if pi_ and pi_[0] == s:
        it["prot_tip"] = pi_[1]

    if nume and "faza" not in atr:
        mfz = re.search(r"\b(monofaz\w*|trifaz\w*)\b", _fara_diacritice(nume))
        if mfz:
            it["retea"] = "mono" if mfz.group(1).startswith("mono") else "tri"
    if m.group("curba"):
        it["curba"] = m.group("curba").upper()
        if not unit:
            it["unit"] = "A"                                   # „B10” = MCB curba B, 10 A
    if "faza" in atr:
        v = re.sub(r"\s+", "", atr["faza"].group("v"))
        it["retea"] = "mono" if re.match(r"mono|1p|1f|230", v) or v == "2p" else "tri"
    if "foc" in atr:
        it["siguranta"] = True
    if nume and re.search(r"\brezerv\w*", _fara_diacritice(nume)):
        it["rezerva"] = True                               # r7: pompa de rezervă (1+1) — nu se adună la sarcină
    if "eta" in atr:
        e_ = numar(atr["eta"].group("v"))
        it["randament"] = _nr(e_ / 100 if e_ > 1 else e_)
    if "xn" in atr and it["mult"] == 1 and int(atr["xn"].group("v")) > 1:
        it["mult"] = int(atr["xn"].group("v"))                 # r8 (#51): „mot 22kw x3” = 3 plecări de 22 kW
    if "ncirc" in atr and it["mult"] == 1:
        it["mult"] = int(atr["ncirc"].group("v"))
        it["n_circuite"] = it["mult"] > 1
        if unit == "kW" and it["mult"] > 1 and re.search(rf"\(\s*{it['mult']}\s*(?:circuite|circuit|circ)",
                                                          getattr(c, "t_brut", "")[s:s + capat_rel + 2]):
            # r8 (industrial #1): „iluminat hală LED 18 kW (6 circuite)” = 18 kW împărțiți pe 6 circuite (6 × 3 kW)
            c.nota(f"„{c.o(s, s + capat_rel).strip()})”: {fmt(val)} kW = puterea totală pe {it['mult']} circuite → "
                   f"{it['mult']} × {fmt(val / it['mult'], 2)} kW")
            it["val"] = val = round(val / it["mult"], 3)
    if "In2" in atr and unit == "kW":
        it["In_decl"] = i2 = numar(atr["In2"].group("v"))
        mono = "faza" in atr and re.match(r"mono|1p|230|1f", atr["faza"].group("v"))
        ib = val * 1000 / ((U_MONO if mono else U_TRI) * norme.COSFI_IMPLICIT["motor"])
        if not (i2 / 3 <= ib <= i2 * 1.3):                # r7 (#54): „compresor 22 kW 16 A” = contradicție
            c.probleme.append(("I08", f"Contradicție: „{c.o(s, s + len(text.rstrip())).strip()}” — {fmt(val)} kW înseamnă "
                                      f"≈ {fmt(ib, 0)} A, nu {fmt(i2)} A (I08).",
                               f"Care e valoarea corectă: {fmt(val)} kW (≈ {fmt(ib, 0)} A) sau {fmt(i2)} A "
                               f"(≈ {fmt(i2 * (U_MONO if mono else U_TRI) * norme.COSFI_IMPLICIT['motor'] / 1000)} kW)?"))
    if getattr(c, "_volt_item", None) and s in c._volt_item:
        it["retea"] = c._volt_item[s]
    if "ddr" in atr and atr["ddr"].group("v"):
        it["ddr_mA"] = int(atr["ddr"].group("v"))
    if "ups" in atr:
        it["ups"] = atr["ups"].group(0).strip()
    if "L" in atr:
        it["L"] = numar(atr["L"].group("v").replace(" ", "")) * UNITATI[atr["L"].group("u")][1]
        if " " in atr["L"].group("v"):                             # r6: „TD-1 63A 1 000 m” — separator de mii în listă
            c.intrebari.append(("I03", f"„{atr['L'].group(0).strip()}” în listă = {fmt(it['L'])} m? (separatorul de mii prin "
                                       "spațiu e ambiguu în liste)"))
    if "cos" in atr:
        it["cosfi"] = numar(atr["cos"].group("v"))
    if "pornire" in atr:
        v = atr["pornire"].group("v")
        it["pornire"] = ("stea_triunghi" if re.match(r"stea|y", v) else "convertizor" if re.match(r"conv|var|vfd", v)
                         else "soft" if v.startswith("soft") else "directa")
    cab = {}
    if "cab" in atr:
        mc = atr["cab"]
        tip = mc.group("tip1") or mc.group("tip2")
        if tip:
            cab["material"] = "Al" if tip.startswith("a") or tip.startswith("na") else "Cu"
            if re.search(r"2x|hx", tip):
                cab["izolatie"] = "XLPE"
            cab["tip_cablu"] = tip.upper()                       # r9: tipul impus (motorul deduce materialul / izolația)
        if (tip and tip.startswith("nhx")) or (mc.group("foc") or "").strip():
            it["siguranta"] = True if e_siguranta(it.get("nume") or "") else it.get("siguranta")
            cab["rezistent_foc"] = True                          # r9 (#35): „NHXH FE180 E90” = cablu rezistent la foc
        if mc.group("s") and numar(mc.group("s")) in SECTIUNI_CABLU:
            cab["S_fortat"] = _nr(numar(mc.group("s")))
            if mc.group("n") and numar(mc.group("n")) != numar(mc.group("s")):
                cab["N_fortat"] = _nr(numar(mc.group("n")))
    if "mat" in atr:
        cab["material"] = "Al" if atr["mat"].group("v") in ("al", "aluminiu") else "Cu"
    if "iz" in atr:
        cab["izolatie"] = atr["iz"].group("v").upper()
    if "poz" in atr:
        v = atr["poz"].group("v")
        cab["metoda"] = next(met for rx, met in POZARE_METODA if re.search(rx, v))
    if cab:
        it["cablu"] = cab
    return it, s + capat_rel


def _e_valoare_simpla(c: Ctx, b) -> bool:
    r = _item(c, b[0], _tl(c)[b[0]:b[1]])
    return bool(r) and r[0]["nume"] is None and r[0]["mult"] == 1


def _tl(c: Ctx) -> str:
    """textul pe care se citește lista: copia de lucru cu ce s-a consumat înainte (cablu impus) mascat"""
    return getattr(c, "t_lista", None) or c.t


def _gaseste_trigger(c: Ctx):
    """Cuvântul care deschide lista. „circuite” precedat în aceeași bucată de un nume („iluminat 5 circuite de 16 A”)
    e multiplicator, nu început de listă (r5 #14)."""
    for m in RE_TRIGGER.finditer(_tl(c)):
        if m.group("w") == "circuite":
            bs = max([x.end() for x in RE_SEP.finditer(_tl(c), 0, m.start())] or [0])
            pre = _tl(c)[bs:m.start()].strip().split()
            if pre and pre[-1] not in ("cu", "are", "si", "general", "tablou", "td", "te", "tg", "tabloul", "pe") \
                    and not RE_ANTET_TABLOU.match(" ".join(pre)):
                continue
        return m
    return RE_TRIGGER_SAGEATA.search(_tl(c))


def _start_fara_trigger(c: Ctx):
    """r5 (#4, #13, #43): listă fără „plecări” — începe la prima bucată „nume valoare unitate” care nu e antetul
    tabloului; cel puțin 2 itemi."""
    buc = _bucati(c, 0)
    for i, (s, e, _) in enumerate(buc):
        txt = _tl(c)[s:e]
        mcu = re.match(r"^(?:tablou\w*|tg\w*|td|te)\b[^,;:]*?\s(?:cu|are)\s+(?=\d|[a-z])", txt) if i == 0 else None
        if mcu and _item(c, s + mcu.end(), txt[mcu.end():]):
            return s + mcu.end()                               # r7 (#15): „tablou atelier cu 3 motoare 4 kW și …”
        mtg = re.match(r"^(?:tablou\w*|tgd?|td|te)\s+(?=\d+\s*(?:x\s+|×\s*)?[a-z])", txt) if i == 0 else None
        if mtg and (RE_RECEPTOR_ITEM.search(txt[mtg.end():]) or re.search(RE_MOTOR_NUME, txt[mtg.end():])) \
                and _item(c, s + mtg.end(), txt[mtg.end():]):
            return s + mtg.end()                               # r8 (#5): „tg 3 pompe 7,5kw din pt 250”
        if i == 0 and re.match(r"^[a-z][a-z ]{2,30}$", txt.strip()) and RE_RECEPTOR_ITEM.search(txt) \
                and i + 1 < len(buc) and ":" in buc[i + 1][2] and _item(c, buc[i + 1][0], _tl(c)[buc[i + 1][0]:buc[i + 1][1]]):
            c._eticheta_lista = nume_normalizat(c.o(s, s + len(txt.rstrip())))
            c.foloseste(s, e)
            return buc[i + 1][0]                               # r7 (#62): „pompe: 2 x 18,5 kW Y/D și 1 x 7,5 kW DOL”
        r = _item(c, s, txt)
        if not r or not r[0]["unit"] or not r[0]["nume"] or i == 0 and RE_ANTET_TABLOU.match(txt) \
                and not RE_COD_TD.match(txt) and not re.match(r"^te\s+\w", txt):
            continue
        if not RE_ANTET_TABLOU.match(txt) and (RE_RECEPTOR_ITEM.search(txt) or re.search(RE_MOTOR_NUME, txt)
                                               or RE_ATOM_REC.search(txt)
                                               or re.search(r"\bcuptor\w*|\bplit\w*|\bhot\w*|\bincarcator\w*|\bpres\w*", txt)):
            if not any(_item(c, b[0], _tl(c)[b[0]:b[1]]) for b in buc[i + 1:i + 2]):
                return s                                       # r7 (#20, #55): un singur receptor = o plecare
        urm = [b for b in buc[i + 1:i + 2] if _item(c, b[0], _tl(c)[b[0]:b[1]]) or "(" in b[2]]
        if urm or "(" in (buc[i + 1][2] if i + 1 < len(buc) else ""):
            return s
        return None
    return None


def parseaza_lista(c: Ctx):
    """F.4: găsește lista de plecări și o transformă în itemi (cu cascadă și multiplicatori)."""
    m = _gaseste_trigger(c)
    retea_trig = None
    if m:
        start, capat, cuvant = m.start(), m.end(), m.group("w")
        if cuvant in ("->", "→"):
            start, cuvant = m.start("w"), "plecari"
        mfz = re.search(r"(monofaz\w*|mono\b)|(trifaz\w*|tri\b)", m.group(0))
        if mfz:
            retea_trig = "mono" if mfz.group(1) else "tri"
        if m.group("n") if "n" in m.groupdict() else None:
            s0 = _start_fara_trigger(c)                    # r7: itemi înaintea lui „6 plecări a câte 10 kW”
            if s0 is not None and s0 < start and not re.search(r"\bplec\w*|\bcircuit\w*", _tl(c)[s0:start]):
                start = s0
    else:
        start = _start_fara_trigger(c)
        if start is None:
            return None
        capat, cuvant = start, "plecari"
    bucati = _bucati(c, start)
    top, nr_cerut, parinte, adanc = [], None, None, 0
    stiva = []                                                    # r8: paranteze imbricate (TG → TD → TE → circuite)
    sectie = None                                                 # r8: secția (semibara) curentă la PT cu 2 trafo
    n_top0 = 0
    i = 0
    while i < len(bucati):
        s, e, sep = bucati[i]
        txt = _tl(c)[s:e]
        if ")" in sep:
            for _ in range(sep.count(")")):                       # „)” închide lista de copii (F.4 r. 3)
                if stiva:
                    stiva.pop()
            parinte, adanc = (stiva[-1], len(stiva)) if stiva else (None, 0)
        elif ";" in sep and adanc == 0:
            parinte = None                                        # „;” în afara parantezelor închide cascada
        urm_sep = bucati[i + 1][2] if i + 1 < len(bucati) else ""
        if "(" in urm_sep and not RE_DOAR_TRIGGER.match(txt):     # „NUME [valoare] (LISTA)” → tablou cu copii
            r = _item(c, s, txt)
            nume_txt = RE_CU_SUB.sub("", txt)
            if r and r[0]["val"] is not None and not RE_CU_SUB.search(txt):
                p = r[0]
                p["copii"] = []
            else:
                e2 = s + len(nume_txt.rstrip())
                p = {"nume": nume_normalizat(c.o(s, e2)), "val": None, "unit": None, "mult": 1, "copii": [],
                     "rec": None, "L": None, "s": s, "e": e, "txt": c.o(s, e2)}
            (parinte["copii"] if (parinte and stiva) else top).append(p)
            stiva.append(p)
            parinte, capat, adanc = p, e, len(stiva)
            i += 1
            continue
        if re.match(r"^(?:cu|toate\s+cu|fiecare\s+cu|si)\s+(?:ddr|rcd|rccb|rcbo|diferential\w*)\b", txt) and top:
            # r8 (industrial #39): „…, cu DDR 30mA” după listă = protecția diferențială a circuitelor listate (atribut)
            c.nota(f"„{c.o(s, e).strip()}” = protecție diferențială pe circuitele listate (desenată pe prize / circuitele finale)")
            capat = e
            i += 1
            continue
        msec = RE_ETICHETA_SECTIE.match(txt)

        if msec:                                                  # r8 (#17): „semibara A: …; semibara B: …”
            for it_ in top[n_top0:]:
                if sectie:
                    it_.setdefault("sectie", sectie)
            n_top0 = len(top)
            sectie = 2 if msec.group("k") in ("b", "2", "ii", "doi", "doua") else 1
            parinte, adanc, stiva = None, 0, []
            capat = e
            i += 1
            continue
        md = RE_DOAR_TRIGGER.match(txt)
        if md:
            if md.group("n"):
                nr_cerut = int(md.group("n"))
            if not md.group(0).startswith(("plecar", "circuit")) and not re.match(r"\d", md.group(0)):
                parinte, adanc = None, 0                          # „TD-uri:” = etichetă de grup (r6 #54)
            capat = e
            i += 1
            continue
        mc = RE_CASCADA.match(txt)
        if mc:
            r = _item(c, s + mc.start("rest"), mc.group("rest"))
            if not r:
                break
            p = {"nume": nume_normalizat(c.o(s, s + mc.end("nume"))), "val": None, "unit": None, "mult": 1,
                 "copii": [r[0]], "rec": None, "L": None, "s": s, "e": e, "txt": c.o(s, e)}
            top.append(p)
            parinte, capat = p, r[1]
            i += 1
            continue
        mt = RE_TRIGGER_REST.match(txt)
        if mt and not (mt.group("w") == "circuite" and m is None):
            r = _item(c, s + mt.start("rest"), mt.group("rest"), prefix_ok=True)
            if not r:
                r0 = _item(c, s, txt)                                  # r8 (#15): „6 circuite prize” fără calibru
                if r0 and r0[0].get("fara_valoare"):
                    (parinte["copii"] if parinte else top).append(r0[0])
                    capat = r0[1]
                    i += 1
                    continue
                break
            it, capat = r
            n = int(mt.group("n")) if mt.group("n") else None
            urm = bucati[i + 1] if i + 1 < len(bucati) else None
            if n and it["nume"] is None and it["mult"] == 1 and not (urm and _e_valoare_simpla(c, urm)):
                it["mult"], it["forma_n_de"] = n, True                 # „4 plecări de 63 A” (F.4 r. 2)
                it["txt"] = c.o(s, capat)
            elif n and it["nume"] and it["mult"] == 1 and mt.group("w") == "circuite" \
                    and re.match(r"(?:ilumin|priz)", _fara_diacritice(it["nume"])):
                it["mult"], it["n_circuite"] = n, n > 1          # r6 (#3): „8 circuite iluminat B10” = 8 circuite
                it["txt"] = c.o(s, capat)
            elif n:
                nr_cerut = n
            (parinte["copii"] if parinte else top).append(it)
            i += 1
            if capat < e:                                              # rest neinterpretabil → lista se termină
                break
            continue
        r = _item(c, s, txt)
        if not r:
            mcu = RE_CASCADA_CU.match(txt)                             # r6: „TD-P 63A 20m cu iluminat 3 circ, …”
            rp = _item(c, s, mcu.group("cap"), fara_valoare_ok=False) if mcu else None
            rc = _item(c, s + mcu.start("rest"), mcu.group("rest")) if rp else None
            if rp and rc and rp[0]["val"] is not None:
                p = rp[0]
                p["copii"] = [rc[0]]
                p["e"], p["txt"] = e, c.o(s, e)
                if parinte and adanc == 0:
                    parinte = None
                (parinte["copii"] if parinte else top).append(p)
                parinte, capat = p, rc[1]
                i += 1
                continue
            break                                                      # ex. „lungime 40 m”, „cablu cupru” → sfârșit
        it, capat = r
        if parinte and adanc == 0 and RE_COD_TD.match(txt):
            parinte = None                                             # cod de tablou = item de nivel superior
        frati_ = parinte["copii"] if parinte else top
        if it["nume"] is None and it["mult"] == 1 and frati_ and frati_[-1].get("unit") and it["unit"] \
                and {frati_[-1]["unit"], it["unit"]} == {"kW", "A"} and not frati_[-1].get("copii"):
            # r8 (industrial #56): „pompa 15 kW, 10 A” — calibrul / puterea fără nume ține de itemul dinainte
            pr = frati_[-1]
            P_, I_ = (pr["val"], it["val"]) if pr["unit"] == "kW" else (it["val"], pr["val"])
            ib_ = P_ * 1000 / (U_TRI * norme.COSFI_IMPLICIT["motor"])
            if not (I_ / 4 <= ib_ <= I_ * 1.3):                # calibrul poate fi de până la ~4 × Ib (circuit de priză / MCB)
                c.probleme.append(("I08", f"Contradicție: „{pr['txt'].strip()}, {it['txt'].strip()}” — {fmt(P_)} kW înseamnă "
                                          f"≈ {fmt(ib_, 0)} A, nu {fmt(I_)} A (I08).",
                                   f"{pr['nume'] or 'Plecarea'}: {fmt(P_)} kW (≈ {fmt(ib_, 0)} A) sau {fmt(I_)} A "
                                   f"(≈ {fmt(I_ * U_TRI * norme.COSFI_IMPLICIT['motor'] / 1000)} kW)? Valorile nu se potrivesc."))
            else:
                c.nota(f"„{it['txt'].strip()}” = calibrul plecării {pr['nume']} (nu o plecare separată)")
            pr["txt"] = pr["txt"] + ", " + it["txt"]
            i += 1
            continue
        if it["nume"] is None and (it.get("_mosteneste") or getattr(c, "_eticheta_lista", None)):
            frati = parinte["copii"] if parinte else top
            baza = getattr(c, "_eticheta_lista", None) or next((re.sub(r"\s+\d+$", "", f["nume"]) for f in reversed(frati)
                                                               if f.get("nume")), None)
            if baza:                                                   # r7: numele grupului / al itemului dinainte
                it["nume"] = baza if getattr(c, "_eticheta_lista", None) and not it.get("_mosteneste") else \
                    f"{baza} {fmt(it['val'])} {it['unit'] or ''}".rstrip()
        (parinte["copii"] if parinte else top).append(it)
        i += 1
    if not top and m is None:
        return None
    for it_ in top[n_top0:]:
        if sectie:
            it_.setdefault("sectie", sectie)
    if any(it_.get("sectie") for it_ in top):                    # itemii dinaintea primei etichete = secția 1
        for it_ in top:
            it_.setdefault("sectie", 1)
    if retea_trig:
        for it in top:
            it.setdefault("retea", retea_trig)
    c.consumat.append((start, capat))
    return {"itemi": top, "nr_cerut": nr_cerut, "s": start, "e": capat, "cuvant": cuvant}


def _unitate_comuna(c: Ctx, itemi: list) -> bool:
    """F.4 r. 1: un item fără unitate primește unitatea primului item următor care are unitate."""
    purtata, folosita = None, False
    for it in reversed(itemi):
        if it["copii"] is not None:
            _unitate_comuna(c, it["copii"])
            continue
        if it.get("fara_valoare"):
            continue
        if it["unit"]:
            purtata = it["unit"]
        elif purtata:
            it["unit"], folosita = purtata, True
        else:
            c.probleme.append(("I03", f"Valoarea {fmt(it['val'])} din listă nu are unitate (A sau kW).",
                               "Valorile din listă sunt în A (calibre) sau în kW (puteri)?"))
    if folosita:
        c.nota(f"unitatea „{purtata}” se aplică tuturor numerelor din listă (unitate comună)")
    return folosita


def _conversii_unitati(c: Ctx, itemi: list):
    """r5: „30 kVA” pe o plecare = S → P = S·0,9 (cosφ presupus, declarat); „15 CP” → kW."""
    for it in itemi:
        if it["copii"] is not None:
            _conversii_unitati(c, it["copii"])
        if it["unit"] == "kVA" and it["val"] is not None:
            p = round(it["val"] * COSFI, 2)
            c.nota(f"„{it['txt'].strip()}”: {fmt(it['val'])} kVA = puterea aparentă a plecării → P = "
                   f"{fmt(it['val'])}·{fmt(COSFI, 2)} = {fmt(p)} kW (cosφ {fmt(COSFI, 2)} presupus)")
            it["val"], it["unit"] = p, "kW"
        elif it["unit"] == "HP" and it["val"] is not None:                # r8 (#29): „10 HP” = 7,46 kW
            p = round(it["val"] * 0.7457, 2)
            c.nota(f"„{it['txt'].strip()}”: {fmt(it['val'])} HP = {fmt(p)} kW (1 HP = 0,7457 kW)")
            it["val"], it["unit"] = p, "kW"
        elif it["unit"] == "CP" and it["val"] is not None:
            p = round(it["val"] * KW_PE_CP, 2)
            c.nota(f"„{it['txt'].strip()}”: {fmt(it['val'])} CP = {fmt(p)} kW (1 CP = 0,7355 kW)")
            it["val"], it["unit"] = p, "kW"


def expandeaza(c: Ctx, itemi: list, nivel: int, tip: str, circuite_finale: bool) -> list[dict]:
    """Multiplicatori + nume generate (F.4 r. 2) → plecări finale {nume, valoare, unitate, receptor, L_m, copii}.
    r5: „NUME N circuite de X” → o plecare cu `n_circuite` = N (motorul o desface în „NUME 1…N”)."""
    out = []
    for it in itemi:
        n = it["mult"]
        rec_txt = it["rec"]
        if it.get("fara_valoare") or (it["val"] is None and it["copii"] is None):
            out.append({"nume": it["nume"] or f"Circuit {len(out) + 1}", "valoare": None, "unitate": None,
                        "receptor": receptor_dupa_nume(it["nume"] or "", nivel, circuite_finale), "n_circuite": n,
                        "fara_valoare": True, "txt": it["txt"].strip()})
            continue
        grup = it.get("n_circuite") and n > 1 and (it["nume"] or rec_txt)
        if n > 1 and grup:
            c.nota(f"„{it['txt'].strip()}” = {n} circuite {it['nume'] or nume_normalizat(rec_txt)} 1…{n} de "
                   f"{fmt(it['val'])} {it['unit'] or ''}".rstrip())
        elif n > 1:
            if it.get("forma_n_de"):
                c.nota(f"„{it['txt'].strip()}” = {n} plecări identice de {fmt(it['val'])} {it['unit'] or ''}".strip())
            else:
                c.nota(f"„{it['txt'].strip()}” = {n} plecări de {fmt(it['val'])} {it['unit'] or ''} "
                       f"(nu {fmt(n * it['val'])} {it['unit'] or ''})".replace("  ", " "))
        if it["L"] is not None:                                        # F.4 r. 6
            c.nota(f"„{it['txt'].strip()}”: lungimea scrisă după calibru ({fmt(it['L'])} m) aparține plecării "
                   f"{it['nume'] or ''}".rstrip())
        if it["nume"] and re.search(r"\s\d+$", it["nume"]) and n == 1:
            c.nota(f"„{it['txt'].strip()}” = numele „{it['nume']}” + {fmt(it['val'])} {it['unit']} "
                   "(separatorul de mii prin spațiu NU se acceptă în liste)")
        for k in range(1, (1 if grup else n) + 1):
            if it.get("cod"):
                nume = f"{it['cod']}-{k}"
            elif it["nume"]:
                nume = it["nume"] if (n == 1 or grup) else f"{it['nume']} {k}"
            elif rec_txt:
                nume = nume_normalizat(rec_txt) if grup else f"{nume_normalizat(rec_txt)} {k}"
            elif nivel == 0 and not circuite_finale:
                nume = f"TD-{len(out) + 1}"
            else:
                nume = f"Circuit {len(out) + 1}"
            rec = receptor_dupa_nume(rec_txt or nume, nivel, circuite_finale)
            p = {"nume": nume, "valoare": _nr(it["val"]), "unitate": it["unit"], "receptor": rec}
            if grup:
                p["n_circuite"] = n
            if it["L"] is not None:
                p["L_m"] = _nr(it["L"])
            for kk in ("cosfi", "pornire", "cablu", "retea", "curba", "ddr_mA", "ups", "fara_valoare", "randament", "rezerva",
                       "sectie", "prot_tip", "siguranta", "_simplu"):
                if it.get(kk) is not None:
                    p[kk] = copy.deepcopy(it[kk])
            if p.get("pornire") and p["receptor"] != "motor":
                p["receptor"] = "motor"
            if it["copii"] is not None:
                p["copii"] = expandeaza(c, it["copii"], nivel + 1, tip, True)
                p["receptor"] = "tablou"
            out.append(p)
    return out


# =====================================================================================================
# F.5 Celelalte elemente: material, izolație, pozare, grupare, cartuș
# =====================================================================================================
def detecteaza_material(c: Ctx) -> str | None:
    """„Cu”/„Al” cu majusculă = material (F.2.4). Excepție tolerată (vezi DISCREPANTE_CHAT.md, F26):
    „al”/„cu” minuscul izolat la sfârșitul unui segment, imediat după o lungime sau după „cablu”."""
    t, o = c.t, c.orig
    if re.search(r"\bcupru\b|\bcyaby\b|\bcyy\b|\bn2xy\b|\bc2xaby\b", t) or re.search(r"\bCu\b", o):
        return "Cu"
    if re.search(r"\baluminiu\b|\bacyaby\b|\bac2xaby\b|\bna2xy\b", t) or re.search(r"\bAl\b", o):
        return "Al"
    m = re.search(rf"(?:{NUM}\s*(?:m|km)|\bcablu)\s+(al|cu)\s*(?:[,;.]|$)", t) or re.search(
        rf"\bcablu\s+(al|cu)\s+{NUM}\s*(?:m|km|metri)\b", t)
    if m:
        return {"al": "Al", "cu": "Cu"}[m.group(1)]
    return None


def detecteaza_izolatie(c: Ctx) -> str | None:
    if re.search(r"\bxlpe\b|\d?2x[a-z]|pe reticulat", c.t):
        return "XLPE"
    if re.search(r"\bpvc\b", c.t):
        return "PVC"
    return None


def detecteaza_metoda(c: Ctx) -> str | None:
    t = re.sub(r"priz\w*\s+(?:propri\w*\s+)?de\s+pamant(?:\s+propri\w*)?", lambda m: " " * len(m.group(0)), c.t)
    t = _masca(t, RE_FARA_PE)                       # r7 (#3): „fără pământ” nu e pozare în pământ
    if re.search(r"direct\s+in\s+pamant", t):
        return "D2"
    if re.search(r"\bpamant|\bingropat|\bsant\b|\btub|\bteava|\bcanalizatie", t):
        return "D1"
    if re.search(r"pat\s+de\s+cabluri|jgheab\s+perforat|scara\s+de\s+cabluri|\bin\s+aer\b", t):
        return "E"
    if re.search(r"\baparent|pe\s+perete|pe\s+zid|\bplafon", t):
        return "C"
    return None


RE_GRUPARE = re.compile(r"acelasi\s+(?:traseu|sant|pat)|\bimpreuna\b|pat\s+comun")


def _sfarsit_camp(t: str, poz: int) -> int:
    m = re.compile(r"\s*(?:[,;]|\s(?:in|din|jud\.?|judetul)\b|\.\s|\.?$)").search(t, poz)
    return m.start() if m else len(t)


def detecteaza_beneficiar(c: Ctx):
    """F.5 beneficiar: din textul original, până la virgulă / „în” / „din” / „jud”. Întoarce (text, capăt)."""
    m = re.search(r"\b(?:beneficiar(?:ul)?|client(?:ul)?)\s*[:\-]?\s+", c.t)
    if m:
        e = _sfarsit_camp(c.t, m.end())
        return c.o(m.end(), e).strip() or None, e
    for m in re.finditer(r"\b(?:pentru|pt)\s+((?:s\.?\s?c\.?\s+)?[^,;]+?\s(?:srl|sa|pfa|ii|if))\b", c.t):
        cuv = c.o(m.start(), m.start(1)).strip()
        sufix = c.o(m.end(1) - 4, m.end(1)).strip()
        if cuv in ("pentru", "pt") and sufix.isupper():                # „PT” majuscul = post de transformare
            return c.o(m.start(1), m.end(1)).strip(), m.end(1)
    return None, None


_LOC = r"[a-z][a-z\-]*(?:\s+[a-z][a-z\-]*){0,2}"
RE_ADR_JUD = re.compile(r"(?:\b(?:in|din|la|loc\.?|localitatea|com\.?|comuna|sat(?:ul)?|oras(?:ul)?|mun\.?|municipiul)"
                        rf"\s+|(?:^|[,;])\s*)(?P<loc>{_LOC})\s*,?\s*(?:jud\.?|judetul)\s*(?P<jud>[a-z][a-z\-]*(?:\s+[a-z][a-z\-]*)?)")


def _majuscul(s: str) -> bool:
    return all(w[:1].isupper() for w in s.split())


def detecteaza_adresa(c: Ctx, capat_benef):
    """F.5 adresă: localitate + județ din textul original, fără diacritice adăugate."""
    for m in RE_ADR_JUD.finditer(c.t):
        s_loc = m.start("loc")
        mp = re.match(r"(?:in|din|la|localitatea|comuna|satul|sat|orasul|oras|municipiul)\s+", c.t[s_loc:m.end("loc")])
        if mp:                                                         # „, în Ciumeghiu, jud. …” → fără prepoziție
            s_loc += mp.end()
        loc = c.o(s_loc, m.end("loc")).strip()
        cuv_jud = c.o(m.start("jud"), m.end("jud")).split()
        jud = " ".join(w for i, w in enumerate(cuv_jud) if i == 0 or w[:1].isupper())
        if loc and _majuscul(loc) and jud[:1].isupper():
            return {"localitate": loc, "judet": jud}
    if capat_benef is not None:                                        # „beneficiar X, Oradea”
        m = re.match(r"\s*,\s*([A-ZĂÂÎȘȚ][a-zăâîșț\-]+(?:\s+[A-ZĂÂÎȘȚ][a-zăâîșț\-]+)*)\s*(?:[,;.]|$)",
                     c.orig[capat_benef:])
        if m:
            return {"localitate": m.group(1), "judet": None}
    m = re.search(r"\b(?:în|in|din|loc\.?|localitatea|com\.?|comuna|sat|oraș|oras|mun\.?)\s+"
                  r"([A-ZĂÂÎȘȚ][a-zăâîșț\-]+(?:[ \-][A-ZĂÂÎȘȚ][a-zăâîșț\-]+)*)", c.orig)
    if m:
        return {"localitate": m.group(1), "judet": None}
    return {"localitate": None, "judet": None}


def detecteaza_cartus(c: Ctx) -> dict:
    benef, capat = detecteaza_beneficiar(c)
    adresa = detecteaza_adresa(c, capat)
    m = re.search(r"plan[sș]a\s*e\s*-?\s*(\d+)", c.t)
    plansa = f"E{int(m.group(1)):02d}" if m else None
    m = re.search(r"\bfaza\s+(sf|pth|pt|dtac|dde|de)\b", c.t)
    faza = {"pth": "PTh"}.get(m.group(1), m.group(1).upper()) if m else None
    return {"beneficiar": benef, "adresa": adresa, "plansa": plansa, "faza": faza}


# =====================================================================================================
# Note din citirea textului (F.2) — declarate în „Am presupus”
# =====================================================================================================
def note_text(c: Ctx, vals: list[dict]):
    o = c.orig
    if re.search(r"\bpt\b", o):
        if re.search(r"\bPT\b", o):
            c.nota("„PT” majuscul = post de transformare; „pt” minuscul = „pentru”")
        else:
            c.nota("„pt” minuscul = „pentru” (nu post de transformare)")
    if re.search(r"\bsi\b", o):
        c.nota("„si” = „și” (fără diacritice)")
    m = re.search(r"\bcu\s+(\d+)\s+(plec\w*|circuite)", o)
    if m:
        c.nota(f"„cu {m.group(1)} {m.group(2)}” = număr de plecări, NU material Cu")
    for v in vals:
        brut = c.o(v["s"], v["e"]).strip()
        if v["s_aprox"] is not None:
            c.nota(f"„{c.o(v['s_aprox'], v['e']).strip()}” = {fmt(v['val'])} {v['marime']}, aproximativ")
        if "," in v["txt"]:
            c.nota(f"„{brut}”: {v['txt']} cu virgulă zecimală (virgula = separator zecimal)")
        if v["u"] in ("mwp", "mva", "mw", "mwh", "w") and v["marime"] != "m":
            c.nota(f"„{brut}” = {fmt(v['val'])} {v['marime']}")
    m = re.search(r"\bsol(?:ul)?\s+(umed|uscat|nisipos|argilos)", c.t)
    if m:
        c.nota(f"„sol {m.group(1)}” nu se convertește automat: rezistivitatea termică rămâne 2,5 K·m/W "
               "(conservator); se poate introduce numeric")


# =====================================================================================================
# Extragerea pe tipuri de schemă → (puteri pentru `extras`, intrare_fizica)
# =====================================================================================================
def _prima(vals, marime):
    return next((v for v in vals if v["marime"] == marime), None)


def _lungime_generala(vals):
    return _prima(vals, "m")


def extrage_bransament(c: Ctx, vals, intr, ex):
    puteri = {}
    mik = RE_IK.search(c.mascat())
    if mik:                                    # r8 (#25): „Ik = 3 kA” din ATR = Ik3 la punctul de racord, nu calibru
        intr["Ik3_OD_kA"] = _nr(numar(mik.group("v")))
        c.consumat.append((mik.start(), mik.end()))
        vals = [v for v in vals if not (mik.start() <= v["s"] < mik.end())]
        c.nota(f"„{c.o(mik.start(), mik.end()).strip()}” = curentul de scurtcircuit la punctul de racord (Ik3_OD_kA)")

    P, I, S = _prima(vals, "kW"), _prima(vals, "A"), _prima(vals, "kVA")
    cos = intr.get("cosfi", COSFI)
    if P:
        puteri["P_kW"] = _nr(P["val"])
        intr["P_kW"] = _nr(P["val"])
        if I:                                           # r5 (P1-9): Q-ul declarat se păstrează
            puteri["Q_In_A"] = intr["Q_In_A"] = _nr(I["val"])
            c.nota(f"„{c.o(I['s'], I['e']).strip()}” = calibrul Q al branșamentului (declarat); Ib din P = {fmt(P['val'])} kW")
    elif I:
        puteri["Ib_A"] = intr["Ib_A"] = _nr(I["val"])               # B.1.1: Ib direct, fără P echivalent
        c.nota(f"{fmt(I['val'])} A interpretat ca Ib (curent maxim absorbit); cosφ {fmt(cos, 2)} folosit doar pentru ΔU")
    elif S:
        puteri["S_kVA"] = intr["S_kVA"] = _nr(S["val"])             # B.1.1: Ib = S/(√3·400), fără cosφ
        ib = S["val"] * 1000 / (U_MONO if ex["retea"] == "mono" else U_TRI)
        c.nota(f"{fmt(S['val'])} kVA la un branșament = putere aparentă: Ib = {fmt(S['val'] * 1000, 0)}/"
               f"{'230' if ex['retea'] == 'mono' else '(√3·400)'} = {fmt(ib)} A; cosφ {fmt(cos, 2)} folosit doar pentru ΔU")
    L = _lungime_generala(vals)
    if L:
        ex["lungimi_m"] = {"C2": _nr(L["val"])}
        intr["L_coloana_m"] = _nr(L["val"])
        c.nota(f"cablul descris („{c.o(L['s_aprox'] or L['s'], L['e']).strip()}” = {fmt(L['val'])} m) = coloana C2 "
               "dintre BMPT și tabloul consumatorului; racordul C1 aparține OD (conform ATR)")
    imp = getattr(c, "_cablu_impus", None)
    if imp and imp.get("material"):
        ex["material"] = imp["material"]
    if ex["material"]:
        intr["material"] = ex["material"]
    if ex["izolatie"] or ex["metoda"] or imp:
        intr["cablu"] = {k: v for k, v in (("material", ex["material"]), ("izolatie", ex["izolatie"]),
                                           ("metoda", ex["metoda"])) if v}
        intr["cablu"].update({k: v for k, v in (imp or {}).items() if k != "n_fortat" or v > 1})
    # măsura și tipul de bloc (F.5 „semidirect”; C.1)
    if re.search(r"bmpti|semidirect|\bindirect|transformatoare\s+de\s+curent", c.t) or re.search(r"\bTC\b", c.orig):
        ex["masura_ceruta"] = intr["masura_ceruta"] = "semidirecta"
    m = re.search(r"\bbmpt([di])\s*-\s*(\d+)\b", c.t)
    if m:
        ex["bmpt_cerut"] = f"BMPT{m.group(1)}-{m.group(2)}"
    elif re.search(r"\bbmptd\b", c.t):
        ex["bmpt_cerut"] = "BMPTd"
    msan = re.search(r"\btablou\w*\s+(?:de\s+)?(?:organizare\s+de\s+)?santier\w*[^,;.]*", c.t)
    if msan:                                           # r8 (P1 locuințe #37): tabloul de șantier = plecările branșamentului
        c.foloseste(msan.start(), msan.end())
        c.intrebari.append(("I02", f"„{c.o(msan.start(), msan.end()).strip()}”: câte prize 400 V (CEE 3P+N+PE) și 230 V, cu ce "
                                   "calibre? Desenez branșamentul provizoriu de șantier; tabloul de șantier (cu DDR 30 mA "
                                   "pe prize) se completează după răspuns."))
    m = re.search(rf"\b3\s*×\s*({NUM})\s*a\b", c.t)
    if m and ex["retea"] == "mono":                     # I08: „monofazat 3×63 A”

        c.probleme.append(("I08", f"Contradicție: „monofazat” și „{c.o(m.start(), m.end())}” (I08).",
                           f"Branșament monofazat (max. 40 A) sau trifazat {m.group(1)} A?"))
    return puteri


RE_SCHEMA_PAMANT = [(re.compile(r"\btn-?c-?s\b"), "TN-C-S"), (re.compile(r"\btn-?s\b"), "TN-S"),
                    (re.compile(r"\btn-?c\b(?!-)"), "TN-C"), (re.compile(r"(?<![\w-])tt(?![\w-])"), "TT")]
RE_RA = re.compile(rf"\b(?:ra|rp|rezistent\w*(?:\s+(?:de\s+dispersie|a\s+prizei|prizei))?|priz\w*\s+(?:de\s+pamant\s+)?"
                   rf"(?:propri\w*\s+)?(?:de\s+)?)\s*(?:=|de|:)?\s*({NUM})\s*(?:ω|ohm\w*)")


RE_SCHEMA_IT = re.compile(r"\b(?:schema|schemei|retea\w*|sistem\w*|regim\w*|neutru\w*)\s+(?:de\s+tip\s+)?it\b|\bneutru\s+izolat")


RE_FARA_PE = re.compile(r"\bfara\s+(?:conductor\w*\s+(?:de\s+)?)?(?:pamant|impamantare|protectie|pe\b|nul\s+de\s+protectie)"
                        r"|\bnu\s+am\s+(?:pamant|impamantare|pe\b)|\b(?:doar|numai)\s+faza\s+si\s+nul")


def schema_pamant(c: Ctx, intr: dict, ex: dict):
    """r5 (P0-1 industrial, P1-12 PV): TN-C-S / TN-S / TN-C / TT + RA pentru ORICE tip de schemă.
    r6: „tt” cu litere mici (N06); mai multe scheme incompatibile („TN-S și TT”, „TT dar și TN-C-S”) → I08; schema IT
    (neutru izolat) → în afara domeniului (I12), nu TN-C-S tacit."""
    gasite = []
    for rx, v in RE_SCHEMA_PAMANT:
        for m in rx.finditer(c.t):
            if not any(s <= m.start() < e for s, e, _ in gasite):
                gasite.append((m.start(), m.end(), v))
    for m in RE_SCHEMA_IT.finditer(c.t):
        gasite.append((m.start(), m.end(), "IT"))
    for s, e, _ in gasite:
        c.foloseste(s, e)
    tipuri = list(dict.fromkeys(v for _, _, v in sorted(gasite)))
    sp = None
    mpen = re.search(r"(?<!fara )(?<!fara  )\bpen\b(?:\s+(?:comun\w*|unic|neseparat\w*))?", c.t)
    if mpen and re.search(r"\b(?:nu\s+(?:exista|are|avem|e)|fara|lipsa|lipseste)\s+(?:\w+\s+)?$", c.t[max(0, mpen.start() - 22):mpen.start()]):
        c.foloseste(max(0, mpen.start() - 22), mpen.end() + 5)     # r8 (locuințe #32): „nu există PEN bun” → motivul TT
        mpen = None
    mpn = re.search(r"\b(?:leg\w*|lega\w*|unesc|unim|uneste|conectez|conectam|fac\w*\s+punte\w*)\s+(?:pe|pamantul|impamantarea)\s+"
                    r"(?:la|cu)\s+(?:nul\w*|n\b|neutru\w*)|\bpunte\w*\s+(?:intre\s+)?pe\s*[-–/ ]\s*n\b|\bpe\s+(?:la|cu)\s+nul\w*", c.t)
    if mpn and "TT" in tipuri:                      # r8 (P1 locuințe #34): puntea PE–N cerută într-o schemă TT
        c.foloseste(mpn.start(), mpn.end())
        mm = re.search(r"\bca\s+sa\s+nu\s+mai\s+[^,.;]*", c.t[mpn.end():])
        if mm:
            c.foloseste(mpn.end() + mm.start(), mpn.end() + mm.end())
        c.intrebari.append(("I08", f"„{c.o(mpn.start(), mpn.end()).strip()}”: legarea PE la nul în tablou NU e permisă în schema TT "
                                   "(la întreruperea nulului carcasele ajung sub tensiune, iar DDR-ul nu mai protejează). "
                                   "Declanșările DDR se rezolvă căutând defectul de izolație / verificând RA. Generez schema TT "
                                   "corectă (PE din priza proprie, fără punte PE–N)?"))
    if "TT" in tipuri and mpen:                     # r7 (#41): „TT dar cu PEN comun” = contradicție
        c.foloseste(mpen.start(), mpen.end())
        c.probleme.append(("I08", f"Contradicție: schema TT și „{c.o(mpen.start(), mpen.end()).strip()}” (în TT nu există PEN: "
                                  "neutrul și PE sunt separate, PE la priza proprie) (I08).",
                           "Schema e TT (priză de pământ proprie, fără PEN), sau TN-C-S (PEN din rețea, separat în BMPT/BMPM)?"))
        return
    mfp = RE_FARA_PE.search(c.t)
    if mfp:                                         # r7 (#3): „doar fază și nul, fără pământ” = fără conductor PE
        c.foloseste(mfp.start(), mfp.end())
        c.intrebari.append(("I08", f"„{c.o(mfp.start(), mfp.end()).strip()}”: instalația nu are conductor de protecție PE "
                                   "(TN-C vechi) — DDR-urile nu protejează fără PE. Se trage PE nou din BMPM (TN-C-S, separare "
                                   "PEN) sau se face priză de pământ proprie (TT)? (desenat TN-C-S)"))
    if "IT" in tipuri:
        # r6 (industrial #13): IT se transmite explicit — motorul o blochează (V28) cu explicație; întrebare, nu TN tacit
        intr["schema_pamant"] = ex["schema_pamant"] = "IT"
        c.intrebari.append(("I12", "Schema IT (neutru izolat / impedant, cu controlor permanent de izolație) nu e acoperită "
                                   "de dimensionare (V28). Instalația e într-adevăr IT? Dacă nu, ce schemă are: TN-C-S, "
                                   "TN-S sau TT?"))
        return
    if "TT" in tipuri and len(tipuri) > 1:
        c.probleme.append(("I08", "Contradicție: schema de legare la pământ e descrisă și " + " și ".join(tipuri) + " (I08).",
                           "Ce schemă de legare la pământ are instalația: " + " sau ".join(tipuri)
                           + "? (TT = priză de pământ proprie, fără PEN; TN = PEN separat în BMPT/BMPM)"))
        return
    if tipuri:
        sp = next(v for v in ("TN-C-S", "TN-S", "TN-C", "TT") if v in tipuri)
        if {"TN-C", "TN-S"} <= set(tipuri) and "TN-C-S" not in tipuri:
            sp = "TN-C-S"
    if not sp:
        mp = re.search(r"priz\w*\s+(?:de\s+pamant\s+propri|propri\w*\s+de\s+pamant)", c.t)
        if mp:
            sp = "TT"
            c.foloseste(mp.start(), mp.end())
    if sp == "TN-C" and getattr(c, "_tip", None) in ("tablou", "locuinta") and re.search(r"\bpriz\w*|\bddr\b|\brcd\b", c.t):
        # r7 (#57): TN-C cu prize → DDR-ul cerut nu funcționează pe PEN — întrebare (motorul blochează V27)
        c.intrebari.append(("I08", "Schema TN-C cu circuite de prize: DDR-ul de 30 mA (obligatoriu la prize) nu funcționează pe "
                                   "conductorul PEN. Se separă PEN-ul la intrarea tabloului (TN-C-S, cablu cu PE), sau "
                                   "rămâne TN-C (fără prize protejate DDR)?"))
    if sp:
        intr["schema_pamant"] = ex["schema_pamant"] = sp
    m = RE_RA.search(c.mascat()) or re.search(rf"(?<![\w.,])({NUM})\s*(?:ω|ohm\w*)", c.mascat())

    if m:
        intr["RA_ohm"] = ex["RA_ohm"] = _nr(numar(m.group(1)))
        c.foloseste(m.start(), m.end())


SECTIUNI_CABLU = set(norme.SECTIUNI_STD) | {400.0, 500.0, 630.0}
_NU_UNITATE_CABLU = r"(?!\s*(?:a|kw|kva|kvar|w|cp|m|km|v|kv|ma|kwh|kwp|ohm)\b)(?![\d]|[.,]\d)"
RE_CABLU_IMPUS = re.compile(
    rf"(?P<par>\d)\s*[×x]\s*\(\s*(?:{_TIP_CABLU}\s+)?(?P<c1>[1-5])\s*[×x]\s*(?P<s1>{NUM})(?:\s*\+\s*(?P<n1>{NUM}))?"
    rf"(?:\s*(?:mm2?|mm²|mmp))?\s*\)"
    # r8 (industrial #25): „2 x NA2XY 4x240 în paralel” = 2 cabluri în paralel (fără paranteze)
    rf"|(?P<par5>[2-4])\s*[×x]\s*{_TIP_CABLU}\s*(?P<c5>[2-5])\s*[×x]\s*(?P<s5>{NUM})(?:\s*\+\s*(?P<n5>{NUM}))?"
    rf"|(?<![\d,.])(?P<c2>[2-5])\s*[×x]\s*(?P<s2>{NUM})(?:\s*\+\s*(?P<n2>{NUM}))?{_NU_UNITATE_CABLU}"
    rf"|(?<![\d,.×])(?P<s3>{NUM})\s*(?:mm2|mm²|mmp)\b")
RE_ITEM_INAINTE = re.compile(rf"(?<![\w.,-]){NUM}\s*(?:a|kw|kva)\b")


def cablu_impus(c: Ctx):
    """r5 (#41, #52, PV #19): „3x150+70 Cu”, „3x185+95 Al”, „3x(4x150)Al” = cablu impus (nu plecări / puteri).
    r6: „2x(NA2XY 4x240)” (2 cabluri în paralel), „4x(1x240) Al” (monopolare), „Al 16 mmp”; cablul scris după
    calibrul unei plecări („TD-1 63A cablu CYABY 5x10”) aparține plecării, nu alimentării; „3x400V” nu e cablu.
    Întoarce {S_fortat, N_fortat?, n_fortat?, material?} sau None; textul se consumă."""
    t = c.mascat()
    for m in RE_CABLU_IMPUS.finditer(t):
        sec = numar(m.group("s1") or m.group("s2") or m.group("s3") or m.group("s5"))
        if sec not in SECTIUNI_CABLU:
            continue
        ctx_inainte = c.t[max(0, m.start() - 30):m.start()]
        dupa = c.t[m.end():m.end() + 12]
        if not (re.search(r"cablu|coloan|alimenta|cyaby|acyaby|n2xy|na2xy|cyy|c2xaby|ac2xaby", ctx_inainte)
                or re.match(r"\s*(?:mm|al\b|cu\b|cupru|aluminiu)", dupa) or m.group("par") or m.group("s3") or m.group("par5")):
            continue
        bs = max([x.end() for x in re.compile(r"(?<!\d),|,(?!\d)|[;:]|\.\s|\bplecari\b").finditer(t, 0, m.start())] or [0])
        if RE_ITEM_INAINTE.search(t[bs:m.start()]) and not re.search(r"coloan|alimentar|alimenteaz", t[bs:m.start()]) \
                and not RE_ANTET_TABLOU.match(t[bs:m.start()].strip()):     # r8 (#57): „TD 80 kW alimentat cu CYABY 5x16”

            continue                                       # r6 (#39, #40): cablul unei plecări
        d = {"S_fortat": _nr(sec)}
        mpar = re.search(r"\b(?P<n>\d|doua|doi|trei|patru)\s+cabluri\s+(?:\w+\s+){0,2}?(?:in\s+)?paralel\w*", c.t[max(0, m.start() - 40):m.start()]) \
            or re.match(r"[^,;]{0,20}?\b(?P<n>\d|doua|doi|trei|patru)\s+(?:cabluri\s+)?(?:in\s+)?paralel\w*", c.t[m.end():])
        if not mpar and re.match(r"\s*(?:mm2?|mm²|mmp)?\s*(?:al|cu|aluminiu|cupru)?\s*(?:in\s+)?paralel\w*", c.t[m.end():]):
            # r9 (industrial #34): „2 cabluri CYABY 3x185+95 în paralel” — numărul înainte, „în paralel” după
            mpar = re.search(rf"\b(?P<n>\d|doua|doi|trei|patru)\s+cabluri\s+(?:{_TIP_CABLU}\s*)?$",
                             c.t[max(0, m.start() - 40):m.start()])
            if mpar:
                mp2 = re.match(r"\s*(?:mm2?|mm²|mmp)?\s*(?:al|cu|aluminiu|cupru)?\s*(?:in\s+)?paralel\w*", c.t[m.end():])
                c.consumat.append((m.end(), m.end() + mp2.end()))
        if mpar:                                           # r7 (#7): „2 cabluri în paralel 3x240+120 Al”
            d["n_fortat"] = _NUMERAL.get(mpar.group("n")) or int(mpar.group("n"))
        n = m.group("n1") or m.group("n2") or m.group("n5")
        if n and numar(n) != sec:
            d["N_fortat"] = _nr(numar(n))
        monopolar = m.group("c1") == "1"
        if m.group("par") and int(m.group("par")) > 1 and not monopolar:
            d["n_fortat"] = int(m.group("par"))
        if m.group("par5"):
            d["n_fortat"] = d["n_paralel"] = int(m.group("par5"))

        mm = re.match(r"\s*(?:mm2?|mm²|mmp)?\s*(al|aluminiu|cu|cupru)\b", dupa)
        e = m.end()
        if mm:
            d["material"] = "Al" if mm.group(1).startswith("al") else "Cu"
            e += mm.end()
        mt = re.search(rf"\b({_TIP_CABLU})\s*$", c.t[max(0, m.start() - 12):m.start()]) or (
            re.search(_TIP_CABLU, m.group(0)) if (m.group("par") or m.group("par5")) else None)
        if mt and "material" not in d:
            d["material"] = "Al" if mt.group(0).strip().startswith(("a", "na")) else "Cu"
        if mt:          # r9: tipul cablului impus (motorul deduce materialul și izolația: N2XY / NA2XY = XLPE)
            d["tip_cablu"] = re.sub(r"\s+", "", mt.group(0)).upper().replace("CYY-F", "CYY-F")
            if re.match(r"n2x|na2x|n2xh|c2x|ac2x", mt.group(0).strip()):
                d["izolatie"] = "XLPE"
        mpre = re.search(r"\b(al|aluminiu|cu|cupru)\s+$", c.t[max(0, m.start() - 10):m.start()])
        if mpre and "material" not in d and (m.group("s3") or re.search(r"\b(?:Al|Cu)\b", c.o(m.start() - 10, m.start()))):
            d["material"] = "Al" if mpre.group(1).startswith("al") else "Cu"
        if mpar:
            ws = c.t.rfind(mpar.group(0), 0, m.start())
            if ws >= 0:
                c.consumat.append((ws, ws + len(mpar.group(0))))
            if d["n_fortat"] > 1:
                d["n_paralel"] = d["n_fortat"]
        c.consumat.append((m.start(), e))
        c.nota(f"„{c.o(m.start(), e).strip()}” = cablu impus: S = {fmt(sec)} mm²"
               + (f", N {fmt(numar(n))} mm²" if d.get("N_fortat") else "")
               + (f", {d['n_fortat']} cabluri în paralel" if d.get("n_fortat") else "")
               + (f", {m.group('par')} conductoare monopolare (3F + N)" if monopolar else "")
               + " (secțiunea se verifică, nu se alege)")
        return d
    return None


def _detectii_cablu(c: Ctx, t: str) -> dict:
    """material / izolație / metodă pe un text dat (ex. textul din afara listei)."""
    class _C:
        pass
    x = _C()
    x.t = t
    x.orig = "".join(ch if t[i] != " " or c.t[i] == " " else " " for i, ch in enumerate(c.orig)) \
        if len(c.orig) == len(c.t) == len(t) else t
    return {"material": detecteaza_material(x), "izolatie": detecteaza_izolatie(x), "metoda": detecteaza_metoda(x)}


RE_ORIG_TG = re.compile(
    r"\b(?:din|de\s+la)\s+(?:tgd?|te|td|tablou\w*(?:\s+general\w*)?)(?:-[a-z0-9]+)?"
    r"(?:\s+(?:existent\w*|exist\b\.?|casa|casei|cladir\w*|parter\w*|etaj\w*|general\w*|hal(?:a|ei)|fabric\w*|principal\w*))*"
    r"|\bsursa\s+(?:tgd?|tablou\w*)(?:\s+(?:existent\w*|exist\b\.?))?|\b(?:tgd?|tablou\w*)\s+existent\w*")
RE_ORIG_BMPT = re.compile(
    rf"\b(?:din|prin|de\s+la)\s+(?:bmp[tm]\w*|bransament\w*|retea\w*(?:\s+publica)?)(?:\s+(?:trifazat\w*|existent\w*|nou))*"
    rf"(?:\s+(?:3\s*×\s*)?(?P<q>{NUM})\s*a\b)?(?:\s+(?P<p>{NUM})\s*kw\b)?"
    rf"(?:\s+(?:trifazat\w*|trifazic\w*|tri|mono\w*|monofazat\w*))?|\bretea\w*\s+publica")


def origine_tablou(c: Ctx, intr: dict, ex: dict):
    """r5 (P1-9, P1-11): sursa tabloului — „din PT (propriu)” → pt_propriu (+ Sn); „din TG/TGD existent” →
    tg_existent; „din rețea / prin BMPT” → bmpt. Nedeclarată → nu se scrie (motorul nu contează pe DDR-ul din amonte)."""
    if getattr(c, "_origine_gata", False):
        return
    c._origine_gata = True
    t = c.mascat()
    ma = re.search(rf"\b(?:prin(?:tr-?un)?|din|cu)\s+(?:intrerup\w*|disjunctor\w*|separator\w*|mccb|sigurant\w*)\s+(?:de\s+)?"
                   rf"(?P<v>{NUM})\s*a\b", t)
    if ma:                                                  # r7 (#56): protecția din amonte (în tabloul sursă)
        intr["In_Q_amonte_A"] = _nr(numar(ma.group("v")))
        c.consumat.append((ma.start(), ma.end()))
        t = c.mascat()
    surse = []
    m = RE_PT_SURSA.search(t)
    if m and not m.group(0).startswith("faza"):
        surse.append(("pt_propriu", m))
    m2 = RE_ORIG_TG.search(t)
    if m2:
        surse.append(("tg_existent", m2))
    m3s = list(RE_ORIG_BMPT.finditer(t))
    m3 = next((x for x in m3s if x.group("q")), m3s[0] if m3s else None)   # r11: „de la rețea …, din BMPT 63 A”
    if m3:
        surse.append(("bmpt", m3))
        for x in m3s:
            if x is not m3:
                c.consumat.append((x.start(), x.end()))
    for _, mm in surse:                        # sursa (cu „alimentare / alimentat / sursa” din fața ei) nu e plecare
        s0 = mm.start()
        mp = re.search(r"(?:\b(?:alimentat\w*|alimentare|alimentarea|sursa|sursă)\s*(?:normal\w*\s*)?(?:retea\w*\s*)?)$",
                       t[max(0, s0 - 25):s0])
        if mp:
            s0 = max(0, s0 - 25) + mp.start()
        c.consumat.append((s0, mm.end()))
    kinds = {k for k, _ in surse}
    if kinds == {"pt_propriu", "tg_existent"}:
        m_tg = next(mm for k, mm in surse if k == "tg_existent")
        if re.match(r"(?:din|de\s+la)\s+(?:td|te)[\w.\-]+", m_tg.group(0)):
            # r11 (industrial #44): „… din TD-stație, alimentare din PT 250 kVA” — lanțul PT → TD-stație: tabloul descris e
            # TD-stație, sursa lui = PT (nu „două surse”)
            c.nota(f"„{c.o(m_tg.start(), m_tg.end()).strip()}” = tabloul descris; sursa lui = PT-ul (lanț de alimentare, nu "
                   "două surse)")
            surse = [x for x in surse if x[0] == "pt_propriu"]
    if len({k for k, _ in surse}) > 1:
        desc = " și ".join(f"„{c.o(mm.start(), mm.end()).strip()}”" for _, mm in surse)
        c.probleme.append(("I08", f"Contradicție: tabloul are două surse ({desc}) (I08).",
                           "Din ce sursă se alimentează tabloul: PT propriu, tablou existent sau BMPT? (două surse cu "
                           "comutare = schemă GE/ATS sau AAR, desenată separat)"))
    if not surse:
        return
    k, m = surse[0]
    intr["origine"] = ex["sursa_alimentare"] = k
    if k == "pt_propriu":
        sn = m.group("sn") or m.group("sn2") or m.group("sn3") or m.group("sn4")
        if sn:
            intr["pt_Sn_kVA"] = _nr(numar(sn))
            if m.group("sn4"):
                c.nota(f"„{c.o(m.start(), m.end()).strip()}”: {sn} = puterea trafo-ului sursă ({sn} kVA, din seria standard)")
        mu = re.match(r"\s*(?:trafo\s+)?(uscat\w*|in\s+ulei|ulei)\b", t[m.end():]) or \
            re.search(r"(uscat\w*|in\s+ulei|ulei)\b", m.group("tr") or "")
        if mu:
            c.foloseste(m.end(), m.end() + mu.end())
            c.nota(f"trafo-ul PT-ului sursă e {'uscat' if mu.group(1).startswith('uscat') else 'în ulei'} (informativ; "
                   "Ik3 la bara TG se calculează din Sn)")
        if "propriu" not in m.group(0):
            c.nota(f"„{c.o(m.start(), m.end()).strip()}” = alimentare din bara JT a unui post de transformare "
                   "(origine „pt_propriu”; dacă e PT-ul OD prin BMPT, schimbați originea)")
    elif k == "bmpt" and m.group("q"):
        c._q_sursa = (numar(m.group("q")), m)
    if k == "bmpt" and m.groupdict().get("p"):
        # r7 (industrial #8, #12): „din BMPT 70 kW” = puterea aprobată a sursei (= P tablou), NU o plecare
        c._p_sursa = (numar(m.group("p")), m)
        c.nota(f"„{c.o(m.start(), m.end()).strip()}” = sursa tabloului (BMPT) cu puterea aprobată "
               f"{fmt(numar(m.group('p')))} kW → P tablou (nu plecare)")


RE_IK = re.compile(rf"\bik\w*\s*(?:3(?=\s*(?:=|:|max\b|la\b|de\b))\s*)?(?:max\s*)?(?:la\s+)?(?:bara\s+)?(?:tg\w*\s+|tablou\w*\s+)?"
                   rf"(?:(?:pcc|pcr|bmpt|punct\w*\s+de\s+(?:racord\w*|conectare|delimitare))\s*)?(?:=|de|:)?\s*"
                   rf"(?P<v>{NUM})\s*ka\b")


RE_N_TRAFO_PT = re.compile(rf"\b(?P<n>2|doua|doi)\s*(?:[x×]\s*)?(?:transformatoare|trafo\w*)\b")


def _cablu_mt(c: Ctx, intr: dict):
    """r10 (industrial #49): „Cablu MT 3x(1x150) A2XS(FL)2Y 18/30 kV, 200 m de la PA la PT” — cablul MT de racord
    (informativ pe planșă: `cablu_MT` {S, tip, L_m, U0_U}); „18/30 kV” = izolația cablului, nu tensiunea rețelei."""
    m = re.search(r"\bcablu\w*\s+(?:de\s+)?mt\b", c.t)
    if not m:
        return
    rest = c.t[m.end():m.end() + 160]
    cab = {}
    ms = re.search(rf"(?:3\s*×\s*)?\(?\s*1\s*×\s*(?P<s>{NUM})\s*\)?", rest)
    if ms:
        cab["S_mm2"] = _nr(numar(ms.group("s")))
    mt = re.search(r"\b(n?a2xs\w*(?:\s*\(\w+\)\s*\w*)?|n?a2xsy\w*|a2xs\(fl\)2y)", rest)
    if mt:
        cab["tip"] = c.o(m.end() + mt.start(), m.end() + mt.end()).strip()
    mu = re.search(r"izolatie\s+u0/u\s+(?P<u>[\d,.]+-\d+)", rest)
    if mu:
        cab["U0_U_kV"] = mu.group("u").replace("-", "/")
    ml = re.search(rf"(?P<l>{NUM})\s*m\b", rest)
    if ml:
        cab["L_m"] = _nr(numar(ml.group("l")))
        c.foloseste(m.end() + ml.start(), m.end() + ml.end())
        mpa = re.search(r"\s*(?:de\s+la\s+\w+\s+)?(?:pana\s+)?(?:la\s+pt)?", rest[ml.end():])
        if mpa:
            c.foloseste(m.end() + ml.end(), m.end() + ml.end() + mpa.end())
    if cab:
        intr["cablu_MT"] = cab
        c.foloseste(m.start(), m.end() + (ms.end() if ms else 0))
        c.nota("cablul MT de racord (informativ): " + ", ".join(f"{k} {v}" for k, v in cab.items()))


def _topologie_pt(c: Ctx, intr: dict, ex: dict):
    """r10 (P0 industrial #8, #30, #47): PT cu 2 transformatoare — `n_trafo: 2` + `cupla` („în paralel pe aceeași bară” =
    închisă; „cuplă longitudinală” = deschisă, interblocaj 2 din 3); ATS între cele 2 trafo = `sursa_rezerva: "trafo"`
    (fără GE). Motorul desenează topologia; interpretorul doar emite cheile."""
    t = c.t
    m = RE_N_TRAFO_PT.search(t)
    if m and not intr.get("n_trafo"):
        intr["n_trafo"] = ex["n_trafo"] = 2
        c.foloseste(m.start(), m.end())
        c.nota(f"„{c.o(m.start(), m.end()).strip()}” = 2 transformatoare (n_trafo = 2)")
    if intr.get("n_trafo") != 2:
        return
    mp = re.search(r"\bin\s+paralel\b(?:\s+pe\s+(?:aceeasi|aceeași|o\s+singura)\s+bar\w*(?:\s+jt)?)?|\bcupl\w*\s+(?:normal\s+)?inchis\w*", t)
    mc = re.search(r"\bcupl\w*(?:\s+(?:longitudinal\w*|de\s+bare|automat\w*|deschis\w*|normal\s+deschis\w*|pe\s+jt|jt))*", t)
    ma = RE_ATS_TRAFO.search(t)
    if mp:
        intr["cupla"] = ex["cupla"] = "inchisa"
        c.foloseste(mp.start(), mp.end())
        c.nota(f"„{c.o(mp.start(), mp.end()).strip()}” = cele 2 trafo în paralel (cupla închisă) — Ik3 la bară cu ambele "
               "trafo în funcțiune (Icu corespunzător)")
    elif ma:
        intr["cupla"] = ex["cupla"] = "deschisa"
        c.nota("ATS între trafo: cupla de bare JT normal deschisă, interblocaj „2 din 3” (Q T1, Q T2, QC)")
    if ma:
        intr["sursa_rezerva"] = ex["sursa_rezerva"] = "trafo"
        intr["comutare"] = "ATS"
        c.foloseste(ma.start(), ma.end())
        mr = re.search(r"\(?\s*rezerv\w*\s+(?:de\s+)?100\s*%\s*\)?|\brezerv\w*\s+reciproc\w*", t)
        if mr:
            c.foloseste(mr.start(), mr.end())
        c.nota(f"„{c.o(ma.start(), ma.end()).strip()}” = ATS între cele 2 transformatoare (sursa de rezervă = al doilea "
               "trafo, rezervă 100 %) — fără grup electrogen")
    for ms in re.finditer(r"\b(?:tg|tgjt|tablou\w*)?\s*cu\s+(?:2|doua)\s+(?:semibare|sectii|sectiuni)(?:\s+de\s+bare)?", t):
        c.foloseste(ms.start(), ms.end())


def extrage_tablou(c: Ctx, vals, intr, ex, tip):
    """Tablou (C.2) și PT (C.5): puterea/calibrul tabloului în afara listei + plecările."""
    puteri = {}
    m = RE_IK.search(c.mascat())
    if m:
        c.consumat.append((m.start(), m.end()))
        intr["Ik3_sursa_kA"] = _nr(numar(m.group("v")))
        vals = [v for v in vals if not (m.start() <= v["s"] < m.end())]
    if tip == "pt":
        S = next((v for v in vals if v["marime"] == "kVA" and _proprietar_kva(c, v) != "ge"), None)
        if S:
            puteri["Sn_kVA"] = _nr(S["val"])
            intr["Sn_kVA"] = _nr(S["val"])
            c.foloseste(S["s"], S["e"])
            mx = re.search(r"(?<![\w.,])(\d+)\s*×\s*$", c.t[max(0, S["s"] - 6):S["s"]])
            if mx and int(mx.group(1)) == 2:           # r6 (industrial #24): „PT zidit 2x630 kVA” → n_trafo 2 (motor)
                c.foloseste(max(0, S["s"] - 6) + mx.start(), S["e"])
                intr["n_trafo"] = ex["n_trafo"] = 2
                c.nota(f"„{c.o(max(0, S['s'] - 6) + mx.start(), S['e']).strip()}” = 2 transformatoare de {fmt(S['val'])} kVA "
                       "în paralel pe barele JT (n_trafo = 2)")
            elif mx and int(mx.group(1)) > 2:
                c.foloseste(max(0, S["s"] - 6) + mx.start(), S["e"])
                c.probleme.append(("I12", f"„{c.o(max(0, S['s'] - 6) + mx.start(), S['e']).strip()}” = "
                                          f"{mx.group(1)} transformatoare în același post: în afara domeniului aplicației "
                                          "(un singur trafo pe schemă) (I12).",
                                   f"Generez câte o schemă pentru fiecare transformator de {fmt(S['val'])} kVA (cu "
                                   "plecările lui), sau un singur trafo?"))
        u_mt = {}
        for mk in re.finditer(rf"\b(?P<u1>{NUM})\s*/\s*0[.,]4\s*kv\b|\b(?P<u3>{NUM})\s*kv\b", c.t):
            u = numar(mk.group("u1") or mk.group("u3"))
            if 1 < u <= 40:
                u_mt.setdefault(u, mk)
        if len(u_mt) > 1:                               # r7 (#58): „trafo 20/0,4 kV … tensiunea MT 15 kV” = contradicție
            desc = " și ".join(f"„{c.o(m_.start(), m_.end()).strip()}”" for m_ in u_mt.values())
            for m_ in u_mt.values():
                c.foloseste(m_.start(), m_.end())
            c.probleme.append(("I08", f"Contradicție: tensiunea MT e scrisă de două ori diferit ({desc}) (I08).",
                               "Rețeaua MT a postului e de " + " sau ".join(f"{fmt(u)} kV" for u in u_mt)
                               + "? (trafo-ul și celula MT se aleg pentru tensiunea rețelei)"))
        for mk in re.finditer(rf"\b(?P<u1>{NUM})\s*/\s*0[.,]4\s*kv\b|\b(?P<u3>{NUM})\s*kv\b", c.t):
            u = numar(mk.group("u1") or mk.group("u3"))
            c.foloseste(mk.start(), mk.end())
            if u <= 1 or len(u_mt) > 1:
                continue
            if u in (6, 10, 15, 20):                    # r6 (#29): tensiunea MT declarată → U_MT_kV (motor)
                intr["U_MT_kV"] = ex["U_MT_kV"] = int(u)
                if u != 20:
                    c.nota(f"„{c.o(mk.start(), mk.end()).strip()}” = rețea MT {fmt(u)} kV (celula și siguranțele MT pentru "
                           f"{fmt(u)} kV)")
                continue
            if abs(u - 20) > 0.01:
                c.probleme.append(("I12", f"„{c.o(mk.start(), mk.end()).strip()}”: rețea MT de {fmt(u)} kV — aplicația "
                                          "acoperă doar PT 20/0,4 kV (siguranțe / celule MT de 24 kV) (I12).",
                                   f"Postul e alimentat la {fmt(u)} kV? Celula trafo și siguranțele MT se aleg pentru "
                                   f"{fmt(u)} kV din tabelul producătorului — confirmați că desenez schema JT cu MT 20 kV "
                                   "doar orientativ, sau indicați datele celulei MT."))
                break
        msk = re.search(rf"\b(?:s\"?\s*kq|scc|sk|putere\w*\s+de\s+scurtcircuit)\w*(?:\s+(?:retea\w*|mt))?\s*(?:=|de|:)?\s*"
                        rf"(?P<v>{NUM})\s*mva\b", c.t)
        if msk:
            intr["SkQ_MVA"] = ex["SkQ_MVA"] = _nr(numar(msk.group("v")))
            c.foloseste(msk.start(), msk.end())
            c.nota(f"„{c.o(msk.start(), msk.end()).strip()}” = puterea de scurtcircuit a rețelei MT S\"kQ (declarată)")
        muk = re.search(rf"\bu\s*k\w*\s*(?:=|de|:)?\s*(?P<v>{NUM})\s*%", c.t)
        if muk:
            c.foloseste(muk.start(), muk.end())
            intr["uk_pct"] = ex["uk_pct"] = _nr(numar(muk.group("v")))      # r10 (P0 industrial #65): uk declarat
            c.nota(f"„{c.o(muk.start(), muk.end()).strip()}” = tensiunea de scurtcircuit declarată (uk_pct = "
                   f"{fmt(intr['uk_pct'])} %, folosită la Ik3 în locul valorii din tabel)")
        _topologie_pt(c, intr, ex)
        _cablu_mt(c, intr)
        if re.search(r"(?:celul\w*|protectie)\s+(?:a\s+)?(?:trafo\s+)?cu\s+sigurant", c.t):
            ex["celula_trafo"] = intr["celula_trafo"] = "sigurante"
        elif re.search(r"(?:celul\w*|protectie)\s+(?:a\s+)?(?:trafo\s+)?cu\s+intrerup(?:a)?tor", c.t):
            ex["celula_trafo"] = intr["celula_trafo"] = "intreruptor"
        elif re.search(r"\bcelul\w*\s+(?:de\s+)?intrerup\w*|\bintrerup\w*\s+(?:in\s+)?(?:vid|sf6)\b"
                       r"|\bprotecti\w*\s+(?:de\s+tip\s+)?50\s*/\s*51\b", c.t):
            # r9 (industrial #20): „celula întreruptor vid cu protecții 50/51” = celula trafo cu întreruptor (nu SF)
            ex["celula_trafo"] = intr["celula_trafo"] = "intreruptor"
            for mm in re.finditer(r"\bcelul\w*\s+(?:de\s+)?intrerup\w*(?:\s+(?:in\s+)?(?:vid|sf6))?|\bintrerup\w*\s+(?:in\s+)?(?:vid|sf6)\b"
                                  r"|(?:cu\s+)?protecti\w*\s+(?:de\s+tip\s+)?50\s*/\s*51\b", c.t):
                c.foloseste(mm.start(), mm.end())
            c.nota("celula trafo cu întreruptor (vid / SF6) și relee 50/51 — nu separator cu siguranțe MT")
        if re.search(r"\bpta\b|\baerian\w*|pe\s+stalp|\bstalp\w*", c.t):   # r6 (industrial #26): PTA pe stâlp
            ex["pt_aerian"] = intr["pt_aerian"] = True
            for mm in re.finditer(r"\bpta\b|\baerian\w*|pe\s+stalp|\bstalp\w*", c.t):
                c.foloseste(mm.start(), mm.end())
            c.avert.append("PTA pe stâlp: separatorul și siguranțele MT (MPR) sunt pe stâlp, fără celule MT de interior — "
                           "verificați partea MT a planșei")
        if re.search(r"\buscat\w*|\brasina|\bcast\s*resin", c.t):
            intr["trafo_izolatie"] = ex["trafo_izolatie"] = "uscat"
        elif re.search(r"\bulei\b|\bin\s+ulei", c.t):
            intr["trafo_izolatie"] = ex["trafo_izolatie"] = "ulei"
        celule = []
        mlmt = re.search(r"celul\w*\s*(?:mt\s*)?:?\s*(?P<s>[lmt](?:\s*\+\s*[lmt]){1,6})\b(?:\s*\(?\s*(?P<p>sigurant\w*|intrerup\w*))?",
                         c.t)
        if re.search(r"celul\w*\s+(?:de\s+)?linie\s+(?:de\s+)?intrare[\s-]*(?:si\s+)?iesire|intrare[\s-]+iesire", c.t) or (
                re.search(r"\bintrare\s+(?:de\s+)?linie|\blinie\s+(?:de\s+)?intrare", c.t)
                and re.search(r"\biesire\s+(?:de\s+)?linie|\blinie\s+(?:de\s+)?iesire", c.t)):
            celule = ["linie_intrare", "linie_iesire"]           # r8 (#18): „intrare linie, ieșire linie”
        elif mlmt:                                                # r8 (#59): „celule L+L+M+T (siguranțe)”
            celule = [{"l": "linie", "m": "masura", "t": "trafo"}[x] for x in re.findall(r"[lmt]", mlmt.group("s"))]
            c.foloseste(mlmt.start(), mlmt.end())
            if mlmt.group("p"):
                ex["celula_trafo"] = intr["celula_trafo"] = "sigurante" if mlmt.group("p").startswith("sig") else "intreruptor"
            c.nota(f"„{c.o(mlmt.start(), mlmt.end()).strip()}” = celulele MT: " + " + ".join(celule))
        elif re.search(r"(\d+)\s+celul\w*\s+(?:de\s+)?linie|celul\w*\s*:?\s*(\d+)\s*(?:×\s*)?(?:celul\w*\s+)?(?:de\s+)?linie",
                       c.t):
            mc = re.search(r"(\d+)\s+celul\w*\s+(?:de\s+)?linie|celul\w*\s*:?\s*(\d+)\s*(?:×\s*)?(?:celul\w*\s+)?(?:de\s+)?linie",
                           c.t)
            celule = ["linie"] * int(mc.group(1) or mc.group(2))
        elif re.search(r"celul\w*\s+(?:de\s+)?linie", c.t):
            celule = ["linie"]
        if re.search(r"masur\w*\s+(?:pe\s+|in\s+|de\s+)?mt\b|celul\w*\s+(?:de\s+)?masur", c.t):
            intr["masura"] = ex["masura"] = "MT"
            if "masura" not in celule:
                celule.append("masura")
        elif re.search(r"masur\w*\s+(?:pe\s+|in\s+|de\s+)?(?:jt|joasa\s+tensiune)\b", c.t):
            intr["masura"] = ex["masura"] = "JT"
            mj = re.search(r"masur\w*\s+(?:pe\s+|in\s+|de\s+)?(?:jt|joasa\s+tensiune)\b", c.t)
            c.foloseste(mj.start(), mj.end())
            if re.search(r"semidirect", c.t):
                intr["masura_ceruta"] = "semidirecta"
            elif re.search(r"masur\w*\s+(?:pe\s+|in\s+|de\s+)?jt\s+direct\w*|\bmasur\w*\s+direct\w*", c.t):
                intr["masura_ceruta"] = ex["masura_ceruta"] = "directa"      # r6 (industrial #26)
        if celule and "trafo" not in celule and re.search(r"(?:protecti\w*|celul\w*)\s+(?:de\s+)?trafo", c.t) \
                and re.search(r"celul\w*\s+mt\s*:|celul\w*\s*:", c.t):
            celule.append("trafo")                                 # r8 (#18): „…, protecție trafo cu întrerupător”
        if celule:
            intr["celule_mt"] = ex["celule_mt"] = celule
    else:
        origine_tablou(c, intr, ex)
        vals = [v for v in vals if not any(s <= v["s"] < e for s, e in c.consumat)]
        P, I = _prima(vals, "kW"), _prima(vals, "A")
        ps = getattr(c, "_p_sursa", None)
        if ps:
            puteri["P_kW"] = intr["P_kW"] = _nr(ps[0])
        elif P:
            puteri["P_kW"] = _nr(P["val"])
            intr["P_kW"] = _nr(P["val"])
            c.foloseste(P["s"], P["e"])
        qs = getattr(c, "_q_sursa", None)
        if qs and not I:                                # r6 (industrial #6, #15, #45): „TG din BMPT 250A”
            q, mq = qs
            I = {"val": q, "s": mq.start("q"), "e": mq.end(), "s_aprox": None}
            c.nota(f"„{c.o(mq.start(), mq.end()).strip()}”: calibrul din BMPT {fmt(q)} A → Q1 al tabloului {fmt(q)} A "
                   "(Q1 ≤ protecția din amonte)")
        if I:
            c.foloseste(I["s"], I["e"])
            q = I["val"]
            serie = norme.MCCB_IN_A
            if q not in serie and q not in norme.MCB_IN_A and q not in norme.GG_IN_A:
                sus = next((x for x in serie if x >= q), None)
                if sus:
                    c.intrebari.append(("I07", f"Q1 {fmt(q)} A nu e calibru standard → {sus} A. Confirmați {sus} A?"))
                    c.nota(f"„{c.o(I['s_aprox'] or I['s'], I['e']).strip()}” → Q1 {sus} A (calibrul standard imediat "
                           "superior)")
                    q = sus
            puteri["In_Q1_A"] = _nr(q)
            intr["In_Q1_A"] = _nr(q)
        if _prima(vals, "kWh"):
            c.probleme.append(("I04", "Unitatea „kWh” (energie) nu are sens la un tablou (I04).",
                               "Puterea tabloului este în kW (sau calibrul în A)?"))
        origine_tablou(c, intr, ex)
        imp = cablu_impus(c) if not getattr(c, "_cablu_impus", None) else c._cablu_impus
        if imp:
            ex["_cablu_impus"] = imp
    # plecările
    plecari, n_cerut = [], None
    if c.lista:
        _unitate_comuna(c, c.lista["itemi"])
        _conversii_unitati(c, c.lista["itemi"])
        cf = c.lista["cuvant"] == "circuite" or bool(re.search(r"(?<![\d×x] )(?<![\d×x])\bTD\b(?!-)(?!\s+\d)", c.orig))
        ex["_circuite_finale"] = cf
        plecari = _scoate_fara_valoare(c, expandeaza(c, c.lista["itemi"], 0, tip, cf))
        n_cerut = c.lista["nr_cerut"]
        # atributele de cablu scrise doar după ULTIMUL item („…, td-2 160 A 0,15 km Al XLPE în tub”) = pentru toate
        cu_cab = [p for p in plecari if p.get("cablu")]
        if len(plecari) > 1 and len(cu_cab) == 1 and cu_cab[0] is plecari[-1]:
            for k, v in plecari[-1]["cablu"].items():
                ex[{"material": "material", "izolatie": "izolatie", "metoda": "metoda"}[k]] = v
            c.nota("cablul descris după ultima plecare („" + ", ".join(plecari[-1]["cablu"].values())
                   + "”) se aplică tuturor plecărilor")
    if not plecari and tip == "tablou":
        plecari = _circuite_implicite_tablou(c, ex)            # r7 (#64): „mansardă: 4 prize, 2 iluminat, AC”
        if plecari:
            ex["_circuite_finale"] = True
    serie_in = set(norme.MCCB_IN_A) | set(norme.MCB_IN_A) | set(norme.GG_IN_A)
    for p in _toate(plecari):                    # r5 (#45): calibru nestandard pe plecare → treapta superioară + întrebare
        if p["unitate"] == "A" and p["valoare"] and p["valoare"] not in serie_in:
            sus = next((x for x in sorted(serie_in) if x >= p["valoare"]), None)
            if sus:
                c.intrebari.append(("I07", f"{p['nume']}: {fmt(p['valoare'])} A nu e calibru standard → {sus} A. "
                                           f"Confirmați {sus} A?"))
                p["valoare"] = sus
    if tip == "pt" and intr.get("n_trafo") == 2:
        msec = re.search(r"\b(?:fiecare|pe\s+fiecare|cate)\s+(?:semibar\w*|sectie\w*|sectiune\w*|bar[ae]\w*)", c.t)
        if msec and plecari:                           # r7 (#24): „fiecare semibară cu 4 plecări de 250 A” → 2 × 4
            c.foloseste(msec.start(), msec.end())
            dubla = []
            for k in (1, 2):
                for p in plecari:
                    q = copy.deepcopy(p)
                    q["sectie"] = k
                    q["nume"] = f"{p['nume']} S{k}" if not re.match(r"TD-\d", p["nume"]) else p["nume"]
                    dubla.append(q)
            for i, q in enumerate(dubla):
                if re.fullmatch(r"TD-\d+", q["nume"]):
                    q["nume"] = f"TD-{i + 1}"
            plecari = dubla
            intr["plecari_pe_sectie"] = ex["plecari_pe_sectie"] = True
            if c.lista and c.lista.get("nr_cerut"):
                c.lista["nr_cerut"] = None
            c.nota(f"„{c.o(msec.start(), msec.end()).strip()}” = plecările se repetă pe fiecare semibară (2 trafo → "
                   f"{len(plecari)} plecări, secțiile 1 și 2)")
        mcup = re.search(r"\bcupl\w*(?:\s+(?:longitudinal\w*|de\s+bare|pe\s+jt|jt|de\s+jt))*(?:\s+(?:normal\s+)?(?P<st>inchis\w*|deschis\w*|ni\b|nd\b|no\b|nc\b))?", c.t)
        if mcup:
            c.foloseste(mcup.start(), mcup.end())
            st = mcup.group("st")
            if st:
                intr["cupla"] = ex["cupla"] = "inchisa" if st.startswith(("inchis", "ni", "nc")) else "deschisa"
            elif intr.get("cupla"):
                pass                                        # r10: stabilită de _topologie_pt (paralel / longitudinală / ATS)
            else:
                c.intrebari.append(("I02", "Cupla longitudinală JT e normal DESCHISĂ (fiecare trafo pe semibara lui, interblocaj "
                                           "2 din 3) sau normal ÎNCHISĂ (trafo-urile în paralel)?"))
    n_gasit = sum(p.get("n_circuite") or 1 for p in plecari)
    ex["plecari"] = plecari
    ex["nr_plecari"] = n_cerut if n_cerut is not None else (n_gasit or None)
    if n_cerut is not None and plecari and n_cerut not in (len(plecari), n_gasit):
        lipsa = n_cerut - len(plecari)
        ordinal = {2: "a doua", 3: "a treia", 4: "a patra", 5: "a cincea", 6: "a șasea", 7: "a șaptea",
                   8: "a opta", 9: "a noua", 10: "a zecea"}
        intreb = (f"Care este {ordinal[n_cerut]} plecare?" if lipsa == 1 and n_cerut in ordinal
                  else f"Care sunt celelalte {lipsa} plecări?" if lipsa > 0
                  else f"Câte plecări are tabloul: {n_cerut} sau {len(plecari)}?")
        c.probleme.append(("I05", f"S-au cerut {n_cerut} plecări, dar s-au găsit {len(plecari)} (I05).", intreb))
    # coduri scrise de utilizator păstrate (F.4 r. 4)
    coduri = [p["nume"] for p in _toate(plecari) if re.fullmatch(r"[A-Z][A-Z0-9\-]*", p["nume"] or "")
              and p["nume"] in c.orig]
    if coduri:
        c.nota("„" + "”, „".join(coduri) + "” păstrat" + ("e" if len(coduri) > 1 else "") + " cu majuscule")
    # lungimea generală: tablou → alimentarea; PT → toate plecările (F.5 „lungime”)
    L = _lungime_generala(vals)
    if L:
        snip = c.o(L["s_aprox"] or L["s"], L["e"]).strip()
        if tip == "pt":
            ex["lungimi_m"] = {"plecari": _nr(L["val"])}
            for p in plecari:
                p.setdefault("L_m", _nr(L["val"]))
            c.nota(f"la PT, o lungime generală se aplică tuturor plecărilor („{snip}” = {fmt(L['val'])} m)")
        else:
            ex["lungimi_m"] = {"alimentare": _nr(L["val"])}
            intr["L_alimentare_m"] = _nr(L["val"])
            fara_L = any("L_m" not in p for p in plecari)
            c.nota(f"lungimea „{snip}” = {fmt(L['val'])} m se aplică DOAR alimentării {_nume_tablou(c)}"
                   + ("; plecări L = 50 m" if fara_L else ""))
    # cablul și gruparea
    cablu = {k: v for k, v in (("material", ex["material"]), ("izolatie", ex["izolatie"]),
                               ("metoda", ex["metoda"])) if v}
    imp = ex.pop("_cablu_impus", None)
    if (cablu or imp) and tip != "pt":
        intr["cablu"] = dict(cablu, **(imp or {}))
        if intr["cablu"].get("S_fortat") and intr["cablu"]["S_fortat"] < 16 and not intr["cablu"].get("material"):
            intr["cablu"]["material"] = "Cu"          # r9 (locuințe #36): sub 16 mm² doar Cu (Al nepermis)
            c.nota(f"cablul {fmt(intr['cablu']['S_fortat'])} mm² fără material = Cu (Al sub 16 mm² nu se folosește)")
        if imp and imp.get("material"):
            ex["material"] = imp["material"]
    n = len(plecari)
    grup = bool(RE_GRUPARE.search(c.t)) or (ex["metoda"] == "E" and n > 1 and re.search(r"pat\s+de\s+cabluri", c.t))
    if grup and n > 1:
        met = ex["metoda"] or "D1"
        ex["grupare"] = {"plecari": n, "aranjament": "pat_perforat" if met == "E" else
                         "perete" if met == "C" else f"{met} atingere"}
    intr["plecari"] = [_plecare_intrare(p, cablu, n if ex.get("grupare") else 0) for p in plecari]
    if not intr["plecari"]:
        del intr["plecari"]
    if ex.get("_circuite_finale") and plecari:
        intr["circuite_finale"] = True
    if tip == "tablou" and intr.get("plecari") and (ex.get("_circuite_finale") or intr.get("circuite_finale")):
        # r8 (industrial #38): circuitele finale de iluminat / prize mici dintr-un tablou trifazat sunt monofazate (L+N,
        # repartizate pe faze) — nu 4P
        mono = []
        for p in intr["plecari"]:
            if p.get("retea") or p.get("copii") or re.search(r"\bcee\b|3p|trifaz|400|industrial", _fara_diacritice(p["nume"])):
                continue
            rec = receptor_dupa_nume(p["nume"], 1, True)
            if rec in ("iluminat", "prize") and ((p.get("P_kW") or 99) <= 3.7 or (p.get("In_A") or 99) <= 16):
                p["retea"] = "mono"
                mono.append(p["nume"])
        if mono:
            c.nota("circuite finale de iluminat / prize ≤ 3,7 kW într-un tablou trifazat → monofazate (L+N, repartizate pe "
                   "faze): " + ", ".join(mono))
    if tip == "tablou":
        m2i = re.search(r"\b(?:doua|2)\s+intrari\b|\bdubla\s+alimentare\b|\bdin\s+pt\s*1\s+si\s+(?:din\s+)?pt\s*2\b"
                        r"|\bintrar\w*\s+din\s+pt\s*1\b", c.t)
        if m2i:                                       # r8 (industrial #49): TG cu 2 intrări (PT1 / PT2) + cuplă
            c.foloseste(m2i.start(), m2i.end())
            mk = re.search(rf"\bfiecare\s+(?:de\s+)?({NUM})\s*kva\b", c.t)
            if mk and not intr.get("origine"):
                intr["origine"] = ex["sursa_alimentare"] = "pt_propriu"
                intr["pt_Sn_kVA"] = _nr(numar(mk.group(1)))
                c.nota(f"sursa: PT1 / PT2 de câte {mk.group(1)} kVA → desenat din PT propriu {mk.group(1)} kVA (o intrare)")

            for mm in re.finditer(r"\bpt\s*[12]\b|\bfiecare\s+\d+\s*kva|\bcupl\w*(?:\s+cu\s+interblocaj(?:\s+\d\s+din\s+\d)?)?", c.t):
                c.foloseste(mm.start(), mm.end())
            c.intrebari.append(("I14", f"„{c.o(m2i.start(), m2i.end()).strip()}”: tabloul cu două intrări (PT1 / PT2) și "
                                       "cuplă (interblocaj) se desenează azi cu O SINGURĂ intrare. Desenez varianta cu o "
                                       "intrare (cupla și a doua intrare se completează manual), sau separat pe secții?"))
        _contradictii_tablou(c, intr)

        _retea_tablou(c, intr, ex, plecari)
        ms = RE_CTX_SIGURANTA.search(c.t)
        if ms:                                        # r7 (P0 #31): titlul tabloului face consumatorii de siguranță
            intr["siguranta_tablou"] = True
            intr["titlu_tablou"] = nume_normalizat(c.o(ms.start(), ms.end()))
            c.foloseste(ms.start(), ms.end())
            c.nota(f"„{c.o(ms.start(), ms.end()).strip()}” = tablou de siguranță (P118/3, I7): fără DDR, cabluri rezistente la "
                   "foc, protecția termică a pompelor doar la semnalizare")
        _siguranta_mixta(c, intr)
        mt = re.match(rf"\s*(?:te|td|ts|tablou\w*(?:\s+de)?)\s+(?P<n>[a-z][a-z ]{{2,40}}?)\s+(?P<v>{NUM})\s*kw\b", c.t)
        if not intr.get("plecari") and intr.get("P_kW") and mt and (RE_RECEPTOR_ITEM.search(mt.group("n"))
                                                                    or e_siguranta(mt.group("n"))):
            # r9 (industrial #63): „TE lift pompieri 18 kW din TG” = tabloul unui singur receptor → plecarea lui
            nume = nume_normalizat(c.o(mt.start("n"), mt.end("n")))
            d = {"nume": nume, "P_kW": intr["P_kW"]}
            if intr.get("siguranta_tablou") or e_siguranta(nume):
                d["siguranta"] = True
            if re.search(r"pomp|ventil|compresor", mt.group("n")):     # liftul are tabloul lui de comandă
                d["pornire"] = "directa"
            intr["plecari"] = [d]
            c.foloseste(mt.start(), mt.end())
            c.nota(f"„{c.o(mt.start(), mt.end()).strip()}” = tabloul unui singur receptor: plecarea {nume} {fmt(intr['P_kW'])} kW")
    return puteri


def _siguranta_mixta(c: Ctx, intr: dict):
    """r9 (industrial #25, #26): tablou MIXT — doar consumatorii de siguranță la incendiu se marchează; ceilalți (rampe,
    iluminat normal, CTA — care se OPRESC la alarmă) primesc explicit `siguranta: false`, ca motorul să nu treacă tot
    tabloul pe regimul de siguranță (regula „≥ 50 % din putere”)."""
    if intr.get("siguranta_tablou"):
        return
    toate = []

    def w(L):
        for p in L or []:
            toate.append(p)
            w(p.get("copii"))
    w(intr.get("plecari"))
    if not any(p.get("siguranta") for p in toate):
        return
    normali = [p for p in toate if not p.get("copii") and p.get("siguranta") is None and not p.get("_compensare")
               and not re.search(r"pilot|jockey|mentinere", _fara_diacritice(p.get("nume", "")).lower())]
    for p in normali:
        p["siguranta"] = False
    if normali:
        c.nota("tablou mixt: consumatori de siguranță la incendiu (" + ", ".join(p["nume"] for p in toate if p.get("siguranta"))
               + ") + consumatori normali (" + ", ".join(p["nume"] for p in normali) + ") — doar primii fără DDR / cu cablu "
               "rezistent la foc; ceilalți rămân normali (se deconectează la incendiu)")


def _p_plecari(pl) -> float:
    """Σ puterilor plecărilor de nivel 1 (kW; calibrul A → P la 400 V, cosφ 0,9), fără rezervele."""
    tot = 0.0
    for p in pl or []:
        if p.get("rezerva"):
            continue
        n = int(p.get("n_circuite") or 1)
        if p.get("P_kW"):
            tot += n * float(p["P_kW"])
        elif p.get("In_A") and not p.get("copii"):
            tot += n * float(p["In_A"]) * U_TRI * 0.9 / 1000 * (1 / 3 if p.get("retea") == "mono" else 1)
        elif p.get("copii"):
            tot += _p_plecari(p["copii"])
    return tot


P_SURSA_INTREBATA_KW = 100      # r9: peste (≥) atât, sursa nedeclarată a unui tablou se întreabă; sub — „Am presupus”


def _contradictii_tablou(c: Ctx, intr: dict):
    """r8 (industrial #7, #24, #55): contradicții numerice la tablou — Q1 sub curentul puterii declarate, Σ plecări peste
    trafo-ul PT-ului sursă, tablou mare fără sursă declarată (nu se presupune BMPT peste 250 A) → întrebare."""
    P = intr.get("P_kW") or _p_plecari(intr.get("plecari"))
    if not P:
        return
    ib = P * 1000 / (U_TRI * 0.9)
    q = intr.get("In_Q1_A")
    if q and ib > 1.05 * q and intr.get("P_kW"):
        c.intrebari.append(("I08", f"Întrerupătorul general {fmt(q)} A e sub curentul puterii declarate ({fmt(P)} kW ≈ "
                                   f"{fmt(ib, 0)} A): Q1 se mărește (≥ {fmt(ib, 0)} A), sau puterea cerută e mai mică (ks)?"))
    elif q and not intr.get("P_kW") and intr.get("plecari") and intr.get("retea") != "mono" \
            and all(p.get("P_kW") for p in intr["plecari"]):          # calibrele plecărilor (A) nu sunt Ib
        # r9 (industrial #37): „întrerupător general 40 A, plecări: 3 motoare 11 kW” — Q1 impus sub Ib din bilanț
        pl1 = [p for p in intr["plecari"] if not p.get("rezerva")]
        ks = 1.0 if sum(int(p.get("n_circuite") or 1) for p in pl1) <= 3 else 0.8
        ib_pl = _p_plecari(intr["plecari"]) * ks * 1000 / (U_TRI * 0.85)
        if ib_pl > 1.1 * q:
            # r10 (clasa 8): nu refuz — se generează și se întreabă, cu opțiunile de remediere
            src = "branșamentul (BMPT)" if intr.get("origine") == "bmpt" else "Q1"
            c.intrebari.append(("I08", f"Întrerupătorul general impus {fmt(q)} A < Ib ≈ {fmt(ib_pl, 0)} A din plecări "
                                       f"(Σ {fmt(_p_plecari(intr['plecari']))} kW, ks {fmt(ks)}): se mărește {src} (≥ "
                                       f"{fmt(ib_pl, 0)} A{', ATR nou' if src.startswith('branș') else ''}), sau plecările nu "
                                       "funcționează simultan (ce ks)?"))
    sn = intr.get("pt_Sn_kVA")
    p_pl = _p_plecari(intr.get("plecari"))
    if sn and p_pl > sn * 1.0:
        c.intrebari.append(("I08", f"Plecările însumează {fmt(p_pl)} kW, iar PT-ul sursă are {fmt(sn)} kVA: ce coeficient de "
                                   "simultaneitate are tabloul (ks), sau trafo-ul e mai mare?"))
    if not intr.get("origine") and ib > norme.BMPT_I_MAX_A and not intr.get("P_kW") and not q:
        c.intrebari.append(("I07", f"Sursa tabloului nu e scrisă, iar {fmt(P)} kW (≈ {fmt(ib, 0)} A) depășesc un BMPT "
                                   f"(max. {fmt(norme.BMPT_I_MAX_A, 0)} A): tabloul se alimentează din PT propriu (ce kVA?) "
                                   "sau dintr-un TG existent?"))
    elif not intr.get("origine") and c._tip == "tablou" and not q and len(intr.get("plecari") or []) == 1 \
            and not re.search(r"\bdin\b|\balimentat\w*|\bsursa\b", c.t):
        # r10 (industrial #25): „cuptor electric 72 kW la 400V” — plecarea unui receptor, sursa nescrisă → întrebare
        c.intrebari.append(("I07", f"De unde se alimentează {intr['plecari'][0].get('nume', 'receptorul')} ({fmt(P)} kW): "
                                   "dintr-un TG existent (desenez doar plecarea), dintr-un BMPT sau dintr-un PT propriu?"))
    elif not intr.get("origine") and P >= P_SURSA_INTREBATA_KW and c._tip == "tablou" and not intr.get("P_kW") and not q:
        # r9 (industrial #8): sursă nedeclarată la o putere mare → întrebare scurtă (BMPT doar presupus, nu tăcut)
        c.intrebari.append(("I07", f"Din ce sursă se alimentează tabloul ({fmt(P)} kW): BMPT (branșament), PT propriu (ce kVA?) "
                                   "sau un TG existent? Până la răspuns e desenat din BMPT (presupus)."))


RE_TABLOU_CASNIC = re.compile(
r"\bmansard\w*|\bgaraj\w*|\banex\w*|\betaj\w*|\bbeci\w*|\bpod\b|\bcas(?:a|ei)\b|\bapartament\w*"
                              r"|\blocuint\w*|\bfoisor\w*|\bsopron\w*")
CALIBRU_IMPLICIT_CASNIC = {"prize": 16, "prize_bucatarie": 16, "prize_baie": 16, "prize_exterior": 16, "iluminat": 10,
                           "aer_conditionat": 16}


def _circuite_implicite_tablou(c: Ctx, ex: dict) -> list:
    """r7 (locuințe #64): tabloul secundar al unei case („mansardă nouă: 4 prize, 2 iluminat, AC, din TG existent”) —
    circuitele casnice listate fără putere primesc calibrul uzual (prize 16 A, iluminat 10 A, AC 16 A) — PRESUPUS,
    declarat; rețeaua NU se deduce din aceste valori."""
    if not RE_TABLOU_CASNIC.search(c.t):
        return []
    out = []
    for g in _gaseste_receptori(c.mascat()):
        if g["exclus"]:
            continue
        nume = g["nume"] or nume_normalizat(c.o(g["s"], g["e"]))
        if g["P"] is not None:
            p = {"nume": nume, "valoare": _nr(g["P"]), "unitate": "kW", "receptor": "forta"}
        elif g["receptor"] in CALIBRU_IMPLICIT_CASNIC:
            p = {"nume": nume, "valoare": CALIBRU_IMPLICIT_CASNIC[g["receptor"]], "unitate": "A",
                 "receptor": "prize" if g["receptor"].startswith("prize") else "iluminat" if g["receptor"] == "iluminat"
                 else "forta", "retea": "mono", "_implicit": True}
        else:
            c.fara_valoare.append(c.o(g["s_tot"], g["coada_e"]).strip())
            c.consumat.append((g["s_tot"], g["coada_e"]))
            continue
        if g["n"] > 1:
            p["n_circuite"] = g["n"]
        c.consumat.append((g["s_tot"], g["coada_e"]))
        out.append(p)
    if out:
        ex["_valori_implicite"] = True
        impl = [p for p in out if p.get("_implicit")]
        if impl:
            c.nota("circuite casnice fără putere → calibrul uzual (PRESUPUS): " + ", ".join(
                f"{p['nume']} {p['valoare']} A" + (f" × {p['n_circuite']}" if p.get("n_circuite") else "") for p in impl)
                   + " — corectați dacă diferă")
        for p in out:
            p.pop("_implicit", None)
    return out


def _scoate_fara_valoare(c: Ctx, plecari: list) -> list:
    """r6 (industrial #7, #22): plecările / circuitele fără putere și fără calibru NU se desenează în tăcere și nici nu
    dispar: se scot din intrare și se întreabă. Un TD cu calibru și cu sub-circuite fără valori rămâne o plecare simplă
    (sub-circuitele se întreabă)."""
    out = []
    for p in plecari:
        if p.get("fara_valoare") and p.get("copii") is None and (re.match(r"priz", _fara_diacritice(p["nume"] or "").lower())
                                                                  or p.get("_simplu") or (
                re.match(r"ilumin", _fara_diacritice(p["nume"] or "").lower()) and not re.search(r"\d", re.sub(
                    r"^\d+\s+(?:circuite\s+(?:de\s+)?)?" + (r"|\s+\d+\s+circuite$" if re.search(
                        r"\btablou\w*\s+secundar|\bmansard|\betaj|\bcas(?:a|ei)\b|\bapartament", c.t) else ""), "",
                    p.get("txt") or "")))):
            # r11 (industrial #20): „3 circuite iluminat” (numărul = circuite, nu putere) → 10 A presupus, ca la prize
            # r10 (locuințe #39): „3 ilum” în TD-ul casei = 3 circuite de iluminat (10 A presupus)
            # r8 (industrial #15, #53, #68): circuitele de prize fără calibru → 16 A presupus (desenate) + întrebare
            # r9 (locuințe #36): iluminatul fără calibru → 10 A presupus
            p.pop("fara_valoare")
            il = bool(re.match(r"ilumin", _fara_diacritice(p["nume"] or "").lower()))
            p["valoare"], p["unitate"], p["receptor"] = (10, "A", "iluminat") if il else (16, "A", "prize")
            c._prize_presupuse = getattr(c, "_prize_presupuse", []) + [p["txt"]]
            out.append(p)
            continue
        if p.get("fara_valoare"):
            c.fara_valoare.append(p["txt"])
            continue
        if p.get("copii"):
            for k in p["copii"]:                      # r8: prizele fără calibru din sub-plecări → 16 A presupus
                if k.get("fara_valoare") and k.get("copii") is None and re.match(r"priz", _fara_diacritice(k["nume"] or "")):
                    k.pop("fara_valoare")
                    k["valoare"], k["unitate"], k["receptor"] = 16, "A", "prize"
                    c._prize_presupuse = getattr(c, "_prize_presupuse", []) + [k["txt"]]
            fv = [k for k in p["copii"] if k.get("fara_valoare")]
            if fv:
                c.fara_valoare += [k["txt"] for k in fv]
                if p["valoare"] is not None:
                    rest = [k for k in p["copii"] if not k.get("fara_valoare")]
                    if rest:                     # r8 (#15): sub-circuitele cu valori se păstrează; restul se întreabă
                        p["copii"] = rest
                        c.nota(f"{p['nume']}: sub-circuitele cu valori ({_plecari_text(rest)}) desenate; celelalte "
                               "se adaugă după completarea calibrului / puterii")
                        out.append(p)
                        continue
                    p.pop("copii")
                    p["receptor"] = "tablou" if re.match(r"t[dge]\b|tablou", _fara_diacritice(p["nume"])) else p["receptor"]
                else:
                    p["copii"] = [k for k in p["copii"] if not k.get("fara_valoare")]
                    if not p["copii"]:
                        c.fara_valoare.append(p["nume"])
                        continue
        out.append(p)
    return out


def _i_mono_echiv(intr, plecari) -> float:
    """Curentul echivalent dacă totul ar fi monofazat (230 V): Σ plecări (A sau kW) sau Q1 / P tablou."""
    tot = 0.0
    for p in plecari:
        n = p.get("n_circuite") or 1
        if p.get("copii"):
            tot += _i_mono_echiv({}, p["copii"]) if p["valoare"] is None else 0
        if p["valoare"] is None:
            continue
        tot += n * (p["valoare"] if p["unitate"] == "A" else p["valoare"] * 1000 / (U_MONO * COSFI))
    alt = max(intr.get("In_Q1_A") or 0, (intr.get("P_kW") or 0) * 1000 / (U_MONO * COSFI))
    return max(tot, alt)


def _retea_tablou(c: Ctx, intr, ex, plecari):
    """r5 (P0-2 industrial): rețeaua tabloului se scrie în intrare; nedeclarată → trifazat DOAR dacă sarcina nu
    încape fizic în monofazat (> 40 A), altfel întrebare. „monofazat” + „3×63 A” / plecări > 63 A → I08."""
    # r6 (industrial #2, #18–#20, #44): rețeaua tabloului se citește în AFARA listei — „iluminat 2 kW monofazat” sau
    # „plecări monofazate” țin de plecare (`plecari[].retea`), nu fac tabloul monofazat; mono + tri în afara listei,
    # sau tablou monofazat cu o plecare trifazată (3P, „trifazat”, 400 V) → I08
    t_afara = c.t
    if c.lista:
        t_afara = c.t[:c.lista["s"]] + " " * (c.lista["e"] - c.lista["s"]) + c.t[c.lista["e"]:]
    if getattr(c, "_retea_nestiuta", False) or RE_RETEA_NESTIUTA.search(t_afara):
        retea_declarata(c, t_afara)
        ex["retea"] = None
        c.intrebari.append(("I02", "Tabloul este monofazat (230 V) sau trifazat (3 × 400/230 V)? Rețeaua nu se presupune."))
        return
    if intr.get("origine") == "bmpt" and RE_MONO_DECLARAT.search(t_afara):
        t_afara = _masca(t_afara, re.compile(r"\bbmpt\w*"))  # r7 (#12): „din BMPT 6 kW mono” — BMPT = sursa, nu rețeaua
    mrep = re.search(r"\b(?:monofaz\w*|mono)\s*,?\s*(?:repartizat\w*|distribuit\w*|impartit\w*|echilibrat\w*)\s+pe\s+"
                     r"(?:cele\s+)?(?:3\s+|trei\s+)?faze\b", c.t)
    if mrep:                     # r9 (industrial #44): „circuite monofazate, repartizate pe faze” = tablou TRIFAZAT
        c.foloseste(mrep.start(), mrep.end())
        for p in _toate(plecari):
            if not p.get("copii") and p.get("retea") in (None, "mono"):
                p["retea"] = "mono"
        intr["retea"] = ex["retea"] = "tri"
        c.nota(f"„{c.o(mrep.start(), mrep.end()).strip()}” = circuite monofazate (L + N) repartizate pe L1 / L2 / L3 → "
               "tablou trifazat 3 × 400/230 V")
        return
    ret = retele_declarate(t_afara)
    pl_tri = [p for p in _toate(plecari) if p.get("retea") == "tri"]
    pl_mono = [p for p in _toate(plecari) if p.get("retea") == "mono"]
    for m in re.finditer(r"monofaz\w*|\bmono\b|\b230\s*v\b|trifaz\w*|\btri\b|\btrif\b|\b3\s*×\s*400\s*v?\b|\b400\s*v\b"
                         r"|\b[34]\s*p\b|\b[13]f\b", t_afara):
        c.foloseste(m.start(), m.end())
    if len(ret) > 1:
        if re.search(r"\bbmpm", t_afara):                     # r9 (industrial #70): „TG trifazat din BMPM 40A”
            c.probleme.append(("I08", "Contradicție: tablou trifazat alimentat dintr-un BMPM (branșament MONOFAZAT) (I08).",
                               "BMPM e monofazat (230 V, max. 40 A): tabloul e monofazat (din BMPM), sau trifazat — "
                               "atunci alimentat dintr-un BMPT (3 × 400 V)?"))
            return
        c.probleme.append(("I08", "Contradicție: tabloul e descris și monofazat, și trifazat (I08).",
                           "Tabloul este monofazat (230 V, aparate 2P) sau trifazat (3 × 400/230 V)?"))
        return
    r = next(iter(ret)) if ret else None
    if r:
        intr["retea"] = ex["retea"] = r
        if r == "mono":
            m = re.search(rf"\b3\s*×\s*({NUM})\s*a\b", t_afara)
            if m:
                c.probleme.append(("I08", f"Contradicție: „monofazat” și „{c.o(m.start(), m.end())}” (I08).",
                                   f"Tablou monofazat sau trifazat cu {m.group(1)} A pe fază?"))
            elif pl_tri:
                c.probleme.append(("I08", f"Contradicție: tablou monofazat și plecarea trifazată „{pl_tri[0]['nume']}” (I08).",
                                   f"Tabloul este trifazat (3 × 400/230 V), sau {pl_tri[0]['nume']} e monofazată?"))
        elif pl_mono:
            c.nota("plecări monofazate într-un tablou trifazat: " + ", ".join(p["nume"] for p in pl_mono)
                   + " (L + N, repartizate pe faze)")
        return
    if pl_tri and not pl_mono:
        intr["retea"] = ex["retea"] = "tri"
        c.nota(f"rețea nedeclarată, dar plecarea „{pl_tri[0]['nume']}” e trifazată → tablou trifazat 3 × 400/230 V")
        return
    if intr.get("origine") == "pt_propriu":
        # r8 (industrial #5): un tablou alimentat din bara JT a unui PT e trifazat (3 × 400/230 V) — nu se întreabă
        intr["retea"] = ex["retea"] = "tri"
        c.nota("rețea nedeclarată, dar tabloul e alimentat din PT → trifazat 3 × 400/230 V")
        return
    i = _i_mono_echiv(intr, [] if ex.get("_valori_implicite") else plecari)
    if i > norme.BMPM["I_max_A"]:
        intr["retea"] = ex["retea"] = "tri"
        c.nota(f"rețea nedeclarată, dar sarcina tabloului (≈ {fmt(i, 0)} A la 230 V) nu încape în monofazat → "
               "trifazat 3 × 400/230 V")
    elif i > 0 or ex.get("_valori_implicite"):
        ex["retea"] = None
        c.intrebari.append(("I02", "Tabloul este monofazat (230 V) sau trifazat (3 × 400/230 V)? Rețeaua nu se "
                                   "presupune" + (" (un cablu „3x…” = L+N+PE sau 3 faze — nu decide rețeaua)."
                                                  if getattr(c, "_cablu_impus", None) else ".")))


def _toate(plecari):
    for p in plecari:
        yield p
        yield from _toate(p.get("copii") or [])


def _nume_tablou(c: Ctx) -> str:
    if re.search(r"\bTG\b", c.orig) or "tablou general" in c.t:
        return "TG"
    if re.search(r"\bTD\b(?!-)", c.orig):
        return "TD"
    return "tabloului"


def _plecare_intrare(p: dict, cablu: dict, n_grup: int) -> dict:
    """Plecare în forma `intrare` din cazuri_golden.json: {nume, In_A | P_kW, L_m, receptor, copii, cablu}."""
    d = {"nume": p["nume"]}
    if p["valoare"] is not None:
        d["In_A" if p["unitate"] == "A" else "P_kW"] = p["valoare"]
    if "L_m" in p:
        d["L_m"] = p["L_m"]
    if p.get("copii") is not None:
        d["copii"] = [_plecare_intrare(k, {}, 0) for k in p["copii"]]
    elif p["receptor"] in ("iluminat", "prize", "motor") and not re.search(
            {"iluminat": "ilumin", "prize": "priz", "motor": "motor|pomp|compresor|ventila|moar|concasor|malaxor"}
            [p["receptor"]], _fara_diacritice(p["nume"])):
        d["receptor"] = p["receptor"]
    for k in ("cosfi", "pornire", "n_circuite", "retea", "curba", "sectie", "rezerva", "randament", "siguranta", "prot_tip"):
        if p.get(k) is not None:
            d[k] = p[k]
    if "siguranta" not in d and e_siguranta(p["nume"]):
        d["siguranta"] = True                     # r8 (P0 #64): „pompă incendiu” într-un TG oarecare = consumator de siguranță
    cb = dict(cablu)
    cb.update(p.get("cablu") or {})                                   # r5 #44: pozarea / materialul per plecare
    if n_grup > 1:
        cb["n_alte"] = n_grup - 1
    if cb:
        d["cablu"] = cb
    return d


# =====================================================================================================
# r5: echipamente PV — mărci, modele, grupuri de invertoare, module, stringuri, BESS, limitarea injecției
# =====================================================================================================
MARCI = {  # text normalizat → (producător, fel implicit)
    "huawei": ("Huawei", "inv"), "sungrow": ("Sungrow", "inv"), "sma": ("SMA", "inv"), "fronius": ("Fronius", "inv"),
    "growatt": ("Growatt", "inv"), "solis": ("Solis", "inv"), "ginlong": ("Solis", "inv"), "goodwe": ("GoodWe", "inv"),
    "solaredge": ("SolarEdge", "inv"), "kostal": ("Kostal", "inv"), "deye": ("Deye", "inv"), "sofar": ("Sofar", "inv"),
    "abb": ("ABB", "inv"), "fimer": ("FIMER", "inv"), "kaco": ("KACO", "inv"), "victron": ("Victron", "inv"),
    "foxess": ("FoxESS", "inv"), "sigenergy": ("Sigenergy", "inv"), "zucchetti": ("Zucchetti", "inv"),
    "longi": ("LONGi", "mod"), "ja solar": ("JA Solar", "mod"), "ja": ("JA Solar", "mod"),
    "trina solar": ("Trina Solar", "mod"), "trina": ("Trina Solar", "mod"), "jinko solar": ("Jinko Solar", "mod"),
    "jinko": ("Jinko Solar", "mod"), "canadian solar": ("Canadian Solar", "mod"), "risen": ("Risen", "mod"),
    "astronergy": ("Astronergy", "mod"), "aiko": ("Aiko", "mod"), "qcells": ("Qcells", "mod"), "q cells": ("Qcells", "mod"),
    "tongwei": ("Tongwei", "mod"), "dah solar": ("DAH Solar", "mod"), "sunpower": ("SunPower", "mod"),
    "byd": ("BYD", "bess"), "pylontech": ("Pylontech", "bess"), "tesla": ("Tesla", "bess"),
}
RE_MARCA = re.compile(r"\b(" + "|".join(sorted((re.escape(k) for k in MARCI), key=len, reverse=True)) + r")\b")
RE_COD_MODEL = re.compile(
    r"\b(?:sun2000-[\w.-]+|luna2000(?:-[\w.-]+)?|sg\d+[a-z]{1,3}\d?[\w-]*|sh\d+(?:\.\d+)?(?:t|rt|rs)\b"
    r"|stp\s*\d+(?:[.,]\d+)?(?![\d.,]|\s*kw)(?:-\w+)*|max\s*\d+\s*ktl\d?(?:-\w+)?|mid\s*\d+\s*ktl\d?(?:-\w+)?"
    r"|s[56]-[a-z]{2}\d+k(?:-\w+)?|battery[\s-]*box(?:\s+premium)?(?:\s+hv[sm](?:\s*\d+(?:[.,]\d+)?)?)?|powerstack(?:\s*\d+\w*)?"
    r"|hi-mo\s*\d|tiger\s+neo|vertex(?:\s+[sn]\+?)?|sunny\s+tripower(?:\s+core\s*\d|\s+x)?|tauro(?:\s+eco)?|symo(?:\s+gen24)?"
    # r8: SMA Sunny Boy (monofazat) / Sunny Boy Storage / Sunny Island (PCS)
    r"|sunny\s+boy\s+storage\s*\d+(?:[.,]\d+)?|sunny\s+boy\s*\d+(?:[.,]\d+)?|sunny\s+island\s*\d+(?:[.,]\d+)?)")
PREFIX_PRODUCATOR = [(r"sun2000|luna2000", "Huawei"), (r"sg\d|sh\d|powerstack", "Sungrow"), (r"stp|sunny", "SMA"),
                     (r"tauro|symo|primo", "Fronius"), (r"battery|hv[sm]", "BYD"), (r"hi-mo", "LONGi"),
                     (r"vertex", "Trina Solar"), (r"tiger", "Jinko Solar"), (r"max\s*\d|mid\s*\d", "Growatt"),
                     (r"s[56]-", "Solis")]
_STOP_MODEL = {"de", "a", "cu", "si", "la", "pe", "in", "x", "×", "racord", "module", "modul", "panouri", "panou",
               "invertor", "invertoare", "inv", "bess", "baterie", "stocare", "trifazat", "trifazic", "monofazat", "mono",
               "tri", "hibrid", "total", "pt", "tg", "cablu", "string", "stringuri", "acoperis", "sol", "diferite",
               "=", "langa", "pentru", "fiecare", "kwp", "agricola", "existent", "existenta",
               # r7: „PowerStack 255CS cuplat …”, „SUN2000-100KTL-M2 dar puterea totală …”
               "cuplat", "cuplata", "cuplate", "dar", "iar", "puterea", "putere", "totala", "centrala", "centralei",
               "pv", "ac", "dc", "schema", "retea", "smart", "contor", "meter", "separat", "separata", "pentru",
               # r10: „Symo 20.0-3-M existente”, „… nou”, „deja” nu fac parte din model
               "existente", "existenti", "existentă", "nou", "noua", "noi", "deja", "adaug", "adaugam", "adaugat"}
RE_VAL_UNIT_START = re.compile(rf"^{NUM}\s*(?:kwp|mwp|wp|kwh|mwh|kva|mva|kw|mw|w|ka|a|km|m|metri)\b")


def _fel_model(model: str, implicit: str) -> str:
    m = model.lower()
    if re.search(r"luna2000|powerstack|battery|hv[sm]\b|\bsb[hr]\b|\bst\d+\s*kwh", m):
        return "bess"
    if re.search(r"hi-mo|tiger|vertex", m):
        return "mod"
    return implicit


def _catalog(producator, model):
    """r6: catalogul motorului (engine/calc/catalog_invertoare.py) — Pn și „hibrid” din codul modelului."""
    if _cat_inv is None or not model:
        return None
    try:
        return _cat_inv.cauta(producator, model)
    except Exception:                                   # noqa: BLE001 — catalogul e opțional pentru interpretor
        return None


def _p_din_model(model: str, producator=None):
    """Puterea c.a. din codul modelului: SUN2000-100KTL → 100, SG110CX → 110, SH25T → 25, MAX 50KTL3 → 50,
    S5-GC50K → 50, „20K” → 20; r6: catalogul motorului (Tauro ECO 50-3-D, STP 110-60 …). None dacă nu e evidentă."""
    mc = _catalog(producator, model)
    if mc and mc.get("Pn_kW"):
        return float(mc["Pn_kW"])
    m = re.search(r"(?:sg|sh)\s*(\d+(?:\.\d+)?)|(\d+(?:[.,]\d+)?)\s*k(?:tl|w)?(?![a-z]{2})", model.lower())
    if not m:
        return None
    v = numar(m.group(1) or m.group(2))
    return v if 1 <= v <= 500 else None


def _modele(c: Ctx, t: str) -> list[dict]:
    """Mărcile și modelele din text: [{s, e, producator, model, fel (inv/mod/bess), P_model}]."""
    out, ocupat = [], []
    for m in RE_MARCA.finditer(t):
        prod, fel = MARCI[m.group(1)]
        if m.group(1) == "ja" and not re.search(r"\d\s*w|modul|panou", t[m.end():m.end() + 25]):
            continue
        poz, toks = m.end(), []
        while True:
            mt = re.match(r"\s*([^\s,;()+:/]+)", t[poz:])
            if not mt:
                break
            tok = mt.group(1)
            rest = t[poz + mt.start(1):]
            if len(tok) > 1 and tok.endswith(".") and re.match(r"\.(?:\s|$)", t[poz + mt.end(1) - 1:]) \
                    and tok[:-1] not in _STOP_MODEL:
                # r10 (fotovoltaic #46): „SG50CX. Racordarea se …” — punctul de final de propoziție închide modelul
                toks.append((poz + mt.start(1), poz + mt.end(1) - 1))
                break
            if tok in _STOP_MODEL or tok.rstrip(".") in _STOP_MODEL or tok in MARCI or RE_VAL_UNIT_START.match(rest) or re.match(r"^\d+\s*[x×]", rest) \
                    or re.fullmatch(r"[x×]\d+", tok) or tok in ("bucati", "buc", "buc.", "pcs", "fiecare", "cuplaj") \
                    or not re.search(r"[a-z0-9]", tok):
                break
            toks.append((poz + mt.start(1), poz + mt.end(1)))
            poz += mt.end()
        # r8 (P0 fotovoltaic #33): „Primo 8.2-1 conectate câte unul” — cuvintele de după cod nu fac parte din model
        while len(toks) > 1 and re.fullmatch(r"[a-z]{3,}", t[toks[-1][0]:toks[-1][1]]) and \
                any(re.search(r"\d", t[a_:b_]) for a_, b_ in toks[:-1]):
            toks.pop()
        e = toks[-1][1] if toks else m.end()
        model = c.o(toks[0][0], e).strip() if toks else ""

        if model and model == model.lower():
            model = model.upper() if re.search(r"\d", model) else model.title()
        out.append(_info_model({"s": m.start(), "e": e, "producator": prod, "model": model or None,
                                "fel": _fel_model(model, fel), "P_model": _p_din_model(model, prod) if model else None,
                                "hibrid": bool((_catalog(prod, model) or {}).get("hibrid"))}))
        ocupat.append((m.start(), e))
    for m in RE_COD_MODEL.finditer(t):
        if any(s <= m.start() < e for s, e in ocupat):
            continue
        model = c.o(m.start(), m.end()).strip()
        if model == model.lower():
            model = model.upper() if re.search(r"\d", model) else model.title()
        prod = next((p for rx, p in PREFIX_PRODUCATOR if re.match(rx, m.group(0))), None)
        out.append(_info_model({"s": m.start(), "e": m.end(), "producator": prod, "model": model,
                                "fel": _fel_model(model, "inv"), "P_model": _p_din_model(model, prod),
                                "hibrid": bool((_catalog(prod, model) or {}).get("hibrid"))}))
    return sorted(out, key=lambda x: x["s"])


def _info_model(x: dict) -> dict:
    """r7: completările de catalog ale interpretorului (engine/interp_text.py): Pn / hibrid / rețea / tensiunea c.a.
    (800 V) pentru modelele lipsă din catalogul motorului; invertoarele de baterie (Sunny Island / Sunny Boy Storage)
    și bateriile (LUNA2000-15-S0, BYD HVS 10.2, Pylontech US5000) = BESS, cu kWh / kW din cod."""
    prod, model = x.get("producator"), x.get("model")
    if not model:
        return x
    if model.endswith("."):                              # r8: „SUN2000-100KTL-M2.” — punctul propoziției nu e din cod
        model = x["model"] = model.rstrip(".")
    sup = cauta_supl(prod, model)
    if sup:
        if x["P_model"] is None or (_catalog(prod, model) or {}).get("Pn_kW") is None:
            x["P_model"] = sup["Pn_kW"]
        if sup.get("hibrid") is not None and not (_catalog(prod, model) or {}).get("hibrid"):
            x["hibrid"] = bool(sup["hibrid"])
        x["retea_model"] = sup.get("retea")
        x["U_ca_V"] = sup.get("U_ca_V")
        x["producator"] = x.get("producator") or sup["producator"]
    else:
        mc = _catalog(prod, model) or {}
        if mc.get("retea"):
            x["retea_model"] = mc["retea"]
    ib = invertor_baterie(prod, model)
    if ib:
        x["fel"], x["inv_baterie"], x["P_model"], x["retea_model"] = "bess", True, ib["P_kW"], ib["retea"]
        x["producator"] = x.get("producator") or ib["producator"]
    kwh = kwh_din_model(prod, model)
    if kwh:
        x["fel"], x["kWh_model"] = "bess", kwh
        x["P_model"] = None
        x["P_bess_model"] = p_bess_din_model(prod, model)
    return x


def _fisa(d) -> dict:
    return {k: d[k] for k in ("producator", "model") if d.get(k)}


RE_BESS_TRIG = re.compile(r"\bbess\b|\bsistem\w*\s+de\s+stocare|\bstocare\b|\bbateri\w*|\bacumulator\w*")
RE_SEP_CLAUZA_PV = re.compile(r"(?<!\d),|,(?!\d)|;|:|(?<=[a-z0-9)])(?<![\s.][a-z])\.(?=\s)|\bsi\b|\+(?!\s*\d+\s*kwh)|\blanga\b|\bpe\s+(?=(?:un\s+|o\s+)?(?:invertor|hibrid))")


RE_CUPLAJ_CA = re.compile(r"\bac[\s-]*coupled\b|\bcupl\w*\s+(?:in\s+|pe\s+)?(?:c\.?\s*a\b\.?|ac\b|curent\s+alternativ)"
                          r"|\b(?:in|pe)\s+c\.\s*a\b\.?|\b(?:in|pe)\s+ca\b|\bpe\s+ac\b|^\s*ac\b|\bpe\s+bara\b")
RE_CUPLAJ_CC = re.compile(r"\bdc[\s-]*coupled\b|\bcupl\w*\s+(?:in\s+|pe\s+)?(?:c\.?\s*c\b\.?|dc\b|curent\s+continuu)"
                          r"|\b(?:in|pe)\s+c\.\s*c\b\.?|\b(?:in|pe)\s+cc\b|\bpe\s+dc\b|^\s*dc\b")


def extrage_bess(c: Ctx, modele: list):
    """BESS: „BESS [marcă model] X kWh [/ Y kW]” sau „Y kW / X kWh”, cu până la ~6 cuvinte între cuvântul-cheie și
    valori (P0-3). Întoarce dict sau None; fără valori → întrebare.
    r7: bateria recunoscută și DOAR după model („BYD HVS 7.7”, „4 x Pylontech US5000”, „LUNA2000-15-S0”) — kWh din
    cod × numărul de module; invertorul de baterie (SMA Sunny Island / Sunny Boy Storage) = PCS (cuplaj c.a.) cu P din
    cod; cuplajul și din „ac coupled”, „baterie ac”, „pe dc”, „în c.a.”."""
    t = _masca(c.mascat(), RE_COMPENSARE)
    m = RE_BESS_TRIG.search(t)
    bm = [x for x in modele if x["fel"] == "bess"]
    if m:
        mneg = re.search(r"\bfara\s+$", t[max(0, m.start() - 6):m.start()])
        if mneg:                                             # r6 (N14): „fără baterie” → nu se întreabă de BESS
            e = re.match(r"\w*", t[m.start():]).end() + m.start()
            c.consumat.append((max(0, m.start() - 6) + mneg.start(), e))
            c.nota(f"„{c.o(max(0, m.start() - 6) + mneg.start(), e).strip()}” → fără stocare")
            return None
    if not m and not bm:
        return None
    s0 = m.start() if m else min(x["s"] for x in bm)
    sep = RE_SEP_CLAUZA_PV.search(t, (m.end() if m else max(x["e"] for x in bm)))
    fin = sep.start() if sep else len(t)
    if not m:                                                # bateria doar după model: clauza modelului
        fin = max(fin, max(x["e"] for x in bm))
        a = max([x.end() for x in RE_SEP_CLAUZA_PV.finditer(t, 0, s0)] or [0])
        s0 = min(s0, a)
    fer = t[s0:fin]
    vs = [v for v in valori(fer) if v["marime"] in ("kWh", "kW")]
    kwh = next((v for v in vs if v["marime"] == "kWh"), None)
    kw = next((v for v in vs if v["marime"] == "kW"), None)
    if not kwh:                                              # r7: kWh lângă modelul bateriei, chiar dacă e după virgulă
        for x in bm:
            mk = re.match(rf"\s*(?P<v>{NUM})\s*(?P<u>kwh|mwh)\b", t[x["e"]:])
            if mk:
                kwh = {"val": numar(mk.group("v")) * UNITATI[mk.group("u")][1], "marime": "kWh", "s": x["e"] - s0 + mk.start("v"),
                       "e": x["e"] - s0 + mk.end()}
                fin = max(fin, x["e"] + mk.end())
    # modelele de baterie din clauză + cel mai apropiat din text (oriunde) — doar dacă e unul singur
    md_bat = [x for x in bm if not x.get("inv_baterie")]
    md_pcs = [x for x in bm if x.get("inv_baterie")]
    md = next((x for x in modele if s0 <= x["s"] < fin and (x["fel"] == "bess" or (m and x["s"] > m.start()
                                                                                    and not x.get("P_model")))), None)
    b = {"kWh": _nr(kwh["val"]) if kwh else None, "P_kW": _nr(kw["val"]) if kw else None}
    if kwh:
        # r8 (fotovoltaic #48): „4 x baterii BOS-G 5,12 kWh” = 4 module × 5,12 kWh = 20,48 kWh (n_module × kWh_modul)
        mxk = re.search(r"(?<![\w.,])(\d+)\s*[x×]\s*$", fer[max(0, kwh["s"] - 8):kwh["s"]])
        if mxk and int(mxk.group(1)) > 1 and "n_module" not in b:     # „baterie 6 x 2,4 kWh”
            n_m = int(mxk.group(1))
            b.update({"n_module": n_m, "kWh_modul": _nr(kwh["val"]), "kWh": _nr(round(n_m * kwh["val"], 3))})
            c.nota(f"„{n_m} x {fmt(kwh['val'], 2)} kWh” = {n_m} module × {fmt(kwh['val'], 2)} kWh = "
                   f"{fmt(n_m * kwh['val'], 2)} kWh")
        a_ = max(0, s0 - 10)
        mnm = re.search(r"(?<![\w.,])(\d+)\s*[x×]\s*(?:baterii|baterie|module|modul|acumulatori|acumulator|pachete|buc\w*)\b",
                        t[a_:s0 + kwh["s"]])
        if mnm and int(mnm.group(1)) > 1 and "n_module" not in b and not re.search(r"\bfiecare\b|\btotal\w*",
                                                                                      fer[kwh["e"]:kwh["e"] + 15]):
            n_m = int(mnm.group(1))
            b.update({"n_module": n_m, "kWh_modul": _nr(kwh["val"]), "kWh": _nr(round(n_m * kwh["val"], 3))})
            c.consumat.append((a_ + mnm.start(), a_ + mnm.end()))
            c.nota(f"„{c.o(a_ + mnm.start(), s0 + kwh['e']).strip()}” = {n_m} module × {fmt(kwh['val'], 2)} kWh = "
                   f"{fmt(n_m * kwh['val'], 2)} kWh")

    # r8 (fotovoltaic #13, #45): „4 x PCS 250 kW”, „8 x 250 kW PCS” = n_pcs convertoare identice (P total = n × P)
    mp = re.search(rf"(?<![\w.,])(?P<n>\d+)\s*[x×]\s*(?:pcs|convertoare?|invertoare?\s+(?:de\s+)?baterie)\s*(?:de\s+)?(?P<p>{NUM})\s*"
                   rf"(?P<u>kw|mw)\b|(?<![\w.,])(?P<n2>\d+)\s*[x×]\s*(?P<p2>{NUM})\s*(?P<u2>kw|mw)\s*(?:pcs|convertoare?)\b", t)
    if mp:
        n_p = int(mp.group("n") or mp.group("n2"))
        p_u = numar(mp.group("p") or mp.group("p2")) * UNITATI[mp.group("u") or mp.group("u2")][1]
        b["n_pcs"] = n_p
        b["pcs"] = dict(b.get("pcs") or {}, n=n_p, Pn_kW=_nr(p_u))
        if not b["P_kW"]:
            b["P_kW"] = _nr(n_p * p_u)
        c.consumat.append((mp.start(), mp.end()))
        c.nota(f"„{c.o(mp.start(), mp.end()).strip()}” = {n_p} PCS × {fmt(p_u)} kW = {fmt(n_p * p_u)} kW (n_pcs = {n_p})")

    if not b["kWh"] and md_bat:
        tot, desc = 0.0, []
        for x in md_bat:
            if not x.get("kWh_model"):
                continue
            mn = re.search(r"(?<![\w.,])(\d+)\s*[x×]\s*$", c.t[max(0, x["s"] - 8):x["s"]])
            n = int(mn.group(1)) if mn else 1
            if mn:
                c.consumat.append((max(0, x["s"] - 8) + mn.start(), x["s"]))
            tot += n * x["kWh_model"]
            desc.append(f"{n} × {x.get('model')} ({fmt(x['kWh_model'], 2)} kWh)" if n > 1 else
                        f"{x.get('model')} = {fmt(x['kWh_model'], 2)} kWh")
        if tot:
            b["kWh"] = _nr(round(tot, 2))
            c.nota("capacitatea bateriei din codul modelului: " + "; ".join(desc)
                   + (f" → {fmt(tot, 2)} kWh" if len(desc) > 1 or "×" in desc[0] else "") + " (confirmați cu fișa)")
    if md_pcs:
        x = md_pcs[0]
        if not b["P_kW"]:
            b["P_kW"] = _nr(x["P_model"])
        b["pcs"] = {k: v for k, v in (("producator", x.get("producator")), ("model", x.get("model")),
                                      ("P_kW", _nr(x["P_model"]))) if v}
        b["_pcs_retea"] = x.get("retea_model")
        c.nota(f"{x.get('model')} = invertor de baterie (PCS, cuplaj c.a.) de {fmt(x['P_model'])} kW")
    if md_bat:
        md = md_bat[0]
        if not b["P_kW"] and md.get("P_bess_model"):           # r8 (#68): LUNA2000-200KWH-2H1 = 100 kW / 200 kWh
            b["P_kW"] = _nr(md["P_bess_model"])
            c.nota(f"{md.get('model')}: P = {fmt(md['P_bess_model'])} kW din codul modelului (…-2H = 2 ore la puterea "
                   "nominală) — confirmați cu fișa")
    if not b["kWh"] and not b["P_kW"]:
        if not re.search(r"\bhibrid", c.t):
            c.intrebari.append(("I02", "Ce capacitate (kWh) și ce putere (kW) are bateria (sistemul de stocare, BESS)? "
                                       "Până la răspuns nu e desenată."))
        if m:
            c.consumat.append((m.start(), m.end()))
        return None
    capat = max([s0 + v["e"] for v in vs] + ([kwh and s0 + kwh["e"]] if kwh else []) + [x["e"] for x in bm if x["s"] < fin + 40]
                + ([md["e"]] if md else []) + [m.end() if m else s0])
    for x in modele:                 # un model din clauza bateriei e baterie, dacă nu e un invertor recunoscut din cod
        if m and m.start() <= x["s"] < fin and x["fel"] != "mod" and not _catalog(x.get("producator"), x.get("model")) \
                and not cauta_supl(x.get("producator"), x.get("model")):
            x["fel"] = "bess"
    if md and md["fel"] != "bess":
        md = None
    if md:
        b.update(_fisa(md))
    # r6 (f20, f21, f22, f24): cuplajul scris — „cuplaj c.c.”, „cuplat în c.a.”, „cuplată ca”; „X kWh fiecare”
    z0 = m.start() if m else s0
    zona = c.t[z0:min(len(c.t), fin + 40)]
    zona_scurta = c.t[max(0, z0 - 25):min(len(c.t), fin + 40)]
    mc = RE_CUPLAJ_CC.search(zona) or RE_CUPLAJ_CA.search(zona) or RE_CUPLAJ_CA.search(zona_scurta) \
        or RE_CUPLAJ_CC.search(zona_scurta)
    if mc:
        b["cuplaj"] = "cc" if RE_CUPLAJ_CC.match(mc.group(0)) or RE_CUPLAJ_CC.search(mc.group(0)) else "ca"
        base = z0 if mc.re is not None and mc.string is zona else max(0, z0 - 25)
        capat = max(capat, base + mc.end())
        c.foloseste(base + mc.start(), base + mc.end())
    if b.get("pcs"):
        if b.get("cuplaj") == "cc":
            c.probleme.append(("I08", f"Contradicție: bateria e declarată cuplată în c.c., dar {b['pcs'].get('model')} e un "
                                      "invertor de baterie (PCS) cuplat în c.a. (I08).",
                               f"Bateria e cuplată în c.a. prin {b['pcs'].get('model')} (PCS separat, pe bara c.a.), sau în "
                               "c.c. pe un invertor hibrid (atunci fără Sunny Island)?"))
        b["cuplaj"] = "ca"
    # r7: pe ce invertor e bateria — „pe INV-2”, „la invertorul 2 și 3”, „pe al doilea invertor” → bess.la
    ml = re.search(r"\b(?:pe|la|conectat\w*\s+(?:pe|la))\s+(?:inv(?:ertorul)?\s*-?\s*(?P<l>\d+(?:\s*(?:,|si)\s*\d+)*)"
                   r"|(?P<o>primul|al\s+doilea|al\s+treilea)\s+invertor)\b", c.t)
    if ml:
        if ml.group("l"):
            la = [f"INV-{x}" for x in re.findall(r"\d+", ml.group("l"))]
        else:
            la = [f"INV-{ {'primul': 1}.get(ml.group('o'), 2 if 'doilea' in ml.group('o') else 3)}"]
        b["la"] = la
        c.foloseste(ml.start(), ml.end())
        c.nota(f"„{c.o(ml.start(), ml.end()).strip()}” = bateria e pe {', '.join(la)} (bess.la)")
    mf = re.search(r"\bfiecare\b|\bpe\s+invertor\b|\bper\s+invertor\b", zona)
    if mf:
        b["fiecare"] = True
        capat = max(capat, z0 + mf.end())
    c.consumat.append((min(s0, m.start() if m else s0), capat))
    return b


RE_LIMITARE = [
    (re.compile(r"\binjecti\w*\s+(?:zero|0\b)|\bzero\s+injecti\w*|\bfara\s+injecti\w*|\bnon[\s-]*injecti\w*"
                r"|\blimitat\w*\s+la\s+0\b(?!\s*[,.]\d)|\bexport\s+zero"), None),
    (re.compile(rf"\b(?:limitare\w*|limitat\w*|limita)\s+(?:a\s+)?(?:injecti\w*\s+)?(?:la\s+)?(?P<v>{NUM})\s*(?P<u>kw|mw)\b"), 1),
    (re.compile(rf"\binjecti\w*\s+(?:limitat\w*|maxim\w*|max\.?)\s+(?:la\s+)?(?P<v>{NUM})\s*(?P<u>kw|mw)\b"), 1),
    (re.compile(rf"\b(?:p\s*)?(?:evacuat\w*|injectat\w*)\s+(?:max\w*\s+)?(?P<v>{NUM})\s*(?P<u>kw|mw)\b"), 2),
]


RE_LIMITARE_PCT = re.compile(rf"\b(?:injecti\w*\s+(?:limitat\w*|maxim\w*)|limitare\w*(?:\s+a)?(?:\s+injecti\w*)?|limitat\w*"
                             rf"|export\w*\s+limitat\w*)\s+(?:la\s+)?(?P<v>{NUM})\s*%(?:\s+din\s+(?:putere\w*(?:\s+instalat\w*)?|pn|pi"
                             rf"|puterea\s+(?:instalata|invertoarelor|centralei)))?")


def extrage_limitare(c: Ctx):
    """„limitare injecție 50 kW”, „injecție limitată la 0”, „injecție zero”, „fără injecție” → kW (0 = injecție zero)."""
    t = c.mascat()
    mp = RE_LIMITARE_PCT.search(t)
    if mp:                          # r10 (P0 fotovoltaic #58): „limitată la 70 % din putere” → kW după Σ invertoare
        c._lim_pct = numar(mp.group("v"))
        c.consumat.append((mp.start(), mp.end()))
        c._lim_pct_txt = c.o(mp.start(), mp.end()).strip()
        return None
    for rx, fel in RE_LIMITARE:
        m = rx.search(t)
        if not m:
            continue
        if fel == 2:
            continue                                   # P evacuată: tratată la prosumator (ATR)
        pre = c.t[max(0, m.start() - 45):m.start()]
        if fel == 1 and re.match(r"limitate\b|limitat\w*\s+(?:fiecare|individual)", c.t[m.start():]) and (
                re.search(r"\d\s*[x×]\s*[a-z]{2,}[\w-]*\d\w*\s*$|\binvert\w*[^,;]*$", pre)
                or re.search(r"\bfiecare\b", c.t[m.start():m.end() + 12])):
            # r9 (fotovoltaic #68): „4 x SG110CX limitate la 100 kW” = Pmax setat pe FIECARE invertor (4 × 100 = 400 kWac),
            # nu limitarea injecției totale la punctul de racord
            v = numar(m.group("v")) * UNITATI[m.group("u")][1]
            c.consumat.append((m.start(), m.end()))
            c.nota(f"„{c.o(m.start(), m.end()).strip()}” = puterea activă maximă setată pe FIECARE invertor ({fmt(v)} kW / "
                   "invertor), nu limitarea injecției la punctul de racord")
            c._pmax_per_inv = v
            continue
        c.consumat.append((m.start(), m.end()))
        v = 0 if fel is None else numar(m.group("v")) * UNITATI[m.group("u")][1]
        c.nota(f"„{c.o(m.start(), m.end()).strip()}” = limitarea injecției la {fmt(v)} kW"
               + (" (injecție zero: analizor/contor de control la punctul de racord + EMS / Power Manager)" if v == 0
                  else " (analizor/contor de control la punctul de racord)"))
        return _nr(v)
    return None


RE_INV_NOUN = re.compile(r"\b(?:invert\w*|inv)\b")
RE_PV_NOUN2 = re.compile(r"fotovoltaic\w*|\bpv\b|\bpanouri\b|\bsolar\w*")


def _segmente(t: str, s0=0, e0=None):
    e0 = len(t) if e0 is None else e0
    out, poz = [], s0
    for m in RE_SEP_CLAUZA_PV.finditer(t, s0, e0):
        if t[poz:m.start()].strip():
            out.append((poz, m.start()))
        poz = m.end()
    if t[poz:e0].strip():
        out.append((poz, e0))
    return out


def grupuri_invertoare(c: Ctx, modele: list) -> list[dict]:
    """r5 (P0-1, P0-2): grupurile de invertoare — fiecare cu n, Pn (de lângă invertor / din model), producător, model.
    Nu se împarte niciodată un kW la n fără întrebare."""
    t = c.mascat()
    grupuri = []
    for s, e in _segmente(c.t):
        seg = t[s:e]
        mods = [x for x in modele if s <= x["s"] < e and x["fel"] == "inv"]
        if any(x.get("model") for x in mods):        # r9 (#35): „invertoare Sungrow 1 x SG125CX-P2” — marca singură nu e grup
            mods = [x for x in mods if x.get("model")]
        noun = RE_INV_NOUN.search(seg)
        mx = re.search(rf"(?<![\w.,])(?P<n>\d+)\s*[x×]\s*(?P<p>{NUM})\s*(?P<u>kw|kva|mw)\b", seg)
        if not (noun or mods or mx):
            # r7 (locuințe #39): „două invertoare 13,5 kW și 13,5 kW” — valorile următoare continuă lista grupului
            prev = grupuri[-1] if grupuri else None
            mv = re.match(rf"\s*({NUM})\s*(kw|kva)\b", seg)
            if prev and mv and prev["Pn_kW"] is None and prev["n"] and prev["n"] > 1 and prev["e"] >= s - 4 \
                    and c.t[prev["e"]:prev["e"] + 2].strip().startswith(":"):
                # r9 (locuințe #21): „2 invertoare: 12 și 12 kW” — antetul cu număr, apoi puterea fiecăruia
                prev["Pn_kW"], prev["explicit"], prev["_lista"] = numar(mv.group(1)), True, []
                prev["_kva"] = mv.group(2) == "kva"
                prev["e_cons"] = s + mv.end()
                prev["e"] = e
                continue
            if prev and mv and prev.get("explicit") and prev["n"] and prev["n"] > 1 + len(prev.get("_lista", [])) \
                    and prev["e"] >= s - 4:
                prev.setdefault("_lista", []).append(numar(mv.group(1)))
                prev["e_cons"] = s + mv.end()
                prev["e"] = e
            continue
        g = {"s": s, "e": e, "n": None, "Pn_kW": None, "plural": False, "explicit": False}
        # numărul
        mi = re.search(r"\binvertor\w*\s+(\d+)\s*=", seg)
        mn = re.search(r"\b(?P<n>\d+|un|o|doua|doi|trei|patru|cinci)\s+(?:invertor\w*|invertoare\w*|inv|bucati|buc\b\.?|pcs)",
                       seg)
        # r6 (fotovoltaic P0-1): „2 x SG110CX”, „3 x Solis …” — pe textul NEmascat (modelul e mascat), „SH50T x2”, „20 kW x2”
        # r7 (P0-1): „N x” lângă o baterie („4 x Pylontech”), un modul sau un cablu („CYABY 5x16”) NU e nr. de invertoare
        mxm = None
        for mm_ in re.finditer(r"(?<![\w.,])(?P<n>\d+)\s*[x×]\s*(?=[a-z(§])", c.t[s:e]):
            poz = s + mm_.end()
            tinta = next((x for x in modele if 0 <= x["s"] - poz <= 2), None)
            if (tinta and tinta["fel"] != "inv") or re.match(rf"\(?\s*{_TIP_CABLU}|module|panouri|baterii|acumulator",
                                                              c.t[poz:]) \
                    or re.search(rf"{_TIP_CABLU}\s*$", c.t[max(s, mm_.start() - 12):mm_.start()]):
                continue
            mxm = mm_
            break
        msuf = None                                               # (n, capăt relativ)
        for x in mods[:1]:
            mm = re.match(r"\s*[x×]\s*(\d+)\b(?!\s*(?:kw|kva|a|m)\b)", c.t[x["e"]:e])
            if mm:
                msuf = (int(mm.group(1)), x["e"] - s + mm.end())
        if not msuf:
            mm = re.search(rf"{NUM}\s*k(?:w|va)\b\s*[x×]\s*(\d+)\b", c.t[s:e])
            if mm:
                msuf = (int(mm.group(1)), mm.end())
        if mi:
            g["n"] = 1
        elif mn:
            g["n"] = _NUMERAL.get(mn.group("n")) or int(mn.group("n"))
        elif mx:
            g["n"] = int(mx.group("n"))
        elif mxm:
            g["n"] = int(mxm.group("n"))
        elif msuf:
            g["n"] = msuf[0]
        elif mods and re.search(r"\bfiecare\b[^,;]*?\b(?:cate\s+)?(?:un|o|1)\s+$", c.t[max(0, s - 40):mods[0]["s"]]) and \
                re.search(r"(?<![\w.,])(\d+)\s*[x×]\s*\d+(?:[.,]\d+)?\s*kwp\b|(?<![\w.,])(\d+)\s+(?:acoperis\w*|campuri|hale"
                          r"|cladiri|zone|parcele|sectoare)\b", c.t[:mods[0]["s"]]):
            # r8 (P0 fotovoltaic #51): „2 x 50 kWp pe 2 acoperișuri, fiecare cu câte un SG50CX” = 2 invertoare
            mf_ = list(re.finditer(r"(?<![\w.,])(\d+)\s*[x×]\s*\d+(?:[.,]\d+)?\s*kwp\b|(?<![\w.,])(\d+)\s+(?:acoperis\w*|campuri"
                                   r"|hale|cladiri|zone|parcele|sectoare)\b", c.t[:mods[0]["s"]]))[-1]
            g["n"] = int(mf_.group(1) or mf_.group(2))
            c.nota(f"„fiecare cu câte un {mods[0].get('model')}” × {g['n']} = {g['n']} invertoare")
        elif mods and re.search(r"(?<![\w.,])(\d{1,2})\s+$", c.t[s:mods[0]["s"]]):     # r6 (f15): „2 SMA STP 50-41”

            g["n"] = int(re.search(r"(\d{1,2})\s+$", c.t[s:mods[0]["s"]]).group(1))
        elif noun and re.match(r"invertor(?:ul)?\b|inv\b", noun.group(0)) and not (
                noun.group(0) == "inv" and c.t[e:e + 2].strip().startswith(":")):   # r9 (#61): „Inv: 1 x A + 1 x B” = antet
            g["n"] = 1
        else:
            g["plural"] = bool(noun)
        # puterea
        vs = [v for v in valori(seg) if v["marime"] in ("kW", "kVA") and not (mi and v["s"] < mi.end() - 0)]
        if mx:
            p, u = numar(mx.group("p")), mx.group("u")
            g["Pn_kW"], g["explicit"] = p * UNITATI[u][1], True
            g["_kva"] = u == "kva"
        else:
            ref = noun.end() if noun else (mods[0]["s"] - s if mods else 0)
            # r7 (#41): „10 invertoare … dar puterea totală a centralei 500 kW” — valoarea legată de alt cuvânt-cheie
            # (total / P aprobată / baterie / limitare) nu e puterea invertorului
            dupa = [v for v in vs if v["s"] >= ref and _ancora(c, {"s": s + v["s"]}) in (None, "inv", "pv")]
            inainte = [v for v in vs if v["s"] < ref]
            v = dupa[0] if dupa else None
            if v is None and mods and mods[0]["P_model"]:
                g["Pn_kW"], g["_din_model"] = mods[0]["P_model"], True
            elif v is None and inainte and noun and not re.search(r"\.\s", c.t[s + inainte[-1]["e"]:s + noun.start()]) and (
                    g["n"] in (None, 1) or not re.search(r"\bcu\b", c.t[s + inainte[-1]["e"]:s + noun.start()])):
                # r8 (P0 fotovoltaic #28, #58): „CEF 300 kW cu 3 invertoare” — kW-ul dinaintea lui „cu N invertoare” e
                # puterea TOTALĂ a centralei, nu a fiecărui invertor
                v = inainte[-1]
            if v is not None:
                g["Pn_kW"], g["explicit"] = v["val"], True
                g["_kva"] = v["marime"] == "kVA"
            par_fisa = v is not None and mods and re.fullmatch(r"\s*\(\s*", c.t[mods[0]["e"]:s + v["s"]] if mods[0]["e"] <= s + v["s"]
                                                                  else "x") and re.match(r"\s*[,)]", c.t[s + v["e"]:s + v["e"] + 6])
            if par_fisa and abs(mods[0]["P_model"] - g["Pn_kW"]) > 0.01:
                # r11 (fotovoltaic #15): „SG350HX (320 kW, ieșire 800 V)” — fișa din paranteză (Pn ≠ codul) se folosește
                c.nota(f"„{mods[0]['model']} ({fmt(g['Pn_kW'])} kW …)”: Pn declarat din fișă {fmt(g['Pn_kW'])} kW ≠ codul modelului "
                       f"({fmt(mods[0]['P_model'])}) — se folosește valoarea declarată")
            elif g["explicit"] and mods and mods[0]["P_model"] and abs(mods[0]["P_model"] - g["Pn_kW"]) > 0.01 \
                    and not (v is not None and v["marime"] == "kVA") and v in dupa:
                # r6 (fotovoltaic P1-8, f44): „SUN2000-100KTL-M2 de 50 kW” = contradicție model ↔ putere → întrebare
                c.probleme.append(("I08", f"Contradicție: {mods[0]['model']} are {fmt(mods[0]['P_model'])} kW (din codul "
                                          f"modelului), dar puterea scrisă e {fmt(g['Pn_kW'])} kW (I08).",
                                   f"Invertorul este {mods[0]['model']} ({fmt(mods[0]['P_model'])} kW) sau un model de "
                                   f"{fmt(g['Pn_kW'])} kW?"))
        if mods:
            g.update(_fisa(mods[0]))
            if mods[0].get("hibrid"):
                g["hibrid"] = True
            for k in ("U_ca_V", "retea_model"):
                if mods[0].get(k):
                    g[k] = mods[0][k]
        if re.search(r"\bhibrid\w*", c.t[s:e]):
            g["hibrid"] = True
        if not mods and noun:
            mb = next((x for x in modele if s <= x["s"] < e), None)
            if mb and mb["fel"] == "inv":
                g.update(_fisa(mb))
        g["txt"] = c.o(s, e).strip()
        capete = [x.end() for x in (noun, mi, mn, mx, mxm) if x] + [x["e"] - s for x in mods]
        inceputuri = [x.start() for x in (noun, mi, mn, mx, mxm) if x] + [x["s"] - s for x in mods]
        if msuf:
            capete.append(msuf[1])
        if g["Pn_kW"] is not None and g.get("explicit") and not mx:
            capete.append(v["e"])
            inceputuri.append(v["s"])
        g["e_cons"] = s + max(capete) if capete else e
        g["s_cons"] = s + min(inceputuri) if inceputuri else s   # r6 (f45): „prosumator 20 kW cu 2 inv…” — 20 kW rămâne
        grupuri.append(g)
    # „N invertoare [diferite]: A, B” / „cu invertoare: 2 × …” — antetul fără putere dă numărul total
    out, i = [], 0
    while i < len(grupuri):
        g = grupuri[i]
        if g["Pn_kW"] is None and (g["n"] or g["plural"]):
            copii = []
            j = i + 1
            antet = c.t[g["e"]:g["e"] + 2].strip().startswith(":")      # r8 (#28): „3 invertoare: 2 x A și 2 x B”
            while j < len(grupuri) and grupuri[j]["Pn_kW"] is not None and (grupuri[j]["n"] is None or not g["n"] or antet):
                copii.append(grupuri[j])
                j += 1
            if copii:
                if g["n"] and len(copii) == 1 and copii[0]["n"] is None:
                    copii[0]["n"] = g["n"]
                for k in copii:
                    k["n"] = k["n"] or 1
                    for kk in ("producator", "model"):
                        if g.get(kk) and not k.get(kk):
                            k[kk] = g[kk]
                tot = sum(k["n"] for k in copii)
                if g["n"] and tot != g["n"]:
                    c.probleme.append(("I05", f"S-au cerut {g['n']} invertoare, dar s-au găsit {tot} (I05).",
                                       f"Câte invertoare are centrala: {g['n']} sau {tot}?"))
                out += copii
                i = j
                continue
        out.append(g)
        i += 1
    lista = []
    for g in out:                               # r7: „2 invertoare 13,5 kW și 13,5 kW” → grupuri pe valori distincte
        if g.get("_lista") and g["n"] == 1 + len(g["_lista"]):
            vals = [g["Pn_kW"]] + g["_lista"]
            c.nota(f"„{c.o(g['s'], g['e_cons']).strip()}” = {g['n']} invertoare: " + " + ".join(fmt(v) for v in vals) + " kW")
            for v in dict.fromkeys(vals):
                lista.append(dict(g, n=vals.count(v), Pn_kW=v, _lista=None))
        else:
            lista.append(g)
    out = lista
    # r9 (fotovoltaic P0 #14): „5 invertoare de 30 kW, Sungrow SG30CX” — modelul fără număr, cu aceeași putere ca un
    # grup numărat fără model, e modelul ACELUI grup (nu încă un invertor)
    for g in list(out):
        if g["n"] is None and g.get("model") and g["Pn_kW"] is not None:
            tinta = next((k for k in out if k is not g and not k.get("model") and k["n"] and k["Pn_kW"] is not None
                          and abs(k["Pn_kW"] - g["Pn_kW"]) < 0.01), None)
            if tinta:
                for kk in ("producator", "model", "hibrid", "U_ca_V", "retea_model"):
                    if g.get(kk) and not tinta.get(kk):
                        tinta[kk] = g[kk]
                c.consumat.append((g.get("s_cons", g["s"]), g.get("e_cons", g["e"])))
                c.nota(f"„{g['txt']}” = modelul celor {tinta['n']} invertoare de {fmt(tinta['Pn_kW'])} kW (nu un invertor în plus)")
                out.remove(g)
    for g in out:
        if g["n"] is None:
            g["n"] = 1
        if g.get("_kva"):
            c.nota(f"„{g['txt']}”: kVA la invertor = puterea aparentă nominală → Pn = {fmt(g['Pn_kW'])} kW (cosφ 1)")
        if g.get("explicit") and not g.get("model") and re.match(r"\s*invertor(?:ul)?\b", c.t[g["s"]:g["e"]]) \
                and not re.search(r"\d\s+invertor", c.t[g["s"]:g["e"]]):
            mm = re.search(rf"invertor(?:ul)?\s+(?:hibrid\w*\s+)?(?:de\s+)?{NUM}\s*k(?:w|va)\b", c.t[g["s"]:g["e"]])
            if mm:
                c.nota(f"„{c.o(g['s'] + mm.start(), g['s'] + mm.end()).strip()}” = 1 invertor de {fmt(g['Pn_kW'])} kW")
        if g.get("_din_model"):
            c.nota(f"Pn = {fmt(g['Pn_kW'])} kW din codul modelului {g.get('model')} — confirmați cu fișa tehnică")
        c.consumat.append((g.get("s_cons", g["s"]), g.get("e_cons", g["e"])))
    return out


def extrage_module_string(c: Ctx, modele: list, intr: dict):
    """Modulul PV (marcă, model, Pmax din „W/Wp” < 1000) + stringuri + gPV declarate."""
    t = c.mascat()
    for v in valori(t):
        if v["u"] in ("w", "wp") and v["brut"] < 1000 and v["brut"] >= 100:
            md = next((x for x in reversed(modele) if x["e"] <= v["s"] and v["s"] - x["e"] < 25 and x["fel"] == "mod"),
                      None)
            mod = {"Pmax_W": _nr(v["brut"])}
            if md:
                mod.update(_fisa(md))
                md["fel"] = "mod"
            s = md["s"] if md else v["s"]
            mm = re.search(r"\b(?:module|modul|panouri|panou)\s*$", t[max(0, s - 12):s])
            c.consumat.append((s - (len(mm.group(0)) if mm else 0), v["e"]))
            intr["modul"] = mod
            c.nota(f"„{c.o(s, v['e']).strip()}” = modulul PV: Pmax {fmt(v['brut'])} W (nu putere de invertor)")
            break
    if "modul" not in intr:                     # r6 (f18): „module JA 550” fără W → Pmax 550 W (presupus)
        mw = re.search(r"\b(?:module|modul|panouri|panou)\s+(?:[a-z]+\s+){0,3}?(?P<v>[2-8]\d\d)\b(?![.,]\d)(?!\s*(?:kw|kwp|a|m|v|wp|w|buc)\b)", t)
        if mw:
            md = next((x for x in modele if mw.start() <= x["s"] < mw.end() and x["fel"] == "mod"), None)
            intr["modul"] = dict({"Pmax_W": int(mw.group("v"))}, **(_fisa(md) if md else {}))
            c.consumat.append((mw.start(), mw.end()))
            c.nota(f"„{c.o(mw.start(), mw.end()).strip()}” = modul de {mw.group('v')} W (unitatea W presupusă)")
    st = {}

    def ia(rx, *chei, conv=int):
        m = re.search(rx, t)
        if not m:
            return None
        for k, g in zip(chei, m.groups()):
            if g is not None and k not in st:
                st[k] = conv(g) if conv is int else _nr(numar(g))
        c.consumat.append((m.start(), m.end()))
        return m
    # r6 (f02, f17, f19): „16 module/string”, „string 18 module x 12 stringuri”, „10 stringuri x 11”
    ia(r"(\d+)\s+module\s*[x×]\s*(\d+)\s+stringuri", "n_module", "n_stringuri_paralel")
    ia(r"(\d+)\s+stringuri\s*(?:[x×]|de|cu)\s*(\d+)(?:\s+module)?\b", "n_stringuri_paralel", "n_module")
    ia(r"(\d+)\s+module\s*(?:pe|/|per|in)\s*string\w*", "n_module")
    ia(r"\bstring\w*\s+(?:de\s+|cu\s+)?(\d+)\s+module", "n_module")
    m = re.search(r"stringuri\s+(\d+)\s+pe\s+mppt|(\d+)\s+stringuri?\s+pe\s+mppt|(\d+)\s+pe\s+mppt", t)
    if m:
        st["n_stringuri_paralel"] = int(next(x for x in m.groups() if x))
        st["_pe_mppt"] = True
        c.consumat.append((m.start(), m.end()))
    elif "n_stringuri_paralel" not in st:
        ia(r"(\d+)\s+stringuri\b(?!\s+pe\s+mppt)", "n_stringuri_paralel") or \
            ia(r"stringuri\s+(\d+)\b(?!\s+pe)", "n_stringuri_paralel")
    ia(r"(?<!pe\s)\b(\d+)\s*mppt\b|\bmppt\s*(?:=|:)?\s*(\d+)\b", "n_MPPT", "n_MPPT")
    ia(rf"\b[vu]oc\w*(?:\s+(?:modul|panou)\w*)?(?:\s+stc)?\s*(?:=|de|:)?\s*({NUM})\s*v\b", "Uoc_V", conv=float)
    ia(rf"\bisc\w*(?:\s+(?:modul|panou)\w*)?(?:\s+stc)?\s*(?:=|de|:)?\s*({NUM})\s*a\b", "Isc_A", conv=float)
    # r8: „96 x Panou fotovoltaic …” / „1000 x modul …” (rândul unui tabel) = numărul total de module
    mt = next((x for x in re.finditer(r"(?<![\w.,])(\d+)\s*(?:[x×]\s*)?(?:module|modul|panouri|panou)\b(?!\s*(?:/|pe|per|in)\s*string)"
                                      r"(?!\s*[x×]\s*\d+\s*string)", t)
               if not re.search(r"string\w*\s+(?:de\s+|cu\s+|[x×]\s*)?$|\b(?:a\s+)?cate\s+$|\bde\s+cate\s+$",
                                t[max(0, x.start() - 14):x.start()])), None)
    if mt:
        c.consumat.append((mt.start(), mt.end()))
        n_tot = int(mt.group(1))
        c._n_module_tot = n_tot
        prod = (st.get("n_module") or 0) * (st.get("n_stringuri_paralel") or 0) * (st.get("n_MPPT") if st.get("_pe_mppt") else 1)
        c.nota(f"„{c.o(mt.start(), mt.end()).strip()}” = numărul total de module (informativ)")
        if prod and prod != n_tot:
            c.intrebari.append(("I08", f"{n_tot} module în total, dar stringurile dau {prod} module "
                                       f"({st.get('n_module')} × {st.get('n_stringuri_paralel')}"
                                       + (f" × {st['n_MPPT']} MPPT" if st.get("_pe_mppt") else "") + "). Care e configurația?"))
    m = re.search(rf"\bgpv\b[^,;]*?({NUM})\s*a\b|sigurant\w*\s+(?:gpv\s+)?({NUM})\s*a\s+pe\s+string", t)
    if m or re.search(r"\bgpv\b|sigurant\w*\s+pe\s+string", t):
        st["gpv"] = True
        if m:
            intr["gpv_In_A"] = st["gpv_In_A"] = _nr(numar(m.group(1) or m.group(2)))
            e = m.end() + (re.match(r"\s*pe\s+(?:fiecare\s+)?string\w*", t[m.end():]) or re.match("", "")).end()
            c.consumat.append((m.start(), e))
    if st:
        pe_mppt = st.pop("_pe_mppt", False)
        c.nota("stringuri: " + ", ".join(f"{k} = {v}" for k, v in st.items()) + (" (pe MPPT)" if pe_mppt else ""))
        intr["string"] = st     # declarat (r5); motorul cere și n_module / Voc pentru verificarea c.c.
        if not st.get("n_module") or not st.get("Uoc_V"):
            c.nota("datele stringului sunt incomplete (lipsește numărul de module pe string / Voc) — se completează în "
                   "Calcul; " + ("siguranțele gPV pe string sunt cerute" if st.get("gpv") else "")
                   .rstrip("; "))


def _valoare_lipita(c: Ctx, rx) -> tuple | None:
    m = rx.search(c.mascat())
    if not m:
        return None
    c.consumat.append((m.start(), m.end()))
    g = next(k for k in m.groupdict() if m.group(k) and k.startswith("v"))
    u = next((m.group(k) for k in ("u", "u2", "u3") if m.groupdict().get(k)), "kw")
    return numar(m.group(g)) * UNITATI.get(u, ("", 1))[1], m


RE_PV_LEGAT = re.compile(
    rf"(?:\bpv\b|\bsolar\w*|\bfotovoltaic\w*|\bpanouri(?:\s+fotovoltaice)?)\s+(?:(?:de|pe\s+casa|tri\w*|mono\w*)\s+){{0,2}}"
    rf"(?P<v>{NUM})\s*(?P<u>kw|mw)\b"
    rf"|(?P<v2>{NUM})\s*(?P<u2>kw|mw)\s+(?:de\s+)?(?:fotovoltaic\w*|pv\b|solar\w*|panouri)")


def _pv_legat(c: Ctx, tip: str):
    """r7: „pv 6 kW”, „solar 10 kw”, „fotovoltaice 10 kW”, „50 kW fotovoltaic” — fără invertor numit: puterea c.a. a
    sistemului = un invertor (PRESUPUS, declarat). La CEF > 100 kW numărul invertoarelor se întreabă (nu se presupune)."""
    m = RE_PV_LEGAT.search(c.mascat())
    if not m:
        return None
    v = numar(m.group("v") or m.group("v2")) * UNITATI[m.group("u") or m.group("u2")][1]
    if tip == "cef" and v > 100:
        return None
    s, e = (m.start("v"), m.end()) if m.group("v") else (m.start(), m.end("u2"))
    c.consumat.append((s, e))
    c.nota(f"„{c.o(m.start(), m.end()).strip()}” = puterea c.a. a sistemului fotovoltaic → 1 invertor de {fmt(v)} kW "
           "(PRESUPUS — indicați modelul / numărul invertoarelor dacă diferă)")
    return {"s": m.start(), "e": m.end(), "n": 1, "Pn_kW": v, "explicit": True, "txt": c.o(m.start(), m.end()).strip()}


RE_ANCORE = [("pa", r"\bpa\b|aprobat\w*|\batr\b|bransament\w*|\bbmp[mt]\w*|absorbit\w*|contractat\w*|\bcas(?:a|ei)\b"
                    r"|locuint\w*|apartament\w*|consum\w*"),
             ("total", r"\btotal\w*|prosumator\w*|instalati\w*|central\w*|\bcef\b|\bsistem\w*"),
             ("inv", r"\binvert\w*|\binv\b"), ("bess", r"bater\w*|\bbess\b|stocare|\bpcs\b|acumulator\w*"),
             ("pv", r"\bpv\b|solar\w*|fotovolt\w*|panouri"), ("lim", r"limit\w*|injecti\w*")]
RE_ANCORE = [(k, re.compile(rx)) for k, rx in RE_ANCORE]


def _ancora(c: Ctx, v) -> str | None:
    """r7: entitatea de care ține o valoare = cuvântul-cheie cel mai apropiat din stânga, în aceeași clauză."""
    a = max([x.end() for x in re.compile(r"(?<!\d),|,(?!\d)|;|:|\bsi\b|\+|\(|\)").finditer(c.t, 0, v["s"])] or [0])
    pre = c.t[a:v["s"]]
    best = None
    for k, rx in RE_ANCORE:
        for m in rx.finditer(pre):
            if best is None or m.start() > best[0]:
                best = (m.start(), k)
    return best[1] if best else None


def _u_ca_800(c: Ctx, intr: dict, ex: dict, grupuri: list):
    """r7 (P0-3): invertoarele de 800 V c.a. (fără N: SG250HX, SUN2000-330KTL-H1 …) → `U_inv_ca_V` 800 și `U_JT_V` 800
    (trafo 20/0,8 kV); racordul lor într-un TG / BMPT de 0,4 kV = contradicție → întrebare (I08)."""
    mod = ", ".join(dict.fromkeys(g.get("model") or "" for g in grupuri))
    alte = [g for g in getattr(c, "_grupuri_pv", []) if g.get("U_ca_V") != 800]
    if alte:                                                # r8 (P1 fotovoltaic #25): 800 V și 400 V pe același trafo
        mod4 = ", ".join(dict.fromkeys(g.get("model") or f"{fmt(g['Pn_kW'])} kW" for g in alte))
        c.intrebari.append(("I08", f"{mod} are ieșirea la 800 V c.a., iar {mod4} la 400 V: pe un singur trafo nu se pot lega "
                                   "ambele. Trafo cu două înfășurări JT / două trafo (20/0,8 și 20/0,4 kV), sau alt model "
                                   "pentru una din grupe?"))
    intr["U_inv_ca_V"] = ex["U_inv_ca_V"] = 800
    intr["U_ca_V"] = 800                                    # cheia motorului (alias U_inv_ca_V)
    m08 = re.search(rf"\b\d+(?:[.,]\d+)?\s*/\s*0[.,]8\s*kv\b|\b0[.,]8\s*kv\b|\b800\s*v\b(?!\s*c\.?c)", c.t)
    m04 = re.search(rf"\b\d+(?:[.,]\d+)?\s*/\s*0[.,]4\s*kv\b|\b400\s*v\b|\b0[.,]4\s*kv\b", c.t)
    if m08:
        c.foloseste(m08.start(), m08.end())
    if (intr.get("racord") in ("tg_existent", "bmpt") or m04) and not m08:
        if m04:
            c.foloseste(m04.start(), m04.end())
        c.probleme.append(("I08", f"Contradicție: {mod} are ieșirea 800 V c.a. (3 faze, fără N), dar racordul e la 0,4 kV "
                                  f"(I08).", f"Invertoarele {mod} (800 V c.a.) se racordează doar printr-un trafo "
                                             "0,8/20 kV (PT nou) — generez cu PT 20/0,8 kV, sau folosiți invertoare de "
                                             "400 V?"))
        return
    intr["U_JT_V"] = ex["U_JT_V"] = 800
    c.nota(f"{mod}: ieșire 800 V c.a. (3 faze, fără N) → bara JT a PT-ului la 800 V, trafo 20/0,8 kV"
           + ("" if m08 else " (din modelul invertorului)") + "; cabluri 3 faze + PE, aparate 3P pentru 800 V, c.c. 1500 V")


def _circuite_casa_pv(c: Ctx, intr: dict):
    """r7 (locuințe #61): „casă … pompă de căldură 9 kW, fotovoltaice 10 kW” — receptoarele casei NU sunt invertoare și
    nici nu se pierd: `circuite_casa` [{nume, receptor, P_kW}] + întrebare I14 (circuitele casei = schema „locuință”)."""
    t = c.mascat()
    if not RE_CASA_TARE.search(_masca(c.t, RE_NU_CASA)):
        return                                             # fără casă numită: receptorul rămâne la plasa de siguranță
    gas = [g for g in _gaseste_receptori(t) if not g["exclus"] and g["P"] is not None
           and not re.search(r"\bbackup\b|\beps\b|\brezerv", t[max(0, g["s"] - 30):g["s"]])
           and not (g["receptor"] == "aer_conditionat" and re.search(r"bater\w*|cupl\w*|coupled|\bdc\b",
                                                                    t[max(0, g["s"] - 15):g["e"] + 12]))]
    if not gas:
        return
    circ = []
    for g in gas:
        c.consumat.append((g["s_tot"], g["coada_e"]))
        circ.append(_circuit_loc(g["nume"] or nume_normalizat(c.o(g["s"], g["e"])), g["receptor"], g["P"]))
    intr["circuite_casa"] = circ
    desc = ", ".join(f"{x['nume']} {fmt(x['P_kW'])} kW" for x in circ)
    c.intrebari.append(("I14", f"Textul descrie și receptoarele casei ({desc}). Desenez prosumatorul (invertorul racordat "
                               "în tabloul casei); circuitele casei se generează ca schemă „locuință” separată — de acord?"))


RE_BACKUP = re.compile(r"\b(?:backup|back-up|eps|iesire\w*\s+de\s+rezerva|alimentare\w*\s+de\s+rezerva)\b"
                       r"(?:\s*\(\s*eps\s*\))?(?:\s+(?:pe|pentru|la))?(?:\s+(?:circuitele|circuitul|circuite|consumatorii|tabloul))?\s*:?\s*")


def _backup_pv(c: Ctx, intr: dict):
    """r7 (locuințe #59): „backup pe circuitele frigider și centrală” = ieșirea de rezervă (EPS / backup) a invertorului
    hibrid cu tabloul ei → `backup` {circuite: [{nume, receptor}]} (cheie nouă — motorul o desenează ca tablou rezervat).
    r8 (#50): lista continuă peste virgule cât timp elementele sunt receptoare („frigider, centrală și iluminat”)."""
    t = c.mascat()
    mt = re.search(r"\b(?:eps|backup|back-up)\b[^.;]{0,30}?\b(?:total|toata\s+casa|intreaga\s+casa|pe\s+toata\s+(?:casa|instalatia))\b"
                   r"|\b(?:toata\s+casa|intreaga\s+casa|toata\s+instalatia)\s+(?:pe|in)\s+(?:backup|eps|regim\s+insular)", t)
    if mt:
        # r10 (locuințe #27): EPS / backup pe TOATĂ casa — comutare (ATS) a întregului TG pe ieșirea de backup, N comutat,
        # legătura N-PE în regim insular (motorul o desenează)
        b = {"toata_casa": True, "comutare": "ATS" if re.search(r"automat\w*|\bats\b", c.t) else "manual"}
        if re.search(r"\bn\s+comutat\b|\bneutru\w*\s+comutat\w*|\b4p\b", c.t):
            b["N_comutat"] = True
        intr["backup"] = b
        for mm in re.finditer(r"\b(?:eps\s*/\s*)?(?:eps|backup)\b[^,;.]{0,30}|\bcomutare\s+automat\w*[^,;.]{0,40}|\bn\s+comutat\b", c.t):
            c.foloseste(mm.start(), mm.end())
        c.nota("EPS / backup pe toată casa: ATS (comutare automată) al întregului tablou pe ieșirea de backup a invertorului "
               "hibrid" + (", neutrul comutat (4P)" if b.get("N_comutat") else "") + "; în regim insular legătura N-PE se face "
               "în invertor / ATS (backup.toata_casa)")
        return
    m = RE_BACKUP.search(t)
    if not m:
        return
    circ, poz, capat = [], m.end(), m.end()
    for mm in re.finditer(r"(?:[^,;.]|(?<=\d)[.,](?=\d))+", t[m.end():]):
        bucata = mm.group(0)
        if mm.start() > 0 and t[m.end() + mm.start() - 1] in ";.":
            break
        gata = False
        for x in re.split(r"\s+si\s+", bucata):
            xs = x.strip()
            if not xs:
                continue
            g = next((g for g in _gaseste_receptori(xs)), None)
            if not g and re.fullmatch(r"[a-z][a-z\- ]{2,24}", xs) and len(xs.split()) <= 3 and circ \
                    and not re.search(r"\b(?:tn|tt|schema|tablou|bransament|retea|invertor|baterie)\w*", xs):
                g = {"nume": None, "receptor": "alt_circuit"}       # r10 (#66): „router”, „pompă puț” — circuit dedicat
            if not g or re.search(r"\d", xs):
                gata = True
                break
            i = c.t.find(xs, poz)
            circ.append({"nume": g["nume"] or nume_normalizat(c.o(i, i + len(xs)) if i >= 0 else xs), "receptor": g["receptor"]})
            capat = m.end() + mm.start() + bucata.find(xs) + len(xs)
        if gata:
            break
    if not circ:
        return
    c.consumat.append((m.start(), capat))
    intr["backup"] = {"circuite": circ}
    c.nota(f"„{c.o(m.start(), capat).strip()}” = ieșirea de rezervă (backup / EPS) a invertorului hibrid → tablou rezervat "
           "cu: " + ", ".join(x["nume"] for x in circ) + " (comutare automată în invertor)")


RE_P_APROBAT = re.compile(
    rf"(?:\bpa\b|\bp\s*aprobat\w*|paprobat\w*|putere\w*\s+aprobat\w*|\baprobat\w*)\s*(?:de\s+|=\s*|:\s*)?"
    rf"(?P<v>{NUM})\s*(?P<u>kw|mw)\b|(?P<v2>{NUM})\s*(?:kw)\s+aprobat\w*")
RE_P_EVACUAT = re.compile(rf"\b(?:p\s*)?evacuat\w*\s*(?:de\s+|=\s*|:\s*)?(?P<v>{NUM})\s*(?P<u>kw|mw)\b"
                          rf"|\bputere\w*\s+aprobat\w*\s+(?:de\s+|la\s+|pentru\s+)?(?:injectare|injectie|evacuare|livrare)\w*"
                          rf"\s*(?:de\s+)?(?P<v3>{NUM})\s*(?P<u3>kw|mw)\b"
                          rf"|\bputere\w*\s+evacuat\w*\s*(?:de\s+)?(?P<v2>{NUM})\s*kw")
# r8 (locuințe #10): „pa 6” (mesaj scurt, fără unitate) = P aprobată 6 kW
RE_PA_FARA_U = re.compile(rf"\bpa\s*(?:=|:)?\s*(?P<v>{NUM})\b(?!\s*(?:kw|kva|mw|a|v|m|ka|%|ohm|ω|kwh|kwp)\b)(?![.,]\d)")
RE_P_CASA = re.compile(
rf"\b(?:casa|casei|locuint\w*|apartament\w*|consum\w*)(?:\s+(?:mono\w*|tri\w*|noua|nou|existent\w*|de|cu"
                       rf"|are|1f|3f|consum\w*|absorbit\w*)){{0,3}}\s+(?P<v>{NUM})\s*(?P<u>kw|mw)\b")
RE_P_BRANS = re.compile(rf"\b(?:bransament\w*|bmp[mt]\w*)(?:\s+(?:mono\w*|tri\w*|nou|existent|de)){{0,3}}\s+(?P<v>{NUM})"
                        rf"\s*(?P<u>kw|mw)\b")
RE_Q_RACORD = re.compile(rf"\b(?:q(?:[a-z]\w*)?|intrerupator\w*|disjunctor\w*)\s*(?:tg\s*|general\s*|bransament\w*\s*)?(?:=|de|:)?\s*"
                         rf"(?P<v>{NUM})\s*a\b|\bbmp[tm]\w*(?:\s+(?:existent\w*|pe\s+soclu|trifaz\w*|monofaz\w*|tri|mono|nou|de))*\s+"
                         rf"(?:[13]\s*×\s*)?(?P<v2>{NUM})\s*a\b"
                         rf"|\b(?:cas(?:a|ei)|bransament\w*)(?:\s+(?:trifaz\w*|tri|existent\w*|are|e|este|de))*\s+3\s*×\s*(?P<v4>{NUM})\s*a\b"
                         rf"|\b(?:tg|tablou\w*)(?:\s+(?!plecari|cu\b|td|si\b)[a-z]+){{0,2}}\s+(?P<v3>{NUM})\s*a\b")


RE_RACORD_TG = re.compile(r"\b(?:tg\d*|tgd\d*|tg-\w+|tablou(?:l)?(?:\s+general)?)\s+existent\w*|\b(?:in|la)\s+(?:tg\d*|tablou\w*)\b"
                          r"|racord\w*\s+(?:in|la)\s+(?:tg|tgd|tablou)"
                          r"|\b(?:are|cu)\s+(?:un\s+)?(?:tg\d*|tgd\d*)\s+alimentat\w*\s+din\b")   # r9 (#35): „hala are TG alimentat din PT”
RE_RACORD_BMPT = re.compile(r"\bbmpt\w*|\bbransament\w*")


_N_TRAFO = r"(?P<n>\d|doua|doi|trei|patru)"
RE_TRAFO_N = [
    re.compile(rf"\b{_N_TRAFO}\s*(?:[x×]\s*)?(?:transformatoare|transformator|trafo|trafuri)\b(?:\s+(?:de|cate|uscat\w*|in\s+ulei"
               rf"|ulei|noi|nou|existent\w*))*\s+(?P<sn>{NUM})\s*kva\b"),
    re.compile(rf"\b(?:pt|post\w*(?:\s+(?:de\s+)?(?:transformare|trafo))?)(?:\s+(?:nou|existent\w*|propriu|cu|de|in|zidit|beton"
               rf"|anvelopa|metalic\w*)){{0,4}}\s+{_N_TRAFO}\s*[x×]\s*(?P<sn>{NUM})\s*kva\b"),
    re.compile(rf"(?<![\w.,]){_N_TRAFO}\s*[x×]\s*(?P<sn>{NUM})\s*kva\b"),
]


def _trafo_pv(c: Ctx, intr: dict, ex: dict):
    """r7 (fotovoltaic P0-2): numărul de transformatoare la CEF / BESS — „2 trafo 1000 kVA”, „2 transformatoare 1250
    kVA”, „PT nou 2 x 630 kVA”, „4 trafo 1600 kVA” → `n_trafo` + `pt_Sn_kVA` (Sn al fiecăruia). Motorul PT acceptă 1–2;
    peste 2 → cheia se transmite, iar verificarea Sn se face pe n × Sn."""
    t = c.mascat()
    for rx in RE_TRAFO_N:
        m = rx.search(t)
        if not m:
            continue
        n = _NUMERAL.get(m.group("n")) or int(m.group("n"))
        if n < 2:
            continue
        sn = numar(m.group("sn"))
        intr["n_trafo"] = ex["n_trafo"] = n
        intr["pt_Sn_kVA"] = _nr(sn)
        c.consumat.append((m.start(), m.end()))
        cl = c.t[max(0, m.start() - 40):m.end() + 40]
        if re.search(r"\bnou\b|\bnoi\b", cl) or re.search(r"\b(?:pt|post\w*)\s+nou\b", c.t):
            intr["pt_existent"] = ex["pt_existent"] = False
        elif re.search(r"existent", cl):
            intr["pt_existent"] = ex["pt_existent"] = True
        for mm in re.finditer(r"\b(?:pt|post\w*)\b(?:\s+(?:nou|existent\w*|in\s+anvelopa(?:\s+de\s+beton)?|zidit|de\s+transformare))*", c.t):
            c.foloseste(mm.start(), mm.end())
        c.nota(f"„{c.o(m.start(), m.end()).strip()}” = {n} transformatoare de {fmt(sn)} kVA (n_trafo = {n}; Sn total "
               f"{fmt(n * sn)} kVA)" + ("" if n <= 2 else " — motorul desenează azi cel mult 2 trafo pe un PT: verificați "
                                                          "împărțirea invertoarelor pe posturi"))
        return


def _masura_pv(c: Ctx, intr: dict, ex: dict):
    """r7 (fotovoltaic #65): „măsura pe MT în celula de măsură” → `masura` MT (ca la PT); „măsura pe JT” → JT."""
    m = re.search(r"\bmasur\w*\s+(?:pe\s+|in\s+|de\s+|la\s+)?(?:mt|medie\s+tensiune)\b(?:\s+in\s+celul\w*\s+(?:de\s+)?masur\w*)?"
                  r"|\bcelul\w*\s+(?:de\s+)?masur\w*", c.t)
    mj = re.search(r"\bmasur\w*\s+(?:pe\s+|in\s+|de\s+|la\s+)?(?:jt|joasa\s+tensiune)\b", c.t)
    if m:
        intr["masura"] = ex["masura"] = "MT"
        c.foloseste(m.start(), m.end())
    elif mj:
        intr["masura"] = ex["masura"] = "JT"
        c.foloseste(mj.start(), mj.end())


def _racord_pv(c: Ctx, intr: dict, ex: dict, tip: str):
    """unde se leagă CEF-ul / prosumatorul: TG existent, BMPT, PT (r5 P1-9): atribut, nu tip de schemă.
    r6 (f08): „cablu … până la TGD” NU e racord în TG existent (TGD-CF e tabloul centralei); (f47) „în TG existent și
    prin BMPT nou” = două racorduri → I08."""
    t = c.t
    mtg = RE_RACORD_TG.search(t) or ("tablou" in getattr(c, "combo", []) and re.search(r"\btg\b|tablou", t))
    mb = RE_RACORD_BMPT.search(t)
    if mtg and mb and re.search(r"\bsi\b|\bsau\b|\+", t[min(mtg.end(), mb.end()):max(mtg.start(), mb.start())]):
        c.foloseste(min(mtg.start(), mb.start()), max(mtg.end(), mb.end()))
        c.probleme.append(("I08", f"Contradicție: două puncte de racord („{c.o(mtg.start(), mtg.end()).strip()}” și "
                                  f"„{c.o(mb.start(), mb.end()).strip()}”) (I08).",
                           "Centrala se racordează în TG-ul existent sau printr-un BMPT nou (branșament separat)?"))
    if mtg:
        ex["racord"] = intr["racord"] = "tg_existent"
        c.foloseste(mtg.start(), mtg.end())
        c.nota("racord în tabloul existent (TG) — protecția din TG și Ik3 la bara TG se completează în Calcul, altfel "
               "se iau ca la punctul de racord")
    elif mb:
        ex["racord"] = intr["racord"] = "bmpt"
        c.foloseste(mb.start(), mb.end())
    elif tip == "cef" and re.search(r"\btg\b", t) and not re.search(r"\b(?:pt|post\w*)\b|\btrafo\b", t):
        ex["racord"] = intr["racord"] = "tg_existent"              # r7 (#61): „solar 10 kw … TG” = racord în TG
        mm = re.search(r"\btg\b", t)
        c.foloseste(mm.start(), mm.end())
    mpt = re.search(r"(?:pana\s+la|in|din|racord\w*\s+(?:in|la))\s+(?:celula\s+jt\s+a\s+)?(?:pt|pt-ului|postul\w*)\b"
                    r"(?P<ex>\s+existent\w*)?(?P<nou>\s+nou\b)?", t)
    if mpt and tip == "cef":
        if mtg and (mpt.group("nou") or re.search(r"\bsi\s+(?:in\s+)?$", t[max(0, mpt.start() - 8):mpt.start() + 3])):
            c.probleme.append(("I08", f"Contradicție: două puncte de racord („{c.o(mtg.start(), mtg.end()).strip()}” și "
                                      f"„{c.o(mpt.start(), mpt.end()).strip()}”) (I08).",
                               "Centrala se racordează în TG-ul existent sau într-un PT (nou / existent)? Un singur punct de "
                               "racord pe schemă."))
        elif not mtg:
            ex["racord"] = intr["racord"] = "pt"
            if mpt.group("ex"):
                intr["pt_existent"] = ex["pt_existent"] = True
        c.foloseste(mpt.start(), mpt.end())
    mn = re.search(r"\bnu\s+stiu\s+(?:puterea|sn|cat\w*)(?:\s+(?:trafo\w*|transformator\w*|pt|postului))?", t)
    if mn:
        c.foloseste(mn.start(), mn.end())


def _lungimi_pv(c: Ctx, intr, tip):
    t = c.mascat()
    if tip == "prosumator":
        m = (re.search(rf"coloan\w*\s*(?:de\s+)?(?:(?:≈|cca\.?|circa|aprox\.?)\s*)?(?P<v>{NUM})\s*(?P<u>m|metri|ml|km)\b", t)
             or re.search(rf"(?P<v>{NUM})\s*(?P<u>m|metri|ml|km)\s+(?:coloan\w*|pana\s+la\s+(?:bmp\w*|tablou|firida))", t))
        if m:
            intr["L_coloana_m"] = _nr(numar(m.group("v")) * UNITATI[m.group("u")][1])
            c.consumat.append((m.start(), m.end()))
            c.nota(f"„{c.o(m.start(), m.end()).strip()}” = coloana BMPT/BMPM → tabloul consumatorului")
        L = _lungime_generala(valori(c.mascat()))
        if L:
            intr["L_inv_m"] = _nr(L["val"])
            c.nota(f"„{c.o(L['s_aprox'] or L['s'], L['e']).strip()}” = cablul invertorului (invertor → tablou)")
        return
    L = _lungime_generala(valori(t))
    if L:
        intr["L_racord_m"] = _nr(L["val"])
        c.nota(f"cablul descris („{c.o(L['s_aprox'] or L['s'], L['e']).strip()}” = {fmt(L['val'])} m) = C0, de la "
               "TGD-CF la " + ("tabloul existent" if intr.get("racord") == "tg_existent" else "punctul de racord"))


_ATR_P = r"\b(?:puterea?|pmax|p\s*max\w*|p)\b"
RE_ATR_EVAC = re.compile(rf"{_ATR_P}[^,;:.]{{0,40}}?(?:evacuar\w*|evacuat\w*|injectar\w*|injectat\w*|livrar\w*"
                         rf"|loc(?:ul)?\s+de\s+producere)[^,;.0-9]{{0,30}}?(?:=|:)?\s*(?P<v>{NUM})\s*(?P<u>kw|mw)\b")
RE_ATR_ABS = re.compile(rf"{_ATR_P}[^,;:.]{{0,40}}?(?:absorbit\w*|\bconsum\b|pentru\s+consum|loc(?:ul)?\s+de\s+consum)"
                        rf"[^,;.0-9]{{0,30}}?(?:=|:)?\s*(?P<v>{NUM})\s*(?P<u>kw|mw)\b")


def _atr_pv(c: Ctx, intr: dict, puteri: dict):
    """r8 (fotovoltaic #1, #15, #16, #56; locuințe #22, #24): vocabularul ATR — „puterea aprobată pentru evacuare /
    maximă (simultan) evacuată / loc de producere X kW” = `P_evacuata_kW` (limitare dacă < invertoare, 0 = injecție zero);
    „puterea aprobată pentru consum / maximă simultan absorbită / loc de consum Y kW” = `P_aprobata_kW` (consumul) —
    niciuna nu e puterea totală a centralei. Întoarce P evacuată sau None."""
    p_evac = None
    t = c.mascat()
    m = RE_ATR_EVAC.search(t)
    if m:
        p_evac = numar(m.group("v")) * UNITATI[m.group("u")][1]
        intr["P_evacuata_kW"] = puteri["P_evacuata_kW"] = _nr(p_evac)
        c.consumat.append((m.start(), m.end()))
        c.nota(f"„{c.o(m.start(), m.end()).strip()}” = puterea aprobată de evacuare din ATR (P_evacuata_kW)")
    t = c.mascat()
    m = RE_ATR_ABS.search(t)
    if m:
        v = numar(m.group("v")) * UNITATI[m.group("u")][1]
        intr.setdefault("P_aprobata_kW", _nr(v))
        puteri.setdefault("P_aprobata_kW", _nr(v))
        c.consumat.append((m.start(), m.end()))
        c.nota(f"„{c.o(m.start(), m.end()).strip()}” = puterea aprobată pentru consum (ATR) — nu e puterea centralei")
    return p_evac


# r10 (fotovoltaic P0 #43, P1 #9, #56): „Avem deja 20 kW (Symo …). Adaug 1 x SUN2000-30KTL-M3”, „invertoare existente
# 3 x 33 kW, nu se modifică; nou: BESS …” — grupul EXISTENT e marcat (`existent: true`), cel nou rămâne nou; niciunul nu
# se pierde. „TG / PT / BMPT existent” (racordul) nu face invertoarele existente.
RE_EXIST_CTX = re.compile(r"\bdeja\b|\bexistent\w*|\bexista\b|\bavem\s+(?=\d)|\bnu\s+se\s+(?:modific|inlocuies|schimb)\w*|\b(?:sunt|e|este)\s+montat\w*"
                          r"|\bin\s+functiune\b|\bactual\w*\b")
RE_NOU_CTX = re.compile(r"\badaug\w*|\bse\s+adauga\b|\bnou[aă]?\b|\bnoi\b|\bse\s+monteaz\w*|\bmontam\b|\bsuplimentar\w*"
                        r"|\bextinder\w*|\binstalam\b|\bvrem\s+(?:sa\s+)?(?:adaug|punem|montam)\w*|\bproiectat\w*")
RE_EXIST_NU_INV = re.compile(r"\b(?:tg\w*|tgd|tablou\w*(?:\s+general)?|pt\w*|post\w*|bmp[tm]\w*|racord\w*|board|mdb|bransament\w*"
                             r"|trafo\w*|cablu\w*|celul\w*)(?:-ul)?\s+existent\w*|\bexistent\w*\s+(?:tg|tablou|pt|bmpt)\b")


def _e_existent(c: Ctx, s: int, e: int) -> bool:
    t = _masca(c.t, RE_EXIST_NU_INV)
    a = max([m.end() for m in re.finditer(r"(?<!\d)\.(?=\s)|;|\n", t) if m.end() <= s + 1] or [0])
    b = next((m.start() for m in re.finditer(r"(?<!\d)\.(?=\s|$)|;|\n", t[e:])), len(t) - e) + e
    pre, post = t[a:e], t[e:min(b, e + 30)]
    ex_ = [m.end() for m in RE_EXIST_CTX.finditer(pre)]
    nou = [m.end() for m in RE_NOU_CTX.finditer(pre)]
    if ex_ and (not nou or max(ex_) > max(nou)):
        return True
    return bool(re.match(r"\s*\(?\s*(?:existent\w*|deja\s+montat\w*|montat\w*\b(?!\s+nou))", post)) and not nou


RE_PLECARE_PT = re.compile(rf"\bplecare\w*\s+(?:noua\s+)?(?:din\s+)?[^,;.]{{0,40}}?\b(?:cu\s+)?(?P<ap>intreruptor\w*|disjunctor\w*"
                           rf"|mccb|acb|sigurant\w*(?:\s+(?:fuzibil\w*|mpr|mpr\w*|gg|nh))*|mpr|separator\w*(?:\s+fuzibil\w*)?)"
                           rf"\s+(?:de\s+)?(?P<v>{NUM})\s*a\b")
RE_BARA_T = re.compile(r"\bbar(?:a|ei|ele)\s+(?:de\s+)?(?:jt\s+)?(?:a\s+)?(?:lui\s+)?(?:trafo\w*\s+)?(?P<t>t\s*[1-4])\b"
                       r"|\b(?:secti\w*|semibar\w*)\s+(?:jt\s+)?(?:a\s+)?(?P<t2>t\s*[1-4])\b")


def _plecare_pt_pv(c: Ctx, intr: dict):
    """r10 (fotovoltaic #15, #64): racordul CEF într-un PT existent — „plecare nouă din TDRI cu întreruptor 630 A” /
    „… cu siguranțe MPR 250 A” = protecția plecării din tabloul JT al PT-ului (`racord_In_Q_A`, `racord_Q_tip`);
    „bara JT a T1” = secția de bare pe care se racordează (`bara`, Ik doar din T1 cu cupla deschisă)."""
    m = RE_PLECARE_PT.search(c.mascat())
    if m:
        ap = m.group("ap")
        intr["racord_In_Q_A"] = _nr(numar(m.group("v")))
        intr["racord_Q_tip"] = "gG" if re.match(r"sigurant|mpr|separator", ap) else ("ACB" if ap == "acb" else "MCCB")
        c.consumat.append((m.start(), m.end()))
        c.nota(f"„{c.o(m.start(), m.end()).strip()}” = protecția plecării de racord din tabloul JT existent "
               f"({intr['racord_Q_tip']} {fmt(intr['racord_In_Q_A'])} A)")
    m = RE_BARA_T.search(c.t)
    if m:
        intr["bara"] = (m.group("t") or m.group("t2")).upper().replace(" ", "")
        c.foloseste(m.start(), m.end())
        c.nota(f"„{c.o(m.start(), m.end()).strip()}” = racord pe secția de bare a {intr['bara']} (Ik3 din acest trafo, "
               "cupla deschisă)")


def extrage_pv(c: Ctx, intr: dict, ex: dict, tip: str) -> dict:

    """CEF și prosumator (r5): modele, grupuri de invertoare, BESS, module, stringuri, limitare, racord, ATR."""
    puteri = {}
    modele = _modele(c, c.t)
    for x in modele:                                              # codurile de model nu sunt valori
        c.consumat.append((x["s"], x["e"]))
    bess = extrage_bess(c, modele)
    lim = extrage_limitare(c)
    if lim is not None:
        intr["limitare_injectie_kW"] = puteri["limitare_injectie_kW"] = lim
    p_evac = _atr_pv(c, intr, puteri)                              # r8: puterile din ATR (evacuare / absorbită)
    r = _valoare_lipita(c, re.compile(rf"\btotal\w*\s*(?:de\s+|=\s*|:\s*)?(?P<v>{NUM})\s*(?P<u>kw|mw)\b"))
    total = r[0] if r else None
    if tip == "prosumator":
        r = _valoare_lipita(c, RE_P_EVACUAT)
        if r:
            intr["P_evacuata_kW"] = puteri["P_evacuata_kW"] = _nr(r[0])
            c.nota(f"„{c.o(r[1].start(), r[1].end()).strip()}” = puterea aprobată de evacuare (injecție) din ATR")
        # r7: „pa / aprobat / branșament / casa X kW” = puterea aprobată (consumul casei), NU invertorul
        r = _valoare_lipita(c, RE_P_APROBAT) or _valoare_lipita(c, RE_P_BRANS) or _valoare_lipita(c, RE_P_CASA) \
            or _valoare_lipita(c, RE_PA_FARA_U)
        if r and r[1].re is RE_PA_FARA_U:
            c.nota(f"„{c.o(r[1].start(), r[1].end()).strip()}” fără unitate = P aprobată {fmt(r[0])} kW (presupus)")
        if r:
            intr["P_aprobata_kW"] = puteri["P_aprobata_kW"] = _nr(r[0])
            if re.match(r"cas|locuint|apartament", r[1].group(0)):
                c.nota(f"„{c.o(r[1].start(), r[1].end()).strip()}” = puterea casei (consum) = P aprobată a branșamentului "
                       "(nu puterea invertorului)")
        _circuite_casa_pv(c, intr)
        _backup_pv(c, intr)
        if lim == 0 and intr.get("P_evacuata_kW"):          # r7 (#20): injecție zero vs P evacuată aprobată > 0
            c.probleme.append(("I08", f"Contradicție: „injecție zero” și puterea aprobată de evacuare "
                                      f"{fmt(intr['P_evacuata_kW'])} kW din ATR (I08).",
                               f"Instalația injectează în rețea până la {fmt(intr['P_evacuata_kW'])} kW (conform ATR), sau "
                               "funcționează cu injecție zero (limitare la 0 kW, analizor la punctul de racord)?"))
    # racordul + datele TG / BMPT
    _racord_pv(c, intr, ex, tip)
    r = _valoare_lipita(c, RE_Q_RACORD)
    if r:
        k = "In_Q_bransament_A" if (tip == "prosumator" or intr.get("racord") == "bmpt") else "racord_In_Q_A"
        intr[k] = _nr(r[0])
    m = RE_IK.search(c.mascat())
    if m:
        c.consumat.append((m.start(), m.end()))
        # r8 (locuințe #22): la racordul prin BMPT / la prosumator, Ik din ATR e al rețelei OD (la BMPT), nu la bara unui TG
        k_ik = "Ik3_OD_kA" if (tip == "prosumator" or intr.get("racord") == "bmpt") and \
            not re.search(r"\bbar[aei]\b|\btg\b", c.t[m.start():m.end() + 12]) else "Ik3_TG_kA"
        intr[k_ik] = _nr(numar(m.group("v")))
    _plecare_pt_pv(c, intr)                                        # r10: „plecare nouă … cu întreruptor 630 A”, „bara T1”
    _trafo_pv(c, intr, ex)                                         # r7: „2 trafo 1000 kVA”, „PT nou 2 x 630 kVA”
    _masura_pv(c, intr, ex)
    # PT: propriu nou sau existent (sursa TG-ului)
    for v in valori(c.mascat()):
        if v["marime"] == "kVA" and _proprietar_kva(c, v) == "pt":
            intr["pt_Sn_kVA"] = _nr(v["val"])
            c.consumat.append((v["s"], v["e"]))
            fer = c.t[max(0, v["s"] - 30):v["s"]] + " " + c.t[v["e"]:v["e"] + 30]
            fer = re.split(r"[,;]", c.t[max(0, v["s"] - 30):v["s"]])[-1] + " " + re.split(r"[,;]", c.t[v["e"]:v["e"] + 30])[0]
            # r6 (f06, f23, f28, f33): „PT existent”, „PT … al beneficiarului / al OD” = existent; „PT nou” = nou
            if re.search(r"\bnou\b", fer):
                intr["pt_existent"] = ex["pt_existent"] = False
                c.nota(f"PT {fmt(v['val'])} kVA NOU (se desenează trafo-ul și celula MT)")
            elif re.search(r"existent|\bal\s+(?:beneficiar\w*|od|fabricii|clientului)\b|\bod\b|" + _OD_NUME, fer):
                intr["pt_existent"] = ex["pt_existent"] = True
                od = bool(re.search(r"\bod\b|" + _OD_NUME, fer))
                if od and intr.get("racord") == "tg_existent":
                    # r10 (fotovoltaic #46): „TG existent alimentat dintr-un PT al Electrica (nu e al nostru)” — PT-ul OD
                    # e doar informativ (sursa TG-ului), nu PT propriu și nici punctul de racord al CEF
                    intr["pt_od"] = True
                    od = False
                if od:
                    ex["atr_jt"] = intr["atr_jt"] = True
                c.nota(f"PT {fmt(v['val'])} kVA EXISTENT" + (" al OD (racord JT în celula JT a PT-ului, conform ATR)"
                                                              if od else "") + " = sursa (nu se desenează trafo nou)")
            for mm in re.finditer(r"\b(?:pt|pt-ului|post\w*)\b[^,;]{0,40}", c.t):
                c.foloseste(mm.start(), mm.end())
            break
    if re.search(r"racord\s+jt\s+(?:conform|cf\.?)\s+atr|\bjt\s+(?:conform|cf\.?)\s+atr", c.t):
        ex["atr_jt"] = intr["atr_jt"] = True
    if tip == "cef" and not intr.get("racord") and not intr.get("pt_Sn_kVA") and "pt_existent" not in intr \
            and not re.search(r"\bpt\b|\bpost\w*|\btrafo\w*|\btransformator\w*|\bmt\b|\bmedie\b|\bcelul\w*|\bracord\w*"
                              r"|\batr\b", c.t):
        # r9 (fotovoltaic #59, #60): racordul (TG / BMPT / PT) schimbă radical schema — nu se presupune tăcut: peste
        # 100 kW se întreabă; până la 100 kW se generează prin BMPT cu avertisment vizibil („Am presupus”)
        sig_ = sum((g.get("n") or 1) * (g.get("Pn_kW") or 0) for g in intr.get("invertoare") or [])
        txt_r = ("Unde se racordează centrala: în TG-ul existent, printr-un BMPT nou (branșament) sau într-un PT (nou / "
                 "existent)? Până la răspuns e desenată prin BMPT (presupus).")
        if sig_ > P_SURSA_INTREBATA_KW:
            c.intrebari.append(("I07", txt_r))
        else:
            c.avert.append("Am presupus racordul prin BMPT (nedeclarat): " + txt_r)
    extrage_module_string(c, modele, intr)
    kwp = _prima(valori(c.mascat()), "kWp")
    if not kwp:                    # r8 (#27): „120 kw panouri” = puterea de vârf a modulelor (kWp), nu puterea c.a.
        mkp = re.search(rf"(?<![\w.,])(?P<v>{NUM})\s*kw\s+(?:de\s+)?(?:panouri|module|fotovoltaic\w*|pv|c\.?c\.?)\b", c.mascat())
        if mkp:
            kwp = {"val": numar(mkp.group("v")), "s": mkp.start(), "e": mkp.end()}
            c.nota(f"„{c.o(mkp.start(), mkp.end()).strip()}” = puterea modulelor ({fmt(kwp['val'])} kWp), nu puterea c.a.")
    if kwp:
        mxk = re.search(r"(?<![\w.,])(\d+)\s*×\s*$", c.t[max(0, kwp["s"] - 6):kwp["s"]])
        if mxk and int(mxk.group(1)) > 1:                       # r8 (#51): „2 x 50 kWp” = 100 kWp
            n_k = int(mxk.group(1))
            c.nota(f"„{c.o(max(0, kwp['s'] - 6) + mxk.start(), kwp['e']).strip()}” = {n_k} × {fmt(kwp['val'])} = "
                   f"{fmt(n_k * kwp['val'])} kWp")
            kwp = dict(kwp, val=n_k * kwp["val"], s=max(0, kwp["s"] - 6) + mxk.start())
        puteri["kWp"] = intr["kWp"] = _nr(kwp["val"])
        c.consumat.append((kwp["s"], kwp["e"]))

    elif getattr(c, "_n_module_tot", None) and (intr.get("modul") or {}).get("Pmax_W"):
        # r7 (#1): 40 module × 500 W = 20 kWp (raportul c.c./c.a. se poate verifica)
        v = c._n_module_tot * intr["modul"]["Pmax_W"] / 1000
        puteri["kWp"] = intr["kWp"] = _nr(round(v, 2))
        kwp = {"val": v}
        c.nota(f"P c.c. = {c._n_module_tot} module × {fmt(intr['modul']['Pmax_W'])} W = {fmt(v, 2)} kWp (calculat)")
    elif (intr.get("string") or {}).get("n_module") and (intr.get("string") or {}).get("n_stringuri_paralel"):
        # r11 (fotovoltaic #24): „12 stringuri a câte 20 module 455 Wp” → 240 module × Pmax = kWp; fără Pmax → întrebare
        st_ = intr["string"]
        n_tot = st_["n_module"] * st_["n_stringuri_paralel"] * (st_.get("n_MPPT") or 1 if re.search(r"\bpe\s+mppt", c.t) else 1)
        if (intr.get("modul") or {}).get("Pmax_W"):
            v = n_tot * intr["modul"]["Pmax_W"] / 1000
            puteri["kWp"] = intr["kWp"] = _nr(round(v, 2))
            kwp = {"val": v}
            c.nota(f"P c.c. = {st_['n_stringuri_paralel']} stringuri × {st_['n_module']} module = {n_tot} module × "
                   f"{fmt(intr['modul']['Pmax_W'])} W = {fmt(v, 2)} kWp (calculat; stringurile = totalul centralei)")
        else:
            c.intrebari.append(("I02", f"{st_['n_stringuri_paralel']} stringuri × {st_['n_module']} module = {n_tot} module: ce "
                                       "putere are un modul (Wp)? (kWp nu se presupune)"))
    grupuri = grupuri_invertoare(c, modele)
    if not grupuri:
        g = _pv_legat(c, tip)                                      # r7: „pv 6 kW”, „solar 10 kw”, „50 kW fotovoltaic”
        if g:
            grupuri = [g]
    vals = valori(c.mascat())
    # puterea declarată a instalației („prosumator 100 kW”, „CEF 50 kW”) = total, nu un invertor în plus
    rest_kw = [v for v in vals if v["marime"] == "kW"]
    if tip == "prosumator" and not grupuri:
        casa = RE_CASA_TARE.search(c.t)
        pv2 = [v for v in rest_kw if RE_PV_NOUN2.search(c.t[max(0, v["s"] - 25):v["s"]])]
        if casa and pv2 and len(rest_kw) > 1:
            g = pv2[0]
            casa_kw = next((v for v in rest_kw if v is not g), None)
            grupuri = [{"n": 1, "Pn_kW": g["val"], "txt": c.o(g["s"], g["e"])}]
            if casa_kw and "P_aprobata_kW" not in intr:
                intr["P_aprobata_kW"] = puteri["P_aprobata_kW"] = _nr(casa_kw["val"])
                c.nota(f"„{c.o(casa_kw['s'], casa_kw['e']).strip()}” = puterea casei (consum) → P aprobată presupusă; "
                       f"„{c.o(g['s'], g['e']).strip()}” = invertorul fotovoltaic")
        elif rest_kw:
            grupuri = [{"n": 1, "Pn_kW": rest_kw[0]["val"], "txt": c.o(rest_kw[0]["s"], rest_kw[0]["e"])}]
            rest_kw = rest_kw[1:]
            mi = next((x for x in modele if x["fel"] == "inv"), None)
            if mi:
                grupuri[0].update(_fisa(mi))
    elif rest_kw and grupuri and total is None:
        v = rest_kw[0]
        sig_g = sum((g["n"] or 1) * g["Pn_kW"] for g in grupuri if g.get("Pn_kW"))
        anc = _ancora(c, v)
        if tip == "prosumator" and "P_aprobata_kW" not in intr and anc not in ("total", "inv") and sig_g \
                and v["val"] > sig_g + 1e-6:
            # r7 (locuințe #59): o putere rămasă, fără cuvânt-cheie, mai mare decât invertoarele = puterea branșamentului
            intr["P_aprobata_kW"] = puteri["P_aprobata_kW"] = _nr(v["val"])
            c.consumat.append((v["s"], v["e"]))
            c.nota(f"„{c.o(*_clauza(c, v['s'], v['e'])).strip(' ,;')}” = puterea aprobată a branșamentului (PRESUPUS: "
                   f"{fmt(v['val'])} kW > invertoarele {fmt(sig_g)} kW, deci nu e puterea lor)")
        else:
            total = v["val"]
            c.foloseste(v["s"], v["e"])
            c.nota(f"„{c.o(v['s'], v['e']).strip()}” = puterea totală declarată a instalației")
    # grupuri fără putere: din puterea totală (doar cu întrebare)
    fara = [g for g in grupuri if g["Pn_kW"] is None]
    if fara:
        P = total or (rest_kw[0]["val"] if rest_kw and not total else None)
        if P and len(grupuri) == 1:
            g = grupuri[0]
            g["Pn_kW"] = P / g["n"]
            puteri["P_ca_kW"] = _nr(P)
            total = None
            c.nota(f"{fmt(P)} kW = putere c.a. totală → {g['n']} × {fmt(P / g['n'])} kW"
                   + ("" if g.get("model") else " (PRESUPUS — modelul invertorului nu e în catalog: confirmați cu fișa "
                                                "tehnică)"))
            if g["n"] > 1:
                c.intrebari.append(("I02", f"Invertoarele sunt de {fmt(P / g['n'])} kW fiecare ({g['n']} × "
                                           f"{fmt(P / g['n'])} = {fmt(P)} kW)? Indicați puterea fiecărui invertor."))
        else:
            grupuri = [g for g in grupuri if g["Pn_kW"] is not None]
    grupuri = [g for g in grupuri if g["Pn_kW"]]
    if not grupuri and tip == "cef" and bess and not total and rest_kw and _ancora(c, rest_kw[0]) == "total":
        total = rest_kw[0]["val"]
        c.foloseste(rest_kw[0]["s"], rest_kw[0]["e"])
    if not grupuri and tip == "cef" and total and bess:
        # r7 (#12): „CEF 100 kW + BESS …” — CEF-ul nu dispare: 1 grup de invertoare cu puterea declarată + întrebare
        grupuri = [{"n": 1, "Pn_kW": total, "txt": f"CEF {fmt(total)} kW"}]
        c.intrebari.append(("I02", f"Invertoarele CEF-ului de {fmt(total)} kW: câte și de ce putere? (desenat 1 × "
                                   f"{fmt(total)} kW până la răspuns)"))
        total = None
    inv = []
    bat_decl = bool(bess) or bool(re.search(r"\bhibrid\w*|(?<!fara )\bbater\w*|(?<!fara )\bstocare\b|\bacumulator\w*", c.t))
    for g in grupuri:
        d = {"n": int(g["n"]), "Pn_kW": _nr(g["Pn_kW"])}
        d.update(_fisa(g))
        if "s" in g and _e_existent(c, g["s"], g.get("e_cons", g["e"])):
            d["existent"] = True                # r10 (P0 #43, #9, #56): grupul existent se păstrează și se marchează
        if g.get("hibrid") and bat_decl:
            d["hibrid"] = True
        elif g.get("hibrid") or (_catalog(d.get("producator"), d.get("model")) or {}).get("hibrid"):
            # r7 (P1 „baterie-fantomă”): invertor care POATE fi hibrid, fără baterie declarată → fără baterie desenată
            d["hibrid"] = False
            c.nota(f"{d.get('model')}: invertor cu port de baterie, dar fără baterie declarată → desenat fără baterie")
        inv.append(d)
    # r8 (P0 fotovoltaic #33): invertoare MONOFAZATE (Primo …-1, SUN2000-…L1) într-o instalație trifazată → repartizate pe
    # faze (L1 / L2 / L3), câte unul pe fază — nu desenate 3 × 400 V
    ret_inst = retea_declarata(c) or ("tri" if tip == "cef" or re.search(r"\bfiecare\s+faz|\bpe\s+(?:cele\s+)?(?:3|trei)\s+faze",
                                                                         c.t) else None)
    lista_faze = _lista_faze(c.t)
    if ret_inst == "mono" and (RE_CASA_TRI.search(c.t) or lista_faze or re.search(r"\bfiecare\s+faz|\bpe\s+faz[ae]\b", c.t)):
        ret_inst = "tri"                 # r10: „2 invertoare monofazate … pe L1 și L3, casa trifazată” — casa e trifazată
    n_mono = sum(g.get("n") or 1 for g in grupuri if g.get("retea_model") == "mono")
    if ret_inst == "tri" and n_mono >= 2 and len(inv) == len(grupuri):
        nou, k = [], 0
        for d, g in zip(inv, grupuri):
            if g.get("retea_model") != "mono":
                nou.append(d)
                continue
            n = int(d["n"])
            pe_faza = {}
            for _ in range(n):
                f_ = lista_faze[k] if k < len(lista_faze) else ("L1", "L2", "L3")[k % 3]   # r10: „pe L1, L2, L3” / „pe R și T”
                pe_faza[f_] = pe_faza.get(f_, 0) + 1
                k += 1
            for f_, nn in pe_faza.items():
                nou.append(dict(d, n=nn, faza=f_))
        inv = nou
        c._retea_model = "tri"
        rep = ", ".join(f"{x['n']} × {fmt(x['Pn_kW'])} kW pe {x['faza']}" for x in inv if x.get("faza"))
        c.nota(f"invertoare monofazate într-o instalație trifazată → repartizate pe faze: {rep}"
               + ("" if n_mono % 3 == 0 else " — DEZECHILIBRU între faze, verificați limita OD"))
        grupuri = [dict(g, retea_model=None) for g in grupuri]
    # r7: rețeaua și tensiunea c.a. din modelul invertoarelor (Deye …LP3 = trifazat; SG250HX / 330KTL-H1 = 800 V fără N)
    rm = {g.get("retea_model") for g in grupuri}
    if len(rm) == 1 and None not in rm:
        c._retea_model = rm.pop()

    u800 = [g for g in grupuri if g.get("U_ca_V") == 800]
    c._grupuri_pv = grupuri
    if u800:
        _u_ca_800(c, intr, ex, u800)
    sigma = sum(i["n"] * i["Pn_kW"] for i in inv)
    if sigma:                      # r8 (#36): „CEF 330 kVA cu 3 invertoare de 110 kVA” — kVA-ul total = Σ invertoare
        for v in valori(c.mascat()):
            if v["marime"] == "kVA" and abs(v["val"] - sigma) <= max(0.5, 0.01 * sigma) and _proprietar_kva(c, v) != "pt":
                c.consumat.append((v["s"], v["e"]))
                c.nota(f"„{c.o(v['s'], v['e']).strip()}” = puterea totală a invertoarelor (Σ = {fmt(sigma)} kVA)")
    mt_ = re.search(r"\b(?:impartit\w*|repartizat\w*|grupat\w*|distribuit\w*)\s+(?:in|pe)\s+(?P<k>\d|doua|trei|patru)\s+"
                    r"(?:tablouri\s+|tgd\w*\s+)*(?:tgd(?:-?cf)?\w*\s+)?(?:\(?\s*)?(?:a\s+|de\s+)?(?:cate\s+)?(?P<m>\d+)?", c.t)
    if mt_ and inv:
        # r10 (fotovoltaic #34): „20 x … împărțite în 2 tablouri TGD-CF a câte 10” → câte un TGD-CF pe grup
        k_ = _NUMERAL.get(mt_.group("k")) or int(mt_.group("k"))
        n_tot = sum(g["n"] for g in inv)
        m_ = int(mt_.group("m")) if mt_.group("m") else (n_tot // k_ if n_tot % k_ == 0 else None)
        if k_ >= 2 and m_ and m_ * k_ == n_tot and len(inv) == 1:
            inv[:] = [dict(inv[0], n=m_, tgd=i + 1) for i in range(k_)]
            intr["n_tgd_cf"] = k_
            c.foloseste(mt_.start(), mt_.end())
            c.nota(f"„{c.o(mt_.start(), mt_.end()).strip()}” = {k_} tablouri TGD-CF a câte {m_} invertoare "
                   "(invertoare[].tgd, n_tgd_cf)")
        elif k_ >= 2:
            c.intrebari.append(("I05", f"„{c.o(mt_.start(), mt_.end()).strip()}”: cum se împart cele {n_tot} invertoare pe "
                                       f"cele {k_} tablouri TGD-CF?"))
    for mpi in re.finditer(rf"\b(?:pi|p\s*inst\w*|puterea?\s+instalat\w*)\s*(?:=|:|de)?\s*(?P<v>{NUM})\s*kw\b", c.mascat()):
        if sigma and abs(numar(mpi.group("v")) - sigma) <= max(1.0, 0.03 * sigma):
            # r10 (locuințe #58): „PI 35 kW” ≈ Σ invertoare (34,8 kW) = puterea instalată (sumă de control)
            c.consumat.append((mpi.start(), mpi.end()))
            c.nota(f"„{c.o(mpi.start(), mpi.end()).strip()}” = puterea instalată ≈ Σ invertoare {fmt(sigma)} kW (sumă de control)")
    if getattr(c, "_lim_pct", None) is not None:
        if sigma:
            lim_ = _nr(sigma * c._lim_pct / 100)
            intr["limitare_injectie_kW"] = puteri["limitare_injectie_kW"] = lim_
            c.nota(f"„{c._lim_pct_txt}” = limitarea injecției la {fmt(c._lim_pct)} % × Σ invertoare {fmt(sigma)} kW = "
                   f"{fmt(lim_)} kW (analizor / contor de control la punctul de racord + EMS)")
        else:
            c.intrebari.append(("I02", f"„{c._lim_pct_txt}”: din ce putere se calculează procentul (kW)?"))
    if sigma and tip in ("cef", "prosumator"):
        # r8 (P1 fotovoltaic #24, #53): curentul invertoarelor peste protecția punctului de racord → întrebare
        q_r = intr.get("In_Q_bransament_A") if intr.get("racord") == "bmpt" or tip == "prosumator" else intr.get("racord_In_Q_A")
        mono_ = (retea_declarata(c) == "mono")
        iac = 1.1 * sigma * 1000 / (U_MONO if mono_ else U_TRI)
        if inv and all(d.get("faza") in ("L1", "L2", "L3") for d in inv):
            pf = {}                               # r10: monofazate repartizate pe faze → Iac pe faza cea mai încărcată
            for d in inv:
                pf[d["faza"]] = pf.get(d["faza"], 0) + d["n"] * d["Pn_kW"]
            iac = 1.1 * max(pf.values()) * 1000 / U_MONO
        if q_r and iac > q_r * 1.0 + 1e-6 and not intr.get("limitare_injectie_kW"):
            unde = "BMPT" if (intr.get("racord") == "bmpt" or tip == "prosumator") else "întrerupătorul din TG"
            c.intrebari.append(("I08", f"Iac,max = 1,1·{fmt(sigma)} kW ≈ {fmt(iac, 0)} A > {unde} {fmt(q_r)} A: se mărește "
                                       "protecția / branșamentul (ATR nou), sau se limitează puterea injectată?"))
    if intr.get("racord") == "bmpt" and intr.get("pt_existent") is False:
        c.intrebari.append(("I08", "Racordul e scris și „în BMPT existent”, și printr-un PT nou: centrala se leagă în BMPT-ul "
                                   "existent sau prin PT-ul nou? (un singur punct de racord pe schemă)"))
    if intr.get("n_trafo") == 2 and intr.get("pt_Sn_kVA") and sigma:
        mt2 = re.search(r"\bbar\w*\s+(?:jt\s+)?(?:a\s+)?(?:trafo\w*\s+|transformator\w*\s+)?t\s*([12])\b", c.t)
        if mt2 and 1.1 * sigma > intr["pt_Sn_kVA"] + 1e-6:      # r8 (#35): racord pe bara unui singur trafo
            c.foloseste(mt2.start(), mt2.end())
            c.intrebari.append(("I08", f"Racord pe bara JT a trafo T{mt2.group(1)} ({fmt(intr['pt_Sn_kVA'])} kVA): S = "
                                       f"1,1·{fmt(sigma)} = {fmt(1.1 * sigma)} kVA > Sn T{mt2.group(1)} — se împart "
                                       "invertoarele pe ambele trafo, cupla se închide, sau se limitează puterea?"))
    if p_evac is not None and sigma:

        if intr.get("limitare_injectie_kW") is None and (p_evac == 0 or p_evac < sigma - 0.5):
            # r8 (fotovoltaic #1, #15, #56): ATR „putere evacuată X kW” < invertoare → limitarea injecției la X (AR la PCC)
            intr["limitare_injectie_kW"] = puteri["limitare_injectie_kW"] = _nr(p_evac)
            c.nota(f"puterea aprobată de evacuare din ATR ({fmt(p_evac)} kW) < invertoarele ({fmt(sigma)} kW) → limitarea "
                   f"injecției la {fmt(p_evac)} kW" + (" (injecție zero)" if p_evac == 0 else "")
                   + ": analizor / releu de putere inversă la punctul de racord + EMS")
        elif intr.get("limitare_injectie_kW") == 0 and p_evac > 0 and tip == "cef":
            c.probleme.append(("I08", f"Contradicție: „injecție zero” și puterea aprobată de evacuare {fmt(p_evac)} kW din ATR (I08).",
                               f"Centrala injectează până la {fmt(p_evac)} kW (ATR), sau funcționează cu injecție zero?"))
    if inv and total and total > sigma + 0.5 and not kwp and tip == "cef" and \
            re.search(rf"\b(?:pi|p\s*inst\w*|puterea?\s+instalat\w*)\s*(?:=|:|de)?\s*{re.escape(fmt(total, 3)).replace(',', '[.,]')}\s*kw\b", c.t):
        # r12 (real X): „CEF Pi 324 kW” cu 3 × 100 kW — „Pi” > Σ invertoare = puterea instalată c.c. (kWp), nu contradicție
        puteri["kWp"] = intr["kWp"] = _nr(total)
        kwp = {"val": total}
        c.nota(f"„Pi {fmt(total)} kW” > Σ invertoare {fmt(sigma)} kW = puterea instalată a modulelor ({fmt(total)} kWp)")
        total = None
    if inv and total and abs(total - sigma) > max(0.5, 0.01 * total):
        desc = " + ".join(f"{i['n']} × {fmt(i['Pn_kW'])}" for i in inv)
        c.probleme.append(("I08", f"Contradicție: invertoarele {desc} kW = {fmt(sigma)} kW, dar puterea totală scrisă e "
                                  f"{fmt(total)} kW (I08).",
                           f"Câte invertoare și de ce putere: {desc} kW (Σ {fmt(sigma)} kW) sau total {fmt(total)} kW?"))
    elif inv and total and len(inv) > 1:
        c.nota(f"Σ invertoare = {fmt(sigma)} kW = puterea totală declarată")
    if kwp and sigma and not (0.8 <= kwp["val"] / sigma <= 1.6) and not re.search(r"\bhibrid", c.t):
        c.intrebari.append(("I08", f"Raportul c.c./c.a. = {fmt(kwp['val'])}/{fmt(sigma)} = "
                                   f"{fmt(kwp['val'] / sigma, 2)} e în afara intervalului uzual 0,8 … 1,6. Confirmați "
                                   "puterea invertoarelor?"))
    if inv:
        puteri["invertoare"] = [{k: v for k, v in i.items() if k != "hibrid"} for i in inv]
        intr["invertoare"] = inv
    if bess:
        hib = [i for i in inv if i.get("hibrid")]
        if "cuplaj" not in bess:
            if (bess.get("model") or bess.get("producator")) and _cat_inv is not None:
                try:
                    if _cat_inv.bess_ca(bess.get("producator"), bess.get("model")):
                        bess["cuplaj"] = "ca"
                    elif _cat_inv.baterie_cc(bess.get("producator"), bess.get("model")) and (hib or tip == "prosumator"):
                        bess["cuplaj"] = "cc"
                except Exception:  # noqa: BLE001
                    pass
            if "cuplaj" not in bess and hib:
                bess["cuplaj"] = "cc"
        if bess.pop("fiecare", False) and bess.get("kWh"):
            n_h = sum(i["n"] for i in (hib or inv)) or 1
            if n_h > 1:
                c.nota(f"„{fmt(bess['kWh'])} kWh fiecare” × {n_h} invertoare = {fmt(bess['kWh'] * n_h)} kWh")
                bess["kWh"] = _nr(bess["kWh"] * n_h)
        if bess.get("cuplaj") == "cc":
            c.nota("bateria e cuplată în c.c. la invertoarele hibride (fără PCS separat)")
            if tip == "cef" and not bess.get("P_kW"):
                bess = {k: v for k, v in bess.items() if v is not None}
                puteri["bess"] = intr["bess"] = bess
                return puteri, total, sigma, kwp
        if tip == "prosumator" and bess.get("cuplaj") != "ca" and not bess.get("P_kW"):
            bess = {k: v for k, v in bess.items() if v is not None}
            puteri["bess"] = intr["bess"] = bess          # cuplajul se decide în extrage_prosumator
            return puteri, total, sigma, kwp
        if bess["kWh"] is None and bess["P_kW"]:
            c.intrebari.append(("I02", f"Ce capacitate (kWh) are BESS-ul de {fmt(bess['P_kW'])} kW?"))
        if bess["P_kW"] is None and bess["kWh"]:
            bess["P_kW"] = _nr(bess["kWh"] / 2)
            c.nota(f"PCS BESS = {fmt(bess['P_kW'])} kW (0,5C din {fmt(bess['kWh'])} kWh) — presupus")
            ex["_pcs_presupus"] = bess["P_kW"]
        if bess.get("model") or bess.get("producator"):
            c.nota(f"BESS {' '.join(x for x in (bess.get('producator'), bess.get('model')) if x)}"
                   f" {fmt(bess['kWh'] or 0)} kWh / {fmt(bess['P_kW'] or 0)} kW")
        bess = {k: v for k, v in bess.items() if v is not None}
        puteri["bess"] = intr["bess"] = bess
    if re.search(r"acoperi[șs]", c.t):
        intr["cablu_inv"] = dict(intr.get("cablu_inv") or {}, metoda="E")
        c.nota("invertoare pe acoperiș → cablurile c.a. pozate pe pat de cabluri / în aer (metoda E)")
    return puteri, total, sigma, kwp


def extrage_cef(c: Ctx, vals, intr, ex):
    puteri, total, sigma, kwp = extrage_pv(c, intr, ex, "cef")
    if total and not intr.get("invertoare"):
        puteri["P_ca_kW"] = _nr(total)
    imp = getattr(c, "_cablu_impus", None)
    cab0 = {k: v for k, v in (("material", ex["material"]), ("izolatie", ex["izolatie"])) if v}
    m_inv = re.search(r"\bcablu\w*\s+(?:de\s+|al\s+|pe\s+|pentru\s+)?(?:circuit\w*\s+)?invertor\w*"
                      r"|\bcablu\w*[^,;]{0,30}?\bde\s+la\s+invertor\w*"        # r10 (#50): „cablu 5x16 de la invertor …”
                      r"|\b(?:fiecare|pe\s+fiecare|cate\s+un\w*)\s+invertor\w*\s+(?:(?:cu|are|alimentat\w*\s+cu|legat\w*\s+cu)\s+)?(?:un\s+)?cablu\w*",
                      c.t)                                     # r11 (#43): „fiecare invertor cu cablu CYY-F 5x16, 25 m”
    if imp and m_inv:
        # r9 (fotovoltaic #25): „cablu invertor NYY-J 5x25 Cu, 45 m” = cablul circuitului invertorului, nu C0
        intr["cablu_inv"] = dict(intr.get("cablu_inv") or {}, **imp)
        c.foloseste(m_inv.start(), m_inv.end())
        c.nota(f"„{c.o(m_inv.start(), m_inv.end()).strip()}” = cablul impus al circuitului invertorului (cablu_inv), nu C0")
        imp, cab0 = None, {}
    if imp:
        cab0.update(imp)
    if cab0:
        intr["cablu_C0"] = cab0
    _lungimi_pv(c, intr, "cef")
    if m_inv and intr.get("cablu_inv", {}).get("S_fortat") and intr.get("L_racord_m") and not intr.get("L_inv_m") \
            and re.search(rf"invertor\w*[^;]{{0,50}}?{NUM}\s*m\b", c.t):
        intr["L_inv_m"] = intr.pop("L_racord_m")
    cab_imp = intr.get("cablu_inv", {}).get("S_fortat") and not intr.get("L_inv_m") and "cablu_inv" or \
        (intr.get("cablu_C0", {}).get("S_fortat") and not intr.get("L_racord_m") and "cablu_C0")
    if cab_imp:
        # r10 (fotovoltaic #51): cablul impus fără lungime nu se ignoră tăcut — se desenează cu L presupus (30 m) și se
        # verifică (Iz, ΔU); lungimea se întreabă
        k_l = "L_inv_m" if cab_imp == "cablu_inv" else "L_racord_m"
        intr[k_l] = 30
        cb = intr[cab_imp]
        c.intrebari.append(("I02", f"Ce lungime are cablul impus ({cb.get('tip_cablu') or ''} {cb.get('n_conductoare') or ''}"
                                   f"×{fmt(cb['S_fortat'])} mm²)? Desenat și verificat (Iz, ΔU) cu L = 30 m presupus.".replace(" ×", " ")
                                   .replace("( ", "(")))
        c.nota(f"cablul impus {fmt(cb['S_fortat'])} mm² fără lungime → L = 30 m presupus (verificat Iz / ΔU)")
    if not kwp and intr.get("invertoare"):
        c.nota("kWp nedeclarat (raport c.c./c.a. necalculat)")
    _retea_pv(c, intr, ex, sigma, "cef")
    if "tablou" in getattr(c, "combo", []):
        pl = ", ".join(c.o(m.start(), m.end()) for m in re.finditer(rf"\btd-?\s*\d+\s+{NUM}\s*a\b", c.t))
        c.intrebari.append(("I14", "Textul descrie și tabloul general (TG" + (f": {pl}" if pl else "") + "). Desenez CEF-ul "
                                   "racordat în TG-ul existent; TG-ul cu plecările lui se generează separat (schemă "
                                   "„tablou”) — de acord?"))
    return puteri


def _retea_pv(c: Ctx, intr, ex, sigma, tip):
    """r5 (P0-7 PV): rețeaua NU se presupune în tăcere; „monofazat” la o CEF care nu încape în 40 A → I08."""
    r = retea_declarata(c) or getattr(c, "_retea_model", None)
    iac_mono = FACTOR_INV * (sigma or 0) * 1000 / U_MONO
    if r == "mono" and iac_mono > norme.BMPM["I_max_A"]:
        c.probleme.append(("I08", f"Contradicție: „monofazat” și invertoare Σ {fmt(sigma)} kW (Iac = {fmt(iac_mono)} A "
                                  "> 40 A la 230 V) (I08).",
                           f"Centrala e trifazată (3 × 400 V), sau invertoarele sunt monofazate de cel mult "
                           f"{math.floor(norme.BMPM['I_max_A'] * U_MONO / FACTOR_INV / 1000)} kW în total?"))
        return
    if r:
        intr["retea"] = ex["retea"] = r
    elif sigma and iac_mono > norme.BMPM["I_max_A"]:
        intr["retea"] = ex["retea"] = "tri"
        c.nota(f"rețea nedeclarată: invertoarele Σ {fmt(sigma)} kW nu încap în monofazat → trifazat 3 × 400/230 V")
    elif sigma:
        ex["retea"] = None
        c.intrebari.append(("I02", "Instalația este monofazată (230 V) sau trifazată (3 × 400 V)? Rețeaua nu se presupune."))


# r10 (locuințe #22, #43): „invertor 6 kW monofazat pe casa trifazata, faza L2”, „prosumator 5 kW mono, dar casa
# trifazata 3x25A. Pune invertorul pe faza R” — casa rămâne TRIFAZATĂ, invertorul monofazat stă pe faza declarată
RE_FAZA_DECL = re.compile(r"\b(?:pe\s+)?faz[ae]\s*(?:a\s+|nr\.?\s*)?(?P<f>l[123]|[rst]|[123])\b|\bpe\s+(?P<f2>l[123])\b")
_FAZA_RST = {"r": "L1", "s": "L2", "t": "L3", "1": "L1", "2": "L2", "3": "L3"}
RE_INV_MONO = re.compile(r"\b(?:invertor\w*|prosumator\w*|pv|fotovolt\w*|panouri)\b[^,.;]{0,30}?\b(?:monofaz\w*|mono)\b"
                         r"|\b(?:monofaz\w*|mono)\b[^,.;]{0,12}\binvertor\w*")
RE_CASA_TRI = re.compile(r"\b(?:cas(?:a|ei)|locuint\w*|instalati\w*|bransament\w*|retea\w*)\s+(?:e\s+|este\s+)?(?:trifaz\w*|tri)\b"
                         r"|\bbmpt\w*(?!\s*(?:existent\w*\s+)?(?:1\s*×|monofaz|mono\b|\d+\s*a\s+monofaz))|\b(?:trifaz\w*|tri)\s+3\s*×\s*\d+\s*a\b")


def _lista_faze(t: str) -> list:
    """„pe L1, L2, L3”, „pe fazele R și T”, „pe L1 si L3” → ["L1", "L3"] (ordinea din text)"""
    m = re.search(r"\bpe\s+(?:fazele\s+|faza\s+)?(?P<l>(?:l[123]|[rst])(?:\s*(?:,|si|și|\+)\s*(?:l[123]|[rst]))+)\b", t)
    if not m:
        return []
    return [x.upper() if x.startswith("l") else _FAZA_RST[x] for x in re.findall(r"l[123]|\b[rst]\b", m.group("l"))]


def _faza_declarata(t: str):
    m = RE_FAZA_DECL.search(t)
    if not m:
        return None, None
    f = (m.group("f") or m.group("f2")).lower()
    return (f.upper() if f.startswith("l") else _FAZA_RST[f]), m


def _inv_mono_pe_tri(c: Ctx, intr: dict, ex: dict):
    mono = RE_INV_MONO.search(c.t) or any(re.search(r"-L\d\b|SUNNY\s+BOY|PRIMO|MIN\s*\d+\s*TL-X|-1\b", (g.get("model") or "").upper())
                                          for g in intr.get("invertoare") or []) \
        or (intr.get("invertoare") and re.search(r"\bmonofaz\w*|\bmono\b", c.t)
                                        and not re.search(r"\b(?:cas(?:a|ei)|locuint\w*|apartament\w*)\s+(?:e\s+)?mono", c.t))
    if not (mono and RE_CASA_TRI.search(c.t)):
        return
    inv = intr.get("invertoare") or ([{"n": 1, "Pn_kW": intr["Pn_inv_kW"]}] if intr.get("Pn_inv_kW") else [])
    if inv and all(g.get("faza") in ("L1", "L2", "L3") for g in inv) and sum(g.get("n", 1) for g in inv) > 1:
        # r10: mai multe invertoare monofazate deja repartizate pe faze, pe casă trifazată → instalația e trifazată
        intr["retea"] = ex["retea"] = "tri"
        c.probleme[:] = [p for p in c.probleme if not ("monofazat" in p[1] and "Contradic" in p[1])]
        mt = RE_CASA_TRI.search(c.t)
        c.foloseste(mt.start(), mt.end())
        return
    if sum(g.get("n", 1) for g in inv) != 1:
        return
    faza, m = _faza_declarata(c.t)
    g = dict(inv[0])
    g["faza"] = faza or "L1"
    if intr.get("invertor"):
        g.update({k: v for k, v in intr["invertor"].items() if k in ("producator", "model")})
    intr["invertoare"] = [g]
    intr["retea"] = ex["retea"] = "tri"
    c.probleme[:] = [p for p in c.probleme if not ("monofazat" in p[1] and "Contradic" in p[1])]
    if m:
        c.foloseste(m.start(), m.end())
    mt = RE_CASA_TRI.search(c.t)
    c.foloseste(mt.start(), mt.end())
    for mm in re.finditer(r"\bdar\b|\bpune\w*\s+invertor\w*", c.t):
        c.foloseste(mm.start(), mm.end())
    c.nota(f"invertor monofazat {fmt(g['Pn_kW'])} kW pe casă trifazată → instalația rămâne trifazată 3 × 400 V, invertorul "
           f"pe faza {g['faza']}" + ("" if faza else " (PRESUPUS — faza nu e declarată)"))


def extrage_prosumator(c: Ctx, vals, intr, ex):
    if not ex.get("_retea_lipsa"):
        intr["retea"] = ex["retea"]
    puteri, total, sigma, kwp = extrage_pv(c, intr, ex, "prosumator")
    inv = intr.pop("invertoare", None) or []
    if inv:
        puteri["invertoare"] = [{k: v for k, v in i.items() if k != "hibrid"} for i in inv]
        intr["Pn_inv_kW"] = _nr(sum(i["n"] * i["Pn_kW"] for i in inv))
        if len(inv) > 1 or inv[0]["n"] > 1 or inv[0].get("model") or inv[0].get("producator"):
            intr["invertoare"] = inv                    # r5 (P0-5): fiecare invertor desenat separat
        if len(inv) == 1 and inv[0]["n"] == 1 and (inv[0].get("model") or inv[0].get("producator")):
            intr["invertor"] = {k: v for k, v in inv[0].items() if k in ("producator", "model", "Pn_kW", "hibrid")}
    b = intr.pop("bess", None)
    if b and b.get("pcs") and b.pop("_pcs_retea", None) == "mono" and intr.get("retea") == "tri":
        c.intrebari.append(("I08", f"{b['pcs'].get('model')} e un invertor de baterie MONOFAZAT, iar instalația e trifazată: "
                                   "pe ce fază se leagă (dezechilibru, limita ATR), sau folosiți un invertor de baterie "
                                   "trifazat?"))
    if b:
        b.pop("_pcs_retea", None)
    if re.search(r"\bhibrid", c.t) or any(i.get("hibrid") for i in inv):
        ex["hibrid"] = intr["hibrid"] = True
    if b and not b.get("cuplaj") and not intr.get("hibrid") and b.get("P_kW"):
        b["cuplaj"] = "ca"                                # „BESS 200 kWh / 100 kW” = sistem cu PCS propriu (c.a.)
    if b and b.get("cuplaj") != "ca" and not intr.get("hibrid") and b.get("cuplaj") != "cc":
        # r6 (locuințe P1-9): baterie fără „hibrid” → cuplajul NU se presupune în tăcere: c.c. (invertor hibrid, uzual la
        # casă) desenat + întrebare
        c.nota("baterie fără „hibrid” / cuplaj declarat: desenată pe portul c.c. al unui invertor hibrid (PRESUPUS)")
        c.intrebari.append(("I02", "Bateria e cuplată în c.c. la un invertor hibrid (desenat așa), sau în c.a., cu PCS / "
                                   "invertor de baterie propriu (atunci indicați puterea PCS, kW)?"))
        b["cuplaj"] = "cc"
    if b:
        if b.get("cuplaj") == "ca" and not b.get("P_kW") and b.get("kWh"):
            b["P_kW"] = _nr(b["kWh"] / 2)
            c.nota(f"PCS BESS = {fmt(b['P_kW'])} kW (0,5C din {fmt(b['kWh'])} kWh) — presupus")
        if b.get("cuplaj") != "ca" and b.get("kWh"):
            puteri["baterie_kWh"] = intr["baterie_kWh"] = b["kWh"]
            if b.get("producator") or b.get("model"):
                intr["baterie"] = {k: v for k, v in b.items() if k in ("producator", "model", "kWh")}
            puteri.pop("bess", None)
            if b.get("la"):                                  # r7: invertorul cu bateria (cheia motorului bess.la)
                intr["bess"] = {k: v for k, v in b.items() if k in ("kWh", "producator", "model", "la", "cuplaj")}
        else:
            intr["bess"] = b                                # BESS cu PCS propriu (cuplaj c.a.)
            if b.get("kWh") and b.get("cuplaj") != "ca":
                intr["baterie_kWh"] = b["kWh"]
    imp = getattr(c, "_cablu_impus", None)
    if imp:
        intr["cablu"] = dict(imp)
    _lungimi_pv(c, intr, "prosumator")
    _inv_mono_pe_tri(c, intr, ex)
    pa = intr.get("P_aprobata_kW")
    if pa and intr.get("Pn_inv_kW") and intr["Pn_inv_kW"] > pa + 1e-6 and intr.get("limitare_injectie_kW") is None:
        c.avert.append(f"Pn invertor {fmt(intr['Pn_inv_kW'])} kW > P aprobată {fmt(pa)} kW — verificați ATR-ul "
                       "(limitarea injecției)")
    return puteri


# r8 (P0 industrial #12, #14, #64): titlul tabloului / al stației numește siguranța la incendiu — „tablou TDSI sprinklere”,
# „TE desfumare”, „tablou pompe incendiu”, „stație hidranți” → toți consumatorii lui sunt de siguranță (P118/3, I7)
_CUV_SIGURANTA = (r"pomp\w*\s+(?:de\s+)?incendiu|desfumar\w*|hidrant\w*|sprinkler\w*|stingere\w*|presurizar\w*|\bpsi\b"
                  r"|lift\w*\s+(?:de\s+|pentru\s+)?pompieri|ascensor\w*\s+(?:de\s+|pentru\s+)?pompieri"
                  r"|\btdsi\b|drencer\w*|evacuare\s+fum\w*|ilumin\w*\s+(?:de\s+)?(?:siguranta|securitate|evacuare)")
RE_CTX_SIGURANTA = re.compile(rf"\b(?:tablou\w*|t[dge]|tdsi|t[dge]-[a-z0-9]+)\s+(?:de\s+|pentru\s+)?(?:[a-z]+\s+){{0,2}}?"
                              rf"(?:{_CUV_SIGURANTA})|\btdsi\b"
                              r"|\bstati\w*\s+(?:de\s+)?(?:pompare\s+(?:pentru\s+)?incendiu|hidrant\w*|sprinkler\w*|stingere\w*)")
# consumatorul de siguranță după nume (aceeași listă ca regula motorului: calc/scheme.text_de_siguranta)
RE_CONS_SIGURANTA = re.compile(rf"{_CUV_SIGURANTA}|\bincendiu\b|\bjockey\b|\bpompieri\b|ilumin\w*\s+(?:de\s+)?(?:siguranta"
                               r"|evacuare|securitate)|detecti\w*\s+(?:de\s+)?incendiu|\bcdi\b")


def e_siguranta(nume: str) -> bool:
    """r8: numele unui consumator de siguranță la incendiu (pompă incendiu, jockey, desfumare, hidranți, sprinklere,
    presurizare, lift pompieri, iluminat de siguranță, centrala de detecție incendiu)."""
    return bool(RE_CONS_SIGURANTA.search(_fara_diacritice(nume or "")))


# r9 (industrial P0 #27): „stație (de) pompare PSI / incendiu”, „grup de pompare PSI” pe GE + ATS = sarcina e de siguranță
RE_CTX_SIG_GE = re.compile(r"\bstati\w*\s+(?:de\s+)?pompare\s+(?:a\s+)?(?:psi|incendiu|stingere|hidranti|sprinkler\w*)\b"
                           r"|\bgrup\w*\s+(?:de\s+)?pompare\s+(?:psi|incendiu)\b|\binstalati\w*\s+(?:de\s+)?stingere\b"
                           r"|\bpompe\s+(?:psi|incendiu)\s*:")
RE_1A1R = re.compile(r"\(?\b(\d)\s*a?\s*\+\s*(\d)\s*r?\b\)?")


def extrage_ge(c: Ctx, vals, intr, ex):
    """GE + ATS (r5): kVA legat de GE (nu de PT), sarcina vitală = Σ consumatorilor listați, L GE–ATS,
    Q rețea, sursa ramurii de rețea (PT / TGD / BMPT)."""
    puteri = {}
    t = c.mascat()
    vals = valori(t)
    sn_ge = sn_pt = None
    for v in vals:
        if v["marime"] != "kVA":
            continue
        if _proprietar_kva(c, v) == "pt":
            sn_pt = sn_pt or v
        elif sn_ge is None:
            sn_ge = v
        c.consumat.append((v["s"], v["e"]))
    if sn_ge:
        puteri["Sn_GE_kVA"] = intr["Sn_GE_kVA"] = _nr(sn_ge["val"])
    if sn_pt and sn_ge:
        c.nota(f"„{c.o(sn_pt['s'], sn_pt['e']).strip()}” = puterea PT-ului (sursa ramurii de rețea), nu a GE")
    m = re.search(rf"(?:(?:ge|grup\w*|generator\w*)\s*[-–/]\s*(?:ats|aar)|cablu\w*\s+(?:ge|grup\w*|generator\w*)(?:\s*[-–/]\s*(?:ats|aar))?)"
                  rf"\s*(?:de\s+|=\s*)?(?P<v>{NUM})\s*(?P<u>m|km|metri)\b"
                  rf"|(?P<v2>{NUM})\s*(?P<u2>m|km)\s+(?:intre\s+)?(?:ge|grup\w*)\s*(?:[-–/]|si)\s*(?:ats|aar)", t)
    if m:
        v, u = (m.group("v"), m.group("u")) if m.group("v") else (m.group("v2"), m.group("u2"))
        intr["L_GE_ATS_m"] = _nr(numar(v) * UNITATI[u][1])
        c.consumat.append((m.start(), m.end()))
        c.nota(f"„{c.o(m.start(), m.end()).strip()}” = cablul GE → ATS")
    m = re.search(rf"\b(?:retea\w*|q\w*\s+retea\w*|q\s*r)(?:\s+(?:din|prin))?(?:\s+(?:bmpt\w*|bransament\w*|tgd?\b|pt\b)"
                  rf"(?:\s+existent\w*)?)?\s*(?:de\s+|=\s*|:\s*)?(?:3\s*×\s*)?(?P<v>{NUM})\s*a\b|\b(?:bmpt|tgd?|tablou)\w*(?:\s+(?:existent\w*|trifaz\w*|tri))*"
                  rf"\s+(?:de\s+)?(?:3\s*×\s*)?(?P<v2>{NUM})\s*a\b", t)
    if m:
        intr["In_Q_retea_A"] = _nr(numar(m.group("v") or m.group("v2")))
        c.consumat.append((m.start(), m.end()))
        c.nota(f"„{c.o(m.start(), m.end()).strip()}” = calibrul Q al ramurii de rețea")
    # sursa ramurii de rețea
    combo = getattr(c, "combo", [])
    mfr = SIN.fara_retea(c.t)            # r11: toate sinonimele („izolat”, „insular”, „off-grid”, „autonom” …)
    if mfr:
        # r10 (P0 industrial #43): GE = singura sursă („fără rețea, site izolat”) — fără ramură de rețea / ATS inventate
        intr["fara_retea"] = ex["fara_retea"] = True
        c.foloseste(mfr.start(), mfr.end())
        for mm in SIN.RX["fara_retea"].finditer(c.t):      # r11: „izolată, fără rețea” — toate mențiunile
            if SIN.fara_retea(c.t[max(0, mm.start() - 40):mm.end()]):
                c.foloseste(mm.start(), mm.end())
        for mm in re.finditer(r"\(\s*site\s+izolat\w*\s*\)|\bcare\s+alimenteaza\s+tot\s+tg(?:-ul)?\b", c.t):
            c.foloseste(mm.start(), mm.end())
        c.nota(f"„{c.o(mfr.start(), mfr.end()).strip()}” = grupul electrogen e SINGURA sursă (fără rețea, fără ATS): Ik mic al GE "
               "— deconectarea automată se verifică pe curentul de defect al GE")
        combo = []
    mex = re.search(r"\b(?:sursa\s+)?retea\w*\s+(?:din|prin|de\s+la)\s+(?P<s>bmpt|bransament|retea\w*\s+publica|pt\b|post|tgd?\b"
                    r"|tablou)", c.t)
    if mex:                                       # r6 (#31): „sursa rețea din BMPT 200A” are prioritate față de „ATS în TGD”
        k = mex.group("s")
        intr["sursa_retea"] = ex["sursa_retea"] = ("bmpt" if k.startswith(("bmpt", "bransament", "retea")) else
                                                   "pt" if k.startswith(("pt", "post")) else "tgd")
        c.foloseste(mex.start(), mex.end())
        if intr["sursa_retea"] == "pt" and sn_pt:
            intr["pt_Sn_kVA"] = _nr(sn_pt["val"])
    elif intr.get("fara_retea"):
        pass
    elif re.search(r"\bbmpt\w*", c.t) and not re.search(r"\btgd\b|\b(?:tg|tablou\w*)(?:\s+general)?\s+existent", c.t) \
            and not ("pt" in combo or RE_PT_SURSA.search(c.t)):
        intr["sursa_retea"] = ex["sursa_retea"] = "bmpt"     # r10 (industrial #15): „TG fermă … BMPT trifazat 50 A”
    elif "pt" in combo or (RE_PT_SURSA.search(c.t) and not RE_PT_SURSA.search(c.t).group(0).startswith("faza")):
        intr["sursa_retea"] = ex["sursa_retea"] = "pt"
        if sn_pt:
            intr["pt_Sn_kVA"] = _nr(sn_pt["val"])
    elif re.search(r"\btgd?\b|tablou\w*\s+(?:general\s+)?existent", c.t):
        intr["sursa_retea"] = ex["sursa_retea"] = "tgd"
    elif re.search(r"\bbmpt|retea\w*\s+publica|bransament", c.t):
        intr["sursa_retea"] = ex["sursa_retea"] = "bmpt"
    # r7 (P0 #31): „tablou pompe incendiu: …” — contextul din titlu face TOȚI consumatorii de siguranță
    ctx_sig = RE_CTX_SIGURANTA.search(c.t) or RE_CTX_SIG_GE.search(c.t)
    if ctx_sig:
        intr["siguranta_tablou"] = True
        intr["titlu_tablou"] = nume_normalizat(c.o(ctx_sig.start(), ctx_sig.end()))
        c.foloseste(ctx_sig.start(), ctx_sig.end())
        c.nota(f"„{c.o(ctx_sig.start(), ctx_sig.end()).strip()}” = consumatori de siguranță (P118/3, I7): fără DDR în amonte, "
               "cabluri rezistente la foc, protecție termică doar la semnalizare")
    ms2 = re.search(r"\balimentare\w*\s+din\s+(?:doua|2)\s+surse(?:\s+(?:retea|ge|si|grup\w*))*", c.t)
    if ms2:
        c.foloseste(ms2.start(), ms2.end())
    # r9 (#67): „TG din PT 630 kVA cu 2 intrări: rețea și GE, ATS, toți consumatorii pe GE” = ATS general (toată sarcina)
    for m2i in re.finditer(r"\b(?:tg\w*|tablou\w*)\b[^,;:]{0,40}?\bcu\s+(?:2|doua)\s+intrari\b"
                           r"|\btoti\s+consumatorii\s+(?:sunt\s+)?pe\s+ge\b", c.t):
        c.foloseste(m2i.start(), m2i.end())
        c.nota(f"„{c.o(m2i.start(), m2i.end()).strip()}” = ATS general rețea / GE: toată sarcina tabloului e pe GE")
    mman = re.search(r"\b(?:inversor|comutator|comutare|inversare)\w*\s+(?:de\s+surs\w*\s+)?manual\w*(?:\s+de\s+surs\w*)?", c.t)
    if mman:                                       # r7 (#63): inversor manual ≠ ATS
        intr["comutare"] = "manual"
        c.foloseste(mman.start(), mman.end())
        c.avert.append("comutare manuală a surselor (inversor 0-I-II, interblocat mecanic) — NU ATS automat; verificați "
                       "simbolul pe planșă")
    # sarcina vitală = Σ consumatorilor listați
    t = c.mascat()
    # r8 (industrial #46): „TG-normal: producție 300 kW” = consumatori alimentați DOAR din rețea (nu din GE)
    for mnorm in re.finditer(r"\b(?:tg|tablou\w*)[\s-]*normal\w*\s*:?[^.;]*?(?=\.\s|;|\btg[\s-]*vital|\btablou\w*\s+vital|$)"
                             r"|\bconsumatori\s+normali\w*\s*:?[^.;]*?(?=\.\s|;|\bvital|$)", t):
        vn = [v for v in valori(mnorm.group(0)) if v["marime"] == "kW"]
        if vn:
            c.consumat.append((mnorm.start(), mnorm.end()))
            c.nota(f"„{c.o(mnorm.start(), mnorm.end()).strip()}” = consumatori normali (doar din rețea, nu din GE) — nu intră "
                   "în sarcina GE")
    t = c.mascat()
    # r9 (#24): „Consumatori vitali pe GE …: … Normali: HVAC 150 kW, prize 40 kW” — normalii rămân în listă cu
    # `vital: false` (motorul îi pune pe ramura de rețea, înaintea ATS) și nu intră în sarcina GE
    # r10 (P0 industrial #12, #67): „Vitali: … Nevitali: …” — nevitalii (vital: false) nu intră în sarcina GE
    zone_norm = [(m.start(), m.end()) for m in re.finditer(
        r"(?:^|(?<=[.;]\s)|(?<=[.;]))\s*(?:consumatori\s+)?(?:normali|nevitali|ne-vitali|neprioritari|nesecurizati)\w*"
        r"(?:\s+(?:doar\s+)?(?:pe|din)\s+retea\w*)?\s*:[^.;]*?(?=\.\s|\.$|;|\bvital|$)", t)]
    for a_, b_ in zone_norm:
        c.nota(f"„{c.o(a_, b_).strip()}” = consumatori normali (vital: false) — pe ramura de rețea, nu din GE")
        c.foloseste(a_, a_ + len(re.match(r"[^:]*:", t[a_:b_]).group(0)))
    zone_vit = [(m.start(), m.end()) for m in re.finditer(
        r"(?:^|(?<=[.;]\s)|(?<=[.;]))\s*(?:consumatori\s+)?(?:vitali|prioritari|esentiali|securizati)\w*[^:.;]{0,40}:[^.;]*?"
        r"(?=\.\s|\.$|;|\bnevital|\bnormal|$)", t)]
    for a_, b_ in zone_vit:
        c.foloseste(a_, a_ + len(re.match(r"[^:]*:", t[a_:b_]).group(0)))
    cons, lista, n_rez = [], [], []
    for v in valori(t):
        if v["marime"] != "kW":
            continue
        pre = t[max(0, v["s"] - 30):v["s"]]
        mm = re.search(r"(?<![\w.,])(\d+)\s*(?:[a-z]+\s+){0,2}[x×]\s*$", pre) or re.search(r"(?<![\w.,])(\d+)\s*×\s*$", pre)
        n = int(mm.group(1)) if mm else 1
        # r6 (#35): consumatorul cu numele lui (din aceeași clauză), multiplicator și pornire → `consumatori[]`
        a = max([x.end() for x in re.compile(r"[,;:]|\bsi\b|\bpentru\b|\bpe\b|\bsarcin\w*|\bconsumator\w*(?:\s+vital\w*)?")
                 .finditer(t, 0, v["s"])] or [0])
        seg = t[a:v["s"]]
        m11 = RE_1A1R.search(seg + t[v["e"]:v["e"] + 10])          # r9 (#27): și „(1A+1R)”
        mnum = re.match(r"\s*(doua|doi|trei|patru)\s+", seg)
        if mnum and n == 1:
            n = _NUMERAL[mnum.group(1)]
        mnum2 = re.match(r"\s*(\d{1,2})\s+(?=[a-z])", seg)           # r9 (#27): „2 electropompe 30 kW”, „3 extrudere 90 kW”
        if mnum2 and n == 1 and int(mnum2.group(1)) > 1:
            n = int(mnum2.group(1))
        seg_n = RE_1A1R.sub(lambda x: " " * len(x.group(0)), seg)       # r8 (#11): „1+1” ≠ nume
        seg_n = re.sub(r"^\s*(?:doua|doi|trei|patru|\d{1,2})\s+", lambda x: " " * len(x.group(0)), seg_n)
        cons.append((n, v))
        mn = re.search(r"([a-z][a-z \-]*?)\s*(?:\d+\s*[x×]\s*)?(?:de\s+)?$", seg_n.rstrip() + " ")
        if mn and mn.group(1).strip() in ("de", "a", "cu"):
            mn = re.search(r"([a-z][a-z \-]*?[a-z])\s*(?:de\s*)?$", seg_n.rstrip())
        nume = mn.group(1).strip() if mn and mn.group(1).strip() else None
        if not nume and t[a - 1:a] == ":":           # r11 (industrial #10): „Pompe: 2 x 22 kW” — numele e cel dinaintea „:”
            mp_ = re.search(r"([a-z][a-z\-]*(?:\s+[a-z][a-z\-]*){0,2})\s*:$", t[max(0, a - 30):a])
            if mp_ and mp_.group(1) not in ("vitali", "nevitali", "normali", "consumatori", "plecari"):
                mn, a = mp_, max(0, a - 30)
                nume = mp_.group(1)
        d = {"nume": nume_normalizat(c.o(a + mn.start(1), a + mn.end(1))) if nume else f"Consumator {len(lista) + 1}",
             "P_kW": _nr(v["val"])}
        if n > 1:
            d["n"] = n
        if m11:                                          # r8 (#11, #46): „1+1” / „2x30 kW (1+1)” = activ + rezervă
            d["n"] = f"{m11.group(1)}+{m11.group(2)}"
            n_rez.append((n - int(m11.group(1)) if n > 1 else 0, v))
            c.nota(f"„{c.o(a, v['e']).strip()} ({m11.group(1)}+{m11.group(2)})”: {m11.group(1)} activ + {m11.group(2)} "
                   "rezervă — la sarcină contează doar unitățile active")
        e = v["e"]
        mp = re.match(r"\s*(?:cu\s+)?(?:pornire\s+)?(stea[\s-]*triunghi|soft[\s-]*start\w*|convertizor\w*|directa)", t[e:])
        if mp:
            d["pornire"] = ("stea_triunghi" if mp.group(1).startswith("stea") else "soft" if mp.group(1).startswith("soft")
                            else "convertizor" if mp.group(1).startswith("conv") else "directa")
            e += mp.end()
        if nume and (re.search(r"incendi|hidrant|sprinkler|desfum", nume + " " + t[a:v["s"]]) or e_siguranta(nume)) or ctx_sig:
            d["siguranta"] = True
        m11b = RE_1A1R.search(t[e:e + 16]) if nume and not m11 else None
        if m11b and n > 1:                          # r11 (industrial #10): „2 x 22 kW cu convertizor (1+1)” = 1 activă + 1 rezervă
            d["n"] = f"{m11b.group(1)}+{m11b.group(2)}"
            n_rez.append((n - int(m11b.group(1)), v))
            e += m11b.end()
            c.nota(f"„{c.o(a, e).strip()}”: {m11b.group(1)} activ + {m11b.group(2)} rezervă — la sarcină contează doar unitățile active")
        elif nume and not m11 and re.search(r"\brezerv\w*|\b1\s*\+\s*1\b", nume + " " + t[e:e + 12]):

            d["rezerva"] = True                         # r7 (P0 #31): pompa de rezervă nu se adună la sarcină
            n_rez.append((n, v))
        if any(a_ <= v["s"] < b_ for a_, b_ in zone_norm):
            d["vital"] = False
            n_rez.append((n, v))                       # nu intră în sarcina GE
        elif any(a_ <= v["s"] < b_ for a_, b_ in zone_vit):
            d["vital"] = True
        if m11 and m11.start() >= len(seg):
            e = max(e, v["e"] + m11.end() - len(seg))
        if nume:
            lista.append(d)
            c.foloseste(a, e)
        else:
            c.foloseste(v["s"], e)
    if cons:
        P = sum(n * v["val"] for n, v in cons) - sum(n * v["val"] for n, v in n_rez)
        puteri["P_kW"] = intr["P_sarcina_kW"] = _nr(P)
        if n_rez:
            c.nota("pompa de rezervă (1+1) nu funcționează simultan cu cea principală → nu se adună la sarcină: "
                   f"P = {fmt(P)} kW")
        if lista and (len(lista) > 1 or lista[0].get("n", 1) > 1 or lista[0].get("pornire") or lista[0].get("siguranta")):
            intr["consumatori"] = lista
            if any(x.get("siguranta") for x in lista):
                c.avert.append("consumatori de incendiu pe GE: alimentare fără DDR în amonte (P118/3, I7) — verificați "
                               "ramura ATS → pompe de incendiu")
        if len(cons) > 1 or cons[0][0] > 1:
            c.nota("sarcina vitală = Σ consumatorilor listați: " + " + ".join(
                (f"{n} × {fmt(v['val'])}" if n > 1 else fmt(v["val"])) for n, v in cons) + f" = {fmt(P)} kW")
    if intr.get("sursa_retea") == "pt" and not intr.get("pt_Sn_kVA"):
        c.intrebari.append(("I07", "Ramura de rețea vine din PT: ce putere are transformatorul (kVA)?"))
    elif "sursa_retea" not in intr and not intr.get("fara_retea") and sn_ge and sn_ge["val"] * 1000 / U_TRI > norme.BMPT_I_MAX_A:
        intr["sursa_retea"] = ex["sursa_retea"] = "pt"
        c.nota(f"sursa ramurii de rețea nedeclarată: In GE = {fmt(sn_ge['val'] * 1000 / U_TRI, 0)} A > 250 A (peste "
               "BMPTi-250) → rețea din PT")
        c.intrebari.append(("I07", "Ramura de rețea a ATS-ului vine dintr-un PT propriu (ce Sn, kVA?) sau dintr-un TGD "
                                   "existent?"))
    if combo == ["tablou"] and intr.get("consumatori"):
        combo = []                     # r10: „TG cu GE … plecări: …” — TG-ul descris e chiar tabloul alimentat prin ATS
    if combo:
        nume = {"pt": f"PT{(' ' + fmt(sn_pt['val']) + ' kVA') if sn_pt else ''}", "tablou": "TG cu plecările",
                "cef": "CEF"}
        c.intrebari.append(("I14", "Textul descrie mai multe instalații (" + ", ".join(nume[x] for x in combo)
                                   + " și GE + ATS). Desenez schema GE + ATS; celelalte se generează ca scheme separate "
                                     "— de acord?"))
    return puteri


# =====================================================================================================
# Locuință (SPEC §C.8): casă / apartament → {alimentare, schema_pamant, RA_ohm, circuite[], ks}
# =====================================================================================================
RE_LOCUINTA = re.compile(r"\bcas(?:a|ei|e|uta)\b|\blocuint\w*|\bapartament\w*|\bgarsonier\w*|\bvil(?:a|e|ei)\b"
                         r"|(?<![\w+])p\s*\+\s*[1-3m]\b|\bparter\b|\bmansard\w*|\bduplex\b")
RE_PRIZA_PAMANT = re.compile(r"priz\w*\s+(?:propri\w*\s+)?(?:de\s+)?pamant(?:\s+propri\w*)?")
_CAMERA = (r"(?:\s+(?:din\s+|de\s+la\s+|de\s+|la\s+)?(?:living\w*|dormitor\w*|camer\w*|hol\w*|birou\w*|parter\w*|etaj\w*"
           r"|garaj\w*|mansard\w*|pod\w*|subsol\w*|interior\w*|exterior\w*|ext\b\.?|curte|gradin\w*|teras\w*|dressing\w*))?")
# (regex pe textul normalizat, receptor, nume canonic | None = numele din text). Ordinea = prioritatea.
RECEPTORI_LOC = [
    (r"wallbox\w*|stati\w*\s+(?:de\s+)?(?:incarcare|ve|ev)\w*(?:\s+(?:masina|auto|ve|ev)\w*)?"
     r"|incarcator\w*(?:\s+(?:pentru\s+|de\s+)?(?:masina|auto|ve|ev|electric)\w*)?|incarcare\s+(?:masina|auto|ve|ev)\w*"
     r"|masin\w*\s+electric\w*|vehicul\w*\s+electric\w*|\bev\b|\bve\b|\bpriz\w*\s+(?:de\s+)?(?:auto|masina|ve|ev)\b",
     "vehicul_electric", "Încărcare VE"),
    (r"pomp\w*\s+(?:de\s+)?caldur\w*(?:\s+aer[\s-]*(?:apa|aer))?|heat\s*pump|\bpdc\b|\bpc\s+aer[\s-]*(?:apa|aer)|\bpc\b(?=\s*\d)"
     r"|\baer[\s-]+apa\b", "pompa_caldura", "Pompă de căldură"),
    (r"(?:masin\w*|\bmas)\s+(?:de\s+)?(?:spalat\s+)?vase|\bmsv\b|spalator\w*\s+(?:de\s+)?vase", "masina_spalat_vase",
     "Mașină de spălat vase"),
    (r"(?:masin\w*|\bmas)\s+(?:de\s+)?spalat(?:\s+rufe)?|(?:masin\w*|\bmas)\s+(?:de\s+)?rufe|\bmsr\b|\bms\b(?=\s*\d)", "masina_spalat_rufe",
     "Mașină de spălat rufe"),
    (r"uscator\w*(?:\s+de\s+rufe)?", "uscator", "Uscător"),
    (r"pomp\w*\s+(?:de\s+|pentru\s+)?piscin\w*", "pompa_apa", "Pompă piscină"),
    (r"pomp\w*\s+(?:de\s+)?(?:filtr\w*|recircul\w*)", "pompa_apa", None),
    # r7: „iluminat piscină 12V” = circuit de iluminat prin trafo SELV (nu puterea aprobată)
    (r"ilumin\w*\s+(?:in\s+|de\s+|al\s+)?piscin\w*(?:\s+(?:la\s+)?12\s*v)?", "iluminat", "Iluminat piscină (SELV 12 V)"),
    # r8 (locuințe #43): „iluminat LED 12V” = circuit de iluminat prin trafo SELV (nu se pierde)
    (r"ilumin\w*\s+(?:led\s+)?(?:la\s+|de\s+)?(?:12|24)\s*v\b(?:\s+(?:led|selv))?|\b(?:banda\s+|benzi\s+)?led\w*\s+(?:la\s+)?"
     r"(?:12|24)\s*v\b", "iluminat", "Iluminat SELV 12/24 V"),
    (r"\bjacuzzi\w*|\bcad\w*\s+cu\s+hidromasaj|\bhidromasaj\w*", "alt_circuit", "Jacuzzi"),
    (r"\bfrigider\w*(?!\s+industrial)(?:\s+separat\w*)?|\bcongelator\w*|\blad\w*\s+frigorific\w*", "alt_circuit", "Frigider"),
    (r"\brezistent\w*(?:\s+(?:electric\w*|de\s+incalzire|aditional\w*|de\s+rezerva|de\s+backup|boiler\w*))?"
     r"(?!\s*(?:a\s+)?(?:priz|de\s+dispersie|de\s+pamant|de\s+izolati|\d+(?:[.,]\d+)?\s*(?:ω|ohm)))", "incalzire_electrica",
     "Rezistență electrică"),
    (r"hidrofor\w*|pomp\w*\s+(?:de\s+)?(?:apa|put\w*|foraj\w*)|pomp\w*\s+submersibil\w*", "pompa_apa", "Pompă apă"),
    (r"poart\w*\s+automat\w*|automatizare\w*\s+poart\w*|motor\w*\s+poart\w*", "poarta_automata", "Poartă automată"),
    # r8 (locuințe #4): „ușa de garaj” (motorul ușii secționale) = circuit separat
    (r"\bus[ai]\w*\s+(?:de\s+)?garaj\w*|\bus[ai]\w*\s+sectional\w*|\bmotor\w*\s+us[ai]\w*", "poarta_automata", "Ușă garaj"),
    # r8 (locuințe #43): „contracurent 3 kW” (pompa de înot contra curent a piscinei)
    (r"\bcontra[\s-]*curent\w*|\binot\s+contra\s+curent\w*", "alt_circuit", "Contracurent piscină"),
    (r"\bplit\w*(?:\s+(?:cu\s+|pe\s+)?inductie)?(?:\s+electric\w*)?|\binductie\b|aragaz\w*(?:\s+electric\w*)?",
     "plita", "Plită"),
    (r"cuptor\w*(?:\s+electric\w*)?", "cuptor", "Cuptor"),
    (r"aer\w*\s+conditionat\w*(?:\s+split\w*)?|aparat\w*\s+de\s+aer(?:\s+conditionat\w*)?|\bclim\w*|\bac\b(?:\s+split\w*)?"
     r"|\bsplit\w*|\baircon\w*",
     "aer_conditionat", "Aer condiționat"),
    (r"\bsaun\w*", "sauna", "Saună"),
    (r"incalzitor\w*(?:\s+(?:de\s+)?prosop\w*)?|port[\s-]*prosop\w*(?:\s+electric\w*)?|\bradiator\w*\s+(?:de\s+)?baie",
     "incalzire_electrica", "Încălzitor prosop"),                                    # r10 (locuințe #56)
    (r"incalzire\w*\s+(?:in\s+pardoseala\s+)?electric\w*|\binc(?:alzire)?\w*\s+(?:in\s+)?pardoseal\w*|convector\w*|calorifer\w*\s+electric\w*"
     r"|radiator\w*\s+electric\w*|pardoseal\w*\s+electric\w*", "incalzire_electrica", "Încălzire electrică"),
    (r"\bcentral\w*(?:\s+termic\w*)?(?:\s+(?:pe|cu)\s+(?:gaz\w*|peleti|lemne))?", "centrala_termica", "Centrală termică"),
    (r"\bboiler\w*", "boiler", "Boiler"),
    (r"priz\w*\s+(?:de\s+|din\s+|la\s+)?bucatari\w*", "prize_bucatarie", "Prize bucătărie"),
    (r"priz\w*\s+(?:de\s+|din\s+|la\s+)?bai\w*(?:\s+(?:parter|etaj)\w*)?", "prize_baie", None),
    (r"priz\w*\s+(?:de\s+|din\s+)?(?:exterior\w*|curte|gradin\w*|teras\w*)", "prize_exterior", "Prize exterior"),
    # r8 (locuințe #43): „pompă 1,5 kW” fără alt context = pompă de apă (filtrare / hidrofor), nu pompa de căldură
    (r"\bpomp\w*(?!\s+(?:de\s+)?caldur)(?=\s+\d|\s+(?:de\s+)?\d)", "pompa_apa", "Pompă"),
    (r"\bpriz\w*" + _CAMERA, "prize", None),
    (r"\bilumin\w*" + _CAMERA, "iluminat", None),
]
RECEPTORI_LOC = [(re.compile(rx), rec, nume) for rx, rec, nume in RECEPTORI_LOC]
ENUM_RECEPTORI_LOC = ("iluminat", "prize", "prize_bucatarie", "prize_baie", "prize_exterior", "masina_spalat_rufe",
                      "masina_spalat_vase", "uscator", "boiler", "cuptor", "plita", "aer_conditionat", "pompa_caldura",
                      "centrala_termica", "incalzire_electrica", "vehicul_electric", "pompa_apa", "poarta_automata",
                      "sauna", "alt_circuit")
GENERICE_LOC = {"iluminat", "prize", "prize_bucatarie", "prize_baie", "prize_exterior"}
TRI_POSIBIL_LOC = {"plita", "pompa_caldura", "vehicul_electric", "sauna"}
FAZE_LOC = ("L1", "L2", "L3", "3F")
P_PRAG_3F_KW = 7.4                 # peste 7,4 kW (32 A monofazat) un receptor trifazabil se leagă pe 3F
P_PRAG_MONO_LOC_KW = 11            # peste → se recomandă branșament trifazat
_NUMERAL = {"un": 1, "o": 1, "doua": 2, "doi": 2, "trei": 3, "patru": 4, "cinci": 5}
RE_STOP_LOC = re.compile(r"(?<!\d),|,(?!\d)|;|:|\.(?:\s|$)|\s(?:si|plus|cu|iar|coloan\w*|cablu\w*|bransament\w*"
                         r"|beneficiar\w*|client\w*|putere\w*|aprobat\w*"
                         r"|in(?!\s+(?:\d+|doua|trei|patru|cinci)\s+(?:camere|dormitoare|incaperi|spatii)"
                         r"|\s+(?:bai|baie|bucatarie|living|dormitor\w*|hol|birou|camer\w*)\b)|din|la|jud\w*"
                         r"|pe\s+(?=cas|apartament|locuint|bransament|retea|bmp)"
                         r"|pentru|retea|schema|dar|insa|am\s+doar|avem|casa|apartament\w*|ap)\b")   # r9 (#14)
RE_PRE_MULT = re.compile(r"(?:(?<![\d+.,×])(?P<n>\d+)|\b(?P<w>doua|doi|trei|patru|cinci))\s*[x×]?\s*"
                         r"(?:(?:aparate|aparat|circuite|circuit|bucati|buc\.?|unitati)\s+(?:de\s+)?"
                         r"|(?:bai|camere|dormitoare|nivele|etaje)\s+(?:cu\s+)?)?$")
RE_NEGATIE_LOC = re.compile(r"\bfara\s+(?:\w+\s+)?$|(?<![\d.,])\b0\s+(?:circuite\s+)?(?:de\s+)?$|\bnici\s+un\w*\s+(?:circuit\s+)?(?:de\s+)?$")
RE_GAZ_DUPA = re.compile(r"^\s*(?:pe\s+|cu\s+|la\s+|pe\s+baza\s+de\s+)?gaz\w*")

# seturi tipice (nume, receptor) — presupuse când descrierea nu listează circuitele
SET_TIPIC = {
    "apartament": [("Iluminat", "iluminat"), ("Prize camere", "prize"), ("Prize bucătărie", "prize_bucatarie"),
                   ("Prize baie", "prize_baie"), ("Mașină de spălat rufe", "masina_spalat_rufe")],
    "casa_parter": [("Iluminat interior", "iluminat"), ("Iluminat exterior", "iluminat"), ("Prize camere", "prize"),
                    ("Prize living", "prize"), ("Prize bucătărie", "prize_bucatarie"),
                    ("Prize baie", "prize_baie"), ("Mașină de spălat rufe", "masina_spalat_rufe"),
                    ("Boiler", "boiler"), ("Centrală termică", "centrala_termica"), ("Prize exterior", "prize_exterior")],
    "casa_p1": [("Iluminat parter", "iluminat"), ("Iluminat etaj", "iluminat"), ("Iluminat exterior", "iluminat"),
                ("Prize parter", "prize"), ("Prize etaj", "prize"), ("Prize bucătărie", "prize_bucatarie"),
                ("Prize baie parter", "prize_baie"),
                ("Prize baie etaj", "prize_baie"), ("Mașină de spălat rufe", "masina_spalat_rufe"),
                ("Mașină de spălat vase", "masina_spalat_vase"), ("Boiler", "boiler"),
                ("Centrală termică", "centrala_termica"), ("Prize exterior", "prize_exterior")],
}
SET_BAZA = [("Iluminat", "iluminat"), ("Prize", "prize"), ("Prize bucătărie", "prize_bucatarie"),
            ("Prize baie", "prize_baie")]
DESCR_LOCUINTA = {"apartament": "apartament", "casa_parter": "casă parter", "casa_p1": "casă P+1"}


def _gaseste_receptori(t: str) -> list[dict]:
    """Receptorii numiți în text (fără suprapuneri, în ordinea din text), cu multiplicator / P / L / „trifazat”."""
    ocupat = [(m.start(), m.end()) for m in RE_PRIZA_PAMANT.finditer(t)]      # „priză de pământ” ≠ circuit de prize
    gasiti = []
    for rx, rec, nume in RECEPTORI_LOC:
        for m in rx.finditer(t):
            if any(m.start() < e and s < m.end() for s, e in ocupat):
                continue
            ocupat.append((m.start(), m.end()))
            if rec == "prize" and re.search(r"(?:incarc\w*|wallbox\w*|\bve\b|\bev\b|statie\w*)[^,;]{0,30}\b(?:in|la|din)\s+$",
                                            t[max(0, m.start() - 45):m.start()]):
                continue                       # r8 (#42): „încărcător EV 3,7 kW în priza din garaj” — priza VE-ului

            # r5 (P1-10): „fără plită”, „plită gaz” → receptorul NU există ca circuit electric
            exclus = bool(RE_NEGATIE_LOC.search(t[max(0, m.start() - 20):m.start()])) or (
                rec in ("plita", "cuptor") and bool(RE_GAZ_DUPA.match(t[m.end():])))
            gasiti.append({"s": m.start(), "e": m.end(), "receptor": rec, "nume": nume, "exclus": exclus})
    gasiti.sort(key=lambda g: g["s"])
    for i, g in enumerate(gasiti):
        urm = gasiti[i + 1]["s"] if i + 1 < len(gasiti) else len(t)
        ms = RE_STOP_LOC.search(t, g["e"])
        stop = min(urm, ms.start() if ms else len(t), g["e"] + 40)
        coada = t[g["e"]:stop]
        # r6 (N41): „saună 9 kW în curte la 30 m” — lungimea circuitului
        ml = re.match(rf"\s*(?:in|din)\s+(?:curte|gradin\w*|exterior\w*|anexa|garaj\w*|pod\w*|subsol\w*|beci\w*|foisor\w*)"
                      rf"(?:\s+la)?\s+({NUM})\s*(?:m|metri|ml)\b", t[stop:])
        if ml and (i + 1 == len(gasiti) or stop + ml.end() <= urm):
            stop += ml.end()
            coada = t[g["e"]:stop]
        g["coada_e"] = stop
        n = 1
        m = re.search(r"(?:^|\s)[x×]\s*(\d+)\b|\(\s*(\d+)\s*(?:buc\w*\.?)?\s*\)"
                      r"|\b(\d+|doua|doi|trei|patru|cinci)\s*(?:bucati|bucata|buc\b\.?|aparate|unitati)"
                      r"|\bin\s+(\d+|doua|trei|patru|cinci)\s+(?:camere|dormitoare|incaperi|spatii)\b", coada)
        if m:
            v = next(x for x in m.groups() if x)
            n = _NUMERAL.get(v) or int(v)
        mx = re.match(rf"\s*(\d+)\s*×\s*{NUM}\s*k?w\b", coada) or \
            re.search(rf"\(\s*(\d+)\s*×\s*{NUM}\s*k?w\b", coada)        # r6 (N39): „AC 3x2.5kw”; r8: „în băi (2 x 1,5 kW)”

        if mx and n == 1:
            n = int(mx.group(1))
        mp = RE_PRE_MULT.search(t[:g["s"]])
        g["s_tot"] = g["s"]
        if mp and n == 1:
            n = int(mp.group("n")) if mp.group("n") else _NUMERAL[mp.group("w")]
            g["s_tot"] = mp.start()
        g["n"] = max(1, min(n, 20))
        m = re.search(rf"(?<![\w.,])({NUM})\s*(kw|w)\b", coada)
        g["P"] = numar(m.group(1)) * UNITATI[m.group(2)][1] if m else None
        if m and re.match(r"\s*termic\w*", coada[m.end():]):
            # r8 (P1 locuințe #40): „pompă de căldură 12 kW termic … consum electric ~3 kW” — puterea electrică contează
            me = re.search(rf"(?:consum\w*|putere\w*|absorbit\w*)\s+electric\w*\s*(?:de\s+)?(?:≈|cca\.?|circa|aprox\.?|max\.?)?\s*"
                           rf"({NUM})\s*kw\b", t[g["e"]:g["e"] + 90])
            g["P_termic"] = g["P"]
            g["P"] = numar(me.group(1)) if me else None
            if me:
                g["coada_e"] = max(stop, g["e"] + me.end())
        if g["P"] is None:                                   # r6 (N01): „plită inducție 7.2, cuptor 3” — kW implicit
            mb = re.match(rf"\s*(?:de\s+)?(?:inductie\s+|electric\w*\s+)?({NUM})(?![\d.,]|\s*(?:a|m|l|ml|mm\w*|kwh|kva|v|buc\w*"
                          rf"|×|x|cam\w*|%)\b|\s*[×x(])", coada)
            if mb and 0.05 <= numar(mb.group(1)) <= 30:
                g["P"], g["P_fara_unitate"] = numar(mb.group(1)), True
        m = re.search(rf"(?<![\w.,])({NUM})\s*(m|metri|ml)\b", coada)
        g["L"] = numar(m.group(1)) if m else None
        g["tri"] = bool(re.search(r"trifaz\w*|\b3f\b|\b400\s*v\b", coada))
        g["mono"] = bool(re.search(r"monofaz\w*|\bmono\b|\b1f\b|\b230\s*v\b", coada))   # r5 (P1-11)
    return gasiti


def _tip_locuinta(t: str) -> str:
    if re.search(r"\bapartament\w*|\bgarsonier\w*|\bapt\b|\bap\.?\s+(?=\d|cam|bloc|et|mono|tri|la\s+bloc)"
                 r"|\b(?:la|in|de)\s+bloc\b", t):                  # r9 (#44): „ap. la bloc”

        return "apartament"
    if re.search(r"(?<![\w+])p\s*\+\s*[1-3m]\b|\betaj\w*|\bmansard\w*|\bduplex\b", t):
        return "casa_p1"
    return "casa_parter"


def _e_locuinta(c: Ctx) -> bool:
    """Casă / apartament. r5: (1) „P+2”, „parter”, „mansardă” singure nu fac o locuință dacă textul numește un tablou
    (TG/TE/TD/plecări — „tg birouri P+2”); (2) „kVA” sub 100 la o casă = puterea aparentă a branșamentului, nu PT;
    (3) „casă … branșament …” rămâne locuință dacă locuința e subiectul (numită înaintea branșamentului) sau are
    circuite/receptori; „branșament … casă” fără circuite rămâne branșament. Prosumator / CEF / GE / PT au prioritate
    (tratate în detecteaza_tip)."""
    t = _masca(c.t, RE_NU_CASA)
    # r8 (industrial #36): „TE apartament de serviciu 230V din TG …” = tablou secundar într-o clădire, nu locuință cu BMPM
    if re.search(r"\b(?:te|td|tablou\w*)\s+(?:\w+\s+){0,2}?(?:apartament\w*|garsonier\w*)\b", t) and \
            re.search(r"\bdin\s+(?:tg\w*|td\w*|tablou\w*)\b", t) and not re.search(r"\bbmp[mt]|\bbransament|\bcas(?:a|ei)\b", t):
        return False
    tare, slab = RE_CASA_TARE.search(t), RE_CASA_SLAB.search(t)
    if tare:            # r7: „TE la etaj”, „garaj … tablou secundar”, „al doilea corp cu TD” = tabloul secundar AL CASEI
        lst = list(t)
        for rx in RE_TD_LOC:
            for m in rx.finditer(t):
                for gname in ("td", "loc"):
                    lst[m.start(gname):m.end(gname)] = " " * (m.end(gname) - m.start(gname))
        t = "".join(lst)
        # r9 (#35): „TG la parter” (TG-ul casei) lângă TD-urile casei nu face din text un tablou industrial
        t = _masca(t, re.compile(r"\btg\b(?=\s+(?:la|de\s+la|in|din|al)\s+(?:parter\w*|cas\w*|locuint\w*))"))
        if not _tablou_numit_t(c, t):
            if any(rx.search(c.t) for rx in RE_TD_LOC):
                return True
    tablou = _tablou_numit_t(c, t) and not re.search(r"tablou\w*\s+(?:de\s+|al\s+)?(?:casa|casei|locuint|apartament)", t)
    if not (tare or slab):
        # r6 (N29): „branșament monofazat existent 7 kW, pompă de căldură 9 kW trifazată” = locuință (receptoare casnice)
        # r7 (#55, #56, #58): „pompă de căldură 16 kW + rezistență 9 kW, tri 20 kW tt”, „AC x3, mono 7 kW” — receptoare
        # casnice + rețea declarată + puterea alimentării, fără tablou / context comercial = locuință
        casnic = any(g["receptor"] not in GENERICE_LOC and not g["exclus"] for g in _gaseste_receptori(t))
        if tablou or RE_COMERCIAL.search(t) or not casnic:
            return False
        if any(v["val"] > 30 for v in valori(t) if v["marime"] in ("kW", "kVA")):
            return False                              # r10 (industrial #25): „cuptor electric 72 kW la 400V” ≠ casă
        if re.search(r"\bbmpm|\bbmpt|bransament", t):
            return True
        return bool((RE_TRI_DECLARAT.search(t) or RE_MONO_DECLARAT.search(t)) and re.search(rf"{NUM}\s*(?:kw|a)\b", t)
                    and not re.search(r"\bmotor\w*|\bcompresor\w*|\bstrung\w*|\bfreza\w*", t))
    if tablou and RE_COMERCIAL.search(t):
        return False                                 # r6 (industrial #6): „TG supermarket … prize casa marcat”
    if not tare and RE_COMERCIAL.search(t):
        return False                                 # r9 (industrial #11): „magazin alimentar parter, … TT” ≠ locuință
    if not tare and (RE_TABLOU_CUV.search(t) and not re.search(r"tablou\w*\s+(?:de\s+)?(?:casa|locuint|apartament)", t)
                     or re.search(r"\bTE\b", c.orig) or re.search(r"\bhala\b|\bbirou\w*|\bindustrial", t)):
        return False
    if _pt_explicit(c) or any(v["val"] >= 100 for v in valori(t) if v["marime"] == "kVA"):
        return False
    mb = re.search(r"\bbmpm|\bbmpt|bransament|\bfirida", t)
    if mb:
        if re.search(r"tablou|circuit|plecar", t) or _gaseste_receptori(t):
            return True
        return bool(tare and tare.start() < mb.start())
    return True


_CUV_ALIMENTARE = re.compile(
    r"(?:cas(?:a|ei|e|uta)|locuint\w*|apartament\w*|garsonier\w*|vil(?:a|e|ei)|duplex|bloc|ap|apt|cam|camere|bransament\w*"
    r"|bmp[mt]\w*|firida|mono\w*|tri\w*|trif|1f|3f|faz[ae]|nul|tn\w*|tt|tns|tncs|schema|sistem|putere\w*|total\w*|noua|nou"
    r"|vech\w*|existent\w*|parter|etaj\w*|mansard\w*|p|m|de|cu|la|si|pe|in|al|o|un|una|doua|doi|am|doar|fara|pamant|nu"
    r"|stiu|sau|subteran|aerian|marire|majorare|putere|aprob\w*|max\w*|absorbit\w*|consum\w*|v|\d+|\d+v|\d+[a-z]?|[a-z]"
    r"|tg|tablou\w*|general|mare|mic[aă]?|normala|individual\w*"
    r"|aprox\w*|cca|circa|cam|aproximativ|et|etajul|palier\w*|nr|tip|instalat\w*|contractat\w*|ok|vreau|are|e|este"
    r"|avem|contract\w*|abonament\w*|clientul|clientului|beneficiarul|proprietarul|actual\w*|curent\w*"
    r"|pentru|pt|aprobati|aprobata|aprobat)")   # r9 (#2, #8); r10 (#40): „… cu ATS pentru casa 15 kW tri”


RE_NU_RETEA_LOC = re.compile(
    r"\b(?:te|td|tablou\w*)(?:\s+(?!monofaz|trifaz|mono\b|tri\b)[\w-]+){0,2}\s+(?:monofazat\w*|mono|trifazat\w*|tri)\b"
    r"|\b(?!(?:cas[ae]|casei|casa|locuint\w*|apartament\w*|bransament\w*|pa|putere\w*|trifazat\w*|monofazat\w*|tri|mono|"
    r"vila|garsonier\w*|alimentare|retea\w*|q|de)\b)[a-z]{3,}(?:\s+de)?\s+\d+(?:[.,]\d+)?\s*(?:kw|kva)\s+"
    r"(?:monofazat\w*|mono|trifazat\w*|tri)\b"
    r"|\b(?:aparat\w*\s+de\s+)?sudur\w*[^,;.]{0,20}?(?:monofazat\w*|trifazat\w*)"
    r"|(?<=\s\s\s)(?:monofazat\w*|trifazat\w*)(?=\s+\d|\s+cu\b)")      # adjectivul unui element deja citit (TE …)


def _contradictii_locuinta(c: Ctx, intr: dict, al: dict, retea):
    """r7 (P0 #19): un receptor care nu încape în alimentare → întrebare (I08), nu desen: P receptor > P aprobată,
    Ib receptor > Q branșament, VE > 7,4 kW / receptor > 9,2 kW (40 A) pe monofazat."""
    pa, q = al.get("P_aprobata_kW"), al.get("In_Q_bransament_A")
    for x in intr.get("circuite") or []:
        P = x.get("P_kW")
        if not P:
            continue
        if P > norme.LOCUINTA_P_CIRCUIT_MAX_KW:
            continue                                      # valoare neplauzibilă → I06 în verifica
        continuu = x["receptor"] in ("vehicul_electric", "pompa_caldura", "sauna", "incalzire_electrica")
        if pa and (P > pa + 1e-6 if continuu else P > 1.5 * pa):
            # sarcină de durată (VE, PdC, saună, încălzire) peste P aprobată; plita / cuptorul doar peste 1,5·Pa (simultaneitate)
            c.probleme.append(("I08", f"Contradicție: {x['nume']} {fmt(P)} kW > puterea aprobată {fmt(pa)} kW (I08).",
                               f"{x['nume']} de {fmt(P)} kW nu încape în {fmt(pa)} kW aprobați: mărire de putere"
                               + (" (branșament trifazat)" if retea == "mono" else "")
                               + f", sau receptor de cel mult {fmt(pa)} kW?"))
            return
        ib = P * 1000 / (U_MONO if (retea == "mono" or x.get("faza") in ("L1", "L2", "L3")) else U_TRI)
        if q and ib > q + 1e-6:
            c.probleme.append(("I08", f"Contradicție: {x['nume']} {fmt(P)} kW (≈ {fmt(ib, 0)} A) > Q branșament {fmt(q)} A (I08).",
                               f"Q branșament {fmt(q)} A nu acoperă {x['nume']} de {fmt(P)} kW: mărire de putere, sau "
                               "receptor mai mic?"))
            return
        if retea == "mono" and (x["receptor"] == "vehicul_electric" and P > P_PRAG_3F_KW + 1e-6 or P > 9.2 + 1e-6):
            c.probleme.append(("I08", f"Contradicție: {x['nume']} {fmt(P)} kW pe branșament monofazat (> "
                                      f"{fmt(P_PRAG_3F_KW if x['receptor'] == 'vehicul_electric' else 9.2)} kW / 32–40 A) (I08).",
                               f"{x['nume']} de {fmt(P)} kW e trifazat(ă): treceți pe branșament trifazat, sau "
                               + ("stație VE monofazată de 7,4 kW (32 A)?" if x["receptor"] == "vehicul_electric"
                                  else f"{x['nume'].lower()} monofazat(ă) de cel mult 9,2 kW?")))
            return


def _kw_alimentare(c: Ctx, tm: str, v) -> bool:
    """r7: valoarea kW e a alimentării dacă în clauza ei, înaintea ei, sunt doar cuvinte despre casă / rețea / branșament."""
    a = max([x.end() for x in re.compile(r"(?<!\d),|,(?!\d)|;|:|\+|\(|\)|[.?!](?=\s|$)|\bdar\b|\biar\b").finditer(tm, 0, v["s"])]
            or [0])                                         # r9 (#14): „vreau VE 22 kW dar am doar 11 kW tri”
    if re.search(r"(?<![\w.,])\d+\s*[×x]\s*$", tm[max(a, v["s"] - 8):v["s"]]):
        return False                                       # r8 (P0 #7): „2 x 1,5 kW” = receptoare, nu alimentarea
    cuv = re.findall(r"[a-z0-9+]+", tm[a:v["s"]].replace("+", " "))
    return all(_CUV_ALIMENTARE.fullmatch(w) for w in cuv)


def _circuit_loc(nume, rec, P=None, L=None, faza=None) -> dict:
    d = {"nume": nume, "receptor": rec}
    if P is not None:
        d["P_kW"] = _nr(P)
    if L is not None:
        d["L_m"] = _nr(L)
    if faza:
        d["faza"] = faza
    return d


def _combina_circuite(baza: list[dict], listati: list[dict]) -> list[dict]:
    """Setul tipic/de bază + receptorii listați: un receptor dedicat listat înlocuiește intrarea tipică de același fel;
    un circuit generic (iluminat/prize) listat cu același nume (sau fără date proprii) e deja acoperit de set."""
    # r5 (P1-12): „3 circuite prize” / „2 circuite iluminat” înlocuiesc circuitele generice de același fel din set
    numerotate = {l["receptor"] for l in listati if l["receptor"] in ("iluminat", "prize") and re.search(r"\s\d+$", l["nume"])}
    out = [dict(b) for b in baza if b["receptor"] not in numerotate]
    listat = [False] * len(out)
    for l in listati:
        idx = [i for i, b in enumerate(out) if b["receptor"] == l["receptor"] and not listat[i]]
        if l["receptor"] in GENERICE_LOC:
            acelasi = [i for i in idx if norm_nume(out[i]["nume"]) == norm_nume(l["nume"])]
            if acelasi:
                out[acelasi[0]], listat[acelasi[0]] = l, True
                continue
            if idx and not ("P_kW" in l or "L_m" in l) and norm_nume(l["nume"]) in ("iluminat", "prize", "priza"):
                continue                                               # „iluminat” / „prize” simplu: deja în set
            out.append(l)
            listat.append(True)
        elif idx:
            out[idx[0]], listat[idx[0]] = l, True
        else:
            out.append(l)
            listat.append(True)
    return out


def norm_nume(s: str) -> str:
    return re.sub(r"\s+", " ", _fara_diacritice(s or "")).strip()


RE_ATELIER = re.compile(
    rf"\b(?P<nume>atelier\w*|anex\w*|garaj\w*|sopron\w*|sur(?:a|ii)\b|tablou\s+secundar\w*|td\s+secundar\w*)"
    rf"(?P<mij>[^:;,]*?)(?:\s*:\s*|\s+cu\s+)(?P<lista>[^;]*)")


RE_GEN_LOC = re.compile(rf"\b(?:generator\w*|grup\w*\s+electrogen\w*|ge)(?:\s+(?:de\s+rezerva|de\s+backup|portabil\w*|diesel"
                        rf"|(?:pe|cu|pe\s+baza\s+de)\s+(?:benzina|motorina|diesel|gaz\w*|gpl)))*\s*(?:de\s+)?(?P<v>{NUM})\s*(?P<u>kva|kw)\b"
                        r"(?:\s+(?:mono|tri)\w*|\s+diesel|\s+(?:pe\s+)?(?:benzina|motorina|gpl))*"
                        r"(?P<com>(?:\s*,)?(?:\s+(?:cu|si|prin))?\s+(?:comutator\w*|inversor\w*|inversare\w*|comutare\w*|ats\b)"
                        r"(?:\s+(?:de\s+)?(?:sursa|surse))?(?:\s+(?:manual\w*|automat\w*))?)?")


def _generator_locuinta(c: Ctx, intr: dict):
    """r7 (locuințe #54): grupul electrogen al unei case = SURSĂ de rezervă (nu consumator): `generator` {P_kW | S_kVA,
    comutare: manual | automat} — cheie nouă; comutatorul manual 0-I-II ≠ ATS (mențiune)."""
    m = RE_GEN_LOC.search(c.mascat())
    if not m:
        return
    v = numar(m.group("v"))
    g = {"Sn_kVA": _nr(v)} if m.group("u") == "kva" else {"Sn_kVA": _nr(round(v / 0.8, 2)), "P_kW": _nr(v)}
    if m.group("u") != "kva":
        c.nota(f"GE {fmt(v)} kW → Sn = {fmt(v)}/0,8 = {fmt(v / 0.8, 2)} kVA (cosφ GE 0,8, presupus)")
    com = m.group("com") or ""
    g["comutare"] = "ATS" if re.search(r"automat|\bats\b", com) else "manual"
    if re.search(r"monofaz\w*|\bmono\b", c.t[m.start():m.end() + 20]) or (retea_declarata(c) == "mono" and not re.search(
            r"trifaz\w*|\btri\b", c.t[m.start():m.end()])):
        g["retea"] = "mono"                         # r10 (locuințe #10): GE monofazat (comutator 2P) — motorul îl acceptă
    mc = re.search(r"\bpe\s+(?:circuitele|consumatorii)\s*(?:de\s+baza|vital\w*|esential\w*|prioritar\w*|importan\w*)?\s*"
                   r"(?:\((?P<l1>[^)]*)\)|:\s*(?P<l2>[^.;]*))", c.t)
    if mc:      # r9 (locuințe #23): „GE cu ATS pe circuitele de bază (centrală, frigider, iluminat)” → doar acele circuite
        lst = mc.group("l1") or mc.group("l2") or ""
        cir = []
        for b in re.split(r",|\bsi\b", lst):
            gr = _gaseste_receptori(b.strip())
            if b.strip():
                cir.append({"nume": gr[0]["nume"] if gr and gr[0]["nume"] else nume_normalizat(b.strip()),
                            "receptor": gr[0]["receptor"] if gr else "alt_circuit"})
        if cir:
            g["circuite"] = cir
            c.foloseste(mc.start(), mc.end())
            c.nota("GE: alimentează doar circuitele " + ", ".join(x["nume"] for x in cir) + " (ge_rezerva.circuite — "
                   "tablou rezervat după comutator); restul casei doar din rețea")
    intr["ge_rezerva"] = g
    c.consumat.append((max(0, m.start() - 2), m.end()))
    c.nota(f"„{c.o(m.start(), m.end()).strip()}” = grup electrogen de {fmt(v)} {'kVA' if m.group('u') == 'kva' else 'kW'} ca "
           f"SURSĂ de rezervă a casei (nu circuit), comutare {'manuală (comutator 0-I-II, interblocat — nu ATS)' if g['comutare'] == 'manual' else 'automată (ATS)'} (ge_rezerva)")
    c.avert.append("GE ca sursă de rezervă: comutatorul de surse (0-I-II) se montează în amontele TG-ului casei, cu "
                   "separarea neutrului — verificați pe planșă ramura GE")


_LOC_TD = (r"etaj\w*|mansard\w*|garaj\w*|atelier\w*|anex\w*|corp(?:ul)?\s*(?:\d|[b-d]\b|doi|al\s+doilea)|al\s+doilea\s+corp|beci\w*"
           r"|piscin\w*|parter\w*"
           r"|subsol\w*|pod\b|foisor\w*|sopron\w*|parter\w*")
RE_TD_LOC = [
    # „TE la etaj”, „tablou secundar la mansardă”, „TD în garaj”
    re.compile(rf"\b(?P<td>te|td|tablou\w*(?:\s+secundar\w*)?)(?:\s+|-)(?:(?:la|de\s+la|din|pe|in|al|pentru)\s+)?(?P<loc>{_LOC_TD})"),
    # „al doilea (corp) cu TD”, „garaj … cu TD”, „corpul 2 cu tablou secundar”
    re.compile(rf"\b(?P<loc>{_LOC_TD}|al\s+doilea)\b[^,;:]{{0,40}}?\b(?:cu|are|si)\s+(?P<td>td|te|tablou\w*(?:\s+secundar\w*)?)\b"),
    # „garaj cu atelier separat la 30 m de casa, tablou secundar, …”
    re.compile(rf"\b(?P<loc>garaj\w*|atelier\w*|anex\w*|mansard\w*)\b[^;:]{{0,60}}?(?P<td>\btablou\s+secundar\w*|\btd\b)"),
]
RE_ITEM_CASA = re.compile(r"\bcas(?:a|ei)\b|\blocuint\w*|\btn-?c?-?s\b|(?<![\w-])tt(?![\w-])|\bbransament\w*|\bbmp[mt]\w*"
                          r"|\bpa\b|aprobat\w*|\b(?:mono|tri)\w*\s+\d")


class _Buc:
    def __init__(self, txt, s, e):
        self._t, self._s, self._e = txt, s, e

    def group(self, _=0):
        return self._t

    def start(self):
        return self._s

    def end(self):
        return self._e


def _bucati_simple(t: str):
    """bucățile unei enumerări separate prin „,” (nu zecimală), „;” sau „și” — cu pozițiile lor"""
    poz, out = 0, []
    for m in re.finditer(r"(?<!\d),|,(?!\d)|;|:|\bsi\b", t):
        out.append(_Buc(t[poz:m.start()], poz, m.start()))
        poz = m.end()
    out.append(_Buc(t[poz:], poz, len(t)))
    return out


def _tablouri_locuinta(c: Ctx):
    """r7 (locuințe #8, #21, #57): tabloul secundar al unei locuințe (TE la etaj, TD garaj / atelier, TD în corpul 2) —
    numele după loc, lungimea („la 30 m”, „60 m”), cablul („cablu 4x10 Al”) și circuitele lui (receptoarele cu sau fără
    putere); itemii care descriu casa („casa tri 20 kW tns”) închid lista. Cu circuite → `tablouri_secundare`; fără
    circuite → întrebare (nu se pierde, nu se desenează gol). Cablul / lungimea TD-ului NU sunt ale coloanei."""
    t = c.mascat()
    gas = []
    for rx in RE_TD_LOC:
        for m in rx.finditer(t):
            if not any(a <= m.start() < b or m.start() <= a < m.end() for a, b, _ in gas):
                gas.append((m.start(), m.end(), m))
    if not gas:
        return None
    gas.sort(key=lambda x: x[0])
    out = []
    for i, (a0, _, m) in enumerate(gas):
        lim = gas[i + 1][0] if i + 1 < len(gas) else len(t)
        if i + 1 < len(gas):                    # zona se oprește la clauza următorului TD
            lim = max([x.end() for x in re.compile(r"[,;:.]").finditer(t, 0, lim)] or [lim])
            lim = max(lim, m.end())
        td = _un_td_locuinta(c, t, m, lim)
        if td:
            out.append(td)
    return out or None


def _un_td_locuinta(c: Ctx, t: str, m, lim: int):
    loc = re.sub(r"\s+", " ", m.group("loc")).strip()
    loc_n = ("Corp 2" if re.search(r"doilea|doi|2", loc) else nume_normalizat(c.o(m.start("loc"), m.start("loc") + len(
        re.match(r"\w+", loc).group(0)))))
    pref = "TE" if m.group("td").strip() == "te" else "TD"
    td = {"nume": f"{pref} {loc_n}", "circuite": []}
    # zona TD-ului: de la începutul clauzei locului până la primul item care descrie casa
    a = max([x.end() for x in re.compile(r"[,;:]|\.(?:\s|$)").finditer(t, 0, min(m.start("loc"), m.start("td")))] or [0])
    zona_e, poz = m.end(), m.end()
    fara = []
    mse = re.search(r"\.(?:\s|$)", t[m.end():lim])               # r9: TD-ul ține până la sfârșitul propoziției
    lim = m.end() + mse.start() if mse else lim
    for it in re.finditer(r"(?:[^,;]|(?<=\d),(?=\d))+", t[m.end():lim]):
        txt = it.group(0)
        s_it = m.end() + it.start()
        if not txt.strip():
            continue
        if RE_ITEM_CASA.search(re.sub(r"\bdin\s+(?:tabloul|tg\w*|te)\s+(?:general\s+)?(?:al\s+)?cas(?:a|ei)\b", " ", txt)) \
                and not re.search(rf"\b(?:la|de)\s+{NUM}\s*m\b", txt):
            break
        zona_e = m.end() + it.end()
    zona = t[a:zona_e]
    mL = re.search(rf"(?:\bla\s+|\b)(?P<v>{NUM})\s*(?:m|metri|ml)\b", zona)
    if mL:
        td["L_m"] = _nr(numar(mL.group("v")))
    cab = {}
    mc = re.search(rf"(?:\bcablu\w*\s+(?:tip\s+)?(?P<tip>{_TIP_CABLU})?|\b(?P<tip2>{_TIP_CABLU})|\bcu\s+(?=[2-5]\s*[×x])"
                   rf"|\balimentat\w*\s+(?:cu\s+)?(?=[2-5]\s*[×x]))\s*(?P<c>[2-5])\s*[×x]\s*(?P<s>{NUM})"
                   rf"(?:\s*(?:mm2?|mm²|mmp))?(?:\s+(?P<mat>al|cu|aluminiu|cupru)\b)?", zona)
    if mc and numar(mc.group("s")) in SECTIUNI_CABLU:
        cab["S_fortat"] = _nr(numar(mc.group("s")))
        tip = mc.group("tip") or mc.group("tip2") or ""
        mat = mc.group("mat") or ("al" if tip.startswith(("a", "na")) else "cu" if tip else None)
        if mat:
            cab["material"] = "Al" if mat.startswith("al") else "Cu"
        td["cablu"] = cab
        td["_n_cond"] = int(mc.group("c"))
    # circuitele TD-ului: itemii cu receptor (casnic sau de atelier), cu sau fără putere
    for it in _bucati_simple(t[m.end():zona_e]):
        txt = it.group(0).strip()
        s_it = m.end() + it.start() + (len(it.group(0)) - len(it.group(0).lstrip()))
        mpar = re.match(r"(?:[(\s]|separat\w*|dedicat\w*|propriu\b)+(?=\(|[a-z0-9])\(?", txt)  # r9 (#17): „separat (prize”
        if mpar and mpar.end():
            txt, s_it = txt[mpar.end():], s_it + mpar.end()
        mpar = re.match(r"[(\s]+", txt)                          # r8 (#45): „(iluminat 2 circ, …, AC 2)”
        if mpar:
            txt, s_it = txt[mpar.end():], s_it + mpar.end()
        taiat = False
        if mc and s_it <= mc.start() + a < s_it + len(txt):       # „AC 2) cu cablu 5x6 20m” — cablul TD-ului, nu circuit
            txt = re.sub(r"\s*(?:\bcu\s*)?$", "", txt[:mc.start() + a - s_it])
            taiat = True
        txt = txt.rstrip(" )")

        mcu = re.match(r"(?:cu|si|plus)\s+", txt)
        if mcu:
            txt, s_it = txt[mcu.end():], s_it + mcu.end()
        if not txt or re.match(r"(?:tablou\s+secundar\w*|td|te|separat\w*|legat\w*|alimentat\w*|in\s+curte)\b", txt) \
                or re.match(rf"(?:la\s+)?{NUM}\s*m\b", txt) or (mc and not taiat and it.start() + m.end() <= mc.start() + a < it.end() + m.end()):

            continue
        if not (RE_ATOM_REC.search(txt) or _gaseste_receptori(txt) or re.search(r"\bsudur\w*|\baparat\w*|\bunelt\w*", txt)
                or re.search(rf"^[a-z][a-z ]{{1,30}}\s+{NUM}\s*(?:kw|a)\b", txt)):     # r9 (#35): „flex 2,2 kW”
            continue
        mv = re.search(rf"(?<![\w.,])(?:(?P<n>\d+)\s*[×x]\s*)?(?P<v>{NUM})\s*(?P<u>kw|a|cp)\b", txt)
        nume_t = txt[:mv.start()].strip() if mv else txt
        nume = nume_normalizat(c.o(s_it, s_it + len(nume_t)))
        mcnt = re.match(r"(?P<nume>[a-z][a-z ]*?)(?:\s+(?P<n>\d{1,2})\s*(?:circ\w*\.?|buc\w*\.?|circuite)?)?$", txt) if not mv else None
        if not mv and not mcnt:                                  # r9 (#3, #35): „4 circuite prize”, „2 iluminat”, „1 AC”
            mcnt = re.match(r"(?P<n>\d{1,2})\s*(?:circ\w*\.?\s+|buc\w*\.?\s+|circuite\s+)?(?:de\s+)?(?P<nume>[a-z][a-z ]*?)$", txt)
        if mcnt:

            # r8 (locuințe #45, #46): „prize 4 circ”, „iluminat 2”, „AC 2” = numărul de circuite; calibrul uzual (presupus)
            gr = _gaseste_receptori(mcnt.group("nume"))
            rec_l = gr[0]["receptor"] if gr else receptor_dupa_nume(mcnt.group("nume"), 1, True)
            if rec_l in CALIBRU_IMPLICIT_CASNIC or (gr and rec_l not in ("alt_circuit",)):
                # circuitele casnice fără putere ale TD-ului: receptorul + numărul de circuite; puterea implicită o pune
                # motorul (declarată: iluminat 1 kW, prize 2 kW, AC din tabelul receptoarelor) — nu un calibru ca sarcină
                n_c = int(mcnt.group("n") or 1)
                nume_c = gr[0]["nume"] if gr and gr[0]["nume"] else nume_normalizat(c.o(s_it + mcnt.start("nume"), s_it + mcnt.end("nume")))
                for kk in range(1, n_c + 1):
                    td["circuite"].append({"nume": nume_c if n_c == 1 else f"{nume_c} {kk}", "receptor": rec_l})
                td.setdefault("_presupus", []).append(f"{nume_c} × {n_c}")
                continue
        if not mv:
            fara.append(txt)
            continue

        v = numar(mv.group("v")) * (KW_PE_CP if mv.group("u") == "cp" else 1)
        mn = re.search(r"\s*(\d+)\s*(?:circuite|circuit|circ\.?|buc\w*)\s*$", nume_t) or \
            re.search(r"^\s*(\d+)\s*(?:circuite|circuit|circ\.?|buc\w*)?\s+", nume_t)
        if mn:
            nume = nume_normalizat(re.sub(r"\s*\d+\s*(?:circuite|circuit|circ\.?|buc\w*)?\s*", " ", nume_t).strip())
        k = {"nume": nume, ("In_A" if mv.group("u") == "a" else "P_kW"): _nr(v)}
        if mn and int(mn.group(1)) > 1:
            k["n_circuite"] = int(mn.group(1))
        rec = receptor_dupa_nume(nume, 1, True)
        gr = _gaseste_receptori(nume_t)
        if gr and gr[0]["receptor"] not in ("alt_circuit",):     # r9 (#3): „2 AC 3,5 kW” = aer condiționat
            k["receptor"] = gr[0]["receptor"]
            if gr[0]["nume"] and len(nume) <= 3:
                k["nume"] = gr[0]["nume"]
        elif rec in ("motor", "prize", "iluminat"):
            k["receptor"] = rec
        coada = txt[mv.end():]
        if re.search(r"monofaz\w*|\bmono\b|\b230\s*v\b", coada + " " + nume_t):
            k["retea"] = "mono"
        elif re.search(r"trifaz\w*|\btri\b|\b3f\b|\b400\s*v\b", coada + " " + nume_t):
            k["retea"] = "tri"
        td["circuite"].append(k)
    c.consumat.append((a, zona_e))
    td["_txt"] = c.o(a, zona_e).strip(" ,;")
    td["_fara"] = fara
    return td


def _atelier_locuinta(c: Ctx):
    """r6 (N08): „atelier în curte la 40 m: strung 4 kW, compresor 3 kW, prize 16A” = tablou secundar alimentat din TE
    → `tablouri_secundare` [{nume, L_m, circuite: [{nume, P_kW | In_A, receptor?}]}] (receptoarele se păstrează)."""
    m = RE_ATELIER.search(c.mascat())
    if not m or not valori(m.group("lista")):
        return None
    mL = re.search(rf"\bla\s+({NUM})\s*(?:m|metri|ml)\b", m.group("mij"))
    c.consumat.append((m.start(), m.end()))
    td = {"nume": f"TD {nume_normalizat(c.o(m.start('nume'), m.end('nume')))}", "circuite": []}
    if mL:
        td["L_m"] = _nr(numar(mL.group(1)))
    s0 = m.start("lista")
    for mi in re.finditer(r"(?:[^,;]|(?<=\d),(?=\d))+", m.group("lista")):
        txt = mi.group(0)
        if not txt.strip():
            continue
        mv = re.search(rf"(?<![\w.,])(?:(?P<n>\d+)\s*[×x]\s*)?(?P<v>{NUM})\s*(?P<u>kw|a|cp)\b", txt)
        nume_t = txt[:mv.start()] if mv else txt
        nume = nume_normalizat(c.o(s0 + mi.start(), s0 + mi.start() + len(nume_t.rstrip())))
        if not mv or not nume.strip():
            c.fara_valoare.append(txt.strip())
            continue
        v = numar(mv.group("v")) * (KW_PE_CP if mv.group("u") == "cp" else 1)
        mn = re.search(r"\s*(\d+)\s*(?:circuite|circuit|circ\.?|buc\w*)\s*$", nume_t) or \
            re.search(r"^\s*(\d+)\s*(?:circuite|circuit|circ\.?|buc\w*)?\s+", nume_t)
        if mn:
            nume = nume_normalizat(re.sub(r"\s*\d+\s*(?:circuite|circuit|circ\.?|buc\w*)?\s*", " ", nume_t).strip())
        k = {"nume": nume, ("In_A" if mv.group("u") == "a" else "P_kW"): _nr(v)}
        if mn and int(mn.group(1)) > 1:
            k["n_circuite"] = int(mn.group(1))
        rec = receptor_dupa_nume(nume, 1, True)
        if rec in ("motor", "prize", "iluminat"):
            k["receptor"] = rec
        coada = txt[mv.end():]
        if re.search(r"monofaz\w*|\bmono\b", coada):
            k["retea"] = "mono"
        if mv.group("n") and int(mv.group("n")) > 1:
            k["n_circuite"] = int(mv.group("n"))
        td["circuite"].append(k)
    if not td["circuite"]:
        return None
    c.nota(f"„{c.o(m.start(), m.end()).strip()}” = tablou secundar {td['nume']} alimentat din TE"
           + (f" (L = {fmt(td['L_m'])} m)" if mL else "") + ": " + ", ".join(x["nume"] for x in td["circuite"]))
    return td


def extrage_locuinta(c: Ctx, intr, ex):
    t = c.t
    puteri = {}
    tipl = ex["locuinta"] = _tip_locuinta(t)
    if re.search(r"\batr\b|\baviz\w*\s+tehnic", t):
        ex["_din_atr"] = True
    mups = re.search(r"\b(?:ups|eps)(?:\s*/\s*(?:ups|eps))?\b[^,;.]*", t)
    if mups and not re.search(r"\binvert\w*|\bpanou\w*\b(?<!fara panouri)", _masca(t, re.compile(r"fara\s+panouri"))):
        # r9 (locuințe #53): „UPS/EPS pt pompa centralei și router, fără panouri” = sursă neîntreruptibilă, nu prosumator
        c.foloseste(mups.start(), mups.end())
        mdupa = re.search(r"\b(?:pt|pentru)\s+(?P<l>[^,;.]+)", t[mups.start():mups.end()])
        c._ups_loc = "UPS" + (f" ({nume_normalizat(mdupa.group('l')).lower()})" if mdupa else "")
        mfp = re.search(r"\bfara\s+panouri\b", t)
        if mfp:
            c.foloseste(mfp.start(), mfp.end())
        c.intrebari.append(("I02", f"„{c.o(mups.start(), mups.end()).strip()}”: UPS-ul (fără panouri) se desenează ca un circuit "
                                   "dedicat din TG spre UPS, cu consumatorii lui după UPS. Ce putere are UPS-ul (VA / kW)? "
                                   "(până atunci: circuit UPS 16 A, presupus)"))
    tds = getattr(c, "_td_loc", None) or None
    if not tds:
        a1 = _atelier_locuinta(c)
        tds = [a1] if a1 else []
    _generator_locuinta(c, intr)
    # circuitele (înainte de puterea generală: kW/A/m de lângă un receptor îi aparțin acestuia)
    gasiti = _gaseste_receptori(c.mascat())
    exclusi = {g["receptor"] for g in gasiti if g["exclus"]}
    for g in gasiti:
        c.consumat.append((g["s_tot"], g["coada_e"]))
        if g["exclus"]:
            mneg = RE_NEGATIE_LOC.search(t[max(0, g["s"] - 20):g["s"]])
            s0 = max(0, g["s"] - 20) + mneg.start() if mneg else g["s"]
            e0 = g["e"] + (RE_GAZ_DUPA.match(t[g["e"]:]).end() if RE_GAZ_DUPA.match(t[g["e"]:]) else 0)
            c.nota(f"„{c.o(s0, max(e0, g['e'])).strip(' ,')}” → fără circuit {g['nume'] or g['receptor']} electric")
    gasiti = [g for g in gasiti if not g["exclus"]]
    # rețeaua: din textul FĂRĂ cozile receptorilor („pompă de căldură trifazată” / „VE monofazată” țin de receptor);
    # nu se presupune
    tm0 = c.mascat()
    if RE_RETEA_NESTIUTA.search(tm0):
        retea_declarata(c)
        tm0 = _masca(tm0, RE_RETEA_NESTIUTA)
    tri = bool(RE_TRI_DECLARAT.search(_masca(tm0, re.compile(r"\bbmpm\w*"))))
    mono_decl = bool(RE_MONO_DECLARAT.search(tm0))
    if tri and mono_decl:
        # r11 (locuințe #14, #34): „TE parter monofazat”, „aparat de sudură 6 kVA monofazat” într-o casă trifazată — rețeaua
        # unui TABLOU SECUNDAR / a unui RECEPTOR nu e rețeaua branșamentului (contradicție doar pe ALIMENTARE)
        tm1 = _masca(tm0, RE_NU_RETEA_LOC)
        tri1 = bool(RE_TRI_DECLARAT.search(_masca(tm1, re.compile(r"\bbmpm\w*"))))
        mono1 = bool(RE_MONO_DECLARAT.search(tm1))
        if tri1 != mono1:
            for mm in RE_NU_RETEA_LOC.finditer(tm0):
                c.nota(f"„{c.o(mm.start(), mm.end()).strip()}” = rețeaua tabloului secundar / receptorului (nu a "
                       f"branșamentului) — instalația e {'trifazată' if tri1 else 'monofazată'}")
            tri, mono_decl = tri1, mono1
    if tri and mono_decl:
        c.probleme.append(("I08", "Contradicție: locuința e descrisă și monofazată, și trifazată (I08).",
                           "Branșamentul locuinței este monofazat (230 V) sau trifazat (3 × 400 V)?"))
    if tri or mono_decl:
        retea = ex["retea"] = intr["retea"] = "tri" if tri else "mono"
    else:                  # rețeaua NU se presupune: schimbă tot tabloul → se cere utilizatorului
        retea = ex["retea"] = None
        ex["_retea_lipsa"] = True
    listati, faza_mono = [], 0
    for g in gasiti:
        nume = g["nume"] or re.sub(r"\b[Ee]xt\b\.?", "exterior", nume_normalizat(c.o(g["s"], g["e"])))
        faza = None
        if g["mono"] and retea == "tri":
            faza = FAZE_LOC[faza_mono % 3]                              # r5 (P1-11): „monofazată” lângă receptor
            faza_mono += 1
            c.nota(f"„{c.o(g['s'], g['coada_e']).strip()}” = circuit monofazat (faza {faza})")
        elif g["receptor"] in TRI_POSIBIL_LOC and retea == "tri" and (g["P"] is None or g["P"] > P_PRAG_3F_KW or g["tri"]):
            faza = "3F"
        for k in range(1, g["n"] + 1):
            x = _circuit_loc(nume if g["n"] == 1 else f"{nume} {k}", g["receptor"], g["P"], g["L"], faza)
            if g["tri"] and faza == "3F":
                x["_tri_declarat"] = True
            listati.append(x)
        if g["n"] > 1:
            c.nota(f"„{c.o(g['s_tot'], g['coada_e']).strip()}” = {g['n']} circuite separate ({nume} 1…{g['n']})")
        if g.get("P_termic"):
            c.nota(f"{nume}: {fmt(g['P_termic'])} kW = puterea TERMICĂ; circuitul se dimensionează la puterea electrică "
                   + (f"{fmt(g['P'])} kW" if g["P"] else "(nescrisă — se cere)"))
            if not g["P"]:
                c.intrebari.append(("I02", f"{nume}: ce putere ELECTRICĂ absoarbe (kW)? {fmt(g['P_termic'])} kW e puterea "
                                           "termică."))
        if g.get("P_fara_unitate"):

            c.nota(f"„{c.o(g['s'], g['coada_e']).strip()}”: {fmt(g['P'])} fără unitate = {fmt(g['P'])} kW (presupus)")
        if g["tri"] and retea == "mono":
            c.probleme.append(("I08", f"Contradicție: „{c.o(g['s'], g['coada_e']).strip()}” trifazat la o locuință "
                                      "monofazată (I08).", "Branșamentul locuinței este trifazat (3 × 400 V)?"))
    for atelier in tds:
            txt, fara, n_cond = atelier.pop("_txt", None), atelier.pop("_fara", []), atelier.pop("_n_cond", None)
            pres_td = atelier.pop("_presupus", [])
            if pres_td:
                c.nota(f"{atelier['nume']}: circuite fără putere ({', '.join(pres_td)}) → puterea implicită a receptorului "
                       "(PRESUPUS, în Calcul)")
            cc_ = []
            for x in atelier.get("circuite") or []:                 # r8: „prize 3 x 2 kW” = 3 circuite (fiecare cu sarcina lui)
                if "In_A" in x:                                      # calibru dat: rămâne o linie cu n_circuite (r7)
                    cc_.append(x)
                    continue
                n_ = int(x.pop("n_circuite", 1) or 1)
                cc_ += [x] if n_ == 1 else [dict(x, nume=f"{x['nume']} {kk}") for kk in range(1, n_ + 1)]
            atelier["circuite"] = cc_

            if fara:
                c.fara_valoare += fara
            if n_cond == 4 and retea == "mono" or n_cond == 5 and retea == "mono":
                c.intrebari.append(("I08", f"{atelier['nume']}: cablul are {n_cond} conductoare, dar locuința e monofazată — TD-ul e "
                                           "trifazat (3F+N+PE) sau monofazat (cablu 3 conductoare)?"))
            if retea == "tri" and atelier["circuite"]:
                atelier["faza"] = "3F"
            if atelier["circuite"]:
                intr.setdefault("tablouri_secundare", []).append(atelier)
                ex["tablouri_secundare"] = intr["tablouri_secundare"]
                if txt:
                    c.nota(f"„{txt}” = tablou secundar {atelier['nume']} alimentat din TG-ul casei"
                           + (f" (L = {fmt(atelier['L_m'])} m)" if atelier.get("L_m") else "") + ": "
                           + ", ".join(x["nume"] for x in atelier["circuite"]))
            else:
                desc = ", ".join(x for x in (f"L = {fmt(atelier['L_m'])} m" if atelier.get("L_m") else None,
                                             f"cablu {fmt(atelier['cablu']['S_fortat'])} mm²"
                                             + (f" {atelier['cablu'].get('material')}" if atelier.get('cablu', {}).get('material')
                                                else "") if atelier.get("cablu") else None) if x)
                alte = []                                           # r8 (#47): „TD etaj, TD garaj” — toate tablourile numite
                for rx in (RE_TD_LOC if len(tds) == 1 else []):
                    for mm in rx.finditer(t):
                        nm = f"{'TE' if mm.group('td').strip() == 'te' else 'TD'} " + nume_normalizat(re.match(r"\w+", mm.group("loc")).group(0))
                        if nm.lower() != atelier["nume"].lower() and nm not in alte:
                            alte.append(nm)
                            c.foloseste(mm.start(), mm.end())
                numele = " și ".join([atelier["nume"]] + alte)
                c.intrebari.append(("I02", f"Ce circuite alimentează {numele}" + (f" ({desc})" if desc else "")
                                           + "? Până la răspuns toate circuitele sunt desenate în TG-ul casei, iar "
                                           f"{numele} nu apar pe planșă."))

    neg = [g for g in _gaseste_receptori(c.t) if g["exclus"] and g["receptor"] in ("iluminat", "prize")]
    if neg:                                       # r8 (#69): „0 circuite de prize, fără iluminat” — locuință fără circuite de bază
        c.intrebari.append(("I02", "Locuința fără " + " și fără ".join(dict.fromkeys(
            "circuite de iluminat" if g["receptor"] == "iluminat" else "circuite de prize" for g in neg))
            + "? Orice locuință are cel puțin un circuit de iluminat și unul de prize (cu DDR 30 mA) — confirmați lista."))
    plus = bool(re.search(r"tablou\w*\s+tipic|\bplus\b|\bin\s+plus\b|\bpe\s+langa\b|\bsi\s+restul\b", t))

    descr = DESCR_LOCUINTA[tipl]
    if tipl == "casa_p1" and any(re.search(r"etaj|mansard", _fara_diacritice(x["nume"]).lower())
                                 for x in intr.get("tablouri_secundare") or []):
        tipl_set = "casa_parter"           # r9 (#3, #35): circuitele etajului / mansardei sunt în TE / TD, nu dublate în TG
        c.nota("etajul / mansarda are tablou propriu → TG-ul casei cu circuitele parterului (fără dublare)")
    else:
        tipl_set = tipl
    for mm in re.finditer(r"\btg\b\s+(?:la|de\s+la|in|din|al)\s+(?:parter\w*|cas\w*|locuint\w*)", t):
        c.foloseste(mm.start(), mm.end())
    tipic = [_circuit_loc(n, r) for n, r in SET_TIPIC[tipl_set] if r not in exclusi]
    if not listati:
        circuite = tipic
        c.nota(f"circuitele nu sunt listate → set tipic pentru {descr}: " + ", ".join(x["nume"] for x in circuite)
               + f" ({len(circuite)} circuite) — PRESUPUNERE, corectați lista dacă diferă")
    elif plus or len(gasiti) < 3:
        circuite = _combina_circuite(tipic, listati)
        c.nota(f"set tipic pentru {descr} + receptorii listați ("
               + ", ".join(dict.fromkeys(x["nume"] for x in listati)) + f") = {len(circuite)} circuite — PRESUPUNERE, "
               "corectați lista dacă diferă")
    else:
        # r8 (#18): „Iluminat parter / Iluminat etaj” listate (cu P / L) acoperă circuitul de bază „Iluminat” — fără dublare
        acoperite = {r for r in GENERICE_LOC if sum(1 for x in listati if x["receptor"] == r
                                                    and "exterior" not in norm_nume(x["nume"])) >= 2}
        circuite = _combina_circuite([_circuit_loc(n, r) for n, r in SET_BAZA if r not in acoperite], listati)
        adaugate = [x["nume"] for x in circuite if x not in listati]
        c.nota(f"receptorii listați + circuitele de bază ale oricărei locuințe"
               + (f" ({', '.join(adaugate)})" if adaugate else "") + f" = {len(circuite)} circuite — PRESUPUNERE, "
               "corectați lista dacă diferă")
    for x in circuite:
        if retea == "tri" and x["receptor"] in TRI_POSIBIL_LOC and "faza" not in x and "P_kW" not in x:
            x["faza"] = "3F"                                           # din setul tipic, la rețea trifazată
        if x.pop("_tri_declarat", False):
            c.nota(f"{x['nume']}: declarat trifazat (3F)")
        elif x.get("faza") == "3F" and "P_kW" not in x:
            c.nota(f"{x['nume']}: receptor trifazat (3F) la rețeaua trifazată")
        elif x.get("faza") == "3F":
            c.nota(f"{x['nume']} {fmt(x['P_kW'])} kW > {fmt(P_PRAG_3F_KW)} kW → circuit trifazat (3F)")
    # r8 (locuințe #4): același receptor dedicat menționat de două ori („stație de încărcare la vilă … wallbox 11 kW”) —
    # mențiunea fără date se contopește cu cea cu putere / lungime
    cu_date = {x["receptor"] for x in circuite if x["receptor"] not in GENERICE_LOC and ("P_kW" in x or "L_m" in x)}
    circuite = [x for x in circuite if not (x["receptor"] in cu_date and "P_kW" not in x and "L_m" not in x
                                            and not re.search(r"\s\d+$", x["nume"]))]
    mlb = re.search(r"\bload\s*(?:balancing|management)\b|\bgestiun\w*\s+(?:dinamic\w*\s+)?(?:a\s+)?(?:sarcin\w*|puteri\w*)"
                    r"|\bechilibrare\w*\s+(?:a\s+)?(?:sarcin\w*|incarcar\w*)|\bdlm\b", t)
    if mlb:                                        # r8 (locuințe #41): gestiunea sarcinii la stațiile VE
        c.foloseste(mlb.start(), mlb.end())
        c.avert.append(f"„{c.o(mlb.start(), mlb.end()).strip()}”: gestiunea dinamică a sarcinii (load balancing) a stațiilor VE "
                       "— limitează curentul total la puterea aprobată; se precizează în memoriu (contorul / TC de la "
                       "intrare și comunicația cu stațiile), pe schemă stațiile au circuitele lor")
    if getattr(c, "_ups_loc", None):
        circuite.append(_circuit_loc(c._ups_loc, "alt_circuit"))
    intr["circuite"] = ex["circuite"] = circuite
    # alimentarea: P aprobată, Q branșament, coloana (din textul rămas după receptori)
    tm = c.mascat()
    vals = valori(tm)
    al = {}
    if re.search(r"bransament\w*\s+(?:\w+\s+)?nou|\bnou\w*\s+bransament|\bbmp[mt]\s+nou|racordare\s+nou"
                 r"|bransament\w*\s+(?:inca\s+)?nu\s+(?:avem|exista|e\b)|\bfara\s+bransament|\bvom\s+cere\b", t):
        al["tip"] = "bransament_nou"
    elif re.search(r"\bexistent", t):
        al["tip"] = "bransament_existent"
    # r8 (locuințe #6): datele OD din ATR — „Ik3 = 4,2 kA” (curent de scurtcircuit, NU calibru), „Zs = 0,45 ohm” (impedanța
    # buclei, NU RA)
    mik = RE_IK.search(tm)
    if mik:
        intr["Ik3_OD_kA"] = ex["Ik3_OD_kA"] = _nr(numar(mik.group("v")))
        c.consumat.append((mik.start(), mik.end()))
        c.nota(f"„{c.o(mik.start(), mik.end()).strip()}” = curentul de scurtcircuit la punctul de racord (Ik3_OD_kA, din ATR)")
    mzs = re.search(rf"\b(?:zs|z\s*s|z\s*bucl\w*|impedant\w*\s+(?:a\s+)?bucl\w*(?:\s+de\s+defect)?)\s*(?:=|:|de)?\s*"
                    rf"(?P<v>{NUM})\s*(?:ohm\w*|ω)", tm)
    if mzs:
        intr["Zb_OD_ohm"] = ex["Zb_OD_ohm"] = _nr(numar(mzs.group("v")))
        c.consumat.append((mzs.start(), mzs.end()))
        c.nota(f"„{c.o(mzs.start(), mzs.end()).strip()}” = impedanța buclei de defect a rețelei (Zb_OD_ohm, din ATR) — nu RA")
    if mik or mzs:
        tm = c.mascat()
        vals = valori(tm)
    # r5 (P0-6): „Pi” / „putere instalată” = informativ; „Pa” / „P aprobată” / „7 kW aprobat” = puterea aprobată

    mi = re.search(rf"(?:\bpi\b|\bp\s*instalat\w*|putere\w*\s+instalat\w*)\s*(?:de\s+|=\s*|:\s*)?({NUM})\s*(kw|mw)\b", tm)
    if mi:
        c.consumat.append((mi.start(), mi.end()))
        c.nota(f"„{c.o(mi.start(), mi.end()).strip()}” = putere instalată (informativ; bilanțul se face din circuite)")
        tm = c.mascat()
        vals = valori(tm)
    m = re.search(rf"(?:\bpa\b|putere\w*(?:\s+(?:aprob|maxim|absorbit|contractat)\w*\.?)?|aprob\w*\.?|\bp\s*aprob\w*\.?"
                  rf"|paprobat\w*)\s*(?:de\s+|=\s*|:\s*)?({NUM})\s*(kw|mw)\b|({NUM})\s*(kw|mw)\s+aprobat\w*", tm)
    if m:
        P = numar(m.group(1) or m.group(3)) * UNITATI[m.group(2) or m.group(4)][1]
    else:
        # r7 (P0 #16): fără „Pa / aprobat”, puterea aprobată e DOAR un kW legat de alimentare („trifazat 16 kW”, „casa 10 kW”,
        # „, 5 kW”) — niciodată kW-ul unui receptor necunoscut („pompa filtrare 1.1kw” rămâne la plasa de siguranță)
        P = next((v["val"] for v in vals if v["marime"] == "kW" and _kw_alimentare(c, tm, v)), None)
    S = _prima(vals, "kVA")
    if S and P is None:                            # r5 (P0-3): „22 kVA” la o casă = S branșament, nu PT
        c.foloseste(S["s"], S["e"])
        ib = S["val"] * 1000 / (U_TRI if retea != "mono" else U_MONO)
        c.nota(f"„{c.o(S['s'], S['e']).strip()}” = puterea aparentă a branșamentului (Ib = {fmt(ib)} A); P aprobată "
               "nedeclarată (kVA ≠ kW)")
    if P is not None:
        al["P_aprobata_kW"] = puteri["P_aprobata_kW"] = _nr(P)
    m = re.search(rf"\bq(?:[a-z]\w*)?\s*(?:bransament\w*\s*|general\s*)?(?:de\s+|=\s*|:\s*)?({NUM})\s*a\b"
                  rf"|(?:intrerupator|disjunctor|sigurant)\w*\s+(?:general\w*\s+)?(?:de\s+)?({NUM})\s*a\b", tm)
    Q = numar(m.group(1) or m.group(2)) if m else (_prima(vals, "A") or {}).get("val")
    if Q is not None:
        al["In_Q_bransament_A"] = puteri["In_Q_bransament_A"] = _nr(Q)
    m = (re.search(rf"coloan\w*\s*(?:de\s+|l\s*=\s*|:\s*)?(?:(?:≈|cca\.?|circa|aprox\.?|cam)\s*)?({NUM})\s*(m|metri|ml|km)\b", tm)
         or re.search(rf"cablu\w*\s*(?:de\s+)?(?:(?:≈|cca\.?|circa|aprox\.?|cam)\s*)?({NUM})\s*(m|metri|ml|km)\b", tm)
         or re.search(rf"({NUM})\s*(m|metri|ml|km)\s+(?:pana|până)\s+la\s+(?:tablou|bmp|firida|cas)", tm))
    if m:
        L = numar(m.group(1)) * UNITATI[m.group(2)][1]
    else:
        Lv = _lungime_generala(vals)
        L = Lv["val"] if Lv else None
        if Lv:
            c.nota(f"„{c.o(Lv['s'], Lv['e']).strip()}” = lungimea coloanei BMP → tabloul locuinței")
    if L is not None:
        al["L_coloana_m"] = _nr(L)
        ex["lungimi_m"] = {"coloana": _nr(L)}
    if RE_PRIZA_PAMANT.search(t):                  # „priză de pământ” nu descrie pozarea coloanei
        class _Fara:
            t = RE_PRIZA_PAMANT.sub(lambda m: " " * len(m.group(0)), c.t)
        ex["metoda"] = detecteaza_metoda(_Fara)
    cablu = {k: v for k, v in (("material", ex["material"]), ("izolatie", ex["izolatie"]),
                               ("metoda", ex["metoda"])) if v}
    imp = getattr(c, "_cablu_impus", None)          # r6 (N37, N43): „coloana Al 2.5mmp existentă”, „CYY-F 3x10”
    if imp:
        cablu.update(imp)
    if cablu:
        al["cablu"] = cablu
    intr["alimentare"] = al
    _contradictii_locuinta(c, intr, al, retea)
    # schema de legare la pământ, RA, ks
    schema_pamant(c, intr, ex)                     # r6: aceeași regulă la toate tipurile („tt”, contradicții, IT)
    ex.pop("RA_ohm", None)
    m = re.search(rf"\bks\s*(?:=|de|:)?\s*({NUM})", t)
    if m:
        intr["ks"] = ex["ks"] = _nr(numar(m.group(1)))
    return puteri


# =====================================================================================================
# Presupuneri (F.6) — generate din intrarea fizică (deci valabile și pentru calea LLM)
# =====================================================================================================
TEXT_OD = (f"Ik3max OD {fmt(norme.OD_IK3MAX_IMPLICIT_KA)} kA și Zbuclă OD {fmt(norme.OD_ZBUCLA_IMPLICIT_OHM[0], 2)} + "
           f"j{fmt(norme.OD_ZBUCLA_IMPLICIT_OHM[1], 2)} Ω (|Z| = 0,201 Ω) (valori implicite — introduceți datele din ATR)")
DESCR_METODA = {"D1": "în tub în pământ", "D2": "direct în pământ", "C": "aparent pe perete", "E": "pat de cabluri / în aer"}
TABEL_GRUPARE = {"D1": "B.52.19", "D2": "B.52.18", "C": "B.52.17", "E": "B.52.17"}


def _cablu_text(intr, implicit_mat="Al", implicit_met="D1"):
    cb = intr.get("cablu") or {}
    mat = intr.get("material") or cb.get("material") or implicit_mat
    iz = cb.get("izolatie") or "PVC"
    met = cb.get("metoda") or implicit_met
    return mat, iz, met


def _sn_standard(s_kva):
    return next((sn for sn in norme.TRAFO_SN_KVA if sn >= s_kva - 1e-6), None)


def _celula(sn) -> str:
    if sn > norme.TRAFO_SN_MAX_SIGURANTE_MT_KVA:
        return "celulă trafo cu întreruptor + releu 50/51, 50N/51N (Sn > 1000 kVA)"
    return ("celulă trafo cu separator de sarcină + siguranțe MT "
            f"{fmt(norme.TRAFO_SIGURANTA_MT_A.get(sn, 0))} A (orientativ, tabel producător)")


def presupuneri(intr: dict, ex: dict) -> list[str]:
    tip = intr.get("tip_schema")
    f = {"bransament": _pres_bransament, "tablou": _pres_tablou, "pt": _pres_pt, "cef": _pres_cef,
         "prosumator": _pres_prosumator, "ge_ats": _pres_ge, "locuinta": _pres_locuinta}.get(tip)
    out = f(intr, ex) if f else []
    adr = ex.get("adresa") or {}
    if not ex.get("beneficiar") and not adr.get("localitate"):
        out.append("beneficiar și adresă necompletate (câmpuri goale în cartuș)")
    elif not adr.get("localitate"):
        out.append("adresă necompletată (câmp gol în cartuș)")
    else:
        out.append(f"localitatea „{adr['localitate']}” se preia așa cum a fost scrisă (fără diacritice adăugate)")
        if not adr.get("judet"):
            out.append("județ necompletat (câmp gol în cartuș)")
    return out


def _pres_bransament(intr, ex):
    out = []
    if "cosfi" not in intr:
        out.append("cosφ 0,9")
    mono = intr.get("retea") == "mono"
    mat, iz, met = _cablu_text(intr)
    if mono and not (intr.get("material") or (intr.get("cablu") or {}).get("material")):
        out.append(f"coloană Cu {iz} (monofazat — secțiuni mici), metoda {met} ({DESCR_METODA[met]})")
    else:
        out.append(f"coloană {mat} {iz} metoda {met} ({DESCR_METODA[met]})"
                   + (", cu trecere pe Cu dacă Al < 16 mm²" if mat == "Al" else ""))
    out.append(f"schema TN-C-S, separare PEN în {'BMPM' if mono else 'BMPT'}")
    out.append(TEXT_OD)
    out.append("limita ΔU la bara TE = 3 % (dacă e depășită, motorul mărește secțiunea C2)")
    if "L_coloana_m" not in intr:
        out.append("coloană L = 50 m (implicit, V11)")
    return out


def _pres_plecari(intr, ex, tip):
    out = []
    pl = ex.get("plecari") or []
    cf = ex.get("_circuite_finale")
    if pl and any("L_m" not in p for p in pl):
        if cf:
            out.append("circuite Cu PVC metoda C, L = 25 m (circuite finale)")
        else:
            mat, iz, met = _cablu_text({"cablu": intr.get("cablu") or {}})
            txt = f"plecări: L = 50 m, {mat} {iz} {met} ({DESCR_METODA[met]})"
            out.append(txt + ("" if ex.get("grupare") else ", trasee separate (fără grupare)"))
    gr = ex.get("grupare")
    if gr:
        met = (intr.get("cablu") or {}).get("metoda") or "D1"
        k = norme.k_grupare(met, gr["plecari"])
        loc = {"E": "același pat de cabluri", "C": "același perete",
               "D1": "același șanț, tuburi alăturate", "D2": "același șanț"}[met]
        out.append(f"plecările pe {loc}: grupare {gr['plecari']} circuite, k grupare {TABEL_GRUPARE[met]} = {fmt(k, 2)}")
    if any(p.get("copii") for p in pl):
        out.append("sub-plecări: circuite finale Cu PVC metoda C, L = 25 m")
        for p in pl:
            if p.get("copii"):
                out.append(f"P {p['nume']} din bilanțul sub-plecărilor (ks {fmt(norme.ks_implicit(len(p['copii'])), 2)})")
    for p in _toate(pl):
        if p["receptor"] == "motor":
            out.append(f"{p['nume']} = receptor motor (cosφ 0,85)")
        elif p["receptor"] == "iluminat":
            out.append(f"{p['nume']} = receptor iluminat (ΔU ≤ 3 %)")
    for p in pl:
        if p["unitate"] == "A" and p["valoare"] and p["valoare"] > 630:
            out.append(f"plecarea de {fmt(p['valoare'])} A: MCCB (gG doar până la 630 A pe plecări)")
    if cf:
        out.append("tablou cu circuite finale (circuite_finale): MCB curba B pentru iluminat/prize, C pentru restul; "
                   "DDR 30 mA tip A pe circuitele de prize")
    return out


def _pres_pamant(intr, implicit="TN-C-S / TN-S (TN-S în aval de separarea PEN)") -> list[str]:
    """r5: schema de legare la pământ e o presupunere periculoasă → se declară mereu."""
    sp = intr.get("schema_pamant")
    if sp == "TT":
        return ["schema TT (declarată): " + (f"RA = {fmt(intr['RA_ohm'])} Ω, DDR pe fiecare plecare, verificare "
                                              "RA·IΔn ≤ 50 V" if intr.get("RA_ohm") else
                                              "RA nedeclarat — introduceți valoarea măsurată (RA·IΔn ≤ 50 V)")]
    if sp:
        return [f"schema {sp} (declarată)"]
    return [f"schema de legare la pământ nedeclarată → {implicit} (implicit) — declarați TN-C-S / TN-S / TT"]


def _pres_tablou(intr, ex):
    out = []
    if "cosfi" not in intr:
        out.append("cosφ 0,9 (forță, iluminat, prize, tablou)")
    pl = ex.get("plecari") or []
    n = len(pl)
    if n:
        ks = norme.ks_implicit(n)
        if "P_kW" in intr:
            out.append(f"ks = {fmt(ks, 2)} ({n} plecări), dar P declarată {fmt(intr['P_kW'])} kW are prioritate "
                       "(V14 dacă P < Pc)")
        elif "In_Q1_A" in intr:
            out.append(f"ks = {fmt(ks, 2)} ({n} plecări); Q1 impus {fmt(intr['In_Q1_A'])} A")
        elif all(p["unitate"] == "kW" for p in pl):
            sigma = sum(p["valoare"] * (p.get("n_circuite") or 1) for p in pl if p["valoare"] is not None)
            out.append(f"P tablou din bilanț: Σ = {fmt(sigma)} kW, ks = {fmt(ks, 2)} → Pc = {fmt(ks * sigma)} kW "
                       "(NU prima valoare din text)")
        else:
            out.append(f"P tablou din bilanțul plecărilor: ks = {fmt(ks, 2)} ({n} plecări) (NU prima valoare din text)")
    out += _pres_plecari(intr, ex, "tablou")
    if "L_alimentare_m" not in intr:
        out.append(f"alimentarea {_nume_alim(ex)} L = 50 m")
    if (intr.get("cablu") or {}).get("S_fortat"):
        out.append(f"cablul de alimentare impus ({fmt(intr['cablu']['S_fortat'])} mm²) se verifică (Iz, ΔU, Ik), nu se "
                   "alege")
    orig = intr.get("origine")
    if orig == "pt_propriu":
        out.append("limite ΔU pentru PT propriu: 6 % iluminat / 8 % altele (de la bornele JT ale PT)")
        if intr.get("pt_Sn_kVA"):
            out.append(f"sursa: bara JT a trafo-ului propriu {intr['pt_Sn_kVA']} kVA (Ik3max și Zb calculate de motor)")
        else:
            out.append("Sn necunoscut: Ik3max 25 kA și impedanța buclei implicite la bara PT (avertismente V32)")
    elif orig == "tg_existent":
        out.append("sursa: tablou existent (TGD) — " + (f"Ik3 la bara lui {fmt(intr['Ik3_sursa_kA'])} kA (declarat)"
                                                         if intr.get("Ik3_sursa_kA") else
                                                         "Ik3 și Zbuclă la bara lui: valori implicite (introduceți-le "
                                                         "din calculul instalației existente)")
                   + "; fără DDR declarat în amonte")
    elif orig == "bmpt":
        out.append("sursa: rețea publică prin BMPT (declarată), RCCB 300 mA în BMPT conform ST 4-JT")
        out.append(TEXT_OD)
    else:
        out.append("sursa tabloului nedeclarată: calculat ca rețea publică prin BMPT, dar RCCB 300 mA din BMPT NU se "
                   "ia în calcul la deconectare — declarați originea (BMPT / tablou existent / PT propriu)")
        out.append(TEXT_OD)
    out += _pres_pamant(intr)
    return out


def _nume_alim(ex):
    return ex.get("_nume_tablou") or "tablou"


def _pres_pt(intr, ex):
    out = []
    sn = intr.get("Sn_kVA")
    if sn in norme.TRAFO:
        uk, pk, _ = norme.TRAFO[sn]
        iz = intr.get("trafo_izolatie")
        out.append(f"trafo {'uscat (rășină)' if iz == 'uscat' else 'ulei'} 20/0,4 kV {norme.TRAFO_GRUPA_CONEXIUNI}, "
                   f"uk {fmt(uk)} %, Pk {pk} W (Tier 2)" + ("" if iz else " — tipul (ulei / uscat) nedeclarat"))
        if intr.get("celula_trafo") == "sigurante" and sn <= norme.TRAFO_SN_MAX_SIGURANTE_MT_KVA:
            out.append(f"siguranțe MT {fmt(norme.TRAFO_SIGURANTA_MT_A.get(sn, 0))} A (orientativ, tabel producător)")
        elif not intr.get("celula_trafo"):
            out.append(_celula(sn))
    if intr.get("celule_mt"):
        out.append("celule MT declarate: " + ", ".join(intr["celule_mt"]))
    if intr.get("masura"):
        out.append(f"măsura pe {intr['masura']} (declarată)")
    out.append(f"S\"kQ = {fmt(norme.MT_SKQ_IMPLICIT_MVA)} MVA (rețea MT 20 kV, valoare implicită)")
    out += _pres_plecari(intr, ex, "pt")
    out += _pres_pamant(intr, "TN-S")
    return out


def _s_cef(intr):
    p_inv = sum(i["n"] * i["Pn_kW"] for i in intr.get("invertoare") or [])
    p_pcs = (intr.get("bess") or {}).get("P_kW") or 0
    return FACTOR_INV * (p_inv + p_pcs), p_inv + p_pcs


def _pres_cef(intr, ex):
    out = ["Iac,max = 1,1·Pn/(√3·400) (fișa invertorului lipsește)",
           "cablu invertor Al PVC D1, L = 30 m"]
    S, P = _s_cef(intr)
    rac = intr.get("racord")
    if intr.get("pt_Sn_kVA") and intr.get("pt_existent"):
        out.append(f"PT propriu {intr['pt_Sn_kVA']} kVA EXISTENT = sursa TG-ului (Ik3 la bara TG din Sn; fără trafo nou)")
    elif intr.get("pt_Sn_kVA"):
        sn = intr["pt_Sn_kVA"]
        if ex.get("_pt_adaugat"):
            out.append(f"S = {fmt(S)} kVA > 400 kVA → PT propriu 20/0,4 kV {sn} kVA adăugat (racord MT); {_celula(sn)}")
        else:
            out.append(f"PT propriu {sn} kVA (declarat); {_celula(sn)}")
    elif rac == "tg_existent":
        out.append(f"racord în TG existent (S = {fmt(S)} kVA)"
                   + ("" if intr.get("racord_In_Q_A") else "; protecția din TG nedeclarată (V44 o cere)"))
        if not intr.get("Ik3_TG_kA"):
            out.append(TEXT_OD.replace("OD", "la bara TG", 1))
    elif S <= norme.PRAG_RACORD_BMPT_KVA:
        out.append(f"racord JT prin BMPT (S = {fmt(S)} kVA ≤ 173 kVA)")
        out.append(TEXT_OD)
    elif intr.get("atr_jt") or S <= norme.PRAG_RACORD_JT_MAX_KVA:
        out.append(f"racord JT direct din PT OD, conform ATR (S = {fmt(S)} kVA)")
        out.append(TEXT_OD)
    if intr.get("limitare_injectie_kW") is not None:
        out.append(f"limitarea injecției la {fmt(intr['limitare_injectie_kW'])} kW: analizor / contor de control la "
                   "punctul de racord (TC) + EMS / Power Manager care comandă invertoarele")
    cat = "B" if P >= norme.RFG_PRAG_TIP_B_KW else "A"
    out.append(f"categoria {cat} RfG ({fmt(P)} kW {'≥' if cat == 'B' else '<'} 1 MW); PI conform Ord. ANRE 208/2018 și ATR")
    out += _pres_pamant(intr, "TN-S în aval de PT propriu" if intr.get("pt_Sn_kVA") else "TN-C-S")
    return out


def _pres_prosumator(intr, ex):
    mono = intr.get("retea") == "mono"
    pn = intr.get("Pn_inv_kW") or 0
    out = [f"Iac,max = 1,1·Pn/{'230' if mono else '(√3·400)'} (fișa invertorului lipsește)"]
    if "L_inv_m" not in intr:
        out.append("invertor la 15 m de tabloul consumatorului, Cu PVC metoda C")
    out.append("DDR pe circuitul invertorului tip A (sau B dacă fișa nu exclude curenți de defect c.c.) — se confirmă")
    prag_pi = getattr(norme, "PROSUMATOR_PI_EXTERNA_KW", 27)
    if pn > prag_pi:
        out.append(f"peste {fmt(prag_pi)} kW: PI externă (tablou cu releu anti-insularizare) cerută de OD — se "
                   "confirmă cu ATR (Ord. ANRE 228/2018); contor bidirecțional furnizat de OD")
    else:
        out.append("PI integrată în invertor, reglaje conform ATR (Ord. ANRE 228/2018); contor bidirecțional furnizat de OD")
    if intr.get("racord") == "tg_existent":
        out.append("racord în TG existent al consumatorului (nu tabloul unei locuințe)")
    if intr.get("hibrid"):
        out.append("baterie cuplată în c.c. la invertorul hibrid (fără PCS separat)")
    if intr.get("limitare_injectie_kW") is not None:
        out.append(f"limitarea injecției la {fmt(intr['limitare_injectie_kW'])} kW: analizor / contor de control la "
                   "punctul de racord + Smart Dongle / Power Manager")
    out += _pres_pamant(intr, "TN-C-S")
    return out


def _pres_ge(intr, ex):
    out = ["cosφ 0,9", f"x\"d = {fmt(norme.GE_XD2_IMPLICIT, 2)} (valoare tipică)",
           "ATS 4 poli cu interblocaj mecanic + electric, categoria AC-33B",
           "fără excitație susținută declarată (Ik1 ≈ In_G)"]
    sr = intr.get("sursa_retea")
    out.append({"pt": "ramura de rețea din PT" + (f" {fmt(intr['pt_Sn_kVA'])} kVA" if intr.get("pt_Sn_kVA") else ""),
                "tgd": "ramura de rețea dintr-un TGD existent", "bmpt": "ramura de rețea din rețeaua publică (BMPT)"}
               .get(sr, "ramura de rețea: rețea publică prin BMPT (sursa nedeclarată — declarați PT / TGD / BMPT)"))
    if "L_GE_ATS_m" not in intr:
        out.append("cablul GE → ATS L = 20 m (implicit)")
    out += _pres_pamant(intr, "TN-S")
    return out


def _pres_locuinta(intr, ex):
    out = []
    mono = intr.get("retea") == "mono"
    al = intr.get("alimentare") or {}
    if "tip" not in al:
        out.append("alimentare din branșament existent (implicit)")
    if "P_aprobata_kW" not in al:
        out.append("putere aprobată nedeclarată — se completează din ATR / certificatul de racordare "
                   "(bilanțul se face din circuite)")
    if "In_Q_bransament_A" not in al:
        out.append(f"calibrul Q din {'BMPM' if mono else 'BMPT'} nedeclarat (valoare implicită a motorului)")
    if "L_coloana_m" not in al:
        out.append(f"coloana {'BMPM' if mono else 'BMPT'} → tabloul locuinței: lungime implicită (motor)")
    if not (al.get("cablu") or {}).get("material"):
        out.append("coloană și circuite Cu")
    if intr.get("schema_pamant") == "TT":
        out.append("schema TT (priză de pământ proprie): " + (f"RA = {fmt(intr['RA_ohm'])} Ω, verificare RA·IΔn ≤ 50 V"
                   if intr.get("RA_ohm") else "RA nedeclarat — introduceți valoarea măsurată (RA·IΔn ≤ 50 V)"))
    else:
        out.append(f"schema TN-C-S, separare PEN în {'BMPM' if mono else 'BMPT'}")
    circ = intr.get("circuite") or []
    if any("P_kW" not in x or "L_m" not in x for x in circ):
        out.append("puterile și lungimile circuitelor nedeclarate: valori tipice pe receptor (norme.LOCUINTA_RECEPTORI)")
    if intr.get("ks") is None:
        out.append("ks după numărul receptoarelor generale (0,8 / 0,6 / 0,5 / 0,4); sarcinile continue (VE, pompă de "
                   "căldură, încălzire electrică) cu ks = 1")
    out.append(f"DDR 30 mA pe grupe de cel mult {norme.LOCUINTA_CIRCUITE_PE_DDR} circuite"
               + ("; încărcarea VE pe DDR propriu tip B" if any(x["receptor"] == "vehicul_electric" for x in circ) else ""))
    out.append(TEXT_OD)
    return out


# =====================================================================================================
# F.7 Refuzuri și întrebări — pe intrarea fizică (comune regulilor locale și LLM)
# =====================================================================================================
class Decizie:
    def __init__(self):
        self.actiune = "genereaza"
        self.cod = None
        self.motiv = None
        self.intrebari: list[str] = []
        self.presupus: list[str] = []
        self.avertismente: list[str] = []

    def refuza(self, cod, motiv, intrebare=None):
        if self.actiune != "refuza":
            self.actiune, self.cod, self.motiv = "refuza", cod, motiv
            self.intrebari = [intrebare] if intrebare else []

    def intreaba(self, cod, intrebare, presupus=None):
        if self.actiune == "refuza":
            return
        self.actiune = "genereaza_cu_intrebare"
        self.cod = self.cod or cod
        self.intrebari.append(intrebare)
        if presupus:
            self.presupus.append(presupus)


def _bloc_bmpt(ib):
    return next((b for b in norme.BMPT_ORDINE if ib <= norme.BMPT[b]["I_max_A"] + 1e-9), None)


def verifica(intr: dict, ex: dict, probleme: list) -> Decizie:
    d = Decizie()
    tip = intr.get("tip_schema")
    if not tip:
        d.refuza("I01", "Tipul schemei nu poate fi determinat (I01).",
                 "Ce tip de schemă: branșament (BMPT/BMPM), tablou, CEF, prosumator, post de transformare "
                 "sau grup electrogen? Care este puterea? (Pentru tabloul unei case / al unui apartament: locuință.)")
        return d
    for cod, motiv, intreb in probleme:          # I03, I04, I05, I08 găsite la parsare
        d.refuza(cod, motiv, intreb)
    _verifica_valori(intr, d)
    if tip in ("bransament", "prosumator") and ex.get("_retea_lipsa"):
        d.intreaba("I02", "Branșamentul este monofazat (230 V, BMPM) sau trifazat (3 × 400 V, BMPT)? "
                          "Rețeaua nu se presupune — alege-o în câmpul „Rețea”.")
    {"bransament": _v_bransament, "tablou": _v_tablou, "pt": _v_pt, "cef": _v_cef,
     "prosumator": _v_prosumator, "ge_ats": _v_ge, "locuinta": _v_locuinta}[tip](intr, ex, d)
    return d


def _v_locuinta(intr, ex, d):
    al = intr.get("alimentare") or {}
    mono = intr.get("retea") == "mono"
    for k, et in (("P_aprobata_kW", "Puterea aprobată"), ("In_Q_bransament_A", "Calibrul Q al branșamentului"),
                  ("L_coloana_m", "Lungimea coloanei")):
        if k in al and al[k] <= 0:
            d.refuza("I06", f"{et} trebuie să fie > 0 (V07/V09).", f"{et} (valoare > 0)?")
    if intr.get("retea") not in ("mono", "tri"):
        # nu se presupune: schema se generează cu rețeaua necompletată (motorul blochează exportul, V07) și se întreabă
        d.intreaba("I02", "Branșamentul este monofazat (230 V, BMPM) sau trifazat (3 × 400 V, BMPT)? "
                          "Rețeaua nu se presupune — alege-o în câmpul „Rețea”.")
    circ = intr.get("circuite") or []
    if not circ:
        d.refuza("I02", "Lipsesc circuitele locuinței (I02).", "Ce circuite are tabloul (iluminat, prize, plită, …)?")
        return
    for x in circ:
        if "P_kW" in x and not (0 < x["P_kW"] <= norme.LOCUINTA_P_CIRCUIT_MAX_KW):
            d.refuza("I06", f"Circuitul {x['nume']}: P = {fmt(x['P_kW'])} kW neplauzibil pentru o locuință "
                            f"(0 … {fmt(norme.LOCUINTA_P_CIRCUIT_MAX_KW, 0)} kW) (V07).",
                     f"Care este puterea circuitului {x['nume']} (kW)?")
        if "L_m" in x and x["L_m"] <= 0:
            d.refuza("I06", f"Lungimea circuitului {x['nume']} trebuie să fie > 0 m (V09).",
                     f"Care este lungimea circuitului {x['nume']}?")
    if intr.get("RA_ohm") is not None and intr["RA_ohm"] <= 0:
        d.refuza("I06", "RA trebuie să fie > 0 Ω (V07).", "Care este rezistența prizei de pământ RA (Ω)?")
    if intr.get("ks") is not None and not (0 < intr["ks"] <= 1):
        d.refuza("I06", f"ks = {fmt(intr['ks'], 2)} în afara intervalului (0; 1] (V08).", "Care este ks (ex. 0,6)?")
    if d.actiune == "refuza":
        return
    P, Q = al.get("P_aprobata_kW"), al.get("In_Q_bransament_A")
    if P is not None and P > 100:
        d.refuza("I06", f"P aprobată = {fmt(P)} kW neplauzibilă pentru o locuință (V07).",
                 "Puterea aprobată a locuinței este în kW (uzual 5 … 30 kW)?")
        return
    if P is not None and P > 30 and not ex.get("_din_atr"):       # r8 (#26): valoarea copiată din ATR nu se re-confirmă
        d.intreaba("I06", f"Confirmați puterea aprobată {fmt(P)} kW? La o locuință se aprobă uzual 5 … 30 kW.")
    if mono and P is not None and P * 1000 / U_MONO > norme.BMPM["I_max_A"] + 1e-6:
        # r7 (#20, #23): P aprobată monofazată peste 40 A (9,2 kW) → întrebare (motorul blochează BMPM)
        d.intreaba("I09", f"P aprobată {fmt(P)} kW la branșament monofazat: Ib = {fmt(P * 1000 / (U_MONO * norme.LOCUINTA_COSFI))} "
                          f"A > 40 A (BMPM max.). Treceți pe branșament trifazat ({fmt(P)} kW), sau P aprobată ≤ 9,2 kW?")
        if P > P_PRAG_MONO_LOC_KW:
            d.avertismente.append(f"P aprobată {fmt(P)} kW la branșament monofazat: peste {P_PRAG_MONO_LOC_KW} kW se "
                                  f"recomandă trifazat (Ib = {fmt(P * 1000 / (U_MONO * norme.LOCUINTA_COSFI))} A; BMPM max. 40 A)")
    if mono and Q is not None and Q > norme.BMPM["I_max_A"]:
        d.avertismente.append(f"Q {fmt(Q)} A > 40 A: depășește BMPM monofazat (ST 3-JT) — branșament trifazat?")
    if Q is not None and Q > 250:
        d.intreaba("I06", f"Confirmați Q branșament {fmt(Q)} A? Pentru o locuință uzual 25 … 63 A.")
    if mono and any(x.get("faza") == "3F" for x in circ):
        d.avertismente.append("circuite 3F declarate la o locuință monofazată")


def _verifica_valori(intr, d):
    """I06: valori absurde (V07, V08, V09)."""
    cos = intr.get("cosfi")
    if cos is not None and not (0 < cos <= 1):
        d.refuza("I06", f"cosφ = {fmt(cos, 2)} în afara intervalului (0; 1] (V08).",
                 "Care este factorul de putere (ex. 0,9)?")
    for k, intreb in (("L_coloana_m", "Care este lungimea coloanei BMPT → tablou?"),
                      ("L_alimentare_m", "Care este lungimea alimentării tabloului?")):
        if k in intr and intr[k] <= 0:
            d.refuza("I06", f"Lungimea coloanei trebuie să fie > 0 m (V09).", intreb)
    for p in intr.get("plecari") or []:
        if "L_m" in p and p["L_m"] <= 0:
            d.refuza("I06", f"Lungimea plecării {p['nume']} trebuie să fie > 0 m (V09).",
                     f"Care este lungimea plecării {p['nume']}?")
        for k in ("P_kW", "In_A"):
            if k in p and p[k] <= 0:
                d.refuza("I06", f"Plecarea {p['nume']}: valoare ≤ 0 (V07).", f"Care este sarcina plecării {p['nume']}?")
    for k in ("P_kW", "Ib_A", "S_kVA", "Sn_kVA", "kWp", "Sn_GE_kVA", "Pn_inv_kW"):
        if k in intr and intr[k] <= 0:
            d.refuza("I06", f"{k} = {intr[k]} ≤ 0 (V07).", "Care este puterea?")


def _ib_bransament(intr, mono, cos):
    """Ib după B.2: din P_kW (cu cosφ), din S_kVA (fără cosφ) sau direct Ib_A. (ib, ib_trifazat echivalent)"""
    if intr.get("Ib_A"):
        ib = intr["Ib_A"]
        return ib, ib * (U_MONO / U_TRI if mono else 1)
    if intr.get("S_kVA"):
        return intr["S_kVA"] * 1000 / (U_MONO if mono else U_TRI), intr["S_kVA"] * 1000 / U_TRI
    P = intr["P_kW"]
    return P * 1000 / ((U_MONO if mono else U_TRI) * cos), P * 1000 / (U_TRI * cos)


def _v_bransament(intr, ex, d):
    surse = [k for k in ("P_kW", "Ib_A", "S_kVA") if intr.get(k) is not None]
    if not surse:
        d.refuza("I02", "Lipsește puterea (kW) sau curentul (A) branșamentului (I02).",
                 "Care este puterea aprobată (kW, din ATR) sau curentul maxim absorbit (A)?")
        return
    cos = intr.get("cosfi") or COSFI
    if not (0 < cos <= 1):
        return
    mono = intr.get("retea") == "mono"
    ib, ib3 = _ib_bransament(intr, mono, cos)
    P = intr.get("P_kW") or ib3 * U_TRI * cos / 1000          # doar pentru propunerea de PT la I10
    if mono and ib > norme.BMPM["I_max_A"] and not (intr.get("P_kW") and intr["P_kW"] <= 9.2 + 1e-6):
        # r8 (#25): P aprobată monofazată ≤ 9,2 kW (= 40 A × 230 V, convenția ATR) încape în BMPM
        d.refuza("I09", f"Ib = {fmt(ib)} A > 40 A (BMPM, ST 3-JT) — V53.",
                 f"Generez branșament trifazat ({_bloc_bmpt(ib3)}, Ib = {fmt(ib3)} A)?")
        return
    if not mono and ib > norme.BMPT_I_MAX_A:
        sn = _sn_standard(P / cos) or norme.TRAFO_SN_KVA[-1]
        d.refuza("I10", f"Ib = {fmt(ib, 0)} A > 250 A: în ST 4-JT nu există BMPT peste BMPTi-250 (V50).",
                 "Racordul se face din PT-ul OD cu măsură în PT, sau prin PT propriu? "
                 f"Pot genera schema „Post de transformare” (ex. {sn} kVA).")
        return
    if mono:
        return
    bloc = _bloc_bmpt(ib)
    cerut = ex.get("bmpt_cerut")
    if cerut == "BMPTd" or (cerut and cerut.startswith("BMPTd") and cerut not in norme.BMPT and ib > 100):
        if ib > 100:
            d.refuza("I08", f"Contradicție: {cerut} (măsură directă, max. 100 A) și Ib = {fmt(ib)} A (I08).",
                     f"Generez BMPTi-250 (măsură semidirectă) pentru Ib = {fmt(ib)} A?")
            return
    if cerut and cerut != "BMPTd":
        if cerut not in norme.BMPT:
            d.intreaba("I13", f"Confirmați {bloc}?",                 # R2: tipul nu se transmite motorului
                       f"I13: tipul {cerut} nu există în ST 4-JT Rev. 3/2024 → nu se transmite motorului; "
                       f"s-a folosit {bloc} (Ib = {fmt(ib)} A)")
        elif cerut != bloc:
            intr["bmpt_fortat"] = cerut                     # motorul verifică (V50/V52)
        else:
            intr["bmpt_fortat"] = cerut
    if intr.get("masura_ceruta") == "semidirecta" and ib <= 100:
        d.avertismente.append(f"V51: la {fmt(ib)} A ST 4-JT prevede {bloc} (măsură directă); se generează {bloc}")
        d.intreaba("V51", f"Confirmați {bloc}? Măsura semidirectă (BMPTi-250) se folosește doar între 100 și 250 A.")


def _are_sarcina(pl):
    return any(p.get("In_A") or p.get("P_kW") or _are_sarcina(p.get("copii") or []) for p in pl)


def _v_tablou(intr, ex, d):
    if not (intr.get("P_kW") or intr.get("In_Q1_A") or _are_sarcina(intr.get("plecari") or [])):
        n = ex.get("nr_plecari")
        d.refuza("I02", "Lipsesc puterile sau calibrele plecărilor și puterea tabloului (I02).",
                 f"Care sunt puterile (kW) sau calibrele (A) celor {n} plecări?" if n
                 else "Care este puterea tabloului (kW) și care sunt plecările (kW sau A)?")
        return
    if intr.get("origine") == "pt_propriu" and not intr.get("pt_Sn_kVA"):
        d.intreaba("I07", "Care este puterea trafo (kVA)?")
    if not intr.get("plecari"):
        # r7 (S5): niciodată „genereaza” cu un tablou fără plecări (motorul îl blochează V07) — se întreabă plecările
        d.intreaba("I02", "Care sunt plecările (circuitele) tabloului — nume și putere (kW) sau calibru (A)? Fără ele "
                          "tabloul se desenează doar cu alimentarea, blocat la export (V07).")
    q1 = intr.get("In_Q1_A")
    if intr.get("origine") == "bmpt":                       # r7 (#37): peste BMPTi-250 nu există BMPT
        ib = max(q1 or 0, (intr.get("P_kW") or 0) * 1000 / (U_TRI * COSFI))
        if ib > norme.BMPT_I_MAX_A:
            d.intreaba("I10", f"„din BMPT” cu Ib ≈ {fmt(ib, 0)} A > 250 A: în ST 4-JT nu există BMPT peste BMPTi-250 (V50). "
                              "Tabloul se alimentează dintr-un PT (propriu / al OD)? Indicați Sn-ul PT-ului.")
    qa = intr.get("In_Q_amonte_A")
    if qa and q1 and q1 > qa + 1e-6:                        # r7 (#56): „TD 250 A … printr-un întreruptor de 160 A”
        d.intreaba("I08", f"Contradicție: tabloul de {fmt(q1)} A e alimentat printr-un întreruptor de {fmt(qa)} A în amonte "
                          f"(selectivitate / supraîncărcare). Q1 al tabloului e {fmt(qa)} A, sau întreruptorul din amonte e "
                          f"≥ {fmt(q1)} A?")
    sn = intr.get("pt_Sn_kVA")
    for p in intr.get("plecari") or []:                    # r7 (#21): pornire directă a unui motor mare față de PT
        if sn and p.get("pornire") == "directa" and (p.get("P_kW") or 0) > 0.15 * sn:
            d.intreaba("I08", f"{p['nume']} {fmt(p['P_kW'])} kW cu pornire directă din PT {fmt(sn)} kVA: curentul de pornire "
                              f"(≈ 6–7·In) dă o cădere de tensiune mare la bara TG. Confirmați pornirea directă, sau "
                              "soft-starter / convertizor?")
            break
    mari = [p for p in intr.get("plecari") or [] if q1 and (p.get("In_A") or 0) > q1]
    if mari:                                      # r6 (industrial #45): „TG din BMPT 100A, plecări TD-1 125A”
        d.intreaba("I07", f"Plecarea {mari[0]['nume']} {fmt(mari[0]['In_A'])} A > Q1 / protecția sursei {fmt(q1)} A: "
                          "confirmați calibrele (plecarea nu poate depăși Q1)?")


def _v_pt(intr, ex, d):
    sn = intr.get("Sn_kVA")
    if not sn:
        d.refuza("I02", "Lipsește puterea transformatorului (kVA) (I02).", "Care este puterea trafo (kVA)?")
        return
    if sn > norme.TRAFO_SN_KVA[-1]:
        d.refuza("I12", f"Sn = {fmt(sn)} kVA > 2500 kVA: în afara domeniului aplicației (SPEC §A.3).",
                 "Împărțiți instalația pe mai multe posturi de transformare?")
        return
    if sn not in norme.TRAFO:
        sus = _sn_standard(sn)
        jos = max((s for s in norme.TRAFO_SN_KVA if s < sn), default=None)
        ex["puteri"]["Sn_kVA"] = intr["Sn_kVA"] = sus
        ex["puteri"]["Sn_cerut_kVA"] = _nr(sn)
        d.intreaba("I07", f"Confirmați {sus} kVA" + (f" (sau {jos} kVA)?" if jos else "?"),
                   f"{fmt(sn)} kVA nu e putere standard în norme.TRAFO → {sus} kVA (următoarea)")
    if not intr.get("plecari"):
        if ex.get("nr_plecari"):                    # r5 (P2-18): „PT 630 kVA cu 4 plecări” — ca la tablou: refuz I02
            d.refuza("I02", f"Lipsesc puterile sau calibrele celor {ex['nr_plecari']} plecări (I02).",
                     f"Care sunt puterile (kW) sau calibrele (A) celor {ex['nr_plecari']} plecări?")
            return
        d.intreaba("I02", "Care sunt plecările din TGJT (kW sau A)?")


def _v_cef(intr, ex, d):
    if not intr.get("invertoare") and not (intr.get("bess") or {}).get("P_kW"):
        d.refuza("I02", "Lipsesc invertoarele (număr și putere) (I02).",
                 "Câte invertoare și de ce putere (kW c.a.)?")
        return
    if not intr.get("invertoare"):
        d.presupus.append("BESS fără invertoare PV în această schemă (stocare independentă / lângă o CEF existentă): "
                          "se desenează doar ramura PCS + BESS")
    S, P = _s_cef(intr)
    n_t = intr.get("n_trafo") or 1
    lim = intr.get("limitare_injectie_kW")
    sig = sum(i["n"] * i["Pn_kW"] for i in intr.get("invertoare") or [])
    sig_b = sig + float((intr.get("bess") or {}).get("P_kW") or 0)   # r8 (#45): BESS-ul injectează și el
    if lim and sig and lim > sig_b + 1e-6:                   # r7 (#63): limitarea peste puterea instalată
        d.intreaba("I08", f"Limitarea injecției {fmt(lim)} kW > puterea instalată {fmt(sig_b)} kW (invertoare"
                          + (" + BESS" if sig_b > sig else "") + "): care e valoarea corectă (limitarea nu poate depăși "
                          "puterea instalată)?")
    if S / n_t > norme.TRAFO_SN_KVA[-1]:
        jum = _sn_standard(S / 2) or norme.TRAFO_SN_KVA[-1]
        d.refuza("I12", f"S = {fmt(S)} kVA > 2500 kVA (un singur trafo standard): în afara domeniului aplicației "
                        "(SPEC §A.3).",
                 f"Împărțiți centrala pe două posturi de transformare (ex. 2 × {jum} kVA)?")
        return
    sn = intr.get("pt_Sn_kVA")
    if intr.get("racord") == "pt" and not sn:                # r7 (#64): „racord în PT existent, nu știu puterea trafo”
        d.intreaba("I07", "Ce putere are transformatorul PT-ului în care se racordează centrala (kVA)? (necesară pentru "
                          "Ik3 la bara JT și verificarea V67)")
    if sn and not intr.get("pt_existent") and sn * n_t < S - 1e-6:
        sus = _sn_standard(S / n_t)                         # r5 (P2-19): întrebare înainte de V67 BLOCANT
        d.intreaba("I07", f"Sn PT {(str(n_t) + ' × ') if n_t > 1 else ''}{fmt(sn)} kVA < S = 1,1·ΣPn = {fmt(S)} kVA (V67). "
                          f"Măriți trafo-ul la {(str(n_t) + ' × ') if n_t > 1 else ''}{sus} kVA?")
    elif sn and intr.get("pt_existent") and sn * n_t < S - 1e-6:
        # r7 (#42): PT existent mai mic decât centrala = contradicție → întrebare (motorul blochează V67)
        d.intreaba("I08", f"PT existent {fmt(sn)} kVA < S = 1,1·ΣPn = {fmt(S)} kVA (V67): trafo-ul existent nu poate prelua "
                          "centrala — limitați puterea / injecția, sau trafo nou mai mare?")
    qb = intr.get("In_Q_bransament_A")
    if intr.get("racord") == "bmpt" and qb and S * 1000 / U_TRI > qb + 1e-6:
        # r6 (fotovoltaic P1-10): V72 și la CEF — Iac,max > Q-ul BMPT existent → întrebare (nu tăcere)
        d.intreaba("V72", f"Iac,max = 1,1·ΣPn/(√3·400) = {fmt(S * 1000 / U_TRI)} A > Q BMPT {fmt(qb)} A: limitați puterea "
                          "invertoarelor / injecția, sau e nevoie de ATR nou (BMPT mai mare)?")
    if sn or S <= norme.PRAG_RACORD_BMPT_KVA:
        return
    if S <= norme.PRAG_RACORD_JT_MAX_KVA:
        if intr.get("racord") != "tg_existent":
            d.avertismente.append(f"V66: S = {fmt(S)} kVA > 173 kVA: racord JT direct din PT OD, conform ATR")
    elif intr.get("atr_jt"):
        d.avertismente.append(f"V66: S = {fmt(S)} kVA > 400 kVA, racord JT acceptat doar conform ATR")
    elif intr.get("racord") == "tg_existent":
        # r5 (P0-4 PV): racord în TG existent → NU se adaugă un PT (ar ieși trafo în serie între două tablouri JT)
        sn = _sn_standard(S)
        d.intreaba("I11", f"S = {fmt(S)} kVA > 400 kVA, racord în TG existent: TG-ul e alimentat dintr-un PT propriu? "
                          f"Indicați Sn-ul lui (ex. {sn} kVA, „PT propriu … kVA existent”) — trafo-ul NU se desenează "
                          "între TGD-CF și TG.")
    else:                                                    # I11: se adaugă PT propriu și se întreabă
        sn = _sn_standard(S)
        intr["pt_Sn_kVA"] = sn
        ex["_pt_adaugat"] = True
        intreb = f"Confirmați PT propriu {sn} kVA ({_celula(sn).split(' (')[0]})? Alternativ, racord JT conform ATR."
        if ex.get("_pcs_presupus"):
            intreb += f" Indicați puterea PCS dacă diferă de {fmt(ex['_pcs_presupus'])} kW."
        d.intreaba("I11", intreb)


def _v_prosumator(intr, ex, d):
    pn = intr.get("Pn_inv_kW")
    if not pn:
        d.refuza("I02", "Lipsește puterea invertorului (kW) (I02).", "Care este puterea invertorului (kW c.a.)?")
        return
    lim = intr.get("limitare_injectie_kW")
    if lim and lim > pn + 1e-6:                              # r7 (#63)
        d.intreaba("I08", f"Limitarea injecției {fmt(lim)} kW > puterea invertorului {fmt(pn)} kW: care e valoarea corectă "
                          "(limitarea nu poate depăși puterea instalată)?")
    if intr.get("retea") == "mono":
        iac = FACTOR_INV * pn * 1000 / U_MONO
        if iac > norme.BMPM["I_max_A"]:
            pmax = math.floor(norme.BMPM["I_max_A"] * U_MONO / FACTOR_INV / 1000)
            d.refuza("I09", f"Iac,max = 1,1·{fmt(pn * 1000, 0)}/230 = {fmt(iac)} A > 40 A (BMPM maxim, ST 3-JT) — V53.",
                     f"Treceți pe prosumator trifazat {fmt(pn)} kW, sau reduceți invertorul monofazat la cel mult "
                     f"{pmax} kW (Iac,max ≤ 40 A)?")
            return
        if pn > norme.MONOFAZAT_P_INVERTOR_AVERTISMENT_KW:
            d.avertismente.append(f"V71: invertor monofazat {fmt(pn)} kW > 3,68 kW (dezechilibru; cerința exactă în ATR)")
    for g in intr.get("invertoare") or []:
        if intr.get("retea") == "tri" and g.get("faza") in ("L1", "L2", "L3") and \
                (g.get("Pn_kW") or 0) > norme.MONOFAZAT_P_INVERTOR_AVERTISMENT_KW:
            d.avertismente.append(f"V71: invertor monofazat {fmt(g['Pn_kW'])} kW pe faza {g['faza']} > 3,68 kW "
                                  "(dezechilibru între faze; cerința exactă în ATR)")
    if intr.get("retea") != "mono":
        iac = FACTOR_INV * pn * 1000 / U_TRI
        if iac > norme.BMPT_I_MAX_A:                          # r7 (#65): peste 250 A nu mai e BMPT
            d.intreaba("I10", f"Iac,max = {fmt(iac, 0)} A > 250 A: racordul nu se mai face prin BMPT — PT propriu / racord "
                              "în PT-ul OD cu măsură semidirectă în PT, conform ATR?")
        elif iac > 100 and (intr.get("In_Q_bransament_A") or 0) >= iac:   # r10 (#61): BMPT declarat ≥ Iac — nu se întreabă
            d.presupus.append(f"Iac,max = {fmt(iac, 0)} A > 100 A: BMPT {fmt(intr['In_Q_bransament_A'])} A declarat → "
                              "măsură semidirectă (TC), conform ATR")
        elif iac > 100:
            d.intreaba("V51", f"Iac,max = {fmt(iac, 0)} A > 100 A: branșamentul trece pe BMPTi-250 cu măsură semidirectă "
                              "(TC) — ATR-ul prevede asta (branșament nou / mărire)?")
    d.avertismente.append("V73: DDR tip A/B pentru circuitul invertorului — se confirmă din fișa invertorului")


def _v_ge(intr, ex, d):
    sn = intr.get("Sn_GE_kVA")
    if not sn:
        d.refuza("I02", "Lipsește puterea grupului electrogen (kVA) (I02).", "Care este puterea GE (kVA)?")
        return
    P = intr.get("P_sarcina_kW")
    if P:
        in_g = sn * 1000 / U_TRI
        ib = P * 1000 / (U_TRI * COSFI)
        if ib > in_g:
            sus = norme.ge_sn_minim(P, COSFI) or sn                     # seria GE_SN_KVA (C.6 pct. 5)
            d.refuza("V86", f"Sarcina {fmt(ib)} A > In GE {fmt(in_g)} A — V86.",
                     f"Măriți GE la cel puțin {sus} kVA (seria standard GE_SN_KVA, Sn ≥ P/cosφ = {fmt(P / COSFI)} kVA; "
                     "pornirea motoarelor neinclusă) sau declarați sarcinile prioritare?")


# =====================================================================================================
# Interpretorul local (reguli)
# =====================================================================================================
def _extras_gol(c: Ctx, tip, retea) -> dict:
    return {"tip_schema": tip, "retea": retea, "puteri": {}, "plecari": [], "nr_plecari": None, "lungimi_m": {},
            "material": detecteaza_material(c), "izolatie": detecteaza_izolatie(c), "metoda": detecteaza_metoda(c),
            "grupare": None, "cosfi": None}


# =====================================================================================================
# r6: plasa de siguranță — ce din text NU a ajuns în intrare → întrebare / „Nu am înțeles: …” (niciodată generare tăcută)
# =====================================================================================================
RE_ATOM_VAL = re.compile(
    rf"(?<![\w.,])(?P<num>{NUM})\s*(?P<u>kwp|mwp|wp|kwh|mwh|kvar|kva|mva|kw|mw|w|ka|ma|a|mm2|mm²|mmp|km|metri|ml|m|kv|v"
    rf"|ω|ohm\w*|cp|hp)(?![\w²])")
_MARIME_ATOM = {"kwp": ("kWp", 1), "mwp": ("kWp", 1000), "wp": ("W", 1), "kwh": ("kWh", 1), "mwh": ("kWh", 1000),
                "kvar": ("kvar", 1), "kva": ("kVA", 1), "mva": ("MVA", 1), "kw": ("kW", 1), "mw": ("kW", 1000),
                "w": ("W", 1), "ka": ("kA", 1), "ma": ("mA", 1), "a": ("A", 1), "mm2": ("mm2", 1), "mm²": ("mm2", 1),
                "mmp": ("mm2", 1), "km": ("m", 1000), "metri": ("m", 1), "ml": ("m", 1), "m": ("m", 1), "kv": ("V", 1000),
                "v": ("V", 1), "ω": ("ohm", 1), "cp": ("kW", KW_PE_CP), "hp": ("kW", 0.7457)}
RE_ATOM_REC = re.compile(
    r"\b(?:ilumin\w*|priz(?:a|e|ele)\b|motor\w*|pomp\w*|compresor\w*|ventilat\w*|boiler\w*|saun\w*|plit\w*|cuptor\w*"
    r"|clim\w*|wallbox\w*|incarcator\w*|strung\w*|polizor\w*|frez\w*|sudur\w*|hidrofor\w*|uscator\w*|calandru\w*"
    r"|chiller\w*|hvac\b|ups\b|server\w*|tablou\s+secundar|hranitor\w*|exhaustor\w*|rindea\w*|circular\w*|lift\w*"
    r"|ascensor\w*|pod\s+rulant|macara\w*|aer\s+conditionat|\bpdc\b|t[dge]-\w+|t[dge]\d+"
    # r7: tablouri secundare / receptoare casnice / surse care nu au voie să dispară tăcut
    r"|t[dge]\s+(?:la|de\s+la|din|pe|in)\s+[a-z]\w*|tablou\w*\s+secundar\w*|frigider\w*|congelator\w*"
    r"|masin\w*\s+(?:de\s+)?(?:spalat\s+)?(?:vase|rufe)|backup\b|\beps\b|corp(?:ul)?\s*(?:\d|doi)\b|al\s+doilea\s+corp"
    r"|jacuzzi\w*|generator\w*|wallbox\w*|incalzire\w*|rezistent\w*\s+(?:electric\w*|\d)|cuptor\w*|plit\w*)")
_KW_DOMENIU = [  # (eticheta, regex, satisfăcut(intr, tip))
    ("TT", re.compile(r"(?<![\w-])tt(?![\w-])"), lambda i, t: i.get("schema_pamant") == "TT"),
    ("TN", re.compile(r"\btn-?c-?s\b|\btn-?s\b|\btn-?c\b"), lambda i, t: str(i.get("schema_pamant") or "").startswith("TN")),
    ("IT", RE_SCHEMA_IT, lambda i, t: False),
    ("paralel", re.compile(r"\bparalel\w*\s+cu\s+retea\w*|\bsincroniz\w*|\bin\s+paralel\s+cu\b"), lambda i, t: False),
    ("compensare", RE_COMPENSARE, lambda i, t: False),
    ("MT", re.compile(r"\bmt\b|\bmedie\s+tensiune|\d\s*/\s*0[.,]4\s*kv\b"),
     lambda i, t: t == "pt" or bool(i.get("pt_Sn_kVA") or i.get("masura") == "MT" or i.get("origine") == "pt_propriu"
                                    or i.get("sursa_retea") == "pt" or i.get("racord") == "pt")),
    ("uscat", re.compile(r"\buscat(?!or)\w*"), lambda i, t: i.get("trafo_izolatie") == "uscat"),
    ("BMPT/BMPM", re.compile(r"\bbmp[tm]\w*"),
     lambda i, t: t in ("bransament", "locuinta", "prosumator") or "bmpt" in (i.get("origine"), i.get("racord"),
                                                                               i.get("sursa_retea"))),
    ("PT nou", re.compile(r"\b(?:pt|post\w*)(?:\s+(?:propriu|de\s+transformare|trafo|\d+(?:[.,]\d+)?\s*kva))*\s+nou\b"),
     lambda i, t: t == "pt" or bool(i.get("pt_Sn_kVA") and not i.get("pt_existent"))),
    ("PT existent", re.compile(r"\b(?:pt|post\w*)(?:\s+(?:propriu|de\s+transformare|trafo|\d+(?:[.,]\d+)?\s*kva))*\s+"
                               r"existent\w*"),
     lambda i, t: bool(i.get("pt_existent") or i.get("origine") == "pt_propriu" or i.get("sursa_retea") == "pt")),
    ("ATS", re.compile(r"\bats\b|\baar\b"), lambda i, t: t == "ge_ats"),
    ("PEN", re.compile(r"\bpen\b"), lambda i, t: bool(i.get("schema_pamant"))),
    ("off-grid", RE_OFFGRID, lambda i, t: False),
    ("hibrid", re.compile(r"\bhibrid\w*"),
     lambda i, t: bool(i.get("hibrid") or any(g.get("hibrid") for g in i.get("invertoare") or [])
                       or (i.get("bess") or {}).get("cuplaj") == "cc")),
    ("cuplaj", re.compile(r"\bcupl\w*\s+(?:in\s+)?(?:c\.?\s*[ca]\b\.?|curent\s+(?:continuu|alternativ))"),
     lambda i, t: bool(i.get("hibrid") or (i.get("bess") or {}).get("cuplaj"))),
]


def _valori_iesire(d, out=None, cheie=""):
    """{mărime: {valori}} din intrarea fizică (pentru potrivirea unei valori din text cu o cheie de ieșire)."""
    out = {} if out is None else out
    if isinstance(d, dict):
        for k, v in d.items():
            _valori_iesire(v, out, k)
        return out
    if isinstance(d, list):
        for v in d:
            _valori_iesire(v, out, cheie)
        return out
    if isinstance(d, bool) or not isinstance(d, (int, float)):
        return out
    k = cheie
    m = ("kW" if k.endswith("_kW") or k in ("P_kW", "Pn_kW") else "kVA" if k.endswith("_kVA") else
         "kWp" if k == "kWp" else "W" if k.endswith("_W") else "kWh" if k.endswith("kWh") else
         "A" if k.endswith("_A") else "m" if k.endswith("_m") else "ohm" if k.endswith("_ohm") else
         "kA" if k.endswith("_kA") else "mm2" if k in ("S_fortat", "N_fortat") else "MVA" if k.endswith("_MVA") else
         "V" if k.endswith("_V") else None)
    if m:
        out.setdefault(m, set()).add(round(float(d), 3))
    return out


_SEP_CL = re.compile(r"(?<!\d),|,(?!\d)|[;:]|\s-\s|\.\s")       # r7: virgula zecimală („5x2,5”) nu separă clauze


def _clauza(c: Ctx, s: int, e: int) -> tuple:
    a = max([x.end() for x in _SEP_CL.finditer(c.t, 0, s)] or [0])
    mb = _SEP_CL.search(c.t, e)
    b = mb.start() if mb else len(c.t)
    if b - a > 60:
        a, b = max(a, s - 25), min(b, e + 25)
        while a > 0 and c.t[a - 1].isalnum():
            a -= 1
        while b < len(c.t) and c.t[b].isalnum():
            b += 1
    return a, b


def plasa_siguranta(c: Ctx, intr: dict, tip: str | None) -> list[str]:
    """r6 (cerința 1): fiecare număr cu unitate, cuvânt-cheie de domeniu și nume de receptor / tablou din text trebuie
    să fi ajuns în intrare (interval consumat / folosit sau valoare regăsită la o cheie de aceeași mărime). Restul =
    fragmentele „neconsumate” → întrebare + „Nu am înțeles: …” în răspuns."""
    if not tip:
        return []
    folosit = list(c.consumat) + list(c.citit)
    t = _masca(c.t, RE_PRIZA_PAMANT)

    def acoperit(s, e):
        return any(a < e and s < b for a, b in folosit)

    vals = _valori_iesire(intr)
    if tip == "tablou":                                       # antetul tabloului („tablou pompe stație epurare”)
        mb = re.compile(r"[,;:]").search(t)
        cap = mb.start() if mb else len(t)
        if RE_TABLOU_CUV.search(t[:cap]) or re.search(r"\bt[dge]-", t[:cap]) or re.search(r"\bTE\b", c.orig[:cap]):
            folosit.append((0, cap))
    rest = []
    if getattr(c, "combo", None):                 # I14: celelalte instalații din frază se generează separat (întrebare)
        folosit.append((0, len(t)))
    for m in RE_ATOM_VAL.finditer(t):
        if acoperit(m.start(), m.end()):
            continue
        u = m.group("u")
        u = "ω" if u.startswith("ohm") else u
        marime, f = _MARIME_ATOM[u]
        v = round(numar(m.group("num")) * f, 3)
        mult = re.search(r"(?<![\w.,])(\d+)\s*×\s*$", t[max(0, m.start() - 6):m.start()])
        if marime == "V":
            ret = intr.get("retea")
            if v <= 1000 and ((v in (230,) and ret == "mono") or (v in (400,) and ret == "tri")):
                continue
            if v in (400, 20000) and (tip == "pt" or intr.get("pt_Sn_kVA")):
                continue
            if v in (230, 400) and tip in ("cef", "prosumator", "ge_ats") and (ret or tip == "ge_ats"):
                continue
            if v in vals.get("V", ()) or (v / 1000 if v >= 1000 else v) <= 1:
                continue
        else:
            cand = {v}
            if marime == "kVA":
                cand |= {round(v * COSFI, 3)}
            if marime == "W":
                cand |= {round(v / 1000, 3)}
            ms = {"W": ("W", "kW", "kWp"), "kWp": ("kWp",), "kVA": ("kVA", "kW")}.get(marime, (marime,))
            if any(x in vals.get(mm, ()) for mm in ms for x in cand):
                continue
        rest.append((m.start(), m.end()))
    for et, rx, ok in _KW_DOMENIU:
        for m in rx.finditer(t):
            if acoperit(m.start(), m.end()) or ok(intr, tip):
                continue
            rest.append((m.start(), m.end()))
    for m in RE_ATOM_REC.finditer(t):
        if acoperit(m.start(), m.end()):
            continue
        rest.append((m.start(), m.end()))
    zone = []
    for s, e in sorted(rest):
        a, b = _clauza(c, s, e)
        if zone and a <= zone[-1][1]:
            zone[-1][1] = max(zone[-1][1], b)
        else:
            zone.append([a, b])
    out = []
    for a, b in zone:
        frag = c.o(a, b).strip(" ,;:.-")
        if frag and frag not in out:
            out.append(frag)
    return out


def _tensiune_jt(c: Ctx, tip, intr: dict):
    """r7 (industrial #53): o tensiune JT declarată în afara 230/400 V (500 … 1000 V c.a., ex. 690 V) → `U_V` (motorul
    blochează) + întrebare; consumată, ca să nu rupă lista plecărilor. 800 V la invertoare PV se tratează la CEF."""
    if tip in ("cef", "prosumator"):
        return
    for m in re.finditer(r"(?:\b(?:la|de|in)\s+)?(?<![\d/.,×])(?P<v>\d{3,4})\s*v\b(?!\s*c\.?c)", c.mascat()):
        v = int(m.group("v"))
        if 500 <= v <= 1000:
            intr["U_V"] = v
            c.consumat.append((m.start(), m.end()))
            c.intrebari.append(("I12", f"„{c.o(m.start(), m.end()).strip()}”: tensiunea de {v} V nu e acoperită (aparataj și "
                                       "cabluri dimensionate pentru 400/230 V). Instalația e într-adevăr la "
                                       f"{v} V (atunci proiect de specialitate), sau 400 V?"))
            return


def _compensare(c: Ctx, tip, intr: dict):
    """r6 (industrial #25, #52): bateria de condensatoare (kvar) nu e BESS → clauza se scoate din listă; la tablou / PT
    → `compensare_kvar` (+ `compensare_L_m`) pentru motor; în rest (sau fără kvar) → întrebare (nu se pierde tăcut)."""
    gas = [m for m in RE_COMPENSARE.finditer(c.t)]
    if not gas:
        return
    zone = []
    for m in gas:
        a, b = _clauza(c, m.start(), m.end())
        mpt = re.search(r"\s(?:in|din|la)\s+(?:pt|post\w*|tg\w*|tablou\w*)\b", c.t[m.end():b])
        if mpt:                                          # r9 (#33): „… 120 kvar în PT 630 kVA” — PT-ul nu e compensarea
            b = m.end() + mpt.start()
        mcu = re.search(r"(?:\bcu\s+|\bsi\s+|\bplus\s+)?$", c.t[a:m.start()])
        if re.search(r"\b(?:din|de\s+la)\s+(?:pt|post\w*|tg|tablou|bmpt)", c.t[a:m.start()]):
            a = a + mcu.start()                          # r7 (#36): „TG din PT 1000 kVA cu compensare” — sursa rămâne
        if not zone or a > zone[-1][1]:
            zone.append([a, b])
        else:
            zone[-1][1] = max(zone[-1][1], b)
    for a, b in zone:
        c.consumat.append((a, b))
    txt = "; ".join(f"„{c.o(a, b).strip(' ,;:')}”" for a, b in zone)
    zt = " ".join(c.t[a:b] for a, b in zone)
    mq = re.search(rf"({NUM})\s*kvar\b", zt)
    toate_q = list(re.finditer(rf"({NUM})\s*kvar\b", c.t))
    if len(toate_q) > 1:                                 # r9 (#33): „compensare fixă trafo 20 kvar + baterie automată 120 kvar”
        pre_q = {}
        for x in toate_q:
            a_ = max([y.end() for y in re.compile(r"(?<!\d),|,(?!\d)|;|\+").finditer(c.t, 0, x.start())] or [0])
            c.consumat.append((a_, x.end()))
            pre_q[x.start()] = c.t[a_:x.start()]
        mq = next((x for x in toate_q if re.search(r"automat\w*", pre_q[x.start()])),
                  max(toate_q, key=lambda x: numar(x.group(1))))
        alte = [x.group(0) for x in toate_q if x is not mq]
        c.nota("compensare fixă a trafo-ului (" + ", ".join(alte) + ") = condensator fix la bornele JT ale trafo-ului "
               "(informativ); plecarea spre bateria automată = " + mq.group(0))
    if tip in ("tablou", "pt") and mq:
        intr["compensare_kvar"] = _nr(numar(mq.group(1)))
        mL = re.search(rf"({NUM})\s*(?:m|metri)\b", zt)
        if mL:
            intr["compensare_L_m"] = _nr(numar(mL.group(1)))
        c.nota(f"{txt} = plecare spre bateria de condensatoare {fmt(intr['compensare_kvar'])} kvar (compensare_kvar)")
        return
    c.intrebari.append(("I14", f"Compensarea energiei reactive {txt} nu se dimensionează în această schemă (plecarea "
                               "bateriei de condensatoare: calibru ≥ 1,43·In, conform fișei). O adaug ca plecare separată "
                               "după ce indicați calibrul, sau rămâne în afara planșei?"))


RE_COSFI_TINTA = re.compile(rf"(?:factor\w*\s+de\s+putere|cos\s*(?:fi|φ|phi))\s*(?:actual\w*|existent\w*|initial\w*|masurat\w*|mediu)?"
                            rf"\s*(?:=|de|:)?\s*(?P<a>0[.,]\d+)[^.;?]{{0,40}}?(?:se\s+doreste|dorit\w*|tinta|->|→|=>|pana\s+la"
                            rf"|imbunatat\w*(?:\s+la)?|ridica\w*(?:\s+la)?|\bla\b)\s*(?:la\s+)?(?:cos\s*(?:fi|φ)\s*)?(?:=\s*)?"
                            rf"(?P<b>0[.,]\d+|1(?:[.,]0+)?)\b")


RE_Q_GENERAL = re.compile(rf"\b(?P<tip>acb|mccb|intrerup(?:a)?tor\w*\s+(?:automat\s+)?general\w*|disjunctor\w*\s+general\w*"
                          rf"|q\s*general\w*|qg)\s*(?:jt\s*)?(?:de\s+|=\s*|:\s*)?(?P<v>{NUM})\s*a\b")


def _q_general(c: Ctx, tip, intr: dict):
    """r8 (industrial #18, #22): „JT: ACB 1600A”, „întrerupător general 400 A” = aparatul general al tabloului / al barei
    JT a PT-ului (In_Q_JT_A la PT, In_Q1_A la tablou; `Q_general_tip` = ACB/MCCB) — NU o plecare."""
    m = RE_Q_GENERAL.search(c.mascat())
    if not m and tip == "pt":
        # r10 (industrial #30, #53, #9): „TG 4000 A”, „tg 1000A”, „PTA … cu BMPT 3x400 A” = aparatul general JT al PT-ului
        m = re.search(rf"(?<!plecare\s)(?<!plecari\s)\b(?P<tip>tgjt|tg|tablou\w*\s+general\w*|cutie\s+bmpt|bmpt\w*)\s+(?:de\s+)?"
                      rf"(?:3\s*×\s*)?(?P<v>{NUM})\s*a\b", c.mascat())
    if not m:
        return
    v = numar(m.group("v"))
    k = "In_Q_JT_A" if tip == "pt" else "In_Q1_A"
    intr[k] = _nr(v)
    t = m.group("tip")
    if t in ("acb", "mccb"):
        intr["Q_general_tip"] = t.upper()
    c.consumat.append((m.start(), m.end()))
    c.nota(f"„{c.o(m.start(), m.end()).strip()}” = întrerupătorul general {'JT al PT-ului' if tip == 'pt' else 'al tabloului'} "
           f"{fmt(v)} A ({k}) — nu o plecare")


def _compensare_cosfi(c: Ctx, tip, intr: dict):

    """r8 (industrial #28): „factor de putere actual 0,78, se dorește 0,95, P = 400 kW” → Qc = P·(tg φ1 − tg φ2) — puterea
    bateriei de compensare (`compensare_kvar`), calculată și declarată (proiectantul confirmă treptele)."""
    if tip not in ("tablou", "pt") or intr.get("compensare_kvar"):
        return
    m = RE_COSFI_TINTA.search(c.mascat())
    if not m:
        return
    a, b = numar(m.group("a")), numar(m.group("b"))
    mp = re.search(rf"\bp\s*(?:=|:)\s*(?P<v>{NUM})\s*(?P<u>kw|mw)\b|(?P<v2>{NUM})\s*(?P<u2>kw|mw)\b", c.mascat())
    if not (0.3 < a < b <= 1) or not mp:
        return
    P = numar(mp.group("v") or mp.group("v2")) * (1000 if (mp.group("u") or mp.group("u2")) == "mw" else 1)
    qc = P * (math.tan(math.acos(a)) - math.tan(math.acos(b)))
    q = int(math.ceil(qc / 10.0) * 10)
    intr["compensare_kvar"] = q
    intr["cosfi"] = _nr(a)
    c.consumat.append((m.start(), m.end()))
    for mm in re.finditer(r"\bce\s+baterie\b[^,;.?]*\??|\bbaterie\w*\b", c.t):
        c.foloseste(mm.start(), mm.end())
    c.nota(f"compensare: Qc = P·(tg φ1 − tg φ2) = {fmt(P)}·(tg(arccos {fmt(a, 2)}) − tg(arccos {fmt(b, 2)})) = {fmt(qc, 0)} kvar "
           f"→ baterie de condensatoare {q} kvar (compensare_kvar, calculat)")
    c.intrebari.append(("I14", f"Bateria de compensare calculată: {q} kvar (cosφ {fmt(a, 2)} → {fmt(b, 2)} la {fmt(P)} kW). "
                               "Confirmați puterea și treptele (ex. automată, cu filtru), sau indicați bateria aleasă?"))


def _domeniu_ge(c: Ctx, intr: dict):
    """r6 (industrial #33, #34): GE monofazat → în afara domeniului (ATS 4P trifazat); GE în paralel cu rețeaua
    (sincronizare) ≠ ATS → se desenează ATS (comutare) + întrebare, niciodată tăcut."""
    m = re.search(r"\bparalel\w*\s+cu\s+retea\w*|\bin\s+paralel\b|\bsincroniz\w*", c.t)
    if m:
        for mm in re.finditer(r"\bparalel\w*(?:\s+cu\s+retea\w*)?|\bsincroniz\w*", c.t):
            c.foloseste(mm.start(), mm.end())
        intr["ge_paralel"] = True          # r6 (#34): motorul îl tratează explicit (≠ ATS)
        c.avert.append("GE în paralel cu rețeaua (sincronizare) ≠ ATS: funcționarea în paralel (protecții de cuplare "
                       "ANRE / ATR) nu e o comutare GE + ATS — vezi verificările motorului")
    if retea_declarata(c) == "mono":
        mm = RE_MONO_DECLARAT.search(c.t)
        c.foloseste(mm.start(), mm.end())
        intr["retea"] = "mono"                                 # r6 (#33): transmis explicit — motorul îl blochează
        c.intrebari.append(("I12", "GE monofazat: schema GE + ATS se dimensionează doar trifazat (ATS 4P). Grupul e "
                                   "trifazat (3 × 400/230 V)?"))


RE_PRET = re.compile(r"\bpret\w*|\bcost\w*\b|\bcat\s+costa\b|\bbuget\w*|\bdeviz\w*\s+de\s+pret|\boferta\s+de\s+pret")


RE_KS_GLOBAL = re.compile(rf"(?:(?<=[,;:.(]\s)|(?<=[,;:.(])|^)\s*(?P<k>k[su]|coef\w*\s+(?:de\s+)?(?:simultaneitate|utilizare|cerere))\s*(?:=|:|de)?\s*(?P<v>0?[.,]\d+|1(?:[.,]0+)?)\b(?!\s*(?:kw|a|kva)\b)")
RE_COS_GLOBAL = re.compile(rf"(?:(?<=[,;:.(]\s)|(?<=[,;:.(])|^)\s*cos\s*(?:fi|φ|phi)?\s*(?:mediu\s*)?(?:=|:|de)?\s*(?P<v>0?[.,]\d+|1(?:[.,]0+)?)\b")
RE_PC_GLOBAL = re.compile(rf"\b(?P<k>p\s*c|p\s*cerut\w*|p\s*calcul|p\s*i|p\s*inst\w*)\s*(?:=|:)\s*(?P<v>{NUM})\s*kw\b")


def _atribute_globale(c: Ctx, intr: dict):
    """r10 (industrial #22, #57): atributele tabloului scrise printre plecări — „ks 0.7, cos 0.85”, „Pi = 180 kW,
    ku = 0,7, Pc = 126 kW, cosφ = 0,92” — nu sunt plecări fără unitate: ks / cosφ globale, Pc = puterea cerută."""
    t = c.mascat()
    ma = RE_ATS_TRAFO.search(t)
    if ma and getattr(c, "_tip", None) == "pt":
        # r10: „ATS între cele două transformatoare 1000 kVA” — sursa (nu o plecare); Sn = kVA-ul din frază
        mk = re.match(rf"[^,;.]{{0,25}}?(?P<v>{NUM})\s*kva\b(?:\s*\([^)]*\))?", t[ma.end():])
        e = ma.end() + (mk.end() if mk else 0)
        if mk:
            intr["Sn_kVA"] = _nr(numar(mk.group("v")))
        c.consumat.append((ma.start(), e))
    for m in re.finditer(r"\bcupl\w*(?:\s+(?:automat\w*|longitudinal\w*|de\s+bare|jt|pe\s+jt|normal\s+\w+|deschis\w*|inchis\w*))*"
                         r"(?:\s*\(\s*interblocaj[^)]*\))?|\binterblocaj\w*(?:\s+[a-z\-]+){0,2}", t):
        c.consumat.append((m.start(), m.end()))          # r10 (#62): cupla / interblocajul nu sunt plecări
    for m in RE_KS_GLOBAL.finditer(t):
        intr["ks"] = _nr(numar(m.group("v")))
        c.consumat.append((m.start(), m.end()))
        c.nota(f"„{c.o(m.start(), m.end()).strip()}” = coeficientul de simultaneitate / utilizare al tabloului (ks = "
               f"{fmt(intr['ks'], 2)})")
    t = c.mascat()
    for m in RE_COS_GLOBAL.finditer(t):
        intr["cosfi"] = _nr(numar(m.group("v")))
        c.consumat.append((m.start(), m.end()))
        c.nota(f"„{c.o(m.start(), m.end()).strip()}” = cosφ mediu al tabloului ({fmt(intr['cosfi'], 2)})")
    t = c.mascat()
    for m in RE_PC_GLOBAL.finditer(t):
        k = re.sub(r"\s+", "", m.group("k"))
        c.consumat.append((m.start(), m.end()))
        if k.startswith(("pc", "pcerut", "pcalcul")):
            intr["P_kW"] = _nr(numar(m.group("v")))
            c.nota(f"„{c.o(m.start(), m.end()).strip()}” = puterea cerută (de calcul) a tabloului")
        else:
            c.nota(f"„{c.o(m.start(), m.end()).strip()}” = puterea instalată (informativă; calculul folosește Pc / ks)")


RE_MULTISPLIT = re.compile(rf"\b(?:ac\s+|aer\s+conditionat\s+)?multi[\s-]*split\w*\s*(?:cu\s+)?(?:(?P<n>\d+)\s+unitat\w*\s+interio\w*)?"
                           rf"[^.;]{{0,30}}?(?:unitat\w*\s+exterio\w*|ue)\s+(?:de\s+)?(?P<p>{NUM})\s*kw(?:\s+(?:mono|tri)\w*)?")
_CAMERE_TD = [(r"bucatari\w*", [("Prize bucătărie", "prize_bucatarie"), ("Iluminat bucătărie", "iluminat")]),
              (r"living\w*|sufrageri\w*", [("Prize living", "prize"), ("Iluminat living", "iluminat")]),
              (r"dormitoar\w*|dormitor\w*|camer\w*", [("Prize dormitoare", "prize"), ("Iluminat dormitoare", "iluminat")]),
              (r"\bbai\b|\bbaie\b|\bbaile\b", [("Prize baie", "prize_baie")])]


def _r10_locuinta_inainte(c: Ctx):
    """r10 (locuințe #30): „AC multisplit 3 unități interioare, unitatea exterioară 2,8 kW” = UN circuit (unitatea
    exterioară), nu 3 circuite de AC — se maschează înaintea citirii receptorilor."""
    m = RE_MULTISPLIT.search(c.mascat())
    if m:
        c.consumat.append((m.start(), m.end()))
        c._multisplit = {"nume": "AC multisplit", "receptor": "aer_conditionat", "P_kW": _nr(numar(m.group("p"))),
                         "multisplit": True}
        if m.group("n"):
            c._multisplit["unitati_interioare"] = int(m.group("n"))
        c.nota(f"„{c.o(m.start(), m.end()).strip()}” = AC multisplit: un singur circuit pentru unitatea exterioară "
               f"({fmt(c._multisplit['P_kW'])} kW); unitățile interioare se alimentează din ea")


def _r10_locuinta(c: Ctx, intr: dict, ex: dict):
    """r10 — locuința: multisplit, TD piscină / corpuri / TE pe niveluri cu camerele lor, kVA → Pa / Q, TN-C → TN-C-S,
    RA mare în TN-C-S, întrebările pentru blocajele anticipate (Pa, Q < P)."""
    al = intr.setdefault("alimentare", {})
    circ = intr.get("circuite") or []
    if getattr(c, "_multisplit", None):
        circ.append(c._multisplit)
        intr["circuite"] = circ
    t = c.t
    # TD piscină: receptorii piscinei (scriși înaintea lui „TD piscină la 25 m”) trec în tabloul ei
    mtd = re.search(rf"\btd\s+(?:pentru\s+|la\s+)?piscin\w*(?:\s+(?:la|de)\s+(?P<L>{NUM})\s*m)?", t)
    if mtd:
        i0 = t.find("piscin")
        span = t[i0:mtd.start()] if 0 <= i0 < mtd.start() else ""
        rec_span = _gaseste_receptori(span)
        td_c = []
        for g in rec_span:
            x = next((x for x in circ if x.get("receptor") == g["receptor"] and x.get("P_kW") == g["P"]), None)
            if x:
                circ.remove(x)
                x = dict(x)
                L_pop = x.pop("L_m", None)
                if L_pop and not mtd.group("L"):
                    c._L_td_piscina = L_pop               # „TD piscină la 25 m” mutat de rescrierea lungimilor pe circuit
                if x["receptor"] == "pompa_apa" and "piscin" not in _fara_diacritice(x["nume"]).lower():
                    x["nume"] = "Pompă piscină"
                if x["receptor"] == "pompa_caldura":
                    x["nume"] = "Pompă de căldură piscină"
                td_c.append(x)
        me = re.search(rf"\belectroliz\w*(?:\s+(?:cu\s+)?sare)?\s+(?P<p>{NUM})\s*kw|\bclorinator\w*\s+(?P<p2>{NUM})\s*kw", t)
        if me:
            td_c.append({"nume": "Electroliză sare", "receptor": "alt_circuit", "P_kW": _nr(numar(me.group("p") or me.group("p2")))})
            c.foloseste(me.start(), me.end())
        if td_c:
            td = {"nume": "TD piscină", "circuite": td_c}
            if mtd.group("L") or getattr(c, "_L_td_piscina", None):
                td["L_m"] = _nr(numar(mtd.group("L"))) if mtd.group("L") else c._L_td_piscina
            if intr.get("retea") == "tri":
                td["faza"] = "3F"
            tds = [x for x in intr.get("tablouri_secundare") or [] if "piscin" not in _fara_diacritice(x.get("nume", "")).lower()]
            intr["tablouri_secundare"] = tds + [td]
            c.foloseste(mtd.start(), mtd.end())
            c.intrebari[:] = [q for q in c.intrebari if "piscin" not in _fara_diacritice(q[1]).lower()]
            c.nota("TD piscină" + (f" la {fmt(td['L_m'])} m" if td.get("L_m") else "") + ": " + ", ".join(x["nume"] for x in td_c))
    # TE pe niveluri cu camerele lor: „TE parter (bucătărie, living) și TE etaj (dormitoare, 2 băi cu încălzitor prosop 0,5 kW)”
    for m in re.finditer(r"\b(?P<td>te|td)\s+(?P<loc>parter\w*|etaj\w*|mansard\w*)\s*\((?P<l>[^)]*)\)", t):
        lst = m.group("l")
        if re.search(r"\d+\s*circ|\bcirc\w*\s*\d|\b(?:ilumin|priz)\w*\s+\d", lst) or any(
                x.get("circuite") and m.group("loc")[:4] in _fara_diacritice(x.get("nume", "")).lower()
                for x in intr.get("tablouri_secundare") or []):
            continue                                    # lista are deja circuite (r9) — nu camere
        cc = []
        for rx, lst_c in _CAMERE_TD:
            if re.search(rx, lst):
                for nume, rec in lst_c:
                    cc.append({"nume": nume, "receptor": rec})
        for g in _gaseste_receptori(lst):
            if g["P"] is not None:
                nb = re.search(r"(\d+)\s+bai\b", lst)
                k = int(nb.group(1)) if nb and g["receptor"] == "incalzire_electrica" else 1
                for i in range(k):
                    cc.append({"nume": f"{g['nume'] or 'Încălzitor'}" + (f" {i + 1}" if k > 1 else ""), "receptor": g["receptor"],
                               "P_kW": g["P"]})
        if not cc:
            continue
        nume = f"{m.group('td').upper()} {nume_normalizat(m.group('loc'))}"
        tds = [x for x in intr.get("tablouri_secundare") or [] if x.get("nume", "").lower() != nume.lower()]
        td = {"nume": nume, "circuite": cc}
        if intr.get("retea") == "tri":
            td["faza"] = "3F"
        intr["tablouri_secundare"] = tds + [td]
        c.foloseste(m.start(), m.end())
        c.intrebari[:] = [q for q in c.intrebari if nume.lower() not in q[1].lower()]
        c.nota(f"„{c.o(m.start(), m.end()).strip()}” = {nume} cu circuitele camerelor: " + ", ".join(x["nume"] for x in cc))
    if any(x.get("nume", "").lower().startswith(("te parter", "td parter")) for x in intr.get("tablouri_secundare") or []):
        # TG-ul de la intrare: doar alimentează TE-urile (circuitele camerelor sunt în TE)
        intr["circuite"] = [x for x in circ if x.get("P_kW") or x.get("receptor") not in GENERICE_LOC | {"masina_spalat_vase",
                                                                                                         "prize_exterior"}]
    # corpuri: „casa 2 corpuri: corp A 10 kW, corp B la 40 m 5 kW tri”
    corpuri = list(re.finditer(rf"\bcorp(?:ul)?\s+(?P<k>[a-d1-4])\b\s*(?:(?:la|de)\s+(?P<L>{NUM})\s*m\s*)?(?P<p>{NUM})\s*kw"
                               rf"(?:\s+(?P<r>tri|mono)\w*)?", t))
    if len(corpuri) >= 2:
        P_tot = 0.0
        for i, mc in enumerate(corpuri):
            P_ = numar(mc.group("p"))
            P_tot += P_
            c.foloseste(mc.start(), mc.end())
            if i == 0:
                continue
            td = {"nume": f"TD Corp {mc.group('k').upper()}", "P_kW": _nr(P_),
                  "circuite": [{"nume": f"Corp {mc.group('k').upper()} (consum total)", "receptor": "alt_circuit", "P_kW": _nr(P_)}]}
            if mc.group("L"):
                td["L_m"] = _nr(numar(mc.group("L")))
            if intr.get("retea") == "tri" or mc.group("r") == "tri":
                td["faza"] = "3F"
            intr.setdefault("tablouri_secundare", []).append(td)
            c.intrebari.append(("I02", f"{td['nume']}: ce circuite are corpul {mc.group('k').upper()}? Desenat cu un circuit "
                                       f"echivalent de {fmt(P_)} kW până la răspuns."))
        if al.get("L_coloana_m") and any(mc.group("L") and numar(mc.group("L")) == al["L_coloana_m"] for mc in corpuri):
            al.pop("L_coloana_m")
        if not al.get("P_aprobata_kW"):
            al["P_aprobata_kW"] = _nr(P_tot)
            c.nota(f"P aprobată = Σ corpuri = {fmt(P_tot)} kW (PRESUPUS — un singur branșament)")
        c.nota("corpurile casei: " + ", ".join(f"corp {mc.group('k').upper()} {mc.group('p')} kW" for mc in corpuri)
               + " — primul în TG, celelalte cu TD propriu")
    # „casa 15 kVA trifazat” → Pa ≈ 0,9 × S, Q din kVA
    mk = re.search(rf"\b(?:cas(?:a|ei)|apartament\w*|locuint\w*|bransament\w*)(?:\s+\w+)?\s+(?P<v>{NUM})\s*kva\b", t)
    if mk and not al.get("P_aprobata_kW") and intr.get("retea") in ("tri", "mono"):
        S = numar(mk.group("v"))
        ib = S * 1000 / (U_TRI if intr["retea"] == "tri" else U_MONO)
        q = next((x for x in (10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160) if x >= ib - 1e-6), None)
        al["P_aprobata_kW"] = _nr(round(S * 0.9, 1))
        if q and not al.get("In_Q_bransament_A"):
            al["In_Q_bransament_A"] = q
        c.foloseste(mk.start(), mk.end())
        c.nota(f"„{c.o(mk.start(), mk.end()).strip()}” = puterea aparentă a branșamentului: Ib = {fmt(ib, 1)} A → Q {q} A; "
               f"P aprobată ≈ 0,9 × {fmt(S)} = {fmt(S * 0.9, 1)} kW (cosφ 0,9, PRESUPUS)")
    # TN-C la casă → TN-C-S cu separarea PEN în BMPT (+ priză de pământ)
    if intr.get("schema_pamant") == "TN-C" and not re.search(r"\bfara\s+(?:pe|pamant|impamantare|conductor)|\bbloc\b|\bvech\w*", t):
        intr["schema_pamant"] = ex["schema_pamant"] = "TN-C-S"
        intr["separare_PEN"] = "BMPT"
        c.nota("rețeaua OD TN-C → instalația casei TN-C-S: separarea PEN în BMPT / firidă, priză de pământ nouă (Rp ≤ 4 Ω), "
               "DDR pe circuite (desenat așa)")
        c.intrebari.append(("I02", "Rețeaua OD e TN-C: desenez instalația casei TN-C-S (separarea PEN în BMPT, priză de pământ "
                                   "nouă, DDR pe circuite). Confirmați, sau aveți altă schemă (TT cu priză proprie)?"))
    # „casa 9 kw monofazat cu cablu 3x6 mm2 de 45 m până la tablou” = coloana (cablul impus + lungimea)
    mcol = re.search(rf"\bcablu\w*\s+(?:cu\s+|tip\s+)?(?:{_TIP_CABLU}\s+)?(?P<c>[2-5])\s*×\s*(?P<s>{NUM})\s*(?:mm2?|mm²|mmp)?\s*(?:cu\b|al\b)?"
                     rf"\s*(?:de\s+|pe\s+)?(?P<L>{NUM})\s*m\b(?:\s+(?:pana\s+la|spre)\s+(?:tablou\w*|te\b|tg\b|casa))?", t)
    if mcol and not (al.get("cablu") or {}).get("S_fortat") and not intr.get("tablouri_secundare") \
            and not re.search(r"\b(?:td|te|tablou\w*\s+secundar\w*|corp\w*|al\s+doilea|anex\w*|garaj\w*|atelier\w*)\b",
                              t[max(0, mcol.start() - 45):mcol.start()]):
        al["cablu"] = dict(al.get("cablu") or {}, S_fortat=_nr(numar(mcol.group("s"))))
        al["cablu"].setdefault("material", "Al" if re.search(r"\bal\b|acyaby", mcol.group(0)) else "Cu")
        al["L_coloana_m"] = _nr(numar(mcol.group("L")))
        c.foloseste(mcol.start(), mcol.end())
        c.nota(f"„{c.o(mcol.start(), mcol.end()).strip()}” = coloana BMPT → tabloul casei: cablu impus "
               f"{mcol.group('c')}×{fmt(al['cablu']['S_fortat'])} mm², L = {fmt(al['L_coloana_m'])} m (ΔU verificat)")
    # RA mare în TN-C-S (I7: priza de pământ a branșamentului / instalației ≤ 4 Ω)
    ra = intr.get("RA_ohm") or al.get("RA_ohm")
    if ra and intr.get("schema_pamant") in ("TN-C-S", "TN-S") and ra > 4:
        c.intrebari.append(("I08", f"Priza de pământ {fmt(ra)} Ω > 4 Ω (I7, TN-C-S): se îmbunătățește priza (electrozi "
                                   "suplimentari, Rp ≤ 4 Ω) — desenată ca de completat, sau valoarea e alta?"))
    # Q < Ib pentru puterea cerută („BMPT 3x25A existent, vreau 22 kW fără mărire de putere”)
    q, P = al.get("In_Q_bransament_A"), al.get("P_aprobata_kW")
    if q and P and intr.get("retea") in ("tri", "mono"):
        ib = P * 1000 / ((U_TRI if intr["retea"] == "tri" else U_MONO) * 0.95)
        if ib > q * 1.05:
            c.intrebari.append(("I08", f"{fmt(P)} kW ≈ {fmt(ib, 0)} A > Q branșament {fmt(q)} A: cereți mărirea puterii (ATR nou, "
                                       f"Q ≥ {fmt(ib, 0)} A), sau limitați puterea simultană la ≈ "
                                       f"{fmt(q * (U_TRI if intr['retea'] == 'tri' else U_MONO) * 0.95 / 1000, 1)} kW (DLM / ks)?"))
    # Q declarat fără P aprobată, cu receptoare mari („casa mono 32A, 2 AC 3,5 kW, plită 7, …”)
    if q and not P and intr.get("retea") in ("tri", "mono"):
        Pq = q * (U_TRI if intr["retea"] == "tri" else U_MONO) * 0.95 / 1000
        sp = sum((x.get("P_kW") or 0) for x in circ)
        if sp > Pq:
            c.intrebari.append(("I02", f"Care e puterea aprobată (ATR)? Q {fmt(q)} A ↔ ≈ {fmt(Pq, 1)} kW; receptoarele declarate "
                                       f"însumează {fmt(sp, 1)} kW (simultaneitatea se aplică pe Pa)."))


RE_DDR_TIP = re.compile(r"\b(?:rcd|ddr|rccb|rcbo|diferential\w*|protecti\w*\s+diferential\w*)\s*(?:de\s+)?(?:(?P<ma>\d+)\s*ma\s+)?"
                        r"(?:de\s+)?tip(?:ul)?\s+(?P<tip>a|ac|b|f|b\+|ev)\b")
RE_PLECARE_NOUA = re.compile(r"\b(?:o\s+)?plecare\w*\s+(?:noua|suplimentar\w*)\s+(?:pentru|pt\.?|spre|catre)\s+")


def _r10_tablou(c: Ctx, intr: dict, ex: dict):
    """r10 — tabloul: plecarea unică din TG existent (cablu / lungime / DDR pe plecare, nu pe alimentare), DDR tip B,
    UPS cu bypass, separarea PEN, cablul existent, TN-C cu secțiuni < 10 mm², stații VE N x P."""
    pl = intr.get("plecari") or []
    # (1) „În TG existent adăugăm o plecare nouă pentru stație EV 22 kW, cablu 5x10 Cu, 45 m” / „motor 30 kW alimentat din
    #     TG existent cu CYABY 4x4, 120 m” — se desenează doar plecarea; cablul și lungimea sunt ale ei
    t_tab = re.sub(r"\b(?:tg|tablou\w*(?:\s+general)?)(?:-ul)?\s+existent\w*|\b(?:din|in)\s+(?:tg|tablou\w*(?:\s+general)?)\b", " ", c.t)
    if intr.get("origine") == "tg_existent" and len(pl) == 1 and not pl[0].get("copii") and not pl[0].get("n_circuite") \
            and not re.search(r"\btablou\w*|\btd\w*\b|\bte\b|\btdf\b|\btg\b", t_tab):
        p = pl[0]
        if intr.get("L_alimentare_m") and not p.get("L_m"):
            p["L_m"] = intr.pop("L_alimentare_m")
            c.nota(f"o singură plecare din TG existent: lungimea {fmt(p['L_m'])} m e a plecării „{p['nume']}”, nu a unei "
                   "alimentări de tablou nou")
        if intr.get("cablu") and intr["cablu"].get("S_fortat") and not (p.get("cablu") or {}).get("S_fortat"):
            p["cablu"] = dict(p.get("cablu") or {}, **intr.pop("cablu"))
        mn = re.match(r"^(?:noua|nou[aă]?|suplimentar\w*)\s+(?:pentru|pt\.?|spre)\s+", _fara_diacritice(p["nume"]).lower())
        if mn:
            p["nume"] = nume_normalizat(p["nume"][mn.end():])
    # (2) DDR tip B (sau A / F) cerut pe plecare
    m = RE_DDR_TIP.search(c.t)
    if m and pl:
        tinta = pl if len(pl) == 1 else [p for p in pl if re.search(r"\b(?:ev|ve)\b|incarc|wallbox|statie", _fara_diacritice(
            p.get("nume", "")).lower())] or []
        for p in tinta:
            p["ddr"] = {"tip": m.group("tip").upper().replace("EV", "B")}
            if m.group("ma"):
                p["ddr"]["IdN_mA"] = int(m.group("ma"))
        if tinta:
            c.foloseste(m.start(), m.end())
            c.nota(f"„{c.o(m.start(), m.end()).strip()}” = DDR tip {tinta[0]['ddr']['tip']} pe plecarea "
                   + ", ".join(p["nume"] for p in tinta))
    # (3) UPS cu bypass: plecarea UPS (receptor ups) cu sarcinile lui în aval
    mu = re.search(rf"\bups\s+(?:de\s+)?(?P<v>{NUM})\s*(?P<u>kva|kw)\b(?P<by>\s+cu\s+by-?pass(?:\s+\w+)?)?", c.t)
    if mu and not re.search(r"\d\s*(?:a|kw|kva)\s+cu\s+$", c.t[max(0, mu.start() - 12):mu.start()]) and not any((p.get("receptor") == "ups" or "ups" in _fara_diacritice(p.get("nume", "")).lower()) for p in pl):
        v = _nr(numar(mu.group("v")))
        u = {"nume": f"UPS {fmt(v)} {'kVA' if mu.group('u') == 'kva' else 'kW'}" + (" cu bypass" if mu.group("by") else ""),
             ("S_kVA" if mu.group("u") == "kva" else "P_kW"): v, "ups": True}
        if mu.group("by"):
            u["bypass"] = True
        if pl and re.search(r"\bpdu\b|\bservere?\b|\brack\w*", " ".join(_fara_diacritice(p.get("nume", "")).lower() for p in pl)):
            u["copii"] = pl
            u["receptor"] = "tablou"                   # UPS = tabloul de ieșire al UPS-ului cu PDU-urile în aval
            intr["plecari"] = [u]
        else:
            intr["plecari"] = pl + [u]
        c.foloseste(mu.start(), mu.end())
        c.nota(f"„{c.o(mu.start(), mu.end()).strip()}” = UPS {fmt(v)} {mu.group('u').upper().replace('KVA', 'kVA')}"
               + (" cu bypass" if mu.group("by") else "") + (", cu sarcinile PDU în aval" if u.get("copii") else ""))
    # (4) separarea PEN în TG / BMPT
    ms = re.search(r"\bsepar\w*\s+(?:a\s+)?(?:conductor\w*\s+)?pen\w*\s+(?:in|la)\s+(?P<l>tg\w*|tablou\w*(?:\s+general)?|bmpt\w*|firida\w*|cutie\w*)", c.t)
    if ms:
        intr["separare_PEN"] = "BMPT" if ms.group("l").startswith(("bmpt", "firida", "cutie")) else "TG"
        c.foloseste(ms.start(), ms.end())
        c.nota(f"„{c.o(ms.start(), ms.end()).strip()}” = separarea PEN în {intr['separare_PEN']} (TN-C-S: PEN → PE + N la "
               "bara tabloului)")
    # (5) cablul de alimentare existent (neutru redus admis pe cablu existent → verificare, nu înlocuire)
    if intr.get("cablu") and re.search(r"\bcablu\w*[^,;.]{0,40}?\bexistent\w*|\bexistent\w*\s+(?:cyaby|acyaby|cablu)", c.t):
        intr["cablu"]["existent"] = True
    # (5b) „prize 6 circuite 2,5 mm²” — secțiunea e a circuitelor, nu a alimentării tabloului
    mcs = re.search(rf"\b(?P<r>priz\w*|ilumin\w*)\s+(?P<n>\d+)\s+circuite\s+(?:(?:cu\s+)?(?:cablu\s+)?(?:3\s*×\s*)?)(?P<s>{NUM})\s*(?:mm2?|mm²|mmp)\b",
                    c.t)
    if mcs and not intr.get("plecari"):
        S = _nr(numar(mcs.group("s")))
        pr = mcs.group("r").startswith("priz")
        intr["plecari"] = [{"nume": "Prize" if pr else "Iluminat", "In_A": 16 if pr else 10, "n_circuite": int(mcs.group("n")),
                            "retea": "mono", "cablu": {"S_fortat": S, "material": "Cu"}}]
        if (intr.get("cablu") or {}).get("S_fortat") == S:
            intr.pop("cablu")
        c.foloseste(mcs.start(), mcs.end())
        c.nota(f"„{c.o(mcs.start(), mcs.end()).strip()}” = {mcs.group('n')} circuite cu {fmt(S)} mm² (calibrul "
               f"{'16' if pr else '10'} A presupus)")
    # (6) TN-C cu circuite < 10 mm² Cu
    if intr.get("schema_pamant") == "TN-C":
        msmall = re.search(r"(?<![\d.,])(?:1[.,]5|2[.,]5|4|6)\s*(?:mm2?|mm²|mmp)\b", c.t)
        if msmall:
            c.intrebari.append(("I08", f"Schema TN-C cu circuite de {c.o(msmall.start(), msmall.end()).strip()}: conductorul PEN "
                                       "trebuie să aibă cel puțin 10 mm² Cu (16 mm² Al) (I7, SR HD 60364-5-54) — separarea "
                                       "PEN în TG (TN-C-S, circuite cu PE și N separate), sau secțiuni ≥ 10 mm²?"))


def interpreteaza_local(text: str) -> dict:
    text, date_r12, note_r12 = R12.preextrage(text)          # r12: texte de proiectant — cabluri / racord / QG pe segmente
    text, note_tabel = rescrie(text)                          # r8: tabel / engleză / cascade / autocorecturi
    c = Ctx(text)
    c._reale = date_r12
    for n in note_r12 + note_tabel:
        c.nota(n)
    mp = RE_PRET.search(c.t)
    if mp and not re.search(r"\d\s*(?:kw|kva|a)\b", c.t):     # r8 (industrial #54): prețul nu e o schemă
        c.foloseste(0, len(c.t))
        c.probleme.append(("I12", f"„{c.o(mp.start(), mp.end()).strip()}”: prețul / costul nu se calculează din chat — în afara "
                                  "scopului interpretorului (I12). Generați întâi schema (cu puterile plecărilor), apoi "
                                  "„Deviz estimativ” din lista de echipamente.",
                           "Descrieți tabloul (sursa, plecările cu puteri / calibre) ca să generez schema și devizul?"))

    mit = re.search(r"\b(?:tablou\w*|retea\w*|schema|sistem\w*)\s+it\s+medical\w*|\bit\s+medical\w*|\bgrup\w*\s+(?:medical\w*\s+)?2\b"
                    r"|\bsal\w*\s+(?:de\s+)?operati\w*|\bterapie\s+intensiv\w*", c.t)
    if mit:                                                   # r9 (industrial #12): IT medical (SR HD 60364-7-710)
        c.foloseste(mit.start(), mit.end())
        c.probleme.append(("I12", f"„{c.o(mit.start(), mit.end()).strip()}”: rețeaua IT medicală (grupa 2: trafo de separare "
                                  "medical, controlor de izolație CPI, SR HD 60364-7-710) e în afara domeniului aplicației — "
                                  "schemele de aici sunt TN / TT (I12).",
                           "Rețeaua IT medicală (trafo de separare + CPI) se proiectează separat — desenez doar alimentarea "
                           "tabloului (TN-S, din TG), sau tabloul nu e IT medical?"))
    tip = R12.corecteaza_tip(c, R11.corecteaza_tip(c, detecteaza_tip(c)))   # r11: UPS … kVA ≠ PT; r12: PV ≠ GE
    c._tip = tip
    retea = detecteaza_retea(c)
    ex = _extras_gol(c, tip, retea)
    ex.update(detecteaza_cartus(c))
    intr = {"tip_schema": tip} if tip else {}
    _compensare(c, tip, intr)
    _compensare_cosfi(c, tip, intr)
    if tip == "locuinta":
        c._td_loc = _tablouri_locuinta(c)                     # r7: TE etaj / TD garaj / corp 2 (cablul lui ≠ coloana)
    if tip in ("tablou", "pt", "cef", "prosumator", "bransament", "locuinta"):
        c._cablu_impus = cablu_impus(c)                       # „3x185+95 Al” nu e listă de plecări (r5 #52)
    if tip == "tablou":
        origine_tablou(c, intr, ex)                           # r6: sursa („din PT 250 kVA”) nu e plecare
    _tensiune_jt(c, tip, intr)                                # r7 (#53): „690 V” — în afara domeniului (U_V)
    if tip in ("tablou", "pt"):
        _q_general(c, tip, intr)                              # r8 (#18, #22): „ACB 1600A” = întrerupătorul general
    if tip in ("tablou", "pt"):
        _atribute_globale(c, intr)                            # r10: „ks 0.7, cos 0.85”, „ku = 0,7”, „Pc = 126 kW”
    if tip in ("tablou", "pt"):
        c.t_lista = c.mascat()
        c.lista = parseaza_lista(c)
        ex["_nume_tablou"] = _nume_tablou(c)
        if c.lista:                                            # materialul/pozarea generale: din afara listei
            ex.update(_detectii_cablu(c, c.mascat()))
    m = re.search(rf"cos\s*(?:fi|φ|phi)\s*(?:actual\w*|existent\w*|initial\w*|masurat\w*|mediu)?\s*(?:=|de|:)?\s*({NUM})",
                  c.mascat())
    if m:
        ex["cosfi"] = intr["cosfi"] = numar(m.group(1))
        c.consumat.append((m.start(), m.end()))
    vals = valori(c.mascat())
    note_text(c, valori(c.t))
    if tip in ("tablou", "pt", "cef", "prosumator", "ge_ats", "bransament"):
        schema_pamant(c, intr, ex)
    if tip == "ge_ats":
        _domeniu_ge(c, intr)
    if tip in ("bransament", "prosumator") and retea_declarata(c) is None:
        ex["_retea_lipsa"] = True
    if tip == "bransament":
        if retea_declarata(c):
            intr["retea"] = retea_declarata(c)
        ex["puteri"] = extrage_bransament(c, vals, intr, ex)
    elif tip in ("tablou", "pt"):
        ex["puteri"] = extrage_tablou(c, vals, intr, ex, tip)
        _r10_tablou(c, intr, ex)
    elif tip == "cef":
        ex["puteri"] = extrage_cef(c, vals, intr, ex)
    elif tip == "prosumator":
        ex["puteri"] = extrage_prosumator(c, vals, intr, ex)
    elif tip == "ge_ats":
        ex["puteri"] = extrage_ge(c, vals, intr, ex)
    if ex.get("_retea_lipsa") and getattr(c, "_retea_model", None) and not getattr(c, "_retea_nestiuta", False):
        intr["retea"] = ex["retea"] = c._retea_model                 # r7: din modelul invertorului (…LP3, MIN …TL-X)
        ex.pop("_retea_lipsa")
        c.nota(f"rețea nedeclarată → {'trifazat 3 × 400 V' if c._retea_model == 'tri' else 'monofazat 230 V'} din modelul "
               "invertorului (fișa tehnică)")
    if ex.get("_retea_lipsa"):
        # nu se presupune — DOAR dacă puterea nu încape fizic în monofazat (BMPM max. 40 A) rețeaua rezultă trifazată
        P = intr.get("P_kW") or intr.get("Pn_inv_kW") or ((intr.get("S_kVA") or 0) * 0.9) or None
        ib_mono = (P * 1000 / (U_MONO * 0.9)) if P else (intr.get("Ib_A") or None)
        if ib_mono and ib_mono > norme.BMPM["I_max_A"]:
            intr["retea"] = ex["retea"] = "tri"; ex.pop("_retea_lipsa")
            c.nota(f"rețea nedeclarată, dar {fmt(P) + ' kW' if P else fmt(ib_mono) + ' A'} nu încape în monofazat (BMPM max. "
                   f"{fmt(norme.BMPM['I_max_A'], 0)} A) → trifazat 3 × 400 V")
    elif tip == "locuinta":
        _r10_locuinta_inainte(c)
        ex["puteri"] = extrage_locuinta(c, intr, ex)
        _r10_locuinta(c, intr, ex)
    mo = RE_OFFGRID.search(c.t)
    if tip in ("cef", "prosumator") and mo:                    # r7 (#66): off-grid ≠ racord la rețea
        c.foloseste(mo.start(), mo.end())
        c.probleme.append(("I12", f"„{c.o(mo.start(), mo.end()).strip()}”: sistemul off-grid (fără racord la rețeaua OD) e în "
                                  "afara domeniului aplicației — schemele PV de aici sunt de racordare (PI, contor "
                                  "bidirecțional) (I12).",
                           "Sistemul e off-grid (autonom, fără rețea), sau e racordat la rețea (prosumator on-grid)?"))
    m = re.search(rf"(?:armonic\w*\s*3|\bh3)\D{{0,12}}?({NUM})\s*%", c.t)
    if m:
        intr["h3"] = _nr(numar(m.group(1)))
    if tip in ("locuinta", "bransament") and intr.get("schema_pamant") == "TN-S":
        intr["schema_pamant"] = ex["schema_pamant"] = "TN-C-S"
        c.nota("„TN-S” la o instalație din rețeaua publică = TN-C-S pe branșament (TN-S în aval de separarea PEN din "
               "BMPT/BMPM)")
    if getattr(c, "_retea_nestiuta", False) and not any("Rețeaua nu se presupune" in q for _, q in c.intrebari):
        c.intrebari.append(("I02", "Instalația este monofazată (230 V) sau trifazată (3 × 400 V)? Rețeaua nu se presupune"
                                   + (" (trifazat propus: puterea nu încape în monofazat)." if intr.get("retea") == "tri" else ".")))
    if getattr(c, "_prize_presupuse", None):
        txt = ", ".join(f"„{x}”" for x in dict.fromkeys(c._prize_presupuse))
        c.nota(f"{txt}: circuite fără calibru → 16 A pe circuitul de prize, 10 A pe cel de iluminat (PRESUPUS)")
        c.intrebari.append(("I02", f"Calibrul circuitelor {txt} nu e scris — desenate cu 16 A (prize) / 10 A (iluminat) pe "
                                   "circuit. Confirmați sau indicați calibrul / puterea?"))
    if c.fara_valoare:
        c.intrebari.append(("I02", "Lipsesc puterea (kW) sau calibrul (A) pentru: " + ", ".join(

            f"„{x}”" for x in dict.fromkeys(c.fara_valoare)) + ". Care sunt? (până atunci nu sunt desenate)"))
    if tip == "cef" and isinstance(intr.get("bess"), dict) and not intr.get("invertoare") and not intr.get("Pn_inv_kW") \
            and not re.search(r"\d\s*(?:kw|mw|kva)\b", c.t):        # r9 (fotovoltaic #60): „BESS 100 kWh” — PCS nescris
        c.intrebari.append(("I02", f"Ce putere are convertorul bateriei (PCS, kW)? Până la răspuns: PCS "
                                   f"{fmt(intr['bess'].get('P_kW') or 0)} kW (0,5C, presupus)."))
    if tip in ("prosumator", "cef"):
        _retea_mixta_pv(c, intr, ex)
        mex = re.search(rf"\binvertor\w*\s+(?:pv\s+|fotovoltaic\s+|solar\s+)?existent\w*\s+(?:de\s+)?(?P<v>{NUM})\s*kw\b|\b(?P<v2>{NUM})\s*kw\s+(?:deja\s+)?existent\w*", c.t)
        if mex:                  # r9 (locuințe #52): invertorul existent se marchează (nu se desenează / listează ca nou)
            pv_ = numar(mex.group("v") or mex.group("v2"))
            inv_ = intr.get("invertoare")
            if not inv_ and intr.get("Pn_inv_kW") and abs(intr["Pn_inv_kW"] - pv_) < 0.01:
                inv_ = intr["invertoare"] = [{"n": 1, "Pn_kW": _nr(pv_)}]
            for g in inv_ or []:
                if abs((g.get("Pn_kW") or 0) - pv_) < 0.01:
                    g["existent"] = True
                    c.foloseste(mex.start(), mex.end())
                    c.nota(f"„{c.o(mex.start(), mex.end()).strip()}” = invertor EXISTENT (se păstrează; nu intră în lista "
                           "de echipamente noi)")
                    break
    al = intr.get("alimentare") or {}
    if tip == "locuinta" and al.get("In_Q_bransament_A") and al.get("P_aprobata_kW") and intr.get("retea"):
        # r9 (locuințe #61): „Q branșament 100 A” pe Pa 15 kW — Q-ul îl stabilește OD după Pa (ATR), nu „să nu sară”
        q, pa_ = al["In_Q_bransament_A"], al["P_aprobata_kW"]
        ib = pa_ * 1000 / ((U_TRI if intr["retea"] == "tri" else U_MONO) * 0.9)
        q_uz = next((x for x in (16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160, 200, 250) if x >= ib), None)
        if q_uz and q > 1.6 * q_uz:
            c.intrebari.append(("I08", f"Q branșament {fmt(q)} A e mult peste Pa {fmt(pa_)} kW (Ib ≈ {fmt(ib, 0)} A → Q uzual "
                                       f"{q_uz} A): calibrul îl stabilește OD prin ATR după puterea aprobată; un Q mai mare "
                                       "cere mărire de putere (ATR nou), nu evită declanșările. Rămâne Q "
                                       f"{fmt(q)} A (cu ATR pentru mai multă putere) sau Q {q_uz} A?"))
    if tip == "bransament" and intr.get("Q_In_A") and intr.get("P_kW") and intr.get("retea") in ("tri", "mono"):
        ib_ = intr["P_kW"] * 1000 / ((U_TRI if intr["retea"] == "tri" else U_MONO) * 0.95)
        if ib_ > intr["Q_In_A"] * 1.05:
            # r10 (locuințe #35): „BMPT 3x25A existent, vreau 22 kW fără mărire” — întrebare (nu blocaj tăcut V04)
            c.intrebari.append(("I08", f"{fmt(intr['P_kW'])} kW ≈ {fmt(ib_, 0)} A > Q {fmt(intr['Q_In_A'])} A existent: fără mărire "
                                       f"de putere încap ≈ {fmt(intr['Q_In_A'] * (U_TRI if intr['retea'] == 'tri' else U_MONO) * 0.95 / 1000, 1)} kW. "
                                       "Cereți ATR pentru mărire (Q mai mare), sau limitați puterea simultană (DLM / ks)?"))
    mbt = re.search(r"\bbmpt\w*(?:\s+(?:trifaz\w*|tri|3\s*×\s*\d+\s*a))", c.t)
    mtm = re.search(r"\b(?:tablou\w*|te|td|tg)(?:\s+\w+)?\s+monofaz\w*", c.t)
    if mbt and mtm and intr.get("retea") == "mono":
        # r10 (industrial #39): „BMPT trifazat 32 A, tablou monofazat” — contradicția se întreabă (nu branșament mono tăcut)
        c.foloseste(mbt.start(), mbt.end())
        c.foloseste(mtm.start(), mtm.end())
        c.intrebari.append(("I08", f"„{c.o(mbt.start(), mbt.end()).strip()}” și „{c.o(mtm.start(), mtm.end()).strip()}”: tabloul e "
                                   "monofazat, alimentat de pe o fază a BMPT-ului trifazat (circuite L+N), sau e trifazat "
                                   "(3 × 400/230 V)?"))
    R11.post(c, intr, ex, tip, sys.modules[__name__])          # r11: UPS, AAR, GE izolat, PV, locuință, rețea dedusă
    R12.aplica(c, intr, ex, tip, sys.modules[__name__])        # r12: cablurile / racordul / QG / monitorizarea pe segmente
    neconsumat = plasa_siguranta(c, intr, tip)
    if neconsumat:
        c.intrebari.append(("I15", "Nu am folosit în schemă: " + "; ".join(f"„{x}”" for x in neconsumat)
                                   + ". Ce reprezintă și unde se aplică? (până atunci nu apar pe planșă)"))
    return _finalizeaza(intr, ex, c.note, c.probleme, motor="reguli", intrebari=c.intrebari, avert=c.avert,
                        neconsumat=neconsumat)


def _retea_mixta_pv(c: Ctx, intr: dict, ex: dict):
    """r9 (fotovoltaic #55): „1 x SUN2000-10KTL-M1 trifazat + 1 x SUN2000-5KTL-L1 monofazat pe L1, BMPT 3x40 A” —
    un invertor trifazat (sau BMPT 3×) face instalația TRIFAZATĂ; invertorul monofazat stă pe faza declarată."""
    grupuri = intr.get("invertoare") or []
    if len(grupuri) < 2:
        return
    fel = []
    for g in grupuri:
        mod = (g.get("model") or "").upper()
        poz = c.t.find(mod.lower()) if mod else -1
        dupa = c.t[poz + len(mod):poz + len(mod) + 30] if poz >= 0 else ""
        dupa = re.split(r"[,;+]|\bsi\b", dupa)[0]
        if re.search(r"monofaz\w*|\bmono\b|\b1f\b", dupa) or re.search(r"-L\d\b|\bSUNNY\s+BOY|-1\b", mod):
            mf = re.search(r"\bpe\s+(?:faza\s+)?(l[123])\b", dupa)
            fel.append(("mono", g, mf.group(1).upper() if mf else None))
        elif re.search(r"trifaz\w*|\btri\b|\b3f\b", dupa) or re.search(r"KTL-M\d|LP3|HP3|-3\b|\bSTP", mod):
            fel.append(("tri", g, None))
        else:
            fel.append((None, g, None))
    if not any(f == "mono" for f, _, _ in fel) or not (any(f == "tri" for f, _, _ in fel) or re.search(r"\bbmpt\w*\s+3\s*×", c.t)):
        return
    intr["retea"] = ex["retea"] = "tri"
    libere = ["L1", "L2", "L3"]
    for f, g, faza in fel:
        if f == "mono" and not g.get("faza"):      # r10 (P0 #41): faza deja repartizată / declarată nu se suprascrie
            g["faza"] = faza or next((x for x in libere if x not in [k.get("faza") for _, k, _ in fel]), "L1")
    c.probleme[:] = [p for p in c.probleme if "monofazat" not in p[1] or "Contradic" not in p[1]]
    c.intrebari[:] = [q for q in c.intrebari if not q[1].startswith("Iac,max = 1,1·")]
    faze = {"L1": 0.0, "L2": 0.0, "L3": 0.0}
    for f, g, _ in fel:
        n_p = g.get("n", 1) * (g.get("Pn_kW") or 0) * 1000 * FACTOR_INV
        if f == "mono":
            faze[g["faza"]] += n_p / U_MONO
        else:
            for k in faze:
                faze[k] += n_p / (3 * U_MONO)
    q_r = intr.get("In_Q_bransament_A")
    fmax = max(faze, key=faze.get)
    if q_r and faze[fmax] > q_r + 1e-6:
        c.intrebari.append(("I08", f"Iac,max pe faza {fmax} ≈ {fmt(faze[fmax], 0)} A > BMPT {fmt(q_r)} A: se mărește protecția / "
                                   "branșamentul, sau se mută invertorul monofazat pe altă fază / se limitează puterea?"))
    c.nota("rețea mixtă: invertor trifazat + invertor monofazat (" + ", ".join(
        f"{g.get('model') or fmt(g.get('Pn_kW')) + ' kW'} pe {g['faza']}" for f, g, _ in fel if f == "mono")
        + ") → instalație trifazată 3 × 400 V")


def _finalizeaza(intr, ex, note, probleme, motor, intrebari=(), avert=(), neconsumat=()) -> dict:
    """Verificări F.7 → presupuneri F.6 → răspuns F.8."""
    d = verifica(intr, ex, probleme)
    for cod, q in intrebari:                          # r5: întrebări din citirea textului (se generează ȘI se întreabă)
        if q not in d.intrebari:
            d.intreaba(cod, q)
    for a in avert:
        if a not in d.avertismente:
            d.avertismente.append(a)
    iac_q, unice = set(), []                          # r10 (P2 #53): aceeași întrebare Iac > Q din două reguli → una
    for q in d.intrebari:
        mq = re.match(r"Iac,max\b.*?>\s*(?:Q\s+)?(?:BMPT|întrerupătorul din TG)\s+(\d+)", q)
        if mq and mq.group(1) in iac_q:
            continue
        if mq:
            iac_q.add(mq.group(1))
        unice.append(q)
    d.intrebari = unice
    if d.actiune == "genereaza" and d.intrebari:      # R1: se generează ȘI se întreabă
        d.actiune = "genereaza_cu_intrebare"
    presupus = [] if d.actiune == "refuza" else _unice(note + d.presupus + presupuneri(intr, ex))
    if d.actiune == "refuza":
        presupus = []
    for n_ in _chei_motor(intr):                       # r11: nicio cheie pe care motorul o refuză (V96 „nesuportat”)
        if n_ not in presupus and d.actiune != "refuza":
            presupus.append(n_)
    cartus = {"beneficiar": ex.get("beneficiar"), "adresa": ex.get("adresa"),
              "plansa": ex.get("plansa"), "faza": ex.get("faza")}
    extras = {k: v for k, v in ex.items() if not k.startswith("_") and k != "tip_schema"}
    rez = {"actiune": d.actiune, "tip_schema": intr.get("tip_schema"), "intrare_fizica": intr, "extras": extras,
           "cartus": cartus, "presupus": presupus, "intrebari": d.intrebari, "avertismente": d.avertismente,
           "refuz_cod": d.cod if d.actiune == "refuza" else None,
           "refuz_motiv": d.motiv if d.actiune == "refuza" else None, "motor": motor,
           "neconsumat": list(neconsumat), "_deduse": list(intr.get("_deduse") or [])}
    rez["intelegere"] = text_raspuns(rez)
    return rez


def _chei_motor(intr: dict) -> list[str]:
    """r11: motorul refuză (V96) cheile pe care schema aleasă nu le folosește (engine/calc/chei.py). Cheile istorice ale
    interpretorului se mapează pe cele acceptate (PT: ATS între trafo → `aar`; măsura semidirectă → `masura: JT`); restul
    se păstrează doar ca metadate `_cheie` (vizibile în „Am presupus”), nu ca intrare de motor."""
    try:
        from .calc import chei as _ch
    except ImportError:
        from engine.calc import chei as _ch  # type: ignore
    tip = intr.get("tip_schema")
    note = []
    if tip == "pt":
        if intr.get("sursa_rezerva") == "trafo" and intr.get("n_trafo") == 2:
            intr["aar"] = True
            if intr.get("cupla") != "inchisa":
                intr["cupla"] = "deschisa"
        if intr.get("masura_ceruta") and not intr.get("masura"):
            intr["masura"] = "JT"
            note.append(f"măsura {intr['masura_ceruta']} pe JT (masura: JT, cu TC)")
    for cale, k in _ch.chei_nefolosite(intr, tip):
        if cale:
            # r12: cheile noi pe elementele listelor (invertoare[].prot_tip …) — informative până le citește motorul
            mc = re.fullmatch(r"(\w+)\[(\d+)\]", cale)
            if mc and isinstance(intr.get(mc.group(1)), list) and int(mc.group(2)) < len(intr[mc.group(1)]):
                el = intr[mc.group(1)][int(mc.group(2))]
                if isinstance(el, dict) and k in el:
                    el["_" + k] = el.pop(k)
            continue
        intr["_" + k] = intr.pop(k)
        note.append(f"„{k}” nu e o dată a schemei „{tip}” — păstrată doar informativ (nu intră în calcul)")
    return note


def _unice(lista):
    out = []
    for x in lista:
        if x not in out:
            out.append(x)
    return out


# =====================================================================================================
# F.8 Răspunsul
# =====================================================================================================
def _puteri_text(p: dict) -> str:
    bucati = []
    for k, eticheta, u in (("P_kW", "P", "kW"), ("Ib_A", "Ib", "A"), ("S_kVA", "S", "kVA"), ("Q_In_A", "Q", "A"),
                           ("In_Q1_A", "Q1", "A"),
                           ("Sn_kVA", "Sn", "kVA"), ("kWp", "P c.c.", "kWp"), ("P_ca_kW", "P c.a.", "kW"),
                           ("Sn_GE_kVA", "Sn GE", "kVA"), ("baterie_kWh", "baterie", "kWh"),
                           ("P_aprobata_kW", "P aprobată", "kW"), ("P_evacuata_kW", "P evacuată", "kW"),
                           ("limitare_injectie_kW", "injecție limitată la", "kW")):
        if p.get(k) is not None:
            bucati.append(f"{eticheta} = {fmt(p[k])} {u}".replace("la =", "la"))
    for i in p.get("invertoare") or []:
        fisa = " ".join(x for x in (i.get("producator"), i.get("model")) if x)
        bucati.append(f"{i['n']} × invertor {fmt(i['Pn_kW'])} kW" + (f" ({fisa})" if fisa else ""))
    b = p.get("bess")
    if b:
        fisa = " ".join(x for x in (b.get("producator"), b.get("model")) if x)
        bucati.append("BESS " + " / ".join(x for x in (f"{fmt(b['P_kW'])} kW" if b.get("P_kW") else None,
                                                      f"{fmt(b['kWh'])} kWh" if b.get("kWh") else None) if x)
                      + (f" ({fisa})" if fisa else ""))
    return ", ".join(bucati)


def _plecari_text(pl) -> str:
    out = []
    for p in pl:
        s = p["nume"]
        if p["valoare"] is not None:
            s += f" {fmt(p['valoare'])} {p['unitate']}"
        if p.get("n_circuite"):
            s += f" × {p['n_circuite']} circuite"
        if "L_m" in p:
            s += f" ({fmt(p['L_m'])} m)"
        if p.get("pornire"):
            s += {"stea_triunghi": ", pornire stea-triunghi", "convertizor": ", cu convertizor", "soft": ", soft-starter",
                  "directa": ", pornire directă"}[p["pornire"]]
        if p.get("copii"):
            s += " cu sub-plecări: " + _plecari_text(p["copii"])
        out.append(s)
    return ", ".join(out)


def _parti_locuinta(r: dict) -> list[str]:
    """Locuința pe scurt: tip, rețea, P aprobată, Q, coloană, schema de pământ, nr. circuite, receptorii dedicați."""
    ex, intr = r["extras"], r["intrare_fizica"]
    al = intr.get("alimentare") or {}
    descr = DESCR_LOCUINTA.get(ex.get("locuinta"))
    parti = [f"locuință ({descr}) " + ({"mono": "monofazată 230 V", "tri": "trifazată 3 × 400 V"}.get(intr.get("retea"), "— rețea nespecificată"))
             if descr else "locuință"]
    if al.get("tip"):
        parti.append({"bransament_nou": "branșament nou", "bransament_existent": "branșament existent"}[al["tip"]])
    if al.get("P_aprobata_kW") is not None:
        parti.append(f"P aprobată = {fmt(al['P_aprobata_kW'])} kW")
    if al.get("In_Q_bransament_A") is not None:
        parti.append(f"Q branșament {fmt(al['In_Q_bransament_A'])} A")
    if al.get("L_coloana_m") is not None:
        parti.append(f"coloana {fmt(al['L_coloana_m'])} m")
    if intr.get("schema_pamant"):
        parti.append(f"schema {intr['schema_pamant']}" + (f" (RA = {fmt(intr['RA_ohm'])} Ω)" if intr.get("RA_ohm") else ""))
    if intr.get("ks") is not None:
        parti.append(f"ks = {fmt(intr['ks'], 2)}")
    circ = intr.get("circuite") or []
    if circ:
        dedicati = []
        for x in circ:
            if x["receptor"] in GENERICE_LOC:
                continue
            s = x["nume"] + (f" {fmt(x['P_kW'])} kW" if "P_kW" in x else "") + (" (3F)" if x.get("faza") == "3F" else "")
            dedicati.append(s)
        parti.append(f"{len(circ)} circuite" + (f", dintre care dedicate: {', '.join(dedicati)}" if dedicati else ""))
    return parti


def text_raspuns(r: dict) -> str:
    ex = r["extras"]
    tip = r["tip_schema"]
    parti = [NUME_TIP.get(tip, "schemă nedeterminată")]
    if tip in ("bransament", "prosumator"):
        ret = (r.get("intrare_fizica") or {}).get("retea")
        parti[0] += " " + {"mono": "monofazat", "tri": "trifazat"}.get(ret, "— rețea nespecificată")
    if tip == "locuinta":
        parti = _parti_locuinta(r)
    if ex.get("puteri") and tip != "locuinta":
        parti.append(_puteri_text(ex["puteri"]))
    intr = r.get("intrare_fizica") or {}
    if tip in ("cef", "tablou") and intr.get("retea"):
        parti.append({"mono": "monofazat", "tri": "trifazat"}[intr["retea"]])
    if intr.get("modul"):
        m = intr["modul"]
        parti.append("module " + " ".join(x for x in (m.get("producator"), m.get("model")) if x)
                     + (f" {fmt(m['Pmax_W'])} W" if m.get("Pmax_W") else ""))
    if intr.get("racord"):
        parti.append({"tg_existent": "racord în TG existent", "bmpt": "racord prin BMPT", "pt": "racord în PT"}
                     [intr["racord"]])
    if intr.get("origine") and tip == "tablou":
        parti.append({"pt_propriu": "alimentat din PT", "tg_existent": "alimentat din tabloul existent",
                      "bmpt": "alimentat din rețea (BMPT)", "retea_publica": "alimentat din rețea"}[intr["origine"]])
    if intr.get("sursa_retea") and tip == "ge_ats":
        parti.append({"pt": "rețea din PT", "tgd": "rețea din TGD", "bmpt": "rețea prin BMPT"}[intr["sursa_retea"]])
    if intr.get("schema_pamant") and tip != "locuinta":
        parti.append(f"schema {intr['schema_pamant']}" + (f" (RA = {fmt(intr['RA_ohm'])} Ω)" if intr.get("RA_ohm") else ""))
    if ex.get("plecari"):
        parti.append(f"{len(ex['plecari'])} plecări: {_plecari_text(ex['plecari'])}")
    for k, v in (ex.get("lungimi_m") or {}).items() if tip != "locuinta" else ():
        parti.append({"C2": "coloana C2", "alimentare": "alimentarea", "plecari": "plecările"}[k] + f" {fmt(v)} m")
    for k in ("material", "izolatie", "metoda"):
        if ex.get(k):
            parti.append(f"{k} {ex[k]}")
    cart = r["cartus"]
    if cart["beneficiar"]:
        parti.append(f"beneficiar {cart['beneficiar']}")
    adr = cart["adresa"] or {}
    if adr.get("localitate"):
        parti.append(adr["localitate"] + (f", jud. {adr['judet']}" if adr.get("judet") else ""))
    for k, et in (("plansa", "planșa"), ("faza", "faza")):
        if cart[k]:
            parti.append(f"{et} {cart[k]}")
    linii = ["Am înțeles: " + ", ".join(parti) + "."]
    if r.get("neconsumat"):
        linii.append("Nu am înțeles: " + "; ".join(f"„{x}”" for x in r["neconsumat"]) + ".")
    if r["actiune"] == "refuza":
        linii.append(f"Nu pot genera schema: {r['refuz_motiv']}")
    if r["presupus"]:
        linii.append("Am presupus: " + "; ".join(r["presupus"]) + ".")
    if r["avertismente"]:
        linii.append("Verificări: " + "; ".join(r["avertismente"]) + ".")
    for q in r["intrebari"]:
        linii.append("Întrebare: " + q)
    return "\n".join(linii)


# =====================================================================================================
# Normalizare și validare de formă a `intrare_fizica` (folosite pentru rezultatul LLM)
# =====================================================================================================
_CHEI_NUMERICE = {"P_kW", "Ib_A", "S_kVA", "L_coloana_m", "L_alimentare_m", "In_Q1_A", "kWp", "pt_Sn_kVA", "Sn_kVA", "Pn_inv_kW",
                  "Sn_GE_kVA", "P_sarcina_kW", "cosfi", "h3", "baterie_kWh", "In_Q_JT_A", "In_QG_A",
                  "In_Q_bransament_A", "L_pcs_m", "RA_ohm", "ks",
                  # r5
                  "Q_In_A", "Ik3_sursa_kA", "Ik3_TG_kA", "racord_In_Q_A", "L_racord_m", "L_inv_m", "L_GE_ATS_m",
                  "In_Q_retea_A", "limitare_injectie_kW", "P_aprobata_kW", "P_evacuata_kW", "gpv_In_A",
                  # r6
                  "compensare_kvar", "compensare_L_m", "U_MT_kV", "n_trafo", "SkQ_MVA", "uk_pct", "n_tgd_cf",  # r10
                  # r7
                  "U_V", "U_ca_V", "U_inv_ca_V", "U_JT_V", "P_sarcina_kW", "In_Q_amonte_A"}
_CHEI_TEXT = {"tip_schema": set(TIPURI), "retea": {"tri", "mono"}, "material": {"Cu", "Al"},
              "masura_ceruta": {"directa", "semidirecta"}, "celula_trafo": {"sigurante", "intreruptor"},
              "origine": {"retea_publica", "pt_propriu", "tg_existent", "bmpt"},
              "schema_pamant": {"TN-C-S", "TN-S", "TT", "TN-C", "IT"}, "bmpt_fortat": set(norme.BMPT),
              # r5
              "racord": {"tg_existent", "bmpt", "pt"}, "sursa_retea": {"bmpt", "pt", "tgd"},
              "trafo_izolatie": {"ulei", "uscat"}, "masura": {"MT", "JT"},
              # r7
              "cupla": {"inchisa", "deschisa"}, "comutare": {"manual", "ATS"}, "titlu_tablou": None,
              # r10
              "sursa_rezerva": {"trafo"}, "bara": {"T1", "T2", "T3", "T4"}, "separare_PEN": {"TG", "BMPT"},
              "racord_Q_tip": {"gG", "MCCB", "ACB", "MCB"}}
_CHEI_TEXT["masura_ceruta"] = {"directa", "semidirecta"}
_CHEI_BOOL = {"atr_jt", "hibrid", "circuite_finale", "pt_existent", "ge_paralel", "pt_aerian", "siguranta_tablou",
              "plecari_pe_sectie",
              "fara_retea", "pt_od"}                                                    # r10
_CHEI_FISA = ("producator", "model")
_CHEI_CABLU = {"material": {"Cu", "Al"}, "izolatie": {"PVC", "XLPE"}, "metoda": {"C", "D1", "D2", "E"}}


def _numar_sau_none(v):
    try:
        return _nr(numar(v) if isinstance(v, str) else float(v))
    except (TypeError, ValueError):
        return None


def _normalizeaza_cablu(cb):
    if not isinstance(cb, dict):
        return None
    out = {k: cb[k] for k in _CHEI_CABLU if cb.get(k) in _CHEI_CABLU[k]}
    for k in ("n_alte", "S_fortat", "N_fortat", "PE_fortat", "n_fortat", "n_paralel", "theta", "rho_sol"):
        if cb.get(k) is not None and _numar_sau_none(cb[k]) is not None:
            out[k] = _numar_sau_none(cb[k])
    return out or None


def _normalizeaza_plecare(p):
    if not isinstance(p, dict) or not str(p.get("nume") or "").strip():
        return None
    out = {"nume": str(p["nume"]).strip()}
    for k in ("In_A", "P_kW", "L_m", "cosfi", "randament", "sectie"):
        if p.get(k) is not None and _numar_sau_none(p[k]) is not None:
            out[k] = _numar_sau_none(p[k])
    if p.get("rezerva") is True:
        out["rezerva"] = True
    if p.get("receptor") in ("iluminat", "prize", "forta", "motor", "tablou"):
        out["receptor"] = p["receptor"]
    if p.get("pornire") in ("directa", "stea_triunghi", "convertizor", "soft"):
        out["pornire"] = p["pornire"]
    if p.get("retea") in ("mono", "tri"):
        out["retea"] = p["retea"]
    if p.get("curba") in ("B", "C", "D"):
        out["curba"] = p["curba"]
    n = _numar_sau_none(p.get("n_circuite"))
    if n and n >= 1 and float(n).is_integer():
        out["n_circuite"] = int(n)
    if isinstance(p.get("copii"), list):
        out["copii"] = [x for x in (_normalizeaza_plecare(k) for k in p["copii"]) if x]
    cb = _normalizeaza_cablu(p.get("cablu"))
    if cb:
        out["cablu"] = cb
    for k, v in _isch_mod.curata_plecare(p).items():      # F.9: siguranta, ks, S_kVA … din schema generată
        if k not in out and k != "copii":
            out[k] = v
    return out


def normalizeaza_intrare(d: dict) -> dict:
    """Păstrează doar cheile cunoscute (forma din cazuri_golden.json → intrare), cu tipuri corecte."""
    if not isinstance(d, dict):
        return {}
    out = {}
    for k, v in d.items():
        if k in _CHEI_NUMERICE and _numar_sau_none(v) is not None:
            out[k] = _numar_sau_none(v)
        elif k in _CHEI_TEXT and (v in _CHEI_TEXT[k] if _CHEI_TEXT[k] is not None else isinstance(v, str)):
            out[k] = v
        elif k in _CHEI_BOOL and isinstance(v, bool):
            out[k] = v
        elif k == "_deduse" and isinstance(v, list):          # r11: cheile deduse (panoul de confirmare le marchează)
            out[k] = [str(x) for x in v if isinstance(x, str)]
    for k in ("cablu", "cablu_pcs"):
        cb = _normalizeaza_cablu(d.get(k))
        if cb:
            out[k] = cb
    if isinstance(d.get("plecari"), list):
        out["plecari"] = [x for x in (_normalizeaza_plecare(p) for p in d["plecari"]) if x]
    if isinstance(d.get("invertoare"), list):
        # F.9: un grup fără Pn dar cu model rămâne — motorul ia Pn din catalog (și îl declară)
        out["invertoare"] = [{k: v for k, v in dict({"n": int(_numar_sau_none(i.get("n")) or 1),
                                                     "Pn_kW": _numar_sau_none(i.get("Pn_kW"))},
                                                    **{k: str(i[k]) for k in _CHEI_FISA if i.get(k)}).items() if v is not None}
                             for i in d["invertoare"] if isinstance(i, dict)
                             and (_numar_sau_none(i.get("Pn_kW")) or i.get("model"))]
    if isinstance(d.get("bess"), dict):
        b = {k: _numar_sau_none(d["bess"].get(k)) for k in ("P_kW", "kWh")}
        b.update({k: str(d["bess"][k]) for k in _CHEI_FISA if d["bess"].get(k)})
        if d["bess"].get("cuplaj") in ("cc", "ca"):
            b["cuplaj"] = d["bess"]["cuplaj"]
        if b["kWh"] or b["P_kW"]:
            out["bess"] = {k: v for k, v in b.items() if v is not None}
    for k in ("modul", "invertor", "baterie"):
        if isinstance(d.get(k), dict):
            f = {kk: str(d[k][kk]) for kk in _CHEI_FISA if d[k].get(kk)}
            for kk in ("Pmax_W", "Pn_kW", "kWh"):
                if _numar_sau_none(d[k].get(kk)):
                    f[kk] = _numar_sau_none(d[k][kk])
            if f:
                out[k] = f
    if isinstance(d.get("string"), dict):
        st = {k: int(_numar_sau_none(d["string"][k])) for k in ("n_module", "n_stringuri_paralel", "n_MPPT")
              if _numar_sau_none(d["string"].get(k))}
        st.update({k: _numar_sau_none(d["string"][k]) for k in ("Uoc_V", "Isc_A", "gpv_In_A")
                   if _numar_sau_none(d["string"].get(k))})
        if d["string"].get("gpv") is True:
            st["gpv"] = True
        if st:
            out["string"] = st
    if isinstance(d.get("celule_mt"), list):
        out["celule_mt"] = [str(x) for x in d["celule_mt"] if x]
    for k in ("cablu_C0", "cablu_inv"):
        cb = _normalizeaza_cablu(d.get(k))
        if cb:
            out[k] = cb
    if isinstance(d.get("alimentare"), dict):                         # locuință
        a = d["alimentare"]
        al = {"tip": a["tip"]} if a.get("tip") in ("bransament_existent", "bransament_nou") else {}
        for k in ("In_Q_bransament_A", "P_aprobata_kW", "L_coloana_m"):
            if a.get(k) is not None and _numar_sau_none(a[k]) is not None:
                al[k] = _numar_sau_none(a[k])
        cb = _normalizeaza_cablu(a.get("cablu"))
        if cb:
            al["cablu"] = cb
        out["alimentare"] = al
    if isinstance(d.get("circuite"), list):
        out["circuite"] = [x for x in (_normalizeaza_circuit_loc(c) for c in d["circuite"]) if x]
    if isinstance(d.get("consumatori"), list):                        # r6: GE
        out["consumatori"] = [{k: v for k, v in c.items() if k in ("nume", "P_kW", "n", "pornire", "siguranta", "rezerva", "vital")}
                              for c in d["consumatori"] if isinstance(c, dict) and _numar_sau_none(c.get("P_kW"))]
    if isinstance(d.get("tablouri_secundare"), list):                 # r6: locuință
        out["tablouri_secundare"] = [
            {"nume": str(t.get("nume") or "TD"), **({"L_m": _numar_sau_none(t["L_m"])} if _numar_sau_none(t.get("L_m")) else {}),
             "circuite": [x for x in (_normalizeaza_plecare(k) for k in t.get("circuite") or []) if x]}
            for t in d["tablouri_secundare"] if isinstance(t, dict)]
    # F.9: restul cheilor cunoscute de schema generată (engine/interp_schema.py), curățate după tip; în obiectele
    # imbricate (bess, alimentare, tablouri_secundare[], invertoare[]) se completează cheile lăsate de normalizarea veche
    _completeaza_din_schema(out, _isch_mod.curata(d))
    return out


def _completeaza_din_schema(out: dict, curat: dict):
    for k, v in curat.items():
        if k not in out:
            out[k] = v
        elif k in ("plecari", "circuite"):
            continue                                      # tratate element cu element (curata_plecare)
        elif isinstance(out[k], dict) and isinstance(v, dict):
            _completeaza_din_schema(out[k], v)
        elif isinstance(out[k], list) and isinstance(v, list) and len(out[k]) == len(v):
            for a, b in zip(out[k], v):
                if isinstance(a, dict) and isinstance(b, dict):
                    _completeaza_din_schema(a, {kk: vv for kk, vv in b.items() if kk not in ("circuite", "copii")})


def _normalizeaza_circuit_loc(c):
    """Circuit de locuință: {nume, receptor ∈ enum (necunoscut → alt_circuit), P_kW, L_m, faza, cablu}."""
    if not isinstance(c, dict):
        return None
    rec = str(c.get("receptor") or "").strip().lower()
    out = {"nume": str(c.get("nume") or "").strip() or (rec.replace("_", " ").capitalize() if rec else "Circuit"),
           "receptor": rec if rec in ENUM_RECEPTORI_LOC else "alt_circuit"}
    for k in ("P_kW", "L_m"):
        if c.get(k) is not None and _numar_sau_none(c[k]) is not None:
            out[k] = _numar_sau_none(c[k])
    f = str(c.get("faza") or "").strip().upper()
    if f in FAZE_LOC:
        out["faza"] = f
    cb = _normalizeaza_cablu(c.get("cablu"))
    if cb:
        out["cablu"] = cb
    return out


def valideaza_forma(d: dict) -> list[str]:
    """Erori de formă care fac intrarea inutilizabilă (rezultatul LLM se aruncă dacă există)."""
    err = []
    tip = d.get("tip_schema")
    if tip not in TIPURI:
        err.append("tip_schema lipsă sau necunoscut")
    if tip == "tablou" and not (d.get("P_kW") or d.get("In_Q1_A") or d.get("plecari")):
        err.append("tablou fără putere și fără plecări")
    if tip == "pt" and not d.get("Sn_kVA"):
        err.append("PT fără Sn_kVA")
    if tip == "cef" and not d.get("invertoare") and not (d.get("bess") or {}).get("P_kW"):
        err.append("CEF fără invertoare")
    for g in d.get("invertoare") or []:
        if g.get("Pn_kW") is None:
            err.append(f"invertorul {g.get('model') or ''} fără Pn și necunoscut în catalog".replace("  ", " "))
    if tip == "locuinta" and not d.get("circuite"):
        err.append("locuință fără circuite")
    if tip == "locuinta" and d.get("retea") == "mono" and any(c.get("faza") not in (None, "L1")
                                                              for c in d.get("circuite") or []):
        err.append("locuință monofazată cu circuite pe altă fază decât L1")
    if tip == "bransament" and sum(1 for k in ("P_kW", "Ib_A", "S_kVA") if d.get(k)) != 1:
        err.append("branșament: trebuie exact una din P_kW / Ib_A / S_kVA (V12)")
    for p in d.get("plecari") or []:
        if "In_A" in p and "P_kW" in p:
            err.append(f"plecarea {p['nume']} are și In_A și P_kW")
    err += _isch_mod.valideaza(d)                      # F.9: forma față de schema generată (tipuri, enumerări, chei)
    return err


# =====================================================================================================
# F.9 Claude = interpretorul PRINCIPAL (când există cheie API); regulile locale = verificare încrucișată și rezervă
# =====================================================================================================
MODEL_LLM = "claude-opus-5-5"
BETA_LLM = "server-side-fallback-2026-07-01"
URL_API = "https://api.anthropic.com/v1/messages"
VERSIUNE_API = "2023-06-01"

_REGULI_LLM = """Ești interpretorul de text al unui generator de scheme monofilare JT din România (proiectare ANRE).
Primești descrierea scrisă de proiectant — frază liberă, email, extras de ATR copiat, tabel Excel/CSV lipit, uneori
în engleză — și răspunzi EXCLUSIV apelând unealta `intrare_fizica`, o singură dată.

Ce faci:
- Scrii DOAR ce spune textul, în cheile schemei. NU dimensiona nimic: fără secțiuni, calibre, protecții, căderi de
  tensiune, trafo „ales”. Cheile pe care textul nu le precizează LIPSESC (motorul aplică și declară implicitele).
- Nu ghici. Ce e ambiguu sau contradictoriu → `intrebari` (scurt, cu variantele posibile). Ce nu poți pune în schemă
  → `neinteles` (citat scurt din text). O întrebare nu oprește completarea a ceea ce e clar.

Reguli de domeniu:
1. Leagă fiecare valoare de entitatea ei: „pompa 7,5 kW” e puterea pompei, nu a tabloului; „casa 15 kW”, „pa 15 kW”,
   „P aprobată 15 kW” e puterea aprobată de consum, nu puterea invertorului; „din PT 400 kVA” / „din BMPT 70 kW” e
   SURSA tabloului (origine + pt_Sn_kVA / P_kW), nu o plecare; „cablu 5x16” e secțiune de cablu, nu 5 bucăți.
2. ATR / certificat de racordare: „putere aprobată pentru consum / absorbită” → P_aprobata_kW (la branșament: P_kW);
   „putere aprobată pentru evacuare / injecție” → P_evacuata_kW, iar dacă e mai mică decât puterea invertoarelor →
   limitare_injectie_kW cu aceeași valoare. „Injecție zero” → limitare_injectie_kW = 0. Calibrul BMPT existent
   („3x250 A”) → In_Q_bransament_A; racordul la bornele BMPT → racord "bmpt".
3. „N x MODEL” / „N buc. MODEL” = N bucăți din model. „N x” urmat de o secțiune (mm²) sau de un model de baterie NU e
   număr de invertoare („Deye … cu 4 x Pylontech US5000” = 1 invertor + 4 module baterie).
4. Tabele / liste: cantitatea din coloana „buc / cant / nr.” înmulțește rândul; fiecare rând e o plecare / un
   consumator. „6 circuite iluminat 16 A” = o plecare cu n_circuite 6. „3 x 63 A” = 3 plecări de 63 A.
5. Invertoare: „N invertoare de X kW” = X pe bucată; „CEF X kW cu N invertoare” = X total (Pn = X/N). Dacă textul nu
   permite să decizi (sau modelul contrazice puterea scrisă), completează varianta cea mai probabilă ȘI întreabă
   („N × X kW sau total X kW?”). Când puterea nu e scrisă, dă producator + model și LASĂ Pn_kW necompletat: motorul
   ia Pn din catalog (codul poate arăta Smax: SUN2000-330KTL-H1 = 300 kW). kWp (c.c.) ≠ kW (c.a.).
   BESS: „N x PCS P kW” → bess.n_pcs = N și bess.P_kW = puterea TOTALĂ; capacitatea în kWh (MWh × 1000).
   Invertoare monofazate „câte unul pe fiecare fază” → câte un grup n = 1 cu faza L1 / L2 / L3.
6. Rețeaua NU se presupune niciodată: retea doar dacă textul o spune (trifazat, 3x400, tri, mono, 230 V, „fază și
   nul”) sau dacă modelul numit e cunoscut ca trifazat/monofazat (…KTL-M1, …LP3 trifazat; …-L1, MIN …TL-X monofazat).
   La locuință / branșament / prosumator fără rețea → lipsește retea și pui întrebarea.
7. Pragul OD de 27 kW (prosumator): peste 27 kW OD cere protecție de interfață externă — o aplică motorul; nu o
   inventa, dar dacă textul cere ceva contrar (PI doar integrată la > 27 kW) → întrebare.
8. Consumatori de siguranță la incendiu (pompă incendiu / PSI, hidranți, sprinklere, jockey, desfumare, presurizare,
   stingere, centrală de detecție, iluminat de siguranță): marchează-i siguranta = true din context (plecari[].siguranta,
   la GE consumatori[].siguranta); un tablou dedicat lor (TDSI, „TE desfumare”, „tablou pompe incendiu”) →
   siguranta_tablou = true și titlu_tablou. O pompă „de
   rezervă” identică = același consumator cu n "1+1" sau rezerva = true — nu se adună la putere.
9. Tipul schemei: casă / apartament / vilă → locuinta (cu circuite pe receptori); doar branșamentul (BMPM/BMPT) →
   bransament; TG/TD/hală cu plecări → tablou; post de transformare / „PT 630 kVA cu plecări” → pt; CEF / centrală /
   BESS cu invertoare → cef; invertor pe branșamentul unui consumator (casă, firmă mică) → prosumator; grup
   electrogen + ATS → ge_ats. Dacă textul amestecă (casă + PV) alege ce cere proiectantul și pune întrebare.
10. Unități: MWp/MVA/MW/km → kWp/kVA/kW/m; CP → kW (×0,7355); virgula zecimală românească („2,5”).
11. Numele plecărilor se păstrează cum au fost scrise (prima literă majusculă). „PT” majuscul = post de
    transformare, „pt” minuscul = „pentru”. Date de cartuș (beneficiar, localitate, județ, planșă, fază) → cartus.
12. În afara domeniului (off-grid, > 2500 kVA, MT ca schemă principală, 690 V, UPS, întrebări de preț): nu inventa o
    schemă — pune tip_schema cel mai apropiat doar dacă textul îl justifică și explică în intrebari.
"""

EXEMPLE_LLM = [
    ("Deye SUN-12K-SG04LP3 cu 4 x Pylontech US5000, casa trifazata, TN-C-S",
     {"intrare_fizica": {"tip_schema": "prosumator", "retea": "tri", "schema_pamant": "TN-C-S", "Pn_inv_kW": 12,
                         "invertor": {"producator": "Deye", "model": "SUN-12K-SG04LP3", "Pn_kW": 12}, "hibrid": True,
                         "baterie": {"producator": "Pylontech", "model": "US5000"}},
      "intrebari": [], "neinteles": []}),
    ("Extras ATR: putere aprobata consum 40 kW; putere aprobata evacuare 30 kW. Racord la bornele BMPT existent 3x63A. "
     "Instalatie de producere: 3 invertoare Huawei SUN2000-12KTL-M5, trifazat.",
     {"intrare_fizica": {"tip_schema": "prosumator", "retea": "tri", "P_aprobata_kW": 40, "P_evacuata_kW": 30,
                         "limitare_injectie_kW": 30, "racord": "bmpt", "In_Q_bransament_A": 63,
                         "invertoare": [{"n": 3, "Pn_kW": 12, "producator": "Huawei", "model": "SUN2000-12KTL-M5"}],
                         "Pn_inv_kW": 36},
      "intrebari": [], "neinteles": []}),
    ("Nr;Consumator;Buc;P [kW]\n1;Compresor aer;2;22\n2;Iluminat hala;1;4,5\n3;Prize 16A;6;\nTG alimentat din PT propriu "
     "630 kVA, TN-S",
     {"intrare_fizica": {"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 630, "schema_pamant": "TN-S",
                         "plecari": [{"nume": "Compresor aer 1", "P_kW": 22, "receptor": "motor"},
                                     {"nume": "Compresor aer 2", "P_kW": 22, "receptor": "motor"},
                                     {"nume": "Iluminat hala", "P_kW": 4.5, "receptor": "iluminat"},
                                     {"nume": "Prize", "In_A": 16, "n_circuite": 6, "receptor": "prize"}]},
      "intrebari": [], "neinteles": []}),
    ("Hi, we need the single-line for a house: 3-phase supply, approved power 15 kW, TN-C-S. Heat pump 9 kW (3-phase), "
     "induction hob, EV charger 11 kW. Thanks, Mark",
     {"intrare_fizica": {"tip_schema": "locuinta", "retea": "tri", "schema_pamant": "TN-C-S",
                         "alimentare": {"P_aprobata_kW": 15},
                         "circuite": [{"nume": "Pompă de căldură", "receptor": "pompa_caldura", "P_kW": 9, "faza": "3F"},
                                      {"nume": "Plită inducție", "receptor": "plita"},
                                      {"nume": "Încărcare VE", "receptor": "vehicul_electric", "P_kW": 11}]},
      "intrebari": [], "neinteles": []}),
    ("tablou pompe incendiu: pompa principala 45 kW, pompa rezerva 45 kW, pompa pilot 2,2 kW, alimentare din retea "
     "si GE 150 kVA",
     {"intrare_fizica": {"tip_schema": "ge_ats", "Sn_GE_kVA": 150, "siguranta_tablou": True,
                         "titlu_tablou": "Tablou pompe incendiu",
                         "consumatori": [{"nume": "Pompă incendiu", "P_kW": 45, "n": "1+1", "siguranta": True},
                                         {"nume": "Pompă pilot", "P_kW": 2.2, "siguranta": True}]},
      "intrebari": [], "neinteles": []}),
    ("CEF 100 kW, 2 invertoare SUN2000-100KTL, cablu CYABY 5x16 pana la TG existent, beneficiar SC Agro SRL",
     {"intrare_fizica": {"tip_schema": "cef", "racord": "tg_existent",
                         "invertoare": [{"n": 2, "Pn_kW": 100, "producator": "Huawei", "model": "SUN2000-100KTL"}],
                         "cablu_C0": {"S_fortat": 16, "n_fortat": 1, "material": "Cu"}},
      "cartus": {"beneficiar": "SC Agro SRL"},
      "intrebari": ["Puterea centralei: 100 kW total (un invertor SUN2000-100KTL) sau 2 × 100 kW = 200 kW, cum scrie "
                    "la invertoare?"],
      "neinteles": []}),
    ("casa monofazata 7 kW TN-C-S; din tabloul casei pleaca TD garaj cu CYY-F 3x4 pe 25 m: prize 2 circuite, iluminat",
     {"intrare_fizica": {"tip_schema": "locuinta", "retea": "mono", "schema_pamant": "TN-C-S",
                         "alimentare": {"P_aprobata_kW": 7},
                         "tablouri_secundare": [{"nume": "TD garaj", "L_m": 25, "cablu": {"S_fortat": 4, "material": "Cu"},
                                                 "circuite": [{"nume": "Prize", "n_circuite": 2, "receptor": "prize"},
                                                              {"nume": "Iluminat", "receptor": "iluminat"}]}]},
      "intrebari": [], "neinteles": []}),
    ("casa P+1 cu pompa de caldura si plita, bransament 16 kw, fara alte date",
     {"intrare_fizica": {"tip_schema": "locuinta", "alimentare": {"P_aprobata_kW": 16},
                         "circuite": [{"nume": "Pompă de căldură", "receptor": "pompa_caldura"},
                                      {"nume": "Plită", "receptor": "plita"}]},
      "intrebari": ["Branșamentul este monofazat (230 V) sau trifazat (3 × 400 V)?"], "neinteles": []}),
]


def system_llm() -> str:
    """Promptul de sistem: reguli de domeniu + cheile pe tip (generate din schemă) + exemple."""
    from . import interp_schema as _isch
    ex = "\n\n".join(f"Text: {t}\nApel intrare_fizica: {json.dumps(o, ensure_ascii=False)}" for t, o in EXEMPLE_LLM)
    return (_REGULI_LLM + "\nCheile de nivel 1 folosite de motor, pe tip de schemă (detaliile în schema uneltei):\n"
            + _isch.rezumat_chei() + "\n\nExemple:\n\n" + ex)


try:
    from . import interp_schema as _isch_mod
except ImportError:  # rulare ca script
    from engine import interp_schema as _isch_mod  # type: ignore
SYSTEM_LLM = system_llm() if __package__ else ""


def cerere_llm(text: str) -> dict:
    """Corpul cererii /v1/messages (același pe server și în browser). Antetul beta: BETA_LLM."""
    return {"model": MODEL_LLM, "max_tokens": 8000, "fallbacks": "default", "output_config": {"effort": "medium"},
            "system": SYSTEM_LLM or system_llm(), "tools": [_isch_mod.unealta()], "tool_choice": {"type": "auto"},
            "messages": [{"role": "user", "content": text}]}


def antete_llm(cheie: str) -> dict:
    h = {"content-type": "application/json", "anthropic-version": VERSIUNE_API, "anthropic-beta": BETA_LLM}
    if cheie.startswith("Bearer "):
        h["authorization"] = cheie
    else:
        h["x-api-key"] = cheie
    return h


def raspuns_din_api(r: dict) -> dict | None:
    """Din răspunsul /v1/messages: inputul uneltei `intrare_fizica` (sau un JSON scris ca text). None la refuz."""
    if not isinstance(r, dict):
        return None
    if r.get("type") == "error":
        raise RuntimeError((r.get("error") or {}).get("message") or "eroare API")
    if r.get("stop_reason") == "refusal":
        return None
    for b in r.get("content") or []:
        if b.get("type") == "tool_use" and b.get("name") == "intrare_fizica" and isinstance(b.get("input"), dict):
            return b["input"]
    txt = "".join(b.get("text", "") for b in r.get("content") or [] if b.get("type") == "text")
    j = re.search(r"\{.*\}", txt, re.S)
    return json.loads(j.group(0)) if j else None


def cheie_llm() -> str | None:
    """Cheia: setată în aplicație (memoria procesului / ~/.config) sau ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN."""
    try:
        from . import cheie_api
    except ImportError:
        from engine import cheie_api  # type: ignore
    return cheie_api.citeste()


def _are_credentiale() -> bool:
    return bool(cheie_llm())


def intrare_llm(text: str, cheie: str | None = None) -> dict | None:
    """Apelează Claude (HTTP direct, fără SDK) și întoarce inputul uneltei. None dacă nu există cheie."""
    cheie = cheie or cheie_llm()
    if not cheie:
        return None
    import urllib.request
    req = urllib.request.Request(URL_API, data=json.dumps(cerere_llm(text)).encode("utf-8"), method="POST",
                                 headers=antete_llm(cheie))
    try:
        with urllib.request.urlopen(req, timeout=180) as f:
            r = json.loads(f.read().decode("utf-8"))
    except urllib.error.HTTPError as e:            # 401 cheie greșită, 429, 529 …
        try:
            r = json.loads(e.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            raise RuntimeError(f"HTTP {e.code}") from None
    return raspuns_din_api(r)


# ------------------------------------------------------------------------------------------- fuziunea
ETICHETE_CRITICE = {"tip_schema": "tipul schemei", "retea": "rețeaua", "schema_pamant": "schema de legare la pământ",
                    "P_aprobata": "puterea aprobată", "Q_bransament": "calibrul Q al branșamentului",
                    "invertoare": "invertoarele (număr × Pn)", "n_trafo": "numărul de transformatoare",
                    "origine": "sursa tabloului", "siguranta": "consumatorii de siguranță la incendiu"}


def _chei_critice(intr: dict) -> dict:
    al = intr.get("alimentare") or {}
    tip = intr.get("tip_schema")
    pa = intr.get("P_aprobata_kW", al.get("P_aprobata_kW"))
    if pa is None and tip == "bransament":
        pa = intr.get("P_kW")
    inv = None
    if intr.get("invertoare"):
        inv = tuple(sorted((int(g.get("n") or 1), float(g["Pn_kW"])) for g in intr["invertoare"] if g.get("Pn_kW")))
    elif intr.get("Pn_inv_kW"):
        inv = ((1, float(intr["Pn_inv_kW"])),)
    sig = None
    cons = intr.get("consumatori") or []
    if intr.get("siguranta_tablou") or any(c.get("siguranta") for c in cons):
        sig = "tot tabloul" if intr.get("siguranta_tablou") else sum(1 for c in cons if c.get("siguranta"))
    elif cons:
        sig = 0
    return {"tip_schema": tip, "retea": intr.get("retea"), "schema_pamant": intr.get("schema_pamant"),
            "P_aprobata": pa, "Q_bransament": intr.get("In_Q_bransament_A", al.get("In_Q_bransament_A")),
            "invertoare": inv or None, "n_trafo": intr.get("n_trafo"), "origine": intr.get("origine"), "siguranta": sig}


def _fmt_critic(k, v) -> str:
    if v is None:
        return "nespecificat"
    if k == "invertoare":
        return " + ".join(f"{n} × {fmt(p)} kW" for n, p in v)
    if k == "retea":
        return {"mono": "monofazat", "tri": "trifazat"}.get(v, v)
    if k == "tip_schema":
        return NUME_TIP.get(v, v)
    if k == "siguranta":
        return v if isinstance(v, str) else ("niciunul" if v == 0 else f"{v} consumator(i)")
    if isinstance(v, (int, float)):
        return fmt(v) + {"P_aprobata": " kW", "Q_bransament": " A"}.get(k, "")
    return str(v)


def diferente_critice(intr_claude: dict, intr_local: dict) -> list[tuple]:
    """(cheie, valoare Claude, valoare reguli) pe cheile critice. Regula locală care doar lipsește (None) nu contează."""
    a, b = _chei_critice(intr_claude), _chei_critice(intr_local or {})
    out = []
    for k in ETICHETE_CRITICE:
        va, vb = a[k], b[k]
        if vb is None:
            continue
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)) and abs(va - vb) <= 1e-6 * max(1, abs(vb)):
            continue
        if va != vb:
            if k == "n_trafo" and {va, vb} <= {None, 1}:
                continue
            # rețeaua lipsă la Claude: la locuință / branșament / prosumator F.7 întreabă oricum (I02); la celelalte
            # motorul lucrează trifazat, iar „tri” al regulilor e doar implicitul lor — contează numai „mono”
            if k == "retea" and va is None and vb == "tri":
                continue
            out.append((k, va, vb))
    return out


def _extras_din_intrare(intr: dict, local: dict, cart: dict) -> dict:
    """Vederea structurală (`extras`) pentru textul „Am înțeles” și verificările F.7, construită din intrarea Claude."""
    ex = {"tip_schema": intr.get("tip_schema"), "retea": intr.get("retea"), "puteri": {}, "plecari": [],
          "nr_plecari": None, "lungimi_m": {}, "grupare": None, "cosfi": intr.get("cosfi")}
    cb = intr.get("cablu") or (intr.get("alimentare") or {}).get("cablu") or {}
    for k in ("material", "izolatie", "metoda"):
        ex[k] = cb.get(k) or (intr.get(k) if k == "material" else None)
    p = ex["puteri"]
    for k in ("P_kW", "Ib_A", "S_kVA", "In_Q1_A", "Sn_kVA", "kWp", "Sn_GE_kVA", "baterie_kWh", "P_aprobata_kW",
              "P_evacuata_kW", "limitare_injectie_kW", "Q_In_A"):
        if intr.get(k) is not None:
            p[k] = intr[k]
    if intr.get("invertoare"):
        p["invertoare"] = [{k: g[k] for k in ("n", "Pn_kW", "producator", "model") if g.get(k) is not None}
                           for g in intr["invertoare"] if g.get("Pn_kW")]
    elif intr.get("Pn_inv_kW"):
        inv = intr.get("invertor") or {}
        p["invertoare"] = [dict({"n": 1, "Pn_kW": intr["Pn_inv_kW"]},
                                **{k: inv[k] for k in ("producator", "model") if inv.get(k)})]
    if isinstance(intr.get("bess"), dict):
        p["bess"] = dict(intr["bess"])

    cf = bool(intr.get("circuite_finale"))
    ex["_circuite_finale"] = cf

    def pl(x, nivel=0):
        v, u = (x["In_A"], "A") if "In_A" in x else (x["P_kW"], "kW") if "P_kW" in x else (None, None)
        rec = x.get("receptor") or receptor_dupa_nume(x["nume"], nivel, cf)
        if x.get("pornire") and rec != "motor":
            rec = "motor"
        o = {"nume": x["nume"], "valoare": v, "unitate": u, "receptor": rec}
        for k in ("n_circuite", "L_m", "pornire"):
            if x.get(k) is not None:
                o[k] = x[k]
        if x.get("copii"):
            o["copii"] = [pl(c, nivel + 1) for c in x["copii"]]
        return o
    ex["plecari"] = [pl(x) for x in intr.get("plecari") or []]
    for k, n in (("L_coloana_m", "C2"), ("L_alimentare_m", "alimentare")):
        if intr.get(k) is not None:
            ex["lungimi_m"][n] = intr[k]
    if intr.get("schema_pamant"):
        ex["schema_pamant"] = intr["schema_pamant"]
    le = local.get("extras") or {}
    if intr.get("tip_schema") == "locuinta":
        ex["locuinta"] = le.get("locuinta") or "casa_parter"
    lc = local.get("cartus") or {}
    adr = dict(lc.get("adresa") or {}) if isinstance(lc.get("adresa"), dict) else {}
    if cart.get("localitate"):
        adr = {"localitate": cart["localitate"], **({"judet": cart["judet"]} if cart.get("judet") else {})}
    ex.update({"beneficiar": cart.get("beneficiar") or lc.get("beneficiar"), "adresa": adr or lc.get("adresa"),
               "plansa": cart.get("plansa") or lc.get("plansa"), "faza": cart.get("faza") or lc.get("faza")})
    if intr.get("tip_schema") in ("bransament", "prosumator") and intr.get("retea") is None:
        ex["_retea_lipsa"] = True
    return ex


def _completeaza_locuinta(intr: dict, ex: dict, note: list):
    """Aceeași convenție ca regulile locale: setul de bază (sau tipic, la < 3 receptori) + receptorii citiți."""
    listati = intr.get("circuite") or []
    tipl = ex.get("locuinta") or "casa_parter"
    citite = {x["receptor"] for x in listati}             # un receptor citit (ex. „Iluminat parter”) nu se mai dublează
    if len(listati) < 3:
        baza = [_circuit_loc(n, r) for n, r in SET_TIPIC[tipl] if r not in citite]
        intr["circuite"] = _combina_circuite(baza, listati)
        note.append(f"set tipic pentru {DESCR_LOCUINTA[tipl]} + receptorii citiți = {len(intr['circuite'])} circuite "
                    "— PRESUPUNERE, corectați lista dacă diferă")
    else:
        intr["circuite"] = _combina_circuite([_circuit_loc(n, r) for n, r in SET_BAZA if r not in citite], listati)
        adaug = [x["nume"] for x in intr["circuite"] if x not in listati]
        if adaug:
            note.append(f"circuitele de bază ale oricărei locuințe ({', '.join(adaug)}) adăugate la cele citite — "
                        "PRESUPUNERE, corectați lista dacă diferă")
    if intr.get("retea") == "tri":
        for x in intr["circuite"]:
            if x["receptor"] in TRI_POSIBIL_LOC and "faza" not in x and "P_kW" not in x:
                x["faza"] = "3F"


def _adauga_intrebari(r: dict, intrebari: list[str], neinteles: list[str] = ()) -> dict:
    """Întrebările lui Claude adăugate peste un rezultat deja finalizat (calea de rezervă)."""
    if neinteles:
        r["neconsumat"] = _unice(list(r.get("neconsumat") or []) + list(neinteles))
    if r["actiune"] != "refuza":
        for q in intrebari:
            if q not in r["intrebari"]:
                r["intrebari"].append(q)
        if r["actiune"] == "genereaza" and r["intrebari"]:
            r["actiune"] = "genereaza_cu_intrebare"
    r["intelegere"] = text_raspuns(r)
    return r


def _sir_lista(x) -> list[str]:
    return [str(q).strip() for q in (x or []) if isinstance(q, (str, int, float)) and str(q).strip()]


def fuzioneaza(text: str, local: dict, brut) -> dict:
    """F.9: rezultatul lui Claude e baza; regulile locale verifică. Diferențele pe chei critice → întrebare cu ambele
    variante (nu alegere tăcută); întrebările și „neînțelesul” lui Claude + verificările F.7 se păstrează."""
    if not isinstance(brut, dict):
        return local
    rasp = brut if isinstance(brut.get("intrare_fizica"), dict) else {"intrare_fizica": brut}
    q_claude = _sir_lista(rasp.get("intrebari"))
    neint = _sir_lista(rasp.get("neinteles"))
    cart = rasp.get("cartus") if isinstance(rasp.get("cartus"), dict) else {}
    cart = {k: str(v).strip() for k, v in cart.items() if isinstance(v, (str, int, float)) and str(v).strip()}
    brut_i = rasp["intrare_fizica"]
    ignorate = [e for e in _isch_mod.valideaza(brut_i) if "cheie necunoscută" in e or "nu e în" in e or "tip " in e]
    intr = normalizeaza_intrare(brut_i)
    note: list[str] = []
    for g in intr.get("invertoare") or []:          # Pn lipsă → din catalogul motorului (codul poate fi Smax, ex. 330KTL)
        if g.get("Pn_kW") is None and _cat_inv is not None:
            mc = _cat_inv.cauta(g.get("producator"), g.get("model"))
            if mc:
                g["Pn_kW"] = mc["Pn_kW"]
                g.setdefault("producator", mc["producator"])
                note.append(f"Pn = {fmt(mc['Pn_kW'])} kW din catalog pentru {mc['producator']} {mc['model']} — confirmați cu fișa")
    if intr.get("tip_schema") == "locuinta":     # setul de bază / tipic — și când Claude n-a listat niciun circuit
        _completeaza_locuinta(intr, {"locuinta": (local.get("extras") or {}).get("locuinta")}, note)
    erori = valideaza_forma(intr)
    if erori:
        r = copy.deepcopy(local)
        r["presupus"].append("(citirea Claude a fost respinsă la validarea formei: " + "; ".join(erori)
                             + " — s-au folosit regulile locale)")
        r["motor"] = "reguli"
        r["citire_claude"] = {"respinsa": erori, "intrare_fizica": brut_i}
        return _adauga_intrebari(r, q_claude, neint)
    ex = _extras_din_intrare(intr, local, cart)
    tip = intr["tip_schema"]
    if tip in ("locuinta", "bransament") and intr.get("schema_pamant") == "TN-S":
        intr["schema_pamant"] = ex["schema_pamant"] = "TN-C-S"
        note.append("„TN-S” la o instalație din rețeaua publică = TN-C-S pe branșament (TN-S în aval de separarea PEN)")
    if ex.get("_retea_lipsa"):          # ca la regulile locale: doar dacă puterea nu încape fizic în monofazat
        P = intr.get("P_kW") or intr.get("Pn_inv_kW") or ((intr.get("S_kVA") or 0) * 0.9) or None
        ib = (P * 1000 / (U_MONO * 0.9)) if P else (intr.get("Ib_A") or None)
        if ib and ib > norme.BMPM["I_max_A"]:
            intr["retea"] = ex["retea"] = "tri"
            ex.pop("_retea_lipsa")
            note.append(f"rețea nedeclarată, dar {fmt(P) + ' kW' if P else fmt(ib) + ' A'} nu încape în monofazat "
                        f"(BMPM max. {fmt(norme.BMPM['I_max_A'], 0)} A) → trifazat 3 × 400 V")
    probleme = []
    if local.get("actiune") == "refuza" and local.get("refuz_cod") == "I12":     # în afara domeniului: rămâne refuz
        probleme.append(("I12", local["refuz_motiv"], (local.get("intrebari") or [None])[0]))
    intrebari = [("I16", q) for q in q_claude]
    dif = diferente_critice(intr, local.get("intrare_fizica") or {})
    for k, va, vb in dif:
        intrebari.append(("I17", f"Citirea textului diferă la {ETICHETE_CRITICE[k]}: citirea avansată (Claude) → "
                                 f"{_fmt_critic(k, va)}; regulile locale → {_fmt_critic(k, vb)}. Care e corect? "
                                 "(schema e generată cu prima variantă)"))
    if neint:
        intrebari.append(("I15", "Nu am folosit în schemă: " + "; ".join(f"„{x}”" for x in neint)
                                 + ". Ce reprezintă și unde se aplică? (până atunci nu apar pe planșă)"))
    r = _finalizeaza(intr, ex, note, probleme, motor="llm", intrebari=intrebari, neconsumat=neint)
    r["verificare_incrucisata"] = {"diferente": [{"cheie": k, "claude": va, "reguli": vb} for k, va, vb in dif],
                                   "actiune_reguli": local.get("actiune"), "tip_reguli": local.get("tip_schema")}
    if ignorate:
        r["verificare_incrucisata"]["ignorate"] = ignorate
    return r


# r10 (clasa 8): nimic blocat fără întrebare — interpretorul rulează motorul pe intrarea citită; un BLOCANT fără întrebare
# devine întrebarea concretă de remediere (opțiunile din verificare), nu o planșă blocată tăcut
def _prop(x):
    """r11: propunerea / remedierea motorului (verificarea însăși știe ce se poate face), fără punctuația finală"""
    p = x.get("remediere")
    pr = x.get("propunere")
    if isinstance(pr, dict) and pr.get("camp") is not None:
        pr = f"{pr['camp'].split('.')[-1]} = {fmt(pr['valoare']) if isinstance(pr.get('valoare'), (int, float)) else pr.get('valoare')}"
    elif not isinstance(pr, str):
        pr = None
    t = "; ".join(str(y).rstrip(".? ") for y in (p, pr) if y)
    return t


def _retea_mono(r):
    i = r.get("intrare_fizica") or {}
    return i.get("retea") == "mono" or (i.get("alimentare") or {}).get("retea") == "mono"


_Q_BLOCANT = {
    # r11: „mutarea pe altă fază” doar la trifazat; propunerea vine din verificarea motorului când există
    "V46": lambda x, r: (f"{x['obiect']}: {x['mesaj']}. Cum procedăm: " + (_prop(x) + " — sau " if _prop(x) else "") +
                         "cereți mărirea puterii (ATR nou), limitați puterea receptorului (plita de inducție are limitator "
                         "de putere; la VE — DLM / curent limitat), sau confirmați altă putere aprobată?"
                         if "Plit" in x["obiect"] or "receptor" in x["mesaj"] else
                         f"{x['mesaj']}. Cum procedăm: " + (_prop(x) + " — sau " if _prop(x) else "") +
                         "mărirea puterii (ATR nou, Q mai mare), DLM / limitarea curentului de încărcare"
                         + ("?" if _retea_mono(r) else ", sau mutarea circuitelor monofazate pe altă fază?")),
    "V04": lambda x, r: (f"{x['obiect']}: {x['mesaj']} (BLOCANT). Cum procedăm: mărirea puterii (ATR nou, Q mai mare), "
                         "limitarea sarcinii (DLM / coeficient de simultaneitate declarat), sau puterea cerută e alta?"),
    "V28": lambda x, r: (f"{x['mesaj'].split(' — ')[0]}. Desenez schema {x.get('remediere') or 'TN-C-S'} (separarea PEN în "
                         "BMPT / tabloul general, priză de pământ nouă), sau schema e alta?"),
    "V53": lambda x, r: (f"{x['mesaj']}. Cum procedăm: " + (_prop(x) + "?" if _prop(x) else (
        "branșament + invertor trifazat, sau invertor monofazat mai mic (Iac ≤ 40 A)?"
        if (r.get("intrare_fizica") or {}).get("tip_schema") in ("prosumator", "cef")
        else "branșament trifazat (BMPT), sau reducerea puterii la ≤ 40 A pe fază (BMPM)?"))),
    "V96": lambda x, r: f"{x['mesaj']}. Remediere: {x.get('remediere')}. Cum procedăm?",
}


def intrebari_din_motor(r: dict) -> dict:
    """Rulează motorul (constructor + validare) pe intrarea citită; fiecare BLOCANT care nu are deja o întrebare →
    întrebare cu remedierea din verificare. Rezultatul rămâne generabil („genereaza_cu_intrebare”)."""
    if r.get("actiune") == "refuza" or not r.get("intrare_fizica") or r.get("_motor_verificat"):
        return r
    try:
        from . import constructor, validare        # import leneș (validare → constructor → calc)
        m, _ = constructor.genereaza(r["intrare_fizica"])
        v = validare.valideaza(m)
    except Exception:  # noqa: BLE001 — verificarea motorului nu are voie să strice citirea
        return r
    r["_motor_verificat"] = True
    if not v.get("blocheaza"):
        return r
    deja = " ".join(r.get("intrebari") or []).lower()
    noi, vazute = [], set()
    for x in v.get("verificari") or []:
        if x.get("nivel") != "BLOCANT" or x.get("cod") in vazute:
            continue
        vazute.add(x["cod"])
        if x["cod"] == "V07" and r.get("intrebari"):
            continue                                      # rețeaua / plecările lipsă — întrebate deja
        f = _Q_BLOCANT.get(x["cod"])
        q = (f(x, r) + (f" (Remediere: {x['remediere'].rstrip('.? ')}.)" if x.get("remediere") and x["cod"] in ("V04",) else "")) \
            if f else (f"Verificarea {x['cod']} blochează planșa — {x.get('obiect')}: {x.get('mesaj')}. Remediere: "
                            f"{x.get('remediere') or '—'}. Aplic remedierea (o desenez așa), sau datele sunt altele?")
        if q.lower()[:60] in deja:
            continue
        noi.append(q)
        if len(noi) >= 3:
            break
    if noi:
        r["intrebari"] = list(r.get("intrebari") or []) + noi
        r["intrebari_motor"] = noi
        if r["actiune"] == "genereaza":
            r["actiune"] = "genereaza_cu_intrebare"
        r["intelegere"] = text_raspuns(r)
    return r


def interpreteaza(text: str, foloseste_llm: bool = False, cheie: str | None = None, raspuns_llm=None,
                  verifica_motor: bool = True) -> dict:
    r = _interpreteaza(text, foloseste_llm, cheie, raspuns_llm)
    if verifica_motor:
        r = intrebari_din_motor(r)
        r.pop("_motor_verificat", None)
    return r


def _interpreteaza(text: str, foloseste_llm: bool = False, cheie: str | None = None, raspuns_llm=None) -> dict:
    """Funcția publică (F.1, F.9).
    * Fără LLM (sau fără cheie): doar regulile locale — exact comportamentul F.1–F.8.
    * Cu LLM: Claude citește textul (unealta `intrare_fizica`), regulile locale rulează în paralel ca verificare
      încrucișată (`fuzioneaza`). La eroarea apelului rămâne rezultatul local, cu mențiune.
    * `raspuns_llm`: răspunsul deja obținut (versiunea web: apelul îl face browserul) — corpul /v1/messages sau
      direct inputul uneltei."""
    local = interpreteaza_local(text)
    if raspuns_llm is not None:
        try:
            brut = raspuns_din_api(raspuns_llm) if isinstance(raspuns_llm, dict) and "content" in raspuns_llm \
                else raspuns_llm
        except Exception as e:  # noqa: BLE001
            return _llm_indisponibil(local, e)
        return fuzioneaza(text, local, brut) if brut is not None else local
    if not foloseste_llm:
        return local
    try:
        brut = intrare_llm(text, cheie) if cheie else intrare_llm(text)
    except Exception as e:  # rețea, cheie invalidă, JSON stricat
        return _llm_indisponibil(local, e)
    if brut is None:
        return local
    return fuzioneaza(text, local, brut)


def _llm_indisponibil(local: dict, e) -> dict:
    local["presupus"].append(f"(LLM indisponibil: {e.__class__.__name__}; s-a folosit interpretorul local)")
    local["intelegere"] = text_raspuns(local)
    return local
