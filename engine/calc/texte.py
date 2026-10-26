"""texte.py — textele de pe listă și de pe desen generate din parametri (SPEC §E), notele cu valori (SPEC §G.3)
și verificările V80 / V81 (listă ≠ parametri, notă ≠ model).

Modelul stochează doar parametri; textele se regenerează la fiecare randare (SPEC §E.1). Funcții publice:
    fmt_ro(x, zecimale)                 → număr formatat românește (SPEC §E.2)
    text_lista(tip, parametri)          → (denumire, caracteristici)            (SPEC §E.3)
    text_desen(tip, parametri)          → list[str], maximum 3 rânduri          (SPEC §E.3)
    text_cablu(...)                     → textul cablului pentru listă          (SPEC §B.9, §E.3)
    note_generate(rezultat)             → notele G.3 ale unei scheme             (SPEC §G.3)
    verifica_aparat(ref, tip, parametri, text_lista, text_desen) → V80          (SPEC §E.1 pct. 3, §D)
    verifica_nota(k, text, text_model)  → V81                                    (SPEC §E.1 pct. 4, §D)
"""
import math
import re

from . import norme

NB = " "          # spațiu fără întrerupere între număr și unitate (SPEC §E.2)
FIN = " "         # spațiu fin fără întrerupere, separator de mii de la 10 000 (SPEC §E.2)
MINUS = "−"
X = "×"           # „×” (SPEC §E.2)
PUNCT = "·"       # „·”
INTERVAL = "…"    # „…”


# ------------------------------------------------------------------------------------------------------------
# E.2 Formatare
# ------------------------------------------------------------------------------------------------------------
def fmt_ro(x, zecimale=2):
    """SPEC §E.2: virgulă zecimală, zerourile finale eliminate (250,0 → „250”), fără separator de mii sub 10 000,
    spațiu fin de la 10 000 în sus („12 500”), minus tipografic."""
    if x is None:
        return "—"
    if isinstance(x, str):
        return x
    v = round(float(x), zecimale)
    if v == 0:
        v = 0.0
    s = f"{abs(v):.{max(zecimale, 0)}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    intreg, _, frac = s.partition(".")
    if abs(v) >= 10000:
        grupe = []
        while len(intreg) > 3:
            grupe.insert(0, intreg[-3:])
            intreg = intreg[:-3]
        grupe.insert(0, intreg)
        intreg = FIN.join(grupe)
    rez = intreg + ("," + frac if frac else "")
    return (MINUS + rez) if v < 0 else rez


def _u(x, unitate, zecimale=2):
    """Număr + spațiu fără întrerupere + unitate („250 A”, „35 mm²”), SPEC §E.2."""
    return f"{fmt_ro(x, zecimale)}{NB}{unitate}"


def _poli(p, implicit=4):
    """Numărul de poli ca text (SPEC §E.3): 4 → „4P”, „1P+N” rămâne „1P+N”."""
    if p is None:
        p = implicit
    if isinstance(p, str):
        return p if p.upper().endswith(("P", "N")) else p + "P"
    return f"{int(p)}P"


def _idn_mic(idn):
    """v1.6: DDR de protecție suplimentară (IΔn ≤ 30 mA) — pe desen tipul se scrie „tip A”."""
    try:
        return float(idn) <= 30
    except (TypeError, ValueError):
        return False


def _g(p, *chei, implicit=None):
    """Primul parametru prezent dintre cheile date (șabloanele SPEC §E.3 acceptă denumiri alternative)."""
    for c in chei:
        if c in p and p[c] is not None:
            return p[c]
    return implicit


def _normalizeaza_tip(tip):
    """Normalizează tipul de aparat la cheile tabelului SPEC §E.3."""
    t = (tip or "").strip().lower().replace("-", "_").replace(" ", "_")
    alias = {"separator_sigurante": "sep_sig", "separator": "sep_sig", "gg": "sep_sig", "nh": "sep_sig",
             "sf": "sf", "sf_bransament": "sf", "mccb_tm": "mccb", "mccb_el": "mccb",
             "spd": "spd_ca", "spd_c.a.": "spd_ca", "spd_cc": "spd_cc", "spd_c.c.": "spd_cc",
             "conductor_pe": "pe", "fy": "pe", "transformator": "trafo", "post_trafo": "trafo",
             "celula_trafo_sigurante": "celula_sigurante", "celula_trafo_intreruptor": "celula_intreruptor",
             "grup_electrogen": "ge", "bess": "baterie", "bare_tablou": "bare", "contor_energie": "contor"}
    return alias.get(t, t)


# ------------------------------------------------------------------------------------------------------------
# E.3 Șabloane
# ------------------------------------------------------------------------------------------------------------
def _mccb_decl(p):
    """Declanșatorul MCCB: TM până la 250 A, EL de la 320 A (SPEC §B.5 pct. 2, §E.3)."""
    d = _g(p, "declansator", "decl")
    if d:
        return "EL" if str(d).upper().startswith(("EL", "LSI")) else "TM"
    return "TM" if float(_g(p, "In_A", implicit=0)) <= norme.MCCB_TM_IN_MAX else "EL"


def _sabloane(tip, p):
    """Returnează (denumire, caracteristici, desen) pentru un tip de aparat — tabelul SPEC §E.3."""
    t = _normalizeaza_tip(tip)
    In = _g(p, "In_A", "In")
    if t == "mcb":
        poli = _poli(_g(p, "poli"), 4)
        curba = _g(p, "curba", implicit="C")
        icn = _g(p, "Icn_kA", "Icu_kA", implicit=6)
        u = _g(p, "U_V", implicit=(230 if poli in ("1P", "2P", "1P+N") else 400))
        bk = p.get("backup_SF_A")
        bk_t = ""
        if bk:
            # r8 (#35): Icn < Ik3 la locul de montaj → back-up prin siguranțele SF gG din amonte (asociere declarată)
            bk_t = (f"; Icn < Ik3 {_u(p.get('backup_Ik3_kA'), 'kA')} — protejat în back-up de SF gG"
                    + (f" {_u(bk, 'A')}" if not isinstance(bk, bool) else "")
                    + " (asociere ≥ Ik3 din tabelele de coordonare ale producătorului)")
        return (f"Întreruptor automat modular {poli}, curba {curba}, In {_u(In, 'A')}",
                f"Icn {_u(icn, 'kA')}, {_u(u, 'V')} c.a., SR EN 60898-1" + bk_t,
                f"{poli} {PUNCT} {curba}{fmt_ro(In)} {PUNCT} {_u(icn, 'kA')}")
    if t in ("mccb", "acb"):
        poli = _poli(_g(p, "poli"), 4)
        ir = _g(p, "Ir_A", implicit=In)
        k = ir / In if In else 1.0
        icu = _g(p, "Icu_kA")
        el = (t == "acb") or _mccb_decl(p) == "EL"
        if not el:
            im = _g(p, "Im_A", implicit=norme.IM_TM_MULTIPLU * In)
            km = (float(im) / float(In)) if In else norme.IM_TM_MULTIPLU
            car = (f"Ir = {fmt_ro(k)}{PUNCT}In = {_u(ir, 'A')}, Im = {fmt_ro(km, 0)}{PUNCT}In = {_u(im, 'A')}, "
                   f"Icu {_u(icu, 'kA')}" + (f" la {_u(_g(p, 'U_V'), 'V')}" if _g(p, "U_V") else "")
                   + f", {_u(_g(p, 'U_V', implicit=400), 'V')} c.a., SR EN 60947-2")
            if _g(p, "bd"):
                car += ", bobină de declanșare BD"
            if _g(p, "intrerupator_motor"):
                return (f"Întreruptor-motor (MCCB, magnetic pentru pornirea motoarelor) {poli}, In {_u(In, 'A')}",
                        car + ", coordonat tip 2 cu contactorul și releul termic (SR EN 60947-4-1)",
                        f"{poli} {PUNCT} {_u(In, 'A')} {PUNCT} Ir {_u(ir, 'A')} {PUNCT} Im {_u(im, 'A')}")
            return (f"Întreruptor automat compact MCCB {poli}, In {_u(In, 'A')}, declanșator termomagnetic", car,
                    f"{poli} {PUNCT} {_u(In, 'A')} {PUNCT} Ir {_u(ir, 'A')} {PUNCT} {_u(icu, 'kA')}")
        nume = "ACB" if t == "acb" else "MCCB"
        isd = _g(p, "Isd_A")
        parti = [f"Ir = {fmt_ro(k)}{PUNCT}In = {_u(ir, 'A')}"]
        if isd is not None:
            m = _g(p, "Isd_multiplu", implicit=(isd / ir if ir else None))
            parti.append(f"Isd = {fmt_ro(m)}{PUNCT}Ir = {_u(isd, 'A')}")
        tsd = _g(p, "tsd_s")
        if tsd is not None:
            parti.append(f"tsd {_u(tsd, 's')}")
        ii = _g(p, "Ii_A")
        if ii is not None:
            parti.append(f"Ii = {_u(ii, 'A')}")
        if icu is not None:
            parti.append(f"Icu {_u(icu, 'kA')}" + (f" la {_u(_g(p, 'U_V'), 'V')}" if _g(p, "U_V") else ""))
        if _g(p, "U_V"):
            parti.append(f"Ue {_u(_g(p, 'U_V'), 'V')} c.a.")       # r7: aparataj pentru rețeaua de 800 V c.a.
        desen = f"{poli} {PUNCT} {_u(In, 'A')} {PUNCT} Ir {_u(ir, 'A')}"
        if isd is not None:
            desen += f" {PUNCT} Isd {_u(isd, 'A')}"
        return (f"Întreruptor automat {nume} {poli}, In {_u(In, 'A')}, declanșator electronic LSI",
                ", ".join(parti), desen)
    if t == "sep_sig":
        poli = _poli(_g(p, "poli"), 3)
        gab = str(_g(p, "gabarit") or gabarit_nh(In))
        gab = gab[2:] if gab.upper().startswith("NH") else gab   # șablonul E.3 conține deja „NH ”
        n = int(_g(p, "poli", implicit=3)) if not isinstance(_g(p, "poli"), str) else 3
        icu = _g(p, "Icu_kA", implicit=norme.GG_ICU_KA)
        return (f"Separator {poli} cu siguranțe fuzibile NH {gab}, {_u(In, 'A')} gG",
                f"{_u(400, 'V')} c.a., {_u(icu, 'kA')}, separare vizibilă, SR EN 60947-3 / SR EN 60269-2",
                f"{n} {X} {_u(In, 'A')} gG")
    if t == "sf":
        gab = _g(p, "gabarit", implicit="NH00")
        soclu = _g(p, "soclu_A", implicit=160)
        return (f"Separator tripolar cu siguranțe fuzibile {gab}, soclu {_u(soclu, 'A')}, fuzibil {_u(In, 'A')} gG",
                f"{_u(400, 'V')}, {_u(50, 'kA')}, sigilabil (ST 4-JT)",
                f"3 {X} {_u(In, 'A')} gG")
    if t == "rccb" and (float(In or 0) > norme.RCCB_IN_A[-1] or _g(p, "aparat") == "bloc_diferential"):
        t = "bloc_diferential"      # M11 (v1.2): peste 125 A nu există RCCB modular → bloc diferențial pe MCCB (§B.4)
    if t == "bloc_diferential":
        poli = _poli(_g(p, "poli"), 4)
        idn = _g(p, "IdN_mA", implicit=300)
        tipd = _g(p, "tip_ddr", "tip_rcd", "clasa", implicit="AC")
        sel = ", S" if _g(p, "selectiv") else ""
        q = _g(p, "asociat", implicit="Q")
        tq = _g(p, "tip_q", implicit="MCCB")
        return (f"Bloc diferențial asociat întreruptorului {q} ({tq} {poli}, In {_u(In, 'A')}), IΔn {_u(idn, 'mA')}, "
                f"tip {tipd}{sel}",
                f"IΔn și Δt reglabile, declanșare prin bobina {tq}, SR EN 60947-2 anexa B",
                f"Bloc dif. {PUNCT} {_u(In, 'A')} {PUNCT} IΔn {_u(idn, 'mA')} {tipd}{' S' if sel else ''}")
    if t == "rccb":
        poli = _poli(_g(p, "poli"), 4)
        idn = _g(p, "IdN_mA", implicit=300)
        tipd = _g(p, "tip_ddr", "tip_rcd", "clasa", implicit="AC")
        sel = ", S" if _g(p, "selectiv") else ""
        return (f"Întreruptor diferențial {poli}, In {_u(In, 'A')}, IΔn {_u(idn, 'mA')}, tip {tipd}{sel}",
                "Icn ≥ 6" + NB + "kA, fără protecție la supracurenți",
                # v1.6 (P2-6): la DDR ≤ 30 mA (circuitele finale) „30 mA tip A”, nu „30 mA A”
                f"{poli} {PUNCT} {_u(In, 'A')} {PUNCT} IΔn {_u(idn, 'mA')} "
                f"{'tip ' if _idn_mic(idn) else ''}{tipd}{' S' if sel else ''}")
    if t == "rcbo":
        # implicit = RCBO-ul din BMPM (ST 3-JT): 1P+N, C, 300 mA AC; pe circuitele locuinței: 30 mA, tip A, curba din calcul
        poli = _g(p, "poli", implicit="1P+N")
        curba = _g(p, "curba", implicit="C")
        idn = _g(p, "IdN_mA", implicit=300)
        tipd = _g(p, "tip_ddr", implicit="AC")
        icn = _g(p, "Icn_kA", "Icu_kA", implicit=None)
        sel = bool(_g(p, "selectiv"))
        return (f"Întreruptor automat cu protecție diferențială {poli}, curba {curba}, In {_u(In, 'A')}, IΔn {_u(idn, 'mA')}, tip {tipd}"
                + (", selectiv (S)" if sel else ""),
                (f"Icn {_u(icn, 'kA')}, SR EN 61009-1" if icn else "Icn ≥ 6" + NB + "kA (ST 3-JT)"),
                f"{poli} {PUNCT} {curba}{fmt_ro(In)} {PUNCT} {_u(idn, 'mA')}" + (f" tip {tipd}" if tipd != "AC" else "")
                + (" S" if sel else ""))
    if t == "tc":
        prim = _g(p, "primar_A")
        cls = _g(p, "clasa", implicit="0,5")
        sn = _g(p, "Sn_VA", implicit=5)
        n = _g(p, "n", "buc", implicit=3)
        um = 1.2 if float(_g(p, "U_V", implicit=400)) > 690 else 0.72       # r7: TC pentru rețeaua de 800 V
        return (f"Transformator de curent JT {fmt_ro(prim)}/5{NB}A, cl. {cls}, {_u(sn, 'VA')}, Fs 5",
                f"{_u(um, 'kV')}, capac sigilabil, SR EN 61869-2 — {fmt_ro(n)} buc.",
                f"{fmt_ro(n)} {X} {fmt_ro(prim)}/5{NB}A {PUNCT} cl. {cls}")
    if t == "contor":
        tri = _g(p, "retea", implicit="tri") == "tri"
        direct = _g(p, "masura", implicit="directa").startswith("dir")
        bidir = ", bidirecțional" if _g(p, "bidirectional") else ""
        u = f"3 {X} 230/400{NB}V" if tri else f"230{NB}V"
        if tri and float(_g(p, "U_V", implicit=400)) > 400:
            u = f"3 {X} {fmt_ro(_g(p, 'U_V'), 0)}{NB}V (3 fire)"        # r7: măsura semidirectă pe 800 V c.a.
        i = (f"5(100){NB}A" if tri else f"5(60){NB}A") if direct else f"5{NB}A"
        return (f"Contor electronic {'tri' if tri else 'mono'}fazat de energie activă și reactivă, "
                f"{'direct' if direct else 'semidirect'}{bidir}",
                f"{u}, {i}, telecitire, furnizat și sigilat de OD", f"kWh {PUNCT} kVArh")
    if t == "dpst":
        return ("Dispozitiv de protecție la supratensiuni de frecvență industrială, trifazat",
                f"Uf = 270 ± 10{NB}V, t = 0,13{INTERVAL}0,2{NB}s, comandă BD pe Q", f"DPST {PUNCT} U> 50{NB}Hz")
    if t == "spd_ca":
        tipd = _g(p, "tip", "tip_spd", implicit="T1+T2")
        poli = _poli(_g(p, "poli"), 4)
        car = ("Iimp 12,5" + NB + "kA/pol (10/350)") if "T1" in tipd else ("In 20" + NB + "kA (8/20)")
        # v1.6 (m-n2 / N4): tipul protecției de rezervă („prot_tip”: gG implicit, sau MCB cu „curba”)
        pt = str(_g(p, "prot_tip", implicit="gG"))
        ia = _g(p, "In_amonte_A", "In_A", implicit=63)
        prot = (f"{_u(ia, 'A')} gG" if pt.lower() == "gg" else
                f"{pt} {_g(p, 'curba', implicit='')}{fmt_ro(ia)}{NB}A")
        uv = _g(p, "U_V")
        if uv and float(uv) > 400:
            # r7 (P0-3): SPD pentru rețeaua de 800 V c.a. (TN, fără N): Uc ≥ 1,1·U0, Up ≤ 2,5 kV
            uc = 1.1 * float(uv) / 3 ** 0.5
            return (f"Descărcător SPD tip {tipd}, {poli}, pentru rețea 3 {X} {fmt_ro(uv, 0)}{NB}V c.a.",
                    f"{car}, Uc ≥ 1,1{PUNCT}U0 = {_u(uc, 'V', 0)}, Up ≤ 2,5{NB}kV, protecție amonte {prot}",
                    f"SPD {tipd} {PUNCT} {poli} {PUNCT} {fmt_ro(uv, 0)}{NB}V")
        return (f"Descărcător SPD tip {tipd}, {poli}",
                f"{car}, Up ≤ 1,5{NB}kV, protecție amonte {prot}",
                f"SPD {tipd} {PUNCT} {poli}")
    if t == "spd_cc":
        u = _g(p, "Ucpv_V")
        car = (f"In {_u(_g(p, 'In_kA', implicit=20), 'kA')} (8/20)"
               + (f", Imax {_u(p['Imax_kA'], 'kA')}" if p.get("Imax_kA") is not None else "")
               + (f", Up ≤ {_u(p['Up_kV'], 'kV')}" if p.get("Up_kV") is not None else "") + ", SR EN 61643-31")
        tipd = "1+2" if "1" in str(p.get("tip") or "") else "2"
        return (_cu_model(f"Descărcător SPD c.c. tip {tipd}, Ucpv {_u(u, 'V')}", p), car,
                f"SPD c.c.{' T1+T2' if tipd == '1+2' else ''} {PUNCT} {_u(u, 'V')}")
    if t == "gpv":
        u = _g(p, "U_V", implicit=1100)
        n = _g(p, "n", "buc", implicit=2)
        if In is None or _g(p, "generic"):
            # r6 (fotovoltaic P1-7): gPV necesare, calibrul din proiectul de c.c. (Isc al modulului necunoscut)
            return (_cu_model(f"Siguranță fuzibilă gPV pe fiecare string, 10{X}38{NB}mm, {_u(u, 'V')} c.c., calibru "
                              f"conform proiect DC (1,5…2,4·Isc ≤ Irev)", p),
                    f"SR EN 60269-6 — {fmt_ro(n)} buc. (+ și −)", "gPV · conform proiect DC")
        return (_cu_model(f"Siguranță fuzibilă gPV {_u(In, 'A')}, 10{X}38{NB}mm, {_u(u, 'V')} c.c.", p),
                f"SR EN 60269-6 — {fmt_ro(n)} buc. (+ și −)", f"gPV {_u(In, 'A')}")
    if t == "camp_pv":
        kwp = _g(p, "kWp")
        n = _g(p, "buc", implicit=1)
        den = f"Câmp fotovoltaic {_u(kwp, 'kWp')}" if kwp is not None else "Câmp fotovoltaic"
        desen = (f"{_u(kwp, 'kWp')}" + (f" {X} {fmt_ro(n)}" if n and n > 1 else "")) if kwp is not None else "câmp PV"
        if not _model_text(p) and p.get("Pmax_W") is None:
            return den + " (module și stringuri conform plan PV)", "—", desen
        pm = p.get("Pmax_W")
        nm = math.ceil(kwp * 1000.0 / pm - 1e-6) if kwp and pm else None
        den += ", " + (f"{fmt_ro(nm)} module " if nm else "module ") + (_model_text(p) or "fotovoltaice") \
            + (f" {_u(pm, 'Wp')}" if pm else "")
        car = []
        if p.get("n_module"):
            car.append(f"{fmt_ro(p['n_module'])} module/string" + (f" {X} {fmt_ro(p['n_stringuri_paralel'])} stringuri"
                                                                  if p.get("n_stringuri_paralel") else "")
                       + (f"/MPPT {X} {fmt_ro(p['n_MPPT'])} MPPT" if p.get("n_MPPT") and p.get("n_stringuri_paralel") else ""))
        for k, et, um in (("Voc_V", "Voc", "V"), ("Isc_A", "Isc", "A"), ("Vmpp_V", "Vmpp", "V"), ("Impp_A", "Impp", "A"),
                          ("beta_Voc_pct_K", "β(Voc)", "%/K"), ("Umax_sistem_V", "Umax sistem", "V")):
            if p.get(k) is not None:
                car.append(f"{et} {_u(p[k], um, 3 if k.startswith('beta') else 2)}")
        return den, ", ".join(car) or "module și stringuri conform plan PV", desen
    if t == "cablu":
        txt = text_cablu(_g(p, "material", implicit="Cu"), _g(p, "izolatie", implicit="PVC"),
                         _g(p, "metoda", implicit="C"), _g(p, "n_paralel", "n", implicit=1),
                         _g(p, "S_faza_mm2", "S"), _g(p, "S_N_mm2", "N"), _g(p, "S_PE_mm2", "PE_mm2"),
                         _g(p, "PE", "PE_loc", implicit="cablu"), _g(p, "retea", implicit="tri"))
        n = int(_g(p, "n_paralel", "n", implicit=1))
        den = f"Cablu {txt} {_g(p, 'material', implicit='Cu')}" + (f", în paralel {n}{X}" if n > 1 else "")
        L = _g(p, "L_m", "L")
        car = (f"0,6/1{NB}kV, L ≈ {_u(L, 'm', 0)}, Iz' = {_u(_g(p, 'Iz_corectat_A', 'Iz_A'), 'A', 1)} "
               f"(metoda {_g(p, 'metoda', implicit='C')}, k = {fmt_ro(_g(p, 'k_total', 'k', implicit=1.0))}), "
               f"ΔU = {_u(_g(p, 'dU_ramura_pct', 'dU', implicit=0.0), '%')}")
        return den, car, f"{txt} {PUNCT} L ≈ {_u(L, 'm', 0)}"
    if t == "pe":
        s = _g(p, "S_PE_mm2", "S")
        return (f"Conductor de protecție FY 1{X}{_u(s, 'mm²')} Cu, galben-verde",
                f"pozat lângă cablul {_g(p, 'ref', implicit='—')}, L ≈ {_u(_g(p, 'L_m', 'L'), 'm', 0)}", None)
    if t == "trafo":
        sn = _g(p, "Sn_kVA")
        izt = _g(p, "izolatie", implicit="ulei")
        uk, pk, p0 = ((norme.TRAFO_USCAT if izt == "uscat" else norme.TRAFO).get(int(sn), (None, None, None))
                      if sn is not None else (None, None, None))
        uk = _g(p, "uk_pct", implicit=uk)
        pk = _g(p, "Pk_W", implicit=pk)
        p0 = _g(p, "P0_W", implicit=p0)
        gr = _g(p, "grupa", implicit=norme.TRAFO_GRUPA_CONEXIUNI)
        umt = fmt_ro(_g(p, "U_MT_kV", implicit=20))
        ujt = fmt_ro(_g(p, "U_JT_kV", implicit=0.4))          # r7: 0,8 kV la CEF cu invertoare de 800 V
        return (f"Transformator de putere {_u(sn, 'kVA')}, {umt} ± 2{X}2,5{NB}% / {ujt}{NB}kV, {gr}",
                f"uk {_u(uk, '%')}, Pk ≤ {_u(pk, 'W')}, P0 ≤ {_u(p0, 'W')} (Reg. UE 548/2014 Tier 2), "
                + ("uscat, rășină epoxidică, clasă F, E2-C2-F1, protecție termică PT100" if izt == "uscat" else "ulei"),
                f"{_u(sn, 'kVA')} {PUNCT} {umt}/{ujt}{NB}kV {PUNCT} {gr}" + (f" {PUNCT} uscat" if izt == "uscat" else ""))
    if t == "celula_sigurante":
        um = _u(_g(p, "Um_kV", implicit=24), "kV")
        return (f"Celulă MT de transformator cu separator de sarcină și siguranțe MT {_u(In, 'A')}",
                f"{um}, SR EN 62271-105, CLP", f"{um} {PUNCT} SF {_u(In, 'A')}")
    if t == "celula_intreruptor":
        um = _u(_g(p, "Um_kV", implicit=24), "kV")
        return (f"Celulă MT de transformator cu întreruptor în vid {um}, 630{NB}A, 16{NB}kA",
                f"releu 50/51, 50N/51N, TC MT {_g(p, 'raport', 'raport_TC', implicit='—')}",
                f"{um} {PUNCT} Q {PUNCT} F>")
    if t == "invertor":
        pn = _g(p, "Pn_kW")
        cert = _g(p, "certificare", implicit="RfG")
        hib = "hibrid " if p.get("hibrid") else ""
        car = f"Iac,max {_u(_g(p, 'Iac_max_A', 'Iac_A'), 'A')}" + _car_fisa_invertor(p) + f", PI integrată, certificat conform {cert}"
        if _g(p, "retea", implicit="tri") == "mono":
            fz = p.get("faza")         # r8: invertor monofazat pe rețea trifazată — faza de racord (L1 / L2 / L3)
            return (_cu_model(f"Invertor monofazat {hib}{_u(pn, 'kW')} c.a., 1 {X} 230{NB}V" + (f" ({fz} + N)" if fz else "")
                              + f", 50{NB}Hz", p), car,
                    f"{_u(pn, 'kW')} {PUNCT} " + (f"{fz} + N {PUNCT} 230{NB}V" if fz else f"1 {X} 230{NB}V"))
        uca = fmt_ro(_g(p, "U_ca_V", implicit=400), 0)        # r7: 800 V c.a. (3 fire, fără N)
        fn = ", fără N" if float(_g(p, "U_ca_V", implicit=400)) > 400 else ""
        return (_cu_model(f"Invertor trifazat {hib}{_u(pn, 'kW')} c.a., 3 {X} {uca}{NB}V{fn}, 50{NB}Hz", p), car,
                f"{_u(pn, 'kW')} {PUNCT} 3 {X} {uca}{NB}V")
    if t == "pcs":
        pn = _g(p, "Pn_kW", "P_kW")
        return (_cu_model(f"Convertor bidirecțional BESS {_u(pn, 'kW')}", p),
                f"Iac,max {_u(_g(p, 'Iac_max_A', 'Iac_A'), 'A')}" + _car_fisa_invertor(p) + ", grid-forming/following",
                f"{_u(pn, 'kW')}")
    if t == "baterie":
        kwh = _g(p, "kWh")
        chim = _g(p, "chimie", implicit="LiFePO₄")
        car = ", ".join(x for x in (f"U nominală {_u(p['U_nom_V'], 'V')} c.c." if p.get("U_nom_V") is not None else "",
                                    f"capacitate utilă {_u(p['kWh_util'], 'kWh')}" if p.get("kWh_util") is not None else "",
                                    f"Pmax {_u(p['P_kW'], 'kW')}" if p.get("P_kW") is not None and _model_text(p) else "") if x)
        return _cu_model(f"Baterie {chim} {_u(kwh, 'kWh')} cu BMS", p), car or "—", f"{_u(kwh, 'kWh')}"
    if t == "inversor":
        # r8 (#48): comutator manual de sursă I-0-II (inversor de sursă cu poziția 0), nu ATS automat
        return (f"Comutator manual de sursă I-0-II (inversor) 4P, {_u(In, 'A')}, AC-23B",
                "poziția 0 între rețea (I) și GE (II) — interblocaj mecanic intrinsec, acționare manuală, SR EN 60947-3",
                f"I-0-II 4P {PUNCT} {_u(In, 'A')}")
    if t == "ats":
        return (f"Comutator automat de sursă (ATS) 4P, {_u(In, 'A')}, AC-33B",
                "interblocaj mecanic + electric, SR EN 60947-6-1", f"ATS 4P {PUNCT} {_u(In, 'A')}")
    if t == "ge":
        sn = _g(p, "Sn_kVA")
        xd = _g(p, "xd_pct", implicit=norme.GE_XD2_IMPLICIT * 100)
        return (f"Grup electrogen {_u(sn, 'kVA')}, 3 {X} 400/230{NB}V",
                f"x\"d {_u(xd, '%')}, In {_u(_g(p, 'In_G_A'), 'A')}", f"GE {_u(sn, 'kVA')}")
    if t == "bare":
        conf = _g(p, "configuratie", implicit="3P+N+PE")
        return (f"Sistem de bare Cu {conf}, {_u(_g(p, 'In_bara_A', 'In_A'), 'A')}",
                f"Icw ≥ {_u(_g(p, 'Ik3_kA'), 'kA')}/1{NB}s", f"{_u(_g(p, 'In_bara_A', 'In_A'), 'A')}")
    raise ValueError(f"tip de aparat necunoscut pentru șabloanele E.3: {tip!r}")


def _model_text(p):
    """„Producător Model” din parametri (fără dublarea producătorului dacă modelul îl conține deja)."""
    pr = str((p or {}).get("producator") or "").strip()
    mo = str((p or {}).get("model") or "").strip()
    if pr and mo.lower().startswith(pr.lower()):
        pr = ""
    return " ".join(x for x in (pr, mo) if x)


def _cu_model(den, p):
    """Denumirea din listă + modelul echipamentului (fișa tehnică): „Invertor … — Huawei SUN2000-100KTL-M2”."""
    mt = _model_text(p)
    return f"{den} — {mt}" if mt else den


def _car_fisa_invertor(p):
    """Caracteristicile din fișa invertorului / PCS (doar cele date): Umax c.c., MPPT, nr. MPPT, Idc,max."""
    out = []
    if p.get("Umax_dc_V") is not None:
        out.append(f"Umax c.c. {_u(p['Umax_dc_V'], 'V')}")
    if p.get("MPPT_min_V") is not None and p.get("MPPT_max_V") is not None:
        out.append(f"MPPT {fmt_ro(p['MPPT_min_V'])}…{_u(p['MPPT_max_V'], 'V')}")
    if p.get("nr_MPPT") is not None:
        out.append(f"{fmt_ro(p['nr_MPPT'])} MPPT")
    if p.get("Idc_max_A") is not None:
        out.append(f"Idc,max {_u(p['Idc_max_A'], 'A')}/MPPT")
    return "".join(", " + x for x in out)


# tipurile la care modelul (fișa) apare și pe desen, pe un rând separat sub caracteristici
TIPURI_CU_MODEL = ("invertor", "pcs", "baterie", "camp_pv", "spd_cc", "gpv")


def model_scurt(p, max_lat=30):
    """modelul pentru textul de lângă simbol (scurt: fără producător dacă nu încape)"""
    mt = _model_text(p)
    if len(mt) > max_lat:
        mt = str((p or {}).get("model") or mt).strip()
    return mt if len(mt) <= max_lat else mt[:max_lat - 1] + "…"


def gabarit_nh(In):
    """Gabaritul NH după In (SPEC §B.4): ≤ 100 NH000, ≤ 160 NH00, ≤ 250 NH1, ≤ 400 NH2, ≤ 630 NH3, ≤ 1250 NH4a."""
    for lim, g in norme.GG_GABARIT_NH:
        if In is not None and In <= lim:
            return g
    return norme.GG_GABARIT_NH[-1][1]


def text_lista(tip, parametri):
    """SPEC §E.3, coloanele „Denumire” și „Caracteristici”: (denumire, caracteristici) generate din parametri."""
    den, car, _ = _sabloane(tip, parametri)
    return den, car


def _pe_randuri(text, max_lat=30, max_randuri=3):
    """Împarte textul de pe desen în cel mult 3 rânduri, la separatorul „ · ” (SPEC §E.3, „text pe desen”)."""
    if text is None:
        return []
    if len(text) <= max_lat:
        return [text]
    seg = text.split(f" {PUNCT} ")
    randuri = []
    for s in seg:
        if randuri and len(randuri[-1]) + 3 + len(s) <= max_lat:
            randuri[-1] = f"{randuri[-1]} {PUNCT} {s}"
        else:
            randuri.append(s)
    while len(randuri) > max_randuri:
        randuri[-2] = f"{randuri[-2]} {PUNCT} {randuri[-1]}"
        randuri.pop()
    return randuri


def text_desen(tip, parametri):
    """SPEC §E.3, coloana „Text pe desen”: rândurile de text de lângă simbol (maximum 3 rânduri).
    Rândurile unite cu „ · ” reproduc exact șablonul E.3."""
    _, _, d = _sabloane(tip, parametri)
    # `lat_desen`: lățimea maximă a rândului (caractere) — coloane înguste la tablourile cu multe circuite (locuințe)
    lat = int((parametri or {}).get("lat_desen") or 30)
    if _normalizeaza_tip(tip) in TIPURI_CU_MODEL and _model_text(parametri):
        # modelul din fișă: ultimul rând de lângă simbol (scurt); lista îl are complet
        return _pe_randuri(d, max_lat=lat, max_randuri=2) + [model_scurt(parametri, lat)]
    return _pe_randuri(d, max_lat=lat)


def tip_cablu(material, izolatie, metoda):
    """Denumirea RO a cablului (SPEC §B.8): armat în pământ (D1/D2), nearmat în aer."""
    return norme.TIP_CABLU[(material, izolatie, metoda in norme.METODE_IN_PAMANT)]


def text_cablu(material, izolatie, metoda, n_paralel, S_faza, S_N=None, S_PE=None, PE="cablu", retea="tri",
               monopolar=False, fara_N=False):
    """Textul cablului pentru listă (SPEC §B.9, §B.10, §B.11, §E.3), de ex.
    „CYABY 5×6 mm²”, „ACYABY 3×185+95 mm² + FY 1×50 mm² (PE)”, „2 × (ACYABY 4×120 mm² + FY 1×35 mm² (PE))”."""
    monopolar = monopolar or str(metoda).startswith("F")
    tip = norme.TIP_CABLU[(material, izolatie, False)] if monopolar else tip_cablu(material, izolatie, metoda)
    S_N = S_faza if S_N is None else S_N
    s, sn = fmt_ro(S_faza), fmt_ro(S_N)
    if fara_N and retea != "mono" and PE != "PEN":
        # r7 (P0-3): rețea de 800 V c.a. (invertoare fără neutru) — 3 faze + PE: „4×S” cu PE în cablu, „3×S” + FY separat
        if monopolar:
            cond = f"3{X}1{X}{s}"
        else:
            cond = f"4{X}{s}" if PE == "cablu" else f"3{X}{s}"
        txt = f"{tip} {cond}{NB}mm²" + (" (3 + PE)" if PE == "cablu" and not monopolar else "")
        if PE not in ("cablu", "fara"):
            txt += f" + {norme.TIP_CONDUCTOR_PE_SEPARAT} 1{X}{fmt_ro(S_PE)}{NB}mm² (PE)"
        n = int(n_paralel or 1)
        return f"{n} {X} ({txt})" if n > 1 else txt
    if monopolar:
        # v1.2 R2: sistem de cabluri monopolare (metoda F): „N2XY 4×1×300 mm²” sau „N2XY 3×1×300 + 1×150 mm²”
        cond = f"4{X}1{X}{s}" if S_N == S_faza else f"3{X}1{X}{s} + 1{X}{sn}"
        if PE == "PEN":
            cond += " (PEN)"
    elif PE == "PEN":
        # v1.2 R2 (N-M2): TN-C — 4 conductoare, al patrulea este PEN, fără PE separat
        cond = (f"4{X}{s}" if S_N == S_faza else f"3{X}{s}+{sn}") + f"{NB}mm² (PEN)"
        txt = f"{tip} {cond}"
        n = int(n_paralel or 1)
        return f"{n} {X} ({txt})" if n > 1 else txt
    elif retea == "mono":
        cond = f"{3 if PE == 'cablu' else 2}{X}{s}"
    elif PE == "cablu":
        cond = f"5{X}{s}" if S_N == S_faza else f"3{X}{s}+{sn}+{fmt_ro(S_PE)}"
    else:
        cond = f"4{X}{s}" if S_N == S_faza else f"3{X}{s}+{sn}"
    txt = f"{tip} {cond}{NB}mm²" if not cond.endswith("(PEN)") else f"{tip} {cond[:-6]}{NB}mm² (PEN)"
    if PE not in ("cablu", "PEN", "fara"):        # v1.6: „fara” — coloana TT a locuinței (L + N, fără PE)
        txt += f" + {norme.TIP_CONDUCTOR_PE_SEPARAT} 1{X}{fmt_ro(S_PE)}{NB}mm² (PE)"
    n = int(n_paralel or 1)
    if n > 1:
        txt = f"{n} {X} ({txt})"
    return txt


def nota_schema_pamant(tip_schema, spl, bloc=None, RA_ohm=None, pt=False, idn_mA=None, ddr_txt=None):
    """SPEC §G.1 nota 3 (v1.2): textul notei de legare la pământ generat din schema EFECTIVĂ (nu din text fix).
    TT: valorile reale RA și IΔn (DDR pe fiecare circuit la tablou, RCCB-ul blocului la branșament)."""
    if spl == "TT":
        ra_v = RA_ohm if RA_ohm is not None else 4.0
        ra = f"RA = {_u(ra_v, 'Ω')}" + ("" if RA_ohm is not None else
                                        (" (valoarea cerută de OD)" if tip_schema == "bransament" else " (presupus)"))
        idn = idn_mA if idn_mA is not None else 300
        x = ra_v * idn / 1000.0
        if ddr_txt:
            # v1.3 R5 (M5-4): DDR-urile reale (amonte, intrare, circuite), nu un IΔn unic „pe fiecare circuit”
            return (f"Schemă de legare la pământ: TT, {ddr_txt}; {ra}, RA·IΔn = {_u(x, 'V', 1)} "
                    f"{'≤' if x <= 50 + 1e-9 else '>'} 50{NB}V (IΔn max {_u(idn, 'mA')}).")
        unde = "RCCB-ul blocului de măsură" if tip_schema == "bransament" else "DDR pe fiecare circuit"
        return (f"Schemă de legare la pământ: TT, {unde} IΔn {_u(idn, 'mA')}, {ra}, RA·IΔn = {_u(x, 'V', 1)} "
                f"{'≤' if x <= 50 + 1e-9 else '>'} 50{NB}V.")
    if spl == "TN-C":
        return ("Schemă de legare la pământ: TN-C pe alimentarea din PT propriu (PEN ≥ 10 mm² Cu / 16 mm² Al), separarea "
                f"PEN în N + PE la bara tabloului, TN-S în aval. Rp ≤ {_u(1, 'Ω')}, conform calcul.")
    if pt or spl == "TN-S" and tip_schema in ("pt", "ge_ats"):
        if tip_schema == "ge_ats":
            return (f"Schemă de legare la pământ: TN-S, neutrul GE legat la priza de pământ locală, ATS 4P (comută și N). "
                    f"Rp ≤ {_u(4, 'Ω')}.")
        return f"Schemă de legare la pământ: TN-S din PT propriu. Rp ≤ {_u(1, 'Ω')}, conform calcul."
    if tip_schema == "bransament":
        return (f"Schemă de legare la pământ: TN-C-S cu separarea PEN pe BN în {bloc or 'bloc'}. Rp ≤ {_u(4, 'Ω')}.")
    return f"Schemă de legare la pământ: TN-S în aval de separarea PEN. Rp ≤ {_u(4, 'Ω')}."


# ------------------------------------------------------------------------------------------------------------
# G.3 Note generate din parametri
# ------------------------------------------------------------------------------------------------------------
def nota_bransament(bloc, Q, TC=None, Pa_kW=None):
    """SPEC §G.3 (v1.1), nota de branșament (forma de referință X02): „Măsurare …; Q {MCB C{In} | MCCB 4P In {In} A}
    [ reglat la Ir = {Ir} A][ (Pa = {Pa} kW din ATR) | (Pa din ATR)]; {bloc} conform ST 4-JT …, varianta {v}.”
    Ir apare doar dacă e în model (nu se deduce din limitele blocului); „(Pa din ATR)” doar cu Ir prezent."""
    b = norme.BMPT.get(bloc)
    if b is None:
        raise ValueError(f"bloc necunoscut: {bloc}")
    if b["masura"] == "semidirecta":
        prim = TC if isinstance(TC, (int, float)) else _primar_din_text(TC)
        mas = f"Măsurare semidirectă prin TC 3 {X} {fmt_ro(prim)}/5{NB}A, cl. 0,5, 5{NB}VA"
    else:
        mas = f"Măsurare directă 5(100){NB}A"
    In = Q.get("In_A")
    ir = None
    if str(Q.get("tip", "MCB")).upper().startswith("MCCB"):
        q = f"Q MCCB 4P In {_u(In, 'A')}"
        ir = Q.get("Ir_A")
        if ir is not None:
            q += f" reglat la Ir = {_u(ir, 'A')}"
    else:
        q = f"Q MCB C{fmt_ro(In)}"
    if Pa_kW is not None:
        q += f" (Pa = {_u(Pa_kW, 'kW')} din ATR)"
    elif ir is not None:
        q += " (Pa din ATR)"
    return f"{mas}; {q}; {bloc} conform ST 4-JT Ed. U1 Rev. 3/2024, varianta {b['varianta']}."


def _primar_din_text(t):
    """Curentul primar dintr-un text „3 × p/5 A” (SPEC §B.19, §G.3)."""
    if t is None:
        return None
    m = re.search(r"(\d+)\s*/\s*5", str(t))
    return int(m.group(1)) if m else None


def note_generate(rezultat):
    """SPEC §G.3: notele cu valori ale planșei, regenerate din rezultatul motorului (nu text liber).
    Acceptă rezultatul unei scheme de branșament, PT sau CEF (cheia „rezultat” din `calculeaza`)."""
    r = rezultat.get("rezultat", rezultat)
    note = []
    if "bloc" in r and str(r["bloc"]).startswith("BMPT"):
        note.append(nota_bransament(r["bloc"], r.get("Q", {}), r.get("TC"), r.get("Pa_kW")))
    elif "bloc" in r and str(r["bloc"]).startswith("BMPM"):
        q = r.get("Q", {})
        pa = f"(Pa = {_u(r['Pa_kW'], 'kW')} din ATR)" if r.get("Pa_kW") is not None else "(Pa din ATR)"
        note.append(f"Măsurare directă 5(60){NB}A; Q RCBO 1P+N C{fmt_ro(q.get('In_A'))}, IΔn 300{NB}mA {pa}; "
                    f"BMPM conform ST 3-JT Ed. U1 Rev. 3/2026.")
    if "trafo" in r and "Q_JT" in r:
        t, q = r["trafo"], r["Q_JT"]
        note.append(f"Trafo {_u(t['Sn_kVA'], 'kVA')}, In_T = {_u(t['In_T_A'], 'A')}; Q JT {q['tip']} {_u(q['In_A'], 'A')}, "
                    f"Ir = {_u(q['Ir_A'], 'A')}; Ik3max bara TGJT = {_u(t['Ik3max_bara_kA'], 'kA', 1)}; "
                    f"celula trafo {r.get('celula_trafo', '—')}.")
    if "sume" in r:
        s = r["sume"]
        pi = ("Ord. ANRE 228/2018" if r.get("prosumator") else "Ord. ANRE 208/2018 și ATR")
        txt = (f"Σ Pn = {_u(s['Pn_total_kW'], 'kW')}, S = {_u(s['S_total_kVA'], 'kVA')}, categoria "
               f"{r.get('categorie_RfG', 'A')} RfG; PI conform {pi}")
        if r.get("Uoc_Tmin_V") is not None:
            txt += (f"; Voc(−25{NB}°C) = {_u(r['Uoc_Tmin_V'], 'V', 1)} ≤ "
                    f"{_u(r.get('Umax_inv_V', norme.PV_UMAX_INVERTOR_IMPLICIT_V), 'V')}")
        note.append(txt + ".")
    return note


# ------------------------------------------------------------------------------------------------------------
# V80 / V81: comparația textelor stocate cu cele regenerate
# ------------------------------------------------------------------------------------------------------------
_NUM = r"\d+(?:[.,]\d+)?"
_TIPARE = [
    re.compile(rf"\bIn\s*=?\s*({_NUM})\s*A\b"),
    re.compile(rf"(?:\bTC\s+)?\b({_NUM})/5\s*A\b"),
    re.compile(rf"\bIr\s*=?\s*({_NUM})\s*A\b"),
    re.compile(rf"\bIc[un]\s*=?\s*({_NUM})\s*kA\b"),
    re.compile(rf"\bIsd\s*=?\s*({_NUM})\s*A\b"),
    re.compile(rf"\bIΔn\s*=?\s*({_NUM})\s*mA\b"),
    re.compile(rf"\b({_NUM})\s*kVA\b"),
    re.compile(rf"\b({_NUM})\s*kW\b"),
    re.compile(r"\b([BCD]\d+)\b"),
    re.compile(r"\bcl\.\s*([0-9,]+S?)"),
]


def _norm_spatii(t):
    """Spațiile fără întrerupere (SPEC §E.2) devin spații obișnuite pentru comparația V80/V81."""
    return re.sub(r"[   ]", " ", t or "")


def _numere(t):
    """Mulțimea valorilor numerice dintr-un text (comparația V80/V81, SPEC §E.1 pct. 3–4)."""
    return {float(x.replace(",", ".")) for x in re.findall(_NUM, _norm_spatii(t))}


def prima_diferenta(text, text_model):
    """Prima valoare numerică din `text` care nu corespunde modelului: (fragment_text, fragment_model) sau None.
    Se compară pe tipare etichetate (In, Ir, TC p/5, Icu, kVA …), apoi mulțimea numerelor (SPEC §E.1, V80/V81)."""
    a, b = _norm_spatii(text), _norm_spatii(text_model)
    for tip in _TIPARE:
        va = [(m.group(0), m.group(1)) for m in tip.finditer(a)]
        vb = [(m.group(0), m.group(1)) for m in tip.finditer(b)]
        if not va or not vb:
            continue
        valori_b = {x[1].replace(",", ".") for x in vb}
        for frag, v in va:
            if v.replace(",", ".") not in valori_b:
                return frag.strip(), vb[0][0].strip()
    na, nb = _numere(a), _numere(b)
    lipsa = sorted(na - nb)
    if lipsa:
        return fmt_ro(lipsa[0]), "—"
    return None


def verifica_aparat(ref, tip, parametri, text_lista_stocat=None, text_desen_stocat=None):
    """SPEC §E.1 pct. 3 și V80: regenerează textele din parametri și le compară cu cele stocate.
    Returnează (lista_regenerata, desen_regenerat, rezultat_V80 | None)."""
    den, car = text_lista(tip, parametri)
    lista = f"{den}, {car}"
    desen = f" {PUNCT} ".join(text_desen(tip, parametri))
    for stocat, regen in ((text_lista_stocat, lista), (text_desen_stocat, desen)):
        if stocat is None:
            continue
        d = prima_diferenta(stocat, regen)
        if d is not None:
            v80 = {"cod": "V80", "nivel": "BLOCANT", "obiect": ref,
                   "mesaj": f"{ref}: lista „{d[0]}” ≠ parametri „{d[1]}”",
                   "remediere": "regenerarea listei din parametri (textul stocat se înlocuiește)"}
            return lista, desen, v80
    return lista, desen, None


def verifica_nota(k, text, text_model):
    """SPEC §E.1 pct. 4 și V81: o notă editată manual care conține valori diferite de model → BLOCANT."""
    d = prima_diferenta(text, text_model)
    if d is None:
        return None
    return {"cod": "V81", "nivel": "BLOCANT", "obiect": f"nota {k}",
            "mesaj": f"nota {k}: „{d[0]}” ≠ model „{d[1]}”", "remediere": "regenerarea notelor din model"}


# ------------------------------------------------------------------------------------------------------------
# v1.3 (P0-2, pct. 5): curățarea mesajelor — pluralul după număr și persoana a II-a singular (ca în interfață)
# ------------------------------------------------------------------------------------------------------------
import re as _re

_SINGULAR = {"electrozi": "electrod", "plecări": "plecare", "circuite": "circuit", "invertoare": "invertor",
             "stringuri": "string", "module": "modul", "sisteme": "sistem", "cabluri": "cablu", "bucăți": "bucată",
             "conductoare": "conductor", "îmbinări": "îmbinare"}
_RE_SINGULAR = _re.compile(r"(?<![\d,.])\b1 (" + "|".join(_SINGULAR) + r")\b")
_IMPERATIV = {"introduceți": "introdu", "verificați": "verifică", "alegeți": "alege", "cereți": "cere",
              "confirmați": "confirmă", "declarați": "declară", "acceptați": "acceptă", "înlocuiți": "înlocuiește",
              "îmbunătățiți": "îmbunătățește", "reduceți": "redu", "măsurați": "măsoară", "limitați": "limitează",
              "solicitați": "solicită", "măriți": "mărește", "folosiți": "folosește", "adăugați": "adaugă",
              "mutați": "mută", "schimbați": "schimbă", "separați": "separă", "utilizați": "utilizează",
              "completați": "completează", "consultați": "consultă", "regenerați": "regenerează", "corectați": "corectează",
              "împărțiți": "împarte", "montați": "montează", "prevedeți": "prevede", "cereti": "cere"}
_RE_IMPERATIV = _re.compile(r"\b(" + "|".join(_IMPERATIV) + r")\b", _re.IGNORECASE)


def curata_text(t):
    """Singularul după „1” („1 electrozi” → „1 electrod”) și imperativul la persoana a II-a singular
    („verificați” → „verifică”), păstrând majuscula inițială."""
    if not isinstance(t, str) or not t:
        return t
    t = _RE_SINGULAR.sub(lambda m: "1 " + _SINGULAR[m.group(1)], t)

    def imp(m):
        w = m.group(1)
        r = _IMPERATIV[w.lower()]
        return r[0].upper() + r[1:] if w[0].isupper() else r
    return _RE_IMPERATIV.sub(imp, t)
