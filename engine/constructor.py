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
        return _ap("sep_fuzibil", ref, "sep_sig", {"In_A": prot["In_A"], "poli": 1 if retea == "mono" else 3})
    if t == "MCB":
        p = poli or ("2P" if retea == "mono" else "4P")
        return _ap("mcb", ref, "mcb", {"In_A": prot["In_A"], "curba": prot.get("curba", "C"), "poli": p,
                                       "Icn_kA": prot.get("Icu_kA") or prot.get("Icn_kA") or 6})
    if t in ("MCCB", "ACB"):
        par = {"In_A": prot["In_A"], "Ir_A": prot.get("Ir_A", prot["In_A"]),
               "poli": poli or prot.get("poli") or ("2P" if retea == "mono" else "4P"),
               "Icu_kA": prot.get("Icu_kA") or prot.get("Icu_kA_min")}
        for k in ("Im_A", "Isd_A", "Isd_multiplu", "tsd_s", "Ii_A", "decl", "intrerupator_motor", "motorizat", "Ir_fortat"):
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
    if r.get("cabluri_yd"):
        return "2 × (3 + PE)"    # echipa1 P0-3: motor stea-triunghi — 2 cabluri, 6 conductoare + PE
    if r.get("fara_N"):
        return "3 + PE"          # r7: rețea de 800 V c.a. (invertoare fără neutru)
    return "3 + N + PE"


_TIP_CABLU = re.compile(r"\b[A-Z](?:[A-Z0-9-]|b(?=[A-Z]))*[A-Z0-9]\b")     # E2: și „CYAbY” (b mic)


def fe180(txt):
    """r8: textul cablului unui circuit de siguranță — tipul de cablu devine NHXH FE180/E90 (rezistent la foc, fără
    halogeni), restul (conductoare, secțiune, paralel) rămâne."""
    if not txt or "FE180" in txt:
        return txt
    return _TIP_CABLU.sub("NHXH FE180/E90", txt, count=1)


def _cablu(r, ref=""):
    """cablul unei ramuri: text pe desen + parametri pentru listă"""
    if not r or not r.get("S_faza_mm2"):
        return {"ref": ref, "cond": "", "text": ""}
    L = r.get("L_m")
    txt = r.get("cablu") or ""
    if r.get("rezistent_foc"):
        txt = fe180(txt)
    t = f"{txt} {PUNCT} L ≈ {fmt_ro(L, 0)}{NB}m" if L else txt
    chei = ("material", "izolatie", "metoda", "n_paralel", "S_faza_mm2", "S_N_mm2", "S_PE_mm2", "PE", "monopolar",
            "retea", "L_m", "Iz_corectat_A", "k_total", "dU_ramura_pct", "rezistent_foc", "fara_N", "cabluri_yd")
    par = {k: r.get(k) for k in chei}
    if r.get("tronsoane"):
        par["tronsoane"] = [{k: t.get(k) for k in chei} for t in r["tronsoane"]]
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
    tt = inp.get("schema_pamant") == "TT"
    if tt:
        # r7 (#52): TT — fără separare PEN în bloc: conductorul rețelei rămâne N, PE numai de la priza proprie (RA)
        ap = [{"tip": "nod", "ref": "", "laterale": [{"tip": "bareta_nul", "eticheta": "BPE", "fara_legatura": True,
                                                       "nota": "TT: fără PEN — PE local de la priza proprie"}]}]
    else:
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
            q = _ap("rcbo", "Q", "rcbo", {"In_A": Q["In_A"], **{k: Q[k] for k in ("selectiv", "tip_ddr") if Q.get(k) is not None}})
        elif Q.get("tip") == "MCB":
            q = _ap("mcb", "Q", "mcb", {"In_A": Q["In_A"], "curba": Q.get("curba", "C"), "poli": "4P", "Icn_kA": Q.get("Icn_kA", 6),
                                        **_backup_sf(Q.get("Icn_kA", 6), c2.get("Ik3max_origine_kA"), SF)})
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
        par = {"In_A": rc["In_A"], "poli": f"{rc.get('poli', 4)}P", "IdN_mA": rc.get("IdN_mA", 300), "tip_ddr": rc.get("tip", "A")}
        for k in ("selectiv", "aparat", "asociat"):
            if rc.get(k) is not None:
                par[k] = rc[k]
        ap.append(_ap("rccb", "RCCB", "rccb", par))
    m["carcasa"] = {"titlu": bloc, "sub": "carcasă PAFS · IP54 · IK10 · cl. II" + (" · ST 3-JT" if mono else " · ST 4-JT")}
    m["intrari"] = [{"sursa": {"titlu": "RED 0,4 kV", "sub": "rețea de distribuție JT — racord conform ATR"},
                     "cablu": {"ref": "C1", "cond": ("L + N" if mono else "3 + N") if tt else ("L + PEN" if mono else "3 + PEN"),
                               "text": "racord OD — conform ATR"}, "aparate": ap}]
    m["bara"] = {"afisare": False}
    cab2 = _cablu(c2, "C2")      # TT: PE-ul din coloană vine de la bara PE a blocului (priza proprie), nu din PEN
    m["plecari"] = [{"aparate": [], "cablu": cab2,
                     "sarcina": {"titlu": "TE consumator", "sub": f"tablou generic {PUNCT} Pa = {_f(rz.get('Pa_kW'))}{NB}kW cf. ATR {PUNCT} {_sub_ramura(c2)}"},
                     "copii": _te_generic(mono, (Q or {}).get("In_A"), tt)}]
    m["lista_pe"] = ["Baretă de nul · piesă de separație · priză de pământ locală",
                     "electrozi OL-Zn Ø 60 mm × 3 m + platbandă OL-Zn 40×4 mm · Rp ≤ 4 Ω"]
    if tt:
        m["lista_pe"] = ["Bară PE în bloc (fără legătură cu N / PEN-ul rețelei — TT) · piesă de separație · priză de pământ proprie",
                         f"electrozi OL-Zn Ø 60 mm × 3 m + platbandă OL-Zn 40×4 mm · RA·IΔn ≤ 50 V"]
        m["rp"] = f"RA = {fmt_ro(inp.get('RA_ohm') or 4, 0)} Ω · RA·IΔn ≤ 50 V"
    m["cartus"]["denumire2"] = f"{bloc} — BLOC DE MĂSURĂ ȘI PROTECȚIE {'MONOFAZAT' if mono else 'TRIFAZAT'}"
    return f"branșament {bloc}"


def _backup_sf(icn, ik3, sf):
    """r8 (#35, f01): MCB-ul din BMPT are Icn 6 kA (ST 4-JT) sub Ik3 la punctul de racord — e protejat în back-up de
    siguranțele SF gG din amonte (asociere declarată în listă, din tabelele de coordonare ale producătorului)."""
    try:
        if ik3 is not None and float(ik3) > float(icn or 6) + 1e-9:
            return {"backup_SF_A": (sf or {}).get("In_A") or True, "backup_Ik3_kA": float(ik3)}
    except (TypeError, ValueError):
        pass
    return {}


def _te_generic(mono, In_q, tt=False):
    """tabloul consumatorului, GENERIC (cerut de OD la documentația de branșament / prosumator): întreruptor general,
    DDR 30 mA pe prize și câteva plecări tipice. Aparatele nu sunt dimensionate — se definitivează în proiectul de
    instalații interioare; textele o spun explicit."""
    P1 = "1P+N" if mono else "1P+N"
    def mcb(ref, txt, rol, In, poli="1P+N", ddr=False):
        tip = "rcbo" if ddr else "mcb"
        spec = [f"{poli} {PUNCT} C{In}{NB}A" + (f" {PUNCT} 30{NB}mA" if ddr else "")]
        den = (f"Întreruptor automat cu protecție diferențială {poli}, C{In} A, IΔn 30 mA tip A" if ddr
               else f"Întreruptor automat modular {poli}, C{In} A")
        return {"aparate": [{"tip": tip, "ref": ref, "spec": spec, "generic": True, "lista": [den + f" — {rol} (generic)",
                                                                        "calibrul și numărul circuitelor conform proiectului de instalații interioare"]}],
                "cablu": {"ref": "", "cond": "L + N + PE" if poli == "1P+N" else "3 + N + PE", "text": "conform proiect IU"},
                "sarcina": {"titlu": txt, "sub": "generic"}}
    # r9 (locuințe #31): în TT fiecare circuit are DDR (RA·IΔn ≤ 50 V) — nota „DDR pe fiecare circuit” e adevărată
    circ = [mcb("Q1", "Iluminat", "circuite de iluminat", 10, ddr=tt), mcb("Q2", "Prize", "circuite de prize", 16, ddr=True),
            mcb("Q3", "Receptoare fixe", "aparate fixe (boiler, cuptor etc.)", 20, ddr=True)]
    if not mono:
        circ.append(mcb("Q4", "Forță 3F", "receptoare trifazate", 20, poli="4P", ddr=tt))
    circ.append(mcb(f"Q{len(circ) + 1}", "Rezervă", "rezervă", 16, ddr=tt))
    In_g = next((x for x in (25, 32, 40, 63, 80, 100, 125, 160, 250) if x >= (In_q or 0)), In_q or 63)
    poli_g = "2P" if mono else "4P"
    qg = {"tip": "separator", "ref": "QG", "spec": [f"{poli_g} {PUNCT} {In_g}{NB}A", "întreruptor-separator"], "generic": True,
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


def _aparataj_motor(am, ref):
    """r5: aparatajul de comandă al motorului (contactoare, releu termic, pornitor Y/Δ, convertizor), desenat în serie
    după protecție și listat (texte generate din valorile calculate în motor)"""
    k = ref[1:] if ref.startswith("Q") else ref
    porn = am.get("pornire")
    np_ = "2P" if am.get("faze") == 1 else "3P"
    u_ = "230 V" if am.get("faze") == 1 else "3 × 400 V"
    f = lambda x: fmt_ro(x, 1)
    if porn == "vfd":
        return [{"tip": "convertizor", "ref": f"U{k}", "spec": [f"VFD {fmt_ro(am['VFD_kW'])}{NB}kW", f"In ≥ {f(am['VFD_In_A'])}{NB}A"],
                 "lista": [f"Convertizor de frecvență {u_}, {fmt_ro(am['VFD_kW'])} kW, In ≥ {f(am['VFD_In_A'])} A",
                           "filtru EMC C2, bobină de rețea, protecție termică motor integrată, SR EN 61800-5-1; cablu motor ecranat"]}]
    if porn == "soft":
        return [{"tip": "convertizor", "ref": f"U{k}", "spec": ["soft-starter", f"In ≥ {f(am['soft_In_A'])}{NB}A"],
                 "lista": [f"Soft-starter {u_}, In ≥ {f(am['soft_In_A'])} A, cu contactor de bypass și protecție termică",
                           "SR EN 60947-4-2"]}]
    if porn == "stea_triunghi":
        return [{"tip": "contact", "ref": f"KM{k}.1", "spec": [f"AC-3 {am['KM1_A']}{NB}A", "linie"],
                 "lista": [f"Contactor de linie 3P, AC-3 {am['KM1_A']} A, 400 V", "pornitor stea-triunghi, SR EN 60947-4-1"]},
                {"tip": "releu_termic", "ref": f"F{k}", "spec": [f"Ir = {f(am['releu_termic_Ir_A'])}{NB}A", "pe ramura Δ"],
                 "lista": [f"Releu termic de suprasarcină, reglat Ir = {f(am['releu_termic_Ir_A'])} A (Ib/√3), clasa 10",
                           "montat pe ramura triunghi, SR EN 60947-4-1"]},
                {"tip": "pornitor_yd", "ref": f"KM{k}.2/3", "spec": [f"KΔ {am['KM2_A']}{NB}A", f"KY {am['KM3_A']}{NB}A"],
                 "lista": [f"Contactoare stea-triunghi: KΔ 3P AC-3 {am['KM2_A']} A + KY 3P AC-3 {am['KM3_A']} A, interblocate",
                           "releu de timp stea-triunghi; motor cu 6 borne (U1V1W1 / U2V2W2), 2 cabluri spre motor"]}]
    return [{"tip": "contact", "ref": f"KM{k}", "spec": [f"AC-3 {am['KM_A']}{NB}A"],
             "lista": [f"Contactor {np_}, AC-3 {am['KM_A']} A, {u_}, bobină 230 V c.a.", "pornire directă, SR EN 60947-4-1"]},
            {"tip": "releu_termic", "ref": f"F{k}", "spec": [f"Ir = {f(am['releu_termic_Ir_A'])}{NB}A"],
             "lista": [f"Releu termic de suprasarcină, reglat Ir = {f(am['releu_termic_Ir_A'])} A (= Ib), clasa 10",
                       "SR EN 60947-4-1"]}]


def _plecare(r, ref, pl_in):
    """o plecare (sau un circuit în cascadă) cu protecție, DDR, cablu și consumator"""
    ap = []
    p = _prot(r.get("protectie"), ref, retea=r.get("retea", "tri"))
    if p:
        ap.append(p)
    d = _ddr(r.get("DDR"), "DDR" + ref[1:] if ref.startswith("Q") else "DDR")
    if d:
        ap.append(d)
    if r.get("aparataj_motor"):
        ap.extend(_aparataj_motor(r["aparataj_motor"], ref))
    nume = r.get("nume") or (pl_in or {}).get("nume") or ref
    sub = _sub_ramura(r)
    am = r.get("aparataj_motor") or {}
    if am:
        sub = f"M {'1' if am.get('faze') == 1 else '3'}~ {_f(am.get('P_kW'))}{NB}kW {PUNCT} " + {"stea_triunghi": "Y/Δ", "vfd": "VFD", "soft": "soft-start"}.get(
            am.get("pornire"), "DOL") + (f" {PUNCT} {sub}" if sub else "")
    if r.get("compensare"):
        # r6: baterie de condensatoare — Ib afișat = In real al bateriei; protecția și cablul la 1,43·In
        sub = (f"Q = {_f(r.get('Q_kvar'), 0)}{NB}kvar {PUNCT} In = {_f(r.get('In_cap_A'))}{NB}A {PUNCT} "
               f"dimensionare 1,43·In = {_f(r.get('Ib_A'))}{NB}A {PUNCT} regulator automat cosφ")
    if r.get("siguranta"):
        # r8 (P0): consumator de siguranță — releul termic doar semnalizează, eticheta o spune (fără DDR, FE180)
        for a in ap:
            if a.get("tip") == "releu_termic" and "doar semnalizare" not in (a.get("spec") or []):
                a["spec"] = (a.get("spec") or [])[:1] + ["doar semnalizare"]
                a["lista"] = [a["lista"][0].replace("Releu termic de suprasarcină", "Releu termic de suprasarcină cu "
                                                    "contact de SEMNALIZARE (nu oprește receptorul de siguranță, P118-3)"),
                              a["lista"][1]]
        sub = ("REZERVĂ interblocată · fără DDR" if r.get("rezerva") else "SIGURANȚĂ · fără DDR") + (f" {PUNCT} {sub}" if sub else "")
    out = {"aparate": ap, "cablu": _cablu(r), "sarcina": {"titlu": nume, "sub": sub}}
    if r.get("rezerva_echipata"):
        # r12: rezervă echipată — doar aparatul, fără cablu și fără sarcină
        out["cablu"] = {"ref": "", "cond": "", "text": ""}
        out["sarcina"] = {"titlu": "REZERVĂ", "sub": "echipată · fără circuit"}
    if r.get("siguranta"):
        out["siguranta"] = True
    copii_in = (pl_in or {}).get("copii") or []
    copii_r = r.get("copii") or []
    if copii_r:
        out["copii"] = [_plecare(cr, f"{ref}.{i + 1}", copii_in[i] if i < len(copii_in) else None) for i, cr in enumerate(copii_r)]
    if r.get("ups"):
        _ups_plecare(out, r, ref)
    elif r.get("ups_bypass"):
        out["sarcina"]["sub"] = f"intrare bypass static UPS {PUNCT} " + out["sarcina"].get("sub", "")
    return out


def _ups_plecare(out, r, ref):
    """r11: plecarea spre UPS — Q intrare (în tabloul părinte) → cablu → [UPS online + bypass static + bypass manual →
    Q ieșire] în tabloul de ieșire → bara tabloului alimentat din UPS → PDU / rack-uri / circuite."""
    u = r["ups"]
    k = ref[1:] if ref.startswith("Q") else ref
    sn, in_o = u.get("Sn_kVA"), u.get("In_iesire_A")
    mono = u.get("retea") == "mono"
    ap_ups = {"tip": "ups", "ref": f"UPS{k}", "bypass_manual": u.get("bypass_manual", True),
              "spec": [f"UPS {_f(sn, 0)}{NB}kVA online", "bypass static + manual" if u.get("bypass") else "fără bypass static"],
              "lista": [f"UPS online dublă conversie {_f(sn, 0)} kVA, {'1/1' if mono else '3/3'}, redresor + invertor, In ieșire "
                        f"{_f(in_o)} A, cu baterie (autonomie " + (f"{_f(u['autonomie_min'], 0)} min" if u.get("autonomie_min")
                                                                     else "conform fișei / proiectului IT") + ")",
                        ("bypass static automat + bypass manual de mentenanță (QBM, interblocat cu ieșirea); SR EN 62040-1/-3"
                         if u.get("bypass") else "fără bypass static (declarat); SR EN 62040-1/-3")],
              "laterale": [{"tip": "cutie", "ref": f"BAT{k}", "eticheta": "BAT", "legatura": "forta", "w": 22,
                            "spec": ["baterie UPS", "c.c."],
                            "lista": ["Baterie UPS (VRLA / Li-ion) în dulap propriu, cu separator-siguranță c.c.",
                                      "capacitate conform autonomiei cerute (fișa UPS)"]}]}
    ap_t = [ap_ups]
    qo = _prot(u.get("Q_iesire"), f"Q{k}.0", retea="mono" if mono else "tri")
    if qo:
        ap_t.append(qo)
    out["aparate_tablou"] = ap_t
    if not out.get("copii"):
        out["copii"] = [{"aparate": [], "cablu": {"ref": "", "cond": "", "text": ""},
                         "sarcina": {"titlu": "Circuite ieșire UPS", "sub": "conform proiect IT (nedeclarate)"}}]
    nume = out["sarcina"].get("titlu") or "UPS"
    out["sarcina"] = {"titlu": f"TD-UPS ({nume})" if "UPS" in nume.upper() else f"{nume} (din UPS)",
                      "sub": f"alimentat din UPS {_f(sn, 0)} kVA {PUNCT} In ieșire {_f(in_o)}{NB}A"
                             + (f" {PUNCT} P ieșire {_f(u.get('P_iesire_kW'))}{NB}kW" if u.get("P_iesire_kW") else "")}


def _tg_doua_sectii(inp, rz, m):
    """r11: TG din PT propriu cu 2 trafo, cupla normal deschisă (± AAR) — intrarea T1 → C1 → Q1.1 pe secția 1, T2 → C2 →
    Q1.2 pe secția 2, cupla QC sub bare; plecările în ordinea secțiilor."""
    st = rz["sectii_tg"]
    sn = inp.get("pt_Sn_kVA")
    i1 = m["intrari"][0]
    for a in i1.get("aparate") or []:
        if a.get("ref") == "Q1":
            a["ref"] = "Q1.1"
    i2 = copy.deepcopy(i1)
    for a in i2.get("aparate") or []:
        if a.get("ref") == "Q1.1":
            a["ref"] = "Q1.2"
    if (i2.get("cablu") or {}).get("ref"):
        i2["cablu"]["ref"] = "C2"
    sub = i1["sursa"].get("sub", "")
    rest = sub.split("bara JT", 1)[1] if "bara JT" in sub else ""
    gr = (rz.get("PT_sursa") or {}).get("grupa")
    i1["sursa"] = {"titlu": f"T1 {sn} kVA", "sub": f"PT propriu 2 × {sn} kVA{(' ' + gr) if gr else ''} — bara JT T1{rest}"}
    i2["sursa"] = {"titlu": f"T2 {sn} kVA", "sub": f"PT propriu 2 × {sn} kVA{(' ' + gr) if gr else ''} — bara JT T2{rest}"}
    m["intrari"] = [i1, i2]
    q1 = (rz.get("Q1_C1") or {}).get("protectie") or {}
    aar = st.get("aar")
    tip_q = "acb" if q1.get("tip") == "ACB" else "mccb"
    qc = {"tip": tip_q, "ref": "QC", "spec": [f"4P {PUNCT} {q1.get('In_A')}{NB}A", "NO · AAR · interblocaj 2/3" if aar
                                             else "NO · interblocaj 2/3"],
          "lista": [f"Întreruptor de cuplă longitudinală {q1.get('tip', 'MCCB')} 4P, In {q1.get('In_A')} A, Icu ≥ "
                    f"{_f(q1.get('Icu_kA'), 0)} kA, cu acționare motorizată",
                    "normal DESCHIS; interblocaj mecanic + electric „2 din 3” cu Q1.1 și Q1.2 (T1 și T2 niciodată în paralel)"
                    + ("; închis automat de AAR la pierderea tensiunii pe o secție" if aar else "")]}
    if aar:
        qc["laterale"] = [{"tip": "cutie", "ref": "AAR", "eticheta": "automatizare", "legatura": "comanda",
                           "spec": ["27 · 2 din 3", "Q1.1 · Q1.2 · QC"],
                           "lista": ["Automatizare AAR de cuplă (PLC / releu dedicat): relee 27 pe secțiile 1 și 2, comandă "
                                     "Q1.k / QC, temporizare reglabilă, blocare la defect pe bară",
                                     "deconectează plecările nevitale la închiderea QC (descărcarea sarcinii)"]}]
    m["bara"]["forteaza"] = True
    m["bara"]["cupla"] = {"n1": st.get("n1", 1), "aparat": qc, "etichete": ["secția 1 (T1)", "secția 2 (T2)"]}
    m["bara"]["eticheta"] = m["bara"]["eticheta"].replace("Bare Cu", "Secția 1 │ secția 2 · bare Cu", 1)
    for p, r in zip(m["plecari"], _ierarhie(rz.get("plecari") or [])):
        if r.get("descarcare_aar"):
            p["sarcina"]["sub"] = f"nevital · deconectat la AAR {PUNCT} " + p["sarcina"].get("sub", "")
    m["carcasa"]["sub"] = (f"TG cu 2 secții (T1 / T2), cuplă QC normal deschisă" + (" + AAR" if aar else "")
                           + f" {PUNCT} " + m["carcasa"].get("sub", ""))
    m["lista_pe"] = ["Bară PE și bară N comune în TG · neutrele T1 și T2 la priza de pământ comună a PT (TN-S)",
                     "cupla QC 4P comută și N; T1 și T2 niciodată în paralel (interblocaj 2 din 3)"]


def _titlu_tablou(inp, titlu="TG"):
    """echipa1 (T02b): tabloul alimentat dintr-un TG existent (origine „tg_existent”) sau numit „TD…” e un tablou de
    DISTRIBUȚIE secundar — titlul „TD”, nu „TG”."""
    if titlu != "TG":
        return titlu
    nume = str(inp.get("titlu_tablou") or inp.get("nume_tablou") or "").strip()
    if re.match(r"(?i)^TD\b", nume) or (inp.get("origine") == "tg_existent" and not re.match(r"(?i)^TG\b", nume)):
        return "TD"
    return titlu


def _tablou(inp, rz, m, titlu="TG"):
    titlu = _titlu_tablou(inp, titlu)
    q1 = rz.get("Q1_C1") or {}
    mono = (rz.get("retea") or inp.get("retea")) == "mono"
    tt = rz.get("schema_pamant") == "TT"
    sursa = rz.get("sursa") or ("PT propriu — bara JT" if inp.get("origine") == "pt_propriu" else "RED 0,4 kV prin BMPT")
    if rz.get("IdN_amonte_mA") or (not tt and inp.get("origine") in (None, "bmpt", "retea_publica")
                                   and inp.get("ddr_amonte", True) is not False and not rz.get("fara_ddr_amonte_siguranta")):
        sursa += f" (RCCB {fmt_ro(rz.get('IdN_amonte_mA') or 300, 0)}{NB}mA)"
    if inp.get("IdN_amonte_mA") is None and inp.get("origine") is None and "presupus" not in sursa.lower():
        sursa += " — PRESUPUS"
    if rz.get("schema_pamant"):
        sursa += f" {PUNCT} {rz['schema_pamant']}"
    ap = []
    p = _prot(q1.get("protectie"), "Q1", poli="2P" if mono else None, retea="mono" if mono else "tri")
    if p:
        ap.append(p)
    d = _ddr(q1.get("DDR"), "DDR1")          # TT: DDR general (RA·IΔn ≤ 50 V)
    if d:
        ap.append(d)
    if rz.get("fara_ddr_amonte_siguranta"):
        sursa += f" {PUNCT} racord înaintea DDR-ului general (circuite de siguranță)"
    q1g = rz.get("Q1_general")
    if q1g:
        # r8 (P0 #64): consumatorii de siguranță racordați ÎNAINTEA întreruptorului general Q1 — intrarea are doar cablul
        # C1 (protejat în tabloul sursă), bara de racord alimentează plecările de siguranță și Q1 general (grupă)
        pc1 = q1.get("protectie") or {}
        sursa += (f" {PUNCT} C1 protejat în tabloul sursă: {pc1.get('tip', '')} {pc1.get('In_A', '')}{NB}A"
                  if pc1.get("In_A") else "")
        ap = []
    m["intrari"] = [{"sursa": {"titlu": "ALIMENTARE", "sub": sursa}, "cablu": _cablu(q1, "C1"), "aparate": ap}]
    In_b = (q1.get("protectie") or {}).get("In_A")
    ik = (rz.get("bara_TG") or {}).get("Ik3max_kA")
    spd = _spd_bara()
    if mono:
        spd["param"]["poli"] = "1P+N"
    m["bara"] = {"afisare": True, "eticheta": f"Bare Cu {PUNCT} {'L + N + PE' if mono else '3P + N + PE'}" + (f" {PUNCT} {In_b}{NB}A" if In_b else "")
                 + (f" {PUNCT} Ik3max {_f(ik, 1)}{NB}kA" if ik else ""), "laterale": [spd]}
    if tt:
        ra = rz.get("RA_ohm")
        m["lista_pe"] = ["Bară PE și bară N separate în TG · bornă principală de împământare · PE local de la priza proprie (TT)",
                         "priză de pământ proprie: electrozi OL-Zn + platbandă OL-Zn 40×4 mm"
                         + (f" · RA = {fmt_ro(ra, 0)} Ω · RA·IΔn = {fmt_ro(rz.get('RA_IdN_V'), 1)} V ≤ 50 V" if ra else " · RA·IΔn ≤ 50 V")]
        m["rp"] = f"RA = {fmt_ro(ra, 0)} Ω · RA·IΔn ≤ 50 V" if ra else "RA·IΔn ≤ 50 V"
    from .calc.scheme import expandeaza_plecari
    pl_in = expandeaza_plecari(inp.get("plecari") or [])
    m["plecari"] = [_plecare(r, f"Q{i + 2}", pl_in[i] if i < len(pl_in) else None) for i, r in enumerate(_ierarhie(rz.get("plecari") or []))]
    if q1g:
        radacini = _ierarhie(rz.get("plecari") or [])
        sig = [p for p, r in zip(m["plecari"], radacini) if r.get("inainte_Q1")]
        norm = [p for p, r in zip(m["plecari"], radacini) if not r.get("inainte_Q1")]
        for p in sig:
            p["sarcina"]["sub"] = p["sarcina"]["sub"].replace("fără DDR", f"fără DDR {PUNCT} înainte de Q1", 1)
        grup = {"grup": True, "aparate": [x for x in [_prot(q1g, "Q1", poli="2P" if mono else None,
                                                           retea="mono" if mono else "tri")] if x],
                "copii": norm, "eticheta_grup": "după Q1 general", "sarcina": {"titlu": "Q1 general", "sub": ""}}
        m["plecari"] = sig + ([grup] if norm else [])
        m["bara"]["eticheta"] = m["bara"]["eticheta"].replace("Bare Cu", "Bare de racord (amonte Q1) Cu", 1)
    b = rz.get("bilant") or {}
    gen = "tablou de distribuție JT (secundar)" if titlu == "TD" else "tablou general de distribuție JT"
    m["carcasa"] = {"titlu": titlu, "sub": f"{gen} · IP54" + (" · monofazat 230 V" if mono else "")
                    + (" · TT" if tt else "")}
    if rz.get("sectii_tg"):
        _tg_doua_sectii(inp, rz, m)
    if str(inp.get("separare_PEN") or "").upper() in ("TG", "TABLOU") and not tt:
        # r11 (industrial j01): TN-C-S cu separarea PEN în TG — borna PEN, puntea spre bara N și bara PE desenate în listă
        m["lista_pe"] = ["Separarea PEN în TG: conductorul PEN al cablului C1 pe borna PEN → bara PE (legată la priza de "
                         "pământ), punte demontabilă PE → bara N; în aval TN-S (N și PE separate, nelegate din nou)",
                         "SR HD 60364-5-54 art. 543.4; PEN ≥ 10 mm² Cu / 16 mm² Al"]
    m["cartus"]["denumire2"] = (f"TABLOU DE DISTRIBUȚIE JT ({titlu})" if titlu == "TD" else
                                f"TABLOU GENERAL DE DISTRIBUȚIE JT ({titlu})") + (" — MONOFAZAT" if mono else "")
    if rz.get("siguranta") == "tot":
        # r8 (P0 #14): tablou de siguranță (desfumare, pompe de incendiu, TDSI) — titlul și cablul de alimentare o spun
        tit_s = inp.get("titlu_tablou") or inp.get("nume_tablou") or "TS"
        m["carcasa"]["titlu"] = tit_s if titlu in ("TG", "TD") else titlu
        m["carcasa"]["sub"] = m["carcasa"]["sub"].replace(gen, "tablou de siguranță la "
                                                          "incendiu · fără DDR · cabluri FE180/E90", 1)
        m["cartus"]["denumire2"] = f"TABLOU DE SIGURANȚĂ LA INCENDIU ({m['carcasa']['titlu']}) — FĂRĂ DDR"
    elif rz.get("siguranta") == "mixt":
        m["carcasa"]["sub"] += " · circuite de siguranță înainte de Q1"
    if rz.get("siguranta"):
        m["lista_pe"] = list(m.get("lista_pe") or ["Bară PE și bară N în tablou · bornă principală de împământare"]) + [
            "Circuite de siguranță (I7/2011, P118-3): fără DDR, cabluri NHXH FE180/E90 pe trasee separate, releu termic "
            "doar de semnalizare; legături echipotențiale suplimentare la pompe / ventilatoare"]
    if b.get("Pc_kW") is not None:
        m["carcasa"]["sub"] += f" · Pi = {_f(b.get('Pi_kW'))} kW · ks = {_f(b.get('ks'), 2)} · Pc = {_f(b.get('Pc_kW'))} kW"
    return "tablou general"


def _pt(inp, rz, m):
    tr = rz.get("trafo") or {}
    sn = tr.get("Sn_kVA") or inp.get("Sn_kVA")
    cel = rz.get("celula_trafo")
    cmt = rz.get("celule_mt") or {"linie": 1}
    nl = int(cmt.get("linie") or 1)
    u_mt = rz.get("U_MT_kV") or 20
    um = rz.get("Um_kV") or 24
    umt, umm = fmt_ro(u_mt), fmt_ro(um)
    n_t = int(rz.get("n_trafo") or 1)
    ap = [_ap("sep_mt", "Q1", None, {}, spec=[f"{umm}{NB}kV · 630{NB}A", "celulă de linie + CLP" if nl == 1
                                              else f"{nl} × celulă de linie (intrare–ieșire)"],
              lista=[f"Celulă MT de linie {umm} kV, 630 A, separator de sarcină cu cuțit de legare la pământ"
                     + ("" if nl == 1 else f" — intrare / ieșire în buclă LES {umt} kV")],
              buc=nl,
              laterale=[{"tip": "descarcator_mt", "ref": "FV", "buc": 3, "spec": [f"ZnO {umm} kV"],
                         "lista": [f"Descărcătoare cu ZnO {umm} kV, 10 kA, la trecerea LEA–LES"]}])]
    ap[0]["param"] = None

    def lant(k):
        """celula trafo → trafo → Q JT (k = 1, 2)"""
        suf = "" if n_t == 1 else f".{k}"
        out = []
        if cel == "intreruptor":
            a = _ap("intreruptor_mt", f"Q2{suf}", "celula_intreruptor", {"raport": "conform Sn", "Um_kV": um})
            a["laterale"] = _lat_dg() if rz.get("dg") else [
                {"tip": "cutie", "eticheta": "F>", "spec": ["50/51 · 50N/51N"], "legatura": "comanda",
                 "lista": ["Releu de protecție digital 50/51, 50N/51N, cu TC MT (sau senzori) și alimentare proprie"]}]
            if comp:
                if k == 1:
                    out.append(dict(celula_racord(umm), compartiment=COMP_UT))
                a["compartiment"] = COMP_UT
            out.append(a)
        else:
            sig = norme.siguranta_mt(int(sn), u_mt) if sn else None
            if comp and k == 1:
                out.append(dict(celula_racord(umm), compartiment=COMP_UT))
            out.append(_ap("sigurante_mt", f"Q2{suf}", "celula_sigurante", {"In_A": sig, "Um_kV": um}))
            if comp:
                out[-1]["compartiment"] = COMP_UT
        par_t = {"Sn_kVA": sn, "uk_pct": tr.get("uk_pct"), "Pk_W": tr.get("Pk_W"), "U_MT_kV": u_mt}
        if tr.get("grupa"):
            par_t["grupa"] = tr["grupa"]          # r11 (j41): grupa de conexiuni declarată (Dyn11 / Dyn5) pe desen și în listă
        if tr.get("izolatie") == "uscat":
            par_t.update({"izolatie": "uscat", "P0_W": tr.get("P0_W")})
        out.append(_ap("trafo", f"T{k}", "trafo", par_t, neutru_pamant=True))
        qj = _prot(rz.get("Q_JT"), f"Q3{suf}")
        if qj:
            out.append(qj)
        if ms.get("loc") == "JT" and ms.get("TC_primar_A"):
            # măsura JT: câte un grup TC + contor pe fiecare trafo (la 2 trafo în paralel)
            out.append(_ap("tc", f"TC{suf}", "tc", {"primar_A": ms["TC_primar_A"], "clasa": ms.get("clasa", "0,5S"), "Sn_VA": ms.get("Sn_VA", 5), "n": 3}, buc=3,
                           laterale=[{"tip": "cleme", "ref": f"K{suf}", "lista": ["Șir de cleme cu bloc de șuntare pe circuitul secundar de curent",
                                                                                 "capac transparent sigilabil"]},
                                     {"tip": "fuzibil", "ref": f"F{suf}", "spec": [f"3 × 2{NB}A gG"], "intrare_contor": "tensiune", "sursa_legatura": "amonte",
                                      "lista": ["Bloc siguranțe fuzibile circuit de tensiune contor 3 × 2 A gG, capace cu dublă sigilare"]},
                                     {"tip": "contor", "ref": f"P{suf}", "eticheta": "kWh · kVArh",
                                      "param": {"sablon": "contor", "retea": "tri", "masura": "semidirecta"}}]))
        return out
    ms = rz.get("masura") or {}
    aerian = bool(inp.get("pt_aerian")) and n_t == 1
    comp = compartimente_od(rz) and not aerian
    if comp:
        ap[0]["compartiment"] = COMP_OD
        marcaje_od(ap[0])
    if aerian:
        # r8 (#21, S10): PTA pe stâlp — fără celule de interior: separator tripolar de exterior cu CLP + descărcătoare
        # pe stâlp, siguranțe fuzibile MT de exterior, trafo pe platforma stâlpului, cutia TDJT (CD) la baza stâlpului
        sig = norme.siguranta_mt(int(sn), u_mt) if sn else None
        ap = [{"tip": "separator", "ref": "Q1", "spec": [f"{umm}{NB}kV · 400{NB}A", "separator exterior + CLP"],
               "lista": [f"Separator tripolar de exterior pe stâlp (STEP) {umm} kV, 400 A, cu cuțite de legare la pământ "
                         f"și dispozitiv de acționare de la sol", "SR EN 62271-102; montat pe stâlpul PTA"],
               "in_carcasa": False,
               "laterale": [{"tip": "descarcator_mt", "ref": "FV", "buc": 3, "spec": [f"ZnO {umm} kV"],
                             "lista": [f"Descărcătoare cu ZnO {umm} kV, 10 kA, pe stâlp, lângă trafo"]}]},
              {"tip": "fuzibil", "ref": "FMT", "spec": [f"3 × {sig}{NB}A", f"MT exterior {umm}{NB}kV"] if sig else ["MT exterior"],
               "lista": [f"Siguranțe fuzibile MT de exterior {umm} kV" + (f", In {sig} A" if sig else "")
                         + " (3 buc.), cu soclu pe consolă", "SR EN 60282-1; protecția trafo PTA"], "buc": 3,
               "in_carcasa": False}]
        par_t = {"Sn_kVA": sn, "uk_pct": tr.get("uk_pct"), "Pk_W": tr.get("Pk_W"), "U_MT_kV": u_mt}
        if tr.get("grupa"):
            par_t["grupa"] = tr["grupa"]
        ap.append(_ap("trafo", "T1", "trafo", par_t, neutru_pamant=True, in_carcasa=False))
        qj = _prot(rz.get("Q_JT"), "Q3")
        if qj:
            ap.append(qj)
        if ms.get("loc") == "JT" and ms.get("TC_primar_A"):
            ap += lant(1)[-1:] if lant(1)[-1].get("tip") == "tc" else []
    else:
        ap += lant(1)
    if ms.get("loc") == "MT":
        ap.insert(1, {"tip": "separator", "ref": "QM", "spec": ["celulă de măsură MT", "TT + TC, conform ATR"],
                      "lista": [f"Celulă de măsură MT {umm} kV cu transformatoare de tensiune și de curent",
                                "conform ATR / avizului OD"],
                      "laterale": [{"tip": "contor", "ref": "P", "eticheta": "kWh · kVArh", "spec": ["măsură MT", f"TT {umt}/0,1 kV · TC"],
                                    "lista": ["Contor electronic de decontare, măsură indirectă pe MT, cl. 0,5S",
                                              "furnizat și sigilat de OD, conform ATR"]}]})
        if comp:
            ap[1]["compartiment"] = COMP_OD
    cmt = inp.get("cablu_MT") if isinstance(inp.get("cablu_MT"), dict) else {}
    # r11 (industrial j60): cablul MT declarat (tip, secțiune, U0/U, L) scris pe racord — nu dimensionat de motor (OD)
    # r12 (#11): fără secțiune inventată când nu e declarată; tronsoanele cablului MT pe rând
    if cmt.get("tronsoane"):
        cond_mt, txt_mt = text_cablu_mt(cmt, u_mt)
        txt_mt = txt_mt.replace(" — conform ATR", "")
    else:
        cond_mt = (f"3 × 1 × {_f(cmt.get('S_mm2'), 0)} mm² {cmt.get('material') or 'Al'}" if cmt.get("S_mm2") else "3 × 1 (MT)")
        txt_mt = " ".join(x for x in [str(cmt.get("tip") or ""), (f"{cmt['U0_U_kV']} kV" if cmt.get("U0_U_kV") else ""),
                                      (f"L ≈ {_f(cmt.get('L_m', cmt.get('L')), 0)} m" if cmt.get("L_m", cmt.get("L")) else "")] if x) or "racord OD"
    m["intrari"] = [{"sursa": {"titlu": f"LES {umt} kV", "sub": "racord MT din rețeaua OD — conform ATR"
                               + (" · buclă intrare–ieșire" if nl > 1 else "")},
                     "cablu": {"ref": "C1", "cond": cond_mt, "text": f"{txt_mt} — conform ATR"}, "aparate": ap}]
    if aerian:
        m["intrari"][0]["sursa"] = {"titlu": f"LEA {umt} kV", "sub": "derivație aeriană din rețeaua OD — conform ATR"}
        m["intrari"][0]["cablu"] = {"ref": "C1", "cond": "3 × OL-Al", "text": "conductoare LEA — conform ATR"}
    cup = rz.get("cupla") or {}
    if n_t == 2:
        # r7 (#24): T2 din ACEEAȘI bară MT a postului (după celula de linie / de măsură), simetric pe secția 2 de bare JT —
        # nu o sursă separată. Rândurile goale aliniază lanțul T2 cu lanțul T1.
        k_mt = 2 if ms.get("loc") == "MT" else 1
        m["intrari"].append({"ramificatie": {"din": 0, "eticheta": f"bară MT {umt} kV"}, "sursa": {},
                             "cablu": {"ref": "", "cond": "", "text": ""},
                             "aparate": [{"tip": "gol"} for _ in range(k_mt)] + lant(2)})
    In_b = (rz.get("Q_JT") or {}).get("In_A")
    ik_b = _f(tr.get('Ik3max_bara_kA') if n_t == 1 else rz.get('Ik3max_bara_kA'), 1)
    if n_t == 1:
        et = f"TGJT {PUNCT} bare Cu {PUNCT} 3P + N + PE {PUNCT} {In_b}{NB}A {PUNCT} Ik3max {ik_b}{NB}kA"
    else:
        no = cup.get("stare", "NO") == "NO"
        et = (f"TGJT {PUNCT} secția 1 (T1) │ secția 2 (T2) {PUNCT} bare Cu 3P + N + PE {PUNCT} {In_b}{NB}A / secție {PUNCT} "
              f"Ik3max {ik_b}{NB}kA {PUNCT} cuplă QC normal {'deschisă' if no else 'închisă (T1 + T2 în paralel)'}")
    m["bara"] = {"afisare": True, "forteaza": True, "eticheta": et, "laterale": [_spd_bara()]}
    pl_in = inp.get("plecari") or []
    q0 = 4
    roots = _ierarhie(rz.get("plecari") or [])
    if n_t == 2:
        from .calc.scheme import _sectii_pt
        from .calc.comun import Jurnal
        pl_in = _sectii_pt(pl_in, inp, Jurnal())
    from .calc.scheme import expandeaza_plecari
    pl_in = expandeaza_plecari(pl_in)
    m["plecari"] = [_plecare(r, f"Q{i + q0}", pl_in[i] if i < len(pl_in) else None) for i, r in enumerate(roots)]
    if rz.get("servicii_proprii"):
        sp = _plecare(rz["servicii_proprii"], f"Q{len(m['plecari']) + q0}", {"nume": "Servicii proprii PT"})
        n1 = sum(1 for r in roots if r.get("sectie", 1) == 1) if n_t == 2 else len(m["plecari"])
        m["plecari"].insert(n1, sp)
    if n_t == 2:
        n1 = sum(1 for r in roots if r.get("sectie", 1) == 1) + (1 if rz.get("servicii_proprii") else 0)
        qj = rz.get("Q_JT") or {}
        no = cup.get("stare", "NO") == "NO"
        tip_q = "acb" if qj.get("tip") == "ACB" else "mccb"
        aar = bool(cup.get("AAR")) and no
        m["bara"]["cupla"] = {"n1": n1, "aparat": {
            "tip": tip_q, "ref": "QC", "spec": [f"4P {PUNCT} {qj.get('In_A')}{NB}A", ("NO · AAR · interblocaj 2/3" if aar else
                                                                                     "NO · interblocaj 2/3") if no else "NI · T1 + T2 în paralel"],
            "lista": [f"Întreruptor de cuplă longitudinală JT {qj.get('tip', 'ACB')} 4P, In {qj.get('In_A')} A, Icu ≥ "
                      f"{_f(qj.get('Icu_kA'), 0)} kA, cu acționare motorizată",
                      ("normal DESCHIS; interblocaj mecanic + electric „2 din 3” cu Q3.1 și Q3.2 (trafo niciodată în "
                       "paralel)" + ("; închis automat de AAR la pierderea tensiunii pe o secție" if aar else "")
                       if no else "normal ÎNCHIS — T1 și T2 în paralel (aceeași grupă de conexiuni, uk egal)")]}}
        if aar:
            # r11 (industrial j05 / j57): automatizarea AAR a cuplei — relee 27 pe secții, comandă pe Q3.1 / Q3.2 / QC
            m["bara"]["cupla"]["aparat"]["laterale"] = [{
                "tip": "cutie", "ref": "AAR", "eticheta": "automatizare", "legatura": "comanda", "spec": ["27 · 2 din 3", "Q3.1 · Q3.2 · QC"],
                "lista": ["Automatizare AAR de cuplă JT (PLC / releu dedicat): relee de minimă tensiune 27 pe secțiile 1 și 2, "
                          "comandă de deschidere Q3.k și de închidere QC, temporizare reglabilă",
                          "blocare la declanșare prin protecție (defect pe bară); interblocaj 2 din 3 — trafo niciodată în "
                          "paralel; revenire cu verificarea tensiunii"]}]
            m["bara"]["cupla"]["etichete"] = ["secția 1 (T1)", "secția 2 (T2)"]
    tit = (f"PTA {sn} kVA" if aerian else f"PT {sn} kVA") if n_t == 1 else f"PT 2 × {sn} kVA"
    if n_t == 2:
        m["carcasa"] = {"titlu": tit, "sub": f"PT {umt}/0,4 kV · 2 trafo" + (f" {tr.get('grupa')}" if tr.get("grupa") else "")
                        + " · cuplă JT "
                        + ("NO" if (rz.get("cupla") or {}).get("stare", "NO") == "NO" else "NI")
                        + (" + AAR" if (rz.get("cupla") or {}).get("AAR") else "")
                        + (" · măsură MT" if (rz.get("masura") or {}).get("loc") == "MT" else "")}
    else:
        m["carcasa"] = {"titlu": tit, "sub": f"post de transformare {umt}/0,4 kV · celule MT + trafo"
                        + (" uscat" if tr.get("izolatie") == "uscat" else "") + " + TGJT"
                        + (" · măsură MT" if (rz.get("masura") or {}).get("loc") == "MT" else "")}
    m["cartus"]["denumire2"] = (f"POST DE TRANSFORMARE {umt}/0,4 kV · {sn if n_t == 1 else '2 × ' + str(sn)} kVA"
                                + (" · CUPLĂ JT CU AAR" if (rz.get("cupla") or {}).get("AAR") else ""))
    if aerian:
        m["carcasa"] = {"titlu": "TDJT", "sub": f"cutie de distribuție JT la baza stâlpului PTA {sn} kVA · IP54 · "
                                               f"separator + siguranțe MT și trafo pe stâlp"}
        m["bara"]["eticheta"] = m["bara"]["eticheta"].replace("TGJT", "TDJT (cutie PTA)", 1)
        m["cartus"]["denumire2"] = f"POST DE TRANSFORMARE AERIAN PE STÂLP (PTA) {umt}/0,4 kV · {sn} kVA"
        m["lista_pe"] = ["Priză de pământ comună MT/JT la baza stâlpului PTA, R ≤ 4 Ω (calcul separat, conform ANRE)",
                         "neutrul trafo și masele (cuva, consolele, cutia TDJT) legate la priza de pământ"]
    else:     # D4: textele PTA nu mai sunt suprascrise de cele ale PT-ului în anvelopă
        m["lista_pe"] = ["Priză de pământ comună MT/JT conform ANRE: R ≤ 1 Ω + tensiuni de atingere (calcul separat)", "neutrul trafo legat la priza de pământ"
                         + (" (ambele trafo; N comun pe bara JT)" if n_t == 2 else "")]
    return "post de transformare"


# datele de fișă care trec în parametrii aparatelor (textul de pe desen și din listă), SPEC §E.3 v1.8
FISA_MODEL = ("producator", "model")
FISA_INVERTOR = FISA_MODEL + ("Umax_dc_V", "MPPT_min_V", "MPPT_max_V", "nr_MPPT", "Idc_max_A", "hibrid")
FISA_MODUL = FISA_MODEL + ("Pmax_W", "Voc_V", "Isc_A", "Vmpp_V", "Impp_A", "beta_Voc_pct_K", "Umax_sistem_V")
FISA_BATERIE = FISA_MODEL + ("chimie", "U_nom_V", "kWh_util")
FISA_SPD_CC = FISA_MODEL + ("In_kA", "Imax_kA", "Up_kV")


def _fisa(d, chei):
    """parametrii de fișă prezenți (nenuli) ai unui echipament"""
    return {k: d[k] for k in chei if isinstance(d, dict) and d.get(k) not in (None, "")}


def _modul(inp):
    st = inp.get("string") if isinstance(inp.get("string"), dict) else {}
    return st.get("modul") if isinstance(st.get("modul"), dict) else inp.get("modul") if isinstance(inp.get("modul"), dict) else {}


def _param_camp(inp, kwp, n, st=None, modul=None, n_mppt=None):
    """parametrii câmpului PV (șablonul „camp_pv”): puterea, modulul din fișă, stringul (v1.8: și pe MPPT)"""
    if st is None:
        st = inp.get("string") if isinstance(inp.get("string"), dict) else {}
    par = dict(_fisa(modul if modul is not None else _modul(inp), FISA_MODUL), kWp=kwp, buc=n)
    if n_mppt and n_mppt > 1 and st.get("n_stringuri_paralel"):
        par["n_MPPT"] = n_mppt
    for k_st, k in (("Voc_V", "Voc_V"), ("Uoc_V", "Voc_V"), ("Isc_A", "Isc_A"), ("beta_Voc_pct_K", "beta_Voc_pct_K"), ("beta", "beta_Voc_pct_K")):
        if st.get(k_st) is not None and k not in par and (par.get("model") or par.get("Pmax_W")):
            par[k] = st[k_st]
    if par.get("model") or par.get("Pmax_W"):
        for k in ("n_module", "n_stringuri_paralel"):
            if st.get(k):
                par[k] = st[k]
    return par


def _refs(k, unic=False):
    """notațiile unei ramuri PV: CEF / prosumator cu mai multe invertoare (PV1, S1, INV-1, Q1 …) sau prosumatorul
    cu un singur invertor (PV, S, INV, QI — notațiile istorice)"""
    if unic:
        return {"PV": "PV", "PE": "PE", "gPV": "F1.1", "SB": "SB", "SPDcc": "F2", "S": "S", "INV": "INV", "Q": "QI",
                "DDR": "DDR", "SPDca": "F3"}
    return {"PV": f"PV{k}", "PE": f"PE{k}", "gPV": f"F{k}.1", "SB": f"SB{k}", "SPDcc": f"F{k}.2", "S": f"S{k}",
            "INV": f"INV-{k}", "Q": f"Q{k}", "DDR": f"DDR{k}", "SPDca": f"F{k}.3"}


def _nod_ca(r, ref, mono, ems=None):
    """v1.9: nodul de la bornele c.a. ale invertorului / PCS (în afara tabloului) cu SPD c.a. tip 2 (cablu > 10 m sau
    cerut de fișă) și / sau legătura de comandă EMS → invertor. None dacă nu e nevoie."""
    lat = []
    if ems:
        lat.append(ems)
    if (r or {}).get("SPD_ca_invertor"):
        lat.append({"tip": "spd", "ref": ref, "param": {"sablon": "spd_ca", "tip": "T2", "poli": "2P" if mono else "4P",
                                                        "In_amonte_A": 63}})
    if not lat:
        return None
    return {"tip": "nod", "ref": "", "in_carcasa": False, "laterale": lat}


def _ems_marker(rz):
    """marcajul legăturii de comandă EMS → invertor / PCS (aceeași poziție în listă cu EMS-ul de la PCC, buc 0)"""
    li = rz.get("limitare_injectie")
    if not li:
        return None
    return {"tip": "cutie", "ref": "", "eticheta": "EMS", "legatura": "comanda", "w": 12, "h": 6, "spec": [],
            "lista": _lista_ems(li), "buc": 0}


def _lista_ems(li):
    p = "injecție zero" if li.get("zero") else f"P inj,max = {_f(li.get('P_kW'))} kW"
    return ["Controller EMS / power manager pentru limitarea injecției, compatibil cu invertoarele și PCS",
            f"{p}; comandă RS485 / Ethernet către {li.get('n_comandate')} invertoare / PCS, timp de răspuns conform ATR"]


def _aparate_limitare(rz, retea_mono, iac):
    """v1.9 (R5 P1-10): la punctul de racord — TC de măsură proprii + analizor de rețea (contor de control al
    injecției) + controller EMS (cu legătura de comandă spre invertoare, desenată la fiecare invertor)"""
    li = rz.get("limitare_injectie")
    if not li:
        return []
    p = prima_tc(iac)
    ar = {"tip": "cutie", "ref": "AR", "eticheta": "AR", "legatura": "masura", "spec": ["analizor rețea", "P la PCC"],
          "lista": [f"Analizor de rețea / contor de control al injecției, {'230 V' if retea_mono else '3 × 230/400 V'}, intrări TC /5 A, Modbus",
                    "măsoară puterea activă la punctul de racord (semn și valoare) pentru EMS"]}
    ems = {"tip": "cutie", "ref": "EMS", "eticheta": "EMS", "legatura": "masura",
           "spec": ["injecție zero" if li.get("zero") else f"P inj ≤ {_f(li.get('P_kW'))} kW", f"→ {li.get('n_comandate')} inv./PCS"],
           "lista": _lista_ems(li)}
    return [_ap("tc", "TCA", "tc", {"primar_A": p, "clasa": "0,5", "Sn_VA": 5, "n": 1 if retea_mono else 3},
                buc=1 if retea_mono else 3, laterale=[ar, ems])]


def prima_tc(i):
    for p in norme.TC_PRIMAR_A:
        if p >= (i or 0):
            return p
    return norme.TC_PRIMAR_A[-1]


def _lant_pv(inp, rz, r, g, cc, refs, kwp_i, n_mppt, st_g, mod_g, cert, mono, port_bat=None):
    """v1.8/v1.9: ramura unui invertor desenată complet — câmpul PV cu stringurile lui (pe MPPT), echipotențializarea
    ramelor, gPV pe string în cutia de joncțiune, separatorul de c.c. sub sarcină și SPD c.c., invertorul cu modelul
    din fișă (și portul de baterie, la hibrid), SPD c.a. la bornele invertorului, protecția și DDR-ul lui (dacă există)"""
    nsp, nm = st_g.get("n_stringuri_paralel"), st_g.get("n_module")
    n_str = int(nsp) * n_mppt if nsp else None
    mono = mono or (r or {}).get("retea") == "mono"       # r8: invertor monofazat pe rețea trifazată (pe o fază)
    echipot = {"tip": "cutie", "ref": refs["PE"], "eticheta": "PE", "legatura": "pe", "spec": ["echipot. rame"],
               "lista": ["Conductor de echipotențializare a ramelor modulelor și a structurii, FY 6 mm² Cu, galben-verde",
                         "legat la bara PE a cutiei de joncțiune / priza de pământ (16 mm² dacă există IPT)"]}
    ap = [_ap("string_pv", refs["PV"], "camp_pv", _param_camp(inp, kwp_i, 1, st=st_g, modul=mod_g, n_mppt=n_mppt),
              in_carcasa=False, laterale=[echipot], eticheta="")]
    integrat = bool(g.get("separator_cc_integrat"))
    voc = cc.get("Voc_Tmin_V") or rz.get("Voc_Tmin_V")
    u_gpv = 1000 if voc and voc <= 1000 else 1500 if voc and voc > 1100 else 1100
    ucpv = cc.get("SPD_cc_Ucpv_V") or rz.get("SPD_cc_Ucpv_V")
    if ucpv and ucpv > 1100:
        u_gpv = 1500          # r7: sistem de 1500 V c.c. (Umax c.c. al invertorului)
    sb = {"tip": "cutie", "ref": refs["SB"], "eticheta": "SB", "legatura": "grup", "spec": ["cutie de joncțiune"],
          "lista": [f"Cutie de joncțiune c.c. (string box), IP65, {u_gpv} V c.c., câte una pe invertor",
                    ("siguranțe gPV pe fiecare string (+ și −), " if (cc.get("gPV_In_A") or cc.get("gPV_generic")) else "") +
                    ("SPD c.c." if integrat else "separator de c.c. sub sarcină și SPD c.c.") + ", bară PE"]}
    if cc.get("gPV_In_A"):
        ap.append(_ap("gpv", refs["gPV"], "gpv", dict(_fisa(inp.get("gpv"), FISA_MODEL), In_A=cc["gPV_In_A"], U_V=u_gpv,
                                                      n=2 * (n_str or 1)), in_carcasa=False))
    elif cc.get("gPV_generic"):
        # r6 (fotovoltaic P1-7): gPV necesare (≥ 3 stringuri în paralel), Isc necunoscut — calibrul „conform proiect DC”
        ap.append(_ap("gpv", refs["gPV"], "gpv", dict(_fisa(inp.get("gpv"), FISA_MODEL), In_A=None, U_V=u_gpv,
                                                      n=2 * (n_str or 1), generic=True), in_carcasa=False))
    spd_f = inp.get("spd_cc") if isinstance(inp.get("spd_cc"), dict) else {}
    lat_spd = {"tip": "spd_cc", "ref": refs["SPDcc"],
               "param": dict(_fisa(spd_f, FISA_SPD_CC + ("tip",)), sablon="spd_cc",
                             Ucpv_V=cc.get("SPD_cc_Ucpv_V") or rz.get("SPD_cc_Ucpv_V") or inp.get("Ucpv_V") or 1100)}
    if rz.get("protectii_cc") is False:
        # Î5 (proiectant 28.10.2026): fără protecții pe partea de c.c. (declarat) — fără cutie de joncțiune / SPD c.c.;
        # rămâne doar separatorul de c.c. integrat în invertor (obligatoriu, SR HD 60364-7-712)
        sep = {"tip": "separator_cc", "ref": refs["S"], "in_carcasa": False, "spec": ["c.c. integrat", "în invertor"],
               "lista": ["Separator de c.c. sub sarcină integrat în invertor (conform fișei tehnice) — fără cutie de "
                         "protecții c.c. (declarat)"]}
    elif integrat:
        sep = {"tip": "separator_cc", "ref": refs["S"], "in_carcasa": False, "spec": ["c.c. integrat", "în invertor"],
               "lista": ["Separator de c.c. sub sarcină integrat în invertor (conform fișei tehnice)"], "laterale": [sb, lat_spd]}
    else:
        sep = {"tip": "separator_cc", "ref": refs["S"], "in_carcasa": False, "spec": ["c.c. sub sarcină"],
               "lista": ["Separator de c.c. sub sarcină pe intrările MPPT" + (f" ({n_mppt} MPPT)" if n_mppt > 1 else ""),
                         f"{u_gpv} V c.c., DC-PV2, SR EN 60947-3"], "laterale": [sb, lat_spd]}
    ap.append(sep)
    par_inv = dict(_fisa(g, FISA_INVERTOR), Pn_kW=g.get("Pn_kW"), Iac_max_A=r.get("Ib_A"), certificare=cert)
    if mono:
        par_inv["retea"] = "mono"
        if r.get("faza"):
            par_inv["faza"] = r["faza"]
    if port_bat:
        par_inv["hibrid"] = True
    inv = _ap("invertor", refs["INV"], "invertor", {k: v for k, v in par_inv.items() if v is not None}, in_carcasa=False)
    ems = _ems_marker(rz)
    if port_bat:
        inv["laterale"] = port_bat
    elif ems:
        inv["laterale"] = [ems]
        ems = None
    ap.append(inv)
    n = _nod_ca(r, refs["SPDca"], mono, ems)
    if n:
        ap.append(n)
    q = _prot(r.get("protectie"), refs["Q"], retea="mono" if mono else "tri")
    if q:
        ap.append(q)
    d = _ddr(r.get("DDR"), refs["DDR"])
    if d:
        ap.append(d)
    return ap


def _lant_bess(b, pcs, kwh, p_kw, mono, ref_q="QB", ucpv=None, sf=""):
    """v1.9 (R5 P1-11): ramura BESS cuplată în c.a. — baterie → separator-siguranță c.c. + SPD c.c. → PCS → (SPD c.a.)
    → protecția c.a."""
    fb = b.get("baterie") if isinstance(b.get("baterie"), dict) else b       # fișa bateriei (sau a sistemului BESS)
    fp = b.get("pcs") if isinstance(b.get("pcs"), dict) else b               # fișa PCS (sau a sistemului BESS)
    ub = fb.get("U_nom_V") if isinstance(fb, dict) else None
    lat_spd = {"tip": "spd_cc", "ref": f"FB{sf}.2", "param": {"sablon": "spd_cc", "Ucpv_V": ucpv or (
        prima_din(norme.SPD_CC_UCPV_V, 1.15 * ub) if ub else 1000)}}
    sep = {"tip": "separator_cc", "ref": f"SB-B{sf}", "in_carcasa": False, "spec": ["c.c. + siguranțe", "baterie"],
           "lista": ["Separator-siguranță c.c. baterie (+ și −), sub sarcină, între rack-ul bateriei și PCS",
                     (f"U {_f(ub, 0)} V c.c., " if ub else "") + "SR EN 60947-3 / SR EN 60269-6 (sau integrat în rack-ul BMS, conform fișei)"],
           "laterale": [lat_spd]}
    ap = [_ap("baterie", f"BAT{sf}", "baterie", dict(_fisa(fb, FISA_BATERIE), kWh=kwh), in_carcasa=False), sep,
          _ap("convertor_bess", f"PCS-{sf}" if sf else "PCS", "pcs",
              dict(_fisa(fp, FISA_INVERTOR), Pn_kW=p_kw, Iac_max_A=pcs.get("Ib_A")), in_carcasa=False)]
    return ap


def prima_din(serie, v):
    return next((x for x in serie if x >= v), serie[-1])


INVERTOARE_COMPACT_PESTE = 6     # r7 (P1 lizibilitate): peste 6 invertoare (8 pe un rând ies la 57–60 %), cele identice compact


def _u_ca(ap_lista, U):
    """r7 (P0-3): aparatele unei rețele de 800 V c.a. — invertoarele „3 × 800 V”, întreruptoarele 3P cu Ue 800 V,
    SPD-urile c.a. pentru 800 V (fără N). Se aplică pe tot arborele de ramuri."""
    def ap(a):
        par = a.get("param")
        if not isinstance(par, dict):
            return
        sb = par.get("sablon")
        if sb == "invertor":
            par["U_ca_V"] = U
        elif sb in ("mccb", "acb", "mcb"):
            par["poli"] = "3P"
            par["U_V"] = U
        elif sb == "spd_ca":
            par["poli"] = "3P"
            par["U_V"] = U
        elif sb in ("tc", "contor"):
            par["U_V"] = U
        elif sb == "pcs":
            par["U_ca_V"] = U

    def br(b):
        for a in b.get("aparate") or []:
            ap(a)
            for l in a.get("laterale") or []:
                ap(l)
        for c in b.get("copii") or []:
            br(c)
    for b in ap_lista:
        br(b)


def _ramura_compacta(inp, rz, r, g, k, k_rep, mono, port, cert):
    """r7 (P1 lizibilitate, > 8 invertoare): invertorul INV-k identic cu INV-k_rep (același grup, același calcul) —
    desenat în coloană îngustă cu eticheta lui, protecția Qk (+ DDR, SPD c.a.) și cablul; partea de c.c. (câmp PV, cutia
    de joncțiune, separatorul, SPD c.c.) e cea a reprezentantului, cu cantitatea × n în listă."""
    refs = _refs(k)
    mono = mono or r.get("retea") == "mono"
    par = dict(_fisa(g, FISA_INVERTOR), Pn_kW=g.get("Pn_kW"), Iac_max_A=r.get("Ib_A"), certificare=cert)
    if mono:
        par["retea"] = "mono"
        if r.get("faza"):
            par["faza"] = r["faza"]
    if port:
        par["hibrid"] = True
    if rz.get("U_ca_V"):
        par["U_ca_V"] = rz["U_ca_V"]
    par = {kk: v for kk, v in par.items() if v is not None}
    den, car = text_lista("invertor", par)
    inv = {"tip": "invertor", "ref": refs["INV"], "in_carcasa": False, "spec": [f"{_f(g.get('Pn_kW'))}{NB}kW", f"idem INV-{k_rep}"],
           "lista": [den, car] if car and car != "—" else [den]}
    ems = _ems_marker(rz)
    if port:
        inv["laterale"] = port
    elif ems:
        inv["laterale"] = [ems]
        ems = None
    ap = [inv]
    n = _nod_ca(r, refs["SPDca"], mono, ems)
    spd_ca = bool(n and any(l.get("tip") == "spd" for l in n["laterale"]))
    if n and ems:
        n["laterale"] = [ems]           # comanda EMS rămâne la invertor; SPD c.a. la borne = idem reprezentant (× n în listă)
        ap.append(n)
    q = _prot(r.get("protectie"), refs["Q"], retea="mono" if mono else "tri")
    if q:
        q["param"]["lat_desen"] = 18     # textul protecției pe rânduri scurte (coloană îngustă)
        ap.append(q)
    d = _ddr(r.get("DDR"), refs["DDR"])
    if d:
        d["param"]["lat_desen"] = 18
        ap.append(d)
    cab = dict(_cablu(r))
    cab["text"] = f"idem INV-{k_rep}"
    return {"sursa": {"titlu": f"PV {k}", "sub": f"idem PV{k_rep}"},
            "cablu": {"ref": "", "cond": "c.c.", "text": "H1Z2Z2-K"}, "cablu_ca": cab, "aparate": ap, "compact": True}


INVERTOARE_COMPRIMA_PESTE = 24  # r8 (lizibilitate CEF mari): peste 24 de invertoare, coloanele „idem” consecutive → o coloană


def _comprima_idem(br):
    """r8: coloanele compacte consecutive identice (același reprezentant „idem INV-r”) devin o singură coloană
    „INV-a … INV-b” cu protecțiile „Qa … Qb” (cantitatea în listă) — CEF de MW cu zeci de invertoare rămâne lizibilă."""
    out, i = [], 0
    while i < len(br):
        b = br[i]
        rep = (b.get("sursa") or {}).get("sub") if b.get("compact") else None
        j_ = i
        while rep and j_ + 1 < len(br) and br[j_ + 1].get("compact") and (br[j_ + 1].get("sursa") or {}).get("sub") == rep:
            j_ += 1
        if j_ - i < 2:
            out.extend(br[i:j_ + 1])
            i = j_ + 1
            continue
        grup = br[i:j_ + 1]
        n = len(grup)
        k_a = (grup[0]["sursa"]["titlu"]).replace("PV ", "")
        k_b = (grup[-1]["sursa"]["titlu"]).replace("PV ", "")
        nb = copy.deepcopy(grup[0])
        nb["sursa"] = {"titlu": f"PV {k_a}…{k_b}", "sub": f"{n} × {rep}"}
        for a in nb["aparate"]:
            r0 = str(a.get("ref") or "")
            mo = re.match(r"^([A-Z]+-?)(\d+)$", r0)
            if mo:
                a["ref"] = f"{mo.group(1)}{k_a}…{k_b}"
                a["buc"] = int(a.get("buc", 1)) * n
            if a.get("tip") == "invertor":
                a["spec"] = [a["spec"][0], f"{n} × {a['spec'][1]}"] if len(a.get("spec") or []) > 1 else a.get("spec")
            for l in a.get("laterale") or []:
                if l.get("ref"):
                    l["buc"] = int(l.get("buc", 1)) * n
        cab = dict(nb.get("cablu_ca") or {})
        cab["text"] = f"{n} × {cab.get('text', '')}"
        if isinstance(cab.get("param"), dict):
            cab["buc"] = n
        nb["cablu_ca"] = cab
        nb["_obiecte"] = [x.get("_obiect") for x in grup]
        out.append(nb)
        i = j_ + 1
    return out


def _inmulteste_cc(ap, n_g):
    """r7: reprezentantul unui grup de n_g invertoare identice — partea de c.c. (câmp PV, gPV, separator, cutie de joncțiune,
    SPD c.c., echipotențializare) apare o singură dată pe desen, cu cantitatea × n_g în listă"""
    for a in ap:
        t = a.get("tip")
        if t == "nod":            # SPD c.a. la bornele invertorului (desenat la reprezentant)
            for l in a.get("laterale") or []:
                if l.get("tip") == "spd":
                    l["buc"] = int(l.get("buc", 1)) * n_g
        if t in ("string_pv", "gpv", "separator_cc"):
            a["buc"] = int(a.get("buc", 1)) * n_g
            if t == "string_pv" and isinstance(a.get("param"), dict):
                a["param"]["buc"] = n_g
            for l in a.get("laterale") or []:
                l["buc"] = int(l.get("buc", 1)) * n_g


def _cef(inp, rz, m):
    inv_r = rz.get("invertoare") or []
    st = inp.get("string") or {}
    kwp = inp.get("kWp")
    n_inv = max(1, len(inv_r))
    mono = rz.get("retea") == "mono"
    U = rz.get("U_ca_V") or 400
    intrari = []
    # v1.8: FIECARE invertor e o ramură proprie (fără „× n” / „…”): câmpul PV cu stringurile lui pe MPPT, partea de
    # c.c. completă (gPV pe string în cutia de joncțiune, separator, SPD c.c.), echipotențializarea ramelor, invertorul
    # cu modelul din fișă, protecția și DDR-ul lui de c.a. și cablul până la bara TGD-CF.
    # r7: peste 8 invertoare, al doilea … al n-lea invertor IDENTIC al unui grup se desenează compact (INV-k + Qk, cu
    # eticheta lui), iar partea de c.c. comună apare la reprezentant cu cantitatea × n
    inv_in = []
    for gi, grp in enumerate(inp.get("invertoare") or []):
        for _ in range(int(grp.get("n", 1))):
            inv_in.append((gi, grp))
    compact = len(inv_r) > INVERTOARE_COMPACT_PESTE
    k_grup = {}
    for i in range(len(inv_r)):
        k_grup.setdefault(inv_in[i][0] if i < len(inv_in) else 0, []).append(i + 1)
    rep_k = {}
    ccg = rz.get("cc_grupuri") or []
    cert = "Ord. ANRE 208/2018 (RfG) + ATR"
    for i, r in enumerate(inv_r):
        k = _nr_obiect(r, i + 1)          # r8: la secții, ordinea rezultatelor poate diferi de ordinea grupurilor
        gi, g = inv_in[k - 1] if k - 1 < len(inv_in) else (0, {})
        bz = rz.get("BESS") or {}
        port = _port_baterie(inp, rz, mono, obiect=f"INV-{k}", k=k if len(bz.get("la") or []) > 1 else None) \
            if bz.get("cuplaj") == "cc" and f"INV-{k}" in (bz.get("la") or []) else None
        ks = k_grup.get(gi, [k])
        if compact and len(ks) > 1 and gi in rep_k:
            intrari.append(dict(_ramura_compacta(inp, rz, r, g, k, rep_k[gi], mono, port, cert), _obiect=f"INV-{k}"))
            if g.get("existent") is True:
                _marcheaza_existent(intrari[-1])
            continue
        cc = ccg[gi] if gi < len(ccg) else {x: rz.get(x) for x in ("SPD_cc_Ucpv_V", "gPV_In_A", "Voc_Tmin_V", "gPV_generic",
                                                                   "string_generic")}
        st_g = dict(st)
        st_g.update(g.get("string") or {})
        mod_g = g.get("modul") if isinstance(g.get("modul"), dict) else _modul(inp)
        n_mppt = int(cc.get("n_MPPT") or 1)
        nsp, nm, pm = st_g.get("n_stringuri_paralel"), st_g.get("n_module"), (mod_g or {}).get("Pmax_W")
        n_str = int(nsp) * n_mppt if nsp else None
        s_pn = sum(float(x.get("Pn_kW") or 0) for _, x in inv_in) or 1.0
        kwp_i = (nm * n_str * pm / 1000.0) if (nm and n_str and pm) else (
            (kwp * float(g.get("Pn_kW") or 0) / s_pn) if kwp and g.get("Pn_kW") else ((kwp / n_inv) if kwp else None))
        ap = _lant_pv(inp, rz, r, g, cc, _refs(k), kwp_i, n_mppt, st_g, mod_g, cert, mono, port)
        pn = g.get("Pn_kW")
        sub = (f"{n_mppt} MPPT × " if n_mppt > 1 else "") + (f"{nsp} str. × {nm} mod." if nsp and nm else
                                                               "stringuri conform proiect DC" if cc.get("string_generic") else
                                                               f"{_f(kwp_i)} kWp" if kwp_i else "invertor " + f"{_f(pn)} kW")
        if port:
            sub = f"{sub} {PUNCT} hibrid + baterie c.c."
        if r.get("faza"):
            sub = f"{sub} {PUNCT} {r['faza']}"
        titlu = f"CÂMP PV {k}"
        if compact and len(ks) > 1:
            rep_k[gi] = k
            _inmulteste_cc(ap, len(ks))
            titlu = f"CÂMP PV {k} … {ks[-1]}"
            sub = f"{len(ks)} × identice {PUNCT} {sub}"
        ccb = rz.get("cablu_cc") or {}
        txt_cc = (f"{ccb.get('tip') or 'H1Z2Z2-K'} 2 × 1 × {_f(ccb.get('S_mm2'), 0)}{NB}mm² Cu"
                  + (f" {PUNCT} L ≈ {_f(ccb.get('L_m'), 0)}{NB}m" if ccb.get("L_m") else "")) if ccb else "H1Z2Z2-K"
        intrari.append({"sursa": {"titlu": titlu, "sub": sub}, "_obiect": f"INV-{k}",
                        "cablu": {"ref": "", "cond": "c.c.", "text": txt_cc}, "cablu_ca": _cablu(r), "aparate": ap})
        if g.get("existent") is True:
            _marcheaza_existent(intrari[-1])
    pcs = rz.get("PCS")
    pcs_l = rz.get("PCS_lista") or ([pcs] if pcs else [])
    for ip_, pcs in enumerate(pcs_l, 1):
        # r8 (BESS): n_pcs PCS identice — fiecare cu ramura lui (BATk → SB-Bk → PCS-k → QBk); kWh împărțit egal
        b = _bess_calc(inp, rz)
        sf = "" if len(pcs_l) == 1 else str(ip_)
        kwh = b.get("kWh")
        kwh_u = (float(kwh) / len(pcs_l)) if (kwh and len(pcs_l) > 1) else kwh
        ap = _lant_bess(b, pcs, kwh_u, pcs.get("Pn_kW") if len(pcs_l) > 1 else b.get("P_kW"), mono, sf=sf)
        if _ems_marker(rz):
            ap[-1]["laterale"] = [_ems_marker(rz)]        # comanda EMS → PCS
        n = _nod_ca(pcs, f"FB{sf}.3", mono)
        if n:
            ap.append(n)
        q = _prot(pcs.get("protectie"), f"QB{sf}", retea="mono" if mono else "tri")
        if q:
            ap.append(q)
        d = _ddr(pcs.get("DDR"), f"DDR-B{sf}")
        if d:
            ap.append(d)
        intrari.append({"sursa": {"titlu": "BESS" if not sf else f"BESS {sf}",
                                  "sub": f"{_f(pcs.get('Pn_kW') if sf else b.get('P_kW'))} kW / {_f(kwh_u)} kWh"},
                        "_obiect": pcs.get("obiect") or ("PCS" if not sf else f"PCS-{sf}"),
                        "cablu": {"ref": "", "cond": "c.c.", "text": ""}, "cablu_ca": _cablu(pcs), "aparate": ap})
    if rz.get("sectii"):
        return _cef_sectii(inp, rz, m, intrari, mono, U, kwp)
    if rz.get("tgd_cf"):
        return _cef_tgd(inp, rz, m, intrari, mono, U, kwp,
                        _aparate_limitare(rz, mono, (rz.get("sume") or {}).get("Iac_total_A")))
    if rz.get("tablouri_intermediare"):
        return _cef_cascada(inp, rz, m, intrari, mono, U, kwp,
                            _aparate_limitare(rz, mono, (rz.get("sume") or {}).get("Iac_total_A")))
    if len(inv_r) > INVERTOARE_COMPRIMA_PESTE:
        intrari = _comprima_idem(intrari)
    for b_ in intrari:
        b_.pop("_obiect", None)
        b_.pop("_obiecte", None)
    m["intrari"] = intrari
    qg = rz.get("QG") or {}
    s = rz.get("sume") or {}
    spd = _spd_bara()
    if mono:
        spd["param"]["poli"] = "2P"
    conf = "L + N + PE" if mono else ("3P + PE" if U > 400 else "3P + N + PE")
    m["bara"] = {"afisare": True, "eticheta": f"Bare Cu {PUNCT} {conf}" + (f" {PUNCT} 3 × {U}{NB}V c.a." if U > 400 else "")
                 + f" {PUNCT} Σ Iac = {_f(s.get('Iac_total_A'))}{NB}A", "laterale": [spd]}
    apq = []
    qga = _prot(qg.get("protectie") or qg, "QG", bd=True)
    if qga:
        if (rz.get("masura") or {}).get("loc") == "MT" and (rz.get("trafo") or {}) and not (rz.get("trafo") or {}).get("existent"):
            # echipa1 P1-9: racord în MT — protecția de interfață e pe MT (QI cu 27/59/59N/81), nu pe QG JT
            qga["spec"] = list(qga.get("spec") or []) + ["PI pe MT (QI)"]
        else:
            qga["param"]["interfata"] = True
            qga["laterale"] = _lat_pi(inp)
        apq.append(qga)
    d = _ddr(qg.get("DDR"), "DDR-G")
    if d:
        apq.append(d)
    tcp = rz.get("TC_primar_A") or (qg.get("TC_primar_A"))
    masura_mt = (rz.get("masura") or {}).get("loc") == "MT"
    if mono:
        apq.append(_ap("contor_direct", "P1", "contor", {"retea": "mono", "masura": "directa", "bidirectional": True}))
    elif tcp and not masura_mt:
        apq.append(_ap("tc", "TC", "tc", {"primar_A": tcp, "clasa": "0,5S", "Sn_VA": 5, "n": 3}, buc=3,
                       laterale=[{"tip": "contor", "ref": "P1", "eticheta": "kWh",
                                  "param": {"sablon": "contor", "retea": "tri", "masura": "semidirecta", "bidirectional": True}}]))
    lim = _aparate_limitare(rz, mono, s.get("Iac_total_A"))
    extra, dest, pt_copii, tg_copii, cab0 = _racord_cef(rz, mono, U, lim)
    apq += extra
    tr = rz.get("trafo")
    ap_tab = dest.pop("_aparate_tablou", None)
    m["plecari"] = [{"aparate": apq, "cablu": cab0, "sarcina": dest}]
    if ap_tab:
        m["plecari"][0]["aparate_tablou"] = ap_tab
    if pt_copii:
        m["plecari"][0].update(copii=pt_copii, pt=True)
        if tr and tr.get("existent"):
            m["plecari"][0].update(pt=False, tablou_existent=True)     # r9: PT existent — fără anvelopă / bare noi
    elif tg_copii:
        m["plecari"][0].update(copii=tg_copii, tablou_existent=True)
    m["carcasa"] = {"titlu": "TGD-CF", "sub": f"tablou general c.a. fotovoltaic · Σ Pn = {_f(s.get('Pn_total_kW'))} kW · categoria {rz.get('categorie_RfG', '—')} RfG"
                    + (f" · 3 × {U} V c.a." if U > 400 else "")}
    if U > 400:
        _u_ca(m["intrari"] + m["plecari"], U)
        spd["param"].update(poli="3P", U_V=U)
    if rz.get("bess_singur"):
        m["carcasa"]["sub"] = f"tablou general c.a. BESS · P = {_f(s.get('Pn_total_kW'))} kW · categoria {rz.get('categorie_RfG', '—')} RfG"
        b = _bess_calc(inp, rz)
        m["cartus"]["denumire2"] = f"BESS {_f(b.get('P_kW') or s.get('Pn_total_kW'))} kW / {_f(b.get('kWh'))} kWh"
    else:
        m["cartus"]["denumire2"] = (f"CEF {_f(kwp)} kWp" if kwp else f"CEF {_f(s.get('Pn_total_kW'))} kW") + \
            (" + BESS" if pcs or (rz.get("BESS") or {}).get("cuplaj") == "cc" else "")
    return "CEF"


def _racord_cef(rz, mono, U, lim):
    """r12 (refactor din `_cef`): partea de racord a CEF — aparatele de limitare puse pe linia QG (când e cazul),
    destinația C0 (PT nou / PT existent / TG existent / PCC), tabloul de racord desenat sub C0 și cablul C0.
    Întoarce (aparate_extra, dest, pt_copii, tg_copii, cab0)."""
    apq = []
    rac = rz.get("racord") or {}
    masura_mt = (rz.get("masura") or {}).get("loc") == "MT"
    tg_copii = None
    tr = rz.get("trafo")
    if rac.get("tg_existent") and lim:
        # r7 (P1): injecție zero / limitată — TC + analizorul AR măsoară la PUNCTUL DE RACORD, pe alimentarea TG-ului
        # existent (consum + producție), nu pe plecarea PV; EMS comandă invertoarele (marcaj EMS la fiecare invertor)
        tg_copii = _tg_existent_pcc(lim, mono, "PCC — rețea OD", "alimentarea TG existent · contor bidirecțional OD")
    elif not (tr and tr.get("existent")):
        apq += lim
    pt_copii = None
    if tr and not tr.get("existent"):
        # r6 (fotovoltaic P0-2): PT propriu NOU — T1 în post (nu în TGD-CF): TGD-CF → C0 (JT) → bara JT a PT → Q JT →
        # T1 → celula trafo → celula de linie → LES 20 kV → PCC MT. r7: n trafo, celula de măsură MT
        pt = rz.get("PT") or {}
        n_t = int(pt.get("n_trafo") or 1)
        ujt = fmt_ro(pt.get("U_JT_kV") or 0.4)
        dest = {"titlu": f"PT {tr.get('Sn_kVA')} kVA" if n_t == 1 else f"PT {n_t} × {tr.get('Sn_kVA')} kVA",
                "sub": f"post de transformare nou 20/{ujt} kV"
                + (f" {PUNCT} bare JT cu cuplă QC normal închisă ({' + '.join(f'T{k}' for k in range(1, n_t + 1))})" if n_t > 1 else "")
                + (f" {PUNCT} măsură de decontare pe MT" if masura_mt else "")}
        pt_copii = _ramura_pt_nou(pt, tr)
    elif tr:
        # v1.9 (R5 P0-4): PT existent = sursa (Ik din trafo); nu se desenează un transformator nou
        dest = {"titlu": f"PT EXISTENT {tr.get('Sn_kVA')} kVA", "sub": f"bara JT a PT-ului existent {PUNCT} Ik3 {_f(tr.get('Ik3max_bara_kA'), 1)} kA"
                + (f" {PUNCT} măsură MT în celula existentă" if masura_mt else "")}
        qpt = _prot(rz.get("Q_PT"), "QPT") if rz.get("Q_PT") else None
        if qpt and not rac.get("tg_existent"):
            # r9 (fotovoltaic #41, #42): plecarea NOUĂ din tabloul JT al PT-ului existent — QPT la capătul sursă al C0.
            # echipa1 P0-2: C0 → QPT → bara JT a PT (QPT protejează C0 la sursă); transformatorul existent intră pe bară
            # prin Q JT existent, iar plecările existente rămân pe bară — NU trec prin QPT
            qpt["spec"] = list(qpt.get("spec") or []) + ["plecare NOUĂ în TGJT existent"]
            n_tr = int(tr.get("n_trafo") or 1)
            t_txt = f"T EXISTENT {tr.get('Sn_kVA')} kVA" if n_tr == 1 else f"{n_tr} × T EXISTENTE {tr.get('Sn_kVA')} kVA"
            pt_copii = [{"aparate": [], "cablu": {"ref": "", "cond": "", "text": "prin Q JT existent"},
                         "sarcina": {"titlu": t_txt, "sub": "sosirea trafo pe bara JT prin Q JT existent · celule MT existente"}},
                        {"aparate": [], "cablu": {"ref": "", "cond": "", "text": "existente"},
                         "sarcina": {"titlu": "PLECĂRI EXISTENTE", "sub": "TGJT existent · neafectate (conform releveu)"}}]
            dest = dict(dest, titlu=f"PT EXISTENT {tr.get('Sn_kVA')} kVA — BARA JT, PLECARE NOUĂ QPT", _aparate_tablou=[qpt])
        if lim and not rac.get("tg_existent"):
            # r11 (fotovoltaic #4): injecție zero / limitată la PT existent — TC + AR + EMS pe sosirea trafo-ului în TGJT
            # (punctul de racord: consum + producție), nu pe plecarea CEF
            pcc = _tg_existent_pcc(lim, mono, f"T EXISTENT {tr.get('Sn_kVA')} kVA — PCC",
                                   "sosirea trafo în TGJT · schimbul total cu rețeaua" + (" · măsură MT" if masura_mt else ""))[0]
            pcc["aparate"][0]["spec"] = ["sosire trafo existent (Q JT)"]
            if pt_copii and pt_copii[0]["sarcina"]["titlu"].startswith(("T EXISTENT", f"{int(tr.get('n_trafo') or 1)} × T")):
                pt_copii = [pcc] + pt_copii[1:]        # sosirea trafo cu TC / AR / EMS înlocuiește sosirea simplă
            else:
                pt_copii = (pt_copii or []) + [pcc]
    else:
        dest = {"titlu": "PCC — RED 0,4 kV", "sub": "punct comun de cuplare conform ATR"}
    if rac.get("tg_existent"):
        qt = rz.get("Q_TG") or {}
        qtxt = f"{qt.get('tip', '')} {qt.get('curba') or ''}{qt.get('In_A')}{NB}A".replace("  ", " ").strip() if qt.get("In_A") else "Q de racord conform releveu"
        dest = {"titlu": "TG EXISTENT", "sub": f"racord pe bara TG prin {qtxt} (existent)" +
                (f" {PUNCT} alimentat din PT existent {tr.get('Sn_kVA')} kVA" if tr else f" {PUNCT} măsura la punctul de racord OD")}
    c0 = rz.get("C0")
    cab0 = _cablu(c0, "C0") if c0 else {"ref": "C0", "cond": "L + N + PE" if mono else ("3 + PE" if U > 400 else "3 + N + PE"),
                                         "text": "legătura JT T1 – TGD-CF · conform proiect" if pt_copii else "conform ATR"}
    if c0:
        dest = dict(dest, sub=dest["sub"] + f" {PUNCT} {_sub_ramura(c0)}")
    return apq, dest, pt_copii, tg_copii, cab0



# ------------------------------------------------------------------------------------------------ r12: PI, monitorizare
ORDIN_PI_IMPLICIT = "Ord. ANRE 208/2018"

# Reglajele implicite ale protecției de interfață (valorile proiectantului, Ord. ANRE 208/2018 / 228/2018 — se
# suprascriu din ATR prin `protectie_interfata.reglaje`): (cheie, funcție, reglaj, temporizare)
PI_REGLAJE = (
    ("U_max", "Tensiune maximă U> (59)", "1,15·Un", "0,5 s"),
    ("U_min", "Tensiune minimă U< (27)", "0,85·Un", "3,2 s"),
    ("f_max", "Frecvență maximă f> (81>)", "52 Hz", "0,5 s"),
    ("f_min", "Frecvență minimă f< (81<)", "47,5 Hz", "0,5 s"),
    ("U_10min", "Tensiune medie pe 10 min (59 med.)", "1,10·Un", "603 s"),
    ("reconectare", "Reconectare automată după declanșare", "U, f în limite", "900 s"),
    ("hvrt_lvrt", "Capabilitate HVRT / LVRT", "activă", "conform ordin"),
    ("statism", "Statism (reducerea P la f > 50,2 Hz)", "5 %", "—"),
    ("cosfi", "Factor de putere (Q reglabil)", "0,8 ind – 0,8 cap", "—"),
)


def tabel_pi(inp, tip):
    """r12 (proiecte reale, Top 15 #7): tabelul „Parametri și protecții invertoare / PI” de pe planșă — valori implicite
    (Ord. ANRE 208/2018 sau ordinul din `protectie_interfata.ordin`), suprascrise din `protectie_interfata.reglaje`
    (dict {cheie: [reglaj, temporizare]} sau listă completă de rânduri [funcție, reglaj, temporizare]). None = fără tabel
    (`protectie_interfata` false / {"tabel": false})."""
    pi = inp.get("protectie_interfata")
    if pi is False or (isinstance(pi, dict) and pi.get("tabel") is False):
        return None
    if tip not in ("cef", "prosumator") or not (inp.get("invertoare") or inp.get("invertor") or inp.get("Pn_inv_kW")):
        return None
    pi = pi if isinstance(pi, dict) else {}
    ordin = str(pi.get("ordin") or ("Ord. ANRE 228/2018" if tip == "prosumator" else ORDIN_PI_IMPLICIT))
    if not ordin.lower().startswith("ord"):
        ordin = "Ord. ANRE " + ordin
    reg = pi.get("reglaje")
    if isinstance(reg, list) and reg and all(isinstance(x, (list, tuple)) and len(x) >= 2 for x in reg):
        randuri = [[str(x[0]), str(x[1]), str(x[2]) if len(x) > 2 else "—"] for x in reg]
    else:
        reg = reg if isinstance(reg, dict) else {}
        randuri = []
        for k, f, v, t in PI_REGLAJE:
            o = reg.get(k)
            if isinstance(o, (list, tuple)) and o:
                v = str(o[0]); t = str(o[1]) if len(o) > 1 else t
            elif isinstance(o, dict):
                v = str(o.get("reglaj", v)); t = str(o.get("t", o.get("temporizare", t)))
            elif o is not None:
                v = str(o)
            randuri.append([f, v, t])
    return {"titlu": "PARAMETRI ȘI PROTECȚII INVERTOARE / PROTECȚIA DE INTERFAȚĂ",
            "sursa": f"valori conform {ordin}" + (" — suprascrise din ATR" if pi.get("reglaje") else
                                                  " (implicite) — se confirmă cu ATR"),
            "randuri": randuri}


def monitorizare(inp):
    """r12 (Top 15 #8): echipamentele de monitorizare și măsură ale CEF / prosumatorului — {smart_meter, smartlogger,
    rs485, contor_productie}: dict (model, TC_primar_A …) sau True. `monitorizare: true` = toate cele uzuale."""
    m = inp.get("monitorizare")
    if m is True:
        m = {"smart_meter": True, "smartlogger": True, "rs485": True}
    out = {}
    if isinstance(m, dict):
        for k in ("smart_meter", "smartlogger", "rs485"):
            v = m.get(k)
            if v:
                out[k] = dict(v) if isinstance(v, dict) else {}
        if "smartlogger" in out and m.get("rs485") is None:
            out["rs485"] = {}
    cp = inp.get("contor_productie") if inp.get("contor_productie") is not None else (m or {}).get("contor_productie") \
        if isinstance(m, dict) else None
    if cp:
        out["contor_productie"] = dict(cp) if isinstance(cp, dict) else {}
    return out


def _lat_pi(inp, ref_q="QG"):
    """lateralul PI de pe întreruptorul de interfață (+ sursa neîntreruptibilă a releului, dacă e declarată)"""
    pi = inp.get("protectie_interfata") if isinstance(inp.get("protectie_interfata"), dict) else {}
    ordin = str(pi.get("ordin") or ORDIN_PI_IMPLICIT)
    if not ordin.lower().startswith("ord"):
        ordin = "Ord. ANRE " + ordin
    releu = pi.get("releu")
    lat = [{"tip": "cutie", "eticheta": "PI", "spec": [str(releu)[:16] if releu else "U / f", "27/59/81"],
            "legatura": "comanda",
            "lista": [f"Protecție de interfață (anti-insularizare) cu declanșare pe bobina BD a {ref_q}"
                      + (f" — releu {releu}" if releu else "") + " — reglaje în tabelul de pe planșă / conform ATR",
                      f"{ordin} (RfG)"]}]
    ups = pi.get("ups_VA")
    if ups:
        lat.append({"tip": "cutie", "ref": "UPS", "eticheta": "~ / =", "legatura": "forta",
                    "spec": [f"{fmt_ro(ups, 0)} VA", "releu PI"],
                    "lista": [f"Sursă neîntreruptibilă (UPS) {fmt_ro(ups, 0)} VA, intrare / ieșire 230 V c.a. ± 10 %",
                              "alimentarea releului de interfață și a bobinei de declanșare (funcționare la lipsa tensiunii)"]})
    return lat


def _lat_smart(mon, n_inv, tc_txt=None):
    """smart meter-ul (pe TC-urile de la punctul de racord) și SmartLogger-ul legat pe RS485 (linie de comunicație)"""
    out = []
    sm = mon.get("smart_meter")
    if sm is not None:
        mod = sm.get("model")
        out.append({"tip": "cutie", "ref": "SM", "eticheta": "kWh · kVArh", "legatura": "masura",
                    "spec": [str(mod)[:16] if mod else "smart meter", "RS485"],
                    "lista": ["Smart meter (contor de control al schimbului cu rețeaua) trifazat"
                              + (f" — {mod}" if mod else "") + ", intrări TC /5 A, Modbus RS485",
                              "montat la punctul de racord" + (f", pe TC {tc_txt}" if tc_txt else "")
                              + "; date către SmartLogger (limitarea injecției / monitorizare)"]})
    sl = mon.get("smartlogger")
    if sl is not None:
        mod = sl.get("model")
        out.append({"tip": "cutie", "ref": "SL", "eticheta": "LOGGER", "legatura": "comunicatie",
                    "spec": [str(mod)[:16] if mod else "SmartLogger", f"RS485 → {n_inv} inv."],
                    "lista": ["Dispozitiv de monitorizare și comunicații (SmartLogger / datalogger)" + (f" — {mod}" if mod else ""),
                              f"magistrală RS485 către {n_inv} invertoare și smart meter; Ethernet / 4G spre SCADA / portal"]})
    return out


def _marker_rs485(mon, k, L=None):
    """marcajul magistralei RS485 la invertorul k (linie de comunicație distinctă, cyan); poziția din listă o dă cablul"""
    if mon.get("rs485") is None:
        return None
    r = mon["rs485"]
    tip_c = r.get("cablu") or "2 × 2 × AWG24 ecranat (LiYCY / FTP)"
    return {"tip": "cutie", "ref": "", "eticheta": "RS485", "legatura": "comunicatie", "w": 14, "h": 6, "spec": [],
            "lista": [f"Cablu de date RS485 {tip_c}, ecranul legat la pământ la un capăt",
                      ("magistrala invertoarelor → SmartLogger (înlănțuire)" if mon.get("smartlogger") is not None
                       else "legătura smart meter ↔ invertor") + (f", l ≈ {fmt_ro(r['L_m'], 0)} m" if r.get("L_m") else "")],
            "buc": 1 if k == 1 else 0}


def tc_smart_meter(rz, mon):
    """raportul TC al smart meter-ului: după curentul de la punctul de racord (In trafo la PT, Σ Iac la TG / OD)"""
    sm = mon.get("smart_meter") or {}
    if sm.get("TC_primar_A"):
        return int(sm["TC_primar_A"])
    tr = rz.get("trafo") or {}
    ib = tr.get("In_T_A") * int(tr.get("n_trafo") or 1) if tr.get("In_T_A") else None
    q = rz.get("Q_TG") or {}
    if ib is None:
        ib = max(float(q.get("In_A") or 0), float((rz.get("sume") or {}).get("Iac_total_A") or 0))
    return prima_tc(ib)


def _ap_smart_meter(rz, mon, mono, n_inv):
    """TC-urile smart meter-ului + SM + SL, ca aparat (pus la punctul de racord)"""
    if mon.get("smart_meter") is None and mon.get("smartlogger") is None:
        return None
    if mon.get("smart_meter") is None:
        return {"tip": "nod", "ref": "", "laterale": _lat_smart(mon, n_inv)}
    p = tc_smart_meter(rz, mon)
    return _ap("tc", "TCS", "tc", {"primar_A": p, "clasa": "0,5", "Sn_VA": 5, "n": 1 if mono else 3}, buc=1 if mono else 3,
               laterale=_lat_smart(mon, n_inv, f"{p}/5 A"))


def _cef_cascada(inp, rz, m, intrari, mono, U, kwp, lim):
    """r12 (proiecte reale V / S, Top 15 #5): CEF cu N tablouri intermediare — fiecare tablou cu invertoarele lui
    (intrările deasupra barei lui), protecția plecării QSk la capătul din tablou, cablul C-TEk și protecția QFk la
    capătul din TEG-ul de interfață comun; în TEG: bara comună, QG cu PI (+ UPS), DDR, TC + contor, SmartLogger;
    C0 → punctul de racord (PT existent / TG existent / PT nou / PCC), cu smart meter-ul la punctul de racord."""
    te = rz.get("tablouri_intermediare") or []
    dupa = {}
    for b in intrari:
        dupa.setdefault(b.get("_obiect"), b)
    ordonate, sect = [], []
    plecari = []
    s = rz.get("sume") or {}
    for z in te:
        grup = [dupa.pop(ob) for ob in z.get("unitati") or [] if ob in dupa]
        if len(rz.get("invertoare") or []) > INVERTOARE_COMPRIMA_PESTE:
            grup = _comprima_idem(grup)
        ordonate += grup
        k = z.get("nr")
        sz = z.get("sume") or {}
        bara = z.get("bara") or {}
        sub = (f"Pi {_f(sz.get('Pn_total_kW'))} kW {PUNCT} U 400 V {PUNCT} Imax {_f(sz.get('Iac_total_A'))} A"
               + (f" {PUNCT} ΔU {_f(bara.get('dU_pct'), 2)} %" if bara.get("dU_pct") is not None else "")
               + f" {PUNCT} {z.get('IP') or 'IP66'}, rezervă 25–30 %")
        sect.append({"n_in": len(grup), "n_out": 1, "titlu": z.get("nume") or f"TE-{k}", "sub": sub})
        q = z.get("Q") or {}
        qs = _prot(q, f"QS{k}", retea="mono" if mono else "tri")
        qf = _prot(q, f"QF{k}", retea="mono" if mono else "tri")
        c = z.get("C")
        cab = _cablu(c, f"C-TE{k}") if c else {"ref": f"C-TE{k}", "cond": "3 + N + PE", "text": "conform proiect"}
        if qf:
            qf["jos"] = True          # r12: QFk la capătul din TEG (desenat în carcasa TEG, deasupra barei comune)
        plecari.append({"aparate": [x for x in (qs, qf) if x], "cablu": cab,
                        "sarcina": {"titlu": "bara TEG", "jonctiune": True}})
    rest = list(dupa.values())
    if rest:
        ordonate += rest
        sect.append({"n_in": len(rest), "n_out": 1, "titlu": "TEG — plecări directe", "sub": "invertoare / PCS pe bara TEG"})
        plecari.append({"aparate": [], "cablu": {"ref": "", "cond": "", "text": ""},
                        "sarcina": {"titlu": "bara TEG", "jonctiune": True}})
    for b in ordonate:
        b.pop("_obiect", None)
        b.pop("_obiecte", None)
    m["intrari"] = ordonate
    spd = _spd_bara()
    m["bara"] = {"afisare": True, "forteaza": True, "laterale": [spd], "eticheta": "", "sectiuni": sect}
    m["plecari"] = plecari
    qg = rz.get("QG") or {}
    apq = []
    qga = _prot(qg, "QG", bd=True)
    if qga:
        qga["param"]["interfata"] = True
        qga["laterale"] = _lat_pi(inp)
        apq.append(qga)
    d = _ddr(qg.get("DDR"), "DDR-G")
    if d:
        apq.append(d)
    masura_mt = (rz.get("masura") or {}).get("loc") == "MT"
    tcp = rz.get("TC_primar_A")
    if tcp and not masura_mt and not mono:
        apq.append(_ap("tc", "TC", "tc", {"primar_A": tcp, "clasa": "0,5S", "Sn_VA": 5, "n": 3}, buc=3,
                       laterale=[{"tip": "contor", "ref": "P1", "eticheta": "kWh",
                                  "param": {"sablon": "contor", "retea": "tri", "masura": "semidirecta", "bidirectional": True}}]))
    extra, dest, pt_copii, tg_copii, cab0 = _racord_cef(rz, mono, U, lim)
    apq += extra
    ap_tab = dest.pop("_aparate_tablou", None)
    jn = {"eticheta": "bara TEG", "aparate": apq, "cablu": cab0, "sarcina": dest, "aparate_tablou": ap_tab or [],
          "carcasa": {"titlu": "TEG — TE INTERFAȚĂ", "sub": f"Pi {_f(kwp)} kWp {PUNCT} U 400 V {PUNCT} Imax "
                                                            f"{_f(s.get('Iac_total_A'))} A {PUNCT} {len(te)} tablouri intermediare"}}
    if pt_copii or tg_copii:
        jn["copii"] = pt_copii or tg_copii
    m["jonctiune"] = jn
    m["carcasa"] = {"titlu": " + ".join(x["titlu"] for x in sect), "sub": ""}
    m["cartus"]["denumire2"] = (f"CEF {_f(kwp)} kWp" if kwp else f"CEF {_f(s.get('Pn_total_kW'))} kW") + \
        f" · {len(te)} tablouri intermediare" + (" + BESS" if rz.get("PCS") else "")
    return "CEF"


def _monitorizare_cef(inp, rz, m, mono):
    """r12: smart meter (TC la punctul de racord), SmartLogger, RS485 la invertoare — adăugate pe modelul CEF construit"""
    mon = monitorizare(inp)
    if not mon:
        return
    n_inv = len(rz.get("invertoare") or [])
    # RS485 la fiecare invertor (lateral de comunicație pe simbolul invertorului)
    k = 0
    for b in m.get("intrari") or []:
        for a in b.get("aparate") or []:
            if a.get("tip") == "invertor":
                k += 1
                mk = _marker_rs485(mon, k)
                if mk:
                    a["laterale"] = list(a.get("laterale") or []) + [mk]
    ap = _ap_smart_meter(rz, mon, mono, n_inv)
    if ap is None:
        return
    # punctul de racord: coloana „sosire” a tabloului existent (PT / TG) sau, altfel, linia QG din TGD-CF / TEG
    tinta = None
    surse = [m.get("jonctiune")] if m.get("jonctiune") else []
    surse += m.get("plecari") or []
    for pl in surse:
        if not isinstance(pl, dict):
            continue
        for ch in pl.get("copii") or []:
            if any(a.get("tip") == "nod" and "sosire" in " ".join(a.get("spec") or []) for a in ch.get("aparate") or []) \
                    or "sosirea trafo" in str((ch.get("sarcina") or {}).get("sub", "")):
                tinta = ch
                break
        if tinta:
            break
    if tinta is None:
        tr = rz.get("trafo") or {}
        rac = rz.get("racord") or {}
        pl0 = (m.get("plecari") or [None])[0] if not m.get("jonctiune") else m["jonctiune"]
        if isinstance(pl0, dict) and not pl0.get("copii") and (rac.get("tg_existent") or tr.get("existent")):
            # tabloul existent nedesenat încă: se desenează cu coloana „sosire” (smart meter-ul la punctul de racord)
            tit = "PCC — rețea OD" if rac.get("tg_existent") else f"T EXISTENT {tr.get('Sn_kVA')} kVA — PCC"
            pl0["copii"] = _tg_existent_pcc([ap], mono, tit, "punctul de racord · smart meter")
            pl0["tablou_existent"] = True
            return
        for pl in surse:
            if isinstance(pl, dict) and pl.get("copii") and (tr.get("existent") or rac.get("tg_existent")):
                # tabloul existent: o coloană nouă „sosire” cu TC-urile smart meter-ului
                sos = {"tip": "nod", "ref": "", "spec": ["sosire existentă"], "laterale": []}
                tit = f"T EXISTENT {tr.get('Sn_kVA')} kVA — PCC" if tr.get("existent") and not rac.get("tg_existent") \
                    else "PCC — rețea OD"
                pl["copii"].append({"aparate": [sos, ap], "cablu": {"ref": "", "cond": "L + N + PE" if mono else "3 + N + PE",
                                                                 "text": "alimentare existentă"},
                                    "sarcina": {"titlu": tit, "sub": "punctul de racord · smart meter"}})
                return
        if m.get("jonctiune"):
            m["jonctiune"]["aparate"].append(ap)
        elif m.get("plecari"):
            m["plecari"][0]["aparate"].append(ap)
        return
    tinta["aparate"].insert(1, ap)


def _tablou_eps(eps, ap, mono):
    """r10 (locuințe #9, #66): tabloul de rezervă (TD-EPS) desenat SEPARAT, legat la portul EPS al invertorului hibrid
    (lateral de forță al invertorului), cu Q-EPS, DDR 30 mA și circuitele lui — nu pe bara TE."""
    inv = next((a for a in ap if a.get("tip") == "invertor"), None) or (ap[-1] if ap else None)
    if inv is None:
        return
    poli = "2P" if eps.get("mono", mono) else "4P"
    circ = eps.get("circuite") or []
    d = eps.get("DDR") or {}
    lista = [f"Tablou de rezervă TD-EPS alimentat din portul EPS / backup al invertorului hibrid ({_f(eps.get('P_kW'))} kW): "
             f"întreruptor Q-EPS {poli} C{eps.get('Q_In_A')} A, cablu Cu {fmt_ro(eps.get('S_mm2'))} mm², "
             f"RCCB {poli} {d.get('In_A')} A 30 mA tip A",
             "circuite: " + "; ".join(f"{c['nume']} MCB {c['curba']}{c['In_A']} A, Cu {fmt_ro(c['S_mm2'])} mm²" for c in circ)
             + " — mutate din TE; N–PE în regim insular conform fișei invertorului"]
    spec = [f"Q-EPS {poli} C{eps.get('Q_In_A')}{NB}A", f"DDR 30{NB}mA A"] + [f"{c['nume']} {c['curba']}{c['In_A']}" for c in circ[:4]]         + ([f"+ {len(circ) - 4} circuite"] if len(circ) > 4 else [])
    cut = {"tip": "cutie", "ref": "TD-EPS", "eticheta": "TD-EPS", "legatura": "forta", "w": 40,
           "spec": ["din portul EPS al INV"] + spec, "lista": lista}
    # nod propriu imediat după invertor (ieșirea EPS), separat de lanțul bateriei și de ieșirea spre rețea
    ap.insert(ap.index(inv) + 1, {"tip": "nod", "ref": "", "spec": [], "laterale": [cut]})


def _marcheaza_existent(intr):
    """r10 (fotovoltaic #43, locuințe #26): invertor / grup EXISTENT — desenat (cu marcajul „E” în locul poziției),
    dar nelistat în materialele noi (aparate și cabluri)."""
    s = intr.setdefault("sursa", {})
    if "EXISTENT" not in str(s.get("titlu", "")):
        s["titlu"] = f"{s.get('titlu', '')} (EXISTENT)".strip()
        s["sub"] = f"existent — nu face obiectul lucrării {PUNCT} " + str(s.get("sub") or "")
    def mark(a):
        a["existent"] = True
        for l in a.get("laterale") or []:
            mark(l)
    for a in intr.get("aparate") or []:
        mark(a)
    for k in ("cablu", "cablu_ca"):
        cab = intr.get(k) or {}
        if cab.get("param"):
            cab["param"] = dict(cab["param"], existent=True)
        if cab.get("text") and "existent" not in cab["text"]:
            cab["text"] = "existent · " + cab["text"]
    return intr


def _tg_existent_pcc(lim, mono, titlu, sub):
    """r7 (P1): tabloul existent în care se racordează CEF / TD-PV, desenat ca tablou secundar: alimentarea lui din rețea
    (punctul de racord) poartă TC-urile, analizorul AR și controller-ul EMS ai limitării injecției — măsoară schimbul
    total cu rețeaua (consum + producție); a doua coloană = plecările existente ale consumatorului."""
    # nodul de sus = intrarea existentă a tabloului (Q general existent, nefurnizat); TC-urile AR/EMS sub el, spre rețea
    sosire = {"tip": "nod", "ref": "", "spec": ["sosire existentă"], "laterale": []}
    return [{"aparate": [sosire] + lim, "cablu": {"ref": "", "cond": "L + N + PE" if mono else "3 + N + PE", "text": "alimentare existentă"},
             "sarcina": {"titlu": titlu, "sub": sub}},
            {"aparate": [], "cablu": {"ref": "", "cond": "", "text": "existente"},
             "sarcina": {"titlu": "Plecări existente", "sub": "consumatori (conform releveu)"}}]


def _nr_obiect(r, implicit):
    """r8: numărul k al invertorului INV-k din rezultatul ramurii (la secții ordinea rezultatelor poate diferi)"""
    mo = re.match(r"INV-(\d+)$", str((r or {}).get("obiect") or ""))
    return int(mo.group(1)) if mo else implicit


def _pi_mt(pt, cat=None):
    """echipa1 P1-9: CEF racordată în MT — întreruptorul de interfață pe MT (QI) cu protecția de interfață 27/59/59N/81
    (59N = deplasarea neutrului, din TT în triunghi deschis) și, de la categoria B RfG, RTU / SCADA (DEN–OD) + PPC"""
    lat = [{"tip": "cutie", "eticheta": "PI MT", "spec": ["27/59/59N", "81 · ROCOF"], "legatura": "comanda",
            "lista": ["Protecție de interfață pe MT: U< (27), U> (59), deplasarea tensiunii homopolare (59N, din TT MT în "
                      "triunghi deschis), f< / f> (81), ROCOF — declanșare pe întreruptorul de interfață QI",
                      "reglaje conform ATR / avizului OD (Ord. ANRE 208/2018, RfG)"]}]
    if cat in ("B", "C", "D"):
        lat.append({"tip": "cutie", "eticheta": "RTU", "spec": ["SCADA DEN / OD", "PPC"], "legatura": "comanda",
                    "lista": [f"Interfață de teleconducere (RTU) cu dispecerul DEN / OD și controlerul centralei (PPC) — "
                              f"categoria {cat} RfG: reglaj P / Q, limitarea puterii la PCC, semnale conform ATR",
                              "conform Ord. ANRE 208/2018 și normei tehnice a OD"]})
    return {"tip": "intreruptor_mt", "ref": "QI", "spec": ["întreruptor de interfață MT", "24 kV · 630 A"],
            "lista": ["Celulă MT 24 kV cu întreruptor în vid 630 A (întreruptor de interfață), TT de linie și TT în "
                      "triunghi deschis (59N), bobină de declanșare", "conform ATR / avizului OD"],
            "laterale": lat}


def _celule_mt_cef(pt, masura_mt):
    """celula de măsură MT (QM, contor de decontare pe MT) și celula de linie (QL cu CLP și descărcătoare) ale PT-ului
    nou al CEF — comune tuturor trafo-urilor postului"""
    ap = []
    if masura_mt:
        ap.append({"tip": "separator", "ref": "QM", "spec": ["celulă de măsură MT", "TT + TC, conform ATR"],
                   "lista": ["Celulă de măsură MT 24 kV cu transformatoare de tensiune 20/√3 / 0,1/√3 kV și de curent, "
                             "cl. 0,5S", "conform ATR / avizului OD"],
                   "laterale": [{"tip": "contor", "ref": "P", "eticheta": "kWh · kVArh", "spec": ["măsură MT", "TT 20/0,1 kV · TC"],
                                 "lista": ["Contor electronic de decontare bidirecțional, măsură indirectă pe MT, cl. 0,5S",
                                           "furnizat și sigilat de OD, conform ATR"]}]})
        ap.insert(0, _pi_mt(pt, pt.get("categorie_RfG")))
    nl = int((pt.get("celule_mt") or {}).get("linie") or 1)
    cl = _ap("sep_mt", "QL", None, {}, spec=[f"24{NB}kV · 630{NB}A", "celulă de linie + CLP" if nl == 1
                                             else f"{nl} × celulă de linie (intrare–ieșire)"],
             lista=["Celulă MT de linie 24 kV, 630 A, separator de sarcină cu cuțit de legare la pământ"
                    + ("" if nl == 1 else " — intrare / ieșire în buclă LES 20 kV")], buc=nl,
             laterale=[{"tip": "descarcator_mt", "ref": "FV", "buc": 3, "spec": ["ZnO 24 kV"],
                        "lista": ["Descărcătoare cu ZnO 24 kV, 10 kA, la trecerea LEA–LES"]}])
    cl["param"] = None
    ap.append(cl)
    return ap


def _bess_calc(inp, rz):
    """r8: datele BESS completate de motor (kWh = n_module × kWh_modul, din cod: LUNA2000-200KWH …, P = n_pcs × PCS)"""
    b = dict(inp.get("bess") or {})
    for k, v in (rz.get("bess_date") or {}).items():
        if v is not None and b.get(k) is None or k in ("kWh", "P_kW") and v is not None:
            b[k] = v
    return b


def _cef_tgd(inp, rz, m, intrari, mono, U, kwp, lim):
    """r11 (fotovoltaic #44): CEF cu 2 tablouri TGD-CF — fiecare cu invertoarele lui (intrările deasupra barei lui),
    QGk → C0.k spre bara JT de racord comună (PT existent: QPT.k în TGJT; TG existent; PT nou: QJT → T1 → celule MT;
    BMPT / OD: PCC), cu TC-urile de decontare și TCA + AR + EMS ale limitării la punctul de racord comun."""
    tg = rz.get("tgd_cf") or []
    dupa = {b.get("_obiect"): b for b in intrari}
    ordonate, n1_in = [], 0
    for k, z in enumerate(tg):
        ordonate += [dupa.pop(ob) for ob in z.get("unitati") or [] if ob in dupa]
        if k == 0:
            n1_in = len(ordonate)
    ordonate += list(dupa.values())
    for b in ordonate:
        b.pop("_obiect", None)
        b.pop("_obiecte", None)
    m["intrari"] = ordonate
    s = rz.get("sume") or {}
    rac = rz.get("racord") or {}
    tr = rz.get("trafo")
    masura_mt = (rz.get("masura") or {}).get("loc") == "MT"
    spd = _spd_bara()
    iac_s = " / ".join(_f((z.get("sume") or {}).get("Iac_total_A")) for z in tg)
    m["bara"] = {"afisare": True, "forteaza": True, "laterale": [spd],
                 "eticheta": " │ ".join(f"TGD-CF{k}" for k in range(1, len(tg) + 1)) + f" {PUNCT} bare Cu 3P + N + PE "
                             f"{PUNCT} Σ Iac {iac_s}{NB}A",
                 "cupla": {"n1": 1, "n1_in": n1_in, "fara_legatura": True,
                           "etichete": [f"TGD-CF{k}" for k in range(1, len(tg) + 1)]}}
    plecari = []
    for k, z in enumerate(tg, 1):
        qg = z.get("QG") or {}
        apq = []
        qga = _prot(qg, f"QG{k}", bd=True)
        if qga:
            qga["laterale"] = [{"tip": "cutie", "eticheta": "PI", "spec": ["U / f"], "legatura": "comanda",
                                "lista": [f"Protecție de interfață (anti-insularizare) cu declanșare pe bobina BD a QG{k} — "
                                          "reglaje conform ATR", "Ord. ANRE 208/2018 (RfG)"]}]
            apq.append(qga)
        d = _ddr(qg.get("DDR"), f"DDR-G{k}")
        if d:
            apq.append(d)
        c0 = z.get("C0")
        cab0 = _cablu(c0, f"C0.{k}") if c0 else {"ref": f"C0.{k}", "cond": "3 + N + PE", "text": "conform ATR / proiect"}
        jos = []
        if z.get("Q_PT"):
            q_ = _prot(z["Q_PT"], f"QPT{k}")
            if q_:
                jos.append(q_)
            tit = f"TGJT EXISTENT — plecarea {k}"
        elif rac.get("tg_existent"):
            tit = f"TG EXISTENT — racord {k}"
        elif tr and not tr.get("existent"):
            tit = f"bara JT PT — racord {k}"
        else:
            tit = f"bara de racord — {k}"
        plecari.append({"aparate": apq, "cablu": cab0,
                        "sarcina": {"titlu": tit, "sub": _sub_ramura(c0) if c0 else ""},
                        "copii": [{"aparate": jos, "cablu": {"ref": "", "cond": "", "text": ""},
                                   "sarcina": {"titlu": "bara", "jonctiune": True}}], "tablou_existent": bool(jos)})
    m["plecari"] = plecari
    ap_j = []
    if rz.get("TC_primar_A") and not masura_mt and not (tr and tr.get("existent")) and not rac.get("tg_existent"):
        ap_j.append(_ap("tc", "TC", "tc", {"primar_A": rz["TC_primar_A"], "clasa": "0,5S", "Sn_VA": 5, "n": 3}, buc=3,
                        laterale=[{"tip": "contor", "ref": "P1", "eticheta": "kWh",
                                   "param": {"sablon": "contor", "retea": "tri", "masura": "semidirecta", "bidirectional": True}}]))
    ap_j += lim
    for a in ap_j:
        _regen(a)
        for l in a.get("laterale") or []:
            _regen(l)
    if tr and not tr.get("existent"):
        pt = rz.get("PT") or {}
        lant = (_ramura_pt_nou(pt, tr) or [{}])[0]
        ap_j += lant.get("aparate") or []
        jc = {"titlu": f"PT {tr.get('Sn_kVA')} kVA", "sub": "post de transformare nou"
              + (" · măsură MT" if masura_mt else "")}
        sar, cab = lant.get("sarcina") or {}, lant.get("cablu") or {}
        et = "bara JT a PT-ului nou"
    elif tr:
        jc = {"titlu": f"PT EXISTENT {tr.get('Sn_kVA')} kVA", "sub": "TGJT existent · punctul de racord"
              + (" · măsură MT existentă" if masura_mt else "")}
        sar = {"titlu": f"T EXISTENT {tr.get('Sn_kVA')} kVA — PCC", "sub": "sosirea trafo · schimbul total cu rețeaua"}
        cab = {"ref": "", "cond": "", "text": "existent"}
        et = "bara JT existentă"
    elif rac.get("tg_existent"):
        jc = {"titlu": "TG EXISTENT", "sub": "bara TG existent · plecările existente conform releveu"}
        sar = {"titlu": "PCC — rețea OD", "sub": "alimentarea TG existent · contor bidirecțional OD"}
        cab = {"ref": "", "cond": "", "text": "alimentare existentă"}
        et = "bara TG existent"
    else:
        jc = None
        sar = {"titlu": "PCC — RED 0,4 kV", "sub": "punct comun de cuplare conform ATR"}
        cab = {"ref": "C1", "cond": "3 + N + PE", "text": "conform ATR"}
        et = "bara de racord"
    m["jonctiune"] = {"eticheta": et, "aparate": ap_j, "cablu": cab, "sarcina": sar}
    if jc:
        m["jonctiune"]["carcasa"] = jc
    m["carcasa"] = {"titlu": " + ".join(f"TGD-CF{k}" for k in range(1, len(tg) + 1)),
                    "sub": f"{len(tg)} tablouri c.a. fotovoltaice separate · Σ Pn = {_f(s.get('Pn_total_kW'))} kW · categoria "
                           f"{rz.get('categorie_RfG', '—')} RfG"}
    m["cartus"]["denumire2"] = (f"CEF {_f(kwp)} kWp" if kwp else f"CEF {_f(s.get('Pn_total_kW'))} kW") + \
        f" · {len(tg)} TGD-CF" + (" + BESS" if rz.get("PCS") else "")
    return "CEF"


def _cef_sectii(inp, rz, m, intrari, mono, U, kwp):
    """r8 (P1, CEF > ~2,2 MW): PT nou cu 2 trafo — TGD-CF cu două secții de bare (câte una pe trafo), cupla QC normal
    deschisă cu interblocaj; pe fiecare secție grupul ei de invertoare / PCS și QGk → C0.k → QJTk → Tk → QTk; celulele
    MT comune (QM, QL) sub ambele celule trafo, pe bara MT a postului → LES 20 kV → PCC MT."""
    sec = rz.get("sectii") or []
    dupa = {}
    for b in intrari:
        dupa.setdefault(b.get("_obiect"), b)
    ordonate, n1_in = [], 0
    for k, z in enumerate(sec):
        for ob in z.get("unitati") or []:
            if ob in dupa:
                ordonate.append(dupa.pop(ob))
        if k == 0:
            n1_in = len(ordonate)
    ordonate += [b for b in intrari if b in dupa.values()]
    if len(rz.get("invertoare") or []) > INVERTOARE_COMPRIMA_PESTE:
        a_, b_ = _comprima_idem(ordonate[:n1_in]), _comprima_idem(ordonate[n1_in:])
        ordonate, n1_in = a_ + b_, len(a_)
    for b in ordonate:
        b.pop("_obiect", None)
        b.pop("_obiecte", None)
    m["intrari"] = ordonate
    pt = rz.get("PT") or {}
    tr = rz.get("trafo") or {}
    sn = tr.get("Sn_kVA")
    ujt = fmt_ro(pt.get("U_JT_kV") or 0.4)
    masura_mt = (rz.get("masura") or {}).get("loc") == "MT"
    s = rz.get("sume") or {}
    spd = _spd_bara()
    conf = "3P + PE" if U > 400 else "3P + N + PE"
    iac_s = " / ".join(_f((z.get("sume") or {}).get("Iac_total_A")) for z in sec)
    m["bara"] = {"afisare": True, "forteaza": True, "laterale": [spd],
                 "eticheta": f"TGD-CF1 (T1) │ TGD-CF2 (T2) {PUNCT} bare Cu {conf}" + (f" {PUNCT} 3 × {U}{NB}V c.a." if U > 400 else "")
                 + f" {PUNCT} Σ Iac {iac_s}{NB}A"}
    qgs = [z.get("QG") or {} for z in sec]
    in_c = max([q.get("In_A") or 0 for q in qgs] + [0])
    tip_c = "acb" if any(q.get("tip") == "ACB" for q in qgs) else "mccb"
    poli_c = "3P" if U > 400 else "4P"
    m["bara"]["cupla"] = {"n1": 1, "n1_in": n1_in, "aparat": {
        "tip": tip_c, "ref": "QC", "spec": [f"{poli_c} {PUNCT} {in_c}{NB}A", "NO · interblocaj"],
        "lista": [f"Întreruptor de cuplă longitudinală a barelor TGD-CF1 / TGD-CF2 {tip_c.upper()} {poli_c}, In {in_c} A, "
                  f"cu acționare motorizată",
                  "normal DESCHIS; interblocaj mecanic + electric cu QJT1 / QJT2 (trafo niciodată în paralel); închis numai "
                  "cu un trafo retras și injecția limitată la Sn (EMS)"]}}
    lim = _aparate_limitare(rz, mono, s.get("Iac_total_A"))
    plecari = []
    for k, z in enumerate(sec, 1):
        qg = z.get("QG") or {}
        apq = []
        qga = _prot(qg, f"QG{k}", bd=True)
        if qga:
            qga["laterale"] = [{"tip": "cutie", "eticheta": "PI", "spec": ["U / f"], "legatura": "comanda",
                                "lista": [f"Protecție de interfață (anti-insularizare) cu declanșare pe bobina BD a QG{k} — "
                                          "reglaje conform ATR", "Ord. ANRE 208/2018 (RfG)"]}]
            apq.append(qga)
        if z.get("TC_primar_A") and not masura_mt:
            apq.append(_ap("tc", f"TC{k}", "tc", {"primar_A": z["TC_primar_A"], "clasa": "0,5S", "Sn_VA": 5, "n": 3}, buc=3,
                           laterale=[{"tip": "contor", "ref": f"P{k}", "eticheta": "kWh",
                                      "param": {"sablon": "contor", "retea": "tri", "masura": "semidirecta", "bidirectional": True}}]))
        if lim and k == 1:
            apq += lim
        elif lim:
            # al doilea set de TC al analizorului AR (măsoară puterea pe ambele secții)
            apq.append(_ap("tc", f"TCA{k}", "tc", {"primar_A": prima_tc((z.get("sume") or {}).get("Iac_total_A")),
                                                    "clasa": "0,5", "Sn_VA": 5, "n": 3}, buc=3))
        c0 = z.get("C0")
        cab0 = _cablu(c0, f"C0.{k}") if c0 else {"ref": f"C0.{k}", "cond": "3 + PE" if U > 400 else "3 + N + PE",
                                                 "text": f"legătura JT T{k} – TGD-CF{k} · conform proiect"}
        sub = f"celula trafo {k} {PUNCT} T{k} {sn} kVA 20/{ujt} kV"
        if c0:
            sub += f" {PUNCT} {_sub_ramura(c0)}"
        plecari.append({"aparate": apq, "cablu": cab0, "sarcina": {"titlu": f"PT — T{k}", "sub": sub},
                        "copii": _ramura_pt_nou(pt, tr, doar=k), "pt": True})
    m["plecari"] = plecari
    m["jonctiune"] = {"eticheta": "bara MT 20 kV", "aparate": _celule_mt_cef(pt, masura_mt),
                      "carcasa": {"titlu": f"PT {len(sec)} × {sn} kVA", "sub": "celule MT comune" + (" · măsură MT" if masura_mt else "")},
                      "cablu": {"ref": "C-MT", "cond": "3 × 1 × 150 mm² Al", "text": "LES 20 kV — conform ATR"},
                      "sarcina": {"titlu": "PCC — rețea MT 20 kV", "sub": "punct de racord MT conform ATR"
                                  + (" · măsură în celula QM" if masura_mt else "")}}
    m["carcasa"] = {"titlu": "TGD-CF", "sub": f"tablou general c.a. fotovoltaic · 2 secții (T1 / T2), cuplă QC normal deschisă · "
                    f"Σ Pn = {_f(s.get('Pn_total_kW'))} kW · categoria {rz.get('categorie_RfG', '—')} RfG"
                    + (f" · 3 × {U} V c.a." if U > 400 else "")}
    if U > 400:
        _u_ca(m["intrari"] + m["plecari"], U)
        spd["param"].update(poli="3P", U_V=U)
    m["cartus"]["denumire2"] = (f"CEF {_f(kwp)} kWp" if kwp else f"CEF {_f(s.get('Pn_total_kW'))} kW") + \
        (" + BESS" if rz.get("PCS") or (rz.get("BESS") or {}).get("cuplaj") == "cc" else "") + f" · PT 2 × {sn} kVA"
    return "CEF"



# ------------------------------------------------------------------------------------------------ r12: PT / PC conform OD
COMP_OD = "COMPARTIMENT OD"
COMP_UT = "COMPARTIMENT UTILIZATOR"


def compartimente_od(d):
    """compartimentele OD / utilizator se desenează când DG-ul cu întreruptor e cerut, OD-ul e declarat, există punct de
    conexiune sau la cerere (`compartimente: true`)"""
    if d.get("compartimente") is False:
        return False
    return bool(d.get("dg") or d.get("OD") or d.get("punct_conexiune") or d.get("compartimente"))


def text_cablu_mt(cmt, u_kv=20):
    """r12 (#11): (conductoare, text) ale cablului MT declarat (`cablu_MT` {tip, S_mm2, material, U0_U_kV, L_m | L,
    tronsoane [{tip, S_mm2, L}]}) — fără secțiune inventată: nedeclarat → „conform ATR”"""
    cmt = cmt if isinstance(cmt, dict) else {}
    tr = [t for t in cmt.get("tronsoane") or [] if isinstance(t, dict)]
    def unu(t):
        S = t.get("S_mm2") or cmt.get("S_mm2")
        mat = t.get("material") or cmt.get("material") or "Al"
        tip = t.get("tip") or cmt.get("tip") or ""
        L = t.get("L_m", t.get("L"))
        return " ".join(x for x in (str(tip), f"3 × 1 × {_f(S, 0)} mm² {mat}" if S else "", f"{_f(L, 0)} m" if L else "") if x)
    if tr:
        return "3 × 1 × … mm²", " + ".join(unu(t) for t in tr) + " — conform ATR"
    S = cmt.get("S_mm2")
    cond = f"3 × 1 × {_f(S, 0)} mm² {cmt.get('material') or 'Al'}" if S else "3 × 1 (MT)"
    L = cmt.get("L_m", cmt.get("L"))
    txt = " ".join(x for x in (str(cmt.get("tip") or f"LES {fmt_ro(u_kv)} kV"),
                               f"{cmt['U0_U_kV']} kV" if cmt.get("U0_U_kV") else "",
                               f"L ≈ {_f(L, 0)} m" if L else "") if x)
    return cond, txt + " — conform ATR"


def _lat_dg():
    return [{"tip": "cutie", "eticheta": "F>", "spec": ["50/51 · 51N", "TC + tor homopolar"], "legatura": "comanda",
             "lista": ["Releu de protecție digital al dispozitivului general (DG) 50/51, 50N/51N, cu TC de protecție și "
                       "tor homopolar (ex. 100/1 A), alimentare auxiliară proprie (UPS / acumulator)",
                       "reglaje conform avizului OD / ATR; declanșare pe bobina YO a întreruptorului"]}]


def celula_racord(umm="24"):
    return {"tip": "separator", "ref": "QR", "spec": [f"{umm}{NB}kV · 630{NB}A", "celulă racord utilizator"],
            "lista": [f"Celulă MT de racord a utilizatorului {umm} kV, 630 A, separator de sarcină cu CLP",
                      "separată de celula de protecție (DG), conform cerințelor OD"]}


def marcaje_od(cl):
    """RGDAT (indicator de defect) și UP (unitate periferică telecomandă) pe celula de linie a OD"""
    cl["laterale"] = list(cl.get("laterale") or []) + [
        {"tip": "cutie", "ref": "", "eticheta": "RGDAT", "legatura": "masura", "w": 20, "spec": ["indicator defect"],
         "lista": ["Indicator de trecere a curentului de defect (RGDAT) pe celula de linie — echipament OD"]},
        {"tip": "cutie", "ref": "", "eticheta": "UP", "legatura": "comunicatie", "w": 16, "spec": ["telecomandă"],
         "lista": ["Unitate periferică (UP) pentru telecomanda celulei de linie, motor 24 V c.c. — echipament OD (SCADA OD)"]}]
    return cl


def punct_conexiune(pc, masura_mt, umm="24", umt="20"):
    """r12 (proiectul real S, Top 15 #9): punctul de conexiune (PC) — tablou MT separat, legat la PT prin LES: celula
    utilizatorului (întreruptor + PI + 50/51/51N + analizor), 2 celule de linie motorizate cu AAR (bucla pe două linii),
    celula de măsură (decontare), celula de servicii proprii cu trafo; compartimentul OD hașurat; marcaj SCADA."""
    pc = pc if isinstance(pc, dict) else {}
    nl = int(pc.get("celule_linie") or 2)
    qu = _ap("intreruptor_mt", "QU", "celula_intreruptor", {"raport": "conform P", "Um_kV": umm})
    qu["spec"] = [f"{umm}{NB}kV · 630{NB}A", "celulă utilizator · DG"]
    qu["laterale"] = _lat_dg() + [{"tip": "cutie", "eticheta": "PI", "spec": ["terminal PI", "27/59/81 · 59N"],
                                   "legatura": "comanda",
                                   "lista": ["Terminal de protecție de interfață pe MT (27, 59, 81<, 81>, 59N) cu declanșare "
                                             "pe întreruptorul celulei utilizatorului", "analizor de calitate cl. A; Ord. ANRE 208/2018"]}]
    qu["param"]["sablon"] = None
    copii = []
    for k in range(1, nl + 1):
        cl = marcaje_od({"tip": "sep_mt", "ref": f"QL{k}", "spec": [f"{umm}{NB}kV · 630{NB}A", "linie · motorizată"],
                         "lista": [f"Celulă MT de linie {umm} kV, 630 A, separator de sarcină motorizat (24 V c.c.) cu CLP",
                                   "echipament OD — buclă pe două linii"], "compartiment": COMP_OD})
        if k == 2 and pc.get("aar", True):
            cl["laterale"].append({"tip": "cutie", "ref": "AAR", "eticheta": "AAR", "legatura": "comanda",
                                   "spec": ["linie 1 ↔ linie 2"],
                                   "lista": ["Automatizare AAR a celulelor de linie (comutarea pe linia de rezervă la lipsa "
                                             "tensiunii), interblocaj — echipament OD"]})
        copii.append({"aparate": [cl], "cablu": {"ref": f"C-L{k}", "cond": "3 × 1 (MT)", "text": "LES / LEA OD — conform ATR"},
                      "sarcina": {"titlu": f"LINIA {k} — {umt} kV", "sub": "rețeaua OD (buclă)"}})
    if masura_mt:
        copii.append({"aparate": [{"tip": "separator", "ref": "QM", "compartiment": COMP_OD,
                                   "spec": ["celulă de măsură", "TT + TC cl. 0,2S"],
                                   "lista": [f"Celulă de măsură MT {umm} kV cu 3 TT și 3 TC (ex. 60/5/5 A) cl. 0,2S",
                                             "conform ATR / avizului OD"],
                                   "laterale": [{"tip": "contor", "ref": "P", "eticheta": "kWh · kVArh", "spec": ["decontare"],
                                                 "lista": ["Contor electronic de decontare bidirecțional pe MT, cl. 0,2S",
                                                           "furnizat și sigilat de OD"]}]}],
                      "cablu": {"ref": "", "cond": "", "text": ""},
                      "sarcina": {"titlu": "MĂSURĂ DECONTARE", "sub": "celula de măsură a PC"}})
    sp = pc.get("servicii_proprii_kVA")
    if sp:
        tsp = {"tip": "trafo", "ref": "TSP", "spec": [f"{_f(sp, 0)} kVA", f"{umt}/0,4 kV"],
               "lista": [f"Transformator de servicii proprii {_f(sp, 0)} kVA, {umt}/0,4 kV, uscat", "în celula de servicii proprii"]}
        qsp = {"tip": "sigurante_mt", "ref": "QSP", "spec": [f"{umm}{NB}kV", "celulă servicii proprii"],
               "lista": [f"Celulă MT de servicii proprii {umm} kV cu separator de sarcină și siguranțe MT"]}
        lat = [{"tip": "cutie", "ref": "SCADA", "eticheta": "SCADA", "legatura": "comunicatie", "spec": ["dulap SCADA"],
                "lista": ["Dulap SCADA / telecomandă PC (RTU, router, UPS), integrat în dispeceratul OD — conform ATR"]}] \
            if pc.get("scada", True) else []
        if lat:
            tsp["laterale"] = lat
        copii.append({"aparate": [qsp, tsp], "cablu": {"ref": "", "cond": "", "text": "0,4 kV"},
                      "sarcina": {"titlu": "SERVICII PROPRII", "sub": "iluminat, prize, SCADA, motoare celule"}})
    return {"aparate_tablou": [qu], "copii": copii}


def _ramura_pt_nou(pt, tr, doar=None):
    """r6 (fotovoltaic P0-2): ramura PT-ului nou al CEF, desenată sub TGD-CF în carcasa postului (tablou secundar al
    plecării C0): Q JT al trafo → T1 20/0,4 kV → celula trafo (separator de sarcină + siguranțe MT / întreruptor +
    releu 50/51) → celula de linie cu CLP și descărcătoare → LES 20 kV → PCC MT. Aceleași simboluri și șabloane ca la
    schema PT (`_pt`). r7: câte o coloană pe fiecare trafo (`n_trafo`: QJTk → Tk → QTk; cupla QC a barelor JT la QJT2),
    celula de măsură MT (QM, contor de decontare pe MT) între celula trafo și celula de linie. Întoarce lista coloanelor."""
    sn = pt.get("Sn_kVA") or tr.get("Sn_kVA")
    n_t = int(pt.get("n_trafo") or 1)
    ujt = pt.get("U_JT_kV") or 0.4
    masura_mt = (pt.get("masura") or {}).get("loc") == "MT"
    out = []
    for k in range(1, n_t + 1):
        if doar is not None and k != doar:
            continue
        suf = "" if n_t == 1 else str(k)
        ap = []
        qj = _prot(pt.get("Q_JT"), f"QJT{suf}")
        if qj:
            if k == 2 and doar is None:
                qjt = pt.get("Q_JT") or {}
                qj["laterale"] = [{"tip": "cutie", "ref": "QC", "eticheta": "QC", "legatura": "grup", "spec": ["cuplă bare JT", "normal închisă"],
                                   "lista": [f"Întreruptor de cuplă longitudinală a barelor JT {qjt.get('tip', '')} {qjt.get('In_A')} A, "
                                             f"normal închis ({' + '.join(f'T{i}' for i in range(1, n_t + 1))})",
                                             "interblocaje conform proiectului PT; la un trafo scos din funcțiune, injecția se limitează"]}]
            ap.append(qj)
        par_t = {"Sn_kVA": sn, "uk_pct": pt.get("uk_pct"), "Pk_W": pt.get("Pk_W")}
        if ujt != 0.4:
            par_t["U_JT_kV"] = ujt
        if pt.get("izolatie") == "uscat":
            par_t["izolatie"] = "uscat"
        ap.append(_ap("trafo", f"T{k}", "trafo", {kk: v for kk, v in par_t.items() if v is not None}, neutru_pamant=True))
        comp = compartimente_od(pt)
        if pt.get("celula_trafo") == "intreruptor":
            a = _ap("intreruptor_mt", f"QT{suf}", "celula_intreruptor", {"raport": "conform Sn"})
            a["laterale"] = _lat_dg() if pt.get("dg") else [
                {"tip": "cutie", "eticheta": "F>", "spec": ["50/51 · 50N/51N"], "legatura": "comanda",
                 "lista": ["Releu de protecție digital 50/51, 50N/51N, cu TC MT (sau senzori) și alimentare proprie"]}]
            ap.append(a)
        else:
            ap.append(_ap("sigurante_mt", f"QT{suf}", "celula_sigurante", {"In_A": norme.TRAFO_SIGURANTA_MT_A.get(int(sn)) if sn else None}))
        if comp:
            ap[-1]["compartiment"] = COMP_UT
            if k == 1 and doar is None:
                # r12: celula de racord a utilizatorului, separată de celula de protecție (DG)
                ap.append(dict(celula_racord(), compartiment=COMP_UT))
        if doar is not None:
            # r8: secția k a CEF cu 2 trafo — celula trafo se leagă pe bara MT comună (joncțiune desenată sub coloane)
            out.append({"aparate": ap, "cablu": {"ref": "", "cond": "", "text": ""},
                        "sarcina": {"titlu": "bara MT", "jonctiune": True}})
            continue
        if k > 1:
            out.append({"aparate": ap, "cablu": {"ref": "", "cond": "", "text": ""},
                        "sarcina": {"titlu": "BARA MT 20 kV", "sub": "a postului — celula de linie QL comună"}})
            continue
        pcx = pt.get("punct_conexiune")
        if masura_mt:
            ap.append(_pi_mt(pt, pt.get("categorie_RfG")))     # echipa1 P1-9: QI (PI MT, 59N) spre centrală, apoi QM
        if masura_mt and not pcx:
            ap.append({"tip": "separator", "ref": "QM", "spec": ["celulă de măsură MT", "TT + TC, conform ATR"],
                       "lista": ["Celulă de măsură MT 24 kV cu transformatoare de tensiune 20/√3 / 0,1/√3 kV și de curent, "
                                 "cl. 0,5S", "conform ATR / avizului OD"],
                       "laterale": [{"tip": "contor", "ref": "P", "eticheta": "kWh · kVArh", "spec": ["măsură MT", "TT 20/0,1 kV · TC"],
                                     "lista": ["Contor electronic de decontare bidirecțional, măsură indirectă pe MT, cl. 0,5S",
                                               "furnizat și sigilat de OD, conform ATR"]}]})
            if comp:
                ap[-1]["compartiment"] = COMP_OD
        nl = int((pt.get("celule_mt") or {}).get("linie") or 1)
        cl = _ap("sep_mt", "QL", None, {}, spec=[f"24{NB}kV · 630{NB}A", "celulă de linie + CLP" if nl == 1
                                                 else f"{nl} × celulă de linie (intrare–ieșire)"],
                 lista=["Celulă MT de linie 24 kV, 630 A, separator de sarcină cu cuțit de legare la pământ"
                        + ("" if nl == 1 else " — intrare / ieșire în buclă LES 20 kV")], buc=nl,
                 laterale=[{"tip": "descarcator_mt", "ref": "FV", "buc": 3, "spec": ["ZnO 24 kV"],
                            "lista": ["Descărcătoare cu ZnO 24 kV, 10 kA, la trecerea LEA–LES"]}])
        cl["param"] = None
        if comp and not pcx:
            cl["compartiment"] = COMP_OD
            marcaje_od(cl)
        elif pcx:
            cl["spec"] = [f"24{NB}kV · 630{NB}A", "celulă de linie spre PC"]
        ap.append(cl)
        cond_mt, txt_mt = text_cablu_mt(pt.get("cablu_MT"))
        if pcx:
            pcd = punct_conexiune(pcx, masura_mt)
            out.append(dict(pcd, aparate=ap, cablu={"ref": "C-MT", "cond": cond_mt, "text": txt_mt},
                            sarcina={"titlu": "PUNCT DE CONEXIUNE (PC)", "sub": "nou · celule MT · AAR · SCADA"
                                     + (" · măsură de decontare" if masura_mt else "")}))
            continue
        out.append({"aparate": ap, "cablu": {"ref": "C-MT", "cond": cond_mt, "text": txt_mt},
                    "sarcina": {"titlu": "PCC — rețea MT 20 kV", "sub": "punct de racord MT conform ATR"
                                + (" · măsură în celula QM" if masura_mt else "")}})
    return out


def _port_baterie(inp, rz, mono, obiect=None, k=None):
    """v1.9 (R5 L27): portul de baterie al invertorului hibrid — lateral de forță c.c. din invertor: protecția /
    separatorul de c.c. al bateriei (FB) → bateria (BAT, cu BMS). Bateria NU stă în serie pe linia c.c. PV → invertor.
    r6: la CEF (`obiect` = INV-k) protecția și capacitatea sunt pe fiecare invertor hibrid (FBk / BATk)."""
    bz = rz.get("BESS") or {}
    b = inp.get("bess") if isinstance(inp.get("bess"), dict) else inp.get("baterie") if isinstance(inp.get("baterie"), dict) else {}
    pc = bz.get("protectie_cc") or {}
    if obiect is not None:
        pc = pc.get(obiect) or {}
    In, U = pc.get("In_A"), pc.get("U_V")
    sf = str(k) if k else ""
    fb = {"tip": "cutie", "ref": f"FB{sf}", "eticheta": "FB · c.c.", "legatura": "forta", "w": 24,
          "spec": [f"{_f(In, 0)} A c.c." if In else "conform fișei", "separ. + sig."],
          "lista": ["Separator-siguranță c.c. pe portul de baterie (+ și −)" + (f", {_f(In, 0)} A, {_f(U, 0)} V c.c." if In else ""),
                    "între baterie și invertorul hibrid (sau integrat în rack-ul BMS, conform fișei)"]}
    kwh = (bz.get("kWh_port") if obiect is not None else None) or bz.get("kWh") or b.get("kWh") or inp.get("baterie_kWh")
    par = dict(_fisa(b, FISA_BATERIE), sablon="baterie", kWh=kwh)
    lat = max([len(x) for x in text_desen("baterie", {kk: v for kk, v in par.items() if kk != "sablon"})] + [12])
    bat = {"tip": "cutie", "ref": f"BAT{sf}", "eticheta": "BAT", "legatura": "forta", "w": max(26, round(1.45 * lat + 5)),
           "param": par}
    if kwh is None and not _fisa(b, FISA_BATERIE):
        bat.pop("param")
        bat["spec"] = ["c.c. · BMS"]
        bat["lista"] = ["Baterie cuplată în c.c. la invertorul hibrid, cu BMS (capacitate conform fișei)"]
    return [fb, bat]


def _prosumator(inp, rz, m):
    mono = inp.get("retea") == "mono"
    invs = rz.get("invertoare") or ([rz["INV"]] if rz.get("INV") else [])
    grupuri = [g for g in inp.get("invertoare") or [] if isinstance(g, dict)]
    inv_f = inp.get("invertor") if isinstance(inp.get("invertor"), dict) else {}
    if grupuri:
        gl = [g for g in grupuri for _ in range(int(g.get("n", 1)))]
    else:
        gl = [dict(inv_f, Pn_kW=inp.get("Pn_inv_kW") or inv_f.get("Pn_kW"), hibrid=inp.get("hibrid") or inv_f.get("hibrid"))]
    unic = len(invs) == 1
    bz = rz.get("BESS") or {}
    st = inp.get("string") if isinstance(inp.get("string"), dict) else {}
    cc = {x: rz.get(x) for x in ("SPD_cc_Ucpv_V", "gPV_In_A", "Voc_Tmin_V", "gPV_generic", "string_generic")}
    n_mppt = int(st.get("n_MPPT") or 1)
    kwp = inp.get("kWp")
    intrari = []
    la = bz.get("la")
    la_l = la if isinstance(la, list) else [la] if la else []
    for i, r in enumerate(invs):
        k = i + 1
        g = gl[i] if i < len(gl) else {}
        port = None
        if bz.get("cuplaj") == "cc" and r.get("obiect") in la_l:
            # r7 (P1): bateria pe fiecare invertor hibrid pe care e repartizată (FBk / BATk), nu „doar pe primul”
            port = _port_baterie(inp, rz, mono) if len(la_l) == 1 else \
                _port_baterie(inp, rz, mono, obiect=r.get("obiect"), k=k)
        kwp_i = (kwp * float(g.get("Pn_kW") or 0) / max(1e-9, sum(float(x.get("Pn_kW") or 0) for x in gl))) if kwp else None
        ap = _lant_pv(inp, rz, r, g, cc, _refs(k, unic), kwp_i, n_mppt, st, _modul(inp), "Ord. ANRE 228/2018", mono, port)
        intrari.append({"sursa": {"titlu": "CÂMP PV" if unic else f"CÂMP PV {k}",
                                  "sub": f"invertor {'hibrid ' if port else ''}{_f(g.get('Pn_kW'))} kW"
                                  + (f" {PUNCT} {r['faza']}" if r.get("faza") else "")},
                        "cablu": {"ref": "", "cond": "c.c.", "text": "H1Z2Z2-K"}, "cablu_ca": _cablu(r), "aparate": ap})
        if g.get("existent") is True:
            _marcheaza_existent(intrari[-1])
        if (rz.get("EPS") or {}).get("la") == r.get("obiect"):
            _tablou_eps(rz["EPS"], ap, mono)
    pcs = rz.get("PCS")
    if pcs:
        b = _bess_calc(inp, rz)
        ap = _lant_bess(b, pcs, b.get("kWh"), pcs.get("Pn_kW") or b.get("P_kW"), mono)
        if _ems_marker(rz):
            ap[-1]["laterale"] = [_ems_marker(rz)]        # comanda EMS → PCS
        n = _nod_ca(pcs, "FB.3", mono)
        if n:
            ap.append(n)
        q = _prot(pcs.get("protectie"), "QB", retea="mono" if mono else "tri")
        if q:
            ap.append(q)
        d = _ddr(pcs.get("DDR"), "DDR-B")
        if d:
            ap.append(d)
        intrari.append({"sursa": {"titlu": "BESS", "sub": f"{_f(pcs.get('Pn_kW'))} kW / {_f(b.get('kWh'))} kWh · cuplaj c.a."},
                        "cablu": {"ref": "", "cond": "c.c.", "text": ""}, "cablu_ca": _cablu(pcs), "aparate": ap})
    m["intrari"] = intrari
    spd = {"tip": "spd", "ref": "F1", "param": {"sablon": "spd_ca", "tip": "T2", "poli": "2P" if mono else "4P", "In_amonte_A": 40}}
    spd_l = [spd] if rz.get("protectii_ca", True) is not False else []        # Î5: protecții c.a. declarate „nu”
    s = rz.get("sume") or {}
    pn = s.get("Pn_invertoare_kW") or inp.get("Pn_inv_kW")
    qb = inp.get("In_Q_bransament_A")
    racord = inp.get("racord")
    lim = _aparate_limitare(rz, mono, rz.get("Iac_max_A"))
    qg = rz.get("QG")
    if qg:
        # prosumator comercial: TD-PV cu QG (și PI externă pe bobina BD) pe o plecare a tabloului existent
        m["bara"] = {"afisare": True, "forteaza": True, "laterale": spd_l,
                     "eticheta": f"Bare Cu {PUNCT} {'L + N + PE' if mono else '3P + N + PE'} {PUNCT} "
                                 + (f"I max fază = {_f(rz.get('Iac_max_A'))}{NB}A" if rz.get("faze") else f"Σ Iac = {_f(rz.get('Iac_max_A'))}{NB}A")}
        qga = _prot(qg, "QG", bd=bool(rz.get("PI_externa")), poli=qg.get("poli"), retea="mono" if mono else "tri")
        apq = []
        if qga:
            if rz.get("PI_externa"):
                qga["laterale"] = [{"tip": "cutie", "eticheta": "PI", "spec": ["U / f"], "legatura": "comanda",
                                    "lista": ["Protecție de interfață externă (anti-insularizare, U/f, ROCOF) cu declanșare pe bobina BD a QG",
                                              "certificată, reglaje conform ATR (Ord. ANRE 228/2018)"]}]
            apq.append(qga)
        qt = rz.get("Q_TG") or {}
        tit = {"tg_existent": "TG EXISTENT", "bmpt": "BMPT EXISTENT", "pt": "PT EXISTENT"}.get(
            racord, "TG EXISTENT" if rz.get("comercial") else "TE EXISTENT")
        sub = (f"racord prin {qt.get('tip', '')} {qt.get('In_A')}{NB}A (existent) {PUNCT} " if qt.get("In_A") else
               "plecări consumator existente " + PUNCT + " ") + "contor bidirecțional OD la punctul de racord"
        c0 = rz.get("C0")
        cab0 = _cablu(c0, "C0") if c0 else {"ref": "C0", "cond": "L + N + PE" if mono else "3 + N + PE", "text": "conform releveu"}
        m["plecari"] = [{"aparate": apq, "cablu": cab0, "sarcina": {"titlu": tit, "sub": sub}}]
        if lim:
            # r7 (P1): limitarea injecției măsoară la punctul de racord — TC + AR + EMS pe alimentarea tabloului existent
            # (consum + producție), nu pe plecarea TD-PV
            m["plecari"][0]["tablou_existent"] = True
            m["plecari"][0]["copii"] = _tg_existent_pcc(
                lim, mono, {"bmpt": "BMPT / branșament OD", "pt": "PT existent (bara JT)"}.get(racord, "Branșament / PCC"),
                "punctul de racord · contor bidirecțional OD")
        m["carcasa"] = {"titlu": "TD-PV", "sub": f"tablou distribuție fotovoltaic · prosumator {_f(pn)} kW · PI {'externă' if rz.get('PI_externa') else 'integrată'}"}
    else:
        m["bara"] = {"afisare": True, "forteaza": True, "eticheta": ("TG consumator · bare existente" if rz.get("comercial")
                                                                     else "TE consumator · bare existente"), "laterale": [spd]}
        tit = {"tg_existent": "TG existent", "bmpt": "BMPT existent", "pt": "PT existent"}.get(racord, "Branșament existent")
        m["plecari"] = [{"aparate": lim, "cablu": {"ref": "", "cond": "L + N + PE" if mono else "3 + N + PE", "text": "existent"},
                         "sarcina": {"titlu": tit, "sub": (f"Q {qb}{NB}A {PUNCT} " if qb else "") + "contor bidirecțional (OD)"}}]
        if not rz.get("comercial"):
            # circuitele consumatorului (generic, cerut de OD): pe aceeași bară a TE
            for k, cg in enumerate(_te_generic(mono, qb, str(inp.get("schema_pamant") or "").upper() == "TT")[0]["copii"]):
                cg["aparate"][0]["ref"] = f"Q{k + 2}"
                cg["sarcina"]["sub"] = "existent / generic"
                m["plecari"].append(cg)
        else:
            m["plecari"].append({"aparate": [], "cablu": {"ref": "", "cond": "", "text": "existente"},
                                 "sarcina": {"titlu": "Plecări existente", "sub": "consumatori existenți (conform releveu)"}})
        m["carcasa"] = {"titlu": "TG" if rz.get("comercial") else "TE",
                        "sub": "tablou general existent · prosumator" if rz.get("comercial") else "tablou electric consumator · prosumator"}
    m["cartus"]["denumire2"] = f"PROSUMATOR {_f(pn)} kW {'MONOFAZAT' if mono else 'TRIFAZAT'}" + (" + BESS" if pcs else "")
    _monitorizare_prosumator(inp, rz, m, mono)
    return "prosumator"


def _monitorizare_prosumator(inp, rz, m, mono):
    """r12 (proiectul real P): contorul de producție separat (BMPM / BMPT „măsură energie produsă”) pe linia
    invertorului, înaintea tabloului consumatorului; smart meter-ul la punctul de racord (direct, ≤ 100 A) cu
    legătura RS485 la invertor"""
    mon = monitorizare(inp)
    if not mon:
        return
    k = 0
    for b in m.get("intrari") or []:
        ap = b.get("aparate") or []
        i_inv = next((i for i, a in enumerate(ap) if a.get("tip") == "invertor"), None)
        if i_inv is None:
            continue
        k += 1
        mk = _marker_rs485(mon, k)
        if mk and mon.get("smart_meter") is not None:
            ap[i_inv]["laterale"] = list(ap[i_inv].get("laterale") or []) + [mk]
        if "contor_productie" in mon:
            cp = mon["contor_productie"]
            j = i_inv + 1
            while j < len(ap) and ap[j].get("tip") == "nod":
                j += 1
            poz = "BMPM" if mono else "BMPT"
            ap.insert(j, {"tip": "contor_direct", "ref": f"PP{k if k > 1 else ''}", "in_carcasa": False,
                          "spec": ["kWh producție", f"{poz} · {'1 × 230 V' if mono else '3 × 230/400 V'}"],
                          "lista": [f"Contor de energie PRODUSĂ (măsură directă, {'monofazat' if mono else 'trifazat'}, "
                                    f"{cp.get('In_A', 5)}(60) A, cl. 1 / B) în {poz} „măsură energie produsă”"
                                    + (f" — {cp['model']}" if cp.get("model") else ""),
                                    "cu siguranță / întreruptor de separare și DDR 300 mA în blocul de măsură, "
                                    "montat între invertor și tabloul consumatorului (cerință OD / ATR)"]})
    sm = mon.get("smart_meter")
    if sm is not None and m.get("plecari"):
        mod = sm.get("model")
        lat = {"tip": "cutie", "ref": "SM", "eticheta": "kWh · kVArh", "legatura": "masura",
               "spec": [str(mod)[:16] if mod else "smart meter", "RS485 → INV"],
               "lista": [f"Smart meter {'monofazat' if mono else 'trifazat'} cu măsură directă (≤ 100 A)"
                         + (f" — {mod}" if mod else "") + ", Modbus RS485",
                         "la intrarea tabloului consumatorului (punctul de racord), cu siguranță 6 A pe circuitul "
                         "de tensiune; date către invertor (limitarea injecției / monitorizare)"]}
        m["plecari"][0]["aparate"] = [{"tip": "nod", "ref": "", "spec": ["sosire"], "laterale": [lat]}] + \
            list(m["plecari"][0].get("aparate") or [])


def _din_fise(intrare):
    """copie a intrării cu cheile de calcul completate din fișe (Pn invertor) — pentru texte și titluri.
    r7: la CEF, Pn-ul grupurilor declarate doar prin model (SG250HX …) se ia din catalog, ca în motor."""
    if intrare.get("tip_schema") in ("cef", "bess", "prosumator") and any(isinstance(g, dict) and g.get("Pn_kW") is None
                                                              for g in intrare.get("invertoare") or []):
        from .calc import catalog_invertoare as cat_inv
        d = copy.deepcopy(intrare)
        for g in d["invertoare"]:
            if isinstance(g, dict) and g.get("Pn_kW") is None:
                mc = cat_inv.cauta(g.get("producator"), g.get("model")) or {}
                if mc.get("Pn_kW"):
                    g["Pn_kW"] = mc["Pn_kW"]
        return d
    if intrare.get("tip_schema") != "prosumator" or not isinstance(intrare.get("invertor"), dict):
        return intrare
    d = copy.deepcopy(intrare)
    inv = d["invertor"]
    if d.get("Pn_inv_kW") is None and inv.get("Pn_kW") is not None:
        d["Pn_inv_kW"] = inv["Pn_kW"]
    return d


def _modele_prosumator(inp, rz, m):
    """v1.9: modelele din fișe se pun direct în `_prosumator` (ramurile comune cu CEF, `_lant_pv`) — păstrat pentru
    compatibilitate (nu mai modifică modelul)."""
    return None


def _ge(inp, rz, m):
    """GE + ATS (SPEC §C.6): două intrări DISTINCTE în ATS — I: rețea (QR → C1), II: GE (QG → C2) —, cei doi poli ai
    comutatorului interblocați mecanic + electric (sursele nu pot fi niciodată în paralel), ieșirea ATS → C3 → consumatori"""
    if rz.get("mod") == "ge_izolat":
        return _ge_izolat(inp, rz, m)
    if rz.get("mod") == "tg_normal_vital":
        return _tg_normal_vital(inp, rz, m)
    if rz.get("mod") == "ats_trafo":
        return _ats_trafo(inp, rz, m)
    qg, qr, ats = rz.get("Q_G") or {}, rz.get("Q_retea") or {}, rz.get("ATS") or {}
    c1, c2, c3 = rz.get("C1") or {}, rz.get("C2") or {}, rz.get("C3") or {}
    sn = inp.get("Sn_GE_kVA")
    p_ats = {"In_A": ats.get("In_A")}
    manual = ats.get("comutare") == "manual"
    sab, et_k = ("inversor", "K") if manual else ("ats", "ATS")
    pol = lambda poz, buc: dict(_ap("separator", f"{et_k}·{poz}", sab, p_ats, interblocaj="I-0-II" if manual else "ATS", buc=buc))
    ap_r = []
    p = _prot((c1.get("protectie") or dict(qr, tip=qr.get("tip", "MCCB"))), "QR")
    if p:
        p["in_carcasa"] = False
        ap_r.append(p)
    if rz.get("plecare_retea"):
        # r9 (#24): consumatorii normali — plecare QN din bara rețelei, ÎNAINTEA ATS (nu sunt alimentați din GE)
        pn = rz["plecare_retea"]
        qn = pn.get("protectie") or {}
        nume_n = ", ".join(f"{c['nume']} {_f(c['P_kW'])} kW" for c in rz.get("consumatori_retea") or [])
        txt_q = f"{qn.get('tip', '')} {qn.get('In_A', '')}{NB}A".strip()
        nod = {"tip": "nod", "ref": "", "spec": [], "in_carcasa": False, "laterale": [
            {"tip": "cutie", "ref": "QN", "eticheta": "NORMALI", "legatura": "forta", "w": 34,
             "spec": [f"doar rețea · {_f(rz.get('P_retea_normali_kW'))} kW", txt_q],
             "lista": [f"Plecare consumatori normali din bara rețelei (înaintea ATS, nu se alimentează din GE): {nume_n}",
                       f"protecție {txt_q}, cablu {_cablu(pn).get('text', '')}; DDR conform tabloului consumatorilor"]}]}
        ap_r.insert(0, nod)
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
    if qg.get("RCM") and p:
        # r6: circuite de siguranță pe GE — fără DDR-G; monitorizare diferențială (doar alarmă)
        p["laterale"] = [{"tip": "cutie", "ref": "", "eticheta": "RCM", "spec": ["IΔn 300 mA", "doar alarmă"],
                          "legatura": "masura",
                          "lista": ["Dispozitiv de monitorizare a curentului diferențial (RCM) cu tor, IΔn 300 mA, "
                                    "contact de alarmă — NU declanșează (circuite de siguranță)", "SR EN 62020"]}]
    den, car = text_lista(sab, p_ats)   # al doilea pol al ATS: același aparat → aceeași poziție în listă, fără text dublat
    ap_g.append({"tip": "separator", "ref": f"{et_k}·II", "spec": [], "lista": [den, car],
                 "interblocaj": "I-0-II" if manual else "ATS", "buc": 0})
    sr = rz.get("sursa_retea")
    src_r = ({"pt": "PT propriu" + (f" {inp['pt_Sn_kVA']} kVA" if inp.get("pt_Sn_kVA") else "") + " — bara JT",
              "tgd": "TGD existent", "bmpt": "RED 0,4 kV prin BMPT"}.get(sr) or "RED 0,4 kV (sursa nedeclarată — PRESUPUS BMPT)")
    m["intrari"] = [{"sursa": {"titlu": "REȚEA", "sub": f"{src_r} · alimentare normală (poziția I)"},
                     "cablu": {"ref": "", "cond": "3 + N + PE", "text": "existent"}, "cablu_ca": _cablu(c1, "C1"), "aparate": ap_r},
                    {"sursa": {"titlu": "GRUP ELECTROGEN", "sub": f"{sn} kVA {PUNCT} In_G = {_f(rz.get('In_G_A'))}{NB}A (poziția II)"},
                     "cablu": {"ref": "", "cond": "", "text": ""}, "cablu_ca": _cablu(c2, "C2"), "aparate": ap_g}]
    m["bara"] = {"afisare": True, "eticheta": f"Ieșire {'comutator I-0-II' if manual else 'ATS'} {PUNCT} bare 3P + N + PE "
                                              f"{PUNCT} {ats.get('In_A', '')}{NB}A"}
    sig = rz.get("plecari_siguranta") or []
    m["plecari"] = []
    if c3.get("QC3"):
        # r6: cu circuite de siguranță, consumatorii normali au plecare proprie cu DDR 300 mA S
        # r9: pe bara ATS sunt doar consumatorii vitali (cei normali sunt pe ramura rețea, înaintea ATS)
        from .calc.scheme import e_consumator_siguranta
        n_ret = {c.get("nume") for c in rz.get("consumatori_retea") or []}
        vit = [c.get("nume") for c in (inp.get("consumatori") or []) if isinstance(c, dict)
               and not e_consumator_siguranta(c) and c.get("nume") and c.get("nume") not in n_ret]
        et3 = ("Consumatori vitali" + (f" ({', '.join(vit[:3])}{'…' if len(vit) > 3 else ''})" if vit else "")
               if rz.get("consumatori_retea") else "Consumatori normali")
        pl = _plecare(dict(c3, nume=et3), "QC3", None)
        pl["cablu"] = _cablu(c3, "C3")
        pl["sarcina"]["sub"] = _sub_ramura(c3) + f" {PUNCT} DDR 300{NB}mA S"
        m["plecari"].append(pl)
    elif c3:
        m["plecari"].append({"aparate": [], "cablu": _cablu(c3, "C3"),
                             "sarcina": {"titlu": "Consumatori", "sub": f"P = {_f(inp.get('P_sarcina_kW'))}{NB}kW {PUNCT} {_sub_ramura(c3)}"}})
    for i, r in enumerate(sig, 1):
        m["plecari"].append(_plecare(dict(r, siguranta=True, rezistent_foc=True), f"QS{i}", None))
    m["carcasa"] = {"titlu": "TAR", "sub": "tablou de anclanșare automată a rezervei (ATS 4P, comută și N)"}
    if manual:
        m["carcasa"] = {"titlu": "TCS", "sub": "tablou de comutare MANUALĂ a sursei (comutator I-0-II 4P, comută și N)"}
    from .calc.scheme import tablou_de_siguranta
    if tablou_de_siguranta(inp) or rz.get("siguranta_tot"):
        # r7 (#31): tabloul întreg e de siguranță (pompe de incendiu): titlul o spune
        m["carcasa"] = {"titlu": "TPI", "sub": "tablou pompe de incendiu · alimentare rețea + GE prin "
                                              + ("comutator I-0-II 4P" if manual else "ATS 4P") + " · fără DDR · cabluri rezistente la foc"}
        for intr in m["intrari"]:
            cab = intr.get("cablu_ca") or {}
            if cab.get("text") and "FE180" not in cab["text"]:
                # cablurile de alimentare ale tabloului de siguranță (rețea → ATS, GE → ATS): rezistente la foc E90
                cab["text"] = fe180(cab["text"])
                cab.setdefault("param", {})["rezistent_foc"] = True
        m["cartus"]["denumire2"] = f"TABLOU POMPE DE INCENDIU — REȚEA + GRUP ELECTROGEN {sn} kVA + ATS"
    m["lista_pe"] = ["Neutrul GE legat la priza de pământ locală (TN-S), Rp ≤ 4 Ω",
                     ("comutatorul I-0-II 4P" if manual else "ATS 4P") + ": comută și conductorul N"]
    if sig:
        m["lista_pe"].append("Circuite de siguranță (I7/2011, P118-3): fără DDR, cabluri rezistente la foc E90 pe trasee "
                             "separate, alimentarea normală racordată înaintea întreruptorului general al clădirii; "
                             "legături echipotențiale suplimentare la pompe")
    if rz.get("ge_paralel_nesuportat"):
        m["intrari"][1]["sursa"]["sub"] += " · ATENȚIE: paralel cu rețeaua NESUPORTAT — desen de comutare ATS"
    if not (tablou_de_siguranta(inp) or rz.get("siguranta_tot")):
        m["cartus"]["denumire2"] = f"GRUP ELECTROGEN {sn} kVA + " + ("COMUTATOR MANUAL I-0-II" if manual else "ATS")
    return "grup electrogen + ATS"



def _tg_normal_vital(inp, rz, m):
    """r11: TG cu bara NORMALĂ (rețea: C1 → Q1, consumatori nevitali) și bara VITALĂ (ATS: I = QV din bara normală,
    II = GE → QG → C2), desenate ca două secții de bare; legătura dintre ele (QV + ATS·I) stă în „U” sub bare."""
    t = rz.get("tablou_intrare") or {}
    sn = inp.get("Sn_GE_kVA")
    _tablou(t, rz, m, titlu=inp.get("titlu_tablou") or "TG")
    ats = rz.get("ATS") or {}
    manual = ats.get("comutare") == "manual"
    sab, et_k = ("inversor", "K") if manual else ("ats", "ATS")
    p_ats = {"In_A": ats.get("In_A")}
    # plecările: normalele rămân pe secția 1; plecarea „Bara vitală (ATS)” devine legătura QV → ATS·I, copiii ei = secția 2
    normale, vitale, qv = [], [], None
    for pl in m["plecari"]:
        if pl["sarcina"].get("titlu") == "Bara vitală (ATS)":
            qv = pl
            vitale = pl.get("copii") or []
        else:
            normale.append(pl)
    if qv is None:
        return "tablou cu bară normală și bară vitală"
    for i, pl in enumerate(vitale, 1):
        # referințele bării vitale: QVk (nu sub-referințe ale plecării QV)
        ref0 = None
        for a in pl.get("aparate") or []:
            r0 = str(a.get("ref") or "")
            if ref0 is None and r0.startswith("Q"):
                ref0 = r0
            mo = re.match(r"^([A-Z]+)(\d+)\.(\d+)(.*)$", r0)
            if mo:
                a["ref"] = f"{mo.group(1)}V{mo.group(3)}{mo.group(4)}"
    leg = []
    for a in qv.get("aparate") or []:
        a = dict(a)
        if str(a.get("ref", "")).startswith("Q"):
            a["ref"] = "QV"
        leg.append(a)
    den, car = text_lista(sab, p_ats)
    leg.append({"tip": "separator", "ref": f"{et_k}·I",
                "spec": [f"4P {PUNCT} {ats.get('In_A')}{NB}A", "poz. I · interblocat cu II"],
                "lista": [den, car]})
    m["plecari"] = normale + vitale
    m["bara"]["forteaza"] = True
    m["bara"]["cupla"] = {"n1": len(normale), "aparate": leg,
                          "etichete": ["BARA NORMALĂ (doar rețea)", "BARA VITALĂ (rețea + GE prin ATS)"]}
    m["bara"]["eticheta"] = m["bara"]["eticheta"].replace("Bare Cu", "Bara normală + bara vitală · bare Cu", 1)
    # intrarea II: GE → QG (+ DDR-G / RCM) → C2 → ATS·II, deasupra barei vitale
    qg, c2 = rz.get("Q_G") or {}, rz.get("C2") or {}
    ap_g = [_ap("generator", "G", "ge", {"Sn_kVA": sn, "In_G_A": rz.get("In_G_A")}, in_carcasa=False, neutru_pamant=True)]
    p = _prot((c2.get("protectie") or dict(qg, tip=qg.get("tip", "MCCB"))), "QG")
    if p:
        p["in_carcasa"] = False
        if qg.get("RCM"):
            p["laterale"] = [{"tip": "cutie", "ref": "", "eticheta": "RCM", "spec": ["IΔn 300 mA", "doar alarmă"],
                              "legatura": "masura",
                              "lista": ["Dispozitiv de monitorizare a curentului diferențial (RCM) cu tor, IΔn 300 mA, "
                                        "contact de alarmă — NU declanșează (circuite de siguranță)", "SR EN 62020"]}]
        ap_g.append(p)
    d = _ddr(qg.get("DDR"), "DDR-G")
    if d:
        d["in_carcasa"] = False
        ap_g.append(d)
    ap_g.append({"tip": "separator", "ref": f"{et_k}·II", "spec": ["poz. II · interblocat cu I"], "lista": [den, car],
                 "buc": 0})
    m["intrari"][0]["sursa"]["titlu"] = "REȚEA"
    m["intrari"].append({"sursa": {"titlu": "GRUP ELECTROGEN", "sub": f"{sn} kVA {PUNCT} In_G = {_f(rz.get('In_G_A'))}{NB}A "
                                                                    f"{PUNCT} bara vitală (poziția II)"},
                         "cablu": {"ref": "", "cond": "", "text": ""}, "cablu_ca": _cablu(c2, "C2"), "aparate": ap_g})
    m["carcasa"]["sub"] = (f"bară normală (rețea) + bară vitală (rețea + GE {sn} kVA prin "
                           + ("comutator I-0-II" if manual else "ATS 4P") + f") {PUNCT} " + m["carcasa"].get("sub", ""))
    m["lista_pe"] = ["Bară PE și bară N comune în TG · neutrul GE legat la priza de pământ locală (TN-S), Rp ≤ 4 Ω",
                     ("comutatorul I-0-II 4P" if manual else "ATS 4P") + ": comută și conductorul N"]
    if any(pl.get("siguranta") for pl in vitale):
        m["lista_pe"].append("Circuite de siguranță pe bara vitală (I7/2011, P118-3): fără DDR, cabluri rezistente la foc "
                             "E90, legături echipotențiale suplimentare la pompe")
    m["cartus"]["denumire2"] = (f"{inp.get('titlu_tablou') or 'TABLOU GENERAL'} — BARĂ NORMALĂ + BARĂ VITALĂ, "
                                f"GRUP ELECTROGEN {sn} kVA + " + ("COMUTATOR MANUAL I-0-II" if manual else "ATS")).upper()
    return "tablou cu bară normală și bară vitală"


def _ge_izolat(inp, rz, m):
    """r10 (industrial i43): GE sursă unică (site izolat) — GE → Q_G (+ bloc diferențial) → C1 → bara TG → plecările
    reale; fără ramură de rețea și fără ATS (nimic inventat)."""
    sn = inp.get("Sn_GE_kVA")
    _tablou(dict(inp, origine="_ge"), rz, m, titlu=inp.get("titlu_tablou") or "TG")
    intr = m["intrari"][0]
    ap = [_ap("generator", "G", "ge", {"Sn_kVA": sn, "In_G_A": rz.get("In_G_A")}, in_carcasa=False, neutru_pamant=True)]
    for a in intr.get("aparate") or []:
        a = dict(a, in_carcasa=False)
        if a.get("ref") == "Q1":
            a["ref"] = "QG"
        elif a.get("ref") == "DDR1":
            a["ref"] = "DDR-G"
        ap.append(a)
    if (rz.get("Q_G") or {}).get("RCM"):
        for a in ap:
            if a.get("ref") == "QG":
                a["laterale"] = [{"tip": "cutie", "ref": "", "eticheta": "RCM", "spec": ["IΔn 300 mA", "doar alarmă"],
                                  "legatura": "masura", "lista": ["Dispozitiv de monitorizare a curentului diferențial "
                                                                  "(RCM) cu tor, IΔn 300 mA, contact de alarmă — NU "
                                                                  "declanșează (circuite de siguranță)", "SR EN 62020"]}]
    intr["aparate"] = ap
    intr["cablu_ca"] = intr.get("cablu") or {}         # C1 (GE → TG) după QG, ca la schema GE + ATS
    intr["cablu"] = {"ref": "", "cond": "", "text": ""}
    intr["sursa"] = {"titlu": "GRUP ELECTROGEN", "sub": f"{sn} kVA {PUNCT} In_G = {_f(rz.get('In_G_A'))}{NB}A {PUNCT} "
                                                       f"sursă unică — site izolat, fără rețea {PUNCT} TN-S"}
    m["carcasa"]["sub"] = m["carcasa"]["sub"].replace("tablou general de distribuție JT",
                                                      "tablou general alimentat din GE (fără rețea)", 1)
    m["lista_pe"] = ["Neutrul GE legat la priza de pământ locală (TN-S), Rp ≤ 4 Ω; bară PE și bară N separate în TG",
                     "regim GE: Ik1 ≈ In_G — protecția la contact indirect prin blocul diferențial 300 mA S de pe QG"
                     if not (rz.get("Q_G") or {}).get("RCM") else
                     "circuite de siguranță fără DDR: RCM cu alarmă pe QG, legături echipotențiale suplimentare"]
    m["cartus"]["denumire2"] = f"TABLOU GENERAL ALIMENTAT DIN GRUP ELECTROGEN {sn} kVA (SITE IZOLAT, FĂRĂ REȚEA)"
    return "grup electrogen izolat"


def _ats_trafo(inp, rz, m):
    """r10 (industrial i47): ATS între două transformatoare identice — intrarea I: T1 → QT1 → C1, intrarea II: T2 → QT2
    → C2, polii ATS interblocați (trafo niciodată în paralel), bara TG cu plecările reale; fără GE."""
    sn = rz.get("Sn_T_kVA") or inp.get("pt_Sn_kVA")
    ats = rz.get("ATS") or {}
    _tablou(dict(inp, origine="pt_propriu", pt_Sn_kVA=sn), rz, m, titlu=inp.get("titlu_tablou") or "TG")
    i1 = m["intrari"][0]
    p_ats = {"In_A": ats.get("In_A")}
    pol = lambda poz, buc: dict(_ap("separator", f"ATS·{poz}", "ats", p_ats, interblocaj="ATS", buc=buc))
    ap1 = []
    for a in i1.get("aparate") or []:
        a = dict(a, in_carcasa=False)
        if a.get("ref") == "Q1":
            a["ref"] = "QT1"
        ap1.append(a)
    ap2 = [dict(copy.deepcopy(a), ref=("QT2" if a.get("ref") == "QT1" else a.get("ref")), buc=1) for a in ap1]
    den, car = text_lista("ats", p_ats)
    ap1.append(pol("I", 1))
    ap2.append({"tip": "separator", "ref": "ATS·II", "spec": [], "lista": [den, car], "interblocaj": "ATS", "buc": 0})
    c1 = copy.deepcopy(i1.get("cablu") or {})
    c2 = copy.deepcopy(c1)
    if c1.get("ref"):
        c2["ref"] = "C2"
    tr = lambda k: {"titlu": f"T{k} {sn} kVA", "sub": f"PT propriu {PUNCT} bara JT T{k} {PUNCT} "
                                                     + ("normal (poziția I)" if k == 1 else "rezervă 100 % (poziția II)")}
    m["intrari"] = [{"sursa": tr(1), "cablu": c1, "aparate": ap1}, {"sursa": tr(2), "cablu": c2, "aparate": ap2}]
    m["bara"]["eticheta"] = f"Ieșire ATS {PUNCT} " + m["bara"]["eticheta"]
    m["carcasa"]["sub"] = m["carcasa"]["sub"].replace("tablou general de distribuție JT",
                                                      "tablou general cu ATS între T1 și T2 (rezervă 100 %)", 1)
    m["lista_pe"] = ["Bară PE și bară N în TG · neutrele T1 și T2 la priza de pământ comună a PT (TN-S)",
                     "ATS 4P: comută și N; T1 și T2 niciodată în paralel (interblocaj mecanic + electric)"]
    m["cartus"]["denumire2"] = f"TABLOU GENERAL CU ATS ÎNTRE DOUĂ TRANSFORMATOARE {sn} kVA (REZERVĂ 100 %)"
    return "ATS între două transformatoare"


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
            q = _ap("rcbo", "QB", "rcbo", {"In_A": Q["In_A"], "IdN_mA": 300, "tip_ddr": al.get("DDR_bransament_tip") or "A"}, in_carcasa=False)
        elif Q.get("tip") == "MCB":
            q = _ap("mcb", "QB", "mcb", {"In_A": Q["In_A"], "curba": Q.get("curba", "C"), "poli": "4P", "Icn_kA": Q.get("Icn_kA", 6),
                                         **_backup_sf(Q.get("Icn_kA", 6), col.get("Ik3max_origine_kA"), SF)}, in_carcasa=False)
        else:
            q = _ap("mccb", "QB", "mccb", {"In_A": Q["In_A"], "Ir_A": Q.get("Ir_A"), "poli": "4P", "Icu_kA": Q.get("Icu_kA") or 25}, in_carcasa=False)
        br.append(q)
    if rc.get("In_A"):
        par = {"In_A": rc["In_A"], "poli": f"{rc.get('poli', 4)}P" if str(rc.get("poli", 4)).isdigit() else rc.get("poli"),
               "IdN_mA": rc.get("IdN_mA", 300), "tip_ddr": al.get("DDR_bransament_tip") or rc.get("tip", "A")}
        for k in ("selectiv", "aparat", "asociat"):
            if rc.get(k) is not None:
                par[k] = rc[k]
        br.append(_ap("rccb", "RCCB", "rccb", par, in_carcasa=False))
    if not nou:
        # echipa1 P1-10: blocul de măsură EXISTENT (SF, contor, Q, RCCB ale OD) e desenat, dar nu se cumpără — marcat „E”,
        # în afara listei de echipamente noi și a devizului (fără patroane de rezervă)
        for a_ in br:
            a_["existent"] = True
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
    ger = rz.get("ge_rezerva")
    if ger:
        # r7 (#54): GE de rezervă = SURSĂ (intrarea II), nu consumator — comutator de sursă I-0-II după Q general
        man = ger["comutare"] == "manual"
        den = (f"Comutator de sursă {'manual I-0-II (inversor)' if man else 'automat ATS'} {ger['poli']}, "
               f"{ger['comutator_In_A']} A, comută și N")
        car = "interblocaj mecanic (+ electric la ATS) — rețea și GE niciodată în paralel; SR EN 60947-3" + ("" if man else " / -6-1")
        kr = "K" if man else "ATS"        # r10 (locuințe #40): ATS declarat → desenat și etichetat ATS
        p_ats = {"tip": "separator", "ref": f"{kr}·I", "sablon": "inversor" if man else "ats", "spec": [f"{ger['poli']} {PUNCT} {ger['comutator_In_A']}{NB}A",
                                                              "inversor I-0-II" if man else "ATS"],
                 "lista": [den, car], "interblocaj": kr}
        ap.append(p_ats)
        m["intrari"].append({"sursa": {"titlu": "GRUP ELECTROGEN", "sub": f"{fmt_ro(ger['Sn_kVA'])} kVA {PUNCT} rezervă {PUNCT} "
                                                                           f"In_G = {_f(ger['In_G_A'])}{NB}A"},
                             "cablu": {"ref": "", "cond": "", "text": ""},
                             "cablu_ca": {"ref": "C-GE", "cond": "L + N + PE" if mono else "3 + N + PE",
                                          "text": "cablu GE — conform fișei GE"},
                             "aparate": [_ap("generator", "G", "ge", {"Sn_kVA": ger["Sn_kVA"], "In_G_A": ger["In_G_A"]},
                                             in_carcasa=False, neutru_pamant=False),
                                         {"tip": "mcb", "ref": "Q-GE", "spec": [f"{'2P' if mono else '4P'} {PUNCT} C{ger['Q_GE_In_A']}{NB}A"],
                                          "lista": [f"Întreruptor automat {'2P' if mono else '4P'} C{ger['Q_GE_In_A']} A — "
                                                    f"protecția cablului GE", "SR EN 60898-1"]},
                                         {"tip": "separator", "ref": f"{kr}·II", "spec": [], "lista": [den, car],
                                          "interblocaj": kr, "buc": 0}]})
    S_pe = max(10, col.get("S_PE_mm2") or 0) if col else 16
    ra = inp.get("RA_ohm")
    if tt:
        m["lista_pe"] = [f"Bară PE și bară N în TE · bornă principală de împământare (BPI) · conductor PE FY {fmt_ro(S_pe, 0)} mm² Cu spre priza de pământ",
                         "priză de pământ proprie (TT): electrozi OL-Zn + platbandă OL-Zn 40×4 mm · RA·IΔn ≤ 50 V · BEP baie legată la BPI"]
        m["rp"] = (f"RA = {fmt_ro(ra, 0)} Ω · RA·IΔn ≤ 50 V" if ra else "RA·IΔn ≤ 50 V")
    else:
        m["lista_pe"] = [f"Bară PE și bară N în TE (separate) · bornă principală de împământare (BPI) · conductor PE FY {fmt_ro(S_pe, 0)} mm² Cu",
                         f"PE din coloana C2 legat la BN din {bloc} · priză de pământ locală (repetată) "
                         + (f"RA = {fmt_ro(ra, 0)} Ω (declarat)" + (" > 4 Ω cerut — de îmbunătățit" if ra > 4 else " ≤ 4 Ω")
                            if ra is not None else "Rp ≤ 4 Ω") + " · BEP baie legată la BPI"]
        # r10 (locuințe #51): RA declarat pe planșă (nu „Rp ≤ 4 Ω” fix)
        m["rp"] = (f"RA = {fmt_ro(ra, 0)} Ω " + ("> 4 Ω — de îmbunătățit" if ra > 4 else "≤ 4 Ω")) if ra is not None else "Rp ≤ 4 Ω"
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
        td = c.get("tablou_secundar")
        if td and td.get("plecari"):
            # r6: tablou secundar (atelier / garaj) alimentat din TE — desenat cu circuitele lui, în carcasa proprie
            out["sarcina"] = {"titlu": td["nume"], "sub": f"tablou secundar {PUNCT} " + out["sarcina"]["sub"]}
            out["copii"] = [_plecare(r, f"{ref}.{i + 1}", None) for i, r in enumerate(_ierarhie(td["plecari"]))]
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
                if (g["DDR"].get("tip") or "A") != "B":
                    # r6 (N34, L42): DDR tip A pe VE → RDC-DD 6 mA c.c. în stația de încărcare, desenat explicit
                    for cp in copii:
                        cp["rdc_dd"] = True
                        cp["sarcina"]["sub"] = f"RDC-DD 6{NB}mA c.c. în stație {PUNCT} " + cp["sarcina"]["sub"]
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


def ramuri_model(model):
    """r12: ramurile de nivel 1 ale modelului — intrări, plecări și joncțiunea (bara comună: TEG-ul cascadelor CEF,
    bara MT a PT-ului cu 2 trafo), parcurse la fel de toți cei care citesc modelul (texte, materiale, validare)"""
    jn = model.get("jonctiune")
    return (model.get("intrari") or []) + (model.get("plecari") or []) + ([jn] if isinstance(jn, dict) else [])


def regenereaza_texte(model):
    """SPEC §E.1: spec / lista se regenerează din `param` pentru fiecare aparat și auxiliar generat"""
    def br(b):
        for a in (b.get("aparate") or []) + (b.get("aparate_tablou") or []):
            _regen(a)
            for l in a.get("laterale") or []:
                _regen(l)
        for c in b.get("copii") or []:
            br(c)
    for b in ramuri_model(model):
        br(b)
    for l in (model.get("bara") or {}).get("laterale") or []:
        _regen(l)
    cup = (model.get("bara") or {}).get("cupla")
    if isinstance(cup, dict):
        br({"aparate": cup.get("aparate") or ([cup["aparat"]] if cup.get("aparat") else [])})
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
            if not (par and par.get("S_faza_mm2") and par.get("L_m")) or par.get("existent"):
                continue
            for par in (par.get("tronsoane") or [par]):        # r12: C0 din tronsoane — fiecare tip de cablu
                n = int(par.get("n_paralel") or 1) * int(par.get("buc_circuite") or 1) * int(par.get("cabluri_yd") or 1)
                metri = math.ceil(par["L_m"] * n * 1.05)
                # doar cablul de fază (conductorul PE separat e rând propriu); același text ca pe planșă, fără „n × (…)”
                txt = text_cablu(par.get("material"), par.get("izolatie"), par.get("metoda"), 1, par.get("S_faza_mm2"),
                                 par.get("S_N_mm2"), par.get("S_PE_mm2"), par.get("PE") or "cablu", par.get("retea", "tri"),
                                 fara_N=bool(par.get("fara_N")))
                txt = txt.split(" + FY")[0]
                if par.get("rezistent_foc"):
                    txt = fe180(txt)
                ref = cab.get("ref") or ref_implicit
                npar = int(par.get("n_paralel") or 1)
                mono_r = par.get("retea") == "mono"
                if par.get("monopolar") or str(par.get("metoda") or "").startswith("F"):
                    # cabluri MONOPOLARE (treflă pe pat de cabluri): lungimea se socotește pe conductor
                    izo = txt.split()[0]
                    S, SN = par.get("S_faza_mm2"), par.get("S_N_mm2") or par.get("S_faza_mm2")
                    nf = 1 if mono_r else 3
                    if par.get("fara_N"):          # r7: 800 V c.a. — numai cele 3 faze
                        adauga(f"Cablu monopolar {izo} 1×{fmt_ro(S)} mm² {par.get('material')}", "0,6/1 kV (1,8/3 kV pentru 800 V c.a. conform fișei), "
                               "3 faze, fără N, în treflă; nr. de sisteme în paralel conform planșei", ref, math.ceil(par["L_m"] * npar * 3 * 1.05))
                    elif SN == S:
                        adauga(f"Cablu monopolar {izo} 1×{fmt_ro(S)} mm² {par.get('material')}", "0,6/1 kV, faze + N, în treflă; nr. de sisteme în paralel conform planșei",
                               ref, math.ceil(par["L_m"] * npar * (nf + 1) * 1.05))
                    else:
                        adauga(f"Cablu monopolar {izo} 1×{fmt_ro(S)} mm² {par.get('material')}", "0,6/1 kV, faze, în treflă; nr. de sisteme în paralel conform planșei",
                               ref, math.ceil(par["L_m"] * npar * nf * 1.05))
                        adauga(f"Cablu monopolar {izo} 1×{fmt_ro(SN)} mm² {par.get('material')}", "0,6/1 kV, neutru; nr. de sisteme în paralel conform planșei",
                               ref, math.ceil(par["L_m"] * npar * 1.05))
                else:
                    adauga(f"Cablu {txt} {par.get('material')}" + (f" — {npar} cabluri în paralel pe circuit" if npar > 1 else ""),
                           "0,6/1 kV, conform secțiunilor de pe planșă" + (" — motor stea-triunghi: 2 cabluri pe motor (U1V1W1 + W2U2V2)"
                                                                             if par.get("cabluri_yd") else ""), ref, metri)
                if par.get("PE") == "separat" and par.get("S_PE_mm2"):
                    adauga(f"Conductor de protecție FY 1×{fmt_ro(par['S_PE_mm2'])} mm² Cu, galben-verde", "pozat lângă cablul de fază", ref, metri)
        for i, c in enumerate(b.get("copii") or []):
            br(c, ((c.get("sarcina") or {}).get("titlu") if b.get("grup") else None) or f"{ref_implicit}.{i + 1}")
    for i, b in enumerate(model.get("intrari") or []):
        br(b, f"C{i + 1}" if len(model.get("intrari") or []) > 1 else "C1")
    for i, b in enumerate(model.get("plecari") or []):
        br(b, (b.get("sarcina") or {}).get("titlu") or f"P{i + 1}")
    if isinstance(model.get("jonctiune"), dict):
        br(model["jonctiune"], (model["jonctiune"].get("cablu") or {}).get("ref") or "C0")     # r12: C0 al TEG-ului
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


def _doar_generic(b):
    """toate aparatele din subarbore sunt generice / existente (nimic de furnizat în acest proiect)"""
    ap = []
    def w(x):
        ap.extend(a for a in x.get("aparate") or [] if a.get("tip") != "nod")
        for c in x.get("copii") or []:
            w(c)
    for c in b.get("copii") or []:
        w(c)
    return bool(ap) and all(a.get("generic") or a.get("existent") for a in ap)


def materiale_aparataj(model, inp, rz):
    """articolele care nu apar ca simbol pe planșă, dar se cumpără (SPEC §E.1 pct. 5, completare v1.3):
    patroanele fuzibile ale separatoarelor, sistemul de bare, carcasa tabloului, accesoriile de cablu și
    materialele prizei de pământ calculate. Rândurile au U.M. „buc” / „set” / „m”."""
    out = []
    pat = {}
    def br(b):
        for a in b.get("aparate") or []:
            par = a.get("param") or {}
            if a.get("existent") or a.get("generic"):
                continue
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
    for b in ramuri_model(model):
        br(b)
    rdc = []
    def br_rdc(b):
        if b.get("rdc_dd"):
            rdc.append((b.get("sarcina") or {}).get("titlu", "VE"))
        for c in b.get("copii") or []:
            br_rdc(c)
    for b in model.get("plecari") or []:
        br_rdc(b)
    if rdc:
        out.append({"ref": "RDC-DD", "lista": ["Dispozitiv de detecție a curentului diferențial continuu RDC-DD 6 mA c.c. "
                                               "(integrat în stația de încărcare VE)",
                                               "SR EN 62955 / SR HD 60364-7-722 art. 722.531.3.101; cu DDR 30 mA tip A în TE — "
                                               + ", ".join(rdc)],
                    "cantitate": len(rdc), "um": "buc"})
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
    elif tip == "cef" or (tip == "prosumator" and rz.get("QG")):
        qg = rz.get("QG") or {}
        In_b = (qg.get("protectie") or qg).get("In_A")
        if In_b is None and rz.get("sectii"):
            # r8: TGD-CF cu 2 secții — bara fiecărei secții ≥ In QGk (se cere pe cea mai mare)
            In_b = max([(z.get("QG") or {}).get("In_A") or 0 for z in rz["sectii"]]) or None
    elif tip == "ge_ats":
        In_b = (rz.get("ATS") or {}).get("In_A") or ((rz.get("Q1_C1") or {}).get("protectie") or {}).get("In_A")
        ik = (rz.get("bara_TG") or {}).get("Ik3max_kA")
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
        conf_b = "L + N + PE" if mono else ("3P + PE (800 V c.a.)" if (rz.get("U_ca_V") or 400) > 400 else "3P + N + PE")
        out.append({"ref": car.get("titlu", ""), "lista": [f"Sistem de bare Cu {conf_b}, In ≥ {In_b}{NB}A",
                    (f"Icw ≥ {fmt_ro(ik, 1)} kA / 1 s, " if ik else "") + "suporți izolatori, SR EN 61439-1/-2"], "cantitate": 1, "um": "set", "tip": "aux"})
    if car and (tip in ("tablou", "cef", "ge_ats") or (tip == "prosumator" and rz.get("QG"))):
        out.append({"ref": car.get("titlu", ""), "lista": [f"Carcasă tablou {car.get('titlu', '')}, metalică, IP54, IK08, uși cu cheie",
                    "plăci de montaj, șine DIN, borne, etichete, schemă în buzunar; SR EN 61439-2"], "cantitate": 1, "um": "buc", "tip": "aux"})
    elif car and tip == "pt" and inp.get("pt_aerian") and int(inp.get("n_trafo") or 1) == 1:
        # r8 (#21): PTA pe stâlp — fără anvelopă și celule de interior
        out.append({"ref": "PTA", "lista": ["Stâlp de beton centrifugat pentru PTA, cu console pentru separator, siguranțe MT, "
                                            "descărcătoare și platformă de trafo", "conform proiect de specialitate / "
                                            "fișe tehnologice OD"], "cantitate": 1, "um": "buc", "tip": "aux"})
        out.append({"ref": car.get("titlu", ""), "lista": ["Cutie de distribuție JT (TDJT) de exterior, poliester armat cu "
                                                           "fibră de sticlă, IP54, IK10, montaj la baza stâlpului",
                                                           "SR EN 61439-5; bare, aparataj și borne conform planșei"],
                    "cantitate": 1, "um": "buc", "tip": "aux"})
    elif car and tip == "pt":
        out.append({"ref": car.get("titlu", ""), "lista": ["Anvelopă post de transformare (beton sau metalică), cu fundație, ventilație și iluminat",
                    "dimensionată pentru celule MT + trafo + TGJT, conform proiect de specialitate"], "cantitate": 1, "um": "buc", "tip": "aux"})
    def sec(b):        # tablouri secundare (plecări cu circuite în cascadă): carcasă + bare proprii
        if b.get("copii") and b.get("grup"):      # grupă DDR în același tablou: fără carcasă proprie
            for c in b["copii"]:
                sec(c)
        elif b.get("copii") and b.get("pt"):
            # r6: PT nou al CEF desenat ca tablou secundar al plecării C0 — anvelopa postului, nu carcasă de tablou
            t = (b.get("sarcina") or {}).get("titlu") or "PT"
            if model.get("jonctiune"):
                t = (model["jonctiune"].get("carcasa") or {}).get("titlu") or t     # r8: un singur post cu 2 trafo
            if not any(o.get("ref") == t and str(o["lista"][0]).startswith("Anvelopă") for o in out):
                out.append({"ref": t, "lista": ["Anvelopă post de transformare (beton sau metalică), cu fundație, ventilație și iluminat",
                        "dimensionată pentru celule MT + trafo + bară JT, conform proiect de specialitate"], "cantitate": 1, "um": "buc", "tip": "aux"})
            # r7: la n trafo bara JT poartă Σ In Q JT (QJT1, QJT2 …); la 800 V fără N
            qjs = [(a.get("param") or {}).get("In_A") for c in b["copii"] for a in c.get("aparate") or []
                   if str(a.get("ref") or "").startswith("QJT") and (a.get("param") or {}).get("In_A")]
            qj = sum(qjs) if qjs else None
            if qj:
                conf_pt = "3P + PE (800 V c.a.)" if (rz.get("U_ca_V") or 400) > 400 else "3P + N + PE"
                out.append({"ref": t, "lista": [f"Sistem de bare Cu {conf_pt} (bara JT a PT), In ≥ {qj}{NB}A"
                                                + (f", cu cuplă longitudinală ({len(qjs)} secții)" if len(qjs) > 1 else ""), "SR EN 61439"],
                            "cantitate": 1, "um": "set", "tip": "aux"})
        elif b.get("copii") and b.get("tablou_existent"):
            pass        # r7: tabloul existent (TG / branșament) desenat doar pentru punctul de racord — nu se furnizează
        elif b.get("copii") and _doar_generic(b):
            pass        # echipa1 P1-10: tabloul consumatorului GENERIC / existent — se furnizează prin proiectul IU
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
    elif str(inp.get("separare_PEN") or "").upper() in ("TG", "TABLOU") and spl != "TT":
        spl_t = "TN-C-S cu separarea PEN în TG (TN-S în aval). Rp ≤ 4 Ω"
    elif inp.get("tip_schema") == "cef" and inp.get("pt_od"):
        spl_t = f"{spl} — rețeaua OD din PT-ul OD (punctul de racord pe bara JT a postului OD). Rp ≤ 4 Ω"
    elif inp.get("tip_schema") in ("pt",) or (inp.get("tip_schema") == "cef" and inp.get("pt_Sn_kVA")):
        spl_t = "TN-S din PT propriu. Rp ≤ 1 Ω, conform calcul"
    else:
        spl_t = "TN-S în aval de separarea PEN. Rp ≤ 4 Ω"
    atr = f" nr. {cartus.get('atr')}" if cartus.get("atr") else ""
    tip = inp.get("tip_schema")
    pt_exist = tip == "cef" and inp.get("pt_Sn_kVA") and (inp.get("pt_existent") or inp.get("racord") == "tg_existent")
    if tip == "cef" and inp.get("pt_od"):
        exclus = f"postul de transformare al OD și bara lui JT (amonte de punctul de racord), conform ATR{atr}; "
    elif pt_exist:
        exclus = f"PT-ul propriu existent și {'TG-ul existent' if inp.get('racord') == 'tg_existent' else 'bara JT a PT'} (amonte de punctul de racord), conform ATR{atr}; "
    elif tip == "pt" or (tip == "cef" and inp.get("pt_Sn_kVA")):
        exclus = f"racordul MT al OD conform ATR{atr}; legătura trafo–TGJT (conform furnizorului postului); "
    elif tip == "ge_ats" and inp.get("fara_retea"):
        exclus = "fundația și instalațiile auxiliare ale GE (combustibil, evacuare gaze); "
    elif tip == "ge_ats" and str(inp.get("sursa_rezerva") or "").lower() in ("trafo", "pt", "t2", "transformator"):
        exclus = "postul de transformare cu T1 și T2 (amonte de QT1 / QT2); "
    elif tip == "ge_ats":
        exclus = f"alimentarea existentă din amonte de QR; "
    elif tip == "tablou" and inp.get("origine") == "pt_propriu":
        exclus = "postul de transformare (amonte de C1); "
    elif tip == "prosumator":
        exclus = (f"tabloul general existent, branșamentul și contorul OD{atr and ' (ATR' + atr + ')'}; "
                  if inp.get("racord") == "tg_existent" else f"branșamentul existent și contorul OD{atr and ' (ATR' + atr + ')'}; ")
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


def atestate_necesare(intrare, rz):
    """echipa1 P1-5: atestatele ANRE cerute de tipul lucrării — (firmă, persoană, descriere lucrare).
    PT 20/0,4 kV și CEF cu PT propriu (racord MT): firmă C2A (LES / PT ≤ 20 kV; C1A la PTA aerian), persoană gr. IV A;
    instalații de joasă tensiune (locuință, branșament, tablouri, GE, CEF / prosumator în JT): firmă B / Bp, persoană
    gr. III A (proiectare)."""
    tip = (intrare or {}).get("tip_schema")
    tr = (rz or {}).get("trafo") or {}
    mt = tip == "pt" or (tip == "cef" and tr and not tr.get("existent"))
    if mt:
        aer = bool((intrare or {}).get("pt_aerian"))
        return ("C1A" if aer else "C2A", "gr. IV A", "post de transformare / racord MT ≤ 20 kV")
    return ("B / Bp", "gr. III A", "instalație electrică de joasă tensiune (≤ 1 kV)")


def _atestat_cartus(m, intrare, r):
    firma, pers, lucr = atestate_necesare(intrare, r.get("rezultat"))
    k = m.setdefault("cartus", {})
    k["atestat_necesar"] = f"necesar: firmă {firma} · persoană {pers}"
    dec = str(k.get("atestat_tip") or "").strip()
    if not dec:
        return
    d = dec.upper().replace(" ", "")
    ok = any(x in d for x in ("C2A", "C1A", "D1", "D2", "E1", "E2")) if firma in ("C2A", "C1A") else \
        any(x in d for x in ("B", "C1A", "C2A", "D", "E"))
    if not ok:
        from .calc.verificari import mesaj, remediere
        par = {"declarat": dec, "lucrare": lucr, "necesar": f"atestat de firmă {firma} și atestat de persoană {pers}"}
        r.setdefault("verificari", []).append({"cod": "V58", "nivel": "AVERTISMENT", "obiect": "cartuș",
                                               "mesaj": mesaj("V58", "", **par), "remediere": remediere("V58", **par)})


def genereaza(intrare, cartus=None, format_="A3", pastreaza=None):
    """intrare fizică → (model grafic, rezultat calcul). `pastreaza` = model vechi din care se păstrează cartușul și setările planșei."""
    if isinstance(intrare, dict) and intrare.get("tip_schema") == "bess":
        intrare = dict(intrare, tip_schema="cef")       # v1.9: BESS de sine stătător = CEF fără invertoare PV
    if isinstance(intrare, dict):
        # r10 (fotovoltaic #46): eticheta modelului = doar codul („SG50CX. Racordarea se” → „SG50CX”)
        from .calc.catalog_invertoare import curata_modele
        intrare = copy.deepcopy(intrare)
        curata_modele(intrare)
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
            intr_c = intrare
            if tip == "cef" and intrare.get("tablouri_intermediare") is not None or intrare.get("n_tgd_cf"):
                from .calc.scheme import normalizeaza_cascada
                intr_c = normalizeaza_cascada(copy.deepcopy(intrare))   # r12: tablouri intermediare (ca în calcul)
            intr_c = _din_fise(intr_c)
            CONSTRUCTORI[tip](intr_c, rz, m)
            if tip == "prosumator":
                _modele_prosumator(intr_c, rz, m)
            if tip == "cef" and rz.get("retea") != "mono":
                _monitorizare_cef(intr_c, rz, m, False)
            tp = tabel_pi(intr_c, tip)
            if tp:
                m["tabel_pi"] = tp
        except Exception as e:      # nu blocăm aplicația: schema rămâne goală, validatorul raportează
            m.update({"intrari": [], "plecari": [], "bara": {"afisare": False}})
            r.setdefault("verificari", []).append({"cod": "V00", "nivel": "BLOCANT", "obiect": "schema",
                                                    "mesaj": f"schema nu a putut fi desenată din rezultat ({e.__class__.__name__}: {e})",
                                                    "remediere": "verificați datele de intrare"})
            r["blocheaza_export"] = True
    else:
        m.update({"intrari": [], "plecari": [], "bara": {"afisare": False}, "carcasa": None})
    _verifica_model_r8(m, r)
    _atestat_cartus(m, intrare if isinstance(intrare, dict) else {}, r)
    from .calc.verificari import completeaza_remedieri
    completeaza_remedieri(r.get("verificari"))         # r10: orice BLOCANT are remediere (→ întrebare în interpretor)
    from .calc.umanizare import umanizeaza_verificari
    umanizeaza_verificari(r.get("verificari"))         # echipa1 (ux 5): fără chei JSON / constante de cod în texte
    if isinstance(r.get("presupus"), list):
        from .calc.umanizare import umanizeaza
        r["presupus"] = [umanizeaza(x) if isinstance(x, str) else x for x in r["presupus"]]
    conf = list((pastreaza or {}).get("confirmari") or [])
    if conf:
        m["confirmari"] = conf
        for v in r.get("verificari") or []:          # avertismentele analizate de proiectant: marcate, scoase din nota de pe planșă
            if v.get("nivel") == "AVERTISMENT" and cheie_confirmare(v) in conf:
                v["confirmat"] = True
    m["note"] = _note(intrare, r, m["cartus"], conf)
    bl = [v for v in r.get("verificari") or [] if v.get("nivel") == "BLOCANT"]
    if bl:
        # r7 (S10): planșa unui calcul blocat NU arată „finală” — ștampilă roșie pe planșă + prima notă cu erorile
        cod = []
        for v in bl:
            t = f"{v['cod']} ({v.get('obiect', '')})"
            if t not in cod:
                cod.append(t)
        txt = ", ".join(cod[:5]) + (f" și încă {len(cod) - 5}" if len(cod) > 5 else "")
        m["blocaj"] = f"NEVERIFICAT — CALCUL BLOCAT: {txt}"
        m["note"] = [f"0. ATENȚIE: planșa NU se folosește la execuție / avizare — verificări BLOCANTE nerezolvate: {txt} "
                     f"(detalii și remedieri în memoriul de calcul)."] + m["note"]
    pr = rz.get("priza") or {}
    if pr.get("Rp_ohm") is not None:          # textul de sub priza de pământ = valoarea calculată
        m["rp"] = f"Rp = {fmt_ro(pr['Rp_ohm'], 2)} Ω {'≤' if pr.get('ok') else '>'} {fmt_ro(pr.get('R_limita_ohm'), 2)} Ω"
    m["materiale"] = materiale_cabluri(m)
    if m.get("intrari") or m.get("plecari"):
        m["materiale"] += materiale_aparataj(m, intrare, rz)
    regenereaza_texte(m)
    m["calc_rezumat"] = rezumat(r)
    if intrare.get("tip_schema") in ("cef", "prosumator") and intrare.get("grupare_invertoare") is not False:
        # E2 (#13): invertoarele identice („tipic pentru N”) — doar datele; desenul decide dacă le comprimă
        from .documente_tabele import grupuri_tipice
        gt_ = grupuri_tipice(m)
        if gt_:
            m["grupuri_tipice"] = gt_
    return m, r


_TIP_DDR = ("rccb", "rcbo", "mccb_dif")


def _are_ddr(a):
    """aparatul conține o protecție diferențială care DECLANȘEAZĂ (RCCB / RCBO / bloc diferențial); RCM = doar alarmă"""
    par = a.get("param") or {}
    return a.get("tip") in _TIP_DDR or (par.get("IdN_mA") is not None and par.get("sablon") in ("rccb", "rcbo"))


def _verifica_model_r8(m, r):
    """r8 — verificări generice pe modelul desenat, pentru ORICE tip de schemă:
    * un consumator de siguranță (plecare marcată `siguranta`) nu are DDR pe calea lui (intrări + ramurile din amonte
      + ramura proprie) și are cablu rezistent la foc (FE180) → altfel V97 BLOCANT;
    * o planșă fără intrări și fără plecări, fără niciun BLOCANT care să o explice → V00 BLOCANT explicit."""
    ver = r.setdefault("verificari", [])

    def bl(cod, ob, mesaj, rem):
        ver.append({"cod": cod, "nivel": "BLOCANT", "obiect": ob, "mesaj": mesaj, "remediere": rem})
        r["blocheaza_export"] = True

    cale0 = [a for b in (m.get("intrari") or []) for a in (b.get("aparate") or [])]

    def walk(bs, cale):
        for b in bs:
            ap = b.get("aparate") or []
            c2 = cale + ap
            if b.get("siguranta"):
                nume = (b.get("sarcina") or {}).get("titlu") or "consumator de siguranță"
                ddr = [a.get("ref") or a.get("tip") for a in c2 if _are_ddr(a)]
                if ddr:
                    bl("V97", nume, f"consumator de siguranță ({nume}) cu DDR pe calea lui ({', '.join(ddr)}) — interzis "
                                    f"(I7/2011, P118-3)", "racord înaintea DDR-ului, fără DDR pe ramură (RCM doar alarmă)")
                txt = (b.get("cablu") or {}).get("text") or ""
                if txt and "FE180" not in txt and "existent" not in txt and "conform" not in txt:
                    bl("V97", nume, f"consumator de siguranță ({nume}) cu cablu nerezistent la foc ({txt.split(' ·')[0]})",
                       "cablu NHXH FE180/E90 pe traseu propriu")
            walk(b.get("copii") or [], c2)
    walk(m.get("plecari") or [], cale0)
    if not (m.get("intrari") or m.get("plecari")) and not any(v.get("nivel") == "BLOCANT" for v in ver):
        bl("V00", "schema", "planșa nu conține nicio schemă desenabilă (fără intrări și fără plecări) — nu se exportă "
                            "o planșă goală", "completați datele schemei (tip, sursă, plecări / circuite)")


def _are_structura(tip, rz):
    """dacă rezultatul blocat conține totuși destule date ca schema să fie desenată (pentru vizualizarea problemei)"""
    if tip == "bransament":
        return bool(rz.get("C2") and rz.get("Q"))
    if tip in ("tablou",):
        return bool(rz.get("plecari") is not None and rz.get("Q1_C1", {}).get("protectie"))
    if tip == "pt":
        return bool(rz.get("trafo"))
    if tip == "cef":
        return bool(rz.get("invertoare") or rz.get("PCS"))
    if tip == "prosumator":
        return bool(rz.get("INV") or rz.get("invertoare"))
    if tip == "ge_ats":
        return bool(rz.get("Q_G") or (rz.get("Q1_C1") or {}).get("protectie"))
    if tip == "locuinta":
        return bool(rz.get("coloana") and rz.get("grupe_DDR") is not None)
    return False
