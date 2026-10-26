"""Testele textelor generate din parametri (SPEC §E.2, §E.3, §G.3, V80/V81).

Verifică: virgula zecimală, lipsa „.0”, „×” în loc de „x”, spațiul fără întrerupere număr–unitate, separatorul de mii
de la 10 000, și textele exacte ale șabloanelor E.3 pentru fiecare tip de aparat și cablu.
"""
import os
import re
import sys

import pytest

RADACINA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RADACINA)

from engine.calc import calculeaza  # noqa: E402
from engine.calc.texte import (fmt_ro, text_lista, text_desen, text_cablu, note_generate, verifica_aparat,  # noqa: E402
                               verifica_nota, NB, FIN)


def s(t):
    """Spațiile fără întrerupere (SPEC §E.2) devin spații obișnuite, pentru lizibilitatea așteptărilor."""
    return re.sub(r"[  ]", " ", t)


# ------------------------------------------------------------------------------------------------------------
# E.2 fmt_ro
# ------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("x, z, asteptat", [
    (250.0, 2, "250"), (0.95, 2, "0,95"), (1.29, 2, "1,29"), (106.25, 2, "106,25"), (2500, 0, "2500"),
    (9999, 0, "9999"), (1600.0, 1, "1600"), (0.4, 1, "0,4"), (1.0, 2, "1"), (0.0, 2, "0"), (-0.27, 2, "−0,27"),
    (12500, 0, f"12{FIN}500"), (1234567.891, 1, f"1{FIN}234{FIN}567,9"), (24.056, 1, "24,1"), (2.649, 2, "2,65"),
    (603.24, 0, "603"), (0.005, 2, "0,01"), (35.0, 0, "35"),
])
def test_fmt_ro(x, z, asteptat):
    assert fmt_ro(x, z) == asteptat


def test_fmt_ro_fara_punct_si_fara_zero_final():
    for v in [0.5, 1.5, 2.5, 10.0, 16.0, 120.0, 0.85, 0.9, 1.1, 1.45, 43.48, 1123.7]:
        t = fmt_ro(v, 2)
        assert "." not in t and not t.endswith(",0") and not t.endswith(",00")


# ------------------------------------------------------------------------------------------------------------
# E.3 șabloane — câte un caz pentru fiecare tip
# ------------------------------------------------------------------------------------------------------------
SABLOANE = [
    ("MCB", {"poli": 4, "curba": "C", "In_A": 32, "Icn_kA": 6},
     "Întreruptor automat modular 4P, curba C, In 32 A", "Icn 6 kA, 400 V c.a., SR EN 60898-1", "4P · C32 · 6 kA"),
    ("MCB", {"poli": "1P+N", "curba": "B", "In_A": 16, "Icn_kA": 10},
     "Întreruptor automat modular 1P+N, curba B, In 16 A", "Icn 10 kA, 230 V c.a., SR EN 60898-1", "1P+N · B16 · 10 kA"),
    ("MCCB", {"poli": 4, "In_A": 125, "Ir_A": 106.25, "Icu_kA": 25},
     "Întreruptor automat compact MCCB 4P, In 125 A, declanșator termomagnetic",
     "Ir = 0,85·In = 106,25 A, Im = 10·In = 1250 A, Icu 25 kA, 400 V c.a., SR EN 60947-2",
     "4P · 125 A · Ir 106,25 A · 25 kA"),
    ("MCCB", {"poli": 4, "In_A": 250, "Ir_A": 250, "Icu_kA": 36, "bd": True},
     "Întreruptor automat compact MCCB 4P, In 250 A, declanșator termomagnetic",
     "Ir = 1·In = 250 A, Im = 10·In = 2500 A, Icu 36 kA, 400 V c.a., SR EN 60947-2, bobină de declanșare BD",
     "4P · 250 A · Ir 250 A · 36 kA"),
    ("MCCB", {"poli": 4, "In_A": 400, "Ir_A": 340, "Isd_A": 680, "tsd_s": 0.1, "Ii_A": 4800, "Icu_kA": 25},
     "Întreruptor automat MCCB 4P, In 400 A, declanșator electronic LSI",
     "Ir = 0,85·In = 340 A, Isd = 2·Ir = 680 A, tsd 0,1 s, Ii = 4800 A, Icu 25 kA",
     "4P · 400 A · Ir 340 A · Isd 680 A"),
    ("ACB", {"poli": 4, "In_A": 2500, "Ir_A": 2375, "Isd_A": 9500, "tsd_s": 0.1, "Ii_A": 30000, "Icu_kA": 42},
     "Întreruptor automat ACB 4P, In 2500 A, declanșator electronic LSI",
     "Ir = 0,95·In = 2375 A, Isd = 4·Ir = 9500 A, tsd 0,1 s, Ii = 30 000 A, Icu 42 kA",
     "4P · 2500 A · Ir 2375 A · Isd 9500 A"),
    ("separator_sigurante", {"poli": 3, "In_A": 160},
     "Separator 3P cu siguranțe fuzibile NH 00, 160 A gG",
     # v1.2: NH gG au Icu 120 kA (SR EN 60269-2), nu 50 kA (verificare independentă, minore)
     "400 V c.a., 120 kA, separare vizibilă, SR EN 60947-3 / SR EN 60269-2", "3 × 160 A gG"),
    ("SF", {"In_A": 250, "soclu_A": 250, "gabarit": "NH1"},
     "Separator tripolar cu siguranțe fuzibile NH1, soclu 250 A, fuzibil 250 A gG", "400 V, 50 kA, sigilabil (ST 4-JT)",
     "3 × 250 A gG"),
    ("RCCB", {"poli": 4, "In_A": 63, "IdN_mA": 300, "tip_ddr": "AC"},
     "Întreruptor diferențial 4P, In 63 A, IΔn 300 mA, tip AC", "Icn ≥ 6 kA, fără protecție la supracurenți",
     "4P · 63 A · IΔn 300 mA AC"),
    ("RCCB", {"poli": 4, "In_A": 125, "IdN_mA": 300, "tip_ddr": "A", "selectiv": True},
     "Întreruptor diferențial 4P, In 125 A, IΔn 300 mA, tip A, S", "Icn ≥ 6 kA, fără protecție la supracurenți",
     "4P · 125 A · IΔn 300 mA A S"),   # v1.2 (M11): marcajul S apare și pe desen
    ("RCBO", {"In_A": 25},
     "Întreruptor automat cu protecție diferențială 1P+N, curba C, In 25 A, IΔn 300 mA, tip AC", "Icn ≥ 6 kA (ST 3-JT)",
     "1P+N · C25 · 300 mA"),
    ("TC", {"primar_A": 150, "clasa": "0,5", "Sn_VA": 5},
     "Transformator de curent JT 150/5 A, cl. 0,5, 5 VA, Fs 5", "0,72 kV, capac sigilabil, SR EN 61869-2 — 3 buc.",
     "3 × 150/5 A · cl. 0,5"),
    ("contor", {"retea": "tri", "masura": "directa"},
     "Contor electronic trifazat de energie activă și reactivă, direct",
     "3 × 230/400 V, 5(100) A, telecitire, furnizat și sigilat de OD", "kWh · kVArh"),
    ("contor", {"retea": "tri", "masura": "semidirecta", "bidirectional": True},
     "Contor electronic trifazat de energie activă și reactivă, semidirect, bidirecțional",
     "3 × 230/400 V, 5 A, telecitire, furnizat și sigilat de OD", "kWh · kVArh"),
    ("DPST", {}, "Dispozitiv de protecție la supratensiuni de frecvență industrială, trifazat",
     "Uf = 270 ± 10 V, t = 0,13…0,2 s, comandă BD pe Q", "DPST · U> 50 Hz"),
    ("SPD_ca", {"tip": "T1+T2", "poli": 4, "In_amonte_A": 125}, "Descărcător SPD tip T1+T2, 4P",
     "Iimp 12,5 kA/pol (10/350), Up ≤ 1,5 kV, protecție amonte 125 A gG", "SPD T1+T2 · 4P"),
    ("SPD_ca", {"tip": "T2", "poli": 4, "In_amonte_A": 63}, "Descărcător SPD tip T2, 4P",
     "In 20 kA (8/20), Up ≤ 1,5 kV, protecție amonte 63 A gG", "SPD T2 · 4P"),
    ("SPD_cc", {"Ucpv_V": 1100}, "Descărcător SPD c.c. tip 2, Ucpv 1100 V", "In 20 kA (8/20), SR EN 61643-31",
     "SPD c.c. · 1100 V"),
    ("gPV", {"In_A": 25, "U_V": 1100, "n": 6}, "Siguranță fuzibilă gPV 25 A, 10×38 mm, 1100 V c.c.",
     "SR EN 60269-6 — 6 buc. (+ și −)", "gPV 25 A"),
    ("cablu", {"material": "Al", "izolatie": "PVC", "metoda": "D1", "n_paralel": 2, "S_faza_mm2": 120,
               "S_N_mm2": 120, "S_PE_mm2": 35, "PE": "separat", "L_m": 80, "Iz_corectat_A": 255.0, "k_total": 0.85,
               "dU_ramura_pct": 1.2934},
     "Cablu 2 × (ACYABY 4×120 mm² + FY 1×35 mm² (PE)) Al, în paralel 2×",
     "0,6/1 kV, L ≈ 80 m, Iz' = 255 A (metoda D1, k = 0,85), ΔU = 1,29 %",
     "2 × (ACYABY 4×120 mm² + FY 1×35 mm² (PE)) · L ≈ 80 m"),
    ("PE", {"S_PE_mm2": 35, "ref": "C2", "L_m": 80}, "Conductor de protecție FY 1×35 mm² Cu, galben-verde",
     "pozat lângă cablul C2, L ≈ 80 m", None),
    ("trafo", {"Sn_kVA": 630}, "Transformator de putere 630 kVA, 20 ± 2×2,5 % / 0,4 kV, Dyn5",
     "uk 4 %, Pk ≤ 4600 W, P0 ≤ 540 W (Reg. UE 548/2014 Tier 2), ulei", "630 kVA · 20/0,4 kV · Dyn5"),
    ("celula_sigurante", {"In_A": 6.3}, "Celulă MT de transformator cu separator de sarcină și siguranțe MT 6,3 A",
     "24 kV, SR EN 62271-105, CLP", "24 kV · SF 6,3 A"),
    ("celula_intreruptor", {"raport": "100/1 A"}, "Celulă MT de transformator cu întreruptor în vid 24 kV, 630 A, 16 kA",
     "releu 50/51, 50N/51N, TC MT 100/1 A", "24 kV · Q · F>"),
    ("invertor", {"Pn_kW": 110, "Iac_max_A": 174.65, "certificare": "RfG"},
     "Invertor trifazat 110 kW c.a., 3 × 400 V, 50 Hz", "Iac,max 174,65 A, PI integrată, certificat conform RfG",
     "110 kW · 3 × 400 V"),
    ("PCS", {"Pn_kW": 500, "Iac_max_A": 793.86}, "Convertor bidirecțional BESS 500 kW",
     "Iac,max 793,86 A, grid-forming/following", "500 kW"),
    ("baterie", {"kWh": 1000}, "Baterie LiFePO₄ 1000 kWh cu BMS", "—", "1000 kWh"),
    ("ATS", {"In_A": 160}, "Comutator automat de sursă (ATS) 4P, 160 A, AC-33B",
     "interblocaj mecanic + electric, SR EN 60947-6-1", "ATS 4P · 160 A"),
    ("GE", {"Sn_kVA": 100, "xd_pct": 12, "In_G_A": 144.34}, "Grup electrogen 100 kVA, 3 × 400/230 V",
     "x\"d 12 %, In 144,34 A", "GE 100 kVA"),
    ("bare", {"In_bara_A": 1000, "Ik3_kA": 23.69}, "Sistem de bare Cu 3P+N+PE, 1000 A", "Icw ≥ 23,69 kA/1 s", "1000 A"),
]


@pytest.mark.parametrize("tip, par, den, car, desen", SABLOANE, ids=[f"{x[0]}-{i}" for i, x in enumerate(SABLOANE)])
def test_sabloane_E3(tip, par, den, car, desen):
    d, c = text_lista(tip, par)
    assert s(d) == den
    assert s(c) == car
    randuri = text_desen(tip, par)
    assert len(randuri) <= 3
    if desen is None:
        assert randuri == []
    else:
        assert s(" · ".join(randuri)) == desen
    for t in [d, c] + randuri:
        assert not re.search(r"\d\.\d", t), f"punct zecimal în „{t}”"
        assert not re.search(r"\d x \d|\dx\d", t), f"„x” în loc de „×” în „{t}”"
        assert not re.search(r",0\b(?![,\d])", t.replace("0,0", "")), f"„,0” final în „{t}”"


def test_unitate_separata_prin_spatiu_fara_intrerupere():
    d, c = text_lista("MCB", {"poli": 4, "curba": "C", "In_A": 32, "Icn_kA": 6})
    assert f"32{NB}A" in d and f"6{NB}kA" in c
    assert f"12{FIN}500" in text_lista("ACB", {"In_A": 2500, "Ir_A": 2500, "Ii_A": 12500, "Icu_kA": 50})[1]


@pytest.mark.parametrize("args, asteptat", [
    (("Cu", "PVC", "D1", 1, 6.0, 6.0, 6.0, "cablu", "tri"), "CYABY 5×6 mm²"),
    (("Cu", "PVC", "D1", 1, 6.0, 6.0, 6.0, "cablu", "mono"), "CYABY 3×6 mm²"),
    (("Cu", "PVC", "C", 1, 2.5, 2.5, 2.5, "cablu", "tri"), "CYY-F 5×2,5 mm²"),
    (("Cu", "PVC", "C", 1, 4.0, 4.0, 4.0, "cablu", "mono"), "CYY-F 3×4 mm²"),
    (("Al", "PVC", "D1", 1, 25.0, 25.0, 10.0, "separat", "tri"), "ACYABY 4×25 mm² + FY 1×10 mm² (PE)"),
    (("Al", "PVC", "D1", 1, 185.0, 95.0, 50.0, "separat", "tri"), "ACYABY 3×185+95 mm² + FY 1×50 mm² (PE)"),
    (("Al", "XLPE", "D1", 4, 240.0, 240.0, 95.0, "separat", "tri"), "4 × (AC2XABY 4×240 mm² + FY 1×95 mm² (PE))"),
    (("Cu", "XLPE", "E", 3, 150.0, 150.0, 95.0, "separat", "tri"), "3 × (N2XY 4×150 mm² + FY 1×95 mm² (PE))"),
    (("Cu", "PVC", "E", 1, 95.0, 95.0, 50.0, "separat", "tri"), "CYY-F 4×95 mm² + FY 1×50 mm² (PE)"),
])
def test_text_cablu(args, asteptat):
    assert s(text_cablu(*args)) == asteptat


def test_texte_cablu_din_motor_fara_punct_zecimal():
    r = calculeaza({"tip_schema": "tablou", "P_kW": 80, "plecari": [{"nume": "Iluminat", "P_kW": 2},
                                                                    {"nume": "Hală", "In_A": 125}]})
    for pl in r["rezultat"]["plecari"]:
        assert not re.search(r"\d\.\d", pl["cablu"]) and ".0" not in pl["cablu"]
    for v in r["verificari"] + r["info"]:
        m = re.sub(r"(art\.|tab\.|anexa)\s*[A-Z]?[\d.]+|B\.52\.\d+|Rev\. \d+/\d+", "", v["mesaj"])  # referințe normative
        assert ".0 " not in m and not re.search(r"\d\.\d", m), v["mesaj"]


# ------------------------------------------------------------------------------------------------------------
# G.3 note și V80 / V81
# ------------------------------------------------------------------------------------------------------------
def test_nota_bransament_X02():
    """SPEC §G.3 v1.1: Ir din model (Q_Ir_A), fără deducere din limitele blocului; „(Pa din ATR)” doar cu Ir prezent."""
    note = note_generate({"bloc": "BMPTi-250", "Q": {"tip": "MCCB", "In_A": 125, "Ir_A": 106.25}, "TC": 125})
    assert s(note[0]) == ("Măsurare semidirectă prin TC 3 × 125/5 A, cl. 0,5, 5 VA; Q MCCB 4P In 125 A reglat la "
                          "Ir = 106,25 A (Pa din ATR); BMPTi-250 conform ST 4-JT Ed. U1 Rev. 3/2024, varianta 4.")
    fara_ir = s(note_generate({"bloc": "BMPTi-250", "Q": {"tip": "MCCB", "In_A": 125}, "TC": 125})[0])
    assert "Ir" not in fara_ir and "Pa" not in fara_ir and "Q MCCB 4P In 125 A; BMPTi-250" in fara_ir
    cu_pa = s(note_generate({"bloc": "BMPTi-250", "Q": {"tip": "MCCB", "In_A": 125, "Ir_A": 106.25}, "TC": 125,
                             "Pa_kW": 62.4})[0])
    assert "reglat la Ir = 106,25 A (Pa = 62,4 kW din ATR)" in cu_pa
    mcb = s(note_generate({"bloc": "BMPTd-40", "Q": {"tip": "MCB", "In_A": 25}, "Pa_kW": 15})[0])
    assert mcb == ("Măsurare directă 5(100) A; Q MCB C25 (Pa = 15 kW din ATR); BMPTd-40 conform ST 4-JT Ed. U1 "
                   "Rev. 3/2024, varianta 2.")


def test_nota_bransament_fara_pa_cu_ib():
    """B.1.1: branșament dat prin Ib_A → Pa necunoscut, nota nu scrie „Pa = … kW”."""
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "Ib_A": 200, "L_coloana_m": 40})
    n = s(note_generate(r)[0])
    assert "Pa =" not in n and "reglat la Ir = 200 A (Pa din ATR)" in n


def test_note_din_rezultatul_motorului():
    r = calculeaza({"tip_schema": "bransament", "retea": "tri", "P_kW": 62.4, "L_coloana_m": 30})
    n = s(note_generate(r)[0])
    assert "3 × 125/5 A" in n and "Ir = 106,25 A" in n and "Pa = 62,4 kW" in n and "varianta 4" in n
    r = calculeaza({"tip_schema": "pt", "Sn_kVA": 630, "plecari": [{"nume": "TD-1", "In_A": 250}]})
    n = s(note_generate(r)[0])
    assert n.startswith("Trafo 630 kVA, In_T = 909,33 A; Q JT MCCB 1000 A, Ir = 950 A; Ik3max bara TGJT = 23,7 kA")
    r = calculeaza({"tip_schema": "cef", "kWp": 50, "invertoare": [{"n": 1, "Pn_kW": 50}],
                    "string": {"n_module": 18, "Uoc_V": 49.5}})
    n = s(note_generate(r)[0])
    assert "Σ Pn = 50 kW" in n and "categoria A RfG" in n and "Ord. ANRE 208/2018 și ATR" in n and "1011,3 V" in n


def test_V80_lista_diferita():
    _, _, v = verifica_aparat("Q", "mccb", {"poli": 4, "In_A": 500, "Ir_A": 475, "Icu_kA": 36},
                              "Întreruptor automat MCCB 4P, In 250 A, Ir = 0,8…1·In, Icu 36 kA")
    assert v and v["cod"] == "V80" and v["nivel"] == "BLOCANT" and "In 250 A" in v["mesaj"] and "In 500" in s(v["mesaj"])
    lista, desen, v = verifica_aparat("TC", "tc", {"primar_A": 600, "clasa": "0,5S", "Sn_VA": 5},
                                      None, "3 × 600/5 A · cl. 0,5S")
    assert v is None and s(desen) == "3 × 600/5 A · cl. 0,5S"


def test_V80_text_identic_nu_blocheaza():
    par = {"poli": 4, "In_A": 160, "Ir_A": 152, "Icu_kA": 25}
    d, c = text_lista("MCCB", par)
    assert verifica_aparat("Q1", "MCCB", par, f"{d}, {c}", " · ".join(text_desen("MCCB", par)))[2] is None


def test_V81_nota():
    model = "2. " + note_generate({"bloc": "BMPTi-250", "Q": {"tip": "MCCB", "In_A": 125, "Ir_A": 106.25}, "TC": 125})[0]
    v = verifica_nota(2, "2. Măsurare semidirectă 100 ÷ 250 A, TC 250/5 A.", model)
    assert v["cod"] == "V81" and v["obiect"] == "nota 2" and "250/5 A" in s(v["mesaj"]) and "125/5 A" in s(v["mesaj"])
    assert verifica_nota(2, model, model) is None
