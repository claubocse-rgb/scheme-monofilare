"""Regresii runda 9 (teste/r9/{locuinte,fotovoltaic,industrial}.md) — INTERPRETORUL LOCAL (regulile, fără Claude).

1. Fiecare frază r9 P0/P1 cu verificările din teste/r9/reverificare.py — scrise din „așteptat” și din observația
   testerului, nu din ce face codul; frazele P2 / fără observații pe care testerul le-a găsit corecte — amprenta de
   dinainte de reparații (regresii).
2. Plasa de siguranță pe toate frazele r9: rest neconsumat ⇒ niciodată „genereaza” fără mențiune.
3. Clasele de greșeli pe formulări NOI (nu cele din rapoarte): autocorecturi, cascade, plecări fantomă, cifre, lungimi,
   GE / backup, mărire de putere, siguranță în tablou mixt și în GE, contradicții întrebate, cabluri impuse până în motor.

Rulare: cd /home/claude/sm && python3 -m pytest -q tests/test_interpretor_r9.py
"""
import importlib.util
import sys
from pathlib import Path

import pytest

RAD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAD))

from engine import constructor, validare  # noqa: E402
from engine.interpretor import interpreteaza_local  # noqa: E402

_spec = importlib.util.spec_from_file_location("reverificare_r9", RAD / "teste" / "r9" / "reverificare.py")
rv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rv)

CAZURI = rv.incarca()
P01 = [c for c in CAZURI if c[4] in ("P0", "P1")]
REST = [c for c in CAZURI if c[4] not in ("P0", "P1") and c[5]]


def _verif(text, verif):
    c = rv.rezultat(text)
    verdict, lipsa = rv.evalueaza(verif, c)
    r = c["r"]
    assert verdict == "corect", (lipsa, r["intrare_fizica"], r["intrebari"], r["neconsumat"])


def _id(c):
    return f"{c[1]}-{c[4]}"


@pytest.mark.parametrize("dom,fid,text,vt,prio,verif", P01, ids=[_id(c) for c in P01])
def test_fraza_p0_p1(dom, fid, text, vt, prio, verif):
    _verif(text, verif)


@pytest.mark.parametrize("dom,fid,text,vt,prio,verif", REST, ids=[_id(c) for c in REST])
def test_fraza_restul_amprenta(dom, fid, text, vt, prio, verif):
    _verif(text, verif)


@pytest.mark.parametrize("text", sorted({c[2] for c in CAZURI}))
def test_plasa_pe_toate_frazele_r9(text):
    d = interpreteaza_local(text)
    assert rv.plasa_ok(d), d["neconsumat"]


# ------------------------------------------------------------------------------- clasele, pe formulări noi
def R(text):
    return interpreteaza_local(text)


def I(text):
    return R(text)["intrare_fizica"]


def inv(i):
    return sorted((x["n"], x["Pn_kW"]) for x in i.get("invertoare") or [])


def pl(i, toate=True):
    out = []

    def w(L):
        for p in L or []:
            out.append(p)
            if toate:
                w(p.get("copii"))
    w(i.get("plecari"))
    return out


def rec(i, r):
    return [x for x in i.get("circuite") or [] if x["receptor"] == r]


def Q(d):
    return " ".join(d["intrebari"] + [d.get("refuz_motiv") or ""] + d["avertismente"]).lower()


def blocante(i):
    m, _ = constructor.genereaza(i)
    return {x["cod"] for x in validare.valideaza(m)["verificari"] if x["nivel"] == "BLOCANT"}


# 1. autocorecturi — ultima valoare câștigă pentru aceeași entitate, fără dublare
def test_autocorectura_grup_de_invertoare_nu_se_dubleaza():
    i = I("3 invertoare de 20 kW... nu, 2 invertoare de 20 kW, Huawei SUN2000-20KTL-M2, TG existent")
    assert inv(i) == [(2, 20)] and i["invertoare"][0]["model"] == "SUN2000-20KTL-M2"


def test_autocorectura_pardon_valoare_cu_unitate():
    i = I("TG cu 4 motoare de 7,5 kW, pardon, 11 kW, din PT 630 kVA, TN-S")
    assert [p["P_kW"] for p in i["plecari"]] == [11] * 4 and i.get("P_kW") != 11


def test_autocorectura_schema_de_pamant_si_greseala():
    assert I("TD birouri din TG, TT... nu, TN-S. plecari: prize 16A, iluminat 10A")["schema_pamant"] == "TN-S"
    assert I("casa mono 9 kw, gresit, e 12 kw, tncs")["alimentare"]["P_aprobata_kW"] == 12
    assert rec(I("casa tri 20 kw tncs, pc 10 kw, scuze, pc 12 kw"), "pompa_caldura")[0]["P_kW"] == 12


def test_nu_e_autocorectura():
    """„nu știu dacă…”, „fără panouri, nu, …” nu înlocuiesc nimic"""
    assert I("casa tri 16 kw tncs, nu stiu daca e tt")["alimentare"]["P_aprobata_kW"] == 16


# 2. cascade
def test_cascada_sageti_trei_niveluri():
    i = I("TG (din PT 400 kVA, TN-S) -> TD-A (pompe 2 x 5,5 kW) -> TE-A1 (iluminat 3 kW)")
    assert i["pt_Sn_kVA"] == 400 and len(i["plecari"]) == 1 and i["plecari"][0]["nume"] == "TD-A"
    assert any(k["nume"] == "TE-A1" and k["copii"][0]["P_kW"] == 3 for k in i["plecari"][0]["copii"])


def test_cascada_din_tg_pleaca_nu_e_a_doua_sursa():
    d = R("TG fabrica din PT 1000 kVA, TN-S. Din TG pleaca TD-1 200 kW si TD-2 150 kW; TD-2 alimenteaza la randul lui "
          "TE-21 50 kW, TE-22 60 kW.")
    i = d["intrare_fizica"]
    assert d["actiune"] != "refuza" and "contradic" not in Q(d)
    assert [p["nume"] for p in i["plecari"]] == ["TD-1", "TD-2"] and len(i["plecari"][1]["copii"]) == 2


def test_cascada_din_indentare():
    i = I("TG\n - TD-X\n    - compresor 15 kW\n    - pompa 4 kW\n - TD-Y\n    - iluminat 5 kW\nsursa PT 630 kVA, TN-S")
    assert [(p["nume"], len(p["copii"])) for p in i["plecari"]] == [("TD-X", 2), ("TD-Y", 1)]


def test_tg_plus_te_etaj_la_casa_fara_dublare():
    i = I("Casa P+1, trifazat, Pa 20 kW, TN-C-S. Parter: 4 circuite prize, 2 iluminat. Etaj: TE-etaj alimentat cu "
          "CYY-F 5x6 de 22 m, cu 3 circuite prize, 2 iluminat, 1 AC 2,5 kW.")
    te = i["tablouri_secundare"][0]
    assert te["L_m"] == 22 and te["cablu"]["S_fortat"] == 6
    assert sum(1 for x in te["circuite"] if x["receptor"] == "prize") == 3
    assert not rec(i, "aer_conditionat") and i["alimentare"].get("L_coloana_m") != 22


# 3. plecări fantomă
def test_pi_pa_in_bilant_nu_sunt_plecari():
    i = I("Bilant: Pi = 300 kW, Pa = 210 kW. Alimentare PT 400 kVA. Consumatori principali: TD1 120 kW, TD2 90 kW")
    assert [p["P_kW"] for p in i["plecari"]] == [120, 90] and i["P_kW"] == 210


def test_tt_si_tc_in_celula_de_masura_nu_e_schema_tt():
    i = I("PT 630 kVA 20/0,4 kV, celula de masura cu TC si TT, plecari JT: 4 x 250 A")
    assert i.get("schema_pamant") != "TT" and i["masura"] == "MT" and len(i["plecari"]) == 4


def test_puterea_instalata_cef_e_suma_de_control():
    i = I("ATR: racord in BMPT 3x200 A. Puterea instalata a CEF: 110 kW. Inv: 1 x SG100CX + 1 x SG10RT. TN-C-S")
    assert inv(i) == [(1, 10), (1, 100)]


def test_dno_cut_out_si_celula_intreruptor():
    i = I("main panel TN-S, fed from DNO cut-out 80A 3ph, 3 x 5.5 kW fans DOL")
    assert i["origine"] == "bmpt" and not any(p.get("In_A") == 80 for p in pl(i))
    j = I("PT 800 kVA 20/0,4 kV, celula cu intreruptor in vid si protectii 50/51, plecari 2 x 400 A")
    assert j["celula_trafo"] == "intreruptor"


def test_rezerva_1_plus_1_in_tablou():
    d = R("statie pompare apa: pompa 30 kW soft starter si pompa 30 kW rezerva (1+1), din TG, TN-S")
    i = d["intrare_fizica"]
    assert d["actiune"] != "refuza" and len([p for p in pl(i) if p.get("P_kW") == 30]) == 2
    assert any(p.get("rezerva") for p in pl(i))


# 4. cifre
def test_cifre_lista_si_fiecare():
    assert inv(I("am 3 invertoare: 10, 10 si 8 kw, tri, pa 30 kw")) == [(1, 8), (2, 10)]
    i = I("2 baterii BYD de 5,1 kWh fiecare pe invertor hibrid 8 kW, casa tri pa 10")
    assert abs(i["baterie_kWh"] - 10.2) < 1e-6 and i["Pn_inv_kW"] == 8


def test_putere_termica_nu_e_electrica():
    i = I("pompa de caldura 12 kW termic, 4 kW electric, casa mono 9 kw tncs")
    assert rec(i, "pompa_caldura")[0]["P_kW"] == 4


def test_alternativa_fara_unitate_e_intrebata():
    d = R("apartament 10 kw (nu stiu daca e 10 sau 16) tri tncs")
    assert d["actiune"] != "genereaza" and "10 kw sau 16 kw" in Q(d)


def test_invertoare_limitate_individual():
    i = I("CEF 300 kWp cu 3 x SG110CX limitate la 90 kW, PT nou 400 kVA")
    assert i.get("limitare_injectie_kW") is None and inv(i) == [(3, 110)]


def test_retea_mixta_tri_plus_mono_pe_faza():
    d = R("prosumator: 1 x SUN2000-8KTL-M1 trifazat + 1 x SUN2000-3KTL-L1 monofazat pe L2, BMPT 3x32 A")
    i = d["intrare_fizica"]
    assert i["retea"] == "tri" and d["actiune"] != "refuza"
    assert [g.get("faza") for g in i["invertoare"] if g["Pn_kW"] == 3] == ["L2"]


# 5. lungimi
def test_lungimea_receptorului_ramane_pe_circuit():
    i = I("casa mono 7 kw tncs, statie ve 3,7 kw la 40 m de tablou")
    assert rec(i, "vehicul_electric")[0]["L_m"] == 40 and i["alimentare"].get("L_coloana_m") != 40
    j = I("ap la bloc mono 6 kw, priza pentru masina electrica in garaj, 3,7 kw, 45 m")
    assert rec(j, "vehicul_electric")[0]["L_m"] == 45
    assert not any("exterior" in x["nume"].lower() for x in j["circuite"])


# 6. GE / backup
def test_ge_manual_la_casa_e_sursa():
    i = I("casa mono 5 kw tncs, generator 4 kW cu comutator manual pe tot tabloul")
    assert i["tip_schema"] == "locuinta" and i["ge_rezerva"]["comutare"] == "manual"


def test_ups_fara_panouri_nu_e_prosumator():
    d = R("UPS pentru centrala si server, casa tri 12 kw tncs, fara panouri")
    assert d["tip_schema"] == "locuinta" and d["actiune"] != "refuza"


# 7. mărire de putere
def test_marire_formulata_vrem_sa_trecem():
    d = R("bransament monofazat 6 kW, vrem sa trecem pe trifazat 20 kW, casa, tncs")
    assert d["intrare_fizica"]["alimentare"]["P_aprobata_kW"] == 20 and d["intrare_fizica"]["retea"] == "tri"
    assert "contradic" not in Q(d)


# 8. siguranță: doar consumatorii de siguranță, în tablou mixt și pe GE
def test_tablou_mixt_doar_consumatorii_de_siguranta():
    i = I("TG hala din PT 400 kVA TN-S: pompa hidranti 30 kW, ventilator hala 5 kW, iluminat 6 kW")
    sig = {p["nume"]: p.get("siguranta") for p in i["plecari"]}
    assert sig == {"Pompa hidranti": True, "Ventilator hala": False, "Iluminat": False}
    m, _ = constructor.genereaza(i)
    assert "siguranță" not in m["carcasa"]["sub"] or "înainte de Q1" in m["carcasa"]["sub"]


def test_statie_pompare_psi_pe_ge_ats():
    i = I("grup de pompare incendiu: 2 pompe 45 kW (1A+1R), pompa jockey 2,2 kW, din PT 400 kVA si GE 160 kVA cu ATS")
    assert i["tip_schema"] == "ge_ats" and i.get("siguranta_tablou")
    p45 = [x for x in i["consumatori"] if x["P_kW"] == 45]
    assert p45 and p45[0]["siguranta"] and p45[0].get("n") == "1+1"
    # echipa1 P1-8: în regim GE contactul indirect al pompelor (fără DDR) cere o soluție declarată — singurele blocaje
    assert blocante(i) <= {"V85", "V97"}
    assert not blocante(dict(i, legaturi_echipotentiale=True))


def test_normalii_pe_ge_cu_vital_false():
    i = I("TG spital din PT 1000 kVA, TN-S. Consumatori vitali pe GE 250 kVA cu ATS: bloc operator 60 kW, iluminat "
          "siguranta 5 kW. Normali: climatizare 200 kW, prize 50 kW")
    assert [x.get("vital") for x in i["consumatori"] if x["P_kW"] in (200, 50)] == [False, False]
    assert i["P_sarcina_kW"] == 65


# 9. contradicții întrebate
def test_q1_impus_sub_ib():
    d = R("TD din TG TN-S cu intrerupator general 32 A, plecari: 2 motoare 15 kW")
    assert d["actiune"] != "genereaza" and "32" in Q(d)


def test_bmpm_si_tablou_trifazat():
    d = R("TG trifazat din BMPM 32A, TN-C-S, motor 3 kW")
    assert d["actiune"] != "genereaza" and "bmpm" in Q(d)


def test_q_bransament_peste_pa():
    d = R("casa mono 6 kw tncs, siguranta bransament 63A ca sa nu mai sara")
    assert "63" in Q(d)


def test_sursa_tabloului_mare_intrebata_cea_mica_presupusa():
    assert "surs" in Q(R("TG pentru hala cu 4 compresoare de 30 kW"))
    assert "Din ce sursă" not in " ".join(R("TG atelier cu 2 motoare de 5,5 kW")["intrebari"])


def test_magazin_tt_nu_e_locuinta():
    i = I("farmacie parter, bransament trifazat TT, BMPT 40 A: frigider medicamente 2 x 0,8 kW, iluminat 2 kW, prize 4 circuite")
    assert i["tip_schema"] == "tablou" and i["schema_pamant"] == "TT"


def test_cabluri_in_paralel_ajung_in_motor():
    i = I("TG din PT 1000 kVA, TN-S, alimentare 2 cabluri NA2XY 3x240+120 in paralel, 50 m, plecari TD1 300 kW, TD2 200 kW")
    assert i["cablu"]["n_paralel"] == 2 and i["cablu"]["tip_cablu"] == "NA2XY" and i["cablu"]["izolatie"] == "XLPE"
    _, calc = constructor.genereaza(i)
    c1 = calc["rezultat"]["Q1_C1"]
    assert c1["n_paralel"] == 2 and c1["izolatie"] == "XLPE"


def test_cablul_impus_al_pompei_de_incendiu():
    i = I("TD din TG TN-S: pompa sprinkler 18,5 kW cu cablu NHXH FE180 E90 4x16 la 60 m, iluminat 2 kW")
    p = [x for x in i["plecari"] if "sprinkler" in x["nume"].lower()][0]
    assert p["siguranta"] and p["L_m"] == 60 and p["cablu"]["S_fortat"] == 16 and i.get("L_alimentare_m") != 60
