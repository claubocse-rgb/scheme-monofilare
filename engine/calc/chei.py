"""r11 — cheile de intrare pe care motorul le FOLOSEȘTE, pe tip de schemă (refuz cinstit al cheilor necunoscute).

Testerii r11 au găsit text „forțat” într-o altă schemă: o cheie emisă de interpretor, dar necitită de schema aleasă,
dispărea tăcut (ex. `n_tgd_cf`, `plecari[].ups`, `circuite_casa`). Regula: orice cheie de intrare care nu e în lista
schemei → V96 BLOCANT „nesuportat: …” cu remediere (planșa se calculează în continuare, exportul e blocat).

Excepțiile pur informative (date de cartuș / comentarii, chei interne `_…`) sunt în `INFORMATIVE`.
"""
from .scheme import CAMPURI_CABLU_SCHEMA, CHEI_TENSIUNE_JT, CHEI_UK

# date care nu schimbă schema (cartuș, comentarii, contractul interpretorului) — acceptate la orice tip
INFORMATIVE = frozenset({"beneficiar", "titlu", "obiectiv", "adresa", "proiect", "observatii", "nota", "note", "comentariu",
                         "descriere", "nr_atr", "atr", "localitate", "judet"})

COMUNE = frozenset({"tip_schema", "schema_pamant", "RA_ohm", "retea", "priza", *CHEI_TENSIUNE_JT})

_SURSA_PT = {"pt_Sn_kVA", "n_trafo", "pt_n_trafo", "cupla", "bara", "bara_racord", "SkQ_MVA", "trafo_izolatie",
             "grupa_conexiuni", "pt_grupa_conexiuni", *CHEI_UK}
_OD = {"Ik3_OD_kA", "Zb_OD_ohm", "DDR_amonte_selectiv", "IdN_amonte_mA", "ddr_amonte"}

CHEI = {
    "bransament": {"Ib_A", "P_kW", "S_kVA", "In_A", "Q_In_A", "L_coloana_m", "cablu", "cosfi", "ks", "masura_ceruta",
                   "bmpt_fortat", "DDR_bransament_tip", "origine", "n_trafo", "pt_n_trafo", *CAMPURI_CABLU_SCHEMA, *_OD},
    "tablou": {"plecari", "origine", "P_kW", "In_A", "In_Q1_A", "Q1_tip", "Q1_DDR", "Q_general_tip", "L_alimentare_m",
               "cablu", "cosfi", "ks", "h3", "h3_pct", "circuite_finale", "compensare_kvar", "compensare_L_m",
               "Ik3_sursa_kA", "Ik3_bara_kA", "dU_origine_pct", "titlu_tablou", "nume_tablou", "separare_PEN",
               "siguranta_tablou", "siguranta", "aar", "plecari_pe_sectie", "plecari_pe_semibara", *_SURSA_PT, *_OD},
    "pt": {"Sn_kVA", "plecari", "U_MT_kV", "In_Q_JT_A", "Q_general_tip", "Q_JT_tip", "aparat", "Q1_tip", "celula_trafo",
           "celule_mt", "cablu_MT", "compensare_kvar", "compensare_L_m", "cupla", "aar", "masura", "masura_pt", "n_trafo",
           "plecari_pe_sectie", "plecari_pe_semibara", "pt_aerian", "trafo_izolatie", "SkQ_MVA", "ks", "cosfi",
           "grupa_conexiuni", "pt_grupa_conexiuni", "siguranta_tablou", "siguranta", "titlu_tablou", "dg_intreruptor",
           "OD", "punct_conexiune", "compartimente", *CHEI_UK},
    "ge_ats": {"Sn_GE_kVA", "consumatori", "plecari", "P_sarcina_kW", "Ib_sarcina_A", "sursa_retea", "sursa_rezerva",
               "fara_retea", "ge_paralel", "bara_vitala", "comutare", "ATS_poli", "ATS_interblocaj", "DDR_GE", "xd",
               "excitatie_sustinuta", "legaturi_echipotentiale", "In_QG_A", "In_Q_retea_A", "L_C1_m", "L_C2_m", "L_C3_m", "L_GE_ATS_m", "L_m",
               "L_normali_m", "L_alimentare_m", "cablu", "cosfi", "ks", "origine", "Ik3_sursa_kA", "Sn_T_kVA", "Sn_T2_kVA",
               "Sn_kVA", "siguranta", "siguranta_tablou", "titlu_tablou", *_SURSA_PT, *_OD},
    "cef": {"invertoare", "bess", "kWp", "modul", "string", "racord", "pt_Sn_kVA", "pt_existent", "pt_od", "n_trafo",
            "cupla", "bara", "bara_racord", "n_tgd_cf", "masura", "masura_pt", "celule_mt", "celula_trafo", "In_Q_JT_A",
            "trafo_izolatie", "SkQ_MVA", "grupa_conexiuni", "atr_jt", "limitare_injectie_kW", "P_aprobata_kW",
            "P_evacuata_kW", "Pn_total_kW", "In_QG_A", "In_Q_bransament_A", "L_racord_m", "L_inv_m", "L_pcs_m", "cablu",
            "cablu_C0", "cablu_inv", "cablu_pcs", "cablu_cc", "U_ca_V", "U_inv_ca_V", "gpv_In_A", "gpv", "spd_cc",
            "Ucpv_V", "racord_In_Q_A", "racord_Icu_kA", "racord_Q_tip", "Ik3_TG_kA", "Ik3_sursa_kA", "Ik3_bara_kA",
            "Zb_TG_ohm", "cosfi", "tablouri_intermediare", "QG", "racord_Ir_A", "racord_Isd_A", "racord_decl",
            "monitorizare", "protectie_interfata", "cablu_MT", "dg_intreruptor", "OD", "punct_conexiune", "planse", "compartimente",
            *CHEI_UK, *_OD},
    "prosumator": {"invertoare", "invertor", "Pn_inv_kW", "hibrid", "Iac_max_A", "baterie", "baterie_kWh", "bess",
                   "backup", "kWp", "modul", "string", "racord", "PI_externa", "protectii_cc", "protectii_ca", "P_aprobata_kW", "P_evacuata_kW",
                   "limitare_injectie_kW", "In_QG_A", "In_Q_bransament_A", "L_racord_m", "L_inv_m", "L_coloana_m",
                   "cablu", "cablu_C0", "cablu_inv", "cablu_pcs", "comercial", "pt_Sn_kVA", "n_trafo", "trafo_izolatie", "SkQ_MVA",
                   "gpv", "gpv_In_A", "spd_cc", "Ucpv_V", "invertor_baterie", "contor_productie", "monitorizare",
                   "protectie_interfata", "planse", *_OD},
    "locuinta": {"alimentare", "circuite", "tablouri_secundare", "ge_rezerva", "ks", "Q_general_tip", "Ik3_OD_kA",
                 "Zb_OD_ohm", "separare_PEN"},
}
CHEI["cascada"] = CHEI["tablou"]

PLECARE = frozenset({"nume", "P_kW", "In_A", "S_kVA", "Sn_kVA", "L_m", "cablu", "receptor", "pornire", "cosfi", "ks",
                     "prot_tip", "curba", "In_fortat", "Icu_fortat", "h3", "h3_pct", "randament", "DDR", "ddr", "copii",
                     "n", "n_circuite", "in_tablou", "retea", "rezerva", "siguranta", "sectie", "ups", "bypass",
                     "bypass_manual", "intrari_separate", "autonomie_min", "vital", "faza", "U_V", "titlu", "tip",
                     "Ir_A", "Isd_A", "decl"})
CONSUMATOR = frozenset({"nume", "P_kW", "n", "n_rezerva", "rezerva", "siguranta", "vital", "pe_ge", "normal", "ramura",
                        "pornire", "receptor", "cosfi", "L_m", "cablu", "retea", "prot_tip", "In_A", "S_kVA", "DDR", "ddr",
                        "ks", "faza", "h3_pct", "copii"})
INVERTOR = frozenset({"n", "Pn_kW", "producator", "model", "Iac_max_A", "Idc_max_A", "Isc_max_A", "Umax_dc_V",
                      "MPPT_min_V", "MPPT_max_V", "nr_MPPT", "hibrid", "existent", "faza", "retea", "U_ca_V", "sectie",
                      "tgd", "cablu", "L_m", "ddr", "IdN_min_mA", "tip_ddr", "spd_ca", "string", "modul",
                      "separator_cc_integrat", "tablou", "prot_tip", "protectie"})
LISTE = {"plecari": PLECARE, "consumatori": CONSUMATOR, "invertoare": INVERTOR}


def _gol(v):
    """echipa1 P0-1: valoare goală (None, "", {}, []) — interfața adaugă `cablu: {}` peste tot; o cheie goală nu poartă
    nicio dată, deci nu are ce „să se piardă în tăcere” → se ignoră (nu V96)"""
    return v is None or (isinstance(v, str) and not v.strip()) or (isinstance(v, (dict, list, tuple)) and not v)


def _ignorata(k, v=None):
    return not isinstance(k, str) or k.startswith("_") or k in INFORMATIVE or _gol(v)


def chei_nefolosite(inp, tip):
    """[(cale, cheie)] — cheile pe care schema `tip` nu le folosește (nivelul 1 și elementele listelor plecari /
    consumatori / invertoare, recursiv pe `copii`)."""
    acc = CHEI.get(tip)
    if acc is None or not isinstance(inp, dict):
        return []
    out = [("", k) for k, v in inp.items() if not _ignorata(k, v) and k not in COMUNE and k not in acc]

    def lista(cale, xs, permise):
        for i, x in enumerate(xs if isinstance(xs, list) else []):
            if not isinstance(x, dict):
                continue
            out.extend((f"{cale}[{i}]", k) for k, v in x.items() if not _ignorata(k, v) and k not in permise)
            if x.get("copii"):
                lista(f"{cale}[{i}].copii", x["copii"], PLECARE)

    for camp, permise in LISTE.items():
        if camp in acc and camp in inp:
            lista(camp, inp[camp], permise)
    return out
