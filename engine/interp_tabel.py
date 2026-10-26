"""r8: tabelele copiate (Excel cu tab-uri, CSV cu „;” / „,”, tabele cu „|”, tabele numerotate) → fraze liniare.

Clientul real trimite datele ca tabel: o ofertă, un BOM, un bilanț de puteri, o listă de receptoare. Interpretorul
citește fraze („2 x Strung CNC 18,5 kW”), nu coloane. Modulul ăsta rescrie FIECARE RÂND al unui tabel recunoscut ca o
frază cu semnificația coloanei, ÎNAINTE de orice altă regulă:

    Nr⇥Denumire⇥P[kW]⇥Buc          →   (antetul dispare)
    1⇥Strung CNC⇥18,5⇥2            →   2 x Strung CNC 18,5 kW
    invertor;Huawei;SUN2000-100KTL-M2;6;100   →   6 x invertor Huawei SUN2000-100KTL-M2 100 kW
    Plita⇥7,4 kW⇥3  (Faze)         →   Plita 7,4 kW trifazat

* antetul: coloanele recunoscute după cuvinte (Denumire / Nume / Receptor / Echipament, Cant / Buc / Qty, P / Putere /
  Pn / P[kW], L / Lungime, U / Faze, In / Curent, Model, Producător, UM, Obs); unitatea din antet („P[kW]”, „L (m)”,
  „P[W]”) se lipește numerelor fără unitate; cantitatea se aplică („6 x …”), nu se pierde;
* fără antet: prima coloană cu numere 1, 2, 3 … = număr de ordine (se scoate); restul coloanelor rămân în ordine;
* rândurile fără rol în schemă (structură de montaj, manoperă, cablu solar c.c., conectori) se scot, cu notă;
* un rând care nu are numărul de celule al tabelului (o propoziție după tabel: „Rețea: trifazat 20 kW, TN-C-S”) încheie
  tabelul și rămâne neschimbat.

Rezultatul e un text NOU (lungimea nu se păstrează) pe care rulează interpretorul obișnuit; notele explică citirea.
"""
from __future__ import annotations

import re

_DIA = str.maketrans("șşțţăâîȘŞȚŢĂÂÎ", "ssttaaiSSTTAAI")
NUM = r"\d+(?:[.,]\d+)?"


def _n(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").translate(_DIA).lower()).strip()


# semnificația unei coloane din antet: (cheie, regex pe celula normalizată)
ANTET = [
    ("idx", r"(?:nr\.?|poz\.?|pozitia|crt\.?|nr\.?\s*crt\.?|#|no\.?|item)"),
    ("n", r"(?:cant\w*\.?|buc\w*\.?|nr\.?\s*buc\w*\.?|qty|quantity|pcs|numar|nr\.?\s*(?:de\s+)?(?:circuite|bucati)|n|x|circuite"
          r"|nr\.?\s*circ\w*\.?)"),
    ("nume", r"(?:denumire\w*|nume|receptor\w*|consumator\w*|circuit\w*|echipament\w*|utilaj\w*|descriere\w*|articol\w*"
             r"|produs\w*|element\w*|tip|item\s+name|name|load\w*|description|equipment|tablou\w*|plecare\w*)"),
    ("model", r"(?:model\w*|cod\w*|tip\s+model|referint\w*|part\s*(?:no|number))"),
    ("prod", r"(?:producator\w*|marca|brand|fabricant\w*|manufacturer|furnizor\w*)"),
    ("P", r"(?:p|pn|pi|pinst|pi\s*\w*|putere\w*(?:\s+\w+)?|power|kw|w|s|sn)"),
    ("L", r"(?:l|lungime\w*|length|lung\.?|distanta)"),
    ("faze", r"(?:faze|faza|nr\.?\s*faze|u|tensiune\w*|retea|phases?|voltage|alimentare)"),
    ("I", r"(?:in|i|ib|curent\w*|calibru\w*|a|current|protectie)"),
    ("um", r"(?:um|u\.m\.?|unit\w*|u/m)"),
    ("obs", r"(?:obs\w*\.?|observati\w*|mentiun\w*|nota|note|remarks?|comentari\w*|pornire|demaror)"),
]
ANTET = [(k, re.compile(rf"^{rx}$")) for k, rx in ANTET]
RE_UNIT_ANTET = re.compile(r"\s*[\[(]\s*(kw|w|kva|a|m|km|kwp|kwh|v|buc)\s*[\])]\s*$|\s+(kw|kva|a|m|kwp|kwh|v)$")
# rânduri fără rol în schema monofilară (BOM-ul unei oferte)
RE_RAND_INUTIL = re.compile(r"\bstructur\w*|\bmontaj\w*|\bmanoper\w*|\btransport\w*|\bconector\w*|\bmc4\b|\baccesori\w*"
                            r"|\bcleme\b|\bsin[ae]\b|\bproiectare\b|\bavizare\b|\bcablu\w*\s+solar\w*|\bcablu\w*\s+(?:c\.?c|dc)\b")
SEPARATORI = ("\t", "|", ";", ",")


def _celule(linie: str, sep: str) -> list[str]:
    if sep == "|":
        linie = linie.strip().strip("|")
    if sep == ",":
        parti = linie.split(",")
    elif sep == ",~":                # virgula zecimală („1,2 kW”, „7,4”) nu separă coloane
        parti = re.split(r"(?<!\d),|,(?!\d)", linie)
    else:
        parti = linie.split(sep)
    return [p.strip() for p in parti]


def _sem_antet(cel: str):
    """(cheie, unitate) pentru o celulă de antet sau None."""
    c = _n(cel.replace("_", " "))
    unit = None
    mu = RE_UNIT_ANTET.search(c)
    if mu:
        unit = mu.group(1) or mu.group(2)
        c = c[:mu.start()].strip()
    c = re.sub(r"[.:]+$", "", c).strip()
    for k, rx in ANTET:
        if rx.match(c):
            if k == "P" and c in ("w",):
                unit = unit or "w"
            if k == "P" and c in ("kw",):
                unit = unit or "kw"
            if k == "P" and c in ("s", "sn"):
                unit = unit or "kva"
            if k == "I" and c == "a":
                unit = unit or "a"
            return k, unit
    if unit:                         # „[kW]” singur
        return {"kw": "P", "w": "P", "kva": "P", "a": "I", "m": "L", "km": "L", "buc": "n"}.get(unit, "obs"), unit
    return None


def _e_antet(celule: list[str]) -> list | None:
    sem = [_sem_antet(c) for c in celule]
    rec = [s for s in sem if s]
    # antet = cel puțin 2 coloane recunoscute, majoritatea celulelor fără cifre
    if len(rec) >= 2 and len(rec) * 2 >= len([c for c in celule if c]) and not any(
            re.search(r"\d", c) and not RE_UNIT_ANTET.search(_n(c)) for c in celule if c):
        return sem
    return None


def _e_numar(c: str) -> bool:
    return bool(re.fullmatch(NUM, c.strip()))


def _faza(v: str) -> str:
    v = _n(v)
    if re.fullmatch(r"3|3f|3p|tri\w*|400\s*v?|3\s*[x×]\s*400\s*v?|3n~?|three[\s-]*phase", v):
        return "trifazat"
    if re.fullmatch(r"1|1f|1p|mono\w*|230\s*v?|1n~?|single[\s-]*phase", v):
        return "monofazat"
    return v


def _cu_unitate(v: str, unit: str | None) -> str:
    v = v.strip()
    if not v:
        return ""
    if unit and _e_numar(v):
        return f"{v} {unit if unit != 'kw' else 'kW'}".replace(" kva", " kVA").replace(" kwp", " kWp").replace(" kwh", " kWh")
    return v


def _rand(celule: list[str], sem: list) -> str | None:
    """Rândul unui tabel cu antet → frază."""
    d = {}
    alte = []
    for cel, s in zip(celule, sem + [None] * (len(celule) - len(sem))):
        if not cel.strip():
            continue
        if s is None:
            alte.append(cel.strip())
            continue
        k, unit = s
        if k in d and k not in ("obs",):
            alte.append(cel.strip())
            continue
        d[k] = (cel.strip(), unit)
    if not d.get("nume") and not d.get("model") and not alte:
        return None
    parti = []
    n = d.get("n", ("", None))[0]
    um = _n(d.get("um", ("", None))[0])
    mn = re.fullmatch(r"(\d+)\s*(?:buc\w*\.?|x|pcs)?", _n(n)) if n else None
    nume_r = _n(d.get("nume", ("", None))[0])
    if mn and int(mn.group(1)) > 1 and "P" in d and _e_numar(d["P"][0]) and re.search(
            r"\bcorp\w*|\blamp\w*|\baplic\w*|\bspot\w*|\bproiector\w*|\bplafonier\w*|\bled\b", nume_r):
        # corpurile de iluminat dintr-un rând = un circuit cu puterea lor totală (nu N plecări de 50 W)
        k = int(mn.group(1))
        v, unit = d["P"]
        f_ = float(v.replace(",", ".")) * (0.001 if (unit or "kw") == "w" else 1)
        d["P"] = (f"{round(k * f_, 3):g}", "kw")
        n, mn = "", None
    if n and um in ("m", "ml", "km") and _e_numar(n):
        n_pref, L_extra = "", f"{n} {um}"                         # „Cablu …⇥m⇥800” = 800 m, nu 800 bucăți
    else:
        n_pref, L_extra = (f"{mn.group(1)} x " if mn and int(mn.group(1)) > 1 else ""), ""
        if n and not mn:
            alte.append(n)
    parti.append(n_pref + " ".join(x for x in (d.get("nume", ("", 0))[0], d.get("prod", ("", 0))[0], d.get("model", ("", 0))[0])
                                    if x).strip())
    if "P" in d:
        v, unit = d["P"]
        if unit is None and _e_numar(v):
            unit = "kw"
        nume_rand = _n(" ".join(x[0] for k, x in d.items() if k in ("nume", "model")))
        if re.search(r"\bmodul\w*|\bpanou\w*|\bmodule\b", nume_rand) and _e_numar(v) and unit in ("kw", "w"):
            # puterea unui modul fotovoltaic = Wp (0,7 kW → 700 Wp); dacă modelul o are deja („700W”), nu se repetă
            wp = float(v.replace(",", ".")) * (1000 if unit == "kw" else 1)
            if not re.search(rf"\b{wp:g}\s*w", nume_rand):
                parti.append(f"{wp:g} Wp")
        else:
            parti.append(_cu_unitate(v, unit))
    if "I" in d:
        parti.append(_cu_unitate(d["I"][0], d["I"][1] or "A"))
    if "L" in d:
        v, unit = d["L"]
        parti.append(_cu_unitate(v, unit or "m"))
    if L_extra:
        parti.append(L_extra)
    if "faze" in d:
        parti.append(_faza(d["faze"][0]))
    parti += alte
    if "obs" in d:
        parti.append(d["obs"][0])
    txt = " ".join(p for p in parti if p).strip()
    return re.sub(r"\s+", " ", txt) or None


def _rand_fara_antet(celule: list[str], col_idx: bool) -> str:
    cel = [c.strip() for c in celule]
    if col_idx:
        cel = cel[1:]
    return re.sub(r"\s+", " ", " ".join(c for c in cel if c)).strip()


def _sep_linie(linie: str):
    """separatorul de coloane al unui rând (în ordinea priorității) și numărul de celule"""
    for sep in SEPARATORI:
        if sep in linie:
            n = len(_celule(linie, sep))
            if n >= 2:
                return sep, n
    return None, 0


def _celula_scurta(c: str) -> bool:
    return len(c.split()) <= 6


def rescrie_tabel(text: str) -> tuple[str, list[str]]:
    """text → (text cu tabelele rescrise ca fraze, note). Fără tabel → (text, [])."""
    if not text or "\n" not in text:
        return text, []
    linii = text.split("\n")
    out, note = [], []
    i = 0
    while i < len(linii):
        sep, nc = _sep_linie(linii[i])
        if not sep:
            out.append(linii[i])
            i += 1
            continue
        # blocul: rândurile consecutive cu același separator și același număr de celule (± celule goale la final)
        j = i + 1
        while j < len(linii):
            s2, n2 = _sep_linie(linii[j])
            if s2 != sep or n2 != nc:
                break
            j += 1
        bloc = linii[i:j]
        cel = [_celule(x, sep) for x in bloc]
        if sep == "," and len({len(r) for r in cel}) > 1:
            cel = [_celule(x, ",~") for x in bloc]
        if sep == "," and not _e_antet(cel[0]) and all(re.fullmatch(r"(?:[^,]*\d,\d[^,]*)+", x.replace(" ", "")) is not None
                                                       and not re.search(r"(?<!\d),|,(?!\d)", x) for x in bloc):
            out.extend(bloc)                       # r8: „1. Strung 7,5 kW” — virgula zecimală, nu un tabel CSV
            i = j
            continue
        sem = _e_antet(cel[0])
        corp = cel[1:] if sem else cel
        # un tabel = antet + ≥ 1 rând, sau ≥ 2 rânduri fără antet; virgula / „;” cer celule scurte (nu proză)
        e_tabel = (sem and len(corp) >= 1) or (len(corp) >= 2 and sep in ("\t", "|"))
        if not sem and sep in (";", ",") and len(corp) >= 2:
            e_tabel = all(_celula_scurta(c) for r in corp for c in r) and any(
                sum(1 for c in r if re.search(r"\d", c)) for r in corp) and len({len(r) for r in corp}) == 1
        if sep in (";", ",") and any(not all(_celula_scurta(c) for c in r) for r in corp):
            e_tabel = False
        if not e_tabel:
            out.extend(bloc)
            i = j
            continue
        scoase = []
        if sem:
            for r in corp:
                if RE_RAND_INUTIL.search(_n(" ".join(r))):
                    scoase.append(" ".join(x for x in r if x))
                    continue
                f = _rand(r, sem)
                if f:
                    out.append(f)
            note.append("tabelul copiat (" + {"\t": "tab-uri", "|": "„|”", ";": "„;”", ",": "„,”"}[sep] + ") citit pe "
                        "coloane după antet („" + " | ".join(x for x in cel[0] if x) + "”): fiecare rând = un element, "
                        "cu cantitatea și unitatea coloanei")
        else:
            prima = [r[0].strip() for r in corp]
            col_idx = all(re.fullmatch(r"\d{1,3}[.)]?", p) for p in prima) and \
                [int(re.sub(r"\D", "", p)) for p in prima] == list(range(int(re.sub(r"\D", "", prima[0])),
                                                                        int(re.sub(r"\D", "", prima[0])) + len(prima)))
            for r in corp:
                if RE_RAND_INUTIL.search(_n(" ".join(r))):
                    scoase.append(" ".join(x for x in r if x))
                    continue
                out.append(_rand_fara_antet(r, col_idx))
            note.append("tabelul copiat fără antet: fiecare rând = un element"
                        + (" (prima coloană = numărul de ordine, ignorat)" if col_idx else ""))
        if scoase:
            note.append("rânduri din tabel fără rol în schema monofilară (ignorate): " + "; ".join(f"„{x}”" for x in scoase))
        i = j
    return "\n".join(out), note
