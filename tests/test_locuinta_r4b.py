"""Runda 4b (teste/r4/proiectant_b.md, teste/r4/verificator_b.md, teste/r4/ux_b.md) — SPEC §C.8 v1.6: bugetul ΔU al
coloanei (N2), coloana pe faza cea mai încărcată (m8), repartizarea pe curentul de calcul (m-n3), Q / Pa nedeclarate
(N5, m-n5), iluminatul pe niveluri (P1-4), V43 agregat (P2-1), „30 mA tip A”, protecția de rezervă SPD (N4, m-n2),
zona rurală (P1-10), chei DDR necunoscute / rețea "" (m-n4), coloana TT (N3), rezultate parțiale și câmpul `camp`
(UX 12, 13). Valorile de referință sunt calculate de mână în comentarii."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.calc import calculeaza, norme  # noqa: E402
from engine.calc.texte import text_desen, text_lista  # noqa: E402
from engine.calc.locuinta import nivel_din_nume  # noqa: E402
from engine import memoriu  # noqa: E402

L = lambda n, r, **k: dict(nume=n, receptor=r, **k)  # noqa: E731


def _v(r, cod, nivel=None):
    return [v for v in r["verificari"] + r["info"] if v["cod"] == cod and (nivel is None or v["nivel"] == nivel)]


def _circuite(z):
    return {c["nume"]: c for g in z["grupe_DDR"] for c in g["circuite"]}


def _loc(retea="mono", circuite=(), **al):
    return {"tip_schema": "locuinta", "retea": retea, "alimentare": al, "circuite": list(circuite)}


APT = _loc("mono", [L("Il", "iluminat", L_m=60), L("Pr", "prize", L_m=55)],
           In_Q_bransament_A=32, P_aprobata_kW=7, L_coloana_m=25)


# ------------------------------------------------------------------------------------------------- N2 — bugetul ΔU
def test_N2_coloana_marita_inaintea_circuitelor():
    # coloana CYABY 3×6, 25 m, Ib 32 A: ΔU = 2,45 % > 1,5 % și iluminatul de 60 m ar ieși 3×6 → coloana se mărește
    # întâi (3×10: ΔU 1,46 % ≤ 1,5 %), iluminatul rămâne la 2,5 mm² (nu 6), prizele 4 mm² (55 m, 5 % cumulat)
    r = calculeaza(APT)
    z = r["rezultat"]
    col = z["coloana"]
    assert col["S_faza_mm2"] == 10 and col["dU_ramura_pct"] <= norme.LOCUINTA_DU_COLOANA_BUGET_PCT
    mb = col["marit_buget_dU"]
    assert mb["S_initial_mm2"] == 6 and mb["dU_initial_pct"] == pytest.approx(2.45, abs=0.01) and "C1·Il" in mb["circuite"]
    c = _circuite(z)
    assert c["Il"]["S_faza_mm2"] == 2.5 and c["Il"]["dU_cumulat_pct"] <= 3.0
    assert c["Pr"]["S_faza_mm2"] == 4 and c["Pr"]["dU_cumulat_pct"] <= 5.0
    assert not r["blocheaza_export"]
    assert "buget ΔU" in memoriu.genereaza_html({"calc": APT}, r)


def test_N2_coloana_neschimbata_cand_circuitele_raman_la_minim():
    # circuite scurte: niciun circuit nu crește din cauza coloanei → coloana rămâne 3×6 (ΔU 2,45 %), fără mărire
    r = calculeaza(_loc("mono", [L("Il", "iluminat", L_m=10), L("Pr", "prize", L_m=10)],
                        In_Q_bransament_A=32, P_aprobata_kW=7, L_coloana_m=25))
    col = r["rezultat"]["coloana"]
    assert col["S_faza_mm2"] == 6 and "marit_buget_dU" not in col
    c = _circuite(r["rezultat"])
    assert c["Il"]["S_faza_mm2"] == 1.5 and c["Pr"]["S_faza_mm2"] == 2.5


def test_N2_coloana_impusa_nu_se_mareste():
    r = calculeaza(dict(APT, alimentare=dict(APT["alimentare"], cablu={"S_fortat": 6})))
    assert r["rezultat"]["coloana"]["S_faza_mm2"] == 6 and "marit_buget_dU" not in r["rezultat"]["coloana"]


# ---------------------------------------------------------------------------------------- m8 — coloana pe faza max.
def test_m8_coloana_pe_faza_cea_mai_incarcata():
    # tri, Q 40 declarat, Pa 11 kW → Ib(Pa) = 11 000/(692,82·0,95) = 16,71 A; VE mono pe L2 7,4 kW continuu = 32,17 A
    # + prize·0,8 → I_L2 ≥ 32,17 A > 16,71 → coloana poartă min(In Q 40, I_f,max)
    r = calculeaza(_loc("tri", [L("VE", "vehicul_electric", faza="L2"), L("Pr", "prize")],
                        In_Q_bransament_A=40, P_aprobata_kW=11))
    z = r["rezultat"]
    assert z["bilant"]["Ib_A"] == pytest.approx(16.71, rel=1e-3)
    assert z["coloana"]["Ib_A"] == pytest.approx(z["faze"]["I_calc_max_A"], rel=1e-6)
    assert z["coloana"]["Ib_A"] >= 32.17


# -------------------------------------------------------------------------------- m-n3 — repartizarea pe I de calcul
def test_mn3_repartizare_pe_curent_de_calcul_K02():
    # K02 (verificator): aplicația v1.5 dădea 37,05 / 37,05 / 40,24 A → Q C50; v1.6: 3F, apoi monofazatele (inclusiv
    # cele din 4P) descrescător după ks·Ib → maxim 38,31 A → Q C40 (vezi test_locuinta.test_casa_tri_15kw…)
    from test_locuinta import CASA_TRI
    z = calculeaza(CASA_TRI)["rezultat"]
    assert z["alimentare"]["Q"]["In_A"] == 40 and z["faze"]["I_calc_max_A"] < 40.24
    assert z["faze"]["dezechilibru_calc_pct"] < 2.0
    assert "curentul de calcul" in z["faze"]["repartizare"]


def test_mn3_grupe_2p_raman_pe_o_faza():
    c = [L(f"Pr{i}", "prize") for i in range(7)] + [L("Plită", "plita"), L("Cuptor", "cuptor"), L("PB", "prize_bucatarie")]
    z = calculeaza(_loc("tri", c, tip="bransament_nou"))["rezultat"]
    for g in z["grupe_DDR"]:
        fz = {x["faza"] for x in g["circuite"]}
        assert ("3F" in fz) == (g["DDR"]["poli"] == "4P")
        if "3F" not in fz:
            assert len(fz) == 1
    f = z["faze"]
    # I_calc pe faze = ks·ΣIb (fără continue); suma pe faze = ks·ΣIb·(3 la 3F)
    ks = z["bilant"]["ks"]
    tot = sum(x["Ib_A"] * (3 if x["faza"] == "3F" else 1) for x in _circuite(z).values())
    assert f["L1_calc_A"] + f["L2_calc_A"] + f["L3_calc_A"] == pytest.approx(ks * tot, rel=1e-6)


# --------------------------------------------------------------------------------------- N5 / m-n5 — Q / Pa presupuse
def test_N5_fara_q_si_fara_pa_avertismente_vizibile():
    c = [L("Il", "iluminat"), L("PC", "pompa_caldura"), L("VE", "vehicul_electric")] + [L(f"P{i}", "prize") for i in range(4)]
    r = calculeaza(_loc("tri", c))
    av = _v(r, "V46", "AVERTISMENT")
    q = [v for v in av if "Q branșament existent nedeclarat" in v["mesaj"]]
    p = [v for v in av if "puterea aprobată (ATR) nedeclarată" in v["mesaj"]]
    assert q and "presupus" in q[0]["mesaj"] and "ATR / certificatul de racordare" in q[0]["mesaj"]
    assert q[0]["camp"] == "alimentare.In_Q_bransament_A" and p and p[0]["camp"] == "alimentare.P_aprobata_kW"
    al = r["rezultat"]["alimentare"]
    assert al["Q_presupus"] and al["Pa_presupus"]
    assert any("Q presupus" in x for x in r["presupus"])


def test_mn5_blocant_pe_q_presupus_spune_ca_e_presupus():
    # N18: tri, Pa 11 kW → Q presupus 20 A (Ib 16,71 A); VE mono pe L2 32,17 A > 1,13·20 = 22,6 A → BLOCANT
    r = calculeaza(_loc("tri", [L("VE", "vehicul_electric", faza="L2"), L("Pr", "prize")], P_aprobata_kW=11))
    b = [v for v in _v(r, "V46", "BLOCANT") if v["obiect"] == "Q"]
    assert b and b[0]["mesaj"].startswith("Q branșament presupus 20 A (nedeclarat)")
    assert b[0]["remediere"].startswith("introdu Q branșament real")


def test_N5_q_declarat_fara_avertisment_q():
    r = calculeaza(_loc("mono", [L("Il", "iluminat")], In_Q_bransament_A=32, P_aprobata_kW=7))
    assert not [v for v in _v(r, "V46") if "nedeclarat" in v["mesaj"]]


def test_q_peste_bloc_nu_goleste_circuitele():
    # UX 12: Q nedeclarat cu Ib > limita BMPM 40 A → V46 BLOCANT „bloc”, dar circuitele se calculează (Q = 40 A)
    c = [L("Plită", "plita"), L("Cuptor", "cuptor"), L("Boiler", "boiler"), L("Inc", "incalzire_electrica"),
         L("Inc2", "incalzire_electrica"), L("Sauna", "sauna")]
    r = calculeaza(_loc("mono", c))
    assert any(v["obiect"] == "Q" and "limita blocului" in v["mesaj"] for v in _v(r, "V46", "BLOCANT"))
    assert r["blocheaza_export"] and len(_circuite(r["rezultat"])) == 6
    assert r["rezultat"]["alimentare"]["Q"]["In_A"] == 40


# ------------------------------------------------------------------------------------------ P1-4 — iluminat pe niveluri
def test_P14_iluminat_separat_pe_niveluri():
    c = [L("Il. parter", "iluminat"), L("Il. etaj", "iluminat"), L("Il. exterior", "iluminat"),
         L("Iluminat parter 2", "iluminat"), L("Pr", "prize")]
    z = calculeaza(_loc("mono", c, In_Q_bransament_A=40, P_aprobata_kW=9))["rezultat"]
    il = [g for g in z["grupe_DDR"] if g["grupa"] == "iluminat"]
    niv = {g["nivel"]: {x["nume"] for x in g["circuite"]} for g in il}
    assert niv == {"parter": {"Il. parter", "Iluminat parter 2"}, "etaj1": {"Il. etaj"}, "exterior": {"Il. exterior"}}
    assert all(len(g["circuite"]) <= norme.LOCUINTA_ILUMINAT_PE_DDR for g in il)


def test_P14_iluminat_fara_niveluri_max_2_pe_ddr():
    z = calculeaza(_loc("mono", [L(f"Il{i}", "iluminat") for i in range(5)], In_Q_bransament_A=32))["rezultat"]
    il = [g for g in z["grupe_DDR"] if g["grupa"] == "iluminat"]
    assert [len(g["circuite"]) for g in il] == [2, 2, 1]


@pytest.mark.parametrize("nume,niv", [("Iluminat parter", "parter"), ("Il. Etaj 2", "etaj2"), ("Lumini mansardă", "mansarda"),
                                      ("Iluminat curte", "exterior"), ("Iluminat subsol", "subsol"), ("Iluminat", None)])
def test_P14_nivel_din_nume(nume, niv):
    assert nivel_din_nume(nume) == niv


# --------------------------------------------------------------------------------------------- P2-1 — V43 agregat
def test_V43_agregat_o_singura_atentionare():
    c = [L("Il1", "iluminat"), L("Il2", "iluminat"), L("Pr", "prize"), L("PB", "prize_bucatarie")]
    r = calculeaza(_loc("mono", c, In_Q_bransament_A=32, P_aprobata_kW=7))
    v = _v(r, "V43", "AVERTISMENT")
    assert len(v) == 1 and v[0]["obiect"] == "DDR1–DDR4 vs RCBO BMPM" and "DDR1–DDR4" in v[0]["mesaj"]


# --------------------------------------------------------------------------------------------- P2-6 — „30 mA tip A”
def test_texte_30mA_tip_A():
    assert text_desen("rccb", {"poli": 2, "In_A": 40, "IdN_mA": 30, "tip_ddr": "A"})[0].endswith("30 mA tip A")
    assert text_desen("rcbo", {"In_A": 10, "curba": "B", "IdN_mA": 30, "tip_ddr": "A"})[0].endswith("30 mA tip A")
    # 300 mA (blocul de măsură) rămâne ca înainte
    assert text_desen("rccb", {"poli": 4, "In_A": 63, "IdN_mA": 300, "tip_ddr": "AC"})[0].endswith("300 mA AC")


# -------------------------------------------------------------------------------------- N4 / m-n2 — rezerva SPD
def test_SPD_protectie_rezerva():
    z = calculeaza(_loc("mono", [L("Il", "iluminat")], In_Q_bransament_A=32, P_aprobata_kW=7))["rezultat"]
    p = z["SPD"]["protectie_rezerva"]
    assert p == {"tip": "MCB", "In_A": 25, "curba": "C", "poli": "1P+N", "Icu_kA": p["Icu_kA"], "ref": "F2",
                 "text": "MCB 1P+N C25 A"}
    assert z["SPD"]["In_amonte_A"] == 25 and z["SPD"]["prot_tip"] == "MCB"
    car = text_lista("spd_ca", dict(z["SPD"], curba=z["SPD"]["curba_amonte"]))[1]
    assert car.endswith("protecție amonte MCB C25 A") and "gG" not in car
    # Q branșament 16 A → rezerva nu depășește Q: C16; trifazat → 3P+N
    z = calculeaza(_loc("tri", [L("Il", "iluminat")], In_Q_bransament_A=16))["rezultat"]
    assert z["SPD"]["protectie_rezerva"]["In_A"] == 16 and z["SPD"]["protectie_rezerva"]["poli"] == "3P+N"


def test_spd_ca_implicit_gG_neschimbat():
    assert text_lista("spd_ca", {"tip": "T2", "poli": 4, "In_amonte_A": 63})[1].endswith("protecție amonte 63 A gG")


# ------------------------------------------------------------------------------------------- P1-10 — zona rurală
def test_zona_rurala_zb_mai_mare():
    base = _loc("mono", [L("Pr", "prize", L_m=30)], In_Q_bransament_A=32, P_aprobata_kW=7)
    ru = calculeaza(dict(base, alimentare=dict(base["alimentare"], zona="rural")))
    ur = calculeaza(base)
    ik_r = _circuite(ru["rezultat"])["Pr"]["Ik1min_capat_A"]
    ik_u = _circuite(ur["rezultat"])["Pr"]["Ik1min_capat_A"]
    assert ik_r < ik_u
    assert any("0,45 Ω (zonă rurală" in p for p in ru["presupus"])
    assert any("Zbuclă OD implicită urbană |Z| = 0,201 Ω" in p for p in ur["presupus"])
    assert ru["rezultat"]["alimentare"]["zona"] == "rural"
    r = calculeaza(dict(base, alimentare=dict(base["alimentare"], zona="munte")))
    assert any(v["camp"] == "alimentare.zona" for v in _v(r, "V12", "BLOCANT"))
    # Zb declarat → zona nu contează
    r = calculeaza(dict(base, Zb_OD_ohm=0.3, alimentare=dict(base["alimentare"], zona="rural")))
    assert not any("zonă rurală" in p for p in r["presupus"])


# ----------------------------------------------------------------------------------------------------- m-n4
def test_mn4_chei_ddr_necunoscute_si_retea_goala():
    r = calculeaza(_loc("mono", [L("Pr", "prize", DDR={"IdN_mA": 30, "In_A": 10})], In_Q_bransament_A=32))
    v = [x for x in _v(r, "V12", "AVERTISMENT") if x.get("camp") == "circuite[0].DDR.In_A"]
    assert v and "nu este cunoscut" in v[0]["mesaj"] and "In_A" not in v[0]["mesaj"]
    r = calculeaza(dict(_loc("mono", [L("Pr", "prize")]), retea=""))
    assert [(v["cod"], v["obiect"]) for v in r["verificari"] if v["nivel"] == "BLOCANT"] == [("V07", "retea")]


# ----------------------------------------------------------------------------------------------------- N3 — TT
@pytest.mark.parametrize("retea,cond,cablu", [("mono", "L + N", "CYABY 2×6 mm²"), ("tri", "3L + N", "CYABY 4×6 mm²")])
def test_N3_tt_coloana_fara_pe(retea, cond, cablu):
    r = calculeaza(dict(_loc(retea, [L("Il", "iluminat")], In_Q_bransament_A=32, P_aprobata_kW=7),
                        schema_pamant="TT", RA_ohm=30))
    z = r["rezultat"]
    col = z["coloana"]
    assert col["conductoare"] == cond and col["PE"] == "fara" and col["S_PE_mm2"] is None
    assert col["PE_origine"] == "priza_locala" and col["legatura_BPE"] is False and col["cablu"] == cablu
    assert z["alimentare"]["C1_conductoare"] == cond
    # TN-C-S: PE din coloană, C1 cu PEN
    z = calculeaza(_loc(retea, [L("Il", "iluminat")], In_Q_bransament_A=32, P_aprobata_kW=7))["rezultat"]
    assert z["coloana"]["conductoare"] == cond + " + PE" and z["coloana"]["legatura_BPE"] is True
    assert z["alimentare"]["C1_conductoare"] == cond.replace("N", "PEN")


# ------------------------------------------------------------------------------------- UX 12 — rezultate parțiale
@pytest.mark.parametrize("rau,cod", [({"P_kW": 0}, "V07"), ({"P_kW": 60}, "V07"), ({"In_A": 17}, "V05"),
                                     ({"faza": "L7"}, "V12"), ({"receptor": "toaster"}, "V12")])
def test_UX12_circuit_invalid_nu_goleste_rezultatul(rau, cod):
    c = [L("Il", "iluminat"), dict(L("Rau", "prize"), **rau), L("Pr", "prize"), L("PB", "prize_bucatarie")]
    r = calculeaza(_loc("mono", c, In_Q_bransament_A=32, P_aprobata_kW=7))
    z = r["rezultat"]
    cc = _circuite(z)
    assert set(cc) == {"Il", "Rau", "Pr", "PB"} and r["blocheaza_export"]
    assert cc["Rau"]["blocat"] is True and z["circuite_blocate"] == ["C2·Rau"]
    assert all(cc[n]["blocat"] is False and cc[n]["protectie"]["In_A"] > 0 for n in ("Il", "Pr", "PB"))
    assert cc["Rau"]["protectie"]["In_A"] > 0          # desenabil (M-n1)
    assert any(v["cod"] == cod and v["obiect"] == "C2·Rau" for v in r["verificari"] if v["nivel"] == "BLOCANT")
    assert "coloana" in z and "SPD" in z


def test_UX12_rcbo_circuit_blocat_singur_in_grupa():
    # M-n1 (verificator): circuit blocat singur în grupă (RCBO) → DDR.In_A > 0, protecția circuitului completă
    r = calculeaza(_loc("mono", [L("Il", "iluminat"), L("Pr", "prize", In_A=17)], In_Q_bransament_A=32, P_aprobata_kW=7))
    g = [g for g in r["rezultat"]["grupe_DDR"] if g["circuite"][0]["nume"] == "Pr"][0]
    assert g["DDR"]["aparat"] == "RCBO" and g["DDR"]["In_A"] == 17 and g["DDR"]["Icn_kA"]
    assert g["circuite"][0]["protectie"]["tip"] == "RCBO" and "blocat" in g["circuite"][0]["protectie_defect"]


def test_UX12_alimentare_invalida_nu_goleste_circuitele():
    r = calculeaza(_loc("mono", [L("Il", "iluminat")], In_Q_bransament_A=-3, P_aprobata_kW="x", pozare_coloana="aer"))
    assert r["blocheaza_export"] and len(_circuite(r["rezultat"])) == 1
    camp = {v.get("camp") for v in r["verificari"] if v["nivel"] == "BLOCANT"}
    assert {"alimentare.In_Q_bransament_A", "alimentare.P_aprobata_kW", "alimentare.pozare_coloana"} <= camp


# ------------------------------------------------------------------------------------- UX 13 — fără chei interne
def test_UX13_mesaje_fara_chei_interne():
    r = calculeaza(_loc("mono", [L("Il", "iluminat"), L("Y", "prize", P_kW=60)], In_Q_bransament_A=-3, P_aprobata_kW=0))
    for v in r["verificari"]:
        for k in ("P_kW", "In_Q_bransament_A", "P_aprobata_kW", "alimentare."):
            assert k not in v["mesaj"] and k not in v.get("remediere", ""), v
    v = [v for v in r["verificari"] if v["obiect"] == "C2·Y"][0]
    assert v["camp"] == "circuite[1].P_kW" and "puterea circuitului" in v["mesaj"]
    v = [v for v in r["verificari"] if v.get("camp") == "alimentare.In_Q_bransament_A" and v["nivel"] == "BLOCANT"][0]
    assert "Q branșament" in v["mesaj"]
