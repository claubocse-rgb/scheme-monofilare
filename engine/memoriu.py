"""Memoriul de calcul (SPEC §G.2, §G.4): document HTML generat din rezultatul motorului — ipoteze, valori presupuse,
tabelul de calcul pe ramuri, verificări și pașii de calcul. Se exportă ca PDF (Chrome) sau HTML."""
import html as H

from .calc import fmt_ro

CSS = """
@page{size:A4;margin:16mm 14mm}
body{font:10pt/1.4 Arial,Helvetica,sans-serif;color:#111}
h1{font-size:15pt;margin:0 0 2mm} h2{font-size:12pt;margin:7mm 0 2mm;border-bottom:1px solid #999;padding-bottom:1mm}
.meta{color:#444;margin-bottom:4mm} table{border-collapse:collapse;width:100%;font-size:8pt;margin:2mm 0}
th,td{border:1px solid #999;padding:1.2mm 1.5mm;vertical-align:top;text-align:left} th{background:#eee}
td.n{text-align:right;white-space:nowrap} .B{color:#b00020;font-weight:bold} .A{color:#8a5a00} .I{color:#555}
ul{margin:1mm 0 1mm 5mm;padding:0} li{margin:.6mm 0} .pasi{font-size:8pt;color:#333}
.ok{color:#1d6b3a;font-weight:bold} .stop{color:#b00020;font-weight:bold}
"""


def _e(x):
    return H.escape("" if x is None else str(x))


def _n(x, z=1):
    return fmt_ro(x, z) if isinstance(x, (int, float)) else _e(x)


def _ramuri(rez, cale=""):
    """toate ramurile dimensionate din rezultat (dict-uri cu Ib_A și protecție), în ordinea apariției"""
    out = []
    if isinstance(rez, dict):
        if "Ib_A" in rez and ("protectie" in rez or "S_faza_mm2" in rez):
            out.append((rez.get("obiect") or rez.get("nume") or cale, rez))
        for k, v in rez.items():
            if k in ("protectie",):
                continue
            out += _ramuri(v, k if not cale else f"{cale}.{k}")
    elif isinstance(rez, list):
        for i, v in enumerate(rez):
            out += _ramuri(v, f"{cale}[{i + 1}]")
    return out


def _prot(p, b=None):
    """textul protecției în tabelul de calcul: tip, In, Ir, reglajele electronice (Isd, tsd, Ii), DDR propriu
    și pornirea motorului (v1.2: Isd/tsd/Ii, DDR 30 mA la prize, Ip pornire)"""
    if not p:
        return "—"
    t = p.get("tip", "")
    s = f"{t} {p.get('curba', '') or ''}{p.get('In_A', '')} A"
    if p.get("Ir_A") and p.get("Ir_A") != p.get("In_A"):
        s += f", Ir {fmt_ro(p['Ir_A'], 2)} A"
    if p.get("Isd_A"):
        s += f", Isd {fmt_ro(p['Isd_A'], 0)} A"
    if p.get("tsd_s"):
        s += f", tsd {fmt_ro(p['tsd_s'], 2)} s"
    if p.get("Ii_A"):
        s += f", Ii {fmt_ro(p['Ii_A'], 0)} A"
    b = b or {}
    if b.get("DDR"):
        s += f" + DDR {b['DDR'].get('IdN_mA', 30)} mA tip {b['DDR'].get('tip', 'A')}"
    if b.get("Ip_pornire_A"):
        s += f" (pornire: Ip {fmt_ro(b['Ip_pornire_A'], 0)} A, ΔU {fmt_ro(b.get('dU_pornire_pct'), 1)} %)"
    return s


def _receptor(c):
    """v1.7 (m-c5): denumirea românească a receptorului (nu cheia internă „prize_bucatarie”)."""
    if c.get("receptor_eticheta"):
        return c["receptor_eticheta"]
    from .calc.locuinta import eticheta_receptor
    return eticheta_receptor(c.get("receptor")) if c.get("receptor") else ""


def _cap_locuinta(rz, nr):
    """v1.4 (SPEC §C.8): capitolul „Bilanț și repartizarea pe faze” al unei locuințe — circuitele cu receptor, fază,
    putere, Ib, protecție și grupa DDR; Pi, ks, Pc, Ib general; curenții pe faze și dezechilibrul; Q general, SPD."""
    b = rz.get("bilant") or {}
    f = rz.get("faze") or {}
    o = [f"<h2>{nr}. Bilanț și repartizarea pe faze</h2>",
         "<table><tr><th>Circuit</th><th>Receptor</th><th>Fază</th><th>P [kW]</th><th>Ib [A]</th><th>Protecție</th>"
         "<th>Cablu</th><th>Grupa DDR</th><th>Protecția la defect (contact indirect)</th></tr>"]
    note_cablu = []
    for g in rz.get("grupe_DDR") or []:
        d = g.get("DDR") or {}
        gtxt = (f"{g.get('obiect')} ({g.get('grupa')}, {g.get('faza')}): {d.get('aparat', 'RCCB')} {d.get('IdN_mA')} mA "
                f"tip {d.get('tip')}, {_n(d.get('In_A'), 0)} A {d.get('poli', '')}") if d else "fără DDR"
        for c in g.get("circuite") or []:
            o.append(f"<tr><td>{_e(c.get('nume') or c.get('obiect'))}</td><td>{_e(_receptor(c))}</td>"
                     f"<td>{_e(c.get('faza'))}</td><td class='n'>{_n(c.get('P_kW'), 2)}</td><td class='n'>{_n(c.get('Ib_A'))}</td>"
                     f"<td>{_e(_prot(c.get('protectie')))}</td><td>{_e(c.get('cablu'))}</td><td>{_e(gtxt)}</td>"
                     f"<td>{_e(c.get('protectie_defect') or '—')}</td></tr>")
            if c.get("cablu_nota"):
                note_cablu.append(f"{c.get('nume') or c.get('obiect')}: {c['cablu_nota']}")
    o.append("</table>")
    if rz.get("schema_pamant") == "TT":
        o.append("<p>Schema TT: protecția la defect (contact indirect) a fiecărui circuit se realizează prin DDR-ul grupei "
                 "(RA·IΔn ≤ 50 V, SR HD 60364-4-41 art. 411.5.3) — curentul de defect prin pământ (≈ U0/(RA + RB)) nu "
                 "acționează MCB-ul. Ik1 / Ia din tabelul de calcul se referă numai la scurtcircuitul fază–nul.</p>")
    o += [f"<p>{_e(t)}</p>" for t in note_cablu]
    o.append("<table>")
    rows = [("Putere instalată Σ Pi [kW]", _n(b.get("Pi_kW"), 2)), ("din care sarcini continue [kW]", _n(b.get("P_continuu_kW"), 2)),
            ("Coeficient de simultaneitate", f"{_n(b.get('ks'), 2)} — {_e(b.get('ks_regula'))}"),
            ("Putere cerută Pc [kW]", _n(b.get("Pc_kW"), 2)), ("cosφ mediu", _n(b.get("cosfi"), 2)),
            ("Curent general Ib [A]", f"{_n(b.get('Ib_A'), 1)} (din {_e(b.get('Ib_baza') or 'Pc')})"),
            ("Ib din Pc (informativ) [A]", _n(b.get("Ib_Pc_A"), 1)),
            ("Putere aprobată (ATR) [kW]", _n(b.get("P_aprobata_kW"), 2) if b.get("P_aprobata_kW") else "—")]
    if f.get("dezechilibru_pct") is not None:
        rows += [("Curent L1 / L2 / L3 [A] (Ib instalat)", f"{_n(f.get('L1_A'))} / {_n(f.get('L2_A'))} / {_n(f.get('L3_A'))}"),
                 ("Dezechilibru (Imax − Imed)/Imed [%]", _n(f.get("dezechilibru_pct"), 1))]
    else:
        rows.append(("Curent total pe fază [A] (Ib instalat)", _n(f.get("L1_A"))))
    if f.get("I_calc_max_A") is not None:
        rows.append(("Ib de calcul pe fază (ks; continue cu 1) L1 / L2 / L3 [A]",
                     f"{_n(f.get('L1_calc_A'))} / {_n(f.get('L2_calc_A'))} / {_n(f.get('L3_calc_A'))} — maxim pe "
                     f"{_e(f.get('faza_max'))}, verificat față de Q branșament (V46)"))
    q = rz.get("Q_general") or {}
    sp = rz.get("SPD") or {}
    rows += [("Q general TE", f"{_e(q.get('tip'))} {_e(q.get('poli'))} {_n(q.get('In_A'), 0)} A"
                              + (f", Icc condiționat {_n(q.get('Icc_kA'), 0)} kA" if q.get("Icc_kA") else "")),
             ("SPD la intrare", f"{_e(sp.get('tip'))} {_e(sp.get('poli'))}, In {_n(sp.get('In_kA'), 0)} kA, Up ≤ "
                                f"{_n(sp.get('Up_kV'), 1)} kV"
                                + (f"; protecție de rezervă F2: {_e((sp.get('protectie_rezerva') or {}).get('text'))}"
                                   if sp.get("protectie_rezerva") else ""))]
    col = rz.get("coloana") or {}
    if col.get("conductoare"):
        # v1.6 (N3): conductoarele coloanei și originea PE (TT: L + N, PE din priza locală)
        rows.append(("Coloana C2 — conductoare", f"{_e(col.get('cablu'))}: {_e(col.get('conductoare'))} — "
                                                 f"{_e(col.get('PE_nota'))}"))
    mb = col.get("marit_buget_dU")
    if mb:
        rows.append(("Coloana C2 — buget ΔU", f"ΔU {_n(mb.get('dU_initial_pct'), 2)} % pe {_n(mb.get('S_initial_mm2'), 0)} "
                                              f"mm² > {_n(mb.get('buget_pct'), 1)} % → mărită la {_n(col.get('S_faza_mm2'), 0)} "
                                              f"mm² (ΔU {_n(col.get('dU_ramura_pct'), 2)} %), circuitele finale rămân la "
                                              f"secțiunea uzuală"))
    for a, v in rows:
        o.append(f"<tr><th style='width:40%'>{_e(a)}</th><td>{v}</td></tr>")
    o.append("</table>")
    return o


def _cap_priza(p, nr=4):
    """v1.3 (SPEC §C.7): capitolul „Priza de pământ” — date, tabelul de calcul, rezultatul și lista de materiale."""
    o = [f"<h2>{nr}. Priza de pământ</h2>",
         f"<p>{_e(p.get('dispunere'))}. Formule: 1.RE-Ip 30-2004 / STAS 12604/5 — R<sub>e</sub> = ρ/(2πL)·[ln(2L/d) + "
         "½·ln((4t+L)/(4t−L))], R<sub>pl</sub> = ρ/(2πL<sub>p</sub>)·ln(2L<sub>p</sub>²/(b·h)), "
         "R<sub>p</sub> = R<sub>e</sub>·R<sub>pl</sub>/(R<sub>e</sub>·η<sub>p</sub> + n·R<sub>pl</sub>·η<sub>e</sub>); "
         "ρ<sub>e</sub> = ψ<sub>e</sub>·ρ, ρ<sub>pl</sub> = ψ<sub>pl</sub>·ρ (coeficienți sezonieri distincți).</p>",
         "<table><tr><th>Mărime</th><th>Valoare</th><th>Mărime</th><th>Valoare</th></tr>"]
    rows = [("ρ măsurat / presupus [Ω·m]", _n(p.get("rho_ohm_m"), 1), "ψ_e electrozi / ψ_pl platbandă",
             f"{_n(p.get('psi'), 2)} / {_n(p.get('psi_platbanda'), 2) if p.get('psi_platbanda') else '—'}"),
            ("ρ_e / ρ_pl de calcul [Ω·m]", f"{_n(p.get('rho_calcul_ohm_m'), 1)} / "
             f"{_n(p.get('rho_calcul_platbanda_ohm_m'), 1) if p.get('rho_calcul_platbanda_ohm_m') else '—'}", "limita Rp [Ω]",
             f"{_n(p.get('R_limita_ohm'), 2)} ({_e(p.get('limita_motiv'))})"),
            ("electrod L × d [m]", f"{_n(p.get('L_electrod_m'), 2)} × {_n(p.get('d_electrod_m'), 4)}",
             "adâncime cap / t [m]", f"{_n(p.get('adancime_m'), 2)} / {_n(p.get('t_m'), 3)}"),
            ("R un electrod R_e [Ω]", _n(p.get("R_electrod_ohm"), 3), "distanța a [m] / a/L",
             f"{_n(p.get('distanta_m'), 2)} / {_n(p.get('a_pe_L'), 2)}"),
            ("platbandă L_p × b [m]", f"{_n(p.get('L_platbanda_m'), 1)} × {_n(p.get('latime_platbanda_m'), 3)}"
             if p.get("R_platbanda_ohm") is not None else "—", "R platbandă R_pl [Ω]", _n(p.get("R_platbanda_ohm"), 3)
             if p.get("R_platbanda_ohm") is not None else "—"),
            ("număr electrozi n (inițial → adoptat)", f"{p.get('n_initial')} → {p.get('n_electrozi')}",
             "η_e / η_p", f"{_n(p.get('eta_e'), 3)} / {_n(p.get('eta_p'), 3) if p.get('eta_p') is not None else '—'}"),
            ("Rp cu n inițial [Ω]", _n(p.get("Rp_initial_ohm"), 2), "Rp adoptat [Ω]", _n(p.get("Rp_ohm"), 2))]
    for a, b, c, d in rows:
        o.append(f"<tr><th>{_e(a)}</th><td class='n'>{_e(b)}</td><th>{_e(c)}</th><td class='n'>{_e(d)}</td></tr>")
    o.append("</table>")
    o.append("<p class='ok'>Priza se încadrează în limită.</p>" if p.get("ok") else
             "<p class='stop'>Priza NU se încadrează în limită nici cu 30 de electrozi (V37 BLOCANT).</p>")
    if p.get("RA_din_priza"):
        o.append("<p>Schema TT: RA = Rp calculat (RA_ohm nedeclarat) — se confirmă prin măsurare.</p>")
    o.append("<table><tr><th>Material</th><th>Cantitate</th><th>U.M.</th><th>Manoperă [ore/U.M.]</th><th>Ore</th></tr>")
    for m in p.get("materiale") or []:
        ou = m.get("ore_u") or 0
        o.append(f"<tr><td>{_e(m.get('denumire'))}</td><td class='n'>{_n(m.get('cantitate'), 1)}</td><td>{_e(m.get('um'))}</td>"
                 f"<td class='n'>{_n(ou, 2)}</td><td class='n'>{_n(ou * (m.get('cantitate') or 0), 1)}</td></tr>")
    o.append("</table>")
    if p.get("nota"):
        o.append(f"<p>{_e(p['nota'])}</p>")
    return o


# v1.3 (P0-2, pct. 4): etichetele românești ale datelor de intrare, cu unități (cheile interne nu apar în memoriu)
ETICHETE = {
    "tip_schema": ("Tip schemă", ""), "retea": ("Rețea", ""), "schema_pamant": ("Schemă de legare la pământ", ""),
    "P_kW": ("Putere", "kW"), "S_kVA": ("Putere aparentă", "kVA"), "Ib_A": ("Curent de calcul Ib", "A"),
    "In_A": ("Calibru", "A"), "cosfi": ("cosφ", ""), "ks": ("Coeficient de simultaneitate ks", ""),
    "L_coloana_m": ("Lungime coloană C2", "m"), "L_alimentare_m": ("Lungime alimentare tablou", "m"),
    "L_inv_m": ("Lungime cablu invertor", "m"), "L_pcs_m": ("Lungime cablu PCS", "m"), "L_m": ("Lungime", "m"),
    "L_C1_m": ("Lungime C1 (rețea → ATS)", "m"), "L_C2_m": ("Lungime C2 (GE → ATS)", "m"),
    "L_C3_m": ("Lungime C3 (ATS → consumatori)", "m"), "L_racord_m": ("Lungime C0 (TGD-CF → punct de racord)", "m"),
    "Ik3_OD_kA": ("Ik3max la punctul de delimitare (ATR)", "kA"), "Zb_OD_ohm": ("Impedanța buclei OD (ATR)", "Ω"),
    "Ik3_TG_kA": ("Ik3max la bara TG existent", "kA"), "Zb_TG_ohm": ("Impedanța buclei la bara TG", "Ω"),
    "SkQ_MVA": ("Putere de scurtcircuit MT S\"kQ", "MVA"), "Sn_kVA": ("Putere transformator", "kVA"),
    "pt_Sn_kVA": ("Putere PT propriu", "kVA"), "origine": ("Originea alimentării", ""),
    "RA_ohm": ("Rezistența prizei RA (TT)", "Ω"), "IdN_amonte_mA": ("IΔn DDR din amonte", "mA"),
    "DDR_amonte_selectiv": ("DDR din amonte temporizat (S)", ""), "Q1_DDR": ("DDR pe Q1", ""),
    "In_Q1_A": ("Calibru Q1 impus", "A"), "Q1_tip": ("Tip Q1 impus", ""), "In_QG_A": ("Calibru QG impus", "A"),
    "In_Q_JT_A": ("Calibru Q JT impus", "A"), "Q_In_A": ("Calibru Q branșament impus", "A"),
    "bmpt_fortat": ("Bloc de măsură impus", ""), "masura_ceruta": ("Măsură cerută", ""),
    "circuite_finale": ("Tablou cu circuite finale", ""), "h3": ("Armonica 3", "%"), "h3_pct": ("Armonica 3", "%"),
    "kWp": ("Putere PV instalată", "kWp"), "bess": ("Stocare (BESS)", ""), "string": ("String PV", ""),
    "racord": ("Punct de racord", ""), "racord_In_Q_A": ("Protecția existentă din TG", "A"),
    "racord_Q_tip": ("Tipul protecției din TG", ""), "racord_Icu_kA": ("Icu protecție TG", "kA"),
    "atr_jt": ("ATR pentru racord JT", ""), "Pn_inv_kW": ("Putere invertor", "kW"), "Iac_max_A": ("Iac,max invertor", "A"),
    "In_Q_bransament_A": ("Calibru Q branșament existent", "A"), "hibrid": ("Invertor hibrid", ""),
    "Sn_GE_kVA": ("Putere grup electrogen", "kVA"), "P_sarcina_kW": ("Putere sarcină", "kW"),
    "Ib_sarcina_A": ("Curent sarcină", "A"), "xd": ("Reactanța subtranzitorie x\"d", "u.r."),
    "In_Q_retea_A": ("Calibru Q rețea impus", "A"), "ATS_poli": ("ATS — număr de poli", ""),
    "ATS_interblocaj": ("ATS — interblocaj", ""), "excitatie_sustinuta": ("Excitație susținută GE", ""),
    "DDR_GE": ("DDR pe Q_G", ""), "celula_trafo": ("Celula trafo", ""), "masura_pt": ("Punctul de măsură PT", ""),
    "cablu": ("Cablu (implicit)", ""), "cablu_inv": ("Cabluri invertoare", ""), "cablu_pcs": ("Cablu PCS", ""),
    "cablu_C0": ("Cablu C0", ""), "priza": ("Priza de pământ", ""), "Pn_kW": ("Putere nominală", "kW"),
    "n": ("Număr", "buc"), "kWh": ("Capacitate", "kWh"),
    "alimentare": ("Alimentare", ""), "P_aprobata_kW": ("Putere aprobată (ATR)", "kW"),
    "Q_general_tip": ("Tip Q general TE", ""), "faza": ("fază", ""), "L_m": ("Lungime", "m"),
    # câmpuri de cablu / priză / DDR (structuri imbricate)
    "material": ("material", ""), "izolatie": ("izolație", ""), "metoda": ("metoda de pozare", ""),
    "theta": ("temperatura mediului", "°C"), "rho_sol": ("rezistivitate termică sol", "K·m/W"),
    "n_alte": ("alte circuite pe traseu", ""), "S_fortat": ("secțiune impusă", "mm²"), "n_fortat": ("cabluri în paralel", ""),
    "N_fortat": ("neutru impus", "mm²"), "PE_fortat": ("PE impus", "mm²"), "PE_loc": ("PE", ""), "L": ("lungime", "m"),
    "distanta": ("distanța între cabluri", ""), "rho_ohm_m": ("rezistivitatea solului ρ", "Ω·m"),
    "electrozi": ("electrozi", ""), "platbanda": ("platbandă", ""), "L_m_e": ("lungime", "m"), "d_m": ("diametru", "m"),
    "distanta_m": ("distanța între electrozi", "m"), "latime_m": ("lățime", "m"), "grosime_m": ("grosime", "m"),
    "adancime_m": ("adâncime", "m"), "R_limita_ohm": ("limita Rp", "Ω"), "sezon": ("zona climatică", ""),
    "psi": ("ψ electrozi", ""), "psi_platbanda": ("ψ platbandă", ""), "IdN_mA": ("IΔn", "mA"), "selectiv": ("tip S", ""),
    "dt_s": ("temporizare Δt", "s"), "tip": ("tip", ""), "n_module": ("module pe string", ""), "Uoc_V": ("Voc modul", "V"),
    "Isc_A": ("Isc modul", "A"), "beta": ("β(Voc)", "%/K"), "Umax_inv_V": ("Umax c.c. invertor", "V"),
    # fișe tehnice (v1.8)
    "modul": ("Modul PV (fișa tehnică)", ""), "invertor": ("Invertor (fișa tehnică)", ""),
    "baterie": ("Baterie (fișa tehnică)", ""), "spd_cc": ("SPD c.c. (fișa tehnică)", ""), "gpv": ("Siguranțe gPV (fișa tehnică)", ""),
    "producator": ("producător", ""), "model": ("model", ""), "Pmax_W": ("Pmax", "W"), "Voc_V": ("Voc", "V"),
    "Vmpp_V": ("Vmpp", "V"), "Impp_A": ("Impp", "A"), "beta_Voc_pct_K": ("β(Voc)", "%/K"),
    "Umax_sistem_V": ("Umax sistem", "V"), "Umax_modul_V": ("Umax sistem modul", "V"), "Umax_dc_V": ("Umax c.c.", "V"),
    "MPPT_min_V": ("MPPT min", "V"), "MPPT_max_V": ("MPPT max", "V"), "Idc_max_A": ("Idc max / MPPT", "A"),
    "Isc_max_A": ("Isc max / MPPT", "A"), "nr_MPPT": ("număr MPPT", ""), "Ucpv_V": ("Ucpv", "V"),
    "U_nom_V": ("U nominală c.c.", "V"), "kWh_util": ("capacitate utilă", "kWh"), "chimie": ("chimie", ""),
    "Iac_max_A_fisa": ("Iac,max", "A"),
    "n_stringuri_paralel": ("stringuri în paralel", ""), "I_rev_A": ("curent invers admis modul", "A"),
    "L_racord_m_pl": ("racord la piesa de separație", "m"), "nume": ("nume", ""), "receptor": ("receptor", ""),
}
VALORI = {"tri": "trifazată 3 × 400/230 V", "mono": "monofazată 230 V", "bransament": "branșament DEER",
          "tablou": "tablou cu bilanț de puteri", "cef": "CEF", "pt": "post de transformare 20/0,4 kV",
          "prosumator": "prosumator", "ge_ats": "grup electrogen + ATS", "tg_existent": "TG existent (consum propriu)",
          "retea_publica": "rețea publică", "pt_propriu": "PT propriu", "semidirecta": "semidirectă",
          "locuinta": "locuință (tabloul casei / apartamentului)", "bransament_existent": "branșament existent",
          "bransament_nou": "branșament nou", "IS": "întreruptor-separator"}


def _et(k):
    """Eticheta românească a unei chei de intrare, cu unitatea între paranteze drepte."""
    if k not in ETICHETE:
        return k.replace("_", " ")
    et, um = ETICHETE[k]
    return f"{et} [{um}]" if um else et


def _val(v, k=None):
    """Valoarea unei chei de intrare, lizibilă: numere în format RO, bool → da/nu, (R, X) → R + jX, structuri imbricate
    → „etichetă: valoare; …”."""
    if isinstance(v, bool):
        return "da" if v else "nu"
    if isinstance(v, (int, float)):
        return fmt_ro(v, 4)
    if isinstance(v, str):
        return VALORI.get(v, v)
    if isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v) and k in (
            "Zb_OD_ohm", "Zb_TG_ohm"):
        return f"{fmt_ro(v[0], 3)} + j{fmt_ro(v[1], 3)}"
    if isinstance(v, dict):
        return "; ".join(f"{_et(kk)}: {_val(vv, kk)}" for kk, vv in v.items() if vv is not None and not str(kk).startswith("_"))
    if isinstance(v, (list, tuple)):
        return " | ".join(_val(x) for x in v)
    return "" if v is None else str(v)


def _cap_e2(model, r, nr):
    """E2: capitolul „Măsuri și evaluări suplimentare” — protecția în regim GE, limitarea la PCC, evaluarea SPD,
    pierderile în cabluri și producția estimată (PV). Ultimul capitol: numerotarea celorlalte nu se schimbă."""
    from . import documente_protectii as dp, documente_tabele as dt, pvgis
    rz = r.get("rezultat") if isinstance(r.get("rezultat"), dict) else {}
    calc = model.get("calc") or {}
    o = []
    ge_p = rz.get("protectie_regim_GE")
    if isinstance(ge_p, dict):
        if ge_p.get("solutie"):
            o.append(f"<h3>Protecția la contact indirect în regim GE</h3><p>Soluția aleasă: <b>{_e(ge_p['titlu'])}</b>. "
                     f"{_e(ge_p.get('implica'))} Pe planșă: {_e(ge_p.get('desen'))}</p>")
        else:
            o.append("<h3>Protecția la contact indirect în regim GE</h3><p class='stop'>Neleasă — alegeți una dintre "
                     "soluții:</p><ul>" + "".join(f"<li><b>{_e(x['titlu'])}</b> — când: {_e(x['cand'])} Implică: "
                                                  f"{_e(x['implica'])}</li>" for x in ge_p.get("optiuni") or []) + "</ul>")
    pcc = rz.get("limitare_PCC")
    if isinstance(pcc, dict) and pcc.get("Sn_kVA"):
        if pcc.get("P_kW"):
            o.append(f"<h3>Limitarea puterii la punctul de racord (PCC)</h3><p>Sn trafo {_n(pcc['Sn_kVA'], 0)} kVA &lt; S "
                     f"invertoare + PCS {_n(pcc['S_necesar_kVA'])} kVA: puterea la PCC se limitează la <b>{_n(pcc['P_kW'])} kW</b> "
                     f"(S = {_n(pcc.get('S_kVA'))} kVA la cosφ {_n(pcc['cosfi'], 2)}) cu EMS / controller de putere, TC + "
                     f"analizor de rețea la PCC și comandă spre invertoare / PCS. Propunerea automată: {_e(pcc['formula'])} = "
                     f"{_n(pcc['propunere_kW'], 0)} kW. Limitarea se confirmă prin ATR.</p>")
        else:
            o.append(f"<h3>Limitarea puterii la punctul de racord (PCC)</h3><p class='stop'>Sn trafo {_n(pcc['Sn_kVA'], 0)} kVA "
                     f"&lt; S {_n(pcc['S_necesar_kVA'])} kVA: alegeți un trafo mai mare sau limitați puterea la PCC (propus "
                     f"{_n(pcc['propunere_kW'], 0)} kW = {_e(pcc['formula'])}).</p>")
    try:
        ev = dp.evaluare_spd(calc, model)
        o.append(f"<h3>Protecția la supratensiuni (SPD)</h3><p>{_e(ev['nota_memoriu'])}</p>"
                 + ("<ul>" + "".join(f"<li>{_e(x)}</li>" for x in ev["motive"] + ev["neconcordante"]) + "</ul>"
                    if ev["motive"] or ev["neconcordante"] else "")
                 + (f"<p class='pasi'>Presupus: {_e('; '.join(ev['presupus']))}</p>" if ev["presupus"] else ""))
    except Exception:
        pass
    if calc.get("tip_schema") in ("cef", "prosumator"):
        pv = model.get("pvgis") if isinstance(model.get("pvgis"), dict) else None
        if pv is None and isinstance(calc.get("productie"), dict) and calc["productie"].get("kWh_kWp_an") and calc.get("kWp"):
            # interfața salvează rezultatul PVGIS / valoarea manuală în calc.productie
            pv = pvgis.din_valoare(calc["productie"]["kWh_kWp_an"], calc["kWp"])
            pv["sursa"] = calc["productie"].get("sursa") or pv["sursa"]
            if calc["productie"].get("unghi") is not None:
                pv["parametri"] = {"unghi": calc["productie"]["unghi"], "azimut": calc["productie"].get("azimut", 0)}
        y = (pv or {}).get("kWh_kWp_an") or calc.get("productie_specifica_kWh_kWp")
        if pv and not pv.get("necesita_valoare"):
            o.append(f"<h3>Producția estimată</h3><p>{_e(pvgis.paragraf_memoriu(pv, calc.get('kWp')))}</p>")
        elif y and calc.get("kWp"):
            o.append(f"<h3>Producția estimată</h3><p>{_e(pvgis.paragraf_memoriu(pvgis.din_valoare(y, calc['kWp'])))}</p>")
        try:
            pc = dt.pierderi_cabluri(model, r, calc, y)
            if pc.get("aplicabil"):
                o.append("<h3>Pierderi de putere în cabluri</h3><p>"
                         + (f"La puterea nominală: c.c. {_n(pc['cc']['P_pierderi_kW'], 2)} kW ({_n(pc['cc']['pct'], 2)} %), "
                            if pc["cc"]["pct"] is not None else "La puterea nominală: c.c. necalculat (kWp nedeclarat), ")
                         + f"c.a. {_n(pc['ca']['P_pierderi_kW'], 2)} kW ({_n(pc['ca']['pct'], 2)} %). Energie anuală pierdută "
                         f"estimată ≈ {_n(pc['energie_pierduta_kWh']['total'], 0)} kWh/an "
                         f"({_n(pc['energie_pierduta_pct'], 2)} % din producție). Metoda: {_e(pc['metoda'])}.</p>"
                         + ("<ul>" + "".join(f"<li>{_e(x)}</li>" for x in pc["avertismente"]) + "</ul>" if pc["avertismente"] else "")
                         + (f"<p class='pasi'>Presupus: {_e('; '.join(pc['presupus']))}</p>" if pc["presupus"] else ""))
        except Exception:
            pass
    if not o:
        return []
    return [f"<h2>{nr}. Măsuri și evaluări suplimentare</h2>"] + o


def genereaza_html(model, r):
    k = model.get("cartus") or {}
    calc = model.get("calc") or {}
    blocant = [v for v in r.get("verificari", []) if v.get("nivel") == "BLOCANT"]
    av = [v for v in r.get("verificari", []) if v.get("nivel") == "AVERTISMENT"]
    o = [f"<!doctype html><html lang='ro'><head><meta charset='utf-8'><title>Memoriu de calcul</title><style>{CSS}</style></head><body>"]
    o.append(f"<h1>Memoriu de calcul — {_e(k.get('denumire2') or 'schemă monofilară')}</h1>")
    o.append(f"<div class='meta'>Beneficiar: {_e(k.get('beneficiar') or '—')} · Amplasament: {_e(k.get('adresa') or '—')} · "
             f"Proiect nr. {_e(k.get('nr_pr') or '—')} · Faza {_e(k.get('faza') or '—')} · Planșa {_e(k.get('plansa') or '—')} rev. {_e(k.get('rev') or '0')}<br>"
             f"Proiectant: {_e(k.get('proiectant') or '—')} · Proiectat: {_e(k.get('proiectat') or '—')} · Verificat: {_e(k.get('verificat') or '—')}</div>")
    priza = (r.get("rezultat") or {}).get("priza") if isinstance(r.get("rezultat"), dict) else None
    rz = r.get("rezultat") if isinstance(r.get("rezultat"), dict) else {}
    loc = bool(rz.get("grupe_DDR"))
    # capitole opționale: 4 „Bilanț și repartizarea pe faze” (locuință, v1.4), apoi „Priza de pământ” (v1.3)
    cap_loc = 4 if loc else None
    cap_pr = (5 if loc else 4) if priza else None
    cap_v = 4 + bool(loc) + bool(priza)
    o.append(f"<p class='stop'>Rezultat: EXPORT BLOCAT — există verificări neîndeplinite (vezi cap. {cap_v}).</p>" if blocant else
             "<p class='ok'>Rezultat: toate verificările blocante sunt îndeplinite.</p>")
    o.append("<h2>1. Date de intrare</h2><table>")
    for kk, v in calc.items():
        if kk in ("plecari", "invertoare", "priza", "aparate", "note", "parametri", "circuite") or v is None or \
                str(kk).startswith("_"):
            continue
        o.append(f"<tr><th style='width:35%'>{_e(_et(kk))}</th><td>{_e(_val(v, kk))}</td></tr>")
    o.append("</table>")
    if calc.get("invertoare"):
        o.append("<table><tr><th>Grup invertoare</th><th>Model (fișa tehnică)</th><th>Număr</th><th>Pn [kW]</th><th>Iac,max [A]</th><th>L [m]</th>"
                 "<th>Cablu</th></tr>")
        from .calc.fise import model_text
        for i, g in enumerate(calc["invertoare"], 1):
            fis = {k: v for k, v in g.items() if k in ("Umax_dc_V", "MPPT_min_V", "MPPT_max_V", "nr_MPPT", "Idc_max_A", "Isc_max_A")}
            mt = model_text(g)
            o.append(f"<tr><td>{i}</td><td>{_e(mt or '—')}{('<br><small>' + _e(_val(fis)) + '</small>') if fis else ''}</td>"
                     f"<td class='n'>{_n(g.get('n', 1), 0)}</td><td class='n'>{_n(g.get('Pn_kW'))}</td>"
                     f"<td class='n'>{_n(g.get('Iac_max_A')) if g.get('Iac_max_A') else '—'}</td>"
                     f"<td class='n'>{_n(g.get('L_m'), 0) if g.get('L_m') else '—'}</td>"
                     f"<td>{_e(_val(g.get('cablu'))) if g.get('cablu') else '—'}</td></tr>")
        o.append("</table>")
    if isinstance(calc.get("circuite"), list):
        o.append("<table><tr><th>Circuit</th><th>Receptor</th><th>P [kW]</th><th>L [m]</th><th>Fază</th><th>Alte date</th></tr>")
        for c in calc["circuite"]:
            if not isinstance(c, dict):
                continue
            alte = {x: y for x, y in c.items() if x not in ("nume", "receptor", "P_kW", "L_m", "faza")}
            o.append(f"<tr><td>{_e(c.get('nume'))}</td><td>{_e(c.get('receptor') or '')}</td>"
                     f"<td class='n'>{_n(c.get('P_kW')) if c.get('P_kW') else '—'}</td>"
                     f"<td class='n'>{_n(c.get('L_m'), 0) if c.get('L_m') else '—'}</td><td>{_e(c.get('faza') or '—')}</td>"
                     f"<td>{_e(_val(alte)) if alte else ''}</td></tr>")
        o.append("</table>")
    if isinstance(calc.get("priza"), dict):
        o.append("<table><tr><th>Priza de pământ (date)</th><th>Valoare</th></tr>")
        for kk, v in calc["priza"].items():
            if v is None:
                continue
            o.append(f"<tr><td>{_e(_et(kk))}</td><td>{_e(_val(v, kk))}</td></tr>")
        o.append("</table>")
    if calc.get("plecari"):
        o.append("<table><tr><th>Plecare</th><th>Putere / calibru</th><th>L [m]</th><th>Receptor</th><th>Circuite</th>"
                 "<th>Alte date</th></tr>")
        for pl in calc["plecari"]:
            val = f"{_n(pl['P_kW'])} kW" if pl.get("P_kW") is not None else (f"{pl.get('In_A')} A" if pl.get("In_A") else "Σ circuite")
            o.append(f"<tr><td>{_e(pl.get('nume'))}</td><td>{val}</td><td class='n'>{_n(pl.get('L_m'), 0)}</td><td>{_e(pl.get('receptor') or '')}</td>"
                     f"<td>{_e(', '.join(c.get('nume', '') for c in pl.get('copii') or []))}</td>"
                     f"<td>{_e(_val({x: y for x, y in pl.items() if x not in ('nume', 'P_kW', 'In_A', 'L_m', 'receptor', 'copii')}))}</td></tr>")
        o.append("</table>")
    o.append("<h2>2. Ipoteze de calcul și valori presupuse</h2><ul>")
    o += [f"<li>{_e(x)}</li>" for x in r.get("ipoteze", [])]
    o.append("</ul><p><b>Valori presupuse (de confirmat):</b></p><ul>")
    o += [f"<li>{_e(x)}</li>" for x in r.get("presupus", [])] or ["<li>—</li>"]
    o.append("</ul>")
    o.append("<h2>3. Tabelul de calcul pe ramuri</h2><table><tr><th>Ramură</th><th>Ib [A]</th><th>Protecție</th><th>Icu [kA]</th>"
             "<th>Cablu</th><th>L [m]</th><th>Iz' [A]</th><th>ΔU ram. [%]</th><th>ΔU cum. [%]</th><th>Ik3 bară [kA]</th>"
             "<th>Ik1 capăt [A]</th><th>Ia [A]</th><th>t [s]</th></tr>")
    obiecte_b = {v.get("obiect") for v in blocant}
    for nume, b in _ramuri(r.get("rezultat") or {}):
        cls = " class='B'" if nume in obiecte_b else ""
        p = b.get("protectie") or {}
        o.append(f"<tr{cls}><td>{_e(nume)}</td><td class='n'>{_n(b.get('Ib_A'))}</td><td>{_e(_prot(p, b))}</td><td class='n'>{_n(p.get('Icu_kA'), 0)}</td>"
                 f"<td>{_e(b.get('cablu'))}</td><td class='n'>{_n(b.get('L_m'), 0)}</td><td class='n'>{_n(b.get('Iz_corectat_A'))}</td>"
                 f"<td class='n'>{_n(b.get('dU_ramura_pct'), 2)}</td><td class='n'>{_n(b.get('dU_cumulat_pct'), 2)} / {_n(b.get('dU_limita_pct'), 0)}</td>"
                 f"<td class='n'>{_n(b.get('Ik3max_origine_kA'), 2)}</td><td class='n'>{_n(b.get('Ik1min_capat_A'), 0)}</td>"
                 f"<td class='n'>{_n(b.get('Ia_A'), 0)}</td><td class='n'>{_n(b.get('t_deconectare_s'), 1)}</td></tr>")
    o.append("</table>")
    if loc:
        o += _cap_locuinta(rz, cap_loc)
    if priza:
        o += _cap_priza(priza, cap_pr)
    o.append(f"<h2>{cap_v}. Verificări</h2>")
    if not (blocant or av):
        o.append("<p>Nicio verificare blocantă sau avertisment.</p>")
    else:
        o.append("<table><tr><th>Cod</th><th>Nivel</th><th>Obiect</th><th>Constatare</th><th>Remediere</th></tr>")
        for v in blocant + av:
            c = "B" if v["nivel"] == "BLOCANT" else "A"
            o.append(f"<tr class='{c}'><td>{_e(v.get('cod'))}</td><td>{_e(v.get('nivel'))}</td><td>{_e(v.get('obiect'))}</td>"
                     f"<td>{_e(v.get('mesaj'))}</td><td>{_e(v.get('remediere'))}</td></tr>")
        o.append("</table>")
    info = r.get("info") or []
    if info:
        o.append("<p><b>Verificări îndeplinite (INFO):</b></p><ul class='pasi'>")
        o += [f"<li>{_e(v.get('cod'))} · {_e(v.get('obiect'))}: {_e(v.get('mesaj'))}</li>" for v in info]
        o.append("</ul>")
    o.append(f"<h2>{cap_v + 1}. Pașii de calcul</h2><ol class='pasi'>")
    o += [f"<li>{_e(x)}</li>" for x in r.get("pasi", [])]
    o.append("</ol><p class='pasi'>Date normative: SR HD 60364-4-41, -4-43, -5-52:2011, -5-54; I7-2011; SR EN 60909-0; ST 4-JT Rev. 3/2024, "
             "ST 3-JT (DEER). Valorile marcate „presupus” trebuie confirmate cu datele din ATR / fișele producătorilor.</p>")
    o += _cap_e2(model, r, cap_v + 2)
    o.append("</body></html>")
    return "\n".join(o)
