"""echipa1 P0-5 — datele obligatorii ale panoului „Verifică ce am înțeles”, calculate pe server (aceeași regulă ca
motorul), ca interfața să nu mai țină o copie proprie, diferită, a condițiilor.

Regula: lipsește doar ce motorul chiar nu poate desena. BESS independent (CEF fără invertoare PV, cu `bess.P_kW`) e o
lucrare completă — motorul desenează ramura PCS + BESS — deci NU cere invertoare.
"""


def _are(x):
    if x is None or isinstance(x, bool):
        return False
    if isinstance(x, (int, float)):
        return x > 0
    if isinstance(x, str):
        try:
            return float(x.replace(",", ".")) > 0
        except ValueError:
            return bool(x.strip())
    return bool(x)


def _sarcina(pl):
    return any(isinstance(p, dict) and (_are(p.get("In_A")) or _are(p.get("P_kW")) or _sarcina(p.get("copii")))
               for p in (pl or []))


def are_invertor(e):
    inv = e.get("invertoare") or []
    return (any(isinstance(r, dict) and _are(r.get("Pn_kW")) for r in inv) or _are(e.get("Pn_inv_kW"))
            or _are((e.get("invertor") or {}).get("Pn_kW") if isinstance(e.get("invertor"), dict) else None))


def are_bess(e):
    b = e.get("bess")
    if isinstance(b, list):
        return any(isinstance(x, dict) and (_are(x.get("P_kW")) or _are(x.get("kWh"))) for x in b)
    return isinstance(b, dict) and (_are(b.get("P_kW")) or _are(b.get("kWh")))


def campuri_lipsa(e):
    """[{camp, mesaj}] — datele fără de care motorul nu poate desena, pe tipul de schemă (lista goală = se poate confirma)"""
    if not isinstance(e, dict):
        return [{"camp": "tip_schema", "mesaj": "tipul lucrării"}]
    t = e.get("tip_schema")
    L = []
    if t == "bransament" and not any(_are(e.get(k)) for k in ("P_kW", "Ib_A", "S_kVA")):
        L.append({"camp": "P_kW", "mesaj": "puterea aprobată din ATR (Pa, kW)"})
    if t == "tablou" and not _are(e.get("P_kW")) and not _are(e.get("In_Q1_A")) and not _sarcina(e.get("plecari")):
        L.append({"camp": "P_kW", "mesaj": "puterea tabloului (Pa, kW) sau valorile plecărilor"})
    if t == "pt" and not _are(e.get("Sn_kVA")):
        L.append({"camp": "Sn_kVA", "mesaj": "puterea transformatorului (Sn trafo)"})
    if t == "ge_ats" and not _are(e.get("Sn_GE_kVA")):
        L.append({"camp": "Sn_GE_kVA", "mesaj": "puterea grupului electrogen (Sn, kVA)"})
    if t == "cef" and not are_invertor(e) and not are_bess(e):
        L.append({"camp": "invertoare", "mesaj": "invertoarele (cel puțin un rând cu puterea Pn, kW) sau sistemul de "
                                                  "stocare BESS (puterea P, kW)"})
    if t == "prosumator" and not are_invertor(e):
        L.append({"camp": "invertoare", "mesaj": "invertorul — puterea Pn (kW)"})
    if t == "locuinta" and not (e.get("circuite") or []):
        L.append({"camp": "circuite", "mesaj": "circuitele tabloului"})
    return L


# Î5 (proiectant 28.10.2026): la prosumator aplicația ÎNTREABĂ dacă există protecții pe partea de c.c. și pe c.a.
# (nu blochează — nedeclarat = desenate amândouă; răspunsul „nu” scoate SPD-ul / separatorul c.c., respectiv SPD-ul c.a.)
INTREBARE_PROTECTII = {
    "protectii_cc": "Există protecții pe partea de c.c. (cutie c.c.: separator de c.c. sub sarcină + SPD c.c.)?",
    "protectii_ca": "Există protecții pe partea de c.a. (SPD c.a. la invertor / în TD-PV)?",
}


def intrebari_confirmare(e):
    """[{camp, intrebare}] — întrebările neblocante ale panoului de confirmare (lista goală = nimic de întrebat)"""
    if not isinstance(e, dict) or e.get("tip_schema") != "prosumator":
        return []
    return [{"camp": k, "intrebare": q} for k, q in INTREBARE_PROTECTII.items() if e.get(k) is None]
