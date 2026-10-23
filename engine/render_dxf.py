"""Randare Canvas -> DXF R2018 (AutoCAD 2018-2025), simboluri ca blocuri cu atribute.

Numele blocului depinde de geometria efectivă a simbolului: două inserări cu geometrie diferită
(de ex. MCCB cu / fără bobină BD, `cutie` de dimensiuni diferite) nu partajează niciodată un bloc.
Prima variantă păstrează numele de bază (`SYM_MCCB`, `SYM_MCCB_BD` …), următoarele primesc un sufix
scurt derivat din geometrie (`SYM_CUTIE_3F9A1C`)."""
import hashlib
import ezdxf
from ezdxf import units
from ezdxf.enums import TextEntityAlignment as TA
from .canvas import *

ALIGN = {"left": TA.LEFT, "middle": TA.CENTER, "right": TA.RIGHT}


def _emit(space, items, dx=0.0, dy=0.0, k=1.0, reg=None):
    def P(p): return (p[0] * k + dx, p[1] * k + dy)
    for it in items:
        if isinstance(it, Line):
            space.add_line(P(it.a), P(it.b), dxfattribs={"layer": it.layer})
        elif isinstance(it, Polyline):
            space.add_lwpolyline([P(p) for p in it.pts], close=it.closed, dxfattribs={"layer": it.layer})
        elif isinstance(it, Rect):
            x, y = it.p
            space.add_lwpolyline([P((x, y)), P((x + it.w, y)), P((x + it.w, y + it.h)), P((x, y + it.h))], close=True, dxfattribs={"layer": it.layer})
        elif isinstance(it, Circle):
            if it.layer == "HASURA":
                h = space.add_hatch(color=7, dxfattribs={"layer": "HASURA"})
                h.paths.add_edge_path().add_ellipse(P(it.c), major_axis=(it.r * k, 0), ratio=1)
            else:
                space.add_circle(P(it.c), it.r * k, dxfattribs={"layer": it.layer})
        elif isinstance(it, Ellipse):
            space.add_ellipse(P(it.c), major_axis=(it.rx * k, 0), ratio=it.ry / it.rx, dxfattribs={"layer": it.layer})
        elif isinstance(it, Solid):
            space.add_solid([P(p) for p in it.pts], dxfattribs={"layer": it.layer, "color": LAYERS[it.layer][0]})
        elif isinstance(it, Text):
            st = "ARIAL_B" if it.bold else ("ARIAL_I" if it.italic else "ARIAL")
            t = space.add_text(it.s, dxfattribs={"layer": it.layer, "style": st, "height": it.h * k, "rotation": it.rot or 0.0})
            t.set_placement(P(it.p), align=ALIGN[it.align])
        elif isinstance(it, BlockRef):
            _insert_block(space, it, dx, dy, k, reg if reg is not None else {})


def _semnatura(prims):
    """amprenta geometriei unui simbol (fără texte, care se emit separat)"""
    def r(v): return round(float(v), 3)
    parts = []
    for p in prims:
        if isinstance(p, Text): continue
        if isinstance(p, Line): parts.append(("L", p.layer, r(p.a[0]), r(p.a[1]), r(p.b[0]), r(p.b[1])))
        elif isinstance(p, (Polyline, Solid)): parts.append((type(p).__name__, p.layer, getattr(p, "closed", True), tuple((r(x), r(y)) for x, y in p.pts)))
        elif isinstance(p, Rect): parts.append(("R", p.layer, r(p.p[0]), r(p.p[1]), r(p.w), r(p.h)))
        elif isinstance(p, Circle): parts.append(("C", p.layer, r(p.c[0]), r(p.c[1]), r(p.r)))
        elif isinstance(p, Ellipse): parts.append(("E", p.layer, r(p.c[0]), r(p.c[1]), r(p.rx), r(p.ry)))
    return hashlib.sha1(repr(parts).encode()).hexdigest()[:6].upper()


def _nume_bloc(doc, br, reg):
    sig = _semnatura(br.prims)
    name = br.name
    if reg.get(name, sig) != sig:          # numele de bază e luat de altă geometrie
        name = f"{br.name}_{sig}"
    if name not in reg:
        reg[name] = sig
        blk = doc.blocks.new(name=name)
        _emit(blk, [p for p in br.prims if not isinstance(p, Text)])
        for i, tag in enumerate(br.attribs):
            a = blk.add_attdef(tag, (0, -8 - 3.5 * i), dxfattribs={"height": 2.3, "style": "ARIAL", "layer": "TEXT", "invisible": 1})
            a.dxf.prompt = tag
    return name


def _insert_block(space, br: BlockRef, dx, dy, k, reg):
    doc = space.doc
    name = _nume_bloc(doc, br, reg)
    kk = k * br.scale
    pos = (br.p[0] * k + dx, br.p[1] * k + dy)
    ins = space.add_blockref(name, pos, dxfattribs={"layer": br.layer, "xscale": kk, "yscale": kk})
    # atribute: valorile reale; textele vizibile ale simbolului se emit ca TEXT normal, lângă bloc
    for i, (tag, val) in enumerate(br.attribs.items()):
        ins.add_attrib(tag, str(val), insert=(pos[0], pos[1] - (8 + 3.5 * i) * kk), dxfattribs={"invisible": 1, "height": 2.3 * kk, "layer": "TEXT"})
    _emit(space, [p for p in br.prims if isinstance(p, Text)], pos[0], pos[1], kk)


def render(c: Canvas, path: str, layout_name="A3"):
    doc = ezdxf.new("R2018", setup=True)
    doc.units = units.MM
    doc.header["$INSUNITS"] = 4
    doc.header["$LTSCALE"] = 1.0
    doc.header["$PSLTSCALE"] = 0
    for name, (aci, lw, lt, _) in LAYERS.items():
        l = doc.layers.add(name, color=aci)
        l.dxf.lineweight = lw
        l.dxf.linetype = lt
    doc.styles.add("ARIAL", font="arial.ttf")
    doc.styles.add("ARIAL_B", font="arialbd.ttf")
    doc.styles.add("ARIAL_I", font="ariali.ttf")
    msp = doc.modelspace()
    _emit(msp, c.items, reg={})
    lay = doc.layouts.get("Layout1")
    lay.page_setup(size=(c.w, c.h), margins=(0, 0, 0, 0), units="mm", scale=1)
    lay.add_viewport(center=(c.w/2, c.h/2), size=(c.w, c.h), view_center_point=(c.w/2, c.h/2), view_height=c.h)
    doc.set_modelspace_vport(height=c.h*1.08, center=(c.w/2, c.h/2))
    doc.saveas(path)
    return path
