"""Preset-uri (modele implicite) pentru cele patru tipuri de scheme.
Utilizatorul le încarcă în formular și le modifică."""
import copy

# Câmpurile proiectului (beneficiar, titlu, adresă, ATR, nr. proiect, dată …) rămân goale până le completează utilizatorul:
# pe planșă un câmp lipsă apare gol, nu cu text de exemplu (SPEC G.5).
CARTUS_CEP = {
    "verificator": "", "referat": "",
    "beneficiar": "", "titlu": "", "adresa": "", "atr": "",
    "atestat_anre": "", "atestat_tip": "", "sef_proiect": "", "verificat": "", "aprobat": "",
    # datele firmei de proiectare NU au valori implicite: vin din profilul de firmă al utilizatorului (tab-ul Proiect)
    "proiectant": "", "adresa_proiectant": "",
    "reg": "",
    "denumire1": "SCHEMA ELECTRICĂ MONOFILARĂ", "denumire2": "",
    "proiectat": "", "desenat": "", "nr_pr": "",
    "faza": "PT", "plansa": "E01", "rev": "0", "scara": "-", "data": "",
}

def _cartus(**kw):
    k = copy.deepcopy(CARTUS_CEP); k.update(kw); return k

# ------------------------------------------------------------------ 1. BMPTi-250 (ST 4-JT DEER, Anexa 3)
BMPTI = {
    "format": "A3",
    "cartus": _cartus(denumire2="BMPTi-250 — BLOC DE MĂSURĂ ȘI PROTECȚIE TRIFAZAT"),
    "carcasa": {"titlu": "BMPTi-250", "sub": "carcasă PAFS · IP54 · IK10 · cl. II · pe soclu PAFS"},
    "intrari": [{
        "sursa": {"titlu": "RED 0,4 kV", "sub": "rețea electrică de distribuție JT — PT / LEA / LES"},
        "cablu": {"ref": "C1", "cond": "3 + PEN", "text": "racord OD"},
        "aparate": [
            {"tip": "nod", "ref": "", "laterale": [{"tip": "bareta_nul"}]},
            {"tip": "sep_fuzibil", "ref": "SF", "spec": ["3 × 250 A gG"], "buc": 1,
             "lista": ["Separator tripolar cu siguranțe fuzibile NH2, 250 A, 400 V, Icu ≥ 50 kA", "fuzibile gG 250 A · separare vizibilă · sigilabil"]},
            {"tip": "tc", "ref": "TC", "spec": ["3 × 250/5 A", "cl. 0,5S"], "buc": 3,
             "lista": ["Transformator de curent JT 250/5 A, cl. 0,5S, 5 VA, FS 5 (ST 24-JT)", "capac sigilabil pe bornele secundare · circuit TC → K → contor: CYEAbY-F 2×1,5 mm²"],
             "laterale": [
                 # circuitul de curent: TC → K → P
                 {"tip": "cleme", "ref": "K", "lista": ["Șir de cleme cu bloc de șuntare pe circuitul secundar de curent", "capac transparent sigilabil"]},
                 # circuitul de tensiune: derivație din bare, în amonte de TC → F → a doua intrare a contorului P
                 {"tip": "fuzibil", "ref": "F", "spec": ["3 × 2 A gG"], "intrare_contor": "tensiune", "sursa_legatura": "amonte",
                  "lista": ["Bloc siguranțe fuzibile circuit tensiune contor 3 × 2 A gG, capace cu dublă sigilare", "bare 230 V → F → contor: CYEAbY-F 1×1,5 mm² / fază"]},
                 {"tip": "contor", "ref": "P", "eticheta": "kWh · kVArh", "spec": ["3 × 230/400 V · 5 A", "semidirect · telecitire"],
                  "lista": ["Contor electronic trifazat energie activă + reactivă, 3 × 230/400 V, 5(6) A, cl. 0,5S / 2", "conectare semidirectă · curbă de sarcină · telecitire · circuit tensiune prin F 3 × 2 A gG · furnizat și sigilat de OD"]}]},
            {"tip": "mccb", "ref": "Q", "spec": ["4P · 250 A", "Ir = 0,8…1 In"], "bd": True,
             "lista": ["Întreruptor automat de branșament MCCB 4P, In 250 A, 400 V, Icu ≥ 36 kA", "declanșator reglabil Ir = 0,8…1 In · bobină de declanșare BD · Ir reglat la Pa din ATR · sigilat"],
             "laterale": [{"tip": "cutie", "ref": "", "eticheta": "DPST", "spec": ["U> 50 Hz · Test"], "legatura": "comanda",
                           "lista": ["Dispozitiv de protecție la supratensiuni de frecvență industrială, trifazat", "separat sau înglobat în Q · buton Test · comandă BD"]}]},
            {"tip": "rccb", "ref": "RCCB", "spec": ["4P · 250 A", "IΔn 300 mA · S"],
             "lista": ["Întreruptor automat diferențial 4P, 250 A, IΔn 300 mA, tip S", "fără protecție la supracurenți"]},
        ]}],
    "bara": {"afisare": False},
    "plecari": [{"aparate": [], "cablu": {"ref": "C2", "cond": "3 + N + PE", "text": "coloană"},
                 "sarcina": {"titlu": "TE cons. trif.", "sub": "tablou electric al consumatorului · Pa cf. ATR"}}],
    "lista_pe": ["Baretă de nul · piesă de separație · priză de pământ locală", "electrozi OL-Zn Ø 60 mm × 3 m + platbandă OL-Zn 40×4 mm · Rp ≤ 4 Ω"],
    "abrevieri": ["RED rețea electrică de distribuție · BN baretă de nul · SF separator cu fuzibil", "TC transformator de curent · K șir de cleme cu bloc de șuntare · Q întreruptor automat",
                  "BD bobină de declanșare · DPST protecție supratensiune frecvență industrială", "RCCB întreruptor diferențial · PS piesă de separație · PPL priză de pământ locală"],
    "note": [
        "1. Schemă electrică monofilară de principiu. Echiparea BMPTi-250 corespunde variantei 4 din ST 4-JT „Bloc de măsură și protecție pentru branșament electric trifazat”, Ed. U1 Rev. 3/2024 (DEER), Anexa 3.",
        "2. Măsurare semidirectă 100 ÷ 250 A. Circuitele TC → K → contor și bare → F → contor se execută în cablu armat CYEAbY-F, cu capete etanșate; grupul de măsură se sigilează de OD.",
        "3. Q se reglează la curentul corespunzător puterii aprobate (Pa) din ATR și se sigilează. DPST comandă declanșarea Q prin BD la supratensiune de frecvență industrială.",
        "4. Schemă de legare la pământ TN-C-S: PEN se separă în N + PE pe BN; PE se leagă prin PS la PPL, Rp ≤ 4 Ω. Secțiunile și lungimile C1, C2 sunt orientative; se definitivează la PT + DDE.",
        "5. Referințe: SR HD 60364, I7-2011, NTE 007/08/00, SR EN 61439-1, SR EN 61869-2, SR EN 62053-22, SR EN 60947-2/-3, ST 4-JT și ST 24-JT (DEER), Ord. ANRE 59/2013."],
}

# ------------------------------------------------------------------ 1b. BMPTd-100 (măsură directă)
BMPTD = copy.deepcopy(BMPTI)
BMPTD["cartus"]["denumire2"] = "BMPTd-100 — BLOC DE MĂSURĂ ȘI PROTECȚIE TRIFAZAT"
BMPTD["carcasa"]["titlu"] = "BMPTd-100"
BMPTD["intrari"][0]["aparate"] = [
    {"tip": "nod", "ref": "", "laterale": [{"tip": "bareta_nul"}]},
    {"tip": "sep_fuzibil", "ref": "SF", "spec": ["3 × 100 A gG"], "lista": ["Separator tripolar cu siguranțe fuzibile NH00, 100 A, 400 V", "fuzibile gG 100 A · separare vizibilă · sigilabil"]},
    {"tip": "contor_direct", "ref": "P", "spec": ["3 × 230/400 V", "direct · furnizat de OD"], "lista": ["Contor electronic trifazat energie activă + reactivă, 3 × 230/400 V", "conectare directă · telecitire · furnizat și montat de OD"]},
    {"tip": "mccb", "ref": "Q", "spec": ["4P · 100 A", "Ir = 0,8…1 In"], "bd": True, "lista": ["Întreruptor automat de branșament MCCB 4P, In 100 A, 400 V, Icu ≥ 25 kA", "declanșator reglabil · bobină de declanșare BD · Ir reglat la Pa din ATR · sigilat"],
     "laterale": [{"tip": "cutie", "eticheta": "DPST", "spec": ["U> 50 Hz · Test"], "legatura": "comanda", "lista": ["Dispozitiv de protecție la supratensiuni de frecvență industrială, trifazat", "separat sau înglobat în Q · comandă BD"]}]},
    {"tip": "rccb", "ref": "RCCB", "spec": ["4P · 100 A", "IΔn 300 mA · S"], "lista": ["Întreruptor automat diferențial 4P, 100 A, IΔn 300 mA, tip S", "fără protecție la supracurenți"]},
]
BMPTD["note"][0] = "1. Schemă electrică monofilară de principiu. Echiparea BMPTd-100 corespunde variantei 3 din ST 4-JT „Bloc de măsură și protecție pentru branșament electric trifazat”, Ed. U1 Rev. 3/2024 (DEER), Anexa 2."
BMPTD["note"][1] = "2. Măsurare directă 40 ÷ 100 A. Circuitele de măsură se execută în cablu armat CYEAbY-F; grupul de măsură se sigilează de OD."

# ------------------------------------------------------------------ 2. Tablou general JT cu plecări
def _plecare(ref, tip, In, sarcina, cablu, spec_extra=None, buc=1):
    return {"aparate": [{"tip": tip, "ref": ref, "spec": [f"3P · {In} A gG"] + (spec_extra or []), "buc": buc,
                         "lista": [f"Separator cu siguranțe fuzibile MPR {In} A gG, 3P" if tip == "sep_fuzibil" else f"Întreruptor automat {In} A, 3P/4P"]}],
            "cablu": {"ref": "", "cond": "3 + N + PE", "text": cablu}, "sarcina": sarcina}

TG = {
    "format": "A3",
    "cartus": _cartus(denumire2="TABLOU GENERAL DE DISTRIBUȚIE JT (TG)"),
    "carcasa": {"titlu": "TG", "sub": "dulap metalic IP54 · bare Cu 3P + N + PE"},
    "intrari": [{
        "sursa": {"titlu": "RED 0,4 kV", "sub": "racord + grup de măsură BMPT"},
        "cablu": {"ref": "C1", "cond": "3 + N + PE", "text": "coloană"},
        "aparate": [
            {"tip": "mccb", "ref": "Q1", "spec": ["4P · 250 A", "Ir ≈ 235 A · Icu 36 kA"],
             "lista": ["Întreruptor general compact MCCB 4P 250 A, Icu ≥ 36 kA, declanșator reglabil", "reglaj Ir cf. puterii aprobate prin ATR"]}]}],
    "bara": {"afisare": True, "eticheta": "Bare Cu 30×5 mm · 3P + N + PE · 250 A",
             "laterale": [{"tip": "spd", "ref": "F1", "spec": ["SPD T1+T2 · 4P", "Iimp 12,5 kA · Up ≤ 1,5 kV"], "lista": ["Descărcător SPD tip 1+2, 4P, Iimp 12,5 kA (10/350), Up ≤ 1,5 kV, cu siguranțe 63 A gG"]}]},
    "plecari": [
        dict(_plecare("Q2", "sep_fuzibil", 160, {"titlu": "TD-1", "sub": "tablou secundar"}, "AC2XABY 3×150+70 mm² Al"),
             copii=[_plecare("Q2.1", "mcb", 32, {"titlu": "Hală", "sub": ""}, "CYY-F 5×6 mm²"), _plecare("Q2.2", "mcb", 63, {"titlu": "Birouri", "sub": ""}, "CYY-F 5×16 mm²")]),
        _plecare("Q3", "sep_fuzibil", 63, {"titlu": "TD-2", "sub": "tablou secundar"}, "CYY-F 5×16 mm² Cu"),
        _plecare("Q4", "sep_fuzibil", 80, {"titlu": "TD-3", "sub": "tablou secundar"}, "AC2XABY 3×70+35 mm² Al"),
    ],
    "note": ["1. Schemă electrică monofilară de principiu a tabloului general. Reglajele protecțiilor și secțiunile finale se stabilesc la faza PT + DDE, cu verificarea selectivității.",
             "2. Schemă de legare la pământ TN-S în aval de TG; bara PE legată la priza de pământ, Rp ≤ 4 Ω (≤ 1 Ω dacă este comună cu IPT).",
             "3. Referințe: SR HD 60364, I7-2011, SR EN 61439-1/-2, SR EN 60947-2/-3, SR EN 61643-11."],
}

# ------------------------------------------------------------------ 3. CEF fotovoltaic + BESS
def _inv(n, kw, strings, mod):
    """o intrare CEF: câmp PV → CC-DC (gPV, separator c.c., SPD c.c.) → invertor — toate în afara TGD-CF — → cablu c.a. → Q în TGD-CF"""
    return {"sursa": {"titlu": f"CÂMP PV {n}", "sub": f"{strings} stringuri × {mod} module"},
            "cablu": {"ref": "", "cond": "2 × 6 mm² PV", "text": "c.c."},
            "cablu_ca": {"ref": "", "cond": "3 + N + PE", "text": "c.a."},
            "aparate": [
                {"tip": "string_pv", "ref": f"PV{n}", "eticheta": f"× {strings}", "spec": [f"{strings} × {mod} module"], "buc": strings * mod,
                 "lista": [f"Module fotovoltaice — {strings} stringuri × {mod} module", "cutie CC-DC cu siguranțe gPV, separator c.c. și SPD tip 2 c.c."]},
                {"tip": "gpv", "ref": f"F{n}.1", "spec": ["gPV · 1000 V c.c."], "buc": strings * 2,
                 "lista": ["Siguranțe fuzibile gPV 1000 V c.c. pe fiecare string (+ / −), în CC-DC"]},
                {"tip": "separator_cc", "ref": f"S{n}", "spec": ["c.c. · 1000 V"],
                 "lista": ["Separator de c.c. sub sarcină 1000 V, pe intrarea MPPT (CC-DC)"],
                 "laterale": [{"tip": "spd_cc", "ref": f"F{n}.2", "spec": ["SPD T2 c.c."], "lista": ["Descărcător SPD tip 2 c.c., Ucpv ≥ Uoc,max, în CC-DC"]}]},
                {"tip": "invertor", "ref": f"INV-{n}", "spec": [f"{kw} kW", "3 × 400 V"], "lista": [f"Invertor trifazat {kw} kW c.a., 3 × 400 V, 50 Hz, cu protecții integrate"]},
                {"tip": "mccb", "ref": f"Q{n}", "spec": [f"4P · {int(kw*1.6)} A"], "lista": [f"Întreruptor automat MCCB 4P {int(kw*1.6)} A pentru invertor INV-{n}"]},
            ]}

CEF = {
    "format": "A3",
    "cartus": _cartus(denumire2="CENTRALĂ ELECTRICĂ FOTOVOLTAICĂ + BESS"),
    "carcasa": {"titlu": "TGD-CF", "sub": "tablou general c.a. fotovoltaic · 3 × 400/230 V · 50 Hz"},
    "intrari": [_inv(1, 125, 13, 20), _inv(2, 125, 13, 20), _inv(3, 100, 7, 20),
                {"sursa": {"titlu": "BESS", "sub": "125 kW / 261 kWh · LiFePO₄"}, "cablu": {"ref": "", "cond": "c.c.", "text": ""},
                 "cablu_ca": {"ref": "", "cond": "3 + N + PE", "text": "c.a."},
                 "aparate": [{"tip": "baterie", "ref": "BAT", "spec": ["261 kWh"], "lista": ["Baterie LiFePO₄ 261 kWh cu BMS"]},
                             {"tip": "convertor_bess", "ref": "PCS", "spec": ["125 kW", "grid-forming"], "lista": ["Convertor bidirecțional 125 kW, grid-forming, 3 × 400 V"]},
                             {"tip": "mccb", "ref": "QB", "spec": ["4P · 250 A"], "lista": ["Întreruptor automat MCCB 4P 250 A"]}]}],
    "bara": {"afisare": True, "eticheta": "Bare Cu · 3P + N + PE · 1.000 A",
             "laterale": [{"tip": "spd", "ref": "F0", "spec": ["SPD T1+T2 · 4P"], "lista": ["Descărcător SPD tip 1+2, 4P, Iimp 12,5 kA"]}]},
    "plecari": [
        {"aparate": [{"tip": "mccb", "ref": "QG", "spec": ["4P · 630 A"], "lista": ["Întreruptor general MCCB 4P 630 A cu bobină de declanșare (protecție de interfață)"],
                      "laterale": [{"tip": "cutie", "eticheta": "PI", "spec": ["U / f · Ord. ANRE 228"], "legatura": "comanda", "lista": ["Protecție de interfață (anti-insularizare) cu declanșare pe bobina MX a QG"]}]},
                     {"tip": "tc", "ref": "TC", "spec": ["3 × 600/5 A", "cl. 0,5S"], "buc": 3, "lista": ["Transformatoare de curent 600/5 A, cl. 0,5S"],
                      "laterale": [{"tip": "contor", "ref": "P1", "eticheta": "kWh", "spec": ["bidirecțional", "telecitire"], "lista": ["Contor electronic trifazat bidirecțional, semidirect, cl. 0,5S, telecitire"]}]}],
         "cablu": {"ref": "C0", "cond": "3 + N + PE", "text": "PCC"},
         "sarcina": {"titlu": "PCC — RED 0,4 kV", "sub": "punct comun de cuplare / consumator"}}],
    "note": ["1. Schemă electrică monofilară de principiu. Repartizarea stringurilor pe intrările MPPT este orientativă și se definitivează la faza PT, cu verificarea tensiunilor la Tmin / Tmax.",
             "2. Protecții: siguranțe gPV și SPD tip II pe c.c.; întreruptoare automate și SPD T1+T2 pe c.a.; protecție de interfață cf. Ord. ANRE 228/2018; instalație de legare la pământ comună, Rp ≤ 4 Ω.",
             "3. Secțiunile de cabluri sunt orientative; dimensionarea finală și reglajele protecțiilor se stabilesc la faza PT + DDE."],
}

# ------------------------------------------------------------------ 4. Post de transformare MT/JT
PT = {
    "format": "A3",
    "cartus": _cartus(denumire2="POST DE TRANSFORMARE 20/0,4 kV"),
    "carcasa": {"titlu": "PT 20/0,4 kV", "sub": "post de transformare în anvelopă de beton · celule MT + trafo + TGJT"},
    "intrari": [{
        "sursa": {"titlu": "LES 20 kV", "sub": "racord MT din rețeaua OD"},
        "cablu": {"ref": "C1", "cond": "3 × 1 × 150 mm² Al", "text": "A2XS(FL)2Y 12/20 kV"},
        "aparate": [
            {"tip": "sep_mt", "ref": "Q1", "spec": ["24 kV · 630 A", "celulă linie + CLP"], "lista": ["Celulă MT de linie, 24 kV, 630 A, separator de sarcină cu cuțit de legare la pământ, izolație SF6 / aer"],
             "laterale": [{"tip": "descarcator_mt", "ref": "FV", "spec": ["ZnO 24 kV"], "buc": 3, "lista": ["Descărcătoare cu ZnO 24 kV, 10 kA, pe intrarea de linie (trecere LEA–LES)"]}]},
            {"tip": "intreruptor_mt", "ref": "Q2", "spec": ["24 kV · 630 A", "protecție trafo"], "lista": ["Celulă MT de transformator cu întreruptor în vid 24 kV, 630 A, 16 kA, releu de protecție"],
             "laterale": [{"tip": "cutie", "eticheta": "F>", "spec": ["50/51 · 50N/51N"], "legatura": "comanda", "lista": ["Releu de protecție digital: maximală de curent 50/51, homopolară 50N/51N"]}]},
            {"tip": "trafo", "ref": "T1", "spec": ["630 kVA", "20/0,4 kV · Dyn5"], "neutru_pamant": True, "lista": ["Transformator de putere 630 kVA, 20 ± 2×2,5 % / 0,4 kV, Dyn5, uk 6 %, ulei / uscat"]},
            {"tip": "mccb", "ref": "Q3", "spec": ["4P · 1000 A"], "lista": ["Întreruptor general JT 4P 1000 A, Icu ≥ 50 kA, declanșator electronic"]},
        ]}],
    "bara": {"afisare": True, "forteaza": True, "eticheta": "TGJT · bare Cu · 3P + N + PE · 1000 A",
             "laterale": [{"tip": "spd", "ref": "F1", "spec": ["SPD T1+T2 · 4P"], "lista": ["Descărcător SPD tip 1+2, 4P"]}]},
    "plecari": [
        _plecare("Q4", "sep_fuzibil", 400, {"titlu": "TD-1", "sub": ""}, "3 × (ACYABY 4×240 mm² Al)"),
        _plecare("Q5", "sep_fuzibil", 250, {"titlu": "TD-2", "sub": ""}, "2 × (ACYABY 4×150 mm² Al)"),
        _plecare("Q6", "sep_fuzibil", 160, {"titlu": "TD-3", "sub": ""}, "ACYABY 4×185 mm² Al"),
    ],
    "note": ["1. Schemă electrică monofilară de principiu. Tipul celulelor MT și al transformatorului se definitivează conform ATR și specificațiilor OD.",
             "2. Instalație de legare la pământ comună MT/JT, Rp ≤ 1 Ω; verificare la tensiunea de atingere conform STAS 12604 / NTE 002.",
             "3. Referințe: NTE 001, NTE 007, PE 101, SR EN 62271-200, SR EN 60076, SR HD 60364."],
}

PRESETS = {
    "bmpt": ("Branșament BMPTi-250 (măsură semidirectă)", BMPTI),
    "bmptd": ("Branșament BMPTd-100 (măsură directă)", BMPTD),
    "tg": ("Tablou general JT cu plecări", TG),
    "cef": ("CEF fotovoltaic + BESS", CEF),
    "pt": ("Post de transformare MT/JT", PT),
}

def get(key): return copy.deepcopy(PRESETS[key][1])
