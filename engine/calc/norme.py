"""norme.py — date normative pentru motorul de dimensionare JT (scheme monofilare).

Modul Python pur (doar biblioteca standard, fără dependențe), importabil oriunde:
    import sys; sys.path.insert(0, "/home/claude/spec"); import norme

Convenții
---------
* Unități SI explicite în numele constantelor: _A (amperi), _V, _KA, _KVA, _W, _M (metri), _KM, _OHM_KM, _PCT (procente).
* Secțiunile sunt în mm², ca float (1.5, 2.5) sau int (16 …). Cheile dicționarelor de secțiuni sunt float: 16.0 == 16 în Python,
  deci IZ[...][16] funcționează.
* Fiecare tabel are câmpul de sursă în comentariu sau în SURSE. Valorile care NU au putut fi verificate pe o sursă
  accesibilă sunt marcate „[NEVERIFICAT]” în comentariu ȘI listate în NEVERIFICAT (cheie → motiv), ca programatorul
  să le poată afișa în memoriul de calcul.
* Unde normativul lasă alegerea liberă, valoarea aleasă este marcată „DECIZIE” și justificată (vezi și SPEC_TEHNIC.md).
* Verificarea tehnică din 28.10.2026 (`teste/verificare_norme/raport.md`, 141 de rânduri) + răspunsurile proiectantului
  (`teste/verificare_norme/raspunsuri_proiectant.md`, 15 decizii): valorile confirmate pe o sursă publică poartă
  „[VERIFICAT: sursă]”, cele hotărâte de proiectant „[DECIZIE proiectant 28.10.2026, Îk]” (k = numărul întrebării),
  iar cele care nu se pot verifica public (standard cu plată) rămân în NEVERIFICAT, cu valoarea din practică.

Surse verificate (12.10.2026):
  [P]   Prysmian, „Electrical Information for Low Voltage Cables” (2024), tab. 3.5–3.10, 2.6–2.7 — reproduce
        IEC 60364-5-52:2009 tab. B.52.2–B.52.5, B.52.10–B.52.13, B.52.18, B.52.19
        https://asean.prysmian.com/sites/asean.prysmian.com/files/media/documents/241218%20-%20Prysmian%20Electrical%20Information%20for%20Low%20Voltage%20Cables.pdf
  [SE1] Schneider Electric, Electrical Installation Guide, „General method for cable sizing” — fig. G12–G18
        (= IEC 60364-5-52 tab. B.52.14–B.52.18) https://www.electrical-installation.org/enwiki/General_method_for_cable_sizing
  [SE2] idem, „Recommended simplified approach for cable sizing” — fig. G21 (= tab. C.52.1), G22, G23
        https://www.electrical-installation.org/enwiki/Recommended_simplified_approach_for_cable_sizing
  [SE3] idem, „Sizing of protective earthing conductor” — fig. G59, G60 (= SR HD 60364-5-54 tab. 54.2, A.54.2, A.54.3)
        https://www.electrical-installation.org/enwiki/Sizing_of_protective_earthing_conductor
  [SE4] Schneider Electric, „Complementary technical information 2018” — I²t de prearc gG (IEC 60269)
        https://www.tekdok.dk/flipbooks/CA908036E/CA908036E.pdf
  [SE5] idem, „Diversity factor” — fig. A13 (= IEC 61439-2 tab. 101) https://www.electrical-installation.org/enwiki/Diversity_factor
  [M]   Mersen, TM-104 „IEC 60269 gG & aM” — porți gG (25/80/250/800/1250 A), Inf/If
        https://www.mersen.com/sites/default/files/files_imported_ep/TM-104-Mersen-EduPack-IEC60269-gG-aM-Standard-Low-Voltage-Fuses.pdf
  [V]   DIN VDE 0100-600 Beiblatt, tab. NB.1 (extras, elektrofachkraft.de) — Ia gG la 0,4 s / 5 s, MCB B/C
        https://www.elektrofachkraft.de/files/userdata_EFK/content/grafiken/azubis-unter-strom-auf-den-punkt-gebracht/pdfs/vde-0100-600-4-schutz-durch-automatische-abschaltung.pdf
  [B]   Bayka, „Conductor resistance” (IEC 60228, clasa 2) https://www.bayka.de/en/service/technical-information/conductor-resistance
  [C]   Groupe Cahors, „Ecodesign directive” — Reg. (UE) 548/2014, pierderi Tier 1/Tier 2
        https://www.groupe-cahors.com/sites/default/files/doc-directive-ecodesign-_cahors-gb_0.pdf
  [D4]  DEER, ST 4-JT „BMPT” Ed. U1 Rev. 3/2024 https://www.distributie-energie.ro/wp-content/uploads/2024/11/ST-4-JT-BMPT-Ed.U1-Rev.3-2024.pdf
  [D3]  DEER, ST 3-JT „BMPM” Ed. U1 Rev. 3/2026 https://www.distributie-energie.ro/wp-content/uploads/2026/01/ST-3-JT-BMPM-Ed.U1-Rev.3-2026.pdf
  [I7]  Normativ I7-2011 (art. 3.3.2.11.1 PEN; art. 5.2.5 căderi de tensiune) + valori ΔU citate în
        https://mirceanetoiublog.blogspot.com/2015/03/caderea-de-tensiune-la-bransamentele.html (concordante cu SR HD 60364-5-52 anexa G)
  [TE]  Transelectrica, decizie implementare RfG (Reg. UE 2016/631) — prag tip B ≤ 1 MW pentru România
  [AG]  AGIR, Univers Ingineresc nr. 13/2023 — prosumator ≤ 400 kW/loc de consum (Ord. ANRE 95/2022)
Surse adăugate la verificarea din 28.10.2026 (detaliile și URL-urile în teste/verificare_norme/raport.md):
  [ST42] DEER, ST 42 JT/MT „Prize de pământ” Ed. U1 Rev. 0/2025 — §3.5, tab. 1, anexa 3 (electrod ø60 × 3,6 mm)
  [O228] Ord. ANRE 228/2018 (normă tehnică prosumatori, mod. Ord. ANRE 132/2020) — art. 12(3)–(5), art. 14, tab. 2P
  [O79]  Ord. ANRE 79/2016 — clasificarea modulelor generatoare RfG (A < 1 MW ≤ B < 5 MW ≤ C < 20 MW ≤ D)
  [ZA]   SR EN 60898-1 anexa ZA (clasa 3 de limitare a energiei), reprodusă în catalogul IPD p. 217
  [TR]   CLC/TR 50480:2011 (factorii de temperatură pentru Ik min: fază 1,20 / 1,28; PE în cablu 1,38 / 1,60)
  [HW1]  Huawei SUN2000-3…10KTL-M1, manualul utilizatorului (DDR ≥ 100 mA); [HW2] SUN2000-100KTL-M1 / -330KTL-H1 (fișe)
  [SMA]  SMA, TI „Criteria for selecting a RCD” (RCD-TI-en-45)
"""

VERSIUNE = "2026-10-28"   # v1.13: verificarea normelor + deciziile proiectantului (28.10.2026); v1.3: priza (§14a), DDR (§14b)

# =====================================================================================================
# 0. Constante de rețea și de calcul
# =====================================================================================================
U_N_V = 400.0          # tensiunea nominală între faze, rețea 3×400/230 V
U_0_V = 230.0          # tensiunea fază–neutru
F_HZ = 50.0
SQRT3 = 1.7320508075688772

# r7 (fotovoltaic P0-3): tensiunea JT ACTIVĂ a calculului — 400 V (implicit) sau 800 V c.a. (invertoare CEF de mare putere
# SG250HX, SUN2000-330KTL …, trafo 20/0,8 kV, 3 conductoare fără N). Se schimbă numai prin `tensiune_jt(u)` (contextvar:
# sigur la cereri paralele), citită de u_calcul, ΔU, Ik3/Ik1 și In_T. U_N_V / U_0_V rămân constantele rețelei publice.
import contextlib as _ctxlib, contextvars as _ctxvars
_U_JT = _ctxvars.ContextVar("U_JT_V", default=(U_N_V, U_0_V))
U_CA_INVERTOR_V = (400, 800)             # tensiunile c.a. de racord acceptate de motor pentru invertoarele CEF


def u_n():
    """tensiunea între faze a calculului JT în curs (400 V sau 800 V)"""
    return _U_JT.get()[0]


def u_0():
    """tensiunea fază–pământ a calculului JT în curs (230 V sau 462 V)"""
    return _U_JT.get()[1]


@_ctxlib.contextmanager
def tensiune_jt(un_v):
    """calculul din blocul `with` se face la tensiunea JT `un_v` (ex. 800 V c.a.)"""
    tok = _U_JT.set((float(un_v), float(un_v) / SQRT3))
    try:
        yield
    finally:
        _U_JT.reset(tok)

# SR EN 60909-0:2016 tab. 1, JT cu toleranță ±10 % (România: SR EN 50160 ±10 %)
C_MAX = 1.10           # pentru Ik max (alegerea Icu, verificarea termică)
C_MIN = 0.95           # pentru Ik min (verificarea deconectării)

# Rețeaua OD la punctul de delimitare — valori IMPLICITE (se înlocuiesc cu datele din ATR / aviz OD).
# Ik3max: echivalentul unui trafo OD ≤ 630 kVA, uk 4 %, la borne: 1,1·630/(√3·0,4·0,04) = 25,0 kA — majorant pentru Icu
# (la trafo OD 1000 / 1600 kVA rezultă 26,5 / 42 kA — ATR-ul are prioritate) [DECIZIE proiectant 28.10.2026, Î7].
# Zbuclă: urban (LES) 0,30 Ω = trafo OD 400 kVA + LES 3×150 Al 250 m + branșament 20 m ≈ 0,28 Ω (calculul
# verificatorului, raport #2) [DECIZIE proiectant 28.10.2026, Î2]; R/X = 2 ca până acum. Rural: LOCUINTA_ZB_OD_RURAL_OHM.
OD_IK3MAX_IMPLICIT_KA = 25.0
OD_RX_RAPORT = 0.1                         # R_Q = 0,1·X_Q (SR EN 60909-0, când nu se cunoaște)
OD_ZBUCLA_MODUL_IMPLICIT_OHM = 0.30
OD_ZBUCLA_IMPLICIT_OHM = (round(0.30 * 2 / 5 ** 0.5, 4), round(0.30 / 5 ** 0.5, 4))   # (0,2683 ; 0,1342) Ω → |Z| = 0,30 Ω
# Rețeaua MT pentru PT propriu
MT_UN_KV = 20.0
MT_SKQ_IMPLICIT_MVA = 500.0                # DEPENDENT DE OD [practică, raport #4]: majorant (Sk tipic 250…500 MVA la 20 kV); ATR prevalează
MT_RX_RAPORT = 0.1

# =====================================================================================================
# 1. Secțiuni standard și materiale
# =====================================================================================================
SECTIUNI_STD = [1.5, 2.5, 4.0, 6.0, 10.0, 16.0, 25.0, 35.0, 50.0, 70.0, 95.0, 120.0, 150.0, 185.0, 240.0, 300.0]

# DECIZIE: cabluri multipolare comerciale RO: Cu 1,5…240 mm², Al 16…240 mm² (Al < 16 → se trece pe Cu, vezi SPEC B.6).
SECTIUNI_MULTIPOLAR = {
    "Cu": [1.5, 2.5, 4.0, 6.0, 10.0, 16.0, 25.0, 35.0, 50.0, 70.0, 95.0, 120.0, 150.0, 185.0, 240.0],
    "Al": [16.0, 25.0, 35.0, 50.0, 70.0, 95.0, 120.0, 150.0, 185.0, 240.0],
}
S_MAX_MULTIPOLAR = 240.0
N_PARALEL_MAX_MULTIPOLAR = 4          # DECIZIE: peste 4 cabluri în paralel → BLOCANT (bare capsulate / alt punct de racord)

# Secțiuni minime (Cu) — SR HD 60364-5-52 tab. 52.2 (1,5 mm² circuite de forță/iluminat fixe) + DECIZIE
S_MIN_CU = {
    "iluminat": 1.5,
    "prize": 2.5,
    "forta": 2.5,
    "motor": 2.5,
    "invertor": 2.5,
    "tablou": 4.0,         # DECIZIE: coloane către tablouri
    "ingropat": 6.0,       # DECIZIE: orice cablu în pământ (D1/D2), rezistență mecanică — practică OD
}
S_MIN_AL = 16.0            # cerință din tema de proiectare: Al armat ≥ 16 mm²

# Combinații 3×S + N redus fabricate în RO (ACYAbY / AC2XAbY / CYAbY). Folosite NUMAI dacă armonica 3 ≤ 15 % declarată.
COMBINATII_N_REDUS = {25.0: 16.0, 35.0: 16.0, 50.0: 25.0, 70.0: 35.0, 95.0: 50.0, 120.0: 70.0, 150.0: 70.0, 185.0: 95.0, 240.0: 120.0}
# SR HD 60364-5-52 art. 524.2.3: reducere permisă doar dacă S > 16 Cu / S > 25 Al și N ≥ 16 Cu / N ≥ 25 Al.
N_REDUS_S_FAZA_MIN = {"Cu": 16.0, "Al": 25.0}   # strict mai mare decât
N_REDUS_S_N_MIN = {"Cu": 16.0, "Al": 25.0}      # mai mare sau egal

# PEN (I7-2011 art. 3.3.2.11.1; SR HD 60364-5-54 art. 543.4.1): ≥ 10 Cu / 16 Al, numai instalații fixe, niciodată în aval de DDR
S_MIN_PEN = {"Cu": 10.0, "Al": 16.0}
# PE separat (neîncorporat în cablu), SR HD 60364-5-54 art. 543.1.3 [SE3]
S_MIN_PE_SEPARAT = {"protejat_mecanic": 2.5, "neprotejat": 4.0}

# Denumiri RO de cabluri (material, izolație, armat) → tip. 0,6/1 kV. E2 (raportul verificatorului #9): notația după
# standardul de produs / ST 80-6 DEER — „Ab” = armătură din bandă de oțel, cu „b” mic: CYAbY, ACYAbY (și C2XAbY, AC2XAbY).
# Potrivirea textelor (DENUMIRE_CABLU, citirea secțiunii) se face fără diferență de majuscule.
TIP_CABLU = {
    ("Cu", "PVC", True): "CYAbY",
    ("Cu", "PVC", False): "CYY-F",
    ("Cu", "XLPE", True): "C2XAbY",    # [practică, raport #9] denumire din ofertele producătorilor RO; alternativ N2XBY
    ("Cu", "XLPE", False): "N2XY",
    ("Al", "PVC", True): "ACYAbY",
    ("Al", "PVC", False): "ACYY",      # [VERIFICAT: DEER ST 80-6 JT Ed. U1 Rev. 1/2025]
    ("Al", "XLPE", True): "AC2XAbY",
    ("Al", "XLPE", False): "NA2XY",
}
# r8b (industrial #25): denumirea impusă a cablului („2 × NA2XY 4x240”) → (material, izolație). Prefixul N/A al
# denumirilor DIN (NYY, NAYY, N2XY, NA2XY) și denumirile RO (CYY, ACYY, CYAbY, C2XAbY…); „2X” = XLPE, altfel PVC.
# Ordinea contează: denumirile mai lungi întâi (NA2XY înaintea N2XY).
DENUMIRE_CABLU = (
    ("NA2XSY", ("Al", "XLPE")), ("NA2XY", ("Al", "XLPE")), ("NA2XBY", ("Al", "XLPE")), ("N2XSY", ("Cu", "XLPE")),
    ("N2XBY", ("Cu", "XLPE")), ("N2XH", ("Cu", "XLPE")), ("N2XY", ("Cu", "XLPE")), ("NAYY", ("Al", "PVC")),
    ("NYY", ("Cu", "PVC")), ("AC2XABY", ("Al", "XLPE")), ("C2XABY", ("Cu", "XLPE")), ("AC2XY", ("Al", "XLPE")),
    ("C2XY", ("Cu", "XLPE")), ("ACYABY", ("Al", "PVC")), ("CYABY", ("Cu", "PVC")), ("ACYY", ("Al", "PVC")),
    ("CYY", ("Cu", "PVC")),
)


def material_izolatie_din_denumire(tip):
    """(material, izolatie) din denumirea comercială a cablului, sau None dacă denumirea nu e cunoscută."""
    t = str(tip or "").upper().replace(" ", "").replace("-F", "")
    for den, mi in DENUMIRE_CABLU:
        if t.startswith(den):
            return mi
    return None


TIP_CONDUCTOR_PE_SEPARAT = "FY"       # conductor Cu izolat PVC, galben-verde (ST 4-JT folosește FY pentru legături interne)

# Temperaturi conductor (SR HD 60364-5-52 tab. 52.1; SR HD 60364-4-43 tab. 43A)
THETA_MAX_C = {"PVC": 70.0, "XLPE": 90.0}       # regim permanent
THETA_SC_C = {"PVC": 160.0, "XLPE": 250.0}      # final la scurtcircuit (PVC ≤ 300 mm²)

# =====================================================================================================
# 2. Rezistențe și reactanțe
# =====================================================================================================
# IEC 60228, clasa 2, rezistența maximă în c.c. la 20 °C [Ω/km] — verificat [B]
R20_OHM_KM = {
    "Cu": {1.5: 12.1, 2.5: 7.41, 4.0: 4.61, 6.0: 3.08, 10.0: 1.83, 16.0: 1.15, 25.0: 0.727, 35.0: 0.524, 50.0: 0.387,
           70.0: 0.268, 95.0: 0.193, 120.0: 0.153, 150.0: 0.124, 185.0: 0.0991, 240.0: 0.0754, 300.0: 0.0601},
    "Al": {10.0: 3.08, 16.0: 1.91, 25.0: 1.20, 35.0: 0.868, 50.0: 0.641, 70.0: 0.443, 95.0: 0.320, 120.0: 0.253,
           150.0: 0.206, 185.0: 0.164, 240.0: 0.125, 300.0: 0.100},
}
# Rezistivitate la 20 °C [Ω·mm²/m] și coeficient de temperatură [1/K] (IEC 60028 Cu recopt; IEC 60889 Al)
RHO20 = {"Cu": 0.017241, "Al": 0.028264}
ALPHA = {"Cu": 0.00393, "Al": 0.00403}

def r_la_temperatura(r20, material, theta_c):
    """R(θ) = R20·[1 + α·(θ − 20)]"""
    return r20 * (1.0 + ALPHA[material] * (theta_c - 20.0))

# Rezistivități la temperatura maximă de regim (pentru ΔU), derivate cu formula de mai sus
RHO_70 = {m: RHO20[m] * (1 + ALPHA[m] * 50.0) for m in RHO20}   # Cu 0,02063 · Al 0,03396
RHO_90 = {m: RHO20[m] * (1 + ALPHA[m] * 70.0) for m in RHO20}   # Cu 0,02198 · Al 0,03624

# Factori de majorare a rezistenței pentru Ik1min [VERIFICAT: CLC/TR 50480:2011, raport #12]:
# * conductoarele de FAZĂ (active) — R20 adus la temperatura maximă de regim: PVC 70 °C → 1,20 ; XLPE 90 °C → 1,28;
# * conductorul PE în cablu — temperatura medie dintre regim și finalul scurtcircuitului: PVC (70+160)/2 = 115 °C →
#   1,38 ; XLPE (90+250)/2 = 170 °C → 1,60 (PE separat: valoarea PVC, ca până acum).
FACTOR_R_IK1MIN = {"PVC": 1.20, "XLPE": 1.28}
FACTOR_R_IK1MIN_PE = {"PVC": 1.38, "XLPE": 1.60}

# Reactanța de secvență pozitivă a cablurilor JT multipolare / monopolare în treflă [Ω/km per conductor]
# [VERIFICAT: Schneider EIG cap. G / SR EN 60909, raport #13] 0,08 mΩ/m pentru cablurile JT.
X_CABLU_OHM_KM = 0.08

# =====================================================================================================
# 3. Curenți admisibili Iz [A] — SR HD 60364-5-52:2011 = IEC 60364-5-52:2009
#    Condiții de referință: aer 30 °C, sol 20 °C, rezistivitate termică sol 2,5 K·m/W, un singur circuit.
#    Cheie: (material, izolatie, metoda, nr_conductoare_incarcate)
#      metoda "C"  = multipolar pe perete / pat neperforat           (tab. B.52.2–B.52.5, col. C)
#      metoda "D1" = multipolar în tub/conductă în pământ             (tab. B.52.2–B.52.5, col. D1)
#      metoda "D2" = multipolar direct în pământ (cu/fără armătură)   (tab. B.52.2–B.52.5, col. D2)
#      metoda "E"  = multipolar în aer liber / pat perforat / scară    (tab. B.52.10–B.52.13, col. E)
#      metoda "F_atingere" / "F_trefla" = monopolar 3 cond. încărcate (tab. B.52.10–B.52.13, col. F)
#    Sursa: [P] tab. 3.5 (C), 3.6 (D1), 3.7 (D2), 3.9 (E), 3.10 (F) — verificat, cu excepțiile marcate.
#    Al 16 mm²: [VERIFICAT: EIG Fig. G20, EUPEN tab. 4.2.2–4.2.5, raport_b3 #1–16]
# =====================================================================================================
_S = SECTIUNI_STD

def _t(valori, sectiuni=_S):
    return {s: v for s, v in zip(sectiuni, valori) if v is not None}

_AL_S = [16.0, 25.0, 35.0, 50.0, 70.0, 95.0, 120.0, 150.0, 185.0, 240.0, 300.0]

IZ = {
    # ---------------- 3 conductoare încărcate (trifazat) ----------------
    ("Cu", "PVC", "C", 3):   _t([17.5, 24, 32, 41, 57, 76, 96, 119, 144, 184, 223, 259, 299, 341, 403, 464]),
    ("Cu", "PVC", "D1", 3):  _t([18, 24, 30, 38, 50, 64, 82, 98, 116, 143, 169, 192, 217, 243, 280, 316]),
    ("Cu", "PVC", "D2", 3):  _t([19, 24, 33, 41, 54, 70, 92, 110, 130, 162, 193, 220, 246, 278, 320, 359]),
    ("Cu", "PVC", "E", 3):   _t([18.5, 25, 34, 43, 60, 80, 101, 126, 153, 196, 238, 276, 319, 364, 430, 497]),
    ("Cu", "XLPE", "C", 3):  _t([22, 30, 40, 52, 71, 96, 119, 147, 179, 229, 278, 322, 371, 424, 500, 576]),
    ("Cu", "XLPE", "D1", 3): _t([21, 28, 36, 44, 58, 75, 96, 115, 135, 167, 197, 223, 251, 281, 324, 365]),
    ("Cu", "XLPE", "D2", 3): _t([23, 30, 39, 49, 65, 84, 107, 129, 153, 188, 226, 257, 287, 324, 375, 419]),
    ("Cu", "XLPE", "E", 3):  _t([23, 32, 42, 54, 75, 100, 127, 158, 192, 246, 298, 346, 399, 456, 538, 621]),
    ("Al", "PVC", "C", 3):   _t([59, 73, 90, 110, 140, 170, 197, 227, 259, 305, 351], _AL_S),
    ("Al", "PVC", "D1", 3):  _t([50, 64, 77, 91, 112, 132, 150, 169, 190, 218, 247], _AL_S),
    ("Al", "PVC", "D2", 3):  _t([53, 69, 83, 99, 122, 148, 169, 189, 214, 250, 282], _AL_S),
    ("Al", "PVC", "E", 3):   _t([61, 78, 96, 117, 150, 183, 212, 245, 280, 330, 381], _AL_S),
    ("Al", "XLPE", "C", 3):  _t([76, 90, 112, 136, 174, 211, 245, 283, 323, 382, 440], _AL_S),
    ("Al", "XLPE", "D1", 3): _t([59, 75, 90, 106, 130, 154, 174, 197, 220, 253, 286], _AL_S),
    ("Al", "XLPE", "D2", 3): _t([64, 82, 98, 117, 144, 172, 197, 220, 250, 290, 326], _AL_S),
    ("Al", "XLPE", "E", 3):  _t([77, 97, 120, 146, 187, 227, 263, 304, 347, 409, 471], _AL_S),
    # ---------------- 2 conductoare încărcate (monofazat) ----------------
    ("Cu", "PVC", "C", 2):   _t([19.5, 27, 36, 46, 63, 85, 112, 138, 168, 213, 258, 299, 344, 392, 461, 530]),
    ("Cu", "PVC", "D1", 2):  _t([22, 29, 37, 46, 60, 78, 99, 119, 140, 173, 204, 231, 261, 292, 336, 379]),
    ("Cu", "PVC", "D2", 2):  _t([22, 28, 38, 48, 64, 83, 110, 132, 156, 192, 230, 261, 293, 331, 382, 427]),
    ("Cu", "PVC", "E", 2):   _t([22, 30, 40, 51, 70, 94, 119, 148, 180, 232, 282, 328, 379, 434, 514, 593]),
    ("Cu", "XLPE", "C", 2):  _t([24, 33, 45, 58, 80, 107, 138, 171, 209, 269, 328, 382, 441, 506, 599, 693]),
    ("Cu", "XLPE", "D1", 2): _t([25, 33, 43, 53, 71, 91, 116, 139, 164, 203, 239, 271, 306, 343, 395, 446]),
    ("Cu", "XLPE", "D2", 2): _t([27, 35, 46, 58, 77, 100, 129, 155, 183, 225, 270, 306, 343, 387, 448, 502]),
    ("Cu", "XLPE", "E", 2):  _t([26, 36, 49, 63, 86, 115, 149, 185, 225, 289, 352, 410, 473, 542, 641, 741]),
    ("Al", "PVC", "C", 2):   _t([66, 83, 103, 125, 160, 195, 226, 261, 298, 352, 406], _AL_S),
    ("Al", "PVC", "D1", 2):  _t([61, 77, 93, 109, 135, 159, 180, 204, 228, 262, 296], _AL_S),
    ("Al", "PVC", "D2", 2):  _t([63, 82, 98, 117, 145, 173, 200, 224, 255, 298, 336], _AL_S),
    ("Al", "PVC", "E", 2):   _t([73, 89, 111, 135, 173, 210, 244, 282, 322, 380, 439], _AL_S),
    ("Al", "XLPE", "C", 2):  _t([84, 101, 126, 154, 198, 241, 280, 324, 371, 439, 508], _AL_S),
    ("Al", "XLPE", "D1", 2): _t([71, 90, 108, 128, 158, 186, 211, 238, 267, 307, 346], _AL_S),
    ("Al", "XLPE", "D2", 2): _t([76, 98, 117, 139, 170, 204, 233, 261, 296, 343, 386], _AL_S),
    ("Al", "XLPE", "E", 2):  _t([91, 108, 135, 164, 211, 257, 300, 346, 397, 470, 543], _AL_S),
}
# Metoda F — cabluri MONOPOLARE, 3 conductoare încărcate, în aer liber, ref. 30 °C [P] tab. 3.10 (verificat)
_F_S = [25.0, 35.0, 50.0, 70.0, 95.0, 120.0, 150.0, 185.0, 240.0, 300.0]
IZ.update({
    ("Cu", "PVC", "F_atingere", 3):  _t([114, 143, 174, 225, 275, 321, 372, 427, 507, 587], _F_S),
    ("Al", "PVC", "F_atingere", 3):  _t([87, 109, 133, 173, 212, 247, 287, 330, 392, 455], _F_S),
    ("Cu", "XLPE", "F_atingere", 3): _t([141, 176, 216, 279, 342, 400, 464, 533, 634, 736], _F_S),
    ("Al", "XLPE", "F_atingere", 3): _t([107, 135, 165, 215, 264, 308, 358, 413, 492, 571], _F_S),
    ("Cu", "PVC", "F_trefla", 3):    _t([110, 137, 167, 216, 264, 308, 356, 409, 485, 561], _F_S),
    ("Al", "PVC", "F_trefla", 3):    _t([84, 105, 128, 166, 203, 237, 274, 315, 375, 434], _F_S),
    ("Cu", "XLPE", "F_trefla", 3):   _t([135, 169, 207, 268, 328, 383, 444, 510, 607, 703], _F_S),
    ("Al", "XLPE", "F_trefla", 3):   _t([103, 129, 159, 206, 253, 296, 343, 395, 471, 547], _F_S),
})

# v1.4 (§C.8, locuințe): metoda B2 = cablu multipolar în tub pe perete / îngropat în perete (tab. B.52.2–B.52.5,
# col. B2), numai Cu [VERIFICAT: IEC 60364-5-52 B.52.2–B.52.5 col. B2 — Schneider EIG Fig. G20, EUPEN tab. 4.2.2/4.2.3, raport_b3 #17]
IZ.update({
    ("Cu", "PVC", "B2", 2):  _t([16.5, 23, 30, 38, 52, 69, 90, 111, 133, 168, 201, 232, 258, 294, 344, 394]),
    ("Cu", "PVC", "B2", 3):  _t([15, 20, 27, 34, 46, 62, 80, 99, 118, 149, 179, 206, 225, 255, 297, 339]),
    ("Cu", "XLPE", "B2", 2): _t([22, 30, 40, 51, 69, 91, 119, 146, 175, 221, 265, 305, 334, 384, 459, 532]),
    ("Cu", "XLPE", "B2", 3): _t([19.5, 26, 35, 44, 60, 80, 105, 128, 154, 194, 233, 268, 300, 340, 398, 455]),
})

METODE_POZARE = {
    "B2": "multipolar în tub pe perete sau îngropat în perete",
    "C": "multipolar fixat pe perete / pat neperforat (aer)",
    "D1": "multipolar în tub sau canalizație în pământ",
    "D2": "multipolar direct în pământ",
    "E": "multipolar în aer liber, pe pat perforat sau scară de cabluri",
    "F_atingere": "monopolare în aer, alăturate în plan",
    "F_trefla": "monopolare în aer, în treflă",
}
METODE_IN_PAMANT = {"D1", "D2"}
# v1.2 R2 (N-M5): cabluri monopolare (metoda F) — secțiuni tabelate, număr maxim de sisteme în paralel pe fază și
# factorul de grupare pentru sisteme trifazate în treflă pe pat perforat, distanțate ≥ 2·De — B.52.21 treflă pat perforat
# 2·De, max. 3 sisteme/pat [VERIFICAT: EUPEN §4.4.3 p. 23, EIG Fig. G17 — raport_b3]
SECTIUNI_MONOPOLAR = [25.0, 35.0, 50.0, 70.0, 95.0, 120.0, 150.0, 185.0, 240.0, 300.0]
N_PARALEL_MAX_MONOPOLAR = 6
K_GRUP_F_DISTANTAT = {1: 1.00, 2: 0.97, 3: 0.96, 4: 0.93, 5: 0.89, 6: 0.89, 7: 0.86, 8: 0.86}

def iz_tabel(material, izolatie, metoda, n_incarcate, s):
    """Iz [A] din tabel sau None dacă nu e tabelat."""
    return IZ.get((material, izolatie, metoda, n_incarcate), {}).get(float(s))

# =====================================================================================================
# 4. Factori de corecție (SR HD 60364-5-52 anexa B) — verificat [SE1], [P]
# =====================================================================================================
# B.52.14 — temperatura aerului (metodele A–C, E, F), ref. 30 °C
K_TEMP_AER = {
    "PVC":  {10: 1.22, 15: 1.17, 20: 1.12, 25: 1.06, 30: 1.00, 35: 0.94, 40: 0.87, 45: 0.79, 50: 0.71, 55: 0.61, 60: 0.50},
    "XLPE": {10: 1.15, 15: 1.12, 20: 1.08, 25: 1.04, 30: 1.00, 35: 0.96, 40: 0.91, 45: 0.87, 50: 0.82, 55: 0.76, 60: 0.71,
             65: 0.65, 70: 0.58, 75: 0.50, 80: 0.41},
}
# B.52.15 — temperatura solului (metoda D), ref. 20 °C
K_TEMP_SOL = {
    "PVC":  {10: 1.10, 15: 1.05, 20: 1.00, 25: 0.95, 30: 0.89, 35: 0.84, 40: 0.77, 45: 0.71, 50: 0.63, 55: 0.55, 60: 0.45},
    "XLPE": {10: 1.07, 15: 1.04, 20: 1.00, 25: 0.96, 30: 0.93, 35: 0.89, 40: 0.85, 45: 0.80, 50: 0.76, 55: 0.71, 60: 0.65,
             65: 0.60, 70: 0.53, 75: 0.46, 80: 0.38},
}
# B.52.16 — rezistivitatea termică a solului [K·m/W], ref. 2,5
K_SOL = {
    "D1": {0.5: 1.28, 0.7: 1.20, 1.0: 1.18, 1.5: 1.10, 2.0: 1.05, 2.5: 1.00, 3.0: 0.96},
    "D2": {0.5: 1.88, 0.7: 1.62, 1.0: 1.50, 1.5: 1.28, 2.0: 1.12, 2.5: 1.00, 3.0: 0.90},
}
# B.52.17 — grupare în aer (circuite sau cabluri multipolare). Index = nr. circuite 1..9, 12, 16, 20.
# Rândurile 2–5 nu se mai reduc peste 9 circuite (nota tabelului) → se folosește valoarea de la 9.
_N_AER = [1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 16, 20]
K_GRUP_AER = {
    "strans": dict(zip(_N_AER, [1.00, 0.80, 0.70, 0.65, 0.60, 0.57, 0.54, 0.52, 0.50, 0.45, 0.41, 0.38])),   # mănunchi, înglobat
    "perete": dict(zip(_N_AER[:9], [1.00, 0.85, 0.79, 0.75, 0.73, 0.72, 0.72, 0.71, 0.70])),               # metoda C
    "pat_perforat": dict(zip(_N_AER[:9], [1.00, 0.88, 0.82, 0.77, 0.75, 0.73, 0.73, 0.72, 0.72])),         # metoda E
    "scara": dict(zip(_N_AER[:9], [1.00, 0.87, 0.82, 0.80, 0.80, 0.79, 0.79, 0.78, 0.78])),                # metoda E
}
# B.52.18 — cabluri direct în pământ (D2). Cheie distanță: "atingere", "1d" (un diametru), 0.125, 0.25, 0.5 [m]
_N_SOL = [2, 3, 4, 5, 6, 7, 8, 9, 12, 16, 20]
K_GRUP_D2 = {
    "atingere": dict(zip(_N_SOL, [0.75, 0.65, 0.60, 0.55, 0.50, 0.45, 0.43, 0.41, 0.36, 0.32, 0.29])),
    "1d":       dict(zip(_N_SOL, [0.80, 0.70, 0.60, 0.55, 0.55, 0.51, 0.48, 0.46, 0.42, 0.38, 0.35])),
    0.125:      dict(zip(_N_SOL, [0.85, 0.75, 0.70, 0.65, 0.60, 0.59, 0.57, 0.55, 0.51, 0.47, 0.44])),
    0.25:       dict(zip(_N_SOL, [0.90, 0.80, 0.75, 0.70, 0.70, 0.67, 0.65, 0.63, 0.59, 0.56, 0.53])),
    0.5:        dict(zip(_N_SOL, [0.90, 0.85, 0.80, 0.80, 0.80, 0.76, 0.75, 0.74, 0.71, 0.68, 0.66])),
}
# B.52.19 — cabluri multipolare în tuburi în pământ (D1), câte un cablu pe tub. n = 2..20 [P] tab. 2.7
_N_D1 = list(range(2, 21))
K_GRUP_D1 = {
    "atingere": dict(zip(_N_D1, [0.85, 0.75, 0.70, 0.65, 0.60, 0.57, 0.54, 0.52, 0.49, 0.47, 0.45, 0.44, 0.42, 0.41, 0.39, 0.38, 0.37, 0.35, 0.34])),
    0.25:       dict(zip(_N_D1, [0.90, 0.85, 0.80, 0.80, 0.80, 0.76, 0.74, 0.73, 0.72, 0.70, 0.69, 0.68, 0.68, 0.67, 0.66, 0.65, 0.65, 0.64, 0.63])),
    0.5:        dict(zip(_N_D1, [0.95, 0.90, 0.85, 0.85, 0.80, 0.80, 0.78, 0.77, 0.76, 0.75, 0.74, 0.73, 0.72, 0.72, 0.71, 0.70, 0.70, 0.69, 0.68])),
    1.0:        dict(zip(_N_D1, [0.95, 0.95, 0.90, 0.90, 0.90, 0.88, 0.88, 0.87, 0.86, 0.86, 0.85, 0.85, 0.84, 0.84, 0.83, 0.83, 0.83, 0.82, 0.82])),
}

def k_temperatura(izolatie, metoda, theta_c):
    """Factor de temperatură. Valori intermediare: se ia rândul cu temperatura IMEDIAT SUPERIOARĂ (conservator, fără interpolare).
    Temperaturi sub minimul tabelului → valoarea minimului; peste maxim → ValueError (BLOCANT)."""
    tab = K_TEMP_SOL[izolatie] if metoda in METODE_IN_PAMANT else K_TEMP_AER[izolatie]
    chei = sorted(tab)
    if theta_c > chei[-1]:
        raise ValueError("temperatura ambiantă în afara tabelului B.52.14/B.52.15")
    for c in chei:
        if c >= theta_c:
            return tab[c]
    return tab[chei[-1]]

def k_rezistivitate_sol(metoda, rho_kmw):
    """Factor de rezistivitate termică a solului (doar D1/D2). Valori intermediare: rândul cu rezistivitatea IMEDIAT SUPERIOARĂ.
    Peste 3,0 K·m/W → ValueError (BLOCANT: necesită studiu)."""
    if metoda not in METODE_IN_PAMANT:
        return 1.0
    tab = K_SOL[metoda]
    chei = sorted(tab)
    if rho_kmw > chei[-1]:
        raise ValueError("rezistivitate termică sol > 3 K·m/W")
    for c in chei:
        if c >= rho_kmw:
            return tab[c]
    return tab[chei[-1]]

def k_grupare(metoda, n_circuite, distanta="atingere", aranjament_aer=None):
    """Factor de grupare pentru n_circuite (inclusiv cablurile în paralel ale aceleiași ramuri, fiecare = un circuit).
    n intermediar (ex. 10, 13) → se ia rândul cu n IMEDIAT SUPERIOR (conservator). n > 20 → ValueError (BLOCANT).
    metoda D1 → B.52.19; D2 → B.52.18; C → B.52.17 'perete'; E → B.52.17 'pat_perforat' (implicit) sau aranjament_aer;
    F_* → B.52.17 'pat_perforat' aplicat pe circuite trifazate [simplificare conservatoare față de B.52.21]."""
    if n_circuite <= 1:
        return 1.0
    if n_circuite > 20:
        raise ValueError("peste 20 de circuite grupate — în afara tabelelor")
    if metoda == "D1":
        tab = K_GRUP_D1[distanta if distanta in K_GRUP_D1 else "atingere"]
    elif metoda == "D2":
        tab = K_GRUP_D2[distanta if distanta in K_GRUP_D2 else "atingere"]
    else:
        rand = aranjament_aer or {"C": "perete", "B2": "strans"}.get(metoda, "pat_perforat")
        tab = K_GRUP_AER[rand]
    chei = sorted(tab)
    for c in chei:
        if c >= n_circuite:
            return tab[c]
    return tab[chei[-1]]          # rândurile 'perete'/'pat'/'scara' nu se mai reduc peste 9

# =====================================================================================================
# 5. Aparate de protecție — serii standard
# =====================================================================================================
# MCB — SR EN 60898-1 (valori preferate + 80…125 A); serii comerciale ABB/Schneider [VERIFICAT: cataloage, raport #19]
MCB_IN_A = [6, 10, 13, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125]
MCB_ICN_KA = [6, 10, 15, 25]           # [VERIFICAT: ST 4-JT §4.2.4 g, ST 3-JT §4.2.1 f — ≥ 6 kA]; 4,5 kA nu se folosește
MCB_CURBE = ("B", "C", "D")
# MCCB — SR EN 60947-2; serii comerciale (In = calibrul declanșatorului) [VERIFICAT: cataloage ABB/Schneider, raport #21]
MCCB_IN_A = [16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160, 200, 250, 320, 400, 500, 630, 800, 1000, 1250, 1600]
MCCB_ICU_KA = [25, 36, 50, 70, 100, 150]          # DECIZIE: minim 25 kA pentru MCCB
# ACB — SR EN 60947-2
ACB_IN_A = [630, 800, 1000, 1250, 1600, 2000, 2500, 3200, 4000]
ACB_ICU_KA = [42, 50, 65, 85, 100, 130]
# gG — SR EN 60269-1/-2 (NH); calibre preferate
GG_IN_A = [2, 4, 6, 10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250]   # seria R10 (35/355 A NH există, dar nu au porți în SR EN 60269-1)
GG_ICU_KA = 120.0                       # v1.2: capacitatea de rupere a patroanelor NH gG la 400/500 V c.a. (SR EN 60269-2,
                                        # ≥ 120 kA la NH 000…4a). 50 kA rămâne cerința minimă ST 4-JT pentru SF din BMPT.
# Gabarit NH după In (limita superioară a gabaritului) — SR EN 60269-2 / cataloage [VERIFICAT: ST 4-JT §4.2.2 e, raport #24]
GG_GABARIT_NH = [(100, "NH000"), (160, "NH00"), (250, "NH1"), (400, "NH2"), (630, "NH3"), (1250, "NH4a")]
# gPV — SR EN 60269-6, cartușe 10×38 mm 1000/1100/1500 V c.c. [VERIFICAT: cataloage Mersen / ETI, raport #25]
GPV_IN_A = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 16, 20, 25, 30, 32]
# RCCB / RCBO
RCCB_IN_A = [16, 25, 40, 63, 80, 100, 125]          # peste 125 A: bloc diferențial asociat MCCB (In = In MCCB)
RCD_IDN_MA = [10, 30, 100, 300, 500, 1000]

# Treptele de reglaj Ir (DECIZIE: pas 0,05·In, rotunjire în sus)
IR_TREPTE = {
    "MCCB_TM": [round(0.70 + 0.05 * i, 2) for i in range(7)],          # 0,70 … 1,00 · In
    "MCCB_EL": [round(0.40 + 0.05 * i, 2) for i in range(13)],         # 0,40 … 1,00 · In
    "ACB":     [round(0.40 + 0.05 * i, 2) for i in range(13)],
}
MCCB_TM_IN_MAX = 250                  # DECIZIE: termomagnetic până la 250 A, electronic (LSI) de la 320 A
IM_TM_MULTIPLU = 10.0                 # Im fix = 10·In (TM uzual) — dar cel puțin IM_TM_MIN_A la In ≤ 50 A (im_tm)
# [VERIFICAT: cataloage ABB Tmax T1/XT1 TMD (I3 fix 500 A la 16…50 A), Schneider TM-D — raport #29]
IM_TM_MIN_A = 500.0
IM_TM_IN_MIN_FIX_A = 50


def im_tm(in_a):
    """Im al declanșatorului termomagnetic MCCB: max(10·In; 500 A) la In ≤ 50 A, altfel 10·In (raport #29)."""
    im = IM_TM_MULTIPLU * float(in_a)
    return max(im, IM_TM_MIN_A) if float(in_a) <= IM_TM_IN_MIN_FIX_A + 1e-9 else im
ISD_MULTIPLI = [1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0]    # ·Ir, electronic
TSD_S = 0.1                           # temporizare scurtă implicită când există aparate în aval
TOLERANTA_MAGNETIC = 1.20             # SR EN 60947-2 art. 8.3.3.1.2: ±20 % → Ia = 1,2·Im (sau 1,2·Isd)

# Curentul convențional de funcționare I2 (SR HD 60364-4-43 art. 433.1: I2 ≤ 1,45·Iz)
I2_MULTIPLU = {
    "MCB": 1.45,      # SR EN 60898-1, ×In
    "MCCB": 1.30,     # SR EN 60947-2 tab. 6, ×Ir
    "ACB": 1.30,      # idem
    "gPV": 1.45,      # SR EN 60269-6, ×In
}
def i2_gg(in_a):
    """gG: If/In după IEC 60269-1 (ed. 2006 tab. 2 / ed. 2024 tab. 3) [VERIFICAT: raport #32]: 2,1 (In ≤ 4 A),
    1,9 (4 < In < 16 A), 1,6 (In ≥ 16 A)."""
    if in_a <= 4:
        return 2.1
    if in_a < 16:
        return 1.9
    return 1.6
# Curentul convențional de nefuncționare gG (pentru informare)
def inf_gg(in_a):
    return 1.5 if in_a < 16 else 1.25

# Timp convențional gG [h] (SR EN 60269-1) [SE4]
GG_TIMP_CONV_H = [(63, 1), (160, 2), (400, 3), (10 ** 6, 4)]

# =====================================================================================================
# 6. Deconectarea automată (SR HD 60364-4-41) — curentul Ia care asigură funcționarea în timpul cerut
# =====================================================================================================
# Timpi maximi (tab. 41.1, U0 = 230 V): TN 0,4 s / TT 0,2 s pentru circuite finale ≤ 63 A (DECIZIE: aplicat tuturor
# circuitelor finale ≤ 63 A, indiferent dacă au prize — conservator); circuite de distribuție și finale > 63 A: TN 5 s / TT 1 s.
T_DECONECTARE_S = {("TN", "final"): 0.4, ("TN", "distributie"): 5.0, ("TT", "final"): 0.2, ("TT", "distributie"): 1.0}
IN_MAX_CIRCUIT_FINAL_0_4S_A = 63

# MCB: Ia = multiplu·In (limita superioară a declanșării instantanee, SR EN 60898-1 tab. 7) — [V] pentru B, C
MCB_IA_MULTIPLU = {"B": 5.0, "C": 10.0, "D": 20.0}

# gG: Ia [A] la 0,4 s și la 5 s.
#  2…80 A: DIN VDE 0100-600 Bbl. tab. NB.1 [V] (verificat).
#  100…1250 A la 5 s: IEC 60269-1 (ed. 2006 tab. 3 / ed. 2024 tab. 4), poarta Imax(5 s) [VERIFICAT: raport #36, #38].
GG_IA_0_4S_A = {2: 16, 4: 32, 6: 47, 10: 82, 16: 107, 20: 145, 25: 180, 32: 265, 35: 295, 40: 310, 50: 460, 63: 550, 80: 960}
GG_IA_5S_A = {2: 9.2, 4: 19, 6: 27, 10: 47, 16: 65, 20: 85, 25: 110, 32: 150, 35: 173, 40: 190, 50: 260, 63: 320, 80: 440,
              100: 580, 125: 715, 160: 950, 200: 1250, 250: 1650, 315: 2200, 355: 2500, 400: 2840, 500: 3800, 630: 5100,
              800: 7000, 1000: 9500, 1250: 13000}
# 355 A: interpolat între 315 și 400 A, rotunjit în sus (conservator; 355 A nu e în GG_IN_A — raport #37).
# ARBITRAJ 12.10.2026 (DISCREPANTE obs. 1): sursa unică pentru Ia(5 s) este REGULA
#   Ia(5 s) = max(valoarea VDE 0100-600 Bbl. NB.1 ; poarta Imax(5 s) din SR EN 60269-1).
# La 50 A și 80 A VDE dă 260/440 A, peste porțile 250/425 A (VDE include toleranța timpului total de funcționare);
# se păstrează valoarea mai mare (conservatoare: cere Ik1 mai mare). Peste 80 A tabelul = poarta. Verificat în _autoverificare().

# Porți gG IEC 60269-1 (ed. 2006 tab. 3 / ed. 2024 tab. 4) (selectivitate și verificare): In: (Imin10s, Imax5s, Imin0,1s, Imax0,1s)
# [VERIFICAT: toate cele 20 de rânduri pe tabelul de porți reprodus de Mersen TM-104 / ETI — raport #38].
GG_PORTI_A = {16: (33, 65, 85, 150), 20: (42, 85, 110, 200), 25: (52, 110, 150, 260), 32: (75, 150, 200, 350),
              40: (95, 190, 260, 450), 50: (125, 250, 350, 610), 63: (160, 320, 450, 820), 80: (215, 425, 610, 1100),
              100: (290, 580, 820, 1450), 125: (355, 715, 1100, 1910), 160: (465, 950, 1450, 2590),
              200: (610, 1250, 1910, 3420), 250: (750, 1650, 2590, 4500), 315: (1050, 2200, 3420, 6000),
              400: (1420, 2840, 4500, 8060), 500: (1780, 3800, 6000, 10600), 630: (2200, 5100, 8060, 14140),
              800: (3060, 7000, 10600, 19000), 1000: (4000, 9500, 14140, 24000), 1250: (5000, 13000, 19000, 35000)}
# I²t de prearc gG la 0,01 s [A²s ×10³] (min, max) [SE4] — selectivitate gG–gG: I²t_prearc_min(amonte) > I²t_total(aval)
GG_I2T_PREARC_KA2S = {16: (0.3, 1.0), 20: (0.5, 1.8), 25: (1.0, 3.0), 32: (1.8, 5.0), 40: (3.0, 9.0), 50: (5.0, 16), 63: (9.0, 27),
                      80: (16, 46), 100: (27, 86), 125: (46, 140), 160: (86, 250), 200: (140, 400), 250: (250, 760),
                      315: (400, 1300), 400: (760, 2250), 500: (1300, 3800), 630: (2250, 7500), 800: (3800, 13600),
                      1000: (7840, 25000), 1250: (13700, 47000)}
RAPORT_SELECTIVITATE_GG = 1.6          # [VERIFICAT: IEC 60269-1/-2, raport #40] raport de selectivitate 1,6:1 pentru gG ≥ 16 A
RAPORT_SELECTIVITATE_SUPRASARCINA = 1.6  # DECIZIE pentru MCCB/MCB amonte față de orice aval (zona termică)
RAPORT_SELECTIVITATE_MAGNETIC = 1.5      # Im/Isd amonte ≥ 1,5 × Ia aval (DECIZIE, regulă uzuală ABB/Schneider)

# =====================================================================================================
# 7. Constante k pentru verificarea adiabatică S ≥ √(I²t)/k [A·√s/mm²]
# =====================================================================================================
# Conductoare de fază — SR HD 60364-4-43 tab. 43A (= A.54.3) [SE3]
K_FAZA = {("Cu", "PVC"): 115, ("Al", "PVC"): 76, ("Cu", "XLPE"): 143, ("Al", "XLPE"): 94}
# PE ca conductor al unui cablu multipolar — SR HD 60364-5-54 tab. A.54.3 [SE3]
K_PE_IN_CABLU = dict(K_FAZA)
# PE izolat neîncorporat în cablu sau gol în contact cu mantaua — tab. A.54.2, inițial 30 °C [SE3]
K_PE_SEPARAT = {("Cu", "PVC"): 143, ("Al", "PVC"): 95, ("Cu", "XLPE"): 176, ("Al", "XLPE"): 116, ("OL", "PVC"): 52, ("OL", "XLPE"): 64}

def s_pe_tabel(s_faza):
    """SR HD 60364-5-54 tab. 54.2 (același material ca faza): S ≤ 16 → S; 16 < S ≤ 35 → 16; S > 35 → S/2. [SE3]"""
    if s_faza <= 16:
        return float(s_faza)
    if s_faza <= 35:
        return 16.0
    return s_faza / 2.0

# =====================================================================================================
# 8. Căderi de tensiune admisibile [%] — I7-2011 art. 5.2.5 / SR HD 60364-5-52 anexa G [I7]
#    Măsurate de la punctul de delimitare (alimentare din rețeaua publică JT) sau de la bornele JT ale PT propriu.
# =====================================================================================================
DU_MAX_PCT = {
    ("retea_publica", "iluminat"): 3.0,
    ("retea_publica", "forta"): 5.0,
    ("pt_propriu", "iluminat"): 6.0,
    ("pt_propriu", "forta"): 8.0,
}
DU_PORNIRE_MOTOR_PCT = 12.0          # dacă producătorul nu dă altă valoare [I7]
DU_REZERVA_CIRCUITE_FINALE_PCT = 2.0  # DECIZIE: la bara unui tablou secundar ΔU ≤ limita_forță − 2 %
DU_CEF_CA_RECOMANDAT_PCT = 1.0        # DECIZIE (practică): creșterea de tensiune invertor → PCC ≤ 1 % (AVERTISMENT)
DU_CEF_CA_MAX_PCT = 3.0               # v1.2 DECIZIE: peste 3 % pe cablul invertorului → mărire automată, altfel V20 BLOCANT
                                      # (PI declanșează la 1,1·Un medie pe 10 min / 1,15·Un în 0,5 s — Ord. ANRE
                                      # 228/2018 tab. 2P și SR EN 50549-1) [VERIFICAT: raport #49]

# =====================================================================================================
# 9. Coeficient de simultaneitate implicit pentru tablouri (IEC 61439-2 tab. 101 „rated diversity factor”) [SE5]
#    Folosit DOAR când utilizatorul nu dă ks; declarat pe planșă.
# =====================================================================================================
KS_TABLOU = [(1, 1.0), (3, 0.9), (5, 0.8), (9, 0.7), (10 ** 6, 0.6)]   # (n_max_plecari, ks)
def mcb_i2t(in_a, ik_a, curba="C"):
    """I²t lăsat să treacă de un MCB B/C clasa 3 (In ≤ 32 A) la Ik [A²s], pe curbă (SR EN 60898-1 anexa ZA);
    None peste 32 A, la curba D sau peste 10 kA (anexa ZA nu tabelează — let-through-ul producătorului)."""
    if in_a > 32:
        return None
    c = str(curba or "C").upper()
    if c not in MCB_I2T_CLASA3_A2S:
        return None
    tab = MCB_I2T_CLASA3_A2S[c][16 if in_a <= 16 else 32]
    for ik, e in tab:
        if ik_a <= ik + 1e-9:
            return float(e)
    return None


def ks_implicit(n_plecari):
    for n_max, ks in KS_TABLOU:
        if n_plecari <= n_max:
            return ks
    return 0.6
COSFI_IMPLICIT = {"forta": 0.90, "iluminat": 0.90, "prize": 0.90, "tablou": 0.90, "motor": 0.85, "invertor": 1.0, "pcs": 1.0}
FACTOR_SMAX_INVERTOR = 1.10   # Smax = 1,1·Pn când fișa invertorului lipsește [VERIFICAT: Huawei 330KTL-H1 / 100KTL-M1, raport #51]
FACTOR_IP_INVERTOR = 1.25     # Ir/In protecție invertor ≥ 1,25·Pn/(√3·Un) [VERIFICAT: manualele producătorilor, raport #52]
FACTOR_ICONTINUU_MOTOR = 1.0
# v1.2 R2: MCB curba B/C, clasa 3 de limitare a energiei (SR EN 60898-1 anexa ZA): I²t max lăsat să treacă [A²s]
# în funcție de curentul de scurtcircuit [A], TABELE SEPARATE pe curbă [VERIFICAT: anexa ZA reprodusă în catalogul
# IPD p. 217 — raport #43]. Anexa ZA se oprește la 10 kA: peste → let-through-ul producătorului (mcb_i2t → None).
MCB_I2T_CLASA3_A2S = {
    "B": {16: [(3000, 15000), (4500, 25000), (6000, 35000), (10000, 70000)],
          32: [(3000, 18000), (4500, 32000), (6000, 45000), (10000, 90000)]},
    "C": {16: [(3000, 18000), (4500, 30000), (6000, 42000), (10000, 84000)],
          32: [(3000, 22000), (4500, 39000), (6000, 55000), (10000, 110000)]},
}
GG_I2T_TOTAL_FACTOR = 2.0   # v1.2 R2: I²t total de deconectare gG ≈ 2 × I²t de prearc max (zona limitatoare) [DECIZIE]
# v1.2: pornirea motoarelor (SPEC §B.3.1). Ip/Ib după modul de pornire; durata de calcul a pornirii.
MOTOR_IP_MULTIPLU = {"directa": 6.0, "stea_triunghi": 2.0, "soft": 3.0, "vfd": 1.0}
MOTOR_DOL_P_MIN_INTRERUPATOR_MOTOR_KW = 18.5   # r6: DOL ≥ 18,5 kW → întrerupător-motor / MCCB, nu MCB curba C
MOTOR_IM_MULTIPLU = 13.0             # întrerupător-motor: magnetic ≈ 13·In [VERIFICAT: Schneider GV2-ME, Siemens 3RV2 — raport #53]
MOTOR_VARF_ASIMETRIC = 2.0           # vârful primei semiperioade la pornire directă ≈ 2·Ip pornire (rms)
MOTOR_T_PORNIRE_S = 10.0              # DECIZIE conservatoare: poarta Imin(10 s) gG; pornire directă „câteva secunde”
MOTOR_COSFI_PORNIRE = 0.35

# r7 (S8): randamentul și cosφ tipice ale motoarelor asincrone trifazate 4 poli, 50 Hz, clasa IE3 — η minim din
# SR EN IEC 60034-30-1 tab. 3 (IE3, 4 poli), cosφ la sarcină nominală din cataloagele uzuale (ABB M3BP / Siemens 1LE1 /
# WEG W22, 400 V) [valori tipice — fișa motorului are prioritate: `randament` / `cosfi` pe plecare].
# Curentul nominal: In = P / (√3·U·η·cosφ) (P = puterea mecanică la arbore, cea de pe plăcuță).
# (P_kW, η, cosφ) — treapta e prima putere ≥ P motorului; peste ultima treaptă se ia ultima.
MOTOR_IE3_4P = (
    (0.75, 0.825, 0.75), (1.1, 0.841, 0.78), (1.5, 0.853, 0.79), (2.2, 0.867, 0.81), (3.0, 0.877, 0.81),
    (4.0, 0.886, 0.82), (5.5, 0.896, 0.83), (7.5, 0.904, 0.84), (11.0, 0.914, 0.84), (15.0, 0.921, 0.85),
    (18.5, 0.926, 0.85), (22.0, 0.930, 0.85), (30.0, 0.936, 0.86), (37.0, 0.939, 0.86), (45.0, 0.942, 0.86),
    (55.0, 0.946, 0.86), (75.0, 0.950, 0.85), (90.0, 0.952, 0.86), (110.0, 0.954, 0.86), (132.0, 0.956, 0.87),
    (160.0, 0.958, 0.87), (200.0, 0.960, 0.87), (250.0, 0.960, 0.87), (315.0, 0.960, 0.87), (375.0, 0.960, 0.87),
)
TC_REZERVA_IB = 1.2               # r7: TC de măsură — primar ≥ 1,2·Ib (nu TC 50/5 la 47,6 A)
LOCUINTA_IB_SEMIDIRECT_A = 80    # r7: casă trifazată peste ~80 A → semnalare măsură semidirectă
LOCUINTA_VE_MONO_MAX_KW = 7.4    # r7 (#19): încărcător VE monofazat max. 32 A × 230 V (SR EN IEC 61851-1)
MOTOR_P_DEMAROR_KW = 18.5        # r7: ≥ 18,5 kW (sau Ip > 63 A) → demaror (întreruptor-motor / MCCB + KM + releu termic)


def motor_eta_cosfi(p_kw):
    """(η, cosφ) tipice IE3 4 poli pentru puterea motorului (MOTOR_IE3_4P); sub 0,75 kW → treapta 0,75 kW."""
    p = float(p_kw)
    for pk, eta, cos in MOTOR_IE3_4P:
        if p <= pk + 1e-9:
            return eta, cos
    return MOTOR_IE3_4P[-1][1], MOTOR_IE3_4P[-1][2]

# =====================================================================================================
# 10. Transformatoare MT/JT 20/0,4 kV
# =====================================================================================================
# Sn [kVA]: (uk %, Pk W, Po W). uk: SR EN 50588-1 (ulei) — 4 % ≤ 630 kVA, 6 % ≥ 800 kVA [practică — standard cu plată, raport #55].
# Pk/Po: Reg. (UE) 548/2014 Tier 2 (de la 01.07.2021), ulei, ≤ 24 kV: Ak / A0−10 % [C] (verificat).
TRAFO = {
    100: (4.0, 1250, 130), 160: (4.0, 1750, 189), 250: (4.0, 2350, 270), 400: (4.0, 3250, 387), 630: (4.0, 4600, 540),
    800: (6.0, 6000, 585), 1000: (6.0, 7600, 693), 1250: (6.0, 9500, 855), 1600: (6.0, 12000, 1080),
    2000: (6.0, 15000, 1305), 2500: (6.0, 18500, 1575),
}
TRAFO_SN_KVA = sorted(TRAFO)
# r5: transformator USCAT (rășină epoxidică, Um ≤ 24 kV) — Reg. UE 548/2014 anexa I tab. I.2, Tier 2: (uk %, Pk W la
# 120 °C, P0 W). uk 4 % până la 400 kVA, 6 % de la 630 kVA (valoarea uzuală a producătorilor) [orientativ — fișa producătorului]
TRAFO_USCAT = {
    100: (4.0, 1800, 252), 160: (4.0, 2600, 360), 250: (4.0, 3400, 468), 400: (4.0, 4500, 675), 630: (6.0, 7100, 990),
    800: (6.0, 8000, 1170), 1000: (6.0, 9000, 1395), 1250: (6.0, 11000, 1620), 1600: (6.0, 13000, 1980),
    2000: (6.0, 16000, 2340), 2500: (6.0, 19000, 2790),
}


def trafo_date(sn_kva, izolatie="ulei"):
    """(uk %, Pk W, P0 W) pentru trafo în ulei (TRAFO) sau uscat (TRAFO_USCAT)."""
    return (TRAFO_USCAT if izolatie == "uscat" else TRAFO)[sn_kva]
TRAFO_GRUPA_CONEXIUNI = "Dyn5"           # [DECIZIE proiectant 28.10.2026, Î9] DEER; se confirmă cu OD (Dyn11 la unele OD)
# Siguranțe MT pentru celula trafo cu separator de sarcină + siguranțe (SR EN 62271-105), 20 kV [practică, raport #58]
# — orientativ ≈ 2…2,2·In_MT; valoarea finală din tabelul producătorului celulei.
TRAFO_SIGURANTA_MT_A = {100: 6.3, 160: 10, 250: 16, 400: 25, 630: 40, 800: 50, 1000: 63}
# r6: tensiunea MT parametrică — U_MT [kV] → tensiunea cea mai ridicată a echipamentului Um [kV] (SR EN 62271-1)
U_MT_UM_KV = {6: 7.2, 10: 12.0, 15: 17.5, 20: 24.0}
SIGURANTE_MT_SERIE_A = (6.3, 10, 16, 20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200)


def siguranta_mt(sn_kva, u_kv=20):
    """Siguranța MT orientativă a celulei trafo: tabelul la 20 kV, altfel ≈ 2·In_MT (aceeași regulă care reproduce
    tabelul de la 20 kV) — valoarea finală din tabelul producătorului celulei [NEVERIFICAT: practică, raport #58]."""
    if u_kv == 20 and sn_kva in TRAFO_SIGURANTA_MT_A:
        return TRAFO_SIGURANTA_MT_A[sn_kva]
    i_mt = sn_kva / (3 ** 0.5 * u_kv)
    return next((x for x in SIGURANTE_MT_SERIE_A if x >= 2.0 * i_mt - 1e-9), None)


TRAFO_SN_MAX_SIGURANTE_MT_KVA = 630     # [DECIZIE proiectant 28.10.2026, Î10]: siguranțe MT până la 630 kVA; peste
                                        # 630 kVA celula trafo cu întreruptor + releu 50/51, 50N/51N

def in_trafo_jt(sn_kva):
    return sn_kva * 1000.0 / (SQRT3 * u_n())

# =====================================================================================================
# 11. Branșamente DEER
# =====================================================================================================
# ST 4-JT Ed. U1 Rev. 3/2024 [D4] — verificat. NU există BMPTd-63 (nici în Rev. 0/2020).
BMPT = {
    "BMPTd-16":  {"I_min_A": 0, "I_max_A": 16, "masura": "directa", "SF_soclu_A": 160, "SF_fuzibil_A": 40, "SF_gabarit": "NH00",
                  "Q_tip": "MCB", "Q_curba": "C", "Q_in_A": [16], "S_int_min_mm2": 6, "varianta": 1},
    "BMPTd-40":  {"I_min_A": 16, "I_max_A": 40, "masura": "directa", "SF_soclu_A": 160, "SF_fuzibil_A": 40, "SF_gabarit": "NH00",
                  "Q_tip": "MCB", "Q_curba": "C", "Q_in_A": [20, 25, 32, 40], "S_int_min_mm2": 10, "varianta": 2},
    "BMPTd-100": {"I_min_A": 40, "I_max_A": 100, "masura": "directa", "SF_soclu_A": 160, "SF_fuzibil_A": 100, "SF_gabarit": "NH00",
                  "Q_tip": "MCB", "Q_curba": "C", "Q_in_A": [50, 63, 80, 100], "S_int_min_mm2": 35, "varianta": 3},
    "BMPTi-250": {"I_min_A": 100, "I_max_A": 250, "masura": "semidirecta", "SF_soclu_A": 250, "SF_fuzibil_A": 250, "SF_gabarit": "NH1",
                  "Q_tip": "MCCB", "Q_curba": None, "Q_in_A": [125, 160, 200, 250], "S_int_min_mm2": 150, "varianta": 4,
                  "S_borna_max_mm2": 150},
}
BMPT_ORDINE = ["BMPTd-16", "BMPTd-40", "BMPTd-100", "BMPTi-250"]
BMPT_I_MAX_A = 250
BMPT_Q_ICN_MIN_KA = 6.0
BMPT_SF_ICU_KA = 50.0
# DDR-ul general din BMPT: RCCB 4P 300 mA tip AC, Inc ≥ 6 kA [VERIFICAT: ST 4-JT §4.2.6 i, §4.5.11 — raport #61;
# DECIZIE proiectant 28.10.2026, Î1 — înlocuiește decizia r8 „tip A”]; tip A / S doar declarat (DDR_bransament_tip)
BMPT_RCCB = {"poli": 4, "idn_ma": 300, "tip": "AC", "icn_min_ka": 6.0, "in_min_A": 16, "in_max_A": 250}
BMPT_DPST = {"Uf_V": 270, "Uf_tol_V": 10, "Ul_V": 467, "t_min_s": 0.13, "t_max_s": 0.20}
BMPT_TC = {"primar_A": [125, 150, 200, 250], "secundar_A": 5, "clasa": "0,5", "Sn_VA": 5.0, "factor_extindere": 1.2}
# Contorul: BMPT / BMPM se livrează FĂRĂ contor, OD îl montează — pe planșă fără curent nominal [VERIFICAT: ST 4-JT
# §4.2.3 / §4.2.8 d, ST 3-JT §4.2.3 — raport #64, #66; DECIZIE proiectant 28.10.2026, Î15]
CONTOR_DIRECT_TRIFAZAT = "contor electronic trifazat, conexiune directă, furnizat și montat de OD"
# ST 3-JT Ed. U1 Rev. 3/2026 [D3] — verificat
BMPM = {"I_max_A": 40, "Q_tip": "RCBO 1P+N", "Q_curba": "C", "Q_in_A": [16, 20, 25, 32, 40], "Q_icn_min_ka": 6.0,
        "idn_ma": 300, "rcd_tip": "AC", "SF": "separator monopolar cu fuzibil 40 A gG, gabarit 00, 50 kA",
        "DPST_Uf_V": 270, "S_int_min_mm2": {32: 6, 40: 10}}
CONTOR_DIRECT_MONOFAZAT = "contor electronic monofazat, conexiune directă, furnizat și montat de OD"

# =====================================================================================================
# 12. Transformatoare de curent (SR EN 61869-2) și circuitul secundar
# =====================================================================================================
TC_PRIMAR_A = [50, 75, 100, 125, 150, 200, 250, 300, 400, 500, 600, 750, 800, 1000, 1250, 1500, 2000, 2500, 3000, 4000]  # [VERIFICAT: SR EN 61869-2, raport #68]
TC_SECUNDAR_A = 5
PT_SERVICII_PROPRII_A = 16          # plecarea de servicii proprii din TGJT (iluminat, prize, încălzire post) — DECIZIE
TC_SN_VA = [2.5, 5.0, 10.0, 15.0]
TC_FACTOR_EXTINDERE = 1.2               # ext. 120 % (DECIZIE; DEER cere cl. 0,5 — ST 4-JT)
TC_RHO_SECUNDAR = 0.021                 # Ω·mm²/m, Cu la 75 °C [VERIFICAT: 0,017241·(1 + 0,00393·55), raport #70]
TC_CONSUM_CONTOR_VA = 1.0               # majorant de normă (IEC 62053-22) când fișa contorului lipsește [practică, raport #71]
TC_CONSUM_CONTACTE_VA = 0.1             # DECIZIE

# =====================================================================================================
# 13. CEF / prosumatori
# =====================================================================================================
PV_T_MIN_C = -25.0                       # DECIZIE: temperatura minimă de calcul (România, conservator)
PV_BETA_UOC_IMPLICIT_PCT_K = -0.27       # majorant module actuale (TOPCon −0,25…−0,26, PERC −0,27…−0,28) [VERIFICAT: fișe, raport #77]
PV_UMAX_INVERTOR_IMPLICIT_V = 1000.0     # minorant când fișa lipsește (Fronius Symo/Primo, SMA STP TL: 1000 V; 1100 V doar
                                         # Huawei/Sungrow) [VERIFICAT: fișe producători, raport #78]
PV_FACTOR_ISC = 1.25                     # dimensionare cabluri string fără siguranțe: Iz ≥ 1,25·Isc_STC (practică IEC 60364-7-712)
GPV_IN_MIN_FACTOR = 1.5                  # SR HD 60364-7-712: 1,5·Isc_STC ≤ In ≤ 2,4·Isc_STC și In ≤ I_MOD_REVERSE
GPV_IN_MAX_FACTOR = 2.4
GPV_NECESAR_DE_LA_STRINGURI = 3          # siguranțe pe string obligatorii de la 3 stringuri în paralel (dacă (Ns−1)·Isc > Irev)
SPD_CC_UCPV_V = [600, 1000, 1100, 1200, 1500]
SPD_CA = {"T1+T2": "Iimp 12,5 kA/pol (10/350), Up ≤ 1,5 kV", "T2": "In 20 kA (8/20), Up ≤ 1,5 kV"}
# Pragurile RfG (A < 1 MW ≤ B < 5 MW ≤ C < 20 MW ≤ D) [VERIFICAT: Ord. ANRE 79/2016 anexa (clasificarea modulelor
# generatoare) + decizia Transelectrica de implementare RfG — raport #83–#85; Ord. 208/2018 = norma de cerințe]
RFG_PRAG_TIP_B_KW = 1000.0
RFG_PRAG_TIP_C_KW = 5000.0
RFG_PRAG_TIP_D_KW = 20000.0              # C/D (sau U ≥ 110 kV)
PROSUMATOR_P_MAX_KW = 400.0              # [VERIFICAT: Ord. ANRE 15/2022, ghidul ANRE — raport #86]; legea nouă (CCR 07/2026,
                                         # nepromulgată la 28.10.2026): 0–200 kW compensare cantitativă — de urmărit
# Ord. ANRE 228/2018 art. 12(3): diferența dintre încărcările fazelor ≤ 16 A → 16 A × 230 V = 3,68 kVA; comparația se face
# pe kVA (Smax = 1,1·Pn fără fișă) [VERIFICAT: raport #87; DECIZIE proiectant 28.10.2026, Î4]
MONOFAZAT_P_INVERTOR_AVERTISMENT_KW = 3.68   # păstrat ca nume (istoric); valoarea e în kVA
MONOFAZAT_S_INVERTOR_AVERTISMENT_KVA = 3.68
# r8 (fotovoltaic P0-5) — invertoare monofazate pe o rețea trifazată (câte unul / mai multe pe fiecare fază)
DEZECHILIBRU_FAZE_MAX_KVA = 3.68         # S max − S min pe fază al generării monofazate ≤ 16 A ≈ 3,68 kVA (Ord. ANRE 228/2018
                                         # art. 12(3); excepții art. 12(4)–(5) în ATR) — peste prag: V71 AVERTISMENT
                                         # [VERIFICAT: raport #88; DECIZIE proiectant 28.10.2026, Î4 — înlocuiește 4,6 kVA]
# r8 (selectivitate CEF cu PT nou): Ir Q JT al trafo se poate ridica peste In_T, cel mult până aici, ca să rămână ≥ Ir QG
# (reglajele cresc spre amonte), numai dacă injecția maximă Σ Iac ≤ In_T (invertoarele își limitează curentul la Iac,max,
# deci trafo nu e suprasolicitat în exploatare; suprasarcina trafo rămâne acoperită de protecția proprie — termometru /
# DGPT2). DECIZIE proiectant; peste prag: V41 AVERTISMENT „selectivitate inversată” cu remediere.
Q_JT_IR_MAX_IN_T = 1.10
# v1.9 (R5 fotovoltaic) — DECIZII proiectant, documentate în SPEC §C.3 / §C.4
# [DECIZIE proiectant 28.10.2026, Î5]: la TOATE casele (prosumatorii) există tablou separat pentru fotovoltaic (TD-PV),
# indiferent de putere. Pragul de 27 kW rămâne doar pentru „prosumatorul comercial” (QG cu releu, PCS separat etc.).
PROSUMATOR_TD_PV_INTOTDEAUNA = True
PROSUMATOR_COMERCIAL_KW = 27.0           # Σ Pn > 27 kW → prosumator comercial (QG general în TD-PV)
PROSUMATOR_PI_EXTERNA_KW = 27.0          # [DECIZIE proiectant 28.10.2026, Î3]: P injectabilă > 27 kW → PI externă (releu
                                         # anti-insularizare pe QG), cerința OD cu care lucrează proiectantul — NU 30 kVA
                                         # (Ord. ANRE 228/2018 art. 14 e mai permisiv); ATR are prioritate
# [DECIZIE proiectant 28.10.2026, Î6]: DDR pe circuitul invertorului DOAR LA CERERE (declarat: `ddr` {IdN_mA, tip} /
# `ddr: true` / `IdN_min_mA` din fișă) — implicit fără DDR în TN („nu prea se pun diferențiale la invertoare”). În TT
# DDR-ul rămâne protecția la defect (regula de mai jos). La cerere fără IΔn: după producător (Huawei ≥ 100 mA la orice
# putere [HW1]; altfel 30 mA ≤ 10 kW, 100 mA peste [SMA] — raport #93).
DDR_INVERTOR_DOAR_LA_CERERE = True
DDR_INVERTOR_PRAG_KW = 30.0              # TT: 100 mA peste 10 kW (curent capacitiv de scurgere al câmpului PV)
DDR_INVERTOR_30MA_MAX_KW = 10.0
DDR_INVERTOR_IDN_MARE_MA = 100           # [VERIFICAT: Huawei „≥ 100 mA” — raport #94]
DDR_INVERTOR_IDN_MIN_PRODUCATOR_MA = {"Huawei": 100}   # [VERIFICAT: HW1 — inclusiv SUN2000-3…10KTL-M1]
SPD_CA_INVERTOR_L_M = 10.0               # SR HD 60364-7-712 (712.534): SPD c.a. și la invertor dacă cablul > 10 m [VERIFICAT: raport #95]
SIGURANTE_CC_BATERIE_A = [16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630]   # gBat / NH c.c.
# E2 (DECIZIE proprietar 28.10.2026): limitarea puterii la punctul de racord (PCC) când Sn trafo < S CEF.
# Propunerea automată: P_lim = Sn trafo × cosφ_PCC × factor (cosφ 0,9 = capabilitatea de putere reactivă cerută la PCC
# de Ord. ANRE 208/2018 / normele tehnice RfG; factor 0,95 = rezervă pentru pierderile trafo și precizia buclei EMS).
PCC_COSFI = 0.9
PCC_FACTOR = 0.95
# Pragurile de racord (DECIZIE de proiectare, nu normă; ATR prevalează):
PRAG_RACORD_BMPT_KVA = SQRT3 * U_N_V * BMPT_I_MAX_A / 1000.0   # ≈ 173,2 kVA (250 A) [VERIFICAT: ST 4-JT BMPTi-250]
PRAG_RACORD_JT_MAX_KVA = 400.0           # [DECIZIE proiectant 28.10.2026, Î13] peste → racord MT cu PT propriu (BLOCANT dacă schema nu are PT și nu există ATR JT)

# =====================================================================================================
# 14. Grup electrogen
# =====================================================================================================
GE_XD2_IMPLICIT = 0.12                   # reactanță subtranzitorie [u.r.] [practică, raport #101] tipic 0,10…0,15
GE_IK_SUSTINUT_MULTIPLU = 3.0            # ≥ 3·In_G timp de ≥ 2 s cu excitație susținută (PMG/AREP) — numai dacă e declarat
GE_IK_SUSTINUT_T_S = 2.0                 # [DECIZIE proiectant 28.10.2026] durata minimă a curentului de scurtcircuit susținut

# Seria de puteri standard GE [kVA] (cataloage uzuale, regim PRP) [VERIFICAT: cataloage, raport #103] — ARBITRAJ F42
GE_SN_KVA = [10, 15, 20, 30, 40, 50, 60, 80, 100, 125, 150, 200, 250, 300, 400, 500, 630, 800, 1000, 1250, 1500, 2000]
GE_COSFI_NOMINAL = 0.8                   # cosφ nominal GE (Sn·0,8 = P activă nominală) — informativ, nu intră în In_G

def ge_sn_minim(P_kW, cosfi=0.9):
    """cea mai mică putere GE din serie cu In_G ≥ Ib sarcină, adică Sn ≥ P/cosφ (pornirea motoarelor NU e inclusă)"""
    s = P_kW / cosfi
    for x in GE_SN_KVA:
        if x >= s - 1e-9:
            return x
    return None

# =====================================================================================================
# 14a. Priza de pământ (v1.3, SPEC §C.7) — electrozi verticali în linie legați cu platbandă orizontală
#      Formule: 1.RE-Ip 30-2004 / STAS 12604/5-90 (forma cu 0,366·ρ/L·lg = ρ/(2πL)·ln), vezi pamant.py.
# =====================================================================================================
PRIZA_RHO_IMPLICIT_OHM_M = 100.0         # [VERIFICAT: prudent față de ST 42 (80 Ω·m) — raport #107] (argilă 40…100,
                                         # nisip argilos 100…300 Ω·m — 1.RE-Ip 30-2004 anexa / STAS 12604/5); se MĂSOARĂ
PRIZA_ELECTROD_L_IMPLICIT_M = 3.0        # electrod OL-Zn × 3 m — practica uzuală (I7 / 1.RE-Ip 30); ATENȚIE: ST 42 Ed. U1 Rev. 0/2025 §3.5 c și tab. 1 dau electrod ø60 × 1,5 m (raport_b3 B3-29) — de decis de proprietar
PRIZA_ELECTROD_D_IMPLICIT_M = 0.060      # țeavă OL-Zn ø60 × 3,6 mm [VERIFICAT: DEER ST 42 anexa 3 — raport #109; înainte 63,5 mm]
PRIZA_N_IMPLICIT = 2
PRIZA_A_PE_L_IMPLICIT = 2.0              # DECIZIE: distanța între electrozi a = 2·L (6 m la L = 3 m)
PRIZA_PLATBANDA_LATIME_IMPLICIT_M = 0.04  # OL-Zn 40 × 4 mm
PRIZA_PLATBANDA_GROSIME_IMPLICIT_M = 0.004
PRIZA_ADANCIME_IMPLICIT_M = 0.8          # platbanda și capul electrozilor la 0,8 m (sub adâncimea de îngheț uzuală — STAS 6054-77: 0,70–0,80 m în câmpia de vest; în zonele mai reci se coboară)
PRIZA_N_MAX = 30                         # dimensionarea automată se oprește la 30 de electrozi (în linie)
PRIZA_RHO_MAX_OHM_M = 10000.0            # DECIZIE: peste → rocă, priză specială (V10)
PRIZA_REZERVA_PLATBANDA = 0.10           # +10 % la lungimea platbandei în lista de materiale
PRIZA_BARA_PLATBANDA_M = 6.0             # DECIZIE: platbanda se livrează în bare de 6 m (numărul de îmbinări sudate)
PRIZA_VOPSEA_KG_IMBINARE = 0.1           # DECIZIE: vopsea bitum pe îmbinările sudate, 0,1 kg/îmbinare
# Coeficienți sezonieri ψ (ρ_calcul = ψ·ρ_măsurat), DISTINCȚI pentru electrozii verticali și pentru platbanda orizontală
# de la ~0,8 m (v1.3 R5, M5-1) [NEVERIFICAT]: 1.RE-Ip 30-2004 / STAS 12604/5 (și PUE tab. 1.7.x) dau, pe zone climatice,
# ψ_e ≈ 1,4…1,8 (electrozi 2…3 m) și ψ_pl ≈ 2,5…4,5 (orizontali la mică adâncime). Zonele (DECIZIE de notare):
# I = rece / sol umed la măsurare, II = medie, III = caldă / sol uscat la măsurare. Implicit zona II.
PRIZA_PSI_ZONE = {"I": 1.8, "II": 1.6, "III": 1.4}                 # electrozi verticali
PRIZA_PSI_PLATBANDA_ZONE = {"I": 4.5, "II": 3.5, "III": 2.5}       # platbandă orizontală la 0,5…0,8 m
PRIZA_PSI_IMPLICIT = 1.6
PRIZA_PSI_PLATBANDA_IMPLICIT = 3.5
PRIZA_L_RACORD_IMPLICIT_M = 5.0          # v1.3 R5 (M5-1): platbanda = (n − 1)·a + racordul la piesa de separație (~5 m)
# Manoperă orientativă pe unitate [ore] (v1.3 R5, minore) — DECIZIE, ordin de mărime din normele de deviz uzuale
# (baterea manuală a electrodului 3 m, montaj platbandă în șanț, sudură, săpătură manuală 0,4 × 0,8 m) [NEVERIFICAT]
PRIZA_ORE_U = {"electrod": 0.8, "platbanda_m": 0.17, "piesa_separatie": 0.5, "sudura": 0.3, "vopsea_kg": 0.5,
               "sapatura_m": 0.6}
# Limite Rp [Ω]: 4 Ω la branșament / tablou / prosumator / CEF JT / GE [DECIZIE proiectant 28.10.2026, Î8 — utilizare și
# branșament 4 Ω]. PT și CEF cu PT propriu (priză comună MT/JT): „conform ANRE” [Î8] — vezi PRIZA_PT_ANRE; normele ANRE
# accesibile (ST 42 DEER §3.5 trimite tot la verificarea tensiunilor de atingere) nu dau o valoare unică: Rp rezultă din
# tratarea neutrului MT (curentul de defect la pământ din ATR) — până la date se păstrează 1 Ω (conservator), declarat.
# TT: RA ≤ 50 V / IΔn (SR HD 60364-4-41 art. 411.5.3).
PRIZA_R_LIMITA_OHM = {"bransament": 4.0, "tablou": 4.0, "cascada": 4.0, "prosumator": 4.0, "cef": 4.0,
                      "ge_ats": 4.0, "pt": 1.0, "cef_pt": 1.0}
# Î8 (28.10.2026) — PT cu priză comună MT/JT „conform ANRE”: căutat în raportul verificatorului (#117) și în sursele ANRE
# accesibile. ST 3-JT / ST 4-JT trimit la 1.RE-Ip 30-2004 fără valoare; ST 42 DEER §3.5 dă 4 Ω (incinte), 10,8 Ω
# (stâlpi), 0,26 Ω (rețea generală la stâlpi comuni MT/JT); suportul de curs pentru examenul ANRE (TUIASI, „Proiectarea
# și verificarea prizelor de pământ” §5.3.1) dă 1 Ω pentru prizele utilizate în comun, iar metoda normată este
# verificarea tensiunilor de atingere și de pas (STAS 12604/5-90) cu curentul de defect la pământ din tratarea
# neutrului MT (ATR). Textul 1.RE-Ip 30-2004 (tematica ANRE) nu s-a putut citi → valoare neclară: se păstrează 1 Ω,
# declarat „conform ANRE — de confirmat cu OD / ATR (Uatingere = Rp·Id)”.
PRIZA_PT_ANRE = {"R_ohm": 1.0, "metoda": "Rp ≤ 1 Ω (priză comună MT/JT, protecție + paratrăsnet); verificarea tensiunilor "
                 "de atingere și de pas cu Id din tratarea neutrului MT (STAS 12604/5-90, 1.RE-Ip 30-2004)",
                 "sursa": "tematica ANRE (1.RE-Ip 30-2004 / curs TUIASI §5.3.1); ST 42 DEER §3.5", "clar": False}
# Coeficienți de utilizare η pentru n electrozi verticali în linie, după a/L ∈ {1, 2, 3} [VERIFICAT: tabelul clasic
# Karyakin / PUE, identic — raport #118].
# Sursa propusă: 1.RE-Ip 30-2004 (Îndreptar de proiectare a prizelor de pământ, ICEMENERG) tab. coeficienți de
# utilizare; aceleași valori în literatura uzuală (Ingeorge R., „Îndrumar pentru proiectarea instalațiilor electrice”;
# Karyakin, „Справочник по заземлению”). n = 30 extrapolat. Între valorile tabelate: interpolare liniară în n;
# a/L se ia pe rândul IMEDIAT INFERIOR (conservator, η mai mic); a/L > 3 → rândul 3; a/L < 1 → V10.
PRIZA_ETA_ELECTROZI = {
    1: {1: 1.00, 2: 0.85, 3: 0.80, 5: 0.70, 10: 0.59, 15: 0.54, 20: 0.49, 30: 0.43},
    2: {1: 1.00, 2: 0.91, 3: 0.87, 5: 0.81, 10: 0.75, 15: 0.71, 20: 0.66, 30: 0.60},
    3: {1: 1.00, 2: 0.94, 3: 0.91, 5: 0.87, 10: 0.81, 15: 0.78, 20: 0.74, 30: 0.69},
}
# Coeficienți de utilizare η ai platbandei care leagă n electrozi în linie [VERIFICAT: tabelul clasic — raport #119];
# n = 2, 3, 15 interpolate/estimate, n = 30 din tabelul pentru 30 de electrozi.
PRIZA_ETA_PLATBANDA = {
    1: {1: 1.00, 2: 0.85, 3: 0.81, 4: 0.77, 5: 0.74, 8: 0.67, 10: 0.62, 15: 0.50, 20: 0.42, 30: 0.31},
    2: {1: 1.00, 2: 0.94, 3: 0.91, 4: 0.89, 5: 0.86, 8: 0.79, 10: 0.75, 15: 0.64, 20: 0.56, 30: 0.46},
    3: {1: 1.00, 2: 0.96, 3: 0.94, 4: 0.92, 5: 0.90, 8: 0.85, 10: 0.82, 15: 0.74, 20: 0.68, 30: 0.58},
}


def priza_eta(tabel, n, a_pe_L):
    """Coeficientul de utilizare η din PRIZA_ETA_* pentru n electrozi și raportul a/L: rândul a/L imediat inferior
    (conservator), interpolare liniară în n. a/L < 1 sau n > 30 → ValueError (în afara tabelelor)."""
    if n == 1:
        return 1.0                       # un singur electrod: fără ecranare reciprocă
    if a_pe_L < 1.0 - 1e-9 or n > PRIZA_N_MAX or n < 1:
        raise ValueError("în afara tabelelor coeficienților de utilizare")
    rand = tabel[max(k for k in tabel if k <= a_pe_L + 1e-9)]
    chei = sorted(rand)
    if n in rand:
        return rand[n]
    jos = max(k for k in chei if k < n)
    sus = min(k for k in chei if k > n)
    return rand[jos] + (rand[sus] - rand[jos]) * (n - jos) / (sus - jos)


# =====================================================================================================
# 14b. Selectivitatea DDR în serie (v1.3, SPEC §B.18.1)
# =====================================================================================================
DDR_RAPORT_SELECTIVITATE = 3.0           # IΔn amonte ≥ 3·IΔn aval (SR HD 60364-5-53; art. 535.3 în ed. 2001) [VERIFICAT: raport #120]
# v1.3 R5 (M5-4): selectivitatea în timp — temporizarea amontelui trebuie să depășească pe a avalului cu ≥ 0,15 s.
# DDR instantaneu (G) = 0 s; DDR tip S (SR EN 61008/61009: nefuncționare ≥ 0,13 s la IΔn, deconectare ≤ 0,5 s) = 0,15 s
# echivalent [DECIZIE]; bloc diferențial / releu reglabil = Δt reglat. Două DDR S în serie NU sunt selective.
DDR_DT_SELECTIVITATE_S = 0.15
DDR_T_ECHIVALENT_S = {"instantaneu": 0.0, "S": 0.15}
DDR_DT_REGLABIL_S = [0.06, 0.15, 0.3, 0.5, 1.0]   # trepte uzuale de temporizare ale releelor diferențiale reglabile
BMPM_RCBO_SELECTIV = False               # [VERIFICAT: ST 3-JT §4.2.4 m „cu declanșare instantanee” — raport #67]

# =====================================================================================================
# 14c. Locuințe — tabloul casei / apartamentului (v1.4, SPEC §C.8)
# =====================================================================================================
# Receptor → valori implicite DECLARATE ca presupuse (DECIZIE după I7-2011 cap. 5–7, SR HD 60364-4-41 art. 411.3.3 /
# 411.3.4, SR HD 60364-7-701 / -7-722 și practica uzuală în România) [NEVERIFICAT individual]:
#   P [kW] mono / tri, cosφ, curba MCB, In minim uzual [A] mono / tri, secțiune minimă Cu [mm²] mono / tri,
#   L implicit [m], receptorul de calcul (§B: iluminat 3 % ΔU, forță 5 %, motor cu pornire), trifazat implicit la rețea
#   tri, grupa DDR dedicată, DDR (obligatoriu / recomandat) și tipul DDR, sarcină continuă (ks = 1 în bilanț).
LOCUINTA_RECEPTORI = {
    #  cheie:                (P mono, P tri, cosφ, curba, In mono, In tri, S mono, S tri, L,  calcul,     3F,    grupa,      DDR,           tip, continuu)
    "iluminat":              (0.5, None, 0.9, "B", 10, None, 1.5, None, 20, "iluminat", False, None, "obligatoriu", "A", False),
    "prize":                 (2.0, None, 0.9, "C", 16, None, 2.5, None, 20, "forta", False, None, "obligatoriu", "A", False),
    "prize_bucatarie":       (2.5, None, 0.9, "C", 16, None, 2.5, None, 15, "forta", False, "bucatarie", "obligatoriu", "A", False),
    "prize_baie":            (2.0, None, 0.9, "C", 16, None, 2.5, None, 15, "forta", False, "baie", "obligatoriu", "A", False),
    "prize_exterior":        (1.5, None, 0.9, "C", 16, None, 2.5, None, 25, "forta", False, "exterior", "obligatoriu", "A", False),
    "masina_spalat_rufe":    (2.2, None, 1.0, "C", 16, None, 2.5, None, 15, "forta", False, None, "obligatoriu", "A", False),
    "masina_spalat_vase":    (2.2, None, 1.0, "C", 16, None, 2.5, None, 15, "forta", False, "bucatarie", "obligatoriu", "A", False),
    "uscator":               (2.5, None, 1.0, "C", 16, None, 2.5, None, 15, "forta", False, None, "obligatoriu", "A", False),
    "boiler":                (2.0, None, 1.0, "C", 16, None, 2.5, None, 15, "forta", False, None, "obligatoriu", "A", False),
    "cuptor":                (3.5, None, 1.0, "C", 16, None, 2.5, None, 15, "forta", False, "bucatarie", "obligatoriu", "A", False),
    "plita":                 (7.2, 7.5, 1.0, "C", 32, 16, 6.0, 2.5, 15, "forta", True, "bucatarie", "obligatoriu", "A", False),
    "aer_conditionat":       (2.5, None, 0.9, "C", 16, None, 2.5, None, 20, "forta", False, None, "obligatoriu", "A", False),
    "pompa_caldura":         (3.5, 6.0, 0.95, "C", 20, 16, 2.5, 2.5, 20, "forta", True, None, "obligatoriu", "A", True),
    "centrala_termica":      (0.2, None, 0.9, "C", 10, None, 1.5, None, 10, "forta", False, None, "obligatoriu", "A", False),
    "incalzire_electrica":   (3.0, None, 1.0, "C", 16, None, 2.5, None, 20, "forta", False, None, "obligatoriu", "A", True),
    "vehicul_electric":      (7.4, 11.0, 1.0, "C", 40, 20, 4.0, 4.0, 25, "forta", True, "VE", "obligatoriu", "B", True),
    "pompa_apa":             (1.1, None, 0.85, "C", 16, None, 2.5, None, 30, "motor", False, "exterior", "obligatoriu", "A", False),
    "poarta_automata":       (0.5, None, 0.85, "C", 10, None, 1.5, None, 30, "forta", False, "exterior", "obligatoriu", "A", False),
    "sauna":                 (6.0, 9.0, 1.0, "C", 32, 16, 6.0, 2.5, 15, "forta", True, "sauna", "obligatoriu", "A", True),
    "alt_circuit":           (2.0, None, 0.9, "C", 16, None, 2.5, None, 20, "forta", False, None, "obligatoriu", "A", False),
    # r6: alimentarea unui tablou secundar (atelier, garaj, anexă) din TE — DDR-urile 30 mA sunt în tabloul secundar
    "tablou_secundar":       (3.0, 6.0, 0.9, "C", 16, 16, 2.5, 2.5, 30, "tablou", False, None, "in_td", "A", False),
}
# [DECIZIE proiectant 28.10.2026, Î11 — seria actuală]: simultaneitatea receptoarelor generale ale unei locuințe
# după numărul lor; sarcinile continue (VE, pompă de căldură, încălzire electrică, saună) intră cu ks = 1.
# Pc = ks(n_general)·Σ P_general + Σ P_continuu.  (n_max, ks)
# v1.5 (runda 4, practică proiectant): ≤ 3: 0,8 · 4–5: 0,6 · 6–9: 0,4 · 10–15: 0,35 · > 15: 0,3
LOCUINTA_KS_GENERAL = [(3, 0.8), (5, 0.6), (9, 0.4), (15, 0.35), (10 ** 6, 0.3)]
LOCUINTA_COSFI = 0.95            # cosφ mediu al unei locuințe (sarcini preponderent rezistive) pentru Ib general (DECIZIE)
LOCUINTA_I_NEDECLANSARE = 1.13   # SR EN 60898-1: curentul convențional de nedeclanșare 1,13·In — Ib ≤ 1,13·In Q → AV
                                 # (și la branșament NOU) [DECIZIE proiectant 28.10.2026, Î14]
LOCUINTA_CIRCUITE_PE_DDR = 5     # v1.5 DECIZIE: cel mult 5 circuite pe un DDR 30 mA — curentul de scurgere cumulat ≤ 0,3·IΔn
                                 # (SR HD 60364-5-53 art. 531.3.2; ~5 circuite casnice < 9 mA) și pierderea parțială la o
                                 # declanșare (I7-2011); grupă cu un singur circuit → RCBO
LOCUINTA_RCCB_IN_MIN_A = 25      # v1.5: RCCB comerciale uzuale de la 25 A (2P și 4P)
# v1.5: capacitatea de rupere condiționată a RCCB / IS (cu protecția din amonte — MCB / Q branșament / SF gG) [NEVERIFICAT]
LOCUINTA_INC_KA = [6, 10]        # Inc / Icc condiționat uzual (SR EN 61008-1 / SR EN 60947-3 + tabelele producătorului)
# v1.5: centrală termică / poartă automată — receptoare fixe ≤ 10 A: 1,5 mm² Cu admis (I7-2011), nu regula generală 2,5
LOCUINTA_S_MIN_FIX_MM2 = {"centrala_termica": 1.5, "poarta_automata": 1.5}
LOCUINTA_SAUNA_CABLU = ("cablu termorezistent cu izolație de silicon (SiHF / SiF, 180 °C) pe porțiunea din cabina saunei "
                        "(SR HD 60364-7-703)")
LOCUINTA_DEZECHILIBRU_MAX_PCT = 30.0   # DECIZIE: dezechilibru (Imax − Imed)/Imed > 30 % → AVERTISMENT
LOCUINTA_P_CIRCUIT_MAX_KW = 30.0       # peste → valoare neplauzibilă pentru un circuit de locuință (V07)
IS_IN_A = [32, 40, 63, 80, 100, 125]   # întreruptor-separator modular (SR EN 60947-3) [VERIFICAT: cataloage, raport #132]
SPD_T2_LOCUINTA = {"tip": "T2", "In_kA": 20, "Imax_kA": 40, "Up_kV": 1.5, "Uc_V": 275}   # SR EN 61643-11
# v1.6 (runda 4b): protecția de rezervă a SPD-ului T2 (F2) — DECIZIE după fișele uzuale ale SPD T2 In 20 kA
# (rezervă admisă MCB C ≤ 25…32 A sau gG ≤ 32…125 A) [NEVERIFICAT pe fișa SPD-ului ales]: MCB C25, limitat la In Q
# branșament (nu peste protecția din amonte); poli = poli SPD
LOCUINTA_SPD_REZERVA = {"tip": "MCB", "In_A": 40, "curba": "C"}   # [VERIFICAT: SE-SPD p. 388 Imax 40 kA → C40; DEHN 952 110 — raport_b3]
# v1.6 (N2): bugetul de ΔU al coloanei C2 (BMPM/BMPT → TE) — DECIZIE: coloana se mărește întâi până la ≤ 1,5 %, ca
# circuitele finale să rămână la 1,5 / 2,5 mm² (rămân 1,5 % iluminat / 3,5 % forță pentru circuite, I7-2011 art. 5.2.5)
LOCUINTA_DU_COLOANA_BUGET_PCT = 1.5
# v1.6 (P1-4): cel mult 2 circuite de iluminat pe un DDR (un defect stinge cel mult două zone); nivelurile deduse din
# nume (subsol / parter / etaj N / mansardă / exterior) nu se amestecă pe același DDR — DECIZIE
LOCUINTA_ILUMINAT_PE_DDR = 2
# v1.6 (P1-10): Zbuclă OD implicită la punctul de delimitare după zonă — urban 0,30 Ω (OD_ZBUCLA_IMPLICIT_OHM),
# rural (LEA JT lungă, case la capăt de linie) 0,8 Ω: TYIR 3×50+50 pe 500 m ≈ 0,62 Ω + trafo + branșament ≈ 0,75…0,8 Ω
# (raport #3) [DECIZIE proiectant 28.10.2026, Î2 — înlocuiește 0,45 Ω], se confirmă cu OD (ATR)
LOCUINTA_ZB_OD_RURAL_OHM = 0.8
# v1.7 (runda 4c, m-c6): plafonul măririi automate pentru ΔU a circuitelor finale ale locuinței — peste 16 mm² Cu
# problema e coloana / poziția tabloului, nu circuitul (DECIZIE): circuitul rămâne la plafon, V20 BLOCANT cu remedierea
# „mărește coloana / mută tabloul / împarte circuitul”
LOCUINTA_S_MAX_CIRCUIT_DU_MM2 = 16.0
# v1.7 (runda 4c, M-c3): tipul DDR-ului 300 mA din blocul de branșament (BMPM: RCBO tip AC, BMPT: RCCB tip AC, ST 3-JT /
# ST 4-JT) — un DDR tip AC / A / F în amontele unui circuit VE (curent de defect c.c. neted) poate fi „orbit”
# (SR HD 60364-5-53:2015 art. 531.3.2, IEC 60364-7-722:2018 art. 722.531.3.101)
LOCUINTA_DDR_TIPURI = ("AC", "A", "F", "B")
# DDR-ul 300 mA din blocul de măsură al unei LOCUINȚE (BMPM / BMPT), când nu e declarat: tip AC, INSTANTANEU — ca în
# ST 3-JT §4.2.4 l–m (RCBO) / ST 4-JT §4.2.6 i (RCCB) DEER [DECIZIE proiectant 28.10.2026, Î1 — înlocuiește decizia r5
# „tip A, selectiv”; elimină contradicția cu BMPM_RCBO_SELECTIV]. V43 (300/30 mA neselectiv) și regula VE (DDR AC
# „orbit”) apar unde sunt reale, cu remedierea „declarați blocul real” (alimentare.DDR_bransament_tip / _selectiv).
LOCUINTA_DDR_BRANSAMENT_IMPLICIT = {"tip": "AC", "selectiv": False}
# cosφ 1 doar pentru limita blocului (BMPM 40 A ↔ ~9,2 kW). Q presupus (r8, proiectant): calibrul standard ≥ Ib la
# cosφ 0,95 (LOCUINTA_COSFI): 7 kW mono → 40 A; 11 kW tri → 20 A; 15 kW tri → 25 A; 25 kW tri → 40 A
LOCUINTA_Q_DIN_PA_COSFI = 1.0
# r5: încărcarea VE fără DDR declarat — DDR 30 mA tip A + RDC-DD 6 mA c.c. în stație (SR HD 60364-7-722 art. 722.531.3.101),
# compatibil cu un DDR tip A în amonte; tip B se declară pe circuit (DDR: {tip: "B"})
LOCUINTA_VE_DDR_IMPLICIT = "A"

# =====================================================================================================
# 15. Lista valorilor neverificate (afișabilă în memoriul de calcul)
# =====================================================================================================
NEVERIFICAT = {
    # Rămân aici doar pozițiile „NU SE POATE VERIFICA PUBLIC” din verificarea din 28.10.2026 (standard cu plată / document
    # inaccesibil) — valoarea e cea din practica de proiectare, confirmată de verificator ca plauzibilă.
    "TRAFO uk": "4 % ≤ 630 kVA / 6 % ≥ 800 kVA după SR EN 50588-1 (standard cu plată; practică, raport #55)",
    "TRAFO_SIGURANTA_MT_A": "orientativ (SIBA / SM6 / ABB), tabelul producătorului celulei (raport #58)",
    "TC_CONSUM_CONTOR_VA": "1,0 VA majorant (IEC 62053-22) când fișa contorului lipsește (raport #71)",
    "N_PARALEL_MAX_MONOPOLAR": "max. 6 sisteme monopolare în paralel pe fază (DECIZIE; B.52.21 treflă pat perforat 2·De, max. 3 sisteme/pat)",
    "TIP_CABLU C2XAbY": "denumire comercială din ofertele producătorilor RO (ST 80-6 acoperă doar PVC; raport #9)",
    "GE_XD2_IMPLICIT": "tipic 0,10…0,15 (fișe alternatoare, raport #101)",
    "GG_I2T_TOTAL_FACTOR": "I²t total ≈ 2 × I²t prearc (practică, raport #44)",
    "PRIZA_PSI_ZONE / PRIZA_PSI_IMPLICIT": "acoperitor față de tabelul clasic PUE/Karyakin, zona III (ψ_e 1,2–1,5) — [URG] tab. 1.3; "
                                           "de confirmat pe 1.RE-Ip 30-2004 (necitit)",
    "PRIZA_PSI_PLATBANDA_ZONE": "acoperitor față de tabelul clasic PUE/Karyakin, zona III (ψ_pl 1,6–3,2) — [URG] tab. 1.3; "
                                "de confirmat pe 1.RE-Ip 30-2004 (necitit)",
    "PRIZA_L_RACORD_IMPLICIT_M": "5 m racord platbandă → piesa de separație (DECIZIE, depinde de amplasament)",
    "PRIZA_ORE_U": "ore de manoperă orientative pe unitate (DECIZIE; în deviz se folosesc normele de deviz)",
    "PRIZA_R_LIMITA_OHM['pt']": "PT cu priză comună MT/JT „conform ANRE” (Î8): ANRE nu dă o valoare unică (rezultă din "
                                "tratarea neutrului MT și tensiunile de atingere) — 1 Ω păstrat, conservator, de confirmat "
                                "cu OD / ATR (vezi PRIZA_PT_ANRE)",
    "DDR_T_ECHIVALENT_S": "DDR tip S tratat ca temporizare echivalentă 0,15 s (DECIZIE, coerent cu SR EN 61008-1 tab. 1)",
    "LOCUINTA_RECEPTORI": "puteri, curbe, calibre, secțiuni și lungimi implicite pe receptor — practică uzuală (raport #123)",
    "LOCUINTA_INC_KA": "Icc condiționat IS 6/10 kA cu protecția din amonte — tabelele producătorului (raport #129); partea RCCB verificată: 4P + amonte curba D → 4,5 kA [HAG, raport_b3]",
    "LOCUINTA_COSFI": "cosφ mediu 0,95 al unei locuințe (DECIZIE, raport #125)",
        "LOCUINTA_S_MAX_CIRCUIT_DU_MM2": "plafonul de 16 mm² al măririi pentru ΔU a circuitelor finale ale locuinței (DECIZIE)",
    "LOCUINTA_TD_P_CALIBRU": "r8b DECIZIE: circuit casnic al unui tablou secundar dat doar prin calibru → în bilanțul TD "
                             "intră puterea implicită a receptorului (LOCUINTA_RECEPTORI), plafonată la U·In·cosφ; TD "
                             "numai cu receptoare casnice → ks LOCUINTA_KS_GENERAL (ca la TE), altfel ks IEC 61439-2",
    "DENUMIRE_CABLU": "r8b: material / izolație din denumirea comercială (DIN N…/NA…, RO C…/AC…) — de confirmat pe fișă",
}

# Deciziile proiectantului din 28.10.2026 (teste/verificare_norme/raspunsuri_proiectant.md) — afișabile în memoriu.
DECIZII_PROIECTANT_28_10_2026 = {
    "Î1 LOCUINTA_DDR_BRANSAMENT_IMPLICIT / BMPT_RCCB": "DDR 300 mA tip AC instantaneu în BMPM / BMPT (ST 3-JT / ST 4-JT DEER)",
    "Î2 OD_ZBUCLA_IMPLICIT_OHM / LOCUINTA_ZB_OD_RURAL_OHM": "Zbuclă OD implicită urban 0,30 Ω, rural 0,8 Ω",
    "Î3 PROSUMATOR_PI_EXTERNA_KW": "PI externă la P > 27 kW (cerința OD), nu 30 kVA",
    "Î4 DEZECHILIBRU_FAZE_MAX_KVA": "16 A ≈ 3,68 kVA (Ord. ANRE 228/2018 art. 12(3))",
    "Î5 PROSUMATOR_TD_PV_INTOTDEAUNA": "TD-PV separat la toți prosumatorii; întrebare „protecții pe c.c. / c.a.”",
    "Î6 DDR_INVERTOR_DOAR_LA_CERERE": "DDR pe invertor doar declarat / cerut (TT: protecția la defect rămâne)",
    "Î7 OD_IK3MAX_IMPLICIT_KA": "Ik3 OD 25 kA peste tot",
    "Î8 PRIZA_R_LIMITA_OHM": "PT cu priză comună: conform ANRE (vezi PRIZA_PT_ANRE); utilizare și branșament 4 Ω",
    "Î9 TRAFO_GRUPA_CONEXIUNI": "Dyn5",
    "Î10 TRAFO_SN_MAX_SIGURANTE_MT_KVA": "siguranțe MT până la 630 kVA; peste, întrerupător cu 50/51",
    "Î11 LOCUINTA_KS_GENERAL": "seria actuală 0,8 / 0,6 / 0,4 / 0,35 / 0,3",
    "Î12 IZ_CABLU_SOLAR_A": "cabluri solare în mănunchi fără factor de grupare",
    "Î13 PRAG_RACORD_JT_MAX_KVA": "prag PT propriu 400 kVA",
    "Î14 LOCUINTA_I_NEDECLANSARE": "branșament nou, Ib între In și 1,13·In → AVERTISMENT",
    "Î15 CONTOR_DIRECT_*": "contorul pe planșă „furnizat de OD”, fără curent nominal",
}


def _autoverificare():
    """Verificări de consistență rulate la `python3 norme.py`."""
    for k, tab in IZ.items():
        vals = [tab[s] for s in sorted(tab)]
        assert all(b > a for a, b in zip(vals, vals[1:])), f"Iz necrescător în {k}"
    for mat in ("Cu", "Al"):
        for iz in ("PVC", "XLPE"):
            for s in SECTIUNI_MULTIPOLAR[mat]:
                for met in ("C", "D1", "D2", "E"):
                    for n in (2, 3):
                        assert iz_tabel(mat, iz, met, n, s) is not None, (mat, iz, met, n, s)
                        assert iz_tabel(mat, iz, met, 2, s) >= iz_tabel(mat, iz, met, 3, s), (mat, iz, met, s)
    assert sorted(GG_IA_0_4S_A) == sorted(GG_IA_0_4S_A, key=float)
    for in_a in GG_IA_5S_A:
        if in_a in GG_IA_0_4S_A:
            assert GG_IA_0_4S_A[in_a] > GG_IA_5S_A[in_a]
    for in_a, porti in GG_PORTI_A.items():
        if in_a in GG_IA_5S_A:
            assert GG_IA_5S_A[in_a] >= porti[1], f"Ia(5 s) gG {in_a} A sub poarta Imax(5 s)"
    assert ge_sn_minim(60) == 80 and ge_sn_minim(100) == 125
    for sn, (uk, pk, po) in TRAFO.items():
        assert pk / (sn * 1000) < uk / 100
    assert abs(in_trafo_jt(1600) - 2309.4) < 0.1
    assert k_grupare("D1", 2) == 0.85 and k_grupare("E", 12) == 0.72 and k_grupare("D2", 10) == 0.36
    assert k_temperatura("PVC", "E", 32) == 0.94 and k_temperatura("XLPE", "D1", 20) == 1.0
    for tab in (PRIZA_ETA_ELECTROZI, PRIZA_ETA_PLATBANDA):
        for aL, rand in tab.items():
            v = [rand[n] for n in sorted(rand)]
            assert all(b < a for a, b in zip(v, v[1:])), f"η necrescător în n ({aL})"
        for n in tab[1]:
            assert tab[1][n] <= tab[2][n] <= tab[3][n], f"η descrescător în a/L (n = {n})"
    assert abs(priza_eta(PRIZA_ETA_ELECTROZI, 4, 2.0) - 0.84) < 1e-9
    return True


if __name__ == "__main__":
    _autoverificare()
    print(f"norme.py {VERSIUNE}: {len(IZ)} tabele Iz, {len(NEVERIFICAT)} poziții [NEVERIFICAT] — autoverificare OK")
