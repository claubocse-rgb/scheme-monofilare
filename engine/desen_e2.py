"""E2 — planșe desenate direct pe canvas (convențiile proiectantului, teste/reale/raport.md):

* `stringuri`      — IE 07.x: fiecare string „SIR k” desenat individual (primul și ultimul modul + „× N”), cablul solar
                     cu secțiunea, siguranțele gPV pe string, separatorul pe MPPT, intrările MPPT pe conturul
                     invertorului (caseta „DATA”), ieșirea c.a.; „tipic pentru INV-1 … INV-N” la invertoarele identice;
* `te_multifilar`  — IE 09: tabloul de interfață (TE-CEF / TEG) desenat multifilar: L1 / L2 / L3 / N / PE ca bare
                     separate colorate, întreruptorul de interfață motorizat (polii, motorul, bobina BD, contactul de
                     semnalizare), releul PI cu bornele lui (L1–L3, N, A1 / A2, Y1–Y3), UPS-ul releului, siguranțele
                     circuitelor releului, TC-urile contorului / smart meter-ului, SPD, plecările spre tablourile
                     intermediare și caseta fiecărui invertor (fiecare invertor cu eticheta lui), magistrala RS485;
* `curbe`          — curbele timp-curent ale protecțiilor înseriate (selectivitate vizuală, log-log);
* etichetele de tablou (A4, benzi pe module DIN de 18 mm) și pagina „schemă de tablou” pentru ușă — în planse.py.

Un desen special primește obiectul `Layout` (rama, notele, legenda, tabelele și cartușul rămân ale lui) și desenează
schema în zona ei: x ∈ [15, L.x_right − 2], y ∈ [note_top + 6, h − 15].
"""
import math

from .canvas import LAYERS, DASH_SVG, BlockRef, Canvas, Line, Polyline, Rect, Solid, Text, text_width
from . import symbols as S

# ---------------------------------------------------------------- straturi noi (culorile conductoarelor, curbe)
CULORI_60445 = {"L1": "#8b4513", "L2": "#000", "L3": "#7f7f7f"}       # SR EN 60445: maro / negru / gri
CULORI_NEGRU = {"L1": "#000", "L2": "#000", "L3": "#000"}             # cum apar fazele în planșele proiectantului
STRATURI_NOI = {
    # nume: (ACI, lineweight, linetype, culoare svg)
    "COND_L1": (34, 50, "CONTINUOUS", CULORI_60445["L1"]),
    "COND_L2": (7, 50, "CONTINUOUS", CULORI_60445["L2"]),
    "COND_L3": (8, 50, "CONTINUOUS", CULORI_60445["L3"]),
    "COND_N": (5, 50, "CONTINUOUS", "#1a5fb4"),
    "COND_PE": (3, 50, "CONTINUOUS", "#1a9f37"),
    "COND_PE_G": (2, 35, "DASHED", "#e5c100"),         # dunga galbenă peste verde (verde-galben)
    "COND_CMD": (1, 25, "CONTINUOUS", "#c00"),          # conductoarele de comandă / alimentare releu (roșu, plin)
    "TABLOU": (6, 35, "CONTINUOUS", "#c000c0"),          # chenarul colorat al tabloului (magenta)
    "CURBA_GRID": (8, 13, "CONTINUOUS", "#c8c8c8"),
    "CURBA_AX": (8, 25, "CONTINUOUS", "#555"),
    "CURBA_1": (1, 50, "CONTINUOUS", "#d01c1c"),
    "CURBA_2": (5, 50, "CONTINUOUS", "#1a5fb4"),
    "CURBA_3": (3, 50, "CONTINUOUS", "#1a8f37"),
    "CURBA_4": (30, 50, "CONTINUOUS", "#e07000"),
    "CURBA_5": (6, 50, "CONTINUOUS", "#a01aa0"),
    "CURBA_6": (4, 50, "CONTINUOUS", "#0096b4"),
    "CURBA_IK": (8, 25, "DASHED", "#555"),
    "FILIGRAN": (9, 13, "CONTINUOUS", "#999"),            # filigranul variantei gratuite (strat separat în DXF)
}
for _k, _v in STRATURI_NOI.items():
    LAYERS.setdefault(_k, _v)
STRATURI_RGB = set(STRATURI_NOI)          # render_dxf: culoarea exactă (true color) pe aceste straturi

NB = " "
PCT = "·"


def _f(x, z=1):
    from .calc.texte import fmt_ro
    if x is None:
        return "—"
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return fmt_ro(x, z)
    return str(x)


def fit(s, h, maxw, bold=False, hmin=0.9):
    """corpul de literă (≤ h) cu care textul încape pe lățimea maxw"""
    if not s:
        return h
    return max(hmin, min(h, h * maxw / max(text_width(s, h, bold) * 1.04, 0.1)))


def deseneaza(L, sp):
    fn = {"stringuri": stringuri, "te_multifilar": te_multifilar, "curbe": curbe}.get(sp.get("tip"))
    if fn is None:
        return
    X1, X2 = 15.0, L.x_right - 2
    Y1, Y2 = (L.note_top + 6 if L.m.get("note") else 15.0), L.h - 15
    fn(L, sp, (X1, Y1, X2, Y2))


def _faze(sp):
    cul = CULORI_NEGRU if sp.get("culori_faze") in ("negru", "proiectant") else CULORI_60445
    for k in ("L1", "L2", "L3"):
        a, lw, lt, _ = LAYERS["COND_" + k]
        LAYERS["COND_" + k] = (a if cul is CULORI_60445 else 7, lw, lt, cul[k])
    if sp.get("mono"):
        return [("L", "COND_L1"), ("N", "COND_N"), ("PE", "COND_PE")]
    return [("L1", "COND_L1"), ("L2", "COND_L2"), ("L3", "COND_L3"), ("N", "COND_N"), ("PE", "COND_PE")]


def _cond(c, a, b, lay):
    """conductor colorat; PE = verde cu dungă galbenă"""
    c.line(a, b, lay)
    if lay == "COND_PE":
        c.line(a, b, "COND_PE_G")


def _pamant(c, x, y, eticheta="Rp ≤ 1 Ω", w=3.2, jos=False):
    for i, f in enumerate((1.0, 2 / 3, 1 / 3)):
        c.line((x - w * f, y - 1.2 * i), (x + w * f, y - 1.2 * i), "SIMBOL")
    if eticheta and jos:
        c.text(x - w, y - 5.2, eticheta, 1.8, layer="TEXT_GRI")
    elif eticheta:
        c.text(x + w + 1.2, y - 2.0, eticheta, 1.8, layer="TEXT_GRI")


def _bloc(c, nume, x, y, prims, ref="", spec="", tip=""):
    br = BlockRef(nume, (x, y), {"REF": ref, "SPEC": spec, "TIP": tip}, prims)
    c.add(br)
    return br


def _contact(x, y, mark="x", h=8.0):
    """contact de forță vertical (un pol), centrat în (x, y), lung h; marcaj sus"""
    p = []
    yf, yh = h / 2 - 2.0, -h / 2 + 2.0
    p.append(Line((0, h / 2), (0, yf), "FORTA"))
    if mark == "x":
        p += [Line((-1.1, yf - 1.1), (1.1, yf + 1.1)), Line((1.1, yf - 1.1), (-1.1, yf + 1.1))]
    elif mark == "fuz":
        p += [Line((-1.2, yf), (1.2, yf))]
    else:
        p.append(Line((-1.2, yf), (1.2, yf)))
    p.append(Line((0, yh), (2.6, yf - 0.2), "FORTA"))
    if mark == "fuz":       # separator cu fuzibil: fuzibilul pe cuțit
        p.append(Polyline([(0.4, yh + 1.1), (2.0, yf - 1.5), (2.9, yf - 1.1), (1.3, yh + 1.5)], "SIMBOL", True))
    p.append(Line((0, yh), (0, -h / 2), "FORTA"))
    return p


def _fuzibil_v(c, x, y, lay="SIMBOL", h=4.0, w=1.6):
    c.rect(x - w / 2, y - h / 2, w, h, "SIMBOL", fill="#fff")
    c.line((x, y - h / 2), (x, y + h / 2), "SIMBOL")


# ================================================================ IE 07 — stringurile
def date_stringuri(b, tipic=None):
    """datele planșei IE 07.k din intrarea `b` a modelului (ramura completă a unui invertor); None dacă stringurile
    nu sunt descrise (numărul de module / stringuri lipsă) — atunci planșa rămâne bloc c.c. generic"""
    ap = b.get("aparate") or []
    pv = next((a for a in ap if a.get("tip") == "string_pv"), None)
    inv = next((a for a in ap if a.get("tip") == "invertor"), None)
    if pv is None or inv is None:
        return None
    par = pv.get("param") or {}
    nm, nsp = par.get("n_module"), par.get("n_stringuri_paralel")
    if not nm or not nsp:
        return None
    pi = inv.get("param") or {}
    n_mppt = int(par.get("n_MPPT") or pi.get("nr_MPPT") or 1)
    if not par.get("n_MPPT"):
        n_mppt = 1 if not pi.get("nr_MPPT") else min(int(pi["nr_MPPT"]), max(1, int(par.get("n_MPPT") or 1)))
    gpv = next((a for a in ap if a.get("tip") == "gpv"), None)
    sep = next((a for a in ap if a.get("tip") == "separator_cc"), None)
    lat = {l.get("tip") + ":" + str(l.get("eticheta") or ""): l for l in (sep or {}).get("laterale") or []}
    spd = next((l for l in (sep or {}).get("laterale") or [] if l.get("tip") == "spd_cc"), None)
    sb = next((l for l in (sep or {}).get("laterale") or [] if l.get("eticheta") == "SB"), None)
    rs = any(l.get("eticheta") == "RS485" for l in inv.get("laterale") or [])
    cab = (b.get("cablu") or {}).get("text") or "H1Z2Z2-K"
    import re
    msec = re.search(r"(\d+(?:[.,]\d+)?)\s*mm²", cab)
    sec = msec.group(1) if msec else None
    mod = " ".join(str(x) for x in (par.get("producator"), par.get("model")) if x)
    return {"n_module": int(nm), "n_par": int(nsp), "n_mppt": n_mppt, "modul": mod, "Pmax_W": par.get("Pmax_W"),
            "kWp": par.get("kWp"), "pv_ref": pv.get("ref", ""), "inv_ref": inv.get("ref", ""),
            "inv_model": " ".join(str(x) for x in (pi.get("producator"), pi.get("model")) if x),
            "inv_Pn": pi.get("Pn_kW"), "inv_Iac": pi.get("Iac_max_A"), "mono": pi.get("retea") == "mono",
            "gpv_In": ((gpv or {}).get("param") or {}).get("In_A"), "gpv": gpv is not None, "gpv_ref": (gpv or {}).get("ref", ""),
            "sep_ref": (sep or {}).get("ref", ""), "sep_spec": (sep or {}).get("spec") or [],
            "sep_integrat": "integrat" in " ".join((sep or {}).get("spec") or []),
            "spd_ref": (spd or {}).get("ref", ""), "spd_spec": (spd or {}).get("spec") or [],
            "sb_ref": (sb or {}).get("ref", ""), "rs485": rs, "cablu_cc": cab, "sectiune_cc": sec,
            "cablu_ca": dict(b.get("cablu_ca") or {}), "tipic": tipic}


def _modul(c, x, y, w=7.0, h=5.0):
    """simbolul unui modul PV (dreptunghi cu diagonală și săgeți de lumină)"""
    c.rect(x, y - h / 2, w, h, "SIMBOL", fill="#fff")
    c.line((x, y - h / 2), (x + w, y + h / 2), "SIMBOL")
    c.line((x + w - 2.2, y - h / 2 + 0.6), (x + w - 0.6, y - h / 2 + 0.6), "SIMBOL")


def stringuri(L, sp, zona):
    c = L.c
    d = sp["date"]
    X1, Y1, X2, Y2 = zona
    n_mppt, n_par, nm = d["n_mppt"], d["n_par"], d["n_module"]
    n_str = n_mppt * n_par
    tipic_par = n_str > 26                   # prea multe stringuri: câte un string tipic pe MPPT (× n_par)
    randuri = []                             # (mppt, k_string, eticheta)
    k = 0
    for m_ in range(n_mppt):
        for j in range(n_par):
            k += 1
            if tipic_par and j > 0:
                continue
            randuri.append((m_, k, f"SIR {k}" if not tipic_par else f"SIR {k}…{k + n_par - 1}"))
    n_r = len(randuri)
    y_top, y_bot = Y2 - 22, Y1 + 30
    gap_m = 3.0 if n_mppt > 1 else 0.0
    pas = min(16.0, max(5.2, (y_top - y_bot - gap_m * (n_mppt - 1)) / max(n_r, 1)))
    h_mod = min(5.0, pas * 0.62)
    # coloanele
    x_sir, x_m1 = X1 + 2, X1 + 17
    x_m2 = x_m1 + 22
    x_cab = x_m2 + 9
    x_sb1 = x_cab + 44
    x_fz = x_sb1 + 8
    x_join = x_fz + 9
    x_sep = x_join + 9
    x_sb2 = x_sep + 12
    x_inv1 = x_sb2 + 16
    w_inv = 46.0
    x_inv2 = min(x_inv1 + w_inv, X2 - 30)
    # titlul invertorului
    tit = d["inv_ref"] if not d.get("tipic") else d["tipic"]["titlu"]
    xc_inv = (x_inv1 + x_inv2) / 2
    ys = []
    y = y_top
    for i, (m_, k_, et) in enumerate(randuri):
        if i and randuri[i - 1][0] != m_:
            y -= gap_m
        ys.append(y - pas / 2)
        y -= pas
    y_last = ys[-1] if ys else y_top
    # invertorul: dreptunghi pe toată înălțimea intrărilor MPPT
    mp_y = []
    for m_ in range(n_mppt):
        yy = [ys[i] for i, r in enumerate(randuri) if r[0] == m_]
        mp_y.append(sum(yy) / len(yy))
    iy2 = max(mp_y) + max(10.0, pas)
    iy1 = min(mp_y) - max(16.0, pas)
    c.rect(x_inv1, iy1, x_inv2 - x_inv1, iy2 - iy1, "SIMBOL", fill="#fff")
    c.line((x_inv1, iy1), (x_inv2, iy2), "SIMBOL")
    c.text(x_inv1 + 8, iy2 - 7.5, "DC", 5.0, True, align="middle")
    c.text(x_inv2 - 8, iy1 + 9.5, "AC", 5.0, True, align="middle")
    c.rect(x_inv2 - 16, iy1, 16, 5.5, "SIMBOL")
    c.text(x_inv2 - 8, iy1 + 1.6, "DATA", 2.6, True, align="middle")
    c.text(xc_inv, iy2 + 9.5, tit, fit(tit, 4.4, 70, True), True, align="middle")
    sub = " · ".join(s for s in (d["inv_model"], (f"Pn {_f(d['inv_Pn'])} kW" if d.get("inv_Pn") else "")) if s)
    c.text(xc_inv, iy2 + 4.2, sub, fit(sub, 2.4, 80, True), True, align="middle")
    pmax = (d["Pmax_W"] or 0) * nm * n_par * n_mppt / 1000.0
    if pmax:
        s_ = f"Pmax (panouri) {_f(pmax, 2)} kWp"
        c.text(xc_inv, iy2 + 0.9, s_, fit(s_, 2.1, 80), align="middle", layer="TEXT_GRI")
    L.meta["obiecte"].append({"tip": "sursa", "nume": d["inv_ref"], "bbox": (x_inv1, iy1, x_inv2, iy2)})
    # stringurile
    sec = d.get("sectiune_cc")
    et_cab = f"2 × H1Z2Z2-K {sec} mm²" if sec else "2 × H1Z2Z2-K"
    for i, ((m_, k_, et), y) in enumerate(zip(randuri, ys)):
        hs = fit(et, 2.6, x_m1 - x_sir - 1.5, True)
        c.text(x_sir, y - hs * 0.4, et, hs, True)
        _modul(c, x_m1, y, 7.0, h_mod)
        _modul(c, x_m2, y, 7.0, h_mod)
        c.line((x_m1 + 7.0, y), (x_m2, y), "MASURA")
        nn = f"× {nm}" if not tipic_par else f"× {nm} · {n_par} str."
        c.text((x_m1 + 7 + x_m2) / 2, y + h_mod / 2 + 0.5, nn, fit(nn, 2.0, x_m2 - x_m1 - 7.5, True), True, align="middle")
        c.line((x_m2 + 7.0, y), (x_fz - 1.0, y), "FORTA")
        # cablul solar: marcaj „//” + secțiunea (pe primul string al fiecărui MPPT, ca să nu se repete de 20 de ori)
        xs = x_sb1 - 5
        for dx in (-0.8, 0.8):
            c.line((xs + dx - 1.0, y - 1.4), (xs + dx + 1.0, y + 1.4), "SIMBOL")
        if pas >= 9 or i == 0 or randuri[i - 1][0] != m_:
            c.text(x_cab + 2, y + 1.1, et_cab, fit(et_cab, 1.9, x_sb1 - x_cab - 10), layer="TEXT_GRI")
        c.text(x_m2 + 8.0, y - 2.6, "+ / −", 1.6, layer="TEXT_GRI")
        if d["gpv"]:
            c.rect(x_fz - 1.0, y - 0.9, 4.0, 1.8, "SIMBOL", fill="#fff")
            c.line((x_fz - 1.0, y), (x_fz + 3.0, y), "SIMBOL")
            c.line((x_fz + 3.0, y), (x_join, y), "FORTA")
        else:
            c.line((x_fz - 1.0, y), (x_join, y), "FORTA")
    # unirea stringurilor pe MPPT → separator → intrarea MPPT
    for m_, ym in enumerate(mp_y):
        yy = [ys[i] for i, r in enumerate(randuri) if r[0] == m_]
        if len(yy) > 1:
            c.line((x_join, min(yy)), (x_join, max(yy)), "FORTA")
            for y in yy:
                c.dot((x_join, y), 0.6)
        c.line((x_join, ym), (x_sep - 2.0, ym), "FORTA")
        # separatorul (cuțit deschis, orizontal)
        c.line((x_sep - 2.0, ym), (x_sep + 2.6, ym + 2.2), "FORTA")
        c.line((x_sep + 3.0, ym + 1.1), (x_sep + 3.0, ym - 1.1), "SIMBOL")
        c.line((x_sep + 3.0, ym), (x_inv1, ym), "FORTA")
        c.circle((x_inv1, ym), 0.8, "SIMBOL")
        lab = f"MPPT{m_ + 1}"
        c.text(x_inv1 + 1.8, ym - 0.7, lab, 1.9, True)
    # cutia de joncțiune (SB) — chenar punctat cu gPV, separatoarele și SPD c.c.
    sb_y1, sb_y2 = min(ys) - pas / 2 - 14, max(ys) + pas / 2 + 3
    c.rect(x_sb1, sb_y1, x_sb2 - x_sb1, sb_y2 - sb_y1, "CARCASA")
    tsb = f"{d['sb_ref'] or 'SB'} — cutie de joncțiune c.c."
    c.text(x_sb1 + 1.0, sb_y2 + 1.2, tsb, fit(tsb, 2.1, x_sb2 - x_sb1 + 8, True), True)
    yl = sb_y1 + 1.6
    det = []
    if d["gpv"]:
        det.append(f"{d['gpv_ref']}: gPV {(_f(d['gpv_In'], 0) + ' A') if d.get('gpv_In') else ''} pe fiecare string (+ și −)")
    det.append(f"{d['sep_ref']}: separator c.c. sub sarcină pe MPPT" + (" (integrat în invertor)" if d["sep_integrat"] else ""))
    if d.get("spd_ref"):
        det.append(f"{d['spd_ref']}: " + " · ".join(d["spd_spec"] or ["SPD c.c."]))
    for s_ in reversed(det):
        c.text(x_sb1 + 1.2, yl, s_, fit(s_, 1.7, x_sb2 - x_sb1 - 2.4), layer="TEXT_GRI")
        yl += 2.6
    # SPD c.c. (simbol) pe prima intrare MPPT, spre pământ
    if d.get("spd_ref"):
        xs_ = x_sb2 - 5
        y0 = mp_y[-1]
        c.dot((xs_, y0), 0.6)
        c.line((xs_, y0), (xs_, y0 - 3.0), "FORTA")
        c.rect(xs_ - 1.8, y0 - 7.0, 3.6, 4.0, "SIMBOL", fill="#fff")
        c.pl([(xs_ - 1.0, y0 - 6.4), (xs_, y0 - 3.6), (xs_ + 1.0, y0 - 6.4)], "SIMBOL")
        c.line((xs_, y0 - 7.0), (xs_, y0 - 8.6), "PE")
        _pamant(c, xs_, y0 - 8.6, "", 2.2)
    # ieșirea c.a.
    ya = (iy1 + iy2) / 2
    xa = x_inv2 + 12
    c.line((x_inv2, ya), (xa, ya), "FORTA")
    cab = d.get("cablu_ca") or {}
    c.line((xa, ya), (xa, Y1 + 18), "FORTA")
    c.line((xa - 1.5, ya - 9), (xa + 1.5, ya - 7), "SIMBOL")
    if cab.get("cond"):
        c.text(xa + 1.8, ya - 9.5, cab["cond"], 1.9)
    txt_ca = cab.get("text") or ""
    if txt_ca:
        hca = fit(txt_ca, 1.9, (ya - 12) - (Y1 + 20))
        c.text(xa - 1.2, (ya - 12 + Y1 + 20) / 2, txt_ca, hca, align="middle", layer="TEXT_GRI", rot=90)
    bx_w = min(64.0, X2 - x_inv1 + 4)
    bx1 = min(max(xa - bx_w / 2, x_inv1), X2 - bx_w)
    c.rect(bx1, Y1 + 6, bx_w, 12, "SIMBOL", fill="#f3f3f3")
    t1 = f"către tabloul c.a. — {d['inv_ref']}" if not d.get("tipic") else "către tabloul c.a. — fiecare invertor"
    c.text(bx1 + bx_w / 2, Y1 + 13.4, t1, fit(t1, 2.6, bx_w - 3, True), True, align="middle")
    t2 = "protecția c.a. și restul instalației: planșa IE 09/FV"
    c.text(bx1 + bx_w / 2, Y1 + 8.6, t2, fit(t2, 1.8, bx_w - 3), align="middle", layer="TEXT_GRI")
    # RS485 + pământul invertorului
    if d.get("rs485"):
        c.rect(x_inv1 + 2, iy1 - 8, 12, 5, "SIMBOL")
        c.text(x_inv1 + 8, iy1 - 6.4, "RS485", 1.9, True, align="middle")
        c.line((x_inv1 + 8, iy1 - 3), (x_inv1 + 8, iy1), "RS485")
        L.are_rs485 = True
    xg = x_inv1 + 24
    c.line((xg, iy1), (xg, iy1 - 6), "PE")
    _pamant(c, xg, iy1 - 6, "Rp ≤ 1 Ω")
    # echipotențializarea ramelor (PE) — sub module
    ype = sb_y1 - 4
    c.line((x_m1 + 3.5, min(ys) - h_mod / 2), (x_m1 + 3.5, ype), "PE")
    c.line((x_m1 + 3.5, ype), (x_m1 + 14, ype), "PE")
    _pamant(c, x_m1 + 14, ype, "")
    c.text(x_m1 + 18, ype - 1.2, "echipotențializare rame FY 6 mm²", 1.7, layer="TEXT_GRI")
    # mențiunea „tipic”
    if d.get("tipic"):
        tt = d["tipic"]["mentiune"]
        hw = text_width(tt, 3.0, True) + 6
        c.rect(X1 + 2, Y2 - 9, hw, 7, "COMANDA")
        c.text(X1 + 5, Y2 - 6.7, tt, 3.0, True, layer="COMANDA")
    L.meta["schema_bbox"] = (X1, Y1, X2, Y2)


# ================================================================ IE 09 — TE de interfață multifilar
def _toate_aparate(m):
    def walk(bs, ctx):
        for b in bs or []:
            for a in (b.get("aparate") or []) + (b.get("aparate_tablou") or []):
                yield a, b, ctx
            yield from walk(b.get("copii"), ctx)
    yield from walk(m.get("intrari"), "intrare")
    yield from walk(m.get("plecari"), "plecare")
    if isinstance(m.get("jonctiune"), dict):
        yield from walk([m["jonctiune"]], "jonctiune")


PROT = ("mcb", "mccb", "mccb_dif", "rcbo", "acb", "sep_fuzibil", "fuzibil", "rccb", "separator")


def _caseta_inv(b):
    inv = next((a for a in b.get("aparate") or [] if a.get("tip") in ("invertor", "convertor_bess")), None)
    if inv is None:
        return None
    par = inv.get("param") or {}
    i = [k for k, a in enumerate(b["aparate"]) if a is inv][0]
    prot = next((a for a in b["aparate"][i + 1:] if a.get("tip") in PROT), None)
    return {"ref": inv.get("ref", ""), "model": " ".join(str(x) for x in (par.get("producator"), par.get("model")) if x),
            "Pn": par.get("Pn_kW"), "Iac": par.get("Iac_max_A"), "mono": par.get("retea") == "mono",
            "kWp": next((((a.get("param") or {}).get("kWp")) for a in b["aparate"] if a.get("tip") == "string_pv"), None),
            "rs485": any(l.get("eticheta") == "RS485" for l in inv.get("laterale") or []),
            "prot": _prot(prot), "cablu": dict(b.get("cablu_ca") or {}), "bess": inv.get("tip") == "convertor_bess",
            "idem": " · ".join(inv.get("spec") or []) if not par else ""}


def _prot(a):
    if not a:
        return None
    return {"ref": a.get("ref", ""), "tip": a.get("tip"), "spec": list(a.get("spec") or []), "param": dict(a.get("param") or {})}


def date_te(m):
    """datele TE de interfață pentru desenul multifilar, din modelul calculat al CEF; None dacă nu există QG"""
    qg = tc = tcs = None
    for a, b, ctx in _toate_aparate(m):
        if a.get("ref") == "QG" and qg is None:
            qg, b_qg = a, b
        elif a.get("ref") == "TC" and tc is None:
            tc = a
        elif a.get("ref") == "TCS" and tcs is None:
            tcs = a
    if qg is None:
        return None
    pq = qg.get("param") or {}
    pi = next((l for l in qg.get("laterale") or [] if l.get("eticheta") == "PI"), None)
    ups = next((l for l in qg.get("laterale") or [] if l.get("ref") == "UPS"), None)
    jn = m.get("jonctiune") if isinstance(m.get("jonctiune"), dict) else None
    tablouri = []
    sect = (m.get("bara") or {}).get("sectiuni")
    intr = m.get("intrari") or []
    if jn and sect:
        i0 = 0
        for k, sc in enumerate(sect):
            ni = int(sc.get("n_in", 0))
            pl = (m.get("plecari") or [])[k] if k < len(m.get("plecari") or []) else {}
            qs = next((a for a in pl.get("aparate") or [] if not a.get("jos") and a.get("tip") in PROT), None)
            qf = next((a for a in pl.get("aparate") or [] if a.get("jos") and a.get("tip") in PROT), None)
            tablouri.append({"titlu": sc.get("titlu") or f"TE-{k + 1}", "sub": sc.get("sub", ""),
                             "qs": _prot(qs), "qf": _prot(qf), "cablu": dict(pl.get("cablu") or {}),
                             "inv": [x for x in (_caseta_inv(b) for b in intr[i0:i0 + ni]) if x]})
            i0 += ni
        plecari = [{"tablou": t} for t in tablouri]
        racord = {"cablu": dict(jn.get("cablu") or {}), "sarcina": dict(jn.get("sarcina") or {})}
        car = dict(jn.get("carcasa") or {})
    else:
        plecari = [{"inv": x} for x in (_caseta_inv(b) for b in intr) if x]
        racord = {"cablu": dict(b_qg.get("cablu") or {}), "sarcina": dict(b_qg.get("sarcina") or {})}
        car = dict(m.get("carcasa") or {})
    spd = next((l for l in (m.get("bara") or {}).get("laterale") or [] if l.get("tip") == "spd"), None)
    mono = (m.get("calc") or {}).get("retea") == "mono" or str(pq.get("poli", "")).startswith("2")
    return {"qg": _prot(qg) | {"motorizat": bool(pq.get("motorizat")), "bd": bool(qg.get("bd") or pq.get("bd")),
                               "lista": list(qg.get("lista") or [])},
            "pi": {"spec": list((pi or {}).get("spec") or []), "lista": list((pi or {}).get("lista") or [])} if pi else None,
            "ups": {"spec": list((ups or {}).get("spec") or []), "lista": list((ups or {}).get("lista") or [])} if ups else None,
            "tc": {"spec": list(tc.get("spec") or []), "contor": next((l.get("ref") for l in tc.get("laterale") or []), "P")} if tc else None,
            "tcs": {"spec": list(tcs.get("spec") or []),
                    "sm": any(l.get("ref") == "SM" for l in tcs.get("laterale") or []),
                    "sl": next((" · ".join(l.get("spec") or []) for l in tcs.get("laterale") or [] if l.get("ref") == "SL"), None)} if tcs else None,
            "spd": {"ref": spd.get("ref", "F1"), "spec": list(spd.get("spec") or [])} if spd else None,
            "plecari": plecari, "racord": racord, "carcasa": car, "mono": mono, "rp": m.get("rp") or "Rp ≤ 1 Ω",
            "cascada": bool(jn and sect)}


def _eticheta_prot(p, latime):
    """eticheta aparatului „în cuvinte” (convenția proiectantului #5) pe cel mult 2 rânduri"""
    if not p:
        return []
    par = p.get("param") or {}
    nume = {"sep_fuzibil": "Separator fuzibil", "fuzibil": "Siguranță fuzibilă", "mcb": "Întreruptor automat",
            "mccb": "Întreruptor automat", "acb": "Întreruptor automat", "rcbo": "Întreruptor automat diferențial",
            "mccb_dif": "Întreruptor automat diferențial", "separator": "Separator"}.get(p.get("tip"), "Aparat")
    poli = str(par.get("poli") or "").replace("P", "")
    r1 = f"{nume} {poli}P" if poli else nume
    r2 = " · ".join(p.get("spec") or [])
    return [r1, r2] if r2 else [r1]


def _sym_prot(c, x, y, p, h=10.0):
    """simbolul protecției (pol unic, monofilar) centrat în (x, y)"""
    tip = (p or {}).get("tip") or "nod"
    mark = {"sep_fuzibil": "fuz", "fuzibil": "fuz", "separator": "bar"}.get(tip, "x")
    _bloc(c, "SYM_E2_" + tip.upper(), x, y, _contact(0, 0, mark, h), (p or {}).get("ref", ""), " | ".join((p or {}).get("spec") or []), tip)


def te_multifilar(L, sp, zona):
    c = L.c
    d = sp["date"]
    X1, Y1, X2, Y2 = zona
    faze = _faze(dict(sp, mono=d.get("mono")))
    nf = len(faze)
    dz = 3.6                                # distanța dintre conductoare
    W, H = X2 - X1, Y2 - Y1
    # --- coloana din dreapta: racordul (sus), TC + contor / smart meter, SmartLogger
    xr2 = X2
    xr1 = X2 - 58
    te_x1, te_x2 = X1 + 2, xr1 - 14
    rac = d["racord"]
    sar = rac.get("sarcina") or {}
    c.rect(xr1, Y2 - 13, xr2 - xr1, 13, "SIMBOL", fill="#f3f3f3")
    t = sar.get("titlu") or "PUNCT DE RACORD"
    c.text((xr1 + xr2) / 2, Y2 - 4.4, t, fit(t, 2.6, xr2 - xr1 - 3, True), True, align="middle")
    s_ = sar.get("sub") or ""
    from .layout import _wrap
    rr = _wrap(s_, max(20, int(len(s_) / 2) + 4)) if text_width(s_, 1.7) > xr2 - xr1 - 3 else [s_]
    for i, r_ in enumerate(rr[:2]):
        c.text((xr1 + xr2) / 2, Y2 - 8.0 - 2.6 * i, r_, fit(r_, 1.7, xr2 - xr1 - 3), align="middle", layer="TEXT_GRI")
    L.meta["obiecte"].append({"tip": "racord", "nume": t, "bbox": (xr1, Y2 - 13, xr2, Y2)})
    # --- bare: conductoarele de sosire (sus în TE) și barele TE (jos)
    y_in0 = Y2 - 31                          # L1 sosire
    y_in = [y_in0 - dz * i for i in range(nf)]
    y_te_sus = y_in0 + 8
    h_rel = 24.0
    y_rel2 = y_in[-1] - 9
    y_rel1 = y_rel2 - h_rel
    y_b0 = y_rel1 - 12                       # L1 bara TE
    y_b = [y_b0 - dz * i for i in range(nf)]
    # coloanele
    x_ups1, w_ups = te_x1 + 6, 27.0
    x_rel1, w_rel = x_ups1 + w_ups + 6, 40.0
    x_q0 = x_rel1 + w_rel + 9               # primul pol al QG
    x_poli = [x_q0 + 5.0 * i for i in range(nf - 1)]           # L1..L3 (+ N), fără PE
    x_ris = [te_x2 + 4 + 2.6 * i for i in range(nf)]           # ieșirea spre racord (verticale)
    # sosirea: orizontale de la stânga TE până la verticalele spre racord, apoi sus până la caseta racordului
    for (nm, lay), y, xv in zip(faze, y_in, x_ris):
        _cond(c, (te_x1 + 3, y), (xv, y), lay)
        _cond(c, (xv, y), (xv, Y2 - 13), lay)
        c.text(te_x1 + 2.5, y - 0.6, nm, 1.6, True, align="right")
    # cablul de racord (text rotit de-a lungul verticalelor)
    cab = rac.get("cablu") or {}
    tc_y = y_in0 + 6.0
    ytxt_lo, ytxt_hi = tc_y + 6, Y2 - 15
    cab_t = " ".join(x for x in ((cab.get("ref") or ""), (cab.get("text") or "")) if x)
    if cab_t and ytxt_hi - ytxt_lo > 8:
        c.text(x_ris[0] - 1.6, (ytxt_lo + ytxt_hi) / 2, cab_t, fit(cab_t, 1.9, ytxt_hi - ytxt_lo), align="middle",
               layer="TEXT_GRI", rot=90)
    if cab.get("cond"):
        c.text(x_ris[-1] + 2.0, Y2 - 22, cab["cond"], 1.8)
    # TC-urile (contor OD și / sau smart meter) pe verticalele fazelor
    n_ph = nf - 2
    tcs = [t_ for t_ in (d.get("tc"), d.get("tcs")) if t_]
    y_tc = [tc_y + 5.0 * j for j in range(len(tcs))]
    x_box = x_ris[-1] + 12
    y_cas = [y_in0 - 1.0 - 10.0 * j for j in range(len(tcs))]          # casetele contoarelor, în coloana din dreapta
    for j, (t_, yt) in enumerate(zip(tcs, y_tc)):
        for xv in x_ris[:n_ph]:
            c.circle((xv, yt), 1.1, "SIMBOL")
        xm_ = x_ris[-1] + 3.0 + 2.4 * j
        yc_ = y_cas[len(tcs) - 1 - j]
        c.line((x_ris[n_ph - 1] + 1.1, yt), (xm_, yt), "MASURA")
        c.line((xm_, yt), (xm_, yc_), "MASURA")
        c.line((xm_, yc_), (x_box, yc_), "MASURA")
        c.arrow((x_box, yc_), "right", 1.6, "HASURA")
    y_tc = list(reversed(y_cas))
    yb_ = None
    if d.get("tc"):
        yt = y_tc[0]
        c.rect(x_box, yt - 4, xr2 - x_box, 8, "SIMBOL", fill="#fff")
        c.text(x_box + 1.5, yt + 0.8, f"{d['tc']['contor']} — contor OD (kWh, bidirecțional)", fit("P1 — contor OD (kWh, bidirecțional)", 1.9, xr2 - x_box - 3, True), True)
        s_ = "TC " + " · ".join(d["tc"]["spec"])
        c.text(x_box + 1.5, yt - 2.6, s_, fit(s_, 1.6, xr2 - x_box - 3), layer="TEXT_GRI")
    if d.get("tcs"):
        yt = y_tc[-1]
        c.rect(x_box, yt - 4, xr2 - x_box, 8, "SIMBOL", fill="#fff")
        c.text(x_box + 1.5, yt + 0.8, "SM — smart meter (kWh · kVArh)", fit("SM — smart meter (kWh · kVArh)", 1.9, xr2 - x_box - 3, True), True)
        s_ = "TC " + " · ".join(d["tcs"]["spec"])
        c.text(x_box + 1.5, yt - 2.6, s_, fit(s_, 1.6, xr2 - x_box - 3), layer="TEXT_GRI")
        yb_ = yt
    # SmartLogger (sub contoare)
    y_sl = None
    if d.get("tcs") and d["tcs"].get("sl") is not None or any((p.get("inv") or {}).get("rs485") for p in d["plecari"]):
        y_sl = min(y_cas + [y_in0 + 9]) - 10
        c.rect(x_box, y_sl - 5, xr2 - x_box, 8, "SIMBOL", fill="#fff")
        c.text(x_box + 1.5, y_sl - 0.2, "SL — SmartLogger / datalogger", fit("SL — SmartLogger / datalogger", 1.9, xr2 - x_box - 3, True), True)
        s_ = d["tcs"]["sl"] if d.get("tcs") and d["tcs"].get("sl") else "RS485 → invertoare"
        c.text(x_box + 1.5, y_sl - 3.4, s_, fit(s_, 1.6, xr2 - x_box - 3), layer="TEXT_GRI")
        if yb_ is not None:
            c.line((xr2 - 6, yb_ - 4), (xr2 - 6, y_sl + 3), "RS485")
        L.are_rs485 = True
    # --- QG: polii pe fiecare fază (fără PE), cu legătura mecanică, motorul și bobina
    y_q = (y_in[-1] + y_b[0]) / 2 + 2
    for xp, (nm, lay), yi, yb in zip(x_poli, faze[:-1], y_in, y_b):
        _cond(c, (xp, yi), (xp, y_q + 4), lay)
        c.dot((xp, yi), 0.55)
        for it in _contact(0, 0, "x" if nm != "N" else "bar", 8.0):
            pass
        _bloc(c, "SYM_E2_POL", xp, y_q, _contact(0, 0, "x", 8.0), "QG", nm, "pol")
        _cond(c, (xp, y_q - 4), (xp, yb), lay)
        c.dot((xp, yb), 0.55)
    qg = d["qg"]
    xm1, xm2 = x_poli[0] + 1.3, x_poli[-1] + 6
    c.line((xm1, y_q - 0.2), (xm2, y_q - 0.2), "MECANIC")
    # motorul + bobina de declanșare + contactul de semnalizare
    bx = xm2
    blocuri = []
    if qg.get("motorizat"):
        blocuri.append(("M", "motor"))
    blocuri.append(("BD", "bobină"))
    blocuri.append(("OF", "contact"))
    yb_cmd = {}
    for i, (et, _) in enumerate(blocuri):
        yy = y_q + 3.2 - 4.6 * i
        c.rect(bx, yy - 1.9, 6.0, 3.8, "SIMBOL", fill="#fff")
        c.text(bx + 3.0, yy - 0.8, et, 1.7, True, align="middle")
        if i:
            c.line((bx + 3.0, yy + 1.9), (bx + 3.0, yy + 2.7), "MECANIC")
        yb_cmd[et] = (bx + 6.0, yy)
    c.line((xm2 - 0.2, y_q - 0.2), (bx, y_q - 0.2), "MECANIC")
    e0 = _eticheta_prot(qg, 0)
    poli = e0[0].split()[-1] if e0 and e0[0].split()[-1].endswith("P") else ""
    et = ["QG", "Întreruptor de interfață", (f"motorizat {poli} · bobină BD" if qg.get("motorizat") else f"{poli} · bobină BD").strip()] + e0[1:]
    hx = bx + 12
    for i, s_ in enumerate(et):
        h0 = 2.6 if i == 0 else 1.7
        c.text(hx, y_q + 6.0 - 2.9 * i - (0.6 if i else 0), s_, fit(s_, h0, te_x2 - hx - 1.5, i == 0), i == 0)
    # --- releul PI (bornele sus: L1–L3, N; jos: A1, A2, Y1, Y2, Y3)
    pi = d.get("pi")
    if pi:
        c.rect(x_rel1, y_rel1, w_rel, h_rel, "SIMBOL", fill="#fff")
        c.text(x_rel1 + w_rel / 2, y_rel2 - 8.0, "RELEU DE INTERFAȚĂ (PI)", fit("RELEU DE INTERFAȚĂ (PI)", 2.1, w_rel - 3, True), True, align="middle")
        sp_ = " · ".join(pi["spec"])
        c.text(x_rel1 + w_rel / 2, y_rel2 - 11.4, sp_, fit(sp_, 1.8, w_rel - 3), align="middle", layer="TEXT_GRI")
        c.text(x_rel1 + w_rel / 2, y_rel2 - 14.4, "anti-insularizare · reglaje în tabel", fit("anti-insularizare · reglaje în tabel", 1.6, w_rel - 3), align="middle", layer="TEXT_GRI")
        borne_sus = [nm for nm, _ in faze[:-1]]
        xs_b = [x_rel1 + 5 + i * (w_rel - 10) / max(len(borne_sus) - 1, 1) for i in range(len(borne_sus))]
        for nm_, xb_, (nm, lay), yi in zip(borne_sus, xs_b, faze, y_in):
            c.rect(xb_ - 1.4, y_rel2 - 2.8, 2.8, 2.8, "SIMBOL")
            c.text(xb_, y_rel2 - 2.2, nm_, 1.3, True, align="middle")
            # derivație din conductoarele de sosire (partea rețelei), prin F-PI pe faze
            c.dot((xb_, yi), 0.5)
            _cond(c, (xb_, yi), (xb_, y_rel2), lay)
            if nm != "N":
                _fuzibil_v(c, xb_, y_rel2 + 4.5, h=3.4, w=1.4)
        s_f = "1P 6 A" if d.get("mono") else "3P 6 A"
        c.text(xs_b[-2] + 1.4, y_rel2 + 3.8, s_f, fit(s_f, 1.5, xs_b[-1] - xs_b[-2] - 2.4), layer="TEXT_GRI")
        borne_jos = ["A1", "A2", "Y1", "Y2", "Y3"]
        xj = [x_rel1 + 4 + i * (w_rel - 8) / 4 for i in range(5)]
        for nm_, xb_ in zip(borne_jos, xj):
            c.rect(xb_ - 1.4, y_rel1, 2.8, 2.8, "SIMBOL")
            c.text(xb_, y_rel1 + 0.6, nm_, 1.2, True, align="middle")
        # Y1 / Y2 → bobina BD a QG (comandă, roșu); Y3 ← contactul de semnalizare OF
        y_c = y_rel1 - 3.5
        xbd, ybd = yb_cmd["BD"]
        xv1 = xbd + 2.5
        c.line((xj[2], y_rel1), (xj[2], y_c), "COMANDA")
        c.line((xj[2], y_c), (xv1, y_c), "COMANDA")
        c.line((xv1, y_c), (xv1, ybd), "COMANDA")
        c.line((xv1, ybd), (xbd + 1.8, ybd), "COMANDA")
        c.arrow((xbd, ybd), "left", 1.8, "COMANDA")
        L.meta["legaturi"].append({"tip": "comanda", "de": "PI", "spre": "QG", "de_xy": (xv1, ybd),
                                   "spre_xy": (xbd, ybd), "sageata": (xbd, ybd)})
        y_c2 = y_rel1 - 5.5
        xof, yof = yb_cmd["OF"]
        xv2 = xof + 4.5
        c.line((xj[4], y_rel1), (xj[4], y_c2), "COMANDA")
        c.line((xj[4], y_c2), (xv2, y_c2), "COMANDA")
        c.line((xv2, y_c2), (xv2, yof), "COMANDA")
        c.line((xv2, yof), (xof, yof), "COMANDA")
        c.text(xj[2], y_c2 - 2.4, "Y1–Y2 → BD · OF → Y3", 1.5, layer="TEXT_GRI")
        # --- UPS: intrare din L1 + N (F-UPS 1P 10 A), ieșire → A1 / A2 (1P 6 A)
        ups = d.get("ups")
        if ups:
            u_y2, u_y1 = y_rel2, y_rel1
            c.rect(x_ups1, u_y1, w_ups, u_y2 - u_y1, "SIMBOL", fill="#fff")
            c.text(x_ups1 + w_ups / 2, u_y2 - 7.5, "SURSĂ NEÎNTRERUPTIBILĂ", fit("SURSĂ NEÎNTRERUPTIBILĂ", 1.9, w_ups - 2, True), True, align="middle")
            va = next((s for s in ups["spec"] if "VA" in s), "")
            c.text(x_ups1 + w_ups / 2, u_y2 - 10.6, f"UPS {va}".strip(), 1.8, align="middle")
            c.text(x_ups1 + w_ups / 2, u_y2 - 13.4, "intrare / ieșire 230 V ± 10 %", fit("intrare / ieșire 230 V ± 10 %", 1.5, w_ups - 2), align="middle", layer="TEXT_GRI")
            xu_l, xu_n = x_ups1 + 6, x_ups1 + 11
            lay_l = faze[0][1]
            c.dot((xu_l, y_in[0]), 0.5); _cond(c, (xu_l, y_in[0]), (xu_l, u_y2), lay_l)
            _fuzibil_v(c, xu_l, u_y2 + 4.5, h=3.4, w=1.4)
            c.dot((xu_n, y_in[-2]), 0.5); _cond(c, (xu_n, y_in[-2]), (xu_n, u_y2), "COND_N")
            c.text(xu_n + 1.4, u_y2 + 3.8, "1P 10 A", 1.5, layer="TEXT_GRI")
            c.text(x_ups1 + 2, u_y2 - 2.6, "INPUT", 1.4, True)
            c.text(x_ups1 + 2, u_y1 + 1.0, "OUTPUT", 1.4, True)
            # ieșirea (jos) → A1 / A2
            for xo, xa_, lay in ((x_ups1 + w_ups - 9, xj[0], "COND_CMD"), (x_ups1 + w_ups - 4, xj[1], "COND_N")):
                yy = u_y1 - (2.5 if lay == "COND_CMD" else 1.5)
                c.line((xo, u_y1), (xo, yy), lay); c.line((xo, yy), (xa_, yy), lay); c.line((xa_, yy), (xa_, y_rel1), lay)
            c.text(x_ups1 + 1.5, u_y1 - 3.6, "1P 6 A → A1 / A2", 1.5, layer="TEXT_GRI")
    # --- barele TE
    xb1, xb2 = te_x1 + 3, te_x2 - 3
    for (nm, lay), y in zip(faze, y_b):
        _cond(c, (xb1, y), (xb2, y), lay)
        c.text(xb1 - 0.5, y - 0.6, nm, 1.6, True, align="right")
    et_b = "Bare Cu " + " · ".join(nm for nm, _ in faze)
    c.text(xb1 + 1.0, y_b[0] + 1.2, et_b, 1.7, layer="TEXT_GRI")
    # SPD pe bare (la capătul din dreapta al barelor) + pământul tabloului
    y_spd = y_b[-1] - 6
    x_s = xb2 - 12
    if d.get("spd"):
        for i, ((nm, lay), y) in enumerate(zip(faze[:-1], y_b)):
            xx = x_s + 1.6 * i
            c.dot((xx, y), 0.45)
            _cond(c, (xx, y), (xx, y_spd), lay)
        wsp = 1.6 * (nf - 2) + 4
        c.rect(x_s - 2, y_spd - 6, wsp, 6, "SIMBOL", fill="#fff")
        c.pl([(x_s - 0.6 + wsp / 2 - 2, y_spd - 5), (x_s + wsp / 2 - 2, y_spd - 1.5), (x_s + 0.6 + wsp / 2 - 2, y_spd - 5)], "SIMBOL")
        _cond(c, (x_s - 2 + wsp, y_spd - 3), (x_s + wsp + 3, y_spd - 3), "COND_PE")
        _cond(c, (x_s + wsp + 3, y_spd - 3), (x_s + wsp + 3, y_b[-1]), "COND_PE")
        c.dot((x_s + wsp + 3, y_b[-1]), 0.45)
        c.text(x_s - 2, y_spd - 8.6, d["spd"]["ref"], 2.2, True)
        s_ = " · ".join(d["spd"]["spec"])
        c.text(x_s - 2, y_spd - 11.2, s_, fit(s_, 1.6, xb2 - x_s + 4), layer="TEXT")
    # --- plecările (spre tablourile intermediare / invertoare)
    pl = d["plecari"]
    n_pl = len(pl)
    n_inv = sum(len((p.get("tablou") or {}).get("inv") or []) or 1 for p in pl)
    y_te_jos = y_b[-1] - 26
    # unde stau invertoarele: pe toată lățimea zonei (fără coloana din dreapta)
    xi1, xi2 = X1 + 2, xr2 - 5
    lat_inv = (xi2 - xi1) / max(n_inv, 1)
    xs_inv, k = [], 0
    for p in pl:
        n_ = len((p.get("tablou") or {}).get("inv") or []) or 1
        xs_inv.append([xi1 + lat_inv * (k + j + 0.5) for j in range(n_)])
        k += n_
    # abscisele plecărilor din TE: echidistante pe bare (etichetele în stânga fiecărei plecări), între marginea
    # din stânga a TE și SPD; nu cad exact pe coborârile polilor QG
    hi = x_s - 9
    lab_w = 30.0 if n_pl <= 3 else max(9.0, (hi - (te_x1 + 6)) / n_pl - 3.0)
    lo = te_x1 + 6 + lab_w
    if n_pl > 1:
        pasp = min((hi - lo) / (n_pl - 1), 60.0)
        st = (lo + hi) / 2 - pasp * (n_pl - 1) / 2 if pasp < 60 else lo
        xs_pl = [st + pasp * i for i in range(n_pl)]
    else:
        pasp = 60.0
        xs_pl = [min(max(sum(xs_inv[0]) / len(xs_inv[0]), lo), hi)] if pl else []
    xs_pl = [x + (2.5 if any(abs(x - xp_) < 1.6 or abs(x + 3.0 - xp_) < 1.0 or abs(x + 5.5 - xp_) < 1.0
                             for xp_ in x_poli) else 0.0) for x in xs_pl]
    compact = pasp < 24
    # nivelurile traseelor orizontale (fără suprapuneri): spre stânga — cele din stânga mai sus; spre dreapta invers
    dest = [(sum(g) / len(g)) if (p.get("tablou")) else g[0] for p, g in zip(pl, xs_inv)]
    niv = [0] * n_pl
    st_ = [i for i in range(n_pl) if dest[i] < xs_pl[i] - 0.5]
    dr_ = [i for i in range(n_pl) if dest[i] > xs_pl[i] + 0.5]
    for j, i in enumerate(st_):
        niv[i] = j
    for j, i in enumerate(sorted(dr_, reverse=True)):
        niv[i] = j
    y_q_pl = y_b[-1] - 11
    y_inv_box = Y1 + 2
    h_cas = 13.0
    y_inv_sym = y_inv_box + h_cas + 9
    cu_simbol = True
    if any(p.get("tablou") for p in pl):
        # tabloul intermediar are nevoie de ~30 mm + eticheta cablului; la loc strâmt invertorul rămâne doar caseta
        if (y_te_jos - 2 - 5 - 2.6 * max(niv + [0]) - 9.0) - 30.0 < y_inv_sym + S.HALF + 3:
            cu_simbol = False
            y_inv_sym = y_inv_box + h_cas
    for i_, (p, xp, g) in enumerate(zip(pl, xs_pl, xs_inv)):
        t_ = p.get("tablou")
        prot = (t_ or {}).get("qf") if t_ else (p.get("inv") or {}).get("prot")
        # L123 (pe fazele L1–L3), N și PE coboară separat din bare
        c.line((xp, y_b[0]), (xp, y_q_pl + 5), "FORTA")
        for y in y_b[:nf - 2]:
            c.dot((xp, y), 0.6)
        _sym_prot(c, xp, y_q_pl, prot)
        xN, xPE = xp + 3.0, xp + 5.5
        _cond(c, (xN, y_b[-2]), (xN, y_te_jos - 2), "COND_N"); c.dot((xN, y_b[-2]), 0.5)
        _cond(c, (xPE, y_b[-1]), (xPE, y_te_jos - 2), "COND_PE"); c.dot((xPE, y_b[-1]), 0.5)
        et = _eticheta_prot(prot, 0)
        if prot:
            stg = xs_pl[i_ - 1] + 7.0 if i_ else te_x1 + 5
            lat = max(7.0, xp - 2.2 - stg)
            c.text(xp - 2.2, y_q_pl + 3.2, prot.get("ref", ""), fit(prot.get("ref", ""), 2.4, lat, True), True, align="right")
            rows = ([eticheta_circuit(prot, "")["calibru"]] if compact else et[:2])
            for i, s_ in enumerate(rows):
                if s_:
                    c.text(xp - 2.2, y_q_pl + 0.3 - 2.4 * i, s_, fit(s_, 1.6, lat), align="right")
        c.line((xp, y_q_pl - 5), (xp, y_te_jos - 2), "FORTA")
        c.line((xp - 1.6, y_te_jos + 1.4), (xp + 1.6, y_te_jos + 3.6), "SIMBOL")
        if i_ == 0:
            c.text(xp + 7.0, y_te_jos + 1.4, "L123 + N + PE" if nf > 3 else "L + N + PE", 1.5, layer="TEXT_GRI")
        y_jog = y_te_jos - 5 - 2.6 * niv[i_]
        # cablul până la destinație
        if t_:
            _tablou_intermediar(L, c, t_, xp, g, y_te_jos - 2, y_inv_sym, y_inv_box, h_cas, lat_inv, faze, y_jog, cu_simbol)
        else:
            inv = p["inv"]
            xi = g[0]
            y_dest = y_inv_sym + 7
            c.line((xp, y_te_jos - 2), (xp, y_jog), "FORTA")
            c.line((xp, y_jog), (xi, y_jog), "FORTA")
            c.line((xi, y_jog), (xi, y_dest), "FORTA")
            cb = inv.get("cablu") or {}
            if cb.get("text"):
                hh = y_jog - 3 - (y_dest + 1)
                c.text(xi - 1.2, (y_jog - 3 + y_dest + 1) / 2, cb["text"], fit(cb["text"], 1.7, hh), align="middle",
                       layer="TEXT_GRI", rot=90)
            _invertor(L, c, inv, xi, y_inv_sym, y_inv_box, h_cas, lat_inv)
    # --- carcasa TE (chenar magenta) + titlu + eticheta tabloului
    te_y1 = y_te_jos
    c.rect(te_x1, te_y1, te_x2 - te_x1, y_te_sus - te_y1, "TABLOU")
    car = d.get("carcasa") or {}
    tit = car.get("titlu") or "TE INTERFAȚĂ"
    ht = fit(tit, 3.0, (te_x2 - te_x1) * 0.4, True)
    c.text(te_x1 + 1.0, y_te_sus + 1.4, tit, ht, True)
    s_ = car.get("sub") or ""
    lat_s = te_x2 - te_x1 - text_width(tit, ht, True) - 6
    if s_:
        c.text(te_x2, y_te_sus + 4.6, s_, fit(s_, 1.9, lat_s, True), True, align="right")
    c.text(te_x2, y_te_sus + 1.4, "Rezervă de spațiu 25–30 % · Tablou IP66", fit("Rezervă de spațiu 25–30 % · Tablou IP66", 1.8, lat_s, True), True, align="right")
    L.meta["carcase"].append({"nume": tit, "bbox": (te_x1, te_y1, te_x2, y_te_sus), "parinte": None, "principala": True})
    # pământul TE
    xg = te_x1 + 6
    _cond(c, (xb1, y_b[-1]), (xg - 3, y_b[-1]), "COND_PE")
    _cond(c, (xg - 3, y_b[-1]), (xg - 3, te_y1 - 3), "COND_PE")
    _pamant(c, xg - 3, te_y1 - 3, d.get("rp") or "Rp ≤ 1 Ω", jos=True)
    # RS485: invertoare → SmartLogger (linie cyan, sub casetele invertoarelor)
    rs = [x for g, p in zip(xs_inv, pl) for x, inv in zip(g, ((p.get("tablou") or {}).get("inv") or [p.get("inv")]))
          if inv and inv.get("rs485")]
    if rs and y_sl is not None:
        yr = y_inv_box - 1.0
        for x in rs:
            c.line((x + 4, y_inv_box), (x + 4, yr), "RS485")
        c.line((min(rs) + 4, yr), (xr2 - 2, yr), "RS485")
        c.line((xr2 - 2, yr), (xr2 - 2, y_sl - 5), "RS485")
        tr = "RS485 2 × 2 × AWG24 ecranat, ecranul legat la pământ la un capăt"
        c.text(xr2 - 3.2, (yr + y_sl - 5) / 2, tr, fit(tr, 1.7, y_sl - 5 - yr - 4), align="middle", layer="TEXT_GRI", rot=90)
        L.are_rs485 = True
    L.meta["schema_bbox"] = (X1, Y1, X2, Y2)


def _invertor(L, c, inv, x, y_sym, y_box, h_cas, lat, cu_simbol=True):
    """simbolul invertorului + caseta lui de date („Către INV-k … U, P, Imax, RS485”)"""
    w = max(10.0, min(lat - 1.6, 44.0))
    if cu_simbol:
        _bloc(c, "SYM_INVERTOR", x, y_sym, S.draw("invertor"), inv.get("ref", ""), inv.get("model", ""), "invertor")
        c.line((x, y_sym - S.HALF), (x, y_box + h_cas), "FORTA")
    c.rect(x - w / 2, y_box, w, h_cas, "SIMBOL", fill="#f3f3f3")
    t = f"Către {inv.get('ref', '')}"
    c.text(x, y_box + h_cas - 3.4, t, fit(t, 2.2, w - 1.5, True), True, align="middle")
    u = "230 V" if inv.get("mono") else "400 V"
    rows = [inv.get("model") or "", f"U {u} · P {_f(inv.get('Pn'))} kW", f"Imax {_f(inv.get('Iac'))} A"
            + (f" · {_f(inv.get('kWp'))} kWp" if inv.get("kWp") else "")]
    if inv.get("idem"):
        rows = [inv["idem"]]
    for i, s_ in enumerate(rows):
        if s_:
            c.text(x, y_box + h_cas - 6.2 - 2.4 * i, s_, fit(s_, 1.6, w - 1.5), align="middle", layer="TEXT_GRI")
    L.meta["obiecte"].append({"tip": "sursa", "nume": inv.get("ref", ""), "bbox": (x - w / 2, y_box, x + w / 2, y_box + h_cas)})


def _tablou_intermediar(L, c, t, xp, g, y_sus, y_inv_sym, y_inv_box, h_cas, lat, faze, y_jog=None, cu_simbol=True):
    """tabloul intermediar (chenar magenta): QS la intrare, bara, protecția fiecărui invertor; invertoarele dedesubt"""
    xg1, xg2 = min(g) - lat / 2 + 1.2, max(g) + lat / 2 - 1.2
    yj0 = y_jog if y_jog is not None else y_sus - 4
    y_t2 = min(y_sus - 20, yj0 - 9.0)
    y_t1 = y_inv_sym + (12 if cu_simbol else 3)
    if y_t2 - y_t1 < 26:
        y_t2 = y_t1 + 26
    xc = (xg1 + xg2) / 2
    # cablul TE → tablou
    yj = y_jog if y_jog is not None else y_sus - 4
    c.line((xp, y_sus), (xp, yj), "FORTA")
    c.line((xp, yj), (xc, yj), "FORTA")
    c.line((xc, yj), (xc, y_t2 - 4), "FORTA")
    cb = t.get("cablu") or {}
    s_ = " ".join(x for x in (cb.get("ref") or "", cb.get("text") or "") if x)
    if s_:
        from .layout import _wrap
        rr = _wrap(s_, int(len(s_) / 2) + 3) if text_width(s_, 1.7) > xg2 - xc - 3 else [s_]
        for i, r_ in enumerate(rr[:2]):
            c.text(xc + 1.6, yj - 3.0 - 2.5 * i, r_, fit(r_, 1.7, xg2 - xc - 3), layer="TEXT_GRI")
    # QS
    yq = y_t2 - 9
    _sym_prot(c, xc, yq, t.get("qs"))
    if t.get("qs"):
        c.text(xc - 2.2, yq + 2.2, t["qs"].get("ref", ""), 2.1, True, align="right")
        s2 = " · ".join(t["qs"].get("spec") or [])
        c.text(xc - 2.2, yq - 0.6, s2, fit(s2, 1.5, xc - xg1 - 4), align="right")
    yb = yq - 7
    c.line((xc, yq - 5), (xc, yb), "FORTA")
    c.line((min(g + [xc]) - 2, yb), (max(g + [xc]) + 2, yb), "FORTA")
    c.dot((xc, yb), 0.6)
    yqi = yb - 7
    for inv, x in zip(t.get("inv") or [], g):
        c.dot((x, yb), 0.6)
        c.line((x, yb), (x, yqi + 5), "FORTA")
        _sym_prot(c, x, yqi, inv.get("prot"))
        if inv.get("prot"):
            c.text(x - 2.0, yqi + 2.2, inv["prot"].get("ref", ""), 1.9, True, align="right")
        c.line((x, yqi - 5), (x, y_inv_sym + (S.HALF if cu_simbol else 0.0)), "FORTA")
        _invertor(L, c, inv, x, y_inv_sym, y_inv_box, h_cas, lat, cu_simbol)
    y_t1 = min(y_t1, yqi - 7)
    c.rect(xg1, y_t1, xg2 - xg1, y_t2 - y_t1, "TABLOU")
    lw = xc - xg1 - 4
    c.text(xg1 + 1.0, y_t2 - 2.8, "Tablou intermediar", fit("Tablou intermediar", 1.9, lw, True), True)
    c.text(xg1 + 1.0, y_t2 - 5.6, t.get("titlu", ""), fit(t.get("titlu", ""), 2.4, lw, True), True)
    sub = t.get("sub") or ""
    if sub:
        from .layout import _wrap
        rw = xg2 - xc - 3
        rr = _wrap(sub, int(len(sub) / 2) + 3) if text_width(sub, 1.5) > rw else [sub]
        for i, r_ in enumerate(rr[:2]):
            c.text(xg2 - 1.0, y_t2 - 2.6 - 2.3 * i, r_, fit(r_, 1.5, rw), align="right", layer="TEXT_GRI")
    L.meta["carcase"].append({"nume": t.get("titlu", ""), "bbox": (xg1, y_t1, xg2, y_t2), "parinte": None})


# ================================================================ curbe timp-curent
PUNCTE_GG = ((1.25, 1e5), (1.6, 3600.0), (2.0, 300.0), (2.5, 60.0), (3.0, 20.0), (4.0, 6.0), (5.0, 2.0),
             (6.0, 0.8), (8.0, 0.2), (10.0, 0.06), (14.0, 0.02), (20.0, 0.008))


def curba_temporara(p, I_max=None):
    """GENERATOR TEMPORAR (până livrează motorul `engine.calc` punctele din fișele de producător): punctele (I [A],
    t [s]) ale caracteristicii de declanșare MAXIME a unei protecții, din parametrii ei (In, Ir, Isd, tsd, Ii, curba).
    Forme orientative: MCB B/C/D (SR EN 60898-1: 1,45·In ≤ 1 h, 2,55·In 1–60 s, magnetic 5 / 10 / 20·In),
    MCCB TM (termic din Ir, magnetic din Im / Ii), electronic LSI (I²t pe L, S temporizat, I instantaneu),
    gG (formă tipică SR EN 60269-1)."""
    par = p.get("param") or {}
    tip = p.get("tip")
    In = par.get("In_A")
    if not In:
        return []
    Ir = par.get("Ir_A") or In
    pts = []
    if tip in ("sep_fuzibil", "fuzibil"):
        pts = [(In * k, t) for k, t in PUNCTE_GG]
    elif tip in ("mcb", "rcbo"):
        curba = str(par.get("curba") or "C").upper()
        im = {"B": 5.0, "C": 10.0, "D": 20.0}.get(curba, 10.0)
        pts = [(1.13 * In, 1e5), (1.45 * In, 3600.0), (2.0 * In, 120.0), (2.55 * In, 40.0), (4.0 * In, 12.0),
               (im * 0.999 * In, 4.0 if im > 6 else 6.0), (im * In, 0.01), (I_max or 50 * In, 0.005)]
    elif par.get("decl") == "EL" or tip == "acb":
        isd = par.get("Isd_A") or 10 * Ir
        tsd = par.get("tsd_s") or 0.1
        ii = par.get("Ii_A") or 15 * In
        pts = [(1.05 * Ir, 1e5), (1.2 * Ir, 2500.0)]
        k = 1.5
        while k * Ir < isd:
            pts.append((k * Ir, max(tsd, 10.0 * (6.0 / k) ** 2)))
            k *= 1.4
        pts += [(isd * 0.999, max(tsd, 10.0 * (6.0 * Ir / isd) ** 2)), (isd, tsd), (ii * 0.999, tsd), (ii, 0.02),
                (I_max or 50 * In, 0.01)]
    else:                                   # MCCB termomagnetic
        im = par.get("Im_A") or par.get("Ii_A") or 10 * In
        pts = [(1.05 * Ir, 1e5), (1.3 * Ir, 3600.0), (2 * Ir, 300.0), (3 * Ir, 60.0), (5 * Ir, 15.0),
               (im * 0.999, max(2.0, 15.0 * (5 * Ir / im) ** 2)), (im, 0.02), (I_max or 50 * In, 0.01)]
    return [(float(i), float(t)) for i, t in pts if i > 0 and t > 0]


def _lant_protectii(m):
    """protecțiile înseriate pe calea cea mai lungă (de la sursă / invertor spre rețea): protecția din ramura primei
    intrări, protecțiile plecării ei, ale joncțiunii și ale racordului — fără dubluri, sortate după In"""
    out, vazut = [], set()

    def add(a):
        if not isinstance(a, dict) or a.get("tip") not in PROT or not (a.get("param") or {}).get("In_A"):
            return
        k = (a.get("ref"), a.get("tip"))
        if k in vazut:
            return
        vazut.add(k)
        out.append(a)
    intr = m.get("intrari") or []
    if intr:
        for a in intr[0].get("aparate") or []:
            add(a)
    pl = m.get("plecari") or []

    def adanc(b):
        for a in (b.get("aparate") or []) + (b.get("aparate_tablou") or []):
            add(a)
        ch = [x for x in b.get("copii") or [] if any(a.get("tip") in PROT for a in x.get("aparate") or [])]
        if ch:
            adanc(max(ch, key=lambda x: max(((a.get("param") or {}).get("In_A") or 0) for a in x.get("aparate") or [{}])))
    if pl:
        cand = [b for b in pl if any(a.get("tip") in PROT for a in b.get("aparate") or [])]
        if cand:
            if intr and any(a.get("tip") == "invertor" for a in intr[0].get("aparate") or []):
                adanc(cand[0])
            else:
                adanc(max(cand, key=lambda b: max(((a.get("param") or {}).get("In_A") or 0) for a in b.get("aparate") or [{}])))
    if isinstance(m.get("jonctiune"), dict):
        for a in (m["jonctiune"].get("aparate") or []) + (m["jonctiune"].get("aparate_tablou") or []):
            add(a)
    return sorted(out, key=lambda a: ((a.get("param") or {}).get("Ir_A") or a["param"]["In_A"]))


def date_curbe(m):
    """datele planșei de curbe: {"curbe": [{ref, eticheta, puncte: [(I, t)], sursa}], "Ik": [(eticheta, I_A)]}.
    Punctele vin din motor (`engine.calc.curbe.curbe_protectii(model)`, dacă există) — altfel din generatorul
    temporar de aici (`curba_temporara`)."""
    lant = _lant_protectii(m)
    if len(lant) < 2:
        return None
    try:
        from .calc import curbe as _cm          # interfața așteptată de la motor (coordonare prin raport)
        dm = _cm.curbe_protectii(m)
        if dm and dm.get("curbe"):
            dm.setdefault("sursa", "motor")
            return dm
    except Exception:       # noqa: BLE001 — modulul motorului încă nu există: generatorul temporar
        pass
    curbe_ = []
    for a in lant:
        pts = curba_temporara(a)
        if pts:
            curbe_.append({"ref": a.get("ref", ""), "eticheta": f"{a.get('ref', '')} — " + " · ".join(a.get("spec") or []),
                           "puncte": pts})
    ik = []
    rez = m.get("calc_rezumat") if isinstance(m.get("calc_rezumat"), dict) else {}
    import re
    msj = " ".join(str(v.get("mesaj", "")) for k_ in ("verificari", "info") for v in rez.get(k_) or [] if isinstance(v, dict))
    num = lambda s_: float(s_.replace("\u202f", "").replace(" ", "").replace(".", "").replace(",", "."))
    i3 = [num(x) for x in re.findall(r"Ik3max ([\d\u202f ,.]+?) kA", msj)]
    i1 = [num(x) for x in re.findall(r"Ik1min ([\d\u202f ,.]+?) A", msj)]
    if i3:
        ik.append(("Ik3 max", max(i3) * 1000.0))
    if i1:
        ik.append(("Ik1 min", min(i1)))
    return {"curbe": curbe_, "Ik": ik, "sursa": "temporar"}


def curbe(L, sp, zona):
    c = L.c
    d = sp["date"]
    X1, Y1, X2, Y2 = zona
    px1, px2 = X1 + 18, X2 - 4
    py1, py2 = max(Y1 + 12, 11 + 67.7 + L.H_REV + 12), Y2 - 14
    toate = [p for cb in d["curbe"] for p in cb["puncte"]] + [(v, 1.0) for _, v in d.get("Ik") or []]
    imin = min(p[0] for p in toate)
    imax = max(p[0] for p in toate)
    d0 = math.floor(math.log10(max(imin * 0.8, 1e-3)))
    d1 = math.ceil(math.log10(imax * 1.2))
    t0, t1 = -2, 4
    def X(i): return px1 + (math.log10(i) - d0) / (d1 - d0) * (px2 - px1)
    def Y(t): return py1 + (math.log10(t) - t0) / (t1 - t0) * (py2 - py1)
    # grila log-log
    for dec in range(d0, d1 + 1):
        for k in range(1, 10):
            v = k * 10 ** dec
            if math.log10(v) > d1:
                break
            c.line((X(v), py1), (X(v), py2), "CURBA_GRID" if k > 1 else "CURBA_AX")
        lab = f"{10 ** dec:g}" if dec < 4 else f"10^{dec}"
        c.text(X(10 ** dec), py1 - 3.2, lab, 1.9, align="middle")
    for dec in range(t0, t1 + 1):
        for k in range(1, 10):
            v = k * 10 ** dec
            if math.log10(v) > t1:
                break
            c.line((px1, Y(v)), (px2, Y(v)), "CURBA_GRID" if k > 1 else "CURBA_AX")
        c.text(px1 - 1.5, Y(10 ** dec) - 0.7, f"{10 ** dec:g}", 1.9, align="right")
    c.rect(px1, py1, px2 - px1, py2 - py1, "CURBA_AX")
    c.text((px1 + px2) / 2, py1 - 7.0, "Curent I [A]", 2.2, True, align="middle")
    c.text(px1 - 12, (py1 + py2) / 2, "Timp de declanșare t [s]", 2.2, True, align="middle", rot=90)
    tit = "CURBE TIMP-CURENT ALE PROTECȚIILOR ÎNSERIATE — SELECTIVITATE"
    c.text(px1, py2 + 6.0, tit, fit(tit, 3.0, px2 - px1, True), True)
    nota = ("caracteristici de declanșare maxime, orientative (generator temporar) — se verifică pe curbele "
            "producătorului" if d.get("sursa") == "temporar" else "curbe din datele de producător (motorul de calcul)")
    c.text(px1, py2 + 1.8, nota, fit(nota, 1.8, px2 - px1), layer="TEXT_GRI")
    # curbele (decupate la fereastra t ∈ [0,01; 10 000] s)
    etich = []
    for k, cb in enumerate(d["curbe"]):
        lay = f"CURBA_{k % 6 + 1}"
        pts = [(X(i), Y(min(max(t, 10 ** t0), 10 ** t1))) for i, t in cb["puncte"] if 10 ** d0 <= i <= 10 ** d1]
        if len(pts) >= 2:
            c.pl(pts, lay)
        # eticheta lângă primul punct
        if pts:
            x0, y0 = pts[min(1, len(pts) - 1)]
            y0 = min(y0, py2 - 3)
            while any(abs(x0 - a) < 6 and abs(y0 - b) < 2.6 for a, b in etich):
                y0 -= 3.0
            etich.append((x0, y0))
            c.text(x0 + 1.2, y0, cb.get("ref", ""), 2.2, True, layer=lay)
    # curenții de scurtcircuit
    for et, v in d.get("Ik") or []:
        if 10 ** d0 <= v <= 10 ** d1:
            c.line((X(v), py1), (X(v), py2), "CURBA_IK")
            c.text(X(v) - 1.0, py1 + 2.0, f"{et} = {_f(v / 1000.0, 2)} kA", 1.8, layer="TEXT_GRI", rot=90)
    # legenda curbelor (sub titlu, în dreapta sus a graficului)
    yl = py2 - 4.5
    xl = px2 - 2
    for k, cb in enumerate(d["curbe"]):
        lay = f"CURBA_{k % 6 + 1}"
        e_ = cb.get("eticheta") or cb.get("ref", "")
        h_ = fit(e_, 1.9, 80)
        c.rect(xl - text_width(e_, h_) - 10, yl - 1.2, text_width(e_, h_) + 10.5, 3.6, "TABEL", fill="#fff")
        c.line((xl - text_width(e_, h_) - 9, yl + 0.6), (xl - text_width(e_, h_) - 2, yl + 0.6), lay)
        c.text(xl, yl, e_, h_, align="right")
        yl -= 3.6
    L.meta["schema_bbox"] = (X1, Y1, X2, Y2)


# ================================================================ etichete de tablou (A4, benzi DIN 18 mm)
MODUL_DIN = 18.0                        # lățimea unui modul DIN (mm)
H_ETICHETA = 16.0                       # înălțimea benzii
DIN_TIP = ("mcb", "rcbo", "rccb", "mccb_dif", "sep_fuzibil", "fuzibil", "spd", "separator", "contact", "mccb")


def _poli(a):
    import re
    par = a.get("param") or {}
    p = par.get("poli")
    if isinstance(p, (int, float)):
        return int(p)
    t = str(p or "") + " " + " ".join(a.get("spec") or [])
    m_ = re.search(r"(\d)P(\+N)?", t)
    if m_:
        return int(m_.group(1)) + (1 if m_.group(2) else 0)
    return 2 if (a.get("tip") == "rcbo") else 1


def module_din(a):
    """lățimea aparatului în module DIN (1 modul = 18 mm); MCCB-ul ocupă o bandă de 4 module"""
    tip = a.get("tip")
    if tip == "mccb":
        return 4
    if tip == "rcbo":
        return 2 if "1P+N" in " ".join(a.get("spec") or []) or _poli(a) <= 2 else _poli(a)
    return max(1, min(_poli(a), 4))


def eticheta_circuit(a, denumire):
    """{cod, denumire, calibru, idn, module} pentru eticheta unui aparat"""
    import re
    par = a.get("param") or {}
    In = par.get("In_A")
    cal = ""
    if In:
        cal = (f"{par.get('curba')}{_f(In, 0)}" if par.get("curba") and a.get("tip") in ("mcb", "rcbo")
               else f"{_f(In, 0)} A" + (" gG" if a.get("tip") in ("sep_fuzibil", "fuzibil") else "")
               + (f" · Ir {_f(par['Ir_A'], 0)} A" if par.get("Ir_A") and par.get("Ir_A") != In else ""))
    elif a.get("spec"):
        cal = a["spec"][0]
    idn = par.get("IdN_mA") or par.get("IΔn_mA") or par.get("Idn_mA")
    if not idn:
        m_ = re.search(r"(\d+)\s*mA", " ".join(a.get("spec") or []))
        idn = int(m_.group(1)) if m_ else None
    return {"cod": a.get("ref") or "", "denumire": denumire or "", "calibru": cal,
            "idn": f"IΔn {idn} mA" if idn else "", "module": module_din(a)}


def pagini_etichete(tablouri, antet="", filigran=None):
    """pagini A4 (vedere) cu benzile de etichete: un rând = o șină de 12 module (216 mm); `tablouri` =
    [{nume, etichete: [eticheta_circuit…]}]. Întoarce lista de Canvas (297 × 210 mm)."""
    W, H = 297.0, 210.0
    pag = []
    c = None
    y = 0.0

    def pagina_noua():
        cv = Canvas(W, H)
        if filigran:
            cv.meta["filigran"] = str(filigran)
        cv.rect(8, 8, W - 16, H - 16, "TABEL")
        cv.text(12, H - 15, "ETICHETE TABLOU — benzi pentru aparate modulare (1 modul DIN = 18 mm)", 3.2, True)
        cv.text(12, H - 20.5, (antet + " · " if antet else "") + "tipăriți la scara 1:1 (100 %), tăiați pe contur",
                2.0, layer="TEXT_GRI")
        pag.append(cv)
        return cv, H - 28
    c, y = pagina_noua()
    for t in tablouri:
        et = [e for e in t.get("etichete") or [] if e]
        if not et:
            continue
        randuri, rand, lat = [], [], 0
        for e in et:
            if lat + e["module"] > 12 and rand:
                randuri.append(rand); rand, lat = [], 0
            rand.append(e); lat += e["module"]
        if rand:
            randuri.append(rand)
        h_t = 8 + len(randuri) * (H_ETICHETA + 4)
        if y - h_t < 12:
            c, y = pagina_noua()
        c.text(12, y - 3, f"Tablou {t.get('nume', '')}", 2.8, True)
        y -= 8
        for rd in randuri:
            if y - H_ETICHETA < 12:
                c, y = pagina_noua()
            x = 12.0
            for e in rd:
                w = e["module"] * MODUL_DIN
                c.rect(x, y - H_ETICHETA, w, H_ETICHETA, "TABEL")
                xc = x + w / 2
                c.text(xc, y - 3.6, e["cod"], fit(e["cod"], 2.8, w - 1.5, True), True, align="middle")
                den = e["denumire"]
                from .layout import _wrap
                rr = _wrap(den, max(6, int(w / 1.6))) if text_width(den, 1.8) > w - 1.5 else [den]
                for i, r_ in enumerate(rr[:2]):
                    c.text(xc, y - 6.8 - 2.3 * i, r_, fit(r_, 1.8, w - 1.2), align="middle")
                c.text(xc, y - 12.2, e["calibru"], fit(e["calibru"], 2.2, w - 1.5, True), True, align="middle")
                if e["idn"]:
                    c.text(xc, y - 15.0, e["idn"], fit(e["idn"], 1.6, w - 1.5), align="middle", layer="TEXT_GRI")
                x += w
            y -= H_ETICHETA + 4
        y -= 2
    return pag
