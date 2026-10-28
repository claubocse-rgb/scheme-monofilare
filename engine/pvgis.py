"""pvgis — producția estimată a unei instalații PV din PVGIS (JRC, API public, gratuit), cu cache și mod offline (E2).

    url = cerere_url(lat, lon, kWp, unghi=30, azimut=0, pierderi=14)     # adresa PVcalc (v5.3, JSON)
    rez = estimeaza(lat, lon, kWp, ...)          # local: apel HTTP + cache în date/pvgis_cache.json
    rez = din_raspuns(json_pvgis, kWp)           # browser (Pyodide): JS face apelul, Python interpretează răspunsul
    rez = din_valoare(kWh_kWp_an, kWp)           # offline: valoarea introdusă de proiectant

Toate întorc același dict: {sursa, kWh_an, kWh_kWp_an, lunar[12], pierderi_pct, parametri, mesaj}. Fără rețea →
{"necesita_valoare": True, "mesaj": …} — interfața cere atunci producția specifică (kWh/kWp/an).
Convenția PVGIS pentru azimut („aspect”): 0 = sud, −90 = est, 90 = vest.
"""
import json
import os
import pathlib
import urllib.parse
import urllib.request

URL_API = "https://re.jrc.ec.europa.eu/api/v5_3/PVcalc"
ROOT = pathlib.Path(__file__).resolve().parents[1]
DATE = pathlib.Path(os.environ.get("SM_DATE") or ROOT / "date")
CACHE = DATE / "pvgis_cache.json"
PIERDERI_SISTEM_IMPLICIT = 14.0      # % — valoarea implicită PVGIS (cabluri, invertor, murdărie, mismatch)
LUNI = ["ian", "feb", "mar", "apr", "mai", "iun", "iul", "aug", "sep", "oct", "nov", "dec"]


def _num(v, nume, lo=None, hi=None):
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"{nume} lipsește sau nu e număr")
    if (lo is not None and x < lo) or (hi is not None and x > hi):
        raise ValueError(f"{nume} = {x} în afara domeniului [{lo}; {hi}]")
    return x


def parametri(lat, lon, kWp, unghi=30, azimut=0, pierderi=None, montaj="free"):
    p = {"lat": round(_num(lat, "latitudinea", -60, 70), 4), "lon": round(_num(lon, "longitudinea", -180, 180), 4),
         "peakpower": _num(kWp, "puterea (kWp)", 0.01, 100000),
         "loss": _num(PIERDERI_SISTEM_IMPLICIT if pierderi is None else pierderi, "pierderile (%)", 0, 50),
         "angle": _num(unghi, "înclinarea (°)", 0, 90), "aspect": _num(azimut, "azimutul (°)", -180, 180),
         "mountingplace": "building" if str(montaj).lower() in ("building", "cladire", "integrat") else "free",
         "outputformat": "json"}
    return p


def cerere_url(lat, lon, kWp, unghi=30, azimut=0, pierderi=None, montaj="free"):
    """adresa completă a cererii PVcalc — o poate apela și browserul"""
    return URL_API + "?" + urllib.parse.urlencode(parametri(lat, lon, kWp, unghi, azimut, pierderi, montaj))


def _cheie(p):
    return "|".join(f"{k}={p[k]}" for k in ("lat", "lon", "angle", "aspect", "loss", "mountingplace"))


def _citeste_cache():
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _scrie_cache(c):
    try:
        DATE.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def din_raspuns(raspuns, kWp=None):
    """interpretarea răspunsului JSON PVcalc (dict sau text) → producția estimată"""
    if isinstance(raspuns, (str, bytes)):
        raspuns = json.loads(raspuns)
    if not isinstance(raspuns, dict) or "outputs" not in raspuns:
        msg = (raspuns or {}).get("message") if isinstance(raspuns, dict) else None
        raise ValueError("răspunsul PVGIS nu conține rezultate" + (f" ({msg})" if msg else ""))
    tot = ((raspuns["outputs"].get("totals") or {}).get("fixed") or {})
    lun = ((raspuns["outputs"].get("monthly") or {}).get("fixed") or [])
    inp = raspuns.get("inputs") or {}
    pp = kWp or ((inp.get("pv_module") or {}).get("peak_power"))
    e_y = float(tot["E_y"])
    pp = float(pp) if pp else None
    return {"sursa": "PVGIS (JRC) " + str((raspuns.get("meta") or {}).get("version") or "v5.3"),
            "kWh_an": e_y, "kWh_kWp_an": e_y / pp if pp else None, "kWp": pp,
            "lunar": [{"luna": LUNI[int(x.get("month", i + 1)) - 1], "kWh": x.get("E_m")} for i, x in enumerate(lun)],
            "iradiere_kWh_m2_an": tot.get("H(i)_y"), "pierderi_pct": tot.get("l_total"),
            "parametri": {"lat": (inp.get("location") or {}).get("latitude"), "lon": (inp.get("location") or {}).get("longitude"),
                          "unghi": ((inp.get("mounting_system") or {}).get("fixed") or {}).get("slope", {}).get("value"),
                          "azimut": ((inp.get("mounting_system") or {}).get("fixed") or {}).get("azimuth", {}).get("value"),
                          "pierderi_sistem_pct": (inp.get("pv_module") or {}).get("system_loss")},
            "mesaj": f"producție estimată {e_y:,.0f} kWh/an".replace(",", " ") + (f" ({e_y / pp:,.0f} kWh/kWp/an)".replace(",", " ") if pp else "")}


def din_valoare(kWh_kWp_an, kWp):
    """modul offline: producția specifică introdusă de proiectant (ex. din PVGIS consultat manual)"""
    y = _num(kWh_kWp_an, "producția specifică (kWh/kWp/an)", 300, 2500)
    p = _num(kWp, "puterea (kWp)", 0.01, 100000)
    return {"sursa": "valoare introdusă de proiectant", "kWh_an": y * p, "kWh_kWp_an": y, "kWp": p, "lunar": [],
            "pierderi_pct": None, "parametri": {}, "mesaj": f"producție estimată {y * p:,.0f} kWh/an".replace(",", " ")}


def estimeaza(lat, lon, kWp, unghi=30, azimut=0, pierderi=None, montaj="free", timeout=15, offline=False):
    """local: cache → apel PVGIS → cache. Fără rețea / eroare → {necesita_valoare: True, mesaj, url}"""
    try:
        p = parametri(lat, lon, kWp, unghi, azimut, pierderi, montaj)
    except ValueError as e:
        return {"necesita_valoare": True, "eroare": str(e), "mesaj": f"Date incomplete pentru PVGIS: {e}."}
    c = _citeste_cache()
    k = _cheie(p)
    if k in c:
        # cache pe 1 kWp (producția specifică) — scalat la puterea cerută
        y = c[k]
        r = din_raspuns(y["raspuns"], 1.0) if "raspuns" in y else None
        if r:
            f = p["peakpower"]
            r.update(kWh_an=r["kWh_kWp_an"] * f, kWp=f, lunar=[dict(x, kWh=(x["kWh"] or 0) * f) for x in r["lunar"]],
                     sursa=r["sursa"] + " (cache)")
            r["mesaj"] = f"producție estimată {r['kWh_an']:,.0f} kWh/an ({r['kWh_kWp_an']:,.0f} kWh/kWp/an)".replace(",", " ")
            return r
    url = URL_API + "?" + urllib.parse.urlencode(dict(p, peakpower=1))
    if offline:
        return {"necesita_valoare": True, "url": cerere_url(lat, lon, kWp, unghi, azimut, pierderi, montaj),
                "mesaj": "Mod offline: introduceți producția specifică (kWh/kWp/an) din PVGIS."}
    try:
        with urllib.request.urlopen(url, timeout=timeout) as fh:
            raspuns = json.loads(fh.read().decode("utf-8"))
        r = din_raspuns(raspuns, 1.0)
    except Exception as e:                       # fără rețea, proxy, PVGIS indisponibil, răspuns neașteptat
        return {"necesita_valoare": True, "url": cerere_url(lat, lon, kWp, unghi, azimut, pierderi, montaj),
                "eroare": type(e).__name__,
                "mesaj": "PVGIS nu poate fi accesat acum (fără rețea sau serviciu indisponibil). Introduceți producția "
                         "specifică (kWh/kWp/an) — o găsiți pe re.jrc.ec.europa.eu/pvg_tools pentru amplasament."}
    c[k] = {"raspuns": raspuns}
    _scrie_cache(c)
    return estimeaza(lat, lon, kWp, unghi, azimut, pierderi, montaj, timeout)


def paragraf_memoriu(rez, kWp=None):
    """paragraful din memoriul tehnic al prosumatorului / CEF"""
    if not rez or rez.get("necesita_valoare"):
        return ""
    kw = rez.get("kWp") or kWp
    kw = (f"{float(kw):.2f}".rstrip("0").rstrip(".").replace(".", ",")) if isinstance(kw, (int, float)) else (kw or "—")
    t = (f"Producția anuală estimată a instalației ({kw} kWp) este de aproximativ "
         f"{rez['kWh_an']:,.0f} kWh/an".replace(",", " ")
         + (f", adică {rez['kWh_kWp_an']:,.0f} kWh/kWp/an".replace(",", " ") if rez.get("kWh_kWp_an") else "")
         + f" (sursa: {rez['sursa']}")
    par = rez.get("parametri") or {}
    if par.get("unghi") is not None:
        t += f"; înclinare {par['unghi']}°, azimut {par.get('azimut')}° (0 = sud)"
    if rez.get("pierderi_pct") is not None:
        t += f"; pierderi totale {rez['pierderi_pct']:.1f} %".replace(".", ",")
    return t + "). Valoarea este o estimare pe baza datelor climatice medii și nu constituie o garanție de producție."
