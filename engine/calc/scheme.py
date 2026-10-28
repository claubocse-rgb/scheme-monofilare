"""scheme.py — regulile pe tip de schemă (SPEC §C.1–§C.6), verificarea modelului (V80/V81, SPEC §E.1) și
punctul de intrare `calculeaza(intrare)`.

    calculeaza(intrare) -> {"rezultat", "verificari", "info", "blocheaza_export", "presupus", "pasi", "ipoteze"}

`intrare` are exact forma câmpului "intrare" din tests/date/cazuri_golden.json.
"""
import copy
import math
import re
import unicodedata

from . import norme
from . import protectii as pr
from . import scurtcircuit as sc
from .comun import Jurnal, ge, gt, lt, eq, prima_din_serie, u_calcul, SQRT3
from .ramura import calculeaza_ramura, valideaza
from . import cabluri as cb
from . import ddr as ddr_mod
from . import pamant
from . import fise
from . import catalog_invertoare as cat_inv
from .texte import fmt_ro, NB, X, text_cablu, note_generate, verifica_aparat, verifica_nota, nota_bransament, nota_schema_pamant
from .verificari import emite, BLOCANT, AVERTISMENT, INFO

DT_QG = norme.DDR_DT_SELECTIVITATE_S         # Δt al blocului diferențial reglabil pe intrarea TT (v1.3 R5)
RCCB_IN_BRANSAMENT = [16, 25, 40, 63, 80, 100, 125, 160, 200, 250]   # SPEC §C.1 (peste 125 A: bloc diferențial, M11)
CAMPURI_CABLU_SCHEMA = ("material", "izolatie", "metoda", "theta", "rho_sol", "n_alte", "S_fortat", "n_fortat", "tip_cablu",
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
    if any(k in n for k in ("motor", "motoar", "pomp", "compresor", "compresoar", "ventila", "moar", "concasor", "malaxor", "strung", "frez",
                            "banda transport", "polizor", "ferastrau", "lift", "ascensor", "macara", "agitator", "extractor",
                            "hidrofor", "jockey")):
        return "motor"
    return "tablou" if nivel == 0 else "forta"


def _zb_din_intrare(zb, j):
    """M2 (v1.2): impedanța buclei OD din ATR — perechea (R, X), dict {R, X} sau modulul |Z| (număr). La modul,
    R/X = 2 (raportul valorii implicite 0,2683 + j0,1342 Ω, |Z| = 0,30 Ω) — declarat ca presupus."""
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
                f"implicită) → Zb = {fmt_ro(z * r0 / m0, 3)} + j{fmt_ro(z * x0 / m0, 3)} Ω")
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
            j.presupune(f"Zbuclă OD {fmt_ro(norme.OD_ZBUCLA_IMPLICIT_OHM[0], 3)} + j{fmt_ro(norme.OD_ZBUCLA_IMPLICIT_OHM[1], 3)} Ω "
                        f"(|Z| = {fmt_ro(norme.OD_ZBUCLA_MODUL_IMPLICIT_OHM, 2)} Ω, valoare implicită presupusă — se confirmă cu OD / ATR)")
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
    "cosfi": ("(0,1]", "V08"), "ks": ("(0,1]", "V10"), "randament": ("(0,1]", "V08"), "n_paralel": ("int>=1", "V07"),
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
    "racord_Icu_kA": (">0", "V07"), "P_aprobata_kW": (">0", "V07"), "P_evacuata_kW": (">=0", "V07"),
    # r5 (tablou / PT / GE): sursa tabloului, circuite multiple, cablul GE–ATS
    "Ik3_sursa_kA": (">0", "V07"), "Ik3_bara_kA": (">0", "V07"), "n_circuite": ("int>=1", "V07"), "L_GE_ATS_m": (">0", "V09"),
    # fișe tehnice (modul PV, invertor, BESS, SPD c.c.) — v1.8
    "Voc_V": (">0", "V07"), "Pmax_W": (">0", "V07"), "Vmpp_V": (">0", "V07"), "Impp_A": (">0", "V07"),
    "beta_Voc_pct_K": ("num", "V07"), "Umax_sistem_V": (">0", "V07"), "Umax_dc_V": (">0", "V07"),
    "MPPT_min_V": (">0", "V07"), "MPPT_max_V": (">0", "V07"), "Idc_max_A": (">0", "V07"), "Isc_max_A": (">0", "V07"),
    "nr_MPPT": ("int>=1", "V07"), "n_MPPT": ("int>=1", "V07"), "Ucpv_V": (">0", "V07"),
    # v1.9 (R5 fotovoltaic): limitarea injecției, puterea totală declarată, bateria, gPV declarat
    "limitare_injectie_kW": (">=0", "V07"), "limitare_PCC_kW": (">0", "V07"), "Pn_total_kW": (">0", "V07"), "U_nom_V": (">0", "V07"),
    "gpv_In_A": (">0", "V07"), "IdN_min_mA": (">0", "V07"), "baterie_kWh": (">0", "V07"),
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
                 "tablou": "tablou", "invertor": "invertor", "pcs": "pcs", "ups": "ups"},
    "origine": {"retea_publica": "retea_publica", "pt_propriu": "pt_propriu", "pt": "pt_propriu",
                # r5: sursa tabloului declarată explicit (nu se presupune „BMPT cu RCCB” în tăcere)
                "bmpt": "bmpt", "retea": "retea_publica", "tg_existent": "tg_existent", "tg": "tg_existent",
                "tgd": "tg_existent", "tgd_existent": "tg_existent", "tablou_existent": "tg_existent"},
    "trafo_izolatie": {"ulei": "ulei", "uscat": "uscat", "rasina": "uscat", "rasina_epoxidica": "uscat"},
    "sursa_retea": {"bmpt": "bmpt", "retea_publica": "bmpt", "pt": "pt", "pt_propriu": "pt", "tgd": "tgd",
                    "tg": "tgd", "tg_existent": "tgd", "tgd_existent": "tgd"},
    "masura_ceruta": {"semidirecta": "semidirecta", "directa": "directa"},
    "PE_loc": {"cablu": "cablu", "separat": "separat"},
    "rol": {"plecare": "plecare", "final": "final"},
    "racord": {"tg_existent": "tg_existent", "tg": "tg_existent", "bmpt": "bmpt", "pt": "pt", "pt_propriu": "pt"},
}
CHEI_ENUM_NULE = ("retea", "schema_pamant", "pornire", "receptor", "origine", "masura_ceruta", "PE_loc", "rol", "racord",
                  "trafo_izolatie", "sursa_retea",
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
        c0 = _fd(ct).lower() if isinstance(ct, str) else ""
        if c0.startswith("sig") or ("separator" in c0 and "sig" in c0):
            d["celula_trafo"] = "sigurante"
        elif c0.startswith("intr") or any(k in c0 for k in ("vid", "vacuum", "sf6", "disjunct", "breaker", "50/51")):
            # r9 (industrial #20): „întreruptor în vid / SF6 / disjunctor (+ 50/51)” = celulă trafo cu întreruptor
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
        if isinstance(t, str) and pr.normalizeaza_tip(t) != t.strip() and str(pr.normalizeaza_tip(t)).upper() in TIPURI_PROT:
            # r12 (proiecte reale): „MPR” / „separator fuzibil” / „NH” = gG, „MCB C” = MCB
            d[k] = t = pr.normalizeaza_tip(t)
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
        _normalizeaza_ddr_plecare(pl, j, ob)
        if isinstance(pl.get("DDR"), dict) and not _valideaza_ddr(pl["DDR"], j, ob, "DDR"):
            return False
        cab = pl.get("cablu")
        if cab is not None and (not isinstance(cab, dict) or not _valideaza_dict(cab, j, ob, sari=("L",))):
            return False
        if pl.get("copii") and not _valideaza_plecari(pl["copii"], j, ob.replace("P", "P", 1) + "."):
            return False
    return True


_VE_RE = re.compile(r"\b(ve|ev|evse|wallbox)\b|incarcare|charger|charging|statie de incarcare|stati[ea] ve")


def e_plecare_ve(pl):
    """r10 (industrial i45): plecare spre o stație de încărcare VE (după nume / receptor)."""
    if not isinstance(pl, dict) or pl.get("copii"):
        return False
    t = " ".join(str(pl.get(k) or "") for k in ("nume", "receptor", "tip"))
    return bool(_VE_RE.search(_fara_diacritice(t).lower().replace("-", " ").replace("_", " ")))


def _normalizeaza_ddr_plecare(pl, j, ob):
    """r10 (industrial i45): DDR declarat pe plecare cu cheia `ddr` (alias al `DDR`) — {tip: "B"} fără IΔn = 30 mA;
    `ddr: true` = 30 mA tip A. Plecare VE fără DDR declarat → DDR 30 mA tip B (SR HD 60364-7-722 art. 722.531.2),
    declarat în presupus. Nimic declarat nu se pierde."""
    d = pl.get("DDR", pl.get("ddr"))
    if d is True:
        d = {}
    if isinstance(d, dict):
        d = dict(d)
        if d.get("IdN_mA") is None:
            d["IdN_mA"] = d.pop("IdN", None) or 30
        if isinstance(d.get("tip"), str):
            d["tip"] = d["tip"].strip().upper().replace("TIP ", "").replace("TYPE ", "")
        pl["DDR"] = d
        pl.pop("ddr", None)
        return
    if d is None and e_plecare_ve(pl) and not pl.get("_siguranta"):
        pl["DDR"] = {"IdN_mA": 30, "tip": "B"}
        j.presupune(f"{ob}: stație de încărcare VE — DDR 30 mA tip B pe plecare (SR HD 60364-7-722); tip A admis numai "
                    f"cu RDC-DD 6 mA c.c. în stație (declarați ddr tip „A”)")


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


def _ddr_amonte(inp, retea="tri", bmpm_sel=None):
    """v1.3 (§B.18.1): DDR-ul din amontele schemei (branșamentul): `IdN_amonte_mA` declarat (tip S după
    `DDR_amonte_selectiv`, implicit S) sau RCCB 300 mA din BMPT (ST 4-JT; S la tablourile din M11, instantaneu la
    locuință — Î1 28.10.2026) / RCBO 300 mA din BMPM (ST 3-JT §4.2.4 m: instantaneu [VERIFICAT])."""
    idn = inp.get("IdN_amonte_mA")
    if idn is not None:
        return ddr_mod.descriere(idn, inp.get("DDR_amonte_selectiv", True), "DDR amonte (declarat)")
    if retea == "mono":
        return ddr_mod.descriere(norme.BMPM["idn_ma"], inp.get("DDR_amonte_selectiv", norme.BMPM_RCBO_SELECTIV
                                                                if bmpm_sel is None else bmpm_sel), "RCBO BMPM")
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
    for k in ("cablu", "cablu_inv", "cablu_pcs", "cablu_C0", "string", "bess", "modul", "invertor", "baterie", "spd_cc", "gpv"):
        d = inp.get(k)
        if d is not None:
            if not isinstance(d, dict) or not _valideaza_dict(d, j, "schema" if k != "string" else "string"):
                if not isinstance(d, dict):
                    emite(j, "V07", BLOCANT, "schema", "param", camp=k, x=repr(d), conditie="se așteaptă un obiect")
                return False
            if k == "string" and d.get("modul") is not None:
                if not isinstance(d["modul"], dict) or not _valideaza_dict(d["modul"], j, "string"):
                    if not isinstance(d["modul"], dict):
                        emite(j, "V07", BLOCANT, "string", "param", camp="string.modul", x=repr(d["modul"]),
                              conditie="se așteaptă un obiect")
                    return False
    bc = (inp.get("bess") or {}).get("cuplaj") if isinstance(inp.get("bess"), dict) else None
    if bc is not None and bc not in ("cc", "ca"):
        emite(j, "V12", BLOCANT, "schema", "camp", camp="bess.cuplaj", valoare=bc)
        return False
    if inp.get("invertoare") is not None and not isinstance(inp.get("invertoare"), list):
        emite(j, "V07", BLOCANT, "schema", "param", camp="invertoare", x=repr(inp["invertoare"]), conditie="se așteaptă o listă")
        return False
    for g in inp.get("invertoare") or []:
        if isinstance(g, dict) and isinstance(g.get("ddr"), dict) and not _valideaza_ddr(g["ddr"], j, "schema", "invertoare[].ddr"):
            return False
        if not isinstance(g, dict) or not _valideaza_dict(g, j, "schema"):
            if not isinstance(g, dict):
                emite(j, "V07", BLOCANT, "schema", "param", camp="invertoare", x=repr(g), conditie="se așteaptă un obiect")
            return False
        if g.get("Pn_kW") is None:
            # r6 (fotovoltaic P1-9): Pn din codul unui model cunoscut (Fronius Tauro ECO, SMA STP 110-60, Sungrow SH…T …)
            mc = cat_inv.cauta(g.get("producator"), g.get("model"))
            if mc is None:
                emite(j, "V07", BLOCANT, "schema", "lipsa")
                return False
            g["Pn_kW"] = mc["Pn_kW"]
            if mc.get("hibrid") and g.get("hibrid") is None:
                g["hibrid"] = True
            j.presupune(f"Pn = {fmt_ro(mc['Pn_kW'])} kW din codul modelului {mc['producator']} {mc['model']}"
                        + (" (invertor hibrid, port de baterie c.c.)" if mc.get("hibrid") else "") + " — confirmați cu fișa tehnică")
        for kk in ("string", "modul"):          # v1.8: stringul / modulul propriu al grupului
            d = g.get(kk)
            if d is not None and (not isinstance(d, dict) or not _valideaza_dict(d, j, "string")):
                if not isinstance(d, dict):
                    emite(j, "V07", BLOCANT, "schema", "param", camp=f"invertoare[].{kk}", x=repr(d), conditie="se așteaptă un obiect")
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
    if tip == "cef" and _bool(inp.get("pt_od")) and inp.get("schema_pamant") is None:
        spl = "TN-C-S"            # r11: PT al OD — rețea publică (TN-C-S), nu „TN-S din PT propriu”
    rez["schema_pamant"] = spl
    if tip == "cef" and _bool(inp.get("pt_od")) and spl != "TT":
        rez["nota_schema_pamant"] = (f"Schemă de legare la pământ: {spl}, racord pe bara JT a PT-ului OD (rețea "
                                     f"publică); TN-S în aval de separarea PEN în TGD-CF. Rp ≤ 4{NB}Ω.")
        return
    if tip == "tablou" and str(inp.get("separare_PEN") or "").upper() in ("TG", "TABLOU") and spl != "TT":
        rez["nota_schema_pamant"] = (f"Schemă de legare la pământ: TN-C-S — PEN pe cablul C1, separarea PEN în N + PE "
                                     f"în TG, TN-S în aval. Rp ≤ 4{NB}Ω.")
        return
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


def cablu_impus_fara_L(cab, j, obiect, camp):
    """r10 (fotovoltaic #51, industrial i18): cablu IMPUS (secțiune declarată) fără lungime → V07 BLOCANT cu întrebare
    explicită (lungimea decide ΔU, deconectarea și Iz la grupare) — nu se ignoră, nu se presupune tăcut."""
    if not isinstance(cab, dict) or cab.get("S_fortat") is None:
        return False
    emite(j, "V07", BLOCANT, obiect, "param", camp=camp, x="—",
          conditie=f"cablu impus {fmt_ro(cab['S_fortat'])} mm² fără lungime — secțiunea nu se poate verifica (Iz, ΔU, "
                   f"deconectare)")
    j.verificari[-1]["remediere"] = f"lungimea cablului impus de {fmt_ro(cab['S_fortat'])} mm² (m) — câmpul {camp}"
    j.verificari[-1]["intrebare"] = True
    j.verificari[-1]["camp"] = camp
    return True


def _cablu_plecare(pl, nivel, j, obiect, implicit_metoda=None, final=False):
    """SPEC §B.0 / §C.2 pct. 9 / §B.1.1: plecări Al PVC D1, L 50 m; sub-plecări și circuite finale (tablou cu
    `circuite_finale`) Cu PVC metoda C, L 25 m (declarate)."""
    cab = dict(pl.get("cablu") or {})
    if pl.get("_siguranta"):
        # r8 (P0): circuit de siguranță — cablu Cu rezistent la foc (NHXH FE180/E90), pe traseu propriu (metoda C)
        cab.setdefault("material", "Cu")
        cab.setdefault("izolatie", "XLPE")
        cb.metoda_implicita(cab, "C")
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
              "pornire", "randament", "S_max_dU", "In_minim"):
        if pl.get(k) is not None:
            r[k] = pl[k]
    # C4 (v1.2): DDR refuzat explicit pe un circuit de prize → V29 BLOCANT în ramură
    if pl.get("_siguranta") or pl.get("_cale_siguranta"):
        # r8 (P0): consumator de siguranță (sau tablou care îl alimentează) — niciodată DDR pe ramura lui
        r["ddr"] = False
    elif pl.get("DDR") is False or pl.get("ddr") is False:
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
    return None if rr["blocat"] else max(rr["Ip"], float((rr.get("prot") or {}).get("In_A") or 0.0))


CONTACTOR_AC3_A = (9, 12, 18, 25, 32, 40, 50, 65, 80, 95, 115, 150, 185, 225, 265, 330, 400, 500, 630, 780)
VFD_KW = (0.75, 1.1, 1.5, 2.2, 3, 4, 5.5, 7.5, 11, 15, 18.5, 22, 30, 37, 45, 55, 75, 90, 110, 132, 160, 200, 250, 315,
          355, 400, 450, 500)


def aparataj_motor(pl, rz, j, obiect):
    """r5 (P1-13): aparatajul de comandă al unei plecări de motor, după `pornire`:
    directă → contactor KM (AC-3, In ≥ Ib) + releu termic F (reglaj = Ib); stea-triunghi → KM1 linie + KM2 Δ
    (≥ Ib/√3) + KM3 Y (≥ Ib/3) + releu termic pe ramura Δ (Ib/√3) + releu de timp; convertizor (VFD) → convertizor
    de frecvență Pn ≥ P motor, In ≥ Ib (protecția termică a motorului în VFD); soft-starter → soft-starter + KM bypass."""
    ib = float(rz["Ib_A"])
    porn = pl.get("pornire") or "directa"
    if pl.get("pornire") is None:
        j.presupune("motor cu pornire directă (contactor + releu termic) — pornirea nedeclarată", obiect)
    ac3 = lambda i: prima_din_serie(CONTACTOR_AC3_A, i) or round(i)
    p_kw = pl.get("P_kW")
    if p_kw is None:
        u = norme.U_0_V if rz.get("retea") == "mono" else SQRT3 * norme.U_N_V
        p_kw = u * ib * 0.85 * 0.9 / 1000.0           # P mecanic estimat (cosφ 0,85, η 0,9)
    out = {"pornire": porn, "P_kW": float(p_kw), "Ib_A": ib, "faze": 1 if rz.get("retea") == "mono" else 3}
    if porn == "stea_triunghi" and out["faze"] == 1:
        emite(j, "V12", BLOCANT, obiect, "camp", camp="pornire", valoare="stea-triunghi la motor monofazat")
        j.verificari[-1]["remediere"] = "pornire directă / soft-starter, sau motor trifazat"
    if porn == "stea_triunghi":
        idelta = ib / SQRT3
        out.update({"KM1_A": ac3(ib), "KM2_A": ac3(idelta), "KM3_A": ac3(ib / 3.0), "releu_termic_Ir_A": idelta,
                    "Ip_pornire_A": rz.get("Ip_pornire_A")})
        j.pas(f"{obiect}: pornire stea-triunghi — KM1 {out['KM1_A']} A, KM2 (Δ) {out['KM2_A']} A, KM3 (Y) {out['KM3_A']} A "
              f"(AC-3), releu termic reglat la Ib/√3 = {fmt_ro(idelta)} A")
    elif porn == "vfd":
        pv = prima_din_serie(VFD_KW, float(p_kw)) or float(p_kw)
        out.update({"VFD_kW": pv, "VFD_In_A": ib})
        j.pas(f"{obiect}: convertizor de frecvență {fmt_ro(pv)} kW (≥ P motor {fmt_ro(p_kw)} kW), In ≥ {fmt_ro(ib)} A; "
              f"curent de pornire ≈ In (fără șoc)")
    elif porn == "soft":
        out.update({"soft_In_A": ib, "KM_A": ac3(ib)})
    else:
        out.update({"KM_A": ac3(ib), "releu_termic_Ir_A": ib, "Ip_pornire_A": rz.get("Ip_pornire_A")})
        j.pas(f"{obiect}: pornire directă — contactor KM {out['KM_A']} A (AC-3), releu termic reglat la Ib = {fmt_ro(ib)} A")
    return out


def _plecari(plecari, ctx_bara, amonte, j, prefix="", final=False, ctx_sig=None, amonte_sig=None):
    """SPEC §C.2 pct. 8–9 / §C.5 pct. 8: dimensionarea plecărilor cu contextul barei, selectivitatea față de aparatul de
    intrare și cascadele (recursiv, fără limită de adâncime). Returnează lista plată (parcurgere în adâncime).
    r8: plecările de siguranță de nivel 0 pot avea alt context / amonte (`ctx_sig`, `amonte_sig`: racord înaintea
    întreruptorului general Q1)."""
    lista = []

    def proceseaza(pl, nivel, ctx, prot_amonte, obiect):
        """O plecare (și recursiv sub-plecările ei) cu contextul barei și aparatul amonte (SPEC §C.2 pct. 8–9)."""
        sig = bool(pl.get("_siguranta"))
        if sig or pl.get("_cale_siguranta"):
            # r8 (P0): pe calea unui consumator de siguranță nu există DDR — nici pe ramură, nici în amonte; un DDR real
            # în amonte (declarat / al tabloului părinte) → BLOCANT; deconectarea nu se bazează pe un DDR din amonte
            if ctx.get("ddr_ramura") or (ctx.get("ddr_amonte") and not ctx.get("ddr_amonte_presupus")
                                         and not ctx.get("_ddr_amonte_ignorat")):
                emite(j, "V97", BLOCANT, obiect, "ddr", nume=pl.get("nume", ""),
                      ddr=ctx.get("ddr_ramura") or "DDR declarat în amonte")
            ctx = dict(ctx, ddr_amonte=False, ddr_amonte_presupus=False, ddr_ramura=None, ddr_sus=None)
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
        if pl.get("_echipata"):
            intrare["rezerva_echipata"] = True
        if pl.get("_compensare"):
            intrare.update({"compensare": True, "Q_kvar": pl["_Q_kvar"], "In_cap_A": pl["_In_cap_A"]})
        if not rr["blocat"] and r.get("receptor") == "motor" and not copii:
            intrare["aparataj_motor"] = aparataj_motor(pl, intrare, j, obiect)
        if pl.get("_ups"):
            intrare["ups"] = _ups_iesire(pl["_ups"], rr, j, obiect)
        if pl.get("_ups_bypass"):
            intrare["ups_bypass"] = True
        if sig:
            intrare.update({"siguranta": True, "rezistent_foc": True})
            if pl.get("_rezerva"):
                intrare["rezerva"] = True
            if pl.get("_inainte_Q1"):
                intrare["inainte_Q1"] = True
            if intrare.get("aparataj_motor"):
                # P118-3: la consumatorii de siguranță releul termic doar semnalizează (nu oprește pompa / ventilatorul)
                intrare["aparataj_motor"]["releu_termic_doar_semnalizare"] = True
            if intrare.get("DDR"):
                emite(j, "V97", BLOCANT, obiect, "ddr", nume=pl.get("nume", ""), ddr="DDR pe ramură")
            emite(j, "V97", INFO, obiect, "plecare", nume=pl.get("nume", ""))
        lista.append(intrare)
        if copii and not rr["blocat"]:
            for k, cpl in enumerate(copii, 1):
                proceseaza(cpl, nivel + 1, rr["ctx_aval"], rr["prot"], f"{obiect}.{k}·{cpl.get('nume', '')}")

    for i, pl in enumerate(plecari, 1):
        if pl.get("_inainte_Q1") and ctx_sig is not None:
            proceseaza(pl, 0, ctx_sig, amonte_sig, f"{prefix}P{i}·{pl.get('nume', '')}")
        else:
            proceseaza(pl, 0, ctx_bara, amonte, f"{prefix}P{i}·{pl.get('nume', '')}")
    return lista


def _ups_iesire(meta, rr, j, obiect):
    """r11: Q ieșire UPS — MCB (≤ 63 A) / MCCB, In ≥ In ieșire, Icu ≥ Ik3 la bornele UPS (prin bypass = Ik rețea)."""
    meta = dict(meta)
    ik = (rr.get("ctx_aval") or {}).get("Ik3_kA") or 25.0
    in_o = meta["In_iesire_A"]
    tip = "MCB" if in_o <= 63 else ("MCCB" if in_o <= 1600 else "ACB")
    In = pr.alege_calibru(tip, in_o)
    if In is None:
        emite(j, "V06", BLOCANT, obiect + "·Q ieșire UPS", Ib=in_o, tip=tip)
        return meta
    q = pr.construieste(tip, In, in_o, are_aval=True)
    q["Icu_kA"], ok = pr.alege_icu(tip, ik)
    meta["Q_iesire"] = {k: q.get(k) for k in ("tip", "In_A", "Ir_A", "Ir_multiplu", "Icu_kA", "curba", "decl")
                        if q.get(k) is not None}
    if tip == "MCB":
        meta["Q_iesire"].setdefault("curba", "C")
    if not ok:
        emite(j, "V33", BLOCANT, obiect + "·Q ieșire UPS", icu=q["Icu_kA"], ik3=ik)
    j.pas(f"{obiect}: Q ieșire UPS {tip} {In} A (In ieșire {fmt_ro(in_o)} A), Icu {fmt_ro(q['Icu_kA'])} kA ≥ Ik3 "
          f"{fmt_ro(ik)} kA (prin bypass)")
    return meta


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
    if tensiune_jt_nesuportata(inp, j):
        return rez
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
    q_f0 = inp.get("Q_In_A")
    ib_atr = False
    if (q_f0 is not None and inp.get("P_kW") is not None and cos_dat is None and gt(ib, q_f0)
            and inp.get("S_kVA") is None and inp.get("Ib_A") is None and inp.get("In_A") is None):
        # r6 (N11): perechea standard ATR „BMPM 32 A + 7 kW” — puterea aprobată e definită ca Pa = U·In (cosφ 1);
        # cu cosφ 0,9 implicit Ib = 33,8 A > 32 A. Dacă Ib (cosφ 1) ≤ In Q și Ib (0,9) ≤ 1,13·In → AVERTISMENT, Ib ATR
        i_atr = float(inp["P_kW"]) * 1000.0 / U
        if not gt(i_atr, q_f0) and not gt(ib, norme.LOCUINTA_I_NEDECLANSARE * q_f0):
            emite(j, "V04", AVERTISMENT, "Q", "atr", P=float(inp["P_kW"]), Ip=q_f0, Iatr=i_atr, cos=cos, Ib=ib,
                  lim=norme.LOCUINTA_I_NEDECLANSARE * q_f0)
            j.presupune(f"Ib din puterea aprobată în convenția ATR (Pa = U·In, cosφ 1) = {fmt_ro(i_atr)} A — Q {q_f0} A "
                        f"declarat; la cosφ {fmt_ro(cos)} Ib ar fi {fmt_ro(ib)} A")
            ib = i_atr
            ib_atr = True
    rez["Ib_A"] = ib
    if inp.get("P_kW") is not None:
        rez["Pa_kW"] = float(inp["P_kW"])
    schema_p = inp.get("schema_pamant", "TN-C-S")
    ctx = _context_od(inp, j, ddr_amonte=False)

    if retea == "mono":
        if gt(ib, norme.BMPM["I_max_A"]):
            emite(j, "V53", BLOCANT, "schema", Ib=ib)
            # r11 (locuințe #3 mono): fără invertor în schemă, remedierea nu vorbește de invertor
            j.verificari[-1]["remediere"] = ("branșament trifazat (BMPT, ATR pentru trecerea pe trifazat) sau reducerea "
                                             "sarcinii simultane sub 40 A (ks / DLM)")
            j.verificari[-1]["intrebare"] = True
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
        # Î1 (proiectant 28.10.2026): RCBO 300 mA din BMPM — tip AC, instantaneu (ST 3-JT §4.2.4 l–m DEER); neselectiv
        # cu DDR-urile de 30 mA din TE (V43, cu remedierea „declarați blocul real”). Blocul cu RCBO A / S se declară.
        sel_q = inp.get("DDR_amonte_selectiv", norme.LOCUINTA_DDR_BRANSAMENT_IMPLICIT["selectiv"])
        tip_q = inp.get("DDR_bransament_tip") or norme.LOCUINTA_DDR_BRANSAMENT_IMPLICIT["tip"]
        if inp.get("DDR_amonte_selectiv") is None and not inp.get("_cosfi_eticheta"):
            j.presupune(f"RCBO 300 mA din BMPM: tip {tip_q}, instantaneu (ST 3-JT DEER) — declarați blocul real "
                        f"(DDR_amonte_selectiv / DDR_bransament_tip) dacă RCBO-ul e de tip S / A")
        rez.update({"bloc": f"BMPM-{In_q}",
                    "Q": {"tip": "RCBO 1P+N", "curba": "C", "In_A": In_q, "IdN_mA": norme.BMPM["idn_ma"],
                          "Icn_kA": int(norme.BMPM["Q_icn_min_ka"]), "selectiv": bool(sel_q), "tip_ddr": tip_q},
                    "SF": {"tip": "separator monopolar cu fuzibil", "In_A": 40},
                    "contor": f"monofazat direct 230{NB}V (furnizat și montat de OD)"})
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
                        "Im_A": norme.im_tm(In_q)}
        rez["SF"] = {"In_A": b["SF_fuzibil_A"], "soclu_A": b["SF_soclu_A"], "gabarit": b["SF_gabarit"]}
        if In_q > b["SF_fuzibil_A"]:
            emite(j, "V52", BLOCANT, "schema", q=In_q, sf=b["SF_fuzibil_A"])
        # M11 (v1.2): DDR general 300 mA în amontele DDR-urilor de 30 mA din instalație → selectiv (S); la LOCUINȚĂ
        # (Î1, proiectant 28.10.2026) implicit instantaneu, ca în ST 4-JT — tipul S / A se declară
        sel_bmpt = inp.get("DDR_amonte_selectiv", norme.LOCUINTA_DDR_BRANSAMENT_IMPLICIT["selectiv"]
                           if inp.get("_cosfi_eticheta") else True)
        rez["RCCB"] = {"poli": norme.BMPT_RCCB["poli"], "In_A": prima_din_serie(RCCB_IN_BRANSAMENT, In_q),
                       "IdN_mA": norme.BMPT_RCCB["idn_ma"], "tip": inp.get("DDR_bransament_tip") or norme.BMPT_RCCB["tip"],
                       "selectiv": bool(sel_bmpt), "aparat": "RCCB"}
        if gt(In_q, norme.RCCB_IN_A[-1]):
            # M11 (v1.2, §B.4): peste 125 A nu există RCCB modular → bloc diferențial asociat MCCB-ului Q, In = In Q
            rez["RCCB"].update({"aparat": "bloc_diferential", "asociat": "Q", "In_A": In_q})
            j.pas(f"DDR general: In Q {In_q} A > 125 A → bloc diferențial asociat MCCB Q, IΔn 300 mA, tip "
                  f"{rez['RCCB']['tip']}{', S' if rez['RCCB']['selectiv'] else ''}")
        if b["masura"] == "semidirecta":
            tc = norme.BMPT_TC
            # r7 (#38): TC primar ≥ 1,2·Ib (Ib în zona de precizie, cu rezervă) și ≥ In_Q/1,2 (domeniu extins 120 %);
            # dacă seria blocului nu are, ≥ Ib (TC cu domeniu extins 120 % la In_Q)
            p = (prima_din_serie(tc["primar_A"], max(norme.TC_REZERVA_IB * ib, In_q / tc["factor_extindere"]))
                 or prima_din_serie(tc["primar_A"], max(ib, In_q / tc["factor_extindere"])))
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
            rez["contor"] = f"semidirect 3 {X} 230/400{NB}V, prin TC (furnizat și montat de OD)"
        else:
            rez["contor"] = f"direct 3 {X} 230/400{NB}V (furnizat și montat de OD)"
            if gt(ib, 100):
                emite(j, "V56", BLOCANT, "schema", Ib=ib)
            elif inp.get("_cosfi_eticheta") and (gt(ib, norme.LOCUINTA_IB_SEMIDIRECT_A)
                                                  or ge(In_q, norme.LOCUINTA_IB_SEMIDIRECT_A)):
                # r7 (#38/#65): casă cu Ib > ~80 A — măsura directă (Imax contor ≈ 100 A) e la limită; OD cere de regulă măsură
                # semidirectă (BMPTi cu TC, primar ≥ 1,2·Ib) — semnalat, se confirmă din ATR
                if gt(ib, norme.LOCUINTA_IB_SEMIDIRECT_A):
                    j.emite("V56", AVERTISMENT, "schema",
                            f"locuință trifazată cu Ib = {fmt_ro(ib)} A > {norme.LOCUINTA_IB_SEMIDIRECT_A} A: contorul direct "
                            f"(Imax ≈ 100 A) lucrează la limită — OD poate cere măsură semidirectă (BMPTi-250 cu TC primar ≥ 1,2·Ib "
                            f"= {fmt_ro(1.2 * ib, 0)} A)",
                            "confirmați tipul măsurii din ATR (masura_ceruta: „semidirecta”) sau reduceți puterea aprobată")
                else:
                    # r9 (locuințe #61): mesajul vechi „Ib = 22,79 A > 80 A” era fals — aici Ib e mic, Q e cel mare
                    j.emite("V56", AVERTISMENT, "schema",
                            f"Q branșament {fmt_ro(In_q, 0)} A ≥ {norme.LOCUINTA_IB_SEMIDIRECT_A} A pentru Ib = {fmt_ro(ib)} A "
                            f"(puterea aprobată): Q supradimensionat față de ATR — OD montează Q după puterea aprobată "
                            f"(≈ {fmt_ro(pr.alege_calibru('MCB', ib) or ib, 0)} A), iar la ≥ 80 A cere de regulă măsură "
                            f"semidirectă",
                            "Q branșament conform puterii aprobate din ATR, sau mărirea puterii aprobate (ATR nou)")
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
    if inp.get("P_kW") is not None and not ib_atr:
        r["P_kW"] = inp["P_kW"]
    elif inp.get("S_kVA") is not None:
        r["S_kVA"] = inp["S_kVA"]
    else:
        r["Ib_A"] = ib
        if ib_atr:
            r["cosfi"] = cos            # ΔU cu cosφ-ul de calcul, Ib din convenția ATR
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
def expandeaza_plecari(plecari):
    """r5: `n_circuite` = N pe o plecare → N plecări identice numerotate („Prize 1…4”), recursiv în cascade.
    Funcție pură (o folosește și constructorul ca să împerecheze intrarea cu rezultatul)."""
    out = []
    for pl in plecari or []:
        if not isinstance(pl, dict):
            out.append(pl)
            continue
        pl = dict(pl)
        if pl.get("copii"):
            pl["copii"] = expandeaza_plecari(pl["copii"])
        n = pl.pop("n_circuite", None)
        n_alias = pl.pop("n", None)          # r11 (industrial j46): `n` pe plecare = n_circuite (6 stații VE identice)
        if n is None:
            n = n_alias
        if isinstance(n, float) and n.is_integer():
            n = int(n)
        in_tab = pl.pop("in_tablou", None)
        if isinstance(n, int) and not isinstance(n, bool) and n > 1:
            baza = (pl.get("nume") or "Circuit").strip()
            circ = [dict(copy.deepcopy(pl), nume=f"{baza} {k}") for k in range(1, n + 1)]
            if in_tab:
                # r11: cele n circuite identice într-un tablou dedicat (TD-VE cu n circuite), alimentat dintr-o plecare
                for c_ in circ:
                    c_.pop("cablu", None) if isinstance(in_tab, dict) else None
                td = {"nume": in_tab.get("nume") if isinstance(in_tab, dict) and in_tab.get("nume") else
                      (f"TD-VE ({n} × {baza})" if e_plecare_ve(pl) else f"TD {baza} ({n} circuite)"),
                      "receptor": "tablou", "copii": circ}
                if isinstance(in_tab, dict):
                    td.update({k: v for k, v in in_tab.items() if k != "nume"})
                if e_plecare_ve(pl) and td.get("ks") is None:
                    td["ks"] = 1.0       # stații VE fără DLM: toate pot încărca simultan
                out.append(td)
            else:
                out.extend(circ)
        else:
            out.append(pl)
    return out


_NR_IN_NUME = re.compile(r"\b(\d{1,3})\s*(?:x\s*)?(?:statii|stații|stati|statiuni|wallbox(?:uri)?|incarcatoare|încărcătoare|"
                         r"puncte de incarcare|puncte de încărcare|chargers?|ev chargers?|borne|prize ve|pompe|motoare|"
                         r"circuite|ups(?:-uri)?|rack(?:-uri)?)\b", re.I)


def plecari_multiple_tacute(plecari, j, obiect="P"):
    """r11 (industrial j46): „Parcare cu 6 stații EV” cu o singură putere și fără `n` — numele spune mai multe unități,
    datele descriu una: nu se desenează tăcut o singură plecare → BLOCANT cu remediere (n / n_circuite pe plecare).
    Întoarce True dacă a emis."""
    emis = False
    for i, pl in enumerate(plecari or [], 1):
        if not isinstance(pl, dict):
            continue
        if pl.get("copii"):
            emis = plecari_multiple_tacute(pl["copii"], j, f"{obiect}{i}.") or emis
            continue
        m = _NR_IN_NUME.search(_fara_diacritice(str(pl.get("nume") or "")))
        if m and int(m.group(1)) > 1 and pl.get("n") is None and pl.get("n_circuite") is None:
            k = int(m.group(1))
            emite(j, "V96", BLOCANT, f"{obiect}{i}·{pl.get('nume', '')}",
                  ce=f"plecarea „{pl.get('nume')}” descrie {k} unități, dar are o singură putere / un singur circuit",
                  detaliu=f"nu se desenează o singură plecare în locul a {k}",
                  remediere=f"n: {k} pe plecare (puterea P_kW pe unitate) → {k} plecări, sau in_tablou: true → un tablou "
                            f"cu {k} circuite; dacă P_kW e totalul, declarați P_kW pe unitate")
            emis = True
    return emis



UPS_K_INTRARE = 1.15        # DECIZIE r11: Ib intrare redresor ≈ In ieșire / η (0,95) + încărcarea bateriilor (~10 %)
UPS_PF_IESIRE = 0.9         # DECIZIE r11 [conservator, raport #105]: puterea activă disponibilă la ieșire = 0,9·Sn (fișa poate da 1,0)


def e_plecare_ups(pl):
    """r11 (industrial j15 / j33): plecare spre un UPS (`ups: true` sau receptor „ups”)."""
    return isinstance(pl, dict) and (pl.get("ups") is True or pl.get("receptor") == "ups")


def pregateste_ups(plecari, retea, j, obiect="P"):
    """r11: UPS ca plecare a tabloului — intrarea redresorului (Q intrare + cablu, Ib = 1,15·In ieșire) → UPS online
    (redresor / invertor + bypass static + bypass manual) → Q ieșire → tabloul alimentat din UPS (`copii` = PDU /
    rack-uri / circuite). `Sn_kVA` (alias `S_kVA`) obligatoriu; sarcina ieșirii ≤ 0,9·Sn; `intrari_separate: true` =
    intrare de bypass separată (a doua plecare din aceeași bară). Întoarce lista nouă sau None (BLOCANT emis)."""
    out = []
    for i, pl in enumerate(plecari or [], 1):
        if not isinstance(pl, dict):
            out.append(pl)
            continue
        ob = f"{obiect}{i}·{pl.get('nume', '')}"
        if pl.get("copii"):
            c2 = pregateste_ups(pl["copii"], pl.get("retea", retea), j, ob + ".")
            if c2 is None:
                return None
            pl = dict(pl, copii=c2)
        if not e_plecare_ups(pl):
            out.append(pl)
            continue
        sn = pl.get("Sn_kVA", pl.get("S_kVA"))
        if not _numar(sn) or sn <= 0:
            emite(j, "V07", BLOCANT, ob, "param", camp="Sn_kVA", x=sn if sn is not None else "—",
                  conditie="puterea aparentă a UPS-ului (kVA) lipsește")
            j.verificari[-1]["remediere"] = "Sn_kVA al UPS-ului (din fișă) pe plecare"
            # planșa rămâne desenabilă (plecarea fără UPS), exportul e blocat până la declararea puterii UPS-ului
            out.append({k: v for k, v in pl.items() if k not in ("ups", "bypass", "bypass_manual", "intrari_separate")
                        and not (k == "receptor" and v == "ups")})
            continue
        sn = float(sn)
        r_ = pl.get("retea", retea)
        u = SQRT3 * norme.U_N_V if r_ != "mono" else norme.U_0_V
        in_out = sn * 1000.0 / u
        bypass = _bool(pl.get("bypass"))
        if bypass is None:
            j.presupune(f"{ob}: UPS cu bypass static automat + bypass manual de mentenanță (nedeclarat — UPS online uzual)")
            bypass = True
        p = {k: v for k, v in pl.items() if k not in ("ups", "receptor", "Sn_kVA", "S_kVA", "P_kW", "In_A", "bypass",
                                                       "bypass_manual", "intrari_separate", "autonomie_min")}
        # intrarea se dimensionează la puterea UPS-ului (nu la sarcina actuală a ieșirii), cosφ ≈ 1 (redresor PFC)
        p.update({"receptor": "tablou", "P_kW": sn * UPS_K_INTRARE, "cosfi": 1.0, "ddr": False})
        meta = {"Sn_kVA": sn, "In_iesire_A": in_out, "Ib_intrare_A": in_out * UPS_K_INTRARE, "bypass": bypass,
                "bypass_manual": _bool(pl.get("bypass_manual")) is not False, "retea": r_}
        if pl.get("autonomie_min") is not None:
            meta["autonomie_min"] = pl["autonomie_min"]
        copii = p.get("copii") or []
        if copii:
            ks = pl.get("ks") or norme.ks_implicit(len(copii))
            ps = float(ks) * sum(_pi(c, 1) for c in copii)
            meta["P_iesire_kW"] = ps
            if gt(ps, UPS_PF_IESIRE * sn):
                j.emite("V62", BLOCANT, ob, f"sarcina ieșirii UPS {fmt_ro(ps)} kW (ks {fmt_ro(ks)}) > {fmt_ro(UPS_PF_IESIRE)}·Sn"
                                           f" = {fmt_ro(UPS_PF_IESIRE * sn)} kW — UPS-ul {fmt_ro(sn)} kVA e subdimensionat",
                        f"UPS ≥ {fmt_ro(ps / UPS_PF_IESIRE, 0)} kVA, sau mai puține circuite pe ieșirea UPS")
            p.pop("ks", None)
        else:
            j.presupune(f"{ob}: circuitele ieșirii UPS nedeclarate — tabloul de ieșire desenat fără plecări")
        p["_ups"] = meta
        j.pas(f"{ob}: UPS {fmt_ro(sn)} kVA — In ieșire = {fmt_ro(in_out)} A; intrare redresor Ib ≈ {fmt_ro(UPS_K_INTRARE)}·In "
              f"= {fmt_ro(in_out * UPS_K_INTRARE)} A (η ≈ 0,95 + încărcare baterii)")
        j.presupune(f"{ob}: circuitele din aval de UPS verificate cu Ik al rețelei prin bypass-ul static (majorant pentru Icu; "
                    f"în regim invertor Ik ≈ 2…3·In UPS, deconectarea prin bypass) — de confirmat cu fișa UPS")
        if not bypass:
            j.emite("V96", AVERTISMENT, ob, "UPS fără bypass static: la scurtcircuit în aval curentul e limitat de invertor "
                                            f"(≈ 2…3·In = {fmt_ro(2 * in_out, 0)}…{fmt_ro(3 * in_out, 0)} A) — deconectarea "
                                            "circuitelor din aval nu e verificată de motor",
                    "UPS cu bypass static, sau verificarea deconectării cu curba Ik a invertorului din fișă")
        out.append(p)
        if _bool(pl.get("intrari_separate")):
            out.append({"nume": f"{pl.get('nume') or 'UPS'} — intrare bypass", "receptor": "tablou", "P_kW": 0.0001,
                        "In_minim": in_out,
                        "cosfi": 1.0, "ddr": False, "L_m": pl.get("L_m"), "_ups_bypass": True,
                        **({"cablu": dict(pl["cablu"])} if isinstance(pl.get("cablu"), dict) else {})})
            if out[-1].get("L_m") is None:
                out[-1].pop("L_m")
            j.pas(f"{ob}: intrare de bypass separată — plecare proprie dimensionată la In ieșire {fmt_ro(in_out)} A")
    return out


def rezerva_echipata(pl):
    """r12: plecare de rezervă echipată (aparat montat, fără circuit): `rezerva: true`, fără putere / sarcină / copii"""
    return (isinstance(pl, dict) and pl.get("rezerva") is True and pl.get("P_kW") is None and pl.get("S_kVA") is None
            and pl.get("Ib_A") is None and not pl.get("copii") and not pl.get("_siguranta") and not pl.get("siguranta"))


def _pregateste_plecari(plecari, retea, j, obiect="P"):
    """r5: rețeaua tabloului se propagă pe plecări (mono → 230 V, 2P / 1P+N); o plecare cu `pornire` e motor;
    o plecare trifazată într-un tablou monofazat → V12 BLOCANT. Întoarce False la eroare."""
    for i, pl in enumerate(plecari, 1):
        ob = f"{obiect}{i}·{pl.get('nume', '')}"
        r_pl = pl.get("retea")
        if retea == "mono":
            if r_pl == "tri":
                emite(j, "V12", BLOCANT, ob, "retea", retea="tri (plecare trifazată într-un tablou monofazat)")
                j.verificari[-1]["remediere"] = "tablou trifazat sau plecarea monofazată"
                return False
            pl["retea"] = "mono"
            # tablou monofazat: plecările mici pe MCB 2P (curba B la iluminat / prize), nu siguranțe NH tripolare
            if (pl.get("prot_tip") is None and not pl.get("copii")
                    and ((pl.get("In_A") is not None and pl["In_A"] <= 63) or (pl.get("P_kW") is not None and pl["P_kW"] <= 13))):
                pl["prot_tip"] = "MCB"
        if pl.get("pornire") is not None and pl.get("receptor") is None:
            pl["receptor"] = "motor"
        if pl.get("copii") and not _pregateste_plecari(pl["copii"], pl.get("retea", retea), j, ob + "."):
            return False
    return True


def _sursa_tablou(inp, j):
    """r5 (P1-11): contextul la originea tabloului după `origine` declarat — „bmpt” / „retea_publica” (RCCB 300 mA din
    BMPT, ST 4-JT), „tg_existent” (tabloul din amonte, Ik3_sursa_kA; DDR amonte doar dacă e declarat IdN_amonte_mA),
    lipsă → calcul ca rețea publică, cu presupunerea declarată și FĂRĂ a conta pe un DDR din amonte nedeclarat.
    Întoarce (ctx, ddr_amonte: bool, eticheta sursei)."""
    orig = inp.get("origine")
    ida = inp.get("IdN_amonte_mA")
    ik3s = inp.get("Ik3_sursa_kA")
    if orig == "tg_existent":
        zb = _zb_din_intrare(inp.get("Zb_OD_ohm"), j)
        ddr = ida is not None or inp.get("ddr_amonte") is True
        ctx = sc.context_od(ik3s, zb, ddr_amonte=ddr, schema="TT" if inp.get("schema_pamant") == "TT" else "TN")
        if inp.get("dU_origine_pct") is not None:
            ctx["dU_pct"] = float(inp["dU_origine_pct"])
        if ik3s is None:
            j.presupune(f"Ik3max la bara tabloului existent din amonte {fmt_ro(norme.OD_IK3MAX_IMPLICIT_KA)} kA (majorant "
                        f"implicit) — Ik3_sursa_kA de introdus din calculul tabloului existent")
        if zb is None:
            j.presupune("Zbuclă la tabloul existent 0,18 + j0,09 Ω (implicită) — se confirmă din calculul instalației existente")
        if not ddr:
            j.presupune("sursa: tablou existent, fără DDR declarat în amonte — nu se contează pe un DDR din amonte")
        j.ipoteza("ik3_od", ctx["Ik3_kA"], ik3s is None)
        j.ipoteza("zb_od", sc.modul(ctx["Zb"]), zb is None)
        return ctx, ddr, "tablou existent (TGD)"
    if ik3s is not None and inp.get("Ik3_OD_kA") is None:
        inp["Ik3_OD_kA"] = ik3s
    if orig in ("bmpt", "retea_publica"):
        ddr = inp.get("ddr_amonte", True) is not False
        ctx = _context_od(inp, j, ddr_amonte=ddr)
        if ddr:
            j.presupune("sursa: rețea publică prin BMPT cu RCCB 300 mA în amonte (ST 4-JT)")
        return ctx, ddr, "RED 0,4 kV prin BMPT"
    # origine nedeclarată (SPEC §C.2, golden): racord din rețeaua publică prin BMPT — PRESUPUS, declarat în presupus[],
    # marcat pe planșă, iar V31 spune explicit că DDR-ul din amonte e presupus (nu o confirmare a deconectării)
    ddr = inp.get("ddr_amonte", True) is not False
    ctx = _context_od(inp, j, ddr_amonte=ddr)
    if ddr and ida is None:
        ctx["ddr_amonte_presupus"] = True
    j.presupune("sursa tabloului nedeclarată (origine): presupus rețea publică prin BMPT"
                + (" cu RCCB 300 mA în amonte" if ddr else "")
                + " — originea de declarat (BMPT / tablou existent / PT propriu)")
    return ctx, ddr, "SURSĂ NEDECLARATĂ — PRESUPUS RED 0,4 kV prin BMPT"


COMPENSARE_FACTOR_IN = 1.43     # SR EN 60831-1: 1,3·In (armonici) × 1,1 (toleranța capacității) ≈ 1,43·In


def _plecare_compensare(inp, plecari, j, sn_kva=None):
    """r6 (#25, #52): `compensare_kvar` → plecare din bară spre o baterie de condensatoare (regulator automat pe trepte):
    In = Q/(√3·400), întreruptorul și cablul dimensionate la 1,43·In. Adaugă plecarea la `plecari`; False la eroare."""
    q = inp.get("compensare_kvar")
    if q is None:
        return True
    if isinstance(q, bool) or not isinstance(q, (int, float)) or q <= 0 or q > 2000:
        emite(j, "V07", BLOCANT, "schema", "param", camp="compensare_kvar", x=repr(q), conditie="0 < Q ≤ 2000 kvar")
        return False
    if inp.get("retea") == "mono":
        emite(j, "V96", BLOCANT, "schema", ce="compensare la tablou monofazat",
              detaliu="bateria de condensatoare se calculează doar trifazat (3 × 400 V)",
              remediere="tablou trifazat sau compensare locală la receptor")
        return False
    in_c = float(q) * 1000.0 / (SQRT3 * norme.U_N_V)
    imin = COMPENSARE_FACTOR_IN * in_c
    plecari.append({"nume": f"Baterie condensatoare {fmt_ro(q, 0)} kvar", "S_kVA": COMPENSARE_FACTOR_IN * float(q),
                    "prot_tip": "MCCB" if imin > 63 else "MCB", "receptor": "forta", "_compensare": True,
                    "L_m": float(inp.get("compensare_L_m") or 5.0),
                    "cablu": {"material": "Cu", "metoda": "C"},
                    "_Q_kvar": float(q), "_In_cap_A": in_c})
    emite(j, "V98", INFO, "compensare", Q=fmt_ro(q, 0), In=in_c, Imin=imin)
    j.pas(f"Compensare: baterie {fmt_ro(q, 0)} kvar, In = {fmt_ro(q)}·1000/(√3·400) = {fmt_ro(in_c)} A → protecție și "
          f"cablu la 1,43·In = {fmt_ro(imin)} A (SR EN 60831-1)")
    if sn_kva and gt(float(q), 0.6 * float(sn_kva)):
        emite(j, "V98", AVERTISMENT, "compensare", "mare", Q=fmt_ro(q, 0), Sn=fmt_ro(sn_kva, 0))
    j.presupune("baterie de condensatoare automată pe trepte, cu regulator de factor de putere și TC de măsură pe "
                "alimentarea tabloului (fără filtre de armonici — de verificat THDi); lângă tablou, cablu Cu "
                + (f"{fmt_ro(inp['compensare_L_m'], 0)} m" if inp.get("compensare_L_m") else "5 m (presupus)"))
    return True


DU_COLOANA_MIN_PCT = 1.0      # r6: bugetul ΔU minim lăsat alimentării unui tablou
DU_RAMURA_MIN_PCT = 1.0       # r6: ΔU minim rămas fiecărei plecări după alimentare


def _buget_du_coloana(plecari, ctx, final, r_col):
    """r6 (#17, #4): dacă alimentarea, dimensionată la limita ei (forță − 2 %), lasă unei plecări mai puțin de 1 % din
    limita ei, bugetul ΔU al alimentării devine min(limita plecării − ΔU-ul plecării la secțiunea dimensionată singură
    de la bară), dar ≥ 1 %. Fără el, alimentarea consuma toată limita de 3 % (iluminat) și o plecare de 7 A ieșea pe
    ACYAbY 3×95 Al. None = alimentarea rămâne la limita normală."""
    jt = Jurnal()
    try:
        rc = calculeaza_ramura(copy.deepcopy(r_col), ctx, jt, "tmp")
    except Exception:      # noqa: BLE001 — estimarea bugetului nu trebuie să blocheze calculul real
        return None
    if rc["blocat"]:
        return None
    du_col = float(rc["rezultat"]["dU_ramura_pct"])
    c0 = dict(ctx, dU_pct=0.0)
    rest, strans = [], False
    for pl in plecari:
        if pl.get("copii"):
            continue           # un TD își preia singur restul (cascada are bugetul ei)
        try:
            r = _ramura_plecare(pl, 0, jt, "tmp", final=final)
            r.pop("are_aval", None)
            rr = calculeaza_ramura(r, c0, jt, "tmp")
        except Exception:      # noqa: BLE001
            continue
        if rr["blocat"]:
            continue
        z = rr["rezultat"]
        if gt(float(z["Ib_A"]), 63.0):
            continue           # doar circuitele mici primesc secțiuni absurde
        lim = float(z["dU_limita_pct"])
        rest.append(lim - float(z["dU_ramura_pct"]))
        if lim - du_col < DU_RAMURA_MIN_PCT - 1e-9 and gt(float(z["dU_ramura_pct"]), lim - du_col):
            strans = True
    if not rest or not strans:
        return None
    # r7 (#12, S14): bugetul nu se mai ia orbește = min(rest) — la puteri mici (chioșc 6 kW mono, 50 m) 1 % pe
    # alimentare cerea ACYAbY 3×95 la C50. Se compară economic (masa de conductor Cu-echivalent) câteva bugete ale
    # alimentării cu plecările redimensionate pe restul limitei și se alege cel mai ieftin ansamblu.
    cand = sorted({round(max(DU_COLOANA_MIN_PCT, min(rest)), 3), 1.5, 2.0})
    best = None
    for t in cand:
        cost = _cost_ansamblu(plecari, ctx, final, r_col, t)
        if cost is not None and (best is None or cost < best[0] - 1e-9):
            best = (cost, t)
    if best is None:
        return max(DU_COLOANA_MIN_PCT, min(rest))
    return best[1]


PRET_RELATIV_MAT = {"Cu": 1.0, "Al": 0.35}     # r7: cost relativ pe mm²·m de conductor (Al ≈ 1/3 din Cu, cu armătură)


def _cost_cablu(z):
    """Masa de conductor Cu-echivalent a unei ramuri dimensionate (n·(faze·S + N + PE)·L·preț material)."""
    nf = 2 if z.get("retea") == "mono" else 3
    s = nf * float(z.get("S_faza_mm2") or 0) + (float(z.get("S_N_mm2") or 0) if nf == 3 else 0) \
        + float(z.get("S_PE_mm2") or 0)
    return float(z.get("n_paralel") or 1) * s * float(z.get("L_m") or 0) * PRET_RELATIV_MAT.get(z.get("material"), 1.0)


def _cost_ansamblu(plecari, ctx, final, r_col, tinta):
    """Costul alimentare + plecări (fără cascade) pentru bugetul ΔU `tinta` al alimentării (None = limita normală);
    None dacă o ramură se blochează."""
    jt = Jurnal()
    r = copy.deepcopy(r_col)
    if tinta is not None:
        r["tinta_dU"] = tinta
    try:
        rc = calculeaza_ramura(r, ctx, jt, "tmp")
    except Exception:      # noqa: BLE001
        return None
    if rc["blocat"]:
        return None
    z0 = dict(rc["rezultat"], retea=r_col.get("retea", "tri"))
    cost = _cost_cablu(z0)
    c0 = dict(ctx, dU_pct=ctx.get("dU_pct", 0.0) + float(z0["dU_ramura_pct"]))
    for pl in plecari:
        if pl.get("copii"):
            continue
        try:
            rp = _ramura_plecare(pl, 0, jt, "tmp", final=final)
            rr = calculeaza_ramura(rp, c0, jt, "tmp")
        except Exception:  # noqa: BLE001
            return None
        if rr["blocat"]:
            return None
        cost += _cost_cablu(dict(rr["rezultat"], retea=rp.get("retea", "tri")))
    return cost


def _pc_tablou(plecari, pis, ks, retea, j):
    """r7 (#40, S11): puterea de calcul a tabloului — ks (IEC 61439-2 tab. 101) NU se aplică iluminatului (funcționează
    simultan, ks = 1); într-un tablou trifazat cu plecări monofazate, Q1/C1 se dimensionează pe faza cea mai încărcată
    (repartizare descrescătoare pe faza cea mai puțin încărcată) → P echivalent = 3·P faza max.
    Întoarce (Pc, P iluminat cu ks 1 | 0, P echivalent pe faza max | None)."""
    p_ilum = 0.0
    faze = [0.0, 0.0, 0.0]
    mono = []
    pc = 0.0
    for pl, p in zip(plecari, pis):
        rec = pl.get("receptor") or receptor_dupa_nume(pl.get("nume", ""), 1)
        sig = bool(pl.get("_siguranta"))
        # r8: consumatorii de siguranță funcționează simultan (ventilatoarele de desfumare, pompele) — ks = 1
        k = 1.0 if (sig or (rec == "iluminat" and not pl.get("copii") and not pl.get("_compensare"))) else ks
        if k == 1.0 and ks < 1.0 and not sig:
            p_ilum += p
        pc += k * p
        if retea == "tri" and pl.get("retea") == "mono":
            mono.append(k * p)
        else:
            for f in range(3):
                faze[f] += k * p / 3.0
    p_faza = None
    if retea == "tri" and mono:
        for p in sorted(mono, reverse=True):
            f = min(range(3), key=lambda i: (faze[i], i))
            faze[f] += p
        p_faza = 3.0 * max(faze)
        if gt(p_faza, pc):
            j.pas(f"Repartizare pe faze: {len(mono)} plecări monofazate → faza cea mai încărcată {fmt_ro(max(faze))} kW; "
                  f"Q1/C1 dimensionate pe 3·{fmt_ro(max(faze))} = {fmt_ro(p_faza)} kW (> Pc echilibrat {fmt_ro(pc)} kW)")
            pc = p_faza
    if p_ilum:
        j.presupune("ks = 1 pe plecările de iluminat (funcționare simultană); ks din IEC 61439-2 doar pe celelalte plecări")
    return pc, p_ilum, p_faza


TENSIUNI_JT_V = {230: "mono", 400: "tri"}
CHEI_TENSIUNE_JT = ("U_V", "U_n_V", "U_JT_V", "tensiune_V")


def tensiune_jt_nesuportata(inp, j, plecari=None):
    """r7 (#53): tensiunea JT declarată (U_V / U_n_V / U_JT_V / tensiune_V, pe schemă sau pe o plecare / consumator)
    în afara 230 / 400 V (ex. 690 V, 500 V, 110 V) → V96 BLOCANT explicit (tabelele, aparatele și ΔU sunt la 230/400 V);
    nu se ignoră tăcut. True dacă s-a blocat."""
    surse = [("schema", inp)] + [(f"{(p or {}).get('nume', '')}", p) for p in (plecari or []) if isinstance(p, dict)]
    for ob, d in surse:
        for k in CHEI_TENSIUNE_JT:
            v = d.get(k)
            if v is None:
                continue
            try:
                u = float(str(v).replace(",", ".").split("/")[-1])
            except ValueError:
                u = None
            if u is not None and int(u) == u and int(u) in TENSIUNI_JT_V:
                continue
            emite(j, "V96", BLOCANT, ob, ce=f"tensiune {v} V", detaliu="motorul dimensionează doar rețele JT 230 V "
                  "(monofazat) / 3 × 400 V (trifazat): cablurile, aparatele (Ue, Icu), ΔU și curenții de motor la altă "
                  "tensiune (ex. 690 V) nu sunt modelate", remediere="rețea 400/230 V sau proiect de specialitate la "
                  "tensiunea respectivă (aparataj Ue ≥ 690 V, trafo dedicat)")
            return True
    return False


PROPORTIE_TABLOU_SIGURANTA = 0.5    # r8 (#14): ≥ 50 % din putere de siguranță → tabloul întreg e de siguranță


def marcheaza_siguranta(plecari, inp, j, obiect="tablou"):
    """r8 (P0 #12, #14, #64): regula de siguranță la incendiu aplicată PE CONSUMATOR, în orice tip de schemă cu plecări
    (tablou, PT). Marchează `_siguranta` pe plecările de siguranță (și pe tot subarborele lor) și `_cale_siguranta` pe
    tablourile care alimentează un consumator de siguranță (fără DDR pe calea lui). Pompa de rezervă („rezervă”,
    `rezerva: true`) e desenată, dar nu se adună la bilanț. Întoarce „tot” (tablou de siguranță), „mixt” (consumatori
    de siguranță + consumatori normali) sau None."""
    tot = tablou_de_siguranta(inp)

    def are_sig(pl, parinte):
        s_ = parinte or e_consumator_siguranta(pl)
        copii = pl.get("copii") or []
        jos = [are_sig(c, s_) for c in copii]
        if s_:
            pl["_siguranta"] = True
            if c_rez(pl):
                pl["_rezerva"] = True
        elif any(jos):
            pl["_cale_siguranta"] = True
        return s_ or any(jos)

    def c_rez(pl):
        return pl.get("rezerva") is True or "rezerv" in _fara_diacritice(str(pl.get("nume") or "")).lower()

    psi = _context_pompe_psi(plecari)
    gasit = [are_sig(pl, tot or (psi and _e_pompa(pl))) for pl in plecari]
    if not any(gasit):
        return None
    if any(pl.get("_siguranta") for pl in plecari) and not tot:
        # jockey / pompă pilot lângă pompe de incendiu = tot instalație de stingere; r9: clapetele / trapele de fum
        # lângă ventilatoarele de desfumare = tot instalația de desfumare
        desf = any(pl.get("_siguranta") and "desfum" in _fara_diacritice(str(pl.get("nume") or "")).lower()
                   for pl in plecari)
        chei = ("pilot", "jockey", "mentinere") + (("clapet", "trapa", "trape", "fum") if desf else ())
        for pl in plecari:
            if not pl.get("_siguranta") and pl.get("siguranta") is None and any(
                    k in _fara_diacritice(str(pl.get("nume") or "")).lower() for k in chei):
                pl["_siguranta"] = True
    if not tot:
        # r9 (industrial #25, #26, S7): regimul de siguranță e al CONSUMATORULUI — tabloul devine „de siguranță” numai
        # dacă e declarat (titlu TDSI / TS / `siguranta_tablou`) sau dacă TOȚI consumatorii lui sunt de siguranță; un
        # tablou mixt (sprinkler + rampe / iluminat normal / CTA) păstrează DDR-ul și cablul normal pe consumatorii
        # normali, iar cei de siguranță se racordează înaintea Q1 general (pragul r8 „≥ 50 % din putere” — eliminat)
        normale = [pl for pl in plecari if not pl.get("_compensare")]
        if normale and all(pl.get("_siguranta") for pl in normale):
            tot = True
    nume = ", ".join(pl.get("nume", "") for pl in plecari if pl.get("_siguranta"))
    if tot:
        emite(j, "V97", INFO, obiect, "tablou", detaliu=f"toate circuitele ({nume}) — fără DDR, alimentare cu cablu "
                                                       f"rezistent la foc, ks = 1")
        return "tot"
    return "mixt"


def _prot_iesire(prot):
    """Protecția unei ramuri (dict al motorului de protecții) în forma rezultatului (`protectie`)."""
    out = {"tip": prot["tip"], "In_A": prot["In_A"]}
    for k in ("curba", "Ir_A", "Ir_multiplu", "decl", "Im_A", "Isd_A", "Isd_multiplu", "Ii_A", "tsd_s", "Icu_kA"):
        if prot.get(k) is not None:
            out[k] = prot[k]
    return out


MONO_MAX_KW = 3.68     # r8 (S11): circuit final de iluminat / prize ≤ 3,68 kW (16 A la 230 V) → monofazat 1P+N


def _circuite_mono_mici(plecari, j):
    """r8 (S11, p38): într-un tablou trifazat, circuitele finale de iluminat / prize ≤ 3,68 kW fără rețea declarată
    sunt monofazate (1P+N, repartizate pe faze), nu 4P."""
    n = 0
    for pl in plecari:
        if not isinstance(pl, dict) or pl.get("retea") is not None or pl.get("copii") or pl.get("pornire"):
            continue
        rec = pl.get("receptor") or receptor_dupa_nume(pl.get("nume", ""), 1)
        if rec in ("iluminat", "prize") and pl.get("P_kW") is not None and pl.get("In_A") is None \
                and pl.get("S_kVA") is None and 0 < float(pl["P_kW"]) <= MONO_MAX_KW + 1e-9:
            pl["retea"] = "mono"
            if pl.get("prot_tip") is None:
                pl["prot_tip"] = "MCB"
            n += 1
    if n:
        j.presupune(f"{n} circuite de iluminat / prize ≤ {fmt_ro(MONO_MAX_KW)} kW monofazate (1P+N), repartizate pe faze "
                    f"— rețeaua se declară pe circuit (retea: „tri”) dacă e trifazat")


def _verifica_q1_tablou(inp, j, rr, pc, p_decl, rez):
    """r8 (S5, #7, #63): coerența Q1 / sursă la un tablou — Σ sarcină > Sn trafo (PT propriu) → V62 BLOCANT; Ir Q1 > In_T
    → V60 (BLOCANT dacă Ib > In_T); P declarată < Pc cu Ib(Pc) > In Q1 → V04 BLOCANT (nu doar V14)."""
    prot = rr.get("prot") or {}
    cos = inp.get("cosfi") or norme.COSFI_IMPLICIT["tablou"]
    u = SQRT3 * norme.U_N_V if inp.get("retea", "tri") == "tri" else norme.U_0_V
    ib_pc = pc * 1000.0 / (u * cos)
    ir = prot.get("Ir_A") or prot.get("In_A")
    if (p_decl is not None and lt(p_decl, pc) and ir and gt(ib_pc, norme.LOCUINTA_I_NEDECLANSARE * ir)
            and inp.get("In_Q1_A") is None):
        # peste 1,13·Ir (curentul convențional de nedeclanșare) Q1 declanșează la sarcina din bilanț — nu e o simplă
        # diferență de ks; între In și 1,13·In rămâne V14 AVERTISMENT
        emite(j, "V04", BLOCANT, "Q1/C1", Ib=ib_pc, Ip=ir)
        j.verificari[-1]["mesaj"] += (f" — Ib din bilanțul plecărilor (Pc = {fmt_ro(pc)} kW); puterea declarată "
                                      f"{fmt_ro(p_decl)} kW e sub bilanț")
        j.verificari[-1]["remediere"] = "puterea tabloului = Pc din bilanț (sau ks justificat) → Q1 / C1 mai mari"
    in_q1 = prot.get("In_A")
    if inp.get("origine") in (None, "bmpt", "retea_publica") and in_q1 and gt(in_q1, norme.BMPT_I_MAX_A):
        # r9 (industrial #71): un BMPT (declarat sau PRESUPUS) nu există peste 250 A (ST 4-JT: BMPTi-250) — Q1 de
        # {In} A nu poate fi alimentat dintr-un BMPT; nu se presupune un bloc peste limita lui
        presupus = inp.get("origine") is None
        # Q1 declarat (In_Q1_A) sau BMPT declarat → BLOCANT; Q1 calculat din bilanț pe o sursă nedeclarată → AVERTISMENT
        # (golden T05: originea se cere, desenul rămâne orientativ)
        txt = (f"Q1 {fmt_ro(in_q1, 0)} A > {fmt_ro(norme.BMPT_I_MAX_A, 0)} A: "
               + ("sursa tabloului e PRESUPUSĂ BMPT, dar" if presupus else "")
               + f" nu există BMPT peste {fmt_ro(norme.BMPT_I_MAX_A, 0)} A (BMPTi-250, ST 4-JT)")
        if inp.get("In_Q1_A") is not None or not presupus:
            emite(j, "V50", BLOCANT, "Q1/C1", "ib", Ib=in_q1)
            j.verificari[-1]["mesaj"] = txt
            j.verificari[-1]["remediere"] = ("declarați originea tabloului: PT propriu (origine „pt_propriu”, pt_Sn_kVA), "
                                             "tablou existent (origine „tg_existent”) sau racord din PT-ul OD; altfel "
                                             "Q1 ≤ 250 A")
            j.verificari[-1]["intrebare"] = True
        else:
            # Q1 calculat din bilanț pe o sursă nedeclarată (golden T05, T09, T13, T14): presupunerea o spune explicit
            j.presupune(txt + " — originea tabloului (PT propriu / tablou existent / PT OD) de declarat")
    sn = inp.get("pt_Sn_kVA")
    if inp.get("origine") == "pt_propriu" and sn:
        in_t = float(sn) * 1000.0 / (SQRT3 * norme.U_N_V)
        sc_ = (float(p_decl) if p_decl is not None and not lt(p_decl, pc) else pc) / cos
        rez["Sc_kVA"] = sc_
        if gt(sc_, float(sn)):
            emite(j, "V62", BLOCANT, "schema", x=sc_, y=sn)
            j.verificari[-1]["remediere"] = "trafo mai mare / sarcina împărțită / ks justificat"
        if ir and gt(ir, in_t):
            ib_t = sc_ * 1000.0 / (SQRT3 * norme.U_N_V)
            emite(j, "V60", BLOCANT if gt(ib_t, in_t) else AVERTISMENT, "Q1/C1", "AV", x=ir, y=in_t)
            j.verificari[-1]["mesaj"] = (f"Ir Q1 {fmt_ro(ir)} A > In_T {fmt_ro(in_t)} A al PT {fmt_ro(sn, 0)} kVA — "
                                         + ("sarcina depășește trafo" if gt(ib_t, in_t) else
                                            "reglați Ir ≤ In_T (trafo neprotejat la suprasarcină de Q1)"))


def _sectii_tablou_pt(inp, j):
    """r11 (panoul de confirmare: TG din PT propriu cu 2 trafo, cupla deschisă, AAR): TG cu două secții de bare —
    T1 → Q1.1 → secția 1, T2 → Q1.2 → secția 2, cupla QC normal deschisă (interblocaj 2 din 3, opțional AAR). Fiecare
    intrare se dimensionează pe toată sarcina (cu cupla închisă un trafo alimentează ambele secții); Ik pe secție = un
    trafo. Întoarce dict (secțiile), None (un singur trafo / paralel) sau False (BLOCANT emis)."""
    n = inp.get("n_trafo", inp.get("pt_n_trafo"))
    aar = _bool(inp.get("aar"))
    cupla = _fd(inp.get("cupla")).lower() if isinstance(inp.get("cupla"), str) else None
    doua = (inp.get("origine") == "pt_propriu" and _numar(n) and int(n) == 2 and cupla in _CUPLA_NO
            and inp.get("bara") is None and inp.get("bara_racord") is None)
    if aar and not doua:
        emite(j, "V96", BLOCANT, "schema", ce="AAR declarat fără două secții de bare alimentate din două trafo",
              detaliu="AAR-ul închide cupla dintre secțiile a două trafo (cuplă normal deschisă)",
              remediere="origine „pt_propriu”, n_trafo 2, cupla „deschisa”, aar true — sau GE + ATS (tip „ge_ats”)")
        return False
    if not doua:
        return None
    j.pas("TG cu două secții de bare din PT propriu 2 trafo: intrările Q1.1 (T1) și Q1.2 (T2) dimensionate fiecare pe "
          "toată sarcina (cu cupla închisă un trafo alimentează ambele secții); Ik3 pe secție = un trafo")
    if aar:
        j.pas("AAR pe cupla QC: lipsă tensiune pe o secție → deschide Q1.k → închide QC; interblocaj 2 din 3")
    elif inp.get("aar") is None:
        j.presupune("cupla QC fără AAR (nedeclarat) — închidere manuală cu interblocaj 2 din 3; cu AAR declarați aar: true")
    return {"aar": bool(aar)}


def _vitali_tablou(plecari, inp, j, sectii_tg):
    """r11 (panoul de confirmare): `vital` pe plecările unui tablou are sens doar cu o rezervă — la TG cu 2 secții + AAR
    plecările nevitale (vital: false) se deconectează la comanda AAR (descărcarea sarcinii). Fără rezervă → BLOCANT
    „nesuportat” (nu se ignoră tăcut). Întoarce False dacă a blocat."""
    vit = [p for p in plecari if isinstance(p, dict) and p.get("vital") is not None]
    if not vit:
        return True
    if sectii_tg and sectii_tg.get("aar"):
        for p in plecari:
            if p.get("vital") is False:
                p["_descarcare_aar"] = True
        j.pas("plecările nevitale se deconectează la comanda AAR (descărcarea sarcinii): "
              + ", ".join(p.get("nume", "") for p in plecari if p.get("_descarcare_aar")))
        return True
    emite(j, "V96", BLOCANT, "schema", ce="plecări marcate vital / nevital într-un tablou fără sursă de rezervă",
          detaliu="fără GE / AAR, marcajul vital nu schimbă schema — nu se ignoră tăcut",
          remediere="GE + ATS cu bară vitală (tip „ge_ats”, bara_vitala true, consumatori vital true/false) sau TG din "
                    "PT cu 2 trafo + AAR (n_trafo 2, cupla „deschisa”, aar true)")
    return True


def schema_tablou(inp, j):
    """SPEC §C.2: bilanțul de puteri, Q1 + alimentarea C1, bara TG și plecările (cu cascade)."""
    rez = {}
    plecari_multiple_tacute(inp.get("plecari") or [], j)
    plecari = expandeaza_plecari(inp.get("plecari") or [])
    plecari = pregateste_ups(plecari, inp.get("retea", "tri"), j)
    if plecari is None:
        return rez
    inp["plecari"] = plecari
    if tensiune_jt_nesuportata(inp, j, plecari):
        return rez
    if not plecari:
        # v1.2: tablou fără plecări → nimic de dimensionat (nu se exportă o schemă goală)
        emite(j, "V07", BLOCANT, "schema", "plecari", tablou="tabloul")
        return rez
    sectii_tg = _sectii_tablou_pt(inp, j)
    if sectii_tg:
        plecari = _sectii_pt(plecari, inp, j)
        inp["plecari"] = plecari
    elif sectii_tg is False:
        return rez
    if not _vitali_tablou(plecari, inp, j, sectii_tg):
        return rez
    retea_tg = inp.get("retea", "tri")
    if retea_tg == "tri":
        _circuite_mono_mici(plecari, j)
    if not _pregateste_plecari(plecari, retea_tg, j):
        return rez
    if not _plecare_compensare(inp, plecari, j, inp.get("pt_Sn_kVA") if inp.get("origine") == "pt_propriu" else None):
        return rez
    rez["retea"] = retea_tg
    mod_sig = marcheaza_siguranta(plecari, inp, j)
    if mod_sig:
        rez["siguranta"] = mod_sig
        nume_sig = ", ".join(pl.get("nume", "") for pl in plecari if pl.get("_siguranta"))
        if inp.get("schema_pamant") == "TT":
            emite(j, "V97", BLOCANT, "schema", "tt", nume=nume_sig)
            j.verificari[-1]["remediere"] = ("alimentarea consumatorilor de siguranță din TN-S (PT propriu / sursă "
                                             "separată) sau proiect de specialitate")
        if (inp.get("origine") in (None, "bmpt", "retea_publica") and inp.get("ddr_amonte") is None
                and inp.get("IdN_amonte_mA") is None):
            # r8 (P0): alimentarea consumatorilor de siguranță se racordează înaintea DDR-ului general al branșamentului
            # (fără RCCB 300 mA în amonte) — nu se presupune un DDR pe calea lor
            inp["ddr_amonte"] = False
            rez["fara_ddr_amonte_siguranta"] = True
            j.presupune("consumatori de siguranță: tabloul racordat înaintea DDR-ului general al branșamentului (fără "
                        "RCCB 300 mA în amonte, I7/2011, P118-3) — de confirmat cu OD / proiectul de branșament")
        if mod_sig == "mixt" and (inp.get("_bara_vitala_ge") or sectii_tg):
            # r11: TG cu bară vitală — circuitele de siguranță au sursa de rezervă (GE prin ATS) pe bara vitală; legătura
            # bara normală → ATS rămâne după Q1 (desenul TG cu două bare)
            j.presupune("circuitele de siguranță pe bara vitală (rețea + GE prin ATS); legătura spre ATS după Q1 general — "
                        "racordul înaintea Q1 general se declară separat, dacă avizul ISU îl cere")
        elif mod_sig == "mixt":
            for pl in plecari:
                if pl.get("_siguranta"):
                    pl["_inainte_Q1"] = True
            emite(j, "V97", INFO, "schema", "amonte_q1", nume=nume_sig)
    if inp.get("schema_pamant") is None:
        j.presupune("schema de legare la pământ nedeclarată → TN-C-S (TN-S în aval de separarea PEN) — de confirmat "
                    "TN-C-S / TN-S / TT")
    # r8: unitatea de rezervă a unui consumator de siguranță (pompa de rezervă) e desenată, dar nu se adună
    pis = [0.0 if pl.get("_rezerva") else _pi(pl, 0) for pl in plecari]
    if any(pl.get("_rezerva") for pl in plecari):
        j.presupune("pompa (unitatea) de rezervă nu funcționează simultan cu cea activă — desenată, neadunată la bilanț")
    spi = sum(pis)
    ks, ks_impl = _ks_bilant(inp, sum(1 for p_ in plecari if not p_.get("_compensare")))
    if mod_sig == "tot" and ks_impl:
        ks = 1.0          # r8: tablou de siguranță — toți consumatorii funcționează simultan
        j.presupune("ks = 1 (tablou de siguranță la incendiu — consumatorii funcționează simultan)")
    elif ks_impl and plecari and all(e_plecare_ve(p_) for p_ in plecari):
        ks = 1.0          # r11: stații VE fără DLM declarat — pot încărca toate simultan
        j.presupune("ks = 1 (stații VE fără gestionare dinamică a sarcinii — încărcare simultană); cu DLM declarați ks")
    elif ks_impl:
        j.presupune(f"ks = {fmt_ro(ks)} (IEC 61439-2 tab. 101, {len(plecari)} plecări)")
    j.ipoteza("ks", ks, ks_impl)
    pc, p_ilum, p_faza = _pc_tablou(plecari, pis, ks, retea_tg, j)
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
    if p_ilum:
        rez["bilant"]["P_iluminat_ks1_kW"] = p_ilum
    if p_faza:
        rez["bilant"]["P_faza_max_kW"] = p_faza
    j.pas(f"Bilanț: Σ Pi = {' + '.join(fmt_ro(p) for p in pis) or '0'} = {fmt_ro(spi)} kW; ks({len(plecari)}) = "
          f"{fmt_ro(ks)}" + (f" (iluminat {fmt_ro(p_ilum)} kW cu ks = 1)" if p_ilum else "") + f" → Pc = {fmt_ro(pc)} kW")
    if p_decl is not None and lt(p_decl, pc):
        emite(j, "V14", AVERTISMENT, "schema", P=p_decl, Pc=pc)

    final = bool(inp.get("circuite_finale"))
    if inp.get("_ctx_sursa") is not None:
        # r10: sursa calculată de schema apelantă (GE izolat — bornele GE în regim generator)
        ctx = dict(inp["_ctx_sursa"])
        rez["sursa"] = inp.get("_sursa_eticheta") or "sursă proprie"
    elif inp.get("origine") == "pt_propriu":
        # SPEC §B.1.1: TG din PT propriu — limite ΔU 6/8 %, fără DDR în amonte; sursa = trafo dacă Sn e dat
        sn = inp.get("pt_Sn_kVA")
        if sn is not None:
            if int(sn) not in norme.TRAFO or float(sn) != int(sn):
                emite(j, "V05", BLOCANT, "schema", "trafo", Sn=sn, vecini=", ".join(str(x) for x in norme.TRAFO_SN_KVA))
                return rez
            nt = n_trafo_sursa(inp, j, f"PT propriu {int(sn)} kVA")
            t = trafo_sursa(inp, j, int(sn), inp.get("trafo_izolatie"), *(nt or (1, False)))
            if nt is None or t is None:
                return rez
            if inp.get("SkQ_MVA") is None:
                j.presupune("S\"kQ = 500 MVA, R/X = 0,1 (rețea MT, majorant)")
            j.ipoteza("skq", t["SkQ_MVA"], inp.get("SkQ_MVA") is None)
            j.ipoteza("trafo", (t["uk_pct"], t["Pk_W"]), not t.get("uk_declarat"))
            ctx = sc.context_pt(t)
            rez["PT_sursa"] = {"Sn_kVA": int(sn), "n_trafo": nt[0], "paralel": nt[1], "uk_pct": t["uk_pct"],
                               "Ik3max_bara_kA": t["Ik3max_bara_kA"]}
            gr_ = grupa_conexiuni(inp, j)
            if gr_ is None:
                return rez
            if inp.get("grupa_conexiuni") is not None or inp.get("pt_grupa_conexiuni") is not None:
                rez["PT_sursa"]["grupa"] = gr_
            if nt[0] > 1:
                j.pas(f"Sursa: PT {nt[0]} × {int(sn)} kVA " + (f"în paralel pe bara JT → Ik3max bară = "
                      f"{fmt_ro(t['Ik3max_bara_kA'])} kA (toate trafo în funcțiune)" if nt[1] else
                      f"cu secții separate → Ik3max bară = {fmt_ro(t['Ik3max_bara_kA'])} kA (un trafo)"))
            j.presupune(f"sursa: bara JT a PT propriu {(str(nt[0]) + ' × ') if nt[0] > 1 else ''}{sn} kVA")
        else:
            ctx = _context_od(inp, j, ddr_amonte=False)
            ctx["origine"] = "pt_propriu"
            j.presupune(f"sursa: PT propriu cu Sn necunoscut — Ik3max 25 kA și Zbuclă {fmt_ro(norme.OD_ZBUCLA_MODUL_IMPLICIT_OHM, 2)} Ω implicite")
    else:
        ctx, ddr_am, rez["sursa"] = _sursa_tablou(inp, j)
        if ddr_am:
            # v1.3 (§B.18.1): DDR-ul branșamentului e amontele tuturor DDR-urilor din tablou
            # r6 / Î1 (28.10.2026): tablou monofazat din BMPM — RCBO 300 mA instantaneu (ST 3-JT), ca la locuință
            bmpm_s = norme.LOCUINTA_DDR_BRANSAMENT_IMPLICIT["selectiv"]
            ctx["ddr_sus"] = _ddr_amonte(inp, inp.get("retea", "tri"), bmpm_sel=bmpm_s)
            if inp.get("retea") == "mono" and inp.get("DDR_amonte_selectiv") is None and inp.get("IdN_amonte_mA") is None:
                ctx["ddr_sus"]["presupus"] = True
                j.presupune("RCBO 300 mA din BMPM instantaneu, tip AC (ST 3-JT DEER) — blocul cu RCBO selectiv (S) se "
                            "declară (DDR_amonte_selectiv: true)")
    if inp.get("origine") == "pt_propriu":
        _ps = rez.get("PT_sursa") or {}
        rez["sursa"] = (f"PT propriu{(' ' + (str(_ps['n_trafo']) + ' × ' if _ps.get('n_trafo', 1) > 1 else '') + fmt_ro(inp['pt_Sn_kVA'], 0) + ' kVA') if inp.get('pt_Sn_kVA') else ''} — bara JT"
                        + (" (trafo în paralel)" if _ps.get("paralel") else ""))
    if inp.get("origine") == "pt_propriu" and inp.get("IdN_amonte_mA") is not None:
        ctx["ddr_sus"] = _ddr_amonte(inp)

    # pct. 4: întâi protecțiile plecărilor (doar Ip)
    jt = Jurnal()
    ips = [x for x in (_ip_preliminar(pl, 0, jt, final) for pl in plecari) if x is not None]

    cab = dict(inp.get("cablu") or {})
    if mod_sig == "tot":
        # r8 (P0): alimentarea unui tablou de siguranță — cablu Cu rezistent la foc (NHXH FE180/E90), traseu propriu
        cab.setdefault("material", "Cu")
        cab.setdefault("izolatie", "XLPE")
        cb.metoda_implicita(cab, "C")
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
    if mod_sig:
        # r8 (#14): consumatorii de siguranță funcționează simultan — Q1/C1 ≥ Σ Ib reale ale lor (motoare cu η·cosφ)
        ib_sig = 0.0
        for pl in plecari:
            if pl.get("_siguranta") and not pl.get("_rezerva"):
                try:
                    rp = _ramura_plecare(pl, 0, Jurnal(), "tmp", final=final)
                    rp["_doar_protectie"] = True
                    ib_sig += float(calculeaza_ramura(rp, {"Ik3_kA": 1.0, "origine": "retea_publica", "dU_pct": 0.0},
                                                      Jurnal(), "tmp")["Ib"] or 0.0)
                except Exception:      # noqa: BLE001 — estimarea nu blochează calculul
                    pass
        if ib_sig and mod_sig == "tot":
            ips.append(ib_sig)
    for k in ("cosfi", "h3", "h3_pct", "Icu_fortat"):
        if inp.get(k) is not None:
            r[k] = inp[k]
    if inp.get("Q1_tip"):
        r["prot_tip"] = inp["Q1_tip"]
    elif tip_q_declarat(inp, "Q_general_tip", "aparat"):
        r["prot_tip"] = tip_q_declarat(inp, "Q_general_tip", "aparat")     # r9 (#20): ACB declarat respectat
    if inp.get("In_Q1_A") is not None:
        r["In_fortat"] = inp["In_Q1_A"]
    if inp.get("_Ib_Q1_A") is not None:
        r["Ib_A"] = float(inp["_Ib_Q1_A"])       # r10: GE izolat — C1 (GE → TG) poartă curentul GE (Ir Q_G)
    elif p_decl is not None:
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
        orig = inp.get("origine")
        if orig == "tg_existent" and inp.get("IdN_amonte_mA") is None:
            # r5: sursa fără DDR declarat în amonte (tablou existent / nedeclarată) — nu se presupune RCCB-ul BMPT;
            # tabloul își asigură singur protecția: bloc diferențial reglabil pe Q1 + DDR pe fiecare plecare
            emite(j, "V34", AVERTISMENT, "C1 (amonte)", "lipsa")
            j.verificari[-1]["mesaj"] = ("TT: DDR în amontele cablului C1 nedeclarat — protecția C1 la contact indirect "
                                         "revine tabloului din amonte (IdN_amonte_mA de declarat)")
            idn_am, am = None, None
        else:
            idn_am = _tt_amonte(inp, j, ra, bmpt=orig != "pt_propriu")
            if idn_am is None:
                return rez
        # v1.3 R5 (§C.2 pct. 13, M5-4): DDR-urile alese selectiv în timp și în IΔn — amonte temporizat → Q1 fără DDR
        # propriu, circuite instantanee ≤ IΔn amonte/3; altfel bloc diferențial reglabil pe Q1 (Δt 0,15 s)
        if idn_am is not None:
            am = ddr_mod.descriere(idn_am, inp.get("DDR_amonte_selectiv", True),
                                   "DDR amonte (declarat)" if inp.get("IdN_amonte_mA") is not None else "RCCB BMPT")
        al = ddr_mod.alege_tt(lim, am)
        idn = al["idn_circuite"]
        ctx["idn_tt_mA"] = idn
        ctx["RA_tt"] = ra
        ctx["ddr_sus"] = am
        if al["intrare"] and not isinstance(r.get("ddr"), dict):
            r["ddr"] = {"IdN_mA": al["intrare"]["IdN_mA"], "dt_s": al["intrare"]["dt_s"], "_motor": True}
        rez["DDR_TT_IdN_mA"] = max(idn, idn_am or 0, al["intrare"]["IdN_mA"] if al["intrare"] else 0)
        rez["IdN_amonte_mA"] = idn_am
        rez["RA_ohm"] = ra
        rez["RA_IdN_V"] = ra * rez["DDR_TT_IdN_mA"] / 1000.0
        j.pas(f"TT: RA = {fmt_ro(ra)} Ω → IΔn ≤ 50/RA = {fmt_ro(50000.0 / ra, 0)} mA; amonte "
              + (f"{am['denumire']} {idn_am} mA {am['temporizare']}" if am else "fără DDR declarat") + " → " + (f"Q1 bloc diferențial reglabil {al['intrare']['IdN_mA']} mA, Δt "
                                         f"{fmt_ro(al['intrare']['dt_s'], 2)} s" if al["intrare"] else
                                         "Q1 fără DDR propriu (protejat de amonte)") +
              f"; circuite DDR {idn} mA instantaneu (prize 30 mA)")
    if (inp.get("cablu") or {}).get("S_fortat") is None:
        tinta = _buget_du_coloana(plecari, ctx, final, r)
        if tinta is not None:
            r["tinta_dU"] = tinta
            j.pas(f"Q1/C1: bugetul ΔU al alimentării ≤ {fmt_ro(tinta)} % — restul limitei rămâne plecărilor (altfel o "
                  f"plecare mică ar primi o secțiune absurdă)")
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
    _verifica_q1_tablou(inp, j, rr, pc, p_decl, rez)
    if mod_sig == "tot":
        rez["Q1_C1"]["rezistent_foc"] = True
    ctx_tg = rr["ctx_aval"]
    rez["bara_TG"] = {"Ik3max_kA": ctx_tg["Ik3_kA"], "dU_pct": ctx_tg["dU_pct"]}
    amonte_n, ctx_sig = rr["prot"], None
    if mod_sig == "mixt" and not (inp.get("_bara_vitala_ge") or sectii_tg):
        # r8 (P0 #64): consumatorii de siguranță se racordează ÎNAINTEA întreruptorului general Q1 (bornele de intrare
        # ale tabloului): C1 îi alimentează pe toți, protejat în tabloul sursă (Q1/C1 = protecția C1); Q1 general
        # (întreruptorul tabloului) poartă doar consumatorii normali și nu deconectează circuitele de siguranță
        norm = [pl for pl in plecari if not pl.get("_siguranta")]
        pis_n = [p for pl, p in zip(plecari, pis) if not pl.get("_siguranta")]
        jq = Jurnal()
        pc_n = _pc_tablou(norm, pis_n, ks, retea_tg, jq)[0]
        ips_n = [x for x in (_ip_preliminar(pl, 0, jq, final) for pl in norm) if x is not None]
        rq = {"rol": "intrare", "receptor": "tablou", "retea": retea_tg, "cablu": dict(cab), "are_aval": True,
              "P_kW": max(pc_n, 0.1), "_doar_protectie": True}
        if ips_n:
            rq["Ip_min_extra"] = max(ips_n) + 0.01
        for k in ("cosfi", "Q1_tip"):
            if inp.get(k) is not None:
                rq["prot_tip" if k == "Q1_tip" else k] = inp[k]
        rrq = calculeaza_ramura(rq, ctx_tg, jq, "Q1")
        if rrq["prot"] is not None:
            pq = dict(rrq["prot"])
            if pq.get("Icu_kA") is None or lt(pq["Icu_kA"], ctx_tg["Ik3_kA"]):
                pq["Icu_kA"] = (rr["prot"] or {}).get("Icu_kA") or pq.get("Icu_kA")
            rez["Q1_general"] = _prot_iesire(pq)
            amonte_n = pq
            j.pas(f"Q1 general (după racordul circuitelor de siguranță): Pc consumatori normali = {fmt_ro(pc_n)} kW → "
                  f"{pq['tip']} {pq['In_A']} A; Q1/C1 = protecția cablului C1 în tabloul sursă")
        ctx_sig = dict(ctx_tg)
    rez["plecari"] = _plecari(plecari, ctx_tg, amonte_n, j, final=final, ctx_sig=ctx_sig, amonte_sig=rr["prot"])
    if sectii_tg:
        it = iter(plecari)
        for z in rez["plecari"]:
            if int(z.get("nivel") or 0) == 0:
                pl_ = next(it, {})
                z["sectie"] = pl_.get("sectie", 1)
                if pl_.get("_descarcare_aar"):
                    z["descarcare_aar"] = True
        rez["sectii_tg"] = dict(sectii_tg, n1=sum(1 for p_ in plecari if p_.get("sectie", 1) == 1))
        sn_t = inp.get("pt_Sn_kVA")
        if sectii_tg.get("aar") and sn_t:
            p_v = sum(p_ for pl_, p_ in zip(plecari, pis) if not pl_.get("_descarcare_aar"))
            s_v = ks * p_v / 0.9
            rez["sectii_tg"]["Sc_AAR_kVA"] = s_v
            if gt(s_v, float(sn_t)):
                emite(j, "V62", AVERTISMENT, "schema", x=s_v, y=sn_t)
                j.verificari[-1]["mesaj"] = (f"regim AAR (un trafo pe ambele secții): Sc = {fmt_ro(s_v)} kVA > Sn = {sn_t} kVA"
                                             " — descărcarea automată a plecărilor nevitale la închiderea QC")
                j.verificari[-1]["remediere"] = "marcați plecările nevitale (vital: false) sau trafo mai mari"
    if inp.get("schema_pamant") == "TT":
        _nota_spl(rez, inp, "tablou")            # v1.3 R5: nota 3 cu DDR-urile reale ale plecărilor
    return rez


# ============================================================================================================
# C.5 Post de transformare 20/0,4 kV
# ============================================================================================================
_CUPLA_NI = ("inchisa", "ni", "nc", "normal_inchisa", "paralel", "in_paralel", "closed")
_CUPLA_NO = ("deschisa", "no", "normal_deschisa", "open", "separat", "separate")


CHEI_UK = ("uk_pct", "pt_uk_pct", "ucc_pct", "pt_ucc_pct")     # r11 (industrial j41): „Ucc” = uk (tensiunea de scurtcircuit)


def _uk_declarat(inp, j):
    """r10 (industrial i65): uk declarat (`uk_pct`, alias `pt_uk_pct`) — None dacă lipsește, False dacă e invalid
    (V12 BLOCANT cu remediere). r11 (j41): alias `ucc_pct` / `pt_ucc_pct` (Ucc din plăcuță = uk); două valori diferite
    declarate → BLOCANT (nu se alege tăcut una)."""
    vals = [(k, inp.get(k)) for k in CHEI_UK if inp.get(k) is not None]
    if not vals:
        return None
    if len({float(v) if _numar(v) else repr(v) for _, v in vals}) > 1:
        emite(j, "V12", BLOCANT, "schema", "camp", camp=" / ".join(k for k, _ in vals),
              valoare=" ≠ ".join(str(v) for _, v in vals))
        j.verificari[-1]["remediere"] = "o singură valoare uk (Ucc) din plăcuța / fișa transformatorului"
        return False
    uk = vals[0][1]
    if uk is None:
        return None
    if not _numar(uk) or not 2.0 <= float(uk) <= 12.0:
        emite(j, "V12", BLOCANT, "schema", "camp", camp="uk_pct", valoare=uk)
        j.verificari[-1]["remediere"] = ("uk din plăcuța / fișa transformatorului, în % (uzual 4 % până la 630 kVA, "
                                         "6 % peste)")
        return False
    return float(uk)


_GRUPA_RE = re.compile(r"^([DYZ])([YZD])(N?)(\d{1,2})$")


def grupa_conexiuni(inp, j):
    """r11 (industrial j41): grupa de conexiuni declarată (`grupa_conexiuni`, alias `pt_grupa_conexiuni`) — „Dyn11”,
    „Dyn5”, „Yzn11” … (indicele orar 0…11) → textul normalizat (desen + listă); nedeclarată → Dyn5 (implicit, presupus);
    invalidă → V12 BLOCANT. Întoarce textul sau None (BLOCANT emis)."""
    g = inp.get("grupa_conexiuni", inp.get("pt_grupa_conexiuni"))
    if g is None:
        return norme.TRAFO_GRUPA_CONEXIUNI
    t = re.sub(r"[\s\-_]", "", str(g)).upper() if isinstance(g, str) else ""
    m = _GRUPA_RE.match(t)
    if not m or not 0 <= int(m.group(4)) <= 11:
        emite(j, "V12", BLOCANT, "schema", "camp", camp="grupa_conexiuni", valoare=g)
        j.verificari[-1]["remediere"] = "grupa de conexiuni din plăcuța trafo (ex. „Dyn11”, „Dyn5”, „Yzn11”)"
        return None
    txt = f"{m.group(1)}{m.group(2).lower()}{'n' if m.group(3) else ''}{int(m.group(4))}"
    if txt != norme.TRAFO_GRUPA_CONEXIUNI:
        j.pas(f"grupa de conexiuni {txt} (declarată) — pe planșă și în listă")
    return txt


def trafo_sursa(inp, j, sn, izolatie=None, n_t=1, paralel=False):
    """r10: transformatorul sursă cu uk declarat (dacă există) și, la n trafo identice în PARALEL pe aceeași bară JT,
    Zk = Z_Q + K_T·Z_T/n → Ik3max bară cu toate trafo în funcțiune (Ik1min rămâne cu un singur trafo, prudent).
    Întoarce dict-ul `sc.trafo` sau None (uk invalid → BLOCANT emis)."""
    uk = _uk_declarat(inp, j)
    if uk is False:
        return None
    t = sc.trafo(int(sn), inp.get("SkQ_MVA"), izolatie or "ulei", uk_pct=uk)
    if uk is not None:
        t["uk_declarat"] = True
        j.pas(f"uk = {fmt_ro(uk)} % declarat (plăcuța trafo) — folosit la Ik3 în locul valorii din tabel")
    if n_t > 1 and paralel:
        t = dict(t)
        t["Zk"] = (t["Z_Q"][0] + t["K_T"] * t["Z_T"][0] / n_t, t["Z_Q"][1] + t["K_T"] * t["Z_T"][1] / n_t)
        t["Ik3max_bara_kA"] = sc.ik3_din_z(t["Zk"])
        t["n_paralel"] = n_t
    return t


def n_trafo_sursa(inp, j, ce="PT-ul sursă"):
    """r10 (industrial i08 / i30, fotovoltaic #15): numărul de transformatoare ale PT-ului SURSĂ al unui tablou / al
    ramurii de rețea și regimul barei: (n, paralel) sau None (BLOCANT emis). `n_trafo` / `pt_n_trafo` (1…4);
    `cupla` „inchisa” → paralel (Ik cu toate trafo); „deschisa” sau `bara` „T1” / „T2” / „sectia 1” → un singur trafo
    pe bara de racord; nedeclarat → paralel (majorant pentru Icu), declarat în presupus. Niciun trafo nu se pierde tăcut."""
    n = inp.get("n_trafo", inp.get("pt_n_trafo"))
    if n is None:
        return 1, False
    if isinstance(n, bool) or not _numar(n) or n != int(n) or not 1 <= int(n) <= 4:
        emite(j, "V96", BLOCANT, "schema", ce=f"{ce} cu n_trafo = {n!r}",
              detaliu="motorul acoperă 1…4 transformatoare identice", remediere="n_trafo întreg 1…4 (câte trafo are "
                                                                              "postul), sau proiect de specialitate")
        return None
    n = int(n)
    if n == 1:
        return 1, False
    bara = inp.get("bara", inp.get("bara_racord"))
    cupla = _fd(inp.get("cupla")).lower() if isinstance(inp.get("cupla"), str) else None
    if bara is not None:
        b = _fd(str(bara)).lower().replace(" ", "").replace("_", "")
        mt = re.match(r"^(?:t|trafo|sectia|sectiunea|semibara|bara)?(\d)$", b)
        if not mt or not 1 <= int(mt.group(1)) <= n:
            emite(j, "V12", BLOCANT, "schema", "camp", camp="bara", valoare=bara)
            j.verificari[-1]["remediere"] = f"bara de racord „T1” … „T{n}” (secția de bare a trafo-ului) sau cupla „inchisa”"
            return None
        if cupla in _CUPLA_NI:
            j.presupune(f"racord pe bara T{mt.group(1)}, dar cupla e declarată închisă — Ik3 cu toate cele {n} trafo în "
                        f"paralel (majorant)")
            return n, True
        j.pas(f"{ce}: {n} trafo, racord pe bara JT a T{mt.group(1)} (cupla deschisă) — Ik3 doar din T{mt.group(1)}")
        return n, False
    if cupla in _CUPLA_NO:
        j.pas(f"{ce}: {n} trafo cu cupla normal deschisă — fiecare secție de bare are un singur trafo (Ik3 dintr-un trafo)")
        return n, False
    if cupla is not None and cupla not in _CUPLA_NI:
        emite(j, "V12", BLOCANT, "schema", "camp", camp="cupla", valoare=inp.get("cupla"))
        j.verificari[-1]["remediere"] = "cupla „inchisa” (trafo în paralel) sau „deschisa” (secții separate)"
        return None
    if cupla is None:
        j.presupune(f"{ce}: {n} trafo în paralel pe aceeași bară JT (cupla nedeclarată — majorant pentru Icu); cu cupla "
                    f"normal deschisă declarați cupla „deschisa” sau bara de racord („T1”)")
    return n, True


def dg_cerut(inp):
    """r12 (proiecte reale C / S, Top 15 #9): dispozitivul general (DG) al utilizatorului cu ÎNTRERUPTOR + 50/51/51N +
    TC + tor homopolar — cerut explicit (`dg_intreruptor: true`, ATR „dispozitiv general cu întrerupător”) sau implicit
    când OD-ul e E-Distribuție (norma lor), indiferent de pragul de 630 kVA."""
    if inp.get("dg_intreruptor") is not None:
        return bool(inp.get("dg_intreruptor"))
    od = _fd(inp.get("OD") or "") if isinstance(inp.get("OD"), str) else ""
    return od.replace("_", "").replace("-", "") in ("edistributie", "enel", "edistributiebanat", "edistributiemuntenia",
                                                    "edistributiedobrogea")


def _celula_trafo_inp(inp):
    """celula trafo impusă: declarată (`celula_trafo`) sau „intreruptor” când DG-ul cu întreruptor e cerut"""
    return inp.get("celula_trafo") or ("intreruptor" if dg_cerut(inp) else None)


def _celula_trafo(sn, fortat, j, u_kv=20):
    """SPEC §C.5 pct. 6: Sn ≤ 630 kVA → separator de sarcină + siguranțe MT; > 630 kVA → întreruptor + releu 50/51
    (DECIZIE proiectant 28.10.2026, Î10). Siguranțe impuse peste 630 kVA → V61 BLOCANT."""
    tip = fortat or ("sigurante" if sn <= norme.TRAFO_SN_MAX_SIGURANTE_MT_KVA else "intreruptor")
    if tip.startswith("sig"):
        if sn > norme.TRAFO_SN_MAX_SIGURANTE_MT_KVA:
            emite(j, "V61", BLOCANT, "schema", Sn=sn)
            return (f"separator de sarcină + siguranțe MT (nepermis peste {norme.TRAFO_SN_MAX_SIGURANTE_MT_KVA} kVA — "
                    f"întreruptor + releu 50/51)")
        return f"separator de sarcină + siguranțe MT {fmt_ro(norme.siguranta_mt(sn, u_kv))}{NB}A"
    return "intreruptor"


def tip_q_declarat(inp, *chei):
    """r9 (industrial #20): tipul aparatului general declarat („ACB 1600 A” → `Q_general_tip` / `aparat` / `Q_JT_tip`)
    — ACB / MCCB respectat (nu înlocuit cu MCCB după calibru)."""
    for k in chei or ("Q_general_tip", "Q_JT_tip", "aparat", "Q1_tip"):
        t = pr.normalizeaza_tip(inp.get(k)) if isinstance(inp.get(k), str) else None
        if t in ("ACB", "MCCB"):
            return t
    return None


def _q_trafo(in_t, ik3_kA, in_fortat=None, tip_fortat=None):
    """SPEC §C.5 pct. 3: Q JT cu Ip,min = In_T → MCCB (≤ 1600 A) sau ACB, Ir = treapta ≥ In_T; Icu ≥ Ik3 bara.
    r9: tipul declarat (ACB / MCCB) se respectă dacă seria lui are calibrul."""
    ref = in_fortat if in_fortat is not None else in_t
    tip = "MCCB" if ref <= 1600 + 1e-9 else "ACB"
    if tip_fortat in ("ACB", "MCCB") and (in_fortat is None or in_fortat in pr.SERII[tip_fortat]) and \
            pr.alege_calibru(tip_fortat, ref) is not None:
        tip = tip_fortat
    In = in_fortat if in_fortat is not None else pr.alege_calibru(tip, in_t)
    if In is None:
        return None
    prot = pr.construieste(tip, In, in_t, are_aval=True)
    prot["Icu_kA"], ok = pr.alege_icu(tip, ik3_kA)
    prot["icu_ok"] = ok
    return prot


def _celule_mt(c, j):
    """r5: `celule_mt` = {"linie": n, "masura": bool} sau listă ["linie", "linie", "masura", "trafo"] → {"linie": n ≥ 1,
    "masura": bool}. Nedeclarat: o celulă de linie (racord radial), presupus."""
    if c is None:
        j.presupune("o celulă MT de linie (racord radial) — celulele MT nedeclarate, conform ATR")
        return {"linie": 1, "masura": False}
    if isinstance(c, (list, tuple)):
        n = [_fd(x) for x in c if isinstance(x, str)]
        if len(n) != len(c) or any(x not in ("linie", "masura", "trafo", "linie_intrare", "linie_iesire") for x in n):
            emite(j, "V12", BLOCANT, "schema", "camp", camp="celule_mt", valoare=c)
            return None
        return {"linie": max(1, sum(1 for x in n if x.startswith("linie"))), "masura": "masura" in n}
    if isinstance(c, dict):
        nl = c.get("linie", 1)
        if not isinstance(nl, int) or isinstance(nl, bool) or nl < 1 or nl > 6:
            emite(j, "V12", BLOCANT, "schema", "camp", camp="celule_mt.linie", valoare=nl)
            return None
        return {"linie": nl, "masura": bool(c.get("masura"))}
    emite(j, "V12", BLOCANT, "schema", "camp", camp="celule_mt", valoare=c)
    return None


def _sectii_pt(plecari, inp, j):
    """r7 (#24, S12): PT cu 2 trafo — plecările pe cele două secții de bare JT. `sectie` (1 | 2) pe plecare; altfel
    `plecari_pe_sectie: true` (alias `plecari_pe_semibara`) = lista se repetă pe FIECARE secție („fiecare semibară cu 4
    plecări”, numerotare continuă); altfel prima jumătate pe secția 1, restul pe secția 2 (presupus)."""
    pl = [dict(p) for p in plecari]
    if any(p.get("sectie") in (1, 2) for p in pl):
        for p in pl:
            if p.get("sectie") not in (1, 2):
                p["sectie"] = 1
        return sorted(pl, key=lambda p: p["sectie"])
    if inp.get("plecari_pe_sectie") or inp.get("plecari_pe_semibara"):
        n = len(pl)
        dubl = []
        for i, p in enumerate(pl):
            q = copy.deepcopy(p)
            m = re.match(r"^(.*?)(\d+)$", str(p.get("nume") or ""))
            q["nume"] = f"{m.group(1)}{int(m.group(2)) + n}" if m else f"{p.get('nume') or 'Plecare'} (S2)"
            q["sectie"] = 2
            p["sectie"] = 1
            dubl.append(q)
        j.pas(f"PT 2 trafo: {n} plecări pe fiecare secție de bare → {2 * n} plecări")
        return pl + dubl
    h = (len(pl) + 1) // 2
    for i, p in enumerate(pl):
        p["sectie"] = 1 if i < h else 2
    if pl:
        j.presupune(f"plecările repartizate pe secțiile de bare: primele {h} pe secția 1 (T1), restul pe secția 2 (T2) — "
                    f"declarați `sectie` pe plecare")
    return pl


PTA_SN_MAX_KVA = 400      # r8: post aerian pe stâlp — un trafo ≤ 400 kVA (uzual ≤ 250 kVA)


def schema_pt(inp, j):
    """SPEC §C.5: trafo, celula trafo, Q JT, Ik3/Ik1 la bara TGJT, bilanț și plecări (origine „pt_propriu”)."""
    rez = {}
    if tensiune_jt_nesuportata(inp, j, inp.get("plecari")):
        return rez
    sn = inp.get("Sn_kVA")
    if sn is None or int(sn) not in norme.TRAFO:
        emite(j, "V05", BLOCANT, "schema", "trafo", Sn=sn, vecini=", ".join(str(s) for s in norme.TRAFO_SN_KVA))
        return rez
    sn = int(sn)
    # r6 (#29): tensiunea MT parametrică (6 / 10 / 15 / 20 kV); altă valoare → nesuportat, nu 20 kV tăcut
    u_mt = inp.get("U_MT_kV", 20)
    try:
        u_mt = float(u_mt)
        u_mt = int(u_mt) if u_mt == int(u_mt) else u_mt
    except (TypeError, ValueError):
        u_mt = None
    if u_mt not in norme.U_MT_UM_KV:
        emite(j, "V96", BLOCANT, "schema", ce=f"tensiune MT {inp.get('U_MT_kV')} kV",
              detaliu="motorul acoperă 6 / 10 / 15 / 20 kV (Um 7,2 / 12 / 17,5 / 24 kV)",
              remediere="U_MT_kV ∈ {6, 10, 15, 20} sau proiect de specialitate MT")
        return rez
    rez["U_MT_kV"], rez["Um_kV"] = u_mt, norme.U_MT_UM_KV[u_mt]
    if inp.get("U_MT_kV") is None:
        j.presupune("tensiunea MT 20 kV (nedeclarată) — 6 / 10 / 15 kV se declară (U_MT_kV)")
    # r6 (#24): doi transformatoare în paralel pe barele JT (n_trafo = 2); mai mulți → nesuportat
    n_t = inp.get("n_trafo", 1)
    if n_t not in (1, 2):
        emite(j, "V96", BLOCANT, "schema", ce=f"PT cu {n_t} transformatoare",
              detaliu="motorul acoperă 1 trafo sau 2 trafo identice în paralel pe barele JT",
              remediere="n_trafo 1 sau 2, sau proiect de specialitate")
        return rez
    izt = inp.get("trafo_izolatie") or "ulei"
    t = trafo_sursa(inp, j, sn, izt)
    if t is None:
        return rez
    grupa = grupa_conexiuni(inp, j)
    if grupa is None:
        return rez
    if inp.get("grupa_conexiuni") is None and inp.get("pt_grupa_conexiuni") is None:
        j.presupune(f"grupa de conexiuni {grupa} (nedeclarată) — se confirmă cu OD / plăcuța trafo (Dyn11 la unele OD)")
    cupla = None
    if n_t == 2:
        cupla = _fd(inp.get("cupla") or "deschisa")
        cupla = {"deschisa": "NO", "no": "NO", "normal_deschisa": "NO", "inchisa": "NI", "ni": "NI", "nc": "NI",
                 "normal_inchisa": "NI", "paralel": "NI"}.get(cupla)
        if cupla is None:
            emite(j, "V12", BLOCANT, "schema", "camp", camp="cupla", valoare=inp.get("cupla"))
            return rez
        if inp.get("cupla") is None:
            j.presupune("cupla longitudinală de bare JT normal DESCHISĂ (NO), cu interblocaj „2 din 3” (Q JT T1, Q JT T2, "
                        "QC — niciodată două trafo în paralel); fiecare trafo alimentează secția lui de bare — "
                        "cupla închisă se declară (cupla: „inchisa”)")
    aar = _bool(inp.get("aar"))
    if aar and n_t != 2:
        emite(j, "V96", BLOCANT, "schema", ce="AAR la un PT cu un singur transformator",
              detaliu="AAR-ul de cuplă comută între două secții de bare alimentate din două trafo — cu un trafo nu are "
                      "ce rezerva (rezerva cu GE: schema „ge_ats”)",
              remediere="n_trafo: 2, cupla: „deschisa”, aar: true — sau GE + ATS (tip „ge_ats”)")
        return rez
    if aar and cupla == "NI":
        _contradictie(j, BLOCANT, "schema", "AAR declarat pe o cuplă normal ÎNCHISĂ (trafo în paralel) — AAR-ul închide "
                                            "o cuplă normal deschisă la pierderea unei secții",
                      "cupla „deschisa” + aar: true (secții separate cu anclanșarea rezervei) sau cupla „inchisa” fără AAR")
        return rez
    if n_t == 2 and cupla == "NO":
        rez["n_trafo"] = 2
        rez["cupla"] = {"stare": "NO", "interblocaj": "2 din 3 (Q3.1, Q3.2, QC)"}
        rez["Ik3max_bara_kA"] = t["Ik3max_bara_kA"]
        j.pas(f"2 × {sn} kVA, cuplă longitudinală JT normal deschisă cu interblocaj 2 din 3: fiecare secție de bare e "
              f"alimentată de un singur trafo → Ik3max bară = {fmt_ro(t['Ik3max_bara_kA'])} kA (un trafo)")
        if aar:
            # r11 (industrial j05 / j57): AAR pe cupla JT — la dispariția tensiunii pe o secție, Q JT al trafo-ului
            # căzut deschide și QC închide (temporizat, cu blocare la defect pe bară); niciodată 3 din 3 închise
            rez["cupla"]["AAR"] = {
                "logica": "lipsă tensiune pe secția k (relee 27) → deschide Q3.k → închide QC (temporizat); revenire "
                          "manuală sau automată cu verificarea tensiunii",
                "blocare": "AAR blocat la declanșarea prin protecție (defect pe bară / plecare)",
                "interblocaj": "2 din 3: Q3.1, Q3.2, QC — trafo niciodată în paralel",
                "actionari": "Q3.1, Q3.2 și QC motorizate, cu bobine de deschidere / închidere"}
            j.pas("AAR pe cupla JT: relee de minimă tensiune 27 pe fiecare secție, Q3.1 / Q3.2 / QC motorizate, "
                  "interblocaj 2 din 3; la pierderea unui trafo, celălalt preia ambele secții (Ik3 bară rămâne cel al unui trafo)")
        elif inp.get("aar") is None:
            j.presupune("cupla JT normal deschisă FĂRĂ anclanșare automată a rezervei (AAR nedeclarat) — închiderea QC se "
                        "face manual, cu interblocaj 2 din 3; cu AAR declarați aar: true")
    if n_t == 2 and cupla == "NI":
        # paralel: Zk = Z_Q + K_T·Z_T/2 → Ik3max la bară (Icu); Ik1min cu un singur trafo în funcțiune (prudent)
        t = dict(t)
        zk2 = (t["Z_Q"][0] + t["K_T"] * t["Z_T"][0] / 2.0, t["Z_Q"][1] + t["K_T"] * t["Z_T"][1] / 2.0)
        t["Zk"] = zk2
        t["Ik3max_bara_kA"] = sc.ik3_din_z(zk2)
        rez["n_trafo"] = 2
        rez["cupla"] = {"stare": "NI", "interblocaj": "—"}
        rez["Ik3max_bara_kA"] = t["Ik3max_bara_kA"]
        j.pas(f"2 × {sn} kVA în paralel pe barele JT (aceeași grupă de conexiuni, uk egal): Ik3max bară = "
              f"{fmt_ro(t['Ik3max_bara_kA'])} kA (ambele în funcțiune); Ik1min cu un singur trafo; cuplă longitudinală "
              f"de bare normal închisă (declarată)")
    if inp.get("SkQ_MVA") is None:
        j.presupune("S\"kQ = 500 MVA, R/X = 0,1 (rețea MT, majorant)")
    if inp.get("trafo_izolatie") is None:
        j.presupune(f"trafo în ulei (izolația nedeclarată) — uk {fmt_ro(t['uk_pct'])} %"
                    + (" (declarat)" if t.get("uk_declarat") else "") + f", Pk {t['Pk_W']} W (Tier 2)")
    j.ipoteza("skq", t["SkQ_MVA"], inp.get("SkQ_MVA") is None)
    j.ipoteza("trafo", (t["uk_pct"], t["Pk_W"]), not t.get("uk_declarat"))
    rez["trafo"] = {"Sn_kVA": sn, "In_T_A": t["In_T_A"], "uk_pct": t["uk_pct"], "Pk_W": t["Pk_W"], "P0_W": t["P0_W"],
                    "izolatie": izt, "Ik3max_bara_kA": t["Ik3max_bara_kA"], "Ik1min_bara_A": t["Ik1min_bara_A"],
                    "grupa": grupa}
    if t.get("uk_declarat"):
        rez["trafo"]["uk_declarat"] = True
    # r5 (P1-12): celulele MT cerute explicit — celule de linie (intrare / intrare-ieșire în buclă) și celula de măsură
    cel_mt = _celule_mt(inp.get("celule_mt"), j)
    if cel_mt is None:
        return rez
    rez["celule_mt"] = cel_mt
    j.pas(f"Trafo {sn} kVA: In_T = {fmt_ro(t['In_T_A'])} A; uk {fmt_ro(t['uk_pct'])} %, Pk {t['Pk_W']} W; "
          f"Z_T = {fmt_ro(t['Z_T'][0] * 1000, 3)} + j{fmt_ro(t['Z_T'][1] * 1000, 3)} mΩ; K_T = {fmt_ro(t['K_T'], 4)}")
    j.pas(f"Ik3max bara TGJT = {fmt_ro(t['Ik3max_bara_kA'])} kA; Ik1min bara = {fmt_ro(t['Ik1min_bara_A'], 0)} A")
    rez["celula_trafo"] = _celula_trafo(sn, _celula_trafo_inp(inp), j, u_mt)
    if dg_cerut(inp):
        rez["dg"] = True            # r12: DG cu întreruptor + 50/51/51N + TC + tor homopolar (celulă proprie)
    for k_ in ("OD", "punct_conexiune", "compartimente"):
        if inp.get(k_) is not None:
            rez[k_] = inp[k_]
    if inp.get("pt_aerian"):
        # r8 (#21, S10): PTA pe stâlp — separator de exterior + siguranțe MT + trafo pe stâlp + cutie TDJT, fără celule
        rez["pt_aerian"] = True
        if n_t != 1 or sn > PTA_SN_MAX_KVA:
            emite(j, "V96", BLOCANT if n_t != 1 else AVERTISMENT, "schema",
                  ce=f"PTA pe stâlp {'cu 2 trafo' if n_t != 1 else f'de {sn} kVA'}",
                  detaliu=f"posturile aeriene pe stâlp au un singur trafo de cel mult {PTA_SN_MAX_KVA} kVA (masa pe stâlp)",
                  remediere="post în anvelopă (PTAB) sau trafo ≤ 400 kVA")
        j.pas(f"PTA pe stâlp: separator tripolar de exterior cu CLP, siguranțe fuzibile MT de exterior "
              f"{fmt_ro(norme.siguranta_mt(sn, u_mt))} A, trafo {sn} kVA pe platforma stâlpului, cutie TDJT la bază")
    if u_mt != 20:
        j.pas(f"MT {fmt_ro(u_mt)} kV: In_MT = {fmt_ro(sn / (SQRT3 * u_mt))} A; echipament MT Um {fmt_ro(norme.U_MT_UM_KV[u_mt])} kV")

    q = _q_trafo(t["In_T_A"], t["Ik3max_bara_kA"], inp.get("In_Q_JT_A"), tip_q_declarat(inp))
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

    plecari = list(inp.get("plecari") or [])
    if n_t == 2:
        plecari = _sectii_pt(plecari, inp, j)
    if not _plecare_compensare(inp, plecari, j, n_t * sn):
        return rez
    if n_t == 2 and plecari and plecari[-1].get("_compensare"):
        plecari[-1]["sectie"] = 1
    _nota_spl(rez, inp, "pt")
    if not plecari:
        emite(j, "V07", BLOCANT, "schema", "plecari", tablou="TGJT")
        return rez
    plecari_multiple_tacute(plecari, j)
    plecari = expandeaza_plecari(plecari)
    plecari = pregateste_ups(plecari, "tri", j)
    if plecari is None:
        return rez
    mod_sig = marcheaza_siguranta(plecari, inp, j, "TGJT")
    if mod_sig:
        rez["siguranta"] = mod_sig
    for pl in plecari:
        if rezerva_echipata(pl):
            # r12 (proiectul real C): rezervă echipată = doar aparatul (calibru), fără cablu și fără sarcină — nu intră
            # în bilanț (V62 fals); cablul de calcul e simbolic (1 m), nu se desenează
            pl["_echipata"] = True
            pl.setdefault("L_m", 1.0)
    pis = [0.0 if (pl.get("_rezerva") or pl.get("_echipata")) else _pi(pl, 0) for pl in plecari]
    spi = sum(pis)
    ks, ks_impl = _ks_bilant(inp, sum(1 for p_ in plecari if not p_.get("_compensare") and not p_.get("_echipata")))
    if ks_impl:
        j.presupune(f"ks = {fmt_ro(ks)} (IEC 61439-2 tab. 101, {len(plecari)} plecări)")
    j.ipoteza("ks", ks, ks_impl)
    pc = ks * spi
    scal = pc / 0.9
    rez["bilant"] = {"Pi_kW": spi, "ks": ks, "Pc_kW": pc, "Sc_kVA": scal}
    j.pas(f"Bilanț plecări: Σ Pi = {fmt_ro(spi)} kW, ks = {fmt_ro(ks)} → Pc = {fmt_ro(pc)} kW, Sc = {fmt_ro(scal)} kVA")
    if gt(scal, n_t * sn):
        # r8 (S5, #7): bilanțul din puteri DECLARATE (P_kW / S_kVA) peste Sn trafo = PT subdimensionat → BLOCANT;
        # plecările date doar prin calibru (In_A) sunt capacități, nu sarcini → AVERTISMENT (golden P05)
        p_decl = sum(p for pl, p in zip(plecari, pis) if pl.get("In_A") is None and not pl.get("_compensare"))
        emite(j, "V62", BLOCANT if gt(ks * p_decl / 0.9, n_t * sn) else AVERTISMENT, "schema", x=scal, y=n_t * sn)
    if n_t == 2:
        # r7 (#24): bilanțul pe fiecare secție de bare (cu cupla deschisă, fiecare trafo își poartă secția)
        rez["sectii"] = []
        for k in (1, 2):
            idx = [i for i, pl in enumerate(plecari) if pl.get("sectie") == k]
            ps = [pis[i] for i in idx]
            ks_k = inp.get("ks") if inp.get("ks") is not None else norme.ks_implicit(max(1, len(ps)))
            sc_k = float(ks_k) * sum(ps) / 0.9
            rez["sectii"].append({"sectie": k, "trafo": f"T{k}", "n_plecari": len(idx), "Pi_kW": sum(ps), "ks": ks_k,
                                  "Sc_kVA": sc_k})
            j.pas(f"Secția {k} (T{k}): {len(idx)} plecări, Σ Pi = {fmt_ro(sum(ps))} kW, ks = {fmt_ro(ks_k)} → Sc = "
                  f"{fmt_ro(sc_k)} kVA")
            if cupla == "NO" and gt(sc_k, sn):
                emite(j, "V62", AVERTISMENT, "schema", x=sc_k, y=sn)
                j.verificari[-1]["mesaj"] = (f"secția {k}: Sc = {fmt_ro(sc_k)} kVA > Sn T{k} = {sn} kVA (cupla normal "
                                             f"deschisă — fiecare trafo își poartă secția)")
        if aar and cupla == "NO" and gt(scal, sn):
            # r11: în regim AAR un singur trafo alimentează ambele secții
            emite(j, "V62", AVERTISMENT, "schema", x=scal, y=sn)
            j.verificari[-1]["mesaj"] = (f"regim AAR (un trafo pe ambele secții): Sc total = {fmt_ro(scal)} kVA > Sn = "
                                         f"{sn} kVA — descărcarea automată a consumatorilor nevitali la închiderea QC")
            j.verificari[-1]["remediere"] = ("deconectarea automată a plecărilor nevitale la comanda AAR (declarați-le) sau "
                                             "trafo dimensionate fiecare pe toată sarcina")
    # C.5 pct. 7 (v1.2, C5): punctul de măsură și serviciile proprii sunt GENERATE în rezultat (și desenate)
    loc = str(inp.get("masura_pt") or inp.get("masura") or ("MT" if (cel_mt.get("masura") or n_t == 2) else "JT")).upper()
    if inp.get("masura_pt") is None and inp.get("masura") is None and not cel_mt.get("masura"):
        j.presupune("punctul de măsură pe MT (2 trafo — o singură măsură comună) — nedeclarat; conform ATR"
                    if n_t == 2 else "punctul de măsură în JT (TC + contor semidirect) — nedeclarat; conform ATR")
    cel_mt["masura"] = loc == "MT"
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
    sp_gen = not any("servicii proprii" in (pl.get("nume") or "").lower() for pl in plecari) and not inp.get("pt_aerian")
    if sp_gen:
        j.presupune(f"servicii proprii PT: plecare {norme.PT_SERVICII_PROPRII_A} A, L = 10 m (iluminat, prize, încălzire în post)")
    elemente = ["neutrul trafo legat la priza de pământ comună MT/JT", "descărcătoare ZnO 24 kV"] + (
        ["servicii proprii PT"] if sp_gen else []) + [
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
    if n_t == 2:
        it = iter(pl.get("sectie", 1) for pl in plecari)
        for z in rez["plecari"]:
            if int(z.get("nivel") or 0) == 0:
                z["sectie"] = next(it, 1)
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
    ik3 = next((inp.get(k) for k in ("Ik3_TG_kA", "Ik3_sursa_kA", "Ik3_bara_kA") if inp.get(k) is not None), None)
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
    # r12: reglajele declarate ale Q-ului de racord (Ir / Isd, declanșator electronic)
    dcl = inp.get("racord_decl")
    dcl = "EL" if isinstance(dcl, str) and _fd(dcl) in ("el", "electronic", "lsi") else (
        "TM" if isinstance(dcl, str) and _fd(dcl) in ("tm", "termomagnetic") else None)
    ir_r = _reglaj(inp.get("racord_Ir_A"), rin) if tip in ("MCCB", "ACB") else None
    if ir_r is not None and not (0.4 * rin - 1e-6 <= ir_r <= rin + 1e-6):
        emite(j, "V12", BLOCANT, "Q TG", "camp", camp="racord_Ir_A", valoare=f"{fmt_ro(ir_r)} A (In {rin} A)")
        return None
    isd_r = inp.get("racord_Isd_A") if tip in ("MCCB", "ACB") else None
    if isd_r is not None:
        dcl = "EL"
        isd_r = _reglaj(isd_r, ir_r or rin)
    q = pr.construieste(tip, rin, rin, "C" if tip == "MCB" else None, are_aval=True, decl=dcl, ir=ir_r, isd=isd_r)
    if q.get("decl") == "EL":
        # v1.9: Q TG cu declanșator electronic (In > 630 A) — Isd ales ca la QG (altfel Ia(5 s) nedefinit)
        pr.alege_isd(q, sc.ik1_din_zb(ctx["Zb"]))
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


def _q_plecare_pt_existent(inp, j, ctx, qg, s_iac):
    """r9 (fotovoltaic #41, #42): plecarea nouă a CEF din tabloul JT al PT-ului existent — Q_PT la capătul sursă al C0.
    Declarat (`racord_In_Q_A`, `racord_Q_tip`) → verificat ca protecția din TG existent; altfel ales: MCCB / ACB cu
    Ir = cea mai mică treaptă ≥ Ir QG (reglajele cresc spre sursă), Icu ≥ Ik3 bara JT a PT-ului."""
    if inp.get("racord_In_Q_A") is not None:
        return _q_tg_existent(inp, j, ctx, s_iac)
    if inp.get("racord_Ir_A") is not None or inp.get("racord_Isd_A") is not None:
        j.presupune("racord_Ir_A / racord_Isd_A fără racord_In_Q_A — reglajele se aplică numai Q-ului de racord declarat")
    tinta = max(float(qg["In_A"]), pr.ip(qg), s_iac)     # ≥ orice reglaj al QG (Ir ≤ In QG)
    tip = "MCCB" if tinta <= 1600 + 1e-9 else "ACB"
    ales = None
    for In in [x for x in pr.SERII[tip] if ge(x, tinta)] or []:
        trepte = norme.IR_TREPTE["MCCB_TM"] if pr.declansator(tip, In) == "TM" else norme.IR_TREPTE["MCCB_EL"]
        k = next((k for k in trepte if ge(k * In, tinta)), None)
        if k is not None:
            ales = (In, k)
            break
    if ales is None:
        return None
    q = pr.construieste(tip, ales[0], ales[1] * ales[0], are_aval=True)
    q["Icu_kA"], ok = pr.alege_icu(tip, ctx["Ik3_kA"])
    if q.get("decl") == "EL":
        pr.alege_isd(q, sc.ik1_din_zb(ctx["Zb"]))
    if not ok:
        emite(j, "V33", BLOCANT, "Q PT", icu=q["Icu_kA"], ik3=ctx["Ik3_kA"])
    j.pas(f"PT existent: plecare nouă în tabloul JT al PT-ului — Q PT {tip} {q['In_A']} A, Ir {fmt_ro(q['Ir_A'])} A "
          f"≥ Ir QG {fmt_ro(pr.ip(qg))} A, Icu {fmt_ro(q['Icu_kA'])} kA ≥ Ik3 bară {fmt_ro(ctx['Ik3_kA'])} kA")
    j.presupune("plecare nouă în tabloul JT al PT-ului existent (Q PT nou, loc de rezervă în tablou) — de confirmat la "
                "releveu; protecția C0 la capătul sursă")
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


INVERTOR_IMPLICIT_PN_MAX_KW = 100.0     # E2 (D4): invertorul de șir trifazat uzual la CEF comerciale (100 kW)


def propunere_limitare_pcc(sn_kva):
    """E2: limita propusă la PCC = Sn trafo × cosφ_PCC × factor [kW] (rotunjită în jos la 5 kW)"""
    v = sn_kva * norme.PCC_COSFI * norme.PCC_FACTOR
    return float(math.floor(v / 5.0 + 1e-9) * 5)


def _v67_pcc(inp, j, rez, sn_tot, s_nec, obiect="schema", varianta="", fractie=1.0, **kw):
    """E2 (decizia proprietarului): Sn trafo < S invertoare+PCS → BLOCANT (V67) fără limitare; cu `limitare_PCC_kW`
    care aduce S la PCC ≤ Sn → AVERTISMENT explicit (nu BLOCANT). Propunerea automată: Sn × cosφ × factor."""
    prop = propunere_limitare_pcc(sn_tot)
    lim = inp.get("limitare_PCC_kW")
    lim = float(lim) * fractie if isinstance(lim, (int, float)) and not isinstance(lim, bool) and lim > 0 else None
    info = {"Sn_kVA": sn_tot, "S_necesar_kVA": s_nec, "propunere_kW": prop, "cosfi": norme.PCC_COSFI,
            "factor": norme.PCC_FACTOR, "formula": f"Sn × cosφ × factor = {fmt_ro(sn_tot, 0)} × "
                                                  f"{fmt_ro(norme.PCC_COSFI)} × {fmt_ro(norme.PCC_FACTOR)}"}
    if lim is not None:
        s_lim = lim / norme.PCC_COSFI
        info.update(P_kW=lim, S_kVA=s_lim, aplicata=not gt(s_lim, sn_tot))
        if info["aplicata"]:
            emite(j, "V67", AVERTISMENT, obiect, "pcc", x=round(sn_tot), y=round(s_nec, 1), P=fmt_ro(lim),
                  S=fmt_ro(s_lim, 1))
            j.verificari[-1]["remediere"] = (
                "confirmați limitarea cu ATR-ul (puterea aprobată la PCC); EMS / controller de putere cu funcție "
                "fail-safe (la pierderea comunicației: reducerea invertoarelor la puterea limitată sau deconectare), "
                "TC + analizor de rețea la PCC; protecția trafo la suprasarcină rămâne activă")
        else:
            emite(j, "V67", BLOCANT, obiect, "pcc_insuf", x=round(sn_tot), y=round(s_nec, 1), P=fmt_ro(lim),
                  S=fmt_ro(s_lim, 1))
            j.verificari[-1]["remediere"] = (f"limitarea la PCC ≤ {fmt_ro(prop)} kW (Sn × cosφ × factor) sau un "
                                             f"transformator cu Sn ≥ {fmt_ro(s_nec, 0)} kVA")
            j.verificari[-1]["propunere"] = {"camp": "limitare_PCC_kW", "valoare": prop}
    else:
        emite(j, "V67", BLOCANT, obiect, varianta, x=kw.pop("x", round(sn_tot)), y=round(s_nec, 1), **kw)
        j.verificari[-1]["remediere"] += (f"; sau limitarea puterii la punctul de racord (limitare_PCC_kW, propus "
                                          f"{fmt_ro(prop)} kW = {info['formula']}) cu EMS / controller de putere, "
                                          f"TC + analizor la PCC")
        j.verificari[-1]["propunere"] = {"camp": "limitare_PCC_kW", "valoare": prop}
    lst = rez.setdefault("limitare_PCC", {})
    if obiect == "schema":
        lst.update(info)
    else:
        lst.setdefault("sectii", {})[obiect] = info
    return info


def invertoare_implicite(inp, j):
    """E2 (D4, decizia proprietarului): CEF cu putere în kW (`Pn_total_kW`) fără invertoare declarate → Pn c.a. =
    puterea declarată, cu invertoare de tip implicit (n = ⌈P / 100 kW⌉, egale), marcate „presupus” — nu întrebare
    blocantă. Returnează lista creată sau None."""
    if inp.get("invertoare") or isinstance(inp.get("bess"), dict) and not inp.get("Pn_total_kW"):
        return None
    try:
        p = float(inp.get("Pn_total_kW") or 0)
    except (TypeError, ValueError):
        return None
    if not gt(p, 0.0):
        return None
    n = max(1, math.ceil(p / INVERTOR_IMPLICIT_PN_MAX_KW - 1e-9))
    pn = round(p / n, 3)
    inp["invertoare"] = [{"n": n, "Pn_kW": pn, "presupus": True}]
    j.presupune(f"CEF {fmt_ro(p)} kW fără invertoare declarate → {n} × {fmt_ro(pn)} kW c.a., invertor de tip implicit "
                f"(trifazat, fără fișă: Iac,max = 1,1·Pn/(√3·U)) — confirmați numărul, puterea și modelul")
    return inp["invertoare"]


def _putere_declarata(inp, j, s_inv):
    """v1.9 (R5 P1-14): contradicția dintre Σ invertoare (n × Pn) și puterea totală declarată (`Pn_total_kW`) →
    V91 AVERTISMENT (se calculează cu lista invertoarelor); la monofazat, un grup declarat trifazat → V91."""
    tot = inp.get("Pn_total_kW")
    if tot is not None and s_inv > 0 and abs(float(tot) - s_inv) > 0.01 * max(float(tot), s_inv):
        emite(j, "V91", AVERTISMENT, "schema", x=round(s_inv, 2), y=float(tot))
    if inp.get("retea") == "mono":
        tri = [g for g in inp.get("invertoare") or [] if isinstance(g, dict) and str(g.get("retea") or "").startswith("tri")]
        if tri:
            emite(j, "V91", AVERTISMENT, "schema", "monofazat", detaliu=f"{len(tri)} grup(uri) de invertoare declarate trifazate")


def _retea_grup(g):
    """r8 (fotovoltaic P0-5): rețeaua unui grup de invertoare — `retea` declarată pe grup > catalogul modelului
    (Fronius Primo …-1, SMA Sunny Boy, Huawei SUN2000-…-L1, Growatt MIN … = „mono”). None = nedeterminată."""
    if not isinstance(g, dict):
        return None
    r = g.get("retea")
    if isinstance(r, str) and r.strip():
        return RETELE.get(_fd(r), r.strip().lower())
    return cat_inv.retea(g.get("producator"), g.get("model"))


FAZE = ("L1", "L2", "L3")


def _repartitie_faze(unitati, j, obiect="schema"):
    """r8 (fotovoltaic P0-5): invertoarele / PCS monofazate (`u["retea"] == "mono"`) pe o rețea trifazată — fiecare pe
    o fază (L1 / L2 / L3). Faza declarată (`invertoare[].faza`: „L2” sau listă pe unități) se respectă; restul se
    repartizează automat pe faza cea mai puțin încărcată (puterile mari întâi). Curentul pe fază = Σ Iac trifazate +
    Σ Iac monofazate de pe fază. Dezechilibrul (S max − S min pe fază, al generării monofazate) > 16 A ≈ 3,68 kVA → V71
    AVERTISMENT (Ord. ANRE 228/2018 art. 12(3), norme.DEZECHILIBRU_FAZE_MAX_KVA). Întoarce {L1: A, L2: A, L3: A} sau None (fără mono)."""
    mono = [u for u in unitati if u.get("retea") == "mono"]
    if not mono:
        return None
    s_f = {f: 0.0 for f in FAZE}
    decl_idx = {}
    libere = []
    for u in mono:
        g = u.get("grup") or {}
        fz = g.get("faza")
        k = decl_idx.get(id(g), 0)
        if isinstance(fz, (list, tuple)):
            fz = fz[k] if k < len(fz) else None
        decl_idx[id(g)] = k + 1
        fz = str(fz).strip().upper() if fz else None
        if fz in FAZE:
            u["faza"] = fz
            u["faza_declarata"] = True
            s_f[fz] += u["Iac"] * norme.u_0() / 1000.0
        else:
            libere.append(u)
    for u in sorted(libere, key=lambda x: -x["Iac"]):
        fz = min(FAZE, key=lambda f: (round(s_f[f], 6), FAZE.index(f)))
        u["faza"] = fz
        s_f[fz] += u["Iac"] * norme.u_0() / 1000.0
    i_tri = sum(u["Iac"] for u in unitati if u.get("retea") != "mono")
    i_f = {f: i_tri + sum(u["Iac"] for u in mono if u["faza"] == f) for f in FAZE}
    dez = max(s_f.values()) - min(s_f.values())
    det = " / ".join(f"{f} {fmt_ro(s_f[f])} kVA" for f in FAZE)
    rep = "; ".join(f"{f}: " + (", ".join(u["obiect"] for u in mono if u["faza"] == f) or "—") for f in FAZE)
    j.pas(f"Invertoare monofazate pe rețea trifazată (1 × 230 V, Iac = 1,1·Pn/230): {rep} → S monofazat pe faze {det}; "
          f"curent pe fază {' / '.join(f'{f} {fmt_ro(i_f[f])} A' for f in FAZE)}")
    if gt(dez, norme.DEZECHILIBRU_FAZE_MAX_KVA):
        emite(j, "V71", AVERTISMENT, obiect, "dezechilibru", det=det, d=round(dez, 2), lim=norme.DEZECHILIBRU_FAZE_MAX_KVA)
        j.verificari[-1]["remediere"] = ("repartizați invertoarele monofazate egal pe L1 / L2 / L3 (invertoare[].faza), "
                                         "invertor trifazat sau acordul OD în ATR pentru dezechilibru")
    else:
        emite(j, "V71", INFO, obiect, "faze", det=det, d=round(dez, 2), lim=norme.DEZECHILIBRU_FAZE_MAX_KVA)
    if not any(u.get("faza_declarata") for u in mono):
        j.presupune(f"invertoarele monofazate repartizate automat pe faze ({rep}) — declarați faza fiecăruia dacă e alta")
    return i_f


def _bess_normalizeaza(b, j):
    """r8 (fotovoltaic P1, BESS): completează `bess` din cod și din cantități —
    * kWh = n_module × kWh_modul (`n_module` / `n_baterii` × `kWh_modul` sau capacitatea modulului din cod: BOS-G 5,12,
      LUNA2000-5-S0 …); contradicție cu kWh declarat → V91 AVERTISMENT (se folosește produsul);
    * sistem cu PCS propriu recunoscut din cod (LUNA2000-200KWH-2H1 = 200 kWh, „2H” = 2 ore → PCS 100 kW);
    * `n_pcs` PCS identice: P total = n_pcs × pcs.Pn_kW (sau P_kW total / n_pcs). Întoarce numărul de PCS."""
    if not isinstance(b, dict):
        return 1
    bat = b.get("baterie") if isinstance(b.get("baterie"), dict) else {}
    n_mod = b.get("n_module", b.get("n_baterii", bat.get("n")))
    kwh_m = b.get("kWh_modul") or (bat.get("kWh") if b.get("baterie") is not None and n_mod else None) or \
        cat_inv.kwh_modul(b.get("producator"), b.get("model")) or cat_inv.kwh_modul(bat.get("producator"), bat.get("model"))
    if n_mod and kwh_m and not isinstance(n_mod, bool):
        tot = float(n_mod) * float(kwh_m)
        if b.get("kWh") is not None and abs(float(b["kWh"]) - tot) > 0.01 * tot and abs(float(b["kWh"]) - float(kwh_m)) > 1e-6:
            emite(j, "V91", AVERTISMENT, "BESS", "bess_kwh", x=round(tot, 2), y=float(b["kWh"]), n=int(n_mod), k=float(kwh_m))
        elif b.get("kWh") is None or abs(float(b["kWh"]) - float(kwh_m)) <= 1e-6:
            j.presupune(f"capacitate baterie = {int(n_mod)} × {fmt_ro(float(kwh_m))} kWh = {fmt_ro(tot)} kWh")
        b["kWh"] = round(tot, 3)
    cod = cat_inv.bess_din_cod(b.get("producator"), b.get("model"))
    if cod:
        if b.get("kWh") is None:
            b["kWh"] = cod["kWh"]
            j.presupune(f"BESS {b.get('model')}: {fmt_ro(cod['kWh'])} kWh din codul modelului — confirmați cu fișa")
        if b.get("P_kW") is None and not (isinstance(b.get("pcs"), dict) and b["pcs"].get("Pn_kW")) and cod.get("P_kW"):
            b["P_kW"] = cod["P_kW"] * (int(b["n_pcs"]) if b.get("n_pcs") else 1)
            j.presupune(f"BESS {b.get('model')}: PCS {fmt_ro(cod['P_kW'])} kW din codul modelului (durata de descărcare din "
                        f"cod) — confirmați cu fișa")
    n_pcs = b.get("n_pcs") or ((b.get("pcs") or {}).get("n") if isinstance(b.get("pcs"), dict) else None) or 1
    try:
        n_pcs = max(1, int(n_pcs))
    except (TypeError, ValueError):
        n_pcs = 1
    p_u = (b.get("pcs") or {}).get("Pn_kW") if isinstance(b.get("pcs"), dict) else None
    if p_u is not None:
        tot = n_pcs * float(p_u)
        if b.get("P_kW") is not None and abs(float(b["P_kW"]) - tot) > 0.01 * tot and not (n_pcs > 1 and abs(float(b["P_kW"]) - float(p_u)) < 1e-6):
            emite(j, "V91", AVERTISMENT, "BESS", "bess_pcs", x=round(tot, 2), y=float(b["P_kW"]), n=n_pcs, k=float(p_u))
        b["P_kW"] = tot
    return n_pcs


def _spd_ca_invertor(j, obiect, rr, fisa):
    """v1.9 (R5 P1-11, SR HD 60364-7-712 art. 712.534): SPD c.a. tip 2 și la capătul invertorului / PCS când cablul
    invertor → tablou > 10 m (`norme.SPD_CA_INVERTOR_L_M`) sau când fișa îl cere (`spd_ca: true`; `false` = exclus)."""
    if rr.get("blocat"):
        return
    res = rr["rezultat"]
    impus = (fisa or {}).get("spd_ca") if isinstance(fisa, dict) else None
    L = res.get("L_m")
    if impus is False:
        return
    if impus or (L is not None and gt(float(L), norme.SPD_CA_INVERTOR_L_M)):
        res["SPD_ca_invertor"] = {"tip": "T2", "motiv": "cerut de fișă" if impus else
                                  f"cablu {fmt_ro(L, 0)} m > {fmt_ro(norme.SPD_CA_INVERTOR_L_M, 0)} m"}
        j.pas(f"{obiect}: SPD c.a. tip 2 la bornele invertorului ({res['SPD_ca_invertor']['motiv']}, SR HD 60364-7-712)")


def _ddr_invertor_mare(j, u, res):
    """v1.9 (R5 P0-6): un DDR de 30 mA pe un invertor > 30 kW declanșează la curentul capacitiv de scurgere al câmpului
    PV — V73 AVERTISMENT (IΔn ≥ 100 mA conform fișei / ATR)."""
    d = (res or {}).get("DDR")
    if d and not u.get("pcs") and gt(u["Pn_kW"], norme.DDR_INVERTOR_30MA_MAX_KW) and d.get("IdN_mA", 0) < norme.DDR_INVERTOR_IDN_MARE_MA:
        emite(j, "V73", AVERTISMENT, u["obiect"], "mare", P=u["Pn_kW"], IdN=d["IdN_mA"])


def _limitare_injectie(inp, j, rez, pn_tot, n, retea):
    """v1.9 (R5 P1-10): limitarea injecției (`limitare_injectie_kW`, 0 = injecție zero): analizor / contor de control
    cu TC la punctul de racord (PCC) + controller EMS cu legătura de comandă spre invertoare / PCS (V92)."""
    v = inp.get("limitare_injectie_kW")
    if v is None:
        return None
    v = float(v)
    zero = not gt(v, 0.0)
    i_inj = v * 1000.0 / u_calcul(retea)
    rez["limitare_injectie"] = {"P_kW": v, "zero": zero, "I_inj_A": i_inj, "n_comandate": n}
    pa = inp.get("P_evacuata_kW")
    if zero and pa is not None and gt(float(pa), 0.0):
        # r7 (P1): injecție zero și putere evacuată > 0 în ATR — contradicție de intenție, nu se rezolvă tacit
        emite(j, "V92", AVERTISMENT, "schema", "zero_aprobat", y=float(pa))
    if not zero and ge(v, pn_tot):
        emite(j, "V92", AVERTISMENT, "schema", "fara_efect", P=v, Pn=pn_tot)
    else:
        emite(j, "V92", INFO, "schema", P=v, z=" (injecție zero)" if zero else "", n=n,
              ce="invertor / PCS" if n == 1 else "invertoare / PCS")
    return rez["limitare_injectie"]


def _contradictie(j, nivel, obiect, detaliu, remediere):
    """r7: date contradictorii (V12 „contradictie”) cu remedierea proprie, nu cea generică a V12"""
    emite(j, "V12", nivel, obiect, "contradictie", detaliu=detaliu)
    if nivel != INFO:
        j.verificari[-1]["remediere"] = remediere


def _u_ca_cef(inp, j):
    """r7 (fotovoltaic P0-3): tensiunea c.a. de racord a invertoarelor / PCS ale CEF — `U_ca_V` (alias `U_inv_ca_V`,
    `U_JT_V`) declarată > `invertoare[].U_ca_V` > catalogul de modele (SG…HX, SUN2000-…KTL-H… = 800 V). Implicit 400 V.
    Completează și `Umax_dc_V` al grupurilor din catalog (1500 V c.c. la invertoarele de 800 V). None = schema se oprește."""
    decl = next((inp.get(k) for k in ("U_ca_V", "U_inv_ca_V", "U_JT_V") if inp.get(k) is not None), None)
    cunoscute = {}
    for i, g in enumerate(inp.get("invertoare") or []):
        if not isinstance(g, dict):
            continue
        mc = cat_inv.cauta(g.get("producator"), g.get("model")) or {}
        if g.get("Umax_dc_V") is None and mc.get("Umax_dc_V"):
            g["Umax_dc_V"] = mc["Umax_dc_V"]
        u = g.get("U_ca_V") or mc.get("U_ca_V") or (400 if mc else None)
        if u is not None:
            cunoscute[i] = u
    if decl is not None:
        try:
            decl = float(decl)
            decl = int(decl) if decl == int(decl) else decl
        except (TypeError, ValueError):
            decl = None
        if decl not in norme.U_CA_INVERTOR_V:
            emite(j, "V96", BLOCANT, "schema", ce=f"tensiune c.a. a invertoarelor {inp.get('U_ca_V') or inp.get('U_inv_ca_V') or inp.get('U_JT_V')} V",
                  detaliu="motorul acoperă 3 × 400/230 V și 3 × 800 V (trafo 20/0,8 kV)",
                  remediere="U_ca_V 400 sau 800, sau proiect de specialitate")
            return None
        alt = sorted({int(u) for u in cunoscute.values() if int(u) != decl})
        if alt and len({int(u) for u in cunoscute.values()}) > 1:
            _mix_400_800(inp, j, cunoscute)
            return None
        if alt:
            _contradictie(j, BLOCANT, "schema", f"U c.a. declarată {decl} V, dar invertoarele din catalog / fișă sunt de "
                          f"{', '.join(str(u) for u in alt)} V c.a.", "corectați U_ca_V sau modelele invertoarelor")
            return None
        return decl
    us = sorted({int(u) for u in cunoscute.values()})
    if len(us) > 1:
        _mix_400_800(inp, j, cunoscute)
        return None
    u = us[0] if us else 400
    if u == 800:
        j.presupune("invertoare de 800 V c.a. (3 fire, fără N) din catalogul modelului — trafo 20/0,8 kV, cabluri 3 + PE, "
                    "aparataj pentru Ue ≥ 800 V c.a. — confirmați cu fișa tehnică")
    return u


def _mix_400_800(inp, j, cunoscute):
    """r8 (P1): invertoare de 800 V c.a. (fără N) și de 400 V c.a. în aceeași CEF — un trafo cu o singură înfășurare JT
    nu le poate alimenta pe amândouă: BLOCANT cu mesaj explicit (grupurile pe tensiuni) și remedierea proiectantului."""
    gr = [g for g in inp.get("invertoare") or [] if isinstance(g, dict)]
    pe_u = {}
    for i, u in cunoscute.items():
        g = gr[i] if i < len(gr) else {}
        pe_u.setdefault(int(u), []).append(f"{int(g.get('n', 1))} × {g.get('model') or fmt_ro(g.get('Pn_kW')) + ' kW'}")
    det = "; ".join(f"{u} V c.a.: {', '.join(v)}" for u, v in sorted(pe_u.items(), reverse=True))
    sn = inp.get("pt_Sn_kVA")
    _contradictie(j, BLOCANT, "schema", f"invertoare de 800 V și de 400 V c.a. pe același trafo / aceeași bară TGD-CF ({det}) "
                  f"— {'trafo-ul de ' + str(sn) + ' kVA are' if sn else 'o bară JT are'} o singură tensiune JT",
                  "trafo cu două înfășurări JT (20/0,8/0,4 kV) sau trafo separate (20/0,8 kV pentru invertoarele de 800 V, "
                  "20/0,4 kV pentru cele de 400 V — câte o schemă), ori invertoare de aceeași tensiune")


def schema_cef(inp, j):
    """SPEC §C.3 + r7: tensiunea c.a. a invertoarelor (400 V sau 800 V) → calculul CEF la tensiunea respectivă."""
    u = _u_ca_cef(inp, j)
    if u is None:
        return {}
    if u == 400:
        return _schema_cef(inp, j)
    # r7 (P0-3): invertoare de 800 V c.a. — numai cu trafo propriu 20/0,8 kV (nu într-un TG / BMPT / PT de 0,4 kV)
    if inp.get("retea") == "mono":
        _contradictie(j, BLOCANT, "schema", "invertoare trifazate de 800 V c.a. pe o rețea monofazată",
                      "rețea trifazată cu trafo propriu 20/0,8 kV")
        return {}
    pt_existent = _bool(inp.get("pt_existent"))
    u_decl = next((inp.get(k) for k in ("U_ca_V", "U_inv_ca_V", "U_JT_V") if inp.get(k) is not None), None)
    if inp.get("pt_Sn_kVA") is None or inp.get("racord") in ("tg_existent", "bmpt") or \
            ((pt_existent or inp.get("racord") == "tg_existent") and u_decl is None):
        _contradictie(j, BLOCANT, "schema", "invertoarele de 800 V c.a. (fără N) nu se pot racorda la o bară de 0,4 kV "
                      "(TG existent / BMPT / PT existent 20/0,4 kV)",
                      "PT propriu nou cu trafo 20/0,8 kV (pt_Sn_kVA, pt_existent false) sau invertoare de 400 V")
        return {}
    with norme.tensiune_jt(u):
        rez = _schema_cef(inp, j)
    rez["U_ca_V"] = u
    return rez


def _fara_neutru(res):
    """r7 (P0-3): ramură la 800 V c.a. — 3 conductoare de fază + PE, fără N (invertoarele de 800 V nu au neutru)"""
    if not res or not res.get("S_faza_mm2"):
        return
    res["fara_N"] = True
    res["S_N_mm2"] = None
    res["cablu"] = text_cablu(res["material"], res["izolatie"], res["metoda"], res.get("n_paralel") or 1,
                              res["S_faza_mm2"], None, res.get("S_PE_mm2"), res.get("PE") or "cablu", "tri",
                              monopolar=bool(res.get("monopolar")), fara_N=True)


TGD_CF_MAX = 2        # r11: tablouri TGD-CF desenate de motor (fiecare cu QG și C0 proprii); mai multe → V96


def normalizeaza_cascada(inp):
    """r12 (proiecte reale, cascade CEF): `tablouri_intermediare` [{nume, L_m, cablu, prot_tip, In_A, Ir_A, Icu_kA,
    invertoare?}] — tablourile intermediare / TE secundare, fiecare cu invertoarele lui și plecarea proprie spre TEG-ul
    de interfață comun (QG + PI + măsură). Invertoarele se leagă prin `invertoare[].tablou` (1…N; 0 = direct pe TEG)
    sau se scriu în tabloul lor (`tablouri_intermediare[k].invertoare`, mutate aici în lista globală). `n_tgd_cf` > 2
    (alias, r11) = N tablouri intermediare, cu `invertoare[].tgd` → `tablou`. Modifică `inp` (copie) pe loc."""
    if not isinstance(inp, dict):
        return inp
    te = inp.get("tablouri_intermediare")
    n = inp.get("n_tgd_cf")
    if te is None and _numar(n) and not isinstance(n, bool) and n == int(n) and int(n) > TGD_CF_MAX:
        te = inp["tablouri_intermediare"] = [{} for _ in range(int(n))]
        inp.pop("n_tgd_cf")
        for g in inp.get("invertoare") or []:
            if isinstance(g, dict) and "tgd" in g and "tablou" not in g:
                g["tablou"] = g.pop("tgd")
        if isinstance(inp.get("bess"), dict) and "tgd" in inp["bess"]:
            inp["bess"]["tablou"] = inp["bess"].pop("tgd")
    if _numar(te) and not isinstance(te, bool) and te == int(te) and int(te) >= 1:
        te = inp["tablouri_intermediare"] = [{} for _ in range(int(te))]
    if isinstance(te, list):
        inv = list(inp.get("invertoare") or [])
        for k, t in enumerate(te, 1):
            if isinstance(t, dict) and isinstance(t.get("invertoare"), list):
                for g in t["invertoare"]:
                    inv.append(dict(g, tablou=k) if isinstance(g, dict) else g)
                te[k - 1] = {kk: v for kk, v in t.items() if kk != "invertoare"}
        inp["invertoare"] = inv
    return inp


def _c0_tronsoane(inp, j, r0, tr, ctx_s, oc0, q_tg, tg):
    """r12 (proiecte reale, G): C0 compus din mai multe tronsoane (`cablu_C0.tronsoane` [{material, S_fortat, n_fortat,
    izolatie, metoda, tip_cablu, L}], listate de la tabloul CEF spre punctul de racord) — fiecare tronson cu Iz', ΔU
    și Ik la capăt; protecția (QG / Q racord) e aceeași pe tot traseul, deconectarea se verifică la capătul fiecărui
    tronson. Calculul merge de la sursă (punctul de racord) spre tablou. Întoarce rezultatul ramurii compuse."""
    n = len(tr)
    baza = {k: v for k, v in (r0.get("cablu") or {}).items() if k in ("metoda", "izolatie", "theta", "rho_sol", "n_alte")}
    ctx, rez_l, ultim = ctx_s, [], None
    for i in range(n - 1, -1, -1):
        t = tr[i]
        if not isinstance(t, dict) or not _valideaza_dict(t, j, "schema", sari=("L",)):
            if not isinstance(t, dict):
                emite(j, "V07", BLOCANT, oc0, "param", camp="cablu_C0.tronsoane", x=repr(t)[:40], conditie="se așteaptă un obiect")
            return None
        L = t.get("L", t.get("L_m"))
        if L is None or not _numar(L) or float(L) <= 0:
            emite(j, "V07", BLOCANT, oc0, "param", camp=f"cablu_C0.tronsoane[{i}].L", x=repr(L), conditie="lungimea tronsonului > 0 m")
            return None
        cab = dict(baza)
        cab.update({k: v for k, v in t.items() if v is not None and k not in ("L", "L_m")})
        cb.metoda_implicita(cab, "D1")
        if cab.get("material") is None:
            cab["material"] = "Al" if cab["metoda"] in norme.METODE_IN_PAMANT else "Cu"
        cab["L"] = float(L)
        ob = f"{oc0}/t{i + 1}"
        rr = calculeaza_ramura(dict(r0, cablu=cab), ctx, j, ob, amonte=q_tg if i == n - 1 else None,
                               obiect_sel="Q TG vs QG" if tg else "Q PT vs QG")
        if rr["blocat"]:
            return rr
        rez_l.insert(0, dict(rr["rezultat"], tronson=i + 1))
        ctx = dict(rr["ctx_aval"], dU_cef_pct=rr["rezultat"]["dU_cumulat_pct"])
        ultim = rr
    comb = dict(ultim["rezultat"])
    comb["tronsoane"] = rez_l
    comb["L_m"] = sum(x["L_m"] for x in rez_l)
    comb["dU_ramura_pct"] = sum(x["dU_ramura_pct"] for x in rez_l)
    comb["Iz_corectat_A"] = min(x["Iz_corectat_A"] for x in rez_l)
    comb["cablu"] = " + ".join(f"{x['cablu']} ({fmt_ro(x['L_m'], 0)} m)" for x in rez_l)
    j.pas(f"{oc0}: {n} tronsoane — " + "; ".join(f"t{x['tronson']}: {x['cablu']}, L {fmt_ro(x['L_m'], 0)} m, Iz' "
                                                  f"{fmt_ro(x['Iz_corectat_A'])} A, ΔU {fmt_ro(x['dU_ramura_pct'], 2)} %"
                                                  for x in rez_l)
          + f"; ΔU total {fmt_ro(comb['dU_ramura_pct'], 2)} %, Ik1min la tablou {fmt_ro(comb['Ik1min_capat_A'], 0)} A")
    return {"rezultat": comb, "prot": ultim["prot"], "ctx_aval": ultim["ctx_aval"], "blocat": False,
            "Ib": ultim["Ib"], "Ip": ultim["Ip"]}


def _reglaj(v, baza):
    """r12: reglaj dat ca multiplu (≤ 20 → ·baza) sau în amperi (> 20)"""
    if v is None or not _numar(v) or isinstance(v, bool):
        return None
    return float(v) * baza if float(v) <= 20 else float(v)


def config_q(d, in_implicit=None):
    """r12 (proiecte reale): configurația impusă a unui întreruptor (QG de interfață, protecția unei plecări):
    {tip | prot_tip: MCCB / ACB / gG / MCB, In_A, electronic | decl („EL”/„electronic”), motorizat, Ir_A | Ir_reglat |
    Ir_multiplu, Isd_A | Isd_reglat | Isd_multiplu, Icu_kA, curba}. Reglajele ≤ 20 sunt multipli (Ir·In, Isd·Ir)."""
    d = d if isinstance(d, dict) else {}
    out = {}
    tip = d.get("tip", d.get("prot_tip"))
    tn = _fd(tip) if isinstance(tip, str) else ""
    if tn in ("electronic", "el", "lsi"):
        out["decl"] = "EL"
        tip = None
    elif tn in ("motorizat",):
        out["motorizat"] = True
        tip = None
    if tip is not None:
        out["tip"] = pr.normalizeaza_tip(tip)
    In = d.get("In_A", in_implicit)
    if In is not None:
        out["In_A"] = In
    dc = d.get("decl")
    if d.get("electronic") is True or (isinstance(dc, str) and _fd(dc) in ("el", "electronic", "lsi")):
        out["decl"] = "EL"
    elif isinstance(dc, str) and _fd(dc) in ("tm", "termomagnetic"):
        out["decl"] = "TM"
    if d.get("motorizat"):
        out["motorizat"] = True
    for k in ("Icu_kA", "curba"):
        if d.get(k) is not None:
            out[k] = d[k]
    ir = next((d.get(k) for k in ("Ir_A", "Ir_reglat", "Ir_multiplu") if d.get(k) is not None), None)
    isd = next((d.get(k) for k in ("Isd_A", "Isd_reglat", "Isd_multiplu") if d.get(k) is not None), None)
    if ir is not None:
        out["_ir"] = ir
    if isd is not None:
        out["_isd"] = isd
        out.setdefault("decl", "EL")
    return out


def q_ramura(cfg, In):
    """r12: cheile de ramură (calculeaza_ramura) din configurația impusă `config_q`, la calibrul In"""
    r = {}
    if cfg.get("tip"):
        r["prot_tip"] = cfg["tip"]
    if cfg.get("In_A") is not None:
        r["In_fortat"] = cfg["In_A"]
    if cfg.get("decl"):
        r["decl_fortat"] = cfg["decl"]
    if cfg.get("motorizat"):
        r["motorizat"] = True
    if cfg.get("Icu_kA") is not None:
        r["Icu_fortat"] = float(cfg["Icu_kA"])
    if cfg.get("curba"):
        r["curba"] = cfg["curba"]
    if In is not None and cfg.get("_ir") is not None:
        r["Ir_fortat"] = _reglaj(cfg["_ir"], In)
    isd = cfg.get("_isd")
    if isd is not None and _numar(isd) and not isinstance(isd, bool):
        if float(isd) <= 20:
            r["Isd_multiplu_fortat"] = float(isd)
        else:
            r["Isd_fortat"] = float(isd)
    return r


def _schema_cef(inp, j):
    """SPEC §C.3: invertoare și PCS (ramuri B.21), sume, QG, praguri de racord, PT propriu, categoria RfG, TC,
    partea de c.c. (Uoc la Tmin, gPV, SPD c.c.). v1.2: Iac,max din fișă verificat (V64), S_total = max(√3·U·ΣIac; ΣPn),
    CEF monofazat calculat la 230 V (C3), racord prin BMPT verificat față de Q BMPT (M4), β_Uoc > 0 → V68 (C9)."""
    rez = {}
    st_original = copy.deepcopy(inp.get("string")) if isinstance(inp.get("string"), dict) else None
    fise.aplica(inp, j, "cef")
    invertoare_implicite(inp, j)
    lim_pcc = inp.get("limitare_PCC_kW")
    if isinstance(lim_pcc, (int, float)) and not isinstance(lim_pcc, bool) and lim_pcc > 0:
        # E2: limitarea la PCC se realizează cu același lanț ca limitarea injecției (TC + analizor la PCC → EMS →
        # invertoare / PCS); dacă ambele sunt date, se aplică valoarea mai mică
        li = inp.get("limitare_injectie_kW")
        if not isinstance(li, (int, float)) or isinstance(li, bool) or li > lim_pcc:
            inp["limitare_injectie_kW"] = float(lim_pcc)
    # v1.9 (R5, regula „rețeaua nu se presupune”): la CEF trifazatul e implicit, dar declarat explicit în „Am presupus”
    if inp.get("retea") is None:
        j.presupune("rețea trifazată 3 × 400/230 V (CEF; rețeaua nu a fost declarată — confirmați)")
    retea = inp.get("retea") or "tri"
    mono = retea == "mono"
    U = u_calcul(retea)
    u_txt = "230 V" if mono else f"√3·{fmt_ro(norme.u_n(), 0)} V"
    unitati = []
    for grup in inp.get("invertoare") or []:
        # r8 (P0-5): invertor monofazat (catalog: Primo …-1, Sunny Boy, SUN2000-…-L1, MIN …; sau `retea` pe grup) pe
        # rețea trifazată → calcul la 230 V, protecție 2P, repartiție pe faze
        r_u = "mono" if (mono or _retea_grup(grup) == "mono") else retea
        for _ in range(int(grup.get("n", 1))):
            unitati.append({"Pn_kW": float(grup["Pn_kW"]), "Iac_max_A": grup.get("Iac_max_A"), "pcs": False,
                            "grup": grup, "retea": r_u})
    for i, u in enumerate(unitati, 1):
        u["obiect"] = f"INV-{i}"
    bess = inp.get("bess")
    n_pcs = _bess_normalizeaza(bess, j) if isinstance(bess, dict) else 1
    if isinstance(bess, dict):
        rez["bess_date"] = {"kWh": bess.get("kWh"), "P_kW": bess.get("P_kW"), "n_pcs": n_pcs}
    if not unitati and not bess:
        emite(j, "V07", BLOCANT, "schema", "lipsa")
        return rez
    if not unitati:
        # v1.9 (R5 P1-16): BESS de sine stătător (fără invertoare PV) — tipul „cef” cu doar `bess` (alias tip „bess”)
        rez["bess_singur"] = True
        j.pas("BESS de sine stătător (fără câmp PV): PCS racordat ca un generator la bara TGD-CF")
    _putere_declarata(inp, j, sum(float(g.get("Pn_kW") or 0) * int(g.get("n", 1)) for g in inp.get("invertoare") or []))
    if unitati and inp.get("kWp") is not None and not gt(float(inp["kWp"]), 0.0):
        # M8 (v1.2): invertoare PV fără putere PV instalată
        emite(j, "V07", BLOCANT, "schema", "param", camp="kWp", x=inp["kWp"], conditie="trebuie > 0 când există invertoare PV")
        return rez
    if bess and _invertor_baterie_ca_cc(inp, j):
        return rez
    cuplaj = _cuplaj_bess_cef(inp, j, bool(unitati)) if bess else None
    if bess and cuplaj == "cc":
        # r6 (fotovoltaic P0-5): baterie pe portul de c.c. al invertoarelor hibride — fără PCS, fără ramură c.a. proprie;
        # puterea bateriei iese prin invertor (nu se adună la Σ Pn / Σ Iac)
        rez["BESS"] = _bess_cc_cef(inp, j, bess, unitati)
    elif bess:
        p = bess.get("P_kW")
        if p is None:
            if not bess.get("kWh"):
                emite(j, "V07", BLOCANT, "PCS", "lipsa")
                return rez
            p = float(bess.get("kWh", 0)) / 2.0
            j.presupune(f"PCS BESS P = kWh/2 = {fmt_ro(p)} kW (0,5C)")
        # r8 (P1): n_pcs PCS identice (bess.n_pcs), fiecare cu ramura și protecția lui (P_kW = total)
        iac_b = bess.get("Iac_max_A")
        for k in range(n_pcs):
            unitati.append({"Pn_kW": float(p) / n_pcs, "Iac_max_A": iac_b, "pcs": True,
                            "obiect": "PCS" if n_pcs == 1 else f"PCS-{k + 1}", "retea": retea})
        if n_pcs > 1:
            j.pas(f"BESS: {n_pcs} PCS × {fmt_ro(float(p) / n_pcs)} kW = {fmt_ro(p)} kW, fiecare cu ramura și protecția lui")
    if mono:
        rez["retea"] = "mono"
        j.presupune("CEF monofazat: Iac = 1,1·Pn/230, protecții 1P+N, cabluri cu 3 conductoare, ΔU pe 230 V")
    elif any(u.get("retea") == "mono" for u in unitati) and norme.u_n() != norme.U_N_V:
        _contradictie(j, BLOCANT, "schema", "invertoare monofazate (1 × 230 V, cu N) pe o bară de 800 V c.a. fără neutru",
                      "invertoare trifazate de 800 V, sau invertoarele monofazate pe o bară separată de 3 × 400/230 V")
        return rez
    # C2 (v1.2): Iac,max din fișă nu poate fi sub Pn/U (cosφ = 1 la tensiunea nominală)
    for u in unitati:
        if u["Iac_max_A"] is not None:
            i_fiz = u["Pn_kW"] * 1000.0 / u_calcul(u.get("retea", retea))
            if lt(float(u["Iac_max_A"]), i_fiz * (1 - 1e-3)):     # R2: toleranță 0,1 % (rotunjirea fișei)
                emite(j, "V64", BLOCANT, u["obiect"], x=float(u["Iac_max_A"]), y=i_fiz, P=u["Pn_kW"],
                      U="230 V" if u.get("retea") == "mono" else u_txt)
    if j.are_blocant():
        return rez
    for u in unitati:
        u["Iac"] = u["Iac_max_A"] or norme.FACTOR_SMAX_INVERTOR * u["Pn_kW"] * 1000.0 / u_calcul(u.get("retea", retea))
        # r11 (fotovoltaic #6 / #39): S pentru trafo (V67) = Smax real: din Iac,max al fișei, din catalog (Smax) sau
        # Pn (cosφ 1) — nu 1,1·Pn (acela rămâne majorantul curentului pentru protecții / cabluri)
        g_ = u.get("grup") or {}
        if u["Iac_max_A"]:
            u["S_trafo_kVA"] = u_calcul(u.get("retea", retea)) * float(u["Iac_max_A"]) / 1000.0
        else:
            u["S_trafo_kVA"] = (cat_inv.smax_kva(g_.get("producator"), g_.get("model")) if not u["pcs"] else None) \
                or u["Pn_kW"]
    s_iac = sum(u["Iac"] for u in unitati)
    s_iac_kva = U * s_iac / 1000.0
    i_faze = None if mono else _repartitie_faze(unitati, j)
    if i_faze:
        # r8 (P0-5): curentul echivalent al barei = curentul fazei celei mai încărcate; S = 230·Σ I faze
        s_iac = max(i_faze.values())
        s_iac_kva = norme.u_0() * sum(i_faze.values()) / 1000.0
        rez["faze"] = {f: round(i_faze[f], 2) for f in FAZE}
    pn_tot = sum(u["Pn_kW"] for u in unitati)
    pn_inv = sum(u["Pn_kW"] for u in unitati if not u["pcs"])
    s_tot = max(s_iac_kva, pn_tot)
    s_v67 = sum(u["S_trafo_kVA"] for u in unitati)
    rez["sume"] = {"Pn_total_kW": pn_tot, "Iac_total_A": s_iac, "S_total_kVA": s_tot, "S_din_Iac_kVA": s_iac_kva,
                   "S_trafo_kVA": s_v67}
    if inp.get("kWp") is not None and pn_inv > 0:
        rez["raport_DC_AC"] = float(inp["kWp"]) / pn_inv
    if i_faze:
        j.pas(f"Curent maxim pe fază (invertoare tri + mono) = {fmt_ro(s_iac)} A; S = 230·Σ I faze = {fmt_ro(s_iac_kva)} kVA; "
              f"Σ Pn = {fmt_ro(pn_tot)} kW → S = {fmt_ro(s_tot)} kVA")
    else:
        j.pas(f"Σ Iac,max = {' + '.join(fmt_ro(u['Iac']) + (' (PCS)' if u['pcs'] else '') for u in unitati)} = "
              f"{fmt_ro(s_iac)} A; S = max({'230' if mono else '√3·' + fmt_ro(norme.u_n(), 0)}·Σ Iac = {fmt_ro(s_iac_kva)} kVA; Σ Pn = "
              f"{fmt_ro(pn_tot)} kW) = {fmt_ro(s_tot)} kVA")

    # racord (pct. 4–5)
    sn = inp.get("pt_Sn_kVA")
    ik_dat = next((inp.get(k) for k in ("Ik3_sursa_kA", "Ik3_bara_kA") if inp.get(k) is not None), None)
    if ik_dat is not None and inp.get("racord") != "tg_existent":
        if sn is None and inp.get("Ik3_OD_kA") is None:
            # r8 (P1): „Ik X kA la bară” = Ik3 la punctul de racord (nu valoarea implicită, nu 0)
            inp["Ik3_OD_kA"] = float(ik_dat)
            j.pas(f"Ik3 la punctul de racord = {fmt_ro(float(ik_dat))} kA (declarat)")
        elif sn is not None:
            j.presupune(f"Ik3 declarat {fmt_ro(float(ik_dat))} kA ignorat — cu PT propriu Ik3 la bara JT se calculează din "
                        f"trafo")
    if inp.get("racord") == "pt" and sn is None:
        emite(j, "V07", BLOCANT, "schema", "param", camp="pt_Sn_kVA", x="—", conditie="racord „pt” fără puterea PT")
        return rez
    # r7 (P1): dublu racord — în TG existent ȘI într-un PT nou declarat explicit (două puncte de racord)
    if inp.get("racord") == "tg_existent" and sn is not None and _bool(inp.get("pt_existent")) is False:
        _contradictie(j, BLOCANT, "schema", "racord în TG existent și în PT nou — CEF are un singur punct de racord",
                      "alegeți: racord în TG existent (PT existent = sursa) sau PT propriu nou (racord „pt”)")
        return rez
    # r7 (P0-2): numărul de transformatoare identice ale PT-ului (`n_trafo`, 1…4) — Σ Sn față de S CEF
    n_t = inp.get("n_trafo", 1)
    if n_t is None:
        n_t = 1
    if isinstance(n_t, bool) or not isinstance(n_t, (int, float)) or n_t != int(n_t) or not 1 <= int(n_t) <= 4:
        emite(j, "V96", BLOCANT, "schema", ce=f"PT cu n_trafo = {n_t!r}",
              detaliu="motorul acoperă 1…4 transformatoare identice în paralel pe barele JT",
              remediere="n_trafo întreg 1…4, sau proiect de specialitate")
        return rez
    n_t = int(n_t)
    if n_t > 1 and sn is None:
        emite(j, "V07", BLOCANT, "schema", "param", camp="pt_Sn_kVA", x="—", conditie=f"n_trafo = {n_t} fără puterea trafo")
        return rez
    masura = _masura_cef(inp, j, sn)
    if masura is False:
        return rez
    t = None
    racord = None
    q_pt = None
    if mono:
        if sn is not None:
            emite(j, "V12", BLOCANT, "schema", poli="monofazat", retea="cu PT propriu (trifazat)")
            return rez
        if gt(s_iac, norme.BMPM["I_max_A"]):
            emite(j, "V53", BLOCANT, "schema", "inv", Ib=s_iac)
            return rez
        s_mono = s_iac * norme.U_0_V / 1000.0          # Ord. ANRE 228/2018 art. 12(3): comparația pe kVA (16 A)
        if gt(s_mono, norme.MONOFAZAT_S_INVERTOR_AVERTISMENT_KVA):
            emite(j, "V71", AVERTISMENT, "schema", P=pn_tot, S=round(s_mono, 2))
        racord = {"tip": "JT monofazat prin BMPM", "In_Q_max_A": norme.BMPM["I_max_A"]}
        ctx = _context_od(inp, j, ddr_amonte=False)
    elif sn is not None:
        if int(sn) not in norme.TRAFO or float(sn) != int(sn):
            emite(j, "V05", BLOCANT, "schema", "trafo", Sn=sn, vecini=", ".join(str(s) for s in norme.TRAFO_SN_KVA))
            return rez
        t = trafo_sursa(inp, j, int(sn), inp.get("trafo_izolatie"))
        if t is None:
            return rez
        # v1.9 (R5 P0-4): PT existent = sursa (Ik din trafo), nu trafo nou desenat în serie între două tablouri JT.
        # Racord în TG existent + PT propriu → PT-ul e cel existent care alimentează TG-ul.
        existent = _bool(inp.get("pt_existent"))
        if _bool(inp.get("pt_od")):
            # r11 (fotovoltaic #1): PT-ul e al OD — sursa existentă (Ik din trafo), nimic nou desenat amonte de racord
            if existent is False:
                _contradictie(j, BLOCANT, "schema", "PT al OD declarat și PT nou (pt_existent false)",
                              "PT al OD (racord pe bara lui JT) sau PT propriu nou")
                return rez
            existent = True
            j.pas(f"PT {int(sn)} kVA al OD: sursa racordului (Ik3 din trafo), nu face obiectul proiectului")
        if existent is None and inp.get("racord") == "tg_existent":
            existent = True
            j.presupune(f"PT propriu {int(sn)} kVA = PT existent care alimentează TG-ul (racord în TG existent) — "
                        f"sursa pentru Ik, fără transformator nou")
        existent = bool(existent)
        bara_un_trafo = False
        if n_t > 1 and existent and (inp.get("bara") is not None or inp.get("bara_racord") is not None
                                     or inp.get("cupla") is not None):
            # r10 (fotovoltaic #15): „racord pe bara JT a T1” / cupla deschisă → Ik3 doar din trafo-ul barei, nu T1 ∥ T2
            nt = n_trafo_sursa(dict(inp, n_trafo=n_t), j, f"PT existent {n_t} × {int(sn)} kVA")
            if nt is None:
                return rez
            bara_un_trafo = not nt[1]
        if n_t > 1 and existent and bara_un_trafo:
            j.presupune(f"injecția CEF pe bara unui singur trafo ({int(sn)} kVA, cupla deschisă) — Sn față de S CEF se "
                        f"verifică pe acest trafo")
        elif n_t > 1 and existent:
            # r7 (P0-2): n trafo identice în paralel pe barele JT ale PT-ului existent (cuplă normal închisă):
            # Zk = Z_Q + K_T·Z_T/n → Ik3max bară (Icu); Ik1min cu un singur trafo în funcțiune (prudent)
            t = dict(t)
            t["Zk"] = (t["Z_Q"][0] + t["K_T"] * t["Z_T"][0] / n_t, t["Z_Q"][1] + t["K_T"] * t["Z_T"][1] / n_t)
            t["Ik3max_bara_kA"] = sc.ik3_din_z(t["Zk"])
            j.pas(f"PT {n_t} × {int(sn)} kVA în paralel pe barele JT (aceeași grupă de conexiuni, uk egal): Ik3max bară = "
                  f"{fmt_ro(t['Ik3max_bara_kA'])} kA (toate în funcțiune); Ik1min cu un singur trafo")
            j.presupune(f"la ieșirea din funcțiune a unui trafo, injecția CEF se limitează la {n_t - 1} × {int(sn)} kVA "
                        f"(EMS / deconectarea unei părți din invertoare) — conform ATR")
        elif n_t > 1:
            # r8 (P1, CEF > ~2,2 MW): PT NOU cu n trafo — fiecare trafo cu secția lui de bare JT (TGD-CF k) și grupul lui
            # de invertoare, câte un QG pe secție; cupla QC normal DESCHISĂ cu interblocaj (trafo niciodată în paralel) —
            # ca la PT-ul de distribuție. Ik3max pe secție = un singur trafo.
            j.pas(f"PT nou {n_t} × {int(sn)} kVA: {n_t} secții de bare JT (câte una pe trafo, fiecare cu QG și grupul ei de "
                  f"invertoare), cuplă QC normal deschisă cu interblocaj — Ik3max secție = {fmt_ro(t['Ik3max_bara_kA'])} kA "
                  f"(un trafo)")
            j.presupune(f"cupla barelor JT normal deschisă, cu interblocaj (trafo niciodată în paralel) — decizia proiectantului; "
                        f"la retragerea unui trafo, secția lui trece pe celălalt prin QC numai cu injecția limitată la "
                        f"{int(sn)} kVA (EMS), conform ATR")
        if inp.get("SkQ_MVA") is None:
            j.presupune("S\"kQ = 500 MVA, R/X = 0,1 (rețea MT, majorant)")
        j.ipoteza("skq", t["SkQ_MVA"], inp.get("SkQ_MVA") is None)
        j.ipoteza("trafo", (t["uk_pct"], t["Pk_W"]), True)
        rez["trafo"] = {"Sn_kVA": int(sn), "In_T_A": t["In_T_A"], "Ik3max_bara_kA": t["Ik3max_bara_kA"]}
        if n_t > 1:
            rez["trafo"]["n_trafo"] = n_t
            rez["n_trafo"] = n_t
        if norme.u_n() != norme.U_N_V:
            rez["trafo"]["U_JT_kV"] = norme.u_n() / 1000.0
        if existent:
            rez["trafo"]["existent"] = True
        else:
            # r6 (fotovoltaic P0-2): PT propriu NOU — celula MT (linie + celula trafo), T1 în post, Q JT al trafo;
            # TGD-CF se leagă prin C0 (legătura JT T1 → TGD-CF), PCC pe MT 20 kV
            if n_t > 2:
                emite(j, "V96", BLOCANT, "schema", ce=f"PT nou cu {n_t} trafo",
                      detaliu="motorul desenează PT-ul nou al CEF cu 1 sau 2 trafo (2 secții de bare JT cu cuplă)",
                      remediere="n_trafo 1 sau 2 (trafo mai mari), sau proiect de specialitate")
                return rez
            rez["PT"], q_pt = _pt_nou_cef(inp, j, int(sn), t, n_t, masura)
        if n_t > 1 and not existent:
            pass        # r8: Sn față de S se verifică pe fiecare secție (trafo cu grupul lui de invertoare), mai jos
        elif lt((1 if bara_un_trafo else n_t) * sn, s_v67):
            # și la PT existent: trafo sub injecție; r7: Σ Sn la n trafo; r11: S = Smax real (fișă / catalog / Pn)
            if n_t > 1 and not bara_un_trafo:
                _v67_pcc(inp, j, rez, n_t * sn, s_v67, "schema", "n", n=n_t, sn=int(sn), x=n_t * sn)
            else:
                _v67_pcc(inp, j, rez, sn, s_v67, "schema", x=sn)
        elif lt((1 if bara_un_trafo else n_t) * sn, s_tot):
            # r11: doar majorantul 1,1·Pn depășește Sn — la limită, nu blocant
            emite(j, "V67", AVERTISMENT, "schema", x=(1 if bara_un_trafo else n_t) * sn, y=s_tot)
            j.verificari[-1]["mesaj"] += (f" (majorant 1,1·Pn; Smax real {fmt_ro(s_v67)} kVA ≤ Sn) — trafo la limită, "
                                          f"confirmați Smax / Iac,max din fișa invertoarelor")
        ctx = sc.context_pt(t)
        racord = {"tip": "MT prin PT propriu" + (" existent" if existent else " nou"), "Sn_kVA": int(sn)}
        if n_t > 1:
            racord["n_trafo"] = n_t
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
        bmpt = bool(racord and "BMPT" in racord.get("tip", ""))
        if inp.get("IdN_amonte_mA") is None and not bmpt:
            # r6 (fotovoltaic P0-4): racord fără BMPT (JT direct din PT OD / PT propriu / TG existent) și fără DDR
            # declarat în amonte — schema NU se oprește: QG primește bloc diferențial reglabil (cel mai mare IΔn
            # admis de RA), invertoarele DDR ≤ IΔn_QG/3; segmentul QG → PCC (C0) rămâne de acoperit în amonte (V34 AV)
            idn_am, am = None, None
            emite(j, "V34", AVERTISMENT, "C0 (amonte de QG)", "cef_amonte")
        else:
            idn_am = _tt_amonte(inp, j, ra, bmpt=bmpt)
            if idn_am is None:
                return rez
            am = ddr_mod.descriere(idn_am, inp.get("DDR_amonte_selectiv", True),
                                   "DDR amonte (declarat)" if inp.get("IdN_amonte_mA") is not None else "RCCB BMPT")
        # v1.3 R5 (§C.2 pct. 13, M5-4): ca la tablou — amonte temporizat → QG fără DDR propriu, invertoare instantanee
        # ≤ IΔn amonte/3; altfel bloc diferențial reglabil asociat QG (Δt 0,15 s)
        al = ddr_mod.alege_tt(lim, am)
        sus = am
        if al["intrare"]:
            idn_qg = al["intrare"]["IdN_mA"]
            sus = ddr_mod.descriere(idn_qg, True, "DDR QG", al["intrare"]["dt_s"])
            if am is not None:
                ddr_mod.verifica(j, am, sus, "QG", RA_ohm=ra)
        ctx = dict(ctx, idn_tt_mA=al["idn_circuite"], ddr_sus=sus, RA_tt=ra)
        if idn_am is not None:
            rez["IdN_amonte_mA"] = idn_am
        rez["DDR_TT_IdN_mA"] = max(al["idn_circuite"], idn_am or 0, idn_qg or 0)
        j.pas(f"TT: RA = {fmt_ro(ra)} Ω → IΔn ≤ {fmt_ro(50000.0 / ra, 0)} mA; amonte "
              + (f"{am['denumire']} {idn_am} mA {am['temporizare']}" if am else "fără DDR declarat") + " → "
              + (f"QG bloc diferențial reglabil {idn_qg} mA, Δt {fmt_ro(DT_QG, 2)} s"
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
    if isinstance(rez.get("PT"), dict):
        rez["PT"]["categorie_RfG"] = cat
    emite(j, "V70", INFO if cat == "A" else AVERTISMENT, "schema", "INFO" if cat == "A" else "AV", X=cat, P=pn_tot)

    # v1.3 (P0-2): punctul de racord — TG existent (QG se leagă pe o plecare a tabloului general existent) și C0
    tg = inp.get("racord") == "tg_existent"
    ctx_pcc = _context_tg(inp, j, ctx) if tg else ctx
    if tg:
        racord["tg_existent"] = True
        racord["tip"] = f"TG existent (consum propriu) — {racord['tip']}"
    L0 = inp.get("L_racord_m", (inp.get("cablu_C0") or {}).get("L"))
    _tr = (inp.get("cablu_C0") or {}).get("tronsoane") if isinstance(inp.get("cablu_C0"), dict) else None
    if isinstance(_tr, list) and _tr and all(isinstance(t, dict) and _numar(t.get("L", t.get("L_m"))) for t in _tr):
        L0 = sum(float(t.get("L", t.get("L_m"))) for t in _tr)        # r12: C0 din tronsoane
    if L0 is None and cablu_impus_fara_L(inp.get("cablu_C0"), j, "C0", "L_racord_m"):
        return rez

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
        r = {"rol": "invertor", "receptor": "pcs" if u["pcs"] else "invertor", "retea": u.get("retea") or retea,
             "Pn_kW": u["Pn_kW"], "cablu": cab_in}
        if u["Iac_max_A"]:
            r["Iac_max_A"] = u["Iac_max_A"]
        # v1.9 (R5 P0-6): DDR pe invertorul CEF doar la cerere (fișă / ATR: `invertoare[].ddr` {IdN_mA, tip}) sau în TT
        if isinstance(g.get("ddr"), dict):
            r["ddr"] = dict(g["ddr"])
        # r12 (proiecte reale): tipul protecției invertorului — separator cu siguranțe gG / MPR, MCB curba C sau MCCB —
        # și calibrul / reglajele impuse (`invertoare[].prot_tip`, `invertoare[].protectie` {In_A, Ir_A, Icu_kA, curba})
        if not u["pcs"] and (g.get("prot_tip") is not None or isinstance(g.get("protectie"), dict)):
            cfg = config_q(dict(g.get("protectie") or {}, **({"tip": g["prot_tip"]} if g.get("prot_tip") else {})))
            r.update(q_ramura(cfg, cfg.get("In_A")))
        return r

    lim_inj = None
    sectii_pt = bool(n_t > 1 and rez.get("PT") and q_pt is not None)
    # r11 (fotovoltaic #44): mai multe tablouri TGD-CF (`n_tgd_cf`, `invertoare[].tgd` 1…n), fiecare cu invertoarele
    # lui, cu QGk → C0.k racordate pe bara JT a punctului de racord (PT / TG existent / PCC)
    n_tgd = inp.get("n_tgd_cf")
    tgd_g = [g.get("tgd") for g in inp.get("invertoare") or [] if isinstance(g, dict) and g.get("tgd") is not None]
    if n_tgd is None and tgd_g and all(_numar(x) for x in tgd_g):
        n_tgd = int(max(tgd_g))
    if n_tgd is not None and (isinstance(n_tgd, bool) or not _numar(n_tgd) or n_tgd != int(n_tgd)
                              or not 1 <= int(n_tgd) <= TGD_CF_MAX):
        emite(j, "V96", BLOCANT, "schema", ce=f"CEF cu n_tgd_cf = {n_tgd!r}",
              detaliu=f"motorul desenează 1…{TGD_CF_MAX} tablouri TGD-CF", remediere=f"n_tgd_cf întreg 1…{TGD_CF_MAX}")
        return rez
    tgd = bool(n_tgd and int(n_tgd) > 1)
    if tgd:
        n_tgd = int(n_tgd)
        motiv = ("PT nou cu 2 trafo (secții)" if sectii_pt else "CEF monofazat" if mono else
                 "invertoare de 800 V c.a." if norme.u_n() != norme.U_N_V else None)
        if motiv:
            emite(j, "V96", BLOCANT, "schema", ce=f"{n_tgd} tablouri TGD-CF la {motiv}",
                  detaliu="combinația nu e desenată de motor", remediere="un singur TGD-CF sau proiect de specialitate")
            return rez
        if any(not _numar(x) or not 1 <= x <= n_tgd or x != int(x) for x in tgd_g):
            emite(j, "V12", BLOCANT, "schema", "camp", camp="invertoare[].tgd", valoare=tgd_g)
            j.verificari[-1]["remediere"] = f"tgd 1…{n_tgd} pe fiecare grup de invertoare"
            return rez

    # r12 (proiecte reale): cascade CEF — N tablouri intermediare (TE secundare), fiecare cu invertoarele lui și
    # plecarea proprie (C-TEk, protecție la ambele capete: QFk în TEG, QSk în tablou) spre TEG-ul de interfață comun
    cascada = None
    te_in = inp.get("tablouri_intermediare")
    if te_in is not None:
        if not isinstance(te_in, list) or not te_in or not all(isinstance(t, dict) for t in te_in):
            emite(j, "V07", BLOCANT, "schema", "param", camp="tablouri_intermediare", x=repr(te_in)[:40],
                  conditie="se așteaptă o listă de tablouri (obiecte)")
            return rez
        motiv = ("PT nou cu 2 trafo (secții)" if sectii_pt else "CEF monofazat" if mono else
                 "n_tgd_cf (TGD-CF cu QG proprii)" if tgd else None)
        if motiv:
            emite(j, "V96", BLOCANT, "schema", ce=f"tablouri intermediare la {motiv}",
                  detaliu="combinația nu e desenată de motor", remediere="tablouri intermediare spre un singur TEG")
            return rez
        for t_ in te_in:
            ok_t = _valideaza_dict({k: v for k, v in t_.items() if k not in ("cablu", "nume", "IP")}, j, "schema")
            if ok_t and t_.get("cablu") is not None:
                ok_t = isinstance(t_["cablu"], dict) and _valideaza_dict(t_["cablu"], j, "schema", sari=("L",))
            if not ok_t:
                return rez
        cascada = []
        for k, t_ in enumerate(te_in, 1):
            cascada.append({"k": k, "spec": t_, "nume": str(t_.get("nume") or f"TE-{k}"), "unitati": []})
        fara = []
        for u in unitati:
            g_ = u.get("grup") or {}
            x = (bess or {}).get("tablou") if u["pcs"] and isinstance(bess, dict) else g_.get("tablou")
            if x is None and not u["pcs"]:
                fara.append(u)
                continue
            if x is None or x == 0:
                continue                     # direct pe bara TEG (PCS, invertor cu tablou 0)
            if isinstance(x, bool) or not _numar(x) or x != int(x) or not 1 <= x <= len(cascada):
                emite(j, "V12", BLOCANT, "schema", "camp", camp="invertoare[].tablou", valoare=x)
                j.verificari[-1]["remediere"] = f"tablou 1…{len(cascada)} (0 = direct pe TEG)"
                return rez
            cascada[int(x) - 1]["unitati"].append(u)
        if fara:
            for k, g_ in enumerate(_repartitie_sectii(fara, len(cascada), Jurnal())):
                cascada[k]["unitati"].extend(g_)
            j.presupune(f"invertoarele fără `tablou` repartizate pe cele {len(cascada)} tablouri intermediare în tranșe "
                        f"de putere egală — declarați invertoare[].tablou")
        for te in cascada:
            if not te["unitati"]:
                emite(j, "V07", BLOCANT, te["nume"], "plecari", tablou=te["nume"])
                j.verificari[-1]["remediere"] = f"invertoare pe {te['nume']} (invertoare[].tablou = {te['k']}) sau mai puține tablouri"
                return rez
            te["unitati"].sort(key=lambda u: unitati.index(u))
            for u in te["unitati"]:
                u["_te"] = te["k"]
            te["iac"] = sum(u["Iac"] for u in te["unitati"])
            te["pn"] = sum(u["Pn_kW"] for u in te["unitati"])
        # ordinea unităților: tablou 1, tablou 2 …, apoi cele directe pe TEG (numerotarea INV-k urmează desenul)
        j.pas(f"{len(cascada)} tablouri intermediare → TEG de interfață comun: " + "; ".join(
            f"{te['nume']}: {', '.join(u['obiect'] for u in te['unitati'])} (Σ Iac {fmt_ro(te['iac'])} A)" for te in cascada))

    def ramura_te(te):
        """r12: plecarea tabloului intermediar k (cablul C-TEk, TEG → TEk) — ramură de tip c0 cu Iac = Σ Iac al
        tabloului, protecția (tip / In / reglaje impuse sau aleasă) ≥ Ip max al invertoarelor lui"""
        t = te["spec"]
        cab = {k: v for k, v in (inp.get("cablu") or {}).items() if k in CAMPURI_CABLU_SCHEMA and v is not None}
        cab.update({k: v for k, v in (t.get("cablu") or {}).items() if v is not None})
        cb.metoda_implicita(cab, "D1")
        if cab.get("material") is None:
            cab["material"] = "Al" if cab["metoda"] in norme.METODE_IN_PAMANT else "Cu"
            cab["material_implicit"] = True
        L = t.get("L_m", cab.get("L"))
        if L is None:
            L = 30.0
            if not te.get("_L_pres"):
                te["_L_pres"] = True
                j.presupune(f"lungime cablu {te['nume']} → TEG 30 m (nedeclarată: tablouri_intermediare[].L_m)")
        cab["L"] = float(L)
        r = {"rol": "c0", "receptor": "invertor", "retea": retea, "Pn_kW": te["pn"], "Iac_max_A": te["iac"],
             "cablu": cab, "are_aval": True, "_validat": True, "Ip_min_extra": te.get("ip_inv") or 0.0}
        cfg = config_q(t.get("protectie") if isinstance(t.get("protectie"), dict) else t, t.get("In_A"))
        In_ = cfg.get("In_A")
        r.update(q_ramura(cfg, In_))
        if r.get("Ir_fortat") is None and cfg.get("_ir") is not None and In_ is None:
            r.pop("Ir_fortat", None)
        return r

    def sectiune(unit_s, suf, ctx_s, rz, i_fz=None):
        """QG, C0, invertoarele / PCS și TC-ul unei bare TGD-CF (r8: o secție = un trafo al PT-ului nou, `suf` = „1”, „2”;
        fără secții `suf` = „” și `rz` = rezultatul schemei). Întoarce QG sau None (schema se oprește)."""
        nonlocal lim_inj
        oqg, oc0 = f"QG{suf}", f"C0{'.' + suf if suf else ''}"
        if suf:
            i_f = None
            if any(u.get("retea") == "mono" for u in unit_s):
                i_f = {f: sum(u["Iac"] for u in unit_s if u.get("retea") != "mono") +
                       sum(u["Iac"] for u in unit_s if u.get("faza") == f) for f in FAZE}
            s_iac_s = max(i_f.values()) if i_f else sum(u["Iac"] for u in unit_s)
            s_kva_s = norme.u_0() * sum(i_f.values()) / 1000.0 if i_f else U * s_iac_s / 1000.0
            pn_s = sum(u["Pn_kW"] for u in unit_s)
            s_s = max(s_kva_s, pn_s)
            rz["sume"] = {"Pn_total_kW": pn_s, "Iac_total_A": s_iac_s, "S_total_kVA": s_s}
            rz["unitati"] = [u["obiect"] for u in unit_s]
            j.pas((f"TGD-CF{suf}" if tgd else f"Secția {suf} (T{suf} {int(sn)} kVA)")
                  + f": {', '.join(rz['unitati'])} — Σ Pn = {fmt_ro(pn_s)} kW, "
                  f"Σ Iac = {fmt_ro(s_iac_s)} A, S = {fmt_ro(s_s)} kVA")
            s_s67 = sum(u["S_trafo_kVA"] for u in unit_s)
            if not tgd and lt(sn, s_s67):
                _v67_pcc(inp, j, rez, sn, s_s67, f"T{suf}", "sectie", fractie=1.0 / n_t, k=suf, x=int(sn),
                         inv=", ".join(rz["unitati"]))
            elif not tgd and lt(sn, s_s):
                emite(j, "V67", AVERTISMENT, f"T{suf}", "sectie", k=suf, x=int(sn), y=s_s, inv=", ".join(rz["unitati"]))
                j.verificari[-1]["mesaj"] += " (majorant 1,1·Pn; Smax real ≤ Sn) — trafo la limită"
        else:
            s_iac_s, pn_s = s_iac, pn_tot
        # QG (pct. 3): Ip,min = max(Σ Iac; Ip invertoare) — protecțiile invertoarelor se calculează întâi (doar Ip)
        jt = Jurnal()
        direct = [u for u in unit_s if not cascada or u.get("_te") is None]
        ip_inv = [x["Ip"] for x in (calculeaza_ramura(dict(ramura_unitate(u), _doar_protectie=True), ctx_s, jt, "tmp")
                                    for u in direct) if x["Ip"] is not None]
        for te in (cascada or []):
            # r12: plecarea fiecărui tablou intermediar — Ip ≥ Σ Iac al tabloului și ≥ Ip max al invertoarelor lui
            ip_te = [x["Ip"] for x in (calculeaza_ramura(dict(ramura_unitate(u), _doar_protectie=True), ctx_s, jt, "tmp")
                                       for u in te["unitati"]) if x["Ip"] is not None]
            te["ip_inv"] = max(ip_te) if ip_te else 0.0
            x = calculeaza_ramura(dict(ramura_te(te), _doar_protectie=True), ctx_s, jt, "tmp")
            if x["Ip"] is not None:
                ip_inv.append(x["Ip"])
        ip_min = max([s_iac_s] + ip_inv)
        qcfg = config_q(inp.get("QG"), inp.get("In_QG_A"))
        in_f = qcfg.get("In_A")
        ref = in_f if in_f is not None else ip_min
        tip = qcfg.get("tip") if qcfg.get("tip") in ("MCCB", "ACB") else ("MCCB" if ref <= 1600 + 1e-9 else "ACB")
        In = in_f if in_f is not None else pr.alege_calibru(tip, ip_min)
        if In is None:
            emite(j, "V06", BLOCANT, oqg, Ib=s_iac_s, tip="ACB")
            if sn is not None and n_t == 1 and rez.get("PT"):
                # r8: un singur QG nu poate duce toată puterea — PT nou cu 2 trafo, câte o secție de bare și un QG pe trafo
                j.verificari[-1]["remediere"] = ("PT nou cu 2 trafo (n_trafo 2): câte o secție de bare JT și un QG pe "
                                                 "trafo, cuplă normal deschisă")
            return None
        qkw = q_ramura(qcfg, In)
        if qkw.get("Ir_fortat") is not None and not (0.4 * In - 1e-6 <= qkw["Ir_fortat"] <= In + 1e-6):
            emite(j, "V12", BLOCANT, oqg, "camp", camp="QG.Ir_A", valoare=f"{fmt_ro(qkw['Ir_fortat'])} A (In {In} A)")
            j.verificari[-1]["remediere"] = "Ir reglat între 0,4·In și In"
            return None
        # r12 (proiecte reale): QG de interfață cu declanșator electronic / motorizat / reglaje Ir, Isd și Icu impuse
        qg = pr.construieste(tip, In, ip_min, are_aval=True, decl=qkw.get("decl_fortat"), ir=qkw.get("Ir_fortat"),
                             isd=qkw.get("Isd_fortat"))
        if qkw.get("Isd_multiplu_fortat") is not None and qg.get("decl") == "EL":
            qg["Isd_multiplu"] = qkw["Isd_multiplu_fortat"]
            qg["Isd_A"] = qg["Isd_multiplu"] * qg["Ir_A"]
            qg["Isd_fortat"] = True
        if qkw.get("Icu_fortat") is not None:
            qg["Icu_kA"] = qkw["Icu_fortat"]
            ok = ge(qg["Icu_kA"], ctx_s["Ik3_kA"])
        else:
            qg["Icu_kA"], ok = pr.alege_icu(tip, ctx_s["Ik3_kA"])
        if qg.get("decl") == "EL":
            pr.alege_isd(qg, sc.ik1_din_zb(ctx_s["Zb"]))
        rz["QG"] = {"tip": tip, "In_A": In, "Ir_A": qg["Ir_A"], "Ir_multiplu": qg["Ir_multiplu"], "Icu_kA": qg["Icu_kA"],
                    "poli": "2P" if mono else "4P"}
        for k in ("decl", "Im_A", "Isd_A", "Isd_multiplu", "tsd_s", "Ii_A"):
            if qg.get(k) is not None:
                rz["QG"][k] = qg[k]
        for k in ("Ir_fortat", "Isd_fortat"):
            if qg.get(k):
                rz["QG"][k] = True
        if qcfg.get("motorizat"):
            rz["QG"]["motorizat"] = True
        if idn_qg is not None:
            # v1.3 R5: bloc diferențial reglabil asociat QG (Δt explicit)
            rz["QG"]["DDR"] = {"IdN_mA": idn_qg, "tip": "A", "selectiv": True, "temporizare": "reglabil", "dt_s": DT_QG,
                               "reglabil": True, "poli": "2P" if mono else "4P", "In_A": In, "aparat": "bloc_diferential",
                               "asociat": "QG", "tip_q": tip}
        j.pas(f"{oqg}: Ip,min = max(Σ Iac {fmt_ro(s_iac_s)}; Ip max invertor {fmt_ro(max(ip_inv) if ip_inv else 0)}) = "
              f"{fmt_ro(ip_min)} A → {tip} {In} A, Ir {fmt_ro(qg['Ir_A'])} A")
        if in_f is not None and In not in pr.SERII[tip]:
            emite(j, "V05", BLOCANT, oqg, In=In, tip=tip, vecini="")
        if lt(pr.ip(qg), s_iac_s):
            emite(j, "V65", BLOCANT, "schema" if not suf else oqg, x=pr.ip(qg), y=s_iac_s)
        if not ok:
            emite(j, "V33", BLOCANT, oqg, icu=qg["Icu_kA"], ik3=ctx_s["Ik3_kA"])
        if t is not None and q_pt is not None:
            # r8 (P1 selectivitate): QG și Q JT al trafo în serie pe C0 — reglajele cresc spre amonte (Ir Q JT ≥ Ir QG);
            # Q JT se poate ridica până la 1,1·In_T (DECIZIE) dacă Σ Iac ≤ In_T, altfel V41 AVERTISMENT „inversat”
            n_par = 1 if sectii_pt else n_t
            _selectivitate_qg_qjt(j, qg, q_pt, rez["PT"], t, s_iac_s, n_par, f"{oqg} / QJT{'' if tgd else suf}")
            sum_qjt = n_par * pr.ip(q_pt)
            if gt(s_iac if tgd else s_iac_s, sum_qjt):
                emite(j, "V60", AVERTISMENT, "schema" if not suf else oqg, "sigma", x=round(s_iac_s, 1), y=sum_qjt, n=n_par)
            if n_par == 1 and lt(pr.ip(q_pt), norme.RAPORT_SELECTIVITATE_SUPRASARCINA * pr.ip(qg)) and q_pt.get("decl") == "EL":
                t_qjt = round(max((qg.get("tsd_s") or 0.0) + 0.1, q_pt.get("tsd_s") or 0.0), 2)
                q_pt["tsd_s"] = t_qjt
                rez["PT"]["Q_JT"]["tsd_s"] = t_qjt
                emite(j, "V41", INFO, f"{oqg} / Q JT", "pt_serie", a=pr.ip(qg), b=pr.ip(q_pt), t=t_qjt)
        elif t is not None and gt(qg["Ir_A"], n_t * t["In_T_A"]):
            emite(j, "V60", AVERTISMENT, "schema", "AV", x=qg["Ir_A"], y=n_t * t["In_T_A"])
        # M4 (v1.2): racord JT prin BMPT/BMPM — QG trebuie să se coordoneze cu Q din bloc (In Q max 250 A / 40 A)
        if racord and racord.get("In_Q_max_A") is not None and gt(pr.ip(qg), racord["In_Q_max_A"]):
            emite(j, "V66", BLOCANT, "schema", "bmpt", x=pr.ip(qg), y=racord["In_Q_max_A"])

        # v1.3 (P0-2): protecția existentă din TG pe care se leagă QG (opțională)
        q_tg = _q_tg_existent(inp, j, ctx_s, s_iac_s) if tg else None
        if q_tg is not None:
            rz["Q_TG"] = {k: q_tg.get(k) for k in ("tip", "In_A", "Ir_A", "curba", "Icu_kA") if q_tg.get(k) is not None}
        if not tg and (rez.get("trafo") or {}).get("existent"):
            # r9 (fotovoltaic #41, #42): PT existent — plecarea NOUĂ din tabloul JT al PT-ului (Q_PT la capătul sursă al
            # C0): Ir ≥ Ir QG (amonte ≥ aval), Icu ≥ Ik3 bara; C0 e protejat la ambele capete
            q_tg = _q_plecare_pt_existent(inp, j, ctx_s, qg, s_iac_s)
            if q_tg is not None:
                rz["Q_PT"] = {k: q_tg.get(k) for k in ("tip", "In_A", "Ir_A", "Ir_multiplu", "Icu_kA", "decl", "Isd_A",
                                                         "Isd_multiplu", "Ii_A", "Im_A") if q_tg.get(k) is not None}

        # v1.3 (P0-2): cablul C0 (TGD-CF → punctul de racord) — ramură completă, protejată de QG, Ik din punctul de racord
        ctx_inv = ctx_s
        pt_nou = rez.get("PT")
        if pt_nou and L0 is None:
            j.presupune("legătura JT T1 → TGD-CF (C0) nedimensionată — lungimea nedeclarată (introduceți L_racord_m)")
        if L0 is not None:
            cab0 = {k: v for k, v in (inp.get("cablu") or {}).items() if k in CAMPURI_CABLU_SCHEMA and v is not None}
            cab0.update({k: v for k, v in (inp.get("cablu_C0") or {}).items() if v is not None and k != "tronsoane"})
            cb.metoda_implicita(cab0, "D1")
            if cab0.get("material") is None:
                cab0["material"] = "Al" if cab0["metoda"] in norme.METODE_IN_PAMANT else "Cu"
                cab0["material_implicit"] = True
                j.presupune(f"cablu C0 {cab0['material']} PVC, metoda {cab0['metoda']}")
            cab0["L"] = float(L0)
            r0 = {"rol": "c0", "receptor": "invertor", "retea": retea, "Pn_kW": pn_s, "Iac_max_A": s_iac_s,
                  "cablu": cab0, "prot_tip": tip, "In_fortat": In, "Icu_fortat": qg["Icu_kA"], "are_aval": True,
                  "_validat": True}
            if qg.get("curba"):
                r0["curba"] = qg["curba"]
            if qg.get("decl"):
                r0["decl_fortat"] = qg["decl"]
            if qg.get("Ir_A") is not None and qg.get("tip") in ("MCCB", "ACB"):
                r0["Ir_fortat"] = qg["Ir_A"]          # r12: același reglaj Ir pe QG și în calculul C0
            if qg.get("Isd_fortat"):
                r0["Isd_fortat"] = qg["Isd_A"]
            tr0 = (inp.get("cablu_C0") or {}).get("tronsoane")
            if isinstance(tr0, list) and tr0:
                rr0 = _c0_tronsoane(inp, j, r0, tr0, ctx_s, oc0, q_tg, tg)
                if rr0 is None:
                    return None
            else:
                rr0 = None
            # (PT nou: Q JT al trafo și QG sunt în serie pe același curent de injecție — fără verificare de selectivitate;
            # C0 se alimentează la defect din ambele capete, protejat de QG și de Q JT)
            if rr0 is None:
                rr0 = calculeaza_ramura(r0, ctx_s, j, oc0, amonte=q_tg, obiect_sel="Q TG vs QG" if tg else f"Q PT vs {oqg}")
            if not rr0["blocat"] and qg.get("decl") == "EL" and not qg.get("Isd_fortat"):
                # r12: Isd al QG ales după Ik1min la capătul C0 (bara TGD-CF) — același reglaj pe planșă și în V30
                p0 = rr0["rezultat"].get("protectie") or {}
                if p0.get("Isd_A") is not None:
                    qg["Isd_A"], qg["Isd_multiplu"] = p0["Isd_A"], p0.get("Isd_multiplu")
                    rz["QG"].update(Isd_A=p0["Isd_A"], Isd_multiplu=p0.get("Isd_multiplu"))
            rz["C0"] = dict(rr0["rezultat"], descriere=f"TGD-CF{suf} → " + ("TG existent" if tg else
                                                                           f"bara JT a PT (T{suf or 1})" if pt_nou
                                                                           else "punctul de racord"))
            if not rr0["blocat"]:
                ctx_inv = dict(rr0["ctx_aval"], dU_cef_pct=rr0["rezultat"]["dU_cumulat_pct"])
                rz["bara_TGD_CF"] = {"Ik3max_kA": ctx_inv["Ik3_kA"], "dU_pct": rr0["rezultat"]["dU_cumulat_pct"]}
                if q_tg is not None:
                    if rz.get("Q_PT") and q_tg.get("decl") == "EL":
                        # r9: Q PT nou — Isd ales după Ik1min la capătul C0 (bara TGD-CF), ca să deconecteze defectul
                        pr.alege_isd(q_tg, rr0["rezultat"]["Ik1min_capat_A"])
                        rz["Q_PT"].update({k: q_tg[k] for k in ("Isd_A", "Isd_multiplu") if q_tg.get(k) is not None})
                    _verifica_q_tg_c0(j, q_tg, rr0["rezultat"], ctx_s)
        elif tg and q_tg is not None:
            pr.selectivitate(q_tg, qg, ctx_s["Ik3_kA"], "Q TG vs QG", j)

        # invertoare și PCS (pct. 1) — cu contextul barei TGD-CF (capătul C0, dacă există)
        ramuri = []
        ctx_u = {}
        if cascada:
            # r12: plecările tablourilor intermediare din bara TEG (protecție la ambele capete, același calibru) →
            # bara fiecărui tablou intermediar (Ik, ΔU cumulat C0 + C-TEk) → invertoarele lui
            rz["tablouri_intermediare"] = []
            for te in cascada:
                k = te["k"]
                rr_t = calculeaza_ramura(ramura_te(te), ctx_inv, j, f"C-TE{k}")
                zt = {"nr": k, "nume": te["nume"], "unitati": [u["obiect"] for u in te["unitati"]],
                      "sume": {"Pn_total_kW": te["pn"], "Iac_total_A": te["iac"]}}
                if te["spec"].get("IP"):
                    zt["IP"] = te["spec"]["IP"]
                if isinstance(rr_t.get("rezultat"), dict):
                    zt["C"] = dict(rr_t["rezultat"], descriere=f"{te['nume']} → bara TEG")
                    zt["Q"] = rr_t["rezultat"].get("protectie")
                rz["tablouri_intermediare"].append(zt)
                if rr_t["blocat"]:
                    ctx_t = ctx_inv
                    # protecția declarată rămâne desenată (planșa blocată arată ce a cerut proiectantul)
                    sp_ = te["spec"]
                    tq = pr.normalizeaza_tip(sp_.get("prot_tip")) if sp_.get("prot_tip") else None
                    if tq and sp_.get("In_A"):
                        zt["Q"] = {"tip": tq, "In_A": sp_["In_A"], "declarat": True}
                else:
                    _selectivitate_qg(qg, rr_t["prot"], ctx_inv["Ik3_kA"], f"QF{k}", j, len(cascada) + len(direct), oqg)
                    ctx_t = dict(rr_t["ctx_aval"], dU_cef_pct=rr_t["rezultat"]["dU_cumulat_pct"])
                    zt["bara"] = {"Ik3max_kA": ctx_t["Ik3_kA"], "dU_pct": rr_t["rezultat"]["dU_cumulat_pct"]}
                te["prot"] = None if rr_t["blocat"] else rr_t["prot"]
                for u in te["unitati"]:
                    ctx_u[u["obiect"]] = (ctx_t, te)
        for u in unit_s:
            c_u, te_u = ctx_u.get(u["obiect"], (ctx_inv, None))
            rr = calculeaza_ramura(ramura_unitate(u), c_u, j, u["obiect"])
            if te_u is not None and isinstance(rr.get("rezultat"), dict):
                rr["rezultat"]["tablou"] = te_u["k"]
            if isinstance(rr.get("rezultat"), dict):
                rr["rezultat"].setdefault("obiect", u["obiect"])
                if u["pcs"]:
                    rr["rezultat"].setdefault("Pn_kW", u["Pn_kW"])
            if u.get("retea") == "mono" and not mono:
                rr["rezultat"]["retea"] = "mono"
                rr["rezultat"]["faza"] = u.get("faza")
            if suf:
                rr["rezultat"]["sectie"] = int(suf)
            ramuri.append((u, rr))
        rz["invertoare"] = [rr["rezultat"] for u, rr in ramuri if not u["pcs"]]
        pcs_l = [rr["rezultat"] for u, rr in ramuri if u["pcs"]]
        if pcs_l:
            rz["PCS"] = pcs_l[0]
            if len([u for u in unitati if u["pcs"]]) > 1:
                rz["PCS_lista"] = pcs_l
        for u, rr in ramuri:
            c_u, te_u = ctx_u.get(u["obiect"], (ctx_inv, None))
            if not rr["blocat"] and te_u is not None:
                if te_u.get("prot") is not None:
                    _selectivitate_qg(te_u["prot"], rr["prot"], c_u["Ik3_kA"], u["obiect"], j, len(te_u["unitati"]),
                                      f"QS{te_u['k']}")
            elif not rr["blocat"]:
                _selectivitate_qg(qg, rr["prot"], ctx_inv["Ik3_kA"], u["obiect"], j, len(unit_s), oqg)
            _spd_ca_invertor(j, u["obiect"], rr, u.get("grup") if not u["pcs"] else (bess or {}))
            _ddr_invertor_mare(j, u, rr["rezultat"])
        if norme.u_n() != norme.U_N_V:
            # r7 (P0-3): 800 V c.a. — cablurile invertoarelor / PCS și C0 fără neutru (3 + PE)
            for u, rr in ramuri:
                _fara_neutru(rr["rezultat"])
            _fara_neutru(rz.get("C0"))
        if not suf:
            lim_inj = _limitare_injectie(inp, j, rez, pn_tot, len(unitati), retea)
            # r6 (fotovoltaic P1-10): Σ Iac față de calibrul Q din BMPT / branșamentul existent (`In_Q_bransament_A`)
            _verifica_iac_q_existent(inp, j, s_iac, lim_inj, pr.ip(qg))

        # TC măsură (pct. 8, B.19) — la monofazat măsura e directă (BMPM, contor furnizat de OD)
        if mono:
            rz["contor"] = "monofazat direct 230 V, bidirecțional (furnizat și montat de OD)"
        elif masura == "MT":
            # r7: măsura de decontare în celula de măsură MT a PT-ului (existent sau nou) — fără TC de decontare pe JT
            rez["masura"] = {"loc": "MT"}
            rez["contor"] = "contor de decontare pe MT (TT + TC MT în celula de măsură), furnizat și sigilat de OD"
            if not pt_nou and not suf:
                j.presupune("măsura de decontare în celula de măsură MT a PT-ului existent (nedesenată) — conform ATR")
        elif tgd:
            pass            # r11: măsura de decontare e una singură, la punctul de racord comun (după bucla TGD-CF)
        else:
            p = prima_din_serie(norme.TC_PRIMAR_A, max(s_iac_s, In / norme.TC_FACTOR_EXTINDERE))
            if p is None:
                emite(j, "V55", BLOCANT, f"TC{suf}", "B", Ib=s_iac_s, p=max(norme.TC_PRIMAR_A))
            else:
                rz["TC"] = f"3 {X} {p}/5{NB}A, cl. 0,5S"
                rz["TC_primar_A"] = p
        return qg

    if sectii_pt:
        grupe = _repartitie_sectii(unitati, n_t, j)
        rez["sectii"] = []
        for k, unit_s in enumerate(grupe, 1):
            rz = {"sectie": k, "trafo": f"T{k}"}
            rez["sectii"].append(rz)
            if not unit_s:
                emite(j, "V07", BLOCANT, f"TGD-CF{k}", "plecari", tablou=f"secția {k} (T{k})")
                j.verificari[-1]["remediere"] = "mai multe invertoare (repartizate pe ambele trafo) sau PT cu un singur trafo"
                continue
            if sectiune(unit_s, str(k), ctx_pcc, rz) is None:
                return rez
        rez["invertoare"] = [x for rz in rez["sectii"] for x in rz.get("invertoare") or []]
        pcs_l = [x for rz in rez["sectii"] for x in (rz.get("PCS_lista") or ([rz["PCS"]] if rz.get("PCS") else []))]
        if pcs_l:
            rez["PCS"] = pcs_l[0]
            if len(pcs_l) > 1:
                rez["PCS_lista"] = pcs_l
        lim_inj = _limitare_injectie(inp, j, rez, pn_tot, len(unitati), retea)
        qg = None
    elif tgd:
        grupe = [[] for _ in range(n_tgd)]
        fara = [u for u in unitati if (u.get("grup") or {}).get("tgd") is None and not u["pcs"]]
        pcs_u = [u for u in unitati if u["pcs"]]
        for u in unitati:
            x = (u.get("grup") or {}).get("tgd")
            if x is not None and not u["pcs"]:
                grupe[int(x) - 1].append(u)
        if fara:
            # repartiția nedeclarată: tranșe consecutive de putere cât mai egală (ca la secțiile PT), declarat
            for k, g_ in enumerate(_repartitie_sectii(fara, n_tgd, Jurnal())):
                grupe[k].extend(g_)
            j.presupune(f"invertoarele fără `tgd` repartizate pe cele {n_tgd} TGD-CF în tranșe de putere egală — declarați "
                        f"invertoare[].tgd")
        tb = (bess or {}).get("tgd") if isinstance(bess, dict) else None
        for u in pcs_u:
            grupe[(int(tb) - 1) if _numar(tb) and 1 <= tb <= n_tgd else 0].append(u)
        rez["tgd_cf"] = []
        for k, unit_s in enumerate(grupe, 1):
            rz = {"tgd": k}
            rez["tgd_cf"].append(rz)
            if not unit_s:
                emite(j, "V07", BLOCANT, f"TGD-CF{k}", "plecari", tablou=f"TGD-CF{k}")
                j.verificari[-1]["remediere"] = f"invertoare pe TGD-CF{k} (invertoare[].tgd = {k}) sau n_tgd_cf mai mic"
                continue
            if sectiune(unit_s, str(k), ctx_pcc, rz) is None:
                return rez
        j.pas(f"{n_tgd} tablouri TGD-CF, fiecare cu QGk → C0.k spre bara de racord comună; Σ Iac = {fmt_ro(s_iac)} A")
        if L0 is not None and inp.get("L_racord_m") is not None:
            j.presupune(f"aceeași lungime C0 ({fmt_ro(float(L0), 0)} m) pentru toate cele {n_tgd} TGD-CF")
        rez["invertoare"] = [x for rz in rez["tgd_cf"] for x in rz.get("invertoare") or []]
        pcs_l = [x for rz in rez["tgd_cf"] for x in (rz.get("PCS_lista") or ([rz["PCS"]] if rz.get("PCS") else []))]
        if pcs_l:
            rez["PCS"] = pcs_l[0]
            if len(pcs_l) > 1:
                rez["PCS_lista"] = pcs_l
        lim_inj = _limitare_injectie(inp, j, rez, pn_tot, len(unitati), retea)
        q_max = max(pr.ip(rz["QG"]) for rz in rez["tgd_cf"] if rz.get("QG"))
        _verifica_iac_q_existent(inp, j, s_iac, lim_inj, q_max)
        if masura != "MT" and not mono:
            p = prima_din_serie(norme.TC_PRIMAR_A, s_iac)
            if p is None:
                emite(j, "V55", BLOCANT, "TC", "B", Ib=s_iac, p=max(norme.TC_PRIMAR_A))
            else:
                rez["TC"] = f"3 {X} {p}/5{NB}A, cl. 0,5S"
                rez["TC_primar_A"] = p
        if racord and racord.get("In_Q_max_A") is not None and gt(s_iac, racord["In_Q_max_A"]):
            emite(j, "V66", BLOCANT, "schema", "bmpt", x=s_iac, y=racord["In_Q_max_A"])
        qg = None
    else:
        qg = sectiune(unitati, "", ctx_pcc, rez)
        if qg is None:
            return rez

    # c.c. (pct. 9) — stringul comun (`string`) și, v1.8, stringurile / modulele proprii ale grupurilor de invertoare
    grupuri = [g for g in inp.get("invertoare") or [] if isinstance(g, dict)]
    proprii = [i for i, g in enumerate(grupuri) if isinstance(g.get("string"), dict) or isinstance(g.get("modul"), dict)]
    ok = _parte_cc(dict(inp, invertoare=[g for i, g in enumerate(grupuri) if i not in proprii]), j, rez, "cef")
    _ucpv_sistem(rez, [g for i, g in enumerate(grupuri) if i not in proprii], j)
    cc = []
    for i, g in enumerate(grupuri):
        if i in proprii:
            st_g = dict(st_original or {})
            st_g.update(g.get("string") or {})
            tmp = {"string": st_g, "invertoare": [g], "modul": g.get("modul") if isinstance(g.get("modul"), dict) else inp.get("modul")}
            fise.aplica(tmp, j, "cef")
            sub = {}
            ok = _parte_cc(tmp, j, sub, "cef", obiect=f"grup INV {i + 1}") and ok
            _ucpv_sistem(sub, [g], j)
        else:
            st_g, sub = inp.get("string") or {}, {k: rez[k] for k in ("Voc_Tmin_V", "Umax_inv_V", "SPD_cc_Ucpv_V", "gPV_In_A",
                                                                       "gPV_generic", "string_generic") if k in rez}
        sub.pop("Uoc_Tmin_V", None)
        n_mppt = st_g.get("n_MPPT") or (g.get("nr_MPPT") if st_g.get("n_stringuri_paralel") else None) or 1
        sub.update({k: st_g[k] for k in ("n_module", "n_stringuri_paralel") if st_g.get(k) is not None}, n_MPPT=int(n_mppt))
        cc.append(sub)
    if cc:
        rez["cc_grupuri"] = cc
        # v1.8: puterea c.c. din stringuri (module × stringuri × MPPT × Pmax din fișă) față de kWp declarat
        kwp_s, complet = 0.0, True
        for g, c_ in zip(grupuri, cc):
            md = g.get("modul") if isinstance(g.get("modul"), dict) else (fise.modul_din(inp) or {})
            if c_.get("n_module") and c_.get("n_stringuri_paralel") and md.get("Pmax_W"):
                kwp_s += int(g.get("n", 1)) * c_["n_module"] * c_["n_stringuri_paralel"] * c_["n_MPPT"] * md["Pmax_W"] / 1000.0
            else:
                complet = False
        if complet and kwp_s > 0:
            rez["kWp_stringuri"] = kwp_s
            if inp.get("kWp") and abs(kwp_s - float(inp["kWp"])) > 0.05 * float(inp["kWp"]):
                emite(j, "V89", AVERTISMENT, "schema", "kwp", x=round(kwp_s, 2), y=inp["kWp"])
        if "Uoc_Tmin_V" not in rez and any(c.get("Voc_Tmin_V") for c in cc):
            w = max((c for c in cc if c.get("Voc_Tmin_V")), key=lambda c: c["Voc_Tmin_V"])
            rez["Uoc_Tmin_V"] = rez["Voc_Tmin_V"] = w["Voc_Tmin_V"]
            rez["Umax_inv_V"] = w.get("Umax_inv_V")
    if not _cablu_cc(inp, j, rez):
        return rez
    if not ok:
        return rez
    _nota_spl(rez, inp, "cef")
    return rez


# r11 (panoul de confirmare `cablu_cc`): cablu solar H1Z2Z2-K (SR EN 50618), Iz monopolar în aer liber la 60 °C,
# pozat pe structură (tabel A.3 EN 50618 [VERIFICAT: raport #18]; fără factori de grupare — DECIZIE proiectant 28.10.2026, Î12)
IZ_CABLU_SOLAR_A = {1.5: 30, 2.5: 41, 4: 55, 6: 70, 10: 98, 16: 132, 25: 176, 35: 218}
RHO_CU_70 = 0.0225      # Ω·mm²/m la ~70 °C


def _cablu_cc(inp, j, rez):
    """Cablul c.c. impus (`cablu_cc`: S_fortat [mm²], L_m [m] dus, material Cu) pe circuitul string → invertor:
    Iz ≥ 1,25·Isc·n_paralel (SR HD 60364-7-712) și ΔU c.c. ≤ 1 % la Umpp. Fără Isc din fișă → BLOCANT (nu se
    desenează un cablu neverificat). Întoarce False dacă a blocat."""
    c = inp.get("cablu_cc")
    if c is None:
        return True
    if not isinstance(c, dict) or not _numar(c.get("S_fortat")):
        emite(j, "V07", BLOCANT, "cablu c.c.", "param", camp="cablu_cc.S_fortat", x=repr(c)[:40],
              conditie="secțiunea cablului solar (mm²)")
        return False
    S = float(c["S_fortat"])
    if str(c.get("material") or "Cu").capitalize() != "Cu":
        emite(j, "V96", BLOCANT, "cablu c.c.", ce="cablu c.c. din aluminiu", detaliu="motorul verifică doar cablu solar Cu "
              "H1Z2Z2-K", remediere="cablu solar Cu H1Z2Z2-K sau verificare separată")
        return False
    st = inp.get("string") if isinstance(inp.get("string"), dict) else {}
    md = fise.modul_din(inp) or {}
    isc = st.get("Isc_A") or md.get("Isc_A")
    npar = int(st.get("n_stringuri_paralel") or 1)
    if not isc:
        emite(j, "V07", BLOCANT, "cablu c.c.", "param", camp="string.Isc_A", x="—",
              conditie="cablul c.c. impus nu se poate verifica fără Isc al modulului (fișă)")
        j.verificari[-1]["remediere"] = "fișa modulului (Isc_A) sau string.Isc_A"
        return False
    ib = 1.25 * float(isc) * npar
    iz = IZ_CABLU_SOLAR_A.get(S)
    rez["cablu_cc"] = {"S_mm2": S, "L_m": c.get("L_m", c.get("L")), "Iz_A": iz, "Ib_A": ib, "tip": c.get("tip_cablu") or "H1Z2Z2-K"}
    j.presupune("cablu c.c. H1Z2Z2-K monopolar pe structură, în aer, 60 °C, fără grupare (Iz tabel EN 50618)")
    if iz is None:
        emite(j, "V05", BLOCANT, "cablu c.c.", In=S, tip="cablu solar (mm²)", vecini="4 / 6 / 10 mm²")
        return False
    if lt(iz, ib):
        j.emite("V02", BLOCANT, "cablu c.c.", f"cablu c.c. {fmt_ro(S)} mm²: Iz {fmt_ro(iz)} A < 1,25·Isc·n = {fmt_ro(ib)} A",
                f"secțiune ≥ {next((k for k, v in sorted(IZ_CABLU_SOLAR_A.items()) if v >= ib), 35)} mm²")
    L = c.get("L_m", c.get("L"))
    nm, vmp = st.get("n_module"), md.get("Vmpp_V")
    if _numar(L) and nm and vmp:
        du = 2 * float(L) * (ib / 1.25) * RHO_CU_70 / S / (float(nm) * float(vmp)) * 100.0
        rez["cablu_cc"]["dU_pct"] = du
        j.pas(f"Cablu c.c. {fmt_ro(S)} mm², L {fmt_ro(L, 0)} m: Iz {fmt_ro(iz)} A ≥ {fmt_ro(ib)} A; ΔU c.c. = {fmt_ro(du)} %")
        if gt(du, 1.0):
            j.emite("V03", AVERTISMENT, "cablu c.c.", f"ΔU c.c. {fmt_ro(du, 2)} % > 1 % (pierderi pe partea c.c.)",
                    "secțiune mai mare sau traseu mai scurt")
    else:
        j.presupune("ΔU pe cablul c.c. neverificată (lipsesc L, numărul de module pe string sau Vmpp)")
    return True


def _repartitie_sectii(unitati, n_t, j):
    """r8 (CEF cu PT nou de n trafo): grupurile de invertoare / PCS pe secțiile de bare JT (câte una pe trafo). Secția
    declarată pe grup (`invertoare[].sectie`, `bess.sectie`: 1…n) se respectă; restul, în ordinea listei (grupurile
    identice rămân alăturate), se împart în tranșe consecutive de putere cât mai egală (DECIZIE). Întoarce n liste."""
    out = [[] for _ in range(n_t)]
    libere = []
    for u in unitati:
        d = (u.get("grup") or {}).get("sectie") if not u["pcs"] else None
        try:
            d = int(d) if d is not None else None
        except (TypeError, ValueError):
            d = None
        if d is not None and 1 <= d <= n_t:
            out[d - 1].append(u)
        else:
            libere.append(u)
    if libere:
        p = [sum(x["Pn_kW"] for x in o) for o in out]
        tot = sum(p) + sum(u["Pn_kW"] for u in libere)
        tinta = tot / n_t
        k = 0
        for u in libere:
            while k < n_t - 1 and (gt(p[k] + u["Pn_kW"] / 2.0, tinta) and p[k] > 0):
                k += 1
            out[k].append(u)
            p[k] += u["Pn_kW"]
        j.presupune("invertoarele repartizate automat pe secțiile de bare / trafo, cu puteri cât mai egale: "
                    + "; ".join(f"T{i + 1}: {', '.join(u['obiect'] for u in o) or '—'}" for i, o in enumerate(out))
                    + " — declarați invertoare[].sectie dacă repartiția e alta")
    for o in out:
        o.sort(key=lambda u: unitati.index(u))
    return out


def _selectivitate_qg_qjt(j, qg, q_pt, rez_pt, t, s_iac, n_par, obiect):
    """r8 (P1 selectivitate inversată): Q JT al trafo (amonte, spre rețea) reglat sub QG (aval) — reglajele trebuie să
    crească spre amonte. La n trafo în paralel (PT existent) Q JT-urile împart curentul (Σ Ir). Dacă Ir QG > Ir Q JT:
    Q JT se ridică la cea mai mică treaptă ≥ Ir QG (eventual calibrul următor) cât timp Ir Q JT ≤ 1,1·In_T și Σ Iac ≤ In_T
    (DECIZIE, norme.Q_JT_IR_MAX_IN_T) — V41 INFO; altfel V41 AVERTISMENT cu remediere (nu planșă „curată”)."""
    a = pr.ip(qg)
    b = n_par * pr.ip(q_pt)
    if not lt(b, a):
        return
    in_t = t["In_T_A"]
    sub_inj = gt(s_iac, n_par * in_t)     # trafo sub injecția maximă — V67 / V60 spun cauza
    lim = norme.Q_JT_IR_MAX_IN_T * in_t
    tinta = a / n_par
    ales = None
    # r9 (fotovoltaic #17, #52, 800 V): reglajele rămân ordonate (Ir Q JT ≥ Ir QG) și când trafo e sub injecție —
    # planșa blocată de V67 nu arată o selectivitate inversată care ar reapărea la mărirea trafo-ului
    if not gt(tinta, lim):
        tip = q_pt["tip"]
        for In in [x for x in pr.SERII[tip] if ge(x, q_pt["In_A"])]:
            trepte = norme.IR_TREPTE["MCCB_TM"] if pr.declansator(tip, In) == "TM" else norme.IR_TREPTE["MCCB_EL"]
            k = next((k for k in trepte if ge(k * In, tinta)), None)
            if k is not None and not gt(k * In, lim):
                ales = (In, k)
                break
    if ales is None:
        if sub_inj:
            return      # trafo sub injecția maximă: V67 / V60 „sigma” spun deja cauza (nu un al doilea mesaj)
        emite(j, "V41", AVERTISMENT, obiect, "inversat", a=a, b=b, lim=round(n_par * lim, 1), k=norme.Q_JT_IR_MAX_IN_T)
        j.verificari[-1]["remediere"] = ("trafo mai mare (In_T ≥ Ir QG), QG reglat mai jos (In_QG_A) sau invertoare cu Iac "
                                         "mai mic — reglajele trebuie să crească spre amonte (QG ≤ Q JT ≤ 1,1·In_T)")
        return
    In, k = ales
    q_pt["In_A"] = In
    q_pt["Ir_multiplu"] = k
    q_pt["Ir_A"] = k * In
    if q_pt.get("decl") == "EL" and t.get("Ik1min_bara_A"):
        pr.alege_isd(q_pt, t["Ik1min_bara_A"])
    for kk in ("In_A", "Ir_A", "Ir_multiplu", "Isd_A", "Isd_multiplu"):
        if q_pt.get(kk) is not None:
            rez_pt["Q_JT"][kk] = q_pt[kk]
    emite(j, "V41", INFO, obiect, "ordonat", a=a, b=n_par * q_pt["Ir_A"], lim=round(n_par * lim, 1),
          k=norme.Q_JT_IR_MAX_IN_T, i=round(s_iac, 1))


def _ucpv_sistem(rez, grupuri, j):
    """r7 (P0-3): SPD c.c. dimensionat după tensiunea maximă a sistemului — fără Voc(Tmin) calculat (string nedescris),
    Ucpv ≥ Umax c.c. al invertorului (fișă / catalog: 1100 V sau 1500 V); cu Voc calculat, cel puțin treapta lui."""
    um = [float(g["Umax_dc_V"]) for g in grupuri if isinstance(g, dict) and g.get("Umax_dc_V")]
    if not um:
        return
    u = prima_din_serie(norme.SPD_CC_UCPV_V, max(um)) or max(norme.SPD_CC_UCPV_V)
    if rez.get("SPD_cc_Ucpv_V") is None or (rez.get("Voc_Tmin_V") is None and lt(rez["SPD_cc_Ucpv_V"], u)):
        rez["SPD_cc_Ucpv_V"] = u
        j.pas(f"SPD c.c.: Ucpv {fmt_ro(u, 0)} V ≥ Umax c.c. al invertorului {fmt_ro(max(um), 0)} V (sistem "
              f"{'1500' if max(um) > 1100 else '1000/1100'} V c.c.)")


def _selectivitate_qg(qg, prot, ik_kA, obiect, j, n_unitati, nume="QG"):
    """r7 (P1): QG față de protecția unui invertor / PCS. Cu un singur generator, QG și Q-ul lui sunt în serie pe același
    curent de injecție — V41 INFO (selectivitatea nu e necesară), nu AVERTISMENT „amonte = aval” generat de aplicație."""
    if n_unitati == 1 and not lt(pr.ip(qg), pr.ip(prot)):
        emite(j, "V41", INFO, f"{nume} vs {obiect}", "un_generator", a=pr.ip(qg), b=pr.ip(prot))
        return
    pr.selectivitate(qg, prot, ik_kA, f"{nume} vs {obiect}", j)


def _verifica_iac_q_existent(inp, j, iac, lim=None, ip_qg=None):
    """r6 (fotovoltaic P1-10): curentul injectat (Σ Iac, sau curentul limitat de EMS) față de calibrul Q din BMPT /
    branșamentul existent (`In_Q_bransament_A`) — V72, la CEF și la prosumator. Peste calibru, Q-ul existent declanșează
    la injecția maximă: limitarea injecției (EMS / setare invertor) sau ATR nou cu Q mai mare."""
    inq = inp.get("In_Q_bransament_A")
    if inq is None:
        return
    i_inj = min(iac, lim["I_inj_A"]) if lim else iac
    if gt(i_inj, float(inq)):
        emite(j, "V72", AVERTISMENT, "schema", "AV", x=i_inj, y=inq)
    else:
        emite(j, "V72", INFO, "schema", "INFO", x=i_inj, y=inq)


def _masura_cef(inp, j, sn):
    """r7 (fotovoltaic P1): locul măsurii de decontare a CEF — `masura` „MT” (celulă de măsură MT în PT-ul propriu, TT + TC
    MT, contor pe MT) sau „JT” (TC + contor semidirect în TGD-CF, implicit). `celule_mt` cu „masura” ⇒ MT.
    MT fără PT propriu → BLOCANT. Întoarce "MT" / "JT" sau False (schema se oprește)."""
    m = inp.get("masura", inp.get("masura_pt"))
    cel = inp.get("celule_mt")
    cel_m = (isinstance(cel, dict) and bool(cel.get("masura"))) or \
        (isinstance(cel, (list, tuple)) and any(isinstance(x, str) and _fd(x) == "masura" for x in cel))
    if m is None:
        if cel_m and sn is not None:
            return "MT"
        if sn is not None and _bool(inp.get("pt_existent")) is not True and inp.get("racord") != "tg_existent" \
                and not inp.get("atr_jt"):
            # echipa1 P1-9: PT propriu NOU = racord în MT — măsura de decontare și PI pe MT (celulă de măsură, QI cu 59N)
            j.presupune("CEF cu PT propriu nou → racord în MT: măsura de decontare în celula de măsură MT și protecția de "
                        "interfață pe MT (27/59/59N/81); declarați măsura „JT” dacă ATR o cere pe JT")
            return "MT"
        return "JT"
    mm = _fd(m) if isinstance(m, str) else ""
    mm = "MT" if mm in ("mt", "medie_tensiune", "celula_masura") else "JT" if mm in ("jt", "joasa_tensiune") else None
    if mm is None:
        emite(j, "V12", BLOCANT, "schema", "camp", camp="masura", valoare=m)
        j.verificari[-1]["remediere"] = "masura „MT” (celulă de măsură în PT propriu) sau „JT” (TC + contor în TGD-CF)"
        return False
    if mm == "MT" and sn is None:
        _contradictie(j, BLOCANT, "schema", "măsura pe MT cerută, dar CEF nu are PT propriu (racord JT)",
                      "PT propriu (pt_Sn_kVA) cu celulă de măsură MT sau măsura „JT”")
        return False
    return mm


def _q_jt_cef(in_t, ik3_kA, in_fortat=None):
    """r7 (P1 selectivitate): Q JT al unui trafo CEF — calibrul ≥ In_T, Ir reglat la cea mai mare treaptă ≤ In_T
    (trafo protejat la suprasarcină, fără V60 generat de aplicație); Ir impus de calibru (In_Q_JT_A) dacă nu se poate."""
    q = _q_trafo(in_t, ik3_kA, in_fortat)
    if q is None or q.get("Ir_A") is None or not gt(q["Ir_A"], in_t):
        return q
    trepte = norme.IR_TREPTE["MCCB_TM"] if q.get("decl") == "TM" else norme.IR_TREPTE["MCCB_EL"]
    jos = [k for k in trepte if ge(in_t, k * q["In_A"])]
    if jos:
        q["Ir_multiplu"] = jos[-1]
        q["Ir_A"] = jos[-1] * q["In_A"]
    return q


def _pt_nou_cef(inp, j, sn, t, n_t=1, masura="JT"):
    """r6 (fotovoltaic P0-2): PT propriu NOU al CEF — celula MT de linie, celula trafo (separator de sarcină + siguranțe MT
    ≤ 630 kVA, întreruptor + releu 50/51 peste), T1 20/0,4 kV în post și Q JT al trafo (Ip,min = In_T, Icu ≥ Ik3 bara).
    TGD-CF se leagă la bara JT a postului prin C0. r7: `n_t` trafo identice (câte o celulă trafo și un Q JT pe fiecare,
    bare JT cu cuplă), Ir Q JT ≤ In_T, celula de măsură MT (`masura` „MT”). Întoarce (rezultat, protecția Q JT)."""
    izt = inp.get("trafo_izolatie") or "ulei"
    r = {"Sn_kVA": sn, "In_T_A": t["In_T_A"], "uk_pct": t["uk_pct"], "Pk_W": t["Pk_W"], "izolatie": izt,
         "Ik3max_bara_kA": t["Ik3max_bara_kA"], "n_trafo": n_t, "U_JT_kV": norme.u_n() / 1000.0}
    cel_mt = _celule_mt(inp.get("celule_mt"), j)
    r["celule_mt"] = dict(cel_mt or {"linie": 1, "masura": False})
    if masura == "MT":
        r["celule_mt"]["masura"] = True
        r["masura"] = {"loc": "MT"}
        j.pas("măsura de decontare pe MT: celulă de măsură MT (TT + TC MT, contor de decontare) în PT-ul propriu — "
              "fără TC de decontare pe JT în TGD-CF")
    r["celula_trafo"] = _celula_trafo(sn, _celula_trafo_inp(inp), j)
    if dg_cerut(inp):
        r["dg"] = True              # r12: DG cu întreruptor + 50/51/51N + TC + tor homopolar
    for k_ in ("OD", "punct_conexiune", "cablu_MT", "compartimente"):
        if inp.get(k_) is not None:
            r[k_] = inp[k_]
    q = _q_jt_cef(t["In_T_A"], t["Ik3max_bara_kA"], inp.get("In_Q_JT_A"))
    if q is None:
        emite(j, "V06", BLOCANT, "Q JT", Ib=t["In_T_A"], tip="ACB")
        return r, None
    if q.get("decl") == "EL":
        pr.alege_isd(q, t["Ik1min_bara_A"])
    r["Q_JT"] = {k: q.get(k) for k in ("tip", "In_A", "Ir_A", "Ir_multiplu", "Icu_kA", "decl", "Im_A", "Isd_A",
                                         "Isd_multiplu", "tsd_s", "Ii_A") if q.get(k) is not None}
    if not q["icu_ok"]:
        emite(j, "V33", BLOCANT, "Q JT", icu=q["Icu_kA"], ik3=t["Ik3max_bara_kA"])
    j.pas(f"PT nou {(str(n_t) + ' × ') if n_t > 1 else ''}{sn} kVA: celula trafo {r['celula_trafo']}; "
          f"T 20/{fmt_ro(norme.u_n() / 1000.0)} kV In_T = {fmt_ro(t['In_T_A'])} A; Q JT "
          f"{q['tip']} {q['In_A']} A (Ir {fmt_ro(q['Ir_A'])} A ≤ In_T, Icu {fmt_ro(q['Icu_kA'])} kA)"
          + (f" pe fiecare trafo" if n_t > 1 else "") + "; PCC pe MT 20 kV")
    return r, q


def _e_hibrid(g):
    """r6 (fotovoltaic P0-5): invertor hibrid (port de baterie c.c.) — `hibrid` declarat sau model recunoscut din cod
    (Sungrow SH…RT / SH…T, Huawei SUN2000-…KTL-M1 / -MB0, Solis S6-EH, Fronius GEN24 …)."""
    if not isinstance(g, dict):
        return False
    h = _bool(g.get("hibrid"))
    if h is not None:
        return h
    return cat_inv.e_hibrid(g.get("producator"), g.get("model"))


def _cuplaj_bess_cef(inp, j, are_inv):
    """r6 (fotovoltaic P0-5): cuplajul BESS la CEF — `bess.cuplaj` declarat; altfel c.c. când există invertoare hibride
    și BESS nu are PCS propriu (fișă `pcs` sau sistem cu PCS: PowerStack, LUNA2000-200/215 …), c.a. în rest."""
    b = inp.get("bess") if isinstance(inp.get("bess"), dict) else None
    if b is None:
        return None
    c = b.get("cuplaj")
    if c == "cc" and not are_inv:
        j.presupune("BESS „cuplaj c.c.” fără invertoare PV — tratat ca BESS cu PCS propriu (cuplaj c.a.)")
        return "ca"
    if c in ("cc", "ca"):
        return c
    if not are_inv or isinstance(b.get("pcs"), dict) or cat_inv.bess_ca(b.get("producator"), b.get("model")):
        return "ca"
    if any(_e_hibrid(g) for g in inp.get("invertoare") or []):
        j.presupune("stocarea pe portul de baterie c.c. al invertoarelor hibride (cuplaj nedeclarat, fără PCS separat) — "
                    "declarați bess.cuplaj „ca” dacă BESS are PCS propriu")
        return "cc"
    return "ca"


def _protectie_port_baterie(j, obiect, p_kw, ub):
    """protecția c.c. a portului de baterie: Idc = P / U_nom → siguranță / întreruptor c.c. ≥ 1,25·Idc (serie
    SIGURANTE_CC_BATERIE_A). Fără U_nom → None (presupunere, conform fișei)."""
    if not ub or not p_kw:
        return None
    idc = float(p_kw) * 1000.0 / float(ub)
    In_b = prima_din_serie(norme.SIGURANTE_CC_BATERIE_A, 1.25 * idc)
    j.pas(f"Port baterie {obiect}: Idc = {fmt_ro(p_kw)} kW / {fmt_ro(ub)} V = {fmt_ro(idc)} A → "
          f"protecție c.c. {fmt_ro(In_b) if In_b else '—'} A (≥ 1,25·Idc)")
    return {"Idc_A": idc, "In_A": In_b, "U_V": float(ub)}


def _baterie_cc_pe_invertor_nehibrid(inp, j, b):
    """r10 (fotovoltaic #57): baterie pe c.c. (`bess.cuplaj: "cc"`, sau `baterie` / `baterie_kWh` la prosumator) la
    invertoare pe care catalogul le știe NE-hibride (Sungrow SG…CX, Huawei …KTL-M2/M3, …) și niciunul declarat hibrid →
    BLOCANT cu întrebare (PCS c.a. separat sau invertor hibrid), nu „hibrid + baterie c.c.” desenat fals."""
    cc = (isinstance(inp.get("bess"), dict) and inp["bess"].get("cuplaj") == "cc") or (
        inp.get("tip_schema") == "prosumator" and not isinstance(inp.get("bess"), dict)
        and (isinstance(inp.get("baterie"), dict) or inp.get("baterie_kWh") is not None)
        and (b or {}).get("cuplaj") != "ca")
    if not cc or _bool(inp.get("hibrid")):
        return False
    grupuri = [g for g in list(inp.get("invertoare") or []) + [inp.get("invertor")] if isinstance(g, dict)]
    if not grupuri or any(_e_hibrid(g) for g in grupuri):
        return False
    stiute = [g for g in grupuri if _bool(g.get("hibrid")) is False or cat_inv.cauta(g.get("producator"), g.get("model"))]
    if len(stiute) != len(grupuri):
        return False        # un invertor necunoscut în catalog: nu se poate afirma că e ne-hibrid
    mt = ", ".join(" ".join(str(x) for x in (g.get("producator"), g.get("model")) if x) or f"{fmt_ro(g.get('Pn_kW'))} kW"
                   for g in grupuri)
    _contradictie(j, BLOCANT, "BESS", f"baterie pe c.c., dar invertorul {mt} nu este hibrid (fără port de baterie c.c.)",
                  "baterie cu PCS / invertor de baterie separat cuplat în c.a. (bess.cuplaj „ca”) sau invertor hibrid "
                  "(ex. Sungrow SH…RT / Huawei …KTL-M1) — confirmați")
    j.verificari[-1]["intrebare"] = True
    return True


def _invertor_baterie_ca_cc(inp, j):
    """r7 (P1): baterie declarată „cuplaj c.c.” dar cu un invertor de baterie cuplat în c.a. (SMA Sunny Island, Sunny Boy
    Storage) — contradicție BLOCANT (nu se desenează tacit nici c.c., nici c.a.). Întoarce True dacă schema se oprește."""
    b = inp.get("bess") if isinstance(inp.get("bess"), dict) else inp.get("baterie") if isinstance(inp.get("baterie"), dict) else None
    if _baterie_cc_pe_invertor_nehibrid(inp, j, b):
        return True
    if b is None or b.get("cuplaj") != "cc":
        return False
    cand = [b, b.get("pcs"), b.get("baterie"), inp.get("invertor"), inp.get("invertor_baterie")] + list(inp.get("invertoare") or [])
    for d in cand:
        if isinstance(d, dict) and cat_inv.invertor_baterie_ca(d.get("producator"), d.get("model")):
            mt = " ".join(str(x) for x in (d.get("producator"), d.get("model")) if x)
            _contradictie(j, BLOCANT, "BESS", f"{mt} este invertor de baterie cuplat în c.a. (pe bara c.a., cu PCS propriu), "
                          f"dar cuplajul declarat este c.c.",
                          "bess.cuplaj „ca” (Sunny Island / Sunny Boy Storage pe bara c.a.) sau invertor hibrid pentru c.c.")
            return True
    return False


def _repartizare_baterie(b, la, j):
    """r7 (P1): pe ce invertoare hibride stă bateria cuplată în c.c. — `bess.la` (listă de obiecte „INV-2” / indici 1…n,
    sau un număr = primele n) > `per_invertor` / `n` = nr. de hibride (câte o baterie cu capacitatea declarată pe fiecare)
    > o baterie pe total împărțită egal pe toate hibridele (declarat în „Am presupus”). Întoarce (unități, per_invertor)."""
    sel = b.get("la")
    if sel is not None:
        if isinstance(sel, (int, float)) and not isinstance(sel, bool):
            ales = la[:max(1, int(sel))]
        else:
            lst = sel if isinstance(sel, (list, tuple)) else [sel]
            ales = [u for i, u in enumerate(la, 1) if u["obiect"] in lst or i in lst or str(i) in lst]
        if ales:
            return ales, bool(_bool(b.get("per_invertor")))
        j.presupune(f"bess.la = {sel!r} nu corespunde niciunui invertor hibrid — bateria pe toate hibridele")
    n = len(la)
    per = bool(_bool(b.get("per_invertor"))) or (b.get("n") is not None and int(b["n"]) == n and n > 1)
    return la, per


def _bess_cc_cef(inp, j, b, unitati):
    """r6 (fotovoltaic P0-5): baterii pe portul de c.c. al invertoarelor hibride ale CEF — fără PCS și fără ramură c.a.
    proprie. Bateria se împarte pe invertoarele hibride (`bess.per_invertor` / `bess.n` = câte una pe invertor, cu
    capacitatea declarată fiecare); puterea bateriei iese prin invertor (nu se adună la Σ Pn)."""
    la = [u for u in unitati if _e_hibrid(u.get("grup"))]
    if not la:
        la = list(unitati)
        j.presupune("cuplaj c.c. declarat: invertoarele CEF sunt hibride (port de baterie) — confirmați cu fișa")
    la, per = _repartizare_baterie(b, la, j)
    n = len(la)
    kwh = b.get("kWh")
    kwh_u = (float(kwh) if per else float(kwh) / n) if kwh else None
    p_b = b.get("P_kW")
    p_u = (float(p_b) if per else float(p_b) / n) if p_b else None
    if n > 1 and kwh and not per:
        j.presupune(f"capacitatea BESS {fmt_ro(kwh)} kWh împărțită pe {n} invertoare hibride ({fmt_ro(kwh_u)} kWh fiecare) — "
                    f"declarați bess.per_invertor dacă e capacitatea fiecăruia")
    ub = (b.get("baterie") or {}).get("U_nom_V") if isinstance(b.get("baterie"), dict) else b.get("U_nom_V")
    port = {}
    for u in la:
        pc = _protectie_port_baterie(j, u["obiect"], p_u or u["Pn_kW"], ub)
        if pc:
            port[u["obiect"]] = pc
    if not port:
        j.presupune("protecția c.c. a bateriilor (separator-siguranță pe portul de baterie) conform fișei invertorului "
                    "hibrid și a BMS — introduceți U_nom_V al bateriei")
    j.pas(f"BESS cuplat în c.c.: baterie pe portul invertorului hibrid ({', '.join(u['obiect'] for u in la)}), fără PCS — "
          f"puterea de injecție rămâne Σ Pn invertoare")
    r = {"cuplaj": "cc", "kWh": kwh, "P_kW": p_b, "la": [u["obiect"] for u in la], "kWh_port": kwh_u}
    if port:
        r["protectie_cc"] = port
    return r


def _parte_cc(inp, j, rez, tip, obiect="schema"):
    """SPEC §C.3 pct. 9: partea de c.c. a stringului — Voc la Tmin (V68), SPD c.c. (V74), gPV (V69) — și, din fișele
    modulului și invertorului, fereastra MPPT și curentul pe intrare (V89). Întoarce False dacă schema se oprește."""
    st = inp.get("string")
    if st:
        beta = st.get("beta")
        if beta is None:
            beta = norme.PV_BETA_UOC_IMPLICIT_PCT_K
            j.presupune("β(Voc) = −0,27 %/K (tipic c-Si)")
        elif not lt(float(beta), 0.0) or lt(float(beta), -1.0):
            # C9 (v1.2): β_Uoc ≥ 0 (sau < −1 %/K) e neplauzibil — nu se ia în modul, se cere fișa corectă
            emite(j, "V68", BLOCANT, obiect, "beta", x=float(beta))
            return False
        if st.get("n_module") is None or st.get("Uoc_V") is None:
            if not (st.get("n_module") or st.get("n_stringuri_paralel") or st.get("gpv") or st.get("gpv_In_A")
                    or st.get("n_MPPT") or inp.get("gpv_In_A")):
                inv_decl = bool(inp.get("invertoare") or inp.get("Pn_inv_kW") or isinstance(inp.get("invertor"), dict))
                if not inv_decl:
                    emite(j, "V07", BLOCANT, "string" if obiect == "schema" else obiect, "param", camp="n_module / Voc_V", x="—", conditie="lipsesc datele stringului")
                    return False
                # r6 (fotovoltaic P1-7): invertor declarat, stringul nedescris — nu se blochează exportul: string generic
                # „conform proiect DC” pe planșă + AVERTISMENT (Voc(Tmin), SPD c.c. și gPV de verificat în proiectul DC)
                emite(j, "V07", AVERTISMENT, "string" if obiect == "schema" else obiect, "string_generic")
                rez["string_generic"] = True
                return True
            # v1.9 (R5 P1-13): stringuri declarate fără fișa modulului — se desenează, Voc(Tmin) rămâne neverificat
            j.presupune(f"{obiect if obiect != 'schema' else 'string'}: Voc(Tmin) și SPD c.c. neverificate — lipsește Voc "
                        f"modulului (introduceți fișa modulului); SPD c.c. Ucpv 1100 V")
            return _gpv(st, inp, j, rez, obiect)
        umax = st.get("Umax_inv_V")
        if umax is None:
            umax = norme.PV_UMAX_INVERTOR_IMPLICIT_V
            j.presupune(f"Umax c.c. invertor {fmt_ro(umax, 0)} V (fișa lipsește — minorantul uzual: Fronius / SMA 1000 V; "
                        f"Huawei / Sungrow 1100 V se declară)")
        tmin = norme.PV_T_MIN_C
        uoc = st["n_module"] * st["Uoc_V"] * (1 + beta / 100.0 * (tmin - 25.0))
        rez["Uoc_Tmin_V"] = uoc
        rez["Umax_inv_V"] = umax
        rez["Voc_Tmin_V"] = uoc
        j.pas(f"Voc(−25 °C) = {st['n_module']}·{fmt_ro(st['Uoc_V'])}·[1 + ({fmt_ro(beta)}/100)·(−25 − 25)] = "
              f"{fmt_ro(uoc, 1)} V")
        lim_u = min(umax, st.get("Umax_modul_V") or umax)
        if gt(uoc, lim_u):
            emite(j, "V68", BLOCANT, obiect, "B", x=round(uoc, 1), y=lim_u)
        else:
            emite(j, "V68", INFO, obiect, "INFO", x=round(uoc, 1), y=lim_u)
        ucpv = prima_din_serie(norme.SPD_CC_UCPV_V, uoc)
        if ucpv is None:
            emite(j, "V74", BLOCANT, obiect, x=max(norme.SPD_CC_UCPV_V), y=round(uoc, 1))
        else:
            rez["SPD_cc_Ucpv_V"] = ucpv
        if not _gpv(st, inp, j, rez, obiect):
            return False
        fise.verifica_mppt(inp, j, tip, beta)
    return True


def _gpv(st, inp, j, rez, obiect):
    """gPV pe string (SR HD 60364-7-712): obligatorii de la 3 stringuri în paralel; `string.gpv: true` = cerute oricum
    (fișa invertorului). v1.9 (R5 P1-13): calibrul declarat (`string.gpv_In_A` sau `gpv.In_A`) se verifică față de
    [1,5·Isc; min(2,4·Isc; Irev)] când Isc e cunoscut; fără Isc se ia ca atare (presupus, neverificat)."""
    ns = st.get("n_stringuri_paralel", 1) or 1
    decl = st.get("gpv_In_A") or ((inp.get("gpv") or {}).get("In_A") if isinstance(inp.get("gpv"), dict) else None) \
        or inp.get("gpv_In_A")
    isc = st.get("Isc_A")
    irev = st.get("I_rev_A")
    if irev is None:
        irev = (fise.modul_din(inp) or {}).get("I_rev_A")
    # r6 (fotovoltaic P1-7, IEC 60364-7-712 art. 712.433): gPV necesare la n_paralel ≥ 3 sau Isc·(n − 1) > Irev
    rev = isc is not None and irev is not None and ns > 1 and gt(float(isc) * (ns - 1), float(irev))
    if not (ns >= norme.GPV_NECESAR_DE_LA_STRINGURI or rev or st.get("gpv") or decl):
        return True
    if isc is None:
        if decl:
            rez["gPV_In_A"] = decl
            j.presupune(f"gPV {fmt_ro(decl)} A pe string (declarat) — neverificat față de Isc (lipsește fișa modulului)")
            return True
        # r6: fără Isc nu se blochează exportul — gPV pe fiecare string desenate „conform proiect DC” (AVERTISMENT)
        rez["gPV_generic"] = True
        emite(j, "V69", AVERTISMENT, obiect, "generic",
              motiv=f"{ns} stringuri în paralel pe MPPT" if ns >= norme.GPV_NECESAR_DE_LA_STRINGURI else "cerute de fișă")
        return True
    a = norme.GPV_IN_MIN_FACTOR * isc
    b = norme.GPV_IN_MAX_FACTOR * isc
    if irev is not None:
        b = min(b, float(irev))
    cand = [x for x in norme.GPV_IN_A if ge(x, a) and ge(b, x)]
    if decl:
        cand = [decl] if ge(decl, a) and ge(b, decl) else []
    j.pas(f"gPV: 1,5·Isc = {fmt_ro(a)} ≤ In ≤ min(2,4·Isc; Irev) = {fmt_ro(b)} → "
          f"{fmt_ro(cand[0]) + ' A' if cand else '—'}" + (" (declarat)" if decl else ""))
    if not cand:
        emite(j, "V69", BLOCANT, obiect, a=a, b=b)
    else:
        rez["gPV_In_A"] = cand[0]
    return True


# ============================================================================================================
# C.4 Prosumator
# ============================================================================================================
PROSUMATOR_BESS_CC_MAX_KW = 50.0     # DECIZIE r6: până aici, „invertor + baterie” fără cuplaj declarat = invertor hibrid (c.c.)


def _bool(v):
    """valoare booleană din intrare (formularul poate trimite „true” / „false” ca text); None = nedeclarat"""
    if v is None or v == "":
        return None
    if isinstance(v, str):
        return v.strip().lower() in ("true", "da", "1", "yes")
    return bool(v)


def _cuplaj_bess(inp, j=None):
    """v1.9 (R5 P0-5 / L27): cum se leagă stocarea la prosumator — „cc” (port de baterie al invertorului hibrid) sau
    „ca” (PCS / invertor de baterie separat, pe bara c.a.). `bess.cuplaj` explicit are prioritate; altfel un invertor
    hibrid (declarat sau recunoscut din model) sau cheia `baterie` / `baterie_kWh` → „cc”. None = fără stocare.
    r6 (locuințe P0-9): un `bess` fără cuplaj declarat e c.a. numai dacă are PCS propriu (fișa `pcs`, sistem cu PCS:
    PowerStack, LUNA2000-200/215 …) sau prosumatorul e mare (> 50 kW / mai multe invertoare); la casă, „baterie X kWh”
    înseamnă invertor hibrid → „cc” (presupus)."""
    b = inp.get("bess") if isinstance(inp.get("bess"), dict) else None
    bat = inp.get("baterie") if isinstance(inp.get("baterie"), dict) else None
    inv = inp.get("invertor") if isinstance(inp.get("invertor"), dict) else {}
    grupuri = [g for g in inp.get("invertoare") or [] if isinstance(g, dict)]
    hib = bool(_bool(inp.get("hibrid")) or _e_hibrid(inv) or any(_e_hibrid(g) for g in grupuri))
    if b is not None:
        if b.get("cuplaj") in ("cc", "ca"):
            return b["cuplaj"]
        if isinstance(b.get("pcs"), dict) or cat_inv.bess_ca(b.get("producator"), b.get("model")):
            return "ca"           # r7: sistem cu PCS propriu / invertor de baterie c.a. (Sunny Island) — chiar lângă hibrid
        if hib:
            return "cc"
        n_u = sum(int(g.get("n", 1)) for g in grupuri) if grupuri else 1
        pn = sum(float(g.get("Pn_kW") or 0) * int(g.get("n", 1)) for g in grupuri) if grupuri else \
            float(inp.get("Pn_inv_kW") or inv.get("Pn_kW") or 0)
        mic = n_u == 1 and pn and not gt(pn, PROSUMATOR_BESS_CC_MAX_KW)
        if mic or cat_inv.baterie_cc(b.get("producator"), b.get("model")):
            if j is not None:
                j.presupune("baterie cuplată în c.c. pe portul invertorului hibrid (cuplaj nedeclarat; la prosumator "
                            "„invertor + baterie” = invertor hibrid) — declarați bess.cuplaj „ca” pentru PCS separat")
            return "cc"
        return "ca"
    # r7 (P1, „baterie-fantomă”): un invertor hibrid FĂRĂ baterie declarată nu primește baterie (hibrid ≠ baterie)
    if bat is not None or inp.get("baterie_kWh") is not None:
        return "cc"
    return None


def _grupuri_prosumator(inp, j):
    """Grupurile de invertoare ale prosumatorului: `invertoare[]` (ca la CEF) sau, ca alias, `Pn_inv_kW` / `invertor`
    (un singur invertor). Ambele declarate și diferite → V91 AVERTISMENT (se folosește lista)."""
    inv_f = inp.get("invertor") if isinstance(inp.get("invertor"), dict) else {}
    grupuri = [g for g in inp.get("invertoare") or [] if isinstance(g, dict)]
    if grupuri:
        s = sum(float(g["Pn_kW"]) * int(g.get("n", 1)) for g in grupuri)
        pa = inp.get("Pn_inv_kW")
        if pa is not None and not (inv_f and pa == inv_f.get("Pn_kW") and len(grupuri) == 1) and abs(float(pa) - s) > 0.01 * s:
            emite(j, "V91", AVERTISMENT, "schema", "alias", x=round(s, 2), y=float(pa))
        if inp.get("hibrid") and not any(g.get("hibrid") for g in grupuri):
            grupuri[0] = dict(grupuri[0], hibrid=True)
        return grupuri
    if inp.get("Pn_inv_kW") is None:
        return None
    g = dict(inv_f, Pn_kW=float(inp["Pn_inv_kW"]), n=1)
    if inp.get("Iac_max_A"):
        g["Iac_max_A"] = inp["Iac_max_A"]
    if inp.get("hibrid"):
        g["hibrid"] = True
    for k in ("ddr", "spd_ca", "IdN_min_mA", "tip_ddr"):
        if inp.get(k) is not None and k not in g:
            g[k] = inp[k]
    return [g]


def _ddr_prosumator(u, tt, ra):
    """v1.9 (R5 P0-6, SPEC §C.4) + Î6 (proiectant 28.10.2026): DDR pe circuitul unui invertor / PCS de prosumator.
    * declarat `ddr` {IdN_mA, tip} (din fișă / ATR) → acela;
    * TT → DDR-ul e protecția la defect: 30 mA ≤ 10 kW, 100 mA peste (sau `IdN_min_mA` din fișă / producător), cât permite RA;
    * TN → DOAR LA CERERE (`ddr: true` sau `IdN_min_mA` din fișă): IΔn după producător (Huawei ≥ 100 mA la orice putere,
      [HW1]; altfel 30 mA ≤ 10 kW, 100 mA peste — raport #93); fără cerere → fără DDR (deconectare prin întreruptor).
    `ddr: false` = exclus (în TN). Întoarce (IΔn, tip) sau None."""
    g = u["grup"]
    d = g.get("ddr")
    if d is False and not tt:
        return None
    tip = str(g.get("tip_ddr") or "A").upper()
    if isinstance(d, dict):
        return int(d["IdN_mA"]), str(d.get("tip") or tip).upper()
    fisa = g.get("IdN_min_mA")
    prod = cat_inv.cauta(g.get("producator"), g.get("model")) if (g.get("producator") or g.get("model")) else None
    prod_min = norme.DDR_INVERTOR_IDN_MIN_PRODUCATOR_MA.get((prod or {}).get("producator") or str(g.get("producator") or "").strip().title())
    mediu = gt(u["Pn_kW"], norme.DDR_INVERTOR_30MA_MAX_KW)       # r11: > 10 kW → 100 mA (curent de scurgere PV)
    idn = norme.DDR_INVERTOR_IDN_MARE_MA if mediu else 30
    if prod_min:
        idn = max(idn, int(prod_min))
    if fisa:
        idn = max(idn, int(fisa)) if tt else int(fisa)
    if tt:
        while ra is not None and gt(ra * idn / 1000.0, 50.0) and idn > 30:
            idn = {300: 100, 100: 30}.get(idn, 30)
        return idn, tip
    cerut = d is True or (isinstance(d, str) and d.strip().lower() in ("true", "da", "1")) or bool(fisa)
    if norme.DDR_INVERTOR_DOAR_LA_CERERE and not cerut:
        return None
    return idn, tip


_EPS_MIC = ("ilumin", "lumin", "led", "central", "router", "internet", "alarm", "camer", "supraveghere", "poarta",
            "automatizar", "senzor")


def _tablou_eps(inp, j, rez, unitati, cuplaj, retea):
    """r10 (locuințe #9, #66): tablou de rezervă (backup / EPS) alimentat din portul EPS al invertorului HIBRID — tablou
    separat după invertor (nu bara TE): Q-EPS din puterea portului, DDR 30 mA tip A pe grupă, circuitele declarate.
    Fără invertor hibrid → BLOCANT cu remediere; fără baterie → AVERTISMENT. Întoarce False dacă schema se oprește."""
    bk = inp.get("backup")
    if bk is True:
        bk = {}
    if not isinstance(bk, dict):
        emite(j, "V07", BLOCANT, "schema", "param", camp="backup", x=repr(bk)[:40],
              conditie="se așteaptă {circuite: [...], P_kW}")
        j.verificari[-1]["remediere"] = "circuitele tabloului de rezervă (backup.circuite: frigider, centrală, iluminat …)"
        return False
    hib = [u for u in unitati if not u.get("pcs") and (_e_hibrid(u["grup"]) or _bool(inp.get("hibrid")))]
    if not hib:
        _contradictie(j, BLOCANT, "EPS", "tablou de rezervă (backup / EPS) cerut, dar niciun invertor nu e hibrid (fără port "
                                         "EPS / backup)",
                      "invertor hibrid cu port EPS (hibrid: true / model hibrid) sau renunțați la tabloul de rezervă")
        j.verificari[-1]["intrebare"] = True
        return False
    u = hib[0]
    mono = u["retea"] == "mono"
    circ = [c if isinstance(c, dict) else {"nume": str(c)} for c in (bk.get("circuite") or [])]
    if not circ:
        circ = [{"nume": "Circuite rezervate"}]
        j.presupune("tabloul de rezervă (EPS) fără circuite declarate — un circuit generic „Circuite rezervate”")
    p_eps = bk.get("P_kW") or u["Pn_kW"]
    if bk.get("P_kW") is None:
        j.presupune(f"puterea portului EPS = Pn invertor {fmt_ro(u['Pn_kW'])} kW (din fișa invertorului hibrid)")
    i_eps = float(p_eps) * 1000.0 / (norme.U_0_V if mono else SQRT3 * norme.U_N_V)
    q_in = prima_din_serie(norme.MCB_IN_A, i_eps * 0.999) or round(i_eps)
    sec = lambda In: 1.5 if In <= 10 else 2.5 if In <= 16 else 4.0 if In <= 25 else 6.0 if In <= 32 else 10.0 if In <= 40 else 16.0
    out = []
    for c in circ:
        n = _fara_diacritice(str(c.get("nume") or c.get("receptor") or "")).lower()
        if c.get("P_kW") is not None:
            ib = float(c["P_kW"]) * 1000.0 / (norme.U_0_V * 0.95)
            In = prima_din_serie(norme.MCB_IN_A, max(ib, 10.0) * 0.999) or 16
        else:
            In = 10 if any(k in n for k in _EPS_MIC) else 16
        if In > q_in:
            emite(j, "V40", AVERTISMENT, "EPS", a=q_in, b=In)
        out.append({"nume": c.get("nume") or "Circuit", "In_A": In, "S_mm2": sec(In), "curba": "B" if In <= 10 else "C"})
    rez["EPS"] = {"la": u["obiect"], "P_kW": float(p_eps), "Q_In_A": q_in, "S_mm2": sec(q_in), "mono": mono,
                  "DDR": {"IdN_mA": 30, "tip": "A", "In_A": prima_din_serie(norme.RCCB_IN_A, max(q_in, 25 if not mono else 16))
                          or q_in}, "circuite": out}
    j.pas(f"Tablou de rezervă TD-EPS din portul EPS al {u['obiect']} (hibrid): P = {fmt_ro(p_eps)} kW → Ib = "
          f"{fmt_ro(i_eps)} A, Q-EPS C{q_in} A, DDR 30 mA tip A; circuite: "
          + ", ".join(f"{c['nume']} C{c['In_A']}" for c in out))
    j.presupune("TD-EPS: în regim insular legătura N–PE se face în invertor (releu intern) conform fișei; circuitele EPS "
                "sunt mutate din TE (nu dublate)")
    if not (cuplaj == "cc" or rez.get("BESS")):
        emite(j, "V96", AVERTISMENT, "EPS", ce="tablou EPS fără baterie",
              detaliu="fără baterie, portul EPS funcționează doar cât produce câmpul PV",
              remediere="declarați bateria (baterie_kWh) sau confirmați EPS fără stocare")
    return True


def schema_prosumator(inp, j):
    """SPEC §C.4: prosumator mono/tri — limite (400 kW, 40 A mono, 3,68 kW), ramurile invertoarelor, V72, V73.
    v1.9 (R5): mai multe invertoare (`invertoare[]`, `Pn_inv_kW` = alias pentru unul singur), fiecare cu ramura și
    protecțiile lui; stocare cuplată în c.c. (port de baterie al invertorului hibrid, cu protecție c.c.) sau în c.a.
    (PCS separat); prosumator > 27 kW (TD-PV cu QG și releu anti-insularizare extern);
    racord TG existent / BMPT / PT; limitarea injecției; SPD c.a. la invertor; DDR doar unde e cerut."""
    rez = {}
    fise.aplica(inp, j, "prosumator")
    retea = inp.get("retea") or "tri"
    U = u_calcul(retea)
    grupuri = _grupuri_prosumator(inp, j)
    if not grupuri:
        emite(j, "V07", BLOCANT, "schema", "lipsa")
        return rez
    unitati = []
    for g in grupuri:
        # r8 (P0-5): invertor monofazat (Primo …-1, Sunny Boy, SUN2000-…-L1 …) pe rețea trifazată — 230 V, 2P, pe o fază
        r_u = "mono" if (retea == "mono" or _retea_grup(g) == "mono") else retea
        for _ in range(int(g.get("n", 1))):
            unitati.append({"Pn_kW": float(g["Pn_kW"]), "Iac_max_A": g.get("Iac_max_A"), "pcs": False, "grup": g,
                            "retea": r_u})
    n_inv = len(unitati)
    for i, u in enumerate(unitati, 1):
        u["obiect"] = "INV" if n_inv == 1 else f"INV-{i}"
    if _invertor_baterie_ca_cc(inp, j):
        return rez
    cuplaj = _cuplaj_bess(inp, j)
    b = inp.get("bess") if isinstance(inp.get("bess"), dict) else None
    bat = b or (inp.get("baterie") if isinstance(inp.get("baterie"), dict) else {})
    if b is not None:
        rez["bess_date"] = {"kWh": None, "P_kW": None, "n_pcs": _bess_normalizeaza(b, j)}
        rez["bess_date"].update(kWh=b.get("kWh"), P_kW=b.get("P_kW"))
    if cuplaj == "ca":
        p = b.get("P_kW")
        if p is None:
            if not b.get("kWh"):
                emite(j, "V07", BLOCANT, "PCS", "lipsa")
                return rez
            p = float(b["kWh"]) / 2.0
            j.presupune(f"PCS BESS P = kWh/2 = {fmt_ro(p)} kW (0,5C)")
        unitati.append({"Pn_kW": float(p), "Iac_max_A": b.get("Iac_max_A"), "pcs": True, "obiect": "PCS", "grup": b,
                        "retea": "mono" if (retea == "mono" or _retea_grup(b) == "mono") else retea})
    for u in unitati:
        u["Iac"] = u["Iac_max_A"] or norme.FACTOR_SMAX_INVERTOR * u["Pn_kW"] * 1000.0 / u_calcul(u.get("retea", retea))
    pn = sum(u["Pn_kW"] for u in unitati if not u["pcs"])
    pn_tot = sum(u["Pn_kW"] for u in unitati)
    iac = sum(u["Iac"] for u in unitati)
    i_faze = _repartitie_faze(unitati, j) if retea == "tri" else None
    if i_faze:
        # r8 (P0-5): curentul de dimensionare al QG / comparația cu Q branșament = curentul fazei celei mai încărcate
        iac = max(i_faze.values())
        rez["faze"] = {f: round(i_faze[f], 2) for f in FAZE}
    rez["Iac_max_A"] = iac
    rez["sume"] = {"Pn_invertoare_kW": pn, "Pn_total_kW": pn_tot, "Iac_total_A": iac, "n_invertoare": n_inv}
    if n_inv == 1 and not unitati[0]["Iac_max_A"] and len(unitati) == 1:
        j.pas(f"Iac,max = 1,1·{fmt_ro(pn)}·1000/{'(√3·400)' if unitati[0].get('retea') == 'tri' else '230'} = {fmt_ro(iac)} A")
    elif len(unitati) > 1:
        j.pas(f"Σ Iac,max = {' + '.join(fmt_ro(u['Iac']) + (' (PCS)' if u['pcs'] else '') for u in unitati)} = "
              f"{fmt_ro(iac)} A; Σ Pn invertoare = {fmt_ro(pn)} kW")
    _putere_declarata(inp, j, pn)
    if gt(pn, norme.PROSUMATOR_P_MAX_KW):
        emite(j, "V70", BLOCANT, "schema", "B")
        return rez
    if retea == "mono" and gt(iac, norme.BMPM["I_max_A"]):
        emite(j, "V53", BLOCANT, "schema", "inv", Ib=iac)
        return rez
    s_mono = iac * norme.U_0_V / 1000.0                 # Ord. ANRE 228/2018 art. 12(3): comparația pe kVA (16 A)
    if retea == "mono" and gt(s_mono, norme.MONOFAZAT_S_INVERTOR_AVERTISMENT_KVA):
        emite(j, "V71", AVERTISMENT, "schema", P=pn, S=round(s_mono, 2))
    # prosumator comercial (DECIZIE, SPEC §C.4): TD-PV cu QG pe o plecare a TG-ului existent; PI externă peste prag
    com = _bool(inp.get("comercial"))
    com = gt(pn_tot, norme.PROSUMATOR_COMERCIAL_KW) if com is None else com
    pi_ext = _bool(inp.get("PI_externa"))
    # r6 (locuințe P0-9): pragul de 27 kW se aplică puterii injectabile — invertoare + PCS la cuplaj c.a.; la cuplaj c.c.
    # bateria iese prin invertor (Σ Pn invertoare)
    p_inj = pn_tot if cuplaj == "ca" else pn
    rez["sume"]["P_injectabila_kW"] = p_inj
    pi_ext = gt(p_inj, norme.PROSUMATOR_PI_EXTERNA_KW) if pi_ext is None else pi_ext
    rez["comercial"] = com
    rez["PI_externa"] = pi_ext
    if pi_ext:
        rez["PI"] = ("protecție de interfață externă (releu U/f, ROCOF) cu declanșare pe QG, certificată, reglaje conform "
                     "ATR (Ord. ANRE 228/2018)")
        if _bool(inp.get("PI_externa")) is None:
            j.presupune(f"PI externă pe QG: Σ Pn {fmt_ro(p_inj)} kW" + (" (invertoare + PCS)" if p_inj != pn else "")
                        + f" > {fmt_ro(norme.PROSUMATOR_PI_EXTERNA_KW, 0)} kW "
                        f"(cerință OD pentru prosumatori > 27 kW — reglaje conform ATR)")
    else:
        rez["PI"] = "protecție de interfață integrată în invertor, certificată (Ord. ANRE 228/2018), reglaje conform ATR"
    rez["contor"] = "bidirecțional, furnizat de OD"
    racord = inp.get("racord")
    rez["racord"] = {"tg_existent": "TG existent al consumatorului", "bmpt": "BMPT existent (branșament OD)",
                     "pt": "PT existent (bara JT)"}.get(racord, "tablou existent al consumatorului (branșament OD)")
    if racord == "pt" or inp.get("pt_Sn_kVA"):
        sn = inp.get("pt_Sn_kVA")
        if sn is None or int(sn) not in norme.TRAFO:
            emite(j, "V07", BLOCANT, "schema", "param", camp="pt_Sn_kVA", x=sn if sn is not None else "—",
                  conditie="racord „pt” fără puterea PT existent (din seria standard)")
            return rez
        nt = n_trafo_sursa(inp, j, f"PT existent {int(sn)} kVA")
        t = trafo_sursa(inp, j, int(sn), inp.get("trafo_izolatie"), *(nt or (1, False)))
        if nt is None or t is None:
            return rez
        j.ipoteza("skq", t["SkQ_MVA"], inp.get("SkQ_MVA") is None)
        ctx = sc.context_pt(t)
        rez["trafo"] = {"Sn_kVA": int(sn), "existent": True, "Ik3max_bara_kA": t["Ik3max_bara_kA"]}
        if nt[0] > 1:
            rez["trafo"]["n_trafo"] = nt[0]
        rez["racord"] = f"PT existent {int(sn)} kVA (bara JT)"
    else:
        ctx = _context_od(inp, j, ddr_amonte=racord != "tg_existent")
    tg = racord == "tg_existent"
    if tg:
        ctx = _context_tg(inp, j, ctx)
    tt = inp.get("schema_pamant") == "TT"
    ra = None
    if tt:
        # v1.2 R3 (N3-C2): DDR pe circuitul invertorului; RA·IΔn ≤ 50 V, altfel V34 BLOCANT
        ra, lim = _tt_ra(inp, j)
        if lim is None:
            return rez
    cab0 = dict(inp.get("cablu") or {})
    # r12 (bug P din proiectele reale): `cablu_inv` (secțiunea / materialul impuse ale cablului invertorului) se aplica
    # doar la CEF — la prosumator era ignorat pe calea manuală (se desena CYY-F 3 × 4 în loc de 3 × 6 cerut)
    cab0.update({k: v for k, v in (inp.get("cablu_inv") or {}).items() if v is not None and k != "L"})
    cb.metoda_implicita(cab0, "C")
    cab0.setdefault("material", "Cu")
    if inp.get("cablu") is None and inp.get("cablu_inv") is None:
        j.presupune("cablu invertor Cu PVC, metoda C")

    def ramura_unitate(u):
        g = u["grup"] or {}
        cab = dict(cab0)
        if u["pcs"] and isinstance(inp.get("cablu_pcs"), dict):
            cab = dict(inp.get("cablu") or {}, **{k: v for k, v in inp["cablu_pcs"].items() if v is not None})
            cb.metoda_implicita(cab, "C")
            cab.setdefault("material", "Cu")
        cab.update({k: v for k, v in (g.get("cablu") or {}).items() if v is not None})
        L = g.get("L_m", (g.get("cablu") or {}).get("L"))
        if L is None:
            L = inp.get("L_pcs_m") if u["pcs"] else None
        if L is None:
            L = inp.get("L_inv_m", cab.get("L", (inp.get("cablu_inv") or {}).get("L")))
        if L is None:
            L = 15.0
            j.presupune("lungime cablu invertor prosumator 15 m")
        cab["L"] = float(L)
        r = {"rol": "invertor", "receptor": "pcs" if u["pcs"] else "invertor", "retea": u.get("retea") or retea,
             "Pn_kW": u["Pn_kW"], "cablu": cab}
        if u["Iac_max_A"]:
            r["Iac_max_A"] = u["Iac_max_A"]
        return r

    # QG al TD-PV: Ip,min = max(Σ Iac; Ip invertoare). Î5 (proiectant 28.10.2026): la TOȚI prosumatorii există tablou
    # separat pentru fotovoltaic (TD-PV), indiferent de putere — nu doar la comercial / PI externă
    q_g = None
    ctx_inv = ctx
    td_pv = bool(norme.PROSUMATOR_TD_PV_INTOTDEAUNA or com or pi_ext)
    rez["td_pv"] = td_pv
    # Î5: protecțiile pe partea de c.c. (separator c.c. + SPD c.c.) și pe c.a. (SPD c.a.) — se întreabă; nedeclarat → desenate
    for k_p, ce in (("protectii_cc", "c.c. (separator c.c. sub sarcină + SPD c.c.)"), ("protectii_ca", "c.a. (SPD c.a.)")):
        v_p = _bool(inp.get(k_p))
        rez[k_p] = True if v_p is None else v_p
        if v_p is None:
            j.presupune(f"protecții pe partea de {ce}: da — nedeclarat (întrebare: există protecții pe c.c. și pe c.a.?)")
        elif not v_p:
            j.pas(f"Protecții pe partea de {ce}: NU (declarat) — nu se desenează")
    if td_pv:
        jt = Jurnal()
        ip_inv = [x["Ip"] for x in (calculeaza_ramura(dict(ramura_unitate(u), _doar_protectie=True), ctx, jt, "tmp")
                                    for u in unitati) if x["Ip"] is not None]
        ip_min = max([iac] + ip_inv)
        in_f = inp.get("In_QG_A")
        tip = "MCB" if (in_f or ip_min) <= 63 + 1e-9 else ("MCCB" if (in_f or ip_min) <= 1600 + 1e-9 else "ACB")
        In = in_f if in_f is not None else pr.alege_calibru(tip, ip_min)
        if In is None:
            emite(j, "V06", BLOCANT, "QG", Ib=iac, tip=tip)
            return rez
        q_g = pr.construieste(tip, In, ip_min, "C" if tip == "MCB" else None, are_aval=True)
        q_g["Icu_kA"], ok = pr.alege_icu(tip, ctx["Ik3_kA"])
        if not ok:
            emite(j, "V33", BLOCANT, "QG", icu=q_g["Icu_kA"], ik3=ctx["Ik3_kA"])
        if lt(pr.ip(q_g), iac):
            emite(j, "V65", BLOCANT, "schema", x=pr.ip(q_g), y=iac)
        rez["QG"] = {k: q_g.get(k) for k in ("tip", "In_A", "Ir_A", "Ir_multiplu", "curba", "Icu_kA", "decl", "Im_A",
                                              "Ii_A", "tsd_s") if q_g.get(k) is not None}
        rez["QG"]["poli"] = "2P" if retea == "mono" else "4P"
        j.pas(f"QG (TD-PV): Ip,min = max(Σ Iac {fmt_ro(iac)}; Ip max invertor {fmt_ro(max(ip_inv) if ip_inv else 0)}) = "
              f"{fmt_ro(ip_min)} A → {tip} {In} A")
        q_tg = _q_tg_existent(inp, j, ctx, iac) if tg else None
        if q_tg is not None:
            rez["Q_TG"] = {k: q_tg.get(k) for k in ("tip", "In_A", "Ir_A", "curba", "Icu_kA") if q_tg.get(k) is not None}
        L0 = inp.get("L_racord_m", (inp.get("cablu_C0") or {}).get("L"))
        if L0 is None and cablu_impus_fara_L(inp.get("cablu_C0"), j, "C0", "L_racord_m"):
            return rez
        if L0 is not None:
            c0 = {k: v for k, v in (inp.get("cablu_C0") or {}).items() if v is not None}
            cb.metoda_implicita(c0, "C")
            c0.setdefault("material", "Cu")
            c0["L"] = float(L0)
            r0 = {"rol": "c0", "receptor": "invertor", "retea": retea, "Pn_kW": pn_tot, "Iac_max_A": iac, "cablu": c0,
                  "prot_tip": tip, "In_fortat": In, "Icu_fortat": q_g["Icu_kA"], "are_aval": True, "_validat": True}
            if q_g.get("curba"):
                r0["curba"] = q_g["curba"]
            rr0 = calculeaza_ramura(r0, ctx, j, "C0", amonte=q_tg, obiect_sel="Q TG vs QG")
            rez["C0"] = dict(rr0["rezultat"], descriere="TD-PV → " + ("TG existent" if tg else "tablou existent"))
            if not rr0["blocat"]:
                ctx_inv = dict(rr0["ctx_aval"], dU_cef_pct=rr0["rezultat"]["dU_cumulat_pct"])
    rez["invertoare"] = []
    are_ddr = False
    for u in unitati:
        dd = _ddr_prosumator(u, tt, ra)
        c_u = dict(ctx_inv, idn_tt_mA=dd[0]) if (tt and dd) else ctx_inv
        rr = calculeaza_ramura(ramura_unitate(u), c_u, j, u["obiect"])
        res = dict(rr["rezultat"], obiect=u["obiect"], Pn_kW=u["Pn_kW"])
        if u.get("retea") == "mono" and retea == "tri":
            res.update(retea="mono", faza=u.get("faza"))
        if u["pcs"]:
            rez["PCS"] = res
        else:
            rez["invertoare"].append(res)
        if not rr["blocat"]:
            if dd:
                In_i = res["protectie"]["In_A"]
                mare = In_i > norme.RCCB_IN_A[-1]
                m_u = (u.get("retea") or retea) == "mono"
                res["DDR"] = {"IdN_mA": dd[0], "tip": dd[1], "In_A": In_i if mare else
                              (prima_din_serie(norme.RCCB_IN_A, max(In_i, 16 if m_u else 25)) or In_i),
                              "poli": "2P" if m_u else "4P", "aparat": "bloc_diferential" if mare else "RCCB"}
                are_ddr = True
                if not tg:
                    # v1.3 (§B.18.1): DDR-ul invertorului în aval de DDR-ul branșamentului (RCCB BMPT 300 mA S / RCBO BMPM)
                    ddr_mod.verifica(j, _ddr_amonte(inp, retea), ddr_mod.descriere(dd[0], False, f"DDR {u['obiect']}"),
                                     u["obiect"], RA_ohm=inp.get("RA_ohm") if tt else None)
                if tt:
                    rez["DDR_TT_IdN_mA"] = max(rez.get("DDR_TT_IdN_mA", 0), dd[0])
            else:
                j.pas(f"{u['obiect']}: fără DDR propriu — deconectare prin întreruptor (TN); DDR pe invertor doar la "
                      f"cerere (fișa invertorului / ATR / `ddr: true`) — DECIZIE proiectant 28.10.2026")
            if q_g is not None:
                _selectivitate_qg(q_g, rr["prot"], ctx_inv["Ik3_kA"], u["obiect"], j, len(unitati))
        if rez.get("protectii_ca", True):               # Î5: protecții c.a. declarate „nu” → fără SPD c.a. la invertor
            _spd_ca_invertor(j, u["obiect"], {"blocat": rr["blocat"], "rezultat": res}, u["grup"])
        _ddr_invertor_mare(j, u, res)
    rez["INV"] = rez["invertoare"][0] if rez["invertoare"] else None
    if rez["INV"] is None:
        rez.pop("INV")
    # stocarea cuplată în c.c.: portul de baterie al invertorului hibrid, cu protecția / separatorul de c.c. al bateriei
    if cuplaj:
        bess = {"cuplaj": cuplaj, "kWh": bat.get("kWh") or inp.get("baterie_kWh"), "P_kW": bat.get("P_kW")}
        if cuplaj == "cc":
            # r7 (P1): bateria pe invertorul / invertoarele hibride — la mai multe hibride identice se repartizează
            # (bess.la / per_invertor / împărțită egal), niciodată „doar pe primul” tăcut
            hibs = [u for u in unitati if not u["pcs"] and _e_hibrid(u["grup"])] or \
                [next(u for u in unitati if not u["pcs"])]
            la, per = _repartizare_baterie(bat, hibs, j)
            kwh = bess["kWh"]
            n_la = len(la)
            if n_la > 1 and kwh and not per:
                j.presupune(f"capacitatea bateriei {fmt_ro(kwh)} kWh împărțită pe {n_la} invertoare hibride "
                            f"({fmt_ro(float(kwh) / n_la)} kWh fiecare) — declarați bess.la (pe care invertor) sau "
                            f"bess.per_invertor")
            if n_la > 1:
                bess["kWh_port"] = (float(kwh) if per else float(kwh) / n_la) if kwh else None
            bess["la"] = la[0]["obiect"] if n_la == 1 else [u["obiect"] for u in la]
            prot = {}
            for u in la:
                p_b = (float(bat["P_kW"]) / (1 if per else n_la)) if bat.get("P_kW") else u["Pn_kW"]
                pc = _protectie_port_baterie(j, u["obiect"], p_b, bat.get("U_nom_V"))
                if pc:
                    prot[u["obiect"]] = pc
            if prot:
                bess["protectie_cc"] = prot[la[0]["obiect"]] if n_la == 1 else prot
            else:
                j.presupune("protecția c.c. a bateriei (siguranțe / întreruptor c.c. pe portul de baterie) conform fișei "
                            "invertorului hibrid și a BMS — introduceți U_nom_V al bateriei")
        rez["BESS"] = bess
    lim = _limitare_injectie(inp, j, rez, pn_tot, len(unitati), retea)
    _verifica_iac_q_existent(inp, j, iac, lim)
    # r6 (locuințe P0-9): puterea injectabilă (invertoare, + PCS la cuplaj c.a.) față de puterea aprobată / evacuată din
    # ATR — peste ea: limitarea injecției (EMS) la Pa sau ATR nou (V76)
    pa = inp.get("P_evacuata_kW") if inp.get("P_evacuata_kW") is not None else inp.get("P_aprobata_kW")
    if pa is not None:
        p_ev = min(p_inj, lim["P_kW"]) if lim else p_inj
        if gt(p_ev, float(pa)):
            emite(j, "V76", AVERTISMENT, "schema", x=p_ev, y=float(pa),
                  ce="invertoare + PCS" if cuplaj == "ca" else "invertoare")
        else:
            emite(j, "V76", INFO, "schema", "INFO", x=p_ev, y=float(pa))
    if are_ddr:
        emite(j, "V73", AVERTISMENT, "schema")
    if inp.get("backup") is not None and not _tablou_eps(inp, j, rez, unitati, cuplaj, retea):
        return rez
    # v1.8: partea de c.c. (Voc la Tmin, SPD c.c., MPPT) când stringul e descris
    if not _parte_cc(inp, j, rez, "prosumator"):
        return rez
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


_SIGURANTA_RE = ("incendiu", "hidrant", "sprinkler", "sprinkl", "drencer", "desfumar", "stingere", "evacuare fum",
                 "presurizar", "pompieri", "jockey", "iluminat de siguranta", "iluminat siguranta", "iluminat de evacuare",
                 "iluminat evacuare", "iluminat de securitate", "iluminatul de siguranta", "detectie incendiu",
                 # r10 (industrial i61, EN): denumirile în engleză ale consumatorilor de siguranță la incendiu
                 "fire pump", "fire fighting", "firefighting", "firefighter", "fireman", "fire hydrant", "fire alarm",
                 "fire protection", "fire water", "smoke extract", "smoke exhaust", "smoke control", "smoke vent",
                 "pressurisation", "pressurization", "emergency lighting", "escape lighting", "deluge", "foam pump")
_SIGURANTA_CUV = re.compile(r"\b(tdsi|psi|cdi|ssi|fire|hydrants?)\b")
# r8: câmpurile text ale unui consumator / plecări / tablou citite de regula de siguranță
_SIGURANTA_CAMPURI = ("nume", "receptor", "titlu", "denumire", "titlu_tablou", "nume_tablou", "tip")


def text_de_siguranta(t):
    """r8 (P0 #12, #14, #64): textul numește un consumator de siguranță la incendiu (I7/2011, P118-3) — incendiu, PSI,
    sprinklere, drencere, hidranți, TDSI, desfumare, presurizare, lift de pompieri, jockey, iluminat de siguranță /
    evacuare, CDI. Regula e în motor, indiferent de formularea frazei."""
    if not isinstance(t, str) or not t:
        return False
    n = _fara_diacritice(t).lower().replace("_", " ").replace("-", " ")
    return any(k in n for k in _SIGURANTA_RE) or bool(_SIGURANTA_CUV.search(n))


def e_consumator_siguranta(c):
    """r6 (#32, #35) / r8: consumator de siguranță (I7/2011, P118-3) — `siguranta: true` sau numele / receptorul /
    titlul (pompă de incendiu, hidranți, sprinklere, TDSI, desfumare, presurizare, lift de pompieri, iluminat de
    siguranță). `siguranta: false` explicit are prioritate."""
    if not isinstance(c, dict):
        return False
    if c.get("siguranta") is not None:
        return bool(c.get("siguranta"))
    return any(text_de_siguranta(c.get(k)) for k in _SIGURANTA_CAMPURI)


def tablou_de_siguranta(inp):
    """r7 (#31, P0): tabloul ÎNTREG e de siguranță — `siguranta_tablou: true`, `siguranta: true` la nivelul schemei, sau
    titlul tabloului (`titlu_tablou` / `nume_tablou` / `titlu`) numește pompe de incendiu / hidranți / sprinklere /
    desfumare / TDSI / presurizare. Atunci toți consumatorii sunt de siguranță (fără DDR, cabluri rezistente la foc)."""
    if inp.get("siguranta_tablou") is True or inp.get("siguranta") is True:
        return True
    for k in ("titlu_tablou", "nume_tablou", "titlu"):
        if text_de_siguranta(inp.get(k)):
            return True
    return False


def _e_pompa(c):
    """Pompă după nume (nu marcată explicit `siguranta: false`)."""
    return (isinstance(c, dict) and c.get("siguranta") is not False
            and any(k in _fara_diacritice(str(c.get("nume") or "")).lower() for k in ("pomp", "jockey", "pilot")))


def _context_pompe_psi(lista):
    """r8 (#12): o pompă jockey (pilot de menținere a presiunii) există doar în instalațiile de stingere — lângă ea,
    pompele (electropompa principală / de rezervă) sunt pompe de incendiu."""
    return any(isinstance(c, dict) and "jockey" in _fara_diacritice(str(c.get("nume") or "")).lower() for c in lista)


def _n_rezerva(c):
    """r7: (n total, n rezervă) al unui consumator — `n` număr sau „1+1” / „2+1” (activ + rezervă); `rezerva: true`
    sau numele „… rezervă” = toate unitățile de rezervă; `n_rezerva` explicit."""
    n = c.get("n", 1)
    nr = 0
    if isinstance(n, str):
        m = re.match(r"^\s*(\d+)\s*\+\s*(\d+)\s*$", n)
        if m:
            n, nr = int(m.group(1)) + int(m.group(2)), int(m.group(2))
        else:
            try:
                n = int(float(n.replace(",", ".")))
            except ValueError:
                n = 1
    n = int(n or 1)
    if c.get("n_rezerva") is not None:
        nr = int(c["n_rezerva"])
    if c.get("rezerva") is True or "rezerv" in _fara_diacritice(str(c.get("nume") or "")).lower():
        nr = n
    return n, min(max(nr, 0), n)


def _consumatori_siguranta(inp):
    """Lista consumatorilor de siguranță ai GE (fiecare cu `n` expandat): din `consumatori`, sau toată sarcina dacă
    `siguranta: true` la nivelul schemei. r7: tabloul de siguranță (titlu / `siguranta_tablou`) → toți consumatorii;
    unitățile de rezervă poartă `_rezerva` (desenate, dar neadunate la sarcină)."""
    cons = inp.get("consumatori") if isinstance(inp.get("consumatori"), list) else []
    tot = tablou_de_siguranta(inp)
    psi = _context_pompe_psi(cons)
    # r9 (#27): pompa pilot / jockey / de menținere lângă o pompă de incendiu face parte din instalația de stingere
    pompa_sig = any(isinstance(c, dict) and e_consumator_siguranta(c) and _e_pompa(c) for c in cons)

    def pilot(c):
        return pompa_sig and _e_pompa(c) and c.get("siguranta") is None and any(
            k in _fara_diacritice(str(c.get("nume") or "")).lower() for k in ("pilot", "jockey", "mentinere"))
    out = []
    for c in cons:
        if isinstance(c, dict) and (tot or e_consumator_siguranta(c) or (psi and _e_pompa(c)) or pilot(c)) \
                and c.get("P_kW") is not None:
            n, nr = _n_rezerva(c)
            for k in range(1, n + 1):
                out.append(dict(c, n=1, siguranta=True, _rezerva=k > n - nr,
                                nume=(f"{c.get('nume') or 'Pompă incendiu'} {k}" if n > 1
                                      else (c.get("nume") or "Pompă incendiu"))))
    if not out and inp.get("siguranta") is True and inp.get("P_sarcina_kW") is not None:
        out.append({"nume": "Consumatori de siguranță", "P_kW": float(inp["P_sarcina_kW"])})
    return out


def _plecari_siguranta_ge(sig, inp, rr1, rr2, j):
    """r6: o plecare din bara ATS pentru fiecare consumator de siguranță — fără DDR, cablu Cu rezistent la foc
    (E90, metoda C pe traseu propriu), dimensionată în regim rețea (sursa = capătul C1) și verificată în regim GE."""
    out = []
    for k, c in enumerate(sig, 1):
        ob = f"PS{k}·{c['nume']}"
        rec = c.get("receptor") or ("motor" if (c.get("pornire") or "pomp" in _fara_diacritice(c["nume"]).lower()
                                                or receptor_dupa_nume(c["nume"], 1) == "motor") else "forta")
        cab = dict(c.get("cablu") or {})
        cab.setdefault("material", "Cu")
        cab.setdefault("izolatie", "XLPE")
        cab.setdefault("metoda", "C")
        cab["L"] = float(c.get("L_m", cab.get("L", 30.0)))
        if c.get("L_m") is None and (c.get("cablu") or {}).get("L") is None:
            j.presupune(f"lungime circuit de siguranță {c['nume']} 30 m (Cu, rezistent la foc E90, metoda C)", ob)
        r = {"rol": "plecare", "receptor": rec, "retea": "tri", "P_kW": float(c["P_kW"]), "cablu": cab, "ddr": False}
        if c.get("pornire"):
            r["pornire"] = c["pornire"]
        if rec == "motor":
            r["prot_tip"] = "MCCB"
        rr = calculeaza_ramura(r, rr1["ctx_aval"], j, ob)
        z = dict(rr["rezultat"], nume=c["nume"], siguranta=True, rezistent_foc=True, receptor=rec)
        if c.get("_rezerva"):
            z["rezerva"] = True          # r7: unitate de rezervă — desenată, interblocată, neadunată la sarcină
        if not rr["blocat"] and rec == "motor":
            z["aparataj_motor"] = aparataj_motor(dict(c, P_kW=float(c["P_kW"])), z, j, ob)
            # P118-3: la pompele de incendiu releul termic doar semnalizează (nu oprește pompa)
            z["aparataj_motor"]["releu_termic_doar_semnalizare"] = True
        emite(j, "V97", INFO, ob, nume=c["nume"])
        out.append(z)
    return out


def _doar_retea(c, toti):
    """r9 (industrial #24, S8): consumator NORMAL al schemei GE — alimentat numai din rețea (înaintea ATS), nu din GE:
    `pe_ge: false` / `vital: false` / `normal: true` / `ramura: "retea"`; sau, când lista declară vitalii (`vital: true`
    / `pe_ge: true`), orice consumator nedeclarat vital și care nu e de siguranță."""
    if not isinstance(c, dict):
        return False
    if c.get("pe_ge") is False or c.get("vital") is False or c.get("normal") is True or \
            _fd(c.get("ramura") or "").lower() in ("retea", "normal", "normala"):
        return True
    if c.get("pe_ge") is True or c.get("vital") is True or e_consumator_siguranta(c):
        return False
    return any(isinstance(x, dict) and (x.get("vital") is True or x.get("pe_ge") is True) for x in toti)


def _separa_consumatori_retea(inp, j, rez):
    """r9 (#24): consumatorii normali (doar rețea) se scot din sarcina GE / ATS — pe ramura GE rămân doar consumatorii
    vitali / declarați. Întoarce puterea lor (kW, n × P) sau 0."""
    cons = inp.get("consumatori")
    if not isinstance(cons, list) or not cons:
        return 0.0
    norm = [c for c in cons if _doar_retea(c, cons)]
    vit = [c for c in cons if c not in norm]
    if not norm or not vit:
        if norm and not vit:
            j.presupune("toți consumatorii sunt declarați normali (doar rețea) — niciun consumator vital pe GE; "
                        "schema îi tratează ca alimentați prin ATS")
        return 0.0
    try:
        p_n = sum(_n_rezerva(c)[0] * float(c["P_kW"]) for c in norm)
        p_all = sum(_n_rezerva(c)[0] * float(c["P_kW"]) for c in cons)
    except (KeyError, TypeError, ValueError):
        return 0.0
    inp["consumatori"] = vit
    if inp.get("P_sarcina_kW") is not None and (abs(float(inp["P_sarcina_kW"]) - p_all) < 1e-6
                                                or gt(float(inp["P_sarcina_kW"]), p_all - p_n)):
        inp.pop("P_sarcina_kW")            # sarcina GE = doar vitalii (recalculată din listă)
    rez["consumatori_retea"] = [{"nume": c.get("nume") or "Consumator", "P_kW": float(c["P_kW"]),
                                 "n": _n_rezerva(c)[0]} for c in norm]
    rez["P_retea_normali_kW"] = p_n
    j.pas("Consumatori normali (doar rețea, înaintea ATS, nu se alimentează din GE): "
          + ", ".join(f"{c.get('nume')} {fmt_ro(c['P_kW'])} kW" for c in norm) + f" = {fmt_ro(p_n)} kW")
    return p_n


_CHEI_PLECARE_CONS = ("receptor", "pornire", "cosfi", "L_m", "cablu", "retea", "siguranta", "rezerva", "prot_tip",
                      "In_A", "S_kVA", "DDR", "ddr", "ks", "faza", "h3_pct", "copii", "vital", "pe_ge")


def _consumatori_plecari(inp, j):
    """r10 (industrial i43 / i47): consumatorii schemei GE / ATS ca plecări reale ale tabloului (nu comasate într-un
    „Consumatori”): n × P → n plecări numerotate. Acceptă și `plecari` declarate direct."""
    if isinstance(inp.get("plecari"), list) and inp["plecari"]:
        return [dict(p) for p in inp["plecari"] if isinstance(p, dict)]
    out = []
    for i, c in enumerate(inp.get("consumatori") or [], 1):
        if not isinstance(c, dict):
            continue
        pl = {"nume": c.get("nume") or f"Consumator {i}"}
        if c.get("P_kW") is not None:
            pl["P_kW"] = c["P_kW"]
        for k in _CHEI_PLECARE_CONS:
            if k in c and k not in ("vital", "pe_ge"):
                pl[k] = c[k]
        n, nr = _n_rezerva(c)
        if n > 1:
            pl["n_circuite"] = n
        out.append(pl)
    return out


L_LEGATURA_ATS_M = 5.0       # DECIZIE r11: ATS montat în TG — legătura bara normală → ATS → bara vitală ≈ 5 m


def _schema_tg_normal_vital(inp, j):
    """r11 (industrial j30 / j08 / j57): TG cu DOUĂ bare — bara NORMALĂ alimentată doar din rețea (C1 → Q1), cu
    consumatorii nevitali, și bara VITALĂ alimentată prin ATS: poziția I din bara normală (QV), poziția II din GE (QG,
    C2). Consumatorii se distribuie automat după `vital` / `siguranta` / `pe_ge` (nedeclarat = normal dacă lista
    declară vitalii). Bara normală + legătura spre ATS se calculează ca un tablou (cascada „bara vitală” = plecare cu
    copiii vitali); GE (In_G, QG, C2, ATS, V86 pe sarcina vitală) ca la schema GE + ATS, doar pe consumatorii vitali."""
    rez = {"mod": "tg_normal_vital"}
    cons = inp.get("consumatori")
    if not isinstance(cons, list) or not all(isinstance(c, dict) for c in cons) or not cons:
        emite(j, "V07", BLOCANT, "schema", "param", camp="consumatori", x=repr(cons)[:60],
              conditie="bara normală + bara vitală cer lista consumatorilor (nume, P_kW, vital true/false)")
        return rez
    if _bool(inp.get("fara_retea")):
        _contradictie(j, BLOCANT, "schema", "bară normală (doar rețea) declarată la un GE fără rețea",
                      "fără bara normală (GE izolat: fara_retea) sau cu rețea (bara_vitala)")
        return rez
    if inp.get("Sn_GE_kVA") is None:
        emite(j, "V07", BLOCANT, "schema", "param", camp="Sn_GE_kVA", x="—", conditie="lipsește puterea GE (kVA)")
        return rez
    if not any(c.get("vital") is not None or c.get("pe_ge") is not None or c.get("normal") is not None
               or e_consumator_siguranta(c) for c in cons):
        emite(j, "V07", BLOCANT, "schema", "param", camp="consumatori[].vital", x="—",
              conditie="nu e declarat care consumatori sunt pe bara vitală")
        j.verificari[-1]["remediere"] = "vital: true pe consumatorii alimentați și din GE, vital: false pe cei doar din rețea"
        j.verificari[-1]["intrebare"] = True
        return rez
    normali = [c for c in cons if _doar_retea(c, cons)]
    vitali = [c for c in cons if c not in normali]
    if not vitali or not normali:
        emite(j, "V96", BLOCANT, "schema", ce="TG cu bară normală + bară vitală, cu " + (
              "bara vitală goală" if not vitali else "bara normală goală"),
              detaliu="o bară fără consumatori nu se desenează",
              remediere="consumatori pe ambele bare (vital true / false), sau schema GE + ATS fără bara_vitala")
        return rez
    # ---- bara normală (+ legătura QV spre ATS) = tablou alimentat din rețea
    sr = inp.get("sursa_retea")
    t = {"tip_schema": "tablou", "schema_pamant": inp.get("schema_pamant"), "retea": "tri",
         "titlu_tablou": inp.get("titlu_tablou"), "_bara_vitala_ge": True}
    if sr == "pt" or inp.get("origine") == "pt_propriu":
        t.update(origine="pt_propriu", pt_Sn_kVA=inp.get("pt_Sn_kVA"))
        for k in ("n_trafo", "cupla", "bara", "SkQ_MVA", "trafo_izolatie") + CHEI_UK:
            if inp.get(k) is not None:
                t[k] = inp[k]
    elif sr == "tgd":
        t["origine"] = "tg_existent"
        if inp.get("Ik3_sursa_kA") is not None:
            t["Ik3_sursa_kA"] = inp["Ik3_sursa_kA"]
    else:
        t["origine"] = "bmpt"
        if sr is None:
            j.presupune("rețeaua normală: BMPT (sursa rețelei nedeclarată) — declarați sursa_retea „pt” / „tgd” / „bmpt”")
    for k in ("Zb_OD_ohm", "Ik3_OD_kA", "RA_ohm", "cablu", "ks"):
        if inp.get(k) is not None:
            t[k] = inp[k]
    L1 = inp.get("L_C1_m", inp.get("L_alimentare_m"))
    if L1 is not None:
        t["L_alimentare_m"] = L1
    pl_n = _consumatori_plecari({"consumatori": normali}, j)
    pl_v = _consumatori_plecari({"consumatori": vitali}, j)
    t["plecari"] = pl_n + [{"nume": "Bara vitală (ATS)", "receptor": "tablou", "L_m": L_LEGATURA_ATS_M,
                            "cablu": {"material": "Cu", "metoda": "C"}, "copii": pl_v, "_bara_vitala": True}]
    j.presupune(f"ATS în TG: legătura bara normală → QV → ATS → bara vitală ≈ {fmt_ro(L_LEGATURA_ATS_M, 0)} m Cu; "
                "plecările vitale dimensionate în regim rețea, deconectarea în regim GE prin blocul diferențial de pe QG")
    for c in t["plecari"][-1]["copii"]:
        c.pop("_bara_vitala", None)
    rt = schema_tablou(t, j)
    rez.update(rt)
    rez["tablou_intrare"] = t
    try:
        p_n = sum(_n_rezerva(c)[0] * float(c["P_kW"]) for c in normali)
        p_v = sum((_n_rezerva(c)[0] - _n_rezerva(c)[1]) * float(c["P_kW"]) for c in vitali)
    except (KeyError, TypeError, ValueError):
        emite(j, "V07", BLOCANT, "schema", "param", camp="consumatori[].P_kW", x="—", conditie="fiecare consumator are P_kW")
        return rez
    rez["P_retea_normali_kW"] = p_n
    rez["P_vitali_kW"] = p_v
    rez["consumatori_retea"] = [{"nume": c.get("nume") or "Consumator", "P_kW": float(c["P_kW"]),
                                 "n": _n_rezerva(c)[0]} for c in normali]
    rez["consumatori_vitali"] = [c.get("nume") for c in vitali]
    j.pas("Bara normală (doar rețea): " + ", ".join(f"{c.get('nume')} {fmt_ro(c['P_kW'])} kW" for c in normali)
          + f"; bara vitală (rețea + GE prin ATS): " + ", ".join(f"{c.get('nume')} {fmt_ro(c['P_kW'])} kW" for c in vitali))
    # ---- GE pe sarcina vitală (calculul GE + ATS cu consumatorii vitali; QR/C1/C3 ai acelui calcul nu se folosesc)
    g = {k: v for k, v in inp.items() if k not in ("bara_vitala", "consumatori", "P_sarcina_kW", "plecari")}
    g.update(consumatori=[dict(c) for c in vitali], sursa_retea=sr or "bmpt")
    jg = Jurnal()
    rg = schema_ge(g, jg)
    pastrate = ("Q_G", "C2", "In_G_A", "Ik3_GE_kA", "Sn_GE_minim_kVA", "Ik1_regim_GE_A", "neutru_GE", "siguranta_tot")
    rez.update({k: rg[k] for k in pastrate if k in rg})
    for v in jg.verificari:
        ob = str(v.get("obiect") or "")
        if (v["cod"] in ("V86", "V85", "V87", "V97") or ob.startswith(("Q_G", "QG", "C2"))) and not (
                v["cod"] == "V86" and v["nivel"] != BLOCANT):
            j.verificari.append(v)
    for x in jg.presupus:
        if "GE" in x or "x\"d" in x or "C2" in x:
            j.presupune(x)
    for x in jg.pasi:
        if "GE" in x or "Q_G" in x or "QG" in x:
            j.pas(x)
    # ATS: In ≥ max(QV, QG)
    fv = next((z for z in rt.get("plecari") or [] if z.get("nume") == "Bara vitală (ATS)" and int(z.get("nivel") or 0) == 0),
              None)
    qv = (fv or {}).get("protectie") or {}
    qg = rez.get("Q_G") or {}
    if qv.get("In_A") and qg.get("In_A"):
        in_ats = max(qv["In_A"], qg["In_A"])
        in_ats = prima_din_serie(sorted(set(pr.SERII["MCCB"]) | set(pr.SERII["ACB"])), in_ats) or in_ats
        manual = str(inp.get("comutare") or "").strip().lower() in ("manual", "manuala", "inversor", "i-0-ii")
        rez["ATS"] = {"poli": inp.get("ATS_poli", 4), "In_A": in_ats, "categorie": "AC-23B" if manual else "AC-33B",
                      "interblocaj": "mecanic (poziția 0 între I și II)" if manual else "mecanic + electric",
                      "intrari": {"I": "bara normală (QV)", "II": "GE (QG, C2)"}, "iesire": "bara vitală"}
        if manual:
            rez["ATS"]["comutare"] = "manual"
        j.pas(f"ATS 4P In ≥ max(QV {qv['In_A']} A; QG {qg['In_A']} A) → {in_ats} A; I = bara normală, II = GE, ieșire = "
              f"bara vitală")
        if isinstance(rez["ATS"]["poli"], (int, float)) and rez["ATS"]["poli"] < 4:
            emite(j, "V87", BLOCANT, "schema", detaliu=f"cu {rez['ATS']['poli']} poli în TN-S (sunt necesari 4 poli)")
    return rez


def _schema_ge_izolat(inp, j):
    """r10 (industrial i43): GE care alimentează singur tabloul (site izolat, `fara_retea: true`) — fără ramură de rețea,
    fără ATS: GE → Q_G (Ir ≤ In_G, bloc diferențial 300 mA S) → C1 → bara TG → plecările reale (dimensionate în regim GE).
    GE subdimensionat față de bilanț → V86 BLOCANT."""
    rez = {"mod": "ge_izolat"}
    U = SQRT3 * norme.U_N_V
    inventat = [k for k in ("sursa_retea", "pt_Sn_kVA", "In_Q_retea_A") if inp.get(k) is not None]
    if inventat:
        # r11: combinație pe care motorul nu o desenează fidel → BLOCANT (desenul rămâne GE izolat, exportul e blocat)
        emite(j, "V12", BLOCANT, "schema", "contradictie",
              detaliu=f"nesuportat: GE fără rețea (site izolat), dar este declarată și o ramură de rețea "
                      f"({', '.join(inventat)}) — ramura de rețea NU se desenează")
        j.verificari[-1]["remediere"] = "confirmați: GE izolat (fara_retea) sau GE de rezervă cu ATS (sursa_retea)"
    if inp.get("retea") == "mono":
        emite(j, "V96", BLOCANT, "schema", ce="GE monofazat izolat", detaliu="motorul calculează GE izolat trifazat",
              remediere="GE trifazat 3P+N sau schemă de specialitate")
        return rez
    if inp.get("schema_pamant") == "TT":
        emite(j, "V96", BLOCANT, "schema", ce="GE izolat în schemă TT",
              detaliu="GE izolat se calculează TN-S (neutrul GE legat la priza de pământ locală)",
              remediere="schema_pamant „TN-S” (neutrul GE la priza locală) sau proiect de specialitate")
        return rez
    if inp.get("Sn_GE_kVA") is None:
        emite(j, "V07", BLOCANT, "schema", "param", camp="Sn_GE_kVA", x="—", conditie="lipsește puterea GE (kVA)")
        return rez
    plecari = _consumatori_plecari(inp, j)
    if not plecari:
        emite(j, "V07", BLOCANT, "schema", "plecari", tablou="TG alimentat din GE")
        return rez
    if not _valideaza_plecari(plecari, j):
        return rez
    sn = float(inp["Sn_GE_kVA"])
    in_g = sn * 1000.0 / U
    xd = inp.get("xd")
    if xd is None:
        xd = norme.GE_XD2_IMPLICIT
        j.presupune("x\"d = 0,12 (lipsește din fișa GE)")
    tip_g = "MCCB" if in_g <= 1600 + 1e-9 else "ACB"
    In_G = inp.get("In_QG_A") or pr.alege_calibru(tip_g, in_g)
    if In_G is None:
        emite(j, "V06", BLOCANT, "Q_G", Ib=in_g, tip="ACB")
        return rez
    k_g, ir_g = pr.alege_reglaj_ir_max(tip_g, In_G, in_g)
    if k_g is None:
        emite(j, "V60", BLOCANT, "schema", "B", x=In_G, y=in_g)
        return rez
    ik3 = sc.ge_ik3(in_g, xd)
    ik1_ge = norme.GE_IK_SUSTINUT_MULTIPLU * in_g if inp.get("excitatie_sustinuta") else in_g
    ctx = _context_ge(in_g, sn, xd, ik1_ge)
    rez.update({"In_G_A": in_g, "Ik3_GE_kA": ik3 / 1000.0, "Ik1_regim_GE_A": ik1_ge, "fara_retea": True})
    j.pas(f"GE {fmt_ro(sn)} kVA, sursă unică (site izolat, fără rețea): In_G = {fmt_ro(in_g)} A; Ik3'' ≈ 1,1·In_G/x''d "
          f"= {fmt_ro(ik3 / 1000.0)} kA; Q_G {tip_g} {In_G} A, Ir ≤ In_G = {fmt_ro(ir_g)} A")
    sig = tablou_de_siguranta(inp) or any(e_consumator_siguranta(p) for p in plecari)
    t_inp = {k: inp[k] for k in ("schema_pamant", "cablu", "ks", "circuite_finale", "titlu_tablou", "nume_tablou",
                                 "siguranta_tablou", "cosfi", "P_kW") if inp.get(k) is not None}
    L = inp.get("L_C2_m", inp.get("L_GE_ATS_m", inp.get("L_alimentare_m")))
    if L is None:
        L = 20.0
        j.presupune("lungime C1 (GE → TG) 20 m")
    t_inp.update({"tip_schema": "tablou", "plecari": plecari, "retea": "tri", "origine": "_ge", "_ctx_sursa": ctx,
                  "_sursa_eticheta": f"GE {fmt_ro(sn, 0)} kVA — sursă unică (site izolat, fără rețea)",
                  "In_Q1_A": In_G, "_Ib_Q1_A": ir_g, "Q1_tip": tip_g, "L_alimentare_m": float(L)})
    t_inp["cablu"] = dict(t_inp.get("cablu") or {}, L=float(L))
    if not sig and inp.get("DDR_GE", True) is not False:
        # regim GE: Ik1 ≈ In_G nu atinge Ia al Q_G → bloc diferențial 300 mA S pe Q_G (SR HD 60364-4-41 art. 411.4.5)
        t_inp["Q1_DDR"] = {"IdN_mA": 300, "selectiv": True, "tip": "A"}
    rz = schema_tablou(t_inp, j)
    rez.update(rz)
    q1 = (rz.get("Q1_C1") or {}).get("protectie") or {}
    rez["Q_G"] = {"tip": q1.get("tip", tip_g), "In_A": q1.get("In_A", In_G), "Ir_A": q1.get("Ir_A", ir_g),
                  "Icu_kA": q1.get("Icu_kA"), "decl": q1.get("decl")}
    if sig:
        rez["Q_G"]["RCM"] = {"IdN_mA": 300, "functie": "monitorizare curent diferențial — doar semnalizare (SR EN 62020)"}
    pc = (rz.get("bilant") or {}).get("Pc_kW")
    cos = inp.get("cosfi", norme.COSFI_IMPLICIT["tablou"])
    if pc is not None:
        rez["Sn_GE_minim_kVA"] = norme.ge_sn_minim(float(pc), cos)
        ib = float(pc) * 1000.0 / (U * cos)
        j.pas(f"GE minim: Sn ≥ Pc/cosφ = {fmt_ro(pc)}/{fmt_ro(cos)} = {fmt_ro(pc / cos)} kVA → "
              f"{rez['Sn_GE_minim_kVA']} kVA (fără pornirea motoarelor)")
        if gt(ib, in_g):
            emite(j, "V86", BLOCANT, "schema", x=ib, y=in_g, Sn=rez["Sn_GE_minim_kVA"])
        elif gt(ib, ir_g):
            emite(j, "V86", BLOCANT, "schema", "ir", x=ib, y=ir_g, Sn=rez["Sn_GE_minim_kVA"])
    rez["nota_schema_pamant"] = ("Schemă de legare la pământ: TN-S, neutrul GE legat la priza de pământ locală (sursă "
                                 f"unică, fără rețea). Rp ≤ 4{NB}Ω.")
    return rez


def _schema_ats_trafo(inp, j):
    """r10 (industrial i47): ATS între DOUĂ transformatoare (rezervă 100 %, `sursa_rezerva: "trafo"`), fără GE —
    intrarea I: T1 → QT1 → C1, intrarea II: T2 → QT2 → C2, ATS 4P cu interblocaj (trafo niciodată în paralel), bara TG
    cu plecările reale. Fiecare trafo poartă singur toată sarcina (V62 pe un trafo). Trafo diferite → BLOCANT explicit."""
    rez = {"mod": "ats_trafo"}
    if inp.get("Sn_GE_kVA") is not None:
        emite(j, "V12", BLOCANT, "schema", "contradictie",
              detaliu=f"ATS între două transformatoare, dar este declarat și un GE {inp['Sn_GE_kVA']} kVA")
        j.verificari[-1]["remediere"] = ("alegeți: rezervă din al doilea trafo (sursa_rezerva „trafo”, fără Sn_GE_kVA) "
                                         "sau GE de rezervă (sursa_rezerva „ge”)")
        return rez
    sn = inp.get("pt_Sn_kVA", inp.get("Sn_kVA", inp.get("Sn_T_kVA")))
    sn2 = inp.get("Sn_T2_kVA", sn)
    if sn is None:
        emite(j, "V07", BLOCANT, "schema", "param", camp="pt_Sn_kVA", x="—",
              conditie="ATS între două transformatoare fără puterea trafo")
        j.verificari[-1]["remediere"] = "puterea transformatoarelor (pt_Sn_kVA, ex. 630 kVA)"
        return rez
    if sn2 != sn:
        emite(j, "V96", BLOCANT, "schema", ce=f"ATS între trafo diferite ({sn} kVA / {sn2} kVA)",
              detaliu="motorul calculează ATS între două transformatoare identice (rezervă 100 %)",
              remediere="transformatoare identice sau proiect de specialitate")
        return rez
    if inp.get("retea") == "mono" or inp.get("schema_pamant") == "TT":
        emite(j, "V96", BLOCANT, "schema", ce="ATS între trafo în rețea monofazată / TT",
              detaliu="ATS între două PT se calculează trifazat TN-S", remediere="TN-S / TN-C-S trifazat")
        return rez
    plecari = _consumatori_plecari(inp, j)
    if not plecari:
        emite(j, "V07", BLOCANT, "schema", "plecari", tablou="TG cu ATS între trafo")
        return rez
    if not _valideaza_plecari(plecari, j):
        return rez
    t_inp = {k: inp[k] for k in ("schema_pamant", "cablu", "ks", "circuite_finale", "titlu_tablou", "nume_tablou",
                                 "siguranta_tablou", "cosfi", "P_kW", "SkQ_MVA", "uk_pct", "trafo_izolatie",
                                 "L_alimentare_m", "Q1_tip", "Q_general_tip") if inp.get(k) is not None}
    if inp.get("L_alimentare_m") is None and inp.get("L_C1_m") is not None:
        t_inp["L_alimentare_m"] = inp["L_C1_m"]
    t_inp.update({"tip_schema": "tablou", "plecari": plecari, "retea": "tri", "origine": "pt_propriu",
                  "pt_Sn_kVA": int(sn)})
    j.pas(f"ATS între T1 și T2 ({int(sn)} kVA fiecare, rezervă 100 %): trafo NICIODATĂ în paralel (interblocaj ATS) — "
          f"Ik3 la bara TG dintr-un singur trafo; fiecare trafo poartă singur toată sarcina")
    rz = schema_tablou(t_inp, j)
    rez.update(rz)
    q1 = (rz.get("Q1_C1") or {}).get("protectie") or {}
    if q1.get("In_A"):
        in_ats = prima_din_serie(sorted(set(pr.SERII["MCCB"]) | set(pr.SERII["ACB"])), q1["In_A"]) or q1["In_A"]
        rez["ATS"] = {"poli": 4, "In_A": in_ats, "interblocaj": "mecanic + electric", "categorie": "AC-33B",
                      "intrari": {"I": f"T1 {int(sn)} kVA (QT1, C1)", "II": f"T2 {int(sn)} kVA (QT2, C2)"},
                      "iesire": "bara TG"}
        j.pas(f"ATS 4P In ≥ In QT1 = In QT2 = {q1['In_A']} A → {in_ats} A; intrări I (T1) / II (T2)")
    rez["Sn_T_kVA"] = int(sn)
    return rez


# E2 (decizia proprietarului, 28.10.2026): GE fără protecție la defect asigurată în regim GE — cele două soluții
# acceptate, fiecare explicată (când se folosește, ce implică, ce se desenează). Câmpul de alegere: `ge_protectie`.
GE_PROTECTIE_OPTIUNI = (
    {"valoare": "excitatie", "titlu": "Excitație susținută + Q_G electronic",
     "cand": "GE nou sau GE al cărui alternator are excitație PMG / AREP (sau booster de excitație) și producătorul "
             "garantează curentul de scurtcircuit susținut; varianta preferată când consumatorii din regim GE sunt "
             "dispersați (nu se pot lega echipotențial toți).",
     "implica": "curent de scurtcircuit susținut ≥ 3·In_G timp de ≥ 2 s (declarația producătorului GE, de anexat); "
                "Q_G cu declanșator electronic, Isd reglat sub Ik1 minim din regim GE și tsd coordonat cu aval; "
                "verificarea deconectării se reface cu Ik1 = 3·In_G.",
     "desen": "pe GE: nota „excitație susținută (PMG/AREP), Ik ≥ 3·In ≥ 2 s”; pe Q_G: „declanșator electronic, "
              "Isd = … A, tsd = … s”; în tabelul de reglaje: valorile Ir / Isd / tsd ale Q_G.",
     "campuri": {"ge_protectie": "excitatie", "excitatie_sustinuta": True}},
    {"valoare": "echipotential", "titlu": "Legături echipotențiale suplimentare (SR HD 60364-4-41 art. 415.2)",
     "cand": "GE existent fără excitație susținută, consumatori de siguranță (pompe de incendiu, desfumare) care nu pot "
             "trece prin DDR, sau încăperi / zone restrânse în care toate masele și elementele conductoare simultan "
             "accesibile se pot lega între ele.",
     "implica": "conductor de echipotențializare suplimentară între toate masele și elementele conductoare străine "
                "simultan accesibile din zona alimentată în regim GE; condiția R ≤ 50 V / Ia (art. 415.2.2) "
                "verificată prin măsurare la PIF; secțiuni conform SR HD 60364-5-54 art. 544.2; nu înlocuiește "
                "protecția la suprasarcină / scurtcircuit.",
     "desen": "nota „Protecție la contact indirect în regim GE prin legături echipotențiale suplimentare "
              "(SR HD 60364-4-41 art. 415.2), R ≤ 50 V/Ia — de măsurat la PIF”; bara BEP suplimentară în zona "
              "consumatorilor alimentați din GE.",
     "campuri": {"ge_protectie": "echipotential", "legaturi_echipotentiale": True}},
)


def ge_protectie_aleasa(inp):
    """'excitatie' | 'echipotential' | None — din `ge_protectie` sau din câmpurile vechi (excitatie_sustinuta,
    legaturi_echipotentiale), pentru compatibilitate"""
    v = str(inp.get("ge_protectie") or "").strip().lower()
    if v in ("excitatie", "excitatie_sustinuta", "excitație"):
        return "excitatie"
    if v in ("echipotential", "echipotentiale", "legaturi_echipotentiale"):
        return "echipotential"
    if inp.get("legaturi_echipotentiale") is True:
        return "echipotential"
    if inp.get("excitatie_sustinuta") is True:
        return "excitatie"
    return None


def _text_optiuni_ge():
    return " ".join(f"({i}) {o['titlu']} — când: {o['cand']} Implică: {o['implica']} Pe planșă: {o['desen']}"
                    for i, o in enumerate(GE_PROTECTIE_OPTIUNI, 1))


def schema_ge(inp, j):
    """echipa1 P1-8 + E2: în regim GE, protecția la contact indirect a circuitelor fără DDR (siguranță) trebuie ASIGURATĂ
    explicit. Fără alegere → BLOCANT cu cele două soluții explicate (`optiuni`); `ge_protectie` = „excitatie” (Ik
    susținut ≥ 3·In_G ≥ 2 s + Q_G electronic) sau „echipotential” (SR HD 60364-4-41 art. 415.2)."""
    alegere = ge_protectie_aleasa(inp)
    if alegere == "excitatie" and not inp.get("excitatie_sustinuta"):
        inp = dict(inp, excitatie_sustinuta=True)
    n0 = len(j.verificari)
    rez = _schema_ge_baza(inp, j)
    echip = alegere == "echipotential"
    optiuni = [dict(o) for o in GE_PROTECTIE_OPTIUNI]
    rem = ("alege una dintre cele două soluții (câmpul ge_protectie): " + _text_optiuni_ge()
           + " Pentru circuitele normale rămâne și varianta DDR pe plecare.")
    afectat = False
    for v in j.verificari[n0:]:
        regim_ge = "regim GE" in (v.get("mesaj") or "")
        if v.get("cod") in ("V85", "V97") and regim_ge and v.get("nivel") in (AVERTISMENT, BLOCANT) \
                and not (v.get("cod") == "V85" and "bloc diferențial" in (v.get("mesaj") or "")):
            afectat = True
            if echip:
                v["nivel"] = INFO
                v["mesaj"] += (" — protecția la contact indirect se asigură prin legături echipotențiale suplimentare "
                               "confirmate de proiectant (SR HD 60364-4-41 art. 415.2); R ≤ 50 V/Ia de măsurat la PIF")
            elif alegere == "excitatie":
                v["nivel"] = BLOCANT
                v["mesaj"] += (" — chiar cu excitație susținută (Ik1 = 3·In_G) deconectarea nu se realizează")
                v["remediere"] = ("reglează Isd al Q_G (declanșator electronic) sub Ik1 din regim GE, scurtează C2 / C3 "
                                  "sau alege legăturile echipotențiale suplimentare (ge_protectie = „echipotential”)")
                v["optiuni"] = optiuni
            else:
                v["nivel"] = BLOCANT
                v["remediere"] = rem
                v["optiuni"] = optiuni
                v["camp"] = "ge_protectie"
    if alegere or afectat:
        o = next((x for x in GE_PROTECTIE_OPTIUNI if x["valoare"] == alegere), None)
        rez["protectie_regim_GE"] = {
            "solutie": alegere, "necesara": afectat,
            "titlu": o["titlu"] if o else "neleasă — de ales una dintre soluții",
            "implica": o["implica"] if o else "", "desen": o["desen"] if o else "",
            "Ik_sustinut_A": (norme.GE_IK_SUSTINUT_MULTIPLU * rez["In_G_A"] if alegere == "excitatie" and rez.get("In_G_A") else None),
            "t_sustinut_s": norme.GE_IK_SUSTINUT_T_S if alegere == "excitatie" else None,
            "optiuni": optiuni}
        if alegere == "excitatie":
            j.pas(f"Regim GE: excitație susținută — Ik ≥ {fmt_ro(norme.GE_IK_SUSTINUT_MULTIPLU, 0)}·In_G timp de ≥ "
                  f"{fmt_ro(norme.GE_IK_SUSTINUT_T_S, 0)} s (declarația producătorului GE), Q_G electronic")
        elif alegere == "echipotential":
            j.pas("Regim GE: protecție la contact indirect prin legături echipotențiale suplimentare "
                  "(SR HD 60364-4-41 art. 415.2), R ≤ 50 V/Ia verificat prin măsurare la PIF")
    return rez


def _schema_ge_baza(inp, j):
    """SPEC §C.6: In_G, Q_G, Ik3" GE, Q rețea, ATS (4P, interblocaj, AC-33B), deconectarea în regim GE (V85), V86, V87.
    v1.2: Q_G MCCB/ACB cu Ir ≤ In_G (M3, protecție strictă la suprasarcină), Icu QR ≥ Ik3 rețea și QG ≥ Ik3 GE,
    cablurile C1 (rețea → ATS, QR), C2 (GE → ATS, QG) și C3 (ATS → consumatori) dimensionate ca ramuri B.21."""
    rez = {}
    U = SQRT3 * norme.U_N_V
    if tensiune_jt_nesuportata(inp, j, inp.get("consumatori") if isinstance(inp.get("consumatori"), list) else None):
        return rez
    rezerva = _fd(inp.get("sursa_rezerva") or "").lower()
    if rezerva in ("trafo", "transformator", "pt", "t2", "trafo_2", "trafo2"):
        return _schema_ats_trafo(inp, j)
    if rezerva and rezerva not in ("ge", "grup_electrogen", "generator"):
        emite(j, "V12", BLOCANT, "schema", "camp", camp="sursa_rezerva", valoare=inp.get("sursa_rezerva"))
        j.verificari[-1]["remediere"] = "sursa de rezervă „ge” (grup electrogen) sau „trafo” (ATS între două transformatoare)"
        return rez
    if _bool(inp.get("bara_vitala")):
        return _schema_tg_normal_vital(inp, j)
    if _bool(inp.get("fara_retea")):
        return _schema_ge_izolat(inp, j)
    p_normali = _separa_consumatori_retea(inp, j, rez)
    if inp.get("retea") == "mono":
        # r6 (#33): GE monofazat — nesuportat (ATS 2P, In_G = S/230 V, Ik în regim GE monofazat) → nu se înlocuiește
        # tăcut cu un GE trifazat
        emite(j, "V96", BLOCANT, "schema", ce="GE monofazat", detaliu="motorul calculează doar GE trifazat 3P+N cu ATS 4P",
              remediere="la o casă: schema locuinței cu generator de rezervă (ge_rezerva: Sn_kVA, comutare „manual” / "
                        "„ATS”) — monofazat suportat; altfel GE trifazat sau schemă de specialitate (ATS 2P)")
        return rez
    if inp.get("ge_paralel"):
        # r6 (#34): GE în paralel cu rețeaua ≠ ATS (comutare). Desenul rămâne de comutare, marcat explicit
        emite(j, "V96", AVERTISMENT, "schema", ce="GE în paralel cu rețeaua (sincronizare)",
              detaliu="desenul e de COMUTARE (ATS, surse niciodată în paralel) — panoul de sincronizare, protecția de "
                      "interfață (27/59, 81, 32R, ROCOF / vector shift) și avizul OD pentru funcționarea în paralel NU sunt "
                      "modelate",
              remediere="proiect de specialitate pentru sincronizare + protecția de interfață (Ord. ANRE 208/2018, ATR), "
                        "sau confirmați funcționarea pe ATS")
        rez["ge_paralel_nesuportat"] = True
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
    # echipa1 P1-8: GE cu excitație susținută → Q_G cu declanșator electronic (Isd reglat sub curentul de defect susținut)
    qg = pr.construieste(tip_g, In_G, ir_g, are_aval=True, decl="EL" if inp.get("excitatie_sustinuta") else None)
    qg["Icu_kA"], ok_g = pr.alege_icu(tip_g, ik3 / 1000.0)
    rez["Q_G"] = {"tip": tip_g, "In_A": In_G, "Ir_A": qg["Ir_A"], "Ir_multiplu": qg["Ir_multiplu"],
                  "Icu_kA": qg["Icu_kA"], "decl": qg.get("decl")}
    j.pas(f"GE {fmt_ro(sn)} kVA: In_G = {fmt_ro(in_g)} A; Ik3'' ≈ 1,1·In_G/x''d = {fmt_ro(ik3 / 1000.0)} kA; "
          f"Q_G {tip_g} {In_G} A, Ir = {fmt_ro(qg['Ir_multiplu'])}·In = {fmt_ro(qg['Ir_A'])} A ≤ In_G, "
          f"Icu {fmt_ro(qg['Icu_kA'])} kA")
    if not ok_g:
        emite(j, "V33", BLOCANT, "Q_G", icu=qg["Icu_kA"], ik3=ik3 / 1000.0)

    cos = inp.get("cosfi", norme.COSFI_IMPLICIT["tablou"])
    cons = inp.get("consumatori")
    if isinstance(cons, list) and cons:
        # r5 (P0-4): lista consumatorilor vitali se ADUNĂ (n × P), nu se ia doar primul receptor
        # r7 (#31): unitățile de rezervă („pompă rezervă”, `rezerva: true`, n „1+1”) NU se adună (nu funcționează simultan)
        try:
            nn = [_n_rezerva(c) for c in cons]
            ps = sum((n - nr) * float(c["P_kW"]) for c, (n, nr) in zip(cons, nn))
            ps_tot = sum(n * float(c["P_kW"]) for c, (n, _) in zip(cons, nn))
        except (KeyError, TypeError, ValueError, AttributeError):
            emite(j, "V07", BLOCANT, "schema", "param", camp="consumatori", x=repr(cons)[:60],
                  conditie="fiecare consumator are P_kW (și opțional n)")
            return rez
        rez["consumatori"] = cons
        p_dat = inp.get("P_sarcina_kW")
        if p_dat is None or (any(nr for _, nr in nn) and abs(float(p_dat) - ps_tot) < 1e-6):
            inp["P_sarcina_kW"] = ps
            j.pas("Sarcina vitală = " + " + ".join(f"{fmt_ro(n - nr, 0)}×{fmt_ro(c['P_kW'])}" for c, (n, nr) in zip(cons, nn)
                                                   if n - nr) + f" = {fmt_ro(ps)} kW"
                  + (f" (unitățile de rezervă, {fmt_ro(ps_tot - ps)} kW, nu se adună — interblocate cu cele active)"
                     if ps_tot > ps + 1e-9 else ""))
            if ps_tot > ps + 1e-9:
                j.presupune("pompa (unitatea) de rezervă nu funcționează simultan cu cea activă — interblocaj / automatizare "
                            "de comutare; sarcina GE fără rezervă")
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
    sig_tab = tablou_de_siguranta(inp)
    _cons = inp.get("consumatori") if isinstance(inp.get("consumatori"), list) else []
    if not sig_tab and _cons and len(_consumatori_siguranta(inp)) == sum(
            (_n_rezerva(c)[0] if isinstance(c, dict) else 1) for c in _cons):
        # r8 (#12): toți consumatorii GE sunt de siguranță → tabloul întreg e de siguranță (alimentări FE180, TPI)
        sig_tab = True
    rez["siguranta_tot"] = sig_tab

    def cablu(L):
        """Cablul unei ramuri GE/ATS (implicit Al PVC D1, ca alimentarea unui tablou)."""
        c = dict(cab0)
        if "material" not in c and sig_tab:
            # r7 (#31): tablou de siguranță — alimentările (rețea → ATS, GE → ATS) Cu XLPE rezistent la foc (E90)
            c.update({"material": "Cu", "izolatie": c.get("izolatie") or "XLPE"})
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
    sr = inp.get("sursa_retea")
    if sr == "pt" and inp.get("origine") is None:
        inp["origine"] = "pt_propriu"
    rez["sursa_retea"] = sr or ("pt" if inp.get("origine") == "pt_propriu" else None)
    if sr == "tgd":
        # r5 (P1-14): ramura de rețea vine dintr-un TGD existent (nu prin BMPT) — Ik3 la bara TGD declarat sau majorant
        ik3s = inp.get("Ik3_sursa_kA")
        zb = _zb_din_intrare(inp.get("Zb_OD_ohm"), j)
        ddr_r = inp.get("IdN_amonte_mA") is not None
        ctx_r = sc.context_od(ik3s, zb, ddr_amonte=ddr_r)
        if ik3s is None:
            j.presupune(f"Ik3max la bara TGD existent {fmt_ro(norme.OD_IK3MAX_IMPLICIT_KA)} kA (majorant implicit) — "
                        f"Ik3_sursa_kA de introdus")
        if zb is None:
            j.presupune("Zbuclă la TGD existent 0,18 + j0,09 Ω (implicită) — se confirmă din calculul instalației existente")
        j.presupune("rețeaua normală: plecare din TGD existent")
        j.ipoteza("ik3_od", ctx_r["Ik3_kA"], ik3s is None)
    elif inp.get("origine") == "pt_propriu":
        sn_pt = inp.get("pt_Sn_kVA")
        if sn_pt is not None:
            if int(sn_pt) not in norme.TRAFO or float(sn_pt) != int(sn_pt):
                emite(j, "V05", BLOCANT, "schema", "trafo", Sn=sn_pt, vecini=", ".join(str(x) for x in norme.TRAFO_SN_KVA))
                return rez
            nt = n_trafo_sursa(inp, j, f"PT propriu {int(sn_pt)} kVA")
            t = trafo_sursa(inp, j, int(sn_pt), inp.get("trafo_izolatie"), *(nt or (1, False)))
            if nt is None or t is None:
                return rez
            if inp.get("SkQ_MVA") is None:
                j.presupune("S\"kQ = 500 MVA, R/X = 0,1 (rețea MT, majorant)")
            j.ipoteza("skq", t["SkQ_MVA"], inp.get("SkQ_MVA") is None)
            j.ipoteza("trafo", (t["uk_pct"], t["Pk_W"]), not t.get("uk_declarat"))
            ctx_r = sc.context_pt(t)
            rez["PT_retea"] = {"Sn_kVA": int(sn_pt), "In_T_A": t["In_T_A"], "Ik3max_bara_kA": t["Ik3max_bara_kA"],
                               "n_trafo": nt[0]}
            sn_pt = nt[0] * int(sn_pt) if nt[1] else sn_pt
            s_sarc = SQRT3 * norme.U_N_V * ib / 1000.0 + p_normali / cos     # r9: + consumatorii normali (doar rețea)
            if gt(s_sarc, float(sn_pt)):
                emite(j, "V62", BLOCANT, "schema", "ge", x=s_sarc, y=sn_pt)
            j.presupune(f"rețeaua normală: bara JT a PT propriu {sn_pt} kVA")
        else:
            ctx_r = _context_od(inp, j, ddr_amonte=False)
            ctx_r["origine"] = "pt_propriu"
            j.presupune(f"rețeaua normală: PT propriu cu Sn necunoscut — Ik3max 25 kA și Zbuclă {fmt_ro(norme.OD_ZBUCLA_MODUL_IMPLICIT_OHM, 2)} Ω implicite")
    else:
        if gt(ib, norme.BMPT_I_MAX_A):
            emite(j, "V50", BLOCANT, "schema", "ib", Ib=ib)
            j.verificari[-1]["remediere"] = ("ramura de rețea din PT (sursa_retea „pt”, cu Sn PT) sau dintr-un TGD existent "
                                             "(sursa_retea „tgd”)")
            return rez
        ddr_amonte = inp.get("ddr_amonte", True)
        if inp.get("ddr_amonte") is None and (tablou_de_siguranta(inp) or _consumatori_siguranta(inp)):
            # r7 (#31): alimentarea normală a consumatorilor de siguranță se racordează înaintea DDR-ului general (fără
            # RCCB 300 mA în amonte) — nu se contează pe un DDR în amonte pentru deconectare
            ddr_amonte = False
            j.presupune("consumatori de siguranță: alimentarea din rețea racordată înaintea DDR-ului general (fără RCCB "
                        "300 mA în amonte, I7/2011, P118-3) — de confirmat cu OD / proiectul de branșament")
        ctx_r = _context_od(inp, j, ddr_amonte=ddr_amonte)
        if ddr_amonte:
            j.presupune("rețeaua normală: rețea publică prin BMPT cu RCCB 300 mA în amonte"
                        + ("" if sr == "bmpt" else " (sursa rețelei nedeclarată)"))
    in_r = inp.get("In_Q_retea_A")
    tip_r = "MCCB" if (in_r if in_r is not None else ib) <= 1600 + 1e-9 else "ACB"
    r1 = {"rol": "intrare", "receptor": "tablou", "retea": "tri", "Ib_A": ib, "cosfi": cos, "prot_tip": tip_r,
          "cablu": cablu(lung("L_C1_m", "L_m", 50.0, "C1 (rețea → ATS)")), "are_aval": True, "_validat": True}
    if in_r is not None:
        r1["In_fortat"] = in_r
    sig0 = _consumatori_siguranta(inp)
    if sig0 and in_r is None:
        # r9 (#27): QR alimentează plecările de siguranță — calibrul lui ≥ cel mai mare calibru al unei plecări de
        # siguranță (selectivitate amonte ≥ aval; o pompă de incendiu nu se pierde prin declanșarea QR)
        ins = []
        for c in sig0:
            rec = c.get("receptor") or ("motor" if (c.get("pornire") or "pomp" in _fara_diacritice(c["nume"]).lower()
                                                    or receptor_dupa_nume(c["nume"], 1) == "motor") else "forta")
            rp = {"rol": "plecare", "receptor": rec, "retea": "tri", "P_kW": float(c["P_kW"]), "ddr": False,
                  "cablu": {"material": "Cu", "izolatie": "XLPE", "metoda": "C", "L": 30.0}, "_doar_protectie": True}
            if rec == "motor":
                rp["prot_tip"] = "MCCB"
            if c.get("pornire"):
                rp["pornire"] = c["pornire"]
            try:
                p_ = calculeaza_ramura(rp, {"Ik3_kA": 1.0, "origine": "retea_publica", "dU_pct": 0.0}, Jurnal(),
                                       "tmp").get("prot")
            except Exception:      # noqa: BLE001 — estimarea nu blochează calculul
                p_ = None
            if p_ and p_.get("In_A"):
                ins.append(float(p_["In_A"]))
        if ins and gt(max(ins), ib):
            r1["Ip_min_extra"] = max(ins) + 0.01
            j.pas(f"QR alimentează plecările de siguranță: Ip,min ≥ max In plecare de siguranță = {fmt_ro(max(ins))} A "
                  f"(amonte ≥ aval)")
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
    if p_normali:
        # r9 (#24): plecarea consumatorilor normali din bara rețelei (înaintea ATS) — protecție proprie QN, nu trece
        # prin ATS și nu e alimentată din GE
        rn = {"rol": "plecare", "receptor": "tablou", "retea": "tri", "P_kW": p_normali, "cosfi": cos,
              "cablu": cablu(lung("L_normali_m", None, 50.0, "plecare consumatori normali (rețea)")), "are_aval": True}
        rrn = calculeaza_ramura(rn, ctx_r, j, "QN·consumatori normali")
        rez["plecare_retea"] = dict(rrn["rezultat"], descriere="consumatori normali — doar rețea, înaintea ATS")

    # C2: GE → ATS, protejat de Q_G (Ib = Ir_G: cablul transportă puterea GE)
    ik1_ge = norme.GE_IK_SUSTINUT_MULTIPLU * in_g if inp.get("excitatie_sustinuta") else in_g
    rez["Ik1_regim_GE_A"] = ik1_ge
    ctx_g = _context_ge(in_g, sn, xd, ik1_ge)
    # v1.2 R2 (N-C1, SR HD 60364-4-41 art. 411.4.5, SR HD 60364-5-55 art. 551.4): în regim GE Ik1 ≈ In_G nu atinge Ia
    # al Q_G → protecția la contact indirect se face cu un bloc diferențial 300 mA tip A, selectiv (S), asociat Q_G
    # (acționează pe tot circuitul alimentat din GE: C2, ATS, C3). Refuzat explicit (`DDR_GE: false`) → V85 BLOCANT.
    ddr_ge = None
    sig = _consumatori_siguranta(inp)
    if sig:
        # r6 (#32, #35): circuitele de siguranță (pompe de incendiu, hidranți) NU trec prin DDR — nici DDR-G 300 mA pe
        # Q_G (I7/2011, P118-3, SR HD 60364-5-56 art. 560.7). Pe Q_G: monitorizare diferențială RCM (doar alarmă)
        rez["Q_G"]["RCM"] = {"IdN_mA": 300, "functie": "monitorizare curent diferențial — doar semnalizare (SR EN 62020)"}
        j.pas("Circuite de siguranță pe GE: " + ", ".join(c["nume"] for c in sig) + " — fără DDR (nici DDR-G); RCM cu "
              "alarmă pe Q_G")
        ctx_g["ge_siguranta"] = True
    elif inp.get("DDR_GE", True) is not False:
        ddr_ge = {"aparat": "bloc_diferential", "asociat": "Q_G", "tip_q": tip_g, "IdN_mA": 300, "tip": "A",
                  "selectiv": True, "In_A": In_G, "poli": "4P"}
        rez["Q_G"]["DDR"] = ddr_ge
        ctx_g["ddr_ramura"] = "bloc diferențial 300 mA S pe Q_G"
        j.pas(f"Regim GE: Ik1 ≈ {fmt_ro(ik1_ge, 0)} A — protecție la contact indirect prin bloc diferențial 300 mA tip A, "
              f"S, asociat Q_G {tip_g} {In_G} A")
    r2 = {"rol": "qg", "receptor": "tablou", "retea": "tri", "Ib_A": qg["Ir_A"], "cosfi": cos, "prot_tip": tip_g,
          **({"decl_fortat": "EL"} if inp.get("excitatie_sustinuta") else {}),
          "In_fortat": In_G, "Icu_fortat": qg["Icu_kA"], "cablu": cablu(lung("L_C2_m", "L_GE_ATS_m", 20.0, "C2 (GE → ATS)")),
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
    manual = str(inp.get("comutare") or "").strip().lower() in ("manual", "manuala", "inversor", "i-0-ii")
    interb = inp.get("ATS_interblocaj", "mecanic (poziția 0 între I și II)" if manual else "mecanic + electric")
    rez["ATS"] = {"poli": poli, "In_A": in_ats, "interblocaj": interb, "categorie": "AC-23B" if manual else "AC-33B",
                  "intrari": {"I": "rețea (QR, C1)", "II": "GE (Q_G, C2)"}, "iesire": "C3 → consumatori"}
    if manual:
        # r8 (#48, S9): comutator MANUAL de sursă I-0-II (inversor cu poziția 0) — nu ATS automat
        rez["ATS"]["comutare"] = "manual"
        j.pas(f"Comutator manual de sursă I-0-II 4P (inversor, AC-23B) In ≥ max(Q rețea {qr['In_A']} A; Q GE {In_G} A) → "
              f"{in_ats} A; poziția 0 între rețea și GE (interblocaj mecanic intrinsec)")
        j.presupune("comutare manuală a sursei (inversor I-0-II): pornirea GE și comutarea se fac de operator — fără "
                    "automatizare de anclanșare a rezervei")
    else:
        j.pas(f"ATS 4P In ≥ max(Q rețea {qr['In_A']} A; Q GE {In_G} A) → {in_ats} A; intrări distincte I (rețea) / II (GE)")
    if (rez.get("Sn_GE_minim_kVA") and inp.get("P_sarcina_kW") is not None
            and gt(sn, 2.5 * rez["Sn_GE_minim_kVA"]) and lt(qr["In_A"] * 2, in_ats)):
        # r5 (P0-4): QR dimensionat pe o sarcină mult sub GE (ex. 50 A lângă ATS 400 A) — de obicei sarcina e incompletă
        emite(j, "V86", AVERTISMENT, "schema", "supra", Sn_GE=fmt_ro(sn, 0), P=fmt_ro(inp["P_sarcina_kW"]),
              Sn=rez["Sn_GE_minim_kVA"], qr=qr["In_A"], ats=in_ats)
        j.verificari[-1]["remediere"] = "sarcina vitală completă (Σ consumatori) sau GE mai mic"
    if not isinstance(poli, (int, float)) or poli < 4:
        emite(j, "V87", BLOCANT, "schema", detaliu=f"cu {poli} poli în TN-S (sunt necesari 4 poli, comută și N)")
    if not interb or "mecanic" not in str(interb) or ("electric" not in str(interb) and not manual):
        emite(j, "V87", BLOCANT, "schema", detaliu="fără interblocaj mecanic + electric")
    rez["neutru_GE"] = "legat la priza de pământ locală (TN-S); ATS 4P comută și N"

    # C3: ATS → consumatori. v1.2 R2 (N-C1): se calculează SEPARAT în ambele regimuri — rețea (QR, sursa = capătul C1)
    # și GE (Q_G, sursa = capătul C2) — cu aceeași secțiune (cea mai mare dintre cele două dimensionări)
    if rr1["blocat"] or rr2["blocat"]:
        _nota_spl(rez, inp, "ge_ats")
        return rez
    ib3 = ib
    if sig:
        p_sig = sum(float(c["P_kW"]) for c in sig if not c.get("_rezerva"))
        rez["plecari_siguranta"] = _plecari_siguranta_ge(sig, inp, rr1, rr2, j=j)
        if inp.get("P_sarcina_kW") is not None:
            p_ns = float(inp["P_sarcina_kW"]) - p_sig
            if p_ns <= 1e-6:
                # toată sarcina e de siguranță: fără C3; deconectarea în regim GE — V97 (fără DDR)
                prot_g0 = rr2["prot"] or qg
                if prot_g0.get("decl") == "EL" and prot_g0.get("Isd_A") is None:
                    pr.alege_isd(prot_g0, ik1_ge)
                ia0 = pr.ia(prot_g0, 5.0)
                if ia0 is not None and lt(ik1_ge, ia0):
                    emite(j, "V97", AVERTISMENT, "schema", "ge", x=round(ik1_ge), y=ia0)
                _nota_spl(rez, inp, "ge_ats")
                return rez
            ib3 = p_ns * 1000.0 / (U * cos)
            j.pas(f"C3 (consumatori normali): P = {fmt_ro(inp['P_sarcina_kW'])} − {fmt_ro(p_sig)} (siguranță) = "
                  f"{fmt_ro(p_ns)} kW → Ib = {fmt_ro(ib3)} A; DDR 300 mA S pe plecarea C3")
    L3 = lung("L_C3_m", "L_m", 50.0, "C3 (ATS → consumatori)")
    r3r = {"rol": "intrare", "receptor": "tablou", "retea": "tri", "Ib_A": ib3, "cosfi": cos, "prot_tip": qr["tip"],
           "In_fortat": qr["In_A"], "Icu_fortat": qr.get("Icu_kA"), "cablu": cablu(L3), "are_aval": True,
           "_validat": True}
    r3r["Ip_min_extra"] = pr.ip(qr) + 1e-6 if gt(pr.ip(qr), ib3) else None
    r3g = dict(r3r, prot_tip=tip_g, In_fortat=In_G, Icu_fortat=qg["Icu_kA"], cablu=cablu(L3),
               Ip_min_extra=qg["Ir_A"] - 1e-9)     # Q_G rămâne reglat la Ir_G (nu se re-reglează după sarcină)
    ctx3g = dict(rr2["ctx_aval"], regim_ge=True)
    if ddr_ge:
        ctx3g["ddr_ramura"] = "bloc diferențial 300 mA S pe Q_G"
    if sig:
        # r6: cu circuite de siguranță pe bara ATS, consumatorii normali au plecare proprie (QC3 + DDR 300 mA S)
        for rr_ in (r3r, r3g):
            for k in ("In_fortat", "Icu_fortat", "Ip_min_extra"):
                rr_.pop(k, None)
            rr_["prot_tip"] = "MCCB"
            rr_["rol"] = "plecare"
            rr_["ddr"] = {"IdN_mA": 300, "selectiv": True, "tip": "A"}
        ctx3g["ge_siguranta"] = True
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
    if sig:
        rez["C3"]["QC3"] = True       # plecare cu protecție proprie (rez["C3"]["protectie"] + DDR) din bara ATS

    # deconectarea în regim GE (SPEC §C.6 pct. 4) — verificată în cel mai defavorabil punct (capătul C3, regim GE)
    prot_g = rr2["prot"] if not rr2["blocat"] else qg
    if prot_g.get("decl") == "EL" and prot_g.get("Isd_A") is None:
        pr.alege_isd(prot_g, ik1_ge)
    ia_g = pr.ia(prot_g, 5.0)
    ik1_min = rr3g["rezultat"].get("Ik1min_capat_A", ik1_ge) if not rr3g["blocat"] else ik1_ge
    if ia_g is not None and lt(ik1_min, ia_g) and sig:
        # consumatorii normali (C3) au DDR 300 mA S propriu; circuitele de siguranță nu pot avea DDR
        emite(j, "V97", AVERTISMENT, "schema", "ge", x=round(ik1_min), y=ia_g)
    elif ia_g is not None and lt(ik1_min, ia_g):
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
            return f"presupus ({impl}, DECIZIE proiectant 28.10.2026) — se confirmă cu OD / ATR"
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
    if isinstance(inp, dict) and inp.get("tip_schema") in ("cef", "bess"):
        normalizeaza_cascada(inp)          # r12: tablouri intermediare (cascade CEF)
    if isinstance(inp, dict) and inp.get("tip_schema") == "bess":
        inp["tip_schema"] = "cef"          # v1.9 (R5): BESS de sine stătător = CEF fără invertoare PV (SPEC §C.3)
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


def _trafo_neacoperit(inp, j, tip):
    """r10 (industrial i08 / i30): mai multe transformatoare declarate (`n_trafo` / `pt_n_trafo` > 1) într-o schemă care
    nu le poate folosi (branșament, locuință, tablou fără PT sursă, …) → BLOCANT explicit, nu un trafo pierdut tăcut."""
    n = inp.get("n_trafo", inp.get("pt_n_trafo"))
    if n is None or isinstance(n, bool) or not _numar(n) or n <= 1:
        return False
    if tip in ("pt", "cef"):
        return False
    pt_sn = inp.get("pt_Sn_kVA") is not None
    if tip == "tablou" and pt_sn and inp.get("origine") == "pt_propriu":
        return False
    if tip == "ge_ats" and pt_sn and (inp.get("sursa_retea") == "pt" or inp.get("origine") == "pt_propriu"
                                      or inp.get("sursa_rezerva") is not None):
        return False
    if tip == "prosumator" and pt_sn:
        return False
    emite(j, "V96", BLOCANT, "schema", ce=f"{int(n)} transformatoare declarate la schema „{tip}”",
          detaliu="schema aleasă nu are un PT sursă în care să intre transformatoarele (lipsește pt_Sn_kVA / originea PT) "
                  "— nu se desenează cu un singur trafo",
          remediere="declarați PT-ul sursă (origine „pt_propriu”, pt_Sn_kVA, n_trafo, cupla „inchisa” / „deschisa”) sau "
                    "schema PT (tip „pt”, Sn_kVA, n_trafo)")
    return True


def _chei_nesuportate(inp, j, tip):
    """r11: cheile de intrare pe care schema `tip` nu le folosește → V96 BLOCANT „nesuportat: …” cu remediere (nu se
    ignoră în tăcere); calculul continuă, exportul e blocat. Lista cheilor: `engine/calc/chei.py`."""
    from .chei import chei_nefolosite
    nf = chei_nefolosite(inp, tip)
    if not nf:
        return
    txt = ", ".join(f"„{c + '.' if c else ''}{k}”" for c, k in nf[:8]) + (f" (+{len(nf) - 8})" if len(nf) > 8 else "")
    emite(j, "V96", BLOCANT, "schema", ce=f"date pe care schema „{tip}” nu le folosește: {txt}",
          detaliu="s-ar pierde în tăcere — planșa nu le-ar reprezenta",
          remediere="eliminați datele respective sau alegeți tipul de schemă care le reprezintă (ex. UPS / bară vitală / "
                    "PT cu 2 trafo — vezi cheile acceptate în engine/calc/chei.py)")
    j.verificari[-1]["chei"] = [f"{c + '.' if c else ''}{k}" for c, k in nf]


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
    elif _trafo_neacoperit(inp, j, tip):
        rez = {}
    else:
        _chei_nesuportate(inp, j, tip)
        try:
            rez = f(inp, j)
        except (KeyError, TypeError, ValueError, ZeroDivisionError, AttributeError, IndexError) as e:
            camp = f"câmpul {e} lipsește" if isinstance(e, KeyError) else f"{type(e).__name__}: {e}"
            emite(j, "V07", BLOCANT, "schema", "intern", detaliu=camp)
            rez = {}
    return j, rez
