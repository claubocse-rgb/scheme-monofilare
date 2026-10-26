"""F.9 — Claude ca interpretor principal, regulile locale ca verificare încrucișată / rezervă.
Fără rețea: răspunsurile lui Claude sunt simulate (mock), apelul HTTP e interceptat."""
import io
import json
import os
import pathlib
import sys

import pytest

RAD = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAD))

from engine import interpretor as m, interp_schema as sch, cheie_api  # noqa: E402
from engine.interp_schema_inventar import INVENTAR  # noqa: E402


@pytest.fixture(autouse=True)
def fara_cheie(monkeypatch, tmp_path):
    """Nicio cheie reală: mediu gol, ~/.config temporar, memoria procesului golită."""
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    cheie_api._MEMORIE["cheie"] = None
    yield
    cheie_api._MEMORIE["cheie"] = None


def _unealta(intr, intrebari=(), neinteles=(), cartus=None):
    d = {"intrare_fizica": intr, "intrebari": list(intrebari), "neinteles": list(neinteles)}
    if cartus:
        d["cartus"] = cartus
    return d


def _api(inp, text=""):
    """Corpul unui răspuns /v1/messages cu apelul uneltei."""
    c = ([{"type": "text", "text": text}] if text else []) + [
        {"type": "tool_use", "id": "toolu_1", "name": "intrare_fizica", "input": inp}]
    return {"id": "msg_1", "type": "message", "role": "assistant", "content": c, "stop_reason": "tool_use"}


# ------------------------------------------------------------------------------------------------ schema generată
def test_inventarul_e_la_zi():
    """Schema e generată din motor + corpus; dacă pică: python3 -m engine.interp_schema --genereaza."""
    assert sch.genereaza_inventar() == INVENTAR


def test_schema_acopera_toate_tipurile():
    p = sch.schema_intrare()["properties"]
    assert set(p["tip_schema"]["enum"]) == set(m.TIPURI)
    for k in ("retea", "schema_pamant", "P_aprobata_kW", "P_evacuata_kW", "invertoare", "n_trafo", "origine",
              "consumatori", "siguranta_tablou", "alimentare", "circuite", "plecari", "bess", "Sn_kVA", "Sn_GE_kVA",
              "Pn_inv_kW", "limitare_injectie_kW", "In_Q_bransament_A", "kWp", "tablouri_secundare"):
        assert k in p, k
    assert p["retea"]["enum"] == ["mono", "tri"]
    assert set(p["circuite"]["items"]["properties"]["receptor"]["enum"]) == set(m.ENUM_RECEPTORI_LOC)
    assert p["invertoare"]["items"]["properties"]["n"]["type"] == "integer"
    assert p["consumatori"]["items"]["properties"]["siguranta"]["type"] == "boolean"
    tipuri_vazute = {t for v in INVENTAR.values() for t in v["tipuri"]}
    assert tipuri_vazute == set(m.TIPURI)


def test_iesirile_locale_trec_validarea_schemei():
    """Tot ce emite interpretorul local (după normalizare) e valid față de schemă — schema nu e mai strictă decât motorul."""
    fraze = json.loads((RAD / "tests/date/fraze_chat.json").read_text(encoding="utf-8"))["fraze"]
    for f in fraze:
        i = m.interpreteaza_local(f["text"])["intrare_fizica"]
        if i.get("tip_schema"):
            assert not sch.valideaza(m.normalizeaza_intrare(i)), (f["text"], sch.valideaza(m.normalizeaza_intrare(i)))


def test_validare_si_curatare():
    err = sch.valideaza({"tip_schema": "cef", "retea": "trifazat", "n_trafo": 1.5, "cheie_x": 1,
                         "invertoare": [{"n": 2, "Pn_kW": -5}]}, domenii=True)
    assert any("retea" in e for e in err) and any("n_trafo" in e for e in err)
    assert any("cheie_x" in e for e in err) and any("Pn_kW" in e for e in err)
    c = sch.curata({"tip_schema": "pt", "Sn_kVA": "630", "U_MT_kV": "20", "masura": "MT", "inventat": 3,
                    "trafo_izolatie": "plastic"})
    assert c == {"tip_schema": "pt", "Sn_kVA": 630, "U_MT_kV": 20, "masura": "MT"}


def test_prompt_si_unealta():
    u = sch.unealta()
    assert u["name"] == "intrare_fizica"
    s = u["input_schema"]
    assert {"intrare_fizica", "intrebari", "neinteles"} <= set(s["required"])
    corp = m.cerere_llm("TG 100 kW")
    assert corp["model"] == "claude-opus-5-5" and corp["fallbacks"] == "default"
    assert corp["output_config"] == {"effort": "medium"} and corp["tools"][0]["name"] == "intrare_fizica"
    assert corp["messages"] == [{"role": "user", "content": "TG 100 kW"}]
    for frag in ("NU dimensiona", "Rețeaua NU se presupune", "27 kW", "N x MODEL", "siguranta", "intrebari",
                 "neinteles", "P_evacuata_kW"):
        assert frag in corp["system"], frag
    assert "- locuinta:" in corp["system"] and "- cef:" in corp["system"]     # cheile pe tip, generate
    for t, o in m.EXEMPLE_LLM:                       # exemplele sunt valide și trec fuziunea ca citire Claude
        assert not sch.valideaza(o["intrare_fizica"]), t
        assert m.interpreteaza(t, raspuns_llm=o)["motor"] == "llm", t
    h = m.antete_llm("sk-ant-test-000000000000000000")
    assert h["x-api-key"].startswith("sk-ant") and h["anthropic-beta"] == m.BETA_LLM


def test_raspuns_din_api():
    inp = _unealta({"tip_schema": "pt", "Sn_kVA": 630})
    assert m.raspuns_din_api(_api(inp, "Iată:")) == inp
    assert m.raspuns_din_api({"content": [{"type": "text", "text": 'x {"intrare_fizica": {"tip_schema": "pt"}}'}]}) == \
        {"intrare_fizica": {"tip_schema": "pt"}}
    assert m.raspuns_din_api({"content": [], "stop_reason": "refusal"}) is None
    with pytest.raises(RuntimeError):
        m.raspuns_din_api({"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}})


# ------------------------------------------------------------------------------------------------ fuziunea
def test_fara_cheie_exact_local():
    t = "TG 120 kW cu 4 plecări de 63 A"
    assert m.interpreteaza(t, foloseste_llm=True) == m.interpreteaza_local(t)


def test_claude_e_baza_si_regulile_verifica():
    t = "Extras ATR: putere aprobata evacuare 80 kW, consum 120 kW. Racord la BMPT existent 3x250A. CEF 99,4 kWp, 1 invertor Huawei SUN2000-100KTL-M2."
    local = m.interpreteaza_local(t)
    r = m.interpreteaza(t, raspuns_llm=_api(_unealta(
        {"tip_schema": "cef", "retea": "tri", "kWp": 99.4, "racord": "bmpt", "In_Q_bransament_A": 250,
         "P_aprobata_kW": 120, "P_evacuata_kW": 80, "limitare_injectie_kW": 80,
         "invertoare": [{"n": 1, "Pn_kW": 100, "producator": "Huawei", "model": "SUN2000-100KTL-M2"}]})))
    assert r["motor"] == "llm" and r["actiune"] != "refuza"
    assert r["intrare_fizica"]["limitare_injectie_kW"] == 80
    assert r["presupus"], "„Am presupus” rămâne"
    assert "Am înțeles" in r["intelegere"]
    assert local["motor"] == "reguli"


def test_diferenta_critica_devine_intrebare_cu_ambele_variante():
    t = "CEF 200 kW cu 4 invertoare SUN2000-50KTL-M3, PT nou 2 x 630 kVA"
    local = m.interpreteaza_local(t)["intrare_fizica"]
    assert local["n_trafo"] == 2
    r = m.interpreteaza(t, raspuns_llm=_unealta({"tip_schema": "cef", "n_trafo": 1, "pt_Sn_kVA": 630,
                                                   "invertoare": [{"n": 4, "Pn_kW": 50}]}))
    q = [x for x in r["intrebari"] if "diferă la numărul de transformatoare" in x]
    assert q and "(Claude) → 1;" in q[0] and "regulile locale → 2." in q[0]
    assert r["actiune"] == "genereaza_cu_intrebare" and r["intrare_fizica"]["n_trafo"] == 1
    assert r["verificare_incrucisata"]["diferente"] == [{"cheie": "n_trafo", "claude": 1, "reguli": 2}]


def test_regula_locala_lipsa_nu_intreaba():
    """Diferență doar când regula locală are o valoare: None la reguli nu produce întrebare."""
    a = {"tip_schema": "prosumator", "retea": "tri", "P_aprobata_kW": 15, "Pn_inv_kW": 10}
    b = {"tip_schema": "prosumator", "Pn_inv_kW": 10}
    assert m.diferente_critice(a, b) == []
    assert [k for k, *_ in m.diferente_critice(b, a)] == ["P_aprobata"]      # „tri” implicit al regulilor nu contează
    assert [k for k, *_ in m.diferente_critice(b, dict(a, retea="mono"))] == ["retea", "P_aprobata"]
    inv1 = {"tip_schema": "cef", "invertoare": [{"n": 1, "Pn_kW": 100}]}
    inv2 = {"tip_schema": "cef", "invertoare": [{"n": 2, "Pn_kW": 50}]}
    assert m.diferente_critice(inv1, inv2)[0][0] == "invertoare"
    s1 = {"tip_schema": "ge_ats", "consumatori": [{"nume": "Pompă incendiu", "P_kW": 45, "siguranta": True}]}
    s2 = {"tip_schema": "ge_ats", "consumatori": [{"nume": "Pompă incendiu", "P_kW": 45}]}
    assert m.diferente_critice(s1, s2)[0][0] == "siguranta"


def test_intrebarile_si_neintelesul_lui_claude_se_pastreaza():
    r = m.interpreteaza("CEF 200 kW cu 4 invertoare, ceva ciudat XYZ", raspuns_llm=_unealta(
        {"tip_schema": "cef", "invertoare": [{"n": 4, "Pn_kW": 50}]},
        intrebari=["200 kW = total (4 × 50 kW) sau 4 × 200 kW?"], neinteles=["ceva ciudat XYZ"]))
    assert "200 kW = total (4 × 50 kW) sau 4 × 200 kW?" in r["intrebari"]
    assert any("ceva ciudat XYZ" in q for q in r["intrebari"]) and r["neconsumat"] == ["ceva ciudat XYZ"]
    assert "Nu am înțeles" in r["intelegere"]


def test_verificarile_f7_raman_peste_claude():
    r = m.interpreteaza("branșament 300 kW", raspuns_llm=_unealta({"tip_schema": "bransament", "retea": "tri", "P_kW": 300}))
    assert r["motor"] == "llm" and r["actiune"] == "refuza" and r["refuz_cod"] == "I10"


def test_reteaua_nu_se_presupune_nici_cu_claude():
    r = m.interpreteaza("prosumator 5 kW", raspuns_llm=_unealta({"tip_schema": "prosumator", "Pn_inv_kW": 5},
                                                                 intrebari=["Monofazat sau trifazat?"]))
    assert "retea" not in r["intrare_fizica"]
    assert any("monofazat" in q.lower() for q in r["intrebari"])


def test_forma_invalida_ramane_local_cu_intrebarile_lui_claude():
    t = "branșament 60 kW, cablu 50 m"
    r = m.interpreteaza(t, raspuns_llm=_unealta({"tip_schema": "pt"}, intrebari=["Ce putere are trafo-ul?"]))
    assert r["motor"] == "reguli" and "Ce putere are trafo-ul?" in r["intrebari"]
    assert any("respinsă la validarea formei" in p for p in r["presupus"])


def test_refuzul_in_afara_domeniului_ramane():
    t = "sistem off-grid 10 kW cu baterii, fara retea"
    local = m.interpreteaza_local(t)
    assert local["refuz_cod"] == "I12"
    r = m.interpreteaza(t, raspuns_llm=_unealta({"tip_schema": "prosumator", "Pn_inv_kW": 10, "retea": "tri"}))
    assert r["actiune"] == "refuza" and r["refuz_cod"] == "I12"


def test_cartus_din_claude():
    r = m.interpreteaza("tablou 50 kW", raspuns_llm=_unealta(
        {"tip_schema": "tablou", "P_kW": 50, "plecari": [{"nume": "TD-1", "In_A": 63}]},
        cartus={"beneficiar": "SC Test SRL", "localitate": "Oradea", "judet": "Bihor"}))
    assert r["cartus"]["beneficiar"] == "SC Test SRL" and r["cartus"]["adresa"]["localitate"] == "Oradea"


def test_eroare_api_ramane_local():
    r = m.interpreteaza("TG 50 kW cu 2 plecări de 32 A",
                        raspuns_llm={"type": "error", "error": {"message": "overloaded"}, "content": []})
    assert r["motor"] == "reguli" and any("LLM indisponibil" in p for p in r["presupus"])


# ------------------------------------------------------------------------------------------------ apelul HTTP (mock)
def test_intrare_llm_http(monkeypatch):
    vazut = {}

    class Rasp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(req, timeout=None):
        vazut["h"] = {k.lower(): v for k, v in req.header_items()}
        vazut["corp"] = json.loads(req.data)
        vazut["url"] = req.full_url
        return Rasp(json.dumps(_api(_unealta({"tip_schema": "pt", "Sn_kVA": 400}))).encode())
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    assert m.intrare_llm("PT 400 kVA") is None                      # fără cheie: niciun apel
    assert "h" not in vazut
    cheie_api.seteaza("sk-ant-api03-" + "x" * 30)
    r = m.interpreteaza("PT 400 kVA", foloseste_llm=True)
    assert r["motor"] == "llm" and r["intrare_fizica"]["Sn_kVA"] == 400
    assert vazut["url"] == m.URL_API and vazut["h"]["x-api-key"].startswith("sk-ant-api03-")
    assert vazut["h"]["anthropic-beta"] == "server-side-fallback-2026-07-01"
    assert vazut["corp"]["model"] == "claude-opus-5-5" and vazut["corp"]["tools"][0]["name"] == "intrare_fizica"


# ------------------------------------------------------------------------------------------------ cheia și serverul
def test_cheia_memorie_fisier_mediu(monkeypatch):
    assert cheie_api.citeste() is None and cheie_api.sursa() is None
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env-" + "y" * 30)
    assert cheie_api.sursa() == "mediu"
    k = "sk-ant-api03-" + "z" * 30
    assert cheie_api.seteaza(k) == "aplicatie" and cheie_api.citeste() == k
    assert not cheie_api.fisier().exists()                          # fără „ține minte”: doar în memorie
    cheie_api.seteaza(k, pastreaza=True)
    f = cheie_api.fisier()
    assert f.read_text() == k and (f.stat().st_mode & 0o777) == 0o600
    assert str(RAD) not in str(f)                                   # niciodată în depozit
    cheie_api.seteaza("")
    assert not f.exists() and cheie_api.sursa() == "mediu"
    with pytest.raises(ValueError):
        cheie_api.seteaza("scurt")


class _H:
    """handler-ul din app.py fără socket (ca puntea Pyodide)."""

    def __new__(cls, metoda, cale, corp):
        import app

        class H(app.H):
            def __init__(self):
                self.command, self.path = metoda, cale
                b = corp if isinstance(corp, bytes) else json.dumps(corp).encode()
                self.headers = {"Content-Length": str(len(b))}
                self.rfile = io.BytesIO(b)

            def _send(self, code, body, ctype="application/json", fname=None, extra=None):
                self.raspuns = (code, body if isinstance(body, str) else body.decode())
        h = H()
        (h.do_GET if metoda == "GET" else h.do_POST)()
        return h.raspuns[0], json.loads(h.raspuns[1])


def test_api_chat_fara_cheie_mesaj_discret():
    st, d = _H("POST", "/api/chat", {"text": "PT 630 kVA cu plecări de 250, 160 și 100 A", "claude": True})
    assert st == 200 and d["interpretare"]["motor"] == "reguli" and d["model"]
    assert d["citire"]["avansata"] is False and "citire avansată indisponibilă" in d["citire"]["mesaj"]
    st, i = _H("GET", "/api/info", b"")
    assert i["claude"] is False


def test_api_cheie_si_chat_cu_raspuns_din_browser():
    k = "sk-ant-api03-" + "q" * 30
    st, d = _H("POST", "/api/setari/cheie", {"cheie": k})
    assert st == 200 and d == {"claude": True, "claude_sursa": "aplicatie"} and k not in json.dumps(d)
    st, i = _H("GET", "/api/info", b"")
    assert i["claude"] is True and k not in json.dumps(i)
    st, c = _H("POST", "/api/chat/cerere", {"text": "PT 400 kVA"})
    assert c["corp"]["model"] == "claude-opus-5-5" and c["beta"] == m.BETA_LLM and k not in json.dumps(c)
    st, d = _H("POST", "/api/chat", {"text": "PT 400 kVA", "raspuns_llm": _api(_unealta(
        {"tip_schema": "pt", "Sn_kVA": 400, "plecari": [{"nume": "TD-1", "In_A": 250}]}))})
    assert st == 200 and d["interpretare"]["motor"] == "llm" and d["citire"]["avansata"] is True
    assert d["model"]["calc"]["tip_schema"] == "pt"
    st, d = _H("POST", "/api/setari/cheie", {"cheie": ""})
    assert d["claude"] is False
    st, d = _H("POST", "/api/setari/cheie", {"cheie": "abc"})
    assert st == 400


def test_api_chat_eroare_din_browser():
    st, d = _H("POST", "/api/chat", {"text": "TG 50 kW cu 2 plecări de 32 A", "claude": False,
                                     "eroare_llm": "apel eșuat (HTTP 401)"})
    assert "HTTP 401" in d["citire"]["mesaj"] and d["interpretare"]["motor"] == "reguli"


def test_web_shim_apel_direct_din_browser():
    s = (RAD / "web/shim.js").read_text(encoding="utf-8")
    assert "anthropic-dangerous-direct-browser-access': 'true'" in s and "'x-api-key': CHEIE" in s
    assert "/api/chat/cerere" in s and "raspuns_llm" in s and "eroare_llm" in s
    assert "try { CHEIE = localStorage.getItem(LS_CHEIE)" in s and "localStorage.removeItem(LS_CHEIE)" in s
    h = (RAD / "static/index.html").read_text(encoding="utf-8")
    assert 'id="llm-cheie"' in h and 'type="password"' in h and "rămâne DOAR în acest browser" in h
    assert "/api/setari/cheie" in h and "r.citire.mesaj" in h
