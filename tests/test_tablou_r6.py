"""Runda 6 (teste/r6/industrial.md, teste/r6/locuinte.md): tablou / PT / GE + ATS / locuință / branșament — motor,
constructor și desen."""
import pytest

from engine import constructor, layout, render_svg
from engine.calc import calculeaza


def _v(r, cod=None, nivel=None):
    return [v for v in r["verificari"] + r.get("info", []) if (cod is None or v["cod"] == cod)
            and (nivel is None or v["nivel"] == nivel)]


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


def _svg(m):
    return render_svg.render(layout.build(m), "t")


# ------------------------------------------------------------------------- 1. secțiuni absurde pe circuite mici (#17, #4)
@pytest.mark.parametrize("inp", [
    {"tip_schema": "tablou", "retea": "mono", "plecari": [{"nume": "Iluminat", "P_kW": 1.5}, {"nume": "Prize", "P_kW": 2},
                                                          {"nume": "Centrala", "P_kW": 0.2}, {"nume": "Pompa caldura", "P_kW": 9}]},
    {"tip_schema": "tablou", "retea": "mono", "origine": "tg_existent", "L_alimentare_m": 25,
     "plecari": [{"nume": "Iluminat", "In_A": 10}, {"nume": "Prize", "In_A": 16}, {"nume": "AC 1", "P_kW": 3.5}]}])
def test_circuite_mici_fara_sectiuni_absurde(inp):
    r = calculeaza(inp)
    assert not _b(r)
    for p in r["rezultat"]["plecari"]:
        if p["Ib_A"] <= 20:
            assert p["material"] == "Cu" and p["S_faza_mm2"] <= 10, (p["nume"], p["cablu"])
    # alimentarea a lăsat buget plecărilor: ΔU alimentare ≤ 3 % − 1 %
    assert r["rezultat"]["Q1_C1"]["dU_ramura_pct"] <= 2.0 + 1e-6


# ------------------------------------------------------------------- 2. motoare DOL ≥ 18,5 kW: întrerupător-motor, nu MCB C
def test_motor_dol_mare_in_td_pe_intrerupator_motor():
    inp = {"tip_schema": "tablou", "retea": "tri", "origine": "pt_propriu", "pt_Sn_kVA": 400,
           "plecari": [{"nume": "TD-1", "In_A": 160, "L_m": 70, "copii": [
               {"nume": "Pompa", "P_kW": 30, "receptor": "motor"}, {"nume": "Compresor", "P_kW": 18.5, "receptor": "motor"},
               {"nume": "Ventilator mic", "P_kW": 4, "receptor": "motor"}]}]}
    r = calculeaza(inp)
    for n in ("Pompa", "Compresor"):
        p = _pl(r, n)
        pr = p["protectie"]
        assert pr["tip"] == "MCCB" and pr.get("intrerupator_motor"), (n, pr)
        assert 0.8 * pr["Im_A"] >= 2.0 * p["Ip_pornire_A"] - 1e-6        # vârful asimetric la pornire
        assert p["aparataj_motor"]["KM_A"] >= p["Ib_A"] and p["aparataj_motor"]["releu_termic_Ir_A"] == p["Ib_A"]
    assert _pl(r, "Ventilator mic")["protectie"]["tip"] == "MCB"          # sub 18,5 kW rămâne MCB
    m, _ = constructor.genereaza(inp)
    assert any("Întreruptor-motor" in (a.get("lista") or [""])[0] for a in _aparate(m))


# ------------------------------------------------------------------------------- 3. GE: pompe de incendiu, GE în paralel
GE_INC = {"tip_schema": "ge_ats", "Sn_GE_kVA": 200, "sursa_retea": "pt", "pt_Sn_kVA": 400,
          "consumatori": [{"nume": "Pompa incendiu", "P_kW": 45, "n": 2, "pornire": "stea_triunghi"},
                          {"nume": "Hidrofor", "P_kW": 7.5}]}


def test_ge_pompe_incendiu_fara_ddr():
    r = calculeaza(dict(GE_INC))
    z = r["rezultat"]
    assert not _b(r)
    assert "DDR" not in z["Q_G"] and z["Q_G"]["RCM"]["IdN_mA"] == 300          # fără DDR-G; doar RCM (alarmă)
    ps = z["plecari_siguranta"]
    assert [p["nume"] for p in ps] == ["Pompa incendiu 1", "Pompa incendiu 2"]
    assert all(not p.get("DDR") and p["siguranta"] and p["aparataj_motor"]["pornire"] == "stea_triunghi" for p in ps)
    assert z["C3"].get("DDR", {}).get("IdN_mA") == 300 and z["C3"]["DDR"]["selectiv"]   # consumatorii normali: DDR S
    assert _v(r, "V97", "AVERTISMENT")
    m, _ = constructor.genereaza(dict(GE_INC))
    assert not any(a.get("ref") == "DDR-G" for a in _aparate(m))
    texte = [p["cablu"]["text"] for p in m["plecari"]]
    assert sum("NHXH FE180/E90" in t for t in texte) == 2
    assert "RCM" in _svg(m)


@pytest.mark.parametrize("cons", [[{"nume": "Hidranti interiori", "P_kW": 15}], [{"nume": "Sprinklere", "P_kW": 30, "siguranta": True}]])
def test_ge_siguranta_dupa_nume_sau_cheie(cons):
    r = calculeaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 100, "sursa_retea": "pt", "pt_Sn_kVA": 250, "consumatori": cons})
    assert r["rezultat"].get("plecari_siguranta") and "DDR" not in r["rezultat"]["Q_G"]


def test_ge_siguranta_toata_sarcina():
    r = calculeaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 100, "P_sarcina_kW": 50, "siguranta": True})
    assert r["rezultat"]["plecari_siguranta"] and "C3" not in r["rezultat"] and not _b(r)


def test_ge_in_paralel_avertisment_explicit():
    inp = {"tip_schema": "ge_ats", "Sn_GE_kVA": 250, "ge_paralel": True, "sursa_retea": "pt", "pt_Sn_kVA": 630}
    r = calculeaza(inp)
    v = _v(r, "V96", "AVERTISMENT")
    assert v and "paralel" in v[0]["mesaj"] and "nesuportat" in v[0]["mesaj"]
    m, _ = constructor.genereaza(inp)
    assert "NESUPORTAT" in m["intrari"][1]["sursa"]["sub"]


# -------------------------------------------------------------------------------------- 4. sursa TG nedeclarată, lizibilă
def test_sursa_nedeclarata_pe_doua_randuri_lizibil():
    m, _ = constructor.genereaza({"tip_schema": "tablou", "plecari": [{"nume": "TD-1", "In_A": 32}]})
    sub = m["intrari"][0]["sursa"]["sub"]
    assert "PRESUPUS" in sub and sub.count("PRESUPUS") == 1
    svg = _svg(m)
    assert "SURSĂ NEDECLARATĂ — PRESUPUS" in svg
    import re
    fonturi = [float(x) for x in re.findall(r'font-size="([\d.]+)"[^>]*>[^<]*(?:PRESUPUS|prin BMPT)', svg)]
    if fonturi:     # textul nu mai e micșorat sub ~1,8 mm (relativ la celelalte texte)
        assert min(fonturi) >= 0.8 * max(fonturi)


# ------------------------------------------------------------------------------------------- 5. locuință / branșament
def _loc(retea, circ, **al):
    return {"tip_schema": "locuinta", "retea": retea, "alimentare": al, "circuite": circ}


C = [{"nume": "Iluminat", "receptor": "iluminat"}, {"nume": "Prize camere", "receptor": "prize"},
     {"nume": "Prize bucătărie", "receptor": "prize_bucatarie"}, {"nume": "Prize baie", "receptor": "prize_baie"},
     {"nume": "Mașină de spălat rufe", "receptor": "masina_spalat_rufe"}]


@pytest.mark.parametrize("retea,pa", [("mono", 2), ("mono", 3), ("mono", 4), ("tri", 11)])
def test_q_presupus_nu_blocheaza_case_banale(retea, pa):
    r = calculeaza(_loc(retea, C, P_aprobata_kW=pa))
    assert not [v for v in _b(r) if v["cod"] in ("V46", "V40")], _b(r)
    z = r["rezultat"]
    # Q presupus = perechea ATR (Pa = U·In, cosφ 1); poate fi ușor sub Ib la cosφ 0,95 — convenția ATR
    assert z["alimentare"]["Q_presupus"] and z["alimentare"]["Q"]["In_A"] * 1.13 >= z["bilant"]["Ib_A"] - 1e-9


def test_q_presupus_treapta_peste_ib():
    r = calculeaza(_loc("tri", C, P_aprobata_kW=11))
    assert r["rezultat"]["alimentare"]["Q"]["In_A"] == 16                     # perechea ATR 11 kW tri ↔ 16 A (r6b, DECIZIE)


def test_q_declarat_ramane_blocant():
    c = C + [{"nume": "VE", "receptor": "vehicul_electric", "P_kW": 7.4, "faza": "L1"}]
    r = calculeaza(_loc("tri", c, P_aprobata_kW=11, In_Q_bransament_A=16))
    assert any(v["cod"] in ("V46", "V40") for v in _b(r))


def test_bransament_bmpm32_7kw_nu_blocheaza():
    inp = {"tip_schema": "bransament", "retea": "mono", "P_kW": 7, "Q_In_A": 32, "L_coloana_m": 20}
    r = calculeaza(inp)
    assert not _b(r) and r["rezultat"]["bloc"] == "BMPM-32"
    v = _v(r, "V04", "AVERTISMENT")
    assert v and "cosφ 1" in v[0]["mesaj"]
    assert r["rezultat"]["Q"]["selectiv"] is True                               # RCBO 300 mA S (V43 evitat)
    m, _ = constructor.genereaza(inp)
    q = next(a for a in _aparate(m) if a.get("ref") == "Q")
    assert "selectiv (S)" in q["lista"][0]
    # Q 25 A cu 7 kW rămâne BLOCANT (Ib ATR 30,4 A > 25 A)
    assert _b(calculeaza(dict(inp, Q_In_A=25)))


def test_repartizare_faze_dezechilibru_mic():
    c = [{"nume": "Iluminat interior", "receptor": "iluminat"}, {"nume": "Iluminat exterior", "receptor": "iluminat"},
         {"nume": "Prize camere", "receptor": "prize"}, {"nume": "Prize living", "receptor": "prize"},
         {"nume": "Prize bucătărie", "receptor": "prize_bucatarie"}, {"nume": "Prize baie", "receptor": "prize_baie"},
         {"nume": "Mașină de spălat rufe", "receptor": "masina_spalat_rufe"}, {"nume": "Boiler", "receptor": "boiler"},
         {"nume": "Centrală termică", "receptor": "centrala_termica"}, {"nume": "Prize exterior", "receptor": "prize_exterior"}]
    r = calculeaza(dict(_loc("tri", c, P_aprobata_kW=15, In_Q_bransament_A=25, L_coloana_m=20), schema_pamant="TT", RA_ohm=20))
    assert r["rezultat"]["faze"]["dezechilibru_pct"] <= 30.0
    assert not _v(r, "V47")


def test_ve_tip_a_rdc_dd_desenat():
    c = C + [{"nume": "Stație VE", "receptor": "vehicul_electric", "P_kW": 7.4}]
    m, _ = constructor.genereaza(_loc("tri", c, P_aprobata_kW=15, In_Q_bransament_A=32))
    ve = [b for p in m["plecari"] for b in (p.get("copii") or [p]) if b["sarcina"]["titlu"] == "Stație VE"]
    assert ve and "RDC-DD 6" in ve[0]["sarcina"]["sub"]
    assert any(x["ref"] == "RDC-DD" for x in m["materiale"])
    assert "RDC-DD" in _svg(m)


# ------------------------------------------------------------------------------ 6. date nesuportate: IT, MT, 2 trafo, GE mono
def test_schema_it_blocant():
    r = calculeaza({"tip_schema": "tablou", "schema_pamant": "IT", "plecari": [{"nume": "TD-1", "In_A": 63}]})
    assert any(v["cod"] == "V28" for v in _b(r))


def test_pt_6kv_parametric():
    inp = {"tip_schema": "pt", "Sn_kVA": 630, "U_MT_kV": 6, "plecari": [{"nume": "TD-1", "In_A": 400}]}
    r = calculeaza(inp)
    assert not _b(r) and r["rezultat"]["U_MT_kV"] == 6 and r["rezultat"]["Um_kV"] == 7.2
    assert "125" in r["rezultat"]["celula_trafo"]                              # 2·In_MT (60,6 A) → SF 125 A, nu 40 A
    m, _ = constructor.genereaza(inp)
    svg = _svg(m)
    assert "LES 6 kV" in svg and "6/0,4" in svg and "24 kV" not in svg.replace(" ", " ")


@pytest.mark.parametrize("u", [35, 0.4, "abc"])
def test_pt_tensiune_mt_nesuportata(u):
    r = calculeaza({"tip_schema": "pt", "Sn_kVA": 630, "U_MT_kV": u, "plecari": [{"nume": "TD-1", "In_A": 400}]})
    assert any(v["cod"] == "V96" and "nesuportat" in v["mesaj"] for v in _b(r))


def test_pt_2x630_doi_trafo_in_paralel():
    inp = {"tip_schema": "pt", "Sn_kVA": 630, "n_trafo": 2, "cupla": "inchisa",     # r7: paralel doar declarat
           "plecari": [{"nume": "TG1", "In_A": 800, "L_m": 30}, {"nume": "TG2", "In_A": 800, "L_m": 40}]}
    r = calculeaza(inp)
    z = r["rezultat"]
    unu = calculeaza(dict(inp, n_trafo=1))["rezultat"]
    assert not _b(r) and z["n_trafo"] == 2
    assert z["Ik3max_bara_kA"] > 1.6 * unu["trafo"]["Ik3max_bara_kA"]           # Icu pe Ik3 cu ambele trafo
    assert not _v(r, "V62")                                                     # Sc ≤ 2 × 630 kVA
    m, _ = constructor.genereaza(inp)
    assert len(m["intrari"]) == 2 and {"T1", "T2"} <= {a.get("ref") for a in _aparate(m)}
    assert "cuplă" in m["bara"]["eticheta"] and "2 × 630" in m["carcasa"]["titlu"]
    assert any(v["cod"] == "V96" for v in _b(calculeaza(dict(inp, n_trafo=3))))


def test_ge_monofazat_nesuportat():
    r = calculeaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 40, "retea": "mono", "P_sarcina_kW": 25})
    assert any(v["cod"] == "V96" and "monofazat" in v["mesaj"] for v in _b(r))


# ------------------------------------------------------------------------------ 7. tablou secundar din TE (atelier)
TD = {"nume": "TD atelier", "L_m": 40, "circuite": [
    {"nume": "Strung", "P_kW": 4, "pornire": "directa"}, {"nume": "Compresor", "P_kW": 3, "receptor": "motor"},
    {"nume": "Iluminat atelier", "P_kW": 0.5}, {"nume": "Prize atelier", "In_A": 16, "n_circuite": 2}]}


@pytest.mark.parametrize("retea", ["tri", "mono"])
def test_locuinta_cu_tablou_secundar(retea):
    inp = dict(_loc(retea, C, P_aprobata_kW=15 if retea == "tri" else 9), tablouri_secundare=[TD])
    r = calculeaza(inp)
    circ = [c for g in r["rezultat"]["grupe_DDR"] for c in g["circuite"]]
    f = next(c for c in circ if c["nume"] == "TD atelier")
    assert f["receptor"] == "tablou_secundar" and f["L_m"] == 40
    td = f["tablou_secundar"]
    assert [p["nume"] for p in td["plecari"]] == ["Strung", "Compresor", "Iluminat atelier", "Prize atelier 1", "Prize atelier 2"]
    assert all(p.get("DDR") for p in td["plecari"] if p["nume"].startswith("Prize"))
    assert _pl({"rezultat": td}, "Strung").get("aparataj_motor")
    assert not [v for v in _b(r) if "TD atelier" in v["obiect"]]
    m, _ = constructor.genereaza(inp)
    def toate(bs):
        for b in bs:
            yield b
            yield from toate(b.get("copii") or [])
    tdm = [b for b in toate(m["plecari"]) if (b.get("sarcina") or {}).get("titlu") == "TD atelier"]
    assert tdm and len(tdm[0]["copii"]) == 5
    _svg(m)


def test_tablou_secundar_fara_circuite_blocant():
    r = calculeaza(dict(_loc("tri", C, P_aprobata_kW=15), tablouri_secundare=[{"nume": "Garaj", "circuite": []}]))
    assert any(v["cod"] == "V07" for v in _b(r))


# ------------------------------------------------------------------------------------ 8. compensare (kvar)
@pytest.mark.parametrize("tip", ["tablou", "pt"])
def test_compensare_kvar(tip):
    pl = [{"nume": "TD-1", "In_A": 250}, {"nume": "TD-2", "In_A": 160}]
    inp = ({"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 630, "compensare_kvar": 120, "plecari": pl}
           if tip == "tablou" else {"tip_schema": "pt", "Sn_kVA": 630, "compensare_kvar": 120, "plecari": pl})
    r = calculeaza(inp)
    z = r["rezultat"]
    bc = next(p for p in z["plecari"] if p.get("compensare"))
    assert bc["In_cap_A"] == pytest.approx(120000 / (3 ** 0.5 * 400), rel=1e-6)
    assert bc["protectie"]["In_A"] >= 1.43 * bc["In_cap_A"] and bc["Iz_corectat_A"] >= 1.43 * bc["In_cap_A"]
    fara = calculeaza(dict(inp, compensare_kvar=None))["rezultat"]
    assert z["bilant"]["Pi_kW"] == pytest.approx(fara["bilant"]["Pi_kW"])       # bateria nu intră în bilanțul P
    assert _v(r, "V98")
    m, _ = constructor.genereaza(inp)
    assert any("Baterie condensatoare 120 kvar" == p["sarcina"]["titlu"] for p in m["plecari"])


def test_compensare_mono_nesuportata():
    r = calculeaza({"tip_schema": "tablou", "retea": "mono", "compensare_kvar": 10, "plecari": [{"nume": "A", "P_kW": 2}]})
    assert any(v["cod"] == "V96" for v in _b(r))
