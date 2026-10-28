"""documente_protectii — evaluarea necesității SPD și curbele timp-curent generice (E2).

* evaluare_spd(inp, m)              SR HD 60364-4-443 (art. 443.4 / 443.5, CRL) + SR HD 60364-7-712 (Lcrit pe c.c.):
                                    decizie (necesar / recomandat / nenecesar), tipul (T1+T2 / T2 / T3), Up, In / Iimp,
                                    și concordanța cu SPD-urile desenate.
* curba(aparat)                     benzile timp-curent generice (t_min / t_max) ale unui aparat: MCB B/C/D
                                    (SR EN 60898-1), fuzibil gG (SR EN 60269-1, porțile din norme.GG_PORTI_A), MCCB
                                    termomagnetic și electronic LSI (SR EN 60947-2). NU sunt curbele producătorului.
* curbe_timp_curent(m, r)           curbele tuturor protecțiilor planșei + perechile amonte / aval + Ik max / min —
                                    datele pe care desenul le randează (log-log).
"""
import math

from .calc import norme
from . import documente_tabele as dt

# ------------------------------------------------------------------------------------------------------- SPD
FENV = {"rural": 85.0, "suburban": 85.0, "urban": 850.0}          # SR HD 60364-4-443 art. 443.5
NG_IMPLICIT = 3.0       # densitatea trăsnetelor la sol [trăsnete/km²/an] — PRESUPUS (RO ≈ 1,5…4,5; Ng ≈ 0,1·Td)
# SR HD 60364-7-712 tab. 712.1: Lcrit [m] = K / Ng
LCRIT_K = {"locuinta": 115.0, "cladire": 450.0, "sol": 200.0}
CONSECINTE_OBLIGATORIU = {
    "viata": "consecințe asupra vieții umane (spitale, siguranță, servicii de urgență)",
    "servicii_publice": "întreruperea serviciilor publice / patrimoniu cultural",
    "activitate": "întreruperea activității comerciale sau industriale",
    "multe_persoane": "un număr mare de persoane în același loc (clădiri publice, birouri, școli)",
}


def _bool(v):
    return v is True or str(v).strip().lower() in ("da", "true", "1", "yes")


def _spd_desenate(m):
    ca, cc = [], []

    def walk(o):
        if isinstance(o, dict):
            t = o.get("tip")
            p = o.get("param") or {}
            if t == "spd" or p.get("sablon") == "spd_ca":
                ca.append({"ref": o.get("ref"), "tip": p.get("tip") or "", "poli": p.get("poli")})
            elif t == "spd_cc" or p.get("sablon") == "spd_cc":
                cc.append({"ref": o.get("ref"), "Ucpv_V": p.get("Ucpv_V")})
            for k, v in o.items():
                if k not in ("lista", "spec", "note", "cartus", "calc", "calc_rezumat"):
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk({k: (m or {}).get(k) for k in ("intrari", "bara", "plecari")})
    return ca, cc


def evaluare_spd(inp, m=None):
    """inp = intrarea fizică; datele chestionarului în inp["evaluare_spd"] (toate opționale):
    LPS (instalație de paratrăsnet), alimentare_aeriana, mediu (rural / suburban / urban), Ng, L_PAL_km, L_PCL_km,
    L_PAH_km, L_PCH_km, consecinte (viata / servicii_publice / activitate / multe_persoane / altele),
    locuinta_unifamiliala_valoare_redusa, echipamente_sensibile, L_cc_m (c.c. invertor ↔ module), tip_cladire_pv
    (locuinta / cladire / sol)."""
    inp = inp if isinstance(inp, dict) else {}
    q = inp.get("evaluare_spd") if isinstance(inp.get("evaluare_spd"), dict) else {}
    presupus = []
    tip_schema = inp.get("tip_schema")
    lps = _bool(q.get("LPS"))
    aerian = _bool(q.get("alimentare_aeriana"))
    mediu = str(q.get("mediu") or "").lower() or None
    if mediu not in FENV:
        mediu = "rural"
        presupus.append("mediu rural / suburban (fenv = 85) — nedeclarat")
    ng = q.get("Ng")
    try:
        ng = float(ng)
        if ng <= 0:
            raise ValueError
    except (TypeError, ValueError):
        ng = NG_IMPLICIT
        presupus.append(f"Ng = {dt._f(ng)} trăsnete/km²/an (harta densității trăsnetelor nu a fost consultată)")

    def km(k):
        try:
            return min(max(float(q.get(k)), 0.0), 1.0)
        except (TypeError, ValueError):
            return None
    lpal, lpcl, lpah, lpch = km("L_PAL_km"), km("L_PCL_km"), km("L_PAH_km"), km("L_PCH_km")
    if all(x is None for x in (lpal, lpcl, lpah, lpch)):
        # art. 443.5: lungimile necunoscute → 1 km (linia aeriană JT dacă alimentarea e aeriană, altfel cablu JT)
        if aerian:
            lpal = 1.0
        else:
            lpcl = 1.0
        presupus.append("lungimea liniei de alimentare JT = 1 km (" + ("aeriană" if aerian else "în cablu") + ", art. 443.5)")
    lp = 2 * (lpal or 0) + (lpcl or 0) + 0.4 * (lpah or 0) + 0.2 * (lpch or 0)
    crl = FENV[mediu] / (lp * ng) if lp > 0 else math.inf
    cons = str(q.get("consecinte") or "").lower()
    motive = []
    if cons in CONSECINTE_OBLIGATORIU:
        necesar, temei = True, f"art. 443.4: {CONSECINTE_OBLIGATORIU[cons]} — protecția este obligatorie"
    elif _bool(q.get("locuinta_unifamiliala_valoare_redusa")) and not lps:
        necesar, temei = False, ("art. 443.4: locuință unifamilială la care valoarea instalației și a echipamentelor nu "
                                 "justifică protecția — SPD nu este obligatoriu (recomandat)")
    else:
        necesar = crl < 1000.0
        temei = (f"art. 443.5: CRL = fenv / (LP·Ng) = {dt._f(FENV[mediu], 0)} / ({dt._f(lp, 2)} × {dt._f(ng)}) = "
                 f"{dt._f(crl, 0) if crl != math.inf else '∞'} " + ("< 1000 → protecție necesară" if necesar
                                                                       else "≥ 1000 → protecția nu este cerută de risc"))
    if lps:
        necesar = True
        motive.append("clădirea are instalație de protecție la trăsnet (LPS) → SPD tip 1 la originea instalației "
                      "(SR EN 62305-4, SR HD 60364-5-534)")
    if aerian:
        motive.append("alimentare din linie aeriană JT → SPD tip 1 + 2 recomandat la intrarea în clădire")
    pv = tip_schema in ("cef", "prosumator")
    if pv:
        motive.append("instalație fotovoltaică: SR HD 60364-7-712 art. 712.443 / 712.534 — SPD pe c.a. la invertor și "
                      "la tablou (cablu > 10 m)")
    tip = "T1+T2" if (lps or aerian) else "T2"
    alim = inp.get("alimentare") if isinstance(inp.get("alimentare"), dict) else {}
    retea_mono = inp.get("retea") == "mono" or alim.get("retea") == "mono"
    tt = str(inp.get("schema_pamant") or "").upper() == "TT"
    poli = ("1P+N" if retea_mono else "3P+N") if tt else ("1P+N" if retea_mono else "4P")
    rec_ca = {"necesar": necesar or pv, "tip": tip, "poli": poli,
              "Up_kV": 1.5 if _bool(q.get("echipamente_sensibile")) else 2.5,
              "In_kA": 20.0, "Iimp_kA": 12.5 if "T1" in tip else None,
              "conexiune": ("CT2 (3+1, N–PE cu eclator)" if tt else "CT1 (L–PE, N–PE)"),
              "protectie_amonte": "conform fișei SPD (MCB C25…C63 sau gG 63 A); derivație ≤ 0,5 m (art. 534.4.8)",
              "T3": bool(_bool(q.get("echipamente_sensibile"))),
              "decizie": ("NECESAR" if necesar else "RECOMANDAT" if pv or aerian else "NECERUT DE RISC (opțional)")}
    if rec_ca["T3"]:
        motive.append("echipamente sensibile → SPD tip 3 (Up ≤ 1,5 kV) la mai puțin de 10 m de echipament")
    rec_cc = None
    if pv:
        cl = str(q.get("tip_cladire_pv") or ("sol" if tip_schema == "cef" and not q.get("pe_cladire") else
                                            "locuinta" if tip_schema == "prosumator" else "cladire"))
        if cl not in LCRIT_K:
            cl = "cladire"
        lcrit = LCRIT_K[cl] / ng
        L = q.get("L_cc_m") or inp.get("L_cc_m") or ((inp.get("cablu_cc") or {}).get("L_m") if isinstance(inp.get("cablu_cc"), dict) else None)
        try:
            L = float(L)
        except (TypeError, ValueError):
            L = None
        nec_cc = True if L is None else L >= lcrit
        if L is None:
            presupus.append("lungimea c.c. invertor ↔ module necunoscută → SPD c.c. considerat necesar (prudent)")
        rec_cc = {"necesar": nec_cc or lps, "Lcrit_m": lcrit, "L_m": L, "tip_cladire": cl,
                  "tip": "T1+T2 (c.c.)" if lps else "T2 (c.c.)",
                  "Ucpv_V": "≥ Uoc,max al stringului la Tmin (SR EN 61643-31)",
                  "temei": (f"SR HD 60364-7-712 tab. 712.1: Lcrit = {dt._f(LCRIT_K[cl], 0)} / Ng = {dt._f(lcrit, 0)} m; "
                            + (f"L = {dt._f(L, 0)} m " + ("≥" if nec_cc else "<") + " Lcrit" if L is not None else "L necunoscut"))}
    ca_des, cc_des = _spd_desenate(m) if m else ([], [])
    neconc = []
    if m is not None and tip_schema in ("tablou", "cascada", "locuinta", "cef", "prosumator"):
        # branșamentul (BMPT / BMPM al OD), PT-ul și GE-ul nu conțin tabloul consumatorului: SPD-ul e acolo
        if rec_ca["necesar"] and not ca_des:
            neconc.append(f"evaluarea cere SPD c.a. {tip}, dar planșa nu are niciun SPD c.a.")
        if rec_ca["necesar"] and "T1" in tip and ca_des and not any("T1" in (x.get("tip") or "") for x in ca_des):
            neconc.append(f"evaluarea cere SPD tip 1 (LPS / linie aeriană), planșa are doar {', '.join(x.get('tip') or '?' for x in ca_des)}")
        if rec_cc and rec_cc["necesar"] and not cc_des:
            neconc.append("evaluarea cere SPD pe c.c., dar planșa nu are SPD c.c.")
    return {"ca": rec_ca, "cc": rec_cc, "CRL": None if crl == math.inf else crl, "LP_km": lp, "Ng": ng, "fenv": FENV[mediu],
            "temei": temei, "motive": motive, "presupus": presupus, "spd_desenate": {"ca": ca_des, "cc": cc_des},
            "neconcordante": neconc,
            "nota_memoriu": (f"Evaluarea protecției la supratensiuni (SR HD 60364-4-443): {temei}. Decizie: SPD c.a. "
                             f"{rec_ca['decizie'].lower()}, tip {tip}, {poli}, Up ≤ {dt._f(rec_ca['Up_kV'])} kV"
                             + (f"; c.c.: {rec_cc['temei']} → " + ("SPD c.c. necesar" if rec_cc["necesar"] else "SPD c.c. necerut")
                                if rec_cc else "") + ".")}


# ------------------------------------------------------------------------------------------------------- curbe
def _logspace(a, b, n):
    la, lb = math.log10(a), math.log10(b)
    return [10 ** (la + (lb - la) * i / (n - 1)) for i in range(n)]


T_MIN_S, T_MAX_S = 0.004, 10000.0
MCB_MAGNETIC = {"B": (3.0, 5.0), "C": (5.0, 10.0), "D": (10.0, 20.0), "K": (8.0, 14.0), "Z": (2.0, 3.0)}


def _putere(x0, t0, x1, t1):
    """t = a·(x − 1)^(−b) prin două puncte (x = I/In)"""
    b = math.log(t0 / t1) / math.log((x1 - 1) / (x0 - 1))
    a = t0 * (x0 - 1) ** b
    return lambda x: a * (x - 1) ** (-b) if x > 1 else T_MAX_S


def _clip(t):
    return min(max(t, T_MIN_S), T_MAX_S)


def curba_mcb(In, curba="C"):
    """SR EN 60898-1: 1,13·In nedeclanșare 1 h, 1,45·In declanșare < 1 h, 2,55·In 1…60 s (In ≤ 32 A; 120 s peste);
    zona magnetică B 3–5·In, C 5–10·In, D 10–20·In (≤ 0,1 s)"""
    lo, hi = MCB_MAGNETIC.get(str(curba).upper(), MCB_MAGNETIC["C"])
    tmax255 = 60.0 if In <= 32 else 120.0
    fmin = _putere(1.13, 3600.0, 2.55, 1.0)
    fmax = _putere(1.45, 3600.0, 2.55, tmax255)
    I, tmin, tmax = [], [], []
    for x in _logspace(1.13, max(hi * 3, 30.0), 48):
        I.append(x * In)
        tmin.append(_clip(fmin(x)) if x < lo else T_MIN_S)
        tmax.append(T_MAX_S if x < 1.45 else (_clip(fmax(x)) if x < hi else 0.1))
    return {"I_A": I, "t_min_s": tmin, "t_max_s": tmax, "model": f"MCB curba {curba} (SR EN 60898-1, bandă generică)"}


def _interp_loglog(pct, x):
    """interpolare log-log pe puncte (I, t) sortate după I; extrapolare I²t = const peste ultimul punct"""
    if x <= pct[0][0]:
        return pct[0][1]
    for (x0, t0), (x1, t1) in zip(pct, pct[1:]):
        if x <= x1:
            f = (math.log(x) - math.log(x0)) / (math.log(x1) - math.log(x0))
            return math.exp(math.log(t0) + f * (math.log(t1) - math.log(t0)))
    x1, t1 = pct[-1]
    return t1 * (x1 / x) ** 2


def curba_gg(In):
    """fuzibil gG (SR EN 60269-1): Inf = 1,25·In / If = 1,6·In la timpul convențional; porțile 10 s / 5 s / 0,1 s"""
    porti = norme.GG_PORTI_A
    k = min(porti, key=lambda v: abs(v - In))
    imin10, imax5, imin01, imax01 = porti[k]
    s = In / k
    tconv = 3600.0 if In <= 63 else 7200.0 if In <= 160 else 10800.0 if In <= 400 else 14400.0
    jos = [(1.25 * In, tconv), (imin10 * s, 10.0), (imin01 * s, 0.1)]
    sus = [(1.6 * In, tconv), (imax5 * s, 5.0), (imax01 * s, 0.1)]
    I, tmin, tmax = [], [], []
    for x in _logspace(1.25 * In, imax01 * s * 4, 48):
        I.append(x)
        tmin.append(_clip(_interp_loglog(jos, x)))
        tmax.append(_clip(_interp_loglog(sus, x)) if x >= 1.6 * In else T_MAX_S)
    return {"I_A": I, "t_min_s": tmin, "t_max_s": tmax, "model": f"fuzibil gG {dt._f(In, 0)} A (SR EN 60269-1, porți)"}


def curba_mccb_tm(In, Ir=None, Im=None):
    """MCCB termomagnetic (SR EN 60947-2): 1,05·Ir nedeclanșare 2 h, 1,30·Ir declanșare < 2 h; 6·Ir ≈ 4…15 s
    (bandă generică); Im ± 20 %"""
    Ir = Ir or In
    Im = Im or 10 * In
    fmin = _putere(1.05, 7200.0, 6.0, 4.0)
    fmax = _putere(1.30, 7200.0, 6.0, 15.0)
    I, tmin, tmax = [], [], []
    for x in _logspace(1.05, max(3 * Im / Ir, 30.0), 48):
        i = x * Ir
        I.append(i)
        tmin.append(T_MIN_S if i >= 0.8 * Im else _clip(fmin(x)))
        tmax.append(0.05 if i >= 1.2 * Im else (_clip(fmax(x)) if x >= 1.3 else T_MAX_S))
    return {"I_A": I, "t_min_s": tmin, "t_max_s": tmax, "model": "MCCB termomagnetic (SR EN 60947-2, bandă generică)"}


def curba_electronic(In, Ir=None, tr=None, Isd=None, tsd=None, Ii=None):
    """declanșator electronic LSI: L — t = tr·(6·Ir/I)², toleranță Ir 1,05…1,20; S — Isd ± 10 %, tsd (timp definit);
    I — Ii ± 10 %, 0,01…0,05 s"""
    Ir = Ir or In
    tr = tr or 10.0
    Ii = Ii or 12 * In
    I, tmin, tmax = [], [], []
    for x in _logspace(1.05, max(3 * Ii / Ir, 30.0), 56):
        i = x * Ir
        I.append(i)
        tl_min = tr * 0.8 * (6.0 / x) ** 2 if x >= 1.2 else T_MAX_S
        tl_max = tr * 1.2 * (6.0 / (x / 1.2)) ** 2 if x >= 1.2 else T_MAX_S
        if x < 1.05:
            tl_min = T_MAX_S
        if Isd and tsd is not None:
            if i >= 1.1 * Isd:
                tl_min = min(tl_min, tsd * 0.8)
                tl_max = min(tl_max, tsd + 0.05)
            elif i >= 0.9 * Isd:
                tl_min = min(tl_min, tsd * 0.8)
        if i >= 1.1 * Ii:
            tl_min, tl_max = T_MIN_S, 0.05
        elif i >= 0.9 * Ii:
            tl_min = T_MIN_S
        tmin.append(_clip(tl_min))
        tmax.append(_clip(tl_max))
    return {"I_A": I, "t_min_s": tmin, "t_max_s": tmax, "model": "declanșator electronic LSI (SR EN 60947-2, generic)"}


def curba(aparat):
    """banda timp-curent generică a unui aparat din planșă ({tip, param}); None dacă aparatul nu are curbă"""
    if not isinstance(aparat, dict):
        return None
    tip = aparat.get("tip")
    p = aparat.get("param") or {}
    In = p.get("In_A")
    if not isinstance(In, (int, float)) or In <= 0:
        return None
    if tip in ("mcb", "rcbo"):
        return curba_mcb(float(In), p.get("curba") or "C")
    if tip in ("fuzibil", "sep_fuzibil", "siguranta"):
        return curba_gg(float(In))
    if tip in ("mccb", "acb", "intreruptor"):
        if p.get("decl") == "EL" or p.get("Isd_A") or tip == "acb":
            return curba_electronic(float(In), p.get("Ir_A"), p.get("tr_s"), p.get("Isd_A"), p.get("tsd_s"),
                                    p.get("Ii_A") or p.get("Im_A"))
        return curba_mccb_tm(float(In), p.get("Ir_A"), p.get("Im_A"))
    return None


def curbe_timp_curent(m, r=None):
    """curbele generice ale protecțiilor + perechile amonte → aval (pe arborele planșei) + Ik la bornele aparatului"""
    pot = dt._Potrivire(r)
    aparate, perechi = [], []

    def ad(a, b, amp):
        c = curba(a)
        if not c:
            return None
        aparate.append({"ref": a.get("ref") or "", "tip": a.get("tip"), "eticheta": " · ".join(a.get("spec") or []),
                        "amplasare": amp, "curba": c,
                        "Ik3max_A": (b or {}).get("Ik3max_origine_kA") and b["Ik3max_origine_kA"] * 1000.0,
                        "Ik1min_A": (b or {}).get("Ik1min_capat_A")})
        return a.get("ref") or ""

    principal = None
    for it in m.get("intrari") or []:
        b = pot.gaseste(it.get("cablu_ca") or it.get("cablu"))
        for a in it.get("aparate") or []:
            if a.get("existent"):
                continue
            ref = ad(a, b, dt._titlu(it.get("sursa")))
            if ref and a.get("tip") in ("mccb", "acb", "mcb", "rcbo", "sep_fuzibil", "fuzibil") and len(m.get("intrari") or []) == 1:
                principal = ref

    def pl(lst, amonte):
        for p in lst or []:
            b = pot.gaseste(p.get("cablu"))
            ref = None
            for a in p.get("aparate") or []:
                ref = ad(a, b, dt._titlu(p.get("sarcina"))) or ref
            if ref and amonte:
                perechi.append({"amonte": amonte, "aval": ref})
            pl(p.get("copii"), ref or amonte)
    pl(m.get("plecari"), principal)
    return {"aparate": aparate, "perechi": perechi, "axe": {"I": "A (log)", "t": "s (log)", "t_min_s": T_MIN_S, "t_max_s": T_MAX_S},
            "nota": "Curbe GENERICE normalizate (benzi din standardele de produs), nu curbele producătorului — "
                    "ilustrează selectivitatea deja verificată în calcul; pentru recepție se folosesc tabelele producătorului."}
