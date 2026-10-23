"""scurtcircuit.py — curenții de scurtcircuit după SR EN 60909-0 (SPEC §B.13, §B.14, §C.5, §C.6) și contextul de
amonte al unei bare (SPEC §B.1 „context_amonte”).

Toate impedanțele sunt raportate la 0,4 kV, în Ω, ca perechi (R, X).
"""
import math

from . import norme
from .comun import SQRT3, UN, U0, modul

C_MAX = norme.C_MAX
C_MIN = norme.C_MIN


def z_retea_od(ik3_kA):
    """SPEC §B.13, sursa „rețea publică OD”: Z_Q = c_max·Un/(√3·Ik3_OD); X_Q = Z_Q/√(1+0,1²); R_Q = 0,1·X_Q."""
    z = C_MAX * UN / (SQRT3 * ik3_kA * 1000.0)
    x = z / math.sqrt(1 + norme.OD_RX_RAPORT ** 2)
    return (norme.OD_RX_RAPORT * x, x)


def ik3_din_z(z):
    """SPEC §B.13: Ik3max = c_max·Un/(√3·|Z|) [kA]."""
    return C_MAX * UN / (SQRT3 * modul(z)) / 1000.0


def ik1_din_zb(zb):
    """SPEC §B.14: Ik1min = c_min·U0/|Z_bucla| [A]."""
    return C_MIN * U0 / modul(zb)


def trafo(sn_kva, skq_mva=None):
    """SPEC §B.13, sursa „trafo propriu”, și §B.14 (bucla Dyn): impedanțele rețelei MT și ale trafo-ului, K_T,
    Ik3max și Ik1min la bara JT. Returnează un dict cu toate mărimile."""
    skq = skq_mva or norme.MT_SKQ_IMPLICIT_MVA
    uk, pk, p0 = norme.TRAFO[sn_kva]
    sn = sn_kva * 1000.0
    zq = C_MAX * UN ** 2 / (skq * 1e6)
    xq = zq / math.sqrt(1 + norme.MT_RX_RAPORT ** 2)
    rq = norme.MT_RX_RAPORT * xq
    zt = uk / 100.0 * UN ** 2 / sn
    rt = pk * UN ** 2 / sn ** 2
    xt = math.sqrt(zt ** 2 - rt ** 2)
    x_t = xt / (UN ** 2 / sn)
    kt = 0.95 * C_MAX / (1 + 0.6 * x_t)
    zk = (rq + kt * rt, xq + kt * xt)
    zb = (rt + 2.0 / 3.0 * rq, xt + 2.0 / 3.0 * xq)
    return {"Sn_kVA": sn_kva, "In_T_A": norme.in_trafo_jt(sn_kva), "uk_pct": uk, "Pk_W": pk, "P0_W": p0,
            "Z_Q": (rq, xq), "Z_T": (rt, xt), "K_T": kt, "Zk": zk, "Zb": zb, "SkQ_MVA": skq,
            "Ik3max_bara_kA": ik3_din_z(zk), "Ik1min_bara_A": ik1_din_zb(zb)}


def ge_ik3(in_g_A, xd=None):
    """SPEC §B.13 / §C.6 pct. 3: Ik3" = c_max·In_G/x"d (x"d = 0,12 implicit) [A]."""
    return C_MAX * in_g_A / (xd or norme.GE_XD2_IMPLICIT)


def context_od(ik3_kA=None, zb=None, ddr_amonte=True, schema="TN"):
    """SPEC §B.0/§B.1: contextul la punctul de delimitare (rețea publică) — Ik3max OD 25 kA și Zb = 0,18 + j0,09 Ω
    implicite, declarate prin flagurile ik3_implicit / z_implicit."""
    ik3_impl = ik3_kA is None
    z_impl = zb is None
    ik3 = norme.OD_IK3MAX_IMPLICIT_KA if ik3_impl else float(ik3_kA)
    if z_impl:
        zbv = tuple(norme.OD_ZBUCLA_IMPLICIT_OHM)
    elif isinstance(zb, (int, float)):
        # M2 (v1.2): modul |Z| → (R, X) cu raportul R/X al valorii implicite
        r0, x0 = norme.OD_ZBUCLA_IMPLICIT_OHM
        m0 = math.hypot(r0, x0)
        zbv = (float(zb) * r0 / m0, float(zb) * x0 / m0)
    else:
        zbv = (float(zb[0]), float(zb[1]))
    zq = z_retea_od(ik3)
    ajustat = False
    if z_impl and not ik3_impl:
        # M9 (v1.2): Zb implicit trebuie să fie coerent cu Ik3 dat — bucla fază–PE ≥ 2·Z_Q pe fiecare componentă
        # (dus + întors pe aceeași rețea), astfel încât Ik1min ≤ Ik3max pe orice ramură din aval
        z2 = (max(zbv[0], 2.0 * zq[0]), max(zbv[1], 2.0 * zq[1]))
        ajustat = z2 != zbv
        zbv = z2
    return {"Zq": zq, "Zb": zbv, "Ik3_kA": ik3_din_z(zq), "dU_pct": 0.0, "origine": "retea_publica",
            "z_implicit": z_impl, "ik3_implicit": ik3_impl, "ddr_amonte": ddr_amonte, "ddr_ramura": None,
            "are_aval": False, "schema": schema, "zb_ajustat": ajustat}


def context_pt(t):
    """SPEC §C.5 pct. 4, §C.5 pct. 8: contextul barei TGJT a unui PT propriu (origine „pt_propriu”, impedanțe cunoscute)."""
    return {"Zq": t["Zk"], "Zb": t["Zb"], "Ik3_kA": t["Ik3max_bara_kA"], "dU_pct": 0.0, "origine": "pt_propriu",
            "z_implicit": False, "ik3_implicit": False, "ddr_amonte": False, "ddr_ramura": None,
            "are_aval": False, "schema": "TN"}


def z_capat(zq, r20_faza, L_m, n):
    """SPEC §B.13, de-a lungul cablului (R la 20 °C): Z_capăt = Z_origine + (R20·L/n, X'·L/n)."""
    Lk = L_m / 1000.0
    return (zq[0] + r20_faza * Lk / n, zq[1] + norme.X_CABLU_OHM_KM * Lk / n)


def zb_capat(zb, r20_faza, f, r20_pe, f_pe, L_m, n):
    """SPEC §B.14: Z_bucla,capăt = Z_bucla,origine + ((R20_fază·f + R20_PE·f_PE)·L/n, 2·X'·L/n)."""
    Lk = L_m / 1000.0
    return (zb[0] + (r20_faza * f + r20_pe * f_pe) * Lk / n, zb[1] + 2.0 * norme.X_CABLU_OHM_KM * Lk / n)
