"""Teste de proprietate (fuzz) — SPEC §H.4 pct. 5, cu seed fix.

Pe 20 000 de ramuri aleatoare (≥ 10 000 dimensionate complet) (P 0,5…2000 kW, L 1…1500 m, toate metodele, materiale/izolații/calibre/secțiuni impuse,
date absurde) și pe scheme întregi aleatoare (tablouri cu 1–15 plecări, cascade, PT, CEF) se verifică:
  * niciodată Ip > Iz' fără V02/V01;
  * niciodată ΔU_cum > limită fără V20/V21;
  * nicio protecție în afara seriilor din norme;
  * niciun cablu Al sub 16 mm²;
  * nicio excepție necapturată;
  * Ib ≤ Ip mereu, când nu există BLOCANT;
  * I2 ≤ 1,45·Iz' mereu, când nu există BLOCANT.
"""
import os
import random
import sys

import pytest

RADACINA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RADACINA)

from engine.calc import calculeaza, calculeaza_ramura, dimensioneaza_ramura_simpla  # noqa: E402
from engine.calc import norme, protectii as pr, scurtcircuit as sc  # noqa: E402
from engine.calc.comun import Jurnal  # noqa: E402

SEED = 20261012
N_RAMURI = 20_000          # ≥ 10 000 dintre ele ajung dimensionate complet (nu blocate la validare)
N_SCHEME = 400
TOL = 1e-6

NUME = ["Hală", "Birouri", "Iluminat hală", "Prize atelier", "Pompe", "Compresor", "Ventilație", "Moară", "HVAC",
        "Depozit", "TD-1", "TD-2", "Cantină", "Iluminat exterior", "Malaxor", "Concasor", "Atelier"]


# ------------------------------------------------------------------------------------------------------------
# generatoare
# ------------------------------------------------------------------------------------------------------------
def _p_log(rnd, a=0.5, b=2000.0):
    return round(10 ** rnd.uniform(__import__("math").log10(a), __import__("math").log10(b)), 2)


def ramura_aleatoare(rnd):
    rol = rnd.choice(["plecare", "final", "intrare", "invertor", "c2"])
    if rol == "invertor":
        receptor = rnd.choice(["invertor", "pcs"])
    else:
        receptor = rnd.choice(["iluminat", "prize", "forta", "motor", "tablou"])
    r = {"rol": rol, "receptor": receptor, "retea": rnd.choice(["tri"] * 4 + ["mono"])}
    if rol == "invertor":
        r["Pn_kW"] = _p_log(rnd, 1, 1000)
        if rnd.random() < 0.2:
            r["Iac_max_A"] = round(r["Pn_kW"] * rnd.uniform(1.4, 1.8), 2)
    else:
        x = rnd.random()
        if x < 0.55:
            r["P_kW"] = _p_log(rnd)
        elif x < 0.85:
            r["In_A"] = rnd.choice(norme.GG_IN_A + norme.MCB_IN_A + norme.MCCB_IN_A + [72, 35, 3000])
        elif x < 0.92:
            r["S_kVA"] = _p_log(rnd, 1, 1500)
        elif x < 0.96:
            r["Ib_A"] = _p_log(rnd, 1, 3000)
        else:
            r["P_kW"] = rnd.choice([0, -5, 10])
    if rnd.random() < 0.15:
        r["cosfi"] = rnd.choice([0.5, 0.65, 0.8, 0.95, 1.0, 1.2, 0.0])
    if rnd.random() < 0.1:
        r["ks"] = rnd.choice([0.3, 0.7, 1.0, 1.3])
    if rnd.random() < 0.1:
        r["h3"] = rnd.choice([5, 10, 20, 30, 40, 50])
    if rnd.random() < 0.15:
        r["prot_tip"] = rnd.choice(["MCB", "MCCB", "ACB", "gG"])
    if rnd.random() < 0.1:
        r["In_fortat"] = rnd.choice([16, 25, 40, 63, 72, 100, 160, 250, 400, 630, 1250])
    if rnd.random() < 0.05:
        r["Icu_fortat"] = rnd.choice([6, 10, 25, 50])
    if rnd.random() < 0.1:
        r["Ip_min_extra"] = rnd.uniform(5, 800)
    r["are_aval"] = rnd.random() < 0.3
    metoda = rnd.choice(["C", "D1", "D2", "E"])
    cab = {"L": rnd.choice([rnd.uniform(1, 1500)] * 9 + [0, -3, 1200]), "metoda": metoda}
    if rnd.random() < 0.7:
        cab["material"] = rnd.choice(["Cu", "Al"])
    if rnd.random() < 0.5:
        cab["izolatie"] = rnd.choice(["PVC", "XLPE"])
    if rnd.random() < 0.2:
        cab["theta"] = rnd.choice([10, 25, 35, 42, 55, 65, 85])
    if rnd.random() < 0.2:
        cab["rho_sol"] = rnd.choice([0.5, 1.2, 2.0, 2.7, 3.5])
    if rnd.random() < 0.25:
        cab["n_alte"] = rnd.randint(0, 22)
    if rnd.random() < 0.12:
        cab["S_fortat"] = rnd.choice(norme.SECTIUNI_STD + [10.0, 300.0])
        if rnd.random() < 0.4:
            cab["n_fortat"] = rnd.randint(1, 4)
    if rnd.random() < 0.05:
        cab["N_fortat"] = rnd.choice([16, 25, 50, 95, 120])
    if rnd.random() < 0.05:
        cab["PE_fortat"] = rnd.choice([4, 10, 16, 35, 70])
        cab["PE_loc"] = rnd.choice(["cablu", "separat"])
    r["cablu"] = cab
    return r


def context_aleator(rnd):
    if rnd.random() < 0.3:
        t = sc.trafo(rnd.choice(norme.TRAFO_SN_KVA))
        ctx = sc.context_pt(t)
    else:
        ik3 = None if rnd.random() < 0.5 else rnd.uniform(2, 60)
        zb = None if rnd.random() < 0.5 else (rnd.uniform(0.01, 0.6), rnd.uniform(0.005, 0.3))
        ctx = sc.context_od(ik3, zb, ddr_amonte=rnd.random() < 0.5, schema=rnd.choice(["TN"] * 5 + ["TT"]))
    ctx["dU_pct"] = rnd.choice([0.0, 0.0, rnd.uniform(0, 4)])
    if rnd.random() < 0.2:
        ctx["ddr_ramura"] = "RCCB"
    return ctx


def plecare_aleatoare(rnd, nivel=0):
    pl = {"nume": rnd.choice(NUME)}
    x = rnd.random()
    if x < 0.5:
        pl["In_A"] = rnd.choice([16, 25, 32, 40, 50, 63, 80, 100, 125, 160, 250, 400])
    else:
        pl["P_kW"] = _p_log(rnd, 0.5, 300 if nivel == 0 else 40)
    if rnd.random() < 0.3:
        pl["L_m"] = rnd.uniform(5, 400)
    if nivel == 0 and rnd.random() < 0.2:
        pl.pop("In_A", None)
        pl.pop("P_kW", None)
        pl["copii"] = [plecare_aleatoare(rnd, nivel + 1) for _ in range(rnd.randint(1, 5))]
    if rnd.random() < 0.1:
        pl["cablu"] = {"material": rnd.choice(["Cu", "Al"]), "metoda": rnd.choice(["C", "D1", "E"]),
                       "n_alte": rnd.randint(0, 6)}
    return pl


def schema_aleatoare(rnd):
    tip = rnd.choice(["tablou", "tablou", "pt", "cef", "bransament", "prosumator", "ge_ats"])
    if tip == "tablou":
        inp = {"tip_schema": "tablou", "plecari": [plecare_aleatoare(rnd) for _ in range(rnd.randint(1, 15))]}
        if rnd.random() < 0.25:
            inp["circuite_finale"] = True
            for pl in inp["plecari"]:
                pl.pop("copii", None)
                if "In_A" not in pl and "P_kW" not in pl:
                    pl["In_A"] = rnd.choice([10, 16, 20, 25, 32])
                if rnd.random() < 0.5:
                    pl["receptor"] = rnd.choice(["iluminat", "prize", "forta", "motor"])
        if rnd.random() < 0.25:
            inp["origine"] = "pt_propriu"
            if rnd.random() < 0.6:
                inp["pt_Sn_kVA"] = rnd.choice(norme.TRAFO_SN_KVA + [300])
        if rnd.random() < 0.6:
            inp["P_kW"] = _p_log(rnd, 5, 800)
        if rnd.random() < 0.6:
            inp["L_alimentare_m"] = rnd.uniform(5, 300)
        if rnd.random() < 0.15:
            inp["In_Q1_A"] = rnd.choice([40, 63, 100, 160, 250, 400])
        return inp
    if tip == "pt":
        return {"tip_schema": "pt", "Sn_kVA": rnd.choice(norme.TRAFO_SN_KVA + [300]),
                "plecari": [plecare_aleatoare(rnd) for _ in range(rnd.randint(1, 12))]}
    if tip == "cef":
        inp = {"tip_schema": "cef", "kWp": _p_log(rnd, 20, 2000),
               "invertoare": [{"n": rnd.randint(1, 8), "Pn_kW": rnd.choice([10, 20, 50, 100, 110, 125, 250])}]}
        if rnd.random() < 0.4:
            inp["bess"] = {"kWh": rnd.choice([100, 200, 1000]), "P_kW": rnd.choice([None, 50, 125, 500])}
        if rnd.random() < 0.4:
            inp["pt_Sn_kVA"] = rnd.choice(norme.TRAFO_SN_KVA)
        if rnd.random() < 0.3:
            inp["string"] = {"n_module": rnd.randint(10, 24), "Uoc_V": 49.5, "n_stringuri_paralel": rnd.randint(1, 4),
                             "Isc_A": 13.9, "I_rev_A": 25}
        return inp
    if tip == "bransament":
        inp = {"tip_schema": "bransament", "retea": rnd.choice(["tri", "tri", "mono"]), "L_coloana_m": rnd.uniform(5, 400)}
        surse = rnd.choice([["P_kW"], ["S_kVA"], ["Ib_A"], ["P_kW", "Ib_A"], ["S_kVA", "P_kW"]])
        for k in surse:
            inp[k] = _p_log(rnd, 1, 200) if k != "Ib_A" else _p_log(rnd, 2, 300)
        return inp
    if tip == "prosumator":
        return {"tip_schema": "prosumator", "retea": rnd.choice(["tri", "mono"]), "Pn_inv_kW": _p_log(rnd, 1, 500),
                "In_Q_bransament_A": rnd.choice([25, 32, 40, 63])}
    return {"tip_schema": "ge_ats", "Sn_GE_kVA": rnd.choice([30, 50, 100, 250, 500]), "P_sarcina_kW": _p_log(rnd, 5, 400)}


# ------------------------------------------------------------------------------------------------------------
# proprietățile
# ------------------------------------------------------------------------------------------------------------
def coduri_obiect(verificari, obiect):
    return {(v["cod"], v["nivel"]) for v in verificari if v["obiect"] == obiect}


def verifica_ramura(rez, verificari, eticheta):
    """Proprietățile SPEC §H.4 pct. 5 pentru rezultatul unei ramuri nedublocate."""
    if rez is None or rez.get("blocat"):
        return
    ob = rez["obiect"]
    cod = coduri_obiect(verificari, ob)
    prot = rez["protectie"]
    ip = prot.get("Ir_A") if prot.get("Ir_A") is not None else prot["In_A"]
    # protecția în serie
    p = dict(prot)
    if prot["tip"] in ("MCCB", "ACB"):
        p["decl"] = prot.get("decl")
    assert pr.in_serie(p), f"{eticheta}: protecție în afara seriei {prot}"
    # Al ≥ 16 mm²
    if rez["material"] == "Al":
        assert rez["S_faza_mm2"] >= 16, f"{eticheta}: Al {rez['S_faza_mm2']} mm²"
    # Ip ≤ Iz' sau V02/V01
    if ip > rez["Iz_corectat_A"] * (1 + TOL):
        assert ("V02", "BLOCANT") in cod or ("V01", "BLOCANT") in cod, \
            f"{eticheta}: Ip {ip} > Iz' {rez['Iz_corectat_A']} fără V02/V01"
    # ΔU cumulat ≤ limită sau V20/V21
    if rez["dU_cumulat_pct"] > rez["dU_limita_pct"] * (1 + TOL):
        assert ("V20", "BLOCANT") in cod or ("V21", "AVERTISMENT") in cod, \
            f"{eticheta}: ΔU {rez['dU_cumulat_pct']} > {rez['dU_limita_pct']} fără V20/V21"
    blocant = any(v["nivel"] == "BLOCANT" for v in verificari if v["obiect"] in (ob, f"{ob} vs amonte"))
    if not blocant:
        assert rez["Ib_A"] <= ip * (1 + TOL), f"{eticheta}: Ib {rez['Ib_A']} > Ip {ip} fără BLOCANT"
        assert rez["I2_A"] <= 1.45 * rez["Iz_corectat_A"] * (1 + TOL), \
            f"{eticheta}: I2 {rez['I2_A']} > 1,45·Iz' {rez['Iz_corectat_A']} fără BLOCANT"
    for k in ("Ib_A", "Iz_corectat_A", "dU_cumulat_pct", "Ik3max_capat_kA", "Ik1min_capat_A"):
        v = rez[k]
        assert v == v and v != float("inf"), f"{eticheta}: {k} = {v}"


def test_fuzz_ramuri():
    rnd = random.Random(SEED)
    blocate = 0
    for i in range(N_RAMURI):
        r = ramura_aleatoare(rnd)
        ctx = context_aleator(rnd)
        j = Jurnal()
        try:
            out = calculeaza_ramura(r, ctx, j, f"R{i}")
        except Exception as e:  # nicio excepție necapturată
            pytest.fail(f"ramura {i}: excepție {type(e).__name__}: {e}\nintrare={r}\nctx={ctx}")
        if out["blocat"]:
            blocate += 1
            assert any(v["nivel"] == "BLOCANT" for v in j.verificari), f"ramura {i} blocată fără BLOCANT"
            continue
        verifica_ramura(out["rezultat"], j.verificari, f"ramura {i} {r}")
    assert N_RAMURI - blocate >= 10_000, f"doar {N_RAMURI - blocate} ramuri dimensionate complet"


def _ramuri_din_rezultat(rez):
    for k in ("C2", "Q1_C1", "INV", "PCS"):
        if isinstance(rez.get(k), dict):
            yield rez[k]
    for k in ("plecari", "invertoare"):
        for x in rez.get(k) or []:
            yield x


def test_fuzz_scheme():
    rnd = random.Random(SEED + 1)
    for i in range(N_SCHEME):
        inp = schema_aleatoare(rnd)
        try:
            r = calculeaza(inp)
        except Exception as e:
            pytest.fail(f"schema {i}: excepție {type(e).__name__}: {e}\nintrare={inp}")
        assert r["blocheaza_export"] == any(v["nivel"] == "BLOCANT" for v in r["verificari"])
        for v in r["verificari"] + r["info"]:
            assert v["mesaj"] and v["cod"].startswith("V")
        for rz in _ramuri_din_rezultat(r["rezultat"]):
            verifica_ramura(rz, r["verificari"], f"schema {i} ({inp['tip_schema']})")
            if rz.get("DDR"):
                # v1.2 R3: DDR și pe circuitul invertorului prosumatorului (30 mA tip A, V73)
                assert (rz["receptor"] == "prize" and rz["protectie"]["In_A"] <= 32) or rz["receptor"] == "invertor"
        if inp["tip_schema"] == "bransament":
            n_surse = sum(inp.get(k) is not None for k in ("P_kW", "S_kVA", "Ib_A"))
            assert (n_surse > 1) == any(v["cod"] == "V12" for v in r["verificari"])
        if inp["tip_schema"] == "ge_ats" and inp.get("P_sarcina_kW"):
            sn = r["rezultat"]["Sn_GE_minim_kVA"]
            assert sn is None or sn in norme.GE_SN_KVA
        for k in ("Q_JT", "QG"):
            q = r["rezultat"].get(k)
            if q:
                assert q["In_A"] in pr.SERII[q["tip"]] or any(v["cod"] == "V05" for v in r["verificari"])
                assert q["Icu_kA"] in pr.SERII_ICU[q["tip"]]


def test_fuzz_date_absurde():
    """Intrări incomplete sau absurde → BLOCANT, niciodată excepție (SPEC §B.2, §D V07–V10)."""
    cazuri = [{"tip_schema": "tablou", "plecari": []},
              {"tip_schema": "tablou", "plecari": [{"nume": "X"}]},
              {"tip_schema": "bransament"},
              {"tip_schema": "pt", "Sn_kVA": 333, "plecari": []},
              {"tip_schema": "necunoscut"},
              {"tip_schema": "cef", "invertoare": []},
              {"tip_schema": "bransament", "P_kW": -3, "L_coloana_m": 10},
              {"tip_schema": "tablou", "P_kW": 50, "plecari": [{"nume": "A", "P_kW": 10, "cosfi": 0}]}]
    for inp in cazuri:
        r = calculeaza(inp)
        assert r["blocheaza_export"], inp


def test_fuzz_ramura_simpla():
    """API-ul panoului „Dimensionează”: aceleași proprietăți, fără excepții, pe intrări aleatoare."""
    rnd = random.Random(SEED + 2)
    for i in range(3000):
        p = {"rol": rnd.choice(["plecare", "final", None]), "retea": rnd.choice(["tri", "tri", "mono"]),
             "receptor": rnd.choice(["iluminat", "prize", "forta", "motor", "tablou", None]),
             "origine": rnd.choice(["retea_publica", "pt_propriu", None])}
        if rnd.random() < 0.6:
            p["P_kW"] = _p_log(rnd, 0.5, 800)
        if rnd.random() < 0.45:
            p["In_A"] = rnd.choice(norme.MCB_IN_A + norme.GG_IN_A[:12] + [72])
        for k, vals in (("cosfi", [0.8, 0.9, 1.0, 1.3]), ("L_m", [5, 30, 120, 600, 0]),
                        ("material", ["Cu", "Al"]), ("izolatie", ["PVC", "XLPE"]), ("metoda", ["C", "D1", "D2", "E"]),
                        ("n_alte", [0, 2, 8]), ("prot_tip", ["MCB", "MCCB", "gG"]), ("curba", ["B", "C", "D"]),
                        ("Ik3_origine_kA", [3, 10, 40]), ("dU_origine_pct", [0.5, 2.5, 4.0])):
            if rnd.random() < 0.3:
                p[k] = rnd.choice(vals)
        try:
            r = dimensioneaza_ramura_simpla(p)
        except Exception as e:
            pytest.fail(f"ramura simplă {i}: {type(e).__name__}: {e}\n{p}")
        if r["rezultat"] and not r["rezultat"].get("blocat"):
            verifica_ramura(r["rezultat"], r["verificari"], f"ramura simplă {i} {p}")
            assert r["text_lista"] and r["text_cablu"] and 1 <= len(r["text_desen"]) <= 3
        else:
            assert r["blocheaza"]
