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

try:  # norme.py e sursa unică pentru seriile standard (trafo, BMPT, ks, factori)
    from .calc import norme
except ImportError:  # rulare ca script izolat
    from engine.calc import norme  # type: ignore

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
}
UNIT_AFIS = {"kwp": "kWp", "mwp": "MWp", "wp": "Wp", "kwh": "kWh", "mwh": "MWh", "kva": "kVA", "mva": "MVA",
             "kw": "kW", "mw": "MW", "w": "W", "ka": "kA", "a": "A", "km": "km", "metri": "m", "ml": "m", "m": "m"}
RE_VAL = re.compile(rf"(?<![\w.,])(?P<num>{NUM}|\d{{1,3}}(?: \d{{3}})+)\s*"
                    r"(?P<u>kwp|mwp|wp|kwh|mwh|kva|mva|kw|mw|w|ka|a|km|metri|ml|m)\b")
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
class Ctx:
    def __init__(self, text: str):
        self.orig = text or ""
        self.t = normalizeaza(self.orig)
        self.note: list[str] = []          # presupuneri care vin din citirea textului (F.2–F.5)
        self.probleme: list[tuple] = []    # (cod, motiv, întrebare) găsite la parsare
        self.lista = None                  # rezultatul parsării listei de plecări
        self.consumat: list[tuple] = []    # intervale din t deja interpretate (lista, invertoare, BESS)

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
# F.5 Tipul schemei (ordinea de decizie: BMPM > BMPT/branșament > prosumator > GE > CEF > PT > tablou)
# =====================================================================================================
RE_PT_PROPRIU = re.compile(r"\bdin\s+(?:pt|postul)\s+propriu\b")


def detecteaza_tip(c: Ctx) -> str | None:
    t = c.t
    # „din PT propriu” descrie sursa unui tablou, nu schema PT → se maschează înainte de detecție
    orig_fara_sursa, orig_pt = list(t), list(c.orig if len(c.orig) == len(t) else t)
    for m in RE_PT_PROPRIU.finditer(t):
        orig_fara_sursa[m.start():m.end()] = orig_pt[m.start():m.end()] = " " * (m.end() - m.start())
    orig_fara_sursa, orig_pt = "".join(orig_fara_sursa), "".join(orig_pt)
    if _e_locuinta(c):
        return "locuinta"
    if re.search(r"\bbmpm", t) or re.search(r"\bbmpt|bransament|\bfirida", t):
        return "bransament"
    if "prosumator" in t:
        return "prosumator"
    if re.search(r"\bgrup(?:ul)?\s+electrogen|\bgenerator\b|\bats\b|\baar\b", t) or re.search(r"\bGE\b", c.orig):
        return "ge_ats"
    if re.search(r"\bcef\b|fotovoltaic|\d\s*[km]wp\b|invertor|\bbess\b|stocare|panouri", t):
        return "cef"
    if (re.search(r"\bPT\b", orig_pt) or re.search(r"\bpost(?:ul)?\s+(?:de\s+)?(?:transformare|trafo)|transformator"
                                                   r"|20/0,4\s*kv|\d\s*[km]va\b", orig_fara_sursa)):
        return "pt"
    if re.search(r"tablou|\btg\b|\btd\b|plecari|circuite", t):
        return "tablou"
    return None


RE_TRI_DECLARAT = re.compile(r"trifaz\w*|\btri\b|\b400\s*v\b|\bbmpt|\b3f\b|\b3\s*[×x]\s*\d|\b3\s*\+\s*n\b")


def retea_declarata(c: Ctx):
    """rețeaua spusă explicit în text ("mono" / "tri") sau None — la branșament, prosumator și locuință nu se presupune"""
    if re.search(r"\bbmpm|monofazat|\bmono\b|\b1f\b|\b230\s*v\b", c.t):
        return "mono"
    return "tri" if RE_TRI_DECLARAT.search(c.t) else None


def detecteaza_retea(c: Ctx) -> str:
    """F.5: mono/tri; implicit tri (tablou / PT / CEF / GE — JT industrial)."""
    if re.search(r"\bbmpm|monofazat|\bmono\b|\b1f\b|\b230\s*v\b", c.t):
        return "mono"
    return "tri"


# =====================================================================================================
# F.4 Lista de plecări
# =====================================================================================================
RECEPTORI = r"iluminat|prize|priza|forta|motor|motoare|pompa|pompe|compresor|ventilatie"
RE_TRIGGER = re.compile(r"(?:\b(?P<n>\d+)\s+)?(?<!sub-)(?<!sub)\b(?P<w>plecari|plecare|circuite)\b")
RE_SEP = re.compile(r"\s*(?:[;:+()]|(?<!\d),|,(?!\d)|\bsi\b)(?:\s*[;,()])*\s*")   # „(” / „)” = cascadă (F.4 r. 3)
_ITEM = (rf"(?:(?P<nume>[^\d\s,;][^,;]*?)\s+)?(?:(?P<mult>\d+)\s*×\s*)?(?P<val>{NUM})\s*(?P<unit>a|kw)?(?![\w²%/])"
         rf"(?:\s*(?P<L>{NUM})\s*(?P<Lu>km|metri|ml|m)\b)?(?:\s+(?P<rec>{RECEPTORI}))?")
RE_ITEM = re.compile(rf"^{_ITEM}$")
RE_ITEM_PREFIX = re.compile(rf"^{_ITEM}(?=\s+[a-z])")
RE_DOAR_TRIGGER = re.compile(r"^(?:(?P<n>\d+)\s+)?(?:plecari|plecare|circuite)(?:\s+de)?$")
RE_TRIGGER_REST = re.compile(r"^(?:(?P<n>\d+)\s+)?(?P<w>plecari|plecare|circuite)\s+(?:de\s+)?(?P<rest>.+)$")
RE_CASCADA = re.compile(r"^(?P<nume>.+?)\s+cu\s+(?:sub-?\s*plecari(?:le)?|circuitele)\s*:?\s*(?P<rest>.+)$")
RE_COD_TD = re.compile(r"^td-?\s*\d+\b")


def receptor_dupa_nume(nume: str, nivel: int, circuite_finale=False) -> str:
    """C.2: receptorul după nume (fără diacritice, litere mici)."""
    n = _fara_diacritice(nume or "")
    if "ilumin" in n:
        return "iluminat"
    if "priz" in n:
        return "prize"
    if re.search(r"motor|pomp|compresor|ventila|moar|concasor|malaxor", n):
        return "motor"
    return "forta" if (nivel >= 1 or circuite_finale) else "tablou"


def nume_normalizat(s: str) -> str:
    """F.4 regula 4: numele se păstrează; dacă e scris integral cu litere mici, prima literă devine majusculă.
    Codurile (TD-1, HVAC) rămân neschimbate. NU .capitalize() pe tot șirul (P1-14)."""
    s = re.sub(r"\s+", " ", s.strip(" ,;:"))
    if s and s == s.lower():
        return s[0].upper() + s[1:]
    return s


def _bucati(c: Ctx, start: int):
    """Taie textul de la începutul listei în bucăți după separatorii F.4 (păstrând pozițiile)."""
    t = c.t
    poz, out, sep = start, [], ""
    for m in RE_SEP.finditer(t, start):
        if m.start() > poz:
            out.append((poz, m.start(), sep))
        sep = m.group(0).strip() or ","
        poz = m.end()
    if poz < len(t):
        out.append((poz, len(t.rstrip(" .")), sep))
    return [(s, e, sp) for s, e, sp in out if t[s:e].strip()]


def _item(c: Ctx, s: int, text: str, prefix_ok=False):
    """Un item „[nume] [N×] valoare [unitate] [lungime] [receptor]” (F.4). Întoarce (dict, capăt) sau None."""
    m = RE_ITEM.match(text)
    if not m and prefix_ok:
        m = RE_ITEM_PREFIX.match(text)
        if m and not m.group("unit"):
            m = None
    if not m:
        return None
    nume = None
    if m.group("nume"):
        nume = nume_normalizat(c.o(s + m.start("nume"), s + m.end("nume")))
        if re.fullmatch(r"(?:de|cu|si|la)", _fara_diacritice(nume)):
            nume = None
    it = {"nume": nume, "val": numar(m.group("val")), "unit": {"a": "A", "kw": "kW"}.get(m.group("unit")),
          "mult": int(m.group("mult")) if m.group("mult") else 1, "copii": None,
          "rec": m.group("rec"), "L": None, "s": s, "e": s + m.end(), "txt": c.o(s, s + m.end())}
    if m.group("L"):
        it["L"] = numar(m.group("L")) * UNITATI[m.group("Lu")][1]
    return it, s + m.end()


def _e_valoare_simpla(c: Ctx, b) -> bool:
    r = _item(c, b[0], c.t[b[0]:b[1]])
    return bool(r) and r[0]["nume"] is None and r[0]["mult"] == 1


def parseaza_lista(c: Ctx):
    """F.4: găsește lista de plecări și o transformă în itemi (cu cascadă și multiplicatori)."""
    m = RE_TRIGGER.search(c.t)
    if not m:
        return None
    bucati = _bucati(c, m.start())
    top, nr_cerut, parinte, capat = [], None, None, m.end()
    i = 0
    while i < len(bucati):
        s, e, sep = bucati[i]
        txt = c.t[s:e]
        if ";" in sep or ")" in sep:
            parinte = None                                        # „;” / „)” închid lista de copii (F.4 r. 3)
        urm_sep = bucati[i + 1][2] if i + 1 < len(bucati) else ""
        if "(" in urm_sep and not RE_ITEM.match(txt):             # „NUME (LISTA)” → NUME e tablou cu copii
            p = {"nume": nume_normalizat(c.o(s, e)), "val": None, "unit": None, "mult": 1, "copii": [],
                 "rec": None, "L": None, "s": s, "e": e, "txt": c.o(s, e)}
            top.append(p)
            parinte, capat = p, e
            i += 1
            continue
        md = RE_DOAR_TRIGGER.match(txt)
        if md:
            if md.group("n"):
                nr_cerut = int(md.group("n"))
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
        if mt:
            r = _item(c, s + mt.start("rest"), mt.group("rest"), prefix_ok=True)
            if not r:
                break
            it, capat = r
            n = int(mt.group("n")) if mt.group("n") else None
            urm = bucati[i + 1] if i + 1 < len(bucati) else None
            if n and it["nume"] is None and it["mult"] == 1 and not (urm and _e_valoare_simpla(c, urm)):
                it["mult"], it["forma_n_de"] = n, True                 # „4 plecări de 63 A” (F.4 r. 2)
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
            break                                                      # ex. „lungime 40 m”, „cablu cupru” → sfârșit
        it, capat = r
        if parinte and RE_COD_TD.match(txt):
            parinte = None                                             # cod de tablou = item de nivel superior
        (parinte["copii"] if parinte else top).append(it)
        i += 1
    c.consumat.append((m.start(), capat))
    return {"itemi": top, "nr_cerut": nr_cerut, "s": m.start(), "e": capat, "cuvant": m.group("w")}


def _unitate_comuna(c: Ctx, itemi: list) -> bool:
    """F.4 r. 1: un item fără unitate primește unitatea primului item următor care are unitate."""
    purtata, folosita = None, False
    for it in reversed(itemi):
        if it["copii"] is not None:
            _unitate_comuna(c, it["copii"])
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


def expandeaza(c: Ctx, itemi: list, nivel: int, tip: str, circuite_finale: bool) -> list[dict]:
    """Multiplicatori + nume generate (F.4 r. 2) → plecări finale {nume, valoare, unitate, receptor, L_m, copii}."""
    out = []
    for it in itemi:
        n = it["mult"]
        rec_txt = it["rec"]
        if n > 1:
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
        for k in range(1, n + 1):
            if it["nume"]:
                nume = it["nume"] if n == 1 else f"{it['nume']} {k}"
            elif rec_txt:
                nume = f"{nume_normalizat(rec_txt)} {k}"
            elif nivel == 0 and not circuite_finale:
                nume = f"TD-{len(out) + 1}"
            else:
                nume = f"Circuit {len(out) + 1}"
            rec = receptor_dupa_nume(rec_txt or nume, nivel, circuite_finale)
            p = {"nume": nume, "valoare": _nr(it["val"]), "unitate": it["unit"], "receptor": rec}
            if it["L"] is not None:
                p["L_m"] = _nr(it["L"])
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
    m = re.search(rf"(?:{NUM}\s*(?:m|km)|\bcablu)\s+(al|cu)\s*(?:[,;.]|$)", t)
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
    t = c.t
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
    P, I, S = _prima(vals, "kW"), _prima(vals, "A"), _prima(vals, "kVA")
    cos = intr.get("cosfi", COSFI)
    if P:
        puteri["P_kW"] = _nr(P["val"])
        intr["P_kW"] = _nr(P["val"])
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
    if ex["material"]:
        intr["material"] = ex["material"]
    if ex["izolatie"] or ex["metoda"]:
        intr["cablu"] = {k: v for k, v in (("material", ex["material"]), ("izolatie", ex["izolatie"]),
                                           ("metoda", ex["metoda"])) if v}
    # măsura și tipul de bloc (F.5 „semidirect”; C.1)
    if re.search(r"bmpti|semidirect|\bindirect|transformatoare\s+de\s+curent", c.t) or re.search(r"\bTC\b", c.orig):
        ex["masura_ceruta"] = intr["masura_ceruta"] = "semidirecta"
    m = re.search(r"\bbmpt([di])\s*-\s*(\d+)\b", c.t)
    if m:
        ex["bmpt_cerut"] = f"BMPT{m.group(1)}-{m.group(2)}"
    elif re.search(r"\bbmptd\b", c.t):
        ex["bmpt_cerut"] = "BMPTd"
    m = re.search(rf"\b3\s*×\s*({NUM})\s*a\b", c.t)
    if m and ex["retea"] == "mono":                     # I08: „monofazat 3×63 A”
        c.probleme.append(("I08", f"Contradicție: „monofazat” și „{c.o(m.start(), m.end())}” (I08).",
                           f"Branșament monofazat (max. 40 A) sau trifazat {m.group(1)} A?"))
    return puteri


def extrage_tablou(c: Ctx, vals, intr, ex, tip):
    """Tablou (C.2) și PT (C.5): puterea/calibrul tabloului în afara listei + plecările."""
    puteri = {}
    if tip == "pt":
        S = _prima(vals, "kVA")
        if S:
            puteri["Sn_kVA"] = _nr(S["val"])
            intr["Sn_kVA"] = _nr(S["val"])
        if re.search(r"celul\w*\s+(?:trafo\s+)?cu\s+sigurant", c.t):
            ex["celula_trafo"] = intr["celula_trafo"] = "sigurante"
        elif re.search(r"celul\w*\s+(?:trafo\s+)?cu\s+intrerupator", c.t):
            ex["celula_trafo"] = intr["celula_trafo"] = "intreruptor"
    else:
        P, I = _prima(vals, "kW"), _prima(vals, "A")
        if P:
            puteri["P_kW"] = _nr(P["val"])
            intr["P_kW"] = _nr(P["val"])
        if I:
            puteri["In_Q1_A"] = _nr(I["val"])
            intr["In_Q1_A"] = _nr(I["val"])
        if _prima(vals, "kWh"):
            c.probleme.append(("I04", "Unitatea „kWh” (energie) nu are sens la un tablou (I04).",
                               "Puterea tabloului este în kW (sau calibrul în A)?"))
        if RE_PT_PROPRIU.search(c.t):                                  # B.1.1: origine (+ pt_Sn_kVA)
            ex["sursa_alimentare"] = intr["origine"] = "pt_propriu"
            S = _prima(vals, "kVA")
            if S:
                intr["pt_Sn_kVA"] = _nr(S["val"])
    # plecările
    plecari, n_cerut = [], None
    if c.lista:
        _unitate_comuna(c, c.lista["itemi"])
        cf = c.lista["cuvant"] == "circuite" or bool(re.search(r"\bTD\b(?!-)", c.orig))
        ex["_circuite_finale"] = cf
        plecari = expandeaza(c, c.lista["itemi"], 0, tip, cf)
        n_cerut = c.lista["nr_cerut"]
    ex["plecari"] = plecari
    ex["nr_plecari"] = n_cerut if n_cerut is not None else (len(plecari) or None)
    if n_cerut is not None and plecari and n_cerut != len(plecari):
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
    if cablu and tip != "pt":
        intr["cablu"] = dict(cablu)
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
    return puteri


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
    cb = dict(cablu)
    if n_grup > 1:
        cb["n_alte"] = n_grup - 1
    if cb:
        d["cablu"] = cb
    return d


_INVERTOR = r"invert(?:or(?:ul|ii|i)?|oare(?:le)?)\b"
RE_INV = [  # F.5 invertoare
    re.compile(rf"\b(?P<n>\d+|un|o)\s+{_INVERTOR}(?:\s+hibrid\w*)?\s+(?:de\s+)?(?P<p>{NUM})\s*(?P<u>kw|mw)\b"),
    re.compile(rf"(?<![\w.,])(?P<n>\d+)\s*×\s*(?P<p>{NUM})\s*(?P<u>kw|mw)\b"),
    re.compile(rf"\binvertor(?:ul)?\b(?:\s+hibrid\w*)?\s+(?:de\s+)?(?P<p>{NUM})\s*(?P<u>kw|mw)\b"),
]
RE_INV_NUMAR = re.compile(rf"\b(?P<n>\d+|un|o)\s+{_INVERTOR}")
RE_BESS = [  # F.5 BESS
    re.compile(rf"(?:bess|stocare|baterie|baterii)\s*(?:de\s+)?(?P<p>{NUM})\s*(?P<pu>kw|mw)\s*/\s*(?P<e>{NUM})\s*(?P<eu>kwh|mwh)"),
    re.compile(rf"(?:bess|stocare|baterie|baterii)\s*(?:de\s+)?(?P<e>{NUM})\s*(?P<eu>kwh|mwh)(?:\s*/\s*(?P<p>{NUM})\s*(?P<pu>kw|mw))?"),
]


def _invertoare(c: Ctx) -> list[dict]:
    out = []
    for i, rx in enumerate(RE_INV):
        for m in rx.finditer(c.mascat()):
            n = m.groupdict().get("n")
            n = 1 if n in (None, "un", "o") else int(n)
            p = numar(m.group("p")) * UNITATI[m.group("u")][1]
            out.append((m.start(), {"n": n, "Pn_kW": _nr(p)}))
            c.consumat.append((m.start(), m.end()))
            if i == 2:
                c.nota(f"„{c.o(m.start(), m.end()).strip()}” = 1 invertor de {fmt(p)} kW")
    return [d for _, d in sorted(out, key=lambda x: x[0])]


def _bess(c: Ctx):
    for rx in RE_BESS:
        m = rx.search(c.mascat())
        if m:
            c.consumat.append((m.start(), m.end()))
            e = numar(m.group("e")) * UNITATI[m.group("eu")][1]
            p = numar(m.group("p")) * UNITATI[m.group("pu")][1] if m.group("p") else None
            return {"kWh": _nr(e), "P_kW": _nr(p)}
    return None


def extrage_cef(c: Ctx, vals, intr, ex):
    puteri = {}
    inv = _invertoare(c)
    bess = _bess(c)
    vals = valori(c.mascat())
    kwp = _prima(vals, "kWp")
    if kwp:
        puteri["kWp"] = intr["kWp"] = _nr(kwp["val"])
    P = _prima(vals, "kW")
    if P:
        puteri["P_ca_kW"] = _nr(P["val"])
    if not inv:
        m = RE_INV_NUMAR.search(c.t)
        n = (1 if m.group("n") in ("un", "o") else int(m.group("n"))) if m else 1
        if P:
            inv = [{"n": n, "Pn_kW": _nr(P["val"] / n)}]
            c.nota(f"{fmt(P['val'])} kW = putere c.a. totală → {n} × {fmt(P['val'] / n)} kW")
    if inv:
        puteri["invertoare"] = intr["invertoare"] = inv
    if bess:
        if bess["P_kW"] is None:
            bess["P_kW"] = _nr(bess["kWh"] / 2)
            c.nota(f"PCS BESS = {fmt(bess['P_kW'])} kW (0,5C din {fmt(bess['kWh'])} kWh) — presupus")
            ex["_pcs_presupus"] = bess["P_kW"]
        puteri["bess"] = intr["bess"] = {"P_kW": bess["P_kW"], "kWh": bess["kWh"]}
    S = _prima(vals, "kVA")
    if S:
        intr["pt_Sn_kVA"] = _nr(S["val"])
    if re.search(r"racord\s+jt\s+(?:conform|cf\.?)\s+atr", c.t):
        ex["atr_jt"] = intr["atr_jt"] = True
    # unde se leagă TGD-CF: un tablou existent al consumatorului
    if re.search(r"\b(tg|tablou(?:l)?(?:\s+general)?)\s+existent|în\s+tg\b|in\s+tg\b|racord\w*\s+(?:în|in)\s+(?:tg|tablou)", c.t):
        ex["racord"] = intr["racord"] = "tg_existent"
        c.nota("racord în tabloul general existent (TG) — protecția din TG și Ik3 la bara TG se completează în Calcul, altfel se iau ca la punctul de racord")
    L = _lungime_generala(vals)
    if L:
        intr["L_racord_m"] = _nr(L["val"])
        c.nota(f"cablul descris („{c.o(L['s_aprox'] or L['s'], L['e']).strip()}” = {fmt(L['val'])} m) = C0, de la TGD-CF la "
               + ("tabloul existent" if intr.get("racord") == "tg_existent" else "punctul de racord"))
    if re.search(r"acoperi[șs]", c.t):
        cab = dict(intr.get("cablu_inv") or {}, metoda="E")
        intr["cablu_inv"] = cab
        c.nota("invertoare pe acoperiș → cablurile c.a. pozate pe pat de cabluri / în aer (metoda E)")
    if not kwp and inv:
        c.nota("kWp nedeclarat (raport c.c./c.a. necalculat)")
    return puteri


def extrage_prosumator(c: Ctx, vals, intr, ex):
    puteri = {}
    if not ex.get("_retea_lipsa"):
        intr["retea"] = ex["retea"]
    inv = _invertoare(c)
    bat = None
    m = re.search(rf"(?:baterie|baterii|stocare|bess)\s*(?:de\s+)?(?P<e>{NUM})\s*(?P<eu>kwh|mwh)", c.mascat())
    if m:
        bat = numar(m.group("e")) * UNITATI[m.group("eu")][1]
        c.consumat.append((m.start(), m.end()))
    vals = valori(c.mascat())
    kwp = _prima(vals, "kWp")
    if kwp:
        puteri["kWp"] = intr["kWp"] = _nr(kwp["val"])
    if not inv and _prima(vals, "kW"):
        inv = [{"n": 1, "Pn_kW": _nr(_prima(vals, "kW")["val"])}]
    if inv:
        puteri["invertoare"] = inv
        intr["Pn_inv_kW"] = _nr(sum(i["n"] * i["Pn_kW"] for i in inv))
    if bat is not None:
        puteri["baterie_kWh"] = intr["baterie_kWh"] = _nr(bat)
    if re.search(r"\bhibrid", c.t):
        ex["hibrid"] = intr["hibrid"] = True
    return puteri


def extrage_ge(c: Ctx, vals, intr, ex):
    puteri = {}
    S, P = _prima(vals, "kVA"), _prima(vals, "kW")
    if S:
        puteri["Sn_GE_kVA"] = intr["Sn_GE_kVA"] = _nr(S["val"])
    if P:
        puteri["P_kW"] = intr["P_sarcina_kW"] = _nr(P["val"])
    return puteri


# =====================================================================================================
# Locuință (SPEC §C.8): casă / apartament → {alimentare, schema_pamant, RA_ohm, circuite[], ks}
# =====================================================================================================
RE_LOCUINTA = re.compile(r"\bcas(?:a|ei|e|uta)\b|\blocuint\w*|\bapartament\w*|\bgarsonier\w*|\bvil(?:a|e|ei)\b"
                         r"|(?<![\w+])p\s*\+\s*[1-3m]\b|\bparter\b|\bmansard\w*|\bduplex\b")
RE_PRIZA_PAMANT = re.compile(r"priz\w*\s+(?:propri\w*\s+)?de\s+pamant(?:\s+propri\w*)?")
_CAMERA = (r"(?:\s+(?:din\s+|de\s+la\s+|de\s+|la\s+)?(?:living\w*|dormitor\w*|camer\w*|hol\w*|birou\w*|parter\w*|etaj\w*"
           r"|garaj\w*|mansard\w*|pod\w*|subsol\w*|interior\w*|exterior\w*|curte|gradin\w*|teras\w*|dressing\w*))?")
# (regex pe textul normalizat, receptor, nume canonic | None = numele din text). Ordinea = prioritatea.
RECEPTORI_LOC = [
    (r"wallbox\w*|statie\s+(?:de\s+)?(?:incarcare|ve|ev)\w*(?:\s+(?:masina|auto|ve|ev)\w*)?"
     r"|incarcator\w*(?:\s+(?:pentru\s+|de\s+)?(?:masina|auto|ve|ev|electric)\w*)?|incarcare\s+(?:masina|auto|ve|ev)\w*"
     r"|masin\w*\s+electric\w*|vehicul\w*\s+electric\w*|\bev\b|\bve\b", "vehicul_electric", "Încărcare VE"),
    (r"pomp\w*\s+de\s+caldura|heat\s*pump|\bpdc\b", "pompa_caldura", "Pompă de căldură"),
    (r"masin\w*\s+de\s+spalat\s+vase|\bmsv\b|spalator\w*\s+de\s+vase", "masina_spalat_vase", "Mașină de spălat vase"),
    (r"masin\w*\s+de\s+spalat(?:\s+rufe)?|\bmsr\b", "masina_spalat_rufe", "Mașină de spălat rufe"),
    (r"uscator\w*(?:\s+de\s+rufe)?", "uscator", "Uscător"),
    (r"hidrofor\w*|pomp\w*\s+(?:de\s+)?(?:apa|put\w*|foraj\w*)|pomp\w*\s+submersibil\w*", "pompa_apa", "Pompă apă"),
    (r"poart\w*\s+automat\w*|automatizare\w*\s+poart\w*|motor\w*\s+poart\w*", "poarta_automata", "Poartă automată"),
    (r"plit\w*(?:\s+(?:cu\s+|pe\s+)?inductie)?(?:\s+electric\w*)?|\binductie\b|aragaz\w*(?:\s+electric\w*)?",
     "plita", "Plită"),
    (r"cuptor\w*(?:\s+electric\w*)?", "cuptor", "Cuptor"),
    (r"aer\w*\s+conditionat\w*|aparat\w*\s+de\s+aer(?:\s+conditionat\w*)?|\bclim\w*|\bac\b|\bsplit\w*",
     "aer_conditionat", "Aer condiționat"),
    (r"\bsaun\w*", "sauna", "Saună"),
    (r"incalzire\w*\s+(?:in\s+pardoseala\s+)?electric\w*|convector\w*|calorifer\w*\s+electric\w*"
     r"|radiator\w*\s+electric\w*|pardoseal\w*\s+electric\w*", "incalzire_electrica", "Încălzire electrică"),
    (r"\bcentral\w*(?:\s+termic\w*)?(?:\s+(?:pe|cu)\s+(?:gaz\w*|peleti|lemne))?", "centrala_termica", "Centrală termică"),
    (r"\bboiler\w*", "boiler", "Boiler"),
    (r"priz\w*\s+(?:de\s+|din\s+|la\s+)?bucatari\w*", "prize_bucatarie", "Prize bucătărie"),
    (r"priz\w*\s+(?:de\s+|din\s+|la\s+)?bai\w*(?:\s+(?:parter|etaj)\w*)?", "prize_baie", None),
    (r"priz\w*\s+(?:de\s+|din\s+)?(?:exterior\w*|curte|gradin\w*|teras\w*)", "prize_exterior", "Prize exterior"),
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
                         r"|beneficiar\w*|client\w*|putere\w*|aprobat\w*|in|din|la|jud\w*|pentru|retea|schema)\b")
RE_PRE_MULT = re.compile(r"(?:(?<![\d+.,×])(?P<n>\d+)|\b(?P<w>doua|doi|trei|patru|cinci))\s*[x×]?\s*$")

# seturi tipice (nume, receptor) — presupuse când descrierea nu listează circuitele
SET_TIPIC = {
    "apartament": [("Iluminat", "iluminat"), ("Prize camere", "prize"), ("Prize bucătărie", "prize_bucatarie"),
                   ("Prize baie", "prize_baie"), ("Mașină de spălat rufe", "masina_spalat_rufe")],
    "casa_parter": [("Iluminat interior", "iluminat"), ("Iluminat exterior", "iluminat"), ("Prize camere", "prize"),
                    ("Prize living", "prize"), ("Prize bucătărie", "prize_bucatarie"), ("Plită", "plita"),
                    ("Cuptor", "cuptor"), ("Prize baie", "prize_baie"), ("Mașină de spălat rufe", "masina_spalat_rufe"),
                    ("Boiler", "boiler"), ("Centrală termică", "centrala_termica"), ("Prize exterior", "prize_exterior")],
    "casa_p1": [("Iluminat parter", "iluminat"), ("Iluminat etaj", "iluminat"), ("Iluminat exterior", "iluminat"),
                ("Prize parter", "prize"), ("Prize etaj", "prize"), ("Prize bucătărie", "prize_bucatarie"),
                ("Plită", "plita"), ("Cuptor", "cuptor"), ("Prize baie parter", "prize_baie"),
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
            gasiti.append({"s": m.start(), "e": m.end(), "receptor": rec, "nume": nume})
    gasiti.sort(key=lambda g: g["s"])
    for i, g in enumerate(gasiti):
        urm = gasiti[i + 1]["s"] if i + 1 < len(gasiti) else len(t)
        ms = RE_STOP_LOC.search(t, g["e"])
        stop = min(urm, ms.start() if ms else len(t), g["e"] + 40)
        coada = t[g["e"]:stop]
        g["coada_e"] = stop
        n = 1
        m = re.search(r"(?:^|\s)[x×]\s*(\d+)\b|\(\s*(\d+)\s*(?:buc\w*\.?)?\s*\)"
                      r"|\b(\d+|doua|doi|trei|patru|cinci)\s*(?:bucati|bucata|buc\b\.?|aparate|unitati)", coada)
        if m:
            v = next(x for x in m.groups() if x)
            n = _NUMERAL.get(v) or int(v)
        mp = RE_PRE_MULT.search(t[:g["s"]])
        g["s_tot"] = g["s"]
        if mp and n == 1:
            n = int(mp.group("n")) if mp.group("n") else _NUMERAL[mp.group("w")]
            g["s_tot"] = mp.start()
        g["n"] = max(1, min(n, 20))
        m = re.search(rf"(?<![\w.,])({NUM})\s*(kw|w)\b", coada)
        g["P"] = numar(m.group(1)) * UNITATI[m.group(2)][1] if m else None
        m = re.search(rf"(?<![\w.,])({NUM})\s*(m|metri|ml)\b", coada)
        g["L"] = numar(m.group(1)) if m else None
        g["tri"] = bool(re.search(r"trifaz\w*|\b3f\b|\b400\s*v\b", coada))
    return gasiti


def _tip_locuinta(t: str) -> str:
    if re.search(r"\bapartament\w*|\bgarsonier\w*", t):
        return "apartament"
    if re.search(r"(?<![\w+])p\s*\+\s*[1-3m]\b|\betaj\w*|\bmansard\w*|\bduplex\b", t):
        return "casa_p1"
    return "casa_parter"


def _e_locuinta(c: Ctx) -> bool:
    """Casă / apartament. „Branșament BMPM 7 kW pentru casă” fără circuite/receptori rămâne branșament;
    prosumator / CEF / GE / PT au prioritate (instalația principală nu e tabloul casei)."""
    t = c.t
    if not RE_LOCUINTA.search(t):
        return False
    if ("prosumator" in t or re.search(r"\bgrup(?:ul)?\s+electrogen|\bats\b", t)
            or re.search(r"\bcef\b|fotovoltaic|\d\s*[km]wp\b|invertor|\bbess\b|panouri", t)
            or re.search(r"\bPT\b", c.orig) or re.search(r"post(?:ul)?\s+(?:de\s+)?transformare|\d\s*[km]va\b", t)):
        return False
    if re.search(r"\bbmpm|\bbmpt|bransament|\bfirida", t):
        return bool(re.search(r"tablou|circuit|plecar", t) or _gaseste_receptori(t))
    return True


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
    out = [dict(b) for b in baza]
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


def extrage_locuinta(c: Ctx, intr, ex):
    t = c.t
    puteri = {}
    tipl = ex["locuinta"] = _tip_locuinta(t)
    # rețeaua: trifazat doar dacă se spune; altfel monofazat (uzual la locuințe)
    tri = bool(re.search(r"trifaz\w*|\btri\b|\b400\s*v\b|\bbmpt|\b3f\b|\b3\s*×\s*\d+\s*a\b", t))
    mono_decl = bool(re.search(r"monofaz\w*|\bmono\b|\b230\s*v\b|\bbmpm|\b1f\b", t))
    if tri or mono_decl:
        retea = ex["retea"] = intr["retea"] = "tri" if tri else "mono"
    else:                  # rețeaua NU se presupune: schimbă tot tabloul → se cere utilizatorului
        retea = ex["retea"] = None
        ex["_retea_lipsa"] = True
    # circuitele (înainte de puterea generală: kW/A/m de lângă un receptor îi aparțin acestuia)
    gasiti = _gaseste_receptori(t)
    for g in gasiti:
        c.consumat.append((g["s_tot"], g["coada_e"]))
    listati = []
    for g in gasiti:
        nume = g["nume"] or nume_normalizat(c.o(g["s"], g["e"]))
        faza = None
        if g["receptor"] in TRI_POSIBIL_LOC and retea == "tri" and (g["P"] is None or g["P"] > P_PRAG_3F_KW or g["tri"]):
            faza = "3F"
        for k in range(1, g["n"] + 1):
            listati.append(_circuit_loc(nume if g["n"] == 1 else f"{nume} {k}", g["receptor"], g["P"], g["L"], faza))
        if g["n"] > 1:
            c.nota(f"„{c.o(g['s_tot'], g['coada_e']).strip()}” = {g['n']} circuite separate ({nume} 1…{g['n']})")
        if g["tri"] and retea == "mono":
            c.probleme.append(("I08", f"Contradicție: „{c.o(g['s'], g['coada_e']).strip()}” trifazat la o locuință "
                                      "monofazată (I08).", "Branșamentul locuinței este trifazat (3 × 400 V)?"))
    plus = bool(re.search(r"tablou\w*\s+tipic|\bplus\b|\bin\s+plus\b|\bpe\s+langa\b|\bsi\s+restul\b", t))
    descr = DESCR_LOCUINTA[tipl]
    tipic = [_circuit_loc(n, r) for n, r in SET_TIPIC[tipl]]
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
        circuite = _combina_circuite([_circuit_loc(n, r) for n, r in SET_BAZA], listati)
        adaugate = [x["nume"] for x in circuite if x not in listati]
        c.nota(f"receptorii listați + circuitele de bază ale oricărei locuințe"
               + (f" ({', '.join(adaugate)})" if adaugate else "") + f" = {len(circuite)} circuite — PRESUPUNERE, "
               "corectați lista dacă diferă")
    for x in circuite:
        if retea == "tri" and x["receptor"] in TRI_POSIBIL_LOC and "faza" not in x and "P_kW" not in x:
            x["faza"] = "3F"                                           # din setul tipic, la rețea trifazată
        if x.get("faza") == "3F" and "P_kW" not in x:
            c.nota(f"{x['nume']}: receptor trifazat (3F) la rețeaua trifazată")
        elif x.get("faza") == "3F":
            c.nota(f"{x['nume']} {fmt(x['P_kW'])} kW > {fmt(P_PRAG_3F_KW)} kW → circuit trifazat (3F)")
    intr["circuite"] = ex["circuite"] = circuite
    # alimentarea: P aprobată, Q branșament, coloana (din textul rămas după receptori)
    tm = c.mascat()
    vals = valori(tm)
    al = {}
    if re.search(r"bransament\w*\s+(?:\w+\s+)?nou|\bnou\w*\s+bransament|\bbmp[mt]\s+nou|racordare\s+nou", t):
        al["tip"] = "bransament_nou"
    elif re.search(r"\bexistent", t):
        al["tip"] = "bransament_existent"
    m = re.search(rf"(?:putere\w*(?:\s+(?:aprobat|maxim|absorbit|instalat|contractat)\w*)?|aprobat\w*|\bp\s*aprobat\w*)"
                  rf"\s*(?:de\s+|=\s*|:\s*)?({NUM})\s*(kw|mw)\b", tm)
    P = numar(m.group(1)) * UNITATI[m.group(2)][1] if m else (_prima(vals, "kW") or {}).get("val")
    if P is not None:
        al["P_aprobata_kW"] = puteri["P_aprobata_kW"] = _nr(P)
    m = re.search(rf"\bq\w*\s*(?:bransament\w*\s*|general\s*)?(?:de\s+|=\s*|:\s*)?({NUM})\s*a\b"
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
    if cablu:
        al["cablu"] = cablu
    intr["alimentare"] = al
    # schema de legare la pământ, RA, ks
    if re.search(r"\bTT\b", c.orig) or re.search(r"\bschema\s+tt\b|priz\w*\s+(?:de\s+pamant\s+propri|propri\w*\s+de\s+pamant)", t):
        intr["schema_pamant"] = ex["schema_pamant"] = "TT"
    elif re.search(r"\btn-?c-?s\b", t):
        intr["schema_pamant"] = ex["schema_pamant"] = "TN-C-S"
    m = re.search(rf"\b(?:ra|rp|rezistent\w*(?:\s+(?:de\s+dispersie|a\s+prizei|prizei))?)\s*(?:=|de|:)?\s*({NUM})\s*(?:ω|ohm\w*)",
                  t) or re.search(rf"(?<![\w.,])({NUM})\s*(?:ω|ohm\w*)", t)
    if m:
        intr["RA_ohm"] = _nr(numar(m.group(1)))
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
            sigma = sum(p["valoare"] for p in pl)
            out.append(f"P tablou din bilanț: Σ = {fmt(sigma)} kW, ks = {fmt(ks, 2)} → Pc = {fmt(ks * sigma)} kW "
                       "(NU prima valoare din text)")
        else:
            out.append(f"P tablou din bilanțul plecărilor: ks = {fmt(ks, 2)} ({n} plecări) (NU prima valoare din text)")
    out += _pres_plecari(intr, ex, "tablou")
    if "L_alimentare_m" not in intr:
        out.append(f"alimentarea {_nume_alim(ex)} L = 50 m")
    if intr.get("origine") == "pt_propriu":
        out.append("limite ΔU pentru PT propriu: 6 % iluminat / 8 % altele (de la bornele JT ale PT)")
        if intr.get("pt_Sn_kVA"):
            out.append(f"sursa: bara JT a trafo-ului propriu {intr['pt_Sn_kVA']} kVA (Ik3max și Zb calculate de motor)")
        else:
            out.append("Sn necunoscut: Ik3max 25 kA și impedanța buclei implicite la bara PT (avertismente V32)")
    else:
        out.append("sursa: rețea publică prin BMPT cu RCCB 300 mA în amonte")
        out.append(TEXT_OD)
    return out


def _nume_alim(ex):
    return ex.get("_nume_tablou") or "tablou"


def _pres_pt(intr, ex):
    out = []
    sn = intr.get("Sn_kVA")
    if sn in norme.TRAFO:
        uk, pk, _ = norme.TRAFO[sn]
        out.append(f"trafo ulei 20/0,4 kV {norme.TRAFO_GRUPA_CONEXIUNI}, uk {fmt(uk)} %, Pk {pk} W (Tier 2)")
        if intr.get("celula_trafo") == "sigurante" and sn <= norme.TRAFO_SN_MAX_SIGURANTE_MT_KVA:
            out.append(f"siguranțe MT {fmt(norme.TRAFO_SIGURANTA_MT_A.get(sn, 0))} A (orientativ, tabel producător)")
        elif not intr.get("celula_trafo"):
            out.append(_celula(sn))
    out.append(f"S\"kQ = {fmt(norme.MT_SKQ_IMPLICIT_MVA)} MVA (rețea MT 20 kV, valoare implicită)")
    out += _pres_plecari(intr, ex, "pt")
    return out


def _s_cef(intr):
    p_inv = sum(i["n"] * i["Pn_kW"] for i in intr.get("invertoare") or [])
    p_pcs = (intr.get("bess") or {}).get("P_kW") or 0
    return FACTOR_INV * (p_inv + p_pcs), p_inv + p_pcs


def _pres_cef(intr, ex):
    out = ["Iac,max = 1,1·Pn/(√3·400) (fișa invertorului lipsește)",
           "cablu invertor Al PVC D1, L = 30 m"]
    S, P = _s_cef(intr)
    if intr.get("pt_Sn_kVA"):
        sn = intr["pt_Sn_kVA"]
        if ex.get("_pt_adaugat"):
            out.append(f"S = {fmt(S)} kVA > 400 kVA → PT propriu 20/0,4 kV {sn} kVA adăugat (racord MT); {_celula(sn)}")
        else:
            out.append(f"PT propriu {sn} kVA (declarat); {_celula(sn)}")
    elif S <= norme.PRAG_RACORD_BMPT_KVA:
        out.append(f"racord JT prin BMPT (S = {fmt(S)} kVA ≤ 173 kVA)")
        out.append(TEXT_OD)
    elif intr.get("atr_jt") or S <= norme.PRAG_RACORD_JT_MAX_KVA:
        out.append(f"racord JT direct din PT OD, conform ATR (S = {fmt(S)} kVA)")
        out.append(TEXT_OD)
    cat = "B" if P >= norme.RFG_PRAG_TIP_B_KW else "A"
    out.append(f"categoria {cat} RfG ({fmt(P)} kW {'≥' if cat == 'B' else '<'} 1 MW); PI conform Ord. ANRE 208/2018 și ATR")
    return out


def _pres_prosumator(intr, ex):
    mono = intr.get("retea") == "mono"
    out = [f"Iac,max = 1,1·Pn/{'230' if mono else '(√3·400)'} (fișa invertorului lipsește)",
           "invertor la 15 m de tabloul consumatorului, Cu PVC metoda C",
           "DDR pe circuitul invertorului tip A (sau B dacă fișa nu exclude curenți de defect c.c.) — se confirmă",
           "PI integrată în invertor, reglaje conform ATR (Ord. ANRE 228/2018); contor bidirecțional furnizat de OD"]
    if intr.get("hibrid"):
        out.append("baterie cuplată în c.c. la invertorul hibrid (fără PCS separat)")
    return out


def _pres_ge(intr, ex):
    return ["cosφ 0,9", f"x\"d = {fmt(norme.GE_XD2_IMPLICIT, 2)} (valoare tipică)",
            "ATS 4 poli cu interblocaj mecanic + electric, categoria AC-33B",
            "fără excitație susținută declarată (Ik1 ≈ In_G)"]


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
    if P is not None and P > 30:
        d.intreaba("I06", f"Confirmați puterea aprobată {fmt(P)} kW? La o locuință se aprobă uzual 5 … 30 kW.")
    if mono and P is not None and P > P_PRAG_MONO_LOC_KW:
        d.avertismente.append(f"P aprobată {fmt(P)} kW la branșament monofazat: peste {P_PRAG_MONO_LOC_KW} kW se recomandă "
                              f"trifazat (Ib = {fmt(P * 1000 / (U_MONO * norme.LOCUINTA_COSFI))} A; BMPM max. 40 A)")
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
    if mono and ib > norme.BMPM["I_max_A"]:
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
        d.intreaba("I02", "Care sunt plecările din TGJT (kW sau A)?")


def _v_cef(intr, ex, d):
    if not intr.get("invertoare"):
        d.refuza("I02", "Lipsesc invertoarele (număr și putere) (I02).",
                 "Câte invertoare și de ce putere (kW c.a.)?")
        return
    S, P = _s_cef(intr)
    if S > norme.TRAFO_SN_KVA[-1]:
        jum = _sn_standard(S / 2) or norme.TRAFO_SN_KVA[-1]
        d.refuza("I12", f"S = {fmt(S)} kVA > 2500 kVA (un singur trafo standard): în afara domeniului aplicației "
                        "(SPEC §A.3).",
                 f"Împărțiți centrala pe două posturi de transformare (ex. 2 × {jum} kVA)?")
        return
    if intr.get("pt_Sn_kVA") or S <= norme.PRAG_RACORD_BMPT_KVA:
        return
    if S <= norme.PRAG_RACORD_JT_MAX_KVA:
        d.avertismente.append(f"V66: S = {fmt(S)} kVA > 173 kVA: racord JT direct din PT OD, conform ATR")
    elif intr.get("atr_jt"):
        d.avertismente.append(f"V66: S = {fmt(S)} kVA > 400 kVA, racord JT acceptat doar conform ATR")
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


def interpreteaza_local(text: str) -> dict:
    c = Ctx(text)
    tip = detecteaza_tip(c)
    retea = detecteaza_retea(c)
    ex = _extras_gol(c, tip, retea)
    ex.update(detecteaza_cartus(c))
    m = re.search(rf"cos\s*(?:fi|φ|phi)\s*(?:=|de)?\s*({NUM})", c.t)
    intr = {"tip_schema": tip} if tip else {}
    if m:
        ex["cosfi"] = intr["cosfi"] = numar(m.group(1))
        c.consumat.append((m.start(), m.end()))
    if tip in ("tablou", "pt"):
        c.lista = parseaza_lista(c)
        ex["_nume_tablou"] = _nume_tablou(c)
    vals = valori(c.mascat())
    note_text(c, valori(c.t))
    if tip in ("bransament", "prosumator") and retea_declarata(c) is None:
        ex["_retea_lipsa"] = True
    if tip == "bransament":
        if retea_declarata(c):
            intr["retea"] = retea_declarata(c)
        ex["puteri"] = extrage_bransament(c, vals, intr, ex)
    elif tip in ("tablou", "pt"):
        ex["puteri"] = extrage_tablou(c, vals, intr, ex, tip)
    elif tip == "cef":
        ex["puteri"] = extrage_cef(c, vals, intr, ex)
    elif tip == "prosumator":
        ex["puteri"] = extrage_prosumator(c, vals, intr, ex)
    elif tip == "ge_ats":
        ex["puteri"] = extrage_ge(c, vals, intr, ex)
    if ex.get("_retea_lipsa"):
        # nu se presupune — DOAR dacă puterea nu încape fizic în monofazat (BMPM max. 40 A) rețeaua rezultă trifazată
        P = intr.get("P_kW") or intr.get("Pn_inv_kW") or ((intr.get("S_kVA") or 0) * 0.9) or None
        ib_mono = (P * 1000 / (U_MONO * 0.9)) if P else (intr.get("Ib_A") or None)
        if ib_mono and ib_mono > norme.BMPM["I_max_A"]:
            intr["retea"] = ex["retea"] = "tri"; ex.pop("_retea_lipsa")
            c.nota(f"rețea nedeclarată, dar {fmt(P) + ' kW' if P else fmt(ib_mono) + ' A'} nu încape în monofazat (BMPM max. "
                   f"{fmt(norme.BMPM['I_max_A'], 0)} A) → trifazat 3 × 400 V")
    elif tip == "locuinta":
        ex["puteri"] = extrage_locuinta(c, intr, ex)
    m = re.search(rf"(?:armonic\w*\s*3|\bh3)\D{{0,12}}?({NUM})\s*%", c.t)
    if m:
        intr["h3"] = _nr(numar(m.group(1)))
    return _finalizeaza(intr, ex, c.note, c.probleme, motor="reguli")


def _finalizeaza(intr, ex, note, probleme, motor) -> dict:
    """Verificări F.7 → presupuneri F.6 → răspuns F.8."""
    d = verifica(intr, ex, probleme)
    if d.actiune == "genereaza" and d.intrebari:      # R1: se generează ȘI se întreabă
        d.actiune = "genereaza_cu_intrebare"
    presupus = [] if d.actiune == "refuza" else _unice(note + d.presupus + presupuneri(intr, ex))
    if d.actiune == "refuza":
        presupus = []
    cartus = {"beneficiar": ex.get("beneficiar"), "adresa": ex.get("adresa"),
              "plansa": ex.get("plansa"), "faza": ex.get("faza")}
    extras = {k: v for k, v in ex.items() if not k.startswith("_") and k != "tip_schema"}
    rez = {"actiune": d.actiune, "tip_schema": intr.get("tip_schema"), "intrare_fizica": intr, "extras": extras,
           "cartus": cartus, "presupus": presupus, "intrebari": d.intrebari, "avertismente": d.avertismente,
           "refuz_cod": d.cod if d.actiune == "refuza" else None,
           "refuz_motiv": d.motiv if d.actiune == "refuza" else None, "motor": motor}
    rez["intelegere"] = text_raspuns(rez)
    return rez


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
    for k, eticheta, u in (("P_kW", "P", "kW"), ("Ib_A", "Ib", "A"), ("S_kVA", "S", "kVA"), ("In_Q1_A", "Q1", "A"),
                           ("Sn_kVA", "Sn", "kVA"), ("kWp", "P c.c.", "kWp"), ("P_ca_kW", "P c.a.", "kW"),
                           ("Sn_GE_kVA", "Sn GE", "kVA"), ("baterie_kWh", "baterie", "kWh")):
        if p.get(k) is not None:
            bucati.append(f"{eticheta} = {fmt(p[k])} {u}")
    for i in p.get("invertoare") or []:
        bucati.append(f"{i['n']} × invertor {fmt(i['Pn_kW'])} kW")
    if p.get("bess"):
        bucati.append(f"BESS {fmt(p['bess']['P_kW'])} kW / {fmt(p['bess']['kWh'])} kWh")
    return ", ".join(bucati)


def _plecari_text(pl) -> str:
    out = []
    for p in pl:
        s = p["nume"]
        if p["valoare"] is not None:
            s += f" {fmt(p['valoare'])} {p['unitate']}"
        if "L_m" in p:
            s += f" ({fmt(p['L_m'])} m)"
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
                  "In_Q_bransament_A", "L_pcs_m", "RA_ohm", "ks"}
_CHEI_TEXT = {"tip_schema": set(TIPURI), "retea": {"tri", "mono"}, "material": {"Cu", "Al"},
              "masura_ceruta": {"directa", "semidirecta"}, "celula_trafo": {"sigurante", "intreruptor"},
              "origine": {"retea_publica", "pt_propriu"}, "schema_pamant": {"TN-C-S", "TN-S", "TT"},
              "bmpt_fortat": set(norme.BMPT)}
_CHEI_BOOL = {"atr_jt", "hibrid", "circuite_finale"}
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
    for k in ("n_alte", "S_fortat", "N_fortat", "PE_fortat", "n_fortat", "theta", "rho_sol"):
        if cb.get(k) is not None and _numar_sau_none(cb[k]) is not None:
            out[k] = _numar_sau_none(cb[k])
    return out or None


def _normalizeaza_plecare(p):
    if not isinstance(p, dict) or not str(p.get("nume") or "").strip():
        return None
    out = {"nume": str(p["nume"]).strip()}
    for k in ("In_A", "P_kW", "L_m"):
        if p.get(k) is not None and _numar_sau_none(p[k]) is not None:
            out[k] = _numar_sau_none(p[k])
    if p.get("receptor") in ("iluminat", "prize", "forta", "motor", "tablou"):
        out["receptor"] = p["receptor"]
    if isinstance(p.get("copii"), list):
        out["copii"] = [x for x in (_normalizeaza_plecare(k) for k in p["copii"]) if x]
    cb = _normalizeaza_cablu(p.get("cablu"))
    if cb:
        out["cablu"] = cb
    return out


def normalizeaza_intrare(d: dict) -> dict:
    """Păstrează doar cheile cunoscute (forma din cazuri_golden.json → intrare), cu tipuri corecte."""
    if not isinstance(d, dict):
        return {}
    out = {}
    for k, v in d.items():
        if k in _CHEI_NUMERICE and _numar_sau_none(v) is not None:
            out[k] = _numar_sau_none(v)
        elif k in _CHEI_TEXT and v in _CHEI_TEXT[k]:
            out[k] = v
        elif k in _CHEI_BOOL and isinstance(v, bool):
            out[k] = v
    for k in ("cablu", "cablu_pcs"):
        cb = _normalizeaza_cablu(d.get(k))
        if cb:
            out[k] = cb
    if isinstance(d.get("plecari"), list):
        out["plecari"] = [x for x in (_normalizeaza_plecare(p) for p in d["plecari"]) if x]
    if isinstance(d.get("invertoare"), list):
        out["invertoare"] = [{"n": int(i.get("n") or 1), "Pn_kW": _numar_sau_none(i.get("Pn_kW"))}
                             for i in d["invertoare"] if isinstance(i, dict) and _numar_sau_none(i.get("Pn_kW"))]
    if isinstance(d.get("bess"), dict):
        b = {k: _numar_sau_none(d["bess"].get(k)) for k in ("P_kW", "kWh")}
        if b["kWh"]:
            out["bess"] = b
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
    return out


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
    if tip == "cef" and not d.get("invertoare"):
        err.append("CEF fără invertoare")
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
    return err


# =====================================================================================================
# Opțional: Claude (SDK `anthropic`) — cerem DOAR intrare_fizica
# =====================================================================================================
SYSTEM_LLM = """Ești interpretorul de text al unui generator de scheme monofilare JT (România).
Primești o descriere în română și întorci STRICT un obiect JSON `intrare_fizica`, fără alt text.
NU dimensiona nimic (fără secțiuni, calibre alese de tine, căderi de tensiune). Scrie doar ce spune textul.
Chei permise: tip_schema (bransament|tablou|cef|pt|prosumator|ge_ats), retea (tri|mono), P_kW, In_Q1_A,
Ib_A (branșament dat în A), S_kVA (branșament dat în kVA) — exact una din P_kW/Ib_A/S_kVA la branșament,
circuite_finale (true pentru un TD cu circuite finale), origine (pt_propriu) cu pt_Sn_kVA opțional,
L_coloana_m (branșament), L_alimentare_m (tablou), material (Cu|Al), cablu{material,izolatie(PVC|XLPE),metoda(C|D1|D2|E),n_alte},
plecari[{nume, In_A | P_kW, L_m, receptor, copii[...], cablu{...}}], kWp, invertoare[{n, Pn_kW}], bess{P_kW, kWh},
pt_Sn_kVA, Sn_kVA, atr_jt, masura_ceruta (semidirecta), bmpt_fortat, Pn_inv_kW, hibrid, baterie_kWh, Sn_GE_kVA,
P_sarcina_kW, cosfi, h3, celula_trafo (sigurante|intreruptor).
Pentru o casă / un apartament: tip_schema "locuinta", retea (mono|tri), alimentare{tip (bransament_existent|bransament_nou),
In_Q_bransament_A, P_aprobata_kW, L_coloana_m, cablu{...}}, schema_pamant (TN-C-S|TT), RA_ohm, ks,
circuite[{nume, receptor, P_kW, L_m, faza (L1|L2|L3|3F)}] cu receptor ∈ iluminat, prize, prize_bucatarie, prize_baie,
prize_exterior, masina_spalat_rufe, masina_spalat_vase, uscator, boiler, cuptor, plita, aer_conditionat, pompa_caldura,
centrala_termica, incalzire_electrica, vehicul_electric, pompa_apa, poarta_automata, sauna, alt_circuit.
Reguli: „3×63 A” = 3 plecări de 63 A; numele plecărilor se păstrează cum au fost scrise (prima literă majusculă dacă
erau minuscule); plecări fără nume → TD-1, TD-2…; „PT” majuscul = post de transformare, „pt” = „pentru”;
MWp/MVA/km se convertesc în kWp/kVA/m. Omite cheile pe care textul nu le precizează."""


def _are_credentiale() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
                or os.path.exists(os.path.expanduser("~/.config/anthropic")))


def intrare_llm(text: str) -> dict | None:
    """Cere modelului doar `intrare_fizica`. None dacă SDK/cheie lipsesc sau răspunsul nu e JSON."""
    try:
        import anthropic
    except ImportError:
        return None
    if not _are_credentiale():
        return None
    client = anthropic.Anthropic()
    msg = client.beta.messages.create(
        model="claude-opus-5-5", max_tokens=4000,
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        output_config={"effort": "medium"},
        system=SYSTEM_LLM,
        messages=[{"role": "user", "content": text}],
    )
    if msg.stop_reason == "refusal":
        return None
    txt = "".join(b.text for b in msg.content if b.type == "text")
    j = re.search(r"\{.*\}", txt, re.S)
    return json.loads(j.group(0)) if j else None


def interpreteaza(text: str, foloseste_llm: bool = False) -> dict:
    """Funcția publică (F.1). Fără LLM: doar reguli locale. Cu LLM: intrare_fizica de la model, validată
    și trecută prin aceleași verificări F.7; la orice eroare rămâne rezultatul local."""
    local = interpreteaza_local(text)
    if not foloseste_llm:
        return local
    try:
        brut = intrare_llm(text)
    except Exception as e:  # rețea, cheie invalidă, JSON stricat
        local["presupus"].append(f"(LLM indisponibil: {e.__class__.__name__}; s-a folosit interpretorul local)")
        local["intelegere"] = text_raspuns(local)
        return local
    if brut is None:
        return local
    intr = normalizeaza_intrare(brut)
    erori = valideaza_forma(intr)
    if erori or (local["tip_schema"] and intr.get("tip_schema") != local["tip_schema"]):
        local["presupus"].append("(rezultatul LLM a fost respins la validarea formei: "
                                 + ("; ".join(erori) or "tip de schemă diferit") + ")")
        local["intelegere"] = text_raspuns(local)
        return local
    ex = copy.deepcopy(local["extras"])
    ex["tip_schema"] = intr["tip_schema"]
    ex.setdefault("puteri", {})
    return _finalizeaza(intr, ex, [], [], motor="llm")
