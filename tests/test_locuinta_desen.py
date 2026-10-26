"""Tabloul locuinței desenat: intrare „locuinta” → constructor → desen (grupe DDR ca „pieptene” în TE) → validare → export.

* grupele DDR sunt plecări `grup` cu DDR-ul ca aparat și circuitele ca `copii`, fără carcasă sau cablu propriu;
* validarea nu adaugă / nu ascunde BLOCANT față de motor;
* SVG și DXF se generează, DXF trece audit();
* lista de materiale conține tabloul modular și pieptenele, fără carcase de „tablou secundar” pentru grupe;
* șablonul „locuinta” din app.py și tablourile tipice din interfață ies fără erori.
"""
import json, pathlib, re, sys
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import constructor, layout, render_svg, render_dxf, validare  # noqa: E402

C = lambda n, r, **k: dict(nume=n, receptor=r, **k)  # noqa: E731

CASA_TRI = {"tip_schema": "locuinta", "retea": "tri", "schema_pamant": "TN-C-S",
            "alimentare": {"tip": "bransament_existent", "In_Q_bransament_A": 63, "P_aprobata_kW": 32, "L_coloana_m": 25},
            "circuite": [C("Iluminat parter", "iluminat"), C("Iluminat etaj", "iluminat"), C("Prize parter", "prize"), C("Prize etaj", "prize"),
                         C("Prize bucătărie", "prize_bucatarie"), C("Plită", "plita", faza="3F"), C("Cuptor", "cuptor"), C("Prize baie", "prize_baie"),
                         C("Mașină de spălat rufe", "masina_spalat_rufe"), C("Pompă de căldură", "pompa_caldura", faza="3F"),
                         C("Încărcător VE", "vehicul_electric", faza="3F", P_kW=11), C("Prize exterior", "prize_exterior")]}
APARTAMENT = {"tip_schema": "locuinta", "retea": "mono", "schema_pamant": "TN-C-S",
              "alimentare": {"In_Q_bransament_A": 32, "P_aprobata_kW": 7, "L_coloana_m": 20},
              "circuite": [C("Iluminat", "iluminat"), C("Prize camere", "prize"), C("Prize bucătărie", "prize_bucatarie"),
                           C("Prize baie", "prize_baie"), C("Mașină de spălat rufe", "masina_spalat_rufe"), C("Aer condiționat", "aer_conditionat")]}
CASA_TT = dict(APARTAMENT, schema_pamant="TT", RA_ohm=30)


def _circuite(m):
    for b in m.get("plecari") or []:
        if b.get("grup"):
            yield from b.get("copii") or []
        else:
            yield b


@pytest.mark.parametrize("inp", [CASA_TRI, APARTAMENT, CASA_TT], ids=["casa_tri", "apartament", "tt"])
def test_desen_si_export(inp, tmp_path):
    m, r = constructor.genereaza(inp)
    assert not any(v["cod"] == "V00" for v in r["verificari"]), r["verificari"]
    v = validare.valideaza(m)
    bl_m = {(x["cod"], x["obiect"]) for x in r["verificari"] if x["nivel"] == "BLOCANT"}
    bl_v = {(x["cod"], x["obiect"]) for x in v["verificari"] if x["nivel"] == "BLOCANT"}
    assert bl_v == bl_m
    assert not bl_m, bl_m
    # toate circuitele de la intrare apar în desen, cu numele lor
    nume = [b["sarcina"]["titlu"] for b in _circuite(m)]
    assert sorted(nume) == sorted(c["nume"] for c in inp["circuite"])
    # grupele: DDR ca aparat, fără cablu propriu
    for b in m["plecari"]:
        if b.get("grup"):
            assert b["aparate"][0]["tip"] == "rccb" and b["aparate"][0]["ref"].startswith("DDR")
            assert not b.get("cablu")
    # Q general + SPD pe bară
    refs = [a["ref"] for a in m["intrari"][0]["aparate"]]
    assert "QG" in refs and "P" in refs                         # Q general în TE, contorul branșamentului deasupra
    assert any(l["tip"] == "bareta_nul" for a in m["intrari"][0]["aparate"] for l in a.get("laterale") or [])   # bara PE + legătura la pământ
    assert all(a.get("in_carcasa") is False for a in m["intrari"][0]["aparate"][:refs.index("P") + 1])
    assert any(l["tip"] == "spd" for l in m["bara"]["laterale"])
    cv = layout.build(m)
    assert render_svg.render(cv, "t").startswith("<svg")
    f = tmp_path / "s.dxf"
    render_dxf.render(cv, str(f))
    import ezdxf
    assert not ezdxf.readfile(str(f)).audit().has_errors
    den = [x["lista"][0] for x in m["materiale"]]
    assert any(d.startswith("Tablou modular TE") for d in den)
    assert any(d.startswith("Pieptene") for d in den)
    assert not any(d.startswith("Carcasă tablou") for d in den), "grupele DDR nu sunt tablouri secundare"


def test_circuit_trifazat_are_mcb_4p_iar_cel_monofazat_1p_n():
    m, _ = constructor.genereaza(CASA_TRI)
    poli = {b["sarcina"]["titlu"]: b["aparate"][0]["param"]["poli"] for b in _circuite(m)}
    assert poli["Plită"] == "4P" and poli["Încărcător VE"] == "4P"
    assert poli["Iluminat parter"] == "1P+N"


def test_ve_are_ddr_tip_b():
    # r5: implicit DDR tip A + RDC-DD 6 mA în stație (compatibil cu DDR tip A în branșament); tip B când e declarat
    m, r = constructor.genereaza(CASA_TRI)
    g = [b for b in m["plecari"] if b.get("grup") and any(c["sarcina"]["titlu"] == "Încărcător VE" for c in b["copii"])][0]
    assert g["aparate"][0]["param"]["tip_ddr"] == "A"
    circ = [dict(c, DDR={"IdN_mA": 30, "tip": "B"}) if c["receptor"] == "vehicul_electric" else c for c in CASA_TRI["circuite"]]
    m, r = constructor.genereaza(dict(CASA_TRI, circuite=circ))
    g = [b for b in m["plecari"] if b.get("grup") and any(c["sarcina"]["titlu"] == "Încărcător VE" for c in b["copii"])][0]
    assert g["aparate"][0]["param"]["tip_ddr"] == "B"


def test_layout_grup_fara_coliziuni_de_coloane():
    m, _ = constructor.genereaza(CASA_TRI)
    cv = layout.build(m)
    obs = [o for o in cv.meta["obiecte"] if o["tip"] == "tablou"]
    xs = sorted((o["bbox"][0], o["bbox"][2]) for o in obs)
    for (a1, a2), (b1, b2) in zip(xs, xs[1:]):
        assert a2 <= b1 + 0.01, "casetele circuitelor se suprapun"


def test_sablon_locuinta_cere_reteaua():
    """șablonul „locuinta” nu presupune rețeaua: singurul BLOCANT e rețeaua nespecificată; cu rețeaua aleasă iese curat"""
    import app
    inp = app.SABLOANE["locuinta"][2]
    assert "retea" not in inp
    _, r = constructor.genereaza(inp)
    assert [(v["cod"], v["obiect"]) for v in r["verificari"] if v["nivel"] == "BLOCANT"] == [("V07", "retea")]
    _, r = constructor.genereaza(dict(inp, retea="tri", alimentare={"In_Q_bransament_A": 25, "P_aprobata_kW": 13, "L_coloana_m": 25}))
    assert not [v for v in r["verificari"] if v["nivel"] == "BLOCANT"]


def _tipice_din_ui():
    """tablourile tipice din static/index.html (TABLOU_TIPIC) → intrări de calcul"""
    s = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    bloc = s[s.index("const TABLOU_TIPIC = {"):s.index("function locRezultate")]
    out = {}
    for m in re.finditer(r"(\w+): \{ nume: '([^']+)', retea: '(\w+)', alim: \{ ([^}]*) \},\s*circuite: \[(.*?)\] \}", bloc, re.S):
        alim = {k: float(v) for k, v in re.findall(r"(\w+): ([\d.]+)", m.group(4))}
        circ = []
        for c in re.finditer(r"LC\('([^']+)', '(\w+)'(?:, \{([^}]*)\})?\)", m.group(5)):
            d = {"nume": c.group(1), "receptor": c.group(2)}
            for k, v in re.findall(r"(\w+): '?([\w.]+)'?", c.group(3) or ""):
                d[k] = float(v) if re.fullmatch(r"[\d.]+", v) else v
            circ.append(d)
        out[m.group(1)] = {"tip_schema": "locuinta", "retea": m.group(3), "schema_pamant": "TN-C-S", "alimentare": alim, "circuite": circ}
    return out


def test_tablourile_tipice_din_interfata_ies_fara_erori():
    tip = _tipice_din_ui()
    assert set(tip) == {"apartament", "parter", "p1", "pc_ve"}
    for k, inp in tip.items():
        m, r = constructor.genereaza(inp)
        bl = [v for v in r["verificari"] if v["nivel"] == "BLOCANT"]
        assert not bl, (k, bl)
        assert not [v for v in r["verificari"] if v["cod"] == "V46"], (k, "puterea aprobată din tabloul tipic trebuie să acopere bilanțul")
