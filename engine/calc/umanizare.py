"""echipa1 (ux problema 5) — textele arătate omului (mesajele verificărilor, remedierile, întrebările interpretorului)
nu conțin denumiri interne: chei JSON („In_Q_bransament_A”), constante de cod („norme.LOCUINTA_RECEPTORI”), căi de
fișiere. Ultima trecere înainte de interfață: cheie → denumirea românească.
Calea tehnică a câmpului rămâne în cheia separată `camp` a verificării (interfața o folosește pentru „du-mă la câmp”).
"""
import re

from .locuinta import ETICHETE, ETICHETE_RECEPTOR

CHEI = dict(ETICHETE)
CHEI.update({
    "pt_Sn_kVA": "puterea PT (kVA)", "Sn_kVA": "puterea transformatorului (kVA)", "Sn_GE_kVA": "puterea GE (kVA)",
    "In_Q1_A": "calibrul întreruptorului general", "In_Q_JT_A": "calibrul Q JT", "In_QG_A": "calibrul QG",
    "In_Q_retea_A": "calibrul Q rețea", "L_racord_m": "lungimea cablului de racord", "L_alimentare_m": "lungimea alimentării",
    "L_coloana_m": "lungimea coloanei", "L_inv_m": "lungimea cablurilor invertoarelor", "L_pcs_m": "lungimea cablului PCS",
    "P_sarcina_kW": "puterea sarcinii", "P_evacuata_kW": "puterea evacuată aprobată", "Pn_inv_kW": "puterea invertorului",
    "compensare_kvar": "bateria de compensare (kvar)", "compensare_L_m": "lungimea cablului bateriei de compensare",
    "circuite_finale": "circuite finale", "n_trafo": "numărul de transformatoare", "n_tgd_cf": "numărul de tablouri TGD-CF",
    "racord_In_Q_A": "calibrul aparatului de racord", "Ik3_TG_kA": "Ik3 la bara TG", "Ik3_sursa_kA": "Ik3 la sursă",
    "Zb_TG_ohm": "impedanța buclei la TG", "U_MT_kV": "tensiunea MT", "masura_pt": "locul măsurii", "pt_existent": "PT existent",
    "schema_pamant": "schema de legare la pământ", "excitatie_sustinuta": "excitație susținută",
    "legaturi_echipotentiale": "legături echipotențiale suplimentare", "limitare_kW": "limitarea puterii VE",
    "limitare_injectie_kW": "limitarea injecției", "In_T": "In trafo", "In_G": "In GE", "Q_G": "QG",
    "In_T_A": "In trafo", "In_G_A": "In GE", "Ir_G": "Ir GE", "tip_schema": "tipul lucrării",
    "atr_jt": "racord JT conform ATR", "bess": "BESS", "invertoare": "invertoarele", "consumatori": "consumatorii",
    "plecari": "plecările", "circuite": "circuitele",
})
CHEI.update({k: v.lower() for k, v in ETICHETE_RECEPTOR.items()})

CONSTANTE = {
    "LOCUINTA_RECEPTORI": "lista receptoarelor de locuință", "TRAFO": "seria standard de transformatoare",
    "GE_SN_KVA": "seria standard a grupurilor electrogene", "MCCB_IN_A": "seria standard MCCB",
    "MCB_IN_A": "seria standard MCB", "GG_IN_A": "seria standard de siguranțe gG",
}

_RE_NORME = re.compile(r"\bnorme\.([A-Z0-9_]+)\b")
_RE_CHEIE = re.compile(r"(?<![\w./])([A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+|Q_G|In_T|In_G)(?![\w/])")
_RE_FISIER = re.compile(r"\s*\(?(?:vezi\s+)?(?:cheile\s+acceptate\s+în\s+)?engine/[\w/.]+\)?")


def umanizeaza(s):
    if not isinstance(s, str) or not s:
        return s
    s = _RE_FISIER.sub("", s)
    s = _RE_NORME.sub(lambda m: CONSTANTE.get(m.group(1), "tabelul de valori standard"), s)
    s = re.sub(r"\b(GE_SN_KVA|LOCUINTA_RECEPTORI)\b", lambda m: CONSTANTE[m.group(1)], s)
    s = _RE_CHEIE.sub(lambda m: CHEI.get(m.group(1), m.group(1)), s)
    return s


def umanizeaza_verificari(ver):
    for v in ver or []:
        if isinstance(v, dict):
            for k in ("mesaj", "remediere"):
                if isinstance(v.get(k), str):
                    v[k] = umanizeaza(v[k])
    return ver
