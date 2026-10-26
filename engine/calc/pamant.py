"""pamant.py — calculul prizei de pământ (SPEC §C.7, v1.3): electrozi verticali în linie legați cu platbandă orizontală.

Intrare (cheia opțională `priza` a oricărei scheme; fără ea calculul NU rulează și nota de pe planșă rămâne
„priza de pământ: calcul separat”):

    {"rho_ohm_m": 100, "electrozi": {"n": 2, "L_m": 3, "d_m": 0.0635, "distanta_m": 6},
     "platbanda": {"L_m": 12, "latime_m": 0.04, "grosime_m": 0.004, "adancime_m": 0.8},   # sau false = fără platbandă
     "R_limita_ohm": null, "sezon": "I"|"II"|"III"|"implicit", "psi": 1.6, "psi_platbanda": 3.5}
    platbanda.L_m implicit = (n − 1)·a + L_racord_m (implicit 5 m); R_limita_ohm doar poate COBORÎ limita normată.

Formule (1.RE-Ip 30-2004 / STAS 12604/5-90, forma 0,366·ρ/L·lg(...) = ρ/(2πL)·ln(...)):
    ρ_e   = ψ_e·ρ ; ρ_pl = ψ_pl·ρ                                   (coeficienți sezonieri distincți, v1.3 R5)
    R_e   = ρ_e/(2πL)·[ln(2L/d) + ½·ln((4t + L)/(4t − L))],  t = h + L/2   (electrod vertical, capul la adâncimea h)
    R_pl  = ρ_pl/(2πL_p)·ln(2·L_p²/(b·h))                                    (platbandă orizontală, lățime b, adâncime h)
    Rp    = R_e·R_pl/(R_e·η_p + n·R_pl·η_e)                                 (combinația, coeficienți de utilizare η)
    Rp    = R_e/(n·η_e)                                                     (fără platbandă)
η_e, η_p: norme.PRIZA_ETA_ELECTROZI / PRIZA_ETA_PLATBANDA în funcție de n și a/L [NEVERIFICAT].
"""
import math

from . import norme
from .texte import fmt_ro, NB, X

OBIECT = "priza de pământ"
ZONE_IMPLICIT = ("k_sezon", "implicit", "")


def _numar(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


class _Erori(list):
    """Lista erorilor de validare: (cod, varianta, parametri) pentru verificari.emite."""

    def param(self, camp, x, conditie, cod="V07"):
        if cod == "V10":
            self.append(("V10", "", {"parametru": f"priza.{camp} = {x if not _numar(x) else fmt_ro(x, 4)}",
                                     "tabel": conditie}))
        elif cod == "V12":
            self.append(("V12", "camp", {"camp": f"priza.{camp}", "valoare": x}))
        else:
            self.append(("V07", "param", {"camp": f"priza.{camp}", "x": x if _numar(x) else repr(x),
                                          "conditie": conditie}))


def normalizeaza(p):
    """Validează și completează intrarea `priza` cu valorile implicite (declarate). Întoarce (par, erori, presupuse);
    la prima eroare (V07 valoare ≤ 0 / nenumerică / n nu e întreg ≥ 1, V10 în afara tabelelor, V12 enumerare)
    `par` este None."""
    er = _Erori()
    pres = []
    if not isinstance(p, dict):
        er.param("", p, "se așteaptă un obiect {rho_ohm_m, electrozi, platbanda, R_limita_ohm, sezon}")
        return None, er, pres

    def num(d, camp, cheie, implicit, text_implicit, cond=">0"):
        v = d.get(cheie)
        if v is None:
            if text_implicit:
                pres.append(text_implicit)
            return implicit
        if not _numar(v):
            er.param(camp, v, "valoare nenumerică (se așteaptă un număr)")
            return None
        if cond == ">=0" and not v >= 0:
            er.param(camp, v, "trebuie ≥ 0")
            return None
        if cond == ">0" and not v > 0:
            er.param(camp, v, "trebuie > 0")
            return None
        if cond == "int>=1" and not (float(v).is_integer() and v >= 1):
            er.param(camp, v, "trebuie număr întreg ≥ 1")
            return None
        return float(v) if cond != "int>=1" else int(v)

    rho = num(p, "rho_ohm_m", "rho_ohm_m", norme.PRIZA_RHO_IMPLICIT_OHM_M,
              f"ρ sol = {fmt_ro(norme.PRIZA_RHO_IMPLICIT_OHM_M)} Ω·m (sol argilos-nisipos) — măsurați rezistivitatea")
    if er:
        return None, er, pres
    if rho > norme.PRIZA_RHO_MAX_OHM_M:
        er.param("rho_ohm_m", rho, f"ρ ≤ {fmt_ro(norme.PRIZA_RHO_MAX_OHM_M, 0)} Ω·m (peste: rocă, priză specială)", "V10")
        return None, er, pres

    el = p.get("electrozi")
    if el is None:
        el = {}
    if not isinstance(el, dict):
        er.param("electrozi", el, "se așteaptă un obiect {n, L_m, d_m, distanta_m}")
        return None, er, pres
    n = num(el, "electrozi.n", "n", norme.PRIZA_N_IMPLICIT, None, "int>=1")      # declarat după dimensionare
    L = num(el, "electrozi.L_m", "L_m", norme.PRIZA_ELECTROD_L_IMPLICIT_M, None) if not er else None
    d = num(el, "electrozi.d_m", "d_m", norme.PRIZA_ELECTROD_D_IMPLICIT_M, None) if not er else None
    if el.get("L_m") is None and el.get("d_m") is None and not er:
        pres.append("electrozi țeavă OL-Zn 2½″ (Ø 63,5 mm) × 3 m")
    elif not er and (el.get("L_m") is None or el.get("d_m") is None):
        pres.append(f"electrod {'L = 3 m' if el.get('L_m') is None else 'Ø 63,5 mm (2½″)'}")
    if er:
        return None, er, pres
    a = num(el, "electrozi.distanta_m", "distanta_m", norme.PRIZA_A_PE_L_IMPLICIT * L,
            f"distanța între electrozi a = 2·L = {fmt_ro(norme.PRIZA_A_PE_L_IMPLICIT * L)} m")
    if er:
        return None, er, pres
    if n > norme.PRIZA_N_MAX:
        er.param("electrozi.n", n, f"n ≤ {norme.PRIZA_N_MAX} electrozi în linie (tabelele coeficienților de utilizare)", "V10")
    elif L > 30.0:
        er.param("electrozi.L_m", L, "L ≤ 30 m (peste: priză de adâncime, calcul dedicat)", "V10")
    elif d >= L:
        er.param("electrozi.d_m", d, "d < L (electrod vertical)", "V10")
    elif n > 1 and a / L < 1.0 - 1e-9:
        er.param("electrozi.distanta_m", a, f"a/L ≥ 1 (a/L = {fmt_ro(a / L, 2)}; tabelele η încep la a/L = 1)", "V10")
    if er:
        return None, er, pres

    pl = p.get("platbanda", {})
    if pl is None:
        pl = {}
    cu_pl = pl is not False
    Lp = b = g = None
    Lr = 0.0
    h = norme.PRIZA_ADANCIME_IMPLICIT_M
    Lp_impus = False
    if cu_pl:
        if not isinstance(pl, dict):
            er.param("platbanda", pl, "se așteaptă un obiect {L_m, L_racord_m, latime_m, adancime_m} sau false")
            return None, er, pres
        # v1.3 R5 (M5-1): n electrozi în linie se întind pe (n − 1)·a; se adaugă racordul la piesa de separație
        Lr = num(pl, "platbanda.L_racord_m", "L_racord_m", norme.PRIZA_L_RACORD_IMPLICIT_M,
                 f"racord platbandă → piesa de separație {fmt_ro(norme.PRIZA_L_RACORD_IMPLICIT_M)} m" if pl.get("L_m") is None
                 else None, ">=0")
        if er:
            return None, er, pres
        Lp_impus = pl.get("L_m") is not None
        Lp0 = (n - 1) * a + Lr
        Lp = num(pl, "platbanda.L_m", "L_m", Lp0, None)                         # declarat după dimensionare
        b = num(pl, "platbanda.latime_m", "latime_m", norme.PRIZA_PLATBANDA_LATIME_IMPLICIT_M, None) if not er else None
        g = num(pl, "platbanda.grosime_m", "grosime_m", norme.PRIZA_PLATBANDA_GROSIME_IMPLICIT_M, None) if not er else None
        h = num(pl, "platbanda.adancime_m", "adancime_m", norme.PRIZA_ADANCIME_IMPLICIT_M, None) if not er else None
        if not er and (pl.get("latime_m") is None or pl.get("adancime_m") is None):
            pres.append("platbandă OL-Zn 40 × 4 mm la 0,8 m adâncime")
        if er:
            return None, er, pres
        if h > 5.0:
            er.param("platbanda.adancime_m", h, "adâncime ≤ 5 m", "V10")
        elif 2 * Lp ** 2 / (b * h) <= math.e:
            er.param("platbanda.L_m", Lp, "platbandă prea scurtă față de b·h (ln(2L²/(b·h)) ≤ 1, formula nu se aplică)", "V10")
    else:
        h = num(el, "electrozi.adancime_m", "adancime_m", norme.PRIZA_ADANCIME_IMPLICIT_M,
                "capul electrozilor la 0,8 m adâncime")
    if er:
        return None, er, pres

    # coeficienții sezonieri ψ (v1.3 R5, M5-1): distincți pentru electrozi (ψ_e) și platbandă (ψ_pl)
    sez = p.get("sezon")
    psi = p.get("psi")
    psi_pl = p.get("psi_platbanda")
    if psi is None and _numar(sez):
        psi = sez
    zona = None
    if sez is not None and not _numar(sez):
        z = str(sez).strip()
        if z.upper() in norme.PRIZA_PSI_ZONE:
            zona = z.upper()
        elif z.lower() not in ZONE_IMPLICIT:
            er.param("sezon", sez, "", "V12")
            return None, er, pres
    for camp, v, lo, hi, txt in (("psi", psi, 1.0, 3.0, "ψ_e ∈ [1; 3] (1.RE-Ip 30: 1,4…1,8 la electrozi verticali)"),
                                 ("psi_platbanda", psi_pl, 1.0, 7.0, "ψ_pl ∈ [1; 7] (1.RE-Ip 30: 2,5…4,5 la platbandă)")):
        if v is not None:
            if not _numar(v):
                er.param(camp, v, "valoare nenumerică (se așteaptă un număr)")
            elif not lo <= v <= hi:
                er.param(camp, v, txt, "V10")
            if er:
                return None, er, pres
    zona_ef = zona or "II"
    if psi is None:
        psi = norme.PRIZA_PSI_ZONE[zona_ef]
        if zona is None:
            pres.append(f"coeficient sezonier electrozi ψ_e = {fmt_ro(psi)} (zona climatică II, 1,4…1,8)")
    if psi_pl is None and cu_pl:
        psi_pl = norme.PRIZA_PSI_PLATBANDA_ZONE[zona_ef]
        if zona is None:
            pres.append(f"coeficient sezonier platbandă ψ_pl = {fmt_ro(psi_pl)} (zona climatică II, 2,5…4,5)")

    rl = p.get("R_limita_ohm")
    if rl is not None and (not _numar(rl) or not rl > 0):
        er.param("R_limita_ohm", rl, "trebuie > 0" if _numar(rl) else "valoare nenumerică (se așteaptă un număr)")
        return None, er, pres
    par = {"n_implicit": el.get("n") is None, "rho": rho, "psi": float(psi), "psi_pl": float(psi_pl) if psi_pl is not None else None, "zona": zona,
           "n": n, "L": L, "d": d, "a": a, "platbanda": cu_pl, "Lp": Lp, "L_racord": Lr, "Lp_impus": Lp_impus,
           "b": b, "g": g, "h": h, "R_limita": float(rl) if rl is not None else None}
    return par, er, pres


def presupuneri_adoptate(par, c0, c):
    """v1.3 (P0-2, pct. 3): valorile presupuse ale prizei declarate cu valorile ADOPTATE după dimensionarea automată
    (numărul de electrozi și lungimea platbandei), cu valorile inițiale între paranteze când diferă."""
    out = []
    marit = c["n"] != c0["n"]
    if par["n_implicit"] or marit:
        t = f"priză: {c['n']} {'electrod' if c['n'] == 1 else 'electrozi'}"
        if marit:
            t += f" (mărit automat de la {c0['n']} pentru Rp ≤ limită)"
        out.append(t)
    if par["platbanda"] and (not par["Lp_impus"] or marit):
        t = f"platbandă {fmt_ro(c['Lp'], 1)} m"
        if not par["Lp_impus"]:
            t += f" = (n − 1)·a + racord = {c['n'] - 1}·{fmt_ro(par['a'])} + {fmt_ro(par['L_racord'])} m"
        if marit:
            t += f" (inițial {fmt_ro(c0['Lp'], 1)} m)"
        out.append(t)
    return out


def r_electrod(rho_c, L, d, h):
    """R unui electrod vertical cu capul la adâncimea h: ρ/(2πL)·[ln(2L/d) + ½·ln((4t+L)/(4t−L))], t = h + L/2."""
    t = h + L / 2.0
    return rho_c / (2 * math.pi * L) * (math.log(2 * L / d) + 0.5 * math.log((4 * t + L) / (4 * t - L))), t


def r_platbanda(rho_c, Lp, b, h):
    """R platbandei orizontale: ρ/(2πL)·ln(2L²/(b·h)) (= 0,366·ρ/L·lg(2L²/(b·h)), 1.RE-Ip 30 / STAS 12604/5)."""
    return rho_c / (2 * math.pi * Lp) * math.log(2 * Lp ** 2 / (b * h))


def lungime_platbanda(par, n):
    """Lungimea platbandei pentru n electrozi (v1.3 R5): impusă + (n − n_impus)·a la electrozii adăugați, altfel
    (n − 1)·a + racordul la piesa de separație."""
    if not par["platbanda"]:
        return 0.0
    if par["Lp_impus"]:
        return par["Lp"] + max(0, n - par["n"]) * par["a"]
    return (n - 1) * par["a"] + par["L_racord"]


def calcul(par, n):
    """Rezistența prizei cu n electrozi (formulele din antetul modulului). Întoarce dict cu valorile intermediare."""
    rho_c = par["psi"] * par["rho"]
    rho_pl = par["psi_pl"] * par["rho"] if par["platbanda"] else None
    re, t = r_electrod(rho_c, par["L"], par["d"], par["h"])
    aL = par["a"] / par["L"]
    eta_e = norme.priza_eta(norme.PRIZA_ETA_ELECTROZI, n, aL)
    Lp = lungime_platbanda(par, n)
    if par["platbanda"]:
        rpl = r_platbanda(rho_pl, Lp, par["b"], par["h"])
        eta_p = norme.priza_eta(norme.PRIZA_ETA_PLATBANDA, n, aL)
        rp = re * rpl / (re * eta_p + n * rpl * eta_e)
    else:
        rpl = eta_p = None
        rp = re / (n * eta_e)
    return {"n": n, "rho_c": rho_c, "rho_pl": rho_pl, "R_e": re, "t": t, "aL": aL, "eta_e": eta_e, "Lp": Lp, "R_pl": rpl,
            "eta_p": eta_p, "Rp": rp}


def dimensioneaza(par, lim):
    """Rp cu n-ul dat; dacă depășește limita, cel mai mic n ≤ 30 cu Rp ≤ limită (platbanda crește cu a la fiecare
    electrod adăugat). Întoarce (calcul_initial, calcul_final, n_necesar | None)."""
    c0 = calcul(par, par["n"])
    if c0["Rp"] <= lim + 1e-9:
        return c0, c0, par["n"]
    c = c0
    if par["a"] / par["L"] < 1.0 - 1e-9:
        return c0, c0, None              # a/L < 1: nu se pot adăuga electrozi în tabelele η (doar n = 1 calculabil)
    for n in range(par["n"] + 1, norme.PRIZA_N_MAX + 1):
        c = calcul(par, n)
        if c["Rp"] <= lim + 1e-9:
            return c0, c, n
    return c0, c, None


def _idn_max(x, acc):
    """IΔn [mA] ale tuturor DDR-urilor din rezultat (DDR, RCCB, Q BMPM, IdN_amonte_mA, DDR_TT_IdN_mA)."""
    if isinstance(x, dict):
        for k, v in x.items():
            if k in ("IdN_mA", "IdN_amonte_mA", "DDR_TT_IdN_mA") and _numar(v):
                acc.append(v)
            else:
                _idn_max(v, acc)
    elif isinstance(x, list):
        for v in x:
            _idn_max(v, acc)
    return acc


def limita_normata(tip, inp, rez):
    """Limita normată Rp [Ω] și motivul: TT → RA·IΔn ≤ 50 V cu cel mai mare IΔn din schemă; PT și CEF cu PT → 1 Ω
    (NTE 001, priză comună MT/JT); altfel 4 Ω (branșament, tablou, prosumator, CEF JT, GE)."""
    if str(inp.get("schema_pamant") or "").strip().upper() == "TT":
        idn = max(_idn_max(rez, []) or [norme.BMPT_RCCB["idn_ma"]])
        return 50000.0 / idn, f"TT: RA·IΔn ≤ 50 V cu IΔn max {fmt_ro(idn, 0)} mA (SR HD 60364-4-41 art. 411.5.3)"
    cheie = "cef_pt" if tip == "cef" and inp.get("pt_Sn_kVA") is not None else tip
    v = norme.PRIZA_R_LIMITA_OHM.get(cheie, 4.0)
    if v <= 1.0:
        return v, "priză comună MT/JT la PT (NTE 001/03/00)"
    return v, "NTE 001/03/00, I7-2011, ST 4-JT (priza locală a consumatorului)"


def limita(tip, inp, rez, par):
    """Limita folosită (v1.3 R5, M5-2): `R_limita_ohm` dat poate doar COBORÎ limita normată. Întoarce
    (limita, motiv, ridicata) — `ridicata` = (valoare cerută, limita normată, motiv normat) când utilizatorul a cerut o
    limită mai mare (→ V12 BLOCANT în schemă; calculul continuă cu limita normată), altfel None."""
    ln, mn = limita_normata(tip, inp, rez)
    u = par["R_limita"]
    if u is None:
        return ln, mn, None
    if u <= ln + 1e-9:
        return u, f"impusă, ≤ limita normată {fmt_ro(ln, 2)} Ω ({mn})", None
    return ln, mn, (u, ln, mn)


def _txt_electrod(par):
    if abs(par["d"] - 0.0635) < 1e-6:
        return f"țeavă OL-Zn 2½″ (Ø 63,5{NB}mm) {X} {fmt_ro(par['L'])}{NB}m"
    return f"OL-Zn Ø {fmt_ro(par['d'] * 1000, 1)}{NB}mm {X} {fmt_ro(par['L'])}{NB}m"


def _txt_platbanda(par):
    return f"platbandă OL-Zn {fmt_ro(par['b'] * 1000, 0)}{X}{fmt_ro(par['g'] * 1000, 0)}{NB}mm"


def materiale(par, c):
    """Lista de materiale din calcul (E.1: cantități din parametri, rotunjite în sus la unitatea de livrare):
    electrozi, platbandă (+10 %, m întregi), piesă de separație, îmbinări sudate, vopsea bitum (kg întregi), săpătură
    (m întregi). v1.3 R5: fiecare articol are `ore_u` (manoperă orientativă pe unitate, norme.PRIZA_ORE_U) și `ref`
    (PP-E, PP-PL, PS, PP-SUD, PP-VOP, PP-SAP) — PS poate coincide cu piesa de separație din blocul BN·PS·PPL."""
    o = norme.PRIZA_ORE_U
    n = c["n"]
    out = [{"ref": "PP-E", "denumire": f"Electrod de pământ {_txt_electrod(par)}", "cantitate": n, "um": "buc",
            "ore_u": o["electrod"]}]
    imbinari = n + 1
    if par["platbanda"]:
        lp = math.ceil(c["Lp"] * (1 + norme.PRIZA_REZERVA_PLATBANDA) - 1e-9)
        out.append({"ref": "PP-PL", "denumire": f"{_txt_platbanda(par)[0].upper()}{_txt_platbanda(par)[1:]} (+10{NB}% rezervă)",
                    "cantitate": lp, "um": "m", "ore_u": o["platbanda_m"]})
        imbinari += max(0, math.ceil(c["Lp"] / norme.PRIZA_BARA_PLATBANDA_M - 1e-9) - 1)
    out.append({"ref": "PS", "denumire": "Piesă de separație (cutie de separație, montaj aparent)", "cantitate": 1,
                "um": "buc", "ore_u": o["piesa_separatie"]})
    out.append({"ref": "PP-SUD", "denumire": "Îmbinare sudată OL-Zn (electrod–platbandă, platbandă–platbandă, racord PS)",
                "cantitate": imbinari, "um": "buc", "ore_u": o["sudura"]})
    out.append({"ref": "PP-VOP", "denumire": "Vopsea bitum pentru protecția îmbinărilor sudate",
                "cantitate": max(1, math.ceil(imbinari * norme.PRIZA_VOPSEA_KG_IMBINARE - 1e-9)), "um": "kg",
                "ore_u": o["vopsea_kg"]})
    if par["platbanda"]:
        out.append({"ref": "PP-SAP", "denumire": f"Săpătură și astupare șanț pentru platbandă, adâncime {fmt_ro(par['h'])}{NB}m",
                    "cantitate": math.ceil(c["Lp"] - 1e-9), "um": "m", "ore_u": o["sapatura_m"]})
    return out


def pasi(par, c, lim, lim_motiv, c0=None):
    """Pașii de calcul pentru memoriu (SPEC §H.3)."""
    out = [f"Priză de pământ: ρ = {fmt_ro(par['rho'])} Ω·m{' (zona ' + par['zona'] + ')' if par.get('zona') else ''}; "
           f"electrozi ψ_e = {fmt_ro(par['psi'])} → ρ_e = {fmt_ro(c['rho_c'])} Ω·m"
           + (f"; platbandă ψ_pl = {fmt_ro(par['psi_pl'])} → ρ_pl = {fmt_ro(c['rho_pl'])} Ω·m" if par["platbanda"] else "")]
    out.append(f"Electrod vertical L = {fmt_ro(par['L'])} m, d = {fmt_ro(par['d'], 4)} m, capul la h = {fmt_ro(par['h'])} m, "
               f"t = h + L/2 = {fmt_ro(c['t'], 3)} m: R_e = ρ_e/(2πL)·[ln(2L/d) + ½·ln((4t+L)/(4t−L))] = "
               f"{fmt_ro(c['rho_c'])}/(2π·{fmt_ro(par['L'])})·[ln({fmt_ro(2 * par['L'] / par['d'], 2)}) + ½·ln("
               f"{fmt_ro((4 * c['t'] + par['L']) / (4 * c['t'] - par['L']), 4)})] = {fmt_ro(c['R_e'], 3)} Ω")

    def linie(x, eticheta):
        s = []
        if par["platbanda"]:
            s.append(f"{eticheta}platbandă L = {fmt_ro(x['Lp'])} m, b = {fmt_ro(par['b'], 3)} m, h = {fmt_ro(par['h'])} m: "
                     f"R_pl = ρ_pl/(2πL)·ln(2L²/(b·h)) = {fmt_ro(x['R_pl'], 3)} Ω")
        s.append(f"{eticheta}n = {x['n']} electrozi în linie, a = {fmt_ro(par['a'])} m, a/L = {fmt_ro(x['aL'], 2)} → "
                 f"η_e = {fmt_ro(x['eta_e'], 3)}" + (f", η_p = {fmt_ro(x['eta_p'], 3)}" if par["platbanda"] else ""))
        if par["platbanda"]:
            s.append(f"{eticheta}Rp = R_e·R_pl/(R_e·η_p + n·R_pl·η_e) = {fmt_ro(x['R_e'], 3)}·{fmt_ro(x['R_pl'], 3)}/"
                     f"({fmt_ro(x['R_e'], 3)}·{fmt_ro(x['eta_p'], 3)} + {x['n']}·{fmt_ro(x['R_pl'], 3)}·"
                     f"{fmt_ro(x['eta_e'], 3)}) = {fmt_ro(x['Rp'], 3)} Ω")
        else:
            s.append(f"{eticheta}Rp = R_e/(n·η_e) = {fmt_ro(x['R_e'], 3)}/({x['n']}·{fmt_ro(x['eta_e'], 3)}) = "
                     f"{fmt_ro(x['Rp'], 3)} Ω")
        return s

    if c0 is not None and c0["n"] != c["n"]:
        out += linie(c0, f"[n = {c0['n']}] ")
        out.append(f"Rp = {fmt_ro(c0['Rp'], 3)} Ω > {fmt_ro(lim, 2)} Ω → se mărește numărul de electrozi")
        out += linie(c, f"[n = {c['n']}] ")
    else:
        out += linie(c, "")
    out.append(f"Limita Rp ≤ {fmt_ro(lim, 2)} Ω ({lim_motiv}) → "
               f"{'îndeplinită' if c['Rp'] <= lim + 1e-9 else 'NEÎNDEPLINITĂ'}")
    return out


def rezultat(par, c0, c, n_nec, lim, lim_motiv, ra_din_priza=False):
    """Dicționarul rez["priza"] (contractul de date §C.7)."""
    ok = c["Rp"] <= lim + 1e-9
    r = {"Rp_ohm": c["Rp"], "R_limita_ohm": lim, "limita_motiv": lim_motiv, "ok": ok,
         "n_electrozi": c["n"], "n_initial": c0["n"], "Rp_initial_ohm": c0["Rp"], "n_necesar": n_nec,
         "L_electrod_m": par["L"], "d_electrod_m": par["d"], "distanta_m": par["a"], "a_pe_L": c["aL"],
         "adancime_m": par["h"], "t_m": c["t"],
         "L_platbanda_m": c["Lp"] if par["platbanda"] else 0.0,
         "latime_platbanda_m": par["b"], "grosime_platbanda_m": par["g"],
         "rho_ohm_m": par["rho"], "psi": par["psi"], "rho_calcul_ohm_m": c["rho_c"],
         "psi_platbanda": par["psi_pl"], "rho_calcul_platbanda_ohm_m": c["rho_pl"],
         "L_racord_m": par["L_racord"] if par["platbanda"] and not par["Lp_impus"] else None,
         "eta_e": c["eta_e"], "eta_p": c["eta_p"], "R_electrod_ohm": c["R_e"], "R_platbanda_ohm": c["R_pl"],
         "dispunere": "electrozi verticali în linie" + (", legați cu platbandă" if par["platbanda"] else ""),
         "materiale": materiale(par, c), "RA_din_priza": bool(ra_din_priza),
         "pasi": pasi(par, c, lim, lim_motiv, c0)}
    pl = (f", legați cu {_txt_platbanda(par)}, L = {fmt_ro(c['Lp'], 1)}{NB}m" if par["platbanda"] else "")
    r["nota"] = (f"Priză de pământ: {c['n']} electrozi {_txt_electrod(par)} în linie, la a = {fmt_ro(par['a'])}{NB}m"
                 f"{pl}, la {fmt_ro(par['h'])}{NB}m adâncime; Rp calculat = {fmt_ro(c['Rp'], 2)}{NB}Ω "
                 f"{'≤' if ok else '>'} {fmt_ro(lim, 2)}{NB}Ω (ρ = {fmt_ro(par['rho'])}{NB}Ω·m, ψ_e = {fmt_ro(par['psi'])}"
                 f"{', ψ_pl = ' + fmt_ro(par['psi_pl']) if par['platbanda'] else ''}). "
                 f"Valoarea se confirmă prin măsurare înainte de punerea în funcțiune.")
    return r
