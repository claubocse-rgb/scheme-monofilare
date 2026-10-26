"""Runda 9 — motor / constructor / desen (teste/r9/industrial.md, fotovoltaic.md, locuinte.md).

Teste generice pe intrarea fizică (fără interpretor): siguranța la incendiu în GE + ATS și pe consumator, consumatorii
normali în afara GE, celula MT / ACB declarate, ștampila NEVERIFICAT pe orice BLOCANT, CEF 800 V / PT existent /
Ik3 presupus, locuința (VE, V56, saună dublată, TT, desen) și BMPT peste 250 A.
"""
import pytest

from engine import constructor, layout, validare
from engine.calc import calculeaza
from engine.calc.locuinta import calibru_ve


def _bl(r):
    return [v for v in r.get("verificari") or [] if v.get("nivel") == "BLOCANT"]


def _toate(pl):
    for p in pl or []:
        yield p
        yield from _toate(p.get("copii"))


def _aparate(m):
    for b in (m.get("intrari") or []):
        yield from (b.get("aparate") or [])
    for p in _toate(m.get("plecari")):
        yield from (p.get("aparate") or [])


# ------------------------------------------------------------------------------- 1. GE + ATS cu consumatori de siguranță
@pytest.mark.parametrize("cons", [
    [{"nume": "Electropompa PSI", "P_kW": 30, "n": "1+1"}, {"nume": "Pompa pilot", "P_kW": 1.1}],
    [{"nume": "Pompa sprinkler", "P_kW": 30}, {"nume": "Pompa jockey", "P_kW": 1.1}],
    [{"nume": "Pompa hidranti", "P_kW": 22}, {"nume": "Pompa incendiu rezerva", "P_kW": 22}],
    [{"nume": "Electropompe", "P_kW": 30, "n": "1+1", "siguranta": True}, {"nume": "Pompa pilot", "P_kW": 1.1}],
])
def test_ge_ats_pompe_incendiu_regim_de_siguranta(cons):
    inp = {"tip_schema": "ge_ats", "Sn_GE_kVA": 100, "sursa_retea": "pt", "pt_Sn_kVA": 250, "consumatori": cons}
    m, r = constructor.genereaza(inp)
    z = r["rezultat"]
    assert not _bl(r), _bl(r)
    assert "DDR" not in z["Q_G"] and z["Q_G"].get("RCM")                      # fără DDR-G, RCM doar alarmă
    assert not any(a.get("tip") in ("rccb", "rcbo", "mccb_dif") for a in _aparate(m))
    sig = z["plecari_siguranta"]
    n_tot = sum(int(str(c.get("n", 1)).split("+")[0]) + (int(str(c["n"]).split("+")[1]) if "+" in str(c.get("n", "")) else 0)
                for c in cons)
    assert len(sig) == n_tot                                                  # fiecare pompă — plecare proprie
    assert all(s["siguranta"] and s["rezistent_foc"] for s in sig)
    pl = [p for p in m["plecari"] if p.get("siguranta")]
    assert len(pl) == n_tot and all("FE180" in p["cablu"]["text"] for p in pl)
    termice = [a for p in pl for a in p["aparate"] if a.get("tip") == "releu_termic"]
    assert termice and all("doar semnalizare" in a["spec"] for a in termice)
    # QR (rețea) nu e sub calibrul unei plecări de siguranță
    assert z["Q_retea"]["In_A"] >= max(s["protectie"]["In_A"] for s in sig)
    assert "INCENDIU" in m["cartus"]["denumire2"]


def test_ge_ats_titlu_statie_psi_marcheaza_toti_consumatorii():
    inp = {"tip_schema": "ge_ats", "titlu_tablou": "Stație pompare PSI", "Sn_GE_kVA": 100, "sursa_retea": "pt",
           "pt_Sn_kVA": 250, "consumatori": [{"nume": "Electropompe", "P_kW": 30, "n": "1+1"},
                                             {"nume": "Pompa pilot", "P_kW": 1.1}]}
    m, r = constructor.genereaza(inp)
    z = r["rezultat"]
    assert z["siguranta_tot"] and len(z["plecari_siguranta"]) == 3 and "DDR" not in z["Q_G"]
    # 1A + 1R: rezerva desenată, neadunată la sarcina GE
    assert sum(1 for s in z["plecari_siguranta"] if s.get("rezerva")) == 1
    assert all("FE180" in (b.get("cablu_ca") or {}).get("text", "FE180") for b in m["intrari"])


# ------------------------------------------------------------------------------- 2. siguranța e a consumatorului
def test_tablou_mixt_doar_consumatorii_de_siguranta_au_regim_special():
    inp = {"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 400, "schema_pamant": "TN-S", "plecari": [
        {"nume": "Pompa sprinkler", "P_kW": 75, "pornire": "stea_triunghi"}, {"nume": "Pompa jockey", "P_kW": 3},
        {"nume": "Rampe 1", "P_kW": 1.1}, {"nume": "Iluminat", "P_kW": 8}, {"nume": "CTA 1", "P_kW": 4},
        {"nume": "CTA 2", "P_kW": 4}]}
    m, r = constructor.genereaza(inp)
    z = r["rezultat"]
    assert z["siguranta"] == "mixt"                       # sprinkler > 50 % din putere, dar tabloul NU devine TS
    sig = {p["nume"] for p in z["plecari"] if p.get("siguranta")}
    assert sig == {"Pompa sprinkler", "Pompa jockey"}
    assert all(p.get("inainte_Q1") for p in z["plecari"] if p.get("siguranta"))
    norm = [p for p in _toate(m["plecari"]) if (p.get("sarcina") or {}).get("titlu") in ("Rampe 1", "Iluminat", "CTA 1")]
    assert norm and all("FE180" not in p["cablu"]["text"] and not p.get("siguranta") for p in norm)
    # consumatorii normali sunt în grupa „după Q1 general”, sprinklerul înaintea lui
    grup = [p for p in m["plecari"] if p.get("grup")]
    assert grup and {c["sarcina"]["titlu"] for c in grup[0]["copii"]} >= {"Rampe 1", "Iluminat", "CTA 1", "CTA 2"}
    assert "SIGURANȚĂ LA INCENDIU" not in m["cartus"]["denumire2"]


def test_tablou_ventilatie_cta_normale_raman_normale():
    inp = {"tip_schema": "tablou", "origine": "tg_existent", "schema_pamant": "TN-S", "plecari": [
        {"nume": "Ventilatoare desfumare 1", "P_kW": 7.5}, {"nume": "Ventilator presurizare scara", "P_kW": 5.5},
        {"nume": "CTA 1", "P_kW": 4}, {"nume": "CTA 2", "P_kW": 4}]}
    _, r = constructor.genereaza(inp)
    z = r["rezultat"]
    assert z["siguranta"] == "mixt"
    assert not any(p.get("siguranta") for p in z["plecari"] if p["nume"].startswith("CTA"))


@pytest.mark.parametrize("decl", [{"titlu_tablou": "TDSI"}, {"siguranta_tablou": True}])
def test_tablou_declarat_de_siguranta_e_intreg_de_siguranta(decl):
    inp = dict({"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 400, "schema_pamant": "TN-S", "plecari": [
        {"nume": "Pompa sprinkler", "P_kW": 30}, {"nume": "Iluminat", "P_kW": 2}]}, **decl)
    _, r = constructor.genereaza(inp)
    assert r["rezultat"]["siguranta"] == "tot"


# ------------------------------------------------------------------------------- 3. consumatorii normali nu sunt pe GE
def test_ge_consumatori_normali_pe_ramura_retea():
    inp = {"tip_schema": "ge_ats", "schema_pamant": "TN-S", "Sn_GE_kVA": 200, "sursa_retea": "pt", "pt_Sn_kVA": 630,
           "P_sarcina_kW": 238, "consumatori": [
               {"nume": "Server", "P_kW": 30, "vital": True}, {"nume": "Iluminat siguranta", "P_kW": 3},
               {"nume": "Lift pompieri", "P_kW": 15}, {"nume": "HVAC", "P_kW": 150}, {"nume": "Prize", "P_kW": 40}]}
    m, r = constructor.genereaza(inp)
    z = r["rezultat"]
    assert not _bl(r), _bl(r)
    assert {c["nume"] for c in z["consumatori_retea"]} == {"HVAC", "Prize"}
    assert z["P_retea_normali_kW"] == pytest.approx(190)
    assert z["Sn_GE_minim_kVA"] <= 200                       # GE dimensionat doar pe vitali (48 kW), nu pe 238 kW
    assert not any(v["cod"] == "V86" and v["nivel"] == "BLOCANT" for v in r["verificari"])
    assert z["plecare_retea"]["protectie"]["In_A"]
    lat = [l for a in m["intrari"][0]["aparate"] for l in (a.get("laterale") or []) if l.get("ref") == "QN"]
    assert lat and "HVAC" in lat[0]["lista"][0]
    titluri = [p["sarcina"]["titlu"] for p in m["plecari"]]
    assert not any("HVAC" in t or "Prize" in t for t in titluri)


@pytest.mark.parametrize("cheie", [{"pe_ge": False}, {"vital": False}, {"normal": True}, {"ramura": "retea"}])
def test_ge_consumator_declarat_doar_retea(cheie):
    inp = {"tip_schema": "ge_ats", "Sn_GE_kVA": 60, "sursa_retea": "pt", "pt_Sn_kVA": 400, "consumatori": [
        {"nume": "Centrala", "P_kW": 10}, dict({"nume": "Chiller", "P_kW": 120}, **cheie)]}
    _, r = constructor.genereaza(inp)
    z = r["rezultat"]
    assert [c["nume"] for c in z["consumatori_retea"]] == ["Chiller"]
    assert not any(v["cod"] == "V86" and v["nivel"] == "BLOCANT" for v in r["verificari"])


# ------------------------------------------------------------------------------- 4. celula MT / ACB declarate
@pytest.mark.parametrize("cel", ["intreruptor", "intreruptor in vid", "vid", "Întrerupător vid 50/51", "SF6"])
def test_pt_celula_trafo_intreruptor_declarata(cel):
    inp = {"tip_schema": "pt", "Sn_kVA": 1000, "U_MT_kV": 6, "celula_trafo": cel, "In_Q_JT_A": 1600,
           "Q_general_tip": "ACB", "plecari": [{"nume": "TG1", "In_A": 630}, {"nume": "TG2", "In_A": 400}]}
    m, r = constructor.genereaza(inp)
    z = r["rezultat"]
    assert not _bl(r), _bl(r)
    assert z["celula_trafo"] == "intreruptor" and z["Q_JT"]["tip"] == "ACB"
    tipuri = [a.get("tip") for a in m["intrari"][0]["aparate"]]
    assert "intreruptor_mt" in tipuri and "sigurante_mt" not in tipuri and "acb" in tipuri


def test_tablou_acb_declarat():
    inp = {"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 1000, "schema_pamant": "TN-S",
           "In_Q1_A": 1250, "Q_general_tip": "ACB", "plecari": [{"nume": "TD1", "P_kW": 300}, {"nume": "TD2", "P_kW": 200}]}
    _, r = constructor.genereaza(inp)
    assert r["rezultat"]["Q1_C1"]["protectie"]["tip"] == "ACB"


# ------------------------------------------------------------------------------- 5. ștampila pe orice BLOCANT
def test_stampila_si_la_blocant_de_desen():
    inp = {"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 800, "schema_pamant": "TN-S", "plecari": [
        {"nume": "Motoare 1", "P_kW": 11, "receptor": "motor"}, {"nume": "Motoare 2", "P_kW": 11, "receptor": "motor"},
        {"nume": "Motoare 3", "P_kW": 11, "receptor": "motor"},
        {"nume": "TE1 linie ambalare", "copii": [{"nume": "Benzi 1", "P_kW": 2.2}, {"nume": "Benzi 2", "P_kW": 2.2}]}]}
    m, _ = constructor.genereaza(inp)
    v = validare.valideaza(m)
    if not v["blocheaza"]:
        pytest.skip("desenul nu mai produce BLOCANT de topologie (V82) — nimic de ștampilat")
    cv = layout.build(m)
    assert cv.meta.get("blocaj")
    assert any("NEVERIFICAT" in getattr(it, "s", "") for it in cv.items)


def test_fara_blocant_fara_stampila():
    m, _ = constructor.genereaza({"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 400,
                                  "plecari": [{"nume": "Pompa", "P_kW": 11}]})
    assert not validare.valideaza(m)["blocheaza"] and not layout.build(m).meta.get("blocaj")


# ------------------------------------------------------------------------------- 6. CEF 800 V / PT existent / Ik3 presupus
@pytest.mark.parametrize("n_t", [1, 2])
def test_cef_800v_reglaje_ordonate_si_cu_trafo_sub_injectie(n_t):
    inp = {"tip_schema": "cef", "masura": "MT", "pt_Sn_kVA": 1600, "n_trafo": n_t, "U_inv_ca_V": 800, "retea": "tri",
           "invertoare": [{"n": 5 * n_t, "Pn_kW": 300, "model": "SUN2000-330KTL-H1"}]}
    m, r = constructor.genereaza(inp)
    z = r["rezultat"]
    assert any(v["cod"] == "V67" for v in _bl(r))             # trafo sub injecție rămâne semnalat
    qjt = z["PT"]["Q_JT"]
    qgs = [s["QG"] for s in z["sectii"]] if z.get("sectii") else [z["QG"]]
    assert all(qjt["Ir_A"] >= q["Ir_A"] - 1e-6 for q in qgs), (qjt, qgs)


def test_cef_pt_existent_plecare_noua_din_tgjt():
    inp = {"tip_schema": "cef", "masura": "JT", "pt_Sn_kVA": 1000, "pt_existent": True, "L_racord_m": 40,
           "retea": "tri", "invertoare": [{"n": 8, "Pn_kW": 100, "model": "SUN2000-100KTL-M2"}]}
    m, r = constructor.genereaza(inp)
    z = r["rezultat"]
    assert not _bl(r), _bl(r)
    q = z["Q_PT"]
    assert q["Ir_A"] >= z["QG"]["Ir_A"] and q["Icu_kA"] >= z["trafo"]["Ik3max_bara_kA"]
    copii = m["plecari"][0].get("copii") or []
    assert copii and any(a.get("ref") == "QPT" for a in copii[0]["aparate"])
    assert not any(str(o["lista"][0]).startswith("Anvelopă") for o in m["materiale"])   # PT existent: fără post nou


def test_cablu_impus_cu_ik3_presupus_nu_blocheaza():
    inp = {"tip_schema": "cef", "racord": "tg_existent", "retea": "tri", "L_racord_m": 45,
           "invertoare": [{"n": 1, "Pn_kW": 30, "model": "SUN2000-30KTL-M3"}],
           "cablu_C0": {"material": "Cu", "S_fortat": 25}}
    r = calculeaza(inp)
    assert not _bl(r), _bl(r)
    assert any(v["cod"] in ("V35", "V36") and v["nivel"] == "AVERTISMENT" for v in r["verificari"])
    # cu Ik3 DECLARAT, secțiunea impusă insuficientă rămâne BLOCANT
    r2 = calculeaza(dict(inp, Ik3_TG_kA=25))
    assert any(v["cod"] in ("V35", "V36") for v in _bl(r2))


def test_cablu_invertor_impus_ramane_pe_invertor():
    inp = {"tip_schema": "cef", "racord": "tg_existent", "retea": "tri",
           "invertoare": [{"n": 1, "Pn_kW": 30, "model": "SUN2000-30KTL-M3"}],
           "cablu_inv": {"material": "Cu", "S_fortat": 25, "L": 45}}
    r = calculeaza(inp)
    inv = r["rezultat"]["invertoare"][0]
    assert inv["S_faza_mm2"] == 25 and "C0" not in r["rezultat"]


# ------------------------------------------------------------------------------- 7. locuință
@pytest.mark.parametrize("p,tri,cal", [(3.7, False, 20), (7.4, False, 40), (11, True, 20), (22, True, 40)])
def test_calibru_ve_din_puterea_statiei(p, tri, cal):
    assert calibru_ve(p, tri) == cal


def _circ(r):
    return [c for g in r["rezultat"]["grupe_DDR"] for c in g["circuite"]]


def _loc(circ, **alim):
    return {"tip_schema": "locuinta", "retea": "tri", "schema_pamant": "TN-C-S", "alimentare": alim,
            "circuite": [{"nume": "Iluminat", "receptor": "iluminat"}, {"nume": "Prize", "receptor": "prize"}] + circ}


def test_ve_11kw_tri_c20_nu_c40():
    r = calculeaza(_loc([{"nume": "Încărcare VE", "receptor": "vehicul_electric", "P_kW": 11}], P_aprobata_kW=16))
    ve = [c for c in _circ(r) if "VE" in c["nume"]][0]
    assert ve["protectie"]["In_A"] == 20


def test_ve_peste_q_bransament_blocant_cu_intrebare():
    r = calculeaza(_loc([{"nume": "Încărcare VE", "receptor": "vehicul_electric", "P_kW": 7.4, "faza": "L1"}],
                        P_aprobata_kW=16))
    b = [v for v in _bl(r) if v["cod"] == "V40" and "VE" in v["obiect"]]
    assert b and all(v.get("intrebare") for v in b) and "DLM" in b[0]["remediere"]


def test_v56_mesaj_corect_la_q_mare_si_ib_mic():
    r = calculeaza(_loc([], P_aprobata_kW=15, In_Q_bransament_A=100))
    v56 = [v for v in r["verificari"] if v["cod"] == "V56"]
    assert v56 and "> 80" not in v56[0]["mesaj"] and "Q branșament 100" in v56[0]["mesaj"]


def test_sauna_declarata_de_doua_ori_desenata_o_data():
    m, r = constructor.genereaza(dict(_loc([{"nume": "Saună", "receptor": "sauna", "P_kW": 9, "faza": "3F"},
                                            {"nume": "Saună", "receptor": "sauna", "L_m": 25, "faza": "3F"}]),
                                      schema_pamant="TT", RA_ohm=12))
    s = [c for c in _circ(r) if c["nume"] == "Saună"]
    assert len(s) == 1 and s[0]["P_kW"] == 9 and s[0]["L_m"] == 25


def test_sauna_cu_date_contradictorii_ramane_dubla():
    r = calculeaza(_loc([{"nume": "Saună", "receptor": "sauna", "P_kW": 9}, {"nume": "Saună", "receptor": "sauna",
                                                                           "P_kW": 6}]))
    assert sum(1 for c in _circ(r) if c["nume"] == "Saună") == 2


def test_tt_prosumator_toate_circuitele_generice_au_ddr():
    m, _ = constructor.genereaza({"tip_schema": "prosumator", "schema_pamant": "TT", "RA_ohm": 4, "retea": "mono",
                                  "P_aprobata_kW": 8, "Pn_inv_kW": 6})
    gen = [p for p in m["plecari"] if "generic" in (p["sarcina"].get("sub") or "")]
    assert gen and all(p["aparate"][0]["tip"] == "rcbo" for p in gen)
    assert any("DDR pe fiecare circuit" in n for n in m["note"])


def test_eticheta_casetei_laterale_nu_taie_liniile():
    from engine.canvas import Line, Polyline, item_segments, seg_hits_box, text_bbox, Text
    m, _ = constructor.genereaza({"tip_schema": "prosumator", "retea": "tri", "P_aprobata_kW": 40, "schema_pamant": "TN-C-S",
                                  "invertoare": [{"n": 2, "Pn_kW": 17.5}]})
    cv = layout.build(m)
    segs = [s for it in cv.items if isinstance(it, (Line, Polyline)) for s in item_segments(it)]
    sb = [it for it in cv.items if isinstance(it, Text) and it.s.startswith("SB") and it.bold and it.h >= 2.5]
    assert sb
    for t in sb:
        bb = text_bbox(t)
        assert not any(seg_hits_box(a, b, bb, 0.3) for a, b in segs), t


def test_coloana_simbol_rupta_pe_randuri():
    from engine.layout import _rupe_refs
    ref = "Iluminat exterior grădină, Prize exterior terasă, Încărcare vehicul electric garaj, Q12.3"
    rand = _rupe_refs(ref, 1.6, 18.5)
    from engine.canvas import text_width
    assert len(rand) > 1 and all(text_width(s, 1.6, True) * 1.1 <= 18.5 + 1e-6 for s in rand)


# ------------------------------------------------------------------------------- 8. BMPT peste 250 A
def test_bmpt_presupus_cu_q1_declarat_400a_blocant():
    r = calculeaza({"tip_schema": "tablou", "schema_pamant": "TN-S", "In_Q1_A": 400,
                    "plecari": [{"nume": "Chiller", "P_kW": 120}]})
    b = [v for v in _bl(r) if v["cod"] == "V50"]
    assert b and "PRESUPUS" in b[0]["mesaj"] and b[0].get("intrebare")


def test_bmpt_declarat_peste_250a_blocant():
    r = calculeaza({"tip_schema": "tablou", "origine": "bmpt", "schema_pamant": "TN-C-S",
                    "plecari": [{"nume": "TD1", "P_kW": 120}, {"nume": "TD2", "P_kW": 120}]})
    assert any(v["cod"] == "V50" for v in _bl(r))
