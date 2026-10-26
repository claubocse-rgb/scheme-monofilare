"""Schema intrării fizice pentru interpretorul cu Claude (SPEC_TEHNIC.md §F.9) — GENERATĂ, nu scrisă de mână.

Sursa cheilor (inventarul, `interp_schema_inventar.py`) se regenerează cu

    python3 -m engine.interp_schema --genereaza

din trei surse care descriu ce acceptă motorul AZI:
  1. intrările cazurilor golden (tests/date/cazuri_golden.json → `intrare`);
  2. cheile emise de interpretorul local pe tot corpusul de fraze (tests/date/fraze_chat.json, teste/r*/…/fraze*.json);
  3. cheile citite de motor din intrare (`inp.get("…")` în engine/calc/scheme.py, locuinta.py, constructor.py).

Tipurile vin din motor: `CAMPURI_NUMERICE` (număr, domeniu, întreg), `ENUMERARI` (valori canonice), plus mulțimile
de valori ale interpretorului (`_CHEI_TEXT`, receptorii locuinței, fazele) și tipurile observate în inventar.

Aceeași schemă e folosită de:
  * promptul / unealta `intrare_fizica` trimisă lui Claude (`unealta()`, `rezumat_chei()`);
  * `valideaza()` — validarea de formă a răspunsului (interpretor.valideaza_forma);
  * `curata()` — păstrează doar cheile cunoscute cu tipuri corecte (interpretor.normalizeaza_intrare).
"""
from __future__ import annotations

import json
import math
import pathlib
import re

try:
    from .calc import scheme as _sch
    from .calc import norme
except ImportError:  # rulare ca script
    from engine.calc import scheme as _sch  # type: ignore
    from engine.calc import norme  # type: ignore

try:
    from .interp_schema_inventar import INVENTAR
except ImportError:  # inventarul încă negenerat
    try:
        from engine.interp_schema_inventar import INVENTAR  # type: ignore
    except ImportError:
        INVENTAR = {}

TIPURI = ("bransament", "tablou", "cef", "pt", "prosumator", "ge_ats", "locuinta")
RECEPTORI_LOCUINTA = ("iluminat", "prize", "prize_bucatarie", "prize_baie", "prize_exterior", "masina_spalat_rufe",
                      "masina_spalat_vase", "uscator", "boiler", "cuptor", "plita", "aer_conditionat", "pompa_caldura",
                      "centrala_termica", "incalzire_electrica", "vehicul_electric", "pompa_apa", "poarta_automata",
                      "sauna", "alt_circuit")

# enumerări pe cale (au prioritate față de numele cheii: receptorul locuinței ≠ receptorul unei plecări)
ENUM_CALE = {
    "tip_schema": list(TIPURI),
    "circuite[].receptor": list(RECEPTORI_LOCUINTA),
    "circuite[].faza": ["L1", "L2", "L3", "3F"],
    "invertoare[].faza": ["L1", "L2", "L3"],
    "bess.cuplaj": ["cc", "ca"],
    "schema_pamant": ["TN-C-S", "TN-S", "TT", "TN-C", "IT"],
    "alimentare.tip": ["bransament_existent", "bransament_nou"],
    "masura": ["MT", "JT"], "masura_pt": ["MT", "JT"],
    "cupla": ["inchisa", "deschisa"], "comutare": ["manual", "ATS"],
    "celula_trafo": ["sigurante", "intreruptor"],
    "bmpt_fortat": list(norme.BMPT),
    "pornire": ["directa", "stea_triunghi", "convertizor", "soft"], "curba": ["B", "C", "D"],
    "prot_tip": sorted(_sch.TIPURI_PROT),
    "material": ["Cu", "Al"], "izolatie": ["PVC", "XLPE"], "metoda": list(norme.METODE_POZARE),
}
# numerice în afara CAMPURI_NUMERICE ale motorului (condiție ca acolo)
NUMERICE_EXTRA = {"n_trafo": "int>=1", "n_pcs": "int>=1", "U_MT_kV": ">0", "compensare_kvar": ">0", "compensare_L_m": ">0", "U_V": ">0",
                  "U_ca_V": ">0", "U_inv_ca_V": ">0", "U_JT_V": ">0", "In_Q_amonte_A": ">0", "sectie": "int>=1"}
_DOAR_NIVEL_1 = {"P_kW"}                    # descrierea generală a cheii nu se aplică în obiectele imbricate
# cheile găsite doar în codul motorului, fără tip deductibil din CAMPURI_NUMERICE / ENUMERARI
TIP_EXPLICIT = {"ddr_amonte": "boolean", "excitatie_sustinuta": "boolean", "comercial": "boolean", "PI_externa": "boolean", "DDR_GE": "boolean",
                "plecari_pe_semibara": "boolean", "ATS_interblocaj": "string", "Q_general_tip": "string",
                "Zb_OD_ohm": "number", "Zb_TG_ohm": "number"}
# tipuri pe cale pe care corpusul nu le arată, dar motorul le acceptă (scheme._n_rezerva: „1+1” = activ + rezervă)
TIP_CALE = {"consumatori[].n": {"type": ["integer", "string"], "description": "bucăți; „1+1” / „2+1” = activ + rezervă"}}
CAI_MOTOR = {"bess.n_pcs": "number", "bess.pcs.n": "number", "bess.pcs.Pn_kW": "number", "bess.pcs.producator": "string",
             "bess.pcs.model": "string", "tablouri_secundare[].cablu.S_fortat": "number",
             "tablouri_secundare[].cablu.material": "string", "tablouri_secundare[].cablu.n_fortat": "number",
             "invertoare[].U_ca_V": "number", "bess.n_module": "number", "bess.kWh_modul": "number",
             "invertoare[].faza": "string", "invertoare[].sectie": "number", "Ik3_bara_kA": "number"}
NUMERICE_EXTRA_INT = {"n_pcs"}
TIP_EXPLICIT_PLECARE = {"siguranta": "boolean", "rezerva": "boolean"}
EXCLUSE_PLECARE = {"DDR", "ddr", "blocat", "nivel", "copii"}
# chei interne / de dimensionare pe care modelul NU le completează (le produce motorul sau interfața)
EXCLUSE = {"note", "parametri", "aparate", "Q1_DDR", "spd_cc", "gpv", "invertor_baterie", "ge_rezerva",
           "dU_origine_pct", "Iac_max_A", "Pn_total_kW", "Ucpv_V", "Q1_tip", "racord_Q_tip"}

# descrieri scurte (sensul de domeniu); cheile fără descriere primesc doar tipurile la care apar
DESCRIERI = {
    "tip_schema": "tipul schemei: bransament (BMPM/BMPT), tablou (TG/TD), cef (centrală PV / BESS, cu invertoare), "
                  "pt (post de transformare cu TGJT), prosumator (invertor pe branșamentul unui consumator), ge_ats "
                  "(grup electrogen + ATS), locuinta (tabloul unei case / apartament)",
    "retea": "mono (230 V) sau tri (3 × 400 V) — DOAR dacă textul o spune; nu se presupune",
    "schema_pamant": "schema de legare la pământ declarată (TN-C-S, TN-S, TT, TN-C, IT)",
    "RA_ohm": "rezistența prizei de pământ declarată (Ω)",
    "P_kW": "puterea declarată (kW): branșament = puterea aprobată/absorbită; tablou = puterea tabloului",
    "Ib_A": "branșament dat în amperi (curent maxim absorbit)",
    "S_kVA": "branșament dat în kVA",
    "L_coloana_m": "lungimea coloanei / cablului de la BMPT la tablou (m)",
    "L_alimentare_m": "lungimea cablului de alimentare al tabloului (m)",
    "In_Q1_A": "calibrul întreruptorului general Q1 al tabloului (A), dacă e dat",
    "origine": "de unde e alimentat tabloul: pt_propriu, tg_existent, bmpt, retea_publica",
    "pt_Sn_kVA": "puterea trafo-ului din amonte (PT propriu / existent), kVA",
    "Sn_kVA": "puterea transformatorului postului (schema pt), kVA",
    "n_trafo": "numărul de transformatoare (2 = două trafo identice, cuplă)",
    "kWp": "puterea de vârf a câmpului PV (c.c.), kWp — NU puterea invertoarelor",
    "invertoare": "grupuri de invertoare (CEF): un element per model/putere; n = bucăți, Pn_kW = puterea UNUI invertor",
    "invertoare[].n": "câte invertoare identice în grup",
    "invertoare[].Pn_kW": "puterea nominală c.a. a UNUI invertor (kW)",
    "Pn_inv_kW": "prosumator: puterea c.a. totală a invertorului (kW)",
    "P_aprobata_kW": "puterea aprobată pentru consum, din ATR / certificat (kW)",
    "P_evacuata_kW": "puterea aprobată pentru evacuare / injecție, din ATR (kW)",
    "limitare_injectie_kW": "limitarea injecției în rețea (kW); 0 = injecție zero",
    "In_Q_bransament_A": "calibrul protecției branșamentului existent / BMPT (A)",
    "racord": "unde se racordează centrala: tg_existent, bmpt, pt",
    "bess": "stocare: P_kW (putere PCS), kWh (energie), cuplaj cc/ca, producator, model",
    "Sn_GE_kVA": "puterea grupului electrogen (kVA)",
    "P_sarcina_kW": "sarcina preluată de GE (kW)",
    "consumatori": "consumatorii alimentați din GE / ATS; siguranta = true pentru consumatori de siguranță la incendiu",
    "consumatori[].siguranta": "true = consumator de siguranță la incendiu (pompă incendiu, hidranți, sprinklere, desfumare)",
    "siguranta_tablou": "true = tabloul întreg alimentează consumatori de siguranță la incendiu",
    "plecari": "plecările tabloului: nume + In_A (calibru dat) SAU P_kW (putere dată), L_m, n_circuite, copii (cascadă)",
    "plecari[].n_circuite": "„6 circuite iluminat 16 A” = o plecare cu n_circuite 6",
    "alimentare": "locuință: tipul branșamentului, P aprobată, Q branșament, lungimea coloanei",
    "circuite": "locuință: circuitele tabloului casei (nume, receptor, P_kW, L_m, faza)",
    "circuite[].faza": "L1/L2/L3 pentru circuit monofazat pe o fază declarată, 3F pentru receptor trifazat",
    "tablouri_secundare": "locuință: tablouri secundare (etaj, garaj, anexă) cu L_m și circuitele lor",
    "cablu": "cablu impus de text: material, izolatie, metoda (C, D1, D2, E), S_fortat/N_fortat/n_fortat („3x150+70”)",
    "modul": "modulul PV: producator, model, Pmax_W",
    "string": "configurația stringurilor: n_module pe string, n_stringuri_paralel, n_MPPT, Uoc_V, Isc_A",
    "compensare_kvar": "baterie de condensatoare (kvar)",
    "U_MT_kV": "tensiunea MT a postului (6, 10, 15, 20 kV)",
    "atr_jt": "true = ATR-ul prevede racord JT (peste pragul uzual)",
    "pt_existent": "true = PT-ul din amonte e existent (nu se proiectează)",
    "ge_paralel": "true = GE în paralel cu rețeaua (sincronizare), nu ATS",
    "masura_ceruta": "măsura cerută explicit (directa / semidirecta)",
    "cosfi": "factorul de putere declarat",
    "plecari[].siguranta": "true = consumator de siguranță la incendiu (fără DDR, cablu rezistent la foc)",
    "plecari[].rezerva": "true = unitate de rezervă (ex. pompa de rezervă) — desenată, dar neadunată la bilanț",
    "plecari[].sectie": "PT cu 2 trafo: secția de bare (semibara) 1 sau 2 a plecării",
    "celule_mt": "celulele MT declarate, în ordine: linie / linie_intrare / linie_iesire / masura / trafo",
    "racord_In_Q_A": "CEF în TG existent: calibrul protecției existente din TG pe care se leagă centrala (A)",
    "Ik3_TG_kA": "Ik3 declarat la bara TG / bara JT în care se racordează (kA)",
    "Ik3_OD_kA": "Ik3 max declarat de OD la punctul de delimitare (kA, din ATR)",
    "Zb_OD_ohm": "impedanța buclei / Zs declarată de OD (Ω, din ATR)",
    "In_Q_amonte_A": "calibrul întreruptorului din amonte care alimentează tabloul (A)",
    "In_Q_JT_A": "întreruptorul general JT al postului (A), dacă e dat",
    "U_ca_V": "tensiunea c.a. a invertoarelor dacă nu e 400 V (ex. 800)",
    "U_MT_kV": "tensiunea MT a postului (6, 10, 15, 20 kV)",
    "n_fortat": "număr de cabluri identice în paralel (cablu impus)",
    "n_paralel": "număr de cabluri identice în paralel (cablu impus)",
    "cupla": "PT cu 2 trafo: cupla longitudinală JT inchisa / deschisa",
    "titlu_tablou": "numele tabloului așa cum e scris (ex. TE desfumare, TDSI sprinklere)",
    "sursa_retea": "GE + ATS: de unde vine alimentarea normală — bmpt, pt, tgd (TG/TGD existent)",
    "trafo_izolatie": "ulei / uscat",
    "compensare_kvar": "baterie de condensatoare declarată (kvar) — nu o dimensiona tu",
    "bess.n_pcs": "numărul de PCS-uri identice („4 x PCS 250 kW” = 4); P_kW rămâne puterea totală",
    "ddr_amonte": "false = sursa tabloului NU are DDR în amonte (ex. alimentare de siguranță din TG înainte de DDR); "
                  "true = există DDR în amonte — doar dacă textul o spune",
    "comutare": "GE: manual (inversor manual) sau ATS (automat)",
    "pt_aerian": "true = post de transformare aerian (pe stâlp)",
    "bess.n_module": "numărul de module de baterie („4 x Pylontech US5000” = 4)",
    "bess.kWh_modul": "capacitatea unui modul de baterie (kWh), dacă e scrisă",
    "invertoare[].faza": "invertor MONOFAZAT într-un sistem trifazat: faza pe care e conectat (L1/L2/L3)",
    "invertoare[].sectie": "CEF cu 2 trafo: secția de bare JT (1 / 2) a grupului",
    "Ik3_bara_kA": "Ik3 declarat la bara de racord (kA)",
    "bess.pcs": "PCS-ul (invertorul bateriei) dacă e numit: n, Pn_kW pe bucată, producator, model",
    "tablouri_secundare[].cablu": "cablul impus al tabloului secundar („3x6” = S_fortat 6)",
}
_CHEI_TEXT_INTERP: dict = {}      # completat la primul apel (interpretorul importă acest modul)
_PREFIX_CUPLARE = ("plecari[]", "tablouri_secundare[].circuite[]")       # copii = aceeași formă ca plecarea


# =====================================================================================================
# Generarea inventarului
# =====================================================================================================
def _cai(o, p, out, tip):
    if isinstance(o, dict):
        for k, v in o.items():
            if not isinstance(k, str) or k.startswith("_"):
                continue
            _cai(v, f"{p}.{k}" if p else k, out, tip)
    elif isinstance(o, list):
        if o and all(isinstance(x, dict) for x in o):
            for x in o:
                _cai(x, p + "[]", out, tip)
        else:
            e = out.setdefault(p, {"t": set(), "v": set(), "tipuri": set()})
            e["t"].add("array")
            e["tipuri"].add(tip)
    else:
        e = out.setdefault(p, {"t": set(), "v": set(), "tipuri": set()})
        e["t"].add({bool: "boolean", int: "number", float: "number", str: "string"}.get(type(o), "null"))
        if isinstance(o, str) and len(e["v"]) < 16:
            e["v"].add(o)
        if tip:
            e["tipuri"].add(tip)


def _colapseaza(cale: str) -> str:
    """„plecari[].copii[].copii[].nume” → „plecari[].nume” (cascada are aceeași formă ca plecarea)."""
    while ".copii[]" in cale:
        cale = cale.replace(".copii[]", "", 1)
    return cale


def genereaza_inventar(radacina=None) -> dict:
    from engine import interpretor as it  # import târziu (interpretorul importă acest modul)
    rad = pathlib.Path(radacina or pathlib.Path(__file__).resolve().parents[1])
    out: dict = {}
    gold = json.loads((rad / "tests/date/cazuri_golden.json").read_text(encoding="utf-8"))
    for c in gold.get("cazuri", []):
        intr = c.get("intrare")
        if isinstance(intr, dict) and intr.get("tip_schema") in TIPURI:
            _cai(intr, "", out, intr["tip_schema"])
    fisiere = [rad / "tests/date/fraze_chat.json"] + sorted(rad.glob("teste/**/fraze*.json"))
    texte = []
    for f in fisiere:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for x in (d.get("fraze") if isinstance(d, dict) else d) or []:
            t = x.get("text") or x.get("fraza") if isinstance(x, dict) else None
            if isinstance(t, str):
                texte.append(t)
    for t in dict.fromkeys(texte):
        try:
            r = it.interpreteaza_local(t)
        except Exception:  # noqa: BLE001 — o frază care pică nu oprește inventarul
            continue
        intr = r.get("intrare_fizica") or {}
        _cai(intr, "", out, intr.get("tip_schema"))
    rx = re.compile(r'inp\.get\("([A-Za-z]\w*)"|inp\["([A-Za-z]\w*)"\]')
    for f in ("engine/calc/scheme.py", "engine/calc/locuinta.py", "engine/constructor.py"):
        for m in rx.finditer((rad / f).read_text(encoding="utf-8")):
            k = m.group(1) or m.group(2)
            if k not in out and k not in EXCLUSE and (k in _sch.CAMPURI_NUMERICE or k in _sch.ENUMERARI or k in TIP_EXPLICIT):
                out[k] = {"t": {TIP_EXPLICIT.get(k, "number" if k in _sch.CAMPURI_NUMERICE else "string")},
                          "v": set(), "tipuri": set()}
    # cheile plecării citite de motor (`pl.get("…")`): siguranța / rezerva pe consumator (r8), ks, S_kVA …
    rxp = re.compile(r'\bpl\.get\("([A-Za-z]\w*)"')
    for f in ("engine/calc/scheme.py", "engine/calc/ramura.py", "engine/constructor.py"):
        for m in rxp.finditer((rad / f).read_text(encoding="utf-8")):
            k = m.group(1)
            cale = "plecari[]." + k
            if cale in out or k in EXCLUSE_PLECARE:
                continue
            t = TIP_EXPLICIT_PLECARE.get(k) or ("number" if k in _sch.CAMPURI_NUMERICE else
                                                "string" if k in _sch.ENUMERARI else None)
            if t:
                out[cale] = {"t": {t}, "v": set(), "tipuri": {"tablou", "pt"}}
    # căi citite de motor pe obiecte imbricate, pe care corpusul nu le arată (PCS-urile BESS, cablul TD-ului casei)
    for cale, t in CAI_MOTOR.items():
        out.setdefault(cale, {"t": {t}, "v": set(), "tipuri": set()})
    # cheile de nivel 1 acceptate de normalizarea interpretorului (aceeași formă ca ieșirea locală)
    for multime, t in ((it._CHEI_NUMERICE, "number"), (it._CHEI_BOOL, "boolean"), (it._CHEI_TEXT, "string")):
        for k in multime:
            if k not in out and k not in EXCLUSE:
                out[k] = {"t": {t}, "v": set(it._CHEI_TEXT.get(k) or ()) if t == "string" else set(), "tipuri": set()}
    rez = {}
    for cale, e in out.items():
        cale = _colapseaza(cale)
        if not cale or cale.split(".")[0].split("[")[0] in EXCLUSE:
            continue
        r = rez.setdefault(cale, {"t": set(), "v": set(), "tipuri": set()})
        r["t"] |= e["t"] - {"null"}
        r["v"] |= e["v"]
        r["tipuri"] |= {x for x in e["tipuri"] if x}
    return {c: {"t": sorted(e["t"]), "v": sorted(e["v"])[:16], "tipuri": sorted(e["tipuri"])}
            for c, e in sorted(rez.items()) if e["t"]}


def scrie_inventar(radacina=None) -> pathlib.Path:
    inv = genereaza_inventar(radacina)
    f = pathlib.Path(__file__).with_name("interp_schema_inventar.py")
    f.write_text('"""GENERAT de `python3 -m engine.interp_schema --genereaza` — nu se editează de mână.\n'
                 'Cale (a.b[].c) → tipuri JSON observate, valori text observate, tipurile de schemă la care apare."""\n'
                 "INVENTAR = " + json.dumps(inv, ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    return f


# =====================================================================================================
# Schema JSON
# =====================================================================================================
def _cheie(cale: str) -> str:
    return cale.split(".")[-1].replace("[]", "")


def _frunza(cale: str, info: dict) -> dict:
    if cale in TIP_CALE:
        return dict(TIP_CALE[cale])
    k = _cheie(cale)
    t = set(info.get("t") or [])
    s: dict
    enum = ENUM_CALE.get(cale)
    if enum is None and "." not in k:                       # cheile ENUM_CALE fără „.” se aplică după nume
        enum = next((v for kk, v in ENUM_CALE.items() if "." not in kk and "[" not in kk and kk == k), None)
    if k == "retea":
        enum = ["mono", "tri"]
    if enum is None and "." not in cale and "[" not in cale and _CHEI_TEXT_INTERP.get(k):
        enum = sorted(_CHEI_TEXT_INTERP[k])
    if enum is None and k in _sch.ENUMERARI and "boolean" not in t:
        enum = sorted(set(_sch.ENUMERARI[k].values()))
    if enum is not None:
        s = {"type": "string", "enum": list(enum)}
    elif (k in _sch.CAMPURI_NUMERICE or k in NUMERICE_EXTRA) and "boolean" not in t:
        cond = _sch.CAMPURI_NUMERICE[k][0] if k in _sch.CAMPURI_NUMERICE else NUMERICE_EXTRA[k]
        s = {"type": "integer" if cond.startswith("int") else "number"}
        if cond in (">0",):
            s["exclusiveMinimum"] = 0
        elif cond in (">=0", "int>=0"):
            s["minimum"] = 0
        elif cond == "int>=1":
            s["minimum"] = 1
        elif cond == "(0,1]":
            s.update(exclusiveMinimum=0, maximum=1)
        elif cond == "[0,100]":
            s.update(minimum=0, maximum=100)
        if "string" in t:                                   # ex. consumatori[].n „1+1” (activ + rezervă)
            s = {"type": [s["type"], "string"]}
    elif t == {"boolean"}:
        s = {"type": "boolean"}
    elif t == {"array"}:
        s = {"type": "array", "items": {"type": "string"}}
        if cale == "celule_mt":
            s["items"]["enum"] = ["linie", "linie_intrare", "linie_iesire", "masura", "trafo"]
    elif t <= {"number"}:
        s = {"type": "number"}
    elif "string" in t:
        s = {"type": "string"} if t == {"string"} else {"type": sorted({"string"} | ({"number"} & t) | ({"boolean"} & t))}
    else:
        s = {"type": sorted(t)[0]}
    d = DESCRIERI.get(cale) or (DESCRIERI.get(k) if "." not in cale or k not in _DOAR_NIVEL_1 else None)
    tip = info.get("tipuri") or []
    if d or tip:
        s["description"] = (d or "") + (f" [{', '.join(tip)}]" if tip and len(tip) < len(TIPURI) else "")
        s["description"] = s["description"].strip()
    return s


def _arbore(inventar: dict) -> dict:
    """Căile plate → arbore {cheie: {"_frunza": info} | {"_lista": bool, "_copii": {...}}}."""
    rad: dict = {}
    for cale, info in inventar.items():
        parti = cale.split(".")
        nod = rad
        acc = []
        for i, p in enumerate(parti):
            lista = p.endswith("[]")
            k = p[:-2] if lista else p
            acc.append(p)
            n = nod.setdefault(k, {"_cale": ".".join(acc)})
            if i == len(parti) - 1:
                if lista:   # listă de obiecte fără câmpuri observate — rar; o tratăm ca listă de text
                    n["_frunza"] = dict(info, t=["array"])
                else:
                    n["_frunza"] = info
            else:
                n["_lista"] = n.get("_lista") or lista
                n.setdefault("_copii", {})
                nod = n["_copii"]
    return rad


def _fara_eticheta(s):
    """plecarea e comună (tablou, PT, TD-urile locuinței): fără eticheta „[tipuri]” din descriere."""
    if isinstance(s, dict):
        s = {k: _fara_eticheta(v) for k, v in s.items()}
        if isinstance(s.get("description"), str):
            s["description"] = re.sub(r"\s*\[[a-z_, ]+\]$", "", s["description"])
            if not s["description"]:
                s.pop("description")
    return s


def _schema_nod(k: str, n: dict, defs: dict) -> dict:
    cale = n["_cale"].replace("[]", "")
    if "_copii" in n:
        props = {kk: _schema_nod(kk, nn, defs) for kk, nn in sorted(n["_copii"].items())}
        if n["_cale"].rstrip("[]") + "[]" in _PREFIX_CUPLARE and n.get("_lista"):
            props["copii"] = {"type": "array", "items": {"$ref": "#/$defs/plecare"},
                              "description": "sub-plecări (cascadă), aceeași formă"}
            props = {kk: _fara_eticheta(v) for kk, v in props.items()}
            prec = defs.get("plecare", {}).get("properties", {})
            defs["plecare"] = {"type": "object", "properties": dict(prec, **props), "required": ["nume"]}
            o = {"type": "array", "items": {"$ref": "#/$defs/plecare"}}
        else:
            ob = {"type": "object", "properties": props}
            o = {"type": "array", "items": ob} if n.get("_lista") else ob
        d = DESCRIERI.get(n["_cale"].replace("[]", "")) or DESCRIERI.get(k)
        if d:
            o["description"] = d
        return o
    return _frunza(n["_cale"], n["_frunza"])


def schema_intrare(inventar: dict | None = None) -> dict:
    """JSON Schema a `intrare_fizica` (toate tipurile de schemă)."""
    if not _CHEI_TEXT_INTERP:
        try:
            from . import interpretor as _it
        except ImportError:
            from engine import interpretor as _it  # type: ignore
        _CHEI_TEXT_INTERP.update({k: v for k, v in _it._CHEI_TEXT.items() if v})
    inv = INVENTAR if inventar is None else inventar
    defs: dict = {}
    arb = _arbore(inv)
    props = {k: _schema_nod(k, n, defs) for k, n in sorted(arb.items())}
    props["tip_schema"] = _frunza("tip_schema", {"t": ["string"]})
    s = {"type": "object", "properties": props, "required": ["tip_schema"]}
    if defs:
        s["$defs"] = defs
    return s


def schema_unealta() -> dict:
    """input_schema a uneltei `intrare_fizica`: intrarea + cartușul + întrebările și ce nu s-a înțeles."""
    si = schema_intrare()
    defs = si.pop("$defs", {})
    s = {
        "type": "object",
        "properties": {
            "intrare_fizica": si,
            "cartus": {"type": "object", "description": "date de cartuș, doar dacă apar în text",
                       "properties": {"beneficiar": {"type": "string"}, "localitate": {"type": "string"},
                                      "judet": {"type": "string"}, "plansa": {"type": "string"},
                                      "faza": {"type": "string"}}},
            "intrebari": {"type": "array", "items": {"type": "string"},
                          "description": "ambiguități / contradicții de clarificat cu proiectantul — completează-le "
                                         "în loc să ghicești (o întrebare scurtă, cu variantele posibile)"},
            "neinteles": {"type": "array", "items": {"type": "string"},
                          "description": "fragmente din text (citate scurte) pe care nu le-ai putut pune în intrare"},
        },
        "required": ["intrare_fizica", "intrebari", "neinteles"],
    }
    if defs:
        s["$defs"] = defs
    return s


def unealta() -> dict:
    return {"name": "intrare_fizica",
            "description": "Întoarce intrarea fizică citită din descrierea proiectantului (fără dimensionare), "
                           "plus întrebările pentru ce e ambiguu și fragmentele neînțelese.",
            "input_schema": schema_unealta()}


def rezumat_chei() -> str:
    """Lista compactă a cheilor de nivel 1 pe tip de schemă (pentru promptul de sistem)."""
    pe_tip: dict = {t: [] for t in TIPURI}
    gen = []
    for cale, info in INVENTAR.items():
        k = cale.split(".")[0].replace("[]", "")
        tipuri = info.get("tipuri") or []
        if not tipuri:
            gen.append(k)
        for t in tipuri:
            pe_tip[t].append(k)
    linii = [f"- {t}: " + ", ".join(dict.fromkeys(sorted(v))) for t, v in pe_tip.items() if v]
    if gen:
        linii.append("- (rare, oricare tip): " + ", ".join(dict.fromkeys(sorted(gen))))
    return "\n".join(linii)


# =====================================================================================================
# Validare și curățare după schemă
# =====================================================================================================
def _tip_ok(v, t) -> bool:
    if isinstance(t, list):
        return any(_tip_ok(v, x) for x in t)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
    if t == "integer":
        return isinstance(v, (int, float)) and not isinstance(v, bool) and float(v).is_integer()
    return {"string": str, "boolean": bool, "object": dict, "array": list}[t] is type(v) or (
        t == "array" and isinstance(v, list)) or (t == "object" and isinstance(v, dict))


def _rezolva(s: dict, defs: dict) -> dict:
    if "$ref" in s:
        return defs[s["$ref"].split("/")[-1]]
    return s


def _val(v, s, cale, defs, err, domenii=True):
    s = _rezolva(s, defs)
    t = s.get("type")
    if t and not _tip_ok(v, t):
        err.append(f"{cale}: tip {type(v).__name__}, se așteaptă {t}")
        return
    if "enum" in s and v not in s["enum"]:
        err.append(f"{cale}: valoarea „{v}” nu e în {s['enum']}")
        return
    if domenii and isinstance(v, (int, float)) and not isinstance(v, bool):
        if "exclusiveMinimum" in s and not v > s["exclusiveMinimum"]:
            err.append(f"{cale}: {v} trebuie > {s['exclusiveMinimum']}")
        if "minimum" in s and v < s["minimum"]:
            err.append(f"{cale}: {v} trebuie ≥ {s['minimum']}")
        if "maximum" in s and v > s["maximum"]:
            err.append(f"{cale}: {v} trebuie ≤ {s['maximum']}")
    if isinstance(v, dict) and "properties" in s:
        for k, x in v.items():
            if k not in s["properties"]:
                err.append(f"{cale}.{k}: cheie necunoscută" if cale else f"{k}: cheie necunoscută")
            elif x is not None:
                _val(x, s["properties"][k], f"{cale}.{k}" if cale else k, defs, err, domenii)
    if isinstance(v, list) and isinstance(s.get("items"), dict):
        for i, x in enumerate(v):
            _val(x, s["items"], f"{cale}[{i}]", defs, err, domenii)


_SCHEMA = None


def _schema():
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = schema_intrare()
    return _SCHEMA


def valideaza(d: dict, domenii: bool = False) -> list[str]:
    """Erorile de formă ale unei `intrare_fizica` față de schemă (chei necunoscute, tipuri, enumerări). Domeniile
    (> 0, ≤ 1 …) se verifică doar la cerere: valorile absurde trec mai departe la verificările F.7 (I06), care
    întreabă cu mesajul potrivit, în loc să arunce toată citirea."""
    s = _schema()
    err: list[str] = []
    if not isinstance(d, dict):
        return ["intrare_fizica nu e un obiect"]
    _val(d, s, "", s.get("$defs", {}), err, domenii)
    return err


def _numar(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v if math.isfinite(v) else None
    if isinstance(v, str):
        try:
            x = float(v.strip().replace(" ", "").replace(",", "."))
            return int(x) if x.is_integer() else x
        except ValueError:
            return None
    return None


def _curata(v, s, defs):
    s = _rezolva(s, defs)
    t = s.get("type")
    ts = t if isinstance(t, list) else [t]
    if isinstance(v, dict) and "properties" in s:
        out = {}
        for k, x in v.items():
            if k in s["properties"] and x is not None:
                y = _curata(x, s["properties"][k], defs)
                if y is not None:
                    out[k] = y
        return out or None
    if isinstance(v, list) and "array" in ts:
        it = s.get("items") or {}
        out = [y for y in (_curata(x, it, defs) for x in v) if y is not None]
        return out or None
    if "enum" in s:
        return v if v in s["enum"] else None
    if ("number" in ts or "integer" in ts) and not isinstance(v, bool):
        n = _numar(v)
        if n is not None:
            return n
        return v if "string" in ts and isinstance(v, str) else None
    if "boolean" in ts:
        return v if isinstance(v, bool) else None
    if "string" in ts:
        return v.strip() if isinstance(v, str) and v.strip() else None
    return None


def curata_plecare(p: dict) -> dict:
    """O plecare (tablou / PT / TD de locuință) curățată după definiția comună `plecare`."""
    s = _schema()
    defs = s.get("$defs", {})
    return (_curata(p, defs["plecare"], defs) or {}) if isinstance(p, dict) and "plecare" in defs else {}


def curata(d: dict) -> dict:
    """Doar cheile cunoscute de schemă, cu numerele convertite („300” → 300) și enumerările valide."""
    s = _schema()
    return _curata(d, s, s.get("$defs", {})) or {} if isinstance(d, dict) else {}


if __name__ == "__main__":
    import sys
    if "--genereaza" in sys.argv:
        print("scris:", scrie_inventar())
    else:
        print(json.dumps(unealta(), ensure_ascii=False, indent=1))
