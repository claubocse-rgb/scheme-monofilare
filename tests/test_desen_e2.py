"""E2 — DESEN: convențiile proiectantului (teste/reale/raport.md), etichete de tablou, revizii, curbe timp-curent,
„tipic pentru N”, încadrarea SVG.  Rulare:  cd /home/claude/sm && python3 -m pytest tests/test_desen_e2.py -q
Datele sunt inventate (teste/e2/desen/genereaza.py)."""
import copy
import io
import pathlib
import re
import sys
import types
import zipfile

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "teste" / "e2" / "desen"))

import ezdxf  # noqa: E402
import genereaza as G  # noqa: E402
from engine import constructor, desen_e2, layout, planse, presets, render_dxf, render_svg  # noqa: E402
from engine.canvas import BlockRef, Line, Text, Rect, iter_texts  # noqa: E402
from engine.topologie import coliziuni, verifica_topologie  # noqa: E402

_CACHE = {}


def model(nume):
    if nume not in _CACHE:
        _CACHE[nume] = constructor.genereaza(G.CAZURI[nume])[0]
    return copy.deepcopy(_CACHE[nume])


def pachet(nume, **chei):
    m = model(nume)
    m.update(chei)
    return dict(planse.planse_din_model(m))


def texte(c):
    return [t.s for t, _ in iter_texts(c.items)]


# ---------------------------------------------------------------- 1. TE de interfață multifilar (IE 09)
@pytest.mark.parametrize("caz", ["cef_2inv", "cef_cascada", "cef_tipic8"])
def test_ie09_te_multifilar(caz):
    p = pachet(caz)
    ca = p["IE 09/FV"]
    assert ca["desen_special"]["tip"] == "te_multifilar"
    c = layout.build(ca)
    straturi = {it.layer for it in c.items if isinstance(it, Line)}
    assert {"COND_L1", "COND_L2", "COND_L3", "COND_N", "COND_PE", "COND_PE_G"} <= straturi
    t = texte(c)
    for s in ("RELEU DE INTERFAȚĂ (PI)", "A1", "A2", "Y1", "Y2", "Y3", "SURSĂ NEÎNTRERUPTIBILĂ", "BD", "OF", "QG"):
        assert s in t, s
    assert any("smart meter" in s for s in t) and any("contor OD" in s for s in t)
    # fiecare invertor apare cu eticheta lui (și la „tipic” pe IE 07)
    n = sum(1 for b in model(caz)["intrari"] if any(a.get("tip") == "invertor" for a in b["aparate"]))
    for k in range(1, n + 1):
        assert f"Către INV-{k}" in t
    assert coliziuni(c) == []
    assert not [v for v in verifica_topologie(ca, c) if v["nivel"] == "BLOCANT"]
    # comanda releu → bobina BD a QG (V83: săgeata intră în BD)
    assert any(l["tip"] == "comanda" and l["spre"] == "QG" for l in c.meta["legaturi"])


def test_ie09_culorile_fazelor():
    ca = pachet("cef_2inv")["IE 09/FV"]
    svg = render_svg.render(layout.build(ca), "t")
    assert 'stroke="#8b4513"' in svg and 'stroke="#7f7f7f"' in svg and 'stroke="#1a5fb4"' in svg   # maro, gri, N albastru
    ca["desen_special"]["culori_faze"] = "negru"           # cum apar fazele în planșele proiectantului
    svg2 = render_svg.render(layout.build(ca), "t")
    assert 'stroke="#8b4513"' not in svg2
    layout.build(pachet("cef_2inv")["IE 09/FV"])           # revine la SR EN 60445


def test_ie09_cascada_tablouri_intermediare():
    c = layout.build(pachet("cef_cascada")["IE 09/FV"])
    t = texte(c)
    assert t.count("Tablou intermediar") == 3 and {"TE-1", "TE-2", "TE-3"} <= set(t)
    car = {k["nume"] for k in c.meta["carcase"]}
    assert {"TE-1", "TE-2", "TE-3"} <= car
    assert sum(1 for it in c.items if isinstance(it, Rect) and it.layer == "TABLOU") == 4     # TEG + 3 TE


def test_ie09_prosumator_ramane_monofilar_dar_cu_racordul_sus():
    p = pachet("prosumator")
    ca = p["IE 09/FV"]
    assert "desen_special" not in ca
    c = layout.build(ca)
    assert c.meta.get("orientare") == "racord_sus"
    inv = next(b for b in c.items if isinstance(b, BlockRef) and b.attribs.get("TIP") == "invertor")
    rac = next(o for o in c.meta["obiecte"] if o["nume"].startswith("TE EXISTENT"))
    assert inv.p[1] < rac["bbox"][1], "invertorul jos, racordul sus"
    assert coliziuni(c) == []


def test_orientare_clasic_si_planse_fara_rasturnare():
    p = pachet("prosumator", orientare="clasic")
    c = layout.build(p["IE 09/FV"])
    assert c.meta.get("orientare") is None
    assert layout.build(pachet("cef_2inv")["IE 11/FV"]).meta.get("orientare") is None     # intrarea = racordul
    # schema principală (nu pachetul) rămâne cum era
    assert layout.build(model("prosumator")).meta.get("orientare") is None


def test_rasturnare_textele_raman_drepte_si_ordonate():
    c = layout.build(pachet("prosumator")["IE 08/FV"])
    assert c.meta.get("orientare") == "racord_sus"
    # ref deasupra specificației (ordinea rândurilor păstrată), textele nerotite rămân nerotite
    q = [t for t, _ in iter_texts(c.items) if t.s == "QI"]
    sp = [t for t, _ in iter_texts(c.items) if t.s.startswith("2P · C32")]
    assert q and sp and q[0].p[1] > sp[0].p[1]
    assert coliziuni(c) == []


# ---------------------------------------------------------------- 2. stringurile pe IE 07
def test_ie07_stringuri_individuale():
    p = pachet("cef_2inv")
    cc = p["IE 07.1/FV"]
    assert cc["desen_special"]["tip"] == "stringuri"
    c = layout.build(cc)
    t = texte(c)
    for k in range(1, 9):
        assert f"SIR {k}" in t
    assert t.count("× 17") == 8
    assert {"MPPT1", "MPPT2", "MPPT3", "MPPT4", "DATA", "DC", "AC"} <= set(t)
    assert any(s.startswith("2 × H1Z2Z2-K") for s in t)
    assert {tb["titlu"] for tb in cc["tabele"]} == {"MODEL PANOU SOLAR", "MODEL INVERTOR"}
    assert "MODEL PANOU SOLAR" in t and "MODEL INVERTOR" in t
    assert coliziuni(c) == []


def test_ie07_gpv_pe_fiecare_string_si_sectiunea_cablului():
    inp = copy.deepcopy(G.CAZURI["cef_2inv"])
    inp["string"] = {"n_module": 16, "n_stringuri_paralel": 3, "n_MPPT": 2}
    inp["cablu_cc"] = {"S_fortat": 6, "L_m": 40}
    m, _ = constructor.genereaza(inp)
    cc = dict(planse.planse_din_model(m))["IE 07.1/FV"]
    d = cc["desen_special"]["date"]
    assert d["gpv"] and d["n_par"] == 3 and d["n_mppt"] == 2
    c = layout.build(cc)
    t = texte(c)
    assert sum(1 for s in t if s.startswith("SIR ")) == 6
    assert any("gPV" in s and "fiecare string" in s for s in t)
    if d.get("sectiune_cc"):
        assert any(s.startswith(f"2 × H1Z2Z2-K {d['sectiune_cc']}") for s in t)
    assert coliziuni(c) == []


def test_ie07_fara_stringuri_descrise_ramane_bloc_generic():
    inp = copy.deepcopy(G.CAZURI["cef_2inv"])
    inp.pop("string"); inp.pop("modul")
    m, _ = constructor.genereaza(inp)
    cc = dict(planse.planse_din_model(m))["IE 07.1/FV"]
    assert "desen_special" not in cc
    assert coliziuni(layout.build(cc)) == []


# ---------------------------------------------------------------- 7. „tipic pentru INV-1 … INV-N”
def test_tipic_invertoare_identice():
    p = pachet("cef_tipic8")
    coduri = [k for k in p if k.startswith("IE 07")]
    assert coduri == ["IE 07.1/FV"]
    cc = p["IE 07.1/FV"]
    assert "TIPIC" in cc["cartus"]["denumire1"]
    c = layout.build(cc)
    assert any("TIPIC PENTRU INV-1 … INV-8" in s for s in texte(c))
    assert any("8 invertoare identice" in n for n in cc["note"])
    # pe IE 09 fiecare invertor rămâne cu eticheta lui
    t9 = texte(layout.build(p["IE 09/FV"]))
    assert all(f"Către INV-{k}" in t9 for k in range(1, 9))


def test_tipic_prag_si_dezactivare():
    m = model("cef_cascada")                      # 2 + 2 + 2 invertoare identice pe grupe: sub prag (6)
    assert not any("TIPIC" in mp["cartus"]["denumire1"] for _, mp in planse.planse_din_model(m))
    m["tipic_invertoare"] = 2                     # pragul coborât: INV-1/INV-2 (identice) desenate o dată
    lst = planse.planse_din_model(m)
    assert any("TIPIC" in mp["cartus"]["denumire1"] for c, mp in lst if c.startswith("IE 07"))
    m2 = model("cef_tipic8"); m2["tipic_invertoare"] = False
    assert not any("TIPIC" in mp["cartus"]["denumire1"] for _, mp in planse.planse_din_model(m2))


# ---------------------------------------------------------------- 4. etichete de tablou + schema de ușă
def test_etichete_tablou_a4_benzi_din():
    m = presets.get("tg")
    tab = planse.tablouri_model(m)
    assert [t["nume"] for t in tab][:2] == ["TG", "TD-1"]
    et = {e["cod"]: e for t in tab for e in t["etichete"]}
    assert {"Q1", "Q2", "Q2.1", "F1"} <= set(et)
    assert et["Q2.1"]["denumire"]
    pag = planse.etichete_tablou(m)
    assert pag and all((w, h) == (297.0, 210.0) for _, w, h in pag)
    cv = desen_e2.pagini_etichete([t for t in tab if t["etichete"]])
    celule = [it for it in cv[0].items if isinstance(it, Rect) and it.h == desen_e2.H_ETICHETA]
    assert celule and all(abs(r.w / desen_e2.MODUL_DIN - round(r.w / desen_e2.MODUL_DIN)) < 1e-6 for r in celule)
    assert all(r.w <= 12 * desen_e2.MODUL_DIN for r in celule)
    assert coliziuni(cv[0]) == []


def test_eticheta_circuit_calibru_si_idn():
    a = {"tip": "rcbo", "ref": "Q4", "param": {"In_A": 16, "curba": "C"}, "spec": ["1P+N · C16", "30 mA tip A"]}
    e = desen_e2.eticheta_circuit(a, "Prize baie")
    assert e == {"cod": "Q4", "denumire": "Prize baie", "calibru": "C16", "idn": "IΔn 30 mA", "module": 2}
    f = desen_e2.eticheta_circuit({"tip": "sep_fuzibil", "ref": "QF1", "param": {"In_A": 100, "poli": 3}}, "TE-1")
    assert f["calibru"] == "100 A gG" and f["module"] == 3


def test_schema_usa_tablou_a4():
    m = presets.get("tg")
    us = planse.scheme_usa(m)
    assert [n for n, _ in us] == ["TG", "TD-1"]
    for nume, mu in us:
        c = layout.build(mu)
        assert (c.w, c.h) == (297.0, 210.0)
        t = texte(c)
        assert f"SCHEMĂ TABLOU {nume}" in t and "LISTĂ DE ECHIPAMENTE ȘI MATERIALE" not in t
        assert "VERIFICATOR:" not in t                  # antet mic, nu cartușul mare
        assert coliziuni(c) == []


def test_zip_contine_etichete_si_usa():
    lst = planse.planse_din_model(model("cef_2inv"))
    z = zipfile.ZipFile(io.BytesIO(planse.pachet_planse_zip(lst, "t")))
    nume = z.namelist()
    assert any(n.startswith("ETICHETE_tablou_") for n in nume)
    assert any(n.startswith("USA_") for n in nume)
    assert "ETICHETE" in z.read("CUPRINS.txt").decode()


# ---------------------------------------------------------------- 5. tabelul de revizii în cartuș
REV = G.REV


def test_revizii_in_cartus():
    m = presets.get("tg")
    m["revizii"] = REV
    L = layout._layout(m)
    t = texte(L.c)
    assert {"Rev.", "Data", "Descriere", "Întocmit", "Verificat"} <= set(t)
    assert "Actualizare ATR — QG motorizat" in t and "Emisă pentru autorizare" in t
    assert layout.rev_curenta(m) == "1"
    # numărul reviziei curente în cartuș (câmpul „NR. REV.”)
    rv = [tt for tt, _ in iter_texts(L.c.items) if tt.s == "1" and tt.h >= 3.0]
    assert rv
    bb = L.meta["revizii_bbox"]
    assert abs(bb[1] - (11 + 67.7)) < 1e-6 and bb[3] - bb[1] == pytest.approx(3.6 * 3)
    assert coliziuni(L.c) == []


def test_revizii_goale_si_in_pachet():
    m = presets.get("tg")
    m["revizii"] = [{"rev": "", "descriere": ""}]
    assert layout.revizii(m) == [] and layout.rev_curenta(m) == str(m["cartus"].get("rev", ""))
    mm = model("cef_2inv"); mm["revizii"] = REV
    for cod, mp in planse.planse_din_model(mm):
        assert mp.get("revizii") == REV, cod
        c = layout.build(mp)
        assert "Actualizare ATR — QG motorizat" in texte(c)


# ---------------------------------------------------------------- 6. curbe timp-curent
def test_curbe_timp_curent_plansa():
    p = pachet("cef_cascada")
    cb = p["IE 10/FV"]
    d = cb["desen_special"]["date"]
    assert d["sursa"] == "temporar" and len(d["curbe"]) >= 3
    for k in d["curbe"]:
        pts = k["puncte"]
        assert all(b[0] >= a[0] and b[1] <= a[1] for a, b in zip(pts, pts[1:])), k["ref"]
    assert any(et.startswith("Ik3") for et, _ in d["Ik"])
    c = layout.build(cb)
    assert "Curent I [A]" in texte(c)
    assert coliziuni(c) == []


def test_curbe_interfata_motor(monkeypatch):
    """când motorul livrează `engine.calc.curbe.curbe_protectii(model)`, randarea folosește punctele lui"""
    fals = types.ModuleType("engine.calc.curbe")
    fals.curbe_protectii = lambda m: {"curbe": [{"ref": "QA", "eticheta": "QA", "puncte": [(100, 1000), (1000, 0.1)]},
                                                {"ref": "QB", "eticheta": "QB", "puncte": [(200, 1000), (3000, 0.2)]}],
                                      "Ik": [("Ik3 max", 5000.0)]}
    import engine.calc as ec
    monkeypatch.setitem(sys.modules, "engine.calc.curbe", fals)
    monkeypatch.setattr(ec, "curbe", fals, raising=False)
    d = desen_e2.date_curbe(model("cef_cascada"))
    assert d["sursa"] == "motor" and [k["ref"] for k in d["curbe"]] == ["QA", "QB"]


def test_curba_temporara_forme():
    mcb = desen_e2.curba_temporara({"tip": "mcb", "param": {"In_A": 16, "curba": "C"}})
    assert any(abs(i - 160) < 1e-6 and t <= 0.01 for i, t in mcb)          # magnetic la 10·In
    gg = desen_e2.curba_temporara({"tip": "sep_fuzibil", "param": {"In_A": 100}})
    assert dict(gg)[160.0] == 3600.0
    el = desen_e2.curba_temporara({"tip": "mccb", "param": {"In_A": 400, "Ir_A": 360, "Isd_A": 3600, "tsd_s": 0.1,
                                                            "Ii_A": 4800, "decl": "EL"}})
    assert any(abs(i - 3600) < 1e-6 and abs(t - 0.1) < 1e-9 for i, t in el)


# ---------------------------------------------------------------- 8. SVG: încadrarea pe telefon, textul netăiat
def test_svg_vedere_schema_si_textlength():
    c = layout.build(model("cef_tipic8"))
    svg = render_svg.render(c, "t")
    m_ = re.search(r'<view id="schema" viewBox="([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)"/>', svg)
    assert m_ and float(m_.group(3)) < c.w and 'data-schema="' in svg and '<view id="plansa"' in svg
    assert 'textLength="' in svg and 'lengthAdjust="spacingAndGlyphs"' in svg
    assert "Liberation Sans" in svg
    # lățimea Arial (metrica Liberation) — un text din cartuș încape în celula lui
    assert render_svg.latime_arial("VERIFICATOR:", 1.9 / 0.72) < 34
    assert render_svg.latime_arial("ab c", 10) == pytest.approx(render_svg.latime_arial("ab c", 10))


# ---------------------------------------------------------------- DXF + coliziuni pe toate planșele E2
def test_dxf_te_multifilar_straturi_colorate(tmp_path):
    c = layout.build(pachet("cef_cascada")["IE 09/FV"])
    f = tmp_path / "ie09.dxf"
    render_dxf.render(c, str(f))
    doc = ezdxf.readfile(str(f))
    l1 = doc.layers.get("COND_L1")
    assert l1.rgb == (0x8B, 0x45, 0x13)
    assert doc.layers.get("TABLOU") and len(doc.modelspace().query("LINE[layer=='COND_PE']")) > 5


# ---------------------------------------------------------------- filigranul variantei gratuite
def test_filigran_svg_dxf_pachet(tmp_path):
    m = model("cef_2inv")
    m["filigran"] = "kromotec · versiune gratuită"
    lst = planse.planse_din_model(m)
    for cod, mp in lst:
        c = layout.build(mp)
        svg = render_svg.render(c, cod)
        assert 'id="filigran"' in svg and "kromotec · versiune gratuită" in svg, cod
        assert coliziuni(c) == [], cod                      # filigranul nu e element de desen
    f = tmp_path / "f.dxf"
    render_dxf.render(layout.build(lst[0][1]), str(f))
    doc = ezdxf.readfile(str(f))
    tx = doc.modelspace().query("TEXT[layer=='FILIGRAN']")
    assert len(tx) == 1 and tx[0].dxf.text == "kromotec · versiune gratuită"
    assert all("kromotec" in s for s, _, _ in planse.etichete_tablou(m))
    for _, mu in planse.scheme_usa(m):
        assert "kromotec" in render_svg.render(layout.build(mu), "u")
    # fără cheie: nimic
    assert 'id="filigran"' not in render_svg.render(layout.build(model("cef_2inv")), "t")


# IE 08 / cascadă: „15” peste „bara TEG” exista și înainte (orientare clasică, A3 fix) — vezi raportul E2
EXCEPTII = {("cef_cascada", "IE 08/FV")}


@pytest.mark.parametrize("caz", list(G.CAZURI))
def test_toate_planse_fara_coliziuni(caz):
    for cod, mp in planse.planse_din_model(model(caz)):
        c = layout.build(mp)
        if (caz, cod) in EXCEPTII:
            continue
        assert coliziuni(c) == [], cod
        assert not [v for v in verifica_topologie(mp, c) if v["nivel"] == "BLOCANT"], cod
