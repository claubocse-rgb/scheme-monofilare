"""Runda 5 (teste/r5/industrial.md, teste/r5/locuinte.md): regresii pe intrarea fizică directă pentru tablou general,
PT, GE + ATS, locuință / branșament și desen (casetele receptoarelor)."""
import pytest

from engine import constructor, layout
from engine.calc import calculeaza


def _v(r, cod=None, nivel=None):
    return [v for v in r["verificari"] + r.get("info", []) if (cod is None or v["cod"] == cod)
            and (nivel is None or v["nivel"] == nivel)]


def _b(r):
    return [v for v in r["verificari"] if v["nivel"] == "BLOCANT"]


def _plecare(r, nume):
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


TG3 = [{"nume": "TD-1", "In_A": 32}, {"nume": "TD-2", "In_A": 32}, {"nume": "TD-3", "In_A": 32}]


# ------------------------------------------------------------------------------------------- 1. TT la tablou (#42, #47)
@pytest.mark.parametrize("ra", [20, 30])
def test_tt_tablou_ddr_pe_plecari_si_verificare_ra(ra):
    inp = {"tip_schema": "tablou", "schema_pamant": "TT", "RA_ohm": ra, "origine": "bmpt", "plecari": TG3}
    r = calculeaza(inp)
    z = r["rezultat"]
    assert not _b(r) and z["schema_pamant"] == "TT" and z["RA_ohm"] == ra
    assert all(p.get("DDR") for p in z["plecari"])
    assert z["RA_IdN_V"] <= 50 and f"RA = {ra} Ω" in z["nota_schema_pamant"].replace("\xa0", " ")
    m, _ = constructor.genereaza(inp)
    assert "TT" in m["intrari"][0]["sursa"]["sub"] and "PEN" not in m["intrari"][0]["cablu"]["cond"]
    assert sum(a["tip"] == "rccb" for a in _aparate(m)) == 3
    assert m["rp"].replace("\xa0", " ").startswith(f"RA = {ra} Ω")


def test_tt_ra_prea_mare_blocheaza():
    r = calculeaza({"tip_schema": "tablou", "schema_pamant": "TT", "RA_ohm": 2000, "origine": "bmpt", "plecari": TG3})
    assert any(v["cod"] == "V34" for v in _b(r))


def test_tt_din_tablou_existent_fara_ddr_amonte_bloc_diferential_pe_q1():
    r = calculeaza({"tip_schema": "tablou", "schema_pamant": "TT", "RA_ohm": 30, "origine": "tg_existent",
                    "plecari": TG3})
    z = r["rezultat"]
    assert not _b(r) and z["Q1_C1"].get("DDR", {}).get("reglabil") and z["IdN_amonte_mA"] is None
    assert any(v["cod"] == "V34" and v["nivel"] == "AVERTISMENT" for v in r["verificari"])


# ----------------------------------------------------------------------------------- 2. tablou monofazat (#53, #11)
def test_tablou_monofazat_2p_bare_l_n_pe_230v():
    inp = {"tip_schema": "tablou", "retea": "mono", "origine": "bmpt",
           "plecari": [{"nume": "Iluminat", "P_kW": 2}, {"nume": "Prize", "P_kW": 3}]}
    r = calculeaza(inp)
    z = r["rezultat"]
    assert not _b(r) and z["retea"] == "mono" and z["Q1_C1"]["retea"] == "mono"
    il = _plecare(r, "Iluminat")
    assert il["retea"] == "mono" and il["Ib_A"] == pytest.approx(2000 / (230 * 0.9), rel=1e-3)
    assert il["protectie"]["tip"] == "MCB" and il["protectie"]["curba"] == "B"
    m, _ = constructor.genereaza(inp)
    assert "L + N + PE" in m["bara"]["eticheta"] and "3P" not in m["bara"]["eticheta"]
    poli = {a["param"].get("poli") for a in _aparate(m) if a.get("param") and a["tip"] in ("mcb", "mccb", "rccb")}
    assert poli <= {"2P"} and poli
    assert m["intrari"][0]["cablu"]["cond"] == "L + N + PE"
    assert "MONOFAZAT" in m["cartus"]["denumire2"]


def test_tablou_monofazat_cu_plecare_trifazata_blocheaza():
    r = calculeaza({"tip_schema": "tablou", "retea": "mono", "plecari": [{"nume": "Motor", "P_kW": 4, "retea": "tri"}]})
    assert any(v["cod"] == "V12" for v in _b(r))


# ------------------------------------------------------------------------------------- 3. sursa tabloului (#41, #52)
def test_tablou_din_tgd_existent_nu_presupune_rccb_bmpt():
    inp = {"tip_schema": "tablou", "origine": "tg_existent", "Ik3_sursa_kA": 12, "L_alimentare_m": 45,
           "plecari": [{"nume": "TD-1", "In_A": 100}, {"nume": "TD-2", "In_A": 100}]}
    r = calculeaza(inp)
    assert not any("RCCB 300 mA" in p for p in r["presupus"])
    assert not _v(r, "V31") and r["rezultat"]["Q1_C1"]["Ik3max_origine_kA"] == pytest.approx(12)
    assert r["rezultat"]["sursa"].startswith("tablou existent")
    m, _ = constructor.genereaza(inp)
    assert "RCCB" not in m["intrari"][0]["sursa"]["sub"] and "existent" in m["intrari"][0]["sursa"]["sub"]


def test_tablou_origine_nedeclarata_presupusa_explicit():
    inp = {"tip_schema": "tablou", "plecari": [{"nume": "Hala", "In_A": 63}, {"nume": "Birouri", "In_A": 32}],
           "L_alimentare_m": 40, "P_kW": 80}
    r = calculeaza(inp)
    assert any(p.startswith("sursa tabloului nedeclarată") for p in r["presupus"])
    v31 = _v(r, "V31", "AVERTISMENT")
    assert v31 and all("PRESUPUS" in v["mesaj"] for v in v31)
    m, _ = constructor.genereaza(inp)
    assert "PRESUPUS" in m["intrari"][0]["sursa"]["sub"]


def test_cablu_alimentare_impus_respectat():
    r = calculeaza({"tip_schema": "tablou", "origine": "tg_existent", "In_Q1_A": 250, "L_alimentare_m": 45,
                    "cablu": {"material": "Cu", "S_fortat": 150},
                    "plecari": [{"nume": "TD-1", "In_A": 100}, {"nume": "TD-2", "In_A": 100}]})
    c1 = r["rezultat"]["Q1_C1"]
    assert c1["S_faza_mm2"] == 150 and c1["material"] == "Cu" and c1["protectie"]["In_A"] == 250


# ---------------------------------------------------------------------------------------------- 4. motoare (#15, #3)
MOTOARE = {"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 400, "schema_pamant": "TN-S",
           "plecari": [{"nume": "Pompa", "P_kW": 30, "pornire": "stea_triunghi", "L_m": 50},
                       {"nume": "Ventilator", "P_kW": 45, "pornire": "convertizor", "L_m": 35},
                       {"nume": "Strung", "P_kW": 7.5}]}


def test_motoare_aparataj_dupa_pornire():
    r = calculeaza(MOTOARE)
    assert not _b(r)
    yd = _plecare(r, "Pompa")
    am = yd["aparataj_motor"]
    assert am["pornire"] == "stea_triunghi" and am["KM2_A"] >= yd["Ib_A"] / 3 ** 0.5
    assert am["releu_termic_Ir_A"] == pytest.approx(yd["Ib_A"] / 3 ** 0.5)
    assert yd["Ip_pornire_A"] == pytest.approx(2 * yd["Ib_A"]) and yd["dU_pornire_pct"] is not None
    vfd = _plecare(r, "Ventilator")["aparataj_motor"]
    assert vfd["pornire"] == "vfd" and vfd["VFD_kW"] >= 45
    st = _plecare(r, "Strung")
    assert st["receptor"] == "motor" and st["aparataj_motor"]["pornire"] == "directa"
    assert st["Ip_pornire_A"] == pytest.approx(6 * st["Ib_A"]) and st["aparataj_motor"]["KM_A"] >= st["Ib_A"]


def test_motoare_desenate_si_in_lista():
    m, _ = constructor.genereaza(MOTOARE)
    tipuri = [a["tip"] for a in _aparate(m)]
    assert tipuri.count("contact") == 2 and tipuri.count("releu_termic") == 2
    assert "pornitor_yd" in tipuri and "convertizor" in tipuri
    den = [a["lista"][0] for a in _aparate(m) if a.get("lista")]
    assert any(d.startswith("Convertizor de frecvență") for d in den)
    assert any(d.startswith("Contactoare stea-triunghi") for d in den)
    assert any(d.startswith("Releu termic") for d in den)
    c = layout.build(m)                       # simbolurile noi se desenează
    assert c.items


# --------------------------------------------------------------------------------------------- 5. plecări (#14)
def test_n_circuite_si_iluminat_curba_b():
    inp = {"tip_schema": "tablou", "origine": "bmpt", "circuite_finale": True,
           "plecari": [{"nume": "Iluminat", "In_A": 16, "n_circuite": 5}, {"nume": "Prize", "In_A": 25, "n_circuite": 4},
                       {"nume": "Forta", "In_A": 32, "n_circuite": 2}]}
    r = calculeaza(inp)
    nume = [p["nume"] for p in r["rezultat"]["plecari"]]
    assert nume == [f"Iluminat {i}" for i in range(1, 6)] + [f"Prize {i}" for i in range(1, 5)] + ["Forta 1", "Forta 2"]
    assert all(p["protectie"]["curba"] == "B" for p in r["rezultat"]["plecari"] if p["nume"].startswith("Iluminat"))
    m, _ = constructor.genereaza(inp)
    assert len(m["plecari"]) == 11 and m["plecari"][8]["sarcina"]["titlu"] == "Prize 4"


def test_cablu_impus_pe_plecare():
    r = calculeaza({"tip_schema": "tablou", "origine": "bmpt",
                    "plecari": [{"nume": "TD-1", "In_A": 125, "L_m": 50, "cablu": {"material": "Cu", "metoda": "E", "S_fortat": 70}},
                                {"nume": "TD-2", "In_A": 63, "L_m": 30, "cablu": {"metoda": "E"}}]})
    p1, p2 = _plecare(r, "TD-1"), _plecare(r, "TD-2")
    assert p1["S_faza_mm2"] == 70 and p1["material"] == "Cu" and p1["metoda"] == "E" and p2["metoda"] == "E"


# --------------------------------------------------------------------------------------------- 6. PT (#23, #28)
def test_pt_trafo_uscat_celule_mt_masura_mt():
    inp = {"tip_schema": "pt", "Sn_kVA": 400, "trafo_izolatie": "uscat", "celule_mt": ["linie", "linie", "masura", "trafo"],
           "plecari": [{"nume": "TD-1", "In_A": 200}, {"nume": "TD-2", "In_A": 160}]}
    r = calculeaza(inp)
    z = r["rezultat"]
    assert not _b(r) and z["trafo"]["izolatie"] == "uscat" and z["trafo"]["Pk_W"] == 4500
    assert z["celule_mt"] == {"linie": 2, "masura": True} and z["masura"]["loc"] == "MT"
    m, _ = constructor.genereaza(inp)
    ap = {a["ref"]: a for a in _aparate(m)}
    assert "uscat" in " ".join(ap["T1"]["lista"]) and "ulei" not in " ".join(ap["T1"]["lista"])
    assert ap["Q1"]["buc"] == 2 and "QM" in ap
    assert "uscat" in m["carcasa"]["sub"]


def test_pt_masura_jt_explicita_si_ulei_implicit_declarat():
    r = calculeaza({"tip_schema": "pt", "Sn_kVA": 250, "masura": "JT", "plecari": [{"nume": "Ferma", "In_A": 100}]})
    assert r["rezultat"]["masura"]["loc"] == "JT" and r["rezultat"]["trafo"]["izolatie"] == "ulei"
    assert any(p.startswith("trafo în ulei") for p in r["presupus"])


def test_pt_celule_mt_invalide():
    r = calculeaza({"tip_schema": "pt", "Sn_kVA": 400, "celule_mt": ["linie", "xyz"], "plecari": [{"nume": "A", "In_A": 63}]})
    assert any(v["cod"] == "V12" for v in _b(r))


# ------------------------------------------------------------------------------------------- 7. GE + ATS (#31–#34)
def test_ge_500kva_din_pt_fara_v50():
    inp = {"tip_schema": "ge_ats", "Sn_GE_kVA": 500, "P_sarcina_kW": 380, "sursa_retea": "pt", "pt_Sn_kVA": 630,
           "L_GE_ATS_m": 15}
    r = calculeaza(inp)
    assert not _b(r) and r["rezultat"]["C2"]["L_m"] == 15 and r["rezultat"]["sursa_retea"] == "pt"
    m, _ = constructor.genereaza(inp)
    assert "PT propriu" in m["intrari"][0]["sursa"]["sub"]


def test_ge_din_tgd_existent():
    r = calculeaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 500, "P_sarcina_kW": 380, "sursa_retea": "tgd", "Ik3_sursa_kA": 20})
    assert not any(v["cod"] == "V50" for v in _b(r)) and r["rezultat"]["C1"]["Ik3max_origine_kA"] == pytest.approx(20)


def test_ge_sursa_nedeclarata_peste_250a_ramane_v50_cu_remediere():
    r = calculeaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 500, "P_sarcina_kW": 380})
    v = [x for x in _b(r) if x["cod"] == "V50"]
    assert v and "sursa_retea" in v[0]["remediere"]


def test_ge_consumatori_se_aduna_si_qr_coerent():
    r = calculeaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 250, "sursa_retea": "bmpt",
                    "consumatori": [{"nume": "Pompe incendiu", "n": 2, "P_kW": 30}, {"nume": "Iluminat siguranță", "P_kW": 3},
                                    {"nume": "Server", "P_kW": 10}]})
    z = r["rezultat"]
    assert z["Sn_GE_minim_kVA"] >= 73 / 0.9 and z["Q_retea"]["In_A"] >= 73000 / (3 ** 0.5 * 400 * 0.9)
    # sarcina luată greșit doar din primul receptor (30 kW) la GE 250 kVA → avertisment de coerență QR / ATS
    r = calculeaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 250, "P_sarcina_kW": 30, "sursa_retea": "bmpt"})
    assert any(v["cod"] == "V86" and v["nivel"] == "AVERTISMENT" for v in r["verificari"])


# --------------------------------------------------------------------------------- 8. casetele receptoarelor (P2-17)
def _suprapuneri(m):
    c = layout.build(m)
    bx = sorted([o["bbox"] for o in c.meta["obiecte"] if o["tip"] == "tablou"], key=lambda b: (round(b[1]), b[0]))
    return [(a, b) for a, b in zip(bx, bx[1:]) if abs(a[1] - b[1]) < 0.5 and a[2] > b[0] + 0.05]


@pytest.mark.parametrize("inp", [
    {"tip_schema": "pt", "Sn_kVA": 630, "plecari": [{"nume": "TD-1", "In_A": 125, "L_m": 60}, {"nume": "TD-2", "In_A": 80, "L_m": 45},
                                                    {"nume": "Compresor", "P_kW": 37, "L_m": 30}, {"nume": "Iluminat", "P_kW": 12}]},
    {"tip_schema": "pt", "Sn_kVA": 1000, "plecari": [{"nume": "TG1", "In_A": 1000, "L_m": 20}, {"nume": "TG2", "In_A": 400, "L_m": 80},
                                                     {"nume": "Iluminat exterior", "P_kW": 10, "L_m": 300}]},
    {"tip_schema": "tablou", "circuite_finale": True,
     "plecari": [{"nume": "Iluminat", "In_A": 16, "n_circuite": 5}, {"nume": "Prize", "In_A": 25, "n_circuite": 4},
                 {"nume": "Forta", "In_A": 32, "n_circuite": 2}]},
    MOTOARE,
], ids=["f01", "f22", "f14", "motoare"])
def test_casetele_receptoarelor_nu_se_suprapun(inp):
    m, _ = constructor.genereaza(inp)
    assert not _suprapuneri(m)


# ------------------------------------------------------------------------------------------- 9. locuință / branșament
def _loc(retea, circuite, **al):
    return {"tip_schema": "locuinta", "retea": retea, "alimentare": al, "circuite": circuite}


CIRC = [{"nume": "Iluminat", "receptor": "iluminat"}, {"nume": "Prize", "receptor": "prize"},
        {"nume": "Prize bucătărie", "receptor": "prize_bucatarie"}, {"nume": "Baie", "receptor": "prize_baie"}]


# r8 (proiectant): Q presupus = calibrul standard ≥ Ib la cosφ 0,95: 7 kW mono → 40 A; 11 kW tri → 20 A
@pytest.mark.parametrize("retea,pa,q", [("mono", 7, 40), ("mono", 5, 25), ("tri", 25, 40), ("tri", 15, 25), ("tri", 11, 20)])
def test_q_presupus_uzual_din_atr(retea, pa, q):
    r = calculeaza(_loc(retea, CIRC, tip="bransament_existent", P_aprobata_kW=pa))
    assert r["rezultat"]["alimentare"]["Q"]["In_A"] == q and r["rezultat"]["alimentare"]["Q_presupus"]


def test_bransament_nou_25kw_q_din_puterea_ceruta():
    c = CIRC + [{"nume": "Pompă de căldură", "receptor": "pompa_caldura", "P_kW": 12},
                {"nume": "VE", "receptor": "vehicul_electric", "P_kW": 22}]
    r = calculeaza(_loc("tri", c, tip="bransament_nou", P_aprobata_kW=25))
    assert r["rezultat"]["alimentare"]["Q"]["In_A"] == 40
    pc = [v for v in _v(r, "V46", "AVERTISMENT") if v["obiect"] == "schema"]
    assert pc and "puterea cerută" in pc[0]["mesaj"] and "Ib general se ia din puterea aprobată" not in pc[0]["mesaj"]
    assert not [v for v in _b(r) if v["cod"] == "V46"]


def test_casa_obisnuita_fara_avertismente_ddr():
    for retea, pa in (("mono", 7), ("tri", 15)):
        c = CIRC + ([{"nume": "VE", "receptor": "vehicul_electric", "P_kW": 7.4}] if retea == "tri" else [])
        r = calculeaza(_loc(retea, c, tip="bransament_existent", P_aprobata_kW=pa))
        assert not _v(r, "V43", "AVERTISMENT"), retea
        assert any("DDR-ul 300 mA din" in p for p in r["presupus"])


def test_avertismentul_ddr_ramane_cand_e_problema():
    c = CIRC + [{"nume": "VE", "receptor": "vehicul_electric", "P_kW": 7.4}]
    r = calculeaza(_loc("tri", c, tip="bransament_existent", P_aprobata_kW=15, DDR_bransament_tip="AC"))
    assert [v for v in _v(r, "V43", "AVERTISMENT") if "c.c." in v["mesaj"]]
    r = calculeaza(_loc("mono", CIRC, tip="bransament_existent", P_aprobata_kW=7, DDR_bransament_selectiv=False))
    assert _v(r, "V43", "AVERTISMENT")
