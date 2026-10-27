"""Regresii runda 11 (teste/r11/{locuinte,fotovoltaic,industrial}.md) — INTERPRETORUL LOCAL (regulile + dicționarul
central de sinonime engine/interp_sinonime.py, fără Claude), pe calea aplicației fără cheie API.

1. Fiecare frază r11 P0/P1 (+ P2 din clasele reparate) cu verificările din teste/r11/reverificare.py.
2. Pe toate frazele r11: plasa de siguranță, „nimic blocat fără întrebare” și nicio cheie refuzată de motor (V96).
3. Sinonimele: pentru fiecare concept, TOATE variantele (română / engleză / prescurtări) dau același rezultat.
4. Clasele r11 pe formulări NOI (5–10 pe clasă, inventate, diferite de cele din rapoarte).

Rulare: cd /home/claude/sm && python3 -m pytest -q tests/test_interpretor_r11.py
"""
import importlib.util
import sys
from pathlib import Path

import pytest

RAD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAD))

from engine import interp_sinonime as S  # noqa: E402
from engine.calc import chei  # noqa: E402
from engine.interpretor import interpreteaza  # noqa: E402

_spec = importlib.util.spec_from_file_location("reverificare_r11", RAD / "teste" / "r11" / "reverificare.py")
rv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rv)

CAZURI = rv.incarca()
EXPLICIT = [c for c in CAZURI if c[5]]


@pytest.mark.parametrize("dom,fid,text,vt,prio,verif", EXPLICIT, ids=[f"{c[1]}-{c[4]}" for c in EXPLICIT])
def test_fraza_r11(dom, fid, text, vt, prio, verif):
    c = rv.rezultat(text)
    verdict, lipsa = rv.evalueaza(verif, c)
    r = c["r"]
    assert verdict == "corect", (lipsa, r["intrare_fizica"], r["intrebari"], r["neconsumat"])


@pytest.mark.parametrize("text", sorted({c[2] for c in CAZURI}))
def test_plasa_blocaj_chei_r11(text):
    c = rv.rezultat(text)
    assert rv.plasa_ok(c["r"]), c["r"]["neconsumat"]
    assert rv.BLOC_INTREBAT[1](c), ([x for x in (c["v"] or {}).get("verificari") or [] if x.get("nivel") == "BLOCANT"],
                                    c["r"]["intrebari"])
    i = c["r"]["intrare_fizica"]
    assert not chei.chei_nefolosite(i, i.get("tip_schema")), chei.chei_nefolosite(i, i.get("tip_schema"))


# ------------------------------------------------------------------------------------------------- utilitare
def R(text):
    return interpreteaza(text)


def I(text):
    return R(text)["intrare_fizica"]


def pl(i):
    out = []

    def w(L):
        for p in L or []:
            out.append(p)
            w(p.get("copii"))
    w(i.get("plecari"))
    return out


def circ(i, rec=None):
    out = list(i.get("circuite") or [])
    for t in i.get("tablouri_secundare") or []:
        out += t.get("circuite") or []
    return [x for x in out if rec is None or x.get("receptor") == rec]


def Q(r):
    return " ".join(r["intrebari"] + [r.get("refuz_motiv") or ""]).lower()


def inv(i):
    return sorted((g.get("n", 1), g.get("Pn_kW"), bool(g.get("existent"))) for g in i.get("invertoare") or [])


# ------------------------------------------------------------------- 3. sinonimele (dicționarul central)
@pytest.mark.parametrize("v", ["Ucc", "ucc", "U cc", "usc", "u_k", "uk", "tensiunea de scurtcircuit", "tensiune de scurtcircuit de",
                               "impedanța de scurtcircuit", "short-circuit voltage", "impedance voltage", "Zk"])
def test_sinonim_uk(v):
    i = I(f"PT 1000 kVA, {v} 4,5%, 20/0,4 kV, TG cu plecari 4 x 250 A")
    assert i["tip_schema"] == "pt" and i["uk_pct"] == 4.5, i


@pytest.mark.parametrize("v,g", [("Dyn11", "Dyn11"), ("Dyn 11", "Dyn11"), ("DYn-11", "Dyn11"), ("D/yn-11", "Dyn11"),
                                 ("Δyn11", "Dyn11"), ("Dyn5", "Dyn5"), ("Yzn11", "Yzn11"), ("Yyn0", "Yyn0")])
def test_sinonim_grupa_conexiuni(v, g):
    i = I(f"PT 630 kVA 20/0,4 kV, {v}, TG cu plecari 3 x 200 A")
    assert i.get("grupa_conexiuni") == g, i


@pytest.mark.parametrize("v", ["izolat", "izolată", "fără rețea", "insular", "în regim insular", "off-grid", "offgrid",
                               "autonom", "stand-alone", "nu există rețea", "fără racord la rețea", "singura sursă",
                               "isolated", "no grid"])
def test_sinonim_fara_retea(v):
    i = I(f"GE 250 kVA {v}, consumatori: concasor 90 kW cu soft starter, iluminat 4 kW")
    assert i["tip_schema"] == "ge_ats" and i.get("fara_retea") is True and not i.get("sursa_retea"), i


@pytest.mark.parametrize("v", ["neutru izolat", "cablu izolat XLPE"])
def test_izolat_alt_sens_nu_e_fara_retea(v):
    i = I(f"GE 100 kVA cu ATS, retea din PT 400 kVA, {v}, consumatori: pompa 30 kW, iluminat 2 kW")
    assert not i.get("fara_retea"), i


@pytest.mark.parametrize("v", ["contor 3x63A", "BMPT 3x63A", "firidă trifazată 63 A", "cutie de branșament trifazată 63A",
                               "contorul trifazat de 63 A", "grup de măsură 3x63A", "DNO cut-out 3x63A"])
def test_sinonim_bmpt_sursa(v):
    i = I(f"depozit, TN-C-S, {v}. iluminat 2 kW, incalzire 2x3 kW, poarta auto 0,75 kW")
    assert i["tip_schema"] == "tablou" and i.get("origine") == "bmpt", i
    assert not any(w in (p.get("nume") or "").lower() for p in pl(i) for w in ("contor", "bmpt", "firid", "cutie", "grup")), pl(i)


@pytest.mark.parametrize("v", ["contor monofazat 1x32A", "firidă monofazată 32 A", "BMPT 1x32A", "BMPM 32A"])
def test_sinonim_bmpm_mono(v):
    i = I(f"prosumator: 1 invertor Huawei SUN2000-5KTL-L1, {v}")
    assert i["retea"] == "mono" and not any(g.get("faza") for g in i.get("invertoare") or []), i


@pytest.mark.parametrize("v", ["AAR", "ATS", "A.A.R.", "anclanșare automată a rezervei", "comutator automat de sursă",
                               "inversor automat de sursă", "automatic transfer switch", "transfer automat"])
def test_sinonim_ats_intre_trafo(v):
    i = I(f"PT cu 2 transformatoare 800 kVA uscate, cupla longitudinala pe JT si {v}, TG cu plecari 4 x 250 A")
    assert i["tip_schema"] == "pt" and i["n_trafo"] == 2 and i.get("aar") is True and i["cupla"] == "deschisa", i
    assert not i.get("Sn_GE_kVA")


@pytest.mark.parametrize("v", ["GE", "grup electrogen", "generator", "genset", "grup diesel", "motogenerator", "diesel generator"])
def test_sinonim_ge(v):
    i = I(f"Tablou cu {v} 100 kVA si ATS, retea din PT 400 kVA, consumatori vitali: pompe 30 kW, iluminat 2 kW")
    assert i["tip_schema"] == "ge_ats" and i["Sn_GE_kVA"] == 100, i


@pytest.mark.parametrize("v", ["fără generator", "fara GE", "fără grup electrogen", "no genset", "without a generator"])
def test_sinonim_fara_ge(v):
    r = R(f"ATS intre trafo T1 si T2 (fiecare 630 kVA) pentru tabloul vital, {v}")
    i = r["intrare_fizica"]
    assert i["tip_schema"] == "pt" and i.get("aar") is True and not i.get("Sn_GE_kVA"), i
    assert "puterea ge" not in Q(r) and "grup electrogen" not in Q(r), r["intrebari"]


@pytest.mark.parametrize("v", ["PT", "post trafo", "post de transformare", "postul de transformare",
                               "cabina de transformare"])
def test_sinonim_pt(v):
    i = I(f"TG hala din {v} 630 kVA, TN-S, plecari: compresor 30 kW, iluminat 10 kW")
    assert i["tip_schema"] == "tablou" and i.get("origine") == "pt_propriu" and i.get("pt_Sn_kVA") == 630, i


@pytest.mark.parametrize("v,n", [("6 lumini", 6), ("6 lumină", 6), ("6 circuite de lumină", 6), ("6 iluminat", 6),
                                 ("6 spoturi", 6), ("6 corpuri de iluminat", 6), ("6 lights", 6), ("6 ilum", 6),
                                 ("8p 6l", 6), ("un circuit lumină", 1)])
def test_sinonim_iluminat_n_circuite(v, n):
    i = I(f"Casă monofazată 40A, Pa 9 kW, 5 prize, {v}, boiler 2 kW")
    assert len(circ(i, "iluminat")) == n, circ(i)


@pytest.mark.parametrize("v", ["wallbox", "stație de încărcare", "stație VE", "stație EV", "încărcător auto", "EV charger",
                               "charging station", "punct de încărcare"])
def test_sinonim_ve(v):
    i = I(f"Casă trifazată 3x32A, Pa 20 kW, {v} 11 kW trifazat, 6 prize, 4 lumini")
    assert any(x.get("receptor") == "vehicul_electric" and x.get("P_kW") == 11 for x in circ(i)), circ(i)


@pytest.mark.parametrize("v", ["6 stații EV de 22 kW", "6 stații de încărcare 22 kW", "6 wallbox-uri de 22 kW",
                               "6 încărcătoare de 22 kW", "6 stații VE a câte 22 kW"])
def test_sinonim_ve_n(v):
    i = I(f"Parcare: {v}, RCD tip B, din TG existent, TN-S")
    assert sum(int(p.get("n_circuite") or 1) for p in pl(i) if p.get("P_kW") == 22) == 6, pl(i)


@pytest.mark.parametrize("v", ["UPS", "U.P.S.", "sursă neîntreruptibilă", "UPS online"])
def test_sinonim_ups(v):
    i = I(f"{v} 200 kVA cu bypass, ieșire pe TD-DC cu 10 plecări de 32 A")
    assert i["tip_schema"] == "tablou" and not i.get("Sn_kVA"), i
    assert any(p.get("receptor") == "ups" and p.get("Sn_kVA") == 200 and p.get("bypass") for p in pl(i)), pl(i)


@pytest.mark.parametrize("v", ["sub-tablou", "subtablou", "subpanel", "panou electric secundar"])
def test_sinonim_tablou(v):
    i = I(f"{v} mansarda alimentat din TG existent cu C32: 4 prize, 2 lumini, AC 2,5 kW")
    assert i["tip_schema"] == "tablou" and i.get("origine") == "tg_existent", i


@pytest.mark.parametrize("v", ["export cap 400 kW", "export limit 400 kW", "limitare injecție 400 kW", "injecție limitată la 400 kW",
                               "plafon de injecție 400 kW", "putere maximă injectată 400 kW"])
def test_sinonim_limitare(v):
    i = I(f"4 x Huawei SUN2000-115KTL-M2, PT existent 1000 kVA, masura MT, {v}")
    assert i["limitare_injectie_kW"] == 400, i


@pytest.mark.parametrize("v", ["ku = 0,65", "ku 0,65", "coeficient de utilizare 0,65", "factor de utilizare 0,65"])
def test_sinonim_ku(v):
    i = I(f"Bilant: Pi total = 420 kW, {v}, cos fi = 0,88. Alimentare din PT propriu 630 kVA. TG cu 8 plecari a cate 50 kW")
    assert i["P_kW"] == 273, i


def test_dictionar_complet():
    """fiecare concept cerut are variantele lui în dicționar (și forma canonică acolo unde se rescrie)"""
    for k in ("uk", "fara_retea", "bmpt", "ats", "ge", "pt", "grupa_conexiuni", "iluminat", "tablou", "ve", "ups"):
        assert len(S.SINONIME[k]) >= 3 and S.RX[k].search
    assert S.are("ats", "aar") and S.are("ge", "genset") and S.are("bmpt", "contor") and S.are("uk", "ucc")
    assert S.grupa_conexiuni("Dyn 11")[0] == "Dyn11" and S.fara_retea("pe ge izolat") and not S.fara_retea("neutru izolat")


# ------------------------------------------------------------------- 4. clasele r11 pe formulări noi
@pytest.mark.parametrize("text,asteptat", [
    ("4 invertoare (3 x SUN2000-50KTL-M3 + 1 x SUN2000-30KTL-M3), TG existent", [(1, 30, False), (3, 50, False)]),
    ("5 invertoare (2 x Sungrow SG110CX și 3 x Huawei SUN2000-100KTL-M2), PT nou 1000 kVA", [(2, 110, False), (3, 100, False)]),
    ("CEF cu 3 invertoare: (1 x SG50CX și 2 x SG33CX), TG existent", [(1, 50, False), (2, 33, False)]),
    ("6 invertoare (4 x SUN2000-20KTL-M3, 2 x SUN2000-12KTL-M2), BMPT 3x250A", [(2, 12, False), (4, 20, False)]),
    ("4 x 50KTL Huawei, TG existent", [(4, 50, False)]),
    ("3 x 100KTL, racord PT existent 630 kVA", [(3, 100, False)]),
])
def test_clasa_invertoare_paranteza(text, asteptat):
    assert inv(I(text)) == asteptat


@pytest.mark.parametrize("text,k,m", [
    ("Două tablouri TGD-CF, fiecare cu 4 x SUN2000-50KTL-M3, PT existent 630 kVA", 2, 4),
    ("2 tablouri TGD-CF, câte unul pe fiecare hală, fiecare cu 5 x SG110CX. PT nou 1250 kVA", 2, 5),
    ("doua TGD-CF pe acoperisuri diferite, fiecare cu 3 x SUN2000-100KTL-M2, TG existent", 2, 3),
    ("2 tablouri de invertoare, fiecare cu 2 x SG110CX, racord PT existent 630 kVA", 2, 2),
])
def test_clasa_fiecare_cu(text, k, m):
    i = I(text)
    assert sum(g.get("n", 1) for g in i["invertoare"]) == k * m and i.get("n_tgd_cf") == k, i


@pytest.mark.parametrize("text,kwh", [("prosumator 10 kW, Deye SUN-10K-SG04LP3-EU hibrid cu 3 baterii BOS-G 5,12 kWh, BMPT 3x32A", 15.36),
                                      ("hibrid Deye SUN-12K-SG04LP3-EU, 4 baterii Pylontech US5000 4,8 kWh, BMPT 3x32A, casa", 19.2),
                                      ("casa, invertor hibrid Huawei SUN2000-10KTL-M1 cu 2 baterii LUNA 5 kWh, BMPT 3x25A", 10)])
def test_clasa_baterii_model(text, kwh):
    i = I(text)
    assert abs((i.get("baterie_kWh") or (i.get("bess") or {}).get("kWh") or 0) - kwh) < 0.01, i


@pytest.mark.parametrize("text,kwp", [("1 x SG110CX, 10 stringuri a câte 22 module 550 Wp, TG existent", 121),
                                      ("2 x SUN2000-50KTL-M3, 8 stringuri de câte 25 module 500 Wp, TG existent", 100),
                                      ("1 x Solis S5-GC50K, 6 stringuri cu câte 20 module 450 Wp, TG existent", 54)])
def test_clasa_stringuri(text, kwp):
    i = I(text)
    assert abs(i["kWp"] - kwp) < 0.01, i


def test_clasa_stringuri_fara_pmax_intreaba():
    r = R("2 x SUN2000-50KTL-M3, 10 stringuri a câte 20 module, TG existent")
    assert "wp" in Q(r) and not r["intrare_fizica"].get("kWp"), r["intrebari"]


@pytest.mark.parametrize("text", ["Avem PT propriu 630 kVA, 3 x SG110CX, masura pe MT",
                                  "Clientul are PT 400 kVA, 2 x SUN2000-100KTL-M2, injectie zero",
                                  "Exista deja un post de transformare 1000 kVA; 5 x SG110CX, masura MT"])
def test_clasa_pt_existent(text):
    assert I(text).get("pt_existent") is True


@pytest.mark.parametrize("text,cheie", [
    ("2 x SUN2000-30KTL-M3, fiecare invertor cu cablu CYY-F 5x16 mmp, 30 m, TG existent", "cablu_inv"),
    ("3 x SG50CX, pe fiecare invertor cablu CYABY 5x25, 40 m, TG existent", "cablu_inv"),
])
def test_clasa_cablu_pe_circuitul_corect(text, cheie):
    i = I(text)
    assert (i.get(cheie) or {}).get("S_fortat") and not (i.get("cablu_C0") or {}).get("S_fortat"), i


def test_clasa_cablu_solar_e_cc():
    i = I("BOM: 1) Invertor SG110CX – 1 buc; 2) Cablu solar 4 mmp – 800 m; racord TG existent")
    assert i.get("cablu_cc", {}).get("S_fortat") == 4 and not i.get("cablu_C0") and i.get("L_racord_m") != 800, i


@pytest.mark.parametrize("text,racord,q", [
    ("1 x SUN2000-50KTL-M3, racord in TG existent... de fapt nu, prin BMPT nou 3x100A", "bmpt", 100),
    ("1 x SG50CX, racord prin BMPT 3x100A, scuze, in TG existent", "tg_existent", None),
])
def test_clasa_autocorectura_racord(text, racord, q):
    i = I(text)
    assert i.get("racord") == racord and (q is None or i.get("In_Q_bransament_A") == q), i


@pytest.mark.parametrize("text", [
    "4 x SUN2000-100KTL-M2 și 2 x SUN2000-100KTL-M2 existente — pardon, existente sunt doar 2, cele 4 sunt noi. PT existent 630 kVA",
    "4 x SUN2000-100KTL-M2 noi și 2 x SUN2000-100KTL-M2 existente, PT existent 630 kVA",
])
def test_clasa_noi_si_existente(text):
    assert inv(I(text)) == [(2, 100, True), (4, 100, False)]


@pytest.mark.parametrize("text,ret", [("Casă trifazată 3x32A... de fapt nu, e monofazată 40 A. 8 kW, 5 prize, 3 lumini", "mono"),
                                      ("casa monofazata 40A, scuze, trifazata 3x25A, Pa 15 kW, 6 prize", "tri"),
                                      ("Casă mono 32 A... corectez, e trifazată 3x32A, Pa 18 kW, 8 prize", "tri")])
def test_clasa_autocorectura_retea(text, ret):
    r = R(text)
    assert r["actiune"] != "refuza" and r["intrare_fizica"]["retea"] == ret, (r["refuz_motiv"], r["intrare_fizica"])


@pytest.mark.parametrize("text,sp", [("Tablou TT, BMPT 63A trifazat. Nu, scuze, e TN-C-S. Plecari: lift 11 kW, iluminat 1 kW", "TN-C-S"),
                                     ("TG TN-S din PT 400 kVA. Pardon, schema e TN-C-S. Plecari: pompa 7,5 kW", "TN-C-S")])
def test_clasa_autocorectura_schema(text, sp):
    r = R(text)
    assert r["actiune"] != "refuza" and r["intrare_fizica"].get("schema_pamant") == sp, (r["refuz_motiv"], r["intrare_fizica"])


@pytest.mark.parametrize("text", ["2 x Huawei SUN2000-100KTL-M2, PT existent 1000 kVA, export cap 150 kW",
                                  "2 x SG110CX, TG existent, export limited to 150 kW"])
def test_clasa_export_cap(text):
    r = R(text)
    assert r["actiune"] != "refuza" and r["intrare_fizica"]["limitare_injectie_kW"] == 150, r["refuz_motiv"]


@pytest.mark.parametrize("text", ["doar baterie 20 kWh cu invertor hibrid Deye SUN-10K-SG04LP3-EU, fără panouri, casă, BMPT 3x32A",
                                  "casa: Deye SUN-8K-SG04LP3-EU hibrid, baterie 15 kWh, fara panouri, BMPT 3x25A"])
def test_clasa_fara_panouri(text):
    i = I(text)
    assert i.get("bess", {}).get("kWh") and not i.get("invertoare") and not i.get("kWp"), i


def test_clasa_sg350hx_fisa():
    i = I("CEF cu 3 x Sungrow SG350HX (320 kW, ieșire 800 V c.a.), PT nou 1250 kVA 20/0,8 kV, măsură pe MT")
    assert inv(i) == [(3, 320, False)]


@pytest.mark.parametrize("text", ["Hala: 4 stații EV 22 kW, din TG existent, TN-S", "parcare cu 3 statii de incarcare de 11 kW, din TG existent",
                                  "8 wallbox-uri de 11 kW, TG din PT 630 kVA"])
def test_clasa_n_statii(text):
    i = I(text)
    n = int(text.split()[[k for k, w in enumerate(text.split()) if w.isdigit() and int(w) < 10][0]])
    assert sum(int(p.get("n_circuite") or 1) for p in pl(i) if p.get("P_kW") in (11, 22)) == n, pl(i)


@pytest.mark.parametrize("text", ["magazin, TT, contor 3x80A: vitrine 3 x 2 kW, iluminat 4 kW, HVAC 10 kW",
                                  "atelier, 3f, TN-C-S, contorul de 50 A: strung 4 kW, compresor 3 kW, iluminat 1 kW",
                                  "Tablou TN-C-S, firida trifazata 63 A: pompa 5,5 kW, iluminat 2 kW, prize 3 circuite 16A"])
def test_clasa_contor_e_sursa(text):
    i = I(text)
    assert i["tip_schema"] == "tablou" and i.get("origine") == "bmpt" and not any(
        any(w in (p.get("nume") or "").lower() for w in ("contor", "bmpt", "firid")) for p in pl(i)), i


@pytest.mark.parametrize("text", ["UPS 120 kVA online, alimenteaza TD IT: 8 rack-uri a cate 10 kW, monofazate. Intrarea UPS din TG, TN-S",
                                  "UPS trifazat 80 kVA cu bypass, iesire pe TD servere cu 6 plecari de 16 A"])
def test_clasa_ups(text):
    i = I(text)
    assert i["tip_schema"] == "tablou" and any(p.get("receptor") == "ups" and p.get("copii") for p in pl(i)), i


@pytest.mark.parametrize("text,vit,nevit", [
    ("GE 200 kVA + ATS, TG cu bara normala si bara vitala, pe bara vitala: pompa incendiu 55 kW, iluminat siguranta 2 kW; "
     "pe bara normala: HVAC 100 kW, prize 20 kW", 57, ("hvac", "prize")),
    ("GE 150 kVA cu ATS pe consumatorii vitali (servere 20 kW, iluminat siguranta 3 kW). Nevitalii (bucatarie 40 kW, AC 30 kW) "
     "raman doar pe retea. Retea din PT 400 kVA.", 23, ("bucatarie", "ac")),
    ("GE 40 kVA cu ATS, TT, retea 3x63A. Doar 2 circuite pe GE: frigider 3 kW si centrala 1 kW, restul (AC 7 kW, cuptor 3 kW) "
     "doar pe retea", 4, ("ac", "cuptor")),
])
def test_clasa_vitali(text, vit, nevit):
    r = R(text)
    i = r["intrare_fizica"]
    assert r["actiune"] != "refuza" and i["P_sarcina_kW"] == vit and i.get("bara_vitala") is True, (r["refuz_motiv"], i)
    assert all(x.get("vital") is False for x in i["consumatori"] if (x["nume"] or "").lower().split()[0] in nevit), i


@pytest.mark.parametrize("text,arbore", [
    ("TG alimenteaza TD1 si TD2, TD1 alimenteaza TD1.1. TD1.1 are iluminat 3 kW, TD2 are un cuptor de 10 kW. Sursa PT 400 kVA, TN-S",
     {"TD1": ["TD1.1"], "TD2": []}),
    ("TG (din PT 630 kVA, TN-S) -> TD-A (L=40 m): iluminat 4 kW, prize 6 kW; TD-B (L=70 m): pompe 2x5,5 kW",
     {"TD-A": [], "TD-B": []}),
])
def test_clasa_cascade(text, arbore):
    r = R(text)
    i = r["intrare_fizica"]
    top = {p["nume"]: [k["nume"] for k in p.get("copii") or [] if k.get("copii") is not None and k["nume"].startswith("TD")]
           for p in i.get("plecari") or []}
    assert top == arbore and not r["neconsumat"], (i, r["neconsumat"])


@pytest.mark.parametrize("text", ["Tablou TE alimentat din TD-3 care e alimentat din TG, iar TG din PT 630 kVA. TE are: 2 pompe 4 kW",
                                  "3 pompe de 7,5 kW in schema 2+1, pornire cu convertizor, din TD-pompe, TN-S, alimentare din PT 400 kVA"])
def test_clasa_surse_in_lant(text):
    r = R(text)
    assert r["actiune"] != "refuza" and "două surse" not in Q(r), (r["refuz_motiv"], r["intrebari"])


@pytest.mark.parametrize("text,n", [
    ("TG 3x400V, TN-S, din PT 400 kVA, plecari: 1. Iluminat hala - 8 kW; 2. Prize 3P 32A - 2 buc; 3. TD birouri - 15 kW", 4),
    ("TG din PT 630 kVA, TN-S, plecari: 1. Compresor - 22 kW; 2. Pod rulant - 15 kW; 3. Iluminat - 6 kW; 4. Rezerva echipata 63A", 4),
])
def test_clasa_lista_numerotata(text, n):
    r = R(text)
    assert r["actiune"] != "refuza" and sum(int(p.get("n_circuite") or 1) for p in r["intrare_fizica"]["plecari"]) == n, r


def test_clasa_excel_faze():
    t = ("Circuit;Destinatie;P(kW);Faze;L(m)\nC1;Iluminat;1,8;1;25\nC2;Prize;3,6;1;20\nC3;Pompa caldura;12;3;15\n"
         "Tablou din TG existent, TN-S, 3F")
    r = R(t)
    i = r["intrare_fizica"]
    assert r["actiune"] != "refuza" and sorted(p.get("retea") for p in i["plecari"]) == ["mono", "mono", "tri"], r


@pytest.mark.parametrize("text,n", [("TGJT cu 5 plecari NH: 2 x 400 A, 3 x 160 A, PT 1000 kVA 20/0,4 kV", 5),
                                    ("PT 630 kVA, TGJT cu 4 plecari MCCB: 1 x 400 A, 3 x 125 A", 4)])
def test_clasa_plecari_nh(text, n):
    assert len(pl(I(text))) == n


def test_clasa_compensare_nx():
    assert I("PT 1600 kVA, TG ACB 2500 A, plecari 4 x 400 A, compensare 2x200 kvar")["compensare_kvar"] == 400


def test_clasa_ge_izolat_dol():
    r = R("moara 110 kW pornire directa pe GE 200 kVA izolat")
    i = r["intrare_fizica"]
    assert i.get("fara_retea") is True and "direct" in Q(r), r["intrebari"]


def test_clasa_pt2_ge_refuz_cinstit():
    r = R("Spital: 2 trafo 1600 kVA, fiecare pe semibara lui, cupla normal deschisa, plus GE 800 kVA prin ATS doar pe bara esentiala")
    assert r["actiune"] == "refuza" and r["refuz_cod"] == "I12" and r["intrebari"]


# ------------------------------------------------------------------- locuință
@pytest.mark.parametrize("text,rec,L", [
    ("Casă monofazată 32A Pa 7 kW cu 5 prize și 3 lumini, dar pompa de apă din puț e la 90 m, 1,1 kW", "pompa_apa", 90),
    ("casa mono 40A, Pa 9 kW, 4 prize, 3 lumini, pompa submersibila e la 60 m de casa, 0,75 kW", "pompa_apa", 60),
])
def test_clasa_receptor_la_m(text, rec, L):
    i = I(text)
    assert any(x.get("receptor") == rec and x.get("L_m") == L for x in circ(i)), circ(i)
    assert (i.get("alimentare") or {}).get("L_coloana_m") != L


@pytest.mark.parametrize("text,a,s", [("Casă mono 40A, Pa 9 kW, prizele pe C20 cu cablu 2,5 mm2, 5 circuite, plus 3 lumini", 20, 2.5),
                                      ("casa tri 3x25A Pa 15 kW, prizele sunt pe C16 cu 2,5 mm2, 8 circuite, 4 lumini", 16, 2.5)])
def test_clasa_prize_pe_cablu(text, a, s):
    i = I(text)
    pr = [x for x in circ(i, "prize") if x.get("In_A") == a]
    assert pr and all((x.get("cablu") or {}).get("S_fortat") == s for x in pr), circ(i)
    assert ((i.get("alimentare") or {}).get("cablu") or {}).get("S_fortat") != s


@pytest.mark.parametrize("text", ["Casă trifazată 3x32A, Pa 18 kW, priză trifazată CEE 16A în atelier, 6 prize, 4 lumini",
                                  "casa tri 3x40A, Pa 22 kW, o priza CEE 32A trifazata in garaj, 8 prize"])
def test_clasa_cee(text):
    assert any(x.get("faza") == "3F" and x.get("In_A") in (16, 32) for x in circ(I(text)))


@pytest.mark.parametrize("text", [
    "TG casă trifazat 3x32A, Pa 20 kW. Din TG pleacă: TE parter monofazat 5 kW, TE etaj monofazat 4 kW",
    "Casă cu atelier, trifazat 3x25A, Pa 15 kW: flex, aparat de sudură 5 kVA monofazat, strung 3 kW trifazat, 5 prize",
    "Mărire de putere de la 4 kW monofazat la 15 kW trifazat: se înlocuiește BMPM cu BMPT 3x25A, 6 prize, 4 lumini",
])
def test_clasa_mono_tri_normal(text):
    r = R(text)
    assert r["actiune"] != "refuza" and "contradic" not in Q(r) and r["intrare_fizica"].get("retea") == "tri", (r["refuz_motiv"], r["intrebari"])


@pytest.mark.parametrize("text", ["Branșament monofazat 3x25A, casa are 10 kW", "Casă monofazată 230V, Q 32 A, cu saună trifazată 9 kW",
                                  "Pa 12 kW, Q 3x25A, monofazat, 5 prize"])
def test_clasa_contradictie_reala_ramane(text):
    r = R(text)
    assert r["actiune"] != "genereaza", r


@pytest.mark.parametrize("text", ["Doar tabloul bucătăriei, TE bucătărie: 3 prize, 1 lumină, plită 7 kW, alimentat monofazat din TE apartament",
                                  "TE garaj nou alimentat din tabloul existent cu C25: 3 prize, 1 lumină, compresor 2,2 kW"])
def test_clasa_doar_te(text):
    i = I(text)
    assert i["tip_schema"] == "tablou" and i.get("origine") == "tg_existent" and not i.get("alimentare"), i


def test_clasa_vila_apartamente():
    r = R("vilă cu 3 apartamente, fiecare cu contorul lui monofazat 32 A, Pa 6 kW fiecare")
    assert "apartamente" in Q(r)


def test_clasa_generator_pe_gen_nu_e_invertor():
    i = I("Hibrid 8 kW trifazat cu baterie 10 kWh și generator 6 kVA pe intrarea GEN a invertorului, Q 3x25A, Pa 11 kW")
    assert not any(g.get("Pn_kW") == 6 for g in i.get("invertoare") or [])


# ------------------------------------------------------------------- rețeaua dedusă (_deduse)
@pytest.mark.parametrize("text", ["prosumator 6 kW pe casă, BMPT existent, invertor de 6 kW",
                                  "casa 10 kW cu 6 prize, 4 lumini, boiler, BMPT 3x25A",
                                  "TG cu plecari: banda 5,5 kW, ventilator 3 kW, iluminat 2 kW"])
def test_retea_dedusa_marcata(text):
    r = R(text)
    i = r["intrare_fizica"]
    assert "retea" in (i.get("_deduse") or []) and "retea" in r["_deduse"], i
    assert any("REȚEA DEDUSĂ" in p for p in r["presupus"]), r["presupus"]


@pytest.mark.parametrize("text", ["Casă trifazată 3x25A, Pa 15 kW, 6 prize", "prosumator monofazat 5 kW, BMPM 32A"])
def test_retea_declarata_nu_e_dedusa(text):
    assert "retea" not in (I(text).get("_deduse") or [])


def test_retea_dedusa_slaba_intreaba():
    r = R("prosumator 6 kW pe casă, BMPT existent, invertor de 6 kW")
    assert "rețeaua nu se presupune" in Q(r), r["intrebari"]
