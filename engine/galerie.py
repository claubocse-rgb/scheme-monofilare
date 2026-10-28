"""galerie — galeria personală de circuite / plecări / tablouri tip, reutilizabile între proiecte (E2, funcționalitatea #6).

Formatul de date (date/galerie.json, lângă profile.json; în browser e păstrat ca celelalte fișiere ale utilizatorului):

    {"versiune": 1,
     "elemente": [{"id": "g-…", "nume": "Tablou bucătărie standard", "tip": "circuit" | "plecare" | "tablou" | "schema",
                   "tip_schema": "locuinta" | "tablou" | … (pentru „tablou” / „schema”),
                   "descriere": "…", "etichete": ["bucătărie", …],
                   "date": {…},        # circuit: un element din intrare.circuite; plecare: un element din plecari;
                                       # tablou: {"circuite": […]} sau {"plecari": […]} (+ câmpurile tabloului);
                                       # schema: intrarea fizică completă (fără cartuș)
                   "creat": "2026-10-28T10:00:00", "modificat": "…"}]}

Operații: citeste(), adauga(elem) (id nou sau înlocuire după id), sterge(id), valideaza(elem), aplica(elem, intrare)
(adaugă circuitul / plecarea / tabloul în intrarea curentă — interfața îl folosește pentru „Inserează din galerie”).
"""
import copy
import datetime
import json
import os
import pathlib
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATE = pathlib.Path(os.environ.get("SM_DATE") or ROOT / "date")
FISIER = DATE / "galerie.json"
TIPURI = ("circuit", "plecare", "tablou", "schema")
MAX_ELEMENTE = 500
MAX_OCTETI_ELEMENT = 200_000


def _gol():
    return {"versiune": 1, "elemente": []}


def citeste():
    try:
        d = json.loads(FISIER.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _gol()
    if not isinstance(d, dict) or not isinstance(d.get("elemente"), list):
        return _gol()
    d["elemente"] = [e for e in d["elemente"] if isinstance(e, dict) and e.get("id")]
    return d


def _scrie(d):
    FISIER.parent.mkdir(parents=True, exist_ok=True)
    FISIER.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


def _fara_interne(o):
    if isinstance(o, dict):
        return {k: _fara_interne(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, list):
        return [_fara_interne(v) for v in o]
    return o


def valideaza(e):
    """elementul curățat sau ValueError cu motivul (în română)"""
    if not isinstance(e, dict):
        raise ValueError("elementul de galerie trebuie să fie un obiect")
    nume = str(e.get("nume") or "").strip()
    if not nume:
        raise ValueError("elementul de galerie are nevoie de un nume")
    tip = e.get("tip")
    if tip not in TIPURI:
        raise ValueError(f"tipul trebuie să fie unul dintre: {', '.join(TIPURI)}")
    date = e.get("date")
    if not isinstance(date, dict) or not date:
        raise ValueError("lipsesc datele elementului (câmpul „date”)")
    date = _fara_interne(copy.deepcopy(date))
    if tip == "circuit" and not date.get("nume"):
        date["nume"] = nume
    if tip == "tablou" and not (isinstance(date.get("circuite"), list) or isinstance(date.get("plecari"), list)):
        raise ValueError("un tablou din galerie conține „circuite” (locuință) sau „plecari” (tablou)")
    if tip == "schema" and not date.get("tip_schema"):
        raise ValueError("o schemă din galerie are nevoie de tip_schema")
    if len(json.dumps(date, ensure_ascii=False)) > MAX_OCTETI_ELEMENT:
        raise ValueError("elementul este prea mare pentru galerie")
    acum = datetime.datetime.now().replace(microsecond=0).isoformat()
    et = e.get("etichete") or []
    return {"id": str(e.get("id") or "g-" + uuid.uuid4().hex[:12]), "nume": nume[:120], "tip": tip,
            "tip_schema": e.get("tip_schema") or (date.get("tip_schema") if tip == "schema" else
                                                   "locuinta" if "circuite" in date else "tablou" if "plecari" in date else None),
            "descriere": str(e.get("descriere") or "")[:500],
            "etichete": [str(x)[:40] for x in et if str(x).strip()][:12] if isinstance(et, list) else [],
            "date": date, "creat": e.get("creat") or acum, "modificat": acum}


def adauga(e):
    d = citeste()
    x = valideaza(e)
    lst = [y for y in d["elemente"] if y["id"] != x["id"]]
    vechi = next((y for y in d["elemente"] if y["id"] == x["id"]), None)
    if vechi:
        x["creat"] = vechi.get("creat") or x["creat"]
    if len(lst) >= MAX_ELEMENTE:
        raise ValueError(f"galeria are deja {MAX_ELEMENTE} elemente — ștergeți câteva")
    lst.append(x)
    d["elemente"] = lst
    _scrie(d)
    return {"element": x, "galerie": d}


def sterge(id_):
    d = citeste()
    n = len(d["elemente"])
    d["elemente"] = [y for y in d["elemente"] if y["id"] != id_]
    if len(d["elemente"]) == n:
        raise ValueError("elementul nu există în galerie")
    return _scrie(d)


def aplica(e, intrare):
    """inserează elementul în intrarea fizică curentă (copie) și o întoarce"""
    e = valideaza(e) if "modificat" not in (e or {}) else e
    out = copy.deepcopy(intrare) if isinstance(intrare, dict) else {}
    dt = copy.deepcopy(e["date"])
    if e["tip"] == "schema":
        return dt
    ts = out.get("tip_schema") or e.get("tip_schema")
    if e["tip"] == "circuit":
        out.setdefault("circuite" if ts == "locuinta" else "plecari", []).append(dt)
    elif e["tip"] == "plecare":
        out.setdefault("plecari", []).append(dt)
    elif e["tip"] == "tablou":
        if ts == "locuinta" and "circuite" in dt:
            out.setdefault("circuite", []).extend(dt["circuite"])
        elif ts == "locuinta":
            out.setdefault("tablouri_secundare", []).append(dt)
        else:
            out.setdefault("plecari", []).extend(dt.get("plecari") or [])
    return out
