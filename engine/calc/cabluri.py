"""cabluri.py — curentul admisibil corectat (SPEC §B.7), căutarea secțiunii și cablurile în paralel (§B.8, §B.9),
neutrul (§B.10), conductorul PE (§B.11) și căderea de tensiune (§B.12)."""
import math

from . import norme
from .comun import ge, gt, SQRT3, UN, U0


class InAfaraTabelelor(Exception):
    """Pozare în afara tabelelor B.52.x (SPEC §B.7.2 → V10 BLOCANT)."""

    def __init__(self, parametru, tabel):
        """Reține parametrul și tabelul depășit, pentru mesajul V10 (SPEC §B.7.2, §D)."""
        super().__init__(parametru)
        self.parametru = parametru
        self.tabel = tabel


def theta_implicit(metoda):
    """SPEC §B.0: temperatura de referință — aer 30 °C, sol 20 °C."""
    return 20.0 if metoda in norme.METODE_IN_PAMANT else 30.0


def factori(izolatie, metoda, theta, rho_sol, n_circuite, distanta="atingere", aranjament=None):
    """SPEC §B.7.2: kθ (B.52.14/B.52.15), ksol (B.52.16, doar D1/D2), kgrup (B.52.17–B.52.19) pentru n_circuite
    = n_paralel + n_alte. Valorile intermediare iau rândul imediat superior; în afara tabelelor → InAfaraTabelelor."""
    try:
        kt = norme.k_temperatura(izolatie, metoda, theta)
    except ValueError:
        raise InAfaraTabelelor(f"temperatura {theta} °C", "B.52.14/B.52.15")
    try:
        ks = norme.k_rezistivitate_sol(metoda, rho_sol)
    except ValueError:
        raise InAfaraTabelelor(f"rezistivitatea termică a solului {rho_sol} K·m/W", "B.52.16")
    try:
        kg = norme.k_grupare(metoda, n_circuite, distanta, aranjament)
    except ValueError:
        raise InAfaraTabelelor(f"{n_circuite} circuite grupate", "B.52.17–B.52.19")
    return kt, ks, kg


def n_incarcate(retea):
    """SPEC §B.7.1: 3 conductoare încărcate la trifazat, 2 la monofazat."""
    return 2 if retea == "mono" else 3


def s_min(material, receptor, metoda):
    """SPEC §B.8, secțiunile minime: Cu iluminat 1,5; prize/forță/motor/invertor 2,5; coloane spre tablouri 4;
    orice cablu în pământ ≥ 6 (DECIZIE); Al ≥ 16."""
    if material == "Al":
        return norme.S_MIN_AL
    s = norme.S_MIN_CU.get(receptor if receptor != "pcs" else "invertor", 2.5)
    if metoda in norme.METODE_IN_PAMANT:
        s = max(s, norme.S_MIN_CU["ingropat"])
    return s


def metoda_implicita(cab, valoare):
    """Setează metoda de pozare implicită și marchează că NU a fost cerută de utilizator (v1.2 R3, N3-C1)."""
    if cab.get("metoda") is None:
        cab["metoda"] = valoare
        cab["metoda_implicit"] = True
    return cab["metoda"]


def monopolar(c):
    """True pentru cablurile monopolare: metoda F (aer) sau sisteme monopolare în pământ (D1/D2) — v1.2 R2/R3."""
    return bool(c.get("monopolar")) or str(c.get("metoda", "")).startswith("F")


def sectiuni(c):
    """Secțiunile disponibile pentru configurația cablului: multipolar (≤ 240) sau monopolar (25…300 mm²)."""
    return norme.SECTIUNI_MONOPOLAR if monopolar(c) else norme.SECTIUNI_MULTIPOLAR[c["material"]]


def n_max(c):
    """Numărul maxim de cabluri / sisteme în paralel: 4 multipolare (§B.8), 6 sisteme monopolare (v1.2 R2)."""
    return norme.N_PARALEL_MAX_MONOPOLAR if monopolar(c) else norme.N_PARALEL_MAX_MULTIPOLAR


def iz_corectat(c, n, S):
    """SPEC §B.7: Iz' = n·Iz·kθ·kgrup·ksol. `c` este configurația cablului (material, izolatie, metoda, retea, theta,
    rho_sol, n_alte, distanta, aranjament). Returnează (Iz_tabel, k_total, Iz')."""
    iz = norme.iz_tabel(c["material"], c["izolatie"], c["metoda"], n_incarcate(c["retea"]), S)
    kt, ks, kg = factori(c["izolatie"], c["metoda"], c["theta"], c["rho_sol"], n + c["n_alte"],
                         c["distanta"], c.get("aranjament"))
    if str(c["metoda"]).startswith("F"):
        # sisteme în treflă pe pat perforat, distanțate ≥ 2·De (B.52.21) — v1.2 R2
        nt = n + c["n_alte"]
        if nt > max(norme.K_GRUP_F_DISTANTAT):
            raise InAfaraTabelelor(f"{nt} sisteme monopolare grupate", "B.52.21")
        kg = norme.K_GRUP_F_DISTANTAT[nt]
    k = kt * ks * kg
    if iz is None:
        raise InAfaraTabelelor(f"secțiunea {S} mm² {c['material']} {c['izolatie']} metoda {c['metoda']}", "B.52.x")
    return iz, k, n * iz * k


def cauta(c, iz_min, smin):
    """SPEC §B.8, algoritmul de căutare: pentru n = 1…4, S crescător ≥ S_min: prima (n, S) cu n·Iz(S)·k ≥ Iz_min."""
    for n in range(1, n_max(c) + 1):
        for S in sectiuni(c):
            if S < smin - 1e-9:
                continue
            _, _, izp = iz_corectat(c, n, S)
            if ge(izp, iz_min):
                return n, S
    return None


def cea_mai_mica_s(c, n, iz_min, smin):
    """SPEC §B.12: „S = cea mai mică secțiune care satisface Iz_min la n” (pentru trecerea la n+1 cabluri)."""
    for S in sectiuni(c):
        if S < smin - 1e-9:
            continue
        if ge(iz_corectat(c, n, S)[2], iz_min):
            return S
    return None


def r_regim(material, izolatie, S):
    """SPEC §B.12: R' = R20(S)·[1 + α·(θ − 20)], θ = 70 °C PVC / 90 °C XLPE [Ω/km]."""
    return norme.r_la_temperatura(norme.R20_OHM_KM[material][float(S)], material, norme.THETA_MAX_C[izolatie])


def du_pct(retea, ib, L_m, material, izolatie, S, n, cosfi):
    """SPEC §B.12: ΔU% = 100·√3·Ib·L·(R'cosφ + X'sinφ)/400 (tri) sau 100·2·Ib·L·(…)/230 (mono); R', X' împărțite la n."""
    r = r_regim(material, izolatie, S) / n
    x = norme.X_CABLU_OHM_KM / n
    sinfi = math.sqrt(max(0.0, 1 - cosfi ** 2))
    Lk = L_m / 1000.0
    if retea == "mono":
        return 100.0 * 2 * ib * Lk * (r * cosfi + x * sinfi) / norme.u_0()
    return 100.0 * SQRT3 * ib * Lk * (r * cosfi + x * sinfi) / norme.u_n()


def sectiune_std_minima(valoare, minim=0.0):
    """Cea mai mică secțiune standard (SECTIUNI_STD) ≥ max(valoare, minim) (SPEC §B.11, §B.17)."""
    v = max(valoare, minim)
    for s in norme.SECTIUNI_STD:
        if ge(s, v):
            return s
    return None


def neutru_redus_permis(material, S, receptor, h3_pct):
    """SPEC §B.10 pct. 4: N redus permis numai dacă h3 declarat ≤ 15 %, receptorul nu e invertor / iluminat (LED) /
    VFD, S > 16 Cu / > 25 Al, N ≥ 16 Cu / ≥ 25 Al și combinația există. Returnează (N | None, motiv)."""
    if h3_pct is None:
        return None, "armonica 3 nedeclarată ≤ 15 %"
    if h3_pct > 15:
        return None, f"armonica 3 = {h3_pct} % > 15 %"
    if receptor in ("invertor", "pcs", "iluminat"):
        return None, "receptor invertor / iluminat LED / VFD"
    if not gt(S, norme.N_REDUS_S_FAZA_MIN[material]):
        return None, f"S ≤ {int(norme.N_REDUS_S_FAZA_MIN[material])} mm² {material}"
    N = norme.COMBINATII_N_REDUS.get(float(S))
    if N is None:
        return None, "combinație nefabricată"
    if N < norme.N_REDUS_S_N_MIN[material] - 1e-9:
        return None, f"N < {int(norme.N_REDUS_S_N_MIN[material])} mm² {material}"
    return N, ""


def compune_neutru(material, S, retea, receptor, h3_pct, N_fortat=None):
    """SPEC §B.10: secțiunea neutrului. Monofazat N = S; implicit N = S; redus doar cu condițiile pct. 4.
    Returnează (N, eroare_V25 | None)."""
    if retea == "mono":
        return S, None
    if N_fortat is not None:
        if N_fortat >= S - 1e-9:
            return float(N_fortat), None
        Nperm, motiv = neutru_redus_permis(material, S, receptor, h3_pct)
        if Nperm is not None and N_fortat >= Nperm - 1e-9:
            return float(N_fortat), None
        return float(N_fortat), motiv or "combinație nepermisă"
    if material == "Cu" and S <= 35:
        return S, None
    Nr, _ = neutru_redus_permis(material, S, receptor, h3_pct)
    return (Nr if Nr is not None else S), None


def s_pe_tabel(material, izolatie, n, S, pe_cupru_separat):
    """SPEC §B.11, tab. 54.2 pe S_tot = n·S; dacă faza e Al și PE e Cu: S_tab·k_faza(Al, izolație)/143."""
    s_tab = norme.s_pe_tabel(n * S)
    if material == "Al" and pe_cupru_separat:
        s_tab = s_tab * norme.K_FAZA[("Al", izolatie)] / norme.K_PE_SEPARAT[("Cu", "PVC")]
    return s_tab


def pe_in_cablu(material, S, retea):
    """SPEC §B.11, compunere: monofazat → PE în cablu (3×S); trifazat Cu S ≤ 35 → 5×S; altfel PE separat FY."""
    return retea == "mono" or (material == "Cu" and S <= 35 + 1e-9)


def compune_pe(material, izolatie, n, S, retea):
    """SPEC §B.11: (S_PE pe cablu, loc 'cablu'|'separat', S_tab) — PE separat = cea mai mică secțiune standard
    ≥ max(S_tab/n; 4 mm²)."""
    if pe_in_cablu(material, S, retea):
        return float(S), "cablu", s_pe_tabel(material, izolatie, n, S, False)
    s_tab = s_pe_tabel(material, izolatie, n, S, True)
    s_pe = sectiune_std_minima(s_tab / n, norme.S_MIN_PE_SEPARAT["neprotejat"])
    return s_pe, "separat", s_tab


def k_pe(material, izolatie, loc):
    """SPEC §B.11, tabelul k: PE în cablu → k după tab. A.54.3 (= k fază); PE separat FY Cu PVC → 143."""
    if loc in ("cablu", "PEN"):
        return norme.K_PE_IN_CABLU[(material, izolatie)]
    return norme.K_PE_SEPARAT[("Cu", "PVC")]


def r20_pe(material, loc, s_pe):
    """Rezistența la 20 °C a conductorului PE (în cablu: materialul fazei; separat: FY Cu) [Ω/km] (SPEC §B.14)."""
    mat = material if loc in ("cablu", "PEN") else "Cu"
    tab = norme.R20_OHM_KM[mat]
    if float(s_pe) in tab:
        return tab[float(s_pe)]
    return norme.RHO20[mat] * 1000.0 / s_pe
