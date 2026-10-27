"""r12 — textele „ca de proiectant” (memorii, ATR-uri, devize copiate): clasele găsite la testarea pe proiecte reale.

Principiu: înaintea regulilor vechi (`interpretor.interpreteaza_local`), `preextrage(text)` citește PE SEGMENTE (rând /
propoziție / „;”) fragmentele pe care regulile vechi le leagă greșit, le scoate din text și le păstrează structurat;
`aplica(c, intr, ex, tip, I)` le pune în `intrare_fizica` după reguli (suprascrie legările vechi). Fiecare fragment scos
lasă o notă („Am presupus”) sau o întrebare — nimic nu dispare tăcut.

Clase (SPEC §F.16):
1. cabluri legate pe segment: invertor → tablou = `invertoare[].cablu` + `L_m`; tablou → PT / TEG / stație / BMPT = `cablu_C0`
   + `L_racord_m` (mai multe tronsoane → `cablu_C0.tronsoane[]`); LES / A2XS(FL)2Y / MT = `cablu_MT` (niciodată C0); TE
   secundar → TEG = `tablouri_intermediare[].cablu`; „N cabluri în paralel” doar pe cablul propoziției; fără context →
   întrebare (nu C0 implicit). „m 600” după un cablu, într-un rând de deviz, e cantitatea, nu lungimea.
2. invertoare pe rânduri („INV1: …”, „Invertorul 2 – … 144 panouri …”) = grupuri separate cu `string` proprii;
   „N stringuri × M module, K MPPT” = N stringuri pe invertor, împărțite pe MPPT (`n_stringuri_paralel` = ⌈N / K⌉).
3. racord existent: „PTAb existent”, „barele JT ale postului”, „stația de 0,4 kV a fabricii”, „TEG beneficiar alimentat din
   PT …”, „TDRI”, „separator vertical … existent” → `pt_existent` / `racord: tg_existent`; PT nou doar cu „nou /
   proiectat / (pr)”.
4. vocabular: „TT 20/0,1 kV” / „2 TT” = transformatoare de tensiune (nu schema TT); „AAR” la celulele MT / PC și „în
   paralel” la cabluri ≠ GE + ATS; „Ir = 36 kA” / „Ir-16kA” = Icu; „MODEL buc N” (deviz) = N × MODEL; „Putere nominală
   totală invertoare X kW” = `Pn_total_kW`; „puterea instalată panouri X kW” = kWp; „… evacuată A kVA / B kW” = B kW;
   codurile de model nu înghit „0,4 kV”.
5. chei noi pentru motor: `QG` {tip, motorizat, Ir_reglat [A], Isd_reglat [A], Icu [kA]} + `In_QG_A`; `invertoare[].prot_tip`
   (gG / MCB / MCCB) + `prot_In_A`; `monitorizare` {smart_meter, smartlogger, rs485, ups_releu, contor_productie};
   `tablouri_intermediare[]` {nume, n_invertoare, cablu, L_m, prot_tip, prot_In_A}; `cablu_MT` {tip, S_mm2, material,
   L_m, tronsoane[]}; celulele MT (`celule_mt`, `celula_trafo: intreruptor` la „dispozitiv general … cu întrerupător”).
"""
from __future__ import annotations

import math
import re

NUM = r"\d+(?:[.,]\d+)?"
_TR = str.maketrans("șşțţăâîȘŞȚŢĂÂÎ", "ssttaaiSSTTAAI")
_NUMERAL = {"un": 1, "o": 1, "unu": 1, "doua": 2, "doi": 2, "trei": 3, "patru": 4, "cinci": 5, "sase": 6, "sapte": 7,
            "opt": 8}
_NUMW = r"\d+|doua|doi|trei|patru|cinci|sase|sapte|opt"


def _num(s: str) -> float:
    s = s.strip()
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", s):
        return float(s.replace(".", ""))
    return float(s.replace(",", "."))


def _int(s: str) -> int:
    return _NUMERAL[s] if s in _NUMERAL else int(s)


def _nr(x):
    if x is None:
        return None
    x = round(float(x), 4)
    return int(x) if x == int(x) else x


def _f(x) -> str:
    x = round(float(x), 3)
    return (f"{x:.3f}".rstrip("0").rstrip(".")).replace(".", ",")


def norm(text: str) -> str:
    """Copia de lucru (aceeași lungime): litere mici, fără diacritice, „×” → „x”."""
    t = text.translate(_TR)
    t = "".join(ch.lower() if len(ch.lower()) == 1 else ch for ch in t)
    return t.replace("×", "x").replace("–", "-").replace("—", "-")


RE_PV = re.compile(r"\binverto\w*|\bpanour?\w*\s+(?:pv|fotovolt\w*|solar\w*)|\bmodul\w*\s+(?:pv|fotovolt\w*)|\bfotovoltai\w*"
                   r"|\bcef\b|\bkwp\b|\bstring\w*|\bprosumator\w*|\bsun2000\b")


class Rez:
    def __init__(self, t: str):
        self.t = t
        self.sterse: list[tuple] = []        # intervale scoase din text
        self.rescrieri: list[tuple] = []     # (s, e, text nou)
        self.note: list[str] = []
        self.intrebari: list[tuple] = []
        self.d: dict = {}                     # datele structurate

    def sterge(self, s, e):
        if e > s:
            self.sterse.append((s, e))

    def rescrie(self, s, e, nou):
        self.rescrieri.append((s, e, nou))

    def liber(self, s, e) -> bool:
        return not any(a < e and s < b for a, b in self.sterse)

    def text(self, orig: str) -> str:
        resc = [r for r in self.rescrieri if not any(a < r[1] and r[0] < b for a, b in self.sterse)]
        ops = [(s, e, " ") for s, e in self.sterse] + resc
        ops.sort(key=lambda x: (x[0], -x[1]))
        out, poz = [], 0
        for s, e, nou in ops:
            if s < poz:                      # suprapuneri: intervalul deja acoperit
                if e > poz:
                    poz = e
                continue
            out.append(orig[poz:s])
            out.append(nou)
            poz = e
        out.append(orig[poz:])
        txt = "".join(out)
        txt = re.sub(r"[ \t]{2,}", " ", txt)
        txt = re.sub(r"\s+([,.;:])", r"\1", txt)
        txt = re.sub(r"([,;:])(?:\s*[,;:])+", r"\1", txt)
        return txt


# ================================================================================================= segmente
def segmente(t: str) -> list[tuple]:
    """(s, e) — rânduri, „;”, „. ” (nu punctul zecimal / „buc.” / „cl.”), „ - ” între clauze nu."""
    out, s = [], 0
    for m in re.finditer(r"\n|;|(?<!\d)(?<!\bbuc)(?<!\bcl)(?<!\bnr)(?<!\bc\.a)(?<!\bc\.c)\.(?=\s|$)", t):
        if m.start() > s:
            out.append((s, m.start()))
        s = m.end()
    if s < len(t):
        out.append((s, len(t)))
    return [(a, b) for a, b in out if t[a:b].strip()]


def _seg_de(segs, poz):
    return next(((a, b) for a, b in segs if a <= poz < b), (0, 0))


# ================================================================================================= 4. vocabular
RE_TT = re.compile(rf"(?:(?<![\w.,])(?P<n>\d)\s*(?:buc\.?\s*)?)?\btt\b(?P<r>\s*{NUM}\s*/\s*{NUM}(?:\s*/\s*{NUM})?\s*(?:kv)?)?"
                   rf"(?P<cl>\s*,?\s*cl(?:asa|\.)?\s*{NUM}\s*s?\b)?")


def _tt_tensiune(R: Rez):
    t = R.t
    for m in RE_TT.finditer(t):
        ctx = t[max(0, m.start() - 60):m.start()]
        if not (m.group("n") or m.group("r") or m.group("cl") or re.search(r"celul\w*\s+(?:de\s+)?masur\w*|\btc\b", ctx)):
            continue
        if re.search(r"\b(?:schema|sistem\w*|regim\w*)\s+(?:de\s+)?(?:legare\s+la\s+pamant\s+)?$", ctx):
            continue
        R.sterge(m.start(), m.end())
        R.d.setdefault("tt_masura", []).append(t[m.start():m.end()].strip())
        R.note.append(f"„{t[m.start():m.end()].strip()}” = transformatoare de tensiune (celula de măsură MT), nu schema "
                      "de legare la pământ TT")


RE_IR_KA = re.compile(rf"\bir\s*(?:=|:|-)?\s*(?P<v>{NUM})\s*ka\b")


def _ir_ka(R: Rez):
    for m in RE_IR_KA.finditer(R.t):
        R.rescrie(m.start(), m.end(), f"Icu {m.group('v')} kA")
        R.note.append(f"„{R.t[m.start():m.end()]}” = puterea de rupere (Icu {m.group('v')} kA), în vocabularul "
                      "proiectanților „Ir” = Icu (nu curentul reglat)")


RE_EVAC = re.compile(rf"\b(?P<cuv>evacuat\w*|evacuar\w*|injectat\w*|absorbit\w*)(?P<mid>(?:\s+din\s+retea)?\s*(?:=|:|de)?\s*)"
                     rf"(?P<kva>{NUM})\s*kva\s*/\s*(?P<kw>{NUM})\s*kw\b")
RE_ABS_KVA = re.compile(rf"(?:,\s*|\s+)(?P<cuv>absorbit\w*)(?:\s+din\s+retea)?\s*(?:=|:|de)?\s*(?P<kva>{NUM})\s*kva\b(?!\s*/)")


def _atr_kva_kw(R: Rez):
    t = R.t
    for m in RE_EVAC.finditer(t):
        R.rescrie(m.start("kva"), m.end(), f"{m.group('kw')} kW")
        R.note.append(f"„{m.group('kva')} kVA / {m.group('kw')} kW” ({m.group('cuv')}) = puterea activă "
                      f"{m.group('kw')} kW din ATR (kVA-ul e informativ)")
    for m in RE_ABS_KVA.finditer(t):
        if R.liber(m.start(), m.end()):
            R.sterge(m.start(), m.end())
            R.d["S_absorbita_kVA"] = _nr(_num(m.group("kva")))
            R.note.append(f"„{t[m.start():m.end()].strip(' ,')}” = puterea aprobată pentru consum, în kVA (informativ; "
                          "nu e puterea centralei)")


RE_PN_TOTAL = re.compile(rf"\bputere\w*\s+nominal\w*\s+total\w*\s+(?:a\s+)?(?:invertoare\w*|invertoarelor)\s*(?:\(?\s*c\.?\s*a\.?\s*\)?)?"
                         rf"\s*(?:=|:|de)?\s*(?P<v>{NUM})\s*(?P<u>kw|mw)\b")
RE_PI_PANOURI = re.compile(rf"\bputere\w*\s+instalat\w*\s+(?:a\s+)?(?:panour\w*|modul\w*)(?:\s+fotovoltaic\w*)?(?:\s*\([^)]*\))?"
                           rf"\s*(?:=|:|de)?\s*(?P<v>{NUM})\s*(?P<u>kw|mw)\b(?!p)")


def _puteri(R: Rez):
    t = R.t
    m = RE_PN_TOTAL.search(t)
    if m:
        v = _num(m.group("v")) * (1000 if m.group("u") == "mw" else 1)
        R.d["Pn_total_kW"] = _nr(v)
        R.sterge(m.start(), m.end())
        R.note.append(f"„{t[m.start():m.end()]}” = puterea nominală totală a invertoarelor (Pn_total_kW = {_f(v)} kW, "
                      "sumă de control), nu un invertor")
    m = RE_PI_PANOURI.search(t)
    if m:
        R.rescrie(m.start("u"), m.end("u"), "kWp" if m.group("u") == "kw" else "MWp")
        R.note.append(f"„{t[m.start():m.end()]}” = puterea de vârf a modulelor (kWp), nu puterea unui modul")


def _model_kv(R: Rez):
    """„SUN2000-60KTL-M0 0,4 kV 60 kW” — „0,4 kV” e tensiunea invertorului, nu o cifră a modelului."""
    t = R.t
    for m in re.finditer(r"(?<=[a-z0-9])\s+0[.,]4\s*kv\b", t):
        w = re.search(r"(\S+)$", t[:m.start()])
        if w and len(re.findall(r"[a-z]", w.group(1))) >= 2 and re.search(r"\d", w.group(1)) and "/" not in w.group(1) \
                and not re.fullmatch(r"(?:dyn|yyn|yzn|dy)\d+", w.group(1)):
            R.sterge(m.start(), m.end())


RE_BUC = re.compile(r"^(?P<pre>[ \t]*)(?P<nume>[^\n]*?\b(?:inverto\w*|panou\w*|modul\w*)\b[^\n]*?)\s+buc\.?\s+(?P<n>\d+)\b"
                    r"(?!\s*(?:w|wp|kw|kwp)\b)", re.M)
RE_BUC_PRE = re.compile(r"(?<![\w.,])(?P<n>\d+)\s*buc\.?\s+(?=(?:de\s+)?(?:inverto\w*|panou\w*|modul\w*)\b)")


def _buc_deviz(R: Rez, orig: str):
    """„INVERTOR HUAWEI SUN2000-100KTL-M2 buc 8” (rând de deviz) = 8 × invertorul."""
    for m in RE_BUC.finditer(R.t):
        rand = R.t[m.start():R.t.find("\n", m.start()) if "\n" in R.t[m.start():] else len(R.t)]
        if re.match(r"\s*\d+\s*(?:x|buc)", m.group("nume")) or re.search(r"\s\d+$", m.group("nume")) or re.search(r"[\t;|]", rand):
            continue
        n = int(m.group("n"))
        nume = orig[m.start("nume"):m.end("nume")]
        R.rescrie(m.start("nume"), m.end(), f"{n} x {nume}")
        R.note.append(f"„{orig[m.start('nume'):m.end()].strip()}” (rând de deviz) = {n} × {nume.strip()}")
    for m in RE_BUC_PRE.finditer(R.t):                 # „2 buc. invertor cu puterea de 50 kW” = 2 × invertor
        if R.liber(m.start(), m.end()):
            R.rescrie(m.start(), m.end(), f"{m.group('n')} x ")


# ================================================================================================= 1. cabluri
_TIP = (r"tyir|acyaby(?:-f)?|cyaby(?:-f)?|ac2xaby|c2xaby|n2xh(?:-j)?|n2xy(?:-j)?|na2xy|na2xh|nyy(?:-j)?|myym|myf|cyy(?:-f)?"
        r"|a2xs\s*\(\s*fl\s*\)\s*2y|na2xs\w*|n2xs\w*|ta2x\s*\(\s*fl\s*\)\s*2y|a2xs\w*")
RE_CABLU = re.compile(
    rf"(?:(?<![\w.,])(?P<np>\d+)\s*x\s*(?=(?:{_TIP})\b)|(?P<nc>{_NUMW})\s+cabluri\s+(?=(?:{_TIP})\b))?"
    rf"(?:(?P<tip>{_TIP})\b\s*(?:\d+\s*ol-?al\s*\+\s*)?)?"
    rf"(?:(?P<par>\d)\s*x\s*\(\s*(?P<c1>\d)\s*x\s*(?P<s1>{NUM})(?:\s*\+\s*(?P<n1>{NUM}))?\s*\)"
    rf"|(?P<c>[1-5])\s*x\s*(?:(?P<mono>1)\s*x\s*)?(?P<s>{NUM})(?:\s*mm2|\s*mmp|\s*mm²)?(?:\s*(?:al|cu))?(?:\s*\+\s*(?P<n>{NUM})(?:\s*(?:al|cu))?)?"
    rf"(?:\s*\+\s*(?P<n2>{NUM})\s*(?:al|cu)?)?"
    rf"|(?<=[a-z\-)]\s)(?P<s0>{NUM})\s*(?:mm2|mmp|mm²)(?=\s))"
    rf"(?:\s*(?:mm2|mmp|mm²))?(?P<mat>\s*(?:al|cu)\b)?")
SECTIUNI = {1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240, 300, 400, 500, 630}


def _material(tip, mat):
    if mat:
        return "Al" if mat.strip().startswith("al") else "Cu"
    if not tip:
        return None
    tip = re.sub(r"\s+", "", tip)
    return "Al" if re.match(r"a|na|tyir|ta2x", tip) else "Cu"


def _izolatie(tip):
    if not tip:
        return None
    tip = re.sub(r"\s+", "", tip)
    return "XLPE" if re.match(r"n2x|na2x|tyir|a2xs|ac2x|c2x|ta2x|n2xs|na2xs", tip) else "PVC"


RE_L = re.compile(rf"(?:\(\s*(?P<a>\d+)\s*-\s*(?P<b>\d+)\s*m\s*\))|(?:(?:cca\.?|circa|aprox\.?|aproximativ|≈|de|l\s*=)\s*)?(?P<v>{NUM})\s*(?:m|ml|metri)\b(?!\s*/)")
RE_L_LUNG = re.compile(rf"\b(?:lungime\w*(?:\s+traseu)?|pe\s+o\s+lungime)\s*(?:de\s+)?(?:(?:aproximativ|cca\.?|circa)\s+)?"
                       rf"(?P<v>{NUM})\s*(?:m|ml|metri)\b")
RE_PARALEL = re.compile(rf"\b(?:(?P<n>{_NUMW})\s+cabluri\s+)?(?:(?:\w+\s+){{0,3}})?in\s+paralel\b|\b(?:este\s+)?necesar\w*\s+(?:de\s+)?"
                        rf"(?P<n2>{_NUMW})\s+cabluri\s+in\s+paralel\b")

# context: unde se leagă un cablu
RE_CTX_MT = re.compile(r"\bles\s*(?:\d+\s*kv|mt)\b|\bcablu\w*\s+(?:de\s+)?mt\b|\bmedie\s+tensiune\b")
RE_CTX_INV = re.compile(r"\binverto\w*|\binv\s*-?\s*\d\b|\bde\s+la\s+inv\b")
def _e_inv(x: str) -> bool:
    """invertorul ca capăt al cablului — nu „TEG invertoare” / „tablou invertoare” (tabloul lor)"""
    return any(not re.search(r"\b(?:teg|tg|tgd|te|tablou\w*)(?:\s+(?:de\s+)?(?:interfata|protectie|electric))?\s+(?:de\s+|al\s+)?$",
                             x[max(0, m.start() - 30):m.start()])
               for m in RE_CTX_INV.finditer(x))


RE_CTX_TE2 = re.compile(r"\b(?:te|tablou\w*)\s+(?:de\s+interfata\s+)?(?:secundar\w*|intermediar\w*)")
RE_CTX_RACORD = re.compile(r"\bpt\w*\b|\bpta\w*|\bpost\w*\b|\bstati[ae]\w*|\bt[eg]?g\w*\s+(?:al\s+)?benef\w*|\btablou\w*\s+(?:general\s+)?(?:al\s+)?benef\w*"
                           r"|\btdri\b|\btgjt\b|\bbmp[tm]\w*|\bpunct\w*\s+de\s+racord\w*|\bsecti[ae]\w*\s+(?:de\s+)?0[.,]4|\btg\s+existent"
                           r"|\btablou\w*\s+existent|\bbare\w*\s+jt\b|\bintreruptor\w*\s+(?:\w+\s+)?existent")
RE_CTX_PROD = re.compile(r"\benergie\w*\s+produs\w*|\bcontor\w*\s+(?:de\s+)?productie|\bbmp[mt]\w*\s+(?:de\s+)?productie")
RE_CTX_COLOANA = re.compile(r"\bbransament\w*|\bcoloan\w*|\bbmp[mt]\w*\s+(?:od|existent\w*)\b|\bfirid\w*")
RE_CTX_CONSUM = re.compile(r"\btablou\w*\s+(?:al\s+)?consumator\w*|\btablou\w*\s+(?:casei|locuintei)\b")
RE_CTX_TRAFO_TDRI = re.compile(r"\b(?:trafo\w*|transformato\w*)\s*-\s*(?:tdri|tablou|tgjt|q\s*jt)|\b(?:legatura|legaturi)\s+trafo\w*")


def _cabluri(R: Rez, segs, grupuri_linii):
    t = R.t
    gasite = []
    for m in RE_CABLU.finditer(t):
        sec = m.group("s1") or m.group("s") or m.group("s0")
        if not sec or not R.liber(m.start(), m.end()):
            continue
        if m.group("s0") and not m.group("tip"):
            continue
        s = _num(sec)
        if s not in SECTIUNI:
            continue
        tip = m.group("tip")
        ctx_ante = t[max(0, m.start() - 25):m.start()]
        if not (tip or m.group("mat") or re.search(r"cablu|conductor|coloan|les\b|legatur", ctx_ante)
                or m.group("par") or m.group("mono") or re.match(r"\s*(?:mm2|mmp)?\s*pe\s+(?:fiecare\s+)?faza", t[m.end():])):
            continue
        a_, _b = _seg_de(segs, m.start())
        prev = next((x for x in reversed(gasite) if a_ <= x.start() < m.start()), None)
        if prev is not None and not tip and re.match(r"\s*(?:mm2|mmp)?\s*pe\s+(?:fiecare\s+)?faza", t[m.end():]) and \
                _num(prev.group("s1") or prev.group("s") or prev.group("s0")) == s:
            continue                  # „N2XH 240mm2 m 135 3x240mm2 pe fiecare faza” = același cablu (3 pe fază)
        if re.match(r"\s*(?:a|kv|v|kw|kva)\b", t[m.end():m.end() + 4]):
            continue
        gasite.append(m)
    if not gasite:
        return
    cabluri = []
    for m in gasite:
        a, b = _seg_de(segs, m.start())
        tip = re.sub(r"\s+", "", m.group("tip") or "") or None
        d = {"S_fortat": _nr(_num(m.group("s1") or m.group("s") or m.group("s0")))}
        n_ = m.group("n1") or m.group("n")
        if n_ and _num(n_) != d["S_fortat"]:
            d["N_fortat"] = _nr(_num(n_))
        mat = _material(tip, m.group("mat"))
        if mat:
            d["material"] = mat
        iz = _izolatie(tip)
        if iz:
            d["izolatie"] = iz
        if tip:
            d["tip_cablu"] = tip.upper().replace("(FL)", "(FL)")
        fin = m.end()
        # prefixul de număr: „2x TYIR …”, „4 cabluri ACYABY …”, „2 x N2XY 1x240 pe faza”
        n_par = None
        if m.group("np"):
            n_par = int(m.group("np"))
        elif m.group("nc"):
            n_par = _int(m.group("nc"))
        elif m.group("par") and int(m.group("par")) > 1 and m.group("c1") != "1":
            n_par = int(m.group("par"))
        monopolar = bool(m.group("mono")) or m.group("c1") == "1"
        mfaza = re.match(r"\s*(?:mm2|mmp)?\s*(?:al|cu)?\s*pe\s+(?:fiecare\s+)?faza\b", t[fin:fin + 30])
        if mfaza:
            fin += mfaza.end()
            if monopolar and m.group("c") and m.group("c") != "1" and not n_par:
                n_par = int(m.group("c"))                       # „3x1x240 pe faza” = 3 conductoare pe fază
            elif not monopolar and m.group("c") and not n_par:   # „3x240mm2 pe fiecare faza” = 3 pe fază
                n_par = int(m.group("c"))
            monopolar = True
        # lungimea / „în paralel” / cantitatea de deviz, în restul segmentului (până la următorul cablu)
        Ls, sterg = [], []
        urm = next((x.start() for x in gasite if x.start() > m.start()), b)
        rest_e = min(b, urm)
        rest = t[fin:rest_e]
        cant = re.match(rf"\s*m\s+(?P<q>\d+)\b", rest)
        mpf = re.search(rf"(?P<k>\d)\s*x\s*(?:1\s*x\s*)?(?P<s>{NUM})\s*(?:mm2|mmp)?\s*pe\s+(?:fiecare\s+)?faza\b", rest)
        if mpf and _num(mpf.group("s")) == d["S_fortat"]:
            n_par, monopolar = int(mpf.group("k")), True
            sterg.append((fin + mpf.start(), fin + mpf.end()))
        if cant:
            sterg.append((fin, fin + cant.end()))
            d["_cantitate_m"] = int(cant.group("q"))
        for ml in RE_L_LUNG.finditer(t, fin, rest_e):
            Ls.append(_num(ml.group("v")))
            sterg.append((ml.start(), ml.end()))
        if not Ls:
            for ml in RE_L.finditer(t, fin, rest_e):
                if cant and ml.start() < fin + cant.end():
                    continue
                pre = t[max(fin, ml.start() - 12):ml.start()]
                if re.search(r"\d\s*$", pre):
                    continue
                if ml.group("a"):
                    Ls.append(float(ml.group("b")))
                    d["_L_interval"] = f"{ml.group('a')}-{ml.group('b')} m"
                else:
                    Ls.append(_num(ml.group("v")))
                sterg.append((ml.start(), ml.end()))
                break
        if not Ls:                                           # „70m conductor TYIR …”, „260 m conductor 2x TYIR …”
            mb = re.search(rf"(?<![\w.,])(?P<v>{NUM})\s*(?:m|ml)\s+(?:conducto\w*|cablu\w*)\s*$", t[max(a, m.start() - 30):m.start()])
            if mb:
                Ls.append(_num(mb.group("v")))
                d["_L_lista"] = True
                sterg.append((max(a, m.start() - 30) + mb.start(), m.start()))
        mp = RE_PARALEL.search(t, fin, rest_e) or RE_PARALEL.search(t[a:m.start()])
        if mp:
            nn = mp.group("n") or mp.group("n2")
            if mp.re is RE_PARALEL and mp.string is t and mp.start() >= fin:
                sterg.append((mp.start(), mp.end()))
            if nn:
                n_par = _int(nn)
            elif not n_par:
                d["_paralel_fara_numar"] = True
        if not mp:          # „Este necesar de 4 cabluri in paralel” în propoziția următoare a aceluiași rând
            rand_e = t.find("\n", m.start())
            rand_e = len(t) if rand_e < 0 else rand_e
            mp2 = RE_PARALEL.search(t, rest_e, rand_e)
            if mp2 and (mp2.group("n") or mp2.group("n2")) and not any(x.start() > m.start() and x.start() < mp2.start() for x in gasite):
                n_par = _int(mp2.group("n") or mp2.group("n2"))
                sterg.append((mp2.start(), mp2.end()))
        if n_par and n_par > 1:
            d["n_fortat"] = n_par
        if Ls:
            d["L_m"] = _nr(Ls[0])
            if d.get("_L_lista") and n_par and n_par > 1:
                d["_L_total"] = d["L_m"]
                d["L_m"] = _nr(Ls[0] / n_par)
        # contextul de legare
        hdr = t[a:m.start()]
        seg = t[a:b]
        cabluri.append({"m": m, "d": d, "seg": (a, b), "hdr": hdr, "segtxt": seg, "monopolar": monopolar,
                        "txt": R.orig[m.start():fin].strip() if hasattr(R, "orig") else t[m.start():fin].strip(),
                        "sterg": sterg + [(m.start(), fin)], "tip": tip})
    # clasificare
    for cb in cabluri:
        a, b = cb["seg"]
        seg, hdr, tip = cb["segtxt"], cb["hdr"], cb["tip"] or ""
        linie = next((g for g in grupuri_linii if g["s"] <= cb["m"].start() < g["e"]), None)
        fel = None
        if re.match(r"a2xs|na2xs|n2xs|ta2x", tip) or RE_CTX_MT.search(t[max(a, cb["m"].start() - 30):cb["m"].start()]):
            fel = "mt"
        elif RE_CTX_TRAFO_TDRI.search(seg):
            fel = "trafo_tdri"
        elif linie is not None:
            fel = "inv"
        elif RE_CTX_PROD.search(seg):
            fel = "productie"
        elif RE_CTX_COLOANA.search(seg) and not RE_CTX_INV.search(seg):
            fel = "coloana"
        elif RE_CTX_CONSUM.search(seg) and not RE_CTX_INV.search(seg):
            fel = "c0"
        else:
            sursa = re.search(r"\bde\s+la\s+(\S+(?:\s+\S+)?)", seg)
            ms_, me_ = cb["m"].start(), cb["m"].end()
            inv = bool(_e_inv(t[max(a, ms_ - 40):min(b, me_ + 60)])
                       or re.match(r"\s*(?:fiecare\s+|pe\s+fiecare\s+)?inverto\w*", seg))
            te2 = RE_CTX_TE2.search(seg)
            rac = bool(RE_CTX_RACORD.search(seg))
            hdr0 = hdr.split(":")[0] if ":" in hdr else ""
            hdr_inv = _e_inv(re.split(r"\s-\s", hdr0)[0]) if hdr0 else False
            if hdr0 and len(re.split(r"\s-\s", hdr0)) > 1 and RE_CTX_RACORD.search(re.split(r"\s-\s", hdr0)[1]):
                inv = False                       # „Legătura X - PT / TEG beneficiar:” = C0
            hdr_inv = hdr_inv or bool(re.search(r"\b(?:fiecare|pe\s+fiecare|cate\s+un)\s+inverto\w*|\bcablu\w*\s+(?:al\s+|de\s+|pentru\s+)?inverto\w*",
                                                t[max(a, cb["m"].start() - 45):cb["m"].start()]))
            if te2 and (re.search(r"\b(?:fiecare|din)\s+(?:te|tablou\w*)\s+(?:de\s+interfata\s+)?(?:secundar|intermediar)", seg)
                        or re.search(r"\b(?:spre|catre|pana\s+la|la)\s+(?:teg|te\s+principal|tablou\w*\s+(?:general|principal)|tdri)", seg)) \
                    and not re.search(r"\binverto\w*\s*:|\bfiecare\s+invertor", seg):
                fel = "te2"
            elif inv and (not rac or hdr_inv or (sursa and RE_CTX_INV.search(sursa.group(1)))):
                fel = "inv"
            elif rac:
                fel = "c0"
            elif inv:
                fel = "inv"
        cb["fel"] = fel
        cb["linie"] = linie
    if len(cabluri) == 1 and cabluri[0]["fel"] is None:
        return                       # un singur cablu, fără context: regulile vechi (C0, cu notă „cablul descris = C0”)
    R.d["cabluri"] = cabluri
    for cb in cabluri:
        for s, e in cb["sterg"]:
            R.sterge(s, e)
        # rutele „de la … la …”, „pana la …”, „Legatura X - Y:” ale cablului (contextul nu mai e nevoie de reguli vechi)
        a, b = cb["seg"]
        for mr in re.finditer(r"\b(?:legatur\w*\s+[^:,;]{0,60}?:|de\s+la\s+[^,;:]{1,40}?\s+(?:la|pana\s+la|spre|catre)\s+[^,;:]{1,50}"
                              r"|(?:pana\s+la|spre|catre)\s+[^,;:(]{1,50})", R.t[a:b]):
            s_, e_ = a + mr.start(), a + mr.end()
            frag = R.t[s_:e_]
            if re.search(r"\d", frag) or ("racord" not in R.d and re.search(
                    r"\b(?:tg\w*|tgd|pt\w*|post\w*|bmp[tm]\w*|bransament\w*|statia|tablou\w*\s+(?:general\s+)?existent)\b", frag)):
                # „Legatura TE-CEF - PTAb existent 20/0,4 kV 1000 kVA:” — PT-ul (existent) îl citește clasa racordului
                continue
            R.sterge(s_, e_)
        for mr in re.finditer(r"\bcablu\w*\s*$|\bconducto\w*\s*$|\bplecare\s+cu\s*$", R.t[a:cb["m"].start()]):
            R.sterge(a + mr.start(), a + mr.end())


# ================================================================================================= 2. invertoare pe rânduri
RE_LINIE_INV = re.compile(r"(?:^|\n)\s*(?P<et>inv\s*-?\s*(?P<k>\d+)|invertor(?:ul)?\s+(?:nr\.?\s*)?(?P<k2>\d+))\b\s*[:\-–]?")
RE_STR_N = re.compile(rf"(?P<ns>\d+)\s+(?:stringuri|siruri)\s*(?:x|de|cu|a\s+cate|de\s+cate)\s*(?P<nm>\d+)(?:\s+module)?\b")
RE_MPPT = re.compile(r"(?<!pe\s)\b(?P<k>\d+)\s*mppt\b|\bmppt\s*(?:=|:)?\s*(?P<k2>\d+)\b")
RE_N_MOD = re.compile(r"(?<![\w.,])(?P<n>\d+)\s+(?:module|panouri|panou|bucati\s+module)\b")


def _linii_invertoare(R: Rez) -> list[dict]:
    t = R.t
    starts = list(RE_LINIE_INV.finditer(t))
    if len(starts) < 2:
        return []
    out = []
    for i, m in enumerate(starts):
        s = m.start() + (1 if t[m.start()] == "\n" else 0)
        e = t.find("\n", m.end())
        e = len(t) if e < 0 else e
        if i + 1 < len(starts):
            e = min(e, starts[i + 1].start())
        g = {"k": int(m.group("k") or m.group("k2")), "s": s, "e": e, "eticheta": t[s:m.end()].strip(" :-")}
        seg = t[s:e]
        ms = RE_STR_N.search(seg)
        mk = RE_MPPT.search(seg)
        mn = RE_N_MOD.search(seg)
        if mn:
            g["n_module_tot"] = int(mn.group("n"))
            R.sterge(s + mn.start(), s + mn.end() - len(re.search(r"\S+$", mn.group(0)).group(0)))
        if ms:
            g["n_str"] = int(ms.group("ns"))
            g["n_mod"] = int(ms.group("nm"))
            R.sterge(s + ms.start(), s + ms.end())
            mi = re.search(r"\bin\s*$", t[s:s + ms.start()])
            if mi:
                R.sterge(s + mi.start(), s + ms.start())
        if mk:
            g["n_mppt"] = int(mk.group("k") or mk.group("k2"))
            R.sterge(s + mk.start(), s + mk.end())
        out.append(g)
    return out


def _string_pe_mppt(n_str, n_mod, n_mppt):
    """N stringuri pe invertor, K MPPT → (n_stringuri_paralel, n_MPPT)."""
    if not n_mppt:
        return n_str, 1, False
    p = max(1, math.ceil(n_str / n_mppt))
    k = n_str // p if n_str % p == 0 else None
    return p, (k or n_mppt), k is None


# ================================================================================================= 3. racord existent
RE_PT_EXIST = re.compile(rf"\b(?P<pt>ptab?\b|pta\b|pt\b|post\w*(?:\s+de\s+transformare)?)(?P<mid>(?:[^,;:.\n]|(?<=\d)[,.](?=\d)){{0,40}}?)\bexistent\w*"
                         rf"|\bbare(?:le)?\s+jt\s+ale\s+postului(?:\s+existent\w*)?|\bpostul(?:ui)?\s+existent\w*")
RE_STATIE_FABRICA = re.compile(r"\b(?:racord\w*\s+(?:in|la)\s+)?(?:statia|statiei|sectia|sectiei|tabloul|panoul)\s+(?:de\s+)?0[.,]4\s*kv"
                               r"(?:\s+(?:a|al)\s+(?:fabricii|beneficiar\w*|uzinei|halei|clientului))?"
                               r"(?:\s+cu\s+(?:un\s+)?intrerup\w*\s+(?:nou\s+)?(?:de\s+)?(?P<q>\d+)\s*a\b)?"
                               r"|\b(?:racord\w*\s+(?:in|la)\s+)?statia\s+(?:fabricii|beneficiar\w*)")
RE_TEG_BENEF = re.compile(rf"\b(?:racord\w*\s+(?:in|la)\s+)?(?:teg|tg|tgd|tablou\w*(?:\s+general)?)\s+(?:al\s+)?(?:beneficiar\w*|existent\w*|clientului)"
                          rf"(?:\s+alimentat\w*\s+din\s+(?:pt|ptab?|post\w*)(?:\s+(?:existent\w*|al\s+\w+))?(?:\s+(?P<sn>{NUM})\s*kva)?"
                          rf"(?:\s+20/0[.,]4\s*kv)?)?")
RE_PT_NOU = re.compile(r"\b(?:ptab?|pta|pt|post\w*|punct\w*\s+de\s+conexiune|pc)\b[^,;.\n]{0,25}?\b(?:nou[a]?|proiectat\w*)\b"
                       r"|\b(?:nou[a]?|proiectat\w*)\s+(?:ptab?|pta|pt|post\w*)\b|\(\s*pr\s*\)")
RE_TRAFO_EXIST = re.compile(rf"\b(?:trafo\w*|transformato\w*)\s+existent\w*\s+(?:de\s+)?(?P<sn>{NUM})\s*kva\b"
                            rf"|\b(?:trafo\w*|transformato\w*)\s+(?:de\s+)?(?P<sn2>{NUM})\s*kva\s+existent\w*")
RE_SEP_EXIST = re.compile(rf"\bpe\s+(?:un\s+)?(?:separato\w*\s+vertical\w*|separato\w*|sigurant\w*)(?:\s+(?:mpr|nh\d?|fuzibil\w*))*"
                          rf"\s+(?P<v>{NUM})\s*a\s+existent\w*")
RE_Q_RACORD_NOU = re.compile(rf"\b(?:pe\s+)?(?:un\s+)?(?:intrerup\w*|disjunctor\w*|usol)\s+(?:nou\s+)?(?:de\s+)?(?P<v>{NUM})\s*a\b"
                             rf"(?P<rest>[^,;.\n]{{0,60}}?\b(?:sectia|statia|panoul|tabloul)\s+(?:de\s+|din\s+)?(?:0[.,]4|fabric|benef)\w*[^,;.\n]{{0,40}})?")
RE_Q_EXIST = re.compile(r"\bpe\s+(?:un\s+)?(?:intrerup\w*|disjunctor\w*)\s+(?:\w+\s+)?existent\w*")


def _racord(R: Rez):
    t = R.t
    nou = RE_PT_NOU.search(t)
    d = {}
    for mq in RE_Q_RACORD_NOU.finditer(t):
        seg_ok = mq.group("rest")
        if not seg_ok or not R.liber(mq.start(), mq.end()):
            continue
        v = _num(mq.group("v"))
        d.update({"racord_In_Q_A": _nr(v), "racord_Q_tip": "ACB" if v >= 1000 else "MCCB"})
        R.sterge(mq.start(), mq.end())
        R.note.append(f"„{t[mq.start():mq.end()].strip()}” = întrerupătorul NOU al plecării de racord, în tabloul / stația JT "
                      f"existentă ({d['racord_Q_tip']} {_f(v)} A)")
        break
    mt = RE_TEG_BENEF.search(t)
    if mt and (mt.group("sn") or re.search(r"alimentat", mt.group(0)) or "benef" in mt.group(0)):
        d["racord"] = "tg_existent"
        if mt.group("sn"):
            d["pt_Sn_kVA"] = _nr(_num(mt.group("sn")))
        R.rescrie(mt.start(), mt.end(), "racord in TG existent")
        R.note.append(f"„{t[mt.start():mt.end()].strip()}” = racord în tabloul EXISTENT al beneficiarului (TG existent)"
                      + (f"; PT-ul {mt.group('sn')} kVA e doar sursa lui (nu PT nou)" if mt.group("sn") else ""))
    ms = RE_STATIE_FABRICA.search(t)
    if ms and "racord" not in d:
        mtr = RE_TRAFO_EXIST.search(t)
        if mtr:
            d.update({"racord": "pt", "pt_existent": True, "pt_Sn_kVA": _nr(_num(mtr.group("sn") or mtr.group("sn2")))})
            R.sterge(mtr.start(), mtr.end())
            R.note.append(f"„{t[ms.start():ms.end()].strip()}” + „{t[mtr.start():mtr.end()].strip()}” = racord pe barele JT "
                          f"ale postului EXISTENT {_f(d['pt_Sn_kVA'])} kVA al beneficiarului (nu PT nou)")
        else:
            d["racord"] = "tg_existent"
            R.note.append(f"„{t[ms.start():ms.end()].strip()}” = racord în tabloul / stația JT EXISTENTĂ a beneficiarului "
                          "(TG existent; nu PT nou)")
        R.rescrie(ms.start(), ms.end(), "racord in PT existent" if d.get("pt_existent") else "racord in TG existent")
        if ms.group("q"):
            v = float(ms.group("q"))
            d.update({"racord_In_Q_A": _nr(v), "racord_Q_tip": "ACB" if v >= 1000 else "MCCB"})
            R.note.append(f"întrerupătorul NOU al plecării de racord în stația JT existentă: {d['racord_Q_tip']} {_f(v)} A")
    for mp in RE_PT_EXIST.finditer(t):
        if "racord" in d and d["racord"] == "tg_existent":
            break
        mid = mp.group("mid") or ""
        if re.search(r"\bnou\b|proiectat", mid):
            continue
        d.setdefault("racord", "pt")
        d["pt_existent"] = True
        # puterea trafo-ului din preajmă („PTAb existent 20/0,4 kV 1000 kVA”, „dupa transformatorul de 1000kVA”)
        fer = t[mp.start():min(len(t), mp.end() + 60)]
        mk = re.search(rf"(?<![\w.,/])(?P<v>{NUM})\s*kva\b", t[max(0, mp.start() - 40):mp.end() + 60])
        if mk and "pt_Sn_kVA" not in d:
            d["pt_Sn_kVA"] = _nr(_num(mk.group("v")))
        e_ = mp.end()
        mu = re.match(r"\s*,?\s*20/0[.,]4\s*kv", t[mp.end():])
        if mu:
            e_ += mu.end()
        # rescris canonic („PT existent”) — regulile vechi citesc PT-ul existent și puterea lui (kVA rămâne în text)
        R.rescrie(mp.start(), e_, "PT existent")
        R.note.append(f"„{t[mp.start():mp.end()].strip()}” = postul de transformare EXISTENT al beneficiarului (racord "
                      "pe barele JT; nu se desenează trafo / celule MT noi)")
        break
    if "racord" not in d and re.search(r"\btdri\b", t) and not nou and not re.search(r"\b(?:pt|ptab?|post\w*)\b", t):
        d.update({"racord": "pt", "pt_existent": True})
        R.note.append("„TDRI” fără PT nou = tabloul JT al postului EXISTENT (racord pe barele JT)")
    if "racord" in d and d.get("racord") == "pt" and not d.get("pt_existent") and nou:
        d.pop("racord")
    mse = RE_SEP_EXIST.search(t)
    if mse:
        d.update({"racord_In_Q_A": _nr(_num(mse.group("v"))), "racord_Q_tip": "gG"})
        R.sterge(mse.start(), mse.end())
        R.note.append(f"„{t[mse.start():mse.end()].strip()}” = protecția EXISTENTĂ a plecării de racord (gG "
                      f"{mse.group('v')} A, în tabloul JT existent)")
    mqe = RE_Q_EXIST.search(t)
    if mqe and R.liber(mqe.start(), mqe.end()):
        R.sterge(mqe.start(), mqe.end())
        R.note.append(f"„{t[mqe.start():mqe.end()].strip()}” = protecția existentă a plecării de racord (calibrul se "
                      "completează în Calcul)")
    if d.get("pt_existent") or d.get("racord") == "tg_existent":
        for mb in re.finditer(r"\bbmpt\w*(?:\s+(?:cu\s+)?masur\w*)?\s+(?:semi-?direct\w*|indirect\w*)", t):
            if R.liber(mb.start(), mb.end()):
                R.sterge(mb.start(), mb.end())
                R.d.setdefault("monitorizare", {})["contor_productie"] = {"tip": "BMPT", "masura": "semidirecta"}
                R.note.append(f"„{t[mb.start():mb.end()].strip()}” = grupul de măsură al CEF (contor de producție, măsură "
                              "semidirectă cu TC); racordul rămâne în PT / TG existent")
    if d:
        R.d["racord"] = d


# ================================================================================================= 5. QG / protecții / monitorizare
RE_QG = re.compile(r"\b(?:intrerup\w*|disjunctor\w*|usol)\s+(?:automat\s+)?(?:de\s+interfata|general\w*|de\s+interfata\s+general\w*)\b"
                   r"(?!\s+(?:al\s+|din\s+)?(?:tg\w*|tablou\w*|pt\w*|bmpt|bransament\w*)\b)")


def _atribute_q(frag: str) -> dict:
    q = {}
    mi = re.search(rf"\bin\s*=\s*(?P<v>{NUM})\s*a\b|(?<![\w.,/x])(?P<v2>\d{{2,4}})\s*a\b(?!\s*/\s*\d)", frag)
    if mi:
        q["In_A"] = _nr(_num(mi.group("v") or mi.group("v2")))
    if re.search(r"motoriz\w*", frag):
        q["motorizat"] = True
    if re.search(r"electronic\w*", frag):
        q["tip"] = "electronic"
    elif re.search(r"termomagnetic\w*", frag):
        q["tip"] = "termomagnetic"
    mk = re.search(rf"\bicu\s*(?:=|:)?\s*(?P<v>{NUM})\s*ka\b|(?P<v2>{NUM})\s*ka\b", frag)
    if mk:
        q["Icu"] = _nr(_num(mk.group("v") or mk.group("v2")))
    mr = re.search(rf"\bir\s*=\s*(?P<f>{NUM})\s*x?\s*in\b|\breglat\w*\s+(?:la\s+)?(?P<f2>{NUM})\s*x\s*in\b", frag)
    if mr:
        q["_Ir_factor"] = _num(mr.group("f") or mr.group("f2"))
    mp = re.search(r"\b([34])\s*p\b|\b([34])\s+poli\b", frag)
    if mp:
        q["poli"] = int(mp.group(1) or mp.group(2))
    return q


def _qg(R: Rez, segs):
    t = R.t
    for m in RE_QG.finditer(t):
        if not R.liber(m.start(), m.end()):
            continue
        a, b = _seg_de(segs, m.start())
        # fragmentul aparatului: până la „comandat / releu / ups / spd / smartlogger / ;” sau la următorul aparat
        e = b
        mstop = re.search(r",\s*(?=comandat|cu\s+releu\s+de\s+interfata|releu|ups|spd|smart|tc\b|bmpt|\d+\s+separato|separato|sigurant)"
                          r"|\bcomandat\w*|\bcu\s+releu\b|\bsmart\w*|\btc\s+\d", t[m.end():b])
        if mstop:
            e = m.end() + mstop.start()
        frag = t[m.start():e]
        q = _atribute_q(frag)
        if not q.get("In_A"):
            continue
        In = q.pop("In_A")
        seg = t[a:b]
        if re.search(r"\btdri\b|\btgjt\b", seg) and "de interfata" not in frag and re.search(r"\bq0\b|general", frag) \
                and RE_PT_NOU.search(t):
            # „În TDRI: întreruptor general Q0 630 A” — Q-ul JT al PT-ului NOU (nu QG-ul centralei)
            R.d["In_Q_JT_A"] = _nr(In)
            R.sterge(m.start(), e)
            R.note.append(f"„{R.orig[m.start():e].strip(' ,')}” = întrerupătorul general JT al PT-ului nou (In_Q_JT_A {_f(In)} A), "
                          "nu QG-ul centralei")
            continue
        qg = {"In_A": _nr(In)}
        if q.get("tip") == "electronic":
            qg["electronic"] = True
        if q.get("motorizat"):
            qg["motorizat"] = True
        if q.get("Icu"):
            qg["Icu_kA"] = q["Icu"]
        if q.get("_Ir_factor"):
            qg["Ir_reglat"] = _nr(In * q["_Ir_factor"])
        R.d["QG"] = qg
        R.d["In_QG_A"] = _nr(In)
        R.sterge(m.start(), e)
        R.note.append(f"„{R.orig[m.start():e].strip(' ,')}” = întrerupătorul general / de interfață al CEF: In_QG {_f(In)} A"
                      + (", declanșator electronic" if qg.get("electronic") else "")
                      + (", motorizat" if qg.get("motorizat") else "")
                      + (f", Icu {_f(qg['Icu_kA'])} kA" if qg.get("Icu_kA") else "")
                      + (f", Ir reglat {_f(qg['Ir_reglat'])} A ({_f(q['_Ir_factor'])} × In)" if qg.get("Ir_reglat") else ""))
        mrel = re.search(r"\b(?:cu\s+|comandat\w*\s+de\s+|si\s+)?releu\w*(?:\s+de\s+interfata|\s+anti-?\s*insularizare)?(?:\s+marca)?(?:\s+abb)?(?:\s+cm-?ufd)?"
                         r"(?:\s+cu\s+separato\w*\s+4p\s+\d+\s*a)?",
                         t[e:b])
        if mrel and mrel.group(0).strip():
            R.sterge(e + mrel.start(), e + mrel.end())
        break
    if "QG" not in R.d:
        mp = re.search(rf"\bplecare\s+(?:q\d+\s+)?(?P<v>{NUM})\s*a\s+(?:motorizat\w*\s+)?(?:spre|catre)\s+(?:te|tablou\w*)[^,;]{{0,30}}?\bcef\b"
                       rf"(?:\s+cu\s+releu\s+de\s+interfata(?:\s+abb)?(?:\s+cm-?ufd)?)?", t)
        if mp:
            v = _num(mp.group("v"))
            R.d["QG"] = {"In_A": _nr(v)}
            R.d["In_QG_A"] = _nr(v)
            R.sterge(mp.start(), mp.end())
            R.note.append(f"„{R.orig[mp.start():mp.end()]}” = plecarea CEF din TDRI = întrerupătorul de interfață (QG {_f(v)} A, cu PI)")


RE_RELEU = re.compile(r"\breleu\w*\s+anti-?\s*insularizare\s+cu\s+separator\s+4p\s+\d+\s*a|\b(?:\d+\s+buc\.?\s+)?releu\w*\s+(?:de\s+(?:protectie\s+)?)?(?:interfata|anti-?\s*insularizare|antiinsularizare)"
                      r"(?:\s+(?:marca|tip))?(?:\s+abb)?(?:\s+cm-?ufd)?|\breleu\w*\s+(?:abb\s+)?cm-?ufd"
                      r"|\breleu\w*\s+anti-?\s*insularizare\s+cu\s+separator\s+4p\s+\d+\s*a")


def _monitorizare(R: Rez, segs):
    t = R.t
    mon = R.d.setdefault("monitorizare", {})
    for m in re.finditer(rf"\b(?:smart\s*-?\s*meter\w*|smartmeter\w*|contor\w*\s+de\s+control)(?P<mod>(?:\s+(?:huawei|janitza|chint))?"
                         rf"(?:\s+(?!cu\b|si\b|in\b|buc\b)[a-z]*\s?\d[\w-]*)?)"
                         rf"(?P<tc>\s+(?:echipat\s+)?cu\s+(?:(?P<ntc>\d)\s+)?(?:tc|transformatoare\s+de\s+curent)(?:\s+(?P<r>\d+/\d+)\s*a?)?)?"
                         rf"(?P<loc>\s+(?:dupa\s+intreruptorul\s+general|in\s+post|in\s+pt\w*|la\s+punctul\s+de\s+racord))?"
                         rf"(?P<buc>\s+buc\.?\s+\d+)?", t):
        if not R.liber(m.start(), m.end()):
            continue
        sm = {}
        mod = (m.group("mod") or "").strip()
        if mod:
            sm["model"] = R.orig[m.start("mod"):m.end("mod")].strip() if hasattr(R, "orig") else mod
        if m.group("r"):
            sm["TC"] = m.group("r")
        if m.group("loc"):
            sm["loc"] = "PT" if re.search(r"post|pt", m.group("loc")) else "racord"
        mon["smart_meter"] = sm or {"prezent": True}
        R.sterge(m.start(), m.end())
        R.note.append(f"„{t[m.start():m.end()].strip()}” = smart meter (monitorizare / limitare, la punctul de racord)")
    if "smart_meter" not in mon:
        m = re.search(r"\b(?:janitza\s+umg\s*\d+|dtsu\s*666[\w-]*|ddsu\s*666[\w-]*)(?:\s+cu\s+(?:\d\s+)?tc\s+(?P<r>\d+/\d+)\s*a?)?", t)
        if m and R.liber(m.start(), m.end()):
            mon["smart_meter"] = {"model": R.orig[m.start():m.end()].split(" cu ")[0].strip() if hasattr(R, "orig") else m.group(0)}
            if m.group("r"):
                mon["smart_meter"]["TC"] = m.group("r")
            R.sterge(m.start(), m.end())
            R.note.append(f"„{t[m.start():m.end()].strip()}” = smart meter (monitorizare / limitare)")
    # „3 TC 1600/5 in post” separat de smart meter (în aceeași propoziție)
    if isinstance(mon.get("smart_meter"), dict) and "TC" not in mon["smart_meter"]:
        m = re.search(r"\b(?:cu\s+)?(?:\d\s+)?(?:tc|transformatoare\s+de\s+curent)\s+(?P<r>\d+/\d+)\s*a?(?:\s+in\s+(?:post|pt)\w*)?", t)
        if m and R.liber(m.start(), m.end()) and re.search(r"smart|janitza|dtsu", t[max(0, m.start() - 80):m.start()]):
            mon["smart_meter"]["TC"] = m.group("r")
            R.sterge(m.start(), m.end())
    for m in re.finditer(r"\b(?:\d+\s+buc\.?\s+)?(?:dispozitiv\w*\s+de\s+(?:comunicatii|monitorizare)\s+)?(?:huawei\s+)?smart\s*-?\s*logger\w*"
                         r"(?:\s*[\d][\w-]*)?(?:\s+buc\.?\s+\d+)?", t):
        if R.liber(m.start(), m.end()):
            mod = re.search(r"\d[\w-]*", m.group(0).split("logger")[-1])
            mon["smartlogger"] = {"model": "SmartLogger " + mod.group(0).upper()} if mod else {"prezent": True}
            R.sterge(m.start(), m.end())
            R.note.append(f"„{t[m.start():m.end()].strip()}” = SmartLogger (monitorizarea invertoarelor, RS485)")
    for m in re.finditer(r"\b(?:magistral\w*\s+|comunicati\w*\s+|cablu\w*\s+de\s+date\s+)?rs\s*-?\s*485\b", t):
        if R.liber(m.start(), m.end()):
            mon["rs485"] = True
            R.sterge(m.start(), m.end())
    for m in re.finditer(rf"\b(?:\d+\s+buc\.?\s+)?(?:alimentat\w*\s+din\s+)?(?:sursa\s+neintreruptibila\s+)?ups\s*(?:ups\s*)?(?P<v>\d+)\s*va\b"
                         rf"(?:\s*,?\s*230\s*v\s*c?\.?a?\.?)?", t):
        if R.liber(m.start(), m.end()):
            mon["ups_releu"] = {"S_VA": int(m.group("v"))}
            R.sterge(m.start(), m.end())
            R.note.append(f"„{t[m.start():m.end()].strip()}” = UPS-ul releului de interfață ({m.group('v')} VA; nu e o plecare UPS)")
    for m in re.finditer(r"\bcontor\w*\s+de\s+productie(?:\s+separat\w*)?|\b(?:bmp[mt]\w*\s+)?masur\w*\s+(?:a\s+)?energie\w*\s+produs\w*"
                         r"|\bcontor\w*\s+(?:energie\s+)?produs\w*", t):
        if R.liber(m.start(), m.end()):
            mon["contor_productie"] = {"tip": "BMPM" if "bmpm" in m.group(0) else ("BMPT" if "bmpt" in m.group(0) else "contor")}
            R.sterge(m.start(), m.end())
            R.note.append(f"„{t[m.start():m.end()].strip()}” = contor de producție separat (măsura energiei produse)")
    for m in RE_RELEU.finditer(t):
        if R.liber(m.start(), m.end()):
            R.sterge(m.start(), m.end())
            R.d["releu_PI"] = t[m.start():m.end()].strip()
            R.note.append(f"„{t[m.start():m.end()].strip()}” = releul protecției de interfață (PI, desenat la QG)")
    if not mon:
        R.d.pop("monitorizare", None)


RE_PROT_INV = re.compile(rf"(?:(?P<n>\d+)\s+(?:buc\.?\s+)?)?(?:cate\s+(?:un\s+)?)?(?P<ap>separato\w*|sigurant\w*\b(?!\s+maxim)|tablou\w*\s+(?:de\s+)?protectie\s+cu\s+sigurant\w*"
                         rf"|intrerup\w*\s+automat\w*|mccb|mcb)"
                         rf"(?P<tipf>(?:(?!\b(?:separato\w*|intrerup\w*|spd|releu\w*|ups|smart\w*|cablu\w*|tc|descarcat\w*)\b)[^;\n]){{0,70}}?)"
                         rf"(?<![\d/,.\-])(?:3\s*x\s*)?(?P<v>\d{{2,4}})\s*a\b"
                         rf"(?P<attr>(?:\s*,?\s*(?:(?:icu|ir)\s*[-=:]?\s*\d+\s*ka|\d+\s*ka\b|cu\s+reglaj\s+electronic(?:\s+[\d,.]+\s*-\s*[\d,.]+\s*x?\s*in)?"
                         rf"|reglat\w*\s+(?:la\s+)?[\d,.]+\s*x\s*in|pe\s+fiecare\s+invertor|buc\.?\s+\d+|curba\s+[bcd]))*)")


def _protectii(R: Rez, segs):
    """Protecțiile pe invertor (tablou de protecție / separator cu siguranțe / întrerupător pe fiecare invertor) și pe
    plecările tablourilor intermediare — candidați; legarea finală în `aplica` (după numărul de invertoare)."""
    t = R.t
    cand = []
    for m in RE_PROT_INV.finditer(t):
        if not R.liber(m.start(), m.end()):
            continue
        a, b = _seg_de(segs, m.start())
        seg = t[a:b]
        ap = m.group("ap") + (m.group("tipf") or "")
        tip = "MCCB" if re.search(r"intrerup|mccb", ap) else ("MCB" if re.search(r"\bmcb|automata", ap) else "gG")
        v = int(m.group("v"))
        attr = m.group("attr") or ""
        if re.search(r"\bgpv\b", ap) or re.match(r"\s*(?:pe\s+(?:fiecare\s+)?string|/\s*string)", t[m.end():m.end() + 20]) \
                or re.search(r"\bplecar\w*\s+(?:noua\s+)?(?:din\s+)?[^,;.]{0,40}$", t[max(a, m.start() - 50):m.start()]):
            continue
        prot = {"In_A": v}
        mk = re.search(r"(?:icu|ir)?\s*[-=:]?\s*(\d+)\s*ka", attr)
        if mk:
            prot["Icu_kA"] = int(mk.group(1))
        mr = re.search(r"reglat\w*\s+(?:la\s+)?([\d,.]+)\s*x\s*in", attr)
        if mr:
            prot["Ir_reglat"] = _nr(_num(mr.group(1)) * v)
        if tip == "MCCB" and re.search(r"electronic", attr):
            prot["electronic"] = True
        mc = re.search(r"curba\s+([bcd])", attr)
        if mc:
            prot["curba"] = mc.group(1).upper()
        ctx = t[max(a, m.start() - 60):min(b, m.end() + 50)]
        rol = None
        if re.search(r"\bpe\s+fiecare\s+invertor|\bfiecare\s+invertor|\bpe\s+invertor|\bde\s+intrare\b|\btablou\w*\s+(?:de\s+)?protectie", ctx + " " + ap) \
                or (RE_CTX_INV.search(seg) and not RE_CTX_TE2.search(seg[:max(0, m.start() - a)])):
            rol = "inv"
        if re.match(r"\s*(?:fiecare|pe\s+fiecare)\s+inverto", seg):
            rol = "inv"
        elif RE_CTX_TE2.search(seg) and (re.search(r"\bplecare|\bspre\s+teg|\bfiecare\s+te\s+secundar", seg) and not re.search(r"invertor", seg)):
            rol = "te2"
        if re.search(r"\bpe\s+fiecare\s+invertor", attr):
            rol = "inv"
        cand.append({"s": m.start(), "e": m.end(), "n": int(m.group("n")) if m.group("n") else None, "tip": tip, "In": v,
                     "rol": rol, "seg": seg, "txt": R.orig[m.start():m.end()] if hasattr(R, "orig") else t[m.start():m.end()],
                     "prot": prot})
    R.d["prot_cand"] = cand


RE_TI = re.compile(r"\b(?:grupat\w*|repartizat\w*|impartit\w*)\s+(?:cate\s+)?(?P<m>\d+)\s+pe\s+(?P<k>\d+)\s+tablouri\s+"
                   r"(?:de\s+interfata\s+|electrice\s+)?(?P<fel>secundar\w*|intermediar\w*)(?:\s+(?P<nume>te-?\d+\s*(?:\.{2,3}|-)\s*te-?\d+))?"
                   r"|\b(?P<k2>\d+)\s+(?:buc\.?\s+)?tablouri\s+(?:de\s+interfata\s+|electrice\s+)?(?P<fel2>secundar\w*|intermediar\w*)"
                   r"(?:\s+(?:a\s+)?cate\s+(?P<m2>\d+)\s+invertoare)?")


def _tablouri_intermediare(R: Rez):
    t = R.t
    m = RE_TI.search(t)
    if not m:
        m2 = re.search(r"\btablou\w*\s+interfata\s+secundar\w*(?:\s*\(\s*proiectat\s*\))?\s+(?P<k>\d+)\s+buc\b", t)
        if m2:
            R.d["ti"] = {"k": int(m2.group("k")), "m": None}
            R.sterge(m2.start(), m2.end())
            R.note.append(f"„{t[m2.start():m2.end()].strip()}” = {m2.group('k')} tablouri intermediare (secundare) de invertoare")
        return
    k = int(m.group("k") or m.group("k2"))
    mm = m.group("m") or m.group("m2")
    R.d["ti"] = {"k": k, "m": int(mm) if mm else None}
    R.sterge(m.start(), m.end())
    R.note.append(f"„{t[m.start():m.end()].strip()}” = {k} tablouri intermediare (secundare) de invertoare"
                  + (f", câte {mm} invertoare" if mm else ""))
    for mx in re.finditer(r"\bmontat\w*\s+in\s+exterior\b", t):
        R.sterge(mx.start(), mx.end())


# ================================================================================================= PT / PC (celule MT)
def _celule(R: Rez):
    t = R.t
    out = {}
    if re.search(r"\bdispozitiv\w*\s+general\w*[^.;]{0,80}?\bintrerup\w*|\bprotecti\w*\s+(?:a\s+)?trafo\w*\s+cu\s+intrerup\w*"
                 r"|\bcelul\w*\s+(?:de\s+)?protecti\w*\s+(?:a\s+)?trafo\w*\s+cu\s+intrerup\w*|\bintrerup\w*\s+sf6", t):
        out["celula_trafo"] = "intreruptor"
        if re.search(r"\bdispozitiv\w*\s+general\w*", t):
            out["dg_intreruptor"] = True
    for m in re.finditer(r"\bprotecti\w*\s+(?:a\s+)?trafo\w*\s+cu\s+intrerup\w*\s+sf6(?:\s+\d+\s*kv)?(?:\s+\d+\s*a)?(?:\s+\d+\s*ka)?"
                         r"(?:\s+cu\s+releu)?(?:\s*,\s*\d\s+tc\s+\d+/\d+)?(?:\s+si\s+tor\s+homopolar)?"
                         r"|\bcelul\w*\s+(?:de\s+)?protecti\w*\s+(?:a\s+)?trafo\w*(?:\s+\d+\s*kva)?(?:\s+cu\s+intrerup\w*)?", t):
        R.sterge(m.start(), m.end())
    ml = re.search(r"\b(?P<n>\d|doua)\s+celule\s+de\s+linie(?:\s+motorizat\w*)?(?:\s+cu\s+aar)?", t)
    if ml:
        n = _int(ml.group("n"))
        out["celule_mt"] = ["linie"] * n
        R.sterge(ml.start(), ml.end())
        R.note.append(f"„{t[ml.start():ml.end()].strip()}” = {n} celule de linie (buclă intrare–ieșire)"
                      + ("; „AAR” = reanclanșarea / comutarea automată a celulelor MT ale OD, nu GE + ATS" if "aar" in ml.group(0) else ""))
    for m in re.finditer(r"\bcu\s+aar\b|\baar\b", t):
        if R.liber(m.start(), m.end()):
            R.sterge(m.start(), m.end())
            R.note.append("„AAR” = automatizarea celulelor MT ale OD (nu GE + ATS)")
    if re.search(r"\bcelul\w*\s+(?:de\s+)?masur\w*", t):
        out.setdefault("celule_mt", ["linie"])
        if "masura" not in out["celule_mt"]:
            out["celule_mt"] = out["celule_mt"] + ["masura"]
    if "celule_mt" in out and out["celule_mt"][-1] != "trafo":
        out["celule_mt"] = out["celule_mt"] + ["trafo"]
    mcl = re.search(r"\bcelule\s*:\s*(?P<l>[^.;\n]+)", t)
    if mcl:
        lst = []
        for mm in re.finditer(r"\b(linie|masura|protectie\s+(?:a\s+)?trafo\w*|trafo)\b", mcl.group("l")):
            k = "trafo" if "trafo" in mm.group(1) else mm.group(1)
            if k not in lst or k == "linie":
                lst.append(k)
        if lst:
            if "trafo" not in lst:
                lst.append("trafo")
            out["celule_mt"] = lst
            if "masura" in lst:
                out["masura"] = "MT"
            R.note.append("celulele MT ale postului: " + ", ".join(lst))
    mpc = re.search(r"\bpunct\w*\s+de\s+conexiune\s+(?:nou\w*|proiectat\w*)?", t)
    if mpc:
        pc = {}
        mcl = re.search(r"\b(\d|doua)\s+celule\s+de\s+linie", t)
        if mcl:
            pc["celule_linie"] = _int(mcl.group(1))
        if re.search(r"\baar\b", t):
            pc["aar"] = True
        msp = re.search(r"\bservici\w*\s+proprii\s+(?:cu\s+)?trafo\w*\s+(\d+(?:[.,]\d+)?)\s*kva", t)
        if msp:
            pc["servicii_proprii_kVA"] = _nr(_num(msp.group(1)))
        if re.search(r"\bscada\b", t):
            pc["scada"] = True
        R.d["punct_conexiune"] = pc or True
        R.note.append("punctul de conexiune (PC) nou: celulele de linie, de măsură și de utilizator ale PC se desenează la "
                      "racordul MT (informativ — PC-ul complet: planșa de racord MT)")
    for m in re.finditer(r"\bcelul\w*\s+(?:de\s+)?utilizator\w*(?:\s+cu\s+protecti\w*\s+de\s+interfata)?|\bservici\w*\s+proprii\s+trafo\s+\d+\s*kva"
                         r"|\bcelul\w*\s+(?:de\s+)?linie\s+sf6|\bcelul\w*\s+(?:de\s+)?(?:linie|racord)\s+(?:utilizator|\(od\))", t):
        if R.liber(m.start(), m.end()):
            R.sterge(m.start(), m.end())
    if out:
        R.d["celule"] = out


# ================================================================================================= date mărunte
def _diverse(R: Rez, segs):
    t = R.t
    d = R.d
    # curentul maxim al invertorului („Iac max 160 A fiecare”, „100 kW, Imax 160,4 A”) / al centralei („CEF … Imax 481 A”)
    for m in re.finditer(rf"\b(?:iac|i\s*ac|imax|i\s*max|i\(max\))\s*(?:max\w*)?\s*(?:=|:|-)?\s*(?P<v>{NUM})\s*a\b(?:\s+fiecare)?", t):
        if not R.liber(m.start(), m.end()):
            continue
        pre = t[max(0, m.start() - 60):m.start()]
        a, _ = _seg_de(segs, m.start())
        if re.search(r"\binverto\w*|ktl|\bsun2000|\bx\s+huawei|\d+\s*kw\s*,?\s*$", pre[-45:]) and not re.search(r"\bcef\b|\bpi\b", t[a:m.start()][-25:]):
            d["Iac_max_A"] = _nr(_num(m.group("v")))
            R.note.append(f"„{R.orig[m.start():m.end()]}” = curentul maxim c.a. al unui invertor (Iac_max_A)")
        else:
            R.note.append(f"„{R.orig[m.start():m.end()]}” = curentul maxim total al centralei (sumă de control)")
        R.sterge(m.start(), m.end())
    m = re.search(rf"\(\s*(?P<v>{NUM})\s*a\s+max\w*\s*\)", t)
    if m:
        d["Iac_max_A"] = _nr(_num(m.group("v")))
        R.sterge(m.start(), m.end())
        R.note.append(f"„{R.orig[m.start():m.end()]}” = curentul maxim c.a. al invertorului (Iac_max_A)")
    # fișa modulului: Vmp / Imp / siguranța maximă în serie / tensiunea maximă de sistem
    mod = {}
    for rx, k in ((rf"\b(?:vmp\w*|umpp|vmpp)\s*(?:=|:)?\s*(?P<v>{NUM})\s*v\b", "Vmpp_V"),
                  (rf"\b(?:imp|impp|impp)\s*(?:=|:)?\s*(?P<v>{NUM})\s*a\b", "Impp_A"),
                  (rf"\bsigurant\w*\s+(?:maxim\w*|serie\s+maxim\w*)\s*(?:=|:|de)?\s*(?P<v>{NUM})\s*a\b", "I_rev_A"),
                  (rf"(?<=,\s)(?P<v>1000|1500)\s*v\b(?=\s*[.,;])", "Umax_sistem_V")):
        m = re.search(rx, t)
        if m and R.liber(m.start(), m.end()) and re.search(r"\bmodul|\bpanou|\bvoc|\bisc", t[max(0, m.start() - 80):m.start()]):
            mod[k] = _nr(_num(m.group("v")))
            R.sterge(m.start(), m.end())
    if mod:
        d["modul_fisa"] = mod
        R.note.append("fișa modulului: " + ", ".join(f"{k} {_f(v)}" for k, v in mod.items()))
    # transformatoarele de curent (măsură)
    for m in re.finditer(r"\b(?:(?P<n>\d+)\s+(?:buc\.?|bucati)\s+)?(?:(?P<n2>\d)\s+)?(?:tc|transformato\w*\s+de\s+curent)\s+"
                         r"(?P<r>\d+/\d+(?:/\d+)?)\s*a?(?:\s*,?\s*cl(?:as[ae])?\.?\s*[\d,.]+\s*s?\b)?(?:\s+buc\.?\s+\d+)?"
                         r"(?:\s+in\s+(?:postul\s+de\s+transformare|post\w*|pt\w*)(?:\s+ptab?)?(?:\s+20/0[.,]4\s*kv)?(?:\s+existent\w*)?)?"
                         r"(?:\s*,?\s*dupa\s+transformato\w*\s+de\s+\d+\s*kva)?(?:\s+si)?", t):
        if not R.liber(m.start(), m.end("r")):
            continue
        ctx = t[max(0, m.start() - 80):m.start()]
        mon = d.setdefault("monitorizare", {})
        txt = R.orig[m.start():m.end()].strip()
        if re.search(r"bmpt|semidirect", ctx) and isinstance(mon.get("contor_productie"), dict) \
                and not re.search(r"post|\bpt", m.group(0)) and "TC" not in mon["contor_productie"]:
            mon["contor_productie"]["TC"] = m.group("r")
            R.note.append(f"„{txt}” = TC-urile grupului de măsură al CEF")
        elif re.search(r"post|\bpt", m.group(0)) or re.search(r"smart|janitza|dtsu", ctx):
            sm = mon.get("smart_meter")
            if not isinstance(sm, dict):
                sm = mon["smart_meter"] = {}
            sm.setdefault("TC", m.group("r"))
            if re.search(r"post|\bpt", m.group(0)):
                sm["loc"] = "PT"
            R.note.append(f"„{txt}” = TC-urile smart meter-ului (la punctul de racord)")
        else:
            R.note.append(f"„{txt}” = transformatoare de curent de măsură (informativ)")
        R.sterge(m.start(), m.end())
    # numele tablourilor fără valori („Tablou interfata TE-CEF:”, „tablou electric de interfata invertoare TE-CEF echipat cu”)
    for m in re.finditer(r"\btablou\w*\s+(?:electric\s+)?(?:de\s+)?(?:interfata|antiinsularizare)(?:\s+invertoare)?(?:\s+(?:general|principal))?"
                         r"(?:\s+[a-z]+-[a-z0-9]+)?(?:\s+echipat\s+cu)?(?=\s*[:;,(]|\s+echipat|\s*$|\s+buc|\s+aici|\s+\d+\s*kwp)", t):
        if R.liber(m.start(), m.end()):
            R.sterge(m.start(), m.end())
            R.note.append(f"„{R.orig[m.start():m.end()].strip()}” = tabloul de interfață al CEF (TGD-CF, cu QG + PI)")
    for m in re.finditer(r"(?:^|(?<=[\s.;]))in\s+(?:teg|te|td|tgd|tablou\w*)(?:[\s-][a-z0-9]+)?\s*:", t):
        if R.liber(m.start(), m.end()):
            R.sterge(m.start(), m.end())
    for m in re.finditer(r"\blegatur\w*\s+[a-z0-9\-]+(?:\s+[a-z0-9\-]+)?\s*-\s*", t):
        if R.liber(m.start(), m.end()):
            R.sterge(m.start(), m.end())
    # puterea c.a. a centralei („o putere maxima in AC de 1.6 MW si o putere efectiva de 1.6 MW”)
    m = re.search(rf"\b(?:o\s+)?putere\w*\s+maxim\w*\s+(?:in\s+)?(?:ac|c\.?a\.?)\s+(?:de\s+)?(?P<v>{NUM})\s*(?P<u>kw|mw)\b"
                  rf"(?:\s+si\s+o\s+putere\s+efectiv\w*\s+de\s+{NUM}\s*(?:kw|mw))?(?:\s+cuprinde\s+urmatoarele\s+elemente)?", t)
    if m:
        v = _num(m.group("v")) * (1000 if m.group("u") == "mw" else 1)
        d.setdefault("Pn_total_kW", _nr(v))
        R.sterge(m.start(), m.end())
        R.note.append(f"„{R.orig[m.start():m.end()]}” = puterea c.a. a centralei (Pn_total_kW {_f(v)} kW, sumă de control)")
    # MT: separatorul de racord de pe stâlp
    for m in re.finditer(r"\bseparato\w*\s+vertical\w*\s+(?:\d+\s*kv|steap\w*)(?:\s+\d+\s*kv)?(?:\s+cu\s+clp)?", t):
        if R.liber(m.start(), m.end()):
            R.sterge(m.start(), m.end())
            R.note.append(f"„{R.orig[m.start():m.end()]}” = separatorul MT de racord (pe stâlp, instalația OD — planșa de racord MT)")
    # prosumator: branșamentul / BMPM OD / tabloul AC al invertorului / tabloul consumatorului (existent)
    m = re.search(rf"\bbransament\w*\s+(?:existent\w*\s+)?(?:(?:trifazat|monofazat)\w*\s+)?(?:de\s+)?(?P<v>{NUM})\s*a\b"
                  rf"|\bbmp[mt]\w*\s+od\s+(?:bidirectional\w*\s+)?(?:1p\+n|3p\+n)?\s*(?P<v2>{NUM})\s*a\b", t)
    if m and R.liber(m.start(), m.end()):
        d["In_Q_bransament_A"] = _nr(_num(m.group("v") or m.group("v2")))
        R.sterge(m.start(), m.end())
        R.note.append(f"„{R.orig[m.start():m.end()]}” = protecția branșamentului existent (In_Q_bransament_A)")
    m = re.search(rf"\btablou\w*\s+te-?ac\s+(?:inverto\w*\s+)?(?:ip\d+\s+)?cu\s+(?P<ap>rcbo|mcb|intrerup\w*)\s+(?:1p\+n\s+|2p\s+|4p\s+)?"
                  rf"(?P<v>{NUM})\s*a(?:\s*/\s*\d+\s*ma)?(?:\s+\d+\s*ka)?", t)
    if m and R.liber(m.start(), m.end()):
        d["In_QG_A_pros"] = _nr(_num(m.group("v")))
        R.sterge(m.start(), m.end())
        R.note.append(f"„{R.orig[m.start():m.end()]}” = tabloul AC al invertorului: protecția invertorului (QG {m.group('v')} A, "
                      f"{m.group('ap').upper()})")
    for a, b in segs:
        seg = t[a:b]
        if re.match(r"\s*(?:spre\s+)?(?:bmp[mt]\w*\s+)?(?:masur\w*\s+(?:a\s+)?)?energie\w*\s+produs|\s*spre\s+bmp[mt]\w*\s+masur", seg) \
                or re.match(r"\s*(?:spre\s+)?tablou\w*\s+(?:al\s+)?consumator", seg):
            prod = "produs" in seg
            for m in re.finditer(r"\b(?:f\d+|q\d+(?:\.\d+)?|rcbo|rccb|mcb|ddr)(?:\s+(?:1p\+n|2p|4p))?\s+\d+\s*a(?:\s*/\s*\d+\s*ma)?(?:\s+\d+\s*ka)?", seg):
                if R.liber(a + m.start(), a + m.end()):
                    R.sterge(a + m.start(), a + m.end())
                    if prod:
                        d.setdefault("aparate_productie", []).append(R.orig[a + m.start():a + m.end()])
            R.note.append(("BMPM-ul de producție" if prod else "tabloul consumatorului") + ": aparatele din text "
                          "(informativ, desenate ca bloc standard)")
        if re.match(r"\s*tablou\w*\s+(?:al\s+)?consumator\w*\s*:", seg):
            for m in re.finditer(r"\b(?:rcbo|rccb|mcb|ddr)(?:\s+(?:1p\+n|2p|4p))?\s+\d+\s*a(?:\s*/\s*\d+\s*ma)?|\bcircuite\s+(?=c\d)"
                                 r"|\bc\d+(?:\s*-\s*c\d+)?\s+\d+\s*a\b|\b(?:tablou\w*\s+(?:al\s+)?consumator\w*\s*:)", seg):
                if R.liber(a + m.start(), a + m.end()):
                    R.sterge(a + m.start(), a + m.end())
            R.note.append("tabloul consumatorului (existent): Q general și circuitele C1…Cn din text — informativ (nu se "
                          "redimensionează)")


# ================================================================================================= intrare
def preextrage(text: str):
    """Întoarce (text_rămas, date, note). Fără text PV / de proiectant → textul neschimbat (doar capcanele de vocabular
    generale: TT de măsură, „Ir = kA”)."""
    if not text:
        return text, {}, []
    t = norm(text)
    R = Rez(t)
    R.orig = text
    _tt_tensiune(R)
    _ir_ka(R)
    if not RE_PV.search(t):
        if not R.sterse and not R.rescrieri:
            return text, {}, []
        return R.text(text), {}, R.note
    segs = segmente(t)
    _atr_kva_kw(R)
    _puteri(R)
    _model_kv(R)
    _buc_deviz(R, text)
    linii = _linii_invertoare(R)
    R.d["linii"] = linii
    _racord(R)
    _qg(R, segs)
    _monitorizare(R, segs)
    _tablouri_intermediare(R)
    _celule(R)
    _cabluri(R, segs, linii)
    _protectii(R, segs)
    for c in R.d.get("prot_cand") or []:
        if c["rol"] or c["n"]:
            R.sterge(c["s"], c["e"])
    _diverse(R, segs)
    for m in re.finditer(r"\b(?:\d+\s+buc\.?\s+)?(?:descarcat\w*|spd)(?:\s+(?:de\s+)?supratensiun\w*)?(?:\s+(?:tip\s+)?(?:t?[12]\b(?:\s*(?:\+|si)\s*t?2\b)?|dpx3))*"
                         rf"(?:\s+(?:3p\+n/pe|4p|3p))?(?:\s+\d+\s*(?:ka|a))?(?:\s+230\s*v)?", t):
        if R.liber(m.start(), m.end()) and m.group(0).strip():
            R.d["spd"] = True
            R.sterge(m.start(), m.end())
            R.note.append(f"„{t[m.start():m.end()].strip()}” = descărcător de supratensiuni c.a. (SPD, desenat la tablou)")
    return R.text(text), R.d, R.note


# ================================================================================================= aplicare
def _grupuri_n1(inv: list, n: int) -> list | None:
    """Grupurile de invertoare ca listă de n invertoare individuale (pentru legarea pe rânduri)."""
    tot = sum(g.get("n") or 1 for g in inv)
    if tot != n:
        return None
    out = []
    for g in inv:
        for _ in range(g.get("n") or 1):
            out.append(dict(g, n=1))
    return out


def _filtreaza(c, rx):
    c.intrebari[:] = [q for q in c.intrebari if not re.search(rx, q[1])]
    c.probleme[:] = [p for p in c.probleme if not re.search(rx, p[1])]


def aplica(c, intr: dict, ex: dict, tip, I):
    D = getattr(c, "_reale", None) or {}
    if not D or tip not in ("cef", "prosumator"):
        if D and tip in ("pt", "tablou") and D.get("celule"):
            pass
        return
    note = []
    inv = intr.get("invertoare") or []
    n_inv = sum(g.get("n") or 1 for g in inv)
    # ---- 2. rânduri INVk
    linii = D.get("linii") or []
    if linii and inv:
        ind = _grupuri_n1(inv, len(linii)) if n_inv == len(linii) else None
        if ind:
            for g, l in zip(ind, linii):
                if l.get("n_str") and not l.get("n_mppt"):
                    frate = next((l2 for g2, l2 in zip(ind, linii) if l2 is not l and l2.get("n_mppt")
                                  and g2.get("model") and g2.get("model") == g.get("model")), None)
                    if frate:
                        l["n_mppt"] = frate["n_mppt"]
                        note.append(f"{l['eticheta'].upper()}: {frate['n_mppt']} MPPT (același model ca {frate['eticheta'].upper()})")
                    else:
                        c.intrebari.append(("I02", f"{l['eticheta'].upper()}: câte intrări MPPT are invertorul (cele {l['n_str']} "
                                                   "stringuri se împart pe MPPT)?"))
            for g, l in zip(ind, linii):
                if l.get("n_str") and l.get("n_mod"):
                    p, k, inegal = _string_pe_mppt(l["n_str"], l["n_mod"], l.get("n_mppt"))
                    g["string"] = {"n_module": l["n_mod"], "n_stringuri_paralel": p, "n_MPPT": k}
                    note.append(f"{l['eticheta'].upper()}: {l['n_str']} stringuri × {l['n_mod']} module (pe invertor)"
                                + (f", {l['n_mppt']} MPPT" if l.get("n_mppt") else "") + f" → {k} MPPT × {p} stringuri în "
                                f"paralel" + (" (repartizare inegală pe MPPT — verificați)" if inegal else ""))
                    if l.get("n_module_tot") and l["n_module_tot"] != l["n_str"] * l["n_mod"]:
                        c.intrebari.append(("I08", f"{l['eticheta'].upper()}: {l['n_module_tot']} module, dar stringurile dau "
                                                   f"{l['n_str']} × {l['n_mod']} = {l['n_str'] * l['n_mod']}. Care e configurația?"))
                elif l.get("n_module_tot"):
                    g["_n_module"] = l["n_module_tot"]
            inv = intr["invertoare"] = ind
            st = intr.get("string")
            if st and all(g.get("string") for g in ind):
                intr.pop("string", None)
                for k_ in ("Uoc_V", "Isc_A", "gpv", "gpv_In_A"):
                    if k_ in st:
                        for g in ind:
                            g["string"][k_] = st[k_]
        else:
            c.intrebari.append(("I05", f"Textul are {len(linii)} rânduri de invertoare ({', '.join(l['eticheta'] for l in linii)}), "
                                       f"dar am găsit {n_inv} invertoare: care rând aparține cărui invertor?"))
    # ---- MPPT: „N stringuri x M, K MPPT” global (un singur rând)
    st = intr.get("string")
    if isinstance(st, dict) and st.get("n_MPPT") and st.get("n_stringuri_paralel") and not re.search(r"\bpe\s+mppt|/\s*mppt", c.t) \
            and st["n_stringuri_paralel"] > 1 and not linii:
        n_s = st["n_stringuri_paralel"]
        p, k, inegal = _string_pe_mppt(n_s, st.get("n_module"), st["n_MPPT"])
        st["n_stringuri_paralel"], st["n_MPPT"] = p, k
        note.append(f"{n_s} stringuri (pe invertor) pe {k} MPPT → {p} stringuri în paralel pe MPPT"
                    + (" (repartizare inegală — verificați)" if inegal else ""))
    # ---- 3. racord
    rac = D.get("racord") or {}
    if rac:
        if rac.get("racord") == "pt" and intr.get("racord") not in (None, "bmpt", "pt"):
            rac = {k: v for k, v in rac.items() if k != "racord"}
        for k in ("racord", "pt_existent", "pt_Sn_kVA", "racord_In_Q_A", "racord_Q_tip"):
            if k in rac:
                intr[k] = rac[k]
                if k in ("racord", "pt_existent"):
                    ex[k] = rac[k]
        if rac.get("racord") == "tg_existent":
            intr.pop("pt_existent", None)
            for k in ("celule_mt", "celula_trafo", "masura"):
                intr.pop(k, None)
        if rac.get("pt_existent") or rac.get("racord") == "tg_existent":
            _filtreaza(c, r"Confirmați PT propriu|Unde se racordează centrala|două puncte de racord|în BMPT existent")
    # ---- 1. cabluri
    tronsoane_c0, mt, te2_cab, nelegate = [], [], [], []
    for cb in D.get("cabluri") or []:
        d = {k: v for k, v in cb["d"].items() if not k.startswith("_")}
        L = d.pop("L_m", None)
        fel = cb["fel"]
        txt = c_txt(cb)
        if cb["d"].get("_L_lista"):
            k_ = n_inv if fel == "inv" and n_inv > 1 and re.search(r"\binvertoare\b", cb["segtxt"]) else 1
            tot = cb["d"].get("_L_total") or L
            if L and k_ > 1:
                L = _nr(L / k_)
            if L:
                c.intrebari.append(("I02", f"„{txt}”: {_f(tot)} m e cantitatea din listă; desenat cu L = {_f(L)} m pe cablu "
                                           f"(÷ {k_ * (cb['d'].get('n_fortat') or 1)}, presupus). Care e lungimea traseului?"))
        if fel == "inv" and tip == "prosumator":
            intr["cablu_inv"] = dict(d)
            if L:
                intr["L_inv_m"] = L
            if isinstance(intr.get("cablu"), dict) and intr["cablu"].get("S_fortat") == d.get("S_fortat"):
                intr.pop("cablu")
            note.append(f"„{txt}” = cablul invertorului (cablu_inv)" + (f", L = {_f(L)} m" if L else ""))
        elif fel == "inv":
            if cb.get("linie") is not None and linii and len(inv) == len(linii):
                g = inv[linii.index(cb["linie"])]
                g["cablu"] = dict(d)
                if L:
                    g["L_m"] = L
                if all(g_.get("cablu") for g_ in inv):
                    intr.pop("cablu_inv", None)
            else:
                intr["cablu_inv"] = dict(intr.get("cablu_inv") or {}, **d)
                if L:
                    intr["L_inv_m"] = L
            note.append(f"„{txt}” = cablul invertorului" + (f" {cb['linie']['eticheta'].upper()}" if cb.get("linie") else "")
                        + " (invertor → tablou), nu C0" + (f"; L = {_f(L)} m" if L else "")
                        + (f" (din intervalul {cb['d']['_L_interval']}, cel mai lung)" if cb["d"].get("_L_interval") else ""))
            if cb["d"].get("_paralel_fara_numar"):
                c.intrebari.append(("I02", f"„{txt}” … „în paralel”: câte cabluri în paralel pe fiecare invertor?"))
        elif fel == "c0":
            tronsoane_c0.append((d, L, cb))
        elif fel == "mt":
            mt.append((d, L, cb))
        elif fel == "te2":
            te2_cab.append((d, L, cb))
        elif fel == "productie":
            mon = intr.setdefault("monitorizare", {})
            cp = mon.get("contor_productie") if isinstance(mon.get("contor_productie"), dict) else {"tip": "BMPM"}
            cp["cablu"] = dict(d)
            if L:
                cp["L_m"] = L
            if D.get("aparate_productie"):
                cp["aparate"] = list(D["aparate_productie"])
            mon["contor_productie"] = cp
            note.append(f"„{txt}” = cablul spre contorul de producție (BMPM / BMPT producție)" + (f", {_f(L)} m" if L else ""))
        elif fel == "coloana":
            if tip == "prosumator":
                if L:
                    intr["L_coloana_m"] = L
                note.append(f"„{txt}” = coloana branșamentului (BMPM / BMPT → tablou)" + (f", L = {_f(L)} m" if L else "")
                            + " — existentă, informativ")
            else:
                tronsoane_c0.append((d, L, cb))
        elif fel == "trafo_tdri":
            note.append(f"„{txt}” = legătura trafo → TDRI din postul de transformare (informativ)")
        else:
            nelegate.append((d, L, cb))
    if tronsoane_c0:
        d0, L0, cb0 = tronsoane_c0[0]
        c0 = dict(d0)
        if len(tronsoane_c0) > 1:
            c0["tronsoane"] = [dict(d, L_m=L) if L else dict(d) for d, L, _ in tronsoane_c0]
        intr["cablu_C0"] = c0
        Ls = [L for _, L, _ in tronsoane_c0 if L]
        if Ls:
            intr["L_racord_m"] = _nr(sum(Ls))
        else:
            intr.pop("L_racord_m", None)
            c.intrebari.append(("I02", f"Ce lungime are legătura tablou CEF → punct de racord („{c_txt(cb0)}”)? Desenată cu L = 30 m "
                                       "(presupus)."))
            intr["L_racord_m"] = 30
        note.append("C0 (tablou CEF → punctul de racord): " + " + ".join(
            f"„{c_txt(cb)}”" + (f" {_f(L)} m" if L else "") for _, L, cb in tronsoane_c0)
            + (f" — {len(tronsoane_c0)} tronsoane, L = {_f(sum(Ls))} m" if len(tronsoane_c0) > 1 else ""))
        for d, L, cb in tronsoane_c0:
            if cb["d"].get("_paralel_fara_numar"):
                c.intrebari.append(("I02", f"„{c_txt(cb)}” … „în paralel”: câte cabluri în paralel pe C0?"))
    elif (D.get("cabluri") and any(cb["fel"] in ("inv", "mt", "te2") for cb in D["cabluri"])
          and intr.get("cablu_C0", {}).get("S_fortat") is None):
        # C0-ul vechi venea din cablul invertorului / MT — se scoate (motorul îl alege)
        if "L_racord_m" in intr and not any(cb["fel"] == "c0" for cb in D["cabluri"]):
            intr.pop("L_racord_m", None)
    if not tronsoane_c0 and any(cb["fel"] in ("inv", "mt", "te2") for cb in D.get("cabluri") or []):
        c0 = intr.get("cablu_C0") or {}
        if c0.get("S_fortat"):
            intr.pop("cablu_C0", None)
            intr.pop("L_racord_m", None)
    if mt:
        d, L, cb = mt[0]
        cm = {"S_mm2": d.get("S_fortat"), "material": d.get("material") or "Al"}
        if d.get("tip_cablu"):
            cm["tip"] = d["tip_cablu"]
        seg = c.t if False else cb["segtxt"]
        trs = [int(x) for x in re.findall(r"(?<![\w.,])(\d+)\s*m\b", seg)]
        if len(trs) > 1:
            cm["tronsoane"] = [{"L_m": x} for x in trs]
            cm["L_m"] = sum(trs)
        elif L:
            cm["L_m"] = L
        intr["cablu_MT"] = {k: v for k, v in cm.items() if v is not None}
        note.append(f"„{c_txt(cb)}” = cablul MT de racord (cablu_MT, informativ; nu C0)"
                    + (f": tronsoane {' + '.join(str(x) for x in trs)} m" if len(trs) > 1 else ""))
        if intr.get("L_racord_m") and not tronsoane_c0 and abs((intr.get("L_racord_m") or 0) - (L or -1)) < 1e-6:
            intr.pop("L_racord_m", None)
    # ---- tablouri intermediare
    ti = D.get("ti")
    if ti or te2_cab:
        k = (ti or {}).get("k") or 1
        m_ = (ti or {}).get("m")
        if not m_ and n_inv and n_inv % k == 0:
            m_ = n_inv // k
        tabl = []
        for i in range(k):
            x = {"nume": f"TE-{i + 1}"}
            if te2_cab:
                d, L, cb = te2_cab[0]
                x["cablu"] = dict(d)
                if L:
                    x["L_m"] = L
            tabl.append(x)
        if te2_cab and te2_cab[0][2]["d"].get("_paralel_fara_numar"):
            c.intrebari.append(("I02", f"Plecarea fiecărui tablou intermediar („{c_txt(te2_cab[0][2])}” în paralel): câte cabluri "
                                       "în paralel?"))
        intr["tablouri_intermediare"] = tabl
        if m_ and len(inv) == 1 and n_inv == k * m_ and k > 1:
            intr["invertoare"] = inv = [dict(inv[0], n=m_, tablou=i + 1) for i in range(k)]
            intr.pop("n_tgd_cf", None)
        note.append(f"{k} tablouri intermediare (TE-1…TE-{k})" + (f", câte {m_} invertoare" if m_ else "")
                    + " → tablouri_intermediare[]; fiecare cu plecarea proprie spre tabloul general (TEG / TE de interfață)")
        if not m_:
            c.intrebari.append(("I05", f"Cum se împart cele {n_inv} invertoare pe cele {k} tablouri intermediare?"))
    # ---- protecții
    for p in D.get("prot_cand") or []:
        rol = p["rol"]
        if rol is None and p["n"] and n_inv and p["n"] == n_inv and p["tip"] == "gG":
            rol = "inv"
        if rol is None and p["n"] and intr.get("tablouri_intermediare") and p["n"] in (len(intr["tablouri_intermediare"]),
                                                                                         2 * len(intr["tablouri_intermediare"])):
            rol = "te2" if p["In"] > 250 else "inv"
        if rol == "inv" and inv:
            for g in inv:
                g["prot_tip"] = p["tip"]
                g["protectie"] = dict(p["prot"])
            note.append(f"„{p['txt'].strip()}” = protecția fiecărui invertor ({p['tip']} {p['In']} A; invertoare[].prot_tip)")
        elif rol == "te2" and intr.get("tablouri_intermediare"):
            for x in intr["tablouri_intermediare"]:
                x["prot_tip"] = p["tip"]
                x.update({k: v for k, v in p["prot"].items()})
            note.append(f"„{p['txt'].strip()}” = protecția plecării fiecărui tablou intermediar ({p['tip']} {p['In']} A)")
        elif p["rol"] or p["n"]:
            note.append(f"„{p['txt'].strip()}” = aparat de protecție (informativ; locul lui nu e clar din text)")
    # ---- QG, monitorizare, puteri
    if D.get("Iac_max_A"):
        if tip == "prosumator":
            intr["Iac_max_A"] = D["Iac_max_A"]
        for g in intr.get("invertoare") or []:
            g["Iac_max_A"] = D["Iac_max_A"]
    if D.get("modul_fisa"):
        intr["modul"] = dict(intr.get("modul") or {}, **D["modul_fisa"])
        st_ = intr.get("string") or {}
        for a_, b_ in (("Uoc_V", "Voc_V"), ("Isc_A", "Isc_A")):
            if a_ in st_:
                intr["modul"].setdefault(b_, st_[a_])
    if D.get("In_Q_JT_A"):
        intr["In_Q_JT_A"] = D["In_Q_JT_A"]
    if D.get("In_Q_bransament_A"):
        intr["In_Q_bransament_A"] = D["In_Q_bransament_A"]
    if D.get("In_QG_A_pros") and tip == "prosumator":
        intr["In_QG_A"] = D["In_QG_A_pros"]
    if D.get("QG"):
        intr["QG"] = D["QG"]
    if D.get("In_QG_A"):
        intr["In_QG_A"] = D["In_QG_A"]
    if D.get("monitorizare"):
        intr["monitorizare"] = D["monitorizare"]
    if D.get("Pn_total_kW"):
        intr["Pn_total_kW"] = D["Pn_total_kW"]
        inv_ = intr.get("invertoare") or []
        sig = sum((g.get("n") or 1) * (g.get("Pn_kW") or 0) for g in inv_)
        rest = [g for g in inv_ if not g.get("model") and abs((g.get("Pn_kW") or 0) - D["Pn_total_kW"]) < 0.01]
        if rest and len(inv_) > 1:
            intr["invertoare"] = [g for g in inv_ if g not in rest]
            sig = sum((g.get("n") or 1) * (g.get("Pn_kW") or 0) for g in intr["invertoare"])
        if sig and abs(sig - D["Pn_total_kW"]) > 0.5:
            c.intrebari.append(("I08", f"Puterea nominală totală a invertoarelor e scrisă {_f(D['Pn_total_kW'])} kW, dar "
                                       f"invertoarele dau {_f(sig)} kW: care e corectă?"))
    cel = D.get("celule") or {}
    if cel and intr.get("racord") != "tg_existent" and not intr.get("pt_existent"):
        for k, v in cel.items():
            intr[k] = v
        if cel.get("celula_trafo"):
            note.append("celula trafo cu întrerupător (dispozitivul general al utilizatorului, protecții 50/51, 51N)")
    if nelegate:
        c.intrebari.append(("I05", "Unde se leagă " + "; ".join(f"„{c_txt(cb)}”" + (f" ({_f(L)} m)" if L else "")
                                                                 for _, L, cb in nelegate)
                                   + ": cablul invertorului (invertor → tablou), C0 (tablou → racord) sau alt segment? "
                                     "(fără context nu îl leg)"))
    _forma_motor(intr, D, tip)
    for n in note:
        c.nota(n)
    # cheile vechi care nu mai au sens
    if intr.get("racord") in ("pt", "tg_existent") and intr.get("pt_existent") and "atr_jt" in intr and not re.search(r"\batr\b", c.t):
        intr.pop("atr_jt", None)


def _tc_primar(r):
    m = re.match(r"\s*(\d+)\s*/", str(r or ""))
    return int(m.group(1)) if m else None


def _forma_motor(intr: dict, D: dict, tip):
    """Forma finală a cheilor r12, așa cum le citește motorul (engine/calc/scheme.py, constructor.monitorizare)."""
    mon = intr.get("monitorizare")
    pi = {}
    if isinstance(mon, dict):
        sm = mon.get("smart_meter")
        if isinstance(sm, dict):
            x = {}
            if sm.get("model"):
                x["model"] = sm["model"]
            if _tc_primar(sm.get("TC")):
                x["TC_primar_A"] = _tc_primar(sm["TC"])
            mon["smart_meter"] = x or True
        sl = mon.get("smartlogger")
        if isinstance(sl, dict):
            mon["smartlogger"] = {"model": sl["model"]} if sl.get("model") else True
        ups = mon.pop("ups_releu", None)
        if isinstance(ups, dict) and ups.get("S_VA"):
            pi["ups_VA"] = ups["S_VA"]
        cp = mon.get("contor_productie")
        if isinstance(cp, dict):
            cp = {k: v for k, v in cp.items() if k not in ("masura", "TC")}
            tc = _tc_primar((mon.get("contor_productie") or {}).get("TC"))
            if tc:
                cp["TC_primar_A"] = tc
            if tip == "prosumator":
                intr["contor_productie"] = cp
                mon.pop("contor_productie")
            else:
                mon["contor_productie"] = cp
        if not mon:
            intr.pop("monitorizare")
    if D.get("releu_PI"):
        mr = re.search(r"(abb\s+)?cm-?ufd\w*", D["releu_PI"])
        pi["releu"] = (mr.group(0).upper() if mr else "releu de interfață")
    if pi:
        intr["protectie_interfata"] = dict(intr.get("protectie_interfata") or {}, **pi)
    c0 = intr.get("cablu_C0")
    if isinstance(c0, dict) and c0.get("tronsoane"):
        c0["tronsoane"] = [dict({k: v for k, v in x.items() if k != "L_m"}, **({"L": x["L_m"]} if x.get("L_m") else {}))
                           for x in c0["tronsoane"]]
    if D.get("punct_conexiune") and tip in ("cef", "pt"):
        intr["punct_conexiune"] = D["punct_conexiune"]


def c_txt(cb) -> str:
    return cb.get("txt") or cb["m"].group(0).strip()


def corecteaza_tip(c, tip):
    """r12: textul are invertoare / panouri, nu GE → CEF (nu „ge_ats” din „AAR / în paralel / TT”)."""
    D = getattr(c, "_reale", None) or {}
    if tip == "ge_ats" and D and RE_PV.search(c.t) and not re.search(r"\bgrup\w*\s+electrogen|\bgenerator\w*|\bge\b|\bdiesel", c.t):
        c.nota("text de centrală PV (invertoare, panouri) fără grup electrogen → CEF (nu GE + ATS)")
        return "cef"
    return tip
