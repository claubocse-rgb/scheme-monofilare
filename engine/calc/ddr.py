"""ddr.py — selectivitatea DDR în serie (SPEC §B.18.1, v1.3 R5) și alegerea DDR-urilor într-un tablou / CEF în TT.

Regula (SR HD 60364-5-53 art. 535.3; SR EN 61008-1 / 61009-1 pentru DDR de tip S; SR EN 60947-2 anexa M pentru
releele diferențiale reglabile):
    pentru orice DDR aflat în aval de alt DDR:
      IΔn amonte ≥ 3·IΔn aval  ȘI  temporizarea amontelui − temporizarea avalului ≥ 0,15 s.
Temporizări: instantaneu (G) = 0 s; tip S = 0,15 s echivalent [DECIZIE, norme.DDR_T_ECHIVALENT_S]; bloc diferențial /
releu reglabil = Δt reglat. Consecință: S → instantaneu e selectiv; S → S NU (aceeași fereastră 0,13…0,5 s); reglabil
Δt 0,3 s → S e selectiv.
Neîndeplinită → V43 AVERTISMENT (variante „egal” — același IΔn și aceeași temporizare; „TT” — RA nu permite IΔn amonte
necesar; „AV” — cazul general, cu motivele). Îndeplinită → V43 INFO.

Un DDR se descrie ca {"IdN_mA", "t_s", "temporizare", "dt_s", "selectiv", "denumire"}.
"""
from . import norme
from .comun import ge
from .texte import fmt_ro
from .verificari import emite, AVERTISMENT, INFO

SERIE_IDN_TT = (300, 100, 30)                 # trepte folosite automat în TT (SPEC §C.2 pct. 13)
SERIE_IDN = sorted(norme.RCD_IDN_MA)          # 10, 30, 100, 300, 500, 1000 mA
K = norme.DDR_RAPORT_SELECTIVITATE
DT = norme.DDR_DT_SELECTIVITATE_S
T_S = norme.DDR_T_ECHIVALENT_S["S"]


def descriere(idn, selectiv=False, denumire="", dt_s=None):
    """Descrierea unui DDR: instantaneu (selectiv False), tip S (selectiv True) sau reglabil (dt_s dat)."""
    if dt_s is not None:
        t, temp = float(dt_s), "reglabil"
    elif selectiv:
        t, temp = T_S, "S"
    else:
        t, temp = 0.0, "instantaneu"
    return {"IdN_mA": idn, "t_s": t, "temporizare": temp, "dt_s": dt_s, "selectiv": temp != "instantaneu",
            "denumire": denumire}


def _txt_temp(d):
    if d["temporizare"] == "reglabil":
        return f" reglabil Δt {fmt_ro(d['dt_s'], 2)} s"
    return " tip S" if d["temporizare"] == "S" else " instantaneu"


def idn_amonte_necesar(idn_aval):
    """Cea mai mică treaptă IΔn din serie cu IΔn ≥ 3·IΔn aval (None dacă nu există)."""
    return next((x for x in SERIE_IDN if ge(x, K * idn_aval)), None)


def idn_aval_maxim(idn_amonte):
    """Cea mai mare treaptă IΔn din serie cu 3·IΔn ≤ IΔn amonte (None dacă nu există)."""
    return next((x for x in reversed(SERIE_IDN) if ge(idn_amonte, K * x)), None)


def ok_timp(am, av):
    """Selectivitatea în timp: t amonte − t aval ≥ 0,15 s."""
    return am["t_s"] - av["t_s"] >= DT - 1e-9


def selectiv(am, av):
    """True dacă perechea (amonte, aval) e selectivă: IΔn amonte ≥ 3·IΔn aval și Δt ≥ 0,15 s."""
    return ge(am["IdN_mA"], K * av["IdN_mA"]) and ok_timp(am, av)


def verifica(j, am, av, obiect, RA_ohm=None):
    """SPEC §B.18.1: verifică perechea DDR amonte → DDR aval și emite V43 (INFO dacă e selectivă, altfel AVERTISMENT
    cu motivul și o remediere concretă). `RA_ohm` (doar TT): când IΔn amonte necesar ar depăși RA·IΔn ≤ 50 V, varianta
    „TT” explică limitarea. Întoarce True dacă perechea e selectivă."""
    ia, iv = am["IdN_mA"], av["IdN_mA"]
    ob = f"{obiect} vs {am['denumire']}"
    par = {"am": am["denumire"], "av": av["denumire"], "IdN_am": ia, "IdN_av": iv, "S_am": _txt_temp(am),
           "S_av": _txt_temp(av), "T_am": _txt_temp(am).strip()}
    if selectiv(am, av):
        emite(j, "V43", INFO, ob, "INFO", **par)
        return True
    nec = idn_amonte_necesar(iv)
    jos = idn_aval_maxim(ia)
    t_nec = av["t_s"] + DT
    rem_t = (f"aval instantaneu (tip G)" if av["t_s"] > 0 else "amonte tip S") + \
        f" sau releu diferențial reglabil în amonte cu Δt ≥ {fmt_ro(t_nec, 2)} s"
    ok_i = ge(ia, K * iv)
    if RA_ohm is not None and not ok_i and nec is not None and RA_ohm * nec / 1000.0 > 50.0 + 1e-9:
        lim = 50000.0 / RA_ohm
        rem = (f"îmbunătățiți priza de pământ: RA ≤ {fmt_ro(50000.0 / nec, 1)} Ω permite DDR amonte {nec} mA "
               f"temporizat (selectiv cu {iv} mA în aval); altfel acceptați lipsa selectivității sau un singur nivel DDR")
        emite(j, "V43", AVERTISMENT, ob, "TT", RA=RA_ohm, lim=fmt_ro(lim, 0), rem=rem, **par)
        return False
    if ia == iv and abs(am["t_s"] - av["t_s"]) < 1e-9:
        alt = [f"DDR amonte {nec} mA temporizat ({rem_t})" if nec else None, f"DDR aval {jos} mA" if jos else None]
        rem = "înlocuiți " + " sau ".join(x for x in alt if x) + " (IΔn amonte ≥ 3·IΔn aval și Δt ≥ 0,15 s)"
        emite(j, "V43", AVERTISMENT, ob, "egal", rem=rem, **par)
        return False
    motive, rem = [], []
    if not ok_timp(am, av):
        if am["t_s"] <= 0:
            motive.append("amontele e instantaneu — nu e de tip S")
        elif am["temporizare"] == av["temporizare"] != "reglabil":
            motive.append(f"aceeași temporizare ({am['temporizare']} → {av['temporizare']}): două DDR S în serie nu "
                          f"sunt selective")
        else:
            motive.append(f"Δt amonte − aval = {fmt_ro(am['t_s'] - av['t_s'], 2)} s < {fmt_ro(DT, 2)} s")
        rem.append(rem_t)
    if not ok_i:
        motive.append(f"IΔn amonte {ia} mA < 3·{iv} = {fmt_ro(K * iv, 0)} mA")
        rem.append((f"IΔn amonte ≥ {nec} mA" if nec else "alt nivel de protecție") +
                   (f" sau IΔn aval ≤ {jos} mA" if jos else ""))
    if am.get("presupus"):
        # Î1 (28.10.2026): DDR-ul din BMPM / BMPT e PRESUPUS (AC instantaneu, ST DEER) — remedierea cere blocul real
        rem.append("sau declarați blocul real (DDR din branșament tip S, dacă așa e echipat)")
    emite(j, "V43", AVERTISMENT, ob, "AV", motiv="; ".join(motive), rem="; ".join(rem), **par)
    return False


def alege_tt(lim_ra, am):
    """SPEC §C.2 pct. 13 (v1.3 R5, M5-4): DDR-urile unui tablou / CEF în TT, alese selectiv.
    `lim_ra` = cea mai mare treaptă 300/100/30 mA cu RA·IΔn ≤ 50 V; `am` = DDR-ul din amonte (descriere) sau None.
    1) Amontele e temporizat (S / reglabil) și există o treaptă y ≤ lim_ra cu 3·y ≤ IΔn amonte → intrarea (Q1 / QG)
       NU primește DDR propriu (protejată de amonte); circuitele primesc y instantaneu (prizele 30 mA).
    2) Altfel, intrarea primește un bloc diferențial reglabil x ∈ {300, 100} mA (x ≤ lim_ra, x ≤ IΔn amonte), Δt 0,15 s,
       iar circuitele y = cea mai mare treaptă ≤ x/3, instantaneu.
    3) Dacă nici asta nu e posibil (RA permite doar 30 mA), intrarea fără DDR, circuitele 30 mA → V43 la verificare.
    Întoarce {"intrare": None | {"IdN_mA", "dt_s"}, "idn_circuite": y}."""
    ia = am["IdN_mA"] if am else None
    if am and am["t_s"] > 0:
        cand = [y for y in SERIE_IDN_TT if y <= lim_ra and ge(ia, K * y)]
        if cand:
            return {"intrare": None, "idn_circuite": max(cand)}
    xs = [x for x in (300, 100) if x <= lim_ra and (ia is None or x <= ia)]
    if xs:
        x = max(xs)
        y = max(z for z in SERIE_IDN_TT if ge(x, K * z))
        return {"intrare": {"IdN_mA": x, "dt_s": DT}, "idn_circuite": y}
    return {"intrare": None, "idn_circuite": min(lim_ra, ia) if ia else lim_ra}
