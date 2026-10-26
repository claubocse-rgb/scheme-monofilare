"""Runda 8 (teste/r8/industrial.md, teste/r8/locuinte.md) — partea de MOTOR / DESEN: consumatorii de siguranță la
incendiu pe consumator (tablou, PT, GE+ATS), compensare la tablou / PT, PT și Q1 subdimensionate, tablou secundar al
locuinței (fără 4 × 3×240 mm²), Q presupus, RCCB tip A și MCB în back-up la branșament, comutator manual I-0-II, PTA pe
stâlp, planșe cu multe circuite (rânduri), planșă goală → BLOCANT."""
import pytest

from engine import constructor, layout, validare
from engine.calc import calculeaza


def _b(r):
    return [v for v in r["verificari"] if v["nivel"] == "BLOCANT"]


def _v(r, cod, nivel=None):
    return [v for v in r["verificari"] if v["cod"] == cod and (nivel is None or v["nivel"] == nivel)]


def _toate(m):
    out = []

    def walk(bs, cale):
        for b in bs:
            c2 = cale + (b.get("aparate") or [])
            out.append((b, c2))
            walk(b.get("copii") or [], c2)
    walk(m.get("plecari") or [], [a for i in m.get("intrari") or [] for a in i.get("aparate") or []])
    return out


def _ddr_pe_cale(cale):
    return [a for a in cale if a.get("tip") in ("rccb", "rcbo", "mccb_dif")]


# --------------------------------------------------------------------------- 1. siguranță la incendiu, generic
SIGURANTA = {
    "tablou_desfumare": {"tip_schema": "tablou", "origine": "tg_existent", "schema_pamant": "TN-S", "plecari": [
        {"nume": "Ventilatoare desfumare 1", "P_kW": 11}, {"nume": "Ventilatoare desfumare 2", "P_kW": 11},
        {"nume": "Clapete 1", "P_kW": 0.1}, {"nume": "Clapete 2", "P_kW": 0.1}]},
    "tablou_bmpt_mixt": {"tip_schema": "tablou", "origine": "bmpt", "schema_pamant": "TN-C-S", "plecari": [
        {"nume": "Pompa hidranti", "P_kW": 7.5}, {"nume": "Prize", "P_kW": 3, "receptor": "prize"},
        {"nume": "Utilaj", "P_kW": 15}]},
    "tg_pt_pompa_incendiu": {"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 630, "schema_pamant": "TN-S",
                             "plecari": [{"nume": "Pompa incendiu", "P_kW": 45}, {"nume": "Pompa tehnologica", "P_kW": 45},
                                         {"nume": "Iluminat", "P_kW": 10}]},
    "tablou_titlu_tdsi": {"tip_schema": "tablou", "titlu_tablou": "TDSI sprinklere", "origine": "tg_existent",
                          "schema_pamant": "TN-S", "plecari": [{"nume": "Electropompa", "P_kW": 55, "pornire": "stea_triunghi"},
                                                               {"nume": "Pompa pilot", "P_kW": 2.2}]},
    "ge_tdsi": {"tip_schema": "ge_ats", "schema_pamant": "TN-S", "Sn_GE_kVA": 125, "sursa_retea": "tgd",
                "P_sarcina_kW": 57.2, "titlu_tablou": "TDSI sprinklere",
                "consumatori": [{"nume": "Electropompa", "P_kW": 55, "pornire": "stea_triunghi"}, {"nume": "Jockey", "P_kW": 2.2}]},
    "ge_jockey_fara_titlu": {"tip_schema": "ge_ats", "schema_pamant": "TN-S", "Sn_GE_kVA": 125, "sursa_retea": "tgd",
                             "P_sarcina_kW": 57.2, "consumatori": [{"nume": "Electropompa", "P_kW": 55, "pornire": "stea_triunghi"},
                                                                    {"nume": "Jockey", "P_kW": 2.2}]},
    "pt_lift_pompieri": {"tip_schema": "pt", "Sn_kVA": 630, "plecari": [
        {"nume": "TG", "P_kW": 200}, {"nume": "Lift de pompieri", "P_kW": 15}, {"nume": "Presurizare scara", "P_kW": 7.5}]},
}


@pytest.mark.parametrize("cid", sorted(SIGURANTA))
def test_consumator_siguranta_fara_ddr_si_fe180_in_orice_schema(cid):
    m, r = constructor.genereaza(SIGURANTA[cid])
    assert not [v for v in _b(r) if v["cod"] == "V97"], _b(r)
    sig = [(b, cale) for b, cale in _toate(m) if b.get("siguranta")]
    assert sig, "niciun consumator de siguranță recunoscut"
    for b, cale in sig:
        assert not _ddr_pe_cale(cale), (b["sarcina"]["titlu"], [a.get("ref") for a in _ddr_pe_cale(cale)])
        assert "FE180" in (b.get("cablu") or {}).get("text", "")
        for a in b.get("aparate") or []:
            if a.get("tip") == "releu_termic":
                assert "doar semnalizare" in a["spec"]


def test_y_delta_pastrat_si_pompele_neconsumate_in_consumatori():
    m, r = constructor.genereaza(SIGURANTA["ge_jockey_fara_titlu"])
    titluri = [b["sarcina"]["titlu"] for b in m["plecari"]]
    assert "Electropompa" in titluri and "Jockey" in titluri and "Consumatori" not in titluri
    ep = next(b for b in m["plecari"] if b["sarcina"]["titlu"] == "Electropompa")
    assert any(a.get("tip") == "pornitor_yd" for a in ep["aparate"])
    assert not any(a.get("ref") == "DDR-G" for a in m["intrari"][1]["aparate"])


def test_mixt_pompa_incendiu_inaintea_q1():
    m, r = constructor.genereaza(SIGURANTA["tg_pt_pompa_incendiu"])
    z = r["rezultat"]
    assert z["siguranta"] == "mixt" and z["Q1_general"]["In_A"] < z["Q1_C1"]["protectie"]["In_A"]
    pi = next(p for p in z["plecari"] if p["nume"] == "Pompa incendiu")
    pt = next(p for p in z["plecari"] if p["nume"] == "Pompa tehnologica")
    assert pi["inainte_Q1"] and pi["rezistent_foc"] and pi["aparataj_motor"]["releu_termic_doar_semnalizare"]
    assert not pt.get("siguranta") and not pt["aparataj_motor"].get("releu_termic_doar_semnalizare")
    # desen: intrarea fără Q1; pompa de incendiu pe bara de racord, Q1 general = grupă cu consumatorii normali
    assert not m["intrari"][0]["aparate"]
    g = next(b for b in m["plecari"] if b.get("grup"))
    assert g["aparate"][0]["ref"] == "Q1" and {c["sarcina"]["titlu"] for c in g["copii"]} == {"Pompa tehnologica", "Iluminat"}


def test_tablou_desfumare_intreg_de_siguranta_ks1_si_c1_fe180():
    m, r = constructor.genereaza(SIGURANTA["tablou_desfumare"])
    z = r["rezultat"]
    assert z["siguranta"] == "tot" and z["bilant"]["ks"] <= 1
    assert z["Q1_C1"]["rezistent_foc"] and "FE180" in m["intrari"][0]["cablu"]["text"]
    ib_vent = sum(p["Ib_A"] for p in z["plecari"] if "desfumare" in p["nume"])
    assert z["Q1_C1"]["protectie"]["In_A"] >= ib_vent           # ventilatoarele funcționează simultan


def test_bmpt_fara_rccb_presupus_pe_calea_sigurantei():
    m, r = constructor.genereaza(SIGURANTA["tablou_bmpt_mixt"])
    assert r["rezultat"]["fara_ddr_amonte_siguranta"] and "RCCB" not in m["intrari"][0]["sursa"]["sub"]


def test_ddr_declarat_in_amonte_blocant():
    r = calculeaza(dict(SIGURANTA["tablou_desfumare"], IdN_amonte_mA=300))
    assert any(v["cod"] == "V97" for v in _b(r))


def test_siguranta_in_tt_blocant_explicit():
    r = calculeaza(dict(SIGURANTA["tg_pt_pompa_incendiu"], schema_pamant="TT", RA_ohm=10))
    assert any(v["cod"] == "V97" for v in _b(r))


def test_pompa_rezerva_neadunata():
    inp = {"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 400, "schema_pamant": "TN-S", "plecari": [
        {"nume": "Pompa incendiu", "P_kW": 37}, {"nume": "Pompa incendiu rezerva", "P_kW": 37}]}
    z = calculeaza(inp)["rezultat"]
    assert z["bilant"]["Pi_kW"] == pytest.approx(37)
    assert next(p for p in z["plecari"] if "rezerva" in p["nume"])["rezerva"]


def test_validator_model_blocheaza_ddr_pe_calea_sigurantei():
    m = {"intrari": [{"aparate": [{"tip": "rccb", "ref": "DDR1"}]}],
         "plecari": [{"siguranta": True, "sarcina": {"titlu": "Pompa incendiu"}, "aparate": [], "cablu": {"text": "CYABY 5×6"}}]}
    r = {"verificari": []}
    constructor._verifica_model_r8(m, r)
    assert len([v for v in r["verificari"] if v["cod"] == "V97"]) == 2


# --------------------------------------------------------------------------- 2. compensare la tablou și PT
@pytest.mark.parametrize("inp", [
    {"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 1000, "compensare_kvar": 250,
     "plecari": [{"nume": "TD1", "P_kW": 200}, {"nume": "TD2", "P_kW": 150}]},
    {"tip_schema": "pt", "Sn_kVA": 1600, "n_trafo": 2, "compensare_kvar": 300,
     "plecari": [{"nume": "TD1", "P_kW": 400}, {"nume": "TD2", "P_kW": 300}]}])
def test_compensare_tablou_si_pt(inp):
    m, r = constructor.genereaza(inp)
    c = next(p for p in r["rezultat"]["plecari"] if p.get("compensare"))
    assert c["protectie"]["In_A"] >= 1.43 * c["In_cap_A"] - 1e-6
    assert any("kvar" in b["sarcina"]["titlu"] for b in m["plecari"])


# --------------------------------------------------------------------------- 3. PT / Q1 subdimensionate
def test_tablou_300kw_pe_pt_250_blocant():
    r = calculeaza({"tip_schema": "tablou", "origine": "pt_propriu", "pt_Sn_kVA": 250, "schema_pamant": "TN-S",
                    "plecari": [{"nume": "Compresor", "P_kW": 160}, {"nume": "Cuptor", "P_kW": 120}, {"nume": "Iluminat", "P_kW": 20}]})
    assert _v(r, "V62", "BLOCANT") and _v(r, "V60", "BLOCANT")


def test_pt_bilant_declarat_peste_sn_blocant_dar_calibre_avertisment():
    r = calculeaza({"tip_schema": "pt", "Sn_kVA": 250, "plecari": [{"nume": "A", "P_kW": 160}, {"nume": "B", "P_kW": 140}]})
    assert _v(r, "V62", "BLOCANT")
    r = calculeaza({"tip_schema": "pt", "Sn_kVA": 400, "plecari": [{"nume": f"TD-{k}", "In_A": 250} for k in range(4)]})
    assert _v(r, "V62", "AVERTISMENT") and not _v(r, "V62", "BLOCANT")


def test_q1_sub_ib_din_bilant_blocant():
    r = calculeaza({"tip_schema": "tablou", "origine": "tg_existent", "P_kW": 3, "plecari": [
        {"nume": "Compresor 1", "P_kW": 55, "pornire": "vfd"}, {"nume": "Compresor 2", "P_kW": 55, "pornire": "vfd"}]})
    assert any(v["cod"] == "V04" and v["obiect"] == "Q1/C1" for v in _b(r))


# --------------------------------------------------------------------------- 4. locuință / branșament
LOC_TD = {"tip_schema": "locuinta", "retea": "mono", "schema_pamant": "TN-C-S",
          "tablouri_secundare": [{"nume": "TD Anexa", "circuite": [{"nume": "Plita", "P_kW": 3.5}]}],
          "circuite": [{"nume": "Iluminat", "receptor": "iluminat"}, {"nume": "Prize", "receptor": "prize"}],
          "alimentare": {"P_aprobata_kW": 9, "L_coloana_m": 30}}


def _td(r):
    return next(c for g in r["rezultat"]["grupe_DDR"] for c in g["circuite"] if c["nume"] == "TD Anexa")


def test_td_monofazat_fara_cabluri_absurde_cu_ddr_si_selectivitate():
    r = calculeaza(LOC_TD)
    f = _td(r)
    assert f["n_paralel"] == 1 and f["S_faza_mm2"] <= 16
    pl = f["tablou_secundar"]["plecari"]
    assert all(p.get("DDR") and p["DDR"]["IdN_mA"] == 30 for p in pl)
    assert f["protectie"]["In_A"] > max(p["protectie"]["In_A"] for p in pl)


def test_td_cablu_declarat_ramane_pe_plecare():
    inp = dict(LOC_TD, tablouri_secundare=[dict(LOC_TD["tablouri_secundare"][0], L_m=30, cablu={"S_fortat": 6})])
    f = _td(calculeaza(inp))
    assert f["S_faza_mm2"] == 6 and f["L_m"] == 30


def test_q_presupus_pereche_atr_in_toleranta_1_13():
    r = calculeaza({"tip_schema": "locuinta", "retea": "tri", "schema_pamant": "TT", "RA_ohm": 10,
                    "circuite": [{"nume": "Iluminat", "receptor": "iluminat"}], "alimentare": {"P_aprobata_kW": 22}})
    v = [x for x in _v(r, "V46") if x["obiect"] == "Q"]
    assert v and "perechea ATR" in v[0]["mesaj"] and "limita blocului" not in v[0]["mesaj"]


def test_bransament_rccb_tip_a_si_mcb_back_up():
    m, r = constructor.genereaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 20, "L_coloana_m": 50,
                                  "schema_pamant": "TN-C-S"})
    assert r["rezultat"]["RCCB"]["tip"] == "A"
    q = next(a for a in m["intrari"][0]["aparate"] if a.get("ref") == "Q")
    assert "back-up" in " ".join(q["lista"])
    assert calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 20,
                       "DDR_bransament_tip": "AC"})["rezultat"]["RCCB"]["tip"] == "AC"


# --------------------------------------------------------------------------- 5. comutator manual
def test_comutator_manual_desenat_i0ii_nu_ats():
    m, r = constructor.genereaza({"tip_schema": "ge_ats", "Sn_GE_kVA": 40, "In_Q_retea_A": 63, "sursa_retea": "bmpt",
                                  "comutare": "manual", "consumatori": [{"nume": "Muls", "P_kW": 7.5}, {"nume": "Racire", "P_kW": 11}]})
    assert not _v(r, "V87")
    txt = " ".join(" ".join(a.get("lista") or []) for i in m["intrari"] for a in i["aparate"])
    assert "I-0-II" in txt and "ATS" not in txt and "AC-33B" not in txt
    assert "automat" not in m["carcasa"]["sub"]


# --------------------------------------------------------------------------- 6. PTA pe stâlp
def test_pta_pe_stalp_fara_celule_de_interior():
    m, r = constructor.genereaza({"tip_schema": "pt", "Sn_kVA": 250, "pt_aerian": True,
                                  "plecari": [{"nume": f"TD-{k}", "In_A": 125} for k in range(1, 4)]})
    txt = " ".join(" ".join(a.get("lista") or []) for a in m["intrari"][0]["aparate"])
    assert "Celulă" not in txt and "Separator tripolar de exterior" in txt and "Siguranțe fuzibile MT de exterior" in txt
    assert m["intrari"][0]["sursa"]["titlu"].startswith("LEA") and m["carcasa"]["titlu"] == "TDJT"
    assert not any("Anvelopă" in x["lista"][0] for x in m["materiale"])
    assert not r["rezultat"].get("servicii_proprii")


# --------------------------------------------------------------------------- 7. multe circuite: rânduri, 1P+N
def test_44_circuite_pe_randuri_lizibile_si_monofazate():
    m, r = constructor.genereaza({"tip_schema": "tablou", "origine": "tg_existent", "schema_pamant": "TN-S",
                                  "circuite_finale": True, "plecari": [{"nume": "Iluminat", "P_kW": 0.8, "n_circuite": 20},
                                                                       {"nume": "Prize", "P_kW": 2, "n_circuite": 24}]})
    assert all(p["retea"] == "mono" for p in r["rezultat"]["plecari"])
    assert all(b["aparate"][0]["param"]["poli"] in ("2P", "1P+N") for b in m["plecari"])
    L = layout._layout(m)
    assert len(L.randuri) >= 3 and L.meta["scara"] >= 0.6
    assert not [v for v in validare.valideaza(m)["verificari"] if v["cod"] == "V95"]


# --------------------------------------------------------------------------- 8. planșă goală
@pytest.mark.parametrize("inp", [{"tip_schema": "tablou", "plecari": []}, {"tip_schema": "pt", "Sn_kVA": 400},
                                 {"tip_schema": "ge_ats"}, {"tip_schema": "nimic"}])
def test_plansa_goala_are_blocant(inp):
    m, r = constructor.genereaza(inp)
    if not (m.get("intrari") or m.get("plecari")):
        assert _b(r)
