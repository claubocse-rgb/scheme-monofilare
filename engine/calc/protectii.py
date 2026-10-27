"""protectii.py — aparatele de protecție: tipul (SPEC §B.3), seriile (§B.4), calibrul și reglajele (§B.5),
I2 (§B.6), curentul de deconectare Ia (§B.15), capacitatea de rupere (§B.5 pct. 6 / §B.16)
și selectivitatea amonte–aval (§B.18).

O protecție se reprezintă ca dict: {tip, In_A, curba?, Ir_A?, Ir_multiplu?, decl ('TM'|'EL')?, Im_A?, Isd_A?,
Isd_multiplu?, Ii_A?, tsd_s?, Icu_kA}. Curentul de reglaj Ip = Ir pentru MCCB/ACB, altfel In.
"""
from . import norme
from .comun import ge, gt, lt, eq, prima_din_serie

SERII = {"MCB": norme.MCB_IN_A, "MCCB": norme.MCCB_IN_A, "ACB": norme.ACB_IN_A, "gG": norme.GG_IN_A,
         "gPV": norme.GPV_IN_A}
SERII_ICU = {"MCB": norme.MCB_ICN_KA, "MCCB": norme.MCCB_ICU_KA, "ACB": norme.ACB_ICU_KA}
IN_MAX_ABSOLUT = 4000


def normalizeaza_tip(tip):
    """Normalizează denumirea tipului de aparat („mccb” → „MCCB”, „GG” → „gG”) la seriile SPEC §B.4."""
    if tip is None:
        return None
    t = str(tip).strip()
    # r12 (proiecte reale): separatorul cu siguranțe MPR / NH (separator fuzibil, „sigurante”) = gG
    return {"MCB": "MCB", "MCCB": "MCCB", "ACB": "ACB", "GG": "gG", "GPV": "gPV", "MPR": "gG", "NH": "gG",
            "SEPARATOR_FUZIBIL": "gG", "SIGURANTE": "gG", "SIGURANTE_GG": "gG", "SEP_SIG": "gG",
            "MCB_C": "MCB"}.get(t.upper().replace(" ", "_").replace("-", "_").replace("Ț", "T"), t)


def tip_implicit(rol, receptor, ip_min):
    """SPEC §B.3: tipul protecției când utilizatorul nu îl impune, după rolul ramurii și Ip,min."""
    if rol == "plecare":
        if ip_min <= 630 + 1e-9:
            return "gG"
        return "MCCB" if ip_min <= 1600 + 1e-9 else "ACB"
    if rol in ("qg", "q_trafo"):
        return "MCCB" if ip_min <= 1600 + 1e-9 else "ACB"
    # final, intrare, invertor, pcs, c2
    if ip_min <= 63 + 1e-9:
        return "MCB"
    return "MCCB" if ip_min <= 1600 + 1e-9 else "ACB"


def curba_implicita(receptor):
    """SPEC §B.3: MCB curba B pentru iluminat și prize, C pentru restul."""
    return "B" if receptor in ("iluminat", "prize") else "C"


def declansator(tip, In):
    """SPEC §B.5 pct. 2–3: MCCB In ≤ 250 A termomagnetic (TM), In ≥ 320 A electronic (EL); ACB electronic."""
    if tip == "MCCB":
        return "TM" if In <= norme.MCCB_TM_IN_MAX else "EL"
    if tip == "ACB":
        return "EL"
    return None


def alege_reglaj_ir_max(tip, In, ir_max):
    """SPEC §C.6 pct. 1 (v1.2): Ir = cel mai mare multiplu din treaptă cu k·In ≤ ir_max (protecție strictă la
    suprasarcină a generatorului). Returnează (k, Ir) sau (None, None) dacă nici treapta minimă nu încape."""
    trepte = norme.IR_TREPTE["MCCB_TM"] if declansator(tip, In) == "TM" else norme.IR_TREPTE["MCCB_EL"]
    ok = [k for k in trepte if ge(ir_max, k * In)]
    if not ok:
        return None, None
    k = max(ok)
    return k, k * In


def ip(prot):
    """Curentul de reglaj al protecției: Ir pentru MCCB/ACB, In pentru MCB/gG (SPEC §B.5)."""
    return prot["Ir_A"] if prot.get("Ir_A") is not None else prot["In_A"]


def alege_reglaj_ir(tip, In, ip_min):
    """SPEC §B.5 pct. 2: Ir = (cel mai mic multiplu din treaptă ≥ Ip,min/In)·In. Dacă niciun multiplu nu ajunge
    (calibru impus prea mic), Ir = In (verificarea se face prin V04/V40/V60/V65)."""
    trepte = norme.IR_TREPTE["MCCB_TM"] if declansator(tip, In) == "TM" else norme.IR_TREPTE["MCCB_EL"]
    for k in trepte:
        if ge(k * In, ip_min):
            return k, k * In
    return 1.0, float(In)


def construieste(tip, In, ip_min, curba=None, are_aval=False, decl=None, ir=None, isd=None):
    """SPEC §B.5: completează protecția (In ales, Ir, Im/Ii, tsd) pentru tipul dat.
    r12 (proiecte reale): `decl` impus („EL” — declanșator electronic și la In ≤ 250 A), `ir` = Ir reglat impus [A]
    (reglajul proiectantului, ex. 0,8·In), `isd` = Isd reglat impus [A] (altfel ales după Ik1min, §B.5 pct. 4)."""
    p = {"tip": tip, "In_A": In}
    if tip == "MCB":
        p["curba"] = curba or "C"
    elif tip in ("MCCB", "ACB"):
        if ir is not None:
            p["Ir_A"] = float(ir)
            p["Ir_multiplu"] = round(float(ir) / In, 3)
            p["Ir_fortat"] = True
        else:
            k, ir_ = alege_reglaj_ir(tip, In, ip_min)
            p["Ir_multiplu"] = k
            p["Ir_A"] = ir_
        p["decl"] = decl if decl in ("TM", "EL") else declansator(tip, In)
        if p["decl"] == "TM":
            p["Im_A"] = norme.IM_TM_MULTIPLU * In
        else:
            p["Ii_A"] = 12.0 * In
            p["tsd_s"] = norme.TSD_S if are_aval else 0.0
            if isd is not None:
                p["Isd_A"] = float(isd)
                p["Isd_multiplu"] = round(float(isd) / p["Ir_A"], 2)
                p["Isd_fortat"] = True
    return p


def alege_calibru(tip, ip_min, serie=None):
    """SPEC §B.5 pct. 1–3: cel mai mic In din serie ≥ Ip,min (None dacă depășește seria)."""
    return prima_din_serie(serie or SERII[tip], ip_min)


def in_max(tip, serie=None):
    """Calibrul maxim al seriei (SPEC §B.3: MCB 125, gG 1250, MCCB 1600, ACB 4000)."""
    return max(serie or SERII[tip])


def alege_icu(tip, ik3_kA):
    """SPEC §B.5 pct. 6: cea mai mică capacitate de rupere din serie ≥ Ik3max la bara aparatului.
    gG NH: 120 kA (v1.2, SR EN 60269-2). Returnează (Icu, suficient)."""
    if tip == "gG":
        return norme.GG_ICU_KA, ge(norme.GG_ICU_KA, ik3_kA)
    serie = SERII_ICU.get(tip)
    if not serie:
        return None, True
    v = prima_din_serie(serie, ik3_kA)
    if v is None:
        return max(serie), False
    return v, True


def i2(prot):
    """SPEC §B.6: curentul convențional de funcționare I2 (MCB 1,45·In; MCCB/ACB 1,30·Ir; gG 1,6/1,9/2,1·In; gPV 1,45·In)."""
    t = prot["tip"]
    if t in ("MCCB", "ACB"):
        return norme.I2_MULTIPLU[t] * prot["Ir_A"]
    if t == "gG":
        return norme.i2_gg(prot["In_A"]) * prot["In_A"]
    return norme.I2_MULTIPLU.get(t, 1.45) * prot["In_A"]


def alege_isd(prot, ik1_A):
    """SPEC §B.5 pct. 4: cel mai mare multiplu m cu 1,2·m·Ir ≤ Ik1min; dacă niciunul nu satisface, m = 1,5.
    r12: Isd reglat impus de proiectant (`Isd_fortat`) nu se modifică."""
    if prot.get("Isd_fortat"):
        return prot.get("Isd_multiplu")
    ok = [m for m in norme.ISD_MULTIPLI if ge(ik1_A, norme.TOLERANTA_MAGNETIC * m * prot["Ir_A"])]
    m = max(ok) if ok else norme.ISD_MULTIPLI[0]
    prot["Isd_multiplu"] = m
    prot["Isd_A"] = m * prot["Ir_A"]
    return m


def timp_deconectare_cerut(receptor, ip_A, schema="TN"):
    """SPEC §B.15: 0,4 s pentru circuitele finale cu Ip ≤ 63 A (receptor ≠ tablou), altfel 5 s; TT: 0,2 s / 1 s."""
    final = receptor != "tablou" and ip_A <= norme.IN_MAX_CIRCUIT_FINAL_0_4S_A + 1e-9
    return norme.T_DECONECTARE_S[("TT" if schema == "TT" else "TN", "final" if final else "distributie")]


def ia(prot, t_s):
    """SPEC §B.15, tabelul Ia: MCB 5/10/20·In; MCCB TM 1,2·Im; EL/ACB 1,2·Isd; gG din tabel la 0,4 s / 5 s.
    Returnează None dacă valoarea nu există pentru calibru și timp (V30 AVERTISMENT)."""
    t = prot["tip"]
    if t == "MCB":
        return norme.MCB_IA_MULTIPLU[prot.get("curba", "C")] * prot["In_A"]
    if t in ("MCCB", "ACB"):
        if prot.get("decl") == "TM":
            return norme.TOLERANTA_MAGNETIC * prot["Im_A"]
        return norme.TOLERANTA_MAGNETIC * prot["Isd_A"]
    if t == "gG":
        tab = norme.GG_IA_0_4S_A if t_s <= 0.4 + 1e-9 else (norme.GG_IA_5S_A if t_s >= 5 - 1e-9 else None)
        if tab is None:
            return None
        return tab.get(prot["In_A"])
    return None


def timp_termic(prot, ik1_A, stare):
    """SPEC §B.17, timpul t la Ik1min pentru verificarea adiabatică: aparate instantanee 0,1 s; gG 0,1 / 0,4 / 5 s
    după porți; deconectare prin DDR 0,3 s; deconectare neîndeplinită 5 s."""
    if stare in ("ddr_propriu", "ddr_amonte"):
        return 0.3
    if stare in ("blocant", "z_implicit", "regim_ge"):
        return 5.0
    if prot["tip"] == "gG":
        In = prot["In_A"]
        porti = norme.GG_PORTI_A.get(In)
        if porti and ge(ik1_A, porti[3]):
            return 0.1
        ia04 = norme.GG_IA_0_4S_A.get(In)
        if ia04 is not None and ge(ik1_A, ia04):
            return 0.4
        return 5.0
    return 0.1


def t_ik3(prot, are_aval):
    """SPEC §B.11 / §B.17: durata pentru verificarea termică la Ik3max a MCCB/ACB: 0,02 s (+0,1 s electronic cu tsd)."""
    t = 0.02
    if prot.get("decl") == "EL" and are_aval:
        t += norme.TSD_S
    return t


def prag_selectivitate(prot):
    """SPEC §B.18 pct. 4b: limita de selectivitate Is [A] = pragul inferior instantaneu al aparatului amonte."""
    t = prot["tip"]
    In = prot["In_A"]
    if t == "MCB":
        return {"B": 3.0, "C": 5.0, "D": 10.0}[prot.get("curba", "C")] * In
    if t in ("MCCB", "ACB"):
        if prot.get("decl") == "TM":
            return 0.8 * norme.IM_TM_MULTIPLU * In
        return 0.8 * 12.0 * In
    if t == "gG":
        porti = norme.GG_PORTI_A.get(In)
        if porti:
            return float(porti[2])
        return float(norme.GG_IA_0_4S_A.get(In, 5 * In))
    return 0.0


def selectivitate(amonte, aval, ik_kA, obiect, jurnal, bmpt=False):
    """SPEC §B.18: regula simplificată de selectivitate pentru perechea (amonte, aval), cu Ik = Ik3max la bara aparatului
    aval. Emite V40 / V41 / V42."""
    from .verificari import emite, BLOCANT, AVERTISMENT, INFO
    a, b = ip(amonte), ip(aval)
    if bmpt:
        emite(jurnal, "V41", INFO, obiect, "bmpt")
        return
    if lt(a, b):
        emite(jurnal, "V40", BLOCANT, obiect, a=a, b=b)
        return
    if eq(a, b):
        emite(jurnal, "V41", AVERTISMENT, obiect, "egal", a=a)
        return
    r = a / b
    if amonte["tip"] == "gG" and aval["tip"] == "gG":
        rr = amonte["In_A"] / aval["In_A"]
        if ge(rr, norme.RAPORT_SELECTIVITATE_GG):
            emite(jurnal, "V42", INFO, obiect, "INFO_gg", r=rr)
        else:
            emite(jurnal, "V41", AVERTISMENT, obiect, "gg", r=rr)
        return
    if lt(r, norme.RAPORT_SELECTIVITATE_SUPRASARCINA):
        emite(jurnal, "V41", AVERTISMENT, obiect, "raport", r=r)
    is_kA = prag_selectivitate(amonte) / 1000.0
    if ge(is_kA, ik_kA):
        emite(jurnal, "V42", INFO, obiect, "INFO", Ik=ik_kA, Is=is_kA)
    else:
        emite(jurnal, "V42", AVERTISMENT, obiect, "AV", Ik=ik_kA, Is=is_kA)


def in_serie(prot):
    """Verifică apartenența protecției la seriile din norme (SPEC §B.4; folosit și de testul de proprietate)."""
    t = prot["tip"]
    if prot["In_A"] not in SERII[t]:
        return False
    if t in ("MCCB", "ACB") and not prot.get("Ir_fortat"):
        trepte = norme.IR_TREPTE["MCCB_TM"] if prot.get("decl") == "TM" else norme.IR_TREPTE["MCCB_EL"]
        if not any(eq(k * prot["In_A"], prot["Ir_A"]) for k in trepte):
            return False
    if t in SERII_ICU and prot.get("Icu_kA") is not None and prot.get("Icu_fortat") is None:
        if prot["Icu_kA"] not in SERII_ICU[t]:
            return False
    return True
