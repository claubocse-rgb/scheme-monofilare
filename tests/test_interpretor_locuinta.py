"""Interpretorul local pentru tipul „locuinta” (casă / apartament → intrarea motorului SPEC §C.8).

Rulare: cd /home/claude/sm && python3 -m pytest tests/test_interpretor_locuinta.py -q
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import interpretor as m  # noqa: E402
from engine.interpretor import interpreteaza, interpreteaza_local  # noqa: E402

ENUM = set(m.ENUM_RECEPTORI_LOC)


def _rec(r):
    return [c["receptor"] for c in r["intrare_fizica"]["circuite"]]


def _circ(r, nume):
    return next(c for c in r["intrare_fizica"]["circuite"] if c["nume"] == nume)


def _forma_valida(r):
    i = r["intrare_fizica"]
    assert i["tip_schema"] == "locuinta" and i["retea"] in ("mono", "tri")
    assert set(i) <= {"tip_schema", "retea", "alimentare", "schema_pamant", "RA_ohm", "circuite", "ks"}
    assert set(i["alimentare"]) <= {"tip", "In_Q_bransament_A", "P_aprobata_kW", "L_coloana_m", "cablu"}
    for c in i["circuite"]:
        assert c["receptor"] in ENUM and c["nume"]
        assert set(c) <= {"nume", "receptor", "P_kW", "L_m", "faza"}
        if i["retea"] == "mono":
            assert "faza" not in c
    assert not m.valideaza_forma(i)
    assert r["intelegere"].startswith("Am înțeles: locuință")


def test_apartament_mono_7kw_set_tipic():
    r = interpreteaza_local("apartament 2 camere, monofazat 7 kW")
    _forma_valida(r)
    i = r["intrare_fizica"]
    assert r["actiune"] == "genereaza"
    assert i["retea"] == "mono" and i["alimentare"] == {"P_aprobata_kW": 7}
    assert _rec(r) == ["iluminat", "prize", "prize_bucatarie", "prize_baie", "masina_spalat_rufe"]
    assert any("set tipic pentru apartament" in p and "PRESUPUNERE" in p for p in r["presupus"])
    assert "P aprobată = 7 kW" in r["intelegere"] and "5 circuite" in r["intelegere"]


def test_casa_p1_trifazat_receptori_speciali():
    r = interpreteaza_local("casă P+1 trifazat 15 kW cu plită, pompă de căldură și încărcător mașină 11 kW, coloană 25 m")
    _forma_valida(r)
    i = r["intrare_fizica"]
    assert i["retea"] == "tri"
    assert i["alimentare"] == {"P_aprobata_kW": 15, "L_coloana_m": 25}       # 11 kW aparține VE, nu alimentării
    assert _circ(r, "Plită") == {"nume": "Plită", "receptor": "plita", "faza": "3F"}
    assert _circ(r, "Pompă de căldură")["faza"] == "3F"
    assert _circ(r, "Încărcare VE") == {"nume": "Încărcare VE", "receptor": "vehicul_electric", "P_kW": 11, "faza": "3F"}
    # ≥ 3 receptori listați (fără „plus”) → setul de bază + cei listați
    assert _rec(r)[:4] == ["iluminat", "prize", "prize_bucatarie", "prize_baie"] and len(_rec(r)) == 7
    assert any("circuitele de bază" in p for p in r["presupus"])
    assert "Încărcare VE 11 kW (3F)" in r["intelegere"] and "casă P+1" in r["intelegere"]


def test_casa_parter_tt_cartus():
    r = interpreteaza_local("casă parter trifazată TT, beneficiar Ion Pop, Oradea")
    _forma_valida(r)
    i = r["intrare_fizica"]
    assert i["schema_pamant"] == "TT" and i["retea"] == "tri"
    assert r["cartus"]["beneficiar"] == "Ion Pop" and r["cartus"]["adresa"]["localitate"] == "Oradea"
    assert [c["nume"] for c in i["circuite"]] == [n for n, _ in m.SET_TIPIC["casa_parter"]]
    assert any("RA nedeclarat" in p for p in r["presupus"])
    assert "schema TT" in r["intelegere"] and "beneficiar Ion Pop" in r["intelegere"]


def test_multiplicatori_bucati_si_x2():
    r = interpreteaza_local("casă parter monofazată cu aer condiționat 2 bucăți, boiler ×2, Q 40 A")
    _forma_valida(r)
    nume = [c["nume"] for c in r["intrare_fizica"]["circuite"]]
    assert {"Aer condiționat 1", "Aer condiționat 2", "Boiler 1", "Boiler 2"} <= set(nume)
    assert "Boiler" not in nume                                  # boilerul tipic e înlocuit de cel listat
    assert _rec(r).count("aer_conditionat") == 2 and _rec(r).count("boiler") == 2
    assert r["intrare_fizica"]["alimentare"] == {"In_Q_bransament_A": 40}
    assert any("2 circuite separate" in p for p in r["presupus"])


def test_sinonime_wallbox_inductie_ac_hidrofor():
    r = interpreteaza_local("vilă trifazată 22 kW: wallbox, inducție, AC x2, hidrofor, centrală, "
                            "coloană 30 m până la tablou")
    _forma_valida(r)
    rec = _rec(r)
    for x in ("vehicul_electric", "plita", "pompa_apa", "centrala_termica"):
        assert x in rec
    assert rec.count("aer_conditionat") == 2
    assert r["intrare_fizica"]["alimentare"] == {"P_aprobata_kW": 22, "L_coloana_m": 30}
    for s, rec_ in (("apartament cu stație de încărcare EV", "vehicul_electric"), ("casă cu aragaz electric", "plita"),
                    ("casă cu climatizare", "aer_conditionat"), ("casă cu mașină de spălat vase", "masina_spalat_vase"),
                    ("casă cu mașină de spălat", "masina_spalat_rufe"), ("casă cu hidrofor", "pompa_apa")):
        assert rec_ in _rec(interpreteaza_local(s)), s


def test_bransament_simplu_ramane_bransament():
    for s in ("branșament BMPM 7 kW", "branșament BMPM 7 kW pentru casă", "BMPT 20 kW casă, cablu 30 m"):
        r = interpreteaza_local(s)
        assert r["tip_schema"] == "bransament", s
    # casă + circuite → locuință, chiar dacă apare branșamentul
    r = interpreteaza_local("branșament BMPT 15 kW pentru casă cu plită, cuptor, pompă de căldură")
    assert r["tip_schema"] == "locuinta" and r["intrare_fizica"]["retea"] == "tri"
    # prosumatorul pe casă rămâne prosumator
    assert interpreteaza_local("prosumator casă 6 kW monofazat")["tip_schema"] == "prosumator"


def test_mono_13kw_atentionare_trifazat():
    r = interpreteaza_local("casă monofazată 13 kW")
    _forma_valida(r)
    # r7 (locuințe #20, #23): peste 40 A (9,2 kW) la monofazat se generează ȘI se întreabă trecerea pe trifazat
    assert r["actiune"] == "genereaza_cu_intrebare" and any("trifazat" in q for q in r["intrebari"])
    assert any("peste 11 kW se recomandă trifazat" in a for a in r["avertismente"])
    assert "Verificări:" in r["intelegere"]
    assert not interpreteaza_local("casă monofazată 9 kW")["avertismente"] or not any(
        "11 kW" in a for a in interpreteaza_local("casă monofazată 9 kW")["avertismente"])


def test_fara_circuite_set_tipic_p1():
    r = interpreteaza_local("tablou de casă P+1, trifazat, Q 25 A")
    _forma_valida(r)
    assert [c["nume"] for c in r["intrare_fizica"]["circuite"]] == [n for n, _ in m.SET_TIPIC["casa_p1"]]
    # r5 (P1-10): plita și cuptorul electrice intră doar dacă sunt numite
    assert not {"plita", "cuptor"} & set(_rec(r))
    assert any("set tipic pentru casă P+1" in p for p in r["presupus"])


def test_plus_tablou_tipic_adauga_la_set():
    r = interpreteaza_local("apartament, tablou tipic plus aer condiționat, boiler, uscător")
    nume = [c["nume"] for c in r["intrare_fizica"]["circuite"]]
    assert nume[:5] == [n for n, _ in m.SET_TIPIC["apartament"]]
    assert nume[5:] == ["Aer condiționat", "Boiler", "Uscător"]


def test_detectii_cuvinte_cheie():
    for s in ("casa 8 kW", "locuință unifamilială", "apartament", "vilă", "P+1 cu mansardă", "parter",
              "tablou de apartament", "tablou de casă"):
        assert interpreteaza_local(s)["tip_schema"] == "locuinta", s


def test_tt_ra_ks_si_pozare():
    r = interpreteaza_local("tablou de apartament monofazat, priză de pământ proprie RA 30 ohm, ks 0,6")
    i = r["intrare_fizica"]
    assert i["schema_pamant"] == "TT" and i["RA_ohm"] == 30 and i["ks"] == 0.6
    assert "cablu" not in i["alimentare"]                       # „pământ” din priză ≠ pozare D1
    assert "prize" in _rec(r)                                    # priza de pământ nu e circuit, dar setul tipic rămâne


def test_putere_receptor_si_3f_explicit():
    r = interpreteaza_local("casă trifazată 20 kW: plită 7 kW, pompă de căldură trifazată 6 kW, wallbox 7,4 kW, saună")
    assert _circ(r, "Plită") == {"nume": "Plită", "receptor": "plita", "P_kW": 7}          # ≤ 7,4 kW → fără 3F
    assert _circ(r, "Pompă de căldură")["faza"] == "3F"                                    # „trifazată” lângă receptor
    assert "faza" not in _circ(r, "Încărcare VE") and _circ(r, "Încărcare VE")["P_kW"] == 7.4
    assert _circ(r, "Saună")["faza"] == "3F"
    assert r["intrare_fizica"]["alimentare"]["P_aprobata_kW"] == 20


@pytest.mark.parametrize("text,cod", [("casă monofazată 150 kW", "I06"),
                                      ("casă trifazată 15 kW cu plită 45 kW, cuptor, boiler", "I06")])
def test_valori_absurde_refuz(text, cod):
    r = interpreteaza_local(text)
    assert r["actiune"] == "refuza" and r["refuz_cod"] == cod and r["intrebari"]


def test_iesirea_merge_in_motor():
    """Intrarea produsă e acceptată de motorul de calcul (fără blocări de formă V07/V12)."""
    from engine.calc import calculeaza
    for s in ("apartament 2 camere, monofazat 7 kW, Q 32 A",
              "casă P+1 trifazat 25 kW, Q 50 A, cu plită, pompă de căldură și încărcător mașină 11 kW, coloană 25 m",
              "tablou de apartament monofazat, priză de pământ proprie RA 30 ohm, ks 0,6"):
        z = calculeaza(interpreteaza_local(s)["intrare_fizica"])
        blocante = [v["cod"] for v in z["verificari"] if v["nivel"] == "BLOCANT"]
        assert not blocante, (s, blocante)


def test_llm_locuinta_normalizare(monkeypatch):
    monkeypatch.setattr(m, "intrare_llm", lambda text: {
        "tip_schema": "locuinta", "retea": "tri", "schema_pamant": "TT", "RA_ohm": "25", "ks": "0,7",
        "alimentare": {"tip": "bransament_nou", "P_aprobata_kW": "15", "L_coloana_m": 20, "x": 1},
        "circuite": [{"nume": "Plită", "receptor": "plita", "faza": "3f", "P_kW": "7,5"},
                     {"nume": "Frigider", "receptor": "frigider"}, "gunoi"]})
    r = interpreteaza("casă trifazată 15 kW cu plită", foloseste_llm=True)
    i = r["intrare_fizica"]
    assert r["motor"] == "llm" and i["ks"] == 0.7 and i["RA_ohm"] == 25 and i["schema_pamant"] == "TT"
    assert i["alimentare"] == {"tip": "bransament_nou", "P_aprobata_kW": 15, "L_coloana_m": 20}
    # F.9: receptorii citiți de Claude + setul tipic al locuinței (aceeași convenție ca regulile locale)
    assert {"nume": "Plită", "receptor": "plita", "P_kW": 7.5, "faza": "3F"} in i["circuite"]
    assert {"nume": "Frigider", "receptor": "alt_circuit"} in i["circuite"]
    assert any(c["receptor"] == "iluminat" for c in i["circuite"])
    monkeypatch.setattr(m, "intrare_llm", lambda text: {"tip_schema": "locuinta", "retea": "mono"})   # fără circuite
    r = interpreteaza("casă 7 kW", foloseste_llm=True)       # F.9: setul tipic declarat ca presupunere (ca regulile locale)
    assert r["motor"] == "llm" and r["intrare_fizica"]["circuite"] and any("set tipic" in p for p in r["presupus"])


def test_reteaua_nu_se_presupune():
    """Rețeaua locuinței e obligatorie: fără „monofazat” / „trifazat” interpretorul întreabă, motorul blochează."""
    for t in ("casă parter cu plită și boiler", "apartament 2 camere 7 kW"):
        r = interpreteaza_local(t)
        assert r["actiune"] == "genereaza_cu_intrebare", (t, r["actiune"])
        assert "retea" not in r["intrare_fizica"]
        assert any("monofazat" in q for q in r["intrebari"])
    from engine.calc import calculeaza
    z = calculeaza({"tip_schema": "locuinta", "alimentare": {"P_aprobata_kW": 7}, "circuite": [{"nume": "Prize", "receptor": "prize"}]})
    assert [(v["cod"], v["obiect"]) for v in z["verificari"] if v["nivel"] == "BLOCANT"] == [("V07", "retea")]


def test_bransament_mic_fara_retea_intreaba_iar_cel_mare_e_trifazat():
    r = interpreteaza_local("branșament 7 kW, cablu 20 m")
    assert r["actiune"] == "genereaza_cu_intrebare" and "retea" not in r["intrare_fizica"]
    r = interpreteaza_local("branșament 60 kW, cablu 30 m")
    assert r["intrare_fizica"]["retea"] == "tri" and any("nu încape în monofazat" in p for p in r["presupus"])
    r = interpreteaza_local("prosumator 3 kW pe branșament existent")
    assert "retea" not in r["intrare_fizica"]
