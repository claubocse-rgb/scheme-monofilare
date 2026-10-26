"""locuinta.py — tabloul electric al unei case / al unui apartament (SPEC §C.8, v1.7).

Branșament (BMPM / BMPT, existent sau nou) → coloana C2 → tabloul locuinței (TE): Q general (întreruptor-separator
sau MCB), SPD T2, grupe DDR 30 mA (RCCB 2P pe o fază / 4P cu circuite 3F; RCBO pentru circuitul singur) și circuitele
finale, cu bilanțul de puteri, repartizarea pe faze și verificarea Q-ului de branșament pe faza cea mai încărcată.
Valorile implicite pe receptor sunt în `norme.LOCUINTA_RECEPTORI` și se declară ca presupuse (V11).

v1.5 (runda 4 de testare, `teste/r4/proiectant.md`, `teste/r4/verificator.md`):
* V46 pe faza cea mai încărcată (Ib de calcul pe fază, cu ks), BLOCANT peste 1,13·In sau peste In la sarcini continue;
* P aprobată declarată → Ib general / coloana / Q general din puterea aprobată, Pc din ks informativ (V46 AV);
* Q branșament nedeclarat → Q presupus = calibrul standard ≥ Ib (nu mai mic decât sarcina), peste limita blocului BLOCANT;
* TT: protecția la defect = DDR (RA·IΔn ≤ 50 V), Ik1/Ia doar pentru scurtcircuitul L–N (V30 „TT”);
* toate circuitele finale cu DDR ≤ 30 mA (V49), MCB / Q general > Q branșament → V40 BLOCANT;
* grupe DDR: max. 5 circuite, iluminatul separat de prize (≥ 2 grupe de iluminat la ≥ 2 circuite), grupe pe o fază → 2P,
  cu circuite 3F → 4P, circuit singur → RCBO; sauna pe DDR propriu, cu cablu termorezistent.

v1.6 (runda 4b, `teste/r4/proiectant_b.md`, `teste/r4/verificator_b.md`, `teste/r4/ux_b.md`):
* N2 — coloana C2 se mărește întâi (buget ΔU 1,5 %), abia apoi circuitele finale; m8 — coloana pe faza cea mai încărcată;
* m-n3 — repartizarea pe faze pe curentul de CALCUL (3F, faze impuse, apoi monofazatele descrescător, inclusiv din 4P);
* N5 / m-n5 — Q / P aprobată nedeclarate la branșament existent → V46 AVERTISMENT vizibil; mesajele pe Q presupus o spun;
* P1-4 — iluminat: max. 2 circuite pe DDR, nivelurile deduse din nume nu se amestecă; P2-1 — V43 agregat;
* SPD.protectie_rezerva; alimentare.zona (Zbuclă rurală); TT — coloana „L + N”, PE din priza locală;
* rezultate parțiale: un circuit invalid e marcat `blocat` și restul se calculează; mesajele fără chei interne (`camp`).

v1.7 (runda 4c, `teste/r4/proiectant_c.md`, `teste/r4/verificator_c.md`, `teste/r4/ux_c.md`):
* M-c1 — Q branșament în afara seriei → V05 cu `camp`, Q ignorat, calculul continuă cu Q presupus (treapta superioară /
  limita blocului); m-c4 — Zb_OD_ohm / RA_ohm / Ik3_OD_kA invalide → V07 cu `camp`, ignorate (valoarea implicită);
* N11 — Zbucla rurală e „presupus (zonă rurală, [NEVERIFICAT]) — se confirmă cu OD / ATR”, nu „din ATR”;
* M-c3 — VE sub DDR-ul 300 mA tip AC / A / F al branșamentului → V43 „ve_dc” (AV; TT: BLOCANT);
* m-c5 / C3 — dicționarele centrale ETICHETE_RECEPTOR / ETICHETE (fără chei interne în mesaje și presupuneri);
* m-c6 — creșterea pentru ΔU a circuitelor finale plafonată la 16 mm² (V20 cu remedierea „mărește coloana”);
* N16 — prizele (și celelalte grupe) pe niveluri deduse din nume; N17 — VE dimensionat normal (minim 4 mm²);
* N13 — cosφ în ipoteze cu eticheta receptorului și „presupus” / „declarat” corect; nota ks fără „după 0 receptoare”.
"""
import math
import re

from . import norme
from . import ddr as ddr_mod
from . import protectii as pr
from .comun import Jurnal, ge, gt, lt, prima_din_serie, SQRT3
from .ramura import calculeaza_ramura
from .texte import fmt_ro, NB, nota_schema_pamant
from .verificari import emite, BLOCANT, AVERTISMENT, INFO

CAMPURI_R = ("P_mono", "P_tri", "cosfi", "curba", "In_mono", "In_tri", "S_mono", "S_tri", "L", "calcul", "tri_posibil",
             "grupa", "ddr", "ddr_tip", "continuu")
TIPURI_ALIMENTARE = ("bransament_existent", "bransament_nou")
FAZE = ("L1", "L2", "L3", "3F")
CHEI_CIRCUIT = ("nume", "receptor", "P_kW", "L_m", "faza", "cablu", "In_A", "DDR", "cosfi", "curba")
NUME_GRUPE = {"VE": "vehicul electric", "baie": "baie", "bucatarie": "bucătărie", "exterior": "exterior",
              None: "general", "fara": "fără DDR", "iluminat": "iluminat", "sauna": "saună", "propriu": "propriu"}
ORDINE_GRUPE = ("iluminat", None, "bucatarie", "baie", "exterior")
# v1.5: pozarea coloanei C2 (alimentare.pozare_coloana) → metoda IEC 60364-5-52
POZARE_COLOANA = {"pamant": "D1", "in_pamant": "D1", "ingropat": "D1", "d1": "D1",
                  "cladire": "B2", "in_cladire": "B2", "tub": "B2", "perete": "B2", "b2": "B2",
                  "aparent": "C", "c": "C"}
SERIE_Q_MONO = norme.BMPM["Q_in_A"]
SERIE_Q_TRI = sorted({v for b in ("BMPTd-16", "BMPTd-40", "BMPTd-100") for v in norme.BMPT[b]["Q_in_A"]})
SERIE_Q_TRI_TOATE = sorted({v for b in norme.BMPT for v in norme.BMPT[b]["Q_in_A"]})
LIMITA_BLOC = {"mono": ("BMPM", norme.BMPM["I_max_A"]), "tri": ("BMPTd-100", norme.BMPT["BMPTd-100"]["I_max_A"])}
CHEI_DDR = ("IdN_mA", "tip", "selectiv", "dt_s")
ZONE = {"urban": "urban", "oras": "urban", "rural": "rural", "sat": "rural"}
# v1.6 (UX 13): denumirile românești ale câmpurilor de intrare — mesajele nu conțin chei interne; câmpul tehnic merge
# în cheia separată `camp` a verificării (ex. "alimentare.In_Q_bransament_A", "circuite[3].P_kW")
ETICHETE = {"P_kW": "puterea circuitului", "L_m": "lungimea circuitului", "In_A": "calibrul impus", "cosfi": "cosφ",
            "curba": "curba MCB", "faza": "faza", "receptor": "receptorul", "DDR": "DDR impus", "cablu": "cablul",
            "nume": "numele", "S_fortat": "secțiunea impusă", "material": "materialul cablului",
            "metoda": "metoda de pozare", "izolatie": "izolația cablului",
            "In_Q_bransament_A": "Q branșament", "P_aprobata_kW": "puterea aprobată (ATR)",
            "L_coloana_m": "lungimea coloanei", "pozare_coloana": "pozarea coloanei", "zona": "zona (urban / rural)",
            "tip": "tipul alimentării", "ks": "coeficientul de simultaneitate", "Q_general_tip": "tipul Q general",
            "IdN_mA": "IΔn DDR", "selectiv": "temporizarea DDR (S)", "dt_s": "temporizarea DDR",
            "alimentare": "alimentarea", "circuit": "circuitul", "Zb_OD_ohm": "impedanța buclei OD",
            "Ik3_OD_kA": "Ik3 OD", "RA_ohm": "rezistența prizei de pământ RA", "S_kVA": "puterea aparentă",
            "Ib_A": "curentul de calcul", "DDR_bransament_tip": "tipul DDR-ului din branșament",
            "IdN_amonte_mA": "IΔn al DDR-ului din amonte"}
# v1.7 (runda 4c, m-c5 / UX C3): dicționarul central receptor → denumirea românească (aceeași ca în interfață,
# `static/index.html` RECEPTOR_LOC); folosit în mesaje, presupuneri, ipoteze și memoriu — cheile interne nu apar în texte
ETICHETE_RECEPTOR = {
    "iluminat": "Iluminat", "prize": "Prize", "prize_bucatarie": "Prize bucătărie", "prize_baie": "Prize baie",
    "prize_exterior": "Prize exterior", "masina_spalat_rufe": "Mașină de spălat rufe",
    "masina_spalat_vase": "Mașină de spălat vase", "uscator": "Uscător de rufe", "boiler": "Boiler", "cuptor": "Cuptor",
    "plita": "Plită", "aer_conditionat": "Aer condiționat", "pompa_caldura": "Pompă de căldură",
    "centrala_termica": "Centrală termică", "incalzire_electrica": "Încălzire electrică",
    "vehicul_electric": "Încărcător vehicul electric", "pompa_apa": "Pompă apă / hidrofor",
    "poarta_automata": "Poartă automată", "sauna": "Saună", "alt_circuit": "Alt circuit",
    "tablou_secundar": "Tablou secundar"}
# câmpurile globale (nivelul schemei) ale locuinței validate local (m-c4): valoarea invalidă se ignoră, nu oprește calculul
CAMPURI_GLOBALE_IGNORABILE = {"Zb_OD_ohm": "Ω", "RA_ohm": "Ω", "Ik3_OD_kA": "kA"}


def eticheta_receptor(cheie):
    """Denumirea românească a unui receptor al locuinței (cheia necunoscută rămâne ca atare, fără „_”)."""
    return ETICHETE_RECEPTOR.get(cheie) or str(cheie).replace("_", " ")


def eticheta_camp(cheie):
    """Denumirea românească a unui câmp de intrare al locuinței."""
    return ETICHETE.get(cheie) or str(cheie).replace("_", " ")
# câmpul unui circuit pe care îl privește o verificare fără câmp numit în mesaj (UX 13)
CAMP_DUPA_COD = {"V04": "In_A", "V05": "In_A", "V09": "L_m", "V13": "cablu.S_fortat", "V07": "P_kW"}
# v1.6 (P1-4): nivelul circuitului de iluminat dedus din nume (fără diacritice, litere mici)
NIVELURI = ((r"\b(sub|demi)sol", "subsol"), (r"\bparter", "parter"),
            (r"\bmansard", "mansarda"), (r"\b(exterior|ext\b|curte|gradin|fatad|terasa|gard)", "exterior"),
            (r"\b(etaj|et\.?)\s*(\d+)", "etaj{}"), (r"\betaj", "etaj1"), (r"\bpod\b", "pod"))


def _rec(cheie):
    return dict(zip(CAMPURI_R, norme.LOCUINTA_RECEPTORI[cheie]))


def _numar(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _cablu_valid(cab, j, ob, camp):
    """Validează și NORMALIZEAZĂ pe loc dicționarul `cablu` (v1.5, m4: „cu” → Cu, „b2” → B2). Întoarce copia sau None."""
    from .scheme import _valideaza_dict
    if not isinstance(cab, dict):
        emite(j, "V07", BLOCANT, ob, "param", camp=camp, x=repr(cab), conditie="se așteaptă un obiect")
        return None
    cab = dict(cab)
    return cab if _valideaza_dict(cab, j, ob, sari=("L",)) else None


def _zb_valid(zb):
    """Aceeași regulă ca validarea generală (scheme._valideaza_intrare): modul > 0 sau pereche (R, X) ≥ 0, |Z| > 0."""
    if isinstance(zb, dict):
        vals = [zb.get("R", zb.get("R_ohm")), zb.get("X", zb.get("X_ohm"))]
    elif isinstance(zb, (list, tuple)):
        vals = list(zb)
    else:
        vals = [zb]
    if len(vals) not in (1, 2) or not all(_numar(v) for v in vals):
        return False
    if len(vals) == 1:
        return vals[0] > 0
    return vals[0] >= 0 and vals[1] >= 0 and math.hypot(vals[0], vals[1]) > 0


def prevalideaza(inp, j):
    """v1.7 (runda 4c, m-c4): câmpurile globale ale locuinței (Zb_OD_ohm, RA_ohm, Ik3_OD_kA) invalide → V07 BLOCANT cu
    `camp` și mesaj fără chei interne; valoarea se IGNORĂ (se folosește valoarea implicită, declarată ca presupusă), iar
    calculul continuă (rezultat parțial, exportul refuzat). Se apelează înaintea validării generale a schemei."""
    if not isinstance(inp, dict):
        return
    for k, um in CAMPURI_GLOBALE_IGNORABILE.items():
        v = inp.get(k)
        if v is None:
            continue
        ok = _zb_valid(v) if k == "Zb_OD_ohm" else (_numar(v) and v > 0)
        if ok:
            continue
        if k != "Zb_OD_ohm" and not _numar(v):
            x, cond = f"„{v}”" if isinstance(v, str) else repr(v), "valoare nenumerică (se așteaptă un număr)"
        else:
            x = f"{fmt_ro(v, 3)} {um}" if _numar(v) else repr(v)
            cond = ("trebuie > 0 (modul |Z| sau pereche (R, X) cu R, X ≥ 0)" if k == "Zb_OD_ohm" else "trebuie > 0")
        emite(j, "V07", BLOCANT, "schema", "param", camp=eticheta_camp(k), x=x,
              conditie=cond + " — valoarea se ignoră, calculul continuă cu valoarea implicită (presupusă)")
        v07 = j.verificari[-1]
        v07["camp"] = k
        v07["remediere"] = f"introdu {eticheta_camp(k)} ca număr pozitiv (din ATR / avizul OD / buletinul de măsurare)"
        inp.pop(k)
        j.presupune(f"{eticheta_camp(k)} invalidă → ignorată, se folosește valoarea implicită")


def _cu_camp(j, camp):
    """Pune `camp` pe ultima verificare emisă (dacă nu îl are deja)."""
    if j.verificari:
        j.verificari[-1].setdefault("camp", camp)


def _valideaza(inp, j, retea):
    """Validarea specifică locuinței (V07 / V09 / V10 / V12 BLOCANT). Întoarce (alimentare, circuite) sau None.

    v1.6 (UX 12, rezultate parțiale): o eroare LOCALĂ (un câmp al alimentării, un circuit) nu mai oprește calculul —
    câmpul invalid se ignoră (se folosește valoarea implicită, declarată), circuitul rămâne marcat `_blocat` (cu
    V-ul lui BLOCANT, exportul rămâne refuzat), iar restul se calculează normal. None doar fără niciun circuit."""
    from .scheme import _valideaza_dict, _valideaza_ddr, _fd
    al = inp.get("alimentare")
    if al is None:
        al = {}
    if not isinstance(al, dict):
        emite(j, "V07", BLOCANT, "alimentare", "param", camp="alimentare", x=repr(al), conditie="se așteaptă un obiect")
        al = {}
    al = dict(al)
    t = al.get("tip", "bransament_existent")
    if t not in TIPURI_ALIMENTARE:
        emite(j, "V12", BLOCANT, "alimentare", "camp", camp="alimentare.tip", valoare=t)
        t = "bransament_existent"
    al["tip"] = t
    for k in ("In_Q_bransament_A", "P_aprobata_kW", "L_coloana_m"):
        v = al.get(k)
        if v is not None and (not _numar(v) or v <= 0):
            if k == "L_coloana_m" and _numar(v):
                emite(j, "V09", BLOCANT, "alimentare", "B", L=v)
            else:
                # v1.7 (P2 verificator): textul spune „nenumerică” la text, nu „trebuie > 0”
                emite(j, "V07", BLOCANT, "alimentare", "param", camp=f"alimentare.{k}",
                      x=v if _numar(v) else (f"„{v}”" if isinstance(v, str) else repr(v)),
                      conditie="trebuie > 0" if _numar(v) else "valoare nenumerică (se așteaptă un număr)")
            _cu_camp(j, f"alimentare.{k}")
            al.pop(k)
            al.setdefault("_invalide", []).append(k)
    q = al.get("In_Q_bransament_A")
    if q is not None:
        # v1.7 (M-c1): Q în afara seriei (ex. 33 A; 63 A la monofazat) → V05 cu `camp`, Q ignorat; calculul continuă cu Q
        # presupus = calibrul standard imediat superior / limita blocului (exportul rămâne refuzat)
        serie = SERIE_Q_MONO if retea == "mono" else SERIE_Q_TRI_TOATE
        if q not in serie:
            sus = [x for x in serie if x > q]
            jos = [x for x in serie if x < q]
            emite(j, "V05", BLOCANT, "Q", In=q, tip="RCBO BMPM (ST 3-JT)" if retea == "mono" else "Q BMPT (ST 4-JT)",
                  vecini=f"{jos[-1] if jos else '—'} A / {sus[0] if sus else '—'} A")
            j.verificari[-1]["camp"] = "alimentare.In_Q_bransament_A"
            al.pop("In_Q_bransament_A")
            al["_q_invalid"] = q
    tb = al.get("DDR_bransament_tip")
    if tb is not None:
        # v1.7 (M-c3): tipul DDR-ului 300 mA din blocul de branșament (implicit AC, ST 3-JT / ST 4-JT)
        tbn = str(tb).strip().upper() if isinstance(tb, str) else None
        if tbn not in norme.LOCUINTA_DDR_TIPURI:
            emite(j, "V12", BLOCANT, "alimentare", "camp", camp="alimentare.DDR_bransament_tip", valoare=tb)
            al.pop("DDR_bransament_tip")
        else:
            al["DDR_bransament_tip"] = tbn
    if al.get("cablu") is not None:
        cab = _cablu_valid(al["cablu"], j, "C2", "alimentare.cablu")
        if cab is None:
            al.pop("cablu")
        else:
            al["cablu"] = cab
    pz = al.get("pozare_coloana")
    if pz is not None:
        met = POZARE_COLOANA.get(_fd(pz)) if isinstance(pz, str) else None
        if met is None:
            emite(j, "V12", BLOCANT, "C2", "camp", camp="alimentare.pozare_coloana", valoare=pz)
            al.pop("pozare_coloana")
        else:
            al["pozare_coloana"] = met
    zn = al.get("zona")
    if zn is not None:
        z = ZONE.get(_fd(zn)) if isinstance(zn, str) else None
        if z is None:
            emite(j, "V12", BLOCANT, "alimentare", "camp", camp="alimentare.zona", valoare=zn)
            al.pop("zona")
        else:
            al["zona"] = z
    circ = inp.get("circuite")
    if not isinstance(circ, list) or not circ:
        emite(j, "V07", BLOCANT, "schema", "plecari", tablou="tabloul locuinței")
        return None
    out = []
    for i, c in enumerate(circ, 1):
        nume = c.get("nume", "") if isinstance(c, dict) else ""
        nume = "" if nume is None else str(nume)          # v1.5 (m3): numele numeric → text
        ob = f"C{i}·{nume}"
        blocat = []
        if not isinstance(c, dict):
            emite(j, "V07", BLOCANT, ob, "param", camp="circuit", x=repr(c), conditie="se așteaptă un obiect")
            c, blocat = {}, ["V07"]
        c = dict(c)
        c["nume"] = nume
        for k in c:
            if k not in CHEI_CIRCUIT:
                # v1.5 (m12): cheile necunoscute nu se ignoră tacit
                emite(j, "V12", AVERTISMENT, ob, "necunoscut", camp=k,
                      acceptate=", ".join(ETICHETE.get(x, x) for x in CHEI_CIRCUIT))
        c = {k: v for k, v in c.items() if k in CHEI_CIRCUIT}
        rec = c.pop("receptor", None)
        if rec is None:
            rec = "alt_circuit"
            j.presupune("receptor nedeclarat → „Alt circuit” (2 kW, C16, 2,5 mm²)", ob)
        if not isinstance(rec, str) or rec.strip().lower() not in norme.LOCUINTA_RECEPTORI:
            emite(j, "V12", BLOCANT, ob, "camp", camp="receptor", valoare=rec)
            rec, blocat = "alt_circuit", blocat + ["V12"]
        rec = rec.strip().lower()
        f = c.pop("faza", None)
        if f is not None:
            fs = str(f).strip().upper()
            if fs not in FAZE or (retea == "mono" and fs not in ("L1",)):
                emite(j, "V12", BLOCANT, ob, "camp", camp="faza", valoare=f)
                fs, blocat = None, blocat + ["V12"]
            f = fs
        ddr_c = c.pop("DDR", None)
        if isinstance(ddr_c, dict):
            for k in ddr_c:
                if k not in CHEI_DDR:
                    # v1.6 (m-n4): cheile necunoscute ale DDR-ului impus nu se ignoră tacit
                    emite(j, "V12", AVERTISMENT, ob, "necunoscut", camp=f"DDR.{k}",
                          acceptate="IΔn, tipul DDR (AC / A / F / B), temporizare S, Δt")
            ddr_c = {k: v for k, v in ddr_c.items() if k in CHEI_DDR}
            if not _valideaza_ddr(ddr_c, j, ob, "DDR"):
                ddr_c, blocat = None, blocat + ["V12"]
            else:
                ddr_c = dict(ddr_c)
                if ddr_c.get("tip") is not None:
                    ddr_c["tip"] = str(ddr_c["tip"]).upper()
                if ddr_c.get("selectiv") and int(ddr_c["IdN_mA"]) < 100:
                    # v1.5 (m9): DDR 30 mA de tip S nu există
                    emite(j, "V12", BLOCANT, ob, "ddr_s", IdN=int(ddr_c["IdN_mA"]))
                    ddr_c, blocat = None, blocat + ["V12"]
        if ddr_c is not None and not isinstance(ddr_c, dict) and ddr_c is not False:
            emite(j, "V12", BLOCANT, ob, "camp", camp="DDR", valoare=ddr_c)
            ddr_c, blocat = None, blocat + ["V12"]
        cab = c.pop("cablu", None)
        if cab is not None:
            cab = _cablu_valid(cab, j, ob, "cablu")
            if cab is None:
                blocat.append("V10")
        nm = c.pop("nume")
        for k in list(c):
            # câmp cu câmp: un câmp invalid se ignoră (valoarea implicită), circuitul rămâne blocat
            d1 = {k: c[k]}
            n0 = len(j.verificari)
            if not _valideaza_dict(d1, j, ob, sari=("P_kW", "L_m")):
                blocat.append(j.verificari[-1]["cod"] if len(j.verificari) > n0 else "V12")
                c.pop(k)
            elif k in d1:
                c[k] = d1[k]
        for k, cod in (("P_kW", "V07"), ("L_m", "V09")):
            v = c.get(k)
            if v is not None and v <= 0:
                if cod == "V09":
                    emite(j, "V09", BLOCANT, ob, "B", L=v)
                else:
                    emite(j, "V07", BLOCANT, ob, P=v)
                c.pop(k)
                blocat.append(cod)
        if c.get("P_kW") is not None and c["P_kW"] > norme.LOCUINTA_P_CIRCUIT_MAX_KW:
            emite(j, "V07", BLOCANT, ob, "param", camp="P_kW", x=c["P_kW"],
                  conditie=f"neplauzibil pentru un circuit de locuință (> {fmt_ro(norme.LOCUINTA_P_CIRCUIT_MAX_KW, 0)} kW)")
            c.pop("P_kW")
            blocat.append("V07")
        if c.get("L_m") is not None and c["L_m"] > 1000:
            emite(j, "V09", AVERTISMENT, ob, "AV", L=c["L_m"])
        out.append(dict(c, nume=nm, receptor=rec, faza=f, DDR=ddr_c, cablu=cab, obiect=ob, idx=i, _blocat=blocat))
    return al, out


VE_CURENTI_NOMINALI_A = (6, 10, 13, 16, 20, 25, 32, 40, 63)   # curenții de încărcare uzuali ai stațiilor (IEC 61851)
VE_FACTOR_CONTINUU = 1.25          # DECIZIE [NEVERIFICAT]: sarcină continuă — In ≥ 1,25·I încărcare (practica producătorilor)
MCB_SERIE_VE = (10, 13, 16, 20, 25, 32, 40, 50, 63)


def curent_ve(p_kw, tri):
    """r9 (locuințe #42, #44, #69): curentul nominal de încărcare al stației VE din puterea ei — P/(3·230) sau P/230,
    rotunjit la curentul nominal uzual (7,4 kW → 32 A, 3,7 kW → 16 A, 11 kW tri → 16 A, 22 kW tri → 32 A)."""
    i = p_kw * 1000.0 / ((3 if tri else 1) * norme.U_0_V)
    return next((x for x in VE_CURENTI_NOMINALI_A if x >= i * 0.97), i)


def calibru_ve(p_kw, tri):
    """r9: calibrul MCB al circuitului VE = treapta ≥ 1,25 · I încărcare (3,7 kW → C20, 7,4 kW → C40, 11 kW tri → C20,
    22 kW tri → C40) — nu C40 indiferent de putere."""
    t = VE_FACTOR_CONTINUU * curent_ve(p_kw, tri)
    return next((x for x in MCB_SERIE_VE if x >= t - 1e-9), MCB_SERIE_VE[-1])


def _circuit(c, retea, j):
    """Intrarea B.1 a unui circuit al locuinței, cu valorile implicite ale receptorului (declarate)."""
    d = _rec(c["receptor"])
    tri = retea == "tri" and (c["faza"] == "3F" or (c["faza"] is None and d["tri_posibil"]))
    tri_fortat = c["faza"] == "3F" and not d["tri_posibil"]
    if tri_fortat:
        j.presupune(f"{eticheta_receptor(c['receptor'])} declarat trifazat (3F) — valorile implicite monofazate se aplică pe fază "
                    f"(P implicit = 3 × {fmt_ro(d['P_mono'])} kW)", c["obiect"])
    P = c.get("P_kW")
    if P is None:
        P = 3 * d["P_mono"] if tri_fortat else (d["P_tri"] if tri and d["P_tri"] else d["P_mono"])
        j.presupune(f"{eticheta_receptor(c['receptor'])}: P = {fmt_ro(P)} kW", c["obiect"])
    L = c.get("L_m", (c.get("cablu") or {}).get("L"))
    if L is None:
        L = d["L"]
        j.presupune(f"{eticheta_receptor(c['receptor'])}: lungime circuit {fmt_ro(L, 0)} m", c["obiect"])
    S_min = (d["S_tri"] if tri and d["S_tri"] else d["S_mono"])
    In_min = (d["In_tri"] if tri and d["In_tri"] else d["In_mono"])
    if d["grupa"] == "VE":
        In_min = calibru_ve(float(P), tri)
        j.presupune(f"{eticheta_receptor(c['receptor'])}: calibrul din puterea stației — I încărcare = "
                    f"{fmt_ro(curent_ve(float(P), tri), 1)} A × 1,25 (sarcină continuă, DECIZIE) → C{In_min}", c["obiect"])
    cab = {"material": "Cu", "metoda": "B2"}
    cab.update({k: v for k, v in (c.get("cablu") or {}).items() if v is not None})
    cab["L"] = float(L)
    cab["S_min"] = S_min
    if c["receptor"] in norme.LOCUINTA_S_MIN_FIX_MM2:
        cab["S_min_fix"] = norme.LOCUINTA_S_MIN_FIX_MM2[c["receptor"]]
    sf = cab.get("S_fortat")
    if sf is not None:
        # v1.5 (m11): secțiunea impusă sub minimul receptorului — prize < 2,5 mm² BLOCANT (I7-2011, §B.8), altfel AV
        prize = c["receptor"].startswith("prize")
        if lt(float(sf), S_min):
            emite(j, "V13", BLOCANT if prize else AVERTISMENT, c["obiect"], "loc", S=sf, Smin=S_min, rec=eticheta_receptor(c["receptor"]),
                  sursa="I7-2011 / SPEC §B.8" if prize else "valoare uzuală §C.8")
    if d["grupa"] == "VE" and sf is None:
        # v1.7 (N17): VE dimensionat normal (Ib / In, Iz, ΔU, Ik) cu minimul 4 mm² Cu — nu o secțiune fixă de 6 mm²
        j.presupune(f"{eticheta_receptor(c['receptor'])}: secțiunea din Ib / In, Iz, ΔU și Ik, minimum "
                    f"{fmt_ro(S_min)} mm² Cu (sarcină continuă, §C.8 — DECIZIE); pentru o rezervă de putere (ex. 22 kW) "
                    f"declară secțiunea impusă", c["obiect"])
    r = {"rol": "final", "receptor": d["calcul"], "retea": "tri" if tri else "mono", "P_kW": float(P),
         "cosfi": c.get("cosfi") or d["cosfi"], "prot_tip": "MCB", "curba": c.get("curba") or d["curba"],
         "cablu": cab, "In_minim": In_min, "_validat": True,
         # v1.7 (N13): cosφ din tabelul receptorului e presupus (nu „declarat”), cu eticheta receptorului în ipoteze
         "_cosfi_eticheta": eticheta_receptor(c["receptor"]), "_cosfi_implicit": c.get("cosfi") is None}
    if sf is None:
        # v1.7 (m-c6): mărirea pentru ΔU a circuitului final plafonată (peste — V20 cu remedierea „mărește coloana”)
        r["S_max_dU"] = norme.LOCUINTA_S_MAX_CIRCUIT_DU_MM2
    if c["receptor"] == "tablou_secundar":
        # r6: alimentarea TD consumă cel mult 1,5 % ΔU — restul limitei rămâne circuitelor din tabloul secundar
        # r8 (P0 #46): bugetul e al RAMURII (relativ la ΔU de la origine), iar mărirea pentru ΔU e plafonată la 16 mm²
        # (peste — problema e coloana / poziția tabloului: V20/V21 cu remedierea „mărește coloana”), fără cabluri în paralel
        r["tinta_dU_ramura"] = 1.5
        r["S_max_dU"] = norme.LOCUINTA_S_MAX_CIRCUIT_DU_MM2
    if c.get("In_A") is not None:
        r["In_fortat"] = c["In_A"]
        r.pop("In_minim")
    if d["calcul"] == "motor":
        r["pornire"] = "directa"
    return r, d, tri


def _categorie(x):
    """Cheia grupei DDR a unui circuit (v1.5): fără DDR, VE, DDR impus (propriu), saună, iluminat, apoi grupa receptorului."""
    c, d = x["c"], x["d"]
    if c["DDR"] is False:
        return "fara"
    if d["grupa"] == "VE":
        return "VE"
    if isinstance(c["DDR"], dict):
        return "propriu"
    if d["grupa"] == "sauna":
        return "sauna"
    if c["receptor"] == "iluminat":
        return "iluminat"
    return d["grupa"]


def _imparte(mem, k):
    """Împarte lista în k bucăți consecutive cât mai egale."""
    k = max(1, min(k, len(mem)))
    n, r = divmod(len(mem), k)
    out, i = [], 0
    for q in range(k):
        m = n + (1 if q < r else 0)
        out.append(mem[i:i + m])
        i += m
    return [x for x in out if x]


def nivel_din_nume(nume):
    """v1.6 (P1-4): nivelul unui circuit de iluminat dedus din nume (subsol / parter / etajN / mansarda / exterior / pod)
    sau None."""
    from .scheme import _fara_diacritice
    n = _fara_diacritice(str(nume or "")).lower()
    for rx, cheie in NIVELURI:
        m = re.search(rx, n)
        if m:
            return cheie.format(m.group(2)) if "{}" in cheie else cheie
    return None


def _pondere(x, ks, ks_decl):
    """v1.6 (m-n3): curentul de CALCUL al unui circuit pe faza lui: ks·Ib (general) sau Ib (sarcină continuă);
    `ks` declarat → ks·Ib pentru toate."""
    return x["Ib"] if (x["d"]["continuu"] and not ks_decl) else ks * x["Ib"]


def _loturi(pe_cat):
    """Loturile de grupare (categorie, membri, limită pe DDR, minimum 2 grupe?) în ordinea ORDINE_GRUPE.
    v1.6 (P1-4): iluminatul — cel mult LOCUINTA_ILUMINAT_PE_DDR circuite pe DDR, câte un lot pe nivel (dedus din nume);
    la un singur lot cu ≥ 2 circuite, cel puțin 2 grupe (v1.5)."""
    LIM = norme.LOCUINTA_CIRCUITE_PE_DDR
    out = []
    for cat in ORDINE_GRUPE:
        mem = pe_cat.get(cat) or []
        if not mem:
            continue
        if cat != "iluminat":
            # v1.7 (N16): prizele (și celelalte receptoare ale categoriei) de pe niveluri diferite, deduse din nume, nu se
            # amestecă pe același DDR; circuitele fără nivel completează lotul cel mai mic (în ordinea intrării), deci
            # fără niveluri / cu un singur nivel comportamentul e cel din v1.6
            niv = {}
            for x in mem:
                n_ = nivel_din_nume(x["c"].get("nume"))
                if n_ is not None:
                    niv.setdefault(n_, []).append(x)
            if len(niv) < 2:
                out.append((cat, mem, LIM, False))
                continue
            loturi = list(niv.values())
            for x in mem:
                if nivel_din_nume(x["c"].get("nume")) is None:
                    min(loturi, key=len).append(x)
            for m in loturi:
                m.sort(key=lambda y: y["c"]["idx"])
                out.append((cat, m, LIM, False))
            continue
        niv = {}
        for x in mem:
            niv.setdefault(nivel_din_nume(x["c"].get("nume")), []).append(x)
        unic = len(niv) == 1
        for m in niv.values():
            out.append((cat, m, norme.LOCUINTA_ILUMINAT_PE_DDR, unic and len(m) >= 2))
    return out


def _grupeaza_si_repartizeaza(ramuri, retea, ks=1.0, ks_decl=False):
    """v1.5 / v1.6 (§C.8 pct. 4–5): grupele DDR și fazele circuitelor.

    * cel mult LOCUINTA_CIRCUITE_PE_DDR circuite pe un DDR (iluminat: 2, pe niveluri); iluminatul separat de prize;
      bucătărie / baie / exterior separate; saună, VE și circuitele cu DDR impus — câte o grupă proprie;
    * la trifazat: circuitele 3F ale unei categorii formează grupe 4P (completate cu monofazate), restul monofazatelor
      formează grupe pe O SINGURĂ fază (DDR 2P);
    * v1.6 (m-n3) — ordinea repartizării, pe curentul de CALCUL (ks·Ib general, Ib continuu): întâi circuitele 3F,
      apoi fazele impuse, apoi toate unitățile monofazate libere — grupele 2P întregi și monofazatele din grupele 4P /
      „fără DDR”, individual — descrescător după curentul de calcul, fiecare pe faza cu cel mai mic curent de calcul.
    Întoarce (grupe, sarc) — sarc = Ib instalat pe fază; setează x["faza"]."""
    pe_cat = {}
    for x in ramuri:
        pe_cat.setdefault(_categorie(x), []).append(x)
    grupe = []                          # {cheie, membri, faza (None = de repartizat), poli}
    for cat, mem, lim, kmin2 in _loturi(pe_cat):
        m3 = [x for x in mem if x["tri"]]
        m1 = [x for x in mem if not x["tri"]]
        g4 = []
        if m3:
            for ch in _imparte(m3, math.ceil(len(m3) / lim)):
                g4.append({"cheie": cat, "membri": list(ch), "faza": "3F", "poli": "4P"})
            for g in g4:
                while len(g["membri"]) < lim and m1:
                    g["membri"].append(m1.pop(0))
        grupe += g4
        if not m1:
            continue
        if retea == "mono":
            k = math.ceil(len(m1) / lim)
            if kmin2 and not m3:
                k = max(k, 2)
            grupe += [{"cheie": cat, "membri": ch, "faza": "L1", "poli": "2P"} for ch in _imparte(m1, k)]
            continue
        impuse = {}
        libere = []
        for x in m1:
            (impuse.setdefault(x["c"]["faza"], []) if x["c"]["faza"] in ("L1", "L2", "L3") else libere).append(x)
        for f in ("L1", "L2", "L3"):
            for ch in _imparte(impuse.get(f) or [], math.ceil(len(impuse.get(f) or []) / lim)):
                grupe.append({"cheie": cat, "membri": ch, "faza": f, "poli": "2P"})
        if libere:
            k = math.ceil(len(libere) / lim)
            if kmin2 and not impuse and not m3:
                k = max(k, 2)
            grupe += [{"cheie": cat, "membri": ch, "faza": None, "poli": "2P"} for ch in _imparte(libere, k)]
    for x in ramuri:                    # grupe proprii, în ordinea de la intrare
        cat = _categorie(x)
        if cat in ("VE", "propriu", "sauna"):
            grupe.append({"cheie": cat, "membri": [x], "faza": "3F" if x["tri"] else
                          ("L1" if retea == "mono" else x["c"]["faza"]), "poli": "4P" if x["tri"] else "2P"})
    fara = pe_cat.get("fara") or []
    if fara:
        grupe.append({"cheie": "fara", "membri": fara, "faza": None, "poli": None})

    # ---- fazele ----
    w = lambda x: _pondere(x, ks, ks_decl)  # noqa: E731

    def repartizeaza():
        """Repartizarea pe faze (greedy descrescător pe curentul de calcul, unitățile = grupele 2P întregi)."""
        sarc = {"L1": 0.0, "L2": 0.0, "L3": 0.0}
        calc = {"L1": 0.0, "L2": 0.0, "L3": 0.0}
        for x in ramuri:
            x.pop("faza", None)
        for g in grupe:
            if g.get("_libera"):
                g["faza"] = None

        def pune(x, f):
            x["faza"] = f
            for ff in (("L1", "L2", "L3") if f == "3F" else (f,)):
                sarc[ff] += x["Ib"]
                calc[ff] += w(x)

        for x in ramuri:
            if x["tri"]:
                pune(x, "3F")
            elif retea == "mono":
                pune(x, "L1")
            elif x["c"]["faza"] in sarc:
                pune(x, x["c"]["faza"])
        if retea == "tri":
            unitati = [(sum(w(x) for x in g["membri"]), n, g["membri"], g) for n, g in enumerate(grupe)
                       if g["cheie"] != "fara" and g["poli"] == "2P" and g["faza"] is None]
            n0 = len(unitati)
            in_grupe = {id(x) for u in unitati for x in u[2]}
            unitati += [(w(x), n0 + n, [x], None) for n, x in
                        enumerate(x for x in ramuri if "faza" not in x and id(x) not in in_grupe)]
            for _, _, mem, g in sorted(unitati, key=lambda u: (-u[0], u[1])):
                f = min(("L1", "L2", "L3"), key=lambda k: (calc[k], k))
                if g is not None:
                    g["faza"] = f
                for x in mem:
                    pune(x, f)
        for g in grupe:
            if g["cheie"] != "fara" and g["poli"] == "2P" and g["faza"] is None:
                g["faza"] = g["membri"][0]["faza"]
        return sarc

    for g in grupe:
        if g["cheie"] != "fara" and g["poli"] == "2P" and g["faza"] is None:
            g["_libera"] = True
    sarc = repartizeaza()
    # r6 (V47 38–60 %): o grupă DDR mare (ex. 5 circuite de prize pe L1) dezechilibrează fazele — se împarte cea mai
    # încărcată grupă liberă în două (un DDR în plus) până când dezechilibrul ≤ limită sau nu mai are ce împărți
    for _ in range(6):
        if retea != "tri":
            break
        imed = sum(sarc.values()) / 3.0
        if imed <= 0 or (max(sarc.values()) - imed) / imed * 100.0 <= norme.LOCUINTA_DEZECHILIBRU_MAX_PCT + 1e-9:
            break
        cand = [g for g in grupe if g.get("_libera") and len(g["membri"]) >= 2]
        if not cand:
            break
        g = max(cand, key=lambda g_: sum(x["Ib"] for x in g_["membri"]))
        mem = sorted(g["membri"], key=lambda x: -x["Ib"])
        a_, b_ = [], []
        for x in mem:
            (a_ if sum(y["Ib"] for y in a_) <= sum(y["Ib"] for y in b_) else b_).append(x)
        a_.sort(key=lambda y: y["c"]["idx"])
        b_.sort(key=lambda y: y["c"]["idx"])
        g["membri"] = a_
        grupe.insert(grupe.index(g) + 1, dict(g, membri=b_))
        sarc = repartizeaza()
    for g in grupe:
        g.pop("_libera", None)
    return grupe, sarc


def _curenti_faza(ramuri, retea, ks, ks_declarat):
    """v1.5 (C1): curentul de calcul pe fiecare fază = ks·Σ Ib general + Σ Ib continuu (ks declarat: ks·Σ Ib);
    circuitele 3F încarcă toate fazele. Întoarce (calc, continuu)."""
    calc = {"L1": 0.0, "L2": 0.0, "L3": 0.0}
    cont = {"L1": 0.0, "L2": 0.0, "L3": 0.0}
    for x in ramuri:
        fz = ("L1", "L2", "L3") if x["faza"] == "3F" else (x["faza"],)
        for f in fz:
            if ks_declarat:
                calc[f] += ks * x["Ib"]
            elif x["d"]["continuu"]:
                calc[f] += x["Ib"]
                cont[f] += x["Ib"]
            else:
                calc[f] += ks * x["Ib"]
        if ks_declarat and x["d"]["continuu"]:
            for f in fz:
                cont[f] += x["Ib"]
    if retea == "mono":
        calc = {"L1": calc["L1"], "L2": 0.0, "L3": 0.0}
        cont = {"L1": cont["L1"], "L2": 0.0, "L3": 0.0}
    return calc, cont


def _capacitate_conditionata(ik3):
    """Inc / Icc condiționat (RCCB / IS) din seria uzuală ≥ Ik3 la bara TE; (valoare, ok)."""
    v = prima_din_serie(norme.LOCUINTA_INC_KA, ik3)
    return (v, True) if v is not None else (norme.LOCUINTA_INC_KA[-1], False)


def _umanizeaza(j, n_v, n_i, circ):
    """v1.6 (UX 13): mesajele emise de locuință fără chei interne — cheia tehnică (ex. „P_kW”) e înlocuită cu denumirea
    românească, iar calea câmpului merge în cheia separată `camp` („alimentare.In_Q_bransament_A”, „circuite[2].P_kW”,
    index de la 0, ca în lista de intrare). Se înlocuiesc doar tokenii care sunt chei: cu „_” / cale cu „.”, sau
    cuvintele simple doar în contextul „câmpul „X”” / „X = …”."""
    idx = {c["obiect"]: c["idx"] - 1 for c in circ or []}
    chei = sorted(ETICHETE, key=len, reverse=True)
    pref = r"(?:alimentare\.cablu\.|alimentare\.|DDR\.|cablu\.)?"

    def regexuri(k):
        # 1) forma cu prefix („alimentare.zona”, „DDR.In_A”); 2) forma simplă: cheile cu „_” oriunde, cuvintele simple
        # doar în contextul „câmpul „X””, „câmpului X”, „X = …”
        yield r"(?<![\w.])(" + pref.replace(")?", ")") + re.escape(k) + r")(?![\w])"
        if "_" in k:
            yield r"(?<![\w.])(" + re.escape(k) + r")(?![\w])"
        else:
            yield (r"(?<=câmpul „)(" + re.escape(k) + r")(?=”)|(?<=câmpului )(" + re.escape(k) + r")(?![\w.])|"
                   r"(?<![\w.])(" + re.escape(k) + r")(?= = )")

    def inlocuieste(txt, gasite):
        # v1.7 (P2 verificator): etichetele puse deja se țin în substituenți, ca să nu fie înlocuite a doua oară
        # („zona (urban / rural) (urban / rural)”)
        puse = []
        for rx, k in [(rx, k) for faza in (0, 1) for k in chei for i, rx in enumerate(regexuri(k)) if i == faza]:

            def rep(m):
                tok = next(g for g in m.groups() if g)
                gasite.append(tok)
                suf = (" (cablul coloanei)" if tok.startswith("alimentare.cablu.") else " (DDR impus)"
                       if tok.startswith("DDR.") else " (cablu)" if tok.startswith("cablu.") else "")
                puse.append(ETICHETE[k] + suf)
                return f"\x01{len(puse) - 1}\x02"
            txt = re.sub(rx, rep, txt)
        return re.sub("\x01(\\d+)\x02", lambda m: puse[int(m.group(1))], txt)

    for v in j.verificari[n_v:] + j.info[n_i:]:
        gasite = []
        v["mesaj"] = inlocuieste(v.get("mesaj") or "", gasite)
        if v.get("remediere"):
            v["remediere"] = inlocuieste(v["remediere"], [])
        if not gasite and v.get("obiect") in idx and v["cod"] in CAMP_DUPA_COD:
            gasite = [CAMP_DUPA_COD[v["cod"]]]
        if gasite and "camp" not in v:
            tok, ob = gasite[0], v.get("obiect")
            if tok.startswith("alimentare"):
                v["camp"] = tok
            elif ob in ("alimentare", "C2"):
                v["camp"] = f"alimentare.{tok}"
            elif ob in idx:
                v["camp"] = f"circuite[{idx[ob]}].{tok}"
            else:
                v["camp"] = tok


def _tablouri_secundare(inp, retea, j):
    """r6 (N08, N50): `tablouri_secundare` = [{nume, L_m, faza?, circuite: [{nume, P_kW | In_A, receptor?, pornire?,
    retea?, L_m?}]}] — fiecare devine un circuit de alimentare din TE (receptor „tablou_secundar”, P = ks·Σ P) plus
    tabloul secundar dimensionat ca tablou (circuitele lui, cu DDR 30 mA pe prize). Întoarce (inp, {idx: td})."""
    tds = inp.get("tablouri_secundare")
    if not tds:
        return inp, {}
    from .scheme import expandeaza_plecari
    inp = dict(inp)
    circ = list(inp.get("circuite") or [])
    td_map = {}
    if not isinstance(tds, list):
        emite(j, "V07", BLOCANT, "tablouri_secundare", "param", camp="tablouri_secundare", x=repr(tds)[:60],
              conditie="listă de tablouri {nume, L_m, circuite}")
        return inp, {}
    for k, td in enumerate(tds, 1):
        nume = (td or {}).get("nume") or f"TD{k}"
        cc = (td or {}).get("circuite") or []
        if not isinstance(td, dict) or not isinstance(cc, list) or not cc or not all(isinstance(c, dict) for c in cc):
            emite(j, "V07", BLOCANT, f"TD·{nume}", "param", camp="tablouri_secundare.circuite", x=repr(cc)[:60],
                  conditie="cel puțin un circuit {nume, P_kW}")
            continue
        # r8b: `n_circuite` multiplică circuitul („prize 4 circ” = 4 circuite) și în bilanțul TD-ului, nu doar pe desen
        cc = expandeaza_plecari(cc)
        casnic = [_receptor_casnic_td(c) for c in cc]
        cc = [_p_implicit_td(c, nume, j) for c in cc]
        td = dict(td, circuite=cc)
        try:
            pn = [_p_bilant_td(c, rc, retea) for c, rc in zip(cc, casnic)]
            pis = [x[0] for x in pn]
        except (TypeError, ValueError):
            emite(j, "V07", BLOCANT, f"TD·{nume}", "param", camp="tablouri_secundare.circuite.P_kW", x=repr(cc)[:60],
                  conditie="P_kW / In_A numerice")
            continue
        note = {}
        for c, (pi, p_in) in zip(cc, pn):
            if p_in is not None:
                note.setdefault((float(c["In_A"]), pi, p_in), []).append(c.get("nume") or "circuit")
        for (in_a, pi, p_in), nn in note.items():
            j.presupune(f"tablou secundar {nume}: {', '.join('„' + x + '”' for x in nn)} dat{'e' if len(nn) > 1 else ''} "
                        f"prin calibru {fmt_ro(in_a)} A → {fmt_ro(pi)} kW în bilanț (puterea implicită a receptorului, "
                        f"nu U·In·cosφ = {fmt_ro(p_in)} kW — DECIZIE) — declarați P_kW dacă sarcina e alta")
        if td.get("ks"):
            ks = td["ks"]
            p = ks * sum(pis)
        elif all(casnic):
            # r8b DECIZIE: tabloul secundar cu receptoare casnice (etaj, mansardă) — simultaneitatea locuinței, ca la
            # circuitele TE (norme.LOCUINTA_KS_GENERAL după numărul receptoarelor generale; continue cu ks = 1), nu
            # ks-ul de tablou de distribuție IEC 61439-2 (0,7 la 7 circuite)
            gen = [pi for pi, rc in zip(pis, casnic) if not norme.LOCUINTA_RECEPTORI[rc][14]]
            cont = sum(pi for pi, rc in zip(pis, casnic) if norme.LOCUINTA_RECEPTORI[rc][14])
            ks = next(k for n_, k in norme.LOCUINTA_KS_GENERAL if len(gen) <= n_) if gen else 1.0
            p = ks * sum(gen) + cont
        else:
            ks = norme.ks_implicit(len(cc))
            p = ks * sum(pis)
        tri_c = any(c.get("retea") == "tri" or (c.get("pornire") is not None and c.get("retea") != "mono") for c in cc)
        faza = td.get("faza")
        if faza is None and retea == "tri" and (tri_c or p > 3.68):
            faza = "3F"
        f = {"nume": nume, "receptor": "tablou_secundar", "P_kW": round(max(p, 0.1), 3)}
        if faza is not None:
            f["faza"] = faza
        if td.get("L_m") is not None:
            f["L_m"] = td["L_m"]
        if td.get("cablu") is not None:
            f["cablu"] = td["cablu"]
        # TN: alimentarea TD protejată prin MCB (deconectare la Ik1), DDR 30 mA în TD; TT: DDR 300 mA S pe alimentare
        f["DDR"] = ({"IdN_mA": 300, "selectiv": True, "tip": "A"} if inp.get("schema_pamant") == "TT" else False)
        circ.append(f)
        td_map[len(circ)] = dict(td, nume=nume, ks=ks)
        j.pas(f"Tablou secundar {nume}: {len(cc)} circuite, Σ Pi = {fmt_ro(sum(pis))} kW, ks = {fmt_ro(ks)} → P "
              f"alimentare = {fmt_ro(p)} kW ({'3F' if faza == '3F' else 'monofazat'})")
    inp["circuite"] = circ
    return inp, td_map


def _receptor_casnic_td(c):
    """r8b: cheia receptorului casnic (norme.LOCUINTA_RECEPTORI) a unui circuit de tablou secundar, sau None (forță,
    motor, receptor de atelier) — din `receptor` sau, în lipsă, din nume (iluminat / prize)."""
    if not isinstance(c, dict):
        return None
    rec = c.get("receptor")
    if rec in norme.LOCUINTA_RECEPTORI and rec != "tablou_secundar":
        return rec
    if rec is None:
        from .scheme import receptor_dupa_nume
        r2 = receptor_dupa_nume(c.get("nume", ""), 1)
        return r2 if r2 in ("iluminat", "prize") else None
    return rec if rec in ("iluminat", "prize") else None


def _retea_circuit_td(c, ret):
    """Rețeaua unui circuit din tabloul secundar: dată, sau (TD trifazat) monofazat pentru iluminat / prize / receptoare
    mici și trifazat pentru motoare și receptoare mari."""
    if c.get("retea") is not None or ret != "tri":
        return c.get("retea") or ret
    from .scheme import receptor_dupa_nume
    rec = c.get("receptor") or receptor_dupa_nume(c.get("nume", ""), 1)
    mic = (c.get("P_kW") is not None and float(c["P_kW"]) <= 2.0) or (c.get("In_A") or 99) <= 16
    return "mono" if rec in ("iluminat", "prize") or (mic and rec != "motor") else "tri"


def _p_bilant_td(c, rec_casnic, ret):
    """r8b: puterea unui circuit al tabloului secundar în bilanțul TD-ului. P_kW dat → P_kW. Dat doar prin calibru
    (In_A): receptor casnic → puterea implicită a receptorului (ca la circuitele TE), plafonată la U·In·cosφ — DECIZIE:
    calibrul unui circuit de prize C16 nu e sarcina lui (3,7 kW încărcat continuu ar umfla TD-ul peste P aprobată);
    receptor de forță / motor → U·In·cosφ (conservator, ca înainte). Rețeaua: a circuitului (iluminat / prize mono).
    Întoarce (P bilanț, U·In·cosφ dacă P a fost redusă — pentru nota de ipoteze — altfel None)."""
    from .scheme import _pi
    cr = dict(c, retea=_retea_circuit_td(c, "tri" if ret == "tri" else "mono"))
    p_in = _pi(cr, 1)
    if c.get("P_kW") is not None or c.get("In_A") is None or rec_casnic is None:
        return p_in, None
    p_imp = float(norme.LOCUINTA_RECEPTORI[rec_casnic][0])
    if cr["retea"] == "tri" and norme.LOCUINTA_RECEPTORI[rec_casnic][1]:
        p_imp = float(norme.LOCUINTA_RECEPTORI[rec_casnic][1])
    return (p_imp, p_in) if p_imp < p_in else (p_in, None)


TD_S_MAX_ILUMINAT_MM2 = 50.0      # r8: plafonul alimentării unui TD cu iluminat (un singur cablu, fără paralel)
TD_P_IMPLICIT_KW = {"iluminat": 1.0, "prize": 2.0, "motor": 2.2, "forta": 2.0}


def _p_implicit_td(c, td_nume, j):
    """r7 (#21, #64): circuit al unui tablou secundar dat doar prin nume — receptorul dedus din nume (iluminat / prize /
    motor / forță) sau din tabelul receptoarelor locuinței, cu puterea implicită PRESUPUSĂ (declarată), nu V07."""
    if not isinstance(c, dict) or c.get("P_kW") is not None or c.get("In_A") is not None:
        return c
    from .scheme import receptor_dupa_nume
    rec = c.get("receptor")
    d = norme.LOCUINTA_RECEPTORI.get(rec) if rec else None
    if d is not None:
        p, rec2 = float(d[0]), d[9] if len(d) > 9 else None
    else:
        rec2 = rec if rec in TD_P_IMPLICIT_KW else receptor_dupa_nume(c.get("nume", ""), 1)
        p = TD_P_IMPLICIT_KW.get(rec2, 2.0)
    out = dict(c, P_kW=p)
    if rec2 in ("iluminat", "prize", "motor", "forta"):
        out["receptor"] = rec2
    elif "receptor" in out and out["receptor"] not in ("iluminat", "prize", "motor", "forta", "tablou"):
        out.pop("receptor")
    if out.get("receptor") == "prize":
        out.setdefault("In_minim", 16)
    j.presupune(f"tablou secundar {td_nume}: „{c.get('nume') or 'circuit'}” fără putere → {fmt_ro(p)} kW "
                f"({out.get('receptor') or 'forță'}, valoare implicită) — de declarat")
    return out


def _circuite_td(td, ret, tt=False):
    """Circuitele tabloului secundar pregătite pentru calcul: rețeaua fiecăruia, DDR 30 mA tip A (v1.5 M1: în locuință
    toate circuitele finale au DDR ≤ 30 mA — și cele din tabloul secundar, r8 #46) și plafonul de 16 mm² al măririi
    pentru ΔU (r8: nu 4 × 3×240 mm² pentru un circuit de iluminat)."""
    from .scheme import expandeaza_plecari
    pl = []
    for c in expandeaza_plecari(td.get("circuite") or []):
        c = dict(c)
        if ret == "tri" and c.get("retea") is None:
            # monofazate implicit: iluminat / prize / receptoare mici; motoarele și receptoarele mari — trifazate
            c["retea"] = _retea_circuit_td(c, ret)
        if c.get("DDR") is None and c.get("ddr") is None:
            c["DDR"] = {"IdN_mA": 30, "tip": "A", "_motor": True}
        if (c.get("cablu") or {}).get("S_fortat") is None:
            c["S_max_dU"] = norme.LOCUINTA_S_MAX_CIRCUIT_DU_MM2
        pl.append(c)
    return pl


def _in_max_td(td, ret, j):
    """Calibrul cel mai mare al circuitelor din tabloul secundar (selectivitatea alimentării TD față de ele)."""
    from .scheme import _ip_preliminar, _pregateste_plecari
    pl = _circuite_td(td, ret)
    jt = Jurnal()
    if not _pregateste_plecari(pl, ret, jt, "tmp."):
        return None
    ips = [x for x in (_ip_preliminar(c, 0, jt, final=True) for c in pl) if x is not None]
    return max(ips) if ips else None


def _calculeaza_td(td, x, rr, j):
    """Circuitele tabloului secundar, dimensionate ca plecări finale de tablou (Cu, metoda C) din bara TD."""
    from .scheme import _plecari, _pregateste_plecari
    ret = "tri" if x["tri"] else "mono"
    pl = _circuite_td(td, ret)
    ob = x["c"]["obiect"]
    if not _pregateste_plecari(pl, ret, j, f"{ob}."):
        return {"nume": td["nume"], "plecari": []}
    lista = _plecari(pl, rr["ctx_aval"], rr["prot"], j, prefix=f"{ob}.", final=True)
    return {"nume": td["nume"], "retea": ret, "ks": td.get("ks"), "plecari": lista}


RECEPTORI_UNICI = ("sauna", "plita", "cuptor", "boiler", "pompa_caldura", "vehicul_electric", "centrala_termica",
                   "masina_spalat_rufe", "masina_spalat_vase", "uscator")


def _comaseaza_duplicate(inp, j):
    """r9 (locuințe #8): același receptor dedicat declarat de două ori cu același nume și date COMPLEMENTARE (ex.
    „Saună 9 kW 3F” + „Saună la 25 m”) = un singur circuit — nu se desenează de două ori. Date contradictorii (P / L
    diferite) → rămân două circuite."""
    circ = inp.get("circuite")
    if not isinstance(circ, list):
        return
    out = []
    for c in circ:
        if not isinstance(c, dict):
            out.append(c)
            continue
        cheie = (c.get("receptor"), _fara_diac(str(c.get("nume") or "")).strip().lower())
        tinta = next((o for o in out if isinstance(o, dict) and c.get("receptor") in RECEPTORI_UNICI
                      and (o.get("receptor"), _fara_diac(str(o.get("nume") or "")).strip().lower()) == cheie
                      and not o.get("n") and not c.get("n")
                      and all(o.get(k) == v for k, v in c.items() if k in o and k not in ("nume",))), None)
        if tinta is None:
            out.append(c)
            continue
        tinta.update({k: v for k, v in c.items() if k not in tinta})
        j.presupune(f"„{c.get('nume')}” declarat de două ori cu date complementare — un singur circuit "
                    f"(datele combinate)")
    inp["circuite"] = out


def _fara_diac(s):
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn")


def calculeaza_locuinta(inp, j):
    """SPEC §C.8: bilanț, branșament + coloană C2, Q general, SPD T2, grupe DDR, circuite și repartizarea pe faze."""
    n_v, n_i, n_p = len(j.verificari), len(j.info), len(j._presupus)
    cutie = {}
    try:
        _comaseaza_duplicate(inp, j)
        from .scheme import tensiune_jt_nesuportata
        if tensiune_jt_nesuportata(inp, j):
            return {}
        rez = _calculeaza(inp, j, cutie)
        if isinstance(inp.get("ge_rezerva"), dict) and rez.get("retea"):
            _ge_rezerva(inp["ge_rezerva"], rez, j)
        return rez
    finally:
        _umanizeaza(j, n_v, n_i, cutie.get("circ"))
        # v1.7 (m-c5 / UX C3): nicio cheie de receptor în mesaje, remedieri și presupuneri
        for v in j.verificari[n_v:] + j.info[n_i:]:
            v["mesaj"] = fara_chei_receptor(v.get("mesaj") or "")
            if v.get("remediere"):
                v["remediere"] = fara_chei_receptor(v["remediere"])
            if v["cod"] == "V34":
                # locuința nu are câmpul „IΔn amonte”: DDR-ul 300 mA din branșament e al blocului OD
                v["remediere"] = ("priză de pământ mai bună (RA mai mic, măsurat), astfel încât RA·IΔn ≤ 50 V cu IΔn al "
                                  "DDR-ului din branșament (300 mA → RA ≤ 166 Ω) și al grupelor (30 mA)")
        j._presupus[n_p:] = [(fara_chei_receptor(t), el) for t, el in j._presupus[n_p:]]
        for v in j.verificari[n_v:]:
            # Q presupus: câmpul de completat (m-n5 / N5)
            if v["cod"] == "V46" and "presupus" in v.get("mesaj", "") and "camp" not in v:
                v["camp"] = "alimentare.In_Q_bransament_A" if "Q " in v["mesaj"] else "alimentare.P_aprobata_kW"


COMUTATOR_IN_A = (25, 32, 40, 63, 80, 100, 125, 160, 200, 250)


def _ge_rezerva(g, rez, j):
    """r7 (#54): grup electrogen de REZERVĂ la locuință (`ge_rezerva: {Sn_kVA, comutare: "manual" | "ATS"}`) — sursă,
    nu consumator: Q-GE (protecția cablului GE), comutator de sursă I (rețea) – 0 – II (GE) cu interblocaj, care comută
    și N (2P / 4P), montat după Q general, înaintea barei TE. Suport minim: nu se verifică regimul GE (Ik1 GE)."""
    sn = g.get("Sn_kVA")
    com = str(g.get("comutare") or "manual").strip().lower()
    com = {"manual": "manual", "inversor": "manual", "inversor_manual": "manual", "ats": "ATS", "automat": "ATS"}.get(com)
    if not isinstance(sn, (int, float)) or isinstance(sn, bool) or sn <= 0 or com is None:
        j.emite("V07", BLOCANT, "GE rezervă", f"ge_rezerva invalid: Sn_kVA {sn!r}, comutare {g.get('comutare')!r}",
                "Sn_kVA > 0 și comutare „manual” (inversor de sursă) sau „ATS”")
        return
    mono = rez["retea"] == "mono"
    u = norme.U_0_V if mono else SQRT3 * norme.U_N_V
    in_g = float(sn) * 1000.0 / u
    q_ge = prima_din_serie(norme.MCB_IN_A, in_g * 0.999) or round(in_g)
    in_q = float(((rez.get("Q_general") or {}).get("In_A")) or in_g)
    in_c = prima_din_serie(COMUTATOR_IN_A, max(in_q, q_ge)) or max(in_q, q_ge)
    poli = "2P" if mono else "4P"
    rez["ge_rezerva"] = {"Sn_kVA": float(sn), "In_G_A": in_g, "comutare": com, "Q_GE_In_A": q_ge,
                         "comutator_In_A": in_c, "poli": poli}
    j.pas(f"GE de rezervă {fmt_ro(sn)} kVA: In_G = {fmt_ro(in_g)} A → Q-GE C{q_ge} A; comutator de sursă "
          f"{'manual I-0-II' if com == 'manual' else 'automat (ATS)'} {poli} {in_c} A (≥ Q general {fmt_ro(in_q, 0)} A), "
          f"comută și N, interblocaj (rețea și GE niciodată în paralel)")
    j.presupune("GE de rezervă: comutatorul de sursă după Q general, înaintea barei TE; neutrul GE comutat (comutator "
                f"{poli}); regimul GE (Ik1 la bornele GE, deconectarea) se verifică cu fișa GE — nemodelat")
    pc = float((rez.get("bilant") or {}).get("Pc_kW") or 0)
    if pc and gt(pc, 0.8 * float(sn)):
        j.emite("V86", AVERTISMENT, "GE rezervă", f"GE {fmt_ro(sn)} kVA < sarcina de calcul a casei Pc = {fmt_ro(pc)} kW "
                f"— în regim GE se alimentează numai consumatorii selectați (sau GE mai mare)",
                "declarați consumatorii alimentați pe GE (tablou rezervat) sau Sn GE ≥ Pc/0,8")


def _verifica_ve_amonte(j, g, tip_av, am_nume, am_idn, am_tip, tt, declarat):
    """v1.7 (M-c3, DECIZIE §C.8 pct. 4): circuitul VE (DDR tip B, sau A / F cu RDC-DD 6 mA în stație) în aval de DDR-ul
    300 mA al branșamentului. Un curent de defect c.c. neted trece și prin DDR-ul din amonte și îl poate „orbi” (SR HD
    60364-5-53:2015 art. 531.3.2, IEC 60364-7-722:2018 art. 722.531.3.101):
    * amonte tip B → în regulă;
    * amonte tip A / F și DDR VE tip A / F (stația limitează c.c. la 6 mA prin RDC-DD; tip A / F e garantat până la
      6 mA c.c., SR EN 61008-1 / IEC 62423) → în regulă;
    * altfel (amonte AC; sau amonte A / F cu DDR VE tip B, fără limitarea c.c.) → V43 „ve_dc” AVERTISMENT la TN-C-S;
      **BLOCANT la TT** — acolo DDR-ul 300 mA e protecția la defect (RA·IΔn ≤ 50 V) a coloanei C2 și a intrării TE."""
    if am_tip == "B" or (am_tip in ("A", "F") and tip_av in ("A", "F")):
        return
    if not declarat:
        j.presupune(f"DDR-ul din branșament ({am_nume} {am_idn} mA) tip {am_tip} (ST 3-JT / ST 4-JT) — declară tipul "
                    f"real al DDR-ului din branșament dacă e altul")
    det = (" — în TT acest DDR e protecția la defect (RA·IΔn ≤ 50 V) a coloanei C2 și a intrării TE, care s-ar pierde"
           if tt else "")
    rem = ("DDR-ul din amonte de tip B (sau F-B / B+, pentru c.c. neted) — dacă e deja de tip B, declară tipul DDR-ului "
           "din branșament; sau alimentarea stației VE dintr-un circuit fără DDR tip AC / A în amonte, conform "
           "producătorului; sau stație cu RDC-DD 6 mA c.c. și DDR VE tip A, cu DDR-ul din amonte cel puțin tip A")
    emite(j, "V43", BLOCANT if tt else AVERTISMENT, f"{g['obiect']} vs {am_nume}", "ve_dc", av=g["obiect"],
          tip_av=tip_av, am=am_nume, IdN_am=am_idn, tip_am=am_tip, detaliu=det, rem=rem)
    j.verificari[-1]["camp"] = "alimentare.DDR_bransament_tip"


def fara_chei_receptor(txt):
    """v1.7 (m-c5): înlocuiește cheile interne ale receptorilor („prize_bucatarie”, „vehicul_electric”, „plita” între
    ghilimele) cu denumirea românească (ETICHETE_RECEPTOR)."""
    for k in sorted(ETICHETE_RECEPTOR, key=len, reverse=True):
        if k not in txt:
            continue
        txt = txt.replace(f"„{k}”", f"„{ETICHETE_RECEPTOR[k]}”")
        if "_" in k:
            txt = re.sub(r"(?<![\w.])" + re.escape(k) + r"(?![\w])", ETICHETE_RECEPTOR[k], txt)
    return txt


def _agrega_v43(j, lst):
    """v1.6 (P2-1): verificările V43 ale grupelor față de DDR-ul branșamentului, agregate — o singură atenționare pentru
    toate grupele cu același mesaj („… DDR1–DDR4”), în loc de una pe grupă."""
    pe_msg = {}
    for ob_g, v in lst:
        cheie = (v["cod"], v["nivel"], v["mesaj"].replace(ob_g, "\x00"), v.get("remediere", "").replace(ob_g, "\x00"))
        pe_msg.setdefault(cheie, []).append((ob_g, v))
    for (cod, nivel, msg, rem), el in pe_msg.items():
        nume = [o for o, _ in el]
        nr = [int(o[3:]) for o in nume if o.startswith("DDR") and o[3:].isdigit()]
        if len(nume) > 1 and len(nr) == len(nume) and nr == list(range(nr[0], nr[0] + len(nr))):
            et = f"{nume[0]}–{nume[-1]}"
        else:
            et = ", ".join(nume)
        ob = el[0][1]["obiect"].replace(nume[0], et)
        if nivel == "INFO":
            j.info.append({"cod": cod, "nivel": nivel, "obiect": ob, "mesaj": msg.replace("\x00", et)})
        else:
            j.verificari.append({"cod": cod, "nivel": nivel, "obiect": ob, "mesaj": msg.replace("\x00", et),
                                 "remediere": rem.replace("\x00", et)})


def _calculeaza(inp, j, cutie):
    from .scheme import _bransament, _tt_ra, RETELE, _fd
    rez = {}
    retea = inp.get("retea")
    retea = RETELE.get(_fd(retea)) if isinstance(retea, str) else None
    if retea not in ("mono", "tri"):
        # rețeaua nu se presupune: monofazat / trifazat schimbă tot tabloul (BMPM / BMPT, Q, DDR 2P / 4P, faze)
        gol = inp.get("retea") is None or (isinstance(inp.get("retea"), str) and not inp["retea"].strip())
        j.emite("V07", "BLOCANT", "retea", "rețeaua locuinței nu este specificată" if gol
                else f"rețea invalidă: {inp.get('retea')!r}",
                "alege monofazat 230 V (BMPM) sau trifazat 3 × 400 V (BMPT), conform ATR / branșamentului existent")
        return rez
    rez["retea"] = retea
    inp, td_map = _tablouri_secundare(inp, retea, j)
    v = _valideaza(inp, j, retea)
    if v is None:
        return rez
    al, circ = v
    cutie["circ"] = circ
    U = SQRT3 * norme.U_N_V if retea == "tri" else norme.U_0_V
    tt = inp.get("schema_pamant") == "TT"

    # ---- circuitele: intrări B.1 și Ib -----------------------------------------------------------------------
    ramuri = []
    for c in circ:
        r, d, tri = _circuit(c, retea, j)
        if c["receptor"] == "tablou_secundar" and c.get("idx") in td_map:
            # r8 (#46): alimentarea TD cu calibru peste cel mai mare circuit din TD (amonte ≠ aval, selectivitate)
            in_td = _in_max_td(td_map[c["idx"]], "tri" if tri else "mono", j)
            if in_td and r.get("In_fortat") is None:
                r["Ip_min_extra"] = in_td + 0.01
            if any(x.get("receptor") == "iluminat" or (x.get("receptor") is None and "ilumin" in
                                                      str(x.get("nume") or "").lower())
                   for x in td_map[c["idx"]].get("circuite") or []) and "S_max_dU" in r:
                # TD cu iluminat (limita 3 %): alimentarea lasă ≥ 0,5 % circuitului de iluminat — mărire până la 50 mm²
                # (un singur cablu), nu cabluri în paralel
                r["tinta_dU"] = norme.DU_MAX_PCT[("retea_publica", "iluminat")] - 0.5
                r.pop("tinta_dU_ramura", None)
                r["S_max_dU"] = TD_S_MAX_ILUMINAT_MM2
        u = SQRT3 * norme.U_N_V if tri else norme.U_0_V
        ramuri.append({"c": c, "r": r, "d": d, "tri": tri, "Ib": r["P_kW"] * 1000.0 / (u * r["cosfi"])})

    # ---- 1. bilanț ---------------------------------------------------------------------------------------------
    pi = sum(x["r"]["P_kW"] for x in ramuri)
    p_cont = sum(x["r"]["P_kW"] for x in ramuri if x["d"]["continuu"])
    p_gen = pi - p_cont
    ks_decl = inp.get("ks") is not None
    if ks_decl:
        ks, regula = float(inp["ks"]), "declarat"
        pc = ks * pi
    else:
        n_gen = sum(1 for x in ramuri if not x["d"]["continuu"])
        # v1.7 (P2 verificator): fără receptoare generale ks nu se aplică (= 1), iar presupunerea nu mai spune
        # „ks după 0 receptoare … 0,8”
        ks = next(k for n, k in norme.LOCUINTA_KS_GENERAL if n_gen <= n) if n_gen else 1.0
        regula = (f"ks {fmt_ro(ks)} pe cele {n_gen} receptoare generale (regulă proprie §C.8 după numărul "
                  f"receptoarelor — DECIZIE proiectant), 1 pe sarcinile continue (VE, pompă de căldură, încălzire "
                  f"electrică, saună)") if n_gen else "toate receptoarele sunt sarcini continue — ks = 1"
        pc = ks * p_gen + p_cont
        if n_gen:
            j.presupune(f"bilanț locuință: Pc = {fmt_ro(ks)}·Σ P generale + Σ P sarcini continue (ks după "
                        f"{n_gen} {'receptor general' if n_gen == 1 else 'receptoare generale'}, DECIZIE proiectant — "
                        f"declarați coeficientul de simultaneitate ks = Pa/Pi dacă diferă)")
        else:
            j.presupune("bilanț locuință: numai sarcini continue (VE, pompă de căldură, încălzire electrică, saună) → "
                        "Pc = Σ P, fără simultaneitate (ks = 1)")
    j.ipoteza("ks", ks, not ks_decl)
    ib_pc = pc * 1000.0 / (U * norme.LOCUINTA_COSFI)
    pa = al.get("P_aprobata_kW")
    ib_pa = pa * 1000.0 / (U * norme.LOCUINTA_COSFI) if pa is not None else None
    ib = ib_pa if ib_pa is not None else ib_pc        # P0-1: cu P aprobată, Ib general = sarcina contractată
    rez["bilant"] = {"Pi_kW": pi, "P_general_kW": p_gen, "P_continuu_kW": p_cont, "ks": ks, "ks_regula": regula,
                     "Pc_kW": pc, "cosfi": norme.LOCUINTA_COSFI, "Ib_A": ib, "Ib_Pc_A": ib_pc,
                     "Ib_baza": "P aprobată (ATR)" if pa is not None else "Pc din bilanț",
                     "P_aprobata_kW": pa, "n_circuite": len(ramuri)}
    uf = '√3·400' if retea == 'tri' else '230'
    j.pas(f"Bilanț locuință: Σ Pi = {fmt_ro(pi)} kW (general {fmt_ro(p_gen)} kW, continuu {fmt_ro(p_cont)} kW); "
          f"Pc = {fmt_ro(pc)} kW ({regula}); Ib(Pc) = {fmt_ro(pc)}·1000/({uf}·{fmt_ro(norme.LOCUINTA_COSFI)}) = "
          f"{fmt_ro(ib_pc)} A" + (f"; Ib general din P aprobată = {fmt_ro(pa)}·1000/({uf}·"
                                  f"{fmt_ro(norme.LOCUINTA_COSFI)}) = {fmt_ro(ib_pa)} A (Pc informativ)"
                                  if pa is not None else ""))
    if pa is not None and lt(pa, pc) and al["tip"] == "bransament_nou":
        # r5 (L04): branșament nou — Pc din bilanț peste puterea cerută: întrebare, nu „Ib se ia din puterea aprobată”
        emite(j, "V46", AVERTISMENT, "schema", "pc_nou", Pc=pc, P=pa,
              rem="puterea cerută în ATR ≥ Pc (sau ks = Pa/Pi justificat / gestionarea dinamică a sarcinii la VE)")
    elif pa is not None and lt(pa, pc):
        emite(j, "V46", AVERTISMENT, "schema", "pc", Pc=pc, P=pa,
              rem="solicită ATR pentru mărirea puterii aprobate" + (" sau trecerea pe branșament trifazat"
                                                                     if retea == "mono" else "") +
              ", ori declară ks = Pa/Pi (simultaneitate justificată) / gestionarea dinamică a sarcinii (DLM la VE)")

    # ---- 1b. r7 (#19, P0): un receptor singur peste puterea aprobată / peste ce poate da rețeaua → BLOCANT clar ----------
    for x in ramuri:
        p_r = float(x["r"]["P_kW"])
        ob = x["c"].get("obiect") or x["c"].get("nume") or "circuit"
        rec = x["c"].get("receptor") or ""
        if retea == "mono" and rec == "vehicul_electric" and gt(p_r, norme.LOCUINTA_VE_MONO_MAX_KW):
            j.emite("V46", BLOCANT, ob,
                    f"încărcătorul VE de {fmt_ro(p_r)} kW nu se poate alimenta monofazat (max. "
                    f"{fmt_ro(norme.LOCUINTA_VE_MONO_MAX_KW)} kW = 32 A la 230 V) — un wallbox de 11 / 22 kW e trifazat",
                    "Treceți pe branșament trifazat (ATR pentru puterea necesară) sau alegeți un încărcător monofazat "
                    f"de max. {fmt_ro(norme.LOCUINTA_VE_MONO_MAX_KW)} kW?")
            j.verificari[-1]["intrebare"] = True
        if pa is not None and gt(p_r, pa) and x["c"].get("P_kW") is not None and "priz" not in rec and "ilumin" not in rec:
            j.emite("V46", BLOCANT, ob,
                    f"receptorul „{x['c'].get('nume') or rec}” de {fmt_ro(p_r)} kW depășește singur puterea aprobată "
                    f"{fmt_ro(pa)} kW (ATR) — branșamentul nu îl poate alimenta",
                    "Solicitați ATR pentru mărirea puterii (eventual trifazat), reduceți puterea receptorului sau "
                    "declarați gestionarea sarcinii (DLM)?")
            j.verificari[-1]["intrebare"] = True

    # ---- 2. grupele DDR și repartizarea pe faze (pe curentul de calcul, v1.6 m-n3) ------------------------------
    grupe, sarc = _grupeaza_si_repartizeaza(ramuri, retea, ks, ks_decl)
    calc, cont = _curenti_faza(ramuri, retea, ks, ks_decl)
    faze_act = ("L1", "L2", "L3") if retea == "tri" else ("L1",)
    f_max = max(faze_act, key=lambda f: (calc[f], -faze_act.index(f)))
    i_calc_max = calc[f_max]
    rez["faze"] = {"L1_A": sarc["L1"], "L2_A": sarc["L2"] if retea == "tri" else 0.0,
                   "L3_A": sarc["L3"] if retea == "tri" else 0.0,
                   "L1_calc_A": calc["L1"], "L2_calc_A": calc["L2"], "L3_calc_A": calc["L3"],
                   "L1_continuu_A": cont["L1"], "L2_continuu_A": cont["L2"], "L3_continuu_A": cont["L3"],
                   "faza_max": f_max, "I_calc_max_A": i_calc_max,
                   "definitie_calc": "Ib de calcul pe fază = ks·Σ Ib general + Σ Ib continuu (ks declarat: ks·Σ Ib)",
                   "repartizare": "pe curentul de calcul: 3F, faze impuse, apoi monofazatele descrescător (§C.8 pct. 5)"}
    if retea == "tri":
        imed = sum(sarc.values()) / 3.0
        dez = (max(sarc.values()) - imed) / imed * 100.0 if imed > 0 else 0.0
        cmed = sum(calc.values()) / 3.0
        dez_c = (max(calc.values()) - cmed) / cmed * 100.0 if cmed > 0 else 0.0
        rez["faze"].update({"dezechilibru_pct": dez, "dezechilibru_calc_pct": dez_c,
                            "definitie": "(Imax − Imed)/Imed, din Ib instalat al circuitelor"})
        j.pas(f"Repartizare pe faze (pe curentul de calcul): Ib instalat L1 {fmt_ro(sarc['L1'])} A, L2 {fmt_ro(sarc['L2'])} A, "
              f"L3 {fmt_ro(sarc['L3'])} A; dezechilibru {fmt_ro(dez, 1)} %; Ib de calcul (ks): L1 {fmt_ro(calc['L1'])} A, "
              f"L2 {fmt_ro(calc['L2'])} A, L3 {fmt_ro(calc['L3'])} A (dezechilibru {fmt_ro(dez_c, 1)} %)")
        if gt(dez, norme.LOCUINTA_DEZECHILIBRU_MAX_PCT):
            emite(j, "V47", AVERTISMENT, "faze", x=dez, lim=norme.LOCUINTA_DEZECHILIBRU_MAX_PCT)
    else:
        rez["faze"].update({"dezechilibru_pct": None, "definitie": "monofazat"})
        j.pas(f"Monofazat: Ib instalat L1 {fmt_ro(sarc['L1'])} A; Ib de calcul (ks) L1 {fmt_ro(calc['L1'])} A")

    # ---- 3. branșament (existent / nou) și coloana C2 -------------------------------------------------------------
    # curentul de dimensionare fără contract: max(Ib din Pc, faza cea mai încărcată)
    i_dim = ib if pa is not None else max(ib_pc, i_calc_max)
    q_decl = al.get("In_Q_bransament_A")
    bi = {"tip_schema": "bransament", "retea": retea, "cosfi": norme.LOCUINTA_COSFI,
          "_cosfi_eticheta": "coloana C2, cosφ mediu al locuinței",
          "L_coloana_m": al.get("L_coloana_m"), "cablu": dict(al.get("cablu") or {})}
    if isinstance(al.get("DDR_bransament_selectiv"), bool):
        bi["DDR_amonte_selectiv"] = al["DDR_bransament_selectiv"]
    if al.get("DDR_bransament_tip"):
        bi["DDR_bransament_tip"] = al["DDR_bransament_tip"]
    q_pres = None
    q_inv = al.get("_q_invalid")
    if q_inv is not None and q_decl is None and al["tip"] == "bransament_existent":
        # v1.7 (M-c1): Q declarat în afara seriei (V05 emis) → Q presupus = calibrul standard imediat superior, limitat la
        # limita blocului (mono: BMPM 40 A); calculul continuă, exportul rămâne refuzat
        if retea == "mono":
            serie_i, lim_i, bloc_i = SERIE_Q_MONO, norme.BMPM["I_max_A"], "BMPM"
        else:
            serie_i, lim_i, bloc_i = SERIE_Q_TRI_TOATE, norme.BMPT["BMPTi-250"]["I_max_A"], "BMPT"
        q_pres = prima_din_serie([x for x in serie_i if x <= lim_i], q_inv) or max(x for x in serie_i if x <= lim_i)
        j.presupune(f"Q branșament {fmt_ro(q_inv, 0)} A nu există în seria {bloc_i} → ignorat; Q presupus {q_pres} A "
                    f"({'calibrul standard imediat superior' if q_pres > q_inv else 'limita blocului ' + bloc_i}) — "
                    f"introdu Q-ul real din BMPM / BMPT (ATR / certificatul de racordare)")
    if al["tip"] == "bransament_existent" and q_pres is None:
        if q_decl is None:
            # P0-2: Q nedeclarat → calibrul standard ≥ Ib (nu mai mic decât sarcina), declarat ca presupus
            bloc_n, lim_b = LIMITA_BLOC[retea]
            serie = SERIE_Q_MONO if retea == "mono" else SERIE_Q_TRI
            # r6: limita blocului se compară cu Ib din P aprobată în convenția ATR (Pa = U·In, cosφ 1) — 9 kW mono
            # = 39,1 A încape în BMPM 40 A; Q-ul fiind PRESUPUS, depășirea e AVERTISMENT, nu BLOCANT
            i_bloc = (pa * 1000.0 / (U * norme.LOCUINTA_Q_DIN_PA_COSFI)) if pa is not None else i_dim
            if gt(i_bloc, lim_b):
                # P aprobată declarată peste limita blocului = date ATR incoerente (BLOCANT); fără P aprobată, Ib vine din
                # bilanțul presupus → AVERTISMENT
                emite(j, "V46", BLOCANT if pa is not None else AVERTISMENT, "Q", "bloc", Ib=i_bloc, bloc=bloc_n, lim=lim_b,
                      rem="declarați Q-ul de branșament existent (din ATR / certificatul de racordare) sau solicitați "
                          "ATR pentru " + ("trecerea pe branșament trifazat (BMPT)" if retea == "mono" else
                                           "un branșament cu măsură semidirectă (BMPTi)") + " / reduceți sarcina simultană")
                j.verificari[-1]["camp"] = "alimentare.In_Q_bransament_A"
                # v1.6 (UX 12): calculul continuă cu Q = limita blocului (exportul rămâne blocat)
                q_pres = max(x for x in serie if x <= lim_b)
            elif pa is not None:
                # r5 (P1-9): Q-ul uzual din ATR pentru P aprobată (Pa = U·In, cosφ 1): 7 kW mono → 32 A, 25 kW tri → 40 A
                # r8 (proiectant, 26.10): Q presupus = calibrul standard ≥ Ib (cosφ 0,95), nu perechea la cosφ 1 —
                # 11 kW tri: Ib 16,7 A → 20 A (nu 16 A); 7 kW mono: Ib 32,0 A → 40 A; limita blocului rămâne la cosφ 1
                q_pres = (prima_din_serie(serie, max(pa * 1000.0 / (U * norme.LOCUINTA_Q_DIN_PA_COSFI), i_dim))
                          or max(x for x in serie if x <= lim_b))
                # r8 (#12, #18): perechea ATR rămâne, dar Q presupus nu coboară sub Ib cu mai mult de toleranța
                # 1,13·In (curentul convențional de nedeclanșare) — altfel calibrul următor din serie (≤ limita blocului)
                if gt(i_dim, norme.LOCUINTA_I_NEDECLANSARE * q_pres):
                    q_up = prima_din_serie([x for x in serie if x <= lim_b], i_dim / norme.LOCUINTA_I_NEDECLANSARE)
                    if q_up is not None:
                        q_pres = q_up
            else:
                q_pres = prima_din_serie(serie, i_dim)
            baza = " din P aprobată" if pa is not None else ""
            if lt(q_pres, i_dim) and pa is not None and not gt(i_dim, norme.LOCUINTA_I_NEDECLANSARE * q_pres):
                # r8 (#12): perechea ATR (Pa = U·In, cosφ 1) — Ib la cosφ de calcul peste In, dar ≤ 1,13·In
                j.presupune(f"Q branșament existent nedeclarat → Q presupus {q_pres} A (perechea ATR Pa = U·In: "
                            f"{fmt_ro(pa)} kW → {q_pres} A; Ib {fmt_ro(i_dim)} A{baza} ≤ 1,13·In = "
                            f"{fmt_ro(norme.LOCUINTA_I_NEDECLANSARE * q_pres)} A, fără rezervă) — introduceți Q-ul real "
                            f"din BMPM/BMPT (ATR / certificatul de racordare)")
            else:
                j.presupune(f"Q branșament existent nedeclarat → Q presupus {q_pres} A ("
                            f"{'calibrul standard ≥' if not lt(q_pres, i_dim) else 'limita blocului;'} Ib "
                            f"{fmt_ro(i_dim)} A{baza}) — introduceți Q-ul real din BMPM/BMPT (ATR / certificatul de racordare)")
            # v1.6 (N5): Q-ul unui branșament EXISTENT e o dată, nu se alege — AVERTISMENT vizibil (DECIZIE: nu BLOCANT,
            # spre deosebire de rețea; mesajele BLOCANTE calculate pe Q presupus o spun explicit, m-n5)
            if "In_Q_bransament_A" not in (al.get("_invalide") or []):
                # v1.7: Q invalid (text / ≤ 0) are deja V07 BLOCANT — nu se mai spune „nedeclarat”
                emite(j, "V46", AVERTISMENT, "Q", "q_pres", Q=q_pres, Ib=i_dim, baza=baza,
                      rem="introduceți Q branșament real (calibrul RCBO / MCB din BMPM / BMPT, din ATR sau "
                          "certificatul de racordare)")
                if lt(q_pres, i_dim):
                    v_ = j.verificari[-1]
                    if pa is not None and not gt(i_dim, norme.LOCUINTA_I_NEDECLANSARE * q_pres) and not gt(
                            pa * 1000.0 / (U * norme.LOCUINTA_Q_DIN_PA_COSFI), lim_b):
                        v_["mesaj"] = v_["mesaj"].replace("(calibrul standard ≥ Ib", "(perechea ATR Pa = U·In; Ib") \
                            + f" — Ib în toleranța de nedeclanșare a Q ({fmt_ro(norme.LOCUINTA_I_NEDECLANSARE * q_pres)} A), fără rezervă"
                    else:
                        v_["mesaj"] = v_["mesaj"].replace("(calibrul standard ≥ Ib", "(limita blocului; Ib")
    if al["tip"] == "bransament_existent":
        q_in = q_decl if q_decl is not None else q_pres
        bi["Q_In_A"] = q_in
        # v1.6 (m8): coloana poartă curentul fazei celei mai încărcate (nu Ib echilibrat din Pa), limitat la In Q
        bi["Ib_A"] = min(float(q_in), max(i_dim, i_calc_max))
    elif pa is not None and q_decl is None:
        # r5 (L04): branșament NOU cu puterea cerută declarată → Q din puterea cerută (convenția ATR, cosφ 1), nu din Pc;
        # Pc > P cerută rămâne semnalat (V46 „pc”), Q-ul nu se mărește în tăcere
        serie_n = SERIE_Q_MONO if retea == "mono" else SERIE_Q_TRI_TOATE
        q_n = prima_din_serie(serie_n, max(pa * 1000.0 / (U * norme.LOCUINTA_Q_DIN_PA_COSFI), i_dim))
        if q_n is not None:
            bi["Q_In_A"] = q_n
            bi["Ib_A"] = min(float(q_n), max(i_dim, i_calc_max))
            j.pas(f"Branșament nou: Q din puterea cerută {fmt_ro(pa)} kW (Pa = U·In) → {q_n} A")
        else:
            bi["Ib_A"] = max(i_dim, ib_pc, i_calc_max)
    else:
        bi["Ib_A"] = max(i_dim, ib_pc, i_calc_max)
    if pa is None and al["tip"] == "bransament_existent" and "P_aprobata_kW" not in (al.get("_invalide") or []):
        emite(j, "V46", AVERTISMENT, "schema", "pa_pres", Pc=pc, Ib=ib_pc,
              rem="introduceți puterea aprobată din ATR / certificatul de racordare")
    for k in ("Ik3_OD_kA", "Zb_OD_ohm", "schema_pamant", "RA_ohm"):
        if inp.get(k) is not None:
            bi[k] = inp[k]
    if inp.get("Zb_OD_ohm") is None:
        # v1.6 (P1-10): Zbuclă OD implicită după zonă
        if al.get("zona") == "rural":
            z = norme.LOCUINTA_ZB_OD_RURAL_OHM
            r0, x0 = norme.OD_ZBUCLA_IMPLICIT_OHM
            m0 = math.hypot(r0, x0)
            bi["Zb_OD_ohm"] = [z * r0 / m0, z * x0 / m0]
            # v1.7 (N11): valoarea după zonă e PRESUPUSĂ — nota de ipoteze / planșa nu o mai atribuie ATR-ului
            bi["_zb_presupus"] = "zonă rurală"
            j.presupune(f"Zbuclă OD {fmt_ro(z, 2)} Ω (zonă rurală) — presupus, valoare implicită prudentă [NEVERIFICAT]; "
                        f"se confirmă cu OD / ATR")
        else:
            j.presupune("zona alimentării nedeclarată → Zbuclă OD implicită urbană |Z| = 0,201 Ω (presupus); la case "
                        "rurale / capăt de linie declarați zona „rural” (0,45 Ω) sau Zb confirmată de OD / ATR")
    bi["_tt_ddr_defect"] = True
    if bi["cablu"].get("material") is None:
        bi["cablu"]["material"] = "Cu"
        j.presupune("coloană C2 Cu (locuință)")
    if bi["cablu"].get("metoda") is None:
        if al.get("pozare_coloana"):
            bi["cablu"]["metoda"] = al["pozare_coloana"]
        else:
            j.presupune("coloana C2 pozată în pământ (D1, CYABY) — pentru apartament / tablou în clădire declarați "
                        "pozarea coloanei „în clădire” (B2, CYY-F)")
    if al.get("L_coloana_m") is None:
        bi["L_coloana_m"] = 15.0
        j.presupune("lungime coloană BMPM/BMPT → tabloul locuinței 15 m")

    # v1.6 (N2): bugetul de ΔU — coloana se mărește ÎNAINTEA circuitelor finale. Proba (jurnal temporar): dacă vreun
    # circuit ar ieși peste secțiunea pe care o are cu coloana la buget, coloana primește ținta ΔU ≤ buget.
    rb = _bransament(dict(bi, cablu=dict(bi["cablu"])), Jurnal())
    buget = norme.LOCUINTA_DU_COLOANA_BUGET_PCT
    c2p, ctxp = rb.get("C2") or {}, rb.get("_ctx_C2")
    rez_buget = None
    if ctxp is not None and bi["cablu"].get("S_fortat") is None and gt(c2p.get("dU_ramura_pct") or 0.0, buget):
        du_or = (ctxp["dU_pct"] or 0.0) - (c2p.get("dU_ramura_pct") or 0.0)
        ctx_b = dict(ctxp, dU_pct=du_or + buget)

        def sect(ctx_):
            jt0 = Jurnal()
            out = []
            for x in ramuri:
                rr0 = calculeaza_ramura(dict(x["r"], cablu=dict(x["r"]["cablu"])), ctx_, jt0, "tmp")["rezultat"]
                out.append((rr0.get("n_paralel") or 1, rr0.get("S_faza_mm2") or 0))
            return out
        marite = [x["c"]["obiect"] for x, a_, b_ in zip(ramuri, sect(ctxp), sect(ctx_b)) if a_ > b_]
        if marite:
            bi["_tinta_dU_C2"] = du_or + buget
            rez_buget = (c2p.get("dU_ramura_pct"), c2p.get("S_faza_mm2"), marite)
    rb = _bransament(bi, j)
    ctx = rb.pop("_ctx_C2", None)
    q_br = rb.pop("_prot_Q", None)
    rez["alimentare"] = {k: v for k, v in rb.items() if k not in ("C2", "schema_pamant", "nota_schema_pamant", "C1")}
    rez["alimentare"]["tip"] = al["tip"]
    rez["alimentare"]["zona"] = al.get("zona")
    if pa is not None:
        rez["alimentare"]["Pa_kW"] = pa
    if q_pres is not None:
        rez["alimentare"]["Q_presupus"] = True
    if pa is None and al["tip"] == "bransament_existent":
        rez["alimentare"]["Pa_presupus"] = True
    # v1.6 (N3): conductoarele racordului OD (C1) — TT: fără PEN
    rez["alimentare"]["C1_conductoare"] = (("3L + N" if retea == "tri" else "L + N") if tt
                                           else ("3L + PEN" if retea == "tri" else "L + PEN"))
    if "C2" in rb:
        col = dict(rb["C2"], descriere="coloana BMPM/BMPT → tabloul locuinței (TE)")
        if tt:
            # v1.6 (N3): TT — coloana NU transportă PE/PEN; PE-ul instalației pornește din priza locală (PPL → BPE)
            from .texte import text_cablu
            col.update({"conductoare": "3L + N" if retea == "tri" else "L + N", "PE": "fara", "S_PE_mm2": None,
                        "PE_origine": "priza_locala", "legatura_BPE": False,
                        "PE_nota": "TT: coloana fără PE / PEN (L + N); PE-ul instalației pornește din priza de pământ "
                                   "locală (PPL → BPE)"})
            col["cablu"] = text_cablu(col["material"], col["izolatie"], col["metoda"], col.get("n_paralel") or 1,
                                      col["S_faza_mm2"], col.get("S_N_mm2"), None, "fara", retea,
                                      monopolar=col.get("monopolar", False))
        else:
            col.update({"conductoare": "3L + N + PE" if retea == "tri" else "L + N + PE", "PE_origine": "bloc",
                        "legatura_BPE": True,
                        "PE_nota": f"TN-C-S: PEN separat pe BN în {rb.get('bloc') or 'bloc'}; PE {fmt_ro(col.get('S_PE_mm2'))} "
                                   f"mm² din coloană la BPE"})
        if rez_buget is not None:
            col["marit_buget_dU"] = {"buget_pct": buget, "dU_initial_pct": rez_buget[0],
                                     "S_initial_mm2": rez_buget[1], "circuite": rez_buget[2]}
            j.pas(f"Coloana C2: ΔU {fmt_ro(rez_buget[0])} % pe {fmt_ro(rez_buget[1])} mm² > bugetul de "
                  f"{fmt_ro(buget)} % și circuitele {', '.join(rez_buget[2])} s-ar mări pentru ΔU → coloana mărită "
                  f"întâi la {fmt_ro(col.get('S_faza_mm2'))} mm² (ΔU {fmt_ro(col.get('dU_ramura_pct'))} %), §C.8 pct. 2")
        rez["coloana"] = col
    if ctx is None:
        return rez
    in_q_br = (rb.get("Q") or {}).get("In_A")

    # ---- 3b. V46 pe faza cea mai încărcată (C1) și P aprobată față de Q ------------------------------------------
    if in_q_br:
        lim113 = norme.LOCUINTA_I_NEDECLANSARE * in_q_br
        rem = ("solicită ATR pentru mărirea puterii (Q branșament mai mare)" +
               (" sau trecerea pe branșament trifazat" if retea == "mono" else " / mută circuite monofazate pe altă fază")
               + ", gestionarea dinamică a sarcinii (DLM la VE) sau redu circuitele simultane")
        if q_pres is not None:
            rem = "introdu Q branșament real din BMPM / BMPT (ATR / certificatul de racordare); altfel " + rem
        niveluri = []
        for f in faze_act:
            i_f = calc[f]
            if gt(i_f, lim113):
                niveluri.append((2, i_f, f, "ib"))
            elif gt(i_f, in_q_br) and cont[f] > 0:
                niveluri.append((2, i_f, f, "cont"))
            elif gt(i_f, in_q_br):
                niveluri.append((1, i_f, f, "av"))
        if niveluri:
            nv, i_f, f, var = max(niveluri)
            nou_pa = al["tip"] == "bransament_nou" and pa is not None and al.get("In_Q_bransament_A") is None
            if nou_pa:
                # r5 (L04): branșament NOU — Q rezultă din puterea CERUTĂ, care încă se poate mări: întrebare (AV), nu blocaj
                rem = "puterea cerută în ATR mărită la ≥ Pc (Q mai mare) sau gestionarea dinamică a sarcinii (DLM la VE)"
            # r6: pe un Q PRESUPUS (nedeclarat) nu se blochează — AVERTISMENT + cererea Q-ului real
            emite(j, "V46", BLOCANT if nv == 2 and not nou_pa and q_pres is None else AVERTISMENT, "Q", var, Ib=i_f,
                  In=in_q_br, lim=lim113,
                  faza=f, cont=cont[f], rem=rem)
            if q_pres is not None:
                # m-n5: mesajul spune că Q e presupus
                v = j.verificari[-1]
                v["mesaj"] = (f"Q branșament presupus {in_q_br} A (nedeclarat) — " + v["mesaj"])
        if ib_pa is not None and q_decl is not None and gt(ib_pa, lim113):
            emite(j, "V46", BLOCANT, "Q", "pa", P=pa, Ib=ib_pa, lim=lim113, rem=rem)
    ik3_te = ctx["Ik3_kA"]
    amonte_txt = (f"Q branșament {(rb.get('Q') or {}).get('tip', '')} {in_q_br} A + SF gG").replace("  ", " ")

    # ---- 4. Q general al TE (întreruptor-separator implicit) și SPD T2 ----------------------------------------
    poli = "4P" if retea == "tri" else "2P"
    tip_qg = str(inp.get("Q_general_tip") or "IS").upper()
    if tip_qg not in ("IS", "MCB"):
        emite(j, "V12", BLOCANT, "Q general", "camp", camp="Q_general_tip", valoare=inp.get("Q_general_tip"))
        tip_qg = "IS"
    if tip_qg == "IS":
        # IS protejat la suprasarcină de Q branșament: In IS ≥ In Q (Ib > In Q e verificat de V46, nu mărește IS)
        In_g = prima_din_serie(norme.IS_IN_A, in_q_br or ib)
        icc, ok = _capacitate_conditionata(ik3_te)
        rez["Q_general"] = {"tip": "IS", "In_A": In_g, "poli": poli, "Icc_kA": icc,
                            "descriere": "întreruptor-separator (fără declanșare — selectivitate asigurată față de Q "
                                         "branșament; In ≥ In Q branșament, protejat la suprasarcină de Q)"}
        j.pas(f"Q general TE: întreruptor-separator {poli} In {In_g} A ≥ In Q branșament {in_q_br} A (protejat de Q)")
        emite(j, "V33", INFO if ok else AVERTISMENT, "Q general", "cond" if ok else "cond_AV",
              aparat=f"IS {In_g} A (curent condiționat de scurtcircuit)", icu=icc, ik3=ik3_te, amonte=amonte_txt)
    else:
        ib_q = min(ib, in_q_br) if in_q_br else ib      # Ib > In Q e verificat de V46, nu mărește Q general
        cand = [x for x in pr.SERII["MCB"] if x >= ib_q - 1e-9 and (in_q_br is None or x <= in_q_br)]
        In_g = cand[-1] if cand else prima_din_serie(pr.SERII["MCB"], ib_q)
        qg = pr.construieste("MCB", In_g, In_g, "C", are_aval=True)
        qg["Icu_kA"], ok = pr.alege_icu("MCB", ik3_te)
        rez["Q_general"] = {"tip": "MCB", "curba": "C", "In_A": In_g, "poli": poli, "Icu_kA": qg["Icu_kA"]}
        if in_q_br and gt(In_g, in_q_br):
            emite(j, "V40", AVERTISMENT if q_pres is not None else BLOCANT, "Q general", "loc",
                  aparat=f"Q general MCB C{In_g}", a=in_q_br, b=In_g)
        if q_br is not None:
            pr.selectivitate(q_br, qg, ik3_te, "Q general vs Q branșament", j)
    # v1.6 (m-n2 / N4): protecția de rezervă a SPD-ului (F2) — MCB C25 (norme.LOCUINTA_SPD_REZERVA), nu peste
    # Q general MCB / Q branșament; poli = poli SPD; Icu ≥ Ik3 la bara TE
    poli_spd = "1P+N" if retea == "mono" else "3P+N"
    rz = norme.LOCUINTA_SPD_REZERVA
    lim_rz = min(x for x in (rz["In_A"], in_q_br, rez["Q_general"]["In_A"] if tip_qg == "MCB" else None) if x)
    In_rz = max([x for x in pr.SERII["MCB"] if x <= lim_rz + 1e-9] or [pr.SERII["MCB"][0]])
    icu_rz, _ = pr.alege_icu("MCB", ik3_te)
    prot_rz = {"tip": rz["tip"], "In_A": In_rz, "curba": rz["curba"], "poli": poli_spd, "Icu_kA": icu_rz,
               "ref": "F2", "text": f"MCB {poli_spd} {rz['curba']}{In_rz}{NB}A"}
    rez["SPD"] = dict(norme.SPD_T2_LOCUINTA, poli=poli_spd,
                      configuratie=("CT2 („1+1” / „3+1”, eclator N–PE) — TT, în aval de DDR (SR HD 60364-5-534)" if tt
                                    else "CT1 (L–PE, N–PE) — TN-S în TE"),
                      loc="intrarea TE, după Q general",
                      protectie=f"protecție de rezervă F2: MCB {poli_spd} {rz['curba']}{In_rz}{NB}A (conform fișei SPD)",
                      protectie_rezerva=prot_rz, In_amonte_A=In_rz, prot_tip="MCB", curba_amonte=rz["curba"],
                      PE_la="BPE")
    j.pas(f"SPD T2 {poli_spd}: protecție de rezervă F2 MCB {rz['curba']}{In_rz} A (≤ {fmt_ro(lim_rz, 0)} A, fișa SPD "
          f"T2 In 20 kA admite MCB C ≤ 25…32 A), Icu {icu_rz} kA ≥ Ik3 TE {fmt_ro(ik3_te)} kA")

    # ---- 5. grupele DDR și circuitele -----------------------------------------------------------------------------
    jt = Jurnal()
    for x in ramuri:
        x["Ip"] = calculeaza_ramura(dict(x["r"], _doar_protectie=True), ctx, jt, "tmp")["Ip"] or 0
        if not x["Ip"]:
            # circuit invalid (V04 / V05 …): calibrul din intrare / cel uzual, ca grupa și desenul să existe (M-n1)
            x["Ip"] = x["r"].get("In_fortat") or x["r"].get("In_minim") or 16
            x["Ip_neales"] = True
    for x in (y for g in grupe if g["cheie"] == "fara" for y in g["membri"]):
        if x["c"]["receptor"] == "tablou_secundar":
            continue        # r6: alimentarea TD (TN) — protecție prin MCB, DDR 30 mA pe circuitele din TD
        if x["c"]["receptor"].startswith("prize"):
            emite(j, "V29", BLOCANT, x["c"]["obiect"], "B", In=x["r"].get("In_fortat") or x["r"]["In_minim"])
        else:
            # v1.5 (M1): în locuințe toate circuitele finale au DDR ≤ 30 mA
            emite(j, "V49", BLOCANT, x["c"]["obiect"], rec=eticheta_receptor(x["c"]["receptor"]))
    sus = None
    impl = norme.LOCUINTA_DDR_BRANSAMENT_IMPLICIT
    sel_decl = al.get("DDR_bransament_selectiv")
    if rb.get("RCCB"):
        sus = ddr_mod.descriere(rb["RCCB"]["IdN_mA"], sel_decl if isinstance(sel_decl, bool) else rb["RCCB"].get("selectiv", True),
                                "RCCB BMPT")
    elif (rb.get("Q") or {}).get("IdN_mA"):
        # r5 (P1-14): RCBO-ul 300 mA din BMPM presupus selectiv (S) dacă nu e declarat altfel — altfel V43 la orice casă
        sel = sel_decl if isinstance(sel_decl, bool) else impl["selectiv"]
        sus = ddr_mod.descriere(rb["Q"]["IdN_mA"], sel, "RCBO BMPM")
        rez["alimentare"]["DDR_bransament_selectiv"] = sel
    if sus is not None:
        nd = ([f"tip {impl['tip']}"] if al.get("DDR_bransament_tip") is None else []) + \
             (["selectiv (S)"] if not isinstance(sel_decl, bool) and not rb.get("RCCB") else [])
        if nd:
            j.presupune(f"DDR-ul 300 mA din {'BMPT' if rb.get('RCCB') else 'BMPM'}: {', '.join(nd)} — presupus (echiparea "
                        f"uzuală a blocurilor noi); branșamentul vechi cu DDR tip AC / instantaneu se declară")
    # v1.7 (M-c3): tipul DDR-ului 300 mA din branșament (declarat sau cel din ST 3-JT / ST 4-JT: AC)
    am_nume = "RCCB BMPT" if rb.get("RCCB") else "RCBO BMPM"
    am_idn = (rb.get("RCCB") or {}).get("IdN_mA") or (rb.get("Q") or {}).get("IdN_mA")
    am_tip = al.get("DDR_bransament_tip") or norme.LOCUINTA_DDR_BRANSAMENT_IMPLICIT["tip"]
    rez["alimentare"]["DDR_bransament_tip"] = am_tip if sus is not None else None
    ra = None
    if tt:
        ra, lim = _tt_ra(inp, j)
        if lim is None:
            return rez
    v43 = []
    k_ddr = 0
    for g in grupe:
        mem = g["membri"]
        if g["cheie"] == "fara":
            g["obiect"] = "fără DDR"
            g["DDR"] = None
        else:
            k_ddr += 1
            g["obiect"] = f"DDR{k_ddr}"
            d0 = mem[0]["c"]["DDR"] if g["cheie"] in ("propriu", "VE") and isinstance(mem[0]["c"]["DDR"], dict) else None
            ve = g["cheie"] == "VE"
            idn = int(d0["IdN_mA"]) if d0 else 30
            tip_d = d0.get("tip") if d0 and d0.get("tip") else (norme.LOCUINTA_VE_DDR_IMPLICIT if ve else "A")
            if ve and not (d0 and d0.get("tip")):
                j.presupune("încărcarea VE: DDR 30 mA tip A + RDC-DD 6 mA c.c. în stație (SR HD 60364-7-722) — tip B se "
                            "declară pe circuit dacă stația nu are RDC-DD")
            rcbo = len(mem) == 1 and not ve      # VE: RCCB tip B + MCB (RCBO tip B — aparat rar, DECIZIE)
            # In DDR: Σ In MCB pe faza cea mai încărcată a grupei
            pe_f = {}
            for x in mem:
                for f in (("L1", "L2", "L3") if x["faza"] == "3F" else (x["faza"],)):
                    pe_f[f] = pe_f.get(f, 0.0) + x["Ip"]
            s_in = max(pe_f.values())
            if rcbo:
                In_d = mem[0]["Ip"]
                g["DDR"] = {"IdN_mA": idn, "tip": tip_d, "In_A": In_d, "poli": g["poli"], "aparat": "RCBO",
                            "curba": mem[0]["r"].get("curba"), "temporizare": "instantaneu", "selectiv": False}
            else:
                # In DDR ≥ cel mai mare MCB din grupă și ≥ min(In Q branșament, Σ In MCB pe fază): DDR-ul e protejat la
                # suprasarcină de Q-ul din amonte sau nu poate fi depășit de suma circuitelor (DECIZIE, art. 531.2);
                # In RCCB > In Q e corect (RCCB protejat de Q) — nu e V40
                ref = max(max(x["Ip"] for x in mem), min(in_q_br or s_in, s_in))
                In_d = prima_din_serie(norme.RCCB_IN_A, max(ref, norme.LOCUINTA_RCCB_IN_MIN_A)) or ref
                inc, ok = _capacitate_conditionata(ik3_te)
                g["DDR"] = {"IdN_mA": idn, "tip": tip_d, "In_A": In_d, "poli": g["poli"], "aparat": "RCCB",
                            "temporizare": "instantaneu", "selectiv": False, "Inc_kA": inc}
                emite(j, "V33", INFO if ok else AVERTISMENT, g["obiect"], "cond" if ok else "cond_AV",
                      aparat=f"RCCB {In_d} A (Inc)", icu=inc, ik3=ik3_te, amonte=amonte_txt)
            if ve:
                g["DDR"]["alternativa"] = "tip A-EV + RDC-DD 6 mA c.c. (SR HD 60364-7-722)"
                if d0 and tip_d != "B":
                    emite(j, "V49", AVERTISMENT, g["obiect"], "ve_tip", tip=tip_d, rec=eticheta_receptor("vehicul_electric"))
                if sus is not None:
                    _verifica_ve_amonte(j, g, tip_d, am_nume, am_idn, am_tip, tt, al.get("DDR_bransament_tip"))
            if d0 and d0.get("selectiv"):
                g["DDR"].update({"selectiv": True, "temporizare": "S"})
            if idn > 30 and not all(x["c"]["receptor"] == "tablou_secundar" for x in mem):
                if any(x["c"]["receptor"].startswith("prize") for x in mem):
                    emite(j, "V29", BLOCANT, g["obiect"], "B", In=max(x["Ip"] for x in mem))
                else:
                    emite(j, "V49", BLOCANT, g["obiect"], "idn", IdN=idn, rec=eticheta_receptor(mem[0]["c"]["receptor"]))
            if tip_d == "AC":
                emite(j, "V49", AVERTISMENT, g["obiect"], "tip_ac", rec=eticheta_receptor(mem[0]["c"]["receptor"]))
            if tt and gt(ra * idn / 1000.0, 50.0):
                emite(j, "V34", BLOCANT, g["obiect"], RA=ra, IdN=idn, x=ra * idn / 1000.0)
            j.pas(f"{g['obiect']} ({NUME_GRUPE.get(g['cheie'], 'propriu')}, {g['faza']}): "
                  + (f"RCBO {idn} mA tip {tip_d} {g['poli']}, In {fmt_ro(In_d)} A (circuit singur)" if rcbo else
                     f"RCCB {idn} mA tip {tip_d} {g['poli']}, In {In_d} A ≥ max(In MCB max; min(In Q branșament, "
                     f"Σ In MCB pe fază = {fmt_ro(s_in)} A))")
                  + f"; {len(mem)} {'circuit' if len(mem) == 1 else 'circuite'}")
            if sus is not None:
                jv = Jurnal()
                ddr_mod.verifica(jv, sus, ddr_mod.descriere(idn, g["DDR"]["selectiv"], g["obiect"]),
                                 g["obiect"], RA_ohm=ra)
                v43 += [(g["obiect"], v) for v in jv.verificari + jv.info]
        cg = dict(ctx, schema="TT" if tt else ctx.get("schema", "TN"), idn_tt_mA=None, ddr_sus=None,
                  ddr_ramura=f"DDR {g['DDR']['IdN_mA']} mA ({g['obiect']})" if g["DDR"] else None)
        if tt and g["DDR"]:
            cg["tt_ddr_defect"] = {"IdN_mA": g["DDR"]["IdN_mA"], "RA_ohm": ra}
        g["circuite"] = []
        for x in mem:
            n_v0 = len(j.verificari)
            rr = calculeaza_ramura(x["r"], cg, j, x["c"]["obiect"])
            if (rr["rezultat"] or {}).get("dU_plafonat_mm2"):
                # v1.7 (m-c6): circuitul nu mai crește peste plafon — problema e coloana / poziția tabloului
                for v in j.verificari[n_v0:]:
                    if v["cod"] == "V20" and v["obiect"] == x["c"]["obiect"]:
                        v["mesaj"] += (f" — secțiunea circuitului plafonată la {fmt_ro(rr['rezultat']['dU_plafonat_mm2'], 0)}"
                                       f" mm² (ΔU la bara TE {fmt_ro(cg['dU_pct'])} %)")
                        v["remediere"] = ("mărește coloana C2 (secțiune mai mare / fără secțiune impusă) sau mută tabloul "
                                          "mai aproape de branșament; altfel scurtează / împarte circuitul (tablou secundar)")
            out = dict(rr["rezultat"], nume=x["c"].get("nume", ""), receptor=x["c"]["receptor"],
                       receptor_eticheta=eticheta_receptor(x["c"]["receptor"]),
                       receptor_calcul=x["r"]["receptor"], faza=x["faza"], P_kW=x["r"]["P_kW"],
                       DDR_grupa=g["obiect"] if g["DDR"] else None,
                       DDR_obligatoriu=x["d"]["ddr"] == "obligatoriu", continuu=x["d"]["continuu"])
            out.setdefault("obiect", x["c"]["obiect"])
            blocat = bool(rr.get("blocat")) or bool(x["c"].get("_blocat"))
            out["blocat"] = blocat
            if x["c"].get("_blocat"):
                out["blocat_coduri"] = sorted(set(x["c"]["_blocat"]))
            prot = out.get("protectie") or {}
            if not prot.get("In_A"):
                # v1.6 (M-n1 / UX 12): circuit blocat — protecția din intrare / calibrul uzual, marcată „neverificat”
                prot = {"tip": "MCB", "In_A": x["Ip"], "curba": x["r"].get("curba"), "neverificat": True}
                out["protectie"] = prot
            if g["DDR"] and g["DDR"]["aparat"] == "RCBO":
                out["protectie"] = dict(prot, tip="RCBO", IdN_mA=g["DDR"]["IdN_mA"], tip_ddr=g["DDR"]["tip"],
                                        poli="1P+N" if g["poli"] == "2P" else "4P")
                g["DDR"]["Icn_kA"] = prot.get("Icu_kA")
            if in_q_br and prot.get("In_A") and gt(prot["In_A"], in_q_br):
                # r6: față de un Q de branșament PRESUPUS — AVERTISMENT (Q-ul real se cere), nu BLOCANT
                ve_c = x["d"]["grupa"] == "VE"
                emite(j, "V40", AVERTISMENT if (q_pres is not None and not ve_c) else BLOCANT, x["c"]["obiect"], "loc",
                      aparat=f"{'RCBO' if g['DDR'] and g['DDR']['aparat'] == 'RCBO' else 'MCB'} {prot.get('curba', '')}"
                             f"{prot['In_A']}", a=in_q_br, b=prot["In_A"])
                if ve_c:
                    # r9 (locuințe #42, #44, #69): stația VE cere mai mult decât branșamentul — nu se desenează tăcut
                    j.verificari[-1]["mesaj"] += (f" — stația VE de {fmt_ro(x['r']['P_kW'])} kW depășește "
                                                  f"branșamentul (Q {fmt_ro(in_q_br, 0)} A)")
                    j.verificari[-1]["remediere"] = (
                        "întrebare pentru beneficiar: stație VE de putere mai mică / curent de încărcare limitat din "
                        "setări (ex. 16 A → C20), gestionarea dinamică a sarcinii (DLM) sau mărirea puterii aprobate "
                        "(Q branșament mai mare)")
                    j.verificari[-1]["intrebare"] = True
            # protecția la defect (contact indirect), explicit pe fiecare circuit (P0-3)
            idn_g = g["DDR"]["IdN_mA"] if g["DDR"] else None
            if g["DDR"] and tt:
                out["protectie_defect"] = (f"DDR {idn_g} mA ({g['obiect']}) — TT: RA·IΔn = {fmt_ro(ra * idn_g / 1000.0)} V "
                                           f"≤ 50 V; Ik1/Ia doar pentru scurtcircuitul L–N")
            elif out.get("Ia_A") is not None and out.get("Ik1min_capat_A") is not None \
                    and ge(out["Ik1min_capat_A"], out["Ia_A"]):
                out["protectie_defect"] = (f"MCB: Ik1min {fmt_ro(out['Ik1min_capat_A'], 0)} A ≥ Ia {fmt_ro(out['Ia_A'], 0)} A"
                                           + (f"; DDR {idn_g} mA protecție suplimentară" if g["DDR"] else ""))
            elif blocat:
                out["protectie_defect"] = (f"DDR {idn_g} mA ({g['obiect']}) — circuit blocat, Ik1 necalculat" if g["DDR"]
                                           else "circuit blocat, neverificat")
            elif g["DDR"]:
                out["protectie_defect"] = f"DDR {idn_g} mA ({g['obiect']}) — Ik1min < Ia"
            else:
                out["protectie_defect"] = "neasigurată fără DDR"
            if x["c"]["receptor"] == "sauna":
                out["cablu_nota"] = norme.LOCUINTA_SAUNA_CABLU
            if x["c"]["idx"] in td_map and not rr["blocat"]:
                out["tablou_secundar"] = _calculeaza_td(td_map[x["c"]["idx"]], x, rr, j)
            g["circuite"].append(out)
        if g["DDR"]:
            fz = sorted({x["faza"] for x in mem})
            g["faza"] = "3F" if "3F" in fz or len(fz) > 1 else fz[0]
            if g["DDR"]["aparat"] == "RCBO" and g["DDR"].get("Icn_kA") is None:
                g["DDR"]["Icn_kA"] = icu_rz
    _agrega_v43(j, v43)
    rez["grupe_DDR"] = [{k: g[k] for k in ("obiect", "DDR", "faza", "circuite") if k in g} |
                        {"grupa": NUME_GRUPE.get(g["cheie"], "propriu")} |
                        ({"nivel": nivel_din_nume(g["membri"][0]["c"].get("nume"))} if g["cheie"] == "iluminat" else {})
                        for g in grupe]
    rez["circuite_blocate"] = [c["obiect"] for g in rez["grupe_DDR"] for c in g["circuite"] if c.get("blocat")]

    # ---- nota 3 -------------------------------------------------------------------------------------------------
    spl = inp.get("schema_pamant") or "TN-C-S"
    rez["schema_pamant"] = spl
    bloc = rb.get("bloc") or "bloc"
    n_g = sum(1 for g in grupe if g["DDR"])
    if spl == "TT":
        ddr_txt = (f"{'RCCB' if rb.get('RCCB') else 'RCBO'} {bloc} 300{NB}mA; DDR {30}{NB}mA pe {n_g} "
                   f"{'grupă' if n_g == 1 else 'grupe'} de circuite (protecția la defect în TT)")
        rez["nota_schema_pamant"] = nota_schema_pamant("tablou", "TT", bloc, inp.get("RA_ohm") if inp.get("RA_ohm")
                                                       is not None else ra, idn_mA=300, ddr_txt=ddr_txt)
    else:
        rez["nota_schema_pamant"] = (f"Schemă de legare la pământ: TN-C-S cu separarea PEN pe BN în {bloc}; TN-S în "
                                     f"tabloul locuinței, DDR 30{NB}mA pe {n_g} {'grupă' if n_g == 1 else 'grupe'} de "
                                     f"circuite. Rp ≤ 4{NB}Ω.")
    return rez
