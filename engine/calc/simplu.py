"""simplu.py — dimensionarea unei singure ramuri pentru panoul „Dimensionează” din interfață.

    dimensioneaza_ramura_simpla(p: dict) -> dict

Contextul implicit (SPEC §B.0): bara unui TG alimentat din rețeaua publică — Ik3max 25 kA și Zbuclă 0,18 + j0,09 Ω
implicite (declarate), RCCB 300 mA din BMPT în amonte, ΔU la origine 0 %. Cu `origine = "pt_propriu"`: limite ΔU 6/8 %,
fără DDR în amonte (SPEC §B.1.1). Lanțul de calcul este exact cel din §B.21 (`ramura.calculeaza_ramura`).
"""
from . import norme
from . import cabluri as cb
from . import scurtcircuit as sc
from .comun import Jurnal
from .ramura import calculeaza_ramura
from .texte import text_lista, text_desen, text_cablu
from .verificari import emite, BLOCANT

CAMPURI_CABLU = ("material", "izolatie", "metoda", "n_alte", "theta", "rho_sol", "S_fortat", "n_fortat", "tip_cablu")


def _parametri_protectie(prot, retea):
    """Parametrii E.3 ai protecției ramurii (SPEC §E.1 pct. 1: textele se generează din parametri)."""
    t = prot["tip"]
    if t == "MCB":
        return "MCB", {"poli": "1P+N" if retea == "mono" else 4, "curba": prot.get("curba", "C"),
                       "In_A": prot["In_A"], "Icn_kA": prot.get("Icu_kA")}
    if t in ("MCCB", "ACB"):
        p = {"poli": 2 if retea == "mono" else 4, "In_A": prot["In_A"], "Ir_A": prot.get("Ir_A"),
             "Icu_kA": prot.get("Icu_kA"), "declansator": prot.get("decl")}
        for k in ("Im_A", "Isd_A", "Isd_multiplu", "tsd_s", "Ii_A"):
            if prot.get(k) is not None and not (k == "tsd_s" and not prot[k]):
                p[k] = prot[k]
        return t, p
    return "separator_sigurante", {"poli": 1 if retea == "mono" else 3, "In_A": prot["In_A"]}


def dimensioneaza_ramura_simpla(p):
    """SPEC §B.21 pentru o ramură izolată (plecare dintr-un TG sau circuit final), cu contextul implicit §B.0.

    Intrare `p`: P_kW | In_A; cosfi, L_m, material, izolatie, metoda, n_alte, retea (tri|mono), receptor,
    rol (plecare|final), prot_tip, curba, origine (retea_publica|pt_propriu), Ik3_origine_kA, dU_origine_pct.
    Ieșire: {"rezultat": {… cheile unei plecări din golden …}, "verificari", "info", "blocheaza", "pasi", "presupus",
    "text_desen": [rânduri protecție], "text_lista": (denumire, caracteristici) protecție, "text_cablu": str,
    "text_lista_cablu": (denumire, caracteristici), "text_desen_cablu": [rânduri]}."""
    j = Jurnal()
    p = dict(p or {})
    rol = p.get("rol") or "plecare"
    if rol not in ("plecare", "final"):
        rol = "plecare"
    retea = p.get("retea") or "tri"
    receptor = p.get("receptor") or "forta"
    rez = {"rezultat": None, "verificari": j.verificari, "info": j.info, "blocheaza": True, "pasi": j.pasi,
           "presupus": j.presupus, "text_desen": [], "text_lista": None, "text_cablu": None,
           "text_lista_cablu": None, "text_desen_cablu": []}

    surse = [k for k in ("P_kW", "In_A") if p.get(k) is not None]
    if len(surse) > 1:
        emite(j, "V12", BLOCANT, "ramura", "surse", surse=", ".join(surse), poli="", retea=retea)
        rez["presupus"] = j.presupus
        return rez

    # contextul barei de origine (SPEC §B.0, §B.1)
    origine = p.get("origine") or "retea_publica"
    ik3 = p.get("Ik3_origine_kA")
    ctx = sc.context_od(ik3, None, ddr_amonte=(origine != "pt_propriu"))
    ctx["origine"] = origine
    if ik3 is None:
        j.presupune("Ik3max la bara de origine 25 kA (valoare implicită OD, majorant pentru Icu)")
    j.presupune("Zbuclă la origine 0,18 + j0,09 Ω (valoare implicită OD, minorant pentru Ik1)")
    if origine != "pt_propriu":
        j.presupune("bara unui TG alimentat din rețeaua publică, prin BMPT cu RCCB 300 mA în amonte")
    else:
        j.presupune("bara unui TG din PT propriu (limite ΔU 6/8 %, fără DDR în amonte)")
    if p.get("dU_origine_pct") is not None:
        ctx["dU_pct"] = float(p["dU_origine_pct"])
    else:
        j.presupune("ΔU la bara de origine 0 %")

    final = rol == "final"
    cab = {k: p[k] for k in CAMPURI_CABLU if p.get(k) is not None}
    cb.metoda_implicita(cab, "C" if final else "D1")
    if "material" not in cab:
        cab["material_implicit"] = True
        cab["material"] = "Al" if cab["metoda"] in norme.METODE_IN_PAMANT else "Cu"
        if cab["material"] == "Al":
            j.presupune("cablu Al PVC în pământ, cu trecere pe Cu sub 16 mm²")
    L = p.get("L_m")
    if L is None:
        L = 25.0 if final else 50.0
        j.presupune(f"lungime {fmt_l(L)} m")
    cab["L"] = float(L)

    r = {"rol": rol, "receptor": receptor, "retea": retea, "cablu": cab}
    for k in ("P_kW", "In_A", "cosfi", "prot_tip", "curba", "ks", "h3"):
        if p.get(k) is not None:
            r[k] = p[k]
    out = calculeaza_ramura(r, ctx, j, p.get("nume") or "ramura")
    rez.update({"rezultat": out["rezultat"], "verificari": j.verificari, "info": j.info, "pasi": j.pasi,
                "presupus": j.presupus,
                "blocheaza": out["blocat"] or any(v["nivel"] == "BLOCANT" for v in j.verificari)})
    if out["blocat"]:
        return rez
    rr = out["rezultat"]
    tip, par = _parametri_protectie(rr["protectie"] | {k: v for k, v in out["prot"].items()
                                                         if k not in rr["protectie"]}, retea)
    rez["text_lista"] = text_lista(tip, par)
    rez["text_desen"] = text_desen(tip, par)
    rez["text_cablu"] = rr["cablu"]
    pc = {k: rr[k] for k in ("material", "izolatie", "metoda", "n_paralel", "S_faza_mm2", "S_N_mm2", "S_PE_mm2",
                             "PE", "retea", "Iz_corectat_A", "k_total", "dU_ramura_pct", "L_m")}
    rez["text_lista_cablu"] = text_lista("cablu", pc)
    rez["text_desen_cablu"] = text_desen("cablu", pc)
    return rez


def fmt_l(L):
    """Lungimea formatată RO pentru declarația valorii implicite (SPEC §E.2)."""
    from .texte import fmt_ro
    return fmt_ro(L, 0)
