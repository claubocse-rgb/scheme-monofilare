"""Catalogul local de echipamente (module PV, invertoare, BESS/PCS, SPD c.c., siguranțe gPV) și importul din fișe tehnice.

* Catalogul: `date/echipamente.json` (lângă aplicație, ca prețurile; în versiunea web — stocat în browser prin web_api).
  Fiecare echipament = {id, tip, producator, model, ...date de fișă, sursa, actualizat}.
* Importul din fișă: `importa_fisa(bytes)` → text (pypdf sau extractorul propriu, `engine.pdftext`) → `extrage(text)`:
  euristici (etichete RO/EN/DE, unități, intervale, tabele cu mai multe variante pe coloane) → propunere cu nivel de
  încredere pe fiecare câmp. Utilizatorul confirmă / corectează în interfață înainte de salvare — nimic nu intră
  automat în catalog sau în calcul.
* Opțional: `rafineaza_claude(text, tip)` structurează textul cu Claude (dacă SDK-ul și cheia există); rezultatul trece
  prin aceleași verificări de plauzibilitate.
"""
import datetime, json, math, os, pathlib, re, unicodedata

from . import pdftext

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _fisier():
    return pathlib.Path(os.environ.get("SM_DATE") or ROOT / "date") / "echipamente.json"


# câmp → (etichetă afișată, unitate, interval plauzibil)
CAMPURI = {
    "modul_pv": {
        "Pmax_W": ("Pmax", "W", (20, 900)), "Voc_V": ("Voc", "V", (5, 120)), "Isc_A": ("Isc", "A", (0.5, 30)),
        "Vmpp_V": ("Vmpp", "V", (5, 110)), "Impp_A": ("Impp", "A", (0.5, 30)),
        "beta_Voc_pct_K": ("β(Voc)", "%/K", (-0.7, -0.05)), "alpha_Isc_pct_K": ("α(Isc)", "%/K", (0.0, 0.2)),
        "gamma_Pmax_pct_K": ("γ(Pmax)", "%/K", (-0.7, -0.1)), "Umax_sistem_V": ("Umax sistem", "V", (300, 1600)),
        "I_rev_A": ("Siguranță max. în serie", "A", (2, 50)), "eficienta_pct": ("Randament", "%", (5, 30)),
    },
    "invertor": {
        "Pn_kW": ("Pn c.a.", "kW", (0.3, 6000)), "Smax_kVA": ("Smax", "kVA", (0.3, 7000)),
        "Iac_max_A": ("Iac,max", "A", (1, 10000)), "Umax_dc_V": ("Umax c.c.", "V", (80, 1600)),
        "MPPT_min_V": ("MPPT min", "V", (30, 1500)), "MPPT_max_V": ("MPPT max", "V", (60, 1600)),
        "U_pornire_V": ("U pornire", "V", (20, 1000)), "Idc_max_A": ("Idc max / MPPT", "A", (3, 3000)),
        "Isc_max_A": ("Isc max / MPPT", "A", (3, 3000)), "nr_MPPT": ("Nr. MPPT", "", (1, 60)),
        "eficienta_pct": ("Randament max.", "%", (80, 100)),
    },
    "bess": {
        "P_kW": ("P nominală", "kW", (0.5, 10000)), "kWh": ("Capacitate", "kWh", (0.5, 50000)),
        "kWh_util": ("Capacitate utilă", "kWh", (0.5, 50000)), "Iac_max_A": ("Iac,max PCS", "A", (1, 20000)),
        "U_nom_V": ("U nominală c.c.", "V", (12, 1600)),
    },
    "spd_cc": {
        "Ucpv_V": ("Ucpv", "V", (100, 1600)), "In_kA": ("In (8/20)", "kA", (1, 60)), "Imax_kA": ("Imax (8/20)", "kA", (1, 100)),
        "Up_kV": ("Up", "kV", (0.5, 10)),
    },
    "gpv": {"In_A": ("In", "A", (1, 630)), "U_V": ("U c.c.", "V", (100, 1600))},
}
TIPURI = {"modul_pv": "Modul fotovoltaic", "invertor": "Invertor", "bess": "BESS / PCS", "spd_cc": "SPD c.c.",
          "gpv": "Siguranță gPV"}
ALIAS_TIP = {"pcs": "bess", "baterie": "bess", "modul": "modul_pv", "panou": "modul_pv", "spd": "spd_cc"}
TEXT_CAMPURI = ("producator", "model", "sursa", "chimie", "retea", "observatii")
BOOL_CAMPURI = ("hibrid",)
NIVEL = {3: "ridicată", 2: "medie", 1: "scăzută"}


# ------------------------------------------------------------------------------------------------ catalog
def citeste_catalog():
    try:
        d = json.loads(_fisier().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    lst = [e for e in (d.get("echipamente") or []) if isinstance(e, dict) and e.get("id")]
    lst.sort(key=lambda e: (e.get("tip", ""), (e.get("producator") or "").lower(), (e.get("model") or "").lower()))
    return {"echipamente": lst, "tipuri": TIPURI, "campuri": {t: {k: [v[0], v[1]] for k, v in c.items()} for t, c in CAMPURI.items()}}


def _slug(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _nr(v):
    """număr din valoarea primită (acceptă „12,5”); None dacă lipsește; ValueError dacă nu e număr"""
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        raise ValueError
    if isinstance(v, (int, float)):
        if not math.isfinite(v):
            raise ValueError
        return v
    t = str(v).strip().replace(" ", "").replace(" ", "").replace("−", "-").replace(",", ".")
    x = float(t)
    if not math.isfinite(x):
        raise ValueError
    return int(x) if x == int(x) and "." not in t else x


def normalizeaza(e):
    """echipamentul primit din interfață → forma de catalog (validată). ValueError cu mesaj în română."""
    if not isinstance(e, dict):
        raise ValueError("echipamentul trebuie să fie un obiect")
    tip = ALIAS_TIP.get(str(e.get("tip") or ""), str(e.get("tip") or ""))
    if tip not in CAMPURI:
        raise ValueError(f"tip de echipament necunoscut „{e.get('tip')}” (se acceptă: {', '.join(TIPURI)})")
    model = str(e.get("model") or "").strip()
    if not model:
        raise ValueError("lipsește modelul echipamentului")
    out = {"tip": tip, "producator": str(e.get("producator") or "").strip()[:80], "model": model[:120]}
    for k in TEXT_CAMPURI[2:]:
        if e.get(k) not in (None, ""):
            out[k] = str(e[k]).strip()[:300]
    for k in BOOL_CAMPURI:
        if e.get(k) is not None:
            out[k] = bool(e[k])
    for k, (et, um, (lo, hi)) in CAMPURI[tip].items():
        try:
            v = _nr(e.get(k))
        except (ValueError, TypeError):
            raise ValueError(f"{et}: „{e.get(k)}” nu este un număr")
        if v is None:
            continue
        if k == "nr_MPPT":
            v = int(round(v))
        if not (lo <= v <= hi):
            raise ValueError(f"{et} = {v} {um} în afara domeniului plauzibil ({lo}…{hi} {um})".replace(" )", ")"))
        out[k] = v
    if tip == "modul_pv":
        for a, b, et in (("Vmpp_V", "Voc_V", "Vmpp < Voc"), ("Impp_A", "Isc_A", "Impp < Isc")):
            if out.get(a) is not None and out.get(b) is not None and out[a] >= out[b]:
                raise ValueError(f"date incoerente: trebuie {et}")
    if tip == "invertor" and out.get("MPPT_min_V") is not None and out.get("MPPT_max_V") is not None \
            and out["MPPT_min_V"] >= out["MPPT_max_V"]:
        raise ValueError("date incoerente: MPPT min trebuie < MPPT max")
    out["id"] = _slug(f"{tip}-{out['producator']}-{model}")
    return out


def scrie(cerere):
    """POST /api/echipamente: {"echipament": {...}} (adaugă / înlocuiește după tip+producător+model) sau
    {"sterge": id}. Întoarce catalogul."""
    f = _fisier()
    d = citeste_catalog()
    lst = d["echipamente"]
    salvat = None
    if cerere.get("sterge"):
        lst = [x for x in lst if x.get("id") != cerere["sterge"]]
    elif cerere.get("echipament") is not None:
        e = normalizeaza(cerere["echipament"])
        e["actualizat"] = datetime.date.today().isoformat()
        lst = [x for x in lst if x.get("id") != e["id"]] + [e]
        salvat = e["id"]
    else:
        raise ValueError("cererea trebuie să conțină „echipament” sau „sterge”")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"echipamente": lst}, ensure_ascii=False, indent=1), encoding="utf-8")
    out = citeste_catalog()
    out["salvat"] = salvat
    return out


# ------------------------------------------------------------------------------------------------ extragerea din text
PRODUCATORI = ["JA Solar", "LONGi", "Jinko Solar", "JinkoSolar", "Trina Solar", "Canadian Solar", "Risen", "Astronergy",
               "DAS Solar", "Aiko", "Tongwei", "REC", "Qcells", "Q CELLS", "Hanwha", "Meyer Burger", "AXITEC", "Bauer",
               "SunPower", "Maxeon", "Yingli", "Seraphim", "ZNShine", "Huasun", "Leapton", "Ulica", "GCL", "Chint",
               "Huawei", "Fronius", "SMA", "Sungrow", "GoodWe", "Solis", "Ginlong", "Growatt", "SolarEdge", "Victron",
               "Deye", "Sofar", "SOFARSOLAR", "Kostal", "ABB", "FIMER", "Enphase", "Hoymiles", "Kehua", "Sigenergy",
               "Huawei Digital Power", "BYD", "Pylontech", "Tesla", "LG Energy Solution", "CATL", "EVE", "Hithium",
               "Alpha ESS", "AlphaESS", "Dyness", "Weco", "Felicity", "Sermatec", "Kaco", "KACO new energy", "Delta",
               "DEHN", "Phoenix Contact", "CITEL", "Mersen", "SIBA", "Bussmann", "Eaton", "Schneider Electric",
               "Hager", "Raycap", "OBO Bettermann", "Legrand", "Socomec", "Weidmüller"]

# eticheta (regex, pe text normalizat cu litere mici) — câmp, unitățile acceptate, excluderi
_TEMP = r"temp|coef|coeff|°c|/k\b|%/"
REGULI = {
    "modul_pv": [
        ("Pmax_W", r"(maximum|max\.?|rated|nominal|peak)\s*power|\bp\s*max\b|\bpmpp\b|\bp\s*mpp\b|putere\w*\s*(maxim|nominal)|nennleistung|\bpmax\b",
         ("w", "wp"), _TEMP + r"|tolerance|toleran|sorting|bin|efficien|nmot|noct|stc\b.*nmot|power\s*class|output\s*power\s*warranty|warranty|garan|density|\bm²|m2|voltage|current|tensiune|curent|spannung|strom"),
        ("Voc_V", r"open[- ]?circuit\s*voltage|\bv\s*oc\b|\bu\s*oc\b|tensiune\w*\s*(în|in|de)\s*gol|leerlaufspannung", ("v",), _TEMP),
        ("Isc_A", r"short[- ]?circuit\s*current|\bi\s*sc\b|curent\w*\s*de\s*scurt|kurzschlussstrom", ("a",), _TEMP),
        ("Vmpp_V", r"(maximum|max\.?|optimum|rated)\s*(power\s*)?(point\s*)?(operating\s*)?voltage|\bv\s*mpp?\b|\bu\s*mpp?\b|\bvmp\b|tensiune\w*\s*(la\s*)?(punctul\s*de\s*)?putere\w*\s*maxim|mpp[- ]spannung|voltage\s*at\s*(max|pmax)",
         ("v",), _TEMP + r"|system|open"),
        ("Impp_A", r"(maximum|max\.?|optimum|rated)\s*(power\s*)?(point\s*)?(operating\s*)?current|\bi\s*mpp?\b|\bimp\b|curent\w*\s*(la\s*)?(punctul\s*de\s*)?putere\w*\s*maxim|mpp[- ]strom|current\s*at\s*(max|pmax)",
         ("a",), _TEMP + r"|short|fuse|reverse"),
        ("beta_Voc_pct_K", r"((temp\w*\.?\s*coef\w*|coeficient\w*\s*de\s*temperatur\w*|temperaturkoeffizient)\w*.{0,30}(\bv\s*oc|\bu\s*oc|open|gol|leerlauf))|β\s*\(?\s*v\s*oc|\bβ\s*_?voc|(v\s*oc|u\s*oc)\s*(temp\w*\.?\s*)?coef",
         ("%/k", "%/°c", "%/℃", "%/c", "mv/k", "mv/°c", "mv/℃", "v/k", "v/°c", "%"), r"\bisc\b|short|pmax|power|current|curent"),
        ("alpha_Isc_pct_K", r"((temp\w*\.?\s*coef\w*|coeficient\w*\s*de\s*temperatur\w*|temperaturkoeffizient)\w*.{0,30}(\bi\s*sc|short|scurt|kurzschluss))|α\s*\(?\s*i\s*sc|(i\s*sc)\s*(temp\w*\.?\s*)?coef",
         ("%/k", "%/°c", "%/℃", "%/c", "%"), r"\bvoc\b|open|pmax|power"),
        ("gamma_Pmax_pct_K", r"((temp\w*\.?\s*coef\w*|coeficient\w*\s*de\s*temperatur\w*|temperaturkoeffizient)\w*.{0,30}(p\s*max|power|putere|pmpp|leistung))|γ\s*\(?\s*p\s*max|(p\s*max)\s*(temp\w*\.?\s*)?coef",
         ("%/k", "%/°c", "%/℃", "%/c", "%"), r"\bvoc\b|open|\bisc\b|short"),
        ("Umax_sistem_V", r"max(imum|\.)?\s*(system|sys\.?)\s*voltage|tensiune\w*\s*maxim\w*\s*(a\s*)?(de\s*)?sistem|max(\.|imale)?\s*systemspannung",
         ("v", "vdc", "v dc"), ""),
        ("I_rev_A", r"(max(imum|\.)?\s*)?series\s*fuse|fuse\s*rating|reverse\s*current|siguranț\w*\s*(maxim\w*\s*)?(în\s*)?serie|rückstrombelastbarkeit|max\.?\s*sicherung",
         ("a",), ""),
        ("eficienta_pct", r"module\s*efficiency|randament\w*\s*(al\s*)?modul|modulwirkungsgrad|panel\s*efficiency", ("%",), r"cell|celul"),
    ],
    "invertor": [
        ("Pn_kW", r"rated\s*(ac\s*)?(active\s*)?(output\s*)?power|nominal\s*(ac\s*)?(active\s*)?(output\s*)?power|ac\s*nominal\s*(output\s*)?power|nominal\s*ac\s*power|putere\w*\s*nominal\w*|nennleistung|\bpn\b|ac\s*output\s*power|rated\s*output",
         ("kw", "w"), r"apparent|aparent|\bva\b|kva|dc|pv\s*power|input|intrare|max(imum)?\s*pv|battery|charge"),
        ("Smax_kVA", r"max(imum|\.)?\s*(ac\s*)?apparent\s*(ac\s*)?(output\s*)?power|putere\w*\s*aparent\w*\s*maxim\w*|max(\.|imale)?\s*scheinleistung|max(imum|\.)?\s*ac\s*output\s*power",
         ("kva", "va", "kw", "w"), r"rated|nominal"),
        ("Iac_max_A", r"max(imum|\.)?\s*(ac\s*)?(continuous\s*)?output\s*current|curent\w*\s*maxim\w*\s*(de\s*ieșire|de\s*iesire|c\.?a\.?|ac)|max(\.|imaler)?\s*ausgangsstrom|ac\s*max(imum|\.)?\s*current|max(imum|\.)?\s*ac\s*current|rated\s*output\s*current|output\s*current\s*\(?max",
         ("a",), r"\bdc\b|input|intrare|battery|fault|inrush|short"),
        ("Umax_dc_V", r"max(imum|\.)?\s*(dc\s*|pv\s*)?input\s*voltage|(dc|pv)\s*input\s*voltage\s*range|max(imum|\.)?\s*(dc|pv)\s*voltage|tensiune\w*\s*maxim\w*\s*(de\s*intrare|c\.?c\.?|dc|pv)|max(\.|imale)?\s*(dc[- ]?)?eingangsspannung|absolute\s*max",
         ("v",), r"mppt|mpp\b|start|battery|rated|nominal"),
        ("MPPT", r"mpp\w*\s*(operating\s*)?voltage\s*range|operating\s*voltage\s*range|mpp\w*\s*range|domeniu\w*\s*(de\s*)?(tensiune\s*)?mppt|interval\w*\s*(de\s*)?(tensiune\s*)?mppt|mpp[- ]?spannungsbereich|voltage\s*range\s*\(?mppt|mppt\s*voltage|tensiune\w*\s*mppt",
         ("v",), r"full\s*(load|power)|rated|nominal|start|battery"),
        ("U_pornire_V", r"start[- ]?up\s*(input\s*)?voltage|start(ing)?\s*voltage|tensiune\w*\s*de\s*pornire|startspannung|min(imum|\.)?\s*input\s*voltage", ("v",), r"range|mppt"),
        ("Isc_max_A", r"max(imum|\.)?\s*(dc\s*|pv\s*|input\s*|array\s*)?short[- ]?circuit\s*current|\bisc\s*(pv|max)|curent\w*\s*(maxim\w*\s*)?de\s*scurtcircuit|max(\.|imaler)?\s*kurzschlussstrom",
         ("a",), r"output|ac\b|ieșire|iesire"),
        ("Idc_max_A", r"max(imum|\.)?\s*(dc\s*|pv\s*|operating\s*)?input\s*current|max(imum|\.)?\s*current\s*per\s*mppt|curent\w*\s*maxim\w*\s*de\s*intrare|max(\.|imaler)?\s*eingangsstrom|max(imum|\.)?\s*dc\s*current",
         ("a",), r"short|scurt|kurzschluss|output|ac\b"),
        ("nr_MPPT", r"(number|no\.?|nr\.?|numărul?|anzahl)\s*(of\s*|de\s*|der\s*)?(independent\s*)?mpp\w*|mppt\s*(number|trackers|count)|mpp[- ]?tracker|mppts?\s*/\s*strings|number\s*of\s*mpp",
         ("",), r"string\s*per|inputs\s*per|per\s*mppt"),
        ("eficienta_pct", r"max(imum|\.)?\s*efficiency|randament\w*\s*maxim|max(\.|imaler)?\s*wirkungsgrad", ("%",), r"euro|cec|mppt"),
    ],
    "bess": [
        ("kWh_util", r"usable\s*(energy|capacity)|capacitate\w*\s*util\w*|nutzbare\s*(energie|kapazität)", ("kwh", "wh", "mwh"), ""),
        ("kWh", r"(rated|nominal|total|battery)?\s*(energy|capacity)|capacitate\w*|energie\w*\s*(nominal\w*|stocat\w*)|nennenergie|kapazität",
         ("kwh", "wh", "mwh"), r"usable|util|nutzbar|per\s*module|module\s*capacity|cell"),
        ("P_kW", r"rated\s*(ac\s*)?(output\s*)?power|nominal\s*(ac\s*)?(output\s*)?power|max(imum|\.)?\s*(continuous\s*)?(charge|discharge|charging|discharging|output)\s*power|putere\w*\s*nominal\w*|nennleistung|pcs\s*power|rated\s*power",
         ("kw", "w", "mw"), r"apparent|peak|pv"),
        ("Iac_max_A", r"max(imum|\.)?\s*ac\s*(output\s*)?current|rated\s*ac\s*(output\s*)?current|ac\s*(output\s*)?current|curent\w*\s*maxim\w*\s*(de\s*ieșire\s*)?c\.?a\.?",
         ("a",), r"\bdc\b|charge|discharge|battery|cell"),
        ("U_nom_V", r"(rated|nominal)\s*(dc\s*|battery\s*)?voltage|tensiune\w*\s*nominal\w*|nennspannung|battery\s*voltage", ("v",), r"\bac\b|grid|range|interval|cell"),
    ],
    "spd_cc": [
        ("Ucpv_V", r"\bu\s*cpv\b|max(imum|\.)?\s*continuous\s*operating\s*(dc\s*)?voltage|tensiune\w*\s*maxim\w*\s*de\s*funcționare", ("v",), ""),
        ("In_kA", r"nominal\s*discharge\s*current|\bi\s*n\b\s*\(?8/20|curent\w*\s*nominal\w*\s*de\s*desc", ("ka",), r"max"),
        ("Imax_kA", r"max(imum|\.)?\s*discharge\s*current|\bi\s*max\b|curent\w*\s*maxim\w*\s*de\s*desc", ("ka",), ""),
        ("Up_kV", r"voltage\s*protection\s*level|\bu\s*p\b|nivel\w*\s*de\s*protecție", ("kv", "v"), ""),
    ],
    "gpv": [
        ("In_A", r"rated\s*current|curent\w*\s*nominal|\bin\b", ("a",), ""),
        ("U_V", r"rated\s*voltage|tensiune\w*\s*nominal\w*|\bun\b", ("v", "vdc", "v dc"), ""),
    ],
}

_NUM = r"[-−–+]?\d+(?:[.,]\d+)*"
_TOKEN_NUM = re.compile(r"(?<![\w.,])(" + _NUM + r")(?:\s*(%\s*/\s*(?:°\s*c|℃|k|c)\b|m?v\s*/\s*(?:°\s*c|℃|k)\b|mwh|kwh|wh|kva|kvar|kv|mw|kw|wp|w|va|vdc|v|ka|ma|a|%|°c))?(?![\w])", re.I)
_INTERVAL = re.compile(r"(" + _NUM + r")\s*(v|a|kw)?\s*(?:~|…|\.\.\.|–|—|-|to|bis|până la|pana la)\s*(" + _NUM + r")\s*(v|a|kw)?\b", re.I)


def _norm_text(t):
    t = unicodedata.normalize("NFKC", t)
    t = t.replace(" ", " ").replace(" ", " ").replace(" ", " ").replace("−", "-").replace("–", "-")
    t = t.replace("℃", "°C").replace("º", "°").replace("˚", "°").replace("µ", "u")
    return t


def _numar(s):
    """„1,500” (mii, EN) / „0,275” / „49,9” (zecimal RO) / „1.500,5” → float"""
    s = s.strip().replace("−", "-").replace("–", "-")
    neg = s.startswith("-")
    s = s.lstrip("+-")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        a, _, b = s.rpartition(",")
        if len(b) == 3 and a and a.lstrip("0") and "," not in a and len(a) <= 3:
            s = a + b          # 1,500 → 1500 (separator de mii)
        else:
            s = s.replace(",", ".") if s.count(",") == 1 else s.replace(",", "")
    elif s.count(".") > 1:
        s = s.replace(".", "")
    v = float(s)
    return -v if neg else v


_PERECHE = re.compile(r"(" + _NUM + r")\s*([a-z%]{0,3})\s*/\s*(" + _NUM + r")\s*([a-z%]{0,3})(?![\w/])", re.I)


def _curata_celula(rest):
    rest = re.sub(r"\(\s*\d+\s*/\s*\d+\s*[uµ]?s?\s*\)", " ", rest)                 # (8/20 µs), (10/350)
    rest = re.sub(r"\[\s*\d\s*\]|\(\s*\d\s*\)|[¹²³⁴⁵⁶⁷⁸⁹](?!\w)", " ", rest)          # note de subsol [1], (2)
    rest = re.sub(r"\((?:[^()\d]|\b[a-zφ]+\d|=\s*\d+)*\)", " ", rest, flags=re.I)      # „(Voc)”, „(Idc max1 / Idc max2)”
    rest = re.sub(r"\[[^\]\d]*\]", " ", rest)                                             # „[V]”

    def pereche(m):            # „25,0 A / 12,5 A”, „1000V/1500V” → valoarea mai mare (MPPT 1 / MPPT 2, clase)
        try:
            a, b = _numar(m.group(1)), _numar(m.group(3))
        except ValueError:
            return m.group(0)
        u = m.group(4) or m.group(2)
        if (m.group(2) or "").lower() not in ("", (m.group(4) or "").lower()) and m.group(4):
            return m.group(0)
        return f"{m.group(1) if a >= b else m.group(3)} {u}"
    return _PERECHE.sub(pereche, rest)


def _valori(rest):
    """numerele unei celule de tabel (restul rândului după etichetă): [(valoare, unitate)]"""
    out = []
    for m in _TOKEN_NUM.finditer(rest):
        try:
            v = _numar(m.group(1))
        except ValueError:
            continue
        u = re.sub(r"\s", "", (m.group(2) or "")).lower().replace("℃", "°c")
        out.append((v, u))
    if any(u for _, u in out):          # cu unități explicite: numerele fără unitate sunt alte mărimi (note, condiții)
        out = [x for x in out if x[1]]
    return out


def _conv(camp, v, u, unit_ok, ctx=None):
    """convertește valoarea la unitatea câmpului; None dacă unitatea nu se potrivește"""
    u = u.replace("°c", "k").replace("/c", "/k")
    if camp.endswith("_pct_K"):
        if u in ("%/k", "%", ""):
            return v
        if u in ("mv/k", "v/k"):
            return ("V/K", v / (1000.0 if u == "mv/k" else 1.0))       # se raportează la Voc al variantei, mai jos
        return None
    if camp.endswith("_kW"):
        return {"kw": v, "w": v / 1000.0, "mw": v * 1000.0, "": v}.get(u)
    if camp.endswith("_kVA"):
        return {"kva": v, "va": v / 1000.0, "kw": v, "w": v / 1000.0, "": v}.get(u)
    if camp in ("kWh", "kWh_util"):
        return {"kwh": v, "wh": v / 1000.0, "mwh": v * 1000.0, "": v}.get(u)
    if camp.endswith("_W"):
        return {"w": v, "wp": v, "": v, "kw": v * 1000.0}.get(u)
    if camp.endswith("_kV"):
        return {"kv": v, "v": v / 1000.0, "": v}.get(u)
    if camp.endswith("_kA"):
        return {"ka": v, "": v}.get(u)
    if camp.endswith("_V"):
        return v if u in ("v", "vdc", "") else None
    if camp.endswith("_A"):
        return v if u in ("a", "") else (v / 1000.0 if u == "ma" else None)
    if camp.endswith("_pct"):
        return v if u in ("%", "") else None
    if camp == "nr_MPPT":
        return v if u == "" and v == int(v) else None
    return v


def detecteaza_tip(t):
    """tipul fișei după cuvintele-cheie: modul_pv, invertor, bess, spd_cc, gpv (+ scor)"""
    tl = t.lower()
    sc = {
        "modul_pv": len(re.findall(r"open[- ]?circuit|\bvoc\b|module efficiency|\bcells?\b|bifacial|junction box|mono[- ]?crystal|\bpmax\b|frame|glass|half[- ]?cut|celul", tl)),
        "invertor": len(re.findall(r"\bmppt?\b|inverter|invertor|wechselrichter|ac output|grid|anti[- ]?island|max\.? input voltage|euro(pean)? efficiency", tl)),
        "bess": len(re.findall(r"battery|baterie|\bkwh\b|\bbms\b|lifepo|\blfp\b|cycle life|state of charge|\bsoc\b|energy storage|stocare|depth of discharge|\bdod\b", tl)),
        "spd_cc": len(re.findall(r"surge|\bspd\b|u\s*cpv|descărcător|varistor|iec 61643|en 61643|type 2|tip 2", tl)),
        "gpv": len(re.findall(r"\bgpv\b|pv fuse|fuse[- ]?link|siguranț|iec 60269-6|10\s*x\s*38", tl)),
    }
    if sc["invertor"] and sc["bess"] and re.search(r"pcs|power conversion|energy storage system|all[- ]in[- ]one|cabinet", tl) \
            and not re.search(r"\bmppt\b.*\bmppt\b", tl, re.S):
        sc["bess"] += 3
    tip = max(sc, key=lambda k: sc[k])
    return (tip if sc[tip] > 0 else "modul_pv"), sc


def _producator(t):
    tl = t.lower()
    best = None
    for p in sorted(PRODUCATORI, key=len, reverse=True):
        m = re.search(r"(?<![a-z])" + re.escape(p.lower()) + r"(?![a-z])", tl)
        if m and (best is None or m.start() < best[1]):
            best = (p, m.start())
    return best[0] if best else ""


_COD = re.compile(r"\b([A-Z][A-Za-z]{0,10}[A-Z0-9]*[0-9][A-Z0-9]*(?:[-/.][A-Za-z0-9]+)+|[A-Z]{2,}[0-9]{2,}[A-Z0-9]*(?:[-/][A-Za-z0-9]+)*)\b")


def _modele(linii, n_var=1):
    """modelele: rândul „Model / Type / Tip” (o valoare sau câte una pe coloană), un rând-antet cu n_var celule
    (fișele cu mai multe variante pe coloane), altfel codurile din primele rânduri"""
    for L in linii[:200]:
        m = re.match(r"\s*(model(\s*name)?|type|tip(\s*modul)?|module\s*type|product\s*model|typ|bezeichnung|technical\s*data|date\s*tehnice|technische\s*daten)\b\s*[:\-]?\s*(.+)$", L, re.I)
        if m:
            rest = m.group(4)
            coduri = [c for c in _COD.findall(rest) if not re.fullmatch(r"(IEC|EN|UL|ISO|SR|VDE|CEI|IP)\d.*", c, re.I)]
            if coduri and (len(coduri) == n_var or n_var == 1) and len(set(coduri)) == len(coduri):
                return coduri
            celule = [c.strip() for c in re.split(r"\s{3,}|\t|\s\|\s", rest) if c.strip()]
            cod = [c for c in celule if re.search(r"\d", c) and re.search(r"[A-Za-z]", c) and len(c) >= 3]
            if cod and (len(cod) == n_var or n_var == 1):
                return cod if n_var > 1 else cod[:1]
    for L in linii[:40]:
        coduri = [c for c in _COD.findall(L) if not re.fullmatch(r"(IEC|EN|UL|ISO|SR|VDE|CEI|IP|ETL)\d.*", c, re.I)
                  and not re.fullmatch(r"\d+[A-Za-z]{1,3}", c)]
        if coduri:
            return coduri if len(coduri) > 1 and len({c[:4] for c in coduri}) == 1 else coduri[:1]
    # denumirea comercială de pe primele rânduri (ex. „DEHNguard M YPV 1000 FM”): prima celulă cu litere și cifre
    for L in linii[:6]:
        c = re.split(r"\s{3,}|\t", L.strip())[0]
        if re.search(r"\d", c) and re.search(r"[A-Za-z]{2}", c) and 4 <= len(c) <= 48 and not re.search(r"\b(19|20)\d\d\b|www\.|@", c):
            return [c]
    return []


def extrage(text, tip=None):
    """text din fișă → propunere {tip, producator, variante[{eticheta, model, campuri{k: {valoare, incredere, sursa}}}],
    implicit, avertismente}. Valorile au nivel de încredere: ridicată (etichetă + unitate + domeniu plauzibil),
    medie (fără unitate sau mai multe candidate), scăzută (dedusă / incoerentă)."""
    t = _norm_text(text or "")
    tip_det, scor = detecteaza_tip(t)
    tip = ALIAS_TIP.get(tip, tip) if tip else tip_det
    if tip not in REGULI:
        tip = tip_det
    linii = [L for L in (x.rstrip() for x in t.splitlines()) if L.strip()]
    sectiune = "stc"
    cand = {}            # câmp → [(valori, scor, sursa, sectiune)]
    for i, L in enumerate(linii):
        ll = L.lower()
        if re.search(r"\b(nmot|noct|nominal operating cell|800\s*w/m)", ll) and not re.search(r"\d+\s*(v|a|w)\b", ll[ll.find("noct"):] if "noct" in ll else ""):
            sectiune = "noct"
        elif re.search(r"\bstc\b|standard test condition", ll) and not re.search(r"\bnoct|nmot", ll):
            sectiune = "stc"
        # toate etichetele recunoscute pe rând (un rând poate avea mai multe mărimi: „… Voc 49,6 V Isc 14 A …”)
        potr = []
        for camp, pat, unit_ok, excl in REGULI[tip]:
            for m in re.finditer(pat, ll):
                if m.end() > m.start():
                    potr.append((m.start(), m.end(), camp, unit_ok, excl))
        potr.sort(key=lambda x: (x[0], -x[1]))
        alese = []
        for p_ in potr:
            if alese and p_[0] < alese[-1][1]:
                continue                       # suprapusă cu o etichetă mai lungă
            if alese and alese[-1][2] == p_[2] and not re.search(r"\d", ll[alese[-1][1]:p_[0]]):
                continue                       # aceeași mărime repetată în etichetă („Max. Power (Pmax)”)
            alese.append(p_)
        for k_, (st_, en_, camp, unit_ok, excl) in enumerate(alese):
            nxt = alese[k_ + 1][0] if k_ + 1 < len(alese) else len(L)
            # eticheta = de la ultima cifră dinaintea potrivirii până la prima cifră de după ea
            mm = re.search(r"\d[^\d]*$", ll[:st_])
            ctx0 = mm.start() + 1 if mm else 0
            dm = re.search(r"\d", ll[en_:nxt])
            eticheta = ll[ctx0:en_ + dm.start() if dm else nxt]
            if excl and not camp.endswith("_pct_K") and re.search(excl, eticheta):
                continue
            if camp.endswith("_pct_K") and excl and re.search(excl, eticheta[eticheta.rfind("coef") if "coef" in eticheta else 0:]):
                continue
            rest = L[en_:nxt]
            if not re.search(r"\d", rest) and nxt == len(L) and i + 1 < len(linii) and \
                    not re.search(r"[a-z]{4,}", linii[i + 1].lower().split("  ")[0] if linii[i + 1] else ""):
                rest = linii[i + 1]               # valoarea pe rândul următor
            rest = _curata_celula(rest)
            if camp == "MPPT" or (camp in ("Umax_dc_V",) and "range" in eticheta):
                iv = [(min(_numar(a), _numar(b)), max(_numar(a), _numar(b))) for a, _, b, _ in _INTERVAL.findall(rest)]
                if camp == "Umax_dc_V":
                    if iv:
                        cand.setdefault(camp, []).append(([x[1] for x in iv], 2, re.sub(r"\s{3,}", "   ", L.strip()), sectiune, 0))
                    continue
            if camp == "MPPT":
                iv = [(min(_numar(a), _numar(b)), max(_numar(a), _numar(b))) for a, _, b, _ in _INTERVAL.findall(rest)]
                if iv:
                    cand.setdefault("MPPT", []).append((iv, 3, re.sub(r"\s{3,}", "   ", L.strip()), sectiune, 0))
                continue
            vals = _valori(rest)
            if not vals:
                continue
            unit_l = re.search(r"\[\s*(%/°c|%/k|[a-z%/°]+)\s*\]|\(\s*(%/°c|%/k|v|a|w|kw|kwh|kva|%)\s*\)", eticheta, re.I)
            unit_et = (unit_l.group(1) or unit_l.group(2)).lower().replace(" ", "") if unit_l else ""
            conv = []
            unit_sigur = False
            for v, u in vals:
                uu = u or unit_et
                x = _conv(camp, v, uu, unit_ok)
                if x is None:
                    continue
                if u or unit_et:
                    unit_sigur = True
                conv.append(x)
            if camp == "Umax_sistem_V" and conv:
                conv = [max(conv)]
            if camp in ("Umax_dc_V", "U_pornire_V") and conv and len(set(conv)) > 1 and tip != "invertor":
                conv = [max(conv)]
            if not conv:
                continue
            sc = 3 if unit_sigur or camp == "nr_MPPT" else 2
            prio = 1 if camp in ("Iac_max_A", "Umax_dc_V", "Idc_max_A", "Isc_max_A", "Smax_kVA") and "max" in eticheta else 0
            cand.setdefault(camp, []).append((conv, sc, re.sub(r"\s{3,}", "   ", L.strip()), sectiune, prio))
    # număr de variante = numărul de coloane al mărimilor principale
    principale = {"modul_pv": ("Pmax_W", "Voc_V", "Isc_A", "Vmpp_V", "Impp_A"), "invertor": ("Pn_kW", "Iac_max_A", "Smax_kVA"),
                  "bess": ("kWh", "kWh_util", "P_kW")}.get(tip, ())
    n_var = 1
    for c in principale:
        for vals, sc, src, sec, _ in cand.get(c, [])[:1]:
            if len(vals) > n_var and len(vals) <= 12:
                n_var = len(vals)
    modele = _modele(linii, n_var)
    if len(modele) > n_var and n_var == 1 and len(modele) <= 12 and tip in ("modul_pv", "invertor", "bess"):
        modele = modele[:1]
    prod = _producator(t)
    avert = []
    variante = []
    for k in range(n_var):
        campuri = {}
        for camp, lst in cand.items():
            # preferă secțiunea STC și rândurile cu unitate; dintre candidate — primul rând
            lst2 = sorted(lst, key=lambda x: (x[3] != "stc", -x[4], -x[1]))
            vals, sc, src, sec, _ = lst2[0]
            if camp == "MPPT":
                iv = vals[k] if len(vals) == n_var else vals[0]
                if len(lst) > 1 and len({tuple(x[0][0]) for x in lst}) > 1:
                    # mai multe intervale (ex. MPPT la putere plină): cel mai larg = funcționare MPPT
                    toate = [v for x in lst for v in x[0]]
                    iv = (min(v[0] for v in toate), max(v[1] for v in toate))
                    sc = 2
                campuri["MPPT_min_V"] = {"valoare": iv[0], "incredere": NIVEL[sc], "sursa": src}
                campuri["MPPT_max_V"] = {"valoare": iv[1], "incredere": NIVEL[sc], "sursa": src}
                continue
            if len(vals) == n_var:
                v = vals[k]
            elif len(vals) == 1:
                v = vals[0]
            else:
                v = vals[min(k, len(vals) - 1)]
                sc = min(sc, 2)
            if len({x[0][0] if len(x[0]) == 1 else None for x in lst2 if x[3] == sec and x[4] == lst2[0][4]}) > 1:
                sc = min(sc, 2)          # mai multe rânduri cu valori diferite pentru același câmp
            if camp in ("kWh", "kWh_util", "P_kW", "Pn_kW") and len(vals) > n_var:
                v = vals[0]
            campuri[camp] = {"valoare": v if isinstance(v, tuple) else _rot(v), "incredere": NIVEL[sc], "sursa": src}
        for camp, c_ in list(campuri.items()):          # coeficient în mV/K → %/K, cu Voc al aceleiași variante
            if isinstance(c_["valoare"], tuple):
                voc = (campuri.get("Voc_V") or {}).get("valoare")
                if voc:
                    c_["valoare"] = _rot(c_["valoare"][1] / voc * 100.0)
                    c_["incredere"] = NIVEL[2]
                else:
                    del campuri[camp]
        if tip == "bess" and "kWh" not in campuri and "kWh_util" in campuri:
            campuri["kWh"] = dict(campuri["kWh_util"], incredere=NIVEL[2], sursa=campuri["kWh_util"]["sursa"] + " (capacitatea utilă)")
        _verifica(tip, campuri, avert if k == 0 else [])
        model = modele[k] if len(modele) == n_var else (modele[0] if modele else "")
        if model and n_var > 1 and len(modele) != n_var and campuri.get("Pmax_W"):
            model = f"{model} {fmt(campuri['Pmax_W']['valoare'])} W"
        eti = model or (f"{fmt(campuri['Pmax_W']['valoare'])} W" if "Pmax_W" in campuri else
                        f"{fmt(campuri['Pn_kW']['valoare'])} kW" if "Pn_kW" in campuri else
                        f"{fmt(campuri['kWh']['valoare'])} kWh" if "kWh" in campuri else f"varianta {k + 1}")
        variante.append({"eticheta": eti, "model": model, "campuri": campuri})
    if tip == "invertor":
        tl = t.lower()
        retea = "tri" if re.search(r"3\s*/\s*n\s*/\s*pe|3w\s*\+\s*n|three[- ]phase|trifazat|3[- ]phase|3\s*~|3\s*x\s*(230|400)|400\s*v\s*/\s*230|230\s*/\s*400", tl) else \
            "mono" if re.search(r"single[- ]phase|monofazat|1\s*/\s*n\s*/\s*pe|1[- ]phase|l\s*/\s*n\s*/\s*pe|1\s*~", tl) else None
        hib = bool(re.search(r"hybrid|hibrid|battery\s*(input|port|voltage)|baterie", tl))
        for v in variante:
            if retea:
                v["campuri"]["retea"] = {"valoare": retea, "incredere": NIVEL[2], "sursa": "detectat din text"}
            if hib:
                v["campuri"]["hibrid"] = {"valoare": True, "incredere": NIVEL[1], "sursa": "detectat din text"}
    if tip == "bess":
        m = re.search(r"lifepo4|\blfp\b|lithium iron phosphate|\bnmc\b|li-?ion", t, re.I)
        if m:
            ch = {"lfp": "LiFePO₄", "lifepo4": "LiFePO₄", "lithium iron phosphate": "LiFePO₄", "nmc": "NMC"}.get(m.group(0).lower(), "Li-ion")
            for v in variante:
                v["campuri"]["chimie"] = {"valoare": ch, "incredere": NIVEL[3], "sursa": m.group(0)}
    if not any(v["campuri"] for v in variante):
        avert.append("Nu am găsit date tehnice în text — fișa poate fi scanată (imagine). Completează valorile manual.")
    if n_var > 1:
        avert.append(f"Fișa are {n_var} variante (coloane) — alege varianta folosită în proiect.")
    implicit = 0
    if n_var > 2:
        implicit = n_var // 2
    return {"tip": tip, "tip_scor": scor, "producator": prod, "variante": variante, "implicit": implicit,
            "avertismente": avert}


def _rot(v):
    if isinstance(v, float):
        r = round(v, 4)
        return int(r) if r == int(r) else r
    return v


def fmt(v):
    if isinstance(v, float):
        return f"{v:g}".replace(".", ",")
    return str(v)


def _verifica(tip, c, avert):
    """plauzibilitate (domenii) + coerență (Vmpp < Voc, Impp < Isc, Pmax ≈ Vmpp·Impp, MPPT ≤ Umax); coboară încrederea"""
    def val(k):
        return c[k]["valoare"] if k in c else None
    if tip == "modul_pv" and "beta_Voc_pct_K" in c and val("beta_Voc_pct_K") is not None and abs(val("beta_Voc_pct_K")) > 1 and val("Voc_V"):
        # dat în mV/K fără unitate recunoscută
        c["beta_Voc_pct_K"]["valoare"] = _rot(val("beta_Voc_pct_K") / 1000.0 / val("Voc_V") * 100.0)
        c["beta_Voc_pct_K"]["incredere"] = NIVEL[1]
    for k, (et, um, (lo, hi)) in CAMPURI.get(tip, {}).items():
        v = val(k)
        if v is None:
            continue
        if not (lo <= v <= hi):
            c[k]["incredere"] = NIVEL[1]
            avert.append(f"{et} = {fmt(v)} {um} pare neplauzibil — verifică în fișă.")
    if tip == "modul_pv":
        if val("Vmpp_V") and val("Voc_V") and val("Vmpp_V") >= val("Voc_V"):
            for k in ("Vmpp_V", "Voc_V"):
                c[k]["incredere"] = NIVEL[1]
            avert.append("Vmpp ≥ Voc — valorile par inversate.")
        if val("Impp_A") and val("Isc_A") and val("Impp_A") >= val("Isc_A"):
            for k in ("Impp_A", "Isc_A"):
                c[k]["incredere"] = NIVEL[1]
            avert.append("Impp ≥ Isc — valorile par inversate.")
        if val("Pmax_W") and val("Vmpp_V") and val("Impp_A"):
            p = val("Vmpp_V") * val("Impp_A")
            if abs(p - val("Pmax_W")) > 0.04 * val("Pmax_W"):
                avert.append(f"Vmpp·Impp = {fmt(round(p, 1))} W ≠ Pmax {fmt(val('Pmax_W'))} W — verifică coloana / rândul.")
                for k in ("Pmax_W", "Vmpp_V", "Impp_A"):
                    c[k]["incredere"] = NIVEL[min(2, _niv(c[k]["incredere"]))]
    if tip == "invertor":
        if val("MPPT_max_V") and val("Umax_dc_V") and val("MPPT_max_V") > val("Umax_dc_V"):
            avert.append("MPPT max > Umax c.c. — verifică intervalul MPPT.")
            c["MPPT_max_V"]["incredere"] = NIVEL[1]
        if val("Pn_kW") and val("Iac_max_A"):
            i_min = val("Pn_kW") * 1000 / (3 ** 0.5 * 400)
            if val("Iac_max_A") < 0.98 * i_min and val("Iac_max_A") * 3 < val("Pn_kW") * 1000 / 230 * 0.98 * 3:
                if val("Iac_max_A") < 0.98 * val("Pn_kW") * 1000 / 230 and val("Iac_max_A") < 0.98 * i_min:
                    avert.append("Iac,max < Pn/(√3·400) — verifică (poate e curentul pe fază al altei variante).")
                    c["Iac_max_A"]["incredere"] = NIVEL[1]


def _niv(s):
    return {v: k for k, v in NIVEL.items()}.get(s, 1)


def importa_fisa(data, tip=None, motor=None):
    """corpul cererii (PDF sau text simplu) → propunerea de echipament (vezi `extrage`) + textul extras"""
    if data[:1024].lstrip().startswith(b"%PDF") or b"%PDF-" in data[:1024]:
        text, mot = pdftext.text_din_pdf(data, motor=motor)
    else:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("fișierul nu e PDF și nici text — încarcă fișa tehnică PDF a echipamentului")
        mot = "text"
    r = extrage(text, tip)
    r["motor"] = mot
    r["text"] = text[:20000]
    r["caractere"] = len(re.sub(r"\s", "", text))
    if r["caractere"] < 40:
        r["avertismente"].insert(0, "PDF-ul nu conține text (fișă scanată?) — completează valorile manual sau lipește textul fișei.")
    return r


# ------------------------------------------------------------------------------------------------ rafinare cu Claude
def claude_disponibil():
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
                or os.path.exists(os.path.expanduser("~/.config/anthropic")))


def rafineaza_claude(text, tip=None):
    """Structurarea textului fișei cu Claude (opțional). Întoarce aceeași formă ca `extrage`, cu motor „claude”."""
    if not claude_disponibil():
        raise ValueError("Claude nu este disponibil (lipsește SDK-ul anthropic sau cheia API)")
    import anthropic
    tip_d = ALIAS_TIP.get(tip, tip) if tip else detecteaza_tip(_norm_text(text))[0]
    chei = ", ".join(f"{k} [{v[1]}]" for k, v in CAMPURI.get(tip_d, {}).items())
    sistem = ("Extragi datele tehnice dintr-o fișă de echipament fotovoltaic / stocare. Întorci STRICT JSON: "
              '{"tip": "' + tip_d + '", "producator": "...", "variante": [{"model": "...", "campuri": {cheie: număr}}]}. '
              f"Chei permise: {chei}" + (", retea (tri|mono), hibrid (bool)" if tip_d == "invertor" else "") +
              ". O variantă pentru fiecare coloană de putere / model din fișă. Unitățile sunt cele din paranteze "
              "(convertește). Coeficienții de temperatură în %/K (negativi pentru Voc și Pmax). Omite ce nu e în text; "
              "nu inventa valori.")
    client = anthropic.Anthropic()
    msg = client.messages.create(model="claude-opus-5-5", max_tokens=4000, system=sistem,
                                 messages=[{"role": "user", "content": text[:60000]}])
    txt = "".join(b.text for b in msg.content if b.type == "text")
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise ValueError("răspunsul Claude nu conține JSON")
    d = json.loads(m.group(0))
    avert = []
    variante = []
    for v in d.get("variante") or []:
        c = {}
        for k, x in (v.get("campuri") or {}).items():
            if k in CAMPURI.get(tip_d, {}) and isinstance(x, (int, float)) and not isinstance(x, bool):
                c[k] = {"valoare": _rot(float(x)), "incredere": NIVEL[2], "sursa": "Claude"}
            elif k in ("retea", "hibrid", "chimie"):
                c[k] = {"valoare": x, "incredere": NIVEL[2], "sursa": "Claude"}
        _verifica(tip_d, c, avert if not variante else [])
        variante.append({"eticheta": v.get("model") or f"varianta {len(variante) + 1}", "model": v.get("model") or "", "campuri": c})
    return {"tip": tip_d, "producator": d.get("producator") or _producator(text), "variante": variante or [{"eticheta": "—", "model": "", "campuri": {}}],
            "implicit": 0, "avertismente": avert, "motor": "claude"}
