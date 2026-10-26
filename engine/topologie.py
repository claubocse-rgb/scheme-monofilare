"""Verificări de topologie ale DESENULUI (SPEC D: V57, V82, V83).

`verifica_topologie(model, canvas)` lucrează pe ce s-a desenat efectiv: casetele carcaselor, ale surselor și ale
tablourilor secundare, legăturile de măsură / tensiune / comandă și vârfurile săgeților, pe care motorul de layout
le pune în `canvas.meta`. Fiecare rezultat are forma `{cod, nivel, obiect, mesaj, remediere}` (SPEC D).
"""
from .canvas import Solid, bbox_overlap


def _r(cod, nivel, obiect, mesaj, remediere=""):
    return {"cod": cod, "nivel": nivel, "obiect": obiect, "mesaj": mesaj, "remediere": remediere}


def _aparate(model):
    def walk(bs):
        for b in bs or []:
            for a in b.get("aparate", []) or []: yield a
            yield from walk(b.get("copii"))
    yield from walk(model.get("intrari"))
    yield from walk(model.get("plecari"))


def _v57(model, meta):
    out = []
    # în model: siguranța circuitului de tensiune forțată în lanțul de curent al unui TC
    for a in _aparate(model):
        if a.get("tip") != "tc": continue
        for l in a.get("laterale", []) or []:
            if l.get("tip") == "fuzibil" and l.get("intrare_contor") == "curent":
                out.append(_r("V57", "BLOCANT", a.get("ref") or "TC",
                              f"{l.get('ref') or 'F'} (tensiune contor) legat în circuitul secundar al {a.get('ref') or 'TC'}",
                              "derivație din bare, în amonte de TC: \"intrare_contor\": \"tensiune\""))
    # pe desen: o siguranță pe un traseu de măsură care pleacă din secundarul unui TC
    for l in meta.get("legaturi", []):
        if l.get("tip") == "masura" and l.get("aparat_tip") == "tc" and l.get("lateral") == "fuzibil":
            msg = f"{l.get('spre') or 'F'} (tensiune contor) legat în circuitul secundar al {l.get('de') or 'TC'}"
            if not any(r["mesaj"] == msg for r in out):
                out.append(_r("V57", "BLOCANT", l.get("de") or "TC", msg, "derivație din bare, în amonte de TC"))
    return out


def _v82(meta):
    out = []
    for o in meta.get("obiecte", []):
        if o.get("tip") not in ("sursa", "tablou"): continue
        for car in meta.get("carcase", []):
            if car.get("nume") == o.get("nume"): continue
            if o["bbox"] and bbox_overlap(o["bbox"], car["bbox"], 0.0):
                cine = "sursa" if o["tip"] == "sursa" else "tabloul"
                out.append(_r("V82", "BLOCANT", o.get("nume") or o["tip"],
                              f"{cine} {o.get('nume')} desenat(ă) în interiorul {car.get('nume')}",
                              "sursele și tablourile secundare se desenează în afara carcasei tabloului părinte"))
    return out


def _sageata_spre(c, tip_pt):
    """direcția (dx, dy) a săgeții care are vârful în `tip_pt`, sau None"""
    for it in c.items:
        if isinstance(it, Solid) and it.layer == "COMANDA" and len(it.pts) == 3:
            (tx, ty) = it.pts[0]
            if abs(tx - tip_pt[0]) < 0.05 and abs(ty - tip_pt[1]) < 0.05:
                bx = (it.pts[1][0] + it.pts[2][0]) / 2; by = (it.pts[1][1] + it.pts[2][1]) / 2
                return (tx - bx, ty - by)
    return None


def _v83(c, meta):
    out = []
    for l in meta.get("legaturi", []):
        if l.get("tip") != "comanda": continue
        de, spre = l.get("de_xy"), l.get("spre_xy")
        d = _sageata_spre(c, l.get("sageata") or spre)
        ok = False
        if d and de and spre:
            # săgeata trebuie să aibă vârful la aparatul comandat și să fie orientată de la protecție spre aparat
            v = (spre[0] - de[0], spre[1] - de[1])
            at_tgt = abs(l["sageata"][0] - spre[0]) < 0.05 and abs(l["sageata"][1] - spre[1]) < 0.05
            ok = at_tgt and (d[0] * v[0] + d[1] * v[1]) > 0
        if not ok:
            out.append(_r("V83", "BLOCANT", f"{l.get('de')}→{l.get('spre')}",
                          f"săgeata {l.get('de')}→{l.get('spre')} inversată (sau lipsă)",
                          "săgeata pleacă de la protecție (DPST / PI / releu) și intră în bobina BD a aparatului comandat"))
    return out


def verifica_topologie(model: dict, canvas) -> list:
    """V57 (circuit de tensiune în serie cu TC), V82 (sursă / tablou desenat în carcasa altui tablou),
    V83 (legătură de comandă inversată). Întoarce lista de rezultate {cod, nivel, obiect, mesaj, remediere}."""
    meta = getattr(canvas, "meta", None) or {}
    return _v57(model, meta) + _v82(meta) + _v83(canvas, meta)


# ---------------------------------------------------------------- coliziuni de text (P2-1)
from .canvas import (Text, BlockRef, Line, Circle, iter_texts, item_segments, seg_hits_box, block_bbox, prim_bbox)

LINII_TEXT = ("CARTUS", "TABEL", "CARCASA", "CHENAR")                       # liniile pe care un text nu are voie să le taie
LINII_POZ = ("FORTA", "MASURA", "COMANDA", "MECANIC", "PE", "CARCASA")


def coliziuni(c, tol=0.25):
    """suprapunerile de pe planșă (casete estimate din lungime × înălțime × rotație):
    text–text, text peste liniile cartușului / tabelului / carcaselor, cerc de poziție peste simboluri, săgeți,
    linii de legătură sau alte texte, conductor PE prin caseta unui consumator. Întoarce o listă de șiruri."""
    meta = getattr(c, "meta", None) or {}
    out = []
    texts = [(t, b) for t, b in iter_texts(c.items) if t.s.strip()]
    for i in range(len(texts)):
        ti, bi = texts[i]
        for j in range(i + 1, len(texts)):
            tj, bj = texts[j]
            if bbox_overlap(bi, bj, tol):
                out.append(f"text „{ti.s}” peste „{tj.s}”")
    segs = [(a, b, it.layer) for it in c.items if getattr(it, "layer", "") in LINII_TEXT for a, b in item_segments(it)]
    for t, bb in texts:
        for a, b, lay in segs:
            if seg_hits_box(a, b, bb, tol):
                out.append(f"text „{t.s}” taie o linie {lay}"); break
    # cercuri de poziție
    sym = [block_bbox(it) for it in c.items if isinstance(it, BlockRef)]
    sol = [prim_bbox(it) for it in c.items if isinstance(it, Solid)]
    lin = [(a, b) for it in c.items if getattr(it, "layer", "") in LINII_POZ and not isinstance(it, Circle) for a, b in item_segments(it)]
    pozs = meta.get("poz", [])
    for k, ((x, y), r) in enumerate(pozs):
        bb = (x - r, y - r, x + r, y + r)
        if any(s and bbox_overlap(bb, s, tol) for s in sym): out.append(f"poziția de la ({x:.0f}, {y:.0f}) peste un simbol")
        if any(s and bbox_overlap(bb, s, tol) for s in sol): out.append(f"poziția de la ({x:.0f}, {y:.0f}) peste o săgeată")
        if any(seg_hits_box(a, b, bb, tol) for a, b in lin): out.append(f"poziția de la ({x:.0f}, {y:.0f}) peste o linie")
        for t, tb in texts:
            if bb[0] <= t.p[0] <= bb[2] and bb[1] <= t.p[1] <= bb[3]: continue      # numărul propriu
            if bbox_overlap(bb, tb, tol): out.append(f"poziția de la ({x:.0f}, {y:.0f}) peste textul „{t.s}”")
        for (x2, y2), r2 in pozs[k + 1:]:
            if (x - x2) ** 2 + (y - y2) ** 2 < (r + r2 - tol) ** 2: out.append(f"pozițiile de la ({x:.0f}, {y:.0f}) și ({x2:.0f}, {y2:.0f}) se suprapun")
    # PE prin caseta unui consumator / tablou
    pe = [(a, b) for it in c.items if getattr(it, "layer", "") == "PE" for a, b in item_segments(it)]
    for o in meta.get("obiecte", []):
        if o.get("tip") == "tablou" and any(seg_hits_box(a, b, o["bbox"], tol) for a, b in pe):
            out.append(f"conductorul PE trece prin caseta {o.get('nume')}")
    return out
