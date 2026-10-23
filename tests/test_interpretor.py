"""Teste pentru engine/interpretor.py (SPEC_TEHNIC.md §F).

1. Toate cele 60 de fraze din tests/date/fraze_chat.json, cu regula de comparare din `_schema`:
   - exact: actiune, tip_schema, retea, puteri, plecari (nume normalizate fără diacritice/majuscule, valoare,
     unitate, ordine, copii; plus receptor și L_m când fraza le cere), nr_plecari, lungimi_m, material,
     beneficiar, adresa — și câmpurile structurale suplimentare prezente în `asteptat`
     (masura_ceruta, hibrid, atr_jt, plansa, faza, metoda, izolatie, grupare, bmpt_cerut, …);
   - `presupus` și `intrebari`: fiecare element așteptat trebuie acoperit de cel puțin un element din răspuns.
     „Acoperit” = elementul din răspuns (normalizat) conține TOATE cuvintele-cheie definite în CUVINTE_CHEIE
     pentru elementul așteptat. Cuvintele-cheie conțin valorile numerice și termenii tehnici esențiali.
2. `intrare_fizica` pentru frazele cu corespondent în cazuri_golden.json („Chat <cheie>” în `descriere`
   ↔ „cases.json:<cheie>” în `sursa`) este egală cu `intrare` din cazul golden pe câmpurile cazului golden.

Rulare: cd /home/claude/sm && python3 -m pytest tests/test_interpretor.py -q
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

import pytest

RADACINA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADACINA))

from engine.interpretor import interpreteaza  # noqa: E402

FRAZE = json.loads((RADACINA / "tests/date/fraze_chat.json").read_text(encoding="utf-8"))["fraze"]
GOLDEN = json.loads((RADACINA / "tests/date/cazuri_golden.json").read_text(encoding="utf-8"))["cazuri"]

# Frazele marcate xfail (motivul e în spec/DISCREPANTE_CHAT.md). Ținta e 60/60, deci lista e goală.
XFAIL: dict[str, str] = {}


# ----------------------------------------------------------------------------------------------- normalizare
def norm(s) -> str:
    """Litere mici, fără diacritice, fără ghilimele tipografice, „×” → „x”, „φ” → „fi”, spații comprimate."""
    s = str(s).translate(str.maketrans("șşțţăâîȘŞȚŢĂÂÎ", "ssttaaiSSTTAAI"))
    s = "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))
    s = s.lower().replace("×", "x").replace("φ", "fi").replace("cos fi", "cosfi")
    s = re.sub(r"[„”“«»]", "", s)
    return re.sub(r"\s+", " ", s).strip()


# ------------------------------------------------------------------------------------------- cuvinte-cheie
# expected (text exact din fraze_chat.json) → cuvinte-cheie (după `norm`) care trebuie să apară TOATE
# în același element din răspuns. Un tuplu = variante acceptate.
OD = ["ik3max", "25 ka", "0,18", "j0,09", "implicit"]
CUVINTE_CHEIE = {
    "cosφ 0,9": ["cosfi 0,9"],
    "coloană Al PVC metoda D1 (în tub în pământ), cu trecere pe Cu dacă Al < 16 mm²":
        ["coloana al pvc", "d1", "tub", "cu daca al < 16"],
    "schema TN-C-S, separare PEN în BMPT": ["tn-c-s", "pen", "bmpt"],
    "Ik3max OD 25 kA și Zbuclă OD 0,18 + j0,09 Ω (valori implicite)": OD,
    "beneficiar și adresă necompletate (câmpuri goale în cartuș)": ["beneficiar", "adresa", "necompletat", "cartus"],
    "Racordul se face din PT-ul OD cu măsură în PT, sau prin PT propriu? Pot genera schema „Post de transformare” (ex. 400 kVA).":
        ["pt-ul od", "pt propriu", "post de transformare", "400 kva"],
    "limita ΔU la bara TE = 3 % (dacă e depășită, motorul mărește secțiunea C2)":
        ["limita δu", "bara te = 3 %", "motorul", "sectiunea c2"],
    "Confirmați BMPTd-100? Măsura semidirectă (BMPTi-250) se folosește doar între 100 și 250 A.":
        ["confirmati bmptd-100", "semidirect", "100 si 250 a"],
    "ks = 0,9 (2 plecări)": ["ks = 0,9", "2 plecari"],
    "plecări: L = 50 m, Al PVC D1": ["plecari", "l = 50 m", "al pvc d1"],
    "sursa: rețea publică prin BMPT cu RCCB 300 mA": ["retea publica", "bmpt", "rccb 300 ma"],
    "ks = 0,6 (12 plecări), dar P declarată 400 kW are prioritate": ["ks = 0,6", "12 plecari", "400 kw", "prioritate"],
    "„hală 1 100 A” = numele „Hală 1” + 100 A (separatorul de mii prin spațiu NU se acceptă în liste)":
        ["hala 1 100 a", "numele hala 1", "+ 100 a", "separatorul de mii"],
    "plecări L = 50 m, trasee separate": ["plecari", "l = 50 m", "trasee separate"],
    "pompe: receptor motor, cosφ 0,85": ["pompe", "receptor motor", "cosfi 0,85"],
    "lungimea de 120 m se aplică DOAR alimentării; plecări L = 50 m": ["120 m", "doar alimentarii", "plecari l = 50 m"],
    "plecări pe același pat de cabluri (grupare 4 circuite, B.52.17: 0,77)":
        ["acelasi pat de cabluri", "4 circuite", "b.52.17", "0,77"],
    "plecări L = 50 m": ["plecari", "l = 50 m"],
    "unitatea „A” se aplică tuturor numerelor din listă": ["unitatea a", "tuturor numerelor"],
    "alimentare L = 50 m": ["aliment", "l = 50 m"],
    "Iac,max = 1,1·Pn/(√3·400) (fișa invertorului lipsește)": ["iac,max = 1,1", "√3·400", "fisa invertorului"],
    "cablu invertor Al PVC D1, L = 30 m": ["cablu invertor al pvc d1", "l = 30 m"],
    "racord JT (S = 55 kVA)": ["racord jt", "s = 55 kva"],
    "PCS BESS = 100 kW (0,5C din 200 kWh)": ["pcs", "100 kw", "0,5c", "200 kwh"],
    "S = 440 kVA > 400 kVA → PT propriu 20/0,4 kV 630 kVA adăugat": ["s = 440 kva", "pt propriu", "630 kva", "adaugat"],
    "Racordul este prin PT propriu (630 kVA presupus) sau JT conform ATR? Indicați puterea PCS dacă diferă de 100 kW.":
        ["pt propriu", "630 kva", "jt conform atr", "pcs", "100 kw"],
    "S = 968 kVA → PT propriu 1000 kVA adăugat (racord MT)": ["s = 968 kva", "pt propriu", "1000 kva", "racord mt"],
    "categoria A RfG (880 kW < 1 MW)": ["categoria a rfg", "880 kw"],
    "Confirmați PT propriu 1000 kVA (celulă trafo cu separator de sarcină + siguranțe MT)?":
        ["confirmati pt propriu 1000 kva", "separator de sarcina", "sigurante mt"],
    "1 MWp = 1000 kWp": ["1 mwp", "1000 kwp"],
    "S = 1518 kVA → PT propriu 1600 kVA, celulă trafo cu întreruptor + releu":
        ["s = 1518 kva", "pt propriu", "1600 kva", "intreruptor + releu"],
    "categoria B RfG (1380 kW ≥ 1 MW)": ["categoria b rfg", "1380 kw"],
    "Confirmați PT propriu 1600 kVA?": ["confirmati pt propriu 1600 kva"],
    "trafo ulei 20/0,4 kV Dyn5, uk 4 %": ["trafo ulei 20/0,4 kv", "dyn5", "uk 4 %"],
    "S\"kQ = 500 MVA": ["s\"kq = 500 mva"],
    "celulă trafo cu separator de sarcină + siguranțe MT 16 A": ["separator de sarcina", "sigurante mt 16 a"],
    "plecări L = 50 m, Al PVC D1": ["plecari", "l = 50 m", "al pvc d1"],
    "uk 4 %": ["uk 4 %"],
    "uk 6 %": ["uk 6 %"],
    "celulă trafo cu întreruptor (Sn > 1000 kVA)": ["celula trafo cu intreruptor", "sn > 1000 kva"],
    "„pt” minuscul = „pentru” (nu post de transformare)": ["pt minuscul", "pentru", "post de transformare"],
    "„cam 35 m” = 35 m, aproximativ": ["cam 35", "35 m", "aproximativ"],
    "cablul descris = coloana C2 dintre BMPT și tabloul consumatorului; racordul C1 aparține OD":
        ["cablul descris", "coloana c2", "bmpt", "racordul c1", "od"],
    "P tablou din bilanț: Σ = 60 kW, ks = 0,9 → Pc = 54 kW (NU prima valoare din text)":
        ["bilant", "60 kw", "ks = 0,9", "pc = 54 kw", "nu prima valoare"],
    "„~70m” se aplică alimentării TG": ["~70m", "alimentarii tg"],
    "moară = receptor motor (cosφ 0,85)": ["moar", "receptor motor", "0,85"],
    "iluminat = receptor iluminat (ΔU ≤ 3 %)": ["iluminat", "receptor iluminat", "3 %"],
    "„PT” majuscul = post de transformare; „pt” minuscul = „pentru”":
        ["pt majuscul", "post de transformare", "pt minuscul", "pentru"],
    "localitatea se preia așa cum a fost scrisă (fără diacritice adăugate)":
        ["localitatea", "cum a fost scrisa", "fara diacritice"],
    "Treceți pe prosumator trifazat 10 kW, sau reduceți invertorul monofazat la cel mult 8 kW (Iac,max ≤ 40 A)?":
        ["prosumator trifazat 10 kw", "monofazat", "8 kw", "40 a"],
    "„cu 2 plecări” = număr de plecări, NU material Cu": ["cu 2 plecari", "numar de plecari", "nu material cu"],
    "„TD-1” păstrat cu majuscule": ["td-1", "majuscul"],
    "P TD-1 din bilanțul sub-plecărilor (ks 0,9)": ["p td-1", "bilantul sub-plecarilor", "ks 0,9"],
    "sub-plecări: circuite finale Cu PVC metoda C, L = 25 m":
        ["sub-plecari", "circuite finale", "cu pvc metoda c", "l = 25 m"],
    "coloană Cu (monofazat)": ["coloana cu", "monofazat"],
    "Generez branșament trifazat (BMPTd-40, Ib = 19,2 A)?": ["trifazat", "bmptd-40", "19,2 a"],
    "I13: tipul BMPTd-63 nu există în ST 4-JT Rev. 3/2024 → nu se transmite motorului; s-a folosit BMPTd-100 (Ib = 56,1 A)":
        ["i13", "bmptd-63", "nu exista", "nu se transmite motorului", "bmptd-100", "56,1 a"],
    "Confirmați BMPTd-100?": ["confirmati bmptd-100"],
    "Care sunt puterile (kW) sau calibrele (A) celor 3 plecări?": ["puterile (kw)", "calibrele (a)", "3 plecari"],
    "0,3 km = 300 m, aplicat alimentării": ["0,3 km", "300 m", "alimentarii"],
    "plecările în același șanț, tuburi alăturate: k grupare B.52.19 pentru 6 circuite = 0,60":
        ["acelasi sant", "tuburi alaturate", "b.52.19", "6 circuite", "0,6"],
    "„3×63 A” = 3 plecări de 63 A (nu 189 A)": ["3x63 a", "3 plecari de 63 a", "189 a"],
    "tablou cu circuite finale (circuite_finale): MCB curba B pentru iluminat/prize, DDR 30 mA tip A pe circuitele de prize":
        ["circuite_finale", "mcb curba b", "iluminat/prize", "ddr 30 ma tip a", "prize"],
    "circuite Cu PVC metoda C, L = 25 m": ["circuite cu pvc metoda c", "l = 25 m"],
    "Cu PVC metoda C, L = 25 m": ["cu pvc metoda c", "l = 25 m"],
    "alimentare TD L = 50 m": ["aliment", "td l = 50 m"],
    "1,6 MVA = 1600 kVA": ["1,6 mva", "1600 kva"],
    "plecarea de 1000 A: MCCB (gG doar până la 630 A pe plecări)": ["1000 a", "mccb", "gg", "630 a"],
    "500 kVA nu e putere standard în norme.TRAFO → 630 kVA (următoarea)": ["500 kva", "standard", "630 kva"],
    "Confirmați 630 kVA (sau 400 kVA)?": ["confirmati 630 kva", "400 kva"],
    "virgula = separator zecimal": ["virgula", "separator zecimal"],
    "Iac,max = 1,1·Pn/(√3·400)": ["iac,max = 1,1", "√3·400"],
    "Împărțiți centrala pe două posturi de transformare (ex. 2 × 1600 kVA)?":
        ["doua posturi de transformare", "2 x 1600 kva"],
    "baterie cuplată în c.c. la invertorul hibrid (fără PCS separat)":
        ["baterie cuplata in c.c.", "hibrid", "fara pcs"],
    "invertor la 15 m de tabloul consumatorului, Cu PVC metoda C": ["invertor la 15 m", "cu pvc metoda c"],
    "județ necompletat (câmp gol în cartuș)": ["judet necompletat", "cartus"],
    "„invertor 12 kW” = 1 invertor de 12 kW": ["invertor 12 kw", "1 invertor de 12 kw"],
    "x\"d = 0,12": ["x\"d = 0,12"],
    "ATS 4 poli cu interblocaj mecanic + electric": ["ats 4 poli", "interblocaj mecanic + electric"],
    "fără excitație susținută declarată": ["fara excitatie sustinuta"],
    "Măriți GE la cel puțin 80 kVA (seria standard GE_SN_KVA, Sn ≥ P/cosφ = 66,7 kVA; pornirea motoarelor neinclusă) sau declarați sarcinile prioritare?":
        ["mariti ge", "cel putin 80 kva", "ge_sn_kva", "66,7 kva", "sarcinile prioritare"],
    "limite ΔU pentru PT propriu: 6 % iluminat / 8 % altele": ["pt propriu", "6 % iluminat", "8 % altele"],
    "Sn necunoscut: Ik3max 25 kA și impedanța buclei implicite la bara PT (avertismente V32)":
        ["sn necunoscut", "ik3max 25 ka", "impedanta buclei", "bara pt", "v32"],
    "Care este puterea trafo (kVA)?": ["puterea trafo", "kva"],
    "„sol umed” nu se convertește automat: rezistivitatea termică rămâne 2,5 K·m/W (conservator); se poate introduce numeric":
        ["sol umed", "nu se converteste", "2,5 k·m/w", "numeric"],
    "„si” = „și” (fără diacritice)": ["si = si", "fara diacritice"],
    "unitatea A comună": ["unitatea a", "comuna"],
    "siguranțe MT 63 A (orientativ, tabel producător)": ["sigurante mt 63 a", "orientativ"],
    "Ce tip de schemă: branșament (BMPT/BMPM), tablou, CEF, prosumator, post de transformare sau grup electrogen? Care este puterea?":
        ["ce tip de schema", "bransament", "tablou", "cef", "prosumator", "post de transformare",
         "grup electrogen", "puterea"],
    "Care este lungimea coloanei BMPT → tablou?": ["lungimea coloanei", "bmpt"],
    "Care este factorul de putere (ex. 0,9)?": ["factorul de putere", "0,9"],
    "200 A interpretat ca Ib (curent maxim absorbit); cosφ 0,9 folosit doar pentru ΔU":
        ["200 a", "ib", "curent maxim absorbit", "cosfi 0,9", "doar pentru δu"],
    "50 kW = putere c.a. totală → 2 × 25 kW": ["50 kw", "putere c.a. totala", "2 x 25 kw"],
    "kWp nedeclarat (raport c.c./c.a. necalculat)": ["kwp nedeclarat"],
    "7,5 kW cu virgulă zecimală": ["7,5 kw", "virgula zecimala"],
    "P TD din bilanțul sub-plecărilor": ["p td", "bilantul sub-plecarilor"],
    "la PT, o lungime generală se aplică tuturor plecărilor (0,2 km = 200 m)":
        ["la pt", "lungime generala", "tuturor plecarilor", "0,2 km", "200 m"],
    "Care este a treia plecare?": ["a treia plecare"],
    "Branșament monofazat (max. 40 A) sau trifazat 63 A?": ["monofazat", "40 a", "trifazat 63 a"],
    "25 kVA la un branșament = putere aparentă: Ib = 25 000/(√3·400) = 36,1 A; cosφ 0,9 folosit doar pentru ΔU":
        ["25 kva", "putere aparenta", "√3·400", "36,1 a", "cosfi 0,9", "doar pentru δu"],
    "coloană L = 50 m": ["coloana l = 50 m"],
    "lungimea scrisă după calibrul unei plecări aparține acelei plecări":
        ["lungimea scrisa dupa calibru", "apartine plecarii"],
}


def acoperit(asteptat: str, raspuns: list[str]) -> bool:
    chei = CUVINTE_CHEIE.get(asteptat)
    assert chei, f"lipsesc cuvintele-cheie pentru: {asteptat!r}"
    for el in map(norm, raspuns):
        if all(any(norm(v) in el for v in (k if isinstance(k, tuple) else (k,))) for k in chei):
            return True
    return False


# --------------------------------------------------------------------------------------------- comparare
CAMPURI_EXACTE = ["retea", "puteri", "nr_plecari", "lungimi_m", "material", "beneficiar", "adresa",
                  "masura_ceruta", "hibrid", "atr_jt", "plansa", "faza", "metoda", "izolatie", "grupare",
                  "bmpt_cerut", "sursa_alimentare", "celula_trafo"]


def plecari_comparabile(lista, model):
    """Plecările în forma de comparat: nume normalizat, valoare, unitate (+ receptor / L_m dacă le cere fraza)."""
    out = []
    for i, p in enumerate(lista or []):
        m = (model or [{}] * (i + 1))[i] if model and i < len(model) else {}
        q = {"nume": norm(p["nume"]), "valoare": p.get("valoare"), "unitate": p.get("unitate")}
        for k in ("receptor", "L_m"):
            if k in m:
                q[k] = p.get(k)
        if p.get("copii") or m.get("copii"):
            q["copii"] = plecari_comparabile(p.get("copii"), m.get("copii"))
        out.append(q)
    return out


def _param(f):
    marks = [pytest.mark.xfail(reason=XFAIL[f["id"]], strict=True)] if f["id"] in XFAIL else []
    return pytest.param(f, id=f["id"], marks=marks)


@pytest.mark.parametrize("fraza", [_param(f) for f in FRAZE])
def test_fraza(fraza):
    a = fraza["asteptat"]
    r = interpreteaza(fraza["text"])
    ex = r["extras"]
    assert r["actiune"] == a["actiune"], (r["actiune"], r["refuz_motiv"], r["intrebari"])
    if "tip_schema" in a:
        assert r["tip_schema"] == a["tip_schema"]
    for k in CAMPURI_EXACTE:
        if k in a:
            assert ex.get(k) == a[k], f"{k}: așteptat {a[k]!r}, obținut {ex.get(k)!r}"
    if "plecari" in a:
        assert plecari_comparabile(ex["plecari"], a["plecari"]) == plecari_comparabile(a["plecari"], a["plecari"])
    if "nr_plecari" in a and a.get("actiune") != "refuza":
        assert len(ex["plecari"]) == a["nr_plecari"]           # F.4 r. 5
    for k in ("presupus", "intrebari"):
        lipsa = [x for x in a.get(k, []) if not acoperit(x, r[k])]
        assert not lipsa, f"{k} neacoperite: {lipsa}\nrăspuns: {r[k]}"
    if "intrare_motor" in a:                                    # contractul B.1.1 (SPEC v1.1)
        egal_pe_campurile_golden(a["intrare_motor"], r["intrare_fizica"], "intrare_motor")
    if a["actiune"] == "refuza":
        assert r["refuz_cod"] and r["refuz_motiv"]
    assert r["intelegere"].startswith("Am înțeles:")


# --------------------------------------------------------------------------- intrare_fizica vs. cazuri_golden
def _perechi_golden():
    dupa_sursa = {f["sursa"].split(":", 1)[1]: f for f in FRAZE if f["sursa"].startswith("cases.json:")}
    perechi = []
    for caz in GOLDEN:
        m = re.match(r"Chat (\w+):", caz.get("descriere", ""))
        if m and m.group(1) in dupa_sursa:
            perechi.append((dupa_sursa[m.group(1)], caz))
    return perechi


# Câmpuri din cazurile golden care NU pot proveni din text (marcate de inginer în `campuri_nu_din_text`).
NU_DIN_TEXT = {c["id"]: set(c.get("campuri_nu_din_text") or c["intrare"].get("campuri_nu_din_text") or [])
               for c in GOLDEN}


def egal_pe_campurile_golden(golden, obtinut, cale="intrare"):
    """Fiecare cheie din golden trebuie să existe în rezultat cu aceeași valoare (recursiv; listele în ordine).
    Cheile în plus din rezultat (ex. masura_ceruta, receptor) sunt permise."""
    if isinstance(golden, dict):
        assert isinstance(obtinut, dict), f"{cale}: așteptat dict, obținut {obtinut!r}"
        for k, v in golden.items():
            assert k in obtinut, f"{cale}.{k} lipsește"
            egal_pe_campurile_golden(v, obtinut[k], f"{cale}.{k}")
    elif isinstance(golden, list):
        assert isinstance(obtinut, list) and len(obtinut) == len(golden), f"{cale}: {obtinut!r} ≠ {golden!r}"
        for i, (g, o) in enumerate(zip(golden, obtinut)):
            egal_pe_campurile_golden(g, o, f"{cale}[{i}]")
    elif isinstance(golden, str) and cale.endswith(".nume"):
        assert norm(obtinut) == norm(golden), f"{cale}: {obtinut!r} ≠ {golden!r}"
    else:
        assert obtinut == golden, f"{cale}: {obtinut!r} ≠ {golden!r}"


@pytest.mark.parametrize("fraza,caz", [pytest.param(f, c, id=f"{f['id']}-{c['id']}") for f, c in _perechi_golden()])
def test_intrare_fizica_golden(fraza, caz):
    r = interpreteaza(fraza["text"])
    golden = {k: v for k, v in caz["intrare"].items() if k not in NU_DIN_TEXT.get(caz["id"], set())}
    egal_pe_campurile_golden(golden, r["intrare_fizica"])


def test_perechi_golden_gasite():
    """Toate cazurile „Chat …” din cazuri_golden.json au o frază corespondentă."""
    chat = [c["id"] for c in GOLDEN if c.get("descriere", "").startswith("Chat ")]
    gasite = {c["id"] for _, c in _perechi_golden()}
    assert set(chat) <= gasite and len(chat) >= 20


# ------------------------------------------------------------------------------------------- proprietăți
def test_nu_dimensioneaza():
    """F.1: intrarea fizică nu conține rezultate de dimensionare (secțiuni, calibre alese, ΔU)."""
    for f in FRAZE:
        txt = json.dumps(interpreteaza(f["text"])["intrare_fizica"])
        for cheie in ("S_faza_mm2", "Iz_", "dU_", "protectie", "bloc"):   # Ib_A e câmp de intrare (B.1.1)
            assert cheie not in txt, (f["id"], cheie)


def test_llm_lipsa_ramane_local(monkeypatch):
    """Fără SDK/cheie, foloseste_llm=True dă exact rezultatul regulilor locale."""
    import engine.interpretor as m
    monkeypatch.setattr(m, "intrare_llm", lambda text: None)
    assert m.interpreteaza("TG 120 kW cu 4 plecări de 63 A", foloseste_llm=True) == \
        m.interpreteaza("TG 120 kW cu 4 plecări de 63 A")


def test_llm_rezultat_validat(monkeypatch):
    """Rezultatul LLM trece prin normalizare + validare + verificările F.7 (nu le poate ocoli)."""
    import engine.interpretor as m
    monkeypatch.setattr(m, "intrare_llm", lambda text: {"tip_schema": "bransament", "P_kW": "300",
                                                         "L_coloana_m": 120, "cheie_inventata": 1})
    r = m.interpreteaza("branșament 300 kW, cablu 120 m", foloseste_llm=True)
    assert r["motor"] == "llm" and "cheie_inventata" not in r["intrare_fizica"]
    assert r["actiune"] == "refuza" and r["refuz_cod"] == "I10"
    monkeypatch.setattr(m, "intrare_llm", lambda text: {"tip_schema": "pt"})       # formă invalidă → local
    r = m.interpreteaza("branșament 60 kW, cablu 50 m", foloseste_llm=True)
    assert r["motor"] == "reguli" and r["actiune"] == "genereaza"
    monkeypatch.setattr(m, "intrare_llm", lambda text: (_ for _ in ()).throw(RuntimeError("rețea")))
    r = m.interpreteaza("branșament 60 kW, cablu 50 m", foloseste_llm=True)
    assert r["motor"] == "reguli" and any("LLM indisponibil" in p for p in r["presupus"])


def test_chat_wrapper():
    from engine import chat
    r = chat.interpreteaza("PT 630 kVA cu 2 plecări de 400 A", foloseste_claude=False)
    assert r["intrare_fizica"]["Sn_kVA"] == 630 and r["model"] is None
