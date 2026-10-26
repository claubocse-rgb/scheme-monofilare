"""Regresii runda 7 (teste/r7/{locuinte,fotovoltaic,industrial}.md) — interpretorul.

1. Fiecare frază r7 (cu accent pe P0/P1) cu verificările din teste/r7/reverificare.py — scrise din „așteptat” și din
   comentariul testerului, nu din ce face codul.
2. Plasa de siguranță pe toate frazele r7: rest neconsumat ⇒ niciodată „genereaza” fără mențiune.
3. Clasele de greșeli pe formulări NOI (nu cele din rapoarte): formatare (rânduri, bullet-uri, „a)”, „a câte”, tab),
   legarea valorii de entitate (receptor ≠ P aprobată, „N x” lângă cablu / baterie, „casa X kW” la prosumator), PV fără
   cuvânt-cheie, contradicții numerice, tablouri secundare, chei noi pentru motor.

Rulare: cd /home/claude/sm && python3 -m pytest -q tests/test_interpretor_r7.py
"""
import importlib.util
import sys
from pathlib import Path

import pytest

RAD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAD))

from engine.interpretor import interpreteaza_local  # noqa: E402

_spec = importlib.util.spec_from_file_location("reverificare_r7", RAD / "teste" / "r7" / "reverificare.py")
rv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rv)

CAZURI = rv.incarca()
P01 = [c for c in CAZURI if c[4] in ("P0", "P1")]
REST = [c for c in CAZURI if c[4] not in ("P0", "P1")]


def _verif(text, verif):
    r = rv.rezultat(text)
    verdict, lipsa = rv.evalueaza(verif, r)
    assert verdict == "corect", (lipsa, r["in"], r["intrebari"], r["nec"])


@pytest.mark.parametrize("rol,fid,text,vi,prio,verif", P01, ids=[f"{c[1]}-{c[4]}" for c in P01])
def test_fraza_p0_p1(rol, fid, text, vi, prio, verif):
    _verif(text, verif)


@pytest.mark.parametrize("rol,fid,text,vi,prio,verif", REST, ids=[f"{c[1]}-{c[4]}" for c in REST])
def test_fraza_restul(rol, fid, text, vi, prio, verif):
    _verif(text, verif)


@pytest.mark.parametrize("text", sorted({c[2] for c in CAZURI}))
def test_plasa_pe_toate_frazele_r7(text):
    d = interpreteaza_local(text)
    assert rv.r6.plasa_ok(d), d["neconsumat"]


# ------------------------------------------------------------------------------- clasele, pe formulări noi
def R(text):
    return interpreteaza_local(text)


def I(text):
    return R(text)["intrare_fizica"]


def inv(i):
    return sorted((x["n"], x["Pn_kW"]) for x in i.get("invertoare") or [])


def npl(i):
    return sum(int(p.get("n_circuite") or 1) for p in i.get("plecari") or [])


# 1. formatare / segmentare
def test_bullet_uri_pe_randuri():
    i = I("TG atelier tamplarie\n* circular 4 kW\n* rindea 3 kW\n* exhaustor 2,2 kW\n* prize 16A 4 circuite\n"
          "din TG existent, TN-S")
    assert npl(i) == 7 and i["origine"] == "tg_existent"


def test_enumerare_cu_litere():
    i = I("TG spalatorie din PT 250 kVA, TN-S: a) masini spalat 3 x 7,5 kW b) uscatoare 2 x 9 kW c) iluminat 2 kW")
    assert npl(i) == 6 and i["pt_Sn_kVA"] == 250


def test_tab_si_a_cate():
    i = I("TG hala:\tcompresor 15 kW\tbanda 4 kW\t6 plecari a cate 10 kW\tdin PT 400 kVA, TN-S")
    assert npl(i) == 8


def test_zecimala_cu_virgula_in_sectiune():
    i = I("cuptor 18 kW cu cablu CYY-F 5x4 de 35 m din TG existent TN-S")
    p = i["plecari"][0]
    assert p["cablu"]["S_fortat"] == 4 and p["L_m"] == 35 and "L_alimentare_m" not in i


def test_w_si_cp_si_n_de():
    i = I("tablou cu 2 pompe de 4kW, una de 7,5 kW, ventilator 1500 W, din TG, TN-S")
    assert npl(i) == 4 and any(p.get("P_kW") == 1.5 for p in i["plecari"])


# 2. legarea valorii de entitatea ei
def test_receptor_necunoscut_nu_devine_putere_aprobata():
    r = R("casa cu foisor: pompa fantana 1.5kw, trifazat 12kw, TN-C-S")
    assert r["intrare_fizica"]["alimentare"].get("P_aprobata_kW") == 12


def test_casa_x_kw_la_prosumator_e_p_aprobata():
    r = R("panouri 12 kwp, invertor 10 kw trifazat, casa 20 kw tn-c-s")
    assert r["tip_schema"] == "prosumator" and r["intrare_fizica"].get("P_aprobata_kW") == 20
    assert not any("total" in q for q in r["intrebari"])


def test_n_x_baterie_nu_e_invertor():
    i = I("Deye SUN-8K-SG04LP3 cu 3 x Pylontech US5000, TN-C-S")
    assert inv(i) == [(1, 8)] and i.get("baterie_kWh") == pytest.approx(14.4)


def test_n_x_cablu_nu_e_invertor():
    i = I("Fronius Tauro 50-3-P cu cablu NYY 5x25 50 m, TG existent, TN-S")
    assert inv(i) == [(1, 50)]


def test_pv_fara_cuvant_cheie():
    assert R("solar 5 kw mono tt")["tip_schema"] == "prosumator"
    assert inv(I("solar 20 kw tri TG tn-s")) == [(1, 20)]


def test_hibrid_fara_baterie_declarata():
    i = I("prosumator 10 kw cu SUN2000-10KTL-M1, fara baterie, tri TN-C-S")
    assert all(x.get("hibrid") is False for x in i["invertoare"])


def test_bmpt_putere_e_sursa_nu_plecare():
    i = I("tablou spalatorie: masina 5 kW, uscator 6 kW, din BMPT 20 kW trifazat")
    assert i["P_kW"] == 20 and npl(i) == 2


def test_trafo_multiplu_la_cef():
    i = I("CEF 1,2 MW cu 12 x SUN2000-100KTL-M2, PT nou 2 x 800 kVA")
    assert i["n_trafo"] == 2 and i["pt_Sn_kVA"] == 800


def test_invertor_800v():
    i = I("CEF 700 kW, 2 x SG350HX, PT nou 1000 kVA 20/0,8 kV")
    assert i["U_ca_V"] == 800 and i["U_JT_V"] == 800
    assert R("2 x SG350HX in TG existent 400 V")["actiune"] == "refuza"


def test_bateria_pe_un_invertor():
    i = I("CEF 100 kW, 2 x SH50T hibride, baterie 50 kWh pe INV-2, TG existent, TN-S")
    assert i["bess"]["la"] == ["INV-2"]


def test_masura_mt_la_cef():
    assert I("CEF 900 kW, 9 x SG110CX, PT nou 1000 kVA, masura pe MT")["masura"] == "MT"


# 3. contradicții numerice → întrebare
@pytest.mark.parametrize("text,cuv", [
    ("wallbox 11 kw, casa monofazata 7 kw tn-c-s", "11"),
    ("casa mono 12 kw tn-c-s", "trifazat"),
    ("pompa 30 kW 20 A din TG existent TN-S", "20"),
    ("PT 630 kVA 20/0,4 kV, rețea MT 10 kV", "10"),
    ("TD 125 A din TG prin intreruptor de 80 A, TN-S", "80"),
    ("TG 250 kW din BMPT", "BMPT"),
    ("prosumator 10 kW injectie zero, putere aprobata de injectare 8 kW, tri TN-C-S", "inject"),
    ("casa tri 10 kw, TT cu PEN comun", "PEN"),
    ("motor 90 kW la 690 V din TG", "690"),
])
def test_contradictii_intrebate(text, cuv):
    r = R(text)
    assert r["actiune"] in ("refuza", "genereaza_cu_intrebare")
    assert any(cuv.lower() in rv._f(q) for q in r["intrebari"]), r["intrebari"]


def test_inversor_manual_nu_e_ats():
    assert I("GE 20 kVA cu comutator manual, retea din BMPT 15 kW")["comutare"] == "manual"


def test_pompa_rezerva_nu_se_aduna():
    i = I("tablou hidranti: pompa principala 30 kW, pompa de rezerva 30 kW, alimentat din TG si GE 100 kVA")
    assert i["P_sarcina_kW"] == 30 and i["siguranta_tablou"] is True


# 4. plasa de siguranță + tablouri secundare
def test_te_etaj_intrebat():
    r = R("casa P+1 cu TE la etaj, tri 18 kw tn-c-s")
    assert any("etaj" in rv._f(q) for q in r["intrebari"])


def test_td_garaj_cu_circuite():
    i = I("vila P+1 trifazata 20 kw TT, TE la mansarda cu prize 3 circuite 16A si iluminat 2 circuite 10A")
    td = i["tablouri_secundare"][0]
    assert td["nume"].startswith("TE") and len(td["circuite"]) == 2


def test_tablou_fara_plecari_intreaba():
    r = R("TD hala alimentat cu CYABY 5x16 de 30 m din TG existent, 40 kW, TN-S")
    assert r["actiune"] != "genereaza" and any("plec" in q for q in r["intrebari"])


def test_cablu_3x_nu_decide_reteaua():
    r = R("anexa: 3 prize, 1 iluminat, alimentata din TG existent cu 3x4 de 20 m")
    assert r["intrare_fizica"].get("retea") != "tri" and any("monofazat" in q for q in r["intrebari"])


def test_ge_la_casa_e_sursa():
    i = I("casa 9kw mono tn-c-s + generator 6 kva cu comutator manual")
    assert i["ge_rezerva"]["Sn_kVA"] == 6 and i["ge_rezerva"]["comutare"] == "manual"
