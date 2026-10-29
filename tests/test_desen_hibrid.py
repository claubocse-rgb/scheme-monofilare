"""r13 — feedback inginer (captură prosumator hibrid trifazat 10 kW + baterie, R01):

1. coloana câmpului PV începe direct cu componentele (PV → cablu c.c. → S → INV), fără caseta-sursă generică
   „CÂMP PV / invertor hibrid 10 kW” deasupra (dubla PV și INV). Idem prosumator ne-hibrid și CEF (coloana
   reprezentantă); coloanele „idem” fără simbol PV își păstrează caseta.
2. casetele laterale nu mai au eticheta dublată deasupra („PE” peste „PE echipot. rame”, „SB”, „FB”, „BAT”); simbolul
   indexat intră în titlul casetei („SB1”, „PE1”); nimic nu se încalecă (texte, simboluri — F2 cu pământul lui față de
   FB / BAT).
"""
import copy
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import app  # noqa: E402
from engine import constructor, layout  # noqa: E402
from engine.canvas import BlockRef, Text, block_bbox, bbox_overlap, iter_texts, text_bbox  # noqa: E402
from engine.topologie import coliziuni  # noqa: E402

ING = ROOT / "tests" / "date" / "echipa1"


def _desen(calc):
    m, _ = constructor.genereaza(copy.deepcopy(calc))
    return m, layout.build(m)


def _calc(caz):
    return json.loads((ING / f"{caz}.json").read_text(encoding="utf-8"))["calc"]


def _x_lista(c):
    return c.w - 10 - 158          # începutul listei de echipamente (coloana „Simbol” repetă referințele)


def _texte_libere(c):
    """textele schemei (fără lista de echipamente, legendă, cartuș din dreapta)"""
    return [it for it in c.items if isinstance(it, Text) and it.s.strip() and it.p[0] < _x_lista(c)]


def _texte_peste_simboluri(c, tol=0.25):
    """texte (libere sau din alte simboluri) care intră în geometria unui simbol (fără textele lui proprii)"""
    out = []
    blocs = [(b, block_bbox(b)) for b in c.items if isinstance(b, BlockRef)]
    for b, bb in blocs:
        if bb is None: continue
        for it in c.items:
            if it is b: continue
            if isinstance(it, Text) and it.s.strip():
                if bbox_overlap(text_bbox(it), bb, tol): out.append(f"„{it.s}” peste {b.name} {b.attribs.get('REF', '')}")
            elif isinstance(it, BlockRef):
                for p in it.prims:
                    if isinstance(p, Text) and p.s.strip() and bbox_overlap(text_bbox(p, it.p[0], it.p[1], it.scale), bb, tol):
                        out.append(f"„{p.s}” ({it.attribs.get('REF', '')}) peste {b.name} {b.attribs.get('REF', '')}")
    return out


CAZURI = {
    "R01_hibrid_bat": lambda: _calc("R01_prosumator_bat"),
    "prosumator": lambda: copy.deepcopy(app.SABLOANE["prosumator"][2]),
    "cef_sablon": lambda: copy.deepcopy(app.SABLOANE["cef"][2]),
    "C02_cef_1MW": lambda: _calc("C02_cef_1MW"),
}


@pytest.mark.parametrize("caz", sorted(CAZURI))
def test_fara_caseta_sursa_redundanta(caz):
    m, c = _desen(CAZURI[caz]())
    pv = [b for b in m["intrari"] if (b.get("aparate") or [{}])[0].get("tip") == "string_pv"]
    assert pv, "cazul trebuie să aibă coloana câmpului PV desenată cu simbol"
    titluri_pv = {b["sursa"]["titlu"] for b in pv if b.get("sursa")}
    sursa = [o for o in c.meta["obiecte"] if o["tip"] == "sursa"]
    assert not any(o["nume"] in titluri_pv for o in sursa), "caseta-sursă CÂMP PV dublează simbolul PV"
    assert not any(t.s.startswith("CÂMP PV") for t in _texte_libere(c))
    # coloana începe cu simbolul PV (cel mai de sus element al coloanei), cablul c.c. rămâne marcat
    ys_pv = [b.p[1] for b in c.items if isinstance(b, BlockRef) and b.attribs.get("TIP") == "string_pv"]
    ys_sym = [b.p[1] for b in c.items if isinstance(b, BlockRef) and b.attribs.get("TIP") in ("separator_cc", "invertor")]
    assert ys_pv and max(ys_pv) > max(ys_sym)
    assert any(t.s == "c.c." for t in _texte_libere(c))


@pytest.mark.parametrize("caz", sorted(CAZURI))
def test_fara_suprapuneri_si_etichete_dublate(caz):
    m, c = _desen(CAZURI[caz]())
    assert coliziuni(c) == []
    # eticheta separată a unei casete laterale nu repetă titlul casetei
    titluri_cutie = {p.s for b in c.items if isinstance(b, BlockRef) and b.attribs.get("TIP") == "cutie"
                     for p in b.prims if isinstance(p, Text) and p.s.strip()}
    dublate = [t.s for t in _texte_libere(c) if t.s in titluri_cutie or any(tc.split(" ")[0] == t.s for tc in titluri_cutie)]
    assert dublate == [], f"etichete dublate: {dublate}"
    zona = [s for s in _texte_peste_simboluri(c) if "LEGEND" not in s]
    assert zona == [], zona


def test_r01_casete_si_spd_cc_separate():
    """captura inginerului: F2 (SPD c.c.) cu pământul lui nu atinge FB / BAT; FB și BAT au simbolul în titlu"""
    m, c = _desen(_calc("R01_prosumator_bat"))
    cut = {}
    for b in c.items:
        if isinstance(b, BlockRef) and b.attribs.get("TIP") in ("cutie", "spd_cc"):
            cut[b.attribs.get("REF")] = (b, block_bbox(b, texts=True))
    assert {"PE", "SB", "FB", "BAT", "F2"} <= set(cut)
    for r in ("PE", "SB", "FB", "BAT"):
        t0 = [p.s for p in cut[r][0].prims if isinstance(p, Text)][0]
        assert t0.split(" ")[0] == r
    for r in ("FB", "BAT", "SB"):
        assert not bbox_overlap(cut["F2"][1], cut[r][1], 0.0), f"F2 peste {r}"
    texte = [t.s for t, bb in iter_texts(c.items) if bb[0] < _x_lista(c)]
    for r in ("PE", "SB", "BAT"):
        assert texte.count(r) == 1, (r, texte.count(r))
