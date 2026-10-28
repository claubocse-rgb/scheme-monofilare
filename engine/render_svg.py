"""Randare Canvas -> SVG (mm, A3/A2 landscape)."""
from .canvas import *
import html

LW_SVG = {18: 0.18, 25: 0.25, 35: 0.35, 50: 0.5, 70: 0.7}

# E2 (D4): lățimile glifelor Arial (metrica Liberation Sans / Arimo, compatibilă), la 1000 unități / em.
# Fiecare text primește textLength = lățimea lui în Arial: pe un dispozitiv fără Arial (telefon Android → Roboto,
# alt font de rezervă) textul se încadrează exact în celula / spațiul calculat — nu mai iese din chenar, nu e tăiat.
_CH = " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~§°±²³µ·¼½¾ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõö÷øùúûüýþÿĂăŞşŢţȘșȚțΔΣΩαβγθλπρφ–—‘’“”„•…′″⁻€←↑→↓√∞∠≈≠≤≥"
_W_R = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584, 556, 400, 549, 333, 333, 576, 333, 834, 834, 834, 667, 667, 667, 667, 667, 667, 1000, 722, 667, 667, 667, 667, 278, 278, 278, 278, 722, 722, 778, 778, 778, 778, 778, 584, 778, 722, 722, 722, 722, 667, 667, 611, 556, 556, 556, 556, 556, 556, 889, 500, 556, 556, 556, 556, 278, 278, 278, 278, 556, 556, 556, 556, 556, 556, 556, 549, 611, 556, 556, 556, 556, 500, 556, 500, 667, 556, 667, 500, 611, 278, 667, 500, 611, 278, 668, 618, 748, 578, 575, 500, 556, 500, 690, 569, 648, 556, 1000, 222, 222, 333, 333, 333, 350, 1000, 188, 354, 750, 556, 1000, 500, 1000, 500, 549, 713, 750, 549, 549, 549, 549]
_W_B = [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611, 975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556, 333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611, 611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584, 556, 400, 549, 333, 333, 576, 333, 834, 834, 834, 722, 722, 722, 722, 722, 722, 1000, 722, 667, 667, 667, 667, 278, 278, 278, 278, 722, 722, 778, 778, 778, 778, 778, 584, 778, 722, 722, 722, 722, 667, 667, 611, 556, 556, 556, 556, 556, 556, 889, 556, 556, 556, 556, 556, 278, 278, 278, 278, 611, 611, 611, 611, 611, 611, 611, 549, 611, 611, 611, 611, 611, 556, 611, 556, 722, 556, 667, 556, 611, 333, 667, 556, 611, 333, 719, 600, 802, 615, 610, 556, 541, 556, 766, 619, 715, 556, 1000, 278, 278, 500, 500, 500, 350, 1000, 240, 479, 750, 556, 1000, 500, 1000, 500, 549, 713, 750, 549, 549, 549, 549]
_MET_R = dict(zip(_CH, _W_R))
_MET_B = dict(zip(_CH, _W_B))
FONT = "Arial,Helvetica,'Liberation Sans',Arimo,sans-serif"


def latime_arial(s, fs, bold=False):
    """lățimea (unități SVG) a textului s cu font-size fs în Arial; None dacă textul are caractere necunoscute"""
    t = _MET_B if bold else _MET_R
    tot = 0
    s = " ".join(s.replace("\u00a0", " ").replace("\u202f", " ").split()) if ("  " in s or s != s.strip()) else \
        s.replace("\u00a0", " ").replace("\u202f", " ")
    for ch in s:
        w = t.get(ch)
        if w is None:
            return None
        tot += w
    return tot / 1000.0 * fs

def _style(layer):
    aci, lw, lt, col = LAYERS[layer]
    s = f'stroke="{col}" stroke-width="{LW_SVG.get(lw, 0.35)}" fill="none"'
    d = DASH_SVG.get(lt)
    if d: s += f' stroke-dasharray="{d}"'
    return s

def render(c: Canvas, title="Schema") -> str:
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{c.w}mm" height="{c.h}mm" viewBox="0 0 {c.w} {c.h}">',
           f'<title>{html.escape(title)}</title>',
           f'<style>text{{font-family:{FONT}}}</style>']
    # E2 (D4): încadrarea pe telefon — vederea „#schema” pe zona desenului (fără cartuș / listă); planșa întreagă rămâne
    # vederea implicită (viewBox), iar interfața poate deschide direct `…svg#schema`
    sb = (getattr(c, "meta", None) or {}).get("schema_bbox")
    if sb:
        m_ = 4.0
        x1, x2 = max(0.0, sb[0] - m_), min(c.w, sb[2] + m_)
        y1, y2 = max(0.0, c.h - sb[3] - m_), min(c.h, c.h - sb[1] + m_)
        out[0] = out[0][:-1] + f' data-schema="{x1:.1f} {y1:.1f} {x2 - x1:.1f} {y2 - y1:.1f}">'
        out.append(f'<view id="schema" viewBox="{x1:.1f} {y1:.1f} {x2 - x1:.1f} {y2 - y1:.1f}"/>')
    out.append(f'<view id="plansa" viewBox="0 0 {c.w} {c.h}"/>')
    out.append(f'<rect x="0" y="0" width="{c.w}" height="{c.h}" fill="#fff"/>')

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
                s_ = str(it.s or "")
                if len(s_) >= 2:
                    lw = latime_arial(s_, fs, it.bold)
                    if lw:
                        st += f' textLength="{lw:.2f}" lengthAdjust="spacingAndGlyphs"'
                out.append(f'<text x="{x:.3f}" y="{y:.3f}" {st}>{html.escape(str(it.s or ""))}</text>')
            elif isinstance(it, BlockRef):
                kk = k * it.scale; ox, oy = it.p[0] * k + dx, it.p[1] * k + dy
                if it.uid:
                    out.append(f'<g class="sym" data-uid="{html.escape(it.uid)}">')
                    emit(it.prims, ox, oy, kk); out.append('</g>')
                else:
                    emit(it.prims, ox, oy, kk)
    emit(c.items)
    fil = (getattr(c, "meta", None) or {}).get("filigran")
    if fil:
        # E2: filigranul (varianta gratuită): discret, centrat în banda de jos dintre rame (y = 6,4 mm de la margine)
        fs = 2.4 / 0.72
        out.append(f'<g class="filigran" id="filigran" pointer-events="none"><text x="{c.w / 2:.3f}" '
                   f'y="{c.h - 6.4:.3f}" text-anchor="middle" font-size="{fs:.2f}" fill="#000" fill-opacity="0.28">'
                   f'{html.escape(str(fil))}</text></g>')
    out.append('</svg>')
    return "\n".join(out)
