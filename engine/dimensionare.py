"""Dimensionare simplificată JT (fază PT): curent de calcul, aparat de protecție, secțiune cablu, cădere de tensiune.
Tabele orientative după I7-2011 / SR HD 60364-5-52 (metode de pozare D = în pământ, E = în aer / pe pat de cabluri),
cabluri cu izolație PVC (ACYABY / CYABY / CYY-F) sau XLPE (AC2XABY / N2XY). Valorile finale se verifică la PT + DDE."""
import math

STD_IN = [6, 10, 16, 20, 25, 32, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600]
SECTIUNI = [1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240, 300]

# Iz [A] pentru 3 conductoare încărcate, 30 °C aer / 20 °C sol — orientativ
IZ = {
 ("Cu", "PVC", "D"):  [22, 29, 38, 47, 63, 81, 104, 125, 148, 183, 216, 246, 278, 312, 361, 408],
 ("Cu", "PVC", "E"):  [18.5, 25, 34, 43, 60, 80, 101, 126, 153, 196, 238, 276, 319, 364, 430, 497],
 ("Cu", "XLPE", "D"): [26, 34, 44, 56, 73, 95, 121, 146, 173, 213, 252, 287, 324, 363, 419, 474],
 ("Cu", "XLPE", "E"): [23, 32, 42, 54, 75, 100, 127, 158, 192, 246, 298, 346, 399, 456, 538, 621],
 ("Al", "PVC", "D"):  [None, None, None, None, 49, 63, 81, 97, 115, 143, 169, 193, 217, 244, 283, 319],
 ("Al", "PVC", "E"):  [None, None, None, None, 46, 62, 78, 97, 118, 151, 183, 212, 245, 280, 330, 381],
 ("Al", "XLPE", "D"): [None, None, None, None, 57, 74, 94, 114, 135, 166, 196, 224, 252, 283, 329, 371],
 ("Al", "XLPE", "E"): [None, None, None, None, 58, 77, 97, 120, 146, 187, 227, 263, 304, 347, 409, 471],
}
RHO = {"Cu": 0.0225, "Al": 0.036}          # Ω·mm²/m la temperatura de regim (~70 °C)
X_KM = 0.08                                 # Ω/km reactanță cablu JT
TIP_CABLU = {("Al", "PVC"): "ACYABY", ("Al", "XLPE"): "AC2XABY", ("Cu", "PVC"): "CYABY", ("Cu", "XLPE"): "N2XY"}


def std_up(v, lst):
    for x in lst:
        if x >= v: return x
    return lst[-1]


def dimensioneaza(Pa_kW, U=400, cosfi=0.92, L_m=50, material="Al", izolatie="PVC", pozare="D",
                  k_simult=1.0, dU_max=3.0, k_corectie=1.0, tip_protectie="mccb", trifazat=True):
    """întoarce un dict cu Ib, In, Ir, secțiunea, Iz, ΔU și textele pentru schemă/listă"""
    Pa = Pa_kW * 1000 * k_simult
    Ib = Pa / (math.sqrt(3) * U * cosfi) if trifazat else Pa / (230 * cosfi)
    In = std_up(Ib, STD_IN)
    # MCCB: In cu Ir reglabil 0,8…1 → alegem In astfel încât Ib ≤ 0,95 In; fuzibil gG: In ≥ 1,1 Ib
    if tip_protectie == "mccb":
        In = std_up(Ib / 0.95, STD_IN)
        Ir = max(0.8, min(1.0, math.ceil(Ib / In * 20) / 20))   # pas 0,05
        I2 = 1.3 * Ir * In
    else:
        In = std_up(Ib * 1.1, STD_IN)
        Ir, I2 = 1.0, 1.6 * In
    tabel = IZ[(material, izolatie, pozare)]
    sectiune = Iz = None
    for s, iz in zip(SECTIUNI, tabel):
        if iz is None: continue
        if iz * k_corectie >= max(In * Ir if tip_protectie == "mccb" else In, Ib) and (I2 <= 1.45 * iz * k_corectie):
            sectiune, Iz = s, iz; break
    if sectiune is None: sectiune, Iz = SECTIUNI[-1], tabel[-1]
    # cădere de tensiune (trifazat): ΔU = √3·Ib·L·(R cosφ + X sinφ)
    sinfi = math.sqrt(1 - cosfi ** 2)
    while True:
        R = RHO[material] * L_m / sectiune; X = X_KM * L_m / 1000
        dU = (math.sqrt(3) if trifazat else 2) * Ib * (R * cosfi + X * sinfi)
        dU_pct = dU / U * 100
        if dU_pct <= dU_max or sectiune == SECTIUNI[-1]: break
        i = SECTIUNI.index(sectiune); sectiune = SECTIUNI[i + 1]; Iz = tabel[i + 1] or Iz
    neutru = sectiune if sectiune <= 16 else std_up(sectiune / 2, SECTIUNI)
    tip = TIP_CABLU[(material, izolatie)]
    cablu = f"{tip} 3×{sectiune:g}+{neutru:g} mm² {material}" if trifazat else f"{tip} 3×{sectiune:g} mm² {material}"
    Ik_min_info = f"Icu ≥ {'36' if In <= 250 else '50'} kA"
    return {
        "Pa_kW": Pa_kW, "Ib": round(Ib, 1), "In": In, "Ir": Ir, "Ir_A": round(In * Ir), "I2": round(I2),
        "sectiune": sectiune, "neutru": neutru, "Iz": Iz, "Iz_corectat": round(Iz * k_corectie), "dU_pct": round(dU_pct, 2), "L_m": L_m,
        "cablu": cablu, "material": material, "izolatie": izolatie, "pozare": pozare, "tip_protectie": tip_protectie,
        "spec_aparat": [f"{'4P' if trifazat else '2P'} · {In} A", f"Ir = {Ir:g} In ≈ {round(In*Ir)} A"] if tip_protectie == "mccb" else [f"3P · {In} A gG"],
        "lista_aparat": [f"Întreruptor automat MCCB {'4P' if trifazat else '2P'} In {In} A, {Ik_min_info}, declanșator reglabil Ir = 0,8…1 In"
                         if tip_protectie == "mccb" else f"Separator cu siguranțe fuzibile MPR {In} A gG, 3P",
                         f"Ib = {Ib:.1f} A · Ir ≈ {round(In*Ir)} A · cablu {cablu}, L ≈ {L_m} m, Iz = {Iz} A, ΔU = {dU_pct:.2f} %"],
        "cablu_text": f"{cablu} · L ≈ {L_m} m",
    }


def tc_pentru(Ib):
    """raport TC standard pentru măsurare semidirectă"""
    for r in (100, 150, 200, 250, 300, 400, 500, 600, 800, 1000, 1200, 1500):
        if r >= Ib * 1.1: return f"{r}/5 A"
    return "2000/5 A"
