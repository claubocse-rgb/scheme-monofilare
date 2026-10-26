"""Runda 7 (teste/r7/industrial.md, teste/r7/locuinte.md): motoare (η/cosφ IE3), tablou de pompe de incendiu, PT cu
2 trafo și cuplă, Q1 vs iluminat, bugetul ΔU al alimentării, cablu impus în paralel, planșa blocată, locuință (VE peste
P aprobată, TT fără PEN, GE de rezervă, TC), tensiuni JT nesuportate."""
import pytest

from engine import constructor, layout, render_svg
from engine.calc import calculeaza, norme


def _b(r):
    return [v for v in r["verificari"] if v["nivel"] == "BLOCANT"]


def _pl(r, nume):
    return next(p for p in r["rezultat"]["plecari"] if p["nume"] == nume)


def _aparate(m):
    out = []

    def walk(bs):
        for b in bs:
            out.extend(b.get("aparate") or [])
            walk(b.get("copii") or [])
    for i in m.get("intrari") or []:
        out.extend(i.get("aparate") or [])
    walk(m.get("plecari") or [])
    return out


# ------------------------------------------------------------------------------------------- 1. motoare (S8)
@pytest.mark.parametrize("p,i_min,i_max", [(15, 27.0, 29.5), (55, 96.0, 101.0), (75, 130.0, 140.0)])
def test_in_motor_cu_randament_si_cosfi(p, i_min, i_max):
    r = calculeaza({"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 1000,
                    "plecari": [{"nume": "Pompa", "P_kW": p}]})
    z = _pl(r, "Pompa")
    eta, cos = norme.motor_eta_cosfi(p)
    assert z["Ib_A"] == pytest.approx(p * 1000 / (3 ** 0.5 * 400 * eta * cos), rel=1e-6)
    assert i_min <= z["Ib_A"] <= i_max
    assert z["aparataj_motor"]["releu_termic_Ir_A"] == pytest.approx(z["Ib_A"])     # termic la In real
    assert any("IE3" in t for t in r["presupus"])


def test_randament_declarat_are_prioritate():
    r = calculeaza({"tip_schema": "tablou", "plecari": [{"nume": "Pompa", "P_kW": 15, "randament": 0.95, "cosfi": 0.9}]})
    assert _pl(r, "Pompa")["Ib_A"] == pytest.approx(15000 / (3 ** 0.5 * 400 * 0.95 * 0.9), rel=1e-6)


def test_compresoare_plural_au_demaror_nu_gg_sub_in():
    inp = {"tip_schema": "pt", "Sn_kVA": 1000, "U_MT_kV": 6, "plecari": [
        {"nume": "Compresoare 1", "P_kW": 75}, {"nume": "Compresoare 2", "P_kW": 75}, {"nume": "Iluminat", "P_kW": 30}]}
    r = calculeaza(inp)
    for n in ("Compresoare 1", "Compresoare 2"):
        z = _pl(r, n)
        assert z["protectie"]["tip"] == "MCCB" and z["protectie"]["Ir_A"] >= z["Ib_A"] > 125
        am = z["aparataj_motor"]
        assert am["KM_A"] >= z["Ib_A"] and am["releu_termic_Ir_A"] == pytest.approx(z["Ib_A"])
    m, _ = constructor.genereaza(inp)
    tipuri = [a.get("tip") for a in _aparate(m)]
    assert tipuri.count("releu_termic") == 2 and tipuri.count("contact") == 2


def test_motoare_in_tablou_de_circuite_finale_au_km_si_termic():
    r = calculeaza({"tip_schema": "tablou", "circuite_finale": True, "origine": "tg_existent", "plecari": [
        {"nume": "Iluminat", "P_kW": 1, "n_circuite": 2}, {"nume": "Motoare 1", "P_kW": 4}, {"nume": "Motoare 2", "P_kW": 4}]})
    for n in ("Motoare 1", "Motoare 2"):
        am = _pl(r, n)["aparataj_motor"]
        assert am["KM_A"] >= 9 and am["releu_termic_Ir_A"] > 7.5


# ------------------------------------------------------------------------------- 2. pompe de incendiu (P0 #31)
POMPE = {"tip_schema": "ge_ats", "Sn_GE_kVA": 150, "P_sarcina_kW": 92.2, "siguranta_tablou": True,
         "consumatori": [{"nume": "Pompa principala", "P_kW": 45}, {"nume": "Pompa rezerva", "P_kW": 45},
                         {"nume": "Pompa pilot", "P_kW": 2.2}]}


@pytest.mark.parametrize("cheie", [{"siguranta_tablou": True}, {"titlu_tablou": "Tablou pompe incendiu retea si GE"}])
def test_tablou_pompe_incendiu_fara_ddr_rezerva_neadunata(cheie):
    inp = {k: v for k, v in POMPE.items() if k != "siguranta_tablou"}
    inp.update(cheie)
    r = calculeaza(inp)
    z = r["rezultat"]
    assert "DDR" not in z["Q_G"] and z["Q_G"].get("RCM")
    ps = z["plecari_siguranta"]
    assert len(ps) == 3 and all(p.get("DDR") is None and p["rezistent_foc"] for p in ps)
    assert [p.get("rezerva", False) for p in ps] == [False, True, False]
    assert z["Sn_GE_minim_kVA"] <= 60            # 45 + 2,2 kW, nu 92,2 kW
    m, _ = constructor.genereaza(inp)
    assert not any(a.get("tip") == "rccb" for a in _aparate(m))
    assert all("FE180" in i["cablu_ca"]["text"] for i in m["intrari"])
    assert all("FE180" in p["cablu"]["text"] for p in m["plecari"])
    assert m["carcasa"]["titlu"] == "TPI" and "REZERVĂ" in m["plecari"][1]["sarcina"]["sub"]


def test_n_1_plus_1_rezerva():
    r = calculeaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 100, "siguranta_tablou": True,
                    "consumatori": [{"nume": "Pompa", "P_kW": 30, "n": "1+1"}]})
    assert r["rezultat"]["consumatori"] and len(r["rezultat"]["plecari_siguranta"]) == 2
    assert any("30 kW" in p or "rezervă" in p for p in r["presupus"])


# ---------------------------------------------------------------------------------------- 3. PT cu 2 trafo (S12)
PT2 = {"tip_schema": "pt", "Sn_kVA": 1000, "n_trafo": 2, "plecari_pe_sectie": True,
       "plecari": [{"nume": f"TD-{k}", "In_A": 250} for k in range(1, 5)]}


def test_pt_2_trafo_8_plecari_cupla_no():
    r = calculeaza(PT2)
    z = r["rezultat"]
    assert not _b(r) and z["cupla"]["stare"] == "NO"
    top = [p for p in z["plecari"] if p["nivel"] == 0]
    assert [p["nume"] for p in top] == [f"TD-{k}" for k in range(1, 9)]
    assert [p["sectie"] for p in top] == [1] * 4 + [2] * 4
    unu = calculeaza(dict(PT2, n_trafo=1))["rezultat"]
    assert z["Ik3max_bara_kA"] == pytest.approx(unu["trafo"]["Ik3max_bara_kA"])     # NO: un trafo pe secție
    m, _ = constructor.genereaza(PT2)
    assert len(m["plecari"]) == 9                                     # 8 + servicii proprii
    assert m["bara"]["cupla"]["n1"] == 5 and m["bara"]["cupla"]["aparat"]["ref"] == "QC"
    assert "NO" in m["bara"]["cupla"]["aparat"]["spec"][1]
    assert m["intrari"][1].get("ramificatie") and "BARA MT" not in str(m["intrari"][1].get("sursa"))
    cv = layout.build(m)
    assert render_svg.render(cv, "t").startswith("<svg")
    from engine.topologie import coliziuni
    assert coliziuni(cv) == []


def test_pt_2_trafo_cupla_inchisa_paralel_si_sectii_explicite():
    inp = dict(PT2, cupla="inchisa", plecari_pe_sectie=False,
               plecari=[{"nume": "A", "In_A": 400, "sectie": 2}, {"nume": "B", "In_A": 400, "sectie": 1}])
    r = calculeaza(inp)
    z = r["rezultat"]
    assert z["cupla"]["stare"] == "NI" and z["Ik3max_bara_kA"] > 1.6 * calculeaza(dict(inp, n_trafo=1))["rezultat"]["trafo"]["Ik3max_bara_kA"]
    assert [p["nume"] for p in z["plecari"] if p["nivel"] == 0] == ["B", "A"]
    assert any(v["cod"] == "V12" for v in _b(calculeaza(dict(PT2, cupla="xyz"))))


# --------------------------------------------------------------------- 4. Q1 vs iluminat (ks = 1, faze) (#40)
def test_q1_pe_iluminat_ks1_si_faza_max():
    r = calculeaza({"tip_schema": "tablou", "origine": "tg_existent", "schema_pamant": "TN-S", "circuite_finale": True,
                    "plecari": [{"nume": "Iluminat", "P_kW": 1.2, "n_circuite": 12, "retea": "mono"}]})
    z = r["rezultat"]
    assert z["bilant"]["Pc_kW"] == pytest.approx(14.4)
    assert z["Q1_C1"]["protectie"]["In_A"] >= 25 and z["Q1_C1"]["Ib_A"] >= 20.7
    assert z["Q1_C1"]["protectie"]["In_A"] >= max(p["protectie"]["In_A"] for p in z["plecari"])


# ---------------------------------------------------------- 5. alimentarea nu mai iese absurdă la puteri mici (#12)
def test_chiosc_mono_alimentare_fara_sectiune_absurda():
    r = calculeaza({"tip_schema": "tablou", "origine": "bmpt", "retea": "mono", "plecari": [
        {"nume": "Frigider", "P_kW": 1}, {"nume": "Aer conditionat", "P_kW": 2.5}, {"nume": "Iluminat", "P_kW": 0.5},
        {"nume": "Prize", "P_kW": 2}, {"nume": "TD-5", "P_kW": 6, "retea": "mono"}]})
    c1 = r["rezultat"]["Q1_C1"]
    assert not _b(r) and c1["S_faza_mm2"] <= 50 and c1["protectie"]["In_A"] == 50


# ----------------------------------------------------------------- 6. cablu impus în paralel + planșa blocată (#7, #18)
def test_cablu_impus_n_paralel_respectat():
    r = calculeaza({"tip_schema": "tablou", "origine": "tg_existent", "schema_pamant": "TN-S", "h3_pct": 10,
                    "cablu": {"S_fortat": 240, "N_fortat": 120, "material": "Al", "n_paralel": 2},
                    "plecari": [{"nume": "Chiller", "P_kW": 180}, {"nume": "CTA", "P_kW": 15}]})
    c1 = r["rezultat"]["Q1_C1"]
    assert c1["n_paralel"] == 2 and c1["S_faza_mm2"] == 240
    assert not any(v["cod"] in ("V02", "V03") for v in _b(r))


def test_lungimea_plecarii_ramane_pe_plecare():
    r = calculeaza({"tip_schema": "tablou", "origine": "tg_existent", "L_alimentare_m": 10,
                    "plecari": [{"nume": "Pompa", "P_kW": 30, "L_m": 120, "cablu": {"material": "Cu", "S_fortat": 6}}]})
    assert _pl(r, "Pompa")["L_m"] == 120 and r["rezultat"]["Q1_C1"]["L_m"] == 10


def test_plansa_blocata_are_stampila_si_nota():
    inp = {"tip_schema": "tablou", "origine": "tg_existent", "L_alimentare_m": 10,
           "plecari": [{"nume": "Pompa", "P_kW": 30, "L_m": 120, "cablu": {"material": "Cu", "S_fortat": 6}}]}
    m, r = constructor.genereaza(inp)
    assert _b(r) and m["blocaj"].startswith("NEVERIFICAT") and m["note"][0].startswith("0. ATENȚIE")
    cv = layout.build(m)
    assert cv.meta.get("blocaj") and "NEVERIFICAT" in render_svg.render(cv, "t")


# ---------------------------------------------------------------------------------------------- 7. locuință
def test_wallbox_22kw_pe_mono_7kw_blocant_cu_intrebare():
    r = calculeaza({"tip_schema": "locuinta", "retea": "mono", "alimentare": {"P_aprobata_kW": 7}, "circuite": [
        {"nume": "Iluminat", "receptor": "iluminat"}, {"nume": "Încărcare VE", "receptor": "vehicul_electric", "P_kW": 22}]})
    b = [v for v in _b(r) if "VE" in v["obiect"]]
    assert b and any("trifazat" in v["remediere"] for v in b) and all(v.get("intrebare") for v in b)


def test_bransament_tt_fara_pen():
    m, r = constructor.genereaza({"tip_schema": "bransament", "retea": "mono", "schema_pamant": "TT", "P_kW": 5})
    i = m["intrari"][0]
    assert "PEN" not in i["cablu"]["cond"]
    bn = i["aparate"][0]["laterale"][0]
    assert bn["fara_legatura"] and "PEN →" not in bn["nota"]


def test_ge_rezerva_locuinta_sursa_nu_consumator():
    inp = {"tip_schema": "locuinta", "retea": "tri", "ge_rezerva": {"Sn_kVA": 5, "comutare": "manual"},
           "alimentare": {"P_aprobata_kW": 11, "In_Q_bransament_A": 16},
           "circuite": [{"nume": "Iluminat", "receptor": "iluminat"}, {"nume": "Prize", "receptor": "prize"}]}
    r = calculeaza(inp)
    g = r["rezultat"]["ge_rezerva"]
    assert g["comutare"] == "manual" and g["comutator_In_A"] >= 16 and g["poli"] == "4P"
    assert r["rezultat"]["bilant"]["Pi_kW"] < 11                     # GE nu e adunat la consumatori
    m, _ = constructor.genereaza(inp)
    assert len(m["intrari"]) == 2 and m["intrari"][1]["sursa"]["titlu"] == "GRUP ELECTROGEN"
    assert {a.get("ref") for a in _aparate(m)} >= {"K·I", "K·II", "Q-GE", "G"}
    assert any(v["cod"] == "V07" for v in _b(calculeaza(dict(inp, ge_rezerva={"Sn_kVA": 5, "comutare": "x"}))))


def test_tc_primar_cu_rezerva_si_semnalare_masura_casa():
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 90, "L_coloana_m": 35})
    z = r["rezultat"]
    assert z["TC_primar_A"] >= 1.2 * z["Ib_A"] or z["TC_primar_A"] == 250
    r = calculeaza({"tip_schema": "locuinta", "retea": "tri", "alimentare": {"P_aprobata_kW": 55},
                    "circuite": [{"nume": "Iluminat", "receptor": "iluminat"}, {"nume": "Pompa caldura", "receptor": "pompa_caldura", "P_kW": 25},
                                  {"nume": "Incalzire", "receptor": "incalzire_electrica", "P_kW": 25}]})
    assert any(v["cod"] == "V56" and "semidirect" in v["mesaj"] for v in r["verificari"])


def test_tablou_secundar_locuinta_circuite_doar_cu_nume():
    r = calculeaza({"tip_schema": "locuinta", "retea": "tri", "alimentare": {"P_aprobata_kW": 20},
                    "circuite": [{"nume": "Iluminat", "receptor": "iluminat"}],
                    "tablouri_secundare": [{"nume": "TD garaj", "L_m": 30, "circuite": [
                        {"nume": "Compresor"}, {"nume": "Iluminat garaj"}, {"nume": "Prize garaj"}]}]})
    assert not any(v["cod"] == "V07" for v in _b(r))
    assert sum("TD garaj" in p for p in r["presupus"]) >= 3


# ------------------------------------------------------------------------------------- 8. tensiuni nesuportate
@pytest.mark.parametrize("inp", [
    {"tip_schema": "tablou", "U_V": 690, "plecari": [{"nume": "Motor", "P_kW": 250}]},
    {"tip_schema": "pt", "Sn_kVA": 630, "U_JT_V": 690, "plecari": [{"nume": "TD", "In_A": 400}]},
    {"tip_schema": "ge_ats", "Sn_GE_kVA": 100, "P_sarcina_kW": 50, "U_V": 690},
    {"tip_schema": "bransament", "retea": "tri", "P_kW": 20, "U_V": "500"},
    {"tip_schema": "tablou", "plecari": [{"nume": "Motor", "P_kW": 250, "U_V": 690}]},
])
def test_tensiune_jt_nesuportata_blocant(inp):
    assert any(v["cod"] == "V96" and "690" in v["mesaj"] or "500" in v["mesaj"] for v in _b(calculeaza(inp)))


def test_400_230_v_acceptate():
    assert not _b(calculeaza({"tip_schema": "tablou", "U_V": 400, "plecari": [{"nume": "Pompa", "P_kW": 5}]}))
