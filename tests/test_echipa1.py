"""Regresii echipa de testare 1 (teste/echipa1/inginer.md, ux.md) — MOTOR + CONSTRUCTOR + INTERPRETOR.

Fiecare P0 / P1 din raportul inginerului (și problemele de calcul 1, 2, 5 din ux.md) are cel puțin un test.
Rulare: cd /home/claude/sm && python3 -m pytest -q tests/test_echipa1.py
"""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

RAD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAD))

import app  # noqa: E402
from engine import constructor, layout, validare, planse  # noqa: E402
from engine.calc import calculeaza  # noqa: E402
from engine.confirmare import campuri_lipsa  # noqa: E402
from engine.interpretor import interpreteaza  # noqa: E402

ING = RAD / "tests" / "date" / "echipa1"  # modelele lucrărilor inginerului (doar calc)


def _calc(caz):
    return json.loads((ING / f"{caz}.json").read_text(encoding="utf-8"))["calc"]


def _gen(inp):
    m, r = constructor.genereaza(copy.deepcopy(inp))
    return m, r, validare.valideaza(m)


def _bl(v):
    return [x for x in v["verificari"] if x["nivel"] == "BLOCANT"]


def _ca_interfata(calc):
    """intrarea așa cum o trimite interfața: `cablu: {}` peste tot (P0-1)"""
    c = copy.deepcopy(calc)
    c["cablu"] = {}
    for pl in c.get("plecari") or []:
        pl["cablu"] = {}
    if isinstance(c.get("alimentare"), dict):
        c["alimentare"]["cablu"] = {}
    return c


def _toate_aparatele(m):
    out = []

    def w(b):
        out.extend(b.get("aparate") or [])
        out.extend(b.get("aparate_tablou") or [])
        for c in b.get("copii") or []:
            w(c)
    for b in (m.get("intrari") or []) + (m.get("plecari") or []):
        w(b)
    if m.get("jonctiune"):
        w(m["jonctiune"])
    return out


# ============================================================================================ P0
@pytest.mark.parametrize("tile", sorted(app.SABLOANE))
def test_P0_1_tile_neatins_fara_v96(tile):
    _, _, v = _gen(_ca_interfata(app.SABLOANE[tile][2]))
    assert not [x for x in v["verificari"] if x["cod"] == "V96"], tile
    if tile != "locuinta":                 # casa: rețeaua e obligatorie (V07), corect
        assert not v["blocheaza"], _bl(v)


def test_P0_1_pt_cu_chei_goale_se_exporta():
    c = dict(_ca_interfata(app.SABLOANE["pt"][2]), nota="", observatii=None, priza_extra=[])
    _, _, v = _gen(c)
    assert not v["blocheaza"], _bl(v)
    # o cheie NEGOALĂ necunoscută rămâne refuzată (V96) — curățarea e doar pentru valorile goale
    _, _, v = _gen(dict(c, cheie_necunoscuta=5))
    assert any(x["cod"] == "V96" for x in _bl(v))


def test_P0_2_cef_pt_existent_qpt_pe_plecarea_noua():
    m, r, v = _gen(_calc("C01b_cef_100"))
    assert not v["blocheaza"]
    pl = m["plecari"][0]
    # C0 → QPT (aparatul de intrare al plecării noi din TGJT) → bara JT; TGJT existent NU trece prin QPT
    assert [a["ref"] for a in pl.get("aparate_tablou") or []] == ["QPT"]
    titluri = [c["sarcina"]["titlu"] for c in pl["copii"]]
    assert any(t.startswith("T EXISTENT") for t in titluri) and "PLECĂRI EXISTENTE" in titluri
    assert not any(a.get("ref") == "QPT" for c in pl["copii"] for a in c.get("aparate") or [])
    assert c_ok(layout.build(m))


def c_ok(c):
    from engine.topologie import coliziuni
    return coliziuni(c) == []


def test_P0_3_stea_triunghi_doua_cabluri_fara_n():
    m, r, v = _gen(_calc("T01_tg_hala"))
    mot = [p for p in r["rezultat"]["plecari"] if p["nume"].startswith("Motoare")]
    assert len(mot) == 3
    for p in mot:
        assert p["cabluri_yd"] == 2 and p["fara_N"] and p["S_N_mm2"] is None
        assert p["cablu"].startswith("2 cabluri") and "(3 + PE)" in p["cablu"]
        assert p["Iz_corectat_A"] >= p["Ib_A"] / 3 ** 0.5 - 1e-6           # fiecare cablu la Ib/√3
    s = json.dumps(m, ensure_ascii=False)
    assert "2 × (3 + PE)" in s
    cab = [x for x in m["materiale"] if "Motoare 1" in x["ref"] and x["lista"][0].startswith("Cablu")]
    L = mot[0]["L_m"]
    assert cab and cab[0]["cantitate"] >= 3 * 2 * L                    # 2 cabluri pe fiecare dintre cele 3 motoare


def test_P0_3_stea_triunghi_delta_u_si_iz_pe_cablu():
    inp = {"tip_schema": "tablou", "retea": "tri", "origine": "pt_propriu", "pt_Sn_kVA": 630, "L_alimentare_m": 20,
           "plecari": [{"nume": "M1", "P_kW": 30, "receptor": "motor", "pornire": "stea_triunghi", "L_m": 60}]}
    r = calculeaza(inp)
    p = r["rezultat"]["plecari"][0]
    assert p["cabluri_yd"] == 2
    assert p["Iz_min_A"] == pytest.approx(p["Ib_A"] / 3 ** 0.5, rel=1e-3)


@pytest.mark.parametrize("caz,fv", [("L02_casa_tri_pc_ve", False), ("B01_bransament_nou_tri", False),
                                    ("T01_tg_hala", False), ("G01b_ge_ats", False), ("C01b_cef_100", True),
                                    ("R01_prosumator_bat", True)])
def test_P0_4_pachet_a3_fv_doar_la_cef_prosumator(caz, fv):
    m, _, _ = _gen(_calc(caz))
    lst = planse.planse_din_model(m)
    coduri = [c for c, _ in lst]
    if fv:
        assert any("/FV" in c for c in coduri)
    else:
        assert len(lst) == 1 and not any("FV" in c for c in coduri)
        assert not any((p.get("cartus") or {}).get("denumire1", "").startswith("SCHEMĂ CONEXIUNI RELEU") for _, p in lst)


def test_P0_5_bess_independent_trece_de_confirmare():
    it = interpreteaza("Sistem de stocare BESS 250 kW / 500 kWh racordat în JT la tabloul general al unei fabrici, "
                       "cablu 40 m", foloseste_llm=False)
    intr = it["intrare_fizica"]
    assert intr["tip_schema"] == "cef" and not intr.get("invertoare")
    assert campuri_lipsa(intr) == []                                  # nu se cer invertoare PV
    out = app._verifica_declarate(intr)
    assert out["lipsa"] == [] and out.get("blocante", 0) == 0
    _, _, v = _gen(intr)
    assert not v["blocheaza"], _bl(v)
    # CEF fără invertoare ȘI fără BESS: lipsește ceva de desenat
    assert campuri_lipsa({"tip_schema": "cef"})[0]["camp"] == "invertoare"


# ============================================================================================ P1 locuință
LC = lambda n, r, **o: dict(nume=n, receptor=r, **o)   # noqa: E731
PC_VE = [LC("Iluminat parter", "iluminat"), LC("Iluminat etaj", "iluminat"), LC("Iluminat exterior", "iluminat"),
         LC("Prize parter", "prize"), LC("Prize etaj", "prize"), LC("Prize bucătărie", "prize_bucatarie"),
         LC("Plită", "plita", faza="3F"), LC("Cuptor", "cuptor"), LC("Prize baie parter", "prize_baie"),
         LC("Prize baie etaj", "prize_baie"), LC("Mașină de spălat rufe", "masina_spalat_rufe"),
         LC("Mașină de spălat vase", "masina_spalat_vase"), LC("Pompă de căldură", "pompa_caldura", faza="3F"),
         LC("Încărcător mașină electrică", "vehicul_electric", faza="3F", P_kW=11), LC("Prize exterior", "prize_exterior"),
         LC("Poartă automată", "poarta_automata")]


def _casa(retea, pa, q, circ, **extra):
    al = {"P_aprobata_kW": pa, "L_coloana_m": 25}
    if q:
        al["In_Q_bransament_A"] = q
    return dict({"tip_schema": "locuinta", "retea": retea, "schema_pamant": "TN-C-S", "alimentare": al,
                 "circuite": copy.deepcopy(circ)}, **extra)


@pytest.mark.parametrize("pa,q", [(15, 25), (20, 32), (25, 40)])
def test_P1_ux1_casa_pc_ve_tablou_tipic_nu_e_blocat(pa, q):
    _, r, v = _gen(_casa("tri", pa, q, PC_VE))
    assert not v["blocheaza"], _bl(v)
    av = [x for x in v["verificari"] if x["cod"] == "V46" and x["obiect"] == "Q" and x["nivel"] == "AVERTISMENT"]
    assert av
    for x in av:
        # remedieri aplicabile: fără „mută pe altă fază” la faze echilibrate, fără DLM inexistent
        assert "altă fază" not in x["remediere"] and "DLM" not in x["remediere"]


@pytest.mark.parametrize("pa,q", [(15, 25), (20, 32), (25, 40)])
def test_P1_ux2_q_gol_sau_scris_acelasi_verdict(pa, q):
    gol = _gen(_casa("tri", pa, None, PC_VE))[2]
    scris = _gen(_casa("tri", pa, q, PC_VE))[2]
    q_gol = gol["rezultat"]["alimentare"]["Q"]["In_A"]
    scris_acelasi = _gen(_casa("tri", pa, q_gol, PC_VE))[2]
    assert gol["blocheaza"] == scris_acelasi["blocheaza"]
    niv = lambda v: sorted((x["cod"], x["nivel"]) for x in v["verificari"] if x["cod"] == "V46" and x["obiect"] == "Q"  # noqa
                           and "nedeclarat —" not in x["mesaj"])
    assert niv(gol) == niv(scris_acelasi)
    # presupusul e doar marcat în mesaj
    assert any(x["mesaj"].startswith("Q branșament presupus") for x in gol["verificari"] if x["cod"] == "V46")
    assert scris["rezultat"]["alimentare"]["Q"]["In_A"] == q                 # Q declarat nu se înlocuiește


def test_P1_q_declarat_nu_se_inlocuieste_niciodata():
    for q in (16, 20, 25, 32, 40):
        r = calculeaza(_casa("tri", 15, q, PC_VE))
        assert r["rezultat"]["alimentare"]["Q"]["In_A"] == q


def test_P1_1_casa_mono_7kw_nu_e_blocata():
    c = {"tip_schema": "locuinta", "retea": "mono", "schema_pamant": "TN-C-S",
         "alimentare": {"P_aprobata_kW": 7, "In_Q_bransament_A": 32, "L_coloana_m": 15},
         "circuite": [LC("Iluminat interior", "iluminat"), LC("Iluminat exterior", "iluminat"), LC("Prize camere", "prize"),
                      LC("Plită", "plita", P_kW=7), LC("Cuptor", "cuptor", P_kW=3.5), LC("Boiler", "boiler", P_kW=2),
                      LC("Centrală termică", "centrala_termica"), LC("Mașină de spălat rufe", "masina_spalat_rufe"),
                      LC("Mașină de spălat vase", "masina_spalat_vase")]}
    _, r, v = _gen(c)
    assert not v["blocheaza"], _bl(v)
    assert r["rezultat"]["alimentare"]["Q"]["In_A"] == 32
    # panoul de confirmare nu propune înlocuirea Q-ului OD
    assert app._verifica_declarate(copy.deepcopy(c))["schimbari"] == []


def test_P1_sarcini_continue_peste_q_blocant_cu_limitare_ve_aplicabila():
    c = {"tip_schema": "locuinta", "retea": "mono", "schema_pamant": "TN-C-S",
         "alimentare": {"P_aprobata_kW": 7, "In_Q_bransament_A": 32},
         "circuite": [LC("Iluminat", "iluminat"), LC("Prize", "prize"), LC("VE", "vehicul_electric", P_kW=7.4),
                      LC("PC", "pompa_caldura", P_kW=3)]}
    _, _, v = _gen(c)
    b = [x for x in _bl(v) if x["cod"] == "V46" and x["obiect"] == "Q"]
    assert b and "Limitare putere VE" in b[0]["remediere"]
    lim = float(re.search(r"cel mult (\d+(?:,\d+)?) kW", b[0]["remediere"]).group(1).replace(",", "."))
    c["circuite"][2]["limitare_kW"] = lim
    _, r, v = _gen(c)
    assert not v["blocheaza"], _bl(v)                                     # remedierea propusă chiar rezolvă
    ve = [x for g in r["rezultat"]["grupe_DDR"] for x in g["circuite"] if x.get("nume") == "VE"][0]
    assert ve["P_kW"] == pytest.approx(lim)


def test_P1_limitare_kw_doar_la_ve():
    c = _casa("tri", 15, 25, [LC("Iluminat", "iluminat"), LC("Prize", "prize", limitare_kW=2)])
    r = calculeaza(c)
    assert any(x["cod"] == "V12" and "stației de încărcare" in x["mesaj"] for x in r["verificari"])


def test_P1_2_circuite_scrise_nu_se_dubleaza():
    it = interpreteaza("Casă parter monofazată, putere aprobată 7 kW, Q 32 A, coloană 15 m, circuite: iluminat interior, "
                       "prize camere, plită 7 kW, cuptor 3,5 kW, boiler 2 kW", foloseste_llm=False)
    nume = [x["nume"] for x in it["intrare_fizica"]["circuite"]]
    assert nume == ["Iluminat interior", "Prize camere", "Plită", "Cuptor", "Boiler"]
    it = interpreteaza("apartament bloc 5 kW monofazat, coloană 25 m, circuite: prize camere, iluminat", foloseste_llm=False)
    assert len([x for x in it["intrare_fizica"]["circuite"] if x["receptor"] == "prize"]) == 1
    # fără nicio listă de circuite: setul implicit rămâne
    it = interpreteaza("casă parter monofazată 7 kW, coloană 15 m", foloseste_llm=False)
    assert len(it["intrare_fizica"]["circuite"]) >= 8


def test_P1_3_casa_cel_mult_a2_apartament_a3():
    m, _, _ = _gen(_calc("L02_casa_tri_pc_ve"))
    assert layout._layout(m).m["format"] in ("A3", "A2")
    m, _, _ = _gen(_calc("L03_apartament"))
    L = layout._layout(m)
    assert L.m["format"] == "A3" and any("anexă" in n for n in L.m.get("note") or [])


# ============================================================================================ P1 motor / interpretor
def test_P1_4_v35_fara_mesaj_contradictoriu():
    for caz in ("T01_tg_hala", "G01b_ge_ats"):
        _, r, _ = _gen(_calc(caz))
        for x in r["verificari"]:
            if x["cod"] in ("V35", "V36") and x["nivel"] != "INFO":
                mm = re.search(r"(\d+)×(\d+(?:,\d+)?) mm² < (\d+(?:,\d+)?) mm²", x["mesaj"]) or \
                    re.search(r"PE (\d+(?:,\d+)?) mm² < (\d+(?:,\d+)?) mm²", x["mesaj"])
                assert mm
                vals = [float(g.replace(",", ".")) for g in mm.groups()]
                stg = vals[0] * vals[1] if len(vals) == 3 else vals[0]
                assert stg < vals[-1], x["mesaj"]


def test_P1_5_atestat_dupa_tipul_lucrarii():
    # Ord. ANRE 134/2021 art. 9 alin. (1) (firme) + Ord. ANRE 66/2023 art. 9 (electricieni)
    m, r, _ = _gen(app.SABLOANE["pt"][2])
    assert "C1A" in m["cartus"]["atestat_necesar"] and "gr. IIIA" in m["cartus"]["atestat_necesar"]
    assert m["cartus"]["atestat_necesar_executie"].startswith("C2A") and "gr. IIIB" in m["cartus"]["atestat_necesar_executie"]
    m, r, _ = _gen(dict(_calc("L02_casa_tri_pc_ve")))
    assert "Bp" in m["cartus"]["atestat_necesar"] and "gr. IIA" in m["cartus"]["atestat_necesar"]
    assert "gr. IIB" in m["cartus"]["atestat_necesar_executie"]
    for tip, v58 in (("Bp", True), ("C2A", True), ("E2", True), ("C1A", False), ("Bp + C1A", False), ("C1B", False),
                     ("D1", False), ("E1", False), ("Ap", True)):
        m, r = constructor.genereaza(app.SABLOANE["pt"][2], cartus={"atestat_tip": tip})
        assert any(x["cod"] == "V58" for x in r["verificari"]) == v58, tip
    for tip, v58 in (("Bp", False), ("B", False), ("C1A", False), ("Be", True), ("C2A", True)):
        m, r = constructor.genereaza(dict(_calc("L02_casa_tri_pc_ve")), cartus={"atestat_tip": tip})
        assert any(x["cod"] == "V58" for x in r["verificari"]) == v58, tip


def test_coduri_anre_oficiale():
    # lista exactă din Ord. ANRE 134/2021 art. 9 alin. (1) lit. a)–q) și gradele din Ord. ANRE 66/2023 art. 9
    assert list(constructor.ATESTATE_ANRE) == ["A", "A1", "A2", "A3", "B", "Bp", "Be", "Bi", "C1A", "C1B", "C2A", "C2B",
                                               "D1", "D2", "E1", "E2", "E2PA"]
    assert list(constructor.GRADE_ANRE) == ["I", "IIA", "IIB", "IIIA", "IIIB", "IVA", "IVB"]
    assert constructor.atestat_include("D2") >= {"C2B", "C2A", "Be", "Bi", "A2", "A1"}
    assert "B" not in constructor.atestate_declarate("C1B")
    html = (Path(__file__).resolve().parents[1] / "static" / "index.html").read_text(encoding="utf-8")
    assert "'Ap'" not in html and "Bp + Ap" not in html
    for t in constructor.ATESTATE_ANRE:
        assert f"['{t}'," in html, t


@pytest.mark.parametrize("text,verif", [
    ("TD birouri trifazat, alimentare din TG cu cablu 40 m, iluminat birouri 3 circuite, prize birouri 6 circuite, "
     "prize server 3 kW, aer condiționat 4 × 3,5 kW",
     lambda i: sum(int(p.get("n_circuite") or 1) for p in i["plecari"]) == 3 + 6 + 1 + 4),
    ("tablou pompe 4 pompe de 5,5 kW cu convertizor, alimentare 30 m",
     lambda i: len(i["plecari"]) == 4 and all(p["P_kW"] == 5.5 for p in i["plecari"])),
    ("stație încărcare VE 2 × 22 kW, tablou 63 A, cablu 50 m",
     lambda i: i.get("In_Q1_A") == 63 and len(i["plecari"]) == 2 and not any(p["nume"] == "Tablou" for p in i["plecari"])),
    ("Grup electrogen 100 kVA cu ATS pentru consumatori vitali: pompe incendiu 15 kW, iluminat siguranță 2 kW, "
     "server 5 kW; alimentare normală din rețea 80 kW",
     lambda i: not any("normal" in c["nume"].lower() for c in i["consumatori"]) and i["P_sarcina_kW"] == 22),
    ("Post de transformare 630 kVA 20/0,4 kV, buclă LES, plecări: 250 A, 160 A, 160 A, 100 A, 63 A și compensare 150 kvar",
     lambda i: [p["In_A"] for p in i["plecari"]] == [250, 160, 160, 100, 63] and i["compensare_kvar"] == 150),
])
def test_P1_6_fraze_uzuale_fara_pierderi(text, verif):
    it = interpreteaza(text, foloseste_llm=False)
    assert verif(it["intrare_fizica"]), it["intrare_fizica"]
    assert not it.get("neconsumat")


def test_P1_8_ge_protectie_regim_ge_blocant_cu_solutii_aplicabile():
    c = _calc("G01b_ge_ats")
    _, _, v = _gen(c)
    b = [x for x in _bl(v) if x["cod"] in ("V85", "V97")]
    assert b and "Excitație susținută" in b[0]["remediere"] and "Legături echipotențiale" in b[0]["remediere"]
    for extra in ({"excitatie_sustinuta": True}, {"legaturi_echipotentiale": True}):
        _, r, v = _gen(dict(c, **extra))
        assert not v["blocheaza"], (extra, _bl(v))
    _, r, _ = _gen(dict(c, excitatie_sustinuta=True))
    assert r["rezultat"]["Q_G"]["decl"] == "EL"


def test_P1_9_cef_mt_masura_si_pi_pe_mt_cu_59n():
    c = dict(_calc("C02_cef_1MW"), pt_Sn_kVA=2000)
    m, r, _ = _gen(c)
    z = r["rezultat"]
    assert z["masura"]["loc"] == "MT"
    ap = _toate_aparatele(m)
    refs = {a.get("ref") for a in ap}
    assert {"QM", "QI"} <= refs and "TC" not in refs                   # fără TC de decontare pe JT
    qi = [a for a in ap if a.get("ref") == "QI"][0]
    assert any("59N" in " ".join(l.get("spec") or []) for l in qi["laterale"])
    assert any(l.get("eticheta") == "RTU" for l in qi["laterale"])     # categoria B RfG: teleconducere + PPC
    qg = [a for a in ap if a.get("ref") == "QG"][0]
    assert not qg.get("laterale")                                       # PI nu mai e pe QG JT


def test_P1_10_generice_si_existente_nu_sunt_de_cumparat():
    for caz in ("B01_bransament_nou_tri", "R01_prosumator_bat"):
        m, _, _ = _gen(_calc(caz))
        _, poz = layout.build_cu_pozitii(m)
        assert not any("(generic)" in " ".join(p[2]) or "— generic" in " ".join(p[2]) for p in poz), caz
        assert not any(x["lista"][0].startswith("Carcasă tablou TE") for x in m["materiale"])
    m, _, _ = _gen(_calc("L02_casa_tri_pc_ve"))           # branșament existent: SF, contor, Q, RCCB ale OD
    _, poz = layout.build_cu_pozitii(m)
    assert not any(p[1] in ("SF", "P", "QB", "RCCB") for p in poz)
    assert not any(x["lista"][0].startswith("Patron fuzibil") for x in m["materiale"])


# ============================================================================================ mesaje (ux problema 5)
RE_INTERN = re.compile(r"\bnorme\.\w+|\bIn_Q_bransament_A\b|\bP_aprobata_kW\b|\bpt_Sn_kVA\b|\bGE_SN_KVA\b|engine/|"
                       r"\bIdN_amonte_mA\b|\bcircuite_finale\b|\bcompensare_kvar\b")


@pytest.mark.parametrize("caz", ["L01_casa_mono", "G01_ge_ats", "C02_cef_1MW", "P01_pt630", "T01_tg_hala", "G01b_ge_ats"])
def test_mesaje_fara_denumiri_interne_si_blocante_cu_remediere(caz):
    _, _, v = _gen(_calc(caz))
    for x in v["verificari"]:
        if x["nivel"] in ("BLOCANT", "AVERTISMENT"):
            assert not RE_INTERN.search(x["mesaj"] + " " + (x.get("remediere") or "")), x
        if x["nivel"] == "BLOCANT":
            assert len((x.get("remediere") or "").split()) >= 3, x


def test_interpretor_intrebari_fara_chei_interne():
    for t in ("grup electrogen 50 kVA, sarcina 90 kW", "PT 500 kVA cu plecări 250 A și 160 A",
              "tablou 3 circuite iluminat 16 A, 2 circuite prize 16 A"):
        it = interpreteaza(t, foloseste_llm=False)
        for x in (it.get("intrebari") or []) + (it.get("presupus") or []):
            assert not RE_INTERN.search(x), x
