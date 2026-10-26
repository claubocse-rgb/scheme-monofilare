"""Regresii runda 10 (teste/r10/{locuinte,fotovoltaic,industrial}.md) — INTERPRETORUL LOCAL (regulile, fără Claude),
pe calea aplicației fără cheie API: `interpretor.interpreteaza(text)` = regulile locale + întrebările din verificarea
motorului (clasa 8: niciun BLOCANT fără întrebare).

1. Fiecare frază r10 P0/P1 (+ P2 din clasele reparate) cu verificările din teste/r10/reverificare.py — scrise din
   „așteptat” și din observația testerului, nu din ce face codul.
2. Pe toate frazele r10: plasa de siguranță și „nimic blocat fără întrebare”.
3. Clasele r10 pe formulări NOI (5–10 pe clasă, inventate, diferite de cele din rapoarte): faze monofazate, existent +
   nou, autocorecturi, cantități vs puteri, cuvinte capcană, topologii PT / GE, locuință, blocaje întrebate.

Rulare: cd /home/claude/sm && python3 -m pytest -q tests/test_interpretor_r10.py
"""
import importlib.util
import sys
from pathlib import Path

import pytest

RAD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAD))

from engine import constructor, validare  # noqa: E402
from engine.interpretor import interpreteaza  # noqa: E402

_spec = importlib.util.spec_from_file_location("reverificare_r10", RAD / "teste" / "r10" / "reverificare.py")
rv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rv)

CAZURI = rv.incarca()
EXPLICIT = [c for c in CAZURI if c[5]]


def _id(c):
    return f"{c[1]}-{c[4]}"


@pytest.mark.parametrize("dom,fid,text,vt,prio,verif", EXPLICIT, ids=[_id(c) for c in EXPLICIT])
def test_fraza_r10(dom, fid, text, vt, prio, verif):
    c = rv.rezultat(text)
    verdict, lipsa = rv.evalueaza(verif, c)
    r = c["r"]
    assert verdict == "corect", (lipsa, r["intrare_fizica"], r["intrebari"], r["neconsumat"])


@pytest.mark.parametrize("text", sorted({c[2] for c in CAZURI}))
def test_plasa_si_blocaj_intrebat_r10(text):
    c = rv.rezultat(text)
    assert rv.plasa_ok(c["r"]), c["r"]["neconsumat"]
    ok = rv.BLOC_INTREBAT[1](c)
    assert ok, ([x for x in (c["v"] or {}).get("verificari") or [] if x.get("nivel") == "BLOCANT"], c["r"]["intrebari"])


# ------------------------------------------------------------------------------------------------- utilitare
def R(text):
    return interpreteaza(text)


def I(text):
    return R(text)["intrare_fizica"]


def faze(i):
    return sorted(f for g in i.get("invertoare") or [] for f in [g.get("faza")] * int(g.get("n", 1)) if f)


def inv(i):
    return sorted((g.get("n", 1), g.get("Pn_kW"), bool(g.get("existent"))) for g in i.get("invertoare") or [])


def circ(i, rec=None):
    out = list(i.get("circuite") or [])
    for t in i.get("tablouri_secundare") or []:
        out += t.get("circuite") or []
    return [x for x in out if rec is None or x.get("receptor") == rec]


def pl(i):
    out = []

    def w(L):
        for p in L or []:
            out.append(p)
            w(p.get("copii"))
    w(i.get("plecari"))
    return out


def Q(r):
    return " ".join(r["intrebari"] + [r.get("refuz_motiv") or ""]).lower()


def motor_blocheaza(i):
    m, _ = constructor.genereaza(i)
    return validare.valideaza(m)["blocheaza"]


# ------------------------------------------------------------------- 1. faze monofazate (regresia r9 #7)
@pytest.mark.parametrize("text,asteptat", [
    ("3 x Fronius Primo 5.0-1, unul pe fiecare faza, BMPT 3x40 A", ["L1", "L2", "L3"]),
    ("6 x SUN2000-5KTL-L1, cate 2 pe fiecare faza, BMPT 3x63A", ["L1", "L1", "L2", "L2", "L3", "L3"]),
    ("2 invertoare monofazate Huawei SUN2000-6KTL-L1 pe L1 si L3, casa trifazata 3x32A", ["L1", "L3"]),
    ("invertor monofazat 5 kW pe faza S, casa trifazata 3x25 A", ["L2"]),
    ("prosumator 4 kW monofazat pe faza T, bransament trifazat 3x32A", ["L3"]),
    ("3 x Growatt MIN 5000TL-X, cate unul pe faza, BMPT 3x32A", ["L1", "L2", "L3"]),
    ("invertor Sunny Boy 5.0 pe L3, casa e trifazata", ["L3"]),
    ("9 x SUN2000-4KTL-L1 pe cele trei faze, BMPT 3x80A", ["L1"] * 3 + ["L2"] * 3 + ["L3"] * 3),
])
def test_clasa1_faze(text, asteptat):
    r = R(text)
    i = r["intrare_fizica"]
    assert i["retea"] == "tri" and faze(i) == asteptat, (i, r["intrebari"])
    assert not any("Iac,max" in q and "L1" in q for q in r["intrebari"]), r["intrebari"]   # fără dezechilibru fals


# ------------------------------------------------------------------- 2. existent + nou; N invertoare (listă)
@pytest.mark.parametrize("text,asteptat", [
    ("Avem deja 30 kW (2 x Huawei SUN2000-15KTL-M2), adaugam 1 x SUN2000-50KTL-M3. TG existent.",
     [(1, 50, False), (2, 15, True)]),
    ("Exista 1 x Fronius Symo 15.0-3-M montat. Se adauga 2 x SG33CX. Racord TG existent", [(1, 15, True), (2, 33, False)]),
    ("invertoare existente 2 x 20 kW nu se modifica; nou 1 x SUN2000-30KTL-M3, TG existent", [(1, 30, False), (2, 20, True)]),
    ("Pe TG existent avem 1 x Symo 20.0-3-M (20 kW existent). Montam 1 x Sungrow SG50CX nou.", [(1, 20, True), (1, 50, False)]),
    ("3 invertoare (Fronius 20 kW, Huawei 30 kW si SMA 25 kW), TG existent", [(1, 20, False), (1, 25, False), (1, 30, False)]),
    ("2 invertoare (SG110CX si SUN2000-100KTL-M2), PT nou 400 kVA", [(1, 100, False), (1, 110, False)]),
    ("Pe TG existent sunt deja 3 invertoare SG33CX (99 kW existenti). Adaugam 1 x SG110CX. Racord TG existent.",
     [(1, 110, False), (3, 33, True)]),
])
def test_clasa2_existent_nou(text, asteptat):
    r = R(text)
    assert r["actiune"] != "refuza" and inv(r["intrare_fizica"]) == sorted(asteptat), (r["intrare_fizica"], r["intrebari"])


# ------------------------------------------------------------------- 3. autocorecturi în formulări noi
def test_clasa3_autocorecturi():
    assert inv(I("CEF cu 3 x SG110CX, rectific: 4 x SG110CX. PT nou 630 kVA")) == [(4, 110, False)]
    assert [x["P_kW"] for x in circ(I("casa tri 15 kW, plita 9 kW, mai exact 7,5 kW"), "plita")] == [7.5]
    assert I("PT nou 400 kVA, am gresit, nu 400 ci 630 kVA. CEF 4 x SUN2000-100KTL-M2")["pt_Sn_kVA"] == 630
    r = R("CEF 2 x SG50CX (100 kW, nu 120). TG existent")
    assert inv(r["intrare_fizica"]) == [(2, 50, False)] and r["actiune"] != "refuza"
    assert [x["P_kW"] for x in circ(I("casa mono 6 kW cu boiler 2 kW, AC 3,5 kW? nu, AC 2,5 kW"), "aer_conditionat")] == [2.5]
    r = R("CEF 90 kW cu 3 x SG30CX. Scuze, sunt 4 x SG30CX, deci 120 kW. TG existent.")
    assert inv(r["intrare_fizica"]) == [(4, 30, False)] and r["actiune"] != "refuza" and not r["neconsumat"]
    i = I("casa tri 20 kW cu VE 22 kW. corectie: VE nu e 22 kW, e 11 kW; restul ramane")
    assert [x["P_kW"] for x in circ(i, "vehicul_electric")] == [11]
    assert I("Corectez: nu 250 kVA, ci 400 kVA. TG din PT propriu, TN-S, plecari: 2 motoare 30 kW")["pt_Sn_kVA"] == 400
    i = I("casa tri 10 kW, pompa caldura 12 kW electric? nu, 12 kW termic, 3,5 kW electric tri")
    assert [x["P_kW"] for x in circ(i, "pompa_caldura")] == [3.5]


# ------------------------------------------------------------------- 4. cantități vs puteri, tabele, atribute globale
def test_clasa4_cantitati():
    i = I("casa tri 12 kW aprobati, 6 circ prize 4 ilum, boiler 2 kW")
    assert len(circ(i, "prize")) == 6 and len(circ(i, "iluminat")) == 4 and not any(x.get("P_kW") == 4 for x in circ(i, "prize"))
    i = I("apartament mono 5 kW, 4 prize 2 lumini, plita 3,5 kW")
    assert len(circ(i, "prize")) == 4 and len(circ(i, "iluminat")) == 2
    i = I("TG hala din PT propriu 630kVA, TN-S, ventilatoare: 3 x 4 kW si 2 x 7,5 kW")
    assert sorted(p["P_kW"] for p in pl(i)) == [4, 4, 4, 7.5, 7.5]
    r = R("TE pompe: 2 pompe 15 kW (1+1 rezerva), din TG existent, TN-S")
    assert r["actiune"] != "refuza" and sum(1 for p in pl(r["intrare_fizica"]) if p.get("rezerva")) == 1
    i = I("TDF cu plecari: M1 15kW, M2 7.5kW, M3 4kW, ks 0.8, cos 0.86, din TG existent")
    assert i["ks"] == 0.8 and i["cosfi"] == 0.86 and len(pl(i)) == 3
    i = I("Item,Qty\nSUN2000-50KTL-M3,4\nNew 400kVA substation,1")
    assert inv(i) == [(4, 50, False)] and i["pt_Sn_kVA"] == 400
    r = R("Invertor;Buc;Pn kW\nSG33CX;3;33\nSG50CX;1;50\nRacord TG existent")
    assert inv(r["intrare_fizica"]) == [(1, 50, False), (3, 33, False)] and r["actiune"] != "refuza"
    i = I("Statie de pompare: 1 pompa 11 kW + 1 de rezerva, din TG existent TN-S")
    assert [p.get("rezerva", False) for p in pl(i)] == [False, True]
    r = R("Nr\tReceptor\tP[kW]\tU[V]\tcos\n1\tCompresor\t11\t400\t0,85\n2\tIluminat\t2\t230\t0,95\nalimentare din TG existent, TN-S")
    assert r["actiune"] != "refuza" and [p.get("retea") for p in pl(r["intrare_fizica"])] == ["tri", "mono"]
    i = I("TG cu sursa dubla: PT1 630 kVA si PT2 630 kVA, cupla automata (interblocaj 2 din 3), 2 semibare cu cate 2 plecari de 100 kW")
    assert i["n_trafo"] == 2 and len(pl(i)) == 4


# ------------------------------------------------------------------- 5. cuvinte care nu sunt ce par
def test_clasa5_cuvinte():
    i = I("pt uscat 1000, tg 1600A, 6 plecari 250A")
    assert i["Sn_kVA"] == 1000 and i["trafo_izolatie"] == "uscat" and i["In_Q_JT_A"] == 1600
    r = R("Cablu MT 3x(1x240) NA2XS(F)2Y 12/20 kV, 300 m, PT 630 kVA 20/0,4 kV")
    assert r["intrare_fizica"]["U_MT_kV"] == 20 and "contradic" not in Q(r) and r["intrare_fizica"]["cablu_MT"]["L_m"] == 300
    i = I("TG magazin, TN-S, BMPT 3x80A, iluminat 4 kW, prize 6 circuite, frigorifice 3 x 2 kW")
    assert i["origine"] == "bmpt" and not any("bmpt" in p["nume"].lower() for p in pl(i))
    r = R("Hi, SLD for car wash: 2 pumps 11 kW, blower 7.5 kW, lighting 1 kW, supply 3x50A from DSO, TT")
    assert r["tip_schema"] == "tablou" and r["intrare_fizica"]["origine"] == "bmpt" and r["intrare_fizica"]["schema_pamant"] == "TT"
    r = R("PTA 160 kVA pe stalp cu cutie BMPT 250 A")
    assert r["tip_schema"] == "pt" and r["intrare_fizica"]["pt_aerian"] and r["actiune"] != "refuza"
    assert R("atelier tamplarie: fierastrau 5,5 kW, rindea 4 kW, exhaustor 3 kW, din BMPT 3x40A")["tip_schema"] == "tablou"
    i = I("casa 20 kVA trifazat cu pompa de caldura 8 kW")
    assert i["alimentare"]["P_aprobata_kW"] == 18 and i["alimentare"]["In_Q_bransament_A"] == 32
    i = I("connection to existing LV switchboard: 2 x SG110CX, export limited to 150 kW")
    assert i["racord"] == "tg_existent" and i["limitare_injectie_kW"] == 150
    assert R("cuptor electric 72 kW la 400V")["tip_schema"] == "tablou"


# ------------------------------------------------------------------- 6. topologii PT / GE / tablou (cheile pentru motor)
def test_clasa6_topologii():
    i = I("PT cu 2 transformatoare 630 kVA in paralel, TG 2000 A, 4 plecari de 250 A")
    assert i["n_trafo"] == 2 and i["cupla"] == "inchisa" and i["In_Q_JT_A"] == 2000
    i = I("ATS intre cele doua transformatoare 1000 kVA, TG cu 3 plecari de 200 kW")
    assert i["sursa_rezerva"] == "trafo" and i["n_trafo"] == 2 and not i.get("Sn_GE_kVA") and len(pl(i)) == 3
    i = I("GE 250 kVA ca unica sursa, fara retea, TN-S, plecari: moara 90 kW, iluminat 4 kW")
    assert i["fara_retea"] is True and "sursa_retea" not in i
    i = I("TG cu GE 150 kVA si ATS, din PT propriu 400 kVA. Vitali: pompe 2x15 kW. Nevitali: cuptoare 3x40 kW.")
    assert {x["nume"]: x["vital"] for x in i["consumatori"]} == {"Pompe": True, "Cuptoare": False} and i["P_sarcina_kW"] == 30
    assert I("PT 630 kVA uk 6%, TG cu 3 plecari de 200 A")["uk_pct"] == 6
    assert [p.get("pornire") for p in pl(I("TD pompe: pompa 30 kW cu convertizor de frecventa, din PT propriu 400 kVA"))] == ["convertizor"]
    p = pl(I("din TG existent adaugam plecare noua pentru wallbox 11 kW, cablu 5x6 Cu, 30 m, RCD tip B"))
    assert len(p) == 1 and p[0]["ddr"]["tip"] == "B" and p[0]["L_m"] == 30 and p[0]["cablu"]["S_fortat"] == 6
    p = pl(I("Rezerva 1+1 pentru pompele de incendiu: electropompa 30 kW + motopompa diesel, din PT propriu 250 kVA"))
    assert len(p) == 1 and p[0]["siguranta"] is True
    i = I("TG IT cu UPS 60 kVA cu bypass, din PT 400 kVA, plecari PDU A 20 kW si PDU B 20 kW")
    assert any(p.get("ups") and p.get("bypass") and len(p.get("copii") or []) == 2 for p in pl(i))
    i = I("Racord in PT existent propriu 2x630 kVA (bara JT a T2), plecare noua cu sigurante MPR 400 A. CEF 4 x SG50CX")
    assert i["bara"] == "T2" and i["racord_In_Q_A"] == 400 and i["racord_Q_tip"] == "gG"
    i = I("Alimentare din PT existent 400 kVA, cablu 3x150+70 Al existent 80 m, TN-C-S, separare PEN in TG, plecari: 3 motoare 15 kW")
    assert i["separare_PEN"] == "TG" and i["cablu"]["existent"] is True


# ------------------------------------------------------------------- 7. locuință
def test_clasa7_locuinta():
    r = R("Hibrid 10 kW trifazat cu baterie 10 kWh si tablou EPS pentru frigider, centrala, router")
    i = r["intrare_fizica"]
    assert r["tip_schema"] == "prosumator" and len(i["backup"]["circuite"]) == 3 and i.get("bess", {}).get("cuplaj") != "ca"
    b = I("EPS pe toata casa: hibrid 8 kW tri, comutare automata, N comutat")["backup"]
    assert b["toata_casa"] and b["comutare"] == "ATS" and b["N_comutat"]
    assert sorted(x["P_kW"] for x in circ(I("casa tri 18 kW cu 2 statii VE: una 11 kW si una 3,7 kW"), "vehicul_electric")) == [3.7, 11]
    al = I("casa mono 7 kW cu cablu 3x10mm de 30 m pana la tablou")["alimentare"]
    assert al["cablu"]["S_fortat"] == 10 and al["L_coloana_m"] == 30
    i = I("casa 2 corpuri: corp A 12 kW, corp B la 30 m 6 kW tri, un singur bransament 3x40")
    td = i["tablouri_secundare"][0]
    assert td["L_m"] == 30 and td["P_kW"] == 6 and i["alimentare"]["In_Q_bransament_A"] == 40
    assert I("prosumator 10 kW, injectie limitata la 50% din putere, BMPT 3x32A")["limitare_injectie_kW"] == 5
    i = I("CEF 500 kW cu 5 invertoare de 100 kW, PT nou 630 kVA, ATR permite doar 400 kW evacuare")
    assert i["limitare_injectie_kW"] == 400
    g = I("generator 6 kVA monofazat cu comutator manual, casa monofazata 32 A")["ge_rezerva"]
    assert g == {"Sn_kVA": 6, "comutare": "manual", "retea": "mono"}
    i = I("piscina cu pompa 1,1 kW si pompa de caldura 5 kW, TD piscina la 30 m de casa, casa trifazata 12 kW")
    td = [t for t in i["tablouri_secundare"] if "piscin" in t["nume"].lower()][0]
    assert td["L_m"] == 30 and sorted(x["P_kW"] for x in td["circuite"]) == [1.1, 5]
    i = I("casa mono 8 kW: AC multisplit 4 unitati interioare, unitate exterioara 3,5 kW")
    assert [x for x in circ(i, "aer_conditionat") if x.get("multisplit")][0]["unitati_interioare"] == 4
    assert len(circ(i, "aer_conditionat")) == 1


# ------------------------------------------------------------------- 8. nimic blocat fără întrebare
@pytest.mark.parametrize("text,cuv", [
    ("BMPT 3x32A existent, vreau 30 kW fara marire", "atr"),
    ("o casa la tara, retea TN-C, trifazat 10 kW", "tn-c-s"),
    ("casa trifazata 9 kW, instalatie TN-C-S, priza de pamant 20 ohmi", "4 ω"),
    ("apartament mono 4 kW, plita inductie 7,4 kW, cuptor 2 kW", "plit"),
    ("vreau wallbox 11 kW la casa, bransament trifazat 3x16A", ""),
    ("casa mono 32A, plita 7 kW, cuptor 3,5 kW, AC 2 x 3,5 kW, boiler 2 kW", "aprobat"),
])
def test_clasa8_blocaj_intrebat(text, cuv):
    r = R(text)
    assert r["actiune"] != "genereaza" and r["intrebari"] and cuv in Q(r), (r["actiune"], r["intrebari"])
    if r["actiune"] != "refuza" and motor_blocheaza(r["intrare_fizica"]):
        assert r["intrebari"]
