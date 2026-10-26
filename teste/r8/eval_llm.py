"""Evaluarea citirii avansate pe 60 de fraze grele din r8 (20 / domeniu, alese dintre cele greșite / parțiale).

ÎNAINTE  = regulile locale (interpreteaza_local), ca azi fără cheie.
DUPĂ     = răspunsul SIMULAT al lui Claude (llm_simulat.json — NU e un apel real) + fuziunea cu regulile locale.
Ambele trec prin constructor.genereaza + validare.valideaza. Verificările pe frază sunt scrise din câmpul „asteptat”.

    python3 teste/r8/eval_llm.py [-v]
"""
import json
import pathlib
import sys

RAD = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAD))
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from engine import interpretor, constructor, validare  # noqa: E402
from selectie_llm import selectie  # noqa: E402

_J = json.loads((pathlib.Path(__file__).parent / "llm_simulat.json").read_text(encoding="utf-8"))
SIM = _J["raspunsuri"]                                                    # v1: orb (scris înainte de „asteptat”)
SIM2 = {d: dict(SIM[d], **_J.get("raspunsuri_v2", {}).get(d, {})) for d in SIM}   # v2: după ajustarea promptului


# ------------------------------------------------------------------------------------------- utilitare de verificare
def Q(c):
    """tot ce i se spune proiectantului: întrebări, refuz, avertismente, „nu am înțeles”."""
    r = c["r"]
    return " ".join([*(r.get("intrebari") or []), r.get("refuz_motiv") or "", *(r.get("avertismente") or []),
                     *(r.get("neconsumat") or [])]).lower()


def I(c):
    return c["r"].get("intrare_fizica") or {}


def gen(c):
    return c["r"]["actiune"] != "refuza"


def coduri(c, nivel=None):
    v = c.get("v") or {}
    return {x.get("cod") for x in v.get("verificari") or [] if nivel is None or x.get("nivel") == nivel}


def inv(c):
    i = I(c)
    if i.get("invertoare"):
        return sorted((g.get("n", 1), g.get("Pn_kW")) for g in i["invertoare"])
    return [(1, i["Pn_inv_kW"])] if i.get("Pn_inv_kW") else []


def pl(c, toate=True):
    out = []

    def w(L):
        for p in L or []:
            out.append(p)
            if toate:
                w(p.get("copii"))
    w(I(c).get("plecari"))
    return out


def gaseste(L, cuv):
    return [p for p in L if cuv in interpretor._fara_diacritice(p.get("nume", "")).lower()]


def circ(c):
    return I(c).get("circuite") or []


def rec(c, r):
    return [x for x in circ(c) if x.get("receptor") == r]


def pa(c):
    i = I(c)
    return i.get("P_aprobata_kW", (i.get("alimentare") or {}).get("P_aprobata_kW"))


def sig(c, cuv):
    return any(p.get("siguranta") for p in gaseste(pl(c), cuv)) or I(c).get("siguranta_tablou") is True


def apx(a, b, tol=0.05):
    return a is not None and b is not None and abs(a - b) <= tol * max(1, abs(b))


def n_sum(L):
    return sum(p.get("n_circuite") or 1 for p in L)


# ------------------------------------------------------------------------------------------- verificări pe frază
V = {"fotovoltaic": {
    28: [("întrebare: 3 declarate vs 4", lambda c: "invert" in Q(c) and ("3" in Q(c) or "4" in Q(c))),
         ("fără invertoare fantomă (Σ ≤ 320 kW)", lambda c: sum(n * p for n, p in inv(c)) <= 320)],
    33: [("3 × 8,2 kW", lambda c: sum(n for n, p in inv(c) if p == 8.2) == 3),
         ("monofazate / câte unul pe fază semnalat", lambda c: "faz" in Q(c) or any(g.get("faza") for g in I(c).get("invertoare") or [])),
         ("pe L1/L2/L3 (nu 3×400 V 4P)", lambda c: sorted(g.get("faza") or "" for g in I(c).get("invertoare") or []) == ["L1", "L2", "L3"])],
    51: [("2 × SG50CX", lambda c: inv(c) == [(2, 50)]), ("100 kWp", lambda c: I(c).get("kWp") == 100)],
    58: [("2 × 50 kW (Σ 100)", lambda c: inv(c) == [(2, 50)]),
         ("model necunoscut: presupunere / întrebare", lambda c: "fis" in interpretor._fara_diacritice(
             " ".join(c["r"]["presupus"])).lower() or "model" in Q(c))],
    61: [("6 × 100 kW", lambda c: inv(c) == [(6, 100)]), ("700 kWp", lambda c: apx(I(c).get("kWp"), 700)),
         ("PT 630 < 660 kVA semnalat", lambda c: "630" in Q(c) or "V67" in coduri(c))],
    26: [("3 × 100 + 2 × 50", lambda c: inv(c) == [(2, 50), (3, 100)]),
         ("BESS 100 kW / 200 kWh", lambda c: (I(c).get("bess") or {}).get("kWh") == 200),
         ("PT existent, fără trafo nou", lambda c: gen(c) and (I(c).get("pt_existent") is True or I(c).get("racord") == "tg_existent"))],
    34: [("2 × 110 kW", lambda c: inv(c) == [(2, 110)]), ("injecție zero", lambda c: I(c).get("limitare_injectie_kW") == 0),
         ("Ik 20 kA la bară", lambda c: I(c).get("Ik3_TG_kA") == 20),
         ("Q TG 400 A", lambda c: I(c).get("racord_In_Q_A") == 400),
         ("racord în TG existent", lambda c: I(c).get("racord") == "tg_existent")],
    45: [("20 × 100 kW", lambda c: inv(c) == [(20, 100)]), ("BESS 2 MW / 4 MWh", lambda c: (I(c).get("bess") or {}).get("kWh") == 4000),
         ("2 trafo × 2000", lambda c: I(c).get("n_trafo") == 2 and I(c).get("pt_Sn_kVA") == 2000),
         ("măsura MT", lambda c: I(c).get("masura") == "MT"), ("limitare 3 MW", lambda c: I(c).get("limitare_injectie_kW") == 3000),
         ("8 PCS reprezentate", lambda c: (I(c).get("bess") or {}).get("n_pcs") == 8)],
    53: [("Ik 30 kA la bară", lambda c: I(c).get("Ik3_TG_kA") == 30),
         ("Iac ≈ 96 A > Q 63 A semnalat", lambda c: "63" in Q(c) or "V44" in coduri(c, "BLOCANT"))],
    1: [("1 × 100 kW", lambda c: inv(c) == [(1, 100)]), ("limitare 80 kW", lambda c: I(c).get("limitare_injectie_kW") == 80),
        ("racord BMPT 250 A", lambda c: I(c).get("racord") == "bmpt" and I(c).get("In_Q_bransament_A") == 250),
        ("generează (fără refuz I08)", gen)],
    7: [("8 invertoare", lambda c: sum(n for n, _ in inv(c)) == 8),
        ("Pn 300 kW (330 = Smax)", lambda c: inv(c) == [(8, 300)]),
        ("800 V c.a.", lambda c: 800 in (I(c).get("U_ca_V"), I(c).get("U_inv_ca_V"))),
        ("măsura MT", lambda c: I(c).get("masura") == "MT")],
    9: [("30 × 100 kW", lambda c: inv(c) == [(30, 100)]),
        ("2 trafo × 1600", lambda c: I(c).get("n_trafo") == 2 and I(c).get("pt_Sn_kVA") == 1600),
        ("măsura MT", lambda c: I(c).get("masura") == "MT")],
    13: [("BESS 1 MW / 2 MWh", lambda c: (I(c).get("bess") or {}).get("P_kW") == 1000 and (I(c).get("bess") or {}).get("kWh") == 2000),
         ("PT nou 1250", lambda c: I(c).get("pt_Sn_kVA") == 1250), ("măsura MT", lambda c: I(c).get("masura") == "MT"),
         ("4 PCS × 250 kW reprezentate", lambda c: (I(c).get("bess") or {}).get("n_pcs") == 4)],
    15: [("2 × 110 kW", lambda c: inv(c) == [(2, 110)]), ("limitare 100 kW", lambda c: I(c).get("limitare_injectie_kW") == 100),
         ("generează (fără refuz I08)", gen)],
    16: [("întrebare: injecție zero vs 20 kW", lambda c: "injec" in Q(c)),
         ("rețea declarată din model / întrebată", lambda c: I(c).get("retea") == "tri" or "monofaz" in Q(c))],
    24: [("întrebare: Iac ≈ 80 A > BMPT 40 A", lambda c: any(("40" in q or "bmpt" in q.lower()) for q in c["r"].get("intrebari") or []))],
    25: [("întrebare: 800 V + 400 V", lambda c: "800" in Q(c))],
    29: [("întrebare: BMPT vs PT nou", lambda c: "bmpt" in Q(c))],
    35: [("10 × 100 kW", lambda c: inv(c) == [(10, 100)]),
         ("PT existent, măsură MT", lambda c: I(c).get("pt_existent") is True and I(c).get("masura") == "MT"),
         ("1100 kVA pe T2 1000 kVA semnalat", lambda c: "1000" in Q(c) or "V67" in coduri(c))],
    37: [("autocorectura → 1 × SG110CX", lambda c: inv(c) == [(1, 110)])],
}, "industrial": {
    12: [("siguranță (TDSI)", lambda c: I(c).get("siguranta_tablou") is True or all(x.get("siguranta") for x in I(c).get("consumatori") or [{}])),
         ("Y/Δ la electropompă", lambda c: any(x.get("pornire") == "stea_triunghi" for x in (I(c).get("consumatori") or []) + pl(c))),
         ("consumatori separați (nu „Consumatori 57,2 kW”)", lambda c: len(I(c).get("consumatori") or []) >= 2)],
    14: [("siguranță (desfumare)", lambda c: I(c).get("siguranta_tablou") is True or all(p.get("siguranta") for p in pl(c) or [{}])),
         ("2 ventilatoare 11 kW", lambda c: n_sum([p for p in pl(c) if p.get("P_kW") == 11]) == 2)],
    64: [("pompa incendiu = siguranță", lambda c: any(p.get("siguranta") for p in gaseste(pl(c), "incendiu"))),
         ("pompa tehnologică normală", lambda c: not any(p.get("siguranta") for p in gaseste(pl(c), "tehnolog"))),
         ("PT 630 citit", lambda c: I(c).get("pt_Sn_kVA") == 630)],
    1: [("TG din PT 400", lambda c: I(c).get("pt_Sn_kVA") == 400 and gen(c)),
        ("toți consumatorii (≥ 7 plecări)", lambda c: len(pl(c, False)) >= 7),
        ("CDI = siguranță", lambda c: any(p.get("siguranta") for p in gaseste(pl(c), "detecti"))),
        ("prize 6 circuite", lambda c: any(p.get("n_circuite") == 6 for p in gaseste(pl(c), "priz")))],
    2: [("5 plecări cu P din tabel", lambda c: sorted(p.get("P_kW") or 0 for p in pl(c)) == [6, 11, 18.5, 18.5, 30]),
        ("din TG existent", lambda c: I(c).get("origine") == "tg_existent")],
    4: [("cablu impus 3x120+70, 60 m", lambda c: (I(c).get("cablu") or {}).get("S_fortat") == 120 and I(c).get("L_alimentare_m") == 60),
        ("2 compresoare 42 kW soft", lambda c: len([p for p in pl(c) if p.get("P_kW") == 42 and p.get("pornire") == "soft"]) == 2),
        ("pompa 5,5 kW VFD", lambda c: any(p.get("pornire") == "convertizor" for p in pl(c) if p.get("P_kW") == 5.5)),
        ("4 ventilatoare 1,5 kW", lambda c: n_sum([p for p in pl(c) if p.get("P_kW") == 1.5]) == 4)],
    5: [("TG din PT 250", lambda c: I(c).get("pt_Sn_kVA") == 250),
        ("3 pompe 7,5 kW", lambda c: n_sum([p for p in pl(c) if p.get("P_kW") == 7.5]) == 3),
        ("nu întreabă mono/tri (sursa e PT)", lambda c: "monofaz" not in Q(c))],
    7: [("300 kW pe PT 250 kVA semnalat", lambda c: "250" in Q(c) or "V62" in coduri(c))],
    15: [("TD-A → TE-1, TE-2", lambda c: any(len(p.get("copii") or []) == 2 for p in gaseste(pl(c, False), "td-a"))),
         ("TE-1 cu motoarele", lambda c: any(p.get("copii") for p in gaseste(pl(c), "te-1"))),
         ("TD-B cu compresor + prize", lambda c: any(len(p.get("copii") or []) >= 2 for p in gaseste(pl(c, False), "td-b")))],
    16: [("TD-Hala1 → TE-Linie1 → 3 motoare", lambda c: any(any(n_sum(k.get("copii") or []) == 3 for k in p.get("copii") or [])
                                                              for p in gaseste(pl(c, False), "hala1")))],
    17: [("PT 2 × 1600", lambda c: I(c).get("tip_schema") == "pt" and I(c).get("n_trafo") == 2 and I(c).get("Sn_kVA") == 1600),
         ("cupla NO", lambda c: I(c).get("cupla") == "deschisa"),
         ("plecări pe semibare", lambda c: len([p for p in pl(c) if p.get("sectie")]) >= 4)],
    18: [("PT 10 kV", lambda c: I(c).get("tip_schema") == "pt" and I(c).get("U_MT_kV") == 10),
         ("ACB 1600 = general, nu plecare", lambda c: I(c).get("In_Q_JT_A") == 1600 and not gaseste(pl(c), "acb")),
         ("6 × 250 A", lambda c: len([p for p in pl(c) if p.get("In_A") == 250]) == 6),
         ("celule 2L + M + T cu întreruptor", lambda c: len(I(c).get("celule_mt") or []) == 4 and I(c).get("celula_trafo") == "intreruptor")],
    22: [("PT 6 kV", lambda c: I(c).get("U_MT_kV") == 6),
         ("ACB 3200 = general, nu plecare", lambda c: I(c).get("In_Q_JT_A") == 3200 and not gaseste(pl(c), "acb")),
         ("4 × 630 A", lambda c: len([p for p in pl(c) if p.get("In_A") == 630]) == 4)],
    25: [("2 cabluri Al 240 în paralel impuse", lambda c: (I(c).get("cablu") or {}).get("S_fortat") == 240 and
          2 in ((I(c).get("cablu") or {}).get("n_paralel"), (I(c).get("cablu") or {}).get("n_fortat"))),
         ("fără V02/V03 BLOCANT", lambda c: not ({"V02", "V03"} & coduri(c, "BLOCANT")))],
    26: [("pompa: cablu 4 mm², 80 m", lambda c: any(p.get("L_m") == 80 for p in gaseste(pl(c), "pomp"))),
         ("iluminat: 2,5 mm², 30 m", lambda c: any(p.get("L_m") == 30 for p in gaseste(pl(c), "ilumin"))),
         ("prize: puterea întrebată", lambda c: "priz" in Q(c))],
    27: [("TG (nu CEF) cu compensare 250 kvar", lambda c: I(c).get("tip_schema") == "tablou" and I(c).get("compensare_kvar") == 250),
         ("TD1 400 A + TD2 315 A", lambda c: sorted(p.get("In_A") or 0 for p in pl(c)) == [315, 400])],
    28: [("nu CEF / fără refuz „invertoare”", lambda c: I(c).get("tip_schema") != "cef"),
         ("compensarea calculată sau întrebată", lambda c: "kvar" in Q(c) or "compens" in Q(c) or bool(I(c).get("compensare_kvar")))],
    29: [("2 × 10 HP = 7,46 kW", lambda c: len([p for p in pl(c) if apx(p.get("P_kW"), 7.46, 0.01)]) == 2),
         ("25 HP Y/Δ", lambda c: any(apx(p.get("P_kW"), 18.64, 0.01) and p.get("pornire") == "stea_triunghi" for p in pl(c))),
         ("macara 2 × 5,5", lambda c: n_sum([p for p in pl(c) if p.get("P_kW") == 5.5]) == 2)],
    30: [("TG din PT 630", lambda c: I(c).get("pt_Sn_kVA") == 630 and gen(c)),
         ("8 plecări, fără fantomă", lambda c: n_sum(pl(c)) == 8 and not gaseste(pl(c), "aliment"))],
    32: [("pompă, ventilator, iluminat, prize", lambda c: len(pl(c)) >= 4 and gaseste(pl(c), "priz")),
         ("prize 4 × 16 A", lambda c: n_sum([p for p in gaseste(pl(c), "priz") if p.get("In_A") == 16]) == 4),
         ("Q1 nu e 16 A", lambda c: I(c).get("In_Q1_A") != 16)],
}, "locuinte": {
    7: [("fără P aprobată inventată (1,5 kW)", lambda c: pa(c) is None or pa(c) >= 20),
        ("puterea / rețeaua întrebate", lambda c: "putere" in Q(c) or "trifaz" in Q(c)),
        ("branșament nou (nu existent)", lambda c: (I(c).get("alimentare") or {}).get("tip") != "bransament_existent")],
    17: [("tri 20 kW", lambda c: I(c).get("retea") == "tri" and pa(c) == 20),
         ("plită 7,4 3F", lambda c: any(x.get("P_kW") == 7.4 and x.get("faza") == "3F" for x in rec(c, "plita"))),
         ("PC 10 kW 3F", lambda c: any(x.get("P_kW") == 10 and x.get("faza") == "3F" for x in rec(c, "pompa_caldura"))),
         ("cuptor, boiler, AC cu P din tabel", lambda c: any(x.get("P_kW") == 3.6 for x in circ(c)) and
          any(x.get("P_kW") == 2.5 for x in rec(c, "aer_conditionat")))],
    19: [("tri 16 kW", lambda c: I(c).get("retea") == "tri" and pa(c) == 16),
         ("VE 22 kW", lambda c: any(x.get("P_kW") == 22 for x in rec(c, "vehicul_electric"))),
         ("VE 22 > Pa 16 semnalat", lambda c: "22" in Q(c))],
    46: [("TD anexă mono din TG casă, 30 m", lambda c: any(t.get("L_m") == 30 for t in I(c).get("tablouri_secundare") or [])),
         ("casa mono 9 kW", lambda c: I(c).get("retea") == "mono" and pa(c) == 9),
         ("cablul 3×6 pe TD (nu pe coloană)", lambda c: any((t.get("cablu") or {}).get("S_fortat") == 6
                                                           for t in I(c).get("tablouri_secundare") or []))],
    4: [("tri 25 kW, TT RA 6 Ω", lambda c: pa(c) == 25 and I(c).get("schema_pamant") == "TT" and I(c).get("RA_ohm") == 6),
        ("VE 11 kW, 35 m", lambda c: any(x.get("L_m") == 35 for x in rec(c, "vehicul_electric"))),
        ("ușa de garaj", lambda c: bool(rec(c, "poarta_automata")) or any("garaj" in x.get("nume", "").lower() and x is not None
                                                                           for x in circ(c) if x.get("receptor") != "vehicul_electric"))],
    6: [("tri 11 kW, fără I08", lambda c: I(c).get("retea") == "tri" and pa(c) == 11 and gen(c)),
        ("Ik 4,2 kA / Zs 0,45 Ω din ATR", lambda c: I(c).get("Ik3_OD_kA") == 4.2 and I(c).get("Zb_OD_ohm") == 0.45),
        ("coloana 28 m", lambda c: (I(c).get("alimentare") or {}).get("L_coloana_m") == 28)],
    22: [("prosumator tri 10 kW", lambda c: I(c).get("tip_schema") == "prosumator" and inv(c) == [(1, 10)] and I(c).get("retea") == "tri"),
         ("Pa consum 14 kW, Ik 6 kA", lambda c: pa(c) == 14 and I(c).get("Ik3_OD_kA") == 6),
         ("fără întrebări", lambda c: not c["r"].get("intrebari"))],
    37: [("organizare de șantier tri 15 kW (nu locuință)", lambda c: I(c).get("tip_schema") != "locuinta" and I(c).get("retea") == "tri"),
         ("tabloul de șantier (prize 3F + 1F)", lambda c: False)],
    41: [("tri 22 kW", lambda c: I(c).get("retea") == "tri" and pa(c) == 22),
         ("2 VE 11 kW", lambda c: len([x for x in rec(c, "vehicul_electric") if x.get("P_kW") == 11]) == 2),
         ("load management semnalat", lambda c: "load" in Q(c) or "gestiun" in Q(c))],
    45: [("TE etaj 20 m", lambda c: any(t.get("L_m") == 20 for t in I(c).get("tablouri_secundare") or [])),
         ("Pa 20 kW", lambda c: pa(c) == 20),
         ("circuitele TE (2 ilum, 4 prize, 2 AC)", lambda c: any(n_sum(t.get("circuite") or []) == 8 for t in I(c).get("tablouri_secundare") or []))],
    5: [("tri 20 kW TN-C-S", lambda c: I(c).get("retea") == "tri" and pa(c) == 20 and I(c).get("schema_pamant") == "TN-C-S"),
        ("PC 12 kW 3F", lambda c: any(x.get("P_kW") == 12 and x.get("faza") == "3F" for x in rec(c, "pompa_caldura"))),
        ("plită, cuptor, VE 11, 2 AC", lambda c: rec(c, "plita") and rec(c, "cuptor") and len(rec(c, "aer_conditionat")) == 2
         and any(x.get("P_kW") == 11 for x in rec(c, "vehicul_electric")))],
    30: [("mono 32 A", lambda c: I(c).get("retea") == "mono" and (I(c).get("alimentare") or {}).get("In_Q_bransament_A") == 32),
         ("iluminat, prize, boiler", lambda c: rec(c, "iluminat") and rec(c, "prize") and rec(c, "boiler"))],
    9: [("tri 15 kW TT", lambda c: I(c).get("retea") == "tri" and pa(c) == 15 and I(c).get("schema_pamant") == "TT"),
        ("fără întrebări", lambda c: not c["r"].get("intrebari"))],
    12: [("tri 22 kW TT RA 10", lambda c: I(c).get("retea") == "tri" and pa(c) == 22 and I(c).get("RA_ohm") == 10),
         ("set tipic", lambda c: len(circ(c)) >= 5)],
    18: [("mono 9 kW", lambda c: I(c).get("retea") == "mono" and pa(c) == 9),
         ("P și L din tabel", lambda c: sum(1 for x in circ(c) if "P_kW" in x and "L_m" in x) == 5),
         ("iluminat nedublat", lambda c: len(rec(c, "iluminat")) == 2)],
    21: [("mono 7 kW", lambda c: I(c).get("retea") == "mono" and pa(c) == 7),
         ("4 AC, 5 prize, 3 iluminat", lambda c: len(rec(c, "aer_conditionat")) == 4 and len(rec(c, "prize")) == 5
          and len(rec(c, "iluminat")) == 3),
         ("fără plită fantomă", lambda c: not rec(c, "plita"))],
    24: [("prosumator tri 30 kW", lambda c: inv(c) == [(1, 30)] and I(c).get("retea") == "tri"),
         ("Q 3 × 50 A citit", lambda c: I(c).get("In_Q_bransament_A") == 50),
         ("Pmax absorbită 30 kW păstrată", lambda c: pa(c) == 30)],
    27: [("tri 16 kW", lambda c: I(c).get("retea") == "tri" and pa(c) == 16),
         ("VE 7,4 kW monofazat", lambda c: any(x.get("P_kW") == 7.4 and x.get("faza") != "3F" for x in rec(c, "vehicul_electric"))),
         ("2 AC", lambda c: len(rec(c, "aer_conditionat")) == 2)],
    34: [("punte PE–N în TT: avertisment / întrebare", lambda c: "nul" in Q(c) or "pe-n" in Q(c) or "pen" in Q(c))],
    39: [("mono, Pa 10 kW", lambda c: I(c).get("retea") == "mono" and pa(c) == 10),
         ("PC 16 kW > Pa 10 kW semnalat", lambda c: "16" in Q(c))],
}}


def ruleaza(text, raspuns=None):
    r = interpretor.interpreteaza(text, raspuns_llm=raspuns) if raspuns is not None else interpretor.interpreteaza_local(text)
    c = {"r": r, "v": None}
    if r["actiune"] != "refuza" and r.get("intrare_fizica"):
        try:
            m, _ = constructor.genereaza(r["intrare_fizica"])
            c["v"] = validare.valideaza(m)
        except Exception as e:  # noqa: BLE001
            c["exc"] = repr(e)
    return c


def nota(c, ver):
    ok = []
    for desc, f in ver:
        try:
            ok.append(bool(f(c)))
        except Exception:  # noqa: BLE001
            ok.append(False)
    k = sum(ok)
    return ("corect" if k == len(ok) else "parțial" if k * 2 >= len(ok) else "greșit"), ok


def main(verbose=False):
    tot = {}
    rand = []
    for dom, L in selectie().items():
        for f in L:
            ver = V[dom][f["id"]]
            a, oka = nota(ruleaza(f["text"]), ver)
            cb = ruleaza(f["text"], SIM[dom][str(f["id"])])
            b, okb = nota(cb, ver)
            r2 = SIM2[dom][str(f["id"])]
            if r2 is not SIM[dom][str(f["id"])]:
                cb = ruleaza(f["text"], r2)
            b2, okb2 = nota(cb, ver)
            tot.setdefault(dom, {"inainte": [], "dupa": [], "dupa2": []})
            tot[dom]["inainte"].append((a, sum(oka), len(oka)))
            tot[dom]["dupa"].append((b, sum(okb), len(okb)))
            tot[dom]["dupa2"].append((b2, sum(okb2), len(okb2)))
            rand.append((dom, f["id"], a, b2, [d for (d, _), o in zip(ver, okb2) if not o], cb))
    pct = lambda x: f"{sum(1 for v, *_ in x if v == 'corect'):2d} C / {sum(1 for v, *_ in x if v == 'parțial'):2d} P / " \
                    f"{sum(1 for v, *_ in x if v == 'greșit'):2d} G · verificări {sum(k for _, k, _ in x)}/{sum(n for *_, n in x)}"
    print("SIMULARE — răspunsurile lui Claude sunt scrise în teste/r8/llm_simulat.json, nu obținute printr-un apel real.\n")
    print(f"{'domeniu':12s} | {'ÎNAINTE (reguli locale)':42s} | {'DUPĂ v1 (Claude simulat orb + fuziune)':42s} | DUPĂ v2 (prompt ajustat, neorb)")
    allA, allB, allC = [], [], []
    for dom, d in tot.items():
        print(f"{dom:12s} | {pct(d['inainte']):42s} | {pct(d['dupa']):42s} | {pct(d['dupa2'])}")
        allA += d["inainte"]; allB += d["dupa"]; allC += d["dupa2"]
    print(f"{'TOTAL':12s} | {pct(allA):42s} | {pct(allB):42s} | {pct(allC)}")
    print("\nRămase nerezolvate după fuziune:")
    for dom, i, a, b, lipsa, cb in rand:
        if lipsa:
            print(f"  {dom[:3]}-{i:<3d} {a:8s} → {b:8s} lipsă: {'; '.join(lipsa)}")
        if verbose and lipsa:
            print("     Q:", cb["r"].get("intrebari"), "| refuz:", cb["r"].get("refuz_motiv"), "| exc:", cb.get("exc"))
    return tot


if __name__ == "__main__":
    main("-v" in sys.argv)
