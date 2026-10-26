"""Bibliotecă de simboluri IEC 60617 pentru scheme monofilare.
Fiecare simbol se desenează în coordonate locale (mm): borna superioară la (0, +H/2),
borna inferioară la (0, -H/2). Textele descriptive se pun în stânga, poziția în dreapta."""
import math
from .canvas import *

M = 16.0          # înălțimea modulului standard al unui aparat (mm)
HALF = M / 2

# ---------------------------------------------------------------- aparate de comutație
# Convenție (IEC 60617, schemă verticală, energia vine de sus): contactul FIX este sus, la YF, și poartă
# marcajul funcției (X = întreruptor automat, bară = separator, bară + cerc = separator de sarcină,
# semicerc = contactor); cuțitul mobil este articulat jos, la YH, și e desenat deschis, spre dreapta.
YF = HALF - 3.0        # contactul fix
YH = -HALF + 3.0       # articulația cuțitului
BOX_X, BOX_W, BOX_H = 6.5, 4.0, 3.8     # coloana declanșatoarelor (I>, IΔ, BD) din dreapta


class _Prims(list):
    """lista de primitive a unui simbol + ancorele lui (pini pentru legăturile de măsură / comandă)"""
    def __init__(self): super().__init__(); self.anc = {}


def _shift(pt, dy): return (pt[0], pt[1] + dy)


def _mark(p, kind, y):
    if kind == "x":
        p.append(Line((-1.6, y - 1.6), (1.6, y + 1.6))); p.append(Line((1.6, y - 1.6), (-1.6, y + 1.6)))
    elif kind in ("bar", "bar_cerc"):
        p.append(Line((-1.8, y), (1.8, y)))
        if kind == "bar_cerc": p.append(Circle((0, y + 0.95), 0.85))
    elif kind == "semicerc":
        p.append(Polyline([(math.cos(math.radians(a)), y - 1.0 + math.sin(math.radians(a))) for a in range(0, 181, 15)]))


def _blade_end(yf): return (3.6, yf - 0.3)


def _switch(p, mark, yf=YF, yh=YH, top=HALF, bot=-HALF):
    """contact deschis: borna de sus -> contact fix (marcat) ... cuțit articulat jos -> borna de jos"""
    lead_top = yf + (1.8 if mark == "bar_cerc" else 0.0)
    p.append(Line((0, top), (0, lead_top), "FORTA"))
    if mark == "bar_cerc": p.append(Line((0, lead_top), (0, yf + 1.8), "FORTA"))
    _mark(p, mark, yf)
    p.append(Line((0, yh), _blade_end(yf), "FORTA"))
    p.append(Line((-1.2, yh), (1.2, yh)))      # articulația
    p.append(Line((0, yh), (0, bot), "FORTA"))
    ex, ey = _blade_end(yf)
    return (ex * 0.5, (yh + ey) * 0.5)          # mijlocul cuțitului (pentru legătura mecanică)


def _relee(p, labels, mid, toroid=None):
    """coloana de declanșatoare din dreapta, legată mecanic (linie întreruptă neagră) de cuțit"""
    if not labels: return
    n = len(labels)
    c0 = min(mid[1], HALF - 0.3 - BOX_H / 2)
    if c0 - (n - 1) * BOX_H - BOX_H / 2 < -HALF + 0.3:
        c0 = -HALF + 0.3 + BOX_H / 2 + (n - 1) * BOX_H
    centers = {}
    for i, lab in enumerate(labels):
        cy = c0 - i * BOX_H
        p.append(Rect((BOX_X, cy - BOX_H / 2), BOX_W, BOX_H))
        p.append(Text((BOX_X + BOX_W / 2, cy - 0.75), lab, 1.8 if lab != "BD" else 1.5, True, align="middle"))
        centers[lab] = cy
    ly = max(min(mid[1], c0 + BOX_H / 2 - 0.4), c0 - (n - 0.5) * BOX_H + 0.4)
    if abs(mid[1] - ly) > 0.05: p.append(Line(mid, (mid[0], ly), "MECANIC"))
    p.append(Line((mid[0], ly), (BOX_X, ly), "MECANIC"))
    if toroid is not None and "IΔ" in centers:   # toroidul diferențial -> releul IΔ
        tx, ty = toroid; cy = centers["IΔ"]
        if cy - BOX_H / 2 <= ty <= cy + BOX_H / 2:
            p.append(Line((tx, ty), (BOX_X, ty), "MECANIC"))
        else:
            xm = BOX_X + BOX_W / 2; yb = c0 - (n - 0.5) * BOX_H
            p.append(Line((tx, ty), (xm, ty), "MECANIC")); p.append(Line((xm, ty), (xm, yb), "MECANIC"))
    p.anc["masura"] = (BOX_X + BOX_W, c0)
    if "BD" in centers: p.anc["comanda"] = (BOX_X + BOX_W, centers["BD"])


def _breaker(p, d, release=True, dif=False, bd=False, mark="x"):
    yh = -2.4 if dif else YH
    mid = _switch(p, mark, YF, yh)
    toroid = None
    if dif:
        p.append(Ellipse((0, -5.4), 2.4, 1.0)); toroid = (2.4, -5.4)
    labels = (["I>"] if release else []) + (["IΔ"] if dif else []) + (["BD"] if bd else [])
    _relee(p, labels, mid, toroid)
    p.anc.setdefault("masura", (3.6, 0)); p.anc.setdefault("comanda", (3.6, 0))


def sep_fuzibil(p, d):
    """separator tripolar cu siguranțe fuzibile (SF / MPR) — cuțitul poartă fuzibilul"""
    p.append(Line((0, HALF), (0, YF + 1), "FORTA")); _mark(p, "bar", YF + 1)
    hx, hy = 0, YH
    ex, ey = 4.2, YF + 0.4
    p.append(Line((hx, hy), (ex, ey), "FORTA"))
    L = math.hypot(ex - hx, ey - hy); ux, uy = (ex - hx) / L, (ey - hy) / L; nx, ny = -uy, ux
    a, b, w = 2.4, 8.4, 1.6
    f = [(hx + ux * t + nx * s_, hy + uy * t + ny * s_) for t, s_ in ((a, -w), (b, -w), (b, w), (a, w))]
    p.append(Polyline(f, "SIMBOL", True))
    p.append(Line((-1.2, hy), (1.2, hy))); p.append(Line((0, hy), (0, -HALF), "FORTA"))
    p.anc["masura"] = (4.5, 0); p.anc["comanda"] = (4.5, 0)


def separator(p, d):
    """întreruptor-separator (separator de sarcină, separare vizibilă)"""
    _switch(p, "bar_cerc"); p.anc["masura"] = (3.6, 0); p.anc["comanda"] = (3.6, 0)


def fuzibil(p, d):
    """siguranță fuzibilă"""
    p.append(Line((0, HALF), (0, 4), "FORTA")); p.append(Rect((-1.8, -4), 3.6, 8))
    p.append(Line((0, 4), (0, -4))); p.append(Line((0, -4), (0, -HALF), "FORTA"))


def gpv(p, d):
    """siguranță fuzibilă gPV pe circuitul de c.c. al stringurilor"""
    fuzibil(p, d); p.append(Text((2.8, -0.6), "gPV", 1.6, True))


def mccb(p, d): _breaker(p, d, release=True, bd=bool(d.get("bd")))
def mcb(p, d): _breaker(p, d, release=True, bd=bool(d.get("bd")))
def mccb_dif(p, d): _breaker(p, d, release=True, dif=True, bd=bool(d.get("bd")))
def rccb(p, d): _breaker(p, d, release=False, dif=True, bd=bool(d.get("bd")))


def rcbo(p, d):
    """întreruptor automat cu protecție diferențială încorporată 1P+N (RCBO)"""
    _breaker(p, d, release=True, dif=True, bd=bool(d.get("bd")))
    p.append(Text((BOX_X + BOX_W / 2, 5.6), "1P+N", 1.4, True, align="middle"))


def acb(p, d):
    """întreruptor automat de putere în aer (ACB), debroșabil"""
    _breaker(p, d, release=True, bd=bool(d.get("bd")))
    p.append(Polyline([(-1.5, 8.2), (0, 7.1), (1.5, 8.2)])); p.append(Polyline([(-1.5, -7.7), (0, -6.5), (1.5, -7.7)]))


def intreruptor_mt(p, d):
    """întreruptor MT: un singur X, pe contactul fix; BD (bobină de declanșare) dacă e comandat de un releu"""
    mid = _switch(p, "x")
    if d.get("bd"): _relee(p, ["BD"], mid)
    p.anc.setdefault("masura", (3.6, 0)); p.anc.setdefault("comanda", (3.6, 0))


def _clp(p, y):
    """cuțit de legare la pământ (CLP), în stânga, legat la conductorul de sub separator"""
    p.append(Line((0, y), (-3.0, y))); p.append(Line((-3.0, y), (-6.4, y + 1.6)))
    p.append(Line((-6.8, y - 0.9), (-6.8, y + 0.9)))     # contactul fix al CLP (bară)
    p.append(Line((-6.8, y), (-8.2, y)))
    for i, w in enumerate((1.6, 1.0, 0.4)):
        xx = -8.2 - 0.7 * i; p.append(Line((xx, y - w), (xx, y + w)))


def sep_mt(p, d):
    """separator de sarcină MT (bară + cerc pe contactul fix) cu cuțit de legare la pământ"""
    _switch(p, "bar_cerc"); _clp(p, -6.6); p.append(Circle((0, -6.6), 0.45, "HASURA"))
    p.anc["masura"] = (3.6, 0); p.anc["comanda"] = (3.6, 0)


def sigurante_mt(p, d):
    """celulă de transformator MT: separator de sarcină + siguranțe MT (combinație SR EN 62271-105)"""
    mid = _switch(p, "bar_cerc", yf=5.6, yh=-0.6)
    p.append(Rect((-1.4, -7.0), 2.8, 5.2)); p.append(Line((0, -1.8), (0, -7.0)))
    p.append(Line((1.4, -4.4), (5.2, -4.4), "MECANIC")); p.append(Line((5.2, -4.4), (5.2, mid[1]), "MECANIC"))
    p.append(Line((5.2, mid[1]), mid, "MECANIC"))           # percutorul fuzibilului deschide separatorul
    p.anc["masura"] = (5.2, 0); p.anc["comanda"] = (5.2, mid[1])


def separator_cc(p, d):
    """separator de c.c. sub sarcină (pe intrarea MPPT)"""
    _switch(p, "bar_cerc"); p.append(Text((5.6, 1.0), "=", 2.6, True, align="middle"))
    p.anc["masura"] = (3.6, 0); p.anc["comanda"] = (3.6, 0)


def tc(p, d):
    """transformator de curent: cerc traversat de conductorul primar; secundarul iese în dreapta"""
    p.append(Line((0, HALF), (0, -HALF), "FORTA")); p.append(Circle((0, 0), 4))
    p.anc["masura"] = (4, 0)


def contor_direct(p, d):
    """contor cu conectare directă (conductorul trece prin contor)"""
    p.append(Line((0, HALF), (0, 5), "FORTA")); p.append(Rect((-7, -5), 14, 10)); p.append(Text((0, -1.1), "kWh", 2.4, True, align="middle"))
    p.append(Line((0, -5), (0, -HALF), "FORTA"))


def trafo(p, d):
    """transformator de putere MT/JT (două înfășurări); `neutru_pamant` = neutrul JT legat la pământ"""
    p.append(Line((0, HALF), (0, 4.2), "FORTA")); p.append(Circle((0, 1.6), 4.2)); p.append(Circle((0, -3.6), 4.2))
    p.append(Line((0, -7.8), (0, -HALF), "FORTA"))
    if d.get("neutru_pamant"):
        p.append(Line((2.6, -3.6), (8.0, -3.6))); p.append(Circle((2.6, -3.6), 0.45, "HASURA"))
        p.append(Text((5.4, -3.0), "N", 1.6, True, align="middle"))
        p.append(Line((8.0, -3.6), (8.0, -5.6))); pamant(p, d, (8.0, -5.6), 2.4)


def invertor(p, d):
    """invertor (convertor c.c./c.a.)"""
    p.append(Line((0, HALF), (0, 6), "FORTA")); p.append(Rect((-7, -6), 14, 12)); p.append(Line((-7, -6), (7, 6)))
    p.append(Text((-5.5, 2.2), "=", 2.6, True, align="middle")); p.append(Text((5.5, -4.6), "~", 2.6, True, align="middle"))
    p.append(Line((0, -6), (0, -HALF), "FORTA"))


def convertor_bess(p, d):
    """convertor bidirecțional + baterie (BESS)"""
    p.append(Line((0, HALF), (0, 6), "FORTA")); p.append(Rect((-7, -6), 14, 12)); p.append(Line((-7, -6), (7, 6)))
    p.append(Text((-5.5, 2.2), "~", 2.6, True, align="middle")); p.append(Text((5.5, -4.6), "=", 2.6, True, align="middle"))
    p.append(Line((0, -6), (0, -HALF), "FORTA"))


def ats(p, d):
    """comutator de sarcină cu interblocaj (sursa A / sursa B)"""
    p.append(Line((0, HALF), (0, YF), "FORTA")); _mark(p, "bar", YF)
    p.append(Line((8, HALF), (8, YF), "FORTA")); _mark_x = 8
    p.append(Line((_mark_x - 1.8, YF), (_mark_x + 1.8, YF)))
    p.append(Line((0, YH), (5.6, YF - 0.6), "FORTA")); p.append(Line((-1.2, YH), (1.2, YH)))
    p.append(Line((0, YH), (0, -HALF), "FORTA"))
    p.append(Text((8, HALF + 1), "B", 2.0, True, align="middle"))


def contact(p, d):
    """contactor (semicerc pe contactul fix)"""
    _switch(p, "semicerc"); p.anc["masura"] = (3.6, 0); p.anc["comanda"] = (3.6, 0)


def releu_termic(p, d):
    """releu termic de suprasarcină (IEC 60617 07-15-21): dreptunghi cu elementul termic (meandru) pe conductor"""
    p.append(Line((0, HALF), (0, 4), "FORTA")); p.append(Rect((-3.2, -4), 6.4, 8))
    p.append(Polyline([(0, 4), (0, 2), (1.6, 2), (1.6, -2), (-1.6, -2), (-1.6, 0), (0, 0), (0, -4)], "FORTA"))
    p.append(Line((0, -4), (0, -HALF), "FORTA"))


def convertizor(p, d):
    """convertizor de frecvență / soft-starter (IEC 60617 06-14-01): dreptunghi cu diagonală, „~” în ambele colțuri"""
    p.append(Line((0, HALF), (0, 6), "FORTA")); p.append(Rect((-7, -6), 14, 12)); p.append(Line((-7, -6), (7, 6)))
    p.append(Text((-4.2, 1.6), "~", 2.6, True, align="middle")); p.append(Text((4.2, -4.6), "~", 2.6, True, align="middle"))
    p.append(Line((0, -6), (0, -HALF), "FORTA"))


def pornitor_yd(p, d):
    """pornitor stea-triunghi (contactoarele KΔ + KY): dreptunghi cu marcajul Y/Δ"""
    p.append(Line((0, HALF), (0, 5), "FORTA")); p.append(Rect((-6, -5), 12, 10))
    p.append(Text((0, -1.0), "Y/Δ", 2.6, True, align="middle"))
    p.append(Line((0, -5), (0, -HALF), "FORTA"))


def nod(p, d):
    """nod / trecere directă (fără aparat)"""
    p.append(Line((0, HALF), (0, -HALF), "FORTA"))

# ---------------------------------------------------------------- simboluri laterale / terminale
def spd(p, d):
    """descărcător de supratensiune (SPD) cu legare la pământ — se desenează la bază (0,0) spre jos"""
    p.append(Line((0, 0), (0, -3), "FORTA")); p.append(Rect((-3, -9), 6, 6)); p.append(Polyline([(-1.6, -8), (0, -4), (1.6, -8)]))
    p.append(Line((0, -9), (0, -12), "PE"))
    if not d.get("fara_pamant"):      # legat la bara PE a tabloului (traseul PE se desenează separat)
        pamant(p, d, (0, -12))

def spd_cc(p, d):
    """descărcător de supratensiune de c.c. (tip 2, pe intrarea MPPT)"""
    spd(p, d); p.append(Text((-4.4, -7.2), "=", 2.4, True, align="right"))

def descarcator_mt(p, d):
    """descărcător de supratensiune MT (ZnO) cu legare la pământ — la bază (0,0) spre jos"""
    p.append(Line((0, 0), (0, -2.5), "FORTA")); p.append(Rect((-2.2, -11), 4.4, 8.5))
    p.append(Line((0, -3.6), (0, -8.2))); p.append(Solid([(0, -10.0), (-0.9, -8.0), (0.9, -8.0)]))
    p.append(Line((0, -11), (0, -13), "PE")); pamant(p, d, (0, -13))

def pamant(p, d, at=(0, 0), w=4.5):
    """priză de pământ: trei linii continue, descrescătoare (IEC 60617 02-15-01)"""
    x, y = at
    for i, f in enumerate((1.0, 2 / 3, 1 / 3)):
        p.append(Line((x - w * f, y - 1.6 * i * w / 4.5), (x + w * f, y - 1.6 * i * w / 4.5), "SIMBOL"))

def contor(p, d):
    """contor (bloc lateral) — centrat la (0,0)"""
    p.append(Rect((-14, -8), 28, 16)); p.append(Text((0, 2.2), d.get("eticheta", "kWh · kVArh"), 2.6, True, align="middle"))
    for i, s in enumerate(d.get("spec", [])[:2]):
        p.append(Text((0, -1.8 - 3.4*i), s, 2.0, align="middle", layer="TEXT_GRI" if i else "TEXT"))

def cleme(p, d):
    """șir de cleme cu bloc de șuntare (K) — centrat la (0,0)"""
    p.append(Rect((-6, -2.6), 12, 5.2))
    for x in (-3.6, -1.2, 1.2, 3.6): p.append(Circle((x, 0), 0.5, "HASURA"))
    p.append(Line((-4.5, 1.4), (4.5, 1.4)))

def fuzibil_lat(p, d):
    """siguranță fuzibilă pe un circuit de măsură/tensiune (orizontal) — centrată la (0,0)"""
    p.append(Rect((-4, -1.8), 8, 3.6)); p.append(Line((-4, 0), (4, 0)))

def cutie(p, d):
    """bloc lateral generic (DPST, IEMS, protecție interfață) — centrat la (0,0)"""
    w, h = d.get("w", 28), d.get("h", 12)
    p.append(Rect((-w/2, -h/2), w, h)); p.append(Text((0, h/2 - 4.2), d.get("eticheta", ""), 2.6, True, align="middle"))
    for i, s in enumerate(d.get("spec", [])[:2]):
        p.append(Text((0, h/2 - 7.8 - 3.2*i), s, 2.0, align="middle", layer="TEXT_GRI"))

def bareta_nul(p, d):
    """baretă de nul (BN) cu separare PEN -> N + PE; la (0,0) este nodul de pe linia de forță"""
    if not d.get("fara_legatura"):
        p.append(Line((0, 0), (-29, 0)))
    p.append(Solid([(-39, -1.6), (-29, -1.6), (-29, 1.6), (-39, 1.6)]))
    p.append(Text((-41, -0.8), d.get("eticheta") or "BN", 2.6, True, align="right"))
    p.append(Text((-32.6, -4.6), d.get("nota") if d.get("nota") is not None else "PEN → N + PE", 1.8, layer="TEXT_GRI"))

def piesa_separatie(p, d):
    p.append(Rect((-2.6, -3.5), 5.2, 7)); p.append(Line((-1.6, -3.5), (1.6, 3.5)))
    p.append(Text((-4.5, -0.9), "PS", 2.6, True, align="right"))

def string_pv(p, d):
    """câmp PV: modul + „× n stringuri”; borna de ieșire jos la (0,-HALF)"""
    p.append(Rect((-9, -4), 7, 9)); p.append(Line((-9, -4), (-2, 5))); p.append(Line((-9, 5), (-2, -4)))
    p.append(Rect((-0.5, -4), 7, 9)); p.append(Line((-0.5, -4), (6.5, 5))); p.append(Line((-0.5, 5), (6.5, -4)))
    p.append(Text((9, -0.5), d.get("eticheta", "× n"), 2.4, True))
    p.append(Line((-5.5, -4), (-5.5, -6))); p.append(Line((3, -4), (3, -6))); p.append(Line((-5.5, -6), (3, -6)))
    p.append(Line((0, -6), (0, -HALF), "FORTA"))

def baterie(p, d):
    """baterie (bloc BESS) — borna sus la (0, HALF)"""
    p.append(Line((0, HALF), (0, 4), "FORTA"))
    for i, w in enumerate((5, 2.5, 5, 2.5)):
        y = 3 - 2.2*i; p.append(Line((-w, y), (w, y), "FORTA" if w > 3 else "SIMBOL"))
    p.append(Line((0, -4), (0, -HALF), "FORTA"))

def generator(p, d):
    p.append(Line((0, HALF), (0, 5), "FORTA")); p.append(Circle((0, 0), 5)); p.append(Text((0, -1.2), "G", 3.0, True, align="middle"))
    p.append(Text((0, -4), "~", 2.0, align="middle")); p.append(Line((0, -5), (0, -HALF), "FORTA"))
    if d.get("neutru_pamant"):      # neutrul GE legat la priza de pământ locală (TN-S)
        p.append(Line((3.5, -3.6), (8.0, -3.6))); p.append(Circle((3.5, -3.6), 0.45, "HASURA"))
        p.append(Text((5.8, -3.0), "N", 1.6, True, align="middle"))
        p.append(Line((8.0, -3.6), (8.0, -5.6))); pamant(p, d, (8.0, -5.6), 2.4)

def motor(p, d):
    p.append(Line((0, HALF), (0, 5), "FORTA")); p.append(Circle((0, 0), 5)); p.append(Text((0, -1.2), "M", 3.0, True, align="middle"))
    p.append(Text((0, -4), "3~", 1.8, align="middle")); p.append(Line((0, -5), (0, -HALF), "FORTA"))

# ---------------------------------------------------------------- registru
SYMBOLS = {
 # cheie: (funcție, denumire RO, categorie)   categorie: serie | lateral | terminal
 "nod":           (nod, "Trecere / nod", "serie"),
 "sep_fuzibil":   (sep_fuzibil, "Separator cu siguranțe fuzibile (SF / MPR)", "serie"),
 "separator":     (separator, "Întreruptor-separator", "serie"),
 "fuzibil":       (fuzibil, "Siguranță fuzibilă", "serie"),
 "mccb":          (mccb, "Întreruptor automat MCCB", "serie"),
 "mcb":           (mcb, "Întreruptor automat MCB", "serie"),
 "mccb_dif":      (mccb_dif, "Întreruptor automat cu protecție diferențială", "serie"),
 "rccb":          (rccb, "Întreruptor diferențial (RCCB)", "serie"),
 "rcbo":          (rcbo, "Întreruptor automat cu protecție diferențială 1P+N (RCBO)", "serie"),
 "acb":           (acb, "Întreruptor automat de putere în aer (ACB), debroșabil", "serie"),
 "tc":            (tc, "Transformator de curent (TC)", "serie"),
 "contor_direct": (contor_direct, "Contor cu conectare directă", "serie"),
 "trafo":         (trafo, "Transformator de putere", "serie"),
 "intreruptor_mt":(intreruptor_mt, "Întreruptor MT", "serie"),
 "sep_mt":        (sep_mt, "Separator de sarcină MT cu CLP", "serie"),
 "sigurante_mt":  (sigurante_mt, "Celulă trafo MT: separator de sarcină + siguranțe MT", "serie"),
 "separator_cc":  (separator_cc, "Separator de c.c. sub sarcină", "serie"),
 "gpv":           (gpv, "Siguranță fuzibilă gPV (c.c.)", "serie"),
 "invertor":      (invertor, "Invertor fotovoltaic", "serie"),
 "convertor_bess":(convertor_bess, "Convertor bidirecțional BESS", "serie"),
 "ats":           (ats, "Comutator automat de sursă (AAR / ATS)", "serie"),
 "contact":       (contact, "Contactor", "serie"),
 "releu_termic":  (releu_termic, "Releu termic de suprasarcină", "serie"),
 "convertizor":   (convertizor, "Convertizor de frecvență / soft-starter", "serie"),
 "pornitor_yd":   (pornitor_yd, "Pornitor stea-triunghi (KΔ + KY)", "serie"),
 "string_pv":     (string_pv, "Câmp fotovoltaic (stringuri)", "serie"),
 "baterie":       (baterie, "Baterie de acumulatori", "serie"),
 "generator":     (generator, "Generator", "serie"),
 "motor":         (motor, "Motor", "serie"),
 # laterale
 "spd":           (spd, "Descărcător de supratensiune (SPD)", "lateral"),
 "spd_cc":        (spd_cc, "Descărcător de supratensiune c.c. (SPD tip 2)", "lateral"),
 "descarcator_mt":(descarcator_mt, "Descărcător de supratensiune MT (ZnO)", "lateral"),
 "contor":        (contor, "Contor (bloc lateral)", "lateral"),
 "cleme":         (cleme, "Șir de cleme cu bloc de șuntare (K)", "lateral"),
 "fuzibil_lat":   (fuzibil_lat, "Siguranță fuzibilă pe circuit de măsură (F)", "lateral"),
 "cutie":         (cutie, "Bloc lateral (DPST / IEMS / protecție)", "lateral"),
 "bareta_nul":    (bareta_nul, "Baretă de nul (BN)", "lateral"),
 "piesa_separatie":(piesa_separatie, "Piesă de separație (PS)", "lateral"),
 "pamant":        (pamant, "Priză de pământ", "lateral"),
}

def draw(key, d=None):
    """întoarce lista de primitive locale ale simbolului `key` (cu ancorele în atributul `.anc`)"""
    d = d or {}
    prims = _Prims()
    SYMBOLS[key][0](prims, d)
    return prims
