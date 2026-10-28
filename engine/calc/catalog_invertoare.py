"""catalog_invertoare.py — modelele de invertoare / baterii recunoscute din cod (fără fișă tehnică), r6 „fotovoltaic”.

Folosit de motor (CEF / prosumator) și disponibil interpretorului:
* `cauta(producator, model)` → {producator, model, Pn_kW, hibrid, retea} sau None — Pn din codul modelului
  (valoarea nominală c.a. din denumirea comercială; Iac,max se ia din fișă, nu se presupune aici);
* `e_hibrid(producator, model)` → True pentru invertoarele cu port de baterie c.c. (Sungrow SH…RT / SH…T,
  Huawei SUN2000-3…10KTL-M1 / -L1 / -MAP0 / -MB0, Fronius GEN24, SMA Smart Energy, GoodWe ET/EH, Solis S6-EH / RHI …);
* `baterie_cc(producator, model)` / `bess_ca(producator, model)` → bateria e un pachet c.c. pentru invertor hibrid
  (Sungrow SBH / SBR, Huawei LUNA2000-5/10/15-S0, BYD HVS / HVM fără PCS) sau un sistem BESS cu PCS propriu
  (Sungrow PowerStack / ST…, Huawei LUNA2000-200/215 …, containere).
Valorile sunt cele din denumirea comercială a producătorului [DECIZIE: fără Iac, fără MPPT — din fișă].
"""
import re

# (regex pe „producător model” normalizat, producător, funcție Pn din match, hibrid, rețea[, extra])
# r7: extra = {"U_ca_V": 800, "Umax_dc_V": 1500} pentru invertoarele de 800 V c.a.; lipsă = 3 × 400 V
_MODELE = [
    # Fronius Tauro / Tauro ECO: „Tauro ECO 50-3-D”, „Tauro 50-3-P”, „Tauro ECO 99.9-3-D”, „Tauro ECO 100-3-D”
    (r"\bTAURO\s*(ECO)?\s*(\d+(?:[.,]\d+)?)\s*-\s*3", "Fronius", lambda m: float(m.group(2).replace(",", ".")), False, "tri"),
    # Fronius Symo / Symo GEN24 (hibrid) / Primo GEN24 (mono, hibrid)
    (r"\bSYMO\s*GEN24\s*(\d+(?:[.,]\d+)?)", "Fronius", lambda m: float(m.group(1).replace(",", ".")), True, "tri"),
    (r"\bPRIMO\s*GEN24\s*(\d+(?:[.,]\d+)?)", "Fronius", lambda m: float(m.group(1).replace(",", ".")), True, "mono"),
    # r8 (fotovoltaic P0-5): Fronius Primo „8.2-1” (sufixul -1 = monofazat, 1 × 230 V); Symo „-3” = trifazat
    (r"\bPRIMO\s*(\d+(?:[.,]\d+)?)\s*-\s*1\b", "Fronius", lambda m: float(m.group(1).replace(",", ".")), False, "mono"),
    (r"\bSYMO\s*(\d+(?:[.,]\d+)?)\s*-\s*3", "Fronius", lambda m: float(m.group(1).replace(",", ".")), False, "tri"),
    # SMA Sunny Tripower: „STP 110-60” (CORE2), „STP 50-41” (CORE1), „STP 25000TL-30”, „STP 10.0 SE” (Smart Energy, hibrid)
    # r8: SMA Sunny Boy (monofazat): „SB 5.0-1AV-41”, „Sunny Boy 6.0”, „SB3.6” (nu Sunny Boy Storage = PCS)
    (r"\b(?:SUNNY\s*BOY|SB)\s*(?!STORAGE)(\d+(?:[.,]\d+)?)(?:\s*-\s*1\w*)?\b(?!\s*K?WH)", "SMA",
     lambda m: float(m.group(1).replace(",", ".")) if float(m.group(1).replace(",", ".")) <= 10 else 0, False, "mono"),
    (r"\bSTP\s*(\d+(?:[.,]\d+)?)\s*(?:-\s*)?SE\b", "SMA", lambda m: float(m.group(1).replace(",", ".")), True, "tri"),
    (r"\bSTP\s*(\d{4,6})\s*TL", "SMA", lambda m: float(m.group(1)) / 1000.0, False, "tri"),
    (r"\bSTP\s*(\d{2,3})\s*-\s*\d{2}\b", "SMA", lambda m: float(m.group(1)), False, "tri"),
    (r"\bSUNNY\s*TRIPOWER\s*(?:CORE\s*[12]\s*)?(\d{2,3})\b", "SMA", lambda m: float(m.group(1)), False, "tri"),
    # Sungrow: SG…CX / SG…CX-P2 / SG…RT (rețea), SH…RT / SH…T / SH…RS (hibrid)
    (r"\bSH\s*(\d+(?:[.,]\d+)?)\s*RS\b", "Sungrow", lambda m: float(m.group(1).replace(",", ".")), True, "mono"),
    (r"\bSH\s*(\d+(?:[.,]\d+)?)\s*(RT|T)\b", "Sungrow", lambda m: float(m.group(1).replace(",", ".")), True, "tri"),
    (r"\bSG\s*(\d+(?:[.,]\d+)?)\s*RS\b", "Sungrow", lambda m: float(m.group(1).replace(",", ".")), False, "mono"),
    # r7 (fotovoltaic P0-3): SG…HX (SG250HX, SG320HX, SG350HX) — 800 V c.a. (3 fire, fără N), sistem 1500 V c.c.
    (r"\bSG\s*(\d+(?:[.,]\d+)?)\s*HX", "Sungrow", lambda m: float(m.group(1).replace(",", ".")), False, "tri",
     {"U_ca_V": 800, "Umax_dc_V": 1500}),
    (r"\bSG\s*(\d+(?:[.,]\d+)?)\s*(CX|RT|KTL)", "Sungrow", lambda m: float(m.group(1).replace(",", ".")), False, "tri"),
    # Huawei: SUN2000-…KTL-M1 / -L1 (hibrid, port LUNA2000), …K-MAP0 / -MB0 (hibrid), …KTL-M2/M3/M5 (rețea)
    # r8: -L1 / -LC0 = monofazat (1 × 230 V), -M1 / -MAP0 / -MB0 = trifazat
    (r"\bSUN\s*2000\s*-?\s*(\d+(?:[.,]\d+)?)\s*KTL\s*-?\s*L1\b", "Huawei", lambda m: float(m.group(1).replace(",", ".")), True, "mono"),
    # verificare 28.10.2026 (raport #99): hibrid DOAR SUN2000-3…10KTL-M1 (rezidențial, port LUNA2000); 100KTL-M1 e invertor
    # de rețea C&I (100 kW / 110 kVA, 10 MPPT, fără port de baterie) → intră pe regula generală „…KTL” (rețea)
    (r"\bSUN\s*2000\s*-?\s*((?:[3-9]|10)(?:[.,]\d+)?)\s*KTL\s*-?\s*M1\b", "Huawei", lambda m: float(m.group(1).replace(",", ".")), True, "tri"),
    (r"\bSUN\s*2000\s*-?\s*(\d+(?:[.,]\d+)?)\s*K\s*-?\s*LC0\b", "Huawei", lambda m: float(m.group(1).replace(",", ".")), True, "mono"),
    (r"\bSUN\s*2000\s*-?\s*(\d+(?:[.,]\d+)?)\s*K\s*-?\s*(MAP0|MB0)\b", "Huawei", lambda m: float(m.group(1).replace(",", ".")), True, "tri"),
    # r8: SUN2000-…K-MG0 (150K-MG0, 115K-MG0) — rețea, 3 × 400 V, Pn = cifra din cod
    (r"\bSUN\s*2000\s*-?\s*(\d+(?:[.,]\d+)?)\s*K\s*-?\s*MG0\b", "Huawei", lambda m: float(m.group(1).replace(",", ".")), False, "tri"),
    # r7: SUN2000-…KTL-H0/H1/H3 (185KTL-H1, 215KTL-H3, 330KTL-H1) — 800 V c.a. (fără N), 1500 V c.c.
    # r8 (fotovoltaic P1): la seria -H… cifra din cod = Smax [kVA], nu Pn — Pn din tabel (fișa Huawei), altfel Smax/1,1
    (r"\bSUN\s*2000\s*-?\s*(\d+(?:[.,]\d+)?)\s*KTL\s*-?\s*H\d\b", "Huawei", lambda m: _pn_huawei_h(m.group(1)),
     False, "tri", {"U_ca_V": 800, "Umax_dc_V": 1500, "Smax_din_cod": True}),
    (r"\bSUN\s*2000\s*-?\s*(\d+(?:[.,]\d+)?)\s*KTL", "Huawei", lambda m: float(m.group(1).replace(",", ".")), False, "tri"),
    # Solis: S6-EH3P…K (hibrid), RHI-…K (hibrid), S5-GC…K / S6-GC…K / S5-GR3P…K (rețea)
    (r"\bS6\s*-?\s*EH\s*1P\s*(\d+(?:[.,]\d+)?)\s*K", "Solis", lambda m: float(m.group(1).replace(",", ".")), True, "mono"),
    (r"\bS6\s*-?\s*EH\s*3P\s*(\d+(?:[.,]\d+)?)\s*K", "Solis", lambda m: float(m.group(1).replace(",", ".")), True, "tri"),
    (r"\bRHI\s*-?\s*3P\s*(\d+(?:[.,]\d+)?)\s*K", "Solis", lambda m: float(m.group(1).replace(",", ".")), True, "tri"),
    (r"\bRHI\s*-?\s*(\d+(?:[.,]\d+)?)\s*K", "Solis", lambda m: float(m.group(1).replace(",", ".")), True, "mono"),
    (r"\bS[56]\s*-?\s*G[CR]\s*(?:3P)?\s*(\d+(?:[.,]\d+)?)\s*K", "Solis", lambda m: float(m.group(1).replace(",", ".")), False, "tri"),
    # GoodWe: GW…K-ET / -EH / -BT (hibrid)
    (r"\bGW\s*(\d+(?:[.,]\d+)?)\s*K?\s*-?\s*(EH|ES)\b", "GoodWe", lambda m: float(m.group(1).replace(",", ".")), True, "mono"),
    (r"\bGW\s*(\d+(?:[.,]\d+)?)\s*K?\s*-?\s*(ET|BT)\b", "GoodWe", lambda m: float(m.group(1).replace(",", ".")), True, "tri"),
    # Growatt: MAX …KTL3, MOD …KTL3-X (rețea), MOD …KTL3-XH / SPH (hibrid)
    (r"\bMOD\s*(\d+(?:[.,]\d+)?)\s*KTL3?\s*-?\s*XH\b", "Growatt", lambda m: float(m.group(1).replace(",", ".")), True, "tri"),
    (r"\bSPH\s*(\d+(?:[.,]\d+)?)\s*(?:000)?\s*TL", "Growatt", lambda m: float(m.group(1).replace(",", ".")), True, None),
    (r"\b(?:MAX|MOD|MID)\s*(\d+(?:[.,]\d+)?)\s*KTL", "Growatt", lambda m: float(m.group(1).replace(",", ".")), False, "tri"),
    # r8: Growatt MIN / MIC …TL-X(E) — monofazat, Pn în W în cod („MIN 6000TL-X” = 6 kW)
    (r"\bMI[NC]\s*(\d{4,5})\s*TL", "Growatt", lambda m: float(m.group(1)) / 1000.0, False, "mono"),
]

# r8 (fotovoltaic P1): Huawei SUN2000-…KTL-H… — cifra din cod este Smax [kVA]; Pn [kW] din fișa producătorului
_HUAWEI_H_PN = {185: 175.0, 196: 175.0, 200: 185.0, 215: 200.0, 330: 300.0}


def _pn_huawei_h(cod):
    smax = float(str(cod).replace(",", "."))
    return _HUAWEI_H_PN.get(int(smax), round(smax / 1.1, 1)) if smax == int(smax) else round(smax / 1.1, 1)

# baterii c.c. (pe portul invertorului hibrid) vs. sisteme BESS cu PCS propriu (cuplaj c.a.)
_BAT_CC = (r"\bSBH\b", r"\bSBR\b", r"\bLUNA\s*2000\s*-?\s*(5|7|10|15|20|30)\s*-?\s*[SE]\d", r"\bLUNA\s*2000\s*$",
           r"\bBATTERY[\s-]*BOX\b(?!.*\bPCS\b)", r"\bHV[SM]\b", r"\bPYLONTECH\b", r"\bLYNX\b", r"\bRESERVOIR\b")
_BESS_CA = (r"\bSUNNY\s*ISLAND\b", r"\bSUNNY\s*BOY\s*STORAGE\b", r"\bSBS\s*\d", r"\bSI\s*\d+[.,]\d\s*H\b",
            r"\bPOWERSTACK\b", r"\bPOWER\s*TITAN\b", r"\bST\s*\d+\s*K?WH\b", r"\bLUNA\s*2000\s*-?\s*(1\d\d|2\d\d)\s*(?:K?WH)?\b",
            r"\bCHESS\b", r"\bPCS\b", r"\bCONTAINER\b", r"\bCUBE\b")


def _txt(producator, model):
    return re.sub(r"\s+", " ", f"{producator or ''} {model or ''}".upper().replace("_", " ")).strip()


# r8 (fotovoltaic P1): sisteme BESS cu PCS propriu — capacitatea [kWh] și puterea PCS [kW] din cod
# (regex, kWh(m), P_kW(m) sau None) — „LUNA2000-200KWH-2H1” = 200 kWh, „2H” = 2 ore → PCS 100 kW;
# „LUNA2000-215-2S10” = 215 kWh, 2 ore; „ST2752UX” (PowerTitan) = 2752 kWh
_BESS_COD = [
    (r"\bLUNA\s*2000\s*-?\s*(\d{3})\s*(?:K?WH)?\s*-?\s*(\d)\s*[HS]\d*", lambda m: float(m.group(1)),
     lambda m: float(m.group(1)) / float(m.group(2)) if int(m.group(2)) else None),
    (r"\bLUNA\s*2000\s*-?\s*(\d{3})\s*(?:K?WH)\b", lambda m: float(m.group(1)), lambda m: None),
    (r"\bST\s*(\d{3,4})\s*K?WH\b", lambda m: float(m.group(1)), lambda m: None),
]
# capacitatea unui modul / pachet de baterie [kWh] din cod (pentru n_module × kWh_modul)
_KWH_MODUL = [
    (r"\bLUNA\s*2000\s*-?\s*(5|7|10|15|20|30)\s*-?\s*[SE]\d", lambda m: float(m.group(1))),
    (r"\bBOS\s*-?\s*G\b", lambda m: 5.12),
    (r"\bUS\s*5000", lambda m: 4.8), (r"\bUS\s*3000", lambda m: 3.55), (r"\bUS\s*2000", lambda m: 2.4),
    (r"\bHV[SM]\s*(\d+(?:[.,]\d+)?)", lambda m: float(m.group(1).replace(",", "."))),
    (r"\bSBR\s*(\d{3})\b", lambda m: float(m.group(1)) / 10.0),
]


def bess_din_cod(producator=None, model=None):
    """r8: {kWh, P_kW?} pentru sistemele BESS cu PCS propriu recunoscute din cod, altfel None."""
    t = _txt(producator, model)
    for rx, kwh, p in _BESS_COD:
        m = re.search(rx, t)
        if m:
            d = {"kWh": kwh(m)}
            pp = p(m)
            if pp:
                d["P_kW"] = round(pp, 1)
            return d
    return None


def kwh_modul(producator=None, model=None):
    """r8: capacitatea unui modul / pachet de baterie din cod [kWh] sau None."""
    t = _txt(producator, model)
    for rx, f in _KWH_MODUL:
        m = re.search(rx, t)
        if m:
            return f(m)
    return None


def retea(producator=None, model=None):
    """r8: rețeaua invertorului din catalog („mono” = 1 × 230 V, „tri”) sau None dacă modelul nu e cunoscut."""
    d = cauta(producator, model)
    return d.get("retea") if d else None


def cauta(producator=None, model=None):
    """Modelul recunoscut din cod: {producator, model, Pn_kW, hibrid, retea?} sau None."""
    t = _txt(producator, model)
    if not t:
        return None
    for rx, prod, pn, hib, retea, *extra in _MODELE:
        m = re.search(rx, t)
        if m:
            try:
                p = pn(m)
            except (ValueError, TypeError):
                continue
            if not p or p <= 0:
                continue
            d = {"producator": prod, "model": (model or "").strip() or m.group(0).title(), "Pn_kW": round(p, 2),
                 "hibrid": hib}
            if retea:
                d["retea"] = retea
            if extra:
                d.update(extra[0])
            return d
    return None


# r11 (fotovoltaic #6 / #39): puterea aparentă maximă c.a. [kVA] din fișa producătorului, unde diferă de Pn sau e
# confirmată (V67 nu mai folosește 1,1·Pn); lipsă → Smax = Pn (cosφ 1 la puterea nominală)
_SMAX_KVA = [
    (r"\bSG\s*110\s*CX", 110.0),
    (r"\bSUN\s*2000\s*-?\s*115\s*KTL", 125.0),
]


def smax_kva(producator=None, model=None):
    """Smax c.a. din catalog (fișa producătorului) sau None."""
    t = _txt(producator, model)
    if not t:
        return None
    for rx, v in _SMAX_KVA:
        if re.search(rx, t):
            return v
    m = re.search(r"\bSUN\s*2000\s*-?\s*(\d+(?:[.,]\d+)?)\s*KTL\s*-?\s*H\d\b", t)
    if m:                       # seria -H…: cifra din cod este Smax [kVA]
        return float(m.group(1).replace(",", "."))
    return None


def e_hibrid(producator=None, model=None):
    d = cauta(producator, model)
    return bool(d and d.get("hibrid"))


def baterie_cc(producator=None, model=None):
    t = _txt(producator, model)
    return bool(t) and not bess_ca(producator, model) and any(re.search(rx, t) for rx in _BAT_CC)


def bess_ca(producator=None, model=None):
    t = _txt(producator, model)
    return bool(t) and any(re.search(rx, t) for rx in _BESS_CA)


# r7 (fotovoltaic P1): invertoarele de baterie cuplate în c.a. (fără port PV) — contradicție cu „cuplaj c.c.”
_INV_BATERIE_CA = (r"\bSUNNY\s*ISLAND\b", r"\bSUNNY\s*BOY\s*STORAGE\b", r"\bSBS\s*\d", r"\bSI\s*\d+[.,]\d\s*H\b")


def invertor_baterie_ca(producator=None, model=None):
    """True pentru invertoarele de baterie care se leagă numai pe bara c.a. (SMA Sunny Island, Sunny Boy Storage)."""
    t = _txt(producator, model)
    return bool(t) and any(re.search(rx, t) for rx in _INV_BATERIE_CA)


def u_ca(producator=None, model=None):
    """r7: tensiunea c.a. de racord a invertorului din catalog (800 V pentru SG…HX / SUN2000-…KTL-H…), altfel None."""
    d = cauta(producator, model)
    return d.get("U_ca_V") if d else None


_STOP_MODEL = {"se", "si", "și", "cu", "pe", "la", "in", "în", "din", "de", "pentru", "racordarea", "racordare", "care",
               "iar", "montat", "montate", "montaj", "existent", "existente", "nou", "noi", "buc", "bucati", "bucăți",
               "and", "with", "on", "the", "connected", "existing", "new"}


def curata_model(model):
    """r10 (fotovoltaic #46): eticheta de model tăiată la codul propriu-zis — „SG50CX. Racordarea se” → „SG50CX”:
    se taie la punctuație urmată de spațiu (sfârșit de frază) și la primul cuvânt de legătură românesc / englezesc."""
    if not isinstance(model, str):
        return model
    t = re.split(r"[.;,:!?]\s|[.;,:!?]$|\s[-–—]\s|\(", model.strip(), maxsplit=1)[0].strip()
    cuv = t.split()
    for i, w in enumerate(cuv):
        if i > 0 and w.lower() in _STOP_MODEL:
            cuv = cuv[:i]
            break
    return " ".join(cuv).strip() or model.strip()


def curata_modele(d):
    """Aplică `curata_model` pe toate câmpurile `model` dintr-o intrare (recursiv). Întoarce lista (vechi, nou)."""
    sch = []

    def rec(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "model" and isinstance(v, str):
                    n = curata_model(v)
                    if n != v:
                        sch.append((v, n))
                        x[k] = n
                else:
                    rec(v)
        elif isinstance(x, list):
            for v in x:
                rec(v)
    rec(d)
    return sch
