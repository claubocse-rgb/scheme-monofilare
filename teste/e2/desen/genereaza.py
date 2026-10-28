"""E2 — randările de verificare ale desenului (date inventate, anonime): pachetele de planșe A3 ale unor CEF /
prosumator, etichetele de tablou, schema de ușă, curbele timp-curent, tabelul de revizii.
Rulare:  cd /home/claude/sm && python3 teste/e2/desen/genereaza.py   (PNG dacă există cairosvg)"""
import pathlib
import sys

RAD = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAD))
from engine import constructor, layout, planse, presets, render_svg  # noqa: E402

OUT = pathlib.Path(__file__).parent
INV_A = {"producator": "Producător A", "model": "INV-60K", "Pn_kW": 60, "Iac_max_A": 90.0, "nr_MPPT": 4}
INV_B = {"producator": "Producător B", "model": "INV-30K", "Pn_kW": 30, "Iac_max_A": 45.0}
MODUL = {"producator": "Modul X", "model": "MX-450", "Pmax_W": 450, "Voc_V": 49.5, "Isc_A": 11.6, "Vmpp_V": 41.5,
         "Impp_A": 10.85}
AL = {"material": "Al", "izolatie": "XLPE", "metoda": "E"}
REV = [{"rev": "0", "data": "09.2026", "descriere": "Emisă pentru autorizare", "intocmit": "ing. A", "verificat": "ing. B"},
       {"rev": "1", "data": "10.2026", "descriere": "Actualizare ATR — QG motorizat", "intocmit": "ing. A"}]

CAZURI = {
    "cef_2inv": {"tip_schema": "cef", "retea": "tri", "schema_pamant": "TN-S", "kWp": 122,
                 "invertoare": [dict(INV_A, n=2, L_m=20)], "modul": MODUL,
                 "string": {"n_module": 17, "n_stringuri_paralel": 2, "n_MPPT": 4}, "racord": "tg_existent",
                 "Ik3_TG_kA": 20, "L_racord_m": 30, "monitorizare": True, "protectie_interfata": {"ups_VA": 1000}},
    "cef_tipic8": {"tip_schema": "cef", "retea": "tri", "schema_pamant": "TN-S", "kWp": 490,
                   "invertoare": [dict(INV_A, n=8, L_m=35)], "modul": MODUL,
                   "string": {"n_module": 17, "n_stringuri_paralel": 2, "n_MPPT": 4},
                   "racord": "pt", "pt_Sn_kVA": 630, "pt_existent": True, "L_racord_m": 25,
                   "cablu_C0": dict(AL, S_fortat=240, n_fortat=2),
                   "QG": {"tip": "MCCB", "In_A": 800, "electronic": True, "motorizat": True},
                   "monitorizare": True, "protectie_interfata": {"ups_VA": 1000}},
    "cef_cascada": {"tip_schema": "cef", "retea": "tri", "schema_pamant": "TN-S", "kWp": 260,
                    "tablouri_intermediare": [
                        {"nume": "TE-1", "L_m": 25, "cablu": dict(AL, S_fortat=50), "prot_tip": "gG", "In_A": 100,
                         "invertoare": [dict(INV_B, n=2, L_m=8, prot_tip="MCB", protectie={"In_A": 63})]},
                        {"nume": "TE-2", "L_m": 40, "cablu": dict(AL, S_fortat=70), "invertoare": [dict(INV_B, n=2, L_m=12)]},
                        {"nume": "TE-3", "L_m": 30, "cablu": dict(AL, S_fortat=95), "prot_tip": "MCCB", "In_A": 200,
                         "invertoare": [dict(INV_A, n=2, L_m=10)]}],
                    "racord": "pt", "pt_Sn_kVA": 630, "pt_existent": True, "L_racord_m": 20,
                    "cablu_C0": dict(AL, S_fortat=185, n_fortat=2),
                    "QG": {"tip": "MCCB", "In_A": 400, "electronic": True, "motorizat": True, "Icu_kA": 36},
                    "monitorizare": True, "protectie_interfata": {"ups_VA": 1000}},
    "prosumator": {"tip_schema": "prosumator", "retea": "mono", "schema_pamant": "TN-C-S", "kWp": 5.2,
                   "invertor": {"producator": "Producător C", "model": "INV-5K", "Pn_kW": 5, "Iac_max_A": 22.8},
                   "Pn_inv_kW": 5, "In_Q_bransament_A": 32, "L_inv_m": 4, "L_coloana_m": 30, "contor_productie": True,
                   "monitorizare": {"smart_meter": {"model": "SM-1"}, "rs485": True}},
}
CASA = {"tip_schema": "locuinta", "retea": "tri", "schema_pamant": "TN-C-S", "Pi_kW": 22, "Pa_kW": 15, "L_bransament_m": 20,
        "circuite": [{"nume": "Iluminat", "tip": "iluminat", "P_kW": 1.2}, {"nume": "Prize living", "tip": "prize"},
                     {"nume": "Prize bucătărie", "tip": "prize"}, {"nume": "Plită", "tip": "plita", "P_kW": 7.2},
                     {"nume": "Boiler", "tip": "boiler", "P_kW": 2}, {"nume": "Pompă de căldură", "tip": "pompa_caldura", "P_kW": 6}]}


def png(svg, fn, w=2400):
    try:
        import cairosvg
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(OUT / fn), output_width=w)
    except ImportError:
        (OUT / fn.replace(".png", ".svg")).write_text(svg, encoding="utf-8")


def main():
    for nume, inp in CAZURI.items():
        m, _ = constructor.genereaza(inp)
        if nume == "cef_2inv":
            m["revizii"] = REV
        for cod, mp in planse.planse_din_model(m):
            png(render_svg.render(layout.build(mp), cod), f"{nume}_{planse.nume_fisier(cod)}.png")
        for i, (svg, _, _) in enumerate(planse.etichete_tablou(m)):
            png(svg, f"{nume}_etichete_{i + 1}.png", 1800)
        print(nume)
    try:
        m, _ = constructor.genereaza(CASA)
    except Exception:       # noqa: BLE001
        m = presets.get("tg")
    m["revizii"] = REV
    png(render_svg.render(layout.build(m), "casa"), "casa_plansa_revizii.png")
    for i, (svg, _, _) in enumerate(planse.etichete_tablou(m)):
        png(svg, f"casa_etichete_{i + 1}.png", 1800)
    for nt, mu in planse.scheme_usa(m):
        png(render_svg.render(layout.build(mu), nt), f"casa_usa_{planse.nume_fisier(nt)}.png", 1800)
    m = presets.get("tg")
    for nt, mu in planse.scheme_usa(m):
        png(render_svg.render(layout.build(mu), nt), f"tg_usa_{planse.nume_fisier(nt)}.png", 1800)
    for i, (svg, _, _) in enumerate(planse.etichete_tablou(m)):
        png(svg, f"tg_etichete_{i + 1}.png", 1800)


if __name__ == "__main__":
    main()
