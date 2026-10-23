"""Constructorul schemei: din intrarea fizică (SPEC §B.1 / cazuri_golden „intrare”) și rezultatul motorului
`engine.calc.calculeaza` → modelul grafic desenat de `engine.layout`.

Principiul (SPEC §E.1): aparatele și cablurile generate poartă `param` = parametrii fizici din calcul, iar textele
de pe desen (`spec`) și din lista de echipamente (`lista`) se REGENEREAZĂ din `param` la fiecare previzualizare și
export (`regenereaza_texte`). Astfel lista nu poate contrazice desenul.

Model grafic rezultat:
  model["calc"]        = intrarea fizică (sursa de adevăr; formularul „Calcul” o editează)
  model["calc_rezumat"] = {blocheaza, verificari, info, presupus}  (informativ, recalculat la validare)
  aparat["param"]      = {"sablon": <cheie §E.3>, ...parametri}   → spec / lista regenerate
"""
import copy, math, re

from .calc import calculeaza, text_lista, text_desen, fmt_ro, note_generate
from .calc import norme
from .calc.texte import text_cablu

NB = " "
PUNCT = "·"

# ------------------------------------------------------------------------------------------------ utilitare
def _f(x, z=1):
    return fmt_ro(x, z) if x is not None else "—"


def _ap(tip, ref, sablon, param, **extra):
    """aparat în serie cu parametri; spec/lista se completează în regenereaza_texte"""
    a = {"tip": tip, "ref": ref, "param": dict(param, sablon=sablon)}
    a.update(extra)
    return a


def _prot(prot, ref, poli=None, bd=False, retea="tri"):
    """aparat de protecție din rezultatul unei ramuri (dict `protectie`); fără calibru (ramură blocată) → nimic de desenat"""
    if not prot or not prot.get("In_A"):
        return None
    t = prot.get("tip")
    if t == "gG":
        return _ap("sep_fuzibil", ref, "sep_sig", {"In_A": prot["In_A"], "poli": 3})
    if t == "MCB":
        p = poli or ("2P" if retea == "mono" else "4P")
        return _ap("mcb", ref, "mcb", {"In_A": prot["In_A"], "curba": prot.get("curba", "C"), "poli": p,
                                       "Icn_kA": prot.get("Icu_kA") or prot.get("Icn_kA") or 6})
    if t in ("MCCB", "ACB"):
        par = {"In_A": prot["In_A"], "Ir_A": prot.get("Ir_A", prot["In_A"]), "poli": poli or prot.get("poli") or "4P",
               "Icu_kA": prot.get("Icu_kA") or prot.get("Icu_kA_min")}
        for k in ("Im_A", "Isd_A", "Isd_multiplu", "tsd_s", "Ii_A", "decl"):
            if prot.get(k) is not None and not (k == "tsd_s" and not prot[k]):
                par[k] = prot[k]
        if bd:
            par["bd"] = True
        a = _ap("acb" if t == "ACB" else "mccb", ref, "acb" if t == "ACB" else "mccb", par)
        if bd:
            a["bd"] = True
        return a
    if t and t.startswith("RCBO"):
        par = {"In_A": prot["In_A"]}
        for k_in, k_out in (("poli", "poli"), ("curba", "curba"), ("IdN_mA", "IdN_mA"), ("tip_ddr", "tip_ddr"), ("Icu_kA", "Icn_kA"), ("Icn_kA", "Icn_kA")):
            if prot.get(k_in) is not None:
                par[k_out] = prot[k_in]
        if poli and "poli" not in par:
            par["poli"] = poli
        return _ap("rcbo", ref, "rcbo", par)
    return None


def _ddr(ddr, ref):
    """DDR propriu pe circuit (K03: 30 mA tip A pe prize)"""
    if not ddr:
        return None
    par = {"In_A": ddr.get("In_A") or 25, "poli": ddr.get("poli", "4P"), "IdN_mA": ddr.get("IdN_mA", 30), "tip_ddr": ddr.get("tip", "A")}
    for k in ("selectiv", "aparat", "asociat", "tip_q", "dt_s", "reglabil", "temporizare"):
        if ddr.get(k) is not None:
            par[k] = ddr[k]
    return _ap("rccb", ref, "rccb", par)


def _cond(r):
    """textul conductoarelor de pe cablu"""
    if r.get("PE") == "PEN":
        return "L + PEN" if r.get("retea") == "mono" else "3 + PEN"
    if r.get("retea") == "mono":
        return "L + N + PE"
    return "3 + N + PE"


def _cablu(r, ref=""):
    """cablul unei ramuri: text pe desen + parametri pentru listă"""
    if not r or not r.get("S_faza_mm2"):
        return {"ref": ref, "cond": "", "text": ""}
    L = r.get("L_m")
    txt = r.get("cablu") or ""
    t = f"{txt} {PUNCT} L ≈ {fmt_ro(L, 0)}{NB}m" if L else txt
    par = {k: r.get(k) for k in ("material", "izolatie", "metoda", "n_paralel", "S_faza_mm2", "S_N_mm2", "S_PE_mm2", "PE", "monopolar",
                                 "retea", "L_m", "Iz_corectat_A", "k_total", "dU_ramura_pct")}
    return {"ref": ref, "cond": _cond(r), "text": t, "param": par}


def _sub_ramura(r):
    """subtitlul casetei de capăt: Ib, ΔU cumulat, Ik3 la capăt"""
    if not r or r.get("Ib_A") is None:
        return ""
    s = f"Ib = {_f(r['Ib_A'])}{NB}A"
    if r.get("dU_cumulat_pct") is not None:
        s += f" {PUNCT} ΔU = {_f(r['dU_cumulat_pct'], 2)}{NB}%"
    return s


def _spd_bara(ik3=None):
    return {"tip": "spd", "ref": "F1", "param": {"sablon": "spd_ca", "tip": "T1+T2", "poli": "4P", "In_amonte_A": 63}}


# ------------------------------------------------------------------------------------------------ pe tip de schemă
def _bransament(inp, rz, m):
    mono = inp.get("retea") == "mono"
    bloc = rz.get("bloc", "")
    c2 = rz.get("C2") or {}
    Q, SF, TC = rz.get("Q") or {}, rz.get("SF") or {}, rz.get("TC_primar_A")
    semidirect = bool(TC)
    ap = [{"tip": "nod", "ref": "", "laterale": [{"tip": "bareta_nul"}]}]
    if SF:
        if mono:
            ap.append(_ap("fuzibil", "SF", "sep_sig", {"In_A": SF.get("In_A", 40), "poli": 1, "gabarit": "00"}))
        else:
            ap.append(_ap("sep_fuzibil", "SF", "sf", {"In_A": SF["In_A"], "soclu_A": SF.get("soclu_A"), "gabarit": SF.get("gabarit")}))
    if semidirect:
        ap.append(_ap("tc", "TC", "tc", {"primar_A": TC, "clasa": norme.BMPT_TC["clasa"], "Sn_VA": norme.BMPT_TC["Sn_VA"], "n": 3}, buc=3,
                      laterale=[
                          {"tip": "cleme", "ref": "K", "lista": ["Șir de cleme cu bloc de șuntare pe circuitul secundar de curent",
                                                                 "capac transparent sigilabil"]},
                          {"tip": "fuzibil", "ref": "F", "spec": [f"3 × 2{NB}A gG"], "intrare_contor": "tensiune", "sursa_legatura": "amonte",
                           "lista": ["Bloc siguranțe fuzibile circuit de tensiune contor 3 × 2 A gG, capace cu dublă sigilare",
                                     "bare → F → contor: CYEAbY-F 1×1,5 mm² / fază"]},
                          {"tip": "contor", "ref": "P", "eticheta": "kWh · kVArh",
                           "param": {"sablon": "contor", "retea": "tri", "masura": "semidirecta"}}]))
    else:
        ap.append(_ap("contor_direct", "P", "contor", {"retea": "mono" if mono else "tri", "masura": "directa"}))
    if Q:
        if mono:
            q = _ap("rcbo", "Q", "rcbo", {"In_A": Q["In_A"]})
        elif Q.get("tip") == "MCB":
            q = _ap("mcb", "Q", "mcb", {"In_A": Q["In_A"], "curba": Q.get("curba", "C"), "poli": "4P", "Icn_kA": Q.get("Icn_kA", 6)})
            q["bd"] = True; q["param"]["bd"] = True
        else:
            q = _ap("mccb", "Q", "mccb", {"In_A": Q["In_A"], "Ir_A": Q.get("Ir_A"), "poli": "4P",
                                          "Icu_kA": max(Q.get("Icu_kA") or 0, norme.MCCB_ICU_KA[0]), "bd": True})
            q["bd"] = True
        if not mono:
            q["laterale"] = [{"tip": "cutie", "ref": "", "eticheta": "DPST", "legatura": "comanda", "param": {"sablon": "dpst"}}]
        ap.append(q)
    rc = rz.get("RCCB")
    if rc:
        par = {"In_A": rc["In_A"], "poli": f"{rc.get('poli', 4)}P", "IdN_mA": rc.get("IdN_mA", 300), "tip_ddr": rc.get("tip", "AC")}
        for k in ("selectiv", "aparat", "asociat"):
            if rc.get(k) is not None:
                par[k] = rc[k]
        ap.append(_ap("rccb", "RCCB", "rccb", par))
    m["carcasa"] = {"titlu": bloc, "sub": "carcasă PAFS · IP54 · IK10 · cl. II" + (" · ST 3-JT" if mono else " · ST 4-JT")}
    m["intrari"] = [{"sursa": {"titlu": "RED 0,4 kV", "sub": "rețea de distribuție JT — racord conform ATR"},
                     "cablu": {"ref": "C1", "cond": "L + PEN" if mono else "3 + PEN", "text": "racord OD — conform ATR"}, "aparate": ap}]
    m["bara"] = {"afisare": False}
    m["plecari"] = [{"aparate": [], "cablu": _cablu(c2, "C2"),
                     "sarcina": {"titlu": "TE consumator", "sub": f"tablou generic {PUNCT} Pa = {_f(rz.get('Pa_kW'))}{NB}kW cf. ATR {PUNCT} {_sub_ramura(c2)}"},
                     "copii": _te_generic(mono, (Q or {}).get("In_A"))}]
    m["lista_pe"] = ["Baretă de nul · piesă de separație · priză de pământ locală",
                     "electrozi OL-Zn 2½″ × 3 m + platbandă OL-Zn 40×4 mm · Rp ≤ 4 Ω"]
    m["cartus"]["denumire2"] = f"{bloc} — BLOC DE MĂSURĂ ȘI PROTECȚIE {'MONOFAZAT' if mono else 'TRIFAZAT'}"
    return f"branșament {bloc}"


def _te_generic(mono, In_q):
    """tabloul consumatorului, GENERIC (cerut de OD la documentația de branșament / prosumator): întreruptor general,
    DDR 30 mA pe prize și câteva plecări tipice. Aparatele nu sunt dimensionate — se definitivează în proiectul de
    instalații interioare; textele o spun explicit."""
    P1 = "1P+N" if mono else "1P+N"
    def mcb(ref, txt, rol, In, poli="1P+N", ddr=False):
        tip = "rcbo" if ddr else "mcb"
        spec = [f"{poli} {PUNCT} C{In}{NB}A" + (f" {PUNCT} 30{NB}mA" if ddr else "")]
        den = (f"Întreruptor automat cu protecție diferențială {poli}, C{In} A, IΔn 30 mA tip A" if ddr
               else f"Întreruptor automat modular {poli}, C{In} A")
        return {"aparate": [{"tip": tip, "ref": ref, "spec": spec, "lista": [den + f" — {rol} (generic)",
                                                                        "calibrul și numărul circuitelor conform proiectului de instalații interioare"]}],
                "cablu": {"ref": "", "cond": "L + N + PE" if poli == "1P+N" else "3 + N + PE", "text": "conform proiect IU"},
                "sarcina": {"titlu": txt, "sub": "generic"}}
    circ = [mcb("Q1", "Iluminat", "circuite de iluminat", 10), mcb("Q2", "Prize", "circuite de prize", 16, ddr=True),
            mcb("Q3", "Receptoare fixe", "aparate fixe (boiler, cuptor etc.)", 20, ddr=True)]
    if not mono:
        circ.append(mcb("Q4", "Forță 3F", "receptoare trifazate", 20, poli="4P"))
    circ.append(mcb(f"Q{len(circ) + 1}", "Rezervă", "rezervă", 16))
    In_g = next((x for x in (25, 32, 40, 63, 80, 100, 125, 160, 250) if x >= (In_q or 0)), In_q or 63)
    poli_g = "2P" if mono else "4P"
    qg = {"tip": "separator", "ref": "QG", "spec": [f"{poli_g} {PUNCT} {In_g}{NB}A", "întreruptor-separator"],
          "lista": [f"Întreruptor-separator general TE {poli_g}, In {In_g} A (≥ In Q branșament) — generic",
                    "SR EN 60947-3; tabloul consumatorului se definitivează în proiectul de instalații interioare"]}
    return [{"grup": True, "aparate": [qg], "copii": circ}]


def _ierarhie(plate):
    """rezultatul motorului listează plecările plat, cu `nivel` (0 = plecare din bară, 1 = circuit din tabloul
    secundar, …) în ordinea arborelui → se reconstituie arborele (`copii`) pentru desen"""
    radacini, stiva = [], []
    for r in plate:
        r = dict(r); r.pop("copii", None)
        niv = int(r.get("nivel") or 0)
        while stiva and int(stiva[-1].get("nivel") or 0) >= niv:
            stiva.pop()
        if stiva:
            stiva[-1].setdefault("copii", []).append(r)
        else:
            radacini.append(r)
        stiva.append(r)
    return radacini


def _plecare(r, ref, pl_in):
    """o plecare (sau un circuit în cascadă) cu protecție, DDR, cablu și consumator"""
    ap = []
    p = _prot(r.get("protectie"), ref, retea=r.get("retea", "tri"))
    if p:
        ap.append(p)
    d = _ddr(r.get("DDR"), "DDR" + ref[1:] if ref.startswith("Q") else "DDR")
    if d:
        ap.append(d)
    nume = r.get("nume") or (pl_in or {}).get("nume") or ref
    out = {"aparate": ap, "cablu": _cablu(r), "sarcina": {"titlu": nume, "sub": _sub_ramura(r)}}
    copii_in = (pl_in or {}).get("copii") or []
    copii_r = r.get("copii") or []
    if copii_r:
        out["copii"] = [_plecare(cr, f"{ref}.{i + 1}", copii_in[i] if i < len(copii_in) else None) for i, cr in enumerate(copii_r)]
    return out


def _tablou(inp, rz, m, titlu="TG"):
    q1 = rz.get("Q1_C1") or {}
    sursa = "PT propriu — bara JT" if inp.get("origine") == "pt_propriu" else "RED 0,4 kV prin BMPT (RCCB 300 mA)"
    ap = []
    p = _prot(q1.get("protectie"), "Q1")
    if p:
        ap.append(p)
    d = _ddr(q1.get("DDR"), "DDR1")          # TT: DDR general (RA·IΔn ≤ 50 V)
    if d:
        ap.append(d)
    m["intrari"] = [{"sursa": {"titlu": "ALIMENTARE", "sub": sursa}, "cablu": _cablu(q1, "C1"), "aparate": ap}]
    In_b = (q1.get("protectie") or {}).get("In_A")
    ik = (rz.get("bara_TG") or {}).get("Ik3max_kA")
    m["bara"] = {"afisare": True, "eticheta": f"Bare Cu {PUNCT} 3P + N + PE" + (f" {PUNCT} {In_b}{NB}A" if In_b else "")
                 + (f" {PUNCT} Ik3max {_f(ik, 1)}{NB}kA" if ik else ""), "laterale": [_spd_bara()]}
    pl_in = inp.get("plecari") or []
    m["plecari"] = [_plecare(r, f"Q{i + 2}", pl_in[i] if i < len(pl_in) else None) for i, r in enumerate(_ierarhie(rz.get("plecari") or []))]
    b = rz.get("bilant") or {}
    m["carcasa"] = {"titlu": titlu, "sub": "tablou general de distribuție JT · IP54"}
    m["cartus"]["denumire2"] = f"TABLOU GENERAL DE DISTRIBUȚIE JT ({titlu})"
    if b.get("Pc_kW") is not None:
        m["carcasa"]["sub"] += f" · Pi = {_f(b.get('Pi_kW'))} kW · ks = {_f(b.get('ks'), 2)} · Pc = {_f(b.get('Pc_kW'))} kW"
    return "tablou general"


def _pt(inp, rz, m):
    tr = rz.get("trafo") or {}
    sn = tr.get("Sn_kVA") or inp.get("Sn_kVA")
    cel = rz.get("celula_trafo")
    ap = [_ap("sep_mt", "Q1", None, {}, spec=[f"24{NB}kV · 630{NB}A", "celulă de linie + CLP"],
              lista=["Celulă MT de linie 24 kV, 630 A, separator de sarcină cu cuțit de legare la pământ"],
              laterale=[{"tip": "descarcator_mt", "ref": "FV", "buc": 3, "spec": ["ZnO 24 kV"],
                         "lista": ["Descărcătoare cu ZnO 24 kV, 10 kA, la trecerea LEA–LES"]}])]
    ap[0]["param"] = None
    if cel == "intreruptor":
        a = _ap("intreruptor_mt", "Q2", "celula_intreruptor", {"raport": "conform Sn"})
        a["laterale"] = [{"tip": "cutie", "eticheta": "F>", "spec": ["50/51 · 50N/51N"], "legatura": "comanda",
                          "lista": ["Releu de protecție digital 50/51, 50N/51N, cu TC MT (sau senzori) și alimentare proprie"]}]
        ap.append(a)
    else:
        sig = norme.TRAFO_SIGURANTA_MT_A.get(int(sn)) if sn else None
        ap.append(_ap("sigurante_mt", "Q2", "celula_sigurante", {"In_A": sig}))
    ap.append(_ap("trafo", "T1", "trafo", {"Sn_kVA": sn, "uk_pct": tr.get("uk_pct"), "Pk_W": tr.get("Pk_W")}, neutru_pamant=True))
    qj = _prot(rz.get("Q_JT"), "Q3")
    if qj:
        ap.append(qj)
    ms = rz.get("masura") or {}
    if ms.get("loc") == "JT" and ms.get("TC_primar_A"):
        ap.append(_ap("tc", "TC", "tc", {"primar_A": ms["TC_primar_A"], "clasa": ms.get("clasa", "0,5S"), "Sn_VA": ms.get("Sn_VA", 5), "n": 3}, buc=3,
                      laterale=[{"tip": "cleme", "ref": "K", "lista": ["Șir de cleme cu bloc de șuntare pe circuitul secundar de curent",
                                                                       "capac transparent sigilabil"]},
                                {"tip": "fuzibil", "ref": "F", "spec": [f"3 × 2{NB}A gG"], "intrare_contor": "tensiune", "sursa_legatura": "amonte",
                                 "lista": ["Bloc siguranțe fuzibile circuit de tensiune contor 3 × 2 A gG, capace cu dublă sigilare"]},
                                {"tip": "contor", "ref": "P", "eticheta": "kWh · kVArh",
                                 "param": {"sablon": "contor", "retea": "tri", "masura": "semidirecta"}}]))
    elif ms.get("loc") == "MT":
        ap.insert(1, {"tip": "separator", "ref": "QM", "spec": ["celulă de măsură MT", "TT + TC, conform ATR"],
                      "lista": ["Celulă de măsură MT 24 kV cu transformatoare de tensiune și de curent, contor de decontare",
                                "conform ATR / avizului OD"]})
    m["intrari"] = [{"sursa": {"titlu": "LES 20 kV", "sub": "racord MT din rețeaua OD — conform ATR"},
                     "cablu": {"ref": "C1", "cond": "3 × 1 × 150 mm² Al", "text": "racord OD — conform ATR"}, "aparate": ap}]
    In_b = (rz.get("Q_JT") or {}).get("In_A")
    m["bara"] = {"afisare": True, "forteaza": True,
                 "eticheta": f"TGJT {PUNCT} bare Cu {PUNCT} 3P + N + PE {PUNCT} {In_b}{NB}A {PUNCT} Ik3max {_f(tr.get('Ik3max_bara_kA'), 1)}{NB}kA",
                 "laterale": [_spd_bara()]}
    pl_in = inp.get("plecari") or []
    m["plecari"] = [_plecare(r, f"Q{i + 4}", pl_in[i] if i < len(pl_in) else None) for i, r in enumerate(_ierarhie(rz.get("plecari") or []))]
    if rz.get("servicii_proprii"):
        m["plecari"].append(_plecare(rz["servicii_proprii"], f"Q{len(m['plecari']) + 4}", {"nume": "Servicii proprii PT"}))
    m["carcasa"] = {"titlu": f"PT {sn} kVA", "sub": "post de transformare 20/0,4 kV · celule MT + trafo + TGJT"}
    m["cartus"]["denumire2"] = f"POST DE TRANSFORMARE 20/0,4 kV · {sn} kVA"
    m["lista_pe"] = ["Priză de pământ comună MT/JT, R ≤ 1 Ω (calcul separat NTE 001)", "neutrul trafo legat la priza de pământ"]
    return "post de transformare"


def _cef(inp, rz, m):
    inv_r = rz.get("invertoare") or []
    st = inp.get("string") or {}
    kwp = inp.get("kWp")
    n_inv = max(1, len(inv_r))
    intrari = []
    k = 0
    inv_in = []
    for grp in inp.get("invertoare") or []:
        for _ in range(int(grp.get("n", 1))):
            inv_in.append(grp)
    # invertoarele identice (aceeași putere, protecție și cablu) se desenează o singură dată, cu „× n” (practica uzuală)
    grupuri = []
    for i, r in enumerate(inv_r):
        g = inv_in[i] if i < len(inv_in) else {}
        cheie = (g.get("Pn_kW"), (r.get("protectie") or {}).get("In_A"), r.get("cablu"))
        if grupuri and grupuri[-1][0] == cheie:
            grupuri[-1][2].append(i)
        else:
            grupuri.append((cheie, r, [i], g))
    for gi, (_, r, idx, g) in enumerate(grupuri):
        n = len(idx); i = idx[0]
        pn = g.get("Pn_kW")
        kwp_i = (kwp / n_inv) if kwp else None
        sfx = (lambda pre: f"{pre}{idx[0] + 1}…{idx[-1] + 1}") if n > 1 else (lambda pre: f"{pre}{i + 1}")
        ap = [{"tip": "string_pv", "ref": sfx("PV"), "in_carcasa": False, "eticheta": f"× {n}" if n > 1 else "", "buc": n,
               "spec": [f"{_f(kwp_i)}{NB}kWp" + (f" × {n}" if n > 1 else "") if kwp_i else "câmp PV"],
               "lista": [f"Câmp fotovoltaic {_f(kwp_i)} kWp (module și stringuri conform plan PV)" if kwp_i else "Câmp fotovoltaic"]}]
        if rz.get("gPV_In_A"):
            ap.append(_ap("gpv", sfx("F") + ".1", "gpv", {"In_A": rz["gPV_In_A"], "U_V": 1100, "n": 2 * int(st.get("n_stringuri_paralel", 1))},
                          in_carcasa=False, buc=n))
        sep = {"tip": "separator_cc", "ref": sfx("S"), "in_carcasa": False, "buc": n, "spec": ["c.c. sub sarcină"],
               "lista": ["Separator de c.c. sub sarcină pe intrarea MPPT (sau integrat în invertor)"],
               "laterale": [{"tip": "spd_cc", "ref": sfx("F") + ".2", "buc": n,
                             "param": {"sablon": "spd_cc", "Ucpv_V": rz.get("SPD_cc_Ucpv_V") or 1100}}]}
        ap.append(sep)
        par_inv = {"Pn_kW": pn, "Iac_max_A": r.get("Ib_A"), "certificare": "Ord. ANRE 208/2018 (RfG) + ATR"}
        if rz.get("retea") == "mono":
            par_inv["retea"] = "mono"
        ap.append(_ap("invertor", sfx("INV-"), "invertor", par_inv, in_carcasa=False, buc=n))
        q = _prot(r.get("protectie"), sfx("Q"), retea=rz.get("retea") or "tri")
        if q:
            q["buc"] = n
            ap.append(q)
        d = _ddr(r.get("DDR"), sfx("DDR"))
        if d:
            d["buc"] = n
            ap.append(d)
        cab = _cablu(r)
        if n > 1 and cab.get("param"):
            cab["param"]["buc_circuite"] = n
            cab["text"] = f"{n} × [{cab['text']}]"
        intrari.append({"sursa": {"titlu": f"CÂMP PV {idx[0] + 1}…{idx[-1] + 1}" if n > 1 else f"CÂMP PV {i + 1}",
                                  "sub": (f"{n} invertoare × " if n > 1 else "invertor ") + f"{_f(pn)} kW"},
                        "cablu": {"ref": "", "cond": "c.c.", "text": "H1Z2Z2-K"}, "cablu_ca": cab, "aparate": ap})
    pcs = rz.get("PCS")
    if pcs:
        b = inp.get("bess") or {}
        ap = [_ap("baterie", "BAT", "baterie", {"kWh": b.get("kWh")}, in_carcasa=False),
              _ap("convertor_bess", "PCS", "pcs", {"Pn_kW": b.get("P_kW"), "Iac_max_A": pcs.get("Ib_A")}, in_carcasa=False)]
        q = _prot(pcs.get("protectie"), "QB")
        if q:
            ap.append(q)
        intrari.append({"sursa": {"titlu": "BESS", "sub": f"{_f(b.get('P_kW'))} kW / {_f(b.get('kWh'))} kWh"},
                        "cablu": {"ref": "", "cond": "c.c.", "text": ""}, "cablu_ca": _cablu(pcs), "aparate": ap})
    m["intrari"] = intrari
    qg = rz.get("QG") or {}
    s = rz.get("sume") or {}
    mono = rz.get("retea") == "mono"
    spd = _spd_bara()
    if mono:
        spd["param"]["poli"] = "2P"
    m["bara"] = {"afisare": True, "eticheta": f"Bare Cu {PUNCT} {'L + N + PE' if mono else '3P + N + PE'} {PUNCT} Σ Iac = {_f(s.get('Iac_total_A'))}{NB}A",
                 "laterale": [spd]}
    apq = []
    qga = _prot(qg.get("protectie") or qg, "QG", bd=True)
    if qga:
        qga["laterale"] = [{"tip": "cutie", "eticheta": "PI", "spec": ["U / f"], "legatura": "comanda",
                            "lista": ["Protecție de interfață (anti-insularizare) cu declanșare pe bobina BD a QG — reglaje conform ATR",
                                      "Ord. ANRE 208/2018 (RfG)"]}]
        apq.append(qga)
    d = _ddr(qg.get("DDR"), "DDR-G")
    if d:
        apq.append(d)
    tcp = rz.get("TC_primar_A") or (qg.get("TC_primar_A"))
    if mono:
        apq.append(_ap("contor_direct", "P1", "contor", {"retea": "mono", "masura": "directa", "bidirectional": True}))
    elif tcp:
        apq.append(_ap("tc", "TC", "tc", {"primar_A": tcp, "clasa": "0,5S", "Sn_VA": 5, "n": 3}, buc=3,
                       laterale=[{"tip": "contor", "ref": "P1", "eticheta": "kWh",
                                  "param": {"sablon": "contor", "retea": "tri", "masura": "semidirecta", "bidirectional": True}}]))
    tr = rz.get("trafo")
    if tr:
        apq.append(_ap("trafo", "T1", "trafo", {"Sn_kVA": tr.get("Sn_kVA")}, neutru_pamant=True))
        dest = {"titlu": "PCC — rețea MT 20 kV", "sub": "racord MT conform ATR"}
    else:
        dest = {"titlu": "PCC — RED 0,4 kV", "sub": "punct comun de cuplare conform ATR"}
    rac = rz.get("racord") or {}
    if rac.get("tg_existent"):
        qt = rz.get("Q_TG") or {}
        qtxt = f"{qt.get('tip', '')} {qt.get('curba') or ''}{qt.get('In_A')}{NB}A".replace("  ", " ").strip() if qt.get("In_A") else "Q de racord conform releveu"
        dest = {"titlu": "TG EXISTENT", "sub": f"racord pe bara TG prin {qtxt} (existent) {PUNCT} măsura la punctul de racord OD"}
    c0 = rz.get("C0")
    cab0 = _cablu(c0, "C0") if c0 else {"ref": "C0", "cond": "L + N + PE" if mono else "3 + N + PE", "text": "conform ATR"}
    if c0:
        dest = dict(dest, sub=dest["sub"] + f" {PUNCT} {_sub_ramura(c0)}")
    m["plecari"] = [{"aparate": apq, "cablu": cab0, "sarcina": dest}]
    m["carcasa"] = {"titlu": "TGD-CF", "sub": f"tablou general c.a. fotovoltaic · Σ Pn = {_f(s.get('Pn_total_kW'))} kW · categoria {rz.get('categorie_RfG', '—')} RfG"}
    m["cartus"]["denumire2"] = (f"CEF {_f(kwp)} kWp" if kwp else f"CEF {_f(s.get('Pn_total_kW'))} kW") + (" + BESS" if pcs else "")
    return "CEF"


def _prosumator(inp, rz, m):
    inv = rz.get("INV") or {}
    mono = inp.get("retea") == "mono"
    pn = inp.get("Pn_inv_kW")
    ap = [_ap("string_pv", "PV", None, {}, in_carcasa=False, spec=["câmp PV"], lista=["Câmp fotovoltaic (module și stringuri conform plan PV)"])]
    ap[0]["param"] = None
    # partea de c.c. (M5): separator de c.c. sub sarcină + SPD c.c. tip 2 (dacă nu sunt integrate în invertor)
    ap.append({"tip": "separator_cc", "ref": "S", "in_carcasa": False, "spec": ["c.c. sub sarcină"],
               "lista": ["Separator de c.c. sub sarcină pe intrarea MPPT (sau integrat în invertor)"],
               "laterale": [{"tip": "spd_cc", "ref": "F2", "param": {"sablon": "spd_cc", "Ucpv_V": inp.get("Ucpv_V") or 1000}}]})
    if inp.get("hibrid"):
        ap.append({"tip": "baterie", "ref": "BAT", "in_carcasa": False, "spec": ["c.c."], "lista": ["Baterie cuplată în c.c. la invertorul hibrid, cu BMS"]})
    ap.append({"tip": "invertor", "ref": "INV", "in_carcasa": False, "spec": [f"{_f(pn)}{NB}kW", "1 × 230 V" if mono else "3 × 400 V"],
               "lista": [f"Invertor {'monofazat' if mono else 'trifazat'} {'hibrid ' if inp.get('hibrid') else ''}{_f(pn)} kW, PI integrată certificată",
                         f"Iac,max {_f(rz.get('Iac_max_A'))} A, reglaje PI conform ATR (Ord. ANRE 228/2018)"]})
    q = _prot(inv.get("protectie"), "QI", retea="mono" if mono else "tri")
    if q:
        ap.append(q)
    d = _ddr(inv.get("DDR"), "DDR") or _ap("rccb", "DDR", "rccb", {"In_A": (inv.get("protectie") or {}).get("In_A", 25) if (inv.get("protectie") or {}).get("In_A", 25) in norme.RCCB_IN_A else 40,
                                         "poli": "2P" if mono else "4P", "IdN_mA": 30, "tip_ddr": "A"})
    ap.append(d)
    m["intrari"] = [{"sursa": {"titlu": "CÂMP PV", "sub": f"invertor {_f(pn)} kW"}, "cablu": {"ref": "", "cond": "c.c.", "text": "H1Z2Z2-K"},
                     "cablu_ca": _cablu(inv), "aparate": ap}]
    spd = {"tip": "spd", "ref": "F1", "param": {"sablon": "spd_ca", "tip": "T2", "poli": "2P" if mono else "4P", "In_amonte_A": 40}}
    m["bara"] = {"afisare": True, "forteaza": True, "eticheta": "TE consumator · bare existente", "laterale": [spd]}
    qb = inp.get("In_Q_bransament_A")
    m["plecari"] = [{"aparate": [], "cablu": {"ref": "", "cond": "L + N + PE" if mono else "3 + N + PE", "text": "existent"},
                     "sarcina": {"titlu": "Branșament existent", "sub": (f"Q {qb}{NB}A {PUNCT} " if qb else "") + "contor bidirecțional (OD)"}}]
    # circuitele consumatorului (generic, cerut de OD): pe aceeași bară a TE
    for k, cg in enumerate(_te_generic(mono, qb)[0]["copii"]):
        cg["aparate"][0]["ref"] = f"Q{k + 2}"
        cg["sarcina"]["sub"] = "existent / generic"
        m["plecari"].append(cg)
    m["carcasa"] = {"titlu": "TE", "sub": "tablou electric consumator · prosumator"}
    m["cartus"]["denumire2"] = f"PROSUMATOR {_f(pn)} kW {'MONOFAZAT' if mono else 'TRIFAZAT'}"
    return "prosumator"


def _ge(inp, rz, m):
    """GE + ATS (SPEC §C.6): două intrări DISTINCTE în ATS — I: rețea (QR → C1), II: GE (QG → C2) —, cei doi poli ai
    comutatorului interblocați mecanic + electric (sursele nu pot fi niciodată în paralel), ieșirea ATS → C3 → consumatori"""
    qg, qr, ats = rz.get("Q_G") or {}, rz.get("Q_retea") or {}, rz.get("ATS") or {}
    c1, c2, c3 = rz.get("C1") or {}, rz.get("C2") or {}, rz.get("C3") or {}
    sn = inp.get("Sn_GE_kVA")
    p_ats = {"In_A": ats.get("In_A")}
    pol = lambda poz, buc: dict(_ap("separator", f"ATS·{poz}", "ats", p_ats, interblocaj="ATS", buc=buc))
    ap_r = []
    p = _prot((c1.get("protectie") or dict(qr, tip=qr.get("tip", "MCCB"))), "QR")
    if p:
        p["in_carcasa"] = False
        ap_r.append(p)
    ap_r.append(pol("I", 1))
    ap_g = [_ap("generator", "G", "ge", {"Sn_kVA": sn, "In_G_A": rz.get("In_G_A")}, in_carcasa=False, neutru_pamant=True)]
    p = _prot((c2.get("protectie") or dict(qg, tip=qg.get("tip", "MCCB"))), "QG")
    if p:
        p["in_carcasa"] = False
        ap_g.append(p)
    d = _ddr(qg.get("DDR"), "DDR-G")      # bloc diferențial pe QG: deconectarea în regim GE (Ik1 ≈ In_G)
    if d:
        d["in_carcasa"] = False
        ap_g.append(d)
    den, car = text_lista("ats", p_ats)   # al doilea pol al ATS: același aparat → aceeași poziție în listă, fără text dublat
    ap_g.append({"tip": "separator", "ref": "ATS·II", "spec": [], "lista": [den, car], "interblocaj": "ATS", "buc": 0})
    m["intrari"] = [{"sursa": {"titlu": "RED 0,4 kV", "sub": "alimentare normală (poziția I)"},
                     "cablu": {"ref": "", "cond": "3 + N + PE", "text": "existent"}, "cablu_ca": _cablu(c1, "C1"), "aparate": ap_r},
                    {"sursa": {"titlu": "GRUP ELECTROGEN", "sub": f"{sn} kVA {PUNCT} In_G = {_f(rz.get('In_G_A'))}{NB}A (poziția II)"},
                     "cablu": {"ref": "", "cond": "", "text": ""}, "cablu_ca": _cablu(c2, "C2"), "aparate": ap_g}]
    m["bara"] = {"afisare": True, "eticheta": f"Ieșire ATS {PUNCT} bare 3P + N + PE {PUNCT} {ats.get('In_A', '')}{NB}A"}
    m["plecari"] = [{"aparate": [], "cablu": _cablu(c3, "C3"),
                     "sarcina": {"titlu": "Consumatori", "sub": f"P = {_f(inp.get('P_sarcina_kW'))}{NB}kW {PUNCT} {_sub_ramura(c3)}"}}]
    m["carcasa"] = {"titlu": "TAR", "sub": "tablou de anclanșare automată a rezervei (ATS 4P, comută și N)"}
    m["lista_pe"] = ["Neutrul GE legat la priza de pământ locală (TN-S), Rp ≤ 4 Ω", "ATS 4P: comută și conductorul N"]
    m["cartus"]["denumire2"] = f"GRUP ELECTROGEN {sn} kVA + ATS"
    return "grup electrogen + ATS"



def _locuinta(inp, rz, m):
    """tabloul unei locuințe (SPEC §C.8): branșamentul (în afara TE: SF, contor, Q / RCBO, RCCB), coloana C2, TE cu bara PE / N
    și legătura la priza de pământ, Q general, SPD pe bară, grupe DDR 30 mA desenate ca „pieptene” în același tablou
    (plecare cu `grup`), circuitele finale sub ele"""
    ret = rz.get("retea") or inp.get("retea")
    ret = {"trifazat": "tri", "trifazic": "tri", "monofazat": "mono", "monofazic": "mono"}.get(str(ret).strip().lower(), str(ret).strip().lower())
    mono = ret != "tri"
    tt = (rz.get("schema_pamant") or inp.get("schema_pamant")) == "TT"
    al = rz.get("alimentare") or {}
    col = rz.get("coloana") or {}
    bloc = al.get("bloc") or ("BMPM" if mono else "BMPT")
    _ia = inp.get("alimentare") if isinstance(inp.get("alimentare"), dict) else {}
    nou = _ia.get("tip") == "bransament_nou"
    # ---- branșamentul: aparatele blocului de măsură, desenate DEASUPRA tabloului (în afara carcasei TE)
    br = []
    SF, Q, rc = al.get("SF") or {}, al.get("Q") or {}, al.get("RCCB") or {}
    if SF.get("In_A"):
        if mono:
            br.append(_ap("fuzibil", "SF", "sep_sig", {"In_A": SF["In_A"], "poli": 1, "gabarit": "00"}, in_carcasa=False))
        else:
            br.append(_ap("sep_fuzibil", "SF", "sf", {"In_A": SF["In_A"], "soclu_A": SF.get("soclu_A"), "gabarit": SF.get("gabarit")}, in_carcasa=False))
    br.append(_ap("contor_direct", "P", "contor", {"retea": "mono" if mono else "tri", "masura": "directa"}, in_carcasa=False))
    if Q.get("In_A"):
        if mono:
            q = _ap("rcbo", "QB", "rcbo", {"In_A": Q["In_A"], "IdN_mA": 300, "tip_ddr": al.get("DDR_bransament_tip") or "AC"}, in_carcasa=False)
        elif Q.get("tip") == "MCB":
            q = _ap("mcb", "QB", "mcb", {"In_A": Q["In_A"], "curba": Q.get("curba", "C"), "poli": "4P", "Icn_kA": Q.get("Icn_kA", 6)}, in_carcasa=False)
        else:
            q = _ap("mccb", "QB", "mccb", {"In_A": Q["In_A"], "Ir_A": Q.get("Ir_A"), "poli": "4P", "Icu_kA": Q.get("Icu_kA") or 25}, in_carcasa=False)
        br.append(q)
    if rc.get("In_A"):
        par = {"In_A": rc["In_A"], "poli": f"{rc.get('poli', 4)}P" if str(rc.get("poli", 4)).isdigit() else rc.get("poli"),
               "IdN_mA": rc.get("IdN_mA", 300), "tip_ddr": al.get("DDR_bransament_tip") or rc.get("tip", "AC")}
        for k in ("selectiv", "aparat", "asociat"):
            if rc.get(k) is not None:
                par[k] = rc[k]
        br.append(_ap("rccb", "RCCB", "rccb", par, in_carcasa=False))
    # ---- TE: bara PE / N (cu legătura PE → priza de pământ), Q general
    ap = list(br)
    ap.append({"tip": "nod", "ref": "", "laterale": [{"tip": "bareta_nul", "la_stanga": True, "eticheta": "BPE",
                                                      "nota": "bare N și PE separate" if not tt else "PE local de la priza proprie (TT)",
                                                      "fara_legatura": col.get("legatura_BPE") is False or tt}]})
    qg = rz.get("Q_general") or {}
    poli_g = qg.get("poli") or ("2P" if mono else "4P")
    if qg.get("tip") == "IS" and qg.get("In_A"):
        ap.append({"tip": "separator", "ref": "QG", "spec": [f"{poli_g} {PUNCT} {qg['In_A']}{NB}A", "întreruptor-separator"],
                   "lista": [f"Întreruptor-separator modular {poli_g}, In {qg['In_A']}{NB}A, {'230' if mono else '400'}{NB}V",
                             "SR EN 60947-3, AC-22A, montaj pe șină DIN — separare generală TE"]})
    else:
        p = _prot(qg, "QG", poli=poli_g)
        if p:
            ap.append(p)
    c2 = _cablu(col, "C2")
    c1 = {"ref": "C1", "cond": al.get("C1_conductoare") or (("L + N" if mono else "3 + N") if tt else ("L + PEN" if mono else "3 + PEN")),
          "text": "racord OD — conform ATR"}
    if c2.get("cond") and col.get("conductoare"):
        c2["cond"] = col["conductoare"]
    elif tt and c2.get("cond"):      # TT: fără PEN / PE în coloană; PE-ul vine de la priza de pământ proprie
        c2["cond"] = "L + N" if mono else "3 + N"
    pres = [x for x, k in (("Q", "Q_presupus"), ("Pa", "Pa_presupus")) if al.get(k)]
    sub_src = f"{bloc} {'nou, conform ATR' if nou else 'existent'} — racord OD" + (" · TT" if tt else "")
    if pres:       # valorile presupuse se văd pe planșă, nu par date confirmate
        sub_src += f" · {' și '.join(pres)} PRESUPUS — de confirmat din ATR"
    m["intrari"] = [{"sursa": {"titlu": "RED 0,4 kV", "sub": sub_src},
                     "cablu": c1, "cablu_ca": c2, "aparate": ap}]
    S_pe = max(10, col.get("S_PE_mm2") or 0) if col else 16
    ra = inp.get("RA_ohm")
    if tt:
        m["lista_pe"] = [f"Bară PE și bară N în TE · bornă principală de împământare (BPI) · conductor PE FY {fmt_ro(S_pe, 0)} mm² Cu spre priza de pământ",
                         "priză de pământ proprie (TT): electrozi OL-Zn + platbandă OL-Zn 40×4 mm · RA·IΔn ≤ 50 V · BEP baie legată la BPI"]
        m["rp"] = (f"RA = {fmt_ro(ra, 0)} Ω · RA·IΔn ≤ 50 V" if ra else "RA·IΔn ≤ 50 V")
    else:
        m["lista_pe"] = [f"Bară PE și bară N în TE (separate) · bornă principală de împământare (BPI) · conductor PE FY {fmt_ro(S_pe, 0)} mm² Cu",
                         f"PE din coloana C2 legat la BN din {bloc} · priză de pământ locală (repetată) Rp ≤ 4 Ω · BEP baie legată la BPI"]
        m["rp"] = "Rp ≤ 4 Ω"
    m["ref_pe"] = "BPE·PS·PPL"
    spd = rz.get("SPD") or {}
    lat = []
    if spd:
        pr = spd.get("protectie_rezerva") or {}
        par = {"sablon": "spd_ca", "tip": spd.get("tip", "T2"), "poli": spd.get("poli") or ("1P+N" if mono else "3P+N"),
               "In_amonte_A": pr.get("In_A") or spd.get("In_amonte_A") or qg.get("In_A") or 32}
        if pr.get("tip"):
            par["prot_tip"] = pr["tip"]
            if pr.get("curba"):
                par["curba"] = pr["curba"]
        sp = {"tip": "spd", "ref": "F1", "param": par, "fara_pamant": True}
        if pr.get("In_A"):
            txt = pr.get("text") or f"MCB {pr.get('poli') or ''} {pr.get('curba') or 'C'}{pr['In_A']}{NB}A"
            sp["rezerva"] = {"ref": pr.get("ref") or "F2", "tip": "mcb",
                             "spec": [f"{pr.get('curba') or 'C'}{pr['In_A']}{NB}A", "rezervă SPD"],
                             "lista": [f"Protecție de rezervă SPD: {txt}",
                                       "conform fișei SPD; derivația SPD ≤ 0,5 m până la BPE (SR HD 60364-5-534)"
                                       + ("; SPD în configurație CT2 (eclator N–PE) — TT" if tt else "")]}
        lat.append(sp)
    m["bara"] = {"afisare": True, "forteaza": True, "eticheta": f"Bare / pieptene Cu {PUNCT} {'L + N + PE' if mono else '3P + N + PE'}"
                 + f" {PUNCT} {max(63, qg.get('In_A') or 0)}{NB}A" + (f" (In QG {qg['In_A']}{NB}A)" if qg.get("In_A") else ""), "laterale": lat}
    n_q = 0
    def circuit(c):
        nonlocal n_q
        n_q += 1
        ref = f"Q{n_q}"            # numerotare de la stânga la dreapta, în ordinea de pe planșă
        f = c.get("faza")
        poli = "4P" if (f == "3F" or (not mono and f not in ("L1", "L2", "L3"))) else "1P+N"
        sub = [f if f and not mono else None,
               f"{_f(c['Ib_A'])}{NB}A" if c.get("Ib_A") is not None else None,
               f"ΔU {_f(c['dU_cumulat_pct'], 1)}{NB}%" if c.get("dU_cumulat_pct") is not None else None]
        out = {"aparate": [], "cablu": _cablu(c), "sarcina": {"titlu": c.get("nume") or ref, "sub": f" {PUNCT} ".join(x for x in sub if x)}}
        pr = _prot(c.get("protectie"), ref, poli=poli, retea="mono" if poli == "1P+N" else "tri")
        if pr:
            pr["param"]["lat_desen"] = 12          # coloane înguste: textul aparatului pe 2–3 rânduri scurte
            out["aparate"].append(pr)
        return out
    pl = []
    for g in rz.get("grupe_DDR") or []:
        copii = [circuit(c) for c in g.get("circuite") or []]
        dd = g.get("DDR") or {}
        if dd.get("aparat") == "RCBO":        # circuit singur: RCBO în locul MCB + DDR (protecția circuitului e deja RCBO)
            pl.extend(copii)
            continue
        d = _ddr(g.get("DDR"), g.get("obiect") or "DDR")
        if d:
            d["param"]["lat_desen"] = 14
            if (g.get("DDR") or {}).get("alternativa"):
                d["param"]["nota"] = g["DDR"]["alternativa"]
            et = g.get("faza") if g.get("faza") in ("L1", "L2", "L3") and not mono else ""
            pl.append({"grup": True, "eticheta_grup": et, "aparate": [d], "copii": copii})
        else:
            pl.extend(copii)
    m["plecari"] = pl
    b = rz.get("bilant") or {}
    m["carcasa"] = {"titlu": "TE", "sub": "tablou electric locuință"
                    + (f" {PUNCT} Pi = {_f(b.get('Pi_kW'))} kW {PUNCT} Pc = {_f(b.get('Pc_kW'))} kW" if b.get("Pc_kW") is not None else "")
                    + (f" {PUNCT} Pa = {_f(b.get('P_aprobata_kW'))} kW " + ("(PRESUPUS)" if al.get("Pa_presupus") else "(ATR)") if b.get("P_aprobata_kW") else "")}
    m["cartus"]["denumire2"] = "TABLOU ELECTRIC LOCUINȚĂ (TE) — " + ("MONOFAZAT" if mono else "TRIFAZAT")
    return "tablou locuință"

CONSTRUCTORI = {"bransament": _bransament, "tablou": _tablou, "pt": _pt, "cef": _cef, "prosumator": _prosumator, "ge_ats": _ge, "locuinta": _locuinta}


# ------------------------------------------------------------------------------------------------ texte din parametri
def _regen(a):
    par = a.get("param")
    if not par or not par.get("sablon"):
        return
    p = {k: v for k, v in par.items() if k != "sablon"}
    try:
        den, car = text_lista(par["sablon"], p)
        a["lista"] = [den, car] if car and car != "—" else [den]
        a["spec"] = text_desen(par["sablon"], p)
        if par["sablon"] == "contor":           # caseta are deja „kWh · kVArh”; dedesubt: tensiune și curent
            a["spec"] = [car.split(", telecitire")[0]]
        elif par["sablon"] == "dpst":
            a["spec"] = [f"U> 50{NB}Hz {PUNCT} t 0,13…0,2{NB}s"]
    except Exception as e:      # parametri incompleți → textul indică problema, validatorul blochează
        a["lista"] = [f"[parametri incompleți: {e}]"]
        a["spec"] = ["?"]


def regenereaza_texte(model):
    """SPEC §E.1: spec / lista se regenerează din `param` pentru fiecare aparat și auxiliar generat"""
    def br(b):
        for a in b.get("aparate") or []:
            _regen(a)
            for l in a.get("laterale") or []:
                _regen(l)
        for c in b.get("copii") or []:
            br(c)
    for b in (model.get("intrari") or []) + (model.get("plecari") or []):
        br(b)
    for l in (model.get("bara") or {}).get("laterale") or []:
        _regen(l)
    return model


def materiale_cabluri(model):
    """cablurile cu parametri → rânduri în lista de echipamente (U.M. m, +5 % rezervă), agregate pe tip de cablu (SPEC §E.1 pct. 5)"""
    grup = {}
    def adauga(den, car, ref, metri):
        g = grup.setdefault(den, {"refs": [], "m": 0, "car": car})
        g["refs"].append(ref); g["m"] += metri
    def br(b, ref_implicit):
        for key in ("cablu", "cablu_ca"):
            cab = b.get(key) or {}
            par = cab.get("param")
            if not (par and par.get("S_faza_mm2") and par.get("L_m")):
                continue
            n = int(par.get("n_paralel") or 1) * int(par.get("buc_circuite") or 1)
            metri = math.ceil(par["L_m"] * n * 1.05)
            # doar cablul de fază (conductorul PE separat e rând propriu); același text ca pe planșă, fără „n × (…)”
            txt = text_cablu(par.get("material"), par.get("izolatie"), par.get("metoda"), 1, par.get("S_faza_mm2"),
                             par.get("S_N_mm2"), par.get("S_PE_mm2"), par.get("PE") or "cablu", par.get("retea", "tri"))
            txt = txt.split(" + FY")[0]
            ref = cab.get("ref") or ref_implicit
            npar = int(par.get("n_paralel") or 1)
            mono_r = par.get("retea") == "mono"
            if par.get("monopolar") or str(par.get("metoda") or "").startswith("F"):
                # cabluri MONOPOLARE (treflă pe pat de cabluri): lungimea se socotește pe conductor
                izo = txt.split()[0]
                S, SN = par.get("S_faza_mm2"), par.get("S_N_mm2") or par.get("S_faza_mm2")
                nf = 1 if mono_r else 3
                if SN == S:
                    adauga(f"Cablu monopolar {izo} 1×{fmt_ro(S)} mm² {par.get('material')}", "0,6/1 kV, faze + N, în treflă; nr. de sisteme în paralel conform planșei",
                           ref, math.ceil(par["L_m"] * npar * (nf + 1) * 1.05))
                else:
                    adauga(f"Cablu monopolar {izo} 1×{fmt_ro(S)} mm² {par.get('material')}", "0,6/1 kV, faze, în treflă; nr. de sisteme în paralel conform planșei",
                           ref, math.ceil(par["L_m"] * npar * nf * 1.05))
                    adauga(f"Cablu monopolar {izo} 1×{fmt_ro(SN)} mm² {par.get('material')}", "0,6/1 kV, neutru; nr. de sisteme în paralel conform planșei",
                           ref, math.ceil(par["L_m"] * npar * 1.05))
            else:
                adauga(f"Cablu {txt} {par.get('material')}" + (f" — {npar} cabluri în paralel pe circuit" if npar > 1 else ""),
                       "0,6/1 kV, conform secțiunilor de pe planșă", ref, metri)
            if par.get("PE") == "separat" and par.get("S_PE_mm2"):
                adauga(f"Conductor de protecție FY 1×{fmt_ro(par['S_PE_mm2'])} mm² Cu, galben-verde", "pozat lângă cablul de fază", ref, metri)
        for i, c in enumerate(b.get("copii") or []):
            br(c, ((c.get("sarcina") or {}).get("titlu") if b.get("grup") else None) or f"{ref_implicit}.{i + 1}")
    for i, b in enumerate(model.get("intrari") or []):
        br(b, f"C{i + 1}" if len(model.get("intrari") or []) > 1 else "C1")
    for i, b in enumerate(model.get("plecari") or []):
        br(b, (b.get("sarcina") or {}).get("titlu") or f"P{i + 1}")
    out = []
    for den, g in grup.items():
        refs = g["refs"]
        ref = refs[0] if len(refs) == 1 else (f"{len(refs)} circ." if len(refs) > 3 else ", ".join(refs))
        out.append({"ref": ref, "lista": [den, g["car"] + (f" — {', '.join(refs)}" if len(refs) > 1 else "")], "cantitate": g["m"], "um": "m"})
    return out


# ------------------------------------------------------------------------------------------------ aparataj auxiliar
_GABARIT_NH = [(160, "00"), (250, "1"), (400, "2"), (630, "3"), (1250, "4a")]


def _gabarit(In):
    for lim, g in _GABARIT_NH:
        if In <= lim:
            return g
    return "4a"


def materiale_aparataj(model, inp, rz):
    """articolele care nu apar ca simbol pe planșă, dar se cumpără (SPEC §E.1 pct. 5, completare v1.3):
    patroanele fuzibile ale separatoarelor, sistemul de bare, carcasa tabloului, accesoriile de cablu și
    materialele prizei de pământ calculate. Rândurile au U.M. „buc” / „set” / „m”."""
    out = []
    pat = {}
    def br(b):
        for a in b.get("aparate") or []:
            par = a.get("param") or {}
            if par.get("sablon") in ("sep_sig", "sf") and par.get("In_A"):
                In = int(par["In_A"])
                try:
                    den_sep = text_lista(par["sablon"], {k: v for k, v in par.items() if k != "sablon"})[0]
                except Exception:
                    den_sep = ""
                mg = re.search(r"NH\s*([0-9a]+)", den_sep)
                g = mg.group(1) if mg else str(par.get("gabarit") or _gabarit(In)).upper().replace("NH", "").strip()
                nr = int(par.get("poli") or 3) if par.get("sablon") == "sep_sig" else 3
                k = (g, In)
                e = pat.setdefault(k, {"refs": [], "n": 0})
                e["refs"].append(a.get("ref") or ""); e["n"] += nr * int(a.get("buc") or 1)
        for c in b.get("copii") or []:
            br(c)
    for b in (model.get("intrari") or []) + (model.get("plecari") or []):
        br(b)
    for (g, In), e in sorted(pat.items(), key=lambda t: t[0][1]):
        refs = e["refs"]
        out.append({"ref": refs[0] if len(refs) == 1 else (f"{len(refs)} sep." if len(refs) > 3 else ", ".join(refs)),
                    "lista": [f"Patron fuzibil NH {g}, {In}{NB}A gG", "400/500 V c.a., SR EN 60269-2 — rezervă: 1 set / calibru recomandat"],
                    "cantitate": e["n"], "um": "buc", "tip": "aux"})
    tip = inp.get("tip_schema")
    car = model.get("carcasa") or {}
    In_b, ik = None, None
    if tip == "tablou":
        In_b = ((rz.get("Q1_C1") or {}).get("protectie") or {}).get("In_A"); ik = (rz.get("bara_TG") or {}).get("Ik3max_kA")
    elif tip == "pt":
        In_b = (rz.get("Q_JT") or {}).get("In_A"); ik = (rz.get("trafo") or {}).get("Ik3max_bara_kA")
    elif tip == "cef":
        qg = rz.get("QG") or {}
        In_b = (qg.get("protectie") or qg).get("In_A")
    elif tip == "ge_ats":
        In_b = (rz.get("ATS") or {}).get("In_A")
    if tip == "locuinta" and car:
        mono = "tri" not in str(rz.get("retea") or inp.get("retea") or "").lower()
        mod = 0
        def nm(a):
            par = a.get("param") or {}
            p = str(par.get("poli") or "")
            return 4 if p.startswith(("4", "3")) else 2 if p.startswith(("2", "1P+N")) else 2
        def wm(b):
            nonlocal mod
            for a in b.get("aparate") or []:
                if a.get("in_carcasa") is False or a.get("tip") == "nod":     # branșamentul (BMPM/BMPT) și nodul barei PE nu ocupă module în TE
                    continue
                mod += nm(a) if a.get("param") else (2 if mono else 4)
            for c in b.get("copii") or []:
                wm(c)
        for b in (model.get("intrari") or []) + (model.get("plecari") or []):
            wm(b)
        mod += len((model.get("bara") or {}).get("laterale") or []) * (2 if mono else 4)
        if (rz.get("SPD") or {}).get("protectie_rezerva"):
            mod += 2 if mono else 4            # F2 — protecția de rezervă a SPD, pe șină
        nec = math.ceil(mod * 1.2)
        std = next((x for x in (12, 18, 24, 36, 48, 54, 72, 96) if x >= nec), nec)
        out.append({"ref": car.get("titlu", "TE"), "lista": [f"Tablou modular TE {std} module DIN ({math.ceil(std / 12)} {'rând' if std <= 12 else 'rânduri'}), cu ușă, IP40 (IP65 la exterior)",
                    f"ocupat {mod} module + rezervă ≥ 20 %; borne N și PE, etichete circuite; SR EN 61439-3"], "cantitate": 1, "um": "buc", "tip": "aux"})
        out.append({"ref": car.get("titlu", "TE"), "lista": [f"Pieptene de conexiuni Cu {'1P+N' if mono else '3P+N'}, {max(63, (rz.get('Q_general') or {}).get('In_A') or 0)} A, cu capace de capăt",
                    "alimentarea DDR-urilor și a circuitelor din aceeași grupă"], "cantitate": 1, "um": "set", "tip": "aux"})
    elif In_b and car:
        mono = rz.get("retea") == "mono" or inp.get("retea") == "mono"
        out.append({"ref": car.get("titlu", ""), "lista": [f"Sistem de bare Cu {'L + N + PE' if mono else '3P + N + PE'}, In ≥ {In_b}{NB}A",
                    (f"Icw ≥ {fmt_ro(ik, 1)} kA / 1 s, " if ik else "") + "suporți izolatori, SR EN 61439-1/-2"], "cantitate": 1, "um": "set", "tip": "aux"})
    if car and tip in ("tablou", "cef", "ge_ats"):
        out.append({"ref": car.get("titlu", ""), "lista": [f"Carcasă tablou {car.get('titlu', '')}, metalică, IP54, IK08, uși cu cheie",
                    "plăci de montaj, șine DIN, borne, etichete, schemă în buzunar; SR EN 61439-2"], "cantitate": 1, "um": "buc", "tip": "aux"})
    elif car and tip == "pt":
        out.append({"ref": car.get("titlu", ""), "lista": ["Anvelopă post de transformare (beton sau metalică), cu fundație, ventilație și iluminat",
                    "dimensionată pentru celule MT + trafo + TGJT, conform proiect de specialitate"], "cantitate": 1, "um": "buc", "tip": "aux"})
    def sec(b):        # tablouri secundare (plecări cu circuite în cascadă): carcasă + bare proprii
        if b.get("copii") and b.get("grup"):      # grupă DDR în același tablou: fără carcasă proprie
            for c in b["copii"]:
                sec(c)
        elif b.get("copii"):
            t = (b.get("sarcina") or {}).get("titlu") or "TD"
            In = next(((a.get("param") or {}).get("In_A") for a in b.get("aparate") or [] if (a.get("param") or {}).get("In_A")), None)
            out.append({"ref": t, "lista": [f"Carcasă tablou {t}, metalică, IP54, IK08, uși cu cheie",
                        "plăci de montaj, șine DIN, borne, etichete; SR EN 61439-3"], "cantitate": 1, "um": "buc", "tip": "aux"})
            if In:
                out.append({"ref": t, "lista": [f"Sistem de bare / repartitor Cu 3P + N + PE, In ≥ {In}{NB}A", "SR EN 61439"],
                            "cantitate": 1, "um": "set", "tip": "aux"})
            for c in b["copii"]:
                sec(c)
    for b in model.get("plecari") or []:
        sec(b)
    ncab = sum(1 for x in model.get("materiale") or [] if (x.get("lista") or [""])[0].startswith("Cablu"))
    if ncab:
        capete = 0
        def nc(b):
            nonlocal capete
            for key in ("cablu", "cablu_ca"):
                par = (b.get(key) or {}).get("param") or {}
                if par.get("S_faza_mm2"):
                    capete += 2 * int(par.get("n_paralel") or 1) * int(par.get("buc_circuite") or 1)
            for c in b.get("copii") or []:
                nc(c)
        for b in (model.get("intrari") or []) + ([] if tip == "locuinta" else (model.get("plecari") or [])):     # casă: doar coloana are papuci
            nc(b)
        if capete:
            out.append({"ref": "cabluri", "lista": ["Set accesorii capăt de cablu: papuci de cablu, presetupă, tub termocontractabil, etichetă",
                        "dimensionat după secțiunea fiecărui cablu"], "cantitate": capete, "um": "set", "tip": "aux"})
    pr = rz.get("priza") or {}
    for mt in pr.get("materiale") or []:
        if "piesă de separație" in (mt.get("denumire") or "").lower():
            continue          # piesa de separație e deja poziția BN · PS · PPL de pe planșă
        out.append({"ref": "PP", "lista": [mt.get("denumire", ""), f"priză de pământ calculată, Rp = {fmt_ro(pr.get('Rp_ohm'), 2)} Ω"],
                    "cantitate": mt.get("cantitate"), "um": mt.get("um", "buc"), "tip": "aux"})
    return out


# ------------------------------------------------------------------------------------------------ note
NOTE_FIXE = [
    "Schemă electrică monofilară de principiu, fază {faza}. Dimensionare conform I7-2011, SR HD 60364-4-41, -4-43, -5-52 (2011), -5-54, "
    "SR EN 60909-0; branșament conform ST 4-JT / ST 3-JT (DEER).",
    "Nu fac obiectul prezentei planșe: {exclus}{pp}analiza de risc la trăsnet.",
    "{spl}",
    "Secțiunile cablurilor sunt dimensionate la Iz' = Iz·kθ·kgrup·ksol (SR HD 60364-5-52 tab. B.52.x), la ΔU (I7-2011) și la stabilitatea "
    "termică; reglajele protecțiilor sunt cele înscrise pe planșă.",
]


def cheie_confirmare(v):
    return f"{v.get('cod')}|{v.get('obiect')}"


def _note(inp, r, cartus, confirmari=()):
    spl = inp.get("schema_pamant") or "TN-C-S"
    if inp.get("tip_schema") == "bransament":
        spl_t = f"{spl} cu separarea PEN pe BN în bloc. Rp ≤ 4 Ω" if spl != "TT" else f"TT, RA = {inp.get('RA_ohm', '—')} Ω"
    elif inp.get("tip_schema") in ("pt",) or (inp.get("tip_schema") == "cef" and inp.get("pt_Sn_kVA")):
        spl_t = "TN-S din PT propriu. Rp ≤ 1 Ω, conform calcul"
    else:
        spl_t = "TN-S în aval de separarea PEN. Rp ≤ 4 Ω"
    atr = f" nr. {cartus.get('atr')}" if cartus.get("atr") else ""
    tip = inp.get("tip_schema")
    if tip == "pt" or (tip == "cef" and inp.get("pt_Sn_kVA")):
        exclus = f"racordul MT al OD conform ATR{atr}; legătura trafo–TGJT (conform furnizorului postului); "
    elif tip == "ge_ats":
        exclus = f"alimentarea existentă din amonte de QR; "
    elif tip == "tablou" and inp.get("origine") == "pt_propriu":
        exclus = "postul de transformare (amonte de C1); "
    elif tip == "prosumator":
        exclus = f"branșamentul existent și contorul OD{atr and ' (ATR' + atr + ')'}; "
    elif tip == "cef":
        exclus = f"instalația din amonte de punctul de racord (rețea OD / tablou existent), conform ATR{atr}; "
    else:
        exclus = f"racordul OD (C1) conform ATR{atr}; "
    nspl = (r.get("rezultat") or {}).get("nota_schema_pamant")
    spl_full = nspl if nspl else f"Schemă de legare la pământ: {spl_t}."
    pr = (r.get("rezultat") or {}).get("priza") or {}
    note = [t.format(faza=cartus.get("faza") or "PT", exclus=exclus, spl=spl_full,
                     pp="" if pr.get("nota") else "priza de pământ (calcul separat); ") for t in NOTE_FIXE]
    if pr.get("nota"):
        note.append(pr["nota"])
    try:
        note += [n.replace("celula trafo intreruptor", "celulă de transformator cu întreruptor în vid și releu 50/51, 50N/51N")
                  .replace("celula trafo sigurante", "celulă de transformator cu separator de sarcină și siguranțe MT")
                 for n in note_generate(r["rezultat"])]
    except Exception:
        pass
    ip = r.get("ipoteze") or []
    if ip:
        note.append("Ipoteze de calcul: " + "; ".join(ip) + ".")
    conf = set(confirmari or ())
    av = [v for v in r.get("verificari") or [] if v.get("nivel") == "AVERTISMENT" and cheie_confirmare(v) not in conf]
    if av:
        coduri = {}
        for v in av:
            coduri.setdefault(v["cod"], []).append(v.get("obiect", ""))
        def _ob(o):
            u = sorted(set(o))
            return ", ".join(u[:4]) + (f" și încă {len(u) - 4}" if len(u) > 4 else "")
        note.append("Atenționări de verificat (detalii în memoriul de calcul): " + "; ".join(f"{c} ({_ob(o)})" for c, o in coduri.items()) + ".")
    return [f"{i + 1}. {n}" for i, n in enumerate(note)]


# ------------------------------------------------------------------------------------------------ API
def rezumat(r):
    return {"blocheaza": r.get("blocheaza_export", False), "verificari": r.get("verificari", []), "info": r.get("info", []),
            "presupus": r.get("presupus", []), "ipoteze": r.get("ipoteze", [])}


def genereaza(intrare, cartus=None, format_="A3", pastreaza=None):
    """intrare fizică → (model grafic, rezultat calcul). `pastreaza` = model vechi din care se păstrează cartușul și setările planșei."""
    r = calculeaza(intrare)
    from .presets import CARTUS_CEP
    m = {"format": format_, "cartus": dict(CARTUS_CEP), "auto_format": True, "lista_auto": True, "legenda": True}
    if pastreaza:
        for k in ("format", "auto_format", "lista_auto", "legenda", "deviz"):
            if k in pastreaza:
                m[k] = copy.deepcopy(pastreaza[k])
        m["cartus"].update({k: v for k, v in (pastreaza.get("cartus") or {}).items() if v not in (None, "")})
    if cartus:
        m["cartus"].update({k: v for k, v in cartus.items() if v not in (None, "")})
    m["calc"] = copy.deepcopy(intrare)
    tip = intrare.get("tip_schema")
    rz = r.get("rezultat") or {}
    if tip in CONSTRUCTORI and rz and not (r.get("blocheaza_export") and not _are_structura(tip, rz)):
        try:
            CONSTRUCTORI[tip](intrare, rz, m)
        except Exception as e:      # nu blocăm aplicația: schema rămâne goală, validatorul raportează
            m.update({"intrari": [], "plecari": [], "bara": {"afisare": False}})
            r.setdefault("verificari", []).append({"cod": "V00", "nivel": "BLOCANT", "obiect": "schema",
                                                    "mesaj": f"schema nu a putut fi desenată din rezultat ({e.__class__.__name__}: {e})",
                                                    "remediere": "verificați datele de intrare"})
            r["blocheaza_export"] = True
    else:
        m.update({"intrari": [], "plecari": [], "bara": {"afisare": False}, "carcasa": None})
    conf = list((pastreaza or {}).get("confirmari") or [])
    if conf:
        m["confirmari"] = conf
        for v in r.get("verificari") or []:          # avertismentele analizate de proiectant: marcate, scoase din nota de pe planșă
            if v.get("nivel") == "AVERTISMENT" and cheie_confirmare(v) in conf:
                v["confirmat"] = True
    m["note"] = _note(intrare, r, m["cartus"], conf)
    pr = rz.get("priza") or {}
    if pr.get("Rp_ohm") is not None:          # textul de sub priza de pământ = valoarea calculată
        m["rp"] = f"Rp = {fmt_ro(pr['Rp_ohm'], 2)} Ω {'≤' if pr.get('ok') else '>'} {fmt_ro(pr.get('R_limita_ohm'), 2)} Ω"
    m["materiale"] = materiale_cabluri(m)
    if m.get("intrari") or m.get("plecari"):
        m["materiale"] += materiale_aparataj(m, intrare, rz)
    regenereaza_texte(m)
    m["calc_rezumat"] = rezumat(r)
    return m, r


def _are_structura(tip, rz):
    """dacă rezultatul blocat conține totuși destule date ca schema să fie desenată (pentru vizualizarea problemei)"""
    if tip == "bransament":
        return bool(rz.get("C2") and rz.get("Q"))
    if tip in ("tablou",):
        return bool(rz.get("plecari") is not None and rz.get("Q1_C1", {}).get("protectie"))
    if tip == "pt":
        return bool(rz.get("trafo"))
    if tip == "cef":
        return bool(rz.get("invertoare"))
    if tip == "prosumator":
        return bool(rz.get("INV"))
    if tip == "ge_ats":
        return bool(rz.get("Q_G"))
    if tip == "locuinta":
        return bool(rz.get("coloana") and rz.get("grupe_DDR") is not None)
    return False
