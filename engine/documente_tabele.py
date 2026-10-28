"""documente_tabele — vederi derivate din planșă (model) + calcul, pentru predare / recepție / PIF (E2, funcționalitățile
preluate de la concurență, teste/echipa1/concurenta.md):

* tabel_cabluri(m, r)        jurnalul de cabluri: ref, de la → la, tip, secțiune, L, pozare, Ib, Iz', ΔU, protecție
* fisa_reglaje(m, r)         reglajele protecțiilor (Ir, tr, Isd, tsd, Ii, curbă, IΔn) + Ik3max / Ik1min la fiecare nod
* dimensionare_carcasa(m)    numărul de module DIN, rânduri, rezervă 20–30 %, carcasa propusă
* pierderi_cabluri(m, r)     pierderi I²R pe c.c. și c.a. (kW, %), energie anuală pierdută estimată (CEF / prosumator)
* grupuri_tipice(m)          invertoarele identice („tipic pentru N”) — datele pentru desen
* tabel_xlsx / tabel_html    exportul oricărui tabel de mai sus (Excel / HTML → PDF)

Referințele (Q…, W…, C…) sunt cele de pe planșă; valorile numerice vin din calcul (aceleași ca în memoriu), potrivite
pe ramură după textul cablului și lungime. Schemele desenate manual au doar valorile din parametrii planșei.
"""
import io
import math
import re

from .calc import norme

NB = " "

METODE_POZARE = {
    "A1": "conductoare izolate în tub, în perete izolat termic", "A2": "cablu multipolar în tub, în perete izolat termic",
    "B1": "conductoare izolate în tub pe / în perete", "B2": "cablu multipolar în tub pe / în perete",
    "C": "aparent pe perete / pe tavan (cu bride)", "D1": "în tub îngropat în pământ", "D2": "direct în pământ (armat)",
    "E": "cablu multipolar în aer liber / pe pat perforat", "F": "cabluri monopolare în aer liber / pe pat perforat",
    "G": "cabluri monopolare distanțate, în aer liber",
}
# aparate care protejează (intră în fișa de reglaje și în curbele timp-curent)
TIPURI_PROTECTIE = {"mcb", "mccb", "acb", "rcbo", "rccb", "fuzibil", "sep_fuzibil", "siguranta", "gpv", "intreruptor"}


def _f(x, d=1):
    if x is None or x == "":
        return ""
    if isinstance(x, str):
        return x
    s = f"{x:.{d}f}".replace(".", ",")
    if "," in s:
        s = s.rstrip("0").rstrip(",")
    return s


def _n(t):
    return re.sub(r"[  ]", " ", str(t or "")).strip()


def _cheie_cablu(text):
    """textul cablului fără lungime / „existent” / tipul (rezistent la foc) — cheia de potrivire model ↔ calcul"""
    t = _n(text).split(" · L")[0]
    t = re.sub(r"^(existent|nou)\s*·\s*", "", t)
    return re.sub(r"\s+", " ", t).strip().upper()


# ------------------------------------------------------------------------------------------------ ramurile calculului
def ramuri_calc(r):
    """ramurile dimensionate din rezultatul calculului (orice dict cu secțiune), în ordinea parcurgerii"""
    out = []
    vazut = set()

    def walk(o, cale):
        if isinstance(o, dict):
            if id(o) in vazut:
                return
            vazut.add(id(o))
            if o.get("S_faza_mm2") is not None and (o.get("Ib_A") is not None or o.get("L_m") is not None):
                out.append(dict(o, _cale=cale))
            for k, v in o.items():
                if k in ("regim_GE",):        # al doilea regim al aceleiași ramuri (GE) — nu e alt cablu
                    continue
                walk(v, cale + (k,))
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, cale + (i,))
    walk((r or {}).get("rezultat") or {}, ())
    return out


class _Potrivire:
    """ramurile calculului indexate după (textul cablului, L) și (S, L, n) — fiecare ramură se folosește o singură dată"""

    def __init__(self, r):
        self.idx = {}
        self.idx2 = {}
        for b in ramuri_calc(r):
            L = b.get("L_m")
            k1 = (_cheie_cablu(b.get("cablu") or ""), round(float(L), 1) if isinstance(L, (int, float)) else None)
            self.idx.setdefault(k1, []).append(b)
            k2 = (b.get("S_faza_mm2"), k1[1], b.get("n_paralel") or 1)
            self.idx2.setdefault(k2, []).append(b)
        self.folosit = set()

    def gaseste(self, cablu):
        if not isinstance(cablu, dict):
            return None
        par = cablu.get("param") or {}
        L = par.get("L_m")
        Lr = round(float(L), 1) if isinstance(L, (int, float)) else None
        for lst in (self.idx.get((_cheie_cablu(cablu.get("text")), Lr)) or [],
                    self.idx2.get((par.get("S_faza_mm2"), Lr, par.get("n_paralel") or 1)) or []):
            for b in lst:
                if id(b) not in self.folosit:
                    self.folosit.add(id(b))
                    return b
        return None


# ------------------------------------------------------------------------------------------------ nodurile planșei
def _titlu(x):
    if isinstance(x, dict):
        return _n(x.get("titlu") or x.get("eticheta") or "")
    return _n(x)


def noduri(m):
    """nodurile planșei care au cablu: {nod, de_la, la, rol, cale}. Intrările: sursa → tabloul; plecările: tabloul /
    plecarea părinte → receptor."""
    tab = _titlu(m.get("carcasa")) or "tablou"
    out = []
    for i, it in enumerate(m.get("intrari") or []):
        sursa = _titlu(it.get("sursa")) or f"intrarea {i + 1}"
        inv = next((a.get("ref") for a in it.get("aparate") or [] if a.get("tip") in ("invertor", "convertor_bess", "generator")), None)
        out.append({"nod": it, "de_la": sursa, "la": inv or tab, "rol": "intrare_cc" if inv else "intrare", "cablu": it.get("cablu"),
                    "cale": ("intrari", i, "cablu")})
        if it.get("cablu_ca"):
            out.append({"nod": it, "de_la": inv or sursa, "la": tab, "rol": "intrare", "cablu": it.get("cablu_ca"),
                        "cale": ("intrari", i, "cablu_ca")})

    def pl(lst, parinte, cale):
        for i, p in enumerate(lst or []):
            la = _titlu(p.get("sarcina")) or next((a.get("ref") for a in p.get("aparate") or [] if a.get("ref")), "") or f"plecarea {i + 1}"
            out.append({"nod": p, "de_la": parinte, "la": la, "rol": "plecare", "cablu": p.get("cablu"), "cale": cale + (i,)})
            if p.get("copii"):
                pl(p["copii"], la, cale + (i, "copii"))
    pl(m.get("plecari"), tab, ("plecari",))
    return out


def _protectie_nod(nod):
    for a in nod.get("aparate") or []:
        if a.get("tip") in TIPURI_PROTECTIE:
            return a
    return None


def _ref_cablu(n, i, folosite):
    """referința cablului: cea de pe planșă (C1, C2 …), altfel W + numărul aparatului care îl protejează (Q2.1 → W2.1),
    altfel W + numărul de ordine; cablurile c.c. → Wcc-<invertor>. Unică în tabel."""
    c = n.get("cablu") or {}
    if c.get("ref"):
        ref = c["ref"]
    elif n["rol"] == "intrare_cc":
        ref = f"Wcc-{n['la']}"
    else:
        a = _protectie_nod(n["nod"])
        mq = re.match(r"^Q(\d[\d.]*)$", (a or {}).get("ref") or "")
        ref = f"W{mq.group(1)}" if mq else f"W{i}"
    baza, k = ref, 2
    while ref in folosite:
        ref = f"{baza}.{k}" if not baza.endswith(tuple("0123456789")) or "." in baza else f"{baza}/{k}"
        k += 1
    folosite.add(ref)
    return ref


_RE_TIP_CABLU = re.compile(r"^(?:\d+\s*×\s*\()?\s*([A-Z0-9](?:[A-Z0-9/-]|b(?=[A-Z]))*[A-Z](?:[A-Z0-9/-]|b(?=[A-Z]))*(?:\s+FE180/E90)?)(?:\s+(.*))?$")


def _tip_formatie(cablu_txt):
    """„2 × (ACYAbY 4×120 mm² + FY 1×35 mm² (PE))” → („ACYAbY”, „4×120 mm² + FY 1×35 mm² (PE)”)"""
    mt = _RE_TIP_CABLU.match(cablu_txt)
    if not mt:
        return "", cablu_txt
    f = (mt.group(2) or "").strip()
    if re.match(r"^\d+\s*×\s*\(", cablu_txt) and f.endswith(")"):
        f = f[:-1]
    return mt.group(1), f


# ------------------------------------------------------------------------------------------------ tabelul de cabluri
COLOANE_CABLURI = [("ref", "Ref."), ("de_la", "De la"), ("la", "La"), ("tip", "Tip cablu"), ("formatie", "Formație / secțiune"),
                   ("conductoare", "Conductoare"), ("n_paralel", "Nr. paralel"), ("L_m", "L [m]"), ("metoda", "Pozare"),
                   ("Ib_A", "Ib [A]"), ("Iz_A", "Iz' [A]"), ("dU_pct", "ΔU ramură [%]"), ("dU_cumulat_pct", "ΔU cumulat [%]"),
                   ("protectie", "Protecție"), ("Ik3max_kA", "Ik3max origine [kA]"), ("Ik1min_A", "Ik1min capăt [A]"),
                   ("observatii", "Observații")]


def tabel_cabluri(m, r=None):
    """jurnalul de cabluri al planșei (o linie pe cablu; cablurile identice în paralel = o linie cu „nr. paralel”)"""
    pot = _Potrivire(r)
    rows = []
    folosite = set()
    for i, n in enumerate(noduri(m), 1):
        c = n.get("cablu") or {}
        txt = _n(c.get("text"))
        if not txt or txt.lower() in ("—", "-"):
            continue
        par = c.get("param") or {}
        b = pot.gaseste(c) or {}
        cablu_txt = txt.split(" · L")[0]
        cablu_txt = re.sub(r"^(existent|nou)\s*·\s*", "", cablu_txt)
        tip, formatie = _tip_formatie(cablu_txt)
        L = par.get("L_m", b.get("L_m"))
        prot = _protectie_nod(n["nod"]) if n["rol"] != "intrare_cc" else None
        met = par.get("metoda") or b.get("metoda")
        obs = []
        if "existent" in txt.lower() or (n["nod"].get("existent") if isinstance(n["nod"], dict) else False):
            obs.append("existent")
        if par.get("rezistent_foc") or "FE180" in txt:
            obs.append("rezistent la foc E90")
        if txt.lower().startswith("conform atr") or "conform ATR" in txt:
            obs.append("conform ATR (OD)")
        if n["rol"] == "intrare_cc":
            obs.append("c.c. — cablu solar EN 50618")
        rows.append({
            "ref": _ref_cablu(n, i, folosite), "de_la": n["de_la"], "la": n["la"], "tip": tip, "formatie": formatie,
            "conductoare": c.get("cond") or "", "n_paralel": par.get("n_paralel") or b.get("n_paralel") or 1,
            "material": par.get("material") or b.get("material") or "", "S_faza_mm2": par.get("S_faza_mm2") or b.get("S_faza_mm2"),
            "L_m": L, "metoda": met or "", "metoda_text": METODE_POZARE.get(met or "", ""),
            "Ib_A": b.get("Ib_A"), "Iz_A": par.get("Iz_corectat_A") or b.get("Iz_corectat_A"),
            "dU_pct": par.get("dU_ramura_pct", b.get("dU_ramura_pct")), "dU_cumulat_pct": b.get("dU_cumulat_pct"),
            "dU_limita_pct": b.get("dU_limita_pct"),
            "protectie": (f"{prot.get('ref', '')} " + " · ".join(prot.get("spec") or [])).strip() if prot else "",
            "Ik3max_kA": b.get("Ik3max_origine_kA"), "Ik1min_A": b.get("Ik1min_capat_A"),
            "observatii": "; ".join(obs), "cale": list(n["cale"]), "din_calcul": bool(b)})
    note = ["Ib, ΔU cumulat și Ik provin din calcul (aceleași valori ca în memoriul de calcul); Iz' = Iz tabel × factorii "
            "de corecție (temperatură, grupare, sol).",
            "Lungimile marcate în calcul ca presupuse se confirmă pe traseu înainte de comanda cablurilor."]
    if not any(x["din_calcul"] for x in rows):
        note.append("Schema nu are calcul (desen manual): coloanele Ib / ΔU cumulat / Ik sunt goale.")
    return {"titlu": "TABEL DE CABLURI", "coloane": COLOANE_CABLURI, "randuri": rows, "note": note}


# ------------------------------------------------------------------------------------------------ fișa de reglaje
COLOANE_REGLAJE = [("ref", "Aparat"), ("amplasare", "Circuit / amplasare"), ("tip", "Tip"), ("poli", "Poli"), ("In_A", "In [A]"),
                   ("curba", "Curbă / declanșator"), ("Ir_A", "Ir [A]"), ("tr_s", "tr [s]"), ("Isd_A", "Isd [A]"),
                   ("tsd_s", "tsd [s]"), ("Ii_A", "Ii / Im [A]"), ("IdN_mA", "IΔn [mA]"), ("tip_ddr", "Tip DDR"),
                   ("Icu_kA", "Icu / Icn [kA]"), ("Ik3max_kA", "Ik3max la borne [kA]"), ("Ik1min_A", "Ik1min capăt [A]"),
                   ("verificat", "Verificat la PIF")]


def _rand_reglaj(a, amplasare, b, ddr_asociat=None):
    p = a.get("param") or {}
    prot = (b or {}).get("protectie") or {}
    tip = a.get("tip")
    decl = p.get("decl") or prot.get("decl")
    curba = p.get("curba") or (("electronic LSI" if decl == "EL" else "termomagnetic" if decl == "TM" else "")
                               if tip in ("mccb", "acb") else "gG" if tip in ("fuzibil", "sep_fuzibil", "siguranta")
                               else "gPV" if tip == "gpv" else "")
    rnd = {"ref": a.get("ref") or "", "amplasare": amplasare, "tip": tip.upper() if tip else "", "poli": p.get("poli") or "",
           "In_A": p.get("In_A") or prot.get("In_A"), "curba": curba,
           "Ir_A": p.get("Ir_A") or prot.get("Ir_A"), "tr_s": p.get("tr_s") or prot.get("tr_s"),
           "Isd_A": p.get("Isd_A") or prot.get("Isd_A"), "tsd_s": p.get("tsd_s") or prot.get("tsd_s"),
           "Ii_A": p.get("Ii_A") or p.get("Im_A") or prot.get("Ii_A") or prot.get("Im_A"),
           "IdN_mA": p.get("IdN_mA"), "tip_ddr": p.get("tip_ddr") or "", "selectiv": bool(p.get("selectiv")),
           "Icu_kA": p.get("Icu_kA") or p.get("Icn_kA") or prot.get("Icu_kA"),
           "Ik3max_kA": (b or {}).get("Ik3max_origine_kA"), "Ik1min_A": (b or {}).get("Ik1min_capat_A"),
           "verificat": "", "param": p}
    if tip in ("mcb", "rcbo") and rnd["Ii_A"] is None and p.get("In_A") and p.get("curba") in ("B", "C", "D"):
        rnd["Ii_A"] = {"B": 5, "C": 10, "D": 20}[p["curba"]] * p["In_A"]      # pragul superior al zonei magnetice
    if tip == "rccb" and p.get("selectiv"):
        rnd["tip_ddr"] = (rnd["tip_ddr"] + " · S").strip(" ·")
    return rnd


def fisa_reglaje(m, r=None):
    """fișa de reglaje a protecțiilor + Ik la fiecare nod (pentru recepție / PIF)"""
    pot = _Potrivire(r)
    rows, ik = [], []
    for n in noduri(m):
        b = pot.gaseste(n.get("cablu")) if n["rol"] != "intrare_cc" else None
        amp = f"{n['de_la']} → {n['la']}"
        # intrările cu cablu c.c. + c.a. apar de două ori: aparatele se listează o dată, cu ramura c.a.
        aparate = [] if (n["rol"] in ("intrare", "intrare_cc") and n["nod"].get("cablu_ca")
                         and n.get("cablu") is not n["nod"].get("cablu_ca")) else (n["nod"].get("aparate") or [])
        for a in aparate:
            if a.get("tip") in TIPURI_PROTECTIE:
                rows.append(_rand_reglaj(a, amp, b))
            for lat in a.get("laterale") or []:
                if isinstance(lat, dict) and lat.get("tip") in TIPURI_PROTECTIE and (lat.get("param") or {}).get("In_A"):
                    rows.append(_rand_reglaj(lat, amp + " (asociat " + (a.get("ref") or "") + ")", b))
        if b:
            ik.append({"nod": n["la"], "de_la": n["de_la"], "Ik3max_origine_kA": b.get("Ik3max_origine_kA"),
                       "Ik3max_capat_kA": b.get("Ik3max_capat_kA"), "Ik1min_capat_A": b.get("Ik1min_capat_A"),
                       "Ia_A": b.get("Ia_A"), "t_deconectare_s": b.get("t_deconectare_s")})
    for lat in (m.get("bara") or {}).get("laterale") or []:
        if isinstance(lat, dict):
            rz = lat.get("rezerva")
            if isinstance(rz, dict) and rz.get("tip") in TIPURI_PROTECTIE:
                rows.append(_rand_reglaj(rz, "protecția de rezervă a SPD", None))
    # aparatele de pe bara principală / intrările fără cablu propriu (ex. Q general fără coloană)
    vazute = {x["ref"] for x in rows}
    for it in m.get("intrari") or []:
        for a in it.get("aparate") or []:
            if a.get("tip") in TIPURI_PROTECTIE and a.get("ref") not in vazute and not a.get("existent"):
                rows.append(_rand_reglaj(a, _titlu(it.get("sursa")) + " → " + (_titlu(m.get("carcasa")) or "tablou"), None))
                vazute.add(a.get("ref"))
    pi = m.get("tabel_pi")
    return {"titlu": "FIȘA DE REGLAJE A PROTECȚIILOR ȘI CURENȚII DE SCURTCIRCUIT",
            "coloane": COLOANE_REGLAJE, "randuri": rows, "ik_noduri": ik,
            "protectie_interfata": pi if isinstance(pi, dict) else None,
            "note": ["Reglajele se aplică și se verifică la punerea în funcțiune (PIF); coloana „Verificat la PIF” se "
                     "completează de executant / dirigintele de șantier.",
                     "Ik3max = curentul maxim de scurtcircuit trifazat la bornele aparatului (Icu ≥ Ik3max); Ik1min = "
                     "curentul minim de defect monofazat la capătul circuitului (deconectarea automată).",
                     "MCB: Ii = pragul superior al zonei magnetice a curbei (B 5·In, C 10·In, D 20·In)."]}


# ------------------------------------------------------------------------------------------------ carcasa (module DIN)
MODULE_POLI = {"1P": 1, "1P+N": 2, "2P": 2, "3P": 3, "3P+N": 4, "4P": 4, 1: 1, 2: 2, 3: 3, 4: 4}
# lățimea implicită [module de 17,5 mm] pe tip de aparat, când polii nu se cunosc
MODULE_IMPLICIT = {"mcb": 1, "rcbo": 2, "rccb": 2, "spd": 2, "contactor": 2, "releu": 1, "contor": 4, "contor_direct": 4,
                   "siguranta": 1, "separator": 2, "intreruptor": 2, "sonerie": 1, "ceas": 1, "transformator_comanda": 2,
                   "releu_pi": 4, "analizor": 4, "smart_meter": 4, "priza_modulara": 3, "lampa": 1}
NEMODULARE = {"mccb", "acb", "sep_fuzibil", "fuzibil", "tc", "invertor", "generator", "convertor_bess", "baterie",
              "string_pv", "camp_pv", "nod", "cutie", "trafo", "celula_mt", "contor_semidirect", "ups"}
SERII_CARCASA = [(1, 12), (1, 18), (2, 12), (2, 18), (3, 12), (3, 18), (4, 18), (5, 18), (6, 18), (8, 24)]


def _module_aparat(a):
    tip = a.get("tip") or ""
    p = a.get("param") or {}
    if tip in NEMODULARE:
        return None
    poli = p.get("poli")
    if isinstance(poli, str):
        poli = poli.upper().replace(" ", "")
    if tip == "spd" and poli in ("4P", "3P+N"):
        return 4
    if poli in MODULE_POLI and tip in ("mcb", "rcbo", "rccb", "separator", "intreruptor", "spd", "siguranta", "contactor"):
        n = MODULE_POLI[poli]
        if tip == "rcbo" and n >= 4:
            return 7          # RCBO 4P = MCB 4P + bloc diferențial
        return n
    if tip in ("mcb",) and p.get("retea") == "tri":
        return 3
    return MODULE_IMPLICIT.get(tip, 2 if tip else None)


def dimensionare_carcasa(m, rezerva_pct=25.0):
    """numărul de module DIN ale tabloului desenat + rezervă (20–30 %, implicit 25 %) → rânduri și carcasa propusă"""
    try:
        rezerva_pct = min(max(float(rezerva_pct), 20.0), 30.0)
    except (TypeError, ValueError):
        rezerva_pct = 25.0
    elem, nemod = [], []

    def ad(a, unde):
        if not isinstance(a, dict) or a.get("in_carcasa") is False or a.get("existent"):
            return
        n = _module_aparat(a)
        if n is None:
            if a.get("tip") in ("mccb", "acb", "sep_fuzibil", "fuzibil") :
                nemod.append({"ref": a.get("ref") or "", "tip": a.get("tip"), "spec": " · ".join(a.get("spec") or []), "unde": unde})
            return
        elem.append({"ref": a.get("ref") or "", "tip": a.get("tip"), "module": n, "unde": unde})
        rz = a.get("rezerva")
        if isinstance(rz, dict):
            ad(rz, unde)

    for it in m.get("intrari") or []:
        for a in it.get("aparate") or []:
            if a.get("tip") not in ("invertor", "string_pv", "separator_cc", "generator", "baterie", "convertor_bess"):
                ad(a, "intrare")
    for a in (m.get("bara") or {}).get("laterale") or []:
        ad(a, "bară")

    def pl(lst):
        for p in lst or []:
            for a in p.get("aparate") or []:
                ad(a, _titlu(p.get("sarcina")))
                for lat in a.get("laterale") or []:
                    ad(lat, _titlu(p.get("sarcina")))
            pl(p.get("copii"))
    pl(m.get("plecari"))
    total = sum(e["module"] for e in elem)
    cu_rez = math.ceil(total * (1 + rezerva_pct / 100.0))
    alege = next(((r_, c_) for r_, c_ in SERII_CARCASA if r_ * c_ >= cu_rez), None)
    if nemod or alege is None or (alege and alege[0] > 6):
        tip = ("dulap / cofret metalic de distribuție IP54 cu panou modular pentru aparatele DIN"
               + (f" și placă de montaj pentru {len(nemod)} aparate nemodulare (MCCB / NH)" if nemod else ""))
        randuri = math.ceil(cu_rez / 24) if cu_rez else 0
        alege = (randuri, 24) if cu_rez else (0, 0)
    else:
        tip = (f"tablou modular din material plastic, {alege[0]} {'rând' if alege[0] == 1 else 'rânduri'} × {alege[1]} "
               f"module, IP40 (interior) / IP65 (exterior, umed), ușă transparentă / plină, bare N și PE")
    return {"module_aparate": total, "rezerva_pct": rezerva_pct, "module_cu_rezerva": cu_rez,
            "randuri": alege[0], "module_pe_rand": alege[1], "capacitate": alege[0] * alege[1],
            "module_libere": alege[0] * alege[1] - total, "carcasa_propusa": tip, "aparate": elem, "nemodulare": nemod,
            "note": ["1 modul = 17,5 mm (SR EN 60715). Lățimile sunt cele uzuale: MCB 1P = 1, 1P+N = 2, 3P = 3, 4P = 4; "
                     "RCCB 2P = 2, 4P = 4; RCBO 1P+N = 2; SPD 1P+N = 2, 3P+N = 4; contor modular trifazat = 4.",
                     "Se verifică lățimea reală din fișa aparatelor alese și disiparea termică (SR EN 61439-3)."]}


# ------------------------------------------------------------------------------------------------ pierderi în cabluri
FACTOR_FORMA_PIERDERI_PV = 0.5      # Σ(P²)/(Pmax·ΣP) pentru profilul de producție PV (estimare, pierderile ∝ I²)
PRODUCTIE_IMPLICITA_KWH_KWP = 1200.0  # RO, medie (Câmpia de Vest / Banat ≈ 1250, Moldova de nord ≈ 1100) — PRESUPUS


def _R(material, S, L, n=1, theta=70):
    rho = (norme.RHO_70 if theta >= 70 else norme.RHO20).get(material or "Cu", norme.RHO_70["Cu"])
    return rho * float(L) / float(S) / max(1, int(n or 1))


def pierderi_cabluri(m, r, inp=None, productie_kWh_kWp=None):
    """pierderile I²R pe c.c. (stringuri) și c.a. (invertoare → TGD → racord) la puterea nominală + energia anuală
    pierdută estimată. Valori de proiect, nu garanție de randament."""
    inp = inp if isinstance(inp, dict) else (m.get("calc") or {})
    tip = inp.get("tip_schema")
    if tip not in ("cef", "prosumator"):
        return {"aplicabil": False, "motiv": "pierderile în cabluri se calculează pentru CEF și prosumator"}
    rz = (r or {}).get("rezultat") or {}
    sume = rz.get("sume") or {}
    pn = sume.get("Pn_total_kW") or sume.get("Pn_invertoare_kW") or 0.0
    kwp = inp.get("kWp")
    presupus = []
    # c.a.: fiecare ramură c.a. a calculului, la curentul nominal (Ib de calcul = 1,1·Pn → Ib / 1,1)
    ca = []
    for b in ramuri_calc(r):
        if not b.get("L_m") or not b.get("S_faza_mm2") or not b.get("Ib_A"):
            continue
        tri = b.get("retea") != "mono"
        i_nom = float(b["Ib_A"]) / (1.1 if b.get("receptor") in ("invertor", "pcs", "PCS") else 1.0)
        R = _R(b.get("material"), b["S_faza_mm2"], b["L_m"], b.get("n_paralel"))
        p = (3 if tri else 2) * i_nom ** 2 * R / 1000.0
        ca.append({"obiect": b.get("obiect") or "/".join(map(str, b["_cale"])), "cablu": b.get("cablu"), "L_m": b["L_m"],
                   "I_A": i_nom, "R_ohm": R, "P_pierderi_kW": p})
    # dedublare: ramura generală (QG / racord) apare o singură dată
    p_ca = sum(x["P_pierderi_kW"] for x in ca)
    # c.c.: stringurile
    st = inp.get("string") if isinstance(inp.get("string"), dict) else {}
    md = st.get("modul") if isinstance(st.get("modul"), dict) else (inp.get("modul") if isinstance(inp.get("modul"), dict) else {})
    impp = md.get("Impp_A") or (float(st["Isc_A"]) / 1.07 if st.get("Isc_A") else None)
    vmpp = md.get("Vmpp_V")
    nm = st.get("n_module")
    ccc = rz.get("cablu_cc") or {}
    cin = inp.get("cablu_cc") if isinstance(inp.get("cablu_cc"), dict) else {}
    S_cc = ccc.get("S_mm2") or cin.get("S_fortat")
    L_cc = ccc.get("L_m") or cin.get("L_m")
    if not S_cc:
        S_cc = 6.0
        presupus.append("cablu c.c. H1Z2Z2-K 6 mm² (nedeclarat)")
    if not L_cc:
        L_cc = 30.0
        presupus.append("lungime cablu c.c. string → invertor 30 m dus (nedeclarată)")
    if not impp:
        impp = 13.0
        presupus.append("Impp = 13 A (fișa modulului lipsește)")
    p_string_kw = (float(nm) * float(vmpp) * float(impp) / 1000.0) if nm and vmpp else None
    if kwp and p_string_kw:
        n_str = max(1, round(float(kwp) / p_string_kw))
    elif kwp:
        p_string_kw = 20 * 0.5
        n_str = max(1, round(float(kwp) / p_string_kw))
        presupus.append("string de ≈ 10 kWp (20 module × 500 W) pentru numărul de stringuri")
    else:
        n_str = 0
    R_cc = _R("Cu", S_cc, 2 * float(L_cc))                 # dus-întors
    p_cc = n_str * impp ** 2 * R_cc / 1000.0
    p_dc = float(kwp) if kwp else (n_str * p_string_kw if p_string_kw else 0.0)
    pct_cc = 100.0 * p_cc / p_dc if p_dc else None
    pct_ca = 100.0 * p_ca / pn if pn else None
    y = productie_kWh_kWp or inp.get("productie_specifica_kWh_kWp") or \
        ((inp.get("productie") or {}).get("kWh_kWp_an") if isinstance(inp.get("productie"), dict) else None)
    if not y:
        y = PRODUCTIE_IMPLICITA_KWH_KWP
        presupus.append(f"producție specifică {_f(y, 0)} kWh/kWp/an (fără PVGIS) — introduceți valoarea PVGIS")
    e_an = (float(kwp) if kwp else pn) * float(y)
    f = FACTOR_FORMA_PIERDERI_PV
    e_cc = e_an * (pct_cc or 0) / 100.0 * f
    e_ca = e_an * (1 - (pct_cc or 0) / 100.0) * (pct_ca or 0) / 100.0 * f
    avert = []
    if pct_cc is not None and pct_cc > 1.0:
        avert.append(f"pierderi c.c. {_f(pct_cc, 2)} % > 1 % — secțiune mai mare pe stringuri")
    if pct_ca is not None and pct_ca > 1.5:
        avert.append(f"pierderi c.a. {_f(pct_ca, 2)} % > 1,5 % — secțiune mai mare pe cablurile c.a.")
    return {"aplicabil": True, "cc": {"n_stringuri": n_str, "I_string_A": impp, "S_mm2": S_cc, "L_m": L_cc, "R_ohm": R_cc,
                                      "P_pierderi_kW": p_cc, "pct": pct_cc},
            "ca": {"ramuri": ca, "P_pierderi_kW": p_ca, "pct": pct_ca},
            "total_kW": p_cc + p_ca, "productie_kWh_kWp": y, "energie_an_kWh": e_an,
            "energie_pierduta_kWh": {"cc": e_cc, "ca": e_ca, "total": e_cc + e_ca},
            "energie_pierduta_pct": 100.0 * (e_cc + e_ca) / e_an if e_an else None,
            "factor_forma": f, "presupus": presupus, "avertismente": avert,
            "metoda": ("P = k·I²·R la puterea nominală (k = 3 trifazat, 2 monofazat / c.c. dus-întors), R la 70 °C; "
                       f"energia anuală ≈ E_produsă × pierderi % × {_f(f)} (pierderile ∝ I², profil de producție PV)")}


# ------------------------------------------------------------------------------------------------ „tipic pentru N”
def _semnatura_intrare(it):
    ap = [(a.get("tip"), tuple(a.get("spec") or []), tuple(sorted((k, str(v)) for k, v in (a.get("param") or {}).items()
                                                                  if k not in ("sablon",))))
          for a in it.get("aparate") or [] if a.get("tip") not in ("nod",)]
    return (_titlu(it.get("sursa", {}).get("sub") if isinstance(it.get("sursa"), dict) else ""),
            _n((it.get("cablu_ca") or {}).get("text")), _n((it.get("cablu") or {}).get("text")),
            tuple((t, s, tuple(x for x in p if x[0] not in ("ref",))) for t, s, p in ap))


def grupuri_tipice(m, minim=2):
    """invertoarele (intrările) identice ale unei CEF / prosumator → grupuri „tipic pentru N”: primul se desenează
    complet, celelalte se notează „tipic pentru INV-2 … INV-N”. Doar datele — desenul decide (regula implicită
    rămâne „fiecare invertor separat”)."""
    grupuri = {}
    for i, it in enumerate(m.get("intrari") or []):
        if not any(a.get("tip") in ("invertor", "convertor_bess") for a in it.get("aparate") or []):
            continue
        grupuri.setdefault(_semnatura_intrare(it), []).append(i)
    out = []
    for idx in grupuri.values():
        if len(idx) < minim:
            continue
        refs = [next((a.get("ref") for a in m["intrari"][i].get("aparate") or [] if a.get("tip") in ("invertor", "convertor_bess")), "")
                for i in idx]
        out.append({"n": len(idx), "indici_intrari": idx, "tipic": refs[0], "reprezinta": refs,
                    "eticheta": f"TIPIC PENTRU {len(idx)} INVERTOARE ({refs[0]} … {refs[-1]})" if len(idx) > 2
                    else f"TIPIC PENTRU {refs[0]} ȘI {refs[-1]}"})
    return out


# ------------------------------------------------------------------------------------------------ export
def _celula(v):
    if isinstance(v, bool):
        return "da" if v else ""
    if isinstance(v, float):
        return round(v, 3)
    return v if v is not None else ""


def tabel_xlsx(tabele, cartus=None):
    """unul sau mai multe tabele {titlu, coloane, randuri, note} → .xlsx (o foaie pe tabel)"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    from openpyxl.utils import get_column_letter
    if isinstance(tabele, dict):
        tabele = [tabele]
    wb = Workbook()
    wb.remove(wb.active)
    k = cartus or {}
    thin = Side(style="thin", color="999999")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for t in tabele:
        ws = wb.create_sheet(re.sub(r"[\[\]:*?/\\]", "", t["titlu"].title())[:31])
        ws["A1"] = t["titlu"]
        ws["A1"].font = Font(bold=True, size=13)
        ws["A2"] = f"{k.get('denumire1', '')} — {k.get('denumire2', '')}".strip(" —")
        ws["A3"] = f"Beneficiar: {k.get('beneficiar', '')} · Proiect nr. {k.get('nr_pr', '')} · Planșa {k.get('plansa', '')}"
        ws.append([])
        ws.append([c[1] for c in t["coloane"]])
        for c in ws[5]:
            c.font = Font(bold=True)
            c.fill = PatternFill("solid", fgColor="EEEEEA")
            c.border = border
            c.alignment = Alignment(vertical="center", wrap_text=True)
        for rnd in t["randuri"]:
            ws.append([_celula(rnd.get(c[0])) for c in t["coloane"]])
            for c in ws[ws.max_row]:
                c.border = border
                c.alignment = Alignment(vertical="top", wrap_text=True)
                if isinstance(c.value, float):
                    c.number_format = "0.00"
        ws.append([])
        for nt in t.get("note") or []:
            ws.append([nt])
        for i, (cheie, _) in enumerate(t["coloane"], 1):
            ws.column_dimensions[get_column_letter(i)].width = 30 if cheie in ("de_la", "la", "protectie", "amplasare",
                                                                                "observatii", "formatie") else 12
        ws.freeze_panes = "A6"
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def tabel_html(tabele, cartus=None):
    """tabelele → HTML A4 peisaj (pentru PDF prin Chrome)"""
    if isinstance(tabele, dict):
        tabele = [tabele]
    k = cartus or {}
    css = ("@page{size:A4 landscape;margin:12mm}body{font:9pt/1.3 'Barlow','Arial',sans-serif;color:#111}"
           "h1{font-size:13pt;margin:0 0 2mm}p.s{margin:0 0 4mm;color:#444}table{border-collapse:collapse;width:100%;"
           "margin-bottom:5mm}th,td{border:0.3mm solid #888;padding:1mm 1.4mm;vertical-align:top}th{background:#eeeeea;"
           "text-align:left}td.n{text-align:right;white-space:nowrap}section{page-break-after:always}"
           "section:last-child{page-break-after:auto}ul{margin:0;padding-left:5mm;color:#333}")
    h = [f"<!doctype html><html lang='ro'><head><meta charset='utf-8'><style>{css}</style></head><body>"]
    for t in tabele:
        h.append(f"<section><h1>{_esc(t['titlu'])}</h1><p class='s'>{_esc(k.get('denumire2', ''))} · Beneficiar: "
                 f"{_esc(k.get('beneficiar', ''))} · Proiect nr. {_esc(k.get('nr_pr', ''))}</p><table><thead><tr>")
        h += [f"<th>{_esc(c[1])}</th>" for c in t["coloane"]]
        h.append("</tr></thead><tbody>")
        for rnd in t["randuri"]:
            h.append("<tr>")
            for c in t["coloane"]:
                v = rnd.get(c[0])
                num = isinstance(v, (int, float)) and not isinstance(v, bool)
                h.append(f"<td class='{'n' if num else ''}'>{_esc(_f(v, 2) if num else _celula(v))}</td>")
            h.append("</tr>")
        h.append("</tbody></table>")
        if t.get("note"):
            h.append("<ul>" + "".join(f"<li>{_esc(n)}</li>" for n in t["note"]) + "</ul>")
        h.append("</section>")
    h.append("</body></html>")
    return "".join(h)
