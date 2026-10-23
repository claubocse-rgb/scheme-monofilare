"""scheme.py — regulile pe tip de schemă (SPEC §C.1–§C.6), verificarea modelului (V80/V81, SPEC §E.1) și
punctul de intrare `calculeaza(intrare)`.

    calculeaza(intrare) -> {"rezultat", "verificari", "info", "blocheaza_export", "presupus", "pasi", "ipoteze"}

`intrare` are exact forma câmpului "intrare" din tests/date/cazuri_golden.json.
"""
import copy
import math
import unicodedata

from . import norme
from . import protectii as pr
from . import scurtcircuit as sc
from .comun import Jurnal, ge, gt, lt, eq, prima_din_serie, u_calcul, SQRT3
from .ramura import calculeaza_ramura, valideaza
from . import cabluri as cb
from . import ddr as ddr_mod
from . import pamant
from .texte import fmt_ro, NB, X, note_generate, verifica_aparat, verifica_nota, nota_bransament, nota_schema_pamant
from .verificari import emite, BLOCANT, AVERTISMENT, INFO

DT_QG = norme.DDR_DT_SELECTIVITATE_S         # Δt al blocului diferențial reglabil pe intrarea TT (v1.3 R5)
RCCB_IN_BRANSAMENT = [16, 25, 40, 63, 80, 100, 125, 160, 200, 250]   # SPEC §C.1 (peste 125 A: bloc diferențial, M11)
CAMPURI_CABLU_SCHEMA = ("material", "izolatie", "metoda", "theta", "rho_sol", "n_alte", "S_fortat", "n_fortat",
                        "N_fortat", "PE_fortat", "PE_loc", "distanta", "aranjament")
C1_TEXT = "racord OD — nu se dimensionează în proiectul consumatorului"


# ============================================================================================================
# utilitare comune schemelor
# ============================================================================================================
def _fara_diacritice(s):
    """Copia de lucru fără diacritice, litere mici (SPEC §C.2 „Receptorul după nume”, §F.2 pct. 2)."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower()


def receptor_dupa_nume(nume, nivel):
    """SPEC §C.2, „Receptorul după nume”: ilumin → iluminat; priz → prize; motor/pomp/compresor/ventila/moar/
    concasor/malaxor → motor; altfel tablou (nivel 0) sau forță (nivel ≥ 1)."""
    n = _fara_diacritice(nume)
    if "ilumin" in n:
        return "iluminat"
    if "priz" in n or "socket" in n:
        return "prize"
    if any(k in n for k in ("motor", "pomp", "compresor", "ventila", "moar", "concasor", "malaxor")):
        return "motor"
    return "tablou" if nivel == 0 else "forta"


def _zb_din_intrare(zb, j):
    """M2 (v1.2): impedanța buclei OD din ATR — perechea (R, X), dict {R, X} sau modulul |Z| (număr). La modul,
    R/X = 2 (raportul valorii implicite 0,18 + j0,09 Ω, rețea rurală LEA/LES) — declarat ca presupus."""
    if zb is None:
        return None
    if isinstance(zb, dict):
        return (float(zb.get("R", zb.get("R_ohm", 0.0))), float(zb.get("X", zb.get("X_ohm", 0.0))))
    if isinstance(zb, (list, tuple)):
        return (float(zb[0]), float(zb[1]))
    z = float(zb)
    r0, x0 = norme.OD_ZBUCLA_IMPLICIT_OHM
    m0 = math.hypot(r0, x0)
    j.presupune(f"Zbuclă OD dată ca modul |Z| = {fmt_ro(z, 3)} Ω: R/X = {fmt_ro(r0 / x0)} presupus (ca la valoarea "
                f"implicită 0,18 + j0,09 Ω) → Zb = {fmt_ro(z * r0 / m0, 3)} + j{fmt_ro(z * x0 / m0, 3)} Ω")
    return (z * r0 / m0, z * x0 / m0)


def _context_od(inp, j, ddr_amonte):
    """SPEC §B.0 și §B.13: contextul rețelei OD la punctul de delimitare, cu declararea valorilor implicite.
    M9 (v1.2): cu Ik3 dat și Zb implicit, Zb implicit se ridică la cel puțin 2·Z_Q (pe componente), astfel încât
    Ik1min ≤ Ik3max pe orice ramură."""
    ik3 = inp.get("Ik3_OD_kA")
    zb = _zb_din_intrare(inp.get("Zb_OD_ohm"), j)
    ctx = sc.context_od(ik3, zb, ddr_amonte=ddr_amonte, schema="TT" if inp.get("schema_pamant") == "TT" else "TN")
    if ik3 is None:
        j.presupune(f"Ik3max OD la punctul de delimitare {fmt_ro(norme.OD_IK3MAX_IMPLICIT_KA)} kA (valoare implicită "
                    f"presupusă — se confirmă cu OD / ATR)")
    if zb is None:
        if ctx.get("zb_ajustat"):
            j.presupune(f"Zbuclă OD implicită ridicată la 2·Z_Q = {fmt_ro(ctx['Zb'][0], 3)} + j{fmt_ro(ctx['Zb'][1], 3)} Ω "
                        f"(consistentă cu Ik3 OD = {fmt_ro(ctx['Ik3_kA'])} kA; Ik1min ≤ Ik3max) — presupusă, se confirmă cu OD / ATR")
        else:
            j.presupune("Zbuclă OD 0,18 + j0,09 Ω (|Z| = 0,201 Ω, valoare implicită presupusă — se confirmă cu OD / ATR)")
    j.ipoteza("ik3_od", ctx["Ik3_kA"], ik3 is None)
    # v1.7 (§C.8, N11): Zb presupus după zonă (locuință rurală) — marcat presupus, cu sursa, nu „declarat”
    j.ipoteza("zb_od", sc.modul(ctx["Zb"]), inp.get("_zb_presupus") or zb is None)
    return ctx


# ============================================================================================================
# v1.2: validarea intrării schemei (C7, C8, C10, M2, M8 din verificarea independentă)
# ============================================================================================================
RETELE = {"tri": "tri", "trifazat": "tri", "trifazic": "tri", "trifazata": "tri", "trifazica": "tri", "3f": "tri",
          "mono": "mono", "monofazat": "mono", "monofazic": "mono", "monofazata": "mono", "monofazica": "mono", "1f": "mono"}
# v1.5: rețeaua nu se presupune la tipurile la care monofazat / trifazat schimbă tot blocul de măsură (BMPM / BMPT)
RETEA_OBLIGATORIE = ("locuinta", "bransament", "prosumator")
SCHEME_PAMANT = ("TN-C-S", "TN-S", "TT", "TN-C")
SPL_ACCEPTATE = {"bransament": ("TN-C-S", "TT"), "tablou": ("TN-C-S", "TN-S", "TT", "TN-C"),
                 "cascada": ("TN-C-S", "TN-S", "TT", "TN-C"), "prosumator": ("TN-C-S", "TN-S", "TT"),
                 "cef": ("TN-C-S", "TN-S", "TT"), "cef_pt": ("TN-S", "TN-C-S"), "pt": ("TN-S", "TN-C-S", "TN-C"),
                 "ge_ats": ("TN-S", "TN-C-S"), "locuinta": ("TN-C-S", "TT")}
TIPURI_PROT = {"MCB", "MCCB", "ACB", "GG"}

# câmp → (condiție, cod, text) ; condiții: ">0", ">=0", "(0,1]", "[0,100]", "int>=1", "int>=0"
CAMPURI_NUMERICE = {
    "P_kW": (">0", "V07"), "S_kVA": (">0", "V07"), "Ib_A": (">0", "V07"), "In_A": (">0", "V07"),
    "Pn_kW": (">0", "V07"), "Pn_inv_kW": (">0", "V07"), "Iac_max_A": (">0", "V07"), "kWh": (">0", "V07"),
    "P_sarcina_kW": (">0", "V07"), "Ib_sarcina_A": (">0", "V07"), "Sn_GE_kVA": (">0", "V07"),
    "Sn_kVA": (">0", "V05"), "pt_Sn_kVA": (">0", "V05"),
    "L_coloana_m": (">0", "V09"), "L_alimentare_m": (">0", "V09"), "L_inv_m": (">0", "V09"), "L_pcs_m": (">0", "V09"),
    "L_m": (">0", "V09"), "L": (">0", "V09"), "L_C1_m": (">0", "V09"), "L_C2_m": (">0", "V09"),
    "L_C3_m": (">0", "V09"),
    "cosfi": ("(0,1]", "V08"), "ks": ("(0,1]", "V10"),
    "Ik3_OD_kA": (">0", "V07"), "SkQ_MVA": (">0", "V07"), "xd": ("(0,1]", "V07"), "RA_ohm": (">0", "V07"),
    "h3": ("[0,100]", "V07"), "h3_pct": ("[0,100]", "V07"), "kWp": (">=0", "V07"),
    "In_Q_bransament_A": (">0", "V07"), "In_QG_A": (">0", "V07"), "In_Q1_A": (">0", "V07"), "In_Q_JT_A": (">0", "V07"),
    "Q_In_A": (">0", "V07"), "In_Q_retea_A": (">0", "V07"), "In_fortat": (">0", "V07"), "Icu_fortat": (">0", "V07"),
    "rho_sol": (">0", "V10"), "theta": ("num", "V10"), "n_alte": ("int>=0", "V10"), "S_fortat": (">0", "V13"),
    "n_fortat": ("int>=1", "V07"), "N_fortat": (">0", "V07"), "PE_fortat": (">0", "V07"),
    "n": ("int>=1", "V07"), "n_module": ("int>=1", "V07"), "Uoc_V": (">0", "V07"), "Umax_inv_V": (">0", "V07"),
    "Umax_modul_V": (">0", "V07"), "Isc_A": (">0", "V07"), "I_rev_A": (">0", "V07"),
    "n_stringuri_paralel": ("int>=1", "V07"), "beta": ("num", "V07"), "ATS_poli": ("int>=1", "V07"),
    "dU_origine_pct": (">=0", "V07"), "IdN_amonte_mA": (">0", "V07"),
    "L_racord_m": (">0", "V09"), "racord_In_Q_A": (">0", "V07"), "Ik3_TG_kA": (">0", "V07"),
    "racord_Icu_kA": (">0", "V07"), "P_aprobata_kW": (">0", "V07"),
}
TEXT_CONDITIE = {">0": "trebuie > 0", ">=0": "trebuie ≥ 0", "(0,1]": "trebuie în intervalul (0; 1]",
                 "[0,100]": "trebuie în intervalul [0; 100] %", "int>=1": "trebuie număr întreg ≥ 1",
                 "int>=0": "trebuie număr întreg ≥ 0", "num": "trebuie să fie număr"}


def _numar(v):
    """True dacă v este un număr finit (nu bool, nu text, nu NaN/inf)."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _cond_ok(cond, v):
    """Verifică o condiție din CAMPURI_NUMERICE pe valoarea numerică v."""
    if cond == ">0":
        return v > 0
    if cond == ">=0":
        return v >= 0
    if cond == "(0,1]":
        return 0 < v <= 1
    if cond == "[0,100]":
        return 0 <= v <= 100
    if cond == "int>=1":
        return float(v).is_integer() and v >= 1
    if cond == "int>=0":
        return float(v).is_integer() and v >= 0
    return True


def _emite_param(j, obiect, camp, v, cond, cod):
    """Mesajul BLOCANT pentru un câmp numeric invalid, cu codul catalogului (V05/V07/V08/V09/V10/V13)."""
    x = v if _numar(v) else repr(v)
    if not _numar(v):
        emite(j, "V07", BLOCANT, obiect, "param", camp=camp, x=x, conditie="valoare nenumerică (se așteaptă un număr)")
    elif cod == "V08":
        emite(j, "V08", BLOCANT, obiect, "B", x=v)
    elif cod == "V09":
        emite(j, "V09", BLOCANT, obiect, "B", L=v)
    elif cod == "V10":
        tabel = {"ks": "ks ∈ (0; 1]", "rho_sol": "B.52.16 (ρ > 0)",
                 "theta": "B.52.14/B.52.15", "n_alte": "B.52.17–B.52.19 (n întreg ≥ 0)"}.get(camp, "B.52.x")
        emite(j, "V10", BLOCANT, obiect, parametru=f"{camp} = {fmt_ro(v)}", tabel=tabel)
    elif cod == "V07" and camp in ("P_kW", "P_sarcina_kW", "Pn_kW", "Pn_inv_kW") and v <= 0:
        emite(j, "V07", BLOCANT, obiect, P=v)
    else:
        emite(j, "V07", BLOCANT, obiect, "param", camp=camp, x=x, conditie=TEXT_CONDITIE[cond])


def _fd(x):
    """Text normalizat pentru valorile enumerate: fără diacritice, litere mici, „-”/spațiu → „_”."""
    return _fara_diacritice(str(x)).strip().replace("-", "_").replace(" ", "_")


# v1.2 R2 (N-M3): valorile enumerate acceptate (după normalizare) → valoarea canonică
ENUMERARI = {
    "pornire": {"directa": "directa", "direct": "directa", "dol": "directa", "stea_triunghi": "stea_triunghi",
                "y_d": "stea_triunghi", "soft": "soft", "soft_starter": "soft", "softstarter": "soft", "vfd": "vfd",
                "convertizor": "vfd"},
    "receptor": {"iluminat": "iluminat", "prize": "prize", "priza": "prize", "forta": "forta", "motor": "motor",
                 "tablou": "tablou", "invertor": "invertor", "pcs": "pcs"},
    "origine": {"retea_publica": "retea_publica", "pt_propriu": "pt_propriu"},
    "masura_ceruta": {"semidirecta": "semidirecta", "directa": "directa"},
    "PE_loc": {"cablu": "cablu", "separat": "separat"},
    "rol": {"plecare": "plecare", "final": "final"},
    "racord": {"tg_existent": "tg_existent", "tg": "tg_existent", "bmpt": "bmpt", "pt": "pt", "pt_propriu": "pt"},
}
CHEI_ENUM_NULE = ("retea", "schema_pamant", "pornire", "receptor", "origine", "masura_ceruta", "PE_loc", "rol", "racord",
                  "racord_Q_tip",
                  "material", "izolatie", "metoda", "prot_tip", "Q1_tip", "curba", "celula_trafo", "masura_pt",
                  "bmpt_fortat")


def _valideaza_dict(d, j, obiect, sari=()):
    """Verifică tipul (număr finit) și domeniul câmpurilor numerice ale unui dict de intrare, plus materialul,
    izolația, metoda de pozare, tipul protecției și curba. Întoarce False la primul câmp invalid."""
    # N-C3 (R2): o cheie enumerată cu valoarea null = absentă (se aplică valoarea implicită, declarată)
    for k in CHEI_ENUM_NULE:
        if k in d and d[k] is None:
            d.pop(k)
            if k == "retea":
                j.presupune("rețea nedeclarată (null) → trifazată 3 × 400/230 V (implicit)")
    for k, acc in ENUMERARI.items():
        if k in d:
            v = d[k]
            canon = acc.get(_fd(v)) if isinstance(v, str) else None
            if canon is None:
                emite(j, "V12", BLOCANT, obiect, "camp", camp=k, valoare=v)
                return False
            d[k] = canon
    ct = d.get("celula_trafo")
    if ct is not None:
        c0 = _fd(ct) if isinstance(ct, str) else ""
        if c0.startswith("sig"):
            d["celula_trafo"] = "sigurante"
        elif c0.startswith("intr"):
            d["celula_trafo"] = "intreruptor"
        else:
            emite(j, "V12", BLOCANT, obiect, "camp", camp="celula_trafo", valoare=ct)
            return False
    for camp, v in d.items():
        if camp in CAMPURI_NUMERICE and v is not None:
            cond, cod = CAMPURI_NUMERICE[camp]
            if not _numar(v) or (camp not in sari and not _cond_ok(cond, v)):
                _emite_param(j, obiect, camp, v, cond, cod)
                return False
    mat = d.get("material")
    if mat is not None:
        m = str(mat).strip().capitalize() if isinstance(mat, str) else ""
        if m not in ("Cu", "Al"):
            emite(j, "V10", BLOCANT, obiect, parametru=f"material „{mat}”", tabel="B.52.2–B.52.13 (numai Cu sau Al)")
            return False
        d["material"] = m
    iz = d.get("izolatie")
    if iz is not None:
        i = str(iz).strip().upper() if isinstance(iz, str) else ""
        if i not in ("PVC", "XLPE"):
            emite(j, "V10", BLOCANT, obiect, parametru=f"izolație „{iz}”", tabel="B.52.2–B.52.13 (numai PVC sau XLPE)")
            return False
        d["izolatie"] = i
    met = d.get("metoda")
    if met is not None:
        mm = str(met).strip().upper() if isinstance(met, str) else ""
        mm = {"F_TREFLA": "F_trefla", "F_ATINGERE": "F_atingere"}.get(mm, mm)
        if mm not in norme.METODE_POZARE:
            emite(j, "V10", BLOCANT, obiect, parametru=f"metoda de pozare „{met}”",
                  tabel=f"B.52.x (metode acceptate: {', '.join(norme.METODE_POZARE)})")
            return False
        d["metoda"] = mm
    for k in ("prot_tip", "Q1_tip", "racord_Q_tip"):
        t = d.get(k)
        if t is not None and (not isinstance(t, str) or t.strip().upper() not in TIPURI_PROT):
            emite(j, "V12", BLOCANT, obiect, "camp", camp=k, valoare=t)
            return False
    c = d.get("curba")
    if c is not None and (not isinstance(c, str) or c.strip().upper() not in ("B", "C", "D")):
        emite(j, "V12", BLOCANT, obiect, "camp", camp="curba", valoare=c)
        return False
    if c is not None:
        d["curba"] = str(c).strip().upper()
    r = d.get("retea")
    if r is not None:
        rn = RETELE.get(_fd(r)) if isinstance(r, str) else None
        if rn is None:
            emite(j, "V12", BLOCANT, obiect, "retea", retea=r)
            # v1.7 (m-c5): remedierea despre rețea, nu cea generică a V12 („o singură sursă de putere”)
            j.verificari[-1]["remediere"] = ("alege monofazat 230 V („mono”) sau trifazat 3 × 400 V („tri”), conform "
                                             "ATR / branșamentului existent")
            j.verificari[-1]["camp"] = "retea"
            return False
        d["retea"] = rn
    return True


def _valideaza_plecari(plecari, j, prefix=""):
    """Validarea recursivă a plecărilor (tip/domeniu numeric, cablu, rețea); P/L/cosφ/ks rămân pe ramură (§B.2)."""
    if not isinstance(plecari, list):
        emite(j, "V07", BLOCANT, "schema", "param", camp="plecari", x=repr(plecari), conditie="se așteaptă o listă")
        return False
    for i, pl in enumerate(plecari, 1):
        ob = f"{prefix}P{i}·{pl.get('nume', '') if isinstance(pl, dict) else ''}"
        if not isinstance(pl, dict):
            emite(j, "V07", BLOCANT, ob, "param", camp="plecare", x=repr(pl), conditie="se așteaptă un obiect")
            return False
        # P ≤ 0, L ≤ 0, cosφ, ks rămân în §B.2 (validarea ramurii, cu obiectul ramurii)
        if not _valideaza_dict(pl, j, ob, sari=("P_kW", "In_A", "S_kVA", "L_m", "cosfi", "ks")):
            return False
        if isinstance(pl.get("DDR"), dict) and not _valideaza_ddr(pl["DDR"], j, ob, "DDR"):
            return False
        cab = pl.get("cablu")
        if cab is not None and (not isinstance(cab, dict) or not _valideaza_dict(cab, j, ob, sari=("L",))):
            return False
        if pl.get("copii") and not _valideaza_plecari(pl["copii"], j, ob.replace("P", "P", 1) + "."):
            return False
    return True


def _valideaza_ddr(d, j, obiect, camp):
    """v1.3 (§B.18.1): un DDR impus {IdN_mA ∈ seria RCD, selectiv: bool, tip: AC|A|F|B} — altfel V12 BLOCANT."""
    idn = d.get("IdN_mA")
    if not _numar(idn) or idn not in norme.RCD_IDN_MA:
        emite(j, "V12", BLOCANT, obiect, "camp", camp=f"{camp}.IdN_mA", valoare=idn)
        return False
    if "selectiv" in d and not isinstance(d["selectiv"], bool):
        emite(j, "V12", BLOCANT, obiect, "camp", camp=f"{camp}.selectiv", valoare=d["selectiv"])
        return False
    if d.get("dt_s") is not None and (not _numar(d["dt_s"]) or not 0 < d["dt_s"] <= 1.0):
        emite(j, "V12", BLOCANT, obiect, "camp", camp=f"{camp}.dt_s", valoare=d["dt_s"])
        return False
    if d.get("tip") is not None and str(d["tip"]).upper() not in ("AC", "A", "F", "B"):
        emite(j, "V12", BLOCANT, obiect, "camp", camp=f"{camp}.tip", valoare=d["tip"])
        return False
    return True


def _ddr_amonte(inp, retea="tri"):
    """v1.3 (§B.18.1): DDR-ul din amontele schemei (branșamentul): `IdN_amonte_mA` declarat (tip S după
    `DDR_amonte_selectiv`, implicit S) sau RCCB 300 mA S din BMPT (ST 4-JT, M11) / RCBO 300 mA din BMPM (ST 3-JT,
    instantaneu [NEVERIFICAT])."""
    idn = inp.get("IdN_amonte_mA")
    if idn is not None:
        return ddr_mod.descriere(idn, inp.get("DDR_amonte_selectiv", True), "DDR amonte (declarat)")
    if retea == "mono":
        return ddr_mod.descriere(norme.BMPM["idn_ma"], inp.get("DDR_amonte_selectiv", norme.BMPM_RCBO_SELECTIV),
                                 "RCBO BMPM")
    return ddr_mod.descriere(norme.BMPT_RCCB["idn_ma"], inp.get("DDR_amonte_selectiv", True), "RCCB BMPT")


def _valideaza_intrare(inp, j, tip):
    """SPEC §B.2 / §D (v1.2): validarea câmpurilor schemei înainte de calcul — numere finite și plauzibile (V07–V10, V13),
    rețea ∈ {tri, mono} cu sinonime evidente (V12), schema de legare la pământ acoperită (V28 / V27), Zb OD > 0,
    material/izolație/metodă cunoscute (V10). Întoarce False dacă schema se oprește."""
    if tip in RETEA_OBLIGATORIE and (inp.get("retea") is None or
                                     (tip == "locuinta" and isinstance(inp.get("retea"), str)
                                      and not inp["retea"].strip())):
        # v1.6 (m-n4): la locuință „retea”: "" = nespecificată → V07 (nu V12 „necunoscută”); la branșament / prosumator
        # rămâne V12 (contract v1.2, test_verificare2 C8)
        # v1.5: rețeaua lipsă (sau null) nu se presupune — BMPM / BMPT, Q, DDR 2P / 4P, faze depind de ea
        inp.pop("retea", None)
        j.emite("V07", BLOCANT, "retea", "rețeaua nu este specificată (monofazat sau trifazat)",
                "alege monofazat 230 V (BMPM) sau trifazat 3 × 400 V (BMPT), conform ATR / branșamentului existent")
        return False
    if not _valideaza_dict(inp, j, "schema"):
        return False
    zb = inp.get("Zb_OD_ohm")
    if zb is not None:
        ok = True
        if isinstance(zb, dict):
            vals = [zb.get("R", zb.get("R_ohm")), zb.get("X", zb.get("X_ohm"))]
        elif isinstance(zb, (list, tuple)):
            vals = list(zb)
        else:
            vals = [zb]
        if len(vals) not in (1, 2) or not all(_numar(v) for v in vals):
            ok = False
        elif len(vals) == 1:
            ok = vals[0] > 0
        else:
            ok = vals[0] >= 0 and vals[1] >= 0 and math.hypot(vals[0], vals[1]) > 0
        if not ok:
            emite(j, "V07", BLOCANT, "schema", "param", camp="Zb_OD_ohm", x=repr(zb),
                  conditie="impedanța buclei OD trebuie > 0 (modul |Z| sau pereche (R, X) cu R, X ≥ 0)")
            return False
    for k in ("cablu", "cablu_inv", "cablu_pcs", "cablu_C0", "string", "bess"):
        d = inp.get(k)
        if d is not None:
            if not isinstance(d, dict) or not _valideaza_dict(d, j, "schema" if k != "string" else "string"):
                if not isinstance(d, dict):
                    emite(j, "V07", BLOCANT, "schema", "param", camp=k, x=repr(d), conditie="se așteaptă un obiect")
                return False
    for g in inp.get("invertoare") or []:
        if not isinstance(g, dict) or not _valideaza_dict(g, j, "schema"):
            if not isinstance(g, dict):
                emite(j, "V07", BLOCANT, "schema", "param", camp="invertoare", x=repr(g), conditie="se așteaptă un obiect")
            return False
        if g.get("Pn_kW") is None:
            emite(j, "V07", BLOCANT, "schema", "lipsa")
            return False
        gc = g.get("cablu")
        if gc is not None and (not isinstance(gc, dict) or not _valideaza_dict(gc, j, "schema", sari=("L",))):
            if not isinstance(gc, dict):
                emite(j, "V07", BLOCANT, "schema", "param", camp="invertoare[].cablu", x=repr(gc), conditie="se așteaptă un obiect")
            return False
    if tip in ("tablou", "cascada", "pt") and inp.get("plecari") is not None:
        if not _valideaza_plecari(inp["plecari"], j):
            return False
    # v1.3 (§B.18.1): DDR impus pe Q1 și tipul DDR-ului din amonte
    q1d = inp.get("Q1_DDR")
    if q1d is not None and q1d is not False:
        if not isinstance(q1d, dict):
            emite(j, "V07", BLOCANT, "schema", "param", camp="Q1_DDR", x=repr(q1d), conditie="se așteaptă un obiect")
            return False
        if not _valideaza_ddr(q1d, j, "Q1/C1", "Q1_DDR"):
            return False
    ida = inp.get("IdN_amonte_mA")
    if ida is not None and ida not in norme.RCD_IDN_MA and str(inp.get("schema_pamant") or "").strip().upper() != "TT":
        emite(j, "V12", BLOCANT, "schema", "camp", camp="IdN_amonte_mA", valoare=ida)
        return False
    if inp.get("DDR_amonte_selectiv") is not None and not isinstance(inp["DDR_amonte_selectiv"], bool):
        emite(j, "V12", BLOCANT, "schema", "camp", camp="DDR_amonte_selectiv", valoare=inp["DDR_amonte_selectiv"])
        return False
    # C7: schema de legare la pământ
    spl = inp.get("schema_pamant")
    if spl is not None:
        sn = spl.strip().upper().replace("_", "-").replace(" ", "-") if isinstance(spl, str) else repr(spl)
        cheie = "cef_pt" if tip == "cef" and inp.get("pt_Sn_kVA") is not None else tip
        acc = SPL_ACCEPTATE.get(cheie, SCHEME_PAMANT)
        if sn not in acc:
            if sn == "TN-C" and tip in ("bransament", "prosumator"):
                emite(j, "V27", BLOCANT, "schema", detaliu="(TN-C) în aval de DDR: la branșament PEN-ul se separă pe "
                                                           "bareta BN, în amonte de RCCB/RCBO (SR HD 60364-5-54 art. 543.4)")
            else:
                emite(j, "V28", BLOCANT, "schema", spl=spl, tip=tip, acceptate=", ".join(acc))
            return False
        inp["schema_pamant"] = sn
    return True


SERIE_IDN_TT = (300, 100, 30)


def _tt_ra(inp, j):
    """TT (v1.2 R2/R3): RA declarat sau 4 Ω presupus (cu AVERTISMENT: pentru priza proprie a consumatorului valoarea
    implicită e neconservatoare) și cel mai mare IΔn din {300, 100, 30} mA cu RA·IΔn ≤ 50 V (None → V34 BLOCANT)."""
    ra = inp.get("RA_ohm")
    if ra is None:
        ra = 4.0
        j.presupune("RA = 4 Ω (priza de pământ TT) — introduceți valoarea măsurată")
        emite(j, "V34", AVERTISMENT, "schema", "ra", RA=ra)
    lim = next((x for x in SERIE_IDN_TT if not gt(ra * x / 1000.0, 50.0)), None)
    if lim is None:
        emite(j, "V34", BLOCANT, "schema", RA=ra, IdN="0,03", x=ra * 0.03)
    return ra, lim


def idn_aval(idn):
    """IΔn al DDR-urilor din aval, selectiv față de un DDR S de IΔn dat: ≤ IΔn/3 (SR HD 60364-5-53 art. 535.3);
    dacă nu există o treaptă mai mică (30 mA) rămâne aceeași valoare."""
    return next((x for x in SERIE_IDN_TT if 3 * x <= idn), idn)


def _tt_amonte(inp, j, ra, bmpt):
    """N3-M2 (v1.2 R3): segmentul dintre originea alimentării și primul DDR al schemei (C1 până la Q1 / QG → PCC) e
    protejat de DDR-ul din amonte: `IdN_amonte_mA` declarat sau RCCB 300 mA din BMPT (SPEC §C.1). RA·IΔn > 50 V →
    V34 BLOCANT. Fără BMPT și fără valoare declarată → V34 BLOCANT (lipsă DDR). Întoarce IΔn amonte sau None."""
    idn = inp.get("IdN_amonte_mA")
    if idn is None:
        if not bmpt:
            emite(j, "V34", BLOCANT, "C1 (amonte)", "lipsa")
            return None
        idn = norme.BMPT_RCCB["idn_ma"]
        j.presupune(f"DDR în amonte = RCCB {idn} mA din BMPT (ST 4-JT) — declarați IdN_amonte_mA dacă e altul")
    elif idn not in (10, 30, 100, 300, 500, 1000):
        emite(j, "V12", BLOCANT, "C1 (amonte)", "camp", camp="IdN_amonte_mA", valoare=idn)
        return None
    if gt(ra * idn / 1000.0, 50.0):
        emite(j, "V34", BLOCANT, "C1 (amonte)", "amonte", RA=ra, IdN=idn, x=ra * idn / 1000.0)
        return None
    return idn


def _nota_spl(rez, inp, tip):
    """G.1 nota 3 (v1.2): schema de legare la pământ efectivă în rezultat + textul notei, generat din valoarea reală."""
    spl = inp.get("schema_pamant")
    if spl is None:
        spl = "TN-C-S" if tip in ("bransament",) else ("TN-S" if tip in ("pt", "ge_ats") or inp.get("pt_Sn_kVA")
                                                       or inp.get("origine") == "pt_propriu" else "TN-C-S")
    rez["schema_pamant"] = spl
    rez["nota_schema_pamant"] = nota_schema_pamant(tip, spl, rez.get("bloc"), inp.get("RA_ohm"),
                                                   pt=bool(tip == "pt" or inp.get("pt_Sn_kVA")),
                                                   idn_mA=rez.get("DDR_TT_IdN_mA"),
                                                   ddr_txt=_ddr_nota(rez) if spl == "TT" and tip in ("tablou", "cef")
                                                   else None)


def _ddr_nota(rez):
    """v1.3 R5 (M5-4): textul DDR-urilor din nota 3 (TT), generat din valorile reale: amonte, intrare (Q1 / QG) și
    IΔn-urile distincte ale circuitelor (plecări, circuite finale, invertoare, PCS)."""
    parti = []
    if rez.get("IdN_amonte_mA") is not None:
        parti.append(f"DDR amonte IΔn {fmt_ro(rez['IdN_amonte_mA'], 0)}{NB}mA temporizat")
    for k, et in (("Q1_C1", "Q1"), ("QG", "QG")):
        d = (rez.get(k) or {}).get("DDR")
        if d:
            parti.append(f"{et}: {'bloc diferențial reglabil' if d.get('reglabil') else 'DDR'} {fmt_ro(d['IdN_mA'], 0)}{NB}mA"
                         + (f", Δt {fmt_ro(d['dt_s'], 2)}{NB}s" if d.get("dt_s") else ""))
        elif k in rez and isinstance(rez[k], dict):
            parti.append(f"{et} fără DDR propriu (protejat de DDR-ul din amonte)")
    circ = sorted({c["DDR"]["IdN_mA"] for k in ("plecari", "invertoare") for c in (rez.get(k) or [])
                   if isinstance(c, dict) and c.get("DDR")} | ({rez["PCS"]["DDR"]["IdN_mA"]}
                                                                if (rez.get("PCS") or {}).get("DDR") else set()),
                  reverse=True)
    if circ:
        parti.append("DDR instantanee pe circuite IΔn " + " / ".join(f"{fmt_ro(x, 0)}{NB}mA" for x in circ))
    return "; ".join(parti) or None


def _pi(pl, nivel):
    """SPEC §C.2 pct. 1: Pi = P_kW, sau (plecare dată în A) Pi = √3·400·In·cosφ/1000; pentru o plecare cu sub-plecări
    Pi = ks(n_copii)·Σ Pi_copii (recursiv)."""
    rec = pl.get("receptor") or receptor_dupa_nume(pl.get("nume", ""), nivel)
    if pl.get("P_kW") is not None:
        return float(pl["P_kW"])
    if pl.get("In_A") is not None:
        cos = pl.get("cosfi") or norme.COSFI_IMPLICIT.get(rec, 0.9)
        u = SQRT3 * norme.U_N_V if pl.get("retea", "tri") == "tri" else norme.U_0_V
        return u * float(pl["In_A"]) * cos / 1000.0
    copii = pl.get("copii") or []
    if copii:
        ks = pl.get("ks") or norme.ks_implicit(len(copii))
        return ks * sum(_pi(c, nivel + 1) for c in copii)
    return 0.0


def _cablu_plecare(pl, nivel, j, obiect, implicit_metoda=None, final=False):
    """SPEC §B.0 / §C.2 pct. 9 / §B.1.1: plecări Al PVC D1, L 50 m; sub-plecări și circuite finale (tablou cu
    `circuite_finale`) Cu PVC metoda C, L 25 m (declarate)."""
    cab = dict(pl.get("cablu") or {})
    if nivel == 0 and not final:
        cb.metoda_implicita(cab, implicit_metoda or "D1")
        if "material" not in cab:
            cab["material_implicit"] = True
            if cab["metoda"] in norme.METODE_IN_PAMANT:
                cab["material"] = "Al"
                j.presupune("plecări Al PVC în tub în pământ (D1), cu trecere pe Cu sub 16 mm²")
            else:
                cab["material"] = "Cu"
        L = pl.get("L_m", cab.get("L"))
        if L is None:
            L = 50.0
            j.presupune("lungime plecări 50 m", obiect)
    else:
        cb.metoda_implicita(cab, "C")
        cab.setdefault("material", "Cu")
        L = pl.get("L_m", cab.get("L"))
        if L is None:
            L = 25.0
            j.presupune("lungime circuite finale 25 m (Cu PVC, metoda C)", obiect)
    cab["L"] = float(L)
    return cab


def _ramura_plecare(pl, nivel, j, obiect, implicit_metoda=None, final=False):
    """SPEC §B.1 / §C.2 pct. 9 / §B.1.1: construiește intrarea B.1 a unei plecări (nivel 0, rol „plecare”), a unei
    sub-plecări (nivel ≥ 1) sau a unui circuit final al unui tablou cu `circuite_finale` (rol „final”)."""
    copii = pl.get("copii") or []
    final = final and not copii
    rec = pl.get("receptor") or receptor_dupa_nume(pl.get("nume", ""), 1 if final else nivel)
    r = {"rol": "plecare" if (nivel == 0 and not final) else "final", "receptor": rec, "retea": pl.get("retea", "tri"),
         "cablu": _cablu_plecare(pl, nivel, j, obiect, implicit_metoda, final), "are_aval": bool(copii)}
    for k in ("P_kW", "In_A", "S_kVA", "cosfi", "ks", "prot_tip", "curba", "In_fortat", "Icu_fortat", "h3", "h3_pct",
              "pornire"):
        if pl.get(k) is not None:
            r[k] = pl[k]
    # C4 (v1.2): DDR refuzat explicit pe un circuit de prize → V29 BLOCANT în ramură
    if pl.get("DDR") is False or pl.get("ddr") is False:
        r["ddr"] = False
    elif isinstance(pl.get("DDR"), dict):
        r["ddr"] = dict(pl["DDR"])      # v1.3: DDR impus {IdN_mA, selectiv, tip} (§B.18.1)
    if copii and r.get("P_kW") is None and r.get("In_A") is None:
        ksd = pl.get("ks") or norme.ks_implicit(len(copii))
        spi = sum(_pi(c, nivel + 1) for c in copii)
        r["P_kW"] = ksd * spi
        r.pop("ks", None)
        j.pas(f"{obiect}: bilanț TD Σ Pi = {fmt_ro(spi)} kW, ks = {fmt_ro(ksd)}")
    return r


def _ip_preliminar(pl, nivel, j_tmp, final=False):
    """SPEC §C.2 pct. 4–5: Ip-ul plecării calculat înaintea barei (doar protecția), recursiv pentru cascade."""
    r = _ramura_plecare(pl, nivel, j_tmp, "tmp", final=final)
    copii = pl.get("copii") or []
    ips = [x for x in (_ip_preliminar(c, nivel + 1, j_tmp) for c in copii) if x is not None]
    if ips:
        r["Ip_min_extra"] = max(ips) + 0.01
    r["_doar_protectie"] = True
    ctx = {"Ik3_kA": 1.0, "origine": "retea_publica", "dU_pct": 0.0}
    rr = calculeaza_ramura(r, ctx, j_tmp, "tmp")
    return None if rr["blocat"] else rr["Ip"]


def _plecari(plecari, ctx_bara, amonte, j, prefix="", final=False):
    """SPEC §C.2 pct. 8–9 / §C.5 pct. 8: dimensionarea plecărilor cu contextul barei, selectivitatea față de aparatul de
    intrare și cascadele (recursiv, fără limită de adâncime). Returnează lista plată (parcurgere în adâncime)."""
    lista = []

    def proceseaza(pl, nivel, ctx, prot_amonte, obiect):
        """O plecare (și recursiv sub-plecările ei) cu contextul barei și aparatul amonte (SPEC §C.2 pct. 8–9)."""
        r = _ramura_plecare(pl, nivel, j, obiect, final=final and nivel == 0)
        copii = pl.get("copii") or []
        if copii:
            jt = Jurnal()
            ips = [x for x in (_ip_preliminar(c, nivel + 1, jt) for c in copii) if x is not None]
            if ips:
                r["Ip_min_extra"] = max(ips) + 0.01
        rr = calculeaza_ramura(r, ctx, j, obiect, amonte=prot_amonte)
        intrare = {"nume": pl.get("nume", ""), "nivel": nivel}
        intrare.update(rr["rezultat"])
        lista.append(intrare)
        if copii and not rr["blocat"]:
            for k, cpl in enumerate(copii, 1):
                proceseaza(cpl, nivel + 1, rr["ctx_aval"], rr["prot"], f"{obiect}.{k}·{cpl.get('nume', '')}")

    for i, pl in enumerate(plecari, 1):
        proceseaza(pl, 0, ctx_bara, amonte, f"{prefix}P{i}·{pl.get('nume', '')}")
    return lista


def _ks_bilant(inp, n):
    """ks declarat sau ks_implicit(n_plecări) după IEC 61439-2 tab. 101 (SPEC §B.0, §C.2 pct. 2)."""
    ks = inp.get("ks")
    return (float(ks), False) if ks is not None else (norme.ks_implicit(n), True)


# ============================================================================================================
# C.1 Branșament DEER
# ============================================================================================================
def schema_bransament(inp, j):
    """SPEC §C.1 (fără cheile interne ale contextului)."""
    rez = _bransament(inp, j)
    rez.pop("_ctx_C2", None)
    rez.pop("_prot_Q", None)
    return rez


def _bransament(inp, j):
    """SPEC §C.1: alegerea blocului BMPT/BMPM, Q, SF, RCCB, TC, contor și coloana C2 (ramură B.21)."""
    rez = {}
    retea = inp.get("retea", "tri")
    L = inp.get("L_coloana_m")
    surse = [k for k in ("P_kW", "S_kVA", "Ib_A") if inp.get(k) is not None]
    if len(surse) > 1:
        emite(j, "V12", BLOCANT, "schema", "surse", surse=", ".join(surse), poli="", retea=retea)
        return rez
    if not valideaza(inp, {"L": L}, j, "schema"):
        return rez
    if inp.get("ks") is not None:
        # R2 (minore): Pa din ATR este deja puterea simultană — ks nu se aplică la branșament (declarat, nu ignorat tacit)
        j.presupune(f"ks = {fmt_ro(inp['ks'])} ignorat la branșament (Pa din ATR este deja puterea simultană)")
    if L is None:
        L = 50.0
        j.presupune("lungime coloană C2 50 m")
    cos_dat = inp.get("cosfi")
    cos = cos_dat if cos_dat is not None else norme.COSFI_IMPLICIT["tablou"]
    if cos_dat is None:
        j.presupune("cosφ 0,9 (forță, iluminat, prize, tablou)")
    U = u_calcul(retea)
    if inp.get("S_kVA") is not None:
        ib = float(inp["S_kVA"]) * 1000.0 / U
        j.pas(f"Ib = {fmt_ro(inp['S_kVA'])}·1000/{'(√3·400)' if retea == 'tri' else '230'} = {fmt_ro(ib)} A")
    elif inp.get("Ib_A") is not None:
        ib = float(inp["Ib_A"])
        j.pas(f"Ib dat = {fmt_ro(ib)} A (fără P; cosφ {fmt_ro(cos)} doar pentru ΔU)")
    elif inp.get("In_A") is not None:
        ib = float(inp["In_A"])
    else:
        ib = float(inp["P_kW"]) * 1000.0 / (U * cos)
        j.pas(f"Ib = {fmt_ro(inp['P_kW'])}·1000/({'√3·400' if retea == 'tri' else '230'}·{fmt_ro(cos)}) = {fmt_ro(ib)} A")
    rez["Ib_A"] = ib
    if inp.get("P_kW") is not None:
        rez["Pa_kW"] = float(inp["P_kW"])
    schema_p = inp.get("schema_pamant", "TN-C-S")
    ctx = _context_od(inp, j, ddr_amonte=False)

    if retea == "mono":
        if gt(ib, norme.BMPM["I_max_A"]):
            emite(j, "V53", BLOCANT, "schema", Ib=ib)
            return rez
        In_q = prima_din_serie(norme.BMPM["Q_in_A"], ib)
        q_f = inp.get("Q_In_A")
        if q_f is not None:
            # v1.4 (§C.8): RCBO existent impus (branșament existent al locuinței)
            if q_f not in norme.BMPM["Q_in_A"]:
                jos, sus = _vecini_serie(norme.BMPM["Q_in_A"], q_f)
                emite(j, "V05", BLOCANT, "Q", In=q_f, tip="RCBO BMPM (ST 3-JT)", vecini=f"{jos} A / {sus} A")
                return rez
            if gt(ib, q_f):
                emite(j, "V04", BLOCANT, "Q", Ib=ib, Ip=q_f)
                return rez
            In_q = q_f
        rez.update({"bloc": f"BMPM-{In_q}",
                    "Q": {"tip": "RCBO 1P+N", "curba": "C", "In_A": In_q, "IdN_mA": norme.BMPM["idn_ma"],
                          "Icn_kA": int(norme.BMPM["Q_icn_min_ka"])},
                    "SF": {"tip": "separator monopolar cu fuzibil", "In_A": 40},
                    "contor": f"230{NB}V, 5(60){NB}A"})
        j.pas(f"BMPM: RCBO 1P+N C{In_q} (seria 16/20/25/32/40 A), SF 40 A gG")
        ctx["ddr_ramura"] = "RCBO"
        sf = {"tip": "gG", "In_A": 40}
        q_tip, q_in = "MCB", In_q
        icu_q = norme.BMPT_Q_ICN_MIN_KA
    else:
        fortat = inp.get("bmpt_fortat")
        if fortat is not None and fortat not in norme.BMPT:
            emite(j, "V50", BLOCANT, "schema", "tip", tip=fortat)
            return rez
        if gt(ib, norme.BMPT_I_MAX_A):
            emite(j, "V50", BLOCANT, "schema", "ib", Ib=ib)
            return rez
        semidirect = inp.get("masura_ceruta") == "semidirecta" or fortat == "BMPTi-250"
        if fortat is not None and fortat != "BMPTi-250" and gt(ib, norme.BMPT[fortat]["I_max_A"]):
            # v1.2: bloc impus insuficient → BLOCANT (nu se mai înlocuiește tacit)
            emite(j, "V50", BLOCANT, "schema", "mic", tip=fortat, Imax=norme.BMPT[fortat]["I_max_A"], Ib=ib)
            return rez
        bloc = next(b for b in norme.BMPT_ORDINE if le_ib(ib, norme.BMPT[b]["I_max_A"]))
        if fortat is not None and fortat != "BMPTi-250":
            bloc = fortat
        q_f = inp.get("Q_In_A")
        if q_f is not None:
            # v1.2: Q impus — trebuie să existe în seria unui bloc ST 4-JT și să fie ≥ Ib
            if gt(ib, q_f):
                emite(j, "V04", BLOCANT, "Q", Ib=ib, Ip=q_f)
                return rez
            if q_f not in norme.BMPT[bloc]["Q_in_A"]:
                alt = next((x for x in norme.BMPT_ORDINE if q_f in norme.BMPT[x]["Q_in_A"]
                            and norme.BMPT_ORDINE.index(x) >= norme.BMPT_ORDINE.index(bloc)), None)
                if alt is None or fortat is not None:
                    serie = sorted({v for x in norme.BMPT_ORDINE for v in norme.BMPT[x]["Q_in_A"]})
                    jos, sus = _vecini_serie(serie, q_f)
                    emite(j, "V05", BLOCANT, "Q", In=q_f, tip=f"Q {bloc} (ST 4-JT)", vecini=f"{jos} A / {sus} A")
                    return rez
                bloc = alt
        if semidirect and bloc != "BMPTi-250":
            emite(j, "V51", AVERTISMENT, "schema", Ib=ib, bloc=bloc)
        b = norme.BMPT[bloc]
        In_q = q_f if q_f is not None else prima_din_serie(b["Q_in_A"], ib)
        rez["bloc"] = bloc
        lim_inf = b["I_min_A"]
        j.pas(f"{bloc} (Ib în ({fmt_ro(lim_inf)}; {fmt_ro(b['I_max_A'])}] A)")
        if b["Q_tip"] == "MCB":
            rez["Q"] = {"tip": "MCB", "curba": "C", "In_A": In_q, "Icn_kA": int(norme.BMPT_Q_ICN_MIN_KA)}
            icu_q = norme.BMPT_Q_ICN_MIN_KA
        else:
            k, ir = pr.alege_reglaj_ir("MCCB", In_q, ib)
            # M12 (v1.2): MCCB-ul din BMPTi are Icu din seria MCCB (min. 25 kA ≥ 6 kA cerut de ST 4-JT) — același
            # Icu în calcul, în memoriu și pe desen
            icu_q = prima_din_serie(norme.MCCB_ICU_KA, norme.BMPT_Q_ICN_MIN_KA)
            rez["Q"] = {"tip": "MCCB", "In_A": In_q, "Ir_multiplu": k, "Ir_A": ir,
                        "Icu_kA_min": int(norme.BMPT_Q_ICN_MIN_KA), "Icu_kA": icu_q, "decl": "TM",
                        "Im_A": norme.IM_TM_MULTIPLU * In_q}
        rez["SF"] = {"In_A": b["SF_fuzibil_A"], "soclu_A": b["SF_soclu_A"], "gabarit": b["SF_gabarit"]}
        if In_q > b["SF_fuzibil_A"]:
            emite(j, "V52", BLOCANT, "schema", q=In_q, sf=b["SF_fuzibil_A"])
        rez["RCCB"] = {"poli": norme.BMPT_RCCB["poli"], "In_A": prima_din_serie(RCCB_IN_BRANSAMENT, In_q),
                       "IdN_mA": norme.BMPT_RCCB["idn_ma"], "tip": norme.BMPT_RCCB["tip"],
                       # M11 (v1.2): DDR general 300 mA în amontele DDR-urilor de 30 mA din instalație → selectiv (S)
                       "selectiv": True, "aparat": "RCCB"}
        if gt(In_q, norme.RCCB_IN_A[-1]):
            # M11 (v1.2, §B.4): peste 125 A nu există RCCB modular → bloc diferențial asociat MCCB-ului Q, In = In Q
            rez["RCCB"].update({"aparat": "bloc_diferential", "asociat": "Q", "In_A": In_q})
            j.pas(f"DDR general: In Q {In_q} A > 125 A → bloc diferențial asociat MCCB Q, IΔn 300 mA, tip AC, S")
        if b["masura"] == "semidirecta":
            tc = norme.BMPT_TC
            p = prima_din_serie(tc["primar_A"], max(ib, In_q / tc["factor_extindere"]))
            if p is None:
                emite(j, "V55", BLOCANT, "TC", "B", Ib=ib, p=max(tc["primar_A"]))
            else:
                s_sec = (tc["secundar_A"] ** 2 * (2 * 3.0 * norme.TC_RHO_SECUNDAR / 1.5)
                         + norme.TC_CONSUM_CONTOR_VA + norme.TC_CONSUM_CONTACTE_VA)
                rez["TC"] = f"3 {X} {p}/5{NB}A, cl. 0,5, 5{NB}VA"
                rez["TC_primar_A"] = p
                rez["TC_sarcina_VA"] = s_sec
                j.pas(f"TC: Ip ≥ max(Ib {fmt_ro(ib)}; In_Q/1,2 = {fmt_ro(In_q / 1.2)}) → {p}/5 A; "
                      f"sarcină secundar = {fmt_ro(s_sec)} VA ≤ 5 VA")
                if gt(s_sec, tc["Sn_VA"]):
                    emite(j, "V55", AVERTISMENT, "TC", "AV", S=s_sec, Sn=tc["Sn_VA"])
            rez["contor"] = f"semidirect 3 {X} 230/400{NB}V, 5{NB}A (furnizat de OD)"
        else:
            rez["contor"] = f"direct 3 {X} 230/400{NB}V, 5(100){NB}A (furnizat de OD)"
            if gt(ib, 100):
                emite(j, "V56", BLOCANT, "schema", Ib=ib)
        ctx["ddr_ramura"] = "RCCB"
        sf = {"tip": "gG", "In_A": b["SF_fuzibil_A"]}
        q_tip, q_in = b["Q_tip"], In_q

    # coloana C2: ramură B.21 cu Q ca protecție
    # M1 (v1.2): dicționarul `cablu` al coloanei C2 (formularul UI) se respectă ca la plecările de tablou; câmpurile
    # de la nivelul schemei rămân acceptate (compatibilitate)
    cab = {}
    for k in CAMPURI_CABLU_SCHEMA:
        if inp.get(k) is not None:
            cab[k] = inp[k]
    cab.update({k: v for k, v in (inp.get("cablu") or {}).items() if v is not None})
    cab["L"] = float(L)
    cb.metoda_implicita(cab, "D1")
    if cab.get("material") is None:
        cab["material_implicit"] = True
        if cab.get("S_fortat") is not None and float(cab["S_fortat"]) < norme.S_MIN_AL:
            cab["material"] = "Cu"
            j.presupune("coloană C2 Cu (secțiune impusă < 16 mm²)")
        elif cab["metoda"] in norme.METODE_IN_PAMANT:
            cab["material"] = "Al"
            j.presupune("coloană C2 Al PVC în tub în pământ (D1), cu trecere pe Cu sub 16 mm²")
        else:
            cab["material"] = "Cu"
    r = {"rol": "c2", "receptor": "tablou", "retea": retea, "cablu": cab, "prot_tip": q_tip, "curba": "C",
         "In_fortat": q_in, "Icu_fortat": icu_q, "bmpt": True, "_validat": True}
    if inp.get("P_kW") is not None:
        r["P_kW"] = inp["P_kW"]
    elif inp.get("S_kVA") is not None:
        r["S_kVA"] = inp["S_kVA"]
    else:
        r["Ib_A"] = ib
    if cos_dat is not None:
        r["cosfi"] = cos_dat
    if inp.get("_cosfi_eticheta"):
        # v1.7 (§C.8, N13): coloana locuinței — cosφ mediu 0,95 (DECIZIE, presupus), cu eticheta în ipoteze
        r["_cosfi_eticheta"], r["_cosfi_implicit"] = inp["_cosfi_eticheta"], True
    if inp.get("_tinta_dU_C2") is not None:
        # v1.6 (§C.8, N2): coloana locuinței mărită până la bugetul de ΔU (ținta mărește S, limita V21 rămâne)
        r["tinta_dU"] = float(inp["_tinta_dU_C2"])
    if inp.get("_tt_ddr_defect") and schema_p == "TT":
        # v1.5 (§C.8, locuință TT): coloana e protejată la defect de DDR-ul 300 mA al blocului (RA·IΔn ≤ 50 V), nu de Q
        ctx["tt_ddr_defect"] = {"IdN_mA": norme.BMPT_RCCB["idn_ma"] if retea != "mono" else norme.BMPM["idn_ma"],
                                "RA_ohm": inp.get("RA_ohm") if inp.get("RA_ohm") is not None else 4.0}
    rr = calculeaza_ramura(r, ctx, j, "C2", amonte=sf, obiect_sel="Q vs SF", bmpt_sel=True)
    rez["C2"] = rr["rezultat"]
    rez["_ctx_C2"] = None if rr["blocat"] else rr["ctx_aval"]     # v1.4: bara TE (locuință, §C.8)
    rez["_prot_Q"] = rr["prot"]
    if not rr["blocat"] and rez.get("bloc") == "BMPTi-250" and gt(rr["rezultat"]["S_faza_mm2"], 150):
        emite(j, "V54", AVERTISMENT, "schema", S=rr["rezultat"]["S_faza_mm2"])
    if retea != "mono":
        rez["C1"] = C1_TEXT
    _nota_spl(rez, inp, "bransament")
    if schema_p == "TT":
        ra = inp.get("RA_ohm")
        if ra is None:
            ra = 4.0
            j.presupune("RA = 4 Ω (valoarea cerută de OD pentru priza de pământ)")
        x = ra * norme.BMPT_RCCB["idn_ma"] / 1000.0
        if gt(x, 50.0):
            emite(j, "V34", BLOCANT, "schema", RA=ra, IdN="0,3", x=x)
    return rez


def _vecini_serie(serie, v):
    """Vecinii unei valori într-o serie (remedierea V05)."""
    jos = [x for x in serie if x < v]
    sus = [x for x in serie if x > v]
    return (jos[-1] if jos else "—"), (sus[0] if sus else "—")


def le_ib(ib, imax):
    """Ib ≤ limita superioară a blocului, cu toleranță (SPEC §C.1, §B.22)."""
    return not gt(ib, imax)


# ============================================================================================================
# C.2 Tablou general cu bilanț de puteri (inclusiv cascadă)
# ============================================================================================================
def schema_tablou(inp, j):
    """SPEC §C.2: bilanțul de puteri, Q1 + alimentarea C1, bara TG și plecările (cu cascade)."""
    rez = {}
    plecari = inp.get("plecari") or []
    if not plecari:
        # v1.2: tablou fără plecări → nimic de dimensionat (nu se exportă o schemă goală)
        emite(j, "V07", BLOCANT, "schema", "plecari", tablou="tabloul")
        return rez
    pis = [_pi(pl, 0) for pl in plecari]
    spi = sum(pis)
    ks, ks_impl = _ks_bilant(inp, len(plecari))
    if ks_impl:
        j.presupune(f"ks = {fmt_ro(ks)} (IEC 61439-2 tab. 101, {len(plecari)} plecări)")
    j.ipoteza("ks", ks, ks_impl)
    pc = ks * spi
    p_decl = inp.get("P_kW")
    # C7 (v1.2): TN-C (PEN) numai între PT propriu și tablou, niciodată în aval de un DDR (SPEC §A.2, V27)
    if inp.get("schema_pamant") == "TN-C":
        if inp.get("origine") != "pt_propriu" or inp.get("ddr_amonte"):
            emite(j, "V27", BLOCANT, "schema",
                  detaliu="(TN-C) în aval de DDR: alimentarea din rețeaua publică trece prin RCCB 300 mA din BMPT, iar "
                          "PEN-ul se separă pe BN (TN-C-S) — TN-C se admite doar între PT propriu și tablou "
                          "(I7-2011 art. 3.3.2.11.1, SR HD 60364-5-54 art. 543.4)")
            return rez
    rez["bilant"] = {"Pi_kW": spi, "ks": ks, "Pc_kW": pc, "P_declarat_kW": p_decl}
    j.pas(f"Bilanț: Σ Pi = {' + '.join(fmt_ro(p) for p in pis) or '0'} = {fmt_ro(spi)} kW; ks({len(plecari)}) = "
          f"{fmt_ro(ks)} → Pc = {fmt_ro(pc)} kW")
    if p_decl is not None and lt(p_decl, pc):
        emite(j, "V14", AVERTISMENT, "schema", P=p_decl, Pc=pc)

    final = bool(inp.get("circuite_finale"))
    if inp.get("origine") == "pt_propriu":
        # SPEC §B.1.1: TG din PT propriu — limite ΔU 6/8 %, fără DDR în amonte; sursa = trafo dacă Sn e dat
        sn = inp.get("pt_Sn_kVA")
        if sn is not None:
            if int(sn) not in norme.TRAFO or float(sn) != int(sn):
                emite(j, "V05", BLOCANT, "schema", "trafo", Sn=sn, vecini=", ".join(str(x) for x in norme.TRAFO_SN_KVA))
                return rez
            t = sc.trafo(int(sn), inp.get("SkQ_MVA"))
            if inp.get("SkQ_MVA") is None:
                j.presupune("S\"kQ = 500 MVA, R/X = 0,1 (rețea MT, majorant)")
            j.ipoteza("skq", t["SkQ_MVA"], inp.get("SkQ_MVA") is None)
            j.ipoteza("trafo", (t["uk_pct"], t["Pk_W"]), True)
            ctx = sc.context_pt(t)
            j.presupune(f"sursa: bara JT a PT propriu {sn} kVA")
        else:
            ctx = _context_od(inp, j, ddr_amonte=False)
            ctx["origine"] = "pt_propriu"
            j.presupune("sursa: PT propriu cu Sn necunoscut — Ik3max 25 kA și Zbuclă 0,201 Ω implicite")
    else:
        ctx = _context_od(inp, j, ddr_amonte=inp.get("ddr_amonte", True))
        if inp.get("ddr_amonte", True):
            j.presupune("sursa: rețea publică prin BMPT cu RCCB 300 mA în amonte")
            # v1.3 (§B.18.1): DDR-ul branșamentului e amontele tuturor DDR-urilor din tablou
            ctx["ddr_sus"] = _ddr_amonte(inp, inp.get("retea", "tri"))
    if inp.get("origine") == "pt_propriu" and inp.get("IdN_amonte_mA") is not None:
        ctx["ddr_sus"] = _ddr_amonte(inp)

    # pct. 4: întâi protecțiile plecărilor (doar Ip)
    jt = Jurnal()
    ips = [x for x in (_ip_preliminar(pl, 0, jt, final) for pl in plecari) if x is not None]

    cab = dict(inp.get("cablu") or {})
    cb.metoda_implicita(cab, "D1")
    if "material" not in cab:
        cab["material_implicit"] = True
        cab["material"] = "Al" if cab["metoda"] in norme.METODE_IN_PAMANT else "Cu"
        j.presupune("alimentare Al PVC în tub în pământ (D1), cu trecere pe Cu sub 16 mm²")
    L = inp.get("L_alimentare_m", cab.get("L"))
    if L is None:
        L = 50.0
        j.presupune("lungime alimentare tablou 50 m")
    cab["L"] = float(L)
    r = {"rol": "intrare", "receptor": "tablou", "retea": inp.get("retea", "tri"), "cablu": cab, "are_aval": True}
    for k in ("cosfi", "h3", "h3_pct", "Icu_fortat"):
        if inp.get(k) is not None:
            r[k] = inp[k]
    if inp.get("Q1_tip"):
        r["prot_tip"] = inp["Q1_tip"]
    if inp.get("In_Q1_A") is not None:
        r["In_fortat"] = inp["In_Q1_A"]
    if p_decl is not None:
        r["P_kW"] = p_decl
    elif inp.get("In_Q1_A") is not None:
        r["In_A"] = inp["In_Q1_A"]
    else:
        r["P_kW"] = pc
    if ips:
        r["Ip_min_extra"] = max(ips) + 0.01
    if inp.get("schema_pamant") == "TN-C":
        # v1.2 R2 (N-M2): alimentarea TN-C — al patrulea conductor al cablului este PEN (fără PE separat)
        r["cablu"]["PE_loc"] = "PEN"
    if isinstance(inp.get("Q1_DDR"), dict):
        r["ddr"] = dict(inp["Q1_DDR"])          # v1.3: DDR general impus pe Q1 (§B.18.1)
    if inp.get("schema_pamant") == "TT":
        # v1.2 R2 (N-C2, SR HD 60364-4-41 art. 411.5): DDR pe fiecare circuit, IΔn cu RA·IΔn ≤ 50 V
        ra, lim = _tt_ra(inp, j)
        if lim is None:
            return rez
        idn_am = _tt_amonte(inp, j, ra, bmpt=inp.get("origine") != "pt_propriu")
        if idn_am is None:
            return rez
        # v1.3 R5 (§C.2 pct. 13, M5-4): DDR-urile alese selectiv în timp și în IΔn — amonte temporizat → Q1 fără DDR
        # propriu, circuite instantanee ≤ IΔn amonte/3; altfel bloc diferențial reglabil pe Q1 (Δt 0,15 s)
        am = ddr_mod.descriere(idn_am, inp.get("DDR_amonte_selectiv", True),
                               "DDR amonte (declarat)" if inp.get("IdN_amonte_mA") is not None else "RCCB BMPT")
        al = ddr_mod.alege_tt(lim, am)
        idn = al["idn_circuite"]
        ctx["idn_tt_mA"] = idn
        ctx["RA_tt"] = ra
        ctx["ddr_sus"] = am
        if al["intrare"] and not isinstance(r.get("ddr"), dict):
            r["ddr"] = {"IdN_mA": al["intrare"]["IdN_mA"], "dt_s": al["intrare"]["dt_s"], "_motor": True}
        rez["DDR_TT_IdN_mA"] = max(idn, idn_am, al["intrare"]["IdN_mA"] if al["intrare"] else 0)
        rez["IdN_amonte_mA"] = idn_am
        j.pas(f"TT: RA = {fmt_ro(ra)} Ω → IΔn ≤ 50/RA = {fmt_ro(50000.0 / ra, 0)} mA; amonte {am['denumire']} {idn_am} mA "
              f"{am['temporizare']} → " + (f"Q1 bloc diferențial reglabil {al['intrare']['IdN_mA']} mA, Δt "
                                         f"{fmt_ro(al['intrare']['dt_s'], 2)} s" if al["intrare"] else
                                         "Q1 fără DDR propriu (protejat de amonte)") +
              f"; circuite DDR {idn} mA instantaneu (prize 30 mA)")
    rr = calculeaza_ramura(r, ctx, j, "Q1/C1")
    rez["Q1_C1"] = rr["rezultat"]
    _nota_spl(rez, inp, "tablou")
    if rr["blocat"]:
        return rez
    if inp.get("schema_pamant") == "TN-C":
        c1 = rr["rezultat"]
        if lt(c1["S_faza_mm2"], norme.S_MIN_PEN[c1["material"]]):
            emite(j, "V27", BLOCANT, "Q1/C1", detaliu=f"{fmt_ro(c1['S_faza_mm2'])} mm² {c1['material']} < "
                                                      f"{fmt_ro(norme.S_MIN_PEN[c1['material']])} mm² (SR HD 60364-5-54 art. 543.4)")
        rez["Q1_C1"]["PEN"] = True    # = PE == "PEN" (v1.2 R2)
    ctx_tg = rr["ctx_aval"]
    rez["bara_TG"] = {"Ik3max_kA": ctx_tg["Ik3_kA"], "dU_pct": ctx_tg["dU_pct"]}
    rez["plecari"] = _plecari(plecari, ctx_tg, rr["prot"], j, final=final)
    if inp.get("schema_pamant") == "TT":
        _nota_spl(rez, inp, "tablou")            # v1.3 R5: nota 3 cu DDR-urile reale ale plecărilor
    return rez


# ============================================================================================================
# C.5 Post de transformare 20/0,4 kV
# ============================================================================================================
def _celula_trafo(sn, fortat, j):
    """SPEC §C.5 pct. 6: Sn ≤ 1000 kVA → separator de sarcină + siguranțe MT; > 1000 kVA → întreruptor + releu.
    Siguranțe impuse peste 1000 kVA → V61 BLOCANT."""
    tip = fortat or ("sigurante" if sn <= norme.TRAFO_SN_MAX_SIGURANTE_MT_KVA else "intreruptor")
    if tip.startswith("sig"):
        if sn > norme.TRAFO_SN_MAX_SIGURANTE_MT_KVA:
            emite(j, "V61", BLOCANT, "schema", Sn=sn)
            return "separator de sarcină + siguranțe MT (calibru nedefinit peste 1000 kVA)"
        return f"separator de sarcină + siguranțe MT {fmt_ro(norme.TRAFO_SIGURANTA_MT_A[sn])}{NB}A"
    return "intreruptor"


def _q_trafo(in_t, ik3_kA, in_fortat=None):
    """SPEC §C.5 pct. 3: Q JT cu Ip,min = In_T → MCCB (≤ 1600 A) sau ACB, Ir = treapta ≥ In_T; Icu ≥ Ik3 bara."""
    ref = in_fortat if in_fortat is not None else in_t
    tip = "MCCB" if ref <= 1600 + 1e-9 else "ACB"
    In = in_fortat if in_fortat is not None else pr.alege_calibru(tip, in_t)
    if In is None:
        return None
    prot = pr.construieste(tip, In, in_t, are_aval=True)
    prot["Icu_kA"], ok = pr.alege_icu(tip, ik3_kA)
    prot["icu_ok"] = ok
    return prot


def schema_pt(inp, j):
    """SPEC §C.5: trafo, celula trafo, Q JT, Ik3/Ik1 la bara TGJT, bilanț și plecări (origine „pt_propriu”)."""
    rez = {}
    sn = inp.get("Sn_kVA")
    if sn is None or int(sn) not in norme.TRAFO:
        emite(j, "V05", BLOCANT, "schema", "trafo", Sn=sn, vecini=", ".join(str(s) for s in norme.TRAFO_SN_KVA))
        return rez
    sn = int(sn)
    t = sc.trafo(sn, inp.get("SkQ_MVA"))
    if inp.get("SkQ_MVA") is None:
        j.presupune("S\"kQ = 500 MVA, R/X = 0,1 (rețea MT, majorant)")
    j.ipoteza("skq", t["SkQ_MVA"], inp.get("SkQ_MVA") is None)
    j.ipoteza("trafo", (t["uk_pct"], t["Pk_W"]), True)
    rez["trafo"] = {"Sn_kVA": sn, "In_T_A": t["In_T_A"], "uk_pct": t["uk_pct"], "Pk_W": t["Pk_W"],
                    "Ik3max_bara_kA": t["Ik3max_bara_kA"], "Ik1min_bara_A": t["Ik1min_bara_A"]}
    j.pas(f"Trafo {sn} kVA: In_T = {fmt_ro(t['In_T_A'])} A; uk {fmt_ro(t['uk_pct'])} %, Pk {t['Pk_W']} W; "
          f"Z_T = {fmt_ro(t['Z_T'][0] * 1000, 3)} + j{fmt_ro(t['Z_T'][1] * 1000, 3)} mΩ; K_T = {fmt_ro(t['K_T'], 4)}")
    j.pas(f"Ik3max bara TGJT = {fmt_ro(t['Ik3max_bara_kA'])} kA; Ik1min bara = {fmt_ro(t['Ik1min_bara_A'], 0)} A")
    rez["celula_trafo"] = _celula_trafo(sn, inp.get("celula_trafo"), j)

    q = _q_trafo(t["In_T_A"], t["Ik3max_bara_kA"], inp.get("In_Q_JT_A"))
    if q is None:
        emite(j, "V06", BLOCANT, "Q", Ib=t["In_T_A"], tip="ACB")
        return rez
    if q.get("decl") == "EL":
        pr.alege_isd(q, t["Ik1min_bara_A"])
    rez["Q_JT"] = {"tip": q["tip"], "In_A": q["In_A"], "Ir_A": q["Ir_A"], "Ir_multiplu": q["Ir_multiplu"],
                   "Icu_kA": q["Icu_kA"]}
    # v1.2: reglajele declanșatorului electronic (Isd/tsd/Ii) în rezultat, pentru listă și desen (§E.3)
    for k in ("decl", "Im_A", "Isd_A", "Isd_multiplu", "tsd_s", "Ii_A"):
        if q.get(k) is not None:
            rez["Q_JT"][k] = q[k]
    j.pas(f"Q JT: Ip,min = In_T = {fmt_ro(t['In_T_A'])} A → {q['tip']} {q['In_A']} A, Ir = "
          f"{fmt_ro(q['Ir_multiplu'])}·In = {fmt_ro(q['Ir_A'])} A, Icu {fmt_ro(q['Icu_kA'])} kA")
    if inp.get("In_Q_JT_A") is not None and q["In_A"] not in pr.SERII[q["tip"]]:
        emite(j, "V05", BLOCANT, "Q", In=q["In_A"], tip=q["tip"], vecini="")
    if lt(q["In_A"], t["In_T_A"]) or lt(q["Ir_A"], t["In_T_A"]):
        emite(j, "V60", BLOCANT, "schema", "B", x=q["In_A"], y=t["In_T_A"])
    if not q["icu_ok"]:
        emite(j, "V33", BLOCANT, "Q", icu=q["Icu_kA"], ik3=t["Ik3max_bara_kA"])

    plecari = inp.get("plecari") or []
    _nota_spl(rez, inp, "pt")
    if not plecari:
        emite(j, "V07", BLOCANT, "schema", "plecari", tablou="TGJT")
        return rez
    pis = [_pi(pl, 0) for pl in plecari]
    spi = sum(pis)
    ks, ks_impl = _ks_bilant(inp, len(plecari))
    if ks_impl:
        j.presupune(f"ks = {fmt_ro(ks)} (IEC 61439-2 tab. 101, {len(plecari)} plecări)")
    j.ipoteza("ks", ks, ks_impl)
    pc = ks * spi
    scal = pc / 0.9
    rez["bilant"] = {"Pi_kW": spi, "ks": ks, "Pc_kW": pc, "Sc_kVA": scal}
    j.pas(f"Bilanț plecări: Σ Pi = {fmt_ro(spi)} kW, ks = {fmt_ro(ks)} → Pc = {fmt_ro(pc)} kW, Sc = {fmt_ro(scal)} kVA")
    if gt(scal, sn):
        emite(j, "V62", AVERTISMENT, "schema", x=scal, y=sn)
    # C.5 pct. 7 (v1.2, C5): punctul de măsură și serviciile proprii sunt GENERATE în rezultat (și desenate)
    loc = str(inp.get("masura_pt") or "JT").upper()
    if loc not in ("JT", "MT"):
        emite(j, "V12", BLOCANT, "schema", "camp", camp="masura_pt", valoare=inp.get("masura_pt"))
        loc = "JT"
    if loc == "JT":
        ptc = prima_din_serie(norme.TC_PRIMAR_A, t["In_T_A"])
        if ptc is None:
            emite(j, "V55", BLOCANT, "TC", "B", Ib=t["In_T_A"], p=max(norme.TC_PRIMAR_A))
            rez["masura"] = {"loc": "JT"}
        else:
            rez["masura"] = {"loc": "JT", "TC_primar_A": ptc, "clasa": "0,5S", "Sn_VA": 5.0}
            j.pas(f"Măsură JT semidirectă: TC 3 × {ptc}/5 A cl. 0,5S (primar ≥ In_T = {fmt_ro(t['In_T_A'])} A), contor trifazat")
    else:
        rez["masura"] = {"loc": "MT"}
        j.pas("Măsură pe MT: celulă de măsură cu TT + TC MT, conform ATR")
    sp_gen = not any("servicii proprii" in (pl.get("nume") or "").lower() for pl in plecari)
    if sp_gen:
        j.presupune(f"servicii proprii PT: plecare {norme.PT_SERVICII_PROPRII_A} A, L = 10 m (iluminat, prize, încălzire în post)")
    elemente = ["neutrul trafo legat la priza de pământ comună MT/JT", "descărcătoare ZnO 24 kV", "servicii proprii PT",
                f"punct de măsură {'JT (TC + contor)' if loc == 'JT' else 'MT (celulă de măsură)'}"]
    if rez["celula_trafo"] == "intreruptor":
        elemente.insert(1, "TC (sau senzori) pentru releul MT")
    emite(j, "V63", INFO, "schema", "INFO", element=", ".join(elemente))
    ctx = sc.context_pt(t)
    if inp.get("schema_pamant") == "TN-C":
        # v1.2 R2 (N-M2): plecările TN-C din TGJT au PEN în cablu (4 conductoare)
        plecari = [dict(pl, cablu=dict(pl.get("cablu") or {}, PE_loc="PEN")) if not pl.get("copii") else pl
                   for pl in plecari]
    rez["plecari"] = _plecari(plecari, ctx, q, j)
    if sp_gen:
        # v1.2 R2 (N-M4): MCB dacă Ik3 bară ≤ Icn max MCB, altfel siguranță gG (limitatoare, 120 kA) pe cablu mic
        # Cu PVC în interiorul postului (metoda C), nu MCCB nelimitator pe cablu mărit pentru stabilitate termică
        rez["servicii_proprii"] = _plecari([{"nume": "Servicii proprii PT", "In_A": norme.PT_SERVICII_PROPRII_A, "L_m": 10,
                                             "prot_tip": "MCB" if t["Ik3max_bara_kA"] <= max(norme.MCB_ICN_KA) else "gG",
                                             "cablu": {"material": "Cu", "metoda": "C"}}],
                                           ctx, q, j, prefix="PT·")[0]
    if inp.get("schema_pamant") == "TN-C":
        # C7 (v1.2): PEN pe plecările din TGJT spre tablouri: ≥ 10 Cu / 16 Al, niciodată cu DDR pe circuit (V27)
        for i, pl in enumerate(rez["plecari"], 1):
            if pl.get("nivel", 0) != 0 or pl.get("blocat"):
                continue
            if pl.get("DDR"):
                emite(j, "V27", BLOCANT, pl["obiect"], detaliu="(TN-C) în aval de DDR 30 mA — separați N/PE înainte de DDR")
            elif lt(pl["S_faza_mm2"], norme.S_MIN_PEN[pl["material"]]):
                emite(j, "V27", BLOCANT, pl["obiect"], detaliu=f"{fmt_ro(pl['S_faza_mm2'])} mm² {pl['material']} < "
                                                              f"{fmt_ro(norme.S_MIN_PEN[pl['material']])} mm²")
            else:
                pl["PEN"] = True
    return rez


# ============================================================================================================
# C.3 CEF (c.a. + c.c.)
# ============================================================================================================
def _context_tg(inp, j, ctx):
    """v1.3 (P0-2): contextul la bara TG-ului existent în care se racordează CEF. Cu `Ik3_TG_kA` (și opțional
    `Zb_TG_ohm`): rețea echivalentă la bara TG (Zb implicit ≥ 2·Z_Q, declarat). Fără: bara TG = punctul de racord
    (OD / PT), majorant pentru Icu, cu flagurile de valoare implicită moștenite (DECIZIE, declarat)."""
    ik3 = inp.get("Ik3_TG_kA")
    if ik3 is None:
        j.presupune("Ik3 la bara TG existent = Ik3 la punctul de racord (majorant pentru Icu) — introdu Ik3_TG_kA "
                    "din calculul TG")
        return dict(ctx, ik3_implicit=True)
    zb = _zb_din_intrare(inp.get("Zb_TG_ohm"), j)
    c = sc.context_od(ik3, zb, ddr_amonte=False, schema=ctx.get("schema", "TN"))
    if zb is None:
        j.presupune(f"Zbuclă la bara TG = 2·Z_Q = {fmt_ro(c['Zb'][0], 3)} + j{fmt_ro(c['Zb'][1], 3)} Ω (din Ik3_TG) — "
                    f"introdu Zb_TG_ohm")
    c["origine"] = ctx.get("origine", "retea_publica")
    for k in ("idn_tt_mA", "ddr_sus", "RA_tt"):
        if k in ctx:
            c[k] = ctx[k]
    return c


def _q_tg_existent(inp, j, ctx, s_iac):
    """v1.3 (P0-2): protecția existentă din TG pe care se leagă QG (`racord_In_Q_A`, `racord_Q_tip`, `racord_Icu_kA`):
    calibru în serie (V05), Ip ≥ Σ Iac (V44 BLOCANT — altfel declanșează la injecție), Icu ≥ Ik3 bara TG (V33)."""
    rin = inp.get("racord_In_Q_A")
    if rin is None:
        j.presupune("protecția din TG existent pentru plecarea CEF nedeclarată — verifică selectivitatea și Icu")
        return None
    tip = pr.normalizeaza_tip(inp.get("racord_Q_tip")) or ("MCB" if rin <= 63 else "MCCB")
    if rin not in pr.SERII[tip]:
        jos, sus = _vecini_serie(pr.SERII[tip], rin)
        emite(j, "V05", BLOCANT, "Q TG", In=rin, tip=tip, vecini=f"{jos} A / {sus} A")
        return None
    q = pr.construieste(tip, rin, rin, "C" if tip == "MCB" else None, are_aval=True)
    if pr.ip(q) < s_iac - 1e-9:
        emite(j, "V44", BLOCANT, "Q TG", "B", x=pr.ip(q), y=s_iac)
    icu = inp.get("racord_Icu_kA")
    if icu is None:
        emite(j, "V33", AVERTISMENT, "Q TG", "nedecl", ik3=ctx["Ik3_kA"])
        q["Icu_kA"] = None
    else:
        q["Icu_kA"] = float(icu)
        if lt(float(icu), ctx["Ik3_kA"]):
            emite(j, "V33", BLOCANT, "Q TG", icu=float(icu), ik3=ctx["Ik3_kA"])
    j.pas(f"Racord în TG existent: Q TG {tip} {fmt_ro(rin)} A (Ip {fmt_ro(pr.ip(q))} A ≥ Σ Iac {fmt_ro(s_iac)} A), "
          f"Ik3 bara TG {fmt_ro(ctx['Ik3_kA'])} kA")
    return q


def _verifica_q_tg_c0(j, q, c0, ctx):
    """v1.3 (P0-2): Q TG față de cablul C0 — suprasarcină (Ip Q TG ≤ Iz' C0, altfel C0 e protejat doar de QG) și
    deconectarea unui defect la capătul C0 (bara TGD-CF), alimentat din rețea prin Q TG, în 5 s."""
    if gt(pr.ip(q), c0["Iz_corectat_A"]):
        emite(j, "V44", AVERTISMENT, "Q TG / C0", "iz", x=pr.ip(q), iz=c0["Iz_corectat_A"])
    else:
        emite(j, "V44", INFO, "Q TG / C0", "INFO", x=pr.ip(q), iz=c0["Iz_corectat_A"])
    ia = pr.ia(q, 5.0)
    if ia is not None and lt(c0["Ik1min_capat_A"], ia):
        emite(j, "V44", AVERTISMENT if ctx.get("z_implicit") or ctx.get("ik3_implicit") else BLOCANT, "Q TG / C0",
              "deconectare", ik1=round(c0["Ik1min_capat_A"]), ia=ia)


def schema_cef(inp, j):
    """SPEC §C.3: invertoare și PCS (ramuri B.21), sume, QG, praguri de racord, PT propriu, categoria RfG, TC,
    partea de c.c. (Uoc la Tmin, gPV, SPD c.c.). v1.2: Iac,max din fișă verificat (V64), S_total = max(√3·U·ΣIac; ΣPn),
    CEF monofazat calculat la 230 V (C3), racord prin BMPT verificat față de Q BMPT (M4), β_Uoc > 0 → V68 (C9)."""
    rez = {}
    retea = inp.get("retea") or "tri"
    mono = retea == "mono"
    U = u_calcul(retea)
    u_txt = "230 V" if mono else "√3·400 V"
    unitati = []
    for grup in inp.get("invertoare") or []:
        for _ in range(int(grup.get("n", 1))):
            unitati.append({"Pn_kW": float(grup["Pn_kW"]), "Iac_max_A": grup.get("Iac_max_A"), "pcs": False,
                            "grup": grup})
    for i, u in enumerate(unitati, 1):
        u["obiect"] = f"INV-{i}"
    bess = inp.get("bess")
    if not unitati and not bess:
        emite(j, "V07", BLOCANT, "schema", "lipsa")
        return rez
    if unitati and inp.get("kWp") is not None and not gt(float(inp["kWp"]), 0.0):
        # M8 (v1.2): invertoare PV fără putere PV instalată
        emite(j, "V07", BLOCANT, "schema", "param", camp="kWp", x=inp["kWp"], conditie="trebuie > 0 când există invertoare PV")
        return rez
    if bess:
        p = bess.get("P_kW")
        if p is None:
            if not bess.get("kWh"):
                emite(j, "V07", BLOCANT, "PCS", "lipsa")
                return rez
            p = float(bess.get("kWh", 0)) / 2.0
            j.presupune(f"PCS BESS P = kWh/2 = {fmt_ro(p)} kW (0,5C)")
        unitati.append({"Pn_kW": float(p), "Iac_max_A": bess.get("Iac_max_A"), "pcs": True, "obiect": "PCS"})
    if mono:
        rez["retea"] = "mono"
        j.presupune("CEF monofazat: Iac = 1,1·Pn/230, protecții 1P+N, cabluri cu 3 conductoare, ΔU pe 230 V")
    # C2 (v1.2): Iac,max din fișă nu poate fi sub Pn/U (cosφ = 1 la tensiunea nominală)
    for u in unitati:
        if u["Iac_max_A"] is not None:
            i_fiz = u["Pn_kW"] * 1000.0 / U
            if lt(float(u["Iac_max_A"]), i_fiz * (1 - 1e-3)):     # R2: toleranță 0,1 % (rotunjirea fișei)
                emite(j, "V64", BLOCANT, u["obiect"], x=float(u["Iac_max_A"]), y=i_fiz, P=u["Pn_kW"], U=u_txt)
    if j.are_blocant():
        return rez
    for u in unitati:
        u["Iac"] = u["Iac_max_A"] or norme.FACTOR_SMAX_INVERTOR * u["Pn_kW"] * 1000.0 / U
    s_iac = sum(u["Iac"] for u in unitati)
    s_iac_kva = U * s_iac / 1000.0
    pn_tot = sum(u["Pn_kW"] for u in unitati)
    pn_inv = sum(u["Pn_kW"] for u in unitati if not u["pcs"])
    s_tot = max(s_iac_kva, pn_tot)
    rez["sume"] = {"Pn_total_kW": pn_tot, "Iac_total_A": s_iac, "S_total_kVA": s_tot, "S_din_Iac_kVA": s_iac_kva}
    if inp.get("kWp") is not None and pn_inv > 0:
        rez["raport_DC_AC"] = float(inp["kWp"]) / pn_inv
    j.pas(f"Σ Iac,max = {' + '.join(fmt_ro(u['Iac']) + (' (PCS)' if u['pcs'] else '') for u in unitati)} = "
          f"{fmt_ro(s_iac)} A; S = max({'230' if mono else '√3·400'}·Σ Iac = {fmt_ro(s_iac_kva)} kVA; Σ Pn = "
          f"{fmt_ro(pn_tot)} kW) = {fmt_ro(s_tot)} kVA")

    # racord (pct. 4–5)
    sn = inp.get("pt_Sn_kVA")
    if inp.get("racord") == "pt" and sn is None:
        emite(j, "V07", BLOCANT, "schema", "param", camp="pt_Sn_kVA", x="—", conditie="racord „pt” fără puterea PT")
        return rez
    t = None
    racord = None
    if mono:
        if sn is not None:
            emite(j, "V12", BLOCANT, "schema", poli="monofazat", retea="cu PT propriu (trifazat)")
            return rez
        if gt(s_iac, norme.BMPM["I_max_A"]):
            emite(j, "V53", BLOCANT, "schema", "inv", Ib=s_iac)
            return rez
        if gt(pn_tot, norme.MONOFAZAT_P_INVERTOR_AVERTISMENT_KW):
            emite(j, "V71", AVERTISMENT, "schema", P=pn_tot)
        racord = {"tip": "JT monofazat prin BMPM", "In_Q_max_A": norme.BMPM["I_max_A"]}
        ctx = _context_od(inp, j, ddr_amonte=False)
    elif sn is not None:
        if int(sn) not in norme.TRAFO or float(sn) != int(sn):
            emite(j, "V05", BLOCANT, "schema", "trafo", Sn=sn, vecini=", ".join(str(s) for s in norme.TRAFO_SN_KVA))
            return rez
        t = sc.trafo(int(sn), inp.get("SkQ_MVA"))
        if inp.get("SkQ_MVA") is None:
            j.presupune("S\"kQ = 500 MVA, R/X = 0,1 (rețea MT, majorant)")
        j.ipoteza("skq", t["SkQ_MVA"], inp.get("SkQ_MVA") is None)
        j.ipoteza("trafo", (t["uk_pct"], t["Pk_W"]), True)
        rez["trafo"] = {"Sn_kVA": int(sn), "In_T_A": t["In_T_A"], "Ik3max_bara_kA": t["Ik3max_bara_kA"]}
        if lt(sn, s_tot):
            emite(j, "V67", BLOCANT, "schema", x=sn, y=s_tot)
        ctx = sc.context_pt(t)
        racord = {"tip": "MT prin PT propriu", "Sn_kVA": int(sn)}
    else:
        if gt(s_tot, norme.PRAG_RACORD_JT_MAX_KVA) and not inp.get("atr_jt"):
            emite(j, "V66", BLOCANT, "schema", "B", x=s_tot)
            racord = {"tip": "MT (PT propriu necesar)"}
        elif gt(s_tot, norme.PRAG_RACORD_BMPT_KVA):
            emite(j, "V66", AVERTISMENT, "schema", "AV", x=s_tot)
            racord = {"tip": "JT direct din PT OD conform ATR"}
        else:
            racord = {"tip": "JT prin BMPT", "bloc": "BMPTi-250", "In_Q_max_A": norme.BMPT_I_MAX_A}
        ctx = _context_od(inp, j, ddr_amonte=False)
    rez["racord"] = racord
    idn_qg = None
    if inp.get("schema_pamant") == "TT":
        # v1.2 R3 (N3-C2): TT — DDR pe QG (S, IΔn maxim admis de RA) și pe fiecare invertor/PCS (≤ IΔn_QG/3);
        # segmentul QG → PCC protejat de DDR-ul din amonte (RCCB BMPT 300 mA sau IdN_amonte_mA declarat)
        ra, lim = _tt_ra(inp, j)
        if lim is None:
            return rez
        idn_am = _tt_amonte(inp, j, ra, bmpt=bool(racord and "BMPT" in racord.get("tip", "")))
        if idn_am is None:
            return rez
        # v1.3 R5 (§C.2 pct. 13, M5-4): ca la tablou — amonte temporizat → QG fără DDR propriu, invertoare instantanee
        # ≤ IΔn amonte/3; altfel bloc diferențial reglabil asociat QG (Δt 0,15 s)
        am = ddr_mod.descriere(idn_am, inp.get("DDR_amonte_selectiv", True),
                               "DDR amonte (declarat)" if inp.get("IdN_amonte_mA") is not None else "RCCB BMPT")
        al = ddr_mod.alege_tt(lim, am)
        sus = am
        if al["intrare"]:
            idn_qg = al["intrare"]["IdN_mA"]
            sus = ddr_mod.descriere(idn_qg, True, "DDR QG", al["intrare"]["dt_s"])
            ddr_mod.verifica(j, am, sus, "QG", RA_ohm=ra)
        ctx = dict(ctx, idn_tt_mA=al["idn_circuite"], ddr_sus=sus, RA_tt=ra)
        rez["IdN_amonte_mA"] = idn_am
        rez["DDR_TT_IdN_mA"] = max(al["idn_circuite"], idn_am, idn_qg or 0)
        j.pas(f"TT: RA = {fmt_ro(ra)} Ω → IΔn ≤ {fmt_ro(50000.0 / ra, 0)} mA; amonte {am['denumire']} {idn_am} mA "
              f"{am['temporizare']} → " + (f"QG bloc diferențial reglabil {idn_qg} mA, Δt {fmt_ro(DT_QG, 2)} s"
                                         if idn_qg else "QG fără DDR propriu (protejat de amonte)") +
              f"; invertoare DDR {al['idn_circuite']} mA instantaneu")
    # categoria RfG (pct. 6)
    if ge(pn_tot, norme.RFG_PRAG_TIP_D_KW):
        cat = "D"
    elif ge(pn_tot, norme.RFG_PRAG_TIP_C_KW):
        cat = "C"
    elif ge(pn_tot, norme.RFG_PRAG_TIP_B_KW):
        cat = "B"
    else:
        cat = "A"
    rez["categorie_RfG"] = cat
    emite(j, "V70", INFO if cat == "A" else AVERTISMENT, "schema", "INFO" if cat == "A" else "AV", X=cat, P=pn_tot)

    # v1.3 (P0-2): punctul de racord — TG existent (QG se leagă pe o plecare a tabloului general existent) și C0
    tg = inp.get("racord") == "tg_existent"
    ctx_pcc = _context_tg(inp, j, ctx) if tg else ctx
    if tg:
        racord["tg_existent"] = True
        racord["tip"] = f"TG existent (consum propriu) — {racord['tip']}"
    L0 = inp.get("L_racord_m")

    def ramura_unitate(u):
        """Intrarea B.1 a cablului unui invertor / PCS (v1.3, P0-2): cablu pe grup > `cablu_inv`/`cablu_pcs` > `cablu`
        global (material, izolație, metodă, θ, ρ_sol, grupare); lungime `invertoare[].L_m` > cablu.L > `L_inv_m` > 30 m."""
        g = u.get("grup") or {}
        cab_in = {k: v for k, v in (inp.get("cablu") or {}).items() if k in CAMPURI_CABLU_SCHEMA and v is not None}
        cab_in.update({k: v for k, v in ((inp.get("cablu_pcs") if u["pcs"] and inp.get("cablu_pcs") else
                                          inp.get("cablu_inv")) or {}).items() if v is not None})
        cab_in.update({k: v for k, v in (g.get("cablu") or {}).items() if v is not None})
        cb.metoda_implicita(cab_in, "D1")
        if "material" not in cab_in:
            cab_in["material"] = "Al" if cab_in["metoda"] in norme.METODE_IN_PAMANT else "Cu"
            cab_in["material_implicit"] = True
            if cab_in["material"] == "Al":
                j.presupune("cabluri invertoare Al PVC în tub în pământ (D1)")
        L = g.get("L_m", (g.get("cablu") or {}).get("L"))
        if L is None:
            L = inp.get("L_pcs_m") if u["pcs"] else inp.get("L_inv_m")
        if L is None:
            L = cab_in.get("L")
        if L is None:
            L = 30.0
            j.presupune("lungime cablu invertor CEF 30 m")
        cab_in["L"] = float(L)
        r = {"rol": "invertor", "receptor": "pcs" if u["pcs"] else "invertor", "retea": retea,
             "Pn_kW": u["Pn_kW"], "cablu": cab_in}
        if u["Iac_max_A"]:
            r["Iac_max_A"] = u["Iac_max_A"]
        return r

    # QG (pct. 3): Ip,min = max(Σ Iac; Ip invertoare) — protecțiile invertoarelor se calculează întâi (doar Ip)
    jt = Jurnal()
    ip_inv = [x["Ip"] for x in (calculeaza_ramura(dict(ramura_unitate(u), _doar_protectie=True), ctx_pcc, jt, "tmp")
                                for u in unitati) if x["Ip"] is not None]
    ip_min = max([s_iac] + ip_inv)
    in_f = inp.get("In_QG_A")
    ref = in_f if in_f is not None else ip_min
    tip = "MCCB" if ref <= 1600 + 1e-9 else "ACB"
    In = in_f if in_f is not None else pr.alege_calibru(tip, ip_min)
    if In is None:
        emite(j, "V06", BLOCANT, "QG", Ib=s_iac, tip="ACB")
        return rez
    qg = pr.construieste(tip, In, ip_min, are_aval=True)
    qg["Icu_kA"], ok = pr.alege_icu(tip, ctx_pcc["Ik3_kA"])
    if qg.get("decl") == "EL":
        pr.alege_isd(qg, sc.ik1_din_zb(ctx_pcc["Zb"]))
    rez["QG"] = {"tip": tip, "In_A": In, "Ir_A": qg["Ir_A"], "Ir_multiplu": qg["Ir_multiplu"], "Icu_kA": qg["Icu_kA"],
                 "poli": "2P" if mono else "4P"}
    for k in ("decl", "Im_A", "Isd_A", "Isd_multiplu", "tsd_s", "Ii_A"):
        if qg.get(k) is not None:
            rez["QG"][k] = qg[k]
    if idn_qg is not None:
        # v1.3 R5: bloc diferențial reglabil asociat QG (Δt explicit)
        rez["QG"]["DDR"] = {"IdN_mA": idn_qg, "tip": "A", "selectiv": True, "temporizare": "reglabil", "dt_s": DT_QG,
                            "reglabil": True, "poli": "2P" if mono else "4P", "In_A": In, "aparat": "bloc_diferential",
                            "asociat": "QG", "tip_q": tip}
    j.pas(f"QG: Ip,min = max(Σ Iac {fmt_ro(s_iac)}; Ip max invertor {fmt_ro(max(ip_inv) if ip_inv else 0)}) = "
          f"{fmt_ro(ip_min)} A → {tip} {In} A, Ir {fmt_ro(qg['Ir_A'])} A")
    if in_f is not None and In not in pr.SERII[tip]:
        emite(j, "V05", BLOCANT, "QG", In=In, tip=tip, vecini="")
    if lt(pr.ip(qg), s_iac):
        emite(j, "V65", BLOCANT, "schema", x=pr.ip(qg), y=s_iac)
    if not ok:
        emite(j, "V33", BLOCANT, "QG", icu=qg["Icu_kA"], ik3=ctx_pcc["Ik3_kA"])
    if t is not None and gt(qg["Ir_A"], t["In_T_A"]):
        emite(j, "V60", AVERTISMENT, "schema", "AV", x=qg["Ir_A"], y=t["In_T_A"])
    # M4 (v1.2): racord JT prin BMPT/BMPM — QG trebuie să se coordoneze cu Q din bloc (In Q max 250 A / 40 A)
    if racord and racord.get("In_Q_max_A") is not None and gt(pr.ip(qg), racord["In_Q_max_A"]):
        emite(j, "V66", BLOCANT, "schema", "bmpt", x=pr.ip(qg), y=racord["In_Q_max_A"])

    # v1.3 (P0-2): protecția existentă din TG pe care se leagă QG (opțională)
    q_tg = _q_tg_existent(inp, j, ctx_pcc, s_iac) if tg else None
    if q_tg is not None:
        rez["Q_TG"] = {k: q_tg.get(k) for k in ("tip", "In_A", "Ir_A", "curba", "Icu_kA") if q_tg.get(k) is not None}

    # v1.3 (P0-2): cablul C0 (TGD-CF → punctul de racord) — ramură completă, protejată de QG, Ik din punctul de racord
    ctx_inv = ctx_pcc
    if L0 is not None:
        cab0 = {k: v for k, v in (inp.get("cablu") or {}).items() if k in CAMPURI_CABLU_SCHEMA and v is not None}
        cab0.update({k: v for k, v in (inp.get("cablu_C0") or {}).items() if v is not None})
        cb.metoda_implicita(cab0, "D1")
        if cab0.get("material") is None:
            cab0["material"] = "Al" if cab0["metoda"] in norme.METODE_IN_PAMANT else "Cu"
            cab0["material_implicit"] = True
            j.presupune(f"cablu C0 {cab0['material']} PVC, metoda {cab0['metoda']}")
        cab0["L"] = float(L0)
        r0 = {"rol": "c0", "receptor": "invertor", "retea": retea, "Pn_kW": pn_tot, "Iac_max_A": s_iac,
              "cablu": cab0, "prot_tip": tip, "In_fortat": In, "Icu_fortat": qg["Icu_kA"], "are_aval": True,
              "_validat": True}
        if qg.get("curba"):
            r0["curba"] = qg["curba"]
        rr0 = calculeaza_ramura(r0, ctx_pcc, j, "C0", amonte=q_tg, obiect_sel="Q TG vs QG")
        rez["C0"] = dict(rr0["rezultat"], descriere="TGD-CF → " + ("TG existent" if tg else "punctul de racord"))
        if not rr0["blocat"]:
            ctx_inv = dict(rr0["ctx_aval"], dU_cef_pct=rr0["rezultat"]["dU_cumulat_pct"])
            rez["bara_TGD_CF"] = {"Ik3max_kA": ctx_inv["Ik3_kA"], "dU_pct": rr0["rezultat"]["dU_cumulat_pct"]}
            if q_tg is not None:
                _verifica_q_tg_c0(j, q_tg, rr0["rezultat"], ctx_pcc)
    elif tg and q_tg is not None:
        pr.selectivitate(q_tg, qg, ctx_pcc["Ik3_kA"], "Q TG vs QG", j)

    # invertoare și PCS (pct. 1) — cu contextul barei TGD-CF (capătul C0, dacă există)
    ramuri = []
    for u in unitati:
        rr = calculeaza_ramura(ramura_unitate(u), ctx_inv, j, u["obiect"])
        ramuri.append((u, rr))
    rez["invertoare"] = [rr["rezultat"] for u, rr in ramuri if not u["pcs"]]
    for u, rr in ramuri:
        if u["pcs"]:
            rez["PCS"] = rr["rezultat"]
    for u, rr in ramuri:
        if not rr["blocat"]:
            pr.selectivitate(qg, rr["prot"], ctx_inv["Ik3_kA"], f"QG vs {u['obiect']}", j)

    # TC măsură (pct. 8, B.19) — la monofazat măsura e directă (BMPM, contor 5(60) A)
    if mono:
        rez["contor"] = "monofazat direct 230 V, 5(60) A, bidirecțional (furnizat de OD)"
    else:
        p = prima_din_serie(norme.TC_PRIMAR_A, max(s_iac, In / norme.TC_FACTOR_EXTINDERE))
        if p is None:
            emite(j, "V55", BLOCANT, "TC", "B", Ib=s_iac, p=max(norme.TC_PRIMAR_A))
        else:
            rez["TC"] = f"3 {X} {p}/5{NB}A, cl. 0,5S"
            rez["TC_primar_A"] = p

    # c.c. (pct. 9)
    st = inp.get("string")
    if st:
        beta = st.get("beta")
        if beta is None:
            beta = norme.PV_BETA_UOC_IMPLICIT_PCT_K
            j.presupune("β_Uoc = −0,27 %/K (tipic c-Si)")
        elif not lt(float(beta), 0.0) or lt(float(beta), -1.0):
            # C9 (v1.2): β_Uoc ≥ 0 (sau < −1 %/K) e neplauzibil — nu se ia în modul, se cere fișa corectă
            emite(j, "V68", BLOCANT, "schema", "beta", x=float(beta))
            return rez
        if st.get("n_module") is None or st.get("Uoc_V") is None:
            emite(j, "V07", BLOCANT, "string", "param", camp="n_module / Uoc_V", x="—", conditie="lipsesc datele stringului")
            return rez
        umax = st.get("Umax_inv_V")
        if umax is None:
            umax = norme.PV_UMAX_INVERTOR_IMPLICIT_V
            j.presupune("Umax invertor 1100 V")
        tmin = norme.PV_T_MIN_C
        uoc = st["n_module"] * st["Uoc_V"] * (1 + beta / 100.0 * (tmin - 25.0))
        rez["Uoc_Tmin_V"] = uoc
        rez["Umax_inv_V"] = umax
        j.pas(f"Uoc(−25 °C) = {st['n_module']}·{fmt_ro(st['Uoc_V'])}·[1 + ({fmt_ro(beta)}/100)·(−25 − 25)] = "
              f"{fmt_ro(uoc, 1)} V")
        lim_u = min(umax, st.get("Umax_modul_V") or umax)
        if gt(uoc, lim_u):
            emite(j, "V68", BLOCANT, "schema", "B", x=round(uoc, 1), y=lim_u)
        else:
            emite(j, "V68", INFO, "schema", "INFO", x=round(uoc, 1), y=lim_u)
        ucpv = prima_din_serie(norme.SPD_CC_UCPV_V, uoc)
        if ucpv is None:
            emite(j, "V74", BLOCANT, "schema", x=max(norme.SPD_CC_UCPV_V), y=round(uoc, 1))
        else:
            rez["SPD_cc_Ucpv_V"] = ucpv
        ns = st.get("n_stringuri_paralel", 1)
        if ns >= norme.GPV_NECESAR_DE_LA_STRINGURI:
            isc = st.get("Isc_A")
            if isc is None:
                emite(j, "V69", BLOCANT, "schema", a="—", b="— (lipsește Isc_STC)")
                return rez
            a = norme.GPV_IN_MIN_FACTOR * isc
            b = norme.GPV_IN_MAX_FACTOR * isc
            if st.get("I_rev_A") is not None:
                b = min(b, st["I_rev_A"])
            cand = [x for x in norme.GPV_IN_A if ge(x, a) and ge(b, x)]
            j.pas(f"gPV: 1,5·Isc = {fmt_ro(a)} ≤ In ≤ min(2,4·Isc; Irev) = {fmt_ro(b)} → "
                  f"{fmt_ro(cand[0]) + ' A' if cand else '—'}")
            if not cand:
                emite(j, "V69", BLOCANT, "schema", a=a, b=b)
            else:
                rez["gPV_In_A"] = cand[0]
    _nota_spl(rez, inp, "cef")
    return rez


# ============================================================================================================
# C.4 Prosumator
# ============================================================================================================
def schema_prosumator(inp, j):
    """SPEC §C.4: prosumator mono/tri — limite (400 kW, 40 A mono, 3,68 kW), ramura invertorului, V72, V73."""
    rez = {}
    retea = inp.get("retea") or "tri"
    U = u_calcul(retea)
    if inp.get("Pn_inv_kW") is None:
        emite(j, "V07", BLOCANT, "schema", "lipsa")
        return rez
    pn = float(inp["Pn_inv_kW"])
    iac = inp.get("Iac_max_A") or norme.FACTOR_SMAX_INVERTOR * pn * 1000.0 / U
    rez["Iac_max_A"] = iac
    j.pas(f"Iac,max = 1,1·{fmt_ro(pn)}·1000/{'(√3·400)' if retea == 'tri' else '230'} = {fmt_ro(iac)} A")
    if gt(pn, norme.PROSUMATOR_P_MAX_KW):
        emite(j, "V70", BLOCANT, "schema", "B")
        return rez
    if retea == "mono" and gt(iac, norme.BMPM["I_max_A"]):
        emite(j, "V53", BLOCANT, "schema", "inv", Ib=iac)
        return rez
    if retea == "mono" and gt(pn, norme.MONOFAZAT_P_INVERTOR_AVERTISMENT_KW):
        emite(j, "V71", AVERTISMENT, "schema", P=pn)
    rez["PI"] = "protecție de interfață integrată în invertor, certificată (Ord. ANRE 228/2018), reglaje conform ATR"
    rez["contor"] = "bidirecțional, furnizat de OD"
    ctx = _context_od(inp, j, ddr_amonte=True)
    cab = dict(inp.get("cablu") or {})
    cb.metoda_implicita(cab, "C")
    cab.setdefault("material", "Cu")
    L = inp.get("L_inv_m", cab.get("L"))
    if L is None:
        L = 15.0
        j.presupune("lungime cablu invertor prosumator 15 m")
    cab["L"] = float(L)
    if inp.get("cablu") is None:
        j.presupune("cablu invertor Cu PVC, metoda C")
    r = {"rol": "invertor", "receptor": "invertor", "retea": retea, "Pn_kW": pn, "cablu": cab}
    if inp.get("Iac_max_A"):
        r["Iac_max_A"] = inp["Iac_max_A"]
    if inp.get("schema_pamant") == "TT":
        # v1.2 R3 (N3-C2): DDR 30 mA tip A pe circuitul invertorului; RA·IΔn ≤ 50 V, altfel V34 BLOCANT
        ra, lim = _tt_ra(inp, j)
        if lim is None:
            return rez
        rez["DDR_TT_IdN_mA"] = 30
        ctx = dict(ctx, idn_tt_mA=30)
    rr = calculeaza_ramura(r, ctx, j, "INV")
    rez["INV"] = rr["rezultat"]
    if not rr["blocat"]:
        In_i = rr["rezultat"]["protectie"]["In_A"]
        mare = In_i > norme.RCCB_IN_A[-1]
        rez["INV"]["DDR"] = {"IdN_mA": 30, "tip": "A", "In_A": In_i if mare else
                             (prima_din_serie(norme.RCCB_IN_A, max(In_i, 16 if retea == "mono" else 25)) or In_i),
                             "poli": "2P" if retea == "mono" else "4P", "aparat": "bloc_diferential" if mare else "RCCB"}
        # v1.3 (§B.18.1): DDR-ul invertorului în aval de DDR-ul branșamentului (RCCB BMPT 300 mA S / RCBO BMPM)
        ddr_mod.verifica(j, _ddr_amonte(inp, retea), ddr_mod.descriere(30, False, "DDR INV"), "INV",
                         RA_ohm=inp.get("RA_ohm") if inp.get("schema_pamant") == "TT" else None)
    inq = inp.get("In_Q_bransament_A")
    if inq is not None:
        if gt(iac, inq):
            emite(j, "V72", AVERTISMENT, "schema", "AV", x=iac, y=inq)
        else:
            emite(j, "V72", INFO, "schema", "INFO", x=iac, y=inq)
    emite(j, "V73", AVERTISMENT, "schema")
    _nota_spl(rez, inp, "prosumator")
    return rez


# ============================================================================================================
# C.6 Grup electrogen + ATS
# ============================================================================================================
def _context_ge(in_g, sn_kva, xd, ik1_ge):
    """SPEC §B.13 / §C.6 (v1.2): contextul la bornele GE — Z_Q = j·x"d·Un²/Sn (Ik3" = c_max·In_G/x"d), bucla fază–PE
    aleasă astfel încât Ik1 la borne = Ik1 în regim GE (In_G sau 3·In_G cu excitație susținută)."""
    x_ohm = xd * norme.U_N_V ** 2 / (sn_kva * 1000.0)
    zb_mod = sc.C_MIN * norme.U_0_V / ik1_ge
    return {"Zq": (0.0, x_ohm), "Zb": (0.0, zb_mod), "Ik3_kA": sc.ge_ik3(in_g, xd) / 1000.0, "dU_pct": 0.0,
            "origine": "retea_publica", "z_implicit": False, "ik3_implicit": False, "ddr_amonte": False,
            "ddr_ramura": None, "are_aval": False, "schema": "TN", "regim_ge": True}


def schema_ge(inp, j):
    """SPEC §C.6: In_G, Q_G, Ik3" GE, Q rețea, ATS (4P, interblocaj, AC-33B), deconectarea în regim GE (V85), V86, V87.
    v1.2: Q_G MCCB/ACB cu Ir ≤ In_G (M3, protecție strictă la suprasarcină), Icu QR ≥ Ik3 rețea și QG ≥ Ik3 GE,
    cablurile C1 (rețea → ATS, QR), C2 (GE → ATS, QG) și C3 (ATS → consumatori) dimensionate ca ramuri B.21."""
    rez = {}
    U = SQRT3 * norme.U_N_V
    if inp.get("Sn_GE_kVA") is None:
        emite(j, "V07", BLOCANT, "schema", "param", camp="Sn_GE_kVA", x="—", conditie="lipsește puterea GE (kVA)")
        return rez
    sn = float(inp["Sn_GE_kVA"])
    in_g = sn * 1000.0 / U
    xd = inp.get("xd")
    if xd is None:
        xd = norme.GE_XD2_IMPLICIT
        j.presupune("x\"d = 0,12 (lipsește din fișa GE)")
    rez["In_G_A"] = in_g
    ik3 = sc.ge_ik3(in_g, xd)
    rez["Ik3_GE_kA"] = ik3 / 1000.0

    # Q_G: Ir ≤ In_G (cel mai mare reglaj care nu depășește In_G), In = cel mai mic calibru ≥ In_G
    in_qg = inp.get("In_QG_A")
    tip_g = "MCCB" if (in_qg if in_qg is not None else in_g) <= 1600 + 1e-9 else "ACB"
    In_G = in_qg if in_qg is not None else pr.alege_calibru(tip_g, in_g)
    if In_G is None:
        emite(j, "V06", BLOCANT, "Q_G", Ib=in_g, tip="ACB")
        return rez
    if in_qg is not None and In_G not in pr.SERII[tip_g]:
        jos, sus = _vecini_serie(pr.SERII[tip_g], In_G)
        emite(j, "V05", BLOCANT, "Q_G", In=In_G, tip=tip_g, vecini=f"{jos} A / {sus} A")
        return rez
    k_g, ir_g = pr.alege_reglaj_ir_max(tip_g, In_G, in_g)
    if k_g is None:
        emite(j, "V60", BLOCANT, "schema", "B", x=In_G, y=in_g)
        return rez
    qg = pr.construieste(tip_g, In_G, ir_g, are_aval=True)
    qg["Icu_kA"], ok_g = pr.alege_icu(tip_g, ik3 / 1000.0)
    rez["Q_G"] = {"tip": tip_g, "In_A": In_G, "Ir_A": qg["Ir_A"], "Ir_multiplu": qg["Ir_multiplu"],
                  "Icu_kA": qg["Icu_kA"], "decl": qg.get("decl")}
    j.pas(f"GE {fmt_ro(sn)} kVA: In_G = {fmt_ro(in_g)} A; Ik3'' ≈ 1,1·In_G/x''d = {fmt_ro(ik3 / 1000.0)} kA; "
          f"Q_G {tip_g} {In_G} A, Ir = {fmt_ro(qg['Ir_multiplu'])}·In = {fmt_ro(qg['Ir_A'])} A ≤ In_G, "
          f"Icu {fmt_ro(qg['Icu_kA'])} kA")
    if not ok_g:
        emite(j, "V33", BLOCANT, "Q_G", icu=qg["Icu_kA"], ik3=ik3 / 1000.0)

    cos = inp.get("cosfi", norme.COSFI_IMPLICIT["tablou"])
    if inp.get("P_sarcina_kW") is not None:
        # SPEC §C.6 pct. 5: puterea GE minimă din seria GE_SN_KVA (Sn ≥ P/cosφ), raportată totdeauna
        rez["Sn_GE_minim_kVA"] = norme.ge_sn_minim(float(inp["P_sarcina_kW"]), cos)
        j.pas(f"GE minim: Sn ≥ {fmt_ro(inp['P_sarcina_kW'])}/{fmt_ro(cos)} = "
              f"{fmt_ro(float(inp['P_sarcina_kW']) / cos)} kVA → {rez['Sn_GE_minim_kVA']} kVA (fără pornirea motoarelor)")
    ib = None
    if inp.get("P_sarcina_kW") is not None:
        ib = float(inp["P_sarcina_kW"]) * 1000.0 / (U * cos)
    elif inp.get("Ib_sarcina_A") is not None:
        ib = float(inp["Ib_sarcina_A"])
    if ib is None:
        ib = qg["Ir_A"]
        j.presupune(f"sarcina consumatorilor nedată: Ib = Ir Q_G = {fmt_ro(ib)} A (cablurile se dimensionează la puterea GE)")
    if gt(ib, in_g):
        emite(j, "V86", BLOCANT, "schema", x=ib, y=in_g, Sn=rez.get("Sn_GE_minim_kVA") or "—")
    elif gt(ib, qg["Ir_A"]):
        emite(j, "V86", BLOCANT, "schema", "ir", x=ib, y=qg["Ir_A"], Sn=rez.get("Sn_GE_minim_kVA") or "—")

    # lungimi (v1.2): C1 rețea → ATS și C3 ATS → consumatori din L_C1_m / L_C3_m sau L_m; C2 GE → ATS din L_C2_m
    def lung(cheie, alt, implicit, text):
        """Lungimea unui cablu GE/ATS, cu declararea valorii implicite."""
        v = inp.get(cheie)
        if v is None and alt is not None:
            v = inp.get(alt)
        if v is None:
            v = implicit
            j.presupune(f"lungime {text} {fmt_ro(implicit, 0)} m")
        return float(v)

    cab0 = dict(inp.get("cablu") or {})
    cb.metoda_implicita(cab0, "D1")

    def cablu(L):
        """Cablul unei ramuri GE/ATS (implicit Al PVC D1, ca alimentarea unui tablou)."""
        c = dict(cab0)
        if "material" not in c:
            c["material"] = "Al" if c["metoda"] in norme.METODE_IN_PAMANT else "Cu"
            c["material_implicit"] = True
            j.presupune("cabluri GE/ATS Al PVC în tub în pământ (D1), cu trecere pe Cu sub 16 mm²")
        c["L"] = L
        return c

    # C1: rețea → ATS, protejat de QR (Icu ≥ Ik3 rețea)
    # v1.2 R3 (N3-M1): alimentarea normală. Fără `origine` = rețea publică prin branșament: Ib > 250 A → V50 BLOCANT
    # (nu există BMPT; racord din PT). Cu `origine = "pt_propriu"`: impedanța și Ik din PT (ca la tablou, §B.1.1), iar
    # Sn PT trebuie să acopere sarcina consumatorilor (altfel V62 BLOCANT).
    if inp.get("origine") == "pt_propriu":
        sn_pt = inp.get("pt_Sn_kVA")
        if sn_pt is not None:
            if int(sn_pt) not in norme.TRAFO or float(sn_pt) != int(sn_pt):
                emite(j, "V05", BLOCANT, "schema", "trafo", Sn=sn_pt, vecini=", ".join(str(x) for x in norme.TRAFO_SN_KVA))
                return rez
            t = sc.trafo(int(sn_pt), inp.get("SkQ_MVA"))
            if inp.get("SkQ_MVA") is None:
                j.presupune("S\"kQ = 500 MVA, R/X = 0,1 (rețea MT, majorant)")
            j.ipoteza("skq", t["SkQ_MVA"], inp.get("SkQ_MVA") is None)
            j.ipoteza("trafo", (t["uk_pct"], t["Pk_W"]), True)
            ctx_r = sc.context_pt(t)
            rez["PT_retea"] = {"Sn_kVA": int(sn_pt), "In_T_A": t["In_T_A"], "Ik3max_bara_kA": t["Ik3max_bara_kA"]}
            s_sarc = SQRT3 * norme.U_N_V * ib / 1000.0
            if gt(s_sarc, float(sn_pt)):
                emite(j, "V62", BLOCANT, "schema", "ge", x=s_sarc, y=sn_pt)
            j.presupune(f"rețeaua normală: bara JT a PT propriu {sn_pt} kVA")
        else:
            ctx_r = _context_od(inp, j, ddr_amonte=False)
            ctx_r["origine"] = "pt_propriu"
            j.presupune("rețeaua normală: PT propriu cu Sn necunoscut — Ik3max 25 kA și Zbuclă 0,201 Ω implicite")
    else:
        if gt(ib, norme.BMPT_I_MAX_A):
            emite(j, "V50", BLOCANT, "schema", "ib", Ib=ib)
            return rez
        ddr_amonte = inp.get("ddr_amonte", True)
        ctx_r = _context_od(inp, j, ddr_amonte=ddr_amonte)
        if ddr_amonte:
            j.presupune("rețeaua normală: rețea publică prin BMPT cu RCCB 300 mA în amonte")
    in_r = inp.get("In_Q_retea_A")
    tip_r = "MCCB" if (in_r if in_r is not None else ib) <= 1600 + 1e-9 else "ACB"
    r1 = {"rol": "intrare", "receptor": "tablou", "retea": "tri", "Ib_A": ib, "cosfi": cos, "prot_tip": tip_r,
          "cablu": cablu(lung("L_C1_m", "L_m", 50.0, "C1 (rețea → ATS)")), "are_aval": True, "_validat": True}
    if in_r is not None:
        r1["In_fortat"] = in_r
    rr1 = calculeaza_ramura(r1, ctx_r, j, "QR/C1")
    rez["C1"] = dict(rr1["rezultat"], descriere="rețea → ATS (intrarea I), protejat de QR")
    if rr1["blocat"] or rr1["prot"] is None:
        In_r = in_r if in_r is not None else pr.alege_calibru(tip_r, ib)
        if In_r is None:
            return rez
        qr = pr.construieste(tip_r, In_r, ib, are_aval=True)
        qr["Icu_kA"], _ = pr.alege_icu(tip_r, ctx_r["Ik3_kA"])
    else:
        qr = rr1["prot"]
    rez["Q_retea"] = {"tip": qr["tip"], "In_A": qr["In_A"], "Ir_A": qr.get("Ir_A", qr["In_A"]),
                      "Ir_multiplu": qr.get("Ir_multiplu"), "Icu_kA": qr.get("Icu_kA"), "decl": qr.get("decl")}

    # C2: GE → ATS, protejat de Q_G (Ib = Ir_G: cablul transportă puterea GE)
    ik1_ge = norme.GE_IK_SUSTINUT_MULTIPLU * in_g if inp.get("excitatie_sustinuta") else in_g
    rez["Ik1_regim_GE_A"] = ik1_ge
    ctx_g = _context_ge(in_g, sn, xd, ik1_ge)
    # v1.2 R2 (N-C1, SR HD 60364-4-41 art. 411.4.5, SR HD 60364-5-55 art. 551.4): în regim GE Ik1 ≈ In_G nu atinge Ia
    # al Q_G → protecția la contact indirect se face cu un bloc diferențial 300 mA tip A, selectiv (S), asociat Q_G
    # (acționează pe tot circuitul alimentat din GE: C2, ATS, C3). Refuzat explicit (`DDR_GE: false`) → V85 BLOCANT.
    ddr_ge = None
    if inp.get("DDR_GE", True) is not False:
        ddr_ge = {"aparat": "bloc_diferential", "asociat": "Q_G", "tip_q": tip_g, "IdN_mA": 300, "tip": "A",
                  "selectiv": True, "In_A": In_G, "poli": "4P"}
        rez["Q_G"]["DDR"] = ddr_ge
        ctx_g["ddr_ramura"] = "bloc diferențial 300 mA S pe Q_G"
        j.pas(f"Regim GE: Ik1 ≈ {fmt_ro(ik1_ge, 0)} A — protecție la contact indirect prin bloc diferențial 300 mA tip A, "
              f"S, asociat Q_G {tip_g} {In_G} A")
    r2 = {"rol": "qg", "receptor": "tablou", "retea": "tri", "Ib_A": qg["Ir_A"], "cosfi": cos, "prot_tip": tip_g,
          "In_fortat": In_G, "Icu_fortat": qg["Icu_kA"], "cablu": cablu(lung("L_C2_m", None, 20.0, "C2 (GE → ATS)")),
          "are_aval": True, "_validat": True}
    rr2 = calculeaza_ramura(r2, ctx_g, j, "QG/C2")
    rez["C2"] = dict(rr2["rezultat"], descriere="GE → ATS (intrarea II), protejat de Q_G")
    if not rr2["blocat"]:
        for k in ("Isd_A", "Isd_multiplu", "tsd_s", "Ii_A", "Im_A"):
            if rr2["prot"].get(k) is not None:
                rez["Q_G"][k] = rr2["prot"][k]

    # ATS
    in_ats = max(qr["In_A"], In_G)
    in_ats = prima_din_serie(sorted(set(pr.SERII["MCCB"]) | set(pr.SERII["ACB"])), in_ats) or in_ats
    poli = inp.get("ATS_poli", 4)
    interb = inp.get("ATS_interblocaj", "mecanic + electric")
    rez["ATS"] = {"poli": poli, "In_A": in_ats, "interblocaj": interb, "categorie": "AC-33B",
                  "intrari": {"I": "rețea (QR, C1)", "II": "GE (Q_G, C2)"}, "iesire": "C3 → consumatori"}
    j.pas(f"ATS 4P In ≥ max(Q rețea {qr['In_A']} A; Q GE {In_G} A) → {in_ats} A; intrări distincte I (rețea) / II (GE)")
    if not isinstance(poli, (int, float)) or poli < 4:
        emite(j, "V87", BLOCANT, "schema", detaliu=f"cu {poli} poli în TN-S (sunt necesari 4 poli, comută și N)")
    if not interb or "mecanic" not in str(interb) or "electric" not in str(interb):
        emite(j, "V87", BLOCANT, "schema", detaliu="fără interblocaj mecanic + electric")
    rez["neutru_GE"] = "legat la priza de pământ locală (TN-S); ATS 4P comută și N"

    # C3: ATS → consumatori. v1.2 R2 (N-C1): se calculează SEPARAT în ambele regimuri — rețea (QR, sursa = capătul C1)
    # și GE (Q_G, sursa = capătul C2) — cu aceeași secțiune (cea mai mare dintre cele două dimensionări)
    if rr1["blocat"] or rr2["blocat"]:
        _nota_spl(rez, inp, "ge_ats")
        return rez
    L3 = lung("L_C3_m", "L_m", 50.0, "C3 (ATS → consumatori)")
    r3r = {"rol": "intrare", "receptor": "tablou", "retea": "tri", "Ib_A": ib, "cosfi": cos, "prot_tip": qr["tip"],
           "In_fortat": qr["In_A"], "Icu_fortat": qr.get("Icu_kA"), "cablu": cablu(L3), "are_aval": True,
           "_validat": True}
    r3r["Ip_min_extra"] = pr.ip(qr) + 1e-6 if gt(pr.ip(qr), ib) else None
    r3g = dict(r3r, prot_tip=tip_g, In_fortat=In_G, Icu_fortat=qg["Icu_kA"], cablu=cablu(L3),
               Ip_min_extra=qg["Ir_A"] - 1e-9)     # Q_G rămâne reglat la Ir_G (nu se re-reglează după sarcină)
    ctx3g = dict(rr2["ctx_aval"], regim_ge=True)
    if ddr_ge:
        ctx3g["ddr_ramura"] = "bloc diferențial 300 mA S pe Q_G"
    proba = [calculeaza_ramura(r3r, rr1["ctx_aval"], Jurnal(), "C3"), calculeaza_ramura(r3g, ctx3g, Jurnal(), "C3")]
    proba = [x["rezultat"] for x in proba if not x["blocat"]]
    if proba:
        dim = max(proba, key=lambda x: (x["Iz_corectat_A"], x["n_paralel"] * x["S_faza_mm2"]))
        fix = {"material": dim["material"], "izolatie": dim["izolatie"], "metoda": dim["metoda"],
               "S_fortat": dim["S_faza_mm2"], "n_fortat": dim["n_paralel"]}
        for rr_ in (r3r, r3g):
            rr_["cablu"] = dict(rr_["cablu"], **fix)
            rr_["cablu"].pop("material_implicit", None)
            rr_["_pe_liber"] = True
    rr3 = calculeaza_ramura(r3r, rr1["ctx_aval"], j, "C3")
    rr3g = calculeaza_ramura(r3g, ctx3g, j, "C3 (regim GE)")
    rez["C3"] = dict(rr3["rezultat"], descriere="ATS → consumatori; regim rețea: protejat de QR (sursa = capătul C1)")
    rez["C3"]["regim_GE"] = dict(rr3g["rezultat"], descriere="ATS → consumatori; regim GE: protejat de Q_G "
                                                             "(+ bloc diferențial), sursa = capătul C2")

    # deconectarea în regim GE (SPEC §C.6 pct. 4) — verificată în cel mai defavorabil punct (capătul C3, regim GE)
    prot_g = rr2["prot"] if not rr2["blocat"] else qg
    if prot_g.get("decl") == "EL" and prot_g.get("Isd_A") is None:
        pr.alege_isd(prot_g, ik1_ge)
    ia_g = pr.ia(prot_g, 5.0)
    ik1_min = rr3g["rezultat"].get("Ik1min_capat_A", ik1_ge) if not rr3g["blocat"] else ik1_ge
    if ia_g is not None and lt(ik1_min, ia_g):
        if ddr_ge:
            ok_ddr = ge(ik1_min, 2.0 * ddr_ge["IdN_mA"] / 1000.0)
            emite(j, "V85", INFO if ok_ddr else BLOCANT, "schema", "DDR" if ok_ddr else "",
                  x=round(ik1_min), y=ia_g, IdN=ddr_ge["IdN_mA"])
        else:
            emite(j, "V85", BLOCANT, "schema", "B", x=round(ik1_min), y=ia_g)
    _nota_spl(rez, inp, "ge_ats")
    return rez


# ============================================================================================================
# E.1 / G.3 Verificarea modelului (V80, V81)
# ============================================================================================================
def schema_verificare_model(inp, j):
    """SPEC §E.1 pct. 3–4: textele listei/desenului și notele cu valori se regenerează din parametri; orice valoare
    numerică diferită → V80 (aparat) / V81 (notă) BLOCANT."""
    rez = {}
    aparate = inp.get("aparate") or []
    if aparate:
        rez["text_lista_regenerat"] = {}
        rez["text_desen_regenerat"] = {}
        for a in aparate:
            lista, desen, v80 = verifica_aparat(a["ref"], a["tip"], a.get("parametri", {}), a.get("text_lista"),
                                                a.get("text_desen"))
            rez["text_lista_regenerat"][a["ref"]] = lista
            rez["text_desen_regenerat"][a["ref"]] = desen
            if v80:
                j.emite(v80["cod"], v80["nivel"], v80["obiect"], v80["mesaj"], v80["remediere"])
    note = inp.get("note") or []
    if note:
        par = inp.get("parametri") or {}
        model = {}
        if par.get("bloc"):
            bloc = par["bloc"]
            b = norme.BMPT.get(bloc, {})
            model = {"bloc": bloc, "Q": {"tip": b.get("Q_tip", "MCB"), "In_A": par.get("Q_In_A"),
                                         "Ir_A": par.get("Q_Ir_A")},
                     "TC": par.get("TC_primar_A"), "Pa_kW": par.get("Pa_kW")}
        regenerate = note_generate(model) if model else []
        for idx, text in enumerate(note, 1):
            k = idx
            if text.strip()[:1].isdigit():
                k = int(text.strip().split(".")[0])
            if idx <= len(regenerate):
                nou = f"{k}. {regenerate[idx - 1]}"
                if len(note) == 1:
                    rez["nota_regenerata"] = nou
                else:
                    rez.setdefault("note_regenerate", []).append(nou)
                v81 = verifica_nota(k, text, nou)
                if v81:
                    j.emite(v81["cod"], v81["nivel"], v81["obiect"], v81["mesaj"], v81["remediere"])
    return rez


# ============================================================================================================
# G.2 Nota de ipoteze
# ============================================================================================================
def _ipoteze(j, tip_schema):
    """SPEC §G.2: nota de ipoteze generată din valorile efectiv folosite; ipotezele implicite au sufixul „(presupus)”."""
    f = j.ipoteze_folosite
    linii = []

    def suf(impl):
        """Sufixul „(presupus)” pentru ipotezele implicite (SPEC §G.2)."""
        return " (presupus)" if impl else ""

    if "cosfi" in f and tip_schema == "locuinta":
        # v1.7 (§C.8, N13): cosφ grupat pe valoare, cu receptoarele: „0,9 (Iluminat, Prize) (presupus)”
        grup = {}
        for (v, et), i in f["cosfi"]:
            lst = grup.setdefault((v, bool(i)), [])
            if et not in lst:
                lst.append(et)
        linii.append("cosφ = " + "; ".join(f"{fmt_ro(v)} ({', '.join(e)}){' (presupus)' if i else ' (declarat)'}"
                                           for (v, i), e in grup.items()))
    elif "cosfi" in f:
        linii.append("cosφ = " + "; ".join(f"{fmt_ro(v[0])} ({v[1]}){suf(i)}" for v, i in f["cosfi"]))
    if "ks" in f:
        ref = (" (regula locuinței §C.8 după numărul receptoarelor — DECIZIE proiectant)" if tip_schema == "locuinta"
               else " (IEC 61439-2 tab. 101)")
        linii.append("ks = " + "; ".join(f"{fmt_ro(v)}{ref if i else ' (declarat)'}{suf(i)}" for v, i in f["ks"]))
    if "pozare" in f:
        for (met, th, rho, ncirc), impl in f["pozare"][:6]:
            txt = f"pozare {met} ({norme.METODE_POZARE.get(met, met)}), θ = {fmt_ro(th)} °C"
            if rho is not None:
                txt += f", ρ sol = {fmt_ro(rho)} K·m/W"
            txt += (f", grupare {ncirc} circuite" if ncirc > 1 else ", fără grupare") + suf(impl)
            linii.append(txt)
        if len(f["pozare"]) > 6:
            linii.append(f"… și încă {len(f['pozare']) - 6} configurații de pozare (vezi tabelul de calcul)")
    if "pozare_F" in f:
        # v1.2 R3 (N3-C1): trecerea pe cabluri monopolare în aer se scrie explicit pe planșă
        ob = ", ".join(v for v, _ in f["pozare_F"])
        impl = any(i for _, i in f["pozare_F"])
        linii.append(f"pozare pe pat de cabluri în aer, monopolare în treflă (metoda F, sisteme distanțate ≥ 2·De) "
                     f"pentru {ob}{suf(impl)}")
    def sursa_od(impl):
        """v1.7 (N11): o valoare implicită / presupusă nu se atribuie ATR-ului; „(declarat)” doar pentru datele introduse."""
        if isinstance(impl, str):
            return f"presupus ({impl}, [NEVERIFICAT]) — se confirmă cu OD / ATR"
        return "(valoare implicită, presupusă — se confirmă cu OD / ATR)" if impl else "(declarat)"

    if "ik3_od" in f:
        v, impl = f["ik3_od"][0]
        linii.append(f"Ik3max la punctul de delimitare = {fmt_ro(v)} kA {sursa_od(impl)}")
    if "zb_od" in f:
        v, impl = f["zb_od"][0]
        linii.append(f"impedanța buclei OD = {fmt_ro(v, 3)} Ω {sursa_od(impl)}")
    if "skq" in f:
        v, impl = f["skq"][0]
        linii.append(f"S\"kQ = {fmt_ro(v)} MVA{suf(impl)}")
    if "trafo" in f:
        (uk, pk), impl = f["trafo"][0]
        linii.append(f"trafo uk = {fmt_ro(uk)} %, Pk = {fmt_ro(pk)} W{suf(impl)}")
    linii.append("c_max = 1,10, c_min = 0,95")
    orig = {v for v, _ in f.get("origine", [])}
    if "pt_propriu" in orig:
        linii.append("limite ΔU: 6/8 % de la bornele JT ale PT")
    if "retea_publica" in orig or not orig:
        linii.append("limite ΔU: 3/5 % de la punctul de delimitare")
    return linii


# ============================================================================================================
# Punctul de intrare
# ============================================================================================================
SCHEME = {"bransament": schema_bransament, "tablou": schema_tablou, "cascada": schema_tablou, "cef": schema_cef,
          "pt": schema_pt, "prosumator": schema_prosumator, "ge_ats": schema_ge,
          "verificare_model": schema_verificare_model, "locuinta": None}


def schema_locuinta(inp, j):
    """SPEC §C.8 (v1.4): tabloul unei locuințe — vezi engine/calc/locuinta.py."""
    from .locuinta import calculeaza_locuinta
    return calculeaza_locuinta(inp, j)


SCHEME["locuinta"] = schema_locuinta


def _e_tt(inp):
    """True dacă intrarea declară schema TT (înainte de normalizare)."""
    return str(inp.get("schema_pamant") or "").strip().upper() == "TT"


def calculeaza(intrare):
    """Motorul de dimensionare și validatorul (SPEC §B–§D, §G.2): calculează schema descrisă de `intrare` (forma câmpului
    „intrare” din cazuri_golden.json) și întoarce rezultatul, verificările, valorile presupuse, pașii și ipotezele.
    v1.3 (§C.7): cu cheia `priza` se calculează și priza de pământ (rez["priza"], V37); în TT fără RA_ohm, RA = Rp
    calculat (declarat)."""
    inp = copy.deepcopy(intrare)
    priza = inp.pop("priza", None) if isinstance(inp, dict) else None
    tip = inp.get("tip_schema") if isinstance(inp, dict) else None
    if priza is None or tip not in SCHEME or tip == "verificare_model":
        j, rez = _ruleaza(inp)
        return _final(j, rez, tip)
    par, erori, pres = pamant.normalizeaza(priza)
    ra_din_priza = None
    c0 = c = n_nec = None
    if par is not None and _e_tt(inp) and inp.get("RA_ohm") is None:
        # TT: RA = Rp calculat cu n-ul dat; dacă depășește limita RA·IΔn ≤ 50 V a schemei rezultate, se recalculează
        # schema cu Rp al prizei dimensionate automat (n_necesar)
        ra_din_priza = pamant.calcul(par, par["n"])["Rp"]
        j, rez = _ruleaza(dict(inp, RA_ohm=ra_din_priza))
        lim, lim_motiv, ridicata = pamant.limita(tip, inp, rez, par)
        c0, c, n_nec = pamant.dimensioneaza(par, lim)
        if n_nec is not None and n_nec != par["n"]:
            ra_din_priza = c["Rp"]
            j, rez = _ruleaza(dict(inp, RA_ohm=ra_din_priza))
            lim, lim_motiv, ridicata = pamant.limita(tip, inp, rez, par)
            c0, c, n_nec = pamant.dimensioneaza(par, lim)
            # n_necesar rămâne cel găsit (schema refăcută cu RA mai mic nu poate cere un IΔn mai mic)
        j.presupune(f"RA = Rp calculat = {fmt_ro(ra_din_priza, 2)} Ω (calculul prizei de pământ, {c['n']} "
                    f"{'electrod' if c['n'] == 1 else 'electrozi'}) "
                    f"— se confirmă prin măsurare")
    else:
        j, rez = _ruleaza(inp)
    for t in pres:
        j.presupune(t)
    if par is None:
        for cod, var, kw in erori:
            emite(j, cod, BLOCANT, pamant.OBIECT, var, **kw)
        return _final(j, rez, tip)
    if c is None:
        lim, lim_motiv, ridicata = pamant.limita(tip, inp, rez, par)
        c0, c, n_nec = pamant.dimensioneaza(par, lim)
    if not isinstance(rez, dict):
        rez = {}
    if ridicata:
        # v1.3 R5 (M5-2): limita normată nu poate fi ridicată de utilizator
        emite(j, "V12", BLOCANT, pamant.OBIECT, "limita", x=ridicata[0], lim=ridicata[1], motiv=ridicata[2])
    for t in pamant.presupuneri_adoptate(par, c0, c):
        j.presupune(t)
    rez["priza"] = pamant.rezultat(par, c0, c, n_nec, lim, lim_motiv, ra_din_priza is not None)
    for t in rez["priza"]["pasi"]:
        j.pas(t)
    p = rez["priza"]
    comun = {"Rp": p["Rp_ohm"], "lim": lim, "n": p["n_electrozi"], "L": par["L"], "Lp": (f" + platbandă {fmt_ro(p['L_platbanda_m'], 1)} m" if par["platbanda"] else ", fără platbandă"),
             "rho": par["rho"], "psi": par["psi"]}
    if not p["ok"]:
        emite(j, "V37", BLOCANT, pamant.OBIECT, "B", **comun)
    elif c0["n"] != c["n"]:
        emite(j, "V37", INFO, pamant.OBIECT, "INFO_marit", n0=c0["n"], Rp0=c0["Rp"], **comun)
    else:
        emite(j, "V37", INFO, pamant.OBIECT, "INFO", **comun)
    return _final(j, rez, tip)


def _final(j, rez, tip):
    """Nota de ipoteze (G.2), V11 și V90; forma rezultatului întors de `calculeaza`."""
    ipoteze = _ipoteze(j, tip) if tip != "verificare_model" else []
    if j.presupus:
        j.emite("V11", INFO, "schema", "Am presupus: " + "; ".join(j.presupus))
    if ipoteze:
        j.emite("V90", INFO, "schema", "Ipoteze de calcul: " + "; ".join(ipoteze))
    return {"rezultat": rez, "verificari": j.verificari, "info": j.info,
            "blocheaza_export": any(v["nivel"] == "BLOCANT" for v in j.verificari),
            "presupus": j.presupus, "pasi": j.pasi, "ipoteze": ipoteze}


def _ruleaza(inp):
    """Validarea și calculul schemei (fără nota de ipoteze); întoarce (jurnal, rezultat)."""
    j = Jurnal()
    tip = inp.get("tip_schema") if isinstance(inp, dict) else None
    f = SCHEME.get(tip) if isinstance(tip, str) else None
    if tip == "locuinta" and isinstance(inp, dict):
        # v1.7 (§C.8 pct. 8, m-c4): Zb / RA / Ik3 invalide → V07 cu `camp`, ignorate (nu opresc calculul)
        from .locuinta import prevalideaza
        prevalideaza(inp, j)
    if not isinstance(inp, dict):
        emite(j, "V07", BLOCANT, "schema", "param", camp="intrare", x=repr(inp)[:40], conditie="se așteaptă un obiect")
        rez = {}
    elif f is None:
        # v1.2: mesaj clar pentru tipul de schemă necunoscut (nu „lipsește puterea”)
        emite(j, "V07", BLOCANT, "schema", "tip", tip=repr(tip) if tip is not None else "nespecificat",
              acceptate=", ".join(k for k in SCHEME if k != "verificare_model"))
        rez = {}
    elif tip != "verificare_model" and not _valideaza_intrare(inp, j, tip):
        rez = {}
    else:
        try:
            rez = f(inp, j)
        except (KeyError, TypeError, ValueError, ZeroDivisionError, AttributeError, IndexError) as e:
            camp = f"câmpul {e} lipsește" if isinstance(e, KeyError) else f"{type(e).__name__}: {e}"
            emite(j, "V07", BLOCANT, "schema", "intern", detaliu=camp)
            rez = {}
    return j, rez
