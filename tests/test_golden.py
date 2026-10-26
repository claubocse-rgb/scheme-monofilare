"""Testul cazurilor golden (SPEC §H.4 pct. 2): toate cele 74 de cazuri (v1.1) din tests/date/cazuri_golden.json.

Compararea câmpurilor urmează `_schema.toleranta_implicita`:
  * exact: bloc, protectie.tip/curba/In_A/Ir_A/Icu_kA, material, n_paralel, S_faza_mm2, S_N_mm2, S_PE_mm2, PE, cablu, TC;
  * relativ 0,5 %: Ib_A, Iz_min_A, Iz_corectat_A, Iac_total_A, S_total_kVA, In_T_A (și celelalte mărimi numerice
    neclasificate în schemă: k_total, Pi_kW, ks …);
  * ΔU: ±2 % relativ sau ±0,02 puncte procentuale (se ia mai larga); Ik3: ±3 %; Ik1: ±5 %; Ia: exact.
  * Textele se compară exact; spațiile fără întrerupere cerute de SPEC §E.2 (U+00A0, U+202F) se compară ca spații
    obișnuite, deoarece JSON-ul golden folosește spații simple.
Verificările BLOCANT/AVERTISMENT se compară ca multiset (cod, nivel, obiect), plus `blocheaza_export`; pentru INFO se
verifică doar că toate codurile din `verificari_info` apar.

Cazurile marcate xfail au discrepanța justificată numeric în spec/DISCREPANTE.md.
"""
import json
import os
import re
import sys
from collections import Counter

import pytest

RADACINA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RADACINA)

from engine.calc import calculeaza  # noqa: E402

with open(os.path.join(RADACINA, "tests", "date", "cazuri_golden.json"), encoding="utf-8") as _f:
    GOLDEN = json.load(_f)
CAZURI = GOLDEN["cazuri"]

DISCREPANTE = {}   # B20, P07, X01 rezolvate prin arbitraj (spec/ARBITRAJ.md D-01…D-03); golden v1.1

EXACT = {"bloc", "tip", "curba", "In_A", "Ir_A", "Icu_kA", "material", "n_paralel", "S_faza_mm2", "S_N_mm2",
         "S_PE_mm2", "PE", "cablu", "TC", "Ia_A"}
REL_05 = {"Ib_A", "Iz_min_A", "Iz_corectat_A", "Iac_total_A", "S_total_kVA", "In_T_A"}


def _norm_text(s):
    return re.sub(r"[   ]", " ", s)


def _num_ok(cheie, a, e):
    if cheie in EXACT:
        return abs(a - e) <= 1e-9 * max(1.0, abs(e))
    if "dU" in cheie:
        return abs(a - e) <= max(0.02 * abs(e), 0.02) + 1e-12
    if "Ik3" in cheie:
        return abs(a - e) <= 0.03 * abs(e) + 1e-12
    if "Ik1" in cheie:
        return abs(a - e) <= 0.05 * abs(e) + 1e-12
    return abs(a - e) <= 0.005 * abs(e) + 1e-9


def compara(asteptat, actual, cale=""):
    """Compară recursiv `asteptat` (golden) cu `actual` (motor); întoarce lista diferențelor."""
    dif = []
    if isinstance(asteptat, dict):
        if not isinstance(actual, dict):
            return [f"{cale}: așteptat dict, primit {actual!r}"]
        for k, v in asteptat.items():
            if k not in actual:
                dif.append(f"{cale}.{k}: lipsește (așteptat {v!r})")
            else:
                dif += compara(v, actual[k], f"{cale}.{k}")
        return dif
    if isinstance(asteptat, list):
        if not isinstance(actual, list) or len(actual) != len(asteptat):
            return [f"{cale}: listă de lungime {len(asteptat)} așteptată, primit "
                    f"{len(actual) if isinstance(actual, list) else actual!r}"]
        for i, (e, a) in enumerate(zip(asteptat, actual)):
            dif += compara(e, a, f"{cale}[{i}]")
        return dif
    cheie = cale.rsplit(".", 1)[-1]
    if isinstance(asteptat, bool) or asteptat is None:
        if actual != asteptat:
            dif.append(f"{cale}: așteptat {asteptat!r}, primit {actual!r}")
    elif isinstance(asteptat, (int, float)):
        if not isinstance(actual, (int, float)) or isinstance(actual, bool) or not _num_ok(cheie, actual, asteptat):
            dif.append(f"{cale}: așteptat {asteptat!r}, primit {actual!r}")
    elif isinstance(asteptat, str):
        if not isinstance(actual, str) or _norm_text(actual) != _norm_text(asteptat):
            dif.append(f"{cale}: așteptat {asteptat!r}, primit {actual!r}")
    return dif


def diferente_caz(caz):
    """Toate diferențele dintre rezultatul motorului și cazul golden (câmpuri + verificări)."""
    r = calculeaza(caz["intrare"])
    dif = compara(caz["asteptat"], r["rezultat"], "asteptat")
    exp = Counter((v["cod"], v["nivel"], v["obiect"]) for v in caz["verificari"])
    act = Counter((v["cod"], v["nivel"], v["obiect"]) for v in r["verificari"])
    if exp != act:
        dif.append(f"verificari: lipsă {dict(exp - act)}, în plus {dict(act - exp)}")
    if r["blocheaza_export"] != caz["blocheaza_export"]:
        dif.append(f"blocheaza_export: așteptat {caz['blocheaza_export']}, primit {r['blocheaza_export']}")
    coduri_info = {i["cod"] for i in r["info"]}
    lipsa = [c for c in caz["verificari_info"] if c not in coduri_info]
    if lipsa:
        dif.append(f"verificari_info lipsă: {lipsa}")
    return dif


def _param(caz):
    marks = []
    if caz["id"] in DISCREPANTE:
        marks.append(pytest.mark.xfail(reason=DISCREPANTE[caz["id"]], strict=True))
    return pytest.param(caz, id=caz["id"], marks=marks)


@pytest.mark.parametrize("caz", [_param(c) for c in CAZURI])
def test_caz_golden(caz):
    dif = diferente_caz(caz)
    assert not dif, f"{caz['id']} ({caz['descriere']}):\n  " + "\n  ".join(dif)


def test_numar_cazuri():
    assert len(CAZURI) == 74
    assert len({c["id"] for c in CAZURI}) == 74
