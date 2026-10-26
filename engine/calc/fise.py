"""fise.py — datele din fișele tehnice ale echipamentelor (modul PV, invertor, BESS/PCS, SPD c.c., gPV) în calcul.

Intrarea fizică acceptă, pe lângă parametrii de calcul, modelul și datele de fișă:

* `modul` (la nivel de schemă) sau `string.modul`: {producator, model, Pmax_W, Voc_V, Isc_A, Vmpp_V, Impp_A,
  beta_Voc_pct_K, Umax_sistem_V, I_rev_A, ...};
* `invertoare[]` (CEF) / `invertor` (prosumator): {producator, model, Pn_kW, Iac_max_A, Umax_dc_V, MPPT_min_V,
  MPPT_max_V, Idc_max_A, Isc_max_A, nr_MPPT, ...};
* `bess` (CEF) / `baterie` (prosumator hibrid): {producator, model, P_kW, kWh, Iac_max_A, ...};
* `spd_cc`, `gpv`: {producator, model, ...}.

`aplica(inp, j, tip)` completează cheile de calcul din fișe (datele de fișă înlocuiesc presupunerile) și declară
sursa fiecărei valori în pașii de calcul. Cheile vechi (`string.Uoc_V`, `string.beta`, `string.Umax_inv_V`) rămân
valabile ca alias; în texte se scrie **Voc**, ca în fișele tehnice. `verifica_mppt` face verificările de compatibilitate
modul–invertor (V89, AVERTISMENT).
"""
from .comun import gt, lt
from .texte import fmt_ro
from .verificari import emite, AVERTISMENT, INFO

T_MAX_CELULA_C = 70.0          # DECIZIE: temperatura maximă a celulei pentru fereastra MPPT (vară, montaj pe acoperiș)

# cheile de fișă care NU sunt parametri de calcul (descriptive) — se păstrează doar pentru desen și listă
CHEI_DESCRIPTIVE = ("producator", "model", "id", "sursa", "tehnologie", "chimie", "observatii", "variante")


def model_text(d):
    """„Producător Model” dintr-o fișă (fără dublarea producătorului dacă modelul îl conține deja)."""
    if not isinstance(d, dict):
        return ""
    p = str(d.get("producator") or "").strip()
    m = str(d.get("model") or "").strip()
    if p and m.lower().startswith(p.lower()):
        p = ""
    return " ".join(x for x in (p, m) if x)


def modul_din(inp):
    """fișa modulului: `string.modul` are prioritate față de `modul` de la nivelul schemei."""
    st = inp.get("string") if isinstance(inp.get("string"), dict) else {}
    m = st.get("modul") if isinstance(st.get("modul"), dict) else None
    return m or (inp.get("modul") if isinstance(inp.get("modul"), dict) else None)


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def aplica(inp, j, tip):
    """Completează intrarea `inp` (copie de lucru a motorului) din fișele tehnice. Modifică `inp` pe loc."""
    mod = modul_din(inp)
    st = inp.get("string")
    if isinstance(st, dict):
        # aliasuri: denumirile din fișe (Voc, β(Voc)) = cheile vechi ale motorului (Uoc_V, beta)
        if st.get("Uoc_V") is None and _num(st.get("Voc_V")):
            st["Uoc_V"] = st["Voc_V"]
        if st.get("beta") is None and _num(st.get("beta_Voc_pct_K")):
            st["beta"] = st["beta_Voc_pct_K"]
        if mod:
            mt = model_text(mod) or "modul"
            for k_st, k_mod, et, um in (("Uoc_V", "Voc_V", "Voc", "V"), ("Isc_A", "Isc_A", "Isc", "A"),
                                        ("beta", "beta_Voc_pct_K", "β(Voc)", "%/K"),
                                        ("Umax_modul_V", "Umax_sistem_V", "Umax sistem modul", "V"),
                                        ("I_rev_A", "I_rev_A", "curent invers admis (siguranța maximă în serie)", "A")):
                if st.get(k_st) is None and _num(mod.get(k_mod)):
                    st[k_st] = mod[k_mod]
                    j.pas(f"{et} = {fmt_ro(mod[k_mod])} {um} — din fișa modulului {mt}")
        if st.get("Umax_inv_V") is None:
            surse = []
            if tip == "cef":
                surse = [g for g in inp.get("invertoare") or [] if isinstance(g, dict) and _num(g.get("Umax_dc_V"))]
            elif tip == "prosumator" and isinstance(inp.get("invertor"), dict) and _num(inp["invertor"].get("Umax_dc_V")):
                surse = [inp["invertor"]]
            if surse:
                g = min(surse, key=lambda x: x["Umax_dc_V"])
                st["Umax_inv_V"] = g["Umax_dc_V"]
                j.pas(f"Umax c.c. invertor = {fmt_ro(g['Umax_dc_V'])} V — din fișa invertorului {model_text(g) or ''}".rstrip())
    if tip == "prosumator":
        inv = inp.get("invertor")
        if isinstance(inv, dict):
            if inp.get("Pn_inv_kW") is None and _num(inv.get("Pn_kW")):
                inp["Pn_inv_kW"] = inv["Pn_kW"]
            if inp.get("Iac_max_A") is None and _num(inv.get("Iac_max_A")):
                inp["Iac_max_A"] = inv["Iac_max_A"]
                j.pas(f"Iac,max = {fmt_ro(inv['Iac_max_A'])} A — din fișa invertorului {model_text(inv)}".rstrip())
            if inv.get("hibrid") and not inp.get("hibrid"):
                inp["hibrid"] = True
        # v1.9 (R5): `baterie` = baterie pe portul invertorului hibrid; `bess` (P_kW, kWh) poate fi și PCS separat (cuplaj c.a.)
        bat = inp.get("baterie") if isinstance(inp.get("baterie"), dict) else None
        if bat and not inp.get("hibrid"):
            inp["hibrid"] = True
    if tip == "cef":
        for g in inp.get("invertoare") or []:
            if isinstance(g, dict) and _num(g.get("Iac_max_A")) and model_text(g):
                j.pas(f"Iac,max = {fmt_ro(g['Iac_max_A'])} A — din fișa invertorului {model_text(g)}")
        b = inp.get("bess")
        if isinstance(b, dict) and _num(b.get("Iac_max_A")) and model_text(b):
            j.pas(f"Iac,max PCS = {fmt_ro(b['Iac_max_A'])} A — din fișa {model_text(b)}")
    return inp


def verifica_mppt(inp, j, tip, beta):
    """V89 (AVERTISMENT): stringul în fereastra MPPT a invertorului și curentul de c.c. pe intrarea MPPT, când fișele
    modulului și ale invertorului dau datele (Vmpp, Isc / MPPT_min, MPPT_max, Isc_max, Idc_max)."""
    st = inp.get("string") if isinstance(inp.get("string"), dict) else None
    mod = modul_din(inp) or {}
    if not st or not st.get("n_module"):
        return
    n = int(st["n_module"])
    npar = int(st.get("n_stringuri_paralel") or 1)
    vmpp = st.get("Vmpp_V") if _num(st.get("Vmpp_V")) else mod.get("Vmpp_V")
    impp = st.get("Impp_A") if _num(st.get("Impp_A")) else mod.get("Impp_A")
    isc = st.get("Isc_A")
    invs = (inp.get("invertoare") or []) if tip == "cef" else [inp.get("invertor")]
    vazute = set()
    for i, g in enumerate(invs, 1):
        if not isinstance(g, dict):
            continue
        ob = model_text(g) or (f"invertor grup {i}" if tip == "cef" else "invertor")
        if ob in vazute:
            continue
        vazute.add(ob)
        if _num(vmpp):
            u_cald = n * vmpp * (1 + beta / 100.0 * (T_MAX_CELULA_C - 25.0))
            u_stc = n * vmpp
            if _num(g.get("MPPT_min_V")) and lt(u_cald, g["MPPT_min_V"]):
                emite(j, "V89", AVERTISMENT, ob, "min", x=round(u_cald, 1), y=g["MPPT_min_V"], n=n)
            elif _num(g.get("MPPT_max_V")) and gt(u_stc, g["MPPT_max_V"]):
                emite(j, "V89", AVERTISMENT, ob, "max", x=round(u_stc, 1), y=g["MPPT_max_V"], n=n)
            elif _num(g.get("MPPT_min_V")) or _num(g.get("MPPT_max_V")):
                emite(j, "V89", INFO, ob, "ok", x=round(u_cald, 1), z=round(u_stc, 1),
                      a=fmt_ro(g.get("MPPT_min_V")) if _num(g.get("MPPT_min_V")) else "—",
                      b=fmt_ro(g.get("MPPT_max_V")) if _num(g.get("MPPT_max_V")) else "—")
            j.pas(f"Vmpp string: {n}·{fmt_ro(vmpp)} = {fmt_ro(u_stc, 1)} V (STC); la {fmt_ro(T_MAX_CELULA_C)} °C ≈ "
                  f"{fmt_ro(u_cald, 1)} V (β(Voc) aplicat și lui Vmpp — aproximare conservatoare)")
        if _num(isc) and _num(g.get("Isc_max_A")) and gt(npar * isc, g["Isc_max_A"]):
            emite(j, "V89", AVERTISMENT, ob, "isc", x=npar * isc, y=g["Isc_max_A"], np=npar)
        elif _num(impp) and _num(g.get("Idc_max_A")) and gt(npar * impp, g["Idc_max_A"]):
            emite(j, "V89", AVERTISMENT, ob, "idc", x=npar * impp, y=g["Idc_max_A"], np=npar)
