"""ramura.py — lanțul de dimensionare al unei ramuri (SPEC §B.0–§B.22, ordinea pașilor din §B.21).

O ramură = aparat de protecție + cablul protejat + sarcina de la capăt. Se calculează cu contextul de amonte
(valorile la bara de origine, SPEC §B.1).

API:
    calculeaza_ramura(ramura, context, jurnal, obiect, amonte=None, obiect_sel=None, bmpt_sel=False) -> dict
        {"rezultat": {...forma 'asteptat' din cazuri_golden.json...}, "prot": {...}, "ctx_aval": {...},
         "blocat": bool, "Ib": float, "Ip": float|None}
"""
import math

from . import norme
from . import cabluri as cb
from . import protectii as pr
from . import scurtcircuit as sc
from . import ddr as ddr_mod
from .comun import ge, gt, lt, u_calcul
from .texte import fmt_ro, text_cablu
from .verificari import emite, BLOCANT, AVERTISMENT, INFO

FALLBACK = [(None, "XLPE"), ("Cu", "PVC"), ("Cu", "XLPE")]
PORNIRE_TXT = {"directa": "directă", "stea_triunghi": "stea-triunghi", "soft": "soft-starter", "vfd": "VFD"}


def limita_du(receptor, origine):
    """SPEC §B.12, limitele ΔU: iluminat 3/6 %, forță/prize/motor 5/8 % (V20 BLOCANT); bara unui tablou secundar
    = limita de forță − 2 % (V21 AVERTISMENT, DECIZIE); invertor/PCS → PCC 1 % (V21 AVERTISMENT)."""
    pt = origine == "pt_propriu"
    if receptor in ("invertor", "pcs"):
        return norme.DU_CEF_CA_RECOMANDAT_PCT, "V21"
    if receptor == "iluminat":
        return norme.DU_MAX_PCT[("pt_propriu" if pt else "retea_publica", "iluminat")], "V20"
    forta = norme.DU_MAX_PCT[("pt_propriu" if pt else "retea_publica", "forta")]
    if receptor == "tablou":
        return forta - norme.DU_REZERVA_CIRCUITE_FINALE_PCT, "V21"
    return forta, "V20"


def limita_du_max(receptor, origine):
    """SPEC §B.12 (v1.2): limita peste care ΔU devine BLOCANT pentru ramurile cu limită de AVERTISMENT: bara unui tablou
    → limita I7 de forță (5 % / 8 %); invertor/PCS → 3 % (mărire automată până la această valoare). Altfel None."""
    if receptor in ("invertor", "pcs"):
        return norme.DU_CEF_CA_MAX_PCT
    if receptor == "tablou":
        return norme.DU_MAX_PCT[("pt_propriu" if origine == "pt_propriu" else "retea_publica", "forta")]
    return None


def idn_aval_tt(idn):
    """IΔn al DDR-urilor din aval, selectiv față de un DDR S de IΔn dat: ≤ IΔn/3 (dacă nu există, aceeași treaptă)."""
    return next((x for x in (300, 100, 30) if 3 * x <= idn), idn)


def prag_pornire(tip, In, curba):
    """SPEC §B.3.1 (v1.2): curentul sub care protecția NU declanșează în timpul pornirii motorului: gG → poarta
    Imin(10 s) din SR EN 60269-1; MCB → pragul instantaneu inferior (B 3·In, C 5·In, D 10·In); MCCB TM → 0,8·Im;
    electronic / ACB → 0,8·Ii. None dacă nu e tabelat."""
    if tip == "gG":
        porti = norme.GG_PORTI_A.get(In)
        return float(porti[0]) if porti else None
    if tip == "MCB":
        return {"B": 3.0, "C": 5.0, "D": 10.0}.get(curba or "C", 5.0) * In
    if tip in ("MCCB", "ACB"):
        if pr.declansator(tip, In) == "TM":
            return 0.8 * norme.IM_TM_MULTIPLU * In
        return 0.8 * 12.0 * In
    return None


def _blocat(ib=None):
    """Rezultatul unei ramuri oprite de un BLOCANT (SPEC §B.21: „⇒ STOP ramura”)."""
    rez = {"blocat": True}
    if ib is not None:
        rez["Ib_A"] = ib
    return {"rezultat": rez, "prot": None, "ctx_aval": None, "blocat": True, "Ib": ib, "Ip": None}


def valideaza(r, cablu, j, obiect):
    """SPEC §B.2, validările prealabile (prima care pică oprește ramura): cosφ ∉ (0;1] → V08; L ≤ 0 → V09 (L > 1000 m
    → V09 AVERTISMENT); P ≤ 0 → V07; ks ∉ (0;1] → V10. Returnează False dacă ramura se oprește."""
    cosfi = r.get("cosfi")
    if cosfi is not None:
        if not (0 < cosfi <= 1):
            emite(j, "V08", BLOCANT, obiect, "B", x=cosfi)
            return False
        if cosfi < 0.7:
            emite(j, "V08", AVERTISMENT, obiect, "AV", x=cosfi)
    L = cablu.get("L")
    if L is not None:
        if L <= 0:
            emite(j, "V09", BLOCANT, obiect, "B", L=L)
            return False
        if L > 1000:
            emite(j, "V09", AVERTISMENT, obiect, "AV", L=L)
    sarcini = [r.get(k) for k in ("P_kW", "In_A", "S_kVA", "Pn_kW", "Ib_A")]
    if all(v is None for v in sarcini):
        emite(j, "V07", BLOCANT, obiect, "lipsa")
        return False
    for k in ("P_kW", "S_kVA", "Pn_kW", "In_A", "Ib_A"):
        if r.get(k) is not None and r[k] <= 0:
            emite(j, "V07", BLOCANT, obiect, P=r[k])
            return False
    ks = r.get("ks")
    if ks is not None and not (0 < ks <= 1):
        emite(j, "V10", BLOCANT, obiect, parametru=f"ks = {fmt_ro(ks)}", tabel="IEC 61439-2 tab. 101")
        return False
    return True


def calculeaza_ramura(r, ctx, j, obiect, amonte=None, obiect_sel=None, bmpt_sel=False):
    """SPEC §B.21: pașii 1–16 pentru o ramură, cu contextul de amonte `ctx` (SPEC §B.1)."""
    retea = r.get("retea", "tri")
    receptor = r.get("receptor", "forta")
    rol = r.get("rol", "final")
    cin = dict(r.get("cablu") or {})
    if cin.get("n_fortat") is None and cin.get("S_fortat") is not None:
        # r7 (#7, S9): cablul impus „2 cabluri în paralel” — `n_paralel` (sau `n`) pe dicționarul cablului = n_fortat
        n_al = cin.get("n_paralel", cin.get("n"))
        if n_al is not None and not isinstance(n_al, bool) and float(n_al).is_integer() and n_al >= 1:
            cin["n_fortat"] = int(n_al)
    are_aval = bool(r.get("are_aval", False))
    metoda_explicita = cin.get("metoda") is not None and not cin.get("metoda_implicit")
    invertor = receptor in ("invertor", "pcs")

    # ---- 1. validări B.2 -------------------------------------------------------------------------------------
    if not r.get("_validat") and not valideaza(r, cin, j, obiect):
        return _blocat()

    # valorile implicite B.0
    metoda = cin.get("metoda") or ("C" if rol == "final" else "D1")
    material = cin.get("material")
    mat_implicit = cin.get("material_implicit", material is None)
    if material is None:
        material = "Al" if metoda in norme.METODE_IN_PAMANT else "Cu"
    izolatie = cin.get("izolatie") or "PVC"
    if cin.get("izolatie") is None:
        j.presupune("izolație PVC (Iz mai mic, conservator)")
    theta = cin.get("theta")
    if theta is None:
        theta = cb.theta_implicit(metoda)
        j.presupune("temperatura de referință: aer 30 °C, sol 20 °C")
    rho = cin.get("rho_sol")
    if rho is None:
        rho = 2.5
        if metoda in norme.METODE_IN_PAMANT:
            j.presupune("rezistivitatea termică a solului 2,5 K·m/W (sol uscat, conservator)")
    n_alte = int(cin.get("n_alte") or 0)
    L = cin.get("L")
    if L is None:
        L = 50.0
        j.presupune("lungime 50 m", obiect)
    L = float(L)
    c = {"material": material, "izolatie": izolatie, "metoda": metoda, "retea": retea, "theta": theta,
         "rho_sol": rho, "n_alte": n_alte, "distanta": cin.get("distanta", "atingere"),
         "aranjament": cin.get("aranjament")}
    j.ipoteza("pozare", (metoda, theta, rho if metoda in norme.METODE_IN_PAMANT else None, n_alte + 1),
              cin.get("metoda") is None)

    # ---- 2. Ib, Ip,min (B.2) ------------------------------------------------------------------------------------
    U = u_calcul(retea)
    cos_dat = r.get("cosfi")
    cosfi = cos_dat if cos_dat is not None else norme.COSFI_IMPLICIT.get(receptor, 0.9)
    eta_m = None
    motor_p = (receptor == "motor" and r.get("P_kW") is not None and r.get("Ib_A") is None and r.get("In_A") is None
               and r.get("S_kVA") is None)
    if motor_p:
        # r7 (S8): In motor = P/(√3·U·η·cosφ) — η și cosφ tipice IE3 4 poli pe treaptă de putere (norme.MOTOR_IE3_4P),
        # dacă fișa nu le dă; fără η, Ib (și releul termic reglat la Ib) ieșea cu 8–12 % sub curentul real
        eta0, cos0 = norme.motor_eta_cosfi(float(r["P_kW"]))
        eta_m = float(r.get("randament") or eta0)
        if cos_dat is None:
            cosfi = cos0
        if r.get("randament") is None or cos_dat is None:
            j.presupune(f"motor {fmt_ro(r['P_kW'])} kW: η {fmt_ro(eta_m, 3)}, cosφ {fmt_ro(cosfi, 2)} — valori tipice IE3 4 poli "
                        f"(SR EN IEC 60034-30-1); se înlocuiesc cu datele de pe plăcuța motorului", obiect)
    elif cos_dat is None and not invertor:
        j.presupune(f"cosφ {fmt_ro(cosfi)} ({'motor' if receptor == 'motor' else 'forță, iluminat, prize, tablou'})")
    ks = r.get("ks", 1.0) or 1.0
    in_dat = r.get("In_A")
    if invertor:
        pn = float(r["Pn_kW"])
        iac = r.get("Iac_max_A") or norme.FACTOR_SMAX_INVERTOR * pn * 1000.0 / U
        ib = float(iac)
        ip_min = max(ib, norme.FACTOR_IP_INVERTOR * pn * 1000.0 / U)
        cosfi = 1.0
        u_txt = "(√3·400)" if retea == "tri" else "230"
        j.pas(f"{obiect}: Ib = Iac,max = 1,1·{fmt_ro(pn)}·1000/{u_txt} = {fmt_ro(ib)} A; "
              f"Ip,min = max(Ib; 1,25·Pn/U = {fmt_ro(norme.FACTOR_IP_INVERTOR * pn * 1000.0 / U)}) = {fmt_ro(ip_min)} A")
    elif r.get("Ib_A") is not None:
        ib = float(r["Ib_A"])
        ip_min = ib
        j.pas(f"{obiect}: Ib dat = {fmt_ro(ib)} A (cosφ {fmt_ro(cosfi)} pentru ΔU)")
    elif in_dat is not None:
        ib = float(in_dat)
        ip_min = ib
        j.pas(f"{obiect}: plecare dată prin calibru {fmt_ro(in_dat)} A → Ib presupus = In = {fmt_ro(ib)} A")
        j.presupune("Ib presupus = In (plecare dată prin calibru)", obiect)
    elif r.get("S_kVA") is not None:
        ib = float(r["S_kVA"]) * 1000.0 / U
        ip_min = ib
        j.pas(f"{obiect}: S = {fmt_ro(r['S_kVA'])} kVA → Ib = {fmt_ro(ib)} A")
    elif eta_m is not None:
        pc = ks * float(r["P_kW"])
        ib = pc * 1000.0 / (U * eta_m * cosfi)
        ip_min = ib
        j.pas(f"{obiect}: motor P = {fmt_ro(pc)} kW → In = P/({'√3·400' if retea == 'tri' else '230'}·η·cosφ) = "
              f"{fmt_ro(pc)}·1000/({fmt_ro(U, 1)}·{fmt_ro(eta_m, 3)}·{fmt_ro(cosfi, 2)}) = {fmt_ro(ib)} A")
    else:
        pc = ks * float(r["P_kW"])
        ib = pc * 1000.0 / (U * cosfi)
        ip_min = ib
        j.pas(f"{obiect}: Pc = {fmt_ro(ks)}·{fmt_ro(r['P_kW'])} = {fmt_ro(pc)} kW → Ib = {fmt_ro(ib)} A "
              f"(cosφ {fmt_ro(cosfi)})")
    inm = r.get("In_minim")
    if inm is not None and gt(inm, ip_min):
        # v1.4 (§C.8): calibrul minim uzual al circuitului (ex. prize C16), chiar dacă Ib e mai mic
        ip_min = float(inm)
        j.pas(f"{obiect}: Ip,min = calibrul minim uzual {fmt_ro(inm)} A")
    extra = r.get("Ip_min_extra")
    if extra is not None and gt(extra, ip_min):
        ip_min = float(extra)
        j.pas(f"{obiect}: Ip,min ridicat peste aval max {fmt_ro(extra - 0.01)} A")

    # ---- 3–4. tip protecție, In, Ir, Icu (B.3–B.5) ----------------------------------------------------------------
    tip_f = pr.normalizeaza_tip(r.get("prot_tip"))
    in_f = r.get("In_fortat", in_dat)
    ref = in_f if in_f is not None else ip_min
    tip = tip_f or pr.tip_implicit(rol, receptor, ref)
    serie = r.get("serie_In") or pr.SERII[tip]
    if in_f is not None:
        if in_f not in serie:
            jos, sus = _vecini(serie, in_f)
            emite(j, "V05", BLOCANT, obiect, In=in_f, tip=tip, vecini=f"{jos} A / {sus} A")
            return _blocat(ib)
        In = in_f
    else:
        In = None
        if not gt(ip_min, pr.IN_MAX_ABSOLUT):
            In = pr.alege_calibru(tip, ip_min, serie)
        if In is None:
            emite(j, "V06", BLOCANT, obiect, Ib=ib, tip=tip)
            return _blocat(ib)
    curba = r.get("curba") or pr.curba_implicita(receptor)
    # SPEC §B.3.1 (v1.2): motor cu pornire directă — protecția trebuie să suporte Ip = k·Ib timp de tp
    pornire = r.get("pornire") or ("directa" if receptor == "motor" else None)
    k_porn = norme.MOTOR_IP_MULTIPLU.get(pornire, 0.0) if receptor == "motor" else 0.0
    ip_porn = k_porn * ib if k_porn > 1.0 else None
    motor_v23 = None
    if ip_porn is not None and tip == "gG" and tip_f is None and in_f is None:
        # pornire directă fără tip impus: întreruptor MCCB TM (motor) în locul siguranțelor gG — pragul magnetic
        # 0,8·10·In ≥ 6·Ib, iar cablul rămâne dimensionat la Ir (fără supradimensionarea cerută de gG la pornire)
        tip = "MCCB"
        serie = r.get("serie_In") or pr.SERII[tip]
        In = pr.alege_calibru(tip, ip_min, serie)
        if In is None:
            emite(j, "V06", BLOCANT, obiect, Ib=ib, tip=tip)
            return _blocat(ib)
        j.pas(f"{obiect}: motor cu pornire {PORNIRE_TXT.get(pornire, pornire)} → MCCB (întreruptor-motor) în loc de gG")
    motor_ma = False
    p_motor = r.get("P_kW")
    if (ip_porn is not None and pornire == "directa" and tip == "MCB" and tip_f is None and in_f is None
            and ((p_motor is not None and ge(float(p_motor), norme.MOTOR_DOL_P_MIN_INTRERUPATOR_MOTOR_KW))
                 or gt(ip_min, 63.0))):
        # r6 (#12, #21): motor DOL ≥ 18,5 kW pe MCB curba C — vârful asimetric de la pornire (≈ 2·Ip pornire ≈ 12·Ib)
        # depășește banda magnetică a curbei C (5…10·In) → întrerupător-motor / MCCB cu declanșator magnetic pentru
        # motoare (Im ≈ 13·In, reglaj termic = Ib) + contactor + releu termic (SR EN 60947-4-1)
        tip = "MCCB"
        motor_ma = True
        serie = r.get("serie_In") or pr.SERII[tip]
        In = pr.alege_calibru(tip, ip_min, serie)
        if In is None:
            emite(j, "V06", BLOCANT, obiect, Ib=ib, tip=tip)
            return _blocat(ib)
        j.pas(f"{obiect}: motor {fmt_ro(p_motor) + ' kW ' if p_motor is not None else ''}cu pornire directă → "
              f"întrerupător-motor (MCCB, magnetic {fmt_ro(norme.MOTOR_IM_MULTIPLU)}·In) în loc de MCB curba C")

    def prag_motor(x):
        """Pragul de nedeclanșare la pornire: întrerupătorul-motor e verificat la vârful asimetric."""
        if motor_ma:
            return 0.8 * norme.MOTOR_IM_MULTIPLU * x / norme.MOTOR_VARF_ASIMETRIC
        return prag_pornire(tip, x, curba)

    if ip_porn is not None:
        prag = prag_motor(In)
        if prag is None or lt(prag, ip_porn):
            if in_f is None:
                for x in sorted(serie):
                    if x < In:
                        continue
                    pg = prag_motor(x)
                    if pg is not None and ge(pg, ip_porn):
                        j.pas(f"{obiect}: pornire {PORNIRE_TXT.get(pornire, pornire)}: Ip = {fmt_ro(k_porn)}·Ib = {fmt_ro(ip_porn)} A > prag "
                              f"{fmt_ro(prag) if prag is not None else '—'} A al {tip} {fmt_ro(In)} A → calibru {fmt_ro(x)} A "
                              f"(prag {fmt_ro(pg)} A)")
                        In = x
                        motor_v23 = ("INFO", pg)
                        break
                else:
                    motor_v23 = ("AV", prag)
            else:
                motor_v23 = ("AV", prag)
        else:
            motor_v23 = ("INFO", prag)
    prot = pr.construieste(tip, In, ip_min, curba, are_aval)
    if motor_ma:
        prot["Im_A"] = norme.MOTOR_IM_MULTIPLU * In
        prot["intrerupator_motor"] = True
        j.pas(f"{obiect}: vârf asimetric la pornire ≈ {fmt_ro(norme.MOTOR_VARF_ASIMETRIC)}·Ip = "
              f"{fmt_ro(norme.MOTOR_VARF_ASIMETRIC * ip_porn)} A ≤ 0,8·Im = {fmt_ro(0.8 * prot['Im_A'])} A "
              f"(Im = {fmt_ro(norme.MOTOR_IM_MULTIPLU)}·In)" if ge(0.8 * prot["Im_A"], norme.MOTOR_VARF_ASIMETRIC * ip_porn)
              else f"{obiect}: vârf asimetric la pornire peste 0,8·Im — de confirmat cu producătorul")
    ik3o = ctx["Ik3_kA"]
    icu_f = r.get("Icu_fortat")
    if icu_f is not None:
        prot["Icu_kA"] = icu_f
        prot["Icu_fortat"] = True
    else:
        icu, ok = pr.alege_icu(tip, ik3o)
        if tip == "MCB" and not ok and not tip_f:
            tip = "MCCB"
            In = in_f if (in_f is not None and in_f in pr.SERII["MCCB"]) else pr.alege_calibru("MCCB", max(ip_min, in_f or 0))
            prot = pr.construieste(tip, In, ip_min, None, are_aval)
            icu, ok = pr.alege_icu(tip, ik3o)
            j.pas(f"{obiect}: Ik3max {fmt_ro(ik3o)} kA > 25 kA → MCCB în loc de MCB")
        prot["Icu_kA"] = icu
    Ip = pr.ip(prot)
    if tip in ("MCCB", "ACB"):
        j.pas(f"{obiect}: protecție {tip} In = {fmt_ro(In)} A, Ir = {fmt_ro(prot['Ir_multiplu'])}·In = {fmt_ro(Ip)} A")
    elif tip == "MCB":
        j.pas(f"{obiect}: protecție MCB {prot['curba']} In = {fmt_ro(In)} A")
    else:
        j.pas(f"{obiect}: protecție {tip} In = {fmt_ro(In)} A")
    if gt(ib, Ip):
        emite(j, "V04", BLOCANT, obiect, Ib=ib, Ip=Ip)
        return _blocat(ib)
    ddr_out = None
    ddr_tt = None
    ddr_f = r.get("ddr") if isinstance(r.get("ddr"), dict) else None
    if ddr_f is not None:
        # v1.3 (SPEC §B.18.1): DDR impus pe ramură {IdN_mA, selectiv, dt_s, tip} — de utilizator (se verifică, nu se
        # modifică) sau de motor (`_motor`: bloc diferențial reglabil pe intrarea TT, §C.2 pct. 13)
        idn_f = int(ddr_f["IdN_mA"])
        dt_f = ddr_f.get("dt_s")
        mare = In > norme.RCCB_IN_A[-1] or dt_f is not None
        d_f = ddr_mod.descriere(idn_f, bool(ddr_f.get("selectiv", False)), "", dt_f)
        ddr_out = {"IdN_mA": idn_f, "tip": ddr_f.get("tip") or "A",
                   "In_A": In if mare else (pr.prima_din_serie(norme.RCCB_IN_A, max(In, 16 if retea == "mono" else 25)) or In),
                   "poli": "2P" if retea == "mono" else "4P", "aparat": "bloc_diferential" if mare else "RCCB",
                   "selectiv": d_f["selectiv"], "temporizare": d_f["temporizare"]}
        if dt_f is not None:
            ddr_out.update({"dt_s": float(dt_f), "reglabil": True, "asociat": obiect.split("·")[0].split("/")[0]})
        if not ddr_f.get("_motor"):
            ddr_out["impus"] = True
        ctx = dict(ctx, ddr_ramura=f"DDR {idn_f} mA" + (" (impus)" if not ddr_f.get("_motor") else ""))
        if not r.get("_doar_protectie"):
            if receptor == "prize" and In <= 32 and not invertor and idn_f > 30:
                emite(j, "V29", BLOCANT, obiect, "B", In=In)
            if ctx.get("schema") == "TT":
                ra_c = ctx.get("RA_tt", 4.0)
                if gt(ra_c * idn_f / 1000.0, 50.0):
                    emite(j, "V34", BLOCANT, obiect, RA=ra_c, IdN=idn_f, x=ra_c * idn_f / 1000.0)
                ddr_tt = idn_f
    elif receptor == "prize" and In <= 32 and not invertor:
        # SPEC §C.2 pct. 10 (v1.2: orice plecare sau circuit final de prize ≤ 32 A): DDR 30 mA tip A obligatoriu
        # (SR HD 60364-4-41 art. 411.3.3); DDR refuzat explicit → V29 BLOCANT
        if r.get("ddr") is False:
            if not r.get("_doar_protectie"):
                emite(j, "V29", BLOCANT, obiect, "B", In=In)
        else:
            # RCCB 4P se fabrică de la 25 A (16 A doar 2P)
            ddr_out = {"IdN_mA": 30, "tip": "A", "In_A": pr.prima_din_serie(norme.RCCB_IN_A, max(In, 1 if retea == "mono" else 25)) or In,
                       "poli": "2P" if retea == "mono" else "4P"}
            ctx = dict(ctx, ddr_ramura="DDR 30 mA tip A")
            j.pas(f"{obiect}: circuit de prize ≤ 32 A → DDR 30 mA tip A")
            if not r.get("_doar_protectie"):
                emite(j, "V29", INFO, obiect, "INFO", In=In)
    if ddr_out is None and ctx.get("schema") == "TT" and rol in ("plecare", "final", "intrare", "invertor"):
        # v1.2 R2 (N-C2, SR HD 60364-4-41 art. 411.5): în TT fiecare circuit are DDR propriu cu RA·IΔn ≤ 50 V
        idn = ctx.get("idn_tt_mA")
        sus = ctx.get("ddr_sus")
        if r.get("ddr") is False:
            if not r.get("_doar_protectie"):
                emite(j, "V34", BLOCANT, obiect, "lipsa")
        elif are_aval and sus and rol in ("plecare", "intrare"):
            # v1.3 R5 (SPEC §C.2 pct. 13, M5-4): intrarea tabloului și alimentările tablourilor secundare NU primesc DDR
            # propriu — sunt protejate de DDR-ul temporizat din amonte (RA·IΔn ≤ 50 V verificat acolo); un al doilea
            # DDR temporizat în serie nu ar fi selectiv. Circuitele din aval primesc DDR instantaneu.
            ctx = dict(ctx, ddr_ramura=f"DDR {sus['IdN_mA']} mA din amonte ({sus['denumire']})")
            j.pas(f"{obiect}: TT — fără DDR propriu, protejat de {sus['denumire']} {sus['IdN_mA']} mA"
                  f"{' (' + sus['temporizare'] + ')' if sus.get('temporizare') else ''}; circuitele din aval: DDR "
                  f"{idn} mA instantaneu")
        elif idn:
            mare = In > norme.RCCB_IN_A[-1]
            ddr_out = {"IdN_mA": idn, "tip": "A",
                       "In_A": In if mare else (pr.prima_din_serie(norme.RCCB_IN_A, max(In, 16 if retea == "mono" else 25)) or In),
                       "poli": "2P" if retea == "mono" else "4P", "aparat": "bloc_diferential" if mare else "RCCB",
                       "selectiv": False, "temporizare": "instantaneu"}
            if mare:
                ddr_out["asociat"] = obiect.split("·")[0]
            ctx = dict(ctx, ddr_ramura=f"DDR {idn} mA (TT)")
            ddr_tt = idn
            j.pas(f"{obiect}: schema TT → DDR {idn} mA instantaneu pe circuit (RA·IΔn ≤ 50 V)")
    if r.get("_doar_protectie"):
        # SPEC §C.2 pct. 4: protecțiile plecărilor se calculează întâi (doar Ip; nu depind de bara TG)
        return {"rezultat": None, "prot": prot, "ctx_aval": None, "blocat": False, "Ib": ib, "Ip": Ip}
    # v1.3 (SPEC §B.18.1): selectivitatea DDR-ului ramurii față de cel mai apropiat DDR din amonte
    ddr_sus_aval = ctx.get("ddr_sus")
    if ddr_out:
        d_aici = ddr_mod.descriere(ddr_out["IdN_mA"], ddr_out.get("selectiv"), f"DDR {obiect}", ddr_out.get("dt_s"))
        if ctx.get("ddr_sus"):
            ddr_mod.verifica(j, ctx["ddr_sus"], d_aici, obiect,
                             RA_ohm=ctx.get("RA_tt") if ctx.get("schema") == "TT" else None)
        ddr_sus_aval = d_aici
    if r.get("_cosfi_eticheta"):
        # v1.7 (§C.8, N13): locuința — cosφ din tabelul receptorului (presupus) sau declarat, cu eticheta receptorului
        j.ipoteza("cosfi", (cosfi, r["_cosfi_eticheta"]), bool(r.get("_cosfi_implicit")))
    else:
        j.ipoteza("cosfi", (cosfi, "invertor" if invertor else ("motor" if receptor == "motor" else "forță/iluminat/prize/tablou")
                             if cos_dat is None else "declarat"), cos_dat is None and not invertor)
    j.ipoteza("origine", ctx["origine"], False)

    # ---- 5. I2, Iz_min (B.6, B.10 pct. 5–6) -------------------------------------------------------------------------
    I2 = pr.i2(prot)
    iz_min = max(Ip, I2 / 1.45)
    h3 = r.get("h3_pct", r.get("h3"))
    if h3 is not None and retea == "tri":
        if 15 < h3 <= 33:
            iz_min = iz_min / 0.86
        elif h3 > 33:
            i_n = 3.0 * h3 / 100.0 * ib
            iz_min = max(iz_min, i_n / 0.86 if h3 <= 45 else i_n)
            # SR HD 60364-4-43 art. 431.2.3: curentul din neutru > curentul de fază → detecția supracurentului în N
            emite(j, "V24", AVERTISMENT, obiect, h3=h3)
    j.pas(f"{obiect}: I2 = {fmt_ro(I2)} A → Iz' ≥ max(Ip; I2/1,45) = {fmt_ro(iz_min)} A")

    lim, cod_lim = r.get("limita_dU") or limita_du(receptor, ctx["origine"])
    lim_max = limita_du_max(receptor, ctx["origine"]) if r.get("limita_dU") is None else None
    # v1.3 (P0-2): la invertoare ΔU se cumulează cu ΔU pe C0 (TGD-CF → punctul de racord), dacă există
    du0 = ctx.get("dU_cef_pct", 0.0) if invertor else ctx["dU_pct"]

    def du(cc, n, S):
        """ΔU pe ramură [%] cu Ib, nu cu Ip (SPEC §B.12)."""
        return cb.du_pct(retea, ib, L, cc["material"], cc["izolatie"], S, n, cosfi)

    def smin(mat):
        """Secțiunea minimă pentru material (SPEC §B.8)."""
        s0 = cb.s_min(mat, receptor, metoda)
        # v1.4: secțiune minimă cerută pe receptor (ex. plită mono / VE 6 mm² Cu la locuințe, §C.8)
        if cin.get("S_min") is not None and mat == "Cu":
            s0 = max(s0, float(cin["S_min"]))
        # v1.5 (§C.8): receptoare fixe ≤ 10 A ale locuinței (centrală, poartă) — 1,5 mm² Cu admis (I7-2011)
        if cin.get("S_min_fix") is not None and mat == "Cu" and metoda not in norme.METODE_IN_PAMANT:
            s0 = float(cin["S_min_fix"])
        return s0

    plafon = [False]

    def creste_du(cc, n, S):
        """SPEC §B.12, mărirea automată pentru ΔU (S, apoi n), dacă S nu e impusă și receptorul nu e invertor/PCS."""
        marit = False
        tinta = lim_max if invertor else lim      # invertor/PCS: mărire doar peste 3 % (v1.2), 1 % rămâne recomandare
        if r.get("tinta_dU") is not None and not invertor:
            # v1.6 (§C.8, N2): ținta de mărire mai strictă decât limita (bugetul coloanei locuinței); limita V20/V21
            # rămâne cea normată
            tinta = min(tinta, float(r["tinta_dU"]))
        if r.get("tinta_dU_ramura") is not None and not invertor:
            # r8 (P0 #46): bugetul ΔU al RAMURII (alimentarea unui tablou secundar al locuinței) — relativ la ΔU deja
            # cumulat la origine, nu o țintă absolută: cumulat ≤ max(limita, origine + buget), dar ≤ limita max − 1 %
            # (rămâne loc circuitelor din tabloul secundar). Înainte, 1,5 % absolut sub 2,2 % la origine creștea
            # cablul până la 4 × 3×240 mm² pentru 17 A.
            sus = (lim_max - 1.0) if lim_max is not None else tinta + float(r["tinta_dU_ramura"])
            tinta = min(max(tinta, du0 + float(r["tinta_dU_ramura"])), max(sus, tinta))
        sect = cb.sectiuni(cc)
        s_max = r.get("S_max_dU")
        while gt(du0 + du(cc, n, S), tinta):
            i = sect.index(S)
            if s_max is not None and (i + 1 >= len(sect) or gt(sect[i + 1], float(s_max))):
                # v1.7 (§C.8, m-c6): plafonul măririi pentru ΔU (circuitele finale ale locuinței) — fără paralel
                plafon[0] = True
                break
            if i + 1 < len(sect):
                S = sect[i + 1]
            elif n < cb.n_max(cc):
                S2 = cb.cea_mai_mica_s(cc, n + 1, iz_min, smin(cc["material"]))
                if S2 is None:
                    break
                n, S = n + 1, S2
            else:
                break
            marit = True
        return n, S, marit

    def solutie(cc):
        """SPEC §B.8: căutarea (n, S), apoi fallback (material, XLPE) → (Cu, PVC) → (Cu, XLPE); plus bucla ΔU."""
        sol = cb.cauta(cc, iz_min, smin(cc["material"]))
        schimb = None
        if sol is None:
            incercate = {(cc["material"], cc["izolatie"])}
            for m, iz in FALLBACK:
                m = m or cc["material"]
                if (m, iz) in incercate:
                    continue
                incercate.add((m, iz))
                c2 = dict(cc, material=m, izolatie=iz)
                sol = cb.cauta(c2, iz_min, smin(m))
                if sol is not None:
                    schimb = (cc["material"], cc["izolatie"], m, iz)
                    cc = c2
                    break
        if sol is None and retea == "tri" and not cb.monopolar(cc):
            # v1.2 R2/R3 (N-M5, N3-C1): curenți mari — sisteme de cabluri monopolare Cu XLPE în treflă, până la 6 pe
            # fază. Metoda cerută explicit în pământ (D1/D2) se păstrează (Iz și grupare din tabelele metodei, fiecare
            # treflă = un circuit); metoda în aer cerută (C/E) sau implicită → pat de cabluri în aer, metoda F.
            if metoda_explicita and cc["metoda"] in norme.METODE_IN_PAMANT:
                cF = dict(cc, material="Cu", izolatie="XLPE", monopolar=True)
            else:
                cF = dict(cc, material="Cu", izolatie="XLPE", metoda="F_trefla",
                          theta=cin.get("theta") if cin.get("theta") is not None else 30.0)
            sol = cb.cauta(cF, iz_min, 0.0)
            if sol is not None:
                schimb = (cc["material"], cc["izolatie"], "Cu", "XLPE", cF["metoda"])
                cc = cF
        if sol is None:
            return None
        n0, S0 = sol
        n, S, marit = creste_du(cc, n0, S0)
        return {"c": cc, "n": n, "S": S, "n0": n0, "S0": S0, "schimb": schimb, "marit_du": marit}

    # ---- 6–8. secțiune (B.7, B.8), Al→Cu, ΔU (B.12) ---------------------------------------------------------------
    S_f = cin.get("S_fortat")
    try:
        if S_f is not None:
            if float(S_f) not in cb.sectiuni(c):
                emite(j, "V13", BLOCANT, obiect, S=S_f, mat=material)
                return _blocat(ib)
            n = int(cin.get("n_fortat") or 1)
            S = float(S_f)
            st = {"c": c, "n": n, "S": S, "n0": n, "S0": S, "schimb": None, "marit_du": False}
        else:
            st = solutie(c)
            if st is None:
                emite(j, "V01", BLOCANT, obiect, Iz_min=iz_min)
                return _blocat(ib)
            if st["schimb"] and len(st["schimb"]) == 5:
                m0, i0 = st["schimb"][:2]
                met1 = st["schimb"][4]
                if met1.startswith("F"):
                    emite(j, "V45", AVERTISMENT, obiect, "F", mat=m0, iz=i0, n=st["n"], S=st["S"])
                    # N3-C1: trecerea în aer e o ipoteză de pozare — scrisă explicit în nota de ipoteze (G.2)
                    j.ipoteza("pozare_F", obiect, not metoda_explicita)
                    j.presupune("pozare pe pat de cabluri în aer, monopolare în treflă (metoda F, sisteme distanțate "
                                "≥ 2·De, tab. B.52.21) — multipolarele în pământ nu ajung; confirmați traseul", obiect)
                else:
                    emite(j, "V45", AVERTISMENT, obiect, "Fsol", mat=m0, iz=i0, n=st["n"], S=st["S"], met=met1)
                    j.presupune(f"sisteme de cabluri monopolare Cu XLPE în treflă, metoda {met1} (în pământ), fiecare treflă "
                                f"= un circuit la grupare", obiect)
                j.pas(f"{obiect}: cablurile multipolare nu ajung → {st['n']} sisteme monopolare Cu XLPE 1×{fmt_ro(st['S'])} "
                      f"mm² în treflă (metoda {met1})")
            elif st["schimb"]:
                m0, i0, m1, i1 = st["schimb"]
                emite(j, "V45", AVERTISMENT, obiect, mat=m0, iz=i0, mat2=m1, iz2=i1)
                j.pas(f"{obiect}: material/izolație schimbate → {m1} {i1}")
            if (mat_implicit and c["material"] == "Al" and not st["schimb"] and st["n"] == 1
                    and st["S"] == norme.S_MIN_AL):
                st_cu = solutie(dict(c, material="Cu"))
                if st_cu and st_cu["n"] == 1 and not st_cu["schimb"] and st_cu["S"] <= 10:
                    j.pas(f"{obiect}: Al ar rezulta < 16 mm² (Cu {fmt_ro(st_cu['S'])} mm² satisface Iz și ΔU) "
                          f"→ se trece pe Cu")
                    emite(j, "V48", INFO, obiect, S=st_cu["S"])
                    st = st_cu
        c = st["c"]
        n, S = st["n"], st["S"]
        iz0, k0, izp0 = cb.iz_corectat(c, st["n0"], st["S0"])
    except cb.InAfaraTabelelor as e:
        emite(j, "V10", BLOCANT, obiect, parametru=e.parametru, tabel=e.tabel)
        return _blocat(ib)
    metoda = c["metoda"]
    j.pas(f"{obiect}: {c['material']} {c['izolatie']} metoda {metoda}: k = {fmt_ro(k0, 4)}; "
          f"{st['n0']}×{fmt_ro(st['S0'])} mm² Iz = {fmt_ro(iz0)} A → Iz' = {fmt_ro(izp0)} A")
    if st["marit_du"]:
        j.pas(f"{obiect}: secțiune mărită pentru ΔU → {n}×{fmt_ro(S)} mm² (Iz' = {fmt_ro(cb.iz_corectat(c, n, S)[2])} A)")
    if S_f is not None:
        _, _, izp = cb.iz_corectat(c, n, S)
        if gt(Ip, izp):
            emite(j, "V02", BLOCANT, obiect, Ip=Ip, Iz=izp)
        if gt(I2, 1.45 * izp):
            emite(j, "V03", BLOCANT, obiect, I2=I2, lim=1.45 * izp)

    mat, izl = c["material"], c["izolatie"]
    N_f, PE_f, PE_loc_f = cin.get("N_fortat"), cin.get("PE_fortat"), cin.get("PE_loc")

    # ---- 9. N, PE (B.10, B.11) ----------------------------------------------------------------------------------------
    def compune(n, S, pe_cfg=None):
        """Compunerea N și PE pentru (n, S), cu valorile impuse (SPEC §B.10, §B.11, pasul 9 din §B.21)."""
        N, motiv = cb.compune_neutru(mat, S, retea, receptor, h3, N_f)
        if PE_loc_f == "PEN":
            # v1.2 R2 (N-M2): TN-C — conductorul PEN este neutrul cablului (4 conductoare, fără PE separat)
            return {"n": n, "S": S, "N": N, "motiv_N": motiv, "s_pe": N, "loc": "PEN", "s_tab": N}
        if PE_f is not None:
            loc = PE_loc_f or ("cablu" if cb.pe_in_cablu(mat, S, retea) else "separat")
            s_tab = cb.s_pe_tabel(mat, izl, n, S, loc == "separat")
            s_pe = float(PE_f)
        elif pe_cfg is not None:
            s_pe, loc = pe_cfg
            s_tab = cb.s_pe_tabel(mat, izl, n, S, loc == "separat")
        else:
            s_pe, loc, s_tab = cb.compune_pe(mat, izl, n, S, retea)
        return {"n": n, "S": S, "N": N, "motiv_N": motiv, "s_pe": s_pe, "loc": loc, "s_tab": s_tab}

    # ---- 10–12. Ik3, Ik1, Isd, Ia, deconectare (B.13–B.15) ------------------------------------------------------------
    schema = ctx.get("schema", "TN")
    t_cer = pr.timp_deconectare_cerut(receptor, Ip, schema)
    f_faza = norme.FACTOR_R_IK1MIN[izl]

    def evalueaza(cfg):
        """Iz', ΔU, Ik3/Ik1 la capăt, Isd, Ia și starea deconectării pentru o configurație (SPEC §B.7, §B.12–§B.15)."""
        n, S = cfg["n"], cfg["S"]
        iz_t, k, izp = cb.iz_corectat(c, n, S)
        dur = du(c, n, S)
        r20 = norme.R20_OHM_KM[mat][float(S)]
        zq = sc.z_capat(ctx["Zq"], r20, L, n)
        fpe = f_faza if cfg["loc"] in ("cablu", "PEN") else norme.FACTOR_R_IK1MIN["PVC"]
        zb = sc.zb_capat(ctx["Zb"], r20, f_faza, cb.r20_pe(mat, cfg["loc"], cfg["s_pe"]), fpe, L, n)
        ik1 = sc.ik1_din_zb(zb)
        if prot.get("decl") == "EL":
            pr.alege_isd(prot, ik1)
        ia_v = pr.ia(prot, t_cer)
        if ia_v is None and ctx.get("ddr_ramura") and schema == "TT":
            stare = "ddr_propriu"     # TT: deconectarea se face prin DDR (Ia doar informativ, §B.15)
        elif ia_v is None:
            stare = "ia_lipsa"
        elif ge(ik1, ia_v):
            stare = "ok"
        elif ctx.get("ddr_ramura"):
            stare = "ddr_propriu"
        elif ctx.get("ddr_amonte"):
            stare = "ddr_amonte"
        elif ctx.get("regim_ge"):
            stare = "regim_ge"
        elif ctx.get("z_implicit"):
            stare = "z_implicit"
        else:
            stare = "blocant"
        e = dict(cfg)
        e.update({"Iz_tab": iz_t, "k": k, "Izp": izp, "dU_r": dur, "dU_c": du0 + dur, "Zq": zq, "Zb": zb,
                  "Ik3c": sc.ik3_din_z(zq), "Ik1": ik1, "Ia": ia_v, "stare": stare})
        return e

    try:
        ev = evalueaza(compune(n, S))
        marit_deconectare = False
        if (ev["stare"] not in ("ok", "ia_lipsa") and not ctx.get("z_implicit") and S_f is None
                and not ctx.get("ddr_ramura") and not ctx.get("regim_ge")):
            sect = cb.sectiuni(c)
            for S2 in sect[sect.index(S) + 1:]:
                e2 = evalueaza(compune(n, S2))
                if e2["stare"] == "ok":
                    ev, marit_deconectare = e2, True
                    j.pas(f"{obiect}: secțiune mărită pentru deconectare → {n}×{fmt_ro(S2)} mm²")
                    break
            if not marit_deconectare:
                ev = evalueaza(compune(n, S))

        # ---- 14. stabilitatea termică a fazei (B.17) -------------------------------------------------------------------
        t3 = pr.t_ik3(prot, are_aval)
        v35 = None
        if tip in ("MCCB", "ACB"):
            need_f = ik3o * 1000.0 * math.sqrt(t3) / norme.K_FAZA[(mat, izl)]
            j.pas(f"{obiect}: termic fază la Ik3max (t = {fmt_ro(t3)} s): n·S ≥ {fmt_ro(need_f, 1)} mm²")
            if lt(ev["n"] * ev["S"], need_f):
                if S_f is not None:
                    v35 = ("B", need_f)
                elif ctx.get("ik3_implicit"):
                    v35 = ("AV", need_f)
                else:
                    S3 = next((s for s in cb.sectiuni(c) if ge(ev["n"] * s, need_f)), None)
                    if S3 is None:
                        v35 = ("B", need_f)
                    else:
                        ev = evalueaza(compune(ev["n"], S3))
                        v35 = ("INFO_marit", need_f)
            else:
                v35 = ("INFO", need_f)
        else:
            v35 = ("INFO", None)

        # ---- 14. stabilitatea termică a PE (B.11) ---------------------------------------------------------------------
        def necesar_pe(e):
            """Secțiunea PE necesară la Ik1min (t după B.17) și la Ik3max pentru MCCB/ACB (SPEC §B.11, §B.17)."""
            kp = cb.k_pe(mat, izl, e["loc"])
            t1 = pr.timp_termic(prot, e["Ik1"], e["stare"])
            n1 = e["Ik1"] * math.sqrt(t1) / kp
            if tip == "gG":
                # v1.2 R2 (N-M4): siguranța gG în zona limitatoare (Ik1 ≥ Imax(0,1 s)) — energia lăsată să treacă
                # I²t ≈ 2·I²t prearc max (SR EN 60269-2), nu Ik1²·0,1 s
                porti = norme.GG_PORTI_A.get(In)
                i2t = norme.GG_I2T_PREARC_KA2S.get(In)
                if porti and i2t and ge(e["Ik1"], porti[3]):
                    n1 = min(n1, math.sqrt(norme.GG_I2T_TOTAL_FACTOR * i2t[1] * 1e3) / kp)
            elif tip == "MCB" and prot.get("curba", "C") in ("B", "C") and e["Ia"] is not None and ge(e["Ik1"], e["Ia"]):
                # MCB clasa 3 (SR EN 60898-1 anexa ZA): I²t limitat în zona instantanee
                e_lim = norme.mcb_i2t(In, e["Ik1"])
                if e_lim is not None:
                    n1 = min(n1, math.sqrt(e_lim) / kp)
            n3 = ik3o * 1000.0 * math.sqrt(t3) / kp if tip in ("MCCB", "ACB") else 0.0
            return n1, n3, t1

        n1, n3, t1 = necesar_pe(ev)
        tot = ev["n"] * ev["s_pe"]
        v36 = ("INFO", max(n1, n3))
        if lt(tot, n1) or lt(tot, n3):
            f1, f3 = lt(tot, n1), lt(tot, n3)
            alt = None
            if ev["loc"] == "cablu" and S_f is None and PE_f is None and not (f3 and not f1 and ctx.get("ik3_implicit")):
                # v1.2 R2 (N-M4): Cu ≤ 35 mm² — PE rămâne în cablu (5×S, §B.11), se mărește secțiunea cablului
                for S4 in cb.sectiuni(c):
                    if S4 <= ev["S"] or not cb.pe_in_cablu(mat, S4, retea):
                        continue
                    e4 = evalueaza(compune(ev["n"], S4))
                    a1, a3, _ = necesar_pe(e4)
                    if e4["loc"] == "cablu" and ge(e4["n"] * e4["s_pe"], max(a1, a3)):
                        alt = e4
                        break
            if alt is not None:
                ev = alt
                n1, n3, t1 = necesar_pe(ev)
                v36 = ("INFO_marit_cablu", max(n1, n3))
            elif (S_f is not None and not r.get("_pe_liber")) or PE_f is not None or ev["loc"] == "PEN":
                v36 = ("B", max(n1, n3))
            elif f3 and not f1 and ctx.get("ik3_implicit"):
                v36 = ("AV", n3)
            else:
                kp = norme.K_PE_SEPARAT[("Cu", "PVC")]
                tinta = ev["Ik1"] * math.sqrt(t1) / kp
                n3s = ik3o * 1000.0 * math.sqrt(t3) / kp if tip in ("MCCB", "ACB") else 0.0
                if not ctx.get("ik3_implicit"):
                    tinta = max(tinta, n3s)
                s_nou = cb.sectiune_std_minima(tinta / ev["n"], max(ev["s_pe"], norme.S_MIN_PE_SEPARAT["neprotejat"]))
                if s_nou is None:
                    v36 = ("B", max(n1, n3))
                else:
                    ev = evalueaza(compune(ev["n"], ev["S"], (s_nou, "separat")))
                    n1, n3, t1 = necesar_pe(ev)
                    v36 = ("INFO_marit", tinta)
                    if lt(ev["n"] * ev["s_pe"], n3) and ctx.get("ik3_implicit"):
                        v36 = ("AV", n3)
    except cb.InAfaraTabelelor as e:
        emite(j, "V10", BLOCANT, obiect, parametru=e.parametru, tabel=e.tabel)
        return _blocat(ib)

    n, S = ev["n"], ev["S"]
    j.pas(f"{obiect}: ΔU = {fmt_ro(ev['dU_r'])} % (L = {fmt_ro(L, 0)} m); cumulat = {fmt_ro(du0)} + "
          f"{fmt_ro(ev['dU_r'])} = {fmt_ro(ev['dU_c'])} % (limită {fmt_ro(lim)} %)")
    j.pas(f"{obiect}: Ik3max la origine {fmt_ro(ik3o)} kA, la capăt {fmt_ro(ev['Ik3c'])} kA; Ik1min la capăt "
          f"{fmt_ro(ev['Ik1'])} A; Ia({fmt_ro(t_cer)} s) = {fmt_ro(ev['Ia']) if ev['Ia'] is not None else '—'} A")
    t3_txt = (f"; la Ik3max {fmt_ro(ik3o)} kA (t = {fmt_ro(t3)} s): S ≥ {fmt_ro(n3, 1)} mm²" if n3 > 0 else "")
    j.pas(f"{obiect}: N = {fmt_ro(ev['N'])} mm², PE = {fmt_ro(ev['s_pe'])} mm² ({ev['loc']}); termic PE: "
          f"la Ik1min {fmt_ro(ev['Ik1'], 0)} A (t = {fmt_ro(t1)} s): S ≥ {fmt_ro(n1, 1)} mm²{t3_txt} "
          f"→ necesar {fmt_ro(max(n1, n3), 1)} mm²")

    # ---- emiterea verificărilor pașilor 8–14, pe configurația finală ---------------------------------------------------
    if gt(ev["dU_c"], lim):
        if lim_max is not None and gt(ev["dU_c"], lim_max):
            # v1.2 (C6): peste limita I7 nici mărirea automată nu ajută → BLOCANT
            emite(j, "V20", BLOCANT, obiect, "inv" if invertor else "bara", x=ev["dU_c"], lim=lim_max,
                  detaliu=" cu secțiunea impusă" if S_f is not None else " chiar la secțiunea maximă (4 × 240 mm²)")
        elif cod_lim == "V21" or invertor:
            emite(j, "V21", AVERTISMENT, obiect, x=ev["dU_c"], lim=lim)
        else:
            emite(j, "V20", BLOCANT, obiect, x=ev["dU_c"], lim=lim)
    # SPEC §B.12 / §B.3.1: ΔU la pornirea directă a motorului (Ip = k·Ib, cosφ 0,35), cu impedanța sursei până la bară
    du_porn = None
    if ip_porn is not None:
        cp = norme.MOTOR_COSFI_PORNIRE
        sp = math.sqrt(1 - cp ** 2)
        zq0 = ctx.get("Zq") or (0.0, 0.0)
        if retea == "mono":
            du_src = 100.0 * 2 * ip_porn * (zq0[0] * cp + zq0[1] * sp) / norme.U_0_V
        else:
            du_src = 100.0 * math.sqrt(3) * ip_porn * (zq0[0] * cp + zq0[1] * sp) / norme.U_N_V
        # v1.2 R2: pe sursă se adaugă doar creșterea de curent (Ip − Ib); ΔU_origine conține deja Ib
        du_src = du_src * max(ip_porn - ib, 0.0) / ip_porn
        du_porn = du0 + du_src + cb.du_pct(retea, ip_porn, L, mat, izl, S, n, cp)
        j.pas(f"{obiect}: ΔU la pornire ({PORNIRE_TXT.get(pornire, pornire)}, Ip = {fmt_ro(ip_porn)} A, cosφ {fmt_ro(cp)}) = {fmt_ro(du0)} + "
              f"{fmt_ro(du_src)} (sursă) + {fmt_ro(du_porn - du0 - du_src)} (cablu) = {fmt_ro(du_porn)} %")
        if gt(du_porn, norme.DU_PORNIRE_MOTOR_PCT):
            emite(j, "V22", AVERTISMENT, obiect, x=du_porn, lim=norme.DU_PORNIRE_MOTOR_PCT, k=k_porn)
        if motor_v23 is not None:
            prag_txt = motor_v23[1]
            if motor_v23[0] == "INFO":
                emite(j, "V23", INFO, obiect, "INFO", prot=f"{tip} {fmt_ro(In)} A", Ip=ip_porn,
                      t=norme.MOTOR_T_PORNIRE_S)
            else:
                emite(j, "V23", AVERTISMENT, obiect, "AV", prot=f"{tip} {fmt_ro(In)} A", Ip=ip_porn,
                      t=norme.MOTOR_T_PORNIRE_S, prag=prag_txt if prag_txt is not None else "—")
    if ev["motiv_N"]:
        emite(j, "V25", BLOCANT, obiect, N=ev["N"], motiv=ev["motiv_N"], S=S)
    if PE_f is not None and lt(n * ev["s_pe"], ev["s_tab"]):
        emite(j, "V26", BLOCANT, obiect, S_PE=ev["s_pe"], S_tab=round(ev["s_tab"], 1))
    stare = ev["stare"]
    ia_v = ev["Ia"]
    if ctx.get("tt_ddr_defect") and schema == "TT" and ctx.get("ddr_ramura"):
        # v1.5 (§C.8 pct. 6, runda 4 P0-3): în TT curentul de defect la masă se închide prin pământ (≈ U0/(RA + RB),
        # câțiva amperi) — MCB-ul NU asigură deconectarea; protecția la defect = DDR (RA·IΔn ≤ 50 V, art. 411.5.3).
        # Ik1 (bucla fază–nul) rămâne doar pentru protecția la scurtcircuit L–N.
        idn_tt = ctx["tt_ddr_defect"]["IdN_mA"]
        ra_tt = ctx["tt_ddr_defect"]["RA_ohm"]
        par = dict(ddr=f"DDR {idn_tt} mA", RA=ra_tt, IdN=idn_tt, x=ra_tt * idn_tt / 1000.0, ik1=round(ev["Ik1"]),
                   ia=ia_v if ia_v is not None else "—")
        if ia_v is not None and ge(ev["Ik1"], ia_v):
            emite(j, "V30", INFO, obiect, "TT", **par)
        else:
            emite(j, "V30", AVERTISMENT, obiect, "TT_AV", **par)
        stare = None
    if stare is None:
        pass
    elif stare == "ok":
        if marit_deconectare:
            emite(j, "V30", INFO, obiect, "INFO_marit", S=S, ik1=round(ev["Ik1"]), ia=ia_v)
        else:
            emite(j, "V30", INFO, obiect, "INFO", ik1=round(ev["Ik1"]), ia=ia_v, t=t_cer)
    elif stare == "ddr_propriu":
        emite(j, "V31", INFO, obiect, "INFO", ik1=round(ev["Ik1"]), ia=ia_v)
    elif stare == "ddr_amonte":
        emite(j, "V31", AVERTISMENT, obiect, "AV", ik1=round(ev["Ik1"]), ia=ia_v)
        if ctx.get("ddr_amonte_presupus"):
            # r5 (P1-11): DDR-ul din amonte e PRESUPUS (origine nedeclarată) — mesajul nu-l prezintă ca dat confirmat
            j.verificari[-1]["mesaj"] += (" — ATENȚIE: DDR-ul din amonte (RCCB 300 mA BMPT) este PRESUPUS, originea "
                                          "tabloului nu e declarată; fără el deconectarea NU este asigurată")
            j.verificari[-1]["remediere"] = "originea tabloului declarată (BMPT / tablou existent cu IdN_amonte_mA / PT propriu) sau DDR pe plecare"
    elif stare == "z_implicit":
        emite(j, "V32", AVERTISMENT, obiect, ik1=round(ev["Ik1"]), ia=ia_v)
    elif stare == "regim_ge" and ctx.get("ge_siguranta"):
        # r6: GE care alimentează circuite de siguranță (fără DDR) — tratat la nivelul schemei (V97 AVERTISMENT:
        # legături echipotențiale suplimentare + RCM)
        emite(j, "V85", AVERTISMENT, obiect, "ramura", x=round(ev["Ik1"]), y=ia_v)
    elif stare == "regim_ge":
        # v1.2 R2 (N-C1): regim GE fără DDR — deconectarea automată nu este asigurată
        emite(j, "V85", BLOCANT, obiect, "ramura", x=round(ev["Ik1"]), y=ia_v)
    elif stare == "blocant":
        emite(j, "V30", BLOCANT, obiect, "B", ik1=round(ev["Ik1"]), ia=ia_v)
    else:
        emite(j, "V30", AVERTISMENT, obiect, "AV", prot=f"{tip} {fmt_ro(In)} A", t=t_cer)
    # 13. Icu (B.16)
    icu = prot.get("Icu_kA")
    if icu is not None and lt(icu, ik3o):
        if r.get("bmpt"):
            emite(j, "V33", INFO, obiect, "bmpt", icu=icu, ik3=ik3o)
        elif r.get("rezerva_gG"):
            emite(j, "V33", AVERTISMENT, obiect, "rezerva", icu=icu, ik3=ik3o)
        else:
            emite(j, "V33", BLOCANT, obiect, icu=icu, ik3=ik3o)
    else:
        emite(j, "V33", INFO, obiect, "ok", icu=icu, ik3=ik3o)
    # 14. termic
    niv, x = v35
    if niv == "B":
        emite(j, "V35", BLOCANT, obiect, "B", n=n, S=S, x=round(x, 1))
    elif niv == "AV":
        emite(j, "V35", AVERTISMENT, obiect, "AV", n=n, S=S, x=round(x, 1), ik3=ik3o)
    elif niv == "INFO_marit":
        emite(j, "V35", INFO, obiect, "INFO_marit", n=n, S=S, x=round(x, 1))
    else:
        emite(j, "V35", INFO, obiect, "INFO", detaliu=("aparat limitator, SR HD 60364-4-43 art. 435.1" if x is None
                                                       else f"n·S ≥ {fmt_ro(x, 1)} mm²"))
    niv, x = v36
    if niv == "B":
        emite(j, "V36", BLOCANT, obiect, "B", S=ev["s_pe"], x=round(x, 1))
    elif niv == "AV":
        emite(j, "V36", AVERTISMENT, obiect, "AV", S=ev["s_pe"], x=round(x, 1))
    elif niv == "INFO_marit":
        emite(j, "V36", INFO, obiect, "INFO_marit", S=ev["s_pe"], x=round(x, 1))
    elif niv == "INFO_marit_cablu":
        emite(j, "V36", INFO, obiect, "INFO_cablu", S=ev["S"], x=round(x, 1))
    else:
        emite(j, "V36", INFO, obiect, "INFO", x=round(x, 1))

    # ---- 15. selectivitate (B.18) -----------------------------------------------------------------------------------
    if amonte is not None:
        pr.selectivitate(amonte, prot, ik3o, obiect_sel or f"{obiect} vs amonte", j, bmpt=bmpt_sel)

    # ---- rezultat și 16. contextul barei din aval ------------------------------------------------------------------
    prot_out = {"tip": tip, "In_A": In}
    if tip == "MCB":
        prot_out["curba"] = prot["curba"]
    if tip in ("MCCB", "ACB"):
        prot_out.update({"Ir_A": prot["Ir_A"], "Ir_multiplu": prot["Ir_multiplu"], "decl": prot["decl"]})
        if prot["decl"] == "TM":
            prot_out["Im_A"] = prot["Im_A"]
        else:
            prot_out.update({"Isd_A": prot.get("Isd_A"), "Isd_multiplu": prot.get("Isd_multiplu"),
                             "Ii_A": prot["Ii_A"], "tsd_s": prot["tsd_s"]})
    prot_out["Icu_kA"] = prot.get("Icu_kA")
    if prot.get("intrerupator_motor"):
        prot_out["intrerupator_motor"] = True
    if prot.get("Icu_fortat"):
        prot_out["Icu_fortat"] = True
    rez = {"obiect": obiect, "Ib_A": ib, "Ip_min_A": ip_min, "protectie": prot_out, "I2_A": I2, "Iz_min_A": iz_min,
           "material": mat, "izolatie": izl, "metoda": c["metoda"], "n_paralel": n, "S_faza_mm2": S,
           "S_N_mm2": ev["N"], "S_PE_mm2": ev["s_pe"], "PE": ev["loc"], "Iz_tabel_A": ev["Iz_tab"],
           "k_total": ev["k"], "Iz_corectat_A": ev["Izp"],
           "cablu": text_cablu(mat, izl, c["metoda"], n, S, ev["N"], ev["s_pe"], ev["loc"], retea,
                               monopolar=cb.monopolar(c)),
           "L_m": L, "dU_ramura_pct": ev["dU_r"], "dU_cumulat_pct": ev["dU_c"], "dU_limita_pct": lim,
           "Ik3max_origine_kA": ik3o, "Ik3max_capat_kA": ev["Ik3c"], "Ik1min_capat_A": ev["Ik1"],
           "Ia_A": ia_v, "t_deconectare_s": t_cer, "retea": retea, "receptor": receptor}
    if cb.monopolar(c):
        rez["monopolar"] = True
    if plafon[0] and gt(ev["dU_c"], lim):
        rez["dU_plafonat_mm2"] = float(r["S_max_dU"])
    if ddr_out:
        rez["DDR"] = ddr_out
    if h3 is not None and retea == "tri" and h3 > 33:
        rez["protectie_neutru"] = True
    if ip_porn is not None:
        rez.update({"pornire": pornire, "Ip_pornire_A": ip_porn, "dU_pornire_pct": du_porn})
    elif receptor == "motor" and pornire:
        rez["pornire"] = pornire          # r5: VFD (Ip ≈ In) — pornirea rămâne în rezultat pentru aparatajul desenat
    # M9: Ik1min nu poate depăși Ik3max (impedanțe incoerente) → V15 BLOCANT
    if gt(ev["Ik1"], ev["Ik3c"] * 1000.0 * (1 + 1e-6)):
        emite(j, "V15", BLOCANT, obiect, ik1=round(ev["Ik1"]), ik3=round(ev["Ik3c"] * 1000.0))
    ctx_aval = {"Zq": ev["Zq"], "Zb": ev["Zb"], "Ik3_kA": ev["Ik3c"], "dU_pct": ev["dU_c"],
                "origine": ctx["origine"], "z_implicit": ctx.get("z_implicit", False),
                "ik3_implicit": ctx.get("ik3_implicit", False),
                "ddr_amonte": bool(ctx.get("ddr_amonte") or ctx.get("ddr_ramura")), "ddr_ramura": None,
                "are_aval": False, "schema": schema,
                # TT (v1.2 R3): DDR-urile din aval ≤ IΔn/3 (selectivitate, SR HD 60364-5-53 art. 535.3)
                "idn_tt_mA": idn_aval_tt(ddr_tt) if ddr_tt else ctx.get("idn_tt_mA"),
                "regim_ge": ctx.get("regim_ge", False),
                # v1.3: cel mai apropiat DDR din amonte (selectivitatea DDR în serie, §B.18.1) și RA în TT
                "ddr_sus": ddr_sus_aval, "RA_tt": ctx.get("RA_tt"),
                "ddr_amonte_presupus": ctx.get("ddr_amonte_presupus") and not ctx.get("ddr_ramura")}
    return {"rezultat": rez, "prot": prot, "ctx_aval": ctx_aval, "blocat": False, "Ib": ib, "Ip": Ip}


def _vecini(serie, v):
    """Vecinii unui calibru inexistent din serie, pentru remedierea V05 (SPEC §D)."""
    s = sorted(serie)
    jos = [x for x in s if x < v]
    sus = [x for x in s if x > v]
    return (jos[-1] if jos else "—"), (sus[0] if sus else "—")


def verifica_cablu(param_cablu, protectie, obiect="cablu"):
    """v1.2 R2 (N-M1): verificarea unui cablu din model (desenat / editat manual) față de protecția lui, cu Iz'
    RECALCULAT din secțiune, material, izolație, metodă și pozare (nu preluat din `Iz_corectat_A`).

    param_cablu: {material, izolatie, metoda, S_faza_mm2 (sau S), n_paralel (sau n), retea, theta?, rho_sol?, n_alte?,
                  distanta?, aranjament?, Iz_corectat_A? (doar comparat)}
    protectie:   {tip: MCB|MCCB|ACB|gG, In_A, Ir_A?, curba?}
    Întoarce lista verificărilor {cod, nivel, obiect, mesaj, remediere}: V13 (secțiune inexistentă), V10 (pozare/
    material în afara tabelelor), V02 (Ip > Iz'), V03 (I2 > 1,45·Iz') — BLOCANT; plus un V02 INFO cu `Iz_corectat_A`
    recalculat (și `Iz_declarat_A` dacă diferă de valoarea din parametri cu > 1 %)."""
    from .comun import Jurnal
    j = Jurnal()
    p = dict(param_cablu or {})
    q = dict(protectie or {})
    mat = p.get("material")
    mat = mat.strip().capitalize() if isinstance(mat, str) else mat
    izl = (p.get("izolatie") or "PVC")
    izl = izl.strip().upper() if isinstance(izl, str) else izl
    met = p.get("metoda") or "D1"
    S = p.get("S_faza_mm2", p.get("S"))
    n = p.get("n_paralel", p.get("n")) or 1
    retea = p.get("retea") or "tri"
    if mat not in ("Cu", "Al") or izl not in ("PVC", "XLPE") or met not in norme.METODE_POZARE:
        emite(j, "V10", BLOCANT, obiect, parametru=f"material/izolație/metodă „{mat} {izl} {met}”", tabel="B.52.2–B.52.13")
        return j.verificari
    c = {"material": mat, "izolatie": izl, "metoda": met, "retea": "mono" if retea == "mono" else "tri",
         "theta": p.get("theta") if p.get("theta") is not None else cb.theta_implicit(met),
         "rho_sol": p.get("rho_sol") if p.get("rho_sol") is not None else 2.5, "n_alte": int(p.get("n_alte") or 0),
         "distanta": p.get("distanta", "atingere"), "aranjament": p.get("aranjament")}
    try:
        S = float(S)
        n = int(n)
    except (TypeError, ValueError):
        emite(j, "V13", BLOCANT, obiect, S=S, mat=mat)
        return j.verificari
    if S not in cb.sectiuni(c) or n < 1 or n > cb.n_max(c):
        emite(j, "V13", BLOCANT, obiect, S=fmt_ro(S), mat=mat)
        return j.verificari
    try:
        _, _, izp = cb.iz_corectat(c, n, S)
    except cb.InAfaraTabelelor as e:
        emite(j, "V10", BLOCANT, obiect, parametru=e.parametru, tabel=e.tabel)
        return j.verificari
    tip = pr.normalizeaza_tip(q.get("tip"))
    if tip not in pr.SERII or q.get("In_A") is None:
        emite(j, "V07", BLOCANT, obiect, "param", camp="protectie", x=repr(q.get("tip")), conditie="protecție necunoscută")
        return j.verificari
    prot = {"tip": tip, "In_A": float(q["In_A"]), "curba": q.get("curba", "C")}
    if tip in ("MCCB", "ACB"):
        prot["Ir_A"] = float(q.get("Ir_A") or q["In_A"])
    Ip = pr.ip(prot)
    I2 = pr.i2(prot)
    if gt(Ip, izp):
        emite(j, "V02", BLOCANT, obiect, Ip=Ip, Iz=izp)
    if gt(I2, 1.45 * izp):
        emite(j, "V03", BLOCANT, obiect, I2=I2, lim=1.45 * izp)
    info = {"cod": "V02", "nivel": "INFO", "obiect": obiect, "remediere": "",
            "mesaj": f"{obiect}: Iz' recalculat = {fmt_ro(izp, 1)} A (Ip = {fmt_ro(Ip)} A, I2 = {fmt_ro(I2)} A)",
            "Iz_corectat_A": izp}
    dec = p.get("Iz_corectat_A")
    if isinstance(dec, (int, float)) and abs(dec - izp) > 0.01 * izp:
        info["Iz_declarat_A"] = dec
        info["mesaj"] += f" — valoarea din parametri {fmt_ro(dec, 1)} A ignorată"
    return j.verificari + [info]
