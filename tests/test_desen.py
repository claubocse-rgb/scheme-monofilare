"""Teste pentru partea de DESEN (audit inginer P0-8, P1-9, P1-10, P1-11, P2-1…P2-4; SPEC B.19, C.3 pct. 10, C.5 pct. 7,
D: V57 / V82 / V83, G.5).  Rulare:  cd /home/claude/sm && python3 -m pytest tests/test_desen.py -q"""
import copy
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import ezdxf  # noqa: E402
from engine import layout, presets, render_dxf, render_svg, symbols as S  # noqa: E402
from engine.canvas import BlockRef, Line, Solid, Text, bbox_overlap, iter_texts  # noqa: E402
from engine.topologie import coliziuni, verifica_topologie  # noqa: E402


# ---------------------------------------------------------------- modele
def tg12():
    """TG cu 12 plecări (cazul din audit: etichetele de cablu se suprapuneau)"""
    m = presets.get("tg")
    nume = ["Hală 1", "Hală 2", "Birouri", "Pompe", "Compresor", "Iluminat", "Prize", "Ventilație", "HVAC", "Cantină", "Depozit", "Atelier"]
    cal = [100, 100, 40, 63, 80, 16, 32, 40, 125, 50, 63, 50]
    sec = ["3×50+25", "3×50+25", "3×16+16", "3×25+16", "3×35+25", "3×10+10", "3×10+10", "3×10+10", "3×70+35", "3×16+16", "3×25+16", "3×16+16"]
    m["plecari"] = [presets._plecare(f"Q{i + 2}", "sep_fuzibil", In, {"titlu": n, "sub": f"{In // 2} kW"}, f"ACYABY {s} mm² Al · L = 60 m")
                    for i, (n, In, s) in enumerate(zip(nume, cal, sec))]
    m["intrari"][0]["aparate"][0]["spec"] = ["4P · 800 A", "Ir = 0,8 In ≈ 640 A"]
    return m


def bmpt_vechi():
    """model BMPTi salvat înainte de modificare: F în lanțul TC → K → F → P, fără câmpurile noi"""
    m = presets.get("bmpt")
    tc = next(a for a in m["intrari"][0]["aparate"] if a["tip"] == "tc")
    lat = {l["tip"]: l for l in tc["laterale"]}
    f = {k: v for k, v in lat["fuzibil"].items() if k not in ("intrare_contor", "sursa_legatura")}
    tc["laterale"] = [lat["cleme"], f, lat["contor"]]
    m["cartus"]["beneficiar"] = "[BENEFICIAR]"
    return m


MODELE = {k: (lambda k=k: presets.get(k)) for k in presets.PRESETS}
MODELE["tg12"] = tg12
MODELE["bmpt_vechi"] = bmpt_vechi


def _blocks(c, tip=None):
    return [it for it in c.items if isinstance(it, BlockRef) and (tip is None or it.attribs.get("TIP") == tip)]


def _blk(c, ref):
    return next(it for it in c.items if isinstance(it, BlockRef) and it.attribs.get("REF") == ref)


# ---------------------------------------------------------------- 1. circuitul de măsură semidirectă (P0-8, V57)
@pytest.mark.parametrize("cheie", ["bmpt", "bmpt_vechi"])
def test_masura_curent_si_tensiune_separate(cheie):
    m = MODELE[cheie]()
    c = layout.build(m)
    leg = c.meta["legaturi"]
    curent = [l for l in leg if l["tip"] == "masura" and l.get("aparat_tip") == "tc"]
    tensiune = [l for l in leg if l["tip"] == "tensiune"]
    # circuitul de curent: TC → K → P, fără siguranțe
    assert [l["lateral"] for l in curent] == ["cleme", "contor"]
    # circuitul de tensiune: derivație separată, prin F, spre contorul P
    assert len(tensiune) == 1 and tensiune[0]["prin"] == "F" and tensiune[0]["spre"] == "P"
    tc = _blk(c, "TC")
    f = next(b for b in _blocks(c, "fuzibil_lat"))
    p = next(b for b in _blocks(c, "contor"))
    # derivația se ia de pe conductorul de forță, în amonte de TC (deasupra lui), nu din secundar
    tx, ty = tensiune[0]["de_xy"]
    assert abs(tx - tc.p[0]) < 1e-6 and ty > tc.p[1] + S.HALF - 0.01
    # F nu mai stă pe traseul de curent (y-ul TC) între K și P
    assert abs(f.p[1] - tc.p[1]) > 5 and f.p[1] > tc.p[1]
    # a doua intrare a contorului: săgeata circuitului de tensiune intră pe latura de sus a lui P
    jos = [s for s in c.items if isinstance(s, Solid) and s.layer == "MASURA"
           and abs(s.pts[0][1] - (p.p[1] + 8)) < 0.05 and p.p[0] - 14 < s.pts[0][0] < p.p[0] + 14]
    assert jos, "lipsește intrarea de tensiune în contor"
    assert not [r for r in verifica_topologie(m, c) if r["cod"] == "V57"]


def test_v57_fuzibil_fortat_in_circuitul_de_curent():
    m = presets.get("bmpt")
    tc = next(a for a in m["intrari"][0]["aparate"] if a["tip"] == "tc")
    f = next(l for l in tc["laterale"] if l["tip"] == "fuzibil")
    f["intrare_contor"] = "curent"
    tc["laterale"] = [tc["laterale"][0], f] + [l for l in tc["laterale"][1:] if l is not f]
    c = layout.build(m)
    rez = [r for r in verifica_topologie(m, c) if r["cod"] == "V57"]
    assert rez and rez[0]["nivel"] == "BLOCANT"


def test_preset_bmpti_are_campurile_noi():
    tc = next(a for a in presets.get("bmpt")["intrari"][0]["aparate"] if a["tip"] == "tc")
    f = next(l for l in tc["laterale"] if l["tip"] == "fuzibil")
    assert f["intrare_contor"] == "tensiune" and f["sursa_legatura"] == "amonte"


# ---------------------------------------------------------------- 2. săgețile de comandă (P1-11, V83)
@pytest.mark.parametrize("cheie", ["bmpt", "bmptd", "cef", "pt"])
def test_sageti_comanda_spre_aparatul_comandat(cheie):
    m = presets.get(cheie)
    c = layout.build(m)
    cmd = [l for l in c.meta["legaturi"] if l["tip"] == "comanda"]
    assert cmd, "preset-ul are o legătură de comandă"
    for l in cmd:
        tip = l["sageata"]
        sol = [s for s in c.items if isinstance(s, Solid) and s.layer == "COMANDA" and abs(s.pts[0][0] - tip[0]) < 0.05 and abs(s.pts[0][1] - tip[1]) < 0.05]
        assert len(sol) == 1
        base_x = (sol[0].pts[1][0] + sol[0].pts[2][0]) / 2
        # protecția (DPST / PI / F>) e în dreapta; săgeata arată spre stânga, spre bobina BD a aparatului
        assert base_x > tip[0]
        assert l["spre_bbox"][0] - 0.1 <= tip[0] <= l["spre_bbox"][2] + 0.1
    assert not [r for r in verifica_topologie(m, c) if r["cod"] == "V83"]
    # aparatul comandat are bobina BD desenată (bloc „_BD”)
    assert any(b.name.endswith("_BD") for b in _blocks(c))


def test_v83_detecteaza_sageata_inversata():
    m = presets.get("bmpt")
    c = layout.build(m)
    l = next(l for l in c.meta["legaturi"] if l["tip"] == "comanda")
    for it in c.items:          # întoarce săgeata: vârful la cutia DPST
        if isinstance(it, Solid) and it.layer == "COMANDA" and it.pts[0] == l["sageata"]:
            x, y = l["de_xy"]; s = 2.2
            it.pts = [(x, y), (x - s, y - .45 * s), (x - s, y + .45 * s)]
    l["sageata"] = l["de_xy"]
    rez = [r for r in verifica_topologie(m, c) if r["cod"] == "V83"]
    assert rez and rez[0]["nivel"] == "BLOCANT"


# ---------------------------------------------------------------- 3. carcase (P1-10, V82)
def test_tablou_secundar_in_afara_tabloului_parinte():
    c = layout.build(presets.get("tg"))
    car = {k["nume"]: k for k in c.meta["carcase"]}
    assert "TG" in car and "TD-1" in car
    tg, td = car["TG"]["bbox"], car["TD-1"]["bbox"]
    assert not bbox_overlap(tg, td)
    assert td[3] < tg[1], "TD-1 se desenează sub TG"
    # aparatele lui TD-1 sunt în carcasa TD-1, nu în TG
    for ref in ("Q2.1", "Q2.2"):
        b = _blk(c, ref)
        assert td[0] < b.p[0] < td[2] and td[1] < b.p[1] < td[3]
        assert not (tg[1] < b.p[1] < tg[3])
    for ref in ("Q2", "Q3", "Q4", "Q1"):
        b = _blk(c, ref)
        assert tg[0] < b.p[0] < tg[2] and tg[1] < b.p[1] < tg[3]
    assert not [r for r in verifica_topologie(presets.get("tg"), c) if r["cod"] == "V82"]


def test_cef_sursele_in_afara_tgd():
    m = presets.get("cef")
    c = layout.build(m)
    tgd = next(k for k in c.meta["carcase"] if k.get("principala"))["bbox"]
    for b in _blocks(c):
        x, y = b.p
        inside = tgd[0] < x < tgd[2] and tgd[1] < y < tgd[3]
        if b.attribs["TIP"] in ("string_pv", "invertor", "convertor_bess", "baterie", "gpv", "separator_cc", "spd_cc"):
            assert not inside, f"{b.attribs['REF']} desenat în TGD-CF"
            assert y > tgd[3], "sursele se desenează deasupra TGD-CF"
        if b.attribs.get("REF") in ("Q1", "Q2", "Q3", "QB", "QG"):
            assert inside
    assert not [r for r in verifica_topologie(m, c) if r["cod"] == "V82"]


def test_v82_detecteaza_sursa_in_carcasa():
    m = presets.get("cef")
    c = layout.build(m)
    tgd = next(k for k in c.meta["carcase"] if k.get("principala"))["bbox"]
    o = next(o for o in c.meta["obiecte"] if o["nume"] == "INV-1")
    o["bbox"] = (tgd[0] + 5, tgd[1] + 5, tgd[0] + 20, tgd[1] + 20)
    rez = [r for r in verifica_topologie(m, c) if r["cod"] == "V82"]
    assert rez and rez[0]["nivel"] == "BLOCANT" and "INV-1" in rez[0]["mesaj"]


def test_v82_detecteaza_tablou_secundar_in_parinte():
    m = presets.get("tg")
    c = layout.build(m)
    tg = next(k for k in c.meta["carcase"] if k["nume"] == "TG")["bbox"]
    o = next(o for o in c.meta["obiecte"] if o["nume"] == "TD-1" and o["tip"] == "tablou")
    o["bbox"] = (tg[0] + 10, tg[1] + 2, tg[0] + 40, tg[1] + 3)
    assert [r for r in verifica_topologie(m, c) if r["cod"] == "V82"]


# ---------------------------------------------------------------- 4. blocuri DXF pe variante (P1-9)
def _dxf(c, tmp_path, name="t.dxf"):
    p = tmp_path / name
    render_dxf.render(c, str(p))
    return ezdxf.readfile(str(p))


def test_dxf_mccb_cu_si_fara_bd_in_blocuri_diferite(tmp_path):
    m = presets.get("tg")
    m["intrari"][0]["aparate"][0]["bd"] = True              # Q1 cu BD, Q2.1 / Q2.2 MCB fără
    m["plecari"][1]["aparate"][0]["tip"] = "mccb"           # Q3: MCCB fără BD
    c = layout.build(m)
    doc = _dxf(c, tmp_path)
    ins = {e.dxf.name for e in doc.modelspace().query("INSERT")}
    mccb = sorted(n for n in ins if n.startswith("SYM_MCCB"))
    assert len(mccb) == 2 and "SYM_MCCB_BD" in mccb and "SYM_MCCB" in mccb
    # blocul fără BD nu conține caseta BD (mai puține entități decât varianta cu BD)
    assert len(doc.blocks.get("SYM_MCCB_BD")) > len(doc.blocks.get("SYM_MCCB"))
    aud = doc.audit()
    assert not aud.has_errors


def test_dxf_geometrie_diferita_nu_partajeaza_blocul(tmp_path):
    m = presets.get("bmpt")
    q = next(a for a in m["intrari"][0]["aparate"] if a["tip"] == "mccb")
    q["laterale"][0]["w"] = 40; q["laterale"][0]["h"] = 14            # „cutie” de altă mărime …
    m["intrari"][0]["aparate"].append({"tip": "mcb", "ref": "QX", "laterale": [{"tip": "cutie", "eticheta": "X", "legatura": "masura"}]})
    c = layout.build(m)
    doc = _dxf(c, tmp_path)
    cutii = {e.dxf.name for e in doc.modelspace().query("INSERT") if e.dxf.name.startswith("SYM_CUTIE")}
    assert len(cutii) == 2
    # fiecare inserare are exact geometria ei: dreptunghiul blocului = dimensiunile cerute
    dims = set()
    for n in cutii:
        pl = [e for e in doc.blocks.get(n) if e.dxftype() == "LWPOLYLINE"][0]
        xs = [p[0] for p in pl.get_points()]; ys = [p[1] for p in pl.get_points()]
        dims.add((round(max(xs) - min(xs), 1), round(max(ys) - min(ys), 1)))
    assert dims == {(40.0, 14.0), (28.0, 12.0)}
    assert not doc.audit().has_errors


@pytest.mark.parametrize("cheie", list(presets.PRESETS) + ["tg12"])
def test_dxf_preseturi_audit(cheie, tmp_path):
    c = layout.build(MODELE[cheie]())
    doc = _dxf(c, tmp_path, cheie + ".dxf")
    assert not doc.audit().has_errors
    # numele unui bloc identifică o singură geometrie: aceleași nume -> același bloc (verificat prin render) și
    # texte rotite ajung în DXF cu rotația lor
    rot = [e for e in doc.modelspace().query("TEXT") if abs(e.dxf.rotation - 90) < 1e-6]
    if cheie in ("tg", "tg12", "pt", "bmpt"):
        assert rot, "etichetele de cablu ale plecărilor se scriu rotit"


# ---------------------------------------------------------------- 5. suprapuneri de text (P2-1)
@pytest.mark.parametrize("cheie", list(MODELE))
def test_fara_coliziuni(cheie):
    c = layout.build(MODELE[cheie]())
    rez = coliziuni(c, tol=0.25)
    assert not rez, "\n".join(rez[:20])


def test_etichete_cablu_plecari_rotite():
    c = layout.build(tg12())
    rot = [t for t in c.items if isinstance(t, Text) and t.rot == 90]
    assert len([t for t in rot if "ACYABY" in t.s]) == 12
    assert len([t for t in rot if t.s == "3 + N + PE"]) == 12


def test_svg_text_rotit_si_data_uid():
    m = presets.get("bmpt")
    m["intrari"][0]["aparate"][1]["_uid"] = "u-sf"
    c = layout.build(m)
    svg = render_svg.render(c)
    assert 'transform="rotate(-90' in svg
    assert 'class="sym" data-uid="u-sf"' in svg


def test_c2_si_pe_bmpt():
    c = layout.build(presets.get("bmpt"))
    car = next(k for k in c.meta["carcase"] if k.get("principala"))["bbox"]
    c2 = next(t for t in c.items if isinstance(t, Text) and t.s == "C2")
    from engine.canvas import text_bbox
    b = text_bbox(c2)
    assert b[3] < car[1], "eticheta C2 stă sub carcasă, nu pe contur"
    te = next(o for o in c.meta["obiecte"] if o["nume"] == "TE cons. trif.")["bbox"]
    pe = [it for it in c.items if isinstance(it, Line) and it.layer == "PE" and it.a[0] < te[2]]   # fără mostra din legendă
    assert pe and all(max(l.a[0], l.b[0]) < te[0] for l in pe), "linia PE ocolește caseta consumatorului"


# ---------------------------------------------------------------- 6. A2 (P2-2)
@pytest.mark.parametrize("cheie", ["cef", "tg12"])
def test_a2_schema_ocupa_spatiul(cheie):
    c = layout.build(MODELE[cheie]())
    assert c.w == 594.0
    bb, z = c.meta["schema_bbox"], c.meta["zona_schema"]
    fw = (bb[2] - bb[0]) / (z[2] - z[0]); fh = (bb[3] - bb[1]) / (z[3] - z[1])
    assert max(fw, fh) > 0.9, (fw, fh)
    if cheie == "cef":
        assert min(fw, fh) > 0.75, (fw, fh)
        assert c.meta["scara"] > 1.0


# ---------------------------------------------------------------- 7. cartuș (P2-3, G.5)
def test_cartus_campuri_si_fara_placeholder():
    m = presets.get("bmpt")
    c = layout.build(m)
    texte = [t.s for t, _ in iter_texts(c.items)]
    for et in ("ATESTAT ANRE:", "NR. ATR / AVIZ:", "Șef proiect", "Verificat", "Semnătura", "NR. PROIECT:"):
        assert et in texte
    assert not [s for s in texte if s.startswith("[")], "câmpurile lipsă rămân goale"
    for k in ("beneficiar", "titlu", "adresa", "nr_pr"):
        assert m["cartus"][k] == ""
    m["cartus"].update(sef_proiect="ing. A. POP", verificat="ing. B. ION", atestat_anre="12345", atestat_tip="Bp", atr="ATR 7001/2026")
    texte = [t.s for t, _ in iter_texts(layout.build(m).items)]
    assert "ing. A. POP" in texte and "ing. B. ION" in texte and "ATR 7001/2026" in texte
    assert "nr. 12345 · tip Bp" in texte


def test_cartus_textele_nu_taie_liniile():
    m = presets.get("cef")
    m["cartus"].update(beneficiar="SC AGRO VEST SRL", titlu="CENTRALĂ ELECTRICĂ FOTOVOLTAICĂ 350 kWp + BESS 125 kW / 261 kWh — RACORDARE LA RED",
                       adresa="Ciumeghiu, CF 51234, jud. Bihor", data="12.10.2026", nr_pr="CEP-118-26",
                       denumire2="CENTRALĂ ELECTRICĂ FOTOVOLTAICĂ 350 kWp + BESS 125 kW — SCHEMA MONOFILARĂ GENERALĂ")
    c = layout.build(m)
    rez = [r for r in coliziuni(c) if "CARTUS" in r or "cartuș" in r]
    assert not rez, rez


# ---------------------------------------------------------------- 8. simboluri IEC 60617 (P2-4)
def _x_lines(prims):
    return [p for p in prims if isinstance(p, Line) and abs(abs(p.a[0] - p.b[0]) - abs(p.a[1] - p.b[1])) < 1e-6 and abs(p.a[0] - p.b[0]) > 2.5]


def test_simboluri_iec():
    assert len(_x_lines(S.draw("intreruptor_mt"))) == 2          # un singur X
    tc = S.draw("tc")
    assert not [p for p in tc if isinstance(p, Line) and abs(p.a[1] - p.b[1]) < 1e-6]   # fără diametru orizontal
    assert all(p.layer == "SIMBOL" for p in S.draw("pamant") if isinstance(p, Line))    # pământ: linie continuă
    assert any(isinstance(p, Text) and p.s == "IΔ" for p in S.draw("rccb"))
    mec = [p for p in S.draw("mccb") if isinstance(p, Line) and p.layer == "MECANIC"]
    assert mec and not [p for p in S.draw("mccb") if getattr(p, "layer", "") == "COMANDA"]
    from engine.canvas import LAYERS
    assert LAYERS["MECANIC"][2] != "CONTINUOUS" and LAYERS["MECANIC"][3] == "#000"
    sm = S.draw("sep_mt")      # separator de sarcină: bară + cerc pe contactul fix
    from engine.canvas import Circle
    assert any(isinstance(p, Circle) and p.layer == "SIMBOL" for p in sm)
    for k in ("rcbo", "acb", "sigurante_mt", "descarcator_mt", "spd_cc", "separator_cc", "gpv"):
        assert k in S.SYMBOLS and S.draw(k)
    assert len(S.draw("trafo", {"neutru_pamant": True})) > len(S.draw("trafo"))


def test_detectorul_de_coliziuni_functioneaza():
    c = layout.build(presets.get("bmpt"))
    t = next(t for t in c.items if isinstance(t, Text) and t.s == "C2")
    c.text(t.p[0] - 0.5, t.p[1], "XX", 2.5, align="right")
    assert any("C2" in r for r in coliziuni(c))
