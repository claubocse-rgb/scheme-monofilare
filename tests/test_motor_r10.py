"""Runda 10 — motor / constructor / desen (teste/r10/industrial.md, fotovoltaic.md, locuinte.md).

Teste pe intrarea fizică (fără interpretor): PT cu 2 trafo (paralel / bara T1 / uk declarat), trafo neacoperit →
BLOCANT, ATS între două trafo, GE izolat, vitali / nevitali, DDR tip B pe plecarea VE, siguranța în engleză, cablu
impus fără L, V25 pe cablu existent, baterie c.c. pe invertor ne-hibrid, model curățat, locuința (plită, RA, GE mono,
ATS, multisplit), tabloul EPS, invertoare existente și remedierea oricărui BLOCANT.
"""
import pytest

from engine import constructor, layout, validare
from engine.calc import calculeaza
from engine.calc.catalog_invertoare import curata_model
from engine.calc.scheme import e_consumator_siguranta


def _bl(r):
    return [v for v in r.get("verificari") or [] if v.get("nivel") == "BLOCANT"]


def _cod(r, cod, nivel=None):
    return [v for v in r.get("verificari") or [] if v["cod"] == cod and (nivel is None or v["nivel"] == nivel)]


def _toate_ap(m):
    def walk(bs):
        for b in bs or []:
            yield from b.get("aparate") or []
            yield from walk(b.get("copii"))
    yield from walk(m.get("intrari"))
    yield from walk(m.get("plecari"))


PL = [{"nume": "TD1", "In_A": 630}, {"nume": "TD2", "In_A": 400}]


# ------------------------------------------------------------------------------- 1. PT cu 2 trafo
def test_pt_2_trafo_paralel_ik_dublu():
    r1 = calculeaza({"tip_schema": "pt", "Sn_kVA": 1250, "plecari": PL})
    r2 = calculeaza({"tip_schema": "pt", "Sn_kVA": 1250, "n_trafo": 2, "cupla": "inchisa", "plecari": PL})
    ik1, ik2 = r1["rezultat"]["trafo"]["Ik3max_bara_kA"], r2["rezultat"]["trafo"]["Ik3max_bara_kA"]
    assert 1.7 * ik1 < ik2 < 2.05 * ik1          # ≈ 60 kA față de 31 kA
    assert r2["rezultat"]["Q_JT"]["Icu_kA"] >= ik2


@pytest.mark.parametrize("decl,paralel", [({"cupla": "inchisa"}, True), ({}, True), ({"bara": "T1"}, False),
                                          ({"cupla": "deschisa"}, False)])
def test_tablou_din_pt_cu_2_trafo(decl, paralel):
    inp = dict({"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 1250, "n_trafo": 2,
                "plecari": [{"nume": "TD1", "P_kW": 300}]}, **decl)
    r = calculeaza(inp)
    ps = r["rezultat"]["PT_sursa"]
    assert ps["n_trafo"] == 2 and ps["paralel"] is paralel
    un = calculeaza({"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 1250,
                     "plecari": [{"nume": "TD1", "P_kW": 300}]})["rezultat"]["bara_TG"]["Ik3max_kA"]
    assert (r["rezultat"]["bara_TG"]["Ik3max_kA"] > 1.2 * un) is paralel


@pytest.mark.parametrize("inp", [
    {"tip_schema": "bransament", "retea": "tri", "P_kW": 10, "n_trafo": 2},
    {"tip_schema": "tablou", "origine": "tg_existent", "n_trafo": 2, "plecari": [{"nume": "A", "P_kW": 10}]},
])
def test_trafo_neacoperit_blocant_explicit(inp):
    r = calculeaza(inp)
    v = _cod(r, "V96", "BLOCANT")
    assert v and v[0]["remediere"] and "n_trafo" in v[0]["remediere"]


def test_n_trafo_invalid_blocant():
    r = calculeaza({"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 630, "n_trafo": 7,
                    "plecari": [{"nume": "A", "P_kW": 10}]})
    assert _cod(r, "V96", "BLOCANT")


# ------------------------------------------------------------------------------- 3. uk declarat, PT existent bara T1
def test_uk_declarat_folosit_la_ik():
    r6 = calculeaza({"tip_schema": "pt", "Sn_kVA": 1000, "plecari": PL})["rezultat"]["trafo"]
    r4 = calculeaza({"tip_schema": "pt", "Sn_kVA": 1000, "uk_pct": 4, "plecari": PL})["rezultat"]["trafo"]
    assert r4["uk_pct"] == 4 and r4["Ik3max_bara_kA"] > 1.35 * r6["Ik3max_bara_kA"]      # ≈ 37 kA vs 25 kA


def test_uk_absurd_blocant():
    r = calculeaza({"tip_schema": "pt", "Sn_kVA": 1000, "uk_pct": 40, "plecari": PL})
    assert _cod(r, "V12", "BLOCANT")[0]["remediere"]


def test_cef_pt_existent_bara_t1_un_singur_trafo():
    base = {"tip_schema": "cef", "racord": "pt", "pt_existent": True, "n_trafo": 2, "pt_Sn_kVA": 1000, "retea": "tri",
            "invertoare": [{"n": 4, "Pn_kW": 100, "producator": "Huawei", "model": "SUN2000-100KTL-M2"}]}
    par = calculeaza(base)["rezultat"]["trafo"]["Ik3max_bara_kA"]
    t1 = calculeaza(dict(base, bara="T1"))["rezultat"]["trafo"]["Ik3max_bara_kA"]
    un = calculeaza(dict(base, n_trafo=1))["rezultat"]["trafo"]["Ik3max_bara_kA"]
    assert t1 == pytest.approx(un) and par > 1.5 * t1


# ------------------------------------------------------------------------------- 2. ATS între trafo, GE izolat, vitali
def test_ats_intre_doua_trafo_fara_ge():
    inp = {"tip_schema": "ge_ats", "sursa_rezerva": "trafo", "pt_Sn_kVA": 630, "schema_pamant": "TN-S",
           "consumatori": [{"nume": "TD", "P_kW": 100, "n": 4}]}
    m, r = constructor.genereaza(inp)
    z = r["rezultat"]
    assert not _bl(r), _bl(r)
    assert z["mod"] == "ats_trafo" and z["ATS"]["In_A"] >= z["Q1_C1"]["protectie"]["In_A"]
    assert [p["nume"] for p in z["plecari"]] == ["TD 1", "TD 2", "TD 3", "TD 4"]         # plecări reale, necomasate
    assert not any(a.get("tip") == "generator" for a in _toate_ap(m))                   # niciun GE inventat
    assert [i["sursa"]["titlu"] for i in m["intrari"]] == ["T1 630 kVA", "T2 630 kVA"]
    assert {a["ref"] for a in _toate_ap(m)} >= {"QT1", "QT2", "ATS·I", "ATS·II"}
    assert not validare.valideaza(m)["blocheaza"]


def test_ats_trafo_cu_ge_declarat_e_contradictie():
    r = calculeaza({"tip_schema": "ge_ats", "sursa_rezerva": "trafo", "pt_Sn_kVA": 630, "Sn_GE_kVA": 630,
                    "consumatori": [{"nume": "TD", "P_kW": 100}]})
    assert _cod(r, "V12", "BLOCANT")


def test_ats_trafo_subdimensionat_v62():
    r = calculeaza({"tip_schema": "ge_ats", "sursa_rezerva": "trafo", "pt_Sn_kVA": 250,
                    "consumatori": [{"nume": "TD", "P_kW": 150, "n": 4}]})
    assert _cod(r, "V62", "BLOCANT")


def test_ge_izolat_fara_ramura_retea():
    inp = {"tip_schema": "ge_ats", "schema_pamant": "TN-S", "Sn_GE_kVA": 500, "fara_retea": True,
           "consumatori": [{"nume": "Concasor", "P_kW": 200}, {"nume": "Bandă", "P_kW": 30}, {"nume": "Iluminat", "P_kW": 5}]}
    m, r = constructor.genereaza(inp)
    z = r["rezultat"]
    assert not _bl(r), _bl(r)
    assert z["mod"] == "ge_izolat" and "Q_retea" not in z and "ATS" not in z
    assert [p["nume"] for p in z["plecari"]] == ["Concasor", "Bandă", "Iluminat"]
    assert len(m["intrari"]) == 1 and m["intrari"][0]["sursa"]["titlu"] == "GRUP ELECTROGEN"
    assert not any(a.get("tip") == "separator" and "ATS" in str(a.get("ref")) for a in _toate_ap(m))
    assert any(a.get("ref") == "DDR-G" for a in _toate_ap(m))                       # deconectare în regim GE
    assert z["Q_G"]["Ir_A"] <= z["In_G_A"] + 1e-6


def test_ge_izolat_subdimensionat_v86():
    r = calculeaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 60, "fara_retea": True,
                    "consumatori": [{"nume": "Concasor", "P_kW": 200}]})
    assert _cod(r, "V86", "BLOCANT")


def test_ge_izolat_cu_retea_declarata_avertisment_nu_desenata():
    m, r = constructor.genereaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 200, "fara_retea": True, "sursa_retea": "tgd",
                                  "consumatori": [{"nume": "Bandă", "P_kW": 30}]})
    assert _cod(r, "V12", "BLOCANT") and len(m["intrari"]) == 1          # r11: combinație nesuportată → BLOCANT


def test_vitali_nevitali_ge_dimensionat_pe_vitali():
    inp = {"tip_schema": "ge_ats", "Sn_GE_kVA": 250, "sursa_retea": "pt", "pt_Sn_kVA": 630, "P_sarcina_kW": 330,
           "consumatori": [{"nume": "Bloc operator", "P_kW": 40}, {"nume": "ATI", "P_kW": 30},
                           {"nume": "Lifturi", "P_kW": 15, "n": 2}, {"nume": "Iluminat siguranță", "P_kW": 5},
                           {"nume": "Bucătărie", "P_kW": 60, "vital": False},
                           {"nume": "Spălătorie", "P_kW": 45, "vital": False}, {"nume": "HVAC", "P_kW": 120, "vital": False}]}
    _, r = constructor.genereaza(inp)
    z = r["rezultat"]
    assert not _cod(r, "V86", "BLOCANT")
    assert z["P_retea_normali_kW"] == pytest.approx(225) and z["Sn_GE_minim_kVA"] <= 250


# ------------------------------------------------------------------------------- 4. RCD tip B, siguranță în engleză
@pytest.mark.parametrize("pl", [
    {"nume": "Stație încărcare EV", "P_kW": 22, "ddr": {"tip": "B"}, "L_m": 45, "cablu": {"S_fortat": 10, "material": "Cu"}},
    {"nume": "nouă pentru stație de încărcare EV", "P_kW": 22},
    {"nume": "EV charger", "P_kW": 22, "DDR": {"tip": "B", "IdN_mA": 30}},
])
def test_plecare_ve_ddr_tip_b(pl):
    m, r = constructor.genereaza({"tip_schema": "tablou", "origine": "tg_existent", "schema_pamant": "TN-S",
                                  "plecari": [pl]})
    d = r["rezultat"]["plecari"][0]["DDR"]
    assert d and d["IdN_mA"] == 30 and d["tip"] == "B"
    assert any("30" in " ".join(a.get("spec") or []) for a in _toate_ap(m) if str(a.get("ref", "")).startswith("DDR"))


def test_ddr_tip_a_declarat_ve_respectat():
    r = calculeaza({"tip_schema": "tablou", "origine": "tg_existent", "plecari": [
        {"nume": "Wallbox", "P_kW": 11, "ddr": {"tip": "A"}}]})
    assert r["rezultat"]["plecari"][0]["DDR"]["tip"] == "A"


@pytest.mark.parametrize("nume,sig", [("Fire pump", True), ("Sprinkler pump", True), ("Hydrant pump", True),
                                      ("Smoke extraction fan", True), ("Firefighting lift", True),
                                      ("Pompă de incendiu", True), ("Firewall server", False), ("Compresor", False)])
def test_siguranta_nume_in_engleza(nume, sig):
    assert e_consumator_siguranta({"nume": nume}) is sig


def test_fire_pump_regim_de_siguranta_in_tablou():
    m, r = constructor.genereaza({"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 400,
                                  "schema_pamant": "TN-S", "plecari": [{"nume": "Fire pump", "P_kW": 45}]})
    pl = r["rezultat"]["plecari"][0]
    assert pl.get("siguranta") and not pl.get("DDR") and "FE180" in m["plecari"][0]["cablu"]["text"]
    termic = [a for a in _toate_ap(m) if a.get("tip") == "releu_termic"]
    assert all("doar semnalizare" in a["spec"] for a in termic)


# ------------------------------------------------------------------------------- 5. cablu impus fără L, V25 existent
def test_cef_cablu_impus_fara_lungime_blocant_cu_intrebare():
    r = calculeaza({"tip_schema": "cef", "racord": "tg_existent", "retea": "tri",
                    "invertoare": [{"n": 1, "Pn_kW": 100, "producator": "Huawei", "model": "SUN2000-100KTL-M2"}],
                    "cablu_C0": {"material": "Cu", "S_fortat": 35}})
    v = [x for x in _bl(r) if x["cod"] == "V07"]
    assert v and v[0].get("intrebare") and "L_racord_m" in v[0]["remediere"]


def test_cef_cablu_impus_cu_lungime_verificat():
    r = calculeaza({"tip_schema": "cef", "racord": "tg_existent", "retea": "tri", "L_racord_m": 40,
                    "invertoare": [{"n": 1, "Pn_kW": 100, "producator": "Huawei", "model": "SUN2000-100KTL-M2"}],
                    "cablu_C0": {"material": "Cu", "S_fortat": 35}})
    assert not any(x["cod"] == "V07" for x in _bl(r)) and _cod(r, "V02", "BLOCANT")


def test_v25_neutru_redus_cablu_existent_avertisment():
    base = {"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 630, "schema_pamant": "TN-S",
            "L_alimentare_m": 120, "plecari": [{"nume": "TD", "P_kW": 150}]}
    nou = calculeaza(dict(base, cablu={"S_fortat": 150, "N_fortat": 70, "material": "Al"}))
    ex = calculeaza(dict(base, cablu={"S_fortat": 150, "N_fortat": 70, "material": "Al", "existent": True}))
    assert _cod(nou, "V25", "BLOCANT")
    assert _cod(ex, "V25", "AVERTISMENT") and not _cod(ex, "V25", "BLOCANT")
    assert "524.2.3" in _cod(ex, "V25")[0]["remediere"]


# ------------------------------------------------------------------------------- 6. baterie c.c. pe invertor ne-hibrid
def test_baterie_cc_pe_sg110cx_blocant():
    r = calculeaza({"tip_schema": "cef", "racord": "tg_existent", "retea": "tri",
                    "invertoare": [{"n": 1, "Pn_kW": 110, "producator": "Sungrow", "model": "SG110CX"}],
                    "bess": {"kWh": 100, "cuplaj": "cc"}})
    v = _cod(r, "V12", "BLOCANT")
    assert v and "nu este hibrid" in v[0]["mesaj"] and "„ca”" in v[0]["remediere"]


def test_baterie_ca_pe_sg110cx_ok():
    r = calculeaza({"tip_schema": "cef", "racord": "tg_existent", "retea": "tri",
                    "invertoare": [{"n": 1, "Pn_kW": 110, "producator": "Sungrow", "model": "SG110CX"}],
                    "bess": {"kWh": 100, "P_kW": 50, "cuplaj": "ca"}})
    assert not any("nu este hibrid" in v["mesaj"] for v in _bl(r))


def test_hibrid_cu_baterie_cc_ok():
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "invertoare": [
        {"n": 1, "Pn_kW": 10, "producator": "Sungrow", "model": "SH10RT"}], "baterie_kWh": 10})
    assert not any("nu este hibrid" in v["mesaj"] for v in _bl(r))


# ------------------------------------------------------------------------------- 7. modelul curățat
@pytest.mark.parametrize("brut,cod", [("SG50CX. Racordarea se", "SG50CX"), ("Symo 20.0-3-M", "Symo 20.0-3-M"),
                                      ("SUN2000-6KTL-L1 pe L2", "SUN2000-6KTL-L1"), ("SG110CX-P2", "SG110CX-P2")])
def test_curata_model(brut, cod):
    assert curata_model(brut) == cod


def test_model_poluat_nu_ajunge_pe_plansa():
    m, _ = constructor.genereaza({"tip_schema": "cef", "racord": "tg_existent", "pt_Sn_kVA": 400, "retea": "tri",
                                  "invertoare": [{"n": 2, "Pn_kW": 50, "producator": "Sungrow",
                                                  "model": "SG50CX. Racordarea se"}]})
    txt = str(m["intrari"]) + str(m.get("materiale"))
    assert "Racordarea" not in txt and "SG50CX" in txt


# ------------------------------------------------------------------------------- 8. locuință
CIRC = [{"nume": "Iluminat", "receptor": "iluminat"}, {"nume": "Prize", "receptor": "prize"}]


def _loc(**kw):
    d = {"tip_schema": "locuinta", "retea": "mono", "circuite": list(CIRC),
         "alimentare": {"P_aprobata_kW": 7, "In_Q_bransament_A": 40}}
    d.update(kw)
    return d


def _circ(z, nume):
    return next(c for g in z["grupe_DDR"] for c in g["circuite"] if c["nume"] == nume)


def test_plita_calibru_din_puterea_declarata():
    z = calculeaza(_loc(circuite=CIRC + [{"nume": "Aragaz", "receptor": "plita", "P_kW": 3},
                                         {"nume": "Plită mare", "receptor": "plita", "P_kW": 7.2}]))["rezultat"]
    a, p = _circ(z, "Aragaz"), _circ(z, "Plită mare")
    assert a["protectie"]["In_A"] == 16 and a["S_faza_mm2"] == 2.5
    assert p["protectie"]["In_A"] == 32 and p["S_faza_mm2"] == 6


def test_ra_declarat_tn_avertisment_si_nota():
    m, r = constructor.genereaza(_loc(retea="tri", schema_pamant="TN-C-S", RA_ohm=30,
                                      alimentare={"P_aprobata_kW": 10, "In_Q_bransament_A": 25}))
    assert _cod(r, "V37", "AVERTISMENT")
    assert "30" in m["rp"] and "Rp ≤ 4" not in m["rp"]
    assert any("RA = 30" in n for n in m["note"])


def test_ra_tt_verificat_cu_idn_real():
    m, r = constructor.genereaza(_loc(retea="tri", schema_pamant="TT", RA_ohm=30,
                                      alimentare={"P_aprobata_kW": 10, "In_Q_bransament_A": 25}))
    assert any("RA = 30" in n and "9" in n for n in m["note"]) and m["rp"].startswith("RA = 30")


@pytest.mark.parametrize("com,ref", [("manual", "K·I"), ("ATS", "ATS·I")])
def test_ge_rezerva_monofazat_la_casa(com, ref):
    m, r = constructor.genereaza(_loc(ge_rezerva={"Sn_kVA": 8, "comutare": com}))
    g = r["rezultat"]["ge_rezerva"]
    assert g["poli"] == "2P" and not _cod(r, "V96", "BLOCANT")
    assert ref in {a.get("ref") for a in _toate_ap(m)}


def test_multisplit_un_circuit():
    z = calculeaza(_loc(circuite=CIRC + [
        {"nume": "Aer condiționat", "receptor": "aer_conditionat", "multisplit": True, "unitati_interioare": 3, "P_kW": 2.8},
        {"nume": "AC dormitor", "receptor": "aer_conditionat", "unitate_interioara": True},
        {"nume": "AC living", "receptor": "aer_conditionat", "unitate_interioara": True}]))
    ac = [c for g in z["rezultat"]["grupe_DDR"] for c in g["circuite"] if "multisplit" in c["nume"] or "AC" in c["nume"]]
    assert len(ac) == 1 and "multisplit" in ac[0]["nume"]
    assert not _cod(z, "V12", "AVERTISMENT")


def test_tablou_eps_dupa_invertorul_hibrid():
    inp = {"tip_schema": "prosumator", "schema_pamant": "TN-C-S", "retea": "tri", "Pn_inv_kW": 12, "hibrid": True,
           "baterie_kWh": 15, "backup": {"circuite": [{"nume": "Frigider"}, {"nume": "Centrală termică"},
                                                      {"nume": "Router"}, {"nume": "Iluminat"}]}}
    m, r = constructor.genereaza(inp)
    e = r["rezultat"]["EPS"]
    assert not _bl(r) and e["la"] == "INV" and len(e["circuite"]) == 4 and e["DDR"]["IdN_mA"] == 30
    ap = m["intrari"][0]["aparate"]
    i_inv = next(i for i, a in enumerate(ap) if a.get("tip") == "invertor")
    lat = [l for a in ap[i_inv + 1:i_inv + 2] for l in a.get("laterale") or []]
    assert lat and lat[0]["ref"] == "TD-EPS"                      # tablou separat, imediat după invertor
    assert not any(p["sarcina"]["titlu"] == "TD-EPS" for p in m["plecari"])        # nu pe bara TE


def test_eps_fara_invertor_hibrid_blocant():
    r = calculeaza({"tip_schema": "prosumator", "retea": "tri", "Pn_inv_kW": 10,
                    "invertoare": [{"n": 1, "Pn_kW": 10, "producator": "Huawei", "model": "SUN2000-10KTL-M2"}],
                    "backup": {"circuite": [{"nume": "Frigider"}]}})
    v = [x for x in _bl(r) if "EPS" in x["mesaj"] or x["obiect"] == "EPS"]
    assert v and v[0]["remediere"]


def test_invertor_existent_desenat_nelistat():
    inp = {"tip_schema": "cef", "racord": "tg_existent", "retea": "tri", "invertoare": [
        {"n": 1, "Pn_kW": 20, "producator": "Fronius", "model": "Symo 20.0-3-M", "existent": True},
        {"n": 1, "Pn_kW": 30, "producator": "Huawei", "model": "SUN2000-30KTL-M3"}]}
    m, r = constructor.genereaza(inp)
    assert len(m["intrari"]) == 2
    assert "EXISTENT" in m["intrari"][0]["sursa"]["titlu"] and "EXISTENT" not in m["intrari"][1]["sursa"]["titlu"]
    assert all(a.get("existent") for a in m["intrari"][0]["aparate"])
    cv = layout.build(m)
    assert cv is not None
    L = layout.Layout(m)
    L.build()
    texte = " ".join(" ".join(p[2]) for p in L.poz)
    assert "Symo" not in texte and "SUN2000-30KTL-M3" in texte


# ------------------------------------------------------------------------------- 9. orice BLOCANT are remediere
@pytest.mark.parametrize("inp", [
    {"tip_schema": "pt", "Sn_kVA": 1250, "n_trafo": 2, "cupla": "ciudata", "plecari": PL},
    {"tip_schema": "ge_ats", "sursa_rezerva": "baterie", "Sn_GE_kVA": 100},
    {"tip_schema": "ge_ats", "sursa_rezerva": "trafo"},
    {"tip_schema": "ge_ats", "fara_retea": True},
    {"tip_schema": "tablou", "plecari": []},
    {"tip_schema": "locuinta", "retea": "mono", "circuite": [], "alimentare": {"P_aprobata_kW": 50}},
    {"tip_schema": "bransament", "retea": "tri"},
    {"tip_schema": "cef", "retea": "tri", "invertoare": [{"n": 1}]},
])
def test_orice_blocant_are_remediere(inp):
    m, r = constructor.genereaza(inp)
    v = validare.valideaza(m)
    bl = _bl(r) + [x for x in v["verificari"] if x["nivel"] == "BLOCANT"]
    assert bl
    for x in bl:
        rem = str(x.get("remediere") or "").strip()
        assert rem and "{" not in rem, x
