"""Runda 11 — motor / constructor / desen (teste/r11/industrial.md, fotovoltaic.md, locuinte.md).

Topologii noi (PT 2 trafo + cuplă NO + AAR, UPS ca plecare, TG cu bară normală + bară vitală, n stații VE, mai multe
TGD-CF), refuzul cinstit al cheilor nefolosite, datele trafo (Ucc, grupa de conexiuni), Q declarat la branșament nou,
V46 la depășiri mici, V53 fără „invertor”, DDR pe invertoare > 10 kW, V67 pe Smax real, PT existent / al OD la CEF.
"""
import pytest

from engine import constructor, layout, validare
from engine.calc import calculeaza
from engine.calc.chei import CHEI, INFORMATIVE, chei_nefolosite
from engine.interp_schema_inventar import INVENTAR


def _bl(r):
    return [v for v in r.get("verificari") or [] if v.get("nivel") == "BLOCANT"]


def _cod(r, cod, nivel=None):
    return [v for v in r.get("verificari") or [] if v["cod"] == cod and (nivel is None or v["nivel"] == nivel)]


def _toate_ap(m):
    def walk(bs):
        for b in bs or []:
            yield from b.get("aparate") or []
            yield from b.get("aparate_tablou") or []
            yield from walk(b.get("copii"))
    yield from walk(m.get("intrari"))
    yield from walk(m.get("plecari"))
    cup = (m.get("bara") or {}).get("cupla") or {}
    yield from cup.get("aparate") or ([cup["aparat"]] if cup.get("aparat") else [])


def _deseneaza(m):
    assert layout.build(m) is not None


PL4 = [{"nume": "TD1", "P_kW": 200, "sectie": 1}, {"nume": "TD2", "P_kW": 150, "sectie": 1},
       {"nume": "TD3", "P_kW": 180, "sectie": 2}, {"nume": "TD4", "P_kW": 90, "sectie": 2}]


# ------------------------------------------------------------------------------- 1a. PT 2 trafo + cuplă NO + AAR
def test_pt_2_trafo_aar_sectii_si_ik_un_trafo():
    inp = {"tip_schema": "pt", "Sn_kVA": 800, "n_trafo": 2, "cupla": "deschisa", "aar": True, "plecari": PL4}
    m, r = constructor.genereaza(inp)
    z = r["rezultat"]
    un = calculeaza({"tip_schema": "pt", "Sn_kVA": 800, "plecari": PL4})["rezultat"]["trafo"]["Ik3max_bara_kA"]
    assert not _bl(r), _bl(r)
    assert z["cupla"]["stare"] == "NO" and z["cupla"]["AAR"] and "2 din 3" in z["cupla"]["AAR"]["interblocaj"]
    assert z["Ik3max_bara_kA"] == pytest.approx(un)                         # Ik pe secție = un trafo
    assert [s["sectie"] for s in z["sectii"]] == [1, 2]
    cup = m["bara"]["cupla"]
    assert "AAR" in " ".join(cup["aparat"]["spec"]) and cup["aparat"]["laterale"][0]["ref"] == "AAR"
    assert sorted(a["ref"] for a in _toate_ap(m) if a.get("tip") == "trafo") == ["T1", "T2"]
    assert "AAR" in m["cartus"]["denumire2"]
    _deseneaza(m)
    assert not validare.valideaza(m)["blocheaza"]


def test_pt_aar_regim_un_trafo_pe_ambele_sectii_avertisment():
    r = calculeaza({"tip_schema": "pt", "Sn_kVA": 400, "n_trafo": 2, "cupla": "deschisa", "aar": True, "ks": 1,
                    "plecari": [{"nume": "A", "P_kW": 250, "sectie": 1}, {"nume": "B", "P_kW": 250, "sectie": 2}]})
    assert any("regim AAR" in v["mesaj"] for v in _cod(r, "V62", "AVERTISMENT"))


@pytest.mark.parametrize("inp", [
    {"tip_schema": "pt", "Sn_kVA": 800, "aar": True, "plecari": PL4},                                  # un trafo
    {"tip_schema": "pt", "Sn_kVA": 800, "n_trafo": 2, "cupla": "inchisa", "aar": True, "plecari": PL4},  # paralel
    {"tip_schema": "pt", "Sn_kVA": 800, "n_trafo": 3, "plecari": PL4},                                  # > suportat
])
def test_pt_aar_combinatii_nesuportate_blocant(inp):
    bl = _bl(calculeaza(inp))
    assert bl and all(v.get("remediere") for v in bl)


def test_tg_din_pt_2_trafo_cupla_deschisa_doua_sectii_aar():
    inp = {"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 630, "n_trafo": 2, "cupla": "deschisa",
           "aar": True, "grupa_conexiuni": "Dyn11",
           "plecari": [{"nume": "Hală", "In_A": 250}, {"nume": "Birouri", "In_A": 100, "vital": False},
                       {"nume": "Pompe", "P_kW": 30}]}
    m, r = constructor.genereaza(inp)
    z = r["rezultat"]
    assert not _bl(r), _bl(r)
    assert z["sectii_tg"]["aar"] and z["sectii_tg"]["n1"] == 2
    assert [i["sursa"]["titlu"] for i in m["intrari"]] == ["T1 630 kVA", "T2 630 kVA"]
    assert {a["ref"] for a in _toate_ap(m)} >= {"Q1.1", "Q1.2", "QC"}
    assert any("deconectat la AAR" in p["sarcina"]["sub"] for p in m["plecari"])
    _deseneaza(m)


def test_vital_pe_tablou_fara_rezerva_nesuportat():
    r = calculeaza({"tip_schema": "tablou", "origine": "tg_existent", "plecari": [{"nume": "A", "P_kW": 10, "vital": True}]})
    v = _cod(r, "V96", "BLOCANT")
    assert v and "bara_vitala" in v[0]["remediere"]


# ------------------------------------------------------------------------------- 3. Ucc, grupa de conexiuni
def test_ucc_alias_si_dyn11_pe_plansa_si_in_lista():
    base = {"tip_schema": "pt", "Sn_kVA": 1000, "plecari": [{"nume": "TD", "P_kW": 300}]}
    r6 = calculeaza(base)["rezultat"]["trafo"]
    m, r = constructor.genereaza(dict(base, ucc_pct=4.5, grupa_conexiuni="dyn 11"))
    t = r["rezultat"]["trafo"]
    assert t["uk_pct"] == 4.5 and t["grupa"] == "Dyn11" and t["Ik3max_bara_kA"] > 1.25 * r6["Ik3max_bara_kA"]
    tr = next(a for a in _toate_ap(m) if a.get("tip") == "trafo")
    assert "Dyn11" in " ".join(tr["spec"]) and "Dyn11" in tr["lista"][0] and "uk 4,5" in tr["lista"][1]


@pytest.mark.parametrize("decl", [{"uk_pct": 6, "ucc_pct": 4.5}, {"grupa_conexiuni": "Dzz99"}])
def test_trafo_date_contradictorii_sau_invalide_blocant(decl):
    r = calculeaza(dict({"tip_schema": "pt", "Sn_kVA": 1000, "plecari": [{"nume": "TD", "P_kW": 300}]}, **decl))
    assert _cod(r, "V12", "BLOCANT")[0]["remediere"]


def test_grupa_nedeclarata_presupusa():
    r = calculeaza({"tip_schema": "pt", "Sn_kVA": 630, "plecari": [{"nume": "TD", "P_kW": 100}]})
    assert any("grupa de conexiuni Dyn5" in p for p in r["presupus"])


# ------------------------------------------------------------------------------- 1b. UPS ca plecare / tablou
def _ups(**kw):
    pl = {"nume": "UPS 200 kVA", "ups": True, "Sn_kVA": 200, "bypass": True, "L_m": 20,
          "copii": [{"nume": "PDU A", "P_kW": 60, "L_m": 15}, {"nume": "PDU B", "P_kW": 60, "L_m": 15}]}
    pl.update(kw)
    return {"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 1000, "schema_pamant": "TN-S",
            "plecari": [pl, {"nume": "Climatizare", "P_kW": 120}]}


def test_ups_plecare_cu_tablou_de_iesire():
    m, r = constructor.genereaza(_ups())
    z = r["rezultat"]
    assert not _bl(r), _bl(r)
    u = next(p for p in z["plecari"] if p.get("ups"))["ups"]
    assert u["In_iesire_A"] == pytest.approx(288.7, abs=0.1) and u["Ib_intrare_A"] == pytest.approx(1.15 * 288.7, abs=0.2)
    assert u["Q_iesire"]["In_A"] >= u["In_iesire_A"] and u["bypass"]
    pl = m["plecari"][0]
    tipuri = [a["tip"] for a in pl["aparate_tablou"]]
    assert tipuri[0] == "ups" and tipuri[1] in ("mccb", "acb")
    assert "TD-UPS" in pl["sarcina"]["titlu"] and [c["sarcina"]["titlu"] for c in pl["copii"]] == ["PDU A", "PDU B"]
    assert "bypass static" in " ".join(pl["aparate_tablou"][0]["lista"])
    assert not any(t == "trafo" for t in (a.get("tip") for a in _toate_ap(m)))           # niciun PT inventat
    _deseneaza(m)


def test_ups_supraincarcat_blocant_si_fara_sn_blocant():
    r = calculeaza(_ups(copii=[{"nume": "PDU", "P_kW": 250}]))
    assert any("UPS" in v["mesaj"] for v in _cod(r, "V62", "BLOCANT"))
    r = calculeaza(_ups(Sn_kVA=None))
    v = [x for x in _bl(r) if "Sn_kVA" in x["mesaj"]]
    assert v and "Sn_kVA" in v[0]["remediere"]


def test_ups_intrari_separate_plecare_bypass():
    r = calculeaza(_ups(intrari_separate=True))
    assert any(p.get("ups_bypass") for p in r["rezultat"]["plecari"])


# ------------------------------------------------------------------------------- 1c. TG bară normală + bară vitală
CONS = [{"nume": "Pompă incendiu", "P_kW": 75, "pornire": "stea_triunghi", "siguranta": True},
        {"nume": "Servere", "P_kW": 20, "vital": True}, {"nume": "HVAC", "P_kW": 150, "vital": False},
        {"nume": "Iluminat", "P_kW": 40, "vital": False}]


def test_tg_bara_normala_bara_vitala():
    inp = {"tip_schema": "ge_ats", "Sn_GE_kVA": 150, "bara_vitala": True, "sursa_retea": "pt", "pt_Sn_kVA": 1000,
           "schema_pamant": "TN-S", "consumatori": CONS}
    m, r = constructor.genereaza(inp)
    z = r["rezultat"]
    assert not _bl(r), _bl(r)
    assert z["mod"] == "tg_normal_vital" and z["P_retea_normali_kW"] == pytest.approx(190)
    assert z["Sn_GE_minim_kVA"] <= 150                       # GE dimensionat doar pe vitali (95 kW)
    assert [i["sursa"]["titlu"] for i in m["intrari"]] == ["REȚEA", "GRUP ELECTROGEN"]
    cup = m["bara"]["cupla"]
    assert cup["n1"] == 2 and [a["ref"] for a in cup["aparate"]] == ["QV", "ATS·I"]
    titluri = [p["sarcina"]["titlu"] for p in m["plecari"]]
    assert titluri == ["HVAC", "Iluminat", "Pompă incendiu", "Servere"]       # câte o plecare, pe bara ei
    assert "ATS·II" in {a["ref"] for a in m["intrari"][1]["aparate"]}
    _deseneaza(m)


@pytest.mark.parametrize("cons", [[{"nume": "A", "P_kW": 10}, {"nume": "B", "P_kW": 20}],           # nimic marcat
                                  [{"nume": "A", "P_kW": 10, "vital": True}]])                       # bară normală goală
def test_tg_bara_vitala_date_insuficiente_blocant(cons):
    r = calculeaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 100, "bara_vitala": True, "sursa_retea": "pt",
                    "pt_Sn_kVA": 400, "consumatori": cons})
    assert _bl(r) and all(v["remediere"] for v in _bl(r))


# ------------------------------------------------------------------------------- 1d. n stații VE identice
def test_6_statii_ve_sase_plecari():
    m, r = constructor.genereaza({"tip_schema": "tablou", "origine": "tg_existent", "schema_pamant": "TN-S",
                                  "plecari": [{"nume": "Stație VE", "P_kW": 22, "n": 6, "ddr": {"tip": "B"}}]})
    pl = r["rezultat"]["plecari"]
    assert len(pl) == 6 and all(p["DDR"]["tip"] == "B" for p in pl)
    assert r["rezultat"]["bilant"]["Pi_kW"] == pytest.approx(132)
    assert len(m["plecari"]) == 6


def test_6_statii_ve_in_tablou_dedicat():
    r = calculeaza({"tip_schema": "tablou", "origine": "tg_existent",
                    "plecari": [{"nume": "Stație VE", "P_kW": 22, "n": 6, "in_tablou": True}]})
    z = r["rezultat"]["plecari"]
    assert z[0]["nume"].startswith("TD-VE") and len([p for p in z if p["nivel"] == 1]) == 6


def test_nume_cu_6_statii_fara_n_nu_devine_tacut_o_plecare():
    r = calculeaza({"tip_schema": "pt", "Sn_kVA": 400, "plecari": [{"nume": "Parcare cu 6 statii EV", "P_kW": 22}]})
    v = _cod(r, "V96", "BLOCANT")
    assert v and "n: 6" in v[0]["remediere"]


# ------------------------------------------------------------------------------- 1e. mai multe TGD-CF
INV2 = [{"n": 3, "Pn_kW": 50, "producator": "Huawei", "model": "SUN2000-50KTL-M3", "tgd": 1},
        {"n": 3, "Pn_kW": 50, "producator": "Huawei", "model": "SUN2000-50KTL-M3", "tgd": 2}]


@pytest.mark.parametrize("racord", [{"racord": "pt", "pt_Sn_kVA": 630, "pt_existent": True},
                                    {"racord": "tg_existent"}, {"pt_Sn_kVA": 630}])
def test_cef_doua_tgd_cf(racord):
    inp = dict({"tip_schema": "cef", "retea": "tri", "n_tgd_cf": 2, "L_racord_m": 40, "limitare_injectie_kW": 0,
                "invertoare": INV2}, **racord)
    m, r = constructor.genereaza(inp)
    z = r["rezultat"]
    assert not _bl(r), _bl(r)
    assert [t["unitati"] for t in z["tgd_cf"]] == [["INV-1", "INV-2", "INV-3"], ["INV-4", "INV-5", "INV-6"]]
    assert z["sume"]["Pn_total_kW"] == 300 and all(t.get("QG") and t.get("C0") for t in z["tgd_cf"])
    refs = {a["ref"] for a in _toate_ap(m)}
    assert {"QG1", "QG2"} <= refs and len(m["intrari"]) == 6
    assert m["bara"]["cupla"]["fara_legatura"] and m["bara"]["cupla"]["n1_in"] == 3
    assert any(a.get("ref") == "TCA" for a in m["jonctiune"]["aparate"])     # limitarea la punctul de racord comun
    _deseneaza(m)


def test_cef_tgd_peste_suportat_blocant():
    # r12: n_tgd_cf > 2 = alias pentru 3 tablouri intermediare spre un TEG comun (nu mai e V96)
    r = calculeaza({"tip_schema": "cef", "retea": "tri", "n_tgd_cf": 3, "invertoare": INV2})
    assert not _cod(r, "V96", "BLOCANT")
    assert _cod(r, "V07", "BLOCANT")            # al treilea tablou fără invertoare
    inv3 = INV2 + [dict(INV2[0], tgd=3)]
    r = calculeaza({"tip_schema": "cef", "retea": "tri", "n_tgd_cf": 3, "invertoare": inv3})
    assert not _cod(r, "V96", "BLOCANT")
    assert len(r["rezultat"]["tablouri_intermediare"]) == 3


def test_cef_tgd_fara_repartitie_declarata_imparte_si_presupune():
    inv = [{"n": 4, "Pn_kW": 50, "producator": "Huawei", "model": "SUN2000-50KTL-M3"}]
    r = calculeaza({"tip_schema": "cef", "retea": "tri", "racord": "tg_existent", "n_tgd_cf": 2, "invertoare": inv})
    assert [len(t["unitati"]) for t in r["rezultat"]["tgd_cf"]] == [2, 2]
    assert any("tgd" in p for p in r["presupus"])


# ------------------------------------------------------------------------------- 5. CEF: V67, PT existent / OD
def test_v67_nu_blocheaza_9_sg110cx_pe_1000():
    r = calculeaza({"tip_schema": "cef", "masura": "MT", "pt_Sn_kVA": 1000, "pt_existent": False, "retea": "tri",
                    "limitare_injectie_kW": 900,
                    "invertoare": [{"n": 9, "Pn_kW": 110, "producator": "Sungrow", "model": "SG110CX"}]})
    assert not _cod(r, "V67", "BLOCANT") and _cod(r, "V67", "AVERTISMENT")
    assert r["rezultat"]["sume"]["S_trafo_kVA"] == pytest.approx(990)


def test_v67_blocheaza_cand_smax_real_depaseste():
    r = calculeaza({"tip_schema": "cef", "masura": "MT", "pt_Sn_kVA": 1000, "pt_existent": False, "retea": "tri",
                    "invertoare": [{"n": 9, "Pn_kW": 115, "producator": "Huawei", "model": "SUN2000-115KTL-M2"}]})
    assert _cod(r, "V67", "BLOCANT")                       # 9 × 125 kVA = 1125 kVA > 1000


def test_cef_pt_existent_fara_trafo_nou_si_tca_la_pt():
    inp = {"tip_schema": "cef", "limitare_injectie_kW": 0, "masura": "MT", "pt_Sn_kVA": 400, "pt_existent": True,
           "retea": "tri", "invertoare": [{"n": 2, "Pn_kW": 110, "producator": "Solis", "model": "Solis-110K-5G"}]}
    m, r = constructor.genereaza(inp)
    assert not any(a.get("tip") == "trafo" for a in _toate_ap(m))
    lista = " ".join(" ".join(x.get("lista") or []) for x in m.get("materiale") or [])
    assert "Anvelopă" not in lista and "Transformator de putere" not in lista
    assert not any(a.get("ref") == "TCA" for a in m["plecari"][0]["aparate"])        # nu pe plecarea CEF
    pcc = [c for c in m["plecari"][0]["copii"] if "PCC" in c["sarcina"]["titlu"]]
    assert pcc and any(a.get("ref") == "TCA" for a in pcc[0]["aparate"])
    _deseneaza(m)


def test_cef_pt_od_note_fara_pt_propriu():
    inp = {"tip_schema": "cef", "pt_Sn_kVA": 630, "pt_od": True, "retea": "tri",
           "invertoare": [{"n": 2, "Pn_kW": 100, "producator": "Huawei", "model": "SUN2000-100KTL-M2"}]}
    m, r = constructor.genereaza(inp)
    assert r["rezultat"]["trafo"]["existent"] and not _bl(r)
    assert not any("PT propriu" in n or "PT-ul propriu" in n for n in m["note"])


def test_cablu_cc_impus_verificat():
    base = {"tip_schema": "cef", "racord": "tg_existent", "retea": "tri",
            "invertoare": [{"n": 1, "Pn_kW": 50, "producator": "Huawei", "model": "SUN2000-50KTL-M3"}],
            "string": {"Isc_A": 18, "n_module": 20, "n_stringuri_paralel": 2}}
    r = calculeaza(dict(base, cablu_cc={"S_fortat": 4, "L_m": 40}))
    assert not _cod(r, "V02", "BLOCANT") and r["rezultat"]["cablu_cc"]["Iz_A"] == 55     # 55 A ≥ 1,25·18·2 = 45 A
    r = calculeaza(dict(base, cablu_cc={"S_fortat": 2.5, "L_m": 40}))
    assert _cod(r, "V02", "BLOCANT")
    r = calculeaza(dict(base, string={}, cablu_cc={"S_fortat": 6}))
    assert any("Isc" in v["mesaj"] for v in _bl(r))


# ------------------------------------------------------------------------------- 4. locuință
CIRC = [{"nume": "Iluminat", "receptor": "iluminat"}, {"nume": "Prize", "receptor": "prize"},
        {"nume": "PC", "receptor": "pompa_caldura", "P_kW": 9, "faza": "3F"},
        {"nume": "Plită", "receptor": "plita", "P_kW": 7.4}, {"nume": "Cuptor", "receptor": "cuptor"}]


@pytest.mark.parametrize("q,pa", [(25, 15), (25, None), (16, 15), (40, 15)])
def test_bransament_nou_q_declarat_respectat(q, pa):
    al = {"tip": "bransament_nou", "In_Q_bransament_A": q}
    if pa:
        al["P_aprobata_kW"] = pa
    r = calculeaza({"tip_schema": "locuinta", "retea": "tri", "circuite": CIRC, "alimentare": al})
    z = r["rezultat"]["alimentare"]
    assert z["Q"]["In_A"] == q                                             # niciodată înlocuit tăcut
    v46 = _cod(r, "V46", "BLOCANT")
    if q < 30:
        assert v46 and all(v.get("propunere", {}).get("valoare", 99) > q for v in v46 if v.get("propunere"))
    assert not any("Q ales pe puterea" in v["mesaj"] for v in _cod(r, "V46"))


def test_v46_depasire_mica_avertisment():
    # 45,33 A față de 1,13·40 = 45,2 A (r11 #35) → AVERTISMENT, nu BLOCANT
    r = calculeaza({"tip_schema": "locuinta", "retea": "mono", "alimentare": {"P_aprobata_kW": 9, "In_Q_bransament_A": 40},
                    "circuite": [{"nume": "Iluminat", "receptor": "iluminat"}, {"nume": "Prize bucătărie", "receptor": "prize_bucatarie"},
                                 {"nume": "Prize baie", "receptor": "prize_baie"},
                                 {"nume": "Plită", "receptor": "plita", "P_kW": 7.4}, {"nume": "Cuptor", "receptor": "cuptor", "P_kW": 3.5},
                                 {"nume": "Frigider", "receptor": "alt_circuit"}] + [{"nume": f"Prize {i}", "receptor": "prize"} for i in range(1, 6)]})
    v = [x for x in _cod(r, "V46") if "1,13·In" in x["mesaj"]]
    assert v and all(x["nivel"] == "AVERTISMENT" for x in v) and "toleranța" in v[0]["mesaj"]


def test_v46_mono_fara_alta_faza_si_v53_fara_invertor():
    r = calculeaza({"tip_schema": "locuinta", "retea": "mono", "alimentare": {"P_aprobata_kW": 7, "In_Q_bransament_A": 32},
                    "circuite": CIRC[:2] + [{"nume": "AC", "receptor": "aer_conditionat", "P_kW": 3.5},
                                            {"nume": "Boiler", "receptor": "boiler", "P_kW": 2},
                                            {"nume": "Plită", "receptor": "plita", "P_kW": 7}]})
    assert all("altă fază" not in (v.get("remediere") or "") for v in _cod(r, "V46"))
    r = calculeaza({"tip_schema": "bransament", "retea": "mono", "P_kW": 15})
    v = _cod(r, "V53", "BLOCANT")
    assert v and "invertor" not in v[0]["remediere"]


@pytest.mark.parametrize("pn,idn", [(8, 30), (10, 30), (15, 100), (25, 100), (30, 100)])
def test_ddr_invertor_prosumator_dupa_putere(pn, idn):
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "schema_pamant": "TN-C-S", "P_aprobata_kW": 30,
                    "invertoare": [{"n": 1, "Pn_kW": pn, "producator": "Huawei", "model": f"SUN2000-{pn}KTL-M1"}]})
    d = [x for x in (r["rezultat"].get("invertoare") or []) if x.get("DDR")]
    assert d and d[0]["DDR"]["IdN_mA"] == idn


# ------------------------------------------------------------------------------- 2. refuz cinstit: chei nefolosite
TIPURI_MINIME = {
    "bransament": {"tip_schema": "bransament", "retea": "tri", "P_kW": 10},
    "tablou": {"tip_schema": "tablou", "origine": "tg_existent", "plecari": [{"nume": "A", "P_kW": 10}]},
    "pt": {"tip_schema": "pt", "Sn_kVA": 400, "plecari": [{"nume": "A", "P_kW": 100}]},
    "ge_ats": {"tip_schema": "ge_ats", "Sn_GE_kVA": 100, "consumatori": [{"nume": "A", "P_kW": 50}]},
    "cef": {"tip_schema": "cef", "retea": "tri", "invertoare": [{"n": 1, "Pn_kW": 50, "producator": "Huawei",
                                                                "model": "SUN2000-50KTL-M3"}]},
    "prosumator": {"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 10},
    "locuinta": {"tip_schema": "locuinta", "retea": "mono", "alimentare": {"P_aprobata_kW": 7, "In_Q_bransament_A": 32},
                 "circuite": [{"nume": "Iluminat", "receptor": "iluminat"}]},
}
LISTA_DE = {"plecari": "tablou", "consumatori": "ge_ats", "invertoare": "cef"}


def _cu_cheie(tip, cale):
    inp = {k: (list(v) if isinstance(v, list) else v) for k, v in TIPURI_MINIME[tip].items()}
    val = (INVENTAR[cale]["v"] or [1])[0] if "." not in cale.split("[].")[-1] else 1
    top = cale.split(".")[0]
    if "[]" in top:
        lst, k = top.split("[]")[0], cale.split("[].")[1].split(".")[0]
        if lst not in inp:
            return None
        inp[lst] = [dict(inp[lst][0], **{k: val})]
    else:
        inp[top] = val
    return inp


def _cazuri_inventar():
    out = []
    for cale, info in sorted(INVENTAR.items()):
        for tip in info["tipuri"]:
            if tip in TIPURI_MINIME:
                out.append((tip, cale))
    return out


@pytest.mark.parametrize("tip,cale", _cazuri_inventar())
def test_cheile_interpretorului_sunt_folosite_sau_refuzate(tip, cale):
    """Orice cheie emisă de interpretor (inventarul) e fie în lista cheilor folosite de schema ei (engine/calc/chei.py),
    fie produce V96 BLOCANT „nesuportat” — niciodată ignorată în tăcere."""
    inp = _cu_cheie(tip, cale)
    if inp is None:
        pytest.skip("lista nu există în intrarea minimă")
    nf = chei_nefolosite(inp, tip)
    if nf:
        r = calculeaza(inp)
        v = [x for x in _cod(r, "V96", "BLOCANT") if x.get("chei")]
        assert v and v[0]["remediere"] and "nesuportat" in v[0]["mesaj"]


@pytest.mark.parametrize("tip", sorted(TIPURI_MINIME))
def test_cheie_necunoscuta_blocant_explicit(tip):
    r = calculeaza(dict(TIPURI_MINIME[tip], cheie_inventata_r11=5))
    v = [x for x in _cod(r, "V96", "BLOCANT") if "cheie_inventata_r11" in " ".join(x.get("chei") or [])]
    assert v and v[0]["remediere"]


@pytest.mark.parametrize("tip", sorted(TIPURI_MINIME))
def test_informative_si_interne_nu_blocheaza(tip):
    inp = dict(TIPURI_MINIME[tip], beneficiar="SC X SRL", _deduse=["retea"])
    assert not [x for x in _cod(calculeaza(inp), "V96", "BLOCANT") if x.get("chei")]
    assert "beneficiar" in INFORMATIVE and set(CHEI) >= set(TIPURI_MINIME)


def test_cheie_necunoscuta_pe_plecare_si_consumator():
    r = calculeaza({"tip_schema": "tablou", "origine": "tg_existent", "plecari": [{"nume": "A", "P_kW": 10, "culoare": "rosu"}]})
    assert any("plecari[0].culoare" in (x.get("chei") or []) for x in _cod(r, "V96", "BLOCANT"))
    r = calculeaza({"tip_schema": "cef", "retea": "tri", "circuite_casa": [{"nume": "PC"}],
                    "invertoare": [{"n": 1, "Pn_kW": 50, "producator": "Huawei", "model": "SUN2000-50KTL-M3"}]})
    assert any("circuite_casa" in (x.get("chei") or []) for x in _cod(r, "V96", "BLOCANT"))


def test_ge_izolat_cu_retea_blocant():
    r = calculeaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 200, "fara_retea": True, "sursa_retea": "pt",
                    "consumatori": [{"nume": "Bandă", "P_kW": 30}]})
    v = _cod(r, "V12", "BLOCANT")
    assert v and "nesuportat" in v[0]["mesaj"] and v[0]["remediere"]
