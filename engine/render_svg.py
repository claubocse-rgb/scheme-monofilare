"""Randare Canvas -> SVG (mm, A3/A2 landscape)."""
from .canvas import *
import html

LW_SVG = {18: 0.18, 25: 0.25, 35: 0.35, 50: 0.5, 70: 0.7}

def _style(layer):
    aci, lw, lt, col = LAYERS[layer]
    s = f'stroke="{col}" stroke-width="{LW_SVG.get(lw, 0.35)}" fill="none"'
    d = DASH_SVG.get(lt)
    if d: s += f' stroke-dasharray="{d}"'
    return s

def render(c: Canvas, title="Schema") -> str:
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{c.w}mm" height="{c.h}mm" viewBox="0 0 {c.w} {c.h}">',
           f'<title>{html.escape(title)}</title>',
           '<style>text{font-family:Arial,Helvetica,sans-serif}</style>',
           f'<rect x="0" y="0" width="{c.w}" height="{c.h}" fill="#fff"/>']

    def emit(items, dx=0.0, dy=0.0, k=1.0):
        def P(p): return p[0] * k + dx, c.h - (p[1] * k + dy)   # local -> SVG (y în jos)
        for it in items:
            if isinstance(it, Line):
                (x1, y1), (x2, y2) = P(it.a), P(it.b)
                out.append(f'<line x1="{x1:.3f}" y1="{y1:.3f}" x2="{x2:.3f}" y2="{y2:.3f}" {_style(it.layer)} stroke-linecap="round"/>')
            elif isinstance(it, Polyline):
                pts = " ".join("%.3f,%.3f" % P(p) for p in it.pts)
                tag = "polygon" if it.closed else "polyline"
                out.append(f'<{tag} points="{pts}" {_style(it.layer)} stroke-linejoin="round"/>')
            elif isinstance(it, Rect):
                x, y = P((it.p[0], it.p[1] + it.h))
                fill = f'fill="{it.fill}"' if it.fill else 'fill="none"'
                st = _style(it.layer).replace('fill="none"', fill)
                out.append(f'<rect x="{x:.3f}" y="{y:.3f}" width="{it.w*k:.3f}" height="{it.h*k:.3f}" {st}/>')
            elif isinstance(it, Circle):
                x, y = P(it.c)
                if it.layer == "HASURA":
                    out.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{it.r*k:.3f}" fill="#000"/>')
                else:
                    out.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{it.r*k:.3f}" {_style(it.layer)}/>')
            elif isinstance(it, Ellipse):
                x, y = P(it.c)
                out.append(f'<ellipse cx="{x:.3f}" cy="{y:.3f}" rx="{it.rx*k:.3f}" ry="{it.ry*k:.3f}" {_style(it.layer)}/>')
            elif isinstance(it, Solid):
                col = LAYERS[it.layer][3]
                pts = " ".join("%.3f,%.3f" % P(p) for p in it.pts)
                out.append(f'<polygon points="{pts}" fill="{col}" stroke="none"/>')
            elif isinstance(it, Text):
                x, y = P(it.p)
                col = LAYERS[it.layer][3]
                anchor = {"left": "start", "middle": "middle", "right": "end"}[it.align]
                fs = it.h * k / 0.72   # înălțimea AutoCAD = înălțimea majusculei ≈ 0,72 em
                st = f'font-size="{fs:.2f}" fill="{col}" text-anchor="{anchor}"'
                if it.bold: st += ' font-weight="bold"'
                if it.italic: st += ' font-style="italic"'
                if it.rot: st += f' transform="rotate({-it.rot:g} {x:.3f} {y:.3f})"'
                out.append(f'<text x="{x:.3f}" y="{y:.3f}" {st}>{html.escape(str(it.s or ""))}</text>')
            elif isinstance(it, BlockRef):
                kk = k * it.scale; ox, oy = it.p[0] * k + dx, it.p[1] * k + dy
                if it.uid:
                    out.append(f'<g class="sym" data-uid="{html.escape(it.uid)}">')
                    emit(it.prims, ox, oy, kk); out.append('</g>')
                else:
                    emit(it.prims, ox, oy, kk)
    emit(c.items)
    out.append('</svg>')
    return "\n".join(out)
