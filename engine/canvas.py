"""Canvas abstract: o listă de primitive geometrice în mm (origine stânga-jos, y în sus).
Același canvas este randat în SVG (previzualizare / PDF) și în DXF (AutoCAD).
Layerele poartă culoarea, grosimea și tipul de linie."""
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import math

Pt = Tuple[float, float]

LAYERS = {
    # nume: (culoare ACI, lineweight 1/100 mm, linetype, culoare svg)
    "CHENAR":   (7, 50, "CONTINUOUS", "#000"),
    "FORTA":    (7, 70, "CONTINUOUS", "#000"),
    "SIMBOL":   (7, 35, "CONTINUOUS", "#000"),
    "MASURA":   (5, 25, "DASHED",     "#1a5fb4"),
    "COMANDA":  (1, 25, "DOT",        "#c00"),
    "MECANIC":  (7, 25, "DASHED",     "#000"),   # legătură mecanică (declanșator ↔ contact)
    "COMUNIC":  (150, 25, "DASHED",   "#7a3fb4"),
    "PE":       (3, 35, "DASHED",     "#1a7f37"),
    "CARCASA":  (7, 35, "DASHEDX2",   "#000"),
    "TEXT":     (7, 18, "CONTINUOUS", "#000"),
    "TEXT_GRI": (8, 18, "CONTINUOUS", "#555"),
    "TABEL":    (7, 18, "CONTINUOUS", "#000"),
    "CARTUS":   (7, 35, "CONTINUOUS", "#000"),
    "HASURA":   (7, 18, "CONTINUOUS", "#000"),
}
DASH_SVG = {"DASHED": "2.4 1.2", "DOT": "0.5 0.9", "DASHEDX2": "3.6 1.8", "CONTINUOUS": None}


@dataclass
class Line:
    a: Pt; b: Pt; layer: str = "SIMBOL"

@dataclass
class Polyline:
    pts: List[Pt]; layer: str = "SIMBOL"; closed: bool = False

@dataclass
class Circle:
    c: Pt; r: float; layer: str = "SIMBOL"

@dataclass
class Ellipse:
    c: Pt; rx: float; ry: float; layer: str = "SIMBOL"

@dataclass
class Solid:        # poligon umplut (vârf de săgeată, punct de nod, baretă)
    pts: List[Pt]; layer: str = "HASURA"

@dataclass
class Text:
    p: Pt; s: str; h: float = 2.5; bold: bool = False; italic: bool = False
    align: str = "left"   # left | middle | right
    layer: str = "TEXT"
    rot: float = 0.0      # grade, sens trigonometric (90 = citire de jos în sus, de-a lungul unui cablu vertical)

@dataclass
class Rect:
    p: Pt; w: float; h: float; layer: str = "SIMBOL"; fill: Optional[str] = None  # fill doar în svg

@dataclass
class BlockRef:
    """Inserție de bloc (simbol) cu atribute. Geometria blocului se desenează
    în DXF o singură dată (definiție), în SVG se expandează inline."""
    name: str; p: Pt; attribs: dict; prims: List[object]; layer: str = "SIMBOL"
    uid: str = ""   # doar pentru previzualizare (legătura planșă ↔ formular); nu ajunge în DXF
    scale: float = 1.0   # factor de scară al inserției (planșa A2 scalată)


@dataclass
class Canvas:
    w: float = 420.0
    h: float = 297.0
    items: List[object] = field(default_factory=list)
    blocks: dict = field(default_factory=dict)   # name -> (prims locale, attdefs)
    meta: dict = field(default_factory=dict)     # topologia desenului (carcase, surse, legături, poziții) — vezi layout.py

    def add(self, *it): self.items.extend(it)

    # --- helpers ---
    def line(self, a, b, layer="SIMBOL"): self.add(Line(a, b, layer))
    def pl(self, pts, layer="SIMBOL", closed=False): self.add(Polyline(list(pts), layer, closed))
    def rect(self, x, y, w, h, layer="SIMBOL", fill=None): self.add(Rect((x, y), w, h, layer, fill))
    def circle(self, c, r, layer="SIMBOL"): self.add(Circle(c, r, layer))
    def ellipse(self, c, rx, ry, layer="SIMBOL"): self.add(Ellipse(c, rx, ry, layer))
    def dot(self, c, r=1.0): self.add(Circle(c, r, "HASURA"))   # randat plin
    def text(self, x, y, s, h=2.5, bold=False, italic=False, align="left", layer="TEXT", rot=0.0):
        if s is None or s == "": return
        self.add(Text((x, y), str(s), h, bold, italic, align, layer, rot))
    def arrow(self, tip, d, size=2.4, layer="HASURA"):
        x, y = tip; s = size
        if d == "down":  pts = [(x, y), (x - .45*s, y + s), (x + .45*s, y + s)]
        elif d == "up":  pts = [(x, y), (x - .45*s, y - s), (x + .45*s, y - s)]
        elif d == "right": pts = [(x, y), (x - s, y - .45*s), (x - s, y + .45*s)]
        else: pts = [(x, y), (x + s, y - .45*s), (x + s, y + .45*s)]
        self.add(Solid(pts, layer))
    def slash(self, x, y, label=None, layer="SIMBOL"):
        """marcaj de conductoare pe o linie verticală + etichetă la dreapta"""
        self.line((x - 3, y - 1.8), (x + 3, y + 1.8), layer)
        if label: self.text(x + 4.5, y - 0.9, label, 2.3)


# ---------------------------------------------------------------- geometrie: casete de încadrare (mm)
CHAR_W = 1.45 / 2.1      # lățimea medie a unui caracter Arial, raportată la înălțimea textului


_NARROW = set("iljtfrI.,:;'|!()[]·- ")
_WIDE = set("mwMW%@")


def _char_em(ch):
    """lățimea aproximativă a unui caracter Arial, în em"""
    if ch in _NARROW: return 0.30
    if ch in _WIDE: return 0.86
    if ch.isdigit(): return 0.56
    if ch.isupper(): return 0.70
    if ch in "×≤≥±→ΔΩ≈": return 0.62
    return 0.53


def text_width(s, h, bold=False):
    """lățimea estimată (mm) a unui text Arial cu înălțimea majusculei h (em ≈ h / 0,72)"""
    return sum(_char_em(ch) for ch in (s or "")) * h / 0.72 * (1.07 if bold else 1.0)


def text_bbox(t: "Text", dx=0.0, dy=0.0, k=1.0):
    """caseta (x1, y1, x2, y2) estimată a unui text: lungime × înălțime, rotit în jurul punctului de inserție"""
    h = t.h * k; w = text_width(t.s, h, t.bold)
    x0 = {"left": 0.0, "middle": -w / 2, "right": -w}[t.align]
    loc = [(x0, -0.22 * h), (x0 + w, -0.22 * h), (x0 + w, h), (x0, h)]
    a = math.radians(t.rot or 0.0); ca, sa = math.cos(a), math.sin(a)
    px, py = t.p[0] * k + dx, t.p[1] * k + dy
    pts = [(px + x * ca - y * sa, py + x * sa + y * ca) for x, y in loc]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def prim_bbox(it, dx=0.0, dy=0.0, k=1.0):
    """caseta unei primitive geometrice (fără texte); None pentru texte"""
    def T(p): return (p[0] * k + dx, p[1] * k + dy)
    if isinstance(it, Line): pts = [T(it.a), T(it.b)]
    elif isinstance(it, (Polyline, Solid)): pts = [T(p) for p in it.pts]
    elif isinstance(it, Rect): pts = [T(it.p), T((it.p[0] + it.w, it.p[1] + it.h))]
    elif isinstance(it, Circle): pts = [T((it.c[0] - it.r, it.c[1] - it.r)), T((it.c[0] + it.r, it.c[1] + it.r))]
    elif isinstance(it, Ellipse): pts = [T((it.c[0] - it.rx, it.c[1] - it.ry)), T((it.c[0] + it.rx, it.c[1] + it.ry))]
    else: return None
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def block_bbox(br: "BlockRef", texts=False):
    """caseta geometriei unui simbol inserat (fără textele lui, dacă texts=False)"""
    bb = None
    for p in br.prims:
        b = text_bbox(p, br.p[0], br.p[1], br.scale) if isinstance(p, Text) else prim_bbox(p, br.p[0], br.p[1], br.scale)
        if b is None or (isinstance(p, Text) and not texts): continue
        bb = b if bb is None else (min(bb[0], b[0]), min(bb[1], b[1]), max(bb[2], b[2]), max(bb[3], b[3]))
    return bb


def iter_texts(items):
    """toate textele planșei în coordonate absolute: (Text, caseta)"""
    for it in items:
        if isinstance(it, Text): yield it, text_bbox(it)
        elif isinstance(it, BlockRef):
            for p in it.prims:
                if isinstance(p, Text): yield p, text_bbox(p, it.p[0], it.p[1], it.scale)


def bbox_union(a, b):
    if a is None: return b
    if b is None: return a
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def bbox_overlap(a, b, tol=0.0):
    """True dacă două casete se suprapun cu mai mult de `tol` mm pe ambele axe"""
    return min(a[2], b[2]) - max(a[0], b[0]) > tol and min(a[3], b[3]) - max(a[1], b[1]) > tol


def seg_hits_box(a, b, box, tol=0.0):
    """True dacă segmentul a–b intră în caseta `box` micșorată cu `tol`"""
    x1, y1, x2, y2 = box[0] + tol, box[1] + tol, box[2] - tol, box[3] - tol
    if x1 >= x2 or y1 >= y2: return False
    (ax, ay), (bx, by) = a, b
    t0, t1 = 0.0, 1.0; dx, dy = bx - ax, by - ay
    for p, q in ((-dx, ax - x1), (dx, x2 - ax), (-dy, ay - y1), (dy, y2 - ay)):
        if abs(p) < 1e-12:
            if q < 0: return False
        else:
            r = q / p
            if p < 0: t0 = max(t0, r)
            else: t1 = min(t1, r)
            if t0 > t1: return False
    return True


def item_segments(it):
    """segmentele unei primitive liniare (Line, Polyline, Rect)"""
    if isinstance(it, Line): return [(it.a, it.b)]
    if isinstance(it, Polyline):
        pts = it.pts + ([it.pts[0]] if it.closed else [])
        return list(zip(pts, pts[1:]))
    if isinstance(it, Rect):
        x, y, w, h = it.p[0], it.p[1], it.w, it.h
        c = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
        return list(zip(c, c[1:]))
    return []


def transform_item(it, k, ox, oy):
    """scalează (factor k, față de origine) și translatează o primitivă de nivel superior; întoarce primitiva nouă"""
    from dataclasses import replace
    def T(p): return (p[0] * k + ox, p[1] * k + oy)
    if isinstance(it, Line): return replace(it, a=T(it.a), b=T(it.b))
    if isinstance(it, Polyline): return replace(it, pts=[T(p) for p in it.pts])
    if isinstance(it, Solid): return replace(it, pts=[T(p) for p in it.pts])
    if isinstance(it, Rect): return replace(it, p=T(it.p), w=it.w * k, h=it.h * k)
    if isinstance(it, Circle): return replace(it, c=T(it.c), r=it.r * k)
    if isinstance(it, Ellipse): return replace(it, c=T(it.c), rx=it.rx * k, ry=it.ry * k)
    if isinstance(it, Text): return replace(it, p=T(it.p), h=it.h * k)
    if isinstance(it, BlockRef): return replace(it, p=T(it.p), scale=it.scale * k)
    return it
